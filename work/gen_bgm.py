# -*- coding: utf-8 -*-
"""
gen_bgm.py —— 原创背景音乐合成（纯标准库，无第三方依赖）

程序即时合成的"原创电子音乐"，版权归生成者，以 MIT 许可证随本项目发布。
不抓取/复制任何商业或术力口曲目（那些仅作推荐清单展示，见 bgm_candidates.json）。
参数化生成 10 首不同氛围的循环 BGM 到 data/bgm/。
"""
import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "bgm"
OUT.mkdir(parents=True, exist_ok=True)
SR = 44100


def freq(midi):
    return 440.0 * (2 ** ((midi - 69) / 12.0))


def osc(n, f, wave_="sine"):
    out = [0.0] * n; w = 2 * math.pi * f / SR
    if wave_ == "sine":
        for i in range(n):
            out[i] = math.sin(w * i)
    elif wave_ == "triangle":
        for i in range(n):
            out[i] = 4 * abs((f * i / SR) % 1.0 - 0.5) - 1
    elif wave_ == "saw":
        for i in range(n):
            out[i] = 2 * ((f * i / SR) % 1.0) - 1
    return out


def env(n, attack=0.01, release=0.15, sustain=0.8):
    e = [0.0] * n; a = max(1, int(attack * SR)); r = max(1, int(release * SR))
    for i in range(n):
        if i < a:
            e[i] = i / a
        elif i > n - r:
            e[i] = max(0.0, (n - i) / r) * sustain
        else:
            e[i] = sustain
    return e


def note(f, dur, wave_="sine", vol=0.5, attack=0.01, release=0.2, sustain=0.8):
    n = int(dur * SR); o = osc(n, f, wave_); e = env(n, attack, release, sustain)
    return [o[i] * e[i] * vol for i in range(n)]


def kick(dur=0.20, vol=0.8):
    n = int(dur * SR); out = [0.0] * n; phase = 0.0
    for i in range(n):
        t = i / SR; f = 120 * math.exp(-t * 22) + 40
        phase += 2 * math.pi * f / SR
        out[i] = math.sin(phase) * math.exp(-t * 16) * vol
    return out


def hat(dur=0.05, vol=0.22):
    n = int(dur * SR); out = [0.0] * n; rng = random.Random(99)
    for i in range(n):
        out[i] = (rng.random() * 2 - 1) * math.exp(-(i / SR) * 90) * vol
    return out


def render(total_dur, events):
    total = int(total_dur * SR); buf = [0.0] * total
    for start, smp in events:
        s0 = int(start * SR)
        for i, v in enumerate(smp):
            j = s0 + i
            if 0 <= j < total:
                buf[j] += v
    peak = max(1e-6, max(abs(x) for x in buf)); scale = 0.55 / peak
    data = bytearray()
    for x in buf:
        data += struct.pack("<h", int(max(-1, min(1, x * scale)) * 32767))
    return bytes(data)


def write_wav(path, pcm):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)


# 和弦（midi）
Am = [45, 57, 60, 64]; F = [41, 53, 57, 60]; C = [48, 60, 64, 67]; G = [43, 55, 59, 62]
Em = [40, 52, 55, 59]; Dm = [38, 50, 53, 57]
PROGS = {
    "pop": [Am, F, C, G], "bright": [C, G, Am, F],
    "sad": [Am, Em, F, C], "dark": [Am, Dm, Em, Am],
}


def build(prog, secs, chord_len, lead_step=None, lead_wave="saw",
          drums=False, bass=False, transpose=0):
    ev = []; t = 0.0; ci = 0
    seq = [0, 1, 2, 3, 2, 1]
    while t < secs:
        ch = [m + transpose for m in prog[ci % len(prog)]]
        for m in ch:
            ev.append((t, note(freq(m), chord_len, "triangle", 0.15, 0.05, chord_len * 0.5, 0.85)))
        if bass:
            ev.append((t, note(freq(ch[0] - 12), chord_len, "sine", 0.20, 0.02, chord_len * 0.4)))
        if lead_step:
            tt = t; k = 0
            while tt < t + chord_len:
                m = ch[seq[k % len(seq)]] + 12
                ev.append((tt, note(freq(m), lead_step * 0.9, lead_wave, 0.12, 0.005, 0.08, 0.6)))
                tt += lead_step; k += 1
        if drums:
            ev.append((t, kick())); ev.append((t + chord_len / 2, hat()))
        t += chord_len; ci += 1
    return render(secs, ev)


TRACKS = [
    ("bgm_01_ambient",  dict(prog=PROGS["pop"],    secs=32, chord_len=4.0)),
    ("bgm_02_arpeggio", dict(prog=PROGS["bright"], secs=28, chord_len=2.0, lead_step=0.25, drums=True)),
    ("bgm_03_chill",    dict(prog=PROGS["pop"],    secs=30, chord_len=3.0, bass=True, drums=True)),
    ("bgm_04_pulse",    dict(prog=PROGS["dark"],   secs=28, chord_len=1.0, bass=True, drums=True)),
    ("bgm_05_dreamy",   dict(prog=PROGS["sad"],    secs=32, chord_len=4.0, transpose=2)),
    ("bgm_06_drive",    dict(prog=PROGS["bright"], secs=26, chord_len=1.0, lead_step=0.2, lead_wave="saw", drums=True, transpose=-2)),
    ("bgm_07_lofi",     dict(prog=PROGS["sad"],    secs=30, chord_len=2.0, bass=True, drums=True, transpose=-3)),
    ("bgm_08_neon",     dict(prog=PROGS["dark"],   secs=28, chord_len=1.0, lead_step=0.25, bass=True, drums=True, transpose=3)),
    ("bgm_09_calm",     dict(prog=PROGS["pop"],    secs=32, chord_len=4.0, transpose=5)),
    ("bgm_10_groove",   dict(prog=PROGS["bright"], secs=28, chord_len=2.0, bass=True, drums=True, transpose=1)),
    ("bgm_11_warm",     dict(prog=PROGS["pop"],    secs=30, chord_len=3.0, bass=True, transpose=3)),
    ("bgm_12_spark",    dict(prog=PROGS["bright"], secs=26, chord_len=1.0, lead_step=0.2, drums=True, transpose=4)),
    ("bgm_13_dusk",     dict(prog=PROGS["sad"],    secs=32, chord_len=4.0, bass=True, transpose=-2)),
    ("bgm_14_rush",     dict(prog=PROGS["dark"],   secs=26, chord_len=1.0, lead_step=0.2, bass=True, drums=True)),
    ("bgm_15_float",    dict(prog=PROGS["pop"],    secs=30, chord_len=2.0, lead_step=0.5, lead_wave="sine", transpose=2)),
    ("bgm_16_night",    dict(prog=PROGS["sad"],    secs=32, chord_len=4.0, lead_step=0.5, lead_wave="triangle", transpose=-4)),
]

if __name__ == "__main__":
    import time
    t0 = time.time()
    for name, kw in TRACKS:
        pcm = build(**kw)
        p = OUT / f"{name}.wav"
        write_wav(p, pcm)
        print(f"  {name}.wav  {p.stat().st_size/1024:.0f} KB  {len(pcm)//2/SR:.1f}s")
    # 清掉旧的不在列表里的 wav
    keep = {f"{n}.wav" for n, _ in TRACKS}
    for f in OUT.glob("*.wav"):
        if f.name not in keep:
            f.unlink(); print("  removed old", f.name)
    print(f"done: {len(TRACKS)} 首原创 BGM -> {OUT}  耗时 {time.time()-t0:.1f}s")