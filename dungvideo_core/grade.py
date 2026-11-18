"""Chỉnh màu (color grade) cho ảnh/clip — áp lên media, không áp lên chữ.

Các kiểu:
  dien_anh : tông cam–xanh ngọc kiểu phim (teal & orange), tương phản nhẹ
  sang     : sáng, trong, tươi
  lanh     : hơi lạnh, hợp chủ đề tài chính/công nghệ
  am       : ấm, vàng nhẹ
  tu_nhien : giữ nguyên
"""
from __future__ import annotations

import numpy as np

PRESETS = ("dien_anh", "sang", "lanh", "am", "tu_nhien")


def _smoothstep(x):
    return x * x * (3 - 2 * x)


def make_grade(name: str | None):
    """Trả về hàm f(arr_uint8 HxWx3) -> arr_uint8, hoặc None nếu không chỉnh."""
    if not name or name in ("tu_nhien", "none", "khong"):
        return None
    x = np.linspace(0, 1, 256, dtype=np.float32)
    sat = 1.0
    if name == "dien_anh":
        y = x + (_smoothstep(x) - x) * 0.45           # tương phản S-curve
        sh, hi = (1 - x) ** 2, x ** 2                  # trọng số vùng tối / sáng
        r = y - 0.045 * sh + 0.065 * hi
        g = y + 0.012 * sh + 0.012 * hi
        b = y + 0.065 * sh - 0.075 * hi
        sat = 1.12
    elif name == "sang":
        y = x ** 0.9
        y = y + (_smoothstep(y) - y) * 0.2
        r, g, b = y, y, y
        sat = 1.15
    elif name == "lanh":
        y = x + (_smoothstep(x) - x) * 0.3
        r, g, b = y - 0.02, y + 0.005, y + 0.04
        sat = 1.05
    elif name == "am":
        y = x + (_smoothstep(x) - x) * 0.25
        r, g, b = y + 0.045, y + 0.01, y - 0.045
        sat = 1.08
    else:
        return None
    luts = [np.clip(c * 255 + 0.5, 0, 255).astype(np.uint8) for c in (r, g, b)]

    def apply(arr: np.ndarray) -> np.ndarray:
        out = np.empty_like(arr)
        for i in range(3):
            out[..., i] = luts[i][arr[..., i]]
        if sat != 1.0:
            f = out.astype(np.float32)
            gray = f @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
            f = gray[..., None] + (f - gray[..., None]) * sat
            out = np.clip(f, 0, 255).astype(np.uint8)
        return out

    return apply
