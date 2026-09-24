#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 A：修复合并进来的新代码缺陷 + 顶层时间接口 + 索引项"""
import io

fails = []


def edit(path, pairs, tag):
    s = io.open(path, encoding='utf-8').read()
    for old, new, name, expect in pairs:
        n = s.count(old)
        if n == 0:
            fails.append('%s/%s 未找到' % (tag, name))
            print('  ✗ %-34s 未找到' % name)
            continue
        if expect is not None and n != expect:
            fails.append('%s/%s 实际 %d 期望 %d' % (tag, name, n, expect))
        s = s.replace(old, new)
        print('  ✓ %-34s %3d 处' % (name, n))
    io.open(path, 'w', encoding='utf-8').write(s)


print('── A. 修复 final-enhancements.js 插入锚点 bug ──')
# insertBefore(el, anchor) 要求 anchor 是 root 的直接子元素；
# .mkt-detail-grid 的父级是 .mkt-content，故改为在 anchor 自己的父级里插入
edit('final-enhancements.js', [
    ("    const anchor=root.querySelector('.mkt-detail-grid')||root.lastElementChild;\n"
     "    const el=document.createElement('section'); el.className='finance-board'; el.innerHTML=`",
     "    const anchor=root.querySelector('.mkt-detail-grid')||root.lastElementChild;\n"
     "    const parent=anchor?anchor.parentElement:root;\n"
     "    const el=document.createElement('section'); el.className='finance-board'; el.innerHTML=`",
     'FA1 anchor 父级', 1),
    ("    root.insertBefore(el,anchor);\n  }",
     "    if(parent)parent.insertBefore(el,anchor);else root.appendChild(el);\n  }",
     'FA2 改为父级插入', 1),
    ("  function boot(){addSidebar();addFinance();ensureModal();bindDepts()}",
     "  function boot(){try{addSidebar()}catch(e){console.warn('side-pulse',e)}\n"
     "                try{addFinance()}catch(e){console.warn('finance',e)}\n"
     "                try{ensureModal()}catch(e){console.warn('modal',e)}\n"
     "                try{bindDepts()}catch(e){console.warn('bindDepts',e)}}",
     'FA3 各步独立容错', 1),
], 'final-enhancements.js')

print()
print('── B. 同类隐患：revision-v6 / marketing-detail 的 boot 容错 ──')
edit('revision-v6.js', [
    ("  function boot(){reorderMarketing();enrichOverview();restoreMarketing()}",
     "  function boot(){try{reorderMarketing()}catch(e){console.warn('reorderMkt',e)}\n"
     "                try{enrichOverview()}catch(e){console.warn('enrichOverview',e)}\n"
     "                try{restoreMarketing()}catch(e){console.warn('restoreMkt',e)}}",
     'RV1 boot 容错', 1),
], 'revision-v6.js')

print()
print('── C. index.html：顶层时间接口 + 新增区块入索引 ──')
edit('index.html', [
    ('id="periodBtn">数据更新至 2026年9月22日<',
     'id="periodBtn">数据更新至 2026年9月24日<',
     'I1 periodBtn', 1),
    ("window.OPS_SNAPSHOT.periodLabel)||'数据更新至 2026年9月22日'",
     "window.OPS_SNAPSHOT.periodLabel)||'数据更新至 2026年9月24日'",
     'I2 JS 兜底 periodLabel', 2),
    ("periodLabel:'数据更新至 2026年9月22日'",
     "periodLabel:'数据更新至 2026年9月24日'",
     'I3 快照 periodLabel', 1),
    ("snapshotAt:'2026-09-24T02:20:00+08:00'",
     "snapshotAt:'2026-09-24T13:30:00+08:00'",
     'I4 snapshotAt', 1),
    ("title=\"本页主口径：本周 9.21—9.27（进行中 · 数据截至 9.22）\"",
     "title=\"本页主口径：本周 9.21—9.27（进行中 · 数据截至 9.23，营收 9.22）\"",
     'I5 rangeChip title', 1),
    ("    {t:'排名数据治理决策（月内动态、月末正式）',k:'版块',f:function(){jump('#rankGovernance')}},",
     "    {t:'排名数据治理决策（月内动态、月末正式）',k:'版块',f:function(){jump('#rankGovernance')}},\n"
     "    {t:'经营问题总览（跨部门链路诊断）',k:'版块',f:function(){jump('#decisionCore')}},",
     'I6 新增 decisionCore 索引', 1),
], 'index.html')

print()
print('── 回读校验 ──')
chk = io.open('index.html', encoding='utf-8').read()
for k, v in [('数据更新至 2026年9月24日', chk.count('数据更新至 2026年9月24日')),
             ('残留 2026年9月22日', chk.count('数据更新至 2026年9月22日')),
             ('decisionCore 索引', chk.count("jump('#decisionCore')"))]:
    print('  %-28s %d' % (k, v))
if chk.count('数据更新至 2026年9月22日'):
    fails.append('旧 periodLabel 未清')
fe = io.open('final-enhancements.js', encoding='utf-8').read()
print('  %-28s %d' % ('FA 父级插入已生效', fe.count('if(parent)parent.insertBefore(el,anchor)')))

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
