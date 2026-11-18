"""Các loại cảnh (scene). Mỗi cảnh trả về khung hình uint8 (H, W, 3) tại thời điểm cục bộ t.

Loại cảnh (khóa `loai` trong file dự án):
  day_du    : một clip/ảnh toàn màn hình, zoom chậm + nhún theo beat, chữ chú thích
  chia      : chia màn hình bằng mask: doc | ngang | cheo | tron | thoi | vien | the
  luoi      : lưới ảnh 3x3, ô giữa là tiêu đề, zoom-out lộ cả lưới
  hinh_mo   : lộ cảnh mới qua hình nở ra: tron | thoi | sao | x | luc_giac | chu_nhat
  tieu_de   : chữ động từng từ (kinetic typography) trên nền màu / ảnh mờ
  flash     : trình chiếu chớp nhanh (mỗi ảnh ~0,3s, mờ dần vào + zoom ra)
  so_sanh   : so sánh 2–3 ảnh/biểu đồ chồng dọc, có nhãn mã & % tăng giảm
  ket       : màn kết: handle, lời kêu gọi theo dõi, nút nhấp nháy theo beat
  nhay      : dồn cắt theo từng nốt nhạc (mỗi nốt 1 clip, cắt thẳng, không nhún), có thể kèm dải ngang mở dần
  rap_hinh  : ráp hình: cùng một clip lộ ra qua các mảnh mask nở lần lượt theo nốt nhạc rồi ráp kín khung
  tuong_anh : tường ảnh: lưới ô mỗi ô một clip, cả lưới cùng đổi hình theo nhịp
  nghi_den  : khoảng nghỉ màn hình đen (có thể kèm chữ)
"""
from __future__ import annotations

import math
import random

import numpy as np

from . import fx as FX
from .comp import blend, blend_rgba, blend_solid, blur_dark, to_uint8, vertical_gradient, zoom_frame
from .masks import rotated_bbox, shape_alpha
from .textfx import chip_parts_rgba, chip_rgba, fit_font, font, nfc, scale_rgba, text_rgba, text_size
from .util import clamp, color, ease, lerp

GREEN = (22, 196, 90)
RED = (239, 68, 68)
YELLOW = (255, 212, 0)


class Ctx:
    def __init__(self, W, H, fps, pool, beats, brand, music_beats: bool, mcache):
        self.W, self.H, self.fps = W, H, fps
        self.pool = pool
        self.beats = beats
        self.brand = brand or {}
        self.music_beats = music_beats
        self.mcache = mcache
        self.s = W / 1080.0
        self.text_cache: dict = {}

    def bg(self):
        if not hasattr(self, "_bg"):
            self._bg = vertical_gradient(self.W, self.H, (18, 18, 26), (4, 4, 8))
        return self._bg.copy()


# ------------------------------------------------------------------ Panel
class Panel:
    def __init__(self, media, cx, cy, w, h, shape="rect", radius=0.0, rotation=0.0, pts=None,
                 enter="none", t0=0.0, d=0.45, direction=(0, 1), dist=None, easing="out_cubic",
                 kb=(1.0, 1.05), shadow=False, media_t0=0.0, cxy=(0.5, 0.5)):
        self.media = media
        self.cx, self.cy, self.w, self.h = cx, cy, w, h
        self.shape, self.radius, self.rotation, self.pts = shape, radius, rotation, pts
        self.enter, self.t0, self.d = enter, t0, d
        self.direction, self.dist, self.easing = direction, dist, easing
        self.kb, self.shadow, self.media_t0 = kb, shadow, media_t0
        self.cxy = cxy

    def draw(self, canvas, ctx: Ctx, t: float, dur: float, extra_zoom: float = 1.0):
        p = 1.0
        if self.enter != "none":
            if t < self.t0 and self.enter in ("pop", "reveal", "fade"):
                return
            p = ease(self.easing, (t - self.t0) / max(self.d, 1e-3))
        s, dx, dy, op, reveal = 1.0, 0.0, 0.0, 1.0, 1.0
        if self.enter == "slide":
            dist = self.dist or (ctx.W if self.direction[0] else ctx.H)
            dx = (1 - p) * self.direction[0] * dist
            dy = (1 - p) * self.direction[1] * dist
        elif self.enter == "pop":
            s = max(p, 0.02)
        elif self.enter == "reveal":
            reveal = max(p, 0.0)
        elif self.enter == "fade":
            op = p
        if reveal <= 0.003:
            return
        sw, sh = self.w * s, self.h * s
        bw, bh = rotated_bbox(sw, sh, self.rotation)
        bw, bh = int(math.ceil(bw)) + 2, int(math.ceil(bh)) + 2
        if bw < 3 or bh < 3:
            return
        x = int(round(self.cx + dx - bw / 2))
        y = int(round(self.cy + dy - bh / 2))
        if x >= ctx.W or y >= ctx.H or x + bw <= 0 or y + bh <= 0:
            return
        z = lerp(self.kb[0], self.kb[1], clamp(t / max(dur, 1e-3))) * extra_zoom
        frame = self.media.frame(max(t, 0) + self.media_t0, bw, bh, zoom=z, cx=self.cxy[0], cy=self.cxy[1]) \
            if self.media is not None else np.full((bh, bw, 3), 30, np.uint8)
        simple = self.shape == "rect" and self.radius <= 0 and not self.rotation and reveal >= 0.999
        alpha = None
        if not simple:
            msw, msh = sw * reveal, sh * reveal
            key = (self.shape, bw, bh, round(msw, 1), round(msh, 1), round(self.rotation, 2),
                   round(self.radius * s * reveal, 1), id(self.pts) if self.pts else 0)
            alpha = ctx.mcache.get(key, lambda: shape_alpha(
                self.shape, bw, bh, msw, msh, self.rotation, self.radius * s * reveal, self.pts))
        if self.shadow and op > 0.05:
            sa = alpha if alpha is not None else np.ones((bh, bw), np.float32)
            off = int(14 * ctx.s)
            blend_solid(canvas, (0, 0, 0), sa, x + off, y + int(off * 1.4), 0.45 * op)
        blend(canvas, frame, alpha, x, y, op)


# ------------------------------------------------------------------ helpers
def _cached(ctx: Ctx, key, fn):
    v = ctx.text_cache.get(key)
    if v is None:
        v = fn()
        ctx.text_cache[key] = v
    return v


def draw_center_title(canvas, ctx: Ctx, text: str, t: float, pos: str = "giua", kind: str = "title",
                      size_rel: float = 0.105, appear: float = 0.12, sub: str | None = None):
    if not text:
        return
    W, H = ctx.W, ctx.H

    def make():
        f, lines = fit_font(text.upper() if kind == "impact" else text, kind, int(W * 0.86), int(H * 0.3),
                            int(W * size_rel))
        return text_rgba("", f, (255, 255, 255), stroke=0, shadow=max(2, int(10 * ctx.s)), lines=lines)

    img = _cached(ctx, ("ctitle", text, kind, size_rel, W), make)
    p = ease("out_back", (t - appear) / 0.35)
    if t < appear:
        return
    sc = lerp(0.82, 1.0, p)
    im = scale_rgba(img, sc)
    h, w = im.shape[:2]
    cy = {"tren": 0.2, "giua": 0.5, "duoi": 0.74}.get(pos, 0.5) * H
    blend_rgba(canvas, im, int(W / 2 - w / 2), int(cy - h / 2), clamp(p * 1.4))
    if sub:
        sub_img = _cached(ctx, ("csub", sub, W), lambda: text_rgba(
            sub, font("body", int(W * 0.036)), (235, 235, 235), shadow=max(2, int(6 * ctx.s))))
        sh, sw_ = sub_img.shape[:2]
        p2 = ease("out_cubic", (t - appear - 0.2) / 0.3)
        blend_rgba(canvas, sub_img, int(W / 2 - sw_ / 2), int(cy + h / 2 - 4 * ctx.s + (1 - p2) * 20 * ctx.s), p2)


def value_color(v: str):
    s = str(v).strip()
    if s.startswith("+") or s.startswith("▲"):
        return GREEN
    if s.startswith("-") or s.startswith("−") or s.startswith("▼"):
        return RED
    return YELLOW


# ------------------------------------------------------------------ Scene base
class Scene:
    kind = "base"

    def __init__(self, cfg: dict, ctx: Ctx, start: float, dur: float):
        self.cfg, self.ctx, self.start, self.dur = cfg, ctx, start, dur
        m = cfg.get("media") or []
        if isinstance(m, (str, dict)):
            m = [m]
        self.medias = [ctx.pool.get(x) for x in m]
        b = ctx.beats.beats if ctx.beats is not None else np.zeros(0)
        self.lbeats = [float(x - start) for x in b if start - 1e-3 <= x < start + dur - 1e-3]
        self.hide_frame = bool(cfg.get("an_khung", False))
        self.seed = int(cfg.get("hat_giong", 0)) + int(start * 1000)

    def media(self, i: int):
        if not self.medias:
            return None
        return self.medias[i % len(self.medias)]

    def render(self, t: float) -> np.ndarray:
        t = clamp(t, 0.0, self.dur)
        canvas = self.draw(t)
        return to_uint8(canvas)

    def draw(self, t: float) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def sfx(self) -> list:
        """Tiếng động của cảnh: [(giây trong cảnh, tên file trong tieng_dong/, âm lượng)]."""
        return []

    def punch(self, t: float, amp: float = 0.055, decay: float = 0.13) -> float:
        if not self.ctx.music_beats or not self.lbeats:
            return 1.0
        last = None
        for b in self.lbeats:
            if b <= t:
                last = b
            else:
                break
        if last is None or last < 0.05:
            return 1.0
        return 1.0 + amp * math.exp(-(t - last) / decay)


# ------------------------------------------------------------------ day_du
class FullScene(Scene):
    kind = "day_du"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        z = cfg.get("zoom", "vao")
        self.kb = {"vao": (1.0, 1.1), "ra": (1.12, 1.0), "khong": (1.0, 1.0)}.get(z, (1.0, 1.08))
        self.do_punch = cfg.get("nhun", True)

    def draw(self, t):
        ctx = self.ctx
        z = lerp(self.kb[0], self.kb[1], ease("in_out_sine", t / max(self.dur, 1e-3)))
        if self.do_punch:
            z *= self.punch(t)
        m = self.media(0)
        canvas = ctx.bg() if m is None else m.frame(t, ctx.W, ctx.H, zoom=z).astype(np.float32)
        box = self._caption(canvas, t)
        self._label(canvas, t, box)
        return canvas

    def _caption(self, canvas, t):
        txt = self.cfg.get("chu")
        if not txt:
            return None
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        pos = self.cfg.get("vi_tri", "duoi")
        if pos == "giua":
            draw_center_title(canvas, ctx, txt, t, "giua")
            return None

        def make():
            f, lines = fit_font(txt, "bold", int(W * 0.8), int(H * 0.2), int(W * 0.062), max_lines=3)
            core = text_rgba("", f, (255, 255, 255), lines=lines, spacing=1.15)
            h, w = core.shape[:2]
            px, py = int(W * 0.035), int(W * 0.022)
            from PIL import Image, ImageDraw
            box = Image.new("RGBA", (w + px * 2, h + py * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(box)
            d.rounded_rectangle((0, 0, box.width - 1, box.height - 1), radius=int(W * 0.03), fill=(8, 8, 12, 190))
            acc = color(self.cfg.get("mau_nhan"), YELLOW)
            d.rounded_rectangle((0, 0, int(W * 0.012), box.height - 1), radius=int(W * 0.006), fill=acc + (255,))
            box.alpha_composite(Image.fromarray(core), (px, py))
            return np.asarray(box)

        img = _cached(ctx, ("cap", txt, W, self.cfg.get("mau_nhan")), make)
        h, w = img.shape[:2]
        cy = {"tren": 0.24}.get(pos, 0.6) * H
        x0, y0 = int(W / 2 - w / 2), int(cy - h / 2)
        p = ease("out_cubic", (t - 0.12) / 0.3)
        if p > 0:
            blend_rgba(canvas, img, x0, int(y0 + (1 - p) * 40 * ctx.s), p)
        return (x0, y0, w, h)

    def _label(self, canvas, t, box=None):
        """Thẻ mã + % đặt ngay trên khung chú thích (hoặc ở 1/3 dưới nếu không có chú thích)."""
        lab = self.cfg.get("nhan")
        val = self.cfg.get("chi_so")
        if not lab and not val:
            return
        ctx = self.ctx
        f = font("bold", int(ctx.W * 0.05))
        img = _cached(ctx, ("lab", lab, val, ctx.W), lambda: chip_parts_rgba(
            [(str(lab or ""), (255, 255, 255)), (str(val or ""), value_color(val or ""))], f, bg=(10, 10, 14)))
        p = ease("out_back", (t - 0.05) / 0.35)
        if p <= 0:
            return
        im = scale_rgba(img, max(p, 0.05))
        h, w = img.shape[:2]
        if box is not None and box[1] > ctx.H * 0.4:
            x, y = box[0], box[1] - h - int(14 * ctx.s)
        else:
            x, y = int(ctx.W * 0.07), int(ctx.H * 0.66)
        blend_rgba(canvas, im, x, y + (h - im.shape[0]) // 2, clamp(p))


# ------------------------------------------------------------------ chia
class SplitScene(Scene):
    kind = "chia"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        self.style = cfg.get("kieu", "ngang")
        n = int(cfg.get("so", 0) or len(self.medias) or 3)
        self.n = max(1, min(n, 7))
        self.panels = self._layout()

    def _layout(self):
        ctx, n, st = self.ctx, self.n, self.style
        W, H, s = ctx.W, ctx.H, ctx.s
        g = float(self.cfg.get("khe", 10)) * s
        enter_d = min(0.5, self.dur * 0.45)
        stagger = min(0.12, self.dur * 0.35 / max(n, 1))
        P = []
        if st == "doc":
            w = (W - g * (n - 1)) / n
            for i in range(n):
                P.append(Panel(self.media(i), i * (w + g) + w / 2, H / 2, w, H, enter="slide",
                               t0=i * stagger, d=enter_d, direction=(0, 1 if i % 2 else -1)))
        elif st == "ngang":
            h = (H - g * (n - 1)) / n
            for i in range(n):
                P.append(Panel(self.media(i), W / 2, i * (h + g) + h / 2, W, h, enter="slide",
                               t0=i * stagger, d=enter_d, direction=(1 if i % 2 else -1, 0)))
        elif st == "cheo":
            ang = math.radians(float(self.cfg.get("goc", 16)))
            off = W / 2 * math.tan(ang)
            bh = H / n
            for i in range(n):
                y0 = i * bh + (g / 2 if i else -off * 2)
                y1 = (i + 1) * bh - (g / 2 if i < n - 1 else -off * 2)
                pts_c = [(0, y0 + off), (W, y0 - off), (W, y1 - off), (0, y1 + off)]
                top, bot = y0 - off, y1 + off
                cy, hh = (top + bot) / 2, bot - top
                pts = [((px - W / 2) / W, (py - cy) / hh) for px, py in pts_c]
                P.append(Panel(self.media(i), W / 2, cy, W, hh, shape="polygon", pts=pts, enter="slide",
                               t0=i * stagger, d=enter_d, direction=(1 if i % 2 else -1, 0), dist=W * 1.15))
        elif st == "tron":
            if n == 1:
                d = W * 0.8
                P.append(Panel(self.media(0), W / 2, H / 2, d, d, shape="circle", enter="pop",
                               d=enter_d, easing="out_back", shadow=True))
            else:
                d = min(W * 0.66, H * 0.88 / (n * 0.8 + 0.2))
                step = d * 0.8
                total = step * (n - 1)
                for i in range(n):
                    cx = W / 2 + (W * 0.14 if i % 2 else -W * 0.14)
                    cy = H / 2 - total / 2 + i * step
                    P.append(Panel(self.media(i), cx, cy, d, d, shape="circle", enter="pop", t0=i * stagger,
                                   d=enter_d, easing="out_back", shadow=True))
        elif st == "thoi":
            d = min(W * 0.82, H * 0.92 / (n * 0.6 + 0.4))
            step = d * 0.6
            total = step * (n - 1)
            for i in range(n):
                cx = W / 2 + ((W * 0.16 if i % 2 else -W * 0.16) if n > 1 else 0)
                cy = H / 2 - total / 2 + i * step
                P.append(Panel(self.media(i), cx, cy, d, d, shape="diamond", enter="pop", t0=i * stagger,
                               d=enter_d, easing="out_back", shadow=True))
        elif st == "vien":
            gg = W * 0.03
            pw = (W - gg * (n + 1)) / n
            hs = [0.62, 0.8, 0.7, 0.86, 0.66, 0.76, 0.72]
            oy = [0.0, -0.035, 0.03, -0.02, 0.04, -0.03, 0.02]
            for i in range(n):
                ph = H * hs[i % 7] * (0.92 if n <= 3 else 1.0)
                P.append(Panel(self.media(i), gg + i * (pw + gg) + pw / 2, H / 2 + oy[i % 7] * H, pw, ph,
                               radius=pw / 2, enter="slide", t0=i * stagger, d=enter_d, direction=(0, 1),
                               dist=H, shadow=True))
        elif st == "the":
            n = min(n, 4)
            cw = W * 0.84
            ch = min(cw * 0.66, H * 0.86 / n - g * 2)
            step = H * 0.86 / n
            rots = [-5, 4, -3, 5]
            for i in range(n):
                cy = H * 0.07 + step * i + step / 2
                P.append(Panel(self.media(i), W / 2, cy, cw, ch, radius=W * 0.045, rotation=rots[i % 4],
                               enter="slide", t0=i * stagger, d=enter_d, direction=(1 if i % 2 else -1, 0),
                               dist=W * 1.2, shadow=True))
        else:
            raise SystemExit(f"Kiểu chia không hợp lệ: {st}")
        return P

    def draw(self, t):
        ctx = self.ctx
        if self.cfg.get("nen") == "mo" and self.medias:
            canvas = blur_dark(self.media(0).frame(0, ctx.W, ctx.H), ctx.W, ctx.H, 0.55)
        else:
            canvas = ctx.bg()
        z = self.punch(t, 0.035) if self.cfg.get("nhun", True) else 1.0
        for pnl in self.panels:
            pnl.draw(canvas, ctx, t, self.dur, z)
        draw_center_title(canvas, ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "giua"),
                          self.cfg.get("font", "title"), sub=self.cfg.get("phu"))
        return canvas


# ------------------------------------------------------------------ luoi
class GridScene(Scene):
    kind = "luoi"

    def draw(self, t):
        ctx = self.ctx
        W, H, s = ctx.W, ctx.H, ctx.s
        g = 8 * s
        cw, ch = (W - 2 * g) / 3, (H - 2 * g) / 3
        canvas = np.zeros((H, W, 3), np.float32)
        canvas[...] = 6
        k = 0
        for r in range(3):
            for c in range(3):
                x, y = c * (cw + g), r * (ch + g)
                if r == 1 and c == 1:
                    canvas[int(y):int(y + ch), int(x):int(x + cw)] = np.array((12, 12, 16), np.float32)
                    continue
                m = self.media(k)
                k += 1
                if m is None:
                    continue
                fr = m.frame(t, int(cw), int(ch), zoom=lerp(1.0, 1.08, t / max(self.dur, 1e-3)))
                blend(canvas, fr, None, int(x), int(y))
        # tiêu đề ở ô giữa
        txt = self.cfg.get("chu") or ""
        if txt:
            def make():
                f, lines = fit_font(txt, "title", int(cw * 0.86), int(ch * 0.5), int(cw * 0.2), max_lines=3)
                return text_rgba("", f, (255, 255, 255), lines=lines)
            im = _cached(ctx, ("gridt", txt, W), make)
            h, w = im.shape[:2]
            blend_rgba(canvas, im, int(W / 2 - w / 2), int(H / 2 - h / 2 - ch * 0.05))
            sub = self.cfg.get("phu")
            if sub:
                si = _cached(ctx, ("grids", sub, W), lambda: text_rgba(
                    "", font("body", int(cw * 0.075)), (220, 220, 220),
                    lines=fit_font(sub, "body", int(cw * 0.86), int(ch * 0.2), int(cw * 0.075))[1]))
                sh, sw_ = si.shape[:2]
                blend_rgba(canvas, si, int(W / 2 - sw_ / 2), int(H / 2 + h / 2 - ch * 0.03))
        zp = ease("in_out_cubic", t / max(min(self.dur * 0.55, 1.4), 1e-3))
        z = lerp(3.0 - 6 * g / W, 1.0, zp)
        frame = zoom_frame(to_uint8(canvas), z)
        return frame.astype(np.float32)


# ------------------------------------------------------------------ hinh_mo
SHAPE_MAP = {"tron": "circle", "thoi": "diamond", "sao": "star", "x": "cross", "luc_giac": "hexagon",
             "chu_nhat": "rect", "cong": "plus"}


class RevealScene(Scene):
    kind = "hinh_mo"

    def draw(self, t):
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        shape = SHAPE_MAP.get(self.cfg.get("hinh", "tron"), "circle")
        a = self.media(0) if len(self.medias) > 1 else None
        b = self.media(1) if len(self.medias) > 1 else self.media(0)
        zt = lerp(1.0, 1.06, t / max(self.dur, 1e-3)) * self.punch(t, 0.03)
        canvas = a.frame(t, W, H, zoom=zt).astype(np.float32) if a is not None else ctx.bg()
        rd = min(0.9, self.dur * 0.6)
        p = ease("in_out_cubic", (t - 0.05) / rd)
        if p <= 0 or b is None:
            return canvas
        diag = math.hypot(W, H)
        k = {"circle": 1.02, "diamond": 1.45, "star": 2.9, "cross": 1.2, "hexagon": 1.25, "rect": 1.0,
             "plus": 1.4}.get(shape, 1.2)
        S = diag * k * p
        rot = (1 - p) * 110 if shape in ("diamond", "star", "cross", "hexagon", "plus") else 0
        fb = b.frame(t, W, H, zoom=zt).astype(np.uint8)
        if p >= 0.999:
            blend(canvas, fb, None, 0, 0)
        else:
            sw, sh = (S, S) if shape != "rect" else (W * p, H * p)
            al = shape_alpha(shape, W, H, sw, sh, rot, radius=W * 0.04 * p if shape == "rect" else 0)
            fade = clamp((p - 0.85) / 0.15)
            if fade > 0:
                al = np.maximum(al, fade)
            # viền sáng mảnh quanh hình
            blend(canvas, fb, al, 0, 0)
        draw_center_title(canvas, ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "giua"))
        return canvas


# ------------------------------------------------------------------ tieu_de
BG = {"den": ((14, 14, 18), (2, 2, 4)), "do": ((222, 40, 48), (150, 14, 22)),
      "trang": ((250, 250, 250), (225, 225, 228)), "xanh": ((20, 46, 98), (6, 14, 36)),
      "tim": ((96, 44, 156), (30, 10, 60)), "vang": ((255, 214, 10), (230, 160, 0))}


class TitleScene(Scene):
    kind = "tieu_de"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        self.text = nfc(cfg.get("chu") or "TIÊU ĐỀ")
        hl = cfg.get("nhan_manh") or []
        if isinstance(hl, str):
            hl = [hl]
        self.hl = [nfc(h).lower() for h in hl]
        self.bgname = cfg.get("nen", "den")
        light = self.bgname == "trang" or self.bgname == "vang"
        self.fg = color(cfg.get("mau_chu"), (16, 16, 20) if light else (255, 255, 255))
        acc_default = RED if light else (YELLOW if self.bgname != "do" else (255, 236, 120))
        self.acc = color(cfg.get("mau_nhan"), acc_default)
        self._layout()

    def _is_hl(self, w):
        lw = w.lower().strip(",.!?:;\"'“”")
        return any(h and (h in lw or lw in h.split()) for h in self.hl)

    def _layout(self):
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        kind = self.cfg.get("font", "title")
        txt = self.text.upper() if self.cfg.get("in_hoa", True) else self.text
        f, lines = fit_font(txt, kind, int(W * 0.86), int(H * 0.5), int(W * 0.15), max_lines=5, spacing=1.08)
        self.font = f
        lh = f.size * 1.1
        space = text_size("a a", f)[0] - text_size("aa", f)[0]
        words = []
        total_h = lh * len(lines)
        y0 = H * 0.47 - total_h / 2
        for li, line in enumerate(lines):
            ws = line.split()
            widths = [text_size(w, f)[0] for w in ws]
            lw = sum(widths) + space * (len(ws) - 1)
            x = W / 2 - lw / 2
            for w, ww in zip(ws, widths):
                words.append({"w": w, "cx": x + ww / 2, "cy": y0 + li * lh + lh / 2, "hl": self._is_hl(w)})
                x += ww + space
        for wd in words:
            col = self.acc if wd["hl"] else self.fg
            wd["img"] = text_rgba(wd["w"], f, col, shadow=max(2, int(6 * ctx.s)) if self.bgname in ("media", "den") else 0)
        # thời điểm xuất hiện từng từ
        n = len(words)
        slots = []
        if self.ctx.music_beats and self.lbeats and self.cfg.get("theo_nhip", True):
            half = []
            for i, b in enumerate(self.lbeats):
                half.append(b)
                nb = self.lbeats[i + 1] if i + 1 < len(self.lbeats) else b + self.ctx.beats.period
                half.append((b + nb) / 2)
            half = [h for h in half if 0.0 <= h < self.dur * 0.75]
            if len(half) >= n:
                slots = half[:n]
        if not slots:
            step = clamp(self.dur * 0.55 / max(n, 1), 0.07, 0.32)
            slots = [0.06 + i * step for i in range(n)]
        for wd, s in zip(words, slots):
            wd["t"] = s
        self.words = words

    def draw(self, t):
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        if self.bgname == "media" and self.medias:
            canvas = blur_dark(self.media(0).frame(0, W, H), W, H, 0.5)
        else:
            top, bot = BG.get(self.bgname, BG["den"])
            canvas = vertical_gradient(W, H, top, bot)
        # chớp nền + rung nhẹ khi từ nhấn mạnh xuất hiện
        shake = 0.0
        for wd in self.words:
            if wd["hl"] and 0 <= t - wd["t"] < 0.18:
                k = 1 - (t - wd["t"]) / 0.18
                canvas += 40 * k
                shake = max(shake, k)
        rnd = random.Random(int(t * 1000))
        sx = (rnd.random() - 0.5) * 16 * ctx.s * shake
        sy = (rnd.random() - 0.5) * 16 * ctx.s * shake
        for wd in self.words:
            dt = t - wd["t"]
            if dt < 0:
                continue
            p = ease("out_cubic", dt / 0.14)
            sc = lerp(2.0 if wd["hl"] else 1.45, 1.0, p)
            im = scale_rgba(wd["img"], sc)
            h, w = im.shape[:2]
            blend_rgba(canvas, im, int(wd["cx"] - w / 2 + sx), int(wd["cy"] - h / 2 + sy), clamp(p * 1.5))
        sub = self.cfg.get("phu")
        if sub:
            last = self.words[-1]["t"] if self.words else 0
            p = ease("out_cubic", (t - last - 0.15) / 0.3)
            if p > 0:
                col = (60, 60, 66) if self.bgname in ("trang", "vang") else (230, 230, 230)
                si = _cached(ctx, ("tsub", sub, W, col), lambda: text_rgba(
                    "", font("body", int(W * 0.04)), col,
                    lines=fit_font(sub, "body", int(W * 0.8), int(H * 0.12), int(W * 0.04))[1]))
                sh, sw_ = si.shape[:2]
                lasty = max((wd["cy"] for wd in self.words), default=H / 2)
                blend_rgba(canvas, si, int(W / 2 - sw_ / 2), int(lasty + self.font.size * 0.9 + (1 - p) * 30), p)
        return canvas


# ------------------------------------------------------------------ flash
class FlashScene(Scene):
    kind = "flash"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        rnd = random.Random(self.seed)
        items = []
        if len(self.medias) == 1:
            m = self.medias[0]
            for i in range(24):
                items.append((m, rnd.choice([1.0, 1.2, 1.35, 1.5, 1.7, 1.15]), rnd.uniform(0.2, 0.8),
                              rnd.uniform(0.2, 0.8)))
        else:
            for m in self.medias:
                items.append((m, 1.0, 0.5, 0.5))
        self.items = items
        moi = cfg.get("moi", "nhip" if ctx.music_beats else 0.3)
        slots = []
        if moi in ("nhip", "nua_nhip") and self.lbeats:
            pts = []
            for i, b in enumerate(self.lbeats):
                pts.append(b)
                if moi == "nua_nhip":
                    nb = self.lbeats[i + 1] if i + 1 < len(self.lbeats) else b + ctx.beats.period
                    pts.append((b + nb) / 2)
            slots = [p for p in pts if p < self.dur - 0.05]
            if not slots or slots[0] > 0.05:
                slots = [0.0] + slots
        if not slots:
            step = float(moi) if not isinstance(moi, str) else 0.3
            slots = list(np.arange(0, self.dur - 0.05, max(step, 0.08)))
        self.slots = slots

    def _draw_item(self, canvas, k, t_in, slot_len):
        m, z, cx, cy = self.items[k % len(self.items)]
        ctx = self.ctx
        p = ease("out_cubic", t_in / max(slot_len, 0.05))
        zz = z * lerp(1.18, 1.0, p)
        fr = m.frame(t_in, ctx.W, ctx.H, zoom=zz, cx=cx, cy=cy)
        op = clamp(t_in / 0.08)
        blend(canvas, fr, None, 0, 0, op)
        if t_in < 0.05:
            canvas += 50 * (1 - t_in / 0.05)

    def draw(self, t):
        canvas = self.ctx.bg()
        k = max(0, int(np.searchsorted(self.slots, t + 1e-6)) - 1)
        if k > 0:
            prev_len = self.slots[k] - self.slots[k - 1]
            self._draw_item(canvas, k - 1, prev_len, prev_len)
        nxt = self.slots[k + 1] if k + 1 < len(self.slots) else self.dur
        self._draw_item(canvas, k, t - self.slots[k], nxt - self.slots[k])
        draw_center_title(canvas, self.ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "giua"),
                          self.cfg.get("font", "title"))
        return canvas


# ------------------------------------------------------------------ so_sanh
class CompareScene(Scene):
    kind = "so_sanh"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        n = max(2, min(3, len(self.medias) or 2))
        self.n = n
        W, H, s = ctx.W, ctx.H, ctx.s
        g = 10 * s
        h = (H - g * (n - 1)) / n
        enter_d = min(0.45, dur * 0.4)
        self.band_h = h
        self.panels = [Panel(self.media(i), W / 2, i * (h + g) + h / 2, W, h, enter="slide", t0=i * 0.1,
                             d=enter_d, direction=(1 if i % 2 else -1, 0), kb=(1.0, 1.04)) for i in range(n)]
        labs = cfg.get("nhan") or []
        vals = cfg.get("chi_so") or []
        self.labs = [str(x) for x in labs] + [""] * n
        self.vals = [str(x) for x in vals] + [""] * n

    def draw(self, t):
        ctx = self.ctx
        W, H, s = ctx.W, ctx.H, ctx.s
        canvas = ctx.bg()
        for p in self.panels:
            p.draw(canvas, ctx, t, self.dur)
        f = font("bold", int(W * 0.055))
        for i in range(self.n):
            lab, val = self.labs[i], self.vals[i]
            if not lab and not val:
                continue
            img = _cached(ctx, ("cmp", lab, val, W), lambda lab=lab, val=val: chip_parts_rgba(
                [(lab, (255, 255, 255)), (val, value_color(val))], f, bg=(10, 10, 14)))
            p = ease("out_back", (t - 0.35 - i * 0.12) / 0.35)
            if p <= 0:
                continue
            im = scale_rgba(img, max(p, 0.05))
            top = i * (self.band_h + 10 * s)
            ch = img.shape[0]
            # đặt thẻ sát đường nối giữa các dải (tránh vùng nhãn trên cùng và vùng chữ TikTok phía dưới)
            y = top + self.band_h - ch - H * 0.025 if i == 0 else top + H * 0.025
            blend_rgba(canvas, im, int(W * 0.05), int(y + (ch - im.shape[0]) / 2), clamp(p))
        if self.n == 2 and self.cfg.get("vs", True):
            p = ease("out_back", (t - 0.5) / 0.35)
            if p > 0:
                d = W * 0.2 * max(p, 0.05)
                al = shape_alpha("circle", int(d) + 2, int(d) + 2, d, d)
                blend_solid(canvas, (230, 32, 40), al, int(W / 2 - d / 2), int(H / 2 - d / 2))
                vs = _cached(ctx, ("vs", W), lambda: text_rgba("VS", font("impact", int(W * 0.085)), (255, 255, 255)))
                vs2 = scale_rgba(vs, max(p, 0.05))
                h, w = vs2.shape[:2]
                blend_rgba(canvas, vs2, int(W / 2 - w / 2), int(H / 2 - h / 2))
        draw_center_title(canvas, ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "tren"))
        return canvas


# ------------------------------------------------------------------ ket
class EndScene(Scene):
    kind = "ket"

    def draw(self, t):
        ctx = self.ctx
        W, H, s = ctx.W, ctx.H, ctx.s
        brand = ctx.brand
        if self.medias:
            canvas = blur_dark(self.media(0).frame(0, W, H), W, H, 0.55)
        else:
            top, bot = BG.get(self.cfg.get("nen", "xanh"), BG["xanh"])
            canvas = vertical_gradient(W, H, top, bot)
        cy = H * 0.42
        logo = brand.get("logo_media")
        if logo is not None:
            p = ease("out_back", t / 0.4)
            d = W * 0.3 * max(p, 0.05)
            fr = logo.frame(0, int(d) + 2, int(d) + 2)
            al = shape_alpha("circle", int(d) + 2, int(d) + 2, d, d)
            blend(canvas, fr, al, int(W / 2 - d / 2), int(cy - W * 0.26 - d / 2))
        handle = self.cfg.get("chu") or brand.get("handle") or ""
        if handle:
            def mk():
                f, lines = fit_font(handle, "title", int(W * 0.86), int(H * 0.15), int(W * 0.085), max_lines=2)
                return text_rgba("", f, (255, 255, 255), lines=lines, shadow=int(8 * s))
            im = _cached(ctx, ("endh", handle, W), mk)
            p = ease("out_cubic", (t - 0.1) / 0.35)
            h, w = im.shape[:2]
            blend_rgba(canvas, im, int(W / 2 - w / 2), int(cy - h / 2 + (1 - p) * 40 * s), p)
        sub = self.cfg.get("phu", brand.get("loi_moi", "Theo dõi để cập nhật mỗi ngày"))
        if sub:
            si = _cached(ctx, ("ends", sub, W), lambda: text_rgba(
                "", font("body", int(W * 0.042)), (225, 225, 225),
                lines=fit_font(sub, "body", int(W * 0.84), int(H * 0.12), int(W * 0.042))[1]))
            p = ease("out_cubic", (t - 0.3) / 0.35)
            h, w = si.shape[:2]
            blend_rgba(canvas, si, int(W / 2 - w / 2), int(cy + W * 0.08), p)
        btn = self.cfg.get("nut", "THEO DÕI")
        if btn:
            bi = _cached(ctx, ("endb", btn, W), lambda: chip_rgba(btn, font("title", int(W * 0.055)),
                                                                   fg=(255, 255, 255), bg=(230, 32, 40),
                                                                   bg_alpha=255, pad_x=1.0, pad_y=0.45, radius=0.5))
            p = ease("out_back", (t - 0.5) / 0.35)
            if p > 0:
                im = scale_rgba(bi, max(p, 0.05) * self.punch(t, 0.08, 0.16))
                h, w = im.shape[:2]
                blend_rgba(canvas, im, int(W / 2 - w / 2), int(cy + W * 0.27 - h / 2), clamp(p))
        return canvas


# ------------------------------------------------------------------ nhay
class MontageScene(Scene):
    """Dồn cắt kiểu reel CapCut: mỗi nốt nhạc là một clip khác, cắt thẳng, không nhún, không chuyển cảnh.
    Clip video lấy một đoạn ngẫu nhiên khác nhau mỗi lần dùng nên hình luôn đang chuyển động.
    Khóa: media [list], cat (not|nua_nhip|nhip|số giây), nguong (độ mạnh nốt tối thiểu, mặc định 1.5),
    cat_toi_thieu (giây, mặc định 0.12), dai_tu / dai_den / dai_giay (dải ngang mở dần: tỉ lệ chiều cao 0..1),
    vao (hiệu ứng ở các cú cắt trúng phách, lần lượt: punch | rung | nhoe | chop), chu, phu, font, vi_tri."""
    kind = "nhay"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        self.cuts = self._cuts(cfg.get("cat", "not"))
        vao = cfg.get("vao") or []
        vao = [vao] if isinstance(vao, str) else list(vao)
        self.fx, j = [], 0
        for c in self.cuts:
            on_beat = any(abs(c - b) < 0.05 for b in self.lbeats)
            self.fx.append(vao[j % len(vao)] if vao and on_beat else None)
            j += bool(vao and on_beat)
        rnd = random.Random(self.seed)
        self.shots = []  # (media, giây bắt đầu trong clip)
        for k, c in enumerate(self.cuts):
            m = self.media(k)
            off = 0.0
            if m is not None and m.kind == "video" and len(self.medias) > 1:
                nxt = self.cuts[k + 1] if k + 1 < len(self.cuts) else dur
                span = m.duration - m.start - (nxt - c) - 0.1
                off = rnd.uniform(0, span) if span > 0 else 0.0
            self.shots.append((m, off))
        self._active = None

    def _cuts(self, mode):
        if len(self.medias) <= 1:
            return [0.0]
        ctx, cfg = self.ctx, self.cfg
        b = ctx.beats
        beats = list(b.beats) if ctx.music_beats else []
        if mode == "not" and ctx.music_beats:
            thr = float(cfg.get("nguong", 1.5))
            pts = [float(x) for x, s in zip(b.onsets, b.onset_strengths) if s >= thr] + beats
        elif mode == "nua_nhip" and beats:
            pts = beats + [(x + y) / 2 for x, y in zip(beats[:-1], beats[1:])]
        elif mode in ("nhip", "not") and beats:
            pts = beats
        else:
            step = max(float(mode) if not isinstance(mode, str) else 0.3, 0.08)
            pts = list(self.start + np.arange(0, self.dur, step))
        gap = float(cfg.get("cat_toi_thieu", 0.12))
        out = [0.0]
        for x in sorted(p - self.start for p in pts):
            if gap <= x < self.dur - gap and x - out[-1] >= gap:
                out.append(x)
        return out

    def sfx(self):
        sound = {"nhoe": "whoosh_ngan", "punch": "hit", "rung": "glitch", "chop": "tick"}
        out = [(c, sound[f], 0.55) for c, f in zip(self.cuts, self.fx) if f in sound]
        if float(self.cfg.get("dai_tu", 1.0)) < 0.05 < float(self.cfg.get("dai_den", 0)):
            out.append((0.0, "whoosh", 0.6))  # vạch ngang mở ra
        return out

    def _band(self, t):
        a = float(self.cfg.get("dai_tu", 1.0))
        z = float(self.cfg.get("dai_den", a))
        d = float(self.cfg.get("dai_giay", self.dur))
        return lerp(a, z, ease("out_cubic", t / max(d, 1e-3)))

    def draw(self, t):
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        k = max(0, int(np.searchsorted(self.cuts, t + 1e-6)) - 1)
        m, off = self.shots[k]
        if self._active is not None and self._active is not m:
            self._active.close()  # giải phóng tiến trình giải mã clip vừa dùng xong
        self._active = m
        t_in = t - self.cuts[k]
        if m is None:
            canvas = np.zeros((H, W, 3), np.float32)
        else:
            z, cx, cy = FX.camera(self.fx[k], t_in, k)
            if m.kind == "image":
                z *= lerp(1.0, 1.06, t / max(self.dur, 1e-3))  # ảnh tĩnh trôi nhẹ
            canvas = m.frame(off + t_in, W, H, zoom=z, cx=cx, cy=cy).astype(np.float32)
            canvas = FX.post(self.fx[k], canvas, t_in)
        band = self._band(t)
        if band < 0.999:
            h = max(2, int(round(H * max(band, 0.0))))
            y0 = (H - h) // 2
            canvas[:y0] = 0
            canvas[y0 + h:] = 0
        draw_center_title(canvas, ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "giua"),
                          self.cfg.get("font", "title"), sub=self.cfg.get("phu"))
        return canvas


# ------------------------------------------------------------------ rap_hinh
# Học từ reel @rasooliarts: mỗi khối là CÙNG một clip lộ ra qua các mảnh mask xuất hiện lần lượt theo nốt nhạc:
# hạt giống (chấm / sao / lục giác...) -> thêm hình -> các dải bay vào ráp kín khung (để lại khe mảnh).
# Mảnh: (hình, x, y, rộng, cao[, "mau"]) - x, y theo tỉ lệ khung; rộng, cao theo tỉ lệ chiều RỘNG khung
# (khung dọc 9:16 cao = 1,78 lần rộng). "mau" = tấm màu đặc thay cho hình. Phần tử cuối = dải ráp kín
# "doc:N" | "ngang:N" | "cheo:N[:góc]".
RAP_KIEU = {
    "tron_cheo": [[("circle", 0.5, 0.5, 0.3, 0.3)],
                  [("circle", 0.25, 0.2, 0.4, 0.4), ("circle", 0.75, 0.8, 0.4, 0.4)],
                  [("circle", 0.4, 0.38, 0.4, 0.4), ("circle", 0.6, 0.62, 0.4, 0.4)],
                  "cheo:5"],
    "tron_doc": [[("circle", 0.5, 0.5, 0.32, 0.32)],
                 [("circle", 0.5, 0.18, 0.42, 0.42), ("circle", 0.5, 0.82, 0.42, 0.42)],
                 [("circle", 0.5, 0.34, 0.42, 0.42), ("circle", 0.5, 0.66, 0.42, 0.42)],
                 "doc:4"],
    "thoi_x": [[("diamond", 0.5, 0.5, 0.12, 0.12)],
               [("diamond", 0.22, 0.2, 0.46, 0.46), ("diamond", 0.78, 0.2, 0.46, 0.46),
                ("diamond", 0.22, 0.8, 0.46, 0.46), ("diamond", 0.78, 0.8, 0.46, 0.46)],
               [("diamond", 0.5, 0.5, 0.66, 0.66)],
               "ngang:4"],
    "x": [[("cross", 0.5, 0.5, 0.45, 0.45)],
          [("cross", 0.5, 0.5, 1.2, 1.2)],
          "cheo:4:45"],
    "sao": [[("star", 0.5, 0.5, 0.2, 0.2)],
            [("star", 0.5, 0.5, 0.64, 0.64)],
            [("rect", 0.17, 0.5, 0.34, 1.78), ("rect", 0.83, 0.5, 0.34, 1.78)],
            "doc:3"],
    "luc_giac": [[("hexagon", 0.5, 0.5, 0.34, 0.34, "mau")],
                 [("hexagon", 0.5, 0.5, 0.56, 0.56)],
                 [("rect", 0.5, 0.18, 1.0, 0.64, "mau")],
                 "ngang:3"],
    "o_vuong": [[("rect", 0.5, 0.86, 1.0, 0.5)],
                [("rect", 0.25, 0.17, 0.5, 0.6)],
                [("rect", 0.75, 0.17, 0.5, 0.6)],
                "ngang:3"],
    "tron_hang": [[("circle", 0.5, 0.5, 0.2, 0.2)],
                  [("circle", 0.14, 0.5, 0.24, 0.24), ("circle", 0.38, 0.5, 0.24, 0.24),
                   ("circle", 0.62, 0.5, 0.24, 0.24), ("circle", 0.86, 0.5, 0.24, 0.24)],
                  [("circle", 0.27, 0.5, 0.56, 0.56), ("circle", 0.73, 0.5, 0.56, 0.56)],
                  "doc:4"],
    "zigzag": [[("diamond", 0.5, 0.5, 0.14, 0.14)],
               [("diamond", x, 0.5, 0.26, 0.26) for x in (0.1, 0.3, 0.5, 0.7, 0.9)],
               [("diamond", x, y, 0.3, 0.3) for y in (0.36, 0.64) for x in (0.2, 0.5, 0.8)],
               "cheo:4:30"],
    "kim_cuong": [[("diamond", 0.5, 0.5, 0.3, 0.3)],
                  [("diamond", 0.5, 0.5, 0.95, 0.95)],
                  [("diamond", x, y, 0.95, 0.95) for x in (0.0, 1.0) for y in (0.0, 1.0)],
                  "ngang:3"],
    "luoi_o": [[("rect", 0.5, 0.375, 0.333, 0.444)],
               [("rect", 0.17, 0.125, 0.333, 0.444), ("rect", 0.83, 0.625, 0.333, 0.444),
                ("rect", 0.17, 0.875, 0.333, 0.444)],
               [("rect", 0.83, 0.125, 0.333, 0.444), ("rect", 0.17, 0.5, 0.333, 0.444),
                ("rect", 0.5, 0.875, 0.333, 0.444)],
               "doc:3"],
    "tam_giac": [[("tri_up", 0.5, 0.5, 0.24, 0.21)],
                 [("tri_up", 0.25, 0.3, 0.5, 0.43), ("tri_down", 0.75, 0.3, 0.5, 0.43)],
                 [("tri_down", 0.25, 0.7, 0.5, 0.43), ("tri_up", 0.75, 0.7, 0.5, 0.43)],
                 "cheo:4:60"],
    "elip": [[("ellipse", 0.5, 0.5, 0.36, 0.14)],
             [("ellipse", 0.5, 0.28, 0.9, 0.34), ("ellipse", 0.5, 0.72, 0.9, 0.34)],
             [("ellipse", 0.5, 0.5, 1.1, 0.6)],
             "ngang:3"],
    "cong": [[("plus", 0.5, 0.5, 0.3, 0.3)],
             [("plus", 0.5, 0.5, 0.9, 0.9)],
             [("plus", 0.5, 0.5, 1.6, 1.6, "mau")],
             "doc:4"],
}
# tam giác = đa giác lồi (toạ độ theo tỉ lệ kích thước hình, quanh tâm)
TRI_PTS = {"tri_up": ((-0.5, 0.5), (0.5, 0.5), (0.0, -0.5)), "tri_down": ((-0.5, -0.5), (0.5, -0.5), (0.0, 0.5))}


def _crop_pad(arr, x, y, w, h):
    """Cắt vùng (x, y, w, h) của ảnh; phần nằm ngoài ảnh là màu đen."""
    H, W = arr.shape[:2]
    out = np.zeros((h, w, 3), np.float32)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 > x0 and y1 > y0:
        out[y0 - y:y1 - y, x0 - x:x1 - x] = arr[y0:y1, x0:x1]
    return out


class AssembleScene(Scene):
    """Ráp hình: cùng một clip lộ ra qua các mảnh mask nở / bay vào lần lượt trúng nốt nhạc rồi ráp kín khung.
    Khóa: media (1 clip/ảnh), kieu (xem RAP_KIEU: tron_cheo, tron_doc, tron_hang, thoi_x, zigzag, kim_cuong,
    x, sao, luc_giac, o_vuong, luoi_o, tam_giac, elip, cong),
    nguong (độ mạnh nốt), mau_nhan (màu tấm màu), khe (px khe giữa các dải), chu, phu, font."""
    kind = "rap_hinh"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        W, H = ctx.W, ctx.H
        spec = RAP_KIEU.get(cfg.get("kieu", "tron_cheo"), RAP_KIEU["tron_cheo"])
        groups, fill = spec[:-1], spec[-1]
        times = self._times(len(groups) + 1)
        self.pieces = []
        for gi, g in enumerate(groups):
            for j, it in enumerate(g):
                kind, x, y, w, h = it[:5]
                self.pieces.append((times[gi] + 0.06 * j, kind, x * W, y * H, w * W, h * W, len(it) > 5))
        self.times = times
        self.t_fill = times[-1]
        self.t_text = times[1] if len(times) > 2 else times[-1]
        self.strips = self._strips(fill, float(cfg.get("khe", 6)) * ctx.s)
        self.acc = np.array(color(cfg.get("mau_nhan"), YELLOW), np.float32)

    def sfx(self):
        # pop rõ ở hạt giống đầu khối, các nhóm sau nhỏ hơn để không thành tiếng lách cách liên tục
        return ([(self.times[0], "pop", 0.5)] + [(t, "pop", 0.2) for t in self.times[1:-1]]
                + [(self.t_fill, "whoosh", 0.55)])

    def _times(self, n):
        """Thời điểm xuất hiện của từng nhóm mảnh: rải đều trên ~62% khối, mỗi mốc bám nốt nhạc gần nhất."""
        ctx = self.ctx
        ev = []
        if ctx.music_beats:
            thr = float(self.cfg.get("nguong", 1.5))
            b = ctx.beats
            ev = sorted(float(x) - self.start for x, s in
                        zip(list(b.onsets) + list(b.beats), list(b.onset_strengths) + [9.0] * len(b.beats))
                        if s >= thr)
        out = [0.0]
        for tgt in np.linspace(0, self.dur * 0.62, n)[1:]:
            near = [x for x in ev if x >= out[-1] + 0.15 and abs(x - tgt) <= 0.25]
            out.append(min(near, key=lambda x: abs(x - tgt)) if near else max(float(tgt), out[-1] + 0.15))
        return out

    def _strips(self, spec, gap):
        W, H = self.ctx.W, self.ctx.H
        parts = str(spec).split(":")
        kind, n = parts[0], int(parts[1]) if len(parts) > 1 else 4
        phi = {"doc": 0.0, "ngang": 90.0}.get(kind, float(parts[2]) if len(parts) > 2 else 20.0)
        a = math.radians(phi)
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        u = xs * math.cos(a) + ys * math.sin(a)
        lo, hi = float(u.min()), float(u.max())
        edges = np.linspace(lo, hi, n + 1)
        dirx, diry = -math.sin(a), math.cos(a)  # dải bay vào dọc theo chiều dài của nó
        out = []
        for i in range(n):
            d = np.minimum(u - edges[i] - (gap / 2 if i else -9), edges[i + 1] - u - (gap / 2 if i < n - 1 else -9))
            al = np.clip(d + 0.5, 0, 1).astype(np.float32)
            rows, cols = np.where(al.any(1))[0], np.where(al.any(0))[0]
            if not len(rows) or not len(cols):
                continue
            y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
            sgn = 1 if i % 2 else -1
            out.append((al[y0:y1, x0:x1], int(x0), int(y0), dirx * sgn, diry * sgn))
        return out

    def draw(self, t):
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        m = self.media(0)
        F = (m.frame(t, W, H, zoom=lerp(1.0, 1.08, t / max(self.dur, 1e-3))).astype(np.float32)
             if m is not None else ctx.bg())
        canvas = np.zeros((H, W, 3), np.float32)
        for t0, kind, cx, cy, w, h, plate in self.pieces:
            if t < t0:
                continue
            q = (t - t0) / 0.3
            dx = dy = 0
            if kind == "rect":  # tấm chữ nhật trượt vào từ mép gần nhất
                s = 1.0
                off = (1 - ease("out_cubic", q)) * max(W, H)
                if abs(cx - W / 2) > abs(cy - H / 2) * W / H:
                    dx = int(off * (1 if cx > W / 2 else -1))
                else:
                    dy = int(off * (1 if cy > H / 2 else -1))
            else:  # hình nở ra
                s = max(ease("out_back", q), 0.02)
            sw, sh = w * s, h * s
            bw, bh = int(math.ceil(sw)) + 2, int(math.ceil(sh)) + 2
            x, y = int(round(cx - bw / 2)), int(round(cy - bh / 2))
            alpha = ctx.mcache.get((kind, bw, bh, round(sw, 1), round(sh, 1)),
                                   lambda: shape_alpha("polygon", bw, bh, sw, sh, pts=TRI_PTS[kind])
                                   if kind in TRI_PTS else shape_alpha(kind, bw, bh, sw, sh))
            if plate:
                blend_solid(canvas, self.acc, alpha, x + dx, y + dy)
                continue
            content = _crop_pad(F, x, y, bw, bh)
            if kind != "rect" and q < 0.5:  # nhoè lúc nở
                content = FX.directional_blur(content, bh * 0.35 * (1 - q / 0.5), 90)
            blend(canvas, content, alpha, x + dx, y + dy)
        dist = max(W, H)
        for i, (al, x0, y0, ux, uy) in enumerate(self.strips):
            ti = self.t_fill + 0.06 * i
            if t < ti:
                continue
            off = (1 - ease("out_cubic", (t - ti) / 0.3)) * dist
            h, w = al.shape
            blend(canvas, F[y0:y0 + h, x0:x0 + w], al, x0 + int(ux * off), y0 + int(uy * off))
        draw_center_title(canvas, ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "giua"),
                          self.cfg.get("font", "title"), appear=self.t_text, sub=self.cfg.get("phu"))
        return canvas


# ------------------------------------------------------------------ tuong_anh
class WallScene(Scene):
    """Tường ảnh: lưới ô, mỗi ô một clip khác nhau; cả lưới cùng đổi hình theo nhịp.
    Khóa: media [list], cot (mặc định 2), hang (3), khe (px, 8), doi (nhip | nua_nhip | số giây), chu, phu."""
    kind = "tuong_anh"

    def __init__(self, cfg, ctx, start, dur):
        super().__init__(cfg, ctx, start, dur)
        self.cols, self.rows = max(1, int(cfg.get("cot", 2))), max(1, int(cfg.get("hang", 3)))
        doi = cfg.get("doi", "nhip")
        pts = []
        if doi in ("nhip", "nua_nhip") and self.lbeats:
            pts = list(self.lbeats)
            if doi == "nua_nhip":
                pts += [(a + b) / 2 for a, b in zip(self.lbeats[:-1], self.lbeats[1:])]
        else:
            step = max(float(doi) if not isinstance(doi, str) else 0.5, 0.15)
            pts = list(np.arange(0, dur, step))
        self.slots = [0.0] + sorted(p for p in set(round(x, 4) for x in pts) if 0.15 < p < dur - 0.1)
        rnd = random.Random(self.seed)
        ncell = self.cols * self.rows
        self.plan = []
        for k, s0 in enumerate(self.slots):
            s1 = self.slots[k + 1] if k + 1 < len(self.slots) else dur
            row = []
            for c in range(ncell):
                m = self.media(k * ncell + c)
                span = (m.duration - m.start - (s1 - s0) - 0.1) if m is not None and m.kind == "video" else 0
                row.append((m, rnd.uniform(0, span) if span > 0 else 0.0))
            self.plan.append(row)
        self._active = set()

    def sfx(self):
        return [(0.0, "whoosh_ngan", 0.5)] + [(s, "tick", 0.4) for s in self.slots[1:]]

    def draw(self, t):
        ctx = self.ctx
        W, H = ctx.W, ctx.H
        g = float(self.cfg.get("khe", 8)) * ctx.s
        cw = int((W - g * (self.cols + 1)) / self.cols)
        ch = int((H - g * (self.rows + 1)) / self.rows)
        k = max(0, int(np.searchsorted(self.slots, t + 1e-6)) - 1)
        t_in = t - self.slots[k]
        canvas = np.zeros((H, W, 3), np.float32)
        active = set()
        for c, (m, off) in enumerate(self.plan[k]):
            if m is None:
                continue
            p = 1.0 if k else ease("out_cubic", (t - 0.05 * c) / 0.25)  # lần đầu: các ô lộ ra lần lượt từ tâm
            if p <= 0.01:
                continue
            active.add(id(m))
            fr = m.frame(off + t_in, cw, ch).astype(np.float32)
            w, h = max(2, int(cw * p)), max(2, int(ch * p))
            x0, y0 = (cw - w) // 2, (ch - h) // 2
            col, row = c % self.cols, c // self.cols
            x = int(g + col * (cw + g)) + x0
            y = int(g + row * (ch + g)) + y0
            blend(canvas, fr[y0:y0 + h, x0:x0 + w], None, x, y)
        for m in {id(m): m for row in self.plan for m, _ in row if m is not None}.values():
            if id(m) in self._active and id(m) not in active:
                m.close()  # giải phóng clip vừa rời khỏi lưới
        self._active = active
        if k and t_in < 0.06:
            canvas += 45.0 * (1 - t_in / 0.06)  # chớp nhẹ lúc cả lưới đổi hình
        draw_center_title(canvas, ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "giua"),
                          self.cfg.get("font", "title"), sub=self.cfg.get("phu"))
        return canvas


# ------------------------------------------------------------------ nghi_den
class BlackScene(Scene):
    kind = "nghi_den"

    def draw(self, t):
        canvas = np.zeros((self.ctx.H, self.ctx.W, 3), np.float32)
        draw_center_title(canvas, self.ctx, self.cfg.get("chu"), t, self.cfg.get("vi_tri", "giua"),
                          self.cfg.get("font", "title"), sub=self.cfg.get("phu"))
        return canvas


SCENES = {c.kind: c for c in (FullScene, SplitScene, GridScene, RevealScene, TitleScene, FlashScene,
                              CompareScene, EndScene, MontageScene, AssembleScene, WallScene, BlackScene)}
