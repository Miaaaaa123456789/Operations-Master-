#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把《质控分及物理治疗数据.docx》里的「物理治疗完成数据汇报」逐日表解析成 JSON。

为什么单独一个脚本：这份 docx 每周由护理部更新、结构固定但不规范
（日期只写在首行、10-17 那张表多出一行重复的「团体」、日期格式在
10/11、10-12、2026-10-15 三种写法之间跳），手工抄一遍下周就会过期。
脚本只做解析，不做任何修补判断 —— 异常原样带进 warnings，由上层决定。

用法：
    python3 parse_nursing_docx.py <docx 路径> [-o 输出 json]
"""
import sys
import json
import re
import argparse
from datetime import datetime

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

# docx 里的治疗项目名 → 看板指标键（与 ingest.py 保持一致）
PROJECT_KEYS = {
    "交流电": "ac_current",
    "经颅磁": "tms",
    "脑功能": "brain_func",
    "放松": "music_relax",
    "失眠": "insomnia",
    "团体": "group_biofeedback",
}
PROJECT_LABELS = {
    "ac_current": "经颅交流电",
    "tms": "经颅磁治疗",
    "brain_func": "脑功能治疗",
    "music_relax": "音乐放松治疗",
    "insomnia": "失眠治疗仪治疗",
    "group_biofeedback": "团体生物反馈",
}


def iter_blocks(doc):
    """按文档真实顺序产出 ('p', Paragraph) / ('t', Table)。"""
    body = doc.element.body
    for child in body.iterchildren():
        tag = child.tag.split('}')[-1]
        if tag == 'p':
            yield 'p', Paragraph(child, doc)
        elif tag == 'tbl':
            yield 't', Table(child, doc)


def parse_date(raw):
    """10/11 · 10-12 · 2026-10-15 → date(2026, m, d)。解析不了返回 None。"""
    s = (raw or '').strip().replace('/', '-').replace('.', '-')
    m = re.match(r'^(?:(\d{4})-)?(\d{1,2})-(\d{1,2})$', s)
    if not m:
        return None
    year = int(m.group(1)) if m.group(1) else 2026
    try:
        return datetime(year, int(m.group(2)), int(m.group(3))).date()
    except ValueError:
        return None


def num(v):
    s = (v or '').strip().replace('％', '%')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse(path):
    doc = Document(path)
    out, warnings = [], []
    pending_header = False
    last_date = None

    for kind, blk in iter_blocks(doc):
        if kind == 'p':
            txt = (blk.text or '').strip()
            pending_header = ('物理治疗完成数据' in txt)
            continue
        if not pending_header:
            continue
        pending_header = False

        rows = blk.rows
        if len(rows) < 2:
            warnings.append('遇到列数不足的表格，已跳过')
            continue
        head = [(c.text or '').strip() for c in rows[0].cells]
        if '治疗项目' not in head:
            continue
        idx = {name: i for i, name in enumerate(head)}

        day = None
        for r_i, row in enumerate(rows[1:], start=2):
            cells = [(c.text or '').strip() for c in row.cells]
            raw_date = cells[idx.get('日期', 0)]
            if raw_date:
                d = parse_date(raw_date)
                if d is None:
                    warnings.append(f'第 {r_i} 行日期无法解析：{raw_date!r}')
                else:
                    day = d
                    last_date = d
            if day is None:
                warnings.append(f'第 {r_i} 行没有日期且上文无可用日期，已跳过')
                continue

            proj_raw = cells[idx['治疗项目']]
            key = PROJECT_KEYS.get(proj_raw)
            if key is None:
                warnings.append(f'第 {r_i} 行未知治疗项目：{proj_raw!r}')
                continue

            due = num(cells[idx['应做']])
            done = num(cells[idx['实做']])
            rec = {
                'date': day.isoformat(),
                'project_raw': proj_raw,
                'key': key,
                'label': PROJECT_LABELS[key],
                'due': None if due is None else int(due),
                'done': None if done is None else int(done),
                'given_rate': num(cells[idx['完成率']]) if '完成率' in idx else None,
                'inpatient': num(cells[idx['住院人数']]) if '住院人数' in idx else None,
                'row': r_i,
            }
            # 同一天同一项目出现两行 → 记重复，保留第一行，不静默合并
            dup = [x for x in out if x['date'] == rec['date'] and x['key'] == key]
            if dup:
                warnings.append(
                    f"{rec['date']} 的「{proj_raw}」重复出现（第 {r_i} 行），"
                    f"保留首行 {dup[0]['due']}/{dup[0]['done']}，本行 {due}/{done} 已忽略")
                continue
            out.append(rec)

    # 交叉校验：文档给的完成率 vs 实做/应做（护理部口径是向下取整）
    for x in out:
        if x['due'] and x['done'] is not None and x['given_rate'] is not None:
            calc = x['done'] / x['due'] * 100
            if abs(int(calc) - int(x['given_rate'])) > 1:
                warnings.append(
                    f"{x['date']} {x['project_raw']}：表内完成率 {x['given_rate']}% "
                    f"与 {x['done']}/{x['due']}={calc:.1f}% 相差超过 1pt")

    out.sort(key=lambda r: (r['date'], r['key']))
    return {
        'source': '质控分及物理治疗数据.docx',
        'parsed_at': datetime.now().isoformat(timespec='seconds'),
        'rows': len(out),
        'first_date': out[0]['date'] if out else None,
        'last_date': out[-1]['date'] if out else None,
        'projects': PROJECT_LABELS,
        'daily': out,
        'warnings': warnings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx')
    ap.add_argument('-o', '--out', default=None)
    args = ap.parse_args()

    data = parse(args.docx)
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"已写出 {args.out}：{data['rows']} 行 · {data['first_date']}~{data['last_date']}")
    else:
        print(text)
    if data['warnings']:
        print(f"\n⚠ {len(data['warnings'])} 条警告：")
        for w in data['warnings']:
            print('  -', w)


if __name__ == '__main__':
    main()
