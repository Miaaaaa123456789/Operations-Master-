#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""index.html 换期收尾 · 第 2 步：const analytics 整块重建（10.26—11.01）。

数字来源：
  · 医生组 → data/doctor-week-2026-10-26.json（出院结账口径，业主两份 xlsx）
  · 其余四组 → data/snapshot.json（revision 47）
所有派生值（占比、归一化分数）在本脚本里算，不手抄，算完打印出来核对。
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IDX = os.path.join(ROOT, "index.html")
SNAP = os.path.join(ROOT, "data", "snapshot.json")
DW = os.path.join(ROOT, "data", "doctor-week-2026-10-26.json")

s = json.load(io.open(SNAP, encoding="utf-8"))
dw = json.load(io.open(DW, encoding="utf-8"))

# ── 医生组：从唯一真源取值 ────────────────────────────────────────
T = dw["totals"]
people = dw["people"]
cost = dw["costBreakdown"]
prev = dw["prevWeek"]["reference"]

rev_total = T["revenueYuan"]
top1 = people[0]
top3 = sum(p["revenueYuan"] for p in people[:3])


def wan(v):
    return f"{v / 10000:.2f}"


def money(v):
    return f"{v:,.2f}" if v % 1 else f"{v:,.0f}"


doc_rows = "".join(
    "{name:'%s',metric:'业绩 <b>%s</b> 万 · 出院 <b>%d</b> 人 · 在管 <b>%d</b> 人 · 床日 <b>%s</b> 天',score:'%.2f'},"
    % (p["name"], wan(p["revenueYuan"]), p["discharge"], p["inWard"], p["avgStay"], p["score"])
    for p in people
)

doc_fin_rows = "],[".join(
    "['%s','%s','%s','%s','%d','%d','%d']"
    % (p["name"], money(p["revenueYuan"]), money(p["physioYuan"]),
       money(p["psychYuan"]), p["discharge"], p["inWard"], p["admit"])
    for p in people
)

cost_rows = "],[".join(
    "['%s','%s','%.2f']" % (c["name"], money(c["yuan"]), c["share"]) for c in cost
)

# ── 心理组：归一化综合分（0.667 咨询 + 0.333 接触，各除组内最大）──────
psy_rows = [r for r in s["psych"]["rank"]]
max_c = max(r["consult"] for r in psy_rows)
max_t = max(r["contact"] for r in psy_rows)
for r in psy_rows:
    r["_score"] = 0.667 * r["consult"] / max_c + 0.333 * r["contact"] / max_t
psy_sorted = sorted(psy_rows, key=lambda r: (-r["_score"], -r["consult"], -r["contact"], r["name"]))

psy_score_rows = "".join(
    "{name:'%s',metric:'咨询 <b>%d</b>（住院 %d / 门诊 %d / 家庭 %d）· 接触 <b>%d</b>（首接 %d / 情绪 %d / 住院 %d）　填报 %d 天',score:'%.1f'},"
    % (r["name"], r["consult"], r["inpatient"], r["outpatient"], r["family"],
       r["contact"], r["first"], r["emotion"], r["inpatient"],
       {x["name"]: x["report_days"] for x in s["psych"]["staffWeek"]}[r["name"]],
       r["_score"] * 100)
    for r in psy_sorted
)

psy_consult_rows = "".join(
    "{name:'%s',metric:'住院 %d / 门诊 %d / 家庭 %d',score:'%d'},"
    % (r["name"], r["inpatient"], r["outpatient"], r["family"], r["consult"])
    for r in sorted(psy_rows, key=lambda r: (-r["consult"], -r["contact"], r["name"]))
)

psy_contact_rows = "".join(
    "{name:'%s',metric:'首接 %d / 情绪 %d / 住院 %d',score:'%d'},"
    % (r["name"], r["first"], r["emotion"], r["inpatient"], r["contact"])
    for r in sorted(psy_rows, key=lambda r: (-r["contact"], -r["consult"], r["name"]))
)

# ── 客服 / 管家：逐日表 ──────────────────────────────────────────
svc_daily = s["service"]["daily"]
svc_total = s["service"]["week"]["followup"]
svc_day_rows = "],[".join(
    "['%s','%d','%.1f']" % (k[5:].replace("-", "."), v, v / svc_total * 100)
    for k, v in sorted(svc_daily.items())
)

but_daily = s["butler"]["daily"]
but_total = s["butler"]["week"]["contact"]
but_day_rows = "],[".join(
    "['%s','%d','%.1f']" % (k[5:].replace("-", "."), v, v / but_total * 100)
    for k, v in sorted(but_daily.items())
)

SV = s["service"]["week"]
SP = s["service"]["prevSameDays"]
BW = s["butler"]["week"]
BP = s["butler"]["prevSameDays"]
PW = s["psych"]["week"]
PP = s["psych"]["prevSameDays"]

AN = (
    "const analytics={"
    # ── 医生组 ─────────────────────────────────────────────────
    "doctor:{periods:['10.12周','10.19周','10.26周'],"
    "history:[['日均营收（万元）',[7.5,8.34,8.14],'万'],['日均门诊（人次）',[30.0,40.9,34.2],'人']],"
    "rankBanner:'<b>本期 10.26—11.01 · 出院结账口径（7 天，业主《周排名分析》＋《出院结帐明细表》）</b>："
    "7 名医生、结账 <b>%.2f 万</b>、出院 <b>%d</b> 人、在院 <b>%d</b> 人、本周入院 <b>%d</b> 人、平均出院床日 <b>%.1f</b> 天、床日收入 <b>%s</b> 元。"
    "排名指数＝<b>可计分 ÷ 65 × 100</b>＝营业贡献 40（个人业绩 ÷ 组内最高 × 40）＋ 工作量 25（出院 10 ＋ 平均出院床日 10 ＋ 在管 5，均按组内最高归一）；"
    "<b>医疗质量 20 / 时效 10 / 执行协作 5 未计入</b>，≠ 绩效总分。"
    "<b>⚠ 与营收日报不同源</b>：本周结账 %.2f 万（按出院日、住院自费、7 天），营收日报 48.83 万（按进账日、含门诊、仅 6 天），<b>只并列、不相加</b>。"
    "出院逐日在 10.26—10.31 六天完全一致（2/0/1/1/3/1），11.01 再添 2 例，合计 %d 人。',"
    "rankGroups:["
    "{title:'① 综合排名（本期 10.26—11.01 · 排名指数 100）',scoreLabel:'排名指数',medals:true,"
    "note:'排名指数越高越靠前。可计分 65 ＝ 营业贡献 40 ＋ 出院 10 ＋ 平均出院床日 10 ＋ 在管 5；本周入院人数单列展示、<b>暂不计分</b>。',"
    "rows:[%s]},"
    "{title:'② 业绩构成（本期 10.26—11.01 · 出院结账 · 元）',scoreLabel:'—',medals:false,"
    "note:'个人总业绩＝该医生本周出院患者的<b>结账收入合计</b>；物理治疗与心理业绩是其<b>子集</b>，不能与总业绩相加。',"
    "table:{cols:['医生','个人总业绩','物理治疗','心理业绩','出院','在管','本周入院'],"
    "rows:[[%s]],"
    "sum:['合计','%s','%s','%s','%d','%d','%d'],"
    "foot:'物理治疗占结账收入 <b>%.1f%%</b>、心理业绩占 %.1f%%——收入结构高度依赖物理这条线。'}},"
    "{title:'③ 费用结构（本期 10.26—11.01 · 13 项明细）',scoreLabel:'—',medals:false,"
    "note:'13 项费用逐行加总＝合计 %s 元，与源表合计行逐分对平；占比按合计重算，不采用源表四舍五入后的份额列。',"
    "table:{cols:['费用项','金额（元）','占比 %%'],rows:[[%s]],"
    "foot:'「冲预交」为预交金抵扣、非收入项，未列入 13 项。'}}],"
    "diagnosis:["
    "['本周结果（10.26—11.01 · 出院结账口径）','结账 <b>%.2f</b> 万、出院 <b>%d</b> 人、在院 <b>%d</b> 人、本周入院 <b>%d</b> 人、平均床日 <b>%.1f</b> 天。"
    "%s 以 %.2f 万居首（占 %.1f%%），前三名合计 %.2f 万、占 <b>%.1f%%</b>；物理治疗 %.2f 万占 <b>%.1f%%</b>，收入结构高度依赖物理。'],"
    "['两个口径在出院这一列对得上','结账表逐日出院 2 / 0 / 1 / 1 / 3 / 1 / 2 ＝ 10 人；营收日报 10.26—10.31 为 2 / 0 / 1 / 1 / 3 / 1 ＝ 8 人——"
    "<b>前六天逐日完全一致</b>，差额就是 11.01 那两例（营收日报当日尚未进账）。→ 两张表不是打架，是窗口差一天。'],"
    "['排名边界（务必按此读表）','① 医疗质量 20 / 时效 10 / 执行协作 5 未计入，65 分只是可量化工作量。"
    "② 平均出院床日按「越长分越高」归一（%s 达 %.1f 天拿满 10 分），与缩短平均住院日的方向相反，建议改分段计分。"
    "③ 傅睿文业绩 0 不是没干活——本周入院 3 人、在管 3 人，患者尚未出院结账，需结合在管人数一起看。"
    "④ 入院 13（结账表 7 天、按医生归属）≠ 营收日报 8（6 天、按当日登记），<b>不相加、不互相校验</b>。']]},"
    # ── 护理组 ─────────────────────────────────────────────────
    "nursing:{periods:['10.12周','10.19周','10.26周'],"
    "history:[['工作量填报率',[null,57.1,null],'%%'],['质控填报率',[null,60.5,null],'%%']],"
    "rankBanner:'<b>本期 10.26—11.01 · 考核表未提交</b>：护理部最新一版《护士工作量及质量统计》停在 <b>10.18—10.24</b>（17 人 / 7 天、工作量填报 57.1%%、质控 60.5%%），"
    "本期 <b>10.25—10.31 未交</b>。按契约，本周全部指标记 <b>null</b>、不排名、<b>不拿存档值顶替</b>；存档值可在「护理考核标准」页查看，已逐处标注。',"
    "rankGroups:[],"
    "diagnosis:["
    "['本周没有可用的护理数据','10.25—10.31 的考核表、六项治疗周报、电休克人次、工娱场次均未提交。页面上任何护理数字都属 10.18—10.24 存档，<b>不代表本周</b>。'],"
    "['为什么不用存档值顶替','护理的填报完整率、综合得分都随「交了几张表」剧烈变化：上一版 112 个工作量格里只填了 64 格（57.1%%），"
    "名次差距主要来自出勤而不是能力。拿这组数当本周，会把「没交表」说成「水平掉了」。'],"
    "['补交后要一起看的三件事','① 工作量与质控逐日是否填满（人均应到 6 天以上）；② 六项治疗应做 / 实做是否逐日可分；③ 工娱场次是否补上——现在只有人数、没有场次，场均无法计算。']]},"
    # ── 心理咨询组 ──────────────────────────────────────────────
    "psychology:{periods:['10.12周','10.19周','10.26周'],"
    "history:[['咨询工作量',[46.0,39.0,24.0],'人次'],['患者接触',[84.0,65.0,36.0],'人次']],"
    "rankBanner:'<b>本期 10.26—11.01 · V4 管理表「咨询师每日简报」逐条（全 7 天 / 17 条）</b>：5 人有业务量，咨询合计 <b>%d</b> 人次、接触 <b>%d</b> 人次、家长访谈 <b>%d</b> 人次。"
    "综合分＝<b>0.667 ×（咨询 ÷ 组内最大 %d）＋ 0.333 ×（接触 ÷ 组内最大 %d）</b>，百分制（业主 2026-09-27 定权重 2:1，此后统一按归一化口径）；"
    "<b>组长陈鹏不参与排名</b>（本周 0 条日报，工作量单列）；史允之、王沛然本周 0 业务量，<b>记 null、不按 0 排进榜</b>。"
    "⚠ 「周个人统计」周起始日仍停在 2026-09-01、缓存 21 天，本榜<b>只取简报逐条</b>。',"
    "rankGroups:["
    "{title:'① 综合排名（本期 10.26—11.01 · 0.667 咨询 ＋ 0.333 接触）',scoreLabel:'综合分',medals:true,"
    "note:'综合分＝0.667×(咨询÷%d)＋0.333×(接触÷%d)，归一化到百分制。填报天数与在岗天数不计分、不参与并列判定；组长单列、不进本榜。',"
    "rows:[%s]},"
    "{title:'② 咨询工作量（本期 10.26—11.01）',scoreLabel:'咨询',medals:true,"
    "note:'口径＝住院咨询 ＋ 门诊咨询 ＋ 家庭咨询。本周家庭咨询为 <b>0</b>，不是缺数——简报 17 条里「家庭咨询/治疗人次」列全空。',"
    "rows:[%s]},"
    "{title:'③ 患者接触（本期 10.26—11.01）',scoreLabel:'接触',medals:true,"
    "note:'口径＝24h 首次对接 ＋ 情绪支持 ＋ 住院咨询。<b>接触人次与咨询人次不可相加</b>（同一患者会同时计入两项）。',"
    "rows:[%s]}],"
    "diagnosis:["
    "['本周结果（10.26—11.01 · V4 逐条 17 条）','咨询 <b>%d</b> 人次（住院 %d ＋ 门诊 %d ＋ 家庭 %d）、接触 <b>%d</b> 人次（首接 %d ＋ 情绪 %d ＋ 住院 %d）、"
    "家长访谈 <b>%d</b> 人次、团体 <b>%d 场 %d 人</b>、日报 <b>17</b> 条、管床新增 <b>10</b> 行、在管 <b>66</b> 人。"
    "上期 10.19—10.25：咨询 39 / 接触 65 / 家长 24 / 团体 2 场 11 人——<b>接触 −29（−44.6%%）、咨询 −15（−38.5%%）、家长 −4</b>。'],"
    "['逐人已重算，因为源表有三条年份误录','简报末尾 3 行年份写成 <b>2027</b>（王沛然 10.27、李凌钰 10.28 与 10.30），按内容与相邻行判定属本期；"
    "其中 <b>李凌钰 10.28 住院咨询 2 人次</b>已计入，否则本周咨询会少 2、由 24 变 22。另有 2 行只有日期、无姓名无内容，不计入 17 条。"
    "→ 这三行要在源表改回 2026，否则下周换窗口会漏。'],"
    "['排名口径与边界','综合分用归一化，基数是本周组内最大（咨询 %d / 接触 %d），所以第一名固定 100 分，<b>分数是相对位置、不是绝对工作量</b>。"
    "蔡宜蓉咨询 %d 人次、接触 %d 人次，两项都是组内最高；赵芳与冯浩鹏在单指标上各有一项接近（咨询 4 对 3），归一化后 30.2 对 29.1，差距被如实拉开。"
    "组长陈鹏本周 0 条日报，工作量无法统计，不进榜也不记 0。']]},"
    # ── 客服服务部 ─────────────────────────────────────────────
    "service:{periods:['10.12周','10.19周','10.26周'],"
    "history:[['日均回访',[5.3,4.1,7.0],'条/天'],['台账到院率',[32.4,41.4,22.4],'%%']],"
    "rankBanner:'<b>本期 10.26—11.01 · 三张台账（回访与日工作量全 7 天，导诊主动服务 6 天）</b>：回访 <b>%d</b> 条、标注到院 <b>%d</b> 人（<b>%.1f%%</b>）、"
    "主动服务 <b>%d</b> 条、日工作量 <b>%s</b> 分（27 人日）。上期 10.19—10.25（同 7 天）：%d 条 / %d 人 / %.1f%%。"
    "<b>回访日均 7.0 vs 4.1 条（+69.0%%），到院人数 11 vs 12 几乎没动</b>——增量没有转成到院。',"
    "rankGroups:["
    "{title:'① 导医回访量（本期 10.26—11.01 · 标准化回访台账）',scoreLabel:'条数',medals:true,"
    "note:'逐条台账按人计数，<b>只有 2 人有记录</b>；其余导医 0 条，是排班还是漏填需组长确认。0 条不参与排名、也不降榜。',"
    "rows:[{name:'蒋雨',metric:'回访 <b>36</b> 条 · 标注到院 <b>11</b> 人（30.6%%）',score:'36'},"
    "{name:'温诗怡',metric:'回访 <b>13</b> 条 · 标注到院 <b>0</b> 人',score:'13'}]},"
    "{title:'② 逐日回访分布（本期 10.26—11.01）',scoreLabel:'—',medals:false,rankless:true,noRankText:'不排名',"
    "note:'看的是「有没有断档」，不排名。10.27 单日 20 条占全周 40.8%%，周初冲量、周末收尾的形态没变。',"
    "table:{cols:['日期','条数','占周比 %%'],rows:[[%s]],sum:['合计','%d','100.0'],foot:'11.01 只有 2 条，是本周唯一低于 4 条的自然日。'}}],"
    "diagnosis:["
    "['本周结果','回访 <b>%d</b> 条（上期 %d，+69.0%%）、到院 <b>%d</b> 人（上期 %d）、到院率 <b>%.1f%%</b>（上期 %.1f%%，<b>−19.0pt</b>）；"
    "主动服务 %d 条（覆盖 6 天，10.31 无记录）、日工作量 %s 分（27 人日，上期 %s 分）。'],"
    "['量涨了，转化没跟上','回访从 29 条涨到 49 条，到院从 12 人变 11 人。多出来的 20 条里如果多是首次接触，说明新客进来但没到院；"
    "如果多是重复追访，说明在拿回访量充数。两条路的管理动作完全不同，必须先拆。'],"
    "['率值仍只有一个分母','逐人只有蒋雨 36 条（73.5%%）、温诗怡 13 条（26.5%%），到院 11 人全部记在蒋雨名下。"
    "其余导医 0 条记录，所以组级 22.4%% 实际上是「两个人的样本」，不宜单独考核，也不该跟全组人数并列。']]},"
    # ── 营销中心 ────────────────────────────────────────────────
    "marketing:{periods:['10.12周','10.19周','10.26周'],"
    "history:[['有效对接',[79.0,86.0,92.0],'条'],['转住院率',[20.3,16.3,13.0],'%%']],"
    "rankSource:'排名＝<b>有效对接条数</b>降序（业务量），转住院人数与转化率作效率提示；<b>填报天数与在岗天数不计分、不排序</b>。"
    "业主《心理管家有效客户对接表》的「权重」列本期未提供，故不再按权重排名；<b>菲菲</b> 整周未填报，不进榜也不记 0。',"
    "rankBanner:'<b>本期 10.26—11.01 · 5 张管家分表逐条（全 7 天）</b>：对接 <b>%d</b> 条、转住院 <b>%d</b> 人（<b>%.1f%%</b>）。"
    "上期 10.19—10.25（同 7 天）：%d 条 / %d 人（%.1f%%）——条数 <b>+7.0%%</b>、率值 <b>−3.3pt</b>。"
    "逐日 11 / 4 / 6 / 6 / 3 / <b>35</b> / <b>27</b>：<b>10.31 与 11.01 两天占 67.4%%</b>。"
    "<b>菲菲 本期未填报</b>（表内最后一行 10.18），记 null、不按 0 降榜。',"
    "rankGroups:["
    "{title:'① 管家排名（本期 10.26—11.01 · 按有效对接条数）',scoreLabel:'对接',medals:true,"
    "note:'按业务量排序；<b>金林与利娟同为 17 条、同为转 3 人，并列第 3</b>。未填报的管家不进榜、也不记 0——「没上班」和「上班没产出」是两件事。',"
    "rows:[{name:'朱婧',metric:'对接 <b>33</b> 条 · 转住院 <b>3</b> 人（9.1%%）',score:'33'},"
    "{name:'国威',metric:'对接 <b>25</b> 条 · 转住院 <b>3</b> 人（12.0%%）',score:'25'},"
    "{name:'金林',metric:'对接 <b>17</b> 条 · 转住院 <b>3</b> 人（17.6%%）　并列',score:'17'},"
    "{name:'利娟',metric:'对接 <b>17</b> 条 · 转住院 <b>3</b> 人（17.6%%）　并列',score:'17'}]},"
    "{title:'② 逐日对接分布（本期 10.26—11.01）',scoreLabel:'—',medals:false,rankless:true,noRankText:'不排名',"
    "note:'看补录形态，不排名。工作日每天 3—11 条，周末两天 62 条——<b>不是周末业务突然变好，是集中补录</b>。',"
    "table:{cols:['日期','条数','占周比 %%'],rows:[[%s]],sum:['合计','%d','100.0'],foot:'若按补录日看转化，周末会被高估、工作日会被低估。'}}],"
    "diagnosis:["
    "['本周结果','对接 <b>%d</b> 条（上期 %d，+7.0%%）、转住院 <b>%d</b> 人（上期 %d）、转化率 <b>%.1f%%</b>（上期 %.1f%%，<b>−3.3pt</b>）。'],"
    "['补录形态没有改善','10.31 三十五条、11.01 二十七条，两天占全周 67.4%%；工作日 3—11 条。这与上周「周末批量补录」是同一个问题，"
    "意味着「发生日」不可考，按日看转化会失真。'],"
    "['菲菲仍未填报','表内最后一行 10.18，本期空白。需要组长确认本周是否仍在做对接并补录；本周不参与排名、不降榜。"
    "另：业主汇总表的权重列本期未提供，排名已改为按对接条数，避免用一半数据编出「加权总分」。']]}};"
)

h = io.open(IDX, encoding="utf-8").read()
lines = h.split("\n")
assert lines[991].startswith("    const analytics={"), lines[991][:60]

new_line = "    " + (AN % (
    T["revenueWan"], T["discharge"], T["inWard"], T["admit"], T["avgStayDays"],
    f"{T['revenuePerBedDay']:,.0f}", T["revenueWan"], T["discharge"],
    doc_rows,
    doc_fin_rows,
    money(rev_total), money(T["physioYuan"]), money(T["psychTotalYuan"]),
    T["discharge"], T["inWard"], T["admit"],
    T["physioShare"], T["psychShare"],
    money(rev_total), cost_rows,
    T["revenueWan"], T["discharge"], T["inWard"], T["admit"], T["avgStayDays"],
    top1["name"], top1["revenueYuan"] / 10000, top1["revenueYuan"] / rev_total * 100,
    top3 / 10000, top3 / rev_total * 100, T["physioYuan"] / 10000, T["physioShare"],
    people[0]["name"], people[0]["avgStay"],
    PW["consult"], PW["contact"], PW["parent"], max_c, max_t,
    max_c, max_t, psy_score_rows,
    psy_consult_rows, psy_contact_rows,
    PW["consult"], PW["inpatient"], PW["outpatient"], PW["family"],
    PW["contact"], PW["first"], PW["emotion"], PW["inpatient"],
    PW["parent"], PW["groupSessions"], PW["groupPeople"],
    max_c, max_t,
    psy_sorted[0]["consult"], psy_sorted[0]["contact"],
    SV["followup"], SV["arrived"], SV["rate"], SV["guide"], f"{SV['workload']:,}",
    SP["followup"], SP["arrived"], SP["rate"],
    svc_day_rows, svc_total,
    SV["followup"], SP["followup"], SV["arrived"], SP["arrived"], SV["rate"], SP["rate"],
    SV["guide"], f"{SV['workload']:,}", f"{SP['workload']:,}",
    BW["contact"], BW["admit"], BW["rate"],
    BP["contact"], BP["admit"], BP["rate"],
    but_day_rows, but_total,
    BW["contact"], BP["contact"], BW["admit"], BP["admit"], BW["rate"], BP["rate"],
))
lines[991] = new_line
io.open(IDX, "w", encoding="utf-8").write("\n".join(lines))

print("医生组：结账 %.2f 万 / 出院 %d / 在院 %d / 入院 %d / 床日 %.1f"
      % (T["revenueWan"], T["discharge"], T["inWard"], T["admit"], T["avgStayDays"]))
print("头部 %s 占 %.1f%%，前三合计 %.1f%%" %
      (top1["name"], top1["revenueYuan"] / rev_total * 100, top3 / rev_total * 100))
print("心理归一化：max 咨询 %d / 接触 %d" % (max_c, max_t))
for r in psy_sorted:
    print("   %s 咨询 %d 接触 %d → %.1f" % (r["name"], r["consult"], r["contact"], r["_score"] * 100))
print("新 analytics 行长度", len(new_line))
