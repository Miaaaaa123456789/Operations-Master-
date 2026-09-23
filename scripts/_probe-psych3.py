#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查看咨询登记 sheet 的表头结构与 9 月覆盖范围。"""
import json
import subprocess
import collections

CLI = '/Users/opp/.local/bin/kdocs-cli'
FID = 'z6x6JbCFfxMDK32s7KRyrxLXkT3MBZ1cp'


def call(tool, params):
    out = subprocess.run([CLI, 'call', tool, json.dumps(params, ensure_ascii=False)],
                         capture_output=True, text=True).stdout
    return json.JSONDecoder().raw_decode(out.lstrip())[0]


r = call('sheet.get_range_data', {'file_id': FID, 'worksheet_id': 1,
                                  'range': {'rowFrom': 0, 'rowTo': 130, 'colFrom': 0, 'colTo': 34}})
rd = r.get('data', {}).get('detail', {}).get('rangeData', [])
grid = collections.defaultdict(dict)
for c in rd:
    t = (c.get('cellText') or '').strip()
    if t:
        grid[c['originRow']][c['originCol']] = t

print('非空行数 %d，最大列 %d' % (len(grid), max((max(v) for v in grid.values()), default=-1) + 1))
print()
print('── 前 4 行（表头）──')
for rw in sorted(grid)[:4]:
    cells = grid[rw]
    print('r%-3d (%d 格): %s' % (rw, len(cells),
                              ' | '.join('c%d=%s' % (k, v[:18]) for k, v in sorted(cells.items())[:16])))
print()
tally = collections.Counter()
for rw, cells in grid.items():
    for v in cells.values():
        if '门' in v or '住' in v or '首' in v:
            tally[rw] += 1
print('── 含「门/住/首」的咨询条目按行统计（前 20）──')
for rw, n in sorted(tally.items())[:20]:
    print('   r%-3d %d 条 | 首格: %s' % (rw, n, (grid[rw].get(0) or list(grid[rw].values())[0])[:30]))
print()
print('总条目行 %d，含咨询条目合计 %d' % (len(tally), sum(tally.values())))
