import os
import shutil
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

SRC_DIR = os.path.join("downloads", "Hỏa Phụng Liêu Nguyên")
DEST_DIR = os.path.join("docs", "chapters")

def clean_dest_dir():
    if os.path.exists(DEST_DIR):
        print(f"Cleaning destination directory: {DEST_DIR}")
        for item in os.listdir(DEST_DIR):
            item_path = os.path.join(DEST_DIR, item)
            if os.path.isdir(item_path) and item.startswith("ch"):
                shutil.rmtree(item_path)
    else:
        os.makedirs(DEST_DIR, exist_ok=True)

def natural_sort_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(s))]

def copy_chapters():
    clean_dest_dir()
    
    if not os.path.exists(SRC_DIR):
        print(f"Source directory not found: {SRC_DIR}")
        return
        
    copied_count = 0
    
    # List all folders in source directory
    src_folders = [f for f in os.listdir(SRC_DIR) if os.path.isdir(os.path.join(SRC_DIR, f))]
    
    # Sort folders naturally
    src_folders.sort(key=natural_sort_key)
    
    for folder in src_folders:
        src_path = os.path.join(SRC_DIR, folder)
        files = [f for f in os.listdir(src_path) if os.path.isfile(os.path.join(src_path, f))]
        
        if not files:
            continue
            
        # Parse chapter number
        # Example formats:
        # Ch_600 -> 600
        # Vol_63_Ch_500 -> 500
        # Vol_66_Ch_519_Ch 519 - 521 -> 519
        ch_num = None
        ch_title = None
        
        # Try to find a range first, e.g. "519 - 521"
        range_match = re.search(r'Ch\s+(\d+\s*-\s*\d+)', folder)
        if range_match:
            ch_range = range_match.group(1).replace(" ", "")
            ch_num = ch_range.split("-")[0]
            ch_title = f"Chương {range_match.group(1)}"
        else:
            # Standard single chapter number
            ch_match = re.search(r'Ch_(\d+)', folder)
            if ch_match:
                ch_num = ch_match.group(1)
                ch_title = f"Chương {ch_num}"
                
        if not ch_num:
            # Fallback to any number in the folder name
            num_matches = re.findall(r'\d+', folder)
            if num_matches:
                ch_num = num_matches[-1] # Use the last number
                ch_title = f"Chương {ch_num}"
            else:
                print(f"Could not parse chapter number from folder name: {folder}. Skipping.")
                continue
                
        dest_folder_name = f"ch{ch_num.zfill(4)}"
        dest_path = os.path.join(DEST_DIR, dest_folder_name)
        os.makedirs(dest_path, exist_ok=True)
        
        # Sort files naturally to ensure correct page order
        files.sort(key=natural_sort_key)
        
        pages = []
        for idx, filename in enumerate(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                continue
                
            dest_filename = f"page_{idx+1:03d}{ext}"
            src_file_path = os.path.join(src_path, filename)
            dest_file_path = os.path.join(dest_path, dest_filename)
            
            shutil.copy2(src_file_path, dest_file_path)
            pages.append(dest_filename)
            
        # Create meta.json
        meta = {
            "chapter": ch_num,
            "title": ch_title,
            "pages": pages
        }
        
        with open(os.path.join(dest_path, "meta.json"), "w", encoding="utf-8") as mf:
            json.dump(meta, mf, ensure_ascii=False, indent=2)
            
        print(f"Copied {folder} -> {dest_folder_name} ({len(pages)} pages)")
        copied_count += 1
        
    print(f"\nSuccessfully copied {copied_count} chapters to {DEST_DIR}.")

if __name__ == "__main__":
    copy_chapters()
