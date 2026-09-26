# -*- coding: utf-8 -*-
"""「更新数据」链路修复 · 第三批：问题地图改为数据派生（原先写死、永不更新）"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []


def rep(fn, old, new, tag, cnt=1):
    p = R + fn
    s = io.open(p, encoding='utf-8').read()
    n = s.count(old)
    if n != cnt:
        fails.append('%-14s %-40s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-14s %-40s %d' % (fn, tag, n))


OLD_BLOCK = (
    "const old=section.querySelector('.problem-map');if(old)old.remove();\n"
    "      section.querySelector('.section-head').insertAdjacentHTML('afterend',"
    "`<div class=\"problem-map\"><div class=\"problem-lane\">"
    "<span class=\"problem-node\"><small>物理治疗应做</small><b>1019 次</b></span>"
    "<span class=\"problem-arrow\">→</span><span class=\"problem-node risk\"><small>未做</small><b>85 次</b></span>"
    "<span class=\"problem-arrow\">→</span><span class=\"problem-node action\"><small>优先动作</small><b>台账闭环</b></span></div>"
    "<div class=\"problem-lane\"><span class=\"problem-node\"><small>9月累计收入</small><b>178.00万</b></span>"
    "<span class=\"problem-arrow\">→</span><span class=\"problem-node risk\"><small>目标完成</small><b>68.5%</b></span>"
    "<span class=\"problem-arrow\">→</span><span class=\"problem-node action\"><small>剩余缺口</small><b>82.00万</b></span></div>"
    "<div class=\"problem-lane\"><span class=\"problem-node\"><small>在管患者</small><b>78 人</b></span>"
    "<span class=\"problem-arrow\">→</span><span class=\"problem-node\"><small>在院</small><b>31 人</b></span>"
    "<span class=\"problem-arrow\">→</span><span class=\"problem-node action\"><small>优先动作</small><b>按在院派班</b></span></div></div>`);\n"
    "      renderDetailedSignals();"
)

NEW_BLOCK = (
    "writeProblemMap();\n"
    "      renderDetailedSignals();"
)

rep('index.html', OLD_BLOCK, NEW_BLOCK, '问题地图·改函数调用')

# 在 renderVisualInsights 定义前插入 writeProblemMap（同一 script 块，函数声明会提升）
rep('index.html',
    "    function renderVisualInsights(){",
    "    /* 问题地图：原先是一段写死的 HTML，导入新数据后永不更新（只有初始化时渲染一次）。\n"
    "       现改为从 OPS_REVENUE（营收日报，唯一真源）派生，并在 ops:revenue-updated 时重绘。\n"
    "       「在管患者」＝当前在院 ＋ 9 月累计出院（营收日报口径）。 */\n"
    "    function writeProblemMap(){\n"
    "      const sec=document.getElementById('insights'); if(!sec) return;\n"
    "      const old=sec.querySelector('.problem-map'); if(old) old.remove();\n"
    "      const head=sec.querySelector('.section-head'); if(!head) return;\n"
    "      let S=null; try{ S=window.OPS_REVENUE&&window.OPS_REVENUE.summary(); }catch(e){}\n"
    "      const inc   = (S&&S.done!=null)   ? S.done.toFixed(2)    : '—';\n"
    "      const pctv  = (S&&S.pct!=null)    ? S.pct.toFixed(1)     : '—';\n"
    "      const gapv  = (S&&S.leftAmt!=null)? S.leftAmt.toFixed(2) : '—';\n"
    "      const P     = (S&&S.tw&&S.tw.p)||{};\n"
    "      const ward  = (P.inhos==null) ? '待补' : String(P.inhos);\n"
    "      const disch = (S&&S.mtd&&S.mtd.p&&S.mtd.p.disch!=null) ? S.mtd.p.disch : null;\n"
    "      const managed = (P.inhos==null||disch==null) ? '待补' : String(P.inhos+disch);\n"
    "      head.insertAdjacentHTML('afterend',\n"
    "        '<div class=\"problem-map\">'\n"
    "        + '<div class=\"problem-lane\"><span class=\"problem-node\"><small>物理治疗应做</small><b>1019 次</b></span>'\n"
    "        + '<span class=\"problem-arrow\">→</span><span class=\"problem-node risk\"><small>未做</small><b>85 次</b></span>'\n"
    "        + '<span class=\"problem-arrow\">→</span><span class=\"problem-node action\"><small>优先动作</small><b>台账闭环</b></span></div>'\n"
    "        + '<div class=\"problem-lane\"><span class=\"problem-node\"><small>9月累计收入</small><b>'+inc+'万</b></span>'\n"
    "        + '<span class=\"problem-arrow\">→</span><span class=\"problem-node risk\"><small>目标完成</small><b>'+pctv+'%</b></span>'\n"
    "        + '<span class=\"problem-arrow\">→</span><span class=\"problem-node action\"><small>剩余缺口</small><b>'+gapv+'万</b></span></div>'\n"
    "        + '<div class=\"problem-lane\"><span class=\"problem-node\"><small>在管患者</small><b>'+managed+' 人</b></span>'\n"
    "        + '<span class=\"problem-arrow\">→</span><span class=\"problem-node\"><small>在院</small><b>'+ward+' 人</b></span>'\n"
    "        + '<span class=\"problem-arrow\">→</span><span class=\"problem-node action\"><small>优先动作</small><b>按在院派班</b></span></div>'\n"
    "        + '</div>');\n"
    "    }\n"
    "    /* 数据更新后重绘问题地图（data-import.js 每次写入都会派发该事件） */\n"
    "    window.addEventListener('ops:revenue-updated',function(){ try{ writeProblemMap(); }catch(e){} });\n"
    "    window.writeProblemMap=writeProblemMap;\n"
    "    function renderVisualInsights(){",
    '新增 writeProblemMap + 监听')

print('=== 第三批完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
