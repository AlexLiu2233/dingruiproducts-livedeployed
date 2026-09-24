#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""download_preview.py -- fetch a local, offline copy of the Dingrui Scholars
notes site's FREE PREVIEW TIER, without cloning the source repo.

What this downloads
--------------------
Only the pages tagged tier="free" in the site's preview-manifest.json, plus the
site shell (home page, subject index pages, logo) and the static assets those
pages need to render (KaTeX/JSXGraph vendor files, KaTeX web fonts, figure
PNGs). It never downloads a page that is not explicitly listed in the
manifest.

Locked / gated study guides, practice sets and solutions are NOT included and
cannot be obtained through this script. Those pages are only readable on the
live site itself, and only after the reader's email has been approved and
unlocked by Dingrui Scholars staff (see the site's own sign-up / unlock flow).
This script has no way to bypass that -- it is a convenience mirror of the
already-public preview tier, not a bulk-download or unlock tool.

Why you must serve it over HTTP, not open the files directly
--------------------------------------------------------------
Every downloaded page loads KaTeX (and, on some pages, JSXGraph) from a
root-relative path: /vendor/katex/katex.min.css, /vendor/katex/katex.min.js,
etc. Root-relative paths only resolve under an HTTP origin -- opened directly
from disk via a file:// URL, the browser cannot find /vendor/... relative to
an arbitrary folder, and all the math on the page silently fails to render.
Always serve the downloaded copy with a local HTTP server (this script can
do it for you with --serve, or run one yourself) and open it via
http://localhost:<port>/ -- never double-click the downloaded index.html.

Usage
-----
    python download_preview.py [--dest DIR] [--site URL] [--serve] [--port 8000] [--force]

    --dest DIR   Where to write the downloaded copy. Default: ./dingrui-preview
    --site URL   Origin to download from. Default: https://notes.dingruischolars.com
    --serve      After downloading, start a local HTTP server rooted at DIR and
                 keep it running in the foreground (Ctrl+C to stop).
    --port N     Port for --serve (or for the "next step" instructions printed
                 without --serve). Default: 8000
    --force      Re-download every file even if it already exists locally.

Requires only the Python standard library. Python 3.8+, any OS.
"""
from __future__ import annotations

import argparse
import functools
import html.parser
import http.server
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_SITE = "https://notes.dingruischolars.com"
DEFAULT_DEST = "dingrui-preview"
MANIFEST_NAME = "preview-manifest.json"
RETRIES = 3
RETRY_SLEEP_SECONDS = 1.0
TIMEOUT_SECONDS = 20

# Extensions we will follow as "assets" when discovered inside downloaded
# .html/.css files. Deliberately excludes .html -- we never fetch a page that
# isn't explicitly in the manifest. Font formats are limited to .woff2: the
# site self-hosts KaTeX fonts as .woff2 only (see FONT_EXTENSIONS below for
# why the legacy .woff/.ttf/.otf/.eot @font-face fallbacks are filtered out
# before we ever queue them, rather than left to 404 here).
ASSET_EXTENSIONS = (
    ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".gif",
    ".woff2",
)

# Legacy web-font formats that vendor CSS (e.g. KaTeX's @font-face rules)
# still lists as fallbacks but that this site does not actually host -- only
# .woff2 is published under vendor/*/fonts/. Requesting these 404s (and, with
# retries, multiplies into dozens of failed requests per page), so
# find_css_asset_refs() drops them before they ever reach the download queue.
FONT_FALLBACK_EXTENSIONS = (".woff", ".ttf", ".otf", ".eot")

SKIP_SCHEMES = ("http://", "https://", "//", "data:", "mailto:", "javascript:", "tel:")


class _AssetRefParser(html.parser.HTMLParser):
    """Collect href=/src= attribute values from an HTML document."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.refs.append(value)


def find_html_asset_refs(html_text):
    """Return raw href/src attribute values found in an HTML document."""
    parser = _AssetRefParser()
    try:
        parser.feed(html_text)
    except Exception:
        # Malformed markup shouldn't abort the whole download; fall back to a
        # permissive regex pass over the raw text.
        return re.findall(r'(?:href|src)="([^"]*)"', html_text)
    return parser.refs


CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)")


def find_css_asset_refs(css_text):
    """Return raw url(...) targets found in a CSS document.

    KaTeX's stylesheet declares three @font-face src formats per font
    (.woff2, .woff, .ttf), but vendor/katex/fonts/ on the live site only
    ships .woff2 -- the other two were never published. Queuing them anyway
    means every page fetch spends 3 retries x 2 dead formats x dozens of
    fonts on guaranteed 404s. Filter them out here, at the source, instead of
    treating the failure as an expected non-fatal warning downstream.
    """
    refs = [m.group(2) for m in CSS_URL_RE.finditer(css_text)]
    return [r for r in refs if not _is_dead_font_fallback(r)]


def _is_dead_font_fallback(ref):
    path_part = ref.split("?", 1)[0].split("#", 1)[0]
    return path_part.lower().endswith(FONT_FALLBACK_EXTENSIONS)


def is_skippable_ref(ref):
    ref = ref.strip()
    if not ref:
        return True
    lower = ref.lower()
    if lower.startswith(SKIP_SCHEMES):
        return True
    if ref.startswith("#"):
        return True
    return False


def looks_like_asset_path(ref):
    """Reject anything that isn't a clean, extension-bearing local path.

    Guards against incidental href="..."/src="..." matches inside inline JS
    string-concatenation (e.g. dynamically built signup links), which are not
    real static assets and would not resolve to a downloadable file anyway.
    """
    path_part = ref.split("?", 1)[0].split("#", 1)[0]
    if any(ch in path_part for ch in ("'", '"', "+", "\n", "\r", "<", ">")):
        return False
    lower = path_part.lower()
    if not lower.endswith(ASSET_EXTENSIONS):
        return False
    return True


def resolve_ref(ref, referrer_repo_path):
    """Resolve an href/src value found in `referrer_repo_path` to a
    repo-relative posix path (forward slashes, no leading slash).

    `referrer_repo_path` is itself repo-relative (e.g.
    "AP Calculus/Study Guides/Unit_1_Limits_and_Continuity.html").
    """
    ref = ref.split("?", 1)[0].split("#", 1)[0]
    if ref.startswith("/"):
        return ref.lstrip("/")
    ref_dir = os.path.dirname(referrer_repo_path)
    joined = "/".join([ref_dir, ref]) if ref_dir else ref
    # Normalize ../ and ./ segments using posixpath semantics, without
    # touching the local OS separator.
    parts = []
    for seg in joined.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
            continue
        parts.append(seg)
    return "/".join(parts)


def repo_path_to_url(site, repo_path):
    """Turn a repo-relative posix path into a full URL, percent-encoding each
    path segment but leaving the slashes themselves alone."""
    segments = repo_path.split("/")
    encoded = "/".join(urllib.parse.quote(seg) for seg in segments)
    return site.rstrip("/") + "/" + encoded


def local_fs_path(dest, repo_path):
    return os.path.join(dest, *repo_path.split("/"))


def winlong(path):
    """Return a path safe to pass to Windows filesystem calls even past the
    260-character MAX_PATH limit (deep destinations, long study-guide
    filenames). No-op on other platforms or already-prefixed/relative-safe
    paths."""
    if os.name != "nt":
        return path
    abs_path = os.path.abspath(path)
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abs_path[2:]
    return "\\\\?\\" + abs_path


def fetch(url):
    """GET url, returning raw bytes. Raises on failure after caller retries."""
    req = urllib.request.Request(url, headers={"User-Agent": "dingrui-preview-downloader/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read()


def fetch_with_retries(url, retries=RETRIES):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return fetch(url), None
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(RETRY_SLEEP_SECONDS)
    return None, last_err


def download_one(site, dest, repo_path, force, seen, errors, downloaded):
    """Download one repo-relative path if not already handled. Returns the
    local file path (or None on failure)."""
    if repo_path in seen:
        return seen[repo_path]
    seen[repo_path] = None  # placeholder to prevent re-entry/dup work

    local_path = local_fs_path(dest, repo_path)
    safe_path = winlong(local_path)
    if not force and os.path.isfile(safe_path) and os.path.getsize(safe_path) > 0:
        seen[repo_path] = local_path
        return local_path

    url = repo_path_to_url(site, repo_path)
    data, err = fetch_with_retries(url)
    if err is not None:
        errors[repo_path] = str(err)
        seen[repo_path] = None
        return None

    os.makedirs(winlong(os.path.dirname(local_path)) or ".", exist_ok=True)
    with open(safe_path, "wb") as f:
        f.write(data)
    seen[repo_path] = local_path
    downloaded.append(repo_path)
    return local_path


def discover_and_queue_assets(repo_path, data, queue, seen_queued):
    """Inspect downloaded bytes (html or css) for local asset refs and add
    unseen ones to `queue`."""
    lower = repo_path.lower()
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return

    if lower.endswith(".html") or lower.endswith(".htm"):
        raw_refs = find_html_asset_refs(text)
    elif lower.endswith(".css"):
        raw_refs = find_css_asset_refs(text)
    else:
        return

    for raw in raw_refs:
        if is_skippable_ref(raw):
            continue
        if not looks_like_asset_path(raw):
            continue
        resolved = resolve_ref(raw, repo_path)
        if not resolved or resolved.lower().endswith(".html"):
            continue
        if resolved in seen_queued:
            continue
        seen_queued.add(resolved)
        queue.append(resolved)


def run_download(site, dest, force):
    manifest_url = site.rstrip("/") + "/" + MANIFEST_NAME
    print("Fetching manifest: %s" % manifest_url)
    data, err = fetch_with_retries(manifest_url)
    if err is not None:
        print("ERROR: could not fetch %s: %s" % (manifest_url, err), file=sys.stderr)
        return 1

    import json
    try:
        manifest = json.loads(data.decode("utf-8"))
    except Exception as exc:
        print("ERROR: manifest is not valid JSON: %s" % exc, file=sys.stderr)
        return 1

    manifest_files = manifest.get("files", [])
    if not manifest_files:
        print("ERROR: manifest has no 'files' entries", file=sys.stderr)
        return 1

    os.makedirs(dest, exist_ok=True)

    seen = {}
    errors = {}
    downloaded = []

    manifest_failures = []
    page_count = 0
    for repo_path in manifest_files:
        local_path = download_one(site, dest, repo_path, force, seen, errors, downloaded)
        if local_path is None:
            manifest_failures.append(repo_path)
        elif repo_path.lower().endswith(".html"):
            page_count += 1

    # BFS over discovered assets referenced by downloaded html/css files.
    asset_queue = []
    seen_queued = set()
    for repo_path in list(seen.keys()):
        local_path = seen.get(repo_path)
        if local_path is None:
            continue
        lower = repo_path.lower()
        if not (lower.endswith(".html") or lower.endswith(".htm") or lower.endswith(".css")):
            continue
        try:
            with open(winlong(local_path), "rb") as f:
                file_data = f.read()
        except OSError:
            continue
        discover_and_queue_assets(repo_path, file_data, asset_queue, seen_queued)

    asset_failures = []
    while asset_queue:
        repo_path = asset_queue.pop(0)
        local_path = download_one(site, dest, repo_path, force, seen, errors, downloaded)
        if local_path is None:
            asset_failures.append(repo_path)
            continue
        if repo_path.lower().endswith(".css"):
            try:
                with open(winlong(local_path), "rb") as f:
                    file_data = f.read()
            except OSError:
                continue
            discover_and_queue_assets(repo_path, file_data, asset_queue, seen_queued)

    manifest_pages = [p for p in manifest_files if p.lower().endswith(".html")]
    manifest_non_html = [p for p in manifest_files if not p.lower().endswith(".html")]
    asset_paths_attempted = [p for p in seen if p not in manifest_files]
    asset_paths_ok = [p for p in asset_paths_attempted if seen.get(p) is not None]

    print("")
    print("Downloaded %d manifest page(s), %d manifest shell asset(s), %d discovered asset(s)."
          % (len(manifest_pages), len(manifest_non_html), len(asset_paths_ok)))
    print("Destination: %s" % os.path.abspath(dest))

    if manifest_failures:
        print("")
        print("FAILED manifest files (%d):" % len(manifest_failures), file=sys.stderr)
        for p in manifest_failures:
            print("  %s -- %s" % (p, errors.get(p, "unknown error")), file=sys.stderr)

    if asset_failures:
        print("")
        print("Warning: %d discovered asset(s) could not be downloaded (non-fatal):"
              % len(asset_failures))
        for p in asset_failures:
            print("  %s -- %s" % (p, errors.get(p, "unknown error")))

    if manifest_failures:
        return 1
    return 0


class _RootedHandler(http.server.SimpleHTTPRequestHandler):
    pass


def serve(dest, port):
    handler = functools.partial(_RootedHandler, directory=dest)
    with http.server.ThreadingHTTPServer(("", port), handler) as httpd:
        print("Serving %s at http://localhost:%d/  (Ctrl+C to stop)" % (os.path.abspath(dest), port))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Download the free-preview tier of the Dingrui Scholars notes site for local, offline viewing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--dest", default=DEFAULT_DEST, help="Output directory (default: %(default)s)")
    parser.add_argument("--site", default=DEFAULT_SITE, help="Site origin to download from (default: %(default)s)")
    parser.add_argument("--serve", action="store_true", help="Start a local HTTP server rooted at DEST after downloading")
    parser.add_argument("--port", type=int, default=8000, help="Port for --serve / for the printed next-step instructions (default: %(default)s)")
    parser.add_argument("--force", action="store_true", help="Re-download files even if already present locally")
    args = parser.parse_args(argv)

    rc = run_download(args.site, args.dest, args.force)
    if rc != 0:
        print("\nOne or more manifest files failed to download; see errors above.", file=sys.stderr)
        return rc

    print("")
    if args.serve:
        serve(args.dest, args.port)
    else:
        print("Next step:")
        print("  cd %s && python -m http.server %d" % (args.dest, args.port))
        print("  then open http://localhost:%d/" % args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
