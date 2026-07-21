import os
import shutil
import json

CH_DIR = os.path.join("docs", "chapters")

def organize():
    if not os.path.exists(CH_DIR):
        print("Chapters directory not found.")
        return

    # 1. Organize Nippon Sangoku
    ns_dir = os.path.join(CH_DIR, "nippon-sangoku")
    os.makedirs(ns_dir, exist_ok=True)
    
    # Write manga.json for Nippon Sangoku
    with open(os.path.join(ns_dir, "manga.json"), "w", encoding="utf-8") as f:
        json.dump({"title": "Nippon Sangoku"}, f, ensure_ascii=False, indent=2)

    # Move folders ch0020 - ch0040
    for item in os.listdir(CH_DIR):
        item_path = os.path.join(CH_DIR, item)
        if os.path.isdir(item_path) and item.startswith("ch") and item <= "ch0045":
            dest_path = os.path.join(ns_dir, item)
            print(f"Moving {item} -> nippon-sangoku/{item}")
            shutil.move(item_path, dest_path)

    # 2. Organize Hỏa Phụng Liêu Nguyên
    hpln_dir = os.path.join(CH_DIR, "hoa-phung-lieu-nguyen")
    os.makedirs(hpln_dir, exist_ok=True)
    
    # Write manga.json for Hỏa Phụng Liêu Nguyên
    with open(os.path.join(hpln_dir, "manga.json"), "w", encoding="utf-8") as f:
        json.dump({"title": "Hỏa Phụng Liêu Nguyên"}, f, ensure_ascii=False, indent=2)

    # Move folders ch0500 - ch0633
    for item in os.listdir(CH_DIR):
        item_path = os.path.join(CH_DIR, item)
        # Skip if it is one of the manga folders
        if item in ["nippon-sangoku", "hoa-phung-lieu-nguyen"]:
            continue
        if os.path.isdir(item_path) and item.startswith("ch") and item >= "ch0400":
            dest_path = os.path.join(hpln_dir, item)
            print(f"Moving {item} -> hoa-phung-lieu-nguyen/{item}")
            shutil.move(item_path, dest_path)

    print("Organization completed.")

if __name__ == "__main__":
    organize()
