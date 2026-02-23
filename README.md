# Cubase Tool - BẢNG ĐIỀU KHIỂN TIẾNG VIỆT

Công cụ điều khiển Cubase với giao diện tiếng Việt, tích hợp Auto-Key Detection và YouTube Key Detector.

## Tính năng

### 1. Điều khiển MIDI
- Điều khiển âm lượng nhạc/mic
- Điều khiển reverb, delay, tune
- Gửi MIDI CC qua loopMIDI
- Lưu/load cấu hình

### 2. Auto-Key Detection
- Phát hiện key/scale từ audio loopback
- Hiển thị realtime trên panel
- Tự động gửi MIDI đến Auto-Tune
- Hỗ trợ nhiều nguồn audio

### 3. YouTube Key Detector
- Tự động phát hiện key từ YouTube
- Mở Chrome tự động
- Monitor URL changes
- Download và phân tích tự động
- Hiển thị kết quả trên panel

### 4. Tự động đóng Cubase
- Gửi Ctrl+Q khi đóng tool
- Tự động click "Don't Save"
- Đóng Cubase sạch sẽ

## Cài đặt

### Yêu cầu
- Python 3.11+
- Windows 10/11
- Google Chrome hoặc Brave Browser
- loopMIDI (cho MIDI routing)

### Cài đặt dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# YouTube integration
pip install -r requirements_youtube.txt

# Audio format support
pip install soundfile audioread
```

### Cài đặt ffmpeg (Tùy chọn, khuyến nghị)

```bash
choco install ffmpeg
```

Hoặc download từ: https://www.gyan.dev/ffmpeg/builds/

## Sử dụng

### Khởi động

```bash
python controller_gui.py
```

### Kích hoạt bản quyền

Key: `HAU_SETUP_STUDIO_2025`

### YouTube Auto Detector

1. Click nút **YOUTUBE** (màu đỏ)
2. Chrome tự động mở vào youtube.com
3. Click vào video bất kỳ
4. Chờ tự động phát hiện và phân tích
5. Kết quả hiển thị trên panel AUTO-KEY

### Auto-Key Detection

1. Click nút **AUTO-KEY**
2. Chọn nguồn audio (loopback device)
3. Phát nhạc
4. Key/scale hiển thị realtime
5. Tự động gửi MIDI đến Auto-Tune

## Cấu trúc thư mục

```
cusbase_tool_py/
├── controller_gui.py           # Main application
├── autokey_tool/              # Auto-Key detection
│   ├── audio_engine.py
│   └── key_detector_improved.py
├── essentia-key-detector/     # Essentia server
│   ├── audio_server.py
│   └── start_server.bat
├── requirements.txt           # Core dependencies
├── requirements_youtube.txt   # YouTube dependencies
└── docs/                      # Documentation
    ├── HUONG_DAN_YOUTUBE_INTEGRATION.md
    ├── FIX_AUDIO_FORMAT.md
    └── YOUTUBE_SIMPLE_METHOD.md
```

## Troubleshooting

### YouTube không tải được

**Giải pháp:**
```bash
pip install soundfile audioread
```

### Essentia server lỗi

**Giải pháp:**
- Cài ffmpeg
- Hoặc dùng librosa fallback (tự động)

### Chrome không mở

**Giải pháp:**
- Cài Google Chrome
- Hoặc Brave Browser

### MIDI không hoạt động

**Giải pháp:**
- Cài loopMIDI
- Tạo port tên "loopMIDI"
- Restart tool

## Tài liệu

- [Hướng dẫn YouTube Integration](HUONG_DAN_YOUTUBE_INTEGRATION.md)
- [Fix Audio Format](FIX_AUDIO_FORMAT.md)
- [YouTube Simple Method](YOUTUBE_SIMPLE_METHOD.md)
- [Debug YouTube](DEBUG_YOUTUBE.md)
- [Cleanup Summary](CLEANUP_SUMMARY.md)

## Changelog

### v2.0.0 (2025-02-23)
- ✅ Tích hợp YouTube Auto Detector
- ✅ Tự động monitor URL changes
- ✅ Download và phân tích tự động
- ✅ Cleanup code (xóa 1244 dòng duplicate)
- ✅ Tối ưu download (dùng format gốc)
- ✅ Auto fallback (Essentia → librosa)

### v1.0.0
- ✅ Điều khiển MIDI cơ bản
- ✅ Auto-Key Detection
- ✅ Tự động đóng Cubase
- ✅ Lưu/load cấu hình

## License

Hậu Setup Live Studio © 2025

## Tác giả

Hậu Setup Live Studio

## Hỗ trợ

Nếu gặp vấn đề, xem:
1. [Troubleshooting](#troubleshooting)
2. [Tài liệu](#tài-liệu)
3. Console log để debug
