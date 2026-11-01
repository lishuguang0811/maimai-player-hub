package com.maimai.dx;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * 引擎单测 —— 在桌面 JVM 上跑（不碰 android.*），把整首歌真打一遍。
 *
 * 跑法：
 *   javac -encoding UTF-8 -d out Chart.java Game.java EngineTest.java
 *   java -cp out com.maimai.dx.EngineTest
 */
public class EngineTest {

    static int pass = 0, fail = 0;

    static void check(String name, boolean ok, String extra) {
        if (ok) {
            pass++;
            System.out.println("  ✓ " + name + (extra.length() > 0 ? "  " + extra : ""));
        } else {
            fail++;
            System.out.println("  ✗ " + name + "  " + extra);
        }
    }

    static void check(String name, boolean ok) { check(name, ok, ""); }

    // ---------------------------------------------------------------- 模拟演奏

    static final class Ev {
        long t;
        int type;            // 0=按下 1=松开 2=SLIDE 送达
        Chart.Note n;
    }

    /**
     * 把整张谱打一遍。
     *
     * @param jitterMs   每次按键的时间抖动（0 = 全 CP）
     * @param deliver    是否把 SLIDE 送到终点
     * @param holdFull   HOLD 是否按满时长
     */
    static Game play(Chart c, final int jitterMs, boolean deliver, boolean holdFull) {
        final Game g = new Game();
        g.load(c);
        g.start();

        List<Ev> evs = new ArrayList<Ev>();
        long seed = 987654321L;
        for (int i = 0; i < c.notes.size(); i++) {
            Chart.Note n = c.notes.get(i);
            seed = seed * 1103515245L + 12345L;
            int err = jitterMs == 0 ? 0 : (int) ((seed >> 16) % (2L * jitterMs + 1)) - jitterMs;
            long t = n.t + err;
            Ev e = new Ev();
            e.t = t < 0 ? 0 : t;
            e.type = 0;
            e.n = n;
            evs.add(e);
            if (n.k == Chart.HOLD || n.k == Chart.THOLD) {
                Ev r = new Ev();
                r.t = e.t + (holdFull ? n.d + 40 : (long) (n.d * 0.3));
                r.type = 1;
                r.n = n;
                evs.add(r);
            }
            if (n.k == Chart.SLIDE && deliver) {
                Ev s = new Ev();
                s.t = e.t + Math.max(1, n.d / 2);
                s.type = 2;
                s.n = n;
                evs.add(s);
            }
        }
        Collections.sort(evs, new Comparator<Ev>() {
            public int compare(Ev a, Ev b) {
                if (a.t != b.t) return a.t < b.t ? -1 : 1;
                return a.type - b.type;      // 同刻：先按，再送 SLIDE，最后松
            }
        });

        long cur = 0;
        for (int i = 0; i < evs.size(); i++) {
            Ev e = evs.get(i);
            if (e.t > cur) {
                g.advance(e.t);
                cur = e.t;
            }
            if (e.type == 0) {
                if (e.n.isCenter()) g.pressCenter();
                else g.pressRing(e.n.p);
            } else if (e.type == 1) {
                if (e.n.k == Chart.THOLD) g.releaseCenter();
                else g.releaseRing(e.n.p);
            } else {
                if (e.n.wp != null) for (int kk = 0; kk < e.n.wp.length; kk++) g.slideMove(e.n.wp[kk]);
                else g.slideMove(e.n.q);
            }
        }
        g.advance(c.lastEnd() + 3000);
        return g;
    }

    static String fmt(double d) { return String.format("%.4f", d); }

    public static void main(String[] args) {
        System.out.println("== 引擎单测（桌面 JVM）==");

        // ---------- 1. 确定性
        Chart a = Chart.generate("PANDORA PARADOXXX", "x", 190, 15.0, 4, 78);
        Chart b = Chart.generate("PANDORA PARADOXXX", "x", 190, 15.0, 4, 78);
        boolean same = a.notes.size() == b.notes.size();
        if (same) {
            for (int i = 0; i < a.notes.size(); i++) {
                Chart.Note x = a.notes.get(i), y = b.notes.get(i);
                if (x.t != y.t || x.k != y.k || x.p != y.p || x.star != y.star) { same = false; break; }
            }
        }
        check("同曲同难度谱面完全一致", same, a.notes.size() + " 音符");
        Chart d3 = Chart.generate("PANDORA PARADOXXX", "x", 190, 15.0, 3, 78);
        check("换难度谱面就不同", a.notes.size() != d3.notes.size(),
                a.notes.size() + " vs " + d3.notes.size());

        // ---------- 2. 五个难度都有谱、都有星星 SLIDE
        String[] diffName = {"BASIC", "ADVANCED", "EXPERT", "MASTER", "Re:MASTER"};
        for (int di = 0; di < 5; di++) {
            Chart c = Chart.generate("QZKago Requiem", "x", 257, 14.5, di, 78);
            int starSlide = 0;
            for (Chart.Note n : c.notes) if (n.k == Chart.SLIDE && n.star == 1) starSlide++;
            check(diffName[di] + " 有谱且音符数合理",
                    c.notes.size() > 40 && c.notes.size() < 4000,
                    c.notes.size() + " 音符 / " + c.stars + " 星星 / " + starSlide + " 星星SLIDE");
            if (di >= 2) {
                check(diffName[di] + " 有滑动星星", starSlide > 0, starSlide + " 颗");
            }
        }

        // ---------- 3. 全 CP = 理论达成率
        for (int di = 0; di < 5; di++) {
            Chart c = Chart.generate("QZKago Requiem", "x", 257, 14.5, di, 78);
            Game g = play(c, 0, true, true);
            double want = c.theoretical();
            check(diffName[di] + " 全 CP = 理论值 " + fmt(want) + "%",
                    Math.abs(g.achievement() - want) < 1e-6, fmt(g.achievement()) + "%");
            check(diffName[di] + " 全 CP 时 CP 数 = 音符数",
                    g.cnt[Game.CP] == c.notes.size(), g.cnt[Game.CP] + "/" + c.notes.size());
            check(diffName[di] + " 全 CP 达成率 ≤ 101%", g.achievement() <= 101.0001,
                    fmt(g.achievement()));
        }

        // ---------- 4. 手滑：抖动 120ms、SLIDE 不送、HOLD 早松
        Chart c4 = Chart.generate("QZKago Requiem", "x", 257, 14.5, 4, 78);
        Game g4 = play(c4, 120, false, false);
        check("手滑打法达成率明显低于理论值",
                g4.achievement() < c4.theoretical() - 3,
                fmt(g4.achievement()) + "% vs " + fmt(c4.theoretical()) + "%");
        check("手滑会掉 GOOD", g4.cnt[Game.GD] > 0, "GOOD " + g4.cnt[Game.GD]);
        check("手滑会有 MISS", g4.cnt[Game.MISS] > 0, "MISS " + g4.cnt[Game.MISS]);
        check("评级跟着掉", !Game.rankOf(g4.achievement()).startsWith("SSS"),
                Game.rankOf(g4.achievement()));

        // ---------- 5. 判定窗口边界
        check("±33ms = CRITICAL", Game.judgeLevel(0) == Game.CP && Game.judgeLevel(33) == Game.CP
                && Game.judgeLevel(-33) == Game.CP);
        check("34~67ms = PERFECT",
                Game.judgeLevel(34) == Game.P && Game.judgeLevel(67) == Game.P);
        check("68~100ms = GREAT",
                Game.judgeLevel(68) == Game.GR && Game.judgeLevel(100) == Game.GR);
        check("101~150ms = GOOD",
                Game.judgeLevel(101) == Game.GD && Game.judgeLevel(150) == Game.GD);
        check("151ms+ = MISS", Game.judgeLevel(151) == Game.MISS);

        // ---------- 6. 评级
        check("101% = SSS+", Game.rankOf(101.0).equals("SSS+"));
        check("100% = SSS", Game.rankOf(100.0).equals("SSS"));
        check("99.6% = SS+", Game.rankOf(99.6).equals("SS+"));
        check("90% = A", Game.rankOf(90.0).equals("A"));
        check("50% = D", Game.rankOf(50.0).equals("D"));

        // ---------- 7. 星星加成封顶
        Chart tiny = Chart.generate("Tiny Star Test", "x", 120, 1.0, 0, 30);
        check("低难度也有谱", tiny.notes.size() > 10, tiny.notes.size() + " 音符");
        check("理论值在 100~101 之间",
                tiny.theoretical() >= 100.0 && tiny.theoretical() <= 101.0,
                fmt(tiny.theoretical()));

        // ---------- 8. Simai 解析
        String simai = "&bpm=150\n&title=Test Song\n&artist=Test\n"
                + "#Master\n"
                + "1,2,3b,4h[4:1],5^7,6-8,1v3,A1,E5,C1h[2:1]\n";
        Chart sc = Chart.parseSimai(simai, 4);
        int taps = 0, holds = 0, slides = 0, touches = 0, exs = 0, tholds = 0, stars = 0;
        for (Chart.Note n : sc.notes) {
            switch (n.k) {
                case Chart.TAP: taps++; break;
                case Chart.HOLD: holds++; break;
                case Chart.SLIDE: slides++; break;
                case Chart.TOUCH: touches++; break;
                case Chart.EX: exs++; break;
                default: tholds++; break;
            }
            if (n.star == 1) stars++;
        }
        check("Simai 认出了 TAP", taps == 3, "tap=" + taps);
        check("Simai 认出了 HOLD", holds == 1, "hold=" + holds);
        check("Simai 认出了 SLIDE（3 种花样）", slides == 3, "slide=" + slides);
        check("Simai 认出了 TOUCH", touches == 1, "touch=" + touches);
        check("Simai 认出了 EX", exs == 1, "ex=" + exs);
        check("Simai 认出了 TOUCH HOLD", tholds == 1, "thold=" + tholds);
        check("Simai 认出了星星", stars == 1, "star=" + stars);
        check("Simai 标题读到了", "Test Song".equals(sc.title), sc.title);
        check("Simai BPM 读到了", sc.bpm == 150, String.valueOf(sc.bpm));

        // ---------- 9. 谱面本身不打架（同一分区不能同时两颗环上音符）
        for (int di = 0; di < 5; di++) {
            Chart c = Chart.generate("Schwarzschild", "x", 220, 15.0, di, 78);
            int conflict = 0;
            for (int i = 0; i < c.notes.size(); i++) {
                Chart.Note x = c.notes.get(i);
                if (x.isCenter()) continue;
                for (int j = i + 1; j < c.notes.size(); j++) {
                    Chart.Note y = c.notes.get(j);
                    if (y.t - x.t > 200) break;
                    if (y.isCenter()) continue;
                    if (y.p == x.p && Math.abs(y.t - x.t) < 45) conflict++;
                }
            }
            check(diffName[di] + " 同分区无冲突", conflict == 0, conflict + " 处");
        }

        // ---------- 10. 内置曲库（Songs 是纯 Java，也能在这儿验）
        check("曲库解析出了歌", Songs.count() > 500, Songs.count() + " 首");
        check("曲库第一首有名字", Songs.title[0] != null && Songs.title[0].length() > 0,
                Songs.title[0]);
        boolean dsOk = true;
        int withBpm = 0;
        for (int i = 0; i < Songs.count(); i++) {
            float mx = 0;
            for (int d = 0; d < 5; d++) mx = Math.max(mx, Songs.ds[i][d]);
            if (mx <= 0) dsOk = false;
            if (Songs.bpm[i] > 0) withBpm++;
            if (Songs.diffsOf(i).length == 0) dsOk = false;
        }
        check("每首歌都有定数和可用难度", dsOk);
        check("大部分歌有 BPM", withBpm > Songs.count() * 0.9,
                withBpm + "/" + Songs.count());
        check("搜得到曲名", Songs.search("PANDORA").length > 0,
                Songs.search("PANDORA").length + " 条");
        check("搜不到就返回全部", Songs.search("").length == Songs.count());

        // 用真实曲库数据开一局，确认端到端没问题
        int si = Songs.search("PANDORA")[0];
        int[] dd = Songs.diffsOf(si);
        Chart real = Chart.generate(Songs.title[si], Songs.artist[si],
                Songs.bpm[si], Songs.ds[si][dd[dd.length - 1]], dd[dd.length - 1], 78);
        Game gr = play(real, 0, true, true);
        check("真实曲库开一局：全 CP = 理论值",
                Math.abs(gr.achievement() - real.theoretical()) < 1e-6,
                Songs.title[si] + " " + fmt(gr.achievement()) + "%");

        // ---------- 11. 滑星星手感（AstroDX 风格：按星星 → 按序划过箭头 → 送达）
        {
            // 路径计算：p=0,q=3 无花样 → 沿环短弧 [1,2,3]
            int[] wp0 = Chart.slideWaypoints(0, 3, null);
            check("滑星星：路径箭头 = [1,2,3]", wp0.length == 3 && wp0[0] == 1 && wp0[1] == 2 && wp0[2] == 3);
            // 穿心花样 line：[-1(中央), q]
            int[] wpl = Chart.slideWaypoints(0, 3, "line");
            check("滑星星：line 穿心路径 = [中央,3]", wpl.length == 2 && wpl[0] == -1 && wpl[1] == 3);

            // 接住 + 按序划箭头 + 送达 = CP
            Chart cs = new Chart();
            cs.notes = new ArrayList<Chart.Note>();
            Chart.Note ns1 = new Chart.Note();
            ns1.t = 1000; ns1.k = Chart.SLIDE; ns1.p = 0; ns1.q = 3; ns1.star = 1; ns1.d = 150; ns1.s = "arc";
            cs.notes.add(ns1); cs.beat = 400;
            Game ng1 = new Game(); ng1.load(cs); ng1.start();
            ng1.advance(1000);
            int k1 = ng1.pressRing(0);
            check("滑星星：在起点接住返回 SLIDE", k1 == Chart.SLIDE);
            check("滑星星：接住瞬间还没判定", !ns1.done);
            ng1.advance(1010);
            int r1 = ng1.slideMove(1);   // 划过第 1 颗箭头 → tick
            int r2 = ng1.slideMove(2);   // 划过第 2 颗箭头 → tick
            int r3 = ng1.slideMove(3);   // 划到终点 → 送达
            check("滑星星：逐箭头划过返回 tick(1)", r1 == 1 && r2 == 1, "r1=" + r1 + " r2=" + r2);
            check("滑星星：拖到终点落地 CP(2)", r3 == 2, "r3=" + r3);
            check("滑星星：送达后记为 1 个 CP", ng1.cnt[Game.CP] == 1 && ns1.done);

            // 容忍跳过中间箭头：从起点直接划到终点也送达（slideTolerance）
            Chart cs2 = new Chart(); cs2.notes = new ArrayList<Chart.Note>();
            Chart.Note ns2 = new Chart.Note();
            ns2.t = 1000; ns2.k = Chart.SLIDE; ns2.p = 0; ns2.q = 3; ns2.star = 1; ns2.d = 150; ns2.s = "arc";
            cs2.notes.add(ns2); cs2.beat = 400;
            Game ng2 = new Game(); ng2.load(cs2); ng2.start();
            ng2.advance(1000); ng2.pressRing(0); ng2.advance(1010);
            int r2b = ng2.slideMove(3);
            check("滑星星：跳中间直接到终点也送达", r2b == 2 && ng2.cnt[Game.CP] == 1 && ns2.done);

            // 接住但抬指没收尾 = MISS
            Chart cs3 = new Chart(); cs3.notes = new ArrayList<Chart.Note>();
            Chart.Note ns3 = new Chart.Note();
            ns3.t = 1000; ns3.k = Chart.SLIDE; ns3.p = 0; ns3.q = 3; ns3.star = 1; ns3.d = 150; ns3.s = "arc";
            cs3.notes.add(ns3); cs3.beat = 400;
            Game ng3 = new Game(); ng3.load(cs3); ng3.start();
            ng3.advance(1000); ng3.pressRing(0); ng3.advance(1010); ng3.lift(0);
            check("滑星星：接住后抬指没收尾 = MISS",
                    ng3.cnt[Game.MISS] == 1 && ns3.done, "miss=" + ng3.cnt[Game.MISS]);

            // 接住但超时没收尾 = MISS
            Chart cs4 = new Chart(); cs4.notes = new ArrayList<Chart.Note>();
            Chart.Note ns4 = new Chart.Note();
            ns4.t = 1000; ns4.k = Chart.SLIDE; ns4.p = 0; ns4.q = 3; ns4.star = 1; ns4.d = 150; ns4.s = "arc";
            cs4.notes.add(ns4); cs4.beat = 400;
            Game ng4 = new Game(); ng4.load(cs4); ng4.start();
            ng4.advance(1000); ng4.pressRing(0);
            ng4.advance(1000 + 150 + 120 + 200);   // 超过收尾时限
            check("滑星星：接住后超时没收尾 = MISS",
                    ng4.cnt[Game.MISS] == 1 && ns4.done, "miss=" + ng4.cnt[Game.MISS]);

            // 完全没碰过 = MISS
            Chart cs5 = new Chart(); cs5.notes = new ArrayList<Chart.Note>();
            Chart.Note ns5 = new Chart.Note();
            ns5.t = 1000; ns5.k = Chart.SLIDE; ns5.p = 0; ns5.q = 3; ns5.star = 1; ns5.d = 150; ns5.s = "arc";
            cs5.notes.add(ns5); cs5.beat = 400;
            Game ng5 = new Game(); ng5.load(cs5); ng5.start();
            ng5.advance(1000 + 150 + 1);           // 过了判定窗口
            check("滑星星：完全没碰 = MISS",
                    ng5.cnt[Game.MISS] == 1 && ns5.done, "miss=" + ng5.cnt[Game.MISS]);

            // 提前按住面板，星星到达时自动接住；然后按序划箭头送达 = CP
            Chart cs6 = new Chart(); cs6.notes = new ArrayList<Chart.Note>();
            Chart.Note ns6 = new Chart.Note();
            ns6.t = 1000; ns6.k = Chart.SLIDE; ns6.p = 0; ns6.q = 3; ns6.star = 1; ns6.d = 150; ns6.s = "arc";
            cs6.notes.add(ns6); cs6.beat = 400;
            Game ng6 = new Game(); ng6.load(cs6); ng6.start();
            ng6.heldMask = (1 << 0);               // 第 0 区一直按着
            ng6.advance(1000);                      // 星星到达，自动接住
            check("滑星星：提前按住也能自动接住", ns6.captured && ns6.sliding);
            ng6.advance(1010);
            ng6.slideMove(1); ng6.slideMove(2); int dl6 = ng6.slideMove(3);
            check("滑星星：自动接住后按序划箭头送达 = CP", dl6 == 2 && ng6.cnt[Game.CP] == 1);

            // line 穿心：划过中央再划到终点也送达
            Chart cs7 = new Chart(); cs7.notes = new ArrayList<Chart.Note>();
            Chart.Note ns7 = new Chart.Note();
            ns7.t = 1000; ns7.k = Chart.SLIDE; ns7.p = 0; ns7.q = 3; ns7.star = 1; ns7.d = 150; ns7.s = "line";
            cs7.notes.add(ns7); cs7.beat = 400;
            Game ng7 = new Game(); ng7.load(cs7); ng7.start();
            ng7.advance(1000); ng7.pressRing(0); ng7.advance(1010);
            int rl = ng7.slideMove(-2);             // 中央屏（s==-2 内部按 -1）
            int rl2 = ng7.slideMove(3);
            check("滑星星：line 穿心（过中央）送达 = CP", rl2 == 2 && ng7.cnt[Game.CP] == 1 && ns7.done);
        }

        System.out.println();
        System.out.println(pass + " 通过 / " + fail + " 失败");
        if (fail > 0) System.exit(1);
    }
}
