from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.db import connect  # noqa: E402


GO_RE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts\\run_sql_file.py database\\99_test_seed.sql")
    sql_path = Path(sys.argv[1])
    batches = [batch.strip() for batch in GO_RE.split(read_text(sql_path)) if batch.strip()]
    with connect(autocommit=True) as conn:
        for batch in batches:
            conn.cursor().execute(batch)
    print(f"executed {len(batches)} SQL batch(es) from {sql_path}")


if __name__ == "__main__":
    main()
