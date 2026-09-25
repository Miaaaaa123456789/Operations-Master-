#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import subprocess

CLI = '/Users/opp/.local/bin/kdocs-cli'
URL_MAIN = 'https://www.kdocs.cn/l/cbwp2cvTiFyK'


def raw(sid, rf, rt, cf, co, url=URL_MAIN):
    r = subprocess.run([CLI, 'call', 'sheet.get_range_data', json.dumps({
        'url': url, 'worksheet_id': sid,
        'range': {'rowFrom': rf, 'rowTo': rt, 'colFrom': cf, 'colTo': co}},
        ensure_ascii=False)], capture_output=True, text=True)
    out = r.stdout or ''
    print('   [debug] stdout %d B, stderr %s' % (len(out), (r.stderr or '')[:160]))
    i = out.find('{')
    if i < 0:
        print('   [debug] 无 JSON:', out[:300])
        return []
    try:
        d = json.JSONDecoder().raw_decode(out[i:])[0]
    except Exception as e:
        print('   [debug] 解析失败:', e, out[:200])
        return []
    rd = ((d.get('data') or {}).get('detail') or {}).get('rangeData') or []
    return [(c.get('originRow'), c.get('originCol'), (c.get('cellText') or '').strip())
            for c in rd if (c.get('cellText') or '').strip()]


print('══ 护理组：先探行 1-20 全列，看哪些格有内容 ══')
for r, c, t in raw(4, 0, 20, 0, 12):
    if len(t) > 40:
        print('\n── r%d c%d  (%d 字) ──' % (r + 1, c, len(t)))
        print(t[:2200])
