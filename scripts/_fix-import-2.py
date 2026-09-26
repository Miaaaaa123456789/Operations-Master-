# -*- coding: utf-8 -*-
"""「更新数据」链路修复 · 第二批：消费方改用统一在院取值 + rangeChip 随数据重绘 + 标签动态化"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []


def rep(fn, old, new, tag, cnt=1):
    p = R + fn
    s = io.open(p, encoding='utf-8').read()
    n = s.count(old)
    if n != cnt:
        fails.append('%-26s %-44s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-26s %-44s %d' % (fn, tag, n))


# ═════════════════ month-dashboard.js ═════════════════
# ① 引入统一在院取值
rep('month-dashboard.js',
    "    var x=source.derive(),m=x.month,w=x.currentWeek,last=source.rows[source.rows.length-1],"
    "fmt=function(v){return (v/10000).toFixed(2);},dis=w.discharges;",
    "    var x=source.derive(),m=x.month,w=x.currentWeek,last=source.rows[source.rows.length-1],"
    "fmt=function(v){return (v/10000).toFixed(2);},dis=w.discharges;\n"
    "    /* 在院人数取「最近一个有填报的日期」，避免最后一天缺该字段时被显示成 0 */\n"
    "    var lw=(source.lastWard&&source.lastWard())||{value:last.ward,date:last.date};",
    '月面板·引入 lw')

# ② KPI 在院人数
rep('month-dashboard.js',
    "{label:'在院人数',value:String(last.ward),unit:'人',note:md(last.date)+' 日终时点'},",
    "{label:'在院人数',value:String(lw.value==null?'—':lw.value),unit:'人',"
    "note:(lw.date?md(lw.date):md(last.date))+' 日终时点'},",
    '月面板·KPI 在院')

# ③ 预警里的在院
rep('month-dashboard.js',
    "copy:'入院'+w.admissions+'人、出院'+dis+'人，9月25日日终在院'+last.ward+'人。'",
    "copy:'入院'+w.admissions+'人、出院'+dis+'人，'+(lw.date?md(lw.date):'')+'日终在院'+lw.value+'人。'",
    '月面板·预警在院')

# ④ 预警标题天数动态
rep('month-dashboard.js',
    "{tone:'blue',icon:'✓',tag:'已核验',title:'25天累计连续勾稽',",
    "{tone:'blue',icon:'✓',tag:'已核验',title:m.days+'天累计连续勾稽',",
    '月面板·预警天数')

# ⑤ 漏斗在院
rep('month-dashboard.js',
    "baseData.funnel=[{label:'门诊',value:w.visits+'人次'},{label:'入院',value:w.admissions+'人'},"
    "{label:'出院',value:dis+'人'},{label:'在院',value:last.ward+'人'}];",
    "baseData.funnel=[{label:'门诊',value:w.visits+'人次'},{label:'入院',value:w.admissions+'人'},"
    "{label:'出院',value:dis+'人'},{label:'在院',value:(lw.value==null?'待补':lw.value)+'人'}];",
    '月面板·漏斗在院')

# ⑥ rangeChip 抽成函数（随数据更新重绘）
rep('month-dashboard.js',
    "if(range){var _ig=window.OPS_INGEST_DATE||'',_snap=window.SEPTEMBER_REVENUE_DATA||{},"
    "_igMd=_ig?((+_ig.slice(5,7))+'月'+(+_ig.slice(8))+'日'):'';"
    "range.innerHTML='<i>▦</i>9月1日—9月27日 · '+WEEK+'进行中 · '"
    "+((_igMd&&_ig!==_snap.updatedThrough)?('部门数据至 '+_igMd+' · '):'')"
    "+'营收数据至 '+(lastDateMd()||'—');}",
    "writeRangeChip();",
    '月面板·rangeChip 改函数调用')

rep('month-dashboard.js',
    "  function lastDateMd(){",
    "  /* rangeChip 抽成函数：原先只在 mount() 里写一次，导入新数据后仍显示旧营收日。\n"
    "     现在 mount 与 september-revenue-updated 各调用一次，时间戳随数据同步。 */\n"
    "  function writeRangeChip(){\n"
    "    var range=document.getElementById('rangeChip'); if(!range) return;\n"
    "    var _ig=window.OPS_INGEST_DATE||'', _snap=window.SEPTEMBER_REVENUE_DATA||{},\n"
    "        _igMd=_ig?((+_ig.slice(5,7))+'月'+(+_ig.slice(8))+'日'):'';\n"
    "    range.innerHTML='<i>▦</i>9月1日—9月27日 · '+WEEK+'进行中 · '\n"
    "      +((_igMd&&_ig!==_snap.updatedThrough)?('部门数据至 '+_igMd+' · '):'')\n"
    "      +'营收数据至 '+(lastDateMd()||'—');\n"
    "  }\n"
    "  function lastDateMd(){",
    '月面板·新增 writeRangeChip')

rep('month-dashboard.js',
    "window.addEventListener('september-revenue-updated',function(){applyRevenueSnapshot();"
    "data=clone(baseData);window.MONTH_DASHBOARD_DATA=data;rerender();});",
    "window.addEventListener('september-revenue-updated',function(){applyRevenueSnapshot();"
    "data=clone(baseData);window.MONTH_DASHBOARD_DATA=data;rerender();writeRangeChip();});",
    '月面板·更新时重绘 rangeChip')

# ═════════════════ marketing-current-report.js ═════════════════
rep('marketing-current-report.js',
    "var all=source.rows.slice(),wrows=source.subset('2026-09-21','2026-09-27'),x=source.derive(),"
    "m=x.month,w=x.currentWeek,prev=x.previousComparable,last=all[all.length-1],"
    "weekGrowth=delta(w.total,prev.total),forecast=x.forecast,top3=x.topDays.slice(0,3),"
    "top3Total=sum(top3,'total');",
    "var all=source.rows.slice(),wrows=source.subset('2026-09-21','2026-09-27'),x=source.derive(),"
    "m=x.month,w=x.currentWeek,prev=x.previousComparable,last=all[all.length-1],"
    "weekGrowth=delta(w.total,prev.total),forecast=x.forecast,top3=x.topDays.slice(0,3),"
    "top3Total=sum(top3,'total');\n"
    "    /* 在院取「最近一个有填报的日期」（缺字段自动回退，口径与月面板一致） */\n"
    "    var lw=(source.lastWard&&source.lastWard())||{value:last.ward,date:last.date};\n"
    "    var mdOf=function(d){return d?((+d.slice(5,7))+'月'+(+d.slice(8))+'日'):'';};",
    'mcr·引入 lw/mdOf')

rep('marketing-current-report.js',
    "window.MARKETING_REPORT_DATA={period:source.reportRange,updated:source.updatedAt,"
    "monthRevenue:m.total,weekRevenue:w.total,goal:goal,admissions:w.admissions,"
    "discharges:w.discharges,inpatients:last.ward,rows:all};",
    "window.MARKETING_REPORT_DATA={period:source.reportRange,updated:source.updatedAt,"
    "monthRevenue:m.total,weekRevenue:w.total,goal:goal,admissions:w.admissions,"
    "discharges:w.discharges,inpatients:lw.value,wardAt:lw.date,rows:all};",
    'mcr·对外数据 inpatients')

# 逐处 last.ward → lw.value（其余 5 处）
rep('marketing-current-report.js', "· 期末在院'+last.ward+'人</small>",
    "· 期末在院'+(lw.value==null?'待补':lw.value)+'人</small>", 'mcr·KPI 期末在院')
rep('marketing-current-report.js',
    "<article class=\"ward\"><i>院</i><span>在院</span><strong>'+last.ward+'<em>人</em></strong>"
    "<small>9月25日日终</small></article>",
    "<article class=\"ward\"><i>院</i><span>在院</span><strong>'+(lw.value==null?'待补':lw.value)"
    "+'<em>人</em></strong><small>'+mdOf(lw.date)+'日终</small></article>",
    'mcr·本周快照在院')
rep('marketing-current-report.js', "；期末在院'+last.ward+'人。",
    "；期末在院'+(lw.value==null?'待补':lw.value)+'人（'+mdOf(lw.date)+'）。", 'mcr·note 在院')
rep('marketing-current-report.js', "<td>期末'+last.ward+'</td><td>'+wan(w.total)+'万</td>",
    "<td>期末'+(lw.value==null?'—':lw.value)+'</td><td>'+wan(w.total)+'万</td>", 'mcr·tfoot 周在院')
rep('marketing-current-report.js', "<td>期末'+last.ward+'</td><td>'+wan(m.total)+'万</td>",
    "<td>期末'+(lw.value==null?'—':lw.value)+'</td><td>'+wan(m.total)+'万</td>", 'mcr·tfoot 月在院')

# ═════════════════ 标签动态化 ═════════════════
rep('marketing-current-report.js',
    "<strong>'+m.admissions+'人</strong><small>9.1—9.25累计</small>",
    "<strong>'+m.admissions+'人</strong><small>9.1—'+mdOf(last.date).replace('月','.').replace('日','')+'累计</small>",
    'mcr·入院累计标签')
rep('marketing-current-report.js',
    "<strong>'+w.discharges+'<em>人</em></strong><small>初次8 · 多次1</small>",
    "<strong>'+w.discharges+'<em>人</em></strong><small>初次'+w.dischargeFirst+' · 多次'+w.dischargeRepeat+'</small>",
    'mcr·出院构成标签')
rep('marketing-current-report.js',
    "<span>5天日均 ¥'+wan(w.average)+'万",
    "<span>'+w.days+'天日均 ¥'+wan(w.average)+'万",
    'mcr·日均天数标签')
rep('marketing-current-report.js',
    "<h2>'+WEEK+'</h2><p>截至9月25日23:59 · 9月26—27日待更新</p>",
    "<h2>'+WEEK+'</h2><p>截至'+mdOf(last.date)+'23:59 · '+(x.remainingDays?('剩余 '+x.remainingDays+' 天待更新'):'报告期已结束')+'</p>",
    'mcr·快照时间戳')
rep('marketing-current-report.js',
    "<b>●</b> 实际数据截至 '+source.updatedAt+' · 9月26—27日待更新</span>",
    "<b>●</b> 实际数据截至 '+source.updatedAt+' · '+(x.remainingDays?('剩余 '+x.remainingDays+' 天待更新'):'报告期已结束')+'</span>",
    'mcr·scope 时间戳')

print('=== 第二批完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
