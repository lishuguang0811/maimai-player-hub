# -*- coding: utf-8 -*-
"""测试公共环境：把 MPH_DATA_DIR 指向临时目录，绝不碰真实 data/。"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="mph-test-"))
_DATA = _TMP / "data"
shutil.copytree(
    ROOT / "data", _DATA,
    ignore=shutil.ignore_patterns(
        "accounts.json", "userdata.json", "settings.json",
        "galgame_saves.json", "playlog.json", "dan.json",
        "INITIAL_ADMIN_PASSWORD.txt", "share", "outputs",
    ),
)
os.environ["MPH_DATA_DIR"] = str(_DATA)
os.environ.setdefault("MPH_ADMIN_PASSWORD", "Admin1234")
atexit.register(lambda: shutil.rmtree(_TMP, ignore_errors=True))

DATA = _DATA
