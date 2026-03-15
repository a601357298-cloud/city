import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class MonitorConfig:
    heartbeat_seconds: int
    timeout_seconds: int
    failure_threshold: int
    idempotent_window_seconds: int
    send_probe_url: str
    receive_probe_url: str
    receive_signal_file: str
    token_refresh_url: str
    channel_rebuild_url: str
    receiver_restart_cmd: str
    alert_webhook_url: str
    alert_cooldown_seconds: int
    log_dir: str
    recovery_check_delay_seconds: int
    headers: Dict[str, str]


class SimpleYamlParser:
    @staticmethod
    def parse(text: str) -> Dict[str, Any]:
        root: Dict[str, Any] = {}
        stack: List[Tuple[int, Dict[str, Any]]] = [(-1, root)]
        for raw_line in text.splitlines():
            if not raw_line.strip():
                continue
            line = raw_line.rstrip()
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            indent = len(line) - len(stripped)
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            while stack and indent <= stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            if value == "":
                node: Dict[str, Any] = {}
                parent[key] = node
                stack.append((indent, node))
            else:
                parent[key] = SimpleYamlParser._to_scalar(value)
        return root

    @staticmethod
    def _to_scalar(value: str) -> Any:
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if value.lower() in {"null", "none"}:
            return None
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return value


class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._last_mtime: Optional[float] = None
        self._config: Optional[MonitorConfig] = None

    def load_if_changed(self) -> MonitorConfig:
        mtime = os.path.getmtime(self.config_path)
        if self._config is None or self._last_mtime != mtime:
            self._config = self._load()
            self._last_mtime = mtime
        return self._config

    def _load(self) -> MonitorConfig:
        content = Path(self.config_path).read_text(encoding="utf-8")
        raw = SimpleYamlParser.parse(content)
        cfg = MonitorConfig(
            heartbeat_seconds=int(raw["monitor"]["heartbeat_seconds"]),
            timeout_seconds=int(raw["monitor"]["timeout_seconds"]),
            failure_threshold=int(raw["monitor"]["failure_threshold"]),
            idempotent_window_seconds=int(raw["monitor"]["idempotent_window_seconds"]),
            send_probe_url=str(raw["probes"]["send_probe_url"]),
            receive_probe_url=str(raw["probes"]["receive_probe_url"]),
            receive_signal_file=str(raw["probes"]["receive_signal_file"]),
            token_refresh_url=str(raw["recovery"]["token_refresh_url"]),
            channel_rebuild_url=str(raw["recovery"]["channel_rebuild_url"]),
            receiver_restart_cmd=str(raw["recovery"]["receiver_restart_cmd"]),
            alert_webhook_url=str(raw["alert"]["webhook_url"]),
            alert_cooldown_seconds=int(raw["alert"]["cooldown_seconds"]),
            log_dir=str(raw["logging"]["log_dir"]),
            recovery_check_delay_seconds=int(raw["recovery"]["check_delay_seconds"]),
            headers={
                "Content-Type": "application/json",
                "Authorization": str(raw["probes"].get("auth_token", "")),
            },
        )
        validate_config(cfg)
        return cfg


def validate_config(config: MonitorConfig) -> None:
    required_values = [
        config.send_probe_url,
        config.receive_probe_url,
        config.receive_signal_file,
        config.token_refresh_url,
        config.channel_rebuild_url,
        config.receiver_restart_cmd,
        config.alert_webhook_url,
        config.log_dir,
    ]
    if any(v is None or str(v).strip() == "" for v in required_values):
        raise ValueError("配置关键字段缺失")
    if config.heartbeat_seconds > 60:
        raise ValueError("heartbeat_seconds 必须不大于 60")
    if config.timeout_seconds > 30:
        raise ValueError("timeout_seconds 必须不大于 30")
    if config.failure_threshold < 1:
        raise ValueError("failure_threshold 必须大于 0")


class JsonlLogger:
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, status: str, latency_ms: int, error: str, recovery_action: str) -> None:
        now = datetime.now()
        file_path = self.log_dir / f"feishu-monitor-{now.strftime('%Y-%m-%d')}.log"
        payload = {
            "timestamp": now.isoformat(),
            "status": status,
            "latency_ms": latency_ms,
            "error": error,
            "recovery_action": recovery_action,
        }
        with file_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")


class HttpClient:
    def post_json(self, url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: int) -> Tuple[int, str]:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url=url, data=data, method="POST")
        for key, value in headers.items():
            if value:
                request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.status, body
        except urllib.error.HTTPError as err:
            try:
                body = err.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(err)
            return err.code, body

    def get(self, url: str, headers: Dict[str, str], timeout: int) -> Tuple[int, str]:
        request = urllib.request.Request(url=url, method="GET")
        for key, value in headers.items():
            if value:
                request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.status, body
        except urllib.error.HTTPError as err:
            try:
                body = err.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(err)
            return err.code, body


class AlertManager:
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client
        self._last_alert_at: Optional[float] = None

    def send_card(self, config: MonitorConfig, status: str, error: str, action: str) -> bool:
        now = time.time()
        if self._last_alert_at is not None:
            if now - self._last_alert_at < config.alert_cooldown_seconds:
                return False
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": f"Feishu Monitor {status}"}},
                "elements": [
                    {"tag": "markdown", "content": f"错误: {error or 'none'}"},
                    {"tag": "markdown", "content": f"动作: {action or 'none'}"},
                ],
            },
        }
        code, _ = self.http_client.post_json(
            config.alert_webhook_url,
            payload,
            {"Content-Type": "application/json"},
            timeout=config.timeout_seconds,
        )
        if code == 200:
            self._last_alert_at = now
            return True
        return False


class ConnectionMonitor:
    def __init__(
        self,
        config_manager: ConfigManager,
        logger: JsonlLogger,
        http_client: Optional[HttpClient] = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[int], None] = time.sleep,
    ):
        self.config_manager = config_manager
        self.logger = logger
        self.http_client = http_client or HttpClient()
        self.alert_manager = AlertManager(self.http_client)
        self.clock = clock
        self.sleeper = sleeper
        self.status = "up"
        self.consecutive_failures = 0
        self.last_recovery_at: Optional[float] = None

    def run_forever(self) -> None:
        while True:
            config = self.config_manager.load_if_changed()
            self.run_once(config)
            self.sleeper(config.heartbeat_seconds)

    def run_once(self, config: Optional[MonitorConfig] = None) -> Dict[str, Any]:
        cfg = config or self.config_manager.load_if_changed()
        start = self.clock()
        send_ok, send_error = self._probe_send(cfg)
        recv_ok, recv_error = self._probe_receive(cfg)
        elapsed_ms = int((self.clock() - start) * 1000)
        if send_ok and recv_ok:
            self.status = "up"
            self.consecutive_failures = 0
            result = {
                "status": "up",
                "latency_ms": elapsed_ms,
                "error": "",
                "recovery_action": "",
            }
            self.logger.write(**result)
            return result
        self.consecutive_failures += 1
        error = "; ".join(v for v in [send_error, recv_error] if v)
        recovery_action = ""
        if self.consecutive_failures >= cfg.failure_threshold:
            self.status = "down"
            recovery_action = self._recover(cfg, error)
        result = {
            "status": self.status,
            "latency_ms": elapsed_ms,
            "error": error,
            "recovery_action": recovery_action,
        }
        self.logger.write(**result)
        return result

    def _probe_send(self, cfg: MonitorConfig) -> Tuple[bool, str]:
        code, body = self.http_client.get(cfg.send_probe_url, cfg.headers, cfg.timeout_seconds)
        if code == 200 and "ok" in body.lower():
            return True, ""
        return False, f"send_probe_failed:{code}:{body[:120]}"

    def _probe_receive(self, cfg: MonitorConfig) -> Tuple[bool, str]:
        signal_file = Path(cfg.receive_signal_file)
        if signal_file.exists():
            age = self.clock() - signal_file.stat().st_mtime
            if age <= cfg.heartbeat_seconds + cfg.timeout_seconds:
                return True, ""
        code, body = self.http_client.get(cfg.receive_probe_url, cfg.headers, cfg.timeout_seconds)
        if code == 200 and "ok" in body.lower():
            return True, ""
        return False, f"receive_probe_failed:{code}:{body[:120]}"

    def _recover(self, cfg: MonitorConfig, error: str) -> str:
        now = self.clock()
        if self.last_recovery_at is not None:
            if now - self.last_recovery_at < cfg.idempotent_window_seconds:
                return "suppress_recovery_in_window"
        self.last_recovery_at = now
        actions: List[str] = []
        if self._run_http_step(cfg.token_refresh_url, cfg):
            actions.append("refresh_token")
            if self._recovery_success(cfg):
                self.status = "up"
                self.consecutive_failures = 0
                self.alert_manager.send_card(cfg, "recovering", error, ",".join(actions))
                return ",".join(actions)
        else:
            actions.append("refresh_token_failed")
        if self._run_http_step(cfg.channel_rebuild_url, cfg):
            actions.append("rebuild_channel")
            if self._recovery_success(cfg):
                self.status = "up"
                self.consecutive_failures = 0
                self.alert_manager.send_card(cfg, "recovering", error, ",".join(actions))
                return ",".join(actions)
        else:
            actions.append("rebuild_channel_failed")
        if self._restart_receiver(cfg.receiver_restart_cmd):
            actions.append("restart_receiver")
            if self._recovery_success(cfg):
                self.status = "up"
                self.consecutive_failures = 0
                self.alert_manager.send_card(cfg, "recovering", error, ",".join(actions))
                return ",".join(actions)
        else:
            actions.append("restart_receiver_failed")
        actions.append("escalate_alert")
        self.status = "recovering"
        self.alert_manager.send_card(cfg, "down", error, ",".join(actions))
        return ",".join(actions)

    def _run_http_step(self, url: str, cfg: MonitorConfig) -> bool:
        code, body = self.http_client.post_json(url, {"event": "recover"}, cfg.headers, cfg.timeout_seconds)
        return code == 200 and "ok" in body.lower()

    def _restart_receiver(self, cmd: str) -> bool:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return proc.returncode == 0

    def _recovery_success(self, cfg: MonitorConfig) -> bool:
        self.sleeper(cfg.recovery_check_delay_seconds)
        send_ok, _ = self._probe_send(cfg)
        recv_ok, _ = self._probe_receive(cfg)
        return send_ok and recv_ok
