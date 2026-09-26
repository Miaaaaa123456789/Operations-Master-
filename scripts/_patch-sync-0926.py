#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 2026-09-26 抓取到的新数据注入看板（营销 63/13、心理 37/19）。

口径要点
  · 统计区间 9.21—9.26（**不是** 9.27）：源表里管家预填了次日的预约行
    （金林 9.27、利娟 9.27/9.29），有姓名有业务标记，只能靠日期挡。
  · 营收日报仍只到 9.24 → 营销面板的营业额/逐日柱状图不动，时间戳分别标注。
  · 主表（医生组 / 护理组）指纹未变 → 医生、护理数据保持原样。

只改数据与文案，不改结构与排序口径（排名口径见 _patch-rank-nodays.py）。
"""
import io, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, 'index.html')
RK = json.load(io.open(os.path.join(REPO, 'data', 'rankings.json'), encoding='utf-8'))
s = io.open(P, encoding='utf-8').read()
before = len(s)
fails = []

SV, PS, MK = RK['depts']['service'], RK['depts']['psychology'], RK['depts']['marketing']
sv, ps, mk = SV['metrics'], PS['metrics'], MK['metrics']

CONTACT = ps['contact']        # 37
ADVICE = ps['advice']          # 19
CUM_C = ps['cumContact']       # 250
CUM_A = ps['cumAdvice']        # 128
CDELTA = '%+.1f' % ps['contactDelta']
DEAL = mk['deal']              # 63
ADMIT = mk['admit']            # 13
RATE = '%.1f' % mk['rate']     # 20.6
MDELTA = '%+.1f' % mk['delta']
PER_PSY = '朱婧 26 / 金林 24 / 利娟 13'


def rep(old, new, tag, expect=1):
    global s
    n = s.count(old)
    if n != expect:
        fails.append('%-50s 匹配 %d（期望 %d）' % (tag, n, expect))
        return
    s = s.replace(old, new)


def esc(t):
    return str(t).replace('\\', '\\\\').replace("'", "\\'")


def js_rows(groups):
    """rankGroups → 看板 JS 字面量（透传 rankless / scoreLabel）"""
    out = []
    for g in groups:
        rows = ','.join(
            "{name:'%s',metric:'%s'%s}" % (
                esc(r['name']), esc(r['metric']),
                (",score:'%s'" % esc(r.get('score'))) if not r.get('missing') else ",missing:true")
            for r in g['rows'])
        extra = ''
        if g.get('rankless'):
            extra += ',rankless:true'
        if g.get('scoreLabel'):
            extra += ",scoreLabel:'%s'" % esc(g['scoreLabel'])
        out.append("{title:'%s',note:'%s'%s,rows:[%s]}" % (esc(g['title']), esc(g['note']), extra, rows))
    return '[' + ','.join(out) + ']'


def arr_end(text, start):
    i, depth, q = start, 0, None
    while i < len(text):
        c = text[i]
        if q:
            if c == '\\':
                i += 2
                continue
            if c == q:
                q = None
        else:
            if c in "'\"":
                q = c
            elif c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return start


def split_top(arr):
    out, cur, depth, q, i = [], '', 0, None, 1
    while i < len(arr) - 1:
        c = arr[i]
        if q:
            cur += c
            if c == '\\':
                cur += arr[i + 1]
                i += 2
                continue
            if c == q:
                q = None
        else:
            if c in "'\"":
                q = c
                cur += c
            elif c == '{':
                depth += 1
                cur += c
            elif c == '}':
                depth -= 1
                cur += c
            elif c == ',' and depth == 0:
                if cur.strip():
                    out.append(cur.strip())
                cur = ''
            else:
                cur += c
        i += 1
    if cur.strip():
        out.append(cur.strip())
    return out


def replace_groups(dep, new_js, keep_kw, tag):
    """把某部门的 rankGroups 换成「新生成组 + 保留的岗位类组」"""
    global s
    # ⚠ 各部门字段前的分隔不一：psychology / marketing 是「换行 + 6 空格」，
    #    service 是「逗号」。用宽松匹配，别写死缩进。
    m = re.search(r"(?:^|[\n,])\s*" + dep + r":\{history:", s)
    if not m:
        fails.append('%-50s 未定位到 %s' % (tag, dep))
        return
    j = s.index('rankGroups:[', m.start()) + len('rankGroups:')
    e = arr_end(s, j)
    groups = split_top(s[j:e])
    kept = [g for g in groups if any(k in g for k in keep_kw)]
    body = new_js.strip()[1:-1]
    n_new = len(split_top(new_js))
    parts = ([body] if body else []) + kept
    s = s[:j] + '[\n' + ',\n'.join(parts) + ']' + s[e:]
    print('  · %-10s 新 %d 组 + 保留 %d 组' % (tag, n_new, len(kept)))


# ═══════════════════════════════ 1. 时间戳
rep('title="本页主口径：本周 9.21—9.27（进行中 · 数据截至 9.24，营收 9.22）"',
    'title="本页主口径：本周 9.21—9.27（进行中 · 数据截至 9.26，营收 9.24）"', '1a rangeChip')
rep('<span class="ov-live"><i></i>每日 09:00 抓取 · 数据更新至 9.24</span>',
    '<span class="ov-live"><i></i>每日 09:00 抓取 · 数据更新至 9.26</span>', '1b ov-live')
rep('数据截至 9.24（营收日报至 9.22；客服 / 心理 / 管家已并入本周至今值）',
    '数据截至 9.26（营收日报至 9.24；客服 / 心理 / 管家已并入本周至今值）', '1c 首页口径段')
rep('<h2>9月1日—9月22日</h2><p>周口径：本周 9.21—9.27（进行中 · 数据截至 9.22）· 上周同期 9.14—9.15（同为 2 天）</p></div><span class="sales-badge">更新于 2026.09.22</span>',
    '<h2>9月1日—9月24日</h2><p>周口径：本周 9.21—9.27（进行中 · 营收数据截至 9.24）· 上周同期 9.14—9.17（同为 4 天）</p></div><span class="sales-badge">更新于 2026.09.24</span>',
    '1d 营销月度栏(静态)')
rep("datebar.querySelector('h2').textContent='9月1日—9月22日';datebar.querySelector('p').textContent='周口径：本周 9.21—9.27（进行中 · 数据截至 9.22）· 上周同期 9.14—9.15（同为 2 天）；旧口径的第一周 9.1—9.6 只有 6 天，不并入上周对比';datebar.querySelector('.sales-badge').textContent='更新于 2026.09.22';",
    "datebar.querySelector('h2').textContent='9月1日—9月24日';datebar.querySelector('p').textContent='周口径：本周 9.21—9.27（进行中 · 营收数据截至 9.24）· 上周同期 9.14—9.17（同为 4 天）；旧口径的第一周 9.1—9.6 只有 6 天，不并入上周对比';datebar.querySelector('.sales-badge').textContent='更新于 2026.09.24';",
    '1e 营销月度栏(JS)')

# ═══════════════════════════════ 2. rankGroups
replace_groups('service', js_rows(SV['rankGroups']), ['客服岗位业绩'], '2a 客服')
replace_groups('psychology', js_rows(PS['rankGroups']), ['组长专项工作'], '2b 心理')
replace_groups('marketing', js_rows(MK['rankGroups']), ['业主明细口径', '营销岗位汇总'], '2c 营销')

# ═══════════════════════════════ 3. DEPT_CARD
rep("psychology:{m1:{label:'本周患者接触',value:'25',unit:'人次'},         trend:[4,6,0,7,0,5,3],axis:'d21',         note:'本周患者接触 25 人次（管理表 V4「咨询师每日简报」9.21—9.25 逐日 4/6/0/7/0/5/3）；上周 9.14—9.20 为 40 人次，环比 −37.5%。本周王沛然未填报'}",
    "psychology:{m1:{label:'本周患者接触',value:'" + str(CONTACT) + "',unit:'人次'},         trend:[8,4,8,10,6,1,0],axis:'d21',         note:'本周患者接触 " + str(CONTACT) + " 人次（管理表 V4「咨询师每日简报」9.21—9.26 逐日 8/4/8/10/6/1）；上周 9.14—9.20 为 40 人次，环比 " + CDELTA + "%。本周王沛然未填报'}",
    '3a DEPT_CARD.psychology')
rep("marketing:{m1:{label:'管家对接',value:'47',unit:'条'},m2:{label:'转住院率',value:'23.4',unit:'%'},         trend:[10,13,8,9,7,0,0],axis:'d21',         note:'本周有效对接 47 条（《患者有效对接表》一人一表逐条：朱婧 17 / 金林 16 / 利娟 14；菲菲、国威本周无新增），转住院 11 人（23.4%）；上周 9.14—9.20 为 80 条 / 14 人（17.5%），对接环比 −41.2%。本周数据截至 9.25'}",
    "marketing:{m1:{label:'管家对接',value:'" + str(DEAL) + "',unit:'条'},m2:{label:'转住院率',value:'" + RATE + "',unit:'%'},         trend:[2,6,3,17,15,20,0],axis:'d21',         note:'本周有效对接 " + str(DEAL) + " 条（《患者有效对接表》一人一表逐条：" + PER_PSY + "；菲菲、国威本周无新增），转住院 " + str(ADMIT) + " 人（" + RATE + "%）；上周 9.14—9.20 为 80 条 / 14 人（17.5%），对接环比 " + MDELTA + "%。本周数据截至 9.26'}",
    '3b DEPT_CARD.marketing')

# ═══════════════════════════════ 4. history 本周节点
rep("['患者接触（V4）',[null,null,null,40,25],'人次']",
    "['患者接触（V4）',[null,null,null,40," + str(CONTACT) + "],'人次']", '4a 心理接触序列')
rep("['咨询工作量（V4）',[null,null,null,26,13],'人次']",
    "['咨询工作量（V4）',[null,null,null,26," + str(ADVICE) + "],'人次']", '4b 心理咨询序列')
rep("['管家有效对接',[85,96,80,80,47],'人次']",
    "['管家有效对接',[85,96,80,80," + str(DEAL) + "],'人次']", '4c 管家对接序列')
rep("['管家转住院',[12,17,14,14,11],'人']",
    "['管家转住院',[12,17,14,14," + str(ADMIT) + "],'人']", '4d 管家转住院序列')
rep("['转住院率',[14.1,17.7,17.5,17.5,23.4],'%']",
    "['转住院率',[14.1,17.7,17.5,17.5," + RATE + "],'%']", '4e 转住院率序列')

# ═══════════════════════════════ 5. deptDaily
rep("psychology:{range:'本周 9月21—27日（管理表 V4 为准；主表表头未滚动）',\n        metrics:[['患者接触（V4）','25人次'],['咨询工作量（V4）','13人次'],['累计接触','238人次'],['累计咨询','122人次']],",
    "psychology:{range:'本周 9月21—26日（管理表 V4 为准；主表表头未滚动）',\n        metrics:[['患者接触（V4）','" + str(CONTACT) + "人次'],['咨询工作量（V4）','" + str(ADVICE) + "人次'],['累计接触','" + str(CUM_C) + "人次'],['累计咨询','" + str(CUM_A) + "人次']],",
    '5a deptDaily.psychology')
rep("service:{range:'本周 9月21—27日（导医台账 + 客服线上表）'",
    "service:{range:'本周 9月21—26日（导医台账 + 客服线上表；客服数据至 9.25）'",
    '5b deptDaily.service')
rep("marketing:{range:'本周 9月21—27日（患者对接表 + 营收日报 + 活动与绿色通道叙述）',metrics:[['管家本周对接','47条'],['本周转住院率','23.4%'],['本周转住院','11人'],",
    "marketing:{range:'本周 9月21—26日（患者对接表 + 营收日报 + 活动与绿色通道叙述）',metrics:[['管家本周对接','" + str(DEAL) + "条'],['本周转住院率','" + RATE + "%'],['本周转住院','" + str(ADMIT) + "人'],",
    '5c deptDaily.marketing')

# ═══════════════════════════════ 6. 部门弹层「本周」口径卡
rep("metrics:[['本周（9.21—9.27 · 数据截至 9.25）',null,null,'','管理表 V4「咨询师每日简报」本周患者接触 <b>25 人次</b>",
    "metrics:[['本周（9.21—9.26 · 数据截至 9.26）',null,null,'','管理表 V4「咨询师每日简报」本周患者接触 <b>" + str(CONTACT) + " 人次</b>",
    '6a 心理口径卡')
rep("metrics:[['本周（9.21—9.27 · 数据截至 9.25）',null,null,'','导医回访台账本周回访 <b>52 条</b>",
    "metrics:[['本周（9.21—9.26 · 数据截至 9.25）',null,null,'','导医回访台账本周回访 <b>52 条</b>",
    '6b 客服口径卡')
rep("metrics:[['本周（9.21—9.27 · 数据截至 9.25）',null,null,'','《患者有效对接表》逐条记录本周对接 <b>47 条</b>（朱婧 17 / 金林 16 / 利娟 14；",
    "metrics:[['本周（9.21—9.26 · 数据截至 9.26）',null,null,'','《患者有效对接表》逐条记录本周对接 <b>" + str(DEAL) + " 条</b>（" + PER_PSY + "；",
    '6c 营销口径卡')

# ═══════════════════════════════ 7. OPS_SNAPSHOT
rep("snapshotAt:'2026-09-25T17:20:00+08:00'", "snapshotAt:'2026-09-26T12:10:00+08:00'", '7 快照时间')

# ═══════════════════════════════ 写入
if fails:
    print('✗ 有 %d 处未按预期匹配，未写文件：' % len(fails))
    for f in fails:
        print('   -', f)
    sys.exit(1)

io.open(P, 'w', encoding='utf-8').write(s)
print('✓ 已写 %s（%d → %d B，%+d）' % (P, before, len(s), len(s) - before))
