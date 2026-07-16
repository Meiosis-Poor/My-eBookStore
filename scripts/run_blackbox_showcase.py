from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from scripts.reset_test_db import is_safe_test_database, reset_test_database  # noqa: E402
from scripts.render_blackbox_report import render  # noqa: E402
from tests.blackbox.coverage_matrix import write_markdown  # noqa: E402


DEFAULT_SEED = 20260716


def parse_junit(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        name: sum(int(suite.attrib.get(name, 0)) for suite in suites)
        for name in ("tests", "failures", "errors", "skipped")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the retained black-box course demonstration.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reset", action="store_true", help="reset the configured _Test database first")
    args = parser.parse_args()

    if Path(os.getenv("EBOOKSTORE_ENV_FILE", "")).name.lower() != ".env.test":
        parser.error("set EBOOKSTORE_ENV_FILE=.env.test before running")
    if not is_safe_test_database(settings.sqlserver_database):
        parser.error("the configured database must safely end with _Test")
    if args.reset:
        reset_test_database(confirm=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result_dir = ROOT / "test-results" / "blackbox" / timestamp
    result_dir.mkdir(parents=True)
    matrix_stats = write_markdown(result_dir / "coverage-matrix.md")
    junit = result_dir / "junit.xml"
    html = result_dir / "report.html"
    env = {**os.environ, "EBOOKSTORE_BLACKBOX_PROFILE": "full"}
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "blackbox_smoke or blackbox_full",
        f"--hypothesis-seed={args.seed}",
        "--hypothesis-show-statistics",
        f"--junitxml={junit}",
        f"--html={html}",
        "--self-contained-html",
        "-q",
    ]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    duration = time.monotonic() - started
    counts = parse_junit(junit) if junit.exists() else {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    summary = result_dir / "summary.md"
    summary.write_text(
        "\n".join(
            [
                "# Black-box demonstration summary",
                "",
                f"- Result: {'PASS' if completed.returncode == 0 else 'FAIL'}",
                f"- Database: `{settings.sqlserver_database}` (isolation guard enabled)",
                f"- Hypothesis seed: `{args.seed}`",
                f"- Duration: `{duration:.1f}s`",
                f"- Tests: `{counts['tests']}`; failures: `{counts['failures']}`; errors: `{counts['errors']}`; skipped: `{counts['skipped']}`",
                f"- OpenAPI operations: `{matrix_stats['operations']}`",
                f"- Matrix gaps: positive `{matrix_stats['positive_gaps']}`, authentication `{matrix_stats['authentication_gaps']}`, role `{matrix_stats['role_gaps']}`",
                f"- Command: `{' '.join(command)}`",
                "- Artifacts: `readable-report.md`, `junit.xml`, `report.html`, `coverage-matrix.md`",
                "",
                "A zero exit code includes the session-level database state and artifact guard.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if junit.exists():
        render(result_dir)
    print(f"black-box report: {summary}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
