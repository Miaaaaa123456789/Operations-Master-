#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看板 UI 优化补丁 —— 业主 2026-09-21「更新看板 ui」（design-update-required）

5 类问题（均来自线上 agent-browser 量化体检）：
  ① 文案矛盾：真名版却写着「员工姓名已脱敏 · 经营数值均为虚构」（index.html:482）
  ② 文本溢出：.kpi-tile label 被 ellipsis 截断 5 处；.sw-card>strong 溢出卡片 4 处
  ③ 字号过小：实测 429 处 <11px（216 处为排班码网格、34 处为日期轴）
  ④ 触控目标：12 处 <40px（AI 洞察 32 / section-link 27 / 待核验 33 / 标记完成 35）
  ⑤ 低对比度：#9AA5B4 仅 2.5:1、--muted #7b8193 仅 3.9:1（WCAG AA 需 4.5:1）

铁律：替换失败只收集到 fails、不中途 raise；最后统一写盘 + 回读校验。
"""
import io
import re

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


# ───────────────────────── ① 脱敏声明矛盾（1 处）
rep('<body><div style="position:relative;z-index:80;padding:7px 12px;text-align:center;'
    'background:#fff4d6;border-bottom:1px solid #ecd28e;color:#795b13;font-size:12px;'
    'font-weight:700">演示版 · 员工姓名已脱敏 · 经营数值均为虚构</div>',
    '<body><div class="sys-banner">内部经营看板 · 数据仅供院内分析使用</div>',
    '① 脱敏声明文案')

# ───────────────────────── ② 文本溢出
# 2a. 核心指标 label 不再 ellipsis 截断（375 视口下 5 处被截）
rep('.kpi-tile label{display:block;font-size:12px;color:var(--muted);white-space:nowrap;'
    'overflow:hidden;text-overflow:ellipsis}',
    '.kpi-tile label{display:block;font-size:12px;color:var(--muted);white-space:normal;'
    'line-height:1.35}',
    '②a .kpi-tile label 允许换行')

# 2b. 营销概况在窄屏改单列，让 ¥37.68万 这类大数字装得下
rep('.sales-kpis{grid-template-columns:1fr 1fr;gap:7px}',
    '.sales-kpis{grid-template-columns:minmax(0,1fr);gap:9px}',
    '②b .sales-kpis 窄屏单列')

# ───────────────────────── ⑤b 散落的硬编码浅灰统一加深
# 这 14 个色值仅用于 color（无一用于背景/边框），且全部落在浅底上（已核验），
# 对比度 2.6—4.3:1，统一提到 #616A7C（白底 5.43:1 / 浅灰底 4.84:1）
GRAYS = ['#8993A4', '#7D8798', '#7B8698', '#7C8597', '#98A0B1', '#828A9B', '#858A98',
         '#737C90', '#788195', '#74798B', '#6F7585', '#7B8398', '#868EA0', '#777C8D',
         '#A0A4B0', '#9296A2', '#999DAB', '#7D8698']
gray_n = 0
for _g in GRAYS:
    gray_n += len(re.findall(r'color:' + _g, s, re.I))
    s = re.sub(r'color:' + _g, 'color:#616A7C', s, flags=re.I)
if gray_n == 0:
    fails.append('⑤b 未匹配到任何散落浅灰色值')

# ───────────────────────── ③④⑤ CSS 覆盖块
CSS = """
/* ===== 看板 UI 优化：字号可读性 / 触控目标 / 对比度（2026-09-21） ===== */
/* ① 顶部信息条（原为「演示版·已脱敏·虚构」黄色警示条，与真名版内容矛盾） */
.sys-banner{position:relative;z-index:80;padding:8px 12px;text-align:center;background:#F0F6FC;border-bottom:1px solid #D6E7F5;color:#0B4F9E;font-size:12px;font-weight:700;letter-spacing:.2px}

/* ② 文本不再截断：核心指标标签允许换行（口径日期完整可见） */
.kpi-tile label{white-space:normal;overflow:visible;text-overflow:clip;line-height:1.35}

/* ③ 字号可读性：密集区（排班码网格 / 日期轴 / 周柱标签）适度放大，
      说明类文字统一到 11px。排班码与日期轴受格子限制，取能容纳的上限。 */
.np-shift-cell{font-size:10.5px}
.sw-week-bars .sw-wbar .dow{font-size:10.5px}
/* 日期轴：格子仅 16px 宽（1100px 等中等屏部门卡多列时），字号不放大，只加深颜色提对比度 */
.dc-axis i{color:#616A7C}
.problem-node small,
.np-tbd,
.np-mismatch,
.week-column span,
.month-day,
.sales-badge,
.dept-status,
.dc-metric label,
.dc-metrics .dc-metric label,
.dept-sales-metrics div,
.dept-sales-head span,
.axis-labels,
.coverage-rings .ring b,
.sw-axis,
.sw-mini div,
.sw-conv-head span,
.sw-pair span,
.ni-card .ni-num,
.ni-sum,
.np-pb-tag,
.np-pb-do em,
.dept-sales-list .dsl-row.dsl-th,
.dept-sales-list .dsl-note{font-size:11px}
.ov-kpi .ov-chip{color:#5A6376;white-space:normal;line-height:1.3;overflow:visible;text-overflow:clip}
.hero-revenue .hr-note,
.dc-foot .dept-hint{font-size:11px}
/* 部门卡双指标标签：容器窄（375 下约 62px），允许换行以免长标签被截断 */
.dc-metrics .dc-metric label{white-space:normal;line-height:1.3;color:#616A7C}
.dc-metric label{color:#616A7C}
.ov-kpi strong em,
.dc-metric strong em{color:#616A7C}
.dc-foot .dept-delta,
.dept-status{color:#616A7C}

/* ④ 触控目标 ≥44px（AI 洞察 32→44 / 标记完成 35→44 / 头部按钮 33-38→44） */
.ai-entry{min-height:44px;display:inline-flex;align-items:center}
.head-action{min-height:44px;display:inline-flex;align-items:center}
.complete-btn{min-height:44px;display:inline-flex;align-items:center;padding:0 16px}
.section-link{min-height:44px;display:inline-flex;align-items:center;padding:0 9px}
/* ④b 其余可点击元素（体检剩余 6 类）：日期按钮 / 营销关闭 / 月份页签 / 工具按钮 / 弹层关闭 / 弹层页签 */
.period{min-height:44px;display:inline-flex;align-items:center}
.sales-close{min-width:44px;min-height:44px}
.sales-month-tabs button{min-height:44px}
.sales-month-tools button{width:44px;height:44px}
.sheet-close{min-width:44px;min-height:44px}
.sheet-tab{min-height:44px}
.flow-head{min-height:44px}

/* ⑤ 对比度：--muted 由 #7b8193(3.9:1) 提到 4.76:1；浅灰 #9AA5B4(2.5:1) 一并加深 */
:root{--muted:#616A7C}
.dc-axis i{color:#616A7C}
.ov-note>summary span{color:#616A7C}
.search-drop .none{color:#616A7C}

/* 窄屏：营销概况单列后给数字留足空间 */
@media(max-width:719px){
  .sales-kpis{grid-template-columns:minmax(0,1fr);gap:9px}
  .sw-card>strong{font-size:26px}
}
/* 极窄屏（≤400px）：部门卡为单列，日期轴格子够宽，可放到 9px */
@media(max-width:400px){
  .dc-axis i{font-size:9px;letter-spacing:-.4px}
  .np-shift-cell{font-size:10px}
}
/* 中等屏（721—1240px）：Hero 5 列收窄，数字略降避免「209人」溢出 */
@media(min-width:721px) and (max-width:1240px){
  .ov-kpi strong{font-size:21px;letter-spacing:-1px}
}
"""

idx = s.rfind('</style>')
if idx < 0:
    fails.append('CSS: 找不到 </style>')
else:
    s = s[:idx] + CSS + s[idx:]

# ───────────────────────── 写盘
if fails:
    print('FAILED (未写盘):')
    for f in fails:
        print('  -', f)
    raise SystemExit(1)

io.open(PATH, 'w', encoding='utf-8').write(s)

chk = io.open(PATH, encoding='utf-8').read()
# (实际出现次数, 期望次数)
checks = {
    '① sys-banner 已启用': (chk.count('class="sys-banner"'), 1),
    '① 旧脱敏文案已清除': (chk.count('员工姓名已脱敏 · 经营数值均为虚构'), 0),
    '① 旧黄条样式已清除': (chk.count('background:#fff4d6;border-bottom:1px solid #ecd28e'), 0),
    '②a label 允许换行': (chk.count('.kpi-tile label{display:block;font-size:12px;'
                                  'color:var(--muted);white-space:normal'), 1),
    '②a 旧的 kpi-tile label 已无 nowrap': (chk.count('.kpi-tile label{display:block;'
                                        'font-size:12px;color:var(--muted);'
                                        'white-space:nowrap'), 0),
    '②b sales-kpis 单列（.kpi-tile 无残留 + 覆盖块各 1）':
        (chk.count('.sales-kpis{grid-template-columns:minmax(0,1fr);gap:9px}'), 2),
    '③ 排班码 10.5px': (chk.count('.np-shift-cell{font-size:10.5px}'), 1),
    '③ 日期轴仅加深颜色（不放大字号）': (chk.count('.dc-axis i{color:#616A7C}'), 1),
    '③ 日期轴字号不再全局放大': (chk.count('.dc-axis i{font-size:9.5px'), 0),
    '中等屏 Hero 数字收缩规则': (chk.count('@media(min-width:721px) and (max-width:1240px)'), 1),
    '④ ai-entry 44px': (chk.count('.ai-entry{min-height:44px'), 1),
    '④ head-action 44px': (chk.count('.head-action{min-height:44px'), 1),
    '④ complete-btn 44px': (chk.count('.complete-btn{min-height:44px'), 1),
    '④ section-link 44px': (chk.count('.section-link{min-height:44px'), 1),
    '④b period 44px（可点击日期按钮）': (chk.count('.period{min-height:44px'), 1),
    '④b sales-close 44px': (chk.count('.sales-close{min-width:44px;min-height:44px}'), 1),
    '④b 月份页签 44px': (chk.count('.sales-month-tabs button{min-height:44px}'), 1),
    '④b 工具按钮 44px': (chk.count('.sales-month-tools button{width:44px;height:44px}'), 1),
    '④b sheet-close 44px': (chk.count('.sheet-close{min-width:44px;min-height:44px}'), 1),
    '④b sheet-tab 44px': (chk.count('.sheet-tab{min-height:44px}'), 1),
    '④b flow-head 折叠按钮 44px': (chk.count('.flow-head{min-height:44px}'), 1),
    '⑤ --muted 加深': (chk.count(':root{--muted:#616A7C}'), 1),
    '⑤ 日期轴颜色覆盖生效': (chk.count('.dc-axis i{color:#616A7C}'), 1),
    '⑤ 浅灰在搜索空状态已覆盖': (chk.count('.search-drop .none{color:#616A7C}'), 1),
    '⑤ 部门卡标签颜色+换行': (chk.count('.dc-metrics .dc-metric label{white-space:normal;'
                                          'line-height:1.3;color:#616A7C}'), 1),
    '⑤ 单位与状态标签加深': (chk.count('.dept-status{color:#616A7C}'), 1),
    '⑤ 单位 em 加深': (chk.count('.dc-metric strong em{color:#616A7C}'), 1),
    '⑤b 散落浅灰已清空': (sum(len(re.findall(r'color:' + g, chk, re.I)) for g in GRAYS), 0),
    '⑤b 替换处数（应为 25）': (gray_n, 25),
    '回退 ov-chip 字号（保持 10px 能放下）': (chk.count('.ov-kpi .ov-chip{font-size:11px}'), 0),
    'CSS 覆盖块已插入': (chk.count('看板 UI 优化：字号可读性'), 1),
}
bad = {k: v for k, v in checks.items() if v[0] != v[1]}
print('写入完成，%d bytes' % len(s))
for k, (got, want) in checks.items():
    print(('  OK  ' if got == want else '  BAD '), k, '→ 实际 %d / 期望 %d' % (got, want))
if bad:
    raise SystemExit(2)
print('ALL CHECKS PASSED')
