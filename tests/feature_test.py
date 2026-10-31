# -*- coding: utf-8 -*-
"""
feature_test.py —— 生日彩蛋 / 分享图 / 背景（多档案+等级版）
运行： .venv\\Scripts\\python.exe tests\\feature_test.py
"""
from _env import ROOT  # noqa: F401  必须在 config 之前导入

import sys
from datetime import date, datetime

import config
from modules import background, owner, recommend, share_card, songs

ok = True


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


records = songs.flatten(songs.load_snapshot())
today = date.today()
BIRTH_M, BIRTH_D = config.OWNER_BIRTHDAY

print("=== 1. 生日彩蛋逻辑 ===")
on = datetime(2026, BIRTH_M, BIRTH_D, 10, 0, 0)
off = datetime(2026, 10, 23, 12, 0, 0)
check(f"{BIRTH_M:02d}-{BIRTH_D:02d} 是生日", owner.is_birthday(on))
check("10-23 不是生日", not owner.is_birthday(off))
check("年龄 = 26", owner.age(on) == 26, str(owner.age(on)))
check("生日当天 countdown 返回 None", owner.countdown_parts(on) is None)
cp = owner.countdown_parts(off)
check("非生日返回倒计时", cp is not None)
check("目标日期 = 2027-01-01", cp["target"].strftime("%Y-%m-%d") == "2027-01-01",
      cp["target"].strftime("%Y-%m-%d"))
check("天数合理(0~366)", 0 <= cp["days"] <= 366, f"{cp['days']} 天")
check("时分秒范围合法", 0 <= cp["hours"] < 24 and 0 <= cp["minutes"] < 60 and 0 <= cp["seconds"] < 60)
dec = datetime(2026, 12, 1, 0, 0, 0)
check("12月时目标为明年", owner.next_birthday(dec).year == 2027,
      owner.next_birthday(dec).strftime("%Y-%m-%d"))
eve = datetime(2026, 12, 31, 23, 59, 0)
cpe = owner.countdown_parts(eve)
check("生日前一天倒计时约1分钟", cpe and cpe["days"] == 0 and cpe["hours"] == 0,
      f"{cpe['days']}天{cpe['hours']}时")

print("=== 2. 分享图（按等级）===")
tiers = recommend.tiers_for_level("高手")
picks = recommend.daily_picks(records, today, {"key": "sunny"}, tiers, 3, ["初音未来"], "高手")
png = share_card.render_card(
    picks, {"key": "sunny", "name": "晴日节奏计划", "line": "x"},
    "北京现在 晴，12.0°C。",
    {"name": "旅人", "city": "北京", "level_tag": "高手玩家", "likes": ["初音未来"]},
    today, "2026-10-23T21:56:49+08:00", is_birthday=False,
)
check("分享图生成", png.exists())
check("合法 PNG", png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n")
from PIL import Image
im = Image.open(png)
check("宽度 = SHARE_WIDTH", im.width == config.SHARE_WIDTH, f"{im.width}")
check("高度合理", im.height > 1200, f"{im.height}")
tiers_b = recommend.tiers_for_level("新手")
picks_b = recommend.daily_picks(records, today, {"key": "sunny"}, tiers_b, 3, None, "新手")
png_b = share_card.render_card(picks_b, {"key": "sunny", "name": "x", "line": "x"}, "x",
                              {"name": "测试", "city": "", "level_tag": "新手", "likes": []},
                              today, "—", out_path=config.SHARE_DIR / "test_beginner.png")
check("新手分享图生成", png_b.exists() and Image.open(png_b).height > 800)

print("=== 3. 背景 ===")
bgs = background.ensure_backgrounds()
check("主题背景 50 张", len(bgs) == config.BG_COUNT, f"{len(bgs)}")
uri = background.to_data_uri(bgs[0])
check("data URI 正确", uri.startswith("data:image/jpeg;base64,"))

print("=== 4. 选曲页卡片数据 ===")
lib = songs.song_select_view(records)
sv = lib[0]
check("最高定数歌有完整难度", len(sv["diffs"]) >= 4, str(list(sv["diffs"])))
check("B站链接可用", songs.bilibili_link(sv["title"]).startswith("https://search.bilibili.com/"))

print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)
