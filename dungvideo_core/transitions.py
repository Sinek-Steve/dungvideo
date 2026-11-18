"""Chuyển cảnh giữa hai cảnh A -> B (p chạy 0..1, điểm cắt ở p = 0.5).

  cat         : cắt thẳng
  mo          : mờ chồng (crossfade)
  flash       : chớp trắng
  zoom        : zoom xuyên (A phóng to nhoè -> B thu về), kiểu CapCut "zoom in"
  truot       : vuốt lên (whip) có nhoè chuyển động
  truot_ngang : vuốt ngang có nhoè
  vblur       : nhoè dọc mạnh rồi lộ cảnh mới (kiểu "vertical blur")
  glitch      : nhiễu RGB + xé lát ngang
"""
from __future__ import annotations

import random

import numpy as np

from .comp import motion_blur_h, motion_blur_v, zoom_frame
from .util import clamp, ease

DEFAULT_DUR = {"cat": 0.0, "mo": 0.4, "flash": 0.26, "zoom": 0.36, "truot": 0.34, "truot_ngang": 0.34,
               "vblur": 0.4, "glitch": 0.22}
NAMES = tuple(DEFAULT_DUR)


def _mix(a, b, k):
    return (a.astype(np.float32) * (1 - k) + b.astype(np.float32) * k).astype(np.uint8)


def apply(kind: str, A: np.ndarray, B: np.ndarray, p: float, frame_no: int = 0) -> np.ndarray:
    p = clamp(p)
    if kind == "mo":
        return _mix(A, B, ease("in_out_sine", p))
    if kind == "flash":
        if p < 0.5:
            k = ease("in_cubic", p / 0.5)
            return _mix(A, np.full_like(A, 255), k * 0.92)
        k = ease("out_cubic", (p - 0.5) / 0.5)
        return _mix(np.full_like(B, 255), B, 0.08 + 0.92 * k)
    if kind == "zoom":
        if p < 0.5:
            q = ease("in_cubic", p / 0.5)
            z = 1 + 0.9 * q
            f = zoom_frame(A, z)
            if q > 0.15:
                f = _mix(f, zoom_frame(A, z * (1 + 0.08 * q)), 0.5)
            return f
        q = ease("out_cubic", (p - 0.5) / 0.5)
        z = 1.9 - 0.9 * q
        f = zoom_frame(B, z)
        if q < 0.85:
            f = _mix(f, zoom_frame(B, z * (1 + 0.08 * (1 - q))), 0.5)
        return f
    if kind in ("truot", "truot_ngang"):
        H, W = A.shape[:2]
        q = ease("in_out_cubic", p)
        speed = np.sin(np.pi * p)
        if kind == "truot":
            off = int(q * H)
            out = np.empty_like(A)
            out[:H - off] = A[off:]
            out[H - off:] = B[:off]
            return motion_blur_v(out, 1 + 26 * speed)
        off = int(q * W)
        out = np.empty_like(A)
        out[:, :W - off] = A[:, off:]
        out[:, W - off:] = B[:, :off]
        return motion_blur_h(out, 1 + 26 * speed)
    if kind == "vblur":
        k = 1 + 45 * np.sin(np.pi * p)
        a = motion_blur_v(A, k)
        b = motion_blur_v(B, k)
        return _mix(a, b, ease("in_out_sine", clamp((p - 0.3) / 0.4)))
    if kind == "glitch":
        base = A if p < 0.5 else B
        amt = np.sin(np.pi * p)
        H, W = base.shape[:2]
        out = base.copy()
        dx = int(W * 0.03 * amt)
        if dx:
            out[..., 0] = np.roll(base[..., 0], dx, axis=1)
            out[..., 2] = np.roll(base[..., 2], -dx, axis=1)
        rnd = random.Random(frame_no)
        for _ in range(int(8 * amt) + 1):
            y0 = rnd.randrange(0, H)
            hh = rnd.randrange(max(2, H // 60), max(3, H // 14))
            sh = int(rnd.uniform(-0.12, 0.12) * W * amt)
            out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], sh, axis=1)
        return out
    return B if p >= 0.5 else A
