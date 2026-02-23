# Hướng Dẫn Phát Hiện Key Từ YouTube

## Chuẩn Bị

### 1. Cài Đặt Python Dependencies

```bash
cd electron-key-detector
pip install -r requirements.txt
```

### 2. Cài Đặt ffmpeg

ffmpeg cần thiết để tải audio từ YouTube.

**Cách 1: Tải trực tiếp**
- Tải từ: https://ffmpeg.org/download.html
- Giải nén và thêm vào PATH

**Cách 2: Dùng Chocolatey**
```bash
choco install ffmpeg
```

### 3. Kiểm Tra Cài Đặt

Chạy script kiểm tra:
```bash
python check_setup.py
```

Nếu tất cả đều ✓ thì bạn đã sẵn sàng!

## Cách Sử Dụng

### Phương Án 1: Tự Động (Khuyến Nghị)

Chạy file batch để khởi động cả server và app:
```bash
start_all.bat
```

### Phương Án 2: Thủ Công

**Bước 1: Khởi động YouTube Server**

Mở terminal thứ nhất:
```bash
cd electron-key-detector
python youtube_server.py
```

Bạn sẽ thấy:
```
Starting YouTube Key Detection Server on http://localhost:5001
 * Running on http://127.0.0.1:5001
```

**GIỮ TERMINAL NÀY MỞ!**

**Bước 2: Khởi động Electron App**

Mở terminal thứ hai:
```bash
cd electron-key-detector
npm start
```

## Test Phát Hiện Key

1. **Mở DevTools**: Nhấn `Ctrl+Shift+I` hoặc `F12`
2. **Vào một video YouTube** trong trình duyệt nhúng
3. **Nhấn nút "Detect Key"** (biểu tượng ▶ trên thanh điều hướng)
4. **Xem Console** để theo dõi quá trình

### Logs Mong Đợi

Khi nhấn "Detect Key", bạn sẽ thấy trong Console:

```
🔘 Detect YouTube button clicked!
🎵 detectKeyFromYouTube() called!
=== YouTube Key Detection Started ===
Step 1: Getting webview reference...
Webview element: [object HTMLWebViewElement]
Step 2: Getting URL from webview...
Current URL: https://www.youtube.com/watch?v=...
Step 3: Checking YouTube server...
YouTube server ready: true
Step 4: Updating UI to loading state...
Step 5: Sending request to download and detect...
Step 6: Result received: {...}
Step 7: YouTube detection successful!
Key: G
Scale: Major
Confidence: 85
=== YouTube Key Detection Complete ===
```

### Kết Quả Thành Công

✅ Nút đổi thành "Processing..." khi nhấn
✅ Hiển thị "..." và "Downloading..."
✅ Popup hiện key đã phát hiện với tên bài và độ tin cậy
✅ Key xuất hiện trong lịch sử phát hiện

## Xử Lý Lỗi

### Lỗi: "YouTube server not running on port 5001"

**Nguyên nhân:** Server chưa chạy

**Giải pháp:**
```bash
python youtube_server.py
```

Kiểm tra server:
```bash
curl http://127.0.0.1:5001/health
```

Phải trả về: `{"status":"ok"}`

### Lỗi: "Not a YouTube video URL"

**Nguyên nhân:** Chưa vào trang video

**Giải pháp:** Điều hướng đến một video YouTube (URL có `/watch?v=`)

### Lỗi: "ffmpeg not found"

**Nguyên nhân:** ffmpeg chưa cài hoặc chưa có trong PATH

**Giải pháp:**
1. Cài ffmpeg: https://ffmpeg.org/download.html
2. Thêm ffmpeg vào PATH
3. Khởi động lại Python server

### Lỗi: "YouTube webview not found"

**Nguyên nhân:** Element webview không tìm thấy

**Giải pháp:** Kiểm tra file `index.html` có:
```html
<webview id="youtubeWebview" ...></webview>
```

### Nút Không Hoạt Động

**Kiểm tra Console:**
- `✅ Detect YouTube button found` - Nút đã tìm thấy
- `🔘 Detect YouTube button clicked!` - Sự kiện click đã kích hoạt
- `🎵 detectKeyFromYouTube() called!` - Hàm đã được gọi

Nếu không thấy các log này, có thể nút chưa được kết nối đúng.

## Logs Python Server

Trong terminal chạy Python server, bạn sẽ thấy:
```
Downloading: https://www.youtube.com/watch?v=...
Downloaded: [Tên Bài Hát]
Detected: G Major (85%)
```

## Các Lỗi Thường Gặp

| Lỗi | Nguyên Nhân | Giải Pháp |
|-----|-------------|-----------|
| `ECONNREFUSED 127.0.0.1:5001` | Server chưa chạy | Chạy `python youtube_server.py` |
| `Not a YouTube video URL` | Chưa vào trang video | Vào một video YouTube |
| `ffmpeg not found` | ffmpeg chưa cài | Cài ffmpeg và thêm vào PATH |
| `yt-dlp error` | Video không khả dụng | Thử video khác |
| `Timeout` | Tải quá chậm | Kiểm tra kết nối internet |

## Video Test Đề Xuất

Thử với các video này:
- Video nhạc ngắn (3-5 phút)
- Bài hát phổ biến với giai điệu rõ ràng
- Tránh video quá dài (>10 phút) để test nhanh

## Ghi Chú Kỹ Thuật

- Server chỉ phân tích **30 giây đầu** của audio để tăng tốc độ
- Sử dụng thuật toán **Krumhansl-Schmuckler** để phát hiện key
- Chroma được trích xuất bằng **librosa's chroma_cqt**
- Kết quả trả về: Key, Scale (Major/Minor), Confidence (0-100%)

## Hỗ Trợ

Nếu gặp vấn đề:
1. Chạy `python check_setup.py` để kiểm tra cài đặt
2. Xem logs trong Console (F12)
3. Xem logs trong terminal Python server
4. Đọc file `YOUTUBE_DETECTION_TEST.md` (tiếng Anh) để biết thêm chi tiết
