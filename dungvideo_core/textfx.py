"""Chữ: font tiếng Việt, xuống dòng, vẽ chữ có viền/bóng, thẻ nhãn."""
from __future__ import annotations

import os
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .util import FONT_DIR

FONT_FILES = {
    "title": ["Montserrat-Black.ttf"],
    "bold": ["Montserrat-ExtraBold.ttf"],
    "body": ["Montserrat-SemiBold.ttf"],
    "impact": ["Anton-Regular.ttf"],
}
FALLBACK = [
    "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def nfc(s) -> str:
    return unicodedata.normalize("NFC", str(s))


@lru_cache(maxsize=128)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    size = max(6, int(size))
    for name in FONT_FILES.get(kind, FONT_FILES["bold"]):
        p = FONT_DIR / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    for p in FALLBACK:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text_size(txt: str, f) -> tuple[int, int]:
    l, t, r, b = f.getbbox(txt)
    return r - l, b - t


def _wrap_greedy(words: list[str], f, max_w: int) -> list[str]:
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if text_size(cand, f)[0] <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def wrap(text: str, f, max_w: int) -> list[str]:
    """Xuống dòng cân: giữ số dòng như cách ngắt thường, nhưng chia các dòng dài gần bằng nhau
    (tránh 1 chữ lẻ rớt xuống dòng cuối)."""
    words = nfc(text).split()
    lines = _wrap_greedy(words, f, max_w)
    if len(lines) < 2:
        return lines
    # tìm bề rộng nhỏ nhất mà vẫn ra đúng số dòng đó
    lo, hi = 1, max_w
    while lo < hi:
        mid = (lo + hi) // 2
        if len(_wrap_greedy(words, f, mid)) <= len(lines):
            hi = mid
        else:
            lo = mid + 1
    return _wrap_greedy(words, f, lo)


def fit_font(text: str, kind: str, max_w: int, max_h: int, start: int, min_size: int = 18,
             max_lines: int = 4, spacing: float = 1.12):
    size = start
    while size > min_size:
        f = font(kind, size)
        lines = wrap(text, f, max_w)
        lh = f.size * spacing
        if len(lines) <= max_lines and lh * len(lines) <= max_h and all(text_size(l, f)[0] <= max_w for l in lines):
            return f, lines
        size = int(size * 0.92)
    f = font(kind, min_size)
    return f, wrap(text, f, max_w)


def text_rgba(text: str, f, fill=(255, 255, 255), stroke: int = 0, stroke_fill=(0, 0, 0),
              shadow: int = 0, align: str = "center", spacing: float = 1.12, lines=None) -> np.ndarray:
    """Vẽ khối chữ (nhiều dòng) ra mảng RGBA vừa khít."""
    lines = lines or nfc(text).split("\n")
    lh = int(f.size * spacing)
    widths = [text_size(l, f)[0] for l in lines]
    pad = stroke + shadow * 2 + 6
    W = max(widths + [1]) + pad * 2
    H = lh * len(lines) + pad * 2 + int(f.size * 0.25)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    asc = f.getbbox("ÁẤg")[1]
    for i, (l, lw) in enumerate(zip(lines, widths)):
        if align == "center":
            x = (W - lw) / 2
        elif align == "right":
            x = W - pad - lw
        else:
            x = pad
        y = pad + i * lh - asc + int(f.size * 0.08)
        d.text((x, y), l, font=f, fill=tuple(fill) + (255,), stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,))
    if shadow:
        a = img.split()[3].filter(ImageFilter.GaussianBlur(shadow))
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.75)))
        base = Image.new("RGBA", img.size, (0, 0, 0, 0))
        base.alpha_composite(sh, (int(shadow * 0.6), int(shadow * 0.9)))
        base.alpha_composite(img)
        img = base
    return np.asarray(img)


def chip_rgba(text: str, f, fg=(255, 255, 255), bg=(0, 0, 0), bg_alpha: int = 200,
              pad_x: float = 0.55, pad_y: float = 0.3, radius: float = 0.35) -> np.ndarray:
    """Thẻ nhãn bo góc có chữ (ví dụ: 'HPG +3,2%')."""
    text = nfc(text)
    tw, th = text_size(text, f)
    px, py = int(f.size * pad_x), int(f.size * pad_y)
    W, H = tw + px * 2, int(f.size * 1.0) + py * 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(H * radius), fill=tuple(bg) + (bg_alpha,))
    l, t, r, b = f.getbbox(text)
    d.text(((W - (r - l)) / 2 - l, (H - (b - t)) / 2 - t), text, font=f, fill=tuple(fg) + (255,))
    return np.asarray(img)


def chip_parts_rgba(parts, f, bg=(0, 0, 0), bg_alpha: int = 210, gap: float = 0.35) -> np.ndarray:
    """Thẻ nhiều đoạn màu khác nhau: parts = [(text, rgb), ...]."""
    parts = [(nfc(t), c) for t, c in parts if t]
    sizes = [text_size(t, f) for t, _ in parts]
    g = int(f.size * gap)
    px, py = int(f.size * 0.55), int(f.size * 0.3)
    W = sum(s[0] for s in sizes) + g * (len(parts) - 1) + px * 2
    H = int(f.size * 1.0) + py * 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(H * 0.35), fill=tuple(bg) + (bg_alpha,))
    x = px
    for (t, c), (tw, _) in zip(parts, sizes):
        l, tt, r, b = f.getbbox(t)
        d.text((x - l, (H - (b - tt)) / 2 - tt), t, font=f, fill=tuple(c) + (255,))
        x += tw + g
    return np.asarray(img)


def scale_rgba(rgba: np.ndarray, s: float) -> np.ndarray:
    if abs(s - 1) < 1e-3:
        return rgba
    h, w = rgba.shape[:2]
    nw, nh = max(1, int(w * s)), max(1, int(h * s))
    return np.asarray(Image.fromarray(rgba).resize((nw, nh), Image.BILINEAR))
