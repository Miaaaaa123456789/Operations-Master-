#!/usr/bin/env python3
"""把营收日报逐日台账（data-import.js 的 SEED）导入事实库。

SEED 列义：[门诊收入, 在院收入, 初诊, 复诊, 在院, 入院, 出院]
营收是「经核验的日事实」，因此与在线表分开存：source_id = revenue_daily_report。
"""
import os, re, sqlite3, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_db
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "db", "live-data.sqlite")
SRC = os.path.join(ROOT, "data-import.js")
CN = timezone(timedelta(hours=8))

COLS = [
    ("revenue.outpatient", "门诊收入", "元", 0),
    ("revenue.inpatient", "在院收入", "元", 1),
    ("visit.new", "初诊", "人次", 2),
    ("visit.return", "复诊", "人次", 3),
    ("ward.count", "在院人数", "人", 4),
    ("admit", "入院", "人", 5),
    ("discharge", "出院", "人", 6),
]


def main():
    src = open(SRC, encoding="utf-8").read()
    m = re.search(r"var SEED = \{(.*?)\n  \};", src, re.S)
    if not m:
        raise SystemExit("未找到 SEED")
    body = m.group(1)
    rows = re.findall(r"'(\d{4}-\d{2}-\d{2})':\s*\[([^\]]+)\]", body)
    c = live_db.connect(DB)
    c.execute("INSERT OR IGNORE INTO source(id,name,url,grain,note) VALUES(?,?,?,?,?)",
              ("revenue_daily_report", "营收日报（逐日台账）", "院方营收日报截图 / 核验后录入",
               "daily_revenue_fact", "门诊+在院=当日合计；经勾稽核验后入库"))
    for mid, label, unit, _ in COLS:
        c.execute("INSERT OR IGNORE INTO metric_def(id,label,unit,grain,source_id,formula) VALUES(?,?,?,?,?,?)",
                  (mid, label, unit, "day", "revenue_daily_report", "营收日报逐列"))
    now = datetime.now(CN).isoformat(timespec="seconds")
    n = 0
    for date, vals in rows:
        parts = [x.strip() for x in vals.split(",")]
        for mid, label, unit, idx in COLS:
            if idx >= len(parts) or parts[idx] in ("", "null", "undefined"):
                continue
            v = float(parts[idx])
            # dim_key/dim_value 用空串而非 NULL：SQLite 的 UNIQUE 视 NULL 互不相等，会导致重复插入
            c.execute("""INSERT OR REPLACE INTO fact(metric_id,business_date,dim_key,dim_value,value,unit,source_id,sheet_name,row_ref,status,fetched_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                      (mid, date, "", "", v, unit, "revenue_daily_report", "SEED", date, "ok", now))
            n += 1
    # 源数据截至
    last = max(r[0] for r in rows)
    c.execute("UPDATE source SET last_pull_at=?, data_through=? WHERE id=?", (now, last, "revenue_daily_report"))
    c.commit()
    print(f"SEED 逐日 {len(rows)} 天 → 写入 {n} 条事实；截至 {last}")
    for mid, label, unit, _ in COLS:
        r = c.execute("SELECT COUNT(*),SUM(value) FROM fact WHERE metric_id=?", (mid,)).fetchone()
        print(f"  {label}: {r[0]} 天, 合计 {r[1]:,.2f} {unit}")


if __name__ == "__main__":
    main()
