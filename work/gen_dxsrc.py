#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 modules/dx_cabinet.js 转义成 standalone/maimai-web/dxsrc.js（window.DX_SRC 字符串）。

为什么要有这个脚本：
  dxsrc.js 是「一整行 JS 字符串」，手工改写极易把 \\r\\n 这类正则转义弄坏
  （历史上就因此坏过一次）。所以统一走 json.dumps 生成，绝不手改。

用法：
  python3 work/gen_dxsrc.py
改引擎 -> 只改 modules/dx_cabinet.js -> 跑这个脚本 -> 重新打包。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "modules", "dx_cabinet.js")
DST = os.path.join(ROOT, "standalone", "maimai-web", "dxsrc.js")


def main() -> int:
    if not os.path.exists(SRC):
        print("[x] 找不到 %s" % SRC)
        return 1
    with open(SRC, encoding="utf-8") as f:
        src = f.read()

    # json.dumps 的转义规则是 JS 字符串字面量的子集，结果可直接当 JS 用。
    # ensure_ascii=False 保留中文，避免生成一堆 \uXXXX。
    enc = json.dumps(src, ensure_ascii=False)
    out = (
        "/* 自动生成：由 modules/dx_cabinet.js 转义而成，请勿手工编辑本文件 */\n"
        "/* 修改引擎请改 modules/dx_cabinet.js，然后运行 python3 work/gen_dxsrc.py */\n"
        "window.DX_SRC = " + enc + ";\n"
    )
    with open(DST, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print("[ok] %s" % DST)
    print("     引擎 %d 字符 -> 转义后 %d 字符" % (len(src), len(enc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
