from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db import connect  # noqa: E402


def main() -> None:
    print(f"Connecting to SQL Server: {settings.sqlserver_server}")
    with connect(database="master", autocommit=True) as conn:
        cur = conn.cursor()
        print("SELECT 1 ->", cur.execute("SELECT 1").fetchval())
        row = cur.execute("SELECT @@SERVERNAME AS server_name, @@VERSION AS version").fetchone()
        print("Server:", row.server_name)
        print("Version:", row.version.splitlines()[0])
    print("SQL Server check succeeded.")


if __name__ == "__main__":
    main()
