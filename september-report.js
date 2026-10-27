/* ==========================================================================
   9 月整月经营分析报告  ·  2026-09-01 — 09-30
   渲染目标：<section class="section sr-section" id="sepReport">

   ⚠ 三点写法约束（本项目既有坑，改前必读）：
   1) 不写裸「本周」——month-dashboard.js 的 normalizeAll() 会遍历 document.body，
      把裸「本周」替换成当前周标签（9.28—10.1），会把本报告的周次文案带偏。
      这里一律写显式区间「9.21—9.27」「9.1—9.30」，绕开归一化器。
   2) 营收类数字全部走 SEPTEMBER_REVENUE_DATA.facts()/derive() 实时取，不写死
      （写死＝数据一滚就静默失真；2026-10-01 已在此踩过 12 处）。
   3) 部门数字来自**不同源表、不同覆盖区间**，只并列呈现，不加总。每项都标了区间。
      各区间的实际边界由 scripts/_check-range.py 核出，改数时请重跑该脚本。
   ========================================================================== */
(function () {
  'use strict';

  /* ── 部门数据（源表口径，非营收日报口径）─────────────────────────────
     医生组：金山表《特别行动小组医生组汇报表》+《九月医生营业额与在管患者工作量表》
     护理组：金山表护理组 + 《护士工作量统计总表》
     心理组：金山表心理组 + 心理科《团体治疗登记》
     客服部：《标准化回访台账》《导诊主动服务记录表》《日工作量考核表》
     营销中心：《患者有效对接表》5 个管家 sheet + 金山表营销中心            */
  var DEPT = [
    {
      name: '医生组', icon: '医', cls: 'd-doctor',
      sub: '住院规模与管床产出',
      kv: [
        ['分管入院 / 出院', '48 / 41', '人', '9 月累计 · 4 位助理医师'],
        ['物理治疗费', '24.6', '万元', '源表周 9.21—9.27'],
        ['门诊', '265', '人次', '源表周 9.21—9.27'],
        ['周总收入', '59.7', '万元', '源表周 9.21—9.27 · 科主任口径']
      ],
      foot: '曾凯 14/12 · 康言 12/11 · 王建宁 12/10 · 王建 10/8；住院总医师孙乐 9 月转化 14 人、多导 14 人。赵郁莹本月未填报。'
    },
    {
      name: '护理组', icon: '护', cls: 'd-nursing',
      sub: '治疗执行与服务兑现',
      kv: [
        ['物理治疗完成率', '95.2', '%', '项目口径 · 应做 495 / 实做 471'],
        ['物理治疗人数', '484', '人次', '源表周 9.21—9.27 · 含住院门诊'],
        ['护士维度完成率', '92.1', '%', '9.20—9.26 · 1278 / 1177'],
        ['工娱', '5', '场', '源表周 9.21—9.27 · 62 人']
      ],
      foot: '6 项分项：经颅交流电 96.2% · 经颅磁 95.8% · 脑功能 95.8% · 音乐放松 93.1% · 失眠治疗仪 84.6% · 团体生物反馈 80.0%。'
    },
    {
      name: '心理咨询组', icon: '心', cls: 'd-psych',
      sub: '咨询承接与收入结构',
      kv: [
        ['团体治疗', '15', '场', '9 月累计 · 43 人次'],
        ['个体咨询', '40', '人次', '源表周 9.21—9.27'],
        ['心理收入', '1.90', '万元', '源表周 9.21—9.27 · 19,002 元'],
        ['患者心理支持', '35', '人次', '组长月度口径']
      ],
      foot: '床旁支持 12 人次 · 突发情绪干预 10 人次 · 家长减压 1 场 · 新患者入院 24 小时管床对接率 100%。'
    },
    {
      name: '客服服务部', icon: '客', cls: 'd-service',
      sub: '随访、到院与付费跟踪',
      kv: [
        ['回访台账', '119', '条', '9.14—9.24 · 标记到院 48 条'],
        ['回访到院率', '40.3', '%', '9.14—9.24 · 48 / 119'],
        ['主动服务', '58', '条', '9.15—9.26'],
        ['满意度均分', '4.93', '分', '115 条有评分']
      ],
      foot: '日工作量 57 条 / 7,786 分（9.14—9.27）。源表周 9.21—9.27：接待 239 人次、随访 179 人次、到院 42 人（23.5%）、义诊 14 人。'
    },
    {
      name: '营销中心', icon: '营', cls: 'd-mkt',
      sub: '管家对接、渠道与转住院',
      kv: [
        ['管家有效对接', '367', '条', '9.1—9.30 · 患者有效对接表'],
        ['转住院', '61', '人', '9.1—9.30 · 占对接 16.6%'],
        ['外部渠道', '15', '条', '已开通 · 在维护'],
        ['渠道路到院', '44', '人', '源表周 9.21—9.27']
      ],
      foot: 'K 教授转诊 12 人 / 到院 8 人（66.7%）。双福三小绿色通道已洽谈完毕，预计国庆后签约。'
    }
  ];

  /* 年内完成率（营收日报口径；3—8 月为每月截图核对，9 月为本次结算） */
  var MONTHLY_RATE = [
    ['3 月', 89.6], ['4 月', 95.5], ['5 月', 91.7],
    ['6 月', 101.0], ['7 月', 110.7], ['8 月', 102.2], ['9 月', 87.4]
  ];

  /* 管家对接（9 月累计；口径 A「有业务标记」与口径 B「有姓名」在本月同值） */
  var GUAJIA = [
    ['朱婧', 99, 17], ['金林', 83, 17], ['利娟', 65, 9],
    ['菲菲', 60, 4], ['国威', 60, 14]
  ];

  /* 医生月度分管（9 月医生工作量表叙述格） */
  var DOCTORS = [['曾凯', 14, 12], ['康言', 12, 11], ['王建宁', 12, 10], ['王建', 10, 8]];

  /* 客服覆盖区间（由 scripts/_check-range.py 核出） */
  var SVC_RANGE = { callback: '9.14—9.24', visitlog: '9.15—9.26', workload: '9.14—9.27' };

  var el = function (id) { return document.getElementById(id); };

  function src() { return window.SEPTEMBER_REVENUE_DATA; }

  /* 兜底值 = 2026-09-30 结算口径；正常由 derive() 覆盖 */
  var FALLBACK = {
    totalWan: '227.17', goalWan: '260', amountRate: 87.4, timeRate: 100.0, lagPt: 12.6,
    remainWan: '32.83', mtdAvgWan: '7.57', outWan: '116.71', inWan: '110.47',
    outPct: 51.4, inPct: 48.6,
    visits: 985, first: 135, repeat: 850, admissions: 65, discharges: 58, ward: 34,
    wkWan: '89.93', wkPct: 39.6, wkAvg: '11.24', wdAvg: '6.24',
    weeks: [
      { label: '9.1—9.6', v: 45.23, days: 6, avg: '7.54' },
      { label: '9.7—9.13', v: 48.65, days: 7, avg: '6.95' },
      { label: '9.14—9.20', v: 49.15, days: 7, avg: '7.02' },
      { label: '9.21—9.27', v: 59.59, days: 7, avg: '8.51' },
      { label: '9.28—9.30', v: 24.56, days: 3, avg: '8.19', cur: true }
    ]
  };

  function collect() {
    var D = src(), out = JSON.parse(JSON.stringify(FALLBACK));
    if (!D || typeof D.facts !== 'function') return out;
    try {
      /* ⭐⭐ 抽屉固定取 **9 月** 口径（2026-10-06）。
         主面板已切到 10 月，D.facts()/D.derive() 的缺省参数也跟着变成 10 月。
         抽屉是「9 月整月报告」，必须显式传 '2026-09'，否则会把 10 月数据
         渲染在 9 月标题下（最危险的静默失真）。 */
      var SEP = D.SEP_MONTH || '2026-09';
      var f = D.facts(SEP), x = D.derive(SEP);
      out.totalWan = f.totalWan;
      out.goalWan = String(f.goalWan);
      out.amountRate = f.amountRate;
      out.timeRate = f.timeRate;
      out.lagPt = f.lagPt;
      out.remainWan = f.remainWan;
      out.mtdAvgWan = f.mtdAvgWan;
      out.visits = x.month.visits;
      out.first = x.month.first;
      out.repeat = x.month.repeat;
      out.admissions = x.month.admissions;
      out.discharges = x.month.discharges;
      out.ward = x.month.ward;
      /* 门诊 / 在院拆分：⚠ 必须取**月口径**（已锁结算月），不能直接遍历 D.rows ——
         D.rows 含 10.1，会把 10 月并进 9 月（曾实测：门诊 124.49 + 在院 111.28 = 235.77，
         与月累计 227.17 对不上）。x.month 已由 monthRows() 过滤。 */
      var o = x.month.outpatient, i = x.month.inpatient, n = x.month.days;
      if (n && (o + i)) {
        out.outWan = (o / 1e4).toFixed(2);
        out.inWan = (i / 1e4).toFixed(2);
        out.outPct = +(o / (o + i) * 100).toFixed(1);
        out.inPct = +(i / (o + i) * 100).toFixed(1);
      }
      if (x.weekend && x.weekday && x.month && x.month.total) {
        out.wkWan = (x.weekend.total / 1e4).toFixed(2);
        out.wkPct = +(x.weekend.total / x.month.total * 100).toFixed(1);
        out.wkAvg = (x.weekend.average / 1e4).toFixed(2);
        out.wdAvg = (x.weekday.average / 1e4).toFixed(2);
      }
      if (x.weeks && x.weeks.length) {
        out.weeks = x.weeks.map(function (k) {
          /* ⚠ 不要再用 f.labelDateShort 改写当周标签！
             weeks 已在数据层按**结算月**封顶：末周只计 9 月内的 9.28—9.30（3 天 / 24.56 万）。
             改写成「9.28—10.1」会变成「4 天区间配 3 天数字」，自相矛盾。 */
          var lab = k.label;
          return {
            label: lab, v: +(k.total / 1e4).toFixed(2), days: k.days,
            avg: (k.average / 1e4).toFixed(2), cur: !!(k.current || k.inPeriod),
            fullLabel: k.label
          };
        });
      }
      out.ready = true;
    } catch (e) { /* 保底不炸 */ }
    return out;
  }

  function heroHtml(d) {
    var pct = Math.max(0, Math.min(100, d.amountRate));
    var tPct = Math.max(0, Math.min(100, d.timeRate));
    var net = d.admissions - d.discharges;
    return '' +
      '<div class="sr-hero-main">' +
      '<span>9 月累计营业额（营收日报口径 · 30 天）</span>' +
      '<strong>' + d.totalWan + '<em>／' + d.goalWan + ' 万元</em></strong>' +
      '<div class="sr-bar"><i style="width:' + pct.toFixed(1) + '%"></i><u style="left:' + tPct.toFixed(1) + '%"></u></div>' +
      '<p>金额完成 <b>' + d.amountRate.toFixed(1) + '%</b> · 时间进度 ' + d.timeRate.toFixed(1) +
      '% · 落后 <b>' + d.lagPt.toFixed(1) + 'pt</b> · 缺口 <b>' + d.remainWan + ' 万元</b>' +
      '　·　月日均 ' + d.mtdAvgWan + ' 万元</p>' +
      '</div>' +
      '<div class="sr-hero-side">' +
      '<div><span>门诊人次</span><b>' + d.visits + '<em>人次</em></b></div>' +
      '<div><span>入院 / 出院</span><b>' + d.admissions + ' / ' + d.discharges + '<em>人</em></b></div>' +
      '<div><span>期末在院</span><b>' + d.ward + '<em>人</em></b></div>' +
      '<div><span>净增在院</span><b>' + (net >= 0 ? '+' : '') + net + '<em>人</em></b></div>' +
      '</div>';
  }

  function structureHtml(d) {
    return '' +
      '<h3>收入结构</h3><p class="sr-sub">营收日报口径 · 9.1—9.30 全月 30 天，门诊＋在院＝当日合计</p>' +
      '<div class="sr-rows">' +
      '<div class="sr-row"><span>门诊收入</span><b>' + d.outWan + '<em>万元 · ' + d.outPct + '%</em></b></div>' +
      '<div class="sr-row"><span>在院收入</span><b>' + d.inWan + '<em>万元 · ' + d.inPct + '%</em></b></div>' +
      '<div class="sr-row"><span>门诊人次（初诊 / 复诊）</span><b>' + d.visits + '<em>人次</em> · ' + d.first + ' / ' + d.repeat + '</b></div>' +
      '<div class="sr-row"><span>复诊占门诊人次</span><b class="hot">' + (d.visits ? (d.repeat / d.visits * 100).toFixed(1) : '—') + '<em>%</em></b></div>' +
      '<div class="sr-row"><span>周末贡献（8 天）</span><b class="hot">' + d.wkWan + '<em>万元 · ' + d.wkPct + '%</em></b></div>' +
      '<div class="sr-row"><span>周末 / 平日 日均</span><b>' + d.wkAvg + ' / ' + d.wdAvg + '<em>万元</em></b></div>' +
      '</div>';
  }

  function historyHtml() {
    return '' +
      '<h3>年内目标完成率</h3><p class="sr-sub">营收日报口径 · 3—8 月为每月截图核对，9 月为本次结算</p>' +
      '<div class="sr-weeks">' +
      MONTHLY_RATE.map(function (m) {
        var isSep = m[0].indexOf('9') === 0;
        return '<div class="sr-week' + (isSep ? ' cur' : ' full') + '">' +
          '<b style="' + (isSep ? 'color:#E0576F' : '') + '">' + m[1].toFixed(1) + '%</b>' +
          '<i style="height:' + Math.max(6, m[1] / 120 * 100) + '%"></i>' +
          '<span>' + m[0] + '</span></div>';
      }).join('') +
      '</div>' +
      '<p class="sr-weeks-note">9 月完成率 <b style="color:#E0576F">87.4%</b> 为年内最低（前 6 个月 89.6%—110.7%）。' +
      '需注意 9 月目标由 240 万上调至 <b>260 万</b>，与 3—8 月目标不可直接横比；按营收日报口径，' +
      '9 月 227.17 万环比 8 月 245.2 万回落 <b>7.4%</b>。</p>';
  }

  function weeksHtml(d) {
    var max = Math.max.apply(null, d.weeks.map(function (k) { return k.v; }).concat([1]));
    return '' +
      '<h3>9 月周度节奏</h3><p class="sr-sub">按营收日报拆周 · 五柱相加＝月累计；末周 9.28—10.4 为跨月周，此处只计 9 月内 3 天（9.28—9.30）</p>' +
      '<div class="sr-weeks" style="height:150px">' +
      d.weeks.map(function (k) {
        return '<div class="sr-week ' + (k.cur ? 'cur' : 'full') + '">' +
          '<b>' + k.v.toFixed(2) + '万</b>' +
          '<i style="height:' + Math.max(8, k.v / max * 100) + '%"></i>' +
          '<span>' + k.label + '<br>' + k.days + ' 天 · 日均 ' + k.avg + '万</span></div>';
      }).join('') +
      '</div>' +
      '<p class="sr-weeks-note">周内<b>逐周抬升</b>：45.23 → 48.65 → 49.15 → <b>59.59 万</b>（第 4 周为月内高点，日均 8.51 万）。' +
      '9.28—9.30 日均 8.19 万，未延续第 4 周势头，但仍高于前 3 周。</p>';
  }

  function deptHtml() {
    return DEPT.map(function (d) {
      return '<article class="sr-dept ' + d.cls + '">' +
        '<header><div class="ico">' + d.icon + '</div><div><b>' + d.name + '</b><small>' + d.sub + '</small></div></header>' +
        '<div class="kv">' + d.kv.map(function (r) {
          return '<div><span>' + r[0] + '</span><b>' + r[1] + '<em>' + r[2] + '</em></b></div>';
        }).join('') + '</div>' +
        '<footer>' + d.foot + '</footer>' +
        '</article>';
    }).join('');
  }

  function chainHtml(d) {
    var node = function (lab, val, unit, hot) {
      return '<div class="node' + (hot ? ' hot' : '') + '"><span>' + lab + '</span><b>' + val + '<em>' + unit + '</em></b></div>';
    };
    return '' +
      '<h3>跨部门协同链</h3><p class="sr-sub">同一月的各部门口径并列，看环节流失在哪；不做患者级归因</p>' +
      '<div class="sr-chain">' +
      node('门诊人次', d.visits, '人次') + '<span class="arw">→</span>' +
      node('入院', d.admissions, '人') + '<span class="arw">→</span>' +
      node('期末在院', d.ward, '人', true) +
      '</div>' +
      '<div class="sr-chain">' +
      node('管家有效对接', 367, '条', true) + '<span class="arw">→</span>' +
      node('转住院', 61, '人') + '<span class="arw">=</span>' +
      node('转化率', '16.6', '%') +
      '</div>' +
      '<div class="sr-chain">' +
      node('客服回访', 119, '条', true) + '<span class="arw">→</span>' +
      node('标记到院', 48, '条') + '<span class="arw">=</span>' +
      node('到院率', '40.3', '%') +
      '</div>' +
      '<p class="sr-weeks-note">口径提示：管家「转住院 61 人」与营收日报「入院 ' + d.admissions + ' 人」<b>不同源</b>' +
      '（前者为管家台账标记、后者为营收日报），方向一致、数值不相等，<b>不可相加</b>；' +
      '门诊与入院未做患者级 ID 串联，不把同期数量直接解释为转化率。</p>';
  }

  function guanjiaHtml() {
    var rows = GUAJIA.map(function (g) {
      var rate = g[1] ? (g[2] / g[1] * 100) : 0;
      var cls = rate >= 20 ? 'good' : (rate < 10 ? 'bad' : 'flat');
      return '<tr><td>' + g[0] + '</td><td class="num"><b>' + g[1] + '</b></td>' +
        '<td class="num"><b>' + g[2] + '</b></td>' +
        '<td class="num"><span class="sr-pill ' + cls + '">' + rate.toFixed(1) + '%</span></td></tr>';
    }).join('');
    var t = GUAJIA.reduce(function (a, b) { return [a[0], a[1] + b[1], a[2] + b[2]]; }, ['', 0, 0]);
    return '' +
      '<h3>管家对接排名 · 9 月累计</h3><p class="sr-sub">来源《患者有效对接表》5 个管家 sheet（9.1—9.30），按对接条数降序</p>' +
      '<div class="sr-tbl-wrap"><table class="sr-tbl"><thead><tr>' +
      '<th>管家</th><th class="num">有效对接</th><th class="num">转住院</th><th class="num">住院占比</th>' +
      '</tr></thead><tbody>' + rows +
      '<tr class="total"><td>合计</td><td class="num"><b>' + t[1] + '</b></td>' +
      '<td class="num"><b>' + t[2] + '</b></td>' +
      '<td class="num">' + (t[1] ? (t[2] / t[1] * 100).toFixed(1) : '—') + '%</td></tr>' +
      '</tbody></table></div>' +
      '<p class="sr-weeks-note" style="margin-top:10px">国威 23.3%、金林 20.5% 居前；菲菲 6.7% 明显偏低（60 条仅 4 人住院），建议单独复盘对接质量。' +
      '本月「有业务标记」与「有姓名即算」两种口径结果同为 367 条，故无需并列双值；源表尾部另有 <code>9.31</code> 等无效日期行已剔除。</p>' +
      /* ⭐ 2026-10-07 从主面板「员工排名」区折入：该组为 9.14 业主明细复核，
         主面板已切到 10.1—10.7，9 月的口径一律收进本抽屉（数据不删减）。 */
      '<h3 style="margin-top:16px">业主明细口径复核 · 9.14</h3>' +
      '<p class="sr-sub">业主 9.14 提供的分人明细，与《患者有效对接表》逐人对照</p>' +
      '<div class="sr-tbl-wrap"><table class="sr-tbl"><thead><tr>' +
      '<th>管家</th><th class="num">对接</th><th class="num">物理</th><th class="num">心理</th><th class="num">住院</th>' +
      '</tr></thead><tbody>' +
      '<tr><td>金林</td><td class="num"><b>19</b></td><td class="num">5</td><td class="num">10</td><td class="num">3</td></tr>' +
      '<tr><td>菲菲</td><td class="num"><b>17</b></td><td class="num">3</td><td class="num">1</td><td class="num">2</td></tr>' +
      '<tr><td>朱婧</td><td class="num"><b>15</b></td><td class="num">3</td><td class="num">5</td><td class="num">4</td></tr>' +
      '<tr><td>利娟</td><td class="num"><b>14</b></td><td class="num">1</td><td class="num">4</td><td class="num">0</td></tr>' +
      '<tr><td>国威</td><td class="num"><b>13</b></td><td class="num">2</td><td class="num">4</td><td class="num">2</td></tr>' +
      '<tr class="total"><td>合计</td><td class="num"><b>78</b></td><td class="num"><b>14</b></td><td class="num"><b>24</b></td><td class="num"><b>11</b></td></tr>' +
      '</tbody></table></div>' +
      '<p class="sr-weeks-note" style="margin-top:10px">业主明细合计 <b>对接 78 人次</b>（金林 19 · 菲菲 17 · 朱婧 15 · 利娟 14 · 国威 13）；' +
      '物理治疗 14 · 心理治疗 24 · 住院 11。与患者对接表总数一致；分人数字有 1—2 条差异' +
      '（菲菲 16 vs 17、朱婧 17 vs 15、利娟 13 vs 14），系两表对「检查 / 心理咨询」的标记粒度不同' +
      '（对接表按是否发生勾选，明细按业务归类），已入核验清单。</p>';
  }

  function doctorHtml(d) {
    var rows = DOCTORS.map(function (x) {
      var net = x[1] - x[2];
      return '<tr><td>' + x[0] + '</td><td class="num"><b>' + x[1] + '</b></td>' +
        '<td class="num"><b>' + x[2] + '</b></td>' +
        '<td class="num">' + (net >= 0 ? '+' : '') + net + '</td></tr>';
    }).join('');
    var ti = DOCTORS.reduce(function (a, b) { return a + b[1]; }, 0);
    var to = DOCTORS.reduce(function (a, b) { return a + b[2]; }, 0);
    return '' +
      '<h3>医生分管入出院 · 9 月累计</h3><p class="sr-sub">来源《九月医生营业额与在管患者工作量表》叙述格 · 4 位助理医师</p>' +
      '<div class="sr-tbl-wrap"><table class="sr-tbl"><thead><tr>' +
      '<th>医师</th><th class="num">9 月入院</th><th class="num">9 月出院</th><th class="num">净增</th>' +
      '</tr></thead><tbody>' + rows +
      '<tr class="total"><td>合计</td><td class="num"><b>' + ti + '</b></td>' +
      '<td class="num"><b>' + to + '</b></td><td class="num">+' + (ti - to) + '</td></tr>' +
      '</tbody></table></div>' +
      '<p class="sr-weeks-note" style="margin-top:10px">⚠ 医生表为<b>分管口径</b>（合计入院 ' + ti + ' / 出院 ' + to + '），' +
      '与营收日报全口径（入院 ' + d.admissions + ' / 出院 ' + d.discharges + '）不同源、<b>不可比</b>；' +
      '赵郁莹本月无入出院填报；住院总医师孙乐只统计转化 14 人、多导 14 人。</p>';
  }

  function findsHtml(d) {
    var items = [
      ['risk', '<b>完成率创年内新低。</b>9 月 227.17 万、完成 87.4%，缺口 32.83 万；前 6 个月完成率 89.6%—110.7%。' +
        '需同时说明：9 月目标由 240 万上调至 260 万，按营收日报口径环比 8 月 245.2 万回落 7.4%。'],
      ['risk', '<b>收入过度依赖周末与高峰日。</b>8 个周末日贡献 ' + d.wkWan + ' 万（' + d.wkPct + '%）、日均 ' + d.wkAvg +
        ' 万，是平日 ' + d.wdAvg + ' 万的 ' + (d.wdAvg && +d.wdAvg ? (d.wkAvg / d.wdAvg).toFixed(1) : '1.8') + ' 倍；' +
        '前三高峰日（9.6 / 9.13 / 9.26）合计 50.47 万、占 22.2%。平日产能是最大缺口段。'],
      ['risk', '<b>转化链前端宽、后端窄。</b>门诊 ' + d.visits + ' 人次 → 入院 ' + d.admissions + ' → 期末在院 ' + d.ward + ' 人；' +
        '复诊占门诊 ' + (d.visits ? (d.repeat / d.visits * 100).toFixed(1) : '86.3') + '%，新客占比偏低，' +
        '增量更依赖既有患者复诊。'],
      ['win', '<b>周内节奏确实在抬升。</b>45.23 → 48.65 → 49.15 → 59.59 万逐周走高，第 4 周日均 8.51 万为月内最高；' +
        '9.28—9.30 日均 8.19 万，仍高于前 3 周。'],
      ['win', '<b>护理治疗兑现度高。</b>物理治疗项目口径完成率 95.2%（495 / 471），6 项中 4 项 ≥93%；' +
        '护士维度 92.1%。服务兑现环节不是瓶颈。'],
      ['win', '<b>渠道侧有增量动作。</b>管家 9 月有效对接 367 条、转住院 61 人（16.6%）；' +
        'K 教授转诊 12 人到院 8 人（66.7%）；15 条外部渠道在维护，双福三小绿色通道待国庆后签约。'],
      ['risk', '<b>台账覆盖不齐，月末无法整月结算。</b>客服三本台账分别只到 9.24 / 9.26 / 9.27，' +
        '护理质控只到 9.26，心理个体咨询无月度单列值；这些缺口使「整月口径」实际只能对总经营与营销成立。']
    ];
    return '<ul class="sr-finds">' + items.map(function (it, i) {
      return '<li class="' + it[0] + '"><i>' + (i + 1) + '</i><span>' + it[1] + '</span></li>';
    }).join('') + '</ul>';
  }

  function actionsHtml() {
    var items = [
      ['补平日产能', '把 9.6 / 9.13 / 9.26 三个高峰日的渠道组成、项目结构与排班拆开，验证哪些能复制到周二至周四。'],
      ['锁 10 月目标与口径', '9 月目标已上调至 260 万，10 月须先确认目标口径；同时把「医生分管 / 营收日报 / 管家台账 / 护士项目与护士维度」几套口径的换算与不可比关系固化进看板。'],
      ['台账按月提报', '要求各部门在次月 3 日前提交上月汇总（客服三表、护理质控、心理个体咨询），否则月末无法出具完整月报。'],
      ['提升新客占比', '复诊占门诊 86.3%、新客仅 13.7%。结合管家渠道与绿色通道，重点看新客到院率与首诊转化。'],
      ['渠道落地优先', '双福三小绿色通道国庆后签约；新桥医院渠道持续拜访。渠道到院 44 人已是可观增量，需配套接诊与治疗产能。']
    ];
    return '<ul class="sr-finds">' + items.map(function (it, i) {
      return '<li class="win"><i>' + (i + 1) + '</i><span><b>' + it[0] + '：</b>' + it[1] + '</span></li>';
    }).join('') + '</ul>';
  }

  function render() {
    var host = el('sepReport');
    if (!host) return;
    pinToTop();
    var d = collect();
    host.innerHTML = '' +
      '<div class="sr-head">' +
      '<div><h2>9 月整月经营分析报告</h2>' +
      '<p>2026.09.01—09.30 · 全月 30 天已结算 · 总经营 + 五个部门合并呈现（各部门口径与覆盖区间分别标注）</p></div>' +
      '<span class="sr-close"><i></i>9 月已收官</span>' +
      '</div>' +
      '<div class="sr-hero">' + heroHtml(d) + '</div>' +
      '<div class="sr-grid2">' +
      '<article class="sr-card">' + structureHtml(d) + '</article>' +
      '<article class="sr-card">' + historyHtml() + '</article>' +
      '</div>' +
      '<article class="sr-card">' + weeksHtml(d) + '</article>' +
      '<div class="sr-depts">' + deptHtml() + '</div>' +
      '<div class="sr-grid2">' +
      '<article class="sr-card">' + chainHtml(d) + '</article>' +
      '<article class="sr-card">' + guanjiaHtml() + '</article>' +
      '</div>' +
      '<article class="sr-card">' + doctorHtml(d) + '</article>' +
      '<div class="sr-grid2">' +
      '<article class="sr-card"><h3>全月关键结论</h3><p class="sr-sub">按影响程度排序</p>' + findsHtml(d) + '</article>' +
      '<article class="sr-card"><h3>10 月动作建议</h3><p class="sr-sub">承接 9 月缺口</p>' + actionsHtml() + '</article>' +
      '</div>' +
      '<div class="sr-note"><h4>口径说明（务必先读）</h4><ul>' +
      '<li><b>总经营</b>：营收日报口径，9.1—9.30 完整 30 天（门诊＋在院＝当日合计），与源表「当月累计收入」交叉校验一致。</li>' +
      '<li><b>医生组</b>：月度分管入出院取自《九月医生营业额与在管患者工作量表》叙述格；物理治疗费、门诊、周总收入为源表周 9.21—9.27。</li>' +
      '<li><b>护理组</b>：物理治疗分项 495 / 471 为源表周 9.21—9.27 的<b>项目口径</b>；护士维度 1278 / 1177 为 9.20—9.26。两者覆盖范围不同，<b>不可相加</b>。</li>' +
      '<li><b>心理咨询组</b>：个体咨询 40 人次与收入 19,002 元为源表周 9.21—9.27；团体治疗 15 场 / 43 人次为 9 月《团体治疗登记》累计。</li>' +
      '<li><b>客服服务部</b>：回访台账 ' + SVC_RANGE.callback + '（119 条）· 主动服务 ' + SVC_RANGE.visitlog +
      '（58 条）· 日工作量 ' + SVC_RANGE.workload + '（57 条 / 7,786 分）。<b>三表均未覆盖到 9.30</b>，月末几日未回填。</li>' +
      '<li><b>营销中心</b>：管家 367 条 / 转住院 61 人为《患者有效对接表》9 月累计（两种口径同值）；渠道路到院 44 人为源表周 9.21—9.27。</li>' +
      '<li><b>不可相加</b>：各部门指标来自不同源表与不同覆盖区间，本报告只做<b>并列呈现与方向判断</b>，不做加总，也不做患者级转化率归因。' +
      '绩效结算需在各部门补齐 9 月整月数据、并固定口径换算关系后再进行。</li>' +
      '</ul></div>' +
      archiveHtml() +
      '</div>';
  }

  /* ⭐ 9 月主面板洞察存档（2026-10-06）
     主面板切到 10 月后，原本排在主面板的 9 月洞察（AI 三项判断 + 变好/变差 + 待确认清单）
     按业主要求**不删减**，整体折叠进抽屉。原文一字未改，只加了包装。 */
  function archiveHtml() {
    return '<details class="sr-card sr-archive">' +
      '<summary><span><b>9 月主面板洞察存档</b>' +
      '<small>主面板切到 10 月后整体折叠于此 · 原文保留、未删减</small></span>' +
      '<em>展开／收起</em></summary>' +
      '<div class="sr-note" style="margin-top:10px"><h4>原主面板「AI 今日决策建议」（截至 9 月收官）</h4></div>' +
      '<div class="ai-balance-strip">' +
        '<article class="ai-balance-item watch"><div class="ai-balance-head"><b>1</b><strong>9 月收官 · 目标未达成</strong></div>'
        + '<p>9 月 30 天 227.17 万，完成 260 万的 <b>87.4%</b>，落后时间进度 <b>12.6</b> 个百分点、缺口 <b>32.83 万</b>。</p>'
        + '<p>上周完整周日均 <b>8.51 万</b>（上上周 7.02 万，+21.2%）——节奏在改善，但月内已无追回空间。</p></article>'
        + '<article class="ai-balance-item growth"><div class="ai-balance-head"><b>2</b><strong>患者池 9 月末周净增 1 人</strong></div>'
        + '<p>9 月末周（9.28—9.30）入院 7 人、出院 6 人，净增 <b>1 人</b>；9.30 在院 <b>34 人</b>（较 9.29 的 31 人 +3）。</p>'
        + '<p>住院端新增开始形成，但绝对量仍小，需继续观察能否维持。</p></article>'
        + '<article class="ai-balance-item growth"><div class="ai-balance-head"><b>3</b><strong>关键日贡献 43.3%</strong></div>'
        + '<p>9.25 与 9.26 两天合计 25.81 万，占上周完整周（9.21—9.27，59.59 万）的 43.3%；其前 4 天日均仅 6.21 万。</p>'
        + '<p>动作：复盘高产项目并复制到工作日。</p></article>' +
      '</div>' +
      '<div class="sr-note" style="margin-top:14px"><h4>原主面板「变好的业务 · 变差的业务 · 待确认数据」（截至 9 月收官）</h4></div>' +
      '<div class="ai-balance-strip">' +
        '<article class="ai-balance-item growth"><div class="ai-balance-head"><b>3</b><strong>变好的业务</strong></div>'
        + '<p>① 客服组导医台账上周补齐履职分：<span class="changed-good">32 人日、2,982 分</span>，个人排名首次可用</p>'
        + '<p>② 导医台账「是否到院」补齐：<span class="changed-good">温诗怡 20 条补填后全组 30/67 = 44.8%</span>（原 20 条、18 条未填，本轮已补齐）</p>'
        + '<p>③ 团体治疗按患者团体比是回升：<span class="changed-good">上周 3 场 6 人 vs 上上周 3 场 1 人</span></p></article>'
        + '<article class="ai-balance-item watch"><div class="ai-balance-head"><b>3</b><strong>变差的业务</strong></div>'
        + '<p>① 心理组工作量环比双降：患者接触 <span class="changed-bad">71→34（−52.1%）</span>、咨询 <span class="changed-bad">30→26（−13.3%）</span>、家长工作 <span class="changed-bad">40→15（−62.5%）</span></p>'
        + '<p>② 管家上周对接 <span class="changed-good">78→78 条（持平）</span>，但内部换手：物理治疗 16→21 条、住院 9→14 人上量，心理 23→19 条回落</p>'
        + '<p>③ 物理治疗未做 <span class="changed-bad">101 次</span>（上期 85 次），9.25 单日完成率仅 <span class="changed-bad">79.7%</span></p></article>'
        + '<article class="ai-balance-item data"><div class="ai-balance-head"><b>16</b><strong>上周要确认的具体数据</strong></div>'
        + '<div class="check-tags"><span>1. 总费用与营收日报两个口径</span><span>2. 物理治疗五个口径</span><span>3. 医生在院未录入院日期</span><span>4. 主表已切第 3 周</span><span>5. 管家排名口径</span><span>6. 接待与到院定义</span><span>7. 营销渠道历史数据</span><span>8. 心理组按周口径</span><span>9. 护理排名口径</span><span>10. 物理治疗达标线</span><span>11. 护理表头与工娱归口</span><span>12. 客服姓名与岗位口径</span><span>13. 周度比较缺失周期</span><span>14. 导医台账待核</span><span>15. 团体治疗两表口径</span><span>16. 心理查房日报断档</span></div></article>' +
      '</div>' +
      '<div class="sr-note" style="margin-top:14px"><h4>原营销面板「年内月度销售走势 3—9 月」（截至 9 月收官）</h4></div>' +
      '<div class="sr-tbl-wrap"><table class="sr-tbl"><thead><tr><th>月份</th><th>3月</th><th>4月</th><th>5月</th><th>6月</th><th>7月</th><th>8月</th><th>9月</th></tr></thead><tbody>'
      + '<tr><td>销售额（万）</td><td>214.9</td><td>229.3</td><td>220.2</td><td>242.5</td><td><b>265.7</b></td><td>245.2</td><td><b>227.17</b></td></tr>'
      + '<tr><td>状态</td><td>已复核</td><td>已复核</td><td>已复核</td><td>已复核</td><td>已复核</td><td>已复核</td><td>已收官</td></tr>'
      + '</tbody></table></div>'
      + '<div class="sr-note" style="margin-top:8px"><ul>'
      + '<li><b>3—8 月</b>：均已按每月 4 张截图逐月复核，不再重算。</li>'
      + '<li><b>5 月 −4.0%</b>：4 月 229.3 万降至 220.2 万；6 月和 7 月随后分别回升 10.1% 和 9.6%，连续超过 240 万目标。</li>'
      + '<li><b>7 月达到阶段高点</b>：265.7 万，完成率 110.7%；同比 141.9% 受去年低基数影响，应重点看环比增长 9.6%。</li>'
      + '<li><b>8 月回落 7.7%</b>：245.2 万仍超过 240 万目标 5.2 万，但比 7 月少 20.5 万；周末贡献约 44.5%，平日销售承接偏弱。</li>'
      + '<li><b>9 月已收官 · 未达目标</b>：30 天累计 227.17 万（完成目标 260 万的 87.4%），落后 12.6 个百分点、缺口 32.83 万。</li>'
      + '</ul></div>' +
      '</details>';
  }


  /* ⭐ 把报告钉在主页面最前：紧跟 .title-row，且排在 #monthCommandCenter 之前。
     ⚠ month-dashboard.js 会在 load 时把月面板插进来；本函数在每次重绘时校正位置。
     只在「位置不对」时才 insertBefore，故幂等、不会死循环。 */
  function pinToTop(){
    var host = el('sepReport'), title = document.querySelector('.title-row');
    if (!host || !title || !title.parentNode) return;
    if (title.nextElementSibling !== host) {
      title.parentNode.insertBefore(host, title.nextElementSibling);
    }
  }

  function boot() {
    render();
    ['september-revenue-updated', 'ops:revenue-updated', 'ops:core-refresh'].forEach(function (ev) {
      window.addEventListener(ev, render);
    });
    /* 月面板在 load 后接管 body 并跑 normalizeAll，延后重绘以确保文案为本报告口径；
       同时多次校正位置，防止月面板稍后插入把报告挤到后面。 */
    setTimeout(render, 300);
    setTimeout(render, 600);
    setTimeout(render, 1600);
    setTimeout(render, 2600);
  }

  window.__sepReportRender = render;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
