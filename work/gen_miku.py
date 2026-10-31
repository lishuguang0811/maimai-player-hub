# -*- coding: utf-8 -*-
"""
gen_miku.py —— 原创绘制初音未来主题插画（程序化，非官方/非他人作品）

说明：这是用 Pillow 从零画的"原创同人风格"初音主题图，供个人非商用。
不抓取、不复制任何官方立绘或他人同人图（那些是 Crypton / 原作者的版权）。
Crypton 的 piapro 角色规约允许个人非商用的初音二次创作，本图属于此类原创。
想要官方/高质量立绘，请从 piapro 下载后用 work/import_miku.py 导入。

画的是一个扁平风格的初音形象：青绿双马尾 + 刘海 + 耳机 + 领带 + 黑裙 + 青绿长靴，
配主题渐变背景 + 音符 + 均衡器 + 光斑。每张用不同种子做配色/构图变化。
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "miku"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1600, 1000
N = 8

TEAL = (57, 197, 187)
TEAL_LT = (127, 224, 216)
TEAL_DK = (24, 110, 106)
SKIN = (250, 224, 205)
DARK = (13, 17, 23)
GREY = (210, 216, 220)
BLACK = (28, 32, 38)
WHITE = (240, 250, 249)
PINK = (227, 110, 150)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(d, c1, c2, diag=False):
    for y in range(H):
        for x in range(0, W, 4):
            t = (x / W * 0.5 + y / H * 0.5) if diag else (y / H)
            d.line([(x, y), (x + 4, y)], fill=lerp(c1, c2, t))


def bokeh(img, rng):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for _ in range(rng.randint(6, 11)):
        r = rng.randint(40, 150)
        x, y = rng.randint(-50, W + 50), rng.randint(-50, H + 50)
        col = rng.choice([TEAL, TEAL_LT, PINK, WHITE])
        ld.ellipse([x - r, y - r, x + r, y + r], fill=(*col, rng.randint(16, 46)))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(26)))


def equalizer(img, rng):
    d = ImageDraw.Draw(img, "RGBA")
    n = rng.randint(26, 40); bw = W // n
    col = rng.choice([TEAL, TEAL_LT, PINK])
    for i in range(n):
        h = rng.randint(24, 200)
        d.rectangle([i * bw + 3, H - h, i * bw + bw - 3, H], fill=(*col, rng.randint(26, 60)))


def notes(img, rng):
    d = ImageDraw.Draw(img, "RGBA")
    col = rng.choice([TEAL_LT, WHITE, PINK])
    for _ in range(rng.randint(5, 10)):
        x, y = rng.randint(50, W - 50), rng.randint(50, H - 120)
        s = rng.randint(9, 20); a = rng.randint(46, 110)
        d.ellipse([x - s, y - int(s * .7), x + s, y + int(s * .7)], fill=(*col, a))
        d.line([(x + s, y), (x + s, y - s * 4)], fill=(*col, a), width=3)
        d.line([(x + s, y - s * 4), (x + s + s * 1.4, y - s * 3)], fill=(*col, a), width=3)


def draw_miku(img, cx, cy, s, rng):
    """扁平风初音形象。s 为缩放，cx,cy 为头部中心。"""
    d = ImageDraw.Draw(img, "RGBA")
    tail_col = rng.choice([TEAL, TEAL_LT])
    # --- 双马尾（最标志性的特征，先画在头后面）---
    for side in (-1, 1):
        # 马尾根部到头侧
        hx = cx + side * int(0.62 * s)
        hy = cy + int(0.05 * s)
        # 长马尾：一串逐渐变细、带波浪的椭圆
        segs = 9
        for i in range(segs):
            t = i / (segs - 1)
            px = hx + side * int((0.25 + 0.55 * t) * s) + int(math.sin(t * 6 + side) * 0.10 * s)
            py = hy + int((0.3 + 2.6 * t) * s)
            rw = int((0.30 - 0.20 * t) * s)
            rh = int((0.42 - 0.24 * t) * s)
            d.ellipse([px - rw, py - rh, px + rw, py + rh],
                      fill=(*lerp(tail_col, TEAL_DK, t * 0.5), 235))
        # 马尾扎带
        d.ellipse([hx - int(.16*s), hy - int(.10*s), hx + int(.16*s), hy + int(.16*s)],
                  fill=(*BLACK, 235))
    # --- 头 ---
    hr = int(0.62 * s)
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=(*SKIN, 255))
    # --- 刘海（青绿，盖住额头）---
    d.pieslice([cx - hr, cy - hr, cx + hr, cy + hr], 180, 360, fill=(*tail_col, 255))
    for i in range(5):   # 刘海尖
        bx = cx - hr + int((i + 0.5) * (2 * hr / 5))
        d.polygon([(bx - int(.12*s), cy - int(.05*s)), (bx + int(.12*s), cy - int(.05*s)),
                   (bx, cy + int(.18*s))], fill=(*tail_col, 255))
    # --- 眼睛 ---
    for side in (-1, 1):
        ex = cx + side * int(0.26 * s); ey = cy + int(0.10 * s)
        d.ellipse([ex - int(.11*s), ey - int(.15*s), ex + int(.11*s), ey + int(.15*s)],
                  fill=(*TEAL_DK, 255))
        d.ellipse([ex - int(.05*s), ey - int(.09*s), ex + int(.02*s), ey + int(.02*s)],
                  fill=(*WHITE, 255))
    # --- 耳机 ---
    d.arc([cx - int(1.02*s), cy - int(1.02*s), cx + int(1.02*s), cy + int(1.02*s)],
          200, 340, fill=(*BLACK, 255), width=int(.10*s))
    for side in (-1, 1):
        ex = cx + side * int(0.98 * s); ey = cy + int(0.05 * s)
        d.rounded_rectangle([ex - int(.16*s), ey - int(.20*s), ex + int(.16*s), ey + int(.20*s)],
                            radius=int(.06*s), fill=(*BLACK, 255))
        d.ellipse([ex - int(.07*s), ey - int(.07*s), ex + int(.07*s), ey + int(.07*s)],
                  fill=(*TEAL_LT, 255))
    # --- 身体：上衣 ---
    ty = cy + int(0.62 * s)
    d.polygon([(cx - int(.5*s), ty), (cx + int(.5*s), ty),
               (cx + int(.42*s), ty + int(.9*s)), (cx - int(.42*s), ty + int(.9*s))],
              fill=(*GREY, 255))
    # 领口青绿边
    d.polygon([(cx - int(.28*s), ty), (cx + int(.28*s), ty),
               (cx, ty + int(.22*s))], fill=(*tail_col, 255))
    # 领带
    d.polygon([(cx - int(.08*s), ty + int(.05*s)), (cx + int(.08*s), ty + int(.05*s)),
               (cx, ty + int(.20*s))], fill=(*tail_col, 255))
    d.polygon([(cx - int(.07*s), ty + int(.20*s)), (cx + int(.07*s), ty + int(.20*s)),
               (cx + int(.05*s), ty + int(.55*s)), (cx, ty + int(.66*s)),
               (cx - int(.05*s), ty + int(.55*s))], fill=(*tail_col, 255))
    # --- 手臂（青绿袖套 + 肤手）---
    for side in (-1, 1):
        ax = cx + side * int(.52 * s)
        d.rounded_rectangle([ax - int(.10*s), ty + int(.05*s), ax + int(.10*s), ty + int(.75*s)],
                            radius=int(.08*s), fill=(*tail_col, 255))
        d.ellipse([ax - int(.09*s), ty + int(.72*s), ax + int(.09*s), ty + int(.90*s)],
                  fill=(*SKIN, 255))
    # --- 黑裙 ---
    sy = ty + int(.88 * s)
    d.polygon([(cx - int(.44*s), sy), (cx + int(.44*s), sy),
               (cx + int(.62*s), sy + int(.5*s)), (cx - int(.62*s), sy + int(.5*s))],
              fill=(*BLACK, 255))
    # --- 腿 + 青绿长靴 ---
    for side in (-1, 1):
        lx = cx + side * int(.20 * s)
        ly = sy + int(.48 * s)
        d.rectangle([lx - int(.07*s), ly, lx + int(.07*s), ly + int(.5*s)], fill=(*SKIN, 255))
        d.rounded_rectangle([lx - int(.09*s), ly + int(.45*s), lx + int(.09*s), ly + int(1.05*s)],
                            radius=int(.05*s), fill=(*tail_col, 255))


def make(idx):
    rng = random.Random(7000 + idx)
    img = Image.new("RGB", (W, H), DARK)
    d = ImageDraw.Draw(img)
    pals = [(DARK, TEAL_DK), (TEAL_DK, DARK), ((10, 26, 30), TEAL_DK), (DARK, (40, 24, 44))]
    c1, c2 = rng.choice(pals)
    gradient(d, c1, c2, diag=rng.random() < 0.5)
    img = img.convert("RGBA")
    img = bokeh(img, rng)
    if rng.random() < 0.8:
        equalizer(img, rng)
    notes(img, rng)
    # 初音形象：居中偏上，大小随机
    s = rng.randint(150, 210)
    cx = W // 2 + rng.randint(-120, 120)
    cy = int(H * 0.34) + rng.randint(-30, 30)
    draw_miku(img, cx, cy, s, rng)
    # 暗角
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for i in range(60):
        vd.rectangle([i, i, W - i, H - i], outline=(0, 0, 0, int(28 * (1 - i / 60))))
    img = Image.alpha_composite(img, vig.filter(ImageFilter.GaussianBlur(30)))
    out = OUT / f"miku_{idx:02d}.jpg"
    img.convert("RGB").save(out, "JPEG", quality=86, optimize=True)
    return out


if __name__ == "__main__":
    import time
    t0 = time.time()
    for i in range(N):
        p = make(i)
        print(f"  {i+1}/{N} {p.name}")
    print(f"done: {N} 张原创初音插画 -> {OUT}  耗时 {time.time()-t0:.1f}s")