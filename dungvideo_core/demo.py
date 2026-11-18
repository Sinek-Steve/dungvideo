"""Tạo bộ media mẫu (ảnh, biểu đồ, clip, nhạc beat) để chạy thử tool khi chưa có tư liệu."""
from __future__ import annotations

import math
import random
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .textfx import font
from .util import ffmpeg_bin

PALETTES = [((15, 32, 75), (249, 115, 22)), ((6, 78, 59), (250, 204, 21)), ((76, 29, 149), (236, 72, 153)),
            ((12, 74, 110), (56, 189, 248)), ((127, 29, 29), (251, 146, 60)), ((17, 24, 39), (16, 185, 129))]


def _gradient(w, h, a, b, angle):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    ca, sa = math.cos(angle), math.sin(angle)
    t = (x / w * ca + y / h * sa)
    t = (t - t.min()) / (t.max() - t.min() + 1e-6)
    a, b = np.array(a, np.float32), np.array(b, np.float32)
    return (a + (b - a) * t[..., None]).astype(np.uint8)


def _scene_image(i, w=1080, h=1920):
    rnd = random.Random(i)
    a, b = PALETTES[i % len(PALETTES)]
    img = Image.fromarray(_gradient(w, h, a, b, rnd.uniform(0, math.pi)))
    d = ImageDraw.Draw(img, "RGBA")
    # "núi" nhiều lớp
    for layer in range(3):
        base = h * (0.55 + 0.12 * layer)
        pts = [(0, h)]
        for x in range(0, w + 60, 60):
            pts.append((x, base - 220 * (1 - layer * 0.3) * abs(math.sin(x / (170 + 40 * layer) + i + layer))))
        pts.append((w, h))
        shade = int(30 + 25 * layer)
        d.polygon(pts, fill=(shade, shade, shade + 15, 150 + layer * 30))
    # mặt trời
    r = rnd.randint(90, 170)
    cx, cy = rnd.randint(200, w - 200), rnd.randint(300, int(h * 0.42))
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - r * 2, cy - r * 2, cx + r * 2, cy + r * 2), fill=(255, 230, 160, 90))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(60)))
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 240, 200, 255))
    f = font("title", 120)
    txt = f"CẢNH {i + 1}"
    l, t, rr, bb = f.getbbox(txt)
    d.text(((w - (rr - l)) / 2, h * 0.8), txt, font=f, fill=(255, 255, 255, 230))
    return img.convert("RGB")


def _chart_image(seed, ticker, up=True, w=1080, h=1920):
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h), (11, 14, 20))
    d = ImageDraw.Draw(img)
    for y in range(300, h - 300, 140):
        d.line((80, y, w - 80, y), fill=(30, 36, 48), width=2)
    pts, v = [], 100.0
    n = 60
    for k in range(n):
        v += rnd.uniform(-2.2, 2.6 if up else 1.6) + (0.5 if up else -0.6)
        pts.append(v)
    lo, hi = min(pts), max(pts)
    xy = [(80 + k * (w - 160) / (n - 1), h - 380 - (p - lo) / (hi - lo + 1e-6) * (h - 900)) for k, p in enumerate(pts)]
    col = (22, 196, 90) if up else (239, 68, 68)
    poly = xy + [(xy[-1][0], h - 380), (xy[0][0], h - 380)]
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(over).polygon(poly, fill=col + (60,))
    img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    d = ImageDraw.Draw(img)
    d.line(xy, fill=col, width=8, joint="curve")
    f = font("title", 150)
    d.text((80, 120), ticker, font=f, fill=(255, 255, 255))
    pct = (pts[-1] - pts[0]) / pts[0] * 100
    d.text((80, 300), f"{pct:+.1f}%".replace(".", ","), font=font("bold", 90), fill=col)
    return img


def _music(path: Path, seconds=34.0, bpm=120, sr=44100):
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n, np.float32)
    beat = 60 / bpm
    drop = beat * 16  # 8 giây đầu là đoạn dạo (build-up)
    rnd = np.random.default_rng(1)
    for k in range(int(seconds / beat) + 1):
        b0 = k * beat
        i0 = int(b0 * sr)
        if b0 >= drop or k % 4 == 0:
            L = int(0.25 * sr)
            tt = np.arange(min(L, n - i0)) / sr
            kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 9)
            out[i0:i0 + len(tt)] += 0.9 * kick
        # hi-hat nửa nhịp
        for off in (0.5,):
            j0 = int((b0 + beat * off) * sr)
            L = int(0.05 * sr)
            if j0 + L < n:
                out[j0:j0 + L] += 0.18 * rnd.standard_normal(L) * np.exp(-np.arange(L) / sr * 80)
        if b0 >= drop and k % 2 == 1:  # clap
            L = int(0.12 * sr)
            if i0 + L < n:
                out[i0:i0 + L] += 0.35 * rnd.standard_normal(L) * np.exp(-np.arange(L) / sr * 25)
    # bass + pad
    notes = [55, 55, 65.4, 49]
    for k in range(int(seconds / (beat * 4)) + 1):
        f0 = notes[k % 4]
        i0 = int(k * beat * 4 * sr)
        L = min(int(beat * 4 * sr), n - i0)
        if L <= 0:
            break
        tt = np.arange(L) / sr
        pad = 0.08 * (np.sin(2 * np.pi * f0 * 4 * tt) + 0.6 * np.sin(2 * np.pi * f0 * 5 * tt) + 0.5 * np.sin(2 * np.pi * f0 * 6 * tt))
        out[i0:i0 + L] += pad * np.minimum(1, tt * 4)
        if k * beat * 4 >= drop:
            out[i0:i0 + L] += 0.3 * np.sign(np.sin(2 * np.pi * f0 * tt)) * 0.5 * (np.sin(2 * np.pi * tt / beat) > -0.2)
    rise = (t < drop) * (t / drop) * 0.15 * rnd.standard_normal(n)
    out += rise.astype(np.float32)
    out /= np.max(np.abs(out)) + 1e-6
    out *= 0.85
    pcm = (out * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def make_demo(folder: Path) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    print(f"Đang tạo media mẫu trong {folder} ...")
    k = 1
    tickers = [("DEMO1", True), ("DEMO2", False), ("DEMO3", True), ("DEMO4", True)]
    for i in range(10):
        _scene_image(i).save(folder / f"{k:02d}_canh.jpg", quality=90)
        k += 1
        if i in (2, 5, 7, 8):
            tk, up = tickers[[2, 5, 7, 8].index(i)]
            _chart_image(i, tk, up).save(folder / f"{k:02d}_bieu_do_{tk}.png")
            k += 1
    try:
        subprocess.run([ffmpeg_bin(), "-y", "-v", "error", "-f", "lavfi", "-i",
                        "gradients=s=720x1280:c0=0x1e3a8a:c1=0xf97316:c2=0x10b981:speed=0.03:d=5:r=30",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                        str(folder / f"{k:02d}_clip.mp4")], check=True)
    except Exception:
        pass
    _music(folder / "nhac_beat.wav")
    (folder / "chu.txt").write_text(
        "# Dòng đầu = tiêu đề. Dòng 'SỐ: ...' = chú thích cho file bắt đầu bằng số đó.\n"
        "# Dòng không có số = chú thích lần lượt cho các cảnh toàn màn hình còn lại.\n"
        "Video mẫu: chỉ số vượt mốc 1.300 điểm\n"
        "04: DEMO1 +6,9% | Chú thích riêng cho file số 04\n"
        "08: DEMO2 -1,2% | Mã giảm tự hiện màu đỏ\n"
        "12: DEMO3 +3,4% | Mã tăng tự hiện màu xanh\n"
        "Dòng chú thích chung thứ nhất\n"
        "Dòng chú thích chung thứ hai\n",
        encoding="utf-8")
    return folder
