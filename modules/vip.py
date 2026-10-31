# -*- coding: utf-8 -*-
"""
vip.py —— 私人空间身份验证（注册主人用户名 -> 回答身份问题 -> 授予访问权）

- 问题与答案存 data/vip_questions.json，答案只存 SHA-256 哈希，不存明文，
  也不写进公开曲库 JSON / 前端代码。
- verify_answers 全对才返回 True，不透露哪一题错、不泄露正确答案。
- 限流/冷却在 app 层用 session_state 计数。
- configured=False 时视为未配置，验证页会提示先设置题目。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import config

QUESTIONS_FILE = config.DATA_DIR / "vip_questions.json"


def _norm_ans(a: str) -> str:
    return (a or "").strip().lower()


def hash_answer(a: str) -> str:
    return hashlib.sha256(_norm_ans(a).encode("utf-8")).hexdigest()


def _load() -> dict:
    if QUESTIONS_FILE.exists():
        try:
            d = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                return d
        except Exception:                    # noqa: BLE001
            pass
    return {"configured": False, "questions": []}


def is_configured() -> bool:
    d = _load()
    return bool(d.get("configured")) and len(d.get("questions", [])) > 0


def question_texts() -> list[str]:
    return [q.get("q", "") for q in _load().get("questions", [])]


def verify_answers(answers: list[str]) -> bool:
    """全部答对才通过；任何一题错都返回 False，不透露具体哪题。"""
    d = _load()
    qs = d.get("questions", [])
    if not d.get("configured") or not qs:
        return False
    if len(answers) != len(qs):
        return False
    for q, a in zip(qs, answers):
        if hash_answer(a) != (q.get("a_hash") or ""):
            return False
    return True


def save_questions(questions: list[dict], configured: bool = True) -> None:
    """questions: [{"q": 题目, "answer": 明文答案}]，转成哈希后落盘。"""
    out = [{"q": it.get("q", ""), "a_hash": hash_answer(it.get("answer", ""))}
           for it in questions]
    data = {"note": "私人空间身份验证问题，答案仅存哈希。", "configured": configured,
            "questions": out}
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    QUESTIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")