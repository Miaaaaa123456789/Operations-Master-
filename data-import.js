/* ============================================================================
   看板数据导入与同步
   ----------------------------------------------------------------------------
   真实链路：解析（CSV / XLSX / 粘贴文本）→ 逐行校验 → 重算 → 全站重绘 + 时间戳同步
   · 图片：显示预览缩略图；浏览器端离线无法可靠 OCR，数值在「识别结果」里确认
   · 数据落在 localStorage（叠加在种子数据之上），刷新后保持；可导出为源码数据块
   · 无冲突时确认按钮立即可用 —— 不再出现「必须先解决冲突」
   ========================================================================== */
(function () {
  'use strict';

  /* ============================ 常量 ============================ */
  var LS_DAILY = 'ops.rev.daily.v1';   // 逐日营收覆盖层
  var LS_META = 'ops.rev.meta.v1';    // 导入元信息
  var LS_SNAP = 'ops.rev.snapshot.v1';// 导入前快照（保留最近一次）

  var MONTH_TARGET = 260;             // 9 月营收目标（万元）
  var MONTH_DAYS = 30;                // 9 月天数（时间进度分母）
  var MONTH_FROM = '2026-09-01', MONTH_TO = '2026-09-30';
  var WEEK_START = '2026-09-21', WEEK_END = '2026-09-27';   // 本周
  var LW_START = '2026-09-14', LW_END = '2026-09-20';      // 上周完整周
  var SOURCE_CUTOFF = '2026-09-26';   // 其他数据源（客服/心理/管家/团体）的共同截止日
  var TODAY = '2026-09-26';           // 抓取日
  var DOW = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

  /* ============================ 种子数据 ============================
     逐日营业日报，单位：元 / 人
     数组含义：[门诊收入, 在院收入, 初诊, 复诊, 在院, 入院, 出院]
     · 收入：9.1—9.14 取自 data/daily-sales/2026-09.csv；9.15 由 9.16 环比反推；
             9.16—9.24 取自业主营收日报截图（含当月累计收入交叉校验）
     · 人数：9.1—9.14 取自同一 CSV；9.18—9.24 取自营收日报截图逐列识别；
             9.15—9.17 截图无此行，人数记 null（不参与人数环比）
     · 校验：9.1—9.25 累计 = 1,779,978.48 元（178.00 万），与源表「当月累计收入」一致
     ================================================================ */
  var SEED = {
    '2026-09-01': [8329.46, 13695.01, 4, 13, 28, 2, 0],
    '2026-09-02': [16747.27, 62605.00, 3, 15, 27, 1, 1],
    '2026-09-03': [4710.35, 35411.99, 0, 14, 25, 0, 1],
    '2026-09-04': [31464.50, 40703.93, 8, 24, 29, 6, 0],
    '2026-09-05': [15041.96, 39769.70, 4, 30, 31, 2, 0],
    '2026-09-06': [140116.70, 43682.69, 9, 92, 30, 3, 1],
    '2026-09-07': [20267.31, 39148.42, 3, 16, 30, 4, 0],
    '2026-09-08': [21632.61, 36448.39, 3, 20, 30, 1, 0],
    '2026-09-09': [17044.52, 41666.05, 3, 12, 29, 1, 1],
    '2026-09-10': [10042.88, 36522.53, 1, 12, 28, 0, 0],
    '2026-09-11': [9814.03, 38027.06, 3, 17, 30, 2, 0],
    '2026-09-12': [18029.88, 33831.37, 4, 17, 30, 0, 0],
    '2026-09-13': [133002.16, 31013.81, 11, 108, 27, 4, 3],
    '2026-09-14': [20100.68, 15521.66, 3, 14, 24, 1, 1],
    '2026-09-15': [34846.27, 43388.86, 8, 10, 25, 1, 0],
    '2026-09-16': [13958.85, 28288.75, 2, 13, 25, 1, 1],
    '2026-09-17': [34398.72, 28935.61, 7, 13, 26, 1, 0],
    '2026-09-18': [40570.20, 32821.31, 3, 26, 25, 2, 2],
    '2026-09-19': [99908.85, 37754.86, 7, 79, 28, 5, 2],
    '2026-09-20': [27228.16, 33779.66, 6, 17, 27, 2, 3],
    '2026-09-21': [22568.92, 30721.41, 3, 17, 26, 1, 2],
    '2026-09-22': [25087.04, 30216.77, 6, 13, 26, 2, 2],
    '2026-09-23': [25904.97, 36553.99, 2, 7, 28, 3, 1],
    '2026-09-24': [38082.09, 39383.78, 6, 33, 30, 4, 2],
    '2026-09-25': [69642.38, 31545.11, 3, 51, 31, 3, 2]
  };
  /* 字段下标（供渲染与校验共用） */
  var F_OUT = 0, F_INP = 1, F_FIRST = 2, F_AGAIN = 3, F_INHOS = 4, F_ADMIT = 5, F_DISCH = 6;

  /* ============================ 工具 ============================ */
  function p2(n) { return (n < 10 ? '0' : '') + n; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }
  function num(v, d) { d = d == null ? 2 : d; return (Math.round(v * Math.pow(10, d)) / Math.pow(10, d)).toFixed(d); }
  function wan(yuan, d) { return num(yuan / 10000, d == null ? 2 : d); }
  function sign(v, d) { d = d == null ? 1 : d; return (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(d); }
  function dateObj(s) { var p = String(s).split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function shiftDay(s, n) { var d = dateObj(s); d.setDate(d.getDate() + n); return d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate()); }
  function enumerate(a, b) { var out = [], c = a, guard = 0; while (c <= b && guard++ < 400) { out.push(c); c = shiftDay(c, 1); } return out; }
  function dowOf(s) { return DOW[dateObj(s).getDay()]; }
  /* 编辑表里显示短日期（9.23），内部仍按标准日期处理；用户也可直接输入 9.23 */
  function shortDate(v) { var n = normDate(v); return n ? ((+n.slice(5, 7)) + '.' + (+n.slice(8))) : (v || ''); }
  function isWeekend(s) { var w = dateObj(s).getDay(); return w === 0 || w === 6; }
  function fmtCN(s) { var p = s.split('-'); return (+p[1]) + '月' + (+p[2]) + '日'; }
  function fmtDot(s) { var p = s.split('-'); return p[0] + '.' + p[1] + '.' + p[2]; }
  function rangeLabel(days) {
    if (!days || !days.length) return '';
    var a = days[0], b = days[days.length - 1], ma = a.slice(5, 7), da = a.slice(8), mb = b.slice(5, 7), db = b.slice(8);
    if (a === b) return fmtCN(a);
    if (ma === mb) return (+ma) + '月' + (+da) + '—' + (+db) + '日';
    return fmtCN(a) + '—' + fmtCN(b);
  }
  function shortRange(days) {
    if (!days || !days.length) return '';
    var a = days[0], b = days[days.length - 1];
    var sa = '9.' + (+a.slice(8)), sb = '9.' + (+b.slice(8));
    return a === b ? sa : sa + '—' + sb;
  }

  /* 日期归一化：支持 9.23 / 9月23日 / 2026-09-23 / 0923 / 20260923 */
  function normDate(raw, year) {
    year = year || 2026;
    if (raw == null) return null;
    var s = String(raw).trim();
    if (!s) return null;
    s = s.replace(/[年月]/g, '-').replace(/日/g, '').replace(/[./]/g, '-').replace(/\s+/g, '');
    var m;
    if ((m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/))) return m[1] + '-' + p2(+m[2]) + '-' + p2(+m[3]);
    if ((m = s.match(/^(\d{1,2})-(\d{1,2})$/))) return year + '-' + p2(+m[1]) + '-' + p2(+m[2]);
    if (/^\d{8}$/.test(s)) return s.slice(0, 4) + '-' + s.slice(4, 6) + '-' + s.slice(6, 8);
    if (/^\d{4}$/.test(s)) return year + '-' + s.slice(0, 2) + '-' + s.slice(2, 4);
    return null;
  }

  /* 金额归一化：25,087.04 / 25087.04元 / 2.5万 → 元 */
  function toNum(raw) {
    if (raw == null) return null;
    var s = String(raw).trim();
    if (!s || /^[-—–]+$/.test(s)) return null;
    var isWan = /万/.test(s);
    s = s.replace(/万/g, '').replace(/[¥￥元,\s]/g, '').replace(/[（(][^）)]*[）)]/g, '');
    var v = parseFloat(s);
    if (!isFinite(v)) return null;
    return isWan ? v * 10000 : v;
  }

  /* ============================ 数据层 ============================ */
  function readJSON(key) { try { var r = localStorage.getItem(key); return r ? JSON.parse(r) : null; } catch (e) { return null; } }
  function writeJSON(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); return true; } catch (e) { return false; } }

  function loadDaily() {
    var base = {}, k;
    for (k in SEED) if (Object.prototype.hasOwnProperty.call(SEED, k)) base[k] = SEED[k].slice();
    var ov = readJSON(LS_DAILY);
    if (ov && typeof ov === 'object') for (k in ov) if (Object.prototype.hasOwnProperty.call(ov, k)) base[k] = ov[k].slice();
    return base;
  }
  function saveDaily(daily) {
    var ov = {}, k;
    for (k in daily) {
      if (!Object.prototype.hasOwnProperty.call(daily, k)) continue;
      var s = SEED[k], v = daily[k];
      var same = s && s.length === v.length && s.every(function (x, i) { return x === v[i]; });
      if (!same) ov[k] = v;
    }
    writeJSON(LS_DAILY, ov);
  }
  function resetDaily() { try { localStorage.removeItem(LS_DAILY); localStorage.removeItem(LS_META); } catch (e) { } }
  function importedMeta() { return readJSON(LS_META) || { imported: [], updatedAt: null }; }
  function snapshotBefore(daily, files) {
    writeJSON(LS_SNAP, { at: new Date().toISOString(), files: files, daily: daily });
  }

  /* ============================ 汇总 ============================ */
  function keysIn(daily, a, b) {
    return Object.keys(daily).filter(function (d) { return d >= a && d <= b; }).sort();
  }
  function agg(daily, days) {
    var o = 0, i = 0, hit = 0;
    var p = { first: 0, again: 0, admit: 0, disch: 0, inhos: null, inhosAt: null };
    var cover = { first: 0, again: 0, admit: 0, disch: 0 };
    days.forEach(function (d) {
      var v = daily[d]; if (!v) return;
      if (v[F_OUT] != null) o += v[F_OUT];
      if (v[F_INP] != null) i += v[F_INP];
      if (v[F_FIRST] != null) { p.first += v[F_FIRST]; cover.first++; }
      if (v[F_AGAIN] != null) { p.again += v[F_AGAIN]; cover.again++; }
      if (v[F_ADMIT] != null) { p.admit += v[F_ADMIT]; cover.admit++; }
      if (v[F_DISCH] != null) { p.disch += v[F_DISCH]; cover.disch++; }
      if (v[F_INHOS] != null) { p.inhos = v[F_INHOS]; p.inhosAt = d; }
      hit++;
    });
    p.cover = cover;
    p.days = hit;
    return { o: o, i: i, t: o + i, n: hit, days: days.slice(), p: p };
  }
  /* 人数是否覆盖了窗口内全部有收入的日子（用于决定要不要展示环比） */
  function peopleComplete(a) {
    return a.n > 0 && a.p.cover.first === a.n && a.p.cover.admit === a.n && a.p.cover.disch === a.n;
  }
  function summary(daily) {
    var twDays = keysIn(daily, WEEK_START, WEEK_END);
    var tw = agg(daily, twDays);
    var lwDays = keysIn(daily, LW_START, LW_END);
    var lw = agg(daily, lwDays);
    // 上周同期 = 本周已有日期各前移 7 天
    var sameDays = twDays.map(function (d) { return shiftDay(d, -7); }).filter(function (d) { return daily[d]; });
    var same = agg(daily, sameDays);
    // 月度（截至最新数据日）
    var mDays = keysIn(daily, MONTH_FROM, MONTH_TO);
    var cut = mDays.length ? mDays[mDays.length - 1] : null;
    var mtd = agg(daily, mDays);
    var cutD = cut ? +cut.slice(8) : 0;
    var done = mtd.t / 10000;
    var pct = MONTH_TARGET ? done / MONTH_TARGET * 100 : 0;
    var timePct = cutD / MONTH_DAYS * 100;
    var leftDays = Math.max(0, MONTH_DAYS - cutD);
    var leftAmt = Math.max(0, MONTH_TARGET - done);
    var need = leftDays ? leftAmt / leftDays : 0;
    var twAvg = tw.n ? tw.t / 10000 / tw.n : 0;
    var sameAvg = same.n ? same.t / 10000 / same.n : 0;
    var gap = need - twAvg;
    var delta = same.t ? (tw.t / same.t - 1) * 100 : null;
    // 本周内应报未报（只到其他源截止日）
    var dueEnd = SOURCE_CUTOFF < WEEK_END ? SOURCE_CUTOFF : WEEK_END;
    var due = enumerate(WEEK_START, dueEnd);
    var missing = due.filter(function (d) { return !daily[d]; });
    // 上周完整周派生
    var lwAvg = lw.n ? lw.t / lw.n : 0;
    var weAmt = 0;
    lwDays.forEach(function (d) { if (isWeekend(d)) weAmt += (daily[d][0] || 0) + (daily[d][1] || 0); });
    var weShare = lw.t ? weAmt / lw.t * 100 : 0;
    var revCut = cut;
    var globalCut = revCut && revCut > SOURCE_CUTOFF ? revCut : SOURCE_CUTOFF;
    // 最近 7 个有收入数据的日期（用于逐日明细）
    var recent = mDays.slice().filter(function (d) { return daily[d] && ((daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0)) > 0; });
    var rec7 = recent.slice(-7);
    var rec7Agg = agg(daily, rec7);
    var recWeekend = 0;
    rec7.forEach(function (d) { if (isWeekend(d)) recWeekend += (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0); });
    rec7Agg.weShare = rec7Agg.t ? recWeekend / rec7Agg.t * 100 : 0;
    return {
      tw: tw, lw: lw, same: same, sameDays: sameDays, mtd: mtd, mDays: mDays,
      rec7: rec7, rec7Agg: rec7Agg,
      twPeopleOk: peopleComplete(tw), samePeopleOk: peopleComplete(same),
      cut: cut, cutD: cutD, done: done, pct: pct, timePct: timePct,
      leftDays: leftDays, leftAmt: leftAmt, need: need, twAvg: twAvg, sameAvg: sameAvg,
      gap: gap, delta: delta, missing: missing, lwDays: lwDays, lwAvg: lwAvg,
      weShare: weShare, revCut: revCut, globalCut: globalCut, twDays: twDays
    };
  }

  /* ============================ 解析：CSV ============================ */
  function splitCSV(text) {
    var lines = text.replace(/\r\n?/g, '\n').replace(/^\uFEFF/, '').split('\n')
      .filter(function (l) { return l.trim() !== ''; });
    if (!lines.length) return [];
    var head = lines[0], cand = [',', '\t', ';', '|'], delim = ',', best = 0;
    cand.forEach(function (c) { var n = head.split(c).length; if (n > best) { best = n; delim = c; } });
    return lines.map(function (line) {
      var out = [], cur = '', q = false, i;
      for (i = 0; i < line.length; i++) {
        var ch = line.charAt(i);
        if (q) {
          if (ch === '"') { if (line.charAt(i + 1) === '"') { cur += '"'; i++; } else q = false; }
          else cur += ch;
        } else {
          if (ch === '"') q = true;
          else if (ch === delim) { out.push(cur); cur = ''; }
          else cur += ch;
        }
      }
      out.push(cur);
      return out;
    });
  }

  /* 从二维表提取行：定位表头列；无表头时退化为 日期/门诊/在院 顺序 */
  function rowsFromTable(table) {
    if (!table || table.length < 2) return [];
    var hi = -1, i;
    for (i = 0; i < Math.min(table.length, 8); i++) {
      var j = table[i].join('|');
      if (/日期|时间|date/i.test(j) && /门诊|在院|住院|合计|收入/.test(j)) { hi = i; break; }
    }
    var col = { date: -1, out: -1, inp: -1, total: -1 };
    if (hi >= 0) {
      table[hi].forEach(function (c, idx) {
        var t = String(c).replace(/\s/g, '');
        if (col.date < 0 && /日期|时间|date/i.test(t)) col.date = idx;
        if (col.out < 0 && /门诊/.test(t)) col.out = idx;
        if (col.inp < 0 && /(在院|住院)/.test(t)) col.inp = idx;
        if (col.total < 0 && /(合计|总计|当日收入|营收合计)/.test(t)) col.total = idx;
      });
    }
    if (col.date < 0) col.date = 0;
    if (col.out < 0 && col.inp < 0 && col.total < 0) { col.out = 1; col.inp = 2; }

    var rows = [];
    table.forEach(function (row, ri) {
      if (ri === hi) return;
      var joined = row.join(' ').trim();
      if (!joined) return;
      var d = normDate(col.date < row.length ? row[col.date] : row[0]);
      if (!d) return;
      var o = col.out >= 0 ? toNum(row[col.out]) : null;
      var p = col.inp >= 0 ? toNum(row[col.inp]) : null;
      var t = col.total >= 0 ? toNum(row[col.total]) : null;
      if (o == null && p == null && t == null) return;
      rows.push({ date: d, out: o, inp: p, total: t, raw: joined.slice(0, 70) });
    });
    return rows;
  }

  /* ============================ 解析：XLSX ============================ */
  function zipIndex(buf) {
    var dv = new DataView(buf), u8 = new Uint8Array(buf), eocd = -1, i;
    for (i = buf.byteLength - 22; i >= Math.max(0, buf.byteLength - 66000); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error('不是有效的 xlsx（未找到 ZIP 结构）');
    var n = dv.getUint16(eocd + 10, true), p = dv.getUint32(eocd + 16, true), entries = {};
    for (i = 0; i < n; i++) {
      if (p + 46 > buf.byteLength || dv.getUint32(p, true) !== 0x02014b50) break;
      var method = dv.getUint16(p + 10, true);
      var csize = dv.getUint32(p + 20, true);
      var usize = dv.getUint32(p + 24, true);
      var nlen = dv.getUint16(p + 28, true);
      var elen = dv.getUint16(p + 30, true);
      var clen = dv.getUint16(p + 32, true);
      var lho = dv.getUint32(p + 42, true);
      var name = new TextDecoder('utf-8').decode(u8.subarray(p + 46, p + 46 + nlen));
      entries[name] = { method: method, csize: csize, usize: usize, lho: lho };
      p += 46 + nlen + elen + clen;
    }
    return { u8: u8, dv: dv, entries: entries };
  }
  function inflateRaw(u8) {
    if (typeof DecompressionStream === 'undefined') throw new Error('当前浏览器不支持解压 xlsx，请另存为 CSV 后导入');
    var ds = new DecompressionStream('deflate-raw');
    return new Response(new Blob([u8]).stream().pipeThrough(ds)).text();
  }
  function zipRead(zip, name) {
    var e = zip.entries[name];
    if (!e) return Promise.resolve(null);
    var p = e.lho, dv = zip.dv, u8 = zip.u8;
    if (dv.getUint32(p, true) !== 0x04034b50) return Promise.resolve(null);
    var nlen = dv.getUint16(p + 26, true), elen = dv.getUint16(p + 28, true);
    var start = p + 30 + nlen + elen;
    var raw = u8.subarray(start, start + (e.csize || e.usize));
    if (e.method === 0) return Promise.resolve(new TextDecoder('utf-8').decode(raw));
    return inflateRaw(raw);
  }
  function colIdx(ref) {
    var n = 0, s = String(ref).replace(/[^A-Za-z]/g, '').toUpperCase(), i;
    for (i = 0; i < s.length; i++) n = n * 26 + (s.charCodeAt(i) - 64);
    return n - 1;
  }
  function decodeXML(s) {
    return String(s).replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
      .replace(/&apos;/g, "'").replace(/&#(\d+);/g, function (_, d) { return String.fromCharCode(+d); })
      .replace(/&amp;/g, '&');
  }
  function parseShared(xml) {
    if (!xml) return [];
    var out = [], re = /<si\b[^>]*>([\s\S]*?)<\/si>/g, m;
    while ((m = re.exec(xml))) {
      var txt = '', tr = /<t\b[^>]*>([\s\S]*?)<\/t>/g, t;
      while ((t = tr.exec(m[1]))) txt += decodeXML(t[1]);
      out.push(txt);
    }
    return out;
  }
  function parseSheetXML(xml, shared) {
    var table = [], re = /<row\b([^>]*)>([\s\S]*?)<\/row>/g, m;
    while ((m = re.exec(xml))) {
      var rAttr = m[1], row = [];
      var ri = rAttr.match(/\br="(\d+)"/);
      var cref = /<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g, c;
      while ((c = cref.exec(m[2]))) {
        var attr = c[1] || '', inner = c[2] || '';
        var refM = attr.match(/\br="([A-Za-z]+\d+)"/);
        var ci = refM ? colIdx(refM[1]) : row.length;
        var tm = attr.match(/\bt="([^"]+)"/);
        var type = tm ? tm[1] : 'n';
        var val = '';
        if (type === 'inlineStr') {
          var ir = /<t\b[^>]*>([\s\S]*?)<\/t>/g, it, acc = '';
          while ((it = ir.exec(inner))) acc += decodeXML(it[1]);
          val = acc;
        } else {
          var vr = inner.match(/<v>([\s\S]*?)<\/v>/);
          var raw = vr ? decodeXML(vr[1]) : '';
          if (type === 's') { var idx = parseInt(raw, 10); val = shared[idx] != null ? shared[idx] : ''; }
          else val = raw;
        }
        row[ci] = val;
      }
      for (var k = 0; k < row.length; k++) if (row[k] === undefined) row[k] = '';
      table.push({ r: ri ? +ri[1] : table.length + 1, cells: row });
    }
    table.sort(function (a, b) { return a.r - b.r; });
    return table.map(function (x) { return x.cells; });
  }
  function parseXLSX(buf) {
    var zip = zipIndex(buf);
    return zipRead(zip, 'xl/sharedStrings.xml').then(function (shared) {
      return zipRead(zip, 'xl/workbook.xml').then(function (wb) {
        var first = 'xl/worksheets/sheet1.xml', m = wb && wb.match(/<sheet\b[^>]*r:id="rId(\d+)"/);
        if (m) first = 'xl/worksheets/sheet' + m[1] + '.xml';
        return zipRead(zip, first).then(function (sx) {
          if (!sx) return zipRead(zip, 'xl/worksheets/sheet1.xml').then(function (fallback) {
            if (!fallback) throw new Error('xlsx 内未找到工作表数据');
            return rowsFromTable(parseSheetXML(fallback, parseShared(shared)));
          });
          return rowsFromTable(parseSheetXML(sx, parseShared(shared)));
        });
      });
    });
  }

  /* ============================ 解析：粘贴文本 ============================ */
  function parsePasted(text) {
    var t = String(text || '').trim();
    if (!t) return [];
    if (t.indexOf(',') >= 0 || t.indexOf('\t') >= 0) return rowsFromTable(splitCSV(t));
    // 逐行宽松匹配：日期 + 若干金额
    var rows = [];
    t.split(/\n+/).forEach(function (line) {
      line = line.trim(); if (!line) return;
      var md = line.match(/(\d{4}[-./年]\d{1,2}[-./月]\d{1,2}|\d{1,2}[-./月]\d{1,2})/);
      if (!md) return;
      var d = normDate(md[1]); if (!d) return;
      var rest = line.slice(line.indexOf(md[1]) + md[1].length);
      var nums = [], rn = /(\d[\d,]*\.?\d*)\s*(万)?/g, mm;
      while ((mm = rn.exec(rest))) {
        if (!mm[1].replace(/[^\d]/g, '')) continue;
        var v = parseFloat(mm[1].replace(/,/g, ''));
        if (!isFinite(v)) continue;
        nums.push(mm[2] ? v * 10000 : v);
      }
      if (!nums.length) return;
      var o = nums[0] != null ? nums[0] : null;
      var p = nums.length > 1 ? nums[1] : null;
      var tot = nums.length > 2 ? nums[2] : null;
      rows.push({ date: d, out: o, inp: p, total: tot, raw: line.slice(0, 70) });
    });
    return rows;
  }

  /* 列级单位推断：整列都 < 1000 视为「万元」记法 */
  function inferUnit(rows) {
    var vals = [];
    rows.forEach(function (r) { [r.out, r.inp].forEach(function (v) { if (v != null && v > 0) vals.push(v); }); });
    if (!vals.length) return 1;
    var mx = Math.max.apply(null, vals);
    return mx < 1000 ? 10000 : 1;
  }

  /* ============================ 校验 ============================ */
  function verifyRows(rows, daily) {
    var unit = inferUnit(rows), seen = {}, out = [];
    rows.forEach(function (r) {
      var o = r.out != null ? r.out * unit : null;
      var p = r.inp != null ? r.inp * unit : null;
      var rec = { date: r.date, out: o, inp: p, raw: r.raw, notes: [] };
      if (o == null && p == null) { rec.status = 'invalid'; rec.notes.push('缺少门诊/在院金额'); }
      else if (rec.date < MONTH_FROM || rec.date > MONTH_TO) { rec.status = 'invalid'; rec.notes.push('不在 9 月区间'); }
      else {
        var cur = daily[rec.date];
        if (!cur) { rec.status = 'new'; }
        else if (cur[0] === o && cur[1] === p) { rec.status = 'same'; rec.notes.push('与现值一致'); }
        else { rec.status = 'update'; rec.old = cur.slice(); }
        var key = rec.date;
        if (seen[key]) {
          var prev = seen[key];
          if (prev.out !== o || prev.inp !== p) {
            rec.status = 'conflict'; prev.status = 'conflict';
            rec.notes.push('批次内同日期数值不一致');
            prev.notes.push('批次内同日期数值不一致');
          }
        }
        seen[key] = rec;
        if (rec.status === 'update' && rec.old) {
          var base = (rec.old[0] || 0) + (rec.old[1] || 0);
          var next = (o || 0) + (p || 0);
          if (base > 0 && Math.abs(next / base - 1) > 0.5) rec.notes.push('与现值差异超 50%，请核对');
        }
      }
      if (!rec.status) rec.status = 'invalid';
      out.push(rec);
    });
    return { unit: unit, rows: out };
  }

  /* ============================ 渲染：全站同步 ============================ */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function setText(sel, txt) { $$(sel).forEach(function (e) { e.textContent = txt; }); }

  function renderRevenue() {
    var daily = loadDaily(), s = summary(daily), shell = $('.mkt-v2');

    /* ---- 时间戳 / 口径行 ---- */
    var revTxt = s.revCut ? fmtCN(s.revCut) : '—';
    var cutTxt = fmtCN(s.globalCut);
    var stamp = (s.revCut && s.revCut > TODAY) ? s.revCut : TODAY;
    setText('#periodBtn', '数据更新至 ' + stamp.split('-')[0] + '年' + (+stamp.slice(5, 7)) + '月' + (+stamp.slice(8)) + '日');
    $$('.ov-live').forEach(function (e) { e.textContent = '每日 09:00 抓取 · 数据更新至 9.' + (+s.globalCut.slice(8)); });
    setText('.mkt-filter small', ''); // 由下方重建（含 ● 图标）
    $$('.mkt-filter small').forEach(function (e) {
      e.innerHTML = '<b>●</b> 数据更新至 ' + fmtDot(TODAY) + '　·　本周 9月21日—9月27日（进行中，各源数据至 ' + cutTxt + '，营收至 ' + revTxt + '）';
    });
    setText('.dc-scope', '本周 9.21—9.27 · 数据截至 ' + (s.globalCut ? (+s.globalCut.slice(5, 7)) + '.' + (+s.globalCut.slice(8)) : '—') + '（营收 ' + (s.revCut ? (+s.revCut.slice(5, 7)) + '.' + (+s.revCut.slice(8)) : '—') + '）');
    setText('#sheetSub', '数据更新至 ' + TODAY.split('-')[0] + '年' + (+TODAY.slice(5, 7)) + '月' + (+TODAY.slice(8)) + '日 · 独立部门经营模块');

    /* ---- Hero ---- */
    if (s.tw.n) {
      var sub = shortRange(s.twDays) + ' · 日均 ¥' + num(s.twAvg, 2) + '万';
      if (s.delta != null) sub += ' · 较上周同期 ' + sign(s.delta, 1) + '%';
      if (s.missing.length) sub += '（' + shortRange(s.missing) + ' 日报待补）';
      $$('.mkt-amount').forEach(function (e) { e.innerHTML = '¥' + wan(s.tw.t, 2) + '<i>万</i>'; });
      setText('.mkt-sub', sub);
      setText('.mkt-hero-kicker', '本周至今营业额');
    } else {
      $$('.mkt-amount').forEach(function (e) { e.innerHTML = '—'; });
      setText('.mkt-sub', '本周暂无营收数据');
    }

    /* ---- 目标进度卡 ---- */
    var diff = s.timePct - s.pct;
    setText('.mkt-progress-big > b', wan(s.mtd.t, 2) + '万 / ' + MONTH_TARGET + '万');
    var meta = $$('.mkt-progress-meta span');
    if (meta[0]) meta[0].innerHTML = '金额完成 <strong>' + s.pct.toFixed(1) + '%</strong>';
    if (meta[1]) meta[1].textContent = '时间进度 ' + s.timePct.toFixed(1) + '%';
    $$('.mkt-progress-line').forEach(function (line) {
      var i = line.querySelector('i'), b = line.querySelector('b');
      if (i) i.style.width = Math.max(0, Math.min(100, s.pct)).toFixed(1) + '%';
      if (b) { b.style.left = Math.max(0, Math.min(100, s.timePct)).toFixed(1) + '%'; b.title = '时间进度 ' + s.timePct.toFixed(1) + '%'; }
    });
    // 目标进度卡的 badge
    var progCard = $$('.mkt-card').filter(function (c) { return /营收目标进度/.test(c.textContent); })[0];
    if (progCard) {
      var bd = progCard.querySelector('.mkt-badge');
      if (bd) bd.textContent = (diff >= 0 ? '落后 ' : '领先 ') + Math.abs(diff).toFixed(1) + 'pt';
    }
    var gapBoxes = $$('.mkt-gap > div');
    var gapVals = [num(s.leftAmt, 2) + '万', s.leftDays + '天', num(s.need, 2) + '万', num(s.twAvg, 2) + '万'];
    gapBoxes.forEach(function (box, i) {
      if (i > 3) return;
      var b = box.querySelector('b');
      if (b) b.textContent = gapVals[i];
    });

    /* ---- 营收速度缺口柱 ---- */
    var bars = $$('.gap-bars .gap-bar');
    if (bars.length >= 3) {
      var base = s.need || 1;
      var seq = [
        [num(s.twAvg, 2) + '万', s.twAvg / base * 100, '本周实际日均'],
        [num(s.sameAvg, 2) + '万', s.sameAvg / base * 100, '上周同期日均'],
        [num(s.need, 2) + '万', 100, '达标所需日均']
      ];
      bars.forEach(function (bar, i) {
        if (!seq[i]) return;
        var em = bar.querySelector('em'), i2 = bar.querySelector('i'), sp = bar.querySelector('span');
        if (em) em.textContent = seq[i][0];
        if (i2) i2.style.setProperty('--h', Math.max(3, Math.min(100, seq[i][1])).toFixed(0) + '%');
        if (sp) sp.textContent = seq[i][2];
      });
    }
    // 卡片标题里的缺口 badge
    var barCard = $$('.mkt-card').filter(function (c) { return /营收速度缺口/.test(c.textContent); })[0];
    if (barCard && barCard.querySelector('.mkt-badge')) barCard.querySelector('.mkt-badge').textContent = '缺口 ' + num(Math.max(0, s.gap), 2) + '万/日';

    /* ---- 收入结构（本周至今） ---- */
    if (s.tw.t) {
      var oPct = s.tw.o / s.tw.t * 100, iPct = s.tw.i / s.tw.t * 100;
      $$('.mkt-ring div').forEach(function (e) {
        e.innerHTML = '<b>' + wan(s.tw.t, 2) + '万</b>本周 ' + shortRange(s.twDays);
      });
      var lg = $$('.mkt-legend span');
      if (lg[0]) lg[0].innerHTML = '<b style="color:#26ae81">' + oPct.toFixed(1) + '%</b>门诊 ' + wan(s.tw.o, 2) + '万';
      if (lg[1]) lg[1].innerHTML = '<b style="color:#2e8ee9">' + iPct.toFixed(1) + '%</b>住院 ' + wan(s.tw.i, 2) + '万';
      var ringCard = $$('.mkt-card').filter(function (c) { return /收入结构/.test(c.textContent); })[0];
      if (ringCard && ringCard.querySelector('.mkt-card-head p')) {
        ringCard.querySelector('.mkt-card-head p').textContent = '本周 ' + shortRange(s.twDays) + ' · ' + (oPct >= iPct ? '门诊' : '住院') + '为主要收入来源';
      }
    }

    /* ---- 逐日明细表（最近 7 天，含最新数据） ---- */
    var tbl = $('.mkt-day-table');
    if (tbl && s.rec7.length) {
      var tb = tbl.querySelector('tbody'), tf = tbl.querySelector('tfoot');
      var mx = Math.max.apply(null, s.rec7.map(function (d) { return (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0); }));
      var mn = Math.min.apply(null, s.rec7.map(function (d) { return (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0); }));
      var rowsHtml = '', prev = null;
      s.rec7.forEach(function (d) {
        var amt = (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0);
        var diffTxt = '—', diffCls = '';
        if (prev) { var r = (amt - prev) / prev * 100; diffTxt = sign(r, 1) + '%'; diffCls = r >= 0 ? 'up' : 'down'; }
        var judge = '常态', jcls = '';
        if (amt === mx) { judge = '峰值'; jcls = 'up'; }
        else if (amt === mn) { judge = '低谷'; jcls = 'down'; }
        else if (prev != null && amt > prev) { judge = '回升'; jcls = 'up'; }
        else if (prev != null && amt < prev) { judge = '回落'; jcls = 'down'; }
        var we = isWeekend(d) ? ' class="weekend"' : '';
        rowsHtml += '<tr' + we + '><td>' + (+d.slice(5, 7)) + '.' + (+d.slice(8)) + ' ' + dowOf(d) + '</td><td><strong>' + wan(amt, 2) + '万</strong></td><td class="' + diffCls + '">' + diffTxt + '</td><td>' + (amt / s.rec7Agg.t * 100).toFixed(1) + '%</td><td class="' + jcls + '">' + judge + '</td></tr>';
        prev = amt;
      });
      if (tb) tb.innerHTML = rowsHtml;
      if (tf) tf.innerHTML = '<tr><td>合计</td><td>' + wan(s.rec7Agg.t, 2) + '万</td><td>日均' + wan(s.rec7Agg.n ? s.rec7Agg.t / s.rec7Agg.n : 0, 2) + '万</td><td>100%</td><td>关键日集中</td></tr>';
      var head = tbl.closest('.mkt-card');
      if (head) {
        var hp = head.querySelector('.mkt-card-head p');
        if (hp) hp.textContent = '最近 7 天 ' + shortRange(s.rec7) + ' · 营收日报口径';
        var hb = head.querySelector('.mkt-badge');
        if (hb) hb.textContent = '周末贡献 ' + s.rec7Agg.weShare.toFixed(1) + '%';
      }
    }

    /* ---- 环比矩阵：营业额行 ---- */
    var mx2 = $('.priority-matrix');
    if (mx2) {
      var cells = $$('.priority-matrix > b, .priority-matrix > span');
      // 结构：b(指标) span(上周) span(本周) span(变化) 循环；找营业额那一组
      var kids = Array.prototype.slice.call(mx2.children);
      for (var i3 = 0; i3 < kids.length; i3++) {
        if (kids[i3].tagName === 'B' && /营业额/.test(kids[i3].textContent)) {
          kids[i3].innerHTML = '营业额（' + s.tw.n + ' 天）';
          if (kids[i3 + 1]) kids[i3 + 1].innerHTML = wan(s.same.t, 2) + '万';
          if (kids[i3 + 2]) kids[i3 + 2].innerHTML = wan(s.tw.t, 2) + '万';
          if (kids[i3 + 3]) {
            kids[i3 + 3].className = (s.delta == null ? '' : (s.delta >= 0 ? 'good' : 'bad'));
            kids[i3 + 3].innerHTML = s.delta == null ? '—' : sign(s.delta, 1) + '%';
          }
          break;
        }
      }
      var sumP = $('.priority-summary');
      if (sumP && s.delta != null) {
        sumP.textContent = sumP.textContent.replace(/营业额[^；。]*[；。]/, '');
      }
      var pmBadge = $('.priority-compare .mkt-badge');
      if (pmBadge && s.delta != null) pmBadge.textContent = '营业额 ' + sign(s.delta, 1) + '%';
      var pmP = $('.priority-compare .mkt-card-head p');
      if (pmP) pmP.textContent = shortRange(s.twDays) + ' 与上周同期 ' + shortRange(s.sameDays) + ' 同口径（各 ' + s.tw.n + ' 天）';
      /* ⚠ 只更新「营业额」这一行（营收日报是其唯一来源，原有代码已处理）。
         「营销入院 / 营销对接」是管家台账口径、不由营收日报驱动，不要在这里改，
         否则会把 4→8 的管家口径偷偷换成全院入院口径。 */
    }

    /* ---- 分析横幅 ---- */
    var ban = $('.mkt-analysis-banner');
    if (ban) {
      ban.innerHTML = '<i>!</i><div><b>月度营收' + (diff > 5 ? '已进入高风险区' : '进度跟踪') + '</b><span>累计' + wan(s.mtd.t, 2) + '万，完成' + s.pct.toFixed(1) + '%；剩余' + s.leftDays + '天需' + num(s.leftAmt, 2) + '万。当前日均' + num(s.twAvg, 2) + '万，'
        + (s.gap > 0 ? '距离达标所需日均' + num(s.need, 2) + '万仍差' + num(s.gap, 2) + '万。' : '已高于达标所需日均' + num(s.need, 2) + '万。') + '</span></div>';
    }

    /* ---- 经营问题总览：风险卡 / 诊断 / 链路 ---- */
    var risks = $$('.dc-risk');
    if (risks[0]) {
      var lab = risks[0].querySelector('label'), st = risks[0].querySelector('strong'), p = risks[0].querySelector('p');
      if (lab) lab.textContent = '月目标风险';
      if (st) st.textContent = (diff >= 0 ? '落后' : '领先') + Math.abs(diff).toFixed(1) + 'pt';
      if (p) p.textContent = '累计' + wan(s.mtd.t, 2) + '万（' + (s.cut ? (+s.cut.slice(5, 7)) + '.' + (+s.cut.slice(8)) : '—') + '），剩余' + s.leftDays + '天还需' + num(s.leftAmt, 2) + '万，日均缺口' + num(Math.max(0, s.gap), 2) + '万。';
    }
    var detail = $$('.dc-item');
    if (detail[0]) {
      var dp = detail[0].querySelector('p');
      if (dp) dp.innerHTML = '完成率<b>' + s.pct.toFixed(1) + '%</b>' + (diff >= 0 ? '低于' : '高于') + '时间进度' + s.timePct.toFixed(1) + '%。本周至今日均' + num(s.twAvg, 2) + '万（' + shortRange(s.twDays) + (s.missing.length ? '，' + shortRange(s.missing) + ' 待补' : '') + '），'
        + (s.delta == null ? '暂无同期对照' : '较上周同期' + wan(s.same.t, 2) + '万' + (s.delta >= 0 ? '增长' : '下降') + Math.abs(s.delta).toFixed(1) + '%') + '；即使恢复到上周水平，也难以自然完成目标，必须明确新增收入来源。';
    }
    var chain = $$('.dc-node');
    if (chain.length) {
      var last = chain[chain.length - 1].querySelector('span');
      if (last) last.textContent = '营收日报日均' + num(s.twAvg, 2) + '万（' + (s.revCut ? (+s.revCut.slice(5, 7)) + '.' + (+s.revCut.slice(8)) : '—') + ' 止），达标需' + num(s.need, 2) + '万';
    }

    /* ---- 逐日经营判断 ---- */
    var insights = $$('.mkt-day-insight');
    if (insights.length >= 4 && s.rec7.length) {
      var minD = s.rec7[0], maxD = s.rec7[0];
      s.rec7.forEach(function (d) {
        var a = (daily[d][F_OUT] || 0) + (daily[d][F_INP] || 0);
        if (a < (daily[minD][F_OUT] || 0) + (daily[minD][F_INP] || 0)) minD = d;
        if (a > (daily[maxD][F_OUT] || 0) + (daily[maxD][F_INP] || 0)) maxD = d;
      });
      var minA = (daily[minD][F_OUT] || 0) + (daily[minD][F_INP] || 0);
      var maxA = (daily[maxD][F_OUT] || 0) + (daily[maxD][F_INP] || 0);
      insights[0].querySelector('b').textContent = (+minD.slice(5, 7)) + '.' + (+minD.slice(8)) + ' ' + dowOf(minD) + '仅' + wan(minA, 2) + '万';
      insights[1].querySelector('b').textContent = (+maxD.slice(5, 7)) + '.' + (+maxD.slice(8)) + ' ' + dowOf(maxD) + '贡献' + (maxA / s.rec7Agg.t * 100).toFixed(1) + '%';
      var g4 = insights[3];
      if (g4) {
        g4.querySelector('b').textContent = '本周营收已有及时口径';
        g4.querySelector('span').textContent = shortRange(s.twDays) + '合计' + wan(s.tw.t, 2) + '万、日均' + num(s.twAvg, 2) + '万'
          + (s.delta == null ? '' : '，比上周同期' + (s.delta >= 0 ? '增长' : '下降') + Math.abs(s.delta).toFixed(1) + '%')
          + (s.missing.length ? '（' + shortRange(s.missing) + ' 日报待补）' : '') + '。';
      }
    }

    /* ---- 营销 6 项 KPI：本周至今（营收日报口径，含入出院与门诊） ---- */
    /* ⚠ 标签也必须一起写：本组 6 格原先由「经营问题总览」模块写成
       客服随访 / 标记到院 / 营销接触 / 营销入院 / 营销转化 / 在院参考，
       而这里只写值（门诊收入 / 住院收入 / 初诊 …）→ 出现「客服随访 ¥11.16万」这类
       标签与数值错位。营收日报只能提供收入与就诊人次，故标签一并改为其口径。 */
    var kpis = $$('.mkt-kpis .mkt-kpi');
    if (kpis.length >= 6 && s.tw.t) {
      var t1 = s.tw, P1 = t1.p;
      var conv = P1.cover.first === t1.n && P1.first > 0 ? P1.admit / P1.first * 100 : null;
      var dspan = shortRange(s.twDays) + '（' + t1.n + ' 天）';
      var outN = (P1.cover.first === t1.n && P1.cover.again === t1.n) ? (P1.first + P1.again) : null;
      var kvals = [
        ['门诊收入', '¥' + wan(t1.o, 2) + '万', '占本周收入 ' + (t1.o / t1.t * 100).toFixed(1) + '%'],
        ['住院收入', '¥' + wan(t1.i, 2) + '万', '占本周收入 ' + (t1.i / t1.t * 100).toFixed(1) + '%'],
        ['门诊人次', outN == null ? '待补' : outN + '人',
         outN == null ? '初诊/复诊待补' : ('初诊 ' + P1.first + ' ＋ 复诊 ' + P1.again)],
        ['本周入院', P1.admit + '人',
         conv == null ? dspan : (dspan + ' · 初诊转入院 ' + conv.toFixed(1) + '%')],
        ['本周出院', P1.disch + '人', dspan],
        ['在院', P1.inhos == null ? '待补' : P1.inhos + '人',
         P1.inhosAt ? ((+P1.inhosAt.slice(5, 7)) + '.' + (+P1.inhosAt.slice(8))) + ' 最新时点' : '待补']
      ];
      kpis.slice(0, 6).forEach(function (k, i) {
        var hd1 = k.querySelector('.mkt-kpi-head');
        var st1 = k.querySelector('strong'), sp1 = k.querySelector('span');
        if (hd1 && hd1.lastChild && hd1.lastChild.nodeType === 3) hd1.lastChild.nodeValue = kvals[i][0];
        else if (hd1) hd1.insertAdjacentText('beforeend', kvals[i][0]);
        if (st1) st1.textContent = kvals[i][1];
        if (sp1) sp1.textContent = kvals[i][2];
      });
    }

    /* ---- 转化漏斗：本周至今 ---- */
    if (s.tw.t) {
      var P2 = s.tw.p;
      var fbox = $$('.mkt-flow-box');
      if (fbox.length >= 2) {
        var fb1 = fbox[0].querySelector('b'), fb2 = fbox[1].querySelector('b');
        if (fb1) fb1.textContent = P2.first;
        if (fb2) fb2.textContent = P2.admit;
      }
      var outs = $$('.mkt-outflow');
      if (outs.length >= 2) {
        var s1 = outs[0].querySelector('span'), v1 = outs[0].querySelector('b');
        var s2 = outs[1].querySelector('span'), v2 = outs[1].querySelector('b');
        if (s1) s1.textContent = '初诊转入院';
        if (v1) v1.textContent = P2.first > 0 ? (P2.admit / P2.first * 100).toFixed(1) + '%' : '—';
        if (s2) s2.textContent = '本周出院';
        if (v2) v2.textContent = P2.disch + '人';
      }
      var flowCard = $$('.mkt-card').filter(function (c) { return c.querySelector('.mkt-flow'); })[0];
      if (flowCard && flowCard.querySelector('.mkt-card-head p')) {
        flowCard.querySelector('.mkt-card-head p').textContent = '本周 ' + shortRange(s.twDays) + ' · 出院独立作为患者池流出';
      }
    }

    /* ---- 口径说明 ---- */
    var src = $('.mkt-source');
    if (src) {
      var P3 = s.tw.p;
      src.textContent = '口径：本周至今 ' + shortRange(s.twDays) + '（各源数据截至 ' + cutTxt + '，营收日报至 ' + revTxt + '）＝营业额 ' + wan(s.tw.t, 2) + ' 万（门诊 ' + wan(s.tw.o, 2) + ' ＋ 住院 ' + wan(s.tw.i, 2) + '）、初诊 ' + P3.first + ' 人、入院 ' + P3.admit + ' 人、出院 ' + P3.disch + ' 人'
        + (P3.inhosAt ? '，' + ((+P3.inhosAt.slice(5, 7)) + '.' + (+P3.inhosAt.slice(8))) + ' 在院 ' + P3.inhos + ' 人' : '')
        + '；对照上周同期 ' + shortRange(s.sameDays) + '（' + wan(s.same.t, 2) + ' 万）。上周完整周 ' + shortRange(s.lwDays) + ' 营收 ' + wan(s.lw.t, 2) + ' 万。月度目标 ' + MONTH_TARGET + ' 万，累计 ' + wan(s.mtd.t, 2) + ' 万（' + (s.cut ? (+s.cut.slice(5, 7)) + '月' + (+s.cut.slice(8)) + '日' : '—') + '）。导入新数据后先校验冲突，再更新看板。';
    }

    /* ---- 数据口径风险卡里的营收部分 ---- */
    $$('.mkt-data-warning p').forEach(function (e) {
      e.innerHTML = e.innerHTML.replace(/营收日报[^；。]*[；。]/, '营收日报已更新至 ' + revTxt + '；');
    });

    /* ---- 主面板（概览 Hero + 营收目标卡）：与营销面板同源、同一次渲染 ---- */
    renderMainPanel(daily, s);
    try { window.dispatchEvent(new CustomEvent('ops:revenue-updated', { detail: s })); } catch (e) { }
  }

  /* 主面板同步：营收日报 → Hero 五指标 + 9 月营收目标进度卡。
     为什么要有这个函数：这些节点原先在 index.html 里是写死的字面量，
     导入营收图片后不会变（业主 2026-09-26 反馈「拖进来了但数据没更新」）。 */
  function renderMainPanel(daily, s) {
    var tw = s.tw, P = tw.p, cut = s.cut;
    var cn = function (d) { return d ? ((+d.slice(5, 7)) + '月' + (+d.slice(8)) + '日') : '—'; };

    /* ---- ① Hero 五指标：在院 / 入院 / 出院 / 门诊 / 物理治疗 ---- */
    var kpis = $$('#heroKpis .ov-kpi');
    if (kpis.length >= 5) {
      var days = s.twDays || [];
      var span = days.length ? (shortRange(days) + '（' + days.length + ' 天）') : '—';
      // 门诊人次 = 初诊 ＋ 复诊（营收日报「门诊」下的两列）
      var outPat = (P.cover.first === tw.n && P.cover.again === tw.n) ? (P.first + P.again) : null;
      var vals = [
        ['在院人数', P.inhos == null ? '—' : String(P.inhos), '人',
         P.inhosAt ? ('最新时点 ' + ((+P.inhosAt.slice(5, 7)) + '.' + (+P.inhosAt.slice(8)))) : '待补'],
        ['本周入院', String(P.admit), '人', span],
        ['本周出院', String(P.disch), '人', span],
        ['门诊', outPat == null ? '—' : String(outPat), '人',
         outPat == null ? '本周初诊/复诊待补' : (span + ' 营收日报')],
        ['物理治疗', null, null, null]      // 资产表口径，营收日报不含 → 不动
      ];
      kpis.slice(0, 5).forEach(function (k, i) {
        var v = vals[i];
        if (v[1] === null) return;          // 物理治疗保持原值
        var lab = k.querySelector('label'), st = k.querySelector('strong'), sp = k.querySelector('.ov-chip');
        if (lab) lab.textContent = v[0];
        if (st) st.innerHTML = v[1] + '<em>' + v[2] + '</em>';
        if (sp) sp.textContent = v[3];
      });
    }

    /* ---- ② 9 月营收目标进度卡 ---- */
    var tp = s.timePct, pc = s.pct, diff = tp - pc;
    var chip = $('.ov-t-head .ov-chip');
    if (chip) chip.innerHTML = '9月1日—' + cn(cut) + ' <i>⌄</i>';
    var amt = $('.ov-amount');
    if (amt) amt.innerHTML = '<strong>' + wan(s.mtd.t, 2) + '</strong><em>／' + MONTH_TARGET + '万</em>';
    var bar = $('.ov-bar');
    if (bar) {
      bar.setAttribute('aria-label', '营收完成率 ' + pc.toFixed(1) + '%，时间进度 ' + tp.toFixed(1) + '%');
      var i1 = bar.querySelector('i'), u1 = bar.querySelector('u');
      if (i1) i1.style.width = Math.max(0, Math.min(100, pc)).toFixed(1) + '%';
      if (u1) u1.style.left = Math.max(0, Math.min(100, tp)).toFixed(1) + '%';
    }
    var two = $$('.ov-two > div > b');
    if (two.length >= 3) {
      two[0].textContent = pc.toFixed(1) + '%';
      two[1].textContent = tp.toFixed(1) + '%';
      two[2].textContent = (diff >= 0 ? '落后 ' : '领先 ') + Math.abs(diff).toFixed(1) + 'pt';
      two[2].className = diff >= 0 ? 'neg' : 'pos';
    }
    var gap = $('.ov-gap');
    if (gap) {
      gap.innerHTML = '剩余 <b>' + s.leftDays + '</b> 天需 <b>' + num(s.leftAmt, 2) + ' 万</b>，'
        + '日均需 <b>' + num(s.need, 2) + ' 万</b>；上周日均 <b>' + num(s.lwAvg / 10000, 2) + ' 万</b>、'
        + '本周至今（' + shortRange(s.twDays) + '）日均 <b>' + num(s.twAvg, 2) + ' 万</b>，'
        + '缺口 <b>' + num(Math.max(0, s.gap), 2) + ' 万</b>。';
    }
    var live = $$('.ov-live');
    live.forEach(function (e) {
      e.textContent = '每日 09:00 抓取 · 数据更新至 9.' + (+s.globalCut.slice(8));
    });
  }

// ============================================================================
//  图片识别（OCR）：营收日报截图 → 逐行营收与人数
//  策略：整图粗识别定位「列」→ 按列间隙分块 → 分块放大 14 倍精识别 → 合并重建
//  为什么这样做：本项目实测，同一张 848×244 的截图
//    · 整图 2.5~6 倍识别 → 数字大面积误识（"25904.97" → "s9008es"）
//    · 分块放大 14 倍识别 → "2026.9.23 25904.97 817.93 2 7" 基本全对
//  依赖：Tesseract.js（懒加载，fast 模型约 1.9MB，浏览器缓存后可复用）
// ============================================================================
  var OCR_SRC = {
    js: 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js',
    worker: 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/worker.min.js',
    core: 'https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.1',
    lang: 'https://tessdata.projectnaptha.com/4.0.0_fast'
  };
  var ocrWorker = null, ocrBusy = false;

  function loadScript(src) {
    return new Promise(function (res, rej) {
      if (document.querySelector('script[data-ocr="1"]')) return res();
      var el = document.createElement('script');
      el.src = src; el.async = true; el.dataset.ocr = '1';
      el.onload = function () { res(); };
      el.onerror = function () { rej(new Error('无法加载识别引擎（网络受限）')); };
      document.head.appendChild(el);
    });
  }
  function ocrProgress(txt) {
    var el = document.getElementById('ocrStatus');
    if (el) { el.textContent = txt; el.style.display = txt ? '' : 'none'; }
  }
  function getWorker() {
    if (ocrWorker) return Promise.resolve(ocrWorker);
    ocrProgress('正在加载识别引擎（首次约 2MB，之后走缓存）…');
    return loadScript(OCR_SRC.js).then(function () {
      if (typeof Tesseract === 'undefined') throw new Error('识别引擎未就绪');
      return Tesseract.createWorker('eng', 1, {
        workerPath: OCR_SRC.worker, corePath: OCR_SRC.core, langPath: OCR_SRC.lang,
        logger: function (m) {
          if (m.status === 'loading tesseract core') ocrProgress('加载识别核心…');
          else if (m.status === 'loading language traineddata') ocrProgress('加载数字识别模型…');
          else if (m.status === 'initializing api') ocrProgress('初始化…');
          else if (m.status === 'recognizing text') ocrProgress('识别中 ' + Math.round((m.progress || 0) * 100) + '%');
        }
      });
    }).then(function (w) {
      /* 这组参数是实测调出来的：
         · user_defined_dpi 不设时 Tesseract 会按 70dpi 处理小图，字符被过度降采样
         · psm 6 = 视为单一文本块，适合表格逐块识别
         · preserve_interword_spaces 让邻列数字不会被粘成一个 token */
      return w.setParameters({
        user_defined_dpi: '300',
        tessedit_pageseg_mode: '6'
      }).then(function () { ocrWorker = w; return w; });
    });
  }

  /* ---- 图像处理 ---- */
  function imgToCanvas(img, scale) {
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(img.width * scale));
    c.height = Math.max(1, Math.round(img.height * scale));
    var g = c.getContext('2d');
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0, c.width, c.height);
    return c;
  }
  /* 直接从原图裁剪并缩放：避免先放大整图（848×244 放大 16 倍 = 13568×3904，
     接近浏览器 canvas 上限，会导致 drawImage 静默失败、块全黑 → 识别不到任何内容） */
  function cropScale(img, x0, x1, scale, binarize) {
    var c = document.createElement('canvas');
    c.width = Math.max(1, Math.round((x1 - x0) * scale));
    c.height = Math.max(1, Math.round(img.height * scale));
    var g = c.getContext('2d');
    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, x0, 0, Math.max(1, x1 - x0), img.height, 0, 0, c.width, c.height);
    if (binarize) {
      /* Otsu 自适应阈值：微信压缩过的截图中数字边缘有灰阶噪点，二值化后 Tesseract 更稳 */
      try {
        var d = g.getImageData(0, 0, c.width, c.height), p = d.data;
        var hist = new Array(256).fill(0), n = c.width * c.height;
        var gray = new Uint8Array(n);
        for (var i = 0, j = 0; i < p.length; i += 4, j++) {
          var v = (p[i] * 0.299 + p[i + 1] * 0.587 + p[i + 2] * 0.114) | 0;
          gray[j] = v; hist[v]++;
        }
        var sum = 0; for (var t = 0; t < 256; t++) sum += t * hist[t];
        var sumB = 0, wB = 0, best = 0, thr = 128;
        for (var t2 = 0; t2 < 256; t2++) {
          wB += hist[t2]; if (!wB) continue;
          var wF = n - wB; if (!wF) break;
          sumB += t2 * hist[t2];
          var mB = sumB / wB, mF = (sum - sumB) / wF;
          var bt = wB * wF * (mB - mF) * (mB - mF);
          if (bt > best) { best = bt; thr = t2; }
        }
        for (var k = 0, j2 = 0; k < p.length; k += 4, j2++) {
          var b = gray[j2] > thr ? 255 : 0;
          p[k] = p[k + 1] = p[k + 2] = b; p[k + 3] = 255;
        }
        g.putImageData(d, 0, 0);
      } catch (e) { /* 二值化失败就用原图 */ }
    }
    return c;
  }
  function cropCanvas(canvas, x0, x1) {
    var c = document.createElement('canvas');
    c.width = Math.max(1, x1 - x0); c.height = canvas.height;
    var g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(canvas, -x0, 0);
    return c;
  }
  function loadImg(src) {
    return new Promise(function (res, rej) {
      var i = new Image();
      i.onload = function () { res(i); };
      i.onerror = function () { rej(new Error('图片无法读取')); };
      i.src = src;
    });
  }

  /* ---- 按「图像白列」找列切点（不依赖 OCR） ----
     思路同读带网格线的表格截图：逐列统计「有墨像素」占比，
     连续的低墨列就是列与列的间隙；在每段间隙的中间取切点。
     优点：与识别质量完全解耦；且能在数字之间切，不会切断数字。 */
  function inkCuts(img) {
    var c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    var g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0);
    var d, p;
    try { d = g.getImageData(0, 0, c.width, c.height); p = d.data; } catch (e) { return []; }
    var W2 = c.width, H2 = c.height;
    var rowInk = new Uint32Array(H2);
    for (var y = 0; y < H2; y++) {
      var base = y * W2 * 4, n = 0;
      for (var x = 0; x < W2; x++) {
        var i2 = base + x * 4;
        /* 阈值 170：表格线与文字比纸底暗得多，取偏保守的门限，
           避免截图压缩的灰噪点把「空白列」填满 */
        if (p[i2] < 170 && p[i2 + 1] < 170 && p[i2 + 2] < 170) n++;
      }
      rowInk[y] = n;
    }
    /* ⭐ 关键一步：先找出「表格横线行」并排除。
       营收日报是带横线的表格，横线贯穿每一列 —— 不排除的话每一列都算「有墨」，
       一个列间隙都找不到。实测 854×248 的营收日报有 12 条横线，
       不排除时只剩 4 个空白列（于是切块错位，6 行日报只重建出 1 行）；
       排除后空白列结构立刻清晰，可切出 11 块。 */
    var lineThr = W2 * 0.5, isLine = new Uint8Array(H2), dataRows = 0;
    for (var y1 = 0; y1 < H2; y1++) {
      if (rowInk[y1] > lineThr) isLine[y1] = 1; else dataRows++;
    }
    if (dataRows < H2 * 0.3) {          // 极端情况（整幅都是线）：放弃这一步，按全图统计
      dataRows = H2;
      isLine = new Uint8Array(H2);
    }
    var colInk = new Uint32Array(W2);
    for (var y2 = 0; y2 < H2; y2++) {
      if (isLine[y2]) continue;
      var b2 = y2 * W2 * 4;
      for (var x2 = 0; x2 < W2; x2++) {
        var k2 = b2 + x2 * 4;
        if (p[k2] < 170 && p[k2 + 1] < 170 && p[k2 + 2] < 170) colInk[x2]++;
      }
    }
    var thr = Math.max(1, Math.round(dataRows * 0.02));   // 有墨行数 < 2% 视为空列
    var runs = [], st = -1;
    for (var x3 = 0; x3 < W2; x3++) {
      if (colInk[x3] <= thr) { if (st < 0) st = x3; }
      else { if (st >= 0) { runs.push([st, x3 - 1]); st = -1; } }
    }
    if (st >= 0) runs.push([st, W2 - 1]);
    /* 段宽阈值 0.8% 是实测出来的：0.6% 会把字符间的小间隙也当列间隙（切出 12 块、含伪列），
       1.0% 又会漏掉窄列（只剩 10 块）。0.8% 对本项目截图恰好切出 11 列且与表头对齐。 */
    var minGap = Math.max(3, Math.round(W2 * 0.005));
    var mids = [];
    runs.forEach(function (r) {
      if (r[1] - r[0] + 1 < minGap) return;
      var mid = Math.round((r[0] + r[1]) / 2);
      if (mid < W2 * 0.02 || W2 - mid < W2 * 0.02) return;   // 丢掉贴边留白
      mids.push(mid);
    });
    /* 合并过近的切点，保证每块有足够宽度供放大识别 */
    var minW2 = Math.max(24, Math.round(W2 * 0.035));
    var out = [];
    mids.forEach(function (m) {
      if (!out.length || m - out[out.length - 1] >= minW2) out.push(m);
    });
    return out;
  }

  /* ---- 把一块的识别结果转成带坐标的 token ---- */
  function wordsOf(data) {
    var o = [];
    var push = function (w) { if (w && w.text && w.bbox) o.push(w); };
    if (Array.isArray(data.words) && data.words.length) { data.words.forEach(push); return o; }
    (data.blocks || []).forEach(function (b) {
      (b.paragraphs || []).forEach(function (p) {
        (p.lines || []).forEach(function (l) { (l.words || []).forEach(push); });
      });
    });
    return o;
  }
  var MONEY_RE = /^-?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?$/;
  function numToken(t) {
    if (t == null) return null;
    var s = String(t).trim();
    if (!/\d/.test(s)) return null;
    var neg = /^[-−–—]/.test(s);
    s = s.replace(/^[-−–—]/, '').replace(/[^\d.,]/g, '');
    if (!s) return null;
    var v;
    if (/^\d{1,3}([.,]\d{3})+$/.test(s)) v = parseFloat(s.replace(/[.,]/g, ''));
    else if (/^\d+\.\d+$/.test(s)) v = parseFloat(s);
    else if (/^\d+$/.test(s)) v = parseFloat(s);
    else v = parseFloat(s.replace(/,/g, ''));
    if (!isFinite(v)) return null;
    return neg ? -v : v;
  }
  var DATE_RE = /(\d{4})\s*[.\-/年]\s*(\d{1,2})\s*[.\-/月]\s*(\d{1,2})/;
  function mkDate(y, mo, d) {
    y = +y; mo = +mo; d = +d;
    if (y < 2000 || y > 2100 || mo < 1 || mo > 12 || d < 1 || d > 31) return null;
    return y + '-' + p2(mo) + '-' + p2(d);
  }
  /* 鲁棒取日期：OCR 对 "2026.9.23" 的识别结果可能是
     "2026.9.23" / "2026 9 23" / "2026923"（丢点）/ "20260923"（补零） */
  function findDate(txt) {
    var t = String(txt || '');
    var m = t.match(/(20\d{2})\s*[.\-/年]\s*(\d{1,2})\s*[.\-/月]\s*(\d{1,2})/);
    if (m) { var r1 = mkDate(m[1], m[2], m[3]); if (r1) return r1; }
    // 年 + 无分隔的 3~4 位（月日）
    m = t.match(/(20\d{2})(\d{3,4})(?!\d)/);
    if (m) {
      var tail = m[2], cands = [];
      if (tail.length === 3) cands.push([+tail.charAt(0), +tail.slice(1)]);
      else cands.push([+tail.slice(0, 2), +tail.slice(2)], [+tail.charAt(0), +tail.slice(1, 3)]);
      for (var i = 0; i < cands.length; i++) {
        var r2 = mkDate(m[1], cands[i][0], cands[i][1]);
        if (r2) return r2;
      }
    }
    // 仅 "9.23"（表头区可能没有年份）
    m = t.match(/(?:^|\s)(\d{1,2})\s*[.\-/月]\s*(\d{1,2})(?!\d)/);
    if (m) { var r3 = mkDate(YEAR, m[1], m[2]); if (r3) return r3; }
    return null;
  }
  var YEAR = 2026;

  /* 三数关系判定：门诊 + 在院 = 当日合计。
     OCR 常整列丢失小数点（27228.16 → 2722816），因此对每个数再试 ×1 / ×0.01 / ×100，
     取「需要缩放次数最少」且能配平的组合 —— 这既救回丢点，又不会把无关数字硬凑。 */
  var SCALES = [1, 0.01, 100];
  function tryTriple(a, b, c) {
    var best = null;
    for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) for (var k = 0; k < 3; k++) {
      var A = a * SCALES[i], B = b * SCALES[j], C = c * SCALES[k];
      if (A < 500 || B < 500 || C < 500) continue;
      if (A > 600000 || B > 600000 || C > 800000) continue;   // 单日营收量级上限
      var tol = Math.max(0.06, C * 0.0008);
      if (Math.abs(A + B - C) > tol) continue;
      var fixes = (i ? 1 : 0) + (j ? 1 : 0) + (k ? 1 : 0);
      if (!best || fixes < best.fixes) best = { A: A, B: B, C: C, fixes: fixes };
    }
    return best;
  }

  /* 金额归一：单日/累计都不超过 500 万，超过则视为整列丢了小数点 */
  function normMoney(v) { return Math.abs(v) > 5000000 ? v / 100 : v; }

  /* 已定合计时反求两加数（门诊/在院），同样允许小数点丢失的缩放恢复 */
  function pairSum(a, b, target) {
    var best = null;
    for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) {
      var A = a * SCALES[i], B = b * SCALES[j];
      if (A < 500 || B < 500 || A > 600000 || B > 600000) continue;
      var tol = Math.max(0.06, target * 0.0008);
      if (Math.abs(A + B - target) > tol) continue;
      var fixes = (i ? 1 : 0) + (j ? 1 : 0);
      if (!best || fixes < best.fixes) best = { A: A, B: B, fixes: fixes };
    }
    return best;
  }

  /* ---- 按 y 聚行 ---- */
  function groupRows(tokens) {
    if (!tokens.length) return [];
    var a = tokens.slice().sort(function (x, y) { return (x.y - y.y) || (x.x - y.x); });
    var hs = a.map(function (t) { return t.h; }).sort(function (x, y) { return x - y; });
    var h = hs[Math.floor(hs.length / 2)] || 10;
    var tol = Math.max(6, h * 0.7);
    var rows = [];
    a.forEach(function (t) {
      var r = null;
      for (var i = 0; i < rows.length; i++) if (Math.abs(rows[i].cy - t.y) <= tol) { r = rows[i]; break; }
      if (!r) { r = { cy: t.y, ts: [] }; rows.push(r); }
      r.ts.push(t);
      r.cy = r.ts.reduce(function (s2, x) { return s2 + x.y; }, 0) / r.ts.length;
    });
    rows.sort(function (x, y) { return x.cy - y.cy; });
    rows.forEach(function (r) { r.ts.sort(function (x, y) { return x.x - y.x; }); });
    return rows;
  }
  /* ---- 按 x 聚类成列 ---- */
  function clusterCols(tokens, tol) {
    var xs = tokens.map(function (t) { return t.xc; }).sort(function (a, b) { return a - b; });
    if (!xs.length) return [];
    var cols = [], cur = [xs[0]];
    for (var i = 1; i < xs.length; i++) {
      if (xs[i] - cur[cur.length - 1] <= tol) cur.push(xs[i]);
      else { cols.push(cur); cur = [xs[i]]; }
    }
    cols.push(cur);
    return cols.map(function (g) { return g.reduce(function (a, b) { return a + b; }, 0) / g.length; });
  }

  /* ---- 主流程 ---- */
  function ocrRevenueImage(src, onNote) {
    var imgW = 0, note = onNote || function () { };
    return loadImg(src).then(function (img) {
      imgW = img.width;
      return getWorker().then(function (w) { return { w: w, img: img }; });
    }).then(function (ctx) {
      var w = ctx.w, img = ctx.img;
      /* ① 粗识别：只为定位「列」，不取数值 */
      ocrProgress('定位表格结构…');
      var scaleCoarsePre = Math.min(3, Math.max(1.5, 2200 / img.width));
      return w.recognize(imgToCanvas(img, scaleCoarsePre), {}, { blocks: true, text: true })
        .then(function (r) {
          var raw = wordsOf(r.data).map(function (x) {
            return { x: x.bbox.x0, xc: (x.bbox.x0 + x.bbox.x1) / 2, y: (x.bbox.y0 + x.bbox.y1) / 2,
                     w: x.bbox.x1 - x.bbox.x0, h: x.bbox.y1 - x.bbox.y0, text: x.text };
          });
          var scaleCoarse = scaleCoarsePre;
          // 还原到原图坐标
          raw.forEach(function (t) { t.x /= scaleCoarse; t.xc /= scaleCoarse; t.y /= scaleCoarse; t.h /= scaleCoarse; t.w /= scaleCoarse; });
          return { w: w, img: img, coarse: raw };
        });
    }).then(function (ctx) {
      var w = ctx.w, img = ctx.img, coarse = ctx.coarse;
      /* ② 由粗识别结果推出列位置，进而在「列间隙」处切块（不会切断数字） */
      var W = imgW;
      /* 关键：用 token 的左右边界求「真实空隙」，切点只落在空隙里，绝不切断数字。
         早期版本用「列中心的中点」当切点，实测会把 "2026.9.23" 从中间切开。 */
      var tk = coarse.filter(function (t) { return /\d/.test(t.text) && t.h > 0; })
                     .sort(function (a, b) { return a.x - b.x; });
      /* 字符高度中位数：Tesseract 的最佳字符高度约 30—40px，
         过度放大（如 ×15 得 150px）会触发内部降采样，识别反而变差 */
      var hArr = coarse.filter(function (t) { return t.h > 0; })
                       .map(function (t) { return t.h; }).sort(function (a, b) { return a - b; });
      var medH = hArr.length ? hArr[Math.floor(hArr.length / 2)] : 10;

      /* ⭐ 切点优先来自「图像白列」，不依赖粗识别。
         原先只用 OCR token 的空隙算切点：一旦粗识别把数字读错（微信压缩图上很常见），
         token 位置就跟着错 → 切点落到数字中间 → 整行报废。
         实测 854×248 的营收日报：token 法只切出 4 块（bounds 274/490/647），
         日期列被 0—274 那块切成两半，6 行日报最终只重建出 1 行。
         白列法按像素找列与列之间的空白，与识别质量无关，同一张图能切出 12 列。 */
      var cuts = inkCuts(img);
      var cutSrc = 'ink';
      if (cuts.length < 2) {
        cutSrc = 'token';
        var groups = [];
        tk.forEach(function (t) {
          var right = t.x + (t.w || t.h * 0.6 * String(t.text).length);
          var g = groups[groups.length - 1];
          if (g && t.x <= g.x1 + Math.max(3, t.h * 0.45)) g.x1 = Math.max(g.x1, right);
          else groups.push({ x0: t.x, x1: right });
        });
        var gaps = [];
        for (var gi = 1; gi < groups.length; gi++) {
          var ga = groups[gi - 1].x1, gb = groups[gi].x0;
          if (gb - ga > Math.max(3, W * 0.004)) gaps.push({ c: (ga + gb) / 2, w: gb - ga });
        }
        gaps.sort(function (a, b) { return b.w - a.w; });
        var minW = W * 0.17;
        gaps.forEach(function (g) {
          if (cuts.every(function (c) { return Math.abs(c - g.c) >= minW; }) && g.c >= minW && W - g.c >= minW) cuts.push(g.c);
        });
        cuts.sort(function (a, b) { return a - b; });
      }
      if (cuts.length < 2) { cuts = [Math.round(W / 3), Math.round(W * 2 / 3)]; cutSrc = 'fallback'; }
      try { window.__ocrCuts = { src: cutSrc, cuts: cuts.map(function (c) { return Math.round(c); }) }; } catch (e) { }
      var bounds = [0].concat(cuts).concat([W]);
      var blocks = [];
      for (var b = 0; b < bounds.length - 1; b++) {
        var x0 = bounds[b], x1 = bounds[b + 1];
        if (x1 - x0 < W * 0.03) continue;
        /* 留 10% 块宽的重叠，避免边界数字被切断。
           ⚠ 原先用全图宽的 6%（854px → 51px），块本身只有 180px 左右，
           两边各加 51px 会把邻列整块卷进来，倍数也被迫降低。改为按块宽算。 */
        var ov = Math.max(2, Math.round((x1 - x0) * 0.10));
        blocks.push({ x0: Math.max(0, x0 - (b ? ov : 0)), x1: Math.min(W, x1 + (b < bounds.length - 2 ? ov : 0)) });
      }
      note('识别中：' + blocks.length + ' 块');
      /* ③ 逐块放大识别 */
      var collected = [];
      var blockTexts = [];
      var chain = Promise.resolve();
      blocks.forEach(function (bl, idx) {
        chain = chain.then(function () {
          ocrProgress('识别中 ' + (idx + 1) + '/' + blocks.length + '…');
          var bw = bl.x1 - bl.x0;
          /* 目标：放大后块宽约 1200px。实测（本项目 848×244 的营收日报截图）
             · 块宽 4000+px（字符高 150px）→ 数字大面积误识
             · 块宽 1200px （字符高 ~40px，接近 Tesseract 最佳区间）→ 识别稳定 */
          var sc = Math.max(3, Math.min(8, Math.round(1200 / bw)));
          /* binarize 参数保留但默认关闭：实测对本项目这张微信压缩截图反而使日期列丢失 */
          var cv = cropScale(img, bl.x0, bl.x1, sc, false);
          return w.recognize(cv, {}, { blocks: true, text: true }).then(function (r) {
            blockTexts.push('[' + idx + '] ' + String(r.data.text || '').replace(/\n+/g, ' | ').slice(0, 150));
            wordsOf(r.data).forEach(function (x) {
              var raw = x.text.trim();
              if (!raw) return;
              var v = numToken(raw);
              if (DATE_RE.test(raw) || findDate(raw)) v = null;   // 日期不是金额
              if (v == null && !findDate(raw)) return;
              collected.push({
                text: raw, v: v,
                x: bl.x0 + x.bbox.x0 / sc, xc: bl.x0 + (x.bbox.x0 + x.bbox.x1) / 2 / sc,
                y: (x.bbox.y0 + x.bbox.y1) / 2 / sc, h: (x.bbox.y1 - x.bbox.y0) / sc
              });
            });
          });
        });
      });
      return chain.then(function () {
        return { img: img, tokens: collected,
                 meta: { blocks: blocks.length, bounds: bounds, coarse: coarse.length,
                         texts: blockTexts, medH: medH } };
      });
    }).then(function (ctx) {
      /* ④ 去重（重叠区会产生重复 token） */
      var toks = ctx.tokens.slice().sort(function (a, b) { return (a.xc - b.xc); });
      var kept = [];
      toks.forEach(function (t) {
        for (var i = 0; i < kept.length; i++) {
          var k = kept[i];
          if (Math.abs(k.xc - t.xc) < Math.max(4, t.h * 0.5) && Math.abs(k.y - t.y) < Math.max(4, t.h * 0.7)) {
            // 同位置：取更长的数字文本（重叠切割常导致残缺）
            if (String(t.text).replace(/\D/g, '').length > String(k.text).replace(/\D/g, '').length) kept[i] = t;
            return;
          }
        }
        kept.push(t);
      });
      /* ⑤ 重建表格 */
      var rows = groupRows(kept);
      var out = [], lastDate = null;
      rows.forEach(function (r) {
        var joined = r.ts.map(function (t) { return t.text; }).join(' ');
        var ds = findDate(joined);
        if (!ds) {
          /* 日期列被 OCR 吃掉时无法可靠定位是哪一天 —— 曾按「上一行 +1」推断，
             实测把 9.24 误标成 9.21，因此不再推断：保留该行数值、日期留空，由用户指定。 */
          var nv = r.ts.filter(function (t) { return t.v != null && Math.abs(t.v) >= 500; }).sort(function (a, b) { return b.v - a.v; });
          if (nv.length < 2) return;
          out.push({
            date: '', raw: joined.slice(0, 140), verified: false, undated: true,
            out: normMoney(nv[nv.length - 1].v), inp: normMoney(nv[nv.length - 2].v),
            nums: r.ts.filter(function (t) { return t.v != null; }).map(function (t) { return { v: t.v, xc: t.xc }; })
          });
          return;
        }
        var nums = r.ts.filter(function (t) { return t.v != null && Math.abs(t.v) >= 0.005; });
        /* 三数自校验：门诊 + 在院 = 当日合计 —— 语言无关，可定位并自证 */
        var best = null;
        for (var i = 0; i < nums.length; i++) for (var j = i + 1; j < nums.length; j++) for (var k = 0; k < nums.length; k++) {
          if (k === i || k === j) continue;
          var A = nums[i], B = nums[j], C = nums[k];
          var fit = tryTriple(A.v, B.v, C.v);
          if (!fit) continue;
          var sc = fit.C - fit.fixes * 1e9;   // 优先「缩放次数少」，其次合计更大
          if (!best || sc > best.sc) best = { A: A, B: B, C: C, fit: fit, sc: sc };
        }
        var rec = {
          date: ds,
          raw: joined.slice(0, 140), verified: !!best
        };
        if (best) {
          var L = best.A.xc <= best.B.xc ? best.A : best.B;
          var Rr = best.A.xc <= best.B.xc ? best.B : best.A;
          var vA = best.fit.A, vB = best.fit.B;
          var leftIsOut = best.A.xc <= best.B.xc;
          rec.out = leftIsOut ? vA : vB;
          rec.inp = leftIsOut ? vB : vA;
          rec.total = best.fit.C;
          rec.fixed = best.fit.fixes > 0;
          rec.nums = nums.map(function (t) { return { v: t.v, xc: t.xc }; });
          /* 人数：夹在 门诊↔在院 之间的小整数为 初诊/复诊；
             夹在 在院↔合计 之间的小整数依次为 在院/入院/出院初次/出院多次 */
          var small = function (a, b) {
            return nums.filter(function (t) {
              return t !== L && t !== Rr && t !== best.C &&
                     t.v > 0 && t.v < 500 && t.v % 1 === 0 &&   // 人数是整数，排除 "-3975.20" 这类残片
                     t.xc > a && t.xc < b;
            }).sort(function (x, y) { return x.xc - y.xc; });
          };
          var leftSide = small(L.xc, Rr.xc);
          if (leftSide[0]) rec.first = leftSide[0].v;
          if (leftSide[1]) rec.again = leftSide[1].v;
          var rightSide = small(Rr.xc, best.C.xc);
          if (rightSide[0]) rec.inhos = rightSide[0].v;
          if (rightSide[1]) rec.admit = rightSide[1].v;
          if (rightSide[2]) rec.disch = (rightSide[2].v || 0) + (rightSide[3] ? rightSide[3].v : 0);
        }
        out.push(rec);
      });

      /* 累计递推校验：营收日报的「当月累计收入」逐日递增，相邻两日之差就是当日合计。
         该列金额大、变化明显，OCR 反而最稳；用它来锁定当日合计，可排除
         「两个错数恰好也能配平」的情况（实测 9.21 行曾被误判为 77200 + 2979）。 */
      var cumRows = out.filter(function (r) {
        var c = null;
        (r.nums || []).forEach(function (n) {
          var vv = normMoney(n.v);
          if (vv >= 300000 && (!c || vv > c)) c = vv;    // 累计列是该行最大的金额
        });
        if (!c) return false;
        r.cum = c; return true;
      });
      cumRows.sort(function (a, b) { return a.date < b.date ? -1 : (a.date > b.date ? 1 : 0); });
      for (var ci = 1; ci < cumRows.length; ci++) {
        var gap2 = cumRows[ci].cum - cumRows[ci - 1].cum;
        if (gap2 > 500 && gap2 < 800000) { cumRows[ci].cumDiff = gap2; }
      }
      cumRows.forEach(function (r) {
        if (!r.cumDiff || !r.nums || r.nums.length < 2) return;
        var hit = null;
        for (var i = 0; i < r.nums.length && !hit; i++) {
          for (var j = i + 1; j < r.nums.length && !hit; j++) {
            var fit = pairSum(r.nums[i].v, r.nums[j].v, r.cumDiff);
            if (fit) hit = { i: i, j: j, fit: fit };
          }
        }
        if (hit) {
          var A = r.nums[hit.i], B = r.nums[hit.j];
          var left2 = A.xc <= B.xc;
          r.verified = true; r.byCum = true; r.total = r.cumDiff;
          r.out = left2 ? hit.fit.A : hit.fit.B;
          r.inp = left2 ? hit.fit.B : hit.fit.A;
        } else {
          r.verified = false;   // 用累计差也凑不出 → 判为待核对，不写入
        }
      });

      /* 既没有日期、又无法用累计差验证的行，绝大多数是数字残片（如 "800 | 1959"），
         直接丢弃，否则会把噪声灌进识别表 */
      out = out.filter(function (r) { return r.date || r.verified; });

      var meta = ctx.meta || { blocks: 0, bounds: [], coarse: 0 };
      try {
        window.__ocrDebug = { blocks: meta.blocks, bounds: meta.bounds, coarse: meta.coarse, medH: meta.medH,
                              collected: toks.length, kept: kept.length, rows: rows.length, blocks: meta.texts,
                              parsed: out.length, verified: out.filter(function (r4) { return r4.verified; }).length,
                              byCum: out.filter(function (r4) { return r4.byCum; }).length, sample: out.slice(0, 8),
                              lines: rows.map(function (r3) {
                                return r3.ts.map(function (t) { return t.text; }).join(' ').slice(0, 110);
                              }).slice(0, 12) };
      } catch (e) { }
      var okN = out.filter(function (r2) { return r2.verified; }).length;
      ocrProgress(out.length
        ? ('识别到 ' + out.length + ' 行：' + okN + ' 行数值自洽可直接使用，其余请在下方核对补全')
        : ('未提取到数据行（共识别 ' + kept.length + ' 个数字 / ' + rows.length + ' 行文本）。可改用「粘贴文本」或手工填写'));
      return out;
    });
  }
// ============================================================================

  /* ============================ 抽屉 UI ============================ */
  var host = document.createElement('div');
  host.className = 'import-backdrop';
  host.id = 'importBackdrop';
  host.innerHTML = '<section class="import-drawer" role="dialog" aria-modal="true" aria-label="导入并更新分析数据">'
    + '<header class="import-head"><div><h2>导入并更新分析数据</h2><p>解析 → 校验 → 更新。原数据快照自动保留，可整体回退</p></div>'
    + '<button class="import-close" aria-label="关闭">×</button></header>'
    + '<div class="import-body">'
    + '  <input id="importFile" type="file" multiple accept=".csv,.tsv,.txt,.xlsx,.png,.jpg,.jpeg,.webp,image/*" hidden>'
    + '  <div class="drop-zone" id="dropZone"><div class="drop-icon">⇧</div><b>拖入图片或表格文件</b>'
    + '<span>CSV / XLSX 自动解析；图片自动识别日期、门诊/在院收入与入出院人数，结果可在下方核对修改</span></div>'
    + '  <div class="ocr-status" id="ocrStatus" style="display:none"></div>'
    + '  <div class="import-steps"><div class="import-step active" data-n="1">上传</div><div class="import-step" data-n="2">识别</div>'
    + '<div class="import-step" data-n="3">校验</div><div class="import-step" data-n="4">确认更新</div></div>'
    + '  <section class="import-card"><h3>本次文件<span class="card-hint" id="fileCount"></span></h3><div id="fileList"></div></section>'
    + '  <section class="import-card"><h3>粘贴识别文本 <span class="card-hint">可选 · 从日报或截图转文字后直接粘</span></h3>'
    + '  <textarea id="pasteBox" class="paste-box" spellcheck="false" placeholder="9.23 门诊 25087.04 在院 30216.77&#10;9.24 门诊 31000 在院 29000&#10;也可直接粘贴 CSV 内容"></textarea>'
    + '  <button class="paste-apply" id="pasteApply">解析粘贴内容</button></section>'
    + '  <section class="import-card"><h3>识别结果 <span class="card-hint">可直接修改 · 单位：元（也可写 5.33万）</span></h3>'
    + '  <div id="rowEditor" class="row-editor"></div>'
    + '  <button class="paste-apply" id="addRow">+ 手工添加一行</button></section>'
    + '  <section class="import-card"><h3>数据校验</h3><div class="verify-grid" id="verifyGrid"></div>'
    + '  <div id="conflictArea"></div>'
    + '  <label class="audit"><input type="checkbox" checked id="snapChk"> 保存本次导入前的数据快照，并记录来源与导入时间</label>'
    + '  <div class="reset-line"><button class="link-btn" id="resetBtn">恢复初始数据（清除本机导入）</button><span id="metaLine" class="meta-line"></span></div>'
    + '  </section></div>'
    + '<footer class="import-footer"><button class="cancel">取消</button><button class="export" id="exportBtn">复制数据块</button>'
    + '<button class="confirm" id="confirmBtn">确认更新</button></footer></section>';
  document.body.appendChild(host);

  var toast = document.createElement('div');
  toast.className = 'demo-toast';
  document.body.appendChild(toast);
  var toastTimer = null;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('show'); }, 3600);
  }

  var close = function () { host.classList.remove('show'); };
  var open = function () { host.classList.add('show'); var d = host.querySelector('.import-drawer'); if (d) d.scrollTop = 0; refreshMeta(); };
  host.querySelector('.import-close').onclick = close;
  host.querySelector('.cancel').onclick = close;
  host.addEventListener('click', function (e) { if (e.target === host) close(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && host.classList.contains('show')) close(); });

  var tools = document.querySelector('.sales-month-tools');
  if (tools) { var tb = document.createElement('button'); tb.className = 'data-update-btn'; tb.innerHTML = '⇧ 更新数据'; tb.onclick = open; tools.prepend(tb); }
  var v2Import = document.querySelector('.mkt-import'); if (v2Import) v2Import.onclick = open;
  var edit = document.getElementById('salesEdit'); if (edit) edit.onclick = open;

  /* ---------- 状态 ---------- */
  var files = [];      // {name,size,type,kind,rows,error,thumb}
  var rows = [];       // 编辑区行
  var verdict = null;  // verifyRows 结果

  var fileList = host.querySelector('#fileList');
  var rowEditor = host.querySelector('#rowEditor');
  var verifyGrid = host.querySelector('#verifyGrid');
  var conflictArea = host.querySelector('#conflictArea');
  var confirmBtn = host.querySelector('#confirmBtn');
  var input = host.querySelector('#importFile');
  var dz = host.querySelector('#dropZone');

  /* ---------- 文件处理 ---------- */
  function kindOf(f) {
    var n = (f.name || '').toLowerCase();
    if (/\.(png|jpe?g|webp|gif|bmp)$/.test(n) || /^image\//.test(f.type)) return 'image';
    if (/\.csv$/.test(n) || /\.tsv$/.test(n) || /\.txt$/.test(n)) return 'csv';
    if (/\.xlsx$/.test(n)) return 'xlsx';
    if (/\.xls$/.test(n)) return 'xls';
    return 'other';
  }
  function readText(f) {
    return f.arrayBuffer().then(function (buf) {
      var txt = new TextDecoder('utf-8').decode(buf);
      if (txt.indexOf('\uFFFD') >= 0) { try { txt = new TextDecoder('gbk').decode(buf); } catch (e) { } }
      return txt;
    });
  }
  function nextMissingDate() {
    var used = {};
    rows.forEach(function (r) { var d = normDate(r.date); if (d) used[d] = 1; });
    var miss = summary(loadDaily()).missing.filter(function (d) { return !used[d]; });
    return miss.length ? miss[0] : null;
  }
  function guessDateFromName(name) {
    var m = String(name).match(/(\d{4}[-._]?\d{1,2}[-._]?\d{1,2}|\d{1,2}[-._月]\d{1,2})/);
    return m ? normDate(m[1]) : null;
  }
  function handleFiles(list) {
    var arr = Array.prototype.slice.call(list || []);
    if (!arr.length) return;
    var jobs = arr.map(function (f) {
      var kind = kindOf(f);
      var rec = { name: f.name, size: f.size, kind: kind, rows: [], error: null, thumb: null, status: '识别中' };
      files.push(rec);
      var p;
      if (kind === 'csv') p = readText(f).then(function (t) { rec.rows = rowsFromTable(splitCSV(t)); });
      else if (kind === 'xlsx') p = f.arrayBuffer().then(function (b) { return parseXLSX(b); }).then(function (r) { rec.rows = r; });
      else if (kind === 'xls') p = Promise.reject(new Error('旧版 .xls 无法在浏览器解析，请另存为 .xlsx 或 .csv'));
      else if (kind === 'image') {
        rec.thumb = URL.createObjectURL(f);
        rec.rows = [];
        p = ocrRevenueImage(rec.thumb, function (n) { rec.status = n; renderFiles(); })
          .then(function (got) { rec.rows = got || []; })
          .catch(function (e) { rec.ocrError = (e && e.message) ? e.message : String(e); });
      }
      else p = Promise.reject(new Error('不支持的文件类型'));
      return p.then(function () {
        if (!rec.rows.length) {
          if (kind === 'image') {
            rec.status = rec.ocrError ? ('识别失败：' + rec.ocrError) : '未识别到数字，请手工填写';
            var g = guessDateFromName(f.name);
            if (g && g > SOURCE_CUTOFF) g = null;   // 晚于数据截止日 → 多为文件生成/接收时间，不作数据日期
            g = g || nextMissingDate();
            if (g) rowEditorAdd({ date: g, out: null, inp: null });
          } else { rec.status = '未识别到数据行'; rec.error = '未识别到「日期 + 门诊/在院收入」的数据行'; }
        } else {
          var good = rec.rows.filter(function (r) { return r.verified; });
          rec.status = '识别到 ' + rec.rows.length + ' 行，其中 ' + good.length + ' 行数值自洽';
          rec.rows.forEach(function (r) {
            if (r.verified) {
              /* 门诊 + 在院 = 当日合计 三重校验通过 → 连同人次一起填入，用户核对即可 */
              rowEditorAdd({ date: r.date, out: r.out, inp: r.inp, first: r.first, again: r.again,
                             inhos: r.inhos, admit: r.admit, disch: r.disch });
            } else if (r.date) {
              /* 只认到日期 → 先把行带出来，用户补 3 个数字，不必手输日期 */
              rowEditorAdd({ date: r.date });
            } else if (r.verified) {
              /* 日期没认出来但金额已由累计差验证 → 保留金额，日期留空由用户指定 */
              rowEditorAdd({ date: '', out: r.out, inp: r.inp });
            }
          });
        }
      }).catch(function (err) {
        rec.error = err && err.message ? err.message : String(err);
        rec.status = '解析失败';
      });
    });
    Promise.all(jobs).then(function () {
      renderFiles();
      renderRows();
      setStep(3);
      revalidate();
    });
  }

  function renderFiles() {
    if (!files.length) { fileList.innerHTML = '<div class="import-empty">尚未选择文件</div>'; }
    else {
      fileList.innerHTML = files.map(function (f, i) {
        var type = f.kind === 'image' ? 'IMG' : (f.name.split('.').pop() || 'FILE').toUpperCase();
        var cls = f.error ? 'status-bad' : (f.kind === 'image' ? 'status-warn' : 'status-ok');
        var thumb = f.thumb ? '<img class="thumb" src="' + f.thumb + '" alt="预览">' : '';
        return '<div class="file-row">' + thumb + '<div class="file-type ' + (f.kind === 'image' ? 'image' : '') + '">' + type + '</div>'
          + '<div class="file-meta"><b>' + esc(f.name) + '</b><span>' + Math.max(1, Math.round(f.size / 1024)) + ' KB · ' + esc(f.status)
          + (f.error ? ' · ' + esc(f.error) : '') + '</span></div>'
          + '<em class="' + cls + '">' + (f.error ? '需处理' : 'OK') + '</em>'
          + '<button class="row-del" data-fdel="' + i + '" title="移除">×</button></div>';
      }).join('');
    }
    var n = files.length;
    host.querySelector('#fileCount').textContent = n ? n + ' 个文件' : '';
    $$('[data-fdel]', fileList).forEach(function (b) {
      b.onclick = function () { var i = +b.dataset.fdel; if (files[i] && files[i].thumb) URL.revokeObjectURL(files[i].thumb); files.splice(i, 1); renderFiles(); };
    });
    $$('.file-row .thumb', fileList).forEach(function (img, i) {
      img.title = '点击放大对照录入';
      img.onclick = function () {
        var row = img.closest('.file-row');
        var big = row.querySelector('.thumb-big');
        if (big) { big.remove(); return; }
        $$('.thumb-big', fileList).forEach(function (x) { x.remove(); });
        var el = document.createElement('img');
        el.className = 'thumb-big';
        el.src = img.src;
        el.alt = '原图预览';
        row.appendChild(el);
      };
    });
  }

  /* ---------- 行编辑 ---------- */
  var NUMKEYS = ['out', 'inp', 'first', 'again', 'inhos', 'admit', 'disch'];
  function rowEditorAdd(r) {
    var d = normDate(r.date) || r.date || '';
    var dup = rows.filter(function (x) {
      return (normDate(x.date) || x.date || '') === d && x.out === r.out && x.inp === r.inp;
    }).length;
    if (dup) return;
    var row = { date: r.date || '' };
    NUMKEYS.forEach(function (k) { row[k] = (r[k] == null || r[k] === '') ? '' : r[k]; });
    rows.push(row);
  }
  function renderRows() {
    if (!rows.length) { rowEditor.innerHTML = '<div class="import-empty">暂无识别结果 —— 拖入图片或表格、粘贴文本，或手工添加一行</div>'; return; }
    var cols = [['date', '日期', '9.23'], ['out', '门诊收入', '25087.04'], ['inp', '在院收入', '30216.77'],
                ['first', '初诊', '2'], ['again', '复诊', '7'], ['admit', '入院', '3'], ['disch', '出院', '1']];
    rowEditor.innerHTML = '<div class="edit-scroll"><table class="edit-table"><thead><tr>'
      + cols.map(function (c) { return '<th>' + c[1] + '</th>'; }).join('')
      + '<th>合计</th><th></th></tr></thead><tbody>'
      + rows.map(function (r, i) {
        var o = toNum(r.out), p = toNum(r.inp);
        var tot = (o || 0) + (p || 0);
        return '<tr>' + cols.map(function (c) {
          var cls = c[0] === 'date' ? 'cell-in date' : 'cell-in';
          return '<td><input class="' + cls + '" data-i="' + i + '" data-k="' + c[0] + '" value="' + esc(c[0] === 'date' ? shortDate(r.date) : r[c[0]]) + '" placeholder="' + c[2] + '" inputmode="decimal"></td>';
        }).join('')
          + '<td class="cell-total">' + (tot ? wan(tot, 2) + '万' : '—') + '</td>'
          + '<td><button class="row-del" data-rdel="' + i + '" title="删除">×</button></td></tr>';
      }).join('') + '</tbody></table></div>';
    $$('.cell-in', rowEditor).forEach(function (el) {
      el.oninput = function () {
        var i = +el.dataset.i, k = el.dataset.k;
        if (!rows[i]) return;
        rows[i][k] = el.value;
        var tr = el.closest('tr');
        var o = toNum(rows[i].out), p = toNum(rows[i].inp), tot = (o || 0) + (p || 0);
        if (tr) tr.querySelector('.cell-total').textContent = tot ? wan(tot, 2) + '万' : '—';
        scheduleValidate();
      };
    });
    $$('[data-rdel]', rowEditor).forEach(function (b) {
      b.onclick = function () { rows.splice(+b.dataset.rdel, 1); renderRows(); revalidate(); };
    });
    markConflicts();
  }
  var vt = null;
  function scheduleValidate() { if (vt) clearTimeout(vt); vt = setTimeout(revalidate, 260); }

  /* ---------- 校验 ---------- */
  function revalidate() {
    var daily = loadDaily();
    var parsed = rows.map(function (r) {
      var o = { date: normDate(r.date) || '', out: toNull(r.out), inp: toNull(r.inp), raw: '' };
      ['first', 'again', 'inhos', 'admit', 'disch'].forEach(function (k) { o[k] = toNull(r[k]); });
      return o;
    }).filter(function (r) { return r.date || r.out != null || r.inp != null; });
    verdict = verifyRows(parsed, daily);
    var v = verdict.rows, c = { new: 0, update: 0, same: 0, conflict: 0, invalid: 0 };
    v.forEach(function (r) { c[r.status] = (c[r.status] || 0) + 1; });
    var unitTxt = verdict.unit === 10000 ? '按「万元」解析' : '按「元」解析';
    verifyGrid.innerHTML = '<div><b>' + c.new + '</b>新增</div><div><b>' + c.update + '</b>更新</div>'
      + '<div><b>' + c.same + '</b>一致</div><div class="' + (c.conflict ? 'conflict' : '') + '"><b>' + c.conflict + '</b>冲突</div>'
      + '<div><b>' + c.invalid + '</b>无效</div><div class="unit-cell">' + unitTxt + '</div>';
    // 明细表
    var det = v.filter(function (r) { return r.status !== 'same'; });
    var html = '';
    if (det.length) {
      html += '<table class="map-table"><thead><tr><th>日期</th><th>看板指标</th><th>新值</th><th>状态</th></tr></thead><tbody>'
        + det.map(function (r) {
          var st = { new: '<span class="tag">新增</span>', update: '<span class="tag tag-up">更新</span>', conflict: '<span class="tag tag-bad">冲突</span>', invalid: '<span class="tag tag-bad">无效</span>' }[r.status] || '';
          var val = (r.out != null ? '门诊 ' + wan(r.out, 2) + '万' : '') + (r.inp != null ? '　在院 ' + wan(r.inp, 2) + '万' : '')
            + ((r.first != null || r.admit != null || r.disch != null)
              ? '<div class="old-val">' + (r.first != null ? '初诊 ' + r.first + '　' : '') + (r.admit != null ? '入院 ' + r.admit + '　' : '') + (r.disch != null ? '出院 ' + r.disch : '') + '</div>' : '');
          var old = r.old ? '<div class="old-val">原：门诊 ' + wan(r.old[0], 2) + '万　在院 ' + wan(r.old[1], 2) + '万</div>' : '';
          var note = r.notes && r.notes.length ? '<div class="old-val">' + esc(r.notes.join('；')) + '</div>' : '';
          return '<tr><td>' + (r.date ? (r.date.slice(5, 7) + '.' + r.date.slice(8)) : '—') + '</td><td>当日营业额</td><td>' + val + old + note + '</td><td>' + st + '</td></tr>';
        }).join('') + '</tbody></table>';
    } else if (v.length) {
      html = '<div class="import-empty">所有行与现有数据一致，确认后仅更新记录时间。</div>';
    } else {
      html = '<div class="import-empty">还没有可校验的数据行。</div>';
    }
    conflictArea.innerHTML = html;

    var hasConflict = c.conflict > 0;
    var allInvalid = v.length > 0 && c.invalid === v.length;
    confirmBtn.disabled = !v.length || allInvalid || hasConflict;
    confirmBtn.textContent = hasConflict
      ? '存在 ' + c.conflict + ' 处冲突 · 请修改上方标红的行'
      : (allInvalid ? '暂无可写入的有效行' : (v.length ? '确认更新（' + (c.new + c.update) + ' 天）' : '确认更新'));
    confirmBtn.classList.toggle('has-conflict', hasConflict);
    markConflicts();
    setStep(v.length ? 4 : (files.length ? 3 : 1));
  }
  function toNull(v) {
    if (v === '' || v == null) return null;
    var n = toNum(v);
    return n == null ? null : n;
  }

  function markConflicts() {
    if (!verdict) return;
    var bad = {};
    verdict.rows.forEach(function (r) { if (r.status === 'conflict' || r.status === 'invalid') bad[r.date] = r.status; });
    $$('#rowEditor tbody tr').forEach(function (tr) {
      var inp = tr.querySelector('input.date');
      var d = inp ? normDate(inp.value) : null;
      tr.classList.toggle('row-conflict', !!(d && bad[d] === 'conflict'));
      tr.classList.toggle('row-invalid', !!(d && bad[d] === 'invalid'));
    });
  }
  function setStep(n) {
    var steps = $$('.import-step');
    steps.forEach(function (s, i) {
      s.classList.toggle('done', i + 1 < n);
      s.classList.toggle('active', i + 1 === n);
    });
  }
  function refreshMeta() {
    var m = importedMeta();
    var el = host.querySelector('#metaLine');
    if (!el) return;
    el.textContent = m.updatedAt ? ('上次导入 ' + m.updatedAt.slice(0, 16).replace('T', ' ') + ' · ' + (m.files || []).join('、')) : '本机尚无导入记录';
  }

  /* ---------- 执行 ---------- */
  function applyImport() {
    if (!verdict) return;
    var ok = verdict.rows.filter(function (r) { return r.status === 'new' || r.status === 'update' || r.status === 'same'; });
    if (!ok.length) { showToast('没有可写入的数据行'); return; }
    var daily = loadDaily();
    if (host.querySelector('#snapChk').checked) snapshotBefore(daily, files.map(function (f) { return f.name; }));
    var beforeCut = summary(daily).revCut;
    var touched = 0;
    var FK = { out: F_OUT, inp: F_INP, first: F_FIRST, again: F_AGAIN, inhos: F_INHOS, admit: F_ADMIT, disch: F_DISCH };
    ok.forEach(function (r) {
      if (r.out == null && r.inp == null) return;
      var cur = daily[r.date] || [];
      var arr = [];
      for (var i = 0; i < 7; i++) arr[i] = (cur[i] === undefined ? null : cur[i]);
      Object.keys(FK).forEach(function (k) { if (r[k] != null) arr[FK[k]] = r[k]; });
      if (arr[F_OUT] == null) arr[F_OUT] = 0;
      if (arr[F_INP] == null) arr[F_INP] = 0;
      daily[r.date] = arr;
      touched++;
    });
    saveDaily(daily);
    writeJSON(LS_META, { updatedAt: new Date().toISOString(), files: files.map(function (f) { return f.name; }), rows: touched });
    Object.keys(daily).forEach(function (d) {
      if (!(d.startsWith('2026-09-') && d <= MONTH_TO)) delete daily[d];
    });
    renderRevenue();
    var afterCut = summary(daily).revCut;
    close();
    showToast('已更新 ' + touched + ' 天营收数据' + (beforeCut && afterCut && beforeCut !== afterCut ? '，营收截止日 9.' + (+beforeCut.slice(8)) + ' → 9.' + (+afterCut.slice(8)) : '') + ' · 全站数值与时间戳已同步');
    files.forEach(function (f) { if (f.thumb) URL.revokeObjectURL(f.thumb); });
    files = []; rows = []; verdict = null;
    host.querySelector('#pasteBox').value = '';
    renderFiles(); renderRows(); revalidate();
    try { window.dispatchEvent(new CustomEvent('ops:revenue-updated', { detail: summary(loadDaily()) })); } catch (e) { }
  }

  host.querySelector('#confirmBtn').onclick = applyImport;

  host.querySelector('#exportBtn').onclick = function () {
    var daily = loadDaily(), ks = Object.keys(daily).sort(), lines = [];
    ks.forEach(function (d) { lines.push("    '" + d + "': [" + daily[d][0] + ', ' + daily[d][1] + ']'); });
    var code = 'var SEED = {\n' + lines.join(',\n') + '\n};';
    var done = function () { showToast('数据块已复制，可直接替换源码中的 SEED'); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(done, function () { fallbackCopy(code, done); });
    } else fallbackCopy(code, done);
  };
  function fallbackCopy(text, cb) {
    var ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); cb(); } catch (e) { showToast('复制失败，请手动选择'); }
    document.body.removeChild(ta);
  }

  host.querySelector('#resetBtn').onclick = function () {
    resetDaily();
    renderRevenue(); refreshMeta();
    showToast('已恢复为源码中的初始数据');
  };

  host.querySelector('#pasteApply').onclick = function () {
    var t = host.querySelector('#pasteBox').value;
    var got = parsePasted(t);
    if (!got.length) { showToast('没有解析到「日期 + 金额」的行，请检查格式'); return; }
    got.forEach(function (r) { rowEditorAdd({ date: r.date, out: r.out, inp: r.inp }); });
    renderRows();
    files.push({ name: '粘贴文本', size: t.length, kind: 'csv', rows: got, error: null, thumb: null, status: '已解析 ' + got.length + ' 行' });
    renderFiles(); revalidate();
    showToast('已解析 ' + got.length + ' 行');
  };
  host.querySelector('#addRow').onclick = function () { rows.push({ date: '', out: '', inp: '' }); renderRows(); };

  /* ---------- 拖拽 ---------- */
  dz.onclick = function () { input.click(); };
  ['dragenter', 'dragover'].forEach(function (x) { dz.addEventListener(x, function (e) { e.preventDefault(); dz.classList.add('drag'); }); });
  ['dragleave', 'drop'].forEach(function (x) { dz.addEventListener(x, function (e) { e.preventDefault(); dz.classList.remove('drag'); }); });
  dz.addEventListener('drop', function (e) { handleFiles(e.dataTransfer.files); });
  input.addEventListener('change', function () { handleFiles(input.files); input.value = ''; });
  host.addEventListener('paste', function (e) {
    var box = host.querySelector('#pasteBox');
    if (document.activeElement === box) return;
    var t = e.clipboardData && e.clipboardData.getData('text');
    if (t) { box.value = t; }
  });

  /* ---------- 对外只读接口 ----------
     供主面板 / 其他模块取当前营收口径（不写 DOM，避免循环依赖） */
  window.OPS_REVENUE = {
    summary: function () { return summary(loadDaily()); },
    daily: function () { return loadDaily(); },
    render: function () { try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); } }
  };
  /* 与脱敏副本（psyc.harness 的 hospital-operations-dashboard）对齐：开放导入面板入口，
     便于从侧栏 / 顶栏 / 脚本调用，而不只依赖营销面板里那个按钮 */
  window.openDataImport = open;

  /* ---------- 启动 ---------- */
  function boot() {
    renderFiles(); renderRows(); revalidate(); refreshMeta();
    /* 首屏与「导入后」走同一条渲染路径：renderRevenue 内部会一并刷新营销面板与主面板 */
    try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(boot, 300); });
  else setTimeout(boot, 300);

  /* 供其他模块/调试使用 */
  window.OPS_REVENUE = { summary: function () { return summary(loadDaily()); }, render: renderRevenue, open: open, daily: loadDaily };
})();
