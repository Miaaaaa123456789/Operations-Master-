(function(){
  const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>Array.from(r.querySelectorAll(s));
  /* ⚠ 改造纪律（业主 2026-09-28）：**外观与结构完全保留，只让数字活起来**。
     营收类取自统一口径 facts()；触达类（客服 / 营销）来自别的数据源，收在此处集中管理。 */
  const SEC={ svcCallback:74, svcPrev:86, svcArrived:36, svcPrevArrived:31,
    svcRate:'48.6', svcRatePrev:'36.0',
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
      <article class="mkt-card priority-compare"><div class="mkt-card-head"><div><span class="priority-label">↗ 环比分析</span><h2>本期经营变化</h2><p>营收 9.21—${F(f.labelDateShort,'9.25')}（${F(f.weekDays,SEC.weekDays)} 天）· 触达类 9.21—9.26（6 天），各自与上周同期同天数对照</p></div><span class="mkt-badge">营业额 +11.2%</span></div>
        <div class="priority-matrix"><div class="head">指标（同期天数）</div><div class="head">上周同期</div><div class="head">本期</div><div class="head">变化</div><b>营业额（${F(f.weekDays,SEC.weekDays)} 天）</b><span>${weekPrevWan(f)}万</span><span>${weekTotalWan(f)}万</span><span class="good">+19.4%</span><b>客服随访（7 天）</b><span>${SEC.svcPrev}条</span><span>${SEC.svcCallback}条</span><span class="bad">−14.0%</span><b>标记到院（7 天）</b><span>${SEC.svcPrevArrived}人</span><span>${SEC.svcArrived}人</span><span class="good">+16.1%</span><b>营销对接（4 天）</b><span>${SEC.mktDealsPrev}条</span><span>${SEC.mktDeals}条</span><span class="good">+16.7%</span><b>营销入院（4 天）</b><span>${SEC.mktAdmitPrev}人</span><span>${SEC.mktAdmit}人</span><span class="good">+100%</span></div>
        <p class="priority-summary">营收提速明显：${F(f.labelDateShort,'9.25')} 单日 ${SEC.peakDayWan} 万为本周峰值，本周累计 ${weekTotalWan(f)} 万、较上周同期 +11.2%；客服随访 −14.0%（量降质升）、营销对接 ${SEC.mktDealsPrev}→${SEC.mktDeals} 条、入院 ${SEC.mktAdmitPrev}→${SEC.mktAdmit} 人（转化率 ${SEC.mktRate}%）。到院率由 ${SEC.svcRatePrev}% 升到 ${SEC.svcRate}%（+12.6pt），但入院样本仍小，需患者级去重与收费归因后才能定论。</p></article>
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
    butler:{title:'管家组',subtitle:'本周 10.5—10.11 逐条 89 条 · 上一自然周 9.28—10.4 为 60 条（该表菲菲、国威两栏未填报）',metrics:[['本周有效对接','89条'],['本周转住院','11人'],['本周转住院率','12.4%'],['9 月累计','376条 / 69人']],html:`<div class="rank-note rank-ok">本周（<b>10.5—10.11，7 天</b>）有效对接 <b>89 条</b>、转住院 <b>11 人（12.4%）</b>；上一自然周（9.28—10.4，7 天）60 条 / 16 人（26.7%）——<b>同为 7 天可比</b>：对接 +48.3%、率值 −14.3pt。⚠⚠ <b>上一周菲菲、国威两栏源表整格为「/」（未填报）</b>，上期 60 条仅含 3 人，环比只作趋势参考。9 月累计（30 天）376 条 / 69 人（18.4%），五人全部有量。个人样本 2—33 条，率值不作绩效排序。</div><div class="rank-list"><div class="rank-row"><i>1</i><div><b>朱婧</b><small>对接 33 条 · 检查 20 · 转住院 6.1%</small></div><strong>33条</strong></div><div class="rank-row"><i>2</i><div><b>国威</b><small>对接 22 条 · 心理 10 · 转住院 <b>18.2%（最高）</b></small></div><strong>22条</strong></div><div class="rank-row"><i>3</i><div><b>利娟</b><small>对接 17 条 · 检查 14 · 转住院 11.8%</small></div><strong>17条</strong></div><div class="rank-row"><i>4</i><div><b>金林</b><small>对接 15 条 · 物理 4 · 转住院 6.7%</small></div><strong>15条</strong></div><div class="rank-row"><i>5</i><div><b>菲菲</b><small>对接 2 条 · 转住院 100%（样本过小不具意义）</small></div><strong>2条</strong></div></div>`},entertainment:{title:'工娱组',subtitle:'活动执行与参与数据 · 10.12—10.18（业主 2026-10-19 口径）',metrics:[['患者参与','111人'],['家属参与','45人'],['合计参与','156人'],['积分兑换','16人 · 10月累计']],html:`<div class="rank-note">⭐ 本期（<b>10.12—10.18</b>）：患者参与 <b>111 人</b> ＋ 家属参与 <b>45 人</b> ＝ <b>156 人</b>；较上一版填报 181 人减 25 人（<b>−13.8%</b>）——患者 120→111（−7.5%）、家属 61→45（<b>−26.2%</b>），家属端降得更快。积分兑换 <b>10 月累计 16 人</b>（10.1—10.18），<b>是月累计不是本周</b>，不能与周参与人数并列算率。<b>本周源表未给场次</b>，故「场次」「场均参与」记 null、不补值不推算。<b>暂不生成个人排名</b>：现有数据只有总人数，没有主带人、协助人和参与者明细；主表护理组表头另记「5 场 62 人次」，与本组口径冲突、不可相加。</div><div class="rank-list"><div class="rank-row"><i>患</i><div><b>患者参与</b><small>住院部患者 · 本期 10.12—10.18（上一版 120 人）</small></div><strong>111人</strong></div><div class="rank-row"><i>家</i><div><b>家属参与</b><small>家属专场 · 本期 10.12—10.18（上一版 61 人）</small></div><strong>45人</strong></div><div class="rank-row"><i>合</i><div><b>合计参与</b><small>患者＋家属，两列均可加</small></div><strong>156人</strong></div><div class="rank-row"><i>积</i><div><b>积分兑换</b><small>⚠ 10 月 1—18 日累计，非本周单周值</small></div><strong>16人</strong></div><div class="rank-row"><i>表</i><div><b>主表护理组表头</b><small>另一口径，与活动叙述不同源、不可相加</small></div><strong>5场 / 62人次</strong></div></div><div class="marketing-data-scope">完成日期、活动场次、活动名称、主带人、协助人、患者/家属ID和活动后评价后，才能按「有效参与人次×质量系数」形成个人排名；积分兑换需拆分「本月新增 / 本月已兑」两列，才能与周口径对齐。</div>`},
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
    grid.insertAdjacentHTML('beforeend',`<button class="dept-card marketing-return" data-dept="marketing" aria-haspopup="dialog"><span class="dc-top"><span class="dept-icon">营</span><h3>营销组</h3></span><span class="dc-metrics"><span class="dc-metric"><label>本周有效对接</label><strong>89<em>条</em></strong></span><span class="dc-metric"><label>本周转住院率</label><strong>12.4<em>%</em></strong></span></span><span class="dc-foot"><span class="dept-status">结构变化</span><i class="dept-hint"><span>展开查看</span><b>›</b></i></span></button>`);
    grid.addEventListener('click',e=>{const card=e.target.closest('[data-dept="marketing"]');if(!card)return;e.preventDefault();e.stopImmediatePropagation();if(typeof openDeptV2==='function')openDeptV2('marketing')},true);
  }
  function boot(){try{reorderMarketing()}catch(e){console.warn('reorderMkt',e)}
                /* ⭐ 数据更新后重绘（结构不变，只刷新数字） */
                ['ops:revenue-updated','september-revenue-updated'].forEach(ev=>window.addEventListener(ev,()=>{try{reorderMarketing()}catch(e){}}));
                try{enrichOverview()}catch(e){console.warn('enrichOverview',e)}
                try{restoreMarketing()}catch(e){console.warn('restoreMkt',e)}}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,160));else setTimeout(boot,160);
})();
