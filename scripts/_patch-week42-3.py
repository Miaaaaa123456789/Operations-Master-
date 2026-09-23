#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 3：全页周标签整体顺延一位
   本周(9.14—9.20) → 上周(9.14—9.20) ；原 上周(9.7—9.13) → 上上周(9.7—9.13)
   用哨兵隔离，避免连锁误替换。
"""
import io
import re

PATH = 'index.html'
SRC = io.open(PATH, encoding='utf-8').read()
fails = []


def rep(old, new, tag, expect=None):
    global SRC
    n = SRC.count(old)
    if n == 0:
        fails.append('%s | 未找到 | %s' % (tag, old[:80]))
        return
    if expect is not None and n != expect:
        fails.append('%s | 实际 %d / 期望 %d | %s' % (tag, n, expect, old[:60]))
    SRC = SRC.replace(old, new)
    print('  %-40s %3d 处' % (tag, n))


print('── A. 定制改写（先做，避免被通用替换波及）──')
rep('<span class="ov-chip">本周 9.13—9.19 <i>⌄</i></span>',
    '<span class="ov-chip">9.13—9.19 <i>⌄</i></span>', 'A1 营收目标卡 chip', 1)
rep('治疗与门诊 9.13—9.19；入出院 9.14—9.20（业主 2026-09-21 更正',
    '治疗与门诊 上周 9.13—9.19；入出院 上周 9.14—9.20（业主 2026-09-21 更正',
    'A2 统计口径行', 1)
rep('心理组与管家组按上周（9.14—9.20）归集（管理表 V4 / 患者对接表）；'
    '<b>本周（9.21—9.27）自 9.21 起重新累计，当日日报尚未产生，本页排名与环比均以上周（9.14—9.20）为准</b>',
    '心理组与管家组按上周（9.14—9.20）归集（管理表 V4 / 患者对接表）；'
    '<b>本周（9.21—9.27）自 9.21 起重新累计、数据截至 9.22（营收 / 客服 / 心理 / 管家已并入本周至今值）；'
    '主表尚未滚动，故排名与深度环比仍以上周（9.14—9.20）完整周为准</b>',
    'A3 周口径说明句', 1)
rep('<i class="sw-ico">转</i>本周转化与患者池', '<i class="sw-ico">转</i>上周转化与患者池',
    'A4 转化卡标题', 1)
rep('「本周转化与患者池」', '「上周转化与患者池」', 'A5 口径说明引用', 1)

print()
print('── B. 哨兵保护 ──')
PROT_SS = '⟦SS⟧'      # 上上周
PROT_N = '⟦NN⟧'       # 本周 →（顺延后）上周
PROT_K = '⟦KK⟧'       # 本周 →（保持）本周
PROT_L = '⟦LL⟧'       # 上周 →（保持）上周

# B1 已有的「上上周」先保护，避免被 上周→上上周 连锁
n = SRC.count('上上周')
SRC = SRC.replace('上上周', PROT_SS)
print('  %-40s %3d 处' % ('B1 保护已有「上上周」', n))

# B2 本周中应保持为「本周」的
KEEP_THIS = [
    '本周按自然周 9.21', '本周 9.21—9.27', '本周比上周同期', '本周<b>10.86万</b>',
    '占本周 <b>43.9%</b>', '占本周 <b>56.1%</b>', '本周至今 10.86', '本周 9.21—9.22',
    '本周（9.21—9.22', '本周经营总览', '本周协同任务', '本周在跑的闭环', '本周 vs 上周',
    '本周绝对数与环比', '本周核心指标', '本周应做 / 实做', '本周核心结果',
    '9.7–9.13 本周', '9.7–9.12（本周）', '本周补做重点', '排进本周补查',
    '主表尚未滚动到本周', '故本周以灰色标注', '本周（9.21—9.27）',
]
ksum = 0
for k in KEEP_THIS:
    c = SRC.count(k)
    if c:
        SRC = SRC.replace(k, k.replace('本周', PROT_K))
        ksum += c
print('  %-40s %3d 处' % ('B2 保护应留的「本周」', ksum))

# B3 上周中应保持为「上周」的（＝本次顺延后仍是上周的 9.14—9.20 引用）
KEEP_LAST = [
    '上周（9.14—9.20', '上周 9.14—9.20', '上周逐日营业收入（9.14—9.20',
    '上周（9.14—9.15', '上周 9.14—9.15', '上周转化与患者池', '上周 9.13—9.19',
    '上周同期 9.14—9.15', '上周同期<b>11.39万</b>', '与上周同期（9.14—9.15）',
    '比上周同期',
]
lsum = 0
for k in KEEP_LAST:
    c = SRC.count(k)
    if c:
        SRC = SRC.replace(k, k.replace('上周', PROT_L))
        lsum += c
print('  %-40s %3d 处' % ('B3 保护应留的「上周」', lsum))

print()
print('── C. 通用顺延 ──')
c1 = SRC.count('本周')
SRC = SRC.replace('本周', PROT_N)
print('  %-40s %3d 处' % ('C1 本周 → 占位', c1))
c2 = SRC.count('上周')
SRC = SRC.replace('上周', PROT_SS)
print('  %-40s %3d 处' % ('C2 上周 → 上上周', c2))

print()
print('── D. 还原 ──')
c3 = SRC.count(PROT_N)
SRC = SRC.replace(PROT_N, '上周')
print('  %-40s %3d 处' % ('D1 顺延占位 → 上周', c3))
c4 = SRC.count(PROT_L)
SRC = SRC.replace(PROT_L, '上周')
print('  %-40s %3d 处' % ('D2 保护上周 → 上周', c4))
c5 = SRC.count(PROT_SS)
SRC = SRC.replace(PROT_SS, '上上周')
print('  %-40s %3d 处' % ('D3 占位/保护 → 上上周', c5))
c6 = SRC.count(PROT_K)
SRC = SRC.replace(PROT_K, '本周')
print('  %-40s %3d 处' % ('D4 保护本周 → 本周', c6))

io.open(PATH, 'w', encoding='utf-8').write(SRC)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
ss = chk.count('上上周')
last = chk.count('上周') - ss
for k, v in [('本周', chk.count('本周')), ('上周（净）', last), ('上上周', ss),
             ('本周 9.21—9.27', chk.count('本周 9.21—9.27')),
             ('本周经营总览', chk.count('本周经营总览')),
             ('本周协同任务', chk.count('本周协同任务')),
             ('本周比上周同期', chk.count('本周比上周同期')),
             ('上周（9.14—9.20', chk.count('上周（9.14—9.20')),
             ('上周同期 9.14—9.15', chk.count('上周同期 9.14—9.15')),
             ('上上周（9.7—9.13', chk.count('上上周（9.7—9.13')),
             ('残留 ⟦', chk.count('⟦'))]:
    print('  %-26s %d' % (k, v))
if chk.count('⟦'):
    fails.append('哨兵未清理干净')
if re.search(r'上上上周|上上上上周', chk):
    fails.append('出现三重/四重「上上」')
if '本周 9.21—9.27' not in chk:
    fails.append('主口径 chip 被误改')

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
