from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import settings  # noqa: E402
from backend.app.db import connect  # noqa: E402
from scripts.init_db import initialize_database  # noqa: E402


DATABASE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SYSTEM_DATABASES = {"master", "model", "msdb", "tempdb"}


def is_safe_test_database(database_name: str) -> bool:
    normalized = database_name.strip().lower()
    return bool(
        DATABASE_NAME_RE.fullmatch(database_name.strip())
        and normalized.endswith("_test")
        and normalized not in SYSTEM_DATABASES
    )


def reset_test_database(confirm: bool) -> None:
    database_name = settings.sqlserver_database.strip()
    if not confirm:
        raise ValueError("Pass --confirm to reset the test database.")
    if not is_safe_test_database(database_name):
        raise ValueError("Refusing to reset a database whose name does not safely end with '_Test'.")
    with connect(database="master", autocommit=True) as conn:
        cursor = conn.cursor()
        if cursor.execute("SELECT DB_ID(?)", database_name).fetchval() is not None:
            cursor.execute(
                f"ALTER DATABASE [{database_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
            )
            cursor.execute(f"DROP DATABASE [{database_name}]")
            print(f"database dropped: {database_name}")
    initialize_database()


def main() -> None:
    parser = argparse.ArgumentParser(description="Recreate the configured SQL Server test database.")
    parser.add_argument("--confirm", action="store_true", help="confirm destructive reset")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("--confirm is required to reset the test database")
    try:
        reset_test_database(args.confirm)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
