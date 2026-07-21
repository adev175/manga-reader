#!/usr/bin/env python3
"""
Scan docs/chapters/ và tạo lại manifest.json
Dùng khi bạn đã có folder ảnh sẵn mà chưa có manifest.
Usage: python generate_manifest.py [--docs ../docs] [--title "Nippon Sangoku"]
"""
import argparse, json, re
from pathlib import Path

IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif'}

def natural_sort_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(s))]

def scan(docs_dir: Path, title: str):
    ch_dir = docs_dir / "chapters"
    if not ch_dir.exists():
        print(f"Not found: {ch_dir}")
        return

    chapters = []
    for d in sorted(ch_dir.iterdir(), key=lambda p: natural_sort_key(p.name)):
        if not d.is_dir():
            continue

        meta_file = d / "meta.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            ch_num = meta.get("chapter", d.name)
            ch_title = meta.get("title", f"Chapter {ch_num}")
            pages = meta.get("pages", [])
        else:
            # auto-detect
            ch_name = d.name  # e.g. ch0040
            ch_num_match = re.search(r'(\d+(?:\.\d+)?)', ch_name)
            ch_num = ch_num_match.group(1).lstrip('0') or '0' if ch_num_match else ch_name
            ch_title = f"Chapter {ch_num}"
            pages = sorted([
                f.name for f in d.iterdir()
                if f.suffix.lower() in IMG_EXTS
            ], key=natural_sort_key)

        if not pages:
            print(f"  [skip] {d.name} — no images")
            continue

        chapters.append({
            "chapter": ch_num,
            "title": ch_title,
            "dir": d.name,
            "pages": pages,
        })
        print(f"  Ch {ch_num}: {len(pages)} pages")

    manifest = {"title": title, "chapters": chapters}
    out = docs_dir / "manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out} — {len(chapters)} chapters total")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="../docs")
    ap.add_argument("--title", default="Manga")
    args = ap.parse_args()
    scan(Path(args.docs), args.title)
