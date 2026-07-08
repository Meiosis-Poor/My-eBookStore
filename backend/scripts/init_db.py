from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db import connect  # noqa: E402


GO_RE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+([A-Za-z_][\w]*)", re.IGNORECASE)


def split_batches(sql: str) -> list[str]:
    return [batch.strip() for batch in GO_RE.split(sql) if batch.strip()]


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
    sql_path = REPO_ROOT / "SQLQuery1.sql"
    try:
        raw = sql_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = sql_path.read_text(encoding="gbk")
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
        for extra in (ROOT / "sql" / "search_history.sql",):
            for batch in split_batches(extra.read_text(encoding="utf-8")):
                execute_if_needed(conn, batch)
        print("schema initialization succeeded.")


if __name__ == "__main__":
    main()
