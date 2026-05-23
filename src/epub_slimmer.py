import os
import sys
import glob
import shutil
import tempfile
import re
import argparse
from ebooklib import epub
import ebooklib
from bs4 import BeautifulSoup

def clean_file(file_path, output_path):
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
    epub.write_epub(output_path, book)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', dest='input', required=True)
    parser.add_argument('-o', dest='output', required=True)
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if os.path.isfile(input_path):
        epub_files = [input_path]
        if output_path.lower().endswith('.epub'):
            tasks = [(input_path, output_path)]
        else:
            if not os.path.exists(output_path):
                os.makedirs(output_path)
            tasks = [(input_path, os.path.join(output_path, os.path.basename(input_path)))]
    elif os.path.isdir(input_path):
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        epub_files = glob.glob(os.path.join(input_path, "*.epub"))
        tasks = [(f, os.path.join(output_path, os.path.basename(f))) for f in epub_files]
    else:
        sys.exit(1)
    
    for f_in, f_out in tasks:
        try:
            old_size = os.path.getsize(f_in)
            out_dir = os.path.dirname(f_out)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir)
                
            clean_file(f_in, f_out)
            new_size = os.path.getsize(f_out)
            print(f"Processed {os.path.basename(f_in)}: {old_size//1024}KB -> {new_size//1024}KB")
        except Exception as e:
            print(f"Failed {os.path.basename(f_in)}: {e}")