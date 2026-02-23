---
description: Cách đóng gói và tích hợp VieNeu-TTS vào App Tikfini-Mod
---

Để người dùng không cần tự mở server thủ công, chúng ta sử dụng PyInstaller để đóng gói code Python thành file `.exe` duy nhất.

### Bước 1: Chuẩn bị môi trường Python
Trong thư mục chứa mã nguồn VieNeu-TTS (không phải thư mục Electron này), hãy cài đặt thư viện cần thiết:
```bash
pip install pyinstaller flask flask-cors
# Và các thư viện TTS của mô hình (onnxruntime, v.v.)
```

### Bước 2: Tạo hoặc sử dụng file server.py
Đảm bảo file `server.py` của bạn lắng nghe ở cổng `23333` (cổng mặc định của app).

### Bước 3: Câu lệnh đóng gói (PyInstaller)
Mở terminal tại thư mục mã nguồn Python và chạy:
// turbo
```bash
pyinstaller --noconfirm --onefile --windowed --name tts_server --clean  --add-data "path_to_model_folder;models"  server.py
```
*Lưu ý: Thay `path_to_model_folder` bằng đường dẫn thực tế chứa mô hình của bạn.*

### Bước 4: Chép file vào App
1. Sau khi chạy lệnh trên, file `tts_server.exe` sẽ xuất hiện trong thư mục `dist`.
2. Tạo thư mục `bin` trong project Electron này: `mkdir d:\project\tikfini-mod\bin`
3. Chép file `tts_server.exe` vào thư mục `d:\project\tikfini-mod\bin`.

### Bước 5: Kiểm tra
Khởi động ứng dụng Electron. Ứng dụng sẽ tự động tìm thấy file `bin/tts_server.exe` và chạy nó ở chế độ ẩn (background).

# turbo-all
