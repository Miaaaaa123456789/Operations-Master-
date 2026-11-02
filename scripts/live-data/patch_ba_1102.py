# -*- coding: utf-8 -*-
"""2026-11-02 换期：business-analysis.js 从 10.19—10.25 叙事切到 10.26—11.01。
所有数字来自 data/snapshot.json（revision 47），不手写臆造。"""
import io, re, sys, json

P = 'business-analysis.js'
src = io.open(P, encoding='utf-8').read()

# ---------- 1) SEC 常量块 ----------
SEC_NEW = u'''  var SEC = {
    /* ⭐ 2026-11-02：护理部本期（10.26—11.01）周报未提交 —— 六项治疗应做/实做、电休克、
       工娱场次均无新数。源表最新只到 10.18—10.24（652 / 605 / 92.8%），按契约记 null、
       不拿存档值顶替本期。 */
    nurseShould: null, nurseDone: null, nurseMiss: null, nurseRate: '\\u2014', nurseDrop: '\\u2014',
    nurseEct: null,
    nurseWeek: '10.26\\u201411.01\\uff08\\u672a\\u62a5\\uff09',
    /* 客服《回访台账》本期 10.26—11.01 已满 7 天：49 条 / 到院 11 人 / 22.4%；
       上期同 7 天（10.19—10.25）29 条 / 12 人 / 41.4%。 */
    svcCallback: 49, svcArrived: 11, svcRate: '22.4', svcRatePrev: '41.4',
    svcPrevCallback: 29, svcPrevArrived: 12, svcGuide: 25, svcWorkload: '3,858',
    mktContacts: 92, mktAdmit: 12, mktRate: '13.0', mktRatePrev: '16.3',
    /* 管家《患者有效对接表》本期 92 条 / 转住院 12 人（13.0%）；
       上期同 7 天 86 / 14（16.3%）；菲菲仍未填报（分表止于 10.18），记 null、不进榜。 */
    mktDeals: 92, mktDealsPrev: 86, mktHosp: 12, mktHospPrev: 14,
    mktConvertRate: '13.0', mktConvertPrev: '16.3',
    mktMonthDeals: 376, mktMonthHosp: 69, mktMonthRate: '18.4',
    inHouse: 33, inHousePrev: 32,
    /* 医生组本期（10.26—11.01）改取出院结账口径（汇报表本周未滚动）：
       结算 21.45 万 / 物理 12.89 万 / 出院 10 / 入院 13 / 在院 36。
       上一期无同源对照 → 环比一律「不可计算」，不拿汇报表旧值硬凑。 */
    docRev: '21.45', docRevPrev: '\\u2014', docRevDelta: '\\u4e0d\\u53ef\\u8ba1\\u7b97',
    docPhysio: '12.89', docPhysioPrev: '\\u2014', docPhysioDelta: '\\u4e0d\\u53ef\\u8ba1\\u7b97',
    docAdmit: 13, docAdmitPrev: null, docAdmitDelta: '\\u4e0d\\u53ef\\u8ba1\\u7b97',
    docDis: 10, docDisPrev: null, docDisDelta: '\\u4e0d\\u53ef\\u8ba1\\u7b97',
    docOpd: null, docOpdPrev: null, docOpdDelta: '\\u4e0d\\u53ef\\u8ba1\\u7b97',
    docDetailAdmit: 13, docDetailDis: 10, docGapAdmit: 0, docGapDis: 0,
    docCabRev: 36
  };'''
SEC_NEW = SEC_NEW.encode('utf-8').decode('unicode_escape') if False else SEC_NEW
# 上一步用了 \\u 转义是为了写完再解码，避免源码里出现难读的长段；这里统一解码为中文
SEC_NEW = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), SEC_NEW)

m1 = re.search(r'  var SEC = \{.*?\n  \};', src, re.S)
assert m1, 'SEC 块未命中'
start = src.index('  var SEC = {')
end = src.index('\n  };', start) + len('\n  };')
src = src[:start] + SEC_NEW + src[end:]

# ---------- 2) buildHTML 主体 ----------
A = '    var analysisHTML=`'
i = src.index(A)
j = src.index('    return analysisHTML;', i)
BODY = u'''    var goalWan = parseFloat(txt(f.goalWan, 260));
    var overWan = (parseFloat(totalWan) - goalWan).toFixed(2);
    var analysisHTML=`<section class="decision-core" id="decisionCore"><header class="dc-head"><div><h2>经营问题总览</h2><p>当前不是单一部门表现不好，而是“营收速度不足、转化链条断点、服务兑现流失、数据口径混乱”同时存在。月度营收进度只是最终表现，根本问题是跨部门转化链没有闭合。</p></div><span class="dc-scope">本期 ${_periodLab} · 数据截至 ${lastShort}（营收 ${lastShort}）</span></header><div class="dc-system"><div class="dc-chain"><div class="dc-node"><i>前端</i><b>触达增加</b><span>客服回访${SEC.svcCallback}条、到院${SEC.svcArrived}人（${SEC.svcRate}%），回访量回升但到院率腰斩</span></div><div class="dc-node"><i>转化</i><b>有效入院不足</b><span>营销接触${SEC.mktContacts} 条、转住院${SEC.mktAdmit} 人（管家对接口径）；每转 1 人需 <b>7.7</b> 条对接（上期 6.1）</span></div><div class="dc-node"><i>服务</i><b>承接与兑现流失</b><span>心理接触 36 人次、咨询 24 人次（环比 −44.6% / −38.5%）；护理本周未交周报</span></div><div class="dc-node"><i>结果</i><b>营收速度不足</b><span>营收日报日均${mtdAvgWan}万（${lastShort} 止），${monthClosed?`全月收官 · 超额 ${overWan} 万`:`达标需${needDailyWan}万`}</span></div></div></div><div class="dc-risks"><article class="dc-risk red"><label>月目标风险</label><strong>${(parseFloat(lagPt)>=0?'落后 ':'领先 ')}${Math.abs(parseFloat(lagPt)).toFixed(1)}pt</strong><p>累计${totalWan}万（${BA_DOT}—${lastShort}），${monthClosed?`<b>${BA_LAB_SP}已收官</b>，完成率 <b>${amountRate}%</b>、<b>超额 ${overWan} 万</b>，月度目标已达成`:`剩余${remainDays}天还需${remainWan}万，日均缺口${gapDailyWan}万`}。</p></article><article class="dc-risk orange"><label>前端转化</label><strong>到院率 ${SEC.svcRate}%</strong><p>本期（10.26—11.01，7 天）回访 ${SEC.svcCallback} 条、到院 ${SEC.svcArrived} 人；<b>到院率由上一期（10.19—10.25，同为 7 天）${SEC.svcRatePrev}% 降到本期 ${SEC.svcRate}%，−19.0 个百分点</b>。回访量 29 → <b>49 条（日均 7.0 vs 4.1，+69.0%）</b>、到院 12 → 11 人（−1 人），<b>量升质降</b>；<b>到院 11 人全部记在蒋雨名下</b>（回访 36 条），温诗怡回访 13 条、到院 0——到院率的分母只来自两人，样本小，暂不当趋势结论。</p></article><article class="dc-risk blue"><label>营销转化</label><strong>${SEC.mktDealsPrev}条 → ${SEC.mktDeals}条</strong><p>管家对接 ${SEC.mktDealsPrev}→${SEC.mktDeals} 条（<b>+7.0%</b>）、转住院 ${SEC.mktHospPrev}→${SEC.mktHosp} 人（<b>−14.3%</b>）、率值 ${SEC.mktConvertPrev}%→${SEC.mktConvertRate}%（<b>−3.3pt</b>；本期 <b>10.26—11.01，7 天</b> 对比上一期 <b>10.19—10.25，7 天</b>，<b>同为 7 天、可直接比总量</b>）—— <b>量升质降</b>，每转 1 人所需对接由 6.1 升到 <b>7.7</b>。⚠ <b>菲菲本周仍未填报</b>（分表止于 10.18），按契约记 null、不按 0 降榜。9 月累计（30 天）376 条 / 69 人（18.4%）可作基线。</p></article><article class="dc-risk purple"><label>数据可用性</label><strong>5 组表头空白</strong><p>汇报表五部门本周表头整行空白，护理周报另缺 1 份；趋势可用，但暂不能支持精确绩效排名或奖金结算。</p></article></div><div class="dc-detail-grid">
  <details class="dc-item" open><summary><span class="dc-no">1</span>10 月收官 262.18 万、超额 2.18 万；但本周靠单日高点撑住</summary><p>完成率<b>${amountRate}%</b>${(parseFloat(amountRate)>=parseFloat(timeRate)?'高于':'低于')}时间进度${timeRate}%，<b>领先 ${Math.abs(parseFloat(lagPt)).toFixed(1)}pt</b>。本期（10.26—11.01，已录 6 天）营收 <b>48.83 万</b>、日均 <b>8.14 万</b>，较上期同 6 天（10.19—10.24）<b>43.53 万</b>上升 <b>12.2%</b>。但 <b>10.31 单日 16.69 万＝全周 34.2%</b>（门诊 13.25 万、101 人次），其余 5 天日均只有 <b>6.43 万</b>——收官日的单点贡献盖住了周内平淡。10 月已收官，不再做月末推演；新一周要看能否在没有单日高点的情况下站上 7 万。</p></details>
  <details class="dc-item" open><summary><span class="dc-no">2</span>回访量升 69%、到院率反降 19pt：放量集中在一天</summary><p>客服回访 <b>${SEC.svcCallback}</b> 条、到院 <b>${SEC.svcArrived}</b> 人（到院率 <b>${SEC.svcRate}%</b>）；上一期（10.19—10.25，同为 7 天）29 条 / 到院 12 人（41.4%）。<b>两段同为完整 7 天，可直接比</b>：回访 <b>+69.0%</b>（日均 7.0 vs 4.1）、到院 <b>−8.3%</b>、<b>到院率 −19.0pt</b>。逐日回访 <b>4 / 20 / 7 / 5 / 5 / 6 / 2</b>，10.27 单日 20 条占 <b>40.8%</b>，其余 6 天日均 4.8 条——<b>放量集中在一天，不是稳定触达</b>。同期主动服务 25 条（覆盖 6 天）、日工作量 3,858 分（27 人日），上期同 7 天 25 条 / 3,149 分（日均 +22.5%）。后续仍须追踪<b>挂号—检查—治疗—入院—实际收入</b>。</p></details>
  <details class="dc-item"><summary><span class="dc-no">3</span>营销组「量升质降」：多接 6 条，少转 2 人</summary><p>管家台账本期（<b>10.26—11.01，7 天</b>）对接 ${SEC.mktDeals} 条、转住院 ${SEC.mktHosp} 人，转住院率 ${SEC.mktConvertRate}%；上一期（10.19—10.25，7 天）${SEC.mktDealsPrev} 条 / ${SEC.mktHospPrev} 人 / ${SEC.mktConvertPrev}%。两段<b>同为 7 天</b>：对接 <b>+7.0%</b>、转住院 <b>−2 人（−14.3%）</b>、率值 <b>−3.3pt</b> —— <b>多接 6 次、少转 2 人</b>，每转 1 人所需对接由 6.1 升到 <b>7.7</b>，前端在放量、转化在变薄。逐日 <b>11 / 4 / 6 / 6 / 3 / 35 / 27</b>：10.31—11.01 两天 <b>62 条＝67.4%</b>，周末集中录入的特征比上一期更重。逐人：朱婧 <b>33</b> · 国威 <b>25</b> · 金林 <b>17</b> · 利娟 <b>17</b>，合计 92。⚠ <b>菲菲整周未填报</b>（分表最后一行 10.18）——记 null、不进榜、不按 0 降榜。9 月累计（30 天）376 条 / 69 人（18.4%）可作基线。</p></details>
  <details class="dc-item"><summary><span class="dc-no">4</span>心理咨询组接触、咨询双降，降幅集中在住院端</summary><p>本期（<b>10.26—11.01，7 天</b>）患者接触 <b>36</b> 人次（上期同 7 天 65，<b>−44.6%</b>）、咨询工作量 <b>24</b> 人次（39，<b>−38.5%</b>）；结构上住院咨询 25→<b>11</b>（−56.0%）、门诊咨询 11→<b>13</b>（+18.2%）、家庭咨询 3→<b>0</b>、首接 9→<b>5</b>、情绪 31→<b>20</b>；<b>17 条日报、7 人填报</b>、家长访谈 20 人次（上期 24）、团体 2 场 / 12 人（上期 2 场 / 11 人）、绑定 10 行 / 10 人。⚠ 数据质量：3 条日报日期误录为 <b>2027</b>（10.27 王沛然、10.28 李凌钰、10.30 李凌钰），已按 2026 计入并单独标注；<b>若 10.28 李凌钰住院 2 不计，咨询会由 24 变 22</b>。降幅主要在住院端，与本周入院 8 人（−38.5%）同向。</p></details>
  <details class="dc-item" open><summary><span class="dc-no">5</span>医生组换口径：结账 21.45 万，物理治疗占 60.1%</summary><p>《特别行动小组汇报表》医生组本周<b>表头四项与上一周逐项同值，判定未滚动</b>，按契约整表不引用；本周改用《出院结帐明细表》（<b>10.26—11.01，7 天</b>）：出院 <b>10 人</b>、结算收入 <b>${SEC.docRev} 万</b>、物理治疗 <b>${SEC.docPhysio} 万（60.1%）</b>、心理 <b>0.92 万（4.3%）</b>、床位费 3.64 万（17.0%）；入院 <b>13 人</b>、在院 <b>${SEC.docCabRev} 人</b>（10.31 时点）、人均住院日 <b>17.5 天</b>、床日收入 <b>1,225 元</b>。逐人结算：王建 <b>8.30 万</b>（出 3）· 王建宁 3.86 万（出 1）· 曾凯 3.10 万（出 2）· 杜宁 2.95 万（出 2）· 康言 1.91 万（出 1）· 邓霏 1.33 万（出 1）· 傅睿文 0 万（出 0、在管 3）。⚠ 该口径按<b>出院日</b>归集、只含住院自费，与营收日报的 48.83 万（按<b>进账日</b>、含门诊）<b>不同源、不可相减</b>；上一期无同源对照，<b>环比不可计算</b>。</p></details>
  <details class="dc-item"><summary><span class="dc-no">6</span>护理组本周未交：六项治疗与考核表均无新数</summary><p>护理部周报本期（<b>10.26—11.01</b>）<b>尚未提交</b>，六项物理治疗应做 / 实做、电休克人次、工娱场次<b>全部记 null</b>；源表最新仍为 10.18—10.24（应做 <b>652</b> / 实做 <b>605</b> / 完成率 <b>92.8%</b>，电休克 11 人次），<b>仅作存档、不参与本期任何计算</b>。上一版工作量完成率 57.1% 同样不得当本期用——把「没交表」说成「水平掉了」是误判。四项补齐后才能算治疗强度与绩效：① 工作量与质控逐日（17 人 × 7 天）；② 六项治疗应做 / 实做逐日；③ 电休克人次；④ 工娱场次。</p></details>
  <details class="dc-item"><summary><span class="dc-no">7</span>业务集中在少数人员和日期</summary><p>营收 <b>34.2%</b> 集中在 10.31 单日；客服回访 40.8% 集中在 10.27、到院 11 人全部来自蒋雨；管家对接 <b>67.4%</b> 压在 10.31—11.01 两天；心理 17 条日报里蔡宜蓉一人 5 条、贡献咨询 <b>14 人次（58.3%）</b>。按总量排名容易奖励资源集中，而非效率与质量。</p></details>
  <details class="dc-item"><summary><span class="dc-no">8</span>数据口径不统一是最大管理障碍</summary><p>仍存在客服回访 <b>${SEC.svcCallback}</b> 条（本期 10.26—11.01，到院 ${SEC.svcArrived} 人 ${SEC.svcRate}%；上期同 7 天 29 条 / 12 人 / 41.4%）、管家对接 <b>${SEC.mktDeals}/${SEC.mktDealsPrev}</b>（同 7 天；⚠ 菲菲仍未填报，92 条是 4 人产出、86 条是 5 人产出）、心理接触 <b>36/65</b>（V4 逐条；汇报表表头停在 9.21 旧值已停用）、<b>营销中心表头三项本周空白</b>（本周入院 / 门诊 / 总收入，记 null 不顶替）、医生组<b>本周改出院结账口径</b>（21.45 万，与营收日报 48.83 万不同源）、<b>护理周报本周未交</b>。客服台账与线上表、营销汇总与逐条等差异仍待统一；护理组排名表为源表考核周口径，与自然周不可混比。</p></details><details class="dc-item"><summary><span class="dc-no">9</span>医生组本周口径：汇报表未滚动，改用出院结账</summary><p>本周（<b>10.26—11.01，7 天</b>）《特别行动小组汇报表》医生组表头四项（总收入 / 入院 / 门诊 / 物理治疗）<b>与上一周逐项同值</b>，判定未滚动，按契约<b>整表不引用</b>；本周改用《出院结帐明细表》：出院 <b>10 人</b>、结算 <b>21.45 万</b>、物理 <b>12.89 万</b>、心理 <b>0.92 万</b>；入院 <b>13 人</b>（科主任正文）、在院 <b>36 人</b>（10.31 时点）、人均住院日 17.5 天。营收台账本周 6 天 <b>48.83 万</b>，与结账 21.45 万<b>口径不同</b>（含门诊、按进账日 vs 按出院日），<b>不可相减</b>，也不做「差额＝漏收」的推断。两套数已在页面并列展示，取用看问题：看现金流用营收日报，看科室产出与费用结构用出院结账。</p></details></div><p class="dc-note"><b>管理结论：</b>优先修复患者级跨部门追踪和“医嘱—排程—执行—计费—退费”闭环；绩效排名只作月内动态试算，待口径冲突、缺失和归因完成后再在月末锁定。</p></section>`;
'''
src = src[:i] + BODY + src[j:]

io.open(P, 'w', encoding='utf-8').write(src)
print('OK business-analysis.js', len(src))
