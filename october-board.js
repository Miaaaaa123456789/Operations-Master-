/* ==========================================================================
   十月经营 + 员工排名 + 九月报告抽屉
   业主 2026-10-02 指定。数据来源：
     · 十月营收 —— window.SEPTEMBER_REVENUE_DATA.rows 里筛 2026-10-*
       （⚠ 不能走 derive()，它按月口径锁死 9 月）
     · 员工排名 —— index.html 内联脚本里的 analytics.<dept>.rankGroups
     · 九月报告 —— 仍由 september-report.js 渲染进 #sepReport，本模块只管抽屉开合

   三条既有铁律（改前必读）：
     1) 文案不写裸「本周」——month-dashboard.js 的 normalizeAll() 会把 body 里的裸「本周」
        改写成当前周标签，导致重复。这里一律写显式日期区间。
     2) 排名只按业务量与效率排序，填报/在岗天数不计分、不排序、不作并列判定。
     3) 10 月目标沿用 9 月的 260 万（业主 2026-10-02 确认）。
   ========================================================================== */
(function () {
  'use strict';

  var OCT_TARGET = 260e4;      // 10 月目标：沿用 9 月 260 万（业主确认）
  var OCT_MONTH = 10;          // 当前经营月
  var OCT_YEAR = 2026;
  var PREFIX = '2026-10';

  var el = function (id) { return document.getElementById(id); };

  function wan(v, d) {
    return (v / 1e4).toFixed(d == null ? 2 : d);
  }
  function int(v) {
    return String(Math.round(v == null ? 0 : v));
  }
  function daysInMonth(y, m) {
    return new Date(y, m, 0).getDate();   // m: 1-12
  }
  /* 中文短日期：2026-10-01 → 10.01 */
  function md(s) {
    return String(s).slice(5).replace('-', '.');
  }

  function rows() {
    var D = window.SEPTEMBER_REVENUE_DATA;
    return (D && D.rows) || [];
  }

  /* ---------------------------------------------------------------- 十月汇总 */
  function octStats() {
    var all = rows().filter(function (r) { return String(r.date).indexOf(PREFIX) === 0; });
    if (!all.length) return null;
    var o = 0, i = 0, first = 0, repeat = 0, admit = 0, dis = 0;
    all.forEach(function (r) {
      o += r.outpatient || 0;
      i += r.inpatient || 0;
      first += r.first || 0;
      repeat += r.repeat || 0;
      admit += r.admit || 0;
      dis += (r.dischargeFirst || 0) + (r.dischargeRepeat || 0);
    });
    var total = o + i;
    var days = all.length;
    var monthDays = daysInMonth(OCT_YEAR, OCT_MONTH);
    var leftDays = monthDays - days;
    return {
      days: days, monthDays: monthDays,
      total: total, out: o, in: i,
      first: first, repeat: repeat, visits: first + repeat,
      admit: admit, discharges: dis,
      /* ⚠ 2026-10-06 修：单日明细卡原先误用 admit/discharges（＝**月累计**），
         结果「10.05 单日明细」里显示「入院/出院 11/8 人」（那是 10 月累计）→ 自相矛盾。
         这里补上末日当天的单日值，卡片改用它们。 */
      dayAdmit: all[all.length - 1].admit || 0,
      dayDischarges: (all[all.length - 1].dischargeFirst || 0) + (all[all.length - 1].dischargeRepeat || 0),
      ward: all[all.length - 1].ward,
      lastDate: all[all.length - 1].date,
      target: OCT_TARGET,
      pct: total / OCT_TARGET * 100,
      timePct: days / monthDays * 100,
      avg: total / days,
      leftDays: leftDays,
      need: leftDays > 0 ? (OCT_TARGET - total) / leftDays : 0,
      gap: Math.max(0, OCT_TARGET - total),
      all: all
    };
  }

  /* 最近 5 天逐日（含跨月尾巴，用于看 9.28—10.2 的节奏） */
  function recentDays(n) {
    var all = rows();
    return all.slice(Math.max(0, all.length - n));
  }

  function barHtml(list) {
    var max = 1;
    list.forEach(function (r) { var t = (r.outpatient || 0) + (r.inpatient || 0); if (t > max) max = t; });
    return list.map(function (r) {
      var t = (r.outpatient || 0) + (r.inpatient || 0);
      var h = Math.max(4, Math.round(t / max * 100));
      var isOct = String(r.date).indexOf(PREFIX) === 0;
      return '<div class="ob-dcol">' +
        '<b>' + wan(t) + '</b>' +
        '<i style="height:' + h + '%;background:' + (isOct ? '#0066CC' : '#9DB8D8') + '"></i>' +
        '<s>' + md(r.date) + '</s>' +
        '</div>';
    }).join('');
  }

  function renderOctober() {
    var host = el('octoberBoard');
    if (!host) return;
    var s = octStats();
    if (!s) {
      host.innerHTML = '<div class="section-head"><div><h2>10 月经营</h2>' +
        '<p>2026.10.01—10.31 · 暂无数据</p></div></div>' +
        '<div class="ob-note">10 月营收日报尚未录入，本区待数据到达后自动生成。</div>';
      return;
    }
    /* ⛔ 月累计口径（业主 2026-10-19 指定）：与《特别行动小组汇报表》冲突时一律取汇报表。
       本区其余字段仍是营收日报逐日口径（2026-10-22 已补到 10.20），故两套数必须同时标出。
       汇报表覆盖时：主数＝汇报表，副注＝台账；无快照时退回纯台账。 */
    var _mr = ((window.OPS_LIVE_SNAPSHOT || {}).metrics || {}).monthRevenue || null;
    /* ⚠ 2026-11-04：快照 monthRevenue 已滚到 11 月，而本板固定是 10 月账
       （标题 2026.10.01—10.31）。月份不符时绝不能拿它顶替，否则
       「10 月累计营业额」会显示 11 月的 21.97 万、缺口 238 万。 */
    if (_mr && _mr.periodStart && _mr.periodStart.slice(0, 7) !== PREFIX) _mr = null;
    var _auth = !!(_mr && _mr.value != null && (_mr.authority === 'action_report' || _mr.authority === 'revenue_daily_report'));
    var _isDaily = !!(_auth && _mr.authority === 'revenue_daily_report');
    var _dt = ((window.OPS_LIVE_SNAPSHOT || {}).watermarks || {}).dept || null;
    var _deptTo = (_auth && _mr.dataThrough) ? md(_mr.dataThrough) : md(s.lastDate);
    /* ⚠ 单位陷阱：快照里的 value / gap 是**万元**，而本文件的 wan() 按**元**除以 1e4。
       直接 wan(kTotal) 会得到 0.02（实测踩过），必须先 ×1e4 再交给 wan()。
       时间进度同理：报表口径已含 10.18，天数应为 18 而不是台账的 17。 */
    var kTotalYuan = _auth ? _mr.value * 1e4 : s.total;
    var kGapYuan = _auth ? (_mr.gap != null ? _mr.gap * 1e4 : OCT_TARGET - kTotalYuan) : s.gap;
    var kPct = _auth ? _mr.amountProgress : s.pct;
    var kTimePct = (_auth && _mr.timeProgress != null) ? _mr.timeProgress : s.timePct;
    var kDays = _auth && _mr.timeProgress != null ? Math.round(_mr.timeProgress / 100 * s.monthDays) : s.days;
    var pace = kPct - kTimePct;
    var paceTxt = pace >= 0 ? '领先时间进度 ' + pace.toFixed(1) + ' 个百分点'
                            : '落后时间进度 ' + Math.abs(pace).toFixed(1) + ' 个百分点';
    var paceCls = pace >= 0 ? '#12A150' : '#E0576F';
    var ledgerNote = _auth
      ? (_isDaily
          ? '<br>汇报表口径（主表至 ' + md(_mr.actionReportThrough || '') + '）'
            + (_mr.actionReportValue != null ? _mr.actionReportValue.toFixed(2) : '—')
            + ' 万 · 只滚到该日，落后日报 2 天；两套不同源、不相加、不互相覆盖。'
          : '<br>台账口径（营收日报至 ' + md(s.lastDate) + '）' + wan(s.total) + ' 万 · 完成 ' + s.pct.toFixed(1) + '%；'
            + '汇报表含 10.18 当天，按指令采用汇报表数。')
      : '';

    host.innerHTML =
      '<div class="section-head">' +
        '<div><h2>10 月经营</h2>' +
        '<p>2026.10.01—10.31 · 营收日报已录 ' + (_auth ? (+String(_mr.dataThrough || '').slice(8) || s.days) : s.days) + ' 天（截至 ' + (_auth ? _deptTo : md(s.lastDate)) + '）'
          + ' · 目标 260 万（沿用 9 月）</p></div>' +
        '<span class="range-chip"><i>▦</i>数据至 ' + (_auth ? _deptTo : md(s.lastDate)) + '</span>' +
      '</div>' +

      '<div class="ob-grid">' +

        /* ① 月累计 */
        '<article class="ob-card ob-wide">' +
          '<label>10 月累计营业额' + (_auth ? (_isDaily ? '（营收日报口径）' : '（汇报表口径）') : '') + '</label>' +
          '<div class="ob-num">' + wan(kTotalYuan) + '<em>万元</em></div>' +
          '<div class="ob-sub">目标 <b>260 万</b> · 完成 <b>' + kPct.toFixed(1) + '%</b> · ' +
            '缺口 <b>' + wan(kGapYuan) + ' 万</b></div>' +
          '<div class="ob-bar"><i style="width:' + Math.min(100, kPct).toFixed(2) + '%"></i>' +
            '<u style="left:' + Math.min(99.4, kTimePct).toFixed(2) + '%"></u></div>' +
          '<div class="ob-legend">' +
            '<s>金额完成 ' + kPct.toFixed(1) + '%</s>' +
            '<s class="t">时间进度 ' + kTimePct.toFixed(1) + '%（' + kDays + '/' + s.monthDays + ' 天）</s>' +
          '</div>' +
          '<div class="ob-note">进度差 <b style="color:' + paceCls + '">' + paceTxt + '</b>。' +
            '⚠ 10 月目标沿用 9 月的 260 万，尚未按 10 月重设，完成率仅供参考。' +
            ledgerNote + '</div>' +
        '</article>' +

        /* ② 日均与所需 */
        '<article class="ob-card">' +
          '<label>日均与后续要求' + (_auth ? '（台账日均）' : '') + '</label>' +
          '<div class="ob-num">' + wan(s.avg) + '<em>万/日</em></div>' +
          '<div class="ob-sub">营收日报已录 ' + s.days + ' 天日均</div>' +
          '<div class="ob-split">' +
            '<div><label>剩余天数</label><b>' + s.leftDays + '<em> 天</em></b></div>' +
            '<div><label>需日均</label><b>' + wan(s.leftDays > 0 ? (OCT_TARGET - kTotalYuan) / s.leftDays : 0) + '<em> 万</em></b></div>' +
          '</div>' +
          (_auth ? '<div class="ob-note">需日均按' + (_isDaily ? '营收日报' : '汇报表') + '月累计 ' + wan(kTotalYuan) + ' 万测算。</div>' : '') +
        '</article>' +

        /* ③ 末日单日明细 */
        '<article class="ob-card">' +
          '<label>' + md(s.lastDate) + ' 单日明细</label>' +
          '<div class="ob-num">' + wan(s.all[s.all.length - 1].total) + '<em>万元</em></div>' +
          '<div class="ob-sub">门诊 ' + wan(s.all[s.all.length - 1].outpatient) + ' 万 ＋ ' +
            '在院 ' + wan(s.all[s.all.length - 1].inpatient) + ' 万</div>' +
          '<div class="ob-split">' +
            '<div><label>在院人数</label><b>' + (s.ward == null ? '待补' : int(s.ward)) + '<em> 人</em></b></div>' +
            '<div><label>入院 / 出院（当日）</label><b>' + int(s.dayAdmit) + ' / ' + int(s.dayDischarges) + '<em> 人</em></b></div>' +
          '</div>' +
        '</article>' +

        /* ④ 月内门诊与人次 */
        '<article class="ob-card">' +
          '<label>10 月门诊人次</label>' +
          '<div class="ob-num">' + int(s.visits) + '<em>人次</em></div>' +
          '<div class="ob-sub">初诊 ' + int(s.first) + ' / 复诊 ' + int(s.repeat) + '</div>' +
          '<div class="ob-split">' +
            '<div><label>门诊收入</label><b>' + wan(s.out) + '<em> 万</em></b></div>' +
            '<div><label>在院收入</label><b>' + wan(s.in) + '<em> 万</em></b></div>' +
          '</div>' +
        '</article>' +

        /* ⑤ 逐日节奏 */
        '<article class="ob-card ob-wide">' +
          '<label>最近 5 天逐日营业额（万元）</label>' +
          '<div class="ob-dbars">' + barHtml(recentDays(5)) + '</div>' +
          '<div class="ob-legend">' +
            '<s>10 月</s>' +
            '<s class="lt">9 月末（跨月尾巴）</s>' +
          '</div>' +
          '<div class="ob-note">深色为 10 月、浅色为 9 月末。' +
            '10 月已录 ' + s.days + ' 天（10.01—' + md(s.lastDate) + '），' +
            '其后日期到达并录入后本区自动更新。</div>' +
        '</article>' +

      '</div>';
  }

  /* ---------------------------------------------------------------- 员工排名 */
  var DEPTS = [
    ['doctor', '医生组', '医'],
    ['nursing', '护理组', '护'],
    ['psychology', '心理咨询组', '心'],
    ['service', '客服服务部', '客'],
    ['marketing', '营销中心', '营']
  ];
  var curDept = 'doctor';
  var expanded = {};

  function getAnalytics() {
    try {
      /* analytics 由 index.html 内联脚本以 const 声明于全局词法环境，后续脚本可读 */
      return (typeof analytics !== 'undefined' && analytics) ? analytics : null;
    } catch (e) { return null; }
  }

  var PREVIEW = 6;

  function renderRank() {
    var body = el('staffRankBody');
    var tabs = el('staffRankTabs');
    if (!body || !tabs) return;

    var A = getAnalytics();
    tabs.innerHTML = DEPTS.map(function (d) {
      return '<button class="rk-tab' + (d[0] === curDept ? ' on' : '') + '" type="button" data-rk="' + d[0] + '">' +
        '<i>' + d[2] + '</i>' + d[1] + '</button>';
    }).join('');

    if (!A) {
      body.innerHTML = '<div class="rk-empty">排名数据尚未就绪。</div>';
      return;
    }
    var dept = A[curDept];
    var groups = (dept && dept.rankGroups) || [];
    if (!groups.length) {
      body.innerHTML = '<div class="rk-empty">该部门本次无可展示的排名。</div>';
      return;
    }

    body.innerHTML = '<div class="rk-grid">' + groups.map(function (g, gi) {
      var key = curDept + ':' + gi;
      var all = g.rows || [];
      var showAll = !!expanded[key];
      var list = showAll ? all : all.slice(0, PREVIEW);
      var rest = all.length - list.length;

      /* ⭐ 2026-10-09：分组支持 `table` 型（医生 × 项目 矩阵）。
         原先只认「行列表」，表达不了这种横竖交叉的明细，只能硬塞成一张卡一行。
         table 结构：{cols:[表头], rows:[[...]], sum:[合计行], foot:'表下注释'} */
      var t = g.table;
      var tHead = '', tBody = '';
      if (t && t.cols) {
        tHead = '<div class="rk-table-wrap"><table class="rk-table"><thead><tr>' +
          t.cols.map(function (c, i) { return '<th' + (i === 0 ? ' class="rk-td-name"' : '') + '>' + c + '</th>'; }).join('') +
          '</tr></thead><tbody>';
        tBody = (t.rows || []).map(function (r) {
          return '<tr>' + r.map(function (c, i) {
            return '<td' + (i === 0 ? ' class="rk-td-name"' : '') + '>' + c + '</td>';
          }).join('') + '</tr>';
        }).join('');
        if (t.sum) {
          tBody += '<tr class="rk-tr-sum">' + t.sum.map(function (c, i) {
            return '<td' + (i === 0 ? ' class="rk-td-name"' : '') + '>' + c + '</td>';
          }).join('') + '</tr>';
        }
        tBody += '</tbody></table></div>' + (t.foot ? '<p class="rk-table-foot">' + t.foot + '</p>' : '');
      }

      var rowsHtml = t ? (tHead + tBody) : list.map(function (r, i) {
        var medal = (g.medals && i < 3) ? ' medal' : '';
        var badge = (g.medals && i < 3) ? ['🥇', '🥈', '🥉'][i] : String(i + 1);
        return '<div class="rk-row' + medal + '">' +
          '<i>' + badge + '</i>' +
          '<div><b>' + (r.name || '—') + '</b>' +
            (r.metric ? '<small>' + r.metric + '</small>' : '') + '</div>' +
          '<em>' + (r.score == null ? '' : r.score) + '</em>' +
          '</div>';
      }).join('');

      return '<article class="rk-card' + (t ? ' rk-card-table' : '') + '">' +
        '<h4>' + (g.title || '排名') + '</h4>' +
        (g.note ? '<small>' + g.note + '</small>' : '') +
        rowsHtml +
        (t ? '' : (rest > 0
          ? '<button class="rk-more" type="button" data-rk-more="' + key + '">展开其余 ' + rest + ' 名 ↓</button>'
          : (showAll && all.length > PREVIEW
              ? '<button class="rk-more" type="button" data-rk-more="' + key + '">收起 ↑</button>'
              : ''))) +
        '</article>';
    }).join('') + '</div>';
  }

  /* ---------------------------------------------------------------- 抽屉 */
  /* ⭐ 2026-11-02：抽屉有两个视图
       · mkt = 10 月营销月报（默认，业主指定「折叠到右上角绿色抽屉」）
       · sep = 9 月整月经营报告（原内容，保留入口）
     两者同一个右滑面板，互斥由 body.mkt-view 控制，切换在左下角 #srSwitch。 */
  var DRAWER_VIEW = 'mkt';
  function setDrawer(open, view) {
    if (view) DRAWER_VIEW = view;
    document.body.classList.toggle('srd-open', !!open);
    document.body.classList.toggle('mkt-view', !!open && DRAWER_VIEW === 'mkt');
    var btn = el('sepReportBtn');
    if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    var sw = el('srSwitch');
    if (sw) Array.prototype.forEach.call(sw.querySelectorAll('[data-view]'), function (b) {
      var on = b.getAttribute('data-view') === DRAWER_VIEW;
      b.classList.toggle('on', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
  }

  function initDrawer() {
    var btn = el('sepReportBtn');
    var backdrop = el('srBackdrop');
    var close = el('srClose');

    if (btn) {
      btn.addEventListener('click', function () {
        var open = document.body.classList.contains('srd-open');
        /* 关闭后再打开，回到默认的「10 月营销月报」 */
        setDrawer(!open, open ? DRAWER_VIEW : 'mkt');
      });
    }
    var sw = el('srSwitch');
    if (sw) {
      sw.addEventListener('click', function (e) {
        var b = e.target.closest ? e.target.closest('[data-view]') : null;
        if (!b) return;
        setDrawer(true, b.getAttribute('data-view'));
      });
    }
    if (backdrop) backdrop.addEventListener('click', function () { setDrawer(false); });
    if (close) close.addEventListener('click', function () { setDrawer(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && document.body.classList.contains('srd-open')) setDrawer(false);
    });
  }

  /* ---------------------------------------------------------------- 事件与启动 */
  function initRankEvents() {
    var tabs = el('staffRankTabs');
    var body = el('staffRankBody');
    if (tabs) {
      tabs.addEventListener('click', function (e) {
        var t = e.target.closest ? e.target.closest('[data-rk]') : null;
        if (!t) return;
        curDept = t.getAttribute('data-rk');
        renderRank();
      });
    }
    if (body) {
      body.addEventListener('click', function (e) {
        var m = e.target.closest ? e.target.closest('[data-rk-more]') : null;
        if (!m) return;
        var k = m.getAttribute('data-rk-more');
        expanded[k] = !expanded[k];
        renderRank();
      });
    }
  }

  /* ---------------------------------------------------------------- 位置校正
     主面板实际由 month-dashboard.js 接管：
       · mount() 把 #monthCommandCenter 插到 #sepReport 之后（锚点 = sepReport || title-row）
       · 并把 #overview / #departments 加 md-legacy-hidden 隐藏（内容由月面板承担）
     业主 2026-10-02 要的顺序是「10 月经营 → 各部门经营 → 员工排名 → AI 洞察」，
     所以这里做幂等校正（同 pinToTop 的思路，只在位置不对时才移动）：
       · #octoberBoard 落到月面板之前
       · #staffRank   紧跟月面板之后（即部门经营之后）
     没有月面板时保持静态 HTML 顺序即可。 */
  function place() {
    var ob = el('octoberBoard'), sr = el('staffRank'), mcc = el('monthCommandCenter');
    if (!ob) return;
    var parent = ob.parentNode;
    if (!parent) return;
    if (mcc && mcc.parentNode === parent) {
      if (mcc.previousElementSibling !== ob) parent.insertBefore(ob, mcc);
      if (sr && sr.parentNode === parent) {
        var want = mcc.nextElementSibling;
        if (sr !== want) parent.insertBefore(sr, want);
      }
    }
  }

  function renderAll() {
    renderOctober();
    renderRank();
    place();
  }

  function boot() {
    initDrawer();
    initRankEvents();
    renderAll();
    /* 其他模块（data-import / month-dashboard）可能在稍后重绘或改写数据，延后兜底重绘 */
    setTimeout(renderAll, 700);
    setTimeout(renderAll, 1800);
    ['ops:revenue-updated', 'september-revenue-updated', 'ops:core-refresh'].forEach(function (ev) {
      window.addEventListener(ev, renderAll);
    });
  }

  window.__octoberBoardRender = renderAll;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
