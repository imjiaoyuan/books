import sys
import re
import argparse
import logging
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import epub, ITEM_DOCUMENT

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

from utils import read_epub_safe

logger = logging.getLogger(__name__)

AD_KEYWORDS = [
    '笔趣阁', 'sobqg', 'txtsk', 'bxwx', 'zww', 'uuks',
    'biquge', '69shu', '电子书免费阅读', '最新精品',
]

AD_DOMAINS = re.compile(
    r'https?://(www\.)?(sobqg|txtsk|bxwx|zww|uuks|biquge|69shu)\.',
    re.IGNORECASE,
)


def remove_ads(book: epub.EpubBook, extra_keywords: list[str] | None = None) -> int:
    keywords = AD_KEYWORDS + (extra_keywords or [])
    cleaned = 0

    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue

        soup = BeautifulSoup(item.get_content(), 'lxml')
        removed = False

        for tag in soup.find_all(['div', 'p', 'span', 'a']):
            text = tag.get_text()
            if any(kw in text for kw in keywords):
                tag.decompose()
                removed = True

        if removed:
            cleaned += 1
            item.set_content(str(soup).encode('utf-8'))

    return cleaned


def remove_stray_links(book: epub.EpubBook) -> int:
    removed = 0

    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue

        soup = BeautifulSoup(item.get_content(), 'lxml')
        changed = False
        for a_tag in soup.find_all('a'):
            if AD_DOMAINS.search(a_tag.get('href', '')):
                a_tag.decompose()
                changed = True

        if changed:
            removed += 1
            item.set_content(str(soup).encode('utf-8'))

    return removed


def fix_language(book: epub.EpubBook, lang: str) -> int:
    changed = 0

    dc_key = 'http://purl.org/dc/elements/1.1/'
    old = book.get_metadata('DC', 'language')
    if not old or old[0][0] != lang:
        if dc_key in book.metadata and 'language' in book.metadata[dc_key]:
            book.metadata[dc_key]['language'] = [(lang, {})]
        else:
            book.add_metadata('DC', 'language', lang)
        changed += 1
        logger.info(f"Language → {lang}")

    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), 'lxml')
        html_tag = soup.find('html')
        if html_tag:
            fixed = False
            if html_tag.get('lang') and html_tag['lang'] != lang:
                html_tag['lang'] = lang
                fixed = True
            if html_tag.get('xml:lang') and html_tag['xml:lang'] != lang:
                html_tag['xml:lang'] = lang
                fixed = True
            if fixed:
                changed += 1
                item.set_content(str(soup).encode('utf-8'))

    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description='Clean up EPUB files')
    parser.add_argument('-i', '--input', required=True, help='Input EPUB file')
    parser.add_argument('-o', '--output', required=True, help='Output EPUB file')
    parser.add_argument('--extra-keywords', help='Comma-separated extra ad keywords')
    parser.add_argument('--lang', help='Fix language (e.g. zh-CN)')
    parser.add_argument('--no-ad-removal', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    fin = Path(args.input).resolve()
    fout = Path(args.output).resolve()

    if not fin.exists():
        logger.error(f"Not found: {fin}")
        sys.exit(1)

    book = read_epub_safe(fin)

    extra = None
    if args.extra_keywords:
        extra = [k.strip() for k in args.extra_keywords.split(',') if k.strip()]

    ad_cleaned = 0
    link_cleaned = 0
    if not args.no_ad_removal:
        ad_cleaned = remove_ads(book, extra)
        link_cleaned = remove_stray_links(book)

    lang_fixes = 0
    if args.lang:
        lang_fixes = fix_language(book, args.lang)

    fout.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(fout), book)

    old_kb = fin.stat().st_size // 1024
    new_kb = fout.stat().st_size // 1024
    print(f"Ad chapters: {ad_cleaned}  |  Links: {link_cleaned}  |  Lang fixes: {lang_fixes}")
    print(f"Size: {old_kb}KB → {new_kb}KB")
    logger.info("Done!")


if __name__ == '__main__':
    main()
