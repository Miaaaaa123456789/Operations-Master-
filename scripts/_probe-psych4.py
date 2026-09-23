#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计咨询登记 sheet 的 9 月咨询条目：按周、按咨询师。"""
import json
import subprocess
import collections
import re

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

day_of_col = {}
for col, val in grid.get(2, {}).items():
    m = re.match(r'(\d+)\.(\d+)', val)
    if m:
        day_of_col[col] = int(m.group(2))
print('日期列映射（列→日）:', sorted(day_of_col.items()))
print()

ENTRY = re.compile(r'[（(]\s*(首|门|住|[0-9])\s*[，,]')
week_of = {}
for col, day in day_of_col.items():
    if 14 <= day <= 20:
        week_of[col] = 'W3(9.14-9.20)'
    elif 21 <= day <= 27:
        week_of[col] = 'W4(9.21-9.27)'
    elif 7 <= day <= 13:
        week_of[col] = 'W2(9.7-9.13)'

by_week = collections.Counter()
by_week_staff = collections.defaultdict(collections.Counter)
for row, cells in grid.items():
    if row < 3:
        continue
    staff = (cells.get(0) or '').strip()
    for col, val in cells.items():
        if col not in week_of:
            continue
        n = len(ENTRY.findall(val))
        if n == 0:
            n = val.count('\n') + 1 if ('门' in val or '住' in val or '首' in val) else 0
        if n:
            by_week[week_of[col]] += n
            by_week_staff[week_of[col]][staff] += n

print('═══ 咨询条目（按周）═══')
for k in ['W2(9.7-9.13)', 'W3(9.14-9.20)', 'W4(9.21-9.27)']:
    print('  %-16s %d 条' % (k, by_week[k]))
print()
print('═══ W3(9.14—9.20) 按咨询师 ═══')
for name, n in by_week_staff['W3(9.14-9.20)'].most_common():
    print('   %-6s %d' % (name, n))
print('   合计 %d' % sum(by_week_staff['W3(9.14-9.20)'].values()))
print()
print('═══ W4(9.21—9.27) 按咨询师 ═══')
for name, n in by_week_staff['W4(9.21-9.27)'].most_common():
    print('   %-6s %d' % (name, n))
print('   合计 %d' % sum(by_week_staff['W4(9.21-9.27)'].values()))
