import os
import sys
import argparse
import logging
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urldefrag
from concurrent.futures import ProcessPoolExecutor, as_completed
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from utils import natural_sort_key, read_epub_safe, get_epub_title

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

logger = logging.getLogger(__name__)
BASE_TPL_DIR = Path(__file__).parent.parent / 'templates'


def load_tpl(name: str) -> str:
    with open(BASE_TPL_DIR / name, 'r', encoding='utf-8') as f:
        return f.read()


def create_master_index(output_dir: Path, books: List[Dict[str, str]]) -> None:
    books.sort(key=lambda x: x['title'])
    items = "".join([f'<li><a href="{b["path"]}">{b["title"]}</a></li>' for b in books])
    out_file = output_dir / 'index.html'
    html = load_tpl('layout_shelf.html').replace('{title}', 'My Bookshelf').replace('{content}', items)
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)


def convert_ebook(epub_path: Path, book_root: Path) -> str:
    book = read_epub_safe(epub_path)
    title = get_epub_title(book, fallback=epub_path.stem)

    chapters_dir = book_root / 'chapters'
    chapters_dir.mkdir(parents=True, exist_ok=True)

    items = [i for i in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
    sorted_items = sorted(items, key=lambda x: natural_sort_key(os.path.basename(x.get_name())))

    filenames_map = {os.path.basename(item.get_name()): f"{i+1}.html" for i, item in enumerate(sorted_items)}
    sorted_orig_names = [os.path.basename(item.get_name()) for item in sorted_items]

    tpl_chapter = load_tpl('layout_chapter.html')
    for item in sorted_items:
        orig_fname = os.path.basename(item.get_name())
        out_fname = filenames_map[orig_fname]
        out_chap_path = chapters_dir / out_fname

        soup = BeautifulSoup(item.get_content().decode('utf-8', 'ignore'), 'lxml')

        for tag in soup.find_all(['img', 'image', 'svg', 'style', 'link', 'script']):
            tag.decompose()

        for tag in soup.find_all():
            tag.attrs = {key: val for key, val in tag.attrs.items() if key in ['href', 'id']}

        body_content = soup.body.decode_contents() if soup.body else str(soup)

        idx = sorted_orig_names.index(orig_fname)
        p_html = filenames_map[sorted_orig_names[idx-1]] if idx > 0 else None
        n_html = filenames_map[sorted_orig_names[idx+1]] if idx < len(sorted_orig_names)-1 else None

        btn = lambda lbl, tgt: f'<div><a href="{tgt}">{lbl}</a></div>' if tgt else f'<div>{lbl}</div>'
        nav_html = f'{btn("Prev", p_html)}{btn("Contents", "../index.html")}{btn("Bookshelf", "../../../index.html")}{btn("Next", n_html)}'

        final = tpl_chapter.replace('{title}', title).replace('{content}', body_content).replace('{nav}', nav_html)
        with open(out_chap_path, 'w', encoding='utf-8') as f:
            f.write(final)

    toc_list = []
    def walk_toc(it):
        toc_list.append('<ul>')
        for i in it:
            link, child = (i, []) if isinstance(i, epub.Link) else i
            try:
                target = book.get_item_with_href(urldefrag(link.href).url)
                if target and target.get_type() == ebooklib.ITEM_DOCUMENT:
                    t_orig = os.path.basename(target.get_name())
                    if t_orig in filenames_map:
                        toc_list.append(f'<li><a href="chapters/{filenames_map[t_orig]}">{link.title}</a>')
                        if child: walk_toc(child)
                        toc_list.append('</li>')
            except Exception as e:
                logger.warning(f"Failed to process TOC link {link.href}: {e}")
        toc_list.append('</ul>')

    walk_toc(book.toc)
    out_toc = book_root / 'index.html'
    final_toc = load_tpl('layout_toc.html').replace('{title}', title).replace('{toc_content}', "".join(toc_list)).replace('../index.html', '../../index.html')
    with open(out_toc, 'w', encoding='utf-8') as f:
        f.write(final_toc)
    return title

def process_epub_file(args: Tuple[Path, Path]) -> Optional[Dict[str, str]]:
    epub_path, books_dir = args
    folder = epub_path.stem
    try:
        title = convert_ebook(epub_path, books_dir / folder)
        return {'title': title, 'path': f"books/{folder}/index.html"}
    except Exception as e:
        logger.error(f"Failed to convert {epub_path.name}: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description='Convert EPUB files to HTML bookshelf')
    parser.add_argument('-i', '--input', required=True, help='Input directory containing EPUB files')
    parser.add_argument('-o', '--output', required=True, help='Output directory for HTML files')
    parser.add_argument('-j', '--jobs', type=int, default=1, help='Number of parallel jobs (default: 1)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    in_dir = Path(args.input).resolve()
    out_dir = Path(args.output).resolve()

    if not in_dir.exists() or not in_dir.is_dir():
        logger.error(f"Input directory does not exist: {in_dir}")
        sys.exit(1)

    books_dir = out_dir / 'books'
    books_dir.mkdir(parents=True, exist_ok=True)

    epub_files = sorted(in_dir.glob('*.epub'))
    if not epub_files:
        logger.warning(f"No EPUB files found in {in_dir}")
        return

    logger.info(f"Processing {len(epub_files)} EPUB file(s)...")

    data: List[Dict[str, str]] = []
    tasks = [(p, books_dir) for p in epub_files]

    if len(tasks) == 1 or args.jobs == 1:
        for task in tasks:
            result = process_epub_file(task)
            if result:
                data.append(result)
                logger.info(f"Converted: {result['title']}")
    else:
        max_workers = min(args.jobs, len(tasks))
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_epub_file, task): task for task in tasks}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    data.append(result)
                    logger.info(f"Converted: {result['title']}")

    create_master_index(out_dir, data)
    logger.info(f"Done! Created bookshelf at {out_dir / 'index.html'}")


if __name__ == '__main__':
    main()