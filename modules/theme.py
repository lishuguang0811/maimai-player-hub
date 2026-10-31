# -*- coding: utf-8 -*-
"""
theme.py —— 天气 -> 当日主题

规则很朴素：看天气状况 + 气温，选一个主题。
每个主题带：名字、一句话基调、选曲倾向、界面强调色。
天气获取失败时用 OFFLINE 主题，功能不受影响。
"""
from __future__ import annotations

import config
from modules import weather as W_

THEMES = {
    "sunny": {
        "name": "晴日节奏计划",
        "line": "天晴，机台边的人也多，节奏要跟得上光。",
        "prefer": "bright",
        "color": "#39C5BB",
    },
    "cloudy": {
        "name": "多云频率调校",
        "line": "光不刺眼，正好专心读谱。",
        "prefer": "steady",
        "color": "#7FB6C4",
    },
    "rain": {
        "name": "雨声与电子音",
        "line": "外面在下雨，里面在下音符，别踩湿踏板就行。",
        "prefer": "melancholy",
        "color": "#5B8FB9",
    },
    "snow": {
        "name": "初音白雪场",
        "line": f"{config.CITY['name']}下雪是稀客，今天这局值得记一下。",
        "prefer": "clear",
        "color": "#A8E6E2",
    },
    "hot": {
        "name": "高温燃曲对策",
        "line": "手汗警告：擦手、慢热、别急着上 14。",
        "prefer": "burn",
        "color": "#E8836B",
    },
    "cold": {
        "name": "低温暖机模式",
        "line": "手指先活过来再谈定数，热身局数加一倍。",
        "prefer": "warmup",
        "color": "#6E9BC3",
    },
    "fog": {
        "name": "雾中读谱训练",
        "line": "能见度低，那就练眼睛和手的一致性。",
        "prefer": "focus",
        "color": "#9AA7B0",
    },
    "offline": {
        "name": "标准选曲日",
        "line": "天气接口暂时联系不上，今天按默认节奏来。",
        "prefer": "steady",
        "color": "#39C5BB",
    },
}


def pick_theme(w: dict | None) -> dict:
    """
    根据天气字典选主题。w 为 None 或 {"ok": False} 时返回 offline 主题。
    判断顺序：极端天气 > 降水 > 气温 > 默认。
    """
    if not w or not w.get("ok"):
        return dict(key="offline", **THEMES["offline"])

    code = w.get("code")
    temp = w.get("temp")
    feels = w.get("feels_like")

    if W_.is_snowy(w):
        key = "snow"
    elif code in (45, 48):
        key = "fog"
    elif W_.is_rainy(w):
        key = "rain"
    elif isinstance(temp, (int, float)) and temp >= 32:
        key = "hot"
    elif isinstance(feels, (int, float)) and feels <= 2:
        key = "cold"
    elif code in (0, 1):
        key = "sunny"
    elif code == 2:
        key = "cloudy"
    else:
        key = "cloudy"
    return dict(key=key, **THEMES[key])


def advice_for(w: dict | None, theme: dict) -> str:
    """生成一句和当天真实天气有关的实用提醒（只用接口返回的数字）。"""
    if not w or not w.get("ok"):
        return "今天没拿到实时天气，出门前自己看一眼窗外。"
    parts = [f"{config.CITY['name']}现在 {w['text']}，{w['temp']}°C（体感 {w['feels_like']}°C）"]
    if isinstance(w.get("wind_kmh"), (int, float)) and w["wind_kmh"] >= 25:
        parts.append(f"风 {w['wind_kmh']} km/h，骑车去机厅注意")
    if W_.is_rainy(w):
        parts.append("带伞，别让手湿了再摸屏幕")
    if W_.is_snowy(w):
        parts.append("路滑，慢慢走")
    if isinstance(w.get("temp_max"), (int, float)) and isinstance(w.get("temp_min"), (int, float)):
        parts.append(f"今日 {w['temp_min']}~{w['temp_max']}°C")
    return "，".join(parts) + "。"