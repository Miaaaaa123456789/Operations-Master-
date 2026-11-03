#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-11-03 复核补丁：修复 11-02 交互会话引入的 2 个未闭合 div。
① nursingPerfPane 在 diagnosisPane 前未闭合 → diagnosisPane 被嵌进 display:none 的
   nursingPerfPane 里，「AI诊断」页签线上不可见（真缺陷）。
② sheet-body 在 </aside> 前未闭合。
预期：div 564/562 → 564/564。"""
P = 'index.html'
s = open(P, encoding='utf-8').read()
fails = []
def rep(o, n, tag, expect=1):
    global s
    c = s.count(o)
    if c != expect:
        fails.append((tag, c, expect)); print('SKIP', tag, 'count=', c); return
    s = s.replace(o, n); print('OK', tag)

# Fix A: 在 diagnosisPane 前补 nursingPerfPane 的闭合
rep('正文仍为 10.5—10.11 存档。</div></div><div class="sheet-pane" id="diagnosisPane">',
    '正文仍为 10.5—10.11 存档。</div></div></div><div class="sheet-pane" id="diagnosisPane">',
    'A-nursingPerfPane-close')
# Fix B: 在 </aside> 前补 sheet-body 的闭合
rep('<div class="diagnosis" id="diagnosisList"></div></div></div></aside>',
    '<div class="diagnosis" id="diagnosisList"></div></div></div></div></aside>',
    'B-sheet-body-close')

open(P, 'w', encoding='utf-8').write(s)
print('失败:', fails if fails else '无')
# 写盘后回读验证
s2 = open(P, encoding='utf-8').read()
print('回读 div:', s2.count('<div'), s2.count('</div>'))
print('回读 A 新值:', s2.count('存档。</div></div></div><div class="sheet-pane" id="diagnosisPane">'))
print('回读 B 新值:', s2.count('id="diagnosisList"></div></div></div></div></aside>'))
