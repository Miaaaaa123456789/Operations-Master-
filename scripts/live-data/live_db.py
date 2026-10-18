#!/usr/bin/env python3
"""SQLite 连接助手。

本机沙箱下 WAL / DELETE 日志模式会报 `disk I/O error`
（无法对已打开的 journal 做 unlink、也不支持共享内存锁），
统一用 TRUNCATE 模式；若上次异常退出残留 journal，先清掉再连。
"""
import os, sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "db", "live-data.sqlite")


def connect(path=DB, schema=True):
    journal = path + "-journal"
    if os.path.exists(journal) and os.path.getsize(journal) > 0:
        # 残留事务日志：先尝试热日志恢复，失败则移除
        try:
            c = sqlite3.connect(path)
            c.execute("PRAGMA journal_mode=TRUNCATE")
            c.execute("PRAGMA integrity_check").fetchone()
            c.close()
        except sqlite3.Error:
            os.unlink(journal)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=TRUNCATE")
    c.execute("PRAGMA foreign_keys=ON")
    if schema:
        c.executescript(open(os.path.join(ROOT, "db", "schema.sql"), encoding="utf-8").read())
        c.execute("PRAGMA journal_mode=TRUNCATE")
    return c
