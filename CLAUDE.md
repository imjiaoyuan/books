# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A personal EPUB-to-HTML bookshelf converter. Takes EPUB files from `epub/`, converts to static HTML with inter-chapter navigation, deploys to GitHub Pages.

## Environment

Python 3.11 managed by [uv](https://docs.astral.sh/uv/). All scripts run via `uv run` which handles the virtualenv automatically.

```bash
uv pip install -r requirements.txt
```

## Commands

All scripts run with `uv run`:

```bash
# Convert all EPUBs to HTML
uv run src/epub2html.py -i ./epub -o ./public [-j N]

# Slim EPUBs (strip images/fonts/media)
uv run src/epub_slimmer.py -i epub/book.epub -o epub/book.epub

# Check EPUB structure/metadata
uv run src/epub_check.py epub/book.epub [--json]

# Clean up ads + fix metadata (pirated EPUBs)
uv run src/epub_cleanup.py -i epub/book.epub -o epub/book.epub --lang zh-CN
uv run src/epub_cleanup.py -i epub/book.epub -o epub/book.epub --lang zh-CN --extra-keywords "广告词1,广告词2"

# Edit title/chapter names interactively
uv run src/edit_epub.py -i epub/book.epub
```

There are no tests — scripts are verified by running them directly.

## Architecture

### Shared foundation (`src/utils.py`)

- `read_epub_safe(path)` — validates and opens EPUB via `ebooklib`
- `get_epub_title(book, fallback)` — extracts DC title metadata
- `natural_sort_key(s)` — natural sort for chapter filenames ("ch2" < "ch10")
- `setup_logger(name, level)` — stream-handler logger factory (only used by `epub_check.py`; other scripts use `logging.basicConfig` directly)

### Core pipeline (`src/epub2html.py` → `templates/`)

Serial for 1 EPUB, `ProcessPoolExecutor` otherwise (capped at `min(jobs, len(tasks))`).

1. Reads `.epub` files from input dir
2. Extracts document items, sorts by natural key, remaps filenames → `1.html`, `2.html`...
3. Strips `<img>`, `<image>`, `<svg>`, `<style>`, `<link>`, `<script>` and all non-href/non-id attributes
4. Injects prev/next/contents/bookshelf nav via `{placeholder}` string replacement (no Jinja2)
5. Builds TOC by walking `book.toc` (recursive `Link`/tuple), resolving hrefs to renamed files
6. Generates bookshelf at `public/index.html` listing all books sorted by title

**Templates**: Three HTML files in `templates/` (`layout_chapter.html`, `layout_toc.html`, `layout_shelf.html`). Use `{title}`, `{content}`/`{toc_content}`, `{nav}` placeholders (string replacement, no Jinja2). Hardcoded `lang="zh-CN"` — change these if adding non-Chinese books.

**Output structure**:
```
public/
├── index.html                  (bookshelf — all books)
└── books/
    └── <BookTitle>/
        ├── index.html          (book TOC)
        └── chapters/
            ├── 1.html
            └── ...
```

Both `epub2html.py` and `epub_slimmer.py` share the same concurrency pattern: serial when `len(tasks) == 1`, otherwise `ProcessPoolExecutor` capped at `min(jobs, len(tasks))`.

### EPUB slimdown (`src/epub_slimmer.py`)

Removes: image/font/audio/video items, `<img>`, `<image>`, `<svg>`, `<video>`, `<audio>`, `<iframe>` tags, `@font-face` CSS blocks. Single-file or directory mode.

### EPUB cleanup (`src/epub_cleanup.py`)

For pirated EPUBs: removes ad elements matching `AD_KEYWORDS` (笔趣阁, sobqg, txtsk, bxwx...) and strips `<a>` links to known piracy domains (`AD_DOMAINS`). Also fixes language metadata and `lang`/`xml:lang` attributes. Use `--extra-keywords` for source-specific ad text, `--no-ad-removal` to skip ad stripping, `--lang` to fix language.

### Diagnostics (`src/epub_check.py`)

Read-only scanner: file size, metadata completeness, TOC depth/preview, spine count, content-type breakdown (docs/images/styles/fonts), heading distribution (H1/H2/H3 counts/samples). Flags: missing author, missing language, no documents. Accepts paths or directory; `--json` for machine output.

### Interactive editor (`src/edit_epub.py`)

Edit EPUB title and TOC chapter titles. Saves atomically (temp-file-then-rename). Only touches `book.toc` (nav links), not `book.spine` (reading order).

## Adding new books

### Step 1 — Extract (if source is .zip)

Many Chinese sites ship epub inside a zip. Filenames are often GBK-encoded, so `unzip -l` shows garbled text. Use Python to decode and extract:

```bash
uv run python -c "
import zipfile
with zipfile.ZipFile('file.zip') as zf:
    for info in zf.infolist():
        name = info.filename.encode('cp437').decode('gbk')
        if name.endswith('.epub'):
            with zf.open(info) as s, open('/tmp/extracted.epub','wb') as d:
                d.write(s.read())
            print(f'Extracted: {name}')
"
```

If source is already `.epub`, skip to step 2.

### Step 2 — Copy & rename

Naming rules (look at `epub/` for examples):
- Chinese-origin books: **Title-Case-With-Hyphens** → `The-Lost-Tomb.epub`, `The-Three-Body-Problem.epub`
- English-origin books: **lowercase-with-hyphens** → `pride-and-prejudice.epub`, `the-catcher-in-the-rye.epub`

```bash
cp /path/to/source.epub epub/<Name>.epub
```

### Step 3 — Inspect

```bash
uv run src/epub_check.py epub/<Name>.epub
```

Check output for:
- Language mismatch (e.g. `en` instead of `zh-CN`) → needs cleanup
- Ad content (search for keywords like 笔趣阁, sobqg in TOC/chapter previews) → needs cleanup
- Missing author, no documents → needs deeper inspection
- Content shows images/fonts → still needs slimming

### Step 4 — Cleanup

Only if inspect step found issues. At minimum, always fix language for Chinese books:

```bash
uv run src/epub_cleanup.py -i epub/<Name>.epub -o epub/<Name>.epub --lang zh-CN
```

If `epub_check` showed ad keywords in content, add `--extra-keywords`:
```bash
uv run src/epub_cleanup.py -i epub/<Name>.epub -o epub/<Name>.epub --lang zh-CN \
    --extra-keywords "额外广告词1,额外广告词2"
```

If the book is from a clean source, run with `--no-ad-removal --lang zh-CN`.

### Step 5 — Slim

Strip images/fonts/media. Slim to temp then copy back (slimmer doesn't overwrite in-place):

```bash
uv run src/epub_slimmer.py -i epub/<Name>.epub -o /tmp/slimmed.epub
cp /tmp/slimmed.epub epub/<Name>.epub
```

### Step 6 — Verify

```bash
uv run src/epub_check.py epub/<Name>.epub
```

Expected: **Clean.** (0 issues), 0 images, 0 fonts.

### Step 7 — Build & push

```bash
uv run src/epub2html.py -i ./epub -o ./public
git add epub/<Name>.epub && git commit -m "update" && git push
```

## CI/CD (`.github/workflows/deploy.yml`)

On push to `main` (trigger: `epub/**`, `src/**`, `templates/**`, workflow itself):
- Checkout with LFS, install Python 3.11 + deps
- `epub2html.py -i ./epub -o ./public`
- Deploy `public/` to GitHub Pages via `peaceiris/actions-gh-pages`

## Git LFS

All `*.epub` files are Git LFS-tracked (`.gitattributes`). `git lfs pull` after clone.

## Notes

- `public/` is gitignored (generated output)
- `index.html` at repo root is legacy, not part of the pipeline
- `.venv/` is gitignored
- EPUB naming convention: Chinese-origin books use Title-Case-With-Hyphens (`The-Lost-Tomb.epub`), English-origin books use lowercase-with-hyphens (`pride-and-prejudice.epub`). The filename stem becomes the output directory name, so get it right before committing.
