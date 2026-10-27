/* ============================================================================
   渠道看板（Channel Dashboard）— 2026-10-08 新增
   ----------------------------------------------------------------------------
   数据来源两条：
     A) 线上表快照 / 手动同步 —— 《梓笙园 · 到院登记表》kdocs cp4lRRCVcqVa
        （快照见 channel-snapshot.js；浏览器内实时同步受跨域与授权限制，
         失败时**如实显示「待连接」**，绝不假装同步成功）
     B) 复制粘贴 —— 直接粘 Excel / 在线表整块数据
   两者汇入**同一份到院记录库**；重叠按指纹合并、冲突显新旧值、不静默覆盖。

   唯一真源：本模块的 S（localStorage 持久化）。所有图表 / 排行 / 推荐 / 入口简报
   都由 S 实时重算，无写死数字。

   ⚠ 三个日期口径不可混用：
     · 就诊日期     → 到院统计
     · 进展日期     → 渠道推进统计
     · 收入发生日期 → 收益统计
   ⚠ 渠道贡献 ＝ 实际收入 − 渠道直接成本，**不是净利润**，界面上一律不写「净利润」。
   ========================================================================== */
(function () {
  'use strict';

  /* ============================ 0. 常量 ============================ */
  var LS_KEY = 'hosp-channel-dashboard-v1';
  var ROUND_START = '2026-10-01';          // 「本轮工作」起点：此日后建立合作的渠道＝新渠道
  var OWNER_DEFAULT = '渠道负责人';

  var STAGES = ['待联系', '已联系', '沟通中', '待签约', '已开通', '持续运营'];
  var STAGE_TERMINAL = ['暂停', '终止'];
  var TYPES = ['学校绿色通道', '医生/机构转介', '合作单位', '线上平台', '其他'];
  var ACTIONS = ['联系', '拜访', '方案沟通', '协议推进', '通道开通', '宣教/筛查', '转介跟进', '复盘'];
  var NEXT_ACTIONS = ['二次拜访', '安排宣教/筛查', '推进协议签署', '对接人换签', '补充材料', '等待对方回复', '暂无（维持现状）'];
  var BIZ_NEXT = ['继续推进', '增加投入', '维持', '优化', '暂停观察'];

  var HDR = ['序号', '就诊日期', '姓名', '年龄', '联系方式', '初/复诊', '来源渠道', '随访人', '备注'];
  var VTYPES = ['初诊', '复诊'];

  /* 渠道类型猜测（仅对**语义明确**的中文值给默认；字母简称一律「待归类」，不臆测） */
  function guessType(raw) {
    var s = String(raw || '');
    if (!s) return '';
    if (/绿色通道/.test(s)) return '学校绿色通道';
    /* ⭐ 2026-10-10：补学校后缀识别 —— 校名常写作「双福五小 / 双福三小」，
       原先只认「小学」，这类一律落到「待归类」，业主得手动改一百次。 */
    if (/(小学|中学|初中|高中|职高|幼儿园|附小|附中|一小|二小|三小|四小|五小|六小|七小|八小|九小|十小)/.test(s)) return '学校绿色通道';
    if (/^网络|线上|抖音|小红书|微信|百度|美团/.test(s)) return '线上平台';
    if (/^内部推荐/.test(s)) return '医生/机构转介';
    if (/(院|医院|精卫|卫生|中心|诊所|机构)/.test(s)) return '合作单位';
    return '';                              // 字母简称（K / HM / AM / CJ / HJL / LC …）→ 待归类
  }

  /* ============================ 1. 工具 ============================ */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function n(v) { var x = Number(v); return isFinite(x) ? x : 0; }
  function isBlank(v) { return v === null || v === undefined || String(v).trim() === ''; }
  function wan(v, d) { return (n(v) / 10000).toFixed(d == null ? 2 : d); }
  function yuan(v) { return n(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 }); }
  function pad2(v) { return (v < 10 ? '0' : '') + v; }
  function ymdOf(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
  function addDays(s, k) { var d = new Date(s + 'T12:00:00'); d.setDate(d.getDate() + k); return ymdOf(d); }
  function weekStartOf(s) { var d = new Date(s + 'T12:00:00'); var w = d.getDay(); return addDays(s, w === 0 ? -6 : 1 - w); }
  function daysBetween(a, b) {
    return Math.round((new Date(b + 'T12:00:00') - new Date(a + 'T12:00:00')) / 86400000) + 1;
  }
  function shortMd(s) { return s ? (+s.slice(5, 7)) + '.' + (+s.slice(8)) : ''; }
  /* 日期合法性校验：只查格式不查范围会放进「2026.13.45」这种值
     （实测：月份 13、日 45 都会被正则匹配，字符串比较又不报错 → 静默入库）。
     本项目脏日期体检必须连**月份非法 / 日非法 / 年份越界**一起查。 */
  function validYmd(y, m, d) {
    if (!(y >= 2000 && y <= 2100)) return false;
    if (!(m >= 1 && m <= 12)) return false;
    if (!(d >= 1)) return false;
    var dim = new Date(y, m, 0).getDate();          // 该月真实天数（含闰年）
    return d <= dim;
  }
  /* 日期归一化：2026.10.1 / 2026-10-01 / 2026/10/1 / 10.1 → '2026-10-01'；非法一律 null */
  function normDate(v, baseYear) {
    var s = String(v == null ? '' : v).trim();
    if (!s) return null;
    var m = s.match(/^(\d{4})[-./](\d{1,2})[-./](\d{1,2})$/);
    if (m) {
      var y = +m[1], mo = +m[2], dd = +m[3];
      return validYmd(y, mo, dd) ? (y + '-' + pad2(mo) + '-' + pad2(dd)) : null;
    }
    m = s.match(/^(\d{1,2})[-./月](\d{1,2})日?$/);
    if (m) {
      var by = +(baseYear || '2026'), bm = +m[1], bd = +m[2];
      return validYmd(by, bm, bd) ? (by + '-' + pad2(bm) + '-' + pad2(bd)) : null;
    }
    var d = new Date(s);
    if (isNaN(d.getTime())) return null;
    var yy = d.getFullYear(), mm = d.getMonth() + 1, ddd = d.getDate();
    return validYmd(yy, mm, ddd) ? ymdOf(d) : null;
  }
  function maskName(s) {
    s = String(s || ''); if (!s) return '';
    if (!state.revealIdentity) return s.slice(0, 1) + (s.length > 1 ? 'X'.repeat(Math.min(s.length - 1, 2)) : '');
    return s;
  }
  function maskPhone(s) {
    s = String(s || ''); if (!s) return '';
    if (!state.revealIdentity) return s.length >= 7 ? s.slice(0, 3) + '****' + s.slice(-4) : '****';
    return s;
  }
  function hash(str) {
    var h = 0x811c9dc5;
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return h.toString(36);
  }
  function todayYmd() { return ymdOf(new Date()); }

  /* ============================ 2. 状态 ============================ */
  var state = { revealIdentity: false, range: 'month', customFrom: '', customTo: '' };
  var S = null;

  function blankState() {
    return {
      v: 1,
      channels: [],        // 渠道档案
      visits: [],          // 到院记录（唯一到院库）
      progress: [],        // 推进记录（按日期的时间线，只增不改）
      money: [],           // 收入 / 成本 记录
      weekly: [],          // 渠道周报（**文字识别**得到的汇总口径，含原文，不并入到院记录库）
      log: [],             // 变更日志
      sync: { status: 'unconfigured', url: '', lastAt: '', lastAdded: 0, lastUpdated: 0, lastErr: '' },
      seeded: false
    };
  }
  function load() {
    var raw = null;
    try { raw = JSON.parse(localStorage.getItem(LS_KEY) || 'null'); } catch (e) { raw = null; }
    S = (raw && raw.v === 1) ? raw : blankState();
    ['channels', 'visits', 'progress', 'money', 'weekly', 'log'].forEach(function (k) { if (!Array.isArray(S[k])) S[k] = []; });
    if (!S.sync) S.sync = { status: 'unconfigured', url: '', lastAt: '', lastAdded: 0, lastUpdated: 0, lastErr: '' };
    if (S.sync.status !== 'unconfigured') S.sync.status = 'unconfigured';   // ⚠ 刷新后不保留「已连接」假象
  }
  function save() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(S)); }
    catch (e) { console.warn('渠道看板：本地保存失败', e); }
  }
  function logAct(what, detail) {
    S.log.unshift({ at: new Date().toISOString(), what: what, detail: detail || '', who: OWNER_DEFAULT });
    if (S.log.length > 400) S.log.length = 400;
  }

  /* ============================ 3. 渠道档案 ============================ */
  function channelById(id) {
    for (var i = 0; i < S.channels.length; i++) if (S.channels[i].id === id) return S.channels[i];
    return null;
  }
  /* 按 名称 / 别名 / 原始来源名 找渠道（别名归并的唯一入口） */
  function findChannel(raw) {
    var s = String(raw || '').trim();
    if (!s) return null;
    for (var i = 0; i < S.channels.length; i++) {
      var c = S.channels[i];
      if (c.name === s) return c;
      if (c.aliases && c.aliases.indexOf(s) >= 0) return c;
      if (c.rawNames && c.rawNames.indexOf(s) >= 0) return c;
    }
    return null;
  }
  /* 首次见到未识别的来源渠道 → 建一条「待归类」档案（不臆测名称与类型） */
  function ensureChannel(raw) {
    var s = String(raw || '').trim();
    if (!s) return null;
    var hit = findChannel(s);
    if (hit) {
      if (hit.rawNames.indexOf(s) < 0) hit.rawNames.push(s);
      if (!hit.aliases.length && hit.name !== s) hit.aliases.push(s);
      return hit;
    }
    var c = {
      id: 'c' + hash(s + '|' + S.channels.length),
      name: s,
      type: guessType(s),
      owner: OWNER_DEFAULT,
      isNew: null,                 // null = 待确认（新渠道 / 既往渠道）
      newBasis: '',                // 分类依据（记录说明，跨月保留）
      createdAt: '',
      startAt: '',
      stage: '',
      stageAt: '',
      lastPushAt: '',
      nextAction: '',
      nextActionDue: '',
      aliases: [],
      rawNames: [s],
      note: guessType(s) ? '' : '来源渠道为简称，名称与类型待负责人归类'
    };
    S.channels.push(c);
    return c;
  }
  /* ⚠ 阶段**不臆测**：从未显式设置过的学校显示「待录入」，而不是默认成「待联系」——
     源表只给了渠道名，无从判断该校实际推进到哪一步，默认值会误导负责人。 */
  function stageOf(c) { return c.stage || ''; }
  function stageLabel(c) { return c.stage || (isSchool(c) ? '待录入' : ''); }
  function isSchool(c) { return c.type === '学校绿色通道'; }
  function isPendingType(c) { return !c.type; }
  function isOverdue(c) {
    if (!c.nextActionDue) return false;
    var cut = cutoff();
    return c.nextActionDue < cut && STAGES.indexOf(stageOf(c)) < STAGES.indexOf('已开通');   // stageOf 为空时 indexOf=-1 → 视为未开通，参与超期判断
  }

  /* ============================ 4. 到院记录 + 指纹去重 ============================ */
  /* 稳定记录 ID：不用「序号」（仅原表字段）。有原始登记 ID 用它；
     否则用 就诊日期 + 姓名 + 来源渠道 + 初复诊 构造指纹。
     ⚠ 同一指纹出现两次**不自动删**（可能是真实同日多次到院）→ 标「疑似重复」交负责人确认。 */
  function fpOf(r) { return [r.date, r.name, r.channelId || r.rawChannel, r.vtype].join('|'); }
  function vidOf(r, seq) {
    if (r.originId) return 'v' + hash('oid|' + r.originId);
    return 'v' + hash(fpOf(r));
  }
  function visitIndex(map) {
    map = map || {};
    S.visits.forEach(function (v) { map[v.id] = v; });
    return map;
  }
  /* 把一批「原始行」并入到院库。
     返回 {added, updated, dup, bad[]}；重叠不重复累计、冲突不静默覆盖。 */
  function mergeVisits(raws, srcTag) {
    var byId = visitIndex();
    /* res.ids = 本批**实际处理到的记录 id**（含新增与重叠）。
       ⭐ 供「源表对账」用：快照重抓后，仅来自线上表、且不在 res.ids 里的旧记录
         即「源表已删除」→ 移出到院库（见 seedFromSnapshot）。 */
    var res = { added: 0, updated: 0, dup: 0, bad: [], conflicts: [], ids: [] };
    var batchFp = {};
    raws.forEach(function (raw) {
      var issues = [];
      if (!raw.date) issues.push('就诊日期无法识别');
      if (isBlank(raw.name)) issues.push('缺姓名');
      if (isBlank(raw.rawChannel)) issues.push('缺来源渠道');
      if (raw.vtype && VTYPES.indexOf(raw.vtype) < 0) issues.push('初/复诊取值异常「' + raw.vtype + '」');
      if (issues.length) { res.bad.push({ row: raw, issues: issues }); return; }

      var ch = ensureChannel(raw.rawChannel);
      var rec = {
        date: raw.date, name: raw.name, age: raw.age, phone: raw.phone,
        vtype: raw.vtype, rawChannel: raw.rawChannel, channelId: ch ? ch.id : '',
        follower: raw.follower, note: raw.note, originId: raw.originId || '',
        seq: raw.seq || ''
      };
      rec.id = vidOf(rec);
      var fp = fpOf(rec);
      /* ⚠⚠ 同一批内同一指纹出现多次 → 可能是**真实同日多次到院**（如复诊），
         一律**不合并、不删除**：另建一条记录并标「疑似重复」，交负责人确认。
         （实测线上表 310 条里有 1 组：袁尚礼 / 2026.10.1 / K ×2） */
      var seen = (batchFp[fp] = (batchFp[fp] || 0) + 1);
      if (seen > 1) rec.id = rec.id + '_' + seen;
      res.ids.push(rec.id);                         /* 记录本批处理到的 id */

      var old = byId[rec.id];
      if (old) {
        /* 同指纹已存在：可能是①同一数据重导（不累计）②另一个来源的重叠（合并）③字段冲突（显新旧值） */
        var srcs = old.src || [];
        if (srcs.indexOf(srcTag) < 0) srcs.push(srcTag);
        old.src = srcs;
        var changed = [];
        ['age', 'phone', 'vtype', 'rawChannel', 'follower', 'note'].forEach(function (k) {
          var a = String(old[k] == null ? '' : old[k]), b = String(rec[k] == null ? '' : rec[k]);
          if (b && a !== b) {
            res.conflicts.push({ id: rec.id, field: k, oldVal: old[k], newVal: rec[k], oldSrc: (old.srcFrom || []).join('/') || '已有记录', newSrc: srcTag });
            changed.push(k);
          }
        });
        /* 只补空字段，不覆盖已有非空值（保留旧的，冲突另列） */
        ['age', 'phone', 'follower', 'note'].forEach(function (k) { if (isBlank(old[k]) && !isBlank(rec[k])) old[k] = rec[k]; });
        old.updatedAt = new Date().toISOString();
        old.updatedBy = srcTag;
        res.dup++;
        return;
      }
      rec.src = [srcTag];
      rec.srcFrom = [srcTag];
      rec.createdAt = rec.updatedAt = new Date().toISOString();
      rec.updatedBy = srcTag;
      S.visits.push(rec);
      byId[rec.id] = rec;
      res.added++;
    });
    /* 同批内重复 → 标「疑似重复」（保留全部，交负责人确认；不重复计数） */
    S.visits.forEach(function (v) { if (batchFp[fpOf(v)] > 1) v.suspectDup = true; });
    res.suspected = S.visits.filter(function (v) { return v.suspectDup; }).length;
    if (res.added || res.updated) logAct('并入到院记录', srcTag + '：新增 ' + res.added + '、重叠 ' + res.dup);
    return res;
  }

  /* 用快照做首次播种（真实数据，非演示）
     ⭐ 用 seedKey（＝快照抓取时点）判重：快照更新后**重新并入**，而不是永远跳过。
     mergeVisits 本身幂等（同指纹→合并），所以重复并入不会重复累计。
     ⚠⚠ **源表对账（本轮新增，2026-10-12）**：到院记录的 id 是「就诊日期+姓名+渠道+初复诊」
        的指纹。源表若**删行**或**改来源渠道**，旧指纹条目仍留在 localStorage 里 →
        mergeVisits 查不到、不会更新它 → 出现「幽灵记录」被重复计入（实测 10-12 源表
        删 43、改 11 行渠道 ⇒ 不做对账会从 489 虚增到 501）。
     ✅ 处置：**快照是权威源**。重抓后，把「仅来自线上表（srcFrom 只含 online）、
        且不在本批处理 id 里」的记录移出到院库并记日志。
        ⛔ 只动「仅来自线上表」的 —— 手工粘贴/其它来源的记录不因快照变动被误删。 */
  function seedFromSnapshot() {
    var snap = window.CHANNEL_SNAPSHOT;
    if (!snap || !snap.rows || !snap.rows.length) return;
    var key = String(snap.fetchedAt || '') + '|' + snap.rows.length;
    if (S.seedKey === key) return;
    var raws = snap.rows.map(function (r) {
      return {
        seq: r[0], date: normDate(r[1]), name: r[2], age: r[3], phone: r[4],
        vtype: r[5], rawChannel: r[6], follower: r[7], note: r[8]
      };
    });
    var res = mergeVisits(raws, 'online');
    /* ---- 源表对账：清掉快照里已不存在的「纯线上」记录（删行 / 改渠道留下的旧指纹） ---- */
    var live = {};
    res.ids.forEach(function (id) { live[id] = 1; });
    var dropped = [];
    S.visits = S.visits.filter(function (v) {
      var onlyOnline = Array.isArray(v.srcFrom) && v.srcFrom.length === 1 && v.srcFrom[0] === 'online';
      if (onlyOnline && !live[v.id]) { dropped.push(v); return false; }
      return true;
    });
    if (dropped.length) {
      logAct('源表对账：移除已删除记录',
        dropped.length + ' 条（' + dropped.slice(0, 5).map(function (v) { return shortMd(v.date) + '/' + v.name; }).join('、')
        + (dropped.length > 5 ? ' 等' : '') + '）——快照中已不存在');
    }
    /* 同批内重复标记要按**现存**记录重算（删行后旧标记会残留） */
    var fpCount = {};
    S.visits.forEach(function (v) { var f = fpOf(v); fpCount[f] = (fpCount[f] || 0) + 1; });
    S.visits.forEach(function (v) { v.suspectDup = fpCount[fpOf(v)] > 1; });
    S.seeded = true; S.seedKey = key;
    logAct('并入线上表快照', snap.fetchedAt + ' · 新增 ' + res.added + '、重叠 ' + res.dup
      + '、异常 ' + res.bad.length + (dropped.length ? '、源表已删 ' + dropped.length : ''));
    save();
  }

  /* ============================ 5. 区间 ============================ */
  function cutoff() {
    /* 数据截至 = 到院记录里的最大就诊日期（按数据、不按今天） */
    var mx = '';
    S.visits.forEach(function (v) { if (v.date > mx) mx = v.date; });
    return mx || todayYmd();
  }
  function currentRange() {
    var cut = cutoff();
    var from, to = cut, label;
    if (state.range === 'today') {
      from = cut; label = '今日（' + shortMd(cut) + '）';
    } else if (state.range === 'week') {
      from = weekStartOf(cut); label = '本周（' + shortMd(from) + '—' + shortMd(to) + '）';
    } else if (state.range === 'custom') {
      from = normDate(state.customFrom) || cut;
      to = normDate(state.customTo) || cut;
      if (from > to) { var t = from; from = to; to = t; }
      if (to > cut) to = cut;
      label = '自定义（' + shortMd(from) + '—' + shortMd(to) + '）';
    } else {
      from = cut.slice(0, 7) + '-01'; label = '本月（' + shortMd(from) + '—' + shortMd(to) + '）';
    }
    return { from: from, to: to, label: label, days: daysBetween(from, to) };
  }
  function prevRange(rg) {
    var to = addDays(rg.from, -1);
    var from = addDays(to, -(rg.days - 1));
    return { from: from, to: to, days: rg.days, label: shortMd(from) + '—' + shortMd(to) };
  }
  function inRange(d, rg) { return d && d >= rg.from && d <= rg.to; }

  /* ============================ 6. 收益口径 ============================ */
  /* 逐笔（day）与期间（period）不得在同一范围重复计入 → 检测冲突并排除期间汇总 */
  function moneyFor(channelId, rg) {
    var list = S.money.filter(function (m) {
      if (m.channelId !== channelId) return false;
      var f = m.scope === 'period' ? m.periodFrom : m.date;
      var t = m.scope === 'period' ? m.periodTo : m.date;
      return !(t < rg.from || f > rg.to);
    });
    var days = list.filter(function (m) { return m.scope !== 'period'; });
    var periods = list.filter(function (m) { return m.scope === 'period'; });
    /* 期间记录若与逐笔记录日期重叠 → 冲突，排除该期间记录 */
    var excluded = [];
    periods.forEach(function (p) {
      var overlap = days.some(function (d) { return d.date >= p.periodFrom && d.date <= p.periodTo; });
      if (overlap) excluded.push(p.id);
    });
    var use = list.filter(function (m) { return excluded.indexOf(m.id) < 0; });
    var revenue = 0, cost = 0, hours = 0, revFilled = false, costFilled = false, hoursFilled = false;
    use.forEach(function (m) {
      if (m.revenue !== null && m.revenue !== undefined && m.revenue !== '') { revenue += n(m.revenue); revFilled = true; }
      if (m.cost !== null && m.cost !== undefined && m.cost !== '') { cost += n(m.cost); costFilled = true; }
      if (m.hours !== null && m.hours !== undefined && m.hours !== '') { hours += n(m.hours); hoursFilled = true; }
    });
    return {
      records: use, excluded: excluded,
      revenue: revFilled ? revenue : null,
      cost: costFilled ? cost : null,
      hours: hoursFilled ? hours : null
    };
  }

  /* ============================ 7. 统计引擎 ============================ */
  function computeStats(rg) {
    rg = rg || currentRange();
    var vs = S.visits.filter(function (v) { return inRange(v.date, rg); });
    /* 到院人次 = 有效到院记录数（跨来源已去重） */
    var visits = vs.length;
    var pmap = {}, pmapFirst = {};
    vs.forEach(function (v) {
      var key = v.name + '|' + (v.phone || '');
      pmap[key] = 1;
      if (v.vtype === '初诊') pmapFirst[key] = 1;
    });
    var patients = Object.keys(pmap).length;
    var first = vs.filter(function (v) { return v.vtype === '初诊'; }).length;
    var repeat = vs.filter(function (v) { return v.vtype === '复诊'; }).length;
    var firstPatients = Object.keys(pmapFirst).length;
    var suspect = vs.filter(function (v) { return v.suspectDup; }).length;
    var refund = vs.filter(function (v) { return /退号/.test(v.note || ''); }).length;

    /* 渠道级
       ⚠ 聚合口径：渠道贡献只对「收入与成本都已填」的渠道求和，
         否则一个只填了成本的渠道会把总贡献拉低（收入按缺失处理，成本却计入）。
         另单独给出 revFilled / costFilled / fullFilled 计数，界面上说清覆盖范围。 */
    var rows = [], totRev = 0, totCost = 0, revFilled = 0, costFilled = 0, fullFilled = 0, totContribution = 0, revTotal = 0;
    S.channels.forEach(function (c) {
      var cv = vs.filter(function (v) { return v.channelId === c.id; });
      if (!cv.length && !S.money.some(function (m) { return m.channelId === c.id; })) return;
      var mf = moneyFor(c.id, rg);
      var pr = prevRange(rg);
      var prevVisits = S.visits.filter(function (v) { return v.channelId === c.id && inRange(v.date, pr); }).length;
      var contribution = (mf.revenue === null || mf.cost === null) ? null : (mf.revenue - mf.cost);
      var roi = (mf.revenue === null || !mf.cost) ? null : (mf.revenue / mf.cost);
      var perHour = (contribution === null || !mf.hours) ? null : (contribution / mf.hours);
      var hasRev = mf.revenue !== null, hasCost = mf.cost !== null;
      revTotal++;
      if (hasRev) { revFilled++; totRev += mf.revenue; }
      if (hasCost) { costFilled++; totCost += mf.cost; }
      if (hasRev && hasCost) { fullFilled++; totContribution += (mf.revenue - mf.cost); }
      rows.push({
        ch: c, visits: cv.length, first: cv.filter(function (v) { return v.vtype === '初诊'; }).length,
        repeat: cv.filter(function (v) { return v.vtype === '复诊'; }).length,
        prevVisits: prevVisits,
        revenue: mf.revenue, cost: mf.cost, hours: mf.hours,
        contribution: contribution, roi: roi, perHour: perHour,
        hasRevenue: hasRev, conflict: mf.excluded.length > 0,
        pushed: S.progress.some(function (p) { return p.channelId === c.id && inRange(p.date, rg); })
      });
    });
    var pushedCh = rows.filter(function (r) { return r.pushed; }).length;
    /* ⚠ 「本期有推进记录的渠道数」要按**推进记录**统计，不能只在 st.channels 里数 ——
       新建学校 / 新渠道在还没有到院前不会进入 st.channels（那里按「有到院或有收益」筛），
       于是「已推进但还没人」的渠道会被漏掉，指标偏低。 */
    var pushedSet = {};
    S.progress.forEach(function (p) { if (inRange(p.date, rg)) pushedSet[p.channelId] = 1; });
    pushedCh = Object.keys(pushedSet).length;
    var schools = S.channels.filter(function (c) { return isSchool(c); });
    var schoolsOpened = schools.filter(function (c) { return ['已开通', '持续运营'].indexOf(c.stage) >= 0; }).length;
    var schoolsNewOpened = schools.filter(function (c) {
      return ['已开通', '持续运营'].indexOf(c.stage) >= 0 && c.stageAt && inRange(c.stageAt, rg);
    }).length;

    return {
      rg: rg, visits: visits, patients: patients, first: first, repeat: repeat,
      firstPatients: firstPatients, suspect: suspect, refund: refund,
      channels: rows, pushedChannels: pushedCh,
      schools: schools.length, schoolsOpened: schoolsOpened, schoolsNewOpened: schoolsNewOpened,
      revenue: totRev, cost: totCost, contribution: totContribution,
      revenueFilled: revFilled, costFilled: costFilled, contributionFilled: fullFilled,
      revenueTotal: revTotal,
      missingRevenue: rows.filter(function (r) { return !r.hasRevenue; }).length,
      untriaged: S.channels.filter(function (c) { return isPendingType(c); }).length
    };
  }

  /* ============================ 8. 推荐规则（透明规则，不编造） ============================ */
  /* ⚠ 同类合并：22 个渠道都「缺收入」时，不能输出 22 条一模一样的建议（实测噪音极大）。
     做法：把「收益待补齐」聚合成 1 条，列出到院量最大的几个渠道；
     其余个性化建议（超期 / 有转介未到院 / 到院多但贡献低）才单独成条，每类最多 3 条。 */
  function buildAdvice(rg, st) {
    var invest = [], optimize = [], follow = [];
    var cut = cutoff();
    var pendingRev = [];
    var sorted = st.channels.slice().sort(function (a, b) {
      return (b.contribution == null ? -1 : b.contribution) - (a.contribution == null ? -1 : a.contribution);
    });
    var maxContribution = sorted.length && sorted[0].contribution > 0 ? sorted[0].contribution : 0;
    var maxVisits = st.channels.reduce(function (a, r) { return Math.max(a, r.visits); }, 0);

    st.channels.forEach(function (r) {
      var c = r.ch;
      var rgTxt = st.rg.label;

      /* 已有转介/咨询但未到院 → 核查预约衔接 */
      var progInquiry = S.progress.filter(function (p) { return p.channelId === c.id && inRange(p.date, st.rg); })
        .reduce(function (a, p) { return a + n(p.newInquiry); }, 0);
      if (progInquiry > 0 && r.visits === 0) {
        follow.push({
          ch: c, kind: 'follow', title: '有转介但未到院，建议核查预约衔接',
          why: rgTxt + ' 记录转介/咨询 ' + progInquiry + ' 人，但到院 0 人次。',
          gap: '需确认是预约未成、到诊流失还是登记遗漏。'
        });
        return;
      }
      /* 长期无进展或跟进超期 → 负责人待办 */
      if (isOverdue(c)) {
        follow.push({
          ch: c, kind: 'follow', title: '跟进已超期，需负责人处理',
          why: '下一步「' + (c.nextAction || '—') + '」截止 ' + shortMd(c.nextActionDue) + '，数据截至 ' + shortMd(cut) + ' 仍未更新。',
          gap: '缺 ' + shortMd(c.nextActionDue) + ' 之后的推进记录。'
        });
        return;
      }
      /* 收益未补齐 → 先收集，稍后聚合成一条 */
      if (!r.hasRevenue) { pendingRev.push(r); return; }
      /* 仅缺成本 → 投入效率不可算 */
      if (r.cost === null) {
        optimize.push({
          ch: c, kind: 'optimize', title: '仅缺成本，投入效率暂不可算',
          why: '收入 ' + yuan(r.revenue) + ' 元已记录，但成本未填，无法算投入产出比。',
          gap: '缺渠道直接成本。'
        });
        return;
      }
      /* 到院多但贡献低 → 核查成本、服务组合及收入数据 */
      if (r.visits >= 5 && maxContribution > 0 && r.contribution != null && r.contribution <= maxContribution * 0.2) {
        optimize.push({
          ch: c, kind: 'optimize', title: '到院多但贡献低，建议核查成本与收入归属',
          why: '到院 ' + r.visits + ' 人次，贡献 ' + yuan(r.contribution) + ' 元（组内最高 ' + yuan(maxContribution) + ' 元）。',
          gap: '需核查直接成本口径、服务组合与收入是否漏记。'
        });
        return;
      }
      /* 样本少、观察时间短 → 观察中 */
      if (r.visits > 0 && r.visits < 3) {
        optimize.push({
          ch: c, kind: 'optimize', title: '样本少，标记观察中',
          why: rgTxt + ' 到院 ' + r.visits + ' 人次（< 3），不足以判断效率。',
          gap: '观察时间短，建议累计 2 个周期后再评估。', observe: true
        });
        return;
      }
      /* 值得培育：新渠道 + 有初诊 */
      if (c.isNew === true && r.first > 0) {
        invest.push({
          ch: c, kind: 'invest', title: '新渠道已产生初诊，值得继续培育',
          why: rgTxt + ' 初诊到院 ' + r.first + ' 人次' + (r.contribution != null ? '、贡献 ' + yuan(r.contribution) + ' 元' : '') + '。',
          gap: c.nextActionDue ? ('下一步「' + (c.nextAction || '—') + '」截止 ' + shortMd(c.nextActionDue) + '。') : '缺下一步行动与截止日期。'
        });
        return;
      }
      /* 当前收益较高 + 连续两期有产出 → 优先安排下一次合作 */
      if (r.contribution != null && maxContribution > 0 && r.contribution >= maxContribution * 0.6 && r.first > 0 && r.prevVisits > 0) {
        invest.push({
          ch: c, kind: 'invest', title: '本期贡献较高且连续两个周期有产出，建议优先安排下一次合作',
          why: rgTxt + ' 贡献 ' + yuan(r.contribution) + ' 元（组内最高 ' + yuan(maxContribution) + ' 元），上一期到院 ' + r.prevVisits + ' 人次。',
          gap: c.nextActionDue ? '' : '缺下一步行动与截止日期。'
        });
      }
    });

    /* 聚合「收益待补齐」：一条说明覆盖多少渠道、主要缺口在谁 */
    if (pendingRev.length) {
      pendingRev.sort(function (a, b) { return b.visits - a.visits; });
      var top = pendingRev.slice(0, 5);
      optimize.unshift({
        ch: top[0].ch, kind: 'optimize', aggregate: true,
        title: '收益未补齐 ' + pendingRev.length + ' 个渠道，暂不参与收益排序',
        why: '本期共 ' + st.visits + ' 人次到院，覆盖 ' + st.channels.length + ' 个渠道，'
          + '但没有任何渠道填写「实际收入 / 直接成本」，无法计算渠道贡献与投入产出比。'
          + '到院量最大：' + top.slice(0, 3).map(function (r) { return r.ch.name + ' ' + r.visits + ' 人次'; }).join('、')
          + (pendingRev.length > 3 ? ' 等' : '') + '。',
        gap: '缺实际收入与直接成本。补齐后即可进入排行；按规则<b>不当作 0 元</b>参与排序。',
        list: top
      });
    }

    invest.sort(function (a, b) { return n(b.ch.contribution) - n(a.ch.contribution); });
    optimize.sort(function (a, b) {
      if (a.aggregate) return -1;
      if (b.aggregate) return 1;
      return n(b.ch.visits || 0) - n(a.ch.visits || 0);
    });
    return { invest: invest.slice(0, 3), optimize: optimize.slice(0, 4), follow: follow.slice(0, 3) };
  }

  /* ============================ 9. 渲染 ============================ */
  function root() { return $('#channelDrawer'); }

  /* ============================ 9. 顶部工具栏 ============================
     示意图：渠道看板 · 时间范围 · 更新数据 · 关闭（紧凑一行）。 */
  function renderTop(st) {
    var rg = st.rg;
    var syncTxt = {
      unconfigured: '<span class="ch-dot warn"></span>在线表：待连接',
      ok: '<span class="ch-dot"></span>在线表：已同步',
      fail: '<span class="ch-dot bad"></span>在线表：同步失败'
    }[S.sync.status] || '<span class="ch-dot warn"></span>在线表：待连接';
    var snap = window.CHANNEL_SNAPSHOT;
    var snapTxt = (snap && !snap.isDemo && snap.rows && snap.rows.length)
      ? ('快照 ' + snap.fetchedAt + '（' + snap.rows.length + ' 条）') : '';

    $('#chTop').innerHTML = ''
      + '<div class="ch-tbar">'
      + '<div class="ch-tbar-l"><span class="ch-logo">◉</span><h1>渠道看板</h1></div>'
      + '<div class="ch-tbar-r">'
      + '<div class="ch-ranges" id="chRanges">'
      + [['today', '今日'], ['week', '本周'], ['month', '本月'], ['custom', '自定义']].map(function (x) {
        return '<button type="button" data-ch-range="' + x[0] + '"' + (state.range === x[0] ? ' class="active"' : '') + '>' + x[1] + '</button>';
      }).join('')
      + '</div>'
      + '<div class="ch-range-custom"' + (state.range === 'custom' ? '' : ' hidden') + ' id="chCustom">'
      + '<input type="date" id="chFrom" value="' + esc(state.customFrom || rg.from) + '">'
      + '<input type="date" id="chTo" value="' + esc(state.customTo || rg.to) + '">'
      + '<button type="button" class="ch-btn ghost" id="chApplyCustom">应用</button></div>'
      + '<button type="button" class="ch-btn primary" id="chOpenUpdate"><i>⤓</i>更新数据</button>'
      + '<button type="button" class="ch-close" id="chClose" aria-label="关闭">×</button>'
      + '</div></div>'
      + '<div class="ch-statusline">'
      + '<span>统计区间 <b>' + esc(rg.label) + '</b>（' + rg.from + ' — ' + rg.to + '）</span>'
      + '<span>数据截至 <b>' + shortMd(cutoff()) + '</b></span>'
      + '<span>' + syncTxt + '</span>'
      + (snapTxt ? '<span>' + esc(snapTxt) + '</span>' : '')
      + '</div>'
      + '<div class="ch-subline">'
      + '<span>推进到哪一步 · 带来多少患者 · 产生多少收益 · 下一步优先投入谁</span>'
      + '<span class="ch-legend-inline">'
      + '<i class="lg done"></i>已完成'
      + '<i class="lg on"></i>当前阶段'
      + '<i class="lg idle"></i>未开始'
      + '<i class="lg todo"></i>待处理</span>'
      + '</div>';
  }

  /* ============================ 10. 渠道成效 ============================
     示意图：左＝前 5 渠道横向条形图（可切换口径），右＝到院主数字 + 摘要。
     收益缺失时只出一条紧凑提示 + 「补录收益」入口。 */
  var effKey = 'visits';
  var EFFS = [['visits', '到院'], ['first', '初诊'], ['revenue', '收入'], ['contribution', '渠道贡献']];
  function fmtEff(k, v) {
    if (v == null) return '待补';
    if (k === 'revenue' || k === 'contribution') return wan(v) + ' 万';
    return String(v);
  }
  function renderEffect(st) {
    var rg = st.rg;
    /* 排序口径：收入 / 贡献只对有收益的渠道排序（缺值不当 0） */
    var revBased = (effKey === 'revenue' || effKey === 'contribution');
    var pool = st.channels.filter(function (r) { return revBased ? r.hasRevenue : true; });
    var list = pool.slice().sort(function (a, b) {
      return n(b[effKey]) - n(a[effKey]);
    }).slice(0, 5);
    var mx = list.length ? Math.max.apply(null, list.map(function (r) { return n(r[effKey]); })) : 0;

    var bars = list.length ? list.map(function (r, k) {
      var w = mx > 0 ? Math.max(6, Math.round(n(r[effKey]) / mx * 100)) : 6;
      var op = 1 - k * 0.13;
      return '<button type="button" class="ch-bar-row" data-ch-open="' + esc(r.ch.id) + '">'
        + '<span class="ch-bar-name">' + esc(r.ch.name) + '</span>'
        + '<span class="ch-bar-track"><i style="width:' + w + '%;opacity:' + op.toFixed(2) + '"></i></span>'
        + '<b class="ch-bar-val">' + fmtEff(effKey, r[effKey]) + '</b>'
        + '</button>';
    }).join('') : '<div class="ch-empty">本期该口径还没有可比较的数据。</div>';

    var pending = st.missingRevenue;
    return ''
      + '<div class="ch-eff">'
      + '<div class="ch-eff-left">'
      + '<div class="ch-eff-head"><h3>渠道成效</h3>'
      + '<div class="ch-eff-tabs" id="chEffTabs">'
      + EFFS.map(function (x) {
        return '<button type="button" data-ch-eff="' + x[0] + '"' + (effKey === x[0] ? ' class="active"' : '') + '>' + x[1] + '</button>';
      }).join('')
      + '</div></div>'
      + '<div class="ch-bars">' + bars + '</div>'
      + (revBased && !pool.length
        ? '<div class="ch-hint" style="margin-top:8px">尚无渠道填写收益，收入与渠道贡献暂不可比。</div>' : '')
      + '</div>'
      + '<div class="ch-eff-right">'
      + '<div class="ch-sum-main"><div><b>' + st.visits + '</b><span>到院人次</span></div>'
      + '<i class="ch-sum-ic" aria-hidden="true">◔</i></div>'
      + '<div class="ch-sum-sub">'
      + '<div><b>' + st.first + '</b><span>初诊人次</span><i>◔</i></div>'
      + '<div><b>' + st.repeat + '</b><span>复诊人次</span><i>↻</i></div>'
      + '<div><b>' + st.schoolsOpened + '</b><span>已开通学校</span><i>▤</i></div>'
      + '</div>'
      + '<div class="ch-eff-foot">去重患者 <b>' + st.patients + '</b> 人'
      + (st.firstPatients ? '（初诊去重 ' + st.firstPatients + ' 人）' : '')
      + ' · 新开通学校 <b>' + st.schoolsNewOpened + '</b> 所（区间新增）</div>'
      + (pending
        ? '<div class="ch-pend-hint"><i>◈</i><span>收益待补：' + pending + ' 个渠道尚未录入收益数据</span>'
          + '<button type="button" class="ch-btn primary sm" data-ch-fill="1">补录收益</button></div>'
        : '')
      + '</div></div>';
  }

  /* ============================ 10b. 双自然周排名 ============================
     业主 2026-10-12：「时间戳分为 9.28—10.04 和 10.05—10.11 两个自然周进行排名」。
     ⭐ 窗口**按数据末日推导**（本周＝含数据末日的自然周，周一起算），不硬编码 ——
        数据滚到下一周时自动跟上；当前数据末日 10.11 ⇒ 本周 10.05—10.11 / 上周 9.28—10.04，
        正好是业主指定的两周。
     ⚠⚠ **覆盖天数必须单列**：源表《10月到院登记表》只从 10.1 起，
        上周窗口 9.28—10.04 实际只有 10.1—10.4（4 天）有记录，9.28—9.30 无记录。
        ⇒ 天数不同的两周**只比日均**，不比总量（本仓铁律：「天数不同只比日均」）。
     ⚠ 两周窗口是**固定自然周**，与顶部「区间选择器」相互独立（后者只影响成效/全部渠道等区块）。 */
  var wkRankKey = 'visits';
  var WKR_KEYS = [['visits', '到院'], ['first', '初诊'], ['repeat', '复诊']];
  function naturalWeeks() {
    var cut = cutoff();
    var curFrom = weekStartOf(cut);
    return {
      cur: { from: curFrom, to: addDays(curFrom, 6) },
      prev: { from: addDays(curFrom, -7), to: addDays(curFrom, -1) }
    };
  }
  function weekAgg(rg) {
    var vs = S.visits.filter(function (v) { return inRange(v.date, rg); });
    var byCh = {}, daysSet = {};
    vs.forEach(function (v) {
      var k = v.channelId || ('raw:' + (v.rawChannel || ''));
      var c = v.channelId ? channelById(v.channelId) : null;
      if (!byCh[k]) byCh[k] = { key: k, name: c ? c.name : (v.rawChannel || '(未归类)'), visits: 0, first: 0, repeat: 0 };
      byCh[k].visits++;
      if (v.vtype === '初诊') byCh[k].first++; else byCh[k].repeat++;
      daysSet[v.date] = 1;
    });
    var covered = Object.keys(daysSet).length;
    return {
      rg: rg, list: Object.keys(byCh).map(function (k) { return byCh[k]; }),
      visits: vs.length,
      first: vs.filter(function (v) { return v.vtype === '初诊'; }).length,
      repeat: vs.filter(function (v) { return v.vtype === '复诊'; }).length,
      nominal: daysBetween(rg.from, rg.to), covered: covered,
      avg: covered ? vs.length / covered : null
    };
  }
  function wkLabel(rg) { return shortMd(rg.from) + '—' + shortMd(rg.to); }
  function wkRankList(agg) {
    /* ⚠ 只排「该口径 > 0」的渠道：切到「初诊」口径时，只有复诊的渠道会显示一堆 0，
       排进去没有意义（实测 17 行里 13 行是 0）。总量为 0 的口径不列，改为提示。 */
    var list = agg.list.filter(function (r) { return r[wkRankKey] > 0; }).sort(function (a, b) {
      return (b[wkRankKey] - a[wkRankKey]) || (b.visits - a.visits) || (a.name < b.name ? -1 : 1);
    });
    if (!list.length) return '<div class="ch-wkr-none">本期该口径无记录</div>';
    var mx = Math.max.apply(null, list.map(function (r) { return r[wkRankKey]; }).concat([1]));
    return list.map(function (r, i) {
      var w = Math.max(4, Math.round(r[wkRankKey] / mx * 100));
      return '<div class="ch-wkr-row' + (i < 3 ? ' top' + (i + 1) : '') + '">'
        + '<span class="ch-wkr-no">' + (i + 1) + '</span>'
        + '<span class="ch-wkr-name" title="' + esc(r.name) + '">' + esc(r.name) + '</span>'
        + '<span class="ch-wkr-bar"><i style="width:' + w + '%"></i></span>'
        + '<b class="ch-wkr-val">' + r[wkRankKey] + '</b></div>';
    }).join('');
  }
  function wkCard(tag, rg, agg) {
    var cover = agg.covered < agg.nominal
      ? '<span class="ch-wkr-cover warn">仅 ' + agg.covered + '/' + agg.nominal + ' 天有记录</span>'
      : '<span class="ch-wkr-cover">' + agg.covered + ' 天</span>';
    return '<div class="ch-wkr-col">'
      + '<div class="ch-wkr-head"><b>' + tag + '</b><span>' + wkLabel(rg) + '</span></div>'
      + '<div class="ch-wkr-meta"><span>到院 <b>' + agg.visits + '</b></span>'
      + '<span>初诊 <b>' + agg.first + '</b></span>'
      + '<span>复诊 <b>' + agg.repeat + '</b></span>' + cover + '</div>'
      + '<div class="ch-wkr-list">' + wkRankList(agg) + '</div></div>';
  }
  function renderWeeklyRank() {
    var W = naturalWeeks();
    var prev = weekAgg(W.prev), cur = weekAgg(W.cur);
    var keyName = { visits: '到院', first: '初诊', repeat: '复诊' }[wkRankKey];
    var cards = wkCard('上周', W.prev, prev) + wkCard('本自然周', W.cur, cur);

    /* 对比表：union 两周边到院渠道；⚠ 天数不同 ⇒ **只比日均**，不比总量 */
    var map = {};
    prev.list.forEach(function (r) { (map[r.key] = map[r.key] || { name: r.name }).pv = r.visits; });
    cur.list.forEach(function (r) { (map[r.key] = map[r.key] || { name: r.name }).cv = r.visits; });
    var rows = Object.keys(map).map(function (k) {
      var m = map[k], pv = m.pv || 0, cv = m.cv || 0;
      var pa = prev.covered ? pv / prev.covered : null;
      var ca = cur.covered ? cv / cur.covered : null;
      return { name: m.name, pv: pv, cv: cv, pa: pa, ca: ca, diff: (pa != null && ca != null) ? (ca - pa) : null };
    }).sort(function (a, b) { return (b.cv - a.cv) || (b.pv - a.pv) || (a.name < b.name ? -1 : 1); });

    function fmtAvg(v) { return v == null ? '—' : (Math.round(v * 100) / 100).toFixed(2); }
    var cmp = rows.length ? ('<div class="ch-wkr-cmp"><div class="ch-sec-head"><div><h2>两周日均对比</h2>'
      + '<p>按<b>日均</b>比较（上周仅 ' + prev.covered + ' 天有记录 vs 本自然周 ' + cur.covered + ' 天，总量不可直接比）</p></div></div>'
      + '<div class="ch-table-wrap"><table class="ch-table"><thead><tr>'
      + '<th>渠道</th><th>上周日均</th><th>本自然周日均</th><th>日均增减</th></tr></thead><tbody>'
      + rows.map(function (r) {
        var cls = r.diff == null ? '' : (r.diff > 0 ? 'up' : (r.diff < 0 ? 'down' : ''));
        var txt = r.diff == null ? '—'
          : ((r.diff > 0 ? '+' : (r.diff < 0 ? '−' : '±')) + Math.abs(Math.round(r.diff * 100) / 100).toFixed(2));
        return '<tr><td>' + esc(r.name) + '</td><td>' + fmtAvg(r.pa) + '</td><td><b>' + fmtAvg(r.ca) + '</b></td>'
          + '<td><b class="ch-wkr-' + cls + '">' + txt + '</b></td></tr>';
      }).join('')
      + '</tbody></table></div></div>') : '';

    var note = (prev.covered < prev.nominal)
      ? '<div class="ch-msg warn">⚠ 上周窗口 ' + wkLabel(W.prev) + ' 名义 7 天，'
        + '但源表《10月到院登记表》<b>仅从 10.1 起</b>，故只有 <b>10.1—10.4（' + prev.covered + ' 天）</b>有记录，'
        + '9.28—9.30 无记录 —— 不是「0 人次」。据此两周<b>只比日均，不比总量</b>；'
        + '上周缺失的 3 天补录后结论会变。</div>'
      : '';

    return '<div class="ch-sec ch-wkr-sec"><div class="ch-sec-head"><div><h2>渠道周排名（自然周）</h2>'
      + '<p>上周 <b>' + wkLabel(W.prev) + '</b> 与 本自然周 <b>' + wkLabel(W.cur) + '</b> 分别排名 · '
      + '口径 <b>' + keyName + '人次</b> · 窗口按数据末日（' + shortMd(cutoff()) + '）推导</p></div>'
      + '<div class="ch-sec-tools"><div class="ch-eff-tabs" id="chWkRankTabs">'
      + WKR_KEYS.map(function (x) {
        return '<button type="button" data-ch-wkrank="' + x[0] + '"' + (wkRankKey === x[0] ? ' class="active"' : '') + '>' + x[1] + '</button>';
      }).join('') + '</div></div></div>'
      + '<div class="ch-wkr-grid">' + cards + '</div>'
      + cmp + note + '</div>';
  }

  /* ============================ 11. 优先行动 ============================
     示意图：最多 3 条行动卡，每条＝渠道名 + 当前状态 + 具体原因 + 下一步 + 操作按钮。 */
  var act_view_label = '';
  function actStateOf(c, item) {
    if (item.kind === 'optimize' && !hasRev(c)) return { txt: '收益待补', cls: 'todo' };
    if (stageLabel(c)) return { txt: stageLabel(c), cls: 'stage' };
    if (isPendingType(c)) return { txt: '待归类', cls: 'todo' };
    return { txt: '进行中', cls: 'stage' };
  }
  function hasRev(c) {
    return S.money.some(function (m) { return m.channelId === c.id && m.revenue !== null && m.revenue !== ''; });
  }
  function actCard(item) {
    var c = item.ch;
    var s0 = actStateOf(c, item);
    var isRev = (item.kind === 'optimize' && !hasRev(c));
    return '<div class="ch-action">'
      + '<span class="ch-action-ic">❦</span>'
      + '<div class="ch-action-mid">'
      + '<div class="ch-action-top"><b>' + esc(c.name) + '</b>'
      + '<span class="ch-state ' + s0.cls + '">' + esc(s0.txt) + '</span></div>'
      + '<div class="ch-action-grid">'
      + '<span><i>最近进展</i>' + esc(c.lastAction || '暂无推进记录') + '</span>'
      + '<span><i>下一步</i>' + esc(c.nextAction || '待填') + (c.nextActionDue ? '（' + shortMd(c.nextActionDue) + '）' : '') + '</span>'
      + '</div>'
      /* ⚠ why / gap 是模块内部生成的文案（含 <b> 等标记），这里按 HTML 输出；
         如需加入外部输入字段，必须先转义。 */
      + '<div class="ch-action-gap">' + item.why + '</div>'
      + '<div class="ch-action-gap">依据：' + (item.gap || '数据完整') + ' · 区间 ' + esc(act_view_label) + '</div>'
      + '</div>'
      + '<button type="button" class="ch-btn ' + (isRev ? 'ghost' : 'primary') + ' sm"'
      + ' data-ch-upd="' + esc(c.id) + '" data-ch-tab="' + (isRev ? 'money' : 'progress') + '">'
      + (isRev ? '补录收益' : '记录跟进') + ' ›</button>'
      + '</div>';
  }
  function renderAdvice(adv, st) {
    act_view_label = st.rg.label;
    /* ⚠ 排序优先级（示意图：最多 3 条，且尽量来自不同渠道）：
         待跟进（超期 / 有转介未到院） > 优先投入 > 需要优化（个性化） > 聚合兜底
       聚合条目（如「22 个渠道缺收益」）永远排最后 —— 只有在没有个性化动作时才占名额。 */
    var all = adv.follow.concat(adv.invest, adv.optimize.filter(function (x) { return !x.aggregate; }))
      .concat(adv.optimize.filter(function (x) { return x.aggregate; }));
    var picked = [], seen = {};
    for (var k = 0; k < all.length && picked.length < 3; k++) {
      var it = all[k];
      /* 同一渠道最多出现一次（聚合条目例外：它是全局兜底） */
      if (!it.aggregate && seen[it.ch.id]) continue;
      seen[it.ch.id] = 1;
      picked.push(it);
    }
    var body = picked.length ? picked.map(actCard).join('')
      : '<div class="ch-empty">本期暂无可执行的行动。<br>先补「下一步行动 + 截止日期」，或录入收益。</div>';
    var rules = '<details class="ch-rules"><summary>行动生成规则（透明，不编造数字）</summary>'
      + '<div>· 收入 / 成本缺失 → 只评价进度和到院，<b>不判断获益最大</b>；</div>'
      + '<div>· 样本少（到院 &lt; 3）或观察时间短 → 标记<b>观察中</b>，不作强结论；</div>'
      + '<div>· 到院多但贡献低（≤ 组内最高的 20%）→ 核查成本、服务组合与收入归属；</div>'
      + '<div>· 已有咨询 / 转介但未到院 → 跟进预约衔接；</div>'
      + '<div>· 长期无进展或跟进超期 → 生成负责人待办；</div>'
      + '<div>· 新渠道因合作时间短，<b>不直接判定为低效</b>，单独给「值得继续培育」。</div>'
      + '<div class="ch-hint" style="margin-top:6px">规则在本机运行，不修改原始数据；若接入 AI，'
      + '仅用于基于结构化统计解释与生成建议。</div></details>';
    return '<div class="ch-card">' + body + rules + '</div>';
  }

  /* ============================ 12. 全部渠道 ============================
     示意图：搜索 + 筛选，下方渠道卡（桌面 2—3 列 / 手机单列）。
     卡片＝名称 + 阶段 + 到院与收益 + 最近进展 + 下一步 + 底部「查看详情 / 更新」。 */
  var fltKey = 'all';
  var fltSearch = '';
  var srchTimer = null;   /* 搜索防抖计时器（模块级，不挂在会被重建的节点上） */
  var sortKey = 'visits';
  function channelCard(r) {
    var c = r.ch;
    var pl = progressLine(c);
    var s0 = stageLabel(c);
    var revTxt = r.hasRevenue ? (yuan(r.revenue) + ' 元') : '待补';
    var tag = null;
    if (isPendingType(c)) tag = { t: '类型待归类', cls: 'todo' };
    else if (!r.hasRevenue && r.visits > 0) tag = { t: '收益待补', cls: 'todo' };
    else if (!s0) tag = { t: '阶段待录入', cls: 'idle' };
    return '<div class="ch-ccard">'
      + '<div class="ch-ccard-head">'
      + '<span class="ch-ccard-ic">' + (isSchool(c) ? '🏫' : '❦') + '</span>'
      + '<div><b>' + esc(c.name) + '</b>'
      + '<small>' + esc(c.type || '类型待归类') + ' · ' + (c.isNew === true ? '新渠道' : (c.isNew === false ? '既往渠道' : '新/既往待确认')) + '</small></div>'
      + (tag ? '<span class="ch-state ' + tag.cls + '">' + esc(tag.t) + '</span>' : '<span class="ch-state stage">' + esc(s0 || '') + '</span>')
      + '</div>'
      + pl
      + '<div class="ch-ccard-kv">'
      + '<div><span>到院人次</span><b>' + r.visits + '</b></div>'
      + '<div><span>最近进展</span><b class="txt">' + esc(c.lastAction || '—') + '</b></div>'
      + '</div>'
      + '<div class="ch-ccard-kv">'
      + '<div><span>实际收入</span><b class="' + (r.hasRevenue ? '' : 'pending') + '">' + revTxt + '</b></div>'
      + '<div><span>下一步</span><b class="txt">' + esc(c.nextAction || '待填') + (c.nextActionDue ? '（' + shortMd(c.nextActionDue) + '）' : '') + '</b></div>'
      + '</div>'
      + '<div class="ch-ccard-foot">'
      + '<button type="button" class="ch-btn ghost sm" data-ch-open="' + esc(c.id) + '">查看详情</button>'
      + '<button type="button" class="ch-btn primary sm" data-ch-upd="' + esc(c.id) + '" data-ch-tab="progress"><i>✎</i>更新</button>'
      + '</div></div>';
  }
  /* 阶段进度条：与详情 / 更新窗口共用同一份 STAGES 数据 */
  function progressLine(c) {
    var i = STAGES.indexOf(c.stage);
    return '<div class="ch-pline">' + STAGES.map(function (x, k) {
      var cls = k === i ? 'on' : (i >= 0 && k < i ? 'done' : 'idle');
      return '<span class="ch-pnode ' + cls + '"><i></i><em>' + esc(x) + '</em></span>';
    }).join('') + '</div>';
  }
  function renderChannels(st) {
    var q = fltSearch.trim().toLowerCase();
    var list = st.channels.filter(function (r) {
      var c = r.ch;
      if (fltKey === 'school' && !isSchool(c)) return false;
      if (fltKey === 'org' && c.type !== '医生/机构转介') return false;
      if (fltKey === 'online' && c.type !== '线上平台') return false;
      if (fltKey === 'norev' && r.hasRevenue) return false;
      if (q) {
        var hay = (c.name + ' ' + (c.aliases || []).join(' ') + ' ' + (c.rawNames || []).join(' ')).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
    list.sort(function (a, b) { return b.visits - a.visits; });
    var FILTERS = [['all', '全部'], ['school', '学校'], ['org', '机构'], ['online', '线上'], ['norev', '收益待补']];
    var counts = {
      all: st.channels.length, school: st.schools, norev: st.missingRevenue,
      org: st.channels.filter(function (r) { return r.ch.type === '医生/机构转介'; }).length,
      online: st.channels.filter(function (r) { return r.ch.type === '线上平台'; }).length
    };
    return ''
      + '<div class="ch-ctools">'
      + '<input class="ch-input ch-csearch" id="chFltSearch" placeholder="搜索渠道名称" value="' + esc(fltSearch) + '">'
      + '<div class="ch-cfilts" id="chFilt">'
      + FILTERS.map(function (x) {
        return '<button type="button" data-ch-flt="' + x[0] + '"' + (fltKey === x[0] ? ' class="active"' : '') + '>'
          + x[1] + '<b>' + (counts[x[0]] == null ? 0 : counts[x[0]]) + '</b></button>';
      }).join('')
      + '</div></div>'
      + '<div class="ch-cgrid">'
      + (list.length ? list.map(channelCard).join('') : '<div class="ch-empty">没有匹配的渠道。</div>')
      + '</div>'
      + '<div class="ch-hint">共 <b>' + list.length + '</b> 个渠道'
      + (fltKey === 'school' ? '（已按「学校绿色通道」筛选）' : '') + '。'
      + '卡片显示与图表、摘要、行动建议<b>同一数据源</b>，保存后同步刷新。</div>';
  }

  function renderDetail(st) {
    var rg = st.rg, pr = prevRange(rg);
    var pv = S.visits.filter(function (v) { return inRange(v.date, pr); });
    /* ⚠⚠ 上一期「覆盖判定」：若整个上一等长周期都早于到院库**最早一条记录**，
       那它是「无数据」而不是「0 人次」——写成 0 会被读成「上期渠道到院为零」，
       属**误判**（本快照只覆盖 10 月，9 月渠道明细根本不在库里）。
       与「缺值→待补、不得默认 0」同源，故这里单列 `prevCovered`。 */
    var minDate = '';
    S.visits.forEach(function (v) { if (v.date && (!minDate || v.date < minDate)) minDate = v.date; });
    var prevCovered = !!(minDate && pr.to >= minDate);
    function cmp(a, b, unit) {
      if (!prevCovered) return '—';                 /* 上一期无覆盖 → 不给增减结论 */
      if (!a && !b) return '无变化';
      if (!a) return '新增';
      var diff = b - a, pct = (b / a - 1) * 100;
      return (diff >= 0 ? '+' : '−') + Math.abs(diff) + ' ' + unit
        + '（' + (diff >= 0 ? '+' : '−') + Math.abs(pct).toFixed(1) + '%）';
    }
    function prevCell(n) {                          /* 上一期单元格：无覆盖时写「无数据」而非 0 */
      return prevCovered ? (n + ' 人次') : '<span class="ch-na">无数据</span>';
    }
    function cnt(list, vt) { return list.filter(function (v) { return v.vtype === vt; }).length; }
    var rows = [
      ['渠道到院人次', prevCell(pv.length), st.visits + ' 人次', cmp(pv.length, st.visits, '人次')],
      ['初诊人次', prevCell(cnt(pv, '初诊')), st.first + ' 人次', cmp(cnt(pv, '初诊'), st.first, '人次')],
      ['复诊人次', prevCell(cnt(pv, '复诊')), st.repeat + ' 人次', cmp(cnt(pv, '复诊'), st.repeat, '人次')]
    ];
    var newCh = st.channels.filter(function (r) { return r.ch.isNew === true; });
    var oldCh = st.channels.filter(function (r) { return r.ch.isNew === false; });
    function sum(l, k) { return l.reduce(function (a, r) { return a + n(r[k]); }, 0); }

    var h = '<details class="ch-details"><summary>趋势与明细<span>点击展开 ⌄</span></summary><div class="ch-details-body">'
      + '<div class="ch-sec-head"><div><h2>与上一等长周期比较</h2>'
      + '<p>' + esc(pr.from) + ' — ' + esc(pr.to) + '（' + pr.days + ' 天） 对 ' + esc(rg.from) + ' — ' + esc(rg.to) + '（' + rg.days + ' 天）</p>'
      + (prevCovered ? ''
          : '<p class="ch-na-note">⚠ 上一期（' + esc(shortMd(pr.from)) + '—' + esc(shortMd(pr.to)) + '）'
            + '<b>早于到院库最早记录 ' + esc(shortMd(minDate)) + '</b>，本页无该期数据，'
            + '故「上一期」记 <b>无数据</b>、增减记 <b>—</b>，<b>不能读作 0 人次</b>。'
            + '要对比该期需补入对应期间的到院记录（或改用「周报口径」区块比较）。</p>')
      + '</div></div>'
      + '<div class="ch-table-wrap"><table class="ch-table"><thead><tr><th>指标</th><th>上一期</th><th>本期</th><th>增减</th></tr></thead><tbody>'
      + rows.map(function (r) {
        var dir = /^\+/.test(r[3]) ? 'up' : (/^−/.test(r[3]) ? 'down' : '');
        return '<tr><td>' + r[0] + '</td><td>' + r[1] + '</td><td><b>' + r[2] + '</b></td>'
          + '<td><b style="color:' + (dir === 'up' ? '#E0576F' : (dir === 'down' ? '#21A6A0' : '#5f6678')) + '">' + r[3] + '</b></td></tr>';
      }).join('')
      + '</tbody></table></div>'
      + '<div style="height:14px"></div>'
      + '<div class="ch-sec-head"><div><h2>新渠道 vs 既往渠道</h2></div></div>'
      + '<div class="ch-table-wrap"><table class="ch-table"><thead><tr><th>分类</th><th>渠道数</th><th>到院人次</th><th>初诊人次</th><th>实际收入</th></tr></thead><tbody>'
      + '<tr><td><span class="ch-tag new">新渠道</span></td><td>' + newCh.length + '</td><td>' + sum(newCh, 'visits') + '</td><td>' + sum(newCh, 'first') + '</td><td>' + (newCh.some(function (r) { return r.hasRevenue; }) ? yuan(sum(newCh, 'revenue')) + ' 元' : '待补齐') + '</td></tr>'
      + '<tr><td><span class="ch-tag old">既往渠道</span></td><td>' + oldCh.length + '</td><td>' + sum(oldCh, 'visits') + '</td><td>' + sum(oldCh, 'first') + '</td><td>' + (oldCh.some(function (r) { return r.hasRevenue; }) ? yuan(sum(oldCh, 'revenue')) + ' 元' : '待补齐') + '</td></tr>'
      + '<tr><td><span class="ch-tag plain">待确认</span></td><td>' + (st.channels.length - newCh.length - oldCh.length) + '</td><td colspan="3" style="color:#8b91a3">新/既往分类待负责人确认（跨月保留，不每月重置）</td></tr>'
      + '</tbody></table></div>'
      + '<div style="height:14px"></div>'
      + '<div class="ch-sec-head"><div><h2>逐日到院</h2><p>' + esc(rg.from) + ' — ' + esc(rg.to) + '，按就诊日期</p></div></div>'
      + barsByDay(rg, st)
      + '</div></details>';
    return h;
  }
  function barsByDay(rg, st) {
    var days = [], d = rg.from, guard = 0;
    while (d <= rg.to && guard++ < 70) { days.push(d); d = addDays(d, 1); }
    var data = days.map(function (x) {
      var list = S.visits.filter(function (v) { return v.date === x; });
      return { d: x, total: list.length, first: list.filter(function (v) { return v.vtype === '初诊'; }).length };
    });
    var mx = Math.max.apply(null, data.map(function (x) { return x.total; }).concat([1]));
    return '<div class="ch-table-wrap"><table class="ch-table"><thead><tr><th>日期</th><th>到院人次</th><th>初诊</th><th>分布</th></tr></thead><tbody>'
      + data.map(function (x) {
        return '<tr><td>' + shortMd(x.d) + '</td><td><b>' + x.total + '</b></td><td>' + x.first + '</td>'
          + '<td><div class="ch-bar" style="width:160px"><i style="width:' + Math.round(x.total / mx * 100) + '%"></i></div></td></tr>';
      }).join('') + '</tbody></table></div>';
  }

  function renderSettings(st) {
    var snap = window.CHANNEL_SNAPSHOT || {};
    var syncState = S.sync.status === 'ok' ? 'good' : (S.sync.status === 'fail' ? 'bad' : 'warn');
    var syncMsg = S.sync.status === 'ok'
      ? '同步成功：新增 ' + S.sync.lastAdded + ' 条、更新 ' + S.sync.lastUpdated + ' 条'
      : (S.sync.status === 'fail' ? ('同步失败：' + esc(S.sync.lastErr)) : '待连接 —— 未配置在线表授权，浏览器无法直接读取');

    return ''
      + '<div class="ch-msg good">数据的填写与导入都在<b>「更新数据」窗口</b>里：'
      + '记录进展 / 补录收益 / 粘贴到院数据。本区只放在线表同步、档案与数据管理。</div>'
      /* ---------- 在线表配置 ---------- */
      + '<details class="ch-details" id="chSecSync"><summary>数据源 · 在线表同步<span>'
      + (S.sync.status === 'ok' ? '已同步' : (S.sync.status === 'fail' ? '失败' : '待连接')) + ' ⌄</span></summary>'
      + '<div class="ch-details-body">'
      + '<div class="ch-msg ' + syncState + '">' + syncMsg + '</div>'
      + '<div class="ch-field" style="margin-top:11px"><label>在线表链接</label>'
      + '<input class="ch-input" id="chSyncUrl" value="' + esc(S.sync.url || snap.sourceUrl || '') + '" placeholder="https://www.kdocs.cn/l/..."></div>'
      + '<div class="ch-row2"><div class="ch-field"><label>授权 / 接口</label>'
      + '<select class="ch-select" id="chSyncAuth"><option value="">未配置</option>'
      + '<option value="kdocs">金山文档（需服务端中转）</option><option value="api">自定义接口</option></select>'
      + '<div class="ch-hint">浏览器直连会受跨域与登录态限制；生产环境建议由服务端中转。</div></div>'
      + '<div class="ch-field"><label>字段映射</label>'
      + '<input class="ch-input" id="chSyncMap" value="序号｜就诊日期｜姓名｜年龄｜联系方式｜初/复诊｜来源渠道｜随访人｜备注" readonly>'
      + '<div class="ch-hint">首次连接后确认；与粘贴入口共用同一套字段。</div></div></div>'
      + '<div class="ch-actions-row"><button class="ch-submit" id="chDoSync">手动同步</button>'
      + '<button class="ch-submit sec" id="chSaveSync">保存配置</button>'
      + '<button class="ch-submit sec" id="chOpenSource">打开源表</button></div>'
      + (snap.rows && snap.rows.length && !snap.isDemo
        ? '<div class="ch-msg">已内置 <b>真实快照</b>：' + esc(snap.sourceName || '') + ' · 抓取于 '
          + esc(snap.fetchedAt) + ' · ' + snap.rows.length + ' 条。'
          + '快照用于离线可用，<b>不等于</b>「已连接」。</div>'
        : '')
      + '</div></details>'

      /* ---------- 渠道档案 ---------- */
      + '<details class="ch-details" id="chSecRegistry"><summary>渠道档案与归并<span>'
      + S.channels.length + ' 个渠道' + (st.untriaged ? ' · ' + st.untriaged + ' 个待归类' : '') + ' ⌄</span></summary>'
      + '<div class="ch-details-body">' + registryHTML() + '</div></details>'

      /* ---------- 变更日志 ---------- */
      + '<details class="ch-details"><summary>操作记录<span>最近 ' + Math.min(S.log.length, 30) + ' 条 ⌄</span></summary>'
      + '<div class="ch-details-body">'
      + (S.log.length ? S.log.slice(0, 30).map(function (l) {
        return '<div class="ch-tl-item"><time>' + esc(l.at.replace('T', ' ').slice(0, 16)) + ' · ' + esc(l.who) + '</time>'
          + '<div class="ch-tl-body"><b>' + esc(l.what) + '</b>' + (l.detail ? '：' + esc(l.detail) : '') + '</div></div>';
      }).join('') : '<div class="ch-empty">暂无操作记录</div>')
      + '</div></details>'

      /* ---------- 数据管理 ---------- */
      + '<details class="ch-details"><summary>数据管理<span>查看完整身份 / 清理 ⌄</span></summary>'
      + '<div class="ch-details-body">'
      + '<div class="ch-msg warn">姓名默认脱敏、联系方式默认遮蔽；排行榜与建议区<b>不展示患者身份信息</b>。'
      + '完整身份、导入导出与修改权限沿用现有角色权限，并保留操作记录。</div>'
      + '<div class="ch-actions-row">'
      + '<button class="ch-submit sec" id="chReveal">' + (state.revealIdentity ? '恢复脱敏' : '查看完整身份') + '</button>'
      + '<button class="ch-submit sec" id="chExport">导出 JSON</button>'
      + '<button class="ch-submit sec" id="chImportJson">导入 JSON</button>'
      + '<button class="ch-submit danger" id="chResetAll">清空渠道看板数据</button>'
      + '</div><div class="ch-legend">'
      + '<span><i style="background:#eef1f7"></i>无记录</span>'
      + '<span><i style="background:#21A6A0"></i>真实 0 值</span>'
      + '<span><i style="background:#EF9F27"></i>待补齐</span>'
      + '<span><i style="background:#E0576F"></i>连接失败 / 口径冲突</span></div>'
      + '</div></details>';
  }

  function registryHTML() {
    var pend = S.channels.filter(isPendingType);
    var h = '';
    if (pend.length) {
      h += '<div class="ch-msg warn"><b>' + pend.length + ' 个来源渠道是简称，类型待归类。</b>'
        + '归类后历史统计会同步重算（按渠道ID归属，不重新累计）。</div>';
    }
    /* 卡片网格，不是表格：每张卡一个渠道，控件就地在卡内，扫一眼就能改 */
    h += '<div class="ch-reg">' + S.channels.map(function (c) {
      var al = (c.aliases || []).concat(c.rawNames || []).filter(function (x, i2, a) { return x && a.indexOf(x) === i2; });
      return '<div class="ch-reg-card">'
        + '<div class="ch-reg-head"><b>' + esc(c.name) + '</b>'
        + (c.isNew === true ? '<span class="ch-tag new">新渠道</span>'
          : (c.isNew === false ? '<span class="ch-tag old">既往</span>' : ''))
        + (isPendingType(c) ? '<span class="ch-tag warn">待归类</span>' : '')
        + '<button class="ch-mini ch-reg-more" data-ch-open="' + esc(c.id) + '">详情</button></div>'
        + '<div class="ch-reg-grid">'
        /* ⭐ 2026-10-10 业主要求：类型**可自由填写**（下拉只能选既有几项，
           而渠道类别不断在更新）→ 改 input + datalist：既能选建议值，也能直接输入新值。 */
        + '<div class="ch-field"><label>类型（可填写）</label>'
        + '<input class="ch-input" list="chTypeList" data-ch-type="' + esc(c.id) + '" '
        + 'value="' + esc(c.type || '') + '" placeholder="选或直接输入新类型"></div>'
        + '<div class="ch-field"><label>新 / 既往</label><select class="ch-select" data-ch-new="' + esc(c.id) + '">'
        + '<option value=""' + (c.isNew === null ? ' selected' : '') + '>待确认</option>'
        + '<option value="1"' + (c.isNew === true ? ' selected' : '') + '>新渠道</option>'
        + '<option value="0"' + (c.isNew === false ? ' selected' : '') + '>既往渠道</option>'
        + '</select></div>'
        + '<div class="ch-field"><label>负责人</label><input class="ch-input" data-ch-owner="' + esc(c.id) + '" value="' + esc(c.owner || '') + '"></div>'
        + (isSchool(c)
          ? '<div class="ch-field"><label>阶段（可填写）</label>'
            + '<input class="ch-input" list="chStageList" data-ch-stage="' + esc(c.id) + '" '
            + 'value="' + esc(c.stage || '') + '" placeholder="选或输入新阶段"></div>'
          : '<div class="ch-field"><label>阶段（可填写）</label>'
            + '<input class="ch-input" list="chStageList" data-ch-stage="' + esc(c.id) + '" '
            + 'value="' + esc(c.stage || '') + '" placeholder="留空＝未开始"></div>')
        + '</div>'
        + '<div class="ch-reg-foot">'
        + '<span class="ch-reg-alias">' + (al.length ? ('别名：' + esc(al.join(' / '))) : '无别名') + '</span>'
        + '<button class="ch-mini" data-ch-merge="' + esc(c.id) + '">归并…</button></div>'
        + '</div>';
    }).join('') + '</div>'
      /* ⭐ 建议值列表：**既有类型 ∪ 已用过的自定义值** ——
         填过的新类型下次自动出现在建议里，所以「类别不断更新」不需要改代码。 */
      + '<datalist id="chTypeList">' + uni(TYPES.concat(S.channels.map(function (c) { return c.type; }).filter(Boolean)))
        .map(function (t) { return '<option value="' + esc(t) + '"></option>'; }).join('') + '</datalist>'
      + '<datalist id="chStageList">' + uni(STAGES.concat(STAGE_TERMINAL)
          .concat(S.channels.map(function (c) { return c.stage; }).filter(Boolean)))
        .map(function (x2) { return '<option value="' + esc(x2) + '"></option>'; }).join('') + '</datalist>'
      /* ⭐ 新增渠道：学校 / 机构是不断新增的，必须能**手动建档**，而不是只能等登记表里出现 */
      + '<div class="ch-reg-add"><b>新增渠道 / 学校</b>'
      + '<div class="ch-reg-add-row">'
      + '<input class="ch-input" id="chNewName" placeholder="名称（如 新桥医院 / 双福三小）">'
      + '<input class="ch-input" id="chRegNewType" list="chTypeList" placeholder="类型（留空＝自动判定）">'
      + '<button class="ch-submit sec" id="chRegAdd" type="button">建档</button></div>'
      + '<div id="chRegAddMsg"></div>'
      + '<div class="ch-hint">类型 / 阶段都能<b>直接输入新值</b>，不必迁就下拉里的旧选项；'
      + '输入过的新值会进入建议列表，下次可直接选。</div></div>'
      + '<div class="ch-hint">归并说明：同一学校/机构的简称与全称通过「别名」归并；'
      + '归并后该渠道的历史到院与收益按渠道ID重新归属，统计同步重算。</div>';
    return h;
  }

  /* ============================ 13. 集中更新窗口（模态） ============================
     2026-10-08 业主：按示意图把填写收敛到**一个窗口**，主页面不再长期显示表单。
       · 入口：顶部「更新数据」或任意渠道卡的「更新」（后者自动带入该渠道）
       · 三个 Tab：记录进展 ｜ 补录收益 ｜ 粘贴到院数据
       · 桌面居中、手机全屏；底部固定绿色「保存更新」
       · 数据逻辑完全复用既有 submitSchool / submitBiz / submitBizBatch / commitImport
     ========================================================================== */
  var modalTab = 'progress';   // progress | money | paste
  var wbPick = '';             // 当前更新的渠道 id
  var wbDraft = {};            // 按渠道暂存的未提交草稿（切换渠道不丢）

  function draftOf(id) { return wbDraft[id] || {}; }
  function clearWbDraft(id) { if (id) delete wbDraft[id]; }
  function chTimeline(cid, k) {
    return S.progress.filter(function (p) { return p.channelId === cid; })
      .sort(function (a, b) { return a.date < b.date ? 1 : -1; }).slice(0, k || 3);
  }
  /* 需要负责人补什么 —— 用于优先行动与渠道卡角标 */
  function wbFlag(r) {
    if (isPendingType(r.ch)) return '待归类';
    if (isOverdue(r.ch)) return '跟进超期';
    if (r.visits > 0 && !r.hasRevenue) return '缺收入';
    return '';
  }

  /* 更新窗口 HTML（挂到 #chModalHost 内） */
  /* ⭐ 周报 Tab：**不绑定某个渠道**（它是一期汇总），所以单独渲染，
     且必须在「请先选择渠道」的前置判断**之前**返回。 */
  function renderWeeklyModal() {
    var tabs = [['progress', '记录进展'], ['money', '补录收益'], ['paste', '粘贴到院数据'], ['weekly', '粘贴文字周报']];
    var head = '<div class="ch-modal-head">'
      + '<b>更新渠道</b>'
      + '<div class="ch-modal-who"><span class="ch-ccard-ic">✎</span>'
      + '<div><span class="ch-modal-name">渠道周报 · 文字识别</span>'
      + '<small>粘贴一段周报文字，自动提取渠道 / 到院 / 拜访 / 计划</small></div></div>'
      + '<button type="button" class="ch-close dk" id="chModalClose" aria-label="关闭">×</button></div>'
      + '<div class="ch-tabs" id="chTabs">' + tabs.map(function (x) {
        return '<button type="button" data-ch-tab="' + x[0] + '"' + (modalTab === x[0] ? ' class="active"' : '') + '>' + x[1] + '</button>';
      }).join('') + '</div>';
    var body = ''
      + '<div class="ch-mfield"><label>本期日期<b>*</b></label>'
      + '<input class="ch-input" id="chWeeklyDate" type="text" inputmode="numeric" autocomplete="off" '
      + 'value="' + esc(wkDefaultDate()) + '" placeholder="如 10.11 或 2026-10-11">'
      + '<div class="ch-hint">周报文字<b>自带</b>日期前缀（如「<b>10.11日本周，</b>」）时<b>以文本为准</b>；'
      + '<b>没带</b>前缀（正文直接从内容开始，如「K教授这周转诊12人…」）就按这里填的日期归档。默认今天，改一下即可。</div></div>'
      + '<div class="ch-mfield"><label>粘贴周报文字<b>*</b></label>'
      + '<textarea class="ch-textarea ch-wk-box" id="chWeeklyBox" spellcheck="false" '
      + 'placeholder="10.11日本周，K教授这周转诊12人，实际到院8人，转化率66.67%。&#10;'
      + '目前我们一共开通15条外部渠道，本周各渠道合计到院44人。&#10;'
      + '具体数据：GY2人、HJL1人、HM10人、LC1人……&#10;'
      + '（原文照粘，不必删改）"></textarea>'
      + '<div class="ch-hint">开头写「<b>10.11日本周，</b>」（日期 + 日本周 + 逗号）即可；'
      + '也认 <b>10.11:</b> / <b>10.11日本周:</b> / <b>10月11日，</b> 这几种写法。'
      + '系统<b>不自行推断周区间</b>；到院人数属渠道汇总、无患者明细，故只进「周报口径」区块，'
      + '<b>不并入到院记录库</b>；识别到的单位会自动建档（类型可再手改）。</div></div>'
      + '<div class="ch-actions-row"><button type="button" class="ch-btn ghost" id="chWeeklyParse">识别并预览</button>'
      + '<button type="button" class="ch-btn ghost" id="chWeeklyClear">清空</button>'
      + '<button type="button" class="ch-btn ghost" id="chWeeklyTpl">填入模板</button>'
      /* ⚠ 一期一个按钮：两期文字拼在一起会被解析成**一期**（只认第一个日期前缀），
         数字混淆、无法核对。 */
      + ((window.CHANNEL_WEEKLY_SEED || {}).reports || []).map(function (r) {
        return '<button type="button" class="ch-btn ghost" data-ch-wkseed="' + esc(r.label) + '">载入 ' + esc(r.label) + ' 样例</button>';
      }).join('') + '</div>'
      + '<div class="ch-hint">⚠ 一次只粘<b>一期</b>：文字带日期前缀时按第一个前缀归档，'
      + '不带则用上面的「本期日期」；多期混在一起会被当成一期。原文会一并存档，便于溯源。<br>'
      + '💡 不知道怎么写？点「<b>填入模板</b>」拿一段骨架，把 XX 换成真实数字即可。</div>'
      + '<div id="chWeeklyPreview"></div>';
    return '<div class="ch-modal" role="dialog" aria-modal="true" aria-label="更新渠道">' + head
      + '<div class="ch-modal-body">' + body + '</div>'
      + '<div class="ch-modal-foot"><span class="ch-hint" style="margin:0">'
      + '周报点「确认写入周报」即生效（无需「保存更新」）</span></div></div>';
  }
  function renderUpdateModal(st) {
    if (modalTab === 'weekly') return renderWeeklyModal();
    var c = channelById(wbPick);
    if (!c) {
      return '<div class="ch-modal"><div class="ch-modal-head"><b>更新渠道</b>'
        + '<button type="button" class="ch-close dk" id="chModalClose">×</button></div>'
        + '<div class="ch-modal-body"><div class="ch-empty">请先选择要更新的渠道。</div></div></div>';
    }
    var cut = cutoff();
    var row = null;
    ((st && st.channels) || []).forEach(function (x) { if (x.ch.id === c.id) row = x; });
    row = row || { visits: 0, first: 0, repeat: 0, revenue: null, cost: null, hasRevenue: false };
    var d = draftOf(c.id);
    var isSch = isSchool(c);

    var opts = S.channels.map(function (x) {
      return '<option value="' + esc(x.id) + '"' + (x.id === c.id ? ' selected' : '') + '>'
        + esc(x.name) + (x.type ? '（' + esc(x.type) + '）' : '') + '</option>';
    }).join('')
      /* ⭐ 2026-10-10 业主：新学校 / 新渠道不在列表里时，要能**就地新建**而不是先跑去别处建档。
         注意 value 用「__new__」这种不可能与渠道 id 冲突的哨兵值（渠道 id 形如 cXXXX）。 */
      + '<option value="__new__">＋ 新建渠道 / 学校…</option>';

    var tabs = [['progress', '记录进展'], ['money', '补录收益'], ['paste', '粘贴到院数据'], ['weekly', '粘贴文字周报']];
    var head = '<div class="ch-modal-head">'
      + '<b>更新渠道</b>'
      + '<div class="ch-modal-who"><span class="ch-ccard-ic">' + (isSch ? '🏫' : '❦') + '</span>'
      + '<div><span class="ch-modal-name">' + esc(c.name) + '</span>'
      + '<small>' + esc(c.type || '类型待归类') + ' · ' + (c.isNew === true ? '新渠道' : (c.isNew === false ? '既往渠道' : '新/既往待确认')) + '</small></div>'
      + '<select class="ch-select ch-modal-pick" id="chPickCh">' + opts + '</select></div>'
      + '<button type="button" class="ch-close dk" id="chModalClose" aria-label="关闭">×</button>'
      + '</div>'
      /* 就地建档行：默认隐藏，选「＋ 新建…」后展开 */
      + '<div class="ch-newpick" id="chNewPick" hidden>'
      + '<div class="ch-newpick-row">'
      + '<input class="ch-input" id="chNewPickName" placeholder="新学校 / 渠道名称，如 双福三小、新桥医院">'
      + '<input class="ch-input" id="chNewPickType" list="chTypeList" placeholder="类型（留空＝按名称自动判定）">'
      + '<button type="button" class="ch-submit" id="chNewPickGo">建档并切换</button>'
      + '</div>'
      + '<div class="ch-hint">建档后自动切到该渠道，可直接接着记录进展；'
      + '名称已存在时<b>不会重复建档</b>，会直接切过去。类型留空＝按名称自动判定'
      + '（含「小学 / 三小 / 五小 / 中学」等字样的自动归为学校绿色通道）。</div>'
      + '<div id="chNewPickMsg"></div>'
      + '</div>'
      + '<div class="ch-tabs" id="chTabs">' + tabs.map(function (x) {
        return '<button type="button" data-ch-tab="' + x[0] + '"' + (modalTab === x[0] ? ' class="active"' : '') + '>' + x[1] + '</button>';
      }).join('') + '</div>';

    var body = '';
    if (modalTab === 'progress') {
      body = ''
        + '<div class="ch-mblock"><label>本次跟进方式</label>'
        + '<div class="ch-checks" id="chSActs">'
        + ACTIONS.map(function (a) {
          var on = (d.acts || []).indexOf(a) >= 0;
          return '<label class="ch-check' + (on ? ' on' : '') + '">'
            + '<input type="checkbox" value="' + esc(a) + '"' + (on ? ' checked' : '') + '>' + esc(a) + '</label>';
        }).join('') + '</div></div>'
        + (isSch
          ? '<div class="ch-mblock"><label>当前阶段</label>'
            + '<div class="ch-mpipe" id="chPipe">' + pipeHTML(c) + '</div>'
            + '<div class="ch-pline-note">点任意一步即记录一次阶段变更（历史只增不改）；'
            + '<span class="ch-state idle">未开始</span>'
            + '<span class="ch-state on">当前</span>'
            + '<span class="ch-state done">已完成</span>'
            + '<button type="button" class="ch-mini" data-ch-pipe="' + esc(c.id) + '" data-ch-pipe-val="暂停">暂停</button>'
            + '<button type="button" class="ch-mini" data-ch-pipe="' + esc(c.id) + '" data-ch-pipe-val="终止">终止</button>'
            + '<span class="ch-hint" style="margin:0">暂停 / 终止需填原因</span></div></div>'
          : '')
        + '<div class="ch-mrow">'
        + '<div class="ch-mfield"><label>下一步计划</label>'
        + '<select class="ch-select" id="chSNext"><option value="">—</option>'
        + NEXT_ACTIONS.map(function (x) {
          return '<option value="' + esc(x) + '"' + (((d.next || c.nextAction) === x) ? ' selected' : '') + '>' + esc(x) + '</option>';
        }).join('') + '</select></div>'
        + '<div class="ch-mfield"><label>跟进日期</label>'
        + '<div class="ch-quick" id="chQuickDue">'
        + '<button type="button" data-ch-due="1">明天</button>'
        + '<button type="button" data-ch-due="3">3天后</button>'
        + '<button type="button" data-ch-due="7">下周</button>'
        + '</div>'
        + '<input class="ch-input" type="date" id="chSDue" value="' + esc(d.due || c.nextActionDue || '') + '">'
        + '</div></div>'
        + '<details class="ch-mmore"><summary>更多信息（可选）</summary>'
        + '<div class="ch-mrow" style="margin-top:10px">'
        + '<div class="ch-mfield"><label>对接人</label><input class="ch-input" id="chSContact" value="' + esc(d.contact || '') + '"></div>'
        + '<div class="ch-mfield"><label>职务</label><input class="ch-input" id="chSTitle" value="' + esc(d.title || '') + '"></div>'
        + '<div class="ch-mfield"><label>今日新增咨询 / 转介（人）</label><input class="ch-input" type="number" min="0" id="chSInquiry" value="' + esc(d.inquiry || '') + '"></div>'
        + '<div class="ch-mfield"><label>本次活动覆盖人数</label><input class="ch-input" type="number" min="0" id="chSCover" value="' + esc(d.cover || '') + '"></div>'
        + '<div class="ch-mfield"><label>当前阻碍</label><input class="ch-input" id="chSBlock" value="' + esc(d.blocker || '') + '"></div>'
        + '<div class="ch-mfield"><label>需要的支持</label><input class="ch-input" id="chSSupport" value="' + esc(d.support || '') + '"></div>'
        + '<div class="ch-mfield"><label>进展日期</label><input class="ch-input" type="date" id="chSDate" value="' + esc(d.date || cut) + '"></div>'
        + '<div class="ch-mfield"><label>一句补充说明</label><input class="ch-input" id="chSNote" value="' + esc(d.note || '') + '"></div>'
        + '</div></details>'
        + '<div class="ch-hint">到院与初复诊由登记表自动统计，这里只记录推进动作与阶段，'
        + '历史按日期形成时间线，<b>更新不会覆盖既往记录</b>。</div>';
    } else if (modalTab === 'money') {
      var rev = (d.rev != null && d.rev !== '') ? d.rev : (row.revenue == null ? '' : row.revenue);
      var cost = (d.cost != null && d.cost !== '') ? d.cost : (row.cost == null ? '' : row.cost);
      body = ''
        + '<div class="ch-mrow">'
        + '<div class="ch-mfield"><label>实际收入（元）</label>'
        + '<input class="ch-input" type="number" min="0" step="0.01" id="chBRev" placeholder="留空＝待补齐" value="' + esc(rev) + '"></div>'
        + '<div class="ch-mfield"><label>渠道直接成本（元）</label>'
        + '<input class="ch-input" type="number" min="0" step="0.01" id="chBCost" placeholder="留空＝待补齐" value="' + esc(cost) + '"></div>'
        + '<div class="ch-mfield"><label>投入工时（可选）</label>'
        + '<input class="ch-input" type="number" min="0" step="0.5" id="chBHours" placeholder="—" value="' + esc(d.hours == null ? '' : d.hours) + '"></div>'
        + '</div>'
        + '<div class="ch-mrow">'
        + '<div class="ch-mfield"><label>收益归属期间</label>'
        + '<select class="ch-select" id="chBScope">'
        + '<option value="day"' + ((d.scope || 'day') === 'day' ? ' selected' : '') + '>按日</option>'
        + '<option value="period"' + (d.scope === 'period' ? ' selected' : '') + '>按期间</option></select></div>'
        + '<div class="ch-mfield"><label>日期 / 起始</label><input class="ch-input" type="date" id="chBFrom" value="' + esc(d.date || cut) + '"></div>'
        + '<div class="ch-mfield"><label>结束（按期间时填）</label><input class="ch-input" type="date" id="chBTo" value="' + esc(d.to || '') + '"></div>'
        + '</div>'
        + '<div class="ch-mrow">'
        + '<div class="ch-mfield"><label>凭证 / 关联记录（可选）</label><input class="ch-input" id="chBProof" value=""></div>'
        + '<div class="ch-mfield"><label>下一步</label><select class="ch-select" id="chBBiz"><option value="">—</option>'
        + BIZ_NEXT.map(function (x) { return '<option value="' + esc(x) + '"' + (c.nextAction === x ? ' selected' : '') + '>' + esc(x) + '</option>'; }).join('')
        + '</select></div></div>'
        + '<div class="ch-hint">填 <b>0</b> ＝ 真实 0 元（参与计算）；<b>留空</b> ＝ 待补齐。'
        + '渠道贡献 ＝ 实际收入 − 直接成本（<b>不是净利润</b>）；成本为 0 或未填时投入产出比显示'
        + '「不适用 / 待补充」，不显示无穷大。重复提交会更新同一条记录，不重复累计。</div>'
        + '<details class="ch-mmore" id="chSecBulk"><summary>批量录入（可选 · 一次填多个渠道）</summary>'
        + '<div class="ch-mrow" style="margin-top:10px">'
        + '<div class="ch-mfield"><label>归属期间</label><select class="ch-select" id="chBulkScope"><option value="day">按日</option><option value="period">按期间</option></select></div>'
        + '<div class="ch-mfield"><label>日期 / 起始</label><input class="ch-input" type="date" id="chBulkFrom" value="' + cut + '"></div>'
        + '<div class="ch-mfield"><label>结束（按期间时填）</label><input class="ch-input" type="date" id="chBulkTo"></div>'
        + '</div><div id="chBulkBody"></div></details>';
    } else {
      body = ''
        + '<div class="ch-mfield"><label>从 Excel / 在线表复制的整块数据（含表头）<b>*</b></label>'
        + '<textarea class="ch-textarea" id="chPasteBox" spellcheck="false" '
        + 'placeholder="序号\t就诊日期\t姓名\t年龄\t联系方式\t初/复诊\t来源渠道\t随访人\t备注&#10;'
        + '1\t2026.10.1\t张X\t15\t13800000000\t复诊\tK\t蒋雨\t"></textarea>'
        + '<div class="ch-hint">自动识别表头 / 制表符 / 换行，也支持逗号分隔。'
        + '同一批数据重复粘贴<b>不会重复累计</b>；日期异常、缺来源渠道、初复诊异常会进入待核对区，'
        + '可先保存有效行、再处理异常行，写入后可撤销本次导入。</div></div>'
        + '<div class="ch-actions-row"><button type="button" class="ch-btn ghost" id="chDoParse">解析并预览</button>'
        + '<button type="button" class="ch-btn ghost" id="chClearPaste">清空</button></div>'
        + '<div id="chPreview"></div>';
    }

    /* 提交类函数读的隐藏字段（保持既有写入逻辑不变） */
    var hidden = ''
      + '<input type="hidden" id="chSCh" value="' + esc(c.id) + '">'
      + '<input type="hidden" id="chSStage" value="">'
      + '<input type="hidden" id="chBCh" value="' + esc(c.id) + '">'
      + '<input type="hidden" id="chBProofDummy" value="">';

    var foot = '<div class="ch-modal-foot">'
      + (modalTab === 'progress'
        ? '<button type="button" class="ch-btn ghost" id="chNoChange">今日无新增进展</button>' : '')
      + '<button type="button" class="ch-btn primary lg" id="chSave">保存更新</button>'
      + '</div>'
      + '<div id="chSchoolMsg"></div><div id="chBizMsg"></div>';

    return '<div class="ch-modal" role="dialog" aria-modal="true" aria-label="更新渠道">'
      + head + '<div class="ch-modal-body">' + body + '</div>' + foot + hidden + '</div>';
  }

  /* 阶段 pipeline（可视化，点哪一步就是哪一步） */
  function pipeHTML(c) {
    var i = STAGES.indexOf(c.stage);
    return '<div class="ch-pipe">' + STAGES.map(function (x, k) {
      var cls = k === i ? ' on' : (i >= 0 && k < i ? ' done' : ' idle');
      return '<button type="button" class="ch-pipe-step ' + cls + '"'
        + ' data-ch-pipe="' + esc(c.id) + '" data-ch-pipe-val="' + esc(x) + '">'
        + '<i></i><em>' + esc(x) + '</em></button>';
    }).join('') + '</div>';
  }

  /* 打开 / 关闭更新窗口 */
  function openUpdate(channelId, tab) {
    if (channelId) wbPick = channelId;
    if (!wbPick || !channelById(wbPick)) {
      var f = S.channels.filter(function (c) { return isSchool(c); })[0] || S.channels[0];
      wbPick = f ? f.id : '';
    }
    if (tab) modalTab = tab;
    var host = $('#chModalHost');
    if (!host) return;
    host.innerHTML = renderUpdateModal(computeStats());
    host.hidden = false;
    host.classList.add('show');
    bindModal();
  }
  function closeUpdate() {
    var host = $('#chModalHost');
    if (!host) return;
    host.classList.remove('show');
    host.hidden = true;
    host.innerHTML = '';
  }

  /* 阶段推进：点 pipeline 某一步即生效（写推进记录，形成时间线） */
  function setStage(id, stage) {
    var c = channelById(id);
    if (!c) return;
    var blocker = (draftOf(id).blocker || '');
    if (STAGE_TERMINAL.indexOf(stage) >= 0) {
      var reason = window.prompt('选择「' + stage + '」需要填写原因（会记入推进记录）：', blocker || '');
      if (reason === null) return;
      if (!String(reason).trim()) { window.alert('暂停 / 终止必须填写原因。'); return; }
      blocker = String(reason).trim();
      (wbDraft[id] = wbDraft[id] || {}).blocker = blocker;
    }
    var date = ($('#chSDate') || {}).value || cutoff();
    var from = c.stage || '待录入';
    if (from === stage) return;
    S.progress.unshift({
      id: 'p' + hash(id + '|' + date + '|' + Date.now()),
      channelId: id, date: date, actions: [],
      stage: stage, nextAction: '', nextFollowUp: '',
      contact: '', contactTitle: '', newInquiry: '', coverage: '',
      blocker: blocker, support: '', note: '',
      noChange: false, owner: OWNER_DEFAULT, createdAt: new Date().toISOString()
    });
    c.stage = stage; c.stageAt = date;
    if (isSchool(c) && !c.type) c.type = '学校绿色通道';
    logAct('阶段变更', c.name + '：' + from + ' → ' + stage);
    save(); renderAll(true); openUpdate(id, modalTab);
  }

  /* 金额速存：按「渠道 + 逐笔 + 数据日」写一条；重复改＝更新同一条 */
  function quickMoney(channelId, field, value) {
    var date = cutoff();
    var m = null;
    for (var i = 0; i < S.money.length; i++) {
      var x = S.money[i];
      if (x.channelId === channelId && (x.scope || 'day') !== 'period' && x.date === date) { m = x; break; }
    }
    if (!m) {
      m = {
        id: 'm' + hash(channelId + '|day|' + date), channelId: channelId, scope: 'day',
        date: date, periodFrom: date, periodTo: date,
        revenue: null, cost: null, hours: null, proof: '', bizNext: '',
        createdAt: new Date().toISOString()
      };
      S.money.push(m);
    }
    m[field] = value;
    m.updatedAt = new Date().toISOString();
    var c = channelById(channelId);
    logAct('效益速填', (c ? c.name : channelId) + ' · ' + date + ' · '
      + (field === 'revenue' ? '实际收入' : (field === 'cost' ? '直接成本' : '投入工时'))
      + '＝' + (value === null ? '待补齐' : yuan(value)));
    if (wbDraft[channelId]) delete wbDraft[channelId][field === 'revenue' ? 'rev' : (field === 'cost' ? 'cost' : 'hours')];
    save(); renderAll(true);
  }

  /* 窗口内的表单 → 按渠道暂存草稿（切换渠道不丢内容） */
  function bindModalDraft() {
    if (!wbPick) return;
    var d = wbDraft[wbPick] || (wbDraft[wbPick] = {});
    function bind(sel, key, ev) {
      var e = $(sel); if (!e) return;
      e[ev || 'oninput'] = function () { d[key] = e.value; };
    }
    bind('#chSDate', 'date'); bind('#chSNext', 'next', 'onchange'); bind('#chSDue', 'due');
    bind('#chBRev', 'rev'); bind('#chBCost', 'cost'); bind('#chBHours', 'hours');
    bind('#chBScope', 'scope', 'onchange'); bind('#chBFrom', 'date'); bind('#chBTo', 'to');
    bind('#chSContact', 'contact'); bind('#chSTitle', 'title'); bind('#chSInquiry', 'inquiry');
    bind('#chSCover', 'cover'); bind('#chSBlock', 'blocker'); bind('#chSSupport', 'support'); bind('#chSNote', 'note');
    $$('#chSActs input').forEach(function (x) {
      x.onchange = function () {
        d.acts = $$('#chSActs input:checked').map(function (y) { return y.value; });
        var l = x.parentNode; if (l && l.classList) l.classList.toggle('on', x.checked);
      };
    });
    /* 跟进日期快捷按钮 */
    var base = ($('#chSDate') || {}).value || cutoff();
    $$('#chQuickDue button').forEach(function (b) {
      b.onclick = function () {
        var v = addDays(base, +b.getAttribute('data-ch-due'));
        var inp = $('#chSDue'); if (inp) inp.value = v;
        d.due = v;
        $$('#chQuickDue button').forEach(function (x) { x.classList.toggle('active', x === b); });
      };
    });
  }

  /* 窗口内的全部事件绑定 */
  function bindModal() {
    var mc = $('#chModalClose'); if (mc) mc.onclick = closeUpdate;
    /* Tab 切换 */
    $$('#chTabs button').forEach(function (b) {
      b.onclick = function () { modalTab = b.getAttribute('data-ch-tab'); openUpdate(wbPick, modalTab); };
    });
    var pick = $('#chPickCh');
    if (pick) pick.onchange = function (ev) {
      /* ⚠⚠ 用 ev.target 而不是闭包里的 pick —— 本仓既有铁律：重渲染界面里
         闭包变量可能已指向被丢弃的旧节点（表现为「点了没反应」）。 */
      var el = (ev && ev.target) || pick;
      var v = el.value;
      if (v === '__new__') {
        var row = $('#chNewPick'); if (row) row.hidden = false;
        var nm = $('#chNewPickName'); if (nm) { nm.focus(); }
        return;
      }
      var row2 = $('#chNewPick'); if (row2) row2.hidden = true;
      openUpdate(v, modalTab);
    };
    /* 建档并切换（弹窗内，故绑在 bindModal） */
    var ngo = $('#chNewPickGo'); if (ngo) ngo.onclick = createChannelInline;
    /* 在名称框里直接回车 = 建档 */
    var nnm = $('#chNewPickName');
    if (nnm) nnm.onkeydown = function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); createChannelInline(); } };
    bindModalDraft();
    /* 阶段 pipeline */
    $$('[data-ch-pipe]').forEach(function (b) {
      b.onclick = function () { setStage(b.getAttribute('data-ch-pipe'), b.getAttribute('data-ch-pipe-val')); };
    });
    /* 保存更新：按当前 Tab 分发到既有写入逻辑 */
    var sv = $('#chSave');
    if (sv) sv.onclick = function () {
      if (modalTab === 'progress') submitSchool(false);
      else if (modalTab === 'money') submitBiz();
      else if (modalTab === 'weekly') doParseWeekly();
      else doParse();
    };
    var nc = $('#chNoChange'); if (nc) nc.onclick = function () { submitSchool(true); };
    /* 周报 Tab（弹窗内） */
    var wp3 = $('#chWeeklyParse'); if (wp3) wp3.onclick = doParseWeekly;
    /* 「填入模板」：给一段**带 XX 占位**的骨架，业主替换成真实数字即可。
       ⚠ 占位符刻意不用数字 —— 模板没改就点识别时，不会被当成真数据写进库里。 */
    var wt = $('#chWeeklyTpl'); if (wt) wt.onclick = function () {
      var b6 = $('#chWeeklyBox'); if (!b6) return;
      if (String(b6.value || '').trim()
        && !window.confirm('文本框里已有内容，填入模板会覆盖它。继续？')) return;
      b6.value = WK_TEMPLATE;
      var d6 = $('#chWeeklyDate');
      if (d6 && !String(d6.value || '').trim()) d6.value = wkDefaultDate();
      var p6 = $('#chWeeklyPreview');
      if (p6) {
        p6.innerHTML = '<div class="ch-msg warn">已填入<b>模板</b>。请：'
          + '① 把 <b>XX</b> 换成真实数字；② 把「渠道A_B_C」「XXX」换成实际渠道与内容；'
          + '③ 把上方「<b>本期日期</b>」改成目标期（如 10.11）；再点「识别并预览」。'
          + '<br>⚠ 占位符是 <b>XX</b> 而非数字 —— 这是刻意的：'
          + '不替换就识别不出金额与渠道，免得把模板当数据写进去。</div>';
      }
    };
    var wc3 = $('#chWeeklyClear'); if (wc3) wc3.onclick = function () {
      var b4 = $('#chWeeklyBox'); if (b4) b4.value = '';
      var p4 = $('#chWeeklyPreview'); if (p4) p4.innerHTML = '';
    };
    $$('[data-ch-wkseed]').forEach(function (b) {
      b.onclick = function () {
        var b5 = $('#chWeeklyBox'); if (!b5) return;
        var seed = window.CHANNEL_WEEKLY_SEED || {};
        var hit = (seed.reports || []).filter(function (r) { return r.label === b.getAttribute('data-ch-wkseed'); })[0];
        if (!hit) return;
        b5.value = hit.text;
        var d5 = $('#chWeeklyDate');
        /* 样例自带前缀 → 日期框同步成那期，避免与上次残留的日期混淆（虽然前缀优先，但看着一致不易误判） */
        if (d5 && hit.reportDate) d5.value = (+hit.reportDate.slice(5, 7)) + '.' + (+hit.reportDate.slice(8, 10));
        doParseWeekly();
      };
    });
    var wk3 = $('#chWeeklyCommit'); if (wk3) wk3.onclick = commitWeekly;
    /* 粘贴 Tab */
    var dp = $('#chDoParse'); if (dp) dp.onclick = doParse;
    var cp = $('#chClearPaste'); if (cp) cp.onclick = function () {
      var box = $('#chPasteBox'); if (box) box.value = '';
      var pv = $('#chPreview'); if (pv) pv.innerHTML = '';
    };
    var ug = $('#chUndoImport'); if (ug) ug.onclick = undoImport;
    /* 批量录入（展开才渲染） */
    var bulk = $('#chSecBulk');
    if (bulk) bulk.addEventListener('toggle', function () {
      if (!bulk.open) return;
      var host = $('#chBulkBody');
      if (!host || host.getAttribute('data-done')) return;
      host.setAttribute('data-done', '1');
      host.innerHTML = '<div class="ch-table-wrap" style="margin-top:10px"><table class="ch-table"><thead><tr>'
        + '<th>渠道</th><th>实际收入</th><th>直接成本</th><th>工时</th></tr></thead><tbody>'
        + S.channels.map(function (c) {
          return '<tr><td>' + esc(c.name) + '</td>'
            + '<td><input class="ch-input" data-ch-bi-rev="' + esc(c.id) + '" placeholder="—"></td>'
            + '<td><input class="ch-input" data-ch-bi-cost="' + esc(c.id) + '" placeholder="—"></td>'
            + '<td><input class="ch-input" data-ch-bi-hours="' + esc(c.id) + '" placeholder="—"></td></tr>';
        }).join('') + '</tbody></table></div>'
        + '<div class="ch-actions-row"><button type="button" class="ch-btn primary" id="chSubmitBizBatch">提交变化字段</button></div>'
        + '<div id="chBulkMsg"></div>';
      var sbb = $('#chSubmitBizBatch'); if (sbb) sbb.onclick = submitBizBatch;
    });
  }

  function renderChipsNav() { return ''; }

  function renderAll(keep) {
    /* ⚠ 重渲染会重建整个 body。为了让负责人的操作不被打断，这里保留两样东西：
       ① 各 <details> 的展开状态  ② body 的滚动位置
       表单内容由「按渠道暂存的草稿」(wbDraft) 负责，切换渠道也不会丢。 */
    var det = openDetailsState();
    var sc = $('#chBody') ? $('#chBody').scrollTop : null;
    var st = computeStats();
    var adv = buildAdvice(st.rg, st);
    renderTop(st);
    var body = '';
    if (window.CHANNEL_SNAPSHOT && window.CHANNEL_SNAPSHOT.isDemo) {
      body += '<div class="ch-demo-banner">当前为<b>演示数据</b>，与真实数据隔离。清空后导入真实数据即可。</div>';
    }
    /* 按示意图组织：① 渠道成效 ② 优先行动 ③ 全部渠道 → 明细 / 设置收起在下面。
       ⚠ 主页面**不出现任何填写表单**，填写全部收敛到「更新数据」窗口。 */
    body += '<div class="ch-sec">' + renderEffect(st) + '</div>'
      + renderWeeklyRank()
      + renderWeeklyBlock()
      + '<div class="ch-sec"><div class="ch-sec-head"><div><h2>优先行动</h2>'
      + '<p>最多 3 条 · 每条含当前状态、具体原因、下一步与操作入口</p></div></div>'
      + renderAdvice(adv, st) + '</div>'
      + '<div class="ch-sec"><div class="ch-sec-head"><div><h2>全部渠道</h2>'
      + '<p>共 ' + S.channels.length + ' 个档案 · 卡片与图表、摘要、行动建议同一数据源</p></div>'
      + '<div class="ch-sec-tools"><button class="ch-mini" id="chGoPaste">粘贴到院数据</button></div></div>'
      + renderChannels(st) + '</div>'
      + '<div class="ch-sec">' + renderDetail(st) + '</div>'
      + '<div class="ch-sec"><div class="ch-sec-head"><div><h2>数据与设置</h2>'
      + '<p>在线表同步、渠道档案与归并、操作记录、数据管理</p></div></div>'
      + renderSettings(st) + '</div>';
    $('#chBody').innerHTML = body;
    restoreDetailsState(det);
    renderBrief();
    bindDynamic();
    if (sc != null) { var bd = $('#chBody'); if (bd) bd.scrollTop = sc; }
  }

  /* 重渲染前后保留 <details> 展开状态（否则每次提交都会把展开的区块收起来） */
  function openDetailsState() {
    var o = {};
    $$('#chBody details').forEach(function (d) { if (d.open && d.id) o[d.id] = 1; });
    return o;
  }
  function restoreDetailsState(o) {
    if (!o) return;
    Object.keys(o).forEach(function (id) { var d = $('#' + id); if (d) d.open = true; });
  }
  /* 重渲染前后保留 <details> 展开状态与滚动位置 */
  function openDetailsState() {
    var o = {};
    $$('#chBody details').forEach(function (d) { if (d.open && d.id) o[d.id] = 1; });
    return o;
  }
  function restoreDetailsState(o) {
    if (!o) return;
    Object.keys(o).forEach(function (id) { var d = $('#' + id); if (d) d.open = true; });
  }

  /* ---------- 渠道简报（主看板左上角，入口按钮下方一行） ----------
     需求：入口旁展示「本期渠道到院人数 / 本期实际收入 / 今日待跟进渠道数」，
     与抽屉**同一套 computeStats**。此处做成**单行紧凑**形式，
     避免在标题块里塞三张卡把标题区撑高。 */
  function renderBrief() {
    var el = $('#channelBrief');
    if (!el) return;
    var st = computeStats();
    var cut = cutoff();
    /* ⭐ 2026-10-26 修：快照重生成后已覆盖 10.1–10.25，`st` 是「本月」口径，
       原来却直接标成「本期」→ 首屏出现 489 那种既非本月也非本期的数。
       另：到院库按**原表行数**记（同指纹不合并、标「疑似重复」），
       而首页「到院登记」按**人日**（日期+姓名+电话）计 → 两者会差 11 条。
       简报是首页摘要，必须与首页同口径，故这里单独按人日重算一次。 */
    var wkFrom = weekStartOf(cut);
    var wkRg = { from: wkFrom, to: cut, days: daysBetween(wkFrom, cut) + 1, label: '' };
    var monthRg = currentRange();
    function peopleDays(rg) {
      var seen = {}, n = 0;
      S.visits.forEach(function (v) {
        if (!inRange(v.date, rg)) return;
        var k = v.date + '|' + v.name + '|' + (v.phone || '');
        if (!seen[k]) { seen[k] = 1; n++; }
      });
      return n;
    }
    var wkPeople = peopleDays(wkRg);
    var monthPeople = peopleDays(monthRg);
    var todo = S.channels.filter(function (c) {
      return c.nextActionDue && c.nextActionDue <= cut && STAGES.indexOf(stageOf(c)) < STAGES.indexOf('已开通');
    }).length;
    function item(label, val, cls) {
      return '<span class="ch-brief-cell' + (cls ? ' ' + cls : '') + '">'
        + '<i>' + label + '</i><b>' + val + '</b></span>';
    }
    el.innerHTML = item('本期渠道到院', wkPeople + '<em>人次</em>')
      + item('本月累计到院', monthPeople + '<em>人次</em>')
      + item('本期实际收入', st.revenueFilled ? (wan(st.revenue) + '<em>万</em>') : '待补齐', st.revenueFilled ? '' : 'pending')
      + item('今日待跟进', todo + '<em>个</em>', todo ? 'warn' : '')
      + '<button class="ch-brief-more" type="button" id="chBriefMore">查看渠道看板 ›</button>';
    var more = $('#chBriefMore'); if (more) more.onclick = openDrawer;
    /* 按钮上的角标 = 本期到院人次 */
    var badge = $('#channelEntry b');
    if (badge) { badge.textContent = wkPeople ? String(wkPeople) : ''; badge.style.display = wkPeople ? '' : 'none'; }
  }

  /* ============================ 10. 粘贴解析 ============================ */
  function splitLines(text) {
    return String(text || '').replace(/\r\n?/g, '\n').split('\n').filter(function (l) { return l.trim() !== ''; });
  }
  function splitCells(line, delim) {
    if (delim === '\t') return line.split('\t');
    var out = [], cur = '', q = false;
    for (var i = 0; i < line.length; i++) {
      var ch = line[i];
      if (ch === '"') { if (q && line[i + 1] === '"') { cur += '"'; i++; } else q = !q; }
      else if (ch === ',' && !q) { out.push(cur); cur = ''; }
      else cur += ch;
    }
    out.push(cur);
    return out;
  }
  function headerIdx(cells) {
    var map = {};
    var norm = cells.map(function (c) { return String(c || '').replace(/\s/g, ''); });
    for (var i = 0; i < norm.length; i++) {
      for (var k = 0; k < HDR.length; k++) {
        if (map[HDR[k]] !== undefined) continue;
        if (norm[i] === HDR[k].replace(/\//g, '').replace(/\s/g, '') || norm[i] === HDR[k]) { map[HDR[k]] = i; break; }
      }
    }
    return map;
  }
  function dateIssues(r, cut) {
    var issues = [];
    if (isBlank(r.rawDate)) { issues.push('缺就诊日期'); return issues; }
    if (!r.date) { issues.push('就诊日期无法识别「' + r.rawDate + '」（月份 / 日 / 年份越界）'); return issues; }
    /* ⚠ 年份笔误：格式合法但与数据期相差过远（本项目真实出现过 2023.10.1 写成 2026.10.1 的情况，
       也有反向的 2023 误写）。这里按「距数据期末 180 天以上、或晚于期末 7 天」判可疑。 */
    if (cut) {
      var lo = addDays(cut, -180), hi = addDays(cut, 7);
      if (r.date < lo || r.date > hi) {
        issues.push('日期「' + r.rawDate + '」与数据期（至 ' + cut + '）相差过远，疑似年份笔误');
      }
    }
    return issues;
  }
  function parsePaste(text) {
    var lines = splitLines(text);
    if (!lines.length) return { error: '没有可解析的内容' };
    var delim = lines[0].indexOf('\t') >= 0 ? '\t' : ',';
    var first = splitCells(lines[0], delim);
    var map = headerIdx(first);
    var hasHeader = Object.keys(map).length >= 3;
    var body = hasHeader ? lines.slice(1) : lines;
    if (!hasHeader) {
      /* 无表头 → 按已知列序兜底 */
      map = { '序号': 0, '就诊日期': 1, '姓名': 2, '年龄': 3, '联系方式': 4, '初/复诊': 5, '来源渠道': 6, '随访人': 7, '备注': 8 };
    }
    var rows = [];
    body.forEach(function (line, i) {
      var c = splitCells(line, delim);
      function g(k) { var ix = map[k]; return ix === undefined ? '' : String(c[ix] == null ? '' : c[ix]).trim(); }
      var vtype = g('初/复诊');
      rows.push({
        seq: g('序号'), date: normDate(g('就诊日期')),
        rawDate: g('就诊日期'),
        name: g('姓名'), age: g('年龄'), phone: g('联系方式'),
        vtype: vtype, rawChannel: g('来源渠道'), follower: g('随访人'), note: g('备注'),
        line: i + (hasHeader ? 2 : 1)
      });
    });
    return { rows: rows, hasHeader: hasHeader, delim: delim === '\t' ? '制表符' : '逗号' };
  }

  /* ========================= 10.5 渠道周报（文字识别） =========================
     业主 2026-10-10：周报是**一段自然语言**（不是表格），要能原样粘进来。
     ⚠ 三条底线（照本项目既有铁律办）：
       ① 只认业主给的**日期前缀**（9.21 / 9.28）定期，**不推断周区间** ——
          原文「本周 / 上周」在同一段里混用，推断必然出错；
       ② 周报到院人数是**按渠道汇总**、没有患者明细 ⇒ 单独作为「周报口径」区块呈现，
          **不并入到院记录库**（⛔ 绝不为了让数字好看而虚构患者记录来凑数）；
       ③ 明细合计与文中声明的合计**对不上就明说**，不四舍五入抹平。
     ========================================================================== */
  var CN_NUM = { '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10 };
  function cn2num(v) {
    var s2 = String(v == null ? '' : v).trim();
    if (/^\d+$/.test(s2)) return +s2;
    if (CN_NUM[s2] != null) return CN_NUM[s2];
    var m = s2.match(/^十(.)$/); if (m) return 10 + (CN_NUM[m[1]] || 0);
    m = s2.match(/^(.)十(.)$/); if (m) return (CN_NUM[m[1]] || 0) * 10 + (CN_NUM[m[2]] || 0);
    return null;
  }
  /* 单位名后缀：只认这些（不靠「猜」把普通词当渠道） */
  var UNIT_SUFFIX = '卫生服务中心|卫生室|卫生院|服务中心|医院|诊所|幼儿园|大学|学院|高中|职高|初中|中学|附中|附小|小学|一小|二小|三小|四小|五小|六小|七小|八小|中心';
  /* 前导动词 → 分隔符：否则「重点开拓新桥医院」会整段被当成渠道名 */
  var LEAD_VERB = /对接|拜访|沟通|开拓|推进|拓展|开发|新增|签约|落地|洽谈|走访|联系|维护|稳定|稳固|涵盖|包括|涉及|跟进|持续|重点/g;
  /* ⛔⛔ 2026-10-10 修：原先是**单字字符类**，其中含「新」（来自「新增」）——
     结果把「**新**桥医院」整条当成动词词头误杀（实测 9.28 周报漏掉该渠道）。
     改成**多字词**匹配：只有出现完整的动词/虚词才算噪声，不会误伤「新X」「开X」这类真名。 */
  var VERB_CHAR = /(对接|拜访|沟通|开拓|推进|拓展|开发|新增|签约|落地|洽谈|走访|联系|维护|稳定|稳固|涵盖|包括|涉及|跟进|持续|重点|我们|方面|内容|事项|相关|工作|计划|目前|已经|同时|继续|提升|增加|储备|筛选|衔接|保障|运转)/;
  function weeklyClean(t) {
    return String(t || '')
      .replace(LEAD_VERB, '|')
      .replace(/[了的]/g, '|')
      .replace(/[「」“”"'（）()【】\[\]]/g, ' ');
  }
  function extractUnits(flat) {
    var clean = weeklyClean(flat);
    var re = new RegExp('([\\u4e00-\\u9fa5]{2,10}?(?:' + UNIT_SUFFIX + '))', 'g');
    var out = [], m;
    while ((m = re.exec(clean))) {
      var v = m[1];
      /* 再兜一层：仍含动词字的一律丢弃（宁可漏，也不要造出「开拓新桥医院」这种假名） */
      if (v.length < 2 || v.length > 10 || VERB_CHAR.test(v)) continue;
      if (out.indexOf(v) < 0) out.push(v);
    }
    return out;
  }
  /* 解析一段周报文字（纯函数，便于核对与复算） */
  /* ⭐⭐⭐ 2026-10-11：识别周报开头的「期」。
     业主给的**粘贴模版**是「<b>9.28日本周，</b>K教授这周转诊12人…」——
     旧实现只认 `9.28:`（冒号结尾），这个格式**一个字都认不出来**（label 为空、写入置灰）。

     兼容这几种写法（均返回 {label:'9.28', date:'2026-09-28'}）：
       9.28:  ·  9.28：  ·  9.28日本周，  ·  9.28日本周:  ·  9.28（本周），  ·  9月28日，
     ⚠ 只在**前 40 个字符**里找：既容错「粘的时候前面多带了几个字」（如「以下为粘贴模版。」），
        又不会误配正文深处的日期。
     ⚠ 必须带**分隔标记**（标点 或 「日本周/上周」等）才算前缀 ——
        否则「10.1到10.7」这类区间写法会被误当为期。 */
  function detectPeriodPrefix(flat) {
    var head = String(flat || '').slice(0, 40);
    /* ① 日期 + [日/号] + [（本周）] + **标点** */
    var re1 = /(\d{1,2})\s*[.\-\/月]\s*(\d{1,2})\s*(?:日|号)?\s*(?:[（(]?\s*(?:本周|上周|当周|该周|这周)\s*[）)]?)?\s*[:：,，、；;]/;
    /* ② 日期 + [日/号] + **周标记**（无标点也算） */
    var re2 = /(\d{1,2})\s*[.\-\/月]\s*(\d{1,2})\s*(?:日|号)?\s*[（(]?\s*(?:本周|上周|当周|该周|这周)\s*[）)]?/;
    var m = head.match(re1) || head.match(re2);
    if (!m) return null;
    var label = (+m[1]) + '.' + (+m[2]);
    var d = normDate(label);
    return d ? { label: label, date: d } : null;
  }

  /* ⭐⭐ 2026-10-11：`optDate` 是**兜底期日期**。
     ⚠ 业务员给的周报**天然没有日期前缀**（正文直接从「K教授这周转诊12人」开始），
       原先强制要求 `^9.28:` 这类前缀 → 这类文本只能落成「未标期」、且写入按钮置灰。
     规则：**文本自带前缀 → 以文本为准**；没有 → 用 optDate（弹窗里「本期日期」）。 */
  function parseWeekly(text, optDate) {
    var t = String(text || '').replace(/\r\n?/g, '\n');
    var flat = t.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim();
    var out = {
      text: t, label: '', date: '', dateFrom: '',
      referred: null, arrived: null, convRate: null,
      openedChannels: null, totalArrived: null, visitedCount: null,
      perChannel: [], detailSum: 0, mismatch: null,
      units: [], green: [], pending: [], plans: []
    };
    if (!flat) return out;

    /* ---- 期：优先取文本前缀（9.28: / 9.28日本周， / 9月28日，…）；没有则用兜底日期 ---- */
    var pp = detectPeriodPrefix(flat);
    if (pp) {
      out.label = pp.label;
      out.date = pp.date;
      out.dateFrom = 'text';
    } else {
      var od = String(optDate == null ? '' : optDate).trim();
      var odFull = od ? normDate(od) : null;
      if (odFull) {
        out.date = odFull;
        out.label = (+odFull.slice(5, 7)) + '.' + (+odFull.slice(8, 10));
        out.dateFrom = 'input';
      }
    }

    function num(pat) { var m = flat.match(pat); return m ? +m[1] : null; }
    out.referred = num(/转诊\s*(\d+)\s*人/);
    out.arrived = num(/实际到院\s*(\d+)\s*人/);
    var cm = flat.match(/转化率\s*([\d.]+)\s*%/); if (cm) out.convRate = +cm[1];
    out.openedChannels = num(/(?:开通|开通了)\s*(\d+)\s*条/);
    out.totalArrived = num(/合计到院\s*(\d+)\s*人/);
    out.visitedCount = num(/(?:累计)?拜访(?:沟通)?\s*(\d+)\s*位/);

    /* ---- 各渠道到院明细：**只在「具体数据：…」段里找** ----
       ⚠ 不全文扫 —— 否则「转诊 12 人 / 到院 8 人 / 合计到院 44 人」会被当成渠道行。 */
    var seg = flat.match(/具体数据\s*[:：]?\s*([^。]*)/);
    if (seg) {
      seg[1].split(/[，,、;；]/).forEach(function (p) {
        var m = p.match(/^\s*([A-Za-z\u4e00-\u9fa5][A-Za-z0-9\u4e00-\u9fa5]{0,11}?)\s*(\d+|[一二三四五六七八九十两])\s*人\s*$/);
        if (!m) return;
        var cnt = cn2num(m[2]);
        if (cnt == null) return;
        out.perChannel.push({ raw: m[1].trim(), count: cnt });
      });
    }
    out.perChannel.forEach(function (x) { out.detailSum += x.count; });
    out.mismatch = (out.totalArrived != null && out.perChannel.length) ? (out.totalArrived - out.detailSum) : null;

    /* ---- 提到的单位（用于建档）---- */
    out.units = extractUnits(flat);

    /* ---- 绿色通道进展：学校名 + 阶段关键词 ---- */
    (function () {
      var re = new RegExp('([\\u4e00-\\u9fa5]{2,10}?(?:' + UNIT_SUFFIX + '))', 'g');
      var clean = weeklyClean(flat), m, seen = {};
      while ((m = re.exec(clean))) {
        var name = m[1];
        if (VERB_CHAR.test(name) || seen[name]) continue;
        var isSch = /(小学|中学|初中|高中|幼儿园|附小|附中|一小|二小|三小|四小|五小|六小|七小|八小)/.test(name);
        if (!isSch) continue;
        var stage = '';
        if (/(已洽谈完|洽谈完毕|正式签约|预计.{0,6}签约|签约落地|待签)/.test(flat)) stage = '待签约';
        else if (/(初步达成|达成合作意向)/.test(flat)) stage = '沟通中';
        if (stage) { seen[name] = 1; out.green.push({ name: name, stage: stage }); }
      }
    })();

    /* ---- 计划 / 下一步 ---- */
    (function () {
      /* ⚠ 捕获到「。」为止（**不能停在「；」**）—— 否则「A；B」里的 B 会被整段丢掉。
         分条放到后面按「；」拆，主次关系才对。 */
      var re = /(?:后续计划|下一步工作|下一步|后续我[们]?|后续)[:：，,]?\s*([^。]+)/g, m;
      while ((m = re.exec(flat))) {
        m[1].split(/[；;]/).forEach(function (s2) {
          s2 = s2.replace(/^[，,\s]*(?:我[们]?)?(?:会|将|要)?/, '').replace(/[。\s]+$/, '').trim();
          if (s2.length > 3 && out.plans.indexOf(s2) < 0) out.plans.push(s2);
        });
      }
    })();

    /* ---- 文中提及但**无法建档**的个人 / 代码（不臆造档案，交负责人确认）---- */
    (function () {
      var m, re = /([A-Za-z]{1,4})\s*教授/g;
      while ((m = re.exec(flat))) { if (out.pending.indexOf(m[1] + '教授') < 0) out.pending.push(m[1] + '教授'); }
      if (/大学城的教授/.test(flat) && out.pending.indexOf('大学城的教授') < 0) out.pending.push('大学城的教授');
      out.pending = out.pending.filter(function (p) { return out.units.indexOf(p) < 0; });
    })();

    return out;
  }

  /* ⭐⭐ 粘贴模板（业主 2026-10-11 给的格式）。
     ⚠ 只用于界面「填入模板」按钮 —— **不进 CHANNEL_WEEKLY_SEED**：
        seed 里放的是**有真实来源的原文**，模板是空骨架，混进去就会被当成一期数据解析。
     ⚠ 占位符用「XX」而不用数字：防止「模板没改就点识别」时被当成真数据写进库里。 */
  var WK_TEMPLATE = '10.11日本周，K教授这周转诊XX人，实际到院XX人，转化率XX%。 '
    + '目前我们一共开通XX条外部渠道，本周各渠道合计到院XX人。'
    + '具体数据：渠道A_X人、渠道B_X人、渠道C_X人。 '
    + '渠道拜访方面，本周已经对接拜访了XXX。'
    + '后续我会持续维护所有现有渠道，保持稳定联系，同时重点开拓XXX。 '
    + '绿色通道方面，XXX。 '
    + '下一步工作，我会XXX。';

  /* 「本期日期」默认值 = 今天（业务员周报按发出日归档，比按数据末日更贴近实际） */
  function wkDefaultDate() {
    var t = todayYmd();
    return (+t.slice(5, 7)) + '.' + (+t.slice(8, 10));
  }

  /* ---------- 周报预览（弹窗内） ---------- */
  function weeklyMetricsHTML(rec) {
    function cell(k, v) {
      return '<div class="ch-wk-cell"><i>' + k + '</i><b>' + (v == null ? '未提及' : esc(String(v))) + '</b></div>';
    }
    return '<div class="ch-wk-metrics">'
      + cell('转诊', rec.referred == null ? null : rec.referred + ' 人')
      + cell('实际到院', rec.arrived == null ? null : rec.arrived + ' 人')
      + cell('转化率', rec.convRate == null ? null : rec.convRate + '%')
      + cell('已开通渠道', rec.openedChannels == null ? null : rec.openedChannels + ' 条')
      + cell('各渠道合计到院', rec.totalArrived == null ? null : rec.totalArrived + ' 人')
      + cell('拜访沟通', rec.visitedCount == null ? null : rec.visitedCount + ' 位')
      + '</div>';
  }
  function weeklyPreviewHTML(rec, errs) {
    var mx = 0;
    rec.perChannel.forEach(function (x) { if (x.count > mx) mx = x.count; });
    var bars = rec.perChannel.map(function (x) {
      return '<div class="ch-wk-bar"><label>' + esc(x.raw) + '</label>'
        + '<span class="ch-wk-track"><i style="width:' + (mx ? Math.max(4, Math.round(x.count / mx * 100)) : 0) + '%"></i></span>'
        + '<b>' + x.count + ' 人</b></div>';
    }).join('');
    var h = '<div class="ch-msg ' + (errs.length ? 'bad' : 'good') + '">'
      + (errs.length ? ('⚠ ' + esc(errs.join('；'))) : ('识别到周报「<b>' + esc(rec.label || '未标期') + '</b>」'
        + (rec.dateFrom === 'input'
          ? '（文本<b>没有</b>日期前缀，按「本期日期」归档）'
          : (rec.dateFrom === 'text' ? '（日期取自文本前缀）' : ''))
        + (/\d{1,2}\s*[.月]\s*\d{1,2}\s*日?\s*[:：][\s\S]*\d{1,2}\s*[.月]\s*\d{1,2}\s*日?\s*[:：]/.test(rec.text)
          ? '（⚠ 文本里出现<b>两个以上</b>日期前缀，只按第一个归属；请拆成单期再粘）' : '')))
      + '：单位为 <b>' + rec.units.length + '</b> 个、渠道明细 <b>' + rec.perChannel.length + '</b> 条'
      + (rec.perChannel.length ? '（合计 ' + rec.detailSum + ' 人）' : '')
      + '、计划 <b>' + rec.plans.length + '</b> 条。'
      + '<br>⚠ 周报到院是<b>渠道汇总口径</b>，无患者明细 → 只进「周报口径」区块，'
      + '<b>不并入到院记录库</b>；也不会虚构成患者记录。</div>';
    h += weeklyMetricsHTML(rec);
    if (rec.mismatch != null && rec.mismatch !== 0) {
      h += '<div class="ch-msg warn"><b>勾稽不一致</b>：明细合计 <b>' + rec.detailSum + ' 人</b>，'
        + '但文中声明合计到院 <b>' + rec.totalArrived + ' 人</b>，差 <b>'
        + (rec.mismatch > 0 ? '+' : '') + rec.mismatch + ' 人</b>。'
        + '两个数都按原文保留、不做抹平，请负责人核对源周报。</div>';
    }
    if (bars) h += '<div class="ch-wk-bars"><h4>各渠道到院（周报明细）</h4>' + bars + '</div>';
    if (rec.units.length) {
      h += '<div class="ch-wk-chips"><h4>识别到的单位（将建档 / 归类）</h4>'
        + rec.units.map(function (u) {
          var t = guessType(u) || '待归类';
          return '<span class="ch-wk-chip">' + esc(u) + '<em>' + esc(t) + '</em></span>';
        }).join('') + '</div>';
    }
    if (rec.green.length) {
      h += '<div class="ch-wk-chips"><h4>绿色通道进展</h4>'
        + rec.green.map(function (g) {
          return '<span class="ch-wk-chip">' + esc(g.name) + '<em>' + esc(g.stage) + '</em></span>';
        }).join('') + '</div>';
    }
    if (rec.pending.length) {
      h += '<div class="ch-wk-chips"><h4>文中提及、但未建档（交你确认）</h4>'
        + rec.pending.map(function (p) { return '<span class="ch-wk-chip muted">' + esc(p) + '</span>'; }).join('')
        + '<div class="ch-hint">这些人 / 代码无法判断是不是渠道，系统<b>不擅自建档</b>。</div></div>';
    }
    if (rec.plans.length) {
      h += '<div class="ch-wk-plans"><h4>下一步计划（原文摘录）</h4><ul>'
        + rec.plans.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul></div>';
    }
    return h;
  }

  var pendingWeekly = null;
  function doParseWeekly() {
    var box = $('#chWeeklyBox');
    var host = $('#chWeeklyPreview');
    if (!host) return;
    var text = box ? box.value : '';
    if (!String(text).trim()) { host.innerHTML = '<div class="ch-msg bad">请先粘贴周报文字。</div>'; return; }
    /* ⭐ 2026-10-11：业务员原文**没有日期前缀**，所以日期可以从「本期日期」字段兜底 */
    var dBox = $('#chWeeklyDate');
    var rec = parseWeekly(text, dBox ? dBox.value : '');
    rec.id = 'w' + hash((rec.date || rec.label || '') + '|wk');
    var errs = [];
    if (!rec.date) {
      errs.push('未识别到日期：文本没有日期前缀，且「本期日期」为空或不合法（应形如 10.11 或 2026-10-11）');
    }
    if (!rec.units.length && !rec.perChannel.length) errs.push('未识别到任何单位或渠道明细');
    pendingWeekly = { rec: rec };

    /* ---- 写前防错：同期覆盖 / 与其他期内容雷同 ---- */
    var extra = '';
    if (rec.date) {
      if (S.weekly.some(function (w) { return w.date === rec.date; })) {
        extra += '<div class="ch-msg warn">该期（<b>' + esc(rec.label) + '</b>）<b>已存在</b>，'
          + '确认写入会<b>覆盖</b>原记录（同期不累积）。</div>';
      }
      var twin = S.weekly.filter(function (w) {
        return w.date !== rec.date && w.perChannel.length
          && w.perChannel.length === rec.perChannel.length
          && w.totalArrived === rec.totalArrived
          && w.perChannel.every(function (x, i) {
            return x.raw === rec.perChannel[i].raw && x.count === rec.perChannel[i].count;
          });
      })[0];
      if (twin) {
        extra += '<div class="ch-msg warn">本期各渠道明细与「<b>' + esc(twin.label) + '</b>」期<b>完全相同</b>'
          + '（渠道与人数逐条一致），请确认不是<b>误贴上一期</b>；确认无误则正常写入。</div>';
      }
    }

    host.innerHTML = weeklyPreviewHTML(rec, errs) + extra
      + '<div class="ch-actions-row"><button type="button" class="ch-submit" id="chWeeklyCommit"'
      + (rec.date && (rec.units.length || rec.perChannel.length) ? '' : ' disabled') + '>确认写入周报</button></div>';
    bindDynamic();
  }
  function commitWeekly() {
    if (!pendingWeekly) return;
    var rec = pendingWeekly.rec;
    var before = S.channels.length;
    /* 建档：只对**识别出的单位**建，不臆测 */
    rec.units.forEach(function (u) {
      var c = ensureChannel(u);
      if (!c) return;
      var t = guessType(u);
      if (!c.type && t) c.type = t;
      if (!c.createdAt) c.createdAt = rec.date || cutoff();
    });
    /* 绿色通道阶段：只**向前**推进，不回退已在更后面的阶段 */
    rec.green.forEach(function (g) {
      var c = findChannel(g.name);
      if (!c) return;
      if (STAGES.indexOf(g.stage) < 0) return;
      if (STAGES.indexOf(stageOf(c)) < STAGES.indexOf(g.stage)) { c.stage = g.stage; c.stageAt = rec.date || cutoff(); }
    });
    touchWeeklyChannels(rec);
    /* 周报本体：同期替换（重复录入同一期不累积） */
    if (rec.date) S.weekly = S.weekly.filter(function (w) { return w.date !== rec.date; });
    S.weekly.push(rec);
    S.weekly.sort(function (a, b) { return String(a.date || '') < String(b.date || '') ? -1 : 1; });
    logAct('渠道周报录入', '期 ' + (rec.label || '—') + ' · 新建渠道 ' + (S.channels.length - before) + ' 个');
    save();
    pendingWeekly = null;
    renderAll(true);
    var host = $('#chWeeklyPreview');
    if (host) {
      host.innerHTML = '<div class="ch-msg good">周报「<b>' + esc(rec.label || '') + '</b>」已写入。'
        + '新增渠道档案 <b>' + (S.channels.length - before) + '</b> 个；'
        + '周报口径数据已上板（<b>不计入</b>到院记录库，故不会与登记表统计重复）。</div>';
    }
    var bx = $('#chWeeklyBox'); if (bx) bx.value = '';
    bindDynamic();
  }

  /* ---------- 主面板：周报口径区块 ---------- */
  function renderWeeklyBlock() {
    if (!S.weekly.length) return '';
    var cards = S.weekly.slice().reverse().map(function (w) {
      var mx = 0; w.perChannel.forEach(function (x) { if (x.count > mx) mx = x.count; });
      var bars = w.perChannel.map(function (x) {
        return '<div class="ch-wk-bar"><label>' + esc(x.raw) + '</label>'
          + '<span class="ch-wk-track"><i style="width:' + (mx ? Math.max(4, Math.round(x.count / mx * 100)) : 0) + '%"></i></span>'
          + '<b>' + x.count + '</b></div>';
      }).join('');
      var mis = (w.mismatch != null && w.mismatch !== 0)
        ? '<div class="ch-msg warn">勾稽：明细合计 <b>' + w.detailSum + '</b> ≠ 声明合计 <b>' + w.totalArrived
          + '</b>，差 <b>' + (w.mismatch > 0 ? '+' : '') + w.mismatch + ' 人</b>（均按原文保留）</div>' : '';
      return '<article class="ch-wk-card">'
        + '<header><b>周报 ' + esc(w.label || '未标期') + '</b>'
        + '<span class="ch-wk-src">文字识别 · ' + esc(w.date || '日期未识别') + '</span></header>'
        + weeklyMetricsHTML(w)
        + (bars ? '<div class="ch-wk-bars"><h4>各渠道到院（周报明细）</h4>' + bars + '</div>' : '')
        + mis
        + (w.units.length ? '<div class="ch-wk-chips"><h4>本期对接单位</h4>'
          + w.units.map(function (u) { return '<span class="ch-wk-chip">' + esc(u) + '</span>'; }).join('') + '</div>' : '')
        + (w.green.length ? '<div class="ch-wk-chips"><h4>绿色通道</h4>'
          + w.green.map(function (g) { return '<span class="ch-wk-chip">' + esc(g.name) + '<em>' + esc(g.stage) + '</em></span>'; }).join('') + '</div>' : '')
        + (w.plans.length ? '<div class="ch-wk-plans"><h4>下一步</h4><ul>'
          + w.plans.slice(0, 3).map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ul></div>' : '')
        + '</article>';
    }).join('');
    return '<div class="ch-sec ch-wk-sec"><div class="ch-sec-head"><div><h2>渠道周报（文字识别）</h2>'
      + '<p>共 ' + S.weekly.length + ' 期 · 数据来自周报文字，属<b>渠道汇总口径（无患者明细）</b>，'
      + '与「渠道成效」「全部渠道」的到院记录<b>分别统计、互不重复累计</b></p></div>'
      + '<div class="ch-sec-tools"><button class="ch-mini" id="chGoWeekly">粘贴文字周报</button></div></div>'
      + '<div class="ch-wk-grid">' + cards + '</div></div>';
  }

  /* 周报 → 渠道副作用（建档 / 阶段推进 / 推进记录）。
     ⭐ 抽成共用函数：**内置周报与手工粘贴走同一条路** —— 两处各写一份的话，
        迟早出现「手工录入有时序线、内置的没有」这种不一致。 */
  function touchWeeklyChannels(rec) {
    var touched = rec.units.concat(rec.green.map(function (g) { return g.name; }))
      .filter(function (x, i, a) { return x && a.indexOf(x) === i; });
    touched.forEach(function (u) {
      var c = findChannel(u); if (!c) return;
      var dup = S.progress.some(function (p) {
        return p.src === 'weekly' && p.channelId === c.id && p.date === (rec.date || cutoff());
      });
      if (dup) return;                       /* 同期同渠道不重复写记录 */
      /* 推进记录是**叙述性**的，不是患者数据 —— 结构与 submitSchool 一致，时间线才能读 */
      S.progress.unshift({
        id: 'p' + hash(c.id + '|wk|' + (rec.date || rec.label) + '|' + Date.now()),
        channelId: c.id, date: rec.date || cutoff(),
        actions: [], stage: '',
        nextAction: rec.plans[0] || '',
        nextFollowUp: '', contact: '', contactTitle: '',
        newInquiry: '', coverage: '', blocker: '', support: '',
        note: '渠道周报（' + (rec.label || '未标期') + '）录入'
          + (rec.plans.length ? '：' + rec.plans[0] : ''),
        noChange: false, owner: OWNER_DEFAULT, src: 'weekly',
        createdAt: new Date().toISOString()
      });
      c.lastPushAt = rec.date || c.lastPushAt || '';
    });
  }

  /* ---------- 内置两期周报（业主微信文字，原文见 channel-weekly.js） ---------- */
  function seedWeekly() {
    var seed = window.CHANNEL_WEEKLY_SEED;
    if (!seed || !seed.reports || !seed.reports.length) return 0;
    var added = 0;
    seed.reports.forEach(function (r) {
      /* ⭐ 2026-10-11：内置期也可能**不带日期前缀**（业主原文如此），故传 reportDate 兜底 */
      var rec = parseWeekly(r.text, r.reportDate);
      if (!rec.date) return;
      if (S.weekly.some(function (w) { return w.date === rec.date; })) return;
      rec.id = 'w' + hash(rec.date + '|wk');
      rec.fromSeed = true;
      rec.enteredAt = new Date().toISOString();
      /* 建档（不臆测类型：能判的按 guessType，判不出保持「待归类」） */
      rec.units.forEach(function (u) {
        var c = ensureChannel(u);
        if (c && !c.type) { var t = guessType(u); if (t) c.type = t; }
        if (c && !c.createdAt) c.createdAt = rec.date;
      });
      rec.green.forEach(function (g) {
        var c = findChannel(g.name);
        if (c && STAGES.indexOf(g.stage) >= 0 && STAGES.indexOf(stageOf(c)) < STAGES.indexOf(g.stage)) {
          c.stage = g.stage; c.stageAt = rec.date;
        }
      });
      touchWeeklyChannels(rec);            /* 与手工录入同一套副作用 */
      S.weekly.push(rec);
      added++;
    });
    if (added) {
      S.weekly.sort(function (a, b) { return String(a.date || '') < String(b.date || '') ? -1 : 1; });
      logAct('内置周报载入', '载入 ' + added + ' 期渠道周报（文字识别，' + (seed.source || '') + '）');
    }
    return added;
  }

  var pendingPreview = null;
  function doParse() {
    var box = $('#chPasteBox');
    var text = box ? box.value : '';
    var out = parsePaste(text);
    var host = $('#chPreview');
    if (out.error) { host.innerHTML = '<div class="ch-msg bad">' + esc(out.error) + '</div>'; return; }

    var byId = visitIndex();
    var plan = [], cnt = { new: 0, upd: 0, dup: 0, bad: 0 };
    var batchFp = {};
    var cut = cutoff();
    out.rows.forEach(function (r) { var f = [r.date, r.name, r.rawChannel, r.vtype].join('|'); batchFp[f] = (batchFp[f] || 0) + 1; });

    out.rows.forEach(function (r) {
      var issues = dateIssues(r, cut);
      if (isBlank(r.name)) issues.push('缺姓名');
      if (isBlank(r.rawChannel)) issues.push('缺来源渠道');
      if (r.vtype && VTYPES.indexOf(r.vtype) < 0) issues.push('初/复诊取值异常「' + r.vtype + '」');
      var fp = [r.date, r.name, r.rawChannel, r.vtype].join('|');
      if (batchFp[fp] > 1) issues.push('同批内疑似重复（保留，交负责人确认）');
      var kind, note = '';
      if (issues.length) { kind = 'bad'; cnt.bad++; }
      else {
        var ch = findChannel(r.rawChannel);
        var id = 'v' + hash([r.date, r.name, ch ? ch.id : r.rawChannel, r.vtype].join('|'));
        if (byId[id]) { kind = (byId[id].src || []).indexOf('paste') >= 0 ? 'dup' : 'upd'; cnt[kind]++; }
        else { kind = 'new'; cnt.new++; }
      }
      r._kind = kind; r._issues = issues;
      plan.push(r);
    });

    pendingPreview = { plan: plan, cnt: cnt, meta: out };
    var label = { new: '<span class="ch-badge new">新增</span>', upd: '<span class="ch-badge upd">更新</span>', dup: '<span class="ch-badge dup">重复（跳过）</span>', bad: '<span class="ch-badge bad">异常</span>' };
    var h = '<div class="ch-msg ' + (cnt.bad ? 'warn' : 'good') + '">识别到 <b>' + out.rows.length + '</b> 行'
      + '（' + out.delim + (out.hasHeader ? ' · 含表头' : ' · 无表头，按默认列序') + '）：'
      + '新增 <b>' + cnt.new + '</b>、更新 <b>' + cnt.upd + '</b>、重复 <b>' + cnt.dup + '</b>、异常 <b>' + cnt.bad + '</b>。'
      + '确认后写入；重复与异常不会重复累计。</div>'
      + '<div class="ch-preview"><table><thead><tr><th>行</th><th>状态</th><th>就诊日期</th><th>姓名</th><th>初/复诊</th><th>来源渠道</th><th>随访人</th><th>说明</th></tr></thead><tbody>'
      + plan.slice(0, 60).map(function (r) {
        var cls = r._kind === 'new' ? 'row-new' : (r._kind === 'bad' ? 'row-bad' : (r._kind === 'dup' ? 'row-dup' : ''));
        return '<tr class="' + cls + '"><td>' + r.line + '</td><td>' + label[r._kind] + '</td>'
          + '<td class="mono">' + esc(r.rawDate || '—') + '</td><td>' + esc(maskName(r.name) || '—') + '</td>'
          + '<td>' + esc(r.vtype || '—') + '</td><td>' + esc(r.rawChannel || '—') + '</td><td>' + esc(r.follower || '—') + '</td>'
          + '<td style="font-size:11px;color:#8b5450">' + esc(r._issues.join('；') || '—') + '</td></tr>';
      }).join('')
      + '</tbody></table></div>'
      + (plan.length > 60 ? '<div class="ch-hint">仅预览前 60 行，实际按 ' + plan.length + ' 行处理。</div>' : '')
      + '<div class="ch-actions-row"><button class="ch-submit" id="chCommit"' + (cnt.new + cnt.upd + cnt.dup ? '' : ' disabled') + '>确认写入（'
      + (cnt.new + cnt.upd + cnt.dup) + ' 行有效）</button>'
      + (cnt.bad ? '<button class="ch-submit sec" id="chCommitValidOnly">先写入有效行，' + cnt.bad + ' 行异常留待核对</button>' : '')
      + '</div>'
      /* ⚠ 撤销按钮**只在写入之后**出现（写入前没有可撤销的东西） */
      + (cnt.bad ? '<div class="ch-tocheck"><h3>待核对 ' + cnt.bad + ' 条</h3><ul class="ch-check-list">'
        + plan.filter(function (r) { return r._kind === 'bad'; }).slice(0, 40).map(function (r) {
          return '<li><span>第 ' + r.line + ' 行 · ' + esc(r.name || '(无名)') + ' / ' + esc(r.rawDate || '(无日期)') + ' / ' + esc(r.rawChannel || '(无渠道)') + '</span>'
            + '<b>' + esc(r._issues.join('；')) + '</b></li>';
        }).join('') + '</ul><div class="ch-hint">异常行不会写入统计；修正源数据后重新粘贴即可。</div></div>' : '');
    host.innerHTML = h;
    bindDynamic();
  }

  var lastImportSnapshot = null;
  function commitImport(validOnly) {
    if (!pendingPreview) return;
    var badRows = pendingPreview.plan.filter(function (r) { return r._kind === 'bad'; });
    var rows = pendingPreview.plan.filter(function (r) { return r._kind === 'new' || r._kind === 'upd'; });
    /* ⚠⚠ 撤销必须**连渠道档案一起回退**：mergeVisits 会为新的来源渠道自动建档，
       只恢复 visits 会留下「到院 0 人」的幽灵渠道（实测撤销后渠道从 22 变 24）。
       这里记录导入前已存在的渠道 id，撤销时只删「本次新建且已无任何引用」的。 */
    var beforeIds = {};
    S.channels.forEach(function (c) { beforeIds[c.id] = 1; });
    var snapVisits = JSON.parse(JSON.stringify(S.visits));
    lastImportSnapshot = { visits: snapVisits, newChannelIds: [] };
    var res = mergeVisits(rows.map(function (r) {
      return { seq: r.seq, date: r.date, name: r.name, age: r.age, phone: r.phone, vtype: r.vtype, rawChannel: r.rawChannel, follower: r.follower, note: r.note };
    }), 'paste');
    lastImportSnapshot.newChannelIds = S.channels.filter(function (c) { return !beforeIds[c.id]; })
      .map(function (c) { return c.id; });
    logAct('粘贴导入', '新增 ' + res.added + '、更新 ' + res.dup + '、异常 ' + badRows.length);
    save();
    pendingPreview = null;
    renderAll(true);
    var host = $('#chPreview');
    if (host) {
      host.innerHTML = '<div class="ch-msg good">写入完成：新增 <b>' + res.added + '</b> 条、重叠合并 <b>' + res.dup
        + '</b> 条、异常 <b>' + badRows.length + '</b> 条未写入。所有指标已重算。'
        + (res.conflicts.length ? ('<br>字段冲突 ' + res.conflicts.length + ' 处：'
          + res.conflicts.slice(0, 5).map(function (c) { return c.field + ' 「' + esc(c.oldVal) + '」→「' + esc(c.newVal) + '」'; }).join('；')
          + '（已保留原值，未静默覆盖）') : '')
        + '<div class="ch-actions-row"><button class="ch-submit sec" id="chUndoImport">撤销本次导入</button></div></div>'
        /* ⚠ 写入后原来会把待核对清单整段冲掉 → 负责人看不到「哪几行没进去」。
           现在保留下来，方便照着源表修正后重粘。 */
        + (badRows.length ? ('<div class="ch-tocheck"><h3>待核对 ' + badRows.length + ' 条（未写入）</h3><ul class="ch-check-list">'
          + badRows.slice(0, 40).map(function (r) {
            return '<li><span>第 ' + r.line + ' 行 · ' + esc(r.name || '(无名)') + ' / ' + esc(r.rawDate || '(无日期)') + ' / ' + esc(r.rawChannel || '(无渠道)') + '</span>'
              + '<b>' + esc(r._issues.join('；')) + '</b></li>';
          }).join('') + '</ul><div class="ch-hint">这些行不会写入统计；修正源数据后重新粘贴即可。</div></div>') : '');
    }
    var keep = $('#chPasteBox');
    if (keep) keep.value = '';
    bindDynamic();
  }
  function undoImport() {
    if (!lastImportSnapshot) return;
    S.visits = lastImportSnapshot.visits;
    /* 清掉本次导入顺手建的空渠道档案；若该渠道已被收益/推进引用则保留 */
    var removed = 0;
    lastImportSnapshot.newChannelIds.forEach(function (id) {
      var used = S.visits.some(function (v) { return v.channelId === id; })
        || S.money.some(function (m) { return m.channelId === id; })
        || S.progress.some(function (p) { return p.channelId === id; });
      if (!used) { S.channels = S.channels.filter(function (c) { return c.id !== id; }); removed++; }
    });
    lastImportSnapshot = null;
    logAct('撤销导入', '恢复到导入前的到院记录，并清理 ' + removed + ' 个本次新建的空渠道');
    save(); renderAll();
    var host = $('#chPreview');
    if (host) host.innerHTML = '<div class="ch-msg warn">已撤销本次导入（含 ' + removed + ' 个本次新建的空渠道档案），统计已重算。</div>';
    bindDynamic();
  }

  /* ============================ 11. 在线表同步 ============================ */
  function doSync() {
    var urlEl = $('#chSyncUrl');
    var url = urlEl ? urlEl.value.trim() : '';
    S.sync.url = url;
    var msgEl = $('#chSecSync .ch-msg');
    function report(cls, txt) {
      S.sync.status = (cls === 'good' ? 'ok' : (cls === 'bad' ? 'fail' : 'unconfigured'));
      S.sync.lastErr = (cls === 'good' ? '' : txt);
      S.sync.lastAt = new Date().toLocaleString('zh-CN', { hour12: false }).slice(0, 16);
      if (msgEl) { msgEl.className = 'ch-msg ' + cls; msgEl.innerHTML = txt; }
      save();
    }
    if (!url) { report('warn', '待连接 —— 请先填写在线表链接'); return; }
    report('warn', '正在尝试同步…');
    /* 浏览器直连在线表：跨域 + 登录态限制，几乎必然失败。
       这里**如实报错**，不伪造成功，也不写入任何模拟数据。 */
    fetch(url, { mode: 'cors', credentials: 'omit' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
      })
      .then(function (t) {
        var out = parsePaste(t);
        if (out.error || !out.rows || !out.rows.length) {
          report('bad', '同步失败：返回内容不是表格数据（可能是登录页）。跨域与登录态限制需服务端中转。');
          return;
        }
        var res = mergeVisits(out.rows.filter(function (r) { return r.date && r.name; })
          .map(function (r) {
            return { seq: r.seq, date: r.date, name: r.name, age: r.age, phone: r.phone, vtype: r.vtype, rawChannel: r.rawChannel, follower: r.follower, note: r.note };
          }), 'online');
        S.sync.lastAdded = res.added; S.sync.lastUpdated = res.dup;
        report('good', '同步成功：新增 ' + res.added + ' 条、更新 ' + res.dup + ' 条');
        save(); renderAll();
      })
      .catch(function (e) {
        report('bad', '同步失败：' + esc(e.message || String(e))
          + '。<br>浏览器无法直连在线表（跨域 + 未授权）。两种可用方式：'
          + '① 用上方「复制粘贴更新」；② 由服务端中转接口拉取后再写入。');
      });
  }

  /* ============================ 12. 今日更新 ============================ */
  function msg(sel, cls, txt) {
    var el = $(sel);
    if (el) el.innerHTML = '<div class="ch-msg ' + cls + '">' + txt + '</div>';
  }
  function submitSchool(noChange) {
    var id = ($('#chSCh') || {}).value;
    if (!id) { msg('#chSchoolMsg', 'bad', '请先选择渠道 / 学校'); return; }
    var c = channelById(id);
    if (!c) { msg('#chSchoolMsg', 'bad', '渠道不存在'); return; }
    var date = normDate(($('#chSDate') || {}).value) || cutoff();
    var acts = $$('#chSActs input:checked').map(function (x) { return x.value; });
    var stage = ($('#chSStage') || {}).value;
    var rec = {
      id: 'p' + hash(c.id + '|' + date + '|' + Date.now()),
      channelId: c.id, date: date,
      actions: noChange ? [] : acts,
      stage: noChange ? '' : stage,
      nextAction: ($('#chSNext') || {}).value || '',
      nextFollowUp: normDate(($('#chSDue') || {}).value) || '',
      contact: ($('#chSContact') || {}).value || '',
      contactTitle: ($('#chSTitle') || {}).value || '',
      newInquiry: ($('#chSInquiry') || {}).value || '',
      coverage: ($('#chSCover') || {}).value || '',
      blocker: ($('#chSBlock') || {}).value || '',
      support: ($('#chSSupport') || {}).value || '',
      note: ($('#chSNote') || {}).value || '',
      noChange: !!noChange,
      owner: OWNER_DEFAULT,
      createdAt: new Date().toISOString()
    };
    S.progress.unshift(rec);                            // 只增，不覆盖既往
    c.lastPushAt = date;
    if (rec.actions.length) c.lastAction = rec.actions.join(' / ');
    if (noChange) c.lastAction = '今日无新增进展';
    if (rec.stage && rec.stage !== c.stage) {
      if (STAGE_TERMINAL.indexOf(rec.stage) >= 0 && !rec.blocker) {
        /* 暂停/终止需要原因 */
        msg('#chSchoolMsg', 'bad', '选择「' + rec.stage + '」时必须填写原因（在「当前阻碍」里说明）');
        S.progress.shift();
        return;
      }
      c.stage = rec.stage; c.stageAt = date;
    }
    if (rec.nextAction) c.nextAction = rec.nextAction;
    if (rec.nextFollowUp) c.nextActionDue = rec.nextFollowUp;
    /* 已有通道开展新活动时不把合作阶段退回初始状态 */
    if (STAGES.indexOf(c.stage) >= STAGES.indexOf('已开通') && rec.actions.length && !rec.stage) {
      c.keepStage = true;
    }
    if (rec.contact) { c.contact = rec.contact; c.contactTitle = rec.contactTitle || c.contactTitle; }
    logAct('学校通道更新', c.name + ' · ' + date + (noChange ? '（无新增进展）' : '：' + (acts.join('、') || '—')));
    clearWbDraft(c.id);
    save(); renderAll(true);
    msg('#chSchoolMsg', 'good', '已记录 ' + esc(c.name) + ' 的 ' + shortMd(date) + ' 进展' + (noChange ? '（今日无新增进展）' : '') + '，历史时间线已保留。');
  }
  /* 弹窗内「建档并切换」：名称必填；名称已存在则复用不重复建档。
     ⚠ 与 addChannelManual（档案区那个）的区别：本函数建档后**自动切换**到新渠道，
       且停留在当前 Tab，方便「新学校 → 立刻记录进展」一气呵成。
     ⚠ 不臆测类型：留空时走 guessType()，判不出就保持「待归类」。 */
  function createChannelInline() {
    var host = $('#chNewPickMsg');
    var nm = (($('#chNewPickName') || {}).value || '').trim();
    var tp = (($('#chNewPickType') || {}).value || '').trim();
    if (!nm) {
      if (host) host.innerHTML = '<div class="ch-msg bad">请填写学校 / 渠道名称。</div>';
      var f = $('#chNewPickName'); if (f) f.focus();
      return;
    }
    /* 已存在 → 复用，不重复建档（避免「双福三小」建出两条档案） */
    var exist = findChannel(nm);
    if (exist) {
      if (!exist.type) { var t0 = guessType(nm); if (t0) exist.type = t0; }
      save();
      logAct('切换渠道', nm + '（已存在，未重复建档）');
      openUpdate(exist.id, modalTab);
      return;
    }
    var c = ensureChannel(nm);
    if (!c) {
      if (host) host.innerHTML = '<div class="ch-msg bad">建档失败，请重试。</div>';
      return;
    }
    c.type = tp || guessType(nm) || '';        /* 判不出＝待归类，不臆测 */
    if (!c.createdAt) c.createdAt = cutoff();
    logAct('新建渠道（更新窗口）', nm + '（' + (c.type || '待归类') + '）');
    save();
    openUpdate(c.id, modalTab);
  }

  /* 手动建档：名称必填；类型留空则按 guessType 判定（判不出＝待归类，不臆测） */
  function addChannelManual() {
    var nm = (($('#chNewName') || {}).value || '').trim();
    var tp = (($('#chRegNewType') || {}).value || '').trim();
    var host = $('#chRegAddMsg');
    if (!nm) { if (host) host.innerHTML = '<div class="ch-msg bad">请填写渠道 / 学校名称。</div>'; return; }
    var already = findChannel(nm);
    if (already) { if (host) host.innerHTML = '<div class="ch-msg warn">「' + esc(nm) + '」已存在（' + esc(already.type || '待归类') + '），未重复建档。</div>'; return; }
    var c = ensureChannel(nm);
    if (!c) return;
    c.type = tp || guessType(nm) || '';
    c.createdAt = cutoff();
    logAct('手动建档', nm + '（' + (c.type || '待归类') + '）');
    save(); renderAll(true);
    var h2 = $('#chRegAddMsg');
    if (h2) h2.innerHTML = '<div class="ch-msg good">已建档：' + esc(nm) + '（' + esc(c.type || '待归类') + '）。</div>';
  }
  /* 去重（保持原顺序）—— 用于建议值列表 */
  function uni(a) {
    var o = [];
    (a || []).forEach(function (x) { if (x && o.indexOf(x) < 0) o.push(x); });
    return o;
  }
  function createSchool() {
    var nm = ($('#chNewName') || {}).value.trim();
    if (!nm) { msg('#chSchoolMsg', 'bad', '请填写学校名称'); return; }
    if (findChannel(nm)) { msg('#chSchoolMsg', 'warn', '已存在同名渠道，已直接选用'); }
    var c = ensureChannel(nm);
    c.type = '学校绿色通道';
    c.owner = ($('#chNewOwner') || {}).value.trim() || OWNER_DEFAULT;
    c.area = ($('#chNewArea') || {}).value.trim();
    c.stage = '待联系';
    c.createdAt = cutoff();
    c.isNew = c.createdAt >= ROUND_START ? true : false;
    c.newBasis = '建立日期 ' + c.createdAt + (c.isNew ? '，晚于本轮工作起点 ' + ROUND_START : '，早于本轮工作起点 ' + ROUND_START);
    c.nextAction = '首次联系';
    c.nextActionDue = addDays(cutoff(), 3);
    logAct('新建学校通道', c.name + '（' + (c.area || '地区待补') + '）· ' + (c.isNew ? '新渠道' : '既往渠道'));
    save(); renderAll(true);
    msg('#chSchoolMsg', 'good', '已新建学校通道「' + esc(c.name) + '」，可按「今日更新」逐日推进。');
  }
  function submitBiz() {
    var id = ($('#chBCh') || {}).value;
    if (!id) { msg('#chBizMsg', 'bad', '请先选择渠道'); return; }
    var scope = ($('#chBScope') || {}).value || 'day';
    var from = normDate(($('#chBFrom') || {}).value) || cutoff();
    var to = normDate(($('#chBTo') || {}).value) || from;
    var rev = ($('#chBRev') || {}).value;
    var cost = ($('#chBCost') || {}).value;
    var hours = ($('#chBHours') || {}).value;
    if (isBlank(rev) && isBlank(cost) && isBlank(hours)) { msg('#chBizMsg', 'bad', '至少填写一项（收入 / 成本 / 工时）'); return; }
    var r = upsertMoney({
      channelId: id, scope: scope, date: from, periodFrom: from, periodTo: scope === 'period' ? to : from,
      revenue: isBlank(rev) ? null : n(rev), cost: isBlank(cost) ? null : n(cost),
      hours: isBlank(hours) ? null : n(hours),
      proof: ($('#chBProof') || {}).value || '',
      bizNext: ($('#chBBiz') || {}).value || ''
    });
    var c = channelById(id);
    if (r.updated && ($('#chBBiz') || {}).value) c.nextAction = ($('#chBBiz') || {}).value;
    logAct('效益更新', (c ? c.name : id) + ' · ' + (scope === 'period' ? (from + '—' + to) : from)
      + '：收入 ' + (isBlank(rev) ? '待补齐' : yuan(rev)) + '、成本 ' + (isBlank(cost) ? '待补齐' : yuan(cost)));
    clearWbDraft(id);
    save(); renderAll(true);
    msg('#chBizMsg', 'good', r.updated ? '已更新同一条记录（未重复累计），统计已重算。' : '已新增记录，统计已重算。');
  }
  /* 重复提交 → 更新对应记录；否则追加 */
  function upsertMoney(rec) {
    var key = rec.channelId + '|' + rec.scope + '|' + (rec.scope === 'period' ? (rec.periodFrom + '~' + rec.periodTo) : rec.date);
    for (var i = 0; i < S.money.length; i++) {
      var m = S.money[i];
      var mk = m.channelId + '|' + m.scope + '|' + (m.scope === 'period' ? (m.periodFrom + '~' + m.periodTo) : m.date);
      if (mk === key) {
        m.revenue = rec.revenue; m.cost = rec.cost; m.hours = rec.hours;
        m.proof = rec.proof; m.bizNext = rec.bizNext;
        m.updatedAt = new Date().toISOString();
        return { updated: true, rec: m };
      }
    }
    rec.id = 'm' + hash(key);
    rec.createdAt = rec.updatedAt = new Date().toISOString();
    S.money.push(rec);
    return { updated: false, rec: rec };
  }
  function submitBizBatch() {
    var scope = ($('#chBulkScope') || {}).value || 'day';
    var from = normDate(($('#chBulkFrom') || {}).value) || cutoff();
    var to = normDate(($('#chBulkTo') || {}).value) || from;
    var cnt = 0;
    $$('[data-ch-bi-rev]').forEach(function (el) {
      var id = el.getAttribute('data-ch-bi-rev');
      var rev = el.value, cost = ($('[data-ch-bi-cost="' + id + '"]') || {}).value, hours = ($('[data-ch-bi-hours="' + id + '"]') || {}).value;
      if (isBlank(rev) && isBlank(cost) && isBlank(hours)) return;
      upsertMoney({
        channelId: id, scope: scope, date: from, periodFrom: from, periodTo: scope === 'period' ? to : from,
        revenue: isBlank(rev) ? null : n(rev), cost: isBlank(cost) ? null : n(cost), hours: isBlank(hours) ? null : n(hours),
        proof: '', bizNext: ''
      });
      cnt++;
    });
    logAct('批量效益更新', '更新 ' + cnt + ' 个渠道 · ' + (scope === 'period' ? (from + '—' + to) : from));
    save(); renderAll(true);
    msg('#chBulkMsg', cnt ? 'good' : 'warn', cnt ? ('已提交 ' + cnt + ' 个渠道的变化字段，统计已重算。') : '没有检测到变化字段，未提交。');
  }

  /* ============================ 13. 归并 ============================ */
  function mergeChannel(fromId) {
    var other = S.channels.filter(function (c) { return c.id !== fromId; });
    if (!other.length) { alert('没有其他渠道可归并'); return; }
    var target = prompt('把该渠道归并到哪个渠道？（输入渠道名）\n可选：\n' + other.map(function (c) { return '· ' + c.name; }).join('\n'));
    if (!target) return;
    var to = findChannel(target.trim());
    if (!to) { alert('未找到渠道：' + target); return; }
    var src = channelById(fromId);
    if (!to) return;
    if (!confirm('确认把「' + src.name + '」归并到「' + to.name + '」？\n归并后历史到院与收益按渠道ID重新归属，统计会同步重算。')) return;
    /* 别名归并：保留原名进别名，记录数改挂到目标渠道 */
    src.aliases.concat(src.rawNames).forEach(function (a) { if (to.aliases.indexOf(a) < 0 && a !== to.name) to.aliases.push(a); });
    S.visits.forEach(function (v) { if (v.channelId === src.id) v.channelId = to.id; });
    S.money.forEach(function (m) { if (m.channelId === src.id) m.channelId = to.id; });
    S.progress.forEach(function (p) { if (p.channelId === src.id) p.channelId = to.id; });
    S.channels = S.channels.filter(function (c) { return c.id !== src.id; });
    logAct('渠道归并', src.name + ' → ' + to.name);
    save(); renderAll();
  }

  /* ============================ 14. 交互绑定 ============================ */
  function bindDynamic() {
    /* 顶部关闭按钮由 renderTop() 注入 → 每次渲染后重新绑定 */
    var cc = $('#chClose'); if (cc) cc.onclick = closeDrawer;
    /* ---- 顶部工具栏：更新数据 / 粘贴入口 ---- */
    var ou = $('#chOpenUpdate'); if (ou) ou.onclick = function () { openUpdate(null, 'progress'); };
    var gp = $('#chGoPaste'); if (gp) gp.onclick = function () { openUpdate(null, 'paste'); };
    /* ---- 渠道成效：口径切换 ---- */
    $$('[data-ch-eff]').forEach(function (b) {
      b.onclick = function () { effKey = b.getAttribute('data-ch-eff'); renderAll(true); };
    });
    /* ---- 双自然周排名：口径切换 ---- */
    $$('[data-ch-wkrank]').forEach(function (b) {
      b.onclick = function () { wkRankKey = b.getAttribute('data-ch-wkrank'); renderAll(true); };
    });
    /* 「补录收益」：跳到第一个待补齐的渠道（没有则第一个渠道） */
    var fl = $('[data-ch-fill]');
    if (fl) fl.onclick = function () {
      var st0 = computeStats();
      var miss = st0.channels.filter(function (r) { return !r.hasRevenue; })
        .sort(function (a, b) { return b.visits - a.visits; })[0];
      openUpdate(miss ? miss.ch.id : null, 'money');
    };
    /* ---- 全部渠道：搜索 / 筛选 ----
       ⚠⚠ 不要用闭包里的 `cs` 读值：每次 renderAll 都会重新执行 bindDynamic 并把
       同名变量指向新节点，旧 handler 存活时会读到 null → 抛错且**搜索词写不进去**。
       统一用事件对象的 target，计时器也放模块级。 */
    var cs = $('#chFltSearch');
    if (cs) {
      cs.oninput = function (ev) {
        var el = (ev && ev.target) || $('#chFltSearch');
        if (!el) return;
        fltSearch = el.value;
        clearTimeout(srchTimer);
        srchTimer = setTimeout(function () {
          renderAll(true);
          var e2 = $('#chFltSearch');
          if (e2) { e2.focus(); try { e2.setSelectionRange(e2.value.length, e2.value.length); } catch (e) {} }
        }, 200);
      };
    }
    $$('[data-ch-flt]').forEach(function (b) {
      b.onclick = function () { fltKey = b.getAttribute('data-ch-flt'); renderAll(true); };
    });
    /* ---- 渠道卡「更新」：带入该渠道并打开窗口 ---- */
    $$('[data-ch-upd]').forEach(function (b) {
      b.onclick = function (e) {
        e.stopPropagation();
        openUpdate(b.getAttribute('data-ch-upd'), b.getAttribute('data-ch-tab') || 'progress');
      };
    });
    /* ---- 行动卡的阶段 pipeline（窗口内）由 bindModal 处理，这里不重复绑 ---- */
    /* 区间 */
    $$('#chRanges button').forEach(function (b) {
      b.onclick = function () {
        state.range = b.getAttribute('data-ch-range');
        var c = $('#chCustom'); if (c) c.hidden = state.range !== 'custom';
        renderAll();
      };
    });
    var apply = $('#chApplyCustom');
    if (apply) apply.onclick = function () {
      state.customFrom = ($('#chFrom') || {}).value || '';
      state.customTo = ($('#chTo') || {}).value || '';
      renderAll();
    };
    /* 排序 */
    /* 打开渠道详情 */
    $$('[data-ch-open]').forEach(function (b) {
      b.onclick = function () { openChannelDetail(b.getAttribute('data-ch-open')); };
    });
    /* 学校卡「一键更新」→ 打开更新窗口并带入该渠道 */
    $$('[data-ch-quick]').forEach(function (b) {
      b.onclick = function () { openUpdate(b.getAttribute('data-ch-quick'), 'progress'); };
    });
    /* 档案编辑 */
    $$('[data-ch-type]').forEach(function (el) {
      el.onchange = function () {
        var c = channelById(el.getAttribute('data-ch-type'));
        if (!c) return;
        c.type = el.value;
        if (isSchool(c) && !c.stage) { c.stage = '待联系'; c.stageAt = cutoff(); }
        logAct('渠道归类', c.name + ' → ' + (el.value || '待归类'));
        save(); renderAll();
      };
    });
    $$('[data-ch-new]').forEach(function (el) {
      el.onchange = function () {
        var c = channelById(el.getAttribute('data-ch-new'));
        if (!c) return;
        c.isNew = el.value === '' ? null : (el.value === '1');
        c.newBasis = '人工确认于 ' + cutoff() + (c.isNew === true ? '（新渠道）' : (c.isNew === false ? '（既往渠道）' : '（待确认）'));
        logAct('新/既往分类', c.name + ' → ' + (el.value === '' ? '待确认' : (el.value === '1' ? '新渠道' : '既往渠道')));
        save(); renderAll();
      };
    });
    $$('[data-ch-owner]').forEach(function (el) {
      el.onchange = function () {
        var c = channelById(el.getAttribute('data-ch-owner'));
        if (c) { c.owner = el.value; save(); }
      };
    });
    $$('[data-ch-stage]').forEach(function (el) {
      el.onchange = function () {
        var c = channelById(el.getAttribute('data-ch-stage'));
        if (!c) return;
        c.stage = el.value; c.stageAt = cutoff();
        logAct('阶段变更', c.name + ' → ' + el.value);
        save(); renderAll();
      };
    });
    $$('[data-ch-merge]').forEach(function (b) {
      b.onclick = function () { mergeChannel(b.getAttribute('data-ch-merge')); };
    });
    /* 今日更新 */
    var ss = $('#chSubmitSchool'); if (ss) ss.onclick = function () { submitSchool(false); };
    var sn = $('#chNoChange'); if (sn) sn.onclick = function () { submitSchool(true); };
    var cs = $('#chCreateSchool'); if (cs) cs.onclick = createSchool;
    var sb = $('#chSubmitBiz'); if (sb) sb.onclick = submitBiz;
    var sbb = $('#chSubmitBizBatch'); if (sbb) sbb.onclick = submitBizBatch;
    /* 粘贴 */
    var dp = $('#chDoParse'); if (dp) dp.onclick = doParse;
    var cp = $('#chClearPaste'); if (cp) cp.onclick = function () { $('#chPasteBox').value = ''; $('#chPreview').innerHTML = ''; };
    /* ---- 周报：主面板入口（在面板里，故留在 bindDynamic） ---- */
    var gw = $('#chGoWeekly'); if (gw) gw.onclick = function () { openUpdate(null, 'weekly'); };
    /* ⚠⚠ 弹窗内的按钮（识别 / 清空 / 载入内置）**必须在 bindModal 里绑** ——
       bindDynamic 只在 renderAll（主面板）后调用，弹窗渲染后不会走它，
       写在这里会「看着绑了、实际永远绑不上」（本轮实测：点载入内置没反应）。 */
    var wk2 = $('#chWeeklyCommit'); if (wk2) wk2.onclick = commitWeekly;
    /* ---- 新增渠道（可手动建档，学校 / 机构不断在新增） ---- */
    var ra2 = $('#chRegAdd'); if (ra2) ra2.onclick = addChannelManual;
    var ci = $('#chCommit'); if (ci) ci.onclick = function () { commitImport(false); };
    var cv = $('#chCommitValidOnly'); if (cv) cv.onclick = function () { commitImport(true); };
    var ug = $('#chUndoImport'); if (ug) ug.onclick = undoImport;
    /* 同步 */
    var ds = $('#chDoSync'); if (ds) ds.onclick = doSync;
    var svs = $('#chSaveSync'); if (svs) svs.onclick = function () {
      S.sync.url = ($('#chSyncUrl') || {}).value || '';
      save(); alert('已保存在线表配置。未配置授权时状态仍为「待连接」。');
    };
    var ops = $('#chOpenSource'); if (ops) ops.onclick = function () {
      var u = ($('#chSyncUrl') || {}).value || (window.CHANNEL_SNAPSHOT || {}).sourceUrl;
      if (u) window.open(u, '_blank', 'noopener');
    };
    /* 数据管理 */
    var rv = $('#chReveal'); if (rv) rv.onclick = function () {
      if (!state.revealIdentity && !confirm('查看完整患者身份需要相应权限，并会留下操作记录。确认继续？')) return;
      state.revealIdentity = !state.revealIdentity;
      logAct(state.revealIdentity ? '查看完整身份（已开启）' : '恢复脱敏');
      save(); renderAll();
    };
    var ex = $('#chExport'); if (ex) ex.onclick = function () {
      var blob = new Blob([JSON.stringify(S, null, 2)], { type: 'application/json' });
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = 'channel-dashboard-' + cutoff() + '.json'; a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      logAct('导出数据', 'JSON');
    };
    var ij = $('#chImportJson'); if (ij) ij.onclick = function () {
      var i = document.createElement('input'); i.type = 'file'; i.accept = '.json,application/json';
      i.onchange = function () {
        var f = i.files[0]; if (!f) return;
        var rd = new FileReader();
        rd.onload = function () {
          try {
            var o = JSON.parse(rd.result);
            if (!o || o.v !== 1) throw new Error('格式不匹配');
            S = o; save(); renderAll(); alert('导入成功');
          } catch (e) { alert('导入失败：' + e.message); }
        };
        rd.readAsText(f);
      };
      i.click();
    };
    var ra = $('#chResetAll'); if (ra) ra.onclick = function () {
      if (!confirm('将清空渠道看板本地数据（渠道档案 / 到院记录 / 推进记录 / 收益）。此操作不可恢复，确认？')) return;
      if (!confirm('再次确认：清空后需重新导入数据。')) return;
      S = blankState(); save(); renderAll();
    };
  }

  /* 渠道详情（含时间线） */
  function openChannelDetail(id) {
    var c = channelById(id); if (!c) return;
    var rg = currentRange();
    var st = computeStats(rg);
    var r = null;
    st.channels.forEach(function (x) { if (x.ch.id === id) r = x; });
    var tl = S.progress.filter(function (p) { return p.channelId === id; })
      .sort(function (a, b) { return b.date < a.date ? -1 : 1; });
    var moneylist = S.money.filter(function (m) { return m.channelId === id; })
      .sort(function (a, b) { return (b.updatedAt || '') < (a.updatedAt || '') ? -1 : 1; });
    var body = ''
      + '<div class="ch-msg">' + (c.type ? esc(c.type) : '<b>类型待归类</b>') + ' · '
      + (c.isNew === true ? '新渠道' : (c.isNew === false ? '既往渠道' : '<b>新/既往待确认</b>')) + ' · '
      + '负责人 ' + esc(c.owner || '—') + (stageLabel(c) ? ' · 阶段 ' + esc(stageLabel(c)) : '')
      + (c.newBasis ? '<br>' + esc(c.newBasis) : '') + '</div>'
      + '<div class="ch-rcard-grid" style="margin:11px 0">'
      + '<div class="ch-rcard-cell"><label>到院人次</label><b>' + (r ? r.visits : 0) + '</b></div>'
      + '<div class="ch-rcard-cell"><label>初诊</label><b>' + (r ? r.first : 0) + '</b></div>'
      + '<div class="ch-rcard-cell"><label>实际收入</label><b' + (r && r.hasRevenue ? '' : ' class="pending"') + '>' + (r && r.hasRevenue ? yuan(r.revenue) + ' 元' : '待补齐') + '</b></div>'
      + '<div class="ch-rcard-cell"><label>直接成本</label><b' + (r && r.cost != null ? '' : ' class="pending"') + '>' + (r && r.cost != null ? yuan(r.cost) + ' 元' : '待补齐') + '</b></div>'
      + '<div class="ch-rcard-cell"><label>渠道贡献</label><b' + (r && r.contribution != null ? '' : ' class="pending"') + '>' + (r && r.contribution != null ? yuan(r.contribution) + ' 元' : '待补齐') + '</b></div>'
      + '</div>'
      + '<div class="ch-sec-head"><div><h2>推进时间线</h2><p>按进展日期，只增不改</p></div></div>'
      + (tl.length ? '<div class="ch-timeline">' + tl.map(function (p) {
        return '<div class="ch-tl-item"><time>' + p.date + ' · ' + esc(p.owner || '') + '</time>'
          + '<div class="ch-tl-body">'
          + (p.noChange ? '<b>今日无新增进展</b>' : '<b>' + esc((p.actions || []).join(' / ') || '—') + '</b>')
          + (p.stage ? ' · 阶段→' + esc(p.stage) : '')
          + (p.newInquiry ? ' · 新增咨询/转介 ' + esc(p.newInquiry) + ' 人' : '')
          + (p.coverage ? ' · 覆盖 ' + esc(p.coverage) + ' 人' : '')
          + (p.nextAction ? '<br>下一步：' + esc(p.nextAction) : '')
          + (p.nextFollowUp ? '（' + p.nextFollowUp + '）' : '')
          + (p.blocker ? '<br>阻碍：' + esc(p.blocker) : '')
          + (p.support ? '<br>需要支持：' + esc(p.support) : '')
          + (p.note ? '<br>' + esc(p.note) : '')
          + '</div></div>';
      }).join('') + '</div>' : '<div class="ch-empty">暂无推进记录</div>')
      + '<div class="ch-sec-head" style="margin-top:14px"><div><h2>收益记录</h2></div></div>'
      + (moneylist.length ? '<div class="ch-table-wrap"><table class="ch-table"><thead><tr>'
        + '<th>期间</th><th>口径</th><th>收入</th><th>成本</th><th>工时</th><th>更新于</th></tr></thead><tbody>'
        + moneylist.map(function (m) {
          return '<tr><td>' + (m.scope === 'period' ? (m.periodFrom + '—' + m.periodTo) : m.date) + '</td>'
            + '<td>' + (m.scope === 'period' ? '期间汇总' : '逐笔') + '</td>'
            + '<td>' + (m.revenue == null ? '待补齐' : yuan(m.revenue)) + '</td>'
            + '<td>' + (m.cost == null ? '待补齐' : yuan(m.cost)) + '</td>'
            + '<td>' + (m.hours == null ? '—' : m.hours) + '</td>'
            + '<td style="font-size:11px;color:#8b91a3">' + esc(String(m.updatedAt || '').slice(0, 16).replace('T', ' ')) + '</td></tr>';
        }).join('') + '</tbody></table></div>' : '<div class="ch-empty">暂无收益记录（到院人数由登记表自动计算）</div>');
    var host = document.getElementById('chDetailHost');
    host.innerHTML = '<div class="ch-drawer-sub"><div class="ch-top-row" style="padding:13px 18px 0">'
      + '<div class="ch-top-title"><button class="ch-btn" id="chDetailBack">‹ 返回</button>'
      + '<h1 style="color:#12243D;font-size:15px">' + esc(c.name) + '</h1></div>'
      + '<button class="ch-close" id="chDetailClose" style="border-color:#dfe4ef;background:#fff;color:#5f6678">×</button></div>'
      + '<div class="ch-details-body">' + body + '</div></div>';
    host.hidden = false;
    var db = $('#chDetailBack'); if (db) db.onclick = function () { host.hidden = true; };
    var dc = $('#chDetailClose'); if (dc) dc.onclick = function () { host.hidden = true; };
  }

  /* ============================ 15. 外壳 ============================ */
  function buildShell() {
    if ($('#channelDrawer')) return;
    var d = document.createElement('section');
    d.className = 'ch-drawer'; d.id = 'channelDrawer';
    d.setAttribute('role', 'dialog'); d.setAttribute('aria-modal', 'true'); d.setAttribute('aria-label', '渠道看板');
    d.innerHTML = '<div class="ch-shell"><header class="ch-top" id="chTop"></header>'
      + '<div class="ch-body" id="chBody"></div>'
      + '<div id="chModalHost" class="ch-modal-host" hidden></div>'
      + '<div id="chDetailHost" hidden style="position:absolute;inset:0;background:#F5F8F6;overflow-y:auto"></div></div>';
    document.body.appendChild(d);
    /* ⚠ 只绑「不依赖内部动态 HTML」的处理器：
       #chClose 由 renderTop() 注入，必须等渲染后再绑（见 bindDynamic）。 */
    d.addEventListener('click', function (e) { if (e.target === d) closeDrawer(); });
    /* 更新窗口：点遮罩空白处关闭 */
    var mh = $('#chModalHost');
    if (mh) mh.addEventListener('click', function (e) { if (e.target === mh) closeUpdate(); });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || !d.classList.contains('show')) return;
      var mh = $('#chModalHost');
      if (mh && !mh.hidden) { closeUpdate(); return; }
      var h = $('#chDetailHost');
      if (h && !h.hidden) { h.hidden = true; return; }
      closeDrawer();
    });
  }
  function openDrawer() {
    buildShell();
    $('#channelDrawer').classList.add('show');
    document.body.style.overflow = 'hidden';
    renderAll();
  }
  function closeDrawer() {
    closeUpdate();
    var d = $('#channelDrawer'); if (d) d.classList.remove('show');
    var h = $('#chDetailHost'); if (h) h.hidden = true;
    document.body.style.overflow = '';
  }

  /* 在主看板**左上角**（.title-row 标题块内）挂入口 + 单行简报。
     ⚠⚠ 为什么挂在标题块**内部**：`september-report.js` 的 `pinToTop()` 会强制把
     `#sepReport` 挪成 `.title-row` 的 `nextElementSibling` —— 任何插在 `.title-row`
     与 `#sepReport` 之间的节点都会被推到最后面去。所以入口与简报必须放进标题块里。
     ⚠ 与营销面板解耦：不再挂 `.mkt-actions` / `.mkt-top`（业主 2026-10-08 要求独立入口）。
     ⚠ `month-dashboard.js` 只会改写 h1 / .subtitle 的 **textContent**，不会重建这两个槽，
       所以挂进去的按钮不会被月面板的 mount/rerender 冲掉。 */
  function wireEntry() {
    var slot = document.getElementById('channelEntrySlot');
    if (slot && !document.getElementById('channelEntry')) {
      var b = document.createElement('button');
      b.id = 'channelEntry'; b.className = 'ch-entry';
      b.type = 'button'; b.title = '打开渠道看板（渠道推进 / 到院 / 收益）';
      b.innerHTML = '<i>◉</i><span>渠道看板</span><b></b>';
      b.onclick = openDrawer;
      slot.appendChild(b);
    }
    var bs = document.getElementById('channelBriefSlot');
    if (bs && !document.getElementById('channelBrief')) {
      var s = document.createElement('div');
      s.className = 'ch-brief'; s.id = 'channelBrief';
      bs.appendChild(s);
    }
  }

  /* ============================ 16. 启动 ============================ */
  function boot() {
    /* ⚠ 启动流程分步 try：任一步出问题都不能连累入口挂载与重试
       （实测首轮 renderAll 抛错 → 后面的重挂定时器整段没注册 → 入口消失） */
    try { load(); seedFromSnapshot(); seedWeekly(); } catch (e) { window.__CH_ERR = 'load:' + (e && e.message); }
    try { buildShell(); } catch (e) { window.__CH_ERR = 'shell:' + (e && e.message); }
    wireEntry();
    /* ⚠ 重试定时器必须**先注册**、renderAll 之后只做兜底：
       标题块内的两个槽在静态 HTML 里，但 month-dashboard.js 会在 load 后接管页面，
       多试几次确保槽存在时一定挂上。 */
    [0, 300, 900, 1800, 3200].forEach(function (t) {
      setTimeout(function () { wireEntry(); renderBrief(); }, t);
    });
    window.addEventListener('ops:core-refresh', function () { wireEntry(); renderBrief(); });
    window.addEventListener('september-revenue-updated', function () { renderBrief(); });
    /* 兜底：任何点击后若发现入口被别的模块重渲染冲掉，就地补挂（开销极小） */
    document.addEventListener('click', function () {
      if (!document.getElementById('channelEntry') || !document.getElementById('channelBrief')) {
        wireEntry(); renderBrief();
      }
    }, true);
    try { renderAll(); }
    catch (e) {
      window.__CH_ERR = 'render:' + (e && e.message) + ' @ ' + String(e && e.stack || '').split('\n')[1];
      console.error('[渠道看板] 首次渲染失败', e);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  /* 对外只读接口（供其它模块复用同一套口径） */
  window.CHANNEL_DASHBOARD = {
    open: openDrawer, close: closeDrawer,
    stats: function (rg) { return computeStats(rg || currentRange()); },
    cutoff: cutoff,
    snapshot: function () { return window.CHANNEL_SNAPSHOT; },
    state: function () { return { channels: S.channels.length, visits: S.visits.length, progress: S.progress.length, money: S.money.length, weekly: S.weekly.length }; },
    parseWeekly: parseWeekly,
    weekly: function () { return S.weekly; }
  };
})();
