"""Ghép lớp (compositing) lên canvas float32."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter


def _clip(x, y, w, h, W, H):
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1, x0 - x, y0 - y


def blend(canvas: np.ndarray, content: np.ndarray, alpha, x: int, y: int, opacity: float = 1.0) -> None:
    """Đè `content` (h,w,3) lên canvas tại (x,y) với alpha (h,w) hoặc None (đặc)."""
    H, W = canvas.shape[:2]
    h, w = content.shape[:2]
    r = _clip(int(x), int(y), w, h, W, H)
    if r is None or opacity <= 0.003:
        return
    x0, y0, x1, y1, ox, oy = r
    c = content[oy:oy + (y1 - y0), ox:ox + (x1 - x0)].astype(np.float32)
    dst = canvas[y0:y1, x0:x1]
    if alpha is None and opacity >= 0.999:
        dst[...] = c
        return
    if alpha is None:
        a = opacity
        dst *= (1 - a)
        dst += c * a
        return
    a = alpha[oy:oy + (y1 - y0), ox:ox + (x1 - x0)]
    if opacity < 0.999:
        a = a * opacity
    a = a[..., None]
    dst -= (dst - c) * a


def blend_rgba(canvas: np.ndarray, rgba: np.ndarray, x: int, y: int, opacity: float = 1.0) -> None:
    a = rgba[..., 3].astype(np.float32) / 255.0
    blend(canvas, rgba[..., :3], a, x, y, opacity)


def blend_solid(canvas: np.ndarray, rgb, alpha: np.ndarray, x: int, y: int, opacity: float = 1.0) -> None:
    h, w = alpha.shape
    content = np.empty((h, w, 3), np.float32)
    content[...] = np.array(rgb, np.float32)
    blend(canvas, content, alpha, x, y, opacity)


def fill(canvas: np.ndarray, rgb) -> None:
    canvas[...] = np.array(rgb, np.float32)


def vertical_gradient(W: int, H: int, top, bottom) -> np.ndarray:
    t = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    a = np.array(top, np.float32)[None, None, :]
    b = np.array(bottom, np.float32)[None, None, :]
    g = a + (b - a) * t
    return np.broadcast_to(g, (H, W, 3)).copy()


def blur_dark(arr: np.ndarray, W: int, H: int, dark: float = 0.45) -> np.ndarray:
    """Nền mờ tối từ một khung hình (dùng cho nền thẻ tiêu đề / kết)."""
    im = Image.fromarray(arr).resize((max(8, W // 8), max(8, H // 8)), Image.BILINEAR)
    im = im.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
    return np.asarray(im).astype(np.float32) * (1 - dark)


def vignette_map(W: int, H: int, strength: float) -> np.ndarray | None:
    if strength <= 0:
        return None
    y, x = np.ogrid[:H, :W]
    nx = (x - W / 2) / (W / 2)
    ny = (y - H / 2) / (H / 2)
    d = np.sqrt(nx * nx * 0.9 + ny * ny * 0.6)
    m = 1 - strength * np.clip(d - 0.35, 0, None) ** 1.6
    return np.clip(m, 0, 1).astype(np.float32)[..., None]


def zoom_frame(arr: np.ndarray, z: float, cx: float = 0.5, cy: float = 0.5) -> np.ndarray:
    """Phóng to khung hình quanh tâm (cx, cy)."""
    if abs(z - 1) < 1e-3:
        return arr
    H, W = arr.shape[:2]
    if z < 1:
        # thu nhỏ: đặt vào giữa nền đen
        im = Image.fromarray(arr).resize((max(2, int(W * z)), max(2, int(H * z))), Image.BILINEAR)
        out = np.zeros_like(arr)
        x, y = (W - im.width) // 2, (H - im.height) // 2
        out[y:y + im.height, x:x + im.width] = np.asarray(im)
        return out
    bw, bh = W / z, H / z
    left = min(max((W - bw) * cx, 0), W - bw)
    top = min(max((H - bh) * cy, 0), H - bh)
    return np.asarray(Image.fromarray(arr).resize((W, H), Image.BILINEAR, box=(left, top, left + bw, top + bh)))


def motion_blur_v(arr: np.ndarray, k: float) -> np.ndarray:
    """Nhoè dọc nhanh (thu nhỏ theo chiều dọc rồi phóng lại)."""
    if k <= 1.05:
        return arr
    H, W = arr.shape[:2]
    im = Image.fromarray(arr).resize((W, max(2, int(H / k))), Image.BILINEAR).resize((W, H), Image.BILINEAR)
    return np.asarray(im)


def motion_blur_h(arr: np.ndarray, k: float) -> np.ndarray:
    if k <= 1.05:
        return arr
    H, W = arr.shape[:2]
    im = Image.fromarray(arr).resize((max(2, int(W / k)), H), Image.BILINEAR).resize((W, H), Image.BILINEAR)
    return np.asarray(im)


def to_uint8(canvas: np.ndarray) -> np.ndarray:
    return np.clip(canvas, 0, 255).astype(np.uint8)
