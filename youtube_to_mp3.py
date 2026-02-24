# File: yt_mp3_nhanh.py
# Cài: pip install yt-dlp
# (Tùy chọn: cài aria2c để tải nhanh gấp nhiều lần)

import yt_dlp
import sys
import os
import time

def download_audio_nhanh(url, output_folder=".", quality="128"):  # 128 hoặc 192 hoặc 0 (best)
    start_time = time.time()  # Bắt đầu đo thời gian

    try:
        ydl_opts = {
            'format': 'bestaudio/best',           # audio-only ngay từ đầu
            'extractaudio': True,
            'audioformat': 'mp3',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
            'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': True,
            'noplaylist': True,
            
            # Tăng tốc download (nếu bạn đã cài aria2c thì bỏ comment 2 dòng dưới)
            # 'external_downloader': 'aria2c',
            # 'external_downloader_args': ['-x', '16', '-k', '1M'],  # 16 kết nối, mỗi chunk 1MB
        }

        print(f"Đang tải audio nhanh từ: {url}")
        print(f"Chất lượng: {quality}kbps | Thư mục lưu: {os.path.abspath(output_folder)}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        end_time = time.time()
        elapsed = end_time - start_time
        elapsed_str = f"{elapsed:.2f} giây" if elapsed < 60 else f"{elapsed//60:.0f} phút {elapsed%60:.0f} giây"

        print("\n" + "="*50)
        print(f"XONG! File MP3 đã tải về thành công.")
        print(f"Thời gian tải: {elapsed_str}")
        print("="*50)

    except Exception as e:
        print("Lỗi xảy ra:")
        print(e)
        if 'start_time' in locals():
            elapsed = time.time() - start_time
            print(f"Thời gian đã trôi qua trước khi lỗi: {elapsed:.2f} giây")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng:")
        print("  python yt_mp3_nhanh.py https://youtu.be/abc123")
        print("  python yt_mp3_nhanh.py https://youtu.be/abc123 128   # chất lượng 128kbps, siêu nhanh")
        print("  python yt_mp3_nhanh.py https://youtu.be/abc123 0     # chất lượng cao nhất")
        sys.exit(1)

    video_url = sys.argv[1]
    
    # Ưu tiên: nếu truyền tham số thứ 2 → dùng nó, còn không mặc định 128kbps
    quality = "128"
    if len(sys.argv) > 2:
        quality = sys.argv[2]
        if quality not in ["0", "128", "160", "192", "256", "320"]:
            print("Chất lượng không hợp lệ, dùng mặc định 128kbps")
            quality = "128"

    # Nếu muốn thay đổi thư mục lưu mặc định, sửa ở đây
    download_audio_nhanh(video_url, ".", quality)