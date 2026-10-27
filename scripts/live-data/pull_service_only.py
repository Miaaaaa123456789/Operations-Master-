#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只重抓「客服服务部」4 张表（不动其他 5 份源），用于核对时间戳与逐条数据。

复用 collect.py 的读取逻辑，避免口径分叉：
  source = service_followups  fileId = qRzhvsBzrxMY7DuYWNPQrxuTUqMUNHPcJ
  sheet 2 标准化回访台账 / 3 客户投诉处理登记表 / 4 导诊主动服务记录表 / 7 日工作量考核表
"""
import importlib.util
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "collect_mod", os.path.join(ROOT, "scripts", "live-data", "collect.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

SRC = "service_followups"
FID, CAP, SHEETS = C.PLAN[SRC]
OUT = os.path.join(C.OUT, SRC)


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    try:
        m = C.unwrap(C.cli("sheet", "get-sheets-info", json.dumps({"file_id": FID})))
        meta = {s["sheetId"]: s for s in ((m.get("detail") or {}).get("sheetsInfo") or [])}
        print("表元信息：", ", ".join("%s=%s" % (s.get("sheetId"), s.get("name")) for s in meta.values()))
    except Exception as e:
        print("⚠ 表元信息失败：", str(e)[:150])

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for sid, name in SHEETS:
        info = meta.get(sid) or {}
        row_end = min(info.get("rowTo", 400), 1200)
        t0 = time.time()
        rows = C.read_sheet(FID, sid, CAP, row_end)
        path = os.path.join(OUT, "%d-%s.json" % (sid, C.safe(name)))
        with open(path, "w") as f:
            json.dump({"source": SRC, "fileId": FID, "sheetId": sid, "sheetName": name,
                       "rows": rows, "pulledAt": stamp}, f, ensure_ascii=False)
        filled = sum(1 for row in rows for v in row if v)
        print("  ✓ %-16s %d 行 × %d 列，非空 %d，声明行数上限 %s（%.1fs）"
              % (name, len(rows), len(rows[0]) if rows else 0, filled,
                 info.get("rowTo", "?"), time.time() - t0), flush=True)
    print("\npulledAt =", stamp)


if __name__ == "__main__":
    main()
