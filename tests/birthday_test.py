# -*- coding: utf-8 -*-
"""
birthday_test.py —— 生日范围 1900-01-01 ~ 2035-12-31 边界测试（文档第二节硬性要求）

覆盖：合法边界、闰年、非法日期、越界、空值(可选)、register/reset 集成、
以及注册页日期选择器的实际允许范围。
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _env import ROOT  # noqa: F401  必须在 config 之前导入

import config
from modules import accounts
from modules.accounts import validate_birthday

ok = True


def check(label, cond, extra=""):
    global ok
    print(f"[{'PASS' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


print("=== 1. 配置范围 ===")
check("BIRTH_MIN_YEAR=1900", config.BIRTH_MIN_YEAR == 1900)
check("BIRTH_MAX_YEAR=2035", config.BIRTH_MAX_YEAR == 2035)

print("=== 2. validate_birthday 边界 ===")
PASS_CASES = ["1900-01-01", "1900-01-02", "2000-02-29", "2025-01-01",
              "2030-12-31", "2035-12-31"]
REJECT_CASES = ["1899-12-31", "2036-01-01", "1900-02-29", "2001-02-29",
                "2035-13-01", "1900-00-10", "abcd"]
for b in PASS_CASES:
    o, norm, _ = validate_birthday(b)
    check(f"通过 {b}", o and norm == b, norm or "")
for b in REJECT_CASES:
    o, _, msg = validate_birthday(b)
    check(f"拒绝 {b}", not o, msg)
o, norm, msg = validate_birthday("")
check("空值按可选处理(通过,返回None)", o and norm is None, msg)
o, norm, _ = validate_birthday(None)
check("None 按可选处理", o and norm is None)
o, norm, _ = validate_birthday(" 2000-02-29 ")
check("去空格后仍有效", o and norm == "2000-02-29")

print("=== 3. register 集成 ===")
def reg(bday):
    n = f"_bd_{abs(hash(bday)) % 100000}"
    r = accounts.register(n, "Bday1234", bday, "北京", "新手", [])
    if r[0]:
        a = accounts.load_accounts(); a.pop(n, None); accounts.save_accounts(a)
    return r[0], r[1]
check("register 1900-01-01 通过", reg("1900-01-01")[0])
check("register 2035-12-31 通过", reg("2035-12-31")[0])
check("register 2000-02-29 通过", reg("2000-02-29")[0])
check("register 空生日 通过(可选)", reg("")[0])
check("register None 生日 通过", reg(None)[0])
o, m = reg("1899-12-31"); check("register 1899-12-31 拒绝", not o, m)
o, m = reg("2036-01-01"); check("register 2036-01-01 拒绝", not o, m)
o, m = reg("1900-02-29"); check("register 1900-02-29 拒绝", not o, m)
o, m = reg("2001-02-29"); check("register 2001-02-29 拒绝", not o, m)

print("=== 4. reset_password 生日校验 ===")
accounts.register("_bd_r", "Bday1234", "2000-02-29", "北京", "新手", [])
o, m = accounts.reset_password("_bd_r", "2000-02-29", "Newpw1234")
check("正确生日+合法范围可找回", o, m)
o, m = accounts.reset_password("_bd_r", "2036-01-01", "Xx123456")
check("越界生日找回被拒(清晰提示)", not o and ("之间" in m or "范围" in m or "真实" in m), m)
o, m = accounts.reset_password("_bd_r", "", "Xx123456")
check("空生日找回被拒", not o, m)
a = accounts.load_accounts(); a.pop("_bd_r", None); accounts.save_accounts(a)

print("=== 5. 注册页日期选择器实际范围 ===")
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
# 注册表单的生日 date_input：找带 min/max 的那个
di = at.date_input
got_min = got_max = None
for el in di:
    mn = getattr(el, "min_value", None); mx = getattr(el, "max_value", None)
    if mn is not None and mx is not None:
        got_min, got_max = mn, mx; break
if got_min is not None:
    check("选择器下限=1900-01-01", got_min == date(1900, 1, 1), str(got_min))
    check("选择器上限=2035-12-31", got_max == date(2035, 12, 31), str(got_max))
else:
    # AppTest 未暴露 min/max 时，退而校验源码确实把 config 范围传给了 date_input
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    check("源码 date_input 用 config 1900 下限",
          "min_value=date(config.BIRTH_MIN_YEAR, 1, 1)" in src)
    check("源码 date_input 用 config 2035 上限",
          "max_value=date(config.BIRTH_MAX_YEAR, 12, 31)" in src)
    print("   (AppTest 未暴露 min/max，改用源码+配置断言)")

print()
print("=== 总结:", "全部通过" if ok else "存在失败项", "===")
sys.exit(0 if ok else 1)