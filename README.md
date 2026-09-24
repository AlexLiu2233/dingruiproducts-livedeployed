# Dingrui Scholars Notes

**Bilingual (English / 简体中文) STEM study products, from high school through AP, IB and first-year university.**

📖 **Read online:** <https://notes.dingruischolars.com>  
<!-- catalog-stats:start -->
🗂️ **Full catalog:** [PRODUCTS.md](PRODUCTS.md) lists all 516 products across 12 courses and shows which ones are free.  
<!-- catalog-stats:end -->
✍️ **Get full access:** [Sign up](https://www.dingruischolars.com/signup) · [中文报名](https://www.dingruischolars.com/signup-ch)

---

> [!WARNING]
> **⏳ These notes are going offline soon.**
> We will shortly stop serving the notes on the open web. After that, they will be available **only as offline copies handed directly to enrolled students**.
>
> **For now, everything is still up:**
> - The **free preview units** stay readable on <https://notes.dingruischolars.com>, and you can [save your own copy](#host-the-free-preview-locally) today.
> - The **unlockable units** are still online behind the email gate. If you can figure out how to get past it, [the puzzle below](#-a-puzzle-for-cs-students) is your chance.
>
> **Don't wait.** Once the site comes down, anything you haven't saved will be gone for good.
>
> **⏳ 笔记即将下线。** 我们很快将停止在公开网络上提供这些笔记，之后只以离线文件的形式直接提供给正式学员。目前免费预览单元仍可在线阅读，也可以[立即下载到本地](#host-the-free-preview-locally)；需解锁的单元仍在邮箱验证之后——如果你能想办法绕过它，请看下面的[谜题](#-a-puzzle-for-cs-students)。请趁现在尽快保存。

## What you get

Each unit comes as a set of three linked products:

| Product | What it is |
|---|---|
| **Study Guide** | A long-form lesson with worked examples, diagrams and check-your-understanding quizzes |
| **Practice Questions** | An exam-style problem set written to match the course's real exam format (AP, IB, university) |
| **Solutions** | A complete worked solution for every practice question, showing the method as well as the answer |

Every page is one self-contained web app:

- **EN ⇄ 中文 in one click.** The full content is written in both languages, so bilingual students can switch languages mid-page while keeping their place.
- **Real math typesetting.** Equations are rendered with KaTeX, so they look like a textbook rather than plain text.
- **Interactive figures and quizzes.** You can drag the graphs, and the quizzes give instant feedback with explanations.
- **Dark mode and print-ready styles.** The pages are easy to read at night, and they print cleanly when you want paper.
- **Works on a phone.** The layouts are checked at phone width.

## Courses

<!-- counts:start -->
| Course | 🆓 Free preview | 🔒 Unlockable | Total |
|---|---:|---:|---:|
| AP Calculus | 9 | 21 | 30 |
| AP CSA | 9 | 3 | 12 |
| AP Physics | 9 | 12 | 21 |
| IB Math HL | 9 | 58 | 67 |
| IB Physics HL | 9 | 63 | 72 |
| IB Chemistry HL | 11 | 9 | 20 |
| High School Math | 9 | 36 | 45 |
| High School Physics | 9 | 27 | 36 |
| High School Chemistry | 9 | 33 | 42 |
| High School Biology | 9 | 27 | 36 |
| High School Computer Science | 9 | 30 | 39 |
| University Calculus | 36 | 60 | 96 |
| **Total** | **137** | **379** | **516** |
<!-- counts:end -->

The first 3 units of every course are **free**, with no account needed. The rest of the catalog unlocks on the live site with an approved student email. For a unit-by-unit list, see **[PRODUCTS.md](PRODUCTS.md)**.

## Host the free preview locally

If you're comfortable with a terminal, you can download the free preview tier and serve it from your own machine. This works offline and needs only Python 3.8+, with nothing to install.

**macOS / Linux**
```bash
curl -O https://notes.dingruischolars.com/download_preview.py
python3 download_preview.py --serve
```

**Windows (PowerShell)**
```powershell
curl.exe -O https://notes.dingruischolars.com/download_preview.py
python download_preview.py --serve
```

Then open <http://localhost:8000/>.

- The script downloads only the **free preview pages** listed in [`preview-manifest.json`](https://notes.dingruischolars.com/preview-manifest.json), together with the math fonts, scripts and figures they need, into `./dingrui-preview/`.
- Running it again skips files you already have. Use `--dest DIR` to choose another folder, `--port N` to use another port, `--force` to download everything again, or leave out `--serve` to download without serving. Run `python download_preview.py --help` to see every option.
- To serve the folder again later: `cd dingrui-preview && python -m http.server 8000`.
- **Serve the files over HTTP; don't open them by double-clicking.** The pages load KaTeX from `/vendor/`, and that path only resolves through a web server, so math shows as raw LaTeX under `file://`.
- **Unlockable products** are only available on the live site at <https://notes.dingruischolars.com>. Links to them from a local copy won't open.

## 🧩 A puzzle for CS students

The download script only gives you the free preview. The rest is online only until the site goes offline-only, so this puzzle has a deadline.

The whole site lives in a public git repository, and you may be looking at it right now. Get *all* of it onto your own machine, serve it the way this README showed you, and see what opens.

Here's a hint, if you need one: a browser treats `localhost` differently from the internet.

Solved it? Tell us how at [dingruischolars.com](https://www.dingruischolars.com). We like students who dig.

## Built with

- **[KaTeX](https://katex.org)** (MIT license) for math rendering, self-hosted under `vendor/katex/`
- **[JSXGraph](https://jsxgraph.org)** (LGPL / MIT) for interactive figures, self-hosted under `vendor/jsxgraph/`
- **Google Fonts**: DM Serif Display, Source Sans 3 and JetBrains Mono
- An AI-assisted authoring pipeline. Every page is written as plain HTML, CSS and JS with no framework, then passes automated checks for structure, math rendering, EN/ZH parity and mobile layout before it is published.

The third-party libraries keep their own licenses. The course content (all study guides, practice questions, solutions and figures) is © Dingrui Scholars, all rights reserved.

---

<sub>Maintainers: this site is generated from a private source repo by its publish script. Only this README, `PRODUCTS.md`, `download_preview.py` and `preview-manifest.json` are maintained by hand here. Don't hand-edit course pages.</sub>
