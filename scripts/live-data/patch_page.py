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


m = SNAP["metrics"]
psy = SNAP["psych"]
svc = SNAP["service"]
but = SNAP["butler"]
dep = SNAP["departments"]

dept_cards = {
    "doctor": {
        "m1": ("本期出院", dep["doctor"]["discharge"], "人"),
        "m2": ("物理治疗费", dep["doctor"]["physioWan"], "万"),
        "trend": [1, 2, 2, 3, 2, 2],
        "axis": "d1012",
        "note": (f"{LBL}（7 天，含 10.18）《特别行动小组汇报表》医生组表头：入院 <b>{dep['doctor']['admit']}</b> 人、"
                 f"出院 <b>{dep['doctor']['discharge']}</b> 人、门诊 <b>{dep['doctor']['outpatient']}</b> 人次、"
                 f"物理治疗 <b>{dep['doctor']['physioWan']}</b> 万、总收入 <b>{dep['doctor']['revenueWan']}</b> 万。"
                 f"本月三周：26.2 → 69 → 72.5 万。"
                 f"⚠ 表头是全组口径，个人明细 6 人加总入院 {dep['doctor']['recon']['admit']['detail']}、"
                 f"出院 {dep['doctor']['recon']['discharge']['detail']}，差 "
                 f"{dep['doctor']['recon']['admit']['gap']} 入 / {dep['doctor']['recon']['discharge']['gap']} 出，"
                 f"全部落在未填的 {'、'.join(dep['doctor']['recon']['blankRows']) or '—'} 一行，按契约记 null 不反推。"),
    },
    "nursing": {
        "m1": ("物理治疗人数", dep["nursing"]["physioPeople"], "人次"),
        "m2": ("6 项治疗完成率", f"{dep['nursing']['treatSummary']['rate']}",
               f"% · {dep['nursing']['treatSummary']['done']}/{dep['nursing']['treatSummary']['due']}"),
        "trend": None,
        "axis": None,
        "note": (f"《特别行动小组汇报表》护理组本周表头：物理治疗 <b>{dep['nursing']['physioPeople']} 人次</b>（含住院＋门诊）、"
                 f"工娱 <b>{dep['nursing']['recreationSessions']} 场 / {dep['nursing']['recreationPeople']} 人次</b>。"
                 f"六项治疗本周应做 <b>{dep['nursing']['treatSummary']['due']}</b>、实做 "
                 f"<b>{dep['nursing']['treatSummary']['done']}</b>，合计完成率 "
                 f"<b>{dep['nursing']['treatSummary']['rate']}%</b>（护理部口径向下取整）；"
                 f"最低为{dep['nursing']['treatSummary']['worst']['label']}"
                 f" {dep['nursing']['treatSummary']['worst']['rate']}%。逐项见抽屉。"),
    },
    "psychology": {
        "m1": ("咨询工作量", dep["psychology"]["consult"], "人次"),
        "m2": ("患者接触", dep["psychology"]["contact"], "人次"),
        "trend": [psy["daily"][k] for k in sorted(psy.get("daily", {}))],
        "axis": "dpsy7",
        "note": (f"<b>本周心理科以 V4 管理表为唯一口径</b>（汇报表心理咨询组表头自 2026-09-21 起未滚动，"
                 f"40 人 / 4 场 / 19,002 元是 9.21—9.27 的旧值，<b>已停用</b>，原值存档可查）。"
                 f"V4「咨询师每日简报」逐条汇总（{LBL}，至 {DT}）：患者接触 <b>{psy['week']['contact']}</b> 人次"
                 f"（24h 首次 {psy['week']['first']} ＋ 情绪支持 {psy['week']['emotion']} ＋ 住院 {psy['week']['inpatient']}）、"
                 f"咨询工作量 <b>{psy['week']['consult']}</b> 人次（住院 {psy['week']['inpatient']} ＋ 门诊 "
                 f"{psy['week']['outpatient']} ＋ 家庭 {psy['week']['family']}）、家长访谈 {psy['week']['parent']}、"
                 f"团体 {psy['week']['groupSessions']} 场 / {psy['week']['groupPeople']} 人次；"
                 f"管床本周新增 <b>{psy.get('boundWeek', {}).get('rows', 0)} 行 / "
                 f"{psy.get('boundWeek', {}).get('people', 0)} 人</b>，累计在管 {psy.get('boundPatients', 0)} 人。"
                 f"周个人统计 {psy['week']['report']} 条填报，与日报逐条对账仅差 1 天（赵芳 10-18，见下表注）。"),
    },
    "service": {
        "m1": ("到院人数（接待）", dep["service"]["arrived"], "人次"),
        "m2": ("义诊", dep["service"]["charity"], "人"),
        "trend": [1, 5, 16, 4, 2, 2],
        "axis": "d1012",
        "note": (f"《特别行动小组汇报表》客服服务部本周表头：到院 <b>{dep['service']['arrived']}</b> 人次（导医接待，含陪同）、"
                 f"义诊 <b>{dep['service']['charity']}</b> 人；「随访人数」一栏<b>未填</b>（记 null，不拿台账数顶替）。"
                 f"另有台账口径（数据至 {DT}）：回访 <b>{svc['week']['followup']}</b> 条、标记到院 {svc['week']['arrived']} 人"
                 f"（{svc['week']['rate']}%）、导诊主动服务 {svc['week']['guide']} 条。"
                 f"⚠ 到院登记逐条 {SNAP['arrival']['week']} 人次为「就诊患者」口径，与接待人次不同，各自保留、不加总。"),
    },
    "marketing": {
        "m1": ("管家对接", but["week"]["contact"], "条"),
        "m2": ("转住院率", but["week"]["rate"], "%"),
        "trend": [v for _, v in but["staff"]],
        "axis": "dbutler",
        "note": (f"{LBL}（数据至 {DT}）《患者有效对接表》各管家分表逐条：有效对接 <b>{but['week']['contact']}</b> 条、"
                 f"转住院 <b>{but['week']['admit']}</b> 人（<b>{but['week']['rate']}%</b>）——"
                 + " · ".join(f"{k} {v}" for k, v in but["staff"]) +
                 f"。上期同 {N} 天 {but['prevSameDays']['contact']} 条 / {but['prevSameDays']['admit']} 人（{but['prevSameDays']['rate']}%）。"
                 f"⚠ {'、'.join(but['missingStaff']) or '—'} 本周无记录，按契约记 null、<b>不按 0 降榜</b>。"
                 f"营销中心表头的入院/门诊/总收入<b>本周未填</b>，故不显示、也不拿其他源代替。"),
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

    tiles = [
        tile("doctor", f"本期营收（{LBL} · {N} 天）", m["weekRevenue"]["value"], "万元",
             pct(m["weekRevenue"]["deltaPct"]), dcls(m["weekRevenue"]["deltaPct"])),
        tile("doctor", "门诊人次（汇报表）", m["weekVisits"]["value"], "人次",
             pct(m["weekVisits"]["deltaPct"]), dcls(m["weekVisits"]["deltaPct"])),
        tile("doctor", "本期入院", m["weekAdmit"]["value"], "人", pct(m["weekAdmit"]["deltaPct"]),
             dcls(m["weekAdmit"]["deltaPct"])),
        tile("doctor", "本期出院", m["weekDischarge"]["value"], "人", pct(m["weekDischarge"]["deltaPct"]),
             dcls(m["weekDischarge"]["deltaPct"])),
        tile("doctor", "物理治疗费", m["weekPhysio"]["value"], "万元", pct(m["weekPhysio"]["deltaPct"]),
             dcls(m["weekPhysio"]["deltaPct"])),
        tile("doctor", "在院人数（时点）", m["wardCount"]["value"], "人"),
        tile("nursing", f"护理 6 项治疗完成率",
             dep["nursing"]["treatSummary"]["rate"], "%",
             f'{dep["nursing"]["treatSummary"]["done"]}/{dep["nursing"]["treatSummary"]["due"]}', "flat"),
        tile("psychology", "心理 咨询工作量", dep["psychology"]["consult"], "人次",
             f'接触 {dep["psychology"]["contact"]}', "flat"),
        tile("service", "客服 到院接待", dep["service"]["arrived"], "人次"),
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

    obj = {
        "range": f"本期 10.12—10.18（V4 管理表 · 日报逐条汇总，7 天）",
        "metrics": [
            ["咨询工作量", f'{w["consult"]} 人次'],
            ["患者接触", f'{w["contact"]} 人次'],
            ["家长访谈", f'{w["parent"]} 人次'],
            ["团体", f'{w["groupSessions"]} 场 / {w["groupPeople"]} 人'],
            ["管床新增", f'{bw.get("rows", 0)} 行 / {bw.get("people", 0)} 人'],
        ],
        "list": {
            "title": "咨询师个人周工作统计（本期 10.12—10.18 · 组长自动汇总表）",
            "sub": "源：V4「周个人统计」，组长只调周起始日、数值由《咨询师每日简报》公式汇出",
            "cols": ["咨询师", "情绪支持", "住院咨询", "门诊咨询", "家长访谈", "填报天", "完整率"],
            "gt": "1.15fr .8fr .8fr .8fr .8fr .92fr 1fr",
            "num": [1, 2, 3, 4, 5, 6],
            "warn": [],
            "rows": rows,
            "sum": sumr,
            "note": "⚠ <b>周个人统计与日报逐条汇总有 1 天差</b>：" + gap_txt +
                    "。差额全部来自<b>赵芳 10-18 那条日报</b>——该行落在每日简报表末尾第 1005 行，"
                    "超出表内公式的汇总区域，所以周表少算 1 天填报、1 天查房、1 次门诊。"
                    f"其余 5 项两侧完全一致（首次对接 {w['first']}、情绪支持 {w['emotion']}、"
                    f"住院咨询 {w['inpatient']}、家庭咨询 {w['family']}、家长访谈 {w['parent']}）。",
        },
        "note": "<b>本周心理科只有一个口径：V4 管理表（日报逐条 + 周个人统计 + 管床对接）。</b>"
                f"患者接触 <b>{w['contact']}</b> 人次（24h 首次 {w['first']} ＋ 情绪支持 {w['emotion']} ＋ 住院 {w['inpatient']}）、"
                f"咨询工作量 <b>{w['consult']}</b> 人次（住院 {w['inpatient']} ＋ 门诊 {w['outpatient']} ＋ "
                f"家庭 {w['family']}）、家长访谈 {w['parent']} 人次、"
                f"团体 {w['groupSessions']} 场 {w['groupPeople']} 人。"
                f"<br><b>⚠ 汇报表表头已停用：</b>40 人 / 4 场 / 19,002 元是 <b>2026-09-21 抓取值</b>，"
                f"与《9 月报告》里 9.21—9.27 那周同值；10.18 23:48 的保存与 17:06 存档逐格比对，心理组 <b>0 变动</b>，"
                f"说明表头没有滚到本周。按「缺项不拿旧值顶替」，本周改用 V4 唯一可核口径，旧值存档不丢。"
                f"其中<b>团辅 4 场 vs 本周 3 场</b>是最直接的证据。"
                f"<br><b>管床对接：本周新增 {bw.get('rows', 0)} 行 / {bw.get('people', 0)} 个患者</b>"
                f"（{by_txt}），累计在管 <b>{p.get('boundPatients', 0)}</b> 人。"
                "陈鹏 2 行只有 1 人——胡峻源 10-14、10-15 重复登记。"
                "<br><b>⚠ 对账差额：</b>" + gap_txt + "，原因见上表注释；不做四舍五入、不互相覆盖。",
        "diag": "<div class=\"diagnosis-item tone-risk\"><b>本周判断 · 工作量真实，但日报完整率全线偏低</b>"
                f"<p>5 名咨询师本周情绪支持 <b>{w['emotion']}</b> 人次、住院咨询 <b>{w['inpatient']}</b> 人次、"
                f"门诊咨询 <b>{w['outpatient']}</b> 人次、家长访谈 <b>{w['parent']}</b> 人次；"
                f"冯浩鹏一人贡献情绪支持 {next((x['emotion'] for x in sw if x['name'] == '冯浩鹏'), 0)} 人次、"
                f"住院咨询 {next((x['inpatient'] for x in sw if x['name'] == '冯浩鹏'), 0)} 人次，是本周主力。"
                "但 5 人日报完整率 <b>0%—57%</b>，汇总状态<b>全部「有待补」</b>，"
                "赵芳、王沛然为 0%——数据可用性比工作量更值得关注。</p></div>"
                "<div class=\"diagnosis-item tone-orange\"><b>已修的两处数据缺陷</b>"
                "<p>① 王沛然 10-14 同日填了「正常班」「测评值班」两条，后一条全空，"
                "原实现按「人＋日」覆盖导致情绪支持、住院咨询各少 2；已改为同日取最大值合并。"
                "② 每天简报表里有 1 条没写姓名（10-17），原先会挂到空维度上；已跳过并单独记账。</p></div>"
                "<div class=\"diagnosis-item tone-risk\"><b>未纳入的个人</b>"
                "<p><b>苏欣然</b>本周管床 2 名患者（杨亦雯 10-12、张琪谕 10-16），"
                "但不在「周个人统计」的 5 人名册里，也没有日报——她的工作量目前<b>不进任何汇总</b>，"
                "建议要么补进名册、要么在对接表注明不参与统计。</p></div>",
    }
    body = json.dumps(obj, ensure_ascii=False).replace('"', "'")
    # 与 nursing 同理：键名允许可选引号，避免第二次跑锚不到
    m = re.search(r"psychology:\{\s*['\"]?range['\"]?\s*:[\s\S]*?\n      service:\{", html)
    if not m:
        print("  ⚠ deptDaily.psychology 锚点未命中，抽屉心理块未更新")
        return html
    return html[:m.start()] + "psychology:" + body + ",\n      service:{" + html[m.end():]


def patch_dept_daily_nursing(html, dep):
    """抽屉「数据变化」页的护理块（deptDaily.nursing）按快照重写。

    这块是 index.html 里**另一处**写死的周报文案，原先停在 10.5—10.11 / 83.2%，
    与部门卡的 93% 同屏矛盾（业主截图里就能同时看到）。改为按 data/snapshot.json 生成，
    六项逐条列出应做/实做/未做/完成率，并保留「向下取整」与「10.18 未进逐日」两个口径说明。
    """
    n = dep["nursing"]
    ts = n["treatSummary"]
    worst = ts["worst"]
    rows = [[t["label"], str(t["due"]), str(t["done"]), f'{t["rate"]}%']
            for t in n["treat"]]
    obj = {
        "range": "本期 10.12—10.18（护理部周报 · 项目口径，7 天）",
        "metrics": [
            ["6 项治疗完成率", f'{ts["rate"]}%'],
            ["应做 / 实做", f'{ts["due"]} / {ts["done"]}'],
            ["未做", f'{ts["missed"]} 人次'],
            ["最低项目", f'{worst["label"]} {worst["rate"]}%'],
            ["达标项目", "0 / %d 项" % ts["items"]],
        ],
        "list": {
            "title": "物理治疗 6 项完成情况（本期 10.12—10.18 · 护理部周报）",
            "sub": "源：护理部本周报送的应做 / 实做人次；逐日明细见《质控分及物理治疗数据》",
            "cols": ["治疗项目", "应做", "实做", "完成率"],
            # 4 列与抽屉既有列模板一致；加第 5 列「未做」会被挤到换行/压行（实测两轮）
            "gt": "1.7fr 1fr 1fr 1fr",
            "num": [1, 2, 3],
            "warn": [0, 0, 3],
            "rows": rows,
            "sum": ["6 项合计", str(ts["due"]), str(ts["done"]), f'{ts["rate"]}%'],
            "note": "⚠ 完成率按护理部口径<b>向下取整</b>（71/75=94.67%、21/26=80.77%、11/14=78.57% 均不进位），"
                    "所以与按比值四舍五入的结果最多差 1 个百分点。"
                    "各项未做（应做−实做）：" +
                    "、".join(f"{t['label']} {t['missed']}" for t in n["treat"]) +
                    f"，合计 <b>{ts['missed']}</b> 人次。"
                    "本周 6 项<b>无一项达到 100%</b>；随附 docx 的逐日表只到 10.17，"
                    "本周 10.18 仅进周合计、未进逐日，故逐日加总会比周合计少 "
                    f"<b>{ts['due'] - sum((t['dailyDue'] or 0) for t in n['treat'])}</b> 人次应做。",
        },
        "note": f"<b>本周（10.12—10.18）6 项治疗应做 {ts['due']} 人次、实做 {ts['done']} 人次，"
                f"合计完成率 {ts['rate']}%</b>（护理部口径向下取整），未做 {ts['missed']} 人次。"
                f"分项看：经颅交流电 {n['treat'][0]['done']}/{n['treat'][0]['due']}（{n['treat'][0]['rate']}%）为完成量最大项；"
                f"<b>{worst['label']} {worst['done']}/{worst['due']}（{worst['rate']}%）最低</b>；"
                f"失眠治疗仪治疗 {n['treat'][4]['done']}/{n['treat'][4]['due']}（{n['treat'][4]['rate']}%）缺口 5 人次，"
                "相对缺口最大。"
                "<b>⚠ 两个口径不要混读</b>：① 部门卡上的 484 人次是《特别行动小组汇报表》的物理治疗总人次，"
                "与本表 656 应做不是同一口径；② docx 逐日表只到 10.17，10.18 的数据只在周合计里。",
        "diag": "<div class=\"diagnosis-item tone-risk\"><b>本周判断 · 整体 93%，但两项明显掉队</b>"
                f"<p>6 项合计 {ts['done']}/{ts['due']}＝<b>{ts['rate']}%</b>，未做 <b>{ts['missed']} 人次</b>。"
                f"其中<b>{worst['label']}</b>只有 <b>{worst['rate']}%</b>（{worst['done']}/{worst['due']}），"
                f"<b>失眠治疗仪</b> <b>{n['treat'][4]['rate']}%</b>（{n['treat'][4]['done']}/{n['treat'][4]['due']}，缺口 5 人次），"
                "两项构成主要拖累；经颅交流电、脑功能、音乐放松三项均在 94% 以上，属正常波动。</p></div>"
                "<div class=\"diagnosis-item tone-orange\"><b>口径提醒</b>"
                "<p>完成率按护理部口径<b>向下取整</b>，71/75 记 94%、21/26 记 80%，"
                "不做四舍五入；若与其他系统比对出现 1 个百分点差，先看是否这一条。</p></div>",
    }
    body = json.dumps(obj, ensure_ascii=False).replace('"', "'")
    # 兼容两种写法：首次替换前是 `nursing:{range:'…'}`，替换后变成 `nursing:{'range': '…'}`（键带引号），
    # 所以键名要允许可选引号，否则第二次跑就锚不到、静默不更新（实测踩过）
    m = re.search(r"nursing:\{\s*['\"]?range['\"]?\s*:[\s\S]*?\},\n      psychology:", html)
    if not m:
        print("  ⚠ deptDaily.nursing 锚点未命中，抽屉护理块未更新")
        return html
    return html[:m.start()] + "nursing:" + body + ",\n      psychology:" + html[m.end():]


def js_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


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
        rows.append(
            f"      {k}:{{m1:{{label:{js_str(m1lab)},value:{js_str(str(m1v))},unit:{js_str(m1u)}}},"
            f"m2:{{label:{js_str(m2lab)},value:{js_str(str(m2v))},unit:{js_str(m2u)}}},\n"
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
    axis_map = {
        # 逐日：入院/出院/接触/回访（10.12—10.17）
        "d1012": ["10.12", "10.13", "10.14", "10.15", "10.16", "10.17"],
        "dpsum": ["首次", "情绪", "住院"],
    }
    add = []
    for k, v in axis_map.items():
        if f"{k}:[" not in html:
            add.append(f"      {k}:[" + ",".join(js_str(x) for x in v) + "]")
    if add:
        html = html.replace("      d6pt:['交','磁','脑','松','失','馈']",
                            "      d6pt:['交','磁','脑','松','失','馈'],\n" + ",\n".join(add), 1)

    # 3) 部门摘要（卡片名下的 delta / status / summary）与抽屉首行
    summ = {
        "doctor": ("本期出院", sgn(m["weekDischarge"]["deltaPct"]) + "%", "高优先级", "high"),
        "nursing": ("物理治疗人数", "总量口径", "待补率值", ""),
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
    rows = {
        "doctor": [f"{MARK} 本期（{LBL} · 汇报表口径 7 天）", None, dep["doctor"]["discharge"], "人",
                   f"《特别行动小组汇报表》医生组：入院 <b>{dep['doctor']['admit']}</b>、出院 <b>{dep['doctor']['discharge']}</b>、"
                   f"门诊 <b>{dep['doctor']['outpatient']}</b> 人次、物理治疗 <b>{dep['doctor']['physioWan']}</b> 万、"
                   f"总收入 <b>{dep['doctor']['revenueWan']}</b> 万。个人明细 6 人加总入院 {dep['doctor']['recon']['admit']['detail']}、"
                   f"出院 {dep['doctor']['recon']['discharge']['detail']}，差 {dep['doctor']['recon']['admit']['gap']} 入 / "
                   f"{dep['doctor']['recon']['discharge']['gap']} 出（{'、'.join(dep['doctor']['recon']['blankRows']) or '—'} 未填）。"
                   f"⚠ 营收日报台账至 {DT} 为 {m['weekRevenue'].get('ledgerValue')} 万（{N-1} 天，未含 10.18），仅作核对、不参与展示。",
                   f"上期 {PS}—{PW}", f"本期 {LBL}"],
        "nursing": [f"{MARK} 本期（{LBL} · 护理部周报）", None, dep["nursing"]["physioPeople"], "人次",
                    f"汇报表护理组表头：物理治疗 <b>{dep['nursing']['physioPeople']} 人次</b>、"
                    f"工娱 <b>{dep['nursing']['recreationSessions']} 场 / {dep['nursing']['recreationPeople']} 人次</b>。"
                    f"<br>六项治疗本周："
                    + "；".join(f"{t['label']} <b>{t['done']}/{t['due']}</b>（{t['rate']}%，未做 {t['missed']}）"
                                for t in dep["nursing"]["treat"])
                    + f"。<br>合计 <b>{dep['nursing']['treatSummary']['done']}/"
                      f"{dep['nursing']['treatSummary']['due']}</b>＝"
                      f"<b>{dep['nursing']['treatSummary']['rate']}%</b>，"
                      f"缺口 {dep['nursing']['treatSummary']['missed']} 人次；"
                      f"最低为{dep['nursing']['treatSummary']['worst']['label']}"
                      f" {dep['nursing']['treatSummary']['worst']['rate']}%。"
                      f"<br>⚠ 完成率按护理部口径<b>向下取整</b>（71/75、21/26 均不进位）；"
                      f"docx 逐日表只到 {DT}，本周 10.18 仅进周合计、未进逐日。",
                    "上周 92.1%（9.20—9.26）", f"本期 {LBL}"],
        "psychology": [f"{MARK} 本期（{LBL} · V4 管理表口径）", None, dep["psychology"]["consult"], "人次",
                       f"本周唯一口径＝V4 管理表：咨询工作量 <b>{dep['psychology']['consult']}</b> 人次、"
                       f"患者接触 <b>{dep['psychology']['contact']}</b> 人次、家长访谈 {psy['week']['parent']}、"
                       f"团体 {psy['week']['groupSessions']} 场 {psy['week']['groupPeople']} 人。"
                       f"管床本周新增 <b>{psy.get('boundWeek', {}).get('rows', 0)} 行 / {psy.get('boundWeek', {}).get('people', 0)} 个患者</b>，"
                       f"累计在管 <b>{psy.get('boundPatients', 0)}</b> 人。"
                       f"⚠ 汇报表心理组表头（40 人 / 4 场 / 19,002 元）自 <b>2026-09-21</b> 起未滚动，已停用，不参与本周计算。"
                       f"<b>对账</b>：周个人统计 5 人 vs 日报逐条，差额 "
                       + ("、".join(f"{r['label']} {r['gap']:+d}" for r in (psy.get('recon') or []) if r.get('gap')) or "无")
                       + "——均因赵芳 10-18 那条日报落在简报表末尾、周表公式未覆盖。",
                       "V4 本周", f"本期 {LBL}"],
        "service": [f"{MARK} 本期（{LBL} · 汇报表口径）", None, dep["service"]["arrived"], "人次",
                    f"汇报表客服服务部表头：到院 <b>{dep['service']['arrived']}</b> 人次（导医接待）、义诊 <b>{dep['service']['charity']}</b> 人；"
                    f"「随访人数」未填，记 null。台账（至 {DT}）：回访 {svc['week']['followup']} 条、标记到院 {svc['week']['arrived']} 人"
                    f"（{svc['week']['rate']}%）、导诊服务 {svc['week']['guide']} 条。",
                    "汇报表本周", f"本期 {LBL}"],
        "marketing": [f"{MARK} 本期（{LBL} · 数据至 {DT}）", but["prevSameDays"]["contact"], but["week"]["contact"], "条",
                      f"管家对接 <b>{but['week']['contact']}</b> 条、转住院 {but['week']['admit']} 人（<b>{but['week']['rate']}%</b>）；"
                      + " · ".join(f"{k} {v}" for k, v in but["staff"]) +
                      f"。上期同 {N} 天 {but['prevSameDays']['contact']} 条 / {but['prevSameDays']['admit']} 人（{but['prevSameDays']['rate']}%）。"
                      f"⚠ {'、'.join(but['missingStaff'])} 未填报，记 null 不降榜",
                      f"上期同 {N} 天", f"本期 {LBL}"],
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

    # 4c) 抽屉「数据变化」页：deptDaily.nursing 整块按快照重写
    html = patch_dept_daily_nursing(html, dep)
    # 4d) 抽屉「数据变化」页：deptDaily.psychology 整块按快照重写（原为 10.1—10.7 的硬编码）
    html = patch_dept_daily_psych(html, SNAP)

    # 5) 页脚口径
    foot_pat = re.compile(r'(<div class="kpi-foot"><i></i><span>)部门数据：.*?(</span></div>)', re.S)
    foot = (f'部门数据：<b>{LBL}（7 天，含 10.18）</b>·'
            f'<b>冲突裁决：以《特别行动小组汇报表》为准</b>（业主 2026-10-19 指定）——'
            f'本周营收 {m["weekRevenue"]["value"]} 万、月累计 {m["monthRevenue"]["value"]} 万、'
            f'入院 {m["weekAdmit"]["value"]}、出院 {m["weekDischarge"]["value"]}、门诊 {m["weekVisits"]["value"]} 人次、'
            f'物理治疗 {m["weekPhysio"]["value"]} 万，均取汇报表医生组表头/正文；'
            f'营收日报逐日台账（至 {DT}，合计 {m["weekRevenue"].get("ledgerValue")} 万）保留在数据核验里，供勾稽与作图，不参与展示。'
            f'护理组/客服服务部/营销中心三张卡＝汇报表各表头本周自填值；'
            f'<b>心理咨询组例外</b>：汇报表该组表头停在 2026-09-21 旧值（40 人 / 4 场 / 19,002 元）未滚动，'
            f'本周改用 V4 管理表（咨询 {psy["week"]["consult"]} 人次 / 接触 {psy["week"]["contact"]} 人次 / 团体 {psy["week"]["groupSessions"]} 场）；'
            f'客服台账＝标准化回访台账＋导诊记录；营销＝《患者有效对接表》各管家分表；到院＝《10月到院登记表》逐条（{SNAP["arrival"]["week"]} 人次，就诊口径）。'
            f'<b>缺失一律记 null、不写 0</b>：营销中心表头三项未填、客服「随访人数」未填、'
            f'医生组个人明细 {("、".join(dep["doctor"]["recon"]["blankRows"]) or "无")} 空白，均不反推。'
            f'数据源共 {len(SNAP["sources"])} 处，逐日自动采集与重算。')
    html, nfoot = foot_pat.subn(lambda x: x.group(1) + foot + x.group(2), html, count=1)
    if not nfoot:
        print("  ⚠ 页脚未替换")

    if dry:
        print(f"dry-run：长度 {orig_len} → {len(html)}（{len(html)-orig_len:+d}）")
        return
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"index.html 已更新：{orig_len} → {len(html)} 字节（{len(html)-orig_len:+d}）")


if __name__ == "__main__":
    main()
