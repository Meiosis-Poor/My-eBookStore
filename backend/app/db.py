from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import pyodbc

from .config import settings


def connect(database: str | None = None, autocommit: bool = False) -> pyodbc.Connection:
    return pyodbc.connect(settings.connection_string(database), autocommit=autocommit, timeout=8)


@contextmanager
def get_conn() -> Iterator[pyodbc.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def one(cur: pyodbc.Cursor) -> dict[str, Any] | None:
    row = cur.fetchone()
    if row is None:
        return None
    return row_to_dict(cur, row)


def many(cur: pyodbc.Cursor) -> list[dict[str, Any]]:
    return [row_to_dict(cur, row) for row in cur.fetchall()]


def row_to_dict(cur: pyodbc.Cursor, row: pyodbc.Row) -> dict[str, Any]:
    columns = [col[0] for col in cur.description]
    return {columns[i]: normalize_value(row[i]) for i in range(len(columns))}


def normalize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def execute_scalar(conn: pyodbc.Connection, sql: str, *params: Any) -> Any:
    return conn.cursor().execute(sql, *params).fetchval()


def procedure_result(cursor: pyodbc.Cursor, sql: str, *params: Any) -> dict[str, Any] | None:
    cursor.execute(sql, *params)
    while cursor.description is None:
        if not cursor.nextset():
            return None
    return one(cursor)
