import argparse
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from monitor import SimpleYamlParser


@dataclass
class GatewayServerConfig:
    host: str
    port: int
    auth_token: str
    receive_signal_file: str
    signal_ttl_seconds: int
    status_cmd: str
    token_refresh_cmd: str
    channel_rebuild_cmd: str
    alert_log_dir: str


class GatewayConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._last_mtime: Optional[float] = None
        self._config: Optional[GatewayServerConfig] = None

    def load_if_changed(self) -> GatewayServerConfig:
        mtime = Path(self.config_path).stat().st_mtime
        if self._config is None or self._last_mtime != mtime:
            self._config = self._load()
            self._last_mtime = mtime
        return self._config

    def _load(self) -> GatewayServerConfig:
        raw = SimpleYamlParser.parse(Path(self.config_path).read_text(encoding="utf-8"))
        probes = raw.get("probes", {})
        gateway = raw.get("gateway", {})
        recovery = raw.get("recovery", {})
        logging = raw.get("logging", {})
        send_probe_url = str(probes.get("send_probe_url", "http://127.0.0.1:18790/send-health"))
        parsed = urlparse(send_probe_url)
        host = str(gateway.get("host", parsed.hostname or "127.0.0.1"))
        port = int(gateway.get("port", parsed.port or 18790))
        return GatewayServerConfig(
            host=host,
            port=port,
            auth_token=str(probes.get("auth_token", "")),
            receive_signal_file=str(probes.get("receive_signal_file", "")),
            signal_ttl_seconds=int(gateway.get("signal_ttl_seconds", 90)),
            status_cmd=str(gateway.get("status_cmd", "openclaw gateway status")),
            token_refresh_cmd=str(gateway.get("token_refresh_cmd", recovery.get("receiver_restart_cmd", "/usr/bin/true"))),
            channel_rebuild_cmd=str(gateway.get("channel_rebuild_cmd", recovery.get("receiver_restart_cmd", "/usr/bin/true"))),
            alert_log_dir=str(gateway.get("alert_log_dir", logging.get("log_dir", "/tmp"))),
        )


class GatewayHandler(BaseHTTPRequestHandler):
    manager: GatewayConfigManager

    def do_GET(self) -> None:
        cfg = self.manager.load_if_changed()
        if not self._authorized(cfg):
            self._reply(401, "unauthorized")
            return
        if self.path == "/send-health":
            ok, detail = self._status_ok(cfg)
            self._reply(200 if ok else 503, "ok" if ok else f"down:{detail}")
            return
        if self.path == "/receive-health":
            if self._receive_signal_fresh(cfg):
                self._reply(200, "ok")
                return
            ok, detail = self._status_ok(cfg)
            self._reply(200 if ok else 503, "ok" if ok else f"down:{detail}")
            return
        self._reply(404, "not found")

    def do_POST(self) -> None:
        cfg = self.manager.load_if_changed()
        if not self._authorized(cfg):
            self._reply(401, "unauthorized")
            return
        if self.path == "/recover/token-refresh":
            ok, detail = self._run_cmd(cfg.token_refresh_cmd)
            self._reply(200 if ok else 500, "ok" if ok else f"failed:{detail}")
            return
        if self.path == "/recover/rebuild-channel":
            ok, detail = self._run_cmd(cfg.channel_rebuild_cmd)
            self._reply(200 if ok else 500, "ok" if ok else f"failed:{detail}")
            return
        if self.path == "/alert":
            body = self._read_body()
            self._write_alert_log(cfg, body)
            self._reply(200, "ok")
            return
        self._reply(404, "not found")

    def _authorized(self, cfg: GatewayServerConfig) -> bool:
        if not cfg.auth_token:
            return True
        return self.headers.get("Authorization", "") == cfg.auth_token

    def _receive_signal_fresh(self, cfg: GatewayServerConfig) -> bool:
        signal = Path(cfg.receive_signal_file)
        if not signal.exists():
            return False
        age = time.time() - signal.stat().st_mtime
        return age <= cfg.signal_ttl_seconds

    def _status_ok(self, cfg: GatewayServerConfig) -> tuple[bool, str]:
        ok, out = self._run_cmd(cfg.status_cmd)
        if not ok:
            return False, out
        text = out.lower()
        if not text.strip():
            return True, ""
        runtime_ok = "runtime: running" in text
        rpc_ok = "rpc probe: ok" in text or "probe: ok" in text
        if runtime_ok and rpc_ok:
            return True, ""
        return False, out

    def _run_cmd(self, cmd: str) -> tuple[bool, str]:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return proc.returncode == 0, output[:500]

    def _write_alert_log(self, cfg: GatewayServerConfig, body: Dict[str, Any]) -> None:
        log_dir = Path(cfg.alert_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file = log_dir / f"feishu-alert-{datetime.now().strftime('%Y-%m-%d')}.log"
        payload = {
            "timestamp": datetime.now().isoformat(),
            "body": body,
        }
        with file.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}

    def _reply(self, code: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def create_server(config_path: str) -> ThreadingHTTPServer:
    manager = GatewayConfigManager(config_path)
    cfg = manager.load_if_changed()
    GatewayHandler.manager = manager
    return ThreadingHTTPServer((cfg.host, cfg.port), GatewayHandler)


def run_server(config_path: str) -> None:
    server = create_server(config_path)
    print(f"gateway server listening on {server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    run_server(args.config)
