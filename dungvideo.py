#!/usr/bin/env python3
"""DựngVideo — tool dựng video dọc 9:16 theo nhịp nhạc (Python + FFmpeg).

Cách dùng nhanh:
  python dungvideo.py demo                    # tạo media mẫu và dựng thử
  python dungvideo.py "D:\\video\\bai_hom_nay"  # tự dựng từ thư mục ảnh/clip + nhạc + chu.txt
  python dungvideo.py render du_an.yaml       # xuất lại sau khi sửa file dự án
  python dungvideo.py hieu-ung                # xem danh sách cảnh & hiệu ứng
"""
from dungvideo_core.cli import main

if __name__ == "__main__":
    main()
