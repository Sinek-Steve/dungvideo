# Kiến thức dựng video kiểu @rasooliarts, rút từ timeline CapCut

Nguồn: kênh Facebook của Hussain Rasooli (@rasooliarts, "Rasooli Templates" trên CapCut), khoảng 70 reel.
43 reel là quay màn hình project CapCut, gồm 8 reel hướng dẫn; còn lại là video AI.

**Cách đọc tài liệu.** Mỗi ý được đánh dấu theo mức độ chắc chắn:
- **[Thấy]** là đọc trực tiếp trên màn hình (timeline, chữ hướng dẫn, khung preview).
- **[Suy ra]** là em suy luận từ hình dạng timeline và kết quả hiển thị, chưa có xác nhận.

Mốc thời gian sai số khoảng ±0,2s. Phần 1 được phân tích bằng cách phóng video lên độ phân giải gốc 720×1280
để đọc rõ từng track.

---

## 1. Giải phẫu timeline của một video mẫu (reel "2026 travel", 29s)

### Các track, từ trên xuống
| Track | Nội dung | Mức chắc chắn |
|---|---|---|
| 2 thanh cam mảnh trên track chính, chạy suốt video | 2 lớp chữ/sticker phủ toàn bộ: dòng chữ nhỏ kiểu poster phim phía trên và dải logo phim (Forrest Gump, Titanic, Destiny…) làm "billing block" | Thấy thanh và logo; việc nó là track chữ/sticker là Suy ra |
| Track chính (main) | Clip dài ~1,2–1,3s (≈4 chấm beat). Mỗi clip gắn hiệu ứng clip "英雄时刻" (bản CapCut tiếng Trung). Có transition ⋈ ở mọi điểm cắt trong đoạn kể | Thấy |
| Đường xanh ngay dưới track chính | Track nhạc thu gọn. **Chấm vàng = beat marker** | Thấy |
| Overlay 1…6 | 4 track ở phần intro, 5–6 track ở đoạn cao trào | Thấy |

**Beat marker:** từ 0–11s các chấm thưa; từ ~11s chấm dày gấp đôi. Nghĩa là đoạn cao trào được cắt theo nửa nhịp. [Thấy]

### Bản đồ thời gian
| Thời gian | Track chính | Overlay | Kết quả trên màn hình |
|---|---|---|---|
| 0–2,6s | 1 clip tuyết | 4 lớp **cùng độ dài**: 2 lớp **đen đặc (black solid)** và 2 bản sao footage | Intro cắt chéo, chữ tên kênh lộ dần |
| 2,6–11,3s | 7 clip, mỗi clip ~1,25s, mỗi clip một footage, transition ở mọi điểm cắt | Không có | "Đoạn kể": cắt nhanh, khung chữ điện ảnh phủ trên |
| 11,3–12,3s | Clip thung lũng | **5 bản sao của CÙNG clip đó, cùng điểm vào/ra** (khối "đồng loạt") | Các vòng tròn hiện lần lượt → so le nhờ **keyframe**, không nhờ vị trí clip [Suy ra] |
| 12,5–13,6s | Clip xe trên đèo | **4 bản sao cùng clip + 1 lớp đen, xếp bậc thang**: track dưới vào trễ hơn track trên ~0,1s, tất cả kết thúc cùng lúc | Các **dải chéo của cùng một khung hình lần lượt ráp lại** thành ảnh đầy đủ, giữa các dải có vạch đen mảnh [Thấy] |
| ~13,6–15,5s | **Cắt vi mô**: nhiều dấu cắt sát nhau, clip 0,1–0,3s | Không | Chuỗi chớp nhanh, có lúc **khung đen trống chỉ còn khung chữ** (khoảng nghỉ) [Thấy] |
| 15,6–16,6s | Clip hồ/thác | 6 bản sao cùng clip, đồng loạt | Vòng tròn đơn hiện ra giữa màn hình [Thấy] |
| 17,3–18,4s | Clip người leo núi | 4 bản sao bậc thang + lớp đen | Mảnh ghép vào lần lượt |
| 19,6–21s | Như trên | Bậc thang + 2 lớp đen | Các thẻ nghiêng ghép thành một ảnh |
| 22,3–24,7s | Clip ngắn | **3 track × 4 clip ~0,35s, mỗi clip một footage khác**, đổi đồng loạt | "Tường ảnh": nhiều ô cùng đổi hình theo nhịp [Suy ra từ hình dạng timeline] |
| 25,2–27,7s | Clip | **6 track bậc thang, mỗi track một footage riêng**, mỗi track 2 clip nối tiếp | Lưới 3×3 (8 ảnh + ô giữa chữ "2026" và vòng nguyệt quế), các ô vào lần lượt |
| ~28–29s | Clip cô gái | Không | Chữ "ROMANTIC TRAVEL LOOK" và nhân vật tách nền đè lên chữ |

---

## 2. Sáu nguyên lý cốt lõi của kỹ thuật "chồng nền"

1. **Nhân bản cùng một clip thành N lớp, mỗi lớp một mask.** Một khung hình bị chia thành mảnh (dải dọc, dải chéo,
   tròn, thoi). Khi các mảnh vào đủ thì chúng **ráp lại đúng ảnh gốc**, giữa các mảnh có khe đen.
   Đây là chỗ khác hẳn kiểu collage nhiều ảnh: người xem thấy *một cảnh bị xé ra rồi tự ghép lại*. [Thấy ở 12,5–13,6s, 17–21s]
2. **So le kiểu bậc thang.** Lớp sau vào trễ ~3 khung hình (≈0,1s @30fps). Tất cả lớp **kết thúc cùng một điểm cắt nằm
   trên beat**. Có 2 cách tạo độ so le:
   - (a) dời điểm bắt đầu clip trên timeline, tạo hình bậc thang;
   - (b) để các clip cùng điểm vào nhưng keyframe vị trí/scale/mask lệch nhau (khối đồng loạt).
3. **Lớp đen đặc (black solid) trong chồng lớp** dùng làm nền tối hoặc vạch chia giữa các mảnh, thường vào cuối cùng
   trong bậc thang. [Thấy có lớp đen; công dụng là Suy ra]
4. **Nền không bao giờ dừng.** Track chính luôn có footage chạy bên dưới. Mỗi khối overlay dài đúng bằng clip nền bên
   dưới, nên không có khung hình "chết".
5. **Đường cong mật độ:**
   - đoạn kể: 1 lớp, clip ~4 chấm beat, có transition;
   - cao trào: 5–6 lớp, mỗi khối ~2 beat, beat marker dày gấp đôi, xen chuỗi cắt vi mô;
   - **khoảng nghỉ đen** khoảng 1 nhịp;
   - finale: lưới 3×3.
6. **Lớp phủ toàn cục làm đồng tông:**
   - khung chữ điện ảnh và dải logo phủ suốt video;
   - ở reel khác thấy thêm **filter "Drama" + điều chỉnh "Clarity"** phủ cả video và **transition "Vertical blur"** ở mọi
     điểm cắt [Thấy chữ chú thích trong reel].

   Nhờ vậy footage khác nguồn vẫn trông cùng một bộ phim.

---

## 3. Quy trình 32 bước (reel "HOW TO MAKE THIS EDIT", chữ hướng dẫn đọc nguyên văn) [Thấy]

Video dạng "giới thiệu nhân vật" (character showcase): mỗi pose nhân vật vào đúng một beat, có nền màu chớp và thẻ icon.

| Bước | Nguyên văn | Ý nghĩa |
|---|---|---|
| 1 | Start a new project and add your background clip | Tạo project, thêm clip nền |
| 2 | Overlay > Add overlay: add your character | Thêm nhân vật làm overlay |
| 3 | Remove BG > Auto removal | Tách nền tự động |
| 4 | Shrink the character and add a keyframe | Thu nhỏ nhân vật, đặt keyframe |
| 5 | Move forward a little and scale it back up | Tiến vài khung, phóng lại cỡ cũ → **cú "punch" zoom** |
| 6 | Between the keyframes: Graphs > Cubic Out | Đường cong tốc độ **Cubic Out** (nhanh rồi chậm dần) |
| 7 | Add a purple background as another overlay | Thêm nền màu tím làm overlay |
| 8 | Trim it short, then Animations: Fade In + Fade Out | Cắt ngắn, hoạt ảnh mờ vào + mờ ra → **chớp màu** |
| 9 | Layer: send the purple behind the character | Đưa nền tím xuống sau nhân vật |
| 10 | Effects > Video effects > Shake, Speed and Intensity at max | Hiệu ứng **Rung**, tốc độ và cường độ tối đa |
| 11 | Object > All videos, then a keyframe at the start | Áp hiệu ứng cho mọi video, keyframe ở đầu |
| 12 | Move forward, set both to 0, then trim the effect | Tiến lên, đặt cả hai về 0, cắt hiệu ứng → **rung chỉ vài khung rồi tắt** |
| 13 | Search "Oblique Blur" and set Blur to max | Hiệu ứng **Nhoè xiên**, đặt tối đa |
| 14 | Object > All videos, Blur 100 at the start | Nhoè 100 ở đầu |
| 15 | Move forward, Blur 0, then Graphs > Cubic Out | Về 0, đường cong Cubic Out → **nhoè tan dần khi vào** |
| 16 | *(chưa đọc được)* | |
| 17 | Next pose: move to the end of the first clip and add another overlay | Pose tiếp theo nối ngay cuối clip trước |
| 18 | *(chưa đọc được)* | |
| 19 | Icon card: back at the start, add an icon as an overlay | Quay lại đầu, thêm thẻ icon |
| 20 | Shrink the card, move it into place and trim it very short | Thu nhỏ, đặt vị trí, cắt **rất ngắn** |
| 21 | Duplicate it, then Replace the copy with the next icon | Nhân bản rồi **Thay thế** bằng icon kế tiếp (giữ nguyên vị trí + hiệu ứng) |
| 22 | Slot view: "?" overlay on the right, characters on the left | Bố cục ô: dấu "?" bên phải, nhân vật bên trái |
| 23 | Add the characters on the left: overlay, shrink, drag into place | Thêm nhân vật bên trái |
| 24 | Music: Audio > Extract, and pick the video that has the sound | Lấy nhạc tách từ một video |
| 25–26 | Add a beat marker on each hit of the music | **Đặt beat marker trên mỗi tiếng nhấn** |
| 27 | The dots are your beats: start each pose and each flash on one | **Chấm = beat: mỗi pose và mỗi lần chớp bắt đầu đúng một chấm** |
| 28 | Next character: move along the timeline and add its first pose | Nhân vật tiếp theo |
| 29 | Give each character its own flash colour, then send it behind with Layer | Mỗi nhân vật một màu chớp riêng, đặt sau nhân vật |
| 30 | *(chưa đọc được)* | |
| 31 | When every cut sits on a beat, tap Export | Khi mọi điểm cắt đều nằm trên beat thì xuất |
| 32 | Saved to your device. Tap Done, or share it from here | Hoàn tất |

**Ba "gói hiệu ứng vào" rút ra, dùng lại được cho mọi cú cắt:**
- **Punch:** scale nhỏ hơn rồi về 100% trong 2–4 khung, đường cong Cubic Out.
- **Rung:** Shake tối đa trong vài khung đầu, sau đó về 0.
- **Nhoè tan:** Oblique Blur 100 về 0, đường cong Cubic Out.

Thêm **chớp màu nền** (overlay màu đặc rất ngắn, Fade In/Out, nằm sau chủ thể).

---

## 4. Trình chiếu chớp từ 1 ảnh (reel "Bet you can't tell… ONE photo") [Thấy]
1. **Import & Trim:** đặt độ dài 0,3s.
2. **Add Music.**
3. **Opacity Fade:** keyframe độ mờ từ 0 lên 100.
4. **Zoom Out:** Animations > In > Zoom out.
5. **Overlay Layer:** đưa clip đầu thành overlay, rồi **nhân bản** nhiều lần.

Kết quả là "Flash slideshow": cùng một ảnh nhưng mỗi bản cắt khung khác nhau, chớp liên tục theo nhịp.

## 5. Lý thuyết beat sync (reel "[Beat Sync] Video Editing Ideas") [Thấy chữ, diễn giải]
- **Kiểu 1:** đi theo tiếng trống, đổi cảnh trên mỗi tiếng nhấn ("CUT / SWAP"). Một cảnh cũng có thể là một cú push-in.
  Giữ cảnh **nhanh hơn beat một chút**.
- **Kiểu 2:** kết hợp beat với **SFX** (chữ "POW!", "Hit!", "BOOM!"). Nhưng beat hay đến mấy cũng cần **khoảng thở**:
  "WAIT", đừng hoảng, thả một beat bất ngờ.
- **Kiểu 3:** thử nhịp khác nhau. Beat quá nhanh thì **bắt ít beat hơn**; có lúc thêm beat; **đổi nhịp** để không nhàm.
- **Trước drop thì không sync**, để cảm xúc dâng lên. Đến drop thì "hit every beat".

## 6. Quy trình mask + beat (reel "Capcut Beatsync trending video tutorial", 3 phút) [Thấy giao diện, không có chữ]
1. Thêm nhạc, tắt tiếng gốc của clip, dùng beat tự động (giao diện có nút Delete beat).
2. **Split** clip đúng tại beat.
3. Đưa clip / bản sao thành **overlay**.
4. Chọn **Mask** trong danh sách: None, Horizontal, Mirror, Circle, Rectangle, Heart…
5. Chỉnh trong các tab **Position / Rotate / Feather**, ví dụ xoay −90°.
6. Thêm overlay tiếp theo, lặp lại.

Kết quả: các dải nghiêng chứa cùng một cảnh, trượt lệch nhau.

## 7. Màu, chữ, chuyển động
- **Màu điện ảnh 3 bước** (reel color grading) [Thấy]:
  - Effect **God Rays**, Range 77, Atmosphere 63;
  - Filter **Cyan Red** 36;
  - Filter **Fogo City** 30 (đọc từ ảnh bìa reel).
- **Reel thành phố** [Thấy chữ]: Filter **Drama + Clarity**, transition **Vertical blur** ở mọi điểm cắt.
- **Chữ động** (reel "Seriously"): mỗi từ là một lớp chữ riêng, khớp lời nói. Nền đỏ/trắng đổi theo nhịp.
- **Chữ chuyên nghiệp:** chữ đậm đi kèm sticker động đặt sát chữ.
- **Speed curves (Graphs)** trên mọi keyframe chuyển động. Reel "POV: You finally learned this CapCut transition"
  chỉ ra đúng điều này: cùng một chuyển động, có đường cong thì mượt hẳn.

## 8. Danh mục hình mask và bố cục đã gặp
- **Hình:**
  - dải dọc, dải ngang, dải chéo (hình bình hành);
  - tròn, elip (dạng "mắt / ống kính");
  - thoi, chữ X, dấu cộng, sao, lục giác, răng cưa (zigzag);
  - viên thuốc bo tròn cao thấp (kiểu "phím đàn"), thẻ bo góc nghiêng;
  - mũi tên/chevron hai bên, ống kính mắt cá.
- **Bố cục:**
  - hàng ngang 5–6 hình ở giữa màn hình;
  - đường chéo cong của các vòng tròn;
  - lưới 3×3 có ô chữ ở giữa; tường ảnh 4×4 có chữ ở giữa;
  - dải chữ cái (mỗi dải dọc mang một chữ của tên kênh);
  - ráp mảnh theo bậc thang.
- **Khung phủ:** chữ kiểu poster phim, dải logo phim, khung ống ngắm có "REC", viền phim có lỗ.

---

## 9. So với tool DựngVideo hiện tại: còn thiếu gì
| Kỹ thuật của @rasooliarts | Tool hiện tại |
|---|---|
| Timeline nhiều lớp chồng, khối overlay nối tiếp liên tục | Dựng theo **cảnh rời**, mỗi cảnh tự vẽ, chuyển cảnh ở ranh giới |
| **Ráp hình từ CÙNG một clip** (mỗi mảnh là một phần của cùng khung hình) | Mỗi ô chia được cover-fit **ảnh riêng** → ra kiểu collage. Chưa có chế độ ráp hình |
| Footage nền **vẫn chạy** dưới các mảnh | Nền tối đứng yên (hoặc ảnh mờ) |
| So le bậc thang ~0,1s, kết thúc đồng loạt đúng beat | Có so le khi vào, nhưng không có quy tắc "kết thúc đồng loạt trên beat" |
| Cắt vi mô, khoảng nghỉ đen, tường ảnh đổi hình đồng loạt | Chưa có |
| Gói hiệu ứng vào: punch Cubic Out, rung vài khung, nhoè xiên tan dần, chớp màu nền | Chỉ có nhún zoom theo beat |
| Tách nền chủ thể (Remove BG) | Chưa có (có thể dùng `rembg`, nhưng nặng) |
| Mật độ beat gấp đôi ở đoạn cao trào | Có nhịp 2-2-1-1 sau drop, chưa có nửa nhịp |

## 10. Đặc tả "layer engine" để làm đúng kiểu này (việc cho Claude Code)

Viết lớp lõi dạng timeline nhiều track giống CapCut, rồi biên dịch các "cảnh" hiện có thành các lớp.

```yaml
lop:                         # mỗi phần tử = 1 clip trên 1 track overlay
  - track: 3                 # số lớn hơn vẽ đè lên trên
    media: 05_deo.mp4
    vao: b:24                # giây (12.5) hoặc beat thứ 24 (b:24) hoặc nửa beat (b:24.5)
    ra: b:26
    mask: {hinh: dai_cheo, goc: -20, vi_tri: 0.4, rong: 0.22, vien_mo: 1.5}
    keyframe:                # nội suy theo easing; thuộc tính: x, y, scale, xoay, do_mo, mask_scale, blur
      - {t: 0.00, x: -1.1}
      - {t: 0.25, x: 0, easing: cubic_out}
    hieu_ung:
      - {loai: rung, tu: 0, den: 0.12, cuong_do: 1.0}
      - {loai: nhoe_xien, tu: 0, den: 0.2, tu_gia_tri: 100, den_gia_tri: 0, easing: cubic_out}
```

**Các macro (khối) cần có, sinh ra nhiều lớp từ một dòng cấu hình:**
- `khoi_rap_hinh`: N bản sao cùng clip; mask dải dọc / dải chéo / tròn / thoi / thẻ chia đều khung hình; mỗi lớp trễ
  `so_le` (mặc định 0,1s); tất cả kết thúc trên beat cuối khối; khe đen 6–10px; footage nền vẫn chạy bên dưới.
- `khoi_dong_loat`: N bản sao cùng clip, cùng điểm vào, so le bằng keyframe `mask_scale` (tròn nở lần lượt).
- `tuong_anh`: lưới K ô, mỗi ô đổi footage đồng loạt theo nửa nhịp.
- `cat_vi_mo`: chuỗi 3–5 clip 0,1–0,25s trước một điểm nhấn.
- `nghi_den`: 1 nhịp màn hình đen, chỉ giữ khung chữ.
- `vao_punch`, `vao_rung`, `vao_nhoe`, `chop_mau`: các gói hiệu ứng vào, gắn được cho mọi điểm cắt.

**Bài kiểm tra chấp nhận:** dựng lại đoạn 11,3–14s của reel mẫu (khối đồng loạt tròn → khối bậc thang dải chéo ráp
hình → cắt vi mô), rồi so từng khung với bản gốc.
