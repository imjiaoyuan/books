import os
import sys
import glob
import shutil
import tempfile
import re
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup

def clean_file(file_path):
    book = epub.read_epub(file_path)
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
            except:
                pass
        
        elif item.get_type() == ebooklib.ITEM_STYLE:
            try:
                css = item.get_content().decode('utf-8', 'ignore')
                css = re.sub(r'@font-face\s*{[^}]*}', '', css, flags=re.DOTALL)
                item.set_content(css.encode('utf-8'))
            except:
                pass
                
        new_items.append(item)

    book.items = new_items
    
    fd, tmp_path = tempfile.mkstemp()
    os.close(fd)
    epub.write_epub(tmp_path, book)
    
    os.remove(file_path)
    shutil.move(tmp_path, file_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)

    target_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(target_dir):
        sys.exit(1)

    epub_files = glob.glob(os.path.join(target_dir, "*.epub"))
    
    for f in epub_files:
        try:
            old_size = os.path.getsize(f)
            clean_file(f)
            new_size = os.path.getsize(f)
            print(f"Processed {os.path.basename(f)}: {old_size//1024}KB -> {new_size//1024}KB")
        except Exception as e:
            print(f"Failed {os.path.basename(f)}: {e}")