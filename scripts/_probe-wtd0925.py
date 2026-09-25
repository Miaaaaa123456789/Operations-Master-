#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本周 9.21—9.27 至今（截至 9.25）与上周同期 各模块精确核算"""
import json
import os
import re
import subprocess
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
CLI = '/Users/opp/.local/bin/kdocs-cli'
URL_PSY = 'https://www.kdocs.cn/l/cgd3nVre7qWs'
URL_VISIT = 'https://www.kdocs.cn/l/coL1GfCvA0an'
URL_GJ = 'https://www.kdocs.cn/l/ctlu8ktnEwi8'
URL_SVC = 'https://www.kdocs.cn/l/cuOhExpV6n29'

CUR = ('2026-09-21', '2026-09-25')
PREV = ('2026-09-14', '2026-09-18')


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


def sec(t):
    print('\n' + '█' * 72)
    print('  ' + t)
    print('█' * 72)


# ══════════ 1. 客服（本地已抓）
sec('1. 客服/导诊（截至 9.25）')
cb, vl, wl = load('service-callback'), load('service-visitlog'), load('service-workload')
for f, nm in [('cb', '回访'), ('vl', '主动服务'), ('wl', '日工作量')]:
    pass
allcb = load('service-callback')
print('回访台账总记录 %d 条，日期范围 %s → %s' % (
    len(allcb), min(str(r['date'])[:10] for r in allcb), max(str(r['date'])[:10] for r in allcb)))
print('  按日：', dict(sorted(Counter(str(r['date'])[:10] for r in allcb).items())))


def cbagg(a, b):
    s = [r for r in cb if a <= str(r.get('date'))[:10] <= b]
    ar = sum(1 for r in s if r.get('arrived') == '是')
    return s, len(s), ar


for lab, (a, b) in [('本周至今 9.21—9.25', CUR), ('上周同期 9.14—9.18', PREV)]:
    s, n, ar = cbagg(a, b)
    print('\n  %s：%d 条 · 到院 %d（%.1f%%）' % (lab, n, ar, ar / n * 100 if n else 0))
    print('    逐日：', dict(sorted(Counter(str(r['date'])[:10] for r in s).items())))
    per = Counter(r['staff'] for r in s)
    arr = Counter(r['staff'] for r in s if r.get('arrived') == '是')
    print('    分人：', ' / '.join('%s %d（到院 %d）' % (k, v, arr[k]) for k, v in per.most_common()))
    print('    满意度：', dict(Counter(r.get('score') for r in s)))

for lab, (a, b) in [('本周 9.21—9.25', CUR), ('上周同期 9.14—9.18', PREV)]:
    sv = [r for r in vl if a <= str(r.get('date'))[:10] <= b]
    sw = [r for r in wl if a <= str(r.get('date'))[:10] <= b]
    tot = sum((r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0) for r in sw)
    print('\n  %s：主动服务 %d 条 · 日工作量 %d 人日 %.0f 分' % (lab, len(sv), len(sw), tot))
    print('    日工作量分人：', {k: round(v) for k, v in sorted(
        ((lambda: (lambda d: d)({}))() or {}).items())} if False else '')
    agg = defaultdict(float)
    for r in sw:
        agg[r['staff']] += (r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0)
    print('    ', {k: round(v) for k, v in sorted(agg.items(), key=lambda x: -x[1])})

# ══════════ 2. 心理 V4 每日简报（在线）
sec('2. 心理V4 — 咨询师每日简报（在线直读）')
g = {}
for r, c, t in cells(URL_PSY, 11, 0, 1004, 0, 16):
    g.setdefault(r, {})[c] = t
recs = []
for r in sorted(g):
    row = g[r]
    d = str(row.get(0, ''))[:10]
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
        continue
    nm = row.get(1, '')
    m = re.search(r'[（(]([^)）]+)[)）]', nm)
    nm = m.group(1) if m else nm
    if not nm:
        continue
    num = lambda i: float(re.sub(r'[^0-9.\-]', '', str(row.get(i, '0'))) or 0)
    recs.append({'date': d, 'name': nm, 'shift': row.get(2, ''),
                 '首次对接': num(6), '床旁支持': num(7), '情绪干预': num(8),
                 '住院咨询': num(9), '门诊咨询': num(10), '家庭咨询': num(11),
                 '家长反馈': num(12), '家长访谈': num(13), '拒绝': num(14)})
print('共 %d 条有效日报（%s → %s）' % (len(recs), recs[0]['date'], recs[-1]['date']) if recs else '无')
print('  按日：', {k: v for k, v in sorted(Counter(r['date'] for r in recs).items()) if k >= '2026-09-10'})
CONTACT = ('首次对接', '床旁支持', '情绪干预')
ADVICE = ('住院咨询', '门诊咨询', '家庭咨询')
PARENT = ('家长反馈', '家长访谈')
for lab, (a, b) in [('本周至今 9.21—9.25', CUR), ('上周同期 9.14—9.18', PREV)]:
    s = [r for r in recs if a <= r['date'] <= b]
    gsum = lambda fs: int(sum(r[k] for r in s for k in fs))
    print('\n  %s：%d 条日报 · 接触 %d · 咨询 %d · 家长 %d'
          % (lab, len(s), gsum(CONTACT), gsum(ADVICE), gsum(PARENT)))
    print('    分人日报数：', dict(Counter(r['name'] for r in s).most_common()))
    d_ = defaultdict(int)
    for r in s:
        d_[r['name']] += int(sum(r[k] for k in CONTACT))
    print('    接触分人：', dict(d_))

# ══════════ 3. 团体治疗登记
sec('3. 心理科来访数量 — 团体治疗登记（9.14 起）')
rows = {}
for r, c, t in cells(URL_VISIT, 5, 0, 175, 0, 11):
    rows.setdefault(r, {})[c] = t
print('  表头 r1:', rows.get(0))
for r in sorted(rows):
    if r < 1:
        continue
    row = rows[r]
    d = str(row.get(1, ''))[:10]
    if d >= '2026-09-14':
        print('   r%-3d %s | %s' % (r + 1, d, ' | '.join(
            '%s' % row.get(c, '') for c in sorted(row) if c != 1)[:150]))

# ══════════ 4. 管家
sec('4. 患者有效对接表（在线直读）')
GJ = {1: '菲菲', 2: '国威', 3: '金林', 4: '朱婧', 6: '利娟'}
for sid, nm in GJ.items():
    rows = {}
    for r, c, t in cells(URL_GJ, sid, 0, 400, 0, 12):
        rows.setdefault(r, {})[c] = t
    last = {}
    cur = None
    cnt = Counter()
    for r in sorted(rows):
        row = rows[r]
        if str(row.get(0, '')).strip() == '序号':
            continue
        ds = str(row.get(1, '')).strip()
        m = re.match(r'^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$', ds)
        if m:
            cur = '%04d-%02d-%02d' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if not cur:
            continue
        if not any(str(row.get(cc, '')).strip() for cc in (2, 3, 4, 5, 6, 7)):
            continue
        cnt[cur] += 1
    recent = {k: v for k, v in sorted(cnt.items()) if k >= '2026-09-14'}
    print('  %-4s 总 %3d 条 | 9.14 起：%s' % (nm, sum(cnt.values()), recent))
