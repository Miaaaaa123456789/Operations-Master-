#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 V4「咨询师每日简报」逐条重算 data/snapshot.json 的 psych 段。

原快照的 psych.staffWeek / weekSum 来自「周个人统计」，该表「周起始日」仍停在
2026-09-01、缓存值合计 21 天，与本期简报 17 条对不上 → 本次全部改为简报逐条重算，
并把 recon（逐条 vs 周表 的对账）置空 + 记录原因，不再拿一张没滚动的表当分母。
"""
import io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAP = os.path.join(ROOT, "data", "snapshot.json")

CUR = {"report": 17, "first": 9, "emotion": 31, "inpatient": 25, "outpatient": 11,
       "family": 3, "parent": 24, "groupSessions": 2, "groupPeople": 11, "bind": 8,
       "contact": 65, "consult": 39}
PREV = {"report": 24, "first": 10, "emotion": 49, "inpatient": 25, "outpatient": 19,
        "family": 2, "parent": 37, "groupSessions": 3, "groupPeople": 17, "bind": 18,
        "contact": 84, "consult": 46}

# 每人：填报天 / 查房天 / 首接 / 情绪 / 住院 / 门诊 / 家庭 / 家长 / 团体参与
STAFF = [
    ("蔡宜蓉", 5, 4, 4, 14, 11, 3, 1, 7, 11),
    ("冯浩鹏", 4, 4, 0, 9, 9, 4, 2, 13, 0),
    ("赵芳", 3, 3, 1, 3, 2, 1, 0, 1, 0),
    ("陈鹏", 2, 0, 0, 5, 2, 1, 0, 3, 0),
    ("王沛然", 2, 1, 3, 0, 0, 2, 0, 0, 0),
    ("史允之", 1, 1, 1, 0, 1, 0, 0, 0, 0),
    ("苏欣然", 0, 0, 0, 0, 0, 0, 0, 0, 0),
    ("李凌钰", 0, 0, 0, 0, 0, 0, 0, 0, 0),
]
DAILY = {"2026-10-19": 3, "2026-10-20": 1, "2026-10-21": 3, "2026-10-22": 3,
         "2026-10-23": 3, "2026-10-24": 2, "2026-10-25": 2}
BOUND = {"rows": 8, "people": 8, "byStaff": [
    {"name": "蔡宜蓉", "rows": 4, "people": 4},
    {"name": "赵芳", "rows": 1, "people": 1},
    {"name": "苏欣然", "rows": 1, "people": 1},
    {"name": "冯浩鹏", "rows": 1, "people": 1},
    {"name": "史允之", "rows": 1, "people": 1},
]}

RATE_NOTE = ("「周个人统计」周起始日仍为 2026-09-01、未滚动（缓存 21 天 vs 本期 17 条），"
             "日报完整率无可用来源，按缺项记 null，不拿旧值顶替")

s = json.load(io.open(SNAP, encoding="utf-8"))
p = s["psych"]

p["week"] = dict(CUR)
p["prevSameDays"] = dict(PREV)

rank = []
for name, days, wd, first, emo, inp, outp, fam, par, gp in STAFF:
    consult = inp + outp + fam
    contact = first + emo + inp
    rank.append({"name": name, "consult": consult, "contact": contact,
                 "inpatient": inp, "outpatient": outp, "family": fam,
                 "emotion": emo, "first": first, "parent": par,
                 "reportDays": days,
                 "score": 2 * consult + contact, "rate": None})
rank = [r for r in rank if r["score"] > 0]   # 本周 0 条的（苏欣然、李凌钰）不进榜、不记 0
rank.sort(key=lambda x: (-x["score"], -x["consult"], x["name"]))
p["rank"] = rank

p["staff"] = [[n, d] for n, d, *_ in sorted(STAFF, key=lambda x: (-x[1], x[0])) if d > 0]
p["staffWeek"] = [{"name": n, "report_days": d, "ward_days": wd, "first": f,
                   "emotion": e, "inpatient": i, "outpatient": o, "family": fa,
                   "parent": pa, "group_attend": g, "rate": None} for n, d, wd, f, e, i, o, fa, pa, g in STAFF]
p["weekSum"] = {"report_days": sum(x[1] for x in STAFF), "ward_days": sum(x[2] for x in STAFF),
                "first": sum(x[3] for x in STAFF), "emotion": sum(x[4] for x in STAFF),
                "inpatient": sum(x[5] for x in STAFF), "outpatient": sum(x[6] for x in STAFF),
                "family": sum(x[7] for x in STAFF), "parent": sum(x[8] for x in STAFF),
                "group_attend": sum(x[9] for x in STAFF)}
p["recon"] = []
p["reconNote"] = ("原表为「日报逐条 vs 周个人统计」对账；周个人统计周起始日停在 2026-09-01 且未重算，"
                  "分母不可用，本次停止对账。本期一切数字取「咨询师每日简报」逐条 17 条，"
                  "已与「日报原始数据」17 键 × 8 字段逐一比对、零差异。")
p["rateNote"] = RATE_NOTE
p["daily"] = dict(DAILY)
p["boundWeek"] = BOUND
p["boundPatients"] = 41
p["boundNote"] = "按「有患者名且未填出院日期」计：冯浩鹏 13、蔡宜蓉 9、王沛然 7、陈鹏 4、苏欣然 4、赵芳 3、史允之 1"
p["dataThrough"] = "2026-10-25"
p["days"] = 7
p["pulledAt"] = "2026-10-26T07:01:34+08:00"
p["timeStamps"] = {
    "dailyReport": "2026-10-25", "rawData": "2026-10-25", "groupTherapy": "2026-10-23",
    "wardRound": "2026-10-24", "leaderDaily": "2026-10-24", "weeklyStats": "2026-09-01",
    "schedule": "2026-11-11",
    "issues": ["团队查房日报缺 10.19—10.21 与 10.25", "组长日管理查看日期停在 10/24",
               "周个人统计周起始日仍为 2026-09-01，未滚动", "新-排班已排至 11 月"],
}

d = s["departments"]["psychology"]
d.update({"consult": 39, "contact": 65, "parent": 24, "groupSessions": 2, "groupPeople": 11,
          "reportDays": 17, "bindRows": 8, "bindPeople": 8, "boundPatients": 41,
          "individual": 39, "people": 65,
          "prevConsult": 46, "prevContact": 84, "prevParent": 37})
d["dataThrough"] = "2026-10-25"
d["headerNote"] = ("汇报表心理组表头自 2026-09-21 抓取值起未滚动（40 人 / 4 场 / 19,002 元），"
                   "与本周 V4 不一致，已停用为本周口径")

s["watermarks"]["psych"] = {"dataThrough": "2026-10-25", "days": 7, "authority": "psych_v4_daily"}
s["revision"] = int(s.get("revision") or 0) + 1
s["revisionCreatedAt"] = "2026-10-26T07:15:00+08:00"
s["generatedAt"] = "2026-10-26T07:15:00+08:00"

json.dump(s, io.open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("revision →", s["revision"])
print("week:", p["week"])
print("weekSum:", p["weekSum"])
print("rank:", [(r["name"], r["score"]) for r in p["rank"]])
print("boundPatients:", p["boundPatients"])
