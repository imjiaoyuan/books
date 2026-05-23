import logging
import re
from typing import Optional
from pathlib import Path
from ebooklib import epub
from bs4 import BeautifulSoup


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def natural_sort_key(s: str) -> list:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def read_epub_safe(path: Path) -> epub.EpubBook:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    if path.suffix.lower() != '.epub':
        raise ValueError(f"Not an EPUB file: {path}")
    return epub.read_epub(str(path))


def get_epub_title(book: epub.EpubBook, fallback: str = "Unknown") -> str:
    try:
        titles = book.get_metadata('DC', 'title')
        if titles and len(titles) > 0:
            return titles[0][0]
    except Exception:
        pass
    return fallback
