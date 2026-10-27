#!/usr/bin/env python3
"""把 index.html 里四个「整块硬编码」的 JS 常量按 data/snapshot.json 重生成。

覆盖：const periods / const departments / const signals / const tasks / const analytics

⛔ 2026-10-24 背景：换到 10.19–10.25 自然周后，这四个块仍整块停在 10.12—10.18
   （signals 甚至停在 9.20—9.26），任何一屏都能看到上一周的数。
   它们结构固定、体量大、手工改必然漏，所以整块重生成而不是逐句替换。

用法：
    python3 scripts/live-data/reweave.py            # 写入
    python3 scripts/live-data/reweave.py --dry-run  # 只打印体量
"""
import datetime as dt
import json
import os
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML = os.path.join(ROOT, "index.html")
DB = os.path.join(ROOT, "db", "live-data.sqlite")
SNAP = json.load(open(os.path.join(ROOT, "data", "snapshot.json"), encoding="utf-8"))
# 医生周排名（《周排名分析_*.xlsx》抽出的个人口径，出院结账）
_DRK = os.path.join(ROOT, "data", "doctor-rank.json")
DRK = json.load(open(_DRK, encoding="utf-8")) if os.path.exists(_DRK) else None

P = SNAP["period"]
LBL = P["label"]                        # 10.19–10.25
DT = P["dataThrough"][5:].replace("-", ".")
N = P["daysRecorded"]
M = SNAP["metrics"]
DEP = SNAP["departments"]
PSY = SNAP["psych"]
SVC = SNAP["service"]
BUT = SNAP["butler"]
ARR = SNAP["arrival"]
PREV = SNAP["previousPeriod"]
PS = PREV["start"][5:].replace("-", ".")
PE = PREV["compareSameDaysEnd"][5:].replace("-", ".")
CUR_LBL = f"本期 {LBL}"
PREV_LBL = f"上期同 {N} 天"
WAY = "营收日报"


# ---------------------------------------------------------------- JS 序列化
def js(v):
    """Python → 单行 JS 字面量。键不加引号；字符串用单引号并转义。"""
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return repr(round(v, 4)) if isinstance(v, float) else str(v)
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(js(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}:{js(x)}" for k, x in v.items()) + "}"
    raise TypeError(type(v))


def pct(a, b):
    if not b:
        return None
    return round((a - b) / b * 100, 1)


def sp(v):
    """带符号的百分比。"""
    return None if v is None else ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v):.1f}%"


# ---------------------------------------------------------------- 周序列
def _conn():
    d = tempfile.mkdtemp()
    shutil.copy(DB, os.path.join(d, "x.sqlite"))
    j = DB + "-journal"
    if os.path.exists(j):
        shutil.copy(j, os.path.join(d, "x.sqlite-journal"))
    return sqlite3.connect(os.path.join(d, "x.sqlite"))


def week_sum(c, mids, start, end):
    tot, any_ = 0.0, False
    for m in mids:
        v = c.execute(
            "SELECT SUM(value) FROM fact WHERE metric_id=? AND business_date BETWEEN ? AND ?",
            (m, start, end)).fetchone()[0]
        if v is not None:
            tot += float(v)
            any_ = True
    return tot if any_ else None


def weekly():
    """近五个自然周（含本周，本周为不完整周）的部门序列。缺数据记 None。"""
    c = _conn()
    weeks = [("2026-09-21", "9.21"), ("2026-09-28", "9.28"),
             ("2026-10-05", "10.5"), ("2026-10-12", "10.12"), ("2026-10-19", "10.19")]
    out = {"labels": [w[1] for w in weeks], "doctor": {}, "psych": {}, "service": {}, "butler": {}}
    for key, mids, scale in (
        ("rev", ("revenue.outpatient", "revenue.inpatient"), 10000.0),
        ("visits", ("visit.new", "visit.return"), 1.0),
        ("admit", ("admit",), 1.0),
        ("discharge", ("discharge",), 1.0),
    ):
        out["doctor"][key] = []
        for s, _ in weeks:
            e = (dt.date.fromisoformat(s) + dt.timedelta(days=6)).isoformat()
            v = week_sum(c, mids, s, e)
            out["doctor"][key].append(None if v is None else round(v / scale, 2))
    for key, mids in (("contact", ("psych.first_contact", "psych.emotion_support", "psych.inpatient_consult")),
                      ("consult", ("psych.inpatient_consult", "psych.outpatient_consult", "psych.family_consult"))):
        out["psych"][key] = []
        for s, _ in weeks:
            e = (dt.date.fromisoformat(s) + dt.timedelta(days=6)).isoformat()
            out["psych"][key].append(week_sum(c, mids, s, e))
    for key, mids in (("followup", ("service.followup",)), ("arrived", ("service.arrived",)),
                      ("workload", ("service.workload",))):
        out["service"][key] = []
        for s, _ in weeks:
            e = (dt.date.fromisoformat(s) + dt.timedelta(days=6)).isoformat()
            out["service"][key].append(week_sum(c, mids, s, e))
    for key, mids in (("contact", ("butler.contact",)), ("admit", ("butler.admit",))):
        out["butler"][key] = []
        for s, _ in weeks:
            e = (dt.date.fromisoformat(s) + dt.timedelta(days=6)).isoformat()
            out["butler"][key].append(week_sum(c, mids, s, e))
    c.close()
    return out


W = weekly()


def trim(series):
    """去掉前面连续的空值，只保留真正有数据的周；返回 (labels, values)。"""
    vals = list(series)
    labs = list(W["labels"])
    while vals and vals[0] is None:
        vals.pop(0)
        labs.pop(0)
    return labs, vals


# ---------------------------------------------------------------- departments
def build_departments():
    d = {}
    doc, nur, psy, svc, mkt = (DEP["doctor"], DEP["nursing"], DEP["psychology"],
                               DEP["service"], DEP["marketing"])
    cw = DEP["compareWeek"]
    wv, wo, wi = M["weekVisits"]["value"], M["weekOutpatient"]["value"], M["weekInpatient"]["value"]
    ward_prev = next((x["ward"] for x in SNAP["daily"] if x["date"] == PREV["compareSameDaysEnd"]), None)

    d["doctor"] = {
        "name": "医生组", "icon": "医", "status": "表头未滚动", "statusClass": "medium",
        "summary": f"{M['weekRevenue']['value']} 万", "delta": sp(M["weekRevenue"]["deltaPct"]),
        "metrics": [
            [f"本期营收（{WAY}台账）", cw["revenueWan"], M["weekRevenue"]["value"], "万元",
             f"营收日报逐日台账，已录 {N} 天（{P['start'][5:]}—{DT}）：门诊 {wo} 万 ＋ 在院 {wi} 万。"
             f"上期取同一窗口长度（{PS}—{PE}，{N} 天）{cw['revenueWan']} 万，"
             f"<b>{sp(M['weekRevenue']['deltaPct'])}</b>。"
             f"⚠ 与《特别行动小组汇报表》表头不同源——那张表本周整表未滚动，已停用。",
             PREV_LBL, CUR_LBL],
            ["门诊人次（门诊收入 ÷ 人次）", cw["outpatient"], wv, "人次",
             f"营收日报「初诊＋复诊」逐日加总：<b>{wv}</b> 人次，上期同 {N} 天 <b>{cw['outpatient']}</b>，"
             f"<b>{sp(M['weekVisits']['deltaPct'])}</b>。门诊收入 {wo} 万，客单 "
             f"<b>{round(wo * 10000 / max(1, wv)):.0f} 元/人次</b>。",
             PREV_LBL, CUR_LBL],
            ["入院人数", cw["admit"], M["weekAdmit"]["value"], "人",
             f"<b>{M['weekAdmit']['value']}</b> 人，上期同 {N} 天 {cw['admit']} 人，"
             f"<b>{sp(M['weekAdmit']['deltaPct'])}</b>。逐日来自营收日报「入院」列，"
             f"与汇报表表头（本周未滚动）不同源、<b>不可互相校验</b>。",
             PREV_LBL, CUR_LBL],
            ["出院人数", cw["discharge"], M["weekDischarge"]["value"], "人",
             f"<b>{M['weekDischarge']['value']}</b> 人，上期同 {N} 天 {cw['discharge']} 人，"
             f"<b>{sp(M['weekDischarge']['deltaPct'])}</b>。口径＝出院初次 ＋ 出院多次，"
             f"与「入院」配对看患者池净变化 <b>{M['weekAdmit']['value'] - M['weekDischarge']['value']:+d} 人</b>。",
             PREV_LBL, CUR_LBL],
            ["在院人数（时点）", ward_prev, M["wardCount"]["value"], "人",
             f"<b>{M['wardCount']['value']} 人</b>（{DT} 时点，营收日报在院列），"
             f"上期同日（{PREV['compareSameDaysEnd'][5:]}）<b>{ward_prev if ward_prev is not None else '—'}</b> 人。"
             f"时点数不等于周内合计，<b>不做环比</b>。", "上期同日", f"{DT} 时点"],
            ["物理治疗费", None, None, "万元",
             "本周<b>无逐日台账</b>，汇报表表头又未滚动，按契约<b>记 null</b>、不拿上一期的值顶替。"
             "需财务补一张按日拆分的物理治疗收入表。", "—", CUR_LBL],
            ["10 月累计营收", None, M["monthRevenue"]["value"], "万元",
             f"10.1—{DT} 累计 <b>{M['monthRevenue']['value']}</b> 万 / 目标 "
             f"{M['monthRevenue']['targetWan']} 万 ＝ <b>{M['monthRevenue']['amountProgress']}%</b>，"
             f"时间进度 {M['monthRevenue']['timeProgress']}%，差 "
             f"<b>{M['monthRevenue']['amountProgress'] - M['monthRevenue']['timeProgress']:+.1f}pt</b>，"
             f"剩余缺口 <b>{M['monthRevenue']['gap']}</b> 万。", "—", f"10.1—{DT}"],
        ],
        "advice": [
            ["本周只认营收日报台账，汇报表整表停用",
             "《特别行动小组汇报表》医生组表头四项与正文「第 3 周」列逐项同值，说明整表还停在上一期。"
             f"本周医生组全部改用营收日报逐日台账（{N} 天）：营收 <b>{M['weekRevenue']['value']}</b> 万、"
             f"门诊 <b>{wv}</b> 人次、入 <b>{M['weekAdmit']['value']}</b> / 出 <b>{M['weekDischarge']['value']}</b>。"
             "原表头值已存档，补齐后自动切回。"],
            ["物理治疗费是本周唯一的空白项",
             "物理治疗费既没有逐日台账、汇报表表头又未滚动，只能记 null。"
             "这是医生组六个核心指标里唯一拿不到数的，建议财务按日拆分后并入营收日报。"],
            ["月度进度需要逐日盯",
             f"10 月累计 {M['monthRevenue']['value']} 万、完成 {M['monthRevenue']['amountProgress']}%，"
             f"时间进度 {M['monthRevenue']['timeProgress']}%，基本同步。"
             f"剩余 {M['monthRevenue']['gap']} 万缺口，按本周日均 "
             f"{round(M['weekRevenue']['value'] / max(1, N), 2)} 万测算，需要保持不掉速。"],
        ],
    }

    d["nursing"] = {
        "name": "护理组", "icon": "护", "status": "本周未提交", "statusClass": "high",
        "summary": "未提交", "delta": "—",
        "metrics": [
            ["六项治疗完成率", None, None, "%",
             "本周<b>未提交</b>：护理部周报与《质控分及物理治疗数据》逐日表最新只到 "
             f"{nur.get('weeklyThrough') or '—'}，10.19 起没有任何一条护理事实入库。"
             "按契约记 null，<b>不拿上一期的 93% 顶替</b>。", "—", CUR_LBL],
            ["物理治疗人数", None, None, "人次",
             "同上，本周无数据。汇报表护理组表头同样未滚动（与上一期逐项同值），不引用。", "—", CUR_LBL],
            ["工娱（场 / 人次）", None, None, "",
             "工娱原由护理组报送、现归营销中心呈现；本周两边都没有新数据，记 null。", "—", CUR_LBL],
            ["五维考核（工作量 / 质控 / 综合）", None, None, "分",
             "《护士工作量及质量排名》四张 sheet 停在同一考核周，未随自然周滚动；"
             "本周无法给出组内排名，<b>不做跨周比较</b>。", "—", CUR_LBL],
            ["周报截止日", None, None, "",
             f"最后一次有数据的日期＝<b>{nur.get('weeklyThrough') or '—'}</b>；"
             f"本周窗口 {LBL} 内 0 条。", "—", CUR_LBL],
        ],
        "advice": [
            ["护理是本周唯一整块缺报的部门",
             f"周报与逐日表都停在 {nur.get('weeklyThrough') or '—'}，本周 0 条事实。"
             "缺报期间不做环比、不排名、不参与绩效核算——拿上一期数字顶上会直接误导派班。"],
            ["需要补报三样东西",
             "① 10.19—10.24 六项治疗应做 / 实做逐日数；② 物理治疗人数（含住院＋门诊）；"
             "③ 工娱场次与参与人数。三项补齐后本周才能与医生组、财务口径对齐。"],
            ["补报前的展示约定",
             "本页所有护理相关格子显示「—」，不显示任何上一期数值；"
             "等补报到位后由同一套管线自动填回，不需要手工改页面。"],
        ],
    }

    w_psy = PSY["week"]
    p_psy = PSY["prevSameDays"]
    bind_rows, bind_ppl = psy.get("bindRows") or 0, psy.get("bindPeople") or 0
    d["psychology"] = {
        "name": "心理咨询组", "icon": "心", "status": "日报待补", "statusClass": "medium",
        "summary": f"{psy['consult']} 人次", "delta": sp(pct(w_psy["consult"], p_psy["consult"])),
        "metrics": [
            ["咨询工作量（V4）", p_psy["consult"], w_psy["consult"], "人次",
             f"口径＝住院 ＋ 门诊 ＋ 家庭咨询。<b>{w_psy['consult']}</b> 人次（住院 {w_psy['inpatient']} ＋ "
             f"门诊 {w_psy['outpatient']} ＋ 家庭 {w_psy['family']}），上期同天数 {p_psy['consult']}，"
             f"<b>{sp(pct(w_psy['consult'], p_psy['consult']))}</b>。", "V4 上期同天数", CUR_LBL],
            ["患者接触（V4）", p_psy["contact"], w_psy["contact"], "人次",
             f"口径＝24h 首次对接 ＋ 情绪支持 ＋ 住院咨询。<b>{w_psy['contact']}</b> 人次"
             f"（首次 {w_psy['first']} ＋ 情绪 {w_psy['emotion']} ＋ 住院 {w_psy['inpatient']}），"
             f"上期同天数 {p_psy['contact']}，<b>{sp(pct(w_psy['contact'], p_psy['contact']))}</b>。"
             f"<b>接触 ≠ 咨询</b>：同一患者可同时计入两项，<b>不可相加</b>。", "V4 上期同天数", CUR_LBL],
            ["家长访谈（V4）", p_psy["parent"], w_psy["parent"], "人次",
             f"「家长访谈人次」列求和：<b>{w_psy['parent']}</b>，上期同天数 {p_psy['parent']}。", "V4 上期同天数", CUR_LBL],
            ["团体治疗", p_psy["groupSessions"], w_psy["groupSessions"], "场",
             f"本期实登 <b>{w_psy['groupSessions']} 场 / {w_psy['groupPeople']} 人次</b>，"
             f"上期同天数 {p_psy['groupSessions']} 场 / {p_psy['groupPeople']} 人次。"
             f"⚠ 汇报表表头仍写「团辅 4 场」，是 2026-09-21 的旧值，<b>与本周不符</b>。", "V4 上期同天数", CUR_LBL],
            ["日报填报", p_psy["report"], w_psy["report"], "条",
             f"本周 <b>{w_psy['report']}</b> 条（上期同天数 {p_psy['report']}）。"
             f"与「周个人统计」的 {PSY.get('weekSum', {}).get('report_days', 0)} 天对不上，"
             f"差额来自查房、首次对接等不进日报的条目，<b>两套口径不可互相校验</b>。", "V4 上期同天数", CUR_LBL],
            ["管床对接新增", None, bind_rows, "行",
             f"本周新建 <b>{bind_rows} 行 / {bind_ppl} 名患者</b>，累计在管 "
             f"<b>{psy.get('boundPatients') or 0}</b> 人。", "—", CUR_LBL],
            ["累计在管患者", None, psy.get("boundPatients") or 0, "人",
             "按对接表「未填出院日期」计。<b>不等于在院人数</b>：含已出院但仍在管随访的患者。", "—", CUR_LBL],
        ],
        "advice": [
            ["汇报表心理组表头不能用",
             f"表头停在 {psy.get('headerAsOf')}，此后一直没滚动（团辅仍写 4 场，本周实登 "
             f"{w_psy['groupSessions']} 场）。本周一律取 V4 管理表逐条汇总，旧值只存档。"],
            ["工作量高度集中",
             f"咨询量第一的咨询师做了 {PSY['rank'][0]['consult']} 人次，占全组 "
             f"{round(PSY['rank'][0]['consult'] / max(1, w_psy['consult']) * 100)}%。"
             "单人依赖是排班风险，需要确认备班。"],
            ["日报完整率仍是短板",
             f"本周只有 {w_psy['report']} 条日报。数据可用性比工作量更值得关注——"
             "建议把日报改成当班即填，而不是周末补。"],
        ],
    }

    sw_, pw_ = SVC["week"], SVC["prevSameDays"]
    staff_txt = "、".join(f"{k} {v}" for k, v in (SVC.get("staff") or [])) or "—"
    d["service"] = {
        "name": "客服服务部", "icon": "客", "status": "到院率回升", "statusClass": "low",
        "summary": f"{sw_['followup']} 条", "delta": sp(pct(sw_["followup"], pw_["followup"])),
        "metrics": [
            ["导医回访（标准化回访台账）", pw_["followup"], sw_["followup"], "条",
             f"逐条台账：<b>{sw_['followup']}</b> 条，上期同 {SVC and SNAP['watermarks']['service']['days']} 天 "
             f"{pw_['followup']} 条，<b>{sp(pct(sw_['followup'], pw_['followup']))}</b>。逐人 <b>{staff_txt}</b>。",
             "上期同天数", CUR_LBL],
            ["标注到院", pw_["arrived"], sw_["arrived"], "人",
             f"回访台账「是否到院＝是」计数：<b>{sw_['arrived']}</b> 人，上期同天数 {pw_['arrived']} 人。",
             "上期同天数", CUR_LBL],
            ["台账到院率", pw_["rate"], sw_["rate"], "%",
             f"到院率 <b>{sw_['rate']}%</b>，上期 {pw_['rate']}%，"
             f"<b>{sw_['rate'] - pw_['rate']:+.1f}pt</b>。⚠ 样本只有 {sw_['followup']} 条，"
             f"率值波动被放大，<b>不宜单独作为考核依据</b>。", "上期同天数", CUR_LBL],
            ["导诊主动服务", pw_["guide"], sw_["guide"], "条",
             f"「导诊主动服务记录表」<b>{sw_['guide']}</b> 条，上期 {pw_['guide']} 条，"
             f"<b>{sp(pct(sw_['guide'], pw_['guide']))}</b>。", "上期同天数", CUR_LBL],
            ["导医日工作量", pw_["workload"], sw_["workload"], "分",
             f"「日工作量考核表(分级)」合计 <b>{sw_['workload']:,}</b> 分，上期 {pw_['workload']:,} 分，"
             f"<b>{sp(pct(sw_['workload'], pw_['workload']))}</b>。"
             f"履职分两期都是满分/人日，差额全部来自增值列。", "上期同天数", CUR_LBL],
        ],
        "advice": [
            ["回访量在掉、到院率在升，不能读成质量改善",
             f"回访 {pw_['followup']} → {sw_['followup']} 条，到院率 {pw_['rate']}% → {sw_['rate']}%。"
             "样本变小会让率值失真——分子分母都变小时，率上升没有统计意义。"],
            ["回访压在一个人身上",
             f"本周台账逐人只有 <b>{staff_txt}</b>，其余导医 0 条记录。"
             "是排班只留一人、还是其他人漏填，需要组长确认，否则排名会变成「谁填表谁上榜」。"],
            ["逐日波动说明台账在补记",
             "本周逐日回访最低 1 条、最高 11 条，说明不是当日记。建议改为当班即录，"
             "否则到院率会跟着失真。"],
        ],
    }

    bw_, bp_ = BUT["week"], BUT["prevSameDays"]
    but_staff = "、".join(f"{k} {v}" for k, v in BUT["staff"])
    d["marketing"] = {
        "name": "营销中心", "icon": "营", "status": "两人零记录", "statusClass": "medium",
        "summary": f"{bw_['contact']} 条", "delta": sp(pct(bw_["contact"], bp_["contact"])),
        "metrics": [
            ["有效对接（管家对接表）", bp_["contact"], bw_["contact"], "条",
             f"各管家分表逐条加总：<b>{bw_['contact']}</b> 条（{but_staff}），"
             f"上期同 {SNAP['watermarks']['butler']['days']} 天 {bp_['contact']} 条，"
             f"<b>{sp(pct(bw_['contact'], bp_['contact']))}</b>。", "上期同天数", CUR_LBL],
            ["转住院", bp_["admit"], bw_["admit"], "人",
             f"<b>{bw_['admit']}</b> 人，上期同天数 {bp_['admit']} 人，"
             f"<b>{sp(pct(bw_['admit'], bp_['admit']))}</b>。", "上期同天数", CUR_LBL],
            ["转住院率", bp_["rate"], bw_["rate"], "%",
             f"<b>{bw_['rate']}%</b>，上期 {bp_['rate']}%，<b>{bw_['rate'] - bp_['rate']:+.1f}pt</b>。"
             f"转化能力基本持平，前端量在收缩。", "上期同天数", CUR_LBL],
            ["本周零记录的管家", None, None, "",
             f"<b>{'、'.join(BUT['missingStaff'])}</b> 本周没有任何对接记录。"
             "按契约记 null、<b>不按 0 降榜</b>；需确认是休假、调岗还是漏填。", "—", CUR_LBL],
            ["营销中心表头（入院 / 门诊 / 总收入）", None, None, "",
             "汇报表营销中心整行空白，本周三项<b>全部记 null</b>，不拿其他源代替。", "—", CUR_LBL],
        ],
        "advice": [
            ["条数降、转化率持平",
             f"{bw_['contact']} 条（上期同天数 {bp_['contact']}）、转住院 {bw_['admit']} 人"
             f"（{bp_['admit']} 人）、率值 {bw_['rate']}%（{bp_['rate']}%）。"
             "转化端没退步，问题在前端接触量。"],
            ["两人整周零记录",
             f"{'、'.join(BUT['missingStaff'])} 一条都没填。空着不等于没问题——"
             "要么补齐记录，要么在对接表注明不参与本周统计。"],
            ["对接到转住院的链条要能追溯",
             "本周只取到对接条数与转住院人数，没有项目结构与权重。"
             "需要管家组长补一张带项目分类的周汇总，否则算不出各项目的转化率。"],
        ],
    }
    return d


# ---------------------------------------------------------------- analytics
def build_analytics():
    a = {}

    # ---- doctor：本周个人口径改用《周排名分析》周排（出院结账），台账作逐日底稿 ----
    _dr = DRK or {}
    _dt_ = _dr.get("totals") or {}
    _drw = _dr.get("rows") or []
    _rev_t = _dt_.get("revenue") or 0
    _top = _drw[0] if _drw else {}
    _top3 = sum(x["revenue"] for x in _drw[:3]) if _drw else 0

    def _wan(v):
        return f"{v / 10000:.2f}"

    def _q(v):
        """去掉小数点后多余的 0：16.75 → 16.75；10.0 → 10。"""
        return (f"{v:.2f}").rstrip("0").rstrip(".")

    def _yuan(v):
        return f"{v:,.0f}" if abs(v - round(v)) < 0.005 else f"{v:,.2f}"

    a["doctor"] = {
        "periods": [f"{x}周" for x in W["labels"]],
        "history": [
            ["营收（万元）", W["doctor"]["rev"], "万"],
            ["门诊人次", W["doctor"]["visits"], "人"],
            ["入院", W["doctor"]["admit"], "人"],
            ["出院", W["doctor"]["discharge"], "人"],
        ],
        "rankBanner": (
            f"<b>本期 {LBL} · 医生周排名（出院结账口径，数据截至 2026-10-25 23:59）</b>："
            f"{len(_drw)} 名医生、出院 <b>{_dt_.get('discharge')}</b> 人、在院 <b>{_dt_.get('inWard')}</b> 人、"
            f"个人业绩合计 <b>{_wan(_rev_t)} 万</b>、本周新入 <b>{_dt_.get('admit')}</b> 人。"
            f"排名指数＝<b>可计分 ÷ 65 × 100</b>＝营业贡献 40（个人业绩 ÷ 组内最高 × 40）"
            f"＋ 工作量 25（出院 10 ＋ 平均出院床日 10 ＋ 在管 5，均按组内最高归一）；"
            f"<b>医疗质量 20 / 时效 10 / 执行协作 5 暂未计入</b>，所以本榜是「可量化工作量排名」，"
            f"<b>不等于绩效总分</b>。"
            f"<b>⚠ 口径不可混：</b>这里是<b>出院结账</b>（15 人结账 {_wan(_rev_t)} 万），"
            f"营收日报是<b>逐日进账</b>（10.19–10.23 共 38.98 万，含门诊），两者分母不同、禁止相加。"
            f"但逐日可勾稽：出院 10.19–10.23 为 4/2/0/2/1＝9 人，与台账逐日完全一致；"
            f"10.24–10.25 再出 6 人、入 4 人，在院 35→<b>{_dt_.get('inWard')}</b>，两张表同一事实、不同切片。"),
        "rankGroups": [
            {"title": f"① 综合排名（本期 {LBL} · 排名指数 100）", "scoreLabel": "排名指数",
             "medals": True,
             "note": ("排名指数越高越靠前。可计分 65 ＝ 营业贡献 40 ＋ 出院 10 ＋ 平均出院床日 10 ＋ 在管 5；"
                      "本周入院人数单列展示、<b>暂不计分</b>。"),
             "rows": [{"name": x["name"],
                       # ⛔ 2026-10-26：这一串原来还带「床日 / 可计分」，在 1280 宽下被挤成
                       #    一字一行（业绩→7.99→万 · 出院…）。细项已在下表②，这里只留三格。
                       "metric": (f"业绩 <b>{_wan(x['revenue'])}</b> 万 · 出院 <b>{x['discharge']}</b> 人"
                                  f" · 在管 <b>{x['inWard']}</b> 人" if x['discharge'] else
                                  f"业绩 <b>{_wan(x['revenue'])}</b> 万 · 本周无出院 · 在管 <b>{x['inWard']}</b> 人"),
                       "score": f"{x['index']:.2f}"} for x in _drw]},
            {"title": f"② 计分明细（本期 {LBL} · 各项按组内最高归一）",
             "scoreLabel": "—", "medals": False,
             "note": ("分数都按「组内最高值＝满分」折算，<b>各项满分不同、不可相加</b>；"
                      "营业贡献 40、出院 10、平均出院床日 10、在管 5。"),
             "table": {
                 "cols": ["医生", "营业贡献 40", "出院 10", "床日 10", "在管 5", "可计分 65", "排名指数"],
                 "rows": [[x["name"], _q(x["scoreRevenue"]), _q(x["scoreDischarge"]),
                           _q(x["scoreBed"]), _q(x["scoreWard"]), _q(x["scoreable"]),
                           f"{x['index']:.2f}"] for x in _drw],
                 "foot": ("平均出院床日按「天数越长分越高」归一（本周王建 17.75 天拿满 10 分）——"
                          "这是现行规则，但与「缩短平均住院日」的管理方向相反，建议下轮改成分段计分。"),
             }},
            {"title": f"③ 业绩构成（本期 {LBL} · 出院结账 · 元）",
             "scoreLabel": "—", "medals": False,
             "note": ("个人总业绩＝该医生本周出院患者的<b>结账收入合计</b>；"
                      "物理治疗与心理业绩是其<b>子集</b>，不能与总业绩相加。"),
             "table": {
                 "cols": ["医生", "个人总业绩", "物理治疗", "心理业绩", "出院", "在管", "本周入院"],
                 "rows": [[x["name"], _yuan(x["revenue"]), _yuan(x["physio"]), _yuan(x["psych"]),
                           str(x["discharge"]), str(x["inWard"]), str(x["admit"])] for x in _drw],
                 "sum": ["合计", _yuan(_rev_t), _yuan(_dt_.get("physio") or 0),
                         _yuan(_dt_.get("psych") or 0), str(_dt_.get("discharge")),
                         str(_dt_.get("inWard")), str(_dt_.get("admit"))],
                 "foot": ("心理业绩＝心理咨询费 ＋ 心理治疗费。本周全组物理治疗 "
                          f"{_yuan(_dt_.get('physio') or 0)} 元、心理 {_yuan(_dt_.get('psych') or 0)} 元，"
                          "分别占个人业绩合计的 "
                          f"{(_dt_.get('physio') or 0) / _rev_t * 100:.1f}% / "
                          f"{(_dt_.get('psych') or 0) / _rev_t * 100:.1f}%。"),
             }},
        ],
        "diagnosis": [
            [f"本周结果（{LBL} · 出院结账口径）",
             f"出院 <b>{_dt_.get('discharge')}</b> 人、在院 <b>{_dt_.get('inWard')}</b> 人、"
             f"个人业绩合计 <b>{_wan(_rev_t)}</b> 万、本周新入 <b>{_dt_.get('admit')}</b> 人。"
             f"{_top.get('name', '—')} 以 {_wan(_top.get('revenue', 0))} 万居首"
             f"（占全组 {_top.get('revenue', 0) / _rev_t * 100:.1f}%），"
             f"前三名合计 {_wan(_top3)} 万、占 <b>{_top3 / _rev_t * 100:.1f}%</b>——"
             f"业绩集中度偏高，前两名之外的医生业绩差距明显。"],
            ["与营收日报逐日勾稽通过",
             "两张表不是同一口径，但可以逐日对上：10.19–10.23 出院为 4/2/0/2/1＝9 人，"
             "与营收日报台账完全一致；10.24–10.25 再出 6 人、再入 4 人，"
             f"在院由 35 人降至 <b>{_dt_.get('inWard')}</b> 人。"
             "→ 周排名表是把逐日台账「按医生拆开并延长到 10.25」，不是另一套数。"],
            ["排名口径的边界（务必按此读表）",
             "① <b>医疗质量 20 / 时效 10 / 执行协作 5 未计入</b>，65 分只是可量化工作量，"
             "不能直接当绩效总分或用它发奖金。"
             "② 平均出院床日按「越长分越高」归一，与缩短平均住院日的目标方向相反。"
             f"③ {_drw[-1]['name'] if _drw else '—'} 业绩为 0 不是没干活——"
             f"{_drw[-1]['name'] if _drw else '—'}本周新入 {_drw[-1]['admit'] if _drw else 0} 人、"
             f"在管 {_drw[-1]['inWard'] if _drw else 0} 人，患者尚未出院结账，"
             "结账口径下自然为 0，需结合在管人数一起看。"],
        ],
    }

    # ---- nursing ----
    a["nursing"] = {
        "periods": ["10.11考核周", "10.19本周"],
        "history": [["六项治疗完成率", [93, None], "%"]],
        "rankBanner": (f"<b>本周（{LBL}）护理部未提交，排名暂停。</b>"
                       f"周报与物理治疗逐日表最新只到 {DEP['nursing'].get('weeklyThrough') or '—'}，"
                       f"本周窗口内 0 条护理事实。<b>不拿上一考核周的名次、"
                       f"也不拿 93% 的完成率顶替本周</b>——缺报期间任何排名都会误导派班。"),
        "rankGroups": [{
            "title": "① 本周无数据 · 排名不计", "scoreLabel": "—", "medals": False,
            "note": ("护理考核四张 sheet（归一化工作量 / 百分制考核分 / 每日质控 / 综合排名）"
                     "仍停在同一考核周。等护理部补报 10.19—10.24 的逐日表与六项应做/实做后，"
                     "本块由管线自动重算。"),
            "rows": [],
        }],
        "diagnosis": [
            ["本周护理无数据",
             f"周报与逐日表停在 {DEP['nursing'].get('weeklyThrough') or '—'}，"
             f"{LBL} 内 0 条事实。六项完成率、物理治疗人数、工娱全部记 null。"],
            ["为什么不能用上一期顶替",
             "护理是周口径（应做 / 实做按周报送），上一期的 93% 是那一周的治疗量。"
             "把它当本周完成率，会让派班和绩效都算错。"],
            ["补报后才恢复计算",
             "补报到位后，六项完成率、物理治疗人数、组内排名会由同一套管线自动填回，"
             "不需要手工改页面。"],
        ],
    }

    # ---- psychology ----
    plab, pcon = trim([x for x in W["psych"]["contact"]])
    _, pcs = trim([x for x in W["psych"]["consult"]])
    prank = PSY.get("rank") or []
    plab = [f"{x}周" for x in plab]
    a["psychology"] = {
        "periods": plab,
        "history": [["患者接触", pcon, "人次"], ["咨询工作量", pcs, "人次"]],
        "rankBanner": (f"<b>本期 {LBL} · V4 管理表逐条（数据至 {SNAP['watermarks']['psych']['dataThrough']}）</b>："
                       f"{len(prank)} 人填报，咨询合计 <b>{PSY['week']['consult']}</b> 人次、"
                       f"接触 <b>{PSY['week']['contact']}</b> 人次。"
                       f"综合分＝<b>0.667×（咨询 ÷ 组内最大）＋ 0.333×（接触 ÷ 组内最大）</b>，"
                       f"咨询权重是接触的 2 倍（业主 2026-09-27 定，沿用）。"
                       f"<b>组长不参与排名</b>，其工作量单列。"),
        "rankGroups": [
            {"title": f"① 综合排名（本期 {LBL} · 咨询 : 接触 ＝ 2 : 1）", "scoreLabel": "综合分",
             "medals": True,
             "note": ("综合分越高越靠前。<b>填报天数与在岗天数不计分、不参与并列判定</b>；"
                      "组长单列、不进本榜。"),
             "rows": [{"name": x["name"],
                       "metric": f"咨询 <b>{x['consult']}</b>（住院 {x['inpatient']} / 门诊 {x['outpatient']} / "
                                 f"家庭 {x['family']}）· 接触 <b>{x['contact']}</b>"
                                 f"（首次 {x['first']} / 情绪 {x['emotion']}）"
                                 f"　完整率 {x['rate'] if x['rate'] is not None else '—'}%",
                       "score": str(x["score"])} for x in prank]},
            {"title": f"② 咨询工作量（本期 {LBL}）", "scoreLabel": "咨询", "medals": True,
             "note": "口径＝住院咨询 ＋ 门诊咨询 ＋ 家庭咨询。",
             "rows": [{"name": x["name"],
                       "metric": f"住院 {x['inpatient']} / 门诊 {x['outpatient']} / 家庭 {x['family']}",
                       "score": str(x["consult"])} for x in
                      sorted(prank, key=lambda y: -y["consult"])]},
            {"title": f"③ 患者接触（本期 {LBL}）", "scoreLabel": "接触", "medals": True,
             "note": "口径＝24h 首次对接 ＋ 情绪支持 ＋ 住院咨询。<b>接触人次与咨询人次不可相加</b>。",
             "rows": [{"name": x["name"],
                       "metric": f"首次 {x['first']} / 情绪 {x['emotion']} / 住院 {x['inpatient']}",
                       "score": str(x["contact"])} for x in
                      sorted(prank, key=lambda y: -y["contact"])]},
        ],
        "diagnosis": [
            ["本周结果", f"咨询 <b>{PSY['week']['consult']}</b> 人次、接触 <b>{PSY['week']['contact']}</b> 人次、"
                         f"家长访谈 <b>{PSY['week']['parent']}</b> 人次、团体 <b>{PSY['week']['groupSessions']}</b> 场；"
                         f"上期同天数 咨询 {PSY['prevSameDays']['consult']} / 接触 {PSY['prevSameDays']['contact']}。"],
            ["日报填报是短板", f"本周只有 <b>{PSY['week']['report']}</b> 条日报。完整率按表内公式算，"
                              "不等于「有日报的天数」；周表汇总状态仍普遍「有待补」。"],
            ["表头停用", f"汇报表心理组表头停在 {PSY.get('headerAsOf')}，未滚动，已停用；本周只用 V4。"],
        ],
    }

    # ---- service ----
    slab, sfol = trim(W["service"]["followup"])
    _, sarr = trim(W["service"]["arrived"])
    slab = [f"{x}周" for x in slab]
    s_staff = SVC.get("staff") or []
    a["service"] = {
        "periods": slab,
        "history": [["回访条数", sfol, "条"], ["标注到院", sarr, "人"]],
        "rankBanner": (f"<b>本期 {LBL} · 三张台账（数据至 {SNAP['watermarks']['service']['dataThrough']}，"
                       f"{SNAP['watermarks']['service']['days']} 天）</b>：回访 <b>{SVC['week']['followup']}</b> 条、"
                       f"标注到院 <b>{SVC['week']['arrived']}</b> 人（<b>{SVC['week']['rate']}%</b>）、"
                       f"主动服务 <b>{SVC['week']['guide']}</b> 条、日工作量 <b>{SVC['week']['workload']:,}</b> 分。"),
        "rankGroups": [
            {"title": f"① 导医回访（本期 {LBL} · 标准化回访台账）", "scoreLabel": "条数", "medals": True,
             "note": ("逐条台账按人计数。<b>本周只有一人有记录</b>——其余导医 0 条，"
                      "是排班还是漏填，需要组长确认；0 条不参与排名、也不降榜。"),
             "rows": [{"name": k,
                       "metric": f"回访 {v} 条 · 标注到院 {SVC.get('staffArrived', {}).get(k, 0)} 人"
                                 f"（{round(SVC.get('staffArrived', {}).get(k, 0) / max(1, v) * 100)}%）",
                       "score": str(v)} for k, v in s_staff]},
        ],
        "diagnosis": [
            ["本周结果", f"回访 <b>{SVC['week']['followup']}</b> 条（上期同天数 {SVC['prevSameDays']['followup']}）、"
                         f"到院 <b>{SVC['week']['arrived']}</b> 人（{SVC['week']['rate']}%，"
                         f"上期 {SVC['prevSameDays']['rate']}%）。"],
            ["一人承担全部回访", "台账逐人只有一人有记录，排名失去比较意义。先解决填报覆盖，再谈排名。"],
            ["率值样本太小", f"只有 {SVC['week']['followup']} 条回访，率值上下 1 条就跳 "
                            f"{round(100 / max(1, SVC['week']['followup']), 1)}pt，不宜单独考核。"],
        ],
    }

    # ---- marketing ----
    blab, bcon = trim(W["butler"]["contact"])
    _, badm = trim(W["butler"]["admit"])
    blab = [f"{x}周" for x in blab]
    a["marketing"] = {
        "periods": blab,
        "history": [["有效对接", bcon, "条"], ["转住院", badm, "人"]],
        "rankBanner": (f"<b>本期 {LBL} · 各管家对接表（数据至 {SNAP['watermarks']['butler']['dataThrough']}，"
                       f"{SNAP['watermarks']['butler']['days']} 天）</b>：有效对接 <b>{BUT['week']['contact']}</b> 条、"
                       f"转住院 <b>{BUT['week']['admit']}</b> 人（<b>{BUT['week']['rate']}%</b>）。"
                       f"<b>{'、'.join(BUT['missingStaff'])} 本周无记录</b>，记 null、不按 0 降榜。"),
        "rankGroups": [
            {"title": f"① 管家个人对接（本期 {LBL}）", "scoreLabel": "条数", "medals": True,
             "note": ("按各管家分表逐条计数。<b>零记录的管家不进榜、也不记 0</b>——"
                      "「没上班」和「上班没产出」是两件事，不能混。"),
             "rows": [{"name": k, "metric": "本周有效对接", "score": str(v)} for k, v in BUT["staff"]]},
        ],
        "diagnosis": [
            ["本周结果", f"对接 <b>{BUT['week']['contact']}</b> 条（上期同天数 {BUT['prevSameDays']['contact']}）、"
                         f"转住院 <b>{BUT['week']['admit']}</b> 人、率值 <b>{BUT['week']['rate']}%</b>"
                         f"（上期 {BUT['prevSameDays']['rate']}%）。"],
            ["两人零记录", f"{'、'.join(BUT['missingStaff'])} 整周空白，需组长确认原因；本周不参与排名、不降榜。"],
            ["项目结构缺失", "本周只拿到条数与转住院，没有项目分类与权重，算不出各项目转化率，需补周汇总。"],
        ],
    }
    return a


# ---------------------------------------------------------------- signals
def build_signals():
    return [
        {"level": "", "title": f"营收 {M['weekRevenue']['value']} 万、门诊 {M['weekVisits']['value']} 人次，"
                               f"按 {M['weekRevenue']['days']} 天口径同比 {sp(M['weekRevenue']['deltaPct'])}",
         "sub": "医生组 × 财务",
         "value": sp(M["weekRevenue"]["deltaPct"]),
         "body": (f"营收日报逐日台账（{P['start'][5:]}—{DT}，{N} 天）：营收 "
                  f"<span class=\"hl-key\">{M['weekRevenue']['value']} 万</span>"
                  f"（门诊 {M['weekOutpatient']['value']} ＋ 在院 {M['weekInpatient']['value']}）、"
                  f"门诊 <span class=\"hl-key\">{M['weekVisits']['value']} 人次</span>、"
                  f"入 {M['weekAdmit']['value']} / 出 {M['weekDischarge']['value']}。"
                  f"上期取同一窗口长度（{N} 天）{DEP['compareWeek']['revenueWan']} 万，"
                  f"<span class=\"changed-good\">{sp(M['weekRevenue']['deltaPct'])}</span>。"
                  f"⚠ 与汇报表表头不同源——那张表本周整表未滚动，已停用。"),
         "action": "把门诊 / 在院收入的日波动图挂到医生组抽屉，逐日盯住掉速的那一天。",
         "owners": ["医生组", "财务"]},
        {"level": "risk", "title": f"护理部本周整块缺报，六项完成率与物理治疗人数全部留空",
         "sub": "护理组",
         "value": "未提交",
         "body": (f"周报与物理治疗逐日表最新只到 "
                  f"<span class=\"hl-key\">{DEP['nursing'].get('weeklyThrough') or '—'}</span>，"
                  f"{LBL} 内 0 条护理事实。三项目前<span class=\"changed-bad\">全部记 null</span>："
                  f"六项治疗完成率、物理治疗人数、工娱场次。"
                  f"按契约不拿上一期数字顶替——缺报期间任何环比、排名、绩效都会算错。"),
         "action": "护理部补报 10.19—10.24 六项应做/实做、物理治疗人数、工娱场次；补完由管线自动填回。",
         "owners": ["护理组", "运营"]},
        {"level": "", "title": f"心理 咨询 {PSY['week']['consult']} 人次、接触 {PSY['week']['contact']} 人次，"
                               f"工作量集中在 1 人",
         "sub": "心理咨询组",
         "value": f"{PSY['week']['consult']} 人次",
         "body": (f"V4 管理表逐条（数据至 {SNAP['watermarks']['psych']['dataThrough']}）：咨询 "
                  f"<span class=\"hl-key\">{PSY['week']['consult']}</span> 人次"
                  f"（住院 {PSY['week']['inpatient']} ＋ 门诊 {PSY['week']['outpatient']} ＋ "
                  f"家庭 {PSY['week']['family']}）、接触 "
                  f"<span class=\"hl-key\">{PSY['week']['contact']}</span> 人次、"
                  f"家长访谈 {PSY['week']['parent']}、团体 {PSY['week']['groupSessions']} 场。"
                  f"咨询量第一的咨询师占全组 "
                  f"<span class=\"changed-key\">"
                  f"{round((PSY['rank'][0]['consult'] if PSY.get('rank') else 0) / max(1, PSY['week']['consult']) * 100)}%</span>。"
                  f"但本周只填了 {PSY['week']['report']} 条日报。"),
         "action": "把日报改成当班即填；同时确认工作量第一的咨询师是否有备班。",
         "owners": ["心理咨询组", "运营"]},
        {"level": "", "title": f"客服回访 {SVC['week']['followup']} 条、到院率 {SVC['week']['rate']}%，"
                               f"回访全部压在 1 人身上",
         "sub": "客服服务部",
         "value": f"{SVC['week']['rate']}%",
         "body": (f"三张台账（数据至 {SNAP['watermarks']['service']['dataThrough']}，"
                  f"{SNAP['watermarks']['service']['days']} 天）：回访 "
                  f"<span class=\"hl-key\">{SVC['week']['followup']} 条</span>、标注到院 "
                  f"<span class=\"hl-key\">{SVC['week']['arrived']} 人</span>"
                  f"（<span class=\"changed-good\">{SVC['week']['rate']}%</span>，"
                  f"上期同天数 {SVC['prevSameDays']['rate']}%）、主动服务 {SVC['week']['guide']} 条、"
                  f"日工作量 {SVC['week']['workload']:,} 分。"
                  f"⚠ 台账逐人只有 "
                  f"{'、'.join(k for k, _ in (SVC.get('staff') or [])) or '—'} 有记录，其余 0 条。"),
         "action": "确认其余导医是排班不出勤还是漏填；同时把「当班即录」写进台账规范。",
         "owners": ["客服服务部"]},
        {"level": "", "title": f"管家对接 {BUT['week']['contact']} 条、转住院 {BUT['week']['admit']} 人"
                               f"（{BUT['week']['rate']}%），两人整周零记录",
         "sub": "营销中心",
         "value": f"{BUT['week']['rate']}%",
         "body": (f"各管家分表逐条（数据至 {SNAP['watermarks']['butler']['dataThrough']}，"
                  f"{SNAP['watermarks']['butler']['days']} 天）：对接 "
                  f"<span class=\"hl-key\">{BUT['week']['contact']} 条</span>、转住院 "
                  f"<span class=\"hl-key\">{BUT['week']['admit']} 人</span>。"
                  f"逐人 {'、'.join(f'{k} {v}' for k, v in BUT['staff'])}。"
                  f"<span class=\"changed-bad\">{'、'.join(BUT['missingStaff'])} 零记录</span>，"
                  f"按契约记 null、不按 0 降榜。营销中心表头三项本周整行空白。"),
         "action": "让管家组长补齐两人记录或注明不参与统计；补一张带项目分类的周汇总。",
         "owners": ["营销中心"]},
    ]


# ---------------------------------------------------------------- tasks
def build_tasks():
    return [
        {"id": "nursing-report", "title": "护理部补报 10.19—10.24 数据",
         "owner": "护理组、运营", "deadline": "本周五前",
         "deliver": "① 六项治疗应做/实做逐日数；② 物理治疗人数（住院＋门诊）；③ 工娱场次与参与人数。"
                    "三项是本周唯一整块空白，补齐后六项完成率、组内排名、绩效才能重算。"},
        {"id": "action-report", "title": "推动《特别行动小组汇报表》按周滚动",
         "owner": "运营、各部门",
         "deadline": "本周内",
         "deliver": "五个部门表头本周整表未滚动（值等于正文「第 3 周」列）。已全部停用、改为明细表口径，"
                    "但这只是绕行；需要让填报人按周切换表头，否则每周都要手工判断哪些数可信。"},
        {"id": "physio-ledger", "title": "财务补一张按日拆分的物理治疗收入表",
         "owner": "财务、医生组", "deadline": "本周内",
         "deliver": "物理治疗费目前既没有逐日台账、汇报表表头又不可用，是医生组六个核心指标里唯一拿不到数的。"
                    "按日拆分后并入营收日报，就能与护理组的治疗人次勾稽。"},
        {"id": "ledger-discipline", "title": "客服 / 管家台账改为当班即录",
         "owner": "客服服务部、营销中心", "deadline": "下周一",
         "deliver": "客服回访全部压在 1 人身上、管家 2 人整周零记录，说明台账是「想起来才补」。"
                    "改为当班即录后，到院率与转化率才有意义，排名也才不会变成「谁填表谁上榜」。"},
        {"id": "month-target", "title": "确认 10 月目标是否仍按 260 万",
         "owner": "运营、医生组", "deadline": "本周内",
         "deliver": f"当前累计 {M['monthRevenue']['value']} 万、完成 {M['monthRevenue']['amountProgress']}%，"
                    f"时间进度 {M['monthRevenue']['timeProgress']}%。目标沿用 9 月定下的 260 万，"
                    f"未按 10 月实际排班重设——需要业主确认是否调整。"},
    ]


# ---------------------------------------------------------------- 写回
def replace_const(html, name, literal):
    head = f"const {name}="
    i = html.find(head)
    if i < 0:
        print(f"  ⚠ 未找到 {head}")
        return html
    k = i + len(head)
    while html[k] not in "{[":
        k += 1
    ob, cb = ("{", "}") if html[k] == "{" else ("[", "]")
    d, e = 0, k
    while e < len(html):
        ch = html[e]
        if ch == "'":
            e += 1
            while e < len(html):
                if html[e] == "\\":
                    e += 2
                    continue
                if html[e] == "'":
                    break
                e += 1
        elif ch == '"':
            e += 1
            while e < len(html):
                if html[e] == "\\":
                    e += 2
                    continue
                if html[e] == '"':
                    break
                e += 1
        elif ch == ob:
            d += 1
        elif ch == cb:
            d -= 1
            if d == 0:
                break
        e += 1
    return html[:k] + literal + html[e + 1:]


def main():
    dry = "--dry-run" in sys.argv
    html = open(HTML, encoding="utf-8").read()
    orig = len(html)

    blocks = [
        ("departments", js(build_departments())),
        ("analytics", js(build_analytics())),
        ("signals", js(build_signals())),
        ("tasks", js(build_tasks())),
        ("periods", js([f"{x}周" for x in W["labels"]])),
    ]
    for name, lit in blocks:
        before = len(html)
        html = replace_const(html, name, lit)
        print(f"  {name}: {before} → {len(html)}")

    if dry:
        print(f"dry-run：{orig} → {len(html)}（{len(html) - orig:+d}）")
        return
    open(HTML, "w", encoding="utf-8").write(html)
    print(f"index.html 已重写：{orig} → {len(html)}（{len(html) - orig:+d}）")


if __name__ == "__main__":
    main()
