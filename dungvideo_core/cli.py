"""Dòng lệnh của DựngVideo."""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

import yaml

from .util import ROOT, setup_console

HELP_EFFECTS = """
CÁC LOẠI CẢNH (loai):
  tieu_de  : chữ động từng từ.  Khóa: chu, nhan_manh [list], nen (den|do|trang|xanh|tim|vang|media), phu, font (title|impact)
  day_du   : 1 ảnh/clip toàn màn hình. Khóa: media, zoom (vao|ra|khong), nhun (true/false), chu (chú thích),
             nhan (VD: HPG), chi_so (VD: +6,9%), vi_tri (duoi|giua|tren)
  chia     : chia màn hình. Khóa: kieu (doc|ngang|cheo|tron|thoi|vien|the), media [list], so, chu, phu, nen (mo)
  hinh_mo  : lộ cảnh mới qua hình nở. Khóa: hinh (tron|thoi|sao|x|luc_giac|chu_nhat|cong), media [cũ, mới]
  luoi     : lưới 3x3 zoom-out, ô giữa là chữ. Khóa: media [8 cái], chu, phu
  flash    : chớp nhanh nhiều ảnh (1 ảnh cũng được). Khóa: media, moi (nhip|nua_nhip|0.3)
  so_sanh  : 2-3 ảnh/biểu đồ chồng dọc. Khóa: media, nhan [HPG, HSG], chi_so [+3%, -1%], vs (true/false)
  ket      : màn kết. Khóa: chu (handle), phu, nut, media (nền mờ)
  nhay     : dồn cắt theo từng nốt nhạc, cắt thẳng, không nhún. Khóa: media [list], cat (not|nua_nhip|nhip|0.2),
             nguong (độ mạnh nốt, mặc định 1.5; lớn hơn = ít cắt hơn), cat_toi_thieu (giây, mặc định 0.12),
             dai_tu / dai_den / dai_giay (dải ngang mở dần, tỉ lệ chiều cao 0..1),
             vao [punch, rung, nhoe, chop] (hiệu ứng ở các cú cắt trúng phách, dùng lần lượt), chu, phu
  rap_hinh : ráp hình từ CÙNG một clip, mảnh nở theo nốt nhạc rồi ráp kín khung. Khóa: media,
             kieu (tron_cheo|tron_doc|thoi_x|x|sao|luc_giac|o_vuong), mau_nhan (màu tấm màu), khe, chu, phu
  nghi_den : khoảng nghỉ màn hình đen. Khóa: chu

THỜI LƯỢNG mỗi cảnh: nhip (số beat, mặc định 4) hoặc giay.
CHUYỂN CẢNH (chuyen, áp vào đầu cảnh): cat | mo | flash | zoom | truot | truot_ngang | vblur | glitch
MÀU (mau_sac): dien_anh | sang | lanh | am | tu_nhien
KHUNG (khung.kieu): toi_gian | phim | hud
MẪU TỰ ĐỘNG (--mau): tin-nhanh | dien-anh | slideshow | <tên mẫu trong kho_mau/> | ngau_nhien
"""

DEFAULT_CFG = {
    "mau": "tin-nhanh",
    "mau_sac": "dien_anh",
    "kich_thuoc": "1080x1920",
    "fps": 30,
    "vignette": 0.22,
    "thanh_tien_do": True,
    "thu_muc_xuat": "xuat",
    "khung": {"bat": True, "kieu": "toi_gian", "tren": [], "duoi": "", "handle": "", "loi_moi": ""},
}


def load_cfg() -> dict:
    cfg = dict(DEFAULT_CFG)
    p = ROOT / "cau_hinh.yaml"
    if p.exists():
        user = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k] = {**cfg[k], **v}
            else:
                cfg[k] = v
    return cfg


def _out_dir(cfg) -> Path:
    d = Path(cfg.get("thu_muc_xuat", "xuat"))
    if not d.is_absolute():
        d = ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M")


def write_project(proj: dict, path: Path):
    head = ("# File dự án DựngVideo — sửa rồi chạy lại: python dungvideo.py render \"" + path.name + "\"\n"
            "# Xem danh sách hiệu ứng: python dungvideo.py hieu-ung\n")
    body = yaml.safe_dump(proj, allow_unicode=True, sort_keys=False, width=110)
    path.write_text(head + body, encoding="utf-8")


def cmd_auto(a, cfg):
    from .render import render
    from .templates import all_templates, pick_template, plan
    folder = Path(a.thu_muc).expanduser().resolve()
    if not folder.is_dir():
        raise SystemExit(f"Không phải thư mục: {folder}")
    tpl = pick_template(a.mau or cfg.get("mau", "tin-nhanh"))
    if tpl not in all_templates():
        raise SystemExit(f"Mẫu không hợp lệ: {tpl}. Chọn: {', '.join(all_templates())} hoặc ngau_nhien")
    planned = plan(folder, tpl, a.tieu_de, a.nhac, a.giong, a.phu_de, a.giay, a.nhac_bat_dau or 0.0)
    style = planned.pop("_phong_cach", {})
    proj = {k: cfg[k] for k in ("kich_thuoc", "fps", "mau_sac", "vignette", "thanh_tien_do") if k in cfg}
    proj.update({k: v for k, v in style.items() if k != "khung"})
    if a.mau_sac:
        proj["mau_sac"] = a.mau_sac
    khung = dict(cfg.get("khung") or {})
    st_k = style.get("khung")
    khung.update(st_k if isinstance(st_k, dict) else ({"kieu": st_k} if st_k else {}))
    logo = planned.pop("_logo", None)
    if logo and not khung.get("logo"):
        khung["logo"] = logo
    proj["khung"] = khung
    proj.update(planned)
    out_dir = _out_dir(cfg)
    name = folder.name.replace(" ", "_")
    out = Path(a.ra).resolve() if a.ra else out_dir / f"{name}_{_stamp()}.mp4"
    proj_path = out.with_name(out.stem + "_du_an.yaml")
    proj_out = dict(proj)
    proj_out = {"dau_ra": str(out), **proj_out}
    write_project(proj_out, proj_path)
    print(f"Đã lên kịch bản {len(proj['canh'])} cảnh (mẫu {tpl}). File dự án: {proj_path}")
    if a.chi_ke_hoach:
        return
    render(proj, folder, out, draft=a.nhap)
    print(f"\nXONG! Video: {out}")


def _load_project(path: Path) -> dict:
    p = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg = load_cfg()
    for k in ("kich_thuoc", "fps", "mau_sac", "vignette", "thanh_tien_do"):
        p.setdefault(k, cfg.get(k))
    if "khung" not in p:
        p["khung"] = cfg.get("khung")
    return p


def cmd_render(a, cfg):
    from .render import render
    path = Path(a.du_an).expanduser().resolve()
    proj = _load_project(path)
    out = Path(a.ra) if a.ra else Path(proj.get("dau_ra") or (_out_dir(cfg) / f"{path.stem}_{_stamp()}.mp4"))
    if not out.is_absolute():
        out = path.parent / out
    if a.nhap:
        out = out.with_name(out.stem + "_nhap.mp4")
    render(proj, path.parent, out, draft=a.nhap)
    print(f"\nXONG! Video: {out}")


def cmd_still(a, cfg):
    from .render import still
    path = Path(a.du_an).expanduser().resolve()
    proj = _load_project(path)
    out = Path(a.ra) if a.ra else path.with_name(f"{path.stem}_{a.giay:.1f}s.png")
    still(proj, path.parent, a.giay, out, draft=a.nhap)
    print(f"Đã lưu khung hình: {out}")


def cmd_demo(a, cfg):
    from .demo import make_demo
    folder = Path(a.ra).resolve() if a.ra else ROOT / "demo_media"
    make_demo(folder)
    ns = argparse.Namespace(thu_muc=str(folder), mau=a.mau, tieu_de=None, nhac=None, giong=None, phu_de=None,
                            giay=None, mau_sac=None, nhap=a.nhap, ra=None, chi_ke_hoach=False, nhac_bat_dau=0.0)
    cmd_auto(ns, cfg)


def main(argv=None):
    setup_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    # kéo-thả: 1 đường dẫn duy nhất -> tự đoán lệnh
    if len(argv) >= 1 and argv[0] not in ("auto", "render", "chup", "demo", "hieu-ung", "tao-nhac", "-h", "--help"):
        p = Path(argv[0])
        if p.is_dir():
            argv = ["auto"] + argv
        elif p.suffix.lower() in (".yaml", ".yml"):
            argv = ["render"] + argv
    ap = argparse.ArgumentParser(prog="dungvideo", description="DựngVideo — dựng video dọc 9:16 theo nhịp nhạc")
    sp = ap.add_subparsers(dest="cmd")

    p = sp.add_parser("auto", help="Tự dựng video từ một thư mục ảnh/clip")
    p.add_argument("thu_muc")
    p.add_argument("--mau", help="tin-nhanh | dien-anh | slideshow | <tên mẫu trong kho_mau/> | ngau_nhien")
    p.add_argument("--tieu-de", dest="tieu_de")
    p.add_argument("--nhac")
    p.add_argument("--nhac-bat-dau", dest="nhac_bat_dau", type=float, help="Bắt đầu nhạc từ giây thứ ...")
    p.add_argument("--giong", help="File giọng đọc (Edge-TTS...)")
    p.add_argument("--phu-de", dest="phu_de", help="File phụ đề .srt")
    p.add_argument("--giay", type=float, help="Độ dài video mong muốn (giây)")
    p.add_argument("--mau-sac", dest="mau_sac")
    p.add_argument("--nhap", action="store_true", help="Bản nháp nhanh (nửa độ phân giải)")
    p.add_argument("--ra", help="File MP4 đầu ra")
    p.add_argument("--chi-ke-hoach", dest="chi_ke_hoach", action="store_true", help="Chỉ tạo file dự án, chưa xuất")

    p = sp.add_parser("render", help="Xuất video từ file dự án .yaml")
    p.add_argument("du_an")
    p.add_argument("--nhap", action="store_true")
    p.add_argument("--ra")

    p = sp.add_parser("chup", help="Xuất 1 khung hình PNG để xem nhanh")
    p.add_argument("du_an")
    p.add_argument("--giay", type=float, default=1.0)
    p.add_argument("--nhap", action="store_true")
    p.add_argument("--ra")

    p = sp.add_parser("demo", help="Tạo media mẫu và dựng thử")
    p.add_argument("--ra")
    p.add_argument("--mau")
    p.add_argument("--nhap", action="store_true")

    sp.add_parser("hieu-ung", help="Liệt kê cảnh/hiệu ứng")

    p = sp.add_parser("tao-nhac", help="Tự tổng hợp thư viện nhạc nền (nhac/) và tiếng động (tieng_dong/)")
    p.add_argument("--so", type=int, default=3, help="Số bài cho mỗi phong cách (mặc định 3)")
    p.add_argument("--kieu", nargs="*", help="Chỉ tạo các phong cách này (trap, house, lofi...)")

    a = ap.parse_args(argv)
    cfg = load_cfg()
    if a.cmd == "auto":
        cmd_auto(a, cfg)
    elif a.cmd == "render":
        cmd_render(a, cfg)
    elif a.cmd == "chup":
        cmd_still(a, cfg)
    elif a.cmd == "demo":
        cmd_demo(a, cfg)
    elif a.cmd == "tao-nhac":
        from .amthanh import NHAC_DIR, SFX_DIR, STYLES, tao_thu_vien, tao_tieng_dong
        print(f"Đang tạo tiếng động -> {SFX_DIR}")
        tao_tieng_dong()
        print(f"Đang soạn nhạc ({', '.join(a.kieu or STYLES)}) -> {NHAC_DIR}")
        rows = tao_thu_vien(a.so, a.kieu)
        print(f"\nXONG! {len(rows)} bài nhạc trong {NHAC_DIR}")
    elif a.cmd == "hieu-ung":
        print(HELP_EFFECTS)
        from .templates import list_recipes
        rcs = list_recipes()
        if rcs:
            print("KHO MẪU RIÊNG (kho_mau/, dùng: --mau <tên> hoặc --mau ngau_nhien):")
            for name, rc in rcs.items():
                print(f"  {name:22s}: {rc.get('ten', '')} - {rc.get('mo_ta', '')}")
    else:
        ap.print_help()
