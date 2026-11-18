"""Chế độ tự động: quét thư mục -> lên kịch bản cảnh theo mẫu -> file dự án YAML.

Quy tắc dựng rút ra từ các reel CapCut đã xem:
  * Cắt theo beat; mỗi cú cắt nhanh hơn beat một chút.
  * Trước "drop" của nhạc: cảnh dài hơn, không nhún; sau drop: cắt dồn 2-1-1-2 nhịp.
  * Nhạc nhanh quá (>158 BPM) thì bắt ít beat hơn (nhân đôi số nhịp mỗi cảnh).
  * Xen kẽ cảnh toàn màn hình với cảnh chia màn hình bằng mask (dải, tròn, thoi, thẻ...).
  * Đổi kiểu chuyển cảnh liên tục để không nhàm; kết bằng lưới ảnh + màn kết.
"""
from __future__ import annotations

import random
import re
from pathlib import Path

import yaml

from .beats import detect, synthetic
from .media import probe_duration
from .util import AUD_EXT, IMG_EXT, ROOT, VID_EXT

TEMPLATES = ("tin-nhanh", "dien-anh", "slideshow")
KHO_MAU = ROOT / "kho_mau"   # kho mẫu riêng: mỗi file .yaml là một công thức dựng


def list_recipes() -> dict:
    """{tên mẫu: công thức} của mọi file trong kho_mau/."""
    out = {}
    for p in sorted(KHO_MAU.glob("*.yaml")) if KHO_MAU.is_dir() else []:
        rc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out[p.stem] = rc
    return out


def all_templates() -> list:
    return list(TEMPLATES) + list(list_recipes())


def pick_template(name: str) -> str:
    """'ngau_nhien' -> chọn ngẫu nhiên một mẫu trong kho."""
    if name == "ngau_nhien":
        names = list(list_recipes()) or list(TEMPLATES)
        return random.choice(names)
    return name


def _natural_key(p: Path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", p.name)]


def scan_folder(folder: Path) -> dict:
    files = sorted([p for p in Path(folder).iterdir() if p.is_file()], key=_natural_key)
    media = [p for p in files if p.suffix.lower() in IMG_EXT | VID_EXT and not p.stem.lower().startswith("logo")]
    audio = [p for p in files if p.suffix.lower() in AUD_EXT]
    voice = next((p for p in audio if re.search(r"giong|voice|tts|doc", p.stem.lower())), None)
    music = next((p for p in audio if p != voice), None)
    srt = next((p for p in files if p.suffix.lower() == ".srt"), None)
    logo = next((p for p in files if p.stem.lower().startswith("logo") and p.suffix.lower() in IMG_EXT), None)
    lines = []
    for name in ("chu.txt", "noi_dung.txt", "text.txt"):
        f = Path(folder) / name
        if f.exists():
            lines = [l.strip() for l in f.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                     if l.strip() and not l.strip().startswith("#")]
            break
    return {"media": media, "music": music, "voice": voice, "srt": srt, "lines": lines, "logo": logo}


def parse_caption(line: str) -> dict:
    """'HPG +6,9% | Hòa Phát tăng trần' -> nhan, chi_so, chu."""
    out = {}
    if "|" in line:
        left, right = [x.strip() for x in line.split("|", 1)]
        toks = left.split()
        if toks:
            out["nhan"] = toks[0]
        if len(toks) > 1:
            out["chi_so"] = " ".join(toks[1:])
        if right:
            out["chu"] = right
    else:
        out["chu"] = line
    return out


def auto_highlight(title: str) -> list:
    """Tự chọn từ nhấn mạnh: con số (1.300, +6,9%) và cụm trong ngoặc kép."""
    hl = re.findall(r"[+\-]?\d[\d.,]*%?", title)
    for a, b in re.findall(r"\"([^\"]+)\"|“([^”]+)”", title):
        hl.append(a or b)
    return [h for h in hl if h]


class _Planner:
    def __init__(self, media, beats, music: bool, total: float):
        self.media = [str(m) for m in media]
        self.queue = list(self.media)
        self.beats = beats
        self.music = music
        self.total = total
        self.bi = 0  # chỉ số beat hiện tại
        self.scenes = []
        self.mult = 2 if music and beats.period < 0.38 else 1

    def t(self):
        b = self.beats.beats
        if self.bi < len(b):
            return float(b[self.bi])
        return float(b[-1] + (self.bi - len(b) + 1) * self.beats.period)

    def take(self, k=1, skip=()):
        """Lấy k media theo thứ tự; bỏ qua các file trong `skip` (để dành cho cảnh có chú thích riêng)."""
        out = []
        guard = 0
        while len(out) < k and guard < 4:
            if not self.queue:
                self.queue = list(self.media)
                guard += 1
            pick = next((m for m in self.queue if m not in skip and m not in out), None)
            if pick is None:
                if guard >= 1 and not out:
                    pick = self.queue[0]
                else:
                    self.queue = []
                    continue
            self.queue.remove(pick)
            out.append(pick)
        return out

    def peek(self):
        if not self.queue:
            self.queue = list(self.media)
        return self.queue[0]

    def before_drop(self):
        d = self.beats.drop
        return bool(self.music and d and self.t() < d - 0.05)

    def add(self, sc: dict, nhip: int):
        nhip = max(1, int(nhip * self.mult))
        sc["nhip"] = nhip
        self.scenes.append(sc)
        self.bi += nhip

    def remaining(self):
        return self.total - self.t()


def plan(folder: Path, template: str = "tin-nhanh", title: str | None = None, music=None, voice=None,
         srt=None, seconds: float | None = None, music_start: float = 0.0) -> dict:
    info = scan_folder(folder)
    media = info["media"]
    if not media:
        raise SystemExit(f"Thư mục {folder} không có ảnh/clip nào.")
    music = Path(music) if music else info["music"]
    voice = Path(voice) if voice else info["voice"]
    recipe = list_recipes().get(template) if template not in TEMPLATES else None
    if not music:
        from .amthanh import chon_nhac
        music = chon_nhac((recipe or {}).get("nhac"))
        if music:
            print(f"Thư mục chưa có nhạc -> lấy từ thư viện nhac/: {music.name}")
    srt = Path(srt) if srt else info["srt"]
    lines = list(info["lines"])
    if not title:
        if lines and not re.match(r"^\s*\d+\s*:", lines[0]):
            title = lines.pop(0)
        else:
            title = Path(folder).name.replace("_", " ")
    # "04: HPG +6,9% | ..." -> chú thích riêng cho file bắt đầu bằng số 04
    keyed, captions = {}, []
    for l in lines:
        m = re.match(r"^\s*(\d+)\s*:\s*(.+)$", l)
        if m:
            num = int(m.group(1))
            for f in media:
                fm = re.match(r"^(\d+)", f.name)
                if fm and int(fm.group(1)) == num:
                    keyed[str(f)] = parse_caption(m.group(2))
                    break
        else:
            captions.append(parse_caption(l))

    n = len(media)
    if seconds:
        total = float(seconds)
    elif voice:
        total = probe_duration(str(voice)) + 0.8
    elif music:
        total = min(probe_duration(str(music)) - music_start, max(12.0, n * 1.6 + 5), 60.0)
    else:
        total = min(max(n * 1.3 + 4, 8.0), 60.0)
    if recipe is not None and not seconds and not voice:
        cap = float(recipe.get("do_dai", 30))
        total = min(probe_duration(str(music)) - music_start, cap) if music else min(cap, 20.0)

    if music:
        print("Đang dò nhịp nhạc để lên kịch bản...")
        beats = detect(str(music), start=music_start)
        has_music = len(beats.beats) >= 4
        if not has_music:
            beats = synthetic(total + 10)
    else:
        beats, has_music = synthetic(total + 10), False

    P = _Planner(media, beats, has_music, total)
    end_beats = 4
    cap_i = 0

    def next_caption(path):
        nonlocal cap_i
        if path in keyed:
            return dict(keyed.pop(path))
        if cap_i < len(captions):
            cap_i += 1
            return dict(captions[cap_i - 1])
        return {}

    if recipe is not None:
        # mẫu trong kho: chữ không gắn vào từng file (mỗi file có thể chỉ hiện ~0,2s) -> dùng các dòng theo thứ tự
        texts = [parse_caption(re.sub(r"^\s*\d+\s*:\s*", "", l)) for l in lines]
        _plan_recipe(P, recipe, title, texts)
        proj = _project(P, music, music_start, voice, srt, info, total, seconds)
        proj["_phong_cach"] = {k: recipe[k] for k in ("mau_sac", "vignette", "thanh_tien_do", "khung") if k in recipe}
        return proj

    trans_cycle = ["vblur", "flash", "truot", "zoom", "glitch", "truot_ngang", "zoom", "mo"]
    tc = 0

    def tr():
        nonlocal tc
        tc += 1
        return trans_cycle[(tc - 1) % len(trans_cycle)]

    mix = [2, 2, 1, 1, 2, 2, 4]
    mx = 0

    def shot_beats():
        nonlocal mx
        if P.before_drop() or not has_music:
            return 4 if has_music else 3
        mx += 1
        return mix[(mx - 1) % len(mix)]

    grid_beats = 8 if n >= 8 else 0

    def end_space():
        return P.beats.period * P.mult * (end_beats + grid_beats) + 0.2

    # ---------------- intro
    if template == "dien-anh":
        P.add({"loai": "chia", "kieu": "cheo", "media": P.take(3, set(keyed)), "chu": title, "font": "impact"},
              8 if P.mult == 1 else 4)
    elif template == "slideshow":
        P.add({"loai": "tieu_de", "chu": title, "nen": "media", "media": P.take(1, set(keyed))[0],
               "nhan_manh": auto_highlight(title)}, 4)
    else:
        P.add({"loai": "tieu_de", "chu": title, "nen": "do", "nhan_manh": auto_highlight(title)}, 4)
        if n >= 3:
            P.add({"loai": "chia", "kieu": "ngang", "media": P.take(3, set(keyed)), "chuyen": "zoom"}, 4)

    # ---------------- thân
    split_cycle = {"tin-nhanh": ["the", "doc", "tron", "vien", "thoi", "cheo"],
                   "dien-anh": ["doc", "tron", "vien", "thoi", "the", "ngang"],
                   "slideshow": ["tron", "the", "vien"]}[template if template in TEMPLATES else "tin-nhanh"]
    reveal_cycle = ["tron", "thoi", "luc_giac", "sao", "x"]
    k = 0
    while P.remaining() > end_space() + P.beats.period * P.mult * 2:
        k += 1
        slot = "full"
        if template == "slideshow" and k % 3 == 0 and n >= 4:
            slot = "flash"
        elif k % 4 == 0:
            slot = "split"
        elif k % 6 == 5 and n >= 2:
            slot = "reveal"
        st = split_cycle[(k // 4 - 1) % len(split_cycle)]
        cnt = {"flash": min(6, n), "reveal": 2, "full": 1,
               "split": min({"vien": 4}.get(st, 3), max(2, n))}[slot]
        # ảnh có chú thích riêng không bị gộp vào cảnh nhiều ảnh -> để dành cho cảnh toàn màn hình
        if P.peek() in keyed:
            slot = "full"
        skip = set(keyed)
        if slot == "flash":
            P.add({"loai": "flash", "media": P.take(cnt, skip), "chuyen": "flash"}, 4)
        elif slot == "split":
            P.add({"loai": "chia", "kieu": st, "media": P.take(cnt, skip), "chuyen": tr()}, 4)
        elif slot == "reveal":
            P.add({"loai": "hinh_mo", "hinh": reveal_cycle[(k // 6) % len(reveal_cycle)],
                   "media": P.take(2, skip), "chuyen": "cat"}, 4)
        else:
            sc = {"loai": "day_du", "media": P.take(1)[0], "chuyen": tr(),
                  "zoom": "vao" if k % 2 else "ra"}
            sc.update(next_caption(sc["media"]))
            if P.before_drop():
                sc["nhun"] = False
            nb = shot_beats()
            if sc.get("chu") and nb < 4:
                nb = 4  # có chữ thì để đủ lâu cho người xem đọc
            P.add(sc, nb)
        if k > 400:
            break

    # ---------------- kết
    if grid_beats:
        short = title if len(title) <= 28 else title[:26].rsplit(" ", 1)[0] + "…"
        P.add({"loai": "luoi", "media": P.take(8), "chu": short, "chuyen": "zoom"}, grid_beats)
    P.add({"loai": "ket", "media": P.take(1)[0], "chuyen": "mo"}, end_beats)
    return _project(P, music, music_start, voice, srt, info, total, seconds)


# số file media mỗi loại khối lấy mặc định (khóa `so` trong công thức đè lên)
SO_MEDIA = {"nhay": 6, "rap_hinh": 1, "day_du": 1, "ket": 1, "luoi": 8, "chia": 3, "hinh_mo": 2,
            "tuong_anh": 6, "flash": 6, "so_sanh": 2, "tieu_de": 0, "nghi_den": 0}
# khóa nhận danh sách để xoay vòng mỗi lần khối lặp lại (các khóa khác giữ nguyên, ví dụ vao: [nhoe, punch])
XOAY_VONG = {"kieu", "hinh", "font", "vi_tri", "zoom", "chuyen", "mau_nhan", "nen"}
KHOA_CONG_THUC = {"so", "nhip", "nhip_co_chu", "tieu_de", "chu", "toi_drop", "dai_nhip"}


def _plan_recipe(P: _Planner, rc: dict, title: str, texts: list):
    """Dựng kịch bản từ một công thức trong kho_mau/: mo_dau (lần lượt) -> than (lặp vòng tới gần hết video,
    khối có `chu: true` nhận lần lượt các dòng chữ) -> ket."""
    beat = P.beats.period * P.mult
    ket = rc.get("ket") or [{"loai": "nghi_den", "nhip": 1}, {"loai": "ket", "nhip": 4}]
    end_space = beat * sum(int(b.get("nhip", 4)) for b in ket) + 0.2
    ti = 0

    def block(spec: dict, rep: int):
        nonlocal ti
        sc = {k: (v[rep % len(v)] if k in XOAY_VONG and isinstance(v, list) else v)
              for k, v in spec.items() if k not in KHOA_CONG_THUC}
        nb = int(spec.get("nhip", 4))
        so = int(spec.get("so", SO_MEDIA.get(sc.get("loai"), 1)))
        if so:
            sc["media"] = P.take(min(so, len(P.media)))
        if spec.get("tieu_de"):
            sc["chu"] = title if sc.get("loai") != "luoi" or len(title) <= 28 \
                else title[:26].rsplit(" ", 1)[0] + "…"
        elif spec.get("chu") and ti < len(texts):
            c = texts[ti]
            ti += 1
            tag = " ".join(x for x in (c.get("nhan"), c.get("chi_so")) if x)
            sc["chu"] = c.get("chu") or tag
            if c.get("chu") and tag:
                sc["phu"] = tag
            nb = int(spec.get("nhip_co_chu", nb))  # khối có chữ giữ lâu hơn cho kịp đọc
        if spec.get("toi_drop") and P.music and P.beats.drop:
            left = int(round((P.beats.drop - P.t()) / beat))
            if 4 <= left <= 16:
                nb = left  # khối kết thúc đúng lúc nhạc bùng lên
        if "dai_nhip" in spec:
            sc["dai_giay"] = round(beat * float(spec["dai_nhip"]), 2)
        elif "dai_tu" in sc:
            sc["dai_giay"] = round(beat * nb * 0.6, 2)
        return sc, nb

    for spec in rc.get("mo_dau") or []:
        P.add(*block(spec, 0))
    body = rc.get("than") or []
    k = 0
    while body and k < 400:
        sc, nb = block(body[k % len(body)], k // len(body))
        fit = int((P.remaining() - end_space) / beat)
        if fit < 2:
            break
        P.add(sc, min(nb, fit))
        k += 1
    for spec in ket:
        P.add(*block(spec, 0))


def _project(P: _Planner, music, music_start, voice, srt, info, total, seconds) -> dict:
    proj = {
        "canh": P.scenes,
    }
    if music:
        proj["nhac"] = str(music)
        if music_start:
            proj["nhac_bat_dau"] = music_start
    if voice:
        proj["giong_doc"] = str(voice)
    if srt:
        proj["phu_de_srt"] = str(srt)
    if info["logo"]:
        proj["_logo"] = str(info["logo"])
    if voice or seconds:
        proj["do_dai"] = round(total, 2)
    return proj
