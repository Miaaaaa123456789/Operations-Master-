#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核查：① 利娟未来日期 ② 心理V4 主任日报/团队查房日报 ③ 客服在线表行数"""
import json
import re
import subprocess

CLI = '/Users/opp/.local/bin/kdocs-cli'
URL_GJ = 'https://www.kdocs.cn/l/ctlu8ktnEwi8'
URL_PSY = 'https://www.kdocs.cn/l/cgd3nVre7qWs'
URL_SVC = 'https://www.kdocs.cn/l/cuOhExpV6n29'


def cells(url, sid, rf, rt, cf, co):
    r = subprocess.run([CLI, 'call', 'sheet.get_range_data', json.dumps({
        'url': url, 'worksheet_id': sid,
        'range': {'rowFrom': rf, 'rowTo': rt, 'colFrom': cf, 'colTo': co}},
        ensure_ascii=False)], capture_output=True, text=True)
    out = r.stdout or ''
    i = out.find('{')
    if i < 0:
        return []
    d = json.JSONDecoder().raw_decode(out[i:])[0]
    rd = ((d.get('data') or {}).get('detail') or {}).get('rangeData') or []
    return [(c.get('originRow'), c.get('originCol'), (c.get('cellText') or '').strip())
            for c in rd if (c.get('cellText') or '').strip()]


print('█' * 72)
print('  ① 利娟表：9.20 之后全部行（含未来日期）')
print('█' * 72)
rows = {}
for r, c, t in cells(URL_GJ, 6, 0, 90, 0, 12):
    rows.setdefault(r, {})[c] = t
for r in sorted(rows):
    row = rows[r]
    ds = str(row.get(1, '')).strip()
    if r < 1 and ds != '日期':
        continue
    if r == 1:
        print('   表头:', ' | '.join('%s' % row.get(c, '') for c in sorted(row)))
        continue
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(row.items()))[:180]))

print('\n\n' + '█' * 72)
print('  ② 心理V4 — 主任日报（id=9）最后 15 行有内容')
print('█' * 72)
rows = {}
for r, c, t in cells(URL_PSY, 9, 0, 119, 0, 16):
    rows.setdefault(r, {})[c] = t
for r in sorted(rows)[-15:]:
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(rows[r].items()))[:230]))

print('\n\n' + '█' * 72)
print('  ② 心理V4 — 团队查房日报（id=5）最后 12 行')
print('█' * 72)
rows = {}
for r, c, t in cells(URL_PSY, 5, 380, 403, 0, 16):
    rows.setdefault(r, {})[c] = t
for r in sorted(rows)[-12:]:
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(rows[r].items()))[:230]))

print('\n\n' + '█' * 72)
print('  ② 心理V4 — 组长日管理（id=10）')
print('█' * 72)
rows = {}
for r, c, t in cells(URL_PSY, 10, 0, 21, 0, 18):
    rows.setdefault(r, {})[c] = t
for r in sorted(rows):
    print('   r%-3d | %s' % (r + 1, ' | '.join('c%d=%s' % (c, v) for c, v in sorted(rows[r].items()))[:230]))

print('\n\n' + '█' * 72)
print('  ③ 客服三表在线行数（验证本地已同步）')
print('█' * 72)
for sid, nm, co in [(2, '标准化回访台账', 11), (4, '导诊主动服务记录表', 9), (7, '日工作量考核表(分级)', 19)]:
    cl = cells(URL_SVC, sid, 0, 200, 0, co)
    if not cl:
        print('   %-22s 读取失败' % nm)
        continue
    maxr = max(r for r, c, t in cl)
    dates = [t for r, c, t in cl if c == 1 or (sid == 7 and c == 1)]
    print('   %-22s 最后行 r%d 非空格 %d' % (nm, maxr + 1, len(cl)))
    tail = sorted({t for r, c, t in cl if re.match(r'^\d{4}[-./]\d{1,2}[-./]\d{1,2}$', t)})
    print('      日期范围 %s → %s' % (tail[0] if tail else '-', tail[-1] if tail else '-'))
