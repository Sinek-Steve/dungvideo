"""Tiện ích chung: easing, tìm ffmpeg, đọc màu, in tiến độ."""
from __future__ import annotations

import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "fonts"

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VID_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUD_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def setup_console() -> None:
    """Cho phép in tiếng Việt trên console Windows."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _find_bin(name: str) -> str:
    exe = name + (".exe" if os.name == "nt" else "")
    env = os.environ.get(name.upper())
    if env and Path(env).exists():
        return env
    for cand in (ROOT / "ffmpeg" / "bin" / exe, ROOT / "ffmpeg" / exe, ROOT / exe):
        if cand.exists():
            return str(cand)
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit(
        f"Không tìm thấy {name}. Cài bằng lệnh: winget install Gyan.FFmpeg "
        f"(hoặc chép thư mục ffmpeg có bin/{exe} vào thư mục tool)."
    )


def ffmpeg_bin() -> str:
    return _find_bin("ffmpeg")


def ffprobe_bin() -> str:
    return _find_bin("ffprobe")


# ---------------------------------------------------------------- easing
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def ease(name: str, p: float) -> float:
    p = clamp(p)
    if name == "linear":
        return p
    if name == "in_cubic":
        return p * p * p
    if name == "out_cubic":
        return 1 - (1 - p) ** 3
    if name == "in_out_cubic":
        return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    if name == "out_back":
        c1, c3 = 1.70158, 2.70158
        return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
    if name == "out_expo":
        return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)
    if name == "in_out_sine":
        return -(math.cos(math.pi * p) - 1) / 2
    return p


def lerp(a: float, b: float, p: float) -> float:
    return a + (b - a) * p


# ---------------------------------------------------------------- màu
NAMED = {
    "den": (10, 10, 14),
    "trang": (245, 245, 245),
    "do": (214, 36, 44),
    "xanh": (14, 32, 72),
    "xanh_la": (22, 163, 74),
    "vang": (255, 212, 0),
    "cam": (255, 122, 0),
    "tim": (88, 40, 140),
}


def color(c, default=(255, 255, 255)) -> tuple:
    if c is None:
        return default
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        return tuple(int(v) for v in c[:3])
    s = str(c).strip().lower()
    if s in NAMED:
        return NAMED[s]
    s = s.lstrip("#")
    if len(s) == 6:
        try:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return default


class Progress:
    def __init__(self, total: int, label: str = "Đang dựng"):
        import time
        self.total = max(1, total)
        self.label = label
        self.t0 = time.time()
        self.last = -1

    def update(self, n: int) -> None:
        import time
        pct = int(n * 100 / self.total)
        if pct == self.last:
            return
        self.last = pct
        el = time.time() - self.t0
        eta = el / max(n, 1) * (self.total - n)
        sys.stdout.write(f"\r{self.label}: {pct:3d}%  (còn ~{int(eta)}s)   ")
        sys.stdout.flush()

    def done(self) -> None:
        import time
        sys.stdout.write(f"\r{self.label}: 100%  xong sau {time.time() - self.t0:.0f}s        \n")
        sys.stdout.flush()
