#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-26 第三轮改版（业主指令）

① 主看板「经营问题总览」（#decisionCore，由 business-analysis.js 动态插入）
   挪到「员工排名」原来的位置 —— 即 10 月经营面板（#monthCommandCenter）之后。
② 删掉主看板的「员工排名」（#staffRank）—— 排名只在各部门专属抽屉的
   「员工排名」页里看，避免同一套排名在两处各渲染一遍（且主看板那份
   在窄栏里被压成一列、文字逐字换行）。
③ 主看板「工娱活动」（#recModule）整块移入营销中心抽屉，替代原来那块
   「绿色通道」样式（.green-channel / #deptSpecialPanel）的工娱摘要。

跑法：PYTHONDONTWRITEBYTECODE=1 python3 scripts/live-data/patch_layout_1026.py
幂等：已处理过的特征存在时直接跳过对应步骤。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IDX = os.path.join(ROOT, "index.html")
BA = os.path.join(ROOT, "business-analysis.js")
MARK = "/* == LAYOUT-2026-10-26 == */"


def read(p):
    with io.open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)


# ─────────────────────────────────────────────────────────── 工娱模块（抽屉版）
# 视觉语言沿用主看板那一套（rec-*），但按 460px 抽屉重排：
# 4 个 KPI 改 2×2、两张卡改单列、字号收一档。数据口径一字不改。
REC_DRAWER = (
    '<section class="rec-module" id="deptSpecialPanel">'
    '<div class="rec-head"><div>'
    '<div class="rec-title"><h3>工娱活动</h3>'
    '<span class="rec-badge">10.19–10.25 · 营销中心 · 本周未报</span></div>'
    '<p class="rec-sub">住院部工娱活动的患者与家属参与、积分兑换。独立成模块核算，'
    '<b>不与管家转化、渠道转诊、护理治疗量混算</b>。</p>'
    '</div></div>'
    '<div class="rec-kpis">'
    '<div class="rec-kpi p"><label>患者参与</label><strong>—<em>人</em></strong>'
    '<span class="rec-chg warn">本周未提交</span>'
    '<span class="rec-note">营销中心未报 10.19—10.25 数据</span></div>'
    '<div class="rec-kpi f"><label>家属参与</label><strong>—<em>人</em></strong>'
    '<span class="rec-chg warn">本周未提交</span>'
    '<span class="rec-note">同上，<b>不拿上一期 45 人补位</b></span></div>'
    '<div class="rec-kpi t"><label>合计参与</label><strong>—<em>人</em></strong>'
    '<span class="rec-chg flat">缺项记 null</span>'
    '<span class="rec-note">患者＋家属两列到位后才可相加</span></div>'
    '<div class="rec-kpi j"><label>积分兑换</label><strong>16<em>人</em></strong>'
    '<span class="rec-chg warn">10 月累计</span>'
    '<span class="rec-note">10.1—10.18，<b>月累计、非本周单周值</b></span></div>'
    '</div>'
    '<div class="rec-grid">'
    '<div class="rec-card"><h3>本期结构与对照</h3>'
    '<p class="rec-cap">本周无数据，<b>不画结构条</b>——空缺不拿上一期补位，'
    '避免把上周构成当本周业绩。</p>'
    '<div class="rec-stack"><i class="sp" '
    'style="width:100%;background:linear-gradient(180deg,#EDF0F6,#E4E8F0);color:#7C828F">'
    '本周未提交 · 10.19—10.25</i></div>'
    '<div class="rec-legend"><span>患者 <b>—</b></span><span>家属 <b>—</b></span>'
    '<span>合计 <b>—</b></span></div></div>'
    '<div class="rec-card"><h3>上一期对照（仅参照）</h3>'
    '<p class="rec-cap">以下为上一期 <b>10.12—10.18</b> 已确认值，'
    '<b>只作趋势对照，不计入本期任何指标</b>。</p>'
    '<div class="rec-row"><span class="rl">患者</span><span class="rv">111 人</span></div>'
    '<div class="rec-row"><span class="rl">家属</span><span class="rv">45 人</span></div>'
    '<div class="rec-row"><span class="rl">合计</span><span class="rv"><b>156 人</b></span></div>'
    '</div></div>'
    '<div class="rec-foot"><span>工娱数据：本周（10.19–10.25）营销中心<b>尚未提交</b>，'
    '模块内患者 / 家属 / 合计三格一律记 <b>—</b>，不拿上一期 156 人顶替。'
    '<b>上一期（10.12—10.18）</b>报数为患者 111 人 ＋ 家属 45 人 ＝ 156 人、'
    '积分兑换 10 月累计 16 人（截至 10.18），<b>仅作对照，不作为本期业绩</b>。'
    '⚠ 汇报表护理组表头的「工娱 5 场 / 62 人次」为另一口径（场次 / 人次，非人数），'
    '<b>与 156 人不可相加</b>；本周无场次数据，场均记 null。</span></div>'
    '</section>'
)


def step_rec_to_drawer(html):
    """删主看板工娱模块，并把它的 CSS 改造成 .rec-module 作用域注入全局。"""
    if 'id="recModule"' not in html:
        print("  · 主看板工娱模块已删除，跳过")
        return html, None

    start_tag = '<section class="section" id="recModule">'
    a = html.find(start_tag)
    b = html.find("</section>", a) + len("</section>")
    seg = html[a:b]
    assert seg.count("</section>") == 1 and seg.count("<section") == 1, "工娱段边界异常"

    # 截图内联 <style>，把选择器作用域从 #recModule 换成 .rec-module
    m = re.search(r"<style>\s*(.*?)</style>", seg, re.S)
    assert m, "工娱 <style> 未找到"
    css = m.group(1)
    css = css.replace("#recModule", ".rec-module")
    # 抽屉宽度不定（桌面全宽 / 移动端 100%），所以一律用 auto-fit 自适应：
    #   宽屏 → KPI 4 列、两张卡并排；窄屏 → KPI 2 列或 1 列、卡片堆叠
    css = css.replace(
        ".rec-module .rec-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}",
        ".rec-module .rec-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}")
    css = css.replace(
        ".rec-module .rec-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:12px;margin-top:12px}",
        ".rec-module .rec-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px;margin-top:10px}")
    css = css.replace(
        ".rec-module .rec-kpi strong{display:block;font-size:30px;",
        ".rec-module .rec-kpi strong{display:block;font-size:26px;")
    css = css.replace(
        ".rec-module .rec-title h2{margin:0;font-size:19px;",
        ".rec-module .rec-title h3{margin:0;font-size:18px;")
    css = css.replace(
        ".rec-module .rec-row{display:grid;grid-template-columns:58px 1fr 120px;",
        ".rec-module .rec-row{display:grid;grid-template-columns:52px minmax(0,1fr);")
    css = css.replace(
        ".rec-module .rec-row .rv{text-align:right;",
        ".rec-module .rec-row .rv{text-align:right;justify-self:end;")
    # 原 @media(max-width:1180px) 里写死的 2 列 / 1 列规则会和 auto-fit 打架，整段去掉
    css = re.sub(r"@media\(max-width:1180px\)\{\.rec-module .*?\}\}\s*\n?", "", css, flags=re.S)
    css = css + (
        "\n.rec-module{margin:4px 0 16px;padding:0 0 14px;border-bottom:1px dashed #E1E5EF}\n"
        ".rec-module .rec-stack{height:38px}\n"
        # 窄屏（390px 抽屉）标题与 badge 会挤在一行，允许换行
        ".rec-module .rec-title{flex-wrap:wrap}\n"
        # 「本期未报」用绿色底会被读成「正常」，改琥珀警示色
        ".rec-module .rec-badge{color:#8A5A12;background:#FFF4E2;border-color:#F0DFC0}\n"
    )
    # 删除主看板区块
    html = html[:a] + html[b:]

    # 注入到全局（</main> 之前，与其它零散 <style> 同层）
    anchor = "\n</div></main>"
    if anchor not in html:
        anchor = "</main>"
    injected = ('<style id="recModuleCss">' + MARK + "\n" + css.strip() + "\n</style>")
    html = html.replace(anchor, "\n" + injected + anchor, 1)
    print("  ✓ 主看板工娱模块已移出，CSS 改为 .rec-module 作用域注入全局")
    return html, seg


def step_drop_staff_rank(html):
    if 'id="staffRank"' not in html:
        print("  · 主看板员工排名已删除，跳过")
        return html
    tag = '<section class="section" id="staffRank">'
    a = html.find(tag)
    b = html.find("</section>", a) + len("</section>")
    seg = html[a:b]
    assert seg.count("</section>") == 1 and seg.count("<section") == 1, "员工排名段边界异常"
    # 顺带吃掉紧随的换行/缩进
    while b < len(html) and html[b] == "\n":
        b += 1
    html = html[:a] + html[b:]
    print("  ✓ 主看板员工排名 #staffRank 已删除（%d 字节）" % len(seg))
    return html


def step_dept_panel_to_rec(html):
    """营销抽屉里那块 green-channel 工娱摘要 → 完整工娱模块。"""
    if '<section class="rec-module" id="deptSpecialPanel">' in html:
        print("  · 营销抽屉工娱模块已就位，跳过")
        return html
    # 定位 insertAdjacentHTML('afterbegin', `...`); 整段
    key = "if(key==='marketing')document.getElementById('trendPane').insertAdjacentHTML('afterbegin',`"
    i = html.find(key)
    assert i > 0, "未找到营销抽屉 green-channel 模板"
    j = html.find("`);", i)
    assert j > 0, "模板结尾未找到"
    old = html[i:j + 3]
    # 模板内不能出现反引号 / ${ ，生成前自检
    assert "`" not in REC_DRAWER and "${" not in REC_DRAWER
    new = key + REC_DRAWER + "`);"
    html = html[:i] + new + html[j + 3:]
    print("  ✓ 营销抽屉「绿色通道」块 → 工娱活动模块（%d → %d 字节）" % (len(old), len(new)))
    return html


def step_ba_relocate():
    """business-analysis.js：decisionCore 插到 10 月面板之后（原员工排名位）。"""
    s = read(BA)
    if MARK in s:
        print("  · business-analysis.js 已迁移逻辑，跳过")
        return
    helper = (
        "  " + MARK + "\n"
        "  /* 业主 2026-10-26：经营问题总览挪到「员工排名」原来的位置。\n"
        "     主看板不再单独放员工排名（排名只进各部门专属抽屉），\n"
        "     所以本块紧跟在 10 月经营面板 #monthCommandCenter 之后。\n"
        "     ⚠ 月面板由 month-dashboard.js 在后续脚本里挂载，首次 mount 时锚点可能还不存在，\n"
        "       故 boot 里再补一次 load / 延迟校正，幂等。 */\n"
        "  function placeDecisionCore(){\n"
        "    var dc=document.getElementById('decisionCore');\n"
        "    if(!dc||!dc.parentNode) return;\n"
        "    var anchor=document.getElementById('monthCommandCenter');\n"
        "    if(!anchor||!anchor.parentNode||anchor.parentNode!==dc.parentNode) return;\n"
        "    if(anchor.nextElementSibling!==dc) anchor.parentNode.insertBefore(dc,anchor.nextElementSibling);\n"
        "  }\n"
    )
    old = "  /* 首次渲染 + 数据更新后重绘（结构不变，只更新数字） */\n  function mount(){"
    assert s.count(old) == 1
    s = s.replace(old, helper + "\n" + old)

    old2 = (
        "    if(overview) overview.insertAdjacentHTML('afterend', buildHTML());\n"
        "    var rank=document.getElementById('rankGovernance'),workspace=document.querySelector('.workspace');"
    )
    assert s.count(old2) == 1
    new2 = (
        "    if(overview) overview.insertAdjacentHTML('afterend', buildHTML());\n"
        "    placeDecisionCore();\n"
        "    var rank=document.getElementById('rankGovernance'),workspace=document.querySelector('.workspace');"
    )
    s = s.replace(old2, new2)

    old3 = "  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();"
    assert s.count(old3) == 1
    new3 = (
        "  window.addEventListener('load',function(){try{placeDecisionCore();}catch(e){}});\n"
        "  setTimeout(function(){try{placeDecisionCore();}catch(e){}},300);\n"
        "  setTimeout(function(){try{placeDecisionCore();}catch(e){}},900);\n" + old3
    )
    s = s.replace(old3, new3)
    write(BA, s)
    print("  ✓ business-analysis.js：decisionCore 改为锚定 #monthCommandCenter")


def step_md_drop_rank():
    """月面板（month-dashboard.js）里的「本期动态排名 / 员工绩效试算」也删掉。

    业主 2026-10-26：主看板不放员工排名，排名只在各部门专属抽屉的
    「员工排名」页看。这里保留「排名数据治理决策」卡（它是规则说明与入口，
    不是排名数据），只去掉标题行与试算表。
    """
    p = os.path.join(ROOT, "month-dashboard.js")
    s = read(p)
    if "本期动态排名" not in s:
        print("  · month-dashboard.js 排名块已删除，跳过")
        return
    lines = s.split("\n")
    drop = []
    for i, ln in enumerate(lines):
        if "本期动态排名" in ln or "员工绩效试算" in ln:
            # 只删「整行就是一个字符串片段」的那种（以 '+ 结尾的拼接行）
            if ln.lstrip().startswith("'<") and ln.rstrip().endswith("'+") or ln.rstrip().endswith("'"):
                drop.append(i)
    assert len(drop) == 2, "月面板排名行定位异常：%r" % drop
    for i in reversed(drop):
        lines.pop(i)
    s = "\n".join(lines)

    # #mdRankTable 已不存在 → 事件绑定必须容错，否则点击 tab 时抛错中断整个 bind
    old = ("var tab=e.target.closest('[data-rank]');if(tab){document.querySelectorAll('[data-rank]').forEach"
           "(function(b){b.classList.toggle('active',b===tab);});document.getElementById('mdRankTable')"
           ".innerHTML=ranking(tab.dataset.rank);return;}")
    new = ("var tab=e.target.closest('[data-rank]');if(tab){document.querySelectorAll('[data-rank]').forEach"
           "(function(b){b.classList.toggle('active',b===tab);});var _rt=document.getElementById('mdRankTable');"
           "if(_rt)_rt.innerHTML=ranking(tab.dataset.rank);return;}")
    if s.count(old) == 1:
        s = s.replace(old, new)
    write(p, s)
    print("  ✓ month-dashboard.js：本期动态排名 / 员工绩效试算已删除（保留治理规则卡）")


def step_version(html):
    m = re.findall(r"\?v=(20261026[a-z])", html)
    if not m:
        print("  · 版本号无需处理")
        return html
    cur = sorted(set(m))[-1]
    nxt = "20261026" + chr(ord(cur[-1]) + 1)
    html = html.replace("?v=" + cur, "?v=" + nxt)
    print("  ✓ 静态资源版本号 %s → %s" % (cur, nxt))
    return html


def main():
    html = read(IDX)
    print("① 工娱模块移入营销抽屉")
    html, _ = step_rec_to_drawer(html)
    print("② 删除主看板员工排名")
    html = step_drop_staff_rank(html)
    print("②b 月面板排名块")
    step_md_drop_rank()
    print("③ 营销抽屉模板替换")
    html = step_dept_panel_to_rec(html)
    print("④ 经营问题总览定位")
    step_ba_relocate()
    print("⑤ 版本号")
    html = step_version(html)
    write(IDX, html)
    print("完成：index.html %d 字节" % len(html))


if __name__ == "__main__":
    sys.exit(main())
