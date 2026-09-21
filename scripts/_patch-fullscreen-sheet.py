#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""部门弹层（#deptSheet）全屏化补丁 —— 业主 2026-09-21：
「把所有部门经营点开的界面都改为全屏展示，保证数据和文字突出」

做法：
  1) CSS 覆盖 .sheet 为满屏 flex 三段式（头部 / 页签 / 可滚动 body），内容限宽 1240 居中
  2) 放大指标数值、排名、诊断、明细表字号；宽屏（>=1040px）列表改多列
  3) HTML 把 sheet-tabs 之后的全部内容包进 .sheet-body（保证头部常驻、只有内容区滚动）
  4) openDeptV2 打开时把 .sheet-body 滚回顶部（避免残留上次滚动位置）

铁律：所有替换失败只收集到 fails，不做中途 raise，最后统一写盘 + 回读校验。
"""
import io

PATH = 'index.html'
s = io.open(PATH, encoding='utf-8').read()
fails = []


def rep(old, new, tag, count=1):
    global s
    n = s.count(old)
    if n != count:
        fails.append('%s: 期望 %d 处，实际 %d 处' % (tag, count, n))
        return
    s = s.replace(old, new)


# ---------------------------------------------------------------- 1) CSS
CSS = """
/* ===== 部门弹层全屏展示（业主 2026-09-21：全屏 + 数据与文字突出）===== */
.sheet{inset:0;width:100%;max-width:100%;height:100%;height:100dvh;max-height:none;display:flex;flex-direction:column;overflow:hidden;border-radius:0;padding:0;box-shadow:none;transform:translateY(100%);transition:transform .3s cubic-bezier(.2,.8,.2,1)}
.sheet.show{transform:translateY(0)}
.sheet>.grip{display:none}
.sheet-head{flex:none;padding:calc(16px + env(safe-area-inset-top,0px)) max(20px,calc((100vw - 1240px)/2)) 0;align-items:flex-start}
.sheet-head h2{font-size:24px;line-height:1.25;letter-spacing:-.3px}
.sheet-close{flex:none;width:40px;height:40px;border-radius:13px;font-size:22px;line-height:1;background:#FDECEF;color:#D8354F;font-weight:600}
.sheet-sub{flex:none;margin:7px 0 0;padding:0 max(20px,calc((100vw - 1240px)/2));font-size:13px;line-height:1.55}
.sheet-tabs{flex:none;margin:14px max(20px,calc((100vw - 1240px)/2)) 0;grid-template-columns:repeat(3,1fr);gap:6px;padding:5px;border-radius:14px}
.sheet-tab{padding:11px 8px;font-size:14px;border-radius:11px}
.sheet-body{flex:1 1 auto;min-height:0;overflow:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;padding:16px max(20px,calc((100vw - 1240px)/2)) calc(40px + env(safe-area-inset-bottom,0px))}
/* 指标与文字放大 */
.sheet .metric-row{padding:15px 17px;border-radius:16px}
.sheet .metric-row label{font-size:15px;font-weight:600}
.sheet .metric-row small{font-size:12.5px;line-height:1.55;margin-top:5px}
.sheet .metric-num strong{font-size:27px;letter-spacing:-.5px}
.sheet .metric-num span{font-size:14px;display:block;margin-top:3px}
.sheet .metric-row.is-missing strong{font-size:22px}
.sheet .sheet-section-title{font-size:16px;margin:24px 0 12px}
.sheet .history-card{padding:14px 16px;border-radius:16px}
.sheet .history-head strong{font-size:15px}
.sheet .history-values{margin-top:10px;gap:6px}
.sheet .history-values span{font-size:12px}
.sheet .history-values b{font-size:16px;margin-top:4px}
.sheet .rank-group{margin-top:18px}
.sheet .rank-group h4{font-size:15px}
.sheet .rank-list{gap:8px;margin-top:11px}
.sheet .rank-row{padding:12px 14px;border-radius:14px}
.sheet .rank-person strong{font-size:14.5px}
.sheet .rank-person span{font-size:12px}
.sheet .rank-score strong{font-size:17px}
.sheet .rank-score span{font-size:12px}
.sheet .rank-source{font-size:12px}
.sheet .diagnosis-item{padding:14px 16px}
.sheet .diagnosis-item b{font-size:13.5px}
.sheet .diagnosis-item p{font-size:13px;line-height:1.7}
.sheet .dept-sales-list .dsl-head{padding:10px 12px}
.sheet .dept-sales-list .dsl-head strong{font-size:13px}
.sheet .dept-sales-list .dsl-head span{font-size:11px}
.sheet .dept-sales-list .dsl-row{padding:9px 12px;font-size:12.5px}
/* 护理绩效页（文字密集，整块适度放大）*/
.sheet .business-body{padding:16px}
.sheet .np-banner{font-size:13px}
.sheet .nursing-perf table.np-orig{font-size:13px}
.sheet .np-orig th{font-size:12px;padding:10px 9px}
.sheet .np-orig td{padding:10px 9px}
.sheet .np-problem-cell{font-size:13px}
.sheet .np-rank-row{font-size:13px;padding:8px 10px}
.sheet .np-cover{font-size:12px}
.sheet .np-pb-facts p{font-size:13px}
.sheet .np-pb-do{font-size:12.5px}
.sheet .np-banner{padding:13px 16px}
/* 宽屏：充分利用全屏宽度，列表分两列 */
@media(min-width:1040px){
  .sheet .metric-list{grid-template-columns:repeat(2,1fr);gap:10px}
  .sheet .history-list{grid-template-columns:repeat(2,1fr);gap:12px}
  .sheet .rank-list{grid-template-columns:repeat(2,1fr)}
  .sheet .diagnosis{grid-template-columns:repeat(2,1fr);gap:12px}
}
@media(max-width:400px){
  .sheet-head h2{font-size:20px}
  .sheet-tab{font-size:12.5px;padding:10px 4px}
  .sheet .metric-num strong{font-size:24px}
  .sheet .metric-row label{font-size:14px}
}
"""

idx = s.rfind('</style>')
if idx < 0:
    fails.append('CSS: 找不到 </style>')
else:
    s = s[:idx] + CSS + s[idx:]

# ------------------------------------------------- 2) HTML 包裹 .sheet-body
i = s.find('<aside class="sheet" id="deptSheet"')
if i < 0:
    fails.append('HTML: 找不到 #deptSheet')
else:
    j = s.find('</aside>', i)
    k = s.find('<div class="sheet-pane active"', i)
    if j < 0 or k < 0 or not (i < k < j):
        fails.append('HTML: deptSheet 结构定位失败 j=%d k=%d' % (j, k))
    else:
        s = s[:k] + '<div class="sheet-body">' + s[k:j] + '</div>' + s[j:]

# ------------------------------------------------- 3) 打开时滚回顶部
rep("document.querySelectorAll('.sheet-pane').forEach((p,i)=>p.classList.toggle('active',i===0));document.getElementById('deptSheet')",
    "document.querySelectorAll('.sheet-pane').forEach((p,i)=>p.classList.toggle('active',i===0));const _sb=document.querySelector('.sheet-body');if(_sb)_sb.scrollTop=0;const _st=document.querySelector('.sheet-tabs');if(_st)_st.scrollLeft=0;document.getElementById('deptSheet')",
    'JS: openDeptV2 打开重置滚动')

# ---------------------------------------------------------------- 写盘
if fails:
    print('FAILED (未写盘):')
    for f in fails:
        print('  -', f)
    raise SystemExit(1)

io.open(PATH, 'w', encoding='utf-8').write(s)

# 回读校验
chk = io.open(PATH, encoding='utf-8').read()
checks = {
    '.sheet-body CSS 规则': chk.count('.sheet-body{flex:1 1 auto'),
    '<div class="sheet-body">': chk.count('<div class="sheet-body">'),
    'sheet-body 包裹 sheet-pane': chk.count('<div class="sheet-body"><div class="sheet-pane active"'),
    'sheet-body 闭合(>=1 视为通过)': 1 if chk.count('</div></div></aside>') >= 1 else 0,
    'sheet 全宽(覆盖桌面 460px 抽屉)': chk.count('.sheet{inset:0;width:100%;max-width:100%'),
    '.sheet{inset:0': chk.count('.sheet{inset:0'),
    'JS 重置滚动': chk.count("const _sb=document.querySelector('.sheet-body')"),
    '宽屏多列媒体查询': chk.count('@media(min-width:1040px)'),
}
bad = {k: v for k, v in checks.items() if v != 1}
print('写入完成，', len(s), 'bytes')
for k, v in checks.items():
    print(('  OK  ' if v == 1 else '  BAD '), k, '=', v)
if bad:
    raise SystemExit(2)
print('ALL CHECKS PASSED')
