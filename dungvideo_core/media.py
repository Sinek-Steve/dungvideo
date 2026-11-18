"""Đọc ảnh/clip và trả khung hình đã cắt vừa khung (cover) + chỉnh màu."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from .util import IMG_EXT, VID_EXT, ffmpeg_bin, ffprobe_bin

Image.MAX_IMAGE_PIXELS = None


def probe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            [ffprobe_bin(), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, check=True,
        ).stdout
        return float(json.loads(out)["format"]["duration"])
    except Exception:
        return 0.0


def _cover_box(sw: int, sh: int, w: int, h: int, zoom: float = 1.0, cx: float = 0.5, cy: float = 0.5):
    """Hộp cắt (left, top, right, bottom) trong ảnh nguồn sw×sh để phủ kín w×h."""
    target = w / h
    if sw / sh > target:
        bh = sh
        bw = sh * target
    else:
        bw = sw
        bh = sw / target
    bw /= max(zoom, 1e-3)
    bh /= max(zoom, 1e-3)
    left = (sw - bw) * cx
    top = (sh - bh) * cy
    left = min(max(left, 0), sw - bw)
    top = min(max(top, 0), sh - bh)
    return (left, top, left + bw, top + bh)


class _VideoReader:
    def __init__(self, path: str, w: int, h: int, fps: float, start: float, dur: float):
        self.path, self.w, self.h, self.fps = path, w, h, fps
        self.start = start
        self.max_idx = max(0, int((max(dur - start, 0.05)) * fps) - 1)
        self.proc = None
        self.idx = -1
        self.frame = np.zeros((h, w, 3), np.uint8)
        self.nbytes = w * h * 3

    def _open(self, idx: int):
        self.close()
        t0 = self.start + idx / self.fps
        vf = (f"scale={self.w}:{self.h}:force_original_aspect_ratio=increase:flags=bicubic,"
              f"crop={self.w}:{self.h},fps={self.fps}")
        cmd = [ffmpeg_bin(), "-v", "error", "-ss", f"{t0:.3f}", "-i", self.path, "-an",
               "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     bufsize=self.nbytes * 2)
        self.idx = idx - 1

    def get(self, t: float) -> np.ndarray:
        target = min(max(int(round(t * self.fps)), 0), self.max_idx)
        if self.proc is None or target < self.idx or target > self.idx + int(self.fps * 2):
            self._open(target)
        while self.idx < target:
            buf = self.proc.stdout.read(self.nbytes) if self.proc else b""
            if len(buf) < self.nbytes:
                self.max_idx = max(self.idx, 0)
                break
            self.frame = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
            self.idx += 1
        return self.frame

    def close(self):
        if self.proc is not None:
            try:
                self.proc.stdout.close()
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:
                pass
            self.proc = None


class Media:
    """Một ảnh hoặc clip. frame(t, w, h, zoom, cx, cy) -> uint8 (h, w, 3)."""

    def __init__(self, path: str, fps: float, grade=None, start: float = 0.0, loop: bool = True):
        self.path = str(path)
        ext = Path(path).suffix.lower()
        self.fps = fps
        self.grade = grade
        self.start = float(start or 0)
        self.loop = loop
        self.readers: dict = {}
        self._last_key = None
        self._last = None
        if ext in IMG_EXT:
            self.kind = "image"
            img = Image.open(self.path)
            img = ImageOps.exif_transpose(img).convert("RGB")
            m = max(img.size)
            if m > 2600:
                s = 2600 / m
                img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
            if grade is not None:
                img = Image.fromarray(grade(np.asarray(img)))
            self.img = img
            self.duration = float("inf")
        elif ext in VID_EXT:
            self.kind = "video"
            self.duration = probe_duration(self.path) or 1.0
        else:
            raise ValueError(f"Định dạng không hỗ trợ: {path}")

    def frame(self, t: float, w: int, h: int, zoom: float = 1.0, cx: float = 0.5, cy: float = 0.5) -> np.ndarray:
        w, h = max(2, int(round(w))), max(2, int(round(h)))
        if self.kind == "image":
            key = (w, h, round(zoom, 4), round(cx, 3), round(cy, 3))
            if key == self._last_key:
                return self._last
            box = _cover_box(self.img.width, self.img.height, w, h, zoom, cx, cy)
            arr = np.asarray(self.img.resize((w, h), Image.BILINEAR, box=box))
            self._last_key, self._last = key, arr
            return arr
        # video
        span = max(self.duration - self.start, 0.1)
        tt = (t % span) if self.loop and t > span else t
        key = (w, h)
        rd = self.readers.get(key)
        if rd is None:
            if len(self.readers) > 6:  # giới hạn số tiến trình giải mã song song
                k0 = next(iter(self.readers))
                self.readers.pop(k0).close()
            rd = _VideoReader(self.path, w, h, self.fps, self.start, self.duration)
            self.readers[key] = rd
        raw = rd.get(tt)
        ck = ("v", w, h, rd.idx, id(rd.proc), round(zoom, 4), round(cx, 3), round(cy, 3))
        if ck == self._last_key:
            return self._last
        arr = raw
        if self.grade is not None:
            arr = self.grade(arr)
        if zoom > 1.001 or cx != 0.5 or cy != 0.5:
            box = _cover_box(w, h, w, h, zoom, cx, cy)
            arr = np.asarray(Image.fromarray(arr).resize((w, h), Image.BILINEAR, box=box))
        self._last_key, self._last = ck, arr
        return arr

    def close(self):
        for rd in self.readers.values():
            rd.close()
        self.readers.clear()


class MediaPool:
    def __init__(self, base_dir: Path, fps: float, grade=None):
        self.base = Path(base_dir)
        self.fps = fps
        self.grade = grade
        self.items: dict = {}

    def resolve(self, p) -> Path:
        pp = Path(p)
        if not pp.is_absolute():
            pp = (self.base / pp)
        return pp

    def get(self, spec) -> Media:
        if isinstance(spec, dict):
            path = spec.get("file") or spec.get("tep")
            start = float(spec.get("bat_dau", 0) or 0)
        else:
            path, start = spec, 0.0
        full = self.resolve(path)
        if not full.exists():
            raise SystemExit(f"Không thấy file media: {full}")
        key = (str(full), start)
        m = self.items.get(key)
        if m is None:
            m = Media(str(full), self.fps, self.grade, start)
            self.items[key] = m
        return m

    def close(self):
        for m in self.items.values():
            m.close()
