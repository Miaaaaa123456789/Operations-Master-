# -*- coding: utf-8 -*-
"""营收日报图片识别（三）：psm 11 为主 + 逐块智能回退 psm 6

本地实测量化（854×248 营收日报，竖线定列 + 数据区裁剪 + ×3，eng 模型，逐列对照真值）：

  列             psm 6        psm 11
  日期/星期       碎（2-4字符） 14 个日期全对
  门诊收入        0/7          7/7
  门诊环比        7/7          7/7
  在院收入        7/7          7/7
  在院环比        0/7          7/7
  当日合计        0/7          7/7
  当月累计        0/7          7/7
  在院           6/7          7/7
  复诊           1/7          6/7
  入院           6/7          0/7
  初诊           3/7          0/7
  出院初次        0/7          0/7

判读：
· 金额/日期类「宽列」用 psm 11（稀疏文本）明显更好 —— psm 6 假定「单一均匀文本块」，
  会被表格横线分隔开的 7 个独立数字当成噪声整块丢弃（输出为空串）。
· 1—2 位小整数「窄列」反而 psm 6 更好（上下文太少）。
故改为：psm 11 先跑；某块数字 token 不足 3 个时，用 psm 6 重跑该块并取更优者。
"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []

OLD = (
    "      var collected = [];\n"
    "      var blockTexts = [];\n"
    "      var chain = Promise.resolve();\n"
    "      blocks.forEach(function (bl, idx) {\n"
    "        chain = chain.then(function () {\n"
    "          ocrProgress('识别中 ' + (idx + 1) + '/' + blocks.length + '…');\n"
    "          var bw = bl.x1 - bl.x0;\n"
    "          /* ⭐ 倍数按「字符高」定，不再按块宽凑 1200px。\n"
    "             实测量化（854×248 营收日报，逐列裁剪，psm 6，eng 模型）：\n"
    "               ×2（字符高 40px）→ 门诊收入列命中 1/2\n"
    "               ×3（字符高 60px）→ 门诊收入 / 在院收入 各命中 2/2（最佳）\n"
    "               ×4 / ×5 / ×6     → 命中数持平或下降\n"
    "             原口径按块宽算会到 ×8（字符高 160px），明显过大。\n"
    "             故取「目标字符高 60px」，并夹在 2—6 倍之间。 */\n"
    "          var sc = Math.max(2, Math.min(6, Math.round(60 / Math.max(6, charH))));\n"
    "          /* binarize 参数保留但默认关闭：实测对本项目这张微信压缩截图反而使日期列丢失 */\n"
    "          var cv = cropScale(img, bl.x0, bl.x1, sc, false, tbl.dataTop, tbl.dataBot);\n"
    "          return w.recognize(cv, {}, { blocks: true, text: true }).then(function (r) {\n"
    "            blockTexts.push('[' + idx + '] ' + String(r.data.text || '').replace(/\\n+/g, ' | ').slice(0, 150));\n"
    "            wordsOf(r.data).forEach(function (x) {\n"
    "              var raw = x.text.trim();\n"
    "              if (!raw) return;\n"
    "              var v = numToken(raw);\n"
    "              if (DATE_RE.test(raw) || findDate(raw)) v = null;   // 日期不是金额\n"
    "              if (v == null && !findDate(raw)) return;\n"
    "              collected.push({\n"
    "                text: raw, v: v,\n"
    "                x: bl.x0 + x.bbox.x0 / sc, xc: bl.x0 + (x.bbox.x0 + x.bbox.x1) / 2 / sc,\n"
    "                /* y 要补回「数据区起点」的偏移，否则分组时会把不同行带串在一起 */\n"
    "                y: (tbl.dataTop || 0) + (x.bbox.y0 + x.bbox.y1) / 2 / sc,\n"
    "                h: (x.bbox.y1 - x.bbox.y0) / sc\n"
    "              });\n"
    "            });\n"
    "          });\n"
    "        });\n"
    "      });\n"
)

NEW = (
    "      var collected = [];\n"
    "      var blockTexts = [];\n"
    "      var chain = Promise.resolve();\n"
    "      /* 块识别结果的 token 抽取器（psm 11 与 psm 6 共用） */\n"
    "      var extractTokens = function (r, bl, sc) {\n"
    "        var got = [];\n"
    "        wordsOf(r.data).forEach(function (x) {\n"
    "          var raw = String(x.text || '').trim();\n"
    "          if (!raw) return;\n"
    "          var v = numToken(raw);\n"
    "          if (DATE_RE.test(raw) || findDate(raw)) v = null;   // 日期不是金额\n"
    "          if (v == null && !findDate(raw)) return;\n"
    "          got.push({\n"
    "            text: raw, v: v,\n"
    "            x: bl.x0 + x.bbox.x0 / sc, xc: bl.x0 + (x.bbox.x0 + x.bbox.x1) / 2 / sc,\n"
    "            /* y 要补回「数据区起点」的偏移，否则分组时会把不同行带串在一起 */\n"
    "            y: (tbl.dataTop || 0) + (x.bbox.y0 + x.bbox.y1) / 2 / sc,\n"
    "            h: (x.bbox.y1 - x.bbox.y0) / sc\n"
    "          });\n"
    "        });\n"
    "        return got;\n"
    "      };\n"
    "      /* ⭐ 逐块「psm 11 优先 + 智能回退 psm 6」。为什么：\n"
    "         psm 6 假定「单一均匀文本块」，会被表格横线分隔开的独立数字整块丢弃 ——\n"
    "         实测对门诊收入 / 当月累计两列输出空串（0/7）；切到 psm 11（稀疏文本）后\n"
    "         门诊收入 7/7、在院收入 7/7、当日合计 7/7、当月累计 7/7、\n"
    "         门诊环比 7/7、在院环比 7/7，日期列 14 个日期全对。\n"
    "         但 1—2 位小整数窄列（初诊 / 入院）反而 psm 6 更好（psm 11 上下文不足 → 0）。\n"
    "         故：psm 11 读到的数字不足 3 个时，用 psm 6 重跑该块并取更优者。 */\n"
    "      blocks.forEach(function (bl, idx) {\n"
    "        chain = chain.then(function () {\n"
    "          ocrProgress('识别中 ' + (idx + 1) + '/' + blocks.length + '…');\n"
    "          /* ⭐ 倍数按「字符高」定，不再按块宽凑 1200px。\n"
    "             实测量化（854×248 营收日报，逐列裁剪）三次：\n"
    "               · psm 6  ×2（字符高 40px）→ 门诊收入 1/2；×3 → 2/2\n"
    "               · psm 11 ×3 → 六列金额全部 7/7；×4 / ×5 略降（当月累计出现 1369264 .20）\n"
    "             原口径按块宽算会到 ×8（字符高 160px），明显过大。\n"
    "             故取「目标字符高 60px」，并夹在 2—6 倍之间。 */\n"
    "          var sc = Math.max(2, Math.min(6, Math.round(60 / Math.max(6, charH))));\n"
    "          /* binarize 参数保留但默认关闭：实测对本项目这张微信压缩截图反而使日期列丢失 */\n"
    "          var cv = cropScale(img, bl.x0, bl.x1, sc, false, tbl.dataTop, tbl.dataBot);\n"
    "          var OCRD = { blocks: true, text: true };\n"
    "          return w.recognize(cv, {}, OCRD).then(function (r) {\n"
    "            var g1 = extractTokens(r, bl, sc);\n"
    "            var n1 = g1.filter(function (t) { return t.v != null; }).length;\n"
    "            blockTexts.push('[11/' + idx + '] ' + String(r.data.text || '').replace(/\\n+/g, ' | ').slice(0, 130));\n"
    "            if (n1 >= 3) return g1;                      // psm 11 已读够 → 不回退\n"
    "            return w.setParameters({ tessedit_pageseg_mode: '6' }).then(function () {\n"
    "              return w.recognize(cv, {}, OCRD);\n"
    "            }).then(function (r2) {\n"
    "              var g2 = extractTokens(r2, bl, sc);\n"
    "              var n2 = g2.filter(function (t) { return t.v != null; }).length;\n"
    "              blockTexts.push('[6/' + idx + '] ' + String(r2.data.text || '').replace(/\\n+/g, ' | ').slice(0, 130));\n"
    "              return (n2 > n1) ? g2 : g1;\n"
    "            }).then(function (best) {\n"
    "              return w.setParameters({ tessedit_pageseg_mode: '11' }).then(function () { return best; });\n"
    "            });\n"
    "          }).then(function (got) {\n"
    "            got.forEach(function (t) { collected.push(t); });\n"
    "          });\n"
    "        });\n"
    "      });\n"
)


def rep(fn, old, new, tag, cnt=1):
    p = R + fn
    s = io.open(p, encoding='utf-8').read()
    n = s.count(old)
    if n != cnt:
        fails.append('%-16s %-40s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-16s %-40s %d' % (fn, tag, n))


rep('data-import.js', OLD, NEW, '块识别·psm11+回退psm6')

# worker 初始 psm 6 → 11
rep('data-import.js',
    "      /* 这组参数是实测调出来的：\n"
    "         · user_defined_dpi 不设时 Tesseract 会按 70dpi 处理小图，字符被过度降采样\n"
    "         · psm 6 = 视为单一文本块，适合表格逐块识别\n"
    "         · preserve_interword_spaces 让邻列数字不会被粘成一个 token */\n"
    "      return w.setParameters({\n"
    "        user_defined_dpi: '300',\n"
    "        tessedit_pageseg_mode: '6'\n"
    "      }).then(function () { ocrWorker = w; return w; });",
    "      /* 这组参数是实测调出来的：\n"
    "         · user_defined_dpi 不设时 Tesseract 会按 70dpi 处理小图，字符被过度降采样\n"
    "         · psm 11 = 稀疏文本。⭐ 实测关键：营收日报每个数字都被表格横线隔开，\n"
    "           用 psm 6（单一均匀文本块）会把它们当噪声整块丢弃（门诊收入列 0/7），\n"
    "           切 psm 11 后六列金额全部 7/7。窄列在 psm 11 下不足时由块内回退 psm 6。\n"
    "         · preserve_interword_spaces 让邻列数字不会被粘成一个 token */\n"
    "      return w.setParameters({\n"
    "        user_defined_dpi: '300',\n"
    "        tessedit_pageseg_mode: '11'\n"
    "      }).then(function () { ocrWorker = w; return w; });",
    'worker 初始 psm 改 11')

print('=== 完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
