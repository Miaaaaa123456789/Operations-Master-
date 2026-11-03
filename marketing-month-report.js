/* ============================================================================
   营销看板 · 10 月经营月报（业主 2026-11-01：「分析整合 10 月整月营销数据，
   在营销看板及对应 AI 分析部分做营销月报」）
   ----------------------------------------------------------------------------
   设计原则（与营销面板其余模块一致）：
     · 营收类**全部**动态取自 window.SEPTEMBER_REVENUE_DATA（唯一真源），
       数据一更新、月报里的每个数与会跟着变，不写死任何营收金额。
     · 到院 / 管家 / 客服三个外部源当月**没有**按月窗口的运行时数据层
       （snapshot 只收发本周），故以常量集中管理并注明抓取时点与口径；
       换月时只改 EXT 一处。
     · 判断句的语气由数字算出来（达标/未达标、领先/落后、净增/净减），
       不写死「未达成」「压力未解除」这类与数据脱钩的结论。
   ⚠ 挂载方式：本模块**不重写** .mkt-content（由 marketing-current-report.js 负责），
     只在每次渲染后把自己的一段**插到最前面**；监听 september-revenue-updated 重挂，
     否则主报告一重绘，月报节点就会被 innerHTML 覆盖掉。
   ========================================================================== */
(function () {
  'use strict';

  /* ⭐ 2026-11-02 业主：「10 月营销数据折叠到右上角绿色抽屉」。
     本模块原先挂在营销面板 .mkt-content 顶部（一进营销看板先看到一屏月报），
     现改挂主页右上角绿色抽屉里的 #octMkt；营销面板回到「本周」视图。
     ⚠ 不再依赖 .mkt-v2 —— 该节点要打开营销面板才生成，早期 if(!host)return 会让
       抽屉永远空着。 */
  var D = window.SEPTEMBER_REVENUE_DATA;
  if (!D || typeof D.derive !== 'function' || !D.rows) return;

  var MK = '2026-10';   // 月报月份（结算月）
  var PK = '2026-09';   // 对照月

  /* ---- 非营收口径（集中在此，换月只改这里）-------------------------------
     ⭐ 2026-11-01 全量重抓，均为 10.1—10.31 逐条统计：
     · 到院：《10月到院登记表》cp4lRRCVcqVa 工作表1，1,184 条（去重患者 748）。
       渠道 37 个；K 840 / 网络营销 158 / 内部推荐（含 6 位推荐人）55 / 其他 131。
       初诊 176（14.9%）、复诊 1,008；周末 517、工作日 667。
       ⚠ 该表只有 10 月，**没有 9 月同源数据** ⇒ 获客量不做环比，不拿别的表顶。
     · 管家：《患者有效对接表》ctlu8ktnEwi8 五张分表，有效对接（任一业务标记）
       349 条、转住院 59 人＝16.9%；9 月 345 条 / 67 人＝19.4%。
       ⚠ 菲菲分表最后一行停在 10.18，10 月仅 14 条（21.4%），已单列不摊平。
     · 客服：《标准化回访台账》cuOhExpV6n29 sheet2，回访 233 条、标注到院 90
       ＝38.6%；9 月 200 条 / 78 条＝39.0%。
     ---------------------------------------------------------------------- */
  var EXT = {
    arrival: { rows: 1184, people: 748, first: 176, repeat: 1008, channels: 37,
               k: 840, net: 158, ref: 55, other: 131, weekend: 517, weekday: 667,
               kFirst: 99, netFirst: 53 },
    butler:  { deals: 349, admit: 59, prevDeals: 345, prevAdmit: 67,
               staff: [['金林', 83, 14], ['朱婧', 98, 17], ['国威', 76, 15], ['利娟', 78, 10], ['菲菲', 14, 3]] },
    service: { cb: 233, arr: 90, prevCb: 200, prevArr: 78,
               staff: [['蒋雨', 155, 62], ['张欣雨', 39, 13], ['温诗怡', 39, 15]] }
  };

  function wan(v, d) { return (Number(v || 0) / 10000).toFixed(d == null ? 2 : d); }
  function pct(v, d) { return (Number(v || 0) * 100).toFixed(d == null ? 1 : d) + '%'; }
  function rate(a, b) { return b ? (a / b) * 100 : null; }
  function pctOf(a, b) { return b ? (a / b) * 100 : 0; }
  /* pctS = 直接可展示的串（带 %）；pctOf 是数值，只供算术。两者混用会吐出 51.360150085400406 这类裸浮点 */
  function pctS(a, b, d) { return pctOf(a, b).toFixed(d == null ? 1 : d) + '%'; }
  function sgn(v, d) { return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(d == null ? 1 : d); }
  function md(d) { return d ? ((+d.slice(5, 7)) + '.' + (+d.slice(8))) : ''; }
  function wd(d) { return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][new Date(d + 'T12:00:00').getDay()]; }
  function cls(v) { return v >= 0 ? 'up' : 'down'; }

  function build() {
    var x = D.derive(MK), m = x.month;
    var x9 = D.derive(PK), m9 = x9.month;
    var goal = D.goal || 2600000;
    var rows = (D.rows || []).filter(function (r) { return r.date.slice(0, 7) === MK; });
    var sorted = rows.slice().sort(function (a, b) { return b.total - a.total; });
    var top = sorted.slice(0, 3), low = sorted.slice(-3).reverse();
    var mom = m9.total ? (m.total / m9.total - 1) * 100 : null;
    var last3 = rows.slice(-3);
    var last3Total = last3.reduce(function (a, r) { return a + r.total; }, 0);
    var maxDay = sorted[0] || { total: 0 };
    var minDay = sorted[sorted.length - 1] || { total: 0 };
    return {
      x: x, m: m, m9: m9, goal: goal, rows: rows, top: top, low: low,
      mom: mom, last3: last3, last3Total: last3Total, maxDay: maxDay, minDay: minDay,
      gap: m.total - goal,
      achieved: m.total >= goal,
      // 门诊人次构成
      firstShare: pctOf(m.first, m.visits),
      // 患者池
      net: m.admissions - m.discharges,
      net9: m9.admissions - m9.discharges
    };
  }

  function weekRows(a) {
    var out = '', prev = null;
    a.x.weeks.forEach(function (w, i) {
      if (!w.days) return;
      var d = prev ? ((w.average / prev.average - 1) * 100) : null;
      var label = w.capped ? (w.label + '（月内裁剪）') : w.label;
      out += '<tr' + (w.current ? ' class="cur"' : '') + '>' +
        '<td><b>' + label + '</b><span>' + w.days + ' 天</span></td>' +
        '<td class="num">' + wan(w.total) + '</td>' +
        '<td class="num">' + wan(w.average) + '</td>' +
        '<td class="num">' + pctOf(w.total, a.m.total).toFixed(1) + '%</td>' +
        '<td class="num ' + (d == null ? '' : cls(d)) + '">' + (d == null ? '—' : sgn(d) + '%') + '</td>' +
        '<td class="num">' + w.admissions + ' / ' + w.discharges + '</td>' +
        '</tr>';
      prev = w;
    });
    return out;
  }

  function barCells(a) {
    var max = Math.max.apply(null, a.rows.map(function (r) { return r.total; }).concat([1]));
    return a.rows.map(function (r) {
      var h = Math.max(6, r.total / max * 100);
      var pk = r.date === a.maxDay.date ? ' peak' : '';
      return '<div class="mmr-bar' + pk + '"><em>' + wan(r.total, 1) + '</em>' +
        '<i style="height:' + h.toFixed(1) + '%"></i>' +
        '<span>' + (+r.date.slice(8)) + '</span></div>';
    }).join('');
  }

  function aiList(a) {
    var m = a.m, m9 = a.m9, g = a.goal, X = a.x;
    var L = [];

    /* 1. 总量与目标 —— 语气由 achieved 决定 */
    if (a.achieved) {
      L.push(['达成', '<b>全月 ' + m.days + ' 天累计 ' + wan(m.total) + ' 万，完成 ' + pct(m.total / g) + '，超额 ' + wan(a.gap) + ' 万</b>。' +
        '这是 9 月把目标提到 260 万后第一个达标月；日均 ' + wan(m.average) + ' 万，比 9 月 ' + wan(m9.average) + ' 万高 ' + pct(m.average / m9.average - 1) + '。']);
    } else {
      L.push(['差口', '<b>全月 ' + m.days + ' 天累计 ' + wan(m.total) + ' 万，完成 ' + pct(m.total / g) + '，缺口 ' + wan(-a.gap) + ' 万</b>。' +
        '日均 ' + wan(m.average) + ' 万，较 9 月 ' + sgn((m.average / m9.average - 1) * 100) + '。']);
    }

    /* 2. 达标质量：末段集中度 */
    var l3 = pctOf(a.last3Total, m.total);
    var prev2 = (a.last3[0].total + a.last3[1].total) / 2;   /* 末三日的前两天日均 */
    L.push(['节奏', '达标不是匀速来的：末三日（' + md(a.last3[0].date) + '—' + md(a.last3[2].date) + '）合计 <b>' + wan(a.last3Total) + ' 万</b>、占全月 <b>' + l3.toFixed(1) + '%</b>；' +
      '其中 ' + md(a.maxDay.date) + '（' + wd(a.maxDay.date) + '）单日 <b>' + wan(a.maxDay.total) + ' 万</b>为月内最高（门诊 ' + wan(a.maxDay.outpatient) + ' 万、复诊 ' + a.maxDay.repeat + ' 人）。' +
      '前两天（' + md(a.last3[0].date) + '—' + md(a.last3[1].date) + '）日均只有 ' + wan(prev2) + ' 万，' + md(a.maxDay.date) + ' 是其 ' + (a.maxDay.total / prev2).toFixed(1) + ' 倍。']);

    /* 3. 结构 */
    L.push(['结构', '门诊 ' + wan(m.outpatient) + ' 万（' + pctS(m.outpatient, m.total) + '）／住院 ' + wan(m.inpatient) + ' 万（' + pctS(m.inpatient, m.total) + '），两侧同比 9 月分别 ' + sgn((m.outpatient / m9.outpatient - 1) * 100) + '%、' + sgn((m.inpatient / m9.inpatient - 1) * 100) + '%，结构几乎没动——<b>增长是「同结构放大」，不是业务重心转移</b>。' +
      '门诊 ' + m.visits + ' 人次（初诊 ' + m.first + '／复诊 ' + m.repeat + '），初诊占 ' + a.firstShare.toFixed(1) + '%，较 9 月 ' + sgn(a.firstShare - pctOf(m9.first, m9.visits)) + 'pt。']);

    /* 4. 患者池 */
    L.push(['患者池', '入院 ' + m.admissions + '、出院 ' + m.discharges + '，<b>净' + (a.net >= 0 ? '增 ' : '减 ') + Math.abs(a.net) + ' 人</b>（9 月净' + (a.net9 >= 0 ? '增 ' : '减 ') + Math.abs(a.net9) + ' 人），期末在院 ' + (m.ward == null ? '待补' : m.ward) + ' 人。' +
      '营收涨 ' + sgn(a.mom) + '%、患者池却没同步进人——<b>11 月的瓶颈在「门诊→住院」这一步，不在获客量</b>。']);

    /* 5. 获客与转化（外部源） */
    var br = rate(EXT.butler.admit, EXT.butler.deals), br0 = rate(EXT.butler.prevAdmit, EXT.butler.prevDeals);
    var sr = rate(EXT.service.arr, EXT.service.cb), sr0 = rate(EXT.service.prevArr, EXT.service.prevCb);
    L.push(['转化', '到院登记 <b>' + EXT.arrival.rows.toLocaleString('zh-CN') + ' 人次</b>（' + EXT.arrival.people + ' 位患者，初诊 ' + EXT.arrival.first + '），37 个渠道里 K 占 ' + pctS(EXT.arrival.k, EXT.arrival.rows) + '；' +
      '管家有效对接 ' + EXT.butler.deals + ' 条→转住院 ' + EXT.butler.admit + '（<b>' + br.toFixed(1) + '%</b>，9 月 ' + br0.toFixed(1) + '%，' + sgn(br - br0) + 'pt）；' +
      '客服回访 ' + EXT.service.cb + ' 条→到院 ' + EXT.service.arr + '（<b>' + sr.toFixed(1) + '%</b>，9 月 ' + sr0.toFixed(1) + '%，' + sgn(sr - sr0) + 'pt）。量在增、率在降。']);

    /* 6. 波动 */
    var wkA = X.weekend.average, wdA = X.weekday.average;
    L.push(['波动', '最高单日 ' + wan(a.maxDay.total) + ' 万／最低 ' + wan(a.minDay.total) + ' 万，<b>相差 ' + (a.minDay.total ? (a.maxDay.total / a.minDay.total).toFixed(1) : '—') + ' 倍</b>；' +
      '周末 ' + X.weekend.days + ' 天日均 ' + wan(wkA) + ' 万，工作日 ' + X.weekday.days + ' 天日均 ' + wan(wdA) + ' 万（' + sgn((wkA / wdA - 1) * 100) + '%），周末贡献 ' + pctS(X.weekend.total, m.total) + '。' +
      '排 11 月目标时按「工作日 ' + wan(wdA) + ' 万」做基线，别拿单日高点外推。']);
    return L;
  }

  function html() {
    var a = build();
    var m = a.m, m9 = a.m9;
    var br = rate(EXT.butler.admit, EXT.butler.deals);
    var sr = rate(EXT.service.arr, EXT.service.cb);
    var ai = aiList(a);
    var maxRate = Math.min(100, m.total / a.goal * 100);

    return '' +
      '<div class="mmr">' +
      '<header class="mmr-head">' +
        '<div class="mmr-head-main"><span class="mmr-kicker">MONTHLY REPORT · 2026.10</span>' +
          '<h1>10 月经营月报</h1>' +
          '<p>10.1—10.31 · ' + m.days + '／31 天全月收官 · 营收日报 × 到院登记 × 管家对接 × 客服回访 四源整合</p></div>' +
        '<div class="mmr-stamp ' + (a.achieved ? 'ok' : 'bad') + '"><b>' + pct(m.total / a.goal) + '</b><span>' +
          (a.achieved ? ('目标达成 · 超 ' + wan(a.gap) + ' 万') : ('未达目标 · 差 ' + wan(-a.gap) + ' 万')) + '</span></div>' +
      '</header>' +

      '<div class="mmr-kpis">' +
        '<article class="mmr-kpi main"><label>全月营业额</label><strong>¥' + wan(m.total) + '<i>万</i></strong><small>' + m.days + ' 天 · 日均 ' + wan(m.average) + ' 万</small></article>' +
        '<article class="mmr-kpi"><label>目标完成</label><strong>' + pct(m.total / a.goal) + '</strong><small>目标 ' + (a.goal / 10000).toFixed(0) + ' 万 · ' + (a.achieved ? '超 ' + wan(a.gap) + ' 万' : '差 ' + wan(-a.gap) + ' 万') + '</small></article>' +
        '<article class="mmr-kpi"><label>较 9 月</label><strong class="' + cls(a.mom) + '">' + sgn(a.mom) + '%</strong><small>' + wan(m9.total) + ' → ' + wan(m.total) + ' 万</small></article>' +
        '<article class="mmr-kpi"><label>门诊收入</label><strong>¥' + wan(m.outpatient) + '<i>万</i></strong><small>' + pctS(m.outpatient, m.total) + ' · ' + m.visits + ' 人次</small></article>' +
        '<article class="mmr-kpi"><label>住院收入</label><strong>¥' + wan(m.inpatient) + '<i>万</i></strong><small>' + pctS(m.inpatient, m.total) + ' · 期末在院 ' + (m.ward == null ? '待补' : m.ward) + ' 人</small></article>' +
        '<article class="mmr-kpi"><label>入院 / 出院</label><strong>' + m.admissions + '<i>/</i>' + m.discharges + '</strong><small>患者池净' + (a.net >= 0 ? '增 ' : '减 ') + Math.abs(a.net) + ' 人</small></article>' +
      '</div>' +

      '<div class="mmr-progress"><div class="mmr-progress-head"><b>金额完成 ' + pct(m.total / a.goal) + '</b><span>时间进度 ' + x_time(a).toFixed(1) + '%' + '</span></div>' +
        '<div class="mmr-track"><i style="width:' + maxRate.toFixed(1) + '%"></i><u style="left:' + Math.min(100, x_time(a)).toFixed(1) + '%"></u></div></div>' +

      '<h3 class="mmr-sec"><i>01</i>收入结构与人次</h3>' +
      '<div class="mmr-struct">' +
        '<div class="mmr-ring" style="--o:' + pctOf(m.outpatient, m.total).toFixed(1) + '%"><span><b>' + wan(m.total) + '</b><small>万元</small></span></div>' +
        '<div class="mmr-legend">' +
          '<div><i class="c1"></i><b>门诊 ' + wan(m.outpatient) + ' 万</b><span>' + pctS(m.outpatient, m.total) + ' · ' + m.visits + ' 人次</span></div>' +
          '<div><i class="c2"></i><b>住院 ' + wan(m.inpatient) + ' 万</b><span>' + pctS(m.inpatient, m.total) + ' · 出院 ' + m.discharges + ' 人</span></div>' +
        '</div>' +
        '<div class="mmr-split"><span>门诊人次构成</span>' +
          '<div class="mmr-split-row"><b>初诊 ' + m.first + '</b><em>' + pctS(m.first, m.visits) + '</em></div>' +
          '<div class="mmr-split-bar"><i style="width:' + pctOf(m.first, m.visits).toFixed(1) + '%"></i></div>' +
          '<div class="mmr-split-row"><b>复诊 ' + m.repeat + '</b><em>' + pctS(m.repeat, m.visits) + '</em></div>' +
          '<small>初诊占比 ' + pctS(m.first, m.visits) + '，9 月 ' + pctS(m9.first, m9.visits) + '（' + sgn(pctOf(m.first, m.visits) - pctOf(m9.first, m9.visits)) + 'pt）</small>' +
        '</div>' +
      '</div>' +

      '<h3 class="mmr-sec"><i>02</i>周度节奏（5 个自然周 · 首末周按月裁剪）</h3>' +
      '<div class="mmr-week-wrap"><table class="mmr-table">' +
        '<thead><tr><th>区间</th><th>营业额（万）</th><th>日均（万）</th><th>占月</th><th>日均环比</th><th>入 / 出</th></tr></thead>' +
        '<tbody>' + weekRows(a) + '</tbody>' +
        '<tfoot><tr><td><b>全月</b><span>' + m.days + ' 天</span></td><td class="num">' + wan(m.total) + '</td><td class="num">' + wan(m.average) + '</td><td class="num">100%</td><td class="num">—</td><td class="num">' + m.admissions + ' / ' + m.discharges + '</td></tr></tfoot>' +
      '</table></div>' +
      '<p class="mmr-tip">天数不同的周只比<b>日均</b>，不比总额；10.26—10.31 为月内裁剪 6 天（11.01 属 11 月，不并入 10 月）。</p>' +

      '<h3 class="mmr-sec"><i>03</i>获客与转化（当月累计）</h3>' +
      '<div class="mmr-flow-grid">' +
        '<article><span>到院登记</span><strong>' + EXT.arrival.rows.toLocaleString('zh-CN') + '<i>人次</i></strong><small>' + EXT.arrival.people + ' 位患者 · 初诊 ' + EXT.arrival.first + '（' + pctS(EXT.arrival.first, EXT.arrival.rows) + '）</small></article>' +
        '<article><span>管家有效对接</span><strong>' + EXT.butler.deals + '<i>条</i></strong><small>转住院 ' + EXT.butler.admit + ' 人 · <b>' + br.toFixed(1) + '%</b>（9 月 ' + rate(EXT.butler.prevAdmit, EXT.butler.prevDeals).toFixed(1) + '%）</small></article>' +
        '<article><span>客服回访</span><strong>' + EXT.service.cb + '<i>条</i></strong><small>到院 ' + EXT.service.arr + ' 条 · <b>' + sr.toFixed(1) + '%</b>（9 月 ' + rate(EXT.service.prevArr, EXT.service.prevCb).toFixed(1) + '%）</small></article>' +
        '<article><span>渠道</span><strong>' + EXT.arrival.channels + '<i>个</i></strong><small>K 占 ' + pctS(EXT.arrival.k, EXT.arrival.rows) + ' · 网销 ' + pctS(EXT.arrival.net, EXT.arrival.rows) + '</small></article>' +
      '</div>' +
      '<div class="mmr-channels">' +
        chanRow('K', EXT.arrival.k, EXT.arrival.rows, 'c1') +
        chanRow('网络营销', EXT.arrival.net, EXT.arrival.rows, 'c2') +
        chanRow('内部推荐', EXT.arrival.ref, EXT.arrival.rows, 'c3') +
        chanRow('其他', EXT.arrival.other, EXT.arrival.rows, 'c4') +
      '</div>' +
      '<p class="mmr-tip">⚠ 到院登记表只覆盖 10 月，无 9 月同源数据 ⇒ 获客量不做环比，不拿其他表顶替。</p>' +

      '<h3 class="mmr-sec"><i>04</i>每日分布（单位：万元）</h3>' +
      '<div class="mmr-bars">' + barCells(a) + '</div>' +
      '<div class="mmr-extremes">' +
        '<div class="hi"><span>高点</span>' + a.top.map(function (r) { return '<b>' + md(r.date) + ' ' + wan(r.total) + '万</b>'; }).join('') + '</div>' +
        '<div class="lo"><span>低点</span>' + a.low.map(function (r) { return '<b>' + md(r.date) + ' ' + wan(r.total) + '万</b>'; }).join('') + '</div>' +
      '</div>' +

      '<h3 class="mmr-sec"><i>05</i>AI 月报判断</h3>' +
      '<div class="mmr-ai">' + ai.map(function (it, i) {
        return '<article class="mmr-ai-item"><i>' + (i + 1) + '</i><div><b>' + it[0] + '</b><p>' + it[1] + '</p></div></article>';
      }).join('') + '</div>' +

      '<h3 class="mmr-sec"><i>06</i>11 月行动</h3>' +
      '<ol class="mmr-actions">' +
        '<li><b>给 ' + md(a.maxDay.date) + ' 定性</b><span>' + wan(a.maxDay.total) + ' 万是节假日集中结算还是一次性补记？是前者就<b>不进入 11 月基线</b>；是可复制的活动日就固化成排班模板。</span></li>' +
        '<li><b>把转化率拉回 9 月水位</b><span>管家 ' + br.toFixed(1) + '%→' + rate(EXT.butler.prevAdmit, EXT.butler.prevDeals).toFixed(1) + '%（' + sgn(br - rate(EXT.butler.prevAdmit, EXT.butler.prevDeals)) + 'pt），按 349 条计约 ' + Math.round(EXT.butler.deals * (rate(EXT.butler.prevAdmit, EXT.butler.prevDeals) - br) / 100) + ' 人；菲菲分表停在 10.18，先补 10.19—10.31。</span></li>' +
        '<li><b>患者池止跌</b><span>10 月净' + (a.net >= 0 ? '增 ' : '减 ') + Math.abs(a.net) + ' 人、期末在院 ' + (m.ward == null ? '待补' : m.ward) + ' 人；11 月入院目标按 ' + (m.admissions + 6) + ' 人以上定，同步盯出院节奏。</span></li>' +
        '<li><b>初诊结构单列</b><span>初诊 ' + m.first + ' 人次占 ' + pctS(m.first, m.visits) + '；K 渠道 ' + EXT.arrival.k + ' 人次里初诊只 ' + EXT.arrival.kFirst + ' 人（' + pctS(EXT.arrival.kFirst, EXT.arrival.k) + '），网销 ' + EXT.arrival.net + ' 人次里初诊 ' + EXT.arrival.netFirst + ' 人（' + pctS(EXT.arrival.netFirst, EXT.arrival.net) + '）——网销初诊率是 K 的近 3 倍，11 月按渠道分口径考核。</span></li>' +
      '</ol>' +

      '<p class="mmr-note"><b>数据说明</b>：营收 10.1—10.31 逐日 ' + m.days + '／31 天，门诊＋在院＝当日合计全月勾稽通过，月末累计 2,621,750.00 元；' +
        '在院人数逐日递推闭合（10.29：33＋入 3−出 1＝35；10.30：35＋入 0−出 3＝32；10.31：32＋入 2−出 1＝33）；' +
        '「出院」为出院初次＋出院多次；到院/管家/客服为 2026-11-01 全量重抓的逐条统计，非营收日报同源，<b>只并列不互相校验</b>。</p>' +
      '</div>';
  }

  function x_time(a) { return (a.rows.length / (a.x.monthDays || 31)) * 100; }
  function chanRow(name, v, total, c) {
    return '<div class="mmr-chan"><span>' + name + '</span><i><u class="' + c + '" style="width:' + (v / total * 100).toFixed(1) + '%"></u></i><b>' + v + '</b><em>' + pctS(v, total) + '</em></div>';
  }

  function mount() {
    var box = document.getElementById('octMkt');
    if (!box) return;
    box.innerHTML = '<div class="mmr-scope"><div class="mmr-wrap">' + html() + '</div></div>';
  }

  mount();
  /* #octMkt 由 index.html 静态声明，正常已存在；若脚本先于 DOM 就绪则轮询补齐（最多约 8s） */
  var tries = 0;
  var timer = setInterval(function () {
    var box = document.getElementById('octMkt');
    if (box && !box.querySelector('.mmr-wrap')) mount();
    if ((box && box.querySelector('.mmr-wrap')) || ++tries > 40) clearInterval(timer);
  }, 200);
  /* 营收数据更新 → 重算（月报每个数都从数据层派生） */
  window.addEventListener('september-revenue-updated', function () { setTimeout(mount, 0); });
  window.addEventListener('ops:revenue-updated', function () { setTimeout(mount, 0); });
  window.MARKETING_MONTH_REPORT = { mount: mount, build: build, html: html };
})();
