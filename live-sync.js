/* Operations Master · live data layer
 * 职责：读取 /api/operations/v1/snapshot，按同一 revision 更新看板可见数据；
 *       提供上墙用的自动滚动；30s 轮询 revision，变化才重绘。
 * 不重写原 DOM 结构，只改数据性文案与数值。
 */
(function () {
  'use strict';

  var STATE = { snap: null, rev: null, autoScroll: localStorage.getItem('ops.autoscroll') !== 'off' };
  var WEEK_LABEL = '10.26–11.01';

  function $(s, root) { return (root || document).querySelector(s); }
  function $$(s, root) { return Array.prototype.slice.call((root || document).querySelectorAll(s)); }
  function fmt(n, d) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return Number(n).toLocaleString('zh-CN', { maximumFractionDigits: d === undefined ? 1 : d, minimumFractionDigits: 0 });
  }
  function signed(n, d) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return (n > 0 ? '+' : n < 0 ? '−' : '') + fmt(Math.abs(n), d);
  }
  function setText(el, text) { if (el && el.textContent !== text) el.textContent = text; }
  /* ⛔ 2026-10-26：f2(null) 曾算成 0.00，页面把「没有数据」说成「收 0 元」。
     缺项按契约显示「—」，不写 0。本周物理治疗费已由汇报表正文补为 16.7 万，
     但空值兜底必须保留（护理六项完成率、双萧工作量等仍有 null）。 */
  function f2(n) {
    if (n === null || n === undefined || (typeof n === 'number' && isNaN(n))) return '—';
    return (Math.round(n * 100) / 100).toFixed(2);
  }

  /* ---------- 顶部滚动带 ---------- */
  function ensureStyles() {
    if ($('#ops-live-style')) return;
    var st = document.createElement('style');
    st.id = 'ops-live-style';
    st.textContent = [
      '#ops-ticker{position:sticky;top:0;z-index:220;display:flex;align-items:center;gap:10px;height:34px;padding:0 12px;background:#0d2b4e;color:#fff;font:600 12px/1.2 -apple-system,BlinkMacSystemFont,"Noto Sans SC",sans-serif;overflow:hidden;border-bottom:1px solid rgba(247,210,121,.35)}',
      '#ops-ticker .ops-tk-label{flex:0 0 auto;color:#f7d279;letter-spacing:.08em;font-size:11px}',
      '#ops-ticker .ops-tk-view{flex:1 1 auto;overflow:hidden;white-space:nowrap;position:relative;height:34px}',
      '#ops-ticker .ops-tk-track{display:inline-flex;align-items:center;gap:26px;height:34px;will-change:transform;animation:opsTk 46s linear infinite}',
      '#ops-ticker:hover .ops-tk-track{animation-play-state:paused}',
      '#ops-ticker .ops-tk-item{display:inline-flex;align-items:baseline;gap:6px;white-space:nowrap}',
      '#ops-ticker .ops-tk-item i{font-style:normal;color:#a9c6e6;font-weight:500}',
      '#ops-ticker .ops-tk-item b{font-size:13px;color:#fff}',
      '#ops-ticker .ops-tk-item em{font-style:normal;color:#8fd9c9;font-size:11px}',
      '@keyframes opsTk{from{transform:translateX(0)}to{transform:translateX(-50%)}}',
      '@media(prefers-reduced-motion:reduce){#ops-ticker .ops-tk-track{animation:none}}',
      '.ops-auto-x{overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}',
      '.ops-auto-x::-webkit-scrollbar{display:none}',
      '.ops-vscroll{max-height:520px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:#c9d6e5 transparent}',
      '#ops-live-badge{display:inline-flex;align-items:center;gap:6px;margin-left:8px;padding:2px 8px;border-radius:999px;background:rgba(0,102,204,.08);color:#0066cc;font:600 11px/1.6 -apple-system,"Noto Sans SC",sans-serif}',
      '#ops-live-badge i{width:6px;height:6px;border-radius:50%;background:#21a6a0;box-shadow:0 0 0 3px rgba(33,166,160,.15)}',
      '#ops-scroll-toggle{position:fixed;right:14px;bottom:74px;z-index:210;border:1px solid #d8e2ee;background:#fff;color:#0d2b4e;border-radius:999px;padding:7px 12px;font:600 12px/1 -apple-system,"Noto Sans SC",sans-serif;box-shadow:0 6px 18px rgba(13,43,78,.12);cursor:pointer}',
      '#ops-scroll-toggle[data-on="1"]{background:#0d2b4e;color:#fff;border-color:#0d2b4e}',
      '@media(prefers-reduced-motion:reduce){.ops-auto-x{overflow-x:auto}}'
    ].join('\n');
    document.head.appendChild(st);
  }

  function ensureTicker() {
    if ($('#ops-ticker')) return;
    var bar = document.createElement('div');
    bar.id = 'ops-ticker';
    bar.innerHTML = '<span class="ops-tk-label">实时数据</span><div class="ops-tk-view"><div class="ops-tk-track" id="opsTkTrack"></div></div>';
    document.body.insertBefore(bar, document.body.firstChild);
  }

  function renderTicker(s) {
    var track = $('#opsTkTrack');
    if (!track) return;
    var m = s.metrics;
    var items = [
      ['本期营收', f2(m.weekRevenue.value) + ' 万', signed(m.weekRevenue.deltaPct) + '%'],
      ['物理治疗', (m.weekPhysio && m.weekPhysio.value != null)
        ? f2(m.weekPhysio.value) + ' 万' : '—（本周未报）'],
      ['日均', fmt(m.weekRevenue.valueYuan / 10000 / s.period.daysRecorded, 2) + ' 万'],
      ['入院', m.weekAdmit.value + ' 人'],
      ['出院', m.weekDischarge.value + ' 人'],
      ['在院人数', m.wardCount.value + ' 人'],
      ['门诊人次', m.weekVisits.value + ' 人次'],
      ['10月累计', f2(m.monthRevenue.value) + ' 万'],
      ['目标完成', m.monthRevenue.amountProgress + '%'],
      ['时间进度', m.monthRevenue.timeProgress + '%'],
      ['剩余缺口', f2(m.monthRevenue.gap) + ' 万']
    ];
    /* ⛔ 心理：汇报表该组表头自 2026-09-21 起未滚动（40 人 / 4 场 / 19,002 元 是 9.21—9.27 旧值），
       已停用；本周一律取 V4 管理表「咨询师每日简报」逐条（10.26—11.01 全 7 天 / 17 条，
       咨询 39 / 接触 65 / 团体 2 场 11 人；与「日报原始数据」17 键 × 8 字段零差异）。
       注：原注释把上期值（46 / 84 / 3 场）写成了本周值，2026-10-26 修正。
       客服仍取汇报表「到院接待」（与台账回访是两件事，不互算）。 */
    var dp = s.departments || {}, dpP = dp.psychology || {}, dpS = dp.service || {};
    if (dpP.consult !== undefined || dpP.contact !== undefined) {
      items.push(['心理咨询', (dpP.consult != null ? dpP.consult : '—') + ' 人次',
                  '接触 ' + (dpP.contact != null ? dpP.contact : '—') + ' · 团体 '
                  + (dpP.groupSessions != null ? dpP.groupSessions : '—') + ' 场']);
    } else if (s.psych && s.psych.week) {
      items.push(['心理接触', s.psych.week.contact + ' 人次', '咨询 ' + s.psych.week.consult]);
      items.push(['团体', s.psych.week.groupSessions + ' 场', s.psych.week.groupPeople + ' 人次']);
    }
    /* ⛔ 2026-10-26：客服本周改用三张台账，departments.service.arrived 已置 null
       （表头 239 / 14 是上一期），原来这里会显示「到院接待 — 人次 · 义诊 —」，
       把本周真实的 11 人 / 40.7% 藏掉。改为台账优先，表头只作回退。 */
    if (s.service && s.service.week) {
      items.push(['客服回访', s.service.week.followup + ' 条']);
      items.push(['标注到院', s.service.week.arrived + ' 人',
                  '到院率 ' + s.service.week.rate + '% · 导诊 ' + s.service.week.guide + ' 条']);
    } else if (dpS.arrived !== undefined) {
      items.push(['到院接待', (dpS.arrived != null ? dpS.arrived : '—') + ' 人次',
                  '义诊 ' + (dpS.charity != null ? dpS.charity : '—')]);
    }
    if (s.butler && s.butler.week) {
      items.push(['管家对接', s.butler.week.contact + ' 条', '转住院 ' + s.butler.week.admit]);
    }
    if (s.arrival) items.push(['到院登记', s.arrival.week + ' 人次', '初诊 ' + s.arrival.new]);
    items.push(['数据至', s.period.dataThrough || '—']);
    var html = items.map(function (it) {
      return '<span class="ops-tk-item"><i>' + it[0] + '</i><b>' + it[1] + '</b>' + (it[2] ? '<em>' + it[2] + '</em>' : '') + '</span>';
    }).join('');
    track.innerHTML = html + html; // 无缝循环
  }

  /* ---------- 顶部与总览 ---------- */
  function renderHeader(s) {
    var compact = window.innerWidth < 560;
    var _dt = (s.period.dataThrough || '2026-10-20');
    setText($('#periodBtn'), compact ? ('更新至 ' + _dt.slice(5).replace('-', '.'))
      : ('数据更新至 ' + _dt.slice(0, 4) + '年' + (+_dt.slice(5, 7)) + '月' + (+_dt.slice(8)) + '日'));
    // 把期间水位挂到全局，供 data-import.js 那条更晚执行的渲染链复用，避免它用「今天」冒充数据截止日
    window.__OPS_PERIOD = s.period; window.__OPS_ASOF = s.asOf;
    var live = $('.ov-live');
    if (live) {
      var span = live.querySelector('span');
      setText(span, '每日 09:00 抓取 · 数据更新至 ' + (s.period.dataThrough || '10.20'));
      if (!live.querySelector('#ops-live-badge')) {
        var b = document.createElement('span');
        b.id = 'ops-live-badge';
        b.innerHTML = '<i></i>rev ' + s.revision;
        live.appendChild(b);
      } else {
        setText(live.querySelector('#ops-live-badge'), 'rev ' + s.revision);
      }
    }
    var chip = $('#rangeChip');
    if (chip) {
      chip.innerHTML = '<i>▦</i>' + s.period.label + '（自然周）';
      chip.title = '本页主口径：自然周 ' + s.period.start + ' 至 ' + s.period.end + '（已录 ' + s.period.daysRecorded + ' 天，数据至 ' + s.period.dataThrough + '）';
    }
  }

  function renderOverview(s) {
    var m = s.metrics;
    var kpis = $('#heroKpis');
    if (kpis) {
      var cells = [
        ['在院人数', m.wardCount.value, '人', (m.wardCount.dataThrough || s.period.dataThrough || '').slice(5).replace('-', '.') + ' 时点 · 营收日报'],
        ['本期入院', m.weekAdmit.value, '人', s.period.label + '（' + s.period.daysRecorded + ' 天）'],
        ['本期出院', m.weekDischarge.value, '人', s.period.label + '（' + s.period.daysRecorded + ' 天）'],
        ['门诊', m.weekVisits.value, '人次', s.period.label + ' · 营收日报'],
        ['物理治疗费', (m.weekPhysio && m.weekPhysio.value != null) ? f2(m.weekPhysio.value) : '—',
         '万元', (m.weekPhysio && m.weekPhysio.value != null) ? s.period.label + ' · 汇报表正文（7 天）'
                                                   : '无逐日台账 · 本周记 null']
      ];
      kpis.innerHTML = cells.map(function (c) {
        return '<div class="ov-kpi"><label>' + c[0] + '</label><strong>' + c[1] + '<em>' + c[2] + '</em></strong><span class="ov-chip">' + c[3] + '</span></div>';
      }).join('');
    }

    var target = $('.ov-target');
    if (target) {
      setText(target.querySelector('.ov-chip'), '10月1日—' + (s.period.dataThrough ? ('10月' + Number(s.period.dataThrough.slice(8, 10)) + '日') : '10月20日') + ' · 营收日报');
      var amt = target.querySelector('.ov-amount strong');
      setText(amt, fmt(m.monthRevenue.value, 2));
      var em = target.querySelector('.ov-amount em');
      if (em) em.innerHTML = '／' + m.monthRevenue.targetWan + '万';
      var barI = target.querySelector('.ov-bar i');
      if (barI) barI.style.width = m.monthRevenue.amountProgress + '%';
      var barU = target.querySelector('.ov-bar u');
      if (barU) barU.style.left = m.monthRevenue.timeProgress + '%';
      var two = target.querySelector('.ov-two');
      if (two) {
        var diff = Math.round((m.monthRevenue.amountProgress - m.monthRevenue.timeProgress) * 10) / 10;
        two.innerHTML =
          '<div><span>金额完成</span><b>' + m.monthRevenue.amountProgress + '%</b></div>' +
          '<div><span>时间进度</span><b>' + m.monthRevenue.timeProgress + '%</b></div>' +
          '<div><span>进度差</span><b class="' + (diff >= 0 ? 'pos' : '') + '">' + (diff >= 0 ? '领先 ' : '落后 ') + Math.abs(diff) + 'pt</b></div>';
      }
      var gapEl = target.querySelector('.ov-gap');
      if (gapEl) {
        var remainDays = 31 - Number((s.period.dataThrough || '').slice(8, 10) || 0);
        var needDaily = remainDays > 0 ? m.monthRevenue.gap / remainDays : null;
        var weekAvg = m.weekRevenue.valueYuan / 10000 / s.period.daysRecorded;
        var overAvg = (needDaily === null) ? null : weekAvg - needDaily;
        /* ⚠ 2026-10-29：营收日报已跨周（数据至 10.28，本期窗口仍 10.26—11.01）。
           原写法只说本期 7 天日均，读者看不出新 3 天掉速 → 补「本周进行中」一段。 */
        var _wk = [], _wkPrev = [];
        (s.daily || []).forEach(function (r) {
          if (r.date > (s.period.end || '')) _wk.push(r);
          else if (r.date >= (s.period.start || '') && r.date <= (s.period.end || '')) _wkPrev.push(r);
        });
        _wkPrev = _wkPrev.slice(0, _wk.length);
        var _wkSum = 0, _pSum = 0;
        _wk.forEach(function (r) { _wkSum += Number(r.total || 0); });
        _wkPrev.forEach(function (r) { _pSum += Number(r.total || 0); });
        var _wkAvg = _wk.length ? _wkSum / _wk.length / 10000 : null;
        gapEl.innerHTML = '剩余 <b>' + remainDays + '</b> 天需 <b>' + fmt(m.monthRevenue.gap, 2) + ' 万</b>，日均需 <b>' + (needDaily === null ? '—' : fmt(needDaily, 2) + ' 万') + '</b>；本期（' + s.period.label + '，7 天，营收日报口径）日均 <b>' + fmt(weekAvg, 2) + ' 万</b>'
          + (overAvg === null ? '' : (overAvg >= 0 ? '，已高于达标日均 <b>' + fmt(overAvg, 2) + ' 万</b>' : '，低于达标日均 <b>' + fmt(-overAvg, 2) + ' 万</b>'))
          + (_wkAvg === null ? '' : '；新一周（' + _wk[0].date.slice(5).replace('-', '.') + '—' + _wk[_wk.length - 1].date.slice(5).replace('-', '.') + '，' + _wk.length + ' 天）日均仅 <b>' + fmt(_wkAvg, 2) + ' 万</b>')
          + '。';
      }
    }

    var sources = $('.ov-sources');
    if (sources) {
      var spans = sources.querySelectorAll('div > span');
      if (spans[1]) {
        spans[1].innerHTML = '营收与入出院 <b>' + s.period.label + '</b>（营收日报，已录 ' + s.period.daysRecorded + ' 天、数据至 ' + (s.period.revenueDataThrough || s.period.dataThrough) + '）；在院 <b>' + m.wardCount.value + ' 人</b>（' + (m.wardCount.dataThrough || s.period.dataThrough) + ' 时点）；上一期 <b>' + s.previousPeriod.start + '—' + s.previousPeriod.end + '</b>（同 ' + s.previousPeriod.daysRecorded + ' 天对照）；心理 / 客服 / 管家 / 护理仍停在各自源表最近一期，未随营收日报推进。';
      }
    }

    var dpDoc = ((s.departments || {}).doctor) || {};
    var summary = $('#heroSummary');
    if (summary) {
      var avg = m.weekRevenue.valueYuan / 10000 / s.period.daysRecorded;
      /* 月末推演用元值算（value 已舍入到两位小数，会把 257.77 推成 257.78） */
      var _proj = (m.monthRevenue.valueYuan || (m.monthRevenue.value * 10000)) / 10000 / m.monthRevenue.coverage.recordedDays * 31;
      summary.innerHTML =
        '<b>本期 ' + s.period.label + '（' + s.period.daysRecorded + ' 天，数据至 ' + s.period.dataThrough + '）· 营收日报（台账）</b>：营收 <b>' + fmt(m.weekRevenue.value, 2) + ' 万</b>（门诊 ' + fmt(m.weekOutpatient.value, 2) + ' ＋ 在院 ' + fmt(m.weekInpatient.value, 2) + '）；' + (dpDoc.revenueWan == null   ? '<b>《特别行动小组汇报表》医生组表头判为混合态（表头总收入 52.6 / 正文 72.5 / 页面此前 50.5 三处对不上，门诊 210 与上一期完全相同），本表本期不引用、只并列</b>；'   : '<b>《特别行动小组汇报表》医生组 10.26—11.01：总收入 ' + dpDoc.revenueWan + ' 万、物理治疗 ' + dpDoc.physioWan + ' 万（占收入 ' + Math.round(dpDoc.physioWan / dpDoc.revenueWan * 1000) / 10 + '%，是收入的科目、不可相加）、入院 ' + dpDoc.admit + ' 人、出院 ' + dpDoc.discharge + ' 人、门诊 ' + dpDoc.outpatient + ' 人次</b>；') + '台账口径入院 <b>' + m.weekAdmit.value + '</b> 人、出院 <b>' + m.weekDischarge.value + '</b> 人、门诊 <b>' + m.weekVisits.value + '</b> 人次；上期同 ' + s.period.daysRecorded + ' 天（' + s.previousPeriod.start + '—' + s.previousPeriod.compareSameDaysEnd + '）<b>' + fmt(m.weekRevenue.valueYuan / (1 + (m.weekRevenue.deltaPct || 0) / 100) / 10000, 2) + ' 万</b>，总量 <b>' + signed(m.weekRevenue.deltaPct) + '%</b>。10 月累计 <b>' + fmt(m.monthRevenue.value, 2) + ' 万</b> / 目标 ' + m.monthRevenue.targetWan + ' 万 = <b>' + m.monthRevenue.amountProgress + '%</b>，时间进度 ' + m.monthRevenue.timeProgress + '%，差 <b>' + signed(Math.round((m.monthRevenue.amountProgress - m.monthRevenue.timeProgress) * 10) / 10) + 'pt</b>，剩余缺口 <b>' + fmt(m.monthRevenue.gap, 2) + ' 万</b>。' + ((_wk && _wk.length && _wkAvg != null) ? ('<b>新一周进行中 ' + _wk[0].date.slice(5).replace('-', '.') + '—' + _wk[_wk.length - 1].date.slice(5).replace('-', '.') + '（' + _wk.length + ' 天）：' + fmt(_wkSum / 10000, 2) + ' 万</b>，日均 <b>' + fmt(_wkAvg, 2) + ' 万</b>'   + (_pSum ? '，较上周同期（' + _wkPrev[0].date.slice(5).replace('-', '.') + '—' + _wkPrev[_wkPrev.length - 1].date.slice(5).replace('-', '.') + '）' + fmt(_pSum / 10000, 2) + ' 万 <b>' + signed(Math.round((_wkSum - _pSum) / _pSum * 1000) / 10) + '%</b>' : '')   + '；按全月日均推演月末 <b>' + fmt(_proj, 2) + ' 万</b>，' + ((_proj) >= m.monthRevenue.targetWan ? '超出目标 <b>' + fmt(_proj - m.monthRevenue.targetWan, 2) + ' 万</b>' : '差目标 <b>' + fmt(m.monthRevenue.targetWan - _proj, 2) + ' 万</b>') + '。') : '') + '在院 <b>' + m.wardCount.value + ' 人</b>（' + (m.wardCount.dataThrough || s.period.dataThrough) + ' 时点，营收日报）——<b>营收日报的入出院/门诊数与主表不同源，本页一律以主表为准</b>。';
    }
  }

  /* ---------- 部门卡：按同一 revision 换数（不动 DOM 结构与点击行为） ---------- */
  function patchDepartments(s) {
    var d = s.departments || {}, p = s.psych || {}, sv = s.service || {}, bt = s.butler || {};
    var m = s.metrics;
    var map = {
      /* 2026-10-26 09:55 修：营收日报补齐 10.24/10.25，本期满 7 天（58.35 万），
         而汇报表医生组「本周总收入」表头 52.6 / 正文 72.5 / 页面 50.5 三处对不上，
         判为混合态 → 医生卡总额改取营收台账 weekRevenue（可逐日勾稽），
         物理治疗仍取汇报表正文 16.7 万（该科目台账没有拆分）。 */
      doctor: [['本周总收入', m.weekRevenue ? m.weekRevenue.value : null, '万'],
               ['物理治疗', (d.doctor || {}).physioWan, '万']],
      nursing: [['六项完成率', d.nursing && d.nursing.treatSummary ? d.nursing.treatSummary.rate : null, '%'],
                ['实做人次', d.nursing && d.nursing.treatSummary ? d.nursing.treatSummary.done : null, '人次']],
      psychology: [['咨询工作量', p.week ? p.week.consult : null, '人次'],
                   ['患者接触', p.week ? p.week.contact : null, '人次']],
      service: [['回访台账', sv.week ? sv.week.followup : null, '条'],
                ['标注到院率', sv.week ? sv.week.rate : null, '%']],
      marketing: [['管家对接', bt.week ? bt.week.contact : null, '条'],
                  ['转住院率', bt.week ? bt.week.rate : null, '%']]
    };
    Object.keys(map).forEach(function (k) {
      var card = document.querySelector('.dept-card[data-dept="' + k + '"]');
      if (!card) return;
      var cells = card.querySelectorAll('.dc-metric');
      map[k].forEach(function (row, i) {
        var el = cells[i];
        if (!el || row[1] === null || row[1] === undefined) return;
        var lab = el.querySelector('label'), st = el.querySelector('strong');
        if (lab) setText(lab, row[0]);
        if (st) st.innerHTML = row[1] + '<em>' + (row[2] || '') + '</em>';
      });
    });
  }

  /* ---------- 月面板「部门经营」五卡（month-dashboard 渲染的 .md-dept） ----------
     ⚠ 2026-10-18：这五张卡由 month-dashboard.js 的 shell() 渲染，数据取自它自己的
     baseData + localStorage（键 hospital-month-dashboard-v3-20260926），与快照无关 ——
     所以业主看到的是 9 月口径的旧值（心理 65、客服 74、营销挂营业额 19.58 万）。
     这里只覆盖显示层、不动它的数据对象，rerender()/localStorage 都不会把数字改回去。
     护理卡的物理治疗六项已于 2026-10-26 按业主实报值填入（652/605/92.8%）。 */
  function patchMdDepartments(s) {
    var m = s.metrics || {}, p = (s.psych || {}).week || {},
        sv = (s.service || {}).week || {}, bt = (s.butler || {}).week || {},
        dp = s.departments || {}, dpPsy = dp.psychology || {}, dpSvc = dp.service || {},
        dpNur = dp.nursing || {};
    var wm = s.watermarks || {}, lab = s.period ? s.period.label : '';
    function wd(k) {
      var w = wm[k];
      return w && w.dataThrough ? w.dataThrough.slice(5).replace('-', '.') : '—';
    }
    function num(v, unit) {
      return (v === null || v === undefined) ? null : v + unit;
    }
    var spec = {
      doctor: {
        /* 2026-11-02：汇报表第 5 周整行空白，医生组改用业主《出院结帐明细表》口径。
           departments.doctor 仍是汇报表口径（全 null），故优先读 departments.doctorWeek。 */
        metric: (dp.doctorWeek && dp.doctorWeek.totals) ? dp.doctorWeek.totals.revenueWan + ' 万'
                : num(dp.doctor && dp.doctor.revenueWan, ' 万'),
        note: (dp.doctorWeek && dp.doctorWeek.totals) ? '本期 ' + lab + ' · 出院结账（7 天）'
                : '本期 ' + lab + ' · 汇报表总收入',
        foot: (dp.doctorWeek && dp.doctorWeek.totals)
                ? '物理 ' + dp.doctorWeek.totals.physioWan + ' 万 · 出院 ' + dp.doctorWeek.totals.discharge
                  + ' · 在院 ' + dp.doctorWeek.totals.inWard
                : '物理 ' + ((dp.doctor && dp.doctor.physioWan) != null ? dp.doctor.physioWan : '—')
                  + ' 万 · 在院 ' + (m.wardCount ? m.wardCount.value : '—')
      },
      psychology: {
        /* 本周唯一口径＝V4 管理表；汇报表该组表头停在 9.21 旧值，已停用 */
        metric: num(dpPsy.contact, ' 人次'),
        note: '本期 ' + lab + ' · 患者接触（V4）',
        foot: '咨询 ' + (dpPsy.consult != null ? dpPsy.consult : '—') + ' 人次 · 团体 '
              + (dpPsy.groupSessions != null ? dpPsy.groupSessions : '—') + ' 场 '
              + (dpPsy.groupPeople != null ? dpPsy.groupPeople + ' 人' : '')
      },
      nursing: {
        /* 2026-11-02：本期考核表已交（10.26—11.01，7 天 / 17 行），
           五卡主指标改取六项治疗完成率；未交时仍退回「未交」。 */
        metric: dpNur.weeklySubmitted
          ? ((dpNur.treatSummary && dpNur.treatSummary.rate != null) ? dpNur.treatSummary.rate + '%' : '已交')
          : '未交',
        note: dpNur.weeklySubmitted ? '本期 ' + lab + ' · 六项治疗完成率'
                : '本期 ' + lab + ' · 考核表未提交',
        foot: dpNur.weeklySubmitted
          ? '630 / 699 · 未做 ' + ((dpNur.treatSummary && dpNur.treatSummary.missed != null) ? dpNur.treatSummary.missed : '—')
          : '本周记 null · 存档值仅作留档'
      },
      service: {
        /* 2026-10-26：客服改用「三张台账」口径（原来读 departments.service.arrived，
           那是汇报表表头的 239 人、本周未滚动，会把真实的 28 条 / 39.3% 盖掉）。
           回访台账已滚到 10.25（全 7 天），导诊表止 10.21 单列说明。 */
        metric: num(sv.followup, ' 条'),
        note: '本期 ' + lab + ' · 回访（台账至 ' + wd('service') + '）',
        foot: '到院 ' + (sv.arrived != null ? sv.arrived : '—') + ' 人 · '
              + (sv.rate != null ? sv.rate : '—') + '%（导诊 ' + (sv.guide != null ? sv.guide : '—') + ' 条·6 天）'
      },
      marketing: {
        /* 2026-10-26：管家表已滚到 10.25（7 天），截止日改由快照 watermark 驱动，
           不再写死「至 10.23」；总排名按业主汇总表「权重」列，见 month-dashboard.js */
        metric: num(bt.contact, ' 条'),
        note: '本期 ' + lab + ' · 管家有效对接（7 天，至 ' + wd('butler') + '）',
        foot: '转住院 ' + (bt.admit != null ? bt.admit : '—') + ' · ' + (bt.rate != null ? bt.rate : '—') + '%'
      }
    };
    Object.keys(spec).forEach(function (k) {
      var card = document.querySelector('.md-dept[data-dept="' + k + '"]');
      if (!card) return;
      var sp = spec[k];
      var st = card.querySelector('.md-dept-metric strong');
      var nt = card.querySelector('.md-dept-metric span');
      var ft = card.querySelector('.md-dept-foot span');
      if (st && sp.metric) st.textContent = sp.metric;
      if (nt && sp.note) nt.textContent = sp.note;
      if (ft && sp.foot) ft.textContent = sp.foot;
    });
  }

  /* ---------- 旧版 #deptGrid 兜底同步 ----------
     #deptGrid 由 month-dashboard 加了 .md-legacy-hidden（display:none!important），日常不可见；
     但它的数字来自 index.html 静态嵌入的 departments 对象，属于第三处硬编码。
     一旦月面板挂载失败（脚本 404 / 沙箱缺文件），这组卡就是唯一可见内容——不能让它留着第 2 周旧值。
     只改写「值 + em 单位」，label 与卡片结构保持原样，幂等可重复调用。 */
  function patchLegacyDeptGrid(s) {
    var g = document.getElementById('deptGrid');
    if (!g) return;
    var dp = s.departments || {}, bt = (s.butler || {}).week || {};
    var dD = dp.doctor || {}, dN = dp.nursing || {}, dP = dp.psychology || {},
        dS = dp.service || {};
    /* 顺序必须与 index.html DEPT_CARD 的 m1 / m2 一致 */
    var spec = {
      /* ⚠ 2026-10-22：doctor 的顺序原先写的是 [[出院,'人'],[物理治疗,'万']]，
         而 DEPT_CARD 的标签已改为「总收入 / 本周入院」→ 页面渲染成
         「总收入 17 人 / 本期入院 32.9 万」。此数组必须与 DEPT_CARD.doctor 的 m1/m2 同序。 */
      /* 2026-11-02：汇报表表头空白时 dD.* 全为 null；改读 doctorWeek（出院结账） */
      doctor: (dp.doctorWeek && dp.doctorWeek.totals)
        ? [[dp.doctorWeek.totals.revenueWan, '万'], [dp.doctorWeek.totals.physioWan, '万']]
        : [[dD.revenueWan, '万'], [dD.physioWan, '万']],
      /* 2026-11-02：护理卡 m1/m2 已改为「六项完成率 / 实做人次」，
         数据取本期考核表 treatSummary（weeklySubmitted=true 时有效）。 */
      nursing: (dN.weeklySubmitted && dN.treatSummary)
        ? [[dN.treatSummary.rate, '%'], [dN.treatSummary.done, '人次']]
        : [[null, '%'], [null, '分']],
      psychology: [[dP.consult, '人次'], [dP.contact, '人次']],
      /* 2026-11-02：DEPT_CARD 的 m1/m2 已是「回访条数 / 标注到院率」，
         必须读 service.week，不能再用 departments.service（那是汇报表表头、本周全空） */
      service: [[(s.service && s.service.week || {}).followup, '条'],
                [(s.service && s.service.week || {}).rate, '%']],
      marketing: [[bt.contact, '条'], [bt.rate, '%']]
    };
    Object.keys(spec).forEach(function (k) {
      var card = g.querySelector('.dept-card[data-dept="' + k + '"]');
      if (!card) return;
      var mets = card.querySelectorAll('.dc-metric strong');
      spec[k].forEach(function (pair, i) {
        var v = pair[0], u = pair[1];
        if (v === null || v === undefined || !mets[i]) return;
        mets[i].innerHTML = v + (u ? '<em>' + u + '</em>' : '');
      });
    });
  }

  /* ---------- AI 摘要条：按同一 revision 换数 ---------- */
  function patchAiStrip(s) {
    var strip = document.querySelector('.ai-balance-strip');
    if (!strip) return;
    var conf = s.conflicts || [];
    var warn = conf.filter(function (c) { return c.severity === 'warn'; }).length;
    var up = 0, down = 0;
    Object.keys(s.metrics || {}).forEach(function (k) {
      var v = s.metrics[k].deltaPct;
      if (typeof v === 'number') { if (v > 0) up++; else if (v < 0) down++; }
    });
    var b = strip.querySelectorAll('.ai-balance-item b');
    if (b[0]) b[0].textContent = warn;
    if (b[1]) b[1].textContent = up;
    if (b[2]) b[2].textContent = down;
    if (b[3]) b[3].textContent = conf.length;
  }

  /* ---------- 数据源状态 ---------- */
  function renderSources(s) {
    var host = $('.ov-sources');
    if (!host) return;
    var old = $('#ops-source-strip');
    if (old) old.remove();
    var wrap = document.createElement('div');
    wrap.id = 'ops-source-strip';
    wrap.style.cssText = 'margin:10px 0 0;padding:10px 12px;border:1px solid #e3ebf5;border-radius:12px;background:#fbfdff;font:12px/1.6 -apple-system,BlinkMacSystemFont,"Noto Sans SC",sans-serif;color:#39506b';
    var ok = s.sources.filter(function (x) { return x.status !== 'authorization_pending' && x.enabled; }).length;
    var pending = s.sources.filter(function (x) { return x.status === 'authorization_pending'; }).length;
    wrap.innerHTML =
      '<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px">' +
        '<b style="color:#0d2b4e">数据源 · ' + s.sources.length + ' 份</b>' +
        '<span style="color:#5b7189">已接入 ' + ok + ' · 待授权 ' + pending + ' · revision ' + s.revision + '</span>' +
      '</div>' +
      '<div style="display:flex;flex-wrap:wrap;gap:6px">' +
      s.sources.map(function (x) {
        var isPending = x.status === 'authorization_pending';
        var color = isPending ? '#b7791f' : '#0e8f71';
        var bg = isPending ? '#fff7e6' : '#eaf7f2';
        return '<span title="' + (x.note || '') + '" style="display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:999px;background:' + bg + ';color:' + color + '">' +
          '<i style="width:6px;height:6px;border-radius:50%;background:' + color + '"></i>' + x.name +
          (x.dataThrough ? ' · 至 ' + x.dataThrough.slice(5).replace('-', '.') : '') + '</span>';
      }).join('') + '</div>' +
      (s.conflicts && s.conflicts.length
        ? '<div style="margin-top:6px;padding:6px 8px;border-radius:8px;background:#fff7e6;color:#8a5a00">' +
            '⚠ 待核 ' + s.conflicts.length + ' 项：' +
            s.conflicts.map(function (c) { return c.label; }).join('；') +
            '<span style="color:#a07830">（按契约以逐日事实为准，累计列不静默抹平）</span>' +
          '</div>'
        : '') +
      '<div style="margin-top:6px;color:#6b8098">采集节奏：每 5 分钟检查源 · 指纹变化才发布新 revision · 前端 30 秒轮询并自动刷新</div>';
    host.parentNode.insertBefore(wrap, host.nextSibling);
  }


  /* ---------- 营销分析面板（开屏默认展开）接到同一份数据 ---------- */
  function patchMarketing(s) {
    var shell = document.querySelector('#salesWorkspace .sales-shell');
    if (!shell || !shell.classList.contains('mkt-v2')) return;
    var m = s.metrics;
    var avg = m.weekRevenue.valueYuan / 10000 / s.period.daysRecorded;
    var last7 = s.daily.slice(-7);
    var maxDay = Math.max.apply(null, last7.map(function (r) { return r.total; })) || 1;
    var wd = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

    var amount = shell.querySelector('.mkt-amount');
    if (amount) amount.innerHTML = '¥' + f2(m.weekRevenue.value) + '<i>万</i>';
    var sub = shell.querySelector('.mkt-sub');
    if (sub) sub.textContent = s.period.label + ' · 日均 ¥' + f2(avg) + '万';

    var filter = shell.querySelector('.mkt-filter small');
    if (filter) filter.innerHTML = '<b>●</b> 数据更新至 ' + (s.period.dataThrough || '').replace(/-/g, '.') + '　·　本期 ' + s.period.label + '（已录 ' + s.period.daysRecorded + ' 天）';

    var kpis = shell.querySelector('.mkt-kpis');
    if (kpis) {
      var items = [
        ['♧', '门诊收入', '¥' + f2(m.weekOutpatient.value) + '万', '占本期 ' + Math.round(m.weekOutpatient.value / m.weekRevenue.value * 1000) / 10 + '%', ''],
        ['▥', '住院收入', '¥' + f2(m.weekInpatient.value) + '万', '占本期 ' + Math.round(m.weekInpatient.value / m.weekRevenue.value * 1000) / 10 + '%', ''],
        ['＋', '初诊', m.weekVisits.visitsNew + '人', '本期 ' + s.period.label, 'green'],
        ['↗', '入院', m.weekAdmit.value + '人', '初诊转入院 ' + (m.weekVisits.visitsNew ? Math.round(m.weekAdmit.value / m.weekVisits.visitsNew * 1000) / 10 : '—') + '%', 'green'],
        ['－', '出院', m.weekDischarge.value + '人', '患者池流出', 'purple'],
        ['◎', '在院', m.wardCount.value + '人', (s.period.dataThrough || '') + ' 时点', '']
      ];
      kpis.innerHTML = items.map(function (x) {
        return '<article class="mkt-kpi ' + x[4] + '"><div class="mkt-kpi-head"><i class="mkt-ico">' + x[0] + '</i>' + x[1] + '</div><strong>' + x[2] + '</strong><span>' + x[3] + '</span></article>';
      }).join('');
    }

    var badge = shell.querySelector('.mkt-badge');
    var diff = Math.round((m.monthRevenue.amountProgress - m.monthRevenue.timeProgress) * 10) / 10;
    if (badge) badge.textContent = (diff >= 0 ? '领先 ' : '落后 ') + Math.abs(diff) + 'pt';
    var big = shell.querySelector('.mkt-progress-big b');
    if (big) big.textContent = f2(m.monthRevenue.value) + '万 / ' + m.monthRevenue.targetWan + '万';
    var line = shell.querySelector('.mkt-progress-line');
    if (line) { line.style.setProperty('--done', m.monthRevenue.amountProgress + '%'); line.style.setProperty('--time', m.monthRevenue.timeProgress + '%'); }
    var li = shell.querySelector('.mkt-progress-line i'); if (li) li.style.width = m.monthRevenue.amountProgress + '%';
    var lb = shell.querySelector('.mkt-progress-line b'); if (lb) { lb.style.left = m.monthRevenue.timeProgress + '%'; lb.title = '时间进度 ' + m.monthRevenue.timeProgress + '%'; }
    var meta = shell.querySelector('.mkt-progress-meta');
    if (meta) meta.innerHTML = '<span>金额完成 <strong>' + m.monthRevenue.amountProgress + '%</strong></span><span>时间进度 ' + m.monthRevenue.timeProgress + '%</span>';
    var gap = shell.querySelector('.mkt-gap');
    if (gap) {
      var remainDays = 31 - Number((s.period.dataThrough || '').slice(8, 10) || 0);
      gap.innerHTML = '<div><span>剩余目标</span><b>' + f2(m.monthRevenue.gap) + '万</b></div><div><span>剩余天数</span><b>' + remainDays + '天</b></div><div><span>日均需完成</span><b>' + (remainDays ? f2(m.monthRevenue.gap / remainDays) : '—') + '万</b></div><div><span>当前日均</span><b>' + f2(avg) + '万</b></div>';
    }

    var bars = shell.querySelector('.mkt-bars');
    if (bars) {
      bars.innerHTML = last7.map(function (r) {
        var d = new Date(r.date + 'T00:00:00+08:00');
        return '<div class="mkt-bar ' + ((d.getDay() === 0 || d.getDay() === 6) ? 'weekend' : '') + '"><em>' + f2(r.total / 10000) + '万</em><i style="--h:' + Math.round(r.total / maxDay * 100) + '%"></i><span>' + r.date.slice(5).replace('-', '.') + '</span></div>';
      }).join('');
    }
    var barsHead = shell.querySelectorAll('.mkt-card-head p');
    if (barsHead[1]) barsHead[1].textContent = last7.length ? last7[0].date.slice(5).replace('-', '.') + '—' + last7[last7.length - 1].date.slice(5).replace('-', '.') + ' 逐日' : '';

    var ring = shell.querySelector('.mkt-ring b'); if (ring) ring.textContent = f2(m.weekRevenue.value) + '万';
    var legend = shell.querySelector('.mkt-legend');
    if (legend) {
      var op = Math.round(m.weekOutpatient.value / m.weekRevenue.value * 1000) / 10;
      legend.innerHTML = '<span><b style="color:#26ae81">' + op + '%</b>门诊 ' + f2(m.weekOutpatient.value) + '万</span><span><b style="color:#2e8ee9">' + (Math.round((100 - op) * 10) / 10) + '%</b>住院 ' + f2(m.weekInpatient.value) + '万</span>';
    }
    var flow = shell.querySelector('.mkt-flow');
    if (flow) flow.innerHTML = '<div class="mkt-flow-box">初诊<b>' + m.weekVisits.visitsNew + '</b>人</div><div class="mkt-arrow">→</div><div class="mkt-flow-box green">入院<b>' + m.weekAdmit.value + '</b>人</div>';
    var outs = shell.querySelectorAll('.mkt-outflow');
    if (outs[0]) outs[0].innerHTML = '<span>初诊转入院</span><b>' + (m.weekVisits.visitsNew ? Math.round(m.weekAdmit.value / m.weekVisits.visitsNew * 1000) / 10 : '—') + '%</b>';
    if (outs[1]) outs[1].innerHTML = '<span>本期出院</span><b>' + m.weekDischarge.value + '人</b>';

    var cmp = shell.querySelector('.mkt-compare');
    if (cmp) {
      var prevTotal = m.weekRevenue.value / (1 + (m.weekRevenue.deltaPct || 0) / 100);
      cmp.innerHTML =
        '<div class="mkt-compare-row"><b>本期营业额</b><span>' + f2(prevTotal) + ' → ' + f2(m.weekRevenue.value) + '万</span><strong>' + signed(m.weekRevenue.deltaPct) + '%</strong></div>' +
        '<div class="mkt-compare-row"><b>门诊收入</b><span>' + f2(m.weekOutpatient.value) + '万</span><strong>' + signed(m.weekOutpatient.deltaPct) + '%</strong></div>' +
        '<div class="mkt-compare-row"><b>门诊人次</b><span>' + m.weekVisits.value + '人次</span><strong>' + signed(m.weekVisits.deltaPct) + '%</strong></div>' +
        '<div class="mkt-compare-row"><b>入院人数</b><span>' + m.weekAdmit.value + '人</span><strong>' + signed(m.weekAdmit.deltaPct) + '%</strong></div>';
    }
    var lists = shell.querySelectorAll('.mkt-list');
    if (lists[0]) lists[0].innerHTML =
      '<li><i>1</i><span>本期营收 ' + f2(m.weekRevenue.value) + ' 万，较上期同 ' + s.period.daysRecorded + ' 天 ' + signed(m.weekRevenue.deltaPct) + '%。</span></li>' +
      '<li><i>2</i><span>门诊 ' + f2(m.weekOutpatient.value) + ' 万、在院 ' + f2(m.weekInpatient.value) + ' 万；门诊占 ' + Math.round(m.weekOutpatient.value / m.weekRevenue.value * 1000) / 10 + '%。</span></li>' +
      '<li><i>3</i><span>入院 ' + m.weekAdmit.value + '、出院 ' + m.weekDischarge.value + '，患者池净 ' + (m.weekAdmit.value - m.weekDischarge.value >= 0 ? '+' : '') + (m.weekAdmit.value - m.weekDischarge.value) + ' 人。</span></li>';
    if (lists[1]) lists[1].innerHTML =
      '<li><i>1</i><span>10 月累计 ' + f2(m.monthRevenue.value) + ' 万 / 目标 ' + m.monthRevenue.targetWan + ' 万 = ' + m.monthRevenue.amountProgress + '%。</span></li>' +
      '<li><i>2</i><span>时间进度 ' + m.monthRevenue.timeProgress + '%，差 ' + signed(diff) + 'pt，剩余缺口 ' + f2(m.monthRevenue.gap) + ' 万。</span></li>' +
      '<li><i>3</i><span>剩余 ' + (31 - Number((s.period.dataThrough || '').slice(8, 10) || 0)) + ' 天，日均需 ' + f2(m.monthRevenue.gap / Math.max(1, 31 - Number((s.period.dataThrough || '').slice(8, 10) || 0))) + ' 万。</span></li>';

    var src = shell.querySelector('.mkt-source');
    if (src) src.textContent = '口径：本期 ' + s.period.start + '—' + s.period.end + '（已录 ' + s.period.daysRecorded + ' 天，营收数据至 ' + s.period.dataThrough + '）；上一期同 ' + s.previousPeriod.daysRecorded + ' 天 ' + s.previousPeriod.start + '—' + s.previousPeriod.compareSameDaysEnd + '；10 月累计为逐日「当日合计」之和，与源表累计列的 11.00 元差异已登记待核。';
  }

  /* ---------- 自动滚动 ---------- */
  var scrollTimers = [];
  function clearScrollers() {
    scrollTimers.forEach(function (t) { cancelAnimationFrame(t.raf); });
    scrollTimers = [];
  }

  function marqueeX(el, speed) {
    if (!el) return;
    var dir = 1;
    function step() {
      if (!STATE.autoScroll) { scrollTimers.push({ raf: requestAnimationFrame(step) }); return; }
      var max = el.scrollWidth - el.clientWidth;
      if (max > 4) {
        el.scrollLeft += dir * speed;
        if (el.scrollLeft >= max - 1) dir = -1;
        if (el.scrollLeft <= 0) dir = 1;
      }
      var rec = { raf: requestAnimationFrame(step) };
      scrollTimers.push(rec);
    }
    scrollTimers.push({ raf: requestAnimationFrame(step) });
  }

  function marqueeY(el, speed) {
    if (!el) return;
    if (el.scrollHeight <= el.clientHeight + 4) return;
    var dir = 1, pause = 0;
    function step() {
      if (!STATE.autoScroll) { scrollTimers.push({ raf: requestAnimationFrame(step) }); return; }
      if (pause > 0) { pause--; }
      else {
        var max = el.scrollHeight - el.clientHeight;
        el.scrollTop += dir * speed;
        if (el.scrollTop >= max - 1) { dir = -1; pause = 90; }
        if (el.scrollTop <= 0) { dir = 1; pause = 90; }
      }
      scrollTimers.push({ raf: requestAnimationFrame(step) });
    }
    scrollTimers.push({ raf: requestAnimationFrame(step) });
  }

  function applyAutoScroll() {
    clearScrollers();
    $$('#heroKpis, #kpiGrid, #deptGrid, .ov-sources, .rk-tabs, .ai-balance-strip').forEach(function (el) {
      el.classList.add('ops-auto-x');
      marqueeX(el, 0.45);
    });
    $$('#signalList, #taskList').forEach(function (el) {
      el.classList.add('ops-vscroll');
      marqueeY(el, 0.3);
    });
    // 明细表横向滚动
    $$('table').forEach(function (tb) {
      var wrap = tb.parentElement;
      if (wrap && wrap.scrollWidth > wrap.clientWidth + 4) {
        wrap.classList.add('ops-auto-x');
        marqueeX(wrap, 0.4);
      }
    });
  }

  function ensureToggle() {
    if ($('#ops-scroll-toggle')) return;
    var b = document.createElement('button');
    b.id = 'ops-scroll-toggle';
    b.type = 'button';
    b.dataset.on = STATE.autoScroll ? '1' : '0';
    b.textContent = STATE.autoScroll ? '自动滚动 · 开' : '自动滚动 · 关';
    b.onclick = function () {
      STATE.autoScroll = !STATE.autoScroll;
      localStorage.setItem('ops.autoscroll', STATE.autoScroll ? 'on' : 'off');
      b.dataset.on = STATE.autoScroll ? '1' : '0';
      b.textContent = STATE.autoScroll ? '自动滚动 · 开' : '自动滚动 · 关';
      applyAutoScroll();
    };
    document.body.appendChild(b);
  }

  function ensureLiveBadge(s) {
    var bar = $('#ops-ticker');
    if (!bar) return;
    var b = $('#ops-live-badge');
    if (!b) {
      b = document.createElement('span');
      b.id = 'ops-live-badge';
      b.style.cssText = 'flex:0 0 auto;display:inline-flex;align-items:center;gap:5px;padding:2px 8px;' +
        'border-radius:999px;background:rgba(247,210,121,.16);color:#f7d279;font-size:11px;font-weight:600';
      bar.appendChild(b);
    }
    b.innerHTML = '<i style="width:6px;height:6px;border-radius:50%;background:#21a6a0;display:inline-block"></i>rev ' +
      s.revision + ' · 自动同步';
  }


  /* ---------- 数字滚动（尊重「减少动态效果」系统设置；每次页面加载只播一次） ---------- */
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var heroRolledOnce = false;

  function countUp(el, to, decimals, dur) {
    if (!el || REDUCED || typeof to !== 'number' || !isFinite(to)) return;
    var from = parseFloat(String(el.dataset.prev || el.textContent || '0').replace(/[^\d.-]/g, '')) || 0;
    if (from === to) { el.textContent = to.toFixed(decimals); return; }
    var t0 = null;
    function frame(ts) {
      if (t0 === null) t0 = ts;
      var k = Math.min(1, (ts - t0) / (dur || 720));
      var e = 1 - Math.pow(1 - k, 3);
      el.textContent = (from + (to - from) * e).toFixed(decimals);
      if (k < 1) requestAnimationFrame(frame);
      else { el.textContent = to.toFixed(decimals); el.dataset.prev = to; }
    }
    requestAnimationFrame(frame);
  }

  /* ⚠ renderOverview 已经把最终数字写进 DOM。这里只在「本次页面加载的第一次」做滚动，
     之后（含 30 秒轮询重绘）一律直接落定 —— 否则每次刷新都会从 0 重滚，
     中途被读到就会显示 3 / 0 / 15 这类不存在于任何源表的中间值。 */
  function animateKpis() {
    var play = !REDUCED && !heroRolledOnce;
    heroRolledOnce = true;
    document.querySelectorAll('#heroKpis .ov-kpi').forEach(function (k, i) {
      var st = k.querySelector('strong');
      if (!st || !st.firstChild || st.firstChild.nodeType !== 3) return;
      var node = st.firstChild;
      var to = parseFloat(String(node.nodeValue || '').replace(/[^\d.-]/g, ''));
      if (!isFinite(to)) return;
      var dec = String(node.nodeValue).indexOf('.') >= 0 ? 1 : 0;
      if (!play) { node.nodeValue = to.toFixed(dec); return; }
      var t0 = null;
      function frame(ts) {
        if (t0 === null) t0 = ts + i * 70;
        var kk = Math.min(1, Math.max(0, (ts - t0) / 620));
        var e = 1 - Math.pow(1 - kk, 3);
        node.nodeValue = (to * e).toFixed(dec);
        if (kk < 1) requestAnimationFrame(frame);
        else node.nodeValue = to.toFixed(dec);
      }
      requestAnimationFrame(frame);
    });
  }

  /* ---------- 核心指标磁贴：按快照换数（保留原 onclick，不重建 DOM） ---------- */
  function patchKpiTiles(s) {
    var m = s.metrics, p = s.psych || {}, sv = s.service || {}, bt = s.butler || {}, ar = s.arrival || {},
        dp = s.departments || {}, dpPsy = dp.psychology || {}, dpSvc = dp.service || {},
        dpNur = dp.nursing || {};
    function pct(v) { return (typeof v === 'number') ? ((v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%') : null; }
    var rows = [
      ['本期营收', f2(m.weekRevenue.value), '万元', pct(m.weekRevenue.deltaPct)],
      ['门诊人次', m.weekVisits.value, '人次', pct(m.weekVisits.deltaPct)],
      ['本期入院', m.weekAdmit.value, '人', pct(m.weekAdmit.deltaPct)],
      ['本期出院', m.weekDischarge.value, '人', pct(m.weekDischarge.deltaPct)],
      ['物理治疗费', m.weekPhysio ? m.weekPhysio.value : null, '万元', m.weekPhysio ? pct(m.weekPhysio.deltaPct) : null],
      ['在院人数', m.wardCount.value, '人', null],
      ['护理 6 项治疗完成率',
        dpNur.treatSummary ? dpNur.treatSummary.rate : null, '%',
        dpNur.treatSummary ? (dpNur.treatSummary.done + '/' + dpNur.treatSummary.due) : null],
      ['心理', dpPsy.consult != null ? dpPsy.consult : (p.week ? p.week.consult : null), '人次',
        (dpPsy.contact != null ? '接触 ' + dpPsy.contact : null)],
      ['客服', dpSvc.arrived != null ? dpSvc.arrived : (sv.week ? sv.week.followup : null), '人次', null],
      ['管家', bt.week ? bt.week.contact : null, '条', bt.week ? pct(Math.round((bt.week.contact - bt.prevSameDays.contact) / Math.max(1, bt.prevSameDays.contact) * 1000) / 10) : null],
      ['到院登记', ar.week, '人次', (ar.prevSameDays ? pct(Math.round((ar.week - ar.prevSameDays) / Math.max(1, ar.prevSameDays) * 1000) / 10) : null)],
      ['10 月累计', f2(m.monthRevenue.value), '万 / ' + m.monthRevenue.targetWan + ' 万',
        m.monthRevenue.amountProgress + '%（时间 ' + m.monthRevenue.timeProgress + '%）']
    ];
    document.querySelectorAll('#kpiGrid .kpi-tile').forEach(function (tile) {
      var lab = tile.querySelector('label');
      if (!lab) return;
      var text = lab.textContent.trim(), row = null;
      for (var i = 0; i < rows.length; i++) { if (text.indexOf(rows[i][0]) === 0) { row = rows[i]; break; } }
      if (!row || row[1] === null || row[1] === undefined) return;
      var st = tile.querySelector('strong');
      if (st) st.innerHTML = row[1] + '<em>' + row[2] + '</em>';
      var d = tile.querySelector('.kpi-delta');
      if (d && row[3]) {
        d.textContent = row[3];
        d.className = 'kpi-delta ' + (String(row[3]).charAt(0) === '+' ? 'up' : String(row[3]).charAt(0) === '−' ? 'down' : 'flat');
      }
      // 标签里的期间/时点同步到最新数据日
      if (text.indexOf('（') > 0) {
        lab.textContent = text.replace(/（[^）]*）/, '（' + (s.period.label) + '）');
      }
    });
  }

  /* ---------- 拉取与轮询 ---------- */
  function render(s) {
    STATE.snap = s;
    STATE.rev = s.revision;
    // 暴露给页面既有渲染器（如 month-dashboard 的「勾稽」卡）读取 conflicts / status
    window.OPS_LIVE_SNAPSHOT = s;
    ensureTicker();
    /* ⛔ 必须先派发、后打补丁。
       october-board（月累计卡）与 final-enhancements（侧栏营收进度）要用汇报表口径重算，
       但 month-dashboard.js:553 收到这个事件会 data=clone(baseData) 后 rerender()，
       把五张部门卡整块按它自己的静态 baseData 重画 —— 若补丁跑在派发之前，会被整块盖回旧值
       （实测：KPI 磁贴对、部门卡全是 495/24、80 人次、37 条这些静态数）。
       所以顺序固定为：派发 → 等月面板同步重绘完 → 再补卡。 */
    try {
      window.dispatchEvent(new CustomEvent('september-revenue-updated', { detail: { source: 'ops-live' } }));
    } catch (e) { }
    // 每一步独立兜底：任一模块数据形状异常，不阻断其余模块刷新
    [['ticker', function () { renderTicker(s); }],
     ['badge', function () { ensureLiveBadge(s); }],
     ['header', function () { renderHeader(s); }],
     ['overview', function () { renderOverview(s); }],
     ['sources', function () { renderSources(s); }],
     ['marketing', function () { patchMarketing(s); }],
     ['departments', function () { patchDepartments(s); }],
     ['mddept', function () { patchMdDepartments(s); }],
     ['legacydept', function () { patchLegacyDeptGrid(s); }],
     ['ai', function () { patchAiStrip(s); }],
     ['kpitiles', function () { patchKpiTiles(s); }],
     ['scroll', function () { applyAutoScroll(); }],
     ['countup', function () { animateKpis(); }]
    ].forEach(function (step) {
      try { step[1](); } catch (e) { console.warn('[ops-live] ' + step[0] + ' 失败：' + (e && e.message)); }
    });
  }

  function load(force) {
    // 优先同源 API（Node + SQLite）；静态部署时回退到构建产物 data/snapshot.json
    /* ⛔ 2026-10-19：静态兜底一律带时间戳查询串。只写 cache:'no-store' 不够——
       部分浏览器/中间层仍会回放旧 JSON（实测本地把 19/17/210 读成 3/0/15）。 */
    var stamp = '?t=' + Date.now();
    return fetch('/api/operations/v1/snapshot' + stamp, { cache: 'no-store' })
      .then(function (r) {
        if (r.ok && (r.headers.get('content-type') || '').indexOf('json') >= 0) return r.json();
        return fetch('./data/snapshot.json' + stamp, { cache: 'no-store' }).then(function (r2) { return r2.ok ? r2.json() : null; });
      })
      .catch(function () {
        return fetch('./data/snapshot.json' + stamp, { cache: 'no-store' }).then(function (r2) { return r2.ok ? r2.json() : null; });
      })
      .then(function (s) {
        if (!s) return;
        if (!force && STATE.rev !== null && s.revision === STATE.rev) return;
        render(s);
      })
      .catch(function (e) { console.warn('[ops-live] snapshot failed', e); });
  }

  /* ⚠ 2026-10-18 撤销：这里原本有一段 closeAutoOpenedPanel()，在 boot 后 1.2s / 2.6s
     各关一次 #salesWorkspace。它是早先为「别每次刷新都弹」加的兜底，但与业主 2026-09-20
     定的「点进链接开屏先弹出营销分析面板」直接冲突 —— 表现为弹窗一闪就消失、
     用户以为「营销分析不自动跳出来了」。开屏弹窗由 index.html 的引导逻辑负责，此处不再干预。 */

  function boot() {
    ensureStyles();
    ensureToggle();
    load(true);
    /* ⛔ 月面板是后挂载的：它 render 时用的还是旧数据，会把刚补好的部门卡盖回去。
       而它收到 september-revenue-updated 会整块重绘 → 所以这里也必须是「先派发、后补卡」，
       否则每次重放都会把部门卡还原成静态数（实测踩过）。 */
    [1200, 3000, 6000].forEach(function (ms) {
      setTimeout(function () {
        if (!STATE.snap) return;
        try {
          window.dispatchEvent(new CustomEvent('september-revenue-updated', { detail: { source: 'ops-live-boot' } }));
        } catch (e) { }
        try { patchMdDepartments(STATE.snap); } catch (e) { }
        try { patchLegacyDeptGrid(STATE.snap); } catch (e) { }
        try { patchKpiTiles(STATE.snap); } catch (e) { }
      }, ms);
    });
    setInterval(function () { load(false); }, 30000);
    /* 供导入链路在写库成功后立刻拉新快照（否则要等 30 秒轮询，
       用户会看到「营收表变了、顶部 KPI 还是旧数」）。 */
    window.OpsLiveSync = { refresh: function () { return load(true); }, load: load, state: STATE };
    window.addEventListener('resize', function () { if (STATE.snap) renderHeader(STATE.snap); });
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) load(false);
    });
    // 原脚本会异步重绘部门/信号，重绘后补一次滚动绑定
    var mo = new MutationObserver(function () {
      clearTimeout(mo._t);
      mo._t = setTimeout(function () { applyAutoScroll(); }, 400);
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
