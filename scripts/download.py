#!/usr/bin/env python3
"""
MangaDex Downloader → GitHub Pages PWA
Usage:
  python download.py <manga_url_or_id> [--lang vi] [--start 1] [--end 50] [--out ../docs]

Requires: pip install requests tqdm
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
import requests
from tqdm import tqdm

BASE_API = "https://api.mangadex.org"
HEADERS = {"User-Agent": "MangaPWA/1.0 (personal offline reader)"}
session = requests.Session()
session.headers.update(HEADERS)

def parse_manga_id(url_or_id: str) -> str:
    m = re.search(r"title/([0-9a-f-]{36})", url_or_id)
    return m.group(1) if m else url_or_id.strip()

def api_get(path: str, params: dict = None, retries=5) -> dict:
    url = f"{BASE_API}{path}"
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 60))
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e

def get_manga_info(manga_id: str) -> dict:
    data = api_get(f"/manga/{manga_id}", {"includes[]": ["cover_art", "author", "artist"]})
    return data["data"]

def get_chapters(manga_id: str, lang: str, start_ch=None, end_ch=None) -> list:
    chapters = []
    offset = 0
    limit = 100
    while True:
        params = {
            "translatedLanguage[]": lang,
            "order[chapter]": "asc",
            "limit": limit,
            "offset": offset,
        }
        data = api_get(f"/manga/{manga_id}/feed", params)
        batch = data.get("data", [])
        if not batch:
            break
        for ch in batch:
            attr = ch["attributes"]
            ch_num_str = attr.get("chapter")
            if ch_num_str is None:
                continue
            try:
                ch_num = float(ch_num_str)
            except ValueError:
                continue
            if start_ch is not None and ch_num < start_ch:
                continue
            if end_ch is not None and ch_num > end_ch:
                continue
            chapters.append(ch)
        offset += limit
        if offset >= data.get("total", 0):
            break
        time.sleep(0.3)
    # deduplicate: keep one per chapter number (prefer longer page count)
    seen = {}
    for ch in chapters:
        num = ch["attributes"].get("chapter", "0")
        pages = ch["attributes"].get("pages", 0)
        if num not in seen or pages > seen[num]["attributes"].get("pages", 0):
            seen[num] = ch
    return sorted(seen.values(), key=lambda c: float(c["attributes"]["chapter"]))

def get_chapter_images(chapter_id: str) -> tuple[str, list]:
    data = api_get(f"/at-home/server/{chapter_id}")
    base = data["baseUrl"]
    ch = data["chapter"]
    files = ch["data"]  # use "dataSaver" for compressed
    return base, ch["hash"], files

def download_chapter(chapter: dict, out_dir: Path) -> list:
    ch_id = chapter["id"]
    attr = chapter["attributes"]
    ch_num = attr.get("chapter", "0")
    title = attr.get("title") or f"Chapter {ch_num}"

    ch_dir = out_dir / f"ch{ch_num.zfill(4)}"
    meta_file = ch_dir / "meta.json"

    if ch_dir.exists() and meta_file.exists():
        print(f"  [skip] Chapter {ch_num} already downloaded")
        return json.loads(meta_file.read_text())["pages"]

    ch_dir.mkdir(parents=True, exist_ok=True)
    base_url, hash_, files = get_chapter_images(ch_id)

    pages = []
    for i, fname in enumerate(tqdm(files, desc=f"  Ch {ch_num}", leave=False)):
        img_url = f"{base_url}/data/{hash_}/{fname}"
        ext = Path(fname).suffix
        local_name = f"page_{i+1:03d}{ext}"
        local_path = ch_dir / local_name

        if not local_path.exists():
            for attempt in range(5):
                try:
                    r = session.get(img_url, timeout=30)
                    r.raise_for_status()
                    local_path.write_bytes(r.content)
                    break
                except Exception:
                    if attempt == 4:
                        print(f"  Failed to download {fname}")
                    time.sleep(2 ** attempt)
        pages.append(local_name)
        time.sleep(0.1)

    meta = {"chapter": ch_num, "title": title, "pages": pages, "id": ch_id}
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return pages

def build_manifest(manga_info: dict, out_dir: Path, chapters_meta: list):
    attr = manga_info["attributes"]
    title = attr.get("title", {}).get("en") or next(iter(attr.get("title", {}).values()), "Manga")

    manifest = {
        "title": title,
        "chapters": chapters_meta
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"  Wrote manifest.json with {len(chapters_meta)} chapters")

def main():
    ap = argparse.ArgumentParser(description="Download MangaDex manga for PWA")
    ap.add_argument("url", help="MangaDex manga URL or ID")
    ap.add_argument("--lang", default="vi", help="Language code (vi, en, ja, ...)")
    ap.add_argument("--start", type=float, default=None, help="Start chapter number")
    ap.add_argument("--end", type=float, default=None, help="End chapter number")
    ap.add_argument("--out", default="../docs/chapters", help="Output directory")
    args = ap.parse_args()

    manga_id = parse_manga_id(args.url)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Fetching manga info: {manga_id}")
    manga_info = get_manga_info(manga_id)
    attr = manga_info["attributes"]
    title = attr.get("title", {}).get("en") or next(iter(attr.get("title", {}).values()), "Manga")
    print(f"  Title: {title}")

    print(f"[2/3] Fetching chapter list (lang={args.lang}) ...")
    chapters = get_chapters(manga_id, args.lang, args.start, args.end)
    print(f"  Found {len(chapters)} chapters")

    if not chapters:
        print("No chapters found. Try --lang en")
        sys.exit(1)

    chapters_meta = []
    print(f"[3/3] Downloading {len(chapters)} chapters to {out_dir}")
    for ch in chapters:
        ch_num = ch["attributes"]["chapter"]
        ch_title = ch["attributes"].get("title") or f"Chapter {ch_num}"
        print(f"  Downloading Chapter {ch_num}: {ch_title}")
        pages = download_chapter(ch, out_dir)
        chapters_meta.append({
            "chapter": ch_num,
            "title": ch_title,
            "dir": f"ch{ch_num.zfill(4)}",
            "pages": pages
        })
        time.sleep(0.5)

    build_manifest(manga_info, out_dir.parent, chapters_meta)
    print("\nDone! Run: cd docs && python -m http.server 8080")

if __name__ == "__main__":
    main()
