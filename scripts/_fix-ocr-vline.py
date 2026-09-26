# -*- coding: utf-8 -*-
"""营收日报图片识别：改用「表格竖线」定列 + 按字符高定放大倍数

业主诉求：图片识别需要往更稳定的方向优化（部分关键金额数字识别有误）。

本地实测（854×248 微信营收日报截图，7 天 × 14 列，英文 eng 模型）：
  · 整图识别（×1—×4，psm 6）→ 大额数字全区间误识（"99908.85" → "s0908.85"）
  · psm 7（单行）→ 40 个组合全部 0 命中（现有代码用 psm 6 是对的）
  · 逐块 ×3 → 门诊收入 / 在院收入 / 当日合计三列命中正确值，×5—×8 明显变差
  · 现有 inkCuts 在同一张图上切出 43 个切点（把数字间空隙也当列间隙），
    且切点落在数字中间 → 当月累计列整列读不出

结论与改法
① 换列检测：新增 analyzeTable()，用「表格竖线」定列边界。
   竖线特征：水平宽度 ≤3px + 表格全高范围内几乎每行都有墨。
   实测：13 条竖线全部命中（另含左右边缘与初诊/复诊分隔线），与表头列逐一对齐。
② 换倍数口径：由「按块宽凑 1200px」改为「按字符高凑 60px」。
   字符高从数据行带高度估出（本图 20px → ×3），夹在 2—6 倍。
③ 重叠缩小：列边界既已是精确竖线，重叠由块宽 10% 降到 3%（±2px 起）。
④ 旧 inkCuts / token 法保留为逐级回退，非表格类图片行为不变。
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
        fails.append('%-16s %-42s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-16s %-42s %d' % (fn, tag, n))


# ══════════════════ ① 新增 analyzeTable()（竖线定列 + 字符高估计） ══════════════════
ANALYZE = r"""  /* ---- 表格结构分析：用「表格竖线」定列边界 ----
     为什么不用「列墨量低 → 判为间隙」：本类营收日报数字之间的空隙与列间空隙宽度相当，
     会把数字切两半（实测同一张图切出 43 列）。而表格竖线是可靠的结构特征：
       ① 水平宽度极窄（1—3px）
       ② 在表格全高范围内几乎每一行都有墨
     实测 854×248 的营收日报：13 条竖线全部命中，与表头 14 列逐一对齐。
     返回 { cols:[列边界x…], charH:字符高, rows:数据行数, hlines:横线数 } */
  function analyzeTable(img) {
    var res = { cols: [], charH: 0, rows: 0, hlines: 0 };
    var c = document.createElement('canvas');
    c.width = img.width; c.height = img.height;
    var g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0);
    var d, p;
    try { d = g.getImageData(0, 0, c.width, c.height); p = d.data; } catch (e) { return res; }
    var W = c.width, H = c.height, x, y;
    var dark = function (xx, yy) {
      var i = (yy * W + xx) * 4;
      return (p[i] < 170 && p[i + 1] < 170 && p[i + 2] < 170);
    };
    /* 行墨量 → 横向表格线（>50% 图宽） */
    var rowInk = new Uint32Array(H);
    for (y = 0; y < H; y++) {
      var n = 0, base = y * W * 4;
      for (x = 0; x < W; x++) {
        var i2 = base + x * 4;
        if (p[i2] < 170 && p[i2 + 1] < 170 && p[i2 + 2] < 170) n++;
      }
      rowInk[y] = n;
    }
    var isLine = new Uint8Array(H), hlines = [];
    for (y = 0; y < H; y++) if (rowInk[y] > W * 0.5) { isLine[y] = 1; hlines.push(y); }
    res.hlines = hlines.length;
    if (hlines.length < 3) return res;                 // 没有表格结构 → 交给旧算法
    var top = hlines[0], bot = hlines[hlines.length - 1];
    var tableH = bot - top + 1;
    /* 数据行带：top 之后、由横线分隔的连续墨行 */
    var bands = [], st = -1;
    for (y = top; y <= bot; y++) {
      var v = isLine[y] ? 0 : rowInk[y];
      if (v > 2) { if (st < 0) st = y; }
      else if (st >= 0) { if (y - st >= 6) bands.push([st, y - 1]); st = -1; }
    }
    if (st >= 0 && bot - st >= 6) bands.push([st, bot]);
    if (bands.length < 2) return res;
    res.rows = bands.length;
    /* 字符高：取数据行带高度的中位数 */
    var hs = bands.map(function (b) { return b[1] - b[0] + 1; })
                  .sort(function (a, b) { return a - b; });
    res.charH = hs[Math.floor(hs.length / 2)] || 0;
    /* 每个 x 的「全高墨量」与「覆盖行带数」 */
    var full = new Uint32Array(W), cover = new Uint32Array(W);
    for (y = top; y <= bot; y++) {
      var b2 = y * W * 4;
      for (x = 0; x < W; x++) {
        var i3 = b2 + x * 4;
        if (p[i3] < 170 && p[i3 + 1] < 170 && p[i3 + 2] < 170) full[x]++;
      }
    }
    var nb = bands.length;
    for (var bi = 0; bi < nb; bi++) {
      var y0 = bands[bi][0], y1 = bands[bi][1];
      for (x = 0; x < W; x++) {
        for (y = y0; y <= y1; y++) { if (dark(x, y)) { cover[x]++; break; } }
      }
    }
    /* 竖线候选：覆盖行带数 ≥ nb-1，按相邻 ≤2px 聚类 */
    var groups = [], cur = null;
    for (x = 0; x < W; x++) {
      if (cover[x] >= nb - 1) {
        if (cur && x - cur[cur.length - 1] <= 2) cur.push(x);
        else { cur = [x]; groups.push(cur); }
      }
    }
    var cols = [];
    groups.forEach(function (gr) {
      if (gr.length > 3) return;                       // 太宽 → 是数字内容，不是线
      var mx = 0;
      gr.forEach(function (xx) { if (full[xx] > mx) mx = full[xx]; });
      if (mx < tableH * 0.85) return;                  // 墨量不足 → 不是贯穿线
      cols.push(Math.round((gr[0] + gr[gr.length - 1]) / 2));
    });
    /* 去掉贴着右边界的（最后一列之后通常是空白），保留作为右边界 */
    res.cols = cols;
    return res;
  }

  /* ---- 按「图像白列」找列切点（旧法，作为回退） ---- */
  function inkCuts(img) {"""

rep('data-import.js',
    "  /* ---- 按「图像白列」找列切点（不依赖 OCR） ----\n  function inkCuts(img) {",
    ANALYZE,
    '新增 analyzeTable()')

# ══════════════════ ② 切点来源：竖线优先 ══════════════════
rep('data-import.js',
    "      var cuts = inkCuts(img);\n      var cutSrc = 'ink';",
    "      /* ⭐ 优先用「表格竖线」定列（见 analyzeTable 的说明）；\n"
    "         竖线法不适用于非表格图时，逐级回退到旧的白列法 / token 法。 */\n"
    "      var tbl = analyzeTable(img);\n"
    "      var charH = tbl.charH || medH || 10;\n"
    "      var cuts = tbl.cols;\n"
    "      var cutSrc = 'vline';\n"
    "      if (cuts.length < 2) { cuts = inkCuts(img); cutSrc = 'ink'; }",
    '切点来源改竖线优先')

# ══════════════════ ③ 重叠缩小（边界已是精确竖线） ══════════════════
rep('data-import.js',
    "        /* 留 10% 块宽的重叠，避免边界数字被切断。\n"
    "           ⚠ 原先用全图宽的 6%（854px → 51px），块本身只有 180px 左右，\n"
    "           两边各加 51px 会把邻列整块卷进来，倍数也被迫降低。改为按块宽算。 */\n"
    "        var ov = Math.max(2, Math.round((x1 - x0) * 0.10));",
    "        /* 留少量重叠，避免边界数字被切断。\n"
    "           竖线法的边界本身就是表格线（数字不会压线），故重叠只需 3%、下限 2px；\n"
    "           用旧白列法时切点可能略偏，留同样比例也够（旧版曾用全图宽 6% = 51px，过大）。 */\n"
    "        var ov = Math.max(2, Math.round((x1 - x0) * 0.03));",
    '重叠改 3%')

# ══════════════════ ④ 倍数改按字符高 ══════════════════
rep('data-import.js',
    "          /* 目标：放大后块宽约 1200px。实测（本项目 848×244 的营收日报截图）\n"
    "             · 块宽 4000+px（字符高 150px）→ 数字大面积误识\n"
    "             · 块宽 1200px （字符高 ~40px，接近 Tesseract 最佳区间）→ 识别稳定 */\n"
    "          var sc = Math.max(3, Math.min(8, Math.round(1200 / bw)));",
    "          /* ⭐ 倍数按「字符高」定，不再按块宽凑 1200px。\n"
    "             实测量化（854×248 营收日报，逐列裁剪，psm 6，eng 模型）：\n"
    "               ×2（字符高 40px）→ 门诊收入列命中 1/2\n"
    "               ×3（字符高 60px）→ 门诊收入 / 在院收入 各命中 2/2（最佳）\n"
    "               ×4 / ×5 / ×6     → 命中数持平或下降\n"
    "             原口径按块宽算会到 ×8（字符高 160px），明显过大。\n"
    "             故取「目标字符高 60px」，并夹在 2—6 倍之间。 */\n"
    "          var sc = Math.max(2, Math.min(6, Math.round(60 / Math.max(6, charH))));",
    '倍数改按字符高')

# ══════════════════ ⑤ 调试信息补充 ══════════════════
rep('data-import.js',
    "      try { window.__ocrCuts = { src: cutSrc, cuts: cuts.map(function (c) { return Math.round(c); }) }; } catch (e) { }",
    "      try {\n"
    "        window.__ocrCuts = { src: cutSrc, cuts: cuts.map(function (c) { return Math.round(c); }),\n"
    "                             charH: charH, rows: tbl.rows, hlines: tbl.hlines };\n"
    "      } catch (e) { }",
    '调试信息补 charH/rows')

print('=== 完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
