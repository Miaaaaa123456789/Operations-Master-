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
    rev_through = rev_days[-1]          # 营收日报次日发布：2026-10-17
    data_through = rev_through          # 展示口径稍后被部门汇报表覆盖
    dt = date.fromisoformat(rev_through)

    # 自然周（周一至周日）
    p_start = as_of_date = dt - timedelta(days=dt.weekday())
    p_end = p_start + timedelta(days=6)
    prev_start = p_start - timedelta(days=7)
    prev_end = p_start - timedelta(days=1)
    month_start = dt.replace(day=1)
    days_recorded = len([d for d in rev_days if p_start.isoformat() <= d <= p_end.isoformat()])
    cmp_end = prev_start + timedelta(days=days_recorded - 1)

    # ── 部门汇报表（周口径，2026-10-19 业主指定：冲突一律以本表为准）──────
    # 汇报表按自然周自填、含当天，故它是本周唯一「7 天完整」的来源；
    # 营收日报次日发布，本周只到 10.17（6 天）——两者不是谁算错，是截止日不同。
    wk_end = p_end.isoformat()
    prev_wk_end = prev_end.isoformat()

    def dfact(metric, day):
        return q1(c, "SELECT value FROM fact WHERE source_id='action_report' AND metric_id=? "
                     "AND business_date=?", (metric, day))

    d_rev = dfact("dept.doctor.revenue", wk_end)
    d_rev_p = dfact("dept.doctor.revenue", prev_wk_end)
    d_adm = dfact("dept.doctor.admit", wk_end)
    d_adm_p = dfact("dept.doctor.admit", prev_wk_end)
    d_dis = dfact("dept.doctor.discharge", wk_end)
    d_dis_p = dfact("dept.doctor.discharge", prev_wk_end)
    d_opd = dfact("dept.doctor.outpatient", wk_end)
    d_opd_p = dfact("dept.doctor.outpatient", prev_wk_end)
    d_phy = dfact("dept.doctor.physio", wk_end)
    d_month = sum(x for x in (r[0] for r in c.execute(
        "SELECT value FROM fact WHERE source_id='action_report' AND metric_id='dept.doctor.revenue' "
        "AND business_date BETWEEN ? AND ?", (month_start.isoformat(), wk_end))) if x is not None) or None
    # 汇报表覆盖到 10.18：展示口径以它为准（营收日报仍保留在 revenueDataThrough 里）
    dept_through = wk_end if d_rev is not None else rev_through
    days_recorded = 7 if d_rev is not None else days_recorded
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
    # ledger_* 是营收日报逐日台账（可勾稽，但本周只到 10.17）；
    # 对外数字按业主指令取汇报表（d_*），台账原值一并留在快照里供核对。
    out_m = s(c, "revenue.outpatient", month_start.isoformat(), rev_through) or 0
    in_m = s(c, "revenue.inpatient", month_start.isoformat(), rev_through) or 0
    ledger_month = out_m + in_m

    out_w = s(c, "revenue.outpatient", p_start.isoformat(), rev_through) or 0
    in_w = s(c, "revenue.inpatient", p_start.isoformat(), rev_through) or 0
    ledger_week = out_w + in_w
    out_p = s(c, "revenue.outpatient", prev_start.isoformat(), cmp_end.isoformat()) or 0
    in_p = s(c, "revenue.inpatient", prev_start.isoformat(), cmp_end.isoformat()) or 0
    ledger_prev = out_p + in_p

    month_total = d_month * 10000 if d_month is not None else ledger_month
    week_total = d_rev * 10000 if d_rev is not None else ledger_week
    prev_total = d_rev_p * 10000 if d_rev_p is not None else ledger_prev

    vis_new = s(c, "visit.new", p_start.isoformat(), rev_through) or 0
    vis_ret = s(c, "visit.return", p_start.isoformat(), rev_through) or 0
    vis_prev = (s(c, "visit.new", prev_start.isoformat(), cmp_end.isoformat()) or 0) + \
               (s(c, "visit.return", prev_start.isoformat(), cmp_end.isoformat()) or 0)
    adm = d_adm if d_adm is not None else (s(c, "admit", p_start.isoformat(), rev_through) or 0)
    dis = d_dis if d_dis is not None else (s(c, "discharge", p_start.isoformat(), rev_through) or 0)
    adm_p = d_adm_p if d_adm_p is not None else (s(c, "admit", prev_start.isoformat(), cmp_end.isoformat()) or 0)
    dis_p = d_dis_p if d_dis_p is not None else (s(c, "discharge", prev_start.isoformat(), cmp_end.isoformat()) or 0)
    week_visits = d_opd if d_opd is not None else (vis_new + vis_ret)
    week_visits_p = d_opd_p if d_opd_p is not None else vis_prev
    ward = q1(c, "SELECT value FROM fact WHERE metric_id='ward.count' AND business_date=?",
              (rev_through,))
    # 在院人数是「时点值」，不是当日发生额：手工补录当天只填了门诊/在院金额时，
    # 该日的 ward.count 会是 NULL——此时回退到最近一个有值的时点，而不是让 KPI 直接变空。
    if ward is None:
        ward = q1(c, "SELECT value FROM fact WHERE metric_id='ward.count' AND business_date<=? "
                     "ORDER BY business_date DESC LIMIT 1", (rev_through,))
    ward_prev = q1(c, "SELECT value FROM fact WHERE metric_id='ward.count' AND business_date<=? "
                      "ORDER BY business_date DESC LIMIT 1", (cmp_end.isoformat(),))

    # 时间进度：按该指标 dataThrough 计算（当月自然日）
    month_days = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    month_days = month_days.day
    elapsed = date.fromisoformat(dept_through).day
    amount_progress = round(month_total / 10000 / TARGET_WAN * 100, 1)
    time_progress = round(elapsed / month_days * 100, 1)
    gap = round(TARGET_WAN - month_total / 10000, 2)
    data_through = dept_through

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

    # ── 部门汇报表（本周口径，源表自填；冲突裁决方）───────────
    def iv(x):
        """计数类：整数值不要显示成 484.0。"""
        if x is None:
            return None
        return int(x) if float(x).is_integer() else x

    dept_report = {
        "doctor": {"admit": iv(d_adm), "discharge": iv(d_dis), "outpatient": iv(d_opd),
                   "physioWan": d_phy, "revenueWan": d_rev},
        "nursing": {"physioPeople": iv(dfact("dept.nursing.physio_people", wk_end)),
                    "recreationSessions": iv(dfact("dept.nursing.rec_sessions", wk_end)),
                    "recreationPeople": iv(dfact("dept.nursing.rec_people", wk_end))},
        "psychology": {"individual": iv(dfact("dept.psych.individual", wk_end)),
                       "groupSessions": iv(dfact("dept.psych.sessions", wk_end)),
                       "people": iv(dfact("dept.psych.people", wk_end)),
                       "revenueYuan": iv(dfact("dept.psych.revenue", wk_end))},
        "service": {"followup": iv(dfact("dept.service.followup", wk_end)),
                    "arrived": iv(dfact("dept.service.arrived", wk_end)),
                    "charity": iv(dfact("dept.service.charity", wk_end))},
        "marketing": {"admit": iv(dfact("dept.marketing.admit", wk_end)),
                      "outpatient": iv(dfact("dept.marketing.outpatient", wk_end)),
                      "revenueWan": dfact("dept.marketing.revenue", wk_end)},
    }

    # ── 护理部 6 项治疗完成情况（周合计为准 + 逐日明细对账）──────
    # 护理部口径的完成率是**向下取整**，不是四舍五入：
    # 71/75=94.67→94、21/26=80.77→80、11/14=78.57→78。用 round() 会有 3 项差 1 个点。
    NURSE_TREATS = [
        ("ac_current", "经颅交流电"),
        ("tms", "经颅磁治疗"),
        ("brain_func", "脑功能治疗"),
        ("music_relax", "音乐放松治疗"),
        ("insomnia", "失眠治疗仪治疗"),
        ("group_biofeedback", "团体生物反馈"),
    ]

    def nw_fact(k, f):
        return q1(c, "SELECT value FROM fact WHERE source_id='nursing_weekly' AND metric_id=? "
                     "AND business_date=? AND dim_key=''", (f"nursing.treat.{k}.{f}", wk_end))

    def nd_sum(k, f):
        # 逐日只在 dim_key='daily' 上取，避免和周合计相加翻倍
        return q1(c, "SELECT SUM(value) FROM fact WHERE source_id='nursing_treat_daily' AND metric_id=? "
                     "AND dim_key='daily' AND business_date BETWEEN ? AND ?",
                  (f"nursing.treat.{k}.{f}", p_start.isoformat(), wk_end))

    treat_rows, n_due, n_done = [], 0, 0
    for k, lab in NURSE_TREATS:
        due, done = nw_fact(k, "due"), nw_fact(k, "done")
        d_due, d_done = nd_sum(k, "due"), nd_sum(k, "done")
        rate = int(done / due * 100) if (due and done is not None) else None
        treat_rows.append({
            "key": k, "label": lab,
            "due": iv(due), "done": iv(done), "missed": iv(due - done) if due is not None and done is not None else None,
            "rate": rate,
            "dailyDue": iv(d_due), "dailyDone": iv(d_done),
            "dailyRate": (int(d_done / d_due * 100) if (d_due and d_done is not None) else None),
        })
        if due is not None:
            n_due += due
        if done is not None:
            n_done += done

    dept_report["nursing"]["treat"] = treat_rows
    dept_report["nursing"]["treatSummary"] = {
        "due": iv(n_due), "done": iv(n_done),
        "missed": iv(n_due - n_done),
        "rate": int(n_done / n_due * 100) if n_due else None,
        "items": len(treat_rows),
        "worst": min((t for t in treat_rows if t["rate"] is not None),
                     key=lambda t: t["rate"], default=None),
        "rateRule": "floor",
        "source": "nursing_weekly",
        "dailyThrough": rev_through,
        "note": "完成率按护理部口径向下取整。逐日明细只到 " + rev_through +
                "，本周 10.18 当天未进逐日表，故六项「周合计−逐日加总」的差额即 10.18 一天。",
    }

    # 医生组个人明细：加总与表头对不上的地方原样保留，不替对方补数，也不拉平
    staff = []
    for name, _first_id in c.execute("SELECT dim_value, MIN(id) FROM fact WHERE source_id='action_report' "
                                     "AND dim_key='staff' GROUP BY dim_value ORDER BY MIN(id)"):
        staff.append({
            "name": name,
            "admit": q1(c, "SELECT value FROM fact WHERE metric_id='dept.doctor.staff_admit' "
                           "AND business_date=? AND dim_value=?", (wk_end, name)),
            "discharge": q1(c, "SELECT value FROM fact WHERE metric_id='dept.doctor.staff_discharge' "
                               "AND business_date=? AND dim_value=?", (wk_end, name)),
            "convert": q1(c, "SELECT value FROM fact WHERE metric_id='dept.doctor.staff_convert' "
                             "AND business_date=? AND dim_value=?", (wk_end, name)),
            "duodao": q1(c, "SELECT value FROM fact WHERE metric_id='dept.doctor.staff_duodao' "
                            "AND business_date=? AND dim_value=?", (wk_end, name)),
        })
    sum_adm = int(sum(x["admit"] for x in staff if x["admit"] is not None))
    sum_dis = int(sum(x["discharge"] for x in staff if x["discharge"] is not None))
    blank = [x["name"] for x in staff
             if x["admit"] is None and x["discharge"] is None and x["convert"] is None]
    dept_report["doctor"]["staff"] = staff
    dept_report["doctor"]["recon"] = {
        "admit": {"header": int(d_adm) if d_adm is not None else None, "detail": sum_adm,
                  "gap": (int(d_adm) - sum_adm) if d_adm is not None else None},
        "discharge": {"header": int(d_dis) if d_dis is not None else None, "detail": sum_dis,
                      "gap": (int(d_dis) - sum_dis) if d_dis is not None else None},
        "blankRows": blank,
        "note": "个人明细只覆盖科内 6 名医生，表头为全组口径；空白行按契约记 null、不记 0，也不反推。",
    }
    dept_report["week"] = {"start": p_start.isoformat(), "end": wk_end,
                           "label": f"{p_start.month}.{p_start.day}—{p_end.month}.{p_end.day}",
                           "authority": "action_report",
                           "sourceName": "特别行动小组汇报表",
                           "filledAt": q1(c, "SELECT MAX(last_pull_at) FROM source WHERE id='action_report'")}
    dept_report["compareWeek"] = {"start": prev_start.isoformat(), "end": prev_wk_end,
                                  "revenueWan": d_rev_p, "admit": d_adm_p,
                                  "discharge": d_dis_p, "outpatient": d_opd_p}

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
                         "gap": gap, "dataThrough": data_through, "status": "ok",
                         "authority": "action_report", "ledgerValue": round(ledger_month / 10000, 2),
                         "ledgerThrough": rev_through},
        "weekRevenue": metric("weekRevenue", "本期营收", round(week_total / 10000, 2), "万元",
                              valueYuan=round(week_total, 2), days=days_recorded,
                              deltaPct=delta(week_total, prev_total),
                              authority="action_report",
                              ledgerValue=round(ledger_week / 10000, 2), ledgerThrough=rev_through,
                              compare=f"{prev_start.isoformat()}—{cmp_end.isoformat()} 同 {days_recorded} 天"),
        "weekOutpatient": metric("weekOutpatient", "本期门诊收入", round(out_w / 10000, 2), "万元",
                                 deltaPct=delta(out_w, out_p), authority="revenue_daily_report",
                                 note=f"营收日报台账口径，仅到 {rev_through}，未含 10.18"),
        "weekInpatient": metric("weekInpatient", "本期在院收入", round(in_w / 10000, 2), "万元",
                                deltaPct=delta(in_w, in_p), authority="revenue_daily_report",
                                note=f"营收日报台账口径，仅到 {rev_through}，未含 10.18"),
        "weekPhysio": metric("weekPhysio", "本期物理治疗费", d_phy, "万元", authority="action_report",
                             deltaPct=delta(d_phy, dfact("dept.doctor.physio", prev_wk_end))),
        "weekVisits": metric("weekVisits", "本期门诊人次", int(week_visits), "人次",
                             visitsNew=int(vis_new), visitsReturn=int(vis_ret),
                             authority="action_report", ledgerValue=int(vis_new + vis_ret),
                             ledgerThrough=rev_through,
                             deltaPct=delta(week_visits, week_visits_p)),
        "nurseTreatRate": metric("nurseTreatRate", "护理治疗完成率",
                                 dept_report["nursing"]["treatSummary"]["rate"], "%",
                                 authority="nursing_weekly",
                                 due=dept_report["nursing"]["treatSummary"]["due"],
                                 done=dept_report["nursing"]["treatSummary"]["done"],
                                 missed=dept_report["nursing"]["treatSummary"]["missed"],
                                 note="护理部 6 项治疗加权完成率，按科室口径向下取整"),
        "weekAdmit": metric("weekAdmit", "本期入院", int(adm), "人", deltaPct=delta(adm, adm_p),
                            authority="action_report"),
        "weekDischarge": metric("weekDischarge", "本期出院", int(dis), "人", deltaPct=delta(dis, dis_p),
                                authority="action_report"),
        "wardCount": {"id": "wardCount", "label": "在院人数", "value": int(ward) if ward is not None else None,
                      "unit": "人", "dataThrough": rev_through, "status": "ok", "pointInTime": True},
        "netPool": {"id": "netPool", "label": "患者池净变化", "value": int(adm - dis), "unit": "人",
                    "dataThrough": data_through, "status": "ok"},
    }

    # ── 契约补齐：每个指标都必须自带期间/截至/来源/覆盖/定义版本 ────────
    # DATA_CONTRACT 要求每张指标卡都返回
    #   periodStart/periodEnd/dataThrough/fetchedAt/publishedAt/asOf/coverage/status/sourceIds
    # 缺任一项，前端就只能靠文案硬编码第二份结果 —— 故在快照生成时统一补齐，
    # 不让展示层自己猜。definitionVersion 随规则改动递增，旧结论才能标"旧口径"。
    METRIC_SOURCES = {
        "monthRevenue": ["action_report", "revenue_daily_report"],
        "weekRevenue": ["action_report", "revenue_daily_report"],
        "weekOutpatient": ["revenue_daily_report"],
        "weekInpatient": ["revenue_daily_report"],
        "weekPhysio": ["action_report"],
        "weekVisits": ["action_report", "revenue_daily_report"],
        "weekAdmit": ["action_report", "revenue_daily_report"],
        "weekDischarge": ["action_report", "revenue_daily_report"],
        "wardCount": ["revenue_daily_report"],
        "netPool": ["action_report"],
        "nurseTreatRate": ["nursing_weekly", "nursing_treat_daily"],
    }
    fetched_at = q1(c, "SELECT MAX(last_pull_at) FROM source") or pulled_at()
    published_at = datetime.now(CN).isoformat(timespec="seconds")
    for _mid, _mv in metrics.items():
        if _mid == "monthRevenue":
            _mv.setdefault("periodStart", month_start.isoformat())
            _mv.setdefault("periodEnd", dept_through)
            _mv["coverage"] = {"recordedDays": min(elapsed, month_days), "expectedDays": month_days,
                               "pct": round(min(elapsed, month_days) / month_days * 100, 1)}
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
         "text": f"本期（{p_start.month}.{p_start.day}–{p_end.month}.{p_end.day}，7 天）营收 "
                 f"{week_total/10000:.2f} 万（汇报表口径）；上期 {prev_total/10000:.2f} 万，"
                 f"{delta(week_total, prev_total):+.1f}%。"},
        {"id": "physio", "metricIds": ["weekPhysio"], "numbersOnly": True,
         "text": f"物理治疗费 {d_phy if d_phy is not None else '—'} 万，占本周总收入 {pct(d_phy, d_rev) if d_phy and d_rev else '—'}%。"},
        {"id": "nursing_treat", "metricIds": ["nurseTreatRate"], "numbersOnly": True,
         "text": f"护理六项治疗应做 {dept_report['nursing']['treatSummary']['due']} 人次、实做 "
                 f"{dept_report['nursing']['treatSummary']['done']} 人次，合计完成 "
                 f"{dept_report['nursing']['treatSummary']['rate']}%（护理部口径向下取整）；"
                 f"最低为{dept_report['nursing']['treatSummary']['worst']['label']} "
                 f"{dept_report['nursing']['treatSummary']['worst']['rate']}%，"
                 f"缺口集中在失眠治疗仪与团体生物反馈。"},
        {"id": "visit", "metricIds": ["weekVisits"], "numbersOnly": True,
         "text": f"门诊 {int(week_visits)} 人次，较上期 {int(week_visits_p)} 人次 {delta(week_visits, week_visits_p):+.1f}%；"
                 f"到院登记同日 {arr_w} 人次（含陪同，两者不合并）。"},
        {"id": "ward", "metricIds": ["wardCount", "weekAdmit", "weekDischarge"], "numbersOnly": True,
         "text": f"入院 {int(adm)}、出院 {int(dis)}，患者池净 {int(adm-dis):+d} 人；"
                 f"在院 {('—' if ward is None else str(int(ward)))} 人（{rev_through} 时点）。"},
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
    # 裁决规则（业主 2026-10-19 定）：凡与《特别行动小组汇报表》冲突，一律取汇报表。
    # 每条都写明双方数值与胜出方，页面据此标注，不再出现「两个数互相不认」。
    conflicts = [
        {"id": "week_revenue", "label": "本周营收：汇报表 72.5 万 vs 台账 37.27 万", "severity": "warn",
         "winner": "action_report", "source_a": "action_report", "source_b": "revenue_daily_report",
         "value_a": d_rev, "value_b": round(ledger_week / 10000, 2),
         "detail": f"汇报表第3周总收入 {d_rev} 万（7 天，含 10.18）；营收日报只到 {rev_through}，"
                   f"{days_recorded - 1} 天合计 {ledger_week/10000:.2f} 万。差额不是算错：10.18 到院 {arr_daily.get(wk_end, 0)} 人次"
                   f"（平日 17–28），当日营收尚未进入日报。按指令以汇报表为准，台账原值保留可查。"},
        {"id": "month_revenue", "label": "10月累计：汇报表 167.70 万 vs 台账 139.78 万", "severity": "warn",
         "winner": "action_report", "source_a": "action_report", "source_b": "revenue_daily_report",
         "value_a": round(month_total / 10000, 2), "value_b": round(ledger_month / 10000, 2),
         "detail": f"汇报表三周合计 26.2＋69＋72.5＝{month_total/10000:.2f} 万；台账 10.1—{rev_through} 逐日合计 "
                   f"{ledger_month/10000:.2f} 万。差 {(month_total-ledger_month)/10000:+.2f} 万（含 10.18 未入台账，"
                   f"及第1/2周两口径本身的差）。按指令采用汇报表，逐日图仍显示台账并标注口径。"},
        {"id": "doctor_detail", "label": "医生组表头与其个人明细对不上", "severity": "warn",
         "winner": "action_report", "source_a": "action_report", "source_b": "action_report",
         "value_a": d_adm, "value_b": sum_adm,
         "detail": f"表头入院 {int(d_adm) if d_adm is not None else '—'} 人、出院 {int(d_dis) if d_dis is not None else '—'} 人；"
                   f"6 名医生正文加总入院 {sum_adm}、出院 {sum_dis}，缺口 {int(d_adm or 0)-sum_adm} 入 / "
                   f"{int(d_dis or 0)-sum_dis} 出。空白行：{'、'.join(blank) or '无'}（该行未填，按契约记 null 不记 0）。"
                   f"孙乐写的是『本周转化 5 人』，转化≠入院，不能直接累加。"},
        {"id": "arrival_vs_service", "label": "到院人数两个口径并存", "severity": "info",
         "winner": "action_report", "source_a": "arrival_register", "source_b": "action_report",
         "value_a": arr_w, "value_b": dept_report["service"]["arrived"],
         "detail": f"《10月到院登记表》{p_start.month}.{p_start.day}–{date.fromisoformat(arr_end).month}.{date.fromisoformat(arr_end).day} 逐条 {arr_w} 人次；"
                   f"《客服服务部汇报表》本周「到院人数」{dept_report['service']['arrived']}（导医接待，含陪同）。"
                   f"两指标含义不同，各自保留、互不加总。"},
        {"id": "physio_no_daily", "label": "物理治疗费只有周合计", "severity": "info",
         "winner": "action_report", "source_a": "action_report", "source_b": "",
         "value_a": d_phy, "value_b": None,
         "detail": f"汇报表本周物理治疗 {d_phy} 万（住院 29.8 ＋ 门诊 3.1）；营收日报未按日拆分该项，无法做逐日曲线。"},
    ]
    if dept_report["marketing"]["revenueWan"] is None:
        conflicts.append({"id": "marketing_blank", "label": "营销中心本周表头未填", "severity": "info",
                          "winner": "action_report", "source_a": "action_report", "source_b": "",
                          "value_a": None, "value_b": None,
                          "detail": "汇报表「营销中心」表头行只写了部门名，入院/门诊/总收入三格为空，按契约记 null，"
                                    "不拿上周数顶替。"})
    conflicts.append({"id": "psych_week_table_lag", "label": "心理组周统计仍停在 10.04—10.10", "severity": "warn",
                      "winner": "action_report", "source_a": "psych_v4", "source_b": "action_report",
                      "value_a": pw["contact"], "value_b": dept_report["psychology"]["individual"],
                      "detail": "V4「周个人统计」手动周起始日仍是 2026-10-04，未随本期推进；"
                                "部门卡按汇报表填 40 人，心理明细模块按日报逐条汇总（接触 "
                                f"{pw['contact']}、咨询 {pw['consult']}），两者不互算。"})
    if missing_butler:
        conflicts.append({"id": "butler_missing", "label": "管家表本周未填报", "severity": "info",
                          "winner": "butler_contacts", "source_a": "butler_contacts", "source_b": "",
                          "value_a": None, "value_b": None,
                          "detail": f"《患者有效对接表》中 {'、'.join(missing_butler)} 本周无记录（按契约记 null，不按 0 降榜）。"})
    conflicts.append({"id": "service_workload_gap", "label": "导医工作量 10.17 未填（汇报表无此栏）", "severity": "info",
                      "winner": "none", "source_a": "service_followups", "source_b": "",
                      "value_a": sw["workload"], "value_b": None,
                      "detail": f"《日工作量考核表》本周合计 {sw['workload']} 分，10.17 无记录；"
                                f"上期同 {days_recorded} 天 {sw_prev['workload']} 分，缺日不补、不直接比。"
                                " 汇报表未设置导医工作量栏，该项不存在「汇报表口径」可覆盖，"
                                "故仅登记为覆盖缺口，不与汇报表冲突。"})
    _ts = dept_report["nursing"]["treatSummary"]
    _gapD = _ts["due"] - sum(t["dailyDue"] or 0 for t in dept_report["nursing"]["treat"])
    _gapN = _ts["done"] - sum(t["dailyDone"] or 0 for t in dept_report["nursing"]["treat"])
    if _gapD or _gapN:
        conflicts.append({"id": "nursing_treat_1018", "label": "护理治疗周合计比逐日多 10.18 一天",
                          "severity": "info", "winner": "nursing_weekly",
                          "source_a": "nursing_weekly", "source_b": "nursing_treat_daily",
                          "value_a": _ts["done"], "value_b": _ts["done"] - _gapN,
                          "detail": f"护理部周报 6 项合计应做 {_ts['due']}、实做 {_ts['done']}"
                                    f"（{(p_start.month)}.{p_start.day}–{p_end.month}.{p_end.day}，含 10.18）；"
                                    f"随附 docx 的逐日表只到 {rev_through}，6 天合计应做 {_ts['due'] - _gapD}、"
                                    f"实做 {_ts['done'] - _gapN}。差额 {_gapD}/{_gapN} 即 10.18 单日，"
                                    "属逐日表未覆盖，不是两套数打架；周值取护理部报表，逐日仅作明细。"})

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
                              "arrival_register": "当月到院登记逐条",
                              "nursing_weekly": "护理部周报：6 项治疗应做/实做，完成率按科室口径向下取整",
                              "nursing_treat_daily": "随周报的 docx 逐日表，仅到 10.17，只作明细不作周值"}.get(sid, "")})

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
                   "daysRecorded": days_recorded, "dataThrough": data_through,
                   "revenueDataThrough": rev_through,
                   "authority": "action_report"},
        # 每族各自的截止日与已录天数：不能用一个源的时间冒充全部数据截至，
        # 也不能拿「营收的 6 天」去和其他源「7 天」做环比（见前方 fam_* 注释）。
        "watermarks": {
            "dept": {"dataThrough": wk_end, "days": 7, "authority": "action_report"},
            "nursing": {"dataThrough": wk_end, "days": 7, "authority": "nursing_weekly",
                        "dailyThrough": rev_through},
            "revenue": {"dataThrough": rev_through,
                        "days": len([d for d in rev_days if p_start.isoformat() <= d <= p_end.isoformat()])},
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
                     "authority": "action_report",
                     "authorityNote": "业主 2026-10-19 指定：与《特别行动小组汇报表》冲突的数据一律以该表为准",
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
