#!/usr/bin/env python3
"""把采集到的工作表打印成对齐文本，便于人工核对。用法: show.py <path> [maxRows] [maxCols]"""
import json, sys, os

path = sys.argv[1]
maxr = int(sys.argv[2]) if len(sys.argv) > 2 else 40
maxc = int(sys.argv[3]) if len(sys.argv) > 3 else 16
if not os.path.isabs(path):
    path = os.path.join("data", "raw-kdocs", path)
d = json.load(open(path))
rows = d["rows"]
print(f"### {d['source']}/{d['sheetName']}  rows={len(rows)} cols={max(len(r) for r in rows) if rows else 0}  pulled={d.get('pulledAt')}")
for i, r in enumerate(rows[:maxr]):
    cells = [str(v).replace("\n", "\\n")[:22] for v in r[:maxc]]
    if not any(cells):
        continue
    print(f"{i:>3} | " + " | ".join(cells))
