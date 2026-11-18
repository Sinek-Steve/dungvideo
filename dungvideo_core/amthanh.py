"""Âm thanh tự tổng hợp bằng code: nhạc nền theo phong cách + tiếng động (whoosh, hit, pop...).
Mọi âm thanh do code tạo ra nên không vướng bản quyền khi đăng TikTok/Facebook.

Lệnh: python dungvideo.py tao-nhac            -> tạo thư viện nhạc trong nhac/ và tiếng động trong tieng_dong/
Cần numpy + scipy (chỉ lúc tạo thư viện; lúc dựng video chỉ đọc file WAV/MP3 đã tạo).
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from .util import ROOT, ffmpeg_bin

SR = 44100
NHAC_DIR = ROOT / "nhac"
SFX_DIR = ROOT / "tieng_dong"


# ------------------------------------------------------------------ tiện ích tín hiệu
def _n(sec: float) -> int:
    return max(1, int(round(sec * SR)))


def _t(n: int) -> np.ndarray:
    return np.arange(n) / SR


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


_SOS: dict = {}


def _sos(kind: str, fc, order: int = 2):
    from scipy.signal import butter
    key = (kind, tuple(round(float(v), 1) for v in np.atleast_1d(fc)), order)
    sos = _SOS.get(key)
    if sos is None:
        wn = np.clip(np.atleast_1d(np.asarray(fc, float)) / (SR / 2), 1e-4, 0.99)
        sos = butter(order, wn if len(wn) > 1 else wn[0],
                     btype={"lp": "lowpass", "hp": "highpass", "bp": "bandpass"}[kind], output="sos")
        _SOS[key] = sos
    return sos


def filt(x, kind: str, fc, order: int = 2):
    from scipy.signal import sosfilt
    return np.asarray(sosfilt(_sos(kind, fc, order), x))


def sweep(x, kind: str, f0: float, f1: float, blocks: int = 48):
    """Bộ lọc quét tần số theo thời gian (riser, filter mở dần); giữ trạng thái bộ lọc giữa các khối."""
    from scipy.signal import sosfilt, sosfilt_zi
    edges = np.linspace(0, len(x), blocks + 1).astype(int)
    out = np.zeros(len(x))
    zi = None
    for i in range(blocks):
        sos = _sos(kind, f0 * (f1 / f0) ** (i / max(blocks - 1, 1)))
        seg = x[edges[i]:edges[i + 1]]
        if not len(seg):
            continue
        if zi is None:
            zi = sosfilt_zi(sos) * seg[0]
        out[edges[i]:edges[i + 1]], zi = sosfilt(sos, seg, zi=zi)
    return out


def osc(kind: str, f, n: int, phase: float = 0.0) -> np.ndarray:
    f = np.broadcast_to(np.asarray(f, np.float64), (n,))
    ph = (phase + np.cumsum(f) / SR) % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    if kind == "saw":
        return 2 * ph - 1
    if kind == "square":
        return np.where(ph < 0.5, 1.0, -1.0)
    return 4 * np.abs(ph - 0.5) - 1  # tri


def adsr(n: int, a=0.005, d=0.1, s=0.7, r=0.1) -> np.ndarray:
    t = _t(n)
    dur = n / SR
    env = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = t > dur - r
    env[rel] *= np.clip((dur - t[rel]) / max(r, 1e-4), 0, 1)
    return env


def fade_tail(x, sec=0.02):
    k = min(len(x), _n(sec))
    x[-k:] *= np.linspace(1, 0, k)
    return x


def add(buf, sig, t: float, gain: float = 1.0, pan: float = 0.0):
    """Cộng tín hiệu (mono hoặc stereo) vào buf stereo tại giây t."""
    i = int(round(t * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    j0 = max(0, -i)
    sig = sig[j0:len(buf) - i]
    i = max(i, 0)
    if sig.ndim == 1:
        l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
        buf[i:i + len(sig), 0] += sig * gain * l * 1.414
        buf[i:i + len(sig), 1] += sig * gain * r * 1.414
    else:
        buf[i:i + len(sig)] += sig * gain


def reverb(x, sec=1.6, wet=0.25, seed=0):
    from scipy.signal import fftconvolve
    rng = np.random.default_rng(seed)
    n = _n(sec)
    env = np.exp(-_t(n) * 6.9 / sec)
    out = np.empty_like(x)
    for c in range(x.shape[1]):
        ir = filt(rng.standard_normal(n), "lp", 5000) * env
        ir[: _n(0.012)] = 0  # pre-delay
        ir /= np.sqrt((ir ** 2).sum()) + 1e-9
        out[:, c] = fftconvolve(x[:, c], ir)[: len(x)]
    return x + out * wet


def norm_rms(x, db: float):
    act = x[np.abs(x).max(axis=-1) > 1e-4] if x.ndim > 1 else x[np.abs(x) > 1e-4]
    r = np.sqrt((act ** 2).mean()) if len(act) else 0
    return x * (10 ** (db / 20) / r) if r > 0 else x


# ------------------------------------------------------------------ nhạc cụ
def kick(rng, f0=160, f1=48, dec=8.0):
    n = _n(0.5)
    t = _t(n)
    x = osc("sine", f1 + (f0 - f1) * np.exp(-t * 32), n) * np.exp(-t * dec)
    c = filt(rng.standard_normal(_n(0.006)), "hp", 2500) * 0.4
    x[: len(c)] += c
    return np.tanh(1.6 * x)


def k808(f, dur, glide_from=None):
    n = _n(dur)
    t = _t(n)
    ff = np.full(n, float(f))
    if glide_from:
        ff = f + (glide_from - f) * np.exp(-t * 14)
    ff = ff * (1 + 0.7 * np.exp(-t * 45))
    x = osc("sine", ff, n) * np.minimum(1, t / 0.003) * np.exp(-t * 1.3)
    return fade_tail(np.tanh(2.4 * x) * 0.85, 0.03)


def snare(rng):
    n = _n(0.28)
    t = _t(n)
    nz = filt(rng.standard_normal(n), "bp", (1200, 8000)) * np.exp(-t * 17)
    tone = osc("sine", 190 * (1 + 0.3 * np.exp(-t * 40)), n) * np.exp(-t * 28)
    return nz * 0.9 + tone * 0.6


def clap(rng):
    n = _n(0.32)
    t = _t(n)
    nz = filt(rng.standard_normal(n), "bp", (900, 3800))
    env = sum(np.where(t >= o, np.exp(-(t - o) * 160), 0) for o in (0, 0.011, 0.023))
    env += np.where(t >= 0.03, 0.7 * np.exp(-(t - 0.03) * 13), 0)
    return nz * env


def hat(rng, open_=False):
    n = _n(0.42 if open_ else 0.07)
    t = _t(n)
    return filt(rng.standard_normal(n), "hp", 7500) * np.exp(-t * (9 if open_ else 65)) * 0.6


def cowbell(f):
    n = _n(0.3)
    t = _t(n)
    x = osc("square", f, n) + osc("square", f * 1.48, n)
    return filt(x, "bp", (f * 0.8, min(f * 5, 15000))) * np.exp(-t * 11) * 0.5


def tom(rng, f=70):
    n = _n(0.9)
    t = _t(n)
    x = osc("sine", f * (1 + 1.2 * np.exp(-t * 20)), n) * np.exp(-t * 4.5)
    x += filt(rng.standard_normal(n), "lp", 900) * np.exp(-t * 14) * 0.5
    return np.tanh(1.4 * x)


def pluck(f, dur, bright=1.0, dec=7.0):
    n = _n(dur)
    t = _t(n)
    x = osc("saw", f, n) + 0.7 * osc("saw", f * 1.007, n, 0.3)
    x = filt(x, "lp", min(f * 7 * bright, 14000)) * np.exp(-t * dec)
    return fade_tail(x * 0.6)


def bell(f, dur):
    n = _n(dur)
    t = _t(n)
    x = osc("sine", f, n) + 0.5 * osc("sine", f * 2.0, n) * np.exp(-t * 6) + 0.25 * osc("sine", f * 3.01, n) * np.exp(-t * 9)
    return fade_tail(x * np.exp(-t * 3.2) * 0.6)


def supersaw(freqs, dur, rng, cutoff=3500, a=0.02, r=0.2, voices=5, spread=0.014):
    n = _n(dur)
    out = np.zeros((n, 2))
    for f in freqs:
        for v in range(voices):
            k = (v - (voices - 1) / 2) / max((voices - 1) / 2, 1)
            x = osc("saw", f * (1 + spread * k), n, rng.random())
            pan = 0.85 * k
            out[:, 0] += x * np.sqrt(0.5 * (1 - pan))
            out[:, 1] += x * np.sqrt(0.5 * (1 + pan))
    out = filt(out.T, "lp", cutoff).T if cutoff else out
    return out * adsr(n, a, 0.4, 0.8, r)[:, None] / (len(freqs) * voices) ** 0.5


def epiano(freqs, dur):
    n = _n(dur)
    t = _t(n)
    x = sum(osc("sine", f, n) + 0.22 * osc("sine", 2 * f, n) * np.exp(-t * 5) for f in freqs)
    x = x * np.exp(-t * 1.6) * (1 + 0.12 * np.sin(2 * np.pi * 4.5 * t))
    return fade_tail(x / len(freqs), 0.08)


def braam(f, dur, rng):
    n = _n(dur)
    t = _t(n)
    x = sum(osc("saw", f * m * (1 + 0.004 * k), n, rng.random()) for m in (1, 1.5, 2) for k in (-1, 1))
    x = filt(x, "lp", 700) * np.minimum(1, t / 0.35) * np.exp(-t * 0.7)
    return fade_tail(np.tanh(x * 0.5), 0.2)


def bass_note(f, dur, kind="saw"):
    n = _n(dur)
    if kind == "sub":
        x = osc("sine", f, n) + 0.15 * osc("sine", 2 * f, n)
    else:
        x = filt(osc("saw", f, n), "lp", 380) + 0.6 * osc("sine", f, n)
    return fade_tail(x * adsr(n, 0.004, 0.15, 0.7, 0.04) * 0.7)


# ------------------------------------------------------------------ tiếng động (dùng cả trong nhạc lẫn lúc dựng)
def riser(dur, rng):
    n = _n(dur)
    t = _t(n)
    x = sweep(rng.standard_normal(n), "hp", 250, 9000)
    x += 0.3 * osc("sine", 180 * 2 ** (3 * t / dur), n)
    return x * (t / dur) ** 2 * 0.5


def impact(rng):
    n = _n(2.0)
    t = _t(n)
    x = osc("sine", 38 + 40 * np.exp(-t * 5), n) * np.exp(-t * 2.2)
    x += filt(rng.standard_normal(n), "lp", 2200) * np.exp(-t * 9) * 0.6
    return np.tanh(1.5 * x)


def downlifter(dur, rng):
    n = _n(dur)
    t = _t(n)
    return sweep(rng.standard_normal(n), "lp", 9000, 200) * (1 - t / dur) ** 1.5 * 0.5


def whoosh(dur, rng):
    n = _n(dur)
    t = _t(n)
    half = n // 2
    x = rng.standard_normal(n)
    y = np.concatenate([sweep(x[:half], "lp", 400, 6000, 24), sweep(x[half:], "lp", 6000, 500, 24)])
    return y * np.sin(np.pi * t / dur) ** 2 * 0.9


def pop():
    n = _n(0.09)
    t = _t(n)
    return osc("sine", 300 + 700 * np.exp(-t * 60), n) * np.exp(-t * 40) * 0.9


def hit(rng):
    n = _n(0.5)
    t = _t(n)
    x = osc("sine", 60 * (1 + 2 * np.exp(-t * 30)), n) * np.exp(-t * 9)
    x += filt(rng.standard_normal(n), "bp", (400, 5000)) * np.exp(-t * 22) * 0.8
    return np.tanh(1.8 * x)


def glitch(rng):
    n = _n(0.18)
    gate = np.repeat(rng.random(18) > 0.45, n // 18 + 1)[:n]
    return (osc("square", 1800, n) * 0.3 + rng.standard_normal(n) * 0.4) * gate * 0.6


def tick(rng):
    n = _n(0.035)
    return filt(rng.standard_normal(n), "hp", 4000) * np.exp(-_t(n) * 90)


def tao_tieng_dong(out_dir: Path = SFX_DIR) -> list:
    """Tạo thư viện tiếng động WAV để chèn vào điểm cắt lúc dựng."""
    rng = np.random.default_rng(7)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = {"whoosh": whoosh(0.45, rng), "whoosh_ngan": whoosh(0.25, rng), "hit": hit(rng), "pop": pop(),
             "impact": impact(rng), "riser": riser(2.0, rng), "glitch": glitch(rng), "tick": tick(rng)}
    paths = []
    for name, x in items.items():
        x = np.asarray(x, np.float64)
        x = x / (np.abs(x).max() + 1e-9) * 0.9
        p = out_dir / f"{name}.wav"
        _write_wav(p, np.stack([x, x], 1))
        paths.append(p)
    return paths


# ------------------------------------------------------------------ soạn nhạc
STYLES = {
    #            bpm          nửa nhịp  bộ trống      bass      hợp âm        giai điệu  sidechain swing
    "trap":        dict(bpm=(136, 148), half=True, kit="trap", bass="808", chord="pad", lead="bell", sc=0.0),
    "drill":       dict(bpm=(138, 146), half=True, kit="drill", bass="808_truot", chord="pad", lead="bell", sc=0.0),
    "phonk":       dict(bpm=(126, 136), kit="phonk", bass="808", chord=None, lead="cowbell", sc=0.0, scale="phrygian"),
    "house":       dict(bpm=(122, 126), kit="house", bass="offbeat", chord="stab", lead="pluck", sc=0.45),
    "techno":      dict(bpm=(126, 130), kit="techno", bass="rumble", chord="stab", lead=None, sc=0.5),
    "edm":         dict(bpm=(126, 128), kit="edm", bass="saw8", chord="supersaw", lead="pluck", sc=0.6),
    "future_bass": dict(bpm=(140, 150), half=True, kit="fb", bass="808", chord="supersaw", lead="pluck_cao", sc=0.75),
    "synthwave":   dict(bpm=(100, 112), kit="synthwave", bass="octave", chord="pad", lead="arp", sc=0.3),
    "lofi":        dict(bpm=(78, 88), kit="lofi", bass="sub", chord="epiano", lead=None, sc=0.0, swing=0.14,
                        vinyl=True, short=True),
    "hiphop":      dict(bpm=(86, 94), kit="boombap", bass="sub", chord="epiano", lead="pluck_em", sc=0.0, swing=0.08,
                        short=True),
    "cinematic":   dict(bpm=(90, 100), kit="cine", bass="braam", chord="strings", lead=None, sc=0.0, short=True),
}

KITS = {  # 16 bước mỗi ô nhịp: k = kick, s = snare/clap, h = hi-hat đóng, o = hi-hat mở
    "trap": dict(k=["x.....x...x.....", "x......x..x...x."], s=["........x......."], h=["x.x.x.x.x.x.x.x."],
                 roll=True, clap=True),
    "drill": dict(k=["x......x..x.....", "x.....x....x...."], s=["........x.....x."], h=["x..x..x.x..x..x."],
                  roll=True, clap=False),
    "phonk": dict(k=["x..x..x...x.x...", "x..x..x...x...x."], s=["....x.......x..."], h=["xxxxxxxxxxxxxxxx"],
                  clap=True),
    "house": dict(k=["x...x...x...x..."], s=["....x.......x..."], h=["x.x.x.x.x.x.x.x."], o=["..x...x...x...x."],
                  clap=True),
    "techno": dict(k=["x...x...x...x..."], s=["....x.......x..."], h=["xxxxxxxxxxxxxxxx"], o=["..x...x...x...x."],
                   clap=True),
    "edm": dict(k=["x...x...x...x..."], s=["....x.......x..."], h=["..x...x...x...x."], clap=True),
    "fb": dict(k=["x.........x.....", "x......x..x....."], s=["........x......."], h=["x.x.x.x.x.x.x.x."],
               clap=True),
    "synthwave": dict(k=["x.......x.......", "x.......x.x....."], s=["....x.......x..."], h=["x.x.x.x.x.x.x.x."],
                      clap=False),
    "lofi": dict(k=["x......x..x.....", "x.........x...x."], s=["....x.......x..."], h=["x.x.x.x.x.x.x.x."],
                 clap=False),
    "boombap": dict(k=["x......x..x.....", "x.x.......x....."], s=["....x.......x..."], h=["x.x.x.x.x.x.x.x."],
                    clap=False),
    "cine": dict(k=[], s=[], h=[], tom=["x.....x...x.....", "x..x..x.x......."]),
}

PROGS = [["i", "VI", "III", "VII"], ["i", "iv", "VI", "V"], ["VI", "VII", "i", "i"], ["i", "VII", "VI", "VII"],
         ["i", "VI", "iv", "V"], ["iv", "VI", "i", "VII"], ["i", "iv", "i", "V"], ["VI", "iv", "i", "V"]]
DEG = {"i": 0, "ii": 2, "III": 3, "iv": 5, "v": 7, "V": 7, "VI": 8, "VII": 10}
SCALES = {"minor": [0, 2, 3, 5, 7, 8, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10]}


def _chord(sym: str, root: int, seventh: bool):
    r = root + DEG[sym]
    minor = sym.islower()
    iv = [0, 3, 7] if minor else [0, 4, 7]
    if seventh:
        iv.append(10 if minor or sym == "V" else 11)
    return r, [r + x for x in iv]


def _steps(pat: str, bar0: float, step: float, swing: float = 0.0):
    for i, c in enumerate(pat):
        if c == "x":
            yield bar0 + i * step + (swing * step if i % 2 else 0.0)


def compose(style: str, seed: int):
    """Soạn một bài: trả về (stereo float32, thông tin)."""
    st = STYLES[style]
    rng = np.random.default_rng(seed)
    bpm = float(rng.integers(st["bpm"][0], st["bpm"][1] + 1))
    beat = 60 / bpm
    bar = beat * 4
    step = bar / 16
    swing = st.get("swing", 0.0)
    plan = ([("intro", 1), ("build", 1), ("drop", 6), ("break", 1), ("drop2", 4), ("outro", 1)] if st.get("short")
            else [("intro", 2), ("build", 2), ("drop", 8), ("break", 2), ("drop2", 6), ("outro", 2)])
    sections = []
    for name, nb in plan:
        sections += [name] * nb
    total = len(sections) * bar + 2.5
    N = _n(total)
    kit = KITS[st["kit"]]
    root = int(rng.integers(45, 53))  # A2..E3
    prog = PROGS[int(rng.integers(len(PROGS)))]
    seventh = st["chord"] == "epiano" or style == "synthwave"
    scale = SCALES[st.get("scale", "minor")]
    kpat = int(rng.integers(len(kit["k"]))) if kit["k"] else 0
    bus = {k: np.zeros((N, 2)) for k in ("kick", "bass", "drum", "hat", "chord", "lead", "fx")}
    kick_times = []
    drop_t = plan[0][1] * bar + plan[1][1] * bar
    s_kick, s_snare, s_clap = kick(rng), snare(rng), clap(rng)
    s_hat, s_open = hat(rng), hat(rng, True)
    # motif giai điệu 2 ô nhịp (8 nốt móc đơn mỗi ô), lặp có biến tấu
    rhythm = [rng.random() < p for p in (0.95, 0.4, 0.75, 0.55, 0.85, 0.35, 0.7, 0.5)] * 2
    motif = [int(rng.choice([0, 2, 4, 2, 0, 4, 6, 1])) for _ in range(16)]

    for bi, sec in enumerate(sections):
        t0 = bi * bar
        sym = prog[bi % 4]
        croot, notes = _chord(sym, root, seventh)
        full = sec in ("drop", "drop2")
        last_build = sec == "build" and (bi + 1 < len(sections) and sections[bi + 1] != "build")
        # ---------- trống
        if kit["k"] and (full or (sec == "build" and st["kit"] in ("house", "techno", "edm", "synthwave"))
                         or (sec == "outro" and bi == sections.index("outro"))):
            pat = kit["k"][(kpat + (bi % 2 if full else 0)) % len(kit["k"])] if full else "x...x...x...x..."
            for tk in _steps(pat, t0, step, swing):
                if last_build and tk - t0 > bar * 0.875:
                    continue
                add(bus["kick"], s_kick, tk)
                kick_times.append(tk)
        if full and kit["s"]:
            for ts in _steps(kit["s"][0], t0, step, swing):
                add(bus["drum"], s_clap if kit.get("clap") else s_snare, ts)
                if style in ("trap", "drill", "fb"):
                    add(bus["drum"], s_snare, ts, 0.5)
        if full or sec == "intro" or (sec == "break" and st["kit"] in ("trap", "drill", "lofi", "boombap")):
            soft = 1.0 if full or st["kit"] in ("trap", "drill", "lofi", "boombap") else 0.45  # intro: hi-hat nhẹ
            for i, th in enumerate(_steps(kit["h"][0] if kit["h"] else "", t0, step, swing)):
                add(bus["hat"], s_hat, th, (0.55 + 0.45 * (i % 2 == 0)) * soft, pan=0.25)
            if kit.get("roll") and full and rng.random() < 0.6:  # cuộn hi-hat kiểu trap
                tr = t0 + step * int(rng.choice([6, 12, 14]))
                for j in range(6):
                    add(bus["hat"], s_hat, tr + j * step / 3, 0.6, pan=0.25)
            if kit.get("o") and full:
                for th in _steps(kit["o"][0], t0, step):
                    add(bus["hat"], s_open, th, 0.5, pan=-0.2)
        if kit.get("tom") and (full or sec == "build"):
            for tt in _steps(kit["tom"][bi % 2], t0, step):
                add(bus["drum"], tom(rng, 65 if tt == t0 else 90), tt)
        if sec == "build":  # snare dồn dập (trừ lofi/hiphop/cinematic) + riser
            k = sections.index("build")
            nb = sections.count("build")
            pos = (bi - k) / nb
            sub = 4 if pos < 0.5 else 8
            for j in range(int(4 * sub)) if st["kit"] not in ("lofi", "boombap", "cine") else ():
                tt = t0 + j * bar / (4 * sub)
                if last_build and tt - t0 > bar * 0.875:
                    break
                add(bus["drum"], s_snare, tt, 0.25 + 0.6 * (pos + j / (4 * sub) / nb))
            if bi == k:
                add(bus["fx"], riser(nb * bar, rng), t0, 0.35 if st["kit"] in ("lofi", "boombap") else 0.9)
        if sec in ("drop", "drop2") and sections[bi - 1] not in ("drop", "drop2"):
            add(bus["fx"], impact(rng), t0, 0.9)
            add(bus["hat"], hat(rng, True), t0, 1.0)
        if sec == "break" and sections[bi - 1] != "break":
            add(bus["fx"], downlifter(bar, rng), t0, 0.7)
        if sec == "break" and (bi + 1 < len(sections) and sections[bi + 1] == "drop2"):
            add(bus["fx"], riser(bar, rng), t0, 0.7)
        # ---------- bass
        bf = hz(croot - 12)
        if full or (sec == "break" and st["bass"] in ("808", "808_truot", "sub")):
            if st["bass"] in ("808", "808_truot"):
                hits = [tk for tk in _steps(kit["k"][kpat % len(kit["k"])] if kit["k"] else "x.......", t0, step)]
                for j, tk in enumerate(hits):
                    end = hits[j + 1] if j + 1 < len(hits) else t0 + bar
                    glide = bf * 2 if st["bass"] == "808_truot" and rng.random() < 0.3 else None
                    add(bus["bass"], k808(bf, max(end - tk, 0.15), glide), tk)
            elif st["bass"] == "offbeat":
                for tb in _steps("..x...x...x...x.", t0, step):
                    add(bus["bass"], bass_note(bf, step * 1.6), tb)
            elif st["bass"] == "saw8":
                for tb in _steps("x.x.x.x.x.x.x.x.", t0, step):
                    add(bus["bass"], bass_note(bf, step * 1.8), tb)
            elif st["bass"] == "octave":
                for j, tb in enumerate(_steps("x.x.x.x.x.x.x.x.", t0, step)):
                    add(bus["bass"], bass_note(bf * (2 if j % 2 else 1), step * 1.7), tb)
            elif st["bass"] == "rumble":
                for tb in _steps("..x...x...x...x.", t0, step):
                    add(bus["bass"], bass_note(bf, step * 2.5, "sub"), tb)
            elif st["bass"] == "sub":
                for tb in _steps(kit["k"][kpat % len(kit["k"])], t0, step, swing):
                    add(bus["bass"], bass_note(bf, beat * 0.9, "sub"), tb)
            elif st["bass"] == "braam":
                add(bus["bass"], braam(bf, bar * 1.05, rng), t0)
        # ---------- hợp âm
        if st["chord"]:
            fr = [hz(m) for m in notes]
            cut = {"intro": 900, "build": 1500 + 2500 * ((bi - sections.index("build") + 1) / 2), "break": 1400,
                   "outro": 1200}.get(sec, 4200)
            if st["chord"] == "supersaw":
                add(bus["chord"], supersaw(fr, bar, rng, cut), t0)
            elif st["chord"] == "pad":
                add(bus["chord"], supersaw(fr, bar, rng, min(cut, 2400), a=0.25, r=0.4, voices=3), t0)
            elif st["chord"] == "strings":
                add(bus["chord"], supersaw(fr, bar * 1.02, rng, min(cut, 1800), a=0.4, r=0.5, voices=4), t0)
            elif st["chord"] == "epiano":
                for tc in (t0, t0 + beat * 2.5) if full else (t0,):
                    add(bus["chord"], epiano(fr, bar * 0.9), tc + swing * step)
            elif st["chord"] == "stab":
                for tc in _steps("x..x..x...x..x..", t0, step) if full else _steps("x.......x.......", t0, step):
                    add(bus["chord"], supersaw(fr, step * 1.5, rng, min(cut, 3000), a=0.003, r=0.05, voices=3), tc)
        # ---------- giai điệu
        lead = st["lead"]
        # không có hợp âm (phonk) thì giai điệu vào luôn từ intro để đầu bài không bị im
        if lead and (full or sec == "break" or (not st["chord"] and sec in ("intro", "build"))):
            hi = 12 if sec == "drop2" else 0
            if lead == "arp":
                order = notes + [notes[1] + 12, notes[2] + 12]
                for j in range(16):
                    add(bus["lead"], pluck(hz(order[j % len(order)] + 12 + hi), step * 1.2, 0.8, 9), t0 + j * step)
            elif lead == "cowbell":
                pat = "x.xx.x.xx.x.x.xx"
                tones = [n - croot for n in notes[:3]] + [12]
                seq = [tones[i] for i in (0, 1, 2, 1, 0, 2, 3, 2)]
                for j, tl in enumerate(_steps(pat, t0, step)):
                    add(bus["lead"], cowbell(hz(croot + 24 + seq[j % len(seq)] + hi)), tl)
            else:
                half = 2 if st.get("half") else 1
                ci = scale.index(DEG[sym]) if DEG[sym] in scale else 0  # bậc của hợp âm trong âm giai
                for j in range(8):
                    if not rhythm[(bi % 2) * 8 + j] or (sec == "break" and j % 2):
                        continue
                    deg = ci + motif[(bi % 2) * 8 + j]  # 0, 2, 4 = nốt trong hợp âm; luôn nằm trong âm giai
                    m = root + 12 + scale[deg % 7] + 12 * (deg // 7)
                    tl = t0 + j * beat / 2 + (swing * step if j % 2 else 0)
                    if lead == "bell":
                        if j % half == 0:
                            add(bus["lead"], bell(hz(m + 12 + hi), beat * 1.5), tl)
                    elif lead == "pluck_em":
                        add(bus["lead"], bell(hz(m + hi), beat), tl, 0.7)
                    else:
                        up = 12 if lead == "pluck_cao" else 0
                        add(bus["lead"], pluck(hz(m + 12 + up + hi), beat * 0.6), tl)

    # ---------- sidechain: hợp âm & bass nhún theo kick
    if st["sc"] > 0 and kick_times:
        g = np.ones(N)
        L = _n(0.3)
        shape = 1 - st["sc"] * np.exp(-_t(L) / 0.09)
        for tk in kick_times:
            i = int(tk * SR)
            seg = g[i:i + L]
            np.minimum(seg, shape[: len(seg)], out=seg)
        bus["chord"] *= g[:, None]
        bus["bass"] *= (1 - (1 - g) * 0.6)[:, None]
    # ---------- trộn
    lvl = {"kick": -13, "bass": -16, "drum": -19, "hat": -27, "chord": -21, "lead": -22, "fx": -24}
    mix = np.zeros((N, 2))
    for k, x in bus.items():
        if np.abs(x).max() < 1e-6:
            continue
        # tiếng động (riser, impact) giữ mức cố định: chuẩn hoá theo RMS sẽ đẩy riser dài lên quá to
        x = x * 0.22 if k == "fx" else norm_rms(x, lvl[k])
        if k in ("drum", "chord", "lead"):
            x = reverb(x, 1.4 if k == "drum" else 2.0, 0.18 if k == "drum" else 0.25, seed)
        if k == "lead":  # tiếng vọng nốt chấm (3/16) trái-phải
            d = _n(step * 3)
            echo = np.zeros_like(x)
            echo[d:, 1] += x[:-d, 0] * 0.35
            echo[2 * d:, 0] += x[:-2 * d, 1] * 0.2
            x = x + echo
        mix += x
    if st.get("vinyl"):
        nz = filt(rng.standard_normal(N), "bp", (800, 6000)) * 0.004
        clicks = (rng.random(N) > 0.99985) * rng.standard_normal(N) * 0.08
        mix += (nz + clicks)[:, None]
    mix = filt(mix.T, "hp", 28).T
    fo = _n(bar)  # outro mờ dần
    end = int(len(sections) * bar * SR)
    mix[end - fo:end] *= np.linspace(1, 0, fo)[:, None] ** 1.5
    mix = mix[: end + _n(0.3)]
    mix = norm_rms(mix, -14.5)
    mix = np.tanh(mix * 1.15) / np.tanh(1.15)
    mix *= 0.95 / (np.abs(mix).max() + 1e-9)
    info = {"phong_cach": style, "bpm": bpm, "tong": int(root), "drop": round(drop_t, 2),
            "do_dai": round(len(mix) / SR, 1), "vong_hop_am": "-".join(prog)}
    return mix.astype(np.float32), info


# ------------------------------------------------------------------ ghi file
def _write_wav(path: Path, x: np.ndarray):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def _write_mp3(path: Path, x: np.ndarray):
    cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
           "-c:a", "libmp3lame", "-b:a", "192k", str(path)]
    subprocess.run(cmd, input=x.astype("<f4").tobytes(), check=True)


def tao_thu_vien(so_moi_kieu: int = 3, kieu: list | None = None, out_dir: Path = NHAC_DIR) -> list:
    """Tạo thư viện nhạc: so_moi_kieu bài cho mỗi phong cách, kèm nhac/danh_sach.yaml."""
    import yaml
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for si, style in enumerate(kieu or list(STYLES)):
        for k in range(so_moi_kieu):
            seed = 1000 * (si + 1) + k
            x, info = compose(style, seed)
            name = f"{style}_{k + 1:02d}_{int(info['bpm'])}bpm.mp3"
            _write_mp3(out_dir / name, x)
            # tempo và drop chính xác (nhạc tự tạo nên biết trước), bộ dò nhịp sẽ đọc file này thay vì đoán
            (out_dir / name).with_suffix(".json").write_text(
                json.dumps({"bpm": info["bpm"], "drop": info["drop"], "tu_tao": True}), encoding="utf-8")
            info["file"] = name
            rows.append(info)
            print(f"  {name:32s} drop {info['drop']:5.1f}s  dài {info['do_dai']:5.1f}s")
    (out_dir / "danh_sach.yaml").write_text(
        "# Thư viện nhạc tự tổng hợp (không bản quyền). drop = giây nhạc bùng lên.\n"
        + yaml.safe_dump(rows, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return rows


def chon_nhac(phong_cach=None, seed=None):
    """Chọn một bài trong thư viện (ưu tiên phong cách cho trước). Trả về Path hoặc None."""
    import random
    import yaml
    f = NHAC_DIR / "danh_sach.yaml"
    if not f.exists():
        return None
    rows = yaml.safe_load(f.read_text(encoding="utf-8")) or []
    want = [phong_cach] if isinstance(phong_cach, str) else list(phong_cach or [])
    pool = [r for r in rows if r.get("phong_cach") in want] or rows
    pool = [r for r in pool if (NHAC_DIR / r["file"]).exists()]
    if not pool:
        return None
    return NHAC_DIR / random.Random(seed).choice(pool)["file"]
