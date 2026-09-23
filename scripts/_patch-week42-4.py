#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 4：概览标注 + 本周至今（9.21—9.22）数据行"""
import io

PATH = 'index.html'
SRC = io.open(PATH, encoding='utf-8').read()
fails = []


def rep(old, new, tag, expect=None):
    global SRC
    n = SRC.count(old)
    if n == 0:
        fails.append('%s | 未找到 | %s' % (tag, old[:80]))
        return
    if expect is not None and n != expect:
        fails.append('%s | 实际 %d / 期望 %d' % (tag, n, expect))
    SRC = SRC.replace(old, new)
    print('  %-36s %3d 处' % (tag, n))


print('── A. 概览指标标注 ──')
rep('<span class="ov-chip">9.14—9.20 主表第 3 周</span>',
    '<span class="ov-chip">上周 9.14—9.20 主表</span>', 'A1 门诊 chip', 1)
rep('<span class="ov-chip">9.14—9.20 主表</span>',
    '<span class="ov-chip">上周 9.14—9.20 主表</span>', 'A2 物理治疗 chip', 1)
rep('<strong>27<em>人</em></strong><span class="ov-chip">9.20</span>',
    '<strong>27<em>人</em></strong><span class="ov-chip">上周 9.20</span>', 'A3 在院 chip', 1)
rep('<strong>14<em>人</em></strong><span class="ov-chip">9.14—9.20</span>',
    '<strong>14<em>人</em></strong><span class="ov-chip">上周 9.14—9.20</span>', 'A4 入院 chip', 1)
rep('<strong>13<em>人</em></strong><span class="ov-chip">9.14—9.20</span>',
    '<strong>13<em>人</em></strong><span class="ov-chip">上周 9.14—9.20</span>', 'A5 出院 chip', 1)

print()
print('── B. 目标卡缺口文案 ──')
rep('剩余 <b>11</b> 天需 <b>106.11 万</b>，日均需 <b>13.26 万</b>；'
    '上周实际日均 <b>7.02 万</b>，缺口 <b>2.70 万</b>。',
    '剩余 <b>8</b> 天需 <b>106.11 万</b>，日均需 <b>13.26 万</b>；'
    '上周日均 <b>7.02 万</b>、本周至今（9.21—9.22）日均 <b>5.43 万</b>，缺口 <b>6.24 万</b>。',
    'B1 ov-gap', 1)

print()
print('── C. 本周至今数据行 ──')
ROW_SVC = ("metrics:[[\"本周至今（9.21—9.22，2 天）\",null,null,'','导医回访台账本周回访 <b>42 条</b>"
           "、标注到院 14 条（33.3%）：蒋雨 22 / 张欣雨 13 / 温诗怡 7；上周同期（9.14—9.15，同为 2 天）"
           "31 条、到院 10 条（32.3%）。导诊主动服务 26 条（上周同期 3 条）；日工作量 8 人日 / 841 分"
           "（上周同期 10 人日 / 1034 分）。完整周对照见以下各行'],"
           "['接待人次（导医）'")
rep("metrics:[['接待人次（导医）'", ROW_SVC, 'C1 客服 本周行', 1)

ROW_PSY = ("metrics:[[\"本周至今（9.21—9.22，2 天）\",null,null,'','管理表 V4「咨询师每日简报」本周仅 9.21 "
           "有 3 条日报：患者接触 <b>8 人次</b>（冯浩鹏 6 · 杨霞 1 · 蔡宜蓉 1）、咨询工作量 <b>6 人次</b>"
           "（蔡宜蓉 5 · 冯浩鹏 1）、家长工作 0；上周同期（9.14—9.15，同为 2 天）3 条日报 · 接触 6 / 咨询 3 / 家长 0。"
           "9.22 起日报尚未填报，本周数据待累积。完整周对照见以下各行'],"
           "['在院患者',30,24,'人'")
rep("metrics:[['在院患者',30,24,'人'", ROW_PSY, 'C2 心理 本周行', 1)

ROW_MKT = ("metrics:[[\"本周至今（9.21—9.22，2 天）\",null,null,'','《管家 患者有效对接表》逐条记录本周对接 "
           "<b>8 条</b>（金林 3 / 朱婧 3 / 利娟 2）、转住院 1 人（12.5%）；上周同期（9.14—9.15，同为 2 天）"
           "9 条、转住院 1 人（11.1%）。完整周对照见以下各行'],"
           "['管家有效对接（上周 9.14—9.20）'")
rep("metrics:[['管家有效对接（上周 9.14—9.20）'", ROW_MKT, 'C3 管家 本周行', 1)

ROW_DOC = ("metrics:[[\"本周数据（9.21—9.27）\",null,null,'','<b>主表尚未滚动到本周</b>："
           "《特别行动小组汇报表》医生组表头仍为上周（9.14—9.20）值，本周入院 / 出院 / 门诊 / 总费用"
           "待主表更新后并入。本页医生组各项均取上周值'],"
           "['在院人数',null,27,'人'")
rep("metrics:[['在院人数',null,27,'人'", ROW_DOC, 'C4 医生组 待更新行', 1)

ROW_NUR = ("metrics:[[\"本周数据（9.21—9.27）\",null,null,'','<b>主表尚未滚动到本周</b>："
           "护理组表头「物理治疗人数」仍为上周（9.14—9.20）的 459 人次；护士日表 9.13—9.19 口径同理。"
           "本周治疗数据待源表更新'],"
           "['物理治疗执行人次',1014,934,'人次'")
rep("metrics:[['物理治疗执行人次',1014,934,'人次'", ROW_NUR, 'C5 护理组 待更新行', 1)

print()
print('── D. 快照 delta 标注 ──')
rep("{label:'上周入院',value:'14',unit:'人',delta:'9.14—9.20 业主更正'}",
    "{label:'上周入院',value:'14',unit:'人',delta:'上周 9.14—9.20 业主更正'}",
    'D1 快照入院', 1)
rep("{label:'上周出院',value:'13',unit:'人',delta:'9.14—9.20 业主更正'}",
    "{label:'上周出院',value:'13',unit:'人',delta:'上周 9.14—9.20 业主更正'}",
    'D2 快照出院', 1)
rep("{label:'门诊',value:'209',unit:'人',delta:'9.14—9.20 主表'}",
    "{label:'门诊',value:'209',unit:'人',delta:'上周 9.14—9.20 主表'}",
    'D3 快照门诊', 1)
rep("{label:'物理治疗',value:'459',unit:'人次',delta:'9.14—9.20 主表'}",
    "{label:'物理治疗',value:'459',unit:'人次',delta:'上周 9.14—9.20 主表'}",
    'D4 快照物理治疗', 1)

io.open(PATH, 'w', encoding='utf-8').write(SRC)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
for k, v in [('本周至今（9.21—9.22', chk.count('本周至今（9.21—9.22')),
             ('本周数据（9.21—9.27）', chk.count('本周数据（9.21—9.27）')),
             ('上周 9.14—9.20 主表', chk.count('上周 9.14—9.20 主表')),
             ('剩余 <b>8</b> 天', chk.count('剩余 <b>8</b> 天')),
             ('残留 剩余 <b>11</b> 天', chk.count('剩余 <b>11</b> 天'))]:
    print('  %-28s %d' % (k, v))
if chk.count('剩余 <b>11</b> 天'):
    fails.append('ov-gap 未更新')

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
