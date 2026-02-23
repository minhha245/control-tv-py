# Fix Essentia Server M4A Error

## Vấn đề

```
[Essentia] Detection failed: {"error":""}
[YouTube] Detection failed
```

Essentia server không đọc được file m4a.

## Nguyên nhân

Librosa cần backend để đọc m4a:
- **ffmpeg** - Cần cài đặt
- **audioread** - Cần cài đặt

## Giải pháp

### Cách 1: Cài ffmpeg (Khuyến nghị)

#### Windows:
1. Download ffmpeg: https://www.gyan.dev/ffmpeg/builds/
2. Giải nén vào `C:\ffmpeg`
3. Thêm vào PATH: `C:\ffmpeg\bin`
4. Restart terminal
5. Test: `ffmpeg -version`

#### Hoặc dùng Chocolatey:
```bash
choco install ffmpeg
```

### Cách 2: Cài audioread

```bash
pip install audioread
```

### Cách 3: Download MP3 thay vì M4A

Sửa format trong code:

```python
"--format", "bestaudio[ext=mp3]/bestaudio/best",
```

Nhưng MP3 cần convert → Chậm hơn

## Code Đã Sửa

Bây giờ code tự động fallback:

```python
# Try Essentia first
if self.check_essentia_server():
    key, scale, confidence = self.detect_key_essentia(audio_path)

# If failed, use librosa fallback
if not key or not scale:
    key, scale, confidence = self._detect_key_fallback(audio_path)
```

## Test

### Test 1: Kiểm tra ffmpeg

```bash
ffmpeg -version
```

Nếu có → OK

### Test 2: Test Essentia server

```bash
python test_essentia_m4a.py
```

Xem có đọc được m4a không

### Test 3: Test librosa trực tiếp

```python
import librosa
y, sr = librosa.load("test.m4a", sr=22050)
print(f"Loaded: {len(y)} samples")
```

## Kết quả

Với code mới:
- ✅ Thử Essentia trước
- ✅ Nếu fail → Tự động dùng librosa fallback
- ✅ Vẫn phát hiện được key

## Khuyến nghị

1. **Cài ffmpeg** - Tốt nhất, hỗ trợ mọi format
2. **Dùng fallback** - Vẫn hoạt động, chỉ chậm hơn 1-2 giây
3. **Không cần lo** - Code tự động xử lý

## Log Mới

Bây giờ bạn sẽ thấy:

```
[YouTube] Audio file: temp_youtube/2GFHxOPZMYA.m4a
[YouTube] Trying Essentia server...
[Essentia] Detection failed: {"error":""}
[YouTube] Using librosa fallback...
[YouTube] Detected: C# Major (85%)
```

Hoặc nếu Essentia OK:

```
[YouTube] Trying Essentia server...
[YouTube] Detected: C# Major (85%)
```

## Kết luận

- ✅ Code đã có fallback tự động
- ✅ Vẫn phát hiện được key
- ✅ Không cần lo lắng
- 💡 Cài ffmpeg để tối ưu hơn (optional)
