import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from monitor import AlertManager, ConfigManager, ConnectionMonitor, HttpClient, JsonlLogger, MonitorConfig, SimpleYamlParser, validate_config


class DummyConfigManager:
    def __init__(self, cfg: MonitorConfig):
        self.cfg = cfg

    def load_if_changed(self) -> MonitorConfig:
        return self.cfg


class StatefulHandler(BaseHTTPRequestHandler):
    routes = {}
    post_routes = {}

    def do_GET(self):
        code, body = self.routes.get(self.path, (404, "not found"))
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self):
        code, body = self.post_routes.get(self.path, (404, "not found"))
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        return


class FakeHttpClient:
    def __init__(self):
        self.state = {
            "send_ok": False,
            "receive_ok": False,
            "send_code": 500,
            "token_ok": True,
            "rebuild_ok": True,
            "alert_ok": True,
        }
        self.calls = []

    def get(self, url, headers, timeout):
        self.calls.append(("get", url))
        if "send-health" in url:
            if self.state["send_ok"]:
                return 200, "ok"
            return self.state["send_code"], "send down"
        if "receive-health" in url:
            return (200, "ok") if self.state["receive_ok"] else (500, "receive down")
        return (404, "missing")

    def post_json(self, url, payload, headers, timeout):
        self.calls.append(("post", url))
        if "token-refresh" in url:
            if self.state["token_ok"]:
                self.state["send_ok"] = True
                self.state["receive_ok"] = True
                return 200, "ok"
            return 401, "unauthorized"
        if "rebuild-channel" in url:
            return (200, "ok") if self.state["rebuild_ok"] else (500, "error")
        if "alert" in url:
            return (200, "ok") if self.state["alert_ok"] else (500, "error")
        return 404, "missing"


class MonitorUnitTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_dir = os.path.join(self.temp_dir.name, "logs")
        self.signal_file = os.path.join(self.temp_dir.name, "signal.txt")
        self.base_cfg = MonitorConfig(
            heartbeat_seconds=30,
            timeout_seconds=30,
            failure_threshold=1,
            idempotent_window_seconds=300,
            send_probe_url="http://127.0.0.1:19080/send-health",
            receive_probe_url="http://127.0.0.1:19080/receive-health",
            receive_signal_file=self.signal_file,
            token_refresh_url="http://127.0.0.1:19080/recover/token-refresh",
            channel_rebuild_url="http://127.0.0.1:19080/recover/rebuild-channel",
            receiver_restart_cmd="/bin/true",
            alert_webhook_url="http://127.0.0.1:19080/alert",
            alert_cooldown_seconds=60,
            log_dir=self.log_dir,
            recovery_check_delay_seconds=0,
            headers={"Content-Type": "application/json", "Authorization": ""},
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _start_server(self, routes, post_routes):
        StatefulHandler.routes = routes
        StatefulHandler.post_routes = post_routes
        server = HTTPServer(("127.0.0.1", 19080), StatefulHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server

    def test_send_probe_200_branch(self):
        server = self._start_server(
            {"/send-health": (200, "ok"), "/receive-health": (200, "ok")},
            {"/alert": (200, "ok")},
        )
        try:
            Path(self.signal_file).write_text("ok", encoding="utf-8")
            monitor = ConnectionMonitor(DummyConfigManager(self.base_cfg), JsonlLogger(self.log_dir), HttpClient(), sleeper=lambda _: None)
            result = monitor.run_once(self.base_cfg)
            self.assertEqual(result["status"], "up")
        finally:
            server.shutdown()
            server.server_close()

    def test_send_probe_401_branch(self):
        fake_http = FakeHttpClient()
        fake_http.state["send_code"] = 401
        Path(self.signal_file).write_text("ok", encoding="utf-8")
        old = time.time() - 120
        os.utime(self.signal_file, (old, old))
        monitor = ConnectionMonitor(DummyConfigManager(self.base_cfg), JsonlLogger(self.log_dir), fake_http, sleeper=lambda _: None)
        result = monitor.run_once(self.base_cfg)
        self.assertIn("send_probe_failed:401", result["error"])

    def test_send_probe_500_branch(self):
        fake_http = FakeHttpClient()
        fake_http.state["send_code"] = 500
        Path(self.signal_file).write_text("ok", encoding="utf-8")
        old = time.time() - 120
        os.utime(self.signal_file, (old, old))
        monitor = ConnectionMonitor(DummyConfigManager(self.base_cfg), JsonlLogger(self.log_dir), fake_http, sleeper=lambda _: None)
        result = monitor.run_once(self.base_cfg)
        self.assertIn("send_probe_failed:500", result["error"])

    def test_idempotent_window_suppresses_recovery(self):
        fake_http = FakeHttpClient()
        monitor = ConnectionMonitor(DummyConfigManager(self.base_cfg), JsonlLogger(self.log_dir), fake_http, sleeper=lambda _: None)
        first = monitor.run_once(self.base_cfg)
        self.assertIn("refresh_token", first["recovery_action"])
        fake_http.state["send_ok"] = False
        fake_http.state["receive_ok"] = False
        second = monitor.run_once(self.base_cfg)
        self.assertEqual(second["recovery_action"], "suppress_recovery_in_window")

    def test_json_log_fields_complete(self):
        fake_http = FakeHttpClient()
        monitor = ConnectionMonitor(DummyConfigManager(self.base_cfg), JsonlLogger(self.log_dir), fake_http, sleeper=lambda _: None)
        monitor.run_once(self.base_cfg)
        files = list(Path(self.log_dir).glob("feishu-monitor-*.log"))
        self.assertTrue(files)
        line = files[0].read_text(encoding="utf-8").strip().splitlines()[-1]
        payload = json.loads(line)
        self.assertIn("timestamp", payload)
        self.assertIn("status", payload)
        self.assertIn("latency_ms", payload)
        self.assertIn("error", payload)
        self.assertIn("recovery_action", payload)

    def test_validate_config_key_fields(self):
        bad_cfg = MonitorConfig(
            heartbeat_seconds=61,
            timeout_seconds=30,
            failure_threshold=1,
            idempotent_window_seconds=300,
            send_probe_url="",
            receive_probe_url="x",
            receive_signal_file="x",
            token_refresh_url="x",
            channel_rebuild_url="x",
            receiver_restart_cmd="x",
            alert_webhook_url="x",
            alert_cooldown_seconds=60,
            log_dir="x",
            recovery_check_delay_seconds=1,
            headers={},
        )
        with self.assertRaises(ValueError):
            validate_config(bad_cfg)

    def test_config_hot_reload(self):
        config_path = os.path.join(self.temp_dir.name, "config.yaml")
        first = f"""
monitor:
  heartbeat_seconds: 30
  timeout_seconds: 30
  failure_threshold: 3
  idempotent_window_seconds: 300
probes:
  send_probe_url: "http://127.0.0.1/send-health"
  receive_probe_url: "http://127.0.0.1/receive-health"
  receive_signal_file: "{self.signal_file}"
  auth_token: ""
recovery:
  token_refresh_url: "http://127.0.0.1/recover/token-refresh"
  channel_rebuild_url: "http://127.0.0.1/recover/rebuild-channel"
  receiver_restart_cmd: "/bin/true"
  check_delay_seconds: 1
alert:
  webhook_url: "http://127.0.0.1/alert"
  cooldown_seconds: 120
logging:
  log_dir: "{self.log_dir}"
""".strip()
        Path(config_path).write_text(first, encoding="utf-8")
        manager = ConfigManager(config_path)
        cfg1 = manager.load_if_changed()
        self.assertEqual(cfg1.heartbeat_seconds, 30)
        time.sleep(0.02)
        second = first.replace("heartbeat_seconds: 30", "heartbeat_seconds: 20")
        Path(config_path).write_text(second, encoding="utf-8")
        cfg2 = manager.load_if_changed()
        self.assertEqual(cfg2.heartbeat_seconds, 20)

    def test_recovery_escalation_path(self):
        fake_http = FakeHttpClient()
        fake_http.state["token_ok"] = False
        fake_http.state["rebuild_ok"] = False
        cfg = MonitorConfig(**{**self.base_cfg.__dict__, "receiver_restart_cmd": "/bin/false"})
        monitor = ConnectionMonitor(DummyConfigManager(cfg), JsonlLogger(self.log_dir), fake_http, sleeper=lambda _: None)
        result = monitor.run_once(cfg)
        self.assertIn("escalate_alert", result["recovery_action"])
        self.assertEqual(result["status"], "recovering")

    def test_alert_noise_control(self):
        fake_http = FakeHttpClient()
        cfg = MonitorConfig(**{**self.base_cfg.__dict__, "alert_cooldown_seconds": 60})
        manager = AlertManager(fake_http)
        ok1 = manager.send_card(cfg, "down", "x", "a")
        ok2 = manager.send_card(cfg, "down", "x", "a")
        self.assertTrue(ok1)
        self.assertFalse(ok2)

    def test_yaml_scalar_parse(self):
        data = """
root:
  text1: "abc"
  text2: 'def'
  bool1: true
  bool2: false
  null1: null
  number1: 12
  number2: 1.5
""".strip()
        parsed = SimpleYamlParser.parse(data)
        self.assertEqual(parsed["root"]["text1"], "abc")
        self.assertEqual(parsed["root"]["text2"], "def")
        self.assertEqual(parsed["root"]["bool1"], True)
        self.assertEqual(parsed["root"]["bool2"], False)
        self.assertEqual(parsed["root"]["null1"], None)
        self.assertEqual(parsed["root"]["number1"], 12)
        self.assertEqual(parsed["root"]["number2"], 1.5)

    def test_run_forever_loop(self):
        fake_http = FakeHttpClient()
        monitor = ConnectionMonitor(DummyConfigManager(self.base_cfg), JsonlLogger(self.log_dir), fake_http)
        monitor.run_once = lambda cfg=None: None

        def stop_sleep(_):
            raise RuntimeError("stop")

        monitor.sleeper = stop_sleep
        with self.assertRaises(RuntimeError):
            monitor.run_forever()


if __name__ == "__main__":
    unittest.main()
