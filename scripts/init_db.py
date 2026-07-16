from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.db import connect  # noqa: E402


GO_RE = re.compile(r"^\s*GO\s*$", re.IGNORECASE | re.MULTILINE)
CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+([A-Za-z_][\w]*)", re.IGNORECASE)
MIGRATIONS = (
    ROOT / "database" / "01_buildlist.sql",
    ROOT / "database" / "02_bulidindex.sql",
    ROOT / "database" / "03_seed.sql",
    ROOT / "database" / "04_procedures.sql",
    ROOT / "database" / "05_triggers.sql",
    ROOT / "database" / "99_test_seed.sql",
)


def split_batches(sql: str) -> list[str]:
    return [batch.strip() for batch in GO_RE.split(sql) if batch.strip()]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


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


def ensure_migration_table(conn) -> None:
    conn.cursor().execute(
        """
        IF OBJECT_ID(N'dbo.deployment_migrations', N'U') IS NULL
        BEGIN
            CREATE TABLE dbo.deployment_migrations(
                migration_name NVARCHAR(255) NOT NULL PRIMARY KEY,
                checksum CHAR(64) NOT NULL,
                applied_time DATETIME2 NOT NULL DEFAULT SYSDATETIME()
            )
        END
        """
    )


def applied_checksum(conn, migration_name: str) -> str | None:
    row = conn.cursor().execute(
        "SELECT checksum FROM dbo.deployment_migrations WHERE migration_name = ?",
        migration_name,
    ).fetchone()
    return str(row[0]) if row else None


def apply_migration(conn, path: Path) -> None:
    migration_name = path.name
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    previous = applied_checksum(conn, migration_name)
    if previous == checksum:
        print(f"skip applied migration: {migration_name}")
        return
    if previous is not None:
        raise RuntimeError(
            f"migration {migration_name} changed after it was applied; add a new migration instead"
        )

    for batch in split_batches(read_text(path)):
        if batch.upper().startswith(("CREATE DATABASE", "USE ")):
            continue
        if migration_name == "01_buildlist.sql":
            execute_if_needed(conn, batch)
        else:
            conn.cursor().execute(batch)

    conn.cursor().execute(
        "INSERT INTO dbo.deployment_migrations(migration_name, checksum) VALUES (?, ?)",
        migration_name,
        checksum,
    )
    print(f"applied migration: {migration_name}")


def main() -> None:
    with connect(database="master", autocommit=True) as master:
        master.cursor().execute(
            f"IF DB_ID(N'{settings.sqlserver_database}') IS NULL CREATE DATABASE [{settings.sqlserver_database}]"
        )
        print(f"database ready: {settings.sqlserver_database}")

    with connect(autocommit=True) as conn:
        ensure_migration_table(conn)
        for migration in MIGRATIONS:
            apply_migration(conn, migration)
        print("database initialization succeeded.")


if __name__ == "__main__":
    main()
