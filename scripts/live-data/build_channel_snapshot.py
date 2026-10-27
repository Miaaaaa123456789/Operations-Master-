#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从今天的《10月到院登记表》原始抓取重生成 channel-snapshot.js（渠道看板快照）

背景（2026-10-26）：
  渠道看板里的 CHANNEL_SNAPSHOT 还是 **2026-10-12 抓的 10.1–10.11、489 条**，
  首屏却把它的总数标成「本期渠道到院 489 人次」——窗口对不上（本期是 10.19–10.25）。
  这里用 data/raw-kdocs/arrival_register/3-工作表1.json（2026-10-26T09:14:22 抓）
  重生成，覆盖 10.1–10.25 全量。

口径：
  · 行结构与源表一致：[序号, 就诊日期, 姓名, 年龄, 联系方式, 初/复诊, 来源渠道, 随访人, 备注]
  · 联系方式**中间 4 位打码**（页面本来就「默认遮蔽」，而指纹去重只用 日期+姓名+渠道+初复诊，
    不打码会把 900+ 位患者手机号明文写进公网 JS 源码）
  · 不删行、不改渠道、不合并：去重交给 channel-dashboard.js 的指纹逻辑
"""
import glob
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "data", "raw-kdocs", "arrival_register")
OUT = os.path.join(ROOT, "channel-snapshot.js")


def mask_phone(p):
    s = str(p or "").strip()
    if not re.fullmatch(r"\d{11}", s):
        return s
    return s[:3] + "****" + s[-4:]


def norm_dot(d):
    """2026.10.5 / 2026-10-05 / 2026/10/5 → 2026.10.5（保持源表写法）"""
    s = str(d or "").strip()
    m = re.match(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if not m:
        return ""
    return f"{m.group(1)}.{int(m.group(2))}.{int(m.group(3))}"


def key(d):
    y, m, dd = d.split(".")
    return f"{y}-{int(m):02d}-{int(dd):02d}"


def main():
    f = sorted(glob.glob(os.path.join(RAW, "*.json")))[0]
    d = json.load(open(f, encoding="utf-8"))
    rows = d["rows"]
    pulled = d.get("pulledAt", "")

    out, skipped = [], 0
    for r in rows[2:]:
        date = norm_dot(r[1])
        if not date:
            skipped += 1
            continue
        cells = [str(x if x is not None else "").strip() for x in r[:9]]
        while len(cells) < 9:
            cells.append("")
        cells[1] = date
        cells[4] = mask_phone(cells[4])
        out.append(cells)

    days = sorted({key(r[1]) for r in out})
    span = f"{days[0]} — {days[-1]}"
    n = len(out)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    head = f"""/* ============================================================================
   渠道看板 · 线上到院登记表快照（真实数据，非演示）
   ----------------------------------------------------------------------------
   来源：《10月到院登记表》https://www.kdocs.cn/l/cp4lRRCVcqVa
   抓取：{now}（kdocs 接口 · 本轮与客服四张表同批抓取）
   源表：pulledAt {pulled} · 工作表「工作表1」
   规模：{n} 条（就诊日期 {span}）
   ⚠ 这是**抓取快照**，不是「已连接」。看板内的「在线表同步」按钮会尝试实时拉取，
     浏览器跨域/未授权时会如实显示「待连接」并给出原因，**不会假装同步成功**。
   字段顺序：[序号, 就诊日期, 姓名, 年龄, 联系方式, 初/复诊, 来源渠道, 随访人, 备注]
   ⭐ 2026-10-26 重生成：上一版是 2026-10-12 抓的 10.1–10.11、489 条，
     首屏却把它的总数标成「本期渠道到院」——窗口对不上。本版补齐 10.12–10.25。
   🔒 联系方式**中间 4 位已打码**（页面本来就默认遮蔽；指纹去重只用
     日期+姓名+渠道+初复诊，与手机号无关），避免把患者手机号明文写进公网 JS 源码。
   ⚠ 快照是**权威源**：重抓时「仅来自线上表」且不在新快照里的记录会被**移出到院库**
     并记日志，避免源表删行后本地残留幽灵记录（见 channel-dashboard.js seedFromSnapshot）。
      手工粘贴等其它来源的记录不受影响；被删行会出现在「操作记录」里可追溯。
   ========================================================================== */
window.CHANNEL_SNAPSHOT = {{
  sourceName: '梓笙园 · 到院登记表',
  sourceUrl: 'https://www.kdocs.cn/l/cp4lRRCVcqVa',
  fileId: 'cp4lRRCVcqVa',
  sheetId: 3,
  fetchedAt: '{pulled}',
  sourceMtime: '{now}',
  fetchedBy: '服务端 kdocs 接口（随客服四张表同批抓取）',
  isDemo: false,
  rows: [
"""

    lines = []
    for i in range(0, len(out), 4):
        chunk = out[i:i + 4]
        lines.append("    " + ", ".join(json.dumps(c, ensure_ascii=False) for c in chunk))
    body = ",\n".join(lines)
    tail = "\n  ]\n};\n"

    open(OUT, "w", encoding="utf-8").write(head + body + tail)
    print(f"✓ {OUT}")
    print(f"  行数 {n}（跳过无日期 {skipped} 行）· 日期 {span}")
    print(f"  手机号打码 {sum(1 for r in out if '****' in r[4])} 条")


if __name__ == "__main__":
    sys.exit(main())
