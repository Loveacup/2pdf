---
name: 2pdf
description: "Typeset Markdown/Obsidian notes to styled PDF/PNG/HTML/WeChat; perform PDF merge/split/rotate/watermark/encrypt, basic text/table extraction, simple OCR, create PDFs, and fill forms. Structured document-to-Markdown parsing is handled by sibling 2md. Triggers: md to pdf, markdown to pdf, 转 PDF, Obsidian 导出 PDF, 笔记转 PDF, export note to PDF, merge/split PDF, fill PDF form, PDF edit."
version: 2.0.0
author: AlexCai
license: Proprietary. LICENSE.txt has complete terms
---

# PDF Processing Skill

> **Source repo**: https://github.com/Loveacup/2pdf (standalone skill). From its repository root, initialize with `python3 scripts/maintenance.py init`; check dependency reminders with `python3 scripts/maintenance.py check-updates`.

## Overview

One skill, independent execution chains. Pick the chain from the user's goal; never swap one engine for another as a silent fallback.

| User task | Execution chain |
|---|---|
| Markdown/Obsidian → typeset PDF/PNG/HTML/WeChat | `scripts/md2pdf_chrome.py`, venv `~/.venvs/pdf-skill`, its own `--setup`/`--preflight`/`--verify` (below) |
| Merge/split/rotate/watermark/encrypt, basic text & table extraction, simple OCR, create PDFs | Tools in `references/pdf-operations.md`; a tool the user names wins |
| Read/fill fillable fields, or fill by coordinates | `references/forms.md` + its helper scripts (Marker's Form *extraction* is not form *filling*) |
| Document → Markdown with extracted images/visual analysis or structured parsing | **Use [2md](https://github.com/Loveacup/2md/blob/main/SKILL.md)** |

Routing rules:
- Plain text/table extraction stays on the light PDF tools; document-to-Markdown parsing belongs to sibling 2md.
- "Process this PDF" with no target result → ask which result is wanted before choosing a chain.
- Multi-stage tasks are explicit file hand-offs. Keep a complete 2md output directory when typesetting with `scripts/md2pdf_chrome.py`, so Markdown-relative images remain resolvable.
- Typesetting and parsing failures are reported within their own chain; neither silently falls back to the other. The skills exchange files only and never import each other.

Reference map:
- **Markdown to PDF** (primary typesetting workflow): `scripts/md2pdf_chrome.py` — see below
- **PDF operations** (merge, split, extract, create): see `references/pdf-operations.md`
- **Document parsing**: use [2md skill](https://github.com/Loveacup/2md/blob/main/SKILL.md)
- **Markdown to PDF internals** (pagination, font sizing, Mermaid, callouts): see `references/md2pdf-details.md`

## Quick Start

```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Markdown to Beautiful PDF (CJK-safe)

Convert Obsidian Flavored Markdown to styled PDF using Chromium/system CJK fonts, with actual font diagnostics and platform-specific visual acceptance.

**Script**: `scripts/md2pdf_chrome.py`
**Prerequisites**: From the standalone repository root, run `python3 scripts/maintenance.py init`. It reuses a healthy `~/.venvs/pdf-skill`; explicit setup may install missing packages and download Chromium/pinned vendor assets. Ordinary conversions are offline by default and never download missing vendor assets. Node.js and a launchable Playwright Chromium or system Chrome are required.

`python3 scripts/maintenance.py check-updates [--json]` queries official PyPI/npm metadata for runtime packages and bundled Mermaid/highlight.js/KaTeX, plus the Playwright package resolved by the current Node setup. It reports reminders only and never installs upgrades. JSON uses schema version 1 (`checked_at`, `overall`, `updates` with `name/source/current/pinned/latest/status/update_available/url`); unavailable metadata or installed versions are marked `unavailable`, and the command exits nonzero when any version cannot be verified.

Avoid relying on legacy automatic bootstrap for installation: when a direct render starts without Markdown dependencies, it may create a persistent environment and install unpinned package versions. Use the explicit maintenance command to initialize; ordinary conversion does not run dependency upgrades.

### Usage

```bash
python scripts/md2pdf_chrome.py <md_file> [pdf_file] [header_text] \
  [--format pdf|png|html|wechat] [--browser playwright|chrome|auto] \
  [--theme NAME] [--page-size A4|430x932] \
  [--verify | --verify-strict] [--require-text TEXT] [--properties] [--byline] [--preview DIR] \
  [--allow-diagram-errors] [--no-metadata] \
  [--resource-root DIR] [--allow-origin ORIGIN] \
  [--sm PATTERN] [--xs PATTERN] [--sm-after PATTERN] [--xs-after PATTERN]

# First use / environment repair; healthy venv is reused
python3 scripts/maintenance.py init

# Official dependency-version reminders; never installs updates
python3 scripts/maintenance.py check-updates
python3 scripts/maintenance.py check-updates --json

# Legacy direct setup/revalidation
python3 scripts/md2pdf_chrome.py --setup

# Render examples
python scripts/md2pdf_chrome.py report.md
python scripts/md2pdf_chrome.py report.md ~/output/report.pdf "My Report Title"
python scripts/md2pdf_chrome.py note.md out.pdf --browser auto --verify
python scripts/md2pdf_chrome.py note.md out.pdf --verify-strict --require-text "Signed: Alex"
python scripts/md2pdf_chrome.py report.md output.pdf --theme academic --sm "开发路线图" --xs-after "变更历史"
python scripts/md2pdf_chrome.py notes/report.md out.pdf --resource-root ./assets
python scripts/md2pdf_chrome.py report.md out.html --format html --allow-origin https://images.example.org
```

### Output formats & resilience

| Flag | Effect |
|------|--------|
| `--format pdf\|png\|html\|wechat` | Output format. `pdf` (default), `png` (full-page screenshot), `html` (standalone), `wechat` (CSS inlined for WeChat paste) |
| `--browser playwright\|chrome\|auto` | `playwright` (default, bundled Chromium); `chrome` (system Chrome via Playwright `executablePath`); `auto` tries bundled → system Chrome. All use the same resource policy and fresh context, never a personal profile. Prints actual `engine` + `executable` |
| `--page-size A4\|WxH` | `A4` (default) or a custom mobile size like `430x932`. Validated up front |
| `--setup` | One-time idempotent bootstrap: persistent venv + deps + Playwright Chromium + pinned vendor assets (Mermaid/hljs/KaTeX JS, CSS, WOFF2 and license; `vendor.lock.json`) + smoke render acceptance. Alias: `--preflight --fix` |
| `--preflight [--json]` | Health-check current interpreter, deps, browsers, pandoc, vendored assets, persistent venv — no rendering. Exit 0 ok / 1 fatal / 2 missing doc |
| `--verify` | Verify staged PDF file/magic/pages, Mermaid-source/error text, diagram/formula counts and metadata. Formula counts compare source parser ↔ PDF total ↔ rendered. Any error fails; warnings/skips remain diagnostic |
| `--verify-strict` | Implies `--verify`; also fails skipped required checks (e.g. pypdf or diagram/formula-count metadata for relevant source). Optional/not-applicable checks may skip. Image-only pages remain valid |
| `--require-text TEXT` | Repeatable PDF body-text sentinel; implies `--verify`. Missing text fails delivery. Opt in to the expected source content; text is not inferred from image pixels |
| `--allow-diagram-errors` | Explicit waiver for completed Mermaid runs with failed blocks (default: **exit 3, no output**). Prints `MERMAID_WAIVER` with honest total/rendered/errors and visible failure placeholders. Timeouts never proceed; `--verify` still rejects count mismatches |
| `--no-bootstrap` | Disable the automatic venv self-healing re-exec |
| `--fallback pandoc` | **Breaking change (P0-B): refuses conversion.** The old pandoc/Chrome CLI path cannot enforce the same request policy. Migrate to `--browser chrome` / `auto`, or initialize bundled Chromium |
| `--no-metadata` | Skip source frontmatter and diagram/formula-count PDF metadata. Combining with strict verification on diagram/formula documents fails the required count check |
| `--properties` | Render YAML frontmatter as a title-adjacent property card; list values use `·`, while `author`, `cli`, and `models` remain in the byline |
| `--byline` | Render frontmatter `author`, `cli`, and `models` beneath H1 as 撰写 / 协作 CLI / 参与模型 rows; missing fields are omitted |
| `--preview DIR` | Export page 1 and pages containing named Mermaid charts as 72-dpi PNGs; print their paths |
| `--resource-root DIR` | Repeatable explicit extra local resource root; default is only the source file's real parent directory. URL-decoded paths and symlinks are checked against real roots |
| `--allow-origin ORIGIN` | Repeatable exact HTTP(S) origin authorization (`scheme://host[:port]`, no path). Without it, remote resources fail before delivery. Every request and redirect is checked; no cookies, proxy environment or implicit authentication |

**Themes** auto-discover from `scripts/themes/*.css` (currently 18; names are listed by the renderer). `--theme auto` routes on visible prose: URLs, code spans/blocks, and Markdown table rows do not add keyword signals; code length is CJK-aware and Mermaid markup does not count as executable-code density. Low-code A4 documents route among light palettes.

**Source frontmatter → PDF metadata**: `title` / `author` / `description` / `tags` / `aliases` / `created` / `modified` map to `/Title /Author /Subject /Keywords /CreationDate /ModDate`. `/Author` is written only when frontmatter explicitly declares `author` (privacy guard); `--no-metadata` disables the whole step.

**Policy-preserving fallback**:
1. **Primary** — Playwright bundled Chromium (`--browser playwright`, default).
2. **System Chrome** — `--browser chrome`, or `auto` when bundled Chromium fails; the same isolated Playwright request interception applies.
3. **Fail closed** — when neither Chromium can render, conversion fails. The former pandoc lifeboat is refused instead of bypassing resource safety.

**Quality-first fail-fast** (the 7-02 `==>` incident hardening — four defense layers):
1. **Fence-first preprocessing** — code fences & inline code are extracted to placeholders BEFORE `==highlight==`/wikilink/tasklist conversions, so Mermaid thick arrows (`A ==> B`) and code containing `[[ ]]`/`- [ ]` are never mangled.
2. **Render-time fail-fast** — every Mermaid block is `mermaid.parse()`-prechecked then rendered individually in the page; any failure aborts with exit 3, block number, error message and source head — **no PDF is produced**. Engine downgrade and the pandoc lifeboat are NOT triggered by diagram content errors.
3. **Parse precheck reporting** — errors are reported in seconds (before full page render), so the agent can fix the md immediately.
4. **Independent verify gate** — `--verify` checks the staged PDF in a separate process before publishing. PDF output is staged beside its target and atomically replaced only after successful rendering and the requested gate; failures preserve an existing target byte-for-byte and never print a success marker. Status and skip reasons are printed. `--verify-strict` rejects skipped required checks.

**Cross-platform (mac + Windows)**: CJK font stacks include PingFang/YaHei (+ Consolas/Cascadia for code); system-Chrome discovery covers `/Applications`, `%ProgramFiles%`, Linux paths; Playwright cache detection covers `Library/Caches`, `.cache`, `%LOCALAPPDATA%`; no `/tmp` hardcoding (uses the platform temp dir); vendored assets live next to `scripts/`. Deploy/sync shell scripts remain mac-side; on Windows just `git pull` + `--setup`.

**P1 font evidence:** all output formats await `document.fonts.ready`, query actual
Chromium platform fonts and print a machine-readable `FONT_REPORT` (faces,
PostScript names, glyph counts, missing-glyph diagnostics). LastResort/notdef
failures stop atomic delivery; macOS also checks CoreText glyph IDs for each
text node's actual fonts. No system font is bundled or downloaded. Inspect final
pages as well: font-ready and cmap coverage alone do not prove visual correctness.
macOS P1 corpus is verified; Windows is explicitly **not yet visually verified**.

### Math (primary CLI, all four output formats)

No new flag: `$$…$$` is display math, `$…$` inline math. Dollar boundaries follow
pandoc `tex_math_dollars`: inline opening `$` cannot be followed by whitespace;
closing `$` cannot be preceded by whitespace or followed by a digit. `\$` is a
literal dollar; fenced/inline code is protected first. Unpaired delimiters stay
literal. Supported TeX is [KaTeX's function subset](https://katex.org/docs/supported),
with pinned **0.16.22**, `strict: "error"`, `trust: false`, `throwOnError: true`.
Trust-dependent HTML/URL/image commands are rejected. No formula HTML/scripts run.
Invalid/unsupported formulas report ordinal + TeX snippet and exit 3 without
publishing or falling back; `--allow-diagram-errors` does not waive formula errors.
JS/CSS/WOFF2 fonts are pinned/hash-checked local vendor; explicit setup provisions
them with the MIT license. Ordinary no-formula documents load no math assets.
`MATH_STAT` and `/JZMathTotal` / `/JZMathRendered` reconcile source/render counts.


### Claude Code Relay Workflow

The script and Claude Code work as a team. The script handles rendering mechanics, Claude Code handles content intelligence.

```
Step 1: Script runs → outputs Outline + PDF (with defaults)
Step 2: Claude Code reads Outline + document head (first ~5 lines) and tail (last ~20 lines) → decides layout
Step 3 (if needed): Claude Code re-runs with flags → script wraps matching content and renders
```

**CLI directives** (script automatically wraps matching content, no file editing needed):

| Flag | Effect |
|------|--------|
| `--theme NAME` | Set visual theme: `blue` (default), `dark`, `academic`, `auto` — auto-discovered from `scripts/themes/*.css`. `auto` uses the content-aware router. |
| `--sm "heading text"` | Wrap children of matching heading in `text-sm` (12px) |
| `--xs "heading text"` | Wrap children of matching heading in `text-xs` (11px) |
| `--sm-after "text"` | Wrap from matching line to end of document in `text-sm` (12px) |
| `--xs-after "text"` | Wrap from matching line to end of document in `text-xs` (11px) |

`--sm`/`--xs`: case-insensitive substring match against **heading text**, wraps child sections.
`--sm-after`/`--xs-after`: case-insensitive substring match against **any line**, wraps from that line to EOF. Use for non-heading content like metadata/changelog at document end.

**Manual markers** can also be inserted into Markdown (raw HTML, preserved by `md_in_html` extension):

| Marker | Effect |
|--------|--------|
| `<div style="page-break-before:always"></div>` | Force page break |
| `<div class="text-sm" markdown="1">...</div>` | Shrink to 12px |
| `<div class="text-xs" markdown="1">...</div>` | Shrink to 11px |

**P1 pagination:** Chromium fragments the final print flow. Headings stay with the
first content fragment; short code/Callout/list/table blocks request keep-together,
while multi-page blocks may split. Images fit the printable area. Explicit page
break markers are preserved; no fixed-height page-position simulation is used.

**Decision heuristics** for Claude Code (not hardcoded in script):
- **Outline**: 5+ child headings with avg <500c → `--sm` to shrink the section
- **Head/Tail**: metadata (版本/日期/作者) or changelog (变更历史) → `--xs-after`
- Section <300c → don't break before it, let it flow with neighbors
- Section >2000c → consider breaking before it
- Short Phase (e.g. Phase 1: 226c) → no break before it

Most documents need zero intervention (one run). Only complex documents with mixed section sizes or metadata/changelog need a second pass with flags.

### Pipeline

```
Obsidian MD → preprocess → Python markdown (md_in_html) → section wrap → styled HTML + JS → Playwright Chromium → PDF
```

1. **Preprocess**: Strip YAML frontmatter, convert all 26 Obsidian callout types (including foldable), remove wikilinks, convert highlights (`==text==` → `<mark>`), convert task lists, embed local images as base64
2. **Convert**: Python `markdown` library with extensions: `tables`, `fenced_code`, `toc`, `sane_lists`, `md_in_html`, `footnotes`
3. **Section Wrap**: Post-process HTML — wrap `<h2>` into `<section class="doc-section">`, wrap `<h3>` into `<div class="doc-subsection">`
4. **Mermaid**: Convert mermaid code blocks → `<div class="mermaid">`, load pinned Mermaid JS vendored next to the script (`scripts/mermaid.min.js` + `vendor.lock.json`, downloaded by `--setup`), auto-scale SVG
5. **Syntax Highlighting**: pinned local highlight.js and theme-aware CSS (atom-one-dark / atom-one-light), embedded into the invocation HTML; no CDN fallback
6. **Content Adaptation JS**: A4 tables keep readable font sizes, wrap cells/code and repeat headers; oversized rows may split. Unreadable/overflowing PDF tables fail with table/cell diagnostics instead of column-count shrinking. Section density classes and mobile-only cards remain.
7. **Render**: await fonts, completed Mermaid status and decoded images (including images created by rendering); invisible/overflowing diagrams fail. No fixed sleeps or timeout-and-proceed. Then `page.pdf()` with A4 format + page numbers + native bookmarks & accessibility tags (`outline: true, tagged: true`). `IMAGE_STAT` records decoded dimensions; offline vendors need no CDN.
8. **Post-process and deliver**: Keep **all** generated pages, including bitmap/vector-only pages, short endings and intentional blanks. Write metadata via pypdf `clone_from` (preserves native outline/tags); use pypdf bookmarks only when no native outline exists. Verify the staged PDF when requested, then atomically publish it.

For pagination rules, font sizing tables, Mermaid details, callout types, and CSS customization, see `references/md2pdf-details.md`.

### Pitfalls
**P0-B resource migration (breaking):** all four formats are offline by default. Local images/styles/fonts/SVG/iframe content must be beneath the real source directory; grant intentional sibling assets with repeatable `--resource-root DIR`. Move remote assets locally or authorize each exact origin with repeatable `--allow-origin ORIGIN`; cross-origin redirects need their own authorization. Resources are recursively frozen as data URIs before Chromium, then guarded again by CSP and request interception. Author-written scripts and event handlers never run; only controlled render scripts do. Missing vendor files require explicit `maintenance.py init`, never an automatic CDN fallback. Allowed remote services may themselves forward data; that server-side behavior is outside this policy.

**All-format isolated delivery:** HTML, Node scripts and post-processing live in one private per-invocation staging directory. Same normalized output targets are nonblocking kernel-locked: one concurrent writer fails immediately; different targets remain independent. Normal exit, exceptions and handled SIGINT/SIGTERM cancellation remove the invocation's stage and release ownership. Hard kills may leave a private directory, but it is never reused. New accepted artifacts atomically replace prior outputs; failures preserve prior bytes. Kernel lock files carry no ownership state and cannot permanently block later runs.

**Local image failures stop delivery.** Missing/unreadable images report their source; browser decoding rejects corrupt images before publication. Legacy `md2pdf_browser.py` uses the same resource, staging, ownership and cancellation safeguards and accepts `--resource-root`, `--allow-origin`, `--verify`, `--verify-strict`, and `--require-text`.


**Mermaid failures never reach the PDF (by design).** If a render exits with code 3 and a `图#N` error listing, the md has a genuine Mermaid syntax error — fix the listed block and re-run. Historical note: thick arrows `==>` used to be destroyed by the highlight preprocessor (2026-07-02 incident); fence-first protection fixed this permanently, so `==>` is safe to use now.

**Playwright PDFs are heavy.** A 7-page CJK document can produce a ~1.9MB PDF because Chromium embeds all fonts and full CSS. This routinely times out when delivering via messaging platforms (Telegram MEDIA delivery, etc.).

**Compression is ineffective.** Ghostscript (`-dPDFSETTINGS=/screen`) only shaves ~20% off font-heavy Playwright PDFs. `weasyprint` requires system libs (`libgobject-2.0-0`, pango) often missing. `fpdf2` chokes on `.ttc` system fonts. Splitting pages helps only marginally.

**Delivery fallback strategy (proven):**
1. Generate the styled PDF with `md2pdf_chrome.py` — save to local disk
2. Send the **markdown source** as a text message to the user (it's ~12KB)
3. Tell the user the PDF path on local disk for direct opening
4. If local delivery is not an option, consider `md2pdf_browser.py` which uses the same Playwright pipeline but may handle differently

**Prefer this pattern when the user asks "make a PDF and send it":**
- Generate PDF → note size → if >500KB, preemptively send markdown + local path
- Don't waste turns on compression — it won't reduce enough for Playwright PDFs

## Quick Reference

| Task | Tool | Details |
|------|------|---------|
| **Markdown to PDF** | `scripts/md2pdf_chrome.py` | Playwright Chromium, CJK-safe |
| Merge/Split/Rotate PDFs | pypdf | `references/pdf-operations.md` |
| Extract text | pdfplumber | `references/pdf-operations.md` |
| Extract tables | pdfplumber | `references/pdf-operations.md` |
| Create PDFs | reportlab | `references/pdf-operations.md` |
| CLI merge/split | qpdf / pdftk | `references/pdf-operations.md` |
| OCR scanned PDFs | pytesseract | `references/pdf-operations.md` |
| Fill PDF forms | pypdf / pdf-lib | `references/forms.md` |
| pypdfium2, pdf-lib | advanced libs | `references/advanced.md` |
| Page headers/footers | `scripts/md2pdf_chrome.py` | Playwright, auto page numbering |
