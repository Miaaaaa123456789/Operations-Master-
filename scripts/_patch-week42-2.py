#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 2：营销分析（营收）面板 —— 明细项换本周 9.21—9.22，主表项保留上周并标注"""
import io

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
        fails.append('%s | 实际 %d / 期望 %d' % (tag, n, expect))
    SRC = SRC.replace(old, new)
    print('  %-34s %3d 处' % (tag, n))


print('── A. 日期条与徽标 ──')
rep("周口径：上周 9.14—9.20 · 上上周 9.7—9.13（同为完整 7 天）</p>",
    "周口径：本周 9.21—9.27（进行中 · 数据截至 9.22）· 上周同期 9.14—9.15（同为 2 天）</p>",
    'A1 datebar（静态）', 1)
rep("textContent='周口径：上周 9.14—9.20 · 上上周 9.7—9.13（同为完整 7 天）；",
    "textContent='周口径：本周 9.21—9.27（进行中 · 数据截至 9.22）· 上周同期 9.14—9.15（同为 2 天）；",
    'A2 datebar（JS）', 1)
rep("'更新于 2026.09.20'", "'更新于 2026.09.22'", 'A3 徽标（JS）', 1)
rep('<span class="sales-badge">更新于 2026.09.20</span>',
    '<span class="sales-badge">更新于 2026.09.22</span>', 'A4 徽标（静态）', 1)

print()
print('── B. hero 卡（医生组＝主表，保留上周值并标注）──')
rep('<label><i class="sw-ico">营</i>本周营业总额</label><strong>¥49.4万</strong>'
    '<small>9.14—9.20 · 日均 ¥7.06 万 · 较上周 <b class="sales-negative">−11.8%</b> · '
    '医生组总收入口径（营收日报同周 49.15 万）</small>',
    '<label><i class="sw-ico">营</i>营业总额 · 上周（9.14—9.20）</label><strong>¥49.4万</strong>'
    '<small>医生组表头总收入口径 · 日均 ¥7.06 万 · 较上上周 <b class="sales-negative">−11.8%</b> · '
    '<b>主表本周待更新</b>；营收日报口径本周（9.21—9.22，2 天）10.86 万</small>',
    'B1 hero 卡', 1)

print()
print('── C. 门诊 / 住院拆分（营收日报＝明细，换本周）──')
rep('<label><i class="sw-ico">诊</i>门诊收入</label><strong>¥27.10万</strong>'
    '<div class="sw-thin"><i style="width:55.1%"></i></div>'
    '<small>占本周 <b>55.1%</b> · 营收日报口径</small>',
    '<label><i class="sw-ico">诊</i>门诊收入</label><strong>¥4.77万</strong>'
    '<div class="sw-thin"><i style="width:43.9%"></i></div>'
    '<small>占本周 <b>43.9%</b> · 营收日报口径 9.21—9.22（2 天）</small>',
    'C1 门诊收入', 1)
rep('<label><i class="sw-ico">住</i>住院收入</label><strong>¥22.05万</strong>'
    '<div class="sw-thin alt"><i style="width:44.9%"></i></div>'
    '<small>占本周 <b>44.9%</b> · 营收日报口径</small>',
    '<label><i class="sw-ico">住</i>住院收入</label><strong>¥6.09万</strong>'
    '<div class="sw-thin alt"><i style="width:56.1%"></i></div>'
    '<small>占本周 <b>56.1%</b> · 营收日报口径 9.21—9.22（2 天）</small>',
    'C2 住院收入', 1)

print()
print('── D. 本周比上周（改同长短口径）──')
rep('<label><i class="sw-ico">比</i>本周比上周</label>'
    '<div class="sw-pair"><span>本周<b>49.15万</b></span><span>上周<b>48.65万</b></span></div>'
    '<div class="sw-bars2"><i class="now" style="height:100%"></i><i class="prev" style="height:99.0%"></i></div>'
    '<small class="sales-positive">+1.0% · 营收日报同口径</small>',
    '<label><i class="sw-ico">比</i>本周比上周同期</label>'
    '<div class="sw-pair"><span>本周<b>10.86万</b></span><span>上周同期<b>11.39万</b></span></div>'
    '<div class="sw-bars2"><i class="now" style="height:100%"></i><i class="prev" style="height:104.9%"></i></div>'
    '<small class="sales-negative">−4.6% · 同为 2 天（9.21—9.22 vs 9.14—9.15）</small>',
    'D1 周对比卡', 1)

print()
print('── E. 逐日柱与周末贡献（数据不足，保留上周完整周并标明）──')
rep('<h3><i class="sw-ico">日</i>每日营业收入（万元）<span class="sw-tag">周末贡献 40.4%</span></h3>',
    '<h3><i class="sw-ico">日</i>上周逐日营业收入（9.14—9.20，万元）'
    '<span class="sw-tag">本周至今 10.86 万（2 天）</span></h3>',
    'E1 柱状图标题', 1)
rep('<div class="sales-tooltip" id="salesTooltip">9.19（周六）13.77 万为本周最高，占全周 28.0%；'
    '9.20（周日）6.10 万；9.19＋9.20 两天合计 19.87 万，占全周 40.4%。</div>',
    '<div class="sales-tooltip" id="salesTooltip">上周（9.14—9.20）9.19（周六）13.77 万为最高，占全周 28.0%；'
    '9.20（周日）6.10 万；两天合计 19.87 万，占全周 40.4%。本周 9.21—9.22 两天合计 10.86 万，'
    '与上周同期（9.14—9.15）11.39 万比 −4.6%。</div>',
    'E2 柱状图 tooltip', 1)
rep('<h3>收入是否太靠周末</h3><p class="sub">本周 2 个周末日的收入贡献</p>',
    '<h3>收入是否太靠周末</h3><p class="sub">上周（9.14—9.20）2 个周末日的收入贡献</p>',
    'E3 周末卡副标题', 1)

print()
print('── F. 住院承接与转化（医生表＝非主表周数据，标注上周）──')
rep('<h3>住院承接有没有跟上</h3><p class="sub">入出院 9.14—9.20 · 医生工作量表</p>',
    '<h3>住院承接有没有跟上</h3><p class="sub">入出院 上周（9.14—9.20）· 医生工作量表</p>',
    'F1 住院卡副标题', 1)

print()
print('── G. 口径说明改写 ──')
rep('本周按自然周 9.14—9.20（7 天）计算，与上上周 9.7—9.13 同为 7 天。'
    '「本周营业总额 49.4 万」取《特别行动小组汇报表》医生组表头总收入（科主任口径，'
    '上周 56 万 → 本周 49.4 万，−11.8%）。'
    '下方逐日柱状图、门诊／住院拆分与「本周比上周」均为营收日报口径的 9.14—9.20，7 天合计 49',
    '本周按自然周 9.21—9.27（<b>进行中</b>，数据截至 9.22，已到 2 天）计算，'
    '区间对比一律取「上周同期 9.14—9.15」同为 2 天。'
    '「营业总额 49.4 万」为<b>上周（9.14—9.20）</b>《特别行动小组汇报表》医生组表头总收入'
    '（科主任口径，上上周 56 万 → 上周 49.4 万，−11.8%），<b>主表尚未滚动到本周</b>，故本周以灰色标注。'
    '门诊／住院拆分与「本周比上周同期」为营收日报口径的本周 9.21—9.22（2 天，合计 10.86 万）；'
    '逐日柱状图仍展示上周完整 7 天（9.14—9.20，合计 49',
    'G1 口径说明首段', 1)

out = SRC
io.open(PATH, 'w', encoding='utf-8').write(out)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
for k, v in [('本周 9.21—9.27（进行中', chk.count('本周 9.21—9.27（进行中')),
             ('更新于 2026.09.22', chk.count('更新于 2026.09.22')),
             ('¥4.77万', chk.count('¥4.77万')),
             ('¥6.09万', chk.count('¥6.09万')),
             ('¥10.86万', chk.count('¥10.86万')),
             ('残留 ¥27.10万', chk.count('¥27.10万')),
             ('残留 ¥22.05万', chk.count('¥22.05万')),
             ('残留 ¥49.15万', chk.count('¥49.15万'))]:
    print('  %-28s %d' % (k, v))
if chk.count('¥27.10万') or chk.count('¥22.05万'):
    fails.append('门诊/住院旧值未清干净')

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
