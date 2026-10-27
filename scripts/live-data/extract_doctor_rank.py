#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把业主给的《周排名分析_2026-10-19至10-25_更新版.xlsx》抽成 data/doctor-rank.json。

口径（写在表里，这里原样保留，不改写）：
  统计口径：出院结账收入；本周入院按 2026-10-19 00:00:00—10-25 23:59:59 入院时间戳；
            在院人数截至 2026-10-25；心理业绩＝心理咨询费＋心理治疗费。
  排名指数＝可计分 ÷ 65 × 100；医疗质量 20 / 时效 10 / 执行协作 5 暂未计入。

⚠ 这是「出院结账」口径，与营收日报的「逐日进账」口径**不可相加、不可互换**。
   - 出院结账 10.19—10.25 共 231,084.49 元（15 人）
   - 营收日报逐日 10.19—10.23 共 389,811 元（5 天，含门诊）
   两者分母不同，页面分开呈现。

用法：
   python3 scripts/live-data/extract_doctor_rank.py [xlsx 路径]
"""
import json
import os
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "doctor-rank.json")
DEFAULT_SRC = ("/Users/opp/Library/Containers/com.tencent.xinWeChat/Data/Documents/"
               "xwechat_files/wxid_w82ow8s27ffg22_3c28/temp/drag/"
               "周排名分析_2026-10-19至10-25_更新版.xlsx")

FIELDS = ["rank", "name", "revenue", "physio", "psych", "discharge", "bedDays",
          "inWard", "scoreRevenue", "scoreDischarge", "scoreBed", "scoreWard",
          "scoreable", "index", "admit"]
INT_FIELDS = {"rank", "discharge", "inWard", "admit", "doctors"}


def num(v, nd=2):
    if v is None or v == "":
        return 0.0
    v = float(v)
    return round(v, nd) if nd else int(round(v))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    wb = openpyxl.load_workbook(src, data_only=True)
    ws = wb["周排名"]
    grid = [[c for c in r] for r in ws.iter_rows(values_only=True)]

    # 标题 / 口径行
    title = str(grid[1][0] or "").strip()
    caliber = str(grid[2][0] or "").strip()

    # 汇总行（「出院人数 | 在院人数 | 个人总业绩合计 …」下一行）
    totals = {}
    for i, row in enumerate(grid[:12]):
        if row[0] == "出院人数":
            vals = grid[i + 1]
            keys = ["discharge", "inWard", "revenue", "physio", "psych", "doctors", "admit"]
            for k, v in zip(keys, vals):
                totals[k] = int(round(float(v))) if k in INT_FIELDS else num(v)
            break

    # 明细行：表头以「排名」开头的那一行之后
    rows, start = [], None
    for i, row in enumerate(grid):
        if row[0] == "排名" and row[1] == "医生":
            start = i + 1
            break
    if start is None:
        raise SystemExit("找不到「排名 | 医生」表头")
    for row in grid[start:]:
        if not row[1]:
            break
        rec = {}
        for k, v in zip(FIELDS, row):
            rec[k] = (int(round(float(v))) if k in INT_FIELDS
                      else str(v).strip() if k == "name" else num(v))
        rec["name"] = str(row[1]).strip()
        rows.append(rec)

    # 校验：人数、业绩合计、出院/在院/入院合计
    err = []
    if len(rows) != int(totals.get("doctors", -1)):
        err.append(f"医生数 {len(rows)} ≠ 表头 {totals.get('doctors')}")
    if abs(sum(r["discharge"] for r in rows) - totals["discharge"]) > 1e-9:
        err.append(f"出院合计 {sum(r['discharge'] for r in rows)} ≠ {totals['discharge']}")
    if abs(sum(r["inWard"] for r in rows) - totals["inWard"]) > 1e-9:
        err.append(f"在管合计 {sum(r['inWard'] for r in rows)} ≠ {totals['inWard']}")
    if abs(sum(r["admit"] for r in rows) - totals["admit"]) > 1e-9:
        err.append(f"入院合计 {sum(r['admit'] for r in rows)} ≠ {totals['admit']}")
    if abs(sum(r["revenue"] for r in rows) - totals["revenue"]) > 0.05:
        err.append(f"业绩合计 {sum(r['revenue'] for r in rows)} ≠ {totals['revenue']}")
    if abs(sum(r["physio"] for r in rows) - totals["physio"]) > 0.05:
        err.append(f"物理治疗合计 {sum(r['physio'] for r in rows)} ≠ {totals['physio']}")
    if abs(sum(r["psych"] for r in rows) - totals["psych"]) > 0.05:
        err.append(f"心理业绩合计 {sum(r['psych'] for r in rows)} ≠ {totals['psych']}")

    # 校验：排名指数 = 可计分 / 65 × 100
    for r in rows:
        calc = round(r["scoreable"] / 65 * 100, 2)
        if abs(calc - r["index"]) > 0.05:
            err.append(f"{r['name']} 排名指数 {r['index']} ≠ {calc}")

    # 明细页：出院 / 在院（做人次与姓名可追溯，姓名已脱敏，只留医生维度）
    out = {
        "period": {"start": "2026-10-19", "end": "2026-10-25", "label": "10.19—10.25"},
        "title": title,
        "caliber": caliber,
        "source": os.path.basename(src),
        "totals": totals,
        "rows": rows,
        "checks": {"ok": not err, "errors": err},
        "notes": [
            "出院结账口径，与营收日报的逐日进账口径不可相加、不可互换",
            "本周入院人数单列展示、暂不计分",
            "医疗质量 20 分、时效 10 分、执行协作 5 分暂未计入，本表为可量化工作量排名",
        ],
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"→ {OUT}")
    print(f"   {title} · {len(rows)} 名医生 · 出院 {totals['discharge']} · 在院 {totals['inWard']} · "
          f"业绩 {totals['revenue']:,.2f} 元")
    print("   校验：" + ("全部通过" if not err else "；".join(err)))
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
