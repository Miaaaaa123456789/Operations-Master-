# -*- coding: utf-8 -*-
"""心理组：组长陈鹏不参与排名，单独列出工作量

业主指令（2026-09-27）：心理组 陈鹏作为组长不参与排名，单独列出单独工作量。

做法
· 从 ①②③④⑥ 五组移除陈鹏行（陈鹏非任何组的归一化基数最大值 → 其余人分值不变，仅顺位上移）
· 「组长专项工作」升级为「⑦ 组长单独工作量（不参与排名 · 陈鹏）」，
  rankless:true，列本周 / 上周同期 / 累计三行
· 顺带修正该组原有的两处数据错误：
    「床旁 3 / 情绪 1」→ 实为「首次 1 / 床旁 4」（源表 9.19 记录）
    「门诊咨询 3」   → 实为「住院咨询 3」（源表 9.19 记录）
· renderRankGroup 新增可选 noRankText / noRankSub，用于覆盖 rankless 组的
  「不排名 / 仅核查」默认标签（向后兼容，不传即维持原样）
"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []


def rep(old, new, tag, cnt=1, fn='index.html'):
    p = R + fn
    s = io.open(p, encoding='utf-8').read()
    n = s.count(old)
    if n != cnt:
        fails.append('%-16s %-46s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-16s %-46s %d 处' % (fn, tag, n))


# ══════════════════════ 一、渲染器：rankless 组标签可覆盖 ══════════════════════
rep(
    "function renderRankGroup(group){const lab=group.scoreLabel||'本周',rl=!!group.rankless;"
    "return `<div class=\"rank-group${rl?' is-rankless':''}\"><h4>${group.title}</h4>"
    "<div class=\"rank-summary\">${group.note}</div><div class=\"rank-list\">"
    "${group.rows.map((r,i)=>`<div class=\"rank-row\"><span class=\"rank-no ${rl?'isnone':(r.missing?'missing':'')}\">"
    "${rl?'·':(r.missing?'—':i+1)}</span><span class=\"rank-person\"><strong>${r.name}</strong>"
    "<span>${r.metric}</span></span><span class=\"rank-score\">"
    "<strong>${rl?'不排名':(r.missing?'未排名':r.score)}</strong>"
    "<span>${rl?'仅核查':(r.missing?'未填报':lab)}</span></span></div>`).join('')}</div></div>`}",
    "function renderRankGroup(group){const lab=group.scoreLabel||'本周',rl=!!group.rankless;"
    "/* rankless 组的右侧标签可覆盖：「填报完整性核查」用默认的「不排名 / 仅核查」，"
    "「组长单独工作量」用「不排名 / 单独列示」 */"
    "const nM=group.noRankText||'不排名',nS=group.noRankSub||'仅核查';"
    "return `<div class=\"rank-group${rl?' is-rankless':''}\"><h4>${group.title}</h4>"
    "<div class=\"rank-summary\">${group.note}</div><div class=\"rank-list\">"
    "${group.rows.map((r,i)=>`<div class=\"rank-row\"><span class=\"rank-no ${rl?'isnone':(r.missing?'missing':'')}\">"
    "${rl?'·':(r.missing?'—':i+1)}</span><span class=\"rank-person\"><strong>${r.name}</strong>"
    "<span>${r.metric}</span></span><span class=\"rank-score\">"
    "<strong>${rl?nM:(r.missing?'未排名':r.score)}</strong>"
    "<span>${rl?nS:(r.missing?'未填报':lab)}</span></span></div>`).join('')}</div></div>`}",
    '渲染器·rankless 标签可覆盖')

# ══════════════════════ 二、① 综合排名：移除陈鹏 + 改 note ══════════════════════
rep("{name:'杨霞',metric:'综合 <b>0.0555</b> · 咨询 0 · 接触 4　填报 2 天（提示）　上周同期 咨询 6 / 接触 11',score:'0.0555'},"
    "{name:'陈鹏',metric:'综合 <b>0.0139</b> · 咨询 0 · 接触 1　填报 1 天（提示）　上周同期 咨询 3 / 接触 5',score:'0.0139'},"
    "{name:'王沛然',metric:'本周未填报（综合分不计，非 0 分）',missing:true}",
    "{name:'杨霞',metric:'综合 <b>0.0555</b> · 咨询 0 · 接触 4　填报 2 天（提示）　上周同期 咨询 6 / 接触 11',score:'0.0555'},"
    "{name:'王沛然',metric:'本周未填报（综合分不计，非 0 分）',missing:true}",
    '① 移除陈鹏')

rep('仅按患者接触排的名次为 冯浩鹏 ＞ 蔡宜蓉 ＞ 赵芳 ＞ 杨霞 ＞ 陈鹏 ＞ 王沛然',
    '仅按患者接触排的名次为 冯浩鹏 ＞ 蔡宜蓉 ＞ 赵芳 ＞ 杨霞 ＞ 王沛然',
    '① note 去陈鹏')

rep('填报天数与在岗天数<b>不计分、不排序</b>（只作提示）。<b>本周未填报：王沛然</b>，需先确认为休假还是漏报。',
    '填报天数与在岗天数<b>不计分、不排序</b>（只作提示）。<span class="hl-key">组长陈鹏不参与 ①—⑥ 的排名</span>'
    '（管理与床旁干预不和咨询师横排），其工作量单独列于 ⑦。<b>本周未填报：王沛然</b>，需先确认为休假还是漏报。',
    '① note 补组长说明')

# ══════════════════════ 三、② 咨询量：移除陈鹏 ══════════════════════
rep("{name:'杨霞',metric:'咨询 0 · 接触 4　填报 2 天（提示）　上周同期 6',score:'0'},"
    "{name:'陈鹏',metric:'咨询 0 · 接触 1　填报 1 天（提示）　上周同期 3',score:'0'},"
    "{name:'王沛然',metric:'本周未填报',missing:true}",
    "{name:'杨霞',metric:'咨询 0 · 接触 4　填报 2 天（提示）　上周同期 6',score:'0'},"
    "{name:'王沛然',metric:'本周未填报',missing:true}",
    '② 移除陈鹏')

# ══════════════════════ 四、③ 接触量：移除陈鹏 ══════════════════════
rep("{name:'杨霞',metric:'接触 4 · 咨询 0　填报 2 天（提示）　上周同期 11',score:'4'},"
    "{name:'陈鹏',metric:'接触 1 · 咨询 0　填报 1 天（提示）　上周同期 5',score:'1'},"
    "{name:'王沛然',metric:'本周未填报（上周同期接触 4）',missing:true}",
    "{name:'杨霞',metric:'接触 4 · 咨询 0　填报 2 天（提示）　上周同期 11',score:'4'},"
    "{name:'王沛然',metric:'本周未填报（上周同期接触 4）',missing:true}",
    '③ 移除陈鹏')

# ══════════════════════ 五、④ 填报核查：移除陈鹏 + 改 note ══════════════════════
rep("{name:'赵芳',metric:'填报 3 天 · 接触 5 · 咨询 1　上周同期（6 天）填报 5 天',score:'3'},"
    "{name:'陈鹏',metric:'填报 1 天 · 接触 1 · 咨询 0　上周同期（6 天）填报 1 天',score:'1'}]}",
    "{name:'赵芳',metric:'填报 3 天 · 接触 5 · 咨询 1　上周同期（6 天）填报 5 天',score:'3'}]}",
    '④ 移除陈鹏')

rep('要看业务量请看 ① 综合排名、② 咨询工作量 与 ③ 患者接触，三者与填报天数无关。',
    '要看业务量请看 ① 综合排名、② 咨询工作量 与 ③ 患者接触，三者与填报天数无关。'
    '组长陈鹏的填报与工作量单列于 ⑦，不在本组核查范围内。',
    '④ note 补组长说明')

# ══════════════════════ 六、⑥ 累计综合：移除陈鹏 ══════════════════════
rep("{name:'王沛然',metric:'综合 <b>0.2659</b> · 咨询 7 · 接触 31　填报 11 天（提示）',score:'0.2659'},"
    "{name:'陈鹏',metric:'综合 <b>0.2259</b> · 咨询 11 · 接触 13　填报 5 天（提示）',score:'0.2259'}]}",
    "{name:'王沛然',metric:'综合 <b>0.2659</b> · 咨询 7 · 接触 31　填报 11 天（提示）',score:'0.2659'}]}",
    '⑥ 移除陈鹏')

# ══════════════════════ 七、组长组：升级为 ⑦ 单独工作量 ══════════════════════
OLD_LEAD = ("{title:'组长专项工作',note:'管理与床旁干预不和咨询师横排。周口径与各组一致"
            "（上周 9.14—9.20 / 上上周 9.7—9.13）。',rows:[\n"
            "{name:'陈鹏',metric:'上周 5 人次接触（首次 1 / 床旁 3 / 情绪 1）· 门诊咨询 3 · "
            "填报 1 天 · 上上周接触 2 人次',missing:true}]}")
NEW_LEAD = (
    "{title:'\u2467 \u7ec4\u957f\u5355\u72ec\u5de5\u4f5c\u91cf\uff08\u4e0d\u53c2\u4e0e\u6392\u540d \u00b7 \u9648\u9e4f\uff09',rankless:true,noRankText:'\u4e0d\u6392\u540d',noRankSub:'\u5355\u72ec\u5217\u793a',"
    "note:'<b>\u7ec4\u957f\u9648\u9e4f\u4e0d\u53c2\u4e0e \u2460\u2014\u2465 \u7684\u6392\u540d</b>\uff1a\u7ba1\u7406\u4e0e\u5e8a\u65c1\u5e72\u9884\u4e0d\u548c\u54a8\u8be2\u5e08\u6a2a\u6392\uff0c\u5176\u5de5\u4f5c\u91cf\u5355\u5217\u4e8e\u672c\u7ec4\uff0c"
    "<b>\u4e0d\u8ba1\u5206\u3001\u4e0d\u6392\u540d\u3001\u4e0d\u4f5c\u5e76\u5217\u5224\u5b9a</b>\u3002\u5468\u53e3\u5f84\u4e0e\u5404\u7ec4\u4e00\u81f4\uff08\u672c\u5468 9.21\u20149.26 / \u4e0a\u5468\u540c\u671f 9.14\u20149.19 / "
    "\u4e0a\u5468\u5b8c\u6574\u5468 9.14\u20149.20\uff09\uff0c\u672c\u671f\u53d6\u5f53\u5468\u5df2\u53d1\u751f\u5929\u6570\u3002"
    "<span class=\\\"hl-key\\\">\u26a0 \u672c\u7ec4\u53ea\u5448\u73b0\u300c\u53ef\u5f52\u56e0\u5230\u65e5\u62a5\u300d\u7684\u4e1a\u52a1\u91cf</span>\u2014\u2014"
    "\u7ec4\u957f\u672c\u5c97\u7684\u7ba1\u7406\u3001\u6392\u73ed\u3001\u7763\u5bfc\u3001\u5e26\u6559\u4e0e\u5bf9\u5916\u534f\u8c03\u5de5\u65f6<b>\u4e0d\u6765\u81ea\u300c\u54a8\u8be2\u5e08\u6bcf\u65e5\u7b80\u62a5\u300d</b>\uff0c\u987b\u53e6\u8868\u767b\u8bb0\uff0c"
    "\u6682\u672a\u7eb3\u5165\u672c\u9875\uff1b\u5efa\u8bae\u540e\u7eed\u4e3a\u7ec4\u957f\u5355\u8bbe\u4e00\u5217\u5de5\u65f6\u53e3\u5f84\uff0c\u907f\u514d\u7528\u4e1a\u52a1\u91cf\u4e0e\u54a8\u8be2\u5e08\u76f4\u63a5\u5bf9\u6bd4\u3002',rows:["
    "{name:'\u9648\u9e4f \u00b7 \u672c\u5468',metric:'\uff089.21\u20149.26\uff0c6 \u5929\uff09\u63a5\u89e6 <b>1</b> \u4eba\u6b21\uff08\u60c5\u7eea\u5e72\u9884 1\uff0c9.24\uff09\u00b7 "
    "\u54a8\u8be2 <b>0</b> \u4eba\u6b21 \u00b7 \u586b\u62a5 <b>1</b> \u5929\uff089.24\uff09',score:'\u2014'},"
    "{name:'\u9648\u9e4f \u00b7 \u4e0a\u5468\u540c\u671f',metric:'\uff089.14\u20149.19\uff0c6 \u5929\uff09\u63a5\u89e6 <b>5</b> \u4eba\u6b21\uff08\u9996\u6b21 1 / \u5e8a\u65c1 4\uff0c9.19\uff09\u00b7 "
    "\u54a8\u8be2 <b>3</b> \u4eba\u6b21\uff08\u4f4f\u9662\u54a8\u8be2 3\uff09\u00b7 \u586b\u62a5 <b>1</b> \u5929\uff089.19\uff09\uff1b\u4e0a\u5468\u5b8c\u6574\u5468 9.14\u20149.20 \u540c\u4e3a 5 / 3 / 1 \u5929',score:'\u2014'},"
    "{name:'\u9648\u9e4f \u00b7 \u7d2f\u8ba1',metric:'\uff088.31\u20149.26\uff09\u63a5\u89e6 <b>13</b> \u4eba\u6b21\uff08\u9996\u6b21 1 / \u5e8a\u65c1 10 / \u60c5\u7eea 2\uff09\u00b7 "
    "\u54a8\u8be2 <b>11</b> \u4eba\u6b21\uff08\u4f4f\u9662 8 / \u5bb6\u5ead 3\uff09\u00b7 \u586b\u62a5 <b>5</b> \u5929',score:'\u2014'}]}")
rep(OLD_LEAD, NEW_LEAD, '⑦ 组长单独工作量')

# ══════════════════════ 八、叙述文案里标注组长身份 ══════════════════════
# 「陈鹏 1 天已填报」的两处并列（基定义 + 覆盖处）
rep('杨霞 2 天 · 陈鹏 1 天已填报，<b>王沛然尚未填报</b>',
    '杨霞 2 天 · 陈鹏 1 天已填报（组长，不参与排名），<b>王沛然尚未填报</b>',
    '叙述·组长标注(基定义)', cnt=1)
rep('赵芳 3 天 · 杨霞 2 天 · 陈鹏 1 天已填报，王沛然 尚未填报',
    '赵芳 3 天 · 杨霞 2 天 · 陈鹏 1 天已填报（组长，不参与排名），王沛然 尚未填报',
    '叙述·组长标注(覆盖处)', cnt=1)

print('═══ 已完成 %d 项 ═══' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('═══ 未匹配 %d 项 ═══' % len(fails))
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
print('\n组长单独列示补丁成功')
