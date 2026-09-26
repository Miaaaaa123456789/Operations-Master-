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

  /* ---- 财务口径模型（全部由数据算出，无写死数字） ---- */
  function financeModel(){
    var s=src();
    if(!s||typeof s.derive!=='function'||!s.rows||!s.rows.length)return null;
    var x=s.derive(),m=x.month,goal=(s.goal||GOAL_FALLBACK*10000)/10000;
    var done=m.total/10000, rem=x.remainingDays, gap=Math.max(0,goal-done);
    var need=rem?gap/rem:0;
    /* 上周＝上一个完整自然周（9.14—9.20）实际日均；本周＝本周已发生天数日均 */
    var lw=x.weeks[2], lwAvg=lw.days?lw.total/10000/lw.days:0;
    var cw=x.currentWeek, cwAvg=cw.days?cw.total/10000/cw.days:0;
    var fcst=done+rem*lwAvg, scn=done+rem*cwAvg;
    var tot=0,out=0,inp=0,wk=0,mx=-1,mxd='',wkDays=0;
    s.rows.forEach(function(r){
      tot+=r.total; out+=r.outpatient; inp+=r.inpatient;
      if(r.weekday==='周六'||r.weekday==='周日'){wk+=r.total;wkDays++;}
      if(r.total>mx){mx=r.total;mxd=r.date;}
    });
    return {
      goal:goal, done:done, rem:rem, gap:gap, need:need,
      lwAvg:lwAvg, cwAvg:cwAvg, fcst:fcst, delta:fcst-goal,
      speed:lwAvg?(need/lwAvg-1)*100:0, scn:scn,
      oShare:tot?out/tot*100:0, iShare:tot?inp/tot*100:0,
      wkShare:tot?wk/tot*100:0, wkDays:wkDays,
      mxShare:tot?mx/tot*100:0, mxDate:mdOf(mxd),
      cwDays:cw.days, days:s.rows.length, cut:mdOf(s.updatedThrough||x.lastDate),
      cutShort:'9.'+(+((s.updatedThrough||x.lastDate||'').slice(8))||'')
    };
  }

  function financeHtml(f){
    var wCur=Math.min(100,Math.max(0,f.goal?f.scn/f.goal*100:0));
    var wPrev=Math.min(100,Math.max(0,f.goal?f.fcst/f.goal*100:0));
    return ''
      + '<div class="finance-head"><div><h3>财务经营分析 · Finance View</h3>'
      + '<p>从预算差异、运行速度、收入结构与情景预测判断经营质量</p></div>'
      + '<span class="finance-tag">营收日报数据截至 '+f.cut+' · 共 '+f.days+' 天</span></div>'
      + '<div class="finance-kpis">'
      +   '<div class="finance-kpi '+(f.gap>0?'bad':'')+'"><span>预算缺口</span><strong>−'+num(f.gap)+'万</strong><em>目标 '+num(f.goal,0)+'万</em></div>'
      +   '<div class="finance-kpi warn"><span>达标所需日均</span><strong>'+num(f.need)+'万</strong><em>剩余 '+f.rem+' 天</em></div>'
      +   '<div class="finance-kpi"><span>基准情景预测</span><strong>'+num(f.fcst)+'万</strong><em>按上周日均 '+num(f.lwAvg)+'万</em></div>'
      +   '<div class="finance-kpi '+(f.delta<0?'bad':'')+'"><span>预测目标差额</span><strong>'+sgn(f.delta)+'万</strong><em>基准情景</em></div>'
      +   '<div class="finance-kpi '+(f.speed>0?'warn':'')+'"><span>所需提速</span><strong>'+(f.speed>=0?'+':'')+num(f.speed,1)+'%</strong><em>相较上周日均</em></div>'
      + '</div>'
      + '<div class="finance-body">'
      +   '<div class="scenario"><h4>月末营收情景测算</h4>'
      +     '<div class="scenario-row"><span>当前速度</span><div class="scenario-bar"><i style="width:'+wCur.toFixed(1)+'%"></i></div><b>'+num(f.scn)+'</b></div>'
      +     '<div class="scenario-row"><span>上周速度</span><div class="scenario-bar"><i style="width:'+wPrev.toFixed(1)+'%"></i></div><b>'+num(f.fcst)+'</b></div>'
      +     '<div class="scenario-row goal"><span>月度目标</span><div class="scenario-bar"><i style="width:100%"></i></div><b>'+num(f.goal)+'</b></div>'
      +   '</div>'
      +   '<div class="quality"><h4>收入质量观察</h4><div class="quality-grid">'
      +     '<div class="quality-item"><small>门诊收入占比</small><b>'+num(f.oShare,1)+'%</b></div>'
      +     '<div class="quality-item"><small>住院收入占比</small><b>'+num(f.iShare,1)+'%</b></div>'
      +     '<div class="quality-item"><small>周末贡献</small><b>'+num(f.wkShare,1)+'%</b></div>'
      +     '<div class="quality-item"><small>单日最高占比</small><b>'+num(f.mxShare,1)+'%</b></div>'
      +   '</div><div class="finance-note">以上四项均为 9 月累计口径（含周末 '+f.wkDays+' 天），'
      +   '单日最高出现在 '+f.mxDate+'。当前速度＝本月累计＋剩余天数×'+(f.cwDays||0)+' 天（9.21—'+f.cutShort+'）日均；上周速度＝本月累计＋剩余天数×上周（9.14—9.20）日均。'
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

  /* ---- 侧栏「9月营收目标进度」：原先写死 59.2% ---- */
  function renderSideGoal(){
    var box=document.querySelector('.side-goal'); if(!box)return;
    var s=src(); if(!s||typeof s.derive!=='function'||!s.rows||!s.rows.length)return;
    var rate=s.derive().amountRate;
    var t=box.querySelector('strong'); if(t)t.textContent=rate.toFixed(1)+'%';
    var b=box.querySelector('.side-goal-track b');
    if(b)b.style.width=Math.min(100,Math.max(0,rate)).toFixed(1)+'%';
    var sm=box.querySelector('small');
    if(sm)sm.textContent='9月营收目标进度（至 '+(mdOf(s.updatedThrough)||'—')+'）';
  }

  function addSidebar(){
    const sidebar=document.querySelector('.sidebar'); if(!sidebar||sidebar.querySelector('.side-pulse')) return;
    const nav=sidebar.querySelector('.nav-label')||sidebar.children[2];
    const box=document.createElement('section'); box.className='side-pulse'; box.innerHTML=`
      <div class="side-pulse-head"><span>经营状态</span><i></i></div>
      <div class="side-goal"><small>9月营收目标进度</small><strong>—</strong><div class="side-goal-track"><b></b></div></div>
      <div class="side-signals"><div class="side-signal risk">目标风险<b>高</b></div><div class="side-signal data">待核验数据<b>17</b></div></div>
      <div class="side-shortcuts"><button data-jump="insights">重大问题</button><button data-jump="departments">部门经营</button></div>`;
    sidebar.insertBefore(box,nav);
    box.addEventListener('click',e=>{const b=e.target.closest('[data-jump]');if(b)document.getElementById(b.dataset.jump)?.scrollIntoView({behavior:'smooth'});});
    renderSideGoal();
  }

  const data={
    entertainment:{title:'工娱组经营详情',metrics:[['患者活动','6场 / 51人'],['家属活动','4场 / 35人'],['合计参与','10场 / 86人'],['场均参与','9人']],rows:[['患者活动','6场','51人','需补效果评价'],['家属活动','4场','35人','需补家属反馈'],['积分兑换','约30人次','—','9月礼品墙已更新']],notes:['主表另有“5场/62人”冲突口径，正式排名前必须核验。','活动需绑定患者ID、执行人、开始结束时间及活动后评估。','停用礼品转节日/活动抽奖，避免库存沉淀。'],source:'原营销模块：工娱活动台账、积分兑换与礼品墙记录'},
    butler:{title:'管家组经营详情',metrics:[['有效接触','80人'],['初诊 / 复诊','21 / 57'],['入院转化','14人'],['住院转化率','17.5%']],rows:[['国威','18','27.8%','重点复盘'],['金林','12','25.0%','小样本'],['朱婧','19','21.1%','较稳定'],['菲菲','15','8.7%','需改善'],['利娟','14','5.0%','需改善']],notes:['业主汇总表 78 条与逐条记录 80 条存在 2 条差异，须以患者级去重清单统一。','本周至今（9.21—9.24）客服随访52条、标记到院18人，到院率34.6%；需继续追踪挂号、治疗、入院和收入。','个人样本仅12—19人，不建议直接用于奖金排名。'],source:'原营销模块：《管家 患者有效对接表》及客服随访台账'},
    channel:{title:'渠道组经营详情',metrics:[['意向机构','3家'],['累计拜访','5客户'],['转介到院','13人'],['教授直转到院','100%']],rows:[['珞康医院','意向','筛查/转介','未签约'],['双福五小','意向','校园合作','未签约'],['双福三小','意向','校园合作','未签约'],['教授直转','执行中','患者转介','到院率100%']],notes:['渠道线索必须从来源标签贯通预约、到院、治疗、入院和收入。','旧表存在机构名单与“2个转化”的冲突记录，需保留版本与核验人。','排名宜看渠道收入、有效转化和回款周期，不能只看拜访次数。'],source:'原营销模块：渠道拜访、机构合作与转介记录'}
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
