#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定稿：本周至今 9.21—9.24（4 天）与上周同期 9.14—9.17（4 天）全模块数值"""
import json
import os
import re
import subprocess
from collections import Counter, defaultdict

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI = '/Users/opp/.local/bin/kdocs-cli'
URL_PSY = 'https://www.kdocs.cn/l/cgd3nVre7qWs'
URL_GJ = 'https://www.kdocs.cn/l/ctlu8ktnEwi8'
YES = {'是', '√', '1', 'Y', 'y', '✓', 'v'}
CUR = ('2026-09-21', '2026-09-24')
PREV = ('2026-09-14', '2026-09-17')


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


def cells(url, sid, rf, rt, cf, co):
    d = call('sheet.get_range_data', {'url': url, 'worksheet_id': sid,
             'range': {'rowFrom': rf, 'rowTo': rt, 'colFrom': cf, 'colTo': co}})
    if not d:
        return []
    rd = ((d.get('data') or {}).get('detail') or {}).get('rangeData') or []
    return [(c.get('originRow'), c.get('originCol'), (c.get('cellText') or '').strip())
            for c in rd if (c.get('cellText') or '').strip()]


def load(f):
    d = json.load(open('data/extra/%s.json' % f, encoding='utf-8'))
    return d if isinstance(d, list) else (d.get('records') or d.get('rows') or [])


print('=' * 76)
print('  定稿数值（统一截止 9.24）')
print('=' * 76)

# ── 客服
print('\n【客服 / 导诊】')
cb, vl, wl = load('service-callback'), load('service-visitlog'), load('service-workload')
res = {}
for lab, (a, b) in [('本周', CUR), ('上周同期', PREV)]:
    s = [r for r in cb if a <= str(r['date'])[:10] <= b]
    ar = sum(1 for r in s if r.get('arrived') == '是')
    sv = [r for r in vl if a <= str(r['date'])[:10] <= b]
    sw = [r for r in wl if a <= str(r['date'])[:10] <= b]
    tot = round(sum((r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0) for r in sw))
    res[lab] = dict(cb=len(s), ar=ar, vl=len(sv), wd=len(sw), wsum=tot,
                    per=Counter(r['staff'] for r in s),
                    arr=Counter(r['staff'] for r in s if r.get('arrived') == '是'),
                    score=Counter(r.get('score') for r in s))
    print('  %-6s 回访 %2d 条 · 到院 %2d（%.1f%%）· 主动服务 %2d 条 · 日工作量 %2d 人日 %.0f 分'
          % (lab, len(s), ar, ar / len(s) * 100 if s else 0, len(sv), len(sw), tot))
c, p = res['本周'], res['上周同期']
print('  环比    回访 %+.1f%% · 到院 %+.1f%% · 主动服务 %+.0f%% · 工作量分 %+.1f%%'
      % ((c['cb'] - p['cb']) / p['cb'] * 100, (c['ar'] - p['ar']) / p['ar'] * 100,
         (c['vl'] - p['vl']) / p['vl'] * 100, (c['wsum'] - p['wsum']) / p['wsum'] * 100))
print('  本周分人：' + ' / '.join('%s %d 条（到院 %d = %.0f%%）' % (k, v, c['arr'][k], c['arr'][k] / v * 100)
                               for k, v in c['per'].most_common()))
print('  本周满意度：', dict(c['score']))
ag = Counter()
for r in [x for x in wl if CUR[0] <= str(x['date'])[:10] <= CUR[1]]:
    ag[r['staff']] += round((r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0))
print('  本周日工作量分人：', dict(ag.most_common()))

# ── 心理
print('\n【心理组·管理表V4 咨询师每日简报】')
rows = {}
for r, c_, t in cells(URL_PSY, 11, 0, 1004, 0, 16):
    rows.setdefault(r, {})[c_] = t
recs = []
for r in sorted(rows):
    row = rows[r]
    d = str(row.get(0, ''))[:10]
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
        continue
    nm = row.get(1, '')
    m = re.search(r'[（(]([^)）]+)[)）]', nm)
    nm = m.group(1) if m else nm
    if not nm:
        continue
    num = lambda i: float(re.sub(r'[^0-9.\-]', '', str(row.get(i, '0'))) or 0)
    recs.append({'date': d, 'name': nm, '首次对接': num(6), '床旁支持': num(7), '情绪干预': num(8),
                 '住院咨询': num(9), '门诊咨询': num(10), '家庭咨询': num(11),
                 '家长反馈': num(12), '家长访谈': num(13)})
CONTACT, ADVICE, PARENT = ('首次对接', '床旁支持', '情绪干预'), ('住院咨询', '门诊咨询', '家庭咨询'), ('家长反馈', '家长访谈')
print('  总 %d 条日报（%s → %s）' % (len(recs), recs[0]['date'], recs[-1]['date']))
for lab, (a, b) in [('本周', CUR), ('上周同期', PREV)]:
    s = [r for r in recs if a <= r['date'] <= b]
    g = lambda fs: int(sum(r[k] for r in s for k in fs))
    print('  %-6s %d 条日报 · 接触 %d · 咨询 %d · 家长 %d' % (lab, len(s), g(CONTACT), g(ADVICE), g(PARENT)))
    print('         分人日报：', dict(Counter(r['name'] for r in s).most_common()))
    d_ = defaultdict(int)
    for r in s:
        d_[r['name']] += int(sum(r[k] for k in CONTACT))
    print('         接触分人：', dict(d_))

# ── 管家
print('\n【管家·患者有效对接表】')
GJ = {1: '菲菲', 2: '国威', 3: '金林', 4: '朱婧', 6: '利娟'}
gj = {}
for sid, nm in GJ.items():
    g = {}
    for r, c_, t in cells(URL_GJ, sid, 0, 400, 0, 12):
        g.setdefault(r, {})[c_] = t
    gj[nm] = g


def gagg(nm, lo, hi):
    c = Counter()
    cur = None
    for r in sorted(gj[nm]):
        row = gj[nm][r]
        if str(row.get(0, '')).strip() == '序号':
            continue
        ds = str(row.get(1, '')).strip()
        m = re.match(r'^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$', ds)
        if m:
            y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2020 <= y <= 2030 and 1 <= mo <= 12:
                cur = '%04d-%02d-%02d' % (y, mo, dd)
        if not (cur and lo <= cur <= hi):
            continue
        if not any(str(row.get(cc, '')).strip() for cc in (3, 4, 5, 6, 7)):
            continue
        c['对接'] += 1
        if str(row.get(4, '')).strip() in YES:
            c['检查'] += 1
        if str(row.get(5, '')).strip() in YES:
            c['物理'] += 1
        if str(row.get(6, '')).strip():
            c['心理'] += 1
        if str(row.get(7, '')).strip() in YES:
            c['住院'] += 1
    return c


for lab, (lo, hi) in [('本周 9.21—9.24', CUR), ('上周同期 9.14—9.17', PREV)]:
    T = Counter()
    line = []
    for sid, nm in GJ.items():
        c = gagg(nm, lo, hi)
        T.update(c)
        line.append('%s %d' % (nm, c['对接']))
    print('  %-16s 对接 %2d（%s）· 检查 %2d · 物理 %2d · 心理 %2d · 住院 %2d → 转住院率 %.1f%%'
          % (lab, T['对接'], ' / '.join(line), T['检查'], T['物理'], T['心理'], T['住院'],
             T['住院'] / T['对接'] * 100 if T['对接'] else 0))
# 校验锚点
F = Counter()
for sid, nm in GJ.items():
    F.update(gagg(nm, '2026-09-14', '2026-09-20'))
print('  ※ 自检锚点 上周完整周 9.14—9.20：对接 %d / 住院 %d（%.1f%%）——面板现值 80 / 14 / 17.5%%'
      % (F['对接'], F['住院'], F['住院'] / F['对接'] * 100))
