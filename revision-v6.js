(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
  function reorderMarketing(){
    const shell=$('.mkt-v2'); if(!shell||$('.mkt-priority',shell))return;
    const hero=$('.mkt-hero',shell); if(!hero)return;
    const priority=document.createElement('section');priority.className='mkt-priority';priority.innerHTML=`
      <article class="mkt-card priority-compare"><div class="mkt-card-head"><div><span class="priority-label">↗ 环比分析</span><h2>本周至今经营变化</h2><p>9.21—9.24 与上周同期 9.14—9.17 同口径（各 4 天；营业额为 2 天口径）</p></div><span class="mkt-badge">营业额 −4.6%</span></div>
        <div class="priority-matrix"><div class="head">指标（同期天数）</div><div class="head">上周同期</div><div class="head">本周至今</div><div class="head">变化</div><b>营业额（2 天）</b><span>11.39万</span><span>10.86万</span><span class="bad">−4.6%</span><b>客服随访（4 天）</b><span>46条</span><span>52条</span><span class="good">+13.0%</span><b>标记到院（4 天）</b><span>17人</span><span>18人</span><span class="good">+5.9%</span><b>营销对接（4 天）</b><span>24条</span><span>28条</span><span class="good">+16.7%</span><b>营销入院（4 天）</b><span>4人</span><span>8人</span><span class="good">+100%</span></div>
        <p class="priority-summary">前端触达增加，但收入没有同步增长；营销对接 24→28 条、入院 4→8 人、转化率 28.6%，回升明显但仍属小样本，需患者级去重与收费归因后才能定论。</p></article>
      <article class="mkt-card priority-ai"><div class="mkt-card-head"><div><span class="priority-label">✦ AI经营判断</span><h2>当前先处理三件事</h2><p>从收入结果倒查链路断点</p></div></div><div class="priority-ai-grid">
        <div class="priority-ai-item"><i>1</i><div><b>营收速度不足</b><span>累计完成59.2%，落后时间进度14.1pt；剩余8天日均需13.26万。</span></div></div>
        <div class="priority-ai-item"><i>2</i><div><b>到院没有充分变现</b><span>随访和到院增长，但同期营业额下降，应继续匹配挂号、治疗、入院与收费。</span></div></div>
        <div class="priority-ai-item"><i>3</i><div><b>收入过度依赖高点</b><span>上周完整周周末贡献40.4%，周一仅3.56万，平日转化能力不足。</span></div></div>
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
    butler:{title:'管家组',subtitle:'本周 9.21—9.27 逐条 47 条 · 上周 80 条',metrics:[['有效对接','47条'],['转住院','11人'],['转住院率','23.4%'],['本周无新增','菲菲 / 国威']],html:`<div class="rank-note rank-ok">本周（9.21—9.27）有效对接 <b>47 条</b>、转住院 <b>11 人（23.4%）</b>；上周 9.14—9.20 为 80 条 / 14 人（17.5%），对接环比 <b>-41.2%</b>。个人样本仅十余条，率值只作趋势参考，不作绩效排序。</div><div class="rank-list"><div class="rank-row"><i>1</i><div><b>朱婧</b><small>有效对接 17 条 · 检查 10 · 转住院 11.8%</small></div><strong>17条</strong></div><div class="rank-row"><i>2</i><div><b>金林</b><small>有效对接 16 条 · 物理 9 · 转住院 43.8%（最高）</small></div><strong>16条</strong></div><div class="rank-row"><i>3</i><div><b>利娟</b><small>有效对接 14 条 · 检查 4 · 转住院 14.3%</small></div><strong>14条</strong></div><div class="rank-row"><i>4</i><div><b>菲菲</b><small>本周无新增对接记录</small></div><strong>0条</strong></div><div class="rank-row"><i>5</i><div><b>国威</b><small>本周无新增对接记录</small></div><strong>0条</strong></div></div>`},
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
    grid.insertAdjacentHTML('beforeend',`<button class="dept-card marketing-return" data-dept="marketing" aria-haspopup="dialog"><span class="dc-top"><span class="dept-icon">营</span><h3>营销组</h3></span><span class="dc-metrics"><span class="dc-metric"><label>有效对接</label><strong>47<em>条</em></strong></span><span class="dc-metric"><label>转住院率</label><strong>23.4<em>%</em></strong></span></span><span class="dc-foot"><span class="dept-status">结构变化</span><i class="dept-hint"><span>展开查看</span><b>›</b></i></span></button>`);
    grid.addEventListener('click',e=>{const card=e.target.closest('[data-dept="marketing"]');if(!card)return;e.preventDefault();e.stopImmediatePropagation();if(typeof openDeptV2==='function')openDeptV2('marketing')},true);
  }
  function boot(){try{reorderMarketing()}catch(e){console.warn('reorderMkt',e)}
                try{enrichOverview()}catch(e){console.warn('enrichOverview',e)}
                try{restoreMarketing()}catch(e){console.warn('restoreMkt',e)}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,160));else setTimeout(boot,160);
})();
