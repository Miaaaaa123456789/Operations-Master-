(function(){
  /* ==========================================================================
     财务经营分析 · Finance View ＋ 侧栏经营状态 ＋ 子部门弹层

     ⚠ 2026-09-26 改造：财务面板原先是一整套**写死的字面量**（9.22 口径：
     预算缺口 −106.11 万、达标所需日均 13.26 万、剩余 8 天、周末贡献 40.4%…）。
     营收推进到 9.25（累计 178.00 万）后，面板仍显示 106.11 万，与首页目标卡
     （剩余 5 天需 82.00 万）互相矛盾。

     现改为**从唯一真源派生**，不自己存一份数据：
        window.SEPTEMBER_REVENUE_DATA.derive()  ← 由 OPS_REVENUE（营收日报）驱动
     并在 september-revenue-updated 事件上重绘 —— 拖图片导入后财务面板自动跟随。
     ========================================================================== */

  var GOAL_FALLBACK = 260;            // 月度目标（万元）

  function num(v,d){return (Number(v)||0).toFixed(d==null?2:d);}
  /* 负数统一用 U+2212 减号，与项目既有行文一致 */
  function sgn(v){v=Number(v)||0;return (v<0?'\u2212':'')+Math.abs(v).toFixed(2);}
  function mdOf(d){return d?((+d.slice(5,7))+'月'+(+d.slice(8))+'日'):'';}
  function src(){return window.SEPTEMBER_REVENUE_DATA;}
  /* ⭐ 结算月标签（2026-10-06 主面板切 10 月）—— 别再写死「9月」 */
  var FE_MONTH=(window.SEPTEMBER_REVENUE_DATA&&window.SEPTEMBER_REVENUE_DATA.SETTLED_MONTH)||'2026-10';
  var FE_NUM=+FE_MONTH.slice(5,7);
  var FE_LAB=FE_NUM+'月';        // '10月'
  var FE_LAB_SP=FE_NUM+' 月';    // '10 月'

  /* ---- 财务口径模型（全部由数据算出，无写死数字） ---- */
  function financeModel(){
    var s=src();
    if(!s||typeof s.derive!=='function'||!s.rows||!s.rows.length)return null;
    var x=s.derive(),m=x.month,goal=(s.goal||GOAL_FALLBACK*10000)/10000;
    var done=m.total/10000, rem=x.remainingDays, gap=Math.max(0,goal-done);
    var need=rem?gap/rem:0;
    /* ⭐⭐ 对照期一律用数据层给的「本期 / 上一期」（业主 2026-10-06：本期＝两周窗口 9.28—10.11）。
       原先取 weeks[] 里「本周的前一项」——本期改成两周窗口后，那一项会落到**本期内部**
       （10.1—10.4），标签却写「上周」，语义自相矛盾；更早的版本还会取到未发生的未来周。 */
    var _per=x.period||{}, _pp=x.prevPeriod||{};
    var _agg=function(from,to){var R=s.subset(from,to),t=0;R.forEach(function(r){t+=r.total;});
      return {t:t,n:R.length,a:R.length?t/R.length/10000:0};};
    var _lw=_agg(_pp.from,_pp.to);
    /* 上上期＝再往前一个等长区间（仅用于「环比节奏」对照） */
    var _prevRows=s.rows.filter(function(r){return _pp.from&&r.date<_pp.from;});
    var _pp2=_prevRows.slice(Math.max(0,_prevRows.length-14)), _pp2t=0;
    _pp2.forEach(function(r){_pp2t+=r.total;});
    var lwAvg=_lw.a, pwAvg=_pp2.length?(_pp2t/_pp2.length/10000):0, lwLabel=_pp.label||'';
    var cw=x.currentWeek, cwAvg=cw.days?cw.total/10000/cw.days:0;
    var fcst=done+rem*lwAvg, scn=done+rem*cwAvg;
    /* ⚠⚠ 2026-10-06 修：原遍历 s.rows（＝全部日期，含 9 月整月）。
       主面板切到 10 月后，这会把 9 月的销售算进「本月门诊/住院占比」、
       且单日峰值会取到 9.6（18.38 万）而不是 10 月内的 10.1。
       改为只统计**结算月区间**。 */
    var _mF=x.monthFirst||(s.SETTLED_MONTH||'2026-10')+'-01',
        _mL=x.monthLast||(s.SETTLED_MONTH||'2026-10')+'-31';
    var tot=0,out=0,inp=0,wk=0,mx=-1,mxd='',wkDays=0,mDays=0;
    s.rows.filter(function(r){ return r.date>=_mF && r.date<=_mL; }).forEach(function(r){
      mDays++;
      tot+=r.total; out+=r.outpatient; inp+=r.inpatient;
      if(r.weekday==='周六'||r.weekday==='周日'){wk+=r.total;wkDays++;}
      if(r.total>mx){mx=r.total;mxd=r.date;}
    });
    var closed=(rem===0);
    return {
      closed:closed, rate:goal?done/goal*100:0,
      wkDelta:(pwAvg?(lwAvg/pwAvg-1)*100:0),
      lwLabel:lwLabel, pwLabel:_pp2.length?('上上期'):'', perLabel:_per.label||'',
      goal:goal, done:done, rem:rem, gap:gap, over:Math.max(0,done-goal), need:need,
      lwAvg:lwAvg, cwAvg:cwAvg, fcst:fcst, delta:fcst-goal,
      speed:lwAvg?(need/lwAvg-1)*100:0, scn:scn,
      oShare:tot?out/tot*100:0, iShare:tot?inp/tot*100:0,
      wkShare:tot?wk/tot*100:0, wkDays:wkDays,
      mxShare:tot?mx/tot*100:0, mxDate:mdOf(mxd),
      cwDays:cw.days,
      /* ⚠ 原为 s.rows.length（＝全部日期，9 月 30 天 + 10 月 5 天 = 35）。
         主面板切到 10 月后，标题写着「营收日报数据截至 10.5 · 共 35 天」会自相矛盾。
         改为结算月内已录天数。 */
      mDays:mDays, mTotalDays:(x.monthDays||31),
      days:s.rows.length, cut:mdOf(s.updatedThrough||x.lastDate),
      /* ⚠ 收官后 scn/fcst 会退化成月累计（rem=0 时 =done），不能直接当「本周/上周完整周」用 */
      cwTotalWan:cw.total/10000, lwTotalWan:_lw.t/10000,
      /* ⚠ cutShort 的月份必须从日期取（原文硬编码 '9.'，跨月后 10.4 会显示成 9.4） */
      cutShort: (function () {
        var _d = String(s.updatedThrough || x.lastDate || '');
        return _d.length >= 10 ? ((+_d.slice(5, 7)) + '.' + (+_d.slice(8))) : '';
      })()
    };
  }

  function financeHtml(f){
    var wCur=Math.min(100,Math.max(0,f.goal?f.scn/f.goal*100:0));
    var wPrev=Math.min(100,Math.max(0,f.goal?f.fcst/f.goal*100:0));
    /* 收官口径：本周/上周完整周相对月度目标的占比 */
    var wCW=Math.min(100,Math.max(0,f.goal?(f.cwTotalWan||0)/f.goal*100:0));
    var wLW=Math.min(100,Math.max(0,f.goal?(f.lwTotalWan||0)/f.goal*100:0));
    return ''
      + '<div class="finance-head"><div><h3>财务经营分析 · Finance View</h3>'
      + '<p>从预算差异、运行速度、收入结构与情景预测判断经营质量</p></div>'
      + '<span class="finance-tag">营收日报数据截至 '+f.cut+' · '+FE_LAB+'已录 '+f.mDays+'/'+f.mTotalDays+' 天</span></div>'
      + '<div class="finance-kpis">'
      +   '<div class="finance-kpi '+(f.gap>0?'bad':'')+'"><span>'+(f.over>0?'目标超额':'预算缺口')+'</span><strong>'+(f.over>0?('+'+num(f.over)+'万'):('−'+num(f.gap)+'万'))+'</strong><em>目标 '+num(f.goal,0)+'万</em></div>'
      +   (f.closed
            ? '<div class="finance-kpi warn"><span>目标达成率</span><strong>'+num(f.rate,1)+'%</strong><em>'+FE_LAB_SP+'已收官 · '+(f.over>0?('超额 '+num(f.over)+' 万'):('缺口 '+num(f.gap)+' 万'))+'</em></div>'
            : '<div class="finance-kpi warn"><span>达标所需日均</span><strong>'+num(f.need)+'万</strong><em>剩余 '+f.rem+' 天</em></div>')
      +   '<div class="finance-kpi"><span>基准情景预测</span><strong>'+num(f.fcst)+'万</strong><em>按上一期日均 '+num(f.lwAvg)+'万</em></div>'
      +   '<div class="finance-kpi '+(f.delta<0?'bad':'')+'"><span>预测目标差额</span><strong>'+sgn(f.delta)+'万</strong><em>基准情景</em></div>'
      +   (f.closed
            ? '<div class="finance-kpi"><span>周环比节奏</span><strong>'+(f.wkDelta>=0?'+':'')+num(f.wkDelta,1)+'%</strong><em>上一期 vs 上上期日均</em></div>'
            : '<div class="finance-kpi '+(f.speed>0?'warn':'')+'"><span>所需提速</span><strong>'+(f.speed>=0?'+':'')+num(f.speed,1)+'%</strong><em>相较上一期日均</em></div>')
      + '</div>'
      + '<div class="finance-body">'
      +   '<div class="scenario"><h4>'+(f.closed?(FE_LAB_SP+'营收收官对比'):'月末营收情景测算')+'</h4>'
      +     '<div class="scenario-row"><span>'+(f.closed?('本期（'+f.cwDays+' 天）已发生'):'当前速度')+'</span><div class="scenario-bar"><i style="width:'+(f.closed?wCW:f.scn/f.goal*100).toFixed(1)+'%"></i></div><b>'+num(f.closed?f.cwTotalWan:f.scn)+'</b></div>'
      +     '<div class="scenario-row"><span>'+(f.closed?('上一期 '+f.lwLabel):'上一期速度')+'</span><div class="scenario-bar"><i style="width:'+(f.closed?wLW:f.fcst/f.goal*100).toFixed(1)+'%"></i></div><b>'+num(f.closed?f.lwTotalWan:f.fcst)+'</b></div>'
      +     '<div class="scenario-row goal"><span>月度目标</span><div class="scenario-bar"><i style="width:100%"></i></div><b>'+num(f.goal)+'</b></div>'
      +   '</div>'
      +   '<div class="quality"><h4>收入质量观察</h4><div class="quality-grid">'
      +     '<div class="quality-item"><small>门诊收入占比</small><b>'+num(f.oShare,1)+'%</b></div>'
      +     '<div class="quality-item"><small>住院收入占比</small><b>'+num(f.iShare,1)+'%</b></div>'
      +     '<div class="quality-item"><small>周末贡献</small><b>'+num(f.wkShare,1)+'%</b></div>'
      +     '<div class="quality-item"><small>单日最高占比</small><b>'+num(f.mxShare,1)+'%</b></div>'
      +   '</div><div class="finance-note">以上四项均为 '+FE_LAB+'累计口径（含周末 '+f.wkDays+' 天），'
      +   '单日最高出现在 '+f.mxDate+'。'+(f.closed?'<b>'+FE_LAB_SP+'已收官</b>：累计＝实际发生额；本期＝'+(f.cwDays||0)+' 天已发生日均。':'当前速度＝本月累计＋剩余天数×本期（'+(f.cwDays||0)+' 天）日均；上一期速度＝本月累计＋剩余天数×上一期（'+f.lwLabel+'）日均。')
      +   '成本、折扣退费、应收账款尚未接入，因此暂不能严谨计算利润率、毛利率与现金流。</div></div>'
      + '</div>';
  }

  function renderFinance(){
    var box=document.querySelector('.finance-board'); if(!box)return;
    var f=financeModel(); if(!f)return;
    box.innerHTML=financeHtml(f);
  }

  function addFinance(){
    const root=document.querySelector('.mkt-v2'); if(!root||root.querySelector('.finance-board')) return;
    const anchor=root.querySelector('.mkt-detail-grid')||root.lastElementChild;
    const parent=anchor?anchor.parentElement:root;
    const el=document.createElement('section'); el.className='finance-board';
    if(parent)parent.insertBefore(el,anchor);else root.appendChild(el);
    renderFinance();
  }

  /* ---- 侧栏「月度营收目标进度」：原先写死 59.2% ---- */
  function renderSideGoal(){
    var box=document.querySelector('.side-goal'); if(!box)return;
    var s=src(); if(!s||typeof s.derive!=='function'||!s.rows||!s.rows.length)return;
    /* ⛔ 月累计完成率（业主 2026-10-22 更新）：营收日报已补到 10.20，覆盖比汇报表多 2 天，
       故月累计改取日报（authority=revenue_daily_report，169.48 万 / 65.2%）；
       汇报表同项 167.70 万只滚到 10.18，仍并存标注、不互相覆盖。
       ⚠ 旧注释「日报只到 10.17、比汇报表少一天」已失效，别再据此改回汇报表口径。 */
    var _mr=((window.OPS_LIVE_SNAPSHOT||{}).metrics||{}).monthRevenue||null;
    /* ⚠ 2026-11-04：monthRevenue 已切 11 月，而本侧栏标签是 FE_LAB（10 月）；
       月份不符时退回 s.derive()，否则会出现「10月营收目标进度（至 11月2日）8.5%」。 */
    if(_mr&&_mr.periodStart&&_mr.periodStart.slice(0,7)!==FE_MONTH)_mr=null;
    var _auth=!!(_mr&&_mr.amountProgress!=null&&(_mr.authority==='action_report'||_mr.authority==='revenue_daily_report'));
    var _dt=((window.OPS_LIVE_SNAPSHOT||{}).watermarks||{}).dept||null;
    var rate=_auth?_mr.amountProgress:s.derive().amountRate;
    var t=box.querySelector('strong'); if(t)t.textContent=rate.toFixed(1)+'%';
    var b=box.querySelector('.side-goal-track b');
    if(b)b.style.width=Math.min(100,Math.max(0,rate)).toFixed(1)+'%';
    var sm=box.querySelector('small');
    var _mCut=(function(){var rr=(s.rows||[]).filter(function(r){return String(r.date).indexOf(FE_MONTH)===0;});return rr.length?rr[rr.length-1].date:(s.updatedThrough||'');})();
    if(sm)sm.textContent=FE_LAB+'营收目标进度（至 '+((_auth&&_mr.dataThrough)?mdOf(_mr.dataThrough):(mdOf(_mCut)||'—'))+'）';
    /* ⚠⚠ 2026-10-07 修：「目标风险 高」原先是**写死**的字符串，不随数据滚动。
       实测 10.6 口径下完成率 22.0% 已**高于**时间进度 19.4%（领先 2.6pt），
       侧栏却仍报「高」，与经营问题总览的「领先 2.6pt」自相矛盾。
       改为按 (时间进度 − 完成率) 分档：≤0 低（领先）、≤5 中、>5 高。 */
    var _d=s.derive();
    var _timeRate=(_auth&&_mr.timeProgress!=null)?_mr.timeProgress:(_d.timeRate||0);
    var _lag=_timeRate-rate;
    var _lv=_lag<=0?'低':(_lag<=5?'中':'高');
    /* ⚠ `.side-signals` 是 `.side-goal` 的**兄弟**节点，不是子节点 ——
       从 box 内部 querySelector 永远查不到（本轮实测踩过）。改从其父容器取。 */
    var _root=box.parentNode||box;
    var _rj=_root.querySelector('.side-signal.risk')||_root.querySelector('.side-signal');
    if(_rj){ _rj.innerHTML='目标风险<b>'+_lv+'</b>';
      _rj.classList.toggle('risk',_lv==='高');
      _rj.classList.toggle('ok',_lv==='低');
      _rj.title='时间进度 '+_timeRate.toFixed(1)+'% − 完成率 '+rate.toFixed(1)+'% = '+_lag.toFixed(1)+'pt';
    }
  }

  function addSidebar(){
    const sidebar=document.querySelector('.sidebar'); if(!sidebar||sidebar.querySelector('.side-pulse')) return;
    const nav=sidebar.querySelector('.nav-label')||sidebar.children[2];
    const box=document.createElement('section'); box.className='side-pulse'; box.innerHTML=`
      <div class="side-pulse-head"><span>经营状态</span><i></i></div>
      <div class="side-goal"><small>月度营收目标进度</small><strong>—</strong><div class="side-goal-track"><b></b></div></div>
      <div class="side-signals"><div class="side-signal risk">目标风险<b>高</b></div><div class="side-signal data">待核验数据<b>17</b></div></div>
      <div class="side-shortcuts"><button data-jump="insights">重大问题</button><button data-jump="departments">部门经营</button></div>`;
    sidebar.insertBefore(box,nav);
    box.addEventListener('click',e=>{const b=e.target.closest('[data-jump]');if(b)document.getElementById(b.dataset.jump)?.scrollIntoView({behavior:'smooth'});});
    renderSideGoal();
  }

  const data={
    entertainment:{title:'工娱组经营详情',metrics:[['患者参与','未报'],['家属参与','未报'],['合计参与','未报'],['积分兑换（10 月累计）','16 人']],rows:[['患者参与','—','住院部患者','本期源表未报，记 null'],['家属参与','—','家属专场','本期源表未报，记 null'],['合计参与','—','患者＋家属','不按 0 计入'],['积分兑换','16 人','10.1—10.18 累计','⚠ 月累计，非本周单周值'],['大众5星打卡点评','21 条','—','节假日抽奖形式 · 平台涨分0.3（上一版填报，本期未更新）'],['抖音/小红书带logo视频','10 条','—','#梓笙园医院logo（上一版填报，本期未更新）']],notes:['⛔ 本期（<b>10.26—11.01</b>）工娱组<b>未报</b>患者参与、家属参与、活动场次——三项全部记 null，<b>不拿上一期 61 / 43 / 104 顶替、也不按 0 计入</b>，否则会把「没交表」算成「参与归零」。','上一期（10.19—10.25）业主报数：患者 61 人 ＋ 家属 43 人 ＝ 104 人，<b>仅作存档</b>，不参与本期任何计算或环比。','⭐ 积分兑换 <b>10 月累计 16 人</b>（10.1—10.18），<b>是月累计、不是本周单周值</b>，不能与周参与人数并列算率；9 月礼品墙口径为「约 30 人次」，<b>人 / 人次不同量纲</b>，不做增减计算。','⚠ 主表护理组表头另记「工娱 <b>5 场 / 62 人次</b>」，与本组叙述口径<b>不同源、不可相加</b>；场次未给，场均<b>记 null、不推算</b>。','活动需绑定患者ID、执行人、开始结束时间及活动后评估；停用礼品转节日/活动抽奖，避免库存沉淀。'],source:'本节数据：本期未报（源表无新数）；上一期存档为业主 2026-10-26 微信报数（61 / 43 / 104）；积分兑换为 10 月累计（截至 10.18）'},
    butler:{title:'管家组经营详情',metrics:[['本周有效对接','92条 / 86人'],['复查 / 初诊','67 / 25'],['权重标记','12 格（＝转住院人数）'],['本周转住院率','13.0%']],rows:[['朱婧','33','3','条数第 1 · 转住院率 9.1%'],['国威','25','3','转住院率 12.0%'],['金林','17','3','转住院率 17.6% · 与利娟并列'],['利娟','17','3','转住院率 17.6% · 与金林并列'],['菲菲','未填报','—','整周无记录，记 null 不记 0']],notes:['管家台账本期（<b>10.26—11.01，7 天</b>）逐条 92 条（朱婧 33 / 国威 25 / 金林 17 / 利娟 17 / 菲菲 未填报）、转住院 12 人（13.0%），复查 67 / 初诊 25；上一期同 7 天 86 条 / 14 人（16.3%）、复查 68 / 初诊 18，两段同为 7 天可直接比：对接 <b>+7.0%</b>、转住院 <b>−2 人（−14.3%）</b>、率值 <b>−3.3pt</b>，每转 1 人所需对接由 6.1 升到 <b>7.7</b>。','逐日 <b>11 / 4 / 6 / 6 / 3 / 35 / 27</b>：10.31—11.01 两天 <b>62 条＝67.4%</b>，周末集中录入比上一期更重。','⚠ 菲菲本期<b>整周未填报</b>（线上分表最后一行 2026-10-18），按「缺项不写 0」记 null、不进榜也不降榜；<b>两期均为 4 人产出</b>（92 vs 86），可直接比。','⚠ 92 条里 <b>6 人次是同一位患者周内二次对接</b>（罗X、谢X馨、刘X成、黄X媛、王X鸿、刘X航），<b>按患者去重 86 位</b>；条数口径与去重口径并列，不相加。','⚠ 利娟分表 <b>2 行只填了姓名、日期为空</b>（孔X凝、张X凤），无法归入任何周窗、未计入，<b>需业主补日期</b>；另有 4 行日期笔误（国威 2026.89.13、金林 226.7.31 / 226.8.22、朱婧 20267.28）落在 7—9 月，不影响本周。','⚠ 「权重」列本期只填 <b>12 格「1」</b>，与 12 人转住院一一对应（每人均 3），属住院标记而非权重打分 → 本轮<b>只按有效对接条数排序</b>，不算权重分，不拿上期 14.0 / 16.0 顶替。','9 月以当月定稿存档 <b>367 条 / 61 人（16.6%）</b> 为基线（逐人 朱婧 99 / 金林 83 / 利娟 65 / 菲菲 60 / 国威 60）；按同一源表现值重算为 367 / 67（住院标记在 9 月后补录），<b>不覆盖存档、两组并列留档</b>。'],source:'《患者有效对接表》线上 5 张管家分表（2026-11-02 重抓）＋9 月定稿存档；权重列仅作住院标记'},
  };
  function ensureModal(){
    if(document.getElementById('subdeptModal'))return;
    const m=document.createElement('div');m.id='subdeptModal';m.className='subdept-backdrop';m.innerHTML='<div class="subdept-modal" role="dialog" aria-modal="true"><div class="subdept-top"><h2 id="subdeptTitle"></h2><button class="subdept-close" aria-label="关闭">×</button></div><div class="subdept-content" id="subdeptContent"></div></div>';document.body.appendChild(m);
    m.addEventListener('click',e=>{if(e.target===m||e.target.closest('.subdept-close'))m.classList.remove('open')});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')m.classList.remove('open')});
  }
  function openDept(key){
    const d=data[key];if(!d)return;ensureModal();
    document.getElementById('subdeptTitle').textContent=d.title;
    document.getElementById('subdeptContent').innerHTML=`<div class="subdept-summary">${d.metrics.map(x=>`<div class="subdept-metric"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('')}</div><div class="subdept-grid"><div class="subdept-card"><h3>数据明细</h3><table class="subdept-table"><thead><tr><th>对象</th><th>工作量</th><th>转化/人数</th><th>判断</th></tr></thead><tbody>${d.rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table><span class="source-chip">数据来源：${d.source}</span></div><div class="subdept-card"><h3>经营判断与动作</h3><ol class="subdept-list">${d.notes.map(n=>`<li>${n}</li>`).join('')}</ol></div></div>`;
    document.getElementById('subdeptModal').classList.add('open');
  }
  function bindDepts(){
    const grid=document.getElementById('deptGrid');if(!grid)return;
    grid.addEventListener('click',e=>{const b=e.target.closest('[data-subdept]');if(!b)return;e.preventDefault();e.stopImmediatePropagation();openDept(b.dataset.subdept);},true);
  }
  function boot(){try{addSidebar()}catch(e){console.warn('side-pulse',e)}
                try{addFinance()}catch(e){console.warn('finance',e)}
                try{ensureModal()}catch(e){console.warn('modal',e)}
                try{bindDepts()}catch(e){console.warn('bindDepts',e)}}
  /* 数据更新（含拖拽导入图片）→ 财务面板与侧栏进度一起重算 */
  window.addEventListener('september-revenue-updated',function(){
    try{renderFinance()}catch(e){console.warn('finance rerender',e)}
    try{renderSideGoal()}catch(e){console.warn('sidegoal rerender',e)}
  });
  window.renderFinanceBoard=renderFinance;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,80));else setTimeout(boot,80);
})();
