# -*- coding: utf-8 -*-
"""「更新数据」链路修复：人数写入失效 + 在院人数归 0 + 若干处不同步

背景（2026-09-27 本地实测发现，均为真实缺陷）
 ① verifyRows() 构造 rec 时丢掉 first/again/inhos/admit/disch 五个字段
    → applyImport() 里 `if (r.first != null)` 恒不成立 → **导入面板的人数完全写不进去**
 ② 因 ① 叠加 `summarize()` 的 `ward: last.ward || 0`
    → 导入任一天营收（未填在院人数）会让「在院人数」显示 0
    （月面板 KPI / 预警 / 营销报告 mcr 全部中招）
 ③ rowEditor 没有「在院」输入列 → 用户无法录入在院人数
 ④ rangeChip 只在 mount() 写一次，导入后仍显示旧营收日
 ⑤ 问题地图（.problem-lane）是写死字符串，导入后不更新
 ⑥ mcr / 月面板若干标签写死（9.1—9.25累计、5天日均、9月25日日终、25天累计…）

本补丁只改代码，不动任何业务数据（SEED 保持不变）。
"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []


def rep(fn, old, new, tag, cnt=1):
    p = R + fn
    s = io.open(p, encoding='utf-8').read()
    n = s.count(old)
    if n != cnt:
        fails.append('%-26s %-46s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-26s %-46s %d' % (fn, tag, n))


# ═══════════════════ ① data-import.js：verifyRows 保留人数字段 ═══════════════════
rep('data-import.js',
    "      var rec = { date: r.date, out: o, inp: p, raw: r.raw, notes: [] };",
    "      var rec = { date: r.date, out: o, inp: p, raw: r.raw, notes: [] };\n"
    "      /* ⚠ 原先这里只带 date/out/inp/raw，把人数全部丢掉，导致 applyImport() 里\n"
    "         `if (r.first != null) arr[F_FIRST] = r.first` 恒不成立 —— 识别结果表里\n"
    "         填的初诊/复诊/在院/入院/出院**一个都写不进去**。此处按原样透传。 */\n"
    "      ['first', 'again', 'inhos', 'admit', 'disch'].forEach(function (k) {\n"
    "        if (r[k] != null) rec[k] = r[k];\n"
    "      });",
    'verifyRows 透传人数字段')

# ═══════════════════ ② data-import.js：识别结果表补「在院」列 ═══════════════════
rep('data-import.js',
    "    var cols = [['date', '日期', '9.23'], ['out', '门诊收入', '25087.04'], ['inp', '在院收入', '30216.77'],\n"
    "                ['first', '初诊', '2'], ['again', '复诊', '7'], ['admit', '入院', '3'], ['disch', '出院', '1']];",
    "    var cols = [['date', '日期', '9.23'], ['out', '门诊收入', '25087.04'], ['inp', '在院收入', '30216.77'],\n"
    "                ['first', '初诊', '2'], ['again', '复诊', '7'], ['inhos', '在院', '31'],\n"
    "                ['admit', '入院', '3'], ['disch', '出院', '1']];",
    '识别表补「在院」列')

# ═══════════════════ ③ september-revenue-data.js：在院人数取「最近有填报日」 ═══════════════════
rep('september-revenue-data.js',
    "  function summarize(list) {\n"
    "    var last = list[list.length - 1] || {};\n"
    "    return {\n"
    "      days: list.length,\n"
    "      total: sum(list, 'total'),\n"
    "      outpatient: sum(list, 'outpatient'),\n"
    "      inpatient: sum(list, 'inpatient'),\n"
    "      first: sum(list, 'first'),\n"
    "      repeat: sum(list, 'repeat'),\n"
    "      visits: sum(list, 'first') + sum(list, 'repeat'),\n"
    "      admissions: sum(list, 'admit'),\n"
    "      discharges: sum(list, 'dischargeFirst') + sum(list, 'dischargeRepeat'),\n"
    "      ward: last.ward || 0,\n"
    "      average: list.length ? sum(list, 'total') / list.length : 0\n"
    "    };\n"
    "  }",
    "  function summarize(list) {\n"
    "    var last = list[list.length - 1] || {};\n"
    "    /* ⚠ 「在院人数」是**时点值**、不是可加量：取区间内最后一个**有填报**的日期。\n"
    "       原先写 last.ward || 0 —— 只要最后一天没填该字段（导入营收时很常见），\n"
    "       在院人数就会直接变成 0，月面板/营销报告会一起显示「在院 0 人」。\n"
    "       现在缺字段的日期自动向前回退，并记录实际时点 wardAt。 */\n"
    "    var wardV = null, wardAt = '';\n"
    "    for (var wi = list.length - 1; wi >= 0; wi--) {\n"
    "      if (list[wi].ward != null) { wardV = list[wi].ward; wardAt = list[wi].date; break; }\n"
    "    }\n"
    "    return {\n"
    "      days: list.length,\n"
    "      total: sum(list, 'total'),\n"
    "      outpatient: sum(list, 'outpatient'),\n"
    "      inpatient: sum(list, 'inpatient'),\n"
    "      first: sum(list, 'first'),\n"
    "      repeat: sum(list, 'repeat'),\n"
    "      visits: sum(list, 'first') + sum(list, 'repeat'),\n"
    "      admissions: sum(list, 'admit'),\n"
    "      discharges: sum(list, 'dischargeFirst') + sum(list, 'dischargeRepeat'),\n"
    "      dischargeFirst: sum(list, 'dischargeFirst'),\n"
    "      dischargeRepeat: sum(list, 'dischargeRepeat'),\n"
    "      ward: wardV,\n"
    "      wardAt: wardAt,\n"
    "      average: list.length ? sum(list, 'total') / list.length : 0\n"
    "    };\n"
    "  }",
    'summarize·在院取最近有值')

rep('september-revenue-data.js',
    "  function lastDay() { return data.rows.length ? Number(data.rows[data.rows.length - 1].date.slice(8)) : 0; }",
    "  function lastDay() { return data.rows.length ? Number(data.rows[data.rows.length - 1].date.slice(8)) : 0; }\n"
    "  /* 全站统一的「最新在院人数」取值：最后一个有填报的日期（缺字段自动回退）。\n"
    "     各面板请用它，不要再直接取 rows 最后一行 —— 见 summarize() 里的说明。 */\n"
    "  function lastWard() {\n"
    "    for (var i = data.rows.length - 1; i >= 0; i--) {\n"
    "      if (data.rows[i].ward != null) return { value: data.rows[i].ward, date: data.rows[i].date };\n"
    "    }\n"
    "    return { value: null, date: '' };\n"
    "  }",
    '新增 lastWard()')

rep('september-revenue-data.js',
    "  data.subset = subset;",
    "  data.subset = subset;\n  data.lastWard = lastWard;",
    '导出 lastWard')

io.open('/dev/null', 'w')
print('=== 第一批（数据层）完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
