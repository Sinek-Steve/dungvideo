"""Gói hiệu ứng vào cảnh kiểu CapCut, áp vào vài khung hình đầu sau một cú cắt
(KIEN_THUC_CAPCUT.md mục 3): punch (phóng rồi thu Cubic Out), rung, nhoè tan dần, chớp màu."""
from __future__ import annotations

import math

import numpy as np

from .util import clamp, ease

FX_NAMES = ("punch", "rung", "nhoe", "chop")
FX_DUR = {"punch": 0.22, "rung": 0.18, "nhoe": 0.22, "chop": 0.1}


def camera(name: str | None, t_in: float, seed: int = 0):
    """Tham số lấy khung hình (zoom, cx, cy) cho hiệu ứng tại thời điểm t_in sau cú cắt."""
    if not name or t_in >= FX_DUR.get(name, 0):
        return 1.0, 0.5, 0.5
    p = t_in / FX_DUR[name]
    if name == "punch":
        return 1.0 + 0.18 * (1 - ease("out_cubic", p)), 0.5, 0.5
    if name == "rung":
        k = int(t_in * 60) + seed  # đổi hướng mỗi khung
        a = 0.5 * (1 - p)
        return 1.08, 0.5 + a * math.sin(k * 2.3), 0.5 + a * math.cos(k * 1.7)
    return 1.0, 0.5, 0.5


def post(name: str | None, canvas: np.ndarray, t_in: float, angle: float = 90.0) -> np.ndarray:
    """Hiệu ứng vẽ đè sau khi đã có khung hình: nhoè hướng tan dần, chớp sáng."""
    if not name or t_in >= FX_DUR.get(name, 0):
        return canvas
    p = t_in / FX_DUR[name]
    if name == "nhoe":
        spread = canvas.shape[0] * 0.07 * (1 - ease("out_cubic", p))
        return directional_blur(canvas, spread, angle)
    if name == "chop":
        canvas += 150.0 * clamp(1 - p)
    return canvas


def directional_blur(arr: np.ndarray, spread: float, angle: float = 90.0, taps: int = 7) -> np.ndarray:
    """Nhoè theo một hướng (90 = dọc, kiểu "Vertical blur"; 70 = xiên), mép ảnh kéo dài thay vì cuộn vòng."""
    if spread < 1.0:
        return arr
    H, W = arr.shape[:2]
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    out = np.zeros_like(arr, dtype=np.float32)
    rows0, cols0 = np.arange(H), np.arange(W)
    for o in np.linspace(-spread / 2, spread / 2, taps):
        dy, dx = int(round(o * uy)), int(round(o * ux))
        rows = np.clip(rows0 - dy, 0, H - 1)
        cols = np.clip(cols0 - dx, 0, W - 1)
        out += arr[rows][:, cols] if dx else arr[rows]
    out /= taps
    return out
