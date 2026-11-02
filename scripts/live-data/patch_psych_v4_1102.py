#!/usr/bin/env python3
"""2026-11-02：把快照的心理组块对齐到 V4 管理表「日报」逐条（与 build_snapshot 同源）。

为什么单独写脚本而不整跑 build_snapshot：
  build 会重建**整份**快照，而医生组「出院结账」块（departments.doctorWeek）是本项目
  另行注入的，build 里没有生成逻辑 → 整跑会把医生组 13 项费用、逐人业绩全部冲掉。
  所以这里只取 build 干跑结果里的 `psych` 块，其余键原样保留。

本轮修掉的两处静默失真：
  1) `周个人统计` 的周窗口由组长在表内手填，实测仍是 2026-10-19—10-25（未滚动）。
     旧 build 把「最新一期周表值」当本周值，导致 recon 变成「本周日报 vs 上周周表」，
     gap 全是周期差（首次 −4 / 情绪 −11 / 住院 −14）。
  2) `rank[].rate` 实为上周周表的日报完整率（蔡 60% / 赵 0% / 冯 0%），挂在本周排名上属错期。

保留字段（build 不生成）：header（汇报表心理表头停在 9.21，已置 null + headerStale）、
  dataQuality、dataThrough、days、pulledAt、rank[].parent。
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "live-data"))
import build_snapshot

SNAP = os.path.join(ROOT, "data", "snapshot.json")

old = json.load(open(SNAP, encoding="utf-8"))
old_psy = old["psych"]

# 干跑：write=False 不落盘、不占 revision
fresh = build_snapshot.main(write=False)["psych"]

# 1) 汇报表表头：源表停在 2026-09-21，属旧值 → 保留旧快照的 null + stale 标记
for k in ("header", "headerStale", "headerAsOf"):
    if k in old_psy:
        fresh[k] = old_psy[k]

# 2) build 不产出的元信息
for k in ("dataQuality", "dataThrough", "days", "pulledAt"):
    if k in old_psy:
        fresh[k] = old_psy[k]

# 3) rank 补 parent（页面口径要用，build 未生成）；staffWeek 补 consult/contact
par = {x["name"]: x.get("parent") for x in old_psy.get("rank", [])}
for x in fresh["rank"]:
    if x["name"] in par:
        x["parent"] = par[x["name"]]
for x in fresh["staffWeek"]:
    v = lambda k: x.get(k) or 0
    x["consult"] = v("inpatient") + v("outpatient") + v("family")
    x["contact"] = v("first") + v("emotion") + v("inpatient")

# 4) 自洽断言
w, ws = fresh["week"], fresh["weekSum"]
assert w["contact"] == w["first"] + w["emotion"] + w["inpatient"], "接触 ≠ 首次＋情绪＋住院"
assert w["consult"] == w["inpatient"] + w["outpatient"] + w["family"], "咨询 ≠ 住院＋门诊＋家庭"
assert ws["report_days"] == w["report"], "周合计填报天数 ≠ week.report"
assert all(x["gap"] == 0 for x in fresh["recon"]), "同窗对账出现非零 gap，先查源表"

old["psych"] = fresh
json.dump(old, open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("周表窗口", fresh["weekTable"]["start"], "—", fresh["weekTable"]["end"],
      "aligned =", fresh["weekTable"]["aligned"])
print("本周 report", w["report"], "接触", w["contact"], "咨询", w["consult"],
      "家长", w["parent"], "团体", w["groupSessions"], "场", w["groupPeople"], "人")
print("上期 接触", fresh["prevSameDays"]["contact"], "咨询", fresh["prevSameDays"]["consult"])
print("同窗对账", [(x["label"], x["daily"], x["weekly"], x["gap"]) for x in fresh["recon"]])
print("逐人", [(x["name"], x["report_days"], x["consult"], x["contact"]) for x in fresh["staffWeek"]])
