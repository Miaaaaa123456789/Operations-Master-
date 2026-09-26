# -*- coding: utf-8 -*-
"""营收日报图片识别（二）：只识别「数据区」，排除顶部标题与表头

本地实测（854×248 营收日报，竖线法已生效、charH=21）：
每块仍裁剪「全高」，于是**顶部两行标题与表头文字在每一块里都出现**，
块文本里能看到 `0-23:59:°59`、`RAUF`、`Re: 41B-` 这类标题/表头残片，
噪声把数据行的数字挤掉 → parsed 仅 1 行、verified 0。

改法：analyzeTable 返回数据区 y 范围（跳过表头带），
      cropScale 支持 y 范围裁剪，token 的 y 坐标补回偏移。
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
        fails.append('%-16s %-44s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-16s %-44s %d' % (fn, tag, n))


# ① analyzeTable 返回数据区范围
rep('data-import.js',
    "    if (st >= 0 && bot - st >= 6) bands.push([st, bot]);\n"
    "    if (bands.length < 2) return res;\n"
    "    res.rows = bands.length;",
    "    if (st >= 0 && bot - st >= 6) bands.push([st, bot]);\n"
    "    if (bands.length < 2) return res;\n"
    "    res.rows = bands.length;\n"
    "    /* 数据区：bands[0] 是表头带（可能含两行表头，如「出院 初次／多次」），\n"
    "       数据从 bands[1] 开始。只识别这一段——否则每个块都会混进顶部标题与表头文字，\n"
    "       噪声会把数据行的数字挤掉（实测：不裁剪时 parsed 仅 1 行、verified 0）。 */\n"
    "    res.dataTop = Math.max(0, bands[1][0] - 3);\n"
    "    res.dataBot = bot;",
    'analyzeTable 返回 dataTop')

rep('data-import.js',
    "    var res = { cols: [], charH: 0, rows: 0, hlines: 0 };",
    "    var res = { cols: [], charH: 0, rows: 0, hlines: 0, dataTop: 0, dataBot: 0 };",
    'res 加 dataTop/dataBot')

# ② cropScale 支持 y 范围
rep('data-import.js',
    "  function cropScale(img, x0, x1, scale, binarize) {\n"
    "    var c = document.createElement('canvas');\n"
    "    c.width = Math.max(1, Math.round((x1 - x0) * scale));\n"
    "    c.height = Math.max(1, Math.round(img.height * scale));\n"
    "    var g = c.getContext('2d');\n"
    "    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';\n"
    "    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);\n"
    "    g.drawImage(img, x0, 0, Math.max(1, x1 - x0), img.height, 0, 0, c.width, c.height);",
    "  function cropScale(img, x0, x1, scale, binarize, y0, y1) {\n"
    "    /* y0/y1 可选：只裁剪竖直方向的一段（用于跳过顶部标题与表头） */\n"
    "    var Y0 = (y0 == null ? 0 : Math.max(0, Math.round(y0)));\n"
    "    var Y1 = (y1 == null ? img.height : Math.min(img.height, Math.round(y1)));\n"
    "    if (Y1 - Y0 < 4) { Y0 = 0; Y1 = img.height; }\n"
    "    var c = document.createElement('canvas');\n"
    "    c.width = Math.max(1, Math.round((x1 - x0) * scale));\n"
    "    c.height = Math.max(1, Math.round((Y1 - Y0) * scale));\n"
    "    var g = c.getContext('2d');\n"
    "    g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high';\n"
    "    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);\n"
    "    g.drawImage(img, x0, Y0, Math.max(1, x1 - x0), Math.max(1, Y1 - Y0), 0, 0, c.width, c.height);",
    'cropScale 支持 y 范围')

# ③ 调用处传入数据区
rep('data-import.js',
    "          var cv = cropScale(img, bl.x0, bl.x1, sc, false);",
    "          var cv = cropScale(img, bl.x0, bl.x1, sc, false, tbl.dataTop, tbl.dataBot);",
    '调用传数据区')

# ④ token 的 y 坐标补偏移
rep('data-import.js',
    "                x: bl.x0 + x.bbox.x0 / sc, xc: bl.x0 + (x.bbox.x0 + x.bbox.x1) / 2 / sc,\n"
    "                y: (x.bbox.y0 + x.bbox.y1) / 2 / sc, h: (x.bbox.y1 - x.bbox.y0) / sc",
    "                x: bl.x0 + x.bbox.x0 / sc, xc: bl.x0 + (x.bbox.x0 + x.bbox.x1) / 2 / sc,\n"
    "                /* y 要补回「数据区起点」的偏移，否则分组时会把不同行带串在一起 */\n"
    "                y: (tbl.dataTop || 0) + (x.bbox.y0 + x.bbox.y1) / 2 / sc,\n"
    "                h: (x.bbox.y1 - x.bbox.y0) / sc",
    'token y 补偏移')

print('=== 完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
