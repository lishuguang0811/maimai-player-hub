# -*- coding: utf-8 -*-
"""
import_miku.py —— 把你自己的初音立绘导入到 data/miku/

用法：
    .venv\\Scripts\\python.exe work\\import_miku.py <图片所在文件夹>

例如你把从 piapro 下载的图放在 D:\\miku_pics，就运行：
    .venv\\Scripts\\python.exe work\\import_miku.py D:\\miku_pics

脚本会：
1) 读取该文件夹里所有 jpg/png/webp
2) 统一转成 JPEG、缩放到背景尺寸（保持比例，居中裁切）
3) 存到 data/miku/miku_00.jpg, miku_01.jpg ...
导入后无需改代码，app 会自动把它们并入背景轮播池。

版权提醒：请只导入你有权用于个人非商用的图片。
初音未来官方授权渠道：piapro（https://piapro.net）的角色使用规约
明确允许个人非商用二次使用，下载时请遵守其署名等要求。
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MIKU_DIR = ROOT / "data" / "miku"
TARGET_W, TARGET_H = 1600, 1000
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def center_crop_resize(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    ratio = max(TARGET_W / w, TARGET_H / h)
    nw, nh = int(w * ratio), int(h * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - TARGET_W) // 2
    top = (nh - TARGET_H) // 2
    return img.crop((left, top, left + TARGET_W, top + TARGET_H))


def main():
    if len(sys.argv) < 2:
        print("用法: python work/import_miku.py <图片文件夹>")
        sys.exit(1)
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"文件夹不存在: {src}")
        sys.exit(1)
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXTS)
    if not files:
        print("该文件夹里没有 jpg/png/webp 图片。")
        sys.exit(1)
    MIKU_DIR.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(files):
        try:
            img = Image.open(f)
            out = MIKU_DIR / f"miku_{i:02d}.jpg"
            center_crop_resize(img).save(out, "JPEG", quality=88, optimize=True)
            print(f"  [{i+1}/{len(files)}] {f.name} -> {out.name}")
        except Exception as e:                # noqa: BLE001
            print(f"  跳过 {f.name}: {e}")
    print(f"完成：共导入到 {MIKU_DIR}")


if __name__ == "__main__":
    main()