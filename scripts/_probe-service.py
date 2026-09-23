#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计算客服/导诊三张表在 W3(9.14—9.20) 的分人明细。"""
import json
import collections

D = 'data/extra/'


def in_week(value):
    return '2026-09-14' <= str(value)[:10] <= '2026-09-20'


callback = json.load(open(D + 'service-callback.json', encoding='utf-8'))
workload = json.load(open(D + 'service-workload.json', encoding='utf-8'))
visitlog = json.load(open(D + 'service-visitlog.json', encoding='utf-8'))

print('workload 字段:', list(workload[0].keys()))
print()

rows = [r for r in callback if in_week(r.get('date'))]
print('【回访 W3】共 %d 条' % len(rows))
cnt = collections.Counter()
arrived = collections.Counter()
score_cnt = collections.Counter()
for r in rows:
    cnt[r['staff']] += 1
    if r.get('arrived') == '是':
        arrived[r['staff']] += 1
    score_cnt[r.get('score')] += 1
for name, n in cnt.most_common():
    print('   %-6s %2d 条 · 到院 %2d · %.1f%%' % (name, n, arrived[name], arrived[name] / n * 100))
print('   到院合计 %d | 满意度分布 %s' % (sum(arrived.values()), dict(score_cnt)))
print()

rows = [r for r in visitlog if in_week(r.get('date'))]
print('【主动服务 W3】共 %d 条' % len(rows))
for name, n in collections.Counter(r['staff'] for r in rows).most_common():
    print('   %-6s %d' % (name, n))
print()

rows = [r for r in workload if in_week(r.get('date'))]
print('【日工作量 W3】共 %d 人日' % len(rows))
agg = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0])
for r in rows:
    a = agg[r['staff']]
    a[0] += 1
    a[1] += r.get('dutyScore') or 0
    a[2] += r.get('extraScore') or 0
    a[3] += r.get('valueScore') or 0
total = 0.0
for name in sorted(agg, key=lambda z: -sum(agg[z][1:])):
    days, duty, extra, value = agg[name]
    print('   %-6s 在岗%d天 履职%.0f 附加%.0f 增值%.0f 合计%.0f'
          % (name, days, duty, extra, value, duty + extra + value))
    total += duty + extra + value
print('   总分合计 %.1f' % total)
