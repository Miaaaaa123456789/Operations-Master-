#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整周收口取数 —— 为「医院经营看板」生成一周的完整口径与环比

用法：
    python3 scripts/week-rollup.py                          # 默认：最近一个已完整结束的自然周（周一—周日）
    python3 scripts/week-rollup.py --week-start 2026-09-14  # 指定周起始（周一）
    python3 scripts/week-rollup.py --json out.json          # 同时写机器可读 JSON

口径约定（与业主一致）：
    · 周 = 周一 — 周日（源表「周起始日 / 周结束日」）
    · 环比一律用「上周同期、同天数」，并写明天数与区间
    · 本周未结束时，只给「截至今日」的进度，不给周环比结论

数据源（三张金山表）：
    1. 特别行动小组汇报表   link cbwp2cvTiFyK  —— 主表（部门汇总，周更；用 kdocs-ingest.js 抓）
    2. 心理管理表 V4        file fdg34kWW8xM3A1fVCrSP1xhVhBazPDzkt —— 「咨询师每日简报」逐条日报
    3. 患者有效对接表       file zTTYxTcbJxMXBcbnnZ8ZrxTDRareiGEH9 —— 一人一表，逐条对接
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

KDOCS_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ["PATH"]}
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PSY_FILE = "fdg34kWW8xM3A1fVCrSP1xhVhBazPDzkt"
PSY_SHEET = "咨询师每日简报"
GJ_FILE = "zTTYxTcbJxMXBcbnnZ8ZrxTDRareiGEH9"
GJ_SHEETS = {1: "菲菲", 2: "国威", 3: "金林", 4: "朱婧(婧姐)", 6: "利娟"}

# 咨询师每日简报列序（0-based）
PSY_COLS = {6: "首次对接", 7: "床旁支持", 8: "情绪干预", 9: "住院咨询",
            10: "门诊咨询", 11: "家庭咨询", 12: "家长反馈", 13: "家长访谈", 14: "拒绝"}
CONTACT_F = ("首次对接", "床旁支持", "情绪干预")
ADVICE_F = ("住院咨询", "门诊咨询", "家庭咨询")
PARENT_F = ("家长反馈", "家长访谈")
PSY_NAMES = ["杨霞", "冯浩鹏", "蔡宜蓉", "王沛然", "赵芳", "陈鹏"]

YES = {"是", "√", "1", "Y", "y", "✓", "v"}


def kdocs(*args):
    r = subprocess.run(["kdocs-cli", *args], capture_output=True, text=True, env=KDOCS_ENV)
    out = r.stdout
    i = out.find("{")
    if i < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(out[i:])
        return obj
    except Exception:
        return None


def num(v):
    s = str(v).strip().replace(",", "")
    try:
        return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else 0.0
    except Exception:
        return 0.0


def name_of(v):
    s = str(v).strip()
    m = re.search(r"[（(]([^)）]+)[)）]", s)
    return m.group(1) if m else s


# ---------------------------------------------------------------- 心理组
def read_psy_chunk(fr, tr):
    obj = kdocs("drive", "read-file", json.dumps({
        "file_id": PSY_FILE, "sheet_name": PSY_SHEET,
        "sheet_range": {"row_from": fr, "row_to": tr, "col_from": 0, "col_to": 22}}))
    if not obj:
        return None
    d = (obj.get("data") or {}).get("content") or {}
    cells = ((d.get("range_data") or {}).get("detail") or {}).get("rangeData") or []
    if not cells:
        return []
    rows = max(c.get("rowTo", 0) for c in cells) + 1
    cols = max(c.get("colTo", 0) for c in cells) + 1
    g = [["" for _ in range(cols)] for _ in range(rows)]
    for c in cells:
        g[c.get("rowFrom", 0)][c.get("colFrom", 0)] = c.get("cellText", "")
    return g


def fetch_psy_records():
    """返回逐条日报记录（只保留有日期的行）"""
    recs = []
    fr, step = 3, 120
    while fr < 1200:
        g = read_psy_chunk(fr, min(fr + step - 1, 1200))
        if g is None:
            print("  [心理] 读取失败 @ 行 %d" % fr, file=sys.stderr)
            break
        for i, row in enumerate(g):
            d = str(row[0]).strip()[:10] if row else ""
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
                continue
            nm = name_of(row[1]) if len(row) > 1 else ""
            if not nm:
                continue
            rec = {"date": d, "name": nm,
                   "shift": str(row[2]).strip() if len(row) > 2 else ""}
            for c, k in PSY_COLS.items():
                rec[k] = num(row[c]) if len(row) > c else 0.0
            recs.append(rec)
        if len(g) < step:
            break
        fr += step
    return recs


def psy_agg(recs, lo, hi):
    a = defaultdict(lambda: defaultdict(float))
    days = defaultdict(set)
    for r in recs:
        if lo <= r["date"] <= hi:
            for k in PSY_COLS.values():
                a[r["name"]][k] += r[k]
            days[r["name"]].add(r["date"])
    return a, days


# ---------------------------------------------------------------- 管家组
def fetch_gj():
    all_data = {}
    for sid, name in GJ_SHEETS.items():
        rows, fr = {}, 0
        while fr < 400:
            obj = kdocs("sheet", "get-range-data", json.dumps({
                "file_id": GJ_FILE, "worksheet_id": sid,
                "range": {"rowFrom": fr, "rowTo": min(fr + 99, 400),
                          "colFrom": 0, "colTo": 12}}))
            if not obj:
                break
            d = obj.get("data") or {}
            cells = (d.get("detail") or {}).get("rangeData") or d.get("rangeData") or []
            if not cells:
                break
            for c in cells:
                r, cc = c.get("rowFrom", 0), c.get("colFrom", 0)
                t = str(c.get("cellText", "")).strip()
                if t or cc == 0:
                    rows.setdefault(r, {})[cc] = t
            last = max(rows) if rows else 0
            if last < fr + 99:
                break
            fr = last
        all_data[name] = rows
    return all_data


def gj_agg(all_data, lo, hi):
    """按周归集；日期留空继承上一行；只跳表头行，靠业务标记判有效性"""
    res = {}
    for name, rows in all_data.items():
        c, last = Counter(), None
        for rk in sorted(rows, key=lambda x: int(x)):
            r = rows[rk]
            if str(r.get(0, "")).strip() == "序号":
                continue
            if str(r.get(1, "")).strip() == "日期" and str(r.get(2, "")).strip() == "患者姓名":
                continue
            ds = str(r.get(1, "")).strip()
            m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})$", ds)
            if m:
                y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
                last = "%04d-%02d-%02d" % (y, mo, dd) if 1900 <= y <= 2100 and 1 <= mo <= 12 else last
            ds = last
            if not (ds and lo <= ds <= hi):
                continue
            # 有效性：患者姓氏 / 初诊复诊 / 任一业务标记，至少一项
            if not any(str(r.get(cc, "")).strip() for cc in (2, 3, 4, 5, 6, 7)):
                continue
            c["对接"] += 1
            if any(str(r.get(4, "")).strip() == v for v in YES):
                c["检查"] += 1
            if any(str(r.get(5, "")).strip() == v for v in YES):
                c["物理"] += 1
            if str(r.get(6, "")).strip():
                c["心理"] += 1
            if any(str(r.get(7, "")).strip() == v for v in YES):
                c["住院"] += 1
        res[name] = c
    return res


# ---------------------------------------------------------------- 主表
def check_main_table():
    """看主表最新抓取里，部门表头是否已是新一周"""
    import glob
    fs = sorted(glob.glob(os.path.join(REPO, "data/raw/discover-*.json")), key=os.path.getmtime)
    if not fs:
        return None
    A = json.load(open(fs[-1]))
    out = {"fetchedAt": A.get("fetchedAt"), "file": os.path.basename(fs[-1]), "heads": {}}
    for dept in ["doctor", "nursing", "psychology", "service", "marketing"]:
        cells = (A.get("sheets") or {}).get(dept, {}).get("cells") or []
        r2 = {}
        for c in cells:
            if c.get("r") == 2 and str(c.get("text", "")).strip():
                r2[c.get("c")] = c.get("text")
        out["heads"][dept] = r2
    if len(fs) > 1:
        B = json.load(open(fs[-2]))
        out["prevFetchedAt"] = B.get("fetchedAt")
    return out


# ---------------------------------------------------------------- 输出
def week_bounds(week_start):
    ws = dt.date.fromisoformat(week_start)
    return ws.isoformat(), (ws + dt.timedelta(days=6)).isoformat()


def prev_week(week_start):
    ws = dt.date.fromisoformat(week_start) - dt.timedelta(days=7)
    return ws.isoformat(), (ws + dt.timedelta(days=6)).isoformat()


def bar(v, mx, w=24):
    n = 0 if not mx else int(round(v / mx * w))
    return "█" * n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-start", default=None, help="周起始（周一），默认取最近一个已结束的周")
    ap.add_argument("--json", default=None, help="同时写 JSON 报告")
    args = ap.parse_args()

    today = dt.date.today()
    if args.week_start:
        ws = args.week_start
    else:
        # 最近一个「已完整结束」的周：向前找到最近的周一，若本周尚未结束则再退一周
        monday = today - dt.timedelta(days=today.weekday())
        ws = (monday - dt.timedelta(days=7)).isoformat() if monday + dt.timedelta(days=6) >= today \
            else monday.isoformat()
    lo, hi = week_bounds(ws)
    plo, phi = prev_week(ws)
    complete = hi < today.isoformat()

    print("=" * 78)
    print("完整周收口报告   本周 %s — %s（%s）" % (lo, hi, "已结束" if complete else "进行中"))
    print("                 上周 %s — %s（同期同长短）" % (plo, phi))
    print("=" * 78)

    # ---------- 主表 ----------
    print("\n【主表】特别行动小组汇报表（周更）")
    mt = check_main_table()
    if mt:
        print("  最新抓取 %s（%s）" % (mt["fetchedAt"][:19], mt["file"]))
        for dept, v in mt["heads"].items():
            if v:
                print("    %-11s %s" % (dept, " | ".join("%s=%s" % (k, x) for k, x in sorted(v.items()))))
        print("  → 表头若仍为旧周，说明主表未更新，Hero 主数字/核心指标/问题链路应保持不动")
    else:
        print("  未找到 data/raw/discover-*.json")

    # ---------- 心理组 ----------
    print("\n【心理组】管理表 V4 · 咨询师每日简报")
    recs = fetch_psy_records()
    if not recs:
        print("  读取失败")
    else:
        recs.sort(key=lambda x: (x["date"], x["name"]))
        print("  共 %d 条有效日报（%s ~ %s）" % (len(recs), recs[0]["date"], recs[-1]["date"]))
        a_c, d_c = psy_agg(recs, lo, hi)
        a_p, d_p = psy_agg(recs, plo, phi)
        # 「累计」必须限定本次统计区间的下界：源表存在日期写成 2020-09-20 的异常行，
        # 用 2000—2099 这种全开区间会把它们计入，导致累计数值偏高（已实测差 8 人次接触）。
        a_all, d_all = psy_agg(recs, "2026-08-31", hi)

        def tot(a, fs):
            return int(sum(a[n][k] for n in a for k in fs))

        print("\n  ── 本周 vs 上周（同期同长短）──")
        print("  %-12s %8s %8s %9s" % ("口径", "本周", "上周", "环比"))
        for lab, fs in [("患者接触", CONTACT_F), ("咨询工作量", ADVICE_F), ("家长工作", PARENT_F)]:
            c, p = tot(a_c, fs), tot(a_p, fs)
            r = "%+.1f%%" % ((c - p) / p * 100) if p else "—"
            print("  %-12s %8d %8d %9s" % (lab, c, p, r))

        print("\n  ── 本周逐人 ──")
        print("  %-7s %4s %7s %7s %7s" % ("姓名", "天数", "接触", "咨询", "家长"))
        for n in PSY_NAMES:
            a = a_c[n]
            print("  %-7s %4d %7d %7d %7d" % (
                n, len(d_c.get(n, set())),
                int(sum(a[k] for k in CONTACT_F)), int(sum(a[k] for k in ADVICE_F)),
                int(sum(a[k] for k in PARENT_F))))
        T = [int(sum(a_c[n][k] for n in a_c for k in fs)) for fs in (CONTACT_F, ADVICE_F, PARENT_F)]
        print("  %-7s %4s %7d %7d %7d" % ("合计", "", T[0], T[1], T[2]))

        print("\n  ── 累计（自 8.31 起，用于累计排名）──")
        print("  %-7s %4s %7s %7s %7s" % ("姓名", "天数", "接触", "咨询", "家长"))
        for n in PSY_NAMES:
            a = a_all[n]
            print("  %-7s %4d %7d %7d %7d" % (
                n, len(d_all.get(n, set())),
                int(sum(a[k] for k in CONTACT_F)), int(sum(a[k] for k in ADVICE_F)),
                int(sum(a[k] for k in PARENT_F))))

        miss = [n for n in PSY_NAMES if n not in d_c]
        print("\n  本周未填报：%s%s" % ("、".join(miss) if miss else "无",
                                  "（需先确认为休假还是漏报）" if miss else ""))
        print("  本周填报日数：%s" % " / ".join("%s %d 天" % (n, len(d_c[n])) for n in PSY_NAMES if n in d_c))

    # ---------- 管家组 ----------
    print("\n【管家组】患者有效对接表")
    gj = fetch_gj()
    if not gj:
        print("  读取失败")
    else:
        g_c = gj_agg(gj, lo, hi)
        g_p = gj_agg(gj, plo, phi)
        def pick(n):
            """表名可能是「朱婧(婧姐)」这种，用包含匹配"""
            for k in gj:
                if n in k:
                    return k
            return None

        print("  ── 本周 vs 上周（同期同长短）──")
        print("  %-10s %6s %6s %6s %6s %6s" % ("管家", "对接", "检查", "物理", "心理", "住院"))
        for n in ["金林", "朱婧", "菲菲", "国威", "利娟"]:
            k = pick(n)
            c = g_c.get(k, Counter()) if k else Counter()
            print("  %-10s %6d %6d %6d %6d %6d" % (n, c["对接"], c["检查"], c["物理"], c["心理"], c["住院"]))
        T = Counter()
        for c in g_c.values():
            T.update(c)
        P = Counter()
        for c in g_p.values():
            P.update(c)
        print("  %-10s %6d %6d %6d %6d %6d" % ("本周合计", T["对接"], T["检查"], T["物理"], T["心理"], T["住院"]))
        print("  %-10s %6d %6d %6d %6d %6d" % ("上周同期", P["对接"], P["检查"], P["物理"], P["心理"], P["住院"]))
        r = "%+.1f%%" % ((T["对接"] - P["对接"]) / P["对接"] * 100) if P["对接"] else "—"
        print("\n  对接环比：%d → %d（%s）" % (P["对接"], T["对接"], r))
        # 自检锚点：2026-09-07~09-13 是已与业主明细对平的完整周，对接应为 78
        g_anchor = gj_agg(gj, "2026-09-07", "2026-09-13")
        ca = sum(c["对接"] for c in g_anchor.values())
        if ca:
            print("  ※ 自检：9.7—9.13 对接合计 = %d%s"
                  % (ca, "（与业主明细 78 一致 ✓）" if ca == 78 else "（≠78，请检查过滤条件！）"))

    print("\n" + "=" * 78)
    print("下一步：以上新数据按「本周为先」替换看板各部门指标、排名、AI 分析与信号卡；")
    print("        环比一律标注「上周同期（同天数）」；未填报人员先确认休假/漏报再定性。")
    print("=" * 78)

    if args.json:
        json.dump({"week": [lo, hi], "prevWeek": [plo, phi], "complete": complete,
                   "mainTable": mt, "psychCount": len(recs), "gjSheets": list(gj.keys())},
                  open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("已写 %s" % args.json)


if __name__ == "__main__":
    main()
