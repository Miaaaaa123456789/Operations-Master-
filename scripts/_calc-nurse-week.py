#!/usr/bin/env python3
# 一次性：按 9.20—9.26 护理日表 + 周排名表，算出全部新口径
import os, json
import openpyxl

D = "/Users/opp/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_w82ow8s27ffg22_3c28/temp/drag"
FILES = [("9.20", "9.20(1).xlsx"), ("9.21", "9.21(1).xlsx"), ("9.22", "9.22(1).xlsx"),
         ("9.23", "9.23(1).xlsx"), ("9.24", "9.24(1).xlsx"), ("9.25", "9-25(1).xlsx"),
         ("9.26", "9.26(1).xlsx")]
DAYS = [d for d, _ in FILES]

def cell(ws, r, c):
    v = ws.cell(row=r, column=c).value
    return v

def f2(x):
    return None if x is None else round(float(x), 4)

daily = {}
per = {}   # per[nurse][day] = dict(B..K)
order = []
for day, fn in FILES:
    wb = openpyxl.load_workbook(os.path.join(D, fn), data_only=True)
    ws = wb.worksheets[0]
    tot = {"B": 0, "C": 0, "D": 0, "E": 0, "F": 0, "H": 0, "I": 0, "rows": 0}
    for r in range(4, ws.max_row + 1):
        name = cell(ws, r, 1)
        if name is None:
            continue
        name = str(name).strip()
        if name in ("合计", "平均值", "最大值", "最小值"):
            continue
        rec = {}
        for col, key in [(2, "B"), (3, "C"), (4, "D"), (5, "E"), (6, "F"), (7, "G"), (8, "H"), (9, "I"), (10, "J"), (11, "K")]:
            rec[key] = f2(cell(ws, r, col)) if cell(ws, r, col) is not None else None
        per.setdefault(name, {})[day] = rec
        if name not in order:
            order.append(name)
        if rec.get("J"):
            tot["rows"] += 1
        for k in ("B", "C", "D", "E", "F", "H", "I"):
            if rec.get(k):
                tot[k] += rec[k]
    daily[day] = tot

print("== 逐日合计（护士日表）==")
print("日期  在岗  分管 入院 出院  应做  实做   完成率   约束  心理咨询")
SE = SF = 0
for d in DAYS:
    t = daily[d]
    SE += t["E"]; SF += t["F"]
    print("%s  %2d  %5g %4g %4g  %5g %5g  %6.2f%%  %4g  %g" % (
        d, t["rows"], t["B"], t["C"], t["D"], t["E"], t["F"],
        (t["F"] / t["E"] * 100 if t["E"] else 0), t["I"], t["H"]))
print("合计      分管 %g  入院 %g  出院 %g  应做 %g  实做 %g  完成率 %.2f%%  未做 %g  约束 %g  心理咨询 %g" % (
    sum(daily[d]["B"] for d in DAYS), sum(daily[d]["C"] for d in DAYS), sum(daily[d]["D"] for d in DAYS),
    SE, SF, SF / SE * 100, SE - SF, sum(daily[d]["I"] for d in DAYS), sum(daily[d]["H"] for d in DAYS)))
print("在岗护士区间 %d—%d 人/天" % (min(daily[d]["rows"] for d in DAYS), max(daily[d]["rows"] for d in DAYS)))

print()
print("== 逐人 9.20—9.26 物理治疗累计（护士维度）==")
rws = []
for n in order:
    E = sum(per[n].get(d, {}).get("E") or 0 for d in DAYS)
    F = sum(per[n].get(d, {}).get("F") or 0 for d in DAYS)
    days = [d for d in DAYS if per[n].get(d, {}).get("J")]
    edays = [d for d in DAYS if (per[n].get(d, {}).get("E") or 0) > 0]
    rws.append((n, E, F, len(days), len(edays)))
for n, E, F, nd, ne in sorted(rws, key=lambda x: (-(x[1] and x[2] / x[1] or -1))):
    rate = ("%.1f%%" % (F / E * 100)) if E else "不适用"
    print("  %-5s 应做 %4g  实做 %4g  %8s  在岗 %d 天  有应做 %d 天" % (n, E, F, rate, nd, ne))
print("有应完成量人数 =", sum(1 for x in rws if x[1] > 0), "/ 名册", len(rws))

print()
print("== 单日应做峰值（按人）==")
pk = []
for n in order:
    for d in DAYS:
        e = per[n].get(d, {}).get("E") or 0
        if e:
            pk.append((e, n, d))
for e, n, d in sorted(pk, reverse=True)[:10]:
    print("  %s  %-5s 应做 %g" % (d, n, e))

print()
print("== 逐日最大缺口（应做-实做）==")
for d in DAYS:
    worst = []
    for n in order:
        r = per[n].get(d, {})
        e = r.get("E") or 0; f = r.get("F") or 0
        if e:
            worst.append((f - e, n, e, f))
    worst.sort()
    s = " ".join("%s %g/%g(差%g)" % (n, f, e, f - e) for df, n, e, f in worst[:3])
    print("  %s  %s" % (d, s))

print()
print("== 周排名表 ==")
wb = openpyxl.load_workbook(os.path.join(D, "护士工作量及工作质量分析排名(9.20-9.26)(1).xlsx"), data_only=True)
ws = wb["综合排名"]
print("综合排名:")
for r in range(2, ws.max_row + 1):
    v = [cell(ws, r, c) for c in range(1, 12)]
    print("  %2s %-5s 综合 %-5s 工作量第%-3s 合计 %-6s 日均 %-5s 出勤 %-2s 质量第%-3s 合计 %-6s 日均 %-5s 考核 %s" % tuple(
        ("" if x is None else x) for x in v))
ws2 = wb["物理治疗汇总"]
print("物理治疗汇总（项目口径）:")
for r in range(2, ws2.max_row + 1):
    print("  ", [cell(ws2, r, c) for c in range(1, 5)])
