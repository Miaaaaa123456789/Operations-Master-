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

  var GOAL = 2600000;                       // 月度目标 260 万（元）
  var REPORT_RANGE = '2026-09-01—2026-09-27';
  var DOW = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  var W1 = ['2026-09-01', '2026-09-06'], W2 = ['2026-09-07', '2026-09-13'],
      W3 = ['2026-09-14', '2026-09-20'], W4 = ['2026-09-21', '2026-09-27'];

  function num(v) { var x = Number(v); return Number.isFinite(x) ? x : 0; }
  function sum(list, key) { return list.reduce(function (a, r) { return a + num(r[key]); }, 0); }

  /* ---- 从唯一真源重建 rows ----
     OPS_REVENUE.daily()：{ '2026-09-21': [门诊, 在院, 初诊, 复诊, 在院数, 入院, 出院] } */
  function buildRows() {
    var src = window.OPS_REVENUE;
    if (!src || !src.daily) return [];
    var daily = src.daily() || {};
    var cum = 0, out = [];
    Object.keys(daily).filter(function (k) { return /^\d{4}-\d{2}-\d{2}$/.test(k); }).sort()
      .forEach(function (k) {
        var v = daily[k] || [];
        if (v[0] == null && v[1] == null) return;
        var o = num(v[0]), i = num(v[1]), total = o + i;
        cum += total;
        out.push({
          date: k,
          weekday: DOW[new Date(k + 'T12:00:00').getDay()],
          outpatient: o, inpatient: i,
          first: num(v[2]), repeat: num(v[3]),
          ward: num(v[4]), admit: num(v[5]),
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
    month: '2026-09',
    reportRange: REPORT_RANGE,
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
      ward: last.ward || 0,
      average: list.length ? sum(list, 'total') / list.length : 0
    };
  }
  function lastDay() { return data.rows.length ? Number(data.rows[data.rows.length - 1].date.slice(8)) : 0; }

  function derive() {
    var month = summarize(data.rows);
    var current = summarize(subset(W4[0], W4[1]));
    /* 上周可比区间＝与本周已发生天数相同的上周片段（同天数口径） */
    var n = Math.max(1, current.days);
    var pcTo = '2026-09-' + String(13 + n).padStart(2, '0');
    var previousComparable = summarize(subset(W3[0], pcTo));
    var weeks = [[W1, '9.1—9.6'], [W2, '9.7—9.13'], [W3, '9.14—9.20'], [W4, '9.21—9.27']]
      .map(function (w) { var x = summarize(subset(w[0][0], w[0][1])); x.label = w[1]; x.current = (w[0] === W4); return x; });

    var used = lastDay() || month.days;
    var remainingDays = Math.max(0, 30 - used);
    var remaining = GOAL - month.total;
    var sorted = data.rows.slice().sort(function (a, b) { return b.total - a.total; });
    var weekend = data.rows.filter(function (r) { return r.weekday === '周六' || r.weekday === '周日'; });
    var weekday = data.rows.filter(function (r) { return r.weekday !== '周六' && r.weekday !== '周日'; });
    return {
      month: month, currentWeek: current, previousComparable: previousComparable, weeks: weeks,
      usedDays: used, remaining: remaining, remainingDays: remainingDays,
      requiredDaily: remainingDays ? remaining / remainingDays : 0,
      forecast: month.total + month.average * remainingDays,
      amountRate: month.total / GOAL * 100,
      timeRate: used / 30 * 100,
      topDays: sorted.slice(0, 5),
      weekend: summarize(weekend), weekday: summarize(weekday),
      lastDate: data.rows.length ? data.rows[data.rows.length - 1].date : ''
    };
  }

  function refresh() {
    data.rows = buildRows();
    var last = data.rows[data.rows.length - 1];
    data.updatedThrough = last ? last.date : '';
    data.updatedAt = last
      ? (last.date.slice(0, 4) + '年' + (+last.date.slice(5, 7)) + '月' + (+last.date.slice(8)) + '日 23:59')
      : '—';
  }

  refresh();
  data.subset = subset;
  data.summarize = summarize;
  data.derive = derive;
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
