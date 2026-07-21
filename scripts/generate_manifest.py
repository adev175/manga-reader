import argparse
import json
import re
import sys
from pathlib import Path

# Fix console encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif'}

def natural_sort_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', str(s))]

def scan_manga_directory(manga_dir: Path) -> list:
    chapters = []
    # Scan chXXXX directories
    for d in sorted(manga_dir.iterdir(), key=lambda p: natural_sort_key(p.name)):
        if not d.is_dir() or not d.name.startswith("ch"):
            continue

        meta_file = d / "meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                ch_num = meta.get("chapter", d.name)
                ch_title = meta.get("title", f"Chapter {ch_num}")
                pages = meta.get("pages", [])
            except Exception as e:
                print(f"  Error reading {meta_file}: {e}")
                continue
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

        # Keep relative path under chapters/, e.g., "nippon-sangoku/ch0020" or just "ch0020"
        rel_dir = d.relative_to(manga_dir.parent).as_posix()

        chapters.append({
            "chapter": ch_num,
            "title": ch_title,
            "dir": rel_dir,
            "pages": pages,
        })
    return chapters

def scan(docs_dir: Path, title: str):
    ch_dir = docs_dir / "chapters"
    if not ch_dir.exists():
        print(f"Not found: {ch_dir}")
        return

    # Check if we have subdirectories containing chapters (Multi-manga structure)
    subdirs = [p for p in ch_dir.iterdir() if p.is_dir() and not p.name.startswith("ch")]
    
    if subdirs:
        print("Detected multi-manga structure:")
        mangas = []
        for manga_path in sorted(subdirs, key=lambda p: p.name.lower()):
            manga_json_file = manga_path / "manga.json"
            manga_title = manga_path.name.replace("-", " ").title()
            if manga_json_file.exists():
                try:
                    manga_meta = json.loads(manga_json_file.read_text(encoding="utf-8"))
                    manga_title = manga_meta.get("title", manga_title)
                except Exception as e:
                    print(f"  Error reading {manga_json_file}: {e}")

            print(f"Scanning manga: {manga_title} ({manga_path.name})")
            chapters = scan_manga_directory(manga_path)
            
            if chapters:
                mangas.append({
                    "id": manga_path.name,
                    "title": manga_title,
                    "chapters": chapters
                })
                print(f"  Added {len(chapters)} chapters")
        
        manifest = {
            "title": "Manga Library",
            "mangas": mangas
        }
        out = docs_dir / "manifest.json"
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote multi-manga manifest to {out} — {len(mangas)} mangas total")
    else:
        # Fallback to single manga structure
        print("Detected single-manga structure:")
        chapters = scan_manga_directory(ch_dir)
        manifest = {"title": title, "chapters": chapters}
        out = docs_dir / "manifest.json"
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote single-manga manifest to {out} — {len(chapters)} chapters total")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="../docs")
    ap.add_argument("--title", default="Manga")
    args = ap.parse_args()
    scan(Path(args.docs), args.title)
