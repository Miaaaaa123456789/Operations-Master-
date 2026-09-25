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
  var SOURCE_CUTOFF = '2026-09-24';   // 其他数据源（客服/心理/管家/团体）的共同截止日
  var TODAY = '2026-09-25';           // 抓取日
  var DOW = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

  /* ============================ 种子数据 ============================
     9.1—9.22 逐日营业日报（单位：元）｜ 9.1—9.14 取自 data/daily-sales/2026-09.csv
     9.15 由 9.16 环比反推、9.16—9.22 取自业主营收日报截图
     合计 9.1—9.22 = 1,538,866.16 元（153.89 万），与看板现值一致
     ================================================================ */
  var SEED = {
    '2026-09-01': [8329.46, 13695.01],
    '2026-09-02': [16747.27, 62605.00],
    '2026-09-03': [4710.35, 35411.99],
    '2026-09-04': [31464.50, 40703.93],
    '2026-09-05': [15041.96, 39769.70],
    '2026-09-06': [140116.70, 43682.69],
    '2026-09-07': [20267.31, 39148.42],
    '2026-09-08': [21632.61, 36448.39],
    '2026-09-09': [17044.52, 41666.05],
    '2026-09-10': [10042.88, 36522.53],
    '2026-09-11': [9814.03, 38027.06],
    '2026-09-12': [18029.88, 33831.37],
    '2026-09-13': [133002.16, 31013.81],
    '2026-09-14': [20100.68, 15521.66],
    '2026-09-15': [34846.27, 43388.86],
    '2026-09-16': [13958.85, 28288.75],
    '2026-09-17': [34398.72, 28935.61],
    '2026-09-18': [40570.20, 32821.31],
    '2026-09-19': [99908.85, 37754.86],
    '2026-09-20': [27228.16, 33779.66],
    '2026-09-21': [22568.92, 30721.41],
    '2026-09-22': [25087.04, 30216.77]
  };

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
      var s = SEED[k];
      if (!s || s[0] !== daily[k][0] || s[1] !== daily[k][1]) ov[k] = daily[k];
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
    days.forEach(function (d) {
      var v = daily[d]; if (!v) return;
      if (v[0] != null) o += v[0];
      if (v[1] != null) i += v[1];
      hit++;
    });
    return { o: o, i: i, t: o + i, n: hit, days: days.slice() };
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
    return {
      tw: tw, lw: lw, same: same, sameDays: sameDays, mtd: mtd, mDays: mDays,
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

    /* ---- 收入结构（上周完整周） ---- */
    if (s.lw.t) {
      var oPct = s.lw.o / s.lw.t * 100, iPct = s.lw.i / s.lw.t * 100;
      $$('.mkt-ring div').forEach(function (e) {
        e.innerHTML = '<b>' + wan(s.lw.t, 2) + '万</b>上周完整周';
      });
      var lg = $$('.mkt-legend span');
      if (lg[0]) lg[0].innerHTML = '<b style="color:#26ae81">' + oPct.toFixed(1) + '%</b>门诊 ' + wan(s.lw.o, 2) + '万';
      if (lg[1]) lg[1].innerHTML = '<b style="color:#2e8ee9">' + iPct.toFixed(1) + '%</b>住院 ' + wan(s.lw.i, 2) + '万';
    }

    /* ---- 逐日明细表（上周完整周） ---- */
    var tbl = $('.mkt-day-table');
    if (tbl && s.lwDays.length) {
      var tb = tbl.querySelector('tbody'), tf = tbl.querySelector('tfoot');
      var mx = Math.max.apply(null, s.lwDays.map(function (d) { return (daily[d][0] || 0) + (daily[d][1] || 0); }));
      var mn = Math.min.apply(null, s.lwDays.map(function (d) { return (daily[d][0] || 0) + (daily[d][1] || 0); }));
      var rowsHtml = '', prev = null;
      s.lwDays.forEach(function (d) {
        var amt = (daily[d][0] || 0) + (daily[d][1] || 0);
        var diffTxt = '—', diffCls = '';
        if (prev) { var r = (amt - prev) / prev * 100; diffTxt = sign(r, 1) + '%'; diffCls = r >= 0 ? 'up' : 'down'; }
        var judge = '常态', jcls = '';
        if (amt === mx) { judge = '峰值'; jcls = 'up'; }
        else if (amt === mn) { judge = '低谷'; jcls = 'down'; }
        else if (prev != null && amt > prev) { judge = '回升'; jcls = 'up'; }
        else if (prev != null && amt < prev) { judge = '回落'; jcls = 'down'; }
        var we = isWeekend(d) ? ' class="weekend"' : '';
        rowsHtml += '<tr' + we + '><td>' + (+d.slice(5, 7)) + '.' + (+d.slice(8)) + ' ' + dowOf(d) + '</td><td><strong>' + wan(amt, 2) + '万</strong></td><td class="' + diffCls + '">' + diffTxt + '</td><td>' + (amt / s.lw.t * 100).toFixed(1) + '%</td><td class="' + jcls + '">' + judge + '</td></tr>';
        prev = amt;
      });
      if (tb) tb.innerHTML = rowsHtml;
      if (tf) tf.innerHTML = '<tr><td>完整周合计</td><td>' + wan(s.lw.t, 2) + '万</td><td>日均' + wan(s.lwAvg, 2) + '万</td><td>100%</td><td>关键日集中</td></tr>';
      var head = tbl.closest('.mkt-card');
      if (head) {
        var hp = head.querySelector('.mkt-card-head p');
        if (hp) hp.textContent = '最近完整周 ' + shortRange(s.lwDays) + ' · 营收日报口径';
        var hb = head.querySelector('.mkt-badge');
        if (hb) hb.textContent = '周末贡献 ' + s.weShare.toFixed(1) + '%';
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
    if (insights.length >= 4 && s.lwDays.length) {
      var minD = s.lwDays[0], maxD = s.lwDays[0];
      s.lwDays.forEach(function (d) {
        var a = (daily[d][0] || 0) + (daily[d][1] || 0);
        if (a < (daily[minD][0] || 0) + (daily[minD][1] || 0)) minD = d;
        if (a > (daily[maxD][0] || 0) + (daily[maxD][1] || 0)) maxD = d;
      });
      var minA = (daily[minD][0] || 0) + (daily[minD][1] || 0);
      var maxA = (daily[maxD][0] || 0) + (daily[maxD][1] || 0);
      insights[0].querySelector('b').textContent = dowOf(minD) + '收入仅' + wan(minA, 2) + '万';
      insights[1].querySelector('b').textContent = dowOf(maxD) + '单日贡献' + (maxA / s.lw.t * 100).toFixed(1) + '%';
      var g4 = insights[3];
      if (g4) {
        g4.querySelector('b').textContent = '本周营收已有及时口径';
        g4.querySelector('span').textContent = shortRange(s.twDays) + '合计' + wan(s.tw.t, 2) + '万、日均' + num(s.twAvg, 2) + '万'
          + (s.delta == null ? '' : '，比上周同期' + (s.delta >= 0 ? '增长' : '下降') + Math.abs(s.delta).toFixed(1) + '%')
          + (s.missing.length ? '（' + shortRange(s.missing) + ' 日报待补）' : '') + '。';
      }
    }

    /* ---- 口径说明 ---- */
    var src = $('.mkt-source');
    if (src) {
      src.textContent = '口径：本周至今为 9.21—9.27（各源数据截至 ' + cutTxt + '，营收日报至 ' + revTxt + '）；上周完整周为 ' + shortRange(s.lwDays) + '（营收 ' + wan(s.lw.t, 2) + ' 万 ＝ 门诊 ' + wan(s.lw.o, 2) + ' ＋ 在院 ' + wan(s.lw.i, 2) + '）；月度目标 ' + MONTH_TARGET + ' 万，累计 ' + wan(s.mtd.t, 2) + ' 万（' + (s.cut ? (+s.cut.slice(5, 7)) + '月' + (+s.cut.slice(8)) + '日' : '—') + '）。导入新数据后先校验冲突，再更新看板。';
    }

    /* ---- 数据口径风险卡里的营收部分 ---- */
    $$('.mkt-data-warning p').forEach(function (e) {
      e.innerHTML = e.innerHTML.replace(/营收日报[^；。]*[；。]/, '营收日报已更新至 ' + revTxt + '；');
    });
  }

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
    + '<span>CSV / XLSX 自动解析并抓取日期、门诊收入、在院收入；图片显示预览，数值在下方确认</span></div>'
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
      else if (kind === 'image') { rec.thumb = URL.createObjectURL(f); rec.rows = []; p = Promise.resolve(); }
      else p = Promise.reject(new Error('不支持的文件类型'));
      return p.then(function () {
        if (!rec.rows.length) {
          if (kind === 'image') {
            rec.status = '待确认数值';
            var g = guessDateFromName(f.name);
            if (g && g > SOURCE_CUTOFF) g = null;   // 晚于数据截止日 → 多为文件生成/接收时间，不作数据日期
            g = g || nextMissingDate();
            if (g) rowEditorAdd({ date: g, out: null, inp: null });
          } else { rec.status = '未识别到数据行'; rec.error = '未识别到「日期 + 门诊/在院收入」的数据行'; }
        } else {
          rec.status = '已解析 ' + rec.rows.length + ' 行';
          rec.rows.forEach(function (r) { rowEditorAdd({ date: r.date, out: r.out, inp: r.inp }); });
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
  function rowEditorAdd(r) {
    var dup = rows.filter(function (x) { return x.date === r.date && x.out === r.out && x.inp === r.inp; }).length;
    if (dup) return;
    rows.push({ date: r.date || '', out: r.out == null ? '' : r.out, inp: r.inp == null ? '' : r.inp });
  }
  function renderRows() {
    if (!rows.length) { rowEditor.innerHTML = '<div class="import-empty">暂无识别结果 —— 拖入文件、粘贴文本，或手工添加一行</div>'; return; }
    rowEditor.innerHTML = '<table class="edit-table"><thead><tr><th>日期</th><th>门诊收入</th><th>在院收入</th><th>合计</th><th></th></tr></thead><tbody>'
      + rows.map(function (r, i) {
        var o = toNum(r.out), p = toNum(r.inp);
        var tot = (o || 0) + (p || 0);
        return '<tr>'
          + '<td><input class="cell-in date" data-i="' + i + '" data-k="date" value="' + esc(shortDate(r.date)) + '" placeholder="9.23"></td>'
          + '<td><input class="cell-in" data-i="' + i + '" data-k="out" value="' + esc(r.out) + '" placeholder="25087.04" inputmode="decimal"></td>'
          + '<td><input class="cell-in" data-i="' + i + '" data-k="inp" value="' + esc(r.inp) + '" placeholder="30216.77" inputmode="decimal"></td>'
          + '<td class="cell-total">' + (tot ? wan(tot, 2) + '万' : '—') + '</td>'
          + '<td><button class="row-del" data-rdel="' + i + '" title="删除">×</button></td></tr>';
      }).join('') + '</tbody></table>';
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
      return { date: normDate(r.date) || '', out: toNull(r.out), inp: toNull(r.inp), raw: '' };
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
          var val = (r.out != null ? '门诊 ' + wan(r.out, 2) + '万' : '') + (r.inp != null ? '　在院 ' + wan(r.inp, 2) + '万' : '');
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
    ok.forEach(function (r) {
      if (r.out == null && r.inp == null) return;
      daily[r.date] = [r.out == null ? 0 : r.out, r.inp == null ? 0 : r.inp];
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

  /* ---------- 启动 ---------- */
  function boot() {
    renderFiles(); renderRows(); revalidate(); refreshMeta();
    try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(boot, 300); });
  else setTimeout(boot, 300);

  /* 供其他模块/调试使用 */
  window.OPS_REVENUE = { summary: function () { return summary(loadDaily()); }, render: renderRevenue, open: open, daily: loadDaily };
})();
