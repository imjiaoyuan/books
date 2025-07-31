import os
import shutil
import glob
from urllib.parse import urldefrag
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import re
import argparse

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

def natural_sort_key(filename):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename)]

def create_master_index(output_dir, books_list):
    books_html_list = "".join(
        f'<li class="book"><a href="{book["path"]}"><span>{book["title"]}</span></a></li>' for book in books_list
    )
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My Bookshelf</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: #f8f9fa;
                margin: 0;
                padding: 1em;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            h1 {{
                text-align: center;
                font-size: 2.2em;
                margin-bottom: 1.5em;
                color: #2c3e50;
                font-weight: 400;
            }}
            .book-list {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                gap: 1.5em;
                list-style-type: none;
                padding: 0;
            }}
            .book a {{
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                min-height: 200px;
                padding: 1em;
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                text-decoration: none;
                color: #343a40;
                text-align: center;
                font-weight: 600;
                font-size: 0.95em;
                transition: all 0.2s ease-in-out;
                box-sizing: border-box;
                overflow: hidden;
            }}
            .book a:hover {{
                transform: translateY(-5px);
                box-shadow: 0 8px 12px rgba(0, 0, 0, 0.1);
                border-color: #007bff;
            }}
            .book a span {{
                display: -webkit-box;
                -webkit-box-orient: vertical;
                -webkit-line-clamp: 4;
                line-clamp: 4;
                overflow: hidden;
                word-break: break-word;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>My Bookshelf</h1>
            <ul class="book-list">
                {books_html_list}
            </ul>
        </div>
    </body>
    </html>
    """
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

def add_navigation_buttons(soup, prev_chapter, next_chapter, book_title):
    if not soup.body:
        return

    nav_style = """
    .chapter-navigation {
        margin-top: 3em;
        padding-top: 1.5em;
        border-top: 1px solid #aaaaaa;
        text-align: center;
        font-size: 1em;
    }
    .chapter-navigation a {
        color: #0056b3;
        text-decoration: underline;
        margin: 0 1em;
    }
    .chapter-navigation a:hover {
        color: #003d7c;
    }
    .chapter-navigation .disabled {
        color: #999999;
        text-decoration: none;
        margin: 0 1em;
        cursor: not-allowed;
    }
    """
    
    existing_style = soup.find('style')
    if existing_style:
        existing_style.string += nav_style
    elif soup.head:
        style_tag = soup.new_tag('style', string=nav_style)
        soup.head.append(style_tag)

    nav_div = soup.new_tag('div', **{'class': 'chapter-navigation'})

    if prev_chapter:
        prev_link = soup.new_tag('a', href=prev_chapter)
        prev_link.string = '← Prev'
        nav_div.append(prev_link)
    else:
        prev_disabled = soup.new_tag('span', **{'class': 'disabled'})
        prev_disabled.string = '← Prev'
        nav_div.append(prev_disabled)

    home_link = soup.new_tag('a', href='../index.html')
    home_link.string = 'Contents'
    nav_div.append(home_link)

    bookshelf_link = soup.new_tag('a', href='../../index.html')
    bookshelf_link.string = 'Bookshelf'
    nav_div.append(bookshelf_link)

    if next_chapter:
        next_link = soup.new_tag('a', href=next_chapter)
        next_link.string = 'Next →'
        nav_div.append(next_link)
    else:
        next_disabled = soup.new_tag('span', **{'class': 'disabled'})
        next_disabled.string = 'Next →'
        nav_div.append(next_disabled)

    soup.body.append(nav_div)

def convert_ebook_to_html(epub_path, output_dir):
    book = epub.read_epub(epub_path)
    try:
        book_title = book.get_metadata('DC', 'title')[0][0]
    except (IndexError, KeyError):
        book_title = os.path.splitext(os.path.basename(epub_path))[0]

    chapters_dir = os.path.join(output_dir, 'chapters')
    os.makedirs(chapters_dir, exist_ok=True)

    chapter_files = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapter_files.append(os.path.basename(item.get_name()))
    
    chapter_files.sort(key=natural_sort_key)
    chapter_index = {filename: i for i, filename in enumerate(chapter_files)}

    title_map = {}
    def build_title_map(toc_items):
        for item in toc_items:
            link_item, children = (item, None) if isinstance(item, epub.Link) else item
            book_item = book.get_item_with_href(urldefrag(link_item.href).url)
            if book_item:
                title_map[os.path.basename(book_item.get_name())] = link_item.title
            if children: build_title_map(children)
    build_title_map(book.toc)

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            filename = item.get_name()
            content = item.get_content().decode('utf-8', 'ignore')
            soup = BeautifulSoup(content, 'lxml')
            
            for tag in soup.find_all(['img', 'image', 'svg']):
                parent = tag.parent
                if parent and parent.name in ['p', 'div'] and not parent.get_text(strip=True):
                    parent.decompose()
                else:
                    tag.decompose()
            
            for p_tag in soup.find_all('p'):
                if not p_tag.get_text(strip=True) and not p_tag.find_all(recursive=False):
                    p_tag.decompose()

            page_title = title_map.get(os.path.basename(filename), book_title)
            if soup.title:
                soup.title.string = page_title
            elif soup.head:
                soup.head.append(soup.new_tag('title', string=page_title))
                
            if soup.head:
                if not soup.find('meta', {'name': 'viewport'}):
                    meta_viewport = soup.new_tag('meta', attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0"})
                    soup.head.insert(0, meta_viewport)

                style_string = """
                body {
                    font-family: serif;
                    max-width: 800px;
                    margin: 1em auto;
                    padding: 0 1em;
                    line-height: 1.8;
                    font-size: 1.1em;
                    background-color: #cce8cf;
                    color: #333333;
                }
                a { color: #0056b3; text-decoration: none; }
                a:hover { text-decoration: underline; }
                p, div, h1, h2, h3, h4, h5, h6 {
                    margin-top: 0;
                    margin-bottom: 1em;
                    padding: 0;
                }
                p {
                    text-indent: 2em;
                }
                """
                style_tag = soup.new_tag('style', string=style_string)
                soup.head.append(style_tag)

            current_filename = os.path.basename(filename)
            if current_filename in chapter_index:
                current_idx = chapter_index[current_filename]
                prev_chapter = chapter_files[current_idx - 1] if current_idx > 0 else None
                next_chapter = chapter_files[current_idx + 1] if current_idx < len(chapter_files) - 1 else None
                add_navigation_buttons(soup, prev_chapter, next_chapter, book_title)
            
            with open(os.path.join(chapters_dir, os.path.basename(filename)), 'w', encoding='utf-8') as f:
                f.write(str(soup))
    
    toc_links = []
    def parse_toc(toc_items, is_nested=False):
        list_class = ' class="nested-list"' if is_nested else ''
        toc_links.append(f'<ul{list_class}>')
        for item in toc_items:
            link_item, children = (item, None) if isinstance(item, epub.Link) else item
            book_item = book.get_item_with_href(urldefrag(link_item.href).url)
            if book_item and book_item.get_type() == ebooklib.ITEM_DOCUMENT:
                href = f"chapters/{os.path.basename(book_item.get_name())}"
                toc_links.append(f'<li><a href="{href}">{link_item.title}</a>')
                if children:
                    parse_toc(children, is_nested=True)
                toc_links.append('</li>')
        toc_links.append('</ul>')
    parse_toc(book.toc)
    
    index_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Contents - {book_title}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 2em;
                background-color: #ffffff;
                color: #343a40;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                border-bottom: 1px solid #dee2e6;
                padding-bottom: 1em;
                margin-bottom: 2em;
            }}
            h1 {{
                font-size: 2em;
                font-weight: 500;
                color: #2c3e50;
                margin: 0;
            }}
            .bookshelf-link a {{
                color: #0056b3;
                text-decoration: underline;
                font-size: 1em;
            }}
            .bookshelf-link a:hover {{
                color: #003d7c;
            }}
            ul {{
                list-style: none;
                padding: 0;
                margin: 0;
            }}
            li a {{
                display: block;
                padding: 0.9em 1.2em;
                text-decoration: none;
                color: #343a40;
                font-size: 1.1em;
                border-bottom: 1px solid #e9ecef;
                transition: background-color 0.2s ease, color 0.2s ease;
            }}
            li:first-child a {{
                border-top: 1px solid #e9ecef;
            }}
            li a:hover {{
                background-color: #eef2f7;
                color: #0056b3;
            }}
            .nested-list a {{
                padding-left: 2.4em;
                font-size: 1em;
                color: #5a6268;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{book_title}</h1>
            <div class="bookshelf-link"><a href="../index.html">Back to Bookshelf</a></div>
        </div>
        <div>{''.join(toc_links)}</div>
    </body>
    </html>
    """
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    return book_title

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Convert a directory of .epub files to a browsable HTML bookshelf.")
    parser.add_argument('-i', '--input', required=True, help='Input directory containing .epub files.')
    parser.add_argument('-o', '--output', required=True, help='Main output directory for the HTML bookshelf.')
    args = parser.parse_args()

    input_directory = args.input
    main_output_directory = args.output

    if not os.path.isdir(input_directory):
        print(f"Error: Input directory not found: {input_directory}")
        exit(1)

    if os.path.isdir(main_output_directory):
        for item_name in os.listdir(main_output_directory):
            if item_name not in ['.git', '.gitignore', 'README.md', 'LICENSE', 'index.html', 'epub_to_html.py']:
                item_path = os.path.join(main_output_directory, item_name)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except OSError as e:
                    print(f"Warning: Could not remove {item_path}. Reason: {e}")
    else:
        os.makedirs(main_output_directory, exist_ok=True)
        
    ebook_files = sorted(glob.glob(os.path.join(input_directory, '*.epub')))

    if not ebook_files:
        print(f"No .epub files found in '{input_directory}'.")
        exit()

    converted_books = []
    for i, ebook_file_path in enumerate(ebook_files):
        book_name = os.path.basename(ebook_file_path)
        print(f"Processing [{i+1}/{len(ebook_files)}]: {book_name}")
        
        output_book_dir_name = os.path.splitext(book_name)[0]
        final_output_path = os.path.join(main_output_directory, output_book_dir_name)
        
        try:
            book_title = convert_ebook_to_html(ebook_file_path, final_output_path)
            converted_books.append({'title': book_title, 'path': f"{output_book_dir_name}/index.html"})
        except Exception as e:
            print(f"  -> Failed to convert {book_name}: {e}")
    
    if converted_books:
        create_master_index(main_output_directory, converted_books)
    
    print("Done.")