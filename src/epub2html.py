import os
import sys
import glob
from urllib.parse import urldefrag
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import re

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
BASE_TPL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def load_tpl(name):
    with open(os.path.join(BASE_TPL_DIR, name), 'r', encoding='utf-8') as f:
        return f.read()

def create_master_index(output_dir, books):
    books.sort(key=lambda x: x['title'])
    items = "".join([f'<li><a href="{b["path"]}">{b["title"]}</a></li>' for b in books])
    out_file = os.path.join(output_dir, 'index.html')
    html = load_tpl('layout_shelf.html').replace('{title}', 'My Bookshelf').replace('{content}', items)
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html)

def convert_ebook(epub_path, book_root):
    book = epub.read_epub(epub_path)
    try:
        title = book.get_metadata('DC', 'title')[0][0]
    except:
        title = os.path.splitext(os.path.basename(epub_path))[0]

    chapters_dir = os.path.join(book_root, 'chapters')
    os.makedirs(chapters_dir, exist_ok=True)

    items = [i for i in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
    sorted_items = sorted(items, key=lambda x: natural_sort_key(os.path.basename(x.get_name())))

    filenames_map = {os.path.basename(item.get_name()): f"{i+1}.html" for i, item in enumerate(sorted_items)}
    sorted_orig_names = [os.path.basename(item.get_name()) for item in sorted_items]

    tpl_chapter = load_tpl('layout_chapter.html')
    for item in sorted_items:
        orig_fname = os.path.basename(item.get_name())
        out_fname = filenames_map[orig_fname]
        out_chap_path = os.path.join(chapters_dir, out_fname)
        
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
            target = book.get_item_with_href(urldefrag(link.href).url)
            if target and target.get_type() == ebooklib.ITEM_DOCUMENT:
                t_orig = os.path.basename(target.get_name())
                if t_orig in filenames_map:
                    toc_list.append(f'<li><a href="chapters/{filenames_map[t_orig]}">{link.title}</a>')
                    if child: walk_toc(child)
                    toc_list.append('</li>')
        toc_list.append('</ul>')

    walk_toc(book.toc)
    out_toc = os.path.join(book_root, 'index.html')
    final_toc = load_tpl('layout_toc.html').replace('{title}', title).replace('{toc_content}', "".join(toc_list)).replace('../index.html', '../../index.html')
    with open(out_toc, 'w', encoding='utf-8') as f:
        f.write(final_toc)
    return title

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(1)
    in_d, out_d = sys.argv[1], sys.argv[2]
    books_dir = os.path.join(out_d, 'books')
    os.makedirs(books_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(in_d, '*.epub')))
    data = []
    for i, p in enumerate(files):
        folder = os.path.splitext(os.path.basename(p))[0]
        try:
            t = convert_ebook(p, os.path.join(books_dir, folder))
            data.append({'title': t, 'path': f"books/{folder}/index.html"})
        except:
            pass
    create_master_index(out_d, data)