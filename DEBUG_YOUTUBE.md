# Debug YouTube Download

## Vấn đề hiện tại

```
[YouTube Monitor] Started
[YouTube Monitor] New video detected: https://www.youtube.com/watch?v=VAqbvUA-nus
[YouTube] Extracting audio URL: https://www.youtube.com/watch?v=VAqbvUA-nus
... (treo ở đây, không thấy tải)
```

## Nguyên nhân

`yt-dlp` đang "extracting" (lấy thông tin video) nhưng mất nhiều thời gian vì:
1. Phải giải mã nhiều thông tin từ YouTube
2. Phải xử lý playlist/radio (URL có `&list=RD...`)
3. Phải kiểm tra nhiều format

## Giải pháp đã áp dụng

### 1. Tối ưu yt-dlp options
```python
ydl_opts = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best',
    'skip_download': True,           # Không download, chỉ lấy info
    'no_check_certificate': True,    # Bỏ qua check SSL (nhanh hơn)
    'prefer_insecure': True,         # Dùng HTTP thay HTTPS (nhanh hơn)
    'youtube_include_dash_manifest': False,  # Bỏ qua DASH manifest
    'socket_timeout': 10,            # Timeout 10s
}
```

### 2. Xử lý nhiều trường hợp audio URL
```python
if 'url' in info:
    audio_url = info['url']  # Trường hợp đơn giản
elif 'formats' in info:
    # Tìm audio format tốt nhất
    audio_formats = [f for f in info['formats'] 
                     if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
    audio_url = audio_formats[0]['url']
```

### 3. Thêm logging chi tiết
```python
print("[YouTube] Getting video info...")
print(f"[YouTube] Title: {title}")
print(f"[YouTube] Format: {ext}")
print(f"[YouTube] Audio URL: {audio_url[:100]}...")
```

## Cách kiểm tra

### 1. Xem console log
Khi click video, bạn sẽ thấy:
```
[YouTube Monitor] New video detected: https://...
[YouTube] Extracting audio URL: https://...
[YouTube] Getting video info...
[YouTube] Title: Tên video
[YouTube] Format: m4a
[YouTube] Audio URL: https://rr3---sn-...
```

### 2. Nếu vẫn treo
Có thể do:
- Mạng chậm
- YouTube block
- Video có vấn đề

### 3. Timeout
Nếu quá 10s không có phản hồi → Tự động báo lỗi

## Test thủ công

Để test xem yt-dlp có hoạt động không:

```python
import yt_dlp

url = "https://www.youtube.com/watch?v=VAqbvUA-nus"

ydl_opts = {
    'format': 'bestaudio',
    'quiet': False,  # Hiển thị log
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    print(f"Title: {info['title']}")
    print(f"URL: {info['url'][:100]}")
```

Chạy script này để xem có lỗi gì không.

## Các trường hợp lỗi

### 1. "Extracting" mãi không xong
**Nguyên nhân:** Mạng chậm hoặc YouTube throttle

**Giải pháp:**
- Đợi thêm vài giây
- Thử video khác
- Restart tool

### 2. "Không tìm thấy audio URL"
**Nguyên nhân:** Video không có audio hoặc bị block

**Giải pháp:**
- Thử video khác
- Kiểm tra video có mở được trên YouTube không

### 3. "Extract error: ..."
**Nguyên nhân:** Lỗi từ yt-dlp

**Giải pháp:**
- Update yt-dlp: `pip install -U yt-dlp`
- Xem log chi tiết

## Tối ưu thêm

Nếu vẫn chậm, có thể:

### 1. Cache video info
```python
# Lưu info đã extract để không phải extract lại
cache = {}
if url in cache:
    info = cache[url]
else:
    info = ydl.extract_info(url, download=False)
    cache[url] = info
```

### 2. Dùng format đơn giản hơn
```python
'format': 'worstaudio'  # Chất lượng thấp nhưng nhanh
```

### 3. Skip playlist
```python
'noplaylist': True,  # Bỏ qua playlist
```

## Monitoring

Để biết đang làm gì:

```python
def progress_hook(d):
    if d['status'] == 'downloading':
        print(f"Downloading: {d['_percent_str']}")
    elif d['status'] == 'finished':
        print("Download finished")

ydl_opts['progress_hooks'] = [progress_hook]
```

## Kết luận

Với các tối ưu đã áp dụng:
- ✅ Extract nhanh hơn (skip nhiều bước không cần)
- ✅ Timeout 10s (không treo mãi)
- ✅ Xử lý nhiều trường hợp audio URL
- ✅ Log chi tiết để debug

Nếu vẫn chậm → Có thể do mạng hoặc YouTube throttle.
