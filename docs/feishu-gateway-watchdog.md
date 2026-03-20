# Feishu Gateway Watchdog

目的：用本地脚本替代聊天内人工巡检，定时检查 OpenClaw gateway 健康状态；发现异常时直接执行 `openclaw gateway restart`。

## 当前策略

- 巡检频率：每 10 分钟
- 检测方式：执行 `openclaw gateway status`
- 健康判定：输出中同时包含
  - `Runtime: running`
  - `RPC probe: ok`（或 `probe: ok`）
  - `Listening:`
- 失败动作：直接执行 `openclaw gateway restart`
- 日志位置：`~/.openclaw/watchdog-logs/`

## 安装

```bash
bash /Users/sk1/.openclaw/workspace/scripts/install_feishu_gateway_watchdog.sh
```

## 手动测试

```bash
python3 /Users/sk1/.openclaw/workspace/scripts/feishu_gateway_watchdog.py
```

## 查看状态

```bash
launchctl print gui/$(id -u)/ai.openclaw.feishu-watchdog
```

## 查看日志

```bash
tail -n 50 ~/.openclaw/watchdog-logs/launchd.err
tail -n 50 ~/.openclaw/watchdog-logs/launchd.out
tail -n 50 ~/.openclaw/watchdog-logs/feishu-gateway-watchdog-$(date +%F).jsonl
```

## 卸载

```bash
launchctl bootout gui/$(id -u)/ai.openclaw.feishu-watchdog || true
rm -f ~/Library/LaunchAgents/ai.openclaw.feishu-watchdog.plist
```

## 边界说明

这个版本是“低 token、低复杂度”的本地看门狗，主要保证 gateway 进程和本地 RPC 探针是健康的。

它**还不是**严格意义上的“飞书端到端收发探测”。
如果后面需要更强版本，可以再升级成：
- 检测 Feishu 通道最近入站/出站活动是否异常停滞
- 独立 HTTP 健康探针
- 多级自愈（先轻量修复，再 restart）
- 连续失败才告警
