# -*- coding: utf-8 -*-
"""smoke_test.py —— 账号/密码规则/定位/攻略/设置/全难度/等级/爱好/名言/视频链接。"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _env import ROOT  # noqa: F401  必须在 config 之前导入

import config
from modules import accounts, guides, quotes, recommend, settings, songs

today = date.today()
ok = True
PWD = "Pass1234"


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


print("=== 1. 曲库 + 全难度 ===")
snap = songs.load_snapshot()
if snap is None:
    songs.refresh_songs(); snap = songs.load_snapshot()
records = songs.flatten(snap)
check("谱面 >= 5000", len(records) >= 5000, f"{len(records)}")
check("绿黄红紫白全在", set(config.DIFF_ORDER) <= {r["diff"] for r in records})

print("=== 2. 选曲页 + 视频链接 ===")
lib = songs.song_select_view(records)
check("不重复曲目 >= 1200", len(lib) >= 1200, f"{len(lib)}")
check("按定数降序", all(lib[i]["max_ds"] >= lib[i + 1]["max_ds"] for i in range(len(lib) - 1)))
link = songs.bilibili_link("初音ミクの消失")
check("B站搜索链接", link.startswith("https://search.bilibili.com/") and "keyword=" in link)

print("=== 3. 密码规则（8位 数字+大写+小写）===")
check("合法密码", accounts.validate_password("Pass1234")[0])
check("缺大写拒绝", not accounts.validate_password("pass1234")[0])
check("缺小写拒绝", not accounts.validate_password("PASS1234")[0])
check("缺数字拒绝", not accounts.validate_password("PassWord")[0])
check("7位拒绝(少于8)", not accounts.validate_password("Pass123")[0])
check("9位允许(>=8)", accounts.validate_password("Pass12345")[0])
check("20位允许", accounts.validate_password("PassWord12345678ab")[0])

print("=== 4. 账号系统 ===")
accounts.ensure_admin()
check("管理员 admin 已创建", accounts.is_admin(config.ADMIN_NAME))
check("is_admin 不区分大小写/空格", accounts.is_admin(" Admin "))
check("非管理员", not accounts.is_admin("路人甲"))
TEST = "_smoke_t"
accounts.load_accounts().pop(TEST, None)
ok_r, msg_r = accounts.register(TEST, PWD, "2000-01-01", "北京", "高手", ["初音未来"], "1元=2币")
check("注册成功", ok_r, msg_r)
ok_l, _, acc = accounts.login(TEST, PWD)
check("登录成功", ok_l and acc["name"] == TEST and acc["coin_note"] == "1元=2币")
check("错误密码被拒", not accounts.login(TEST, "Wrong999")[0])
check("重复账号被拒", not accounts.register(TEST, PWD, None, "", "高手", [])[0])
check("弱密码注册被拒", not accounts.register("_smoke_x", "weak", None, "", "高手", [])[0])
raw = config.ACCOUNTS_FILE.read_text(encoding="utf-8")
check("不存明文密码", PWD not in raw)
check("改密码", accounts.change_password(TEST, PWD, "Newpass9")[0])
check("新密码可登录", accounts.login(TEST, "Newpass9")[0])
# 手机号 + 自动找回
okp, _ = accounts.register("_smoke_p", "Phone1234", "2000-05-05", "北京", "新手", [], "", "13800138000")
check("带手机号注册", okp)
check("手机号登录", accounts.login("13800138000", "Phone1234")[0])
check("账号名也能登录", accounts.login("_smoke_p", "Phone1234")[0])
check("生日找回成功", accounts.reset_password("13800138000", "2000-05-05", "Newpw1234")[0])
check("找回后可登录", accounts.login("_smoke_p", "Newpw1234")[0])
check("生日错误找回失败", not accounts.reset_password("_smoke_p", "1999-01-01", "Xx123456")[0])
check("未填生日无法找回", (lambda: (accounts.register("_smoke_nb", "Phone1234", None, "", "新手", []), not accounts.reset_password("_smoke_nb", "2000-01-01", "Xx123456")[0])[1])())
check("重复手机号注册被拒", not accounts.register("_smoke_q", "Phone1234", None, "", "新手", [], "", "13800138000")[0])

accs = accounts.load_accounts()
for _n in [TEST, "_smoke_p", "_smoke_q", "_smoke_nb"]:
    accs.pop(_n, None)
accounts.save_accounts(accs)

print("=== 5. 设置覆盖层 ===")
check("默认应用名", settings.get_app_name() == config.APP_NAME)
settings.save_overrides({"app_name": "测试助手"})
check("覆盖生效", settings.get_app_name() == "测试助手")
import os
os.remove(config.SETTINGS_FILE)
check("删除覆盖后回退默认", settings.get_app_name() == config.APP_NAME)

print("=== 7. 攻略专区 ===")
gs = guides.load_guides()
check("攻略 >= 10 条", len(gs) >= 10, f"{len(gs)}")
check("都有分类/标题/内容", all(g.get("category") and g.get("title") and g.get("body") for g in gs))
bc = guides.by_category(gs)
check("按分类分组", len(bc) >= 3, str(list(bc)))
n0 = len(gs)
guides.add_guide("测试", "临时攻略", "内容")
check("添加攻略", len(guides.load_guides()) == n0 + 1)
check("删除攻略", guides.delete_guide(len(guides.load_guides()) - 1) and len(guides.load_guides()) == n0)

print("=== 8. 等级 + 爱好 + 名言 ===")
for lv in config.LEVEL_ORDER:
    tiers = recommend.tiers_for_level(lv)
    check(f"{lv} 三档", len(tiers) == 3)
    picks = recommend.daily_picks(records, today, {"key": "sunny"}, tiers, 3, None, lv)
    flat = [x["song"]["title"] for p in picks for x in p["songs"]]
    check(f"{lv} 9首不重复", len(flat) == 9 and len(set(flat)) == 9)
qs = quotes.load_quotes()
check("名言 >= 20", len(qs) >= 20, f"{len(qs)}")
check("名言年份 2000-2017", all(config.QUOTES_YEAR_MIN <= q["year"] <= config.QUOTES_YEAR_MAX for q in qs))
nq = len(qs)
quotes.add_quote("测试名言", "测试作品", 2010, "测试")
check("添加名言", len(quotes.load_quotes()) == nq + 1)
quotes.delete_quote(len(quotes.load_quotes()) - 1)
check("删除名言", len(quotes.load_quotes()) == nq)

print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)
