#!/bin/zsh
# ============================================================================
# 线上表格 → 本地事实库 → 发布快照 → 线上看板  的一键管线
#
#   sh scripts/live-data/run.sh            # 只采集+重算（不发布）
#   sh scripts/live-data/run.sh --deploy   # 采集+重算+推线上
#
# 退出码：0 成功（含"无变化"）；1 采集失败；2 重算失败；3 发布失败
# ============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1

PY="${PY_BIN:-/Users/opp/.workbuddy/binaries/python/versions/3.13.12/bin/python3}"
[ -x "$PY" ] || PY=python3
# ⛔ 别写 .pyc：本机安全策略把 __pycache__ 的原子写（临时文件 rename → delete）
#    判为高风险删除动作，会直接把命令打断。禁掉字节码写入最省事。
export PYTHONDONTWRITEBYTECODE=1
LOG="$ROOT/logs/live-data.log"
mkdir -p "$ROOT/logs"

MODE="${1:-local}"
# ⛔ 时间戳要每行现算：原先 STAMP 只在启动时取一次，整轮日志都盖同一个时刻，
#    看起来像"采集与发布同时完成"，排障时会误判先后顺序。
say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

say "── 开始：采集 6 份在线表 ──"
"$PY" scripts/live-data/collect.py >>"$LOG" 2>&1 || { say "❌ 采集失败，保留上一版数据"; exit 1; }

say "── 入库（原始层 + 规范化事实）──"
"$PY" scripts/live-data/ingest.py >>"$LOG" 2>&1 || { say "❌ 入库失败"; exit 2; }

say "── 营收逐日台账（经核验的日事实）──"
"$PY" scripts/live-data/seed_import.py >>"$LOG" 2>&1 || { say "❌ 营收台账导入失败"; exit 2; }

say "── 重算发布快照 ──"
OUT=$("$PY" scripts/live-data/build_snapshot.py 2>&1) || { echo "$OUT" >>"$LOG"; say "❌ 快照重算失败"; exit 2; }
echo "$OUT" >>"$LOG"
say "$(echo "$OUT" | tr '\n' ' | ')"

if [ "$MODE" = "--deploy" ]; then
  say "── 推线上 ──"
  if sh scripts/deploy-online.sh >>"$LOG" 2>&1; then
    say "✅ 已发布到 https://hospital-ops-collab-77609.app.workbuddy.host/"
  else
    say "⚠️ 发布失败（见日志尾部），本地数据已更新，可稍后重试：sh scripts/deploy-online.sh"
    exit 3
  fi
else
  say "（未加 --deploy，仅更新本地数据）"
fi

say "── 完成 ──"
