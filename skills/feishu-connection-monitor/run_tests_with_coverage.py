import subprocess
import sys
from pathlib import Path


def run_tests() -> int:
    cover_dir = Path.cwd() / ".trace"
    cover_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "trace",
        "--count",
        "--summary",
        f"--coverdir={cover_dir}",
        "--module",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr.strip():
        print(result.stderr)
    return result.returncode


def compute_coverage() -> float:
    target = Path.cwd() / "monitor.py"
    cover_files = list((Path.cwd() / ".trace").glob("**/monitor.cover"))
    if not cover_files:
        return 0.0
    cover_file = cover_files[0]
    executed = 0
    total = 0
    source = target.read_text(encoding="utf-8").splitlines()
    counts = cover_file.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(source, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("import ", "from ")):
            continue
        total += 1
        marker = counts[idx - 1].split(":", 1)[0].strip()
        if marker and marker != ">>>>>>":
            try:
                if int(marker) > 0:
                    executed += 1
            except ValueError:
                pass
    if total == 0:
        return 0.0
    return executed / total * 100


def main() -> int:
    code = run_tests()
    coverage = compute_coverage()
    print(f"COVERAGE={coverage:.2f}%")
    if code != 0:
        return code
    if coverage < 80:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
