#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""护理模块同步（F 批：员工排名「本周」组前三名加奖牌组件 🥇🥈🥉）"""
import io

P = "/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/index.html"
src = io.open(P, encoding="utf-8").read()
pairs = []


def add(old, new, n=1):
    pairs.append((old, new, n))


# ---------- F1 奖牌样式 ----------
CSS_OLD = ".rank-no.isnone{background:#f2f3f6;color:#9498a5}"
CSS_NEW = CSS_OLD + (
    ".rank-group.has-medal .rank-row{grid-template-columns:26px 30px 1fr auto}"
    ".rank-medal{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-size:13px;line-height:1;background:#fff;border:1px solid #e6e9f0;flex:none}"
    ".rank-medal.hollow{background:transparent;border-color:transparent}"
    ".rank-medal.gold{background:linear-gradient(140deg,#FFF4C8,#F3C33C 60%,#D79A0B);border-color:#D9A011}"
    ".rank-medal.silver{background:linear-gradient(140deg,#FCFEFF,#CCD7E5 60%,#98A8BC);border-color:#9FAFC2}"
    ".rank-medal.bronze{background:linear-gradient(140deg,#FCE9D7,#DFA46B 60%,#B97433);border-color:#BB7735}"
    ".rank-row.is-top1{background:linear-gradient(90deg,rgba(243,195,60,.14),transparent 66%);border-color:#EFD591}"
    ".rank-row.is-top2{background:linear-gradient(90deg,rgba(204,215,229,.22),transparent 66%);border-color:#D6DFEA}"
    ".rank-row.is-top3{background:linear-gradient(90deg,rgba(223,164,107,.17),transparent 66%);border-color:#E9CBAF}"
    "@media(max-width:560px){.rank-group.has-medal .rank-row{grid-template-columns:22px 28px 1fr auto}.rank-medal{width:22px;height:22px;font-size:12px}}"
)
add(CSS_OLD, CSS_NEW)

# ---------- F2 renderRankGroup 加奖牌 ----------
RG_OLD = "function renderRankGroup(group){const lab=group.scoreLabel||'本周',rl=!!group.rankless;/* rankless 组的右侧标签可覆盖：「填报完整性核查」用默认的「不排名 / 仅核查」，「组长单独工作量」用「不排名 / 单独列示」 */const nM=group.noRankText||'不排名',nS=group.noRankSub||'仅核查';return `<div class=\"rank-group${rl?' is-rankless':''}\"><h4>${group.title}</h4><div class=\"rank-summary\">${group.note}</div><div class=\"rank-list\">${group.rows.map((r,i)=>`<div class=\"rank-row\"><span class=\"rank-no ${rl?'isnone':(r.missing?'missing':'')}\">${rl?'·':(r.missing?'—':i+1)}</span><span class=\"rank-person\"><strong>${r.name}</strong><span>${r.metric}</span></span><span class=\"rank-score\"><strong>${rl?nM:(r.missing?'未排名':r.score)}</strong><span>${rl?nS:(r.missing?'未填报':lab)}</span></span></div>`).join('')}</div></div>`}"
RG_NEW = (
    "function renderRankGroup(group){const lab=group.scoreLabel||'本周',rl=!!group.rankless;"
    "/* rankless 组的右侧标签可覆盖：「填报完整性核查」用默认的「不排名 / 仅核查」，「组长单独工作量」用「不排名 / 单独列示」 */"
    "const nM=group.noRankText||'不排名',nS=group.noRankSub||'仅核查';"
    "/* 奖牌：仅对显式标 medals:true 的「本周」人员排名组生效（业主 2026-09-27 要求），"
    "rankless 组、项目口径组、逐日明细组、岗位汇总组一律不加，避免给「天」或「岗位」发奖牌。 */"
    "const md=!!group.medals&&!rl;"
    "const medal=i=>i===0?'<span class=\"rank-medal gold\" title=\"第 1 名\" aria-label=\"第 1 名\">🥇</span>':"
    "i===1?'<span class=\"rank-medal silver\" title=\"第 2 名\" aria-label=\"第 2 名\">🥈</span>':"
    "i===2?'<span class=\"rank-medal bronze\" title=\"第 3 名\" aria-label=\"第 3 名\">🥉</span>':"
    "'<span class=\"rank-medal hollow\" aria-hidden=\"true\"></span>';"
    "return `<div class=\"rank-group${rl?' is-rankless':''}${md?' has-medal':''}\"><h4>${group.title}</h4>"
    "<div class=\"rank-summary\">${group.note}</div><div class=\"rank-list\">${group.rows.map((r,i)=>{"
    "const top=md&&i<3&&!r.missing;return `<div class=\"rank-row${top?' is-top'+(i+1):''}\">${md?medal(i):''}"
    "<span class=\"rank-no ${rl?'isnone':(r.missing?'missing':'')}\">${rl?'·':(r.missing?'—':i+1)}</span>"
    "<span class=\"rank-person\"><strong>${r.name}</strong><span>${r.metric}</span></span>"
    "<span class=\"rank-score\"><strong>${rl?nM:(r.missing?'未排名':r.score)}</strong>"
    "<span>${rl?nS:(r.missing?'未填报':lab)}</span></span></div>`}).join('')}</div></div>`}"
)
add(RG_OLD, RG_NEW)

# ---------- F3 给「本周」人员排名组打标 ----------
flags = [
    "{title:'① 本周排名 · 出院结帐明细（9.21—9.27，实际至 9.24）',scoreLabel:'本周',",
    "{title:'① 综合排名 · 源表口径（9.20—9.26）',scoreLabel:'综合分',",
    "{title:'② 工作量排名 · 源表口径（9.20—9.26）',",
    "{title:'②·对照 按日均重排名次（剔除出勤天数影响 · 9.20—9.26）',",
    "{title:'③ 工作质量考核排名 · 源表口径（9.20—9.26）',",
    "{title:'④ 物理治疗完成率排名 · 按人累计（9.20—9.26 · 护士日表）',",
    "{title:'① 综合排名（本周 09.21—09.26 · 咨询量 : 患者接触 ＝ 2 : 1）',scoreLabel:'综合分',",
    "{title:'② 咨询工作量排名（本周 09.21—09.26）',scoreLabel:'咨询',",
    "{title:'③ 患者接触排名（本周 09.21—09.26）',scoreLabel:'接触',",
    "{title:'⑤ 团体治疗带领（本周 09.21—09.27 · 心理科来访数量「团体治疗登记」）',",
    "{title:'① 导医回访排名（本周 09.21—09.26 · 客服导诊部台账）',",
    "{title:'② 导诊主动服务排名（本周 09.21—09.26）',",
    "{title:'③ 导医日工作量排名（本周 09.21—09.26 · 按日均分）',",
    "{title:'① 管家个人对接排名（本周 09.21—09.26 · 患者有效对接表）',",
    "{title:'② 管家转住院率排名（本周 09.21—09.26 · 按率值）',",
]
for f in flags:
    add(f, f + "medals:true,")

bad = 0
for old, new, n in pairs:
    c = src.count(old)
    if c != n:
        print("!! 命中 %d 次（期望 %d）：%s" % (c, n, old[:110].replace("\n", "\\n")))
        bad += 1
        continue
    src = src.replace(old, new)
if bad:
    print("有 %d 处未匹配，未写入。" % bad)
    raise SystemExit(1)
io.open(P, "w", encoding="utf-8").write(src)
print("F 批完成：奖牌样式 + renderRankGroup + %d 个本周排名组打标" % len(flags))
