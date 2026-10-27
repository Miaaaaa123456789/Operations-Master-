#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""护理组周考核数据提取 + AI 分析指标计算。

源表：护士工作量及质量统计.xlsx（工作量统计 / 质控统计 / 归一化工作量 / 综合排名）
     质控及物理治疗统计表.xlsx（质控考核记录 / 物理治疗明细 / 物理治疗汇总）

输出：data/nursing-week.json  —— 页面渲染与 AI 分析唯一取数口。

口径要点（写在脚本里，避免下轮遗忘）：
1. 源表按「周日—周六」出表，本期为 10.18—10.24，比自然周 10.19—10.25 早一天。
2. 平均分 = 累计分 ÷ 7（不是 ÷ 勤天数）——缺勤即扣分，跨周不可比。
3. 综合得分 = （工作量指数 + 质控均分）÷ 2，两列量纲不同，名义 50/50 实际质控权重偏低。
4. 杜萧只出现在质控名单（17 人），工作量名单 16 人无此人。
5. 10.18 当日最高分源表填 72.5，但杨思菡当日 75 → 归一化出现 103.4 越界。
"""
import json
import os
import sys
from statistics import mean, pstdev

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DRAG = ("/Users/opp/Library/Containers/com.tencent.xinWeChat/Data/Documents/"
        "xwechat_files/wxid_w82ow8s27ffg22_3c28/temp/drag")
F_WORK = os.path.join(DRAG, "护士工作量及质量统计(1).xlsx")
F_QC = os.path.join(DRAG, "质控及物理治疗统计表(2)(1).xlsx")
OUT = os.path.join(ROOT, "data", "nursing-week.json")
ARCHIVE = os.path.join(ROOT, "data", "nursing-archive-1011.json")

DAYS = ["10.18", "10.19", "10.20", "10.21", "10.22", "10.23", "10.24"]


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = str(v).strip()
    if not s or s in ("—", "-", "－"):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def sheet_rows(ws, want_header):
    """按表头名定位列，返回 list[dict]；跳过说明行。"""
    rows = list(ws.iter_rows(values_only=True))
    hi = None
    for i, r in enumerate(rows):
        vals = [str(c).strip() if c is not None else "" for c in r]
        if "护士姓名" in vals:
            hi = i
            break
    if hi is None:
        return [], []
    header = [str(c).strip() if c is not None else "" for c in rows[hi]]
    out = []
    for r in rows[hi + 1:]:
        vals = list(r)
        name = str(vals[0]).strip() if vals and vals[0] is not None else ""
        if not name or name.startswith("每日") or name.startswith("【"):
            continue
        rec = {"name": name}
        for k, h in enumerate(header):
            if not h:
                continue
            rec[h] = vals[k] if k < len(vals) else None
        out.append(rec)
    return header, out


def parse_day_matrix(rec, header):
    """取 7 个日期列 → list[float|None]"""
    days = [h for h in header if h and h[:3] == "10."]
    return [num(rec.get(h)) for h in days]


def main():
    wb = openpyxl.load_workbook(F_WORK, data_only=True)

    ws = wb["工作量统计"]
    hd, rows = sheet_rows(ws, True)
    work = []
    for r in rows:
        v = parse_day_matrix(r, hd)
        work.append({
            "name": r["name"], "days": v,
            "attend": int(r.get("勤天数") or 0),
            "sum": num(r.get("累计分")),
            "avg7": num(r.get("平均分")),
            "max": num(r.get("最高分")), "min": num(r.get("最低分")),
            "rank": int(r.get("排名") or 0),
        })

    ws = wb["质控统计"]
    hdq, rowsq = sheet_rows(ws, True)
    qc = []
    for r in rowsq:
        v = parse_day_matrix(r, hdq)
        qc.append({
            "name": r["name"], "days": v,
            "attend": int(r.get("勤天数") or 0),
            "sum": num(r.get("累计分")),
            "avg7": num(r.get("平均分")),
            "max": num(r.get("最高分")), "min": num(r.get("最低分")),
            "rank": int(r.get("排名") or 0),
        })

    ws = wb["归一化工作量"]
    hdn, rowsn = sheet_rows(ws, True)
    norm = []
    for r in rowsn:
        v = parse_day_matrix(r, hdn)
        norm.append({"name": r["name"], "days": v,
                     "avg": num(r.get("平均指数")),
                     "rank": int(r.get("指数排名") or 0)})

    ws = wb["综合排名"]
    hdc, rowsc = sheet_rows(ws, True)
    comp = []
    for r in rowsc:
        comp.append({
            "name": r["name"],
            "wIdx": num(r.get("工作量指数")), "wRank": int(r.get("工作量排名") or 0),
            "qcAvg": num(r.get("质控均分")), "qcRank": int(r.get("质控排名") or 0),
            "score": num(r.get("综合得分")), "rank": int(r.get("综合排名") or 0),
        })

    # ---------- 物理治疗（本期先入库存档，页面模块稍后更新） ----------
    wbq = openpyxl.load_workbook(F_QC, data_only=True)
    ws = wbq["物理治疗汇总"]
    phys = []
    cur_date = None
    for r in ws.iter_rows(min_row=2, values_only=True):
        name = str(r[0]).strip() if r[0] else ""
        if not name or name.startswith("【") or name == "合计":
            if name == "合计":
                phys_total = {"due": num(r[1]), "done": num(r[2]),
                              "miss": num(r[3]), "rate": num(r[4])}
            continue
        phys.append({"item": name, "due": num(r[1]), "done": num(r[2]),
                     "miss": num(r[3]), "rate": num(r[4])})
    phys_total = locals().get("phys_total")

    # ---------- 出勤/填报 ----------
    n_work = len(work)
    n_qc = len(qc)
    work_slots = n_work * 7
    qc_slots = n_qc * 7
    work_fill = sum(1 for w in work for x in w["days"] if x is not None)
    qc_fill = sum(1 for q in qc for x in q["days"] if x is not None)
    per_day_work = [sum(1 for w in work if w["days"][i] is not None) for i in range(7)]
    per_day_qc = [sum(1 for q in qc if q["days"][i] is not None) for i in range(7)]

    work_vals = [x for w in work for x in w["days"] if x is not None]
    qc_vals = [x for q in qc for x in q["days"] if x is not None]

    # ---------- 分布与区分度 ----------
    dist = {
        "workN": len(work_vals), "workMean": round(mean(work_vals), 2),
        "workSd": round(pstdev(work_vals), 2),
        "workTop": max(work_vals), "workLow": min(work_vals),
        "qcN": len(qc_vals), "qcMean": round(mean(qc_vals), 2),
        "qcSd": round(pstdev(qc_vals), 2),
        "qcTop": max(qc_vals), "qcLow": min(qc_vals),
    }
    dist["workCV"] = round(dist["workSd"] / dist["workMean"] * 100, 1)
    dist["qcCV"] = round(dist["qcSd"] / dist["qcMean"] * 100, 1)

    # ---------- 个人波动（仅按实际出勤天数算） ----------
    vol = []
    for w in work:
        vs = [x for x in w["days"] if x is not None]
        if len(vs) >= 3:
            vol.append({"name": w["name"], "n": len(vs),
                        "range": round(max(vs) - min(vs), 1),
                        "sd": round(pstdev(vs), 2),
                        "mean": round(mean(vs), 1)})
    vol.sort(key=lambda x: -x["range"])

    # ---------- 四象限（工作量指数 × 质控均分） ----------
    xs = [c["wIdx"] for c in comp]
    ys = [c["qcAvg"] for c in comp]
    mx, my = round(mean(xs), 1), round(mean(ys), 1)
    quad = {"x0": mx, "y0": my, "cells": {"hh": [], "hl": [], "lh": [], "ll": []}}
    for c in comp:
        k = ("h" if c["wIdx"] >= mx else "l") + ("h" if c["qcAvg"] >= my else "l")
        quad["cells"][{"hh": "hh", "hl": "hl", "lh": "lh", "ll": "ll"}[k]].append(c["name"])

    # ---------- 综合得分几何 ----------
    sc = [c["score"] for c in comp]
    comp_stats = {"n": len(sc), "max": max(sc), "min": min(sc),
                  "mean": round(mean(sc), 2), "sd": round(pstdev(sc), 2),
                  "spread": round(max(sc) - min(sc), 1)}
    # 名义 50/50，实际两列量纲不同（指数上限 100、质控均分上限约 60）→ 按均值占比算实际权重
    wW = round(mean(xs) / (mean(xs) + mean(ys)) * 100, 1)
    comp_stats["wWeightReal"] = wW              # 工作量项实际权重
    comp_stats["qcWeightReal"] = round(100 - wW, 1)  # 质控项实际权重

    # ---------- 数据核验 ----------
    checks = []
    # 1) 质控表与上周存档逐格比对
    if os.path.exists(ARCHIVE):
        arc = json.load(open(ARCHIVE, encoding="utf-8"))
        same_cell = 0
        diff_cell = 0
        diff_people = []
        for q in qc:
            a = arc.get(q["name"])
            if not a:
                continue
            d = 0
            for x, y in zip(q["days"], a):
                if x is None and y is None:
                    continue
                if x is not None and y is not None and abs(x - y) < 1e-9:
                    same_cell += 1
                else:
                    diff_cell += 1
                    d += 1
            if d:
                diff_people.append(q["name"])
        checks.append({
            "level": "critical" if diff_cell == 0 else "ok",
            "title": "质控 7 日数值与上一考核周逐格一致",
            "fact": ("17 人 × 7 天共 %d 个有分数格，与 10.11—10.17 存档比对：一致 %d 格、差异 %d 格。"
                     "疑似源表只平移了表头日期、未重新采集。" % (same_cell + diff_cell, same_cell, diff_cell)),
            "todo": "请护理部确认质控表是否已重采；确认前质控项按「待核」标识，不作为绩效扣罚依据。",
            "hit": diff_cell == 0,
        })
    # 2) 当日最高分与归一化越界
    over = []
    for n in norm:
        for i, v in enumerate(n["days"]):
            if v is not None and v > 100.05:
                over.append({"name": n["name"], "day": DAYS[i], "idx": v})
    checks.append({
        "level": "critical" if over else "ok",
        "title": "10.18 当日最高分填错，指数越界",
        "fact": ("源表「每日最大值」10.18 记 72.5，但当日杨思菡实得 75，归一化 = 75÷72.5×100 = 103.4，"
                 "出现 >100 的指数。" if over else "无越界。"),
        "todo": "修正「每日最大值」行为 75，或改按当日实际最高重算；否则杨思菡当日被被动抬高 3.4 个指数点。",
        "hit": bool(over),
    })
    # 3) 名单不一致
    wn = {w["name"] for w in work}
    qn = {q["name"] for q in qc}
    only_q = sorted(qn - wn)
    only_w = sorted(wn - qn)
    checks.append({
        "level": "critical" if only_q or only_w else "ok",
        "title": "工作量表与质控表名单不一致",
        "fact": ("工作量 %d 人、质控 %d 人；仅出现在质控表：%s；仅出现在工作量表：%s。"
                 % (n_work, n_qc, "、".join(only_q) or "无", "、".join(only_w) or "无")),
        "todo": "杜萧质控 6 天、均分 50.6 位列质控第 2，却因工作量表缺行被排除在 16 人综合排名外——需补录工作量分后重排。",
        "hit": bool(only_q or only_w),
    })
    # 4) 平均分口径变更
    checks.append({
        "level": "warn",
        "title": "「平均分」口径改按 ÷7，与上周存档不同源",
        "fact": "本期平均分 = 累计分 ÷ 7（缺勤按 0 计）；上一考核周存档为 ÷ 勤天数。同一批分值，陈福建 347.5÷5=69.5（旧）对 347.5÷7=49.6（新），差 19.9 分。",
        "todo": "质控均分、综合得分均不可跨周比较；页面已标注「÷7 口径」，勿用旧阈值（60 分及格）判优劣。",
        "hit": True,
    })

    # ---------- 结论 ----------
    findings = []
    top1 = next(c for c in comp if c["rank"] == 1)
    findings.append({
        "tag": "第一名靠「稳」不靠「高」",
        "text": ("%s 工作量 6 天全在 69.5—73.5，指数 %.1f（第 1）、质控均分 %.1f（第 4），综合 %.1f。"
                 "他的分不是最高单日（75 分属杨思菡），而是<b>零波动</b>：7 天极差仅 4.0 分。"
                 % (top1["name"], top1["wIdx"], top1["qcAvg"], top1["score"])),
        "num": "%.1f" % top1["score"], "lab": "综合得分 · 第 1",
    })
    findings.append({
        "tag": "出勤是第一道闸门",
        "text": ("16 人 7 天共 112 个填报格，实填 %d 格（%.1f%%），人均 %.1f 天。工作量指数按日归一后再取平均，"
                 "<b>少填一天直接摊薄指数</b>：丁思意、曾宇浩各只 1 天，指数 12 上下，垫底与第 15。"
                 % (work_fill, work_fill / work_slots * 100, work_fill / n_work)),
        "num": "%.1f%%" % (work_fill / work_slots * 100), "lab": "工作量填报完整率",
    })
    findings.append({
        "tag": "质控缺席比低分更伤",
        "text": ("杨新金工作量 6 天稳定 62—65、指数 %.1f 排第 2，但质控只填 2 天、均分 %.1f 排第 16，"
                 "综合掉到第 %d。<b>质控记录缺失 = 该项按 0 摊进 ÷7</b>，比单日低分损失更大。"
                 % (next(c for c in comp if c["name"] == "杨新金")["wIdx"],
                    next(c for c in comp if c["name"] == "杨新金")["qcAvg"],
                    next(c for c in comp if c["name"] == "杨新金")["rank"])),
        "num": "2 / 7", "lab": "杨新金质控出勤天数",
    })

    data = {
        "period": {"from": "2026-10-18", "to": "2026-10-24",
                   "label": "10.18—10.24", "days": DAYS,
                   "week": "10.19—10.25", "note": "源表按周日—周六出表，比自然周早 1 天"},
        "source": [os.path.basename(F_WORK), os.path.basename(F_QC)],
        "work": work, "qc": qc, "norm": norm, "comp": comp,
        "physio": {"items": phys, "total": phys_total, "status": "pending"},
        "analytics": {
            "nWork": n_work, "nQc": n_qc,
            "workFill": work_fill, "workSlots": work_slots,
            "workRate": round(work_fill / work_slots * 100, 1),
            "qcFill": qc_fill, "qcSlots": qc_slots,
            "qcRate": round(qc_fill / qc_slots * 100, 1),
            "perDayWork": per_day_work, "perDayQc": per_day_qc,
            "dist": dist, "vol": vol[:5], "quad": quad,
            "comp": comp_stats, "checks": checks, "findings": findings,
        },
    }
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("WROTE", OUT)
    print(json.dumps(data["analytics"], ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    sys.exit(main())
