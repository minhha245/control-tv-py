# 🚀 Bắt Đầu Nhanh - YouTube Key Detection

## Bước 1: Cài ffmpeg (Chỉ Cần 1 Lần)

ffmpeg là dependency duy nhất còn thiếu.

### Cách Nhanh Nhất:
```bash
choco install ffmpeg
```

### Hoặc Tải Thủ Công:
1. Tải: https://ffmpeg.org/download.html
2. Giải nén vào `C:\ffmpeg`
3. Thêm `C:\ffmpeg\bin` vào PATH
4. Khởi động lại terminal

### Kiểm Tra:
```bash
ffmpeg -version
```

## Bước 2: Khởi Động

### Cách 1: Tự Động (Khuyến Nghị)
```bash
start_all.bat
```

### Cách 2: Thủ Công

**Terminal 1:**
```bash
cd electron-key-detector
python youtube_server.py
```

**Terminal 2:**
```bash
cd electron-key-detector
npm start
```

## Bước 3: Test

1. Nhấn `F12` để mở DevTools
2. Vào một video YouTube
3. Nhấn nút "Detect Key"
4. Xem Console logs

## ✅ Logs Thành Công

```
🔘 Detect YouTube button clicked!
🎵 detectKeyFromYouTube() called!
YouTube server ready: true
Step 7: YouTube detection successful!
Key: G
Scale: Major
```

## ❌ Lỗi Thường Gặp

### "YouTube server not running"
→ Chạy: `python youtube_server.py`

### "Not a YouTube video URL"
→ Vào trang video YouTube (URL có `/watch?v=`)

### "ffmpeg not found"
→ Cài ffmpeg (xem Bước 1)

## 🔍 Kiểm Tra Setup

```bash
python check_setup.py
```

Phải thấy tất cả ✓ (trừ ffmpeg nếu chưa cài)

## 📚 Tài Liệu Chi Tiết

- `HUONG_DAN_YOUTUBE.md` - Hướng dẫn đầy đủ (Tiếng Việt)
- `YOUTUBE_DETECTION_TEST.md` - Testing guide (English)
- `STATUS.md` - Current status and debugging

## 💡 Ghi Chú

- Server phân tích **30 giây đầu** của video
- Thời gian: 5-15 giây tùy internet
- Thuật toán: Krumhansl-Schmuckler
- Độ chính xác: Cao với nhạc có giai điệu rõ

## 🎯 Kết Quả Mong Đợi

1. Nhấn "Detect Key"
2. Nút hiện "Processing..."
3. Sau 5-15 giây
4. Popup hiện key đã phát hiện
5. Key xuất hiện trong display và history

Xong! 🎉
