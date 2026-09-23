#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探查心理文档中未被脚本接入的 4 个 sheet，找最近的记录。"""
import json
import subprocess
import re
import collections

CLI = '/Users/opp/.local/bin/kdocs-cli'
FID = 'z6x6JbCFfxMDK32s7KRyrxLXkT3MBZ1cp'
TARGETS = [(1, '咨询登记', 117), (11, '工娱活动记录', 131),
           (21, 'VIP患者对接情况', 1), (23, '住院患者对接情况', 33)]


def call(tool, params):
    out = subprocess.run([CLI, 'call', tool, json.dumps(params, ensure_ascii=False)],
                         capture_output=True, text=True).stdout
    return json.JSONDecoder().raw_decode(out.lstrip())[0]


def rows_of(sid, r1, c1=20):
    r = call('sheet.get_range_data', {'file_id': FID, 'worksheet_id': sid,
                                      'range': {'rowFrom': 0, 'rowTo': r1, 'colFrom': 0, 'colTo': c1}})
    rd = r.get('data', {}).get('detail', {}).get('rangeData', [])
    grid = collections.defaultdict(dict)
    for c in rd:
        t = (c.get('cellText') or '').strip()
        if t:
            grid[c['originRow']][c['originCol']] = t
    return grid


DATE = re.compile(r'(\d{4})?[-./]?\s*(\d{1,2})\s*[-./月]\s*(\d{1,2})')
MONTHS = collections.Counter()

for sid, name, r1 in TARGETS:
    grid = rows_of(sid, r1)
    print('═══ %s (id=%s) 非空行 %d ═══' % (name, sid, len(grid)))
    for r in sorted(grid)[:2]:
        line = ' | '.join('%s' % v for _, v in sorted(grid[r].items()))
        print('   r%-3d %s' % (r, line[:150]))
    months = collections.Counter()
    for r, cells in grid.items():
        for v in cells.values():
            for m in re.finditer(r'(\d{1,2})\s*[月./-]\s*(\d{1,2})', v):
                months['%02d' % int(m.group(1))] += 1
    print('   月份分布:', dict(sorted(months.items())))
    print('   末 3 行:')
    for r in sorted(grid)[-3:]:
        line = ' | '.join('%s' % v for _, v in sorted(grid[r].items()))
        print('     r%-3d %s' % (r, line[:150]))
    print()
