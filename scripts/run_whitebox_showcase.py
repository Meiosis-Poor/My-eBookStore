from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from scripts.render_whitebox_report import render  # noqa: E402
from scripts.reset_test_db import is_safe_test_database  # noqa: E402


DEFAULT_SEED = 20260716


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the retained one-time white-box showcase.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--archive", action="store_true", help="replace the teacher-facing report snapshot")
    args = parser.parse_args()
    if Path(os.getenv("EBOOKSTORE_ENV_FILE", "")).name.lower() != ".env.test":
        parser.error("set EBOOKSTORE_ENV_FILE=.env.test before running")
    if not is_safe_test_database(settings.sqlserver_database):
        parser.error("the configured database must safely end with _Test")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    result_dir = ROOT / "test-results" / "whitebox" / timestamp
    result_dir.mkdir(parents=True)
    junit = result_dir / "junit.xml"
    coverage_json = result_dir / "coverage.json"
    coverage_html = result_dir / "coverage-html"
    command = [
        sys.executable, "-m", "pytest",
        "tests/whitebox", "tests/test_embedding.py",
        "tests/test_acceptance_transaction.py", "tests/test_acceptance_security.py",
        "tests/test_database_workflows.py",
        "-m", "not performance",
        f"--junitxml={junit}",
        "--cov=backend.app", "--cov-branch",
        f"--cov-report=json:{coverage_json}",
        f"--cov-report=html:{coverage_html}",
        "--cov-report=term-missing", "-q",
    ]
    env = {**os.environ, "HYPOTHESIS_SEED": str(args.seed)}
    started = time.monotonic()
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    duration = time.monotonic() - started
    commit = _git_commit()

    condition_matrix = """# 关键条件覆盖矩阵

| 判定 | 有效路径 | 无效/拒绝路径 |
| --- | --- | --- |
| Token | 合法用户 | 缺失、伪造、用户不存在、禁用 |
| 角色 | 角色在允许集合 | 角色不在允许集合 |
| 支付 | 待支付且库存充足 | 不存在、重复支付、状态非法、空明细、库存不足、过程异常 |
| 评价 | 已购买且已支付且未评价 | 未购买、未支付、重复评价、评分越界 |
| 事务 | 正常提交 | 异常回滚并重新抛出 |
"""
    (result_dir / "condition-matrix.md").write_text(condition_matrix, encoding="utf-8")
    summary = "\n".join([
        "# White-box showcase summary", "",
        f"- Result: {'PASS' if completed.returncode == 0 else 'FAIL'}",
        f"- Commit: `{commit}`", f"- Database: `{settings.sqlserver_database}`",
        f"- Seed: `{args.seed}`", f"- Duration: `{duration:.2f}s`",
        f"- Command: `{' '.join(command)}`", "",
        "This is a retained pre-executed report; it does not need to run during acceptance.",
    ]) + "\n"
    (result_dir / "summary.md").write_text(summary, encoding="utf-8")
    if junit.exists() and coverage_json.exists():
        render(result_dir, commit=commit, database=settings.sqlserver_database, seed=args.seed, duration=duration)

    if completed.returncode == 0 and args.archive:
        archive = ROOT / "docs" / "reports" / "whitebox-showcase"
        if archive.exists():
            shutil.rmtree(archive)
        shutil.copytree(result_dir, archive)
    print(f"white-box report: {result_dir / 'readable-report.md'}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
