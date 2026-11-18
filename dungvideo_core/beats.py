"""Dò nhịp (beat) của bài nhạc bằng numpy — không cần librosa.

Cách làm: spectral flux -> đường onset -> ước lượng tempo bằng tự tương quan
-> dò beat theo lưới tempo + tinh chỉnh từng beat. Thêm dò điểm "drop"
(lúc nhạc bùng lên) để trước drop cắt chậm, sau drop cắt dồn theo beat.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

import numpy as np

from .util import ffmpeg_bin

SR = 22050
HOP = 512
NFFT = 2048


@dataclass
class BeatInfo:
    bpm: float
    beats: np.ndarray            # thời điểm beat (giây)
    duration: float
    drop: float | None = None
    strengths: np.ndarray = field(default_factory=lambda: np.zeros(0))

    @property
    def period(self) -> float:
        return 60.0 / self.bpm

    def after(self, t: float) -> int:
        """Chỉ số beat đầu tiên >= t."""
        return int(np.searchsorted(self.beats, t - 1e-6))


def load_audio(path: str, sr: int = SR, start: float = 0.0, max_sec: float | None = None) -> np.ndarray:
    cmd = [ffmpeg_bin(), "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if max_sec:
        cmd += ["-t", f"{max_sec:.3f}"]
    cmd += ["-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def _onset_env(y: np.ndarray):
    y = np.pad(y, (NFFT // 2, NFFT // 2))
    n = 1 + (len(y) - NFFT) // HOP
    if n < 8:
        z = np.zeros(8, np.float32)
        return z, z, z
    base = np.arange(NFFT)[None, :]
    win = np.hanning(NFFT).astype(np.float32)
    env = np.zeros(n, np.float32)
    low = np.zeros(n, np.float32)
    rms = np.zeros(n, np.float32)
    nlow = max(4, int(250 * NFFT / SR))  # các bin dưới ~250 Hz (tiếng kick/bass)
    prev = None
    step = 256  # xử lý theo khối để đỡ tốn RAM
    for s in range(0, n, step):
        idx = base + HOP * np.arange(s, min(s + step, n))[:, None]
        fr = y[idx] * win
        rms[s:s + step] = np.sqrt((fr ** 2).mean(1))
        mag = np.log1p(10 * np.abs(np.fft.rfft(fr, axis=1)).astype(np.float32))
        if prev is not None:
            mag_full = np.vstack([prev[None, :], mag])
        else:
            mag_full = np.vstack([mag[:1], mag])
        dif = np.maximum(0, np.diff(mag_full, axis=0))
        env[s:s + step] = dif.sum(1)
        low[s:s + step] = dif[:, 1:nlow].sum(1)
        prev = mag[-1]
    # bỏ xu hướng chậm, chuẩn hoá, cộng thêm trọng số dải trầm
    k = max(3, int(0.4 * SR / HOP))

    def norm(e):
        ma = np.convolve(e, np.ones(k) / k, mode="same")
        e = np.maximum(e - ma, 0)
        return e / (e.std() or 1.0)

    low_n = norm(low)
    return norm(env) + 1.5 * low_n, rms, low_n


def _tempo(env: np.ndarray, lo_bpm: float = 70, hi_bpm: float = 180, prior: float = 118) -> float:
    n = len(env)
    f = np.fft.rfft(env - env.mean(), 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    fps = SR / HOP
    lags = np.arange(1, n)
    bpm = 60 * fps / lags
    ok = (bpm >= lo_bpm) & (bpm <= hi_bpm)
    if not ok.any():
        return prior
    w = np.exp(-0.5 * (np.log2(bpm[ok] / prior) / 0.9) ** 2)
    score = ac[1:][ok] * w
    best = int(lags[ok][int(np.argmax(score))])
    # nội suy parabol quanh đỉnh để tempo chính xác hơn độ phân giải 1 khung
    if 1 <= best < n - 1:
        y0, y1, y2 = ac[best - 1], ac[best], ac[best + 1]
        den = y0 - 2 * y1 + y2
        if den < 0:
            best = best + 0.5 * (y0 - y2) / den
    return float(60 * fps / best)


def _track(env: np.ndarray, low: np.ndarray, bpm: float) -> np.ndarray:
    """Dò beat theo lưới tempo cố định: chọn pha tốt nhất (ưu tiên dải trầm = tiếng kick),
    rồi tinh chỉnh từng beat về đỉnh onset gần nhất (±10% chu kỳ) để bám theo nhạc lệch nhịp nhẹ."""
    fps = SR / HOP
    P = 60 * fps / bpm
    n = len(env)
    sc = env + 2.0 * low
    best_phi, best_v = 0.0, -1.0
    for phi in np.arange(0, P, 0.5):
        idx = np.round(np.arange(phi, n, P)).astype(int)
        idx = idx[idx < n]
        v = float(sc[idx].sum()) / max(len(idx), 1)
        if v > best_v:
            best_phi, best_v = phi, v
    thr = sc.mean() + sc.std()
    w = max(1, int(round(0.1 * P)))
    out = []
    x = best_phi
    while x < n:
        xi = int(round(x))
        lo, hi = max(0, xi - w), min(n, xi + w + 1)
        seg = sc[lo:hi]
        adj = float(xi)
        if len(seg):
            j = int(np.argmax(seg))
            if seg[j] > thr:
                adj = float(lo + j)
        out.append(adj)
        x = 0.5 * (adj + x) + P
    return np.array(out)


_CACHE: dict = {}


def detect(path: str, start: float = 0.0, max_sec: float | None = 240.0) -> BeatInfo:
    import os
    key = (str(path), float(start), os.path.getmtime(path))
    if key in _CACHE:
        return _CACHE[key]
    info = _detect(path, start, max_sec)
    _CACHE[key] = info
    return info


def _detect(path: str, start: float, max_sec: float | None) -> BeatInfo:
    y = load_audio(path, start=start, max_sec=max_sec)
    dur = len(y) / SR
    env, rms, low = _onset_env(y)
    bpm = _tempo(env)
    fr = _track(env, low, bpm)
    times = fr * HOP / SR + 0.03  # bù độ trễ cửa sổ STFT (onset bị phát hiện sớm ~30 ms)
    # nội suy beat thiếu ở đầu bài
    period = 60 / bpm
    if len(times) and times[0] > period * 1.5:
        pre = np.arange(times[0] - period, 0, -period)[::-1]
        times = np.concatenate([pre, times])
    times = times[(times >= 0) & (times < dur)]
    strengths = env[np.clip((times * SR / HOP).astype(int), 0, len(env) - 1)] if len(times) else np.zeros(0)
    # dò drop: năng lượng làm mượt vượt 80% cực đại lần đầu (sau giây thứ 3)
    drop = None
    if len(rms) > 10:
        k = max(3, int(2.0 * SR / HOP))
        sm = np.convolve(rms, np.ones(k) / k, mode="same")
        thr = 0.8 * sm.max()
        idx = np.where(sm >= thr)[0]
        if len(idx):
            t = idx[0] * HOP / SR
            if 3.0 < t < dur * 0.7:
                j = np.searchsorted(times, t)
                drop = float(times[min(j, len(times) - 1)]) if len(times) else t
    return BeatInfo(bpm=bpm, beats=times, duration=dur, drop=drop, strengths=strengths)


def synthetic(duration: float, bpm: float = 120.0) -> BeatInfo:
    p = 60 / bpm
    beats = np.arange(0, duration + p, p)
    return BeatInfo(bpm=bpm, beats=beats, duration=duration, drop=None, strengths=np.ones(len(beats)))
