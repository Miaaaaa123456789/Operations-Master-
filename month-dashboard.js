(function(){
  'use strict';

  /* ⚠ 改造纪律（业主 2026-09-28）：**外观与结构完全保留，只让数字活起来**。
     本模块已监听 september-revenue-updated，但模板里仍有写死的文案数字，此处统一接上口径。 */
  function MDF(){ var d=window.SEPTEMBER_REVENUE_DATA;
    if(d&&typeof d.facts==='function'){ try{ return d.facts(); }catch(e){} } return null; }
  function MDFv(v,dflt){ return (v==null||v===''||(typeof v==='number'&&!isFinite(v)))?dflt:v; }
  /* ⭐⭐ 结算月标签（2026-10-06 改造：主面板切 10 月，不再写死「9月」）
     数据层 SEPTEMBER_REVENUE_DATA.SETTLED_MONTH 是唯一真源，
     下方所有「N月」「N.1—N.M」文案一律由这里派生，避免下次切月又要满页找。
     ⚠ 月末天数也按月份取（10 月 31 天），不能再写 30。 */
  var MD_SRC = window.SEPTEMBER_REVENUE_DATA || {};
  var MD_MONTH = MD_SRC.SETTLED_MONTH || '2026-10';
  var MD_NUM = +MD_MONTH.slice(5, 7);
  var MD_LABEL = MD_NUM + '月';                                // '10月'
  var MD_LABEL_SP = MD_NUM + ' 月';                            // '10 月'
  var MD_MDAYS = (function () { var a = MD_SRC.monthFirst ? MD_SRC.monthFirst(MD_MONTH) : MD_MONTH + '-01',
                                   b = MD_SRC.monthLast ? MD_SRC.monthLast(MD_MONTH) : MD_MONTH + '-31';
                                 return (+b.slice(8)); })();   // 31
  var MD_RANGE_CN = MD_LABEL + '1日—' + MD_LABEL + MD_MDAYS + '日';   // '10月1日—10月31日'
  var MD_PILL = MD_NUM + '.1—' + MD_NUM + '.' + MD_MDAYS;             // '10.1—10.31'
  function MDFt(){ var f=MDF()||{}; return {
    date: MDFv(f.labelDateShort,'10.14'), dateCN: MDFv(f.labelDate,'2026年10月14日'),
    remain: MDFv(f.remainDays,17), total: MDFv(f.totalWan,'123.55'),
    amt: (f.amountRate!=null?f.amountRate.toFixed(1):'47.5'),
    tim: (f.timeRate!=null?f.timeRate.toFixed(1):'45.2'),
    need: MDFv(f.needDailyWan,'8.03'), remainWan: MDFv(f.remainWan,'136.45'),
    avg: MDFv(f.mtdAvgWan,'8.82')
  }; }

  /* ⭐⭐ 2026-10-10：营收节奏卡的**语气必须跟着数据翻**。
     原先 tone/icon/tag/title 全部写死为「红 / ↘ / 高风险 / 营收速度不足」，只有正文按
     (时间进度 − 金额完成) 的正负切词 —— 数据转为「领先」后就出现
     「高风险 · 营收速度不足」＋「高于时间进度 2.0 个百分点」的自相矛盾。
     口径：gap ＝ 时间进度 − 金额完成（与数据层 facts().lagPt 同义）；>0 落后 / <0 领先 / ≈0 同步。
     ⚠ 别再把判断句写死在数据里 —— 它必须由数字算出来（本项目反复出现的一类 bug）。 */
  function mdPaceDate(s) {
    s = String(s || '');
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return (+s.slice(5, 7)) + '月' + (+s.slice(8)) + '日';
    var m = s.split('.');
    return m.length === 2 ? ((+m[0]) + '月' + (+m[1]) + '日') : s;
  }
  function mdPaceAlert(o) {
    var gap = o.gap, base = '截至' + mdPaceDate(o.date) + '金额完成' + o.amt + '%';
    /* ⚠ 收官后「缺口」必须由 累计−目标 算符号：超额时不能写「缺口 0.00 万 / 未达成」 */
    var _over = (o.total != null && o.goal) ? (Number(o.total) - Number(o.goal)) : null;
    var tail = o.closed
      ? ((_over != null && _over >= 0)
          ? ('，' + MD_LABEL_SP + '已收官，完成 ' + o.amt + '%，超额 ' + _over.toFixed(2) + ' 万元，月度目标已达成。')
          : ('，' + MD_LABEL_SP + '已收官，缺口 ' + (_over != null ? Math.abs(_over).toFixed(2) : o.remainWan) + ' 万元，月度目标未达成。'))
      : ('，剩余 ' + o.days + ' 天、日均需 ' + o.need + ' 万元。');
    if (gap == null || !isFinite(gap) || Math.abs(gap) < 0.05)
      return {tone:'blue',icon:'↔',tag:'进度同步',title:'营收进度与时间同步',copy:base + '，与时间进度基本持平' + tail};
    if (gap > 0)
      return {tone:'red',icon:'↘',tag:'高风险',title:'营收速度落后',copy:base + '，低于时间进度 ' + gap.toFixed(1) + ' 个百分点' + tail};
    return {tone:'blue',icon:'↗',tag:'节奏领先',title:'营收进度领先',copy:base + '，高于时间进度 ' + Math.abs(gap).toFixed(1) + ' 个百分点' + tail};
  }

  /* ⭐⭐ 特别行动小组例会 · 关键结论与待办（业主 2026-10-10 指定放在告警卡行下方）
     来源：业主提供的例会 AI 纪要。内容属「编辑性内容」故用常量而非 data 层
     （避免被 localStorage 旧存档覆盖）。改纪要只改这一处。 */
  var MEETING={
    title:'特别行动小组例会',
    sub:'医疗业务运营周会 · 关键结论与待办',
    attendees:'周凯、涌现、z、韩玉霜',
    /* ⭐ 数据时间戳（业主 2026-10-10 确认）：纪要数据截至 9.28。
       与原文「仅剩 3 天」互证 —— 9.28 起算到 9.30 正好 3 天。 */
    meetDate:'9.28',
    meetDateCN:'2026 年 9 月 28 日',
    brief:'通报 9 月营收进度及各部门运营数据，重点研讨护理考核、心理科信息同步、客服随访与新媒体运营。',
    countLabel:'待办',
    /* ⚠ 文案刻意**避开裸「本周」** —— 会被 normalizeAll() 改写成「本期（9.28—10.11）」，
       而例会数据是 9.28 会议口径、不在「本期」内。也**不写具体周区间**（见脚本头注）。 */
    note:'本模块数据时间戳为 9.28（9 月营收收尾期，原文载「仅剩 3 天」，9.28—9.30 恰为 3 天）；'
       + '各部门数据均为<b>会议当时的通报口径</b>，与主面板当月月口径不同源，勿与上方月累计混用。',
    /* ⭐ 2026-10-10 加：主视图改为「多图表少文字」。
       百分比都写明分母（营收/目标、抖音/全平台、到院/抓取、到院/转诊），不臆造刻度。
       ⚠ conclusions / blocks / todos / extra 保留 —— 抽屉「查看完整纪要」用全文。 */
    kpis:[
      {icon:'↘',tone:'red',   label:'营收缺口',   value:'57',unit:'万',  note:'9 月累计 202 万 / 目标 260 万'},
      {icon:'⇄',tone:'orange',label:'护理权重',   value:'1.2→0.6',      note:'物理数据权重下调一半'},
      {icon:'⟳',tone:'purple',label:'同步时限',   value:'24',unit:'小时',note:'超时强制转派并扣分'},
      {icon:'⇲',tone:'blue',  label:'管理下沉',   value:'2 人分管 4 人', note:'下周起 · 与奖金挂钩'}
    ],
    charts:[
      {label:'整体营收（9 月累计 / 目标）', pct:77.7, tone:'blue', right:'202 万',
       note:'目标 260 万 · 距缺口 57 万 · 预计全月约 220 万'},
      {label:'医疗部收入构成', right:'59.7 万',
       segs:[{n:'物理治疗 24.6 万',v:41.2,cls:'s1'},{n:'其余 35.1 万',v:58.8,cls:'s2'}],
       note:'物理治疗中 住院 14.8 万 · 门诊 9.8 万（门诊呈增长）'},
      {label:'心理科个体咨询', pct:78, tone:'purple', right:'39 人次', delta:'+30%',
       note:'环比增长 · 情绪爆发干预降至 25 例'},
      {label:'新媒体播放量平台占比', pct:76.7, tone:'green', right:'4.3 万+',
       note:'抖音 3.3 万（占 76.7%）· 四平台 5 条 · 新增粉丝 75'},
      {label:'公寓活动参与人次', pct:100, tone:'teal', right:'86 人次',
       note:'住院部 6 场 51 人 · 家属 4 场 35 人 · 单场平均 9 人'}
    ],
    funnels:[
      {label:'客服随访转化', unit:'人',
       steps:[{n:'AI 抓取',v:179},{n:'人工复核',v:160},{n:'实际到院',v:42}],
       note:'到院率 23.5%（42 / 179）· 有效接待 120、转化 18%'},
      {label:'渠道转诊转化', unit:'人',
       steps:[{n:'转诊',v:12},{n:'到院',v:8}],
       note:'转化率 66.7%（8 / 12）· 外部渠道合计到院 44 人'}
    ],
    /* 待办责任人分布（用于条形图）—— 逐项与 todos 表核对，合计 14 项 */
    todoBy:[
      {who:'周凯',n:4},{who:'金凤',n:2},{who:'倩儿姐 · 金凤姐',n:1},{who:'玉霜',n:1},
      {who:'国威',n:1},{who:'朱静',n:1},{who:'菲菲',n:1},
      {who:'军哥 · 苏欣然 · 陈鹏',n:1},{who:'陈主任',n:1},{who:'公鱼',n:1}
    ],
    conclusions:[
      '9 月营收预计达 220 万，距 260 万目标存在 57 万缺口，需持续关注销售进度。',
      '优化护理考核与奖金分配方案，把「面向患者」纳入考核维度。',
      '建立咨询师信息同步机制，确保患者动态变化有效同步至医生端。',
      '管理者需深入一线辅导团队、明确管理奖金来源，发挥医生「指挥棒」作用。'
    ],
    blocks:[
      {k:'整体营收',v:'9 月累计 202 万',n:'日均 7.5 万 · 预计全月约 220 万'},
      {k:'医疗部',v:'总收入 59.7 万',n:'物理治疗 24.6 万（住院 14.8 · 门诊 9.8）'},
      {k:'心理科',v:'个体咨询 39 人次',n:'环比 +30% · 情绪爆发干预 25 例（较前减少）'},
      {k:'客服随访',v:'到院 42 人',n:'AI 抓取 179 → 复核 160 余人 · 有效接待 120、转化 18%'},
      {k:'新媒体',v:'播放 4.3 万+',n:'四平台 5 条 · 新增粉丝 75 · 抖音单条最高 1.1 万'},
      {k:'渠道销售',v:'转诊到院 8 人',n:'转诊 12 人 · 转化 66.7% · 外部渠道到院 44 人'},
      {k:'公寓活动',v:'住院部 6 场 51 人',n:'家属 4 场 35 人 · 单场平均 9 人，与往周持平'}
    ],
    todos:[
      ['核查护理部夜间数据未同步导致在院收入异常','倩儿姐、金凤姐'],
      ['与玉霜讨论并优化员工排名评分标准，把医生对患者入院目标的设定纳入考核','周凯'],
      ['跟进医生书面提交患者入院核心目标及期望的精细化管理动作','周凯'],
      ['收集员工对护理奖金分配及考核方案的意见','金凤'],
      ['持续推进护士面向患者的负责制，并将相关考核指标纳入排名表','金凤'],
      ['将医生交代的每周任务记录并挂接至周凯的文档反馈中','玉霜'],
      ['制定客服随访的专业化计划，结合患者具体症状做针对性沟通','国威'],
      ['将患者问题细分并下发至各科室，推动服务前置化','朱静'],
      ['提前提醒咨询师教授查房时间，确保患者咨询信息同步到位','菲菲'],
      ['推进疗愈房间的改造与软装布置，争取节后完成','周凯'],
      ['每周固定安排一次选题和脚本沟通，确认拍摄时间，提升内容生产效率','军哥、苏欣然、陈鹏'],
      ['持续跟踪新桥医院新渠道及双福三小合作协议的落地','周凯'],
      ['推进医生将患者入院核心目标的设定动作落实，发挥指挥棒作用','陈主任'],
      ['研究并策划孩子喜欢的活动，引导孩子记录并分享交流瞬间','公鱼']
    ],
    extra:[
      {h:'护理与心理科',items:[
        '交流电应做 183 人、实做 176 人，完成率 96%；9.25 因患者请假晚归降至 87%。',
        '护理工作量权重已由 1.2 调整为 0.6，考核结合工作量、护理质量与夜班分值。',
        '青少年个体化陪伴服务定价 260 元/小时，由咨询师在非饱和时段承接。',
        '心理科业绩暂无法单独核算（住院患者未结算、财务分账困难），混在住院与门诊中。'
      ]},
      {h:'客服、新媒体与活动',items:[
        '随访仍围绕教授号源与复诊指导；后续需结合具体症状（手抖、紧张等）做专业沟通。',
        '管家收集到 33 条患者问题，集中在就医流程（抢号难、距离远）、心理困扰、躯体症状三方面。',
        '新媒体将对比高低播放量内容、优化封面比例、增加引导私信与评论的「钩子」。',
        '公寓活动要引导患者分享真实住院细节与专业感受，重点策划孩子喜欢的活动。'
      ]},
      {h:'管理要求',items:[
        '管理者必须深入一线掌握患者与员工实情，带教与跟进是拿管理奖金的前提。',
        '医生须对患者入院核心目标做专业化设定并同步给心理管家与咨询师，该动作纳入考核排名。',
        '护士考核向「面向患者负责制」倾斜，把行为过程与患者结果一并纳入排名表。',
        '科室与护理部设 AB 角分工；下周起由两名管理分管四人，奖金与分工挂钩。'
      ]}
    ]
  };

  /* ⭐⭐ 本期（观察期）标签（2026-10-06 业主定：所有「本期」时间戳与洞察按 9.28—10.11 算）。
     区间唯一真源＝数据层 derive().period（两周窗口），不再自己按自然周推导
     —— 原先本地推导只能得到单周「本周（10.5）」，与业主口径不符。
     ⚠ 下方 WEEK_SHORT（归一化替换文本）与 WEEK_LABEL_RE 都在这一带定义，勿分散改。 */
var WEEK=(function(){
var _d=window.SEPTEMBER_REVENUE_DATA||{}, _r=_d.rows||[];
var _x=(typeof _d.derive==='function')?(function(){try{return _d.derive()||{}}catch(e){return {}}})():{};
var _p=_x.period||{};
var _from=_p.from||'2026-09-28', _to=_p.to||'2026-10-11';
function _md(d){return (+d.slice(5,7))+'.'+(+d.slice(8));}
var _last=_r.length?_r[_r.length-1].date:'';
/* 「本期是否已完整」＝数据末日是否已到本期终点（原 __WEEK_DONE 用「末日＝周日」判断） */
window.__WEEK_DONE = !!(_last && _last>=_to);
return '本期（'+(_from===_to?_md(_from):(_md(_from)+'—'+_md(_to)))+'）';
})();
  /* 归一化的「排除项」必须是**当前** WEEK 标签本身，否则已带标签的文案会被再追加一次：
     「本周（9.28—10.1）」→「本周（9.28—10.1）（9.28—10.1）」（周窗口滚动后实测命中，部门卡脚注重复）。
     此前把排除项写死成 9.21—9.27，窗口一滚就失效。 */
  /* ⚠ 负向先行断言里放的必须是「本周」**之后**的那段（＝ WEEK 去掉开头的「本周」），
     不是整条 WEEK —— 被匹配的是「本周」，紧随其后的是「（9.28—10.1）」。
     写成整条 WEEK 会让断言恒真 → 每渲染一次就再追加一次标签
     （实测出现「本周（9.28—10.1）（9.28—10.1）期内单日高点」）。 */
  /* ⭐ 归一化用的替换文本是**简称「本期」**（不是带区间的 WEEK）：
     index.html 里大量结构标题写的是裸「本周」（「本周协同任务」「本周经营总览」…），
     若替换成「本期（9.28—10.11）」会变成又长又怪的标题。
     需要区间的场合（本模块自己的模板）一律显式使用 WEEK。 */
  var WEEK_SHORT='本期';
  var WEEK_LABEL_RE=/本周/g;
  /* ⚠ 称呼已改：原先叫「上周（9.21—9.27）」，但营收周口径滚动到 10 月后
     「上周」应为 9.28—10.4，沿用旧称呼会张冠李戴。
     这几张部门台账（心理 / 客服）**尚未收到新一周数据**，故按各自最新周显式标注区间。 */
  /* ⚠ 2026-10-07：原常量 PWEEK（'9.21—9.27（源表台账周）· '）已删除 ——
     心理组（10.1—10.7）与客服组（10.1—10.7）本轮都已收到新一周数据、切到本期口径，
     已无「台账仍停在旧周」的部门，留着会成为死常量误导后来者。
     ⭐ 今后若某张台账未收到新周数据，**请在各自卡片里显式写区间**，
        不要再用一个全局常量代指「源表台账周」。 */
  var baseData={
    meta:{range:MD_RANGE_CN+'（报告期）',updated:'数据截至 2026年10月6日 23:59'},
    kpis:[
      {label:MD_LABEL+'累计营业额',value:'57.15',unit:'万元',note:'截至 10.6 · 完成目标 22.0%'},
      {label:WEEK+'营业额',value:'19.58',unit:'万元',note:'9.28—10.6 · 日均 9.08 万'},
      {label:'在院人数',value:'33',unit:'人',note:'10.6 日终时点'},
      {label:WEEK+'入院',value:'19',unit:'人',note:'9.28—10.6 已发生'},
      {label:WEEK+'出院',value:'19',unit:'人',note:'营收日报口径（含多次）'},
      {label:MD_LABEL+'门诊人次',value:'281',unit:'人次',note:'初诊 28＋复诊 253'}
    ],
    target:{closed:false,actual:57.15,goal:260,amountRate:22.0,timeRate:19.4,gap:-2.6,days:25,remaining:202.85,requiredDaily:8.11,currentDaily:9.08,dailyGap:-0.97},
    alerts:[
      mdPaceAlert({date:MDFt().date,amt:MDFt().amt,gap:(MDFt().tim-0)-(MDFt().amt-0),closed:false,remainWan:MDFt().remainWan,days:MDFt().remain,need:MDFt().need}),
      {tone:'orange',icon:'◆',tag:'结构风险',title:'收入集中在少数高峰日',copy:'10月1日16.22万元为月内单日最高，10月6日12.51万元、10月2日10.44万元次之。'},
      {tone:'purple',icon:'＋',tag:'患者池变化',title:'本期净减4人',copy:'10.6 入院1人、出院5人，10.6 日终在院33人。'},
      {tone:'blue',icon:'✓',tag:'已核验',title:'6天累计连续勾稽',copy:'10月1—10月6日每日合计与累计连续一致，区间内无缺日。'}
    ],
    daily:[
      {d:'10.1',v:16.220027},{d:'10.2',v:10.444441},{d:'10.3',v:6.194017},{d:'10.4',v:4.710167},{d:'10.5',v:7.076667},{d:'10.6',v:12.507558}
    ],
    weeks:[
      {label:'10.1—10.4',value:37.57},{label:'10.5—10.11',value:19.58,current:true}
    ],
    funnelAdm:1,funnelDis:5,funnelNet:-4,funnelWard:33,funnelWardAt:'10.6',
    funnel:[
      {label:'门诊',value:'70人次'},{label:'入院',value:'1人'},{label:'出院',value:'5人'},{label:'在院',value:'33人'}
    ],
    departments:[
      /* ⚠ 2026-10-18：五张卡的默认值统一到 snapshot rev5（10.26–11.01），
         只作「快照没取到」时的兜底；线上真实刷新由 live-sync.js 的 patchMdDepartments 完成。 */
      {key:'doctor',cls:'doctor',icon:'医',name:'医生组',desc:'住院规模与管床贡献',metric:'21.45 万',note:'本期 10.26–11.01 · 出院结账（7 天）',foot:'物理 12.89 万 · 出院 10 · 在院 36'},
      {key:'nursing',cls:'nursing',icon:'护',name:'护理组',desc:'治疗执行与服务兑现',metric:'90.1%',note:'本期 10.26–11.01 · 六项治疗完成率（7 天）',foot:'630 / 699 · 未做 69'},
      {key:'psychology',cls:'psychology',icon:'心',name:'心理咨询组',desc:'咨询承接与收入结构',metric:'36 人次',note:'本期 10.26–11.01 · 患者接触（V4 · 7 天 17 条）',foot:'咨询 24 人次 · 团体 2 场 12 人'},
      {key:'service',cls:'service',icon:'客',name:'客服服务部',desc:'随访、到院及付费跟踪',metric:'49 条',note:'本期 10.26–11.01 · 回访（7 天）',foot:'到院 11 · 22.4% · 日均 +69.0%'},
      /* ⚠ 营销组不再挂「营业额」：营业额属全院口径，挂到营销组名下会被读成营销贡献。 */
      {key:'marketing',cls:'marketing',icon:'营',name:'营销组',desc:'管家、工娱与渠道归集',metric:'92 条',note:'本期 10.26–11.01 · 管家有效对接（7 天）',foot:'转住院 12 · 13.0%'}
    ],
    ranks:{
      /* ⭐ 2026-11-02：医生组本周汇报表未滚动 → 排名改按《出院结帐明细表》结算收入降序，
         只给条数与金额、不算占比；上一期无同源对照，故不写环比。 */
      doctor:[['王建','医生组','结算 8.30 万 · 出院 3 · 床日 24.0 · 在管 5 · 床日收入 1,152 元','出院结账 · 本周 10.26—11.01（7 天）','动态试算'],['王建宁','医生组','结算 3.86 万 · 出院 1 · 床日 25.0 · 床日收入 1,543 元（组内最高）','出院结账 · 本周 10.26—11.01（7 天）','动态试算'],['曾凯','医生组','结算 3.10 万 · 出院 2 · 床日 14.5 · 在院 7','出院结账 · 本周 10.26—11.01（7 天）','动态试算'],['杜宁','医生组','结算 2.95 万 · 出院 2 · 床日 12.5 · 在院 6','出院结账 · 本周 10.26—11.01（7 天）','动态试算'],['康言','医生组','结算 1.91 万 · 出院 1 · 床日 15.0','出院结账 · 本周 10.26—11.01（7 天）','动态试算'],['邓霏','医生组','结算 1.33 万 · 出院 1 · 床日 9.0 · 床日收入 1,478 元（组内第 2）','出院结账 · 本周 10.26—11.01（7 天）','动态试算'],['谭喜文','医生组','结算 0 万 · 本周无出院 · 在管 3 人（新入 3）','出院结账 · 本周 10.26—11.01（7 天）','在管未出']],
      /* ⭐ 2026-11-02：护理考核表已交 → 按周总完成率（效率口径）排 14 人；
         李永鑫、陈福建 7 天无完成率不进榜，赵林烦整行空。 */
      nursing:[['沈琳','护理组','完成率 94.8% · 得分 22.2 · 填 2 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['杨思菡','护理组','完成率 92.66% · 得分 26.2 · 填 5 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['袁怡','护理组','完成率 86.3% · 得分 16 · 填 3 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['任健康','护理组','完成率 86.3% · 得分 26 · 填 4 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['梅燕萍','护理组','完成率 85.65% · 得分 13.4 · 填 2 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['赵雯倩','护理组','完成率 85.2% · 得分 11.7 · 填 2 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['丁思意','护理组','完成率 83.92% · 得分 16.1 · 填 4 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['杨欢','护理组','完成率 82.7% · 得分 21.5 · 填 3 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['何培培','护理组','完成率 82.5% · 得分 11.3 · 填 3 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['吴雨霏','护理组','完成率 77.75% · 得分 25 · 填 2 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['刘佳佳','护理组','完成率 77.4% · 得分 28.8 · 填 2 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['杨新金','护理组','完成率 73.35% · 得分 30.2 · 填 4 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['彭龙华','护理组','完成率 66.8% · 得分 15 · 填 3 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算'],['彭榆凯','护理组','完成率 64.5% · 得分 21.6 · 填 1 天','护士周工作量统计表 · 本周 10.26—11.01（7 天）','动态试算']],
      /* 心理：综合分 = 0.667×(咨询÷组内最大) + 0.333×(接触÷组内最大)，百分制；组长陈鹏不参与排名 */
      psychology:[['蔡宜蓉','心理咨询组','综合 100 · 咨询 14 / 接触 18 · 填报 5 天','V4 简报逐条 · 归一化综合分（咨询 2 : 接触 1）','动态试算'],['赵芳','心理咨询组','综合 30 · 咨询 4 / 接触 6 · 填报 3 天','V4 简报逐条 · 归一化综合分（咨询 2 : 接触 1）','动态试算'],['冯浩鹏','心理咨询组','综合 29 · 咨询 3 / 接触 8 · 填报 3 天','V4 简报逐条 · 归一化综合分（咨询 2 : 接触 1）','动态试算'],['李凌钰','心理咨询组','综合 13 · 咨询 2 / 接触 2 · 填报 2 天','V4 简报逐条 · 归一化综合分（咨询 2 : 接触 1）','动态试算'],['苏欣然','心理咨询组','综合 8 · 咨询 1 / 接触 2 · 填报 1 天','V4 简报逐条 · 归一化综合分（咨询 2 : 接触 1）','动态试算'],['史允之','心理咨询组','综合 0 · 咨询 0 / 接触 0 · 填报 2 天','V4 简报逐条 · 归一化综合分（咨询 2 : 接触 1）','无业务量'],['王沛然','心理咨询组','综合 0 · 咨询 0 / 接触 0 · 填报 1 天（1 条日期误录 2027）','V4 简报逐条 · 归一化综合分（咨询 2 : 接触 1）','无业务量']],
      /* 客服：本周只有两人在回访台账有记录，按条数排；日工作量逐人明细本周未取到 → 不排名 */
      service:[['蒋雨','客服服务部','回访 36 条（第 1）· 到院 11 人（全组到院率 22.4%）','标准化回访台账 · 本周 10.26—11.01（7 天）','动态试算'],['温诗怡','客服服务部','回访 13 条 · 到院 0','标准化回访台账 · 本周 10.26—11.01（7 天）','动态试算'],['其他人','客服服务部','本周回访台账无记录 · 日工作量逐人明细待补','标准化回访台账 · 本周 10.26—11.01','待补']],
      /* ⭐ 2026-11-02：管家组 5 张分表逐条，转住院按「住院」列非空且非否/斜杠计。
         权重列本周只填 12 格「1」，与 12 人转住院一一对应（每人均 3），属住院标记而非权重打分
         → 只按条数排、不算权重分，不拿上期 14.0 / 16.0 顶替。 */
      marketing:[['朱婧','营销组','有效对接 33 条（第 1）· 转住院 3 人（9.1%）','管家分表逐条 · 本周 10.26—11.01（7 天）','动态试算'],['国威','营销组','有效对接 25 条 · 转住院 3 人（12.0%）','管家分表逐条 · 本周 10.26—11.01（7 天）','动态试算'],['金林','营销组','有效对接 17 条（与利娟并列）· 转住院 3 人（17.6%）','管家分表逐条 · 本周 10.26—11.01（7 天）','动态试算'],['利娟','营销组','有效对接 17 条（与金林并列）· 转住院 3 人（17.6%）','管家分表逐条 · 本周 10.26—11.01（7 天）','动态试算'],['菲菲','营销组','本期未填报（分表最后一行 10.18）· 权重列为空 · 记 null 不按 0','管家分表逐条 · 本周 10.26—11.01','待补']]

    }
  };

  function applyRevenueSnapshot(){
    var source=window.SEPTEMBER_REVENUE_DATA;if(!source||!source.derive)return;
    var x=source.derive(),m=x.month,w=x.currentWeek,last=(function(){/* ⚠ 2026-11-04：营收日报已进 11 月，而本板是 10 月账；last 必须截到结算月内，否则「10月1日—11月2日」、累计卡「截至 11月2日」全错。 */var rr=source.rows.filter(function(r){return String(r.date).indexOf(MD_MONTH)===0;});return rr.length?rr[rr.length-1]:source.rows[source.rows.length-1];})(),fmt=function(v){return (v/10000).toFixed(2);},dis=w.discharges;
    /* 在院人数取「最近一个有填报的日期」，避免最后一天缺该字段时被显示成 0 */
    var lw=(source.lastWard&&source.lastWard())||{value:last.ward,date:last.date};if(lw&&lw.date&&String(lw.date).indexOf(MD_MONTH)!==0)lw={value:last.ward,date:last.date};
    var md=function(d){return d?(+d.slice(5,7))+'月'+(+d.slice(8))+'日':'';};
    var _ing=window.OPS_INGEST_DATE||'';
    var _ingTxt=_ing?(_ing.slice(0,4)+'年'+(+_ing.slice(5,7))+'月'+(+_ing.slice(8))+'日'):'';
/* ⚠ 月口径末日 ≠ 数据末日。9 月已收官（10-05 时数据末日已到 10.4），
   「报告期」与「9月累计」的截止应锁定月口径末日（9.30），
   否则会显示「9月1日—10月4日」这种自相矛盾的区间，并让人以为 9 月还在滚。
   周口径（WEEK 营业额/入院/出院）与在院时点仍跟数据末日走，两者语义不同。 */
var _mLast=(function(){var rr=String(source.reportRange||'');var p=rr.split('—');return (p[1]||'').trim();})()||last.date;
baseData.meta={range:MD_LABEL+'1日—'+MD_LABEL+MD_MDAYS+'日（报告期）',
updated:(_ingTxt&&_ing!==source.updatedThrough)?('数据截至 '+_ingTxt+'（营收 '+source.updatedAt+'）'):('数据截至 '+source.updatedAt)};
baseData.kpis=[
/* ⚠ 「截至」用**数据末日**（10.5）。原用月口径末日（10-31）—— 9 月收官时两者相同，
     但 10 月进行中会写成「截至 10月31日」，让人误以为已结账。月口径区间另见报告期字段。 */
{label:MD_LABEL+'累计营业额',value:fmt(m.total),unit:'万元',note:'截至 '+md(last.date)+' · 完成目标 '+x.amountRate.toFixed(1)+'%'},
      {label:WEEK+'营业额',value:fmt(w.total),unit:'万元',note:'截至 '+md(last.date)+' · 日均 '+fmt(w.average)+' 万'},
      {label:'在院人数',value:String(lw.value==null?'—':lw.value),unit:'人',note:(lw.date?md(lw.date):md(last.date))+' 日终时点'},
      {label:WEEK+'入院',value:String(w.admissions),unit:'人',note:(function(){var s=String(WEEK).match(/（([^—]+)—([^）]+)）/);var d=md(last.date);return (s&&s[1]!==s[2])?(s[1]+'—'+d+' 已发生'):(d+' 已发生');})()},
      {label:WEEK+'出院',value:String(dis),unit:'人',note:'营收日报口径（含多次）'},
      {label:MD_LABEL+'门诊人次',value:String(m.visits),unit:'人次',note:'初诊 '+m.first+'＋复诊 '+m.repeat}
    ];
    var _closed=(x.remainingDays===0);
    var _tActual=m.total/10000, _tGoal=(window.SEPTEMBER_REVENUE_DATA&&window.SEPTEMBER_REVENUE_DATA.goal)?window.SEPTEMBER_REVENUE_DATA.goal/10000:260;
    baseData.target={closed:_closed,actual:Number(fmt(m.total)),goal:Number(_tGoal.toFixed(2)),amountRate:Number(x.amountRate.toFixed(1)),timeRate:Number(x.timeRate.toFixed(1)),gap:Number((x.timeRate-x.amountRate).toFixed(1)),days:x.remainingDays,remaining:Number(fmt(Math.max(0,_tGoal-_tActual))),over:Number(Math.max(0,_tActual-_tGoal).toFixed(2)),requiredDaily:Number(fmt(x.requiredDaily)),currentDaily:Number(fmt(w.average)),dailyGap:Number(fmt(x.requiredDaily-w.average))};
    baseData.alerts=[
      mdPaceAlert({date:last.date,amt:x.amountRate.toFixed(1),gap:x.timeRate-x.amountRate,closed:x.remainingDays===0,remainWan:fmt(Math.max(0,x.remaining)),total:m.total/10000,goal:(window.SEPTEMBER_REVENUE_DATA&&window.SEPTEMBER_REVENUE_DATA.goal)?window.SEPTEMBER_REVENUE_DATA.goal/10000:260,days:x.remainingDays,need:fmt(x.requiredDaily)}),
      {tone:'orange',icon:'◆',tag:'结构风险',title:'收入集中在少数高峰日',copy:(function(){var _t=(x.topDays||[]).slice(0,3).map(function(r){return (+r.date.slice(5,7))+'月'+(+r.date.slice(8))+'日'+fmt(r.total)+'万';});return (_t.length?(_t[0]+'为'+MD_LABEL+'内单日最高'+(_t.length>1?('（'+_t.slice(1).join('、')+'次之）'):'')):('（'+MD_LABEL+'内数据不足）'))+'，周末日均'+fmt(x.weekend.average)+'万元，平日日均'+fmt(x.weekday.average)+'万元。';})()},
      {tone:'purple',icon:'＋',tag:'患者池变化',title:'本期患者池'+(w.admissions-dis>=0?'净增':'净减')+Math.abs(w.admissions-dis)+'人',copy:'入院'+w.admissions+'人、出院'+dis+'人，'+(lw.date?md(lw.date):'')+'日终在院'+lw.value+'人。'},
      {tone:'blue',icon:'✓',tag:'已核验',title:m.days+'天累计连续勾稽',copy:MD_LABEL+'1日—'+md(last.date)+'每日合计与累计连续一致；'+MD_LABEL+'内 '+m.days+' 天无缺日。'}
    ];
    /* ⚠ 待补日不能硬编码 9.26/9.27：数据真到 9.26 后会重复出现两根「待更新」柱。
       改为「本周 9.21—9.27 中数据里缺的那几天」，并把日期格式统一成 09.xx（与已有柱一致）。 */
    var _have={};source.rows.forEach(function(r){_have[r.date]=1;});
    /* 逐日柱：9.21—9.30（上周完整周 + 本周进行中 3 天），不预置未来日期 */
    var _pend=[];
    baseData.daily=source.rows.filter(function(r){return r.date>=x.monthFirst&&r.date<=x.monthLast;}).map(function(r){return {d:r.date.slice(5).replace('-','.'),v:r.total/10000};}).concat(_pend);
    /* ⚠ 原按固定数组下标判断本周 —— 周窗口滚动后指向的不是本周。
       本期＝两周窗口，故标记**落在本期内的所有周**（当前为 10.1—10.4 与 10.5—10.11）。 */
    /* ⭐ 2026-10-10：周行要区分「未来周 / 进行中 / 已完整」——
       原先未来周也渲染成 0.00 万，会被读成「那一周营收为 0」（与「缺值→待补、不得默认 0」冲突）。
       future：周起点晚于数据末日；days/recorded：本周已录天数（跨周比较必须写明天数）。 */
    var _lastD=(last&&last.date)||'';
    baseData.weeks=x.weeks.map(function(q){
      var _future=!!(q.from&&_lastD&&q.from>_lastD);
      var _days=0;
      if(q.from&&q.to){_days=Math.round((new Date(q.to.replace(/-/g,'/'))-new Date(q.from.replace(/-/g,'/')))/86400000)+1;}
      var _rec=_future?0:source.rows.filter(function(r){return r.date>=q.from&&r.date<=q.to;}).length;
      return {label:q.label,value:q.total/10000,current:!!(q.inPeriod||q.current),future:_future,days:_days,recorded:_rec};
    });
    baseData.funnelAdm=w.admissions;baseData.funnelDis=dis;baseData.funnelNet=w.admissions-dis;
    baseData.funnelWard=(lw.value==null?'待补':lw.value);
    baseData.funnelWardAt=(lw.date?(+lw.date.slice(5,7))+'.'+(+lw.date.slice(8)):'');
    baseData.funnel=[{label:'门诊',value:w.visits+'人次'},{label:'入院',value:w.admissions+'人'},{label:'出院',value:dis+'人'},{label:'在院',value:(lw.value==null?'待补':lw.value)+'人'}];
    /* ⚠ 2026-10-18 撤掉「营销组 metric = 本期营业额」：
       营业额是全院口径（门诊＋在院），挂在营销组名下会被误读成营销贡献。
       营销组本地数据是《患者有效对接表》的管家对接/转住院，由 live-sync.js 按快照写入。 */
    /* ⚠ 医生部门卡此前是静态值，营收数据推进后不跟随（表现为卡上仍写上一个时点的在院/入出院）。
       这里与营销卡一样接入快照，避免每轮都要手改。 */
    if(baseData.departments[0]){
      baseData.departments[0].metric=(lw.value==null?'—':lw.value)+' 人';
      var _ldt=lw.date||last.date;
      baseData.departments[0].note='在院 · '+(+_ldt.slice(5,7))+'.'+(+_ldt.slice(8))+' 时点';
      baseData.departments[0].foot='入院 '+w.admissions+' · 出院 '+dis;
    }
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
  /* rangeChip 抽成函数：原先只在 mount() 里写一次，导入新数据后仍显示旧营收日。
     现在 mount 与 september-revenue-updated 各调用一次，时间戳随数据同步。 */
  function writeRangeChip(){
    var range=document.getElementById('rangeChip'); if(!range) return;
    var _ig=window.OPS_INGEST_DATE||'', _snap=window.SEPTEMBER_REVENUE_DATA||{},
        _igMd=_ig?((+_ig.slice(5,7))+'月'+(+_ig.slice(8))+'日'):'';
    /* ⚠ 报告期取**结算月**末日（9月30日），不能跟数据末日走
       —— 否则会显示「9月1日—10月1日」，把 10 月并进 9 月报告。
       而「营收数据至」用数据末日（10月1日），两者语义不同，勿混用同一函数。 */
    range.innerHTML='<i>▦</i>'+monthRangeText()+' · '+WEEK+(window.__WEEK_DONE?'已完整':'进行中')+' · '
      +((_igMd&&_ig!==_snap.updatedThrough)?('部门数据至 '+_igMd+' · '):'')
      +'营收数据至 '+(lastDateMd()||'—');
  }
  /* 结算月区间文本（如「9月1日—9月30日」），来源 data.reportRange，数据层已锁结算月 */
  function monthRangeText(){
    var src=window.SEPTEMBER_REVENUE_DATA||{}, r=String(src.reportRange||'');
    var p=r.split('—');
    if(p.length<2||!p[1])return MD_RANGE_CN;
    var f=function(s){return (+s.slice(5,7))+'月'+(+s.slice(8))+'日';};
    return f(p[0])+'—'+f(p[1]);
  }
  function lastDateMd(){var src=window.SEPTEMBER_REVENUE_DATA;if(!src||!src.rows||!src.rows.length)return '';var d=src.rows[src.rows.length-1].date;return (+d.slice(5,7))+'月'+(+d.slice(8))+'日';}
  function mascotSrc(){var x=document.querySelector('.hero-mascot img,.hero-mascot,.mascot img,.mascot,[src*="mascot"],[src*="pet"]');return x&&x.tagName==='IMG'?x.src:'';}
  function oldSection(id){var el=document.getElementById(id);if(el)el.classList.add('md-legacy-hidden');}

  function bars(){
    var vals=data.daily.map(function(x){return n(x.v);}), max=Math.max.apply(null,vals.concat([1]));
    return data.daily.map(function(x,i){var has=x.v!==null&&x.v!==undefined;var h=has?Math.max(7,n(x.v)/max*150):5;return '<div class="md-bar-item"><span class="md-bar-value">'+(has?esc(n(x.v).toFixed(2))+'万':'待更新')+'</span><i class="md-bar '+(i===0||i===6?'peak':'')+'" style="height:'+h+'px;'+(!has?'opacity:.18':'')+'"></i><span class="md-bar-date">'+esc(x.d)+'</span></div>';}).join('');
  }
  function weeks(){var max=Math.max.apply(null,data.weeks.map(function(x){return n(x.value);}).concat([1]));
    return data.weeks.map(function(x){
      var _f=!!x.future,_cur=!!x.current;
      /* 未来周：虚线空槽 + 「未开始」，**不写 0.00 万**（空格不代表营收 0） */
      var _bar='<span class="md-week-track'+(_f?' ghost':'')+'">'+(_f?'':'<i style="width:'+Math.max(6,n(x.value)/max*100)+'%"></i>')+'</span>';
      var _val=_f?'<b class="w-future">未开始</b>':('<b>'+esc(n(x.value).toFixed(2))+'万</b>');
      /* 进行中的周：标明已录天数，避免与完整周直接比大小 */
      var _tag=(!_f&&_cur&&x.days&&x.recorded<x.days)?('<em>已录 '+x.recorded+'/'+x.days+' 天</em>'):'';
      return '<div class="md-week-row'+(_cur?' current':'')+(_f?' future':'')+'"><label>'+esc(x.label)+_tag+'</label>'+_bar+_val+'</div>';
    }).join('');}
  function kpis(){return data.kpis.map(function(x,i){return '<button class="md-kpi md-click" type="button" data-md-panel="kpi-'+i+'"><label>'+esc(x.label)+'</label><strong>'+esc(x.value)+'<em>'+esc(x.unit)+'</em></strong><span>'+esc(x.note)+'</span></button>';}).join('');}
  function alerts(){return data.alerts.map(function(x,i){return '<button class="md-card md-alert md-click '+esc(x.tone)+'" type="button" data-md-panel="alert-'+i+'"><span class="md-alert-top"><i class="md-alert-icon">'+esc(x.icon)+'</i><em class="md-severity">'+esc(x.tag)+'</em></span><h3>'+esc(x.title)+'</h3><p>'+esc(x.copy)+'</p></button>';}).join('');}
  /* 例会模块（2026-10-10 图表化）：主视图只给图表，全文留在抽屉。
     ⚠ 全部字段 esc()——纪要原文含「：」「（）」「→」等，且是外部文本。 */
  function meeting(){
    var m=MEETING||{};
    if(!m.title)return '';
    /* ① 核心结论：4 张卡（图标 + 大数字 + 短注） */
    var kpis=(m.kpis||[]).map(function(k){
      return '<div class="md-mk '+esc(k.tone||'')+'"><i>'+esc(k.icon||'')+'</i>'
        +'<label>'+esc(k.label)+'</label>'
        +'<strong>'+esc(k.value)+(k.unit?'<em>'+esc(k.unit)+'</em>':'')+'</strong>'
        +'<span>'+esc(k.note||'')+'</span></div>';
    }).join('');
    /* ② 业务板块：横向条形（支持分段堆叠 + 环比标签） */
    var bars=(m.charts||[]).map(function(c){
      var track;
      if(c.segs&&c.segs.length){
        track='<span class="md-mb-track">'+c.segs.map(function(g){
          return '<i class="'+esc(g.cls||'')+'" style="width:'+Math.min(100,Math.max(0,g.v))+'%"></i>';
        }).join('')+'</span>';
      }else{
        track='<span class="md-mb-track"><i class="'+(c.tone||'')+'" style="width:'
          +Math.min(100,Math.max(2,c.pct||0))+'%"></i></span>';
      }
      return '<div class="md-mb">'
        +'<div class="md-mb-top"><label>'+esc(c.label)+'</label><b>'+esc(c.right)+'</b>'
        +(c.delta?'<em class="up">'+esc(c.delta)+'</em>':'')+'</div>'
        +track
        +(c.note?'<div class="md-mb-note">'+esc(c.note)+'</div>':'')
        +(c.segs&&c.segs.length?'<div class="md-mb-legend">'+c.segs.map(function(g){
            return '<span><i class="'+esc(g.cls||'')+'"></i>'+esc(g.n)+'</span>';
          }).join('')+'</div>':'')
        +'</div>';
    }).join('');
    /* ③ 转化漏斗：条宽＝各步 / 首步 */
    var funnels=(m.funnels||[]).map(function(f){
      var top=(f.steps&&f.steps.length)?f.steps[0].v:1;
      return '<div class="md-mf"><label class="md-mf-head">'+esc(f.label)+'</label>'
        +(f.steps||[]).map(function(st){
          var pct=Math.round(st.v/top*100);
          return '<div class="md-mf-step"><span>'+esc(st.n)+'</span>'
            +'<i><b style="width:'+Math.max(5,pct)+'%"></b></i>'
            +'<em>'+esc(st.v)+(f.unit||'')+'</em></div>';
        }).join('')
        +(f.note?'<div class="md-mf-note">'+esc(f.note)+'</div>':'')+'</div>';
    }).join('');
    /* ④ 待办：责任人分布条形 + 紧凑 chip 清单 */
    var by=(m.todoBy||[]), maxN=by.reduce(function(p,c){return Math.max(p,c.n||0);},1);
    var todos=(m.todos||[]);
    var byBars=by.map(function(t){
      return '<div class="md-tb-row"><label>'+esc(t.who)+'</label>'
        +'<span class="md-tb-track"><i style="width:'+Math.round((t.n||0)/maxN*100)+'%"></i></span>'
        +'<b>'+esc(t.n)+'</b></div>';
    }).join('');
    var chips=todos.map(function(t,i){
      return '<li><i>'+esc(i+1)+'</i><span>'+esc(t[0])+'</span><em>'+esc(t[1])+'</em></li>';
    }).join('');

    return '<div class="md-section-head"><div><h2>'+esc(m.title)+' · 关键结论与待办</h2>'
        +'<p>'+esc(m.sub)+' · 参会 '+esc(m.attendees)+' · '+esc(m.countLabel)+' '+todos.length+' 项</p></div>'
        +'<div class="md-meet-head-right">'
          +'<span class="md-meet-date" title="'+esc(m.meetDateCN)+'">数据截至 '+esc(m.meetDate||'—')+'</span>'
          +'<button class="md-more" data-md-panel="meeting" type="button">查看完整纪要</button>'
        +'</div></div>'
      +'<section class="md-meeting" aria-label="例会关键结论与待办">'
        /* ① 结论卡 */
        +'<div class="md-mk-grid">'+kpis+'</div>'
        /* ② 板块条形图 + ③ 漏斗 */
        +'<div class="md-meeting-grid">'
          +'<article class="md-card md-meet-card"><header class="md-card-title"><div><h3>各业务板块 · 数据表现</h3>'
            +'<p>条长＝该指标占其分母的比例 · 截至 '+esc(m.meetDate||'')+'</p></div>'
            +'<span class="md-meet-pill">'+esc(m.meetDate||'')+' 例会口径</span></header>'
            +'<div class="md-mb-list">'+bars+'</div></article>'
          +'<article class="md-card md-meet-card"><header class="md-card-title"><div><h3>转化漏斗</h3>'
            +'<p>条长＝该步占漏斗首步的比例</p></div>'
            +'<span class="md-meet-pill">'+esc(m.meetDate||'')+' 例会口径</span></header>'
            +'<div class="md-mf-list">'+funnels+'</div>'
            +'<div class="md-mk-grid md-mk-grid-sm">'
              +(m.kpis||[]).slice(0,0).join('')
            +'</div></article>'
        +'</div>'
        /* ④ 待办 */
        +'<div class="md-meeting-grid md-grid-todo">'
          +'<article class="md-card md-meet-card"><header class="md-card-title"><div><h3>'+esc(m.countLabel)+'责任人分布</h3>'
            +'<p>共 '+todos.length+' 项 · 按责任人条长排序</p></div></header>'
            +'<div class="md-tb-list">'+byBars+'</div></article>'
          +'<article class="md-card md-meet-card"><header class="md-card-title"><div><h3>'+esc(m.countLabel)+'清单</h3>'
            +'<p>按例会既定分工 · 右侧为责任人</p></div>'
            +'<span class="md-meet-count">'+todos.length+'</span></header>'
            +'<ul class="md-meet-todos">'+chips+'</ul></article>'
        +'</div>'
      +'</section>';
  }

  function departments(){return data.departments.map(function(x){return '<button class="md-card md-dept md-click '+esc(x.cls)+'" type="button" data-dept="'+esc(x.key)+'"><i class="md-dept-icon">'+esc(x.icon)+'</i><h3>'+esc(x.name)+'</h3><p>'+esc(x.desc)+'</p><div class="md-dept-metric"><strong>'+esc(x.metric)+'</strong><span>'+esc(x.note)+'</span></div><div class="md-dept-foot"><span>'+esc(x.foot)+'</span><b>查看详情 ›</b></div></button>';}).join('');}
  function funnel(){return data.funnel.map(function(x){return '<div class="md-funnel-step"><span>'+esc(x.label)+'</span><b>'+esc(x.value)+'</b></div>';}).join('');}
  function ranking(tab){var rows=(data.ranks[tab]||[]);return '<table class="md-table"><thead><tr><th>排名</th><th>员工</th><th>部门</th><th>核心结果</th><th>当前依据</th><th>状态</th></tr></thead><tbody>'+rows.map(function(r,i){return '<tr><td class="rank">#'+(i+1)+'</td><td><b>'+esc(r[0])+'</b></td><td>'+esc(r[1])+'</td><td class="score">'+esc(r[2])+'</td><td>'+esc(r[3])+'</td><td><span class="status '+(r[4].indexOf('待核')>-1?'warn':'')+'">'+esc(r[4])+'</span></td></tr>';}).join('')+'</tbody></table>';
  }

  function shell(){
    var src=mascotSrc();
    return '<div class="md-dashboard" id="monthCommandCenter">'+
      '<section class="md-hero-grid" aria-label="月累计经营总览">'+
        '<article class="md-card md-summary"><header class="md-card-title"><div><h2>'+MD_LABEL+'经营总览</h2><p>月累计与 '+WEEK+' 关键指标</p></div><span class="md-live"><i></i>每日 09:00 更新</span></header><div class="md-kpis">'+kpis()+'</div></article>'+
        '<article class="md-card md-target md-click" tabindex="0" role="button" data-md-panel="target"><header class="md-card-title"><div><h2>'+MD_LABEL+'营收目标与预测</h2><p>金额进度与时间进度双轨监测</p></div><span class="md-period-pill">'+MD_PILL+'</span></header><div class="md-amount"><strong>'+esc(data.target.actual)+'</strong><span>／'+esc(data.target.goal)+' 万</span></div><div class="md-progress" aria-label="金额完成 '+esc(data.target.amountRate)+'%，时间进度 '+esc(data.target.timeRate)+'%"><i style="width:'+esc(data.target.amountRate)+'%"></i><u style="left:'+esc(data.target.timeRate)+'%"></u></div><div class="md-progress-label"><div><span>金额完成</span><b>'+esc(data.target.amountRate)+'%</b></div><div><span>时间进度</span><b>'+esc(data.target.timeRate)+'%</b></div><div><span>进度差</span><b class="'+((Number(data.target.gap)>=0)?'warn':'')+'">'+(Number(data.target.gap)>=0?'落后 ':'领先 ')+Math.abs(Number(data.target.gap))+'pt</b></div></div><p class="md-target-copy">'+(data.target.closed?((MD_LABEL_SP+'已收官（'+MD_MDAYS+' 天）：累计 '+esc(data.target.actual)+' 万元，完成目标 '+esc(data.target.amountRate)+'%，<b>'+(Number(data.target.over)>0?('超额 '+esc(data.target.over)+' 万元，月度目标已达成'):('缺口 '+esc(data.target.remaining)+' 万元'))+'</b>；'+WEEK+'实际日均 '+esc(data.target.currentDaily)+' 万元。')):('剩余 '+esc(data.target.days)+' 天需 '+esc(data.target.remaining)+' 万元，日均需 '+esc(data.target.requiredDaily)+' 万元；'+WEEK+'实际日均 '+esc(data.target.currentDaily)+' 万元，'+((Number(data.target.dailyGap)>0)?('真实缺口 '+esc(data.target.dailyGap)+' 万元。'):('已高于达标日均 '+Math.abs(Number(data.target.dailyGap)).toFixed(2)+' 万元。'))))+'</p>'+(src?'<img class="md-mascot" src="'+esc(src)+'" alt="医院吉祥物">':'')+'</article>'+
      '</section>'+
      '<section class="md-alerts" aria-label="重点经营问题">'+alerts()+'</section>'+
      /* 业主 2026-10-18 指示：「部门经营」上提到「10 月经营」正下方（原在营业与转化分析之后，
         需要滚过例会纪要 + 逐日营收才能看到，太深）。此处整块前移，其余顺序不动。 */
      '<div class="md-section-head"><div><h2>部门经营</h2><p>点击任一部门，查看完整数据、趋势、排名与行动建议</p></div></div><section class="md-departments">'+departments()+'</section>'+
      meeting()+
      '<div class="md-section-head"><div><h2>营业与转化分析</h2><p>从逐日收入、周度趋势到跨部门服务兑现</p></div><button class="md-more" data-md-panel="analysis" type="button">查看完整分析</button></div>'+
      '<section class="md-analysis-grid">'+
        '<article class="md-card md-chart-card md-click" tabindex="0" role="button" data-md-panel="daily"><header class="md-chart-top"><div><h3>'+MD_NUM+'.1—'+(data.daily.length?data.daily[data.daily.length-1].d:MDFt().date)+' 逐日营业额</h3><p>单位：万元 · 截至 '+(lastDateMd()||'—')+((data.target&&data.target.closed)?'，10 月已收官':'，本周剩余天数待更新')+'</p></div><span class="md-chart-badge">日均 '+MDFt().avg+' 万</span></header><div class="md-bars">'+bars()+'</div><p class="md-chart-note">'+MD_LABEL+'累计 '+MDFt().total+' 万元（'+MD_MDAYS+'/'+MD_MDAYS+' 天）；11.1 起计入 11 月，未并入本图。</p></article>'+
        '<div class="md-side-stack"><article class="md-card md-week-card md-click" tabindex="0" role="button" data-md-panel="weeks"><header class="md-card-title"><div><h3>'+MD_LABEL+'各周营业对比</h3><p>'+WEEK+((data.target&&data.target.closed)?'已结束':'为进行中')+'（数据至 '+(lastDateMd()||'—')+'）</p></div><b style="color:#15976c">月累计 '+MDFt().total+' 万</b></header><div class="md-week-list">'+weeks()+'</div></article><article class="md-card md-funnel md-click" tabindex="0" role="button" data-md-panel="funnel"><header class="md-card-title"><div><h3>'+WEEK+'经营流量</h3><p>门诊、入院、出院为同期数量，不直接计算转化率</p></div><span class="md-severity" style="color:#d57e1c">截至'+MDFt().date+'</span></header><div class="md-funnel-steps">'+funnel()+'</div><p class="md-funnel-foot">'+WEEK+'入院'+esc(data.funnelAdm)+'人、出院'+esc(data.funnelDis)+'人，患者池'+(data.funnelNet>=0?'净增':'净减')+Math.abs(data.funnelNet)+'人；'+esc(data.funnelWardAt)+'日终在院'+esc(data.funnelWard)+'人。</p></article></div>'+
      '</section>'+
      '<button class="md-card md-governance md-click" type="button" data-md-panel="governance"><div class="md-gov-grid"><i class="md-gov-icon">⌘</i><div class="md-gov-copy"><h3>排名数据治理决策</h3><p>当日记录、次日核验、月内动态试算、月末正式锁定；缺失记“待补”，冲突记“待核”，不得静默改榜。</p></div><span class="md-gov-badge">17 项待核验</span></div></button>'+
    '</div>';
  }

  function drawerMarkup(){return '<div class="md-drawer-backdrop" id="mdDrawerBackdrop"></div><aside class="md-drawer" id="mdDrawer" role="dialog" aria-modal="true" aria-labelledby="mdDrawerTitle"><header class="md-drawer-head"><div><h2 id="mdDrawerTitle">经营详情</h2><p id="mdDrawerSub">'+data.meta.updated+'</p></div><button class="md-drawer-close" type="button" aria-label="关闭">×</button></header><div class="md-drawer-body" id="mdDrawerBody"></div></aside><button class="md-fab-update" id="mdUpdateButton" type="button">＋ 更新数据</button>';}
  function detail(type){
    if(type==='target')return [MD_LABEL+'营收目标与预测','<div class="md-detail-grid"><div class="md-detail-kpi"><span>累计营业额</span><b>'+data.target.actual+' 万</b></div><div class="md-detail-kpi"><span>目标完成</span><b>'+data.target.amountRate+'%</b></div><div class="md-detail-kpi"><span>剩余金额</span><b>'+data.target.remaining+' 万</b></div><div class="md-detail-kpi"><span>所需日均</span><b>'+data.target.requiredDaily+' 万</b></div></div><h3>经营判断</h3><p>金额进度落后时间进度 '+data.target.gap+' 个百分点。后续即使恢复上周日均，也难以自然完成目标，需要明确新增收入来源与患者转化动作。</p>'];
    if(type==='daily'||type==='weeks'||type==='analysis')return ['营业趋势分析','<div class="md-detail-list"><div><b>月度进度：</b>截至'+MDFt().dateCN+'累计'+MDFt().total+'万元，完成260万元目标的'+MDFt().amt+'%。</div><div><b>'+WEEK+'：</b>日均'+MDFt().avg+'万元。</div><div><b>收入结构：</b>门诊与住院两端拆分见下方结构图。</div><div><b>行动：</b>'+MD_LABEL+'剩余'+MDFt().remain+'天仍需'+MDFt().remainWan+'万元，日均需'+MDFt().need+'万元。</div></div>'];
    if(type==='funnel')return [WEEK+'经营流量','<div class="md-detail-list"><div><b>门诊：</b>'+MD_LABEL+'1日—'+MDFt().date+'合计 '+esc(data.funnel[0].value)+'。</div><div><b>住院流入：</b>本期入院'+esc(data.funnelAdm)+'人。</div><div><b>住院流出：</b>本期出院'+esc(data.funnelDis)+'人（营收口径，含多次）。</div><div><b>患者池：</b>'+(data.funnelNet>=0?'净增':'净减')+Math.abs(data.funnelNet)+'人，'+esc(data.funnelWardAt)+'日终在院'+esc(data.funnelWard)+'人。门诊与入院不是患者级匹配数据，不计算门诊转入院率。</div></div>'];
    if(type==='rankrule'||type==='governance')return ['排名数据治理决策','<div class="md-detail-list"><div><b>月内：</b>每月 1 日重置，新数据通过核验后自动重算，名次仅作动态试算。</div><div><b>准入：</b>完整率 ≥95%、按时率 ≥90%、关键冲突率 ≤2%，否则不进入正式榜。</div><div><b>缺失：</b>未填显示“待补”，冲突显示“待核”，不按 0 分处理。</div><div><b>月末：</b>次月 1 日复核，次月 2 日 12:00 锁定；更正必须留痕并保留原快照。</div></div><button class="md-drawer-action" type="button" onclick="document.getElementById(\'rankGovernance\')?.scrollIntoView()">查看完整治理规则</button>'];
    if(type==='meeting'){var M=MEETING||{};var _n=(M.todos||[]).length;
      return [esc(M.title)+' · 完整纪要',
        '<p>'+esc(M.brief)+'</p>'
        +'<div class="md-detail-grid"><div class="md-detail-kpi"><span>数据时间戳</span><b>'+esc(M.meetDate||'—')+'</b></div>'
        +'<div class="md-detail-kpi"><span>'+esc(M.countLabel)+'</span><b>'+_n+' 项</b></div>'
        +'<div class="md-detail-kpi" style="grid-column:1/-1"><span>参会</span><b style="font-size:13px">'+esc(M.attendees)+'</b></div></div>'
        +'<h3>核心结论</h3><div class="md-detail-list">'+(M.conclusions||[]).map(function(t){return '<div>'+esc(t)+'</div>';}).join('')+'</div>'
        +'<h3>各业务板块数据</h3><div class="md-detail-list">'+(M.blocks||[]).map(function(b){return '<div><b>'+esc(b.k)+'：</b>'+esc(b.v)+'（'+esc(b.n)+'）</div>';}).join('')+'</div>'
        +'<h3>'+esc(M.countLabel)+'事项（'+_n+'）</h3><div class="md-detail-list">'+(M.todos||[]).map(function(t,i){return '<div><b>'+(i+1)+'.</b> '+esc(t[0])+' —— <b>'+esc(t[1])+'</b></div>';}).join('')+'</div>'
        +(M.extra||[]).map(function(g){return '<h3>'+esc(g.h)+'</h3><div class="md-detail-list">'+(g.items||[]).map(function(x){return '<div>'+esc(x)+'</div>';}).join('')+'</div>';}).join('')
        +'<h3>口径说明</h3><p>'+esc(M.note)+'</p>'];
    }
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
    nodes.forEach(function(t){t.nodeValue=t.nodeValue.replace(WEEK_LABEL_RE,WEEK_SHORT);});
  }
  function normalizeAll(){normalizeNode(document.body);document.querySelectorAll('[title],[aria-label]').forEach(function(el){['title','aria-label'].forEach(function(a){var v=el.getAttribute(a);if(v&&v.indexOf('本周')>-1)el.setAttribute(a,v.replace(WEEK_LABEL_RE,WEEK_SHORT));});});}

  function mount(){
    if(document.getElementById('monthCommandCenter'))return;
    document.body.classList.add('md-mode');
    ['overview','departments','monthSnapshot'].forEach(oldSection);   /* 只隐藏被月面板完全替代的重复区块；
       decisionCore / insights / coreMetrics / nursingItems / comparison / tasks / rankGovernance
       保留 —— 它们承载本项目独有的本周深度呈现（护理分项、经营对比、AI 诊断、协同任务） */
    var title=document.querySelector('.title-row');if(!title)return;
    var h=title.querySelector('h1'),sub=title.querySelector('.subtitle'),range=document.getElementById('rangeChip'),period=document.getElementById('periodBtn');
    if(h)h.textContent=MD_LABEL+'经营协同';if(sub)sub.textContent='月累计结果 · '+WEEK+'变化 · 跨部门闭环';/* rangeChip 同时写明月报告期与本周口径（业主：注意保留本周 9.21—9.27 的呈现）；
       periodBtn 交给 data-import.js 统一写抓取日，避免两个模块争抢同一节点 */
    writeRangeChip();
    /* ⚠ 月面板原本固定插在 .title-row 之后 —— 那样会落到「9 月整月经营分析报告」前面。
       业主 2026-10-01 指定报告在最前，故锚点改为：有报告就插在报告之后，否则退回 title-row。 */
    var _mccAnchor=document.getElementById('sepReport')||title;
    _mccAnchor.insertAdjacentHTML('afterend',shell());document.body.insertAdjacentHTML('beforeend',drawerMarkup());
    bind();normalizeAll();
    var observer=new MutationObserver(function(ms){ms.forEach(function(m){m.addedNodes.forEach(function(node){if(node.nodeType===1)normalizeNode(node);});});});observer.observe(document.body,{childList:true,subtree:true});
  }
  function bind(){
    document.addEventListener('click',function(e){
      var panel=e.target.closest('[data-md-panel]');if(panel){openDrawer(panel.dataset.mdPanel);return;}
      var dept=e.target.closest('[data-dept]');if(dept){if(typeof window.openDeptV2==='function')window.openDeptV2(dept.dataset.dept);return;}
      var tab=e.target.closest('[data-rank]');if(tab){document.querySelectorAll('[data-rank]').forEach(function(b){b.classList.toggle('active',b===tab);});var _rt=document.getElementById('mdRankTable');if(_rt)_rt.innerHTML=ranking(tab.dataset.rank);return;}
    });
    document.getElementById('mdDrawerBackdrop').addEventListener('click',closeDrawer);document.querySelector('.md-drawer-close').addEventListener('click',closeDrawer);
    document.addEventListener('keydown',function(e){if(e.key==='Escape')closeDrawer();if((e.key==='Enter'||e.key===' ')&&e.target.matches('[role="button"][data-md-panel]')){e.preventDefault();openDrawer(e.target.dataset.mdPanel);}});
    document.getElementById('mdUpdateButton').addEventListener('click',function(){var b=document.querySelector('.mkt-import');if(b)b.click();else{var ib=document.getElementById('importBackdrop');if(ib){ib.classList.add('show');ib.hidden=false;}else openDrawer('analysis');}});
  }
  function rerender(){var old=document.getElementById('monthCommandCenter');if(old){old.outerHTML=shell();normalizeAll();}}
  window.updateMonthDashboard=function(patch,options){merge(data,patch||{});window.MONTH_DASHBOARD_DATA=data;if(!options||options.persist!==false){try{localStorage.setItem('hospital-month-dashboard-v3-20260926',JSON.stringify(data));}catch(e){}}rerender();return clone(data);};
  window.resetMonthDashboard=function(){data=clone(baseData);window.MONTH_DASHBOARD_DATA=data;try{localStorage.removeItem('hospital-month-dashboard-v3-20260926');}catch(e){}rerender();return clone(data);};
  window.openMonthDashboardPanel=openDrawer;
  window.addEventListener('september-revenue-updated',function(){applyRevenueSnapshot();data=clone(baseData);window.MONTH_DASHBOARD_DATA=data;rerender();writeRangeChip();});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
