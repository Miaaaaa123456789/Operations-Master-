#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按《患者有效对接表》5 张管家分表逐条重算 data/snapshot.json 的 butler 段。

数据源：data/raw-kdocs/butler_contacts/*.json（2026-10-26T07:28 抓取）
表结构：c1=日期 c2=患者姓名 c3=复查/初诊 c7=住院（√ 或 是 → 转住院）c10=权重
"""
import io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAP = os.path.join(ROOT, "data", "snapshot.json")

# 逐人：对接条数 / 转住院 / 初诊 / 有记录天数 / 权重（业主《心理管家有效客户对接表》10.19-10.25 块）
# ⚠ 排序＝权重降序，权重相同者按有效对接条数降序（业主 2026-10-26 指令「总排名按权重来」）
STAFF = [
    ("金林", 27, 4, 5, 7, 4.0),
    ("朱婧", 22, 4, 2, 5, 4.0),
    ("利娟", 21, 3, 6, 7, 3.0),
    ("国威", 17, 3, 5, 6, 3.0),
]
# 上期 10.12-10.18 业主表权重：菲菲 1.0 / 国威 2.7 / 金林 5.3 / 朱婧 4.0 / 利娟 3.0（合计 16.0）
PREV_WEIGHT = {"菲菲": 1.0, "国威": 2.7, "金林": 5.3, "朱婧": 4.0, "利娟": 3.0}
TOTAL, ADMIT = 87, 14
PREV_TOTAL, PREV_ADMIT = 79, 16
PREV_STAFF = [["利娟", 20], ["金林", 17], ["朱婧", 17], ["国威", 13], ["菲菲", 12]]

DAILY = {"2026-10-19": 4, "2026-10-20": 11, "2026-10-21": 9, "2026-10-22": 9,
         "2026-10-23": 18, "2026-10-24": 5, "2026-10-25": 31}
DAILY_ADMIT = {"2026-10-19": 0, "2026-10-20": 1, "2026-10-21": 3, "2026-10-22": 2,
               "2026-10-23": 4, "2026-10-24": 1, "2026-10-25": 3}

s = json.load(io.open(SNAP, encoding="utf-8"))
b = s["butler"]

b["week"] = {"contact": TOTAL, "admit": ADMIT, "rate": round(ADMIT / TOTAL * 100, 1)}
b["prevSameDays"] = {"contact": PREV_TOTAL, "admit": PREV_ADMIT,
                     "rate": round(PREV_ADMIT / PREV_TOTAL * 100, 1)}
b["staff"] = [[n, c] for n, c, *_ in STAFF]
b["staffPrev"] = PREV_STAFF
b["staffDetail"] = [{"name": n, "contact": c, "admit": a, "first": f, "days": d,
                     "weight": w, "rate": round(a / c * 100, 1)}
                    for n, c, a, f, d, w in STAFF]
b["rankBy"] = "weight"
b["rankNote"] = ("按业主《心理管家有效客户对接表》10.19—10.25 块的「权重」列降序；"
                 "权重相同者按有效对接条数降序。菲菲权重列为空（整周未填报）→ 不进榜、不记 0。"
                 "权重合计 14.0（上期 16.0）。")
b["weightSum"] = 14.0
b["prevWeightSum"] = 16.0
b["prevWeight"] = PREV_WEIGHT
b["missingStaff"] = ["菲菲"]
b["missingNote"] = ("菲菲表最后一行是 2026-10-18；她惯常周日批量补录"
                    "（10.11 周日 2 条、10.18 周日 12 条），本期尚未录入，"
                    "按契约记 null、不按 0 降榜")
b["daily"] = dict(DAILY)
b["dailyAdmit"] = dict(DAILY_ADMIT)
b["kindSplit"] = {"firstVisit": 18, "revisit": 68, "blank": 1}
b["dataThrough"] = "2026-10-25"
b["days"] = 7
b["pulledAt"] = "2026-10-26T07:28:57+08:00"
b["timeStamps"] = {
    "菲菲": "2026-10-18", "国威": "2026-10-25", "金林": "2026-10-25",
    "朱婧": "2026-10-25", "利娟": "2026-10-25",
    "issues": [
        "菲菲表停在 10.18，本期（10.19—10.25）整周未录入",
        "朱婧表第 425、426 行日期误写 2025.10.25（实为 2026.10.25，已按 10.25 计入）",
        "「复查/初诊」列存在 复查/复/初诊/初 四种写法，已归一",
        "分表第 10 列表头写「权重」，但本期只在该列 14 个住院行填 1，实为住院标记、不是考核系数",
    ],
}
b["typoRows"] = [{"staff": "朱婧", "row": 425, "patient": "龚晟", "written": "2025.10.25",
                  "used": "2026-10-25"},
                 {"staff": "朱婧", "row": 426, "patient": "孙正阳", "written": "2025.10.25",
                  "used": "2026-10-25"}]
b["recon"] = {"raw": 87, "dedup": 87, "duplicateSameDay": 0,
              "note": "5 张分表逐条 87 行；同日同患者无多人重复申报，无需去重"}
b["sourceNote"] = ("线上《患者有效对接表》5 张管家分表（菲菲/国威/金林/朱婧/利娟）逐条。"
                   "2026-10-26 07:28 全量重抓；原快照的 32 条 / 7 人 / 21.9% 是「至 10.23、5 天」旧抓取，"
                   "10.24—10.26 间各组把 10.19—10.23 补录了一轮（32→51），再加 10.24—10.25 的 36 条。")

s["watermarks"]["butler"] = {"dataThrough": "2026-10-25", "days": 7,
                             "authority": "butler_contacts",
                             "latestPerStaff": {"菲菲": "2026-10-18", "国威": "2026-10-25",
                                                "金林": "2026-10-25", "朱婧": "2026-10-25",
                                                "利娟": "2026-10-25"},
                             "stale": ["菲菲"]}

s["revision"] = max(int(s.get("revision") or 0) + 1, 32)
s["revisionCreatedAt"] = "2026-10-26T07:40:00+08:00"
s["generatedAt"] = "2026-10-26T07:40:00+08:00"

json.dump(s, io.open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("revision →", s["revision"])
print("butler.week:", b["week"])
print("prevSameDays:", b["prevSameDays"])
print("staff:", [(x["name"], x["weight"], x["contact"]) for x in b["staffDetail"]],
      "| missing:", b["missingStaff"], "| 权重合计", b["weightSum"])
print("daily:", b["daily"])
print("watermark:", s["watermarks"]["butler"]["dataThrough"], s["watermarks"]["butler"]["days"], "天")
