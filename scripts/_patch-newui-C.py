#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 C：marketing-redesign.js 数据同步（本周至今 + 上周完整周 9.14—9.20）"""
import io

PATH = 'marketing-redesign.js'
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


print('── C1. 逐日数组改为上周完整周 9.14—9.20 ──')
rep("const days=[['9.13','16.40','100','周日'],['9.14','3.56','22','周一'],"
    "['9.15','7.82','48','周二'],['9.16','4.22','26','周三'],['9.17','6.33','39','周四'],"
    "['9.18','7.34','45','周五'],['9.19','13.77','84','周六']];",
    "const days=[['9.14','3.56','26','周一'],['9.15','7.82','57','周二'],"
    "['9.16','4.22','31','周三'],['9.17','6.33','46','周四'],['9.18','7.34','53','周五'],"
    "['9.19','13.77','100','周六'],['9.20','6.10','44','周日']];",
    'days 数组')

print()
print('── C2. 顶部筛选行与 hero ──')
rep("<small><b>●</b> 数据更新至 2026.09.20　·　9月13日—9月19日</small>",
    "<small><b>●</b> 数据更新至 2026.09.23　·　本周 9月21日—9月27日（进行中，营收至 9月22日）</small>",
    '筛选行')
rep('<div class="mkt-hero-kicker">本周营业总额</div>'
    '<div class="mkt-amount">¥59.45<i>万</i></div>'
    '<div class="mkt-sub">7天合计 · 日均 ¥8.49万 · 较上周 +6.2%</div>',
    '<div class="mkt-hero-kicker">本周至今营业额</div>'
    '<div class="mkt-amount">¥10.86<i>万</i></div>'
    '<div class="mkt-sub">9月21—22日 · 日均 ¥5.43万 · 较上周同期 −4.6%（9.23 日报待补）</div>',
    'hero')

print()
print('── C3. 六项 KPI（默认值，随后由 business-analysis 覆盖）──')
rep('<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">♧</i>门诊收入</div>'
    '<strong>¥37.68万</strong><span>占总收入 63.4%</span></article>'
    '<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">▥</i>住院收入</div>'
    '<strong>¥21.77万</strong><span>占总收入 36.6%</span></article>'
    '<article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">＋</i>初诊</div>'
    '<strong>41人</strong><span>本周新增线索</span></article>'
    '<article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">↗</i>入院</div>'
    '<strong>15人</strong><span>初诊转入院 36.6%</span></article>'
    '<article class="mkt-kpi purple"><div class="mkt-kpi-head"><i class="mkt-ico">－</i>出院</div>'
    '<strong>17人</strong><span>患者池流出</span></article>'
    '<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">◎</i>在院</div>'
    '<strong>30人</strong><span>9月20日时点</span></article>',
    '<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">♧</i>门诊收入</div>'
    '<strong>¥27.10万</strong><span>占完整周 55.1%</span></article>'
    '<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">▥</i>住院收入</div>'
    '<strong>¥22.05万</strong><span>占完整周 44.9%</span></article>'
    '<article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">＋</i>初诊</div>'
    '<strong>41人</strong><span>上周完整周线索</span></article>'
    '<article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">↗</i>入院</div>'
    '<strong>14人</strong><span>初诊转入院 34.1%</span></article>'
    '<article class="mkt-kpi purple"><div class="mkt-kpi-head"><i class="mkt-ico">－</i>出院</div>'
    '<strong>13人</strong><span>患者池流出</span></article>'
    '<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">◎</i>在院</div>'
    '<strong>27人</strong><span>9月20日时点</span></article>',
    '六项 KPI')

print()
print('── C4. 目标进度卡 ──')
rep('<div class="mkt-progress-big"><b>153.89万 / 260万</b>',
    '<div class="mkt-progress-big"><b>153.89万 / 260万</b>', '目标进度（占位核对）')
rep('<div><span>当前日均</span><b>8.10万</b></div>',
    '<div><span>当前日均</span><b>5.43万</b></div>', '当前日均')

print()
print('── C5. 每日营业收入卡头 ──')
rep('<div><h2>每日营业收入</h2><p>万元 · 周末贡献 50.7%</p></div>'
    '<span class="mkt-badge">峰值 9.13</span>',
    '<div><h2>每日营业收入</h2><p>上周完整周 9.14—9.20 · 周末贡献 40.4%</p></div>'
    '<span class="mkt-badge">峰值 9.19</span>',
    '柱状图卡头')

print()
print('── C6. 收入结构卡 ──')
rep('<div class="mkt-ring-row"><div class="mkt-ring"><div><b>59.45万</b>本周总额</div></div>'
    '<div class="mkt-legend"><span><b style="color:#26ae81">63.4%</b>门诊 37.68万</span>'
    '<span><b style="color:#2e8ee9">36.6%</b>住院 21.77万</span></div></div>',
    '<div class="mkt-ring-row"><div class="mkt-ring"><div><b>49.15万</b>上周完整周</div></div>'
    '<div class="mkt-legend"><span><b style="color:#26ae81">55.1%</b>门诊 27.10万</span>'
    '<span><b style="color:#2e8ee9">44.9%</b>住院 22.05万</span></div></div>',
    '收入结构')

print()
print('── C7. 转化漏斗卡 ──')
rep('<div class="mkt-flow"><div class="mkt-flow-box">初诊<b>41</b>人</div>'
    '<div class="mkt-arrow">→</div><div class="mkt-flow-box green">入院<b>15</b>人</div></div>'
    '<div class="mkt-outflow"><span>初诊转入院</span><b>36.6%</b></div>'
    '<div class="mkt-outflow"><span>本周出院</span><b>17人</b></div>',
    '<div class="mkt-flow"><div class="mkt-flow-box">初诊<b>41</b>人</div>'
    '<div class="mkt-arrow">→</div><div class="mkt-flow-box green">入院<b>14</b>人</div></div>'
    '<div class="mkt-outflow"><span>初诊转入院</span><b>34.1%</b></div>'
    '<div class="mkt-outflow"><span>上周出院</span><b>13人</b></div>',
    '转化漏斗')

print()
print('── C8. 环比分析卡 ──')
rep('<h2>环比分析</h2><p>与上一个完整周比较</p></div></div>'
    '<div class="mkt-compare"><div class="mkt-compare-row"><b>周营业额</b><span>55.98 → 59.45万</span><strong>+6.2%</strong></div>'
    '<div class="mkt-compare-row"><b>日均收入</b><span>8.00 → 8.49万</span><strong>+6.1%</strong></div>'
    '<div class="mkt-compare-row"><b>初诊人数</b><span>40 → 41人</span><strong>+2.5%</strong></div>'
    '<div class="mkt-compare-row"><b>入院人数</b><span>12 → 15人</span><strong>+25.0%</strong></div></div>',
    '<h2>环比分析</h2><p>上周完整周 9.14—9.20 与上上周 9.7—9.13 比较</p></div></div>'
    '<div class="mkt-compare"><div class="mkt-compare-row"><b>周营业额</b><span>48.65 → 49.15万</span><strong>+1.0%</strong></div>'
    '<div class="mkt-compare-row"><b>日均收入</b><span>6.95 → 7.02万</span><strong>+1.0%</strong></div>'
    '<div class="mkt-compare-row"><b>初诊人数</b><span>40 → 41人</span><strong>+2.5%</strong></div>'
    '<div class="mkt-compare-row"><b>入院人数</b><span>12 → 14人</span><strong>+16.7%</strong></div></div>',
    '环比分析')

print()
print('── C9. AI 经营判断卡 ──')
rep('<li><i>1</i><span>月目标落后时间进度 14.1 个百分点，需要提高平日收入。</span></li>'
    '<li><i>2</i><span>周末贡献超过一半，收入结构仍然过度集中。</span></li>'
    '<li><i>3</i><span>初诊转入院改善，但患者池本周净减少 2 人。</span></li>',
    '<li><i>1</i><span>月目标落后时间进度 14.1 个百分点，需要提高平日收入。</span></li>'
    '<li><i>2</i><span>上周完整周周末贡献 40.4%，收入结构仍偏集中。</span></li>'
    '<li><i>3</i><span>上周完整周入院 14、出院 13，患者池仅净增 1 人。</span></li>',
    'AI 判断')

print()
print('── C10. 下周行动卡 ──')
rep('<li><i>1</i><span>复制周末高收入项目到周一至周三。</span></li>'
    '<li><i>2</i><span>逐条跟进未入院的 26 位初诊患者。</span></li>'
    '<li><i>3</i><span>将日收入低于 6 万设为即时预警。</span></li>',
    '<li><i>1</i><span>复制高峰日高收入项目到周一至周三。</span></li>'
    '<li><i>2</i><span>逐条跟进上周未入院的 27 位初诊患者。</span></li>'
    '<li><i>3</i><span>将日收入低于 5 万设为即时预警（上周最低 3.56 万）。</span></li>',
    '下周行动')

print()
print('── C11. 底部口径行 ──')
rep('<p class="mkt-source">口径：营业收入 9.13—9.19；转化漏斗为初诊 41 → 入院 15；'
    '出院 17 独立作为患者池流出。导入新数据后先校验冲突，再更新看板。</p>',
    '<p class="mkt-source">口径：本周至今为 9.21—9.27（数据截至 9.23，营收日报至 9.22）；'
    '上周完整周为 9.14—9.20（营收 49.15 万 ＝ 门诊 27.10 ＋ 在院 22.05），'
    '转化漏斗为初诊 41 → 入院 14，出院 13 独立作为患者池流出。'
    '导入新数据后先校验冲突，再更新看板。</p>',
    '底部口径')

io.open(PATH, 'w', encoding='utf-8').write(s)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
for k, v in [('¥10.86', chk.count('¥10.86')), ('¥27.10万', chk.count('¥27.10万')),
             ('¥22.05万', chk.count('¥22.05万')), ('5.43万', chk.count('5.43万')),
             ('数据更新至 2026.09.23', chk.count('数据更新至 2026.09.23')),
             ('残留 59.45', chk.count('59.45')), ('残留 37.68', chk.count('37.68')),
             ('残留 21.77', chk.count('21.77')), ('残留 9.13—9.19', chk.count('9.13—9.19')),
             ('残留 2026.09.20', chk.count('2026.09.20'))]:
    print('  %-24s %d' % (k, v))
for bad, lab in [('59.45', '营收 59.45'), ('37.68', '门诊 37.68'), ('21.77', '住院 21.77'),
                 ('9.13—9.19', '旧周区间'), ('2026.09.20', '旧更新日')]:
    if chk.count(bad):
        fails.append('营销模块残留旧值 %s（%d 处）' % (lab, chk.count(bad)))

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
