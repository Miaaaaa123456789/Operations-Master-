#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 F：修复旧营销渲染函数在新版面板下的空引用 + 入口文案与目标卡 chip"""
import io

PATH = 'index.html'
s = io.open(PATH, encoding='utf-8').read()
fails = []


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n == 0:
        fails.append('%s 未找到' % tag)
        print('  ✗ %-32s 未找到' % tag)
        return
    if n != expect:
        fails.append('%s 实际 %d 期望 %d' % (tag, n, expect))
    s = s.replace(old, new)
    print('  ✓ %-32s %3d 处' % (tag, n))


print('── F1. selectSalesMonth 空引用守卫 ──')
rep("      const datebar=document.querySelector('.sales-datebar'),"
    "snapshot=document.getElementById('monthSnapshot'),"
    "kpis=document.querySelector('.sales-kpis'),main=document.querySelector('.sales-main');\n"
    "      if(month===9){",
    "      const datebar=document.querySelector('.sales-datebar'),"
    "snapshot=document.getElementById('monthSnapshot'),"
    "kpis=document.querySelector('.sales-kpis'),main=document.querySelector('.sales-main');\n"
    "      /* 新版营销面板（mkt-v2）已替换旧 .sales-shell 结构，旧渲染目标不存在时安全跳过 */\n"
    "      if(!datebar||!snapshot||!kpis||!main){selectedSalesMonth=month;return}\n"
    "      if(month===9){",
    'F1 守卫')

print()
print('── F2. openSales 容错 + 月度锚点守卫 ──')
rep("function openSales(focus){if(typeof closeSheet==='function')closeSheet();"
    "salesWorkspace.classList.add('show');document.body.style.overflow='hidden';"
    "selectSalesMonth(9);salesWorkspace.scrollTop=0;"
    "if(focus==='monthly')setTimeout(()=>document.getElementById('monthlyHistory')"
    ".scrollIntoView({behavior:'smooth',block:'start'}),180)}",
    "function openSales(focus){if(typeof closeSheet==='function')closeSheet();"
    "salesWorkspace.classList.add('show');document.body.style.overflow='hidden';"
    "try{selectSalesMonth(9)}catch(e){}salesWorkspace.scrollTop=0;"
    "if(focus==='monthly'){const h=document.getElementById('monthlyHistory');"
    "if(h)setTimeout(()=>h.scrollIntoView({behavior:'smooth',block:'start'}),180)}}",
    'F2 openSales')

print()
print('── F3. 入口按钮文案 ──')
rep("b.textContent='营业分析　9.13—9.19'",
    "b.textContent='营业分析　本周 9.21—9.27'", 'F3a 侧栏入口')
rep("b.innerHTML='营销分析 <span>9月上周</span>'",
    "b.innerHTML='营销分析 <span>本周至今</span>'", 'F3b 顶栏入口')

print()
print('── F4. 营收目标卡 chip（对应当前显示的月度累计 153.89 万）──')
rep('<h2>9月营收目标进度</h2><span class="ov-chip">9.13—9.19 <i>⌄</i></span>',
    '<h2>9月营收目标进度</h2><span class="ov-chip">9月1日—9月22日 <i>⌄</i></span>',
    'F4 目标卡 chip')

io.open(PATH, 'w', encoding='utf-8').write(s)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
for k, v in [('守卫已插入', chk.count('if(!datebar||!snapshot||!kpis||!main){selectedSalesMonth=month;return}')),
             ('openSales try', chk.count('try{selectSalesMonth(9)}catch(e){}')),
             ('侧栏入口', chk.count('营业分析　本周 9.21—9.27')),
             ('顶栏入口', chk.count('营销分析 <span>本周至今</span>')),
             ('目标卡 chip', chk.count('9月1日—9月22日 <i>⌄</i>')),
             ('残留 9月上周', chk.count('9月上周')),
             ('残留 营业分析　9.13', chk.count('营业分析　9.13'))]:
    print('  %-24s %d' % (k, v))
for bad in ['9月上周', '营业分析　9.13']:
    if chk.count(bad):
        fails.append('残留 %s' % bad)

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
