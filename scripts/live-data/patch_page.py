#!/usr/bin/env python3
"""按 data/snapshot.json 刷新 index.html 的静态兜底数据（部门卡 / 部门摘要 / 页脚口径）。

原则：
- 只改「数值与口径说明」，不动 DOM 结构、不动历史对比正文；
- 每次写入新的一行「本期」指标，保留原有历史行；
- 同一行重复执行不会叠加（用 marker 检测）。
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML = os.path.join(ROOT, "index.html")
SNAP = json.load(open(os.path.join(ROOT, "data", "snapshot.json"), encoding="utf-8"))
MARK = "[[AUTO-DEPT]]"

# 医生周排名（出院结账口径的个人表，由 extract_doctor_rank.py 从《周排名分析_*.xlsx》抽出）
_DRK = os.path.join(ROOT, "data", "doctor-rank.json")
DRK = json.load(open(_DRK, encoding="utf-8")) if os.path.exists(_DRK) else {}
DRT = DRK.get("totals") or {}
DRR = DRK.get("rows") or []
DR_TOP = DRR[0] if DRR else {}

P = SNAP["period"]
LBL = P["label"]
DT = P["dataThrough"][5:].replace("-", ".")
N = P["daysRecorded"]
PW = SNAP["previousPeriod"]["compareSameDaysEnd"][5:].replace("-", ".")
PS = SNAP["previousPeriod"]["start"][5:].replace("-", ".")


def sgn(v):
    if v is None:
        return "—"
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.1f}"


def _dd_span(html):
    """返回 `const deptDaily={` 到其后下一个 `const ` 之间的区间（半开）。

    ⛔ 2026-10-24 事故复盘：原来用 r"nursing:\\{[\\s\\S]*?\\n      psychology:\\{" 直接在全文
      搜索，命中的其实是 `const departments` 里的 `nursing:{`，一次替换就毁掉了
      departments / signals / tasks / DEPT_CARD 等大段内容。所有对 deptDaily 的改写
      都必须先收敛到本函数给出的区间内。
    """
    i = html.find("const deptDaily={")
    if i < 0:
        return None, None
    j = html.find("const ", i + 20)
    if j < 0:
        return None, None
    return i, j


def replace_dept_daily_key(html, key, nxt, body):
    """把 deptDaily 里 `<key>:{...}` 整块替换为 body（保留后面的 `<nxt>:{`）。"""
    i, j = _dd_span(html)
    if i is None:
        print(f"  ⚠ 未找到 const deptDaily，deptDaily.{key} 跳过")
        return html
    seg = html[i:j]
    # ⛔ 分隔符必须宽松匹配：历史补丁写出来的缩进并不统一（实测出现过 `}, \nnursing:{`
    #    这种「逗号+空格+换行、无缩进」的形态），写死 `\n      ` 会直接锚不到。
    pat = re.compile(key + r":\{[\s\S]*?,\s*" + nxt + r":\{")
    m = pat.search(seg)
    if not m:
        print(f"  ⚠ deptDaily.{key} 锚点未命中")
        return html
    new_seg = seg[:m.start()] + key + ":" + body + ",\n      " + nxt + ":{" + seg[m.end():]
    return html[:i] + new_seg + html[j:]


m = SNAP["metrics"]
psy = SNAP["psych"]
svc = SNAP["service"]
but = SNAP["butler"]
dep = SNAP["departments"]

# 本周（10.19—10.25）卡片口径 —— 全部由快照驱动，且必须反映「填报到哪一天」。
# ⛔ 2026-10-24：汇报表五个部门表头整周未滚动（值 = 正文第 3 周 = 上一周），
#    故本周卡片一律不引用汇报表表头，改用各自真正在跑的明细表；缺的写 null 并注明「本周未提交」。
_stale = dep["week"].get("stale")
_nur = dep["nursing"]
_svc = dep["service"]
_doc_ledger = [x for x in SNAP["daily"] if P["start"] <= x["date"] <= P["end"]]

dept_cards = {
    "doctor": {
        "m1": ("本期营收", m["weekRevenue"]["value"], "万"),
        "m2": ("本期门诊", m["weekVisits"]["value"], "人次"),
        "trend": [x["discharge"] if x["discharge"] is not None else None for x in _doc_ledger],
        "axis": "d1019",
        "note": (f"<b>本周（{LBL}）取营收日报逐日台账，已录 {N} 天（{P['start'][5:]}—{DT}）</b>："
                 f"营收 <b>{m['weekRevenue']['value']}</b> 万（门诊 {m['weekOutpatient']['value']} 万 ＋ "
                 f"在院 {m['weekInpatient']['value']} 万）、门诊 <b>{m['weekVisits']['value']}</b> 人次、"
                 f"入院 <b>{m['weekAdmit']['value']}</b> 人、出院 <b>{m['weekDischarge']['value']}</b> 人、"
                 f"在院 <b>{m['wardCount']['value']}</b> 人（{DT} 时点）。"
                 f"上期同 {N} 天：营收 {dep['compareWeek']['revenueWan']} 万、门诊 {dep['compareWeek']['outpatient']} 人次、"
                 f"入院 {dep['compareWeek']['admit']} 人、出院 {dep['compareWeek']['discharge']} 人。"
                 f"⚠⚠ <b>《特别行动小组汇报表》医生组表头本周未滚动</b>——表头四项与正文「第 3 周」列逐项同值，"
                 f"说明整表还停在上一期，按「缺项不拿旧值顶替」一律不引用，原值存档在 departments.actionReportRaw。"
                 f"物理治疗费无逐日台账，本期留空待补。"
                 + (f"<br><b>本周个人周排已到位（10.19–10.25 · 出院结账口径）</b>："
                    f"{len(DRR)} 名医生、出院 <b>{DRT.get('discharge')}</b> 人、在院 "
                    f"<b>{DRT.get('inWard')}</b> 人（10.25 时点）、个人业绩合计 "
                    f"<b>{DRT.get('revenue', 0) / 10000:.2f} 万</b>、新入 {DRT.get('admit')} 人；"
                    f"<b>{DR_TOP.get('name', '—')}</b> 以 {DR_TOP.get('revenue', 0) / 10000:.2f} 万、"
                    f"{DR_TOP.get('discharge')} 人出院、{DR_TOP.get('inWard')} 人在管居首，"
                    f"排名指数 {DR_TOP.get('index')}。点开本卡「排名」页看 6 人明细。"
                    if DRR else "")),
    },
    "nursing": {
        "m1": ("物理治疗人数", None, "本周未提交"),
        "m2": ("6 项治疗完成率", None, "本周未提交"),
        "trend": None,
        "axis": None,
        "note": ("⚠⚠ <b>护理部本周（" + LBL + "）未提交</b>：周报与物理治疗逐日表最新只到 "
                 + str(_nur.get("weeklyThrough") or "—") + "，本期没有任何一条护理事实入库，"
                 "故「物理治疗人数 / 六项治疗完成率 / 工娱」三项<b>全部留空</b>，"
                 "不拿上一期的数字与 93% 完成率顶替。"
                 "汇报表护理组表头本周同样未滚动（与上一期逐项同值），已不引用。"
                 "→ 需护理部补报 10.19—10.24 的物理治疗逐日表与六项治疗应做/实做。"),
    },
    "psychology": {
        "m1": ("咨询工作量", dep["psychology"]["consult"], "人次"),
        "m2": ("患者接触", dep["psychology"]["contact"], "人次"),
        "trend": [psy["daily"][k] for k in sorted(psy.get("daily", {}))],
        "axis": "dpsy7",
        "note": (f"<b>本周心理科以 V4 管理表为唯一口径</b>（汇报表心理咨询组表头自 2026-09-21 起"
                 f"未滚动、与上一期逐项同值，<b>已停用</b>，原值存档可查）。"
                 f"V4「咨询师每日简报」逐条汇总（{LBL}，数据至 {SNAP['watermarks']['psych']['dataThrough'][5:]}）："
                 f"患者接触 <b>{psy['week']['contact']}</b> 人次（24h 首次 {psy['week']['first']} ＋ "
                 f"情绪支持 {psy['week']['emotion']} ＋ 住院 {psy['week']['inpatient']}）、"
                 f"咨询工作量 <b>{psy['week']['consult']}</b> 人次（住院 {psy['week']['inpatient']} ＋ 门诊 "
                 f"{psy['week']['outpatient']} ＋ 家庭 {psy['week']['family']}）、家长访谈 {psy['week']['parent']}、"
                 f"团体 {psy['week']['groupSessions']} 场 / {psy['week']['groupPeople']} 人次；"
                 f"日报 {psy['week']['report']} 条填报；管床本周新增 <b>{psy.get('boundWeek', {}).get('rows', 0)} 行 / "
                 f"{psy.get('boundWeek', {}).get('people', 0)} 名患者</b>，累计在管 {psy.get('boundPatients', 0)} 人。"
                 f"上期同天数：接触 {psy['prevSameDays']['contact']}、咨询 {psy['prevSameDays']['consult']}。"),
    },
    "service": {
        "m1": ("回访条数", svc["week"]["followup"], "条"),
        "m2": ("标注到院率", svc["week"]["rate"], "%"),
        "trend": [svc["daily"][k] for k in sorted(svc.get("daily", {}))],
        "axis": "dsvc5",
        "note": (f"客服服务部本周（{LBL}）以三张台账为准，数据至 "
                 f"{SNAP['watermarks']['service']['dataThrough'][5:]}（{SNAP['watermarks']['service']['days']} 天）："
                 f"标准化回访 <b>{svc['week']['followup']}</b> 条、标注到院 <b>{svc['week']['arrived']}</b> 人"
                 f"（<b>{svc['week']['rate']}%</b>）、导诊主动服务 <b>{svc['week']['guide']}</b> 条、"
                 f"日工作量 <b>{svc['week']['workload']:,}</b> 分。上期同 {SNAP['watermarks']['service']['days']} 天："
                 f"回访 {svc['prevSameDays']['followup']} 条 / 到院 {svc['prevSameDays']['arrived']} 人"
                 f"（{svc['prevSameDays']['rate']}%）/ 主动服务 {svc['prevSameDays']['guide']} 条 / "
                 f"工作量 {svc['prevSameDays']['workload']:,} 分。"
                 f"⚠ 汇报表客服组表头本周未滚动（与上一期同值），已不引用；"
                 f"「随访人数」一栏历来为空，记 null 不拿台账顶替。"),
    },
    "marketing": {
        "m1": ("管家对接", but["week"]["contact"], "条"),
        "m2": ("转住院率", but["week"]["rate"], "%"),
        "trend": [v for _, v in but["staff"]],
        "axis": "dbutler",
        "note": (f"{LBL}（数据至 {SNAP['watermarks']['butler']['dataThrough'][5:]}，"
                 f"{SNAP['watermarks']['butler']['days']} 天）《患者有效对接表》各管家分表逐条：有效对接 "
                 f"<b>{but['week']['contact']}</b> 条、转住院 <b>{but['week']['admit']}</b> 人"
                 f"（<b>{but['week']['rate']}%</b>）——"
                 + " · ".join(f"{k} {v}" for k, v in but["staff"]) +
                 f"。上期同 {SNAP['watermarks']['butler']['days']} 天 {but['prevSameDays']['contact']} 条 / "
                 f"{but['prevSameDays']['admit']} 人（{but['prevSameDays']['rate']}%）。"
                 + (f"⚠ {'、'.join(but['missingStaff'])} 本周无任何对接记录，按契约记 null、<b>不按 0 降榜</b>。"
                    if but["missingStaff"] else "")
                 + "营销中心表头的入院/门诊/总收入本周整行空白，按契约不显示、也不拿其他源代替。"),
    },
}


def find_div_end(html, start):
    """从 <div ...> 的起点找到配对的 </div> 结束位置（含）。"""
    i = start
    depth = 0
    while i < len(html):
        nxt_open = html.find("<div", i)
        nxt_close = html.find("</div>", i)
        if nxt_close == -1:
            raise ValueError("div 未闭合")
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
        else:
            depth -= 1
            i = nxt_close + 6
            if depth == 0:
                return i
    raise ValueError("div 未闭合")


def render_kpis():
    def tile(dept, label, value, unit, delta=None, cls=""):
        d = f'<span class="kpi-delta {cls}">{delta}</span>' if delta else ""
        onclick = f' onclick="openDeptV2(\'{dept}\')"' if dept else ""
        return (f'<div class="kpi-tile"{onclick}><label>{label}</label>'
                f'<strong>{value}<em>{unit}</em></strong>{d}</div>')

    def dcls(v):
        return "up" if (v or 0) > 0 else "down" if (v or 0) < 0 else ""

    arr_prev = SNAP["arrival"]["prevSameDays"]
    arr_cur = SNAP["arrival"]["week"]
    arr_delta = round((arr_cur - arr_prev) / arr_prev * 100, 1) if arr_prev else None
    psy_prev, psy_cur = psy["prevSameDays"]["contact"], psy["week"]["contact"]
    psy_d = round((psy_cur - psy_prev) / psy_prev * 100, 1) if psy_prev else None
    svc_prev, svc_cur = svc["prevSameDays"]["followup"], svc["week"]["followup"]
    svc_d = round((svc_cur - svc_prev) / svc_prev * 100, 1) if svc_prev else None
    but_prev, but_cur = but["prevSameDays"]["contact"], but["week"]["contact"]
    but_d = round((but_cur - but_prev) / but_prev * 100, 1) if but_prev else None

    def pct(v):
        return None if v is None else (("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.1f}%")

    _ts = dep["nursing"].get("treatSummary") or {}
    _nur_tile = (f'{_ts["rate"]}%', f'{_ts.get("done")}/{_ts.get("due")}', "flat") if _ts.get("due") \
        else ("—", "本周未提交", "flat")
    tiles = [
        tile("doctor", f"本期营收（{LBL} · {N} 天）", m["weekRevenue"]["value"], "万元",
             pct(m["weekRevenue"]["deltaPct"]), dcls(m["weekRevenue"]["deltaPct"])),
        tile("doctor", "门诊人次（营收日报）", m["weekVisits"]["value"], "人次",
             pct(m["weekVisits"]["deltaPct"]), dcls(m["weekVisits"]["deltaPct"])),
        tile("doctor", "本期入院", m["weekAdmit"]["value"], "人", pct(m["weekAdmit"]["deltaPct"]),
             dcls(m["weekAdmit"]["deltaPct"])),
        tile("doctor", "本期出院", m["weekDischarge"]["value"], "人", pct(m["weekDischarge"]["deltaPct"]),
             dcls(m["weekDischarge"]["deltaPct"])),
        tile("doctor", "物理治疗费（无逐日台账）",
             "—" if m["weekPhysio"]["value"] is None else m["weekPhysio"]["value"],
             "" if m["weekPhysio"]["value"] is None else "万元",
             None if m["weekPhysio"]["value"] is None else pct(m["weekPhysio"]["deltaPct"]),
             "flat" if m["weekPhysio"]["value"] is None else dcls(m["weekPhysio"]["deltaPct"])),
        tile("doctor", "在院人数（时点）", m["wardCount"]["value"], "人"),
        tile("nursing", "护理 6 项治疗完成率", _nur_tile[0], "%", _nur_tile[1], _nur_tile[2]),
        tile("psychology", "心理 咨询工作量", dep["psychology"]["consult"], "人次",
             f'接触 {dep["psychology"]["contact"]}', "flat"),
        tile("service", "客服 标注到院", svc["week"]["arrived"], "人次",
             f'{svc["week"]["rate"]}%', "flat"),
        tile("marketing", "管家 有效对接", but_cur, "条", pct(but_d), dcls(but_d)),
        tile("", "10 月累计 / 目标", f'{m["monthRevenue"]["value"]}', f'万 / {m["monthRevenue"]["targetWan"]} 万',
             f'{m["monthRevenue"]["amountProgress"]}%（时间 {m["monthRevenue"]["timeProgress"]}%）', "flat"),
    ]
    return "".join(tiles)


def patch_dept_daily_psych(html, snap):
    """抽屉「数据变化」页的心理块（deptDaily.psychology）按快照重写。

    ⛔ 原块整段是 10.1—10.7 的历史硬编码（接触 65 / 咨询 39 / 四人排名 / 累计 356-198 /
       「应填未填 2 处」），在本周语境下会与部门卡的 40 人同屏矛盾，且那些旧账早已过期。
       改为按 data/snapshot.json 生成：汇报表表头五数 + V4 五人周明细 + 对接表本周新增 + 对账差额。
    """
    p = snap["psych"]
    w = p["week"]
    dp = snap["departments"]["psychology"]
    sw = p.get("staffWeek") or []
    bw = p.get("boundWeek") or {}
    rc = p.get("recon") or []
    ws = p.get("weekSum") or {}

    rows = [[x["name"], str(x["emotion"] or 0), str(x["inpatient"] or 0),
             str(x["outpatient"] or 0), str(x["parent"] or 0),
             str(x["report_days"] or 0), f'{int(x["rate"] or 0)}%'] for x in sw]
    sumr = ["5 人合计", str(ws.get("emotion", 0)), str(ws.get("inpatient", 0)),
            str(ws.get("outpatient", 0)), str(ws.get("parent", 0)),
            str(ws.get("report_days", 0)), f'{round(sum((x["rate"] or 0) for x in sw) / max(1, len(sw)))}%']

    by = bw.get("byStaff") or []
    by_txt = "、".join(f'{x["name"]} {x["rows"]} 行 / {x["people"]} 人' for x in by) or "—"
    gaps = [r for r in rc if r["gap"]]
    gap_txt = "、".join(f'{r["label"]} {r["gap"]:+d}' for r in gaps) or "无"

    _psy_end = str(snap["watermarks"]["psych"]["dataThrough"] or "")[5:].replace("-", ".")
    _psy_days = snap["watermarks"]["psych"]["days"]
    _rank = [x for x in (p.get("rank") or []) if (x.get("consult") or 0) > 0]
    _psy_top = _rank[0]["name"] if _rank else "—"
    _psy_top_v = _rank[0]["consult"] if _rank else 0
    _rates = [x["rate"] for x in sw if x.get("rate") is not None]
    _psy_rate_rng = f"{min(_rates):.0f}%—{max(_rates):.0f}%" if _rates else "—"
    _psy_ppl = len(_rank)
    obj = {
        "range": f"本期 {LBL}（V4 管理表 · 日报逐条汇总，{_psy_days} 天，数据至 {_psy_end}）",
        "metrics": [
            ["咨询工作量", f'{w["consult"]} 人次'],
            ["患者接触", f'{w["contact"]} 人次'],
            ["家长访谈", f'{w["parent"]} 人次'],
            ["团体", f'{w["groupSessions"]} 场 / {w["groupPeople"]} 人'],
            ["管床新增", f'{bw.get("rows", 0)} 行 / {bw.get("people", 0)} 人'],
        ],
        "list": {
            "title": "咨询师个人周工作统计（本期 " + LBL + " · 组长自动汇总表）",
            "sub": "源：V4「周个人统计」，组长只调周起始日、数值由《咨询师每日简报》公式汇出",
            "cols": ["咨询师", "情绪支持", "住院咨询", "门诊咨询", "家长访谈", "填报天", "完整率"],
            "gt": "1.15fr .8fr .8fr .8fr .8fr .92fr 1fr",
            "num": [1, 2, 3, 4, 5, 6],
            "warn": [],
            "rows": rows,
            "sum": sumr,
            "note": "⚠ <b>「周个人统计」与「日报逐条」两套汇总对不上</b>，差额：" + gap_txt +
                    "。<b>周个人统计</b>是组长按周汇总、数值由《咨询师每日简报》公式汇出，"
                    "含查房、首次对接等日报之外的条目；<b>日报逐条</b>只统计当周新填的简报行。"
                    "两者口径不同、<b>不可互相校验、也不做四舍五入拉平</b>；"
                    "本页一律以<b>日报逐条</b>为准，周表仅用于看个人分布。",
        },
        "note": "<b>本周心理科只有一个口径：V4 管理表（日报逐条 + 周个人统计 + 管床对接）。</b>"
                f"患者接触 <b>{w['contact']}</b> 人次（24h 首次 {w['first']} ＋ 情绪支持 {w['emotion']} ＋ 住院 {w['inpatient']}）、"
                f"咨询工作量 <b>{w['consult']}</b> 人次（住院 {w['inpatient']} ＋ 门诊 {w['outpatient']} ＋ "
                f"家庭 {w['family']}）、家长访谈 {w['parent']} 人次、"
                f"团体 {w['groupSessions']} 场 {w['groupPeople']} 人；日报 <b>{w['report']}</b> 条，"
                f"数据至 <b>{_psy_end}</b>（{_psy_days} 天）。"
                f"<br><b>⚠ 汇报表表头已停用：</b>心理组表头 {dp.get('header', {}).get('people')} 人 / "
                f"{dp.get('header', {}).get('groupSessions')} 场 / "
                f"{'{:,}'.format(dp.get('header', {}).get('revenueYuan') or 0)} 元是 <b>{dp.get('headerAsOf')}</b> 抓取值，"
                f"此后一直未滚动（团辅 4 场 vs 本周 {w['groupSessions']} 场就是最直接的证据）。"
                f"按「缺项不拿旧值顶替」，本周改用 V4 唯一可核口径，旧值仅存档、不参与展示。"
                f"<br><b>管床对接：本周新增 {bw.get('rows', 0)} 行 / {bw.get('people', 0)} 名患者</b>"
                f"（{by_txt}），累计在管 <b>{p.get('boundPatients', 0)}</b> 人。"
                "<br><b>⚠ 对账差额：</b>" + gap_txt + "，原因见上表注释；不做四舍五入、不互相覆盖。",
        "diag": "<div class=\"diagnosis-item tone-risk\"><b>本周判断 · 工作量集中在 1 人，日报填报是短板</b>"
                f"<p>{_psy_ppl} 名有工作量的咨询师本周情绪支持 <b>{w['emotion']}</b> 人次、住院咨询 <b>{w['inpatient']}</b> 人次、"
                f"门诊咨询 <b>{w['outpatient']}</b> 人次、家长访谈 <b>{w['parent']}</b> 人次；"
                f"<b>{_psy_top}</b> 一人咨询 {_psy_top_v} 人次（占全组 "
                f"{round(_psy_top_v / max(1, w['consult']) * 100)}%），是本周绝对主力。"
                f"但 {_psy_days} 天窗口内全组只填了 <b>{w['report']}</b> 条日报，"
                f"个人完整率 {_psy_rate_rng}——<b>数据可用性比工作量更值得关注</b>。</p></div>"
                "<div class=\"diagnosis-item tone-orange\"><b>两套汇总对不上，是本组的老问题</b>"
                "<p>「周个人统计」按公式汇总 21 天填报，日报逐条只有 "
                f"{w['report']} 条——差额来自查房、首次对接等不进日报的条目。"
                "本页统一以<b>日报逐条</b>为准，周表只看个人相对分布，<b>两者不可互相校验</b>。</p></div>"
                "<div class=\"diagnosis-item tone-risk\"><b>管床在管人数已到 50，需确认名册</b>"
                f"<p>按对接表「未填出院日期」计，累计在管 <b>{p.get('boundPatients', 0)}</b> 人，"
                f"本周新增 {bw.get('rows', 0)} 行 / {bw.get('people', 0)} 人。"
                "建议本周内核对一次名册，确认已出院但未填出院日期的记录，避免在管数虚高。</p></div>",
    }
    body = json.dumps(obj, ensure_ascii=False).replace('"', "'")
    # 与 nursing 同理：必须限制在 const deptDaily 内部，否则会命中 const departments 里的同名键
    return replace_dept_daily_key(html, "psychology", "service", body)


def patch_dept_daily_nursing(html, dep):
    """抽屉「数据变化」页的护理块（deptDaily.nursing）按快照重写。

    ⛔ 2026-10-24：护理部本周未提交（周报 / 逐日表都停在上一期），原实现直接取
      treatSummary.worst 会 TypeError，而且在「没数据」时仍把上一期 93% 画出来。
      现在分两支：有本周数据 → 照旧逐项列；没有 → 明确写「本周未提交」并留空，
      不拿上一期数字顶替。
    """
    n = dep["nursing"]
    ts = n.get("treatSummary") or {}
    has_week = bool(ts.get("due"))

    if not has_week:
        obj = {
            "range": "本期 10.19—10.25（护理部周报 · 本周未提交）",
            "metrics": [
                ["6 项治疗完成率", "—"],
                ["应做 / 实做", "—"],
                ["未做", "—"],
                ["最低项目", "—"],
                ["本周提交", "0 份"],
            ],
            "list": {
                "title": "物理治疗 6 项完成情况（本周无数据）",
                "sub": "护理部周报与《质控分及物理治疗数据》逐日表均未覆盖 10.19—10.24",
                "cols": ["治疗项目", "应做", "实做", "完成率"],
                "gt": "1.7fr 1fr 1fr 1fr",
                "num": [1, 2, 3],
                "warn": [0, 0, 3],
                "rows": [],
                "sum": ["6 项合计", "—", "—", "—"],
                "note": "⚠ 本周（10.19—10.25）护理部没有提交数据，本表<b>留空</b>，"
                        "不拿上一期 606/656＝93% 顶替。汇报表护理组表头（484 人次 / 5 场 / 62 人次）"
                        "也与上周逐项同值、未滚动，同样不引用。",
            },
            "note": "<b>本周护理无数据</b>。周报最新只到 "
                    + str(n.get("weeklyThrough") or "—") + "，逐日物理治疗表同样停在上一期；"
                    "因此「物理治疗人数 / 六项治疗完成率 / 工娱场次」三项本周全部记 null。"
                    "<b>→ 需护理部补报 10.19—10.24 的逐日表与六项应做/实做。</b>",
            "diag": "<div class=\"diagnosis-item tone-risk\"><b>本周判断 · 数据缺报，无法评价</b>"
                    "<p>护理是本周<b>唯一整块缺报</b>的部门：周报与逐日表都停在上一期，"
                    "本周窗口内 0 条事实。缺报期间不做环比、不排名、不参与绩效核算——"
                    "拿上周 93% 当本周完成率会直接误导派班。</p></div>"
                    "<div class=\"diagnosis-item tone-orange\"><b>补报要求</b>"
                    "<p>① 10.19—10.24 六项治疗应做/实做逐日数；② 物理治疗人数（含住院＋门诊）；"
                    "③ 工娱场次与参与人数。三项补齐后本周才能与医生组、财务口径对齐。</p></div>",
        }
        body = json.dumps(obj, ensure_ascii=False).replace('"', "'")
        return replace_dept_daily_key(html, "nursing", "psychology", body)

    worst = ts["worst"]
    rows = [[t["label"], str(t["due"]), str(t["done"]), f'{t["rate"]}%']
            for t in n["treat"]]
    obj = {
        "range": "本期 " + LBL + "（护理部周报 · 项目口径）",
        "metrics": [
            ["6 项治疗完成率", f'{ts["rate"]}%'],
            ["应做 / 实做", f'{ts["due"]} / {ts["done"]}'],
            ["未做", f'{ts["missed"]} 人次'],
            ["最低项目", f'{worst["label"]} {worst["rate"]}%'],
            ["达标项目", "0 / %d 项" % ts["items"]],
        ],
        "list": {
            "title": "物理治疗 6 项完成情况（本期 " + LBL + " · 护理部周报）",
            "sub": "源：护理部本周报送的应做 / 实做人次",
            "cols": ["治疗项目", "应做", "实做", "完成率"],
            "gt": "1.7fr 1fr 1fr 1fr",
            "num": [1, 2, 3],
            "warn": [0, 0, 3],
            "rows": rows,
            "sum": ["6 项合计", str(ts["due"]), str(ts["done"]), f'{ts["rate"]}%'],
            "note": "⚠ 完成率按护理部口径<b>向下取整</b>，与按比值四舍五入最多差 1 个百分点。"
                    "各项未做（应做−实做）：" +
                    "、".join(f"{t['label']} {t['missed']}" for t in n["treat"]) +
                    f"，合计 <b>{ts['missed']}</b> 人次。",
        },
        "note": f"<b>本周（{LBL}）6 项治疗应做 {ts['due']} 人次、实做 {ts['done']} 人次，"
                f"合计完成率 {ts['rate']}%</b>（护理部口径向下取整），未做 {ts['missed']} 人次。",
        "diag": "<div class=\"diagnosis-item tone-risk\"><b>本周判断</b>"
                f"<p>6 项合计 {ts['done']}/{ts['due']}＝<b>{ts['rate']}%</b>，未做 <b>{ts['missed']}</b> 人次；"
                f"最低 {worst['label']} {worst['rate']}%。</p></div>",
    }
    body = json.dumps(obj, ensure_ascii=False).replace('"', "'")
    return replace_dept_daily_key(html, "nursing", "psychology", body)


def js_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _jso(obj):
    """Python dict/list → 单行 JS 字面量（键不加引号、字符串用单引号）。"""
    return json.dumps(obj, ensure_ascii=False).replace('"', "'")


def patch_dept_daily_rest(html, dep, snap):
    """抽屉「数据变化」页的 doctor / service / marketing 三块按快照重写。

    ⛔ 2026-10-24：这三块长期停在 10.12—10.18（医生 72.5 万 / 客服 37 条 / 管家 80 条），
      换期后不重写会把上一周的数和本周同事的新数同屏并排。
      marketing 自带 list（周对照表），一并重生成，否则表里仍是上周三行。
    """
    mm, p, sv, bt = snap["metrics"], snap["psych"], snap["service"], snap["butler"]
    ar = snap["watermarks"]
    _svc_end = ar["service"]["dataThrough"][5:].replace("-", ".")
    _but_end = ar["butler"]["dataThrough"][5:].replace("-", ".")
    _svc_n = ar["service"]["days"]
    _but_n = ar["butler"]["days"]
    prev = snap["previousPeriod"]

    # ---- doctor：营收日报逐日台账 ----
    doctor = {
        "range": (f"本期 {LBL}（营收台账至 {DT} · {N} 天 ／ 个人周排至 2026-10-25 · 出院结账口径）"),
        "metrics": [
            ["本周营收（台账）", f"{mm['weekRevenue']['value']} 万"],
            ["门诊收入", f"{mm['weekOutpatient']['value']} 万"],
            ["在院收入", f"{mm['weekInpatient']['value']} 万"],
            ["门诊人次", f"{mm['weekVisits']['value']} 人次"],
            ["入院", f"{mm['weekAdmit']['value']} 人"],
            ["出院", f"{mm['weekDischarge']['value']} 人"],
            ["在院（{0} 时点）".format(DT), f"{mm['wardCount']['value']} 人"],
            ["物理治疗费", "— （无逐日台账）"],
            ["汇报表表头", "本周未滚动 · 停用"],
        ] + ([["出院（结账 · 至 10.25）", f"{DRT.get('discharge')} 人"],
              ["在院（10.25 时点）", f"{DRT.get('inWard')} 人"],
              ["个人业绩合计", f"{DRT.get('revenue', 0) / 10000:.2f} 万"],
              ["个人周排第一", f"{DR_TOP.get('name')} · {DR_TOP.get('index')}"]]
             if DRR else []),
        "note": (f"<b>本期只认营收日报逐日台账。{LBL} 已录 {N} 天（{P['start'][5:]}—{DT}）："
                 f"营收 {mm['weekRevenue']['value']} 万＝门诊 {mm['weekOutpatient']['value']} 万 ＋ "
                 f"在院 {mm['weekInpatient']['value']} 万，门诊 {mm['weekVisits']['value']} 人次、"
                 f"入院 {mm['weekAdmit']['value']} 人、出院 {mm['weekDischarge']['value']} 人。</b>"
                 f"上期取同一窗口长度（{prev['start'][5:]}—{prev['compareSameDaysEnd'][5:]}，{N} 天）："
                 f"营收 {dep['compareWeek']['revenueWan']} 万、门诊 {dep['compareWeek']['outpatient']} 人次、"
                 f"入院 {dep['compareWeek']['admit']} 人、出院 {dep['compareWeek']['discharge']} 人。"
                 f"<br><b>⚠ 为什么不用《特别行动小组汇报表》表头：</b>本周表头四项（72.5 万 / 19 人 / 210 人次 / 32.9 万）"
                 f"与该表正文「第 3 周」列逐项完全相同，说明整表还停在上一期、没有滚动，"
                 f"直接引用会把上周数字当本周业绩。原值已存档（departments.actionReportRaw），表头补齐后自动切回。"
                 + (f"<br><b>✅ 个人周排（10.19–10.25）已到位：</b>{len(DRR)} 名医生、出院 "
                    f"{DRT.get('discharge')} 人、在院 {DRT.get('inWard')} 人、个人业绩合计 "
                    f"{DRT.get('revenue', 0) / 10000:.2f} 万、新入 {DRT.get('admit')} 人。"
                    f"该表是<b>出院结账</b>口径，与上面的<b>逐日进账</b>不同，<b>禁止相加</b>；"
                    f"但逐日能对上——出院 10.19–10.23 为 4/2/0/2/1＝9 人，与台账完全一致，"
                    f"10.24–10.25 再出 6 人、入 4 人，在院 35→{DRT.get('inWard')}。"
                    f"个人明细见「排名」页三张表（综合排名 / 计分明细 / 业绩构成）。"
                    if DRR else "")),
        "diag": ("<div class=\"diagnosis-item tone-risk\"><b>本周判断 · 收入节奏正常，但报表填报掉了链子</b>"
                 f"<p>{N} 天营收 <b>{mm['weekRevenue']['value']} 万</b>、日均 "
                 f"<b>{round(mm['weekRevenue']['value'] / max(1, N), 2)} 万</b>；"
                 f"门诊 {mm['weekVisits']['value']} 人次、入院 {mm['weekAdmit']['value']} 人、"
                 f"出院 {mm['weekDischarge']['value']} 人，患者池净变化 "
                 f"<b>{mm['weekAdmit']['value'] - mm['weekDischarge']['value']:+d} 人</b>。</p></div>"
                 "<div class=\"diagnosis-item tone-orange\"><b>汇报表整表未滚动，是本周最大的数据风险</b>"
                 "<p>医生组表头四项与正文「第 3 周」列逐项同值，说明报表还停在上周。"
                 "本周已改用营收日报台账，但<b>物理治疗费没有逐日台账</b>，只能留空——"
                 "需财务补一张按日拆分的物理治疗收入表。</p></div>"
                 "<div class=\"diagnosis-item tone-risk\"><b>月度进度要盯住</b>"
                 f"<p>10 月累计 <b>{mm['monthRevenue']['value']} 万</b> / 目标 "
                 f"{mm['monthRevenue']['targetWan']} 万 ＝ <b>{mm['monthRevenue']['amountProgress']}%</b>，"
                 f"时间进度 {mm['monthRevenue']['timeProgress']}%，差 "
                 f"<b>{round(mm['monthRevenue']['amountProgress'] - mm['monthRevenue']['timeProgress'], 1):+}pt</b>。"
                 "剩余天数按当前日均测算，需要逐日盯。</p></div>"),
    }

    # ---- service：三张台账 ----
    sv_w, sv_p = sv["week"], sv["prevSameDays"]
    _svc_staff = "、".join(f"{k} {v}" for k, v in (sv.get("staff") or [])) or "—"
    service = {
        "range": f"本期 {LBL}（标准化回访 / 导诊主动服务 / 日工作量三张台账 · 数据至 {_svc_end}，{_svc_n} 天）",
        "metrics": [
            ["导医回访", f"{sv_w['followup']} 条"],
            ["标注到院", f"{sv_w['arrived']} 人"],
            ["台账到院率", f"{sv_w['rate']}%"],
            ["导诊主动服务", f"{sv_w['guide']} 条"],
            ["日工作量", f"{sv_w['workload']:,} 分"],
            [f"上期同 {_svc_n} 天回访", f"{sv_p['followup']} 条"],
            ["上期到院率", f"{sv_p['rate']}%"],
        ],
        "note": (f"<b>三张台账一并推进到 {_svc_end}（{_svc_n} 天）。</b>"
                 f"回访 <b>{sv_w['followup']}</b> 条、标注到院 <b>{sv_w['arrived']}</b> 人"
                 f"（<b>{sv_w['rate']}%</b>）、导诊主动服务 <b>{sv_w['guide']}</b> 条、"
                 f"日工作量 <b>{sv_w['workload']:,}</b> 分。"
                 f"上期取同一窗口长度（{_svc_n} 天）：回访 {sv_p['followup']} 条、到院 {sv_p['arrived']} 人"
                 f"（{sv_p['rate']}%）、主动服务 {sv_p['guide']} 条、工作量 {sv_p['workload']:,} 分。"
                 f"<br><b>⚠ 汇报表客服组表头（到院 239 / 义诊 14）本周未滚动</b>，与上周同值，已不引用；"
                 f"「随访人数」一栏长期为空，按契约记 null、不拿台账顶替。"),
        "diag": ("<div class=\"diagnosis-item tone-risk\"><b>本周判断 · 到院率回升，但回访量在掉</b>"
                 f"<p>到院率 {sv_p['rate']}% → <b>{sv_w['rate']}%</b>"
                 f"（<b>{round(sv_w['rate'] - sv_p['rate'], 1):+.1f}pt</b>），"
                 f"但回访量 {sv_p['followup']} → <b>{sv_w['followup']}</b> 条"
                 f"（<b>{round((sv_w['followup'] - sv_p['followup']) / max(1, sv_p['followup']) * 100, 1):+.1f}%</b>）。"
                 "样本变小、率值上升，<b>不能直接读成质量改善</b>。</p></div>"
                 "<div class=\"diagnosis-item tone-orange\"><b>回访任务压在一个人身上</b>"
                 f"<p>本周回访台账逐人：<b>{_svc_staff}</b>——其余导医本周 0 条记录。"
                 "要么是排班只留一人做回访，要么是其他人漏填。需要组长确认，"
                 "否则排名会变成「谁填表谁上榜」。</p></div>"
                 "<div class=\"diagnosis-item tone-orange\"><b>逐日波动异常</b>"
                 "<p>本周逐日回访量高低差很大（最低 1 条、最高 11 条），"
                 "说明台账是「想起来才补」，不是当日记；这会让到院率跟着失真。"
                 "建议改为当班即录。</p></div>"),
    }

    # ---- marketing：对接表 + 周对照 list ----
    bt_w, bt_p = bt["week"], bt["prevSameDays"]
    _staff_txt = "、".join(f"{k} {v}" for k, v in bt["staff"])
    marketing = {
        "range": f"本期 {LBL}（数据至 {_but_end}，{_but_n} 天）｜源：《心理管家一周有效客户对接表》各管家分表",
        "metrics": [
            ["有效对接", f"{bt_w['contact']} 条"],
            ["转住院", f"{bt_w['admit']} 人"],
            ["转住院率", f"{bt_w['rate']}%"],
        ] + [[k, f"{v} 条"] for k, v in bt["staff"]]
          + [[s, "本周无记录（null）"] for s in bt["missingStaff"]],
        "list": {
            "title": f"本周（{LBL}）与上期同 {_but_n} 天对照 · 患者有效对接表",
            "sub": f"来源：《心理管家一周有效客户对接表》各管家分表逐条；数据至 {_but_end}",
            "cols": ["口径", "有效对接", "转住院", "转住院率"],
            "gt": "1.6fr 1fr 1fr 1fr",
            "num": [1, 1, 1, 1],
            "rows": [
                [f"本期 {LBL}（{_but_n} 天）", str(bt_w["contact"]), str(bt_w["admit"]),
                 f"{bt_w['rate']}%"],
                [f"上期同 {_but_n} 天（{prev['start'][5:]}—{prev['compareSameDaysEnd'][5:]}）",
                 str(bt_p["contact"]), str(bt_p["admit"]), f"{bt_p['rate']}%"],
            ],
            "note": ("⚠ 两行<b>窗口长度相同</b>，可直接比总量与率值。"
                     "管家表头（入院 / 门诊 / 总收入）本周整行空白，按契约不显示、不拿其他源代替。"),
        },
        "note": (f"<b>管家侧本周（{_but_end}，{_but_n} 天）逐人：{_staff_txt}，合计 {bt_w['contact']} 条。</b>"
                 f"转住院 <b>{bt_w['admit']}</b> 人（<b>{bt_w['rate']}%</b>）。"
                 f"上期同 {_but_n} 天：{bt_p['contact']} 条 / {bt_p['admit']} 人（{bt_p['rate']}%）。"
                 + (f"<br><b>⚠ {'、'.join(bt['missingStaff'])} 本周无任何对接记录</b>，"
                    "按契约记 null、<b>不按 0 降榜</b>——是没上班还是漏填，需管家组长确认。" if bt["missingStaff"] else "")),
        "diag": ("<div class=\"diagnosis-item tone-risk\"><b>本周判断 · 条数降、转化率基本持平</b>"
                 f"<p>{_but_n} 天对接 <b>{bt_w['contact']}</b> 条（上期同 {_but_n} 天 {bt_p['contact']} 条，"
                 f"<b>{round((bt_w['contact'] - bt_p['contact']) / max(1, bt_p['contact']) * 100, 1):+.1f}%</b>）、"
                 f"转住院 <b>{bt_w['admit']}</b> 人（{bt_p['admit']} 人）、"
                 f"率值 <b>{bt_w['rate']}%</b>（{bt_p['rate']}%，"
                 f"<b>{round(bt_w['rate'] - bt_p['rate'], 1):+.1f}pt</b>）。"
                 "转化能力没变，前端量在收缩。</p></div>"
                 "<div class=\"diagnosis-item tone-risk\"><b>两人整周零记录</b>"
                 f"<p>{'、'.join(bt['missingStaff'])} 本周一条对接记录都没有。"
                 "按契约记 null、不按 0 参与排名，但<b>空着不等于没问题</b>——"
                 "需要确认是休假、调岗，还是漏填。</p></div>"
                 "<div class=\"diagnosis-item tone-orange\"><b>营销中心表头整行空白</b>"
                 "<p>入院 / 门诊 / 总收入三项本周都没填，因此转住院只能取对接表逐条，"
                 "与营收日报、汇报表<b>三套口径互不相加</b>。</p></div>"),
    }

    html = replace_dept_daily_key(html, "doctor", "nursing", _jso(doctor))
    html = replace_dept_daily_key(html, "service", "marketing", _jso(service))

    # marketing 是 deptDaily 的最后一个键（后面只剩 list），整段尾替
    i, j = _dd_span(html)
    if i is not None:
        seg = html[i:j]
        mk = re.search(r"marketing:\{", seg)
        if mk:
            # ⛔ 2026-10-25 事故复盘：这里原用 seg.rfind("}") 取 deptDaily 的收尾，
            #    一旦哪次把 `};` 的 `;` 吃掉，rfind 就会把收尾位置一路后挪，
            #    写出 `}const openDeptSales` —— 同一个 token 行没有换行/分号，
            #    ASI 不成立，整块 script 直接 SyntaxError。改为括号匹配定位收尾，
            #    并自己补 `;\n    `，不再依赖原文尾部的形状。
            k = seg.find("{")
            depth, e, quote = 0, k, None
            while e < len(seg):
                c = seg[e]
                if quote:
                    if c == "\\":
                        e += 2
                        continue
                    if c == quote:
                        quote = None
                elif c in "'\"":
                    quote = c
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                e += 1
            seg = seg[:mk.start()] + "marketing:" + _jso(marketing) + "\n    };\n    "
            html = html[:i] + seg + html[j:]
        else:
            print("  ⚠ deptDaily.marketing 锚点未命中")
    else:
        print("  ⚠ 未找到 const deptDaily，marketing 跳过")
    return html



# ---------------------------------------------------------------- 自愈：deptSalesList
# ⛔ 2026-10-26：这个函数曾被整块重写连带删掉，只剩调用点，
#    导致 nursing / psychology / service / marketing 四个抽屉进「数据变化」页就抛
#    ReferenceError，后面的 Tab 切换与诊断渲染全部不执行（医生组跳过该面板，所以没暴露）。
#    补丁脚本每次跑都检查一次，缺了就补回去。
_DEPT_SALES_LIST = r"""function deptSalesList(x){if(!x||!x.list)return '';var L=x.list,gt=L.gt||'1.35fr .72fr .72fr .95fr',nm=function(i){return (L.num&&L.num[i])?'dsl-n':''},warn=L.warn||[];var row=function(cells,cls){return '<div class="dsl-row'+(cls?' '+cls:'')+'">'+cells.map(function(v,i){return '<span class="'+nm(i)+'">'+v+'</span>'}).join('')+'</div>'};return '<div class="dept-sales-list" style="--dsl-cols:'+gt+'"><div class="dsl-head"><strong>'+L.title+'</strong><span>'+(L.sub||'')+'</span></div>'+row(L.cols,'dsl-th')+L.rows.map(function(r,i){return row(r,warn.indexOf(i)>=0?'warn':'')}).join('')+(L.sum?row(L.sum,'dsl-sum'):'')+(L.note?'<p class="dsl-note">'+L.note+'</p>':'')+'</div>'}"""


def ensure_dept_sales_list(html):
    if "function deptSalesList" in html:
        return html, 0
    anchor = "    const openDeptSales=openDeptV2;"
    if anchor not in html:
        return html, 0
    return html.replace(anchor, "    " + _DEPT_SALES_LIST + "\n" + anchor), 1


def build_card_js():
    out = ["    /* ⚠ 本段由 scripts/live-data/patch_page.py 依 data/snapshot.json 生成，勿手改 */",
           "    const DEPT_CARD={"]
    keys = ["doctor", "nursing", "psychology", "service", "marketing"]
    rows = []
    for k in keys:
        c = dept_cards[k]
        m1lab, m1v, m1u = c["m1"]
        m2lab, m2v, m2u = c["m2"]
        trend = "null" if c["trend"] is None else "[" + ",".join(str(x) for x in c["trend"]) + "]"
        axis = "null" if c["axis"] is None else js_str(c["axis"])
        # ⛔ None 必须渲染成「—」，绝不能落到 JS 里变成字符串 "None"
        m1s = "—" if m1v is None else str(m1v)
        m2s = "—" if m2v is None else str(m2v)
        rows.append(
            f"      {k}:{{m1:{{label:{js_str(m1lab)},value:{js_str(m1s)},unit:{js_str(m1u)}}},"
            f"m2:{{label:{js_str(m2lab)},value:{js_str(m2s)},unit:{js_str(m2u)}}},\n"
            f"        trend:{trend},axis:{axis},\n"
            f"        note:{js_str(c['note'])}"
            f"{',pct:true' if m2u == '%' else ''}}}"
        )
    out.append(",\n".join(rows))
    out.append("    };")
    return "\n".join(out)


def main():
    dry = "--dry-run" in sys.argv
    html = open(HTML, encoding="utf-8").read()
    orig_len = len(html)

    # 1) 整块替换 DEPT_CARD
    # ⛔ 必须把紧邻的「本段由…生成」注释一起吃掉：build_card_js() 会重新生成这条注释，
    #    若正则从 const 开始，旧注释留着、新注释又插一条，每跑一次文件就长 76 字节（实测踩过）。
    blk = re.search(
        r"(?:[ \t]*/\* ⚠ 本段由[^\n]*\*/\n)?[ \t]*const DEPT_CARD=\{.*?\n[ \t]*\};\n",
        html, re.S)
    if not blk:
        raise SystemExit("未定位到 DEPT_CARD 块")
    html = html[:blk.start()] + build_card_js() + "\n" + html[blk.end():]

    # 2) 补 DEPT_AXIS 轴标
    # ⛔ 轴标必须跟着本周实际有数据的那几天走：写死 10.12…10.17 会让趋势图横轴
    #    跟卡片数字不同期（业主 2026-10-07 已提过一次，10-24 换周再次踩到）。
    _axis_days = [x["date"][5:].replace("-", ".") for x in _doc_ledger]
    _psy_days = [f"{int(k[5:7])}.{int(k[8:])}" for k in sorted(psy.get("daily", {}))]
    _svc_days = [f"{int(k[5:7])}.{int(k[8:])}" for k in sorted(svc.get("daily", {}))]
    axis_map = {
        "d1019": _axis_days,          # 医生逐日（营收日报台账）
        "dsvc5": _svc_days,           # 客服逐日（三张台账，天数与营收台账不同）
        "dpsy7": _psy_days,           # 心理逐日
        "dbutler": [k for k, _ in but["staff"]],
        "dpsum": ["首次", "情绪", "住院"],
    }
    # 同名键若内容变了（换周后日期不同），先删旧行再补，不能靠「键已存在」跳过
    import re as _re
    for k in ("d1019", "dsvc5", "dpsy7"):
        html = _re.sub(r"\n\s*" + k + r":\[[^\]]*\],?", "", html)
    add = []
    for k, v in axis_map.items():
        if f"{k}:[" not in html:
            add.append(f"      {k}:[" + ",".join(js_str(x) for x in v) + "]")
    if add:
        html = html.replace("      d6pt:['交','磁','脑','松','失','馈']",
                            "      d6pt:['交','磁','脑','松','失','馈'],\n" + ",\n".join(add), 1)

    # 3) 部门摘要（卡片名下的 delta / status / summary）与抽屉首行
    summ = {
        "doctor": ("总收入", sgn(m["weekRevenue"]["deltaPct"]) + "%", "高优先级", "high"),
        "nursing": ("物理治疗人数", "总量口径", "本周未提交", ""),
        "psychology": ("患者接触", sgn(round((psy["week"]["contact"] - psy["prevSameDays"]["contact"]) /
                                            max(1, psy["prevSameDays"]["contact"]) * 100, 1)) + "%", "需关注", ""),
        "service": ("回访台账", sgn(round((svc["week"]["followup"] - svc["prevSameDays"]["followup"]) /
                                         max(1, svc["prevSameDays"]["followup"]) * 100, 1)) + "%", "待并轨", ""),
        "marketing": ("管家对接", sgn(round((but["week"]["contact"] - but["prevSameDays"]["contact"]) /
                                          max(1, but["prevSameDays"]["contact"]) * 100, 1)) + "%", "待并轨", ""),
    }
    for k, (summary, delta, status, cls) in summ.items():
        pat = re.compile(r"(" + k + r":\{name:'[^']*',icon:'[^']*',status:')[^']*('[,]statusClass:')[^']*(')"
                         r"([^,]*),summary:'[^']*',delta:'[^']*'")
        new = r"\g<1>" + status + r"\g<2>" + cls + r"\g<3>\g<4>,summary:'" + summary + "',delta:'" + delta + "'"
        html, n = pat.subn(new, html, count=1)
        if n == 0:
            print(f"  ⚠ {k} 摘要未替换（锚点不匹配）")

    # 4) 每部门抽屉补一行「本期」，保留历史行；marker 去重
    _psyc_end = SNAP["watermarks"]["psych"]["dataThrough"][5:].replace("-", ".")
    _svc_end = SNAP["watermarks"]["service"]["dataThrough"][5:].replace("-", ".")
    _but_end = SNAP["watermarks"]["butler"]["dataThrough"][5:].replace("-", ".")
    rows = {
        "doctor": [f"{MARK} 本期（{LBL} · 营收日报台账 {N} 天）", None, m["weekRevenue"]["value"], "万",
                   f"营收日报逐日台账，已录 {N} 天（{P['start'][5:]}—{DT}）：营收 <b>{m['weekRevenue']['value']}</b> 万"
                   f"（门诊 {m['weekOutpatient']['value']} 万 ＋ 在院 {m['weekInpatient']['value']} 万）、"
                   f"门诊 <b>{m['weekVisits']['value']}</b> 人次、入院 <b>{m['weekAdmit']['value']}</b> 人、"
                   f"出院 <b>{m['weekDischarge']['value']}</b> 人、在院 <b>{m['wardCount']['value']}</b> 人（{DT} 时点）。"
                   f"上期同 {N} 天 {dep['compareWeek']['revenueWan']} 万 / 门诊 {dep['compareWeek']['outpatient']} / "
                   f"入 {dep['compareWeek']['admit']} / 出 {dep['compareWeek']['discharge']}。"
                   f"⚠⚠ 《特别行动小组汇报表》医生组表头本周未滚动（与上一期逐项同值），"
                   f"按契约不引用；物理治疗费无逐日台账，本期记 null。",
                   f"上期 {PS}—{PW}", f"本期 {LBL}"],
        "nursing": [f"{MARK} 本期（{LBL} · 护理部未提交）", None, None, "人次",
                    f"⚠⚠ 护理部本周未提交：周报与物理治疗逐日表最新只到 {_nur.get('weeklyThrough') or '—'}，"
                    f"本期窗口内 <b>0 条护理事实</b>，因此六项治疗完成率、物理治疗人数、工娱场次 <b>全部留空</b>。"
                    f"汇报表护理组表头同样未滚动（与上一期逐项同值），不引用。"
                    f"→ 需补报 10.19—10.24 逐日表与六项应做/实做。",
                    "上周值，已停用", f"本期 {LBL}"],
        "psychology": [f"{MARK} 本期（{LBL} · V4 管理表口径）", None, dep["psychology"]["consult"], "人次",
                       f"V4 管理表逐条：咨询工作量 <b>{dep['psychology']['consult']}</b> 人次、"
                       f"患者接触 <b>{dep['psychology']['contact']}</b> 人次、家长访谈 {psy['week']['parent']}、"
                       f"团体 {psy['week']['groupSessions']} 场 {psy['week']['groupPeople']} 人；"
                       f"日报 {psy['week']['report']} 条，数据至 {_psyc_end}。"
                       f"管床本周新增 <b>{psy.get('boundWeek', {}).get('rows', 0)} 行 / "
                       f"{psy.get('boundWeek', {}).get('people', 0)} 名患者</b>，累计在管 <b>{psy.get('boundPatients', 0)}</b> 人。"
                       f"上期同天数 接触 {psy['prevSameDays']['contact']} / 咨询 {psy['prevSameDays']['consult']}。"
                       f"⚠ 汇报表心理组表头自 2026-09-21 起未滚动（与上一期同值），已停用。",
                       "V4 上期同天数", f"本期 {LBL}"],
        "service": [f"{MARK} 本期（{LBL} · 三张台账）", None, svc["week"]["followup"], "条",
                    f"台账数据至 {_svc_end}：回访 <b>{svc['week']['followup']}</b> 条、标注到院 "
                    f"<b>{svc['week']['arrived']}</b> 人（<b>{svc['week']['rate']}%</b>）、导诊主动服务 "
                    f"<b>{svc['week']['guide']}</b> 条、日工作量 <b>{svc['week']['workload']:,}</b> 分。"
                    f"上期同 {SNAP['watermarks']['service']['days']} 天 回访 {svc['prevSameDays']['followup']} 条 / "
                    f"到院 {svc['prevSameDays']['arrived']} 人（{svc['prevSameDays']['rate']}%）。"
                    f"⚠ 汇报表客服组表头本周未滚动（与上一期同值），已不引用；「随访人数」长期为空，记 null。",
                    "上期同天数", f"本期 {LBL}"],
        "marketing": [f"{MARK} 本期（{LBL} · 数据至 {_but_end}）", but["prevSameDays"]["contact"], but["week"]["contact"], "条",
                      f"管家对接 <b>{but['week']['contact']}</b> 条、转住院 {but['week']['admit']} 人"
                      f"（<b>{but['week']['rate']}%</b>）；"
                      + " · ".join(f"{k} {v}" for k, v in but["staff"]) +
                      f"。上期同 {SNAP['watermarks']['butler']['days']} 天 {but['prevSameDays']['contact']} 条 / "
                      f"{but['prevSameDays']['admit']} 人（{but['prevSameDays']['rate']}%）。"
                      f"⚠ {'、'.join(but['missingStaff'])} 本周无记录，记 null 不降榜；营销中心表头整行空白。",
                      f"上期同 {SNAP['watermarks']['butler']['days']} 天", f"本期 {LBL}"],
    }
    # ⛔ 旧版逻辑是「检测到 MARK 就全部跳过」，结果口径改了、抽屉里还留着上一版的数。
    #    改为：先删掉旧自动行，再按当前快照重新注入五条，保证不叠加也不过期。
    if MARK in html:
        html, _n = re.subn(r"\['\[\[AUTO-DEPT\]\][\s\S]*?\],", "", html)
        print(f"  清除旧自动行 {_n} 条")
    for k, row in rows.items():
        anchor = re.compile(r"(" + k + r":\{name:'[^']*',icon:'[^']*',[^\[]*?metrics:\[)")
        mm = anchor.search(html)
        if not mm:
            print(f"  ⚠ {k} metrics 锚点未命中")
            continue
        html = html[:mm.end()] + json.dumps(row, ensure_ascii=False).replace('"', "'") + "," + html[mm.end():]

    # 4b) 核心指标磁贴（整块重渲染）
    try:
        st = html.index('id="kpiGrid">') + len('id="kpiGrid">')
        en = find_div_end(html, st - len('id="kpiGrid">'))
        # find_div_end 从头算起，需跳过 id 属性本身
        en = find_div_end(html, html.rindex("<div", 0, st))
        html = html[:st] + render_kpis() + "</div>" + html[en:]
    except ValueError as e:
        print(f"  ⚠ kpiGrid 未替换：{e}")

    # 4c) 抽屉「数据变化」页：deptDaily 五个部门整块按快照重写
    html = patch_dept_daily_rest(html, dep, SNAP)
    html = patch_dept_daily_nursing(html, dep)
    # 4d) 抽屉「数据变化」页：deptDaily.psychology 整块按快照重写（原为 10.1—10.7 的硬编码）
    html = patch_dept_daily_psych(html, SNAP)

    # 5) 页脚口径
    # ⛔ 2026-10-24：这一条原来写「以《特别行动小组汇报表》为准」——本周该表整表未滚动，
    #    继续这么写等于告诉业主「首页是上周的数」。改为先讲本周真正在跑的口径和各源截止日。
    foot_pat = re.compile(r'(<div class="kpi-foot"><i></i><span>)部门数据：.*?(</span></div>)', re.S)
    _w = SNAP["watermarks"]
    foot = (f'部门数据：<b>{LBL}（本周·营收台账至 {DT}，个人周排至 2026-10-25）</b>·'
            f'<b>本周口径已整体切到「各部门真正在跑的明细表」</b>——'
            f'医生组＝营收日报逐日台账（至 {_w["revenue"]["dataThrough"]}，{_w["revenue"]["days"]} 天，'
            f'营收 {m["weekRevenue"]["value"]} 万、门诊 {m["weekVisits"]["value"]} 人次、'
            f'入 {m["weekAdmit"]["value"]} / 出 {m["weekDischarge"]["value"]}）'
            + (f' ＋《周排名分析》个人周排（10.19–10.25，出院结账口径：{len(DRR)} 人、出院 '
               f'{DRT.get("discharge")} 人、在院 {DRT.get("inWard")} 人、个人业绩合计 '
               f'{DRT.get("revenue", 0) / 10000:.2f} 万）' if DRR else '')
            + f'；'
            f'心理＝V4 管理表（至 {_w["psych"]["dataThrough"]}，{_w["psych"]["days"]} 天，'
            f'咨询 {psy["week"]["consult"]} / 接触 {psy["week"]["contact"]}）；'
            f'客服＝三张台账（至 {_w["service"]["dataThrough"]}，{_w["service"]["days"]} 天，'
            f'回访 {svc["week"]["followup"]} 条 / 到院率 {svc["week"]["rate"]}%）；'
            f'营销＝各管家对接表（至 {_w["butler"]["dataThrough"]}，{_w["butler"]["days"]} 天，'
            f'对接 {but["week"]["contact"]} 条 / 转住院 {but["week"]["admit"]}）；'
            f'到院＝《10月到院登记表》逐条（{SNAP["arrival"]["week"]} 人次，就诊口径）。'
            f'<b>⚠ 《特别行动小组汇报表》五个部门表头本周整表未滚动</b>（值等于正文「第 3 周」列、与上一期逐项相同），'
            f'已全部停用、原值存档在 departments.actionReportRaw，表头补齐后自动切回。'
            f'<b>⚠ 护理部本周未提交</b>：周报与物理治疗逐日表停在 {_nur.get("weeklyThrough") or "—"}，'
            f'六项完成率 / 物理治疗人数 / 工娱本周一律留空，不拿上一期 93% 顶替。'
            f'<b>缺失一律记 null、不写 0</b>：物理治疗费（无逐日台账）、护理整块、'
            f'营销中心表头三项、客服「随访人数」、'
            f'到院以外的旧口径，均不反推、不互相覆盖。'
            f'数据源共 {len(SNAP["sources"])} 处，逐日自动采集与重算。')
    html, nfoot = foot_pat.subn(lambda x: x.group(1) + foot + x.group(2), html, count=1)

    # 5a) 自愈：deptSalesList 定义缺失
    html, _ns = ensure_dept_sales_list(html)
    if _ns:
        print("  已补回 deptSalesList()（原定义被整块重写删掉）")

    # 5b) 抽屉指标行渲染时剥离内部标记
    # ⛔ 2026-10-26：自动注入的「本期」行必须带 [[AUTO-DEPT]] 才能被下一轮清掉，
    #    但渲染时直接 `${m[0]}` 会把它当标题显示出来（线上已出现「[[AUTO-DEPT]] 本期（…）」）。
    #    数据层保留标记、渲染层剥掉，两边都不动对方的前提。
    _lbl_old = "<label>${m[0]}</label>"
    if _lbl_old in html:
        html = html.replace(
            _lbl_old, "<label>${m[0].replace('[[AUTO-DEPT]]','').trim()}</label>")
        print("  已修正指标标题的标记泄漏")
    if not nfoot:
        print("  ⚠ 页脚未替换")

    if dry:
        print(f"dry-run：长度 {orig_len} → {len(html)}（{len(html)-orig_len:+d}）")
        return
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"index.html 已更新：{orig_len} → {len(html)} 字节（{len(html)-orig_len:+d}）")


if __name__ == "__main__":
    main()
