#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-11-09：护理组 11.02—11.08 周工作量统计表入库，全站换数。

源表：护士周工作量统计表含排名11.2-11.8.xlsx（3 sheet）
  1) 护士周工作量统计表   17 人 × 7 天（完成率 / 综合得分）+ 周汇总
  2) 物理治疗完成数据记录 7 天 × 6 项 = 42 行
  3) 物理治疗项目汇总     6 项 + 合计行

口径纪律：
  · 源表未改，只读；「护士周工作量统计表」R5 有一处公式错误（误引 J5），
    页面保留源表显示值，同时在排名与「口径与数据质量」中给出重算值并标注。
  · 空白记 null / 「—」，不按 0；不拿上期值顶替。
  · 汇报表 484 人（人数）与周报 691/652（人次）不同源、不相加、不互相校验。
"""
import json
import os
import re

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
XLSX = "/tmp/nurse_1102_1108.xlsx"
HTML = os.path.join(ROOT, "index.html")
SNAP = os.path.join(ROOT, "data", "snapshot.json")

DAYS = ["11.02", "11.03", "11.04", "11.05", "11.06", "11.07", "11.08"]
ROWS = list(range(5, 22))          # 17 名护士
COLS = [("B", "C"), ("D", "E"), ("F", "G"), ("H", "I"),
        ("J", "K"), ("L", "M"), ("N", "O")]

wb = openpyxl.load_workbook(XLSX, data_only=True)
ws1, ws2, ws3 = wb["护士周工作量统计表"], wb["物理治疗完成数据记录"], wb["物理治疗项目汇总"]


def n(v, nd=1):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), nd)
    s = str(v).strip()
    if not s or s in ("—", "-"):
        return None
    try:
        return round(float(s), nd)
    except ValueError:
        return None


# ---------- 表1 逐人 ----------
people = []
for r in ROWS:
    name = str(ws1["A%d" % r].value).replace(" ", "").strip()
    days = []
    for c1, c2 in COLS:
        days.append((n(ws1["%s%d" % (c1, r)].value), n(ws1["%s%d" % (c2, r)].value)))
    rate = n(ws1["P%d" % r].value, 3)
    rank = ws1["Q%d" % r].value
    score = n(ws1["R%d" % r].value)
    srank = ws1["S%d" % r].value
    pct = n(ws1["T%d" % r].value)
    score_fix = round(sum(d[1] for d in days if d[1] is not None), 1)
    people.append(dict(name=name, days=days, rate=rate,
                       rank=int(rank) if rank else None, score=score,
                       srank=int(srank) if srank else None, pct=pct,
                       score_fix=score_fix,
                       filled=sum(1 for d in days if d[0] is not None),
                       scoreDays=sum(1 for d in days if d[1] is not None)))

# 修正排名（按同列公式重算）
fix_sorted = sorted([p for p in people if p["score_fix"] > 0],
                    key=lambda x: -x["score_fix"])
for i, p in enumerate(fix_sorted, 1):
    p["srank_fix"] = i
for p in people:
    p.setdefault("srank_fix", None)

filled_rate = sum(p["filled"] for p in people)
filled_score = sum(p["scoreDays"] for p in people)
cells = len(people) * 7

# ---------- 表2/表3 ----------
proj = []
for r in range(3, 9):
    proj.append(dict(label=str(ws3["A%d" % r].value).strip(),
                     due=int(ws3["B%d" % r].value),
                     done=int(ws3["C%d" % r].value),
                     miss=int(ws3["D%d" % r].value),
                     rate=float(ws3["E%d" % r].value)))
TOT_DUE = int(ws3["B9"].value)
TOT_DONE = int(ws3["C9"].value)
TOT_MISS = int(ws3["D9"].value)
TOT_RATE = float(ws3["E9"].value)

daily = []
for i, d in enumerate(DAYS):
    r0 = 3 + i * 6
    seg = list(range(r0, r0 + 6))
    due = sum(int(ws2["C%d" % r].value) for r in seg)
    done = sum(int(ws2["D%d" % r].value) for r in seg)
    miss = due - done
    daily.append((d, due, done, miss, round(done / due * 100, 1)))

assert TOT_DUE == 691 and TOT_DONE == 652 and TOT_MISS == 39, (TOT_DUE, TOT_DONE, TOT_MISS)
assert sum(x[1] for x in daily) == TOT_DUE and sum(x[2] for x in daily) == TOT_DONE

PROJ_NAME = {"交流电": "经颅交流电", "经颅磁": "经颅磁治疗", "脑功能": "脑功能治疗",
             "放松": "音乐放松治疗", "失眠": "失眠治疗仪治疗", "团体": "团体生物反馈"}

s = open(HTML, encoding="utf-8").read()
cnt = [0]


def rep(old, new, label=""):
    c = s.count(old)
    assert c == 1, "命中 %d 次（应为 1）：%s" % (c, label)
    globals()["s"] = s.replace(old, new)
    cnt[0] += 1


def between(start, end, new, label=""):
    """把 start 起、end 前的整段替换（end 本身保留）。"""
    global s
    i = s.find(start)
    assert i >= 0, "找不到起点：%s" % label
    j = s.find(end, i)
    assert j > i, "找不到终点：%s" % label
    s = s[:i] + new + s[j:]
    cnt[0] += 1


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# =====================================================================
# 1. 护理抽屉 · departments.nursing
# =====================================================================
nur_dept = (
    "nursing:{name:'护理组',icon:'护',status:'已交 · 7 天',statusClass:'',summary:'六项完成率',delta:'+4.3pt',"
    "metrics:["
    "['[[AUTO-DEPT]] 本期（11.02—11.08 · 护理周报已交，7 天 / 17 人）',90.1,94.4,'%',"
    "'《护士周工作量统计表含排名》本周<b>已交</b>：三张 sheet、7 天齐全。六项应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b>，完成率 <b>94.4%</b>；上期 10.26—11.01 为 699 / 630 / 69 / <b>90.1%</b>，<b>+4.3pt</b>。"
    "应做量 −8、实做 +22、未做 −30——<b>分母略降、分子增 22</b>，回升不是单靠分母变少。<br>⚠ 源表 R5（李永鑫）公式误引 J5，显示 100.1 / 第 1；详见「护理考核标准」待修项。',"
    "'上期 10.26—11.01','本期 11.02—11.08'],"
    "['实做 / 应做',630,652,'人次',"
    "'本期 <b>652 / 691</b>（未做 39）；上期 <b>630 / 699</b>（未做 69）。口径＝6 项物理治疗逐日应做与实做的人次合计，与汇报表「物理治疗 <b>484 人</b>」<b>不同源、不可相加</b>。',"
    "'上期 10.26—11.01','本期 11.02—11.08'],"
    "['六项未做',69,39,'人次',"
    "'本期未做 <b>39</b>，比上期 69 <b>少 30</b>。绝对量前三：交流电 12、经颅磁 9、团体 8；团体未做率仍最高（8/63＝12.7%）。',"
    "'上期 10.26—11.01','本期 11.02—11.08'],"
    "['完成率首名',94.8,100,'%',"
    "'本期 <b>彭龙华、赵雯倩并列 100.0%</b>（源表并列第 1，下一名第 3）；上期首名沈琳 94.8%（仅填 2 天）。⚠ 周总完成率＝已填日均值，<b>填 1 天 100% 与填 3 天 100% 同分</b>，名次对填报天数敏感。',"
    "'上期 10.26—11.01','本期 11.02—11.08'],"
    "['工作量首名',30.2,62.1,'分',"
    "'按同列公式重算，本期首名<b>沈琳 62.1</b>（6 天 / 完成率 87.2%），上期杨新金 30.2。⚠ 源表 S 列显示<b>李永鑫 100.1 第 1</b>，系 R5 公式把 11.6 完成率 86.7 当得分计入；重算应为 <b>18.3 / 第 13</b>，源文件未改。',"
    "'上期 10.26—11.01','本期 11.02—11.08'],"
    "['物理治疗人数（汇报表）',null,484,'人',"
    "'汇报表护理组表头 <b>484 人</b>（工娱 <b>5 场 62 人</b>）。这是<b>人数</b>口径，与周报 691 / 652 <b>人次</b>不同源，<b>不可直接比、不互相校验</b>。',"
    "'—','本期 11.02—11.08']],"
    "advice:["
    "['完成率回到 94.4%，但先看「应做少了 8」这层','本期 691 / 652 / 39 / <b>94.4%</b>，上期 699 / 630 / 69 / 90.1%。完成率 +4.3pt 由两部分组成：应做量 <b>−8</b>（699→691）、实做 <b>+22</b>（630→652）。分子涨得比分母降得多，是真实改善；但应做量本身在缩，需确认是住院量下降还是排班减少，<b>不能只看率</b>。'],"
    "['短板从「两项崩」收敛到「团体一项」','上期团体 71.1%、失眠 72.2% 两项低于 75%；本期<b>失眠回到 90.9%</b>（+18.7pt），只剩<b>团体 87.3%</b>（55/63）低于 90%。团体 7 天里有 6 天未做 1—4 人次，11.02 单日 63.6%（7/11）是全周最低格。建议按「当天团体带组人」逐日复盘，而不是笼统归因。'],"
    "['两套排名有 3 处口径要先修，再谈考核','① <b>李永鑫 R5 公式</b>误引 11.6 完成率，把 100.1 顶到工作量第 1，重算应为 18.3 / 第 13；② 周总完成率＝已填日<b>简单平均</b>，彭龙华只填 1 天 100% 就并列第 1；③ 百分制基准 30 失效，<b>7 人超 100</b>（最高 333.7）。这三项不修，名次不能进本月考核。']]}"
)
between("nursing:{name:'护理组'", ",psychology:{name:'心理咨询组'", nur_dept, "departments.nursing")

# =====================================================================
# 2. 抽屉排名页 · analytics.nursing
# =====================================================================
rate_ranked = [p for p in people if p["rate"] is not None]
rate_ranked.sort(key=lambda x: (-x["rate"], x["name"]))
work_ranked = [p for p in people if p["score_fix"] > 0]
work_ranked.sort(key=lambda x: (-x["score_fix"], x["name"]))
rmax = max(p["rate"] for p in rate_ranked)
wmax = max(p["score_fix"] for p in work_ranked)

rate_rows = []
prev = None
for p in rate_ranked:
    r = p["rate"] * 100
    tag = "（并列）" if prev is not None and abs(r - prev) < 0.05 else ""
    rate_rows.append("{name:'%s',score:'%.1f%%',metric:'填 %d 天 · 得分 %.1f'}"
                     % (p["name"], r, p["filled"], p["score_fix"]))
    prev = r
work_rows = []
for p in work_ranked:
    work_rows.append("{name:'%s',score:'%.1f',metric:'百分制 %.1f · 完成率 %.1f%%'}"
                     % (p["name"], p["score_fix"], p["score_fix"] / 30 * 100,
                        (p["rate"] or 0) * 100))

proj_rows = ",".join("['%s','%d','%d','%d','%.1f%%']"
                     % (PROJ_NAME[x["label"]], x["due"], x["done"], x["miss"], x["rate"])
                     for x in proj)

nur_analytics = (
    "nursing:{periods:['10.12周','10.19周','10.26周','11.02周'],"
    "history:[['六项完成率',[null,92.8,90.1,94.4],'%'],"
    "['完成率填报率',[null,null,35.7,42.0],'%'],"
    "['综合得分填报率',[null,null,52.7,53.8],'%']],"
    "rankBanner:'<b>本期 11.02—11.08 · 《护士周工作量统计表含排名》已交（7 天 / 17 人）</b>：六项应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b> / <b>94.4%</b>，上期 90.1%，<b>+4.3pt</b>。应做 −8、实做 +22、未做 −30。"
    "两套榜：完成率 <b>15 人</b>（彭龙华、赵雯倩并列 100.0%）、工作量 <b>16 人</b>（沈琳 62.1 第 1）。<br>"
    "⚠ <b>源表 R5（李永鑫）公式误引 J5</b>，把 11.6 的完成率 86.7 当得分，显示 100.1 / 第 1 / 百分制 333.7；按同列其余 16 行公式重算为 <b>18.3 / 第 13 / 61.0</b>。"
    "<b>本页排名按重算值，源文件未改</b>，已列「口径与数据质量」待修。',"
    "rankGroups:["
    "{title:'① 周总完成率 · 效率口径（本期 11.02—11.08 · __RATE_N__ 人）',scoreLabel:'周完成率',medals:true,"
    "note:'周总完成率＝已填日期完成率的算术平均，未填日期忽略。<b>陈福建 7 天无完成率、任健康整周 0 行，不进榜、不按 0 计</b>。⚠ 该口径对天数敏感：彭龙华只填 1 天 100% 即与填 3 天 100% 的赵雯倩并列第 1。',rows:[__RATE_ROWS__]},"
    "{title:'② 周总工作量得分 · 累计口径（本期 11.02—11.08 · __WORK_N__ 人）',scoreLabel:'周得分',medals:true,"
    "note:'周总工作量得分＝7 天综合得分之和，满分基准 30。⚠ <b>李永鑫按同列公式重算为 18.3（第 13）</b>；源表显示 100.1（第 1）系 R5 误引 11.6 完成率，源文件未改。任健康整周 0 行，不进榜。',rows:[__WORK_ROWS__]},"
    "{title:'未进榜与口径说明（不排名 · 仅核查）',rankless:true,noRankText:'不排名',noRankSub:'仅核查',"
    "note:'完成率缺失按 null 处理，绝不按 0 计入。',rows:["
    "{name:'任健康',metric:'整周 7 天 0 行，完成率与得分均为空，两套榜都不参与'},"
    "{name:'陈福建',metric:'6 天有综合得分（23.8，第 9），但 0 天完成率 → 只进工作量榜'},"
    "{name:'李永鑫',metric:'源表 100.1 / 第 1 为公式错误，重算 18.3 / 第 13；完成率 83.5% 第 10'}]},"
    "{title:'物理治疗 6 项（本期 11.02—11.08 · 7 天）',note:'应做 691 / 实做 652 / 未做 39，整体 94.4%。团体 87.3% 仍是六项最低，失眠已从 72.2% 修复到 90.9%。',"
    "table:{cols:['治疗项目','应做','实做','未做','完成率'],rows:[__PROJ_ROWS__],"
    "sum:['6 项合计','__DUE__','__DONE__','__MISS__','__RATE__'],foot:'完成率＝实做÷应做；合计与源表《物理治疗项目汇总》第 9 行逐项一致。'}}],"
    "diagnosis:["
    "['核对 · 完成率回升是两个方向合成的','应做 <b>699→691（−8）</b>、实做 <b>630→652（+22）</b>、未做 <b>69→39（−30）</b>，率由 90.1% 升到 <b>94.4%</b>。分子增 22 是主因，但应做量本身在缩——要分清是住院量下降还是排班减少，<b>不能只用完成率代表治疗兑现</b>。'],"
    "['短板收敛：只剩团体低于 90%','失眠治疗仪 <b>72.2%→90.9%</b>（+18.7pt）已修复；团体 <b>87.3%</b>（55/63）仍是六项最低，7 天里 6 天有未做，11.02 单日 63.6%（7/11）为全周最低格。建议按带组人逐日复盘。'],"
    "['三处口径不修，名次不能进考核','① R5 公式把完成率当得分；② 周总完成率是已填日<b>简单平均</b>，1 天 100% 可并列第 1；③ 百分制基准 30 使 <b>7 人超 100</b>（最高 333.7）。建议：修 R5 公式、完成率改按人天加权或设最低填报天数、基准调到 ≥65。']]}")


nur_analytics = (nur_analytics.replace("__RATE_N__", str(len(rate_ranked))).replace("__RATE_ROWS__", ",".join(rate_rows)).replace("__WORK_N__", str(len(work_ranked))).replace("__WORK_ROWS__", ",".join(work_rows)).replace("__PROJ_ROWS__", proj_rows).replace("__DUE__", str(TOT_DUE)).replace("__DONE__", str(TOT_DONE)).replace("__MISS__", str(TOT_MISS)).replace("__RATE__", "%.1f%%" % TOT_RATE))

between("nursing:{periods:['10.12周'", ",psychology:{periods:['10.12周'", nur_analytics, "analytics.nursing")

# =====================================================================
# 3. 首页护理排名块
# =====================================================================
rep('<p>两套口径分开排、不合成总分（<b>11.02—11.08 周报未交 · 下列为 10.26—11.01 存档</b>）</p></div><span class="ni-sum" style="color:#168C83">存档 · 完成率榜 14 人 · 工作量榜 16 人</span>',
    '<p>两套口径分开排、不合成总分（<b>11.02—11.08 已交 · 7 天 / 17 人</b>）</p></div><span class="ni-sum" style="color:#168C83">完成率榜 15 人 · 工作量榜 16 人</span>',
    "nursingRank head")

rep('李永鑫、陈福建 7 天无完成率 → 不进效率榜、不按 0 计；赵林烦整行空 → 不参与计算。',
    '陈福建 7 天无完成率 → 不进效率榜、不按 0 计；任健康整周 0 行 → 两榜都不参与。⚠ 源表李永鑫工作量 100.1 系 R5 公式误引完成率，按同列公式重算为 18.3（第 13），排名按重算值。',
    "nursingRank foot")

# =====================================================================
# 4. 首页物理治疗分项
# =====================================================================
items = "".join(
    '<article class="ni-card%s"><div class="ni-top"><span>%s</span><b>%.1f<em>%%</em></b></div>'
    '<div class="ni-bar"><i style="width:%.1f%%"></i></div>'
    '<div class="ni-num">应做 %d · 实做 %d · 未做 %d</div></article>'
    % ("" if x["rate"] >= 90 else " warn", PROJ_NAME[x["label"]],
       x["rate"], x["rate"], x["due"], x["done"], x["miss"])
    for x in proj)
items += ('<article class="ni-card na"><div class="ni-top"><span>电休克治疗（ECT）</span>'
          '<b>—<em>人次</em></b></div><div class="ni-bar"><i></i></div>'
          '<div class="ni-num">本次 Excel 未含 · 记 null，不拿上期 11 人次顶替</div></article>')

nursing_items = (
    '<section class="section" id="nursingItems"><div class="section-head"><div><h2>护理组 · 物理治疗分项</h2>'
    '<p>6 个项目应做 / 实做 / 未做 ＋ 电休克（<b>11.02—11.08 已交 · 7 天 / 17 人</b>）</p></div>'
    '<span class="ni-sum" style="color:#168C83">本期 · 六项合计 <b>94.4%</b> · 691 → 652</span></div>'
    '<div class="ni-grid">__ITEMS__</div>'
    '<div class="kpi-foot"><i></i><span><b>本期数据来自《护士周工作量统计表含排名》三张 sheet，7 天齐全。</b>'
    '应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b>，整体 <b>94.4%</b>；上期 10.26—11.01 为 699 / 630 / 69 / <b>90.1%</b>，'
    '<b>+4.3pt</b>——应做 <b>−8</b>、实做 <b>+22</b>、未做 <b>−30</b>，回升主要靠实做增长。'
    '<b>团体 87.3%（55/63）</b>是唯一低于 90% 的项目，但已从上期 71.1% 修复 16.2pt；<b>失眠 90.9%</b>（40/44）从 72.2% 回升 18.7pt。'
    '未做绝对量前三：交流电 <b>12</b>、经颅磁 <b>9</b>、团体 <b>8</b>。逐日看，<b>11.05 六项全 100%</b>，11.03 90.7% 最低（经颅磁 80.8% 拖累），11.02 团体 63.6%（7/11）为全周单格最低。'
    '<br><b>电休克不在本次 Excel 内</b>，记 null、不按 0 计入、不拿上期 11 人次顶替；工娱场次与参与人数同样未含，见营销中心抽屉。'
    '</span></div></section>'
) 

nursing_items = nursing_items.replace("__ITEMS__", items)

between('<section class="section" id="nursingItems">',
        '\n      <section class="section" id="nursingWork">',
        nursing_items, "nursingItems")

# =====================================================================
# 5. 首页本周工作情况（只换 ①，②—⑤ 仍是 10.5—10.11 存档）
# =====================================================================
rep('（<b>11.02—11.08 周报未交</b>，见「护理考核标准」；① 为汇报表本周实填：物理治疗 <b>484 人</b>、工娱 <b>5 场 62 人</b>，六项完成率 null；② — ⑤ 为科室周报 <b>10.5—10.11 存档</b>，<b>仅作留档、不计入本期</b>）',
    '（<b>11.02—11.08 周报已交</b>，六项 <b>94.4%</b>，详见「护理考核标准」；① 为周报本期实填＋汇报表人数，② — ⑤ 为科室周报 <b>10.5—10.11 存档</b>，<b>仅作留档、不计入本期</b>）',
    "nursingWork head")

old_card1 = ('本周（11.02—11.08）护理周报未交：六项应做 / 实做 / 未做与完成率<b>全部记 null</b>，'
             '<b>不拿上期 90.1%（630/699）顶替</b>。汇报表护理组本周只填两项：物理治疗 <b>484 人</b>、'
             '工娱 <b>5 场 62 人</b>（合计口径，未拆患者 / 家属，与营销中心工娱不同源，<b>不并数</b>）。'
             '<br><b>存档参考（10.26—11.01，7 天 / 17 行）</b>：应做 <b>699</b> / 实做 <b>630</b> / 未做 <b>69</b>，'
             '完成率 <b>90.1%</b>；失眠治疗仪 72.2%（26/36）、团体生物反馈 71.1%（32/45）是唯二低于 75% 的项目，'
             '未做量最大的是经颅磁 17 人次。<br>⚠ <b>484 人与 699 人次口径不同、不可直接比</b>：'
             '484 是汇报表当天填的人数，未见应做基数；699 是护理周报的人次应做量。要判完成率，必须等周报补交。')
new_card1 = ('本周（11.02—11.08）周报<b>已交</b>：六项应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b>，完成率 <b>94.4%</b>'
             '（上期 699 / 630 / 69 / 90.1%，<b>+4.3pt</b>）。<b>团体 87.3%</b>（55/63）是唯一低于 90% 的项目，'
             '失眠 90.9%（40/44）已从 72.2% 修复；未做量前三：交流电 12、经颅磁 9、团体 8。'
             '逐日 11.05 六项全 100%，11.03 90.7% 最低。<br>汇报表护理组另填：物理治疗 <b>484 人</b>、'
             '工娱 <b>5 场 62 人</b>（工娱归营销中心口径，<b>不并数</b>）。<br>⚠ <b>484 人与 691/652 人次不同源、不可直接比</b>：'
             '484 是汇报表的人数，周报是治疗人次；两者只并列，不互相校验。<br>⚠ 源表 R5（李永鑫）公式误引 11.6 完成率，'
             '工作量显示 100.1 / 第 1，重算应为 18.3 / 第 13——<b>源文件未改</b>，已在排名页标注。')
rep(old_card1, new_card1, "nursingWork card1")

# =====================================================================
# 6. OPS 快照块（页面运行时被 live-sync 读取的静态兜底）
# =====================================================================
list_rows = ",".join("['%s','%d','%d','%d','%.1f%%']"
                     % (PROJ_NAME[x["label"]], x["due"], x["done"], x["miss"], x["rate"])
                     for x in proj)
ops = (
    "nursing:{'range': '本期 11.02—11.08 · 周报已交（7 天 / 17 人）', "
    "'metrics': [['六项完成率', '94.4%'], ['实做 / 应做', '652 / 691'], ['未做', '39 人次'], "
    "['物理治疗人数', '484 人'], ['工娱', '5 场 / 62 人'], ['周报数据截至', '2026-11-08']], "
    "'list': {'title': '物理治疗 6 项 · 本期 11.02—11.08（7 天）', "
    "'sub': '应做 691 / 实做 652 / 未做 39；完成率＝实做÷应做，与源表汇总第 9 行一致', "
    "'cols': ['治疗项目','应做','实做','未做','完成率'], 'gt': '1.7fr 1fr 1fr 1fr 1fr', "
    "'num': [1,2,3,4], 'warn': [0,0,0,0], 'rows': [__ROWS__], "
    "'sum': ['6 项合计','691','652','39','94.4%'], "
    "'note': '本期 7 天应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b>，整体 <b>94.4%</b>（上期 90.1%，+4.3pt）。"
    "团体 87.3% 最低，失眠 90.9% 已从 72.2% 修复；未做最多的是交流电 12。'}, "
    "'note': '<b>本周（11.02—11.08）护理周报已交。</b>《护士周工作量统计表含排名》三张 sheet、7 天 / 17 人全部入库："
    "六项完成率 <b>94.4%</b>（652/691）、未做 <b>39</b>，上期 90.1%，<b>+4.3pt</b>。"
    "汇报表护理组另填物理治疗 <b>484 人</b>、工娱 <b>5 场 62 人</b>，<b>人数与人次不同源、不可相加</b>。<br>"
    "⚠ 源表 R5（李永鑫）公式误引 11.6 完成率，工作量显示 100.1 / 第 1 / 百分制 333.7；"
    "按同列公式重算为 <b>18.3 / 第 13 / 61.0</b>，页面排名按重算值、源文件未改。"
    "另：完成率榜为已填日简单平均，1 天 100% 可并列第 1。', "
    "'diag': \"<div class='diagnosis-item tone-people'><b>完成率 94.4%，回升靠实做 +22</b>"
    "<p>应做 699→<b>691</b>（−8）、实做 630→<b>652</b>（+22）、未做 69→<b>39</b>（−30）。"
    "分子涨得比分母降得多，是真实改善；但应做量在缩，需确认是住院量还是排班变化。</p></div>"
    "<div class='diagnosis-item tone-risk'><b>三处口径不修，名次不能进考核</b>"
    "<p>李永鑫 R5 公式误把完成率当得分（100.1→应为 18.3）；周总完成率简单平均，填 1 天 100% 即并列第 1；"
    "百分制基准 30 导致 7 人超 100（最高 333.7）。</p></div>\"},"
)
ops = ops.replace("__ROWS__", list_rows)

between("nursing:{'range': '本期 11.02—11.08 · 周报未交",
        "\n      psychology:{'range': '本期 11.02—11.08",
        ops, "OPS nursing")

# =====================================================================
# 7. DEPT_CARD.nursing（首页旧卡兜底）
# =====================================================================
old_card = ('nursing:{m1:{label:"六项完成率",value:"—",unit:"%"},m2:{label:"物理治疗人数",value:"484",unit:"人"},\n'
            '        note:"<b>本周（11.02—11.08）护理周报未交</b>：源表《护士周工作量统计表含排名》最新只到 <b>2026-10-17</b>，'
            '六项完成率、实做/应做、两套排名<b>全部 null</b>，<b>不拿上期 90.1% 顶替</b>。汇报表只填了两项：'
            '物理治疗 <b>484 人</b>、工娱 <b>5 场 62 人</b>，没有质量数据。上期 10.26—11.01 为 699 / 630 / 69 / 90.1%，'
            '仅作历史参照。⚠ 已连续三周未滚动。"},')
new_card = ('nursing:{m1:{label:"六项完成率",value:"94.4",unit:"%"},m2:{label:"实做人次",value:"652",unit:"人次"},\n'
            '        note:"<b>本周（11.02—11.08）护理周报已交</b>：《护士周工作量统计表含排名》三张 sheet、7 天 / 17 人。'
            '六项应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b> / <b>94.4%</b>；上期 699 / 630 / 69 / 90.1%，'
            '<b>+4.3pt</b>。团体 87.3% 最低，失眠 90.9% 已修复。汇报表另填物理治疗 <b>484 人</b>、工娱 <b>5 场 62 人</b>，'
            '<b>人数与人次不同源、不可相加</b>。⚠ 源表 R5 公式误引完成率，李永鑫工作量重算为 18.3 / 第 13。"},')
rep(old_card, new_card, "DEPT_CARD.nursing")

# =====================================================================
# 8. NP 面板整块重写
# =====================================================================
def bar(w):
    return "%.1f" % w


kpi_rows = ""
proj_rows_html = ""
for i, x in enumerate(sorted(proj, key=lambda y: -y["rate"]), 1):
    proj_rows_html += (
        '<div class="npa-rk-row%s"><span class="no">%d</span><span class="nm">%s</span>'
        '<span class="bar"><i style="width:%.1f%%"></i></span><span class="sv">%.1f%%</span>'
        '<span class="qt">%d/%d · 未做 <b>%d</b></span></div>'
        % (" m1" if i == 1 else "", i, PROJ_NAME[x["label"]], x["rate"], x["rate"],
           x["done"], x["due"], x["miss"]))

daily_html = ""
for d, due, done, miss, rate in daily:
    daily_html += ('<tr><td class="npst-name">%s</td><td class="npst-num">%d</td>'
                   '<td class="npst-num">%d</td><td class="npst-num">%d</td>'
                   '<td class="npst-num npst-total">%.1f%%</td></tr>' % (d, due, done, miss, rate))
daily_html += ('<tr class="npst-sum"><td class="npst-name">7 天合计</td><td class="npst-num">%d</td>'
               '<td class="npst-num">%d</td><td class="npst-num">%d</td>'
               '<td class="npst-num">%.1f%%</td></tr>' % (TOT_DUE, TOT_DONE, TOT_MISS, TOT_RATE))

detail_html = ""
for p in people:
    cells_html = ""
    for rate, score in p["days"]:
        if rate is None and score is None:
            cells_html += '<td class="npst-num npst-null">—</td>'
        elif rate is None:
            cells_html += '<td class="npst-num npst-null">— / %.1f</td>' % score
        elif score is None:
            cells_html += '<td class="npst-num">%.1f%% / —</td>' % rate
        else:
            cells_html += '<td class="npst-num">%.1f%% / %.1f</td>' % (rate, score)
    detail_html += (
        '<tr><td class="npst-name">%s</td>%s<td class="npst-num npst-total">%s</td>'
        '<td class="npst-num">%s</td><td class="npst-num">%s</td><td class="npst-num">%s</td>'
        '<td class="npst-num">%s</td></tr>'
        % (p["name"], cells_html,
           ("%.1f%%" % (p["rate"] * 100)) if p["rate"] is not None else "—",
           p["rank"] if p["rank"] else "—",
           "%.1f" % p["score"] if p["score"] is not None else "—",
           p["srank"] if p["srank"] else "—",
           "%.1f" % p["pct"] if p["pct"] is not None else "—"))

rate_rank_html = ""
for i, p in enumerate(rate_ranked, 1):
    cls = " m%d" % i if i <= 3 else ""
    rate_rank_html += (
        '<div class="npa-rk-row%s"><span class="no">%d</span><span class="nm">%s</span>'
        '<span class="bar"><i style="width:%.1f%%"></i></span><span class="sv">%.1f%%</span>'
        '<span class="qt">填 %d 天</span></div>'
        % (cls, i, p["name"], p["rate"] * 100 / rmax * 100, p["rate"] * 100, p["filled"]))

work_rank_html = ""
for i, p in enumerate(work_ranked, 1):
    cls = " m%d" % i if i <= 3 else ""
    work_rank_html += (
        '<div class="npa-rk-row%s"><span class="no">%d</span><span class="nm">%s</span>'
        '<span class="bar"><i style="width:%.1f%%"></i></span><span class="sv">%.1f</span>'
        '<span class="qt">百分制 %.1f</span></div>'
        % (cls, i, p["name"], p["score_fix"] / wmax * 100, p["score_fix"],
           p["score_fix"] / 30 * 100))

np_block = (
    '<div class="np-head"><span class="np-head-title">护理组 · 工作量与物理治疗</span>'
    '<span class="np-head-sub">11.02—11.08 · 周报已交 · 7 天 / 17 人</span></div>'
    '<div class="np-banner"><b>本期（11.02—11.08）《护士周工作量统计表含排名》已交，三张 sheet 全部入库。</b>'
    '来源：<b>逐人逐日完成率与综合得分</b>、<b>物理治疗 6 项逐日应做 / 实做 / 未做</b>、<b>项目汇总</b>。'
    '三条口径不变：① <b>周总完成率 ＝ 已填日期完成率的算术平均</b>，未填日期忽略、不拉低均值；'
    '② <b>周总工作量得分 ＝ 7 天综合得分之和</b>；③ <b>周得分百分制 ＝ 周总得分 ÷ 30 × 100</b>（基准 30，源表可改）。'
    '完成率是效率（实做 ÷ 应做），得分是当日工作量权重，<b>两者不能互推，故排两张榜、不合成总分</b>。<br>'
    '<b>⚠ 源表 R5 有一处公式错误</b>（李永鑫行误引 J5，把 11.6 完成率当得分）：本页逐人明细保留源表显示值，'
    '排名按同列其余 16 行公式重算并标注，<b>源文件未改</b>。</div>'

    '<div class="npa-hero"><div class="npa-hero-main"><span class="npa-eyebrow">本期判断</span>'
    '<h3>物理治疗整体 <b>94.4%</b>，六项全部 ≥87%，<b>团体</b>仍是最后一块短板</h3>'
    '<p>7 天应做 <b>691</b>、实做 <b>652</b>、未做 <b>39</b> 人次，整体 <b>94.4%</b>（上期 90.1%，<b>+4.3pt</b>）。'
    '拆开看是三件事：应做 <b>699→691（−8）</b>、实做 <b>630→652（+22）</b>、未做 <b>69→39（−30）</b>——'
    '<b>分子涨得比分母降得多</b>，是真实改善，不是只靠应做变少。'
    '六项里 <b>音乐放松 97.2%</b>、<b>脑功能 96.8%</b>、<b>交流电 95.0%</b>（230/242，应做量最大）、经颅磁 93.8%、失眠 90.9% 都在 90% 以上；'
    '<b>团体 87.3%（55/63）</b>是唯一低于 90% 的项目，但已从上期 <b>71.1%</b> 修复 <b>16.2pt</b>。'
    '逐日看，<b>11.05 六项全 100%</b>（104/104）；<b>11.03 90.7% 最低</b>（107/118，经颅磁 80.8% 拖累）；'
    '<b>11.02 团体 63.6%（7/11）</b>是全周单格最低。'
    '工作量端 16 人合计 <b>459.9</b> 分（重算），<b>沈琳 62.1</b> 居首、完成率也排 9；<b>杨新金 57.2</b> 次之——'
    '「做得多」与「做得齐」本期仍不是同一批人。</p></div>'
    '<div class="npa-hero-side">'
    '<div class="npa-fact"><strong>94.4%</strong><span>六项完成率 · 652 / 691 人次</span></div>'
    '<div class="npa-fact"><strong class="bad">39</strong><span>未做合计 · 交流电 12 ＋ 经颅磁 9</span></div>'
    '<div class="npa-fact"><strong>42.0%</strong><span>完成率填报 · 50 / 119 格</span></div>'
    '</div></div>'

    '<div class="npa-kpis">'
    '<div class="npa-kpi ok"><label>六项完成率</label><strong>94.4<em>%</em></strong><small>实做 652 ÷ 应做 691</small></div>'
    '<div class="npa-kpi"><label>实做 / 应做</label><strong>652<em>/691</em></strong><small>未做 39 · 7 天</small></div>'
    '<div class="npa-kpi"><label>完成率首名</label><strong>100.0<em>%</em></strong><small>彭龙华、赵雯倩并列 · 下一名第 3</small></div>'
    '<div class="npa-kpi"><label>工作量首名</label><strong>62.1<em>分</em></strong><small>沈琳 · 源表显示李永鑫 100.1（公式待修）</small></div>'
    '<div class="npa-kpi warn"><label>完成率填报</label><strong>42.0<em>%</em></strong><small>50 / 119 格</small></div>'
    '<div class="npa-kpi warn"><label>综合得分填报</label><strong>53.8<em>%</em></strong><small>64 / 119 格</small></div>'

    '</div><div class="npa-duo"><div class="npa-card"><h4>物理治疗 6 项完成率 <em>7 天合计</em></h4>'
    '<p class="cap">按完成率排序，条长＝完成率本身（不是相对首名）。右侧为实做 / 应做与未做量。</p>'
    '<div class="npa-rk">__PROJ__</div></div>'
    '<div class="npa-card"><h4>逐日完成率 <em>11.02—11.08</em></h4>'
    '<p class="cap">应做量与完成率并不同向：11.03 应做 118 为全周最高、完成率 90.7% 最低；11.05 应做 104、六项全 100%。</p>'
    '<div class="np-orig-wrap"><table class="np-orig np-wide"><thead><tr><th>日期</th>'
    '<th class="npst-num">应做</th><th class="npst-num">实做</th><th class="npst-num">未做</th>'
    '<th class="npst-num">完成率</th></tr></thead><tbody>__DAILY__</tbody></table></div></div></div>'

    '<div class="npa-card" style="margin-bottom:12px"><h4>逐人逐日明细 <em>17 人 × 7 天</em></h4>'
    '<p class="cap">单元格＝<b>完成率% / 综合得分</b>；「—」为源表未填，<b>不按 0 计</b>。周总完成率＝已填日平均，'
    '周总得分＝7 天求和，百分制＝得分 ÷ 30 × 100。<b>李永鑫周得分 100.1 为源表 R5 公式误引 J5 所致</b>，'
    '本表保留源表显示值，排名卡按重算值 18.3 排序。</p>'
    '<div class="np-orig-wrap"><table class="np-orig np-wide"><thead><tr><th>姓名</th>'
    '<th class="npst-num">11.02</th><th class="npst-num">11.03</th><th class="npst-num">11.04</th>'
    '<th class="npst-num">11.05</th><th class="npst-num">11.06</th><th class="npst-num">11.07</th>'
    '<th class="npst-num">11.08</th><th class="npst-num">周完成率</th><th class="npst-num">率排名</th>'
    '<th class="npst-num">周得分</th><th class="npst-num">分排名</th><th class="npst-num">百分制</th>'
    '</tr></thead><tbody>__DETAIL__</tbody></table></div></div>'

    '<div class="npa-duo"><div class="npa-card"><h4>周总完成率排名 <em>效率口径 · 15 人</em></h4>'
    '<p class="cap">按已填日完成率的平均值排序。<b>陈福建 7 天无完成率、任健康整周 0 行，不进榜</b>（不是 0 分）。'
    '⚠ 并列第 1：彭龙华（只填 1 天）、赵雯倩（填 3 天），下一名直接第 3。</p>'
    '<div class="npa-rk">__RATERANK__</div></div>'
    '<div class="npa-card"><h4>周总工作量得分排名 <em>累计口径 · 16 人</em></h4>'
    '<p class="cap">按 7 天综合得分之和排序，满分基准 30。<b>⚠ 李永鑫为 18.3（第 13）</b>——源表显示 100.1 / 第 1，'
    '系 R5 误引 11.6 完成率；本榜按同列公式重算。任健康整周 0 行，不进榜。</p>'
    '<div class="npa-rk">__WORKRANK__</div></div></div>'

    '<div class="npa-card"><h4>口径与数据质量 <em>3 条待修 · 4 条说明</em></h4><div class="npa-ck">'
    '<div class="npa-ck-item"><h5>李永鑫 R5 公式误引 J5，工作量排名第 1 不成立<em>待修</em></h5>'
    '<p>R5 为 <b>SUM(C5,E5,G5,I5,J5,M5,O5)</b>，把 11.6 的<b>完成率 86.7</b> 当成综合得分计入，'
    '同时漏掉 K5（4.9）。同列其余 16 行均为 C,E,G,I,K,M,O。结果：周得分 <b>100.1</b>（应为 <b>18.3</b>）、'
    '排名 <b>1</b>（应为 <b>13</b>）、百分制 <b>333.7</b>（应为 <b>61.0</b>）。'
    '页面排名用重算值并标注，源文件未改。<b>建议直接把 R5 公式改为 K5。</b></p></div>'
    '<div class="npa-ck-item warn"><h5>周总完成率＝简单平均，填 1 天也能并列第 1<em>待定</em></h5>'
    '<p>AVERAGE 忽略空白日，不按治疗量加权：彭龙华只填 11.6 一天（100%）→ 周总 100.0%、第 1，但工作量只有 19.8（第 12）；'
    '赵雯倩 3 天全 100% → 同样第 1。梅燕萍只填 1 天 56.3% → 第 15。<b>分母天数在 1—6 天之间差异极大</b>，'
    '建议改按人次加权，或设「最低填报 4 天」才进效率榜。</p></div>'
    '<div class="npa-ck-item warn"><h5>百分制基准 30 失效，7 人超 100<em>待定</em></h5>'
    '<p>B22 基准仍为 30，而实际周得分区间 4.5—62.1，导致 7 人百分制越界（333.7 / 207.0 / 190.7 / 168.7 / 165.0 / 161.0 / 114.3）。'
    '建议基准改为 ≥65，或改用「组内最高＝100」归一。另：说明第 6 条写「基准在 B24」，实际在 <b>B22</b>。</p></div>'
    '<div class="npa-ck-item ok"><h5>底表自洽：42 行逐行成立、汇总与明细一致<em>通过</em></h5>'
    '<p>表2 全部 42 行满足「应做 − 实做 ＝ 未做」；表3 六项 SUMIF 与明细逐项吻合，合计 <b>691 / 652 / 39 / 94.4%</b>；'
    '逐日小计相加同为 691 / 652。表1 除 R5 外，其余 16 行的 P/Q/R/S/T 全部重算通过。</p></div>'
    '<div class="npa-ck-item warn"><h5>「住院人数」列 42 行全空，人次指标本周无法计算<em>缺项</em></h5>'
    '<p>表2 G 列（住院人数）42 行全空 → H 列「人次＝当日实做合计 ÷ 住院人数」公式全部返回空。'
    '本周只能报治疗人次 652，<b>不能报人均治疗次数</b>；说明区仍留着「10.18：78÷29≈2.7」的旧示例。</p></div>'
    '<div class="npa-ck-item warn"><h5>名册与上期不同：多赵林烦、梅燕萍，少杜萧、曾宇浩<em>待核</em></h5>'
    '<p>本期 17 人：李永鑫 / 彭龙华 / 杨新金 / 吴雨霏 / 陈福建 / 刘佳佳 / 沈琳 / 袁怡 / 何培培 / 彭榆凯 / 任健康 / '
    '杨思菡 / 丁思意 / 赵雯倩 / 杨欢 / 梅燕萍 / 赵林烦。上期名册里的<b>杜萧、曾宇浩</b>本周未出现；'
    '「沈 琳」源表姓名含空格，「赵林烦」疑录入有误，跨表匹配前需统一。</p></div>'
    '<div class="npa-ck-item ok"><h5>电休克与工娱不在本表，仍记 null<em>说明</em></h5>'
    '<p>本次 Excel 只含 6 项物理治疗；电休克、工娱场次与参与人数均未提供，页面留「—」，'
    '不拿上期 11 人次或汇报表 5 场 62 人顶替（后者为营销中心口径）。</p></div>'
    '</div></div>'

    '<div class="npa-pending"><span class="tg">源表</span><div>'
    '《护士周工作量统计表含排名11.2-11.8(1).xlsx》三张 sheet 逐格读取：'
    '17 人 × 7 天完成率 / 综合得分、42 行物理治疗逐日记录、6 项汇总。'
    '<b>与 Excel 复算一致</b>：691 / 652 / 39 / 94.4%，逐日小计 104 / 107 / 104 / 104 / 83 / 74 / 76；'
    '两套名次除 R5 外全部对齐。日期列为「11.2…11.8」数值/文本混用，已按 11.02—11.08 归一，7 天齐全。'
    '本期<b>未含</b>护理质量、制度建设、专项培训、人员配置四项——正文仍为 10.5—10.11 存档。'
    '</div></div>')


np_block = (np_block.replace("__PROJ__", proj_rows_html).replace("__DAILY__", daily_html).replace("__DETAIL__", detail_html).replace("__RATERANK__", rate_rank_html).replace("__WORKRANK__", work_rank_html))

between('<div class="np-head"><span class="np-head-title">护理组',
        '<div class="sheet-pane" id="diagnosisPane">',
        np_block, "np pane")

# =====================================================================
# 9. KPI 磁贴 / 全局口径文案
# =====================================================================
rep('<div class="kpi-tile" onclick="openDeptV2(\'nursing\')"><label>护理 6 项治疗完成率</label><strong>—<em>%</em></strong><span class="kpi-delta flat">周报未交 · 源表 10.17</span></div>',
    '<div class="kpi-tile" onclick="openDeptV2(\'nursing\')"><label>护理 6 项治疗完成率</label><strong>94.4<em>%</em></strong><span class="kpi-delta up">652 / 691 · +4.3pt</span></div>',
    "KPI tile")

rep('护理六项完成率本周<b>周报未交</b>（源表 10.17），记 null、<b>不拿上期 90.1% 顶替</b>。',
    '护理六项完成率 <b>94.4%</b>（<b>652 / 691</b>，未做 39）取《护士周工作量统计表含排名》11.02—11.08（7 天 / 17 人），较上期 90.1% <b>+4.3pt</b>。',
    "kpi-foot")

rep('护理＝汇报表只填物理治疗 <b>484 人</b>、工娱 <b>5 场 62 人</b>，<b>周报未交</b>（源表 10.17）。<b>缺失一律记 null、不写 0</b>：六项完成率、出院、营销表头、到院登记本周值均留空。',
    '护理＝周报《护士周工作量统计表含排名》（7 天 / 17 人）六项应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b> / <b>94.4%</b>；汇报表另填物理治疗 <b>484 人</b>、工娱 <b>5 场 62 人</b>（<b>人数与人次不同源、不可相加</b>）。<b>缺失一律记 null、不写 0</b>：出院、营销表头、到院登记本周值留空。',
    "dept kpi-foot")

rep('管家取 5 张分表；<b>护理本周周报未交</b>（源表 10.17），六项完成率记 null。抓取时间 2026-11-08 22:26',
    '管家取 5 张分表；<b>护理周报已交</b>（11.02—11.08，7 天 / 17 人），六项完成率 <b>94.4%</b>（652/691）。抓取时间 2026-11-09 09:20',
    "signals kpi-foot")

rep('<div class="ai-balance-head"><b>1</b><strong>变差的业务</strong></div><p>① 门诊 181 人次（<span class="changed-bad">−32.2%</span>）、营销对接 41 条（<span class="changed-bad">−55.4%</span>），前端两条线同时缩量。</p><p>② 护理周报连续三周未交，六项完成率全空；到院登记本周无新表，记 null。</p>',
    '<div class="ai-balance-head"><b>1</b><strong>变差的业务</strong></div><p>① 门诊 181 人次（<span class="changed-bad">−32.2%</span>）、营销对接 41 条（<span class="changed-bad">−55.4%</span>），前端两条线同时缩量。</p><p>② 护理六项 94.4%（<span class="changed-good">+4.3pt</span>）已回升，但两套排名口径待修；到院登记本周无新表，记 null。</p>',
    "ai-balance-more")

rep("['护理组','六项完成率（周报未交）',null,'—']", "['护理组','六项完成率',94.4,'652 / 691']", "benchmarks")

rep('<b>17/18</b>', '<b>16/17</b>', "coverage ring")
rep('护士 17/18 是 <b>10.26—11.01 存档</b>，本周周报未交。',
    '护士 16/17（<b>任健康整周 0 行</b>）本期已交，六项完成率 94.4%。', "coverage note")

rep('<small>护理周报</small><b>未交</b>', '<small>护理六项</small><b>94.4%</b>', "flow node")

# 质量清单里的护理条目
i = s.find('<div class="quality-item"><strong>护理部：')
assert i > 0
j = s.find("</div>", i)
quality_new = ('<div class="quality-item"><strong>护理部：周报已交，但源表有 1 处公式错、2 处排门口径要修</strong>'
               '<p>本期（11.02—11.08）《护士周工作量统计表含排名》7 天 / 17 人已入库：应做 <b>691</b> / 实做 <b>652</b> / '
               '未做 <b>39</b> / <b>94.4%</b>，上期 90.1%，<b>+4.3pt</b>。'
               '⚠ ① R5（李永鑫）公式误引 J5，把 11.6 的完成率 86.7 当得分，显示 100.1 / 第 1 / 百分制 333.7，'
               '按同列公式应为 <b>18.3 / 第 13 / 61.0</b>；② 周总完成率是已填日<b>简单平均</b>，彭龙华只填 1 天 100% 即并列第 1；'
               '③ 百分制基准 30 失效，<b>7 人超 100</b>。页面按重算值排名并保留源表显示值，<b>源文件未改</b>。'
               '另：汇报表 <b>484 人</b>与周报 <b>691/652 人次</b>不同源，只并列、不相加。</p></div>')
s = s[:i] + quality_new + s[j + len("</div>"):]
cnt[0] += 1

# =====================================================================
# 10. 信号卡 / 可视化卡 / 任务卡
# =====================================================================
def cut_from(start, endmark, new, label, keep_end=False):
    """从 start 起到 endmark（含/不含）整段替换。"""
    global s
    a = s.find(start)
    assert a >= 0, "找不到起点 " + label
    b = s.find(endmark, a + len(start))
    assert b > a, "找不到终点 " + label
    b2 = b if keep_end else b + len(endmark)
    s = s[:a] + new + s[b2:]
    cnt[0] += 1


simple_sig = ("{level:'growth',title:'护理周报已交：六项 94.4%，团体仍是唯一低于 90% 的项目',sub:'护理组',value:'94.4%',"
              "body:'《护士周工作量统计表含排名》11.02—11.08（7 天 / 17 人）：应做 <span class=\"hl-key\">691</span> / "
              "实做 <span class=\"hl-key\">652</span> / 未做 <span class=\"hl-key\">39</span>，完成率 "
              "<span class=\"hl-key\">94.4%</span>（上期 699 / 630 / 69 / 90.1%，<b>+4.3pt</b>）。"
              "团体 87.3%（55/63）仍是六项最低，失眠 90.9% 已从 72.2% 修复。',"
              "action:'修 R5 公式（J5→K5）与百分制基准；团体按带组人逐日复盘；汇报表 484 人与周报 652 人次只并列、不相加。',"
              "owners:['护理组','运营']}")
cut_from("{level:'watch',title:'护理周报连续三周未交", "owners:['护理组','运营']}", simple_sig, "simple signal")

detail_sig = ("{level:'growth',title:'护理周报已交：94.4%，团体仍是唯一低于 90% 的项目',sub:'护理组',value:'94.4%',"
              "evidence:'《护士周工作量统计表含排名》11.02—11.08（7 天 / 17 人）：应做 <b>691</b> / 实做 <b>652</b> / 未做 <b>39</b>，"
              "完成率 <b>94.4%</b>（上期 699 / 630 / 69 / 90.1%，<b>+4.3pt</b>）。团体 87.3%（55/63）最低；失眠 90.9%（40/44）已从 72.2% 修复。'"
              ",judgment:'完成率 <span class=\"changed-good\">+4.3pt</span> 由两端合成：应做 <b>−8</b>、实做 <b>+22</b>、未做 <b>−30</b>。"
              "实做增长是主因，但应做量本身在缩，<b>不能只用完成率代表治疗兑现</b>。'"
              ",verify:'应做 699→691 是住院量下降还是排班减少？团体 7 天里 6 天有未做，11.02 单日 63.6% 是谁带组？源表 R5 公式与百分制基准何时修？'"
              ",action:'先修 R5（J5→K5）与基准；团体按带组人复盘；完成率榜改按人次加权或设最低填报 4 天。'"
              ",owners:[\"护理组\", \"运营\"]}")
cut_from("{level:'watch',title:'护理周报连续三周未交", "owners:[\"护理组\", \"运营\"]}", detail_sig, "detail signal")

viz_new = ('<article class="viz-card"><div class="viz-card-head"><div><strong>护理六项完成率 94.4%，团体 87.3% 仍是唯一短板</strong>'
           '<br><span>护理组 11.02—11.08 · 7 天 / 17 人</span></div><div class="big-signal">94.4%<small>六项完成率</small></div></div>'
           '<div class="viz-main"><div class="pair-chart">'
           '<div class="pair-row"><label>应做</label><span class="pair-track"><i class="pair-fill" style="--w:100%"></i></span><b>691</b></div>'
           '<div class="pair-row"><label>实做</label><span class="pair-track"><i class="pair-fill" style="--w:94.4%"></i></span><b>652</b></div>'
           '<div class="pair-row"><label>未做</label><span class="pair-track"><i class="pair-fill" style="--w:5.6%"></i></span><b>39</b></div>'
           '</div></div><div class="chart-note always-show action-note">'
           '<b>说明什么：</b>上期 699 / 630 / 69 / 90.1% → 本期 691 / 652 / 39 / <b>94.4%</b>，应做 <b>−8</b>、实做 <b>+22</b>、未做 <b>−30</b>，'
           '分子涨得比分母降得多，是真实改善。<b>团体 87.3%</b>（55/63）仍是六项最低，但已从 71.1% 修复 16.2pt；<b>失眠 90.9%</b> 从 72.2% 修复 18.7pt。'
           '<br><b>先确认：</b>应做量为什么缩了 8？团体 11.02 为什么只有 7/11？源表 R5 公式与百分制基准谁来修？'
           '<br><b>下一步：</b>修 R5（J5→K5）、基准 30→≥65；团体按带组人逐日复盘；汇报表 484 人与周报 652 人次只并列、不相加。</div></article>')
cut_from('<article class="viz-card alert"><div class="viz-card-head"><div><strong>护理周报连续三周未交', '</article>', viz_new, "viz card")

task_new = ("{id:'nursing-report',title:'护理部：修 R5 公式与两套排名口径',owner:'护理组、运营',deadline:'下周三前',"
            "deliver:'周报已交（11.02—11.08，7 天 / 17 人，94.4%），但源表有 3 处口径要修：① R5 误引 J5（J5→K5），"
            "李永鑫 100.1 / 第 1 应改为 <b>18.3 / 第 13</b>；② 周总完成率为已填日简单平均，1 天 100% 即并列第 1，"
            "建议按人次加权或设最低填报 4 天；③ 百分制基准 30 失效，7 人超 100，建议 ≥65。"
            "另需书面确认汇报表 484 是人数还是人次（与周报 691/652 人次不同源）。'}")
# 任务卡：整对象替换
a = s.find("{id:'nursing-report',title:'护理部：恢复周报")
assert a > 0
b = s.find("不同源的归属。'}", a)
assert b > a
b += len("不同源的归属。'}")
s = s[:a] + task_new + s[b:]
cnt[0] += 1


open(HTML, "w", encoding="utf-8").write(s)
print("index.html replacements:", cnt[0])

# =====================================================================
# 11. snapshot.json
# =====================================================================
snap = json.load(open(SNAP, encoding="utf-8"))
nd = snap["departments"]["nursing"]
nd["weeklySubmitted"] = True
nd["weeklyThrough"] = "2026-11-08"
key_map = {"交流电": "ac_current", "经颅磁": "tms", "脑功能": "brain_func",
           "放松": "music_relax", "失眠": "insomnia", "团体": "group_biofeedback"}
for t in nd["treat"]:
    src = next(x for x in proj if key_map[x["label"]] == t["key"])
    t["due"], t["done"], t["missed"], t["rate"] = src["due"], src["done"], src["miss"], src["rate"]
nd["treatSummary"] = {
    "due": TOT_DUE, "done": TOT_DONE, "missed": TOT_MISS, "rate": TOT_RATE,
    "items": 6, "worst": "团体生物反馈",
    "rateRule": "round1",
    "source": "nursing_weekly",
    "dailyThrough": "2026-11-08",
    "note": "应做/实做/未做取源表《物理治疗项目汇总》第 9 行；完成率=实做÷应做，保留 1 位小数。"
}
snap["watermarks"]["nursing"] = {"dataThrough": "2026-11-08", "days": 7,
                                 "authority": "nursing_weekly",
                                 "dailyThrough": "2026-11-08", "stale": False}
json.dump(snap, open(SNAP, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("snapshot.json nursing updated")

# =====================================================================
# 12. 其它 JS
# =====================================================================
for path, pairs in {
    "live-sync.js": [
        ("'630 / 699 · 未做 ' + ((dpNur.treatSummary && dpNur.treatSummary.missed != null) ? dpNur.treatSummary.missed : '—')",
         "((dpNur.treatSummary && dpNur.treatSummary.done != null) ? dpNur.treatSummary.done : '—') + ' / '\n"
         "              + ((dpNur.treatSummary && dpNur.treatSummary.due != null) ? dpNur.treatSummary.due : '—')\n"
         "              + ' · 未做 ' + ((dpNur.treatSummary && dpNur.treatSummary.missed != null) ? dpNur.treatSummary.missed : '—')"),
    ],
    "month-dashboard.js": [
        ("metric:'90.1%',note:'本期 10.26–11.01 · 六项治疗完成率（7 天）',foot:'630 / 699 · 未做 69'",
         "metric:'94.4%',note:'本期 11.02–11.08 · 六项治疗完成率（7 天）',foot:'652 / 691 · 未做 39'"),
    ],
    "business-analysis.js": [
        ("nurseShould: 699, nurseDone: 630, nurseMiss: 69, nurseRate: '90.1', nurseDrop: '-2.7',",
         "nurseShould: 691, nurseDone: 652, nurseMiss: 39, nurseRate: '94.4', nurseDrop: '+4.3',"),
        ("nurseWeek: '10.26—11.01（已交 · 7 天）',", "nurseWeek: '11.02—11.08（已交 · 7 天）',"),
        ("/* ⭐ 2026-11-02：护理考核表已交（10.26—11.01，7 天 / 17 行）——\n       物理治疗应做 699 / 实做 630 / 未做 69、完成率 90.1%（上期 92.8%，−2.7pt）；",
         "/* ⭐ 2026-11-09：护理周报已交（11.02—11.08，7 天 / 17 人）——\n       物理治疗应做 691 / 实做 652 / 未做 39、完成率 94.4%（上期 90.1%，+4.3pt）；"),
    ],
}.items():
    p = os.path.join(ROOT, path)
    t = open(p, encoding="utf-8").read()
    for old, new in pairs:
        if t.count(old) == 1:
            t = t.replace(old, new)
        elif t.count(new) == 1:
            continue
        else:
            raise AssertionError("%s 命中 %d 次：%s" % (path, t.count(old), old[:50]))
    open(p, "w", encoding="utf-8").write(t)
    print(path, "updated")

print("DONE")
