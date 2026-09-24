#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 E：index.html 客服/导诊数据全面纠正（完整周 9.14—9.20 精确值）"""
import io

PATH = 'index.html'
s = io.open(PATH, encoding='utf-8').read()
fails = []

# 精确值（源表实算，9.14—9.20）：
#   回访 67 条；到院 30 = 44.8%；蒋雨 28（13→46.4%，41.8%，均分 4.96）
#   温诗怡 20（10→50.0%，29.9%，均分 4.85）；张欣雨 19（7→36.8%，28.4%，均分 4.84）
#   满意度 5 分 60 / 4 分 7；到院字段 是30 / 否36 / 空1
#   主动服务 12 条；日工作量 32 人日 3,382 分
#   逐日回访 8/23/11/4/3/11/7 = 67

STEPS = [
    ('30/68', '30/67', '到院率分数 30/68', 6),
    ('61/68', '60/67', '满意度占比 61/68', 1),
    ('44.1%', '44.8%', '到院率 44.1%', 13),
    ('68 条', '67 条', '回访条数 68 条', None),
    ('68条', '67条', '回访条数 68条', 1),
    ("value:'68',unit:'条'", "value:'67',unit:'条'", '部门卡数值', 1),
    ('张欣雨 20', '张欣雨 19', '张欣雨条数', None),
    ('7/20 = 35.0%', '7/19 = 36.8%', '张欣雨到院率', 1),
    ('trend:[8,24,11,4,3,11,7]', 'trend:[8,23,11,4,3,11,7]', '部门卡趋势线', 1),
    ('8/24/11/4/3/11/7', '8/23/11/4/3/11/7', '逐日序列', None),
    ('否 37', '否 36', '到院字段否', 1),
    ('蒋雨 28 条（占 41.2%）', '蒋雨 28 条（占 41.8%）', '蒋雨占比', 1),
    ('蒋雨一人承担 28 条（42.4%）', '蒋雨一人承担 28 条（41.8%）', '蒋雨占比2', 1),
    ('导诊主动服务 <span class="hl-key">13 条</span>',
     '导诊主动服务 <span class="hl-key">12 条</span>', '主动服务 13→12', None),
]

for old, new, tag, expect in STEPS:
    n = s.count(old)
    if n == 0:
        fails.append('%s 未找到' % tag)
        print('  ✗ %-26s 未找到' % tag)
        continue
    if expect is not None and n != expect:
        fails.append('%s 实际 %d 期望 %d' % (tag, n, expect))
    s = s.replace(old, new)
    print('  ✓ %-26s %3d 处' % (tag, n))

io.open(PATH, 'w', encoding='utf-8').write(s)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
resid = {'30/68': chk.count('30/68'), '61/68': chk.count('61/68'), '44.1%': chk.count('44.1%'),
         '68 条': chk.count('68 条'), '68条': chk.count('68条'), '张欣雨 20': chk.count('张欣雨 20'),
         '否 37': chk.count('否 37'), '41.2%': chk.count('41.2%'), '42.4%': chk.count('42.4%'),
         '13 条主动服务': chk.count('主动服务 <span class="hl-key">13 条')}
for k, v in resid.items():
    print('  残留 %-14s %d' % (k, v))
    if v:
        fails.append('残留 %s' % k)
print()
for k, v in [('回访 67 条', chk.count('67 条')), ('30/67', chk.count('30/67')),
             ('44.8%', chk.count('44.8%')), ('60/67', chk.count('60/67')),
             ('张欣雨 19', chk.count('张欣雨 19'))]:
    print('  新值 %-14s %d' % (k, v))

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
