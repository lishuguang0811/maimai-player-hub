# -*- coding: utf-8 -*-
"""
share_card.py —— 把当日推荐渲染成一张竖版分享图（PNG）

用 Pillow 直接画，不依赖浏览器截图。
做法是"两遍布局"：先把要画的东西整理成一个 rows 列表并算出总高度，
再按顺序画到画布上。这样卡片数量变化（3 档 / 4 档、每档 3 首 / 5 首）
时图片高度会自动跟着变，不会被截断。

注意：emoji（🎧⚡👑）在 Windows 自带的中日韩字体里没有字形，
直接画会变成方框，所以这里统一用 strip_emoji() 去掉，
改用色条 + 文字标签来表达档位，视觉上不损失信息。
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\uFE0F\u200D]"
)


def strip_emoji(text: str) -> str:
    """去掉 emoji 和变体选择符，避免字体缺字形画成方框。"""
    return _EMOJI_RE.sub("", str(text)).strip()


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    """按候选顺序找第一个存在的字体。全都找不到就退回 Pillow 默认字体。"""
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:                # noqa: BLE001
                continue
    return ImageFont.load_default()


def _wrap(text: str, font, max_width: int) -> list[str]:
    """按像素宽度折行（日文曲名常常很长，必须折行）。"""
    text = str(text or "")
    if not text:
        return [""]
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) <= max_width:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines or [""]


# 每个档位对应的强调色，画成左侧色条
TIER_COLORS = {
    "warmup": (126, 200, 190),
    "main": (57, 197, 187),
    "boss": (232, 146, 106),
    "devil": (198, 120, 221),
}


def render_card(
    picks: list[dict],
    theme: dict,
    weather_line: str,
    profile: dict,
    today: date,
    snapshot_at: str,
    is_birthday: bool = False,
    out_path: Path | None = None,
) -> Path:
    """
    画出分享图，返回文件路径。
    picks 是 recommend.daily_picks() 的返回值，结构见该函数文档。
    """
    W = config.SHARE_WIDTH
    PAD = 54
    INNER = W - PAD * 2

    f_h1 = _font(config.FONT_BOLD_CANDIDATES, 52)
    f_h2 = _font(config.FONT_BOLD_CANDIDATES, 38)
    f_tier = _font(config.FONT_BOLD_CANDIDATES, 34)
    f_song = _font(config.FONT_TITLE_CANDIDATES, 34)
    f_body = _font(config.FONT_CJK_CANDIDATES, 24)
    f_small = _font(config.FONT_CJK_CANDIDATES, 20)
    f_ds = _font(config.FONT_BOLD_CANDIDATES, 40)

    # ---------- 第一遍：组装 rows 并算高度 ----------
    rows: list[tuple] = []      # (kind, payload, height)

    def add_gap(h: int):
        rows.append(("gap", h, h))

    def add_text(text, font, color, max_w=INNER, line_extra=6):
        lines = _wrap(text, font, max_w)
        lh = font.size + line_extra
        rows.append(("text", (lines, font, color, 0), lh * len(lines)))

    def add_song(idx, song, miku, accent):
        title = strip_emoji(song["title"])
        artist = strip_emoji(song["artist"] or "艺术家未记录")
        meta = (f"{song['diff']} · Lv.{song['level']} · BPM "
                f"{song['bpm'] if song['bpm'] not in (None, 0) else '—'} · "
                f"{song['genre'] or '未分类'}")
        t_lines = _wrap(f"{idx:02d}  {title}", f_song, INNER - 190)
        a_lines = _wrap(artist, f_small, INNER - 190)
        h = (f_song.size + 6) * len(t_lines) + (f_small.size + 6) * len(a_lines) + 46
        rows.append(("song", (idx, t_lines, a_lines, meta, song, miku, accent), h))

    def add_tier_header(tier, pool_size, extra=""):
        label = f"{strip_emoji(tier['emoji'])} {tier['label']}".strip()
        rng = f"定数 {tier['ds_min']:.1f}~{tier['ds_max']:.1f}"
        diffs = "/".join(tier.get("diffs") or [])
        sub = f"{diffs} · {rng} · 候选 {pool_size} 首"
        if extra:
            sub += f" · {extra}"
        rows.append(("tier", (label, sub, TIER_COLORS.get(tier["key"], config.SHARE_MIKU)),
                     f_tier.size + f_small.size + 30))

    add_gap(46)
    add_text(config.APP_NAME, f_h1, config.SHARE_MIKU)
    add_gap(6)
    add_text(config.APP_SUBTITLE, f_small, config.SHARE_SUB)
    add_gap(24)

    name = profile.get("name", "—")
    add_text(f"玩家：{name}　|　{today.strftime('%Y年%m月%d日')}", f_h2, config.SHARE_TEXT)
    add_gap(8)
    add_text(f"常驻地：{profile.get('city', '—')}　|　{profile.get('level_tag', '')}",
             f_small, config.SHARE_SUB)
    add_gap(18)

    if is_birthday:
        rows.append(("banner", (config.BIRTHDAY["banner"],), 74))
        add_gap(14)

    rows.append(("theme", (strip_emoji(theme.get("name", "")), theme.get("line", "")), 108))
    add_gap(10)
    add_text(f"天气：{weather_line}", f_small, config.SHARE_SUB)
    add_gap(30)

    for p in picks:
        tier = p["tier"]
        add_tier_header(tier, p["pool_size"])
        add_gap(10)
        if not p["songs"]:
            add_text("该定数区间暂无匹配谱面（待补充，不做猜测填充）", f_body, (242, 193, 78))
        for i, item in enumerate(p["songs"], start=1):
            song = item["song"]
            miku = any(k in (song.get("artist") or "") for k in config.MIKU_KEYWORDS)
            add_song(i, song, miku, TIER_COLORS.get(tier["key"], config.SHARE_MIKU))
        add_gap(22)

    add_gap(6)
    add_text(f"{config.SONGS_SOURCE_NOTE} · 快照时间 {snapshot_at}", f_small, config.SHARE_SUB)
    add_text("曲名/艺术家/分类/BPM/定数均为快照原值，程序不做推测；"
             "定数与收录随版本变化，与机台不符时以机台为准。", f_small, config.SHARE_SUB)
    add_text(f"生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f_small, (110, 124, 132))
    add_gap(40)

    H = sum(r[2] for r in rows)

    # ---------- 第二遍：真正绘制 ----------
    img = Image.new("RGB", (W, H), config.SHARE_BG)
    d = ImageDraw.Draw(img)

    # 背景装饰：顶部渐层色块 + 细网格线，做出音游 UI 的感觉
    for i in range(0, 360):
        ratio = 1 - i / 360
        c = tuple(int(config.SHARE_BG[k] + (config.SHARE_MIKU[k] - config.SHARE_BG[k])
                      * 0.18 * ratio) for k in range(3))
        d.line([(0, i), (W, i)], fill=c)
    d.rectangle([0, 0, W - 1, H - 1], outline=(45, 56, 66), width=2)
    d.rectangle([PAD - 26, 46, PAD - 20, 46 + 96], fill=config.SHARE_MIKU)

    y = 0
    for kind, payload, h in rows:
        if kind == "gap":
            y += h
            continue
        if kind == "text":
            lines, font, color, _ = payload
            for ln in lines:
                d.text((PAD, y), ln, font=font, fill=color)
                y += font.size + 6
            continue
        if kind == "banner":
            text = strip_emoji(payload[0])
            d.rounded_rectangle([PAD, y, W - PAD, y + h - 14], radius=14,
                                fill=(60, 30, 46), outline=(232, 146, 190), width=2)
            d.text((PAD + 24, y + 18), text, font=f_tier, fill=(255, 214, 236))
            y += h
            continue
        if kind == "theme":
            name_, line_ = payload
            d.rounded_rectangle([PAD, y, W - PAD, y + h - 12], radius=14,
                                fill=(20, 40, 42), outline=config.SHARE_MIKU, width=2)
            d.text((PAD + 24, y + 14), f"今日主题：{name_}", font=f_tier,
                   fill=config.SHARE_MIKU)
            for ln in _wrap(line_, f_small, INNER - 60):
                d.text((PAD + 24, y + 14 + f_tier.size + 10), ln, font=f_small,
                       fill=config.SHARE_SUB)
                y += 0  # 单行足够，主题语很短
            y += h
            continue
        if kind == "tier":
            label, sub, accent = payload
            d.rectangle([PAD, y + 6, PAD + 8, y + 8 + f_tier.size], fill=accent)
            d.text((PAD + 22, y), label, font=f_tier, fill=config.SHARE_TEXT)
            d.text((PAD + 22, y + f_tier.size + 2), sub, font=f_small, fill=config.SHARE_SUB)
            d.line([(PAD, y + h - 16), (W - PAD, y + h - 16)], fill=config.SHARE_LINE, width=1)
            y += h
            continue
        if kind == "song":
            idx, t_lines, a_lines, meta, song, miku, accent = payload
            top = y
            d.rounded_rectangle([PAD, top, W - PAD, top + h - 10], radius=12,
                                fill=config.SHARE_CARD_BG,
                                outline=accent if miku else config.SHARE_LINE,
                                width=2 if miku else 1)
            d.rectangle([PAD, top + 10, PAD + 5, top + h - 20], fill=accent)
            tx = PAD + 24
            ty = top + 14
            for ln in t_lines:
                d.text((tx, ty), ln, font=f_song, fill=(255, 255, 255))
                ty += f_song.size + 6
            for ln in a_lines:
                d.text((tx, ty), ln, font=f_small, fill=config.SHARE_SUB)
                ty += f_small.size + 6
            d.text((tx, ty), meta, font=f_small, fill=(140, 154, 162))
            # 右侧定数大字
            ds_text = f"{song['ds']:.1f}"
            dw = f_ds.getlength(ds_text)
            d.text((W - PAD - 24 - dw, top + 16), ds_text, font=f_ds, fill=accent)
            d.text((W - PAD - 24 - f_small.getlength("定数"), top + 16 + f_ds.size + 2),
                   "定数", font=f_small, fill=config.SHARE_SUB)
            if miku:
                tag = "★ MIKU / 世界计划"
                d.text((W - PAD - 24 - f_small.getlength(tag), top + h - 42),
                       tag, font=f_small, fill=config.SHARE_MIKU)
            y += h
            continue
        y += h

    config.SHARE_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(out_path) if out_path else (
        config.SHARE_DIR / f"maimai_{today.strftime('%Y%m%d')}.png"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    return out