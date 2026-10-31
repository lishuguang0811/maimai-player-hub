# -*- coding: utf-8 -*-
"""
weather.py —— 实时天气（城市见 config.CITY）

数据源：Open-Meteo（免费、无需 API Key）
接口不可用时返回 None，由界面显示"获取失败"，其它功能照常。
"""
from __future__ import annotations

import requests

import config

# WMO 天气代码 -> 中文。这是 Open-Meteo 官方定义的标准编码，
# 我们只是翻译成中文，不做任何猜测性描述。
WMO_TEXT = {
    0: "晴",
    1: "大致晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "大阵雪",
    95: "雷阵雨",
    96: "雷阵雨伴小冰雹",
    99: "雷阵雨伴大冰雹",
}

RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
SNOW_CODES = {71, 73, 75, 77, 85, 86}


def fetch_weather(lat: float | None = None, lon: float | None = None,
                  city_name: str | None = None, timeout: int | None = None) -> dict | None:
    """抓一次实时 + 今日天气。失败返回 None（并带上 error 字段供界面提示）。"""
    timeout = timeout or config.WEATHER_TIMEOUT
    lat = config.CITY["latitude"] if lat is None else lat
    lon = config.CITY["longitude"] if lon is None else lon
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "weather_code", "wind_speed_10m",
        ]),
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset",
        "timezone": config.CITY["timezone"],
        "forecast_days": 1,
    }
    try:
        resp = requests.get(config.WEATHER_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        cur = data["current"]
        daily = data["daily"]
        code = int(cur["weather_code"])
        return {
            "ok": True,
            "city": city_name or config.CITY["name"],
            "observed_at": cur["time"],
            "text": WMO_TEXT.get(code, f"未知天气(代码{code})"),
            "code": code,
            "temp": cur["temperature_2m"],
            "feels_like": cur["apparent_temperature"],
            "humidity": cur["relative_humidity_2m"],
            "wind_kmh": cur["wind_speed_10m"],
            "precipitation": cur["precipitation"],
            "temp_max": daily["temperature_2m_max"][0],
            "temp_min": daily["temperature_2m_min"][0],
            "sunrise": daily["sunrise"][0],
            "sunset": daily["sunset"][0],
        }
    except Exception as exc:            # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def is_rainy(w: dict) -> bool:
    return bool(w) and w.get("code") in RAIN_CODES


def is_snowy(w: dict) -> bool:
    return bool(w) and w.get("code") in SNOW_CODES