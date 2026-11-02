#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正 snapshot.psych 的 staffWeek / weekSum / rank 与本周（10.26—11.01）不同期的问题。

背景：patch_psych_1026.py 当时把 `week` 与本文件里的 staffWeek 一起写成 10.19—10.25 的值；
换周到 10.26 后只更新了 week / rank / staff，staffWeek 与 weekSum 还留着上一周，
导致同一份快照里「组级 36 人次」与「逐人合计 65 人次」并存。

本脚本按「咨询师每日简报」逐条重算 2026-10-26—2026-11-01 的逐人值，并写回：
  咨询 = 住院 + 门诊 + 家庭；接触 = 24h首次 + 情绪 + 住院
另记录三条年份误录（2027-10-27 / 2027-10-28 / 2027-10-30，应为 2026）——
这三条本身有业务量（李凌钰住院 2），按本期归集，但在 dataQuality 里留痕。
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAP = os.path.join(ROOT, "data", "snapshot.json")

# 逐条重算结果（来源 data/raw-kdocs/psych_v4/11-咨询师每日简报.json，
# 窗口 2026-10-26—2026-11-01，含 3 条年份误录为 2027 的行）
STAFF = [
    # 姓名, 填报天, 首接, 情绪, 住院, 门诊, 家庭, 家长, 团体参与
    ("蔡宜蓉", 5, 2, 11, 5, 9, 0, 8, 12),
    ("赵芳", 3, 3, 1, 2, 2, 0, 3, 0),
    ("冯浩鹏", 3, 0, 7, 1, 2, 0, 9, 0),
    ("李凌钰", 2, 0, 0, 2, 0, 0, 0, 0),
    ("史允之", 2, 0, 0, 0, 0, 0, 0, 0),
    ("苏欣然", 1, 0, 1, 1, 0, 0, 0, 0),
    ("王沛然", 1, 0, 0, 0, 0, 0, 0, 0),
    ("陈鹏", 0, 0, 0, 0, 0, 0, 0, 0),
]

DATA_QUALITY = {
    "yearTypo": [
        {"date": "2027-10-27", "name": "王沛然", "intended": "2026-10-27", "values": "全空"},
        {"date": "2027-10-28", "name": "李凌钰", "intended": "2026-10-28", "values": "住院咨询 2"},
        {"date": "2027-10-30", "name": "李凌钰", "intended": "2026-10-30", "values": "全空"},
    ],
    "note": ("简报末尾 3 行的年份误录为 2027（王沛然 10.27、李凌钰 10.28 与 10.30），"
             "按内容与相邻行判定属本期；其中李凌钰 10.28 住院咨询 2 人次已计入本周，"
             "否则本周住院咨询会少 2、咨询合计由 24 变 22。另有 2 行只有日期、无姓名无内容，不计入。"),
}

s = json.load(io.open(SNAP, encoding="utf-8"))
p = s["psych"]

staff_week = []
for name, days, first, emo, inp, outp, fam, par, grp in STAFF:
    staff_week.append({
        "name": name, "report_days": days, "ward_days": None,
        "first": first, "emotion": emo, "inpatient": inp, "outpatient": outp,
        "family": fam, "parent": par, "group_attend": grp,
        "consult": inp + outp + fam, "contact": first + emo + inp,
        "rate": None,
    })

week_sum = {
    "report_days": sum(x[1] for x in STAFF),
    "first": sum(x[2] for x in STAFF),
    "emotion": sum(x[3] for x in STAFF),
    "inpatient": sum(x[4] for x in STAFF),
    "outpatient": sum(x[5] for x in STAFF),
    "family": sum(x[6] for x in STAFF),
    "parent": sum(x[7] for x in STAFF),
    "group_attend": sum(x[8] for x in STAFF),
}
week_sum["consult"] = week_sum["inpatient"] + week_sum["outpatient"] + week_sum["family"]
week_sum["contact"] = week_sum["first"] + week_sum["emotion"] + week_sum["inpatient"]

# 与组级 week 断言互校：任何一处不等就停，避免又写进一份自相矛盾的快照
w = p["week"]
checks = {
    "report": (week_sum["report_days"], w["report"]),
    "first": (week_sum["first"], w["first"]),
    "emotion": (week_sum["emotion"], w["emotion"]),
    "inpatient": (week_sum["inpatient"], w["inpatient"]),
    "outpatient": (week_sum["outpatient"], w["outpatient"]),
    "family": (week_sum["family"], w["family"]),
    "parent": (week_sum["parent"], w["parent"]),
    "consult": (week_sum["consult"], w["consult"]),
    "contact": (week_sum["contact"], w["contact"]),
    "groupPeople": (week_sum["group_attend"], w["groupPeople"]),
}
bad = {k: v for k, v in checks.items() if v[0] != v[1]}
if bad:
    raise SystemExit(f"✗ 逐人合计与组级 week 不一致，已中止：{bad}")

p["staffWeek"] = staff_week
p["weekSum"] = week_sum
p["dataQuality"] = DATA_QUALITY
p["dataThrough"] = "2026-11-01"
p["days"] = 7
p["pulledAt"] = "2026-11-01T23:54:00+08:00"

# rank 保留（已由管线按本周重算），仅补 parent 字段便于页面拆解
rank_parent = {x[0]: x[7] for x in STAFF}
for r in p.get("rank", []):
    r["parent"] = rank_parent.get(r["name"])

s["revision"] = int(s.get("revision") or 0) + 1
s["revisionCreatedAt"] = "2026-11-02T01:10:00+08:00"
s["generatedAt"] = "2026-11-02T01:10:00+08:00"

json.dump(s, io.open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("revision →", s["revision"])
print("weekSum:", json.dumps(week_sum, ensure_ascii=False))
print("逐人:", [(x["name"], x["consult"], x["contact"], x["report_days"]) for x in staff_week])
