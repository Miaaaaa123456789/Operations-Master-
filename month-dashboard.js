(function(){
  'use strict';

  var WEEK='本周（9.21—9.27）';
  var baseData={
    meta:{range:'9月1日—9月27日（报告期）',updated:'数据截至 2026年9月25日 23:59'},
    kpis:[
      {label:'9月累计营业额',value:'178.00',unit:'万元',note:'截至 9.25 · 完成目标 68.5%'},
      {label:WEEK+'营业额',value:'34.97',unit:'万元',note:'截至 9.25 · 日均 6.99 万'},
      {label:'在院人数',value:'31',unit:'人',note:'9.25 日终时点'},
      {label:WEEK+'入院',value:'13',unit:'人',note:'9.21—9.25 已发生'},
      {label:WEEK+'出院',value:'9',unit:'人',note:'初次 8＋多次 1'},
      {label:'物理治疗',value:'459',unit:'人次',note:'上周完整周'}
    ],
    target:{actual:178.00,goal:260,amountRate:68.5,timeRate:83.3,gap:14.9,days:5,remaining:82.00,requiredDaily:16.40,currentDaily:6.99,dailyGap:9.41},
    alerts:[
      {tone:'red',icon:'↘',tag:'高风险',title:'营收速度不足',copy:'截至9月25日时间进度83.3%，金额完成68.5%，剩余5天日均需16.40万元。'},
      {tone:'orange',icon:'↗',tag:'改善信号',title:'营业额连续5日上升',copy:'从9月21日5.33万元升至9月25日10.12万元，但仍低于达标所需日均。'},
      {tone:'purple',icon:'＋',tag:'患者池增长',title:'本周净增4人',copy:'入院13人、出院9人，9月25日日终在院31人。'},
      {tone:'blue',icon:'…',tag:'数据待补',title:'周末两天尚未更新',copy:'9月26—27日显示待更新，不以0计入营业额或患者流动。'}
    ],
    daily:[
      {d:'9.21',v:5.329033},{d:'9.22',v:5.530381},{d:'9.23',v:6.245896},{d:'9.24',v:7.746587},{d:'9.25',v:10.118749},{d:'9.26',v:null},{d:'9.27',v:null}
    ],
    weeks:[
      {label:'9.1—9.6',value:37.88},{label:'9.7—9.13',value:56.00},{label:'9.14—9.20',value:49.15},{label:'9.21—9.27',value:34.97,current:true}
    ],
    funnel:[
      {label:'门诊',value:'141人次'},{label:'入院',value:'13人'},{label:'出院',value:'9人'},{label:'在院',value:'31人'}
    ],
    departments:[
      {key:'doctor',cls:'doctor',icon:'医',name:'医生组',desc:'住院规模与管床贡献',metric:'31 人',note:'在院 · 9.25 时点',foot:'本周入院 13 · 出院 9'},
      {key:'nursing',cls:'nursing',icon:'护',name:'护理组',desc:'治疗执行与服务兑现',metric:'94.1%',note:'物理治疗完成率（项目口径）',foot:'应做 488 · 未做 29'},
      {key:'psychology',cls:'psychology',icon:'心',name:'心理咨询组',desc:'咨询承接与收入结构',metric:'37 人次',note:WEEK+'患者接触',foot:'上周接触 40（−7.5%）'},
      {key:'service',cls:'service',icon:'客',name:'客服服务部',desc:'随访、到院及付费跟踪',metric:'52 条',note:WEEK+'回访台账',foot:'到院 18 · 34.6%'},
      {key:'marketing',cls:'marketing',icon:'营',name:'营销组',desc:'管家、工娱与渠道归集',metric:'34.97万',note:WEEK+'营业额',foot:'入院 13 · 出院 9'}
    ],
    ranks:{
      doctor:[['康言','医生组','出院费用 19.64 万（8 人次）','出院结帐明细 9.1—9.24','动态试算'],['王建林','医生组','出院费用 15.98 万（9 人次）','出院结帐明细 9.1—9.24','动态试算'],['曾凯','医生组','出院费用 15.84 万（11 人次，人次第 1）','出院结帐明细 9.1—9.24','动态试算'],['王建','医生组','出院费用 12.74 万（7 人次）','出院结帐明细 9.1—9.24','动态试算'],['赵郁莹','医生组','出院费用 11.17 万（6 人次）','出院结帐明细 9.1—9.24','动态试算']],
      nursing:[['何培培','护理组','综合 0.9432 · 周总 24.93','工作量×质控（源表口径）','动态试算'],['李永鑫','护理组','综合 0.9406 · 周总 25.68','工作量×质控（源表口径）','动态试算'],['沈琳','护理组','综合 0.8764','工作量×质控（源表口径）','动态试算'],['刘佳佳','护理组','综合 0.8640','工作量×质控（源表口径）','动态试算'],['赵雯倩','护理组','综合 0.8596','工作量×质控（源表口径）','动态试算']],
      psychology:[['冯浩鹏','心理咨询组','接触 14 · 咨询 7','V4 日报 9.21—9.26','动态试算'],['蔡宜蓉','心理咨询组','接触 13 · 咨询 11','V4 日报 9.21—9.26','动态试算'],['赵芳','心理咨询组','接触 5 · 咨询 1','V4 日报 9.21—9.26','动态试算'],['杨霞','心理咨询组','接触 4','V4 日报 9.21—9.26','动态试算'],['陈鹏','心理咨询组','接触 1','V4 日报 9.21—9.26','动态试算']],
      service:[['蒋雨','客服服务部','日均 319.3 分 · 回访 29 条','日工作量（按日均）','动态试算'],['温诗怡','客服服务部','日均 123.0 分 · 回访 7 条','日工作量（按日均）','动态试算'],['陈宇轩','客服服务部','日均 119.0 分 · 主动服务 8 条','日工作量（按日均）','动态试算'],['黄诗棋','客服服务部','日均 113.7 分','日工作量（按日均）','动态试算'],['张钰洁','客服服务部','日均 105.3 分','日工作量（按日均）','动态试算']],
      marketing:[['金林','营销组','转住院率 29.2%','对接 24 条','趋势参考'],['利娟','营销组','转住院率 23.1%','对接 13 条','趋势参考'],['朱婧','营销组','转住院率 11.5%','对接 26 条','趋势参考'],['菲菲','营销组','本周无新增对接','—','待核'],['国威','营销组','本周无新增对接','—','待核']]
    }
  };

  function applyRevenueSnapshot(){
    var source=window.SEPTEMBER_REVENUE_DATA;if(!source||!source.derive)return;
    var x=source.derive(),m=x.month,w=x.currentWeek,last=source.rows[source.rows.length-1],fmt=function(v){return (v/10000).toFixed(2);},dis=w.discharges;
    var md=function(d){return d?(+d.slice(5,7))+'月'+(+d.slice(8))+'日':'';};
    baseData.meta={range:'9月1日—9月27日（报告期）',updated:'数据截至 '+source.updatedAt};
    baseData.kpis=[
      {label:'9月累计营业额',value:fmt(m.total),unit:'万元',note:'截至 '+md(last.date)+' · 完成目标 '+x.amountRate.toFixed(1)+'%'},
      {label:WEEK+'营业额',value:fmt(w.total),unit:'万元',note:'截至 '+md(last.date)+' · 日均 '+fmt(w.average)+' 万'},
      {label:'在院人数',value:String(last.ward),unit:'人',note:md(last.date)+' 日终时点'},
      {label:WEEK+'入院',value:String(w.admissions),unit:'人',note:'9.21—'+md(last.date)+' 已发生'},
      {label:WEEK+'出院',value:String(dis),unit:'人',note:'初次 8＋多次 1'},
      {label:'9月门诊人次',value:String(m.visits),unit:'人次',note:'初诊 '+m.first+'＋复诊 '+m.repeat}
    ];
    baseData.target={actual:Number(fmt(m.total)),goal:260,amountRate:Number(x.amountRate.toFixed(1)),timeRate:Number(x.timeRate.toFixed(1)),gap:Number((x.timeRate-x.amountRate).toFixed(1)),days:x.remainingDays,remaining:Number(fmt(x.remaining)),requiredDaily:Number(fmt(x.requiredDaily)),currentDaily:Number(fmt(w.average)),dailyGap:Number(fmt(x.requiredDaily-w.average))};
    baseData.alerts=[
      {tone:'red',icon:'↘',tag:'高风险',title:'营收速度不足',copy:'截至'+md(last.date)+'金额完成'+x.amountRate.toFixed(1)+'%，落后时间进度'+(x.timeRate-x.amountRate).toFixed(1)+'个百分点，剩余日均需'+fmt(x.requiredDaily)+'万元。'},
      {tone:'orange',icon:'◆',tag:'结构风险',title:'收入集中在少数高峰日',copy:'9月6、13、19日三天贡献约27.3%，周末日均'+fmt(x.weekend.average)+'万元，平日日均'+fmt(x.weekday.average)+'万元。'},
      {tone:'purple',icon:'＋',tag:'改善信号',title:'本周患者池净增4人',copy:'入院'+w.admissions+'人、出院'+dis+'人，9月25日日终在院'+last.ward+'人。'},
      {tone:'blue',icon:'✓',tag:'已核验',title:'25天累计连续勾稽',copy:'9月1—'+md(last.date)+'每日合计与累计连续一致；9月1—6日采用后续修订口径，9月26—27日待更新。'}
    ];
    /* ⚠ 待补日不能硬编码 9.26/9.27：数据真到 9.26 后会重复出现两根「待更新」柱。
       改为「本周 9.21—9.27 中数据里缺的那几天」，并把日期格式统一成 09.xx（与已有柱一致）。 */
    var _have={};source.rows.forEach(function(r){_have[r.date]=1;});
    var _pend=[];for(var _d=21;_d<=27;_d++){var _k='2026-09-'+String(_d).padStart(2,'0');if(!_have[_k])_pend.push({d:_k.slice(5).replace('-','.'),v:null});}
    baseData.daily=source.rows.filter(function(r){return r.date>='2026-09-21';}).map(function(r){return {d:r.date.slice(5).replace('-','.'),v:r.total/10000};}).concat(_pend);
    baseData.weeks=x.weeks.map(function(q,i){return {label:q.label,value:q.total/10000,current:i===3};});
    baseData.funnel=[{label:'门诊',value:w.visits+'人次'},{label:'入院',value:w.admissions+'人'},{label:'出院',value:dis+'人'},{label:'在院',value:last.ward+'人'}];
    baseData.departments[4].metric=fmt(w.total)+'万';baseData.departments[4].foot='入院 '+w.admissions+' · 出院 '+dis;
  }
  applyRevenueSnapshot();

  function clone(o){return JSON.parse(JSON.stringify(o));}
  function merge(a,b){Object.keys(b||{}).forEach(function(k){if(b[k]&&typeof b[k]==='object'&&!Array.isArray(b[k])&&a[k]&&typeof a[k]==='object'&&!Array.isArray(a[k])) merge(a[k],b[k]);else a[k]=b[k];});return a;}
  var saved={};
  try{saved=JSON.parse(localStorage.getItem('hospital-month-dashboard-v3-20260926')||'{}');}catch(e){}
  var data=merge(clone(baseData),saved);
  window.MONTH_DASHBOARD_DATA=data;

  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
  function n(v){return typeof v==='number'?v:parseFloat(v)||0;}
  function lastDateMd(){var src=window.SEPTEMBER_REVENUE_DATA;if(!src||!src.rows||!src.rows.length)return '';var d=src.rows[src.rows.length-1].date;return (+d.slice(5,7))+'月'+(+d.slice(8))+'日';}
  function mascotSrc(){var x=document.querySelector('.hero-mascot img,.hero-mascot,.mascot img,.mascot,[src*="mascot"],[src*="pet"]');return x&&x.tagName==='IMG'?x.src:'';}
  function oldSection(id){var el=document.getElementById(id);if(el)el.classList.add('md-legacy-hidden');}

  function bars(){
    var vals=data.daily.map(function(x){return n(x.v);}), max=Math.max.apply(null,vals.concat([1]));
    return data.daily.map(function(x,i){var has=x.v!==null&&x.v!==undefined;var h=has?Math.max(7,n(x.v)/max*150):5;return '<div class="md-bar-item"><span class="md-bar-value">'+(has?esc(n(x.v).toFixed(2))+'万':'待更新')+'</span><i class="md-bar '+(i===0||i===6?'peak':'')+'" style="height:'+h+'px;'+(!has?'opacity:.18':'')+'"></i><span class="md-bar-date">'+esc(x.d)+'</span></div>';}).join('');
  }
  function weeks(){var max=Math.max.apply(null,data.weeks.map(function(x){return n(x.value);}).concat([1]));return data.weeks.map(function(x){return '<div class="md-week-row '+(x.current?'current':'')+'"><label>'+esc(x.label)+'</label><span class="md-week-track"><i style="width:'+Math.max(6,n(x.value)/max*100)+'%"></i></span><b>'+esc(n(x.value).toFixed(2))+'万</b></div>';}).join('');}
  function kpis(){return data.kpis.map(function(x,i){return '<button class="md-kpi md-click" type="button" data-md-panel="kpi-'+i+'"><label>'+esc(x.label)+'</label><strong>'+esc(x.value)+'<em>'+esc(x.unit)+'</em></strong><span>'+esc(x.note)+'</span></button>';}).join('');}
  function alerts(){return data.alerts.map(function(x,i){return '<button class="md-card md-alert md-click '+esc(x.tone)+'" type="button" data-md-panel="alert-'+i+'"><span class="md-alert-top"><i class="md-alert-icon">'+esc(x.icon)+'</i><em class="md-severity">'+esc(x.tag)+'</em></span><h3>'+esc(x.title)+'</h3><p>'+esc(x.copy)+'</p></button>';}).join('');}
  function departments(){return data.departments.map(function(x){return '<button class="md-card md-dept md-click '+esc(x.cls)+'" type="button" data-dept="'+esc(x.key)+'"><i class="md-dept-icon">'+esc(x.icon)+'</i><h3>'+esc(x.name)+'</h3><p>'+esc(x.desc)+'</p><div class="md-dept-metric"><strong>'+esc(x.metric)+'</strong><span>'+esc(x.note)+'</span></div><div class="md-dept-foot"><span>'+esc(x.foot)+'</span><b>查看详情 ›</b></div></button>';}).join('');}
  function funnel(){return data.funnel.map(function(x){return '<div class="md-funnel-step"><span>'+esc(x.label)+'</span><b>'+esc(x.value)+'</b></div>';}).join('');}
  function ranking(tab){var rows=(data.ranks[tab]||[]);return '<table class="md-table"><thead><tr><th>排名</th><th>员工</th><th>部门</th><th>核心结果</th><th>当前依据</th><th>状态</th></tr></thead><tbody>'+rows.map(function(r,i){return '<tr><td class="rank">#'+(i+1)+'</td><td><b>'+esc(r[0])+'</b></td><td>'+esc(r[1])+'</td><td class="score">'+esc(r[2])+'</td><td>'+esc(r[3])+'</td><td><span class="status '+(r[4].indexOf('待核')>-1?'warn':'')+'">'+esc(r[4])+'</span></td></tr>';}).join('')+'</tbody></table>';
  }

  function shell(){
    var src=mascotSrc();
    return '<div class="md-dashboard" id="monthCommandCenter">'+
      '<section class="md-hero-grid" aria-label="月累计经营总览">'+
        '<article class="md-card md-summary"><header class="md-card-title"><div><h2>9月经营总览</h2><p>月累计与 '+WEEK+' 关键指标</p></div><span class="md-live"><i></i>每日 09:00 更新</span></header><div class="md-kpis">'+kpis()+'</div></article>'+
        '<article class="md-card md-target md-click" tabindex="0" role="button" data-md-panel="target"><header class="md-card-title"><div><h2>9月营收目标与预测</h2><p>金额进度与时间进度双轨监测</p></div><span class="md-period-pill">9.1—9.27</span></header><div class="md-amount"><strong>'+esc(data.target.actual)+'</strong><span>／'+esc(data.target.goal)+' 万</span></div><div class="md-progress" aria-label="金额完成 '+esc(data.target.amountRate)+'%，时间进度 '+esc(data.target.timeRate)+'%"><i style="width:'+esc(data.target.amountRate)+'%"></i><u style="left:'+esc(data.target.timeRate)+'%"></u></div><div class="md-progress-label"><div><span>金额完成</span><b>'+esc(data.target.amountRate)+'%</b></div><div><span>时间进度</span><b>'+esc(data.target.timeRate)+'%</b></div><div><span>进度差</span><b class="warn">落后 '+esc(data.target.gap)+'pt</b></div></div><p class="md-target-copy">剩余 '+esc(data.target.days)+' 天需 '+esc(data.target.remaining)+' 万元，日均需 '+esc(data.target.requiredDaily)+' 万元；'+WEEK+'实际日均 '+esc(data.target.currentDaily)+' 万元，真实缺口 '+esc(data.target.dailyGap)+' 万元。</p>'+(src?'<img class="md-mascot" src="'+esc(src)+'" alt="医院吉祥物">':'')+'</article>'+
      '</section>'+
      '<section class="md-alerts" aria-label="重点经营问题">'+alerts()+'</section>'+
      '<div class="md-section-head"><div><h2>营业与转化分析</h2><p>从逐日收入、周度趋势到跨部门服务兑现</p></div><button class="md-more" data-md-panel="analysis" type="button">查看完整分析</button></div>'+
      '<section class="md-analysis-grid">'+
        '<article class="md-card md-chart-card md-click" tabindex="0" role="button" data-md-panel="daily"><header class="md-chart-top"><div><h3>'+WEEK+'逐日营业额</h3><p>单位：万元 · 截至 '+(lastDateMd()||'—')+'，本周剩余天数待更新</p></div><span class="md-chart-badge">日均 6.99 万</span></header><div class="md-bars">'+bars()+'</div><p class="md-chart-note">截至9月25日累计34.97万元；9月25日单日10.12万元，为本周当前高点。</p></article>'+
        '<div class="md-side-stack"><article class="md-card md-week-card md-click" tabindex="0" role="button" data-md-panel="weeks"><header class="md-card-title"><div><h3>9月四周营业对比</h3><p>'+WEEK+'为进行中数据</p></div><b style="color:#15976c">月累计 178.00 万</b></header><div class="md-week-list">'+weeks()+'</div></article><article class="md-card md-funnel md-click" tabindex="0" role="button" data-md-panel="funnel"><header class="md-card-title"><div><h3>'+WEEK+'经营流量</h3><p>门诊、入院、出院为同期数量，不直接计算转化率</p></div><span class="md-severity" style="color:#d57e1c">截至9.25</span></header><div class="md-funnel-steps">'+funnel()+'</div><p class="md-funnel-foot">本周入院13人、出院9人，患者池净增4人；9月25日日终在院31人。</p></article></div>'+
      '</section>'+
      '<div class="md-section-head"><div><h2>部门经营</h2><p>点击任一部门，查看完整数据、趋势、排名与行动建议</p></div></div><section class="md-departments">'+departments()+'</section>'+
      '<div class="md-section-head"><div><h2>月累计动态排名</h2><p>新数据进入后自动重算；月末核验后才形成正式排名</p></div><button class="md-more" data-md-panel="rankrule" type="button">查看排名规则</button></div>'+
      '<section class="md-card md-rank"><header class="md-card-title"><div><h3>员工绩效试算</h3><p>业务量、质量、转化与数据完整性分岗计算</p></div><div class="md-rank-tabs"><button class="active" data-rank="doctor">医生</button><button data-rank="nursing">护理</button><button data-rank="psychology">心理</button><button data-rank="service">客服</button><button data-rank="marketing">营销</button></div></header><div class="md-table-wrap" id="mdRankTable">'+ranking('doctor')+'</div></section>'+
      '<button class="md-card md-governance md-click" type="button" data-md-panel="governance"><div class="md-gov-grid"><i class="md-gov-icon">⌘</i><div class="md-gov-copy"><h3>排名数据治理决策</h3><p>当日记录、次日核验、月内动态试算、月末正式锁定；缺失记“待补”，冲突记“待核”，不得静默改榜。</p></div><span class="md-gov-badge">17 项待核验</span></div></button>'+
    '</div>';
  }

  function drawerMarkup(){return '<div class="md-drawer-backdrop" id="mdDrawerBackdrop"></div><aside class="md-drawer" id="mdDrawer" role="dialog" aria-modal="true" aria-labelledby="mdDrawerTitle"><header class="md-drawer-head"><div><h2 id="mdDrawerTitle">经营详情</h2><p id="mdDrawerSub">'+data.meta.updated+'</p></div><button class="md-drawer-close" type="button" aria-label="关闭">×</button></header><div class="md-drawer-body" id="mdDrawerBody"></div></aside><button class="md-fab-update" id="mdUpdateButton" type="button">＋ 更新数据</button>';}
  function detail(type){
    if(type==='target')return ['9月营收目标与预测','<div class="md-detail-grid"><div class="md-detail-kpi"><span>累计营业额</span><b>'+data.target.actual+' 万</b></div><div class="md-detail-kpi"><span>目标完成</span><b>'+data.target.amountRate+'%</b></div><div class="md-detail-kpi"><span>剩余金额</span><b>'+data.target.remaining+' 万</b></div><div class="md-detail-kpi"><span>所需日均</span><b>'+data.target.requiredDaily+' 万</b></div></div><h3>经营判断</h3><p>金额进度落后时间进度 '+data.target.gap+' 个百分点。后续即使恢复上周日均，也难以自然完成目标，需要明确新增收入来源与患者转化动作。</p>'];
    if(type==='daily'||type==='weeks'||type==='analysis')return ['营业趋势分析','<div class="md-detail-list"><div><b>月度进度：</b>截至9月25日累计177.997848万元，完成260万元目标的68.5%。</div><div><b>'+WEEK+'：</b>截至9月25日34.97万元，日均6.99万元。</div><div><b>收入结构：</b>门诊18.13万元、住院16.84万元，分别占51.8%与48.2%。</div><div><b>行动：</b>9月剩余5天仍需82.00万元，日均需16.40万元。</div></div>'];
    if(type==='funnel')return [WEEK+'经营流量','<div class="md-detail-list"><div><b>门诊：</b>截至9月25日初诊20人次、复诊121人次，合计141人次。</div><div><b>住院流入：</b>本周入院13人。</div><div><b>住院流出：</b>出院初次8人、出院多次1人，合计9人。</div><div><b>患者池：</b>本周净增4人，9月25日日终在院31人。门诊与入院不是患者级匹配数据，不计算门诊转入院率。</div></div>'];
    if(type==='rankrule'||type==='governance')return ['排名数据治理决策','<div class="md-detail-list"><div><b>月内：</b>每月 1 日重置，新数据通过核验后自动重算，名次仅作动态试算。</div><div><b>准入：</b>完整率 ≥95%、按时率 ≥90%、关键冲突率 ≤2%，否则不进入正式榜。</div><div><b>缺失：</b>未填显示“待补”，冲突显示“待核”，不按 0 分处理。</div><div><b>月末：</b>次月 1 日复核，次月 2 日 12:00 锁定；更正必须留痕并保留原快照。</div></div><button class="md-drawer-action" type="button" onclick="document.getElementById(\'rankGovernance\')?.scrollIntoView()">查看完整治理规则</button>'];
    if(type.indexOf('alert-')===0){var a=data.alerts[+type.split('-')[1]];return [a.title,'<div class="md-detail-kpi"><span>风险等级</span><b>'+esc(a.tag)+'</b></div><h3>问题判断</h3><p>'+esc(a.copy)+'</p><h3>建议动作</h3><div class="md-detail-list"><div>明确唯一数据源、负责人和更新时间。</div><div>把发现的问题转为可核验的患者级或业务级清单。</div><div>次日更新状态，完成后保留处理证据。</div></div>'];}
    if(type.indexOf('kpi-')===0){var k=data.kpis[+type.split('-')[1]];return [k.label,'<div class="md-detail-grid"><div class="md-detail-kpi"><span>当前数值</span><b>'+esc(k.value)+' '+esc(k.unit)+'</b></div><div class="md-detail-kpi"><span>统计说明</span><b style="font-size:13px">'+esc(k.note)+'</b></div></div><h3>更新规则</h3><p>此卡片由统一数据对象驱动；导入并核验新数据后，数值、图表和相关分析同步刷新。</p>'];}
    return ['经营详情','<p>点击部门卡片可查看部门完整数据、趋势、排名与行动建议。</p>'];
  }
  function openDrawer(type){var d=detail(type),drawer=document.getElementById('mdDrawer'),bd=document.getElementById('mdDrawerBackdrop');document.getElementById('mdDrawerTitle').textContent=d[0];document.getElementById('mdDrawerBody').innerHTML=d[1];drawer.classList.add('show');bd.classList.add('show');document.body.style.overflow='hidden';drawer.querySelector('.md-drawer-close').focus();}
  function closeDrawer(){var drawer=document.getElementById('mdDrawer'),bd=document.getElementById('mdDrawerBackdrop');if(drawer)drawer.classList.remove('show');if(bd)bd.classList.remove('show');document.body.style.overflow='';}

  function normalizeNode(root){
    if(!root||root.nodeType!==1)return;
    var walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:function(node){var p=node.parentElement;if(!p||/^(SCRIPT|STYLE|TEXTAREA|INPUT)$/.test(p.tagName))return NodeFilter.FILTER_REJECT;return node.nodeValue&&node.nodeValue.indexOf('本周')>-1?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT;}}),nodes=[],x;
    while((x=walker.nextNode()))nodes.push(x);
    nodes.forEach(function(t){t.nodeValue=t.nodeValue.replace(/本周(?!（9\.21—9\.27）)/g,WEEK);});
  }
  function normalizeAll(){normalizeNode(document.body);document.querySelectorAll('[title],[aria-label]').forEach(function(el){['title','aria-label'].forEach(function(a){var v=el.getAttribute(a);if(v&&v.indexOf('本周')>-1)el.setAttribute(a,v.replace(/本周(?!（9\.21—9\.27）)/g,WEEK));});});}

  function mount(){
    if(document.getElementById('monthCommandCenter'))return;
    document.body.classList.add('md-mode');
    ['overview','departments','monthSnapshot'].forEach(oldSection);   /* 只隐藏被月面板完全替代的重复区块；
       decisionCore / insights / coreMetrics / nursingItems / comparison / tasks / rankGovernance
       保留 —— 它们承载本项目独有的本周深度呈现（护理分项、经营对比、AI 诊断、协同任务） */
    var title=document.querySelector('.title-row');if(!title)return;
    var h=title.querySelector('h1'),sub=title.querySelector('.subtitle'),range=document.getElementById('rangeChip'),period=document.getElementById('periodBtn');
    if(h)h.textContent='9月经营协同';if(sub)sub.textContent='月累计结果 · '+WEEK+'变化 · 跨部门闭环';/* rangeChip 同时写明月报告期与本周口径（业主：注意保留本周 9.21—9.27 的呈现）；
       periodBtn 交给 data-import.js 统一写抓取日，避免两个模块争抢同一节点 */
    if(range)range.innerHTML='<i>▦</i>9月1日—9月27日 · '+WEEK+'进行中 · 营收数据至 '+(lastDateMd()||'—');
    title.insertAdjacentHTML('afterend',shell());document.body.insertAdjacentHTML('beforeend',drawerMarkup());
    bind();normalizeAll();
    var observer=new MutationObserver(function(ms){ms.forEach(function(m){m.addedNodes.forEach(function(node){if(node.nodeType===1)normalizeNode(node);});});});observer.observe(document.body,{childList:true,subtree:true});
  }
  function bind(){
    document.addEventListener('click',function(e){
      var panel=e.target.closest('[data-md-panel]');if(panel){openDrawer(panel.dataset.mdPanel);return;}
      var dept=e.target.closest('[data-dept]');if(dept){if(typeof window.openDeptV2==='function')window.openDeptV2(dept.dataset.dept);return;}
      var tab=e.target.closest('[data-rank]');if(tab){document.querySelectorAll('[data-rank]').forEach(function(b){b.classList.toggle('active',b===tab);});document.getElementById('mdRankTable').innerHTML=ranking(tab.dataset.rank);return;}
    });
    document.getElementById('mdDrawerBackdrop').addEventListener('click',closeDrawer);document.querySelector('.md-drawer-close').addEventListener('click',closeDrawer);
    document.addEventListener('keydown',function(e){if(e.key==='Escape')closeDrawer();if((e.key==='Enter'||e.key===' ')&&e.target.matches('[role="button"][data-md-panel]')){e.preventDefault();openDrawer(e.target.dataset.mdPanel);}});
    document.getElementById('mdUpdateButton').addEventListener('click',function(){var b=document.querySelector('.mkt-import');if(b)b.click();else{var ib=document.getElementById('importBackdrop');if(ib){ib.classList.add('show');ib.hidden=false;}else openDrawer('analysis');}});
  }
  function rerender(){var old=document.getElementById('monthCommandCenter');if(old){old.outerHTML=shell();normalizeAll();}}
  window.updateMonthDashboard=function(patch,options){merge(data,patch||{});window.MONTH_DASHBOARD_DATA=data;if(!options||options.persist!==false){try{localStorage.setItem('hospital-month-dashboard-v3-20260926',JSON.stringify(data));}catch(e){}}rerender();return clone(data);};
  window.resetMonthDashboard=function(){data=clone(baseData);window.MONTH_DASHBOARD_DATA=data;try{localStorage.removeItem('hospital-month-dashboard-v3-20260926');}catch(e){}rerender();return clone(data);};
  window.openMonthDashboardPanel=openDrawer;
  window.addEventListener('september-revenue-updated',function(){applyRevenueSnapshot();data=clone(baseData);window.MONTH_DASHBOARD_DATA=data;rerender();});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
