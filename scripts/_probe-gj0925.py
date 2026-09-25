#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管家有效对接表：本周至今精确核算 + 数据质量检查"""
import json
import re
import subprocess
from collections import Counter, defaultdict

CLI = '/Users/opp/.local/bin/kdocs-cli'
URL = 'https://www.kdocs.cn/l/ctlu8ktnEwi8'
GJ = {1: '菲菲', 2: '国威', 3: '金林', 4: '朱婧', 6: '利娟'}
YES = {'是', '√', '1', 'Y', 'y', '✓', 'v'}
CUR = ('2026-09-21', '2026-09-25')
FULL = ('2026-09-14', '2026-09-20')


def cells(sid, rf, rt):
    r = subprocess.run([CLI, 'call', 'sheet.get_range_data', json.dumps({
        'url': URL, 'worksheet_id': sid,
        'range': {'rowFrom': rf, 'rowTo': rt, 'colFrom': 0, 'colTo': 12}},
        ensure_ascii=False)], capture_output=True, text=True)
    out = r.stdout or ''
    i = out.find('{')
    if i < 0:
        return []
    d = json.JSONDecoder().raw_decode(out[i:])[0]
    rd = ((d.get('data') or {}).get('detail') or {}).get('rangeData') or []
    return [(c.get('originRow'), c.get('originCol'), (c.get('cellText') or '').strip())
            for c in rd if (c.get('cellText') or '').strip()]


print('█' * 72)
print('  管家表：表头 + 异常日期检查')
print('█' * 72)
alldata = {}
for sid, nm in GJ.items():
    g = {}
    for r, c, t in cells(sid, 0, 400):
        g.setdefault(r, {})[c] = t
    alldata[nm] = g
    # 表头
    print('\n── %s（%d 行有内容）' % (nm, len(g)))
    for r in sorted(g)[:3]:
        print('    r%-2d %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:190]))
    # 日期异常
    bad = []
    for r in sorted(g):
        ds = str(g[r].get(1, '')).strip()
        m = re.match(r'^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$', ds)
        if m:
            y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if not (2026 == y and 1 <= mo <= 9 and 1 <= dd <= 30):
                bad.append((r + 1, ds))
    if bad:
        print('    ⚠ 异常日期 %d 处：' % len(bad), bad[:8])

print('\n\n' + '█' * 72)
print('  本周至今 9.21—9.25 与 上周完整周 9.14—9.20')
print('█' * 72)


def agg(nm, lo, hi, rows=None):
    g = alldata[nm]
    c = Counter()
    for r in sorted(g):
        row = g[r]
        if str(row.get(0, '')).strip() == '序号':
            continue
        ds = str(row.get(1, '')).strip()
        m = re.match(r'^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$', ds)
        if m:
            y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1900 <= y <= 2100 and 1 <= mo <= 12:
                g_cur = '%04d-%02d-%02d' % (y, mo, dd)
            else:
                g_cur = getattr(agg, 'last_%s' % nm, None)
        else:
            g_cur = getattr(agg, 'last_%s' % nm, None)
        setattr(agg, 'last_%s' % nm, g_cur)
        if not (g_cur and lo <= g_cur <= hi):
            continue
        if not any(str(row.get(cc, '')).strip() for cc in (2, 3, 4, 5, 6, 7)):
            continue
        c['对接'] += 1
        if str(row.get(4, '')).strip() in YES:
            c['检查'] += 1
        if str(row.get(5, '')).strip() in YES:
            c['物理'] += 1
        if str(row.get(6, '')).strip():
            c['心理'] += 1
        if str(row.get(7, '')).strip() in YES:
            c['住院'] += 1
    return c


for lab, (lo, hi) in [('本周至今 9.21—9.25', CUR), ('上周完整周 9.14—9.20', FULL)]:
    print('\n══ %s' % lab)
    print('  %-6s %6s %6s %6s %6s %6s' % ('管家', '对接', '检查', '物理', '心理', '住院'))
    T = Counter()
    for sid, nm in GJ.items():
        c = agg(nm, lo, hi)
        T.update(c)
        print('  %-6s %6d %6d %6d %6d %6d' % (nm, c['对接'], c['检查'], c['物理'], c['心理'], c['住院']))
    print('  %-6s %6d %6d %6d %6d %6d' % ('合计', T['对接'], T['检查'], T['物理'], T['心理'], T['住院']))
    if T['对接']:
        print('  → 转住院率 %d/%d = %.1f%%' % (T['住院'], T['对接'], T['住院'] / T['对接'] * 100))

# 上周同期 3 天
print('\n══ 上周同期 9.14—9.16（3 天，对齐营收周期）')
T = Counter()
for sid, nm in GJ.items():
    c = agg(nm, '2026-09-14', '2026-09-16')
    T.update(c)
print('  合计 对接 %d / 检查 %d / 物理 %d / 心理 %d / 住院 %d' %
      (T['对接'], T['检查'], T['物理'], T['心理'], T['住院']))
if T['对接']:
    print('  → 转住院率 %.1f%%' % (T['住院'] / T['对接'] * 100))
