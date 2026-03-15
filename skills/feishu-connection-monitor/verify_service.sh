#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="feishu-connection-monitor.service"
LOG_DIR="/Users/sk1/.openclaw/workspace/logs"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl 不可用，当前系统可能不支持 systemd"
  exit 1
fi

sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl is-active "${SERVICE_NAME}"
latest_log=$(ls -1t "${LOG_DIR}"/feishu-monitor-*.log 2>/dev/null | head -n 1 || true)
if [ -z "${latest_log}" ]; then
  echo "未发现监控日志"
  exit 2
fi
echo "服务重启后已检测到日志: ${latest_log}"
