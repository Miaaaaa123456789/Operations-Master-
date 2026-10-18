#!/usr/bin/env python3
"""原始工作表 → SQLite 事实库。

- pull：原始层，按 (source, sheet, sha256) 去重，内容不变不重复入库。
- fact：规范化事实，按 (metric_id, 业务日, 维度, 来源行) 幂等。
- 缺项写 NULL，不写 0（契约 null_policy）。
"""
import glob, hashlib, json, os, re, sqlite3, sys
from datetime import date, datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_db

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "data", "raw-kdocs")
DB = os.path.join(ROOT, "db", "live-data.sqlite")
CN = timezone(timedelta(hours=8))

SOURCES = {
    "action_report": ("特别行动小组汇报表", "https://www.kdocs.cn/l/cbwp2cvTiFyK", "department_report"),
    "psych_v4": ("心理治疗与咨询组_管理表_V4", "https://www.kdocs.cn/l/cgd3nVre7qWs", "psych_daily_report"),
    "psych_visits": ("心理科来访数量", "https://www.kdocs.cn/l/coL1GfCvA0an", "psych_visit_schedule"),
    "butler_contacts": ("患者有效对接表", "https://www.kdocs.cn/l/ctlu8ktnEwi8", "contact_event_per_staff"),
    "service_followups": ("医院客服与导诊部管理规范及配套表格", "https://www.kdocs.cn/l/cuOhExpV6n29", "followup_event"),
    "arrival_register": ("10月到院登记表", "https://www.kdocs.cn/l/cp4lRRCVcqVa", "arrival_event"),
}

METRICS = [
    ("arrival.visit", "到院人次", "人次", "day", "arrival_register", "逐条计数"),
    ("arrival.new", "到院初诊", "人次", "day", "arrival_register", "初/复诊=初诊"),
    ("psych.report", "心理日报条数", "条", "day", "psych_v4", "逐条计数"),
    ("psych.first_contact", "24小时首次对接", "人次", "day", "psych_v4", "列求和"),
    ("psych.emotion_support", "日常情绪支持与干预", "人次", "day", "psych_v4", "列求和"),
    ("psych.inpatient_consult", "住院咨询", "人次", "day", "psych_v4", "列求和"),
    ("psych.outpatient_consult", "门诊咨询", "人次", "day", "psych_v4", "列求和"),
    ("psych.family_consult", "家庭咨询/治疗", "人次", "day", "psych_v4", "列求和"),
    ("psych.parent_interview", "家长访谈", "人次", "day", "psych_v4", "列求和"),
    ("psych.group_session", "团体场次", "场", "day", "psych_visits", "逐条计数"),
    ("psych.group_attendee", "团体参与人次", "人次", "day", "psych_visits", "参加人数求和"),
    ("psych.patient_bind", "新增管床对接", "人", "day", "psych_v4", "对接日期计数"),
    ("psych.ward_round", "团队查房覆盖", "%", "day", "psych_v4", "实际/应查"),
    ("butler.contact", "管家有效对接", "条", "day", "butler_contacts", "逐条计数"),
    ("butler.admit", "管家转住院", "人", "day", "butler_contacts", "住院列非空"),
    ("service.followup", "回访条数", "条", "day", "service_followups", "逐条计数"),
    ("service.arrived", "回访后到院", "人", "day", "service_followups", "是否到院=是"),
    ("service.guide", "导诊主动服务", "条", "day", "service_followups", "逐条计数"),
    ("service.workload", "导医工作量分", "分", "day", "service_followups", "当日总分求和"),
    # ── 特别行动小组汇报表（部门周报口径，业主 2026-10-19 指定为冲突裁决方）──
    ("dept.doctor.admit", "医生组本周入院", "人", "week", "action_report", "表头本周入院人数"),
    ("dept.doctor.discharge", "医生组本周出院", "人", "week", "action_report", "科主任正文第N周出院"),
    ("dept.doctor.outpatient", "医生组本周门诊", "人次", "week", "action_report", "表头本周门诊人数"),
    ("dept.doctor.physio", "医生组物理治疗费", "万元", "week", "action_report", "表头物理治疗费用"),
    ("dept.doctor.revenue", "医生组本周总收入", "万元", "week", "action_report", "表头总收入"),
    ("dept.doctor.staff_admit", "医生组个人入院", "人", "week", "action_report", "正文『本周入N人』"),
    ("dept.doctor.staff_discharge", "医生组个人出院", "人", "week", "action_report", "正文『出N人』"),
    ("dept.doctor.staff_convert", "医生组个人转化", "人", "week", "action_report", "正文『本周转化N人』"),
    ("dept.doctor.staff_duodao", "医生组个人多导", "人", "week", "action_report", "正文『多导N人』"),
    ("dept.nursing.physio_people", "护理组物理治疗人次", "人次", "week", "action_report", "表头物理治疗人数"),
    ("dept.nursing.rec_sessions", "护理组工娱场次", "场", "week", "action_report", "表头工娱场次"),
    ("dept.nursing.rec_people", "护理组工娱人次", "人次", "week", "action_report", "表头工娱人数"),
    ("dept.psych.individual", "心理组个体咨询", "人", "week", "action_report", "表头个体咨询人数"),
    ("dept.psych.sessions", "心理组团辅场次", "场", "week", "action_report", "表头团辅场次"),
    ("dept.psych.people", "心理组总人数", "人", "week", "action_report", "表头总人数"),
    ("dept.psych.revenue", "心理组总收入", "元", "week", "action_report", "表头总收入"),
    ("dept.service.followup", "客服组随访人数", "人", "week", "action_report", "表头随访人数"),
    ("dept.service.arrived", "客服组到院人数", "人次", "week", "action_report", "表头到院人数（导医接待）"),
    ("dept.service.charity", "客服组义诊人数", "人", "week", "action_report", "表头义诊人数"),
    ("dept.marketing.admit", "营销中心本周入院", "人", "week", "action_report", "表头本周入院人数"),
    ("dept.marketing.outpatient", "营销中心本周门诊", "人次", "week", "action_report", "表头本周门诊人数"),
    ("dept.marketing.revenue", "营销中心本周总收入", "万元", "week", "action_report", "表头总收入"),
]


def norm_date(s):
    """业务日归一。只接受合法月/日；明显手误（年份 2020 的 9 月）按 2026 处理并留痕。"""
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 < y < 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
            if y == 2020 and mo == 9:      # 源表手误：2020-09-20 实为 2026-09-20
                y = 2026
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return None
    m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})$", s)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"2026-{mo:02d}-{d:02d}"
    return None


def num(s):
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in ("", "/", "—", "-", "无"):
        return None
    m = re.search(r"-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None


def conn():
    return live_db.connect(DB)


def ensure_meta(c):
    for sid, (name, url, grain) in SOURCES.items():
        c.execute("INSERT OR IGNORE INTO source(id,name,url,grain) VALUES(?,?,?,?)", (sid, name, url, grain))
    for row in METRICS:
        c.execute("INSERT OR IGNORE INTO metric_def(id,label,unit,grain,source_id,formula) VALUES(?,?,?,?,?,?)", row)
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('period_weeks','1')")
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('period_anchor','2026-10-12')")
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('period_basis','natural_week')")


def hkey(*parts):
    """行级稳定键：由业务自然键哈希，避免源表插入/删除行导致行号漂移而重复计数。"""
    raw = "|".join("" if p is None else str(p).strip() for p in parts)
    return "k" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def add_fact(c, metric, date, value, source, sheet, row_ref, dim_key=None, dim_value=None, unit=None, status="ok"):
    if value is None and status == "ok":
        status = "missing"
    dim_key = "" if dim_key is None else str(dim_key)
    dim_value = "" if dim_value is None else str(dim_value)
    c.execute(
        """INSERT OR REPLACE INTO fact(metric_id,business_date,dim_key,dim_value,value,unit,source_id,sheet_name,row_ref,status,fetched_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (metric, date, dim_key, dim_value, value, unit, source, sheet, row_ref, status,
         datetime.now(CN).isoformat(timespec="seconds")),
    )


def add_week_fact(c, metric, week, value, source, sheet, row_ref,
                  dim_key=None, dim_value=None, unit=None):
    """周粒度事实：business_date 记周末日，period_start/end 记窗口。缺项仍记 NULL。"""
    a, b = week
    c.execute(
        """INSERT OR REPLACE INTO fact(metric_id,business_date,period_start,period_end,
               dim_key,dim_value,value,unit,source_id,sheet_name,row_ref,status,fetched_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (metric, b.isoformat(), a.isoformat(), b.isoformat(), dim_key or "", dim_value or "",
         value, unit, source, sheet, row_ref,
         "ok" if value is not None else "missing",
         datetime.now(CN).isoformat(timespec="seconds")),
    )


def dept_weeks(c):
    """第1/2/3 周窗口。锚点取 settings.period_anchor（本周自然周起始日）。"""
    row = c.execute("SELECT value FROM settings WHERE key='period_anchor'").fetchone()
    anchor = date.fromisoformat(row[0]) if row else date(2026, 10, 12)
    w3s = anchor
    w2e = w3s - timedelta(days=1)
    w2s = w2e - timedelta(days=6)
    w1s = w2s.replace(day=1)
    w1e = w2s - timedelta(days=1)
    return {1: (w1s, w1e), 2: (w2s, w2e), 3: (w3s, w3s + timedelta(days=6))}


# 表头 → (metric_id, 单位)。同一张表内表头可能重复（合并单元格），只取首个。
SHEET_FIELDS = {
    "医生组": {
        "本周入院人数": ("dept.doctor.admit", "人"),
        "本周门诊人数": ("dept.doctor.outpatient", "人次"),
        "物理治疗费用": ("dept.doctor.physio", "万元"),
        "总收入": ("dept.doctor.revenue", "万元"),
    },
    "护理组": {
        "物理治疗人数": ("dept.nursing.physio_people", "人次"),
        "工娱场次": ("dept.nursing.rec_sessions", "场"),
        "工娱人数": ("dept.nursing.rec_people", "人次"),
    },
    "心理咨询组": {
        "个体咨询人数": ("dept.psych.individual", "人"),
        "团辅场次": ("dept.psych.sessions", "场"),
        "总人数": ("dept.psych.people", "人"),
        "总收入": ("dept.psych.revenue", "元"),
    },
    "客服服务部": {
        "随访人数": ("dept.service.followup", "人"),
        "到院人数": ("dept.service.arrived", "人次"),
        "义诊人数": ("dept.service.charity", "人"),
    },
    "营销中心": {
        "本周入院人数": ("dept.marketing.admit", "人"),
        "本周门诊人数": ("dept.marketing.outpatient", "人次"),
        "总收入": ("dept.marketing.revenue", "万元"),
    },
}


def _norm_head(s):
    """表头归一：去掉括号补充说明与换行，『物理治疗人数（含住院、门诊）』→『物理治疗人数』。"""
    return re.sub(r"[（(].*?[）)]", "", (s or "").replace("\n", "")).strip()


def _clean_week(seg):
    """把『第1周（10.1-10.4）：』里的括号日期去掉，避免被当成数值。"""
    return re.sub(r"第([123])周[（(][^）)]{0,24}[）)]", r"第\1周", seg)


def _triplet(seg):
    """从一段正文里取第1/2/3周的第一个数（源表常有重复周次，取首个）。"""
    out = {}
    for m in re.finditer(r"第([123])周[：:]\s*([\d.]+)", _clean_week(seg)):
        out.setdefault(int(m.group(1)), float(m.group(2)))
    return out


def _slice(text, a, b=None, last_b=False):
    i = text.find(a)
    if i < 0:
        return ""
    if b is None:
        return text[i:]
    j = text.rfind(b) if last_b else text.find(b, i + len(a))
    return text[i:j] if j > i else text[i:]


def ingest_dept(c, sheet, rows):
    """特别行动小组：表头本周值 + 医生组正文里的第1/2/3周轨迹 + 个人明细。"""
    weeks = dept_weeks(c)

    def cell(r, i):
        return rows[r][i].strip() if r < len(rows) and i < len(rows[r]) else ""

    fields = SHEET_FIELDS.get(sheet)
    if fields is None:
        return
    # 表头行固定第 1 行、数值行第 2 行；合并单元格会让同一表头重复，只取首个列
    idx = {}
    for i in range(len(rows[1]) if len(rows) > 1 else 0):
        h = _norm_head(cell(1, i))
        if h in fields and h not in idx:
            idx[h] = i

    def val(h):
        i = idx.get(h)
        return num(cell(2, i)) if i is not None else None

    for h, (mid, unit) in fields.items():
        add_week_fact(c, mid, weeks[3], val(h), "action_report", sheet,
                      hkey("dept", sheet, h), unit=unit)

    if sheet != "医生组":
        return

    # ── 医生组正文：前三周轨迹 + 出院（表头没有出院这一格）──
    txt = cell(6, 7)
    rev = _triplet(_slice(txt, "总费用", "物理治疗"))
    phy = _triplet(_slice(txt, "物理治疗", "入院："))
    adm = _triplet(_slice(txt, "入院：", "出院"))
    dis = _triplet(_slice(txt, "出院", "门诊：", last_b=True))
    opd = _triplet(txt[txt.rfind("门诊："):]) if "门诊：" in txt else {}

    for k in (1, 2, 3):
        wk = weeks[k]
        # ⛔ 第3周的四项表头已在上方按「表头口径」写过一次；这里若再用另一 row_ref 写一遍，
        #    SUM 会翻倍。第3周只补表头没有的「出院」，其余跳过。
        if k == 3:
            add_week_fact(c, "dept.doctor.discharge", wk, dis.get(k), "action_report", sheet,
                          hkey("dept-hist", "discharge", k), unit="人")
            continue
        pair = [(rev.get(k), "dept.doctor.revenue", "万元"),
                (phy.get(k), "dept.doctor.physio", "万元"),
                (adm.get(k), "dept.doctor.admit", "人"),
                (opd.get(k), "dept.doctor.outpatient", "人次")]
        for v, mid, unit in pair:
            add_week_fact(c, mid, wk, v, "action_report", sheet,
                          hkey("dept-hist", mid, k), unit=unit)
        add_week_fact(c, "dept.doctor.discharge", wk, dis.get(k), "action_report", sheet,
                      hkey("dept-hist", "discharge", k), unit="人")

    # ── 个人明细：本周入/出、转化、多导 ──
    for i in range(6, len(rows)):
        mc = cell(i, 1)
        mm = re.search(r"[（(]([^）)]+)[）)]", mc)
        if not mm:
            continue
        name = mm.group(1).strip()
        body = ""
        for j in range(len(rows[i]) - 1, -1, -1):
            if cell(i, j):
                body = cell(i, j)
                break
        head = re.split(r"[；;]", body)[0]          # 只取「本周」那半句，别吃到历史月份
        ref = hkey("dept-staff", name)
        pat = {
            "dept.doctor.staff_admit": (r"本周入\s*(\d+)\s*人", "人"),
            "dept.doctor.staff_discharge": (r"出\s*(\d+)\s*人", "人"),
            "dept.doctor.staff_convert": (r"本周转化\s*(\d+)\s*人", "人"),
            "dept.doctor.staff_duodao": (r"多导\s*(\d+)\s*人", "人"),
        }
        for mid, (p, unit) in pat.items():
            m = re.search(p, head)
            add_week_fact(c, mid, weeks[3], float(m.group(1)) if m else None,
                          "action_report", sheet, ref, "staff", name, unit)


def ingest_sheet(c, source, sheet_name, rows, pulled_at):
    """按来源把二维表拆成事实。行号写进 row_ref 便于回溯。"""
    def cell(r, i):
        return rows[r][i].strip() if r < len(rows) and i < len(rows[r]) else ""

    if source == "action_report":
        ingest_dept(c, sheet_name, rows)
        return

    if source == "arrival_register":
        for i in range(1, len(rows)):
            d = norm_date(cell(i, 1))
            if not d:
                continue
            kind = cell(i, 5)
            ref = hkey(d, cell(i, 2), cell(i, 4))
            add_fact(c, "arrival.visit", d, 1, source, sheet_name, ref, "channel", cell(i, 6) or "未填")
            if "初" in kind:
                add_fact(c, "arrival.new", d, 1, source, sheet_name, ref, "channel", cell(i, 6) or "未填")

    elif source == "psych_v4" and sheet_name == "咨询师每日简报":
        cols = {"psych.first_contact": 6, "psych.emotion_support": 7, "psych.inpatient_consult": 8,
                "psych.outpatient_consult": 9, "psych.family_consult": 10, "psych.parent_interview": 11}
        for i in range(4, len(rows)):
            d = norm_date(cell(i, 0))
            if not d:
                continue
            staff = re.sub(r"^(咨询师|治疗师|组长)[（(]", "", cell(i, 1)).rstrip("）)")
            ref = hkey(d, staff)
            add_fact(c, "psych.report", d, 1, source, sheet_name, ref, "staff", staff)
            for mid, ci in cols.items():
                add_fact(c, mid, d, num(cell(i, ci)), source, sheet_name, ref, "staff", staff)

    elif source == "psych_v4" and sheet_name == "管床心理师患者对接表":
        for i in range(1, len(rows)):
            d = norm_date(cell(i, 3))
            if not d or not cell(i, 2):
                continue
            add_fact(c, "psych.patient_bind", d, 1, source, sheet_name,
                     hkey(d, cell(i, 0), cell(i, 2)), "staff", cell(i, 0))

    elif source == "psych_v4" and sheet_name == "团队查房日报":
        for i in range(4, len(rows)):
            d = norm_date(cell(i, 0))
            if not d:
                continue
            should, actual = num(cell(i, 2)), num(cell(i, 3))
            if should:
                add_fact(c, "psych.ward_round", d, round(actual / should * 100, 1) if actual is not None else None,
                         source, sheet_name, hkey(d))

    elif source == "psych_visits" and sheet_name == "团体治疗登记":
        for i in range(3, len(rows)):
            d = norm_date(cell(i, 1))
            if not d:
                continue
            ref = hkey(d, cell(i, 2)[:20], cell(i, 3))
            add_fact(c, "psych.group_session", d, 1, source, sheet_name, ref, "topic", cell(i, 2)[:20])
            add_fact(c, "psych.group_attendee", d, num(cell(i, 5)) or 0, source, sheet_name, ref, "topic", cell(i, 2)[:20])

    elif source == "butler_contacts":
        staff = sheet_name
        for i in range(1, len(rows)):
            d = norm_date(cell(i, 1))
            if not d or not cell(i, 2):
                continue
            ref = hkey(d, cell(i, 2), staff)
            add_fact(c, "butler.contact", d, 1, source, sheet_name, ref, "staff", staff)
            if cell(i, 7) not in ("", "否", "/"):
                add_fact(c, "butler.admit", d, 1, source, sheet_name, ref, "staff", staff)

    elif source == "service_followups" and sheet_name == "标准化回访台账":
        for i in range(2, len(rows)):
            d = norm_date(cell(i, 1))
            if not d:
                continue
            staff = cell(i, 2)
            ref = hkey(d, staff, cell(i, 3), cell(i, 6))
            add_fact(c, "service.followup", d, 1, source, sheet_name, ref, "staff", staff)
            if cell(i, 11) == "是":
                add_fact(c, "service.arrived", d, 1, source, sheet_name, ref, "staff", staff)

    elif source == "service_followups" and sheet_name == "导诊主动服务记录表":
        for i in range(2, len(rows)):
            d = norm_date(cell(i, 1))
            if not d:
                continue
            add_fact(c, "service.guide", d, 1, source, sheet_name,
                     hkey(d, cell(i, 2), cell(i, 3)), "staff", cell(i, 2))

    elif source == "service_followups" and sheet_name == "日工作量考核表":
        for i in range(3, len(rows)):
            d = norm_date(cell(i, 1))
            if not d or not cell(i, 0):
                continue
            add_fact(c, "service.workload", d, num(cell(i, 18)), source, sheet_name,
                     hkey(d, cell(i, 0)), "staff", cell(i, 0))


def main():
    c = conn()
    ensure_meta(c)
    total_pull = 0
    for path in sorted(glob.glob(os.path.join(RAW, "*", "*.json"))):
        d = json.load(open(path))
        src, sheet, rows = d["source"], d["sheetName"], d["rows"]
        blob = json.dumps(rows, ensure_ascii=False).encode()
        sha = hashlib.sha256(blob).hexdigest()
        before = c.total_changes
        c.execute(
            "INSERT OR IGNORE INTO pull(source_id,sheet_id,sheet_name,pulled_at,row_count,sha256,rows_json) VALUES(?,?,?,?,?,?,?)",
            (src, d.get("sheetId"), sheet, d.get("pulledAt") or datetime.now(CN).isoformat(), len(rows), sha, json.dumps(rows, ensure_ascii=False)),
        )
        is_new = c.total_changes > before
        # 该表本次重抓：先清空旧事实，避免键规则升级/行数变化导致残留重复
        c.execute("DELETE FROM fact WHERE source_id=? AND sheet_name=?", (src, sheet))
        total_pull += 1 if is_new else 0
        ingest_sheet(c, src, sheet, rows, d.get("pulledAt"))
        # 更新源状态：数据截至＝该表不晚于今天的最大业务日
        today = datetime.now(CN).strftime("%Y-%m-%d")
        row = c.execute(
            "SELECT MAX(business_date) FROM fact WHERE source_id=? AND sheet_name=? AND business_date<=?",
            (src, sheet, today)).fetchone()
        dt = row[0] if row and row[0] else None
        c.execute("""UPDATE source SET last_pull_at=?,
                       data_through = CASE
                         WHEN ? IS NULL THEN data_through
                         WHEN data_through IS NULL OR ? > data_through THEN ?
                         ELSE data_through END
                     WHERE id=?""",
                  (datetime.now(CN).isoformat(timespec="seconds"), dt, dt, dt, src))
    c.commit()
    print(f"工作表 {total_pull} 张为新内容（其余未变化未重复入库）")
    for r in c.execute("SELECT id,last_pull_at,data_through FROM source ORDER BY id"):
        print("  源", r)
    print("事实行数", c.execute("SELECT COUNT(*) FROM fact").fetchone()[0])
    for r in c.execute("SELECT metric_id,COUNT(*),MIN(business_date),MAX(business_date) FROM fact GROUP BY metric_id"):
        print("  ", r)


if __name__ == "__main__":
    main()
