import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from ebooklib import ITEM_DOCUMENT

warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

from utils import read_epub_safe

logger = logging.getLogger(__name__)

AD_KEYWORDS = [
    '笔趣阁', 'sobqg', 'txtsk', 'bxwx', 'soduso', 'biquge',
    '梦想文学', '最快更新', '请记住本站', '求书网', '全本小说网',
    '69书吧', '八一中文网', '顶点小说', '书包网', '笔下文学',
    '书荒部落', 'noveless',
]

GARBLED_CHARS = {'�', '\x00'}


def _is_suspect_char(ch: str) -> bool:
    cp = ord(ch)
    if 0xE000 <= cp <= 0xF8FF:
        return True
    if 0xD800 <= cp <= 0xDFFF:
        return True
    return False


def _find_ads(text: str, extra_keywords: List[str]) -> List[str]:
    keywords = list(AD_KEYWORDS) + list(extra_keywords)
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _find_garbled(text: str, sample_size: int = 5000) -> List[str]:
    issues = []
    sample = text[:sample_size]
    for ch in GARBLED_CHARS:
        if ch in sample:
            issues.append('replacement-char U+{:04X}'.format(ord(ch)))
    for i, ch in enumerate(sample):
        if _is_suspect_char(ch):
            issues.append('suspect-char U+{:04X} at {}'.format(ord(ch), i))
    latin1_count = sum(1 for ch in sample if 0x0080 <= ord(ch) <= 0x00FF)
    if latin1_count > len(sample) * 0.3:
        issues.append('high-latin1-ratio ({}/{})'.format(latin1_count, len(sample)))
    return issues


def scan_content(epub_path: Path, extra_keywords: List[str] = None) -> Dict:
    if extra_keywords is None:
        extra_keywords = []

    book = read_epub_safe(epub_path)

    doc_items = [item for item in book.get_items()
                 if item.get_type() == ITEM_DOCUMENT]

    ad_hits: Dict[str, List[str]] = {}
    garbled_hits: Dict[str, List[str]] = {}
    short_chapters: Dict[str, int] = {}

    for item in doc_items:
        try:
            soup = BeautifulSoup(item.get_body_content(), 'html.parser')
            text = soup.get_text()
        except Exception:
            soup = BeautifulSoup(item.get_content().decode('utf-8', 'ignore'), 'lxml')
            text = soup.get_text()

        name = item.get_name()

        ads = _find_ads(text, extra_keywords)
        if ads:
            ad_hits[name] = ads

        garbled = _find_garbled(text)
        if garbled:
            garbled_hits[name] = garbled

        char_count = len(text.strip())
        if char_count > 0 and char_count < 50:
            short_chapters[name] = char_count

    return {
        'file': epub_path.name,
        'size_kb': epub_path.stat().st_size // 1024,
        'total_docs': len(doc_items),
        'ad_hits': ad_hits,
        'garbled_hits': garbled_hits,
        'short_chapters': short_chapters,
    }


def print_result(r: Dict):
    print("\n" + "─" * 60)
    print("[{}]  {} KB  |  {} chapters".format(r['file'], r['size_kb'], r['total_docs']))

    if r['ad_hits']:
        print("\n  AD: {} chapter(s)".format(len(r['ad_hits'])))
        for name, keywords in sorted(r['ad_hits'].items()):
            print("    - {}: {}".format(name, ', '.join(keywords)))
    else:
        print("\n  AD: none")

    if r['garbled_hits']:
        print("\n  GARBLED: {} chapter(s)".format(len(r['garbled_hits'])))
        for name, issues in sorted(r['garbled_hits'].items()):
            print("    - {}: {}".format(name, ', '.join(issues)))
    else:
        print("  GARBLED: none")

    if r['short_chapters']:
        print("\n  SHORT: {} chapter(s) (< 50 chars)".format(len(r['short_chapters'])))
        for name, count in sorted(r['short_chapters'].items()):
            print("    - {}: {} chars".format(name, count))
    else:
        print("  SHORT: none")


def main():
    parser = argparse.ArgumentParser(
        description='Scan EPUB chapter content for ads, garbled text, and blank chapters'
    )
    parser.add_argument('path', nargs='+', help='EPUB file(s) or directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--extra-keywords', default='',
                        help='Comma-separated extra ad keywords to search for')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
        stream=sys.stderr,
    )

    extra_keywords = [k.strip() for k in args.extra_keywords.split(',') if k.strip()]

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

    has_issues = False
    for fp in files:
        try:
            r = scan_content(fp, extra_keywords)
            if args.json:
                print(json.dumps(r, ensure_ascii=False, default=str))
            else:
                print_result(r)
            if r['ad_hits'] or r['garbled_hits'] or r['short_chapters']:
                has_issues = True
        except Exception as e:
            logger.error('{}: {}'.format(fp.name, e))
            print('\nERROR [{}]: {}'.format(fp.name, e))
            has_issues = True

    if not args.json:
        print("\n" + "─" * 60)
        if has_issues:
            print("Issues found.")
        else:
            print("All clear.")


if __name__ == '__main__':
    main()
