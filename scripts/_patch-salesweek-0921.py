#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""营销分析面板：时间口径切 9.14—9.20 + 营业总额改 49.4 万（业主 2026-09-21 指示）

业主原话：
  「营销分析时间接口改为9.14-9.20本周，也就是营利总额改为四十九万多那条」
  「都按9.19口径。其它数值不变」

数据来源：49.4 万 = 《特别行动小组汇报表》医生组表头「总收入」（2026-09-21 09:12 抓取），
          科主任叙述同口径：第 2 周（9.7—9.13）56 万 → 第 3 周（9.14—9.20）49.4 万，−11.8%。

改动范围（严格限定在 #salesWorkspace 面板内）：
  A. 周标签 9.13—9.19 → 9.14—9.20（datebar HTML + JS 重置、两个 section 副标题、口径说明）
  B. 营业总额 hero 卡 59.45 万 → 49.4 万，并同步该卡自身的日均与环比（同一指标，必须自洽）
  C. 其余数值一律不动（门诊/住院拆分、每日柱状图、月度累计、周对比卡、周末贡献、AI 文本）
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


# ═══════════════ A. 时间接口：周标签 9.13—9.19 → 9.14—9.20 ═══════════════
# A1 datebar 主行（HTML）
rep('<h2>9月1日—9月19日</h2>',
    '<h2>9月1日—9月20日</h2>',
    'A1 datebar 主行(HTML)')

# A2 datebar 周口径行（HTML）
rep('<p>周口径：本周 9.13—9.19 · 上周 9.7—9.13（同为完整 7 天）</p>',
    '<p>周口径：本周 9.14—9.20 · 上周 9.7—9.13（同为完整 7 天）</p>',
    'A2 datebar 周口径(HTML)')

# A3 datebar 主行 + 周口径行（JS 重置，切回 9 月时执行）
rep("datebar.querySelector('h2').textContent='9月1日—9月19日'",
    "datebar.querySelector('h2').textContent='9月1日—9月20日'",
    'A3 datebar 主行(JS)')
rep("datebar.querySelector('p').textContent='周口径：本周 9.13—9.19 · 上周 9.7—9.13（同为完整 7 天）；旧口径的第一周 9.1—9.6 只有 6 天，不并入本周对比'",
    "datebar.querySelector('p').textContent='周口径：本周 9.14—9.20 · 上周 9.7—9.13（同为完整 7 天）；旧口径的第一周 9.1—9.6 只有 6 天，不并入本周对比'",
    'A4 datebar 周口径(JS)')

# A5「本周与上周到底差在哪」副标题
rep('本周 9.13—9.19 相对上周 9.7—9.13（同为 7 天）',
    '本周 9.14—9.20 相对上周 9.7—9.13（同为 7 天）',
    'A5 周对比副标题')

# A6「既往几个月销售走势」副标题
rep('9 月本周（9.13—9.19）逐日已并入上方柱状图',
    '9 月本周（9.14—9.20）逐日已并入上方柱状图',
    'A6 月度走势副标题')

# A7 口径说明：周期改 9.14—9.20；逐日明细仍为 9.13—9.19，据实说明（不掩盖）
rep('本周按自然周 9.13—9.19（7 天）计算，与上周 9.7—9.13 同为 7 天；'
    '逐日营业额中 9.13／9.14 取逐日明细源表，9.15—9.19 取已核营收日报口径，'
    '7 天合计 59.44 万（页面显示 59.45 万，差额为四舍五入）。',
    '本周按自然周 9.14—9.20（7 天）计算，与上周 9.7—9.13 同为 7 天。'
    '「本周营业总额 49.4 万」取《特别行动小组汇报表》医生组表头总收入（科主任口径，'
    '上周 56 万 → 本周 49.4 万，−11.8%）。'
    '下方逐日柱状图与门诊／住院拆分仍为营收日报口径的 9.13—9.19（9.13／9.14 取逐日明细源表，'
    '9.15—9.19 取已核营收日报），7 天合计 59.44 万（页面显示 59.45 万，差额为四舍五入）——'
    '与 49.4 万分属两个口径，不互相校验。',
    'A7 口径说明')

# ═══════════════ B. 营业总额 hero 卡：59.45 → 49.4 万 ═══════════════
rep('<article class="sw-card"><label><i class="sw-ico">营</i>本周营业总额</label>'
    '<strong>¥59.45万</strong>'
    '<small>7 天合计 · 日均 ¥8.49 万 · 较上周 <b class="sales-positive">+6.2%</b></small></article>',
    '<article class="sw-card"><label><i class="sw-ico">营</i>本周营业总额</label>'
    '<strong>¥49.4万</strong>'
    '<small>7 天合计 · 日均 ¥7.06 万 · 较上周 <b class="sales-negative">−11.8%</b>'
    ' · 医生组总收入口径</small></article>',
    'B1 营业总额 hero 卡')


if fails:
    print('FAILED (未写盘):')
    for f in fails:
        print('  -', f)
    raise SystemExit(1)

io.open(PATH, 'w', encoding='utf-8').write(s)

chk = io.open(PATH, encoding='utf-8').read()
i = chk.find('id="salesWorkspace"')
j = chk.find('</aside>', i)
seg = chk[i:j]

checks = {
    'A1 datebar 主行为 9.20': (seg.count('9月1日—9月20日'), 1),
    'A1 旧主行已清除': (seg.count('9月1日—9月19日'), 0),
    'A2/A4 本周 9.14—9.20 两处（HTML+JS）': (seg.count('本周 9.14—9.20'), 2),
    'A2 旧「本周 9.13—9.19」在 datebar 已清除': (seg.count('周口径：本周 9.13—9.19'), 0),
    'A5 周对比副标题': (seg.count('本周 9.14—9.20 相对上周'), 1),
    'A6 月度走势副标题': (seg.count('9 月本周（9.14—9.20）'), 1),
    'A7 口径说明周期': (seg.count('本周按自然周 9.14—9.20（7 天）计算'), 1),
    'B1 营业总额 =49.4 万': (seg.count('<strong>¥49.4万</strong>'), 1),
    'B1 旧 59.45 万 hero 已清除': (seg.count('<strong>¥59.45万</strong>'), 0),
    'B1 日均同步 7.06': (seg.count('日均 ¥7.06 万'), 1),
    'B1 环比同步 −11.8%': (seg.count('sales-negative">−11.8%</b>'), 1),
    'B1 口径标注': (seg.count('医生组总收入口径'), 1),
    # —— 按业主指示「其它数值不变」，以下应保持原样 ——
    'C 门诊 37.68 万未动': (seg.count('¥37.68万'), 1),
    'C 住院 21.77 万未动': (seg.count('¥21.77万'), 1),
    'C 周对比卡 59.45 万未动': (seg.count('<span>本周<b>59.45万</b></span>'), 1),
    'C 周末贡献 30.17/59.45 未动': (seg.count('30.17万 / 59.45万'), 1),
    # 以下两项在 JS 段（不在 #salesWorkspace HTML 内），改用全文校验
    'C 每日柱状图仍是 9.13 起（JS）': (chk.count("['9.13',16.40,'周日']"), 1),
    'C 月度累计 136.93 面板内未动': (seg.count('136.93'), 5),
    'C 月度累计 136.93 全文未动': (chk.count('136.93'), 14),
    'C 面板内 49.4（hero 1 + 口径说明 3）': (seg.count('49.4'), 4),
}
bad = {k: v for k, v in checks.items() if v[0] != v[1]}
print('写入完成，%d bytes' % len(s))
for k, (got, want) in checks.items():
    print(('  OK  ' if got == want else '  BAD '), k, '→ 实际 %d / 期望 %d' % (got, want))
if bad:
    raise SystemExit(2)
print('ALL CHECKS PASSED')
