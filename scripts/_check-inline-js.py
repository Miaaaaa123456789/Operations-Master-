#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抽取 index.html 中全部内联 <script> 块，写出 /tmp/ops-script-N.js 并逐个 node --check"""
import io, os, re, subprocess, sys

P = "/Users/opp/WorkBuddy/2026-09-13-10-26-58/repo/index.html"
html = io.open(P, encoding="utf-8").read()
blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
NODE = "/Users/opp/.workbuddy/binaries/node/versions/22.22.2-3/bin/node"
print("内联脚本块：%d 个" % len(blocks))
bad = 0
for i, b in enumerate(blocks, 1):
    if not b.strip():
        continue
    p = "/tmp/ops-script-%d.js" % i
    io.open(p, "w", encoding="utf-8").write(b)
    r = subprocess.run([NODE, "--check", p], capture_output=True, text=True)
    tag = "OK " if r.returncode == 0 else "FAIL"
    print("  %s 块 %2d  长度 %6d  %s" % (tag, i, len(b), (r.stderr.strip().split("\n")[0][:120] if r.returncode else "")))
    if r.returncode:
        bad += 1
        print(r.stderr[:800])
print("失败：%d" % bad)
sys.exit(1 if bad else 0)
