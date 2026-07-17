import os
import sys
import time
import requests
import asyncio
import re
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

# List of chapters to download from Facebook (only the ones missing/failed on MangaDex)
TARGET_CHAPTERS = [str(x) for x in range(600, 623)]  # 600 to 622

OUT_DIR_BASE = os.path.join("downloads", "Hỏa Phụng Liêu Nguyên")

def download_image(url, save_path):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"Failed to download image {url}: {e}")
        return False

async def inject_force_style(page):
    try:
        await page.evaluate("""() => {
            const styleId = 'force-scroll-style-antigravity';
            let style = document.getElementById(styleId);
            if (!style) {
                style = document.createElement('style');
                style.id = styleId;
                document.head.appendChild(style);
            }
            style.innerHTML = `
                html, body, #mount_0_0_, #scrollview {
                    overflow: auto !important;
                    overflow-y: auto !important;
                    height: auto !important;
                }
                div[style*="position: fixed"] {
                    display: none !important;
                }
                div[role="dialog"] {
                    display: none !important;
                }
            `;
        }""")
    except Exception:
        pass

async def load_albums_page(page):
    print(f"Navigating to albums list page...")
    await page.goto("https://www.facebook.com/hplnthucac/photos_albums")
    await page.wait_for_timeout(6000)
    
    # Try to click the close button of the login modal (up to 5 attempts)
    for attempt in range(5):
        clicked = await page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
            const closeBtn = buttons.find(btn => {
                const label = btn.getAttribute('aria-label') || '';
                const text = btn.innerText || '';
                return label.includes('Close') || label.includes('閉じる') || text === '✕' || text === 'X';
            });
            if (closeBtn) {
                closeBtn.click();
                return true;
            }
            return false;
        }""")
        if clicked:
            print(f"Successfully dismissed login modal on attempt {attempt+1}")
            await page.wait_for_timeout(2000)
            break
        await page.wait_for_timeout(1000)
        
    await inject_force_style(page)
    await page.wait_for_timeout(1000)

async def download_chapter(page, ch_num):
    ch_dir = os.path.join(OUT_DIR_BASE, f"Ch_{ch_num}")
    os.makedirs(ch_dir, exist_ok=True)
    
    # Check if all files are already downloaded
    # (We can check this first to avoid reloading the list page!)
    # Let's count existing files of reasonable size
    existing_files = [f for f in os.listdir(ch_dir) if f.startswith("Page_") and os.path.getsize(os.path.join(ch_dir, f)) > 1024]
    
    # Note: we don't know the exact number of pages for this chapter yet,
    # but we can do a quick check if there are files. If we want to be thorough,
    # we proceed anyway, but if it has e.g. 20+ files, it's highly likely completed.
    # To be safe, we always do the scan unless we have a flag, but let's allow resuming.
    
    print(f"\n==========================================")
    print(f"Starting Download for Chapter {ch_num}")
    print(f"Output directory: {os.path.abspath(ch_dir)}")
    print(f"==========================================")
    
    await load_albums_page(page)
    
    target_link = None
    target_href = None
    target_text = ""
    
    # Scroll and scan dynamically
    # 25 scrolls is plenty to reach Chapter 600
    for scroll_step in range(25):
        await inject_force_style(page)
        
        # Scan visible links
        links = await page.query_selector_all("a")
        for a in links:
            text = await a.inner_text()
            href = await a.get_attribute("href")
            if href and ("set=a." in href or "/photos/a." in href) and re.search(rf'\bHồi\s+{ch_num}\b', text):
                target_link = a
                target_href = href
                target_text = text.strip().replace("\n", " ")
                break
                
        if target_link:
            print(f"Found target album link: {target_text} -> {target_href}")
            break
            
        # Scroll scrollview down
        await page.evaluate("""() => {
            const sv = document.getElementById('scrollview');
            if (sv) {
                sv.scrollTo(0, sv.scrollHeight);
            }
        }""")
        await page.wait_for_timeout(2000)
        
    if not target_link:
        print(f"Error: Chapter {ch_num} album link not found in scrolling scan! Skipping.")
        return False
        
    # Extract album ID for filtering photos
    album_id = None
    if "set=a." in target_href:
        album_id = target_href.split("set=a.")[1].split("&")[0]
        
    # Click target link to route via SPA transition
    print("Clicking target link...")
    try:
        await target_link.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await target_link.click()
    except Exception as e:
        print(f"Click failed: {e}. Trying direct page.goto...")
        await page.goto(f"https://www.facebook.com{target_href}" if not target_href.startswith("http") else target_href)
        
    await page.wait_for_timeout(5000)
    await inject_force_style(page)
    
    # Scroll the album details grid view to load all photos
    for grid_scroll in range(6):
        await inject_force_style(page)
        await page.evaluate("""() => {
            const sv = document.getElementById('scrollview');
            if (sv) {
                sv.scrollTo(0, sv.scrollHeight);
            }
        }""")
        await page.wait_for_timeout(1500)
        
    # Extract photo links
    grid_links = await page.query_selector_all("a")
    photo_links = []
    for a in grid_links:
        href = await a.get_attribute("href")
        if href and ("/photo/" in href or "photo.php" in href) and (album_id is None or album_id in href):
            if href not in photo_links:
                photo_links.append(href)
                
    num_photos = len(photo_links)
    print(f"Found {num_photos} photo links in the grid.")
    if num_photos == 0:
        print("Error: No photos found in this album grid. Skipping.")
        return False
        
    # Download each photo
    success_count = 0
    for idx, href in enumerate(photo_links):
        page_num = idx + 1
        photo_url = href if href.startswith("http") else f"https://www.facebook.com{href}"
        
        # Check if already downloaded
        file_exists = False
        for ext in [".jpg", ".png", ".webp"]:
            save_path = os.path.join(ch_dir, f"Page_{page_num:03d}{ext}")
            if os.path.exists(save_path) and os.path.getsize(save_path) > 1024:
                file_exists = True
                break
                
        if file_exists:
            success_count += 1
            continue
            
        print(f"Chapter {ch_num} - Navigating to page {page_num}/{num_photos}...")
        await page.goto(photo_url)
        await page.wait_for_timeout(3000)
        
        # Extract active image src
        imgs = await page.query_selector_all("img")
        active_src = None
        for img in imgs:
            src = await img.get_attribute("src")
            if src and ("fbcdn.net" in src or "scontent" in src) and not await img.get_attribute("width"):
                active_src = src
                break
                
        if not active_src:
            # Retry
            await page.wait_for_timeout(3000)
            imgs = await page.query_selector_all("img")
            for img in imgs:
                src = await img.get_attribute("src")
                if src and ("fbcdn.net" in src or "scontent" in src) and not await img.get_attribute("width"):
                    active_src = src
                    break
                    
        if active_src:
            ext = ".jpg"
            if ".png" in active_src.lower():
                ext = ".png"
            elif ".webp" in active_src.lower():
                ext = ".webp"
            save_path = os.path.join(ch_dir, f"Page_{page_num:03d}{ext}")
            success = download_image(active_src, save_path)
            if success:
                success_count += 1
        else:
            print(f"Warning: Could not find image src for page {page_num}!")
            
        await page.wait_for_timeout(500)
        
    print(f"Chapter {ch_num} Download completed: {success_count}/{num_photos} pages downloaded successfully.")
    return True

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        
        # Download target chapters one by one
        for ch in TARGET_CHAPTERS:
            try:
                await download_chapter(page, ch)
            except Exception as e:
                print(f"Error downloading chapter {ch}: {e}")
                
        await browser.close()
        print("\nAll target Facebook downloads completed!")

if __name__ == "__main__":
    asyncio.run(main())
