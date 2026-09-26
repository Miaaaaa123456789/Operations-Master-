#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
排名与本周指标生成器 —— 从源数据直接算出「本周排名」，供看板注入

为什么需要它：看板里各部门的排名原先是一次性手写的，源表更新后不会自动变。
本脚本把「抓取 → 算排名」固化成一条命令，避免排名长期停留在旧周。

排名口径（业主 2026-09-26 定）：**各部门都不要以填报天数作为排名权重。**
排名只按业务量与效率排序（条数 / 人次 / 金额、日均、完成率、转化率）；
填报天数、在岗天数只作数据完整性与可比性提示 —— 不计分、不排序、不作并列判定。
需要「总量 vs 效率」两看的（如导医日工作量），排序键取「日均」，总量只写在说明里。

用法：
    python3 scripts/gen-rankings.py                      # 本周 = 最近一个周一
    python3 scripts/gen-rankings.py --week-start 2026-09-21 --out data/rankings.json

产出 JSON 结构：
    {week:{lo,hi}, prev:{lo,hi}, asOf:'', depts:{
        service:{rankGroups:[{title,note,rows:[{name,metric,score,missing}]}], metrics:{...}},
        psychology:{...}, marketing:{...} }}
"""
import argparse, datetime as dt, io, json, os, re, sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))

# 复用周收口脚本里的取数实现，避免两处口径分叉
import importlib.util
_spec = importlib.util.spec_from_file_location('week_rollup', os.path.join(REPO, 'scripts', 'week-rollup.py'))
wr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wr)

YES = wr.YES


# ────────────────────────────── 工具
def load_extra(f):
    p = os.path.join(REPO, 'data', 'extra', f + '.json')
    if not os.path.exists(p):
        return []
    d = json.load(io.open(p, encoding='utf-8'))
    if isinstance(d, list):
        return d
    for k in ('records', 'rows', 'data'):
        if isinstance(d.get(k), list):
            return d[k]
    return []


def in_week(rec, lo, hi):
    d = str(rec.get('date') or '')[:10]
    return lo <= d <= hi


def pct(a, b, nd=1):
    return round(a / b * 100, nd) if b else 0.0


def r1(v):
    return round(v, 1)


# ────────────────────────────── 客服与导诊部
def build_service(lo, hi, plo, phi):
    cb = load_extra('service-callback')
    vl = load_extra('service-visitlog')
    wl = load_extra('service-workload')

    cur, pre = [r for r in cb if in_week(r, lo, hi)], [r for r in cb if in_week(r, plo, phi)]
    ca = [r for r in cur if r.get('arrived') == '是']
    pa = [r for r in pre if r.get('arrived') == '是']

    def by_staff(recs):
        g = defaultdict(lambda: {'n': 0, 'a': 0, 'sc': []})
        for r in recs:
            k = r.get('staff') or '未署名'
            g[k]['n'] += 1
            if r.get('arrived') == '是':
                g[k]['a'] += 1
            if r.get('score') is not None:
                try:
                    g[k]['sc'].append(float(r['score']))
                except (TypeError, ValueError):
                    pass
        return g

    gc, gp = by_staff(cur), by_staff(pre)
    names = sorted(gc, key=lambda k: (-gc[k]['n'], k))
    rows = []
    for k in names:
        v = gc[k]
        avg = sum(v['sc']) / len(v['sc']) if v['sc'] else 0
        prev_n = gp[k]['n'] if k in gp else 0
        d = ('较上周 %+d 条' % (v['n'] - prev_n)) if prev_n else '上周无记录'
        rows.append({'name': k, 'metric': '%d 条 · 到院 %d（%.1f%%）· 均分 %.2f · %s'
                     % (v['n'], v['a'], pct(v['a'], v['n']), avg, d), 'score': v['n']})

    vcur, vpre = [r for r in vl if in_week(r, lo, hi)], [r for r in vl if in_week(r, plo, phi)]
    vc = Counter(r.get('staff') or '未署名' for r in vcur)
    vp = Counter(r.get('staff') or '未署名' for r in vpre)
    vrows = [{'name': k, 'metric': '%d 条%s' % (n, ('（上周 %d）' % vp[k]) if vp.get(k) else ''),
              'score': n} for k, n in vc.most_common()]

    wcur, wpre = [r for r in wl if in_week(r, lo, hi)], [r for r in wl if in_week(r, plo, phi)]

    def wagg(recs):
        g = defaultdict(lambda: {'d': 0, 'du': 0.0, 'ex': 0.0, 'va': 0.0, 't': 0.0})
        for r in recs:
            k = r.get('staff') or '未署名'
            g[k]['d'] += 1
            g[k]['du'] += r.get('dutyScore') or 0
            g[k]['ex'] += r.get('extraScore') or 0
            g[k]['va'] += r.get('valueScore') or 0
            g[k]['t'] += r.get('total') or ((r.get('dutyScore') or 0) + (r.get('extraScore') or 0) + (r.get('valueScore') or 0))
        return g

    wc, wp = wagg(wcur), wagg(wpre)

    def dayavg(v):
        return (v['t'] / v['d']) if v['d'] else 0.0

    wk_rows = []
    # 排序键＝日均分（总分 ÷ 在岗天数）。按周总分排会让在岗天数多的人天然靠前，
    # 等于把天数当权重；在岗天数只在说明里作可比性提示。
    for k in sorted(wc, key=lambda z: (-dayavg(wc[z]), z)):
        v = wc[k]
        prevd = wp[k]['d'] if k in wp else 0
        wk_rows.append({'name': k,
                        'metric': '日均 %.1f 分 · 在岗 %d 天 · 总分 %.0f（履职 %.0f / 附加 %.0f / 增值 %.0f）%s'
                                  % (dayavg(v), v['d'], v['t'], v['du'], v['ex'], v['va'],
                                     ('　在岗较上周 %+d 天' % (v['d'] - prevd)) if prevd or v['d'] else ''),
                        'score': r1(dayavg(v))})

    rankGroups = [
        {'title': '① 导医回访排名（本周 %s · 客服导诊部台账）' % _rng(lo, hi),
         'note': '来源：《医院客服与导诊部》「标准化回访台账」逐条记录。本周合计 <b>%d 条</b>、'
                 '到院 <b>%d 人</b>（到院率 %.1f%%）；上周 %s 为 %d 条 / 到院 %d 人（%.1f%%）。'
                 '⚠ 线上汇报表另记「随访 179 人次 / 到院 42 人（23.5%%）」，与台账口径不同，两者不互校。'
                 % (len(cur), len(ca), pct(len(ca), len(cur)),
                    _rng(plo, phi), len(pre), len(pa), pct(len(pa), len(pre))),
         'rows': rows},
        {'title': '② 导诊主动服务排名（本周 %s）' % _rng(lo, hi),
         'note': '口径＝导医主动迎送、协助、宣教等主动服务条数。本周合计 <b>%d 条</b>，'
                 '上周 %s 为 %d 条。' % (len(vcur), _rng(plo, phi), len(vpre)),
         'rows': vrows or [{'name': '—', 'metric': '本周暂无记录', 'score': 0, 'missing': True}]},
        {'title': '③ 导医日工作量排名（本周 %s · 按日均分）' % _rng(lo, hi),
         'scoreLabel': '日均分',
         'note': '来源：「日工作量考核表(分级)」。单日总分 = 履职分 ＋ 附加分 ＋ 增值分。'
                 '本周合计 <b>%d 人日 / %s 分</b>，上周 %s 为 %d 人日 / %s 分。'
                 '<b>名次按「日均分」（总分 ÷ 在岗天数）排序</b>——按周总分排会让在岗天数多的人'
                 '天然靠前，等于用天数当权重；在岗天数只作可比性提示，不计入排名。'
                 % (len(wcur), '{:,.0f}'.format(sum(v['t'] for v in wc.values())),
                    _rng(plo, phi), len(wpre), '{:,.0f}'.format(sum(v['t'] for v in wp.values()))),
         'rows': wk_rows or [{'name': '—', 'metric': '本周暂无记录', 'score': 0, 'missing': True}]},
    ]

    metrics = {
        'callback': len(cur), 'arrived': len(ca), 'arriveRate': pct(len(ca), len(cur)),
        'callbackPrev': len(pre), 'arrivedPrev': len(pa), 'arriveRatePrev': pct(len(pa), len(pre)),
        'visitlog': len(vcur), 'visitlogPrev': len(vpre),
        'workloadDays': len(wcur), 'workloadScore': sum(v['t'] for v in wc.values()),
        'workloadDaysPrev': len(wpre), 'workloadScorePrev': sum(v['t'] for v in wp.values()),
        'callbackDelta': (r1(pct(len(cur) - len(pre), len(pre))) if pre else None),
        'arrivedDelta': (r1(pct(len(ca) - len(pa), len(pa))) if pa else None),
        'visitlogDelta': (r1(pct(len(vcur) - len(vpre), len(vpre))) if vpre else None),
        'workloadDelta': (r1(pct(sum(v['t'] for v in wc.values()) - sum(v['t'] for v in wp.values()),
                                 sum(v['t'] for v in wp.values()))) if wpre else None),
    }
    return rankGroups, metrics


def _rng(lo, hi):
    a, b = lo[5:].replace('-', '.'), hi[5:].replace('-', '.')
    return '%s—%s' % (a, b)


def _psy_vals(agg, days, nm):
    a = agg.get(nm) or {}
    return (sum(a.get(f, 0) for f in wr.CONTACT_F),
            sum(a.get(f, 0) for f in wr.ADVICE_F),
            sum(a.get(f, 0) for f in wr.PARENT_F),
            len(days.get(nm) or ()))


def _rows_by(agg, days, prev, prev_days, kind):
    """kind: advice 咨询量 / days 填报天数（填报天数只作提示，不排序）"""
    out = []
    for nm in wr.PSY_NAMES:
        c, q, p, d = _psy_vals(agg, days, nm)
        if not (c or q or d):
            out.append({'name': nm, 'metric': '本周未填报', 'score': 0, 'missing': True})
            continue
        sc = q if kind == 'advice' else d
        # 业务量前置，填报天数后置并标注为提示 —— 不让它看起来像权重
        m = ('咨询 %d · 接触 %d　填报 %d 天（提示）' % (q, c, d)) if kind == 'advice' \
            else ('填报 %d 天 · 接触 %d · 咨询 %d' % (d, c, q))
        if prev is not None:
            pc, pq, _, pd = _psy_vals(prev, prev_days or {}, nm)
            pv = pq if kind == 'advice' else pd
            if kind == 'advice':
                m += ('　上周 %d' % pv) if pv else '　上周无'
            else:
                m += ('　上周填报 %d 天' % pv) if pv else '　上周无'
        out.append({'name': nm, 'metric': m, 'score': sc})
    if kind != 'days':
        # 不排名组按名册顺序列出，避免"按天数列序"再次变成隐形排名
        out.sort(key=lambda r: (r.get('missing', False), -r['score']))
    return out


def _group_rows(lo, hi):
    """团体治疗带领：按主带人归集本周场次与人数"""
    try:
        g = load_extra('psych-group')
    except Exception:
        return [{'name': '—', 'metric': '源表不可读', 'score': 0, 'missing': True}]
    per = defaultdict(lambda: {'n': 0, 'p': 0, 'items': []})
    for x in g:
        if not isinstance(x, dict):
            continue
        d = str(x.get('date') or '')[:10]
        if not (lo <= d <= hi):
            continue
        lead = (x.get('lead') or '未署名').strip() or '未署名'
        cnt = x.get('count')
        cnt = int(cnt) if isinstance(cnt, (int, float)) else 0
        per[lead]['n'] += 1
        per[lead]['p'] += cnt
        per[lead]['items'].append('%s %s' % (d[5:].replace('-', '.'), x.get('theme') or '团体'))
    if not per:
        return [{'name': '—', 'metric': '本周无记录', 'score': 0, 'missing': True}]
    out = []
    for nm, v in sorted(per.items(), key=lambda z: (-z[1]['n'], z[0])):
        out.append({'name': nm, 'metric': '%d 场 · 参加 %d 人 · %s'
                    % (v['n'], v['p'], ' / '.join(v['items'])), 'score': v['n']})
    return out


# ────────────────────────────── 心理组
def build_psych(lo, hi, plo, phi):
    """psy_agg 返回 (a, days)：a[name][列名]=合计，days[name]=填报日期集合"""
    recs = wr.fetch_psy_records()
    cur_a, cur_d = wr.psy_agg(recs, lo, hi)
    pre_a, pre_d = wr.psy_agg(recs, plo, phi)
    cum_a, cum_d = wr.psy_agg(recs, '2026-08-31', hi)

    def stat(agg, days, nm):
        a = agg.get(nm) or {}
        c = sum(a.get(f, 0) for f in wr.CONTACT_F)
        q = sum(a.get(f, 0) for f in wr.ADVICE_F)
        p = sum(a.get(f, 0) for f in wr.PARENT_F)
        return c, q, p, len(days.get(nm) or ())

    def tot(agg, days):
        c = q = p = 0
        for nm in wr.PSY_NAMES:
            x, y, z, _ = stat(agg, days, nm)
            c += x; q += y; p += z
        return {'contact': int(c), 'advice': int(q), 'parent': int(p)}

    def rows_of(agg, days, prev=None, prev_days=None):
        out = []
        for nm in wr.PSY_NAMES:
            c, q, p, d = stat(agg, days, nm)
            if not (c or q or d):
                out.append({'name': nm, 'metric': '本周未填报', 'score': 0, 'missing': True})
                continue
            # 业务量前置，填报天数只作提示
            m = '接触 %d · 咨询 %d　填报 %d 天（提示）' % (c, q, d)
            if prev is not None:
                pc, _, _, _ = stat(prev, prev_days or {}, nm)
                m += ('　上周接触 %d' % pc) if pc else '　上周无'
            out.append({'name': nm, 'metric': m, 'score': int(c)})
        out.sort(key=lambda r: (r.get('missing', False), -r['score']))
        return out

    tc, tp, tcm = tot(cur_a, cur_d), tot(pre_a, pre_d), tot(cum_a, cum_d)
    d_contact = r1(pct(tc['contact'] - tp['contact'], tp['contact'])) if tp['contact'] else None
    d_advice = r1(pct(tc['advice'] - tp['advice'], tp['advice'])) if tp['advice'] else None
    not_filled = [nm for nm in wr.PSY_NAMES if stat(cur_a, cur_d, nm)[3] == 0]

    rankGroups = [
        {'title': '① 患者接触排名（本周 %s · 管理表 V4「咨询师每日简报」）' % _rng(lo, hi),
         'note': '口径＝首次对接 ＋ 床旁支持 ＋ 情绪干预，按自然周归集。本周接触 <b>%d</b> 人次'
                 '（上周 %s 为 %d，%s）；咨询工作量 <b>%d</b>（上周 %d，%s）。%s'
                 % (tc['contact'], _rng(plo, phi), tp['contact'],
                    ('%+.1f%%' % d_contact) if d_contact is not None else '—',
                    tc['advice'], tp['advice'],
                    ('%+.1f%%' % d_advice) if d_advice is not None else '—',
                    ('<b>本周未填报：%s</b>，需先确认为休假还是漏报。' % '、'.join(not_filled)) if not_filled else ''),
         'rows': rows_of(cur_a, cur_d, pre_a, pre_d)},
        {'title': '② 咨询工作量排名（本周 %s）' % _rng(lo, hi),
         'note': '口径＝住院咨询 ＋ 门诊咨询 ＋ 家庭咨询。本周合计 <b>%d</b> 人次，上周 %d（%s）。'
                 '接触看投入面，咨询看实际完成量，两者不合并成总分。'
                 % (tc['advice'], tp['advice'], ('%+.1f%%' % d_advice) if d_advice is not None else '—'),
         'rows': _rows_by(cur_a, cur_d, pre_a, pre_d, 'advice')},
        {'title': '③ 填报完整性核查（不计分 · 不排名）',
         'rankless': True,
         'note': '本组只核对日报是否齐、能不能作可比口径，<b>不产生名次</b>：填报天数不计入任何分值，'
                 '也不参与排序与并列判定，因此本组<b>不按天数列序</b>（按名册顺序列出）。'
                 '<b>本周未填报：%s</b>，需先确认为休假还是漏报。'
                 '要看业务量请看 ① 患者接触 与 ② 咨询工作量，两者与填报天数无关。'
                 % ('、'.join(not_filled) if not_filled else '无'),
         'rows': _rows_by(cur_a, cur_d, pre_a, pre_d, 'days')},
        {'title': '④ 团体治疗带领（本周 %s · 心理科来访数量「团体治疗登记」）' % _rng(lo, hi),
         'note': '按主带人归集。本周 2 场：9.21 团体（冯浩鹏主 / 蔡宜蓉副，1 人）、'
                 '9.24 家长课堂（王沛然，参加人数源表未填）。上周 9.14—9.20 为 3 场 6 人。',
         'rows': _group_rows(lo, hi)},
        {'title': '⑤ 累计排名（自 8.31 起累计 · 看持续贡献）',
         'note': '累计口径与周排名不合并：周排名看当期投入，累计排名看持续贡献。'
                 '累计接触 <b>%d</b>、咨询 <b>%d</b>。' % (tcm['contact'], tcm['advice']),
         'rows': rows_of(cum_a, cum_d)},
    ]
    metrics = {'contact': tc['contact'], 'advice': tc['advice'], 'parent': tc['parent'],
               'contactPrev': tp['contact'], 'advicePrev': tp['advice'],
               'contactDelta': d_contact, 'adviceDelta': d_advice,
               'cumContact': tcm['contact'], 'cumAdvice': tcm['advice'],
               'notFilled': not_filled}
    return rankGroups, metrics


def _rate_rows(agg, prev):
    """按率值降序 —— 不按转住院人数排，否则对接条数多的人天然靠前，等于用条数当率值"""
    out = []
    for nm in wr.GJ_SHEETS.values():
        c = agg.get(nm) or {}
        n = c.get('对接', 0)
        if not n:
            out.append({'name': _short(nm), 'metric': '本周无新增对接记录', 'score': 0, 'missing': True})
            continue
        zi = c.get('住院', 0)
        rate = pct(zi, n)
        m = '%.1f%% · 转住院 %d / 对接 %d' % (rate, zi, n)
        if prev is not None:
            pc = prev.get(nm) or {}
            if pc.get('对接', 0):
                m += '　上周 %.1f%%' % pct(pc.get('住院', 0), pc['对接'])
            else:
                m += '　上周无'
        out.append({'name': _short(nm), 'metric': m, 'score': rate})
    out.sort(key=lambda r: (r.get('missing', False), -r['score']))
    return out


# ────────────────────────────── 管家组
def build_gj(lo, hi, plo, phi):
    all_data = wr.fetch_gj()
    cur = wr.gj_agg(all_data, lo, hi)
    pre = wr.gj_agg(all_data, plo, phi)

    def rows_of(agg, prev=None):
        out = []
        for nm in wr.GJ_SHEETS.values():
            c = agg.get(nm) or {}
            n = c.get('对接', 0)
            if not n:
                out.append({'name': _short(nm), 'metric': '本周无新增对接记录', 'score': 0, 'missing': True})
                continue
            zi = c.get('住院', 0)
            m = '对接 %d · 检查 %d · 物理 %d · 心理 %d · 转住院 %d（%.1f%%）' % (
                n, c.get('检查', 0), c.get('物理', 0), c.get('心理', 0), zi, pct(zi, n))
            if prev is not None:
                pn = (prev.get(nm) or {}).get('对接', 0)
                m += ('　上周 %d' % pn) if pn else '　上周无'
            out.append({'name': _short(nm), 'metric': m, 'score': n})
        out.sort(key=lambda r: (r.get('missing', False), -r['score']))
        return out

    tn = sum((a or {}).get('对接', 0) for a in cur.values())
    pn = sum((a or {}).get('对接', 0) for a in pre.values())
    tz = sum((a or {}).get('住院', 0) for a in cur.values())
    pz = sum((a or {}).get('住院', 0) for a in pre.values())
    S = lambda k: sum((a or {}).get(k, 0) for a in cur.values())
    rankGroups = [
        {'title': '① 管家个人对接排名（本周 %s · 患者有效对接表）' % _rng(lo, hi),
         'note': '来源：《患者有效对接表》一人一表逐条记录，按自然周归集。本周有效对接 '
                 '<b>%d 条</b>、转住院 <b>%d 人</b>（%.1f%%）；上周 %s 为 %d 条 / %d 人（%.1f%%），'
                 '对接环比 <b>%s</b>。个人样本仅十余条，率值只作趋势参考。'
                 % (tn, tz, pct(tz, tn), _rng(plo, phi), pn, pz, pct(pz, pn),
                    ('%+.1f%%' % r1(pct(tn - pn, pn))) if pn else '—'),
         'rows': rows_of(cur, pre)},
        {'title': '② 管家转住院率排名（本周 %s · 按率值）' % _rng(lo, hi),
         'scoreLabel': '率值',
         'note': '率值 = 转住院人数 ÷ 有效对接条数。本组<b>按率值降序</b>——原先按转住院人数排，'
                 '对接条数多的人天然靠前，等于用条数当率值。本周全组 <b>%.1f%%</b>（上周 %.1f%%）。'
                 '⚠ 个人分母仅十余条，增加 1 人即可波动 5—8 个百分点，<b>只作趋势参考，不作绩效排序</b>。'
                 % (pct(tz, tn), pct(pz, pn)),
         'rows': _rate_rows(cur, pre)},
        {'title': '③ 本周项目结构（全组合计）',
         'note': '对接后的项目分布，用于判断转化质量而非只看条数。',
         'rows': [{'name': '检查', 'metric': '本周合计', 'score': int(S('检查'))},
                  {'name': '物理治疗', 'metric': '本周合计', 'score': int(S('物理'))},
                  {'name': '心理咨询', 'metric': '本周合计', 'score': int(S('心理'))},
                  {'name': '转住院', 'metric': '本周合计', 'score': int(tz)}]},
    ]
    metrics = {'deal': tn, 'dealPrev': pn, 'admit': tz, 'admitPrev': pz,
               'rate': pct(tz, tn), 'ratePrev': pct(pz, pn),
               'delta': (r1(pct(tn - pn, pn)) if pn else None)}
    return rankGroups, metrics


def _short(nm):
    return nm.replace('(婧姐)', '')


# ────────────────────────────── main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week-start', default=None)
    ap.add_argument('--out', default=os.path.join(REPO, 'data', 'rankings.json'))
    a = ap.parse_args()

    if a.week_start:
        ws = a.week_start
    else:
        mon = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
        ws = mon.isoformat()
    lo, hi = wr.week_bounds(ws)
    plo, phi = wr.prev_week(ws)
    today = dt.date.today().isoformat()

    print('本周 %s — %s ｜ 上周 %s — %s' % (lo, hi, plo, phi))
    out = {'week': {'lo': lo, 'hi': hi}, 'prev': {'lo': plo, 'hi': phi},
           'asOf': today, 'depts': {}}

    for key, fn in [('service', build_service), ('psychology', build_psych), ('marketing', build_gj)]:
        try:
            rg, mt = fn(lo, hi, plo, phi)
            out['depts'][key] = {'rankGroups': rg, 'metrics': mt}
            print('  ✓ %-12s 排名组 %d ｜ %s' % (key, len(rg), json.dumps(mt, ensure_ascii=False)[:150]))
        except Exception as e:
            print('  ✗ %-12s 失败：%s' % (key, e))
            out['depts'][key] = {'error': str(e)}

    io.open(a.out, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('已写 %s' % a.out)


if __name__ == '__main__':
    main()
