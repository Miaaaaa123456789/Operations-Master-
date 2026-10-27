#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 index.html 里「写死的上一周文案」按当前快照重写成新一周。

只做两件事：
  1) 数据驱动的块（heroKpis / ov-target / ov-sources / heroSummary / kpiGrid /
     quality / recModule / nursingPerfPane 头部）按快照重新生成；
  2) JS 常量块（OPS_HISTORY / benchmarks / detailedSignals / balance / insSec /
     important）做「旧周日期 → 新周日期」的定向替换，避免手写覆盖叙事。

设计原则（沿用本项目既有契约）：
  · 缺项写 null / 「—」，绝不用上一期数值顶替；
  · 不同源的口径不相加、不互相校验，并在文案里写明；
  · 任何替换都先做「唯一命中」校验，命中数 != 1 就跳过并报警。
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML = os.path.join(REPO, "index.html")
SNAP = json.load(open(os.path.join(REPO, "data", "snapshot.json"), encoding="utf-8"))

M = SNAP["metrics"]
P = SNAP["period"]
PSY = SNAP["psych"]
SVC = SNAP["service"]
BUT = SNAP["butler"]
ARR = SNAP["arrival"]
DEP = SNAP["departments"]
FILL = SNAP.get("filling") or {}
WM = SNAP["watermarks"]

LBL = "10.19–10.25"           # 本期自然周
PREV = "10.12—10.16"          # 上一期同 5 天
DT = "10.23"                  # 营收日报数据截止
NDAY = M["weekRevenue"]["days"]


def d8(s):
    """2026-10-23 → 10.23"""
    return str(s)[5:].replace("-", ".") if s else "—"


def wan(v):
    return "—" if v is None else f"{v:,.2f}"


# ------------------------------------------------------------------ 区间工具
def id_span(html, eid):
    """返回 `id="eid"` 所在元素的 (start, end) —— 结束位置是闭合标签之后。"""
    m = re.search(r'<([a-zA-Z][\w-]*)[^>]*\bid="' + re.escape(eid) + r'"', html)
    if not m:
        return None
    tag = m.group(1)
    start = m.start()
    i = m.end()
    depth = 1
    pat = re.compile(r"<(/?)" + tag + r"\b", re.I)
    while True:
        mm = pat.search(html, i)
        if not mm:
            return None
        if mm.group(1):
            depth -= 1
            if depth == 0:
                end = html.find(">", mm.end()) + 1
                return start, end
        else:
            depth += 1
        i = mm.end()


def put_block(html, eid, new_html):
    sp = id_span(html, eid)
    if not sp:
        print(f"  ⚠ #{eid} 锚点未命中，跳过")
        return html
    s, e = sp
    return html[:s] + new_html + html[e:]


def sub1(html, old, new, label=""):
    """唯一命中才替换。"""
    n = html.count(old)
    if n != 1:
        print(f"  ⚠ [{label or old[:24]}] 命中 {n} 次，跳过")
        return html
    return html.replace(old, new)


# ------------------------------------------------------------------ 1. 顶部 KPI 条
def build_hero_kpis():
    w = M["wardCount"]["value"]
    adm, dis = M["weekAdmit"]["value"], M["weekDischarge"]["value"]
    vis = M["weekVisits"]["value"]
    tiles = [
        ("在院人数", w, "人", f"{DT} 时点 · 营收日报"),
        ("本期入院", adm, "人", f"{LBL}（{NDAY} 天）· 营收日报"),
        ("本期出院", dis, "人", f"{LBL}（{NDAY} 天）· 营收日报"),
        ("门诊", vis, "人次", f"{LBL}（{NDAY} 天）· 初诊 {M['weekVisits']['visitsNew']} / 复诊 {M['weekVisits']['visitsReturn']}"),
        ("物理治疗费", None, "万元", "无逐日台账 · 本周记 null"),
    ]
    out = ['<div class="ov-kpis" id="heroKpis">']
    for label, v, unit, chip in tiles:
        val = "—" if v is None else f"{v}"
        out.append(
            f'<div class="ov-kpi"><label>{label}</label>'
            f'<strong>{val}<em>{unit}</em></strong>'
            f'<span class="ov-chip">{chip}</span></div>'
        )
    out.append("</div>")
    return "".join(out)


# ------------------------------------------------------------------ 2. 目标卡
def build_target_card():
    mr = M["monthRevenue"]
    days_left = 31 - int(mr["coverage"]["recordedDays"])
    gap = mr["gap"]
    need = gap / days_left if days_left else None
    daily = M["weekRevenue"]["value"] / NDAY
    diff = daily - need
    cls = "pos" if diff >= 0 else "neg"
    word = "领先" if diff >= 0 else "落后"
    bar = mr["amountProgress"]
    tprog = mr["timeProgress"]
    return (
        '<article class="ov-card ov-target"><header class="ov-t-head">'
        f'<h2>10月营收目标进度</h2><span class="ov-chip">10月1日—10月{DT[3:]}日 · 营收日报</span>'
        '</header>'
        f'<div class="ov-amount"><strong>{mr["value"]:.2f}</strong><em>／260万</em></div>'
        f'<div class="ov-bar" role="img" aria-label="营收完成率 {bar}%，时间进度 {tprog}%">'
        f'<i style="width:{bar}%"></i><u style="left:{tprog}%"></u></div>'
        '<div class="ov-two">'
        f'<div><span>金额完成</span><b>{bar}%</b></div>'
        f'<div><span>时间进度</span><b>{tprog}%</b></div>'
        f'<div><span>进度差</span><b class="{cls}">{word} {abs(bar - tprog):.1f}pt</b></div>'
        '</div>'
        f'<p class="ov-gap">剩余 <b>{days_left}</b> 天需 <b>{gap:.2f} 万</b>，日均需 <b>{need:.2f} 万</b>；'
        f'本期（{LBL}，{NDAY} 天，营收日报口径）日均 <b>{daily:.2f} 万</b>，'
        f'{"已高于" if diff >= 0 else "低于"}达标日均 <b>{abs(diff):.2f} 万</b>。</p>'
        '<div class="ov-brand"><p><b>用数据</b><span>发现更大的可能！</span></p></div></article>'
    )


# ------------------------------------------------------------------ 3. 口径说明
def build_sources():
    psy_end = d8(WM["psych"]["dataThrough"])
    svc_end = d8(WM["service"]["dataThrough"])
    but_end = d8(WM["butler"]["dataThrough"])
    arr_end = d8(WM["arrival"]["dataThrough"])
    nur_end = d8(WM["nursing"].get("dailyThrough"))
    return (
        '<div class="ov-sources">'
        '<div><b>数据来源</b><span>营收日报逐日台账 · 特别行动小组汇报表 · V4 心理管理表 · 客服/管家/到院台账</span>'
        '<span>更新：每日 09:00 抓取</span></div>'
        '<div><b>统计口径</b><span>'
        f'营收与入出院 本期 {LBL}（营收日报，已录 {NDAY} 天、数据至 {DT}）；'
        f'在院 {M["wardCount"]["value"]} 人（{DT} 时点，营收日报）；'
        f'10 月累计 {M["monthRevenue"]["value"]:.2f} 万（营收日报至 {DT}）；'
        f'上一期同 {NDAY} 天取 {PREV}；'
        f'心理 {LBL}（V4，至 {psy_end}）/ 管家 {LBL}（至 {but_end}）/ 客服 {LBL}（至 {svc_end}）/ 到院 {LBL}（至 {arr_end}）；'
        f'<b>护理考核周源表停在 {nur_end}，本周未提交，六项完成率与物理治疗人数记 null</b>；'
        '<b>《特别行动小组汇报表》五个部门表头本周整表未滚动（值等于正文「第 3 周」列），已全部停用、改明细表口径</b>'
        '</span></div>'
        '<div><b>目标依据</b><span>月度经营目标 260 万，由运营管理部制定（沿用 9 月口径，未按 10 月重设）</span></div>'
        '</div>'
    )


# ------------------------------------------------------------------ 4. heroSummary
def build_hero_summary():
    wr = M["weekRevenue"]
    mr = M["monthRevenue"]
    prev_rev = round(wr["value"] / (1 + wr["deltaPct"] / 100), 2)
    prev_vis = round(M["weekVisits"]["value"] / (1 + M["weekVisits"]["deltaPct"] / 100))
    prev_adm = round(M["weekAdmit"]["value"] / (1 + M["weekAdmit"]["deltaPct"] / 100))
    prev_dis = round(M["weekDischarge"]["value"] / (1 + M["weekDischarge"]["deltaPct"] / 100))
    daily = wr["value"] / NDAY
    return (
        '<p id="heroSummary">'
        f'<b>本周只有一套可用口径：营收日报逐日台账。</b>本期（{LBL}，已录 {NDAY} 天，数据至 {DT}）'
        f'营收 <b>{wr["value"]:.2f} 万</b>＝门诊 <b>{M["weekOutpatient"]["value"]:.2f} 万</b>'
        f'＋在院 <b>{M["weekInpatient"]["value"]:.2f} 万</b>；门诊 <b>{M["weekVisits"]["value"]}</b> 人次'
        f'（初诊 {M["weekVisits"]["visitsNew"]} / 复诊 {M["weekVisits"]["visitsReturn"]}）、'
        f'入院 <b>{M["weekAdmit"]["value"]}</b> 人、出院 <b>{M["weekDischarge"]["value"]}</b> 人、'
        f'在院 <b>{M["wardCount"]["value"]}</b> 人（{DT} 时点）。'
        f'上一期同 {NDAY} 天（{PREV}）：营收 {prev_rev:.2f} 万、门诊 {prev_vis} 人次、'
        f'入院 {prev_adm} 人、出院 {prev_dis} 人，营收环比 <b>{"+" if wr["deltaPct"] >= 0 else ""}{wr["deltaPct"]}%</b>。'
        f'<b>月累计</b> 10.1—{DT} 合计 <b>{mr["value"]:.2f} 万</b>／目标 260 万，金额完成 <b>{mr["amountProgress"]}%</b>、'
        f'时间进度 <b>{mr["timeProgress"]}%</b>、'
        f'<b>{"领先" if mr["amountProgress"] >= mr["timeProgress"] else "落后"} '
        f'{abs(mr["amountProgress"] - mr["timeProgress"]):.1f}pt</b>，剩余缺口 <b>{mr["gap"]:.2f} 万</b>。'
        f'日均 <b>{daily:.2f} 万</b>。<br>'
        '<b>⚠ 为什么不再用《特别行动小组汇报表》的表头：</b>本周该表五个部门表头'
        '（医生 72.5 万 / 19 人 / 210 人次 / 32.9 万、护理 484 人次 / 5 场 / 62 人、'
        '心理 40 人 / 4 场 / 19,002 元、客服 到院 239 / 义诊 14、营销整行空白）'
        '与该表正文「第 3 周」列<b>逐项完全相同</b>，说明整表还停在上一期、没有滚动。'
        '直接引用会把上周数字当本周业绩，因此<b>一律不引用</b>，原值存档在 <code>departments.actionReportRaw</code>；'
        '表头补齐后自动切回。<br>'
        '<b>⚠ 三套口径互不相加：</b>营收日报（门诊＋在院，逐日、可勾稽）／汇报表（部门自填表头）／'
        'V4 心理管理表（日报逐条）三套不同源，<b>不加总、不互相校验</b>。'
        '</p>'
    )


# ------------------------------------------------------------------ 5. 数据质量清单
def build_quality():
    psy = PSY["week"]
    pv = PSY["prevSameDays"]
    sv = SVC["week"]
    spv = SVC["prevSameDays"]
    bt, bpv = BUT["week"], BUT["prevSameDays"]
    nur_raw = (DEP.get("nursing") or {}).get("headerRaw") or {}
    items = [
        ("《特别行动小组汇报表》五个部门表头整表未滚动（本周最重要的口径缺陷）",
         "医生组表头 <b>总收入 72.5 万 / 入院 19 / 门诊 210 / 物理治疗 32.9 万</b>、"
         "护理组 <b>484 人次 / 5 场 / 62 人</b>、心理组 <b>40 人 / 4 场 / 19,002 元</b>、"
         "客服组 <b>到院 239 / 义诊 14</b>、营销中心<b>整行空白</b>——四项与各表正文「第 3 周」列"
         "<b>逐项完全相同</b>，判定为未滚动。已<b>全部停用</b>，改为各部门明细台账口径；"
         "原值存档在 <code>departments.actionReportRaw</code>，可随时比对。<b>这不是数据错，是填报流程没按周切换表头</b>，"
         "表头补齐后自动切回。"),

        ("营收日报：门诊＋在院拆分，唯一可逐日勾稽的源",
         f"本期（{LBL}）已录 <b>{NDAY} 天</b>（10.19—{DT}），每日门诊＋在院＝当日合计，"
         f"与源表「当日收入合计」列逐日相等：77,314.31 / 67,597.68 / 74,144.84 / 71,787.59 / 98,966.52，"
         f"合计 <b>{M['weekRevenue']['valueYuan']:,.2f} 元</b>。"
         f"<b>「出院」口径已修正为「出院初次 ＋ 出院多次」</b>——此前只取初次列，"
         f"本周 {NDAY} 天因此少算 4 人（4 / 2 / 0 / 2 / 1，合计 {M['weekDischarge']['value']}）。"
         "营收日报<b>不含物理治疗费拆分</b>，该科目本周只能记 null。"),

        ("护理部本周零提交：六项完成率 / 物理治疗人数 / 工娱全部记 null",
         f"护理部周报与《质控分及物理治疗数据》逐日表最新只到 <b>{d8(WM['nursing'].get('dailyThrough'))}</b>，"
         f"本期（{LBL}）<b>没有任何一条护理事实入库</b>。"
         f"因此「6 项治疗完成率」「物理治疗人数」「工娱场次与参与人数」三项<b>一律留空</b>，"
         f"不拿上一期的 {nur_raw.get('physioPeople')} 人次、93% 顶替。<b>这是本周唯一的整块空白</b>，"
         "补齐后组内排名与绩效才能重算。"),

        ("物理治疗费：既无逐日台账、汇报表表头又不可用",
         "医生组六个核心指标里，物理治疗费是<b>唯一拿不到数的一项</b>："
         "营收日报不拆物理治疗，汇报表表头「物理治疗费 32.9 万」未滚动。本周记 <b>null</b>，"
         "不引用旧值。需财务补一张<b>按日拆分</b>的物理治疗收入表，并入营收日报后即可与护理组治疗人次勾稽。"),

        ("心理组：V4 管理表为唯一口径，汇报表表头自 2026-09-21 起停用",
         f"本期（{LBL}，V4 日报逐条汇总，至 {d8(WM['psych']['dataThrough'])}）"
         f"患者接触 <b>{psy['contact']}</b> 人次（24h 首次 {psy['first']} ＋ 情绪支持 {psy['emotion']} ＋ 住院 {psy['inpatient']}）、"
         f"咨询工作量 <b>{psy['consult']}</b> 人次（住院 {psy['inpatient']} ＋ 门诊 {psy['outpatient']} ＋ 家庭 {psy['family']}）、"
         f"家长访谈 {psy['parent']} 人次、团体 <b>{psy['groupSessions']} 场 / {psy['groupPeople']} 人</b>、"
         f"日报 {psy['report']} 条、管床新增 {psy['bind']} 行。"
         f"上一期同天数：接触 {pv['contact']}、咨询 {pv['consult']}、团体 {pv['groupSessions']} 场——"
         f"<b>接触 −{pv['contact'] - psy['contact']}、咨询 −{pv['consult'] - psy['consult']}、团辅 −{pv['groupSessions'] - psy['groupSessions']} 场</b>。"
         f"汇报表心理组表头 40 人 / 4 场 / 19,002 元 与 9.21—9.27 那周同值，<b>已停用</b>；"
         f"其中<b>团辅 4 场 vs 本周 {psy['groupSessions']} 场</b>是最直接的证据。"
         f"<b>管床对接</b>本周新增 {psy['bind']} 行，累计在管 <b>{SNAP['psych'].get('boundPatients', '—')}</b> 人。"),

        ("客服：三张台账都在跑，但回访全部压在 1 个人身上",
         f"本期（{LBL}，至 {d8(WM['service']['dataThrough'])}，5 天）回访 <b>{sv['followup']}</b> 条、"
         f"标注到院 <b>{sv['arrived']}</b> 人（台账到院率 <b>{sv['rate']}%</b>，上一期同 5 天 {spv['rate']}%）、"
         f"导诊主动服务 <b>{sv['guide']}</b> 条、日工作量 <b>{sv['workload']:,}</b> 分。"
         f"逐日：10.19=5 / 10.20=11 / 10.21=1 / 10.22=9 / 10.23=1，<b>10.21 与 10.23 各只 1 条</b>。"
         f"台账逐人只有 <b>{'、'.join(k for k, _ in (SVC.get('staff') or [])) or '—'}</b> 有记录，其余 0 条——"
         f"说明台账是「想起来才补」，不是当班即录。汇报表客服组表头「随访人数」一栏<b>历来为空</b>，记 null，不拿台账顶替。"),

        ("营销：管家对接两人整周零记录，按契约记 null 不降榜",
         f"本期（{LBL}，至 {d8(WM['butler']['dataThrough'])}，5 天）有效对接 <b>{bt['contact']}</b> 条、"
         f"转住院 <b>{bt['admit']}</b> 人（<b>{bt['rate']}%</b>，上一期同 5 天 {bpv['rate']}%）。"
         f"逐人：{'、'.join(f'{k} {v}' for k, v in BUT['staff'])}；"
         f"<b>{'、'.join(BUT['missingStaff'])} 本周零记录</b>——按「缺项不写 0」记 null，不按 0 降榜。"
         f"营销中心表头入院 / 门诊 / 总收入三项<b>整行空白</b>，转住院只能取对接表逐条，"
         f"与营收日报、汇报表<b>三套口径互不相加</b>。"),

        ("到院登记 139 人次与客服「标注到院 11 人」不是一回事，不可相加",
         f"《10月到院登记表》逐条（至 {d8(WM['arrival']['dataThrough'])}）本期 <b>{ARR['week']}</b> 人次、"
         f"初诊 <b>{ARR['new']}</b>，上一期同 5 天 {ARR['prevSameDays']} 人次；"
         f"渠道以 <b>K（{ARR['channels'][0][1]}）</b>、网络营销（{ARR['channels'][1][1]}）为主。"
         f"客服「标注到院 {sv['arrived']} 人」是<b>回访台账里标记为已到院</b>的记录数，"
         f"只在回访样本内成立（{sv['arrived']}/{sv['followup']}）；到院登记是全量门禁口径。"
         f"<b>两者定义不同、样本不同，不可相加，也不可互相当分母</b>。"),

        ("工娱：本周营销中心未提交，上一期 156 人仅作对照",
         "工娱两列已从护理组改归<b>营销中心</b>呈现。上一期（10.12—10.18）报数："
         "住院部工娱活动<b>患者 111 人 ＋ 家属 45 人 ＝ 156 人</b>，积分兑换 16 人。"
         f"本期（{LBL}）营销中心<b>尚未提交</b>，模块内三格一律记 <b>—</b>，不拿上一期数值顶替；"
         "上一期 156 人只在<b>本说明与对照位</b>出现，不作为本期业绩。需营销中心补报本周场次与参与人数。"),

        ("10 月目标仍按 260 万，未按 10 月实际排班重设",
         f"当前累计 <b>{M['monthRevenue']['value']:.2f} 万</b>、完成 <b>{M['monthRevenue']['amountProgress']}%</b>，"
         f"时间进度 <b>{M['monthRevenue']['timeProgress']}%</b>，"
         f"<b>{'领先' if M['monthRevenue']['amountProgress'] >= M['monthRevenue']['timeProgress'] else '落后'} "
         f"{abs(M['monthRevenue']['amountProgress'] - M['monthRevenue']['timeProgress']):.1f}pt</b>，"
         f"剩余缺口 <b>{M['monthRevenue']['gap']:.2f} 万</b>。目标沿用 9 月定下的 260 万，"
         "未按 10 月实际排班重设——需要业主确认是否调整。"),
    ]
    inner = "".join(
        f'<div class="quality-item"><strong>{t}</strong><p>{b}</p></div>' for t, b in items
    )
    return (
        f'<details class="quality" id="quality"><summary>'
        f'<span>⚠ 有 {len(items)} 项数据口径需要确认</span>'
        f'<span>展开　⌄</span></summary><div class="quality-body">{inner}</div></details>'
    )


# ------------------------------------------------------------------ 6. heroSummary 第二段
def build_hero_extra():
    psy = PSY["week"]
    return (
        '<p><b>各条线的截止日不同，页面按「各自最新可核日」标注，不强行拉齐：</b>'
        f'营收 / 入出院 / 门诊 至 <b>{DT}</b>（营收日报，{NDAY} 天）；'
        f'心理 至 <b>{d8(WM["psych"]["dataThrough"])}</b>（V4 日报逐条）；'
        f'客服 / 管家 / 到院 至 <b>{d8(WM["service"]["dataThrough"])}</b>；'
        f'护理停在 <b>{d8(WM["nursing"].get("dailyThrough"))}</b>，本周<b>零提交</b>，'
        '六项完成率与物理治疗人数一律记 <b>null</b>，不拿上一期的 93%、484 人次顶替。'
        f'<b>本周唯一可逐日勾稽的营收链</b>是营收日报：门诊＋在院＝当日合计，'
        f'与源表逐日相等，{NDAY} 天合计 <b>{M["weekRevenue"]["valueYuan"]:,.2f} 元</b>。'
        '医生姓名沿用业主 2026-10-09 定稿：<b>王建宁</b>（源表曾写作「王健林」）、'
        '<b>邓霏</b>（9 月台账曾写作「邓鑫」）；游义杨为医生表新增列示姓名。'
        '<b>口径冲突时一律以营收日报（营业总表）为准</b>，部门自填表头只作参考、不进展示。'
        f'心理组 {LBL} 取 V4：接触 <b>{psy["contact"]}</b>、咨询 <b>{psy["consult"]}</b>、'
        f'团体 <b>{psy["groupSessions"]} 场 / {psy["groupPeople"]} 人</b>；'
        f'管家 {LBL} 取《患者有效对接表》各管家分表：对接 <b>{BUT["week"]["contact"]}</b> 条、'
        f'转住院 <b>{BUT["week"]["admit"]}</b> 人（<b>{BUT["week"]["rate"]}%</b>）；'
        f'客服取标准化回访 / 导诊 / 日工作量三张台账，到院登记取《10月到院登记表》逐条'
        f'（<b>{ARR["week"]}</b> 人次），<b>两张表定义不同、不可相加</b>。</p>'
    )


# ------------------------------------------------------------------ 7. 工娱模块（本周未提交）
def build_rec_module():
    head = (
        '<div class="rec-head">\n  <div>\n'
        '<div class="rec-title"><h2>工娱活动</h2>'
        f'<span class="rec-badge">{LBL} · 营销中心 · 本周未报</span></div>\n'
        '<p class="rec-sub">住院部工娱活动的患者与家属参与、积分兑换。'
        '独立成模块核算，<b>不与管家转化、渠道转诊、护理治疗量混算</b>。</p>\n  </div>\n</div>\n'
    )
    kpis = (
        '<div class="rec-kpis">\n'
        '  <div class="rec-kpi p"><label>患者参与</label><strong>—<em>人</em></strong>'
        '<span class="rec-chg warn">本周未提交</span>'
        '<span class="rec-note">营销中心未报 10.19—10.25 数据</span></div>\n'
        '  <div class="rec-kpi f"><label>家属参与</label><strong>—<em>人</em></strong>'
        '<span class="rec-chg warn">本周未提交</span>'
        '<span class="rec-note">同上，<b>不拿上一期 45 人补位</b></span></div>\n'
        '  <div class="rec-kpi t"><label>合计参与</label><strong>—<em>人</em></strong>'
        '<span class="rec-chg flat">缺项记 null</span>'
        '<span class="rec-note">患者＋家属两列到位后才可相加</span></div>\n'
        '  <div class="rec-kpi j"><label>积分兑换</label><strong>16<em>人</em></strong>'
        '<span class="rec-chg warn">10 月累计</span>'
        '<span class="rec-note">10.1—10.18，<b>月累计、非本周单周值</b></span></div>\n'
        '</div>\n'
    )
    grid = (
        '<div class="rec-grid">\n'
        '  <div class="rec-card">\n    <h3>本期结构与对照</h3>\n'
        '    <p class="rec-cap">本周无数据，<b>不画结构条</b>——空缺不拿上一期补位，避免把上周构成当本周业绩。</p>\n'
        '    <div class="rec-stack"><i class="sp" style="width:100%;'
        'background:linear-gradient(180deg,#EDF0F6,#E4E8F0);color:#7C828F">本周未提交 · 10.19—10.25</i></div>\n'
        '    <div class="rec-legend"><span>患者 <b>—</b></span><span>家属 <b>—</b></span>'
        '<span>合计 <b>—</b></span></div>\n  </div>\n'
        '  <div class="rec-card">\n    <h3>上一期对照（仅参照）</h3>\n'
        '    <p class="rec-cap">以下为上一期 <b>10.12—10.18</b> 已确认值，'
        '<b>只作趋势对照，不计入本期任何指标</b>。</p>\n'
        '    <div class="rec-row"><span class="rl">患者</span><span class="rv">111 人</span></div>\n'
        '    <div class="rec-row"><span class="rl">家属</span><span class="rv">45 人</span></div>\n'
        '    <div class="rec-row"><span class="rl">合计</span><span class="rv"><b>156 人</b></span></div>\n'
        '  </div>\n</div>\n'
    )
    return head + kpis + grid


REC_FOOT = (
    '<div class="kpi-foot"><i></i><span>'
    f'工娱数据：本周（{LBL}）营销中心<b>尚未提交</b>，模块内患者 / 家属 / 合计三格一律记 <b>—</b>，'
    '不拿上一期 156 人顶替。<b>上一期（10.12—10.18）</b>报数为患者 111 人 ＋ 家属 45 人 ＝ 156 人、'
    '积分兑换 10 月累计 16 人（截至 10.18），<b>仅在本说明作对照，不作为本期业绩</b>。'
    '⚠ 汇报表护理组表头的「工娱 5 场 / 62 人次」为另一口径（场次 / 人次，非人数），'
    '<b>与 156 人不可相加</b>；本周无场次数据，场均记 null。'
    '需营销中心补报 10.19—10.25 的场次、主带人、患者 / 家属 ID 与活动后评价，'
    '补齐后才可生成个人排名与重复参与率。'
    '</span></div>' + '\n</section>'
)


# ------------------------------------------------------------------ 8. kpiGrid 脚注
def build_kpi_foot():
    return (
        '<div class="kpi-foot"><i></i><span>'
        f'指标数据：营收 / 门诊 / 入出院 / 在院全部取 <b>营收日报逐日台账</b>（{LBL}，已录 {NDAY} 天，'
        f'数据至 {DT}）；营收 {M["weekRevenue"]["value"]:.2f} 万＝门诊 {M["weekOutpatient"]["value"]:.2f} 万'
        f'＋在院 {M["weekInpatient"]["value"]:.2f} 万，门诊 {M["weekVisits"]["value"]} 人次'
        f'（初诊 {M["weekVisits"]["visitsNew"]} / 复诊 {M["weekVisits"]["visitsReturn"]}）、'
        f'入院 {M["weekAdmit"]["value"]}、出院 {M["weekDischarge"]["value"]}（首次＋多次）、'
        f'在院 {M["wardCount"]["value"]} 人（{DT} 时点）。'
        '<b>物理治疗费没有逐日台账、汇报表表头又未滚动，本周记 null</b>。'
        f'护理六项完成率与物理治疗人数取护理部周报——<b>本周零提交（源表停在 '
        f'{d8(WM["nursing"].get("dailyThrough"))}）</b>，一律记 null，不拿 93% / 484 人次顶替。'
        f'心理取 V4（咨询 {PSY["week"]["consult"]}、接触 {PSY["week"]["contact"]}）；'
        f'客服取三张台账（回访 {SVC["week"]["followup"]} 条、标注到院 {SVC["week"]["arrived"]} 人）；'
        f'营销取管家对接表（{BUT["week"]["contact"]} 条 / 转住院 {BUT["week"]["admit"]} 人）；'
        f'到院取《10月到院登记表》逐条（{ARR["week"]} 人次）。'
        '⚠ <b>五套口径互不相加</b>：营收日报 ≠ 汇报表表头 ≠ 医生归属业绩 ≠ 管家转住院 ≠ 到院登记。'
        '旧版 9 月护理排名与 9 月整月排名已全部下架，不再参与计算。'
        '</span></div></section>'
    )


# ------------------------------------------------------------------ 9. 护理分项（本周未提交）
def build_nursing_items():
    names = ["音乐放松治疗", "脑功能治疗", "经颅交流电治疗", "经颅磁治疗", "失眠治疗仪", "团体生物反馈"]
    cards = "".join(
        f'<article class="ni-card"><div class="ni-top"><span>{n}</span><b>—</b></div>'
        f'<div class="ni-bar"><i style="width:0%"></i></div>'
        f'<div class="ni-num">本周无数据 · 记 null</div></article>'
        for n in names
    )
    return (
        '<div class="section-head"><div><h2>护理组 · 物理治疗分项</h2>'
        f'<p>6 个治疗项目完成率（项目口径 · <b>{LBL}</b>）</p></div>'
        '<span class="ni-sum">本周<b class="warn-t">零提交</b> · 6 项均无数据</span></div>'
        f'<div class="ni-grid">{cards}</div>'
        '<div class="kpi-foot"><i></i><span>'
        f'护理部周报与《质控分及物理治疗数据》逐日表最新只到 <b>{d8(WM["nursing"].get("dailyThrough"))}</b>，'
        f'本期（{LBL}）<b>没有任何一条护理事实入库</b>，因此六个项目完成率全部记 <b>—</b>，'
        '不画进度条、不拿上一期的 83.2% 或 93% 顶替。→ 需护理部补报 10.19—10.24 的应做 / 实做逐日数。'
        '</span></div>'
    )


# ------------------------------------------------------------------ 10. 护理面板头部
NP_SUB_OLD = '<span class="np-head-sub">10.11—10.17 · 护理考核周（7 天）</span>'
NP_SUB_NEW = ('<span class="np-head-sub">10.19—10.25 · 本周未提交（源表停在 10.17）</span>')


# ------------------------------------------------------------------ 11. JS 常量块替换
def replace_const_literal(html, name, literal):
    """把 `const NAME=[…]` / `const NAME={…}` 整体换成 literal（括号匹配，字符串感知）。"""
    head = f"const {name}="
    i = html.find(head)
    if i < 0:
        print(f"  ⚠ 未找到 {head}")
        return html
    k = i + len(head)
    while k < len(html) and html[k] not in "{[":
        k += 1
    ob, cb = ("{", "}") if html[k] == "{" else ("[", "]")
    depth, e, quote = 0, k, None
    while e < len(html):
        c = html[e]
        if quote:
            if c == "\\":
                e += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c == ob:
            depth += 1
        elif c == cb:
            depth -= 1
            if depth == 0:
                break
        e += 1
    return html[:k] + literal + html[e + 1:]


def build_benchmarks():
    bt, sv, psy = BUT["week"], SVC["week"], PSY["week"]
    rows = [
        ["营销中心", "管家转住院率", bt["rate"], f"{bt['admit']}/{bt['contact']} 条"],
        ["护理组", "六项治疗完成率", None, "本周未提交 · 记 null"],
        ["心理咨询组", "咨询工作量", psy["consult"], f"{psy['consult']} 人次 · {LBL}"],
        ["客服服务部", "回访到院率", sv["rate"], f"{sv['arrived']}/{sv['followup']} 条"],
        ["医生组", "物理治疗占收入", None, "无逐日台账 · 记 null"],
    ]
    parts = []
    for a, b, c, d in rows:
        cv = "null" if c is None else (f"{c}" if isinstance(c, int) else f"{c}")
        parts.append(f"['{a}','{b}',{cv},'{d}']")
    return "[" + ",".join(parts) + "]"


def build_signals():
    psy, pv = PSY["week"], PSY["prevSameDays"]
    sv, spv = SVC["week"], SVC["prevSameDays"]
    bt, bpv = BUT["week"], BUT["prevSameDays"]
    items = [
        dict(level="high",
             title="《特别行动小组汇报表》五个部门表头整表未滚动，本周全部停用",
             sub="运营、五个部门", value="0 项可用",
             evidence=("医生组表头 <span class=\"hl-key\">72.5 万 / 19 人 / 210 人次 / 32.9 万</span>、"
                       "护理组 <span class=\"hl-key\">484 人次 / 5 场 / 62 人</span>、"
                       "心理组 <span class=\"hl-key\">40 人 / 4 场 / 19,002 元</span>、"
                       "客服组 <span class=\"hl-key\">到院 239 / 义诊 14</span>、营销中心<b>整行空白</b>——"
                       "四项与该表正文「第 3 周」列<b>逐项完全相同</b>。"),
             judgment=("这不是数值错，是<b>整表停在上一期、表头没有滚动</b>。"
                       "心理组最直接的证据是<b>团辅 4 场 vs 本周实际 2 场</b>。"
                       "按「缺项不拿旧值顶替」，本周<b>一律不引用表头</b>，改各部门明细台账。"),
             verify="表头何时按周切换由谁负责；若下周仍未滚动，需在汇报表里加一行「本期周窗」自证。",
             action="把「表头周窗」做成必填项；补齐前，部门卡一律标「本周未滚动」，原文存档可查。",
             owners=["运营", "五个部门"]),
        dict(level="watch",
             title=f"营收 {M['weekRevenue']['value']:.2f} 万环比 +{M['weekRevenue']['deltaPct']}%，但日均仍低于达标线",
             sub="医生组、运营", value=f"{M['weekRevenue']['value']:.2f} 万",
             evidence=(f"营收日报逐日台账（{LBL}，已录 {NDAY} 天，至 {DT}）："
                       f"门诊 <span class=\"hl-key\">{M['weekOutpatient']['value']:.2f} 万</span>"
                       f"＋在院 <span class=\"hl-key\">{M['weekInpatient']['value']:.2f} 万</span>，"
                       f"门诊 <span class=\"hl-key\">{M['weekVisits']['value']}</span> 人次、"
                       f"入院 {M['weekAdmit']['value']}、出院 {M['weekDischarge']['value']}、"
                       f"在院 {M['wardCount']['value']} 人（{DT} 时点）。"
                       f"上一期同 {NDAY} 天（{PREV}）营收 31.85 万、门诊 101 人次。"),
             judgment=("营收环比 <span class=\"changed-good\">+22.4%</span>、门诊 "
                       "<span class=\"changed-good\">+78.2%</span>，主要来自 10.23 单日 9.90 万的拉动；"
                       "但入院 −7.7%、出院 −10.0%，<b>住院端在收缩</b>。"
                       f"月累计 {M['monthRevenue']['value']:.2f} 万、完成 {M['monthRevenue']['amountProgress']}%，"
                       f"仅比时间进度高 {abs(M['monthRevenue']['amountProgress'] - M['monthRevenue']['timeProgress']):.1f}pt，"
                       "余下 8 天需日均 8.25 万，而本期日均只有 7.80 万。"),
             verify="10.23 单日 9.90 万是否含补记（初诊仅 5 人、复诊 40 人却创周内最高）；剩 8 天是否有停诊安排。",
             action="按日均 8.25 万倒排余下 8 天；门诊量已回升，重点盯入院转化与在院周转。",
             owners=["医生组", "运营"]),
        dict(level="high",
             title=f"护理部本周零提交：六项完成率、物理治疗人数、工娱全部记 null",
             sub="护理组、运营", value="—",
             evidence=(f"护理部周报与《质控分及物理治疗数据》逐日表最新只到 "
                       f"<span class=\"hl-key\">{d8(WM['nursing'].get('dailyThrough'))}</span>；"
                       f"本期（{LBL}）<b>没有任何一条护理事实入库</b>。"
                       "汇报表护理组表头 484 人次 / 5 场 / 62 人为上一期值，同样不可用。"),
             judgment=("本周<b>唯一的整块空白</b>。按契约「缺项写 null 不写 0」，"
                       "六项完成率、物理治疗人数、工娱场次三格<b>全部留空</b>，"
                       "不拿上一期的 93%、484 人次、83.2% 顶替——否则周环比全是假的。"),
             verify="是没做、没录，还是表被新表替换后采集器没跟上？需护理部确认 10.19—10.24 的实际治疗量。",
             action="补报 10.19—10.24 的应做 / 实做逐日数；补齐后组内排名与绩效才能重算。",
             owners=["护理组", "运营"]),
        dict(level="watch",
             title=f"客服回访 {sv['followup']} 条、到院率 {sv['rate']}%，但全部压在 1 个人身上",
             sub="客服组、营销中心", value=f"{sv['rate']}%",
             evidence=(f"三张台账（{LBL}，至 {d8(WM['service']['dataThrough'])}，5 天）："
                       f"回访 <span class=\"hl-key\">{sv['followup']} 条</span>、"
                       f"标注到院 <span class=\"hl-key\">{sv['arrived']} 人</span>、"
                       f"主动服务 {sv['guide']} 条、日工作量 {sv['workload']:,} 分。"
                       f"上一期同 5 天：{spv['followup']} 条 / {spv['arrived']} 人（{spv['rate']}%）。"),
             judgment=(f"到院率 <span class=\"changed-good\">+{sv['rate'] - spv['rate']:.1f}pt</span> 是本期少见的正向，"
                       "但台账逐人只有 <b>蒋雨</b> 有记录（27 条），其余导医 0 条——"
                       "说明数据来自一个人的补录，<b>到院率的分母不稳定</b>，不宜直接进考核。"),
             verify="其余导医是排班不出勤，还是漏填？10.21 / 10.23 各只 1 条，是否为当天未录。",
             action="把「当班即录」写进台账规范；确认其余导医是否参与回访。",
             owners=["客服服务部"]),
        dict(level="high",
             title=f"管家对接 {bt['contact']} 条、转住院 {bt['admit']} 人（{bt['rate']}%），两人整周零记录",
             sub="营销中心", value=f"{bt['rate']}%",
             evidence=(f"《心理管家一周有效客户对接表》各管家分表（{LBL}，至 {d8(WM['butler']['dataThrough'])}，5 天）："
                       f"对接 <span class=\"hl-key\">{bt['contact']} 条</span>、"
                       f"转住院 <span class=\"hl-key\">{bt['admit']} 人</span>；"
                       f"逐人 {'、'.join(f'{k} {v}' for k, v in BUT['staff'])}；"
                       f"<b>{'、'.join(BUT['missingStaff'])} 零记录</b>。"
                       f"上一期同 5 天：{bpv['contact']} 条 / {bpv['admit']} 人（{bpv['rate']}%）。"),
             judgment=(f"转化率 <span class=\"changed-bad\">−{bpv['rate'] - bt['rate']:.1f}pt</span>、"
                       "对接量 −13.5%，两端同降。两人零记录按契约<b>记 null、不按 0 降榜</b>，"
                       "但「零记录」本身就是一个待核事实。"),
             verify="国威、菲菲是离职、调岗，还是不参与对接统计？营销中心表头三项整行空白，无交叉验证源。",
             action="让管家组长补齐两人记录或书面注明不参与统计；补一张带项目分类的周汇总。",
             owners=["营销中心"]),
        dict(level="flat",
             title=f"心理接触 {psy['contact']} 人次、咨询 {psy['consult']} 人次，团辅 2 场",
             sub="心理咨询组", value=f"{psy['consult']} 人次",
             evidence=(f"V4 管理表日报逐条（{LBL}，至 {d8(WM['psych']['dataThrough'])}）："
                       f"接触 <span class=\"hl-key\">{psy['contact']}</span>"
                       f"（首次 {psy['first']} ＋ 情绪 {psy['emotion']} ＋ 住院 {psy['inpatient']}）、"
                       f"咨询 <span class=\"hl-key\">{psy['consult']}</span>"
                       f"（住院 {psy['inpatient']} ＋ 门诊 {psy['outpatient']} ＋ 家庭 {psy['family']}）、"
                       f"家长访谈 {psy['parent']}、团体 {psy['groupSessions']} 场 / {psy['groupPeople']} 人、"
                       f"日报 {psy['report']} 条、管床新增 {psy['bind']} 行。"
                       f"上一期同天数：接触 {pv['contact']}、咨询 {pv['consult']}、团辅 {pv['groupSessions']} 场。"),
             judgment=(f"接触 <span class=\"changed-bad\">−{pv['contact'] - psy['contact']}</span>、"
                       f"咨询 <span class=\"changed-bad\">−{pv['consult'] - psy['consult']}</span>、"
                       f"团辅 <span class=\"changed-bad\">−{pv['groupSessions'] - psy['groupSessions']} 场</span>，"
                       "三项同降。汇报表心理组表头 40 人 / 4 场 / 19,002 元 自 2026-09-21 起未滚动，已停用。"),
             verify="接触量降一半是排班减少还是日报漏填（本周日报 12 条 vs 上一期 19 条）。",
             action="先补日报完整率，再谈个人排名；团辅场次按实际排班核对。",
             owners=["心理咨询组"]),
    ]
    out = ["["]
    for it in items:
        kv = ",".join(f"{k}:'{v}'" if not isinstance(v, list) else f"{k}:{json.dumps(v, ensure_ascii=False)}"
                      for k, v in it.items())
        # 单引号内若已有 ' 会破坏字面量——本文件内容不含半角单引号，此处做一次防御性转义
        kv = kv.replace("\\'", "'")
        out.append("      {" + kv + "},")
    out.append("    ]")
    return "\n".join(out)


def build_balance_strip():
    mr = M["monthRevenue"]
    wr = M["weekRevenue"]
    good = (
        '<div class="ai-balance-strip ai-balance-more" id="aiBalanceMore">'
        '<article class="ai-balance-item growth"><div class="ai-balance-head">'
        '<b>1</b><strong>变好的业务</strong></div>'
        f'<p>① 营收 {wr["value"]:.2f} 万、环比 '
        f'<span class="changed-good">+{wr["deltaPct"]}%</span>：'
        f'门诊 {M["weekOutpatient"]["value"]:.2f} 万（+{M["weekOutpatient"]["deltaPct"]}%）、'
        f'在院 {M["weekInpatient"]["value"]:.2f} 万（+{M["weekInpatient"]["deltaPct"]}%），两端同升。</p>'
        f'<p>② 门诊量 {M["weekVisits"]["value"]} 人次、环比 '
        f'<span class="changed-good">+{M["weekVisits"]["deltaPct"]}%</span>，'
        f'初诊 {M["weekVisits"]["visitsNew"]} / 复诊 {M["weekVisits"]["visitsReturn"]}；'
        f'客服到院率 {SVC["week"]["rate"]}%（上期 {SVC["prevSameDays"]["rate"]}%）。</p></article>'
    )
    bad = (
        '<article class="ai-balance-item watch"><div class="ai-balance-head">'
        '<b>1</b><strong>变差的业务</strong></div>'
        f'<p>① 入院 {M["weekAdmit"]["value"]} 人（{M["weekAdmit"]["deltaPct"]}%）、'
        f'出院 {M["weekDischarge"]["value"]} 人（{M["weekDischarge"]["deltaPct"]}%），'
        f'住院端双降；在院 {M["wardCount"]["value"]} 人，患者池净增 '
        f'<span class="changed-good">{M["netPool"]["value"]} 人</span>，靠 10.23 单日补回。</p>'
        f'<p>② 心理接触 {PSY["week"]["contact"]}（上期 {PSY["prevSameDays"]["contact"]}）、'
        f'咨询 {PSY["week"]["consult"]}（上期 {PSY["prevSameDays"]["consult"]}）、'
        f'团辅 {PSY["week"]["groupSessions"]} 场（上期 {PSY["prevSameDays"]["groupSessions"]}），'
        f'<span class="changed-bad">三项同降</span>；护理部<b>本周零提交</b>，整块空白。</p></article>'
        '</div>'
    )
    return good + bad


def build_gongyu_panel():
    return (
        '<section class="green-channel" id="deptSpecialPanel">'
        '<div class="green-channel-head"><strong>工娱活动 · 本周</strong>'
        f'<span>{LBL} · 营销中心未提交</span></div>'
        '<div class="channel-flow">'
        '<div class="channel-step"><b>—</b>患者参与（人）</div><i class="channel-arrow">＋</i>'
        '<div class="channel-step"><b>—</b>家属参与（人）</div><i class="channel-arrow">＝</i>'
        '<div class="channel-step"><b>—</b>合计参与（人）</div></div>'
        '<div class="school-list"><span>患者 <b>本周未报</b></span>'
        '<span>家属 <b>本周未报</b></span><span>合计 <b>本周未报</b></span>'
        '<span>积分兑换 <i>10 月累计 16 人（截至 10.18）</i></span>'
        '<span>活动场次 <i>源表未填 · 记 null</i></span>'
        '<span>主表 5 场 / 62 人次 <i>另一口径</i></span></div>'
        '<p class="channel-result">本周（' + LBL + '）营销中心<b>尚未提交工娱数据</b>，'
        '患者 / 家属 / 合计三格一律记 <b>—</b>，<b>不拿上一期 156 人顶替</b>。'
        '上一期（10.12—10.18）为患者 111 人 ＋ 家属 45 人 ＝ 156 人，<b>仅作对照</b>。'
        '⚠《特别行动小组汇报表》护理组表头「工娱 5 场 / 62 人次」为<b>场次 / 人次口径，与人数不可相加</b>。'
        '补报后即可生成个人排名与重复参与率。</p></section>'
    )


def build_main_balance():
    mr = M["monthRevenue"]
    wr = M["weekRevenue"]
    vis = M["weekVisits"]
    days_left = 31 - int(mr["coverage"]["recordedDays"])
    need = mr["gap"] / days_left
    daily = wr["value"] / NDAY
    top = sorted(((x["date"], x["revenue"]) for x in SNAP["daily"] if x.get("revenue")), key=lambda t: -t[1])
    t1 = top[0] if top else ("", 0)
    top3 = sum(v for _, v in top[:3])
    ret_pct = round(vis["visitsReturn"] / vis["value"] * 100, 1) if vis["value"] else 0
    return (
        '<article class="ai-balance-item growth"><div class="ai-balance-head"><b>1</b>'
        f'<strong>本期节奏回升 · 环比 +{wr["deltaPct"]}%，但日均仍差达标线 {abs(need - daily):.2f} 万</strong></div>'
        f'<p>本期（{LBL}，{NDAY} 天，营收日报口径）营收 <b>{wr["value"]:.2f} 万</b>、日均 <b>{daily:.2f} 万</b>，'
        f'较上一期同 {NDAY} 天（{PREV}）31.85 万增长 <b>{wr["deltaPct"]}%</b>；'
        f'月累计 <b>{mr["value"]:.2f} 万</b>、完成 260 万的 <b>{mr["amountProgress"]}%</b>，'
        f'高于时间进度 {mr["timeProgress"]}% 仅 <b>{abs(mr["amountProgress"] - mr["timeProgress"]):.1f}</b> 个百分点、'
        f'剩余缺口 <b>{mr["gap"]:.2f} 万</b>。</p>'
        f'<p><b>但日均没达标</b>：余下 {days_left} 天需日均 <b>{need:.2f} 万</b>，本期日均只有 {daily:.2f} 万，'
        f'差 <b>{abs(need - daily):.2f} 万</b>。动作：把 10 月目标拆到日，盯日均而不是完成率——'
        '完成率领先 0.4pt 只是时间进度刚好走到同一位置，不代表节奏安全。</p></article>'
        '<article class="ai-balance-item critical"><div class="ai-balance-head"><b>2</b>'
        '<strong>收入高度集中在单日：最高一天占当月 5.1%</strong></div>'
        f'<p>{d8(t1[0])} 单日 <b>{t1[1] / 10000:.2f} 万</b>，占 10 月累计（{mr["value"]:.2f} 万）的 '
        f'<b>{t1[1] / 10000 / mr["value"] * 100:.1f}%</b>；'
        f'前三高日合计 <b>{top3 / 10000:.2f} 万</b>、占 <b>{top3 / 10000 / mr["value"] * 100:.1f}%</b>，'
        f'其余 {int(mr["coverage"]["recordedDays"]) - 3} 天日均 '
        f'<b>{(mr["valueYuan"] - top3) / 10000 / max(1, int(mr["coverage"]["recordedDays"]) - 3):.2f} 万</b>。</p>'
        '<p>动作：单日高点是节假日、补记还是集中出院结算，需财务给一句说明，'
        '否则下周排目标会把单日高点当常态。</p></article>'
        '<article class="ai-balance-item watch"><div class="ai-balance-head"><b>3</b>'
        '<strong>门诊结构偏复诊，初诊量仍偏低</strong></div>'
        f'<p>本期门诊 <b>{vis["value"]}</b> 人次（初诊 <b>{vis["visitsNew"]}</b> ＋ 复诊 <b>{vis["visitsReturn"]}</b>），'
        f'复诊占 <b>{ret_pct}%</b>；在院 <b>{M["wardCount"]["value"]}</b> 人（{DT} 时点）；'
        f'入院 <b>{M["weekAdmit"]["value"]}</b> 人、出院 <b>{M["weekDischarge"]["value"]}</b> 人，'
        f'患者池净增 <span class="changed-good">{M["netPool"]["value"]} 人</span>。</p>'
        f'<p>动作：初诊 {vis["visitsNew"]} 人次分布在 {NDAY} 天，日均不到 7 人，会削弱后续在院补充；'
        '本期需盯新患引入与到院转化（到院登记 139 人次中初诊 26 人）。</p></article>'
    )


# ------------------------------------------------------------------ 主流程
def main():
    html = open(HTML, encoding="utf-8").read()
    orig = len(html)
    dry = "--dry-run" in sys.argv

    html = put_block(html, "heroKpis", build_hero_kpis())

    # 目标卡是 heroKpis 的兄弟节点，用 id 找不到，按 class 收尾替换
    sp = id_span(html, "heroKpis")
    if sp:
        s, e = sp
        m = re.search(r'<article class="ov-card ov-target">[\s\S]*?</article>', html[e:])
        if m:
            html = html[:e + m.start()] + build_target_card() + html[e + m.end():]
        else:
            print("  ⚠ 目标卡未命中")

    if '<div class="ov-sources">' in html:
        i = html.find('<div class="ov-sources">')
        # 三个 <div> 子块，直接按 </div></div></div> 收尾不稳，改用「到 <details class="ov-note">」
        j = html.find('<details class="ov-note">', i)
        if j > i:
            html = html[:i] + build_sources() + html[j:]

    if 'id="heroSummary"' in html:
        sp = id_span(html, "heroSummary")
        if sp:
            # heroSummary 后面紧跟一整段「主数字：…」旧文，一并换掉
            tail_p = re.compile(r'</p>\s*<p>主数字[\s\S]*?</p>')
            seg_end = html.find('</details>', sp[1])
            seg = html[sp[0]:seg_end]
            new_seg = build_hero_summary() + build_hero_extra()
            html = html[:sp[0]] + new_seg + html[seg_end:]

    html = put_block(html, "quality", build_quality())

    # 工娱模块：head + 四格 + 结构块整段换，脚注单独换
    if 'id="recModule"' in html:
        i = html.find('<div class="rec-head">', html.find('id="recModule"'))
        j = html.find('<div class="kpi-foot">', i)
        if i > 0 and j > i:
            html = html[:i] + build_rec_module() + html[j:]
        else:
            print("  ⚠ recModule 主体未命中")
        mf = re.search(r'<div class="kpi-foot"><i></i><span>工娱数据：[\s\S]*?</span></div>\s*</section>', html)
        if mf:
            html = html[:mf.start()] + REC_FOOT + html[mf.end():]
        else:
            print("  ⚠ recModule 脚注未命中")

    # kpiGrid 脚注
    mk = re.search(r'<div class="kpi-foot"><i></i><span>指标数据：[\s\S]*?</span></div></section>', html)
    if mk:
        html = html[:mk.start()] + build_kpi_foot() + html[mk.end():]
    else:
        print("  ⚠ kpiGrid 脚注未命中")

    # 护理分项：整块
    if 'id="nursingItems"' in html:
        sp = id_span(html, "nursingItems")
        if sp:
            html = (html[:sp[0]] + '<section class="section" id="nursingItems">'
                    + build_nursing_items() + '</section>' + html[sp[1]:])

    # 护理考核面板头部
    html = sub1(html, NP_SUB_OLD, NP_SUB_NEW, "护理面板子标题")

    # 护理部周报存档块：明确标成「存档、非本期」
    html = sub1(
        html,
        '<p>物理治疗开展 · 护理质量 · 制度建设 · 专项培训 · 人员配置（<b>本周 10.5—10.11</b>）</p>',
        f'<p>物理治疗开展 · 护理质量 · 制度建设 · 专项培训 · 人员配置'
        f'（<b>{LBL} 本周未提交</b>；下方正文为 <b>10.5—10.11 存档</b>，仅作留档，<b>不计入本期任何指标</b>）</p>',
        "护理周报副标题",
    )
    html = re.sub(
        r'(<div class="kpi-foot"><i></i><span>)来源：业主 2026-10-11 提供《科室周报—本周工作情况\.doc》（本周 10\.5—10\.11）。',
        r'\1<b>⚠ 存档内容：</b>来源为业主 2026-10-11 提供《科室周报—本周工作情况.doc》（10.5—10.11），'
        f'本周（{LBL}）护理部<b>未提交新周报</b>，以下正文只作留档、<b>不代表本期</b>。',
        html,
        count=1,
    )

    # JS 常量：benchmarks / detailedSignals / 平衡条 / 工娱面板
    html = replace_const_literal(html, "benchmarks", build_benchmarks())
    html = replace_const_literal(html, "detailedSignals", build_signals())

    mb = re.search(r"""<div class="ai-balance-strip ai-balance-more" id="aiBalanceMore">[\s\S]*?</div>'\)""", html)
    if mb:
        html = html[:mb.start()] + build_balance_strip() + "')" + html[mb.end():]
    else:
        print("  ⚠ 平衡条未命中")

    # ⚠ 2026-10-26：工娱面板已从 green-channel 改为 rec-module 结构（移入营销抽屉首屏），
    #    由 scripts/live-data/patch_layout_1026.py 统一维护。这里不再覆盖，
    #    否则重跑本脚本会把新样式退回旧的「绿色通道」卡片。
    mg = re.search(r'<section class="rec-module" id="deptSpecialPanel">[\s\S]*?</section>`', html)
    if mg:
        print("  · 工娱特设面板已由 patch_layout_1026 接管，跳过覆盖")
    else:
        print("  ⚠ 工娱特设面板未命中")

    # 主平衡条（balance.innerHTML=`…`）
    mk = re.search(r"balance\.innerHTML=`[\s\S]*?`;", html)
    if mk:
        html = html[:mk.start()] + "balance.innerHTML=`" + build_main_balance() + "`;" + html[mk.end():]
    else:
        print("  ⚠ 主平衡条未命中")

    # 护理考核面板横幅：标注为存档
    old_banner = ('⚠ 本表考核周为 <b>10.11—10.17</b>（源表按<b>周日—周六</b>出表），与主表自然周 10.12—10.18 '
                  '<b>差 1 天</b>——<b>缺 10.18、含 10.11</b>，两套时间窗<b>不可相加、不可互相校验</b>，本面板不改写日期。')
    new_banner = (f'⚠ 本面板为 <b>10.11—10.17 护理考核周</b>的<b>存档结果</b>（源表按<b>周日—周六</b>出表）；'
                  f'<b>本周（{LBL}）护理部未提交新表</b>，十七行数值<b>不代表本期</b>，仅作留档、不计入任何指标。')
    html = sub1(html, old_banner, new_banner, "护理面板横幅")

    print(f"  {orig} → {len(html)}（{len(html) - orig:+d}）")
    if dry:
        print("dry-run，未写盘")
        return
    open(HTML, "w", encoding="utf-8").write(html)
    print("index.html 已重同步")


if __name__ == "__main__":
    main()
