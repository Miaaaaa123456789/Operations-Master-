#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 J：把「本周至今」说明行从「待补」改为「本期」中性呈现"""
import io

PATH = 'index.html'
s = io.open(PATH, encoding='utf-8').read()
fails = []


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n == 0:
        fails.append('%s 未找到' % tag)
        print('  ✗ %-28s 未找到' % tag)
        return
    if n != expect:
        fails.append('%s 实际 %d 期望 %d' % (tag, n, expect))
    s = s.replace(old, new)
    print('  ✓ %-28s %3d 处' % (tag, n))


print('── J1. 两个渲染点加「本期」分支 ──')
OLD = ("const miss=m[2]===null||m[2]===undefined;"
       "if(miss)return`<div class=\"metric-row is-missing\">"
       "<div><label>${m[0]}</label><small>${m[4]||'线上表未填报'}</small></div>")
NEW = ("const miss=m[2]===null||m[2]===undefined;"
       "const cur=miss&&/^本周/.test(m[0]);"
       "if(cur)return`<div class=\"metric-row is-current\">"
       "<div><label>${m[0]}</label><small>${m[4]||''}</small></div>"
       "<div class=\"metric-num\"><span class=\"cur-tag\">本期</span></div></div>`;"
       "if(miss)return`<div class=\"metric-row is-missing\">"
       "<div><label>${m[0]}</label><small>${m[4]||'线上表未填报'}</small></div>")
rep(OLD, NEW, 'J1 渲染分支', 2)

print()
print('── J2. 补 CSS ──')
CSS_OLD = '.metric-row.is-missing strong{color:#C77A00;font-size:15px;font-weight:600}'
CSS_NEW = ('.metric-row.is-missing strong{color:#C77A00;font-size:15px;font-weight:600}'
           '\n    /* 「本周至今」说明行：中性蓝，不带「待补」语义 */'
           '\n    .metric-row.is-current{background:#F2F8FF;box-shadow:inset 0 0 0 1px rgba(0,102,204,.20)}'
           '\n    .metric-row.is-current label{color:#0A54C4}'
           '\n    .metric-row.is-current small{color:#3A5A80}'
           '\n    .metric-row.is-current .cur-tag{display:inline-block;padding:4px 10px;border-radius:999px;'
           'background:#E4F0FF;color:#0A54C4;font-size:12px;font-weight:800;white-space:nowrap}')
rep(CSS_OLD, CSS_NEW, 'J2 CSS')

io.open(PATH, 'w', encoding='utf-8').write(s)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
for k, v in [('is-current 渲染分支', chk.count('const cur=miss&&/^本周/.test(m[0])')),
             ('is-current CSS', chk.count('.metric-row.is-current{')),
             ('cur-tag CSS', chk.count('.metric-row.is-current .cur-tag'))]:
    print('  %-24s %d' % (k, v))
    if v == 0:
        fails.append(k)

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
