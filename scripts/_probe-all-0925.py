#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""5 个在线表的全量数据勘探（截至 2026-09-25）"""
import json
import re
import subprocess
from collections import Counter, defaultdict

CLI = '/Users/opp/.local/bin/kdocs-cli'
URL_MAIN = 'https://www.kdocs.cn/l/cbwp2cvTiFyK'
URL_PSY = 'https://www.kdocs.cn/l/cgd3nVre7qWs'
URL_VISIT = 'https://www.kdocs.cn/l/coL1GfCvA0an'
URL_GJ = 'https://www.kdocs.cn/l/ctlu8ktnEwi8'
URL_SVC = 'https://www.kdocs.cn/l/cuOhExpV6n29'


def call(tool, params):
    r = subprocess.run([CLI, 'call', tool, json.dumps(params, ensure_ascii=False)],
                       capture_output=True, text=True)
    out = r.stdout or ''
    i = out.find('{')
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(out[i:])[0]
    except Exception:
        return None


def grid(url, sid, rf, rt, cf, co):
    """返回 {row: {col: text}}"""
    d = call('sheet.get_range_data', {'url': url, 'worksheet_id': sid,
             'range': {'rowFrom': rf, 'rowTo': rt, 'colFrom': cf, 'colTo': co}})
    if not d:
        return {}
    rd = ((d.get('data') or {}).get('detail') or {}).get('rangeData') or []
    rows = {}
    for c in rd:
        t = (c.get('cellText') or '').strip()
        if t:
            rows.setdefault(c.get('originRow'), {})[c.get('originCol')] = t
    return rows


def sec(t):
    print('\n' + '█' * 74)
    print('  ' + t)
    print('█' * 74)


# ══════════════════ ① 主表
sec('① 特别行动小组汇报表')
for sid, nm in [(3, '医生组'), (4, '护理组'), (5, '心理咨询组'), (6, '客服服务部'), (8, '营销中心')]:
    g = grid(URL_MAIN, sid, 0, 20, 0, 20)
    print('\n── %s (id=%d)' % (nm, sid))
    for r in sorted(g):
        print('   r%-2d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:250]))

# ══════════════════ ② 心理 V4
sec('② 心理V4管理表 — 咨询师每日简报（id=11）近 30 行')
g = grid(URL_PSY, 11, 0, 40, 0, 16)
for r in sorted(g):
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:230]))

sec('② 心理V4 — 主任日报（id=9）')
g = grid(URL_PSY, 9, 0, 40, 0, 16)
for r in sorted(g):
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:230]))

sec('② 心理V4 — 团队查房日报（id=5）末尾 20 行')
g = grid(URL_PSY, 5, 380, 403, 0, 16)
for r in sorted(g):
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:230]))

# ══════════════════ ③ 心理科来访数量（前三个表）
sec('③ 心理科来访数量 — 团体治疗登记（id=5）末尾 25 行')
g = grid(URL_VISIT, 5, 145, 171, 0, 11)
for r in sorted(g):
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:220]))

sec('③ 课程排班（id=3）')
g = grid(URL_VISIT, 3, 0, 30, 0, 77)
for r in sorted(g):
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:250]))

sec('③ 新-排班（id=19）前 25 行')
g = grid(URL_VISIT, 19, 0, 25, 0, 30)
for r in sorted(g):
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(g[r].items()))[:250]))
