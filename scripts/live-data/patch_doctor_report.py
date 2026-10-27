#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""医生组接入《特别行动小组汇报表》线上表（2026-10-26）。

背景：10-24 抓的那一版表头四项与正文「第 3 周」逐项同值（整表未滚动），当时按契约停用、
改用营收日报台账。本轮重新抓取后整表已滚动到「第 4 周（10.19—10.25）」：
    表头  入院 16 / 门诊 210 / 物理治疗费用 32.9 / 总收入 50.5
    正文  第4周 总收入 50.5、物理 16.7（住院 12.7 ＋ 门诊 4.0）、入院 16、出院 15
    ⇒ 唯一没滚动的是「物理治疗费用 32.9」＝第 3 周原值（正文第 3 周逐字相同）。
本脚本把「本周总收入 / 物理治疗」两项补进医生组卡片、抽屉与全站文案，并明确标出这一格陈旧值。

用法：python3 scripts/live-data/patch_doctor_report.py [--dry]
"""
import io
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "data", "raw-kdocs", "action_report", "3-医生组.json")
SNAP = os.path.join(ROOT, "data", "snapshot.json")
IDX = os.path.join(ROOT, "index.html")
BA = os.path.join(ROOT, "business-analysis.js")
MD = os.path.join(ROOT, "month-dashboard.js")
LS = os.path.join(ROOT, "live-sync.js")

DRY = "--dry" in sys.argv


# ---------------------------------------------------------------- 解析汇报表
def parse():
    raw = json.load(io.open(RAW, encoding="utf-8"))
    rows = raw["rows"]

    def num(v):
        try:
            return float(str(v).replace(",", "").strip())
        except Exception:
            return None

    # 表头：第 2 行是「本周入院人数 / 本周门诊人数 / 物理治疗费用 / 总收入」，值在第 3 行
    head_label = rows[1]
    head_val = rows[2]
    cols = {}
    for i, v in enumerate(head_label):
        t = (v or "").strip()
        if t in ("本周入院人数", "本周门诊人数", "物理治疗费用", "总收入"):
            cols[t] = i
    header = {
        "admit": num(head_val[cols["本周入院人数"]]),
        "outpatient": num(head_val[cols["本周门诊人数"]]),
        "physio": num(head_val[cols["物理治疗费用"]]),
        "revenue": num(head_val[cols["总收入"]]),
    }

    # 正文：科主任那一段最长
    body = max((r[cols["总收入"]] or "" for r in rows), key=len) if False else None
    body = ""
    for r in rows:
        for c in r:
            c = c or ""
            if "总费用" in c and len(c) > len(body):
                body = c
    assert body, "未找到科主任正文"

    def seg(start, end=None):
        i = body.find(start)
        assert i >= 0, "正文缺段落：" + start
        j = len(body)
        for e in (end or []):
            k = body.find(e, i + 1)
            if k > 0:
                j = min(j, k)
        return body[i:j]

    def week_vals(text, pat):
        return {int(m.group(1)): m.group(2) for m in re.finditer(pat, text)}

    def f(v):
        try:
            return float(str(v).replace(" ", ""))
        except Exception:
            return None

    rev_txt = seg("总费用：", ["物理治疗："])
    rev = {k: f(v) for k, v in week_vals(rev_txt, r"第([1-4])周[：:]?\s*([\d.]+)\s*万").items()}

    ph_txt = seg("物理治疗：5月", ["入院："]).replace(" ", "")
    ph, ph_ip, ph_op = {}, {}, {}
    # 逐周切块：「第N周（区间）：总额万（住院：xx万，门诊：yy万）」，周次前缀/住院/门诊写法各周不一致
    parts = re.split(r"第([1-4])周", ph_txt)
    for i in range(1, len(parts) - 1, 2):
        w = int(parts[i])
        chunk = parts[i + 1]
        m = re.search(r"[:：]\s*([\d.]+)万", chunk)
        if m:
            ph[w] = f(m.group(1))
        mi = re.search(r"住[院]?[:：]\s*([\d.]+)万", chunk)
        if mi:
            ph_ip[w] = f(mi.group(1))
        mo = re.search(r"门[诊]?[:：]\s*([\d.]+)万", chunk)
        if mo:
            ph_op[w] = f(mo.group(1))

    adm_txt = seg("入院：", ["出院"])
    adm = {k: int(float(v)) for k, v in week_vals(adm_txt, r"第([1-4])周[：:]?\s*(\d+)\s*人").items()}

    dis_txt = seg("出院", ["门诊："])
    dis = {k: int(float(v)) for k, v in week_vals(dis_txt, r"第([1-4])周[：:]?\s*(\d+)\s*人").items()}

    opd_txt = seg("门诊：5月", [])
    opd = {k: int(float(v)) for k, v in week_vals(opd_txt, r"第([1-4])周[：:]?\s*(\d+)\s*人").items()}

    return {
        "header": header,
        "rev": rev, "physio": ph, "physioIn": ph_ip, "physioOut": ph_op,
        "admit": adm, "discharge": dis, "outpatient": opd,
        "pulledAt": raw.get("pulledAt"),
    }


def build(p):
    h, w4, w3 = p["header"], 4, 3
    out = {
        "revenueWan": p["rev"][w4],
        "physioWan": p["physio"][w4],
        "physioInWan": p["physioIn"].get(w4),
        "physioOutWan": p["physioOut"].get(w4),
        "admit": int(p["admit"][w4]),
        "discharge": int(p["discharge"][w4]),
        "outpatient": int(h["outpatient"]),
        "prev": {
            "revenueWan": p["rev"][w3],
            "physioWan": p["physio"][w3],
            "physioInWan": p["physioIn"].get(w3),
            "physioOutWan": p["physioOut"].get(w3),
            "admit": int(p["admit"][w3]),
            "discharge": int(p["discharge"][w3]),
            "outpatient": p["outpatient"].get(w3),
        },
        "headerPhysioWan": h["physio"],
        "headerAdmit": int(h["admit"]),
        "headerRevenueWan": h["revenue"],
        "pulledAt": p["pulledAt"],
    }
    o = out
    o["revDeltaPct"] = round((o["revenueWan"] / o["prev"]["revenueWan"] - 1) * 100, 1)
    o["phyDeltaPct"] = round((o["physioWan"] / o["prev"]["physioWan"] - 1) * 100, 1)
    o["admDeltaPct"] = round((o["admit"] / o["prev"]["admit"] - 1) * 100, 1)
    o["disDeltaPct"] = round((o["discharge"] / o["prev"]["discharge"] - 1) * 100, 1)
    o["opdDeltaPct"] = round((o["outpatient"] / (o["prev"]["outpatient"] or o["outpatient"]) - 1) * 100, 1)
    o["physioShare"] = round(o["physioWan"] / o["revenueWan"] * 100, 1)
    o["physioSharePrev"] = round(o["prev"]["physioWan"] / o["prev"]["revenueWan"] * 100, 1)
    o["revDrop"] = round(o["prev"]["revenueWan"] - o["revenueWan"], 1)
    o["phyDrop"] = round(o["prev"]["physioWan"] - o["physioWan"], 1)
    o["phyDropShare"] = round(o["phyDrop"] / o["revDrop"] * 100, 1) if o["revDrop"] else None
    o["phyInDeltaPct"] = round((o["physioInWan"] / o["prev"]["physioInWan"] - 1) * 100, 1)
    o["phyOutDeltaPct"] = round((o["physioOutWan"] / o["prev"]["physioOutWan"] - 1) * 100, 1)
    o["headerPhysioStale"] = abs((h["physio"] or 0) - (o["physioWan"] or 0)) > 0.05
    return out


# ---------------------------------------------------------------- 文本
def sd(v):
    """带符号的百分比（负数用 U+2212，与页面其它位置一致）。"""
    return ("\u2212%.1f" % abs(v)) if v < 0 else ("+%.1f" % v)


def texts(o):
    R = {}
    R["card"] = (
        '      doctor:{m1:{label:"本周总收入",value:"%s",unit:"万"},m2:{label:"物理治疗",value:"%s",unit:"万"},\n'
        '        trend:[4,2,0,2,1],axis:"d1019",\n'
        '        note:"<b>本周（10.19–10.25）已切回《特别行动小组汇报表》医生组——整表已滚动到第 4 周。</b>'
        '总收入 <b>%s</b> 万、物理治疗 <b>%s</b> 万（住院 %s ＋ 门诊 %s）、入院 <b>%d</b> 人、出院 <b>%d</b> 人、门诊 <b>%d</b> 人次。'
        '环比上一周（第 3 周 10.12–10.18）：总收入 %s → %s 万（<b>%s%%</b>）、物理 %s → %s 万（<b>%s%%</b>）、'
        '入院 %d → %d（%s%%）、出院 %d → %d（%s%%）、门诊 %d → %d（持平）。'
        '⚠ <b>表头「物理治疗费用 %s 万」是上一周的旧值、没滚动</b>（与该表正文第 3 周逐字相同），'
        '本周真实值取正文 <b>%s 万</b>，两者差 %s 万——照抄表头会把本周物理多报一倍、环比写成 0%%。'
        '⚠ 营收台账只到 10.23（5 天 38.98 万），<b>缺 10.24–10.25，不能与汇报表 7 天 %s 万直接相减</b>。'
        '个人周排（出院结账，至 10.25）出院 15、在院 33、新入 16，与汇报表全组口径逐项对上。点开本卡「排名」页看 6 人明细。"},\n'
        % (
            o["revenueWan"], o["physioWan"],
            o["revenueWan"], o["physioWan"], o["physioInWan"], o["physioOutWan"],
            o["admit"], o["discharge"], o["outpatient"],
            o["prev"]["revenueWan"], o["revenueWan"], o["revDeltaPct"],
            o["prev"]["physioWan"], o["physioWan"], o["phyDeltaPct"],
            o["prev"]["admit"], o["admit"], o["admDeltaPct"],
            o["prev"]["discharge"], o["discharge"], o["disDeltaPct"],
            o["prev"]["outpatient"], o["outpatient"],
            o["headerPhysioWan"], o["physioWan"], o["phyDrop"],
            o["revenueWan"],
        )
    )

    R["drawer"] = (
        "doctor:{'range': '本期 10.19–10.25（汇报表 7 天全周 ／ 营收台账至 10.23 · 5 天 ／ 个人周排至 10.25 · 出院结账）', "
        "'metrics': [['本周总收入', '%s 万'], ['物理治疗费', '%s 万'], ['物理·住院/门诊', '%s / %s 万'], "
        "['门诊人次', '%d 人次'], ['入院 / 出院', '%d / %d 人'], ['营收台账（5 天）', '38.98 万'], "
        "['在院（10.25 时点）', '33 人'], ['个人业绩合计', '23.11 万'], ['个人周排第一', '曾凯 · 99.13']], "
        "'note': '<b>本周（10.19–10.25）医生组回到《特别行动小组汇报表》主表口径，整表已滚动到第 4 周。</b>"
        "总收入 <b>%s 万</b>、物理治疗 <b>%s 万</b>（住院 %s ＋ 门诊 %s，占收入 %s%%）、入院 <b>%d</b> 人、出院 <b>%d</b> 人、门诊 <b>%d</b> 人次。"
        "上一周（第 3 周 10.12–10.18）：%s 万 / 物理 %s 万 / 入院 %d / 出院 %d / 门诊 %d。<br>"
        "<b>⚠ 表头有一格没滚动：</b>「物理治疗费用」仍写 %s 万，与该表正文第 3 周逐字相同；正文第 4 周为 <b>%s 万</b>。"
        "两项差 %s 万，若照抄表头，本周物理会多报一倍、环比从 %s%% 变成 0%%。本周一律取正文，表头原值存档在 departments.actionReportRaw。"
        "<br><b>⚠ 两个窗口不要相减：</b>营收台账 10.19–10.23 共 5 天 38.98 万（日均 7.80 万），汇报表 7 天 %s 万（日均 7.21 万），"
        "差 11.52 万对应 10.24–10.25 两天、日均 5.76 万——低于本周工作日，周末没有出现往常的冲高。"
        "<br><b>✅ 三重交叉核对：</b>汇报表全组 入 %d / 出 %d；个人周排（出院结账，6 人）入 16 / 出 15；"
        "汇报表正文 5 人自填 入 16 / 出 12（赵郁莹两格空白）→ <b>入院零差、出院差 3 全落在空白那一行</b>。', "
        "'diag': '<div class=\\'diagnosis-item tone-risk\\'><b>本周判断 · 收入降三成，七成降幅来自物理治疗</b>"
        "<p>总收入 <b>%s 万</b>（−%s 万 / <b>%s%%</b>）、物理治疗 <b>%s 万</b>（−%s 万 / <b>%s%%</b>）。"
        "物理占收入从 %s%% 掉到 %s%%。%s 万的降幅里，物理一项贡献 %s 万＝<b>%s%%</b>——"
        "<b>不是总量均匀下滑，是物理治疗这条线断了</b>：住院物理 %s→%s 万（<b>%s%%</b>）、门诊物理 %s→%s 万（+%s%%），"
        "门诊端还在涨、住院端腰斩。同期入院 %d→%d、出院 %d→%d、在院 35→33（10.25），量掉了物理自然跟着掉——"
        "<b>先查住院量，再查治疗开单与执行</b>。</p></div>"
        "<div class=\\'diagnosis-item tone-orange\\'><b>表头一格没滚动，是会直接算错的坑</b>"
        "<p>「物理治疗费用」表头 %s 万与本表正文第 3 周逐字相同，本周正文是 %s 万。照抄表头 → 物理多报 <b>%s 万</b>、"
        "环比被写成 <b>0%%</b>、物理占收入被算成 %s%%。已按正文取值，表头原值存 departments.actionReportRaw.headerPhysioWan，下轮自动比对。</p></div>"
        "<div class=\\'diagnosis-item tone-risk\\'><b>两个窗口不能相减，也别拿它解释「周末掉了」</b>"
        "<p>营收台账 5 天 38.98 万（日均 7.80 万）＋ 汇报表 7 天 %s 万（日均 7.21 万），差 11.52 万＝10.24–10.25 两天、日均 5.76 万。"
        "前几天周末日均在 10–15 万，<b>这个周末明显偏低</b>，值得翻一下 10.24–10.25 的排班与收费记录。"
        "另：汇报表周收入与台账逐周对不上（第 1 周 −30.2%%、第 2 周 +6.2%%、第 3 周 +38.2%%），"
        "<b>两套数只能各自比、不能互相校验</b>，需财务定一个主口径。</p></div>'}," % (
            o["revenueWan"], o["physioWan"], o["physioInWan"], o["physioOutWan"],
            o["outpatient"], o["admit"], o["discharge"],
            o["revenueWan"], o["physioWan"], o["physioInWan"], o["physioOutWan"], o["physioShare"],
            o["admit"], o["discharge"], o["outpatient"],
            o["prev"]["revenueWan"], o["prev"]["physioWan"], o["prev"]["admit"], o["prev"]["discharge"], o["prev"]["outpatient"],
            o["headerPhysioWan"], o["physioWan"], o["phyDrop"], o["phyDeltaPct"],
            o["revenueWan"], o["admit"], o["discharge"],
            o["revenueWan"], o["revDrop"], sd(o["revDeltaPct"]), o["physioWan"], o["phyDrop"], sd(o["phyDeltaPct"]),
            o["physioSharePrev"], o["physioShare"], o["revDrop"], o["phyDrop"], o["phyDropShare"],
            o["prev"]["physioInWan"], o["physioInWan"], sd(o["phyInDeltaPct"]),
            o["prev"]["physioOutWan"], o["physioOutWan"], o["phyOutDeltaPct"],
            o["prev"]["admit"], o["admit"], o["prev"]["discharge"], o["discharge"],
            o["headerPhysioWan"], o["physioWan"], o["phyDrop"], round(o["headerPhysioWan"] / o["revenueWan"] * 100, 1),
            o["revenueWan"],
        )
    )
    return R


def main():
    p = parse()
    o = build(p)
    print("解析结果：")
    print(json.dumps(o, ensure_ascii=False, indent=1))
    T = texts(o)

    # ---- 1. snapshot.json
    snap = json.load(io.open(SNAP, encoding="utf-8"))
    dep = snap["departments"]
    old_raw = dep.get("actionReportRaw") or {}
    dep["doctor"].update({
        "admit": o["admit"], "discharge": o["discharge"], "outpatient": o["outpatient"],
        "physioWan": o["physioWan"], "revenueWan": o["revenueWan"],
    })
    dep["actionReportRaw"] = {
        "revenueWan": o["revenueWan"], "admit": o["admit"], "discharge": o["discharge"],
        "outpatient": o["outpatient"], "physioWan": o["physioWan"],
        "headerPhysioWan": o["headerPhysioWan"],
        "headerPhysioStale": o["headerPhysioStale"],
        "prevWeek": o["prev"],
        "replaced": old_raw.get("revenueWan"),
        "judgedBy": "header==week4_narrative; header.physio==week3 (stale)",
        "pulledAt": o["pulledAt"],
    }
    dep["doctorReport"] = dict(o, week=["2026-10-19", "2026-10-25"], sheet="action_report/医生组")
    dep["week"] = dict(dep.get("week") or {})
    dep["week"].update({
        "label": "10.19—10.25", "sourceName": "特别行动小组汇报表 · 医生组（第 4 周）",
        "authority": "action_report", "stale": False,
        "staleNote": "整表已滚动到第 4 周；仅表头「物理治疗费用 32.9 万」仍为第 3 周旧值，本周物理取正文 16.7 万",
        "filledAt": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    })
    snap["period"]["reportFilled"] = True
    snap["period"]["reportDataThrough"] = "2026-10-25"
    snap["revision"] = int(snap.get("revision") or 0) + 1
    snap["revisionCreatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    snap["generatedAt"] = snap["revisionCreatedAt"]
    if not DRY:
        io.open(SNAP, "w", encoding="utf-8").write(json.dumps(snap, ensure_ascii=False, indent=1))
    print("snapshot revision →", snap["revision"])

    # ---- 2. index.html：部门卡 + 抽屉
    s = io.open(IDX, encoding="utf-8").read()
    a = s.find('      doctor:{m1:{label:"本期营收"')
    b = s.find('      nursing:{m1:{label:"工作量填报"', a)
    assert a > 0 and b > a, "DEPT_CARD.doctor 定位失败"
    s = s[:a] + T["card"] + s[b:]

    a = s.find("doctor:{'range': '本期 10.19–10.25（营收台账至 10.23")
    b = s.find("      nursing:{'range':", a)
    assert a > 0 and b > a, "deptDaily.doctor 定位失败"
    s = s[:a] + T["drawer"] + "\n" + s[b:]
    if not DRY:
        io.open(IDX, "w", encoding="utf-8").write(s)
    print("index.html 已更新（卡 + 抽屉）")

    # ---- 3. business-analysis.js
    s = io.open(BA, encoding="utf-8").read()
    old = re.search(r"    /\* ⭐ 2026-10-25：医生组改用营收日报逐日台账.*?docCabRev: 21\n", s, re.S)
    assert old, "business-analysis SEC 医生段定位失败"
    new = (
        "    /* ⭐ 2026-10-26：汇报表医生组整表已滚动到第 4 周（10.19—10.25），回到主表口径。\n"
        "       表头「物理治疗费用 %s 万」= 第 3 周旧值（正文第 3 周逐字相同），本周物理取正文 %s 万。\n"
        "       营收台账（10.19—10.23，5 天）38.98 万是另一个窗口，两者不可相减、也不可互相校验。 */\n"
        "    docRev: '%s', docRevPrev: '%s', docRevDelta: '%s',\n"
        "    docPhysio: '%s', docPhysioPrev: '%s', docPhysioDelta: '%s',\n"
        "    docAdmit: %d, docAdmitPrev: %d, docAdmitDelta: '%s',\n"
        "    docDis: %d, docDisPrev: %d, docDisDelta: '%s',\n"
        "    docOpd: %d, docOpdPrev: %d, docOpdDelta: '%s',\n"
        "    docDetailAdmit: 16, docDetailDis: 12, docGapAdmit: 0, docGapDis: 3,\n"
        "    docCabRev: 33\n"
    ) % (
        o["headerPhysioWan"], o["physioWan"],
        o["revenueWan"], o["prev"]["revenueWan"], ("+%s" % o["revDeltaPct"]) if o["revDeltaPct"] > 0 else ("−%s" % abs(o["revDeltaPct"])),
        o["physioWan"], o["prev"]["physioWan"], ("+%s" % o["phyDeltaPct"]) if o["phyDeltaPct"] > 0 else ("−%s" % abs(o["phyDeltaPct"])),
        o["admit"], o["prev"]["admit"], ("+%s" % o["admDeltaPct"]) if o["admDeltaPct"] > 0 else ("−%s" % abs(o["admDeltaPct"])),
        o["discharge"], o["prev"]["discharge"], ("+%s" % o["disDeltaPct"]) if o["disDeltaPct"] > 0 else ("−%s" % abs(o["disDeltaPct"])),
        o["outpatient"], o["prev"]["outpatient"], ("+%s" % o["opdDeltaPct"]) if o["opdDeltaPct"] > 0 else ("%s" % o["opdDeltaPct"]),
    )
    s = s[:old.start()] + new + s[old.end():]

    # dc-item 5
    i = s.find('<span class="dc-no">5</span>')
    a = s.rfind("<details", 0, i)
    b = s.find("</details>", i) + len("</details>")
    item5 = (
        '<details class="dc-item" open><summary><span class="dc-no">5</span>收入降三成、七成降幅在物理治疗，不是均匀下滑</summary>'
        "<p>本期（<b>10.19—10.25，7 天</b>·《特别行动小组汇报表》医生组·整表已滚动到第 4 周）"
        "总收入 <b>${SEC.docRev} 万</b>（上期 ${SEC.docRevPrev} 万，<b>${SEC.docRevDelta}%</b>）、"
        "物理治疗 <b>${SEC.docPhysio} 万</b>（上期 ${SEC.docPhysioPrev} 万，<b>${SEC.docPhysioDelta}%</b>）、"
        "入院 <b>${SEC.docAdmit} 人</b>（上期 ${SEC.docAdmitPrev}，<b>${SEC.docAdmitDelta}%</b>）、"
        "出院 <b>${SEC.docDis} 人</b>（上期 ${SEC.docDisPrev}，<b>${SEC.docDisDelta}%</b>）、"
        "门诊 <b>${SEC.docOpd} 人次</b>（上期 ${SEC.docOpdPrev}，<b>${SEC.docOpdDelta}%</b>）。"
        "<b>22.0 万的收入降幅里，物理治疗一项贡献 16.2 万＝73.6%</b>；拆开看是"
        "<b>住院物理 29.8→12.7 万（−57.4%）、门诊物理 3.1→4.0 万（+29.0%）</b>——门诊端还在涨、住院端腰斩，"
        "同期在院由 35 人（10.23）降到 33 人（10.25）。⚠ 表头「物理治疗费用」仍写 32.9 万、与该表正文第 3 周逐字相同，"
        "<b>照抄会把本周物理多报一倍、环比写成 0%</b>，本周一律取正文。在院 <b>${SEC.docCabRev} 人</b>（10.25 时点，个人周排）。"
        "个人正文 5 人自填加总入院 <b>${SEC.docDetailAdmit}</b>、出院 <b>${SEC.docDetailDis}</b>，"
        "<b>入院零差、出院差 ${SEC.docGapDis} 全落在赵郁莹空白行</b>，按契约记 null、不反推。</p></details>"
    )
    s = s[:a] + item5 + s[b:]

    # dc-item 9
    i = s.find('<span class="dc-no">9</span>')
    a = s.rfind("<details", 0, i)
    b = s.find("</details>", i) + len("</details>")
    item9 = (
        '<details class="dc-item"><summary><span class="dc-no">9</span>医生组本周口径：主表整表已滚动，只剩物理治疗一格没滚</summary>'
        "<p>本周（<b>10.19—10.25，7 天</b>）《特别行动小组汇报表》医生组：总收入 <b>${SEC.docRev} 万</b>、"
        "物理治疗 <b>${SEC.docPhysio} 万</b>、入院 <b>${SEC.docAdmit} 人</b>、门诊 <b>${SEC.docOpd} 人次</b>、"
        "出院 <b>${SEC.docDis} 人</b>。较上一自然周（10.12—10.18，同为 7 天）：收入 <b>${SEC.docRevDelta}%</b>、"
        "物理 <b>${SEC.docPhysioDelta}%</b>、入院 <b>${SEC.docAdmitDelta}%</b>、出院 <b>${SEC.docDisDelta}%</b>、"
        "门诊 <b>${SEC.docOpdDelta}%</b>。⚠ 唯一没滚动的表头格是「物理治疗费用 32.9 万」（＝第 3 周原值），"
        "正文第 4 周为 16.7 万，差 16.2 万，已存档并在页面标注。个人正文：曾凯 入 5 / 出 2、康言 入 4 / 出 3、"
        "王建 入 4 / 出 2、王建宁 入 3 / 出 5（单独转化 1 人）、<b>赵郁莹两格空白</b>；孙乐（住院总医师）转化 5 / 多导 5，"
        "岗位口径不同、不并入入出院。加总入 16 / 出 12，对表头 <b>入院零差、出院差 3</b>。"
        "营收台账（10.19—10.23，5 天）38.98 万与主表 7 天 50.5 万是<b>两个窗口</b>，差 11.52 万＝10.24–10.25 两天、"
        "日均 5.76 万，<b>不可相减、也不可互相校验</b>（两套数逐周差异 −30%～+38%）。</p></details>"
    )
    s = s[:a] + item9 + s[b:]
    if not DRY:
        io.open(BA, "w", encoding="utf-8").write(s)
    print("business-analysis.js 已更新（SEC + 第 5 / 9 条）")

    # ---- 4. month-dashboard.js 默认卡
    s = io.open(MD, encoding="utf-8").read()
    old = "{key:'doctor',cls:'doctor',icon:'医',name:'医生组',desc:'住院规模与管床贡献',metric:'38.98 万',note:'本期 10.19–10.25 · 营收日报（5 天，至 10.23）',foot:'入院 12 · 门诊 180 · 物理 —（无台账）'},"
    assert s.count(old) == 1, "month-dashboard 医生卡未匹配"
    new = ("{key:'doctor',cls:'doctor',icon:'医',name:'医生组',desc:'住院规模与管床贡献',metric:'%s 万',"
           "note:'本期 10.19–10.25 · 汇报表（第 4 周 · 7 天）',foot:'物理 %s 万 · 入院 %d · 门诊 %d'},") % (
        o["revenueWan"], o["physioWan"], o["admit"], o["outpatient"])
    s = s.replace(old, new)
    if not DRY:
        io.open(MD, "w", encoding="utf-8").write(s)
    print("month-dashboard.js 默认卡已更新")

    # ---- 5. live-sync.js
    s = io.open(LS, encoding="utf-8").read()
    old = ("      doctor: [['总收入', m.weekRevenue.value, '万'],\n"
           "               ['本周入院', m.weekAdmit.value, '人']],")
    assert s.count(old) == 1, "live-sync patchDepartments doctor 未匹配"
    s = s.replace(old,
                  "      /* 2026-10-26：汇报表整表已滚动 → 卡片回到主表口径（总收入 / 物理治疗），\n"
                  "         取 departments.doctor（快照已按 action_report 回填），不再用营收日报的 5 天窗口。 */\n"
                  "      doctor: [['本周总收入', (d.doctor || {}).revenueWan, '万'],\n"
                  "               ['物理治疗', (d.doctor || {}).physioWan, '万']],")

    old = ("      doctor: {\n"
           "        metric: m.wardCount ? num(m.wardCount.value, ' 人') : null,\n"
           "        note: '在院 · ' + wd('revenue') + ' 时点',\n"
           "        foot: '入院 ' + (m.weekAdmit ? m.weekAdmit.value : '—') + ' · 出院 ' + (m.weekDischarge ? m.weekDischarge.value : '—')")
    assert s.count(old) == 1, "live-sync patchMdDepartments doctor 未匹配"
    s = s.replace(old,
                  "      doctor: {\n"
                  "        metric: num(dp.doctor && dp.doctor.revenueWan, ' 万'),\n"
                  "        note: '本期 ' + lab + ' · 汇报表总收入（第 4 周）',\n"
                  "        foot: '物理 ' + ((dp.doctor && dp.doctor.physioWan) != null ? dp.doctor.physioWan : '—') + ' 万 · 入院 ' + (m.weekAdmit ? m.weekAdmit.value : '—') + ' · 在院 ' + (m.wardCount ? m.wardCount.value : '—')")

    old = "      doctor: [[dD.revenueWan, '万'], [dD.admit, '人']],"
    assert s.count(old) == 1, "live-sync legacy doctor 未匹配"
    s = s.replace(old, "      doctor: [[dD.revenueWan, '万'], [dD.physioWan, '万']],")

    # heroSummary：把「医生组一律取汇报表」的说法改成「台账窗口 + 汇报表窗口」并列
    old = "    var summary = $('#heroSummary');"
    assert s.count(old) == 1, "heroSummary 声明行未匹配"
    s = s.replace(old, "    var dpDoc = ((s.departments || {}).doctor) || {};\n" + old)

    old = "'）· 医生组一律取《特别行动小组汇报表》</b>：总收入 <b>' + fmt(m.weekRevenue.value) + ' 万</b>、物理治疗 <b>' + fmt(m.weekPhysio.value) + ' 万</b>（占收入 ' + Math.round(m.weekPhysio.value / m.weekRevenue.value * 1000) / 10 + '%，是收入的科目、不可相加）、入院 <b>'"
    assert s.count(old) == 1, "heroSummary 医生句未匹配"
    s = s.replace(old,
                  "'）· 营收日报（台账）</b>：营收 <b>' + fmt(m.weekRevenue.value) + ' 万</b>（门诊 ' + fmt(m.weekOutpatient.value) + ' ＋ 在院 ' + fmt(m.weekInpatient.value) + '）；"
                  "<b>《特别行动小组汇报表》本周 7 天：总收入 ' + dpDoc.revenueWan + ' 万、物理治疗 ' + dpDoc.physioWan + ' 万（占收入 ' + Math.round(dpDoc.physioWan / dpDoc.revenueWan * 1000) / 10 + '%，是收入的科目、不可相加）、入院 ' + dpDoc.admit + ' 人、出院 ' + dpDoc.discharge + ' 人、门诊 ' + dpDoc.outpatient + ' 人次</b>；台账口径入院 <b>'")
    if not DRY:
        io.open(LS, "w", encoding="utf-8").write(s)
    print("live-sync.js 已更新（三处 doctor + heroSummary）")

    # ---- 6. 版本号
    v_old = "?v=20261026c"
    v_new = "?v=20261026d"
    s = io.open(IDX, encoding="utf-8").read()
    n = s.count(v_old)
    s = s.replace(v_old, v_new)
    if not DRY:
        io.open(IDX, "w", encoding="utf-8").write(s)
    print("index.html ?v= 升级：%s → %s（%d 处）" % (v_old, v_new, n))


if __name__ == "__main__":
    main()
