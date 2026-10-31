# -*- coding: utf-8 -*-
"""
location.py —— 当前位置 / 最近机厅 / 币价

设计原则（不瞎编）：
- 城市定位：先用 IP 网络定位猜一个城市（服务器侧，约等于本机/同网络位置），
  再让用户手动填中文城市修正。
- 中文城市 -> 经纬度：用 Open-Meteo 免费地理编码，天气跟着城市走。
- 最近机厅 / 币价：美团、抖音、高德都有反爬和登录墙，无法可靠自动抓取，
  所以这里只生成"真实可用的搜索入口"，绝不编造具体价格或机厅坐标。
  币价另提供"玩家自填本地记录"（明确标注非抓取）。

geocode / detect_city_ip 用 lru_cache 缓存，避免每次交互都发网络请求。
"""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

import requests

import config


@lru_cache(maxsize=1)
def detect_city_ip() -> str | None:
    """用 IP 定位猜城市（英文），失败返回 None。"""
    for url in config.IP_GEO_URLS:
        try:
            d = requests.get(url, timeout=config.GEO_TIMEOUT).json()
            city = d.get("city") or d.get("region")
            if city:
                return str(city)
        except Exception:                    # noqa: BLE001
            continue
    return None


@lru_cache(maxsize=64)
def geocode(city: str) -> dict | None:
    """中文城市名 -> {name, latitude, longitude}，失败 None。"""
    if not city:
        return None
    try:
        r = requests.get(
            config.GEOCODE_URL,
            params={"name": city, "count": 1, "language": "zh"},
            timeout=config.GEO_TIMEOUT,
        )
        res = r.json().get("results") or []
        if res:
            g = res[0]
            return {"name": g.get("name", city),
                    "latitude": g["latitude"], "longitude": g["longitude"]}
    except Exception:                        # noqa: BLE001
        pass
    return None


def resolve_city(city: str | None) -> dict:
    """解析城市坐标；解析不到就退回默认城市（config.DEFAULT_CITY）。"""
    g = geocode(city) if city else None
    if g:
        return g
    return dict(config.DEFAULT_CITY)


def arcade_links(city: str) -> dict:
    """最近机厅的搜索入口（真实链接，非编造数据）。"""
    kw_raw = config.ARCADE_KEYWORD_TPL.format(city=city)
    return {
        "高德地图": config.AMAP_SEARCH.format(kw=quote(kw_raw)),
        "百度地图": config.BAIDU_MAP_SEARCH.format(kw=quote(kw_raw)),
        "美团": config.MEITUAN_SEARCH.format(kw=quote(kw_raw)),
    }


def price_links(city: str) -> dict:
    """币价的搜索入口（美团/抖音有反爬，无法自动抓，只给搜索链接）。"""
    kw_raw = config.PRICE_KEYWORD_TPL.format(city=city)
    return {
        "美团": config.MEITUAN_SEARCH.format(kw=quote(kw_raw)),
        "抖音": config.DOUYIN_SEARCH.format(kw=quote(kw_raw)),
    }