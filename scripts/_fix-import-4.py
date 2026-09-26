# -*- coding: utf-8 -*-
"""「更新数据」链路修复 · 第四批：剩余写死文案（mcr AI 判断 / 快照标签 / 月面板出院注）"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []


def rep(fn, old, new, tag, cnt=1):
    p = R + fn
    s = io.open(p, encoding='utf-8').read()
    n = s.count(old)
    if n != cnt:
        fails.append('%-28s %-40s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-28s %-40s %d' % (fn, tag, n))


# ① 本周快照·入院标签日期
rep('marketing-current-report.js',
    "<strong>'+w.admissions+'<em>人</em></strong><small>9.21—9.25累计</small>",
    "<strong>'+w.admissions+'<em>人</em></strong><small>9.21—'+mdOf(last.date)+'累计</small>",
    'mcr·入院标签日期')

# ② AI 判断第 1 条：月累计 / 天数 / 剩余天数 全部动态
rep('marketing-current-report.js',
    "<li><i>1</i><span>月累计177.998万元，若按25天平均速度推演，月末约'+wan(forecast)+'万元，"
    "预计缺口'+wan(goal-forecast)+'万元；达标需未来5天日均'+wan(x.requiredDaily)+'万元。</span></li>",
    "<li><i>1</i><span>月累计'+wan(m.total)+'万元，若按'+m.days+'天平均速度推演，月末约'+wan(forecast)+'万元，"
    "预计缺口'+wan(goal-forecast)+'万元；达标需未来'+x.remainingDays+'天日均'+wan(x.requiredDaily)+'万元。</span></li>",
    'mcr·AI 1 动态')

# ③ AI 判断第 2 条：本周天数
rep('marketing-current-report.js',
    "<li><i>2</i><span>本周前5天较上周同期增长'",
    "<li><i>2</i><span>本周前'+w.days+'天较上周同期增长'",
    'mcr·AI 2 天数')

# ④ 出院「初次/多次」拆分：本仓 OPS_REVENUE 出院只有一列合计（多次记 0），
#    展示拆分会误导成「多次 0 人」，故改为口径说明
rep('marketing-current-report.js',
    "<strong>'+w.discharges+'<em>人</em></strong><small>初次'+w.dischargeFirst+' · 多次'+w.dischargeRepeat+'</small>",
    "<strong>'+w.discharges+'<em>人</em></strong><small>营收日报口径（含多次）</small>",
    'mcr·快照出院口径')
rep('marketing-current-report.js',
    "<strong>'+m.discharges+'人</strong><small>初次与多次出院合计</small>",
    "<strong>'+m.discharges+'人</strong><small>营收日报口径（含多次）</small>",
    'mcr·KPI 出院口径')

# ⑤ 月面板 KPI 出院注
rep('month-dashboard.js',
    "{label:WEEK+'出院',value:String(dis),unit:'人',note:'初次 8＋多次 1'},",
    "{label:WEEK+'出院',value:String(dis),unit:'人',note:'营收日报口径（含多次）'},",
    '月面板·出院口径')

print('=== 第四批完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
