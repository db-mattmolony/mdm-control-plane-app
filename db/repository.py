"""Generic, domain-agnostic CRUD repository over Lakebase.

Nothing here knows about vendors or supply regions — it operates on table names
and column dicts supplied by the domain registry. That is what lets a new
master-data domain be added with config only (no new data-access code).

Identifiers (schema/table/column names) come from trusted config, never from
user input; values are always passed as bound parameters.
"""
from __future__ import annotations

import json
from typing import Any

from psycopg import sql

from db.connection import SCHEMA, get_connection


def _tbl(table: str) -> sql.Composed:
    return sql.SQL("{}.{}").format(sql.Identifier(SCHEMA), sql.Identifier(table))


def fetch_all(table: str, where: str | None = None,
              params: tuple | None = None, order_by: str | None = None) -> list[dict]:
    query = sql.SQL("SELECT * FROM {}").format(_tbl(table))
    if where:
        query = query + sql.SQL(" WHERE ") + sql.SQL(where)  # noqa: S608 (config only)
    if order_by:
        query = query + sql.SQL(" ORDER BY ") + sql.SQL(order_by)
    with get_connection() as conn:
        return conn.execute(query, params or ()).fetchall()


def get_one(table: str, pk_col: str, pk_val: Any) -> dict | None:
    query = sql.SQL("SELECT * FROM {} WHERE {} = %s").format(_tbl(table), sql.Identifier(pk_col))
    with get_connection() as conn:
        return conn.execute(query, (pk_val,)).fetchone()


def insert(table: str, data: dict[str, Any], returning: str | None = None) -> Any:
    cols = list(data.keys())
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        _tbl(table),
        sql.SQL(", ").join(map(sql.Identifier, cols)),
        sql.SQL(", ").join(sql.Placeholder() * len(cols)),
    )
    if returning:
        query = query + sql.SQL(" RETURNING {}").format(sql.Identifier(returning))
    with get_connection() as conn:
        cur = conn.execute(query, tuple(data.values()))
        row = cur.fetchone() if returning else None
        conn.commit()
        return row[returning] if row else None


def bulk_insert(table: str, rows: list[dict[str, Any]]) -> int:
    """Insert many rows in a single transaction (one commit).

    Used for the initial seed load — the per-row insert() commits every row,
    which is unworkable for thousands of rows. All rows must share the same
    columns (taken from the first row).
    """
    if not rows:
        return 0
    cols = list(rows[0].keys())
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        _tbl(table),
        sql.SQL(", ").join(map(sql.Identifier, cols)),
        sql.SQL(", ").join(sql.Placeholder() * len(cols)),
    )
    with get_connection() as conn:
        conn.cursor().executemany(query, [tuple(r[c] for c in cols) for r in rows])
        conn.commit()
    return len(rows)


def update(table: str, pk_col: str, pk_val: Any, data: dict[str, Any]) -> None:
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = %s").format(sql.Identifier(c)) for c in data
    )
    query = sql.SQL("UPDATE {} SET {} WHERE {} = %s").format(
        _tbl(table), assignments, sql.Identifier(pk_col)
    )
    with get_connection() as conn:
        conn.execute(query, tuple(data.values()) + (pk_val,))
        conn.commit()


def count(table: str, where: str | None = None, params: tuple | None = None) -> int:
    query = sql.SQL("SELECT COUNT(*) AS n FROM {}").format(_tbl(table))
    if where:
        query = query + sql.SQL(" WHERE ") + sql.SQL(where)
    with get_connection() as conn:
        return conn.execute(query, params or ()).fetchone()["n"]


def write_audit(changed_by: str, action: str, domain_key: str,
                record_pk: Any, before: dict | None, after: dict | None) -> None:
    def _clean(d):
        if d is None:
            return None
        return json.dumps(d, default=str)

    query = sql.SQL(
        "INSERT INTO {} (changed_by, action, domain_key, record_pk, before_json, after_json) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    ).format(_tbl("audit_log"))
    with get_connection() as conn:
        conn.execute(query, (changed_by, action, domain_key, str(record_pk),
                             _clean(before), _clean(after)))
        conn.commit()
