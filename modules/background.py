# -*- coding: utf-8 -*-
"""
background.py —— 初音主题背景图管理

50 张背景由 work/gen_bg.py 程序化生成（青绿色调 + 音波/均衡器/音符/双马尾曲线），
放在 data/bg/。这里负责：
1) 确认 50 张都在（缺了就调用生成逻辑补齐）
2) 随机挑一张
3) 转成 base64 data URI，供 CSS 当背景用

为什么用 base64：Streamlit 的 CSS 不能直接引用本地文件路径，
但能引用 data URI。一次只嵌一张，体积可控。
"""
from __future__ import annotations

import base64
import random
from pathlib import Path

import config


def _list_bgs() -> list[Path]:
    if not config.BG_DIR.exists():
        return []
    return sorted(config.BG_DIR.glob("bg_*.jpg"))


def ensure_backgrounds() -> list[Path]:
    """50 张都在就直接返回；缺了就现场生成补齐。"""
    bgs = _list_bgs()
    if len(bgs) >= config.BG_COUNT:
        return bgs[: config.BG_COUNT]
    # 延迟导入，避免没装 Pillow 时 import 本模块就崩
    from work.gen_bg import make          # noqa: PLC0415
    config.BG_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(config.BG_COUNT):
        if not (config.BG_DIR / f"bg_{i:02d}.jpg").exists():
            make(i)
    return _list_bgs()[: config.BG_COUNT]


def pick_background(seed: int | None = None) -> Path | None:
    """随机挑一张背景。seed 给定时结果可复现（测试用）。"""
    bgs = ensure_backgrounds()
    if not bgs:
        return None
    rng = random.Random(seed) if seed is not None else random.Random()
    return rng.choice(bgs)


def to_data_uri(path: Path) -> str:
    """把 JPEG 读成 base64 data URI，可直接塞进 CSS 的 background-image。"""
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"