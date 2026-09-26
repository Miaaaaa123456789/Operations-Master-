#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把营收口径从 9.24 推进到 9.25（数据源：psyc.harness@bdc215f 的 9.25 日报）。

新口径（已交叉验证：178.00 万累计、34.97 万本周，与 GitHub 版一致）
  · 9.1—9.25 累计 177.9978 万 → 178.00 万，完成 68.5%
  · 时间进度 25/30 = 83.3%，落后 14.9pt
  · 剩余 5 天、82.00 万，日均需 16.40 万
  · 本周 9.21—9.25（5 天）34.97 万，日均 6.99 万，缺口 9.41 万
  · 上周同期 9.14—9.18（5 天）29.28 万 → +19.4%
  · Hero：在院 31 / 本周入院 13 / 本周出院 9 / 门诊 141
"""
import io, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def patch(fname, pairs):
    p = os.path.join(REPO, fname)
    s = io.open(p, encoding='utf-8').read()
    before = len(s)
    ok = 0
    for old, new, tag in pairs:
        n = s.count(old)
        if n != 1:
            fails.append('%-22s %-30s 匹配 %d' % (fname, tag, n))
            continue
        s = s.replace(old, new)
        ok += 1
    if ok == len(pairs):
        io.open(p, 'w', encoding='utf-8').write(s)
        print('  ✓ %-22s %d 处（%+d B）' % (fname, ok, len(s) - before))
    else:
        print('  ✗ %-22s 仅 %d/%d，未写' % (fname, ok, len(pairs)))


# ═════════════ index.html：Hero 五指标 + 营收目标卡
patch('index.html', [
    # Hero：在院 30→31、入院 10→13、出院 7→9、门诊 87→141，天数 4→5
    ('<div class="ov-kpi"><label>在院人数</label><strong>30<em>人</em></strong><span class="ov-chip">最新时点 9.24</span></div>'
     '<div class="ov-kpi"><label>本周入院</label><strong>10<em>人</em></strong><span class="ov-chip">9.21—9.24（4 天）</span></div>'
     '<div class="ov-kpi"><label>本周出院</label><strong>7<em>人</em></strong><span class="ov-chip">9.21—9.24（4 天）</span></div>'
     '<div class="ov-kpi"><label>门诊</label><strong>87<em>人</em></strong><span class="ov-chip">9.21—9.24（4 天）营收日报</span></div>',
     '<div class="ov-kpi"><label>在院人数</label><strong>31<em>人</em></strong><span class="ov-chip">最新时点 9.25</span></div>'
     '<div class="ov-kpi"><label>本周入院</label><strong>13<em>人</em></strong><span class="ov-chip">9.21—9.25（5 天）</span></div>'
     '<div class="ov-kpi"><label>本周出院</label><strong>9<em>人</em></strong><span class="ov-chip">9.21—9.25（5 天）</span></div>'
     '<div class="ov-kpi"><label>门诊</label><strong>141<em>人</em></strong><span class="ov-chip">9.21—9.25（5 天）营收日报</span></div>',
     'Hero 五指标'),
    ('<span class="ov-chip">9月1日—9月24日 <i>⌄</i></span>',
     '<span class="ov-chip">9月1日—9月25日 <i>⌄</i></span>', '目标卡 chip'),
    ('<div class="ov-amount"><strong>167.88</strong><em>／260万</em></div>'
     '<div class="ov-bar" role="img" aria-label="营收完成率 64.6%，时间进度 80.0%">'
     '<i style="width:64.6%"></i><u style="left:80.0%"></u></div>'
     '<div class="ov-two"><div><span>金额完成</span><b>64.6%</b></div>'
     '<div><span>时间进度</span><b>80.0%</b></div>'
     '<div><span>进度差</span><b class="neg">落后 15.4pt</b></div></div>',
     '<div class="ov-amount"><strong>178.00</strong><em>／260万</em></div>'
     '<div class="ov-bar" role="img" aria-label="营收完成率 68.5%，时间进度 83.3%">'
     '<i style="width:68.5%"></i><u style="left:83.3%"></u></div>'
     '<div class="ov-two"><div><span>金额完成</span><b>68.5%</b></div>'
     '<div><span>时间进度</span><b>83.3%</b></div>'
     '<div><span>进度差</span><b class="neg">落后 14.9pt</b></div></div>',
     '目标卡数值'),
    ('<p class="ov-gap">剩余 <b>6</b> 天需 <b>92.12 万</b>，日均需 <b>15.35 万</b>；上周日均 <b>7.02 万</b>、本周至今（9.21—9.24）日均 <b>6.21 万</b>，缺口 <b>9.14 万</b>。</p>',
     '<p class="ov-gap">剩余 <b>5</b> 天需 <b>82.00 万</b>，日均需 <b>16.40 万</b>；上周日均 <b>7.02 万</b>、本周至今（9.21—9.25）日均 <b>6.99 万</b>，缺口 <b>9.41 万</b>。</p>',
     '目标卡缺口句'),
    # 时间戳
    ('title="本页主口径：本周 9.21—9.27（进行中 · 数据截至 9.26，营收 9.24）"',
     'title="本页主口径：本周 9.21—9.27（进行中 · 数据截至 9.26，营收 9.25）"', 'rangeChip'),
    ('数据截至 9.26（营收日报至 9.24；客服 / 心理 / 管家已并入本周至今值）',
     '数据截至 9.26（营收日报至 9.25；客服 / 心理 / 管家已并入本周至今值）', '首页口径段'),
    ('<h2>9月1日—9月24日</h2><p>周口径：本周 9.21—9.27（进行中 · 营收数据截至 9.24）· 上周同期 9.14—9.17（同为 4 天）</p></div><span class="sales-badge">更新于 2026.09.24</span>',
     '<h2>9月1日—9月25日</h2><p>周口径：本周 9.21—9.27（进行中 · 营收数据截至 9.25）· 上周同期 9.14—9.18（同为 5 天）</p></div><span class="sales-badge">更新于 2026.09.25</span>',
     '月度栏静态'),
    ("datebar.querySelector('h2').textContent='9月1日—9月24日';datebar.querySelector('p').textContent='周口径：本周 9.21—9.27（进行中 · 营收数据截至 9.24）· 上周同期 9.14—9.17（同为 4 天）；旧口径的第一周 9.1—9.6 只有 6 天，不并入上周对比';datebar.querySelector('.sales-badge').textContent='更新于 2026.09.24';",
     "datebar.querySelector('h2').textContent='9月1日—9月25日';datebar.querySelector('p').textContent='周口径：本周 9.21—9.27（进行中 · 营收数据截至 9.25）· 上周同期 9.14—9.18（同为 5 天）；旧口径的第一周 9.1—9.6 只有 6 天，不并入上周对比';datebar.querySelector('.sales-badge').textContent='更新于 2026.09.25';",
     '月度栏 JS'),
])

# ═════════════ marketing-redesign.js：营销 hero
patch('marketing-redesign.js', [
    ('<div class="mkt-amount">¥24.85<i>万</i></div><div class="mkt-sub">9月21—24日 · 日均 ¥6.21万 · 较上周同期 +13.3%（9.25—9.26 日报待补）</div>',
     '<div class="mkt-amount">¥34.97<i>万</i></div><div class="mkt-sub">9月21—25日 · 日均 ¥6.99万 · 较上周同期 +19.4%（9.26—9.27 日报待补）</div>',
     '营销 hero'),
])

# ═════════════ revision-v6.js：环比卡营业额行
patch('revision-v6.js', [
    ('<p>9.21—9.24 与上周同期 9.14—9.17 同口径（各 4 天）</p></div><span class="mkt-badge">营业额 +13.3%</span>',
     '<p>营收 9.21—9.25（5 天）· 触达类 9.21—9.24（4 天），各自与上周同期同天数对照</p></div><span class="mkt-badge">营业额 +19.4%</span>',
     '卡头'),
    ('<b>营业额（4 天）</b><span>21.94万</span><span>24.85万</span><span class="good">+13.3%</span>',
     '<b>营业额（5 天）</b><span>29.28万</span><span>34.97万</span><span class="good">+19.4%</span>',
     '营业额行'),
    ('<p class="priority-summary">触达与收入同向增长：营业额 +13.3%、客服随访 +13.0%、营销对接 24→28 条、入院 4→8 人（转化率 28.6%）。但到院率由 37.0% 降到 34.6%，且入院样本仍小，需患者级去重与收费归因后才能定论。</p>',
     '<p class="priority-summary">营收提速明显：9.25 单日 10.12 万为本周峰值，本周累计 34.97 万、较上周同期 +19.4%；客服随访 +13.0%、营销对接 24→28 条、入院 4→8 人（转化率 28.6%）。但到院率由 37.0% 降到 34.6%，且入院样本仍小，需患者级去重与收费归因后才能定论。</p>',
     '小结'),
])

# ═════════════ marketing-detail.js：逐日判断 + 环比矩阵
patch('marketing-detail.js', [
    ('<div class="mkt-day-insight good"><b>本周营收已有及时口径</b><span>9.21—9.24 合计24.85万、日均6.21万，比上周同期 21.94 万增长13.3%（9.25—9.26 日报待补）。</span></div>',
     '<div class="mkt-day-insight good"><b>本周营收已有及时口径</b><span>9.21—9.25 合计34.97万、日均6.99万，比上周同期 29.28 万增长19.4%；9.25 单日 10.12 万为本周峰值（9.26—9.27 日报待补）。</span></div>',
     '逐日判断'),
    ('<b>营业额（4 天）</b><span>21.94万</span><span>24.85万</span><span class="good">+13.3%</span>',
     '<b>营业额（5 天）</b><span>29.28万</span><span>34.97万</span><span class="good">+19.4%</span>',
     '环比矩阵营业额行'),
])

# ═════════════ business-analysis.js：时间戳 + 营收判断
patch('business-analysis.js', [
    ('<span class="dc-scope">本周 9.21—9.27 · 数据截至 9.26（营收 9.24）</span>',
     '<span class="dc-scope">本周 9.21—9.27 · 数据截至 9.26（营收 9.25）</span>', 'dc-scope'),
    ('<span>营收日报日均6.21万（9.24 止），达标需15.35万</span>',
     '<span>营收日报日均6.99万（9.25 止），达标需16.40万</span>', 'dc-node 结果'),
    ("shell.querySelector('.mkt-sub').textContent='9月21—24日 · 日均 ¥6.21万 · 较上周同期 +13.3%（9.25—9.26 日报待补）';",
     "shell.querySelector('.mkt-sub').textContent='9月21—25日 · 日均 ¥6.99万 · 较上周同期 +19.4%（9.26—9.27 日报待补）';",
     'mkt-sub 静态'),
    ('<span>累计167.88万，完成64.6%；剩余6天需92.12万。当前日均6.21万，距离达标所需日均15.35万仍差9.14万。</span>',
     '<span>累计178.00万，完成68.5%；剩余5天需82.00万。当前日均6.99万，距离达标所需日均16.40万仍差9.41万。</span>',
     '横幅静态'),
])

# ═════════════ final-enhancements.js：时间戳
patch('final-enhancements.js', [
    ('<span class="finance-tag">数据截至 9月26日（营收 9月24日）</span>',
     '<span class="finance-tag">数据截至 9月26日（营收 9月25日）</span>', 'finance-tag'),
])

if fails:
    print('\n✗ 未匹配：')
    for f in fails:
        print('   -', f)
    sys.exit(1)
print('\n✓ 9.25 营收口径同步完成')
