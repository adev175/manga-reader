import os
import sys
import re
import requests
import asyncio
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8')

OUT_DIR_BASE = os.path.join("downloads", "Hỏa Phụng Liêu Nguyên")

def download_image(url, save_path, referer):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": referer
    }
    try:
        r = requests.get(url, headers=headers, timeout=30, verify=False)
        r.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"Failed to download image {url}: {e}")
        return False

async def download_chapter(page, ch_num):
    ch_dir = os.path.join(OUT_DIR_BASE, f"Ch_{ch_num}")
    os.makedirs(ch_dir, exist_ok=True)
    
    # Check if already downloaded
    if os.path.exists(ch_dir):
        existing_files = [f for f in os.listdir(ch_dir) if f.startswith("Page_") and os.path.getsize(os.path.join(ch_dir, f)) > 1024]
        if len(existing_files) >= 15:
            print(f"Chapter {ch_num} already downloaded ({len(existing_files)} pages). Skipping.")
            return True
            
    url = f"https://truyenqq.ca/truyen-tranh/hoa-phung-lieu-nguyen/chuong-{ch_num}"
    print(f"\n==========================================")
    print(f"Starting Download for Chapter {ch_num}")
    print(f"URL: {url}")
    print(f"==========================================")
    
    try:
        await page.goto(url, timeout=45000)
        await page.wait_for_timeout(6000)
        
        # Get all img tags
        imgs = await page.query_selector_all("img")
        chapter_imgs = []
        for img in imgs:
            src = await img.get_attribute("src")
            data_src = await img.get_attribute("data-original") or await img.get_attribute("data-src")
            
            # Prefer lazy loading data-src
            active_src = data_src if data_src else src
            if active_src and ("cdn" in active_src or "chapter" in active_src or "upload" in active_src or "nettruyen" in active_src or "qq" in active_src):
                if active_src not in chapter_imgs:
                    chapter_imgs.append(active_src)
                    
        num_pages = len(chapter_imgs)
        print(f"Found {num_pages} pages in Chapter {ch_num}")
        
        if num_pages == 0:
            print(f"Error: 0 pages found for Chapter {ch_num}!")
            return False
            
        success_count = 0
        for idx, img_url in enumerate(chapter_imgs):
            page_num = idx + 1
            
            # Resolve relative URLs
            if img_url.startswith("//"):
                full_img_url = f"https:{img_url}"
            elif img_url.startswith("/"):
                full_img_url = f"https://truyenqq.ca{img_url}"
            else:
                full_img_url = img_url
                
            # Determine extension
            ext = ".jpg"
            if ".png" in full_img_url.lower():
                ext = ".png"
            elif ".webp" in full_img_url.lower():
                ext = ".webp"
                
            save_path = os.path.join(ch_dir, f"Page_{page_num:03d}{ext}")
            
            # Download with referer
            success = download_image(full_img_url, save_path, url)
            if success:
                success_count += 1
            else:
                # Try one retry
                await asyncio.sleep(1)
                success = download_image(full_img_url, save_path, url)
                if success:
                    success_count += 1
                    
        print(f"Chapter {ch_num} completed: {success_count}/{num_pages} pages downloaded successfully.")
        return success_count == num_pages
        
    except Exception as e:
        print(f"Failed downloading Chapter {ch_num}: {e}")
        return False

async def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Range of chapters to download
    chapters = [str(x) for x in range(600, 623)]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True
        )
        page = await context.new_page()
        
        failed_chapters = []
        for ch in chapters:
            success = await download_chapter(page, ch)
            if not success:
                failed_chapters.append(ch)
            # Short sleep between chapters to avoid overloading the server
            await asyncio.sleep(2)
            
        print("\n==========================================")
        print("ALL CHAPTER DOWNLOAD PROCESS COMPLETED!")
        if failed_chapters:
            print(f"Failed chapters: {failed_chapters}")
        else:
            print("All chapters from 600 to 622 downloaded successfully!")
        print("==========================================")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
