#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 H：index.html 收尾（营收待补标注 + 团体治疗参加人数本周化）"""
import io

PATH = 'index.html'
s = io.open(PATH, encoding='utf-8').read()
fails = []


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n == 0:
        fails.append('%s 未找到' % tag)
        print('  ✗ %-32s 未找到' % tag)
        return
    if n != expect:
        fails.append('%s 实际 %d 期望 %d' % (tag, n, expect))
    s = s.replace(old, new)
    print('  ✓ %-32s %3d 处' % (tag, n))


print('── H1. 营收 hero 卡：标注 9.23—9.24 待补 ──')
rep('营收日报口径本周（9.21—9.22，2 天）10.86 万</small>',
    '营收日报口径本周（9.21—9.22，2 天）10.86 万 · <b>9.23—9.24 日报待补</b></small>',
    'H1 营收待补')

print()
print('── H2. 团体治疗参加人数 → 本周口径 ──')
rep("['团体治疗参加人数（9.14—9.20）',null,6,'人','同源：上周 3 场合计 6 人（1/2/3）；"
    "上上周 4 场合计 16 人（含 9.12 家长减压团体 15 人，家长类与患者团体不同性质）']",
    "['本周团体治疗参加人数（9.21—9.24）',null,1,'人','同源：本周 2 场，9.21 团体 1 人；"
    "9.24 家长课堂参加人数源表未填（<b>待补</b>）。上周（9.14—9.20）3 场 6 人；"
    "上上周（9.7—9.13）4 场 16 人（含 9.12 家长减压团体 15 人，家长类与患者团体不同性质）']",
    'H2 团体参加人数', 2)

io.open(PATH, 'w', encoding='utf-8').write(s)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
for k, v in [('9.23—9.24 日报待补', chk.count('9.23—9.24 日报待补')),
             ('本周团体治疗参加人数', chk.count('本周团体治疗参加人数')),
             ('残留 团体治疗参加人数（9.14', chk.count('团体治疗参加人数（9.14'))]:
    print('  %-28s %d' % (k, v))
    if '残留' in k and v:
        fails.append(k)

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
