#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本周 9.21—9.27（数据截至 9.22）与上周同期 9.14—9.15 各模块数值核算"""
import importlib.util
import json
import os
import re
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)

spec = importlib.util.spec_from_file_location("wr", os.path.join(REPO, "scripts/week-rollup.py"))
wr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wr)

CUR = ("2026-09-21", "2026-09-22")   # 本周已到数据
PREV = ("2026-09-14", "2026-09-15")  # 上周同期（同 2 天）


def sec(t):
    print("\n" + "═" * 66)
    print("  " + t)
    print("═" * 66)


# ─────────────────────────── 1. 营收
sec("1. 营收（营收日报口径，元）")
DAILY = {
    "2026-09-14": (20100.68, 15521.66),
    "2026-09-15": (34846.27, 43388.86),
    "2026-09-16": (13958.85, 28288.75),
    "2026-09-17": (34398.72, 28935.61),
    "2026-09-18": (40570.20, 32821.31),
    "2026-09-19": (99908.85, 37754.86),
    "2026-09-20": (27228.16, 33779.66),
    "2026-09-21": (22568.92, 30721.41),
    "2026-09-22": (25087.04, 30216.77),
}
print("  %-12s %11s %11s %11s" % ("日期", "门诊", "在院", "合计"))
for d in sorted(DAILY):
    o, i = DAILY[d]
    print("  %-12s %11.2f %11.2f %11.2f" % (d, o, i, o + i))


def agg(a, b):
    ds = [d for d in DAILY if a <= d <= b]
    o = sum(DAILY[d][0] for d in ds)
    i = sum(DAILY[d][1] for d in ds)
    return o, i, o + i, len(ds)


co, ci, ct, cn = agg(*CUR)
po, pi, pt, pn = agg(*PREV)
print("\n  本周 %s~%s（%d 天）：门诊 %.2f 万 / 在院 %.2f 万 / 合计 %.2f 万" % (CUR[0], CUR[1], cn, co / 1e4, ci / 1e4, ct / 1e4))
print("  上周同期 %s~%s（%d 天）：门诊 %.2f 万 / 在院 %.2f 万 / 合计 %.2f 万" % (PREV[0], PREV[1], pn, po / 1e4, pi / 1e4, pt / 1e4))
print("  环比：门诊 %+.1f%% / 在院 %+.1f%% / 合计 %+.1f%%" % ((co - po) / po * 100, (ci - pi) / pi * 100, (ct - pt) / pt * 100))
print("  本周占比：门诊 %.1f%% / 在院 %.1f%%" % (co / ct * 100, ci / ct * 100))
print("  本周至今日均：合计 %.2f 万" % (ct / 1e4 / cn))

# 月度
MTD = sum(v[0] + v[1] for v in DAILY.values() if v)  # 只有 9.14 起
MON = 1538866.16
print("\n  月度累计（9.1—9.22）：%.2f 万（源表 1,538,866.16 元）" % (MON / 1e4))
print("  目标 260 万 → 完成率 %.1f%%；时间进度 %d/30 = %.1f%%；落后 %.1f pt"
      % (MON / 1e4 / 260 * 100, 22, 22 / 30 * 100, 22 / 30 * 100 - MON / 1e4 / 260 * 100))
print("  剩余 %d 天，需日均 %.2f 万" % (30 - 22, (260 - MON / 1e4) / (30 - 22)))

# ─────────────────────────── 2. 客服
sec("2. 客服 / 导诊（三表）")


def load(f):
    d = json.load(open(os.path.join("data/extra", f), encoding="utf-8"))
    return d if isinstance(d, list) else (d.get("records") or d.get("rows") or [])


cb = load("service-callback.json")
vl = load("service-visitlog.json")
wl = load("service-workload.json")


def rng(recs, a, b):
    return [r for r in recs if a <= str(r.get("date"))[:10] <= b]


def cbdays(a, b):
    s = rng(cb, a, b)
    return Counter(str(r["date"])[:10] for r in s), len(s), sum(1 for r in s if r.get("arrived") == "是")


dc, nc, ac = cbdays(*CUR)
dp, np_, ap = cbdays(*PREV)
print("  回访：本周 %d 条（到院 %d = %.1f%%）vs 上周同期 %d 条（到院 %d = %.1f%%）"
      % (nc, ac, ac / nc * 100 if nc else 0, np_, ap, ap / np_ * 100 if np_ else 0))
print("    本周逐日：%s" % dict(sorted(dc.items())))
print("    上周同期逐日：%s" % dict(sorted(dp.items())))
s = rng(cb, *CUR)
print("    本周分人：%s" % dict(Counter(r["staff"] for r in s).most_common()))
print("    满意度分布：%s" % dict(Counter(r.get("score") for r in s)))

vc = Counter(str(r["date"])[:10] for r in rng(vl, *CUR))
vp = Counter(str(r["date"])[:10] for r in rng(vl, *PREV))
print("  主动服务：本周 %d 条 vs 上周同期 %d 条" % (sum(vc.values()), sum(vp.values())))
print("    本周逐日：%s" % dict(sorted(vc.items())))
print("    本周分人：%s" % dict(Counter(r["staff"] for r in rng(vl, *CUR)).most_common()))

sc = rng(wl, *CUR)
sp = rng(wl, *PREV)
tot = lambda s: sum((r.get("dutyScore") or 0) + (r.get("extraScore") or 0) + (r.get("valueScore") or 0) for r in s)
print("  日工作量：本周 %d 人日 / %.0f 分 vs 上周同期 %d 人日 / %.0f 分"
      % (len(sc), tot(sc), len(sp), tot(sp)))
per = defaultdict(float)
for r in sc:
    per[r["staff"]] += (r.get("dutyScore") or 0) + (r.get("extraScore") or 0) + (r.get("valueScore") or 0)
print("    本周分人：%s" % {k: round(v) for k, v in sorted(per.items(), key=lambda x: -x[1])})

# ─────────────────────────── 3. 心理
sec("3. 心理组（管理表 V4 · 咨询师每日简报）")
recs = wr.fetch_psy_records()
print("  共 %d 条日报" % len(recs))
if recs:
    def pday(a, b):
        s = [r for r in recs if a <= r["date"] <= b]
        da = defaultdict(int)
        for r in s:
            da[r["date"]] += 1
        contact = int(sum(r[k] for r in s for k in wr.CONTACT_F))
        advice = int(sum(r[k] for r in s for k in wr.ADVICE_F))
        parent = int(sum(r[k] for r in s for k in wr.PARENT_F))
        return len(s), contact, advice, parent, dict(sorted(da.items()))

    cn_, cc, ca, cp, cdd = pday(*CUR)
    pn_, pc, pa, pp, pdd = pday(*PREV)
    print("  本周 %s~%s：%d 条日报 · 接触 %d · 咨询 %d · 家长 %d" % (CUR[0], CUR[1], cn_, cc, ca, cp))
    print("    逐日条数：%s" % cdd)
    print("  上周同期：%d 条日报 · 接触 %d · 咨询 %d · 家长 %d" % (pn_, pc, pa, pp))
    print("    逐日条数：%s" % pdd)
    s = [r for r in recs if CUR[0] <= r["date"] <= CUR[1]]
    print("  本周分人：%s" % {k: v for k, v in Counter(r["name"] for r in s).items()})
    for f, lab in [(wr.CONTACT_F, "接触"), (wr.ADVICE_F, "咨询"), (wr.PARENT_F, "家长")]:
        d = defaultdict(int)
        for r in s:
            d[r["name"]] += int(sum(r[k] for k in f))
        print("    %s分人：%s" % (lab, dict(d)))

# ─────────────────────────── 4. 管家
sec("4. 管家组（患者有效对接表）")
gj = wr.fetch_gj()
if not gj:
    print("  读取失败")
else:
    gc = wr.gj_agg(gj, *CUR)
    gp = wr.gj_agg(gj, *PREV)
    print("  %-8s %6s %6s %6s %6s %6s" % ("管家", "对接", "检查", "物理", "心理", "住院"))
    for n in ["金林", "朱婧", "菲菲", "国威", "利娟"]:
        k = None
        for kk in gj:
            if n in kk:
                k = kk
        c = gc.get(k, Counter()) if k else Counter()
        print("  %-8s %6d %6d %6d %6d %6d" % (n, c["对接"], c["检查"], c["物理"], c["心理"], c["住院"]))
    T, P = Counter(), Counter()
    for c in gc.values():
        T.update(c)
    for c in gp.values():
        P.update(c)
    print("  %-8s %6d %6d %6d %6d %6d" % ("本周合计", T["对接"], T["检查"], T["物理"], T["心理"], T["住院"]))
    print("  %-8s %6d %6d %6d %6d %6d" % ("上周同期", P["对接"], P["检查"], P["物理"], P["心理"], P["住院"]))
    r = "%+.1f%%" % ((T["对接"] - P["对接"]) / P["对接"] * 100) if P["对接"] else "—"
    print("  对接环比：%d → %d（%s）；转住院率 %d/%d = %.1f%%（上周同期 %.1f%%）"
          % (P["对接"], T["对接"], r, T["住院"], T["对接"],
             T["住院"] / T["对接"] * 100 if T["对接"] else 0,
             P["住院"] / P["对接"] * 100 if P["对接"] else 0))
    # 完整周对照
    full = wr.gj_agg(gj, "2026-09-14", "2026-09-20")
    F = Counter()
    for c in full.values():
        F.update(c)
    print("  ※ 参照 上周完整周 9.14—9.20：对接 %d / 住院 %d（%.1f%%）" % (F["对接"], F["住院"], F["住院"] / F["对接"] * 100 if F["对接"] else 0))
