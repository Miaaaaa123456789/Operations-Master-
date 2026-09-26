#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部模块的 9.26 数据同步（管家 47→63、心理 25→37、时间戳 9.25→9.26）。

为什么单独一个脚本：本项目 index.html 与 6 个外部 .js 各存一份同数据文案，
只改 index.html 会让「子部门卡 / 营销返回卡」与主面板互相矛盾。
"""
import io, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RK = json.load(io.open(os.path.join(REPO, 'data', 'rankings.json'), encoding='utf-8'))
mk = RK['depts']['marketing']['metrics']
ps = RK['depts']['psychology']['metrics']
DEAL, ADMIT, RATE = mk['deal'], mk['admit'], '%.1f' % mk['rate']
RATE_PREV = '%.1f' % mk['ratePrev']
MDELTA = '%+.1f' % mk['delta']
CONTACT, ADVICE = ps['contact'], ps['advice']

fails = []


def patch(fname, pairs):
    p = os.path.join(REPO, fname)
    s = io.open(p, encoding='utf-8').read()
    before = len(s)
    ok = 0
    for old, new, tag, expect in pairs:
        n = s.count(old)
        if n != expect:
            fails.append('%-22s %-34s 匹配 %d（期望 %d）' % (fname, tag, n, expect))
            continue
        s = s.replace(old, new)
        ok += 1
    if ok == len(pairs):
        io.open(p, 'w', encoding='utf-8').write(s)
        print('  ✓ %-22s %d 处（%+d B）' % (fname, ok, len(s) - before))
    else:
        print('  ✗ %-22s 仅 %d/%d 处，未写' % (fname, ok, len(pairs)))


# ─────────────── revision-v6.js（营销返回卡 + 管家子面板）
patch('revision-v6.js', [
    ("subtitle:'本周 9.21—9.27 逐条 47 条 · 上周 80 条'",
     "subtitle:'本周 9.21—9.26 逐条 %d 条 · 上周 80 条'" % DEAL,
     'subtitle', 1),
    ("metrics:[['有效对接','47条'],['转住院','11人'],['转住院率','23.4%'],['本周无新增','菲菲 / 国威']]",
     "metrics:[['有效对接','%d条'],['转住院','%d人'],['转住院率','%s%%'],['本周无新增','菲菲 / 国威']]"
     % (DEAL, ADMIT, RATE),
     'metrics', 1),
    ("<div class=\"rank-note rank-ok\">本周（9.21—9.27）有效对接 <b>47 条</b>、转住院 <b>11 人（23.4%）</b>；上周 9.14—9.20 为 80 条 / 14 人（17.5%），对接环比 <b>-41.2%</b>。",
     "<div class=\"rank-note rank-ok\">本周（9.21—9.26）有效对接 <b>%d 条</b>、转住院 <b>%d 人（%s%%）</b>；上周 9.14—9.20 为 80 条 / 14 人（%s%%），对接环比 <b>%s%%</b>。"
     % (DEAL, ADMIT, RATE, RATE_PREV, MDELTA),
     'rank-note', 1),
    ("<label>有效对接</label><strong>47<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label><strong>23.4<em>%</em></strong>",
     "<label>有效对接</label><strong>%d<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label><strong>%s<em>%%</em></strong>"
     % (DEAL, RATE),
     '返回卡指标', 1),
    # 管家三行排名
    ("<small>有效对接 17 条 · 检查 10 · 转住院 11.8%</small></div><strong>17条</strong>",
     "<small>有效对接 26 条 · 检查 20 · 转住院 11.5%</small></div><strong>26条</strong>",
     '朱婧行', 1),
    ("<small>有效对接 16 条 · 物理 9 · 转住院 43.8%（最高）</small></div><strong>16条</strong>",
     "<small>有效对接 24 条 · 物理 9 · 转住院 29.2%（最高）</small></div><strong>24条</strong>",
     '金林行', 1),
    ("<small>有效对接 14 条 · 检查 4 · 转住院 14.3%</small></div><strong>14条</strong>",
     "<small>有效对接 13 条 · 检查 5 · 转住院 23.1%</small></div><strong>13条</strong>",
     '利娟行', 1),
    # 三行顺序：原 朱婧1/金林2/利娟3 → 现 朱婧26/金林24/利娟13，顺序不变
    ("<i>2</i><div><b>金林</b>", "<i>2</i><div><b>金林</b>", '金林序号(不变)', 1),
])

# ─────────────── marketing-detail.js（子部门卡）
patch('marketing-detail.js', [
    ("['有效对接','47条'],['转住院','11人'],['转住院率','23.4%'],['心理咨询服务','11人次']",
     "['有效对接','%d条'],['转住院','%d人'],['转住院率','%s%%'],['心理咨询服务','15人次']"
     % (DEAL, ADMIT, RATE),
     '管家指标', 1),
    ("['总量回落，但转化率上升','本周对接 47 条（上周 80 条，-41.2%），转住院 11 人、转化率 23.4%（上周 17.5%）。金林 43.8% 最高、朱婧 11.8%、利娟 14.3%；菲菲与国威本周无新增。']",
     "['对接回落但转化率上升','本周对接 %d 条（上周 80 条，%s%%），转住院 %d 人、转化率 %s%%（上周 %s%%）。金林 29.2%% 最高、利娟 23.1%%、朱婧 11.5%%；菲菲与国威本周无新增。']"
     % (DEAL, MDELTA, ADMIT, RATE, RATE_PREV),
     '管家建议', 1),
    ("'数据更新至 2026年9月25日 · 独立部门经营模块'",
     "'数据更新至 2026年9月26日 · 独立部门经营模块'",
     '时间戳', 1),
    ("<label>有效对接</label><strong>47<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label><strong>23.4<em>%</em></strong>",
     "<label>有效对接</label><strong>%d<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label><strong>%s<em>%%</em></strong>"
     % (DEAL, RATE),
     '返回卡指标', 1),
])

# ─────────────── marketing-redesign.js（口径行）
patch('marketing-redesign.js', [
    ("口径：本周至今为 9.21—9.27（数据截至 9.23，营收日报至 9.22）",
     "口径：本周至今为 9.21—9.27（各源数据截至 9.26，营收日报至 9.24）",
     '口径行', 1),
    ("<span>剩余天数</span><b>8天</b>", "<span>剩余天数</span><b>6天</b>", '剩余天数', 1),
])

# ─────────────── business-analysis.js（经营问题总览时间戳）
patch('business-analysis.js', [
    ("<span class=\"dc-scope\">本周 9.21—9.27 · 数据截至 9.24（营收 9.22）</span>",
     "<span class=\"dc-scope\">本周 9.21—9.27 · 数据截至 9.26（营收 9.24）</span>",
     'dc-scope', 1),
])

# ─────────────── final-enhancements.js
patch('final-enhancements.js', [
    ("<span class=\"finance-tag\">数据截至 9月24日（营收 9月22日）</span>",
     "<span class=\"finance-tag\">数据截至 9月26日（营收 9月24日）</span>",
     'finance-tag', 1),
])

if fails:
    print('\n✗ 有 %d 处未按预期匹配：' % len(fails))
    for f in fails:
        print('   -', f)
    sys.exit(1)
print('\n✓ 外部模块同步完成')
