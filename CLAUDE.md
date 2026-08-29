# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A personal EPUB-to-HTML bookshelf converter. Takes EPUB files from `epub/`, converts them to static HTML with inter-chapter navigation and offline reading (service worker), and deploys to GitHub Pages.

## Environment

Python venv at `.venv/` (system python3). `uv` is no longer installed, so run scripts with `.venv/bin/python` directly.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Commands

All scripts run with `.venv/bin/python`:

```bash
# Convert all EPUBs to HTML (emits public/index.html, books/, sw.js, book.js)
.venv/bin/python src/epub2html.py -i ./epub -o ./public [-j N]

# Slim EPUBs (strip images/fonts/media + cover pages)
.venv/bin/python src/epub_slimmer.py -i epub/book.epub -o epub/book.epub

# Check EPUB structure/metadata
.venv/bin/python src/epub_check.py epub/book.epub [--json]

# Content-quality scan (ads, garbled text, short chapters)
.venv/bin/python src/epub_content_check.py epub/book.epub [--extra-keywords "词1,词2"]

# Clean up ads + fix metadata (pirated EPUBs)
.venv/bin/python src/epub_cleanup.py -i epub/book.epub -o epub/book.epub --lang zh-CN

# Edit title/chapter names interactively
.venv/bin/python src/edit_epub.py -i epub/book.epub

# Split a collection EPUB into individual books (config-driven; see below)
.venv/bin/python src/epub_splitter.py epub/Collection.epub -o /tmp/split-epubs
```

There are no tests — scripts are verified by running them directly.

## Architecture

### Shared foundation (`src/utils.py`)

- `read_epub_safe(path)` — validates and opens an EPUB via `ebooklib`
- `get_epub_title(book, fallback)` — extracts the DC title metadata
- `natural_sort_key(s)` — natural sort for chapter filenames ("ch2" < "ch10")
- `setup_logger(name, level)` — stream-handler logger factory (only used by `epub_check.py`; other scripts use `logging.basicConfig` directly)

Scripts import siblings flat (`from utils import ...`), not `from src.utils` — this works because `.venv/bin/python src/foo.py` puts `src/` itself on `sys.path`. There is no package structure; don't introduce one.

### Core pipeline (`src/epub2html.py` → `templates/`)

Serial for 1 EPUB, `ProcessPoolExecutor` otherwise (capped at `min(jobs, len(tasks))`).

1. Stamps `__CACHE_VERSION__` (git short SHA, or `dev`) into `sw.js`/`book.js` and writes them to the site root.
2. Reads `.epub` files from the input dir.
3. Extracts document items, sorts by natural key, remaps filenames → `1.html`, `2.html`...
4. Strips `<img>`, `<image>`, `<svg>`, `<style>`, `<link>`, `<script>` and all non-href/non-id attributes, then remaps internal `<a href>`s to the renamed chapter files (books with an in-content TOC link across chapters by original filename, e.g. the-qin-empire).
5. Injects prev/next/contents/bookshelf nav via `{placeholder}` string replacement (no Jinja2).
6. Builds TOC by walking `book.toc` (recursive `Link`/tuple), resolving hrefs to renamed files.
7. Generates bookshelf at `public/index.html` listing all books sorted by title.

**Output structure**:
```
public/
├── index.html                  (bookshelf — all books)
├── sw.js, book.js              (offline-caching assets, version-stamped)
└── books/
    └── <BookTitle>/
        ├── index.html          (book TOC + "Save Offline" button)
        └── chapters/
            ├── 1.html
            └── ...
```

Both `epub2html.py` and `epub_slimmer.py` share the same concurrency pattern: serial when `len(tasks) == 1`, otherwise `ProcessPoolExecutor` capped at `min(jobs, len(tasks))`.

### Offline reading (`templates/sw.js` + `templates/book.js`)

- `book.js` registers `sw.js` (resolving the site root from its own script URL, so it works under any subpath) and wires the `#dl-offline` button on each book's TOC page to pre-cache all chapters for that book. The button lives in `layout_toc.html` and carries `data-folder`/`data-total` attributes that `book.js` reads.
- `sw.js` serves same-origin GETs stale-while-revalidate, and runs a sliding-window prefetch: opening chapter N caches N+1..N+20 (stops at first 404 = end of book; skips on metered/save-data connections). On cache miss while offline, returns a `503` fallback page.

These pieces share a load-bearing invariant: chapters are sequential `1.html..N.html` files under `books/<Folder>/chapters/`. `epub2html.py`'s renaming, `sw.js`'s URL regex, and `book.js`'s download loop all assume it — preserve the numbering scheme when changing any of them.
- `__CACHE_VERSION__` is the cache-busting key. It's substituted by `epub2html.py`'s `write_static_assets()`/`get_cache_version()`, so editing these files requires no manual version bump.

### EPUB slimdown (`src/epub_slimmer.py`)

Removes image/font/audio/video items, cover pages (detected by OPF `cover` meta, filename, or `<title>封面</title>`), `<img>`/`<image>`/`<svg>`/`<video>`/`<audio>`/`<iframe>` tags, `@font-face` CSS blocks, and clears the OPF `cover` metadata. Single-file or directory mode.

### Collection splitter (`src/epub_splitter.py`)

Splits a multi-book collection EPUB into individual EPUBs. **Config-driven, not general-purpose**: only files named in the `SPLIT_CONFIG` dict at the top of the script are processed. To split a new collection, add an entry there with a `mode`:

- `structured` — one output per top-level TOC group that has children
- `flat` — one output per top-level TOC entry (skips 书名页/版权页/目录/封面)
- `markers` — one output per spine range between the given `markers` TOC titles

Takes a single EPUB positional arg; `-o` defaults to `/tmp/split-epubs`.

### EPUB cleanup (`src/epub_cleanup.py`)

For pirated EPUBs: removes ad elements matching `AD_KEYWORDS` (笔趣阁, sobqg, txtsk, bxwx...) and strips `<a>` links to known piracy domains (`AD_DOMAINS`). Also fixes language metadata and `lang`/`xml:lang` attributes. Use `--extra-keywords` for source-specific ad text, `--no-ad-removal` to skip ad stripping, `--lang` to fix language.

### Diagnostics (`src/epub_check.py`)

Read-only scanner: file size, metadata completeness, TOC depth/preview, spine count, content-type breakdown (docs/images/styles/fonts), heading distribution (H1/H2/H3 counts/samples). Flags: missing author, missing language, no documents. Accepts paths or directory; `--json` for machine output.

### Content check (`src/epub_content_check.py`)

Scans chapter body text for ad keywords, garbled/encoding artifacts, and suspiciously short chapters. Use `--extra-keywords` for source-specific ad text. Run after `epub_check.py` to verify content quality before committing.

### Interactive editor (`src/edit_epub.py`)

Edit EPUB title and TOC chapter titles. Saves atomically (temp-file-then-rename). Only touches `book.toc` (nav links), not `book.spine` (reading order).

## Adding new books

### Step 1 — Extract (if source is .zip)

Many Chinese sites ship an epub inside a zip with GBK-encoded filenames, so `unzip -l` shows garbled text. Use Python to decode and extract:

```bash
.venv/bin/python -c "
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

If the source is already `.epub`, skip to step 2.

### Step 2 — Copy & rename

Naming rules (look at `epub/` for examples):
- Chinese-origin books: **Title-Case-With-Hyphens** → `The-Lost-Tomb.epub`, `The-Three-Body-Problem.epub`
- English-origin books: **lowercase-with-hyphens** → `pride-and-prejudice.epub`, `the-catcher-in-the-rye.epub`

```bash
cp /path/to/source.epub epub/<Name>.epub
```

### Step 3 — Inspect

```bash
.venv/bin/python src/epub_check.py epub/<Name>.epub
```

Check output for:
- Language mismatch (e.g. `en` instead of `zh-CN`) → needs cleanup
- Ad content (search for keywords like 笔趣阁, sobqg in TOC/chapter previews) → needs cleanup
- Missing author, no documents → needs deeper inspection
- Content shows images/fonts → still needs slimming

### Step 4 — Cleanup

Only if the inspect step found issues. At minimum, always fix language for Chinese books:

```bash
.venv/bin/python src/epub_cleanup.py -i epub/<Name>.epub -o epub/<Name>.epub --lang zh-CN
```

If `epub_check` showed ad keywords in content, add `--extra-keywords`:
```bash
.venv/bin/python src/epub_cleanup.py -i epub/<Name>.epub -o epub/<Name>.epub --lang zh-CN \
    --extra-keywords "额外广告词1,额外广告词2"
```

If the book is from a clean source, run with `--no-ad-removal --lang zh-CN`.

### Step 5 — Slim

Strip images/fonts/media. Slim to a temp path then copy back (the slimmer overwrites `-o`, but using a temp avoids losing the input if something fails):

```bash
.venv/bin/python src/epub_slimmer.py -i epub/<Name>.epub -o /tmp/slimmed.epub
cp /tmp/slimmed.epub epub/<Name>.epub
```

### Step 6 — Verify

```bash
.venv/bin/python src/epub_check.py epub/<Name>.epub
```

Expected: **Clean.** (0 issues), 0 images, 0 fonts.

### Step 7 — Build & push

```bash
.venv/bin/python src/epub2html.py -i ./epub -o ./public
git add epub/<Name>.epub && git commit -m "update" && git push
```

## CI/CD (`.github/workflows/deploy.yml`)

On push to `main` (trigger: `epub/**.epub`, `src/**`, `templates/**`, workflow itself):
- Checkout with LFS, install Python 3.11 + deps
- `python src/epub2html.py -i ./epub -o ./public`
- Deploy `public/` to GitHub Pages via `peaceiris/actions-gh-pages` (`force_orphan: true`)

## Git LFS

All `*.epub` files are Git LFS-tracked (`.gitattributes`). Run `git lfs pull` after clone.

## Notes

- `public/` is gitignored (generated output)
- `index.html` at repo root is legacy, not part of the pipeline
- `README.md` is a brief intro that defers to this file for the full workflow; its Tools section lists the `src/` scripts, so update it when adding a new one
- `.venv/` and `src/__pycache__/` are gitignored
- UI text in templates/JS is English; Chinese strings in `src/` (ad keywords, `封面`/`书名页` detection) are functional, not UI — don't translate them
- The filename stem of each EPUB becomes its output directory name, so get it right before committing
