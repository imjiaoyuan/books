import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub, ITEM_DOCUMENT, ITEM_IMAGE, ITEM_STYLE, ITEM_FONT

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

from utils import read_epub_safe, get_epub_title, setup_logger

logger = logging.getLogger(__name__)


def scan_headings(book: epub.EpubBook):
    h1, h2, h3 = [], [], []
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        try:
            soup = BeautifulSoup(item.get_content().decode('utf-8', 'ignore'), 'lxml')
            for tag in soup.find_all(['h1', 'h2', 'h3']):
                text = tag.get_text(strip=True)
                if not text:
                    continue
                if tag.name == 'h1':
                    h1.append(text)
                elif tag.name == 'h2':
                    h2.append(text)
                else:
                    h3.append(text)
        except Exception:
            pass
    return h1, h2, h3


def scan_epub(epub_path: Path):
    book = read_epub_safe(epub_path)

    meta = {}
    for field in ('title', 'creator', 'language', 'date', 'publisher', 'identifier'):
        vals = book.get_metadata('DC', field)
        if vals:
            meta[field] = vals[0][0]

    toc = []
    def walk(items, depth=0):
        for item in items:
            if isinstance(item, tuple) and len(item) >= 1:
                link = item[0]
                if isinstance(link, epub.Link):
                    toc.append({'title': link.title, 'depth': depth})
                if len(item) > 1 and isinstance(item[1], list):
                    walk(item[1], depth + 1)
            elif isinstance(item, epub.Link):
                toc.append({'title': item.title, 'depth': depth})

    walk(book.toc)

    docs = imgs = styles = fonts = 0
    for item in book.get_items():
        t = item.get_type()
        if t == ITEM_DOCUMENT:
            docs += 1
        elif t == ITEM_IMAGE:
            imgs += 1
        elif t == ITEM_STYLE:
            styles += 1
        elif t == ITEM_FONT:
            fonts += 1

    h1, h2, h3 = scan_headings(book)
    spine_count = len(list(book.spine))

    issues = []
    if not meta.get('creator'):
        issues.append('missing author')
    if not meta.get('language'):
        issues.append('missing language')
    if docs == 0:
        issues.append('no document items')

    return {
        'file': epub_path.name,
        'size': epub_path.stat().st_size,
        'meta': meta,
        'toc': toc,
        'spine': spine_count,
        'docs': docs,
        'images': imgs,
        'styles': styles,
        'fonts': fonts,
        'h1': len(h1),
        'h2': len(h2),
        'h3': len(h3),
        'h1_samples': h1[:8],
        'issues': issues,
    }


def print_result(r):
    size_kb = r['size'] // 1024
    m = r['meta']
    print(f"\n{'─' * 60}")
    print(f"[{r['file']}]  {size_kb} KB")
    print(f"  Title:    {m.get('title', 'N/A')}")
    print(f"  Author:   {m.get('creator', 'N/A')}")
    print(f"  Language: {m.get('language', 'N/A')}")
    if m.get('date'):
        print(f"  Date:     {m['date']}")

    toc = r['toc']
    max_depth = max((e['depth'] for e in toc), default=0)
    print(f"  TOC:      {len(toc)} entries, max depth {max_depth}")
    if toc:
        print(f"  TOC preview:")
        for e in toc[:10]:
            indent = "  " * e['depth']
            print(f"    {indent}- {e['title'][:80]}")

    print(f"  Spine:    {r['spine']} items")
    print(f"  Content:  {r['docs']} docs | {r['images']} images | {r['styles']} styles | {r['fonts']} fonts")
    print(f"  Headings: H1={r['h1']}, H2={r['h2']}, H3={r['h3']}")
    if r['h1_samples']:
        print(f"  H1 samples:")
        for h in r['h1_samples']:
            print(f"    - {h[:100]}")

    if r['issues']:
        print(f"  Issues: {', '.join(r['issues'])}")
    else:
        print(f"  Clean.")


def main():
    parser = argparse.ArgumentParser(description='Scan EPUB files for structure and issues')
    parser.add_argument('path', nargs='+', help='EPUB file(s) or directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    args = parser.parse_args()

    setup_logger(__name__, logging.DEBUG if args.verbose else logging.WARNING)

    files: List[Path] = []
    for p in args.path:
        pp = Path(p).resolve()
        if pp.is_dir():
            files.extend(sorted(pp.glob('*.epub')))
        elif pp.suffix == '.epub':
            files.append(pp)

    if not files:
        print('No EPUB files found.')
        sys.exit(0)

    results = []
    issues_total = 0
    for fp in files:
        try:
            r = scan_epub(fp)
            results.append(r)
            issues_total += len(r['issues'])
            if args.json:
                print(json.dumps(r, ensure_ascii=False, default=str))
            else:
                print_result(r)
        except Exception as e:
            logger.error(f'{fp.name}: {e}')
            print(f'\nERROR [{fp.name}]: {e}')

    if not args.json:
        print(f"\n{'─' * 60}")
        print(f"Checked {len(files)} file(s), {issues_total} issue(s).")


if __name__ == '__main__':
    main()
