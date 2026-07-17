import os
import sys
import time
import argparse
import requests
# No tqdm needed

sys.stdout.reconfigure(encoding='utf-8')

API_BASE_URL = "https://api.mangadex.org"

def get_manga_title(manga_id):
    url = f"{API_BASE_URL}/manga/{manga_id}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    title_dict = data['data']['attributes']['title']
    if not title_dict:
        return 'Unknown Manga'
    for lang in ['en', 'vi', 'ja', 'zh', 'zh-hk']:
        if lang in title_dict:
            return title_dict[lang]
    return next(iter(title_dict.values()))

def fetch_all_chapters(manga_id, lang):
    feed_url = f"{API_BASE_URL}/manga/{manga_id}/feed"
    params = {
        'limit': 500,
        'offset': 0,
        'translatedLanguage[]': [lang],
        'order[chapter]': 'asc'
    }
    
    chapters = []
    offset = 0
    print(f"Fetching chapter list for language '{lang}'...")
    while True:
        params['offset'] = offset
        r = requests.get(feed_url, params=params)
        r.raise_for_status()
        res = r.json()
        data = res.get('data', [])
        if not data:
            break
        chapters.extend(data)
        if len(data) < params['limit']:
            break
        offset += len(data)
        
    print(f"Found {len(chapters)} chapter records in language '{lang}'.")
    return chapters

def group_and_deduplicate(chapters):
    # Group chapters by chapter number
    grouped = {}
    for ch in chapters:
        attrs = ch.get('attributes', {})
        ch_num = attrs.get('chapter')
        if ch_num is None:
            continue
        
        # Parse chapter number as float for sorting, fallback to string if fails
        try:
            ch_num_val = float(ch_num)
        except ValueError:
            ch_num_val = ch_num

        vol = attrs.get('volume', 'N/A')
        title = attrs.get('title', '')
        group_id = ""
        # Find group relationship
        for rel in ch.get('relationships', []):
            if rel['type'] == 'scanlation_group':
                group_id = rel['id']
                
        ch_data = {
            'id': ch['id'],
            'chapter': ch_num,
            'volume': vol,
            'title': title,
            'group_id': group_id,
            'pages': attrs.get('pages', 0)
        }
        
        if ch_num not in grouped:
            grouped[ch_num] = []
        grouped[ch_num].append(ch_data)
        
    # Deduplicate: pick the entry with the most pages, or first if equal
    deduped = {}
    for ch_num, list_chs in grouped.items():
        # Sort by number of pages descending, then group ID completeness
        best_ch = sorted(list_chs, key=lambda x: x['pages'], reverse=True)[0]
        deduped[ch_num] = best_ch
        
    return deduped

def download_page(url, save_path, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                f.write(r.content)
            return True
        except Exception as e:
            if i == retries - 1:
                print(f"\nFailed to download {url} after {retries} retries: {e}")
                return False
            time.sleep(2)

def download_chapter(chapter_id, folder_name, out_dir, quality, delay):
    # Create folder for the chapter
    chapter_dir = os.path.join(out_dir, folder_name)
    os.makedirs(chapter_dir, exist_ok=True)
    
    # Fetch At-Home server URL and page list
    athome_url = f"{API_BASE_URL}/at-home/server/{chapter_id}"
    athome_data = None
    for attempt in range(5):
        try:
            r = requests.get(athome_url, timeout=30)
            if r.status_code == 429:
                wait_time = int(r.headers.get("Retry-After", 10))
                print(f"Rate limited. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            r.raise_for_status()
            athome_data = r.json()
            break
        except Exception as e:
            if attempt == 4:
                print(f"Failed to get image server for chapter {chapter_id} after 5 attempts: {e}")
                return False
            time.sleep(2 ** attempt)
            
    if not athome_data:
        return False
        
    base_url = athome_data.get('baseUrl')
    chapter_hash = athome_data.get('chapter', {}).get('hash')
    
    # Quality select
    q_key = 'data' if quality == 'original' else 'dataSaver'
    filenames = athome_data.get('chapter', {}).get(q_key, [])
    
    if not filenames:
        print(f"No pages found for chapter {chapter_id}.")
        return False
        
    print(f"Downloading {len(filenames)} pages for '{folder_name}'...")
    
    success_count = 0
    for idx, filename in enumerate(filenames):
        # Extract file extension
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = ".jpg"
            
        page_num = idx + 1
        page_filename = f"Page_{page_num:03d}{ext}"
        save_path = os.path.join(chapter_dir, page_filename)
        
        # Skip if page already exists and is non-empty
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1024:
            success_count += 1
            continue
            
        url_quality_path = 'data' if quality == 'original' else 'data-saver'
        page_url = f"{base_url}/{url_quality_path}/{chapter_hash}/{filename}"
        
        if download_page(page_url, save_path):
            success_count += 1
            time.sleep(delay)
            
    print(f"Done: {success_count}/{len(filenames)} pages downloaded successfully.")
    return success_count == len(filenames)

def parse_chapters_range(chapters_str, available_chapters):
    if not chapters_str or chapters_str.lower() == 'all':
        return sorted(list(available_chapters.keys()), key=lambda x: float(x) if x.replace('.','',1).isdigit() else -1)
        
    selected = []
    parts = chapters_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-')
                start_f = float(start.strip())
                end_f = float(end.strip())
                # Find all available chapters within this range
                for ch_num in available_chapters.keys():
                    try:
                        ch_num_f = float(ch_num)
                        if start_f <= ch_num_f <= end_f:
                            selected.append(ch_num)
                    except ValueError:
                        pass
            except ValueError:
                print(f"Warning: Invalid range format '{part}'")
        else:
            if part in available_chapters:
                selected.append(part)
            else:
                # Try float matching
                try:
                    part_f = float(part)
                    for ch_num in available_chapters.keys():
                        try:
                            if float(ch_num) == part_f:
                                selected.append(ch_num)
                        except ValueError:
                            pass
                except ValueError:
                    print(f"Warning: Chapter '{part}' is not available.")
                    
    # Remove duplicates and sort
    selected = list(set(selected))
    return sorted(selected, key=lambda x: float(x) if x.replace('.','',1).isdigit() else -1)

def main():
    parser = argparse.ArgumentParser(description="MangaDex Chapter Downloader")
    parser.add_argument("--manga-id", default="f6ce20ca-73c3-4fdd-9367-e2901fca780e", help="MangaDex Manga ID")
    parser.add_argument("--lang", default="vi", choices=["vi", "en", "ja"], help="Translation language")
    parser.add_argument("--chapters", default="", help="Chapters to download, e.g. '1-5', '10', '1,2,5-7', or 'all'")
    parser.add_argument("--out-dir", default="", help="Output directory")
    parser.add_argument("--quality", default="original", choices=["original", "saver"], help="Image quality (original or saver)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between page requests (seconds)")
    
    args = parser.parse_args()
    
    manga_id = args.manga_id
    lang = args.lang
    
    try:
        manga_title = get_manga_title(manga_id)
        print(f"Manga Title: {manga_title}")
    except Exception as e:
        print(f"Failed to verify manga ID {manga_id}: {e}")
        return
        
    out_dir = args.out_dir
    if not out_dir:
        # Create safe folder name
        if manga_id == "f6ce20ca-73c3-4fdd-9367-e2901fca780e":
            safe_title = "Hỏa Phụng Liêu Nguyên"
        else:
            safe_title = "".join(c for c in manga_title if c.isalnum() or c in (' ', '_', '-')).strip()
        out_dir = os.path.join("downloads", safe_title)
        
    os.makedirs(out_dir, exist_ok=True)
    print(f"Output directory: {os.path.abspath(out_dir)}")
    
    raw_chapters = fetch_all_chapters(manga_id, lang)
    if not raw_chapters:
        print(f"No chapters found for language '{lang}'.")
        return
        
    deduped_chapters = group_and_deduplicate(raw_chapters)
    
    # Sort chapter keys
    def parse_key(k):
        try:
            return float(k)
        except ValueError:
            return -1.0
            
    sorted_keys = sorted(deduped_chapters.keys(), key=parse_key)
    
    if sorted_keys:
        print(f"Available chapters range: {sorted_keys[0]} to {sorted_keys[-1]} (Total: {len(sorted_keys)} distinct chapters)")
    else:
        print("No distinct chapters found.")
        return
        
    chapters_str = args.chapters
    if not chapters_str:
        print("\nEnter chapters to download (e.g., '1-5' for chapters 1 to 5, '10,12' for specific chapters, 'all' for all chapters):")
        chapters_str = input("Chapters: ").strip()
        
    selected_chapters = parse_chapters_range(chapters_str, deduped_chapters)
    
    if not selected_chapters:
        print("No valid chapters selected for download.")
        return
        
    print(f"\nPreparing to download {len(selected_chapters)} chapters: {', '.join(selected_chapters[:10])}{'...' if len(selected_chapters) > 10 else ''}")
    
    for ch_num in selected_chapters:
        ch_info = deduped_chapters[ch_num]
        vol = ch_info['volume']
        title_str = ch_info['title']
        ch_id = ch_info['id']
        
        # Build clean folder name
        vol_part = f"Vol_{vol}_" if vol not in [None, 'N/A', ''] else ""
        title_part = f"_{title_str}" if title_str else ""
        safe_title_part = "".join(c for c in title_part if c.isalnum() or c in (' ', '_', '-')).strip()
        folder_name = f"{vol_part}Ch_{ch_num}{safe_title_part}"
        
        print(f"\n--- Downloading Chapter {ch_num} (ID: {ch_id}) ---")
        success = download_chapter(ch_id, folder_name, out_dir, args.quality, args.delay)
        if success:
            print(f"Chapter {ch_num} downloaded successfully.")
        else:
            print(f"Chapter {ch_num} finished with errors.")
        # Sleep between chapters to avoid triggering rate limit (429)
        time.sleep(1.0)
            
    print(f"\nAll downloads completed. Files are saved in: {os.path.abspath(out_dir)}")
