#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取主表长文本（叙述列），判断是否已滚到第 4 周"""
import json
import subprocess

CLI = '/Users/opp/.local/bin/kdocs-cli'
URL_MAIN = 'https://www.kdocs.cn/l/cbwp2cvTiFyK'


def cells(sid, rf, rt, cf, co):
    r = subprocess.run([CLI, 'call', 'sheet.get_range_data', json.dumps({
        'url': URL_MAIN, 'worksheet_id': sid,
        'range': {'rowFrom': rf, 'rowTo': rt, 'colFrom': cf, 'colTo': co}},
        ensure_ascii=False)], capture_output=True, text=True)
    out = r.stdout or ''
    i = out.find('{')
    if i < 0:
        return []
    d = json.JSONDecoder().raw_decode(out[i:])[0]
    rd = ((d.get('data') or {}).get('detail') or {}).get('rangeData') or []
    return [(c.get('originRow'), c.get('originCol'), (c.get('cellText') or '').strip())
            for c in rd if (c.get('cellText') or '').strip()]


print('█' * 74)
print('  医生组：叙述列全量（找第 4 周线索）')
print('█' * 74)
for r, c, t in cells(3, 0, 20, 5, 12):
    print('\n── r%d c%d ──' % (r + 1, c))
    print(t[:1400])

print('\n\n' + '█' * 74)
print('  护理组：叙述列全量')
print('█' * 74)
for r, c, t in cells(4, 0, 20, 4, 12):
    if len(t) < 30:
        continue
    print('\n── r%d c%d ──' % (r + 1, c))
    print(t[:1600])
