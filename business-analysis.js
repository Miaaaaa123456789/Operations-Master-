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
    /* ⭐ 2026-10-26：护理部六项物理治疗已报（业主 08:21 微信给出）→ 不再是 null。
       本期 10.19—10.25（7 天）应做 652 / 实做 605 / 未做 47 / 完成率 92.8%；
       上一期 10.12—10.18 为 656 / 613 / 93%（六项同口径，可直接比总量）。 */
    nurseShould: 652, nurseDone: 605, nurseMiss: 47, nurseRate: '92.8', nurseDrop: '0.6',
    /* 电休克：10.19—10.25 实做 11 人次，源表未给应做数 → 单列，不并入上面 652/605 的完成率 */
    nurseEct: 11,
    nurseWeek: '10.19—10.25（6 项已报）',
    /* ⭐ 2026-10-26 08:57 重抓《客服服务部》4 张表：回访台账已滚到 10.25（全 7 天）。
       本期 28 条 / 到院 11 人 / 39.3%；真上一期（10.12—10.18，7 天）37 条 / 12 人 / 32.4%。
       ⚠ 上一版把 10.05—10.11 的 79 条 / 40 人 / 50.6% 当成上一期，导致 −53.2% / −20.9pt 全错。 */
    svcCallback: 28, svcArrived: 11, svcRate: '39.3', svcRatePrev: '32.4',
    svcPrevCallback: 37, svcPrevArrived: 12, svcGuide: 25, svcWorkload: '3,139',
    mktContacts: 87, mktAdmit: 14, mktRate: '16.1', mktRatePrev: '20.3',
    /* 管家/营销组（2026-10-26 07:28 全量重抓线上《患者有效对接表》5 张分表，逐条核对）：
       本期 10.19—10.25（7 天）87 条 / 转住院 14 人（16.1%），逐人 金林 27 / 朱婧 22 / 利娟 21 / 国威 17 / 菲菲 未填报；
       上一自然周 10.12—10.18（7 天）79 条 / 16 人（20.3%），逐人 利娟 20 / 金林 17 / 朱婧 17 / 国威 13 / 菲菲 12。
       ⚠ 菲菲线上分表最后一行停在 2026-10-18、本期整周 0 条 ⇒ 记 null，不写 0、不进榜、不降榜；
         剔除菲菲后可比口径：87 vs 67 条（+29.9%）、16.1% vs 22.4%。
       ⭐ 总排名按业主《心理管家有效客户对接表》10.19—10.25 块「权重」列：
         金林 4.0 / 朱婧 4.0 / 利娟 3.0 / 国威 3.0，合计 14.0（上期块 16.0：金林 5.3 / 朱婧 4 / 利娟 3 / 国威 2.7 / 菲菲 1）。
         权重相同者按有效对接条数降序；该权重区分不出金林与朱婧、也区分不出利娟与国威。
       ⚠ 线上分表 c10 列表头虽写「权重」，但本期只在 14 个住院行填 1，实为住院标记、不是考核系数，两处不可混。
       ⚠ 营销中心表头（本周入院/门诊/总收入）整行空白，记 null、不拿旧值顶替。 */
    mktDeals: 87, mktDealsPrev: 79, mktHosp: 14, mktHospPrev: 16,
    mktConvertRate: '16.1', mktConvertPrev: '20.3',
    mktMonthDeals: 376, mktMonthHosp: 69, mktMonthRate: '18.4',
    inHouse: 35, inHousePrev: 32,
    /* 医生组本期（10.19—10.25）严格取《特别行动小组汇报表》医生组填报条目：
       表头四列＝本周入院人数 / 本周门诊人数 / 物理治疗费用 / 总收入；出院取自科主任正文。
       上一自然周10.12—10.18 为同源同长度对照。
       ⚠ 旧的「出院结帐明细」「个人归属业绩」两套口径已从首页下架（窗口不是本周），不再参与任何计算。 */
    /* ⭐ 2026-10-26：汇报表医生组整表已滚动到第 4 周（10.19—10.25），回到主表口径。
       表头「物理治疗费用 32.9 万」= 第 3 周旧值（正文第 3 周逐字相同），本周物理取正文 16.7 万。
       营收台账（10.19—10.25，7 天）58.35 万与汇报表同为 7 天却差 7.85 万（13.4%），两套不同源、只并列不相减。 */
    docRev: '50.5', docRevPrev: '72.5', docRevDelta: '−30.3',
    docPhysio: '16.7', docPhysioPrev: '32.9', docPhysioDelta: '−49.2',
    docAdmit: 16, docAdmitPrev: 19, docAdmitDelta: '−15.8',
    docDis: 15, docDisPrev: 17, docDisDelta: '−11.8',
    docOpd: 210, docOpdPrev: 210, docOpdDelta: '0.0',
    docDetailAdmit: 16, docDetailDis: 12, docGapAdmit: 0, docGapDis: 3,
    docCabRev: 33
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

    var analysisHTML=`<section class="decision-core" id="decisionCore"><header class="dc-head"><div><h2>经营问题总览</h2><p>当前不是单一部门表现不好，而是“营收速度不足、转化链条断点、服务兑现流失、数据口径混乱”同时存在。月度营收进度只是最终表现，根本问题是跨部门转化链没有闭合。</p></div><span class="dc-scope">本期 ${_periodLab} · 数据截至 ${lastShort}（营收 ${lastShort}）</span></header><div class="dc-system"><div class="dc-chain"><div class="dc-node"><i>前端</i><b>触达增加</b><span>客服回访${SEC.svcCallback}条、到院${SEC.svcArrived}人（${SEC.svcRate}%），到院率回升但回访量再降</span></div><div class="dc-node"><i>转化</i><b>有效入院不足</b><span>营销接触${SEC.mktContacts} 条、转住院${SEC.mktAdmit} 人（管家对接口径）；每转 1 人需 <b>6.2</b> 条对接（上期 4.9）</span></div><div class="dc-node"><i>服务</i><b>承接与兑现流失</b><span>心理业务回落，护理存在${SEC.nurseMiss}人次应做未做</span></div><div class="dc-node"><i>结果</i><b>营收速度不足</b><span>营收日报日均${mtdAvgWan}万（${lastShort} 止），${monthClosed?`全月收官 · 缺口 ${remainWan} 万`:`达标需${needDailyWan}万`}</span></div></div></div><div class="dc-risks"><article class="dc-risk red"><label>月目标风险</label><strong>${(parseFloat(lagPt)>=0?'落后 ':'领先 ')}${Math.abs(parseFloat(lagPt)).toFixed(1)}pt</strong><p>累计${totalWan}万（${BA_DOT}—${lastShort}），${monthClosed?`<b>${BA_LAB_SP}已收官</b>，缺口 <b>${remainWan} 万</b>，月度目标未达成`:`剩余${remainDays}天还需${remainWan}万，日均缺口${gapDailyWan}万`}。</p></article><article class="dc-risk orange"><label>前端转化</label><strong>到院率 ${SEC.svcRate}%</strong><p>本期（10.19—10.25）回访 ${SEC.svcCallback} 条、到院 ${SEC.svcArrived} 人；<b>到院率由上一期（10.12—10.18）${SEC.svcRatePrev}% 升到本期 ${SEC.svcRate}%，+6.9 个百分点</b>。回访量 37 → <b>28 条（−24.3%）</b>、到院 12 → 11 人（−1 人），<b>量降质升</b>；但<b>台账只有蒋雨一人有记录（28 条）</b>，其余导医 0 条，到院率的分母不稳定。</p></article><article class="dc-risk blue"><label>营销转化</label><strong>${SEC.mktDealsPrev}条 → ${SEC.mktDeals}条</strong><p>管家对接 ${SEC.mktDealsPrev}→${SEC.mktDeals} 条（<b>+10.1%</b>）、转住院 ${SEC.mktHospPrev}→${SEC.mktHosp} 人（<b>−12.5%</b>）、率值 ${SEC.mktConvertPrev}%→${SEC.mktConvertRate}%（<b>−4.2pt</b>；本周 <b>10.19—10.25，7 天</b> 对比上一自然周 <b>10.12—10.18，7 天</b>，<b>同为 7 天、可直接比总量</b>）—— <b>量升质降</b>，每转 1 人所需对接由 4.9 升到 <b>6.2</b>。⚠ <b>菲菲本周整周未填报</b>（表内止于 10.18），按契约记 null、不按 0 降榜；剔除后可比 87 vs 67 条、16.1% vs 22.4%。9 月累计（30 天）376 条 / 69 人（18.4%）可作基线。总排名按业主汇总表<b>权重</b>列：金林 4.0 · 朱婧 4.0 · 利娟 3.0 · 国威 3.0（合计 14.0，上期 16.0），权重相同按条数降序。</p></article><article class="dc-risk purple"><label>数据可用性</label><strong>5组口径冲突</strong><p>趋势可用，但暂不能支持精确绩效排名或奖金结算。</p></article></div><div class="dc-detail-grid">
  <details class="dc-item" open><summary><span class="dc-no">1</span>月度营收节奏达标、但依赖单日高点</summary><p>完成率<b>${amountRate}%</b>${(parseFloat(amountRate)>=parseFloat(timeRate)?'高于':'低于')}时间进度${timeRate}%。本期日均<b>${weekAvgWan} 万</b>，较上一期同期（${pcLabel}，同为 ${pcDays} 天）的 <b>${pcAvgWan} 万</b>${growthTxt}；按当前节奏推演，月末约 ${forecastWan} 万：${(parseFloat(forecastGapWan)>0)?('仍差约 '+forecastGapWan+' 万，必须明确新增收入来源。'):('已可覆盖 260 万目标、超出 '+Math.abs(parseFloat(forecastWan)-parseFloat(txt(f.goalWan,260))).toFixed(2)+' 万；但仍需盯住单日高点依赖与初诊补充。')}</p></details>
  <details class="dc-item" open><summary><span class="dc-no">2</span>客服到院率连升两期，但主动服务量降待确认</summary><p>客服回访 ${SEC.svcCallback} 条、到院 ${SEC.svcArrived} 人（到院率 <b>${SEC.svcRate}%</b>）；上一期（10.12—10.18，同为 7 天）37 条 / 到院 12 人（32.4%）。<b>两段同为完整 7 天，可直接比</b>：回访 <b>−24.3%</b>、到院 <b>−8.3%</b>、<b>到院率 +6.9 pt</b>，<b>量降质升</b>。同期导诊主动服务 25 条（表止 10.21，仅 3 天）对上期同 3 天 21 条（<b>+23.8%</b>）——<b>现场动作没掉、电话回访量在收缩但到院转化反而变好</b>。后续仍须追踪<b>挂号—检查—治疗—入院—实际收入</b>。</p></details>
  <details class="dc-item"><summary><span class="dc-no">3</span>营销组「量升质降」：对接多 8 条，转住院少 2 人</summary><p>管家台账本周（<b>10.19—10.25，7 天</b>）对接 ${SEC.mktDeals} 条、转住院 ${SEC.mktHosp} 人，转住院率 ${SEC.mktConvertRate}%；上一自然周（10.12—10.18，7 天）${SEC.mktDealsPrev} 条 / ${SEC.mktHospPrev} 人 / ${SEC.mktConvertPrev}%。两段<b>同为 7 天</b>：对接 <b>+10.1%</b>、转住院 <b>−2 人（−12.5%）</b>、率值 <b>−4.2pt</b> —— <b>多接 8 次、少转 2 人</b>，每转 1 人所需对接由 4.9 升到 <b>6.2</b>，前端在放量、转化在变薄。结构：复查 68 · 初诊 18 · 空 1。逐日 10.19 <b>4</b> / 10.20 11 / 10.21 9 / 10.22 9 / 10.23 18 / 10.24 5 / 10.25 <b>31</b>（10.25 单日占全周 <b>35.6%</b>，周日集中补录）。逐人：金林 27（住院 4 / 14.8%）· 朱婧 22（4 / 18.2%）· 利娟 21（3 / 14.3%）· 国威 17（3 / 17.6%）。⚠ <b>菲菲本周整周 0 条</b>（分表最后一行 10.18）——记 null、不进榜、不按 0 降榜；剔除后可比 87 vs 67 条（+29.9%）、16.1% vs 22.4%。<b>总排名按业主《心理管家有效客户对接表》10.19—10.25 块「权重」列</b>：金林 <b>4.0</b> / 朱婧 <b>4.0</b> / 利娟 <b>3.0</b> / 国威 <b>3.0</b>，合计 <b>14.0</b>（上期 16.0）；权重相同者按对接条数降序 —— <b>该权重区分不出金林与朱婧、也区分不出利娟与国威</b>，要拉开名次差需组长重设权重。9 月累计（30 天）376 条 / 69 人（18.4%）。⚠ 线上分表 c10 列表头虽写「权重」，但本期只在 14 个住院行填 1，实为<b>住院标记</b>、不是考核系数；朱婧分表第 425、426 行日期写成 2025.10.25，已按笔误计入 10.25，建议原表改回。</p></details>
  <details class="dc-item"><summary><span class="dc-no">4</span>心理咨询组接触升三成、咨询量基本持平</summary><p>本期（<b>10.19—10.25，7 天</b>）患者接触 <b>84</b> 人次（上期 10.19—10.25 为 64，<b>+31.3%</b>）、咨询工作量 <b>46</b> 人次（49，<b>−6.1%</b>）；结构上住院咨询 26→<b>25</b>（−3.8%）、门诊咨询 23→<b>19</b>（−17.4%）、家庭咨询 0→<b>2</b>，<b>23 条日报、5 人填报</b>、家长访谈 37 人次、团体 3 场 / 17 人。仍需核验：① 汇报表心理组表头停在 9.21 旧值（40 人 / 4 场 / 19,002 元），已停用、改用 V4；② 5 人日报完整率 0%—57%（赵芳、王沛然 0%），周表汇总全部「有待补」；③ 苏欣然管床 2 人但不在 5 人名册、不填日报；④ 赵芳 10-18 日报落在简报表末尾第 1005 行，周表公式未覆盖（差 1 天填报 / 1 天查房 / 1 次门诊）。</p></details>
  <details class="dc-item" open><summary><span class="dc-no">5</span>收入降三成、七成降幅在物理治疗，不是均匀下滑</summary><p>本期（<b>10.19—10.25，7 天</b>·《特别行动小组汇报表》医生组·整表已滚动到第 4 周）总收入 <b>${SEC.docRev} 万</b>（上期 ${SEC.docRevPrev} 万，<b>${SEC.docRevDelta}%</b>）、物理治疗 <b>${SEC.docPhysio} 万</b>（上期 ${SEC.docPhysioPrev} 万，<b>${SEC.docPhysioDelta}%</b>）、入院 <b>${SEC.docAdmit} 人</b>（上期 ${SEC.docAdmitPrev}，<b>${SEC.docAdmitDelta}%</b>）、出院 <b>${SEC.docDis} 人</b>（上期 ${SEC.docDisPrev}，<b>${SEC.docDisDelta}%</b>）、门诊 <b>${SEC.docOpd} 人次</b>（上期 ${SEC.docOpdPrev}，<b>${SEC.docOpdDelta}%</b>）。<b>22.0 万的收入降幅里，物理治疗一项贡献 16.2 万＝73.6%</b>；拆开看是<b>住院物理 29.8→12.7 万（−57.4%）、门诊物理 3.1→4.0 万（+29.0%）</b>——门诊端还在涨、住院端腰斩，同期在院由 35 人（10.23）降到 33 人（10.25）。⚠ 表头「物理治疗费用」仍写 32.9 万、与该表正文第 3 周逐字相同，<b>照抄会把本周物理多报一倍、环比写成 0%</b>，本周一律取正文。在院 <b>${SEC.docCabRev} 人</b>（10.25 时点，个人周排）。个人正文 5 人自填加总入院 <b>${SEC.docDetailAdmit}</b>、出院 <b>${SEC.docDetailDis}</b>，<b>入院零差、出院差 ${SEC.docGapDis} 全落在赵郁莹空白行</b>，按契约记 null、不反推。</p></details>
  <details class="dc-item"><summary><span class="dc-no">6</span>物理治疗 92.8%：缺口压在两个项目上</summary><p>本周（<b>10.19—10.25，7 天</b>）6 项应做 <b>${SEC.nurseShould}</b> 人次、实做 <b>${SEC.nurseDone}</b> 人次，仍有 <b>${SEC.nurseMiss} 人次未做</b>（完成率 ${SEC.nurseRate}%）；上一期（10.12—10.18）656 / 613（93%），应做量基本持平（−${SEC.nurseDrop}%）。<b>缺口高度集中</b>：团体生物反馈 25→18（<b>72%</b>，未做 7）、经颅磁 152→139（<b>92%</b>，未做 13），两项占全部 47 人次的 <b>42.6%</b>；失眠治疗仪 33→32（<b>96%</b>）最好。团体是「凑组难」（一周需 25 人次）、经颅磁是「设备与时段不够」，<b>两个原因不同、不能用同一套办法补</b>。当前缺少改期、替代项目、再次沟通、计费与退费的完整闭环。另有<b>电休克治疗 ${SEC.nurseEct} 人次</b>（10.19—10.25 实做），源表只报开展量、<b>未报应做数</b>，故<b>单列、不并入 652/605</b>。</p></details>
  <details class="dc-item"><summary><span class="dc-no">7</span>业务集中在少数人员和日期</summary><p>客服单人负担上升、在院患者集中于少数管床医生、心理记录集中于少数人员和单日、营收依赖周末和高收入日。按总量排名容易奖励资源集中，而非效率与质量。</p></details>
  <details class="dc-item"><summary><span class="dc-no">8</span>数据口径不统一是最大管理障碍</summary><p>仍存在客服回访 <b>${SEC.svcCallback}</b> 条（本周 10.19—10.25，到院 ${SEC.svcArrived} 人 ${SEC.svcRate}%；上期同 7 天 37 条 / 12 人 / 32.4%）、管家对接 <b>${SEC.mktDeals}/${SEC.mktDealsPrev}</b>（本周 10.19—10.25 对上一自然周 10.12—10.18，同为 7 天；⚠ 本周菲菲整周未填报，87 条是 4 人产出、79 条是 5 人产出）、心理接触 <b>84/64</b>（V4 逐条；两期口径已统一为「首接＋情绪＋住院」；汇报表表头停在 9.21 旧值已停用）、<b>营销中心表头三项本周整行空白</b>（本周入院 / 门诊 / 总收入，记 null 不顶替）、医生组表头 <b>入院 ${SEC.docAdmit} / 门诊 ${SEC.docOpd} / 物理 ${SEC.docPhysio} 万 / 总收入 ${SEC.docRev} 万</b>（主表本期），与营收日报的在院 <b>${SEC.inHouse} 人</b>（${lastShort} 时点）<b>不同源、不可互算</b>。客服台账与线上表、营销汇总与逐条等差异仍待统一。护理组排名表为源表考核周口径，与自然周不可混比。</p></details><details class="dc-item"><summary><span class="dc-no">9</span>医生组本周口径：主表整表已滚动，只剩物理治疗一格没滚</summary><p>本周（<b>10.19—10.25，7 天</b>）《特别行动小组汇报表》医生组：总收入 <b>${SEC.docRev} 万</b>、物理治疗 <b>${SEC.docPhysio} 万</b>、入院 <b>${SEC.docAdmit} 人</b>、门诊 <b>${SEC.docOpd} 人次</b>、出院 <b>${SEC.docDis} 人</b>。较上一自然周（10.12—10.18，同为 7 天）：收入 <b>${SEC.docRevDelta}%</b>、物理 <b>${SEC.docPhysioDelta}%</b>、入院 <b>${SEC.docAdmitDelta}%</b>、出院 <b>${SEC.docDisDelta}%</b>、门诊 <b>${SEC.docOpdDelta}%</b>。⚠ 唯一没滚动的表头格是「物理治疗费用 32.9 万」（＝第 3 周原值），正文第 4 周为 16.7 万，差 16.2 万，已存档并在页面标注。个人正文：曾凯 入 5 / 出 2、康言 入 4 / 出 3、王建 入 4 / 出 2、王建宁 入 3 / 出 5（单独转化 1 人）、<b>赵郁莹两格空白</b>；孙乐（住院总医师）转化 5 / 多导 5，岗位口径不同、不并入入出院。加总入 16 / 出 12，对表头 <b>入院零差、出院差 3</b>。营收台账 10.19—10.25 共 7 天 <b>58.35 万</b>，与主表 7 天 50.5 万<b>同为 7 天</b>却差 7.85 万（13.4%）——两套不同源，<b>不可相减、也不可互相校验</b>（两套数逐周差异 −30%～+38%）；且汇报表自身「本周总收入」表头 52.6、正文 72.5、页面沿用 50.5 三处对不上，本轮一律以台账为准。</p></details></div><p class="dc-note"><b>管理结论：</b>优先修复患者级跨部门追踪和“医嘱—排程—执行—计费—退费”闭环；绩效排名只作月内动态试算，待口径冲突、缺失和归因完成后再在月末锁定。</p></section>`;
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
