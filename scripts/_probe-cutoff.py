#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""各数据源逐日覆盖 → 确定统一「本周至今」截止日"""
import json
import os
import re
from collections import Counter

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(f):
    d = json.load(open('data/extra/%s.json' % f, encoding='utf-8'))
    return d if isinstance(d, list) else (d.get('records') or d.get('rows') or [])


print('█' * 70)
print('  各源逐日覆盖（仅 9.20 起）')
print('█' * 70)
days = {}
for f, nm, key in [('service-callback', '客服·回访', 'date'),
                   ('service-visitlog', '客服·主动服务', 'date'),
                   ('service-workload', '客服·日工作量', 'date')]:
    r = load(f)
    c = Counter(str(x.get(key))[:10] for x in r)
    days[nm] = c
    print('  %-16s %s' % (nm, {k: v for k, v in sorted(c.items()) if k >= '2026-09-20'}))

print()
print('█' * 70)
print('  心理/管家/团体 —— 来自前几步的结论')
print('█' * 70)
print('  心理·每日简报   ', {'09-21': 3, '09-22': 1, '09-23': 3, '09-24': 2})
print('  团体治疗登记     09-21=1场 / 09-24=1场（家长课堂）')
print('  管家·有效对接    ', {'09-21': 2, '09-22': 6, '09-23': 3, '09-24': 17, '09-25': 13})

print()
print('█' * 70)
print('  结论：9.24 是全部 5 个源都有数据的最后一天；9.25 仅管家有（13 条）')
print('█' * 70)

print()
print('█' * 70)
print('  统一口径：本周至今 = 9.21—9.24（4 天）')
print('█' * 70)
CUR = ('2026-09-21', '2026-09-24')
PREV = ('2026-09-14', '2026-09-17')   # 上周同期 4 天


def cb(a, b):
    s = [r for r in load('service-callback') if a <= str(r.get('date'))[:10] <= b]
    ar = sum(1 for r in s if r.get('arrived') == '是')
    return s, len(s), ar


for lab, (a, b) in [('本周 9.21—9.24（4 天）', CUR), ('上周同期 9.14—9.17（4 天）', PREV)]:
    s, n, ar = cb(a, b)
    print('\n  %s' % lab)
    print('    回访 %d 条 · 到院 %d（%.1f%%）' % (n, ar, ar / n * 100 if n else 0))
    per = Counter(r['staff'] for r in s)
    arr = Counter(r['staff'] for r in s if r.get('arrived') == '是')
    print('    分人：' + ' / '.join('%s %d（到院 %d = %.0f%%）' % (k, v, arr[k], arr[k] / v * 100)
                                  for k, v in per.most_common()))
    print('    满意度：', dict(Counter(r.get('score') for r in s)))
    sv = [r for r in load('service-visitlog') if a <= str(r.get('date'))[:10] <= b]
    sw = [r for r in load('service-workload') if a <= str(r.get('date'))[:10] <= b]
    tot = sum((r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0) for r in sw)
    print('    主动服务 %d 条 · 日工作量 %d 人日 %.0f 分' % (len(sv), len(sw), tot))
    agg = Counter()
    for r in sw:
        agg[r['staff']] += round((r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0))
    print('    日工作量分人：', dict(agg.most_common()))

print()
print('█' * 70)
print('  周合计（本周 9.21—9.24 vs 上周同期 9.14—9.17）变化')
print('█' * 70)
for lab, (a, b) in [('本周', CUR), ('上周同期', PREV)]:
    s, n, ar = cb(a, b)
    sv = len([r for r in load('service-visitlog') if a <= str(r.get('date'))[:10] <= b])
    sw = [r for r in load('service-workload') if a <= str(r.get('date'))[:10] <= b]
    tot = sum((r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0) for r in sw)
    print('  %-8s 回访 %2d · 到院 %2d · 主动服务 %2d · 工作量 %2d 人日 %.0f 分'
          % (lab, n, ar, sv, len(sw), tot))
