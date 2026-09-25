#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「本周 9.21—9.27」数据与重建后的排名注入看板 index.html。"""
import io, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, 'index.html')
RK = json.load(io.open(os.path.join(REPO, 'data', 'rankings.json'), encoding='utf-8'))
s = io.open(P, encoding='utf-8').read()
PRV = io.open('/tmp/idx.before-w43.html', encoding='utf-8').read()
fails = []


def prv_group(dep, title_kw):
    """从补丁前的版本里取出某个排名组原文（用于保留「岗位类」等非个人排名）"""
    mi = PRV.index(dep + ":{history:[")
    mr = re.search(r'rankGroups:\s*\[', PRV[mi:])
    if not mr:
        return None
    st = mi + mr.end() - 1
    en = None
    i = st; depth = 0; q = None
    while i < len(PRV):
        c = PRV[i]
        if q:
            if c == '\\': i += 2; continue
            if c == q: q = None
        else:
            if c in "'\"": q = c
            elif c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0: en = i + 1; break
        i += 1
    arr = PRV[st:en]
    # 顶层组切分
    i = 1; depth = 0; q = None; cur = ''
    while i < len(arr) - 1:
        c = arr[i]
        if q:
            cur += c
            if c == '\\': cur += arr[i+1]; i += 2; continue
            if c == q: q = None
        else:
            if c in "'\"": q = c; cur += c
            elif c == '{': depth += 1; cur += c
            elif c == '}': depth -= 1; cur += c
            elif c == ',' and depth == 0:
                if title_kw in cur:
                    return cur.strip()
                cur = ''
            else:
                cur += c
        i += 1
    if cur.strip() and title_kw in cur:
        return cur.strip()
    return None


# 需要保留的「岗位类 / 非个人周排名」组
KEEP = [('service', '客服岗位业绩'), ('psychology', '组长专项工作'),
        ('marketing', '业主明细口径'), ('marketing', '营销岗位汇总')]


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n != expect:
        fails.append('%-46s 匹配 %d（期望 %d）' % (tag, n, expect))
        return
    s = s.replace(old, new)


def obj_from(text, start):
    """从 start 处的 { 或 [ 开始做配对（跳过字符串）"""
    i = start; depth = 0; q = None; open_c = text[start]; close_c = '}' if open_c == '{' else ']'
    while i < len(text):
        c = text[i]
        if q:
            if c == '\\': i += 2; continue
            if c == q: q = None
        else:
            if c in "'\"": q = c
            elif c == open_c: depth += 1
            elif c == close_c:
                depth -= 1
                if depth == 0: return i + 1
        i += 1
    return start


def obj_replace(new_body, tag, finder):
    """finder(s) 返回目标对象起始下标（指向 { 或 [）"""
    global s
    st = finder(s)
    if st is None or st < 0:
        fails.append('%-46s 定位失败' % tag); return
    en = obj_from(s, st)
    if en <= st + 20:
        fails.append('%-46s 对象过短' % tag); return
    s = s[:st] + new_body + s[en:]


def esc(t):
    return str(t).replace('\\', '\\\\').replace("'", "\\'")


def js_rows(groups):
    """把生成器的 rankGroups 转成看板用的 JS 字面量"""
    out = []
    for g in groups:
        rows = ','.join(
            "{name:'%s',metric:'%s'%s}" % (
                esc(r['name']), esc(r['metric']),
                (",score:'%s'" % esc(r.get('score'))) if not r.get('missing') else ",missing:true")
            for r in g['rows'])
        out.append("{title:'%s',note:'%s',rows:[%s]}" % (esc(g['title']), esc(g['note']), rows))
    return '[' + ','.join(out) + ']'


def arr_from(text, start):
    i = start; depth = 0; q = None
    while i < len(text):
        c = text[i]
        if q:
            if c == '\\': i += 2; continue
            if c == q: q = None
        else:
            if c in "'\"": q = c
            elif c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0: return i + 1
        i += 1
    return start


svc, psy, mkt = RK['depts']['service']['metrics'], RK['depts']['psychology']['metrics'], RK['depts']['marketing']['metrics']
CUR = '本周（9.21—9.27 · 数据截至 9.25）'

# ───────────────────────── 1. periods 扩为 5 节点
rep("const periods=['8月初','8月中','8月末','上周'];",
    "const periods=['8月初','8月中','8月末','上周','本周'];", '1 periods')
rep("<span>四节点</span>", "<span>${periods.length}节点</span>", '1b 节点标签')

# ───────────────────────── 2. 排名卡分值标签（原先写死「上周」）
rep("${r.missing?'未填报':'上周'}", "${r.missing?'未填报':'本周'}", '2 排名标签')

# ───────────────────────── 3. 趋势序列：追加「本周」节点
HIST = [
    # doctor 主表未滚动 → 本周为 null
    ("['入院人数',[22,16,14,14],'人']", "['入院人数',[22,16,14,14,null],'人']", '3 doctor 入院'),
    ("['门诊人数',[265,282,274,209],'人']", "['门诊人数',[265,282,274,209,null],'人']", '3 doctor 门诊'),
    ("['物理治疗费用',[23.9,36.5,30.8,21.8],'万元']", "['物理治疗费用',[23.9,36.5,30.8,21.8,null],'万元']", '3 doctor 物理费'),
    ("['总收入',[60.8,81,67.9,49.4],'万元']", "['总收入',[60.8,81,67.9,49.4,null],'万元']", '3 doctor 总收入'),
    ("['物理治疗人次',[809,558,530,459],'人次']", "['物理治疗人次',[809,558,530,459,null],'人次']", '3 nursing'),
    # psychology 主表口径留空，另加 V4 口径本周
    ("['个体咨询人数',[53,52,57,40],'人']", "['个体咨询人数',[53,52,57,40,null],'人']", '3 psy 个体'),
    ("['团辅场次',[0,0,2,4],'场']", "['团辅场次',[0,0,2,4,null],'场']", '3 psy 团辅'),
    ("['服务总人数',[54,52,65,40],'人']", "['服务总人数',[54,52,65,40,null],'人']", '3 psy 总人数'),
    ("['咨询收入',[23874,32722,46155,19002],'元']", "['咨询收入',[23874,32722,46155,19002,null],'元']", '3 psy 收入'),
    # service 线上表口径留空，另加台账口径本周
    ("['随访人数',[251,198,224,179],'人']", "['随访人数',[251,198,224,179,null],'人']", '3 svc 随访'),
    ("['接待人次',[290,286,274,218],'人次']", "['接待人次',[290,286,274,218,null],'人次']", '3 svc 接待'),
    ("['义诊人数',[16,14,35,14],'人']", "['义诊人数',[16,14,35,14,null],'人']", '3 svc 义诊'),
    ("['最终到院率',[30.7,34.8,25.8,23.5],'%']", "['最终到院率',[30.7,34.8,25.8,23.5,null],'%']", '3 svc 到院率'),
    # marketing 源表已更新，直接追加本周
    ("['管家有效对接',[85,96,80,80],'人次']", "['管家有效对接',[85,96,80,80,%d],'人次']" % mkt['deal'], '3 mkt 对接'),
    ("['管家转住院',[12,17,14,14],'人']", "['管家转住院',[12,17,14,14,%d],'人']" % mkt['admit'], '3 mkt 住院'),
    ("['转住院率',[14.1,17.7,17.5,17.5],'%']", "['转住院率',[14.1,17.7,17.5,17.5,%s],'%%']" % mkt['rate'], '3 mkt 率'),
    ("['心理咨询服务',[10,14,15,19],'人次']", "['心理咨询服务',[10,14,15,19,null],'人次']", '3 mkt 心理'),
]
for o, n, t in HIST:
    rep(o, n, t)

# 新增「台账口径」序列（只有近两周有数据，前面留空）
rep("['随访人数',[251,198,224,179,null],'人'],",
    "['导医回访台账',[null,null,null,%d,%d],'条'],['随访人数',[251,198,224,179,null],'人'],"
    % (svc['callbackPrev'], svc['callback']), '3d 新增台账-回访')
rep("['义诊人数',[16,14,35,14,null],'人'],",
    "['导诊主动服务',[null,null,null,%d,%d],'条'],['义诊人数',[16,14,35,14,null],'人'],"
    % (svc['visitlogPrev'], svc['visitlog']), '3d 新增主动服务')
rep("['最终到院率',[30.7,34.8,25.8,23.5,null],'%']],",
    "['最终到院率',[30.7,34.8,25.8,23.5,null],'%'],"
    "['导医日工作量',[null,null,null,{a},{b}],'分']],".format(a=svc['workloadScorePrev'], b=svc['workloadScore']),
    '3d 新增日工作量')
rep("['咨询收入',[23874,32722,46155,19002,null],'元']],",
    "['咨询收入',[23874,32722,46155,19002,null],'元'],"
    "['患者接触（V4）',[null,null,null,%d,%d],'人次'],"
    "['咨询工作量（V4）',[null,null,null,%d,%d],'人次']],"
    % (psy['contactPrev'], psy['contact'], psy['advicePrev'], psy['advice']),
    '3d 新增心理V4')

# ───────────────────────── 4. rankGroups 整体替换
for dep, nm in [('service', '客服服务部'), ('psychology', '心理咨询组'), ('marketing', '营销中心')]:
    mi = s.index(dep + ":{history:[")
    mr = re.search(r'rankGroups:\s*\[', s[mi:])
    if not mr:
        fails.append('4 %s 未找到 rankGroups' % dep); continue
    st = mi + mr.end() - 1
    en = arr_from(s, st)
    old = s[st:en]
    kept = [prv_group(dep, kw) for d, kw in KEEP if d == dep]
    kept = [k for k in kept if k]
    body = js_rows(RK['depts'][dep]['rankGroups'])
    for k in kept:
        body = body[:-1] + ',' + k + ']'
        if not re.search(r"\d+、|①|②|③", k[:60]):
            pass
    new = body
    if len(old) < 100:
        fails.append('4 %s rankGroups 过短' % dep); continue
    s = s[:st] + new + s[en:]

# ───────────────────────── 5. 部门卡 summary / delta / 本周行
rep("summary:'导医回访台账',delta:'67 条'", "summary:'导医回访台账',delta:'52 条'", '5a svc summary')
rep("summary:'上周患者接触',delta:'−52.1%'", "summary:'本周患者接触',delta:'−37.5%'", '5b psy summary')
rep("summary:'管家对接（上周）',delta:'持平'", "summary:'管家对接（本周）',delta:'−41.2%'", '5c mkt summary')

NEW_M = {
 'service': "'%s',null,null,'','导医回访台账本周回访 <b>%d 条</b>、到院 <b>%d 人（%.1f%%）</b>：蒋雨 29（13 = 44.8%%）/ 张欣雨 16（3 = 18.8%%）/ 温诗怡 7（2 = 28.6%%）；上周 %s 为 %d / %d（%.1f%%），回访 <b>%+.1f%%</b>、到院 %+.1f%%。导诊主动服务 <b>%d 条</b>（上周 %d）；日工作量 <b>%d 人日 / %s 分</b>（上周 %d 人日 / %s 分，<b>%+.1f%%</b>）。<b>三项个人排名已按本周重建</b>'" % (
    CUR, svc['callback'], svc['arrived'], svc['arriveRate'], '9.14—9.20', svc['callbackPrev'], svc['arrivedPrev'], svc['arriveRatePrev'],
    svc['callbackDelta'], svc['arrivedDelta'], svc['visitlog'], svc['visitlogPrev'],
    svc['workloadDays'], '{:,.0f}'.format(svc['workloadScore']), svc['workloadDaysPrev'],
    '{:,.0f}'.format(svc['workloadScorePrev']), svc['workloadDelta']),
 'psychology': "'%s',null,null,'','管理表 V4「咨询师每日简报」本周患者接触 <b>%d 人次</b>（冯浩鹏 14 · 赵芳 5 · 杨霞 4 · 蔡宜蓉 1 · 陈鹏 1）、咨询工作量 <b>%d</b>、家长工作 0；上周 %s 为 %d / %d，接触 <b>%+.1f%%</b>、咨询 <b>%+.1f%%</b>。<b>王沛然本周未填报</b>，需先确认为休假还是漏报。累计（自 8.31）接触 %d / 咨询 %d。<b>排名已按本周重建</b>'" % (
    CUR, psy['contact'], psy['advice'], '9.14—9.20', psy['contactPrev'], psy['advicePrev'],
    psy['contactDelta'], psy['adviceDelta'], psy['cumContact'], psy['cumAdvice']),
 'marketing': "'%s',null,null,'','《患者有效对接表》逐条记录本周对接 <b>%d 条</b>（朱婧 17 / 金林 16 / 利娟 14；<b>菲菲与国威本周无新增</b>），检查 20 · 物理 12 · 心理 11 · 转住院 <b>%d 人（%.1f%%）</b>；上周 %s 为 %d 条 / %d 人（%.1f%%），对接 <b>%+.1f%%</b>。绿色通道转诊到院 13 人（与管家转住院不同口径，不可相加）。<b>排名已按本周重建</b>'" % (
    CUR, mkt['deal'], mkt['admit'], mkt['rate'], '9.14—9.20', mkt['dealPrev'], mkt['admitPrev'], mkt['ratePrev'], mkt['delta']),
}
for dep, nm, key in [('service', '客服服务部', 'service'), ('psychology', '心理咨询组', 'psychology'), ('marketing', '营销中心', 'marketing')]:
    base = s.index(dep + ":{name:'" + nm + "'")
    mi = s.index('metrics:[', base)
    st = s.index('[', mi)
    en = arr_from(s, st)
    inner = s[st + 1:en - 1]
    # 首个顶层元素
    depth = 0; q = None; cut = -1
    for i, c in enumerate(inner):
        if q:
            if c == '\\': continue
            if c == q: q = None
        else:
            if c in "'\"": q = c
            elif c in '[{': depth += 1
            elif c in ']}': depth -= 1
            elif c == ',' and depth == 0:
                cut = i; break
    if cut < 0:
        fails.append('5 %s 首个元素定位失败' % dep); continue
    old_first = inner[:cut]
    if '本周' not in old_first:
        fails.append('5 %s 首个元素非本周行' % dep); continue
    s = s[:st + 1] + '[' + NEW_M[key] + ']' + inner[cut:] + s[en - 1:]

# ───────────────────────── 6. DEPT_CARD：小卡值与趋势（整体替换对象）
_CARD = {
 'service': "{m1:{label:'导医回访台账',value:'52',unit:'条'},         trend:[38,7,6,1,0,0,0],axis:'d21',         note:'导医回访台账本周 52 条（《医院客服与导诊部》标准化回访台账 9.21—9.24 逐日 38/7/6/1），到院 18 人（34.6%）；上周 9.14—9.20 为 67 条 / 到院 30 人（44.8%）'}",
 'psychology': "{m1:{label:'本周患者接触',value:'25',unit:'人次'},         trend:[4,6,0,7,0,5,3],axis:'d21',         note:'本周患者接触 25 人次（管理表 V4「咨询师每日简报」9.21—9.25 逐日 4/6/0/7/0/5/3）；上周 9.14—9.20 为 40 人次，环比 −37.5%。本周王沛然未填报'}",
 'marketing': "{m1:{label:'管家对接',value:'47',unit:'条'},m2:{label:'转住院率',value:'23.4',unit:'%'},         trend:[10,13,8,9,7,0,0],axis:'d21',         note:'本周有效对接 47 条（《患者有效对接表》一人一表逐条：朱婧 17 / 金林 16 / 利娟 14；菲菲、国威本周无新增），转住院 11 人（23.4%）；上周 9.14—9.20 为 80 条 / 14 人（17.5%），对接环比 −41.2%。本周数据截至 9.25'}",
}
def _card_finder(key):
    base = s.index('const DEPT_CARD')
    m = re.search(r'\b' + key + r':\{m1:\{', s[base:])
    return (base + m.start() + len(key) + 1) if m else None
for _k, _v in _CARD.items():
    obj_replace(_v, '6 %s 小卡' % _k, (lambda k: (lambda _s: _card_finder(k)))(_k))

# ───────────────────────── 7. deptDaily 范围与本周指标
rep("range:'9月14—20日（导医台账 + 客服线上表）',metrics:[['导医回访','67条'],['主动服务','12条'],['日工作量','3,382分']]",
    "range:'本周 9月21—27日（导医台账 + 客服线上表）',metrics:[['导医回访','52条'],['主动服务','42条'],['日工作量','2,783分']]",
    '7a svc deptDaily')
def _daily_finder(key):
    b2 = s.index('const deptDaily')
    m2 = re.search(r'\b' + key + r':\{', s[b2:])
    return (b2 + m2.start() + len(key) + 1) if m2 else None
def _psy_daily_fix(s_):
    """只改 range 与 metrics，保留 list / note 等内容（整体替换会丢字段）"""
    global s
    b2 = s.index('const deptDaily') if 'const deptDaily' in s else 0
    st = _daily_finder('psychology')
    if not st:
        fails.append('7b psy deptDaily 定位失败'); return
    en = obj_from(s, st)
    seg = s[st:en]
    ns = re.sub(r"range:'[^']*'",
                "range:'本周 9月21—27日（管理表 V4 为准；主表表头未滚动）'", seg, count=1)
    # metrics 是嵌套数组，必须按括号配对整体替换（用 [^\]]* 只会截到第一个 ]，会留下残片）
    mm = re.search(r'metrics:\s*\[', ns)
    if mm:
        mst = ns.index('[', mm.start())
        men = obj_from(ns, mst)
        ns = ns[:mm.start()] + "metrics:[['患者接触（V4）','25人次'],['咨询工作量（V4）','13人次'],['累计接触','238人次'],['累计咨询','122人次']]" + ns[men:]
    if ns == seg:
        fails.append('7b psy deptDaily 未发生替换')
    s = s[:st] + ns + s[en:]
_psy_daily_fix(s)
rep("range:'9月14—20日（患者对接表 + 营收日报 + 活动与绿色通道叙述）',metrics:[['管家上周对接','78条'],['上周转住院率','17.9%'],['上周转住院','14人'],['绿色通道转诊到院','13人'],['工娱活动参与','86人']]",
    "range:'本周 9月21—27日（患者对接表 + 营收日报 + 活动与绿色通道叙述）',metrics:[['管家本周对接','47条'],['本周转住院率','23.4%'],['本周转住院','11人'],['绿色通道转诊到院','13人'],['工娱活动参与','86人']]",
    '7c mkt deptDaily')

# ───────────────────────── 8. 顶层时间戳
rep("数据更新至 2026年9月25日", "数据更新至 2026年9月26日", '8a 时间戳', expect=s.count('数据更新至 2026年9月25日'))
rep("更新于 2026.09.25", "更新于 2026.09.26", '8b 徽标', expect=s.count('更新于 2026.09.25'))

if fails:
    print('补丁未通过：')
    for f in fails:
        print('  ✗', f)
    sys.exit(1)

io.open(P, 'w', encoding='utf-8').write(s)
print('✓ 注入完成，index.html %d bytes' % len(s.encode()))
