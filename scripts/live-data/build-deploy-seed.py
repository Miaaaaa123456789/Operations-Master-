#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成本地全量库的「脱敏部署种子」db/deploy-seed.sqlite。

为什么要单独一份，而不是直接把 db/live-data.sqlite 传上去
------------------------------------------------------------
线上是公网可访问的目录。`live-data.sqlite` 里有 `pull.rows_json` ——
各张金山表的**原始行**，含患者/客户姓名与 11 位手机号（实测命中）。
把它传上去，等于把院内受控数据放到了互联网上，只是暂时没人知道路径。

所以上云的那一份：
  · 清空 pull（原始层只留本地，它本来就不可变、不需要在线上被读）
  · revision 只保留最新一条（历史快照是本地审计用的，线上不需要）
  · fact / source / metric_def / settings 全留 —— 快照重算与导入都依赖它们
  · VACUUM 压体积
  · 写完后**再扫一遍手机号**，有命中就直接失败，不生成文件

用法：
  python3 scripts/live-data/build-deploy-seed.py
"""
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "db", "live-data.sqlite")
OUT = os.path.join(ROOT, "db", "deploy-seed.sqlite")
PHONE = re.compile(r"1[3-9]\d{9}")


def build():
    if not os.path.exists(SRC):
        sys.exit("找不到源库：%s" % SRC)
    # ⚠ 两个坑，都实测过：
    #   ① conn.backup() 在本机沙箱报 disk I/O error（与 WAL 同源的锁限制）→ 整文件字节复制；
    #   ② 直接在 db/ 目录里开库做删改也会报 disk I/O error（journal 建不进去）→
    #      **先在 /tmp 里把库改好，最后整文件写回 db/**，全程不在 db/ 里开 SQLite 连接。
    tmp = os.path.join("/tmp", "ops-deploy-seed.sqlite")
    for p in (tmp, tmp + "-journal"):
        if os.path.exists(p):
            os.unlink(p)
    with open(SRC, "rb") as f:
        blob = f.read()
    with open(tmp, "wb") as f:
        f.write(blob)
    dst = sqlite3.connect(tmp)
    dst.execute("PRAGMA journal_mode=TRUNCATE")

    # ① 原始层不上云
    pull_rows = dst.execute("SELECT COUNT(*) FROM pull").fetchone()[0]
    dst.execute("DELETE FROM pull")

    # ② 历史 revision 只留最新（线上只需要「当前这一版」）
    rev_keep = dst.execute("SELECT MAX(revision) FROM revision").fetchone()[0]
    dropped_rev = 0
    if rev_keep is not None:
        dropped_rev = dst.execute("SELECT COUNT(*) FROM revision WHERE revision<?",
                                  (rev_keep,)).fetchone()[0]
        dst.execute("DELETE FROM revision WHERE revision<?", (rev_keep,))

    dst.commit()
    dst.execute("VACUUM")
    dst.commit()

    # ④ 自检：不留手机号；保留核心表数据
    # ⚠ 不能把 fact.row_ref 当内容扫：它是自然键哈希（k + 16 位十六进制），
    #   里面经常出现「连续 11 位数字且以 1[3-9] 开头」的片段 —— 实测 7 处全是假阳性
    #   （如 kd647f17971148967）。对 row_ref 只校验「它确实是哈希」，不校验内容。
    hits = []
    for tbl, col in (("fact", "dim_value"), ("fact", "sheet_name"),
                     ("source", "note")):
        for (v,) in dst.execute("SELECT %s FROM %s" % (col, tbl)):
            if v and PHONE.search(str(v)):
                hits.append("%s.%s" % (tbl, col))
    # ⚠ 2026-10-26 修：revision.snapshot_json 里的 `_fp` 是 sha256 指纹（64 位十六进制），
    #   必然出现「1[3-9] 开头的连续 11 位数字」片段 —— 与 fact.row_ref 同源的假阳性
    #   （实测 rev30 的 _fp 里就藏着 18469942836，把整轮发布卡住）。
    #   改法：先把 _fp 摘掉，只对正文扫手机号。
    for (v,) in dst.execute("SELECT snapshot_json FROM revision"):
        if not v:
            continue
        try:
            obj = json.loads(v)
            obj.pop("_fp", None)
            body = json.dumps(obj, ensure_ascii=False)
        except Exception:
            body = str(v)
        if PHONE.search(body):
            hits.append("revision.snapshot_json")
    # row_ref 只有两种合法形态：自然键哈希 k+16hex，或营收 seed 用的日期。
    bad_ref = 0
    for (v,) in dst.execute("SELECT row_ref FROM fact WHERE row_ref IS NOT NULL"):
        s = str(v)
        if not (re.match(r"^k[0-9a-f]{16}$", s) or re.match(r"^\d{4}-\d{2}-\d{2}$", s)):
            bad_ref += 1
    fact_n = dst.execute("SELECT COUNT(*) FROM fact").fetchone()[0]
    dst.close()

    if hits:
        os.unlink(tmp)
        sys.exit("⛔ 脱敏失败：%s 仍有手机号，已放弃生成" % "、".join(sorted(set(hits))))
    if bad_ref:
        os.unlink(tmp)
        sys.exit("⛔ fact.row_ref 有 %d 处不是规范哈希，脱敏中止" % bad_ref)

    # 从 /tmp 整文件写回（不在 db/ 里开 SQLite，见上方 ②）
    with open(tmp, "rb") as f:
        final = f.read()
    with open(OUT, "wb") as f:
        f.write(final)
    for p in (tmp, tmp + "-journal"):
        if os.path.exists(p):
            os.unlink(p)
    size = os.path.getsize(OUT)
    print("已生成 %s" % os.path.relpath(OUT, ROOT))
    print("  清空 pull %d 行 · 删除历史 revision %d 条 · fact 保留 %d 行" % (pull_rows, dropped_rev, fact_n))
    print("  体积 %.2f MB · 手机号扫描 0 命中" % (size / 1048576))


if __name__ == "__main__":
    build()
