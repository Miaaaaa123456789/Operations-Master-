#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本周 9.21—9.27 至今（截至 9.23）与上周同期 9.14—9.16 数值核算"""
import importlib.util
import json
import os
import re
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
spec = importlib.util.spec_from_file_location("wr", os.path.join(REPO, "scripts/week-rollup.py"))
wr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wr)

CUR = ("2026-09-21", "2026-09-23")
PREV = ("2026-09-14", "2026-09-16")


def sec(t):
    print("\n" + "═" * 62)
    print("  " + t)
    print("═" * 62)


def load(f):
    d = json.load(open(os.path.join("data/extra", f), encoding="utf-8"))
    return d if isinstance(d, list) else (d.get("records") or d.get("rows") or [])


def rng(recs, a, b):
    return [r for r in recs if a <= str(r.get("date"))[:10] <= b]


# ── 客服
sec("1. 客服 / 导诊（三表）")
cb, vl, wl = load("service-callback.json"), load("service-visitlog.json"), load("service-workload.json")


def cbstat(a, b):
    s = rng(cb, a, b)
    ar = sum(1 for r in s if r.get("arrived") == "是")
    daily = Counter(str(r["date"])[:10] for r in s)
    return len(s), ar, daily


nc, ac, dc = cbstat(*CUR)
np_, ap, dp = cbstat(*PREV)
print("  回访：本周 %d 条（到院 %d = %.1f%%）vs 上周同期 %d 条（到院 %d = %.1f%%）→ %+.1f%%"
      % (nc, ac, ac / nc * 100, np_, ap, ap / np_ * 100, (nc - np_) / np_ * 100))
print("    本周逐日 %s" % dict(sorted(dc.items())))
print("    上周同期逐日 %s" % dict(sorted(dp.items())))
s = rng(cb, *CUR)
per = Counter(r["staff"] for r in s)
sarr = Counter(r["staff"] for r in s if r.get("arrived") == "是")
print("    本周分人：" + " / ".join("%s %d（到院 %d = %.0f%%）" % (k, v, sarr[k], sarr[k] / v * 100)
                                for k, v in per.most_common()))
print("    满意度 %s" % dict(Counter(r.get("score") for r in s)))

vc, vp = Counter(str(r["date"])[:10] for r in rng(vl, *CUR)), Counter(str(r["date"])[:10] for r in rng(vl, *PREV))
print("  主动服务：本周 %d 条 vs 上周同期 %d 条；逐日 %s" % (sum(vc.values()), sum(vp.values()), dict(sorted(vc.items()))))
print("    本周分人 %s" % dict(Counter(r["staff"] for r in rng(vl, *CUR)).most_common()))

totf = lambda s: sum((r.get("dutyScore") or 0) + (r.get("extraScore") or 0) + (r.get("valueScore") or 0) for r in s)
sc, sp = rng(wl, *CUR), rng(wl, *PREV)
print("  日工作量：本周 %d 人日 / %.0f 分 vs 上周同期 %d 人日 / %.0f 分" % (len(sc), totf(sc), len(sp), totf(sp)))
per = defaultdict(float)
for r in sc:
    per[r["staff"]] += (r.get("dutyScore") or 0) + (r.get("extraScore") or 0) + (r.get("valueScore") or 0)
print("    本周分人 %s" % {k: round(v) for k, v in sorted(per.items(), key=lambda x: -x[1])})
w3 = rng(wl, "2026-09-14", "2026-09-20")
print("  ※ 上周完整周 9.14—9.20：%d 人日 / %.0f 分" % (len(w3), totf(w3)))

# ── 心理
sec("2. 心理组（管理表 V4 每日简报）")
recs = wr.fetch_psy_records()
print("  共 %d 条日报" % len(recs))


def psy(a, b):
    s = [r for r in recs if a <= r["date"] <= b]
    g = lambda fs: int(sum(r[k] for r in s for k in fs))
    daily = Counter(r["date"] for r in s)
    return len(s), g(wr.CONTACT_F), g(wr.ADVICE_F), g(wr.PARENT_F), dict(sorted(daily.items())), s


cn, cc, ca, cp, cdd, cs = psy(*CUR)
pn, pc, pa, pp, pdd, ps = psy(*PREV)
print("  本周 %s~%s：%d 条 · 接触 %d · 咨询 %d · 家长 %d；逐日 %s" % (CUR[0], CUR[1], cn, cc, ca, cp, cdd))
print("  上周同期：%d 条 · 接触 %d · 咨询 %d · 家长 %d；逐日 %s" % (pn, pc, pa, pp, pdd))
print("  本周分人 %s" % dict(Counter(r["name"] for r in cs).most_common()))
for f, lab in [(wr.CONTACT_F, "接触"), (wr.ADVICE_F, "咨询")]:
    d = defaultdict(int)
    for r in cs:
        d[r["name"]] += int(sum(r[k] for k in f))
    print("    %s分人 %s" % (lab, dict(d)))

# ── 管家
sec("3. 管家组（患者有效对接表）")
gj = wr.fetch_gj()
gc, gp = wr.gj_agg(gj, *CUR), wr.gj_agg(gj, *PREV)
print("  %-8s %6s %6s %6s %6s %6s" % ("管家", "对接", "检查", "物理", "心理", "住院"))
for n in ["金林", "朱婧", "菲菲", "国威", "利娟"]:
    k = next((kk for kk in gj if n in kk), None)
    c = gc.get(k, Counter()) if k else Counter()
    print("  %-8s %6d %6d %6d %6d %6d" % (n, c["对接"], c["检查"], c["物理"], c["心理"], c["住院"]))
T, P = Counter(), Counter()
for c in gc.values():
    T.update(c)
for c in gp.values():
    P.update(c)
print("  %-8s %6d %6d %6d %6d %6d" % ("本周合计", T["对接"], T["检查"], T["物理"], T["心理"], T["住院"]))
print("  %-8s %6d %6d %6d %6d %6d" % ("上周同期", P["对接"], P["检查"], P["物理"], P["心理"], P["住院"]))
print("  环比 %+.1f%%；转住院率 %d/%d = %.1f%%（上周同期 %.1f%%）"
      % ((T["对接"] - P["对接"]) / P["对接"] * 100, T["住院"], T["对接"],
         T["住院"] / T["对接"] * 100, P["住院"] / P["对接"] * 100 if P["对接"] else 0))
F = Counter()
for c in wr.gj_agg(gj, "2026-09-14", "2026-09-20").values():
    F.update(c)
print("  ※ 上周完整周：对接 %d / 住院 %d（%.1f%%）" % (F["对接"], F["住院"], F["住院"] / F["对接"] * 100))

# ── 心理团体登记（新周）
sec("4. 团体治疗 / 课程排班（新周）")
for f, lab in [("psych-group", "团体治疗登记"), ("psych-course", "课程排班")]:
    d = load(f + ".json")
    if d and isinstance(d[0], dict):
        print("  %s 字段 %s" % (lab, list(d[0].keys())[:10]))
        recent = [r for r in d if str(r.get("date", ""))[:10] >= "2026-09-21"]
        print("    9.21 起 %d 条" % len(recent))
        for r in recent[:8]:
            print("      ", json.dumps(r, ensure_ascii=False)[:170])
