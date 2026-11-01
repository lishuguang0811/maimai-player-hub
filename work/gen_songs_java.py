# -*- coding: utf-8 -*-
"""把本地曲库快照导出成 Java 源码，给原生 APK 当内置曲库用。

注意：不能直接写成 `String[] TITLE = { ... 1281 个 ... }` —— Java 单个方法的
字节码上限是 64KB，<clinit> 会爆。所以压成一个个不超过 ~20KB 的字符串块，
运行时再 split 出来。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from modules import songs  # noqa: E402

OUT = (Path(__file__).resolve().parent.parent / "package" / "native" / "src"
       / "com" / "maimai" / "dx" / "Songs.java")
DIFFS = list(config.DIFF_ORDER[:5])
CHUNK_BYTES = 20000


def esc(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return s


def main() -> None:
    snap = songs.load_snapshot()
    recs = songs.flatten(snap) if snap else []
    if not recs:
        print("[失败] 本地没有曲库快照")
        sys.exit(1)

    best: dict = {}
    for r in recs:
        t = r["title"]
        e = best.get(t)
        if e is None:
            e = {"artist": r.get("artist", ""), "bpm": r.get("bpm"), "ds": [0.0] * 5}
            best[t] = e
        if not e["artist"] and r.get("artist"):
            e["artist"] = r["artist"]
        if r.get("diff") in DIFFS:
            i = DIFFS.index(r["diff"])
            e["ds"][i] = max(e["ds"][i], float(r["ds"]))
        if r.get("bpm"):
            e["bpm"] = r["bpm"]

    items = sorted(best.items(), key=lambda kv: -max(kv[1]["ds"]))
    print(f"曲库：{len(items)} 首")

    # 切成字符串块
    chunks, cur = [], []
    for t, v in items:
        line = "%s\t%s\t%d\t%s" % (
            esc(t), esc(v["artist"]), int(v["bpm"] or 0),
            ",".join("%.1f" % x for x in v["ds"]))
        cur.append(line)
        blob = "\n".join(cur)
        if len(blob.encode("utf-8")) > CHUNK_BYTES:
            chunks.append("\n".join(cur[:-1]))
            cur = [line]
    if cur:
        chunks.append("\n".join(cur))
    print(f"分成 {len(chunks)} 块，最大 {max(len(c.encode('utf-8')) for c in chunks)} 字节")

    L = []
    L.append("package com.maimai.dx;")
    L.append("")
    L.append("/**")
    L.append(" * 内置曲库 —— 由 work/gen_songs_java.py 从本地快照生成，别手改。")
    L.append(" *")
    L.append(" * 数据压成字符串块：Java 单个方法字节码上限 64KB，")
    L.append(" * 直接写死上千个数组元素会把 <clinit> 撑爆，所以运行时再 split。")
    L.append(" */")
    L.append("public final class Songs {")
    L.append("")
    L.append("    public static final String[] DIFF = {"
             + ", ".join('"%s"' % esc(d) for d in DIFFS) + "};")
    L.append("")
    L.append("    public static final String[] DIFF_CN = {"
             + '"BASIC", "ADVANCED", "EXPERT", "MASTER", "Re:MASTER"' + "};")
    L.append("")
    L.append("    private static final String[] DATA = {")
    # Java 字符串字面量不能跨行 —— 换行和 Tab 必须转义成 \n \t
    L.append(",\n".join(
        '        "%s"' % c.replace("\\", "\\\\").replace('"', '\\"')
        .replace("\n", "\\n").replace("\t", "\\t")
        for c in chunks))
    L.append("    };")
    L.append("")
    L.append("    public static String[] title;")
    L.append("    public static String[] artist;")
    L.append("    public static int[] bpm;")
    L.append("    public static float[][] ds;")
    L.append("    public static int[] order;          // 默认按定数从高到低")
    L.append("")
    L.append("    static {")
    L.append("        int n = 0;")
    L.append("        for (int i = 0; i < DATA.length; i++) {")
    L.append("            String s = DATA[i];")
    L.append("            for (int j = 0; j < s.length(); j++) if (s.charAt(j) == '\\n') n++;")
    L.append("            n++;")
    L.append("        }")
    L.append("        title = new String[n];")
    L.append("        artist = new String[n];")
    L.append("        bpm = new int[n];")
    L.append("        ds = new float[n][5];")
    L.append("        order = new int[n];")
    L.append("        int k = 0;")
    L.append("        for (int i = 0; i < DATA.length; i++) {")
    L.append("            String[] lines = DATA[i].split(\"\\n\");")
    L.append("            for (int j = 0; j < lines.length; j++) {")
    L.append("                if (k >= n || lines[j].length() == 0) continue;")
    L.append("                String[] f = lines[j].split(\"\\t\");")
    L.append("                title[k] = f[0];")
    L.append("                artist[k] = f.length > 1 ? f[1] : \"\";")
    L.append("                bpm[k] = f.length > 2 ? Integer.parseInt(f[2]) : 0;")
    L.append("                if (f.length > 3) {")
    L.append("                    String[] p = f[3].split(\",\");")
    L.append("                    for (int d = 0; d < 5 && d < p.length; d++)")
    L.append("                        ds[k][d] = Float.parseFloat(p[d]);")
    L.append("                }")
    L.append("                order[k] = k;")
    L.append("                k++;")
    L.append("            }")
    L.append("        }")
    L.append("    }")
    L.append("")
    L.append("    public static int count() { return title.length; }")
    L.append("")
    L.append("    /** 某首歌可用难度下标（定数 > 0 的那些） */")
    L.append("    public static int[] diffsOf(int i) {")
    L.append("        int n = 0;")
    L.append("        for (int d = 0; d < 5; d++) if (ds[i][d] > 0) n++;")
    L.append("        int[] out = new int[n];")
    L.append("        int k = 0;")
    L.append("        for (int d = 0; d < 5; d++) if (ds[i][d] > 0) out[k++] = d;")
    L.append("        return out;")
    L.append("    }")
    L.append("")
    L.append("    /** 按曲名/艺人模糊搜，返回下标数组 */")
    L.append("    public static int[] search(String q) {")
    L.append("        if (q == null || q.length() == 0) {")
    L.append("            int[] all = new int[title.length];")
    L.append("            for (int i = 0; i < all.length; i++) all[i] = i;")
    L.append("            return all;")
    L.append("        }")
    L.append("        String key = q.toLowerCase();")
    L.append("        int[] tmp = new int[title.length];")
    L.append("        int n = 0;")
    L.append("        for (int i = 0; i < title.length; i++) {")
    L.append("            if (title[i].toLowerCase().indexOf(key) >= 0")
    L.append("                    || artist[i].toLowerCase().indexOf(key) >= 0) tmp[n++] = i;")
    L.append("        }")
    L.append("        int[] out = new int[n];")
    L.append("        System.arraycopy(tmp, 0, out, 0, n);")
    L.append("        return out;")
    L.append("    }")
    L.append("}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"写出 {OUT}（{OUT.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
