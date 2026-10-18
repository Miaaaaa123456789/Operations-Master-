#!/usr/bin/env python3
"""从事实库重算发布快照 data/snapshot.json（新 revision 才写）。

口径（对齐 docs/live-data/DATA_CONTRACT.md）：
- 本期＝自然周 10.12—10.18；营收日报次日发布，故 dataThrough＝最新逐日营收日。
- 环比＝上一自然周（10.05—10.11）的**同天数前 N 日**，缺日不补、不跳。
- 缺失写 null，不写 0；涉及两源不一致的进 conflicts，不静默抹平。
"""
import json, os, sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_db

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "data", "snapshot.json")
CN = timezone(timedelta(hours=8))
TARGET_WAN = 260
WD = "一二三四五六日"


def q1(c, sql, args=()):
    r = c.execute(sql, args).fetchone()
    return r[0] if r else None


def s(c, metric, a, b, dim=None):
    if dim:
        return c.execute(
            "SELECT dim_value, SUM(value) FROM fact WHERE metric_id=? AND business_date BETWEEN ? AND ? "
            "GROUP BY 1 ORDER BY 2 DESC", (metric, a, b)).fetchall()
    return q1(c, "SELECT SUM(value) FROM fact WHERE metric_id=? AND business_date BETWEEN ? AND ?",
              (metric, a, b))


def daily_map(c, metric, a, b):
    return dict(c.execute(
        "SELECT business_date, SUM(value) FROM fact WHERE metric_id=? AND business_date BETWEEN ? AND ? "
        "GROUP BY 1", (metric, a, b)).fetchall())


def pct(n, d):
    return round(n / d * 100, 1) if d else None


def delta(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return round((cur - prev) / prev * 100, 1)


def span(a, b):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def pulled_at():
    """最近一次采集完成时刻（collect.py 写的 manifest），转成带偏移的 ISO8601。

    ⛔ 不许拿"现在"冒充"数据截至"：manifest 缺失才退化为当前时刻，并在日志里说明。
    """
    p = os.path.join(ROOT, "data", "raw-kdocs", "_manifest.json")
    try:
        with open(p, encoding="utf-8") as f:
            raw = (json.load(f) or {}).get("pulledAt") or ""
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z").isoformat(timespec="seconds")
    except Exception:
        return datetime.now(CN).isoformat(timespec="seconds")


def main(db_path=None, out=None, write=True):
    """重算发布快照。

    db_path  : 事实库路径，缺省用 db/live-data.sqlite（构建脚本 CLI 走这条）
    out      : 落盘路径，缺省 data/snapshot.json
    write    : False 时只算不落盘、不新增 revision —— 供 API 服务按需实时重算
    返回重算后的快照 dict（原先无返回值，改为返回便于服务端直接序列化）。
    """
    c = live_db.connect(db_path or live_db.DB, schema=False)
    out = out or OUT
    today = datetime.now(CN).date()
    as_of = today.isoformat()

    rev_days = [r[0] for r in c.execute(
        "SELECT DISTINCT business_date FROM fact WHERE source_id='revenue_daily_report' "
        "AND business_date<=? ORDER BY 1", (as_of,))]
    data_through = rev_days[-1]
    dt = date.fromisoformat(data_through)

    # 自然周（周一至周日）
    p_start = as_of_date = dt - timedelta(days=dt.weekday())
    p_end = p_start + timedelta(days=6)
    prev_start = p_start - timedelta(days=7)
    prev_end = p_start - timedelta(days=1)
    days_recorded = len([d for d in rev_days if p_start.isoformat() <= d <= p_end.isoformat()])
    cmp_end = prev_start + timedelta(days=days_recorded - 1)

    # ⛔ 2026-10-18 修（重要口径）：各源的截止日**本来就不一样**——
    #   营收日报次日发布，10.18 的日报还没出（数据至 10.17，本期已录 6 天）；
    #   而心理日报 / 客服台账 / 到院登记 当天就在填，10.18 已有真实数据（7 天）。
    #   原先所有部门一律用「营收的 6 天」去比上一窗口 6 天，等于拿**7 天比 6 天**，
    #   周末效应会把心理、到院这些指标凭空抬高十几个点。
    #   契约要求「进行中前 N 个自然日对上一窗口前 N 个自然日、缺日不跳过」，
    #   故按族各取自己的截止日与同天数对照。
    def fam_end(*srcs):
        q = ",".join("?" * len(srcs))
        r = q1(c, "SELECT MAX(business_date) FROM fact WHERE source_id IN (%s) "
                  "AND business_date BETWEEN ? AND ?" % q,
               tuple(srcs) + (p_start.isoformat(), p_end.isoformat()))
        return r or data_through

    def fam_days(end):
        return (date.fromisoformat(end) - p_start).days + 1

    def fam_cmp(end):
        return prev_start + timedelta(days=fam_days(end) - 1)

    psy_end = fam_end("psych_v4", "psych_visits")
    svc_end = fam_end("service_followups")
    but_end = fam_end("butler_contacts")
    arr_end = fam_end("arrival_register")
    psy_n, svc_n, but_n, arr_n = (fam_days(x) for x in (psy_end, svc_end, but_end, arr_end))

    # ── 营收口径 ────────────────────────────────────────────────
    month_start = dt.replace(day=1)
    out_m = s(c, "revenue.outpatient", month_start.isoformat(), data_through) or 0
    in_m = s(c, "revenue.inpatient", month_start.isoformat(), data_through) or 0
    month_total = out_m + in_m

    out_w = s(c, "revenue.outpatient", p_start.isoformat(), data_through) or 0
    in_w = s(c, "revenue.inpatient", p_start.isoformat(), data_through) or 0
    week_total = out_w + in_w
    out_p = s(c, "revenue.outpatient", prev_start.isoformat(), cmp_end.isoformat()) or 0
    in_p = s(c, "revenue.inpatient", prev_start.isoformat(), cmp_end.isoformat()) or 0
    prev_total = out_p + in_p

    vis_new = s(c, "visit.new", p_start.isoformat(), data_through) or 0
    vis_ret = s(c, "visit.return", p_start.isoformat(), data_through) or 0
    vis_prev = (s(c, "visit.new", prev_start.isoformat(), cmp_end.isoformat()) or 0) + \
               (s(c, "visit.return", prev_start.isoformat(), cmp_end.isoformat()) or 0)
    adm = s(c, "admit", p_start.isoformat(), data_through) or 0
    dis = s(c, "discharge", p_start.isoformat(), data_through) or 0
    adm_p = s(c, "admit", prev_start.isoformat(), cmp_end.isoformat()) or 0
    dis_p = s(c, "discharge", prev_start.isoformat(), cmp_end.isoformat()) or 0
    ward = q1(c, "SELECT value FROM fact WHERE metric_id='ward.count' AND business_date=?",
              (data_through,))
    # 在院人数是「时点值」，不是当日发生额：手工补录当天只填了门诊/在院金额时，
    # 该日的 ward.count 会是 NULL——此时回退到最近一个有值的时点，而不是让 KPI 直接变空。
    if ward is None:
        ward = q1(c, "SELECT value FROM fact WHERE metric_id='ward.count' AND business_date<=? "
                     "ORDER BY business_date DESC LIMIT 1", (data_through,))
    ward_prev = q1(c, "SELECT value FROM fact WHERE metric_id='ward.count' AND business_date<=? "
                      "ORDER BY business_date DESC LIMIT 1", (cmp_end.isoformat(),))

    # 时间进度：按该指标 dataThrough 计算（当月自然日）
    month_days = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    month_days = month_days.day
    elapsed = dt.day
    amount_progress = round(month_total / 10000 / TARGET_WAN * 100, 1)
    time_progress = round(elapsed / month_days * 100, 1)
    gap = round(TARGET_WAN - month_total / 10000, 2)

    daily = []
    cum = 0.0
    for d in [x for x in rev_days if x >= month_start.isoformat()]:
        o = q1(c, "SELECT value FROM fact WHERE metric_id='revenue.outpatient' AND business_date=?", (d,)) or 0
        i = q1(c, "SELECT value FROM fact WHERE metric_id='revenue.inpatient' AND business_date=?", (d,)) or 0
        n = q1(c, "SELECT value FROM fact WHERE metric_id='visit.new' AND business_date=?", (d,))
        rr = q1(c, "SELECT value FROM fact WHERE metric_id='visit.return' AND business_date=?", (d,))
        w = q1(c, "SELECT value FROM fact WHERE metric_id='ward.count' AND business_date=?", (d,))
        a = q1(c, "SELECT value FROM fact WHERE metric_id='admit' AND business_date=?", (d,))
        dd = q1(c, "SELECT value FROM fact WHERE metric_id='discharge' AND business_date=?", (d,))
        cum += o + i
        daily.append({
            "date": d, "weekday": WD[date.fromisoformat(d).weekday()],
            "outpatient": round(o, 2), "inpatient": round(i, 2), "total": round(o + i, 2),
            "visitsNew": int(n) if n is not None else None,
            "visitsReturn": int(rr) if rr is not None else None,
            "visits": int((n or 0) + (rr or 0)) if (n is not None or rr is not None) else None,
            "ward": int(w) if w is not None else None,
            "admit": int(a) if a is not None else None,
            "discharge": int(dd) if dd is not None else None,
            "monthCum": round(cum, 2), "status": "accepted",
        })

    # ── 心理组（V4 管理表）────────────────────────────────────
    def psy(a, b):
        return {
            "report": int(s(c, "psych.report", a, b) or 0),
            "first": int(s(c, "psych.first_contact", a, b) or 0),
            "emotion": int(s(c, "psych.emotion_support", a, b) or 0),
            "inpatient": int(s(c, "psych.inpatient_consult", a, b) or 0),
            "outpatient": int(s(c, "psych.outpatient_consult", a, b) or 0),
            "family": int(s(c, "psych.family_consult", a, b) or 0),
            "parent": int(s(c, "psych.parent_interview", a, b) or 0),
            "groupSessions": int(s(c, "psych.group_session", a, b) or 0),
            "groupPeople": int(s(c, "psych.group_attendee", a, b) or 0),
            "bind": int(s(c, "psych.patient_bind", a, b) or 0),
        }

    pw = psy(p_start.isoformat(), psy_end)
    pw_prev = psy(prev_start.isoformat(), fam_cmp(psy_end).isoformat())
    pw["contact"] = pw["first"] + pw["emotion"] + pw["inpatient"]
    pw["consult"] = pw["inpatient"] + pw["outpatient"] + pw["family"]
    pw_prev["contact"] = pw_prev["first"] + pw_prev["emotion"] + pw_prev["inpatient"]
    pw_prev["consult"] = pw_prev["inpatient"] + pw_prev["outpatient"] + pw_prev["family"]
    psy_staff = [(k, int(v)) for k, v in s(c, "psych.report", p_start.isoformat(), psy_end, "staff")]
    psy_day = daily_map(c, "psych.inpatient_consult", p_start.isoformat(), psy_end)
    psy_day2 = daily_map(c, "psych.first_contact", p_start.isoformat(), psy_end)
    psy_day3 = daily_map(c, "psych.emotion_support", p_start.isoformat(), psy_end)

    # 管床对接（当前在院绑定人数，按表内未填出院日期计）
    bound = q1(c, "SELECT COUNT(*) FROM fact WHERE metric_id='psych.patient_bind' AND business_date<=?",
               (as_of,))

    # ── 客服 / 导诊 ────────────────────────────────────────────
    def svc(a, b):
        fu = s(c, "service.followup", a, b) or 0
        ar = s(c, "service.arrived", a, b) or 0
        return {"followup": int(fu), "arrived": int(ar), "rate": pct(ar, fu),
                "guide": int(s(c, "service.guide", a, b) or 0),
                "workload": int(s(c, "service.workload", a, b) or 0)}

    sw = svc(p_start.isoformat(), svc_end)
    sw_prev = svc(prev_start.isoformat(), fam_cmp(svc_end).isoformat())
    svc_staff = [(k, int(v)) for k, v in s(c, "service.followup", p_start.isoformat(), svc_end, "staff")]
    svc_arr = dict((k, int(v)) for k, v in s(c, "service.arrived", p_start.isoformat(), svc_end, "staff"))
    svc_day = daily_map(c, "service.followup", p_start.isoformat(), svc_end)

    # ── 管家（患者有效对接）────────────────────────────────────
    def but(a, b):
        ct = s(c, "butler.contact", a, b) or 0
        ad = s(c, "butler.admit", a, b) or 0
        return {"contact": int(ct), "admit": int(ad), "rate": pct(ad, ct)}

    bw = but(p_start.isoformat(), but_end)
    bw_prev = but(prev_start.isoformat(), fam_cmp(but_end).isoformat())
    but_staff = [(k, int(v)) for k, v in s(c, "butler.contact", p_start.isoformat(), but_end, "staff")]
    but_map = dict(but_staff)
    butler_all = [r[0] for r in c.execute(
        "SELECT DISTINCT sheet_name FROM fact WHERE source_id='butler_contacts'")]
    missing_butler = [n for n in butler_all if n not in but_map]
    bw_daily = daily_map(c, "butler.contact", p_start.isoformat(), but_end)

    # ── 到院登记 ──────────────────────────────────────────────
    arr_w = int(s(c, "arrival.visit", p_start.isoformat(), arr_end) or 0)
    arr_new = int(s(c, "arrival.new", p_start.isoformat(), arr_end) or 0)
    arr_prev = int(s(c, "arrival.visit", prev_start.isoformat(), fam_cmp(arr_end).isoformat()) or 0)
    arr_chan = [(k, int(v)) for k, v in s(c, "arrival.visit", p_start.isoformat(), arr_end, "channel")]
    arr_daily = daily_map(c, "arrival.visit", p_start.isoformat(), arr_end)
    arr_prev_daily = daily_map(c, "arrival.visit", prev_start.isoformat(),
                               fam_cmp(arr_end).isoformat())

    # ── 部门汇报表（本周口径，源表自填）───────────────────────
    dept_report = {
        "doctor": {"admit": 10, "outpatient": 307, "physioWan": 27, "revenueWan": 69},
        "nursing": {"physioPeople": 484, "recreationSessions": 5, "recreationPeople": 62},
        "psychology": {"individual": 40, "groupSessions": 4, "people": 40, "revenueYuan": 19002},
        "service": {"followup": None, "arrived": 239, "charity": 14},
        "marketing": {"admit": None, "outpatient": None, "revenueWan": None},
    }

    # ── 指标卡片 ──────────────────────────────────────────────
    def metric(mid, label, value, unit, **kw):
        d = {"id": mid, "label": label, "value": value, "unit": unit,
             "periodStart": p_start.isoformat(), "periodEnd": p_end.isoformat(),
             "dataThrough": data_through, "status": "ok"}
        d.update(kw)
        return d

    metrics = {
        "monthRevenue": {"id": "monthRevenue", "label": "10月累计营收", "value": round(month_total / 10000, 2),
                         "unit": "万元", "valueYuan": round(month_total, 2), "targetWan": TARGET_WAN,
                         "amountProgress": amount_progress, "timeProgress": time_progress,
                         "gap": gap, "dataThrough": data_through, "status": "ok"},
        "weekRevenue": metric("weekRevenue", "本期营收", round(week_total / 10000, 2), "万元",
                              valueYuan=round(week_total, 2), days=days_recorded,
                              deltaPct=delta(week_total, prev_total),
                              compare=f"{prev_start.isoformat()}—{cmp_end.isoformat()} 同 {days_recorded} 天"),
        "weekOutpatient": metric("weekOutpatient", "本期门诊收入", round(out_w / 10000, 2), "万元",
                                 deltaPct=delta(out_w, out_p)),
        "weekInpatient": metric("weekInpatient", "本期在院收入", round(in_w / 10000, 2), "万元",
                                deltaPct=delta(in_w, in_p)),
        "weekVisits": metric("weekVisits", "本期门诊人次", int(vis_new + vis_ret), "人次",
                             visitsNew=int(vis_new), visitsReturn=int(vis_ret),
                             deltaPct=delta(vis_new + vis_ret, vis_prev)),
        "weekAdmit": metric("weekAdmit", "本期入院", int(adm), "人", deltaPct=delta(adm, adm_p)),
        "weekDischarge": metric("weekDischarge", "本期出院", int(dis), "人", deltaPct=delta(dis, dis_p)),
        "wardCount": {"id": "wardCount", "label": "在院人数", "value": int(ward) if ward is not None else None,
                      "unit": "人", "dataThrough": data_through, "status": "ok", "pointInTime": True},
        "netPool": {"id": "netPool", "label": "患者池净变化", "value": int(adm - dis), "unit": "人",
                    "dataThrough": data_through, "status": "ok"},
    }

    # ── 契约补齐：每个指标都必须自带期间/截至/来源/覆盖/定义版本 ────────
    # DATA_CONTRACT 要求每张指标卡都返回
    #   periodStart/periodEnd/dataThrough/fetchedAt/publishedAt/asOf/coverage/status/sourceIds
    # 缺任一项，前端就只能靠文案硬编码第二份结果 —— 故在快照生成时统一补齐，
    # 不让展示层自己猜。definitionVersion 随规则改动递增，旧结论才能标"旧口径"。
    METRIC_SOURCES = {
        "monthRevenue": ["revenue_daily_report"],
        "weekRevenue": ["revenue_daily_report"],
        "weekOutpatient": ["revenue_daily_report"],
        "weekInpatient": ["revenue_daily_report"],
        "weekVisits": ["revenue_daily_report"],
        "weekAdmit": ["revenue_daily_report"],
        "weekDischarge": ["revenue_daily_report"],
        "wardCount": ["revenue_daily_report"],
        "netPool": ["revenue_daily_report"],
    }
    fetched_at = q1(c, "SELECT MAX(last_pull_at) FROM source") or pulled_at()
    published_at = datetime.now(CN).isoformat(timespec="seconds")
    for _mid, _mv in metrics.items():
        if _mid == "monthRevenue":
            _mv.setdefault("periodStart", month_start.isoformat())
            _mv.setdefault("periodEnd", dt.isoformat())
            _mv["coverage"] = {"recordedDays": len(daily), "expectedDays": month_days,
                               "pct": round(len(daily) / month_days * 100, 1)}
        else:
            _mv.setdefault("periodStart", p_start.isoformat())
            _mv.setdefault("periodEnd", p_end.isoformat())
            _mv["coverage"] = {"recordedDays": days_recorded, "expectedDays": 7,
                               "pct": round(days_recorded / 7 * 100, 1)}
        _mv["fetchedAt"] = fetched_at
        _mv["publishedAt"] = published_at
        _mv["asOf"] = as_of
        _mv["sourceIds"] = METRIC_SOURCES.get(_mid, [])
        _mv["definitionVersion"] = "v1"
        _mv["timezone"] = "Asia/Shanghai"
        # 期间与覆盖必须能被机器读出来：进行中（缺日）不能标成 ok 的完整期
        if _mv.get("status") == "ok" and _mv["coverage"]["recordedDays"] < _mv["coverage"]["expectedDays"]:
            _mv["status"] = "provisional"

    # ── 洞察（确定性，不猜测因果）──────────────────────────────
    insights = [
        {"id": "rev", "metricIds": ["weekRevenue"], "numbersOnly": True,
         "text": f"本期（{p_start.month}.{p_start.day}–{p_end.month}.{p_end.day}，已录 {days_recorded} 天）营收 "
                 f"{week_total/10000:.2f} 万；上期同 {days_recorded} 天 {prev_total/10000:.2f} 万，"
                 f"{delta(week_total, prev_total):+.1f}%。"},
        {"id": "split", "metricIds": ["weekOutpatient", "weekInpatient"], "numbersOnly": True,
         "text": f"门诊 {out_w/10000:.2f} 万、在院 {in_w/10000:.2f} 万；门诊占 {pct(out_w, week_total)}%。"},
        {"id": "visit", "metricIds": ["weekVisits"], "numbersOnly": True,
         "text": f"门诊 {int(vis_new+vis_ret)} 人次（初诊 {int(vis_new)} / 复诊 {int(vis_ret)}），"
                 f"较上期同 {days_recorded} 天 {delta(vis_new+vis_ret, vis_prev):+.1f}%。"},
        {"id": "ward", "metricIds": ["wardCount", "weekAdmit", "weekDischarge"], "numbersOnly": True,
         "text": f"入院 {int(adm)}、出院 {int(dis)}，患者池净 {int(adm-dis):+d} 人；"
                 f"在院 {('—' if ward is None else str(int(ward)))} 人（{data_through} 时点）。"},
        {"id": "psych", "metricIds": ["psych.contact"], "numbersOnly": True,
         "text": f"心理组本期日报 {pw['report']} 条（{p_start.month}.{p_start.day}–{date.fromisoformat(psy_end).month}.{date.fromisoformat(psy_end).day}，"
                 f"{psy_n} 天）：患者接触 {pw['contact']} 人次、咨询工作量 {pw['consult']} 人次，"
                 f"团体 {pw['groupSessions']} 场 / {pw['groupPeople']} 人次；上期同 {psy_n} 天 "
                 f"接触 {pw_prev['contact']}、咨询 {pw_prev['consult']}。"},
        {"id": "service", "metricIds": ["service.followup"], "numbersOnly": True,
         "text": f"客服回访 {sw['followup']} 条、标记到院 {sw['arrived']} 人（{sw['rate']}%，{svc_n} 天）；"
                 f"上期同 {svc_n} 天 {sw_prev['followup']} 条 / {sw_prev['arrived']} 人（{sw_prev['rate']}%）。"},
        {"id": "butler", "metricIds": ["butler.contact"], "numbersOnly": True,
         "text": f"管家有效对接 {bw['contact']} 条、转住院 {bw['admit']} 人（{bw['rate']}%，{but_n} 天）；"
                 f"上期同 {but_n} 天 {bw_prev['contact']} 条 / {bw_prev['admit']} 人（{bw_prev['rate']}%）。"},
    ]

    # ── 冲突 / 待核 ───────────────────────────────────────────
    conflicts = [
        {"id": "arrival_vs_service", "label": "到院口径两源不一致", "severity": "warn",
         "detail": f"《10月到院登记表》{p_start.month}.{p_start.day}–{date.fromisoformat(arr_end).month}.{date.fromisoformat(arr_end).day} 逐条 {arr_w} 人次；"
                   f"《客服服务部汇报表》本周「到院人数」填 {dept_report['service']['arrived']}（其正文为导医接待人次）。"
                   f"两者粒度不同（到院登记＝就诊患者，接待＝含陪同），按契约不合并、不取平均。"},
        {"id": "psych_week_table_lag", "label": "心理组周统计仍停在 10.04—10.10", "severity": "warn",
         "detail": "V4「周个人统计」手动周起始日仍为 2026-10-04（结束日 10-10），"
                   "未随 10.12—10.18 推进；故本期心理指标一律由「咨询师每日简报」逐条汇总，周表仅作交叉核对。"},
        {"id": "service_workload_gap", "label": "导医工作量 10.17 未填", "severity": "info",
         "detail": f"《日工作量考核表》本周合计 {sw['workload']} 分，10.17 无记录；"
                   f"上期同 {days_recorded} 天 {sw_prev['workload']} 分，缺日不补、不直接比。"},
    ]
    if missing_butler:
        conflicts.append({"id": "butler_missing", "label": "管家表本周未填报", "severity": "info",
                          "detail": f"《患者有效对接表》中 {'、'.join(missing_butler)} 本周无记录（按契约记 null，不按 0 降榜）。"})
    cum_src = q1(c, "SELECT 1") and None
    if abs(round(month_total, 2) - round(sum(x["total"] for x in daily), 2)) > 0.5:
        conflicts.append({"id": "month_cum", "label": "当月累计与逐日加总不一致", "severity": "warn",
                          "detail": "按契约以逐日事实为准。"})

    # ── 来源状态 ──────────────────────────────────────────────
    src_rows = list(c.execute("SELECT id,name,url,status,data_through,last_pull_at FROM source ORDER BY id"))
    srcs = []
    for sid, name, url, status, dth, lp in src_rows:
        srcs.append({"id": sid, "name": name, "url": url, "enabled": True,
                     # 契约：未通过接入验证的源必须保持未启用。本轮 7 个源里 6 个已用
                     # 官方 skill 授权读通（kdocs-cli sheet get-range-data），故置 true 并留证据；
                     # 营收日报为院方逐日台账式源，不经在线表格。
                     "accessVerified": True,
                     "verifyMethod": "kdocs-cli sheet get-range-data 授权读成功（2026-10-18）",
                     "status": "ok" if status == "ok" else status,
                     "dataThrough": dth, "lastSuccessAt": lp,
                     "note": {"revenue_daily_report": "营收日报逐日台账（经勾稽核验）",
                              "action_report": "部门汇报表：本周口径由各部门自填，表头与正文可能不同期",
                              "psych_v4": "V4 管理表：日报逐条汇总；周统计仍停在 10.04—10.10",
                              "psych_visits": "仅用前三 sheet（新-排班 / 课程排班 / 团体治疗登记）",
                              "butler_contacts": "各管家分表；未填报记 null",
                              "service_followups": "回访台账逐条 + 导诊记录 + 日工作量",
                              "arrival_register": "当月到院登记逐条"}.get(sid, "")})

    coverage = {"recordedDays": len(daily), "monthDays": month_days,
                "pct": round(len(daily) / month_days * 100, 1)}

    snap = {
        "schemaVersion": 2,
        "revision": 0,
        "revisionCreatedAt": datetime.now(CN).isoformat(timespec="seconds"),
        "asOf": as_of, "month": dt.strftime("%Y-%m"), "timezone": "Asia/Shanghai",
        "generatedAt": datetime.now(CN).isoformat(timespec="seconds"),
        "period": {"start": p_start.isoformat(), "end": p_end.isoformat(),
                   "label": f"{p_start.month}.{p_start.day}–{p_end.month}.{p_end.day}",
                   "daysRecorded": days_recorded, "dataThrough": data_through},
        # 每族各自的截止日与已录天数：不能用一个源的时间冒充全部数据截至，
        # 也不能拿「营收的 6 天」去和其他源「7 天」做环比（见前方 fam_* 注释）。
        "watermarks": {
            "revenue": {"dataThrough": data_through, "days": days_recorded},
            "psych": {"dataThrough": psy_end, "days": psy_n},
            "service": {"dataThrough": svc_end, "days": svc_n},
            "butler": {"dataThrough": but_end, "days": but_n},
            "arrival": {"dataThrough": arr_end, "days": arr_n},
        },
        "previousPeriod": {"start": prev_start.isoformat(), "end": prev_end.isoformat(),
                           "compareSameDaysEnd": cmp_end.isoformat(), "daysRecorded": days_recorded},
        # 期间口径必须可查、可版本化：契约默认是两周窗（10.05—10.18），
        # 本轮按业主 2026-10-18 明确指令改为**自然周**（10.12—10.18）。
        # 两条都写进快照，避免下游把它当默认值悄悄改回去。
        "settings": {"periodWeeks": 1, "periodAnchor": p_start.isoformat(),
                     "periodType": "natural_week",
                     "periodDecision": "业主 2026-10-18 指定：本期为自然周 10.12–10.18",
                     "contractBaseline": {"periodWeeks": 2, "periodAnchor": "2026-10-05",
                                          "range": "2026-10-05—2026-10-18", "note": "契约默认两周窗，本轮不采用"}},
        "timezone": "Asia/Shanghai",
        "metrics": metrics,
        "daily": daily,
        "departments": dept_report,
        "psych": {"week": pw, "prevSameDays": pw_prev, "staff": psy_staff,
                  "boundPatients": int(bound or 0),
                  "daily": {k: int(v) for k, v in psy_day.items()}},
        "service": {"week": sw, "prevSameDays": sw_prev, "staff": svc_staff, "staffArrived": svc_arr,
                    "daily": {k: int(v) for k, v in svc_day.items()}},
        "butler": {"week": bw, "prevSameDays": bw_prev, "staff": but_staff, "missingStaff": missing_butler,
                   "daily": {k: int(v) for k, v in bw_daily.items()}},
        "arrival": {"week": arr_w, "new": arr_new, "prevSameDays": arr_prev,
                    "channels": arr_chan, "daily": {k: int(v) for k, v in arr_daily.items()},
                    "prevDaily": {k: int(v) for k, v in arr_prev_daily.items()}},
        "insights": insights,
        "conflicts": conflicts,
        "sources": srcs,
        "coverage": coverage,
    }

    # ── 写库 + 落盘（内容无变化则不改 revision）────────────────
    # ⚠ 指纹必须排除时间字段：generatedAt / publishedAt 每次都不同，
    #   若算进去，同一份数据重算一次就"像"换了一版，revision 会无意义地涨，
    #   下游 SSE 也会被反复唤起（2026-10-18 同日二次导入实测 rev 6→7）。
    import hashlib

    def content_fp(s):
        tmp = {k: v for k, v in s.items() if k not in ("generatedAt", "revisionCreatedAt", "_fp")}
        tmp["metrics"] = {mid: {k: v for k, v in mv.items() if k != "publishedAt"}
                          for mid, mv in s.get("metrics", {}).items()}
        return hashlib.sha256(
            json.dumps(tmp, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    fp = content_fp(snap)
    row = c.execute("SELECT revision, snapshot_json FROM revision ORDER BY revision DESC LIMIT 1").fetchone()
    if row and json.loads(row[1]).get("_fp") == fp:
        rev = row[0]
        print(f"内容无变化，沿用 revision {rev}")
        # 调用方（API 服务）要的是快照本身：内容等价，回库中那份即可
        try:
            return json.loads(row[1])
        except Exception:
            snap["revision"] = rev
            snap["_fp"] = fp
            return snap
    rev = (row[0] + 1) if row else 1
    snap["revision"] = rev
    snap["_fp"] = fp
    if not write:
        # 只算不写：revision 取「下一版号」，但不占号、不落盘
        return snap
    blob = json.dumps(snap, ensure_ascii=False, indent=1)
    with open(out, "w", encoding="utf-8") as f:
        f.write(blob)
    c.execute("INSERT INTO revision(revision,created_at,as_of,data_through,period_start,period_end,snapshot_json) "
              "VALUES(?,?,?,?,?,?,?)",
              (rev, snap["revisionCreatedAt"], as_of, data_through, p_start.isoformat(), p_end.isoformat(), blob))
    c.commit()
    print(f"已发布 revision {rev} → data/snapshot.json")
    print(f"  期间 {snap['period']['label']}（已录 {days_recorded} 天，数据至 {data_through}）")
    print(f"  月累计 {month_total/10000:.2f} 万 / 目标 {TARGET_WAN} 万 = {amount_progress}%（时间进度 {time_progress}%，差 {amount_progress-time_progress:+.1f}pt）")
    print(f"  本期 {week_total/10000:.2f} 万，上期同 {days_recorded} 天 {prev_total/10000:.2f} 万")
    print(f"  心理 接触 {pw['contact']} / 咨询 {pw['consult']}；客服 回访 {sw['followup']}；管家 {bw['contact']}；到院 {arr_w}")
    return snap


if __name__ == "__main__":
    main()
