---
name: "feishu-connection-monitor"
description: "周期检测 OpenClaw 与飞书双向通道，断连自动自愈并告警。"
---

# Feishu Connection Monitor

监控循环：

```bash
python3 main.py --mode monitor --config /Users/sk1/.openclaw/workspace/config/feishu-monitor.yaml
```

Gateway HTTP 服务（提供健康检查与自愈端点）：

```bash
python3 main.py --mode gateway-server --config /Users/sk1/.openclaw/workspace/config/feishu-monitor.yaml
```

部署 systemd（Linux）：

```bash
bash deploy_systemd.sh
```
