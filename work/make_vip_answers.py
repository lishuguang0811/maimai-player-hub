# -*- coding: utf-8 -*-
"""
make_vip_answers.py —— 配置私人空间身份验证的三道题与答案（答案只存哈希）

用法： .venv\\Scripts\\python.exe work\\make_vip_answers.py
按提示输入 3 道题和答案，写入 data/vip_questions.json（configured=True）。
明文答案不会写入任何文件。题目请用"只有目标用户知道、非敏感、非公开可搜"的纪念信息。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import vip


def main():
    print("设置私人空间身份验证的 3 道题（答案只存哈希）：")
    qs = []
    for i in range(1, 4):
        q = input("第 %d 题题目: " % i).strip()
        a = input("第 %d 题答案: " % i).strip()
        if not q or not a:
            print("题目和答案都不能为空。"); sys.exit(1)
        qs.append({"q": q, "answer": a})
    vip.save_questions(qs, configured=True)
    print("已写入 data/vip_questions.json（configured=True）。")


if __name__ == "__main__":
    main()