My Bookshelf

Convert from epub file using Python.

## Tools

This project contains three EPUB processing tools:

- **epub2html.py** - Convert EPUB files to HTML bookshelf with navigation
- **edit_epub.py** - Interactive editor for EPUB metadata and chapter titles
- **epub_slimmer.py** - Slim down EPUB files by removing media resources

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Convert EPUB to HTML
python src/epub2html.py -i <input_dir> -o <output_dir> [-j <jobs>]

# Edit EPUB metadata
python src/edit_epub.py -i <epub_file>

# Slim EPUB files
python src/epub_slimmer.py -i <input_path> -o <output_path> [-j <jobs>]
```
