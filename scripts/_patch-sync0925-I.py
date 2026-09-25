#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 I：JS 模块 —— 经营问题总览 / 营销面板 / 子部门数据 同步到 9.24"""
import io

fails = []


def edit(path, pairs):
    global fails
    s = io.open(path, encoding='utf-8').read()
    for old, new, tag, expect in pairs:
        n = s.count(old)
        if n == 0:
            fails.append('%s/%s 未找到' % (path, tag))
            print('  ✗ %-30s 未找到' % tag)
            continue
        if expect is not None and n != expect:
            fails.append('%s/%s 实际 %d 期望 %d' % (path, tag, n, expect))
        s = s.replace(old, new)
        print('  ✓ %-30s %3d 处' % (tag, n))
    io.open(path, 'w', encoding='utf-8').write(s)


print('══ business-analysis.js ══')
edit('business-analysis.js', [
    ('<span class="dc-scope">本周 9.21—9.27 · 数据截至 9.23（营收 9.22）</span>',
     '<span class="dc-scope">本周 9.21—9.27 · 数据截至 9.24（营收 9.22）</span>', '范围标签', 1),
    ('<span>客服随访49条、到院18人，但收入未同步增长</span>',
     '<span>客服随访52条、到院18人，但收入未同步增长</span>', '链路1 触达', 1),
    ('<span>营销接触11人、入院3人，小样本仍不足以证明改善</span>',
     '<span>营销接触28人、入院8人，转化回升但仍待观察</span>', '链路2 转化', 1),
    ('<article class="dc-risk orange"><label>前端未变现</label><strong>到院率36.7%</strong>'
     '<p>随访 +16.7%、到院 +12.5%，但营业额反降4.6%，到院未形成足够付费。</p></article>',
     '<article class="dc-risk orange"><label>前端未变现</label><strong>到院率34.6%</strong>'
     '<p>随访 +13.0%、到院 +5.9%，但营业额反降4.6%，到院未形成足够付费。</p></article>',
     '风险2 未变现', 1),
    ('<article class="dc-risk blue"><label>营销小样本</label><strong>11人 → 3人</strong>'
     '<p>接触量下降15.4%，转化率27.3%由小分母放大，暂不能判定效率改善。</p></article>',
     '<article class="dc-risk blue"><label>营销转化</label><strong>24人 → 28人</strong>'
     '<p>住院 4→8 人、转化率 28.6%，仍需患者级去重与收费归因后才能定论。</p></article>',
     '风险3 小样本', 1),
    ("<strong>49条</strong><span>较上周同期 +16.7%（9.14—9.16）</span>",
     "<strong>52条</strong><span>较上周同期 +13.0%（9.14—9.17）</span>", 'KPI 客服随访', 1),
    ("<strong>18人</strong><span>到院率 36.7%</span>",
     "<strong>18人</strong><span>到院率 34.6%</span>", 'KPI 标记到院', 1),
    ("<strong>11人</strong><span>较上周同期 −15.4%</span>",
     "<strong>28人</strong><span>较上周同期 +16.7%</span>", 'KPI 营销接触', 1),
    ("<strong>3人</strong><span>与上周同期持平（3 人）</span>",
     "<strong>8人</strong><span>较上周同期 +100%</span>", 'KPI 营销入院', 1),
    ("<strong>27.3%</strong><span>小样本，不判定改善</span>",
     "<strong>28.6%</strong><span>小样本，不判定改善</span>", 'KPI 营销转化', 1),
    ("shell.querySelector('.mkt-sub').textContent='9月21—22日 · 日均 ¥5.43万 · "
     "较上周同期 −4.6%（9.23 日报待补）';",
     "shell.querySelector('.mkt-sub').textContent='9月21—22日 · 日均 ¥5.43万 · "
     "较上周同期 −4.6%（9.23—9.24 日报待补）';", 'hero 副标题', 1),
    ('<article class="mkt-analysis-card"><label>客服触达</label><strong>增长但未变现</strong>'
     '<p>到院 16→18 人，同期营业额却下降4.6%。</p></article>',
     '<article class="mkt-analysis-card"><label>客服触达</label><strong>增长但未变现</strong>'
     '<p>到院 17→18 人、回访 +13.0%，同期营业额却下降4.6%。</p></article>', '分析卡1', 1),
    ('<article class="mkt-analysis-card"><label>营销转化</label><strong>小样本待观察</strong>'
     '<p>入院 3 人，但接触量下降15.4%，率升来自分母变小。</p></article>',
     '<article class="mkt-analysis-card"><label>营销转化</label><strong>本期明显回升</strong>'
     '<p>对接 24→28 条、入院 4→8 人，转化率 28.6%，待患者级归因确认。</p></article>',
     '分析卡2', 1),
    ('本周至今日均5.43万（9.21—9.22，9.23 待补），较上周同期11.39万下降4.6%；',
     '本周至今日均5.43万（9.21—9.22，9.23—9.24 待补），较上周同期11.39万下降4.6%；',
     '条目1', 1),
    ('<p>客服随访49条、到院18人；上周同期42条、到院16人。随访增长16.7%、到院增长12.5%，'
     '但营业额反降。',
     '<p>客服随访52条、到院18人；上周同期46条、到院17人。随访增长13.0%、到院增长5.9%，'
     '但营业额反降。', '条目2', 1),
    ('<p>本周接触11人、入院3人，转化率27.3%；上周同期13人、入院3人，23.1%。'
     '入院绝对数未增加、触达量还下降15.4%，',
     '<p>本周对接28条、入院8人，转化率28.6%；上周同期24条、入院4人，16.7%。'
     '入院与对接同步上升，但样本仍小，', '条目3', 1),
    ('等差异；医生组和护理组尚未更新到本周，营收日报 9.23 尚未回传。',
     '等差异；医生组和护理组尚未更新到本周，营收日报 9.23—9.24 尚未回传。', '警示条', 1),
])

print()
print('══ revision-v6.js ══')
edit('revision-v6.js', [
    ('<p>9.21—9.23 与上周同期 9.14—9.16 同口径（营业额为 2 天口径）</p>',
     '<p>9.21—9.24 与上周同期 9.14—9.17 同口径（各 4 天；营业额为 2 天口径）</p>', '标题', 1),
    ('<b>客服随访（3 天）</b><span>42条</span><span>49条</span><span class="good">+16.7%</span>'
     '<b>标记到院（3 天）</b><span>16人</span><span>18人</span><span class="good">+12.5%</span>'
     '<b>营销入院（3 天）</b><span>3人</span><span>3人</span><span>持平</span>',
     '<b>客服随访（4 天）</b><span>46条</span><span>52条</span><span class="good">+13.0%</span>'
     '<b>标记到院（4 天）</b><span>17人</span><span>18人</span><span class="good">+5.9%</span>'
     '<b>营销对接（4 天）</b><span>24条</span><span>28条</span><span class="good">+16.7%</span>'
     '<b>营销入院（4 天）</b><span>4人</span><span>8人</span><span class="good">+100%</span>',
     '环比矩阵', 1),
    ('前端触达增加，但收入没有同步增长；本周营销转化率 27.3% 由小分母放大，'
     '实际入院仍为 3 人、接触量下降 15.4%，暂不能解释为效率改善。',
     '前端触达增加，但收入没有同步增长；营销对接 24→28 条、入院 4→8 人、'
     '转化率 28.6%，回升明显但仍属小样本，需患者级去重与收费归因后才能定论。',
     '结论句', 1),
    ('<span>完整周周末贡献40.4%，周一仅3.56万，平日转化能力不足。</span>',
     '<span>上周完整周周末贡献40.4%，周一仅3.56万，平日转化能力不足。</span>', 'AI-3', 1),
])

print()
print('══ marketing-detail.js ══')
edit('marketing-detail.js', [
    ('<h2>环比分析</h2><p>本周至今（9.21—9.23）与上周同期（9.14—9.16）同口径比较</p>',
     '<h2>环比分析</h2><p>本周至今（9.21—9.24）与上周同期（9.14—9.17）同口径比较（各 4 天）</p>',
     '标题', 1),
    ('<b>客服随访（3 天）</b><span>42条</span><span>49条</span><span class="good">+16.7%</span>'
     '<b>标记到院（3 天）</b><span>16人</span><span>18人</span><span class="good">+12.5%</span>'
     '<b>客服到院率</b><span>38.1%</span><span>36.7%</span><span class="bad">−1.4pt</span>'
     '<b>营销接触（3 天）</b><span>13人</span><span>11人</span><span class="bad">−15.4%</span>'
     '<b>营销入院（3 天）</b><span>3人</span><span>3人</span><span>持平</span>'
     '<b>营销转化率</b><span>23.1%</span><span>27.3%</span><span class="bad">分母缩小</span>',
     '<b>客服随访（4 天）</b><span>46条</span><span>52条</span><span class="good">+13.0%</span>'
     '<b>标记到院（4 天）</b><span>17人</span><span>18人</span><span class="good">+5.9%</span>'
     '<b>客服到院率</b><span>37.0%</span><span>34.6%</span><span class="bad">−2.4pt</span>'
     '<b>营销对接（4 天）</b><span>24条</span><span>28条</span><span class="good">+16.7%</span>'
     '<b>营销入院（4 天）</b><span>4人</span><span>8人</span><span class="good">+100%</span>'
     '<b>营销转化率</b><span>16.7%</span><span>28.6%</span><span class="good">+11.9pt</span>',
     '环比矩阵', 1),
    ('前端触达改善，但营业额没有同步增长；营销转化率上升不能视为效率改善，'
     '因为入院绝对数未增加、接触量还下降 15.4%。',
     '前端触达改善，但营业额没有同步增长；营销对接量与入院数同步上升、转化率 28.6%，'
     '回升明显但仍属小样本，需患者级归因确认。', '结论句', 1),
    ('<span>9.21—9.22合计10.86万、日均5.43万，比上周同期下降4.6%（9.23 日报待补）。</span>',
     '<span>9.21—9.22合计10.86万、日均5.43万，比上周同期下降4.6%（9.23—9.24 日报待补）。</span>',
     '判断卡', 1),
])

print()
print('══ final-enhancements.js ══')
edit('final-enhancements.js', [
    ("'本周至今（9.21—9.23）客服随访49条、标记到院18人，到院率36.7%；"
     "需继续追踪挂号、治疗、入院和收入。'",
     "'本周至今（9.21—9.24）客服随访52条、标记到院18人，到院率34.6%；"
     "需继续追踪挂号、治疗、入院和收入。'", '管家备注', 1),
    ('<span class="finance-tag">数据截至 9月23日（营收 9月22日）</span>',
     '<span class="finance-tag">数据截至 9月24日（营收 9月22日）</span>', '财务标签', 1),
])

print()
print('── 回读校验 ──')
for f in ['business-analysis.js', 'revision-v6.js', 'marketing-detail.js',
          'final-enhancements.js']:
    c = io.open(f, encoding='utf-8').read()
    bad = {k: c.count(k) for k in ['36.7%', '27.3%', '15.4%', '49条', '11人</strong>',
                                   '9.21—9.23', '3 人）', '9月23日（营收'] if c.count(k)}
    print('  %-24s 残留 %s' % (f, bad if bad else '无'))
    if bad:
        fails.append('%s 残留 %s' % (f, bad))

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
