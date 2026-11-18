# DựngVideo: bối cảnh dự án

Tool Python + FFmpeg dựng video dọc 9:16 theo nhịp nhạc, cho kênh @hieusichungkhoan (tin chứng khoán).
Phong cách học từ kênh CapCut của Hussain Rasooli (@rasooliarts): chia màn hình bằng mask, cắt theo beat,
chữ động từng từ, lưới ảnh zoom-out, lộ cảnh qua hình nở, flash slideshow, khung thương hiệu, màu cam–xanh.
Chủ dự án không phải dev: giao diện, thông báo và hướng dẫn đều bằng tiếng Việt, ưu tiên bấm đúp / kéo thả.

Kiến thức dựng video (giải phẫu timeline, quy trình 32 bước, lý thuyết beat sync, đặc tả layer engine) nằm trong
file dưới đây. ĐỌC KỸ trước khi sửa phần dựng hình:
@KIEN_THUC_CAPCUT.md

## Kiến trúc (dungvideo_core/)
- `cli.py`: lệnh `auto | render | chup | demo | hieu-ung`. Kéo thả thư mục sẽ chạy `auto`, kéo thả .yaml sẽ chạy `render`.
- `templates.py`: chế độ auto. Quét thư mục (ảnh/clip/nhạc/giong*.mp3/.srt/logo.png/chu.txt), lên kịch bản
  cảnh theo mẫu `tin-nhanh | dien-anh | slideshow` và ghi ra file dự án YAML. Quy tắc: cắt theo beat; trước
  drop cảnh dài và không nhún; sau drop nhịp 2-2-1-1-2; BPM trên 158 thì nhân đôi số nhịp; cảnh có chữ giữ ≥4 nhịp.
  `chu.txt`: dòng 1 = tiêu đề; `04: HPG +6,9% | chú thích` gắn vào file số 04; các dòng khác gán lần lượt.
- `render.py`: lớp Timeline (cảnh, chuyển cảnh căn giữa điểm cắt, vignette, khung thương hiệu, phụ đề, thanh tiến
  độ). Khung RGB được pipe vào stdin của ffmpeg (libx264 veryfast crf20). Âm thanh: nhạc + giọng đọc, có amix/apad.
- `scenes.py`: các cảnh `tieu_de, day_du, chia(doc|ngang|cheo|tron|thoi|vien|the), luoi, hinh_mo, flash,
  so_sanh, ket`. Lớp Panel = media cover-fit + mask SDF + hiệu ứng vào (slide/pop/reveal/fade).
- `transitions.py`: cat, mo, flash, zoom, truot, truot_ngang, vblur, glitch.
- `beats.py`: dò beat bằng numpy (spectral flux, có trọng số dải trầm; tempo bằng autocorr + nội suy parabol;
  lưới pha + tinh chỉnh ±10%; bù +30ms) và dò điểm drop. Sai số trên nhạc test khoảng 7ms.
- `masks.py` (SDF khử răng cưa), `media.py` (ảnh + đọc video bằng ffmpeg pipe), `comp.py` (ghép lớp),
  `textfx.py` (font tiếng Việt Montserrat/Anton trong fonts/), `grade.py` (LUT màu), `demo.py` (media mẫu).
- `cau_hinh.yaml`: cấu hình mặc định (mẫu, màu, khung thương hiệu, handle). `HUONG_DAN.md`: hướng dẫn người dùng.

## Trạng thái
- Đã chạy thử toàn bộ loại cảnh, chuyển cảnh và 3 mẫu trên Linux. 29 giây ở 1080x1920@30 dựng mất khoảng 40 giây trên 2 core.
- CHƯA chạy thử trên Windows (các file .bat, đường dẫn, ffmpeg từ winget).
- Phụ thuộc: numpy, pillow, pyyaml + ffmpeg/ffprobe trong PATH (hoặc thư mục ffmpeg/bin cạnh tool).

## Việc tiếp theo (theo thứ tự ưu tiên)
1. Chạy thử trên Windows và sửa lỗi nếu có.
2. **Layer engine** (KIEN_THUC_CAPCUT.md mục 10): timeline nhiều track, clip có vao/ra theo giây hoặc beat, mask +
   keyframe + easing (cubic_out…) + hiệu ứng (rung, nhoè xiên, chớp màu). Biên dịch các cảnh hiện có thành lớp.
   Thêm các macro `khoi_rap_hinh` (ráp hình từ CÙNG một clip, so le bậc thang 0,1s, kết thúc đồng loạt trên beat,
   footage nền vẫn chạy), `khoi_dong_loat`, `tuong_anh`, `cat_vi_mo`, `nghi_den`. Mẫu auto mới "rasooli" dùng
   đường cong mật độ: đoạn kể → cao trào nửa nhịp → nghỉ đen → lưới.
   Kiểm tra chấp nhận: dựng lại đoạn 11,3–14s của reel mẫu.
3. Chế độ kho lớn: trỏ vào cả kho, chọn ngẫu nhiên N file, không lặp file đã dùng (lưu lịch sử),
   chọn chủ đề theo thư mục con (`--chu-de`), tự cắt đoạn có chuyển động trong clip dài, dựng hàng loạt nhiều video.
4. Giao diện cửa sổ (tkinter): chọn thư mục/nhạc/mẫu/màu, ô tiêu đề, nút Bản nháp / Dựng video, thanh tiến độ.
5. `DONG_GOI_EXE.bat` bằng PyInstaller (kèm fonts/, cau_hinh.yaml, tùy chọn ffmpeg) để chia sẻ cho người khác.
6. Chỉnh vị trí chữ với ảnh chụp biểu đồ FireAnt thật; kiểm tra vùng an toàn của giao diện TikTok.

## Quy ước làm việc
- Sau mỗi thay đổi về hình: render bản nháp (`--nhap`), ghép khung hình thành ảnh lưới bằng ffmpeg
  (`fps=2,scale=240:-1,tile=7x2`) rồi tự xem lại trước khi báo xong.
- Không đổi tên các khóa YAML đã có (người dùng đang có file dự án cũ); chỉ thêm khóa mới.
