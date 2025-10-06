#!/usr/bin/env python3
import os
import sys
import shutil
import glob
from urllib.parse import urldefrag
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import re

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
            :root {{
                --bg-color: #f8f9fa; --text-color: #343a40; --header-color: #2c3e50;
                --card-bg: #ffffff; --card-border: #dee2e6; --card-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                --card-hover-shadow: 0 8px 12px rgba(0, 0, 0, 0.1); --link-hover-border: #007bff;
            }}
            @media (prefers-color-scheme: dark) {{
                :root {{
                    --bg-color: #121212; --text-color: #e0e0e0; --header-color: #f1f1f1;
                    --card-bg: #1e1e1e; --card-border: #444444; --card-shadow: none;
                    --card-hover-shadow: none; --link-hover-border: #58a6ff;
                }}
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: var(--bg-color); color: var(--text-color); margin: 0; padding: 1em;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            h1 {{ text-align: center; font-size: 2.2em; margin-bottom: 1.5em; color: var(--header-color); font-weight: 400; }}
            .book-list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 1.5em; list-style-type: none; padding: 0; }}
            .book a {{
                display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 200px;
                padding: 1em; background-color: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px;
                box-shadow: var(--card-shadow); text-decoration: none; color: var(--text-color); text-align: center;
                font-weight: 600; font-size: 0.95em; transition: all 0.2s ease-in-out; box-sizing: border-box; overflow: hidden;
            }}
            .book a:hover {{ transform: translateY(-5px); box-shadow: var(--card-hover-shadow); border-color: var(--link-hover-border); }}
            .book a span {{ display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 4; line-clamp: 4; overflow: hidden; word-break: break-word; }}
        </style>
    </head>
    <body>
        <div class="container"><h1>My Bookshelf</h1><ul class="book-list">{books_html_list}</ul></div>
    </body>
    </html>
    """
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

def add_navigation_buttons(soup, prev_chapter, next_chapter):
    if not soup.body: return
    nav_div = soup.new_tag('div', **{'class': 'chapter-navigation'})
    prev_elem = soup.new_tag('a' if prev_chapter else 'span', href=prev_chapter)
    prev_elem.string = 'Prev'
    if not prev_chapter: prev_elem['class'] = 'disabled'
    nav_div.append(prev_elem)
    home_link = soup.new_tag('a', href='../index.html'); home_link.string = 'Contents'; nav_div.append(home_link)
    bookshelf_link = soup.new_tag('a', href='../../index.html'); bookshelf_link.string = 'Bookshelf'; nav_div.append(bookshelf_link)
    next_elem = soup.new_tag('a' if next_chapter else 'span', href=next_chapter)
    next_elem.string = 'Next'
    if not next_chapter: next_elem['class'] = 'disabled'
    nav_div.append(next_elem)
    soup.body.append(nav_div)

def convert_ebook_to_html(epub_path, output_dir):
    book = epub.read_epub(epub_path)
    try: book_title = book.get_metadata('DC', 'title')[0][0]
    except (IndexError, KeyError): book_title = os.path.splitext(os.path.basename(epub_path))[0]

    chapters_dir = os.path.join(output_dir, 'chapters')
    os.makedirs(chapters_dir, exist_ok=True)

    chapter_files = sorted([os.path.basename(item.get_name()) for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)], key=natural_sort_key)
    chapter_index = {filename: i for i, filename in enumerate(chapter_files)}

    title_map = {}
    def build_title_map(toc_items):
        for item in toc_items:
            link_item, children = (item, []) if isinstance(item, epub.Link) else item
            book_item = book.get_item_with_href(urldefrag(link_item.href).url)
            if book_item: title_map[os.path.basename(book_item.get_name())] = link_item.title
            if children: build_title_map(children)
    build_title_map(book.toc)

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        filename, content = item.get_name(), item.get_content().decode('utf-8', 'ignore')
        soup = BeautifulSoup(content, 'lxml')
        
        if soup.head:
            for s in soup.head.find_all(['style', 'link']):
                s.decompose()
        
        for tag in soup.find_all(['img', 'image', 'svg']): tag.decompose()
        for p_tag in soup.find_all('p', string=lambda s: not s or s.isspace()):
             if not p_tag.contents: p_tag.decompose()

        page_title = title_map.get(os.path.basename(filename), book_title)
        if soup.title: soup.title.string = page_title
        elif soup.head: soup.head.append(soup.new_tag('title', string=page_title))
            
        if soup.head:
            if not soup.find('meta', {'name': 'viewport'}):
                soup.head.insert(0, soup.new_tag('meta', attrs={"name": "viewport", "content": "width=device-width, initial-scale=1.0"}))
            
            style_string = """
            :root {
                --body-bg: #C7EDCC; --text-color: #2E4033; --link-color: #005a5a;
                --nav-border: #a5c5a9; --link-hover: #004848; --disabled-color: #7b8b7d;
            }
            @media (prefers-color-scheme: dark) {
                :root { 
                    --body-bg: #6E7B6C; --text-color: #d1d1d1; --link-color: #a8d7a8;
                    --nav-border: #535d52; --link-hover: #c3e3c3; --disabled-color: #929a91;
                }
            }
            html { overflow-x: hidden; }
            body { font-family: serif; max-width: 800px; margin: 1em auto; padding: 0 1em;
                   line-height: 1.8; font-size: 1.1em; background-color: var(--body-bg); color: var(--text-color); }
            a { color: var(--link-color); text-decoration: none; } a:hover { text-decoration: underline; }
            p, div, h1, h2, h3, h4, h5, h6 { margin-top: 0; margin-bottom: 1em; padding: 0; word-wrap: break-word; }
            p { text-indent: 2em; }
            .chapter-navigation { margin-top: 3em; padding-top: 1.5em; border-top: 1px solid var(--nav-border);
                                  font-size: 1em; display: flex; justify-content: center; align-items: center; flex-wrap: wrap; }
            .chapter-navigation a, .chapter-navigation .disabled { margin: 0 0.7em; white-space: nowrap; }
            .chapter-navigation a { color: var(--link-color); text-decoration: underline; }
            .chapter-navigation a:hover { color: var(--link-hover); }
            .chapter-navigation .disabled { color: var(--disabled-color); text-decoration: none; cursor: not-allowed; }
            """
            soup.head.append(soup.new_tag('style', string=style_string))

        current_filename = os.path.basename(filename)
        if current_filename in chapter_index:
            current_idx = chapter_index[current_filename]
            prev_chapter = chapter_files[current_idx - 1] if current_idx > 0 else None
            next_chapter = chapter_files[current_idx + 1] if current_idx < len(chapter_files) - 1 else None
            add_navigation_buttons(soup, prev_chapter, next_chapter)
        
        with open(os.path.join(chapters_dir, os.path.basename(filename)), 'w', encoding='utf-8') as f:
            f.write(str(soup))
    
    toc_links = []
    def parse_toc(toc_items, is_nested=False):
        toc_links.append(f'<ul class="{"nested-list" if is_nested else ""}">')
        for item in toc_items:
            link_item, children = (item, []) if isinstance(item, epub.Link) else item
            book_item = book.get_item_with_href(urldefrag(link_item.href).url)
            if book_item and book_item.get_type() == ebooklib.ITEM_DOCUMENT:
                href = f"chapters/{os.path.basename(book_item.get_name())}"
                toc_links.append(f'<li><a href="{href}">{link_item.title}</a>')
                if children: parse_toc(children, is_nested=True)
                toc_links.append('</li>')
        toc_links.append('</ul>')
    parse_toc(book.toc)
    
    index_html = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Contents - {book_title}</title>
    <style>
        :root {{
            --bg-color: #ffffff; --text-color: #343a40; --header-color: #2c3e50;
            --header-border: #dee2e6; --link-color: #0056b3; --link-hover: #003d7c;
            --item-border: #e9ecef; --item-hover-bg: #eef2f7; --nested-text: #5a6268;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #1c1c1c; --text-color: #e0e0e0; --header-color: #f1f1f1;
                --header-border: #444444; --link-color: #90caff; --link-hover: #c7e1ff;
                --item-border: #3a3a3a; --item-hover-bg: #2a2a2a; --nested-text: #bbbbbb;
            }}
        }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
               max-width: 800px; margin: 0 auto; padding: 2em; background-color: var(--bg-color); color: var(--text-color); }}
        .header {{ display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid var(--header-border);
                  padding-bottom: 1em; margin-bottom: 2em; }}
        h1 {{ font-size: 2em; font-weight: 500; color: var(--header-color); margin: 0; }}
        .bookshelf-link a {{ color: var(--link-color); text-decoration: underline; font-size: 1em; }}
        .bookshelf-link a:hover {{ color: var(--link-hover); }}
        ul {{ list-style: none; padding: 0; margin: 0; }}
        li a {{ display: block; padding: 0.9em 1.2em; text-decoration: none; color: var(--text-color);
                font-size: 1.1em; border-bottom: 1px solid var(--item-border); transition: background-color 0.2s ease, color 0.2s ease; }}
        li:first-child a {{ border-top: 1px solid var(--item-border); }}
        li a:hover {{ background-color: var(--item-hover-bg); color: var(--link-hover); }}
        .nested-list a {{ padding-left: 2.4em; font-size: 1em; color: var(--nested-text); }}
    </style></head><body>
        <div class="header"><h1>{book_title}</h1><div class="bookshelf-link"><a href="../index.html">Back to Bookshelf</a></div></div>
        <div>{''.join(toc_links)}</div>
    </body></html>
    """
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index_html)
    return book_title

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <input_directory> <output_directory>")
        sys.exit(1)

    input_directory, main_output_directory = sys.argv[1], sys.argv[2]

    if not os.path.isdir(input_directory):
        print(f"Error: Input directory not found: {input_directory}")
        sys.exit(1)

    os.makedirs(main_output_directory, exist_ok=True)
        
    ebook_files = sorted(glob.glob(os.path.join(input_directory, '*.epub')))
    if not ebook_files:
        print(f"No .epub files found in '{input_directory}'.")
        sys.exit()

    converted_books = []
    for i, ebook_file_path in enumerate(ebook_files):
        book_name = os.path.basename(ebook_file_path)
        output_book_dir_name = os.path.splitext(book_name)[0]
        final_output_path = os.path.join(main_output_directory, output_book_dir_name)
        
        target_index_html = os.path.join(final_output_path, 'index.html')
        
        if os.path.exists(target_index_html):
            source_mtime, target_mtime = os.path.getmtime(ebook_file_path), os.path.getmtime(target_index_html)
            if target_mtime > source_mtime:
                print(f"Skipping [{i+1}/{len(ebook_files)}]: {book_name} (already up-to-date)")
                book_title = os.path.splitext(book_name)[0]
                try: book_title = epub.read_epub(ebook_file_path).get_metadata('DC', 'title')[0][0]
                except Exception: pass
                converted_books.append({'title': book_title, 'path': f"{output_book_dir_name}/index.html"})
                continue
        
        print(f"Processing [{i+1}/{len(ebook_files)}]: {book_name}")
        try:
            book_title = convert_ebook_to_html(ebook_file_path, final_output_path)
            converted_books.append({'title': book_title, 'path': f"{output_book_dir_name}/index.html"})
        except Exception as e:
            print(f"  -> Failed to convert {book_name}: {e}")
    
    if converted_books:
        print("Creating bookshelf index...")
        create_master_index(main_output_directory, converted_books)
    
    print("Done.")