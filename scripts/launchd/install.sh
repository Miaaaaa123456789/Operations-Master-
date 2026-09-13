#!/bin/sh
# 启用 / 停止每日 09:00 抓金山表的 launchd 任务
# 用法：sh scripts/launchd/install.sh [enable|disable|status]
set -eu

LABEL="com.workbuddy.ops.kdocs-ingest"
SRC="$HOME/Library/LaunchAgents/$LABEL.plist"
HERE="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HERE/$LABEL.plist"

case "${1:-enable}" in
  enable)
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$PLIST" "$SRC"
    launchctl unload "$SRC" 2>/dev/null || true
    launchctl load "$SRC"
    echo "✓ 已启用：$LABEL（每天 09:00 运行）"
    echo "  任务文件：$SRC"
    echo "  日志：/Users/opp/WorkBuddy/2026-09-13-10-26-58/logs/kdocs-ingest.log"
    echo "  立即试跑：launchctl start $LABEL"
    ;;
  disable)
    if [ -f "$SRC" ]; then
      launchctl unload "$SRC" 2>/dev/null || true
      rm "$SRC"
      echo "✓ 已停用：$LABEL"
    else
      echo "（未启用，无需停用）"
    fi
    ;;
  status)
    if launchctl list | grep -q "$LABEL"; then
      echo "✓ 启用中"
      launchctl list | grep "$LABEL"
    else
      echo "✗ 未启用"
    fi
    ;;
  *)
    echo "用法：$0 [enable|disable|status]"
    exit 2
    ;;
esac