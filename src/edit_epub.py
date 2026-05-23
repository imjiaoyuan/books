import sys
import os
import tempfile
import argparse
import logging
from pathlib import Path
from typing import List
from ebooklib import epub

logger = logging.getLogger(__name__)


def collect_links(items: list, all_links: List[epub.Link]) -> None:
    for item in items:
        if isinstance(item, tuple):
            if len(item) > 0 and isinstance(item[0], epub.Link):
                all_links.append(item[0])
            if len(item) > 1:
                collect_links(item[1], all_links)
        elif isinstance(item, epub.Link):
            all_links.append(item)


def edit_title(book: epub.EpubBook) -> bool:
    titles = book.get_metadata('DC', 'title')
    current_title = titles[0][0] if titles else "Unknown"
    print(f"\n[Title Editing]\nCurrent title: {current_title}")
    new_title = input("Enter new title (Enter to skip): ").strip()

    if new_title:
        if 'http://purl.org/dc/elements/1.1/' in book.metadata:
            book.metadata['http://purl.org/dc/elements/1.1/']['title'] = []
        book.set_title(new_title)
        return True
    return False


def edit_chapters(all_links: List[epub.Link]) -> bool:
    modified = False
    while True:
        print("\n[Chapter Editing]")
        for i, link in enumerate(all_links):
            print(f"[{i}] {link.title}")

        cmd = input("\nEnter index to rename chapter, or 's' to save, 'q' to quit: ").strip().lower()

        if cmd == 'q':
            sys.exit(0)
        if cmd == 's':
            break

        try:
            idx = int(cmd)
            if 0 <= idx < len(all_links):
                old_name = all_links[idx].title
                new_name = input(f"New name for '{old_name}': ").strip()
                if new_name:
                    all_links[idx].title = new_name
                    modified = True
            else:
                print("Invalid index.")
        except ValueError:
            print("Invalid input.")

    return modified


def save_epub(book: epub.EpubBook, save_path: Path) -> None:
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.epub') as tmp_file:
        temp_path = Path(tmp_file.name)

    try:
        epub.write_epub(str(temp_path), book)
        if save_path.exists():
            save_path.unlink()
        temp_path.rename(save_path)
        print(f"Saved to: {save_path}")
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        logger.error(f"Failed to save EPUB: {e}")
        raise


def run_editor(epub_path: Path) -> None:
    if not epub_path.exists():
        logger.error(f"File not found: {epub_path}")
        sys.exit(1)

    if not epub_path.is_file():
        logger.error(f"Not a file: {epub_path}")
        sys.exit(1)

    try:
        book = epub.read_epub(str(epub_path))
    except Exception as e:
        logger.error(f"Failed to read EPUB: {e}")
        sys.exit(1)

    title_modified = edit_title(book)

    all_links: List[epub.Link] = []
    collect_links(book.toc, all_links)

    chapters_modified = edit_chapters(all_links)

    if title_modified or chapters_modified:
        book.toc = list(book.toc)
        save_path_str = input(f"\nSave as (default: {epub_path}): ").strip() or str(epub_path)
        save_path = Path(save_path_str).resolve()
        save_epub(book, save_path)
    else:
        print("No changes made.")


def main() -> None:
    parser = argparse.ArgumentParser(description='Edit EPUB metadata and chapter titles')
    parser.add_argument('-i', '--input', required=True, help='Input EPUB file path')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    epub_path = Path(args.input).resolve()
    run_editor(epub_path)


if __name__ == '__main__':
    main()