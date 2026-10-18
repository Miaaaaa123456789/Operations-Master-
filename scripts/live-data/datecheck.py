#!/usr/bin/env python3
"""扫描各表日期列分布，确认数据截至日与本周覆盖。"""
import json, os, re, collections

RAW = "data/raw-kdocs"


def load(p):
    return json.load(open(os.path.join(RAW, p)))["rows"]


def norm_date(s):
    s = (s or "").strip()
    m = re.match(r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})$", s)
    if m:
        return f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None


def scan(path, col, label):
    rows = load(path)
    c = collections.Counter()
    for r in rows[2:]:
        d = norm_date(r[col]) if col < len(r) else None
        if d:
            c[d] += 1
    if not c:
        print(f"{label}: 无日期")
        return
    ks = sorted(c)
    print(f"{label}: {ks[0]} → {ks[-1]}  共{sum(c.values())}条 日数{len(ks)}")
    tail = [(k, c[k]) for k in ks[-8:]]
    print("   末8日:", ", ".join(f"{k}:{v}" for k, v in tail))


scan("arrival_register/3-工作表1.json", 1, "到院登记")
scan("psych_v4/11-咨询师每日简报.json", 0, "心理每日简报")
scan("psych_visits/5-团体治疗登记.json", 1, "团体治疗")
scan("psych_v4/5-团队查房日报.json", 0, "团队查房")
scan("service_followups/2-标准化回访台账.json", 1, "回访台账")
scan("service_followups/4-导诊主动服务记录表.json", 1, "导诊记录")
