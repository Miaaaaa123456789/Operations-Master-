#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extra-ingest.py — 医院经营协同看板 · 两个补充数据源抓取

接入日期 2026-09-20（业主提供）。两个数据源：

  A. 心理科来访数量（业主原话「只能抓前三个表」）
     file_id z6x6JbCFfxMDK32s7KRyrxLXkT3MBZ1cp
     · 新-排班        sheetId 19   心理科排班（倒序，最新月在最上）
     · 课程排班        sheetId 3    团体治疗/工娱的周主题排班
     · 团体治疗登记     sheetId 5    团体治疗逐场记录（含人数）

  B. 医院客服与导诊部管理规范及配套表格 → 客服部（导医）数据
     file_id qRzhvsBzrxMY7DuYWNPQrxuTUqMUNHPcJ
     · 标准化回访台账      sheetId 2   回访逐条记录（可归因到导医个人）
     · 客户投诉处理登记表   sheetId 3   投诉登记（当前为示例数据）
     · 导诊主动服务记录表   sheetId 4   导诊主动服务逐条记录
     · 日工作量考核表(分级) sheetId 7   导医逐日工作量（含两级评分）

用法：
  python3 scripts/extra-ingest.py            # 抓取 + 落盘 + 打印统计
  python3 scripts/extra-ingest.py --fprint   # 只打印指纹（供每日抓取比对）

输出：
  data/extra/psych-schedule.json    排班（新-排班 + 课程排班）
  data/extra/psych-group.json       团体治疗登记
  data/extra/service-visit.json     导诊主动服务记录
  data/extra/service-callback.json  标准化回访台账
  data/extra/service-workload.json  导医日工作量
  data/extra/complaint.json         客户投诉登记
  data/extra/fingerprint.json       指纹（6 项）

依赖：kdocs-cli v2.6.13+（认证在系统钥匙串）
"""

import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, 'data', 'extra')

KDOCS = os.environ.get('KDOCS_CLI') or os.path.expanduser('~/.local/bin/kdocs-cli')

FID_PSY = 'z6x6JbCFfxMDK32s7KRyrxLXkT3MBZ1cp'      # 心理科来访数量
FID_SVC = 'qRzhvsBzrxMY7DuYWNPQrxuTUqMUNHPcJ'      # 医院客服与导诊部

# sheetId → (中文名, 最大行, 最大列)
PSY_SHEETS = {
    'schedule': (19, '新-排班', 200, 14),
    'course':   (3,  '课程排班', 40, 21),
    'group':    (5,  '团体治疗登记', 200, 9),
}
SVC_SHEETS = {
    'callback':  (2, '标准化回访台账', 120, 12),
    'complaint': (3, '客户投诉处理登记表', 40, 11),
    'visitlog':  (4, '导诊主动服务记录表', 60, 10),
    'workload':  (7, '日工作量考核表(分级)', 60, 20),
}


# ─── kdocs 取数 ──────────────────────────────────────────────

class KdocsError(RuntimeError):
    pass


def _read_raw(file_id, sheet_id, r0, r1, c0, c1):
    payload = json.dumps({
        'file_id': file_id,
        'worksheet_id': sheet_id,
        'range': {'rowFrom': r0, 'rowTo': r1, 'colFrom': c0, 'colTo': c1},
    }, ensure_ascii=False)
    try:
        p = subprocess.run([KDOCS, 'sheet', 'get-range-data', payload],
                           capture_output=True, text=True, timeout=90)
    except FileNotFoundError:
        raise KdocsError('找不到 kdocs-cli：%s（可用 KDOCS_CLI 环境变量指定）' % KDOCS)
    except subprocess.TimeoutExpired:
        raise KdocsError('kdocs-cli 超时（sheet %s）' % sheet_id)
    txt = p.stdout.strip()
    if not txt:
        raise KdocsError('kdocs-cli 无输出（sheet %s）：%s' % (sheet_id, p.stderr[:200]))
    try:
        obj, _ = json.JSONDecoder().raw_decode(txt)
    except ValueError:
        raise KdocsError('kdocs-cli 返回非 JSON（sheet %s）：%s' % (sheet_id, txt[:200]))
    if obj.get('code') != 0:
        raise KdocsError('取数失败 sheet %s：%s' % (sheet_id, obj.get('message')))
    return obj


def fetch_grid(file_id, sheet_id, rows, cols, chunk=60):
    """返回 {(row, col): text}；行分块抓，避免单次过大。"""
    grid = {}
    r = 0
    while r <= rows:
        r1 = min(r + chunk - 1, rows)
        obj = _read_raw(file_id, sheet_id, r, r1, 0, cols - 1)
        for cd in ((obj.get('data') or {}).get('detail', {}) or {}).get('rangeData', []) or []:
            t = cd.get('cellText')
            if t is None:
                continue
            t = str(t).strip()
            if t == '':
                continue
            grid[(cd.get('rowFrom'), cd.get('colFrom'))] = t
        r = r1 + 1
    return grid


def grid_to_rows(grid):
    """{(r,c):v} → {r: {c: v}}"""
    out = defaultdict(dict)
    for (r, c), v in grid.items():
        out[r][c] = v
    return dict(out)


# ─── 通用小工具 ──────────────────────────────────────────────

def norm_date(s):
    """'2026.9.14' / '9.14' / '2026-09-14' → 'YYYY-MM-DD'（无年份默认 2026）。"""
    if not s:
        return None
    s = str(s).strip().replace('：', ':')
    s = s.split(' ')[0].split('（')[0]
    s = s.replace('-', '.').replace('/', '.').replace('年', '.').replace('月', '.').replace('日', '')
    parts = [p for p in s.split('.') if p != '']
    try:
        if len(parts) == 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            y, m, d = 2026, int(parts[0]), int(parts[1])
        else:
            return None
    except ValueError:
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    return '%04d-%02d-%02d' % (y, m, d)


def num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == '':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def week_label(d):
    """返回 'W1(8.31-9.6)' 形式；d 为 'YYYY-MM-DD'。"""
    if not d:
        return None
    # 本周（9.14—9.20）/ 上周（9.7—9.13）/ 上上周（8.31—9.6）
    if '2026-09-14' <= d <= '2026-09-20':
        return 'W3(9.14-9.20)'
    if '2026-09-07' <= d <= '2026-09-13':
        return 'W2(9.7-9.13)'
    if '2026-08-31' <= d <= '2026-09-06':
        return 'W1(8.31-9.6)'
    return 'other'


# ─── A1. 新-排班 ─────────────────────────────────────────────

def parse_schedule(rows):
    """心理科排班：每个「心理科」标题行开启一个周的块。返回 [{dates:[], rows:[{name, shifts:{date:code}}]}]"""
    blocks = []
    cur = None
    for r in sorted(rows):
        line = rows[r]
        first = (line.get(0) or '').strip()
        if first == '心理科':
            # 下一行是日期行
            cur = {'headerRow': r, 'dates': [], 'dows': [], 'rows': [], 'caption': None}
            blocks.append(cur)
            continue
        if cur is None:
            continue
        # 日期行：第一个单元格为空、后面是月.日
        if not first:
            ds = []
            dows = []
            for c in sorted(line):
                v = line[c]
                if c == 0:
                    continue
                nd = norm_date(v)
                if nd:
                    ds.append(nd)
                else:
                    dows.append(v)
            if len(ds) >= 5:
                cur['dates'] = ds
                cur['dows'] = dows
            continue
        # 表尾说明行
        if first.startswith('（') or '排班）' in first or first in ('正休', '备注'):
            cur['caption'] = first
            cur = None
            continue
        if first in ('时间', '主题', '主带领', '副带领') or '时间\n' in first:
            continue
        # 姓名行
        cur['rows'].append({
            'name': first,
            'shifts': {str(c): line[c] for c in sorted(line) if c != 0},
        })
    # 只保留有日期的块
    return [b for b in blocks if b['dates']]


# ─── A2. 课程排班 ────────────────────────────────────────────

def parse_course(rows):
    """课程排班：三列一组（时间/7天/时间）。抓第一部分（左 8 列）。"""
    periods = []
    i = 0
    rowids = sorted(rows)
    # 找到所有「时间」行作为块起点
    for r in rowids:
        if (rows[r].get(0) or '').startswith('时间'):
            periods.append(r)
    out = []
    for k, start in enumerate(periods):
        end = periods[k + 1] if k + 1 < len(periods) else start + 4
        hdr = rows.get(start, {})
        dates = []
        for c in range(1, 8):
            d = norm_date(hdr.get(c))
            if d:
                dates.append(d)
        theme = rows.get(start + 2, {})
        lead = rows.get(start + 3, {})
        assist = rows.get(start + 4, {})
        items = []
        for idx, d in enumerate(dates):
            c = idx + 1
            t = theme.get(c) or ''
            if not t:
                continue
            items.append({
                'date': d,
                'theme': t,
                'lead': (lead.get(c) or '').strip(),
                'assist': (assist.get(c) or '').strip(),
            })
        if items:
            out.append({'dateFrom': dates[0], 'dateTo': dates[-1], 'items': items})
    return out


# ─── A3. 团体治疗登记 ────────────────────────────────────────

def parse_group(rows):
    """团体治疗登记：表头在第 2 行（序号/日期/主题/主带领者/副带领者/参加人数/耗材/备注）。"""
    recs = []
    for r in sorted(rows):
        if r < 3:
            continue
        line = rows[r]
        idx = line.get(0) or ''
        date_raw = line.get(1) or ''
        theme = line.get(2) or ''
        lead = line.get(3) or ''
        assist = line.get(4) or ''
        cnt = line.get(5)
        note = line.get(7) or line.get(6) or ''
        if lead == '合计' or theme in ('合计',):
            continue
        d = norm_date(date_raw)
        if not d:
            continue
        if not theme and not lead:
            continue
        recs.append({
            'seq': idx,
            'date': d,
            'theme': theme,
            'lead': lead,
            'assist': assist,
            'count': int(num(cnt)) if num(cnt) is not None else None,
            'note': note,
        })
    return recs


# ─── B1. 标准化回访台账 ──────────────────────────────────────

def parse_callback(rows):
    """表头在第 1 行：序号/回访日期/回访者/患者姓名/联系方式/患者类型/回访次数/
    回访内容/患者反馈/满意度评分/跟进处理情况/是否到院。日期与回访者向下继承。"""
    recs = []
    last_date = None
    last_who = None
    for r in sorted(rows):
        if r < 2:
            continue
        line = rows[r]
        d = norm_date(line.get(1)) or last_date
        who = (line.get(2) or '').strip() or last_who
        if line.get(1):
            last_date = d
        if line.get(2):
            last_who = who
        pat = (line.get(3) or '').strip()
        if not pat or pat in ('患者姓名',):
            continue
        recs.append({
            'date': d,
            'staff': who,
            'patient': pat,
            'ptype': (line.get(5) or '').strip(),
            'times': num(line.get(6)),
            'content': (line.get(7) or '').strip(),
            'feedback': (line.get(8) or '').strip(),
            'score': num(line.get(9)),
            'followup': (line.get(10) or '').strip(),
            'arrived': (line.get(11) or '').strip(),
        })
    return recs


# ─── B2. 导诊主动服务记录 ────────────────────────────────────

def parse_visitlog(rows):
    """表头在第 1 行：序号/服务日期/导诊人员/患者姓名/患者情况/主动服务内容/
    解决方案/患者反馈/服务效果/备注。服务日期向下继承。"""
    recs = []
    last_date = None
    for r in sorted(rows):
        if r < 2:
            continue
        line = rows[r]
        d = norm_date(line.get(1)) or last_date
        if line.get(1):
            last_date = d
        who = (line.get(2) or '').strip()
        pat = (line.get(3) or '').strip()
        if not pat or pat == '患者姓名':
            continue
        recs.append({
            'date': d,
            'staff': who,
            'patient': pat,
            'scene': (line.get(4) or '').strip(),
            'service': (line.get(5) or '').strip(),
            'solution': (line.get(6) or '').strip(),
            'feedback': (line.get(7) or '').strip(),
            'effect': (line.get(8) or '').strip(),
        })
    return recs


# ─── B3. 导医日工作量 ────────────────────────────────────────

WL_COLS = {
    0: 'staff', 1: 'date', 2: 'shift', 3: 'keyday', 4: 'keydayFactor',
    5: 'dutyScore', 6: 'record', 7: 'assist', 8: 'escort', 9: 'entry',
    10: 'otherExtra', 11: 'extraScore', 12: 'callback', 13: 'revisit',
    14: 'satisfaction', 15: 'referral', 16: 'education', 17: 'valueScore',
    18: 'total', 19: 'memo',
}


def parse_workload(rows):
    """表头在第 2 行；第 3 行是无姓名的合计/示例行，跳过。"""
    recs = []
    for r in sorted(rows):
        if r < 4:
            continue
        line = rows[r]
        staff = (line.get(0) or '').strip()
        if not staff or staff == '导医姓名':
            continue
        d = norm_date(line.get(1))
        if not d:
            continue
        rec = {'row': r, 'staff': staff, 'date': d}
        for c, k in WL_COLS.items():
            if k in ('staff', 'date'):
                continue
            rec[k] = line.get(c)
        for k in ('keydayFactor', 'dutyScore', 'extraScore', 'valueScore', 'total'):
            rec[k] = num(rec.get(k))
        for k in ('record', 'assist', 'escort', 'entry', 'otherExtra',
                  'callback', 'revisit', 'satisfaction', 'referral', 'education'):
            rec[k] = num(rec.get(k))
        recs.append(rec)
    return recs


def parse_complaint(rows):
    recs = []
    for r in sorted(rows):
        if r < 2:
            continue
        line = rows[r]
        if not (line.get(1) or '').strip():
            continue
        recs.append({
            'no': (line.get(1) or '').strip(),
            'date': norm_date(line.get(2)),
            'subject': (line.get(5) or '').strip(),
            'handler': (line.get(6) or '').strip(),
            'result': (line.get(8) or '').strip(),
            'status': (line.get(10) or '').strip(),
        })
    return recs


# ─── 统计 ────────────────────────────────────────────────────

def summarize(psy_group, svc_callback, svc_visitlog, svc_workload):
    out = {}

    # 团体治疗：按周聚合
    gw = defaultdict(lambda: {'sessions': 0, 'people': 0, 'items': []})
    for g in psy_group:
        k = week_label(g['date'])
        gw[k]['sessions'] += 1
        gw[k]['people'] += (g['count'] or 0)
        gw[k]['items'].append('%s %s(%s人)' % (g['date'][5:], g['theme'], g['count'] if g['count'] is not None else '—'))
    out['group_by_week'] = {k: {'sessions': v['sessions'], 'people': v['people'], 'items': v['items']}
                            for k, v in sorted(gw.items())}

    # 回访：按周 + 按人
    cw = defaultdict(lambda: {'n': 0, 'arrived': 0, 'scores': []})
    cby = defaultdict(lambda: {'n': 0, 'arrived': 0, 'scores': []})
    for c in svc_callback:
        k = week_label(c['date'])
        cw[k]['n'] += 1
        cby[c['staff'] or '(未填)']['n'] += 1
        if c['score'] is not None:
            cw[k]['scores'].append(c['score'])
            cby[c['staff'] or '(未填)']['scores'].append(c['score'])
        if (c['arrived'] or '').strip() == '是':
            cw[k]['arrived'] += 1
            cby[c['staff'] or '(未填)']['arrived'] += 1
    def fmt(d):
        return {k: {'n': v['n'], 'arrived': v['arrived'],
                    'avg': round(sum(v['scores']) / len(v['scores']), 2) if v['scores'] else None}
                for k, v in sorted(d.items())}
    out['callback_by_week'] = fmt(cw)
    out['callback_by_staff'] = fmt(cby)

    # 导诊服务记录：按人 + 按周
    vby = defaultdict(int)
    vw = defaultdict(int)
    for v in svc_visitlog:
        vby[v['staff'] or '(未填)'] += 1
        vw[week_label(v['date'])] += 1
    out['visitlog_by_staff'] = dict(sorted(vby.items(), key=lambda kv: -kv[1]))
    out['visitlog_by_week'] = dict(sorted(vw.items()))

    # 导医工作量：按人汇总 + 按周
    wby = defaultdict(lambda: {'days': 0, 'duty': 0.0, 'extra': 0.0, 'value': 0.0,
                               'total': 0.0, 'callback': 0.0, 'revisit': 0.0,
                               'referral': 0.0, 'keyday': 0.0})
    ww = defaultdict(lambda: {'days': 0, 'total': 0.0, 'keyday': 0.0})
    for w in svc_workload:
        s = wby[w['staff']]
        s['days'] += 1
        for k, src in (('duty', 'dutyScore'), ('extra', 'extraScore'), ('value', 'valueScore'),
                       ('total', 'total'), ('callback', 'callback'), ('revisit', 'revisit'),
                       ('referral', 'referral'), ('keyday', 'keydayFactor')):
            s[k] += (w.get(src) or 0)
        k2 = week_label(w['date'])
        ww[k2]['days'] += 1
        ww[k2]['total'] += (w.get('total') or 0)
        ww[k2]['keyday'] += (w.get('keydayFactor') or 0)
    out['workload_by_staff'] = {k: {kk: round(vv, 2) for kk, vv in v.items()}
                                for k, v in sorted(wby.items(), key=lambda kv: -kv[1]['total'])}
    out['workload_by_week'] = {k: {kk: round(vv, 2) for kk, vv in v.items()}
                               for k, v in sorted(ww.items())}
    return out


# ─── main ────────────────────────────────────────────────────

def main():
    fprint_only = '--fprint' in sys.argv

    print('抓取 心理科来访数量（前三个表）…')
    psy = {}
    for key, (sid, name, rows, cols) in PSY_SHEETS.items():
        g = fetch_grid(FID_PSY, sid, rows, cols)
        psy[key] = grid_to_rows(g)
        print('  · %-10s sheetId=%-3d 非空 %d 格' % (name, sid, len(g)))

    print('抓取 医院客服与导诊部…')
    svc = {}
    for key, (sid, name, rows, cols) in SVC_SHEETS.items():
        g = fetch_grid(FID_SVC, sid, rows, cols)
        svc[key] = grid_to_rows(g)
        print('  · %-16s sheetId=%-3d 非空 %d 格' % (name, sid, len(g)))

    schedule = parse_schedule(psy['schedule'])
    course = parse_course(psy['course'])
    group = parse_group(psy['group'])
    callback = parse_callback(svc['callback'])
    visitlog = parse_visitlog(svc['visitlog'])
    workload = parse_workload(svc['workload'])
    complaint = parse_complaint(svc['complaint'])

    stats = summarize(group, callback, visitlog, workload)

    fp = {
        'psyScheduleBlocks': len(schedule),
        'psyCoursePeriods': len(course),
        'psyGroupRecords': len(group),
        'svcCallbackRecords': len(callback),
        'svcVisitlogRecords': len(visitlog),
        'svcWorkloadRecords': len(workload),
        'svcComplaintRecords': len(complaint),
    }

    if not fprint_only:
        os.makedirs(OUT_DIR, exist_ok=True)
        def w(name, obj):
            p = os.path.join(OUT_DIR, name)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(obj, f, ensure_ascii=False, indent=1)
            print('  → %s' % p)
        w('psych-schedule.json', schedule)
        w('psych-course.json', course)
        w('psych-group.json', group)
        w('service-callback.json', callback)
        w('service-visitlog.json', visitlog)
        w('service-workload.json', workload)
        w('complaint.json', complaint)
        w('fingerprint.json', fp)
        w('stats.json', stats)

    print('\n指纹：%s' % json.dumps(fp, ensure_ascii=False))
    print('\n── 团体治疗（按周）──')
    for k, v in stats['group_by_week'].items():
        print('  %-14s %d 场 / %d 人  %s' % (k, v['sessions'], v['people'], '，'.join(v['items'])))
    print('\n── 回访（按周）──')
    for k, v in stats['callback_by_week'].items():
        print('  %-14s %d 条 · 到院 %d · 均分 %s' % (k, v['n'], v['arrived'], v['avg']))
    print('\n── 回访（按导医）──')
    for k, v in sorted(stats['callback_by_staff'].items(), key=lambda kv: -kv[1]['n']):
        print('  %-8s %d 条 · 到院 %d · 均分 %s' % (k, v['n'], v['arrived'], v['avg']))
    print('\n── 导诊主动服务（按人）──')
    for k, v in stats['visitlog_by_staff'].items():
        print('  %-8s %d 条' % (k, v))
    print('\n── 导医日工作量（按人）──')
    for k, v in stats['workload_by_staff'].items():
        print('  %-8s 在岗 %2d 天 · 总分 %6.2f（履职 %5.2f / 附加 %5.2f / 增值 %6.2f）'
              % (k, v['days'], v['total'], v['duty'], v['extra'], v['value']))
    print('\n── 导医日工作量（按周）──')
    for k, v in stats['workload_by_week'].items():
        print('  %-14s 在岗 %d 人日 · 总分 %.2f' % (k, v['days'], v['total']))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KdocsError as e:
        print('❌ %s' % e, file=sys.stderr)
        sys.exit(2)
