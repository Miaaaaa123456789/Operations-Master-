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
    nurseShould: 1278, nurseDone: 1177, nurseMiss: 101, nurseRate: '92.1', nurseDrop: '25.4',
    nurseWeek: '9.20—9.26',
    svcCallback: 37, svcArrived: 11, svcRate: '29.7', svcRatePrev: '50.6',
    mktContacts: 80, mktAdmit: 17, mktRate: '21.2', mktRatePrev: '12.4',
    /* 管家/营销组（业主 2026-10-19 微信提供《10.12-10.18心理管家本周有效客户对接表.xlsx》）：
       本周 10.12—10.18（7 天）80 条 / 转住院 17 人（21.2%），逐人 利娟 20 / 金林 18 / 朱婧 17 / 国威 13 / 菲菲 12；
       上一自然周 10.05—10.11（7 天）89 条 / 11 人（12.4%）；再上一周 9.28—10.4（7 天）60 条 / 16 人（⚠ 菲菲、国威未填报，分母仅 3 人）；
       9 月累计（30 天）376 条 / 69 人（18.4%）。三周同为 7 天，可直接比总量。
       ⚠ 源表 I 列另有「权重」（合计 16.0，金林 5.3 / 朱婧 4 / 利娟 3 / 国威 2.7 / 菲菲 1），与条数排名不同序，
         源表未说明算法，本站只呈现、不据此发钱。
       ⚠ 营销中心表头（本周入院/门诊/总收入）本周整行空白，记 null、不拿旧值顶替——这与心理组「停在 9.21 的旧值」是两种不同的缺项。 */
    mktDeals: 80, mktDealsPrev: 89, mktHosp: 17, mktHospPrev: 11,
    mktConvertRate: '21.2', mktConvertPrev: '12.4',
    mktMonthDeals: 376, mktMonthHosp: 69, mktMonthRate: '18.4',
    inHouse: 32, inHousePrev: 27,
    /* 医生组本期（9.28—10.7）出院结帐明细口径 —— 业主 2026-10-09 提供
       ⚠ 仅「已出院结帐」金额，不含门诊与在院未结算；对照期＝上一期同长 10 天（9.14—9.23） */
    docDis: 25, docDisPrev: 18, docTotal: '36.72', docTotalPrev: '29.40',
    docGrowth: '+24.9', docCaseGrowth: '+38.9',
    docPerCase: '1.47', docPerCasePrev: '1.63', docPerCaseDelta: '−10.0',
    docCab: 30, docCabPrev: 35, docCabRev: 32
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

    var analysisHTML=`<section class="decision-core" id="decisionCore"><header class="dc-head"><div><h2>经营问题总览</h2><p>当前不是单一部门表现不好，而是“营收速度不足、转化链条断点、服务兑现流失、数据口径混乱”同时存在。月度营收进度只是最终表现，根本问题是跨部门转化链没有闭合。</p></div><span class="dc-scope">本期 ${_periodLab} · 数据截至 ${lastShort}（营收 ${lastShort}）</span></header><div class="dc-system"><div class="dc-chain"><div class="dc-node"><i>前端</i><b>触达增加</b><span>客服回访${SEC.svcCallback}条、到院${SEC.svcArrived}人（${SEC.svcRate}%），到院率连升两期但回访量降</span></div><div class="dc-node"><i>转化</i><b>有效入院不足</b><span>营销接触${SEC.mktContacts}人、入院${SEC.mktAdmit}人（营收日报口径）；管家台账本周 89 条、转住院 11 人（12.4%）</span></div><div class="dc-node"><i>服务</i><b>承接与兑现流失</b><span>心理业务回落，护理存在${SEC.nurseMiss}人次应做未做</span></div><div class="dc-node"><i>结果</i><b>营收速度不足</b><span>营收日报日均${mtdAvgWan}万（${lastShort} 止），${monthClosed?`全月收官 · 缺口 ${remainWan} 万`:`达标需${needDailyWan}万`}</span></div></div></div><div class="dc-risks"><article class="dc-risk red"><label>月目标风险</label><strong>${(parseFloat(lagPt)>=0?'落后 ':'领先 ')}${Math.abs(parseFloat(lagPt)).toFixed(1)}pt</strong><p>累计${totalWan}万（${BA_DOT}—${lastShort}），${monthClosed?`<b>${BA_LAB_SP}已收官</b>，缺口 <b>${remainWan} 万</b>，月度目标未达成`:`剩余${remainDays}天还需${remainWan}万，日均缺口${gapDailyWan}万`}。</p></article><article class="dc-risk orange"><label>前端转化</label><strong>到院率 ${SEC.svcRate}%</strong><p>本期（10.05—10.11）回访 ${SEC.svcCallback} 条、到院 ${SEC.svcArrived} 人；<b>到院率由上一期（9.28—10.04）${SEC.svcRatePrev}% 升到本期 ${SEC.svcRate}%，+12.6 个百分点</b>。回访量 86 → 74 条（−14.0%），属「量降质升」（连续第二周）；<b>温诗怡 0.0% → 66.7%</b> 改善最大，张欣雨 23.3% → 16.7% 是唯一回落。</p></article><article class="dc-risk blue"><label>营销转化</label><strong>${SEC.mktDealsPrev}条 → ${SEC.mktDeals}条</strong><p>管家对接 ${SEC.mktDealsPrev}→${SEC.mktDeals} 条（<b>−10.1%</b>）、转住院 ${SEC.mktHospPrev}→${SEC.mktHosp} 人（<b>+54.5%</b>）、率值 ${SEC.mktConvertPrev}%→${SEC.mktConvertRate}%（本周 <b>10.12—10.18，7 天</b> 对比上一自然周 <b>10.05—10.11，7 天</b>，<b>同为 7 天、可直接比总量</b>）—— <b>量降质升</b>。⚠ <b>上期菲菲只有 2 条</b>（本周 12 条），上期基数偏低是本轮率值跳升的部分原因，<b>需连续 3 周同向才能判定能力提升</b>；9 月累计（30 天）376 条 / 69 人（18.4%）可作基线。</p></article><article class="dc-risk purple"><label>数据可用性</label><strong>5组口径冲突</strong><p>趋势可用，但暂不能支持精确绩效排名或奖金结算。</p></article></div><div class="dc-detail-grid">
  <details class="dc-item" open><summary><span class="dc-no">1</span>月度营收节奏达标、但依赖单日高点</summary><p>完成率<b>${amountRate}%</b>${(parseFloat(amountRate)>=parseFloat(timeRate)?'高于':'低于')}时间进度${timeRate}%。本期日均<b>${weekAvgWan} 万</b>，较上一期同期（${pcLabel}，同为 ${pcDays} 天）的 <b>${pcAvgWan} 万</b>${growthTxt}；按当前节奏推演，月末约 ${forecastWan} 万：${(parseFloat(forecastGapWan)>0)?('仍差约 '+forecastGapWan+' 万，必须明确新增收入来源。'):('已可覆盖 260 万目标、超出 '+Math.abs(parseFloat(forecastWan)-parseFloat(txt(f.goalWan,260))).toFixed(2)+' 万；但仍需盯住单日高点依赖与初诊补充。')}</p></details>
  <details class="dc-item" open><summary><span class="dc-no">2</span>客服到院率连升两期，但主动服务量降待确认</summary><p>客服回访 ${SEC.svcCallback} 条、到院 ${SEC.svcArrived} 人（到院率 <b>${SEC.svcRate}%</b>）；上一期（9.28—10.04，同为 7 天）86 条 / 到院 31 人（36.0%）。<b>两段同为完整 7 天，可直接比</b>：回访 <b>−14.0%</b>、到院 <b>+16.1%</b>、<b>到院率 +12.6 pt</b>。同时导诊主动服务由 33 条降到 <b>23 条</b>（上一期仅覆盖 5 天、日均降 30.3%），<b>但回访台账同日补录的先例说明「显示无记录」不等于「没做」，建议先核实 10.3 / 10.4 再定论</b>。后续仍须追踪<b>挂号—检查—治疗—入院—实际收入</b>。</p></details>
  <details class="dc-item"><summary><span class="dc-no">3</span>营销组「量降质升」：对接少 9 条，转住院多 6 人</summary><p>管家台账本周（<b>10.12—10.18，7 天</b>）对接 ${SEC.mktDeals} 条、转住院 ${SEC.mktHosp} 人，转住院率 ${SEC.mktConvertRate}%；上一自然周（10.05—10.11，7 天）${SEC.mktDealsPrev} 条 / ${SEC.mktHospPrev} 人 / ${SEC.mktConvertPrev}%。两段<b>同为 7 天</b>：对接 <b>−10.1%</b>、转住院 <b>+54.5%</b>、率值 <b>+8.8pt</b> —— <b>少做 9 次对接、多转 6 个住院</b>，是本周最值得肯定的一条。结构：复诊 51 · 初诊 28 · 检查 59 · 物理 21 · 心理 20。⚠ <b>上期菲菲只有 2 条</b>（本周已回到 12 条），上期基数偏低是本轮率值跳升的部分原因，<b>需连续 3 周同向才能判定能力提升</b>；个人样本 12—20 条，<b>率值只作趋势参考</b>。9 月累计（30 天）376 条 / 69 人（18.4%），五人全部有量。⚠ 源表另有「权重」列（合计 16.0，金林 5.3 最高），与条数排名不同序，本站只呈现、不当绩效依据。</p></details>
  <details class="dc-item"><summary><span class="dc-no">4</span>心理咨询组接触升三成、咨询量基本持平</summary><p>本期（<b>10.12—10.18，7 天</b>）患者接触 <b>84</b> 人次（上期 10.05—10.11 为 64，<b>+31.3%</b>）、咨询工作量 <b>46</b> 人次（49，<b>−6.1%</b>）；结构上住院咨询 26→<b>25</b>（−3.8%）、门诊咨询 23→<b>19</b>（−17.4%）、家庭咨询 0→<b>2</b>，<b>23 条日报、5 人填报</b>、家长访谈 37 人次、团体 3 场 / 17 人。仍需核验：① 汇报表心理组表头停在 9.21 旧值（40 人 / 4 场 / 19,002 元），已停用、改用 V4；② 5 人日报完整率 0%—57%（赵芳、王沛然 0%），周表汇总全部「有待补」；③ 苏欣然管床 2 人但不在 5 人名册、不填日报；④ 赵芳 10-18 日报落在简报表末尾第 1005 行，周表公式未覆盖（差 1 天填报 / 1 天查房 / 1 次门诊）。</p></details>
  <details class="dc-item"><summary><span class="dc-no">5</span>住院规模没有形成增长</summary><p>上一期完整（9.21—10.4，14 天）入院 38 人、出院 26 人，净增 12 人；本期（10.5—10.18，进行中 · 已录 10 天）入院 18 人、出院 25 人，<b>净减 7 人</b>，10.14 日终在院 <b>32 人</b>。住院端进出基本平衡、患者池未扩张，难以单独承担剩余营收缺口；医生表还存在「在管 35 人」（9.27）与「在院 32 人」（10.14）的口径差异及入院日期缺失。<b>本期出院结帐明细（9.28—10.7）：25 人、个人总业绩 ${SEC.docTotal} 万</b>，较上一期同长 10 天（9.14—9.23）${SEC.docDisPrev} 人 / ${SEC.docTotalPrev} 万 <b>+24.9%</b>，但<b>人均费用 ${SEC.docPerCasePrev} → ${SEC.docPerCase} 万/人次（${SEC.docPerCaseDelta}%）</b>——出院人数涨 ${SEC.docCaseGrowth}%、金额只涨 ${SEC.docGrowth}%，量增额缓。</p></details>
  <details class="dc-item"><summary><span class="dc-no">6</span>护理与物理治疗存在兑现损失</summary><p>应执行${SEC.nurseShould}人次、完成${SEC.nurseDone}人次，仍有<b>${SEC.nurseMiss}人次未执行</b>；治疗应做量较参考期上升约${SEC.nurseDrop}%。当前缺少改期、替代项目、再次沟通、计费与退费的完整闭环。</p></details>
  <details class="dc-item"><summary><span class="dc-no">7</span>业务集中在少数人员和日期</summary><p>客服单人负担上升、在院患者集中于少数管床医生、心理记录集中于少数人员和单日、营收依赖周末和高收入日。按总量排名容易奖励资源集中，而非效率与质量。</p></details>
  <details class="dc-item"><summary><span class="dc-no">8</span>数据口径不统一是最大管理障碍</summary><p>仍存在客服回访 <b>${SEC.svcCallback}</b> 条（本周 10.12—10.18，到院 ${SEC.svcArrived} 人 ${SEC.svcRate}%；上期同 7 天 79 条 / 40 人 / 50.6%）、管家对接 <b>${SEC.mktDeals}/${SEC.mktDealsPrev}</b>（本周 10.12—10.18 对上一自然周 10.05—10.11，同为 7 天；⚠ 上期菲菲仅 2 条、基数偏低）、心理接触 <b>84/64</b>（V4 逐条；两期口径已统一为「首接＋情绪＋住院」；汇报表表头停在 9.21 旧值已停用）、<b>营销中心表头三项本周整行空白</b>（本周入院 / 门诊 / 总收入，记 null 不顶替）、医生在院 <b>${SEC.inHouse} 人</b>（营收日报 ${lastShort}）对医生表在管 35 人（9.27）。客服台账与线上表、营销汇总与逐条等差异仍待统一。护理组排名表为源表考核周口径，与自然周不可混比。</p></details><details class="dc-item"><summary><span class="dc-no">9</span>医生组本期业绩回升，但集中在两人、人均产出下滑</summary><p>新增《出院结帐明细表》口径：本期（9.28—10.7，10 天）已出院结帐 <b>${SEC.docDis} 人</b>、个人总业绩 <b>${SEC.docTotal} 万</b>；上一期同长 10 天（9.14—9.23）${SEC.docDisPrev} 人 / ${SEC.docTotalPrev} 万，<b>总业绩 ${SEC.docGrowth}%、出院人次 ${SEC.docCaseGrowth}%</b>。但 <b>人均费用 ${SEC.docPerCasePrev} 万降到 ${SEC.docPerCase} 万/人次（${SEC.docPerCaseDelta}%）</b>——量增额缓。<b>王建宁 11.96 万 ＋ 曾凯 10.33 万合计占 60.7%</b>，集中度高；王建宁出院 <b>7 人次</b>最多、在管仅 5 人，曾凯物理治疗 <b>6.80 万</b>全组第 1。下降的是 <b>康言（−55.8%）与赵郁莹（−52.0%）</b>：赵郁莹 9.27 在管 7 人已<b>清到 0 人</b>、本期仅出院 1 人次，<b>岗位与管床安排必须确认</b>。结构上 <b>物理治疗 21.24 万 ＋ 床位费 6.93 万 ＝ 76.7%</b>，仍靠治疗与床日；心理治疗合并 1.41 万（咨询 1.26 ＋ 治疗 0.15），量级很小。⚠ 「在管 / 在院」三种口径并存（本表在院清单 <b>${SEC.docCab} 人</b> / 9.27 台账 <b>${SEC.docCabPrev} 人</b> / 营收日报 <b>${SEC.docCabRev} 人</b>），<b>不可相加、不可互相替代</b>；本表无质量与及时性数据，<b>只能作业务量参考，不作绩效排名</b>。</p></details></div><p class="dc-note"><b>管理结论：</b>优先修复患者级跨部门追踪和“医嘱—排程—执行—计费—退费”闭环；绩效排名只作月内动态试算，待口径冲突、缺失和归因完成后再在月末锁定。</p></section>`;
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
    var k=shell.querySelector('.mkt-kpis');if(k)k.innerHTML=`<article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">☎</i>客服随访</div><strong>${SEC.svcCallback}条</strong><span>本周 10.12—10.18 · 到院率 ${SEC.svcRate}%</span></article><article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">◎</i>标记到院</div><strong>${SEC.svcArrived}人</strong><span>到院率 ${SEC.svcRate}%</span></article><article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">♧</i>管家对接</div><strong>${SEC.mktContacts}条</strong><span>本周 10.12—10.18 · 较上期 −10.1%</span></article><article class="mkt-kpi green"><div class="mkt-kpi-head"><i class="mkt-ico">↗</i>管家转住院</div><strong>${SEC.mktAdmit}人</strong><span>较上期 +54.5%（11 → 17 人）</span></article><article class="mkt-kpi purple"><div class="mkt-kpi-head"><i class="mkt-ico">％</i>营销转化</div><strong>${SEC.mktConvertRate}%</strong><span>小样本，不判定改善</span></article><article class="mkt-kpi"><div class="mkt-kpi-head"><i class="mkt-ico">▥</i>在院参考</div><strong>${SEC.inHouse}人</strong><span>${lastShort} 日终时点</span></article>`;
    var oldBanner = shell.querySelector('.mkt-analysis-banner'); if(oldBanner) oldBanner.remove();
    var oldGrid = shell.querySelector('.mkt-analysis-grid'); if(oldGrid) oldGrid.remove();
    if(k)k.insertAdjacentHTML('afterend',`<div class="mkt-analysis-banner"><i>!</i><div><b>月度营收已进入高风险区</b><span>累计${totalWan}万，完成${amountRate}%；剩余${remainDays}天需${remainWan}万。当前日均${mtdAvgWan}万，距离达标所需日均${needDailyWan}万仍差${gapDailyWan}万。</span></div></div><div class="mkt-analysis-grid"><article class="mkt-analysis-card"><label>客服触达</label><strong>触达与收入同向</strong><p>到院 ${SEC.svcArrived} 人、到院率 ${SEC.svcRatePrev}%→${SEC.svcRate}%（+12.6pt）；回访量 −14.0%，属量降质升（连续第二周）。</p></article><article class="mkt-analysis-card"><label>营销转化</label><strong>对接上量、转化回落</strong><p>对接 ${SEC.mktDealsPrev}→${SEC.mktContacts} 条（+48.3%）、转住院 ${SEC.mktHospPrev}→${SEC.mktAdmit} 人（−31.3%），率值 ${SEC.mktRatePrev}%→${SEC.mktRate}%。⚠ 上一周菲菲、国威两栏源表未填报，需补录后再定论。</p></article><article class="mkt-analysis-card"><label>服务承接</label><strong>心理组断点</strong><p>接触、家属工作和收入均明显回落。</p></article><article class="mkt-analysis-card"><label>治疗兑现</label><strong>${SEC.nurseMiss}人次未完成</strong><p>缺少改期、替代、计费与退费闭环。</p></article></div>`);
    var charts=shell.querySelectorAll('.mkt-card');for(const c of charts){if(c.querySelector('h2')?.textContent==='每日营业收入'||c.querySelector('h2')?.textContent==='营收速度缺口'){c.querySelector('.mkt-card-head').innerHTML='<div><h2>营收速度缺口</h2><p>日均万元 · 当前速度不足达标所需的一半</p></div><span class="mkt-badge">缺口 '+gapDailyWan+'万/日</span>';var bars=c.querySelector('.mkt-bars')||c.querySelector('.gap-bars');if(bars){var mtdNum=parseFloat(mtdAvgWan), needNum=parseFloat(needDailyWan);var prevAvg=parseFloat('8.69');var h1=needNum?Math.round(mtdNum/needNum*100):51;var h2=needNum?Math.round(prevAvg/needNum*100):42;bars.outerHTML='<div class="gap-bars"><div class="gap-bar"><em>'+mtdAvgWan+'万</em><i style="--h:'+h1+'%"></i><span>本周实际日均</span></div><div class="gap-bar"><em>'+prevAvg.toFixed(2)+'万</em><i style="--h:'+h2+'%"></i><span>上周日均</span></div><div class="gap-bar required"><em>'+needDailyWan+'万</em><i style="--h:100%"></i><span>达标所需日均</span></div></div>';}break}}
    var bottom=shell.querySelector('.mkt-bottom');
    if(bottom){
      var oldWarn=shell.querySelector('.mkt-data-warning'); if(oldWarn) oldWarn.remove();
      bottom.insertAdjacentHTML('afterend',`<section class="mkt-data-warning"><h2>数据口径风险：当前看板可发现趋势，但暂不能用于奖金结算</h2><p>客服回访存在<b>${SEC.svcCallback} / 86</b>（本期与上一期均为完整 7 天，符合同天数）、管家对接存在<b>${SEC.mktDeals} / ${SEC.mktDealsPrev}</b>（本周 10.12—10.18 对上一自然周 10.05—10.11，同为 7 天；⚠ 上期菲菲仅 2 条、基数偏低；源表另有「权重」列与条数不同序）、营销中心表头本周<b>整行空白</b>（入院 / 门诊 / 总收入记 null，不拿旧值顶替）、心理接触存在<b>84 / 64</b>（V4 逐条口径＝首接＋情绪＋住院；汇报表表头停在 9.21 旧值已停用）、医生在院存在<b>${SEC.inHouse} / 35</b>（营收日报 10.14 对医生工作量表 9.27「在管」口径）等差异；心理 / 客服 / 管家 / 医生组均已切到本周（10.12—10.18），护理组为本周 10.12—10.18（6 项治疗周报），营收日报真实数据已到 ${txt(f.labelDateShort,'10.14')}。所有排名需保留“数据期、来源、冲突状态”，月末核验后再锁定。</p></section>`);
    }
  }

  /* 首次渲染 + 数据更新后重绘（结构不变，只更新数字） */
  function mount(){
    var overview=document.getElementById('overview');
    var old=document.getElementById('decisionCore');
    if(old) old.remove();
    if(overview) overview.insertAdjacentHTML('afterend', buildHTML());
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
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
