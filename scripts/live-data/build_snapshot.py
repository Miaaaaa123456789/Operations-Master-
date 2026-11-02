#!/usr/bin/env python3
"""从事实库重算发布快照 data/snapshot.json（新 revision 才写）。

口径（对齐 docs/live-data/DATA_CONTRACT.md）：
- 本期＝自然周 10.12—10.18；营收日报次日发布，故 dataThrough＝最新逐日营收日。
- 环比＝上一自然周（10.05—10.11）的**同天数前 N 日**，缺日不补、不跳。
- 缺失写 null，不写 0；涉及两源不一致的进 conflicts，不静默抹平。
"""
import json, os, re, sys
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
    # ⚠ 2026-10-22 修：本期窗口固定取 settings.period_anchor，不再由「最新营收日」反推。
    #   营收日报一旦推进到下周一/二（如 10.19、10.20），按 dt 反推会把本期整体切到
    #   新一周（10.19—10.25），而主表（汇报表）仍停在上周，Hero 五格会集体变空。
    #   锚点由 ingest.py 写入，是业务口径的唯一真源。
    anchor = q1(c, "SELECT value FROM settings WHERE key='period_anchor'")
    p_start = date.fromisoformat(anchor) if anchor else dt - timedelta(days=dt.weekday())
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
    # ⛔⛔ 2026-10-24 新增（关键口径）：汇报表「本周」表头检测——**没滚动就不许当本周数**。
    #   起因：10.24 抓取时《特别行动小组汇报表》五个部门表头全部还是上一周的内容
    #   （医生组 19 / 210 / 32.9 / 72.5 与 10.12—10.18 逐项同值），若照旧以它为本期权威，
    #   页面会出现「本周又做到 72.5 万」——正是业主明确不要的旧数据。
    #   判定依据：医生组正文里的「第 1/2/3 周」轨迹（ingest 另存为 dept.doctor.tri.*）。
    #   第 3 周 = 填表当时刚结束的那一周；表头四项若与第 3 周逐项相同，说明整行还在复读上一周。
    _tri = {m: q1(c, "SELECT value FROM fact WHERE metric_id=? AND business_date=?",
                  (f"dept.doctor.tri.{m}", wk_end))
            for m in ("revenue", "physio", "admit", "outpatient", "discharge")}
    _hdr_pairs = [("revenue", d_rev), ("physio", d_phy), ("admit", d_adm), ("outpatient", d_opd)]
    _matched = sum(1 for k, v in _hdr_pairs
                   if _tri.get(k) is not None and v is not None
                   and abs(float(_tri[k]) - float(v)) < 1e-9)
    _cmp_ok = bool(_hdr_pairs) and _matched == len(_hdr_pairs)
    # ⚠ 2026-10-26 补：**部分命中 ≠ 已滚动**，是「表头一半还停在上一周」的混合态。
    #   实测本周表头：营收 52.6（对不上任何一周）/ 入院 16（第 4 周）/ 门诊 210（第 4 周）/
    #   物理 32.9（第 3 周）—— 四项里只有两项落在第 3 周。这种表头不能当本期权威：
    #   照用会把月累计算成 26.2+69+52.6=147.8 万，而营收日报逐日 23 天是 193.97 万。
    #   规则：四项全等第 3 周 → 未滚动；有命中但不全等 → 混合态，同样回退台账；
    #   一项都不等 → 视为已滚动到新一周，按表头用。
    _mixed = 0 < _matched < len(_hdr_pairs)
    # ⛔ 2026-11-02 补：**表头整行为空**（换周次日、五部门都还没填）也必须走「不引用」分支。
    #   原先只判 _cmp_ok / _mixed，全空时 _matched=0、两者皆 False，于是走「已滚动」分支，
    #   后面 int(d_adm) 直接 TypeError 崩掉整条管线（10.26 换周首次运行实测）。
    _all_blank = all(v is None for v in (d_rev, d_adm, d_dis, d_opd, d_phy))
    stale_ar = _cmp_ok or _mixed or _all_blank
    # 表头原值留档：即便判为未滚动，也要把「表里到底写了什么」留在快照里可查（psych.header 同一做法）
    ar_header_raw = {"revenueWan": d_rev, "admit": d_adm, "discharge": d_dis,
                     "outpatient": d_opd, "physioWan": d_phy,
                     "week3Triplet": _tri,
                     "judgedBy": ("header_blank" if _all_blank
                                  else "header==week3_triplet" if _cmp_ok else "header!=week3")}
    _hdr_phy = d_phy
    if stale_ar:
        _why = ("本周表头四项整行为空（尚未填报）" if _all_blank
                else "与正文第 3 周逐项同值" if _cmp_ok
                else f"与第 3 周只对上 {_matched}/4 项（混合态）")
        print(f"⚠ 汇报表本周表头{_why}（{_tri}）→ 判定不可信，本周改用营收日报台账")
        d_rev = d_rev_p = d_adm = d_adm_p = d_dis = d_dis_p = d_opd = d_opd_p = d_phy = None
        d_month = None

    # 汇报表覆盖到 wk_end 才以它为准（营收日报仍保留在 revenueDataThrough 里）
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
        # ⚠ 排除 '.week.' 周桶：组长的「周个人统计」把一周汇总写在**周末那个日期**上，
        #   若不过滤，fam_end 会把 10-25（名义周末）当成"已有数据日"，
        #   心理/到院这些按天的口径就会被算成 7 天，实际只有 5 天的逐日数据。
        r = q1(c, "SELECT MAX(business_date) FROM fact WHERE source_id IN (%s) "
                  "AND metric_id NOT LIKE '%%.week.%%' "
                  "AND business_date BETWEEN ? AND ?" % q,
               tuple(srcs) + (p_start.isoformat(), p_end.isoformat()))
        return r or data_through

    def fam_days(end):
        return (date.fromisoformat(end) - p_start).days + 1

    def fam_cmp(end):
        return prev_start + timedelta(days=fam_days(end) - 1)

    # 护理部：周报 + 物理治疗逐日表。本周有没有提交，直接看本期窗口内有没有事实——
    # 没有就是没提交（nur_end=None），页面显示「本周未提交」，绝不拿上一期的 93% 顶上。
    nur_dates = [r[0] for r in c.execute(
        "SELECT DISTINCT business_date FROM fact WHERE source_id IN ('nursing_weekly','nursing_treat_daily') "
        "AND business_date BETWEEN ? AND ? ORDER BY 1", (p_start.isoformat(), p_end.isoformat()))]
    nur_end = nur_dates[-1] if nur_dates else None
    nur_n = fam_days(nur_end) if nur_end else 0
    nur_daily_end = q1(c, "SELECT MAX(business_date) FROM fact WHERE source_id='nursing_treat_daily'")

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

    # ⚠ 本期台账必须截到 p_end：营收日报已推进到 10.20，若直接用到 rev_through，
    #   10.19、10.20 两天会被算进「本期（10.12—10.18）」，等于把下一周塞进本周。
    rev_end = min(rev_through, p_end.isoformat())
    out_w = s(c, "revenue.outpatient", p_start.isoformat(), rev_end) or 0
    in_w = s(c, "revenue.inpatient", p_start.isoformat(), rev_end) or 0
    ledger_week = out_w + in_w
    out_p = s(c, "revenue.outpatient", prev_start.isoformat(), cmp_end.isoformat()) or 0
    in_p = s(c, "revenue.inpatient", prev_start.isoformat(), cmp_end.isoformat()) or 0
    ledger_prev = out_p + in_p

    # ── 月累计口径：跟着「最新逐日台账」走 ─────────────────────
    # 汇报表只到本期周末。一旦营收日报推进过当周周末、或汇报表本周未滚动（d_month 判空），
    # 月累计若仍用汇报表，就会出现「标签写 10.22、金额还是 10.18」的自相矛盾。
    # 规则：谁的覆盖更全用谁，并在快照里标清 authority，两套原值都保留。
    if ledger_month and (d_month is None or rev_through > wk_end):
        month_total = ledger_month
        month_authority = "revenue_daily_report"
    else:
        month_total = d_month * 10000 if d_month is not None else ledger_month
        month_authority = "action_report"
    week_total = d_rev * 10000 if d_rev is not None else ledger_week
    prev_total = d_rev_p * 10000 if d_rev_p is not None else ledger_prev

    vis_new = s(c, "visit.new", p_start.isoformat(), rev_end) or 0
    vis_ret = s(c, "visit.return", p_start.isoformat(), rev_end) or 0
    vis_prev = (s(c, "visit.new", prev_start.isoformat(), cmp_end.isoformat()) or 0) + \
               (s(c, "visit.return", prev_start.isoformat(), cmp_end.isoformat()) or 0)
    adm = d_adm if d_adm is not None else (s(c, "admit", p_start.isoformat(), rev_end) or 0)
    dis = d_dis if d_dis is not None else (s(c, "discharge", p_start.isoformat(), rev_end) or 0)
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
    # 月累计改走日报后，进度也必须跟到同一天，否则「已到 10.20」却按 18 号算时间进度。
    month_days = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    month_days = month_days.day
    elapsed = max(date.fromisoformat(dept_through).day, date.fromisoformat(rev_through).day)
    amount_progress = round(month_total / 10000 / TARGET_WAN * 100, 1)
    time_progress = round(elapsed / month_days * 100, 1)
    gap = round(TARGET_WAN - month_total / 10000, 2)
    # data_through 是「全表最新水位」：写 revision、页面顶部「数据至」都用它。
    # 周口径指标各自用 dept_through，不跟这个值走。
    data_through = rev_through

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

    # ── 周个人统计（组长自动汇总表）与日报逐条汇总并存 ─────────
    # ⚠ 两者口径不同：周个人统计是表内公式（按人×日去重），日报汇总是逐条累加。
    #   实测周表漏算赵芳 10-18 那条（落在每日简报表末尾第 1005 行），
    #   所以「门诊咨询」差 1、「填报天数」差 1；其余 5 项完全一致。差额在对账里明示、不互相覆盖。
    WK_COLS = [("report_days", "填报天数"), ("ward_days", "参加查房"), ("first", "首次对接"),
               ("emotion", "情绪支持"), ("inpatient", "住院咨询"), ("outpatient", "门诊咨询"),
               ("family", "家庭咨询"), ("parent", "家长访谈"), ("group_attend", "团体参与")]
    # ⛔⛔ 2026-11-02：本表的周窗口由组长在表内手填（第 3 行「周起始日 / 周结束日」，
    #   另有 B2 手动覆盖值），**不会**随 settings.period_anchor 滚动。原实现直接取
    #   dept_weeks 的本周窗口、又把「最新一期周表值」当作本周值 → 与本周日报跨期对账，
    #   gap 全是周期差（首次 −4 / 情绪 −11 / 住院 −14），不是漏填。
    #   契约：staffWeek/weekSum 永远是「本周」口径；周表口径只用于同窗 recon。
    _wt = c.execute("SELECT period_start, period_end FROM fact "
                    "WHERE metric_id='psych.week.report_days' AND period_start IS NOT NULL "
                    "ORDER BY period_end DESC LIMIT 1").fetchone()
    wt_start, wt_end = (_wt[0], _wt[1]) if _wt else (p_start.isoformat(), psy_end)
    wt_aligned = (wt_start == p_start.isoformat() and wt_end == psy_end)

    # 日报侧逐人聚合（周表未滚动时，作为本周唯一可用口径）
    _daily_fields = [("psych.report", "report_days"), ("psych.ward_attend", "ward_days"),
                     ("psych.first_contact", "first"), ("psych.emotion_support", "emotion"),
                     ("psych.inpatient_consult", "inpatient"),
                     ("psych.outpatient_consult", "outpatient"),
                     ("psych.family_consult", "family"), ("psych.parent_interview", "parent"),
                     ("psych.group_attend_daily", "group_attend")]
    _dmap = {}
    for _mid, _f in _daily_fields:
        for _k, _v in s(c, _mid, p_start.isoformat(), psy_end, "staff"):
            _dmap.setdefault(_k, {})[_f] = int(_v)

    _wk_names = [r[0] for r in c.execute(
        "SELECT dim_value, MIN(id) FROM fact WHERE metric_id='psych.week.report_days' "
        "AND period_start=? AND period_end=? GROUP BY dim_value ORDER BY MIN(id)",
        (wt_start, wt_end))]

    psy_staff_week = []
    for nm in _wk_names + [k for k in _dmap if k not in _wk_names]:
        row = {"name": nm}
        if wt_aligned:
            for f, _lab in WK_COLS:
                v = q1(c, "SELECT value FROM fact WHERE metric_id=? AND dim_value=? "
                          "AND period_start=? AND period_end=?",
                       (f"psych.week.{f}", nm, wt_start, wt_end))
                row[f] = int(v) if v is not None else None
            row["rate"] = q1(c, "SELECT value FROM fact WHERE metric_id='psych.week.rate' "
                                "AND dim_value=? AND period_start=? AND period_end=?",
                             (nm, wt_start, wt_end))
            row["source"] = "week_table"
        else:
            # 天数类：名单内却无日报＝0 天，属可观测事实；
            # 业务量类：整周未填＝null，不当 0、也不拿上周周表值顶替。
            d = _dmap.get(nm, {})
            for f, _lab in WK_COLS:
                row[f] = d.get(f, 0) if f in ("report_days", "ward_days") else d.get(f)
            row["rate"] = None
            row["source"] = "daily"
        psy_staff_week.append(row)
    psy_week_sum = {f: sum((x[f] or 0) for x in psy_staff_week) for f, _ in WK_COLS}

    # 周表自身窗口的合计（只用于同窗对账，不冒充本周）
    psy_wt_sum = {}
    for f, _lab in WK_COLS:
        tot = q1(c, "SELECT SUM(value) FROM fact WHERE metric_id=? "
                    "AND period_start=? AND period_end=?",
                 (f"psych.week.{f}", wt_start, wt_end))
        psy_wt_sum[f] = int(tot) if tot is not None else None
    psy_ward_attend = int(s(c, "psych.ward_attend", p_start.isoformat(), psy_end) or 0)

    # ── 个人本周排名（替代月面板里 8.31—9.26 的旧榜）─────────────
    # 口径与历史一致：加权分＝咨询量 ×2 ＋ 接触量 ×1；咨询＝住院＋门诊＋家庭，
    # 接触＝24h 首次＋情绪支持＋住院咨询。只排本周，不累计 9 月。
    def _staff_map(mid):
        return {k: int(v) for k, v in s(c, mid, p_start.isoformat(), psy_end, "staff")}

    _m_ip, _m_op, _m_fam = (_staff_map("psych.inpatient_consult"),
                            _staff_map("psych.outpatient_consult"),
                            _staff_map("psych.family_consult"))
    _m_fc, _m_em = _staff_map("psych.first_contact"), _staff_map("psych.emotion_support")
    _names = set(_m_ip) | set(_m_op) | set(_m_fam) | set(_m_fc) | set(_m_em)
    _wk_rate = {x["name"]: x["rate"] for x in psy_staff_week}
    psy_rank = []
    for _nm in _names:
        _ip, _op, _fa = _m_ip.get(_nm, 0), _m_op.get(_nm, 0), _m_fam.get(_nm, 0)
        _fc, _em = _m_fc.get(_nm, 0), _m_em.get(_nm, 0)
        _consult = _ip + _op + _fa
        _contact = _fc + _em + _ip
        psy_rank.append({"name": _nm, "consult": _consult, "contact": _contact,
                         "inpatient": _ip, "outpatient": _op, "family": _fa,
                         "emotion": _em, "first": _fc,
                         "score": _consult * 2 + _contact,
                         "rate": _wk_rate.get(_nm)})
    psy_rank.sort(key=lambda x: (-x["score"], -x["consult"], -x["contact"]))

    # 同窗对账：日报（周表窗口内）vs 周表 —— 只有窗口一致，gap 才是真差额。
    _pw_wt = psy(wt_start, wt_end)
    _ward_wt = int(s(c, "psych.ward_attend", wt_start, wt_end) or 0)
    psy_recon = []
    for lab, dv, wv in [("填报天数", _pw_wt["report"], psy_wt_sum["report_days"]),
                        ("参加查房", _ward_wt, psy_wt_sum["ward_days"]),
                        ("首次对接", _pw_wt["first"], psy_wt_sum["first"]),
                        ("情绪支持", _pw_wt["emotion"], psy_wt_sum["emotion"]),
                        ("住院咨询", _pw_wt["inpatient"], psy_wt_sum["inpatient"]),
                        ("门诊咨询", _pw_wt["outpatient"], psy_wt_sum["outpatient"]),
                        ("家庭咨询", _pw_wt["family"], psy_wt_sum["family"]),
                        ("家长访谈", _pw_wt["parent"], psy_wt_sum["parent"])]:
        gap = (dv - wv) if (dv is not None and wv is not None) else None
        psy_recon.append({"label": lab, "daily": dv, "weekly": wv, "gap": gap})

    # 本周新增对接（行数 / 去重患者数 / 按管床分组）。患者姓名不进快照，只出计数。
    def _pd(s):
        t = str(s or "").strip()
        m = re.match(r"^(\d{4})(\d{2})(\d{2})\D*$", t)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = re.match(r"^(\d{4,5})[.\-/](\d{1,2})[.\-/](\d{1,2})", t)
        if m:
            y = m.group(1)
            y = y if len(y) == 4 else "20" + y[-2:]
            return f"{y}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        return None

    bound_rows, bound_people, bound_by = 0, set(), {}
    try:
        rp = c.execute("SELECT rows_json FROM pull WHERE source_id='psych_v4' "
                       "AND sheet_name='管床心理师患者对接表' "
                       "ORDER BY pulled_at DESC LIMIT 1").fetchone()
        # pull.rows_json 有的源存 {"rows":[...]}，有的直接存二维数组，两种都要吃
        _raw = json.loads(rp[0]) if rp else []
        _rows = _raw.get("rows") if isinstance(_raw, dict) else _raw
        for r in (_rows or [])[1:]:
            if len(r) < 4 or not str(r[2] or "").strip():
                continue
            d = _pd(r[3])
            if not d or not (p_start.isoformat() <= d <= psy_end):
                continue
            if not d.startswith("2026-"):
                d = "2026-" + d[5:]
            bound_rows += 1
            bound_people.add(str(r[2]).strip())
            who = str(r[0] or "").strip() or "未指派"
            b = bound_by.setdefault(who, {"rows": 0, "people": set()})
            b["rows"] += 1
            b["people"].add(str(r[2]).strip())
    except Exception:
        pass
    bound_by = [{"name": k, "rows": v["rows"], "people": len(v["people"])}
                for k, v in sorted(bound_by.items(), key=lambda x: -x[1]["rows"])]

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

    # ⭐ 2026-10-19：管家个人项目明细来自业主微信提供的周汇总 xlsx（复诊/初诊/检查/
    #    物理治疗/心理咨询/住院/权重 七列，逐条流水里没有）。落盘在 data/extra/butler-week.json，
    #    只在该文件的 week 与本快照窗口一致时启用，避免旧周明细被当本周用。
    but_detail = None
    _bw_path = os.path.join(ROOT, "data", "extra", "butler-week.json")
    if os.path.exists(_bw_path):
        with open(_bw_path, encoding="utf-8") as _f:
            _bwd = json.load(_f)
        if _bwd.get("week") == p_start.isoformat():
            _rows = []
            for _ppl in _bwd.get("people", []):
                _ct = _ppl.get("contact") or 0
                _rows.append({**_ppl, "rate": pct(_ppl.get("admit") or 0, _ct)})
            _rows.sort(key=lambda r: (-(r.get("weight") or 0), -(r.get("contact") or 0)))
            but_detail = {"week": _bwd.get("week"), "weekEnd": _bwd.get("weekEnd"),
                          "label": _bwd.get("label"), "asOf": _bwd.get("asOf"),
                          "source": _bwd.get("source"), "nameNote": _bwd.get("_nameNote"),
                          "people": _rows, "total": _bwd.get("total"),
                          "weightSum": sum((r.get("weight") or 0) for r in _rows),
                          "admitSum": sum((r.get("admit") or 0) for r in _rows)}

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

    # ⛔ 2026-10-19 业主核查：汇报表心理咨询组表头 **自 9.21 抓取值起就没滚动过**
    #    （40 / 4 场 / 40 / 19,002 元 与《9 月报告》里 9.21—9.27 那周完全同值；
    #      10.18 23:48 的保存与 17:06 存档逐格比对，心理组 0 变动）。
    #    它不是本周填报值，按「缺项不拿旧值顶替」的契约应视为未填，
    #    本周主值改用 V4 日报逐条（唯一可核的本周口径）。表头原值存档在 header 里可查、不丢。
    dept_report = {
        "doctor": {"admit": iv(d_adm), "discharge": iv(d_dis), "outpatient": iv(d_opd),
                   "physioWan": d_phy, "revenueWan": d_rev},
        # 护理组表头同样受「汇报表未滚动」牵连：本周值置空、原值另存，避免把上周 484/5/62 当本周。
        "nursing": {"physioPeople": None if stale_ar else iv(dfact("dept.nursing.physio_people", wk_end)),
                    "recreationSessions": None if stale_ar else iv(dfact("dept.nursing.rec_sessions", wk_end)),
                    "recreationPeople": None if stale_ar else iv(dfact("dept.nursing.rec_people", wk_end)),
                    "headerStale": bool(stale_ar),
                    "headerRaw": {"physioPeople": iv(dfact("dept.nursing.physio_people", wk_end)),
                                  "recreationSessions": iv(dfact("dept.nursing.rec_sessions", wk_end)),
                                  "recreationPeople": iv(dfact("dept.nursing.rec_people", wk_end))},
                    "weeklySubmitted": nur_end is not None,
                    "weeklyThrough": nur_daily_end},
        "psychology": {
            # —— 本周主值：V4 管理表（日报逐条 + 周个人统计 + 管床对接）——
            "consult": pw["consult"], "contact": pw["contact"], "parent": pw["parent"],
            "groupSessions": pw["groupSessions"], "groupPeople": pw["groupPeople"],
            "reportDays": pw["report"],
            "bindRows": bound_rows, "bindPeople": len(bound_people),
            "boundPatients": int(bound or 0),
            # 兼容字段：individual 语义＝咨询工作量（人次）、people＝患者接触（人次）
            "individual": pw["consult"], "people": pw["contact"], "revenueYuan": None,
            # —— 汇报表表头存档（旧值，不作为本周口径）——
            "header": {"individual": iv(dfact("dept.psych.individual", wk_end)),
                       "groupSessions": iv(dfact("dept.psych.sessions", wk_end)),
                       "people": iv(dfact("dept.psych.people", wk_end)),
                       "revenueYuan": iv(dfact("dept.psych.revenue", wk_end))},
            "headerStale": True,
            "headerAsOf": "2026-09-21",
            "headerNote": "汇报表心理组表头自 2026-09-21 抓取值起未滚动，与本周 V4 不一致，已停用为本周口径",
        },
        "service": {"followup": iv(dfact("dept.service.followup", wk_end)),
                    "arrived": None if stale_ar else iv(dfact("dept.service.arrived", wk_end)),
                    "charity": None if stale_ar else iv(dfact("dept.service.charity", wk_end)),
                    "headerStale": bool(stale_ar),
                    "headerRaw": {"arrived": iv(dfact("dept.service.arrived", wk_end)),
                                  "charity": iv(dfact("dept.service.charity", wk_end)),
                                  "followup": iv(dfact("dept.service.followup", wk_end))}},
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
    # ── 医生组出院结账周报（业主 2026-11-02 提供）──────────────
    # 换周后《特别行动小组汇报表》医生组表头整行为空，本周主表没有数。
    # 业主另给《周排名分析_2026-10-26至11-01》＋《医院出院结帐明细表》，
    # 口径是「出院结账（住院自费）」——按出院日期归集，不含门诊、不含医保统筹。
    # 它与营收日报（逐日进账、含门诊）**不同源**，故单独放 doctorWeek，
    # 绝不覆盖 departments.doctor（那是汇报表口径），页面只并列展示、不相加。
    # 窗口不匹配（换周后旧的周报文件还在）就不挂，避免把上周数当本周。
    _dw_path = os.path.join(ROOT, "data", "doctor-week-2026-10-26.json")
    dept_report["doctorWeek"] = None
    if os.path.exists(_dw_path):
        try:
            with open(_dw_path, encoding="utf-8") as _f:
                _dw = json.load(_f)
        except Exception as _e:
            print(f"⚠ 医生组周报读取失败：{_e}")
            _dw = None
        if _dw and (_dw.get("period") or {}).get("start") == p_start.isoformat():
            dept_report["doctorWeek"] = _dw
            print(f"  医生组周报已接入（出院结账口径）："
                  f"{_dw['totals']['revenueWan']} 万 / 出院 {_dw['totals']['discharge']} 人 / "
                  f"在院 {_dw['totals']['inWard']} 人")
        elif _dw:
            print(f"⚠ 医生组周报窗口 {( _dw.get('period') or {}).get('start')} 与本期 "
                  f"{p_start.isoformat()} 不符，本次不挂载")

    dept_report["week"] = {"start": p_start.isoformat(), "end": wk_end,
                           "label": f"{p_start.month}.{p_start.day}—{p_end.month}.{p_end.day}",
                           "authority": "revenue_daily_report" if stale_ar else "action_report",
                           "sourceName": "营收日报（逐日台账）" if stale_ar else "特别行动小组汇报表",
                           "stale": bool(stale_ar),
                           "staleNote": ("《特别行动小组汇报表》本周表头未滚动：医生组 总收入/入院/门诊/"
                                         "物理治疗 四项与上一周逐项同值，按契约不把上周数当本周数，"
                                         "本周改用营收日报逐日台账（同天数对照）") if stale_ar else None,
                           "filledAt": q1(c, "SELECT MAX(last_pull_at) FROM source WHERE id='action_report'")}
    # 汇报表原值存档：即便判为未滚动也留着，便于业主核对「表里到底写了什么」
    dept_report["actionReportRaw"] = ar_header_raw
    dept_report["compareWeek"] = {"start": prev_start.isoformat(), "end": cmp_end.isoformat(),
                                  "revenueWan": d_rev_p if d_rev_p is not None else round(ledger_prev / 10000, 2),
                                  "admit": d_adm_p if d_adm_p is not None else
                                           int(s(c, "admit", prev_start.isoformat(), cmp_end.isoformat()) or 0),
                                  "discharge": d_dis_p if d_dis_p is not None else
                                               int(s(c, "discharge", prev_start.isoformat(), cmp_end.isoformat()) or 0),
                                  "outpatient": d_opd_p if d_opd_p is not None else
                                                int(vis_prev) if vis_prev else None,
                                  "authority": "revenue_daily_report" if stale_ar else "action_report",
                                  "days": days_recorded}

    # ── 各部门线上表「填报情况」（业主 2026-10-24：对齐各部门的线上表填写情况）──
    # 只回答两件事：①汇报表本周表头有没有滚动；②该部门真正在用的明细表填到哪一天。
    # 缺就是缺：表头空白的写 blank，不拿别的源顶替。
    _hdr = {r[0]: r[1] for r in c.execute(
        "SELECT metric_id, value FROM fact WHERE source_id='action_report' AND business_date=?",
        (wk_end,))}
    _detail_through = {r[0]: r[1] for r in c.execute(
        "SELECT source_id, MAX(business_date) FROM fact WHERE source_id<>'action_report' GROUP BY source_id")}

    def _hdr_state(keys):
        vals = [_hdr.get(k) for k in keys]
        if all(v is None for v in vals):
            return "blank"
        return "stale" if stale_ar else "ok"

    filling = {
        "checkedAt": as_of,
        "periodLabel": f"{p_start.month}.{p_start.day}—{p_end.month}.{p_end.day}",
        "actionReport": {"rolled": not stale_ar, "through": wk_end,
                         "filledAt": q1(c, "SELECT MAX(last_pull_at) FROM source WHERE id='action_report'"),
                         "note": ("汇报表本周表头与上周逐项同值，判定未滚动；本周一律不引用它"
                                  if stale_ar else "汇报表本周表头已滚动，按业主指令作为周口径权威")},
        "departments": [
            {"key": "doctor", "name": "医生组", "header": _hdr_state(
                ["dept.doctor.revenue", "dept.doctor.admit", "dept.doctor.outpatient", "dept.doctor.physio"]),
             "headerNote": "总收入 / 本周入院 / 本周门诊 / 物理治疗 四项（表头一格全组口径）",
             "detail": "营收日报逐日台账", "detailThrough": rev_through, "detailDays": days_recorded,
             "status": "stale" if stale_ar else "ok"},
            {"key": "nursing", "name": "护理组", "header": _hdr_state(
                ["dept.nursing.physio_people", "dept.nursing.rec_sessions", "dept.nursing.rec_people"]),
             "headerNote": "物理治疗人数 / 工娱场次 / 工娱人数",
             "detail": "护理部周报 + 物理治疗逐日表", "detailThrough": _detail_through.get("nursing_treat_daily"),
             "detailDays": None, "status": "stale" if stale_ar else "ok"},
            {"key": "psychology", "name": "心理咨询组", "header": _hdr_state(
                ["dept.psych.individual", "dept.psych.sessions", "dept.psych.people", "dept.psych.revenue"]),
             "headerNote": "个体咨询 / 团辅场次 / 总人数 / 总收入（该表头自 2026-09-21 起未滚动）",
             "detail": "V4 管理表·咨询师每日简报", "detailThrough": psy_end, "detailDays": psy_n,
             "status": "stale"},
            {"key": "service", "name": "客服服务部", "header": _hdr_state(
                ["dept.service.arrived", "dept.service.charity", "dept.service.followup"]),
             "headerNote": "随访人数一栏为空，到院 / 义诊有值",
             "detail": "回访台账 / 主动服务 / 日工作量", "detailThrough": svc_end, "detailDays": svc_n,
             "status": "partial"},
            {"key": "marketing", "name": "营销中心", "header": "blank",
             "headerNote": "本周入院 / 门诊 / 总收入 / 指标进度 整行空白",
             "detail": "患者有效对接表（5 名管家分表）", "detailThrough": but_end, "detailDays": but_n,
             "status": "detail_only"},
        ],
    }

    # ── 指标卡片 ──────────────────────────────────────────────
    def metric(mid, label, value, unit, **kw):
        d = {"id": mid, "label": label, "value": value, "unit": unit,
             "periodStart": p_start.isoformat(), "periodEnd": p_end.isoformat(),
             "dataThrough": dept_through, "status": "ok"}
        d.update(kw)
        return d

    metrics = {
        "monthRevenue": {"id": "monthRevenue", "label": "10月累计营收", "value": round(month_total / 10000, 2),
                         "unit": "万元", "valueYuan": round(month_total, 2), "targetWan": TARGET_WAN,
                         "amountProgress": amount_progress, "timeProgress": time_progress,
                         "gap": gap, "dataThrough": rev_through, "status": "ok",
                         "authority": month_authority, "ledgerValue": round(ledger_month / 10000, 2),
                         "ledgerThrough": rev_through,
                         "actionReportValue": round(d_month, 2) if d_month is not None else None,
                         "actionReportThrough": wk_end},
        "weekRevenue": metric("weekRevenue", "本期营收", round(week_total / 10000, 2), "万元",
                              valueYuan=round(week_total, 2), days=days_recorded,
                              deltaPct=delta(week_total, prev_total),
                              authority="revenue_daily_report" if stale_ar else "action_report",
                              ledgerValue=round(ledger_week / 10000, 2), ledgerThrough=rev_through,
                              compare=f"{prev_start.isoformat()}—{cmp_end.isoformat()} 同 {days_recorded} 天"),
        "weekOutpatient": metric("weekOutpatient", "本期门诊收入", round(out_w / 10000, 2), "万元",
                                 deltaPct=delta(out_w, out_p), authority="revenue_daily_report",
                                 note=f"营收日报台账口径，10.12—{rev_end} 逐日合计"),
        "weekInpatient": metric("weekInpatient", "本期在院收入", round(in_w / 10000, 2), "万元",
                                deltaPct=delta(in_w, in_p), authority="revenue_daily_report",
                                note=f"营收日报台账口径，10.12—{rev_end} 逐日合计"),
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
                    "dataThrough": dept_through, "status": "ok"},
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
            _mv.setdefault("periodEnd", rev_through)
            _mv["coverage"] = {"recordedDays": min(elapsed, month_days), "expectedDays": month_days,
                               "pct": round(min(elapsed, month_days) / month_days * 100, 1)}
        else:
            _mv.setdefault("periodStart", p_start.isoformat())
            _mv.setdefault("periodEnd", p_end.isoformat())
            # ⚠ 2026-10-29 修：营收日报已推进到 10.28（跨周），但周口径窗口仍是 10.19—10.25。
            #   dataThrough 原先跟着全局 data_through 走，周指标会被标成「数据至 10.28」，
            #   读者会误以为 58.35 万里含 10.26—10.28。周口径一律夹到 periodEnd。
            #   ⚠ 时点值（在院人数）例外：它就是「最新一天的时点」，不能被夹回周内。
            if not _mv.get("pointInTime"):
                _dtw = str(_mv.get("dataThrough") or p_end.isoformat())
                _mv["dataThrough"] = min(_dtw, p_end.isoformat())
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
    _nur = dept_report["nursing"].get("treatSummary") or {}
    _ins_rev = (f"本期（{p_start.month}.{p_start.day}–{p_end.month}.{p_end.day}，已录 {days_recorded} 天）营收 "
                f"{week_total/10000:.2f} 万（营收日报台账口径，汇报表本周未滚动）；上期同 {days_recorded} 天 "
                f"{prev_total/10000:.2f} 万，环比 {delta(week_total, prev_total):+.1f}%。" if stale_ar else
                f"本期（{p_start.month}.{p_start.day}–{p_end.month}.{p_end.day}，7 天）营收 "
                f"{week_total/10000:.2f} 万（汇报表口径）；上期 {prev_total/10000:.2f} 万，"
                f"{delta(week_total, prev_total):+.1f}%。")
    _ins_phy = (f"汇报表医生组本周未滚动，「物理治疗费用」一栏仍写 {_hdr_phy} 万（上周值），"
                f"按契约不引用；物理治疗按日无台账可拆，本期该指标留空待补。" if stale_ar else
                f"物理治疗费 {d_phy} 万，占本期总收入 {pct(d_phy, d_rev)}%。")
    _ins_nur = (f"护理六项治疗应做 {_nur.get('due')} 人次、实做 {_nur.get('done')} 人次，合计完成 "
                f"{_nur.get('rate')}%（护理部口径向下取整）；最低为{(_nur.get('worst') or {}).get('label')} "
                f"{(_nur.get('worst') or {}).get('rate')}%。" if _nur.get("due") else
                "护理部周报本周尚未提交（源表 latest 为上一期周末），六项治疗完成率本期留空、不拿上周数顶替。")
    insights = [
        {"id": "rev", "metricIds": ["weekRevenue"], "numbersOnly": True, "text": _ins_rev},
        {"id": "physio", "metricIds": ["weekPhysio"], "numbersOnly": True, "text": _ins_phy},
        {"id": "nursing_treat", "metricIds": ["nurseTreatRate"], "numbersOnly": True, "text": _ins_nur},
        {"id": "visit", "metricIds": ["weekVisits"], "numbersOnly": True,
         "text": f"门诊 {int(week_visits)} 人次，较上期 {int(week_visits_p)} 人次 {delta(week_visits, week_visits_p):+.1f}%；"
                 f"到院登记同日 {arr_w} 人次（含陪同，两者不合并）。"},
        {"id": "ward", "metricIds": ["wardCount", "weekAdmit", "weekDischarge"], "numbersOnly": True,
         "text": f"入院 {int(adm)}、出院 {int(dis)}，患者池净 {int(adm-dis):+d} 人；"
                 f"在院 {('—' if ward is None else str(int(ward)))} 人（{rev_through} 时点）。"},
        {"id": "psych", "metricIds": ["psych.contact"], "numbersOnly": True,
         "text": f"心理组本期日报 {pw['report']} 条（{p_start.month}.{p_start.day}–{date.fromisoformat(psy_end).month}.{date.fromisoformat(psy_end).day}，"
                 f"{psy_n} 天）：患者接触 {pw['contact']} 人次、咨询工作量 {pw['consult']} 人次，"
                 f"团体 {pw['groupSessions']} 场 / {pw['groupPeople']} 人次，家长访谈 {pw['parent']} 人次；"
                 f"上期同 {psy_n} 天 接触 {pw_prev['contact']}、咨询 {pw_prev['consult']}。"
                 f"⚠ 汇报表心理组表头（40 人 / 4 场 / 19002 元）自 9.21 起未滚动，已停用为本周口径。"},
        {"id": "service", "metricIds": ["service.followup"], "numbersOnly": True,
         "text": f"客服回访 {sw['followup']} 条、标记到院 {sw['arrived']} 人（{sw['rate']}%，{svc_n} 天）；"
                 f"上期同 {svc_n} 天 {sw_prev['followup']} 条 / {sw_prev['arrived']} 人（{sw_prev['rate']}%）。"},
        {"id": "butler", "metricIds": ["butler.contact"], "numbersOnly": True,
         "text": (f"管家有效对接 {bw['contact']} 条、转住院 {bw['admit']} 人（{bw['rate']}%，{but_n} 天），"
                  f"上期同 {but_n} 天 {bw_prev['contact']} 条 / {bw_prev['admit']} 人（{bw_prev['rate']}%）"
                  + (f"；逐人 {' / '.join('{} {}'.format(r['name'], r['contact']) for r in sorted(but_detail['people'], key=lambda r: -(r['contact'] or 0)))}，"
                     f"复诊 {but_detail['total']['revisit']} · 初诊 {but_detail['total']['first']} · "
                     f"检查 {but_detail['total']['exam']} · 物理 {but_detail['total']['physio']} · "
                     f"心理咨询 {but_detail['total']['psych']}（周汇总表 10.12—10.18）"
                     if but_detail else "")
                  + "。⚠ 营销中心表头「本周入院/门诊/总收入」本周整行空白，按契约记 null、不拿旧值顶替。")},
    ]

    # ── 冲突 / 待核 ───────────────────────────────────────────
    # 裁决规则（业主 2026-10-19 定）：凡与《特别行动小组汇报表》冲突，一律取汇报表。
    # 每条都写明双方数值与胜出方，页面据此标注，不再出现「两个数互相不认」。
    # 裁决规则（业主 2026-10-19 定）：凡与《特别行动小组汇报表》冲突，一律取汇报表；
    # ⛔ 2026-10-24 增补：若汇报表本周表头根本没滚动，则它的值不是「本周冲突的另一方」，
    #    而是「上一周的数」。此时不再做双方对账，改记一条「未填报」待核，避免把旧值当值。
    if stale_ar:
        conflicts = [
            {"id": "report_stale",
             "label": ("汇报表本周表头整行空白（五部门均未填报）" if _all_blank
                       else "汇报表本周表头未滚动（五个部门均未更新）"),
             "severity": "risk", "winner": "revenue_daily_report",
             "source_a": "action_report", "source_b": "revenue_daily_report",
             "value_a": ar_header_raw["revenueWan"], "value_b": round(ledger_week / 10000, 2),
             "detail": (
                 (f"汇报表医生组本周表头四项（总收入 / 入院 / 门诊 / 物理治疗）全部为空，"
                  f"护理组、客服组同样未填 —— 换周后源表尚未填报，"
                  f"按『缺项不拿旧值顶替』一律不引用该表，数值改取各源台账。")
                 if _all_blank else
                 (f"汇报表医生组本周四项（总收入 {ar_header_raw['revenueWan']} 万 / 入院 "
                  f"{ar_header_raw['admit']} 人 / 门诊 {ar_header_raw['outpatient']} 人次 / 物理治疗 "
                  f"{ar_header_raw['physioWan']} 万）与 10.12—10.18 那一周逐项完全相同，判定整周未滚动；"
                  f"护理组（{_hdr.get('dept.nursing.physio_people')} 人次 / {_hdr.get('dept.nursing.rec_sessions')} 场）"
                  f"、客服组（到院 {_hdr.get('dept.service.arrived')} / 义诊 {_hdr.get('dept.service.charity')}）同样未变。")
             )
             + (f"按『缺项不拿旧值顶替』，本周一律不引用该表，改用营收日报逐日台账（{days_recorded} 天 "
                f"{ledger_week/10000:.2f} 万）；原值存档在 departments.actionReportRaw，不丢、不覆盖。")},
            {"id": "month_revenue", "label": f"10月累计：台账 {ledger_month/10000:.2f} 万（至 {rev_through}）",
             "severity": "info", "winner": "revenue_daily_report",
             "source_a": "revenue_daily_report", "source_b": "",
             "value_a": round(ledger_month / 10000, 2), "value_b": None,
             "detail": (f"营收日报 10.1—{rev_through} 逐日合计 {ledger_month/10000:.2f} 万；汇报表 10 月累计一栏"
                        f"因本周未滚动而不取用，故本期只有一个可核数，不存在两套并列。")},
            {"id": "nursing_missing", "label": "护理部周报本周未提交", "severity": "warn",
             "winner": "", "source_a": "nursing_weekly", "source_b": "",
             "value_a": None, "value_b": None,
             "detail": ("护理部周报（六项治疗应做/实做）与物理治疗逐日表最新只到上一期周末，"
                        "本期完成率、逐日曲线留空，不拿上周 93% 顶替。")},
            {"id": "arrival_vs_service", "label": "到院人数两个口径并存", "severity": "info",
             "winner": "", "source_a": "arrival_register", "source_b": "",
             "value_a": arr_w, "value_b": None,
             "detail": (f"《10月到院登记表》{p_start.month}.{p_start.day}–"
                        f"{date.fromisoformat(arr_end).month}.{date.fromisoformat(arr_end).day} 逐条 {arr_w} 人次；"
                        f"客服汇报表「到院人数」本周未滚动，不再并列，避免把上周 239 当本周接待量。")},
        ]
    else:
        conflicts = [
            {"id": "week_revenue", "label": f"本周营收：汇报表 {d_rev} 万 vs 台账 {ledger_week/10000:.2f} 万", "severity": "warn",
             "winner": "action_report", "source_a": "action_report", "source_b": "revenue_daily_report",
             "value_a": d_rev, "value_b": round(ledger_week / 10000, 2),
             "detail": f"汇报表本期（{p_start.month}.{p_start.day}—{p_end.month}.{p_end.day}，7 天）总收入 {d_rev} 万；"
                       f"营收日报同期累计 {ledger_week/10000:.2f} 万。差额不是算错：汇报表是部门自填总收入，"
                       f"日报只统计门诊＋在院两列，口径宽度不同。展示值按指令取汇报表，台账原值保留、逐日图用台账。"},
            {"id": "month_revenue", "label": f"10月累计：台账 {ledger_month/10000:.2f} 万（至 {rev_through}）vs 汇报表 {d_month} 万（至 {wk_end}）", "severity": "warn",
             "winner": "revenue_daily_report", "source_a": "revenue_daily_report", "source_b": "action_report",
             "value_a": round(ledger_month / 10000, 2), "value_b": d_month,
             "detail": f"营收日报 10.1—{rev_through} 逐日合计 {ledger_month/10000:.2f} 万，本页月累计取此值；"
                       f"汇报表 10 月累计 {d_month} 万只滚到 {wk_end}。两者不同源，不相加、不互相覆盖。"},
            {"id": "doctor_detail", "label": "医生组表头与其个人明细对不上", "severity": "warn",
             "winner": "action_report", "source_a": "action_report", "source_b": "action_report",
             "value_a": d_adm, "value_b": sum_adm,
             "detail": f"表头入院 {int(d_adm)} 人、出院 {int(d_dis)} 人；6 名医生正文加总入院 {sum_adm}、"
                       f"出院 {sum_dis}，缺口 {int(d_adm)-sum_adm} 入 / {int(d_dis)-sum_dis} 出。"
                       f"空白行：{'、'.join(blank) or '无'}（该行未填，按契约记 null 不记 0）。"},
            {"id": "arrival_vs_service", "label": "到院人数两个口径并存", "severity": "info",
             "winner": "action_report", "source_a": "arrival_register", "source_b": "action_report",
             "value_a": arr_w, "value_b": dept_report["service"]["arrived"],
             "detail": f"《10月到院登记表》逐条 {arr_w} 人次；《客服服务部汇报表》本周「到院人数」"
                       f"{dept_report['service']['arrived']}（导医接待，含陪同）。含义不同，各自保留、互不加总。"},
            {"id": "physio_no_daily", "label": "物理治疗费只有周合计", "severity": "info",
             "winner": "action_report", "source_a": "action_report", "source_b": "",
             "value_a": d_phy, "value_b": None,
             "detail": f"汇报表本周物理治疗 {d_phy} 万；营收日报未按日拆分该项，无法做逐日曲线。"},
        ]
    if dept_report["marketing"]["revenueWan"] is None:
        conflicts.append({"id": "marketing_blank", "label": "营销中心本周表头未填", "severity": "info",
                          "winner": "action_report", "source_a": "action_report", "source_b": "",
                          "value_a": None, "value_b": None,
                          "detail": "汇报表「营销中心」表头行只写了部门名，入院/门诊/总收入三格为空，按契约记 null，"
                                    "不拿上周数顶替。"})
    conflicts.append({"id": "psych_header_stale", "label": "汇报表心理组表头停在 9.21 旧值，未滚动到本周", "severity": "warn",
                      "winner": "psych_v4", "source_a": "action_report", "source_b": "psych_v4",
                      "value_a": dept_report["psychology"]["header"]["individual"],
                      "value_b": pw["consult"],
                      "detail": "汇报表心理咨询组表头 40 人 / 4 场 / 40 人 / 19,002 元 自 2026-09-21 抓取值起未变化"
                                "（与《9 月报告》里 9.21—9.27 那周同值；10.18 23:48 保存与 17:06 存档逐格比对，本组 0 变动）。"
                                f"它不是本周填报值：本周 V4 咨询 {pw['consult']} 人次、接触 {pw['contact']} 人次、"
                                f"团体 {pw['groupSessions']} 场。按「缺项不拿旧值顶替」，该格视为未填，"
                                "本周改用 V4 唯一可核口径；表头原值存档在 psych.header，不丢、不覆盖。"})
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
                              "psych_v4": "V4 管理表：咨询师每日简报逐条（本周唯一口径）+ 周个人统计（起始日由组长手填，当前 10.19 未滚动，只作同窗对账）+ 管床对接；既往旧数据已清理（只留上一期起）",
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
                   "daysRecorded": days_recorded,
                   # dataThrough = 全表最新水位（页面顶部「数据至」用它）；
                   # reportDataThrough = 汇报表周口径截止；revenueDataThrough = 营收日报截止。
                   "dataThrough": rev_through,
                   # 汇报表本周未滚动时 reportDataThrough 置 null —— 页面据此显示
                   # 「主表未更新」，而不是把 10.25 这个"名义周末"当成已填报日期。
                   "reportDataThrough": None if stale_ar else wk_end,
                   "reportFilled": not stale_ar,
                   "revenueDataThrough": rev_through,
                   "authority": "revenue_daily_report" if stale_ar else "action_report"},
        # 每族各自的截止日与已录天数：不能用一个源的时间冒充全部数据截至，
        # 也不能拿「营收的 6 天」去和其他源「7 天」做环比（见前方 fam_* 注释）。
        "watermarks": {
            "dept": ({"dataThrough": rev_through, "days": days_recorded,
                      "authority": "revenue_daily_report", "reportStale": True} if stale_ar
                     else {"dataThrough": wk_end, "days": 7, "authority": "action_report"}),
            "nursing": ({"dataThrough": nur_end, "days": nur_n, "authority": "nursing_weekly",
                         "dailyThrough": nur_daily_end, "stale": nur_end is None} if nur_end is None
                        else {"dataThrough": nur_end, "days": nur_n, "authority": "nursing_weekly",
                              "dailyThrough": nur_daily_end, "stale": False}),
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
                     "periodDecision": "业主 2026-10-24 指定：本期为自然周 10.19–10.25",
                     "authority": "revenue_daily_report" if stale_ar else "action_report",
                     "authorityNote": "业主 2026-10-19 指定：与《特别行动小组汇报表》冲突的数据一律以该表为准",
                     "contractBaseline": {"periodWeeks": 2, "periodAnchor": "2026-10-05",
                                          "range": "2026-10-05—2026-10-18", "note": "契约默认两周窗，本轮不采用"}},
        "timezone": "Asia/Shanghai",
        "metrics": metrics,
        "daily": daily,
        "departments": dept_report,
        "filling": filling,
        "psych": {"week": pw, "prevSameDays": pw_prev, "staff": psy_staff,
                  "staffWeek": psy_staff_week, "weekSum": psy_week_sum, "recon": psy_recon,
                  "weekTable": {"start": wt_start, "end": wt_end, "aligned": wt_aligned,
                                "note": ("周个人统计窗口与本周一致，逐人值取表内公式"
                                         if wt_aligned else
                                         f"周个人统计表内窗口仍为 {wt_start}—{wt_end}，未滚动到本周；"
                                         f"本周逐人值改由日报逐条聚合，recon 只做同窗对账")},
                  "rank": psy_rank,
                  "header": dept_report["psychology"]["header"],
                  "headerStale": True, "headerAsOf": "2026-09-21",
                  "boundWeek": {"rows": bound_rows, "people": len(bound_people), "byStaff": bound_by},
                  "boundPatients": int(bound or 0),
                  "daily": {k: int(v) for k, v in psy_day.items()}},
        "service": {"week": sw, "prevSameDays": sw_prev, "staff": svc_staff, "staffArrived": svc_arr,
                    "daily": {k: int(v) for k, v in svc_day.items()}},
        "butler": {"week": bw, "prevSameDays": bw_prev, "staff": but_staff, "missingStaff": missing_butler,
                   "detail": but_detail,
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
