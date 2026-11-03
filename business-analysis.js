(function(){
  /* ============================================================================
     经营问题总览（#decisionCore）
     ----------------------------------------------------------------------------
     ⚠ 改造纪律（业主 2026-09-28）：**外观与结构完全保留，只让数字活起来**。
     DOM 结构、class 名、文案排版一字不动；只把会变的数字换成变量插值。

     两类数据分开处理：
       · 营收类（累计 / 缺口 / 剩余天数 / 时间进度 / 落后 / 日均 / 达标日均 / 预测）
         → 一律取自 window.SEPTEMBER_REVENUE_DATA.facts()，随拖入数据实时变化。
       · 非营收类（护理 / 客服 / 营销 / 心理）
         → 收进下方 SEC 常量集中管理；它们来自别的数据源，改一处即可，模板结构不动。
     ========================================================================== */
  /* ---- 非营收口径（来自护理 / 客服 / 营销各源；集中在此便于单独更新） ---- */
  var SEC = {
    /* ⭐ 2026-11-02：护理考核表已交（10.26—11.01，7 天 / 17 行）——
       物理治疗应做 699 / 实做 630 / 未做 69、完成率 90.1%（上期 92.8%，−2.7pt）；
       电休克与工娱不在本次 Excel 内，仍记 null、不拿上期 11 人次顶替。 */
    nurseShould: 699, nurseDone: 630, nurseMiss: 69, nurseRate: '90.1', nurseDrop: '-2.7',
    nurseEct: null,
    nurseWeek: '10.26—11.01（已交 · 7 天）',
    /* 客服《回访台账》本期 10.26—11.01 已满 7 天：49 条 / 到院 11 人 / 22.4%；
       上期同 7 天（10.19—10.25）29 条 / 12 人 / 41.4%。 */
    svcCallback: 49, svcArrived: 11, svcRate: '22.4', svcRatePrev: '41.4',
    svcPrevCallback: 29, svcPrevArrived: 12, svcGuide: 25, svcWorkload: '3,858',
    mktContacts: 92, mktAdmit: 12, mktRate: '13.0', mktRatePrev: '16.3',
    /* 管家《患者有效对接表》本期 92 条 / 转住院 12 人（13.0%）；
       上期同 7 天 86 / 14（16.3%）；菲菲仍未填报（分表止于 10.18），记 null、不进榜。 */
    mktDeals: 92, mktDealsPrev: 86, mktHosp: 12, mktHospPrev: 14,
    mktConvertRate: '13.0', mktConvertPrev: '16.3',
    /* 9 月为当月定稿存档（页面 9 月档同源）：367 条 / 61 人 / 16.6%；
       按源表现值重算为 367/67，差在 9 月后补的住院标记，不覆盖存档 */
    mktMonthDeals: 367, mktMonthHosp: 61, mktMonthRate: '16.6',
    inHouse: 33, inHousePrev: 32,
    /* 医生组本期（10.26—11.01）改取出院结账口径（汇报表本周未滚动）：
       结算 21.45 万 / 物理 12.89 万 / 出院 10 / 入院 13 / 在院 36。
       上一期无同源对照 → 环比一律「不可计算」，不拿汇报表旧值硬凑。 */
    docRev: '21.45', docRevPrev: '—', docRevDelta: '不可计算',
    docPhysio: '12.89', docPhysioPrev: '—', docPhysioDelta: '不可计算',
    docAdmit: 13, docAdmitPrev: null, docAdmitDelta: '不可计算',
    docDis: 10, docDisPrev: null, docDisDelta: '不可计算',
    docOpd: null, docOpdPrev: null, docOpdDelta: '不可计算',
    docDetailAdmit: 13, docDetailDis: 10, docGapAdmit: 0, docGapDis: 0,
    docCabRev: 36
  };

  function F() {
    var d = window.SEPTEMBER_REVENUE_DATA;
    if (d && typeof d.facts === 'function') { try { return d.facts(); } catch (e) { } }
    return null;
  }
  function txt(v, dflt) { return (v == null || v === '' || (typeof v === 'number' && !isFinite(v))) ? dflt : v; }

  /* ⭐ 结算月标签（2026-10-06 主面板切 10 月）—— 别再写死「9月」 */
  var BA_MONTH=(window.SEPTEMBER_REVENUE_DATA&&window.SEPTEMBER_REVENUE_DATA.SETTLED_MONTH)||'2026-10';
  var BA_NUM=+BA_MONTH.slice(5,7), BA_LAB=BA_NUM+'月', BA_LAB_SP=BA_NUM+' 月', BA_DOT=BA_NUM+'.1';
  function buildHTML() {
    var f = F() || {};
    var lastShort = txt(f.labelDateShort, '10.14');            // 10.14
    var remainDays = txt(f.remainDays, 17);
    var totalWan = txt(f.totalWan, '123.55');
    var amountRate = (f.amountRate != null) ? f.amountRate.toFixed(1) : '47.5';
    var timeRate = (f.timeRate != null) ? f.timeRate.toFixed(1) : '45.2';
    var lagPt = (f.lagPt != null) ? f.lagPt.toFixed(1) : '-2.4';
    var remainWan = txt(f.remainWan, '136.45');
    var needDailyWan = txt(f.needDailyWan, '8.03');
    var mtdAvgWan = txt(f.mtdAvgWan, '8.82');
    var gapDailyWan = txt(f.gapDailyWan, '0.00');
    var forecastWan = txt(f.forecastWan, '273.57');
    var forecastGapWan = txt(f.forecastGapWan, '0.00');
    var weekAvgWan = txt(f.weekAvgWan, '8.60');
    var monthClosed = !!f.monthClosed;
    /* ⚠ 「上周同期区间 / 同期日均 / 环比增幅」三项原为硬编码 ——
       周窗口一滚就全错（天数、区间、日均、增幅都会变）。
       改为从 derive() 实时算。 */
    var _dv=(window.SEPTEMBER_REVENUE_DATA&&window.SEPTEMBER_REVENUE_DATA.derive)?window.SEPTEMBER_REVENUE_DATA.derive():null;
    var _pc=_dv&&_dv.previousComparable?_dv.previousComparable:null;
    var _cw=_dv&&_dv.currentWeek?_dv.currentWeek:null;
    var _periodLab=(_dv&&_dv.period&&_dv.period.label)?_dv.period.label:'';
    var pcDays=(_pc&&_pc.days)?_pc.days:'—';
    var pcAvgWan=(_pc&&_pc.days)?(_pc.total/_pc.days/10000).toFixed(2):'—';
    /* ⚠⚠ 同期区间**必须**直接用数据层给的 label。
       原先从 _dv.weeks 的「最后一个非本周周」反推 —— 本期改成两周窗口后，
       数组里未发生的周（10.26—10.31）会被取到，算出「上周同期 10.19—10.26」这种未来区间。 */
    var pcLabel=(_pc&&_pc.label)?_pc.label:'上一期同期';
    var _g=(_cw&&_pc&&_pc.total)?((_cw.total/_pc.total-1)*100):null;
    var growthTxt=(_g!=null)?('上升 <b>'+_g.toFixed(1)+'%</b>'):'环比待算';

    var goalWan = parseFloat(txt(f.goalWan, 260));
    var overWan = (parseFloat(totalWan) - goalWan).toFixed(2);
    var analysisHTML=`<section class="decision-core" id="decisionCore"><header class="dc-head"><div><h2>经营问题总览</h2><p>当前不是单一部门表现不好，而是“营收速度不足、转化链条断点、服务兑现流失、数据口径混乱”同时存在。月度营收进度只是最终表现，根本问题是跨部门转化链没有闭合。</p></div><span class="dc-scope">本期 ${_periodLab} · 数据截至 ${lastShort}（营收 ${lastShort}）</span></header><div class="dc-system"><div class="dc-chain"><div class="dc-node"><i>前端</i><b>触达增加</b><span>客服回访${SEC.svcCallback}条、到院${SEC.svcArrived}人（${SEC.svcRate}%），回访量回升但到院率腰斩</span></div><div class="dc-node"><i>转化</i><b>有效入院不足</b><span>营销接触${SEC.mktContacts} 条、转住院${SEC.mktAdmit} 人（管家对接口径）；每转 1 人需 <b>7.7</b> 条对接（上期 6.1）</span></div><div class="dc-node"><i>服务</i><b>承接与兑现流失</b><span>心理接触 36 人次、咨询 24 人次（环比 −44.6% / −38.5%）；护理六项完成率 90.1%（−2.7pt）</span></div><div class="dc-node"><i>结果</i><b>营收速度不足</b><span>营收日报日均${mtdAvgWan}万（${lastShort} 止），${monthClosed?`全月收官 · 超额 ${overWan} 万`:`达标需${needDailyWan}万`}</span></div></div></div><div class="dc-risks"><article class="dc-risk red"><label>月目标风险</label><strong>${(parseFloat(lagPt)>=0?'落后 ':'领先 ')}${Math.abs(parseFloat(lagPt)).toFixed(1)}pt</strong><p>累计${totalWan}万（${BA_DOT}—${lastShort}），${monthClosed?`<b>${BA_LAB_SP}已收官</b>，完成率 <b>${amountRate}%</b>、<b>超额 ${overWan} 万</b>，月度目标已达成`:`剩余${remainDays}天还需${remainWan}万，日均缺口${gapDailyWan}万`}。</p></article><article class="dc-risk orange"><label>前端转化</label><strong>到院率 ${SEC.svcRate}%</strong><p>本期（10.26—11.01，7 天）回访 ${SEC.svcCallback} 条、到院 ${SEC.svcArrived} 人；<b>到院率由上一期（10.19—10.25，同为 7 天）${SEC.svcRatePrev}% 降到本期 ${SEC.svcRate}%，−19.0 个百分点</b>。回访量 29 → <b>49 条（日均 7.0 vs 4.1，+69.0%）</b>、到院 12 → 11 人（−1 人），<b>量升质降</b>；<b>到院 11 人全部记在蒋雨名下</b>（回访 36 条），温诗怡回访 13 条、到院 0——到院率的分母只来自两人，样本小，暂不当趋势结论。</p></article><article class="dc-risk blue"><label>营销转化</label><strong>${SEC.mktDealsPrev}条 → ${SEC.mktDeals}条</strong><p>管家对接 ${SEC.mktDealsPrev}→${SEC.mktDeals} 条（<b>+7.0%</b>）、转住院 ${SEC.mktHospPrev}→${SEC.mktHosp} 人（<b>−14.3%</b>）、率值 ${SEC.mktConvertPrev}%→${SEC.mktConvertRate}%（<b>−3.3pt</b>；本期 <b>10.26—11.01，7 天</b> 对比上一期 <b>10.19—10.25，7 天</b>，<b>同为 7 天、可直接比总量</b>）—— <b>量升质降</b>，每转 1 人所需对接由 6.1 升到 <b>7.7</b>。⚠ <b>菲菲本周仍未填报</b>（分表止于 10.18），按契约记 null、不按 0 降榜。9 月定稿存档 367 条 / 61 人（16.6%）可作基线（源表现值重算 367/67，差在后补住院标记）。</p></article><article class="dc-risk purple"><label>数据可用性</label><strong>5 组表头空白</strong><p>汇报表五部门本周表头整行空白；趋势可用，但暂不能支持精确绩效排名或奖金结算。</p></article></div><div class="dc-detail-grid">
  <details class="dc-item" open><summary><span class="dc-no">1</span>10 月收官 262.18 万、超额 2.18 万；但本周靠单日高点撑住</summary><p>完成率<b>${amountRate}%</b>${(parseFloat(amountRate)>=parseFloat(timeRate)?'高于':'低于')}时间进度${timeRate}%，<b>领先 ${Math.abs(parseFloat(lagPt)).toFixed(1)}pt</b>。本期（10.26—11.01，已录 7 天）营收 <b>62.51 万</b>、日均 <b>8.93 万</b>，较上期同 7 天（10.19—10.25）<b>58.35 万</b>上升 <b>7.1%</b>。但 <b>10.31 单日 16.69 万＝全周 26.7%</b>（门诊 13.25 万、101 人次），其余 6 天日均 <b>7.64 万</b>——收官日的单点贡献盖住了周内平淡。10 月已收官，不再做月末推演；新一周要看能否在没有单日高点的情况下站上 7 万。</p></details>
  <details class="dc-item" open><summary><span class="dc-no">2</span>回访量升 69%、到院率反降 19pt：放量集中在一天</summary><p>客服回访 <b>${SEC.svcCallback}</b> 条、到院 <b>${SEC.svcArrived}</b> 人（到院率 <b>${SEC.svcRate}%</b>）；上一期（10.19—10.25，同为 7 天）29 条 / 到院 12 人（41.4%）。<b>两段同为完整 7 天，可直接比</b>：回访 <b>+69.0%</b>（日均 7.0 vs 4.1）、到院 <b>−8.3%</b>、<b>到院率 −19.0pt</b>。逐日回访 <b>4 / 20 / 7 / 5 / 5 / 6 / 2</b>，10.27 单日 20 条占 <b>40.8%</b>，其余 6 天日均 4.8 条——<b>放量集中在一天，不是稳定触达</b>。同期主动服务 25 条（覆盖 6 天）、日工作量 3,858 分（27 人日），上期同 7 天 25 条 / 3,149 分（日均 +22.5%）。后续仍须追踪<b>挂号—检查—治疗—入院—实际收入</b>。</p></details>
  <details class="dc-item"><summary><span class="dc-no">3</span>营销组「量升质降」：多接 6 条，少转 2 人</summary><p>管家台账本期（<b>10.26—11.01，7 天</b>）对接 ${SEC.mktDeals} 条、转住院 ${SEC.mktHosp} 人，转住院率 ${SEC.mktConvertRate}%；上一期（10.19—10.25，7 天）${SEC.mktDealsPrev} 条 / ${SEC.mktHospPrev} 人 / ${SEC.mktConvertPrev}%。两段<b>同为 7 天</b>：对接 <b>+7.0%</b>、转住院 <b>−2 人（−14.3%）</b>、率值 <b>−3.3pt</b> —— <b>多接 6 次、少转 2 人</b>，每转 1 人所需对接由 6.1 升到 <b>7.7</b>，前端在放量、转化在变薄。逐日 <b>11 / 4 / 6 / 6 / 3 / 35 / 27</b>：10.31—11.01 两天 <b>62 条＝67.4%</b>，周末集中录入的特征比上一期更重。逐人：朱婧 <b>33</b> · 国威 <b>25</b> · 金林 <b>17</b> · 利娟 <b>17</b>，合计 92。⚠ <b>菲菲整周未填报</b>（分表最后一行 10.18）——记 null、不进榜、不按 0 降榜。9 月定稿存档 367 条 / 61 人（16.6%）可作基线（源表现值重算 367/67，差在后补住院标记）。</p></details>
  <details class="dc-item"><summary><span class="dc-no">4</span>心理咨询组接触、咨询双降，降幅集中在住院端</summary><p>本期（<b>10.26—11.01，7 天</b>）患者接触 <b>36</b> 人次（上期同 7 天 65，<b>−44.6%</b>）、咨询工作量 <b>24</b> 人次（39，<b>−38.5%</b>）；结构上住院咨询 25→<b>11</b>（−56.0%）、门诊咨询 11→<b>13</b>（+18.2%）、家庭咨询 3→<b>0</b>、首接 9→<b>5</b>、情绪 31→<b>20</b>；<b>17 条日报、7 人填报</b>、家长访谈 20 人次（上期 24）、团体 2 场 / 12 人（上期 2 场 / 11 人）、绑定 10 行 / 10 人。⚠ 数据质量：3 条日报日期误录为 <b>2027</b>（10.27 王沛然、10.28 李凌钰、10.30 李凌钰），已按 2026 计入并单独标注；<b>若 10.28 李凌钰住院 2 不计，咨询会由 24 变 22</b>。降幅主要在住院端，与本周入院 13 人（−18.8%）同向。</p></details>
  <details class="dc-item" open><summary><span class="dc-no">5</span>医生组换口径：结账 21.45 万，物理治疗占 60.1%</summary><p>《特别行动小组汇报表》医生组本周<b>表头四项与上一周逐项同值，判定未滚动</b>，按契约整表不引用；本周改用《出院结帐明细表》（<b>10.26—11.01，7 天</b>）：出院 <b>10 人</b>、结算收入 <b>${SEC.docRev} 万</b>、物理治疗 <b>${SEC.docPhysio} 万（60.1%）</b>、心理 <b>0.92 万（4.3%）</b>、床位费 3.64 万（17.0%）；入院 <b>13 人</b>、在院 <b>${SEC.docCabRev} 人</b>（10.31 时点）、人均住院日 <b>17.5 天</b>、床日收入 <b>1,225 元</b>。逐人结算：王建 <b>8.30 万</b>（出 3）· 王建宁 3.86 万（出 1）· 曾凯 3.10 万（出 2）· 杜宁 2.95 万（出 2）· 康言 1.91 万（出 1）· 邓霏 1.33 万（出 1）· 谭喜文 0 万（出 0、在管 3）。⚠ 该口径按<b>出院日</b>归集、只含住院自费，与营收日报的 62.51 万（按<b>进账日</b>、含门诊）<b>不同源、不可相减</b>；上一期无同源对照，<b>环比不可计算</b>。</p></details>
  <details class="dc-item" open><summary><span class="dc-no">6</span>护理组已交：物理治疗 90.1%，短板在团体与失眠</summary><p>本期（<b>10.26—11.01，7 天</b>）物理治疗应做 <b>699</b> / 实做 <b>630</b> / 未做 <b>69</b> 人次，完成率 <b>90.1%</b>（上期 10.18—10.24：652 / 605 / 92.8%，<b>−2.7pt</b>；应做 +7.2%、实做 +4.1%）。<b>团体 71.1%（32/45）与失眠 72.2%（26/36）</b>是唯二低于 75% 的项目，两项未做 23 人次＝全部未做 33.3%；未做绝对量最大的是<b>经颅磁 17 人次</b>。逐日看，11.01 应做 116 最高、完成率 85.3% 最低；10.30 应做 95 最低、完成率 94.7% 最高。<b>两套排名并列、不合成</b>：完成率榜 14 人（沈琳 94.8% 第 1），工作量榜 16 人（杨新金 30.2 第 1）。⚠ <b>完成率仅填 40/112 格（35.7%）</b>：李永鑫、陈福建 7 天无完成率（不进效率榜，不按 0 计），赵林烦整行空。电休克与工娱场次不在本次 Excel 内，仍记 null、不拿存档顶替。</p></details>
  <details class="dc-item"><summary><span class="dc-no">7</span>业务集中在少数人员和日期</summary><p>营收 <b>48.6%</b> 集中在 10.31—11.01 两天（26.7% ＋ 21.9%）；客服回访 40.8% 集中在 10.27、到院 11 人全部来自蒋雨；管家对接 <b>67.4%</b> 压在 10.31—11.01 两天；心理 17 条日报里蔡宜蓉一人 5 条、贡献咨询 <b>14 人次（58.3%）</b>。按总量排名容易奖励资源集中，而非效率与质量。</p></details>
  <details class="dc-item"><summary><span class="dc-no">8</span>数据口径不统一是最大管理障碍</summary><p>仍存在客服回访 <b>${SEC.svcCallback}</b> 条（本期 10.26—11.01，到院 ${SEC.svcArrived} 人 ${SEC.svcRate}%；上期同 7 天 29 条 / 12 人 / 41.4%）、管家对接 <b>${SEC.mktDeals}/${SEC.mktDealsPrev}</b>（同 7 天；⚠ 菲菲两期均未填报，92 条与 86 条同为 4 人产出，可直接比）、心理接触 <b>36/65</b>（V4 逐条；汇报表表头停在 9.21 旧值已停用）、<b>营销中心表头三项本周空白</b>（本周入院 / 门诊 / 总收入，记 null 不顶替）、医生组<b>本周改出院结账口径</b>（21.45 万，与营收日报 62.51 万不同源）、<b>护理考核表本期已交（六项 90.1%）</b>。客服台账与线上表、营销汇总与逐条等差异仍待统一；护理组排名表为源表考核周口径，与自然周不可混比。</p></details><details class="dc-item"><summary><span class="dc-no">9</span>医生组本周口径：汇报表未滚动，改用出院结账</summary><p>本周（<b>10.26—11.01，7 天</b>）《特别行动小组汇报表》医生组表头四项（总收入 / 入院 / 门诊 / 物理治疗）<b>与上一周逐项同值</b>，判定未滚动，按契约<b>整表不引用</b>；本周改用《出院结帐明细表》：出院 <b>10 人</b>、结算 <b>21.45 万</b>、物理 <b>12.89 万</b>、心理 <b>0.92 万</b>；入院 <b>13 人</b>（科主任正文）、在院 <b>36 人</b>（11.01 时点）、人均住院日 17.5 天。营收台账本周 7 天 <b>62.51 万</b>，与结账 21.45 万<b>口径不同</b>（含门诊、按进账日 vs 按出院日），<b>不可相减</b>，也不做「差额＝漏收」的推断。两套数已在页面并列展示，取用看问题：看现金流用营收日报，看科室产出与费用结构用出院结账。</p></details></div><p class="dc-note"><b>管理结论：</b>优先修复患者级跨部门追踪和“医嘱—排程—执行—计费—退费”闭环；绩效排名只作月内动态试算，待口径冲突、缺失和归因完成后再在月末锁定。</p></section>`;
    return analysisHTML;
  }

  /* 覆盖营销面板里的营收数字（结构不动，只改数值） */
  function decorateShell() {
    var f = F() || {};
    var shell=document.querySelector('.mkt-v2');if(!shell)return;
    var lastShort = txt(f.labelDateShort, '10.14');
    var remainDays = txt(f.remainDays, 17);
    var totalWan = txt(f.totalWan, '123.55');
    var amountRate = (f.amountRate!=null)?f.amountRate.toFixed(1):'47.5';
    var remainWan = txt(f.remainWan, '136.45');
    var needDailyWan = txt(f.needDailyWan, '8.03');
    var mtdAvgWan = txt(f.mtdAvgWan, '8.82');
    var gapDailyWan = txt(f.gapDailyWan, '0.00');
    var weekVal = shell.querySelector('.mkt-amount');
    if(weekVal){
      var cw = f.currentWeek || null;
      /* ⚠ 兜底值原写死一个过期周额、日均与环比百分比，数据到 9.30 后全部过时。
         环比改为从 source.derive() 实时算，兜底值同步到当前口径。 */
      var _x=(window.SEPTEMBER_REVENUE_DATA&&window.SEPTEMBER_REVENUE_DATA.derive)?window.SEPTEMBER_REVENUE_DATA.derive():null;
      var _pv=_x&&_x.previousComparable?_x.previousComparable:null;
      var _cw=_x&&_x.currentWeek?_x.currentWeek:(cw||null);
      var _growth=(_cw&&_pv&&_pv.total)?((_cw.total/_pv.total-1)*100):null;
      var wkTotalWan = (f.weekAvgWan!=null && f.weekDays) ? (parseFloat(f.weekAvgWan)*f.weekDays).toFixed(2) : '85.98';
      weekVal.innerHTML='¥'+wkTotalWan+'<i>万</i>';
      var sub = shell.querySelector('.mkt-sub');
      if(sub) sub.textContent=(function(){try{var _d=window.SEPTEMBER_REVENUE_DATA;if(_d&&_d.derive){var _s=((_d.derive().currentWeek||{}).from)||'';if(_s)return (+_s.slice(5,7))+'.'+(+_s.slice(8))+'—';}}catch(e){}return BA_DOT+'—';})()+lastShort+' · 日均 ¥'+txt(f.weekAvgWan,'8.60')+'万'
        +(_growth!=null?(' · 较上周同期 '+(_growth>=0?'+':'')+_growth.toFixed(1)+'%（同为 '+((_cw&&_cw.days)||'—')+' 天）'):'');
    }
    var k=shell.querySelector('.mkt-kpis');if(k)k.innerHTML=`<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">☎</i>客服随访</div><strong>${SEC.svcCallback}条</strong><span>本周 10.19—10.25 · 到院率 ${SEC.svcRate}%</span></article><article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">◎</i>标记到院</div><strong>${SEC.svcArrived}人</strong><span>到院率 ${SEC.svcRate}%</span></article><article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">♧</i>管家对接</div><strong>${SEC.mktContacts}条</strong><span>本周 10.19—10.25 · 较上期 <b>+10.1%</b></span></article><article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">↗</i>管家转住院</div><strong>${SEC.mktAdmit}人</strong><span>较上期 −12.5%（16 → 14 人）</span></article><article class="mkt-kpi purple"><div class="mkt-kpi-head"><i class="mkt-ico">％</i>营销转化</div><strong>${SEC.mktConvertRate}%</strong><span>较上期 20.3%，<b>−4.2pt</b></span></article><article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">▥</i>在院参考</div><strong>${SEC.inHouse}人</strong><span>${lastShort} 日终时点</span></article>`;
    var oldBanner = shell.querySelector('.mkt-analysis-banner'); if(oldBanner) oldBanner.remove();
    var oldGrid = shell.querySelector('.mkt-analysis-grid'); if(oldGrid) oldGrid.remove();
    if(k)k.insertAdjacentHTML('afterend',`<div class="mkt-analysis-banner"><i>!</i><div><b>月度营收已进入高风险区</b><span>累计${totalWan}万，完成${amountRate}%；剩余${remainDays}天需${remainWan}万。当前日均${mtdAvgWan}万，距离达标所需日均${needDailyWan}万仍差${gapDailyWan}万。</span></div></div><div class="mkt-analysis-grid"><article class="mkt-analysis-card"><label>客服触达</label><strong>触达与收入同向</strong><p>到院 ${SEC.svcArrived} 人、到院率 ${SEC.svcRatePrev}%→${SEC.svcRate}%（+6.9pt）；回访量 −24.3%，量降质升。</p></article><article class="mkt-analysis-card"><label>营销转化</label><strong>对接上量、转化变薄</strong><p>对接 ${SEC.mktDealsPrev}→${SEC.mktContacts} 条（<b>+10.1%</b>）、转住院 ${SEC.mktHospPrev}→${SEC.mktAdmit} 人（<b>−12.5%</b>），率值 ${SEC.mktRatePrev}%→${SEC.mktRate}%（<b>−4.2pt</b>）。⚠ 本周<b>菲菲整周未填报</b>，环比混有缺口；每转 1 人所需对接由 4.9 升到 6.2。</p></article><article class="mkt-analysis-card"><label>服务承接</label><strong>心理组断点</strong><p>接触、家属工作和收入均明显回落。</p></article><article class="mkt-analysis-card"><label>治疗兑现</label><strong>${SEC.nurseMiss}人次未完成</strong><p>缺少改期、替代、计费与退费闭环。</p></article></div>`);
    var charts=shell.querySelectorAll('.mkt-card');for(const c of charts){if(c.querySelector('h2')?.textContent==='每日营业收入'||c.querySelector('h2')?.textContent==='营收速度缺口'){c.querySelector('.mkt-card-head').innerHTML='<div><h2>营收速度缺口</h2><p>日均万元 · 当前速度不足达标所需的一半</p></div><span class="mkt-badge">缺口 '+gapDailyWan+'万/日</span>';var bars=c.querySelector('.mkt-bars')||c.querySelector('.gap-bars');if(bars){var mtdNum=parseFloat(mtdAvgWan), needNum=parseFloat(needDailyWan);var prevAvg=parseFloat('8.69');var h1=needNum?Math.round(mtdNum/needNum*100):51;var h2=needNum?Math.round(prevAvg/needNum*100):42;bars.outerHTML='<div class="gap-bars"><div class="gap-bar"><em>'+mtdAvgWan+'万</em><i style="--h:'+h1+'%"></i><span>本周实际日均</span></div><div class="gap-bar"><em>'+prevAvg.toFixed(2)+'万</em><i style="--h:'+h2+'%"></i><span>上周日均</span></div><div class="gap-bar required"><em>'+needDailyWan+'万</em><i style="--h:100%"></i><span>达标所需日均</span></div></div>';}break}}
    var bottom=shell.querySelector('.mkt-bottom');
    if(bottom){
      var oldWarn=shell.querySelector('.mkt-data-warning'); if(oldWarn) oldWarn.remove();
      bottom.insertAdjacentHTML('afterend',`<section class="mkt-data-warning"><h2>数据口径风险：当前看板可发现趋势，但暂不能用于奖金结算</h2><p>客服回访存在<b>${SEC.svcCallback} / ${SEC.svcPrevCallback}</b>（本期与上一期均为完整 7 天，符合同天数；⚠ 上一版误把 10.05—10.11 的 79 条当成上一期，已更正为 37 条）、管家对接存在<b>${SEC.mktDeals} / ${SEC.mktDealsPrev}</b>（本周 10.19—10.25 对上一自然周 10.12—10.18，同为 7 天；⚠ 本周菲菲整周未填报，应剔除后重算；总排名按业主汇总表「权重」列，金林 / 朱婧 并列 4.0、利娟 / 国威 并列 3.0）、营销中心表头本周<b>整行空白</b>（入院 / 门诊 / 总收入记 null，不拿旧值顶替）、心理接触存在<b>84 / 64</b>（V4 逐条口径＝首接＋情绪＋住院；汇报表表头停在 9.21 旧值已停用）、医生组表头 <b>入院 ${SEC.docAdmit} / 门诊 ${SEC.docOpd} / 总收入 ${SEC.docRev} 万</b> 对个人正文加总 <b>${SEC.docDetailAdmit} 入 / ${SEC.docDetailDis} 出</b>（差 ${SEC.docGapAdmit} / ${SEC.docGapDis}，赵郁莹空白）等差异；心理 / 客服 / 管家 / 医生组均已切到本周（10.19—10.25），护理组为本周 10.19—10.25（6 项治疗周报），营收日报真实数据已到 ${txt(f.labelDateShort,'10.14')}。所有排名需保留“数据期、来源、冲突状态”，月末核验后再锁定。</p></section>`);
    }
  }

  /* == LAYOUT-2026-10-26 == */
  /* 业主 2026-10-26：经营问题总览挪到「员工排名」原来的位置。
     主看板不再单独放员工排名（排名只进各部门专属抽屉），
     所以本块紧跟在 10 月经营面板 #monthCommandCenter 之后。
     ⚠ 月面板由 month-dashboard.js 在后续脚本里挂载，首次 mount 时锚点可能还不存在，
       故 boot 里再补一次 load / 延迟校正，幂等。 */
  function placeDecisionCore(){
    var dc=document.getElementById('decisionCore');
    if(!dc||!dc.parentNode) return;
    var anchor=document.getElementById('monthCommandCenter');
    if(!anchor||!anchor.parentNode||anchor.parentNode!==dc.parentNode) return;
    if(anchor.nextElementSibling!==dc) anchor.parentNode.insertBefore(dc,anchor.nextElementSibling);
  }

  /* 首次渲染 + 数据更新后重绘（结构不变，只更新数字） */
  function mount(){
    var overview=document.getElementById('overview');
    var old=document.getElementById('decisionCore');
    if(old) old.remove();
    if(overview) overview.insertAdjacentHTML('afterend', buildHTML());
    placeDecisionCore();
    var rank=document.getElementById('rankGovernance'),workspace=document.querySelector('.workspace');
    if(rank&&workspace&&rank.parentNode!==workspace)workspace.appendChild(rank);
    decorateShell();
  }
  function boot(){
    var rank=document.getElementById('rankGovernance'),workspace=document.querySelector('.workspace');if(rank&&workspace)workspace.appendChild(rank);
    mount();
    /* 数据更新后重绘本区块（结构不变，只刷新数字）。
       'ops:core-refresh' 是 data-import.js 的 renderRevenue 在每次写入后派发的专用事件。 */
    ['ops:revenue-updated','september-revenue-updated','ops:core-refresh'].forEach(function(ev){
      window.addEventListener(ev,function(){ try{ mount(); }catch(e){} });
    });
  }
  window.addEventListener('load',function(){try{placeDecisionCore();}catch(e){}});
  setTimeout(function(){try{placeDecisionCore();}catch(e){}},300);
  setTimeout(function(){try{placeDecisionCore();}catch(e){}},900);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
