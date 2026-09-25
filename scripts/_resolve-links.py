#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析业主新给的 5 个金山文档链接 → file_id + sheet 结构"""
import json
import subprocess
import sys

CLI = '/Users/opp/.local/bin/kdocs-cli'

LINKS = [
    ('① 特别行动小组汇报表', 'https://www.kdocs.cn/l/cbwp2cvTiFyK'),
    ('② 心理V4管理表（主任日报联动）', 'https://www.kdocs.cn/l/cgd3nVre7qWs'),
    ('③ 心理科来访数量', 'https://www.kdocs.cn/l/coL1GfCvA0an'),
    ('④ 患者有效对接表', 'https://www.kdocs.cn/l/ctlu8ktnEwi8'),
    ('⑤ 医院客服与导诊部', 'https://www.kdocs.cn/l/cuOhExpV6n29'),
]


def call(tool, params):
    r = subprocess.run([CLI, 'call', tool, json.dumps(params, ensure_ascii=False)],
                       capture_output=True, text=True)
    out = r.stdout or ''
    i = out.find('{')
    if i < 0:
        return {'_err': (r.stderr or out)[:300]}
    try:
        return json.JSONDecoder().raw_decode(out[i:])[0]
    except Exception as e:
        return {'_err': '%s | %s' % (e, out[:200])}


print('=' * 78)
print('  解析 5 个链接')
print('=' * 78)
for label, url in LINKS:
    print('\n╔══ %s' % label)
    print('║   %s' % url)
    info = call('sheet.get_sheets_info', {'url': url})
    if '_err' in info:
        # 不是 sheet，试 drive 元信息
        meta = call('drive.get_file_info', {'url': url})
        print('║   sheet 读取失败：%s' % info['_err'][:160])
        print('║   drive meta: %s' % json.dumps(meta, ensure_ascii=False)[:400])
        continue
    d = (info.get('data') or {}).get('detail') or {}
    fid = d.get('fileId') or d.get('file_id')
    print('║   file_id = %s' % fid)
    print('║   fileName = %s' % d.get('fileName'))
    si = d.get('sheetsInfo') or []
    print('║   共 %d 个 sheet：' % len(si))
    for s in si:
        print('║     id=%-4s %-30s rows %s-%s cols %s-%s' % (
            s.get('sheetId'), s.get('sheetName'), s.get('rowFrom'),
            s.get('rowTo'), s.get('colFrom'), s.get('colTo')))
