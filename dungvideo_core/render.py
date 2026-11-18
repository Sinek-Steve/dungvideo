"""Dựng timeline từ file dự án và xuất MP4 qua ffmpeg."""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from . import transitions as TR
from .beats import BeatInfo, detect, synthetic
from .comp import blend, blend_rgba, vignette_map
from .grade import make_grade
from .masks import MaskCache
from .media import MediaPool, probe_duration
from .scenes import SCENES, Ctx
from .textfx import fit_font, font, nfc, text_rgba
from .util import Progress, clamp, color, ease, ffmpeg_bin


# ------------------------------------------------------------------ phụ đề
def parse_srt(path: Path):
    txt = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    cues = []
    for block in re.split(r"\n\s*\n", txt.strip()):
        lines = [l for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        tl = lines[1] if "-->" in lines[1] else lines[0]
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", tl.strip())
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        body = " ".join(lines[lines.index(tl) + 1:])
        cues.append((a, b, nfc(body)))
    return cues


# ------------------------------------------------------------------ khung thương hiệu
class BrandFrame:
    def __init__(self, cfg: dict, W: int, H: int, pool: MediaPool):
        self.on = bool(cfg.get("bat", True))
        self.W, self.H = W, H
        self.kind = cfg.get("kieu", "toi_gian")
        self.pieces = []  # (rgba, x, y)
        self.cache = {}
        if not self.on:
            return
        s = W / 1080
        today = _dt.date.today().strftime("%d/%m/%Y")

        def sub(x):
            return nfc(str(x).replace("{ngay}", today)) if x else ""

        top = [sub(x) for x in (cfg.get("tren") or [])][:3]
        bottom = sub(cfg.get("duoi", ""))
        y_top = H * float(cfg.get("vi_tri_tren", 0.055))
        y_bot = H * float(cfg.get("vi_tri_duoi", 0.885))
        if self.kind == "phim":
            bh = int(H * 0.032)
            bar = Image.new("RGBA", (W, bh), (0, 0, 0, 235))
            d = ImageDraw.Draw(bar)
            hw, hh = int(bh * 0.55), int(bh * 0.5)
            for x in range(int(bh * 0.4), W, int(hw * 1.9)):
                d.rounded_rectangle((x, (bh - hh) // 2, x + hw, (bh + hh) // 2), radius=int(hh * 0.3),
                                    fill=(235, 235, 235, 210))
            arr = np.asarray(bar)
            self.pieces += [(arr, 0, 0), (arr, 0, H - bh)]
            y_top = max(y_top, bh * 1.9)
            y_bot = min(y_bot, H - bh * 2.4)
        if self.kind == "hud":
            L, th = int(W * 0.09), max(3, int(5 * s))
            m = int(W * 0.05)
            corner = Image.new("RGBA", (L, L), (0, 0, 0, 0))
            d = ImageDraw.Draw(corner)
            d.rectangle((0, 0, L, th), fill=(255, 255, 255, 220))
            d.rectangle((0, 0, th, L), fill=(255, 255, 255, 220))
            c = np.asarray(corner)
            self.pieces += [(c, m, int(H * 0.1)), (c[:, ::-1], W - m - L, int(H * 0.1)),
                            (c[::-1], m, int(H * 0.86) - L), (c[::-1, ::-1], W - m - L, int(H * 0.86) - L)]
        f_small = font("body", int(W * 0.026))
        if top:
            n = len(top)
            for i, txt in enumerate(top):
                im = text_rgba(txt, f_small, (255, 255, 255), shadow=max(1, int(3 * s)))
                h, w = im.shape[:2]
                if n == 1:
                    x = W / 2 - w / 2
                elif i == 0:
                    x = W * 0.06
                elif i == n - 1:
                    x = W * 0.94 - w
                else:
                    x = W / 2 - w / 2
                self.pieces.append((self._fade(im, 0.88), int(x), int(y_top - h / 2)))
        if bottom:
            f_b = font("bold", int(W * 0.032))
            im = text_rgba(bottom, f_b, (255, 255, 255), shadow=max(1, int(4 * s)))
            h, w = im.shape[:2]
            self.pieces.append((self._fade(im, 0.92), int(W / 2 - w / 2), int(y_bot - h / 2)))
        logo = cfg.get("logo")
        if logo:
            try:
                m = pool.get(logo)
                d = int(W * 0.11)
                fr = m.frame(0, d, d)
                from .masks import shape_alpha
                al = (shape_alpha("circle", d, d, d - 2, d - 2) * 255).astype(np.uint8)
                rgba = np.dstack([fr, al])
                self.pieces.append((rgba, int(W * 0.94 - d), int(H * 0.11)))
            except SystemExit:
                pass

    @staticmethod
    def _fade(rgba, k):
        out = rgba.copy()
        out[..., 3] = (out[..., 3].astype(np.float32) * k).astype(np.uint8)
        return out

    def draw(self, canvas, t: float):
        if not self.on:
            return
        for rgba, x, y in self.pieces:
            blend_rgba(canvas, rgba, x, y)
        if self.kind == "hud":
            W, H = self.W, self.H
            s = W / 1080
            if int(t * 2) % 2 == 0:
                d = int(22 * s)
                yy, xx = np.ogrid[:d, :d]
                al = ((xx - d / 2) ** 2 + (yy - d / 2) ** 2 <= (d / 2) ** 2).astype(np.float32)
                c = np.zeros((d, d, 3), np.float32)
                c[...] = (235, 30, 40)
                blend(canvas, c, al, int(W * 0.07), int(H * 0.13))
            tc = f"{int(t // 60):02d}:{int(t % 60):02d}:{int((t % 1) * 30):02d}"
            key = ("tc", tc)
            im = self.cache.get(key)
            if im is None:
                im = text_rgba("REC  " + tc, font("body", int(W * 0.028)), (255, 255, 255))
                if len(self.cache) > 200:
                    self.cache.clear()
                self.cache[key] = im
            blend_rgba(canvas, im, int(W * 0.07 + 30 * s), int(H * 0.13 - im.shape[0] * 0.3))


class Subtitles:
    def __init__(self, cues, W, H, y_rel=0.76):
        self.cues = cues
        self.W, self.H = W, H
        self.y = H * y_rel
        self.cache = {}

    def draw(self, canvas, t):
        for a, b, txt in self.cues:
            if a <= t < b:
                im = self.cache.get(txt)
                if im is None:
                    W = self.W
                    f, lines = fit_font(txt, "bold", int(W * 0.86), int(self.H * 0.16), int(W * 0.058), max_lines=3)
                    im = text_rgba("", f, (255, 255, 255), stroke=max(2, int(W * 0.006)), stroke_fill=(0, 0, 0),
                                   lines=lines, spacing=1.15)
                    self.cache[txt] = im
                p = ease("out_back", (t - a) / 0.16)
                from .textfx import scale_rgba
                im2 = scale_rgba(im, max(0.6, min(p, 1.08))) if p < 1 else im
                h, w = im2.shape[:2]
                blend_rgba(canvas, im2, int(self.W / 2 - w / 2), int(self.y - h / 2), clamp(p * 2))
                return


# ------------------------------------------------------------------ timeline
class Timeline:
    def __init__(self, project: dict, base_dir: Path, draft: bool = False):
        self.p = project
        self.base = Path(base_dir)
        size = str(project.get("kich_thuoc", "1080x1920")).lower().split("x")
        W, H = int(size[0]), int(size[1])
        fps = float(project.get("fps", 30))
        if draft:
            W, H, fps = W // 2, H // 2, min(fps, 24)
        W, H = W - W % 2, H - H % 2
        self.W, self.H, self.fps = W, H, fps
        grade = make_grade(project.get("mau_sac", "dien_anh"))
        self.pool = MediaPool(self.base, fps, grade)

        # nhạc & beat
        self.music = self._path(project.get("nhac"))
        self.music_start = float(project.get("nhac_bat_dau", 0) or 0)
        self.voice = self._path(project.get("giong_doc"))
        beats = None
        music_beats = False
        if self.music and project.get("dong_bo_nhac", True):
            print("Đang dò nhịp nhạc...")
            beats = detect(str(self.music), start=self.music_start)
            music_beats = True
            print(f"  Tempo ~{beats.bpm:.0f} BPM, {len(beats.beats)} beat"
                  + (f", drop ở giây {beats.drop:.1f}" if beats.drop else ""))
        if beats is None or len(beats.beats) < 4:
            beats = synthetic(600, float(project.get("bpm", 120)))
            music_beats = False
        self.beats = beats
        brand = dict(project.get("khung") or {})
        if brand.get("logo"):
            try:
                brand["logo_media"] = self.pool.get(brand["logo"])
            except SystemExit:
                brand["logo_media"] = None
        self.ctx = Ctx(W, H, fps, self.pool, beats, brand, music_beats, MaskCache())

        # dựng cảnh
        self.scenes, self.trans, self.tdur = [], [], []
        t = 0.0
        for i, c in enumerate(project.get("canh") or []):
            kind = c.get("loai", "day_du")
            if kind not in SCENES:
                raise SystemExit(f"Loại cảnh không hợp lệ: {kind} (cảnh thứ {i + 1})")
            dur = self._duration(c, t)
            sc = SCENES[kind](c, self.ctx, t, dur)
            self.scenes.append(sc)
            tr = c.get("chuyen", "cat") if i > 0 else "cat"
            if tr not in TR.DEFAULT_DUR:
                raise SystemExit(f"Kiểu chuyển cảnh không hợp lệ: {tr} (cảnh thứ {i + 1})")
            self.trans.append(tr)
            self.tdur.append(float(c.get("chuyen_giay", TR.DEFAULT_DUR[tr])))
            t += dur
        if not self.scenes:
            raise SystemExit("Dự án chưa có cảnh nào (mục 'canh').")
        for i in range(1, len(self.scenes)):
            lim = 0.9 * min(self.scenes[i - 1].dur, self.scenes[i].dur)
            self.tdur[i] = min(self.tdur[i], lim)
        self.total = t
        if project.get("do_dai"):
            self.total = min(self.total, float(project["do_dai"]))

        self.vig = vignette_map(W, H, float(project.get("vignette", 0.22)))
        self.frame_ov = BrandFrame(brand, W, H, self.pool)
        cues = []
        if project.get("phu_de_srt"):
            sp = self._path(project["phu_de_srt"])
            if sp:
                cues = parse_srt(sp)
        for c in project.get("phu_de") or []:
            cues.append((float(c["tu"]), float(c["den"]), nfc(c["chu"])))
        self.subs = Subtitles(cues, W, H, float(project.get("vi_tri_phu_de", 0.76))) if cues else None
        self.progress_bar = bool(project.get("thanh_tien_do", False))
        self.accent = color(project.get("mau_nhan"), (255, 212, 0))

    def _path(self, p):
        if not p:
            return None
        pp = Path(p)
        if not pp.is_absolute():
            pp = self.base / pp
        if not pp.exists():
            raise SystemExit(f"Không thấy file: {pp}")
        return pp

    def _duration(self, c: dict, start: float) -> float:
        if c.get("giay") is not None:
            return max(0.2, float(c["giay"]))
        nb = int(c.get("nhip", 4))
        b = self.beats.beats if self.beats is not None else None
        if b is not None and len(b):
            i0 = int(np.searchsorted(b, start - 0.06))
            i1 = i0 + nb
            if i1 < len(b):
                end = b[i1]
            else:
                end = (b[-1] if len(b) else start) + (i1 - len(b) + 1) * self.beats.period
            return max(0.2, float(end - start))
        return nb * 0.5

    def scene_at(self, t: float) -> int:
        for i, sc in enumerate(self.scenes):
            if t < sc.start + sc.dur:
                return i
        return len(self.scenes) - 1

    def frame(self, n: int) -> np.ndarray:
        t = n / self.fps
        i = self.scene_at(t)
        sc = self.scenes[i]
        out = None
        if i + 1 < len(self.scenes) and self.trans[i + 1] != "cat":
            d = self.tdur[i + 1]
            b = sc.start + sc.dur
            if t >= b - d / 2:
                nx = self.scenes[i + 1]
                A, B = sc.render(t - sc.start), nx.render(t - nx.start)
                out = TR.apply(self.trans[i + 1], A, B, (t - (b - d / 2)) / max(d, 1e-3), n)
        if out is None and i > 0 and self.trans[i] != "cat":
            d = self.tdur[i]
            b = sc.start
            if t < b + d / 2:
                pv = self.scenes[i - 1]
                A, B = pv.render(t - pv.start), sc.render(t - sc.start)
                out = TR.apply(self.trans[i], A, B, (t - (b - d / 2)) / max(d, 1e-3), n)
        if out is None:
            out = sc.render(t - sc.start)
        hide = sc.hide_frame
        canvas = out.astype(np.float32)
        if self.vig is not None:
            canvas *= self.vig
        if not hide:
            self.frame_ov.draw(canvas, t)
        if self.subs:
            self.subs.draw(canvas, t)
        if self.progress_bar:
            h = max(3, int(self.H * 0.005))
            w = int(self.W * clamp(t / max(self.total, 1e-3)))
            if w > 0:
                canvas[:h, :w] = np.array(self.accent, np.float32)
        return np.clip(canvas, 0, 255).astype(np.uint8)

    def close(self):
        self.pool.close()


def _audio_args(tl: Timeline, total: float):
    args, filt, maps = [], [], []
    idx = 1
    mlabel = vlabel = None
    if tl.music:
        args += ["-ss", f"{tl.music_start:.3f}", "-i", str(tl.music)]
        vol = float(tl.p.get("am_luong_nhac", 0.22 if tl.voice else 1.0))
        fo = min(1.5, total / 4)
        filt.append(f"[{idx}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={vol},"
                    f"afade=t=out:st={max(total - fo, 0):.3f}:d={fo:.3f},apad[m]")
        mlabel = "[m]"
        idx += 1
    if tl.voice:
        args += ["-i", str(tl.voice)]
        vv = float(tl.p.get("am_luong_giong", 1.0))
        filt.append(f"[{idx}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume={vv},apad[v]")
        vlabel = "[v]"
        idx += 1
    if mlabel and vlabel:
        filt.append(f"{mlabel}{vlabel}amix=inputs=2:duration=first:normalize=0[a]")
        maps = ["-map", "[a]"]
    elif mlabel:
        maps = ["-map", mlabel]
    elif vlabel:
        maps = ["-map", vlabel]
    if filt:
        args += ["-filter_complex", ";".join(filt)]
    return args, maps


def render(project: dict, base_dir: Path, out: Path, draft: bool = False) -> Path:
    tl = Timeline(project, base_dir, draft)
    total = tl.total
    nframes = int(round(total * tl.fps))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    a_args, a_maps = _audio_args(tl, total)
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{tl.W}x{tl.H}", "-r", f"{tl.fps}", "-i", "-"] + a_args + ["-map", "0:v"] + a_maps
    cmd += ["-c:v", "libx264", "-preset", "ultrafast" if draft else str(project.get("preset", "veryfast")),
            "-crf", "26" if draft else str(project.get("crf", 20)), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{total:.3f}"]
    if a_maps:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += [str(out)]
    print(f"Video {tl.W}x{tl.H} @{tl.fps:g}fps, dài {total:.1f}s, {len(tl.scenes)} cảnh -> {out}")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    prog = Progress(nframes)
    try:
        for n in range(nframes):
            proc.stdin.write(tl.frame(n).tobytes())
            if n % 3 == 0:
                prog.update(n)
        proc.stdin.close()
        rc = proc.wait()
    except BrokenPipeError:
        rc = proc.wait()
    finally:
        tl.close()
    if rc != 0:
        raise SystemExit("ffmpeg báo lỗi khi xuất video.")
    prog.done()
    return out


def still(project: dict, base_dir: Path, t: float, out: Path, draft: bool = False) -> Path:
    tl = Timeline(project, base_dir, draft)
    n = int(round(min(t, tl.total - 1 / tl.fps) * tl.fps))
    Image.fromarray(tl.frame(n)).save(out)
    tl.close()
    return out
