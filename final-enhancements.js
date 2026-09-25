(function(){
  function addSidebar(){
    const sidebar=document.querySelector('.sidebar'); if(!sidebar||sidebar.querySelector('.side-pulse')) return;
    const nav=sidebar.querySelector('.nav-label')||sidebar.children[2];
    const box=document.createElement('section'); box.className='side-pulse'; box.innerHTML=`
      <div class="side-pulse-head"><span>经营状态</span><i></i></div>
      <div class="side-goal"><small>9月营收目标进度</small><strong>59.2%</strong><div class="side-goal-track"><b></b></div></div>
      <div class="side-signals"><div class="side-signal risk">目标风险<b>高</b></div><div class="side-signal data">待核验数据<b>17</b></div></div>
      <div class="side-shortcuts"><button data-jump="insights">重大问题</button><button data-jump="departments">部门经营</button></div>`;
    sidebar.insertBefore(box,nav);
    box.addEventListener('click',e=>{const b=e.target.closest('[data-jump]');if(b)document.getElementById(b.dataset.jump)?.scrollIntoView({behavior:'smooth'});});
  }
  function addFinance(){
    const root=document.querySelector('.mkt-v2'); if(!root||root.querySelector('.finance-board')) return;
    const anchor=root.querySelector('.mkt-detail-grid')||root.lastElementChild;
    const parent=anchor?anchor.parentElement:root;
    const el=document.createElement('section'); el.className='finance-board'; el.innerHTML=`
      <div class="finance-head"><div><h3>财务经营分析 · Finance View</h3><p>从预算差异、运行速度、收入结构与情景预测判断经营质量</p></div><span class="finance-tag">数据截至 9月24日（营收 9月22日）</span></div>
      <div class="finance-kpis">
        <div class="finance-kpi bad"><span>预算缺口</span><strong>−106.11万</strong><em>目标 260万</em></div>
        <div class="finance-kpi warn"><span>达标所需日均</span><strong>13.26万</strong><em>剩余 8 天</em></div>
        <div class="finance-kpi"><span>基准情景预测</span><strong>210.05万</strong><em>按上周日均 7.02万</em></div>
        <div class="finance-kpi bad"><span>预测目标差额</span><strong>−49.95万</strong><em>基准情景</em></div>
        <div class="finance-kpi warn"><span>所需提速</span><strong>+88.9%</strong><em>相较上周日均</em></div>
      </div>
      <div class="finance-body">
        <div class="scenario"><h4>月末营收情景测算</h4>
          <div class="scenario-row"><span>当前速度</span><div class="scenario-bar"><i style="width:75.9%"></i></div><b>197.33</b></div>
          <div class="scenario-row"><span>上周速度</span><div class="scenario-bar"><i style="width:80.8%"></i></div><b>210.05</b></div>
          <div class="scenario-row goal"><span>月度目标</span><div class="scenario-bar"><i style="width:100%"></i></div><b>260.00</b></div>
        </div>
        <div class="quality"><h4>收入质量观察</h4><div class="quality-grid">
          <div class="quality-item"><small>门诊收入占比</small><b>55.1%</b></div><div class="quality-item"><small>住院收入占比</small><b>44.9%</b></div>
          <div class="quality-item"><small>周末贡献</small><b>40.4%</b></div><div class="quality-item"><small>单日最高占比</small><b>28.0%</b></div>
        </div><div class="finance-note">成本、折扣退费、应收账款尚未接入，因此暂不能严谨计算利润率、毛利率与现金流。</div></div>
      </div>`;
    if(parent)parent.insertBefore(el,anchor);else root.appendChild(el);
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
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,80));else setTimeout(boot,80);
})();
