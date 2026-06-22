# Manga PWA Reader — MangaDex Offline

PWA đọc manga offline, có thể deploy lên GitHub Pages.

## Cấu trúc

```
manga-pwa/
├── scripts/
│   ├── download.py          ← download từ MangaDex API
│   └── generate_manifest.py ← tạo manifest từ folder ảnh có sẵn
├── docs/                    ← thư mục serve bởi GitHub Pages
│   ├── index.html           ← PWA reader
│   ├── sw.js                ← Service Worker (offline cache)
│   ├── manifest.webmanifest ← PWA install manifest
│   ├── manifest.json        ← ← được tạo ra bởi script ↑
│   └── chapters/
│       ├── ch0040/
│       │   ├── meta.json
│       │   ├── page_001.jpg
│       │   ├── page_002.jpg
│       │   └── ...
│       └── ch0041/
│           └── ...
└── .github/workflows/deploy.yml
```

## Quick Start

### 1. Download chapter

```bash
cd scripts
pip install requests tqdm

# Download chapter 40 tiếng Việt
python download.py "https://mangadex.org/title/c4b36f15-4ee5-425f-a77d-c2e7cbb970d8" \
  --lang vi --start 40 --end 40

# Download nhiều chapter
python download.py "https://mangadex.org/title/c4b36f15-4ee5-425f-a77d-c2e7cbb970d8" \
  --lang vi --start 1 --end 50

# Download tất cả
python download.py "https://mangadex.org/title/c4b36f15-4ee5-425f-a77d-c2e7cbb970d8" \
  --lang vi
```

### 2. Test local

```bash
cd docs
python -m http.server 8080
# Mở: http://localhost:8080
```

### 3. Deploy GitHub Pages

```bash
git init
git remote add origin git@github.com:<user>/<repo>.git
git add .
git commit -m "init manga pwa"
git push -u origin main

# Sau đó vào GitHub repo → Settings → Pages → Source: GitHub Actions
```

URL sau khi deploy: `https://<user>.github.io/<repo>/`

### 4. Nếu đã có ảnh sẵn (không dùng download.py)

```bash
# Copy ảnh vào docs/chapters/ch0040/page_001.jpg ...
# Rồi chạy:
cd scripts
python generate_manifest.py --title "Nippon Sangoku"
```

## Tips

- **Private repo**: GitHub Pages vẫn public nếu dùng free plan → dùng private repo + GitHub Pages (cần GitHub Pro) hoặc self-host
- **Ảnh nhiều**: Git LFS hoặc dùng external image host (Cloudflare R2, etc.)
- **Cập nhật chapter mới**: chạy lại download.py với `--start <new_ch>`, manifest tự update
- **Offline hoàn toàn**: sau lần đầu load trên mobile, Service Worker cache lại tất cả

## Reader Features

- ✅ Chế độ từng trang + cuộn dài (webtoon)
- ✅ LTR / RTL (manga Nhật)
- ✅ Swipe trên mobile
- ✅ Keyboard (←→ hoặc A/D)
- ✅ Tap zones (tap trái/phải để lật trang, giữa để ẩn UI)
- ✅ Progress bar có thể click để nhảy trang
- ✅ Lưu vị trí đọc (localStorage)
- ✅ Đánh dấu chapter đã đọc
- ✅ Install as PWA (Add to Home Screen)
- ✅ Offline cache qua Service Worker
