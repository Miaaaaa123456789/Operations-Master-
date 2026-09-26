# -*- coding: utf-8 -*-
"""「更新数据」链路修复 · 第五批：医生部门卡随营收日报同步（出院 / 患者池 / 趋势线）"""
import io
import sys

R = '/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/'
ok, fails = [], []


def rep(fn, old, new, tag, cnt=1):
    p = R + fn
    s = io.open(p, encoding='utf-8').read()
    n = s.count(old)
    if n != cnt:
        fails.append('%-14s %-40s 匹配 %d（期望 %d）' % (fn, tag, n, cnt))
        return
    io.open(p, 'w', encoding='utf-8').write(s.replace(old, new))
    ok.append('%-14s %-40s %d' % (fn, tag, n))


NEW = (
    "    /* 医生部门卡：本周出院 / 患者池净变化 / 趋势线改由营收日报驱动。\n"
    "       此前这组是静态值，导入营收数据后不更新（业主 2026-09-27 要求全链路同步）。\n"
    "       「在院」取营收日报最近一个有填报的时点，避免最后一天缺该字段时被读成 0。 */\n"
    "    function syncDoctorCard(){\n"
    "      try{\n"
    "        var S=window.OPS_REVENUE&&window.OPS_REVENUE.summary(); if(!S) return;\n"
    "        var P=S.tw.p, d=(typeof DEPT_CARD!=='undefined')&&DEPT_CARD&&DEPT_CARD.doctor;\n"
    "        if(!d||!d.m1||!d.m2) return;\n"
    "        var daily=window.OPS_REVENUE.daily();\n"
    "        d.m1.value=String(P.disch);\n"
    "        var net=P.admit-P.disch;\n"
    "        d.m2.value=(net>=0?'+':'')+net;\n"
    "        var tr=[];\n"
    "        for(var i=21;i<=27;i++){ var k='2026-09-'+String(i).padStart(2,'0'); var v=daily[k]; tr.push(v&&v[6]!=null?v[6]:null); }\n"
    "        d.trend=tr;\n"
    "        var ds=S.twDays||[];\n"
    "        var span=ds.length?(ds[0].slice(5).replace('-','.')+'—'+ds[ds.length-1].slice(5).replace('-','.')):'本周';\n"
    "        var at=P.inhosAt?((+P.inhosAt.slice(5,7))+'月'+(+P.inhosAt.slice(8))+'日'):'';\n"
    "        d.note='本周（'+span+'）出院 '+P.disch+' 人、入院 '+P.admit+' 人，患者池净增 '+((net>=0?'+':'')+net)\n"
    "          +' 人（营收日报口径），趋势线为本周逐日出院；'\n"
    "          +(P.inhos!=null?('最近时点 '+at+' 在院 '+P.inhos+' 人'):'在院人数待补')\n"
    "          +'。科主任口径主表表头仍为上周值，两口径统计范围不同，不互相校验。';\n"
    "      }catch(e){}\n"
    "    }\n"
    "    function syncDoctorCardAndRender(){\n"
    "      syncDoctorCard();\n"
    "      try{ if(typeof renderDepts==='function') renderDepts(); }catch(e){}\n"
    "    }\n"
    "    window.addEventListener('ops:revenue-updated',syncDoctorCardAndRender);\n"
    "    setTimeout(syncDoctorCardAndRender,700);\n"
    "    window.syncDoctorCard=syncDoctorCardAndRender;\n"
    "    const DEPT_CARD={"
)

rep('index.html', "    const DEPT_CARD={", NEW, '医生部门卡同步')

print('=== 第五批完成 %d 项 ===' % len(ok))
for l in ok:
    print('  ✓', l)
if fails:
    print('=== 未匹配 ===')
    for l in fails:
        print('  ✗', l)
    sys.exit(1)
