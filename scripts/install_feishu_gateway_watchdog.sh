#!/bin/bash
set -euo pipefail

LABEL="ai.openclaw.feishu-watchdog"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"
SCRIPT_PATH="/Users/sk1/.openclaw/workspace/scripts/feishu_gateway_watchdog.py"
PYTHON_BIN="$(command -v python3)"
LOG_DIR="$HOME/.openclaw/watchdog-logs"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$LOG_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${SCRIPT_PATH}</string>
    <string>--quiet</string>
    <string>--log-dir</string>
    <string>${LOG_DIR}</string>
  </array>
  <key>StartInterval</key>
  <integer>600</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/launchd.out</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/launchd.err</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST

chmod 644 "$PLIST_PATH"
chmod +x "$SCRIPT_PATH"

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/${LABEL}"

echo "Installed ${LABEL}"
echo "plist: $PLIST_PATH"
echo "logs:  $LOG_DIR"
