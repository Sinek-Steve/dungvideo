# DựngVideo: tool dựng video dọc 9:16 theo nhịp nhạc

Tool được viết dựa trên các kỹ thuật học từ kênh CapCut của Hussain Rasooli (@rasooliarts):
chia màn hình bằng mask, cắt theo beat, chữ động từng từ, khung thương hiệu phủ suốt video, lưới ảnh zoom-out,
lộ cảnh qua hình nở, trình chiếu chớp nhanh và chỉnh màu điện ảnh. Tất cả được làm lại cho **khung dọc** và cho
**kênh tin chứng khoán**.

## 1. Cài đặt (làm 1 lần)
1. Cần Python 3.10+ và ffmpeg (máy anh đã có sẵn nếu đang chạy MoneyPrinterTurbo).
2. Bấm đúp `1_CAI_DAT.bat`.
3. Bấm đúp `4_CHAY_THU_DEMO.bat` để chạy thử. Tool sẽ tạo ảnh và nhạc mẫu rồi dựng video vào thư mục `xuat`.

## 2. Dùng hằng ngày: kéo thả một thư mục
Chuẩn bị một thư mục, ví dụ `D:\video\tin_18_11`, gồm:

| File | Vai trò |
|---|---|
| `01.jpg`, `02.mp4`, `03.png`… | Ảnh / clip / ảnh chụp biểu đồ, dùng theo thứ tự tên file |
| 1 file nhạc `.mp3/.wav` | Nhạc nền. Tool tự dò beat và cắt cảnh theo nhịp |
| `giong_doc.mp3` (tên có chữ *giong / voice / tts*) | Giọng đọc. Video dài đúng bằng giọng đọc, nhạc tự giảm nhỏ |
| `*.srt` | Phụ đề (Edge-TTS / MoneyPrinterTurbo xuất được) |
| `logo.png` | Logo tròn ở góc và ở màn kết |
| `chu.txt` | Chữ trên video (xem bên dưới) |

**`chu.txt`:**
```
VN-Index vượt mốc 1.300 điểm              <- dòng đầu = tiêu đề mở màn (con số tự tô màu)
04: HPG +6,9% | Hòa Phát tăng trần          <- chú thích riêng cho file bắt đầu bằng số 04
07: VNM -1,2% | Tiêu dùng chịu áp lực        <- mã giảm tự hiện màu đỏ, mã tăng màu xanh
Khối ngoại mua ròng hơn 500 tỷ               <- dòng không số: chú thích lần lượt cho các cảnh còn lại
```

Kéo thư mục đó thả lên `2_TAO_VIDEO_TU_THU_MUC.bat`. Video ra trong `xuat\`, kèm một file `..._du_an.yaml`.

## 3. Sửa rồi xuất lại
Mở file `..._du_an.yaml` bằng Notepad để sửa: đổi chữ, đổi kiểu cảnh, đổi chuyển cảnh, đổi số nhịp…
Sau đó kéo file thả lên `3_XUAT_LAI_TU_FILE_DU_AN.bat`.

Ví dụ một cảnh:
```yaml
- loai: chia          # chia màn hình
  kieu: tron          # doc | ngang | cheo | tron | thoi | vien | the
  media: [01.jpg, 02.mp4, 03.jpg]
  nhip: 4             # dài 4 beat (hoặc dùng  giay: 2.5)
  chuyen: zoom        # cat | mo | flash | zoom | truot | truot_ngang | vblur | glitch
```
Gõ `python dungvideo.py hieu-ung` để xem đủ danh sách cảnh và khóa.

## 4. Các loại cảnh
- **tieu_de**: chữ hiện từng từ, từ nhấn mạnh nảy to và chớp nền. Nền có thể là `do`, `den`, `trang`, `xanh` hoặc `media` (ảnh mờ).
- **day_du**: một ảnh/clip toàn màn hình, zoom chậm và nhún theo beat. Có khung chú thích và thẻ mã + %.
- **chia**: chia màn hình. `doc` cho dải dọc, `ngang` cho dải ngang, `cheo` cho dải chéo, `tron` cho hình tròn, `thoi` cho hình thoi, `vien` cho thanh bo tròn cao thấp, `the` cho thẻ nghiêng.
- **hinh_mo**: cảnh mới lộ ra qua một hình nở to và xoay. Chọn hình `tron`, `thoi`, `sao`, `x`, `luc_giac` hoặc `chu_nhat`.
- **luoi**: lưới 3x3, khởi đầu phóng to ô giữa rồi zoom ra để lộ cả lưới.
- **flash**: chớp nhanh mỗi ảnh khoảng 0,3s, mờ dần vào kèm zoom ra. Dùng được với chỉ 1 ảnh (tool tự cắt nhiều góc).
- **so_sanh**: 2–3 biểu đồ chồng dọc, có thẻ mã + % và huy hiệu VS.
- **ket**: màn kết với handle, lời mời theo dõi và nút THEO DÕI nhún theo beat.

## 5. Quy tắc dựng tool tự áp dụng (học từ các reel hướng dẫn beat sync)
- Cắt cảnh đúng beat. Trước đoạn "drop" của nhạc thì cảnh dài và không nhún. Sau drop thì cắt dồn theo nhịp 2-2-1-1-2.
- Nhạc nhanh quá (trên ~158 BPM) thì chỉ bắt mỗi 2 beat.
- Cảnh có chữ luôn giữ đủ 4 beat để người xem kịp đọc.
- Đổi kiểu chuyển cảnh liên tục, xen kẽ cảnh toàn màn hình với cảnh chia mask.

## 6. Cấu hình chung: `cau_hinh.yaml`
Ở đây đặt mẫu mặc định (`tin-nhanh`, `dien-anh` hoặc `slideshow`), màu (`dien_anh`, `sang`, `lanh`, `am` hoặc `tu_nhien`),
khung thương hiệu (`toi_gian`, `phim` hoặc `hud`), các nhãn trên cùng và handle. Nếu chữ TikTok che dòng handle phía dưới
thì giảm `vi_tri_duoi` (ví dụ 0.82).

## 7. Dòng lệnh (cho pipeline tự động)
```
python dungvideo.py auto "D:\video\tin_18_11" --mau tin-nhanh --tieu-de "..." --nhap
python dungvideo.py auto THU_MUC --nhac nhac.mp3 --nhac-bat-dau 30 --giay 25
python dungvideo.py auto THU_MUC --giong voice.mp3 --phu-de voice.srt
python dungvideo.py render du_an.yaml [--nhap]
python dungvideo.py chup du_an.yaml --giay 5.2      # xuất 1 khung hình PNG để xem nhanh
```
`--nhap` xuất bản nháp nửa độ phân giải, nhanh gấp khoảng 4 lần.

Font kèm theo: Montserrat và Anton (giấy phép SIL OFL, xem thư mục `fonts`).
