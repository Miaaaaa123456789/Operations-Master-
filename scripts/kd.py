#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取金山主表指定 sheet 的当前内容。用法: kd.py <sheetId> [rowTo]"""
import json, subprocess, sys

URL = 'https://www.kdocs.cn/l/cbwp2cvTiFyK'
CLI = '/Users/opp/.local/bin/kdocs-cli'


def call(tool, params):
    out = subprocess.run([CLI, 'call', tool, json.dumps(params, ensure_ascii=False)],
                         capture_output=True, text=True).stdout
    d, _ = json.JSONDecoder().raw_decode(out.lstrip())
    return d


def sheets():
    d = call('sheet.get_sheets_info', {'url': URL})
    return d['data']['detail']['sheetsInfo']


def read(sid, rowTo=14, colTo=9):
    d = call('sheet.get_range_data', {'url': URL, 'worksheet_id': sid,
                                      'range': {'rowFrom': 0, 'rowTo': rowTo,
                                                'colFrom': 0, 'colTo': colTo}})
    rd = d['data']['detail']['rangeData']
    rows = {}
    for c in rd:
        t = (c.get('cellText') or '').strip()
        if t:
            rows.setdefault(c['originRow'], {})[c['originCol']] = t
    return rows


def show(sid, rowTo=14, colTo=9):
    info = {s['sheetId']: s['sheetName'] for s in sheets()}
    print('════════ sheetId=%s  「%s」 ════════' % (sid, info.get(sid, '?')))
    for r in sorted(read(sid, rowTo, colTo)):
        cells = ['c%s=%s' % (k, v) for k, v in sorted(read(sid, rowTo, colTo)[r].items())]
        line = ' | '.join(cells)
        print('r%-2d | %s' % (r + 1, line[:240]))


if __name__ == '__main__':
    sid = int(sys.argv[1])
    rt = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    show(sid, rt)
