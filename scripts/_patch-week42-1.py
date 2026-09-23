#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 1：顶层时间接口推进到本周 9.21—9.27，并把周标签整体顺延一位"""
import io

PATH = 'index.html'
SRC = io.open(PATH, encoding='utf-8').read()

fails = []


def rep(old, new, tag, expect=None):
    global SRC
    n = SRC.count(old)
    if n == 0:
        fails.append('%s | 未找到 | %s' % (tag, old[:70]))
        return
    if expect is not None and n != expect:
        fails.append('%s | 实际 %d / 期望 %d | %s' % (tag, n, expect, old[:70]))
    SRC = SRC.replace(old, new)
    print('  %-38s %3d 处' % (tag, n))


print('── A. 顶层时间接口 ──')
# A1 主口径 chip
rep('<span class="range-chip" id="rangeChip" title="本页主口径：本周 9.14—9.20"><i>▦</i>9月14日—9月20日（本周）</span>',
    '<span class="range-chip" id="rangeChip" title="本页主口径：本周 9.21—9.27（进行中 · 数据截至 9.22）"><i>▦</i>9月21日—9月27日（本周）</span>',
    'A1 rangeChip', 1)

# A2 数据更新至（按钮）
rep('id="periodBtn">数据更新至 2026年9月21日<', 'id="periodBtn">数据更新至 2026年9月22日<',
    'A2 periodBtn', 1)

# A3 JS 兜底 periodLabel（2 处同串）
rep("window.OPS_SNAPSHOT.periodLabel)||'数据更新至 2026年9月19日'",
    "window.OPS_SNAPSHOT.periodLabel)||'数据更新至 2026年9月22日'",
    'A3 JS 兜底 periodLabel', 2)

# A4 快照 periodLabel / snapshotAt
rep("periodLabel:'数据更新至 2026年9月21日'", "periodLabel:'数据更新至 2026年9月22日'",
    'A4 快照 periodLabel', 1)
rep("snapshotAt:'2026-09-21T07:10:00+08:00'", "snapshotAt:'2026-09-24T02:20:00+08:00'",
    'A5 快照 snapshotAt', 1)

print()
print('── B. 周标签顺延（9.14—9.20 → 上周；9.7—9.13 → 上上周）──')
rep('本周（9.14—9.20', '上周（9.14—9.20', 'B1 本周（9.14—9.20…）', 47)
rep('本周 9.14—9.20', '上周 9.14—9.20', 'B2 本周 9.14—9.20…', 18)  # rangeChip 那处已被 A1 消费
rep('上周（9.7—9.13', '上上周（9.7—9.13', 'B3 上周（9.7—9.13…）', 15)
rep('上周 9.7—9.13', '上上周 9.7—9.13', 'B4 上周 9.7—9.13', None)

out = SRC
io.open(PATH, 'w', encoding='utf-8').write(out)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
checks = [
    ('本周 9.21—9.27', chk.count('本周 9.21—9.27')),
    ('9月21日—9月27日（本周）', chk.count('9月21日—9月27日（本周）')),
    ('数据更新至 2026年9月22日', chk.count('数据更新至 2026年9月22日')),
    ('残留 数据更新至 2026年9月21日', chk.count('数据更新至 2026年9月21日')),
    ('残留 数据更新至 2026年9月19日', chk.count('数据更新至 2026年9月19日')),
    ('残留 本周（9.14—9.20）', chk.count('本周（9.14—9.20')),
    ('残留 本周 9.14—9.20', chk.count('本周 9.14—9.20')),
    ('新 上周（9.14—9.20）', chk.count('上周（9.14—9.20')),
    ('新 上上周（9.7—9.13）', chk.count('上上周（9.7—9.13')),
    ('残留 上周（9.7—9.13）', chk.count('上周（9.7—9.13') - chk.count('上上周（9.7—9.13')),
]
for k, v in checks:
    print('  %-32s %d' % (k, v))
bad = [k for k, v in checks if '残留' in k and v != 0]
if bad:
    fails.append('回读残留：%s' % bad)

print()
print('写入完成，%d bytes' % len(out))
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
