#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把外部模块里的旧周排名数据同步为「本周 9.21—9.27」。"""
import io, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RK = json.load(io.open(os.path.join(REPO, 'data', 'rankings.json'), encoding='utf-8'))
M = RK['depts']['marketing']['metrics']
fails = []


def fix(path, pairs):
    p = os.path.join(REPO, path)
    s = io.open(p, encoding='utf-8').read()
    for old, new, tag in pairs:
        n = s.count(old)
        if n != 1:
            fails.append('%-24s %-30s 匹配 %d' % (path, tag, n))
            continue
        s = s.replace(old, new)
    io.open(p, 'w', encoding='utf-8').write(s)


# ── 本周管家逐人（生成排名行 HTML）
def rows_html(items):
    out = []
    for i, (nm, n, zi, note) in enumerate(items, 1):
        rate = (zi / n * 100) if n else 0
        out.append('<div class="rank-row"><i>%d</i><div><b>%s</b><small>%s</small></div><strong>%d条</strong></div>'
                   % (i, nm, note, n))
    return ''.join(out)


ROWS = rows_html([
    ('朱婧', 17, 2, '有效对接 17 条 · 检查 10 · 转住院 11.8%'),
    ('金林', 16, 7, '有效对接 16 条 · 物理 9 · 转住院 43.8%（最高）'),
    ('利娟', 14, 2, '有效对接 14 条 · 检查 4 · 转住院 14.3%'),
    ('菲菲', 0, 0, '本周无新增对接记录'),
    ('国威', 0, 0, '本周无新增对接记录'),
])

NOTE = ('<div class="rank-note rank-ok">本周（9.21—9.27）有效对接 <b>%d 条</b>、转住院 <b>%d 人（%.1f%%）</b>；'
        '上周 9.14—9.20 为 %d 条 / %d 人（%.1f%%），对接环比 <b>%+.1f%%</b>。'
        '个人样本仅十余条，率值只作趋势参考，不作绩效排序。</div>'
        % (M['deal'], M['admit'], M['rate'], M['dealPrev'], M['admitPrev'], M['ratePrev'], M['delta']))

# ── revision-v6.js
fix('revision-v6.js', [
    ("subtitle:'业主汇总 78 条 / 逐条 80 条 · 9.14—9.20'",
     "subtitle:'本周 9.21—9.27 逐条 %d 条 · 上周 80 条'" % M['deal'], 'butler subtitle'),
    ("metrics:[['有效对接','80条'],['转住院','14人'],['转住院率','17.5%'],['初诊 / 复诊','21 / 57']]",
     "metrics:[['有效对接','%d条'],['转住院','%d人'],['转住院率','%.1f%%'],['本周无新增','菲菲 / 国威']]"
     % (M['deal'], M['admit'], M['rate']), 'butler metrics'),
])

# butler 的 rank-note + rank-list 整体替换
p = os.path.join(REPO, 'revision-v6.js')
s = io.open(p, encoding='utf-8').read()
old_head = '<div class="rank-note rank-ok">看板按逐条记录 80 条呈现'
i = s.find(old_head)
if i < 0:
    fails.append('revision-v6.js butler html 未找到')
else:
    j = s.find('</div>`}', i)
    if j < 0:
        fails.append('revision-v6.js butler html 结束未找到')
    else:
        s = s[:i] + NOTE + '<div class="rank-list">' + ROWS + '</div>' + s[j + len('</div>'):]
        io.open(p, 'w', encoding='utf-8').write(s)

fix('revision-v6.js', [
    ("<label>有效对接</label><strong>80<em>条</em></strong>",
     "<label>有效对接</label><strong>%d<em>条</em></strong>" % M['deal'], 'restore card 对接'),
    ("<label>转住院率</label><strong>17.5<em>%</em></strong>",
     "<label>转住院率</label><strong>%.1f<em>%%</em></strong>" % M['rate'], 'restore card 率'),
])

# ── marketing-detail.js
fix('marketing-detail.js', [
    ("<span class=\"dc-metric\"><label>有效对接</label><strong>80<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label><strong>17.5<em>%</em></strong></span>",
     "<span class=\"dc-metric\"><label>有效对接</label><strong>%d<em>条</em></strong></span><span class=\"dc-metric\"><label>转住院率</label><strong>%.1f<em>%%</em></strong></span>"
     % (M['deal'], M['rate']), '子部门卡'),
    ("metrics:[['有效对接','80条'],['转住院','14人'],['转住院率','17.5%'],['心理咨询转介','19条']]",
     "metrics:[['有效对接','%d条'],['转住院','%d人'],['转住院率','%.1f%%'],['心理咨询服务','11人次']]"
     % (M['deal'], M['admit'], M['rate']), 'butler metrics'),
    ("[['总量持平，结构换手','检查58条基本持平，物理治疗21条和住院14人均增加，心理咨询转介减少4条。']",
     "[['总量回落，但转化率上升','本周对接 %d 条（上周 80 条，%+.1f%%），转住院 %d 人、转化率 %.1f%%（上周 %.1f%%）。"
     "金林 43.8%% 最高、朱婧 11.8%%、利娟 14.3%%；菲菲与国威本周无新增。']"
     % (M['deal'], M['delta'], M['admit'], M['rate'], M['ratePrev']), 'butler advice 1'),
])

if fails:
    print('补丁未通过：')
    for f in fails:
        print('  ✗', f)
    sys.exit(1)
print('✓ 外部模块排名数据已同步本周')
