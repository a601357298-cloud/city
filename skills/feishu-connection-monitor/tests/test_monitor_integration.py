import os
import tempfile
import time
import unittest
from pathlib import Path

from monitor import ConfigManager, ConnectionMonitor, JsonlLogger


class IntegrationHttpClient:
    def __init__(self):
        self.offline = True
        self.alert_count = 0
        self.recovery_count = 0

    def get(self, url, headers, timeout):
        if self.offline:
            return 500, "network down"
        return 200, "ok"

    def post_json(self, url, payload, headers, timeout):
        if "token-refresh" in url:
            self.recovery_count += 1
            self.offline = False
            return 200, "ok"
        if "rebuild-channel" in url:
            return 200, "ok"
        if "alert" in url:
            self.alert_count += 1
            return 200, "ok"
        return 404, "missing"


class MonitorIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "feishu-monitor.yaml")
        self.signal_file = os.path.join(self.temp_dir.name, "receive.signal")
        self.log_dir = os.path.join(self.temp_dir.name, "logs")
        old = time.time() - 61
        Path(self.signal_file).write_text("stale", encoding="utf-8")
        os.utime(self.signal_file, (old, old))
        content = f"""
monitor:
  heartbeat_seconds: 30
  timeout_seconds: 30
  failure_threshold: 1
  idempotent_window_seconds: 300
probes:
  send_probe_url: "http://local/send-health"
  receive_probe_url: "http://local/receive-health"
  receive_signal_file: "{self.signal_file}"
  auth_token: ""
recovery:
  token_refresh_url: "http://local/recover/token-refresh"
  channel_rebuild_url: "http://local/recover/rebuild-channel"
  receiver_restart_cmd: "/bin/true"
  check_delay_seconds: 0
alert:
  webhook_url: "http://local/alert"
  cooldown_seconds: 0
logging:
  log_dir: "{self.log_dir}"
""".strip()
        Path(self.config_path).write_text(content, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_simulate_60s_disconnect_then_auto_recover(self):
        config_manager = ConfigManager(self.config_path)
        cfg = config_manager.load_if_changed()
        http_client = IntegrationHttpClient()
        monitor = ConnectionMonitor(config_manager, JsonlLogger(cfg.log_dir), http_client, sleeper=lambda _: None)
        first = monitor.run_once(cfg)
        self.assertEqual(first["status"], "up")
        self.assertIn("refresh_token", first["recovery_action"])
        self.assertEqual(http_client.recovery_count, 1)
        files = list(Path(self.log_dir).glob("feishu-monitor-*.log"))
        self.assertTrue(files)
        payload = files[0].read_text(encoding="utf-8")
        self.assertIn("recovery_action", payload)


if __name__ == "__main__":
    unittest.main()
