from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from scripts.render_selenium_report import render  # noqa: E402
from scripts.reset_test_db import is_safe_test_database  # noqa: E402
from tests.ui.case_matrix import CASES  # noqa: E402


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def git_commit() -> str:
    result = subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() or "unknown"


def chrome_version() -> str:
    candidates = [
        Path(os.getenv("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.getenv("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    chrome = next((path for path in candidates if path.exists()), None)
    if chrome is None:
        raise RuntimeError("Google Chrome is not installed")
    versions = [path.name for path in chrome.parent.iterdir() if path.is_dir() and path.name[:1].isdigit()]
    return max(versions, default="installed")


def wait_for_server(port: int, process: subprocess.Popen) -> None:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Uvicorn exited before health check")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Uvicorn health check timed out")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and retain the Chrome Selenium course showcase.")
    parser.add_argument("--archive", action="store_true", help="replace the teacher-facing snapshot")
    parser.add_argument("--headed", action="store_true", help="show Chrome while running")
    args = parser.parse_args()
    if Path(os.getenv("EBOOKSTORE_ENV_FILE", "")).name.lower() != ".env.test":
        parser.error("set EBOOKSTORE_ENV_FILE=.env.test before running")
    if not is_safe_test_database(settings.sqlserver_database):
        parser.error("the configured database must safely end with _Test")

    version = chrome_version()
    port = free_port()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result_dir = ROOT / "test-results" / "selenium" / timestamp
    result_dir.mkdir(parents=True)
    env = {
        **os.environ,
        "EBOOKSTORE_UI_BASE_URL": f"http://127.0.0.1:{port}",
        "EBOOKSTORE_UI_RESULT_DIR": str(result_dir),
    }
    log = (result_dir / "uvicorn.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    junit = result_dir / "junit.xml"
    html = result_dir / "report.html"
    command = [sys.executable, "-m", "pytest", "tests/ui", f"--junitxml={junit}", f"--html={html}", "--self-contained-html", "-q"]
    if args.headed:
        command.append("--headed")
    started = time.monotonic()
    try:
        wait_for_server(port, server)
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill(); server.wait(timeout=5)
        log.close()
    duration = time.monotonic() - started
    commit = git_commit()
    matrix_lines = ["# Selenium 场景矩阵", "", "| 编号 | 角色 | 场景 | 预期结果 | pytest 用例 |", "| --- | --- | --- | --- | --- |"]
    matrix_lines.extend(f"| {cid} | {role} | {scene} | {expected} | `{test}` |" for cid, role, scene, expected, test in CASES)
    (result_dir / "case-matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")
    (result_dir / "summary.md").write_text(
        "\n".join(["# Selenium showcase summary", "", f"- Result: {'PASS' if completed.returncode == 0 else 'FAIL'}", f"- Commit: `{commit}`", f"- Chrome: `{version}`", f"- Database: `{settings.sqlserver_database}`", f"- Port: `{port}`", f"- Duration: `{duration:.2f}s`", f"- Command: `{' '.join(command)}`", "", "This report was executed in advance; acceptance only needs to display the archived artifacts."]) + "\n",
        encoding="utf-8",
    )
    if junit.exists():
        render(result_dir, commit=commit, chrome_version=version, duration=duration, port=port)
    if completed.returncode == 0 and args.archive:
        archive = ROOT / "docs/reports/selenium-showcase"
        if archive.exists():
            shutil.rmtree(archive)
        shutil.copytree(result_dir, archive)
    print(f"selenium report: {result_dir / 'readable-report.md'}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
