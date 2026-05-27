import sys
import re
import argparse
import logging
from pathlib import Path
from typing import Tuple, List, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup

from utils import read_epub_safe

logger = logging.getLogger(__name__)


def clean_file(file_path: Path, output_path: Path) -> Tuple[int, int]:
    book = read_epub_safe(file_path)
    new_items = []

    for item in book.get_items():
        if item.get_type() in [ebooklib.ITEM_IMAGE, ebooklib.ITEM_FONT, ebooklib.ITEM_VIDEO, ebooklib.ITEM_AUDIO]:
            continue

        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            try:
                soup = BeautifulSoup(item.get_content().decode('utf-8', 'ignore'), 'lxml')
                for tag in soup.find_all(['img', 'image', 'svg', 'video', 'audio', 'iframe']):
                    tag.decompose()
                item.set_content(str(soup).encode('utf-8'))
            except Exception as e:
                logger.warning(f"Failed to clean document content: {e}")

        elif item.get_type() == ebooklib.ITEM_STYLE:
            try:
                css = item.get_content().decode('utf-8', 'ignore')
                css = re.sub(r'@font-face\s*{[^}]*}', '', css, flags=re.DOTALL)
                item.set_content(css.encode('utf-8'))
            except Exception as e:
                logger.warning(f"Failed to clean CSS content: {e}")

        new_items.append(item)

    book.items = new_items
    old_size = file_path.stat().st_size
    epub.write_epub(str(output_path), book)
    new_size = output_path.stat().st_size
    return old_size, new_size


def process_single_file(args: Tuple[Path, Path]) -> Optional[Tuple[str, int, int]]:
    f_in, f_out = args
    try:
        out_dir = f_out.parent
        if out_dir and not out_dir.exists():
            out_dir.mkdir(parents=True, exist_ok=True)

        old_size, new_size = clean_file(f_in, f_out)
        return (f_in.name, old_size, new_size)
    except Exception as e:
        logger.error(f"Failed {f_in.name}: {e}")
        return None

def main() -> None:
    parser = argparse.ArgumentParser(description='Slim down EPUB files by removing media resources')
    parser.add_argument('-i', '--input', required=True, help='Input EPUB file or directory')
    parser.add_argument('-o', '--output', required=True, help='Output EPUB file or directory')
    parser.add_argument('-j', '--jobs', type=int, default=1, help='Number of parallel jobs (default: 1)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        sys.exit(1)

    tasks: List[Tuple[Path, Path]] = []

    if input_path.is_file():
        if output_path.suffix.lower() == '.epub':
            tasks = [(input_path, output_path)]
        else:
            output_path.mkdir(parents=True, exist_ok=True)
            tasks = [(input_path, output_path / input_path.name)]
    elif input_path.is_dir():
        output_path.mkdir(parents=True, exist_ok=True)
        epub_files = list(input_path.glob("*.epub"))
        if not epub_files:
            logger.warning(f"No EPUB files found in {input_path}")
            return
        tasks = [(f, output_path / f.name) for f in epub_files]
    else:
        logger.error(f"Invalid input path: {input_path}")
        sys.exit(1)

    logger.info(f"Processing {len(tasks)} file(s)...")

    if len(tasks) == 1 or args.jobs == 1:
        for task in tasks:
            result = process_single_file(task)
            if result:
                name, old_size, new_size = result
                print(f"Processed {name}: {old_size//1024}KB -> {new_size//1024}KB")
    else:
        max_workers = min(args.jobs, len(tasks))
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_file, task): task for task in tasks}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    name, old_size, new_size = result
                    print(f"Processed {name}: {old_size//1024}KB -> {new_size//1024}KB")

    logger.info("Done!")


if __name__ == '__main__':
    main()