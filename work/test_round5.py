# -*- coding: utf-8 -*-
"""work/test_round5.py —— 第五轮新增内容的自检：机台 / 成绩码 / 段位 / 新小游戏"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config                                   # noqa: E402
from modules import arcade, dan, maimai, minigames, playlog, songs   # noqa: E402

ok = True


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


print("=== 1. 曲库 ===")
snap = songs.load_snapshot()
if snap is None:
    songs.refresh_songs()
    snap = songs.load_snapshot()
records = songs.flatten(snap) if snap else []
check("曲库记录 > 5000", len(records) > 5000, f"{len(records)}")

print("\n=== 2. 机台谱面 ===")
chart = maimai.build_chart(records[3000], 3)
check("谱面有音符", len(chart["notes"]) > 120, f"{len(chart['notes'])}")
check("谱面按时间有序", all(a["t"] <= b["t"] for a, b in zip(chart["notes"], chart["notes"][1:])))
check("分区都在 0~7", all(0 <= n["p"] <= 7 for n in chart["notes"]))
html = maimai.cabinet_html(chart)
check("机台 HTML 含投币", "投币" in html)
check("机台 HTML 含评级阈值", "SSS+" in html and "CRITICAL PERFECT" in html)
check("机台 HTML 含成绩码前缀", "MM1:" in html or "'MM1:'" in html)
check("机台 HTML 无外部资源", "http://" not in html and "https://" not in html)
check("评级函数正确", maimai.rank_of(100.6) == "SSS+" and maimai.rank_of(97.2) == "AAA"
      and maimai.rank_of(69) == "D")

print("\n=== 3. 成绩码 ===")
payload = {"g": "dx", "t": "测试曲", "df": "MASTER", "ds": 13.8,
           "ach": 98.72, "rk": "SS", "sc": 987200}
code = playlog.encode(payload)
d1, got = playlog.decode(code)
check("编解码往返成功", d1 and got.get("ach") == 98.72, code[:28] + "...")
check("标题中文不丢", d1 and got.get("t") == "测试曲")
check("截断被识破", not playlog.decode(code[:-3])[0])
check("伪造被识破", not playlog.decode(code.replace("MM1:", "MM1:")[:-1] + "z")[0])
check("乱输入被拒", not playlog.decode("随便写点什么")[0])
check("空输入被拒", not playlog.decode("")[0])
check("越界达成率被拒", not playlog.decode(playlog.encode({"g": "x", "ach": 500}))[0])

U = "round5bot"
playlog.clear(U)
check("登记成功", playlog.submit(U, code)[0])
check("记录能读回", len(playlog.list_plays(U)) == 1)
check("按游戏过滤", len(playlog.list_plays(U, game="dx")) == 1
      and len(playlog.list_plays(U, game="rhythm")) == 0)
b = playlog.best_of(U, "dx")
check("最佳成绩正确", b and b.get("ach") == 98.72)
playlog.submit(U, playlog.encode({"g": "steady", "t": "节奏稳定性", "ach": 70.0, "rk": "SS"}))
dm = playlog.dimension_scores(U)
check("能力维度有值", "节奏" in dm and 0 <= dm["节奏"] <= 100, str(dm))
check("打卡", playlog.checkin(U)[0])
check("今日已打卡", playlog.checked_today(U))
check("连续天数 >= 1", playlog.streak(U) >= 1)
check("重复打卡被拒", not playlog.checkin(U)[0])
playlog.clear(U)
check("清空后无记录", playlog.total_plays(U) == 0)

print("\n=== 4. 段位 ===")
check("段位表 11 级", len(dan.DANS) == 11)
check("段位递增", all(dan.DANS[i]["need"] <= dan.DANS[i + 1]["need"] for i in range(10)))
check("下一段", dan.next_dan("")["name"] == "初段" and dan.next_dan("九段")["name"] == "十段")
check("皆伝之后无段位", dan.next_dan("皆伝") is None)
exam = dan.make_exam(dan.DANS[2], records, "seed-1")
check("出题成功", len(exam) == dan.DANS[2]["n"], f"{len(exam)}")
check("题有三种类型", len({q["kind"] for q in exam}) == 3)
ans = {}
for i, q in enumerate(exam):
    if q["kind"] == "ds":
        ans[i] = q["ds"]
    elif q["kind"] == "bpm":
        ans[i] = q["bpm"]
    else:
        ans[i] = q["answer"]
g = dan.grade_exam(exam, ans)
check("全对接近满分", g["total"] >= 95, str(g["total"]))
g0 = dan.grade_exam(exam, {})
check("全空得 0 分", g0["total"] == 0)
pr_ok = dan.grade_practical(dan.DANS[0], {"ach": 90.0, "ds": 6.0, "t": "x", "df": "EXPERT", "rk": "AAA"})
check("实技达标通过", pr_ok["ok"], pr_ok["msg"])
pr_no = dan.grade_practical(dan.DANS[10], {"ach": 90.0, "ds": 14.0})
check("皆伝不达标", not pr_no["ok"], pr_no["msg"])
pr_low = dan.grade_practical(dan.DANS[4], {"ach": 94.5, "ds": 5.0})
check("低定数加严 1%", (not pr_low["ok"]) and pr_low["need"] == 95.0, pr_low["msg"])
check("无成绩码不放行", not dan.grade_practical(dan.DANS[0], None)["ok"])
D = "dan5bot"
check("发证", dan.award(D, "三段", {"written": 88, "ach": 91.2}))
check("读回段位", dan.get(D)["dan"] == "三段")
check("不降段", not dan.award(D, "初段", {}))
check("可升段", dan.award(D, "五段", {"written": 92}))
check("升段后读回", dan.get(D)["dan"] == "五段")
check("段位牌有名字", "五段" in dan.badge_html("五段", D))
check("阶梯含全部段位", all(d["name"] in dan.ladder_html("五段") for d in dan.DANS))
try:
    import json
    p = config.DATA_DIR / "dan.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        d.pop(D, None)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
except Exception as e:                                       # noqa: BLE001
    print("（清理段位测试数据时出错，可忽略）", e)

print("\n=== 5. 新小游戏 ===")
h_score = arcade.score_html(records)
check("读谱训练含配置题", "交替" in h_score and "BREAK" in h_score)
h_steady = arcade.steady_html()
check("节奏稳定性 32 下", "32" in h_steady)
h_stam = arcade.stamina_html()
check("连打耐力 30 秒", "30" in h_stam)
card = arcade.bingo_cards(records, "s1")
check("宾果卡 25 格", card and len(card["cells"]) == 25)
check("中心是 FREE", card["cells"][12].get("free") is True)
check("每个球都有解", card and all(1 <= len(b["hits"]) <= 8 for b in card["balls"]))
check("球数量足够", card and len(card["balls"]) >= 8, f"{len(card.get('balls', []))}")
h_bingo = arcade.bingo_html(card)
check("宾果页含卡数据", "BPM" in h_bingo or "定数" in h_bingo)
for name, h in [("读谱", h_score), ("稳定性", h_steady), ("耐力", h_stam), ("宾果", h_bingo)]:
    check(f"{name} 无外部资源", "http://" not in h and "https://" not in h)
    check(f"{name} 含成绩码函数", "__code" in h)

print("\n=== 6. 老功能没被碰坏 ===")
check("今日运势还在", minigames.fortune(__import__("datetime").date.today())["rank"] != "")
check("定数竞猜还能出题", minigames.ds_round(records, "x") is not None)

print("\n" + ("ALL PASS" if ok else "有 FAIL"))
sys.exit(0 if ok else 1)
