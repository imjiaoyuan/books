import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from ebooklib import epub, ITEM_DOCUMENT

from utils import read_epub_safe, get_epub_title

logger = logging.getLogger(__name__)

SPLIT_CONFIG = {
    'Selected-Works-of-Liang-Xiaosheng.epub': {
        'mode': 'structured',
        'output_dir': 'Liang-Xiaosheng',
    },
    'Three-Novels-of-Liu-Cixin.epub': {
        'mode': 'markers',
        'markers': ['球状闪电', '三体全集', '超新星纪元'],
        'output_dir': 'Liu-Cixin-Novels',
    },
    'Liu-Cixin-Short-Stories-28.epub': {
        'mode': 'flat',
        'output_dir': 'Liu-Cixin-Short-Stories',
    },
}


def _collect_toc_hrefs(toc_item) -> set:
    hrefs = set()
    if isinstance(toc_item, tuple):
        link = toc_item[0]
        if isinstance(link, epub.Link) and link.href:
            hrefs.add(link.href.split('#')[0])
        if len(toc_item) > 1 and isinstance(toc_item[1], list):
            for child in toc_item[1]:
                hrefs |= _collect_toc_hrefs(child)
    elif isinstance(toc_item, epub.Link):
        if toc_item.href:
            hrefs.add(toc_item.href.split('#')[0])
    return hrefs


def _collect_toc_entries(toc_item) -> List:
    entries = []
    if isinstance(toc_item, tuple):
        entries.append(toc_item[0])
        if len(toc_item) > 1 and isinstance(toc_item[1], list):
            for child in toc_item[1]:
                entries.extend(_collect_toc_entries(child))
    elif isinstance(toc_item, epub.Link):
        entries.append(toc_item)
    return entries


def _spine_items_in_range(book, start: int, end: int) -> List:
    items = []
    seen = set()
    spine = list(book.spine)
    for i in range(start, end + 1):
        if i >= len(spine):
            break
        item_id, _ = spine[i]
        if item_id not in seen:
            item = book.get_item_with_id(item_id)
            if item is not None:
                items.append(item)
                seen.add(item_id)
    return items


def _hrefs_to_items(book, hrefs: set, spine_order: bool = True) -> List:
    items = []
    seen = set()
    if spine_order:
        for item_id, _ in book.spine:
            if item_id in seen:
                continue
            item = book.get_item_with_id(item_id)
            if item and item.file_name in hrefs and item.get_type() == ITEM_DOCUMENT:
                items.append(item)
                seen.add(item_id)
    else:
        for item_id, _ in book.spine:
            if item_id in seen:
                continue
            item = book.get_item_with_id(item_id)
            if item and item.file_name in hrefs:
                items.append(item)
                seen.add(item_id)
    return items


def _make_epub(book, spine_items: List, title: str, author: str, lang: str,
               toc_titles: List[str] = None):
    new_book = epub.EpubBook()
    new_book.set_title(title)
    new_book.add_author(author)
    new_book.set_language(lang)

    spine_items = [item for item in spine_items if item is not None]
    new_book.items = list(spine_items)

    ncx_item = epub.EpubNcx()
    new_book.add_item(ncx_item)
    new_book.spine = [(item.id, 'yes') for item in spine_items]

    new_book.toc = []
    if toc_titles and len(toc_titles) == len(spine_items):
        for item, t in zip(spine_items, toc_titles):
            if item.get_type() == ITEM_DOCUMENT:
                new_book.toc.append(epub.Link(item.file_name, t, item.id))
    else:
        for item in spine_items:
            if item.get_type() == ITEM_DOCUMENT:
                new_book.toc.append(epub.Link(item.file_name, title, item.id))

    return new_book


def split_structured(book, epub_path: Path, output_base: Path) -> List[Path]:
    author = book.get_metadata('DC', 'creator')
    author = author[0][0] if author else 'Unknown'
    lang = book.get_metadata('DC', 'language')
    lang = lang[0][0] if lang else 'zh-CN'

    results = []
    for item in book.toc:
        if not isinstance(item, tuple):
            continue
        link = item[0]
        children = item[1] if len(item) > 1 else []
        if not isinstance(children, list) or len(children) == 0:
            continue

        title = link.title
        hrefs = _collect_toc_hrefs(item)
        spine_items = _hrefs_to_items(book, hrefs)

        entries = _collect_toc_entries(item)
        toc_titles = [e.title for e in entries if isinstance(e, epub.Link)]

        if not spine_items:
            logger.warning(f'No items for: {title}')
            continue

        safe_name = title.replace('/', '-').replace('：', '-').replace(':', '-').strip()
        out_path = output_base / f'{safe_name}.epub'

        new_book = _make_epub(book, spine_items, title, author, lang, toc_titles)
        epub.write_epub(str(out_path), new_book)
        results.append(out_path)
        print(f'  {title} ({len(spine_items)} items) -> {out_path.name}')

    return results


def split_flat(book, epub_path: Path, output_base: Path) -> List[Path]:
    author = book.get_metadata('DC', 'creator')
    author = author[0][0] if author else 'Unknown'
    lang = book.get_metadata('DC', 'language')
    lang = lang[0][0] if lang else 'zh-CN'

    results = []
    for item in book.toc:
        if isinstance(item, tuple):
            link = item[0]
        elif isinstance(item, epub.Link):
            link = item
        else:
            continue

        title = link.title
        if not title or title in ('书名页', '版权页', '目录', '封面'):
            continue

        hrefs = _collect_toc_hrefs(item)
        spine_items = _hrefs_to_items(book, hrefs)

        if not spine_items:
            continue

        safe_name = title.replace('/', '-').replace('：', '-').replace(':', '-').strip()
        out_path = output_base / f'{safe_name}.epub'

        toc_titles = [e.title for e in _collect_toc_entries(item) if isinstance(e, epub.Link)]
        new_book = _make_epub(book, spine_items, title, author, lang, toc_titles)
        epub.write_epub(str(out_path), new_book)
        results.append(out_path)
        print(f'  {title} ({len(spine_items)} items) -> {out_path.name}')

    return results


def split_by_markers(book, epub_path: Path, output_base: Path, markers: List[str]) -> List[Path]:
    author = book.get_metadata('DC', 'creator')
    author = author[0][0] if author else 'Unknown'
    lang = book.get_metadata('DC', 'language')
    lang = lang[0][0] if lang else 'zh-CN'

    toc_entries = []
    for item in book.toc:
        if isinstance(item, tuple):
            toc_entries.append(item[0])
        elif isinstance(item, epub.Link):
            toc_entries.append(item)

    marker_spine_pos = {}
    spine_list = list(book.spine)
    for i, entry in enumerate(toc_entries):
        if entry.title in markers and entry.href:
            href = entry.href.split('#')[0]
            for j, (item_id, _) in enumerate(spine_list):
                item = book.get_item_with_id(item_id)
                if item and item.file_name == href:
                    marker_spine_pos[entry.title] = j
                    break

    sorted_markers = sorted(marker_spine_pos.items(), key=lambda x: x[1])

    results = []
    for mi, (title, start_pos) in enumerate(sorted_markers):
        end_pos = sorted_markers[mi + 1][1] - 1 if mi + 1 < len(sorted_markers) else len(spine_list) - 1

        items_in_range = _spine_items_in_range(book, start_pos, end_pos)

        if not items_in_range:
            continue

        safe_name = title.replace('/', '-').replace('：', '-').replace(':', '-').strip()
        out_path = output_base / f'{safe_name}.epub'

        new_book = _make_epub(book, items_in_range, title, author, lang)
        epub.write_epub(str(out_path), new_book)
        results.append(out_path)
        print(f'  {title} ({len(items_in_range)} items, spine {start_pos}-{end_pos}) -> {out_path.name}')

    return results


def main():
    parser = argparse.ArgumentParser(description='Split collection EPUBs into individual books')
    parser.add_argument('epub', help='Path to collection EPUB')
    parser.add_argument('-o', '--output', default='/tmp/split-epubs',
                        help='Output directory (default: /tmp/split-epubs)')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stderr,
    )

    epub_path = Path(args.epub).resolve()
    if not epub_path.exists():
        print(f'File not found: {epub_path}')
        sys.exit(1)

    fname = epub_path.name
    config = SPLIT_CONFIG.get(fname)
    if not config:
        print(f'No split config for: {fname}')
        sys.exit(1)

    book = read_epub_safe(epub_path)
    output_base = Path(args.output).resolve() / config['output_dir']
    output_base.mkdir(parents=True, exist_ok=True)

    print(f'Splitting: {fname}')
    print(f'Output: {output_base}')

    mode = config['mode']
    if mode == 'structured':
        results = split_structured(book, epub_path, output_base)
    elif mode == 'flat':
        results = split_flat(book, epub_path, output_base)
    elif mode == 'markers':
        results = split_by_markers(book, epub_path, output_base, config['markers'])

    print(f'\nCreated {len(results)} EPUBs.')


if __name__ == '__main__':
    main()
