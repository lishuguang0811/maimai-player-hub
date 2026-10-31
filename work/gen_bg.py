# -*- coding: utf-8 -*-
"""
gen_bg.py —— 程序化生成 50 张初音未来主题背景图（JPEG）。

为什么不用真实立绘：初音未来是受版权保护的角色，直接抓取/生成官方立绘
既侵权也不可靠。所以这里用 Pillow 画"初音主题抽象背景"——
青绿色调 + 音波 / 均衡器 / 音符 / 光斑 / 双马尾曲线等元素，
每张用不同随机种子，得到 50 张各不相同的图。纯本地生成，零版权风险。
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
BG_DIR = ROOT / "data" / "bg"
BG_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1600, 1000
N = 50

# 初音未来配色
TEAL = (57, 197, 187)
TEAL_LT = (127, 224, 216)
TEAL_DK = (18, 64, 66)
PINK = (227, 110, 150)
DARK = (13, 17, 23)
WHITE = (235, 250, 248)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(d, c1, c2, diag=False):
    for y in range(H):
        for x in range(0, W, 4):
            t = (x / W * 0.5 + y / H * 0.5) if diag else (y / H)
            d.line([(x, y), (x + 4, y)], fill=lerp(c1, c2, t))


def bokeh(d, rng):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(rng.randint(6, 12)):
        r = rng.randint(40, 160)
        x, y = rng.randint(-50, W + 50), rng.randint(-50, H + 50)
        col = rng.choice([TEAL, TEAL_LT, PINK, WHITE])
        a = rng.randint(18, 55)
        ld.ellipse([x - r, y - r, x + r, y + r], fill=(*col, a))
    layer = layer.filter(ImageFilter.GaussianBlur(28))
    return layer


def sound_waves(img, rng):
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = rng.choice([(0, H), (W, 0), (0, 0), (W, H)])
    col = rng.choice([TEAL, TEAL_LT, WHITE])
    base = rng.randint(60, 140)
    for i in range(rng.randint(5, 9)):
        r = base + i * rng.randint(55, 95)
        a = max(8, 46 - i * 5)
        d.arc([cx - r, cy - r, cx + r, cy + r], start=rng.randint(0, 90),
              end=rng.randint(180, 270), fill=(*col, a), width=rng.randint(2, 5))


def equalizer(img, rng):
    d = ImageDraw.Draw(img, "RGBA")
    n = rng.randint(24, 40)
    bw = W // n
    col = rng.choice([TEAL, TEAL_LT, PINK])
    for i in range(n):
        h = rng.randint(30, 260)
        x = i * bw
        a = rng.randint(30, 70)
        d.rectangle([x + 3, H - h, x + bw - 3, H], fill=(*col, a))


def notes(img, rng):
    """画简笔音符：实心圆 + 符干 + 符尾，不依赖字体，保证不出方框。"""
    d = ImageDraw.Draw(img, "RGBA")
    col = rng.choice([TEAL_LT, WHITE, PINK])
    for _ in range(rng.randint(5, 11)):
        x, y = rng.randint(60, W - 60), rng.randint(60, H - 120)
        s = rng.randint(10, 22)
        a = rng.randint(50, 120)
        d.ellipse([x - s, y - int(s * 0.7), x + s, y + int(s * 0.7)], fill=(*col, a))
        d.line([(x + s, y), (x + s, y - s * 4)], fill=(*col, a), width=3)
        d.line([(x + s, y - s * 4), (x + s + s * 1.4, y - s * 3)], fill=(*col, a), width=3)


def twintails(img, rng):
    """两条柔和曲线，暗示双马尾。"""
    d = ImageDraw.Draw(img, "RGBA")
    col = rng.choice([TEAL, TEAL_LT])
    for side in (-1, 1):
        pts = []
        x0 = W // 2 + side * rng.randint(120, 260)
        for t in range(0, 61):
            tt = t / 60
            x = x0 + side * math.sin(tt * math.pi * rng.uniform(1.2, 2.2)) * 120
            y = int(tt * H)
            pts.append((x, y))
        for i in range(len(pts) - 1):
            a = int(30 + 30 * math.sin(i / 10))
            d.line([pts[i], pts[i + 1]], fill=(*col, max(10, a)), width=rng.randint(3, 7))


def grid(img, rng):
    d = ImageDraw.Draw(img, "RGBA")
    step = rng.randint(70, 110)
    a = rng.randint(8, 18)
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=(*TEAL, a), width=1)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=(*TEAL, a), width=1)


def make(idx):
    rng = random.Random(1000 + idx)
    img = Image.new("RGB", (W, H), DARK)
    # 底色渐变：随机选一组配色和方向
    palettes = [
        (DARK, TEAL_DK), (TEAL_DK, DARK), (DARK, (24, 40, 52)),
        ((10, 26, 30), TEAL_DK), (DARK, (40, 24, 40)),
    ]
    c1, c2 = rng.choice(palettes)
    d = ImageDraw.Draw(img)
    gradient(d, c1, c2, diag=rng.random() < 0.5)

    if rng.random() < 0.7:
        grid(img, rng)
    img = Image.alpha_composite(img.convert("RGBA"), bokeh(d, rng))
    if rng.random() < 0.85:
        sound_waves(img, rng)
    if rng.random() < 0.6:
        twintails(img, rng)
    if rng.random() < 0.8:
        equalizer(img, rng)
    notes(img, rng)

    # 轻微暗角，让前景文字更清晰
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    vd.rectangle([0, 0, W, H], outline=(0, 0, 0, 0))
    for i in range(60):
        a = int(90 * (1 - i / 60))
        vd.rectangle([i, i, W - i, H - i], outline=(0, 0, 0, a // 3))
    vig = vig.filter(ImageFilter.GaussianBlur(30))
    img = Image.alpha_composite(img, vig)

    out = BG_DIR / f"bg_{idx:02d}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=82, optimize=True)
    return out


if __name__ == "__main__":
    import time
    t0 = time.time()
    for i in range(N):
        p = make(i)
        if i % 10 == 0:
            print(f"  {i+1}/{N}  {p.name}")
    print(f"done: {N} 张背景 -> {BG_DIR}  耗时 {time.time()-t0:.1f}s")