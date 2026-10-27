#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全写入 live-data.sqlite 的小工具。

本机 SQLite 在 db/ 目录下会出现 hot journal（disk I/O error），
所以统一用「db + journal 一起拷到 /tmp 打开（自动回滚）→ 写入 → 拷回」的方式。
"""
import os
import shutil
import sqlite3
import tempfile
import datetime as dt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(REPO, "db", "live-data.sqlite")


def open_copy():
    d = tempfile.mkdtemp(prefix="dbw-")
    dst = os.path.join(d, "x.sqlite")
    shutil.copy(DB, dst)
    j = DB + "-journal"
    if os.path.exists(j):
        shutil.copy(j, dst + "-journal")
    con = sqlite3.connect(dst)
    con.execute("PRAGMA journal_mode=TRUNCATE")
    return con, d, dst


def commit_back(con, d, dst):
    con.commit()
    con.close()
    shutil.copy(dst, DB)
    for suf in ("-journal", "-wal", "-shm"):
        p = DB + suf
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    shutil.rmtree(d, ignore_errors=True)


def put(con, metric_id, date, value, unit="", source_id="revenue_daily_report",
        sheet="SEED", row_ref=None, dim_key="", dim_value=""):
    if value is None:
        return
    con.execute(
        """INSERT INTO fact(metric_id,business_date,dim_key,dim_value,value,unit,
                            source_id,sheet_name,row_ref,status,fetched_at)
           VALUES(?,?,?,?,?,?,?,?,?, 'ok', ?)
           ON CONFLICT(metric_id,business_date,dim_key,dim_value,source_id,sheet_name,row_ref)
           DO UPDATE SET value=excluded.value, unit=excluded.unit, fetched_at=excluded.fetched_at""",
        (metric_id, date, dim_key, dim_value, float(value), unit,
         source_id, sheet, row_ref or date,
         dt.datetime.now().astimezone().replace(microsecond=0).isoformat()),
    )


def set_setting(con, key, value):
    con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
    con.execute("UPDATE settings SET value=? WHERE key=?", (value, key))


if __name__ == "__main__":
    con, d, dst = open_copy()
    print("ok", con.execute("select max(business_date) from fact").fetchone())
    commit_back(con, d, dst)
