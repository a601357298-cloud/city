#!/usr/bin/env python3
"""Local watchdog for OpenClaw gateway on macOS.

Goal: avoid spending chat tokens on routine connectivity babysitting.
This script performs a cheap local health check and restarts the gateway if unhealthy.

Default strategy:
- run `openclaw gateway status`
- if output does not indicate a healthy runtime+probe, run `openclaw gateway restart`
- append structured logs locally for later inspection
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_LOG_DIR = Path.home() / ".openclaw" / "watchdog-logs"
DEFAULT_STATUS_CMD = "openclaw gateway status"
DEFAULT_RESTART_CMD = "openclaw gateway restart"


@dataclass
class CheckResult:
    timestamp: str
    status: str
    reason: str
    action: str
    status_exit_code: int
    restart_exit_code: Optional[int]
    status_excerpt: str
    restart_excerpt: str


@dataclass
class HealthResult:
    healthy: bool
    reason: str
    excerpt: str
    exit_code: int


def run_command(command: str, timeout: int = 45) -> tuple[int, str]:
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    return proc.returncode, output


def evaluate_health(output: str, exit_code: int) -> HealthResult:
    text = output.lower()
    if exit_code != 0:
        return HealthResult(False, f"status command failed ({exit_code})", output[:1000], exit_code)

    runtime_ok = "runtime: running" in text
    probe_ok = "rpc probe: ok" in text or "probe: ok" in text
    listening = "listening:" in text

    if runtime_ok and probe_ok and listening:
        return HealthResult(True, "gateway healthy", output[:1000], exit_code)

    missing = []
    if not runtime_ok:
        missing.append("runtime")
    if not probe_ok:
        missing.append("probe")
    if not listening:
        missing.append("listening")
    reason = "gateway unhealthy: missing " + ", ".join(missing)
    return HealthResult(False, reason, output[:1000], exit_code)


def append_log(log_dir: Path, result: CheckResult) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"feishu-gateway-watchdog-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
    return path


def do_check(status_cmd: str, restart_cmd: str, log_dir: Path) -> CheckResult:
    now = datetime.now().isoformat(timespec="seconds")
    status_exit, status_output = run_command(status_cmd)
    health = evaluate_health(status_output, status_exit)

    if health.healthy:
        result = CheckResult(
            timestamp=now,
            status="ok",
            reason=health.reason,
            action="none",
            status_exit_code=status_exit,
            restart_exit_code=None,
            status_excerpt=health.excerpt,
            restart_excerpt="",
        )
        append_log(log_dir, result)
        return result

    restart_exit, restart_output = run_command(restart_cmd)
    result = CheckResult(
        timestamp=now,
        status="restarted" if restart_exit == 0 else "restart_failed",
        reason=health.reason,
        action=restart_cmd,
        status_exit_code=status_exit,
        restart_exit_code=restart_exit,
        status_excerpt=health.excerpt,
        restart_excerpt=restart_output[:1000],
    )
    append_log(log_dir, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw Feishu gateway watchdog")
    parser.add_argument("--status-cmd", default=DEFAULT_STATUS_CMD)
    parser.add_argument("--restart-cmd", default=DEFAULT_RESTART_CMD)
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    result = do_check(args.status_cmd, args.restart_cmd, Path(args.log_dir).expanduser())

    if not args.quiet:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))

    return 0 if result.status in {"ok", "restarted"} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "status": "timeout",
            "reason": f"command timeout: {shlex.join(exc.cmd) if isinstance(exc.cmd, list) else exc.cmd}",
        }
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
