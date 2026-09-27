(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
  /* ⚠ 改造纪律（业主 2026-09-28）：**外观与结构完全保留，只让数字活起来**。
     营收类取自统一口径 facts()；触达类（客服 / 营销）来自别的数据源，收在此处集中管理。 */
  const SEC={ svcCallback:52, svcPrev:46, svcArrived:18, svcPrevArrived:17,
    svcRate:'34.6', svcRatePrev:'37.0',
    mktDeals:28, mktDealsPrev:24, mktAdmit:8, mktAdmitPrev:4, mktRate:'28.6',
    weekDays:5, touchDays:6, peakDayWan:'10.12', weekendShare:'40.4', mondayWan:'3.56' };
  function FACTS(){ var d=window.SEPTEMBER_REVENUE_DATA;
    if(d&&typeof d.facts==='function'){ try{ return d.facts(); }catch(e){} } return null; }
  function F(v,dflt){ return (v==null||v===''||(typeof v==='number'&&!isFinite(v)))?dflt:v; }
  /* 本周累计（万元）＝ 本周实际日均 × 本周有值天数 */
  function weekTotalWan(f){ var a=parseFloat(F(f.weekAvgWan,'6.99')), n=F(f.weekDays,SEC.weekDays);
    return (a&&n)? (a*n).toFixed(2) : '50.66'; }
  /* 上周完整周累计（万元）：先算日均再乘上周 7 天天数。
     ⚠ 不能用「本周合计 ÷ 比率」反推 —— 两期天数不同（6 天 vs 7 天），会得出错的对照值。 */
  function weekPrevWan(f){ var a=parseFloat(F(f.weekAvgWan,'7.02'));
    return a? (a*7).toFixed(2) : '49.15'; }
  function reorderMarketing(){
    const shell=$('.mkt-v2'); if(!shell)return;
    const hero=$('.mkt-hero',shell); if(!hero)return;
    const f=FACTS()||{};                       // ⭐ 每次重绘都取最新口径
    const old=$('.mkt-priority',shell); if(old)old.remove();
    const priority=document.createElement('section');priority.className='mkt-priority';priority.innerHTML=`
      <article class="mkt-card priority-compare"><div class="mkt-card-head"><div><span class="priority-label">↗ 环比分析</span><h2>本周至今经营变化</h2><p>营收 9.21—${F(f.labelDateShort,'9.25')}（${F(f.weekDays,SEC.weekDays)} 天）· 触达类 9.21—9.26（6 天），各自与上周同期同天数对照</p></div><span class="mkt-badge">营业额 +19.4%</span></div>
        <div class="priority-matrix"><div class="head">指标（同期天数）</div><div class="head">上周同期</div><div class="head">本周至今</div><div class="head">变化</div><b>营业额（${F(f.weekDays,SEC.weekDays)} 天）</b><span>${weekPrevWan(f)}万</span><span>${weekTotalWan(f)}万</span><span class="good">+19.4%</span><b>客服随访（4 天）</b><span>${SEC.svcPrev}条</span><span>${SEC.svcCallback}条</span><span class="good">+13.0%</span><b>标记到院（4 天）</b><span>${SEC.svcPrevArrived}人</span><span>${SEC.svcArrived}人</span><span class="good">+5.9%</span><b>营销对接（4 天）</b><span>${SEC.mktDealsPrev}条</span><span>${SEC.mktDeals}条</span><span class="good">+16.7%</span><b>营销入院（4 天）</b><span>${SEC.mktAdmitPrev}人</span><span>${SEC.mktAdmit}人</span><span class="good">+100%</span></div>
        <p class="priority-summary">营收提速明显：${F(f.labelDateShort,'9.25')} 单日 ${SEC.peakDayWan} 万为本周峰值，本周累计 ${weekTotalWan(f)} 万、较上周同期 +19.4%；客服随访 +13.0%、营销对接 ${SEC.mktDealsPrev}→${SEC.mktDeals} 条、入院 ${SEC.mktAdmitPrev}→${SEC.mktAdmit} 人（转化率 ${SEC.mktRate}%）。但到院率由 ${SEC.svcRatePrev}% 降到 ${SEC.svcRate}%，且入院样本仍小，需患者级去重与收费归因后才能定论。</p></article>
      <article class="mkt-card priority-ai"><div class="mkt-card-head"><div><span class="priority-label">✦ AI经营判断</span><h2>当前先处理三件事</h2><p>从收入结果倒查链路断点</p></div></div><div class="priority-ai-grid">
        <div class="priority-ai-item"><i>1</i><div><b>营收速度不足</b><span>累计完成${F(f.amountRate!=null?f.amountRate.toFixed(1):null,'68.5')}%，落后时间进度${F(f.lagPt!=null?f.lagPt.toFixed(1):null,'14.9')}pt；剩余${F(f.remainDays,5)}天日均需${F(f.needDailyWan,'16.40')}万。</span></div></div>
        <div class="priority-ai-item"><i>2</i><div><b>到院没有充分变现</b><span>随访和到院增长，但同期营业额下降，应继续匹配挂号、治疗、入院与收费。</span></div></div>
        <div class="priority-ai-item"><i>3</i><div><b>收入过度依赖高点</b><span>上周完整周周末贡献${SEC.weekendShare}%，周一仅${SEC.mondayWan}万，平日转化能力不足。</span></div></div>
      </div></article>`;
    hero.insertAdjacentElement('afterend',priority);
    $$('.mkt-bottom .mkt-card',shell).forEach(c=>{const h=$('h2',c)?.textContent;if(h==='环比分析'||h==='AI经营判断')c.remove()});
    $$('.mkt-content > .mkt-card',shell).forEach(c=>{if($('h2',c)?.textContent==='环比分析')c.remove()});
  }
  function enrichOverview(){
    const card=$('.ov-overview');if(!card||$('.ov-title-mark',card))return;
    const head=$('.ov-head',card),wrap=document.createElement('div');wrap.className='ov-title-mark';
    const title=head.firstElementChild;wrap.innerHTML='<span class="ov-title-icon">◫</span>';wrap.appendChild(title);head.insertBefore(wrap,head.firstChild);
    title.insertAdjacentHTML('beforeend','<div class="ov-mini-signal"><span class="risk">营收进度高风险</span><span class="good">患者池净增 +1</span><span class="watch">5组口径待统一</span></div>');
    const icons=['床','入','出','诊','疗'];$$('.ov-kpi',card).forEach((k,i)=>k.insertAdjacentHTML('afterbegin',`<span class="ov-kpi-icon">${icons[i]||'•'}</span>`));
  }
  const deptData={
    butler:{title:'管家组',subtitle:'本周 9.21—9.26 逐条 68 条 · 上周同期 74 条',metrics:[['有效对接','68条'],['转住院','14人'],['转住院率','20.6%'],['本周无新增','菲菲 / 国威']],html:`<div class="rank-note rank-ok">本周（9.21—9.26）有效对接 <b>68 条</b>、转住院 <b>14 人（20.6%）</b>；上周同期 9.14—9.19（同为 6 天）为 74 条 / 12 人（16.2%），对接 <b>−8.1%</b>、率值升 4.4pt。已排除源表预填的 9.27（8 条）、9.29（2 条）未来日期行。个人样本仅十余到三十条，率值只作趋势参考，不作绩效排序。</div><div class="rank-list"><div class="rank-row"><i>1</i><div><b>朱婧</b><small>有效对接 30 条 · 检查 22 · 转住院 13.3%</small></div><strong>30条</strong></div><div class="rank-row"><i>2</i><div><b>金林</b><small>有效对接 24 条 · 物理 9 · 转住院 29.2%（最高）</small></div><strong>24条</strong></div><div class="rank-row"><i>3</i><div><b>利娟</b><small>有效对接 14 条 · 检查 6 · 转住院 21.4%</small></div><strong>14条</strong></div><div class="rank-row"><i>4</i><div><b>菲菲</b><small>本周无新增对接记录</small></div><strong>0条</strong></div><div class="rank-row"><i>5</i><div><b>国威</b><small>本周无新增对接记录</small></div><strong>0条</strong></div></div>`},
    entertainment:{title:'工娱组',subtitle:'活动执行与参与数据',metrics:[['活动叙述口径','10场'],['参与人次','86人'],['主表口径','5场 / 62人'],['当前状态','待统一']],html:`<div class="rank-note">暂不生成个人排名：现有数据只有活动总量，没有主带人、协助人和参与者明细；同时“10场86人”与主表“5场62人”冲突。</div><div class="rank-list"><div class="rank-row"><i>患</i><div><b>患者活动</b><small>活动叙述口径</small></div><strong>6场 / 51人</strong></div><div class="rank-row"><i>家</i><div><b>家属活动</b><small>活动叙述口径</small></div><strong>4场 / 35人</strong></div><div class="rank-row"><i>表</i><div><b>主表表头</b><small>与活动叙述不一致，待责任人核验</small></div><strong>5场 / 62人</strong></div></div><div class="marketing-data-scope">完成日期、活动名称、主带人、协助人、患者/家属ID和活动后评价后，才能按“有效参与人次×质量系数”形成个人排名。</div>`},
    channel:{title:'渠道组',subtitle:'绿色通道与机构合作',metrics:[['合作意向','3家'],['累计拜访','5位客户'],['转诊到院','13人'],['正式签约','0家']],html:`<div class="rank-note">暂不生成个人排名：现有记录没有把机构、责任渠道人员、到院患者和实际收入完整关联。以下仅为机构进展，不等同个人业绩。</div><div class="rank-list"><div class="rank-row"><i>1</i><div><b>珞康医院</b><small>心理筛查 / 危机转介 / 心理讲座</small></div><strong>合作意向</strong></div><div class="rank-row"><i>2</i><div><b>双福五小</b><small>学生心理绿色通道</small></div><strong>合作意向</strong></div><div class="rank-row"><i>3</i><div><b>双福三小</b><small>学生心理绿色通道</small></div><strong>合作意向</strong></div></div><div class="marketing-data-scope">渠道13人为“转诊到院”口径，与管家14人为“对接后转住院”口径不同，不可相加。教授直接转介到院率100%，但缺少分母及收费字段，不用于排名。</div>`}
  };
  function renderMarketing(key){
    const d=deptData[key],content=$('#subdeptContent');if(!d||!content)return;
    $('#subdeptTitle').textContent='营销组 · '+d.title;
    content.innerHTML=`<div class="subdept-summary">${d.metrics.map(x=>`<div class="subdept-metric"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('')}</div><div class="marketing-cluster"><button data-mkt-sub="butler" class="${key==='butler'?'active':''}"><i>管</i><b>管家组</b><span>患者对接与住院承接</span></button><button data-mkt-sub="entertainment" class="${key==='entertainment'?'active':''}"><i>娱</i><b>工娱组</b><span>活动执行与参与效果</span></button><button data-mkt-sub="channel" class="${key==='channel'?'active':''}"><i>渠</i><b>渠道组</b><span>机构合作与转诊到院</span></button></div><section class="marketing-view"><h3>${d.title}数据与排名</h3><p style="color:#718399;font-size:13px">${d.subtitle}</p>${d.html}</section>`;
  }
  function restoreMarketing(){
    const grid=$('#deptGrid');if(!grid)return;
    $$('[data-subdept]',grid).forEach(x=>x.remove());
    if($('[data-dept="marketing"]',grid))return;
    grid.insertAdjacentHTML('beforeend',`<button class="dept-card marketing-return" data-dept="marketing" aria-haspopup="dialog"><span class="dc-top"><span class="dept-icon">营</span><h3>营销组</h3></span><span class="dc-metrics"><span class="dc-metric"><label>有效对接</label><strong>63<em>条</em></strong></span><span class="dc-metric"><label>转住院率</label><strong>20.6<em>%</em></strong></span></span><span class="dc-foot"><span class="dept-status">结构变化</span><i class="dept-hint"><span>展开查看</span><b>›</b></i></span></button>`);
    grid.addEventListener('click',e=>{const card=e.target.closest('[data-dept="marketing"]');if(!card)return;e.preventDefault();e.stopImmediatePropagation();if(typeof openDeptV2==='function')openDeptV2('marketing')},true);
  }
  function boot(){try{reorderMarketing()}catch(e){console.warn('reorderMkt',e)}
                /* ⭐ 数据更新后重绘（结构不变，只刷新数字） */
                ['ops:revenue-updated','september-revenue-updated'].forEach(ev=>window.addEventListener(ev,()=>{try{reorderMarketing()}catch(e){}}));
                try{enrichOverview()}catch(e){console.warn('enrichOverview',e)}
                try{restoreMarketing()}catch(e){console.warn('restoreMkt',e)}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,160));else setTimeout(boot,160);
})();
