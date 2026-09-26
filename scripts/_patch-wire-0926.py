#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task 3：把「营收日报 → 主面板」的通路接上。

现状（已用 grep 确认）：renderRevenue() 只写营销面板，主面板的
.ov-target / #heroKpis / .ov-two / .ov-gap / .ov-bar 命中 0 次，
Hero 的「在院 / 入院 / 出院 / 门诊」是写死的字面量 → 导入营收图片后主面板不动。

做法：在 data-import.js 里新增 renderMainPanel(daily, s)，由 renderRevenue() 末尾调用。
      这样**所有**入口（图片 / CSV / XLSX / 粘贴 / 手工改行 / 恢复初始）都会同步，
      不需要每个入口各写一遍。
"""
import io, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, 'data-import.js')
s = io.open(P, encoding='utf-8').read()
before = len(s)
fails = []

# ────────────────────────── 1. renderRevenue 末尾调用主面板渲染
OLD_CALL = """    /* ---- 数据口径风险卡里的营收部分 ---- */
    $$('.mkt-data-warning p').forEach(function (e) {
      e.innerHTML = e.innerHTML.replace(/营收日报[^；。]*[；。]/, '营收日报已更新至 ' + revTxt + '；');
    });
  }
"""
NEW_CALL = """    /* ---- 数据口径风险卡里的营收部分 ---- */
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
"""
rep_n = s.count(OLD_CALL)
if rep_n != 1:
    fails.append('renderRevenue 末尾锚点 匹配 %d（期望 1）' % rep_n)
else:
    s = s.replace(OLD_CALL, NEW_CALL)

# ────────────────────────── 2. 同时同步营销面板「环比分析」卡里的 2 行营收口径值
OLD_PRIO = """      var pmP = $('.priority-compare .mkt-card-head p');
      if (pmP) pmP.textContent = shortRange(s.twDays) + ' 与上周同期 ' + shortRange(s.sameDays) + ' 同口径（各 ' + s.tw.n + ' 天）';"""
NEW_PRIO = """      var pmP = $('.priority-compare .mkt-card-head p');
      if (pmP) pmP.textContent = shortRange(s.twDays) + ' 与上周同期 ' + shortRange(s.sameDays) + ' 同口径（各 ' + s.tw.n + ' 天）';
      /* 营收日报能直接推的两行：营业额 / 营销入院（其余行来自客服与管家的独立台账，不由图片驱动） */
      for (var i4 = 0; i4 < kids.length; i4++) {
        if (kids[i4].tagName !== 'B') continue;
        var t4 = kids[i4].textContent;
        if (/^营业额/.test(t4)) {
          kids[i4].innerHTML = '营业额（' + s.tw.n + ' 天）';
          if (kids[i4 + 1]) kids[i4 + 1].innerHTML = wan(s.same.t, 2) + '万';
          if (kids[i4 + 2]) kids[i4 + 2].innerHTML = wan(s.tw.t, 2) + '万';
          if (kids[i4 + 3]) {
            kids[i4 + 3].className = (s.delta == null ? '' : (s.delta >= 0 ? 'good' : 'bad'));
            kids[i4 + 3].innerHTML = s.delta == null ? '—' : sign(s.delta, 1) + '%';
          }
        } else if (/^营销入院/.test(t4)) {
          kids[i4].innerHTML = '营销入院（' + s.tw.n + ' 天）';
          if (kids[i4 + 1]) kids[i4 + 1].innerHTML = s.same.p.admit + '人';
          if (kids[i4 + 2]) kids[i4 + 2].innerHTML = s.tw.p.admit + '人';
          if (kids[i4 + 3]) {
            var d3 = s.same.p.admit ? (s.tw.p.admit - s.same.p.admit) / s.same.p.admit * 100 : null;
            kids[i4 + 3].className = d3 == null ? '' : (d3 >= 0 ? 'good' : 'bad');
            kids[i4 + 3].innerHTML = d3 == null ? '—' : sign(d3, 1) + '%';
          }
        }
      }"""
rep_n = s.count(OLD_PRIO)
if rep_n != 1:
    fails.append('priority-compare 锚点 匹配 %d（期望 1）' % rep_n)
else:
    s = s.replace(OLD_PRIO, NEW_PRIO)

# ────────────────────────── 3. boot 里也触发一次（首屏无导入时也要对齐）
OLD_BOOT = """  function boot() {
    renderFiles(); renderRows(); revalidate(); refreshMeta();
    try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); }
  }"""
NEW_BOOT = """  function boot() {
    renderFiles(); renderRows(); revalidate(); refreshMeta();
    /* 首屏与「导入后」走同一条渲染路径：renderRevenue 内部会一并刷新营销面板与主面板 */
    try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); }
  }"""
rep_n = s.count(OLD_BOOT)
if rep_n != 1:
    fails.append('boot 锚点 匹配 %d（期望 1）' % rep_n)
else:
    s = s.replace(OLD_BOOT, NEW_BOOT)

# ────────────────────────── 4. 暴露只读接口（便于外部模块与测试复用）
OLD_END = """  /* ---------- 启动 ---------- */"""
NEW_END = """  /* ---------- 对外只读接口 ----------
     供主面板 / 其他模块取当前营收口径（不写 DOM，避免循环依赖） */
  window.OPS_REVENUE = {
    summary: function () { return summary(loadDaily()); },
    daily: function () { return loadDaily(); },
    render: function () { try { renderRevenue(); } catch (e) { console.warn('renderRevenue', e); } }
  };

  /* ---------- 启动 ---------- */"""
rep_n = s.count(OLD_END)
if rep_n != 1:
    fails.append('接口锚点 匹配 %d（期望 1）' % rep_n)
else:
    s = s.replace(OLD_END, NEW_END)

if fails:
    print('✗ 有 %d 处未按预期匹配，未写文件：' % len(fails))
    for f in fails:
        print('   -', f)
    sys.exit(1)

io.open(P, 'w', encoding='utf-8').write(s)
print('✓ 已写 data-import.js（%d → %d B，%+d）' % (before, len(s), len(s) - before))
