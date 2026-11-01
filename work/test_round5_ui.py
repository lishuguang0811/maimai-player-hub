# -*- coding: utf-8 -*-
"""work/test_round5_ui.py —— 用 Streamlit AppTest 真跑一遍第五轮新增的两个页面 + 小游戏分类。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import accounts, playlog                     # noqa: E402
from streamlit.testing.v1 import AppTest                  # noqa: E402

ok = True
PWD = "Maimai2026"
U = "体验官"


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


def html_of(at):
    parts = [str(b.value) for b in at.markdown] + [str(b.value) for b in at.caption]
    return "\n".join(parts)


def nav(at, page):
    at.sidebar.radio[0].set_value(page).run()


accounts.ensure_admin()
if not accounts.find_account(U)[0]:
    accounts.register(U, PWD, "2000-01-01", "北京", "高手", ["初音未来"])
acc = accounts.find_account(U)[1]
if acc and not acc.get("vip"):
    accounts.grant_vip(U)

at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300).run()
check("首次运行无异常", not at.exception, str(at.exception))
at.text_input[0].set_value(U)
at.text_input[1].set_value(PWD)
[b for b in at.button if b.label == "登录"][0].click().run()
check("登录无异常", not at.exception, str(at.exception))
check("已登录", f"你好，{U}" in html_of(at), html_of(at)[:80])

print("\n=== 街机厅页 ===")
nav(at, "🕹 街机厅")
check("街机厅页无异常", not at.exception, str(at.exception))
h = html_of(at)
check("有街机厅标题", "街机厅" in h)
check("有投币/选曲说明", "投币" in h and "选曲" in h)
check("有段位认定", "段位认定" in h)
check("有成绩登记", "成绩登记" in h)
check("有机台 tab", "机台" in h)
check("有搜曲框", any("搜曲名" in (t.label or "") for t in at.text_input),
      str([t.label for t in at.text_input]))
check("有选曲下拉", any("选曲" in (s.label or "") for s in at.selectbox),
      str([s.label for s in at.selectbox]))
check("有难度按钮", any("打这个" in (b.label or "") for b in at.button),
      str([b.label for b in at.button]))
check("机台谱面统计出来了", ("个音符" in h) or ("谱面" in h))
check("评级阈值写在页面上", "SSS+" in h and "CRITICAL PERFECT" in h)

print("\n=== 导入谱面（Simai）===")
_ex_sel = [s for s in at.selectbox if "示例" in (s.label or "")]
check("有示例谱下拉", len(_ex_sel) >= 1, str([s.label for s in at.selectbox]))
_ex_sel[0].set_value([o for o in _ex_sel[0].options if o != "（不选）"][0]).run()
check("选示例无异常", not at.exception, str(at.exception))
_ta_imp = [t for t in at.text_area if "谱面文本" in (t.label or "")]
check("有谱面文本框", len(_ta_imp) >= 1, str([t.label for t in at.text_area]))
check("示例文本灌进去了", _ta_imp and "&bpm=" in str(_ta_imp[0].value),
      str(_ta_imp[0].value[:40]) if _ta_imp else "")
_imp_btn = [b for b in at.button if "解析并打这一张" in (b.label or "")]
check("有解析按钮", len(_imp_btn) >= 1, str([b.label for b in at.button]))
_imp_btn[0].click().run()
check("解析无异常", not at.exception, str(at.exception))
check("解析出难度", any("读出来" in str(s.value) for s in at.success),
      str([str(s.value) for s in at.error])[:160])
check("有难度选择框（解析成功）",
      any("打哪个难度" in (s.label or "") for s in at.selectbox),
      str([s.label for s in at.selectbox]))
_h3 = html_of(at)
check("展示了星星/理论达成率", "理论达成率" in _h3 and "滑动星星" in _h3)

print("\n=== 成绩登记 ===")
code = playlog.encode({"g": "cabinet", "t": "UI测试曲", "df": "MASTER", "ds": 13.7,
                       "ach": 97.5, "rk": "AAA", "sc": 975000, "mx": 120})
_ta = [t for t in at.text_area if "成绩码" in (t.label or "")]
check("找到成绩码输入框", len(_ta) >= 1, str([t.label for t in at.text_area]))
_ta[0].set_value(code)
[b for b in at.button if "登记这局成绩" in (b.label or "")][0].click().run()
check("登记无异常", not at.exception, str(at.exception))
_ok2 = any("已记录" in str(s.value) for s in at.success)
check("登记有反馈", _ok2 or any(p.get("t") == "UI测试曲" for p in playlog.list_plays(U)))
plays = playlog.list_plays(U)
check("落库成功", any(p.get("t") == "UI测试曲" for p in plays), f"{len(plays)} 条")
_at_code = "\n".join(str(getattr(b, "value", "")) for b in at.text_area)
check("最近记录显示出来", "UI测试曲" in html_of(at) or "UI测试曲" in _at_code)

print("\n=== 段位认定 ===")
nav(at, "🕹 街机厅")
_exam_btn = [b for b in at.button if "生成这套题" in (b.label or "")]
check("有生成题目按钮", len(_exam_btn) >= 1)
if _exam_btn:
    _exam_btn[0].click().run()
    check("出题无异常", not at.exception, str(at.exception))
    check("渲染出题目控件", len(at.slider) + len(at.number_input) + len(at.radio) >= 3,
          f"slider{len(at.slider)} num{len(at.number_input)} radio{len(at.radio)}")
    _g = [b for b in at.button if "交卷" in (b.label or "")]
    if _g:
        _g[0].click().run()
        check("交卷无异常", not at.exception, str(at.exception))
        check("给出笔试分数", "笔试" in html_of(at), html_of(at)[-120:])

print("\n=== 玩家档案页 ===")
nav(at, "📊 玩家档案")
check("档案页无异常", not at.exception, str(at.exception))
h2 = html_of(at)
check("有玩家档案标题", "玩家档案" in h2)
check("有能力雷达", "能力雷达" in h2)
check("有成绩单", "成绩单" in h2)
check("有段位阶梯", "初段" in h2 and "皆伝" in h2)
check("雷达 SVG 渲染出来", "<svg" in h2 and "polygon" in h2)
check("显示登记局数", "局" in h2)

print("\n=== 小游戏分类 ===")
nav(at, "🎮 小游戏")
check("游戏页无异常", not at.exception, str(at.exception))
check("分类 8 类", len(at.radio[0].options) == 8, str(at.radio[0].options))
for cat in at.radio[0].options:
    at.radio[0].set_value(cat).run()
    check(f"「{cat}」无异常", not at.exception, str(at.exception))
    _t = html_of(at)
    check(f"「{cat}」有说明文字", len(_t) > 60, f"{len(_t)} 字")

print("\n=== 清理 ===")
playlog.clear(U)
check("测试数据已清理", playlog.total_plays(U) == 0)
try:
    import json
    import config
    p = config.DATA_DIR / "dan.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        d.pop(U.lower().replace(" ", ""), None)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
except Exception:                                          # noqa: BLE001
    pass

print("\n" + ("ALL PASS" if ok else "有 FAIL"))
sys.exit(0 if ok else 1)
