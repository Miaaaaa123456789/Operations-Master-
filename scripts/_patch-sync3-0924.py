#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看板同步 · 补丁 3：清理最后 6 处仍指向 9.13—9.19 的营收引用。"""
import io

PATH = 'index.html'
s = io.open(PATH, encoding='utf-8').read()
fails = []
log = []


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n != expect:
        fails.append('%s: 期望 %d 处，实际 %d 处' % (tag, expect, n))
        return
    s = s.replace(old, new)
    log.append((tag, n))


rep('<b>总收入 59.45 万</b>取营收日报（9.13—9.19 当日合计逐日加总，门诊 37.68 万 + 在院 21.77 万）',
    '<b>总收入 49.15 万</b>取营收日报（9.14—9.20 当日合计逐日加总，门诊 27.10 万 + 在院 22.05 万）',
    'heroSummary·营收口径')
rep('与营收日报 59.45 万相差 10.05 万',
    '与营收日报 49.15 万相差 0.25 万', '核验清单·差额')
rep('营收日报口径本周收入 <b>59.45 万</b> 另列',
    '营收日报口径本周收入 <b>49.15 万</b> 另列', '核验清单·另列')
rep("title:'本周总收入 59.45 万，但月度进度落后'",
    "title:'本周总收入 49.15 万，但月度进度落后'", 'AI 标题(月度)')
rep('本周（9.13—9.19）总收入 <span class="hl-key">59.45 万</span>'
    '（门诊 37.68 万 ＋ 在院 21.77 万），较上周 56 万',
    '本周（9.14—9.20）总收入 <span class="hl-key">49.15 万</span>'
    '（门诊 27.10 万 ＋ 在院 22.05 万），较上周 48.65 万', 'AI evidence')
rep('本周（9.13—9.19）逐日营业额：9.13/9.14 取逐日明细源表，9.15—9.19 取已核营收日报口径',
    '本周（9.14—9.20）逐日营业额：9.14 取逐日明细源表，9.15—9.20 取营收日报口径', 'JS 注释(前半)')
rep('合计 59.44 万（与 59.45 万的差额为四舍五入）',
    '合计 49.15 万（业主 2026-09-24 截图，9.16—9.22 逐日）', 'JS 注释(后半)')

if fails:
    print('FAILED（未写盘）：')
    for f in fails:
        print('  -', f)
    raise SystemExit(1)
io.open(PATH, 'w', encoding='utf-8').write(s)
print('补丁 3 完成，%d bytes' % len(s))
for tag, n in log:
    print('  OK  %-24s %d 处' % (tag, n))
chk = io.open(PATH, encoding='utf-8').read()
print('残留：59.45=%d 37.68=%d 21.77=%d' % (chk.count('59.45'), chk.count('37.68'), chk.count('21.77')))
