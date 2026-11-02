#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月面板与 live-sync 的运行时兜底文案同步到 10.26—11.01。

改三处：
  1. month-dashboard.js 五张卡的静态默认值（首屏/离线时可见）
  2. live-sync.js patchMdDepartments：医生组改读 doctorWeek（结账口径）、护理改「未交」、
     客服去掉「导诊止于 10.21」的旧截止说明
  3. live-sync.js patchLegacyDeptGrid：如仍有硬编码旧值，一并对齐
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MD = os.path.join(ROOT, "month-dashboard.js")
LS = os.path.join(ROOT, "live-sync.js")

hits = []


def rep(path, old, new, tag):
    s = io.open(path, encoding="utf-8").read()
    if old not in s:
        raise SystemExit(f"✗ 未找到 {tag}\n  期望：{old[:120]}")
    s = s.replace(old, new, 1)
    io.open(path, "w", encoding="utf-8").write(s)
    hits.append(f"  ✓ {tag}")


# ── 1 月面板静态默认值 ──────────────────────────────────────────
rep(MD,
    "{key:'doctor',cls:'doctor',icon:'医',name:'医生组',desc:'住院规模与管床贡献',metric:'58.35 万',"
    "note:'本期 10.26–11.01 · 营收台账（7 天满窗）',foot:'物理 16.7 万 · 入院 16 · 出 15'}",
    "{key:'doctor',cls:'doctor',icon:'医',name:'医生组',desc:'住院规模与管床贡献',metric:'21.45 万',"
    "note:'本期 10.26–11.01 · 出院结账（7 天）',foot:'物理 12.89 万 · 出院 10 · 在院 36'}",
    "月面板 医生卡")

rep(MD,
    "metric:'92.8%',note:'六项 652 应做 / 605 实做，另电休克 11 人次',foot:'未做 47 人次 · 团体生物反馈 72% 最低 · ECT 11'}",
    "metric:'未交',note:'本期 10.26–11.01 · 考核表未提交',foot:'最新存档 10.18—10.24 · 工作量 57.1%'}",
    "月面板 护理卡")

rep(MD,
    "metric:'65 人次',note:'本期 10.26–11.01 · 患者接触（V4 · 至 10.25，7 天 17 条）',foot:'咨询 39 人次 · 团体 2 场 11 人'}",
    "metric:'36 人次',note:'本期 10.26–11.01 · 患者接触（V4 · 7 天 17 条）',foot:'咨询 24 人次 · 团体 2 场 12 人'}",
    "月面板 心理卡")

rep(MD,
    "metric:'28 条',note:'本期 10.26–11.01 · 回访（表内至 10.25）',foot:'到院 11 · 39.3%'}",
    "metric:'49 条',note:'本期 10.26–11.01 · 回访（7 天）',foot:'到院 11 · 22.4% · 日均 +69.0%'}",
    "月面板 客服卡")

rep(MD,
    "metric:'87 条',note:'本期 10.26–11.01 · 管家有效对接（至 10.25）',foot:'转住院 14 · 16.1%'}",
    "metric:'92 条',note:'本期 10.26–11.01 · 管家有效对接（7 天）',foot:'转住院 12 · 13.0%'}",
    "月面板 营销卡")

# ── 2 live-sync 运行时驱动 ──────────────────────────────────────
rep(LS,
    """        metric: num(dp.doctor && dp.doctor.revenueWan, ' 万'),
        note: '本期 ' + lab + ' · 汇报表总收入（第 4 周）',
        foot: '物理 ' + ((dp.doctor && dp.doctor.physioWan) != null ? dp.doctor.physioWan : '—') + ' 万 · 入院 ' + ((dp.doctor && dp.doctor.admit) != null ? dp.doctor.admit : (m.weekAdmit ? m.weekAdmit.value : '—')) + ' · 在院 ' + (m.wardCount ? m.wardCount.value : '—')""",
    """        /* 2026-11-02：汇报表第 5 周整行空白，医生组改用业主《出院结帐明细表》口径。
           departments.doctor 仍是汇报表口径（全 null），故优先读 departments.doctorWeek。 */
        metric: (dp.doctorWeek && dp.doctorWeek.totals) ? dp.doctorWeek.totals.revenueWan + ' 万'
                : num(dp.doctor && dp.doctor.revenueWan, ' 万'),
        note: (dp.doctorWeek && dp.doctorWeek.totals) ? '本期 ' + lab + ' · 出院结账（7 天）'
                : '本期 ' + lab + ' · 汇报表总收入',
        foot: (dp.doctorWeek && dp.doctorWeek.totals)
                ? '物理 ' + dp.doctorWeek.totals.physioWan + ' 万 · 出院 ' + dp.doctorWeek.totals.discharge
                  + ' · 在院 ' + dp.doctorWeek.totals.inWard
                : '物理 ' + ((dp.doctor && dp.doctor.physioWan) != null ? dp.doctor.physioWan : '—')
                  + ' 万 · 在院 ' + (m.wardCount ? m.wardCount.value : '—')""",
    "live-sync 医生卡改读 doctorWeek")

rep(LS,
    """        /* 2026-10-26：物理治疗按业主指示暂不更新，主指标改用护理考核表的工作量填报率
           （纯静态值，快照里还没有 nursing.workFill；等快照补上再改成 num() 取值） */
        metric: '57.1%',
        note: '本期 ' + lab + ' · 工作量填报 64/112 格（人均 4.0 天）',
        foot: '综合首名 67.7 · 质控 60.5% · 6 项 92.8% · 电休克 11 人次'""",
    """        /* 2026-11-02：10.25—10.31 考核表未提交（weeklySubmitted=false），
           本周一律记 null、不拿 10.18—10.24 存档顶替。补交后快照置 true 自动切回数值。 */
        metric: dpNur.weeklySubmitted ? (dpNur.workFill != null ? dpNur.workFill + '%' : '—') : '未交',
        note: dpNur.weeklySubmitted ? '本期 ' + lab + ' · 工作量填报'
                : '本期 ' + lab + ' · 考核表未提交',
        foot: dpNur.weeklySubmitted ? '综合首名 ' + (dpNur.topScore != null ? dpNur.topScore : '—')
                : '最新存档 ' + (dpNur.weeklyThrough || '—') + ' · 不参与本期计算'""",
    "live-sync 护理卡改「未交」")

rep(LS,
    """        foot: '到院 ' + (sv.arrived != null ? sv.arrived : '—') + ' 人 · '
              + (sv.rate != null ? sv.rate : '—') + '%（导诊 ' + (sv.guide != null ? sv.guide : '—') + ' 条·止 10.21）'""",
    """        foot: '到院 ' + (sv.arrived != null ? sv.arrived : '—') + ' 人 · '
              + (sv.rate != null ? sv.rate : '—') + '%（导诊 ' + (sv.guide != null ? sv.guide : '—') + ' 条·6 天）'""",
    "live-sync 客服注释掉旧截止日")

# 客服 note：回访台账已覆盖全 7 天，不再写「表内至 …」以外的误导文案；保留 watermark 驱动
rep(LS,
    """        note: '本期 ' + lab + ' · 管家有效对接（至 ' + wd('butler') + '）',""",
    """        note: '本期 ' + lab + ' · 管家有效对接（7 天，至 ' + wd('butler') + '）',""",
    "live-sync 管家 note 补「7 天」")

print("\n".join(hits))
