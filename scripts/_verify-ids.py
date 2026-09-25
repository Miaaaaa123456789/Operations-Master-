#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证：旧 file_id（脚本里硬编码）与新分享链接是否指向同一文件"""
import json
import subprocess

CLI = '/Users/opp/.local/bin/kdocs-cli'

PAIRS = [
    ('心理V4管理表', 'fdg34kWW8xM3A1fVCrSP1xhVhBazPDzkt', 'https://www.kdocs.cn/l/cgd3nVre7qWs'),
    ('心理科来访数量', 'z6x6JbCFfxMDK32s7KRyrxLXkT3MBZ1cp', 'https://www.kdocs.cn/l/coL1GfCvA0an'),
    ('患者有效对接表', 'zTTYxTcbJxMXBcbnnZ8ZrxTDRareiGEH9', 'https://www.kdocs.cn/l/ctlu8ktnEwi8'),
    ('客服与导诊部', 'qRzhvsBzrxMY7DuYWNPQrxuTUqMUNHPcJ', 'https://www.kdocs.cn/l/cuOhExpV6n29'),
]


def sheets(param, key):
    r = subprocess.run([CLI, 'call', 'sheet.get_sheets_info',
                        json.dumps({key: param}, ensure_ascii=False)],
                       capture_output=True, text=True)
    out = r.stdout or ''
    i = out.find('{')
    if i < 0:
        return None, (r.stderr or out)[:200]
    try:
        d = json.JSONDecoder().raw_decode(out[i:])[0]
        si = ((d.get('data') or {}).get('detail') or {}).get('sheetsInfo') or []
        return [(s.get('sheetId'), s.get('sheetName'),
                 s.get('rowFrom'), s.get('rowTo')) for s in si], None
    except Exception as e:
        return None, '%s | %s' % (e, out[:200])


for label, fid, url in PAIRS:
    print('\n══ %s' % label)
    a, ea = sheets(fid, 'file_id')
    b, eb = sheets(url, 'url')
    if ea:
        print('   旧 file_id 读取失败: %s' % ea[:120])
    if eb:
        print('   新 url 读取失败: %s' % eb[:120])
    if a and b:
        same = a == b
        print('   旧 file_id: %d sheets | 新 url: %d sheets → %s'
              % (len(a), len(b), '完全一致 ✓' if same else '有差异 ✗'))
        if not same:
            print('   旧:', a)
            print('   新:', b)
    elif a:
        print('   旧 file_id 可用（%d sheets），新 url 不可用' % len(a))
    elif b:
        print('   仅新 url 可用（%d sheets）' % len(b))
