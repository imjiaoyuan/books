My Bookshelf

Convert EPUB files to a static HTML bookshelf with inter-chapter navigation, deployed to GitHub Pages.

## Tools

- **epub2html.py** — Convert EPUB files to HTML bookshelf with navigation
- **epub_slimmer.py** — Strip images, fonts, and media from EPUBs
- **epub_cleanup.py** — Remove ads and fix metadata (for pirated EPUBs)
- **epub_check.py** — Scan EPUB structure, metadata, and content
- **edit_epub.py** — Interactive editor for EPUB title and chapter names

## Quick start

```bash
# Install dependencies
uv pip install -r requirements.txt

# Convert EPUBs to HTML
uv run src/epub2html.py -i ./epub -o ./public

# Check an EPUB
uv run src/epub_check.py epub/book.epub

# Slim an EPUB
uv run src/epub_slimmer.py -i epub/book.epub -o epub/book.epub

# Clean up ads + fix language
uv run src/epub_cleanup.py -i epub/book.epub -o epub/book.epub --lang zh-CN

# Edit title/chapter names interactively
uv run src/edit_epub.py -i epub/book.epub
```

See [CLAUDE.md](CLAUDE.md) for the full workflow when adding new books.
