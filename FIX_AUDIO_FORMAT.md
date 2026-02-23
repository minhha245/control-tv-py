# Fix Audio Format Support

## Vấn đề

```
PySoundFile failed. Trying audioread instead.
[Fallback] Error:
[YouTube] Detection failed
```

Librosa không đọc được file audio vì thiếu backend.

## Nguyên nhân

Librosa cần backend để đọc audio:
- **soundfile** - Đọc WAV, FLAC, OGG
- **audioread** - Đọc MP3, M4A, AAC (cần ffmpeg)
- **ffmpeg** - Convert mọi format

## Giải pháp Nhanh (Khuyến nghị)

### Bước 1: Cài soundfile và audioread

```bash
pip install soundfile audioread
```

Hoặc chạy file:
```bash
install_audio_support.bat
```

### Bước 2: Thử lại

Bây giờ librosa sẽ đọc được webm/opus (format mặc định của YouTube)

## Giải pháp Đầy Đủ (Tốt nhất)

### Cài ffmpeg

#### Windows - Cách 1: Chocolatey
```bash
choco install ffmpeg
```

#### Windows - Cách 2: Thủ công
1. Download: https://www.gyan.dev/ffmpeg/builds/
2. Giải nén vào `C:\ffmpeg`
3. Thêm vào PATH: `C:\ffmpeg\bin`
4. Restart terminal
5. Test: `ffmpeg -version`

## Code Đã Sửa

Bây giờ download format mặc định (webm/opus):

```python
"--format", "bestaudio",  # Không chỉ định ext, lấy format gốc
```

Thay vì:
```python
"--format", "bestaudio[ext=m4a]",  # Bắt buộc m4a (cần convert)
```

## Ưu điểm

✅ **Không cần convert** - Tải format gốc (webm/opus)
✅ **Nhanh hơn** - Không mất thời gian convert
✅ **Ít lỗi hơn** - Không phụ thuộc ffmpeg

## Test

### Test 1: Kiểm tra soundfile

```python
import soundfile
print(soundfile.__version__)
```

### Test 2: Kiểm tra audioread

```python
import audioread
print(audioread.__version__)
```

### Test 3: Test đọc file

```python
import librosa
y, sr = librosa.load("test.webm", sr=22050)
print(f"Loaded: {len(y)} samples")
```

## Format Hỗ Trợ

Sau khi cài:

| Format | soundfile | audioread | ffmpeg |
|--------|-----------|-----------|--------|
| WAV    | ✅        | ✅        | ✅     |
| FLAC   | ✅        | ✅        | ✅     |
| OGG    | ✅        | ✅        | ✅     |
| OPUS   | ✅        | ✅        | ✅     |
| WEBM   | ✅        | ✅        | ✅     |
| MP3    | ❌        | ✅*       | ✅     |
| M4A    | ❌        | ✅*       | ✅     |
| AAC    | ❌        | ✅*       | ✅     |

*Cần ffmpeg

## Khuyến nghị

1. **Cài soundfile + audioread** (Bắt buộc)
   ```bash
   pip install soundfile audioread
   ```

2. **Cài ffmpeg** (Tùy chọn, nhưng nên cài)
   ```bash
   choco install ffmpeg
   ```

## Kết quả

Sau khi cài:

```
[YouTube] Download completed
[YouTube] Audio file: temp_youtube/xxx.webm
[YouTube] Trying Essentia server...
[YouTube] Using librosa fallback...
[YouTube] Detected: C# Major (85%)  ✅
```

## Tóm tắt

- ✅ Cài `soundfile` và `audioread`
- ✅ Download format gốc (webm/opus)
- ✅ Không cần convert
- 💡 Cài ffmpeg để hỗ trợ đầy đủ (optional)

Chạy ngay:
```bash
pip install soundfile audioread
```
