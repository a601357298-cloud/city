#!/usr/bin/env bash
set -euo pipefail

SKILL_ROOT="/Users/sk1/.openclaw/.openclaw/skills/feishu-connection-monitor"
CONFIG_PATH="/Users/sk1/.openclaw/workspace/config/feishu-monitor.yaml"
SERVICE_NAME="feishu-connection-monitor.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl 不可用，当前系统可能不支持 systemd"
  exit 1
fi

sudo mkdir -p /etc/systemd/system
sudo bash -c "cat > ${SERVICE_PATH}" <<EOF
[Unit]
Description=Feishu Connection Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${SKILL_ROOT}
ExecStart=/usr/bin/env python3 ${SKILL_ROOT}/main.py --config ${CONFIG_PATH}
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl status "${SERVICE_NAME}" --no-pager
echo "部署完成: ${SERVICE_NAME}"
