#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 D：revision-v6.js / final-enhancements.js / marketing-detail.js 数据同步"""
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


print('══ revision-v6.js ══')
edit('revision-v6.js', [
    ("<h2>本周前两天经营变化</h2><p>9.21—9.22 与上周同期同口径</p></div>"
     '<span class="mkt-badge">营业额 −4.6%</span></div>',
     "<h2>本周至今经营变化</h2><p>9.21—9.23 与上周同期 9.14—9.16 同口径（营业额为 2 天口径）</p></div>"
     '<span class="mkt-badge">营业额 −4.6%</span></div>',
     'RV 标题', 1),
    ('<div class="priority-matrix"><div class="head">指标</div><div class="head">上周同期</div>'
     '<div class="head">本周至今</div><div class="head">变化</div>'
     '<b>营业额</b><span>11.39万</span><span>10.86万</span><span class="bad">−4.6%</span>'
     '<b>客服随访</b><span>31条</span><span>42条</span><span class="good">+35.5%</span>'
     '<b>标记到院</b><span>10人</span><span>14人</span><span class="good">+40.0%</span>'
     '<b>营销入院</b><span>1人</span><span>1人</span><span>持平</span></div>',
     '<div class="priority-matrix"><div class="head">指标（同期天数）</div><div class="head">上周同期</div>'
     '<div class="head">本周至今</div><div class="head">变化</div>'
     '<b>营业额（2 天）</b><span>11.39万</span><span>10.86万</span><span class="bad">−4.6%</span>'
     '<b>客服随访（3 天）</b><span>42条</span><span>49条</span><span class="good">+16.7%</span>'
     '<b>标记到院（3 天）</b><span>16人</span><span>18人</span><span class="good">+12.5%</span>'
     '<b>营销入院（3 天）</b><span>3人</span><span>3人</span><span>持平</span></div>',
     'RV 环比矩阵', 1),
    ('<p class="priority-summary">前端触达增加，但收入没有同步增长；本周营销转化率12.5%是分母缩小所致，'
     '实际入院仍为1人，暂不能解释为效率改善。</p>',
     '<p class="priority-summary">前端触达增加，但收入没有同步增长；本周营销转化率 27.3% 由小分母放大，'
     '实际入院仍为 3 人、接触量下降 15.4%，暂不能解释为效率改善。</p>',
     'RV 结论句', 1),
    ("<span>累计完成59.2%，落后时间进度14.1pt；剩余8天日均需13.26万。</span>",
     "<span>累计完成59.2%，落后时间进度14.1pt；剩余8天日均需13.26万。</span>",
     'RV AI-1', 1),
    # 部门卡数据
    ("butler:{title:'管家组',subtitle:'正式汇总口径 · 9.14—9.20',"
     "metrics:[['有效对接','78条'],['转住院','14人'],['转住院率','17.9%'],['初诊 / 复诊','21 / 57']]",
     "butler:{title:'管家组',subtitle:'业主汇总 78 条 / 逐条 80 条 · 9.14—9.20',"
     "metrics:[['有效对接','80条'],['转住院','14人'],['转住院率','17.5%'],['初诊 / 复诊','21 / 57']]",
     'RV 管家卡指标', 1),
    ("<div class=\"rank-note rank-ok\">工作量排名按业主汇总表78条计算；逐条记录80条（利娟多2条）"
     "保留为待核，不混入正式汇总。</div>",
     "<div class=\"rank-note rank-ok\">看板按逐条记录 80 条呈现（业主汇总表 78 条，差 2 条为利娟条目，"
     "已入核验清单）。个人样本仅 12—19 条，率值只作趋势参考。</div>",
     'RV 管家 rank-note', 1),
    ("<strong>78<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label>"
     "<strong>17.9<em>%</em></strong></span>",
     "<strong>80<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label>"
     "<strong>17.5<em>%</em></strong></span>",
     'RV 营销返回卡', 1),
])

print()
print('══ final-enhancements.js ══')
edit('final-enhancements.js', [
    ('<span class="finance-tag">数据截至 9月22日</span>',
     '<span class="finance-tag">数据截至 9月23日（营收 9月22日）</span>',
     'FE 财务标签', 1),
    ("butler:{title:'管家组经营详情',metrics:[['有效接触','78人'],['初诊 / 复诊','21 / 57'],"
     "['入院转化','14人'],['住院转化率','17.9%']]",
     "butler:{title:'管家组经营详情',metrics:[['有效接触','80人'],['初诊 / 复诊','21 / 57'],"
     "['入院转化','14人'],['住院转化率','17.5%']]",
     'FE 管家指标', 1),
    ("notes:['另有总量80人的旧口径冲突，须以患者级去重清单统一。',"
     "'本周客服随访42条、标记到院14人，到院率33.3%；需继续追踪挂号、治疗、入院和收入。',",
     "notes:['业主汇总表 78 条与逐条记录 80 条存在 2 条差异，须以患者级去重清单统一。',"
     "'本周至今（9.21—9.23）客服随访49条、标记到院18人，到院率36.7%；需继续追踪挂号、治疗、入院和收入。',",
     'FE 管家备注', 1),
])

print()
print('══ marketing-detail.js ══')
edit('marketing-detail.js', [
    ("<div class=\"mkt-day-insight good\"><b>本周前两天已有及时口径</b>"
     '<span>9.21—9.22合计10.86万、日均5.43万，比上周同期下降4.6%。</span></div>',
     '<div class="mkt-day-insight good"><b>本周营收已有及时口径</b>'
     '<span>9.21—9.22合计10.86万、日均5.43万，比上周同期下降4.6%（9.23 日报待补）。</span></div>',
     'MD 判断卡', 1),
    ('<h2>环比分析</h2><p>本周前两天与上周同期同口径比较</p>',
     '<h2>环比分析</h2><p>本周至今（9.21—9.23）与上周同期（9.14—9.16）同口径比较</p>',
     'MD 环比标题', 1),
    ('<div class="head">指标</div><div class="head">上周同期</div>'
     '<div class="head">本周至今</div><div class="head">变化 / 判断</div>'
     '<b>营业额</b><span>11.39万</span><span>10.86万</span><span class="bad">−4.6%</span>'
     '<b>客服随访</b><span>31条</span><span>42条</span><span class="good">+35.5%</span>'
     '<b>标记到院</b><span>10人</span><span>14人</span><span class="good">+40.0%</span>'
     '<b>客服到院率</b><span>32.3%</span><span>33.3%</span><span class="good">+1.0pt</span>'
     '<b>营销接触</b><span>9人</span><span>8人</span><span class="bad">−11.1%</span>'
     '<b>营销入院</b><span>1人</span><span>1人</span><span>持平</span>'
     '<b>营销转化率</b><span>11.1%</span><span>12.5%</span><span class="bad">分母缩小</span></div>',
     '<div class="head">指标（同期天数）</div><div class="head">上周同期</div>'
     '<div class="head">本周至今</div><div class="head">变化 / 判断</div>'
     '<b>营业额（2 天）</b><span>11.39万</span><span>10.86万</span><span class="bad">−4.6%</span>'
     '<b>客服随访（3 天）</b><span>42条</span><span>49条</span><span class="good">+16.7%</span>'
     '<b>标记到院（3 天）</b><span>16人</span><span>18人</span><span class="good">+12.5%</span>'
     '<b>客服到院率</b><span>38.1%</span><span>36.7%</span><span class="bad">−1.4pt</span>'
     '<b>营销接触（3 天）</b><span>13人</span><span>11人</span><span class="bad">−15.4%</span>'
     '<b>营销入院（3 天）</b><span>3人</span><span>3人</span><span>持平</span>'
     '<b>营销转化率</b><span>23.1%</span><span>27.3%</span><span class="bad">分母缩小</span></div>',
     'MD 环比矩阵', 1),
    ('前端触达改善，但营业额没有同步增长；营销转化率上升不能视为效率改善，因为实际入院仍为1人。',
     '前端触达改善，但营业额没有同步增长；营销转化率上升不能视为效率改善，因为入院绝对数未增加、'
     '接触量还下降 15.4%。', 'MD 结论句', 1),
    ("document.getElementById('sheetSub').textContent='数据更新至 2026年9月22日 · 独立部门经营模块'",
     "document.getElementById('sheetSub').textContent='数据更新至 2026年9月24日 · 独立部门经营模块'",
     'MD sheetSub', 1),
    ("butler:{title:'管家组',sub:'患者对接、项目转介与住院承接',"
     "intro:'管家组关注患者级转化路径，单纯对接条数不能代表转化质量。',"
     "metrics:[['有效对接','78条'],['转住院','14人'],['转住院率','17.9%'],['心理咨询转介','19条']]",
     "butler:{title:'管家组',sub:'患者对接、项目转介与住院承接',"
     "intro:'管家组关注患者级转化路径，单纯对接条数不能代表转化质量。',"
     "metrics:[['有效对接','80条'],['转住院','14人'],['转住院率','17.5%'],['心理咨询转介','19条']]",
     'MD 管家子卡', 1),
    ("<div class=\"dc-metric\"><label>有效对接</label><strong>78<em>条</em></strong></div>"
     "<span class=\"dc-metric\"><label>转住院率</label><strong>17.9<em>%</em></strong></span>",
     "<div class=\"dc-metric\"><label>有效对接</label><strong>80<em>条</em></strong></div>"
     "<span class=\"dc-metric\"><label>转住院率</label><strong>17.5<em>%</em></strong></span>",
     'MD 管家卡片', 1),
])

print()
print('── 回读校验 ──')
for f in ['revision-v6.js', 'final-enhancements.js', 'marketing-detail.js']:
    c = io.open(f, encoding='utf-8').read()
    print('  %-26s 残留78条=%d 残留17.9=%d' % (f, c.count('78条'), c.count('17.9')))
    if c.count('78条'):
        fails.append('%s 残留 78条' % f)

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
