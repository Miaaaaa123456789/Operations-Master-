#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/nursing-week.json 渲染成 index.html 里的「护理组 · 考核与质量」面板。

设计原则（业主 2026-10-26 要求）：不是把 Excel 贴上去，要有 AI 判断 + 数据呈现。
面板结构：
  head / 口径 banner
  AI 本周判断（一句话结论 + 3 个支撑数字）
  6 张 KPI（填报率 / 日均分 / 首末位）
  双维四象限 + AI 三条结论
  综合得分排行（横向条）
  4 张明细表（Tab）
  数据核验与行动（4 条，含 3 条红线）
  物理治疗「稍后更新」占位
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "data", "nursing-week.json")
HTML = os.path.join(ROOT, "index.html")

CSS_OPEN = "    /* == NPA-2026-10-26 == 护理组 AI 分析层 == */\n"
CSS_CLOSE = "    /* == /NPA-2026-10-26 == */\n"

CSS = r"""
    .npa-hero{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);border:1px solid #E3E8F2;border-radius:16px;overflow:hidden;margin:0 0 12px;background:#fff}
    .npa-hero-main{padding:16px 18px;background:linear-gradient(135deg,#F7FAFF 0%,#FFF 64%)}
    .npa-eyebrow{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.1em;color:#0058B0;background:#EAF2FE;border-radius:6px;padding:3px 8px;margin-bottom:9px}
    .npa-hero-main h3{margin:0 0 7px;font-size:16px;line-height:1.45;color:#1B2233;font-weight:800}
    .npa-hero-main h3 b{color:#A8203C}
    .npa-hero-main p{margin:0;font-size:12.5px;line-height:1.75;color:#5B6377}
    .npa-hero-main p b{color:#1B2233;font-weight:800}
    .npa-hero-side{display:grid;grid-template-rows:repeat(3,minmax(0,1fr));border-left:1px solid #E3E8F2;background:#FBFCFE}
    .npa-fact{padding:10px 15px;border-bottom:1px solid #EDF0F6;display:flex;flex-direction:column;justify-content:center}
    .npa-fact:last-child{border-bottom:0}
    .npa-fact strong{display:block;font-size:19px;font-weight:800;color:#0058B0;line-height:1.2;font-variant-numeric:tabular-nums}
    .npa-fact strong.bad{color:#A8203C}
    .npa-fact span{font-size:10.5px;color:#6B7280;line-height:1.4;margin-top:2px}
    .npa-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-bottom:12px}
    .npa-kpi{padding:11px 12px;border:1px solid #E3E8F2;border-radius:13px;background:#fff;min-width:0}
    .npa-kpi label{font-size:10.5px;color:#6B7280;font-weight:700;display:block;margin-bottom:5px;line-height:1.3}
    .npa-kpi strong{font-size:19px;font-weight:800;color:#1B2233;font-variant-numeric:tabular-nums;display:block;line-height:1.15}
    .npa-kpi strong em{font-size:10.5px;font-style:normal;color:#8A90A0;font-weight:700;margin-left:2px}
    .npa-kpi small{display:block;font-size:10px;color:#8A90A0;margin-top:3px;line-height:1.45}
    .npa-kpi.warn strong{color:#A8203C}
    .npa-kpi.ok strong{color:#12805A}
    .npa-duo{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:12px}
    .npa-card{border:1px solid #E3E8F2;border-radius:15px;background:#fff;padding:13px 14px;margin-bottom:12px}
    .npa-card h4{margin:0 0 3px;font-size:13.5px;color:#1B2233;display:flex;align-items:center;gap:7px;flex-wrap:wrap}
    .npa-card h4 em{font-style:normal;font-size:10px;font-weight:800;color:#0058B0;background:#EAF2FE;border-radius:5px;padding:2px 6px}
    .npa-card .cap{margin:0 0 10px;font-size:11px;color:#6B7280;line-height:1.55}
    .npa-quad{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
    .npa-q{border:1px solid #E8ECF5;border-radius:11px;padding:9px 10px;background:#FAFBFE;min-height:80px}
    .npa-q label{display:flex;justify-content:space-between;gap:6px;font-size:10.5px;font-weight:800;color:#5B6377;margin-bottom:5px;align-items:baseline}
    .npa-q label i{font-style:normal;color:#8A90A0;font-weight:700;font-size:10px;white-space:nowrap}
    .npa-q p{margin:0;font-size:11.5px;line-height:1.6;color:#3D4457}
    .npa-q.hh{background:#F0FAF7;border-color:#C9EBE2}.npa-q.hh label{color:#12805A}
    .npa-q.hl{background:#FFF8F0;border-color:#F3E2C6}.npa-q.hl label{color:#A5670F}
    .npa-q.lh{background:#F4F8FF;border-color:#D6E4F7}.npa-q.lh label{color:#1D4ED8}
    .npa-q.ll{background:#FCF2F3;border-color:#F2CCD4}.npa-q.ll label{color:#A8203C}
    .npa-find{display:grid;gap:9px}
    .npa-find-row{display:grid;grid-template-columns:22px 1fr;gap:9px}
    .npa-find-no{width:22px;height:22px;border-radius:50%;background:#0058B0;color:#fff;font-size:11px;font-weight:800;display:grid;place-items:center;margin-top:1px}
    .npa-find-row strong{display:block;font-size:12.5px;color:#1B2233;margin-bottom:2px;line-height:1.4}
    .npa-find-row p{margin:0;font-size:11.5px;line-height:1.62;color:#5B6377}
    .npa-find-row p b{color:#A8203C}
    .npa-rk{display:grid;gap:1px}
    .npa-rk-row{display:grid;grid-template-columns:24px 58px minmax(0,1fr) 50px 92px;gap:8px;align-items:center;padding:5px 6px;border-radius:8px}
    .npa-rk-row:hover{background:#F7F9FD}
    .npa-rk-row .no{font-size:11px;font-weight:800;color:#9AA0AF;text-align:center;font-variant-numeric:tabular-nums}
    .npa-rk-row.m1 .no{color:#B4791F}.npa-rk-row.m2 .no{color:#6B7280}.npa-rk-row.m3 .no{color:#9A6B3F}
    .npa-rk-row .nm{font-size:12px;font-weight:700;color:#242A38;white-space:nowrap}
    .npa-rk-row .bar{height:9px;border-radius:5px;background:#EEF1F7;overflow:hidden}
    .npa-rk-row .bar i{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,#5C9DE8,#0058B0);transform-origin:left;animation:growBar .8s ease both}
    .npa-rk-row.m1 .bar i{background:linear-gradient(90deg,#E8A03C,#C77A00)}
    .npa-rk-row .sv{font-size:12px;font-weight:800;color:#0058B0;text-align:right;font-variant-numeric:tabular-nums}
    .npa-rk-row .qt{font-size:10px;color:#8A90A0;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
    .npa-rk-row .qt b{color:#5B6377;font-weight:700}
    .npa-ck{display:grid;gap:8px}
    .npa-ck-item{border:1px solid #E3E8F2;border-left:4px solid #E0576F;border-radius:11px;padding:10px 12px;background:#fff}
    .npa-ck-item.warn{border-left-color:#C77A00}
    .npa-ck-item.ok{border-left-color:#1F9D55}
    .npa-ck-item h5{margin:0 0 4px;font-size:12.5px;color:#1B2233;display:flex;gap:7px;align-items:center;flex-wrap:wrap;line-height:1.4}
    .npa-ck-item h5 em{font-style:normal;font-size:9.5px;font-weight:800;padding:2px 6px;border-radius:5px;background:#FCF2F3;color:#A8203C;white-space:nowrap}
    .npa-ck-item.warn h5 em{background:#FFF6E5;color:#8A5B00}
    .npa-ck-item.ok h5 em{background:#EAF7F0;color:#12805A}
    .npa-ck-item p{margin:0;font-size:11.5px;line-height:1.62;color:#5B6377}
    .npa-ck-item p.doit{margin-top:5px;color:#168C83;font-weight:600}
    .npa-ck-item p b{color:#1B2233}
    .npa-pending{display:flex;gap:10px;align-items:flex-start;padding:11px 13px;border-radius:12px;background:#F6F7FB;border:1px dashed #CBD2E0;font-size:11.5px;color:#5B6377;line-height:1.62;margin-top:2px}
    .npa-pending .tg{flex:0 0 auto;font-size:10px;font-weight:800;color:#7C6338;background:#FFF6E5;border:1px solid #F0DFBE;border-radius:999px;padding:3px 9px;margin-top:1px}
    .npa-pending b{color:#3D4457}
    .npa-flag{display:inline-block;font-size:9.5px;font-weight:800;color:#8A5B00;background:#FFF6E5;border:1px solid #F0DFBE;border-radius:5px;padding:1px 5px;margin-left:4px;white-space:nowrap}
    @media(max-width:900px){
      .npa-hero{grid-template-columns:1fr}
      .npa-hero-side{border-left:0;border-top:1px solid #E3E8F2;grid-template-rows:none;grid-template-columns:repeat(3,1fr)}
      .npa-fact{border-bottom:0;border-right:1px solid #EDF0F6}
      .npa-fact:last-child{border-right:0}
      .npa-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}
      .npa-duo{grid-template-columns:1fr}
    }
    @media(max-width:600px){
      .npa-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
      .npa-rk-row{grid-template-columns:22px 52px minmax(0,1fr) 44px}
      .npa-rk-row .qt{display:none}
      .npa-quad{grid-template-columns:1fr}
    }
"""


def f(v, nd=1, dash="—"):
    if v is None:
        return dash
    if isinstance(v, str):
        return v
    return ("%." + str(nd) + "f") % v


def cell(v, cls="npst-num"):
    if v is None:
        return '<td class="%s npst-null">—</td>' % cls
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return '<td class="%s">%s</td>' % (cls, s)


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    A = d["analytics"]
    days = d["period"]["days"]
    work, qc, norm, comp = d["work"], d["qc"], d["norm"], d["comp"]
    dist, cst = A["dist"], A["comp"]

    o = []
    w = o.append

    # ---------- head + banner ----------
    w('<div class="np-head"><span class="np-head-title">护理组 · 考核与质量</span>'
      '<span class="np-head-sub">10.19—10.25 周 · 考核窗口 10.18—10.24（%d 人 / %d 天）</span></div>'
      % (A["nQc"], 7))
    w('<div class="np-banner"><b>数据窗口 10.18—10.24</b>（源表按周日—周六出表，比自然周早 1 天；'
      '10.25 护理部未交，<b>不拿上周值补位</b>）。来源《护士工作量及质量统计》四张 sheet＋《质控及物理治疗统计表》。'
      '⚠ 本期有两处口径必须知道：<b>平均分 = 累计分 ÷ 7</b>（不是 ÷ 勤天数，缺勤按 0 摊）；'
      '<b>综合得分 = 工作量指数与质控均分的算术平均</b>（名义各 50%%，因两列量纲不同，实际工作量占 %.0f%%、质控占 %.0f%%）。'
      '<b>质控 7 日数值与 10.11—10.17 存档逐格一致</b>，按「待核」呈现，不作为扣罚依据。'
      '<b>物理治疗模块本期暂不更新</b>，等新表。</div>'
      % (cst["wWeightReal"], cst["qcWeightReal"]))

    # ---------- AI 本周判断 ----------
    w('<div class="npa-hero"><div class="npa-hero-main">'
      '<span class="npa-eyebrow">AI 本周判断</span>'
      '<h3>护理组的瓶颈不是「分低」，是<b>「表没填满」</b></h3>'
      '<p>7 天里 %d 个工作量填报格只填了 <b>%d 格（%.1f%%）</b>，质控 %d 格填了 <b>%d 格（%.1f%%）</b>。'
      '分数其实很集中：%d 个有效分值全部落在 <b>%s—%s</b> 分，组内标准差仅 %.1f 分（变异系数 %.1f%%）——'
      '同样的活、同样的水平，<b>真正拉开名次的是谁交了表、交了几次</b>。'
      '所以本周的第一动作不该是「抓分数」，而是<b>把日报填满</b>：出勤从人均 %.1f 天提到 6 天，'
      '指数和质控均分就会整体自然上移，不需要任何人多干活。</p></div>'
      '<div class="npa-hero-side">'
      '<div class="npa-fact"><strong class="bad">%.1f%%</strong><span>工作量填报完整率 · %d / %d 格</span></div>'
      '<div class="npa-fact"><strong>%.1f</strong><span>综合得分首末差 · 67.7 对 19.3</span></div>'
      '<div class="npa-fact"><strong class="bad">3</strong><span>条数据核验红线 · 见页尾</span></div>'
      '</div></div>'
      % (A["workSlots"], A["workFill"], A["workRate"],
         A["qcSlots"], A["qcFill"], A["qcRate"],
         dist["workN"], f(dist["workLow"], 0), f(dist["workTop"], 0), dist["workSd"], dist["workCV"],
         A["workFill"] / A["nWork"], A["workRate"], A["workFill"], A["workSlots"],
         cst["spread"]))

    # ---------- KPI ----------
    w('<div class="npa-kpis">')
    w('<div class="npa-kpi warn"><label>工作量填报</label><strong>%.1f<em>%%</em></strong>'
      '<small>%d / %d 格 · 人均 %.1f 天</small></div>'
      % (A["workRate"], A["workFill"], A["workSlots"], A["workFill"] / A["nWork"]))
    w('<div class="npa-kpi warn"><label>质控填报</label><strong>%.1f<em>%%</em></strong>'
      '<small>%d / %d 格 · 人均 %.1f 天</small></div>'
      % (A["qcRate"], A["qcFill"], A["qcSlots"], A["qcFill"] / A["nQc"]))
    w('<div class="npa-kpi"><label>工作量日均分</label><strong>%s<em>分</em></strong>'
      '<small>σ %.1f · 最高 %s / 最低 %s</small></div>'
      % (f(dist["workMean"]), dist["workSd"], f(dist["workTop"], 0), f(dist["workLow"], 0)))
    w('<div class="npa-kpi"><label>质控日均分</label><strong>%s<em>分</em></strong>'
      '<small>σ %.1f · ÷7 后均分 %s</small></div>'
      % (f(dist["qcMean"]), dist["qcSd"], f(sum(c["qcAvg"] for c in comp) / len(comp))))
    t1 = next(c for c in comp if c["rank"] == 1)
    w('<div class="npa-kpi ok"><label>综合首名</label><strong>%s<em>分</em></strong>'
      '<small>%s · 工作量第 %d / 质控第 %d</small></div>'
      % (f(t1["score"]), t1["name"], t1["wRank"], t1["qcRank"]))
    tz = next(c for c in comp if c["rank"] == len(comp))
    w('<div class="npa-kpi warn"><label>综合末位</label><strong>%s<em>分</em></strong>'
      '<small>%s · 仅 %d 天工作量记录</small></div>'
      % (f(tz["score"]), tz["name"],
         next(x["attend"] for x in work if x["name"] == tz["name"])))
    w('</div>')

    # ---------- 四象限 + 三条结论 ----------
    Q = A["quad"]
    qn = {"hh": "双优", "hl": "量足·质控弱", "lh": "质控强·量偏少", "ll": "双弱"}

    def qcell(k, cls, sub):
        names = Q["cells"][k]
        return ('<div class="npa-q %s"><label>%s <i>%d 人 · %s</i></label><p>%s</p></div>'
                % (cls, qn[k], len(names), sub, "、".join(names) or "—"))

    w('<div class="npa-duo">')
    w('<div class="npa-card"><h4>双维四象限 <em>工作量 × 质控</em></h4>'
      '<p class="cap">横轴工作量指数（均值 %s，满分 100）、纵轴质控 ÷7 均分（均值 %s）。'
      '分界线取组内均值——<b>不是及格线，是相对位置</b>。</p>'
      % (f(Q["x0"]), f(Q["y0"])))
    w('<div class="npa-quad">')
    w(qcell("lh", "lh", "质控≥均值"))
    w(qcell("hh", "hh", "量质双高"))
    w(qcell("ll", "ll", "量质双低"))
    w(qcell("hl", "hl", "指数≥均值"))
    w('</div>')
    w('<p class="cap" style="margin:9px 0 0">判断：<b>双弱仅 2 人</b>，说明整体底子不差；'
      '真正要处理的是「量足·质控弱」的 5 人——他们的质控记录要么天数少、要么单日跳变，'
      '是<b>记录问题多于能力问题</b>。</p></div>')

    w('<div class="npa-card"><h4>AI 三条结论</h4>'
      '<p class="cap">每条都带可核对的数字，能直接拿去问人。</p><div class="npa-find">')
    for i, fd in enumerate(A["findings"], 1):
        w('<div class="npa-find-row"><span class="npa-find-no">%d</span><div>'
          '<strong>%s</strong><p>%s</p></div></div>' % (i, fd["tag"], fd["text"]))
    w('</div></div>')
    w('</div>')

    # ---------- 排行 ----------
    w('<div class="npa-card"><h4>综合得分排行 <em>16 人</em></h4>'
      '<p class="cap">条长按得分占首名比例；右侧两组名次分别是<b>工作量指数名次</b>与<b>质控均分名次</b>，'
      '两个名次差得越远，说明这个人偏科越明显。</p><div class="npa-rk">')
    top = cst["max"]
    for c in sorted(comp, key=lambda x: x["rank"]):
        cls = " m%d" % c["rank"] if c["rank"] <= 3 else ""
        w('<div class="npa-rk-row%s"><span class="no">%d</span><span class="nm">%s</span>'
          '<span class="bar"><i style="width:%.1f%%"></i></span>'
          '<span class="sv">%s</span>'
          '<span class="qt">量 <b>%d</b> · 质 <b>%d</b></span></div>'
          % (cls, c["rank"], c["name"], c["score"] / top * 100, f(c["score"]),
             c["wRank"], c["qcRank"]))
    w('</div></div>')

    # ---------- 4 张明细表 ----------
    w('<div class="np-tabs" id="npStdTabs">'
      '<button class="np-tab np-std-tab active" type="button" data-npstd="rank">综合排名</button>'
      '<button class="np-tab np-std-tab" type="button" data-npstd="work">归一化工作量</button>'
      '<button class="np-tab np-std-tab" type="button" data-npstd="score">百分制考核分</button>'
      '<button class="np-tab np-std-tab" type="button" data-npstd="qc">每日质控</button></div>')

    # 1 综合排名
    w('<div class="np-pane active" id="npStdRankPane"><div class="np-orig-wrap">'
      '<table class="np-orig"><thead><tr><th>名次</th><th>姓名</th>'
      '<th class="npst-num">工作量出勤</th><th class="npst-num">工作量指数</th><th class="npst-num">量名次</th>'
      '<th class="npst-num">质控出勤</th><th class="npst-num">质控均分<br>(÷7)</th><th class="npst-num">质名次</th>'
      '<th class="npst-num">综合得分</th></tr></thead><tbody>')
    qmap = {q["name"]: q for q in qc}
    for c in sorted(comp, key=lambda x: x["rank"]):
        wq = next(x for x in work if x["name"] == c["name"])
        qq = qmap.get(c["name"], {})
        w('<tr><td><span class="np-rankno">%d</span></td><td class="npst-name">%s</td>'
          '%s%s%s%s%s%s<td class="npst-num npst-total">%s</td></tr>'
          % (c["rank"], c["name"],
             cell(wq["attend"]), cell(c["wIdx"]), cell(c["wRank"]),
             cell(qq.get("attend")), cell(c["qcAvg"]), cell(c["qcRank"]),
             f(c["score"])))
    w('</tbody></table></div>'
      '<p class="npst-note"><b>综合得分 = （工作量指数 ＋ 质控均分）÷ 2</b>。'
      '问题是工作量指数按满分 100 计、质控均分按 ÷7 计（本组最高只到 55.4），'
      '两列量纲不同却直接算术平均，<b>质控项实际只占 %.0f%%</b>，名义上的「质量 50%%」并未兑现——'
      '这是评分模型本身的结构问题，建议下期改为<b>先各自转标准分（Z 分或百分位）再按权重合成</b>。'
      '</p></div>' % cst["qcWeightReal"])

    # 2 归一化工作量
    w('<div class="np-pane" id="npStdWorkPane"><div class="np-orig-wrap">'
      '<table class="np-orig np-wide"><thead><tr><th>姓名</th>')
    for dd in days:
        w('<th class="npst-num">%s</th>' % dd)
    w('<th class="npst-num">出勤</th><th class="npst-num">平均指数</th><th class="npst-num">名次</th></tr></thead><tbody>')
    for n in sorted(norm, key=lambda x: x["rank"]):
        w('<tr><td class="npst-name">%s</td>' % n["name"])
        for v in n["days"]:
            if v is None:
                w('<td class="npst-num npst-null">—</td>')
            else:
                over = ' style="color:#A8203C;font-weight:800"' if v > 100.05 else ''
                w('<td class="npst-num"%s>%s</td>' % (over, ("%.1f" % v).rstrip("0").rstrip(".")))
        w('%s%s%s</tr>' % (cell(sum(1 for x in n["days"] if x is not None)),
                           cell(n["avg"]), cell(n["rank"])))
    w('</tbody></table></div>'
      '<p class="npst-note">指数 = 当日得分 ÷ 当日组内最高分 × 100，用来消除不同日之间题目难度差异。'
      '<b style="color:#A8203C">杨思菡 10.18 的 103.4 是越界值</b>：源表该日「每日最大值」填 72.5，'
      '但当日她实得 75，正确指数应为 100。这一格已被强制抬高 3.4 点，同时把当日其他人的指数被动压低。'
      '<b>平均指数 = 7 天指数之和 ÷ 7</b>，未填天数按 0 —— 所以「少填一天」等于全部指数打八折。</p></div>')

    # 3 百分制考核分（工作量原始分）
    w('<div class="np-pane" id="npStdScorePane"><div class="np-orig-wrap">'
      '<table class="np-orig np-wide"><thead><tr><th>姓名</th>')
    for dd in days:
        w('<th class="npst-num">%s</th>' % dd)
    w('<th class="npst-num">出勤</th><th class="npst-num">累计分</th>'
      '<th class="npst-num">最高</th><th class="npst-num">最低</th><th class="npst-num">极差</th></tr></thead><tbody>')
    for wkr in sorted(work, key=lambda x: x["rank"]):
        w('<tr><td class="npst-name">%s</td>' % wkr["name"])
        for v in wkr["days"]:
            w(cell(v))
        rng = None if (wkr["max"] is None) else round(wkr["max"] - wkr["min"], 1)
        w('%s%s%s%s%s</tr>' % (cell(wkr["attend"]), cell(wkr["sum"]),
                               cell(wkr["max"]), cell(wkr["min"]), cell(rng)))
    w('</tbody></table></div>'
      '<p class="npst-note">这就是源表的「百分制考核分值」原始分，<b>全组最高单日只有 75 分</b>（杨思菡 10.18），'
      '日均 %s 分、标准差 %.1f。号称百分制却没人过 75，说明<b>评分尺度整体压在 60—70 区间</b>，'
      '区分度不足（变异系数仅 %.1f%%）——这会让排名更像噪声，建议护理部校准评分刻度。</p></div>'
      % (f(dist["workMean"]), dist["workSd"], dist["workCV"]))

    # 4 每日质控
    w('<div class="np-pane" id="npStdQcPane"><div class="np-orig-wrap">'
      '<table class="np-orig np-wide"><thead><tr><th>姓名</th>')
    for dd in days:
        w('<th class="npst-num">%s</th>' % dd)
    w('<th class="npst-num">勤天数</th><th class="npst-num">累计分</th>'
      '<th class="npst-num">均分(÷7)</th><th class="npst-num">名次</th></tr></thead><tbody>')
    for q in sorted(qc, key=lambda x: x["rank"]):
        mark = ' <span class="npa-flag">仅质控</span>' if q["name"] not in {x["name"] for x in work} else ''
        w('<tr><td class="npst-name">%s%s</td>' % (q["name"], mark))
        for v in q["days"]:
            w(cell(v))
        w('%s%s%s%s</tr>' % (cell(q["attend"]), cell(q["sum"]), cell(q["avg7"]), cell(q["rank"])))
    w('</tbody></table></div>'
      '<p class="npst-note"><b>⚠ 整张表与 10.11—10.17 存档逐格相同（72 个有分数格，差异 0 格）</b>，'
      '疑为只平移表头日期、未重新采集，已标「待核」，<b>暂不作为绩效扣减依据</b>。'
      '另：杜萧只在本表出现（6 天、均分 50.6，质控第 2），工作量表没有他这一行，'
      '因此被排除在 16 人综合排名之外——补录后名次会变。</p></div>')

    # ---------- 数据核验 ----------
    w('<div class="npa-card"><h4>数据核验与行动 <em>%d 条</em></h4>'
      '<p class="cap">每条都能对着源表复现；红线项建议本周内改表。</p><div class="npa-ck">'
      % len(A["checks"]))
    lvl = {"critical": ("", "红线"), "warn": (" warn", "待核"), "ok": (" ok", "通过")}
    for ck in A["checks"]:
        cls, tag = lvl.get(ck["level"], ("", "提示"))
        w('<div class="npa-ck-item%s"><h5>%s<em>%s</em></h5><p>%s</p><p class="doit">→ %s</p></div>'
          % (cls, ck["title"], tag, ck["fact"], ck["todo"]))
    w('</div></div>')

    # ---------- 物理治疗占位 ----------
    pt = d.get("physio") or {}
    tot = pt.get("total") or {}
    w('<div class="npa-pending"><span class="tg">稍后更新</span><div>'
      '<b>物理治疗模块本期不动</b>，等业主新表。《质控及物理治疗统计表》里的'
      '<b>物理治疗明细/汇总已随本轮入库</b>（10.18—10.24 六项：应做 %s / 实做 %s / 完成率 %s），'
      '但按指示<b>先不替换页面现有物理治疗面板</b>，避免半更新造成两处口径不一致。'
      '下轮拿到新表后一次性重做：六项分项完成率＋未做原因拆解＋按住院人数的人均治疗强度。</div></div>'
      % (("%d" % tot["due"]) if tot.get("due") else "—",
         ("%d" % tot["done"]) if tot.get("done") else "—",
         ("%.1f%%" % (tot["rate"] * 100)) if tot.get("rate") else "—"))

    pane = "".join(o)
    # ⚠ 原面板结构是 <div class="sheet-pane" id="nursingPerfPane"><div class="nursing-perf">
    #    ... </div></div>。替换区间止于 diagnosisPane 之前，所以这两个闭合必须自己补，
    #    否则会把 diagnosisPane / 其它 sheet-pane 全部吞进护理面板（表现为「AI 分析页空白」）。
    pane += "</div></div>"

    # ---------- 写回 index.html ----------
    s = open(HTML, encoding="utf-8").read()

    # 1) CSS：替换旧 NPA 块或插到护理面板 style 末尾
    si, ei = s.find(CSS_OPEN), s.find(CSS_CLOSE)
    if si >= 0 and ei > si:
        s = s[:si] + CSS_OPEN + CSS + CSS_CLOSE + s[ei + len(CSS_CLOSE):]
        print("CSS: replaced")
    else:
        head = s.find('<div class="np-head">')
        close = s.rfind('</style>', 0, head)
        if close < 0:
            raise SystemExit("找不到护理面板 style 结束标签")
        s = s[:close] + CSS_OPEN + CSS + CSS_CLOSE + s[close:]
        print("CSS: inserted at", close)

    # 2) 面板正文
    a = s.find('<div class="np-head">')
    b = s.find('<div class="sheet-pane" id="diagnosisPane">')
    if a < 0 or b < 0 or b < a:
        raise SystemExit("找不到护理面板边界")
    s = s[:a] + pane + s[b:]
    print("PANE: %d -> %d chars" % (b - a, len(pane)))

    open(HTML, "w", encoding="utf-8").write(s)
    print("OK", HTML, len(s))


if __name__ == "__main__":
    main()
