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
      goal:goal, done:done, rem:rem, gap:gap, need:need,
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
      +   '<div class="finance-kpi '+(f.gap>0?'bad':'')+'"><span>预算缺口</span><strong>−'+num(f.gap)+'万</strong><em>目标 '+num(f.goal,0)+'万</em></div>'
      +   (f.closed
            ? '<div class="finance-kpi warn"><span>目标达成率</span><strong>'+num(f.rate,1)+'%</strong><em>'+FE_LAB_SP+'已收官 · 缺口 '+num(f.gap)+' 万</em></div>'
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
    /* ⛔ 月累计完成率（业主 2026-10-19 指定）：与《特别行动小组汇报表》冲突时取汇报表。
       营收日报只到 10.17，比汇报表少一天，直接用日报算会把完成率压低约 10pt。 */
    var _mr=((window.OPS_LIVE_SNAPSHOT||{}).metrics||{}).monthRevenue||null;
    var _auth=!!(_mr&&_mr.authority==='action_report'&&_mr.amountProgress!=null);
    var _dt=((window.OPS_LIVE_SNAPSHOT||{}).watermarks||{}).dept||null;
    var rate=_auth?_mr.amountProgress:s.derive().amountRate;
    var t=box.querySelector('strong'); if(t)t.textContent=rate.toFixed(1)+'%';
    var b=box.querySelector('.side-goal-track b');
    if(b)b.style.width=Math.min(100,Math.max(0,rate)).toFixed(1)+'%';
    var sm=box.querySelector('small');
    if(sm)sm.textContent=FE_LAB+'营收目标进度（至 '+((_auth&&_dt&&_dt.dataThrough)?mdOf(_dt.dataThrough):(mdOf(s.updatedThrough)||'—'))+'）';
    /* ⚠⚠ 2026-10-07 修：「目标风险 高」原先是**写死**的字符串，不随数据滚动。
       实测 10.6 口径下完成率 22.0% 已**高于**时间进度 19.4%（领先 2.6pt），
       侧栏却仍报「高」，与经营问题总览的「领先 2.6pt」自相矛盾。
       改为按 (时间进度 − 完成率) 分档：≤0 低（领先）、≤5 中、>5 高。 */
    var _d=s.derive();
    var _lag=(_d.timeRate||0)-rate;
    var _lv=_lag<=0?'低':(_lag<=5?'中':'高');
    /* ⚠ `.side-signals` 是 `.side-goal` 的**兄弟**节点，不是子节点 ——
       从 box 内部 querySelector 永远查不到（本轮实测踩过）。改从其父容器取。 */
    var _root=box.parentNode||box;
    var _rj=_root.querySelector('.side-signal.risk')||_root.querySelector('.side-signal');
    if(_rj){ _rj.innerHTML='目标风险<b>'+_lv+'</b>';
      _rj.classList.toggle('risk',_lv==='高');
      _rj.classList.toggle('ok',_lv==='低');
      _rj.title='时间进度 '+(_d.timeRate||0).toFixed(1)+'% − 完成率 '+rate.toFixed(1)+'% = '+_lag.toFixed(1)+'pt';
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
    entertainment:{title:'工娱组经营详情',metrics:[['患者活动','12场 / 120人'],['家属活动','7场 / 61人'],['合计参与','19场 / 181人'],['场均参与','10人']],rows:[['患者活动','12场','120人','住院部患者参加'],['家属活动','7场','61人','家属专场'],['大众5星打卡点评','—','21条','节假日抽奖形式 · 平台涨分0.3'],['抖音/小红书带logo视频','—','10条','#梓笙园医院logo'],['积分兑换','约30人次','—','9月礼品墙已更新']],notes:['⭐ 本周整体上量：患者 12 场 120 人 ＋ 家属 7 场 61 人 ＝ <b>19 场 181 人</b>，场均 <b>10 人</b>（上一版 10 场 86 人）。','主表护理组表头仍记「5 场 62 人」，与本组叙述口径冲突，正式排名前必须核验、不可相加。','活动需绑定患者ID、执行人、开始结束时间及活动后评估；停用礼品转节日/活动抽奖，避免库存沉淀。'],source:'原营销模块：工娱活动台账、积分兑换与礼品墙记录；业主 2026-10-12 截图口径'},
    butler:{title:'管家组经营详情',metrics:[['本周有效对接','89条'],['复诊 / 初诊','73 / 16'],['检查 / 物理 / 心理','62 / 19 / 23'],['本周转住院率','12.4%']],rows:[['朱婧','33','6.1%','量最大、率值最低，最该复盘'],['国威','22','18.2%','率值最高（样本充足）'],['利娟','17','11.8%','样本渐足'],['金林','15','6.7%','率值回落'],['菲菲','2','100%','样本过小，率值不具意义']],notes:['管家台账本周（<b>10.5—10.11，7 天</b>）逐条 89 条（朱婧 33 / 国威 22 / 利娟 17 / 金林 15 / 菲菲 2）、转住院 11 人（12.4%）；上一自然周（9.28—10.4，7 天）60 条 / 16 人（26.7%），两段同为 7 天可直接比总量。','⚠⚠ 上一周（9.28—10.4）表中<b>菲菲、国威两栏源表整格为「/」（未填报）</b>，上期 60 条仅含金林 12 / 朱婧 23 / 利娟 12 三人 ⇒ 环比混有口径缺口，<b>不能据此判定两人上期未工作</b>，建议补录后重算。','9 月累计（9.1—9.30，30 天）有效对接 376 条 / 转住院 69 人（18.4%），逐人 朱婧 99 / 金林 83 / 国威 68 / 利娟 66 / 菲菲 60，<b>五人全部有量</b>，与本周菲菲 2 条形成反差，印证上期缺口属填报问题。','⚠ 源表「住院人数」列（69）与「住院权重」列（68.3）并存、口径未说明，本页取住院人数列、权重列原样保留待业主确认。个人样本 2—33 条，率值只作趋势参考。'],source:'《10月心理管家本周有效客户对接表》（业主 2026-10-12 提供）'},channel:{title:'渠道组经营详情',metrics:[['意向机构','3家'],['累计拜访','5客户'],['转介到院','13人'],['教授直转到院','100%']],rows:[['珞康医院','意向','筛查/转介','未签约'],['双福五小','意向','校园合作','未签约'],['双福三小','意向','校园合作','未签约'],['教授直转','执行中','患者转介','到院率100%']],notes:['渠道线索必须从来源标签贯通预约、到院、治疗、入院和收入。','旧表存在机构名单与“2个转化”的冲突记录，需保留版本与核验人。','排名宜看渠道收入、有效转化和回款周期，不能只看拜访次数。'],source:'原营销模块：渠道拜访、机构合作与转介记录'}
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
