#!/bin/sh
# 医院经营协同看板 · 每日数据抓取（统一入口）
#
# 依次运行两个抓取脚本：
#   1. kdocs-ingest.js   主表 + 护士工作量表（8 项指纹 + 护士指纹）
#   2. extra-ingest.py   心理科来访数量 + 客服与导诊部（落盘 data/extra/）
#
# 用法：
#   sh scripts/daily-ingest.sh              # 正常抓取
#   sh scripts/daily-ingest.sh --dry-run    # 只算指纹不写快照（传给 kdocs-ingest）
#
# 退出码：0 = 全部成功；非 0 = 有脚本失败（日志里能看到是哪一步）
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

export PATH="$HOME/.local/bin:$PATH"

NODE="${NODE_BIN:-/Users/opp/.workbuddy/binaries/node/versions/24.14.0/bin/node}"
PY="${PY_BIN:-/Users/opp/.workbuddy/binaries/python/envs/default/bin/python}"

# 运行环境兜底：managed 版本不在时退回 PATH 上的同名命令
[ -x "$NODE" ] || NODE="node"
[ -x "$PY" ] || PY="python3"

echo "═══ $(date '+%Y-%m-%d %H:%M:%S') 开始抓取 ═══"
rc=0

echo ""
echo "─── [1/2] 主表 + 护士工作量表（kdocs-ingest.js）───"
if "$NODE" scripts/kdocs-ingest.js "$@"; then
  echo "✓ kdocs-ingest 完成"
else
  echo "✗ kdocs-ingest 失败（退出码 $?）"
  rc=1
fi

echo ""
echo "─── [2/2] 心理科来访数量 + 客服与导诊部（extra-ingest.py）───"
if "$PY" scripts/extra-ingest.py; then
  echo "✓ extra-ingest 完成"
else
  echo "✗ extra-ingest 失败（退出码 $?）"
  rc=1
fi

echo ""
if [ "$rc" -eq 0 ]; then
  echo "═══ 全部完成 ═══"
else
  echo "═══ 有脚本失败，请检查上方日志；看板数据不要基于残缺结果更新 ═══"
fi
exit "$rc"
