# -*- coding: utf-8 -*-
"""
arcade_map.py —— 音游地图（3.0 附录：真实机厅 / 信息核验 / 纠错队列）

核心原则（文档强调）：宁可只展示少量经过核验的机厅，也不展示虚构/未确认地点。
- 店铺信息与机台信息分离（文档第六节）：exists / operating / has_maimai /
  machine_count / verified_at / source 各自独立，不用一个布尔混代表。
- 未核实舞萌 DX 的地点显示"机台待确认"，不冒充"已确认"。
- 用户纠错进入待审核队列，不直接覆盖已核验数据。
- 距离用 Haversine 直线距离（无实时交通数据，不冒充驾车距离）。
- 导航打开高德真实导航页（传入核验过的坐标/地址）。
- 当前 data/arcades.json 为空：没有可靠来源前不填假数据。
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import config

ARCADES_FILE = config.DATA_DIR / "arcades.json"
FEEDBACK_FILE = config.DATA_DIR / "arcade_feedback.json"
AMAP_NAV = "https://uri.amap.com/navigation?to={lon},{lat},{name}&mode=car"
AMAP_NAV_ADDR = "https://www.amap.com/search?query={kw}"


def _read(path: Path, default: dict) -> dict:
    if path.exists():
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except Exception:                    # noqa: BLE001
            pass
    return default


def load_arcades() -> list[dict]:
    """已核验机厅列表（当前为空，不虚构）。"""
    return _read(ARCADES_FILE, {"arcades": []}).get("arcades", [])


def save_arcades(arcades: list[dict]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    ARCADES_FILE.write_text(
        json.dumps({"note": "已核验机厅。无可靠来源前保持为空，不虚构坐标。",
                    "updated": datetime.now().isoformat(timespec="seconds"),
                    "arcades": arcades}, ensure_ascii=False, indent=2),
        encoding="utf-8")


def load_feedback() -> list[dict]:
    return _read(FEEDBACK_FILE, {"pending": []}).get("pending", [])


def add_feedback(entry: dict) -> None:
    """用户纠错/新增 -> 待审核队列（不直接覆盖已核验数据）。"""
    d = _read(FEEDBACK_FILE, {"pending": []})
    entry = dict(entry)
    entry["submitted_at"] = datetime.now().isoformat(timespec="seconds")
    entry["status"] = "pending"
    d.setdefault("pending", []).append(entry)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def approve_feedback(index: int) -> bool:
    """管理员审核通过：把待审核条目转成已核验机厅（需含坐标）。"""
    d = _read(FEEDBACK_FILE, {"pending": []})
    pend = d.get("pending", [])
    if not (0 <= index < len(pend)):
        return False
    item = pend.pop(index)
    if item.get("latitude") is None or item.get("longitude") is None:
        return False
    arcade = {
        "name": item.get("name", ""), "address": item.get("address", ""),
        "district": item.get("district", ""),
        "latitude": item["latitude"], "longitude": item["longitude"],
        "exists": True, "operating": item.get("operating", True),
        "has_maimai": item.get("has_maimai", False),
        "machine_count": item.get("machine_count"),   # None = 未核实
        "other_games": item.get("other_games", []),
        "source": item.get("source", "玩家提交"),
        "verified_at": datetime.now().isoformat(timespec="seconds"),
    }
    arcades = load_arcades(); arcades.append(arcade); save_arcades(arcades)
    d["pending"] = pend
    FEEDBACK_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """两点直线距离（km）。无交通数据，不冒充驾车距离。"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nav_link(arcade: dict) -> str:
    """高德导航链接：有坐标用坐标，否则用地址搜索。"""
    if arcade.get("latitude") is not None and arcade.get("longitude") is not None:
        return AMAP_NAV.format(lon=arcade["longitude"], lat=arcade["latitude"],
                               name=quote(arcade.get("name", "")))
    return AMAP_NAV_ADDR.format(kw=quote(f"{arcade.get('name', '')} {arcade.get('address', '')}"))


def maimai_status(arcade: dict) -> str:
    """机台核验状态文案（不把'店铺存在'当成'已确认舞萌DX'）。"""
    if arcade.get("has_maimai"):
        mc = arcade.get("machine_count")
        return f"已确认舞萌DX" + (f" · {mc} 台" if mc is not None else " · 机台数待核实")
    return "机台待确认"