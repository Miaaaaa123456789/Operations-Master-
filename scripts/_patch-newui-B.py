#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补丁 B：business-analysis.js 数据同步至 9.23"""
import io

PATH = 'business-analysis.js'
s = io.open(PATH, encoding='utf-8').read()
fails = []


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n == 0:
        fails.append('%s 未找到' % tag)
        print('  ✗ %-30s 未找到' % tag)
        return
    if n != expect:
        fails.append('%s 实际 %d 期望 %d' % (tag, n, expect))
    s = s.replace(old, new)
    print('  ✓ %-30s %3d 处' % (tag, n))


print('── B1. 范围标签 ──')
rep('<span class="dc-scope">本周 9.21—9.27 · 截至 9.22</span>',
    '<span class="dc-scope">本周 9.21—9.27 · 数据截至 9.23（营收 9.22）</span>',
    'dc-scope')

print()
print('── B2. 链路四节点 ──')
rep('<span>客服随访42条、到院14人，但收入未同步增长</span>',
    '<span>客服随访49条、到院18人，但收入未同步增长</span>', '节点1 触达')
rep('<span>营销接触8人、入院1人，小样本无法证明改善</span>',
    '<span>营销接触11人、入院3人，小样本仍不足以证明改善</span>', '节点2 转化')
rep('<span>实际日均5.43万，达标需13.26万</span>',
    '<span>营收日报日均5.43万（9.22 止），达标需13.26万</span>', '节点4 结果')

print()
print('── B3. 四张风险卡 ──')
rep('<article class="dc-risk red"><label>月目标风险</label><strong>落后14.1pt</strong>'
    '<p>累计153.89万，剩余8天还需106.11万，真实日均缺口7.83万。</p></article>',
    '<article class="dc-risk red"><label>月目标风险</label><strong>落后14.1pt</strong>'
    '<p>累计153.89万（9.1—9.22），剩余8天还需106.11万，日均缺口7.83万。</p></article>',
    '风险1 目标')
rep('<article class="dc-risk orange"><label>前端未变现</label><strong>到院率33.3%</strong>'
    '<p>随访和到院均增长，但本周营业额反降4.6%，到院未形成足够付费。</p></article>',
    '<article class="dc-risk orange"><label>前端未变现</label><strong>到院率36.7%</strong>'
    '<p>随访 +16.7%、到院 +12.5%，但营业额反降4.6%，到院未形成足够付费。</p></article>',
    '风险2 未变现')
rep('<article class="dc-risk blue"><label>营销小样本</label><strong>8人 → 1人</strong>'
    '<p>转化率12.5%仅由分母缩小产生，实际入院没有增加。</p></article>',
    '<article class="dc-risk blue"><label>营销小样本</label><strong>11人 → 3人</strong>'
    '<p>接触量下降15.4%，转化率27.3%由小分母放大，暂不能判定效率改善。</p></article>',
    '风险3 小样本')

print()
print('── B4. 六项 KPI（覆盖 marketing-redesign 的默认值）──')
rep("<strong>42条</strong><span>较上周同期 +35.5%</span>",
    "<strong>49条</strong><span>较上周同期 +16.7%（9.14—9.16）</span>", 'KPI 客服随访')
rep("<strong>14人</strong><span>到院率 33.3%</span>",
    "<strong>18人</strong><span>到院率 36.7%</span>", 'KPI 标记到院')
rep("<strong>8人</strong><span>较上周同期 −11.1%</span>",
    "<strong>11人</strong><span>较上周同期 −15.4%</span>", 'KPI 营销接触')
rep("<strong>1人</strong><span>与上周同期持平</span>",
    "<strong>3人</strong><span>与上周同期持平（3 人）</span>", 'KPI 营销入院')
rep("<strong>12.5%</strong><span>小样本，不判定改善</span>",
    "<strong>27.3%</strong><span>小样本，不判定改善</span>", 'KPI 营销转化')
rep("<strong>27人</strong><span>最近完整口径 9.20</span>",
    "<strong>27人</strong><span>最近完整口径 9.20</span>", 'KPI 在院参考')

print()
print('── B5. hero 副标题 ──')
rep("shell.querySelector('.mkt-sub').textContent='9月21—22日 · 日均 ¥5.43万 · 较上周同期 −4.6%';",
    "shell.querySelector('.mkt-sub').textContent='9月21—22日 · 日均 ¥5.43万 · 较上周同期 −4.6%（9.23 日报待补）';",
    'hero 副标题')

print()
print('── B6. 四张分析卡 ──')
rep('<article class="mkt-analysis-card"><label>客服触达</label><strong>增长但未变现</strong>'
    '<p>到院增加40%，同期营业额却下降4.6%。</p></article>',
    '<article class="mkt-analysis-card"><label>客服触达</label><strong>增长但未变现</strong>'
    '<p>到院 16→18 人，同期营业额却下降4.6%。</p></article>',
    '分析卡1')
rep('<article class="mkt-analysis-card"><label>营销转化</label><strong>小样本假改善</strong>'
    '<p>入院仍为1人，转化率上升来自分母变小。</p></article>',
    '<article class="mkt-analysis-card"><label>营销转化</label><strong>小样本待观察</strong>'
    '<p>入院 3 人，但接触量下降15.4%，率升来自分母变小。</p></article>',
    '分析卡2')

print()
print('── B7. 明细条目数字（正文叙述）──')
rep('<p>完成率<b>59.2%</b>低于时间进度73.3%。本周前两天10.86万、日均5.43万，'
    '较上周同期11.39万下降4.6%；',
    '<p>完成率<b>59.2%</b>低于时间进度73.3%。本周至今日均5.43万（9.21—9.22，9.23 待补），'
    '较上周同期11.39万下降4.6%；', '条目1')
rep('<p>客服随访42条、到院14人；上周同期31条、到院10人。随访增长35.5%、到院增长40%，'
    '但营业额反降。',
    '<p>客服随访49条、到院18人；上周同期42条、到院16人。随访增长16.7%、到院增长12.5%，'
    '但营业额反降。', '条目2')
rep('<p>本周接触8人、入院1人，转化率12.5%；上周同期9人、入院1人，11.1%。'
    '入院绝对数未增加、触达量还下降11.1%，',
    '<p>本周接触11人、入院3人，转化率27.3%；上周同期13人、入院3人，23.1%。'
    '入院绝对数未增加、触达量还下降15.4%，', '条目3')
rep('<p>最近完整周入院14人、出院13人，净增仅1人；9.20在院约27人。',
    '<p>上周完整周（9.14—9.20）入院14人、出院13人，净增仅1人；9.20在院27人。', '条目5')
rep("页面旧缺口6.24万应改为<b>7.83万</b>。医生和护理尚未更新至本周，"
    "必须明确区分“本周前两天”和“上周完整周”。</p>",
    "客服台账与线上表、营销汇总与逐条等差异仍待统一。医生组和护理组尚未更新至本周，"
    "必须明确区分“本周至今”和“上周完整周”。</p>", '条目8')

print()
print('── B8. 数据口径警示条 ──')
rep('<p>客服随访存在<b>67 / 68</b>、营销完整周存在<b>78 / 80</b>、心理接触存在<b>34 / 40</b>、'
    '医生在院存在<b>27 / 28</b>等差异；医生组和护理组尚未更新到本周。',
    '<p>客服台账存在<b>67 / 68</b>、营销完整周存在<b>78 / 80</b>、心理接触存在<b>34 / 40</b>、'
    '医生在院存在<b>27 / 28</b>等差异；医生组和护理组尚未更新到本周，'
    '营收日报 9.23 尚未回传。', '警示条')

io.open(PATH, 'w', encoding='utf-8').write(s)

print()
chk = io.open(PATH, encoding='utf-8').read()
print('── 回读校验 ──')
for k, v in [('49条', chk.count('<strong>49条</strong>')), ('18人', chk.count('<strong>18人</strong>')),
             ('11人', chk.count('<strong>11人</strong>')), ('3人', chk.count('<strong>3人</strong>')),
             ('27.3%', chk.count('27.3%')),
             ('残留 42条', chk.count('<strong>42条</strong>')),
             ('残留 14人', chk.count('<strong>14人</strong>')),
             ('残留 12.5%', chk.count('12.5%')),
             ('残留 35.5%', chk.count('35.5%')),
             ('残留 40%', chk.count('增加40%'))]:
    print('  %-22s %d' % (k, v))
for bad in ['<strong>42条</strong>', '<strong>12.5%</strong>', '增加40%']:
    if chk.count(bad):
        fails.append('残留旧值 %s' % bad)

print()
if fails:
    print('!! 问题 %d 项：' % len(fails))
    for f in fails:
        print('   -', f)
    raise SystemExit(2)
print('ALL CHECKS PASSED')
