# -*- coding: utf-8 -*-
"""
accounts.py —— 账号系统（3.0：注册校验 + scrypt 哈希 + role/vip_status 权限）

权限模型（文档 2.4）：
- role: "user" / "admin"
- vip_status: None(普通) / "pending"(注册了主人用户名但未验证) / "verified"(已验证)
- vip_verified_at: 验证通过时间
区分四类：普通用户 / 已注册未验证 / 已验证 VIP / 管理员。
"用户名是主人" != "已有权限"——必须通过身份验证才授予访问权。

密码：新注册用 hashlib.scrypt（文档要求的专用 KDF）；旧的 sha256 账号登录时
自动迁移为 scrypt。盐随机，不存明文，不联网。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import date, datetime
from pathlib import Path

import config

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
SCRYPT_MAXMEM = 64 * 1024 * 1024


def _hash_scrypt(password: str, salt_hex: str) -> str:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=SCRYPT_MAXMEM,
    ).hex()


def _hash_sha256(password: str, salt_hex: str) -> str:
    return hashlib.sha256((salt_hex + password).encode("utf-8")).hexdigest()


def _hash(password: str, salt_hex: str, kdf: str = "scrypt") -> str:
    return _hash_scrypt(password, salt_hex) if kdf == "scrypt" else _hash_sha256(password, salt_hex)


def _norm(name: str) -> str:
    return (name or "").strip().replace(" ", "").lower()


def _norm_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def validate_password(pw: str) -> tuple[bool, str]:
    if not pw or len(pw) < config.PW_MIN_LEN:
        return False, f"密码至少 {config.PW_MIN_LEN} 位。"
    if not re.search(r"\d", pw):
        return False, "密码必须包含数字。"
    if not re.search(r"[A-Z]", pw):
        return False, "密码必须包含大写字母。"
    if not re.search(r"[a-z]", pw):
        return False, "密码必须包含小写字母。"
    return True, "密码格式正确。"


def validate_username(name: str) -> tuple[bool, str]:
    name = (name or "").strip()
    if not name:
        return False, "用户名不能为空。"
    if len(name) > 20:
        return False, "用户名太长（最多 20 字）。"
    if not re.fullmatch(r"[\w\u4e00-\u9fff\- ]+", name):
        return False, "用户名只能包含字母、数字、中文、下划线、连字符。"
    return True, "用户名格式正确。"


def validate_phone(phone: str) -> tuple[bool, str]:
    p = _norm_phone(phone)
    if not p:
        return True, "未填手机号。"
    if not (6 <= len(p) <= 15):
        return False, "手机号应为 6~15 位数字。"
    return True, "手机号格式正确。"


def validate_birthday(birthday) -> tuple[bool, str | None, str]:
    """
    生日校验（前后端统一规则）：可选字段，空=允许。
    非空时必须是真实日历日期(YYYY-MM-DD，含闰年判断)，且在
    config.BIRTH_MIN_YEAR-01-01 ~ config.BIRTH_MAX_YEAR-12-31 之间。
    返回 (ok, 规范化字符串或None, 提示)。
    """
    if birthday is None or (isinstance(birthday, str) and not birthday.strip()):
        return True, None, "未填生日（可选）。"
    s = str(birthday).strip()
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()   # 拒绝 1900-02-29 / 2001-02-29 等假日期
    except ValueError:
        return False, None, "生日格式应为 YYYY-MM-DD，且必须是真实存在的日期。"
    lo = date(config.BIRTH_MIN_YEAR, 1, 1)
    hi = date(config.BIRTH_MAX_YEAR, 12, 31)
    if d < lo or d > hi:
        return False, None, (f"生日必须在 {config.BIRTH_MIN_YEAR}-01-01 到 "
                             f"{config.BIRTH_MAX_YEAR}-12-31 之间。")
    return True, s, "生日有效。"


def load_accounts() -> dict:
    p = Path(config.ACCOUNTS_FILE)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:                        # noqa: BLE001
        return {}


def save_accounts(accounts: dict) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    Path(config.ACCOUNTS_FILE).write_text(
        json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_accounts() -> None:
    """给旧账号补 role/vip_status/vip_verified_at/kdf 字段（不破坏已有数据）。"""
    accounts = load_accounts()
    changed = False
    for key, acc in accounts.items():
        if "role" not in acc:
            acc["role"] = "admin" if key == _norm(config.ADMIN_NAME) else "user"; changed = True
        if "vip_status" not in acc:
            acc["vip_status"] = None; changed = True
        if "vip_verified_at" not in acc:
            acc["vip_verified_at"] = None; changed = True
        if "kdf" not in acc:
            acc["kdf"] = "sha256"; changed = True
        acc.setdefault("phone", acc.get("phone", ""))
        acc.setdefault("coin_note", acc.get("coin_note", ""))
    if changed:
        save_accounts(accounts)


def find_account(name_or_phone: str) -> tuple[str | None, dict | None]:
    accounts = load_accounts()
    key = _norm(name_or_phone)
    if key in accounts:
        return key, accounts[key]
    phone = _norm_phone(name_or_phone)
    if phone:
        for k, acc in accounts.items():
            if _norm_phone(acc.get("phone", "")) == phone:
                return k, acc
    return None, None


def is_owner_name(name: str) -> bool:
    return _norm(name) == _norm(config.OWNER_NAME)


def register(name, password, birthday, city, level, hobbies,
             coin_note: str = "", phone: str = "") -> tuple[bool, str]:
    ok, msg = validate_username(name)
    if not ok:
        return False, msg
    name = name.strip()
    ok, msg = validate_password(password)
    if not ok:
        return False, msg
    ok, msg = validate_phone(phone)
    if not ok:
        return False, msg
    ok_b, norm_bday, msg_b = validate_birthday(birthday)
    if not ok_b:
        return False, msg_b
    if level not in config.LEVELS:
        return False, f"等级不合法，可选：{'/'.join(config.LEVEL_ORDER)}"

    accounts = load_accounts()
    key = _norm(name)
    for existing in accounts.values():
        if _norm(existing.get("name", "")) == key:
            return False, "这个用户名已经被注册了，换一个吧。"
    phone_n = _norm_phone(phone)
    if phone_n:
        for existing in accounts.values():
            if _norm_phone(existing.get("phone", "")) == phone_n:
                return False, "这个手机号已被其它账号绑定。"

    salt = secrets.token_hex(16)
    # 注册主人用户名 -> 创建为待验证状态（不自动授权，需后续身份验证）
    vip_status = "pending" if is_owner_name(name) else None
    accounts[key] = {
        "name": name, "salt": salt, "kdf": "scrypt",
        "password_hash": _hash(password, salt, "scrypt"),
        "birthday": norm_bday,
        "city": city or config.DEFAULT_CITY["name"],
        "level": level, "hobbies": hobbies or [],
        "coin_note": coin_note or "", "phone": phone_n,
        "role": "user", "vip_status": vip_status, "vip_verified_at": None,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    save_accounts(accounts)
    if vip_status == "pending":
        return True, f"已创建「{name}」，请完成专属身份验证以开通 VIP。"
    return True, f"注册成功，欢迎 {name}！"


def _verify_pw(acc: dict, password: str) -> bool:
    kdf = acc.get("kdf", "sha256")
    return _hash(password or "", acc.get("salt", ""), kdf) == acc.get("password_hash")


def login(name_or_phone, password) -> tuple[bool, str, dict | None]:
    key, acc = find_account(name_or_phone)
    if acc is None:
        return False, "账号不存在，先去注册一个吧。", None
    if not _verify_pw(acc, password):
        return False, "密码不对。", None
    # 登录成功：旧 sha256 账号顺手迁移为 scrypt
    if acc.get("kdf", "sha256") != "scrypt":
        salt = secrets.token_hex(16)
        acc["salt"] = salt; acc["kdf"] = "scrypt"
        acc["password_hash"] = _hash(password, salt, "scrypt")
        allacc = load_accounts(); allacc[key] = acc; save_accounts(allacc)
    return True, f"欢迎回来，{acc['name']}！", acc


def change_password(name, old_pw, new_pw) -> tuple[bool, str]:
    key, acc = find_account(name)
    if acc is None:
        return False, "账号不存在。"
    if not _verify_pw(acc, old_pw):
        return False, "原密码不对。"
    ok, msg = validate_password(new_pw)
    if not ok:
        return False, msg
    salt = secrets.token_hex(16)
    acc["salt"] = salt; acc["kdf"] = "scrypt"
    acc["password_hash"] = _hash(new_pw, salt, "scrypt")
    allacc = load_accounts(); allacc[key] = acc; save_accounts(allacc)
    return True, "密码已更新。"


def reset_password(name_or_phone, birthday, new_pw) -> tuple[bool, str]:
    key, acc = find_account(name_or_phone)
    if acc is None:
        return False, "找不到这个账号/手机号。"
    if not (birthday or "").strip():
        return False, "找回需要提供注册时填写的生日。"
    ok_b, norm_bday, msg_b = validate_birthday(birthday)
    if not ok_b:
        return False, msg_b
    stored = (acc.get("birthday") or "").strip()
    if not stored:
        return False, "这个账号注册时没填生日，无法用生日找回。"
    if stored != norm_bday:
        return False, "生日不对，找回失败。"
    ok, msg = validate_password(new_pw)
    if not ok:
        return False, msg
    salt = secrets.token_hex(16)
    acc["salt"] = salt; acc["kdf"] = "scrypt"
    acc["password_hash"] = _hash(new_pw, salt, "scrypt")
    allacc = load_accounts(); allacc[key] = acc; save_accounts(allacc)
    return True, "找回成功，密码已重置，请用新密码登录。"


def grant_vip(name: str) -> bool:
    """身份验证通过后，由后端授予 VIP（不能由前端决定）。"""
    key, acc = find_account(name)
    if acc is None:
        return False
    acc["vip_status"] = "verified"
    acc["vip_verified_at"] = datetime.now().isoformat(timespec="seconds")
    allacc = load_accounts(); allacc[key] = acc; save_accounts(allacc)
    return True


def is_vip(acc: dict | None) -> bool:
    return bool(acc) and acc.get("vip_status") == "verified"


def is_admin(name: str) -> bool:
    _, acc = find_account(name)
    return bool(acc) and acc.get("role") == "admin"


def update_field(name, **fields) -> bool:
    key, acc = find_account(name)
    if acc is None:
        return False
    acc.update(fields)
    allacc = load_accounts(); allacc[key] = acc; save_accounts(allacc)
    return True


def _random_admin_password() -> str:
    """生成一个满足密码规则（8 位以上，含数字/大写/小写）的随机密码。"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(16))
        if validate_password(pwd)[0]:
            return pwd


def ensure_admin(default_password: str | None = None) -> None:
    """首次运行时创建管理员账号。

    密码来源优先级：显式参数 > 环境变量 MPH_ADMIN_PASSWORD > 随机生成。
    随机生成时会写入 data/INITIAL_ADMIN_PASSWORD.txt，登录后请立即修改。
    """
    migrate_accounts()
    accounts = load_accounts()
    if _norm(config.ADMIN_NAME) in accounts:
        return
    password = (default_password or os.environ.get(config.ADMIN_PASSWORD_ENV, "")).strip()
    generated = False
    if not password or not validate_password(password)[0]:
        password = _random_admin_password()
        generated = True
    salt = secrets.token_hex(16)
    accounts[_norm(config.ADMIN_NAME)] = {
        "name": config.ADMIN_NAME, "salt": salt, "kdf": "scrypt",
        "password_hash": _hash(password, salt, "scrypt"),
        "birthday": None, "city": config.DEFAULT_CITY["name"],
        "level": config.DEFAULT_LEVEL, "hobbies": [],
        "coin_note": "", "phone": "",
        "role": "admin", "vip_status": None, "vip_verified_at": None,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    save_accounts(accounts)
    if generated:
        note = config.DATA_DIR / "INITIAL_ADMIN_PASSWORD.txt"
        note.write_text(
            f"首次运行自动创建的管理员账号：{config.ADMIN_NAME}\n"
            f"临时密码：{password}\n"
            "登录后请在「我的与设置」里修改密码，并删除本文件。\n",
            encoding="utf-8",
        )
        print(f"[舞萌助手] 已创建管理员 {config.ADMIN_NAME}，临时密码已写入 {note}")