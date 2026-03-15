import json
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from gateway_http_server import create_server


class GatewayServerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.yaml"
        self.signal_path = Path(self.temp_dir.name) / "feishu-receive.signal"
        self.log_dir = Path(self.temp_dir.name) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.port = self._free_port()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _free_port(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def _write_config(self, auth_token="", token_refresh_cmd="/usr/bin/true", channel_rebuild_cmd="/usr/bin/true"):
        yaml = f"""
monitor:
  heartbeat_seconds: 30
  timeout_seconds: 30
  failure_threshold: 3
  idempotent_window_seconds: 300
probes:
  send_probe_url: "http://127.0.0.1:{self.port}/send-health"
  receive_probe_url: "http://127.0.0.1:{self.port}/receive-health"
  receive_signal_file: "{self.signal_path}"
  auth_token: "{auth_token}"
recovery:
  token_refresh_url: "http://127.0.0.1:{self.port}/recover/token-refresh"
  channel_rebuild_url: "http://127.0.0.1:{self.port}/recover/rebuild-channel"
  receiver_restart_cmd: "/usr/bin/true"
  check_delay_seconds: 1
alert:
  webhook_url: "http://127.0.0.1:{self.port}/alert"
  cooldown_seconds: 120
logging:
  log_dir: "{self.log_dir}"
gateway:
  host: "127.0.0.1"
  port: {self.port}
  status_cmd: "/usr/bin/true"
  token_refresh_cmd: "{token_refresh_cmd}"
  channel_rebuild_cmd: "{channel_rebuild_cmd}"
  signal_ttl_seconds: 90
  alert_log_dir: "{self.log_dir}"
""".strip()
        self.config_path.write_text(yaml, encoding="utf-8")

    def _request(self, method, path, body=None, auth_token=""):
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if auth_token:
            req.add_header("Authorization", auth_token)
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")

    def test_endpoints_work(self):
        self._write_config()
        self.signal_path.write_text("ok", encoding="utf-8")
        server = create_server(str(self.config_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.05)
        try:
            status, body = self._request("GET", "/send-health")
            self.assertEqual(status, 200)
            self.assertIn("ok", body)
            status, body = self._request("GET", "/receive-health")
            self.assertEqual(status, 200)
            self.assertIn("ok", body)
            status, body = self._request("POST", "/recover/token-refresh", {"event": "recover"})
            self.assertEqual(status, 200)
            self.assertIn("ok", body)
            status, body = self._request("POST", "/recover/rebuild-channel", {"event": "recover"})
            self.assertEqual(status, 200)
            self.assertIn("ok", body)
            status, body = self._request("POST", "/alert", {"x": 1})
            self.assertEqual(status, 200)
            self.assertIn("ok", body)
            alert_files = list(self.log_dir.glob("feishu-alert-*.log"))
            self.assertTrue(alert_files)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def test_auth_token_enforced(self):
        self._write_config(auth_token="Bearer test-token")
        server = create_server(str(self.config_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.05)
        try:
            status, _ = self._request("GET", "/send-health")
            self.assertEqual(status, 401)
            status, _ = self._request("GET", "/send-health", auth_token="Bearer test-token")
            self.assertEqual(status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def test_recover_endpoint_failure(self):
        self._write_config(token_refresh_cmd="/usr/bin/false")
        server = create_server(str(self.config_path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.05)
        try:
            status, body = self._request("POST", "/recover/token-refresh", {"event": "recover"})
            self.assertEqual(status, 500)
            self.assertIn("failed", body)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
