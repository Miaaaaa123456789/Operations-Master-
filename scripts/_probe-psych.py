#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""心理在线表：实时抓取 vs 已存档 逐项比对。"""
import json
import subprocess
import hashlib

CLI = '/Users/opp/.local/bin/kdocs-cli'
FID_PSY = 'z6x6JbCFfxMDK32s7KRyrxLXkT3MBZ1cp'
SHEETS = [(19, '新-排班'), (3, '课程排班'), (5, '团体治疗登记')]


def call(tool, params):
    out = subprocess.run([CLI, 'call', tool, json.dumps(params, ensure_ascii=False)],
                         capture_output=True, text=True).stdout
    return json.JSONDecoder().raw_decode(out.lstrip())[0]


def live_cells(sid, r1, c1):
    r = call('sheet.get_range_data', {'file_id': FID_PSY, 'worksheet_id': sid,
                                      'range': {'rowFrom': 0, 'rowTo': r1, 'colFrom': 0, 'colTo': c1}})
    rd = r.get('data', {}).get('detail', {}).get('rangeData', [])
    return sorted((c.get('originRow'), c.get('originCol'), (c.get('cellText') or '').strip())
                  for c in rd if (c.get('cellText') or '').strip())


print('═══ 实时抓取 ═══')
live = {}
for sid, name in SHEETS:
    cells = live_cells(sid, 200, 21)
    live[name] = cells
    h = hashlib.sha256(json.dumps(cells, ensure_ascii=False).encode()).hexdigest()[:12]
    print('  %-12s 非空格 %-5d sha=%s' % (name, len(cells), h))

print()
print('═══ 与存档比对 ═══')
for fn, key in [('psych-schedule.json', 'schedule'), ('psych-group.json', 'group'),
                ('psych-course.json', 'course')]:
    try:
        d = json.load(open('data/extra/' + fn, encoding='utf-8'))
    except FileNotFoundError:
        print('  %-22s 文件不存在' % fn)
        continue
    if isinstance(d, dict):
        keys = list(d.keys())
        recs = None
        for k in ('records', 'rows', 'items', 'data'):
            if isinstance(d.get(k), list):
                recs = d[k]
                break
        print('  %-22s 顶层键 %s | 记录数 %s | fetchedAt %s'
              % (fn, keys[:6], len(recs) if recs is not None else '?', d.get('fetchedAt')))
    else:
        print('  %-22s list len=%d' % (fn, len(d)))

print()
print('═══ 团体治疗登记 9 月记录（实时）═══')
for r, c, t in live['团体治疗登记']:
    if t.startswith('09-') or '09-' in t[:6]:
        print('   r%-3d c%-2d %s' % (r, c, t[:80]))
