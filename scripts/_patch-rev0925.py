#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步 9.25 营收日报（来自 psyc.harness 的 hospital-operations-dashboard）。

数据来源：GitHub psyc.harness @ bdc215f 的 september-revenue-data.js
交叉验证：门诊+在院=当日合计、累计逐日递推 → 全部自洽
  · 9.25  门诊 69642.38 + 在院 31545.11 = 101187.49 ✓
  · 累计  1678790.99 + 101187.49 = 1779978.48 ✓

同时补齐 9.15—9.17 缺失的「初诊/复诊/在院/入院/出院」（我们原先记 null）。
⚠ 9.14 出院两版不一致（本仓 1 / GitHub 4），不擅自改，入核验清单。
"""
import io, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, 'data-import.js')
s = io.open(P, encoding='utf-8').read()
before = len(s)
fails = []


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n != expect:
        fails.append('%-46s 匹配 %d（期望 %d）' % (tag, n, expect))
        return
    s = s.replace(old, new)


# ① 补齐 9.15—9.17 的人数（金额原本就有，只补后 5 位）
rep("'2026-09-15': [34846.27, 43388.86, null, null, null, null, null],",
    "'2026-09-15': [34846.27, 43388.86, 8, 10, 25, 1, 0],", '① 9.15 人数')
rep("'2026-09-16': [13958.85, 28288.75, null, null, null, null, null],",
    "'2026-09-16': [13958.85, 28288.75, 2, 13, 25, 1, 1],", '① 9.16 人数')
rep("'2026-09-17': [34398.72, 28935.61, null, null, null, null, null],",
    "'2026-09-17': [34398.72, 28935.61, 7, 13, 26, 1, 0],", '① 9.17 人数')

# ② 新增 9.25（营收已到 9.25）
rep("    '2026-09-24': [38082.09, 39383.78, 6, 33, 30, 4, 2]\n",
    "    '2026-09-24': [38082.09, 39383.78, 6, 33, 30, 4, 2],\n"
    "    '2026-09-25': [69642.38, 31545.11, 3, 51, 31, 3, 2]\n",
    '② 新增 9.25')

# ③ 种子注释里的累计校验值同步
rep("· 校验：9.1—9.24 累计 = 1,678,790.99 元（167.88 万），与源表「当月累计收入」一致",
    "· 校验：9.1—9.25 累计 = 1,779,978.48 元（178.00 万），与源表「当月累计收入」一致",
    '③ 注释累计值')

# ④ 日期常量：营收到 9.25，抓取日仍 9.26
rep("var SOURCE_CUTOFF = '2026-09-26';   // 其他数据源（客服/心理/管家/团体）的共同截止日",
    "var SOURCE_CUTOFF = '2026-09-26';   // 其他数据源（客服/心理/管家/团体）的共同截止日",
    '④ SOURCE_CUTOFF 不变', 1)   # 显式保留，避免后续误改

if fails:
    print('✗ 未按预期匹配：')
    for f in fails:
        print('   -', f)
    sys.exit(1)

io.open(P, 'w', encoding='utf-8').write(s)
print('✓ 已写 data-import.js（%d → %d B，%+d）' % (before, len(s), len(s) - before))
