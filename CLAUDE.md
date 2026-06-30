# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A personal EPUB-to-HTML bookshelf converter. It takes EPUB files (stored via Git LFS in `epub/`), converts them to static HTML with inter-chapter navigation, and deploys the result to GitHub Pages.

## Commands

```bash
# Install dependencies (Python 3.11+)
pip install -r requirements.txt

# Convert all EPUBs in epub/ to HTML in public/
python src/epub2html.py -i ./epub -o ./public

# Parallel conversion (e.g., 4 workers)
python src/epub2html.py -i ./epub -o ./public -j 4

# Slim EPUBs (strip images, fonts, media)
python src/epub_slimmer.py -i ./epub -o ./slimmed_epub -j 4

# Edit EPUB metadata/chapter titles interactively
python src/edit_epub.py -i epub/some-book.epub

# Scan EPUB structure (headings, TOC depth, metadata, issues)
python src/epub_check.py epub/some-book.epub         # human-readable
python src/epub_check.py epub/ --json                 # JSON, whole directory
```

There are no tests in this project. The scripts are verified by running them directly.

## Architecture

### Shared foundation (`src/utils.py`)

All scripts depend on `utils.py` for:
- `read_epub_safe(path)` — validates and opens an EPUB file via `ebooklib`, raising descriptive errors
- `get_epub_title(book, fallback)` — extracts the DC title metadata
- `natural_sort_key(s)` — sorts chapter filenames containing numbers naturally (e.g., "ch2" before "ch10")
- `setup_logger(name, level)` — creates a logger with stream handler

### Core conversion pipeline (`src/epub2html.py` → `templates/`)

The main tool. Uses `ProcessPoolExecutor` for parallelism (serial path when `-j 1` or a single file).

1. Reads all `.epub` files from the input directory
2. For each EPUB: extracts document items, sorts by natural key, maps old→new filenames
3. Strips `<img>`, `<image>`, `<svg>`, `<style>`, `<link>`, `<script>` tags and all non-href/non-id attributes from chapter HTML
4. Injects prev/next/contents/bookshelf navigation into each chapter page using simple `{placeholder}` string replacement (not Jinja2)
5. Builds a TOC page by walking `book.toc` (recursive `Link`/tuple structure) and resolving hrefs to the renamed chapter files
6. Generates `create_master_index()` — a top-level bookshelf page listing all converted books

**Template system**: Three HTML templates in `templates/` using `{title}`, `{content}`, `{nav}`, `{toc_content}` placeholders substituted via `str.replace()`. The output is a three-level hierarchy:
```
public/
├── index.html              (bookshelf — lists all books)
└── books/
    └── <BookTitle>/
        ├── index.html       (book TOC)
        └── chapters/
            ├── 1.html
            ├── 2.html
            └── ...
```

### EPUB slimdown (`src/epub_slimmer.py`)

Removes media items (images, fonts, audio, video) from EPUB files, strips `<img>`, `<image>`, `<svg>`, `<video>`, `<audio>`, `<iframe>` tags from documents, and removes `@font-face` blocks from CSS.

### Interactive editor (`src/edit_epub.py`)

Interactive CLI for editing EPUB metadata (title) and TOC chapter titles. Saves atomically via a temp-file-then-rename pattern.

### Diagnostics (`src/epub_check.py`)

Read-only scanner. Reports per-EPUB: file size, metadata completeness, TOC depth/preview, spine count, content-type breakdown (docs/images/styles/fonts), heading distribution (H1/H2/H3 counts and samples), and flags issues (missing author, missing language, no documents).

### CI/CD (`.github/workflows/deploy.yml`)

On push to `main` when `epub/**`, `src/**`, `templates/**`, or the workflow itself changes:
- Checks out with LFS, installs Python 3.11 + deps
- Runs `epub2html.py -i ./epub -o ./public`
- Deploys `public/` to GitHub Pages via `peaceiris/actions-gh-pages`

### Git LFS

All `*.epub` files are tracked via Git LFS (`.gitattributes`). After cloning, run `git lfs pull` to fetch actual file contents.

### Key dependencies

- `ebooklib` — EPUB read/write operations
- `beautifulsoup4` + `lxml` — HTML parsing and manipulation
- No web framework, no database, no asset pipeline — pure static site generation
