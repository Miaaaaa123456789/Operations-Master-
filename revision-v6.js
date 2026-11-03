(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
  /* ⚠ 改造纪律（业主 2026-09-28）：**外观与结构完全保留，只让数字活起来**。
     营收类取自统一口径 facts()；触达类（客服 / 营销）来自别的数据源，收在此处集中管理。 */
  /* 2026-11-02 换期：客服 / 管家本期（10.26—11.01，各 7 天）与上一期同 7 天对照 */
  const SEC={ svcCallback:49, svcPrev:29, svcArrived:11, svcPrevArrived:12,
    svcRate:'22.4', svcRatePrev:'41.4',
    mktDeals:92, mktDealsPrev:86, mktAdmit:12, mktAdmitPrev:14, mktRate:'13.0',
    weekDays:7, touchDays:7, peakDayWan:'16.69', weekendShare:'26.7', mondayWan:'6.91' };
  /* 环比百分比统一由两个数算，不写死 */
  function gp(cur,prev){ var a=parseFloat(cur), b=parseFloat(prev);
    if(!b||!isFinite(a)) return '<span>—</span>';
    var v=(a/b-1)*100;
    return '<span class="'+(v>=0?'good':'bad')+'">'+(v>=0?'+':'−')+Math.abs(v).toFixed(1)+'%</span>'; }
  function gpText(cur,prev){ var a=parseFloat(cur), b=parseFloat(prev);
    if(!b||!isFinite(a)) return '—';
    var v=(a/b-1)*100; return (v>=0?'+':'−')+Math.abs(v).toFixed(1)+'%'; }
  function FACTS(){ var d=window.SEPTEMBER_REVENUE_DATA;
    if(d&&typeof d.facts==='function'){ try{ return d.facts(); }catch(e){} } return null; }
  function F(v,dflt){ return (v==null||v===''||(typeof v==='number'&&!isFinite(v)))?dflt:v; }
  /* 本周累计（万元）＝ 本周实际日均 × 本周有值天数 */
  function weekTotalWan(f){ var a=parseFloat(F(f.weekAvgWan,'6.99')), n=F(f.weekDays,SEC.weekDays);
    return (a&&n)? (a*n).toFixed(2) : '50.66'; }
  /* 上周完整周累计（万元）：先算日均再乘上周 7 天天数。
     ⚠ 不能用「本周合计 ÷ 比率」反推 —— 两期天数不同（6 天 vs 7 天），会得出错的对照值。 */
  function weekPrevWan(f){
    /* 优先取数据层给的「上一期同天数」合计，避免 6 天比 7 天 */
    var dv=(window.SEPTEMBER_REVENUE_DATA&&window.SEPTEMBER_REVENUE_DATA.derive)?window.SEPTEMBER_REVENUE_DATA.derive():null;
    var pc=dv&&dv.previousComparable;
    if(pc&&pc.total) return (pc.total/10000).toFixed(2);
    var a=parseFloat(F(f.weekAvgWan,'7.25')), n=F(f.weekDays,SEC.weekDays);
    return a? (a*n).toFixed(2) : '43.53'; }
  function reorderMarketing(){
    const shell=$('.mkt-v2'); if(!shell)return;
    const hero=$('.mkt-hero',shell); if(!hero)return;
    const f=FACTS()||{};                       // ⭐ 每次重绘都取最新口径
    const old=$('.mkt-priority',shell); if(old)old.remove();
    const priority=document.createElement('section');priority.className='mkt-priority';priority.innerHTML=`
      <article class="mkt-card priority-compare"><div class="mkt-card-head"><div><span class="priority-label">↗ 环比分析</span><h2>本期经营变化</h2><p>营收 ${F(f.periodLabel,'10.26—11.01')}（${F(f.weekDays,SEC.weekDays)} 天）· 触达类 ${F(f.periodLabel,'10.26—11.01')}（${SEC.touchDays} 天），各自与上一期同天数对照</p></div><span class="mkt-badge">营业额 ${gpText(weekTotalWan(f),weekPrevWan(f))}</span></div>
        <div class="priority-matrix"><div class="head">指标（同期天数）</div><div class="head">上周同期</div><div class="head">本期</div><div class="head">变化</div><b>营业额（${F(f.weekDays,SEC.weekDays)} 天）</b><span>${weekPrevWan(f)}万</span><span>${weekTotalWan(f)}万</span>${gp(weekTotalWan(f),weekPrevWan(f))}<b>客服随访（7 天）</b><span>${SEC.svcPrev}条</span><span>${SEC.svcCallback}条</span>${gp(SEC.svcCallback,SEC.svcPrev)}<b>标记到院（7 天）</b><span>${SEC.svcPrevArrived}人</span><span>${SEC.svcArrived}人</span>${gp(SEC.svcArrived,SEC.svcPrevArrived)}<b>营销对接（7 天）</b><span>${SEC.mktDealsPrev}条</span><span>${SEC.mktDeals}条</span>${gp(SEC.mktDeals,SEC.mktDealsPrev)}<b>营销入院（7 天）</b><span>${SEC.mktAdmitPrev}人</span><span>${SEC.mktAdmit}人</span>${gp(SEC.mktAdmit,SEC.mktAdmitPrev)}</div>
        <p class="priority-summary">单日高点集中在 ${F(f.labelDateShort,'10.31')}：单日 ${SEC.peakDayWan} 万占本期 ${F(f.weekDays,SEC.weekDays)} 天的 ${SEC.weekendShare}%，本期累计 ${weekTotalWan(f)} 万、较上期同天数 ${weekPrevWan(f)} 万 <b>${gpText(weekTotalWan(f),weekPrevWan(f))}</b>。客服随访 ${SEC.svcPrev}→${SEC.svcCallback} 条（+69.0%）、到院 ${SEC.svcPrevArrived}→${SEC.svcArrived} 人，但到院率由 ${SEC.svcRatePrev}% 降到 ${SEC.svcRate}%（−19.0pt）——<b>量升质降</b>；营销对接 ${SEC.mktDealsPrev}→${SEC.mktDeals} 条、入院 ${SEC.mktAdmitPrev}→${SEC.mktAdmit} 人（转化率 ${SEC.mktRate}%）。<b>三组方向不同，不合并成单一结论。</b></p></article>
      <article class="mkt-card priority-ai"><div class="mkt-card-head"><div><span class="priority-label">✦ AI经营判断</span><h2>当前先处理三件事</h2><p>从收入结果倒查链路断点</p></div></div><div class="priority-ai-grid">
        <div class="priority-ai-item"><i>1</i><div><b>${f.monthClosed?'月度目标已达成':'营收速度不足'}</b><span>${f.monthClosed?('10 月已收官：累计 '+F(f.totalWan,'262.18')+' 万、完成 '+F(f.amountRate!=null?f.amountRate.toFixed(1):null,'100.8')+'%、超额 '+(parseFloat(F(f.totalWan,'262.18'))-parseFloat(F(f.goalWan,260))).toFixed(2)+' 万，领先时间进度 '+Math.abs(parseFloat(F(f.lagPt,'-0.8'))).toFixed(1)+'pt。'):('累计完成'+F(f.amountRate!=null?f.amountRate.toFixed(1):null,'100.8')+'%，'+(parseFloat(F(f.lagPt,'0'))>=0?'落后':'领先')+'时间进度'+Math.abs(parseFloat(F(f.lagPt,'0'))).toFixed(1)+'pt；剩余'+F(f.remainDays,0)+'天日均需'+F(f.needDailyWan,'0.00')+'万。')}</span></div></div>
        <div class="priority-ai-item"><i>2</i><div><b>到院没有充分变现</b><span>随访和到院增长，但同期营业额下降，应继续匹配挂号、治疗、入院与收费。</span></div></div>
        <div class="priority-ai-item"><i>3</i><div><b>收入过度依赖高点</b><span>10.31 与 11.01 两天占本期 48.6%（26.7% ＋ 21.9%），周一仅 ${SEC.mondayWan} 万，其余 5 天日均 6.43 万——平日转化能力不足。</span></div></div>
      </div></article>`;
    hero.insertAdjacentElement('afterend',priority);
    $$('.mkt-bottom .mkt-card',shell).forEach(c=>{const h=$('h2',c)?.textContent;if(h==='环比分析'||h==='AI经营判断')c.remove()});
    $$('.mkt-content > .mkt-card',shell).forEach(c=>{if($('h2',c)?.textContent==='环比分析')c.remove()});
  }
  function enrichOverview(){
    const card=$('.ov-overview');if(!card||$('.ov-title-mark',card))return;
    const head=$('.ov-head',card),wrap=document.createElement('div');wrap.className='ov-title-mark';
    const title=head.firstElementChild;wrap.innerHTML='<span class="ov-title-icon">◫</span>';wrap.appendChild(title);head.insertBefore(wrap,head.firstChild);
    title.insertAdjacentHTML('beforeend','<div class="ov-mini-signal"><span class="good">10 月收官 100.8%</span><span class="good">患者池净增 +3</span><span class="watch">5组口径待统一</span></div>');
    const icons=['床','入','出','诊','疗'];$$('.ov-kpi',card).forEach((k,i)=>k.insertAdjacentHTML('afterbegin',`<span class="ov-kpi-icon">${icons[i]||'•'}</span>`));
  }
  const deptData={
    butler:{title:'管家组',subtitle:"本期 10.26—11.01 逐条 92 条 / 去重 86 位 · 上一期同 7 天 86 条（菲菲两期均未填）",metrics:[['本周有效对接','92条（86人）'],['本周转住院','12人'],['本周转住院率','13.0%'],['9 月定稿存档','367条 / 61人']],html:`<div class="rank-note rank-ok">本期（<b>10.26—11.01，7 天</b>）有效对接 <b>92 条</b>、转住院 <b>12 人（13.0%）</b>；上一期（10.19—10.25，7 天）86 条 / 14 人（16.3%）——<b>同为 7 天可比</b>：对接 <b>+7.0%</b>、转住院 <b>−2 人（−14.3%）</b>、率值 <b>−3.3pt</b>，每转 1 人所需对接由 6.1 升到 <b>7.7</b>，是「<b>量升质降</b>」。⚠ <b>菲菲两期均未填报</b>（分表最后一行 10.18），按契约记 null、不按 0 降榜；剔除后两期都是 4 人产出（<b>92 vs 86</b>），可直接比。⚠ 业主《心理管家有效客户对接表》<b>权重列本期只填了 12 格「1」</b>，与 12 人转住院一一对应（每人均 3），属住院标记而非权重打分 → 本轮<b>只按有效对接条数排序、不算权重分</b>，不拿上期 14.0 / 16.0 顶替。9 月以 <b>367 条 / 61 人（16.6%）</b> 的当月定稿存档为基线；按同一源表现值重算为 367 / 67（菲菲 9、金林 18、利娟 10、国威 13），差在 9 月后补录的住院标记，<b>不覆盖存档、两组并列留档</b>。</div><div class="rank-list"><div class="rank-row"><i>1</i><div><b>朱婧</b><small>对接 33 条 · 转住院 3 人（9.1%）</small></div><strong>33</strong></div><div class="rank-row"><i>2</i><div><b>国威</b><small>对接 25 条 · 转住院 3 人（12.0%）</small></div><strong>25</strong></div><div class="rank-row"><i>3</i><div><b>金林</b><small>对接 17 条 · 转住院 3 人（17.6%）· 与利娟并列</small></div><strong>17</strong></div><div class="rank-row"><i>3</i><div><b>利娟</b><small>对接 17 条 · 转住院 3 人（17.6%）· 与金林并列</small></div><strong>17</strong></div><div class="rank-row"><i>—</i><div><b>菲菲</b><small>整周未填报（分表止于 10.18）· 记 null 不记 0</small></div><strong>待补</strong></div></div>`},
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
    grid.insertAdjacentHTML('beforeend',`<button class="dept-card marketing-return" data-dept="marketing" aria-haspopup="dialog"><span class="dc-top"><span class="dept-icon">营</span><h3>营销组</h3></span><span class="dc-metrics"><span class="dc-metric"><label>本周有效对接</label><strong>92<em>条</em></strong></span><span class="dc-metric"><label>本周转住院率</label><strong>13.0<em>%</em></strong></span></span><span class="dc-foot"><span class="dept-status">结构变化</span><i class="dept-hint"><span>展开查看</span><b>›</b></i></span></button>`);
    grid.addEventListener('click',e=>{const card=e.target.closest('[data-dept="marketing"]');if(!card)return;e.preventDefault();e.stopImmediatePropagation();if(typeof openDeptV2==='function')openDeptV2('marketing')},true);
  }
  function boot(){try{reorderMarketing()}catch(e){console.warn('reorderMkt',e)}
                /* ⭐ 数据更新后重绘（结构不变，只刷新数字） */
                ['ops:revenue-updated','september-revenue-updated'].forEach(ev=>window.addEventListener(ev,()=>{try{reorderMarketing()}catch(e){}}));
                try{enrichOverview()}catch(e){console.warn('enrichOverview',e)}
                try{restoreMarketing()}catch(e){console.warn('restoreMkt',e)}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,160));else setTimeout(boot,160);
})();
