"""Mặt nạ (mask) hình học, khử răng cưa bằng hàm khoảng cách (SDF).

Mỗi hàm trả về alpha float32 (h, w) trong [0, 1] cho một ô (bbox) kích thước w×h,
hình được đặt ở giữa ô, có thể xoay (độ) và co giãn.
Các hình: rect (bo góc), circle, ellipse, diamond, polygon (lồi), cross (X), plus,
star, hexagon.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=64)
def _grid(w: int, h: int):
    xs = np.arange(w, dtype=np.float32) - (w - 1) / 2.0
    ys = np.arange(h, dtype=np.float32) - (h - 1) / 2.0
    return np.meshgrid(xs, ys)


def _rot(x, y, deg):
    if not deg:
        return x, y
    a = math.radians(-deg)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


def _sd_round_rect(x, y, hw, hh, r):
    r = min(r, hw, hh)
    qx = np.abs(x) - (hw - r)
    qy = np.abs(y) - (hh - r)
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    inside = np.minimum(np.maximum(qx, qy), 0)
    return outside + inside - r


def _sd_star5(x, y, r, rf=0.45):
    k1x, k1y = 0.809016994375, -0.587785252292
    k2x, k2y = -k1x, k1y
    px = np.abs(x)
    py = -y  # trục y hướng lên để ngôi sao chỉ lên trên
    d = np.maximum(k1x * px + k1y * py, 0)
    px, py = px - 2 * d * k1x, py - 2 * d * k1y
    d = np.maximum(k2x * px + k2y * py, 0)
    px, py = px - 2 * d * k2x, py - 2 * d * k2y
    px = np.abs(px)
    py = py - r
    bax, bay = rf * (-k1y), rf * k1x - 1
    hh = np.clip((px * bax + py * bay) / (bax * bax + bay * bay), 0, r)
    return np.hypot(px - bax * hh, py - bay * hh) * np.sign(py * bax - px * bay)


def _sd_hexagon(x, y, r):
    kx, ky, kz = -0.866025404, 0.5, 0.577350269
    px, py = np.abs(x), np.abs(y)
    d = np.minimum(kx * px + ky * py, 0)
    px, py = px - 2 * d * kx, py - 2 * d * ky
    px = px - np.clip(px, -kz * r, kz * r)
    py = py - r
    return np.hypot(px, py) * np.sign(py)


def _sd_convex_poly(x, y, pts):
    """pts: danh sách (x, y) theo pixel quanh tâm, thứ tự bất kỳ chiều (lồi)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sign = 1.0 if area > 0 else -1.0
    d = None
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        ln = math.hypot(ex, ey) or 1.0
        nx, ny = ey / ln * sign, -ex / ln * sign  # pháp tuyến hướng ra ngoài
        di = (x - x0) * nx + (y - y0) * ny
        d = di if d is None else np.maximum(d, di)
    return d


def shape_sdf(kind: str, x, y, sw: float, sh: float, radius: float = 0.0, pts=None):
    """sw, sh: kích thước hình (px). x, y: lưới toạ độ quanh tâm hình."""
    hw, hh = sw / 2.0, sh / 2.0
    if kind == "rect":
        return _sd_round_rect(x, y, hw, hh, radius)
    if kind == "circle":
        return np.hypot(x, y) - min(hw, hh)
    if kind == "ellipse":
        a, b = max(hw, 1e-3), max(hh, 1e-3)
        k = np.hypot(x / a, y / b)
        return (k - 1) * min(a, b)
    if kind == "diamond":
        a, b = max(hw, 1e-3), max(hh, 1e-3)
        return (np.abs(x) / a + np.abs(y) / b - 1) * (a * b / math.hypot(a, b))
    if kind == "cross":  # chữ X
        t = min(sw, sh) * 0.17
        L = math.hypot(sw, sh) / 2
        x1, y1 = _rot(x, y, 45)
        x2, y2 = _rot(x, y, -45)
        return np.minimum(_sd_round_rect(x1, y1, L, t, 0), _sd_round_rect(x2, y2, L, t, 0))
    if kind == "plus":
        t = min(sw, sh) * 0.17
        return np.minimum(_sd_round_rect(x, y, hw, t, 0), _sd_round_rect(x, y, t, hh, 0))
    if kind == "star":
        return _sd_star5(x, y, min(hw, hh))
    if kind == "hexagon":
        return _sd_hexagon(x, y, min(hw, hh) * 0.95)
    if kind == "polygon" and pts:
        return _sd_convex_poly(x, y, [(px * sw, py * sh) for px, py in pts])
    return _sd_round_rect(x, y, hw, hh, radius)


def shape_alpha(kind: str, bw: int, bh: int, sw: float, sh: float, rotation: float = 0.0,
                radius: float = 0.0, pts=None, feather: float = 1.0) -> np.ndarray:
    """Alpha (bh, bw) cho hình kích thước sw×sh đặt giữa ô bw×bh, xoay `rotation` độ."""
    gx, gy = _grid(int(bw), int(bh))
    x, y = _rot(gx, gy, rotation)
    d = shape_sdf(kind, x, y, sw, sh, radius, pts)
    f = max(feather, 0.75)
    return np.clip(0.5 - d / f, 0.0, 1.0).astype(np.float32)


def rotated_bbox(w: float, h: float, deg: float):
    if not deg:
        return w, h
    a = math.radians(deg)
    c, s = abs(math.cos(a)), abs(math.sin(a))
    return w * c + h * s, w * s + h * c


class MaskCache:
    """Cache mask tĩnh (khi panel đứng yên) để khỏi tính lại mỗi khung hình."""

    def __init__(self, cap: int = 96):
        self.cap = cap
        self.d: dict = {}

    def get(self, key, fn):
        v = self.d.get(key)
        if v is None:
            v = fn()
            if len(self.d) >= self.cap:
                self.d.pop(next(iter(self.d)))
            self.d[key] = v
        return v
