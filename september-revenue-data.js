/* ============================================================================
   9 月营收统一数据源（移植自 psyc.harness 的 hospital-operations-dashboard）
   ----------------------------------------------------------------------------
   ⚠ 与源版的关键差异：**不自带 rows**，而是从本仓唯一真源 window.OPS_REVENUE
   （data-import.js）派生。源版自己也存一份 rows + localStorage，两边并存会出现
   「拖图片后只有一个面板更新」的双数据源问题。
   这里改为：OPS_REVENUE 更新 → 重建 rows → 派发 september-revenue-updated。

   对外 API 与源版保持一致（derive / subset / summarize / rows / updatedAt …），
   使 month-dashboard.js 与 marketing-current-report.js 可原样工作。
   ========================================================================== */
(function () {
  'use strict';

  var GOAL = 2600000;   // 月度目标 260 万（元）—— 2026-10 沿用 9 月目标（业主 2026-10-06 确认）
  var DOW = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  /* ⭐⭐ 月口径**可参数化**（2026-10-06 改造。业主：主面板切 10 月，9 月内容折进抽屉）
     · SETTLED_MONTH ＝ 主面板的结算月（当前 '2026-10'）
     · SEP_MONTH     ＝ 9 月整月报告抽屉**固定**用的月份（'2026-09'），不随结算月滚动
     derive(ym) / facts(ym) 都接受可选月份参数，缺省＝结算月。
     ⚠ 改造前月口径是「全局唯一」的：抽屉一旦跟着切月，就会把 9 月数据渲染成 10 月标题。 */
  var SETTLED_MONTH = '2026-11';
  var SEP_MONTH = '2026-09';
  /* ⭐⭐ 本期（观察期）＝**两周窗口**，不是单周（业主 2026-10-06 定）。
     由来：10.5 是周一，单周口径下「本期」＝10.5—10.11、实际只有 1 天数据（7.08 万），
     口径太窄且与 9 月末的连续走势断开。
     业主指定：**所有「本期」时间戳与分析洞察一律按 9.28—10.11 算**。
     实现：本期起点 ＝ 数据末日所在自然周的周一，再往前推 (PERIOD_WEEKS-1) 周；
           本期终点 ＝ 该周周日。
     · 数据末日 10.5（周一）→ 本期 9.28—10.11、上一期 9.14—9.27（各 14 天）
     · 「同期对照」仍取**与本期已发生天数相同**的上一期前缀段（同天数口径）
     与 data-import.js 的 refreshWindow() 必须保持同一口径，两处一起改。
     ⚠ 月内周序列仍由 weeksOfMonth(ym) 按月份推导（10 月 → 10.1—10.4 / 10.5—10.11 / …）。 */
  var PERIOD_WEEKS = 1;   // 本期跨度（自然周数）
  /* ⭐⭐ 2026-10-22：本期窗口锚点显式给定，与 data-import.js 的 PERIOD_ANCHOR、
     build_snapshot.py 的 settings.period_anchor 三处同一取值。
     起因：营收日报补到 10.20 后，原「按数据末日重算」把本期算成 10.19—10.20（2 天），
     财务面板的「当前速度＝累计＋剩余天数×本期日均」与「上一期速度」两组数整段错位一周
     （把 10.12—10.18 当成了上一期）。 */
  var PERIOD_ANCHOR = '2026-11-02';   // ⭐ 2026-11-08：本期 11.02—11.08，与 data-import.js / 快照 settings 三处同改
  var CUR = ['2026-09-28', '2026-10-11'], PREV = ['2026-09-14', '2026-09-27'];   // 初值；derive() 按数据实际末日重算
  function ymd(x) {
    return x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0');
  }
  function addDays(d, n) {
    var x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return ymd(x);
  }
  /* 返回 d 所在自然周的周一（周一为一周之始） */
  function weekStartOf(d) {
    var x = new Date(d + 'T12:00:00');
    var dow = x.getDay();                      // 0=周日
    return addDays(d, -(dow === 0 ? 6 : dow - 1));
  }
  /* 按数据末日重算本期窗口。
     ⚠⚠ 2026-10-06 修：原先 CUR/PREV **硬编码**为 W5/W4（9.28—10.4）。
     数据推进到 10.5（周一，属**新的一周**）后窗口不动，周口径面板整段不更新
     （「本周」永远显示上一周的数）——「窗口不跟数据滚」是本项目最常见的静默失真。
     现改为：本期＝数据末日所在周 + 其前 (PERIOD_WEEKS-1) 周（共 14 天）。 */
  function refreshWindow() {
    var rs = data.rows;
    if (!rs || !rs.length) return;
    /* 锚点必须真实存在于数据里；换期时若锚点尚未录入，退回数据末日，避免窗口整段空转。 */
    var _anchorOk = false;
    for (var _i = 0; _i < rs.length; _i++) { if (rs[_i].date === PERIOD_ANCHOR) { _anchorOk = true; break; } }
    var mon = weekStartOf(_anchorOk ? PERIOD_ANCHOR : rs[rs.length - 1].date);
    var from = addDays(mon, -7 * (PERIOD_WEEKS - 1));
    CUR = [from, addDays(mon, 6)];
    PREV = [addDays(from, -7 * PERIOD_WEEKS), addDays(from, -1)];
  }
  /* ---- 月份工具：月口径参数化的基础设施 ----
     ⚠ 2026-10-06 前这里是 `var SETTLED_MONTH='2026-09'` + `MONTH_FIRST/MONTH_LAST` 常量，
     全站只有「一个月」。现在改为按 ym 推导，主面板（10 月）与抽屉（9 月）可并存。 */
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function monthFirst(ym) { return ym + '-01'; }
  function monthDaysOf(ym) { return new Date(+ym.slice(0, 4), +ym.slice(5, 7), 0).getDate(); }
  function monthLast(ym) { return ym + '-' + pad2(monthDaysOf(ym)); }
  function monthRowsOf(ym) { return subset(monthFirst(ym), monthLast(ym)); }
  function shortMd(d) { return (+d.slice(5, 7)) + '.' + (+d.slice(8)); }
  /* 某月的**周序列**：按自然周（周一—周日）切，首尾按所在月裁剪。
     · 9 月 → 9.1—9.6 / 9.7—9.13 / 9.14—9.20 / 9.21—9.27 / 9.28—9.30（＝原 W1—W5，末周封顶）
     · 10 月 → 10.1—10.4 / 10.5—10.11 / 10.12—10.18 / 10.19—10.25 / 10.26—10.31 */
  function weeksOfMonth(ym) {
    var first = monthFirst(ym), last = monthLast(ym);
    var mon = weekStartOf(first), out = [], guard = 0;
    while (mon <= last && guard++ < 8) {
      var sun = addDays(mon, 6);
      out.push({
        from: mon < first ? first : mon,
        to: sun > last ? last : sun,
        mon: mon,
        capped: (mon < first || sun > last)      // 首/末周被月份裁剪
      });
      mon = addDays(mon, 7);
    }
    return out;
  }
  /* 结算月的快捷方式；⚠ 仅供「缺省口径」使用，需指定月份处一律走 monthRowsOf(ym)。 */
  function monthRows() { return monthRowsOf(SETTLED_MONTH); }

  function num(v) { var x = Number(v); return Number.isFinite(x) ? x : 0; }
  function sum(list, key) { return list.reduce(function (a, r) { return a + num(r[key]); }, 0); }

  /* ---- 从唯一真源重建 rows ----
     OPS_REVENUE.daily()：{ '2026-09-21': [门诊, 在院, 初诊, 复诊, 在院数, 入院, 出院] } */
  function buildRows() {
    var src = window.OPS_REVENUE;
    if (!src || !src.daily) return [];
    var daily = src.daily() || {};
    var cum = 0, curM = '', out = [];
    Object.keys(daily).filter(function (k) { return /^\d{4}-\d{2}-\d{2}$/.test(k); }).sort()
      .forEach(function (k) {
        var v = daily[k] || [];
        if (v[0] == null && v[1] == null) return;
        var o = num(v[0]), i = num(v[1]), total = o + i;
        /* ⚠ 「当月累计」必须**按月归零**：原先 cum 从 9.1 一路累加，
           10 月表格里 10.5 那行会显示 271.82 万（＝9 月 227.17 + 10 月 44.65），
           与表尾「当月累计 44.65 万」自相矛盾。 */
        var mk = k.slice(0, 7);
        if (mk !== curM) { curM = mk; cum = 0; }
        cum += total;
        out.push({
          date: k,
          weekday: DOW[new Date(k + 'T12:00:00').getDay()],
          outpatient: o, inpatient: i,
          first: num(v[2]), repeat: num(v[3]),
          /* ⚠ 在院人数是**时点值**，必填字段缺失时必须保留 null：
             num(null) 会返回 0，使 lastWard() 的「ward != null」判断永远成立，
             结果取到最后一天 → 在院被读成 0。 */
          ward: (v[4] == null || v[4] === '') ? null : num(v[4]), admit: num(v[5]),
          /* ⚠ 本仓 OPS_REVENUE 的出院是一列「合计」（＝初次＋多次）；
             源版拆两列。统一放进 dischargeFirst、dischargeRepeat 记 0，
             这样 summarize() 的 dischargeFirst+dischargeRepeat 仍等于合计。 */
          dischargeFirst: num(v[6]), dischargeRepeat: 0,
          total: total, cumulative: cum
        });
      });
    return out;
  }

  var data = {
    month: SETTLED_MONTH,
    reportRange: monthFirst(SETTLED_MONTH) + '—' + monthLast(SETTLED_MONTH),
    updatedThrough: '',
    updatedAt: '—',
    goal: GOAL,
    source: '销售部每日销售日报（截图 OCR）＋ 金山文档主表',
    revision: '9月1—6日为后续修订口径；出院＝出院初次＋多次',
    rows: []
  };

  function subset(from, to) {
    return data.rows.filter(function (r) { return r.date >= from && r.date <= to; });
  }
  function summarize(list) {
    var last = list[list.length - 1] || {};
    /* ⚠ 「在院人数」是**时点值**、不是可加量：取区间内最后一个**有填报**的日期。
       原先写 last.ward || 0 —— 只要最后一天没填该字段（导入营收时很常见），
       在院人数就会直接变成 0，月面板/营销报告会一起显示「在院 0 人」。
       现在缺字段的日期自动向前回退，并记录实际时点 wardAt。 */
    var wardV = null, wardAt = '';
    for (var wi = list.length - 1; wi >= 0; wi--) {
      if (list[wi].ward != null) { wardV = list[wi].ward; wardAt = list[wi].date; break; }
    }
    return {
      days: list.length,
      total: sum(list, 'total'),
      outpatient: sum(list, 'outpatient'),
      inpatient: sum(list, 'inpatient'),
      first: sum(list, 'first'),
      repeat: sum(list, 'repeat'),
      visits: sum(list, 'first') + sum(list, 'repeat'),
      admissions: sum(list, 'admit'),
      discharges: sum(list, 'dischargeFirst') + sum(list, 'dischargeRepeat'),
      dischargeFirst: sum(list, 'dischargeFirst'),
      dischargeRepeat: sum(list, 'dischargeRepeat'),
      ward: wardV,
      wardAt: wardAt,
      average: list.length ? sum(list, 'total') / list.length : 0
    };
  }
  function lastDay() { return data.rows.length ? Number(data.rows[data.rows.length - 1].date.slice(8)) : 0; }
  /* 全站统一的「最新在院人数」取值：最后一个有填报的日期（缺字段自动回退）。
     各面板请用它，不要再直接取 rows 最后一行 —— 见 summarize() 里的说明。 */
  function lastWard() {
    for (var i = data.rows.length - 1; i >= 0; i--) {
      if (data.rows[i].ward != null) return { value: data.rows[i].ward, date: data.rows[i].date };
    }
    return { value: null, date: '' };
  }

  /* ⭐ derive(ym)：ym 缺省＝结算月（主面板）。
     9 月整月报告抽屉传 derive('2026-09')，保证抽屉里始终是 9 月口径。 */
  function derive(ym) {
    ym = ym || SETTLED_MONTH;
    var mFirst = monthFirst(ym), mLast = monthLast(ym), mDays = monthDaysOf(ym);
    refreshWindow();                             // ⭐ 先按数据末日重算周窗口
    var month = summarize(subset(mFirst, mLast));
    var current = summarize(subset(CUR[0], CUR[1]));   // ⭐ 本期（两周窗口，含跨月日）
    /* ⭐ 给本期加 label（2026-10-06）：各模块显示「本期（X—Y）」需要它，
       原先只有 weeks[] 的元素有 label，currentWeek 没有 → 模块只能自己拼或写死。 */
    current.label = shortMd(CUR[0]) + '—' + shortMd(CUR[1]);
    current.from = CUR[0]; current.to = CUR[1];
    /* 上一期可比区间＝与本期已发生天数相同的上一期前缀段（同天数口径）
       ⚠ pcTo 必须用日期加法算；原先把月份硬编码成 '2026-09-'，
       PREV 一旦落在别的月份（如 9.28—10.4）就会算错。 */
    var n = Math.max(1, current.days);
    var pcTo = addDays(PREV[0], n - 1);
    if (pcTo > PREV[1]) pcTo = PREV[1];
    var previousComparable = summarize(subset(PREV[0], pcTo));
    /* ⭐ 上一期区间与「同期对照」区间都带上，供各模块直接取用（别再自己拼日期） */
    previousComparable.from = PREV[0]; previousComparable.to = pcTo;
    previousComparable.label = shortMd(PREV[0]) + '—' + shortMd(pcTo);
    /* ⚠ 本期是两周窗口：CUR[0]（9.28）已不是「本周一」，
       标 current 必须用**最新数据所在周**的周一（10.5），否则会标错柱。 */
    var lastRow = data.rows[data.rows.length - 1];
    var curMon = lastRow ? weekStartOf(lastRow.date) : weekStartOf(CUR[0]);
    /* ⭐ 月内周序列按 ym 推导（原先硬编码 W1—W5）。首/末周被月份裁剪，
       保证「各周相加 ＝ 月累计」：9 月末周裁到 9.30、10 月首周裁到 10.1 起。
       ⚠ 跨月自然周在两个月里各自只计本月的部分，这是刻意的。 */
    var weeks = weeksOfMonth(ym).map(function (w) {
      var x = summarize(subset(w.from, w.to));
      x.label = shortMd(w.from) + '—' + shortMd(w.to);
      x.fullLabel = x.label;
      x.capped = w.capped;
      /* ⭐ 2026-10-10：把周区间一并带出 —— 消费方要判断「该周是不是还没开始」
         （未开始的周不能渲染成 0.00 万）。原先只带 label，消费方无法还原日期。 */
      x.from = w.from;
      x.to = w.to;
      x.current = (w.mon === curMon);
      x.inPeriod = (w.to >= CUR[0] && w.from <= CUR[1]);   // 该周是否落在本期内
      return x;
    });

    /* ⚠ 原为 lastDay()（＝数据末日的「日」）—— 数据到 10.1 后会变成 1，
       时间进度掉到 3.2%、剩余 30 天。改为当月实际覆盖天数。
       ⚠ 天数也按 ym 取（10 月 31 天、9 月 30 天），不能再写死 30。 */
    var used = subset(mFirst, mLast).length || month.days;
    var remainingDays = Math.max(0, mDays - used);
    var remaining = GOAL - month.total;
    var MR = subset(mFirst, mLast);             // 该月的样本
    var sorted = MR.slice().sort(function (a, b) { return b.total - a.total; });
    var weekend = MR.filter(function (r) { return r.weekday === '周六' || r.weekday === '周日'; });
    var weekday = MR.filter(function (r) { return r.weekday !== '周六' && r.weekday !== '周日'; });
    return {
      monthKey: ym, monthFirst: mFirst, monthLast: mLast, monthDays: mDays,
      month: month, currentWeek: current, previousComparable: previousComparable, weeks: weeks,
      /* 本期 / 上一期的原始区间（供需要自行切片的模块使用，别再自己拼日期） */
      period: { from: CUR[0], to: CUR[1], label: shortMd(CUR[0]) + '—' + shortMd(CUR[1]) },
      prevPeriod: { from: PREV[0], to: PREV[1], label: shortMd(PREV[0]) + '—' + shortMd(PREV[1]) },
      periodWeeks: PERIOD_WEEKS,
      usedDays: used, remaining: remaining, remainingDays: remainingDays,
      requiredDaily: remainingDays ? remaining / remainingDays : 0,
      forecast: month.total + month.average * remainingDays,
      amountRate: month.total / GOAL * 100,
      timeRate: used / mDays * 100,
      monthClosed: remainingDays === 0,
      topDays: sorted.slice(0, 5),
      weekend: summarize(weekend), weekday: summarize(weekday),
      lastDate: data.rows.length ? data.rows[data.rows.length - 1].date : ''
    };
  }

  /* ⭐ 统一「经营口径」对象 —— 全站文案取数的**唯一入口**。
     为什么要它：此前 9 个模块各自硬编码「剩余 5 天 / 需 82.00 万 / 落后 14.9pt」，
     口径一改就要满页找数字，且极易改漏（本轮实测漏过 3 轮）。
     现在所有会变的数字都从这里取；数据一变，全站文案跟着变。
     ⚠ 口径约定（业主 2026-09-28 定）：
       · 「剩余 X 天」按**数据最新日**算（不是按今天）——
         这样与「数据更新至」时间戳同源，不会出现「时间戳跳了、天数没跳」。
       · 时间进度 = 数据最新日 ÷ 当月天数（与营收进度同源比较）。
       · 负数一律用 U+2212「−」而非 ASCII「-」。 */
  /* ⭐ buildFacts(ym)：ym 缺省＝结算月（主面板 10 月）。
     ⚠ 月口径**不能**用 data.rows 与 last（数据末日）：
        10.1 进来后 last 变 10-01 → used=1、时间进度 3.2%、剩余 30 天，
        9 月的「已收官」整站文案会全部退回错误表述。
     抽屉（9 月）传 facts('2026-09')，与主面板互不干扰。 */
  function buildFacts(ym) {
    ym = ym || SETTLED_MONTH;
    var mFirst = monthFirst(ym), mLast = monthLast(ym);
    var m = summarize(subset(mFirst, mLast));
    var last = data.rows.length ? data.rows[data.rows.length - 1].date : '';
    /* 实际末日（10.5）只用于时间戳 labelDate / labelDateShort */
    var ly = +last.slice(0, 4), lmo = +last.slice(5, 7), lday = +last.slice(8);
    var y = +ym.slice(0, 4), mo = +ym.slice(5, 7);
    var monthDays = monthDaysOf(ym);
    var used = subset(mFirst, mLast).length;
    var remainDays = Math.max(0, monthDays - used);
    var remain = Math.max(0, GOAL - m.total);
    var needDaily = remainDays ? remain / remainDays : 0;
    var timeRate = monthDays ? used / monthDays * 100 : 0;
    var amountRate = m.total / GOAL * 100;
    var sgn = function (v, d) { d = d == null ? 1 : d; return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(d); };
    var wan = function (yuan, d) { return (yuan / 10000).toFixed(d == null ? 2 : d); };
    /* 本期已发生的日均（用有值的实际天数，不用自然天数，避免"待补"拉低均值） */
    refreshWindow();                             // 与 derive() 同口径（facts 可能先被调用）
    var cw = summarize(subset(CUR[0], CUR[1]));
    var cwAvg = cw.days ? cw.total / cw.days : 0;
    return {
      lastDate: last,                              // '2026-09-25'
      monthDays: monthDays, usedDays: used, remainDays: remainDays,
      total: m.total, totalWan: wan(m.total),      // '178.00'
      goalWan: GOAL / 10000,                       // 260
      remainWan: wan(remain),                      // '82.00'
      needDailyWan: wan(needDaily),                // '16.40'
      mtdAvgWan: wan(m.average),                   // 当月日均
      weekAvgWan: wan(cwAvg),                      // 本期（两周窗口）实际日均
      /* ⭐ 月末收官：数据已覆盖整月（剩余 0 天）时，「剩余 X 天 / 日均需」不再成立，
         各模块据此换文案（否则会显示「日均需 0.00 万」这种误导性说法）。 */
      monthClosed: remainDays === 0,
      gapDailyWan: wan(Math.max(0, needDaily - m.average)),
      timeRate: timeRate, amountRate: amountRate,
      lagPt: timeRate - amountRate,                // 落后百分点（正数=落后）
      forecastWan: wan(m.total + m.average * remainDays),
      forecastGapWan: wan(Math.max(0, GOAL - (m.total + m.average * remainDays))),
      days: m.days, weekDays: cw.days,
      /* 本期 / 上一期区间标签（「本期」＝两周窗口，别再写死成单周） */
      periodLabel: shortMd(CUR[0]) + '—' + shortMd(CUR[1]),
      prevPeriodLabel: shortMd(PREV[0]) + '—' + shortMd(PREV[1]),
      /* 统一格式化的字符串，模块直接用，避免各处再拼 */
      labelDate: last ? (ly + '年' + lmo + '月' + lday + '日') : '—',
      labelDateShort: last ? (lmo + '.' + lday) : '—',       // 实际末日 10.1（营收数据至）
      labelMonth: y + '年' + mo + '月',                       // 结算月 2026年9月
      sgn: sgn
    };
  }
  /* ⚠ 按月份分别缓存：主面板取 facts()（10 月），抽屉取 facts('2026-09')。
     改造前只有单个 FACTS 缓存，参数化后必须按月分开，否则两边互相污染。 */
  var FACTS = {};
  function facts(ym) {
    var k = ym || SETTLED_MONTH;
    if (!FACTS[k]) FACTS[k] = buildFacts(k);
    return FACTS[k];
  }

  function refresh() {
    data.rows = buildRows();
    var last = data.rows[data.rows.length - 1];
    data.updatedThrough = last ? last.date : '';
    data.updatedAt = last
      ? (last.date.slice(0, 4) + '年' + (+last.date.slice(5, 7)) + '月' + (+last.date.slice(8)) + '日 23:59')
      : '—';
    /* ⚠ 报告期**不能**跟着 last 走 —— 数据到 10.1 后报告期会变成 09-01—10-01，
       把 10 月并进 9 月报告。固定为结算月区间（当前 2026-10-01—2026-10-31）。 */
    data.reportRange = monthFirst(SETTLED_MONTH) + '—' + monthLast(SETTLED_MONTH);
    FACTS = {};            // 数据变了 → 各月口径缓存全部失效，下次取用时重算
    /* ⚠ 不要把 data.facts 覆盖成对象：data.facts 必须始终是**函数**，
       否则各模块调用 data.facts() 会抛错（此前 refresh 每次写入都会把它换成对象）。 */
    data.factsCache = facts();
  }

  refresh();
  data.subset = subset;
  data.lastWard = lastWard;
  data.facts = facts;          // ⭐ 全站统一口径：data.facts() 取最新值
  data.summarize = summarize;
  data.derive = derive;
  /* ⭐ 暴露月份常量：主面板 = SETTLED_MONTH，9 月抽屉 = SEP_MONTH */
  data.SETTLED_MONTH = SETTLED_MONTH;
  data.SEP_MONTH = SEP_MONTH;
  data.monthLast = monthLast;
  data.monthFirst = monthFirst;
  window.SEPTEMBER_REVENUE_DATA = data;

  /* 源版这里会写自己的 localStorage；本仓不落第二份数据，转交 OPS_REVENUE */
  window.updateSeptemberRevenueData = function (nextRows, meta) {
    if (window.OPS_REVENUE && typeof window.OPS_REVENUE.applyRows === 'function' && Array.isArray(nextRows) && nextRows.length) {
      window.OPS_REVENUE.applyRows(nextRows, meta);
    } else {
      refresh();
      window.dispatchEvent(new CustomEvent('september-revenue-updated', { detail: data }));
    }
    return derive();
  };
  window.resetSeptemberRevenueData = function () {
    if (window.OPS_REVENUE && typeof window.OPS_REVENUE.reset === 'function') window.OPS_REVENUE.reset();
    refresh();
    window.dispatchEvent(new CustomEvent('september-revenue-updated', { detail: data }));
  };

  /* ⭐ 唯一真源更新 → 重建 rows → 通知两个新面板 */
  window.addEventListener('ops:revenue-updated', function () {
    refresh();
    window.dispatchEvent(new CustomEvent('september-revenue-updated', { detail: data }));
  });
})();
