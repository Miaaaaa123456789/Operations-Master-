# -*- coding: utf-8 -*-
"""营收日报图片识别（四）：用列边界直接定位人数字段，杜绝「错位」

现状：金额列已 7/7，但人数字段靠「在 门诊收入↔在院收入 之间取第 1、2 个小整数」
这种相对取法 —— 一旦某列没读出（如初诊列），后面的值会**前移顶替**，
把「复诊 79」写成「初诊 79」，比留空更危险。

改法：列边界（表格竖线）已精确，直接按列号取：
  门诊收入列 cA → 初诊 = cA+2、复诊 = cA+3
  在院收入列 cB → 在院 = cB+2、入院 = cB+3、出院初次 = cB+4、出院多次 = cB+5
  且要求该列**唯一命中**才采信，否则留空。
  仅当拿不到列边界时才回退到旧的相对取法。
"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []

OLD = (
    "          /* 人数：夹在 门诊↔在院 之间的小整数为 初诊/复诊；\n"
    "             夹在 在院↔合计 之间的小整数依次为 在院/入院/出院初次/出院多次 */\n"
    "          var small = function (a, b) {\n"
    "            return nums.filter(function (t) {\n"
    "              return t !== L && t !== Rr && t !== best.C &&\n"
    "                     t.v > 0 && t.v < 500 && t.v % 1 === 0 &&   // 人数是整数，排除 \"-3975.20\" 这类残片\n"
    "                     t.xc > a && t.xc < b;\n"
    "            }).sort(function (x, y) { return x.xc - y.xc; });\n"
    "          };\n"
    "          var leftSide = small(L.xc, Rr.xc);\n"
    "          if (leftSide[0]) rec.first = leftSide[0].v;\n"
    "          if (leftSide[1]) rec.again = leftSide[1].v;\n"
    "          var rightSide = small(Rr.xc, best.C.xc);\n"
    "          if (rightSide[0]) rec.inhos = rightSide[0].v;\n"
    "          if (rightSide[1]) rec.admit = rightSide[1].v;\n"
    "          if (rightSide[2]) rec.disch = (rightSide[2].v || 0) + (rightSide[3] ? rightSide[3].v : 0);\n"
)

NEW = (
    "          /* 人数：优先按「列号」取值（表格列边界已知且精确），避免前移顶替。\n"
    "             列序（以本类营收日报为例）：\n"
    "               门诊收入 → 门诊环比 → 初诊 → 复诊 → 在院收入\n"
    "                        → 在院环比 → 在院 → 入院 → 出院初次 → 出院多次 → 当日合计\n"
    "             即：初诊 = 门诊收入列 +2、复诊 = +3；\n"
    "                 在院 = 在院收入列 +2、入院 = +3、出院初次 = +4、出院多次 = +5。\n"
    "             若某列没读出，宁可留空（由用户核对补全），也不要让后面的值顶上 ——\n"
    "             实测旧相对取法会把「复诊 79」写成「初诊 79」。 */\n"
    "          var bnd = (meta && meta.bounds) || [];\n"
    "          var colOf = function (xc) {\n"
    "            for (var ci = 0; ci < bnd.length - 1; ci++) if (xc >= bnd[ci] && xc < bnd[ci + 1]) return ci;\n"
    "            return -1;\n"
    "          };\n"
    "          var cA = colOf(L.xc), cB = colOf(Rr.xc);\n"
    "          var pickCol = function (ci) {\n"
    "            if (ci < 0 || ci >= bnd.length) return null;\n"
    "            var hit = nums.filter(function (t) {\n"
    "              return t !== L && t !== Rr && t !== best.C &&\n"
    "                     t.v > 0 && t.v < 500 && t.v % 1 === 0 && colOf(t.xc) === ci;\n"
    "            });\n"
    "            return hit.length === 1 ? hit[0].v : null;   // 唯一命中才采信\n"
    "          };\n"
    "          if (cA >= 0 && cB > cA) {\n"
    "            var f1 = pickCol(cA + 2), f2 = pickCol(cA + 3);\n"
    "            var p1 = pickCol(cB + 2), p2 = pickCol(cB + 3), p3 = pickCol(cB + 4), p4 = pickCol(cB + 5);\n"
    "            if (f1 != null) rec.first = f1;\n"
    "            if (f2 != null) rec.again = f2;\n"
    "            if (p1 != null) rec.inhos = p1;\n"
    "            if (p2 != null) rec.admit = p2;\n"
    "            if (p3 != null || p4 != null) rec.disch = (p3 || 0) + (p4 || 0);\n"
    "          } else {\n"
    "            /* 回退：没有列边界时，仍按「夹在两组收入之间的第 n 个小整数」取，但要求不模糊 */\n"
    "            var small = function (a, b) {\n"
    "              return nums.filter(function (t) {\n"
    "                return t !== L && t !== Rr && t !== best.C &&\n"
    "                       t.v > 0 && t.v < 500 && t.v % 1 === 0 &&\n"
    "                       t.xc > a && t.xc < b;\n"
    "              }).sort(function (x, y) { return x.xc - y.xc; });\n"
    "            };\n"
    "            var leftSide = small(L.xc, Rr.xc);\n"
    "            if (leftSide.length <= 2) {\n"
    "              if (leftSide[0]) rec.first = leftSide[0].v;\n"
    "              if (leftSide[1]) rec.again = leftSide[1].v;\n"
    "            }\n"
    "            var rightSide = small(Rr.xc, best.C.xc);\n"
    "            if (rightSide.length <= 4) {\n"
    "              if (rightSide[0]) rec.inhos = rightSide[0].v;\n"
    "              if (rightSide[1]) rec.admit = rightSide[1].v;\n"
    "              if (rightSide[2]) rec.disch = (rightSide[2].v || 0) + (rightSide[3] ? rightSide[3].v : 0);\n"
    "            }\n"
    "          }\n"
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


rep('data-import.js', OLD, NEW, '人数按列号定位')

print('=== 完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
