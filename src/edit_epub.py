import sys
import os
import shutil
import tempfile
from ebooklib import epub

def run_editor():
    if len(sys.argv) < 2:
        sys.exit(1)

    path = os.path.abspath(sys.argv[1])
    if not os.path.exists(path):
        sys.exit(1)

    book = epub.read_epub(path)

    titles = book.get_metadata('DC', 'title')
    current_title = titles[0][0] if titles else "Unknown"
    print(f"\n[Title Editing]\nCurrent title: {current_title}")
    new_title = input("Enter new title (Enter to skip): ").strip()
    
    if new_title:
        # 强力清除旧标题元数据，防止重复或读取旧值
        if 'http://purl.org/dc/elements/1.1/' in book.metadata:
            book.metadata['http://purl.org/dc/elements/1.1/']['title'] = []
        book.set_title(new_title)

    all_links = []
    def collect_links(items):
        for item in items:
            if isinstance(item, tuple):
                if len(item) > 0 and isinstance(item[0], epub.Link):
                    all_links.append(item[0])
                if len(item) > 1:
                    collect_links(item[1])
            elif isinstance(item, epub.Link):
                all_links.append(item)
    
    collect_links(book.toc)

    while True:
        print("\n[Chapter Editing]")
        for i, link in enumerate(all_links):
            print(f"[{i}] {link.title}")
        
        cmd = input("\nEnter index to rename chapter, or 's' to save, 'q' to quit: ").strip().lower()
        
        if cmd == 'q':
            sys.exit(0)
        if cmd == 's':
            book.toc = list(book.toc)
            break
        
        try:
            idx = int(cmd)
            if 0 <= idx < len(all_links):
                old_name = all_links[idx].title
                new_name = input(f"New name for '{old_name}': ").strip()
                if new_name:
                    all_links[idx].title = new_name
            else:
                print("Invalid index.")
        except ValueError:
            print("Invalid input.")

    save_path = input(f"\nSave as (default: {path}): ").strip() or path
    save_path = os.path.abspath(save_path)

    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    
    try:
        epub.write_epub(temp_path, book)
        if os.path.exists(save_path):
            os.remove(save_path)
        shutil.move(temp_path, save_path)
        print(f"Saved to: {save_path}")
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"Error: {e}")

if __name__ == '__main__':
    run_editor()