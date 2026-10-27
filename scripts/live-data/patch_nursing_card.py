#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""护理部门卡（DEPT_CARD）＋ 趋势轴标 + 静态资源版本号。

DEPT_CARD 在 index.html 里由 patch_page.py 生成（注释写着「勿手改」），
但护理考核数据不在 snapshot 里，本轮先在这里落静态值；
等 build_snapshot.py 补上 nursing.workFill / compTop 后再改回按快照注入。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HTML = os.path.join(ROOT, "index.html")
s = open(HTML, encoding="utf-8").read()
n = 0


def rep(old, new, label):
    global s, n
    c = s.count(old)
    assert c == 1, "命中 %d 次（应为 1）：%s" % (c, label)
    s = s.replace(old, new)
    n += 1


# ---------- 1) 部门卡 ----------
OLD = ('nursing:{m1:{label:"物理治疗人数",value:"—",unit:"本周未提交"},m2:{label:"6 项治疗完成率",value:"—",unit:"本周未提交"},\n'
       '        trend:null,axis:null,\n'
       '        note:"⚠⚠ <b>护理部本周（10.19–10.25）未提交</b>：周报与物理治疗逐日表最新只到 2026-10-17，本期没有任何一条护理事实入库，故「物理治疗人数 / 六项治疗完成率 / 工娱」三项<b>全部留空</b>，不拿上一期的数字与 93% 完成率顶替。汇报表护理组表头本周同样未滚动（与上一期逐项同值），已不引用。→ 需护理部补报 10.19—10.24 的物理治疗逐日表与六项治疗应做/实做。"}')
NEW = ('nursing:{m1:{label:"工作量填报",value:"57.1",unit:"%"},m2:{label:"综合首名",value:"67.7",unit:"分"},\n'
       '        trend:[10,8,10,9,10,8,9],axis:"dnurse7",\n'
       '        note:"<b>本周护理考核表已交（10.18—10.24，7 天 / 17 人）</b>：工作量填报 <b>64/112</b> 格（<b>57.1%</b>，人均 4.0 天）、'
       '质控填报 <b>72/119</b> 格（60.5%）、综合首名 <b>陈福建 67.7 分</b>（工作量指数 85.7 第 1、质控均分 49.6 第 4），'
       '末位丁思意 19.3，首末差 48.4 分；64 个有效分值标准差仅 8.2、最高 75。'
       '趋势线为逐日<b>填报人数</b>（10.18—10.24：10/8/10/9/10/8/9）。'
       '⚠ 源表按周日—周六出表，比自然周早 1 天，10.25 未交、不补。'
       '⚠ <b>质控 7 日数值与 10.11—10.17 存档逐格一致（72 格 / 差异 0）</b>，标「待核」，不作扣罚依据。'
       '⚠ <b>物理治疗按业主指示本期先不更新</b>：六项完成率与物理治疗人数留空，不拿上一期 93% 顶替。'
       '→ 点开本卡「护理考核标准」看 4 张表和 3 条核验红线。"}')
rep(OLD, NEW, "DEPT_CARD.nursing")

# ---------- 2) 轴标 ----------
rep('      dpsum:["首次","情绪","住院"],\n    };',
    ('      dpsum:["首次","情绪","住院"],\n'
     '      /* 2026-10-26 补：护理卡趋势线改为「逐日填报人数」（10.18—10.24，源表按周日—周六出表）。 */\n'
     '      dnurse7:["10.18","10.19","10.20","10.21","10.22","10.23","10.24"],\n    };'),
    "DEPT_AXIS.dnurse7")

# ---------- 3) 版本号 ----------
s2 = re.sub(r'\?v=2026102[0-9][a-z]', '?v=20261026c', s)
assert s2 != s
s = s2
n += 1

open(HTML, "w", encoding="utf-8").write(s)
print("护理部门卡补丁 %d 处完成，版本号统一为 20261026c" % n)
