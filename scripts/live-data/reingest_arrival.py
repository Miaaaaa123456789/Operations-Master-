#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只重算《10月到院登记表》的事实（arrival.visit / arrival.new），幂等。

为什么单独做：
  09:14:22 这次抓取把 10.24 / 10.25 补齐了，但 fact 表里**上一周（10.12–10.18）**
  还是更早一版抓取的结果 —— 实测 10.18 少 3 行（fact 91 行 / 源表现有 94 行），
  于是「上期 210」既不是源表行数也不是人日数。
  这里把该来源的事实整段删掉、用 ingest.py 同一个 ingest_sheet() 重放，
  保证本期与上一期出自**同一次抓取、同一套去重规则**（行键 = 日期+姓名+电话）。

用法：
  python3 scripts/live-data/reingest_arrival.py            # 重算并打印核对
  python3 scripts/live-data/reingest_arrival.py --dry-run  # 只看不写
"""
import importlib.util
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ING = os.path.join(ROOT, "scripts", "live-data", "ingest.py")
RAW = os.path.join(ROOT, "data", "raw-kdocs", "arrival_register")
DB = os.path.join(ROOT, "db", "live-data.sqlite")

spec = importlib.util.spec_from_file_location("ingest_mod", ING)
ing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ing)


def main():
    dry = "--dry-run" in sys.argv
    f = [x for x in sorted(os.listdir(RAW)) if x.endswith(".json")][0]
    d = json.load(open(os.path.join(RAW, f), encoding="utf-8"))
    rows, pulled = d["rows"], d.get("pulledAt", "")

    c = sqlite3.connect(DB)
    before = c.execute(
        "SELECT COUNT(*) FROM fact WHERE source_id='arrival_register'").fetchone()[0]

    if not dry:
        c.execute("DELETE FROM fact WHERE source_id='arrival_register'")
        ing.ingest_sheet(c, "arrival_register", d.get("sheetName") or "工作表1", rows, pulled)
        c.execute("UPDATE source SET last_pull_at=?, data_through=? WHERE id='arrival_register'",
                  (pulled, c.execute(
                      "SELECT MAX(business_date) FROM fact WHERE source_id='arrival_register'"
                  ).fetchone()[0]))
        c.commit()

    print(f"原始 rows={len(rows)} · pulledAt={pulled}")
    print(f"fact 行数：{before} → {c.execute('SELECT COUNT(*) FROM fact WHERE source_id=\"arrival_register\"').fetchone()[0]}")

    for label, a, b in (("本期 10.19–10.25", "2026-10-19", "2026-10-25"),
                        ("上期 10.12–10.18", "2026-10-12", "2026-10-18")):
        tot = c.execute("SELECT COUNT(*) FROM fact WHERE metric_id='arrival.visit' AND business_date BETWEEN ? AND ?", (a, b)).fetchone()[0]
        new = c.execute("SELECT COUNT(*) FROM fact WHERE metric_id='arrival.new' AND business_date BETWEEN ? AND ?", (a, b)).fetchone()[0]
        print(f"  {label}: 到院人日 {tot} · 初诊 {new}")
    print("  逐日:", dict(c.execute(
        "SELECT business_date, COUNT(*) FROM fact WHERE metric_id='arrival.visit' "
        "AND business_date BETWEEN '2026-10-12' AND '2026-10-25' GROUP BY 1").fetchall()))
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
