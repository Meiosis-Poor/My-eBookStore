from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.db import connect  # noqa: E402


GO_RE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+([A-Za-z_][\w]*)", re.IGNORECASE)


def split_batches(sql: str) -> list[str]:
    return [batch.strip() for batch in GO_RE.split(sql) if batch.strip()]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk")


def table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.cursor()
        .execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = ?", table_name)
        .fetchone()
    )


def execute_if_needed(conn, batch: str) -> None:
    match = CREATE_TABLE_RE.search(batch)
    if match and table_exists(conn, match.group(1)):
        print(f"skip existing table {match.group(1)}")
        return
    conn.cursor().execute(batch)


def main() -> None:
    sql_path = ROOT / "database" / "01_buildlist.sql"
    raw = read_text(sql_path)
    batches = split_batches(raw)

    with connect(database="master", autocommit=True) as master:
        master.cursor().execute(
            f"IF DB_ID(N'{settings.sqlserver_database}') IS NULL CREATE DATABASE [{settings.sqlserver_database}]"
        )
        print(f"database ready: {settings.sqlserver_database}")

    with connect(autocommit=True) as conn:
        for batch in batches:
            upper = batch.upper()
            if upper.startswith("CREATE DATABASE") or upper.startswith("USE "):
                continue
            execute_if_needed(conn, batch)
        print("schema initialization succeeded.")


if __name__ == "__main__":
    main()
