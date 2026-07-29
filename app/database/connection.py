"""
Postgres connection layer with SQLite-compatible shim.
"""

from typing import Any

import psycopg2

from langgraph.checkpoint.postgres import PostgresSaver

from app.config.settings import DATABASE_URL


class _SqliteStyleConn:
    """Shim so SQLite-style ? placeholders and conn.execute(...)
    calls work seamlessly against Postgres via psycopg2."""

    def __init__(self, dsn):
        self._dsn = dsn
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True  # avoid idle-in-transaction on reads

    def _ensure_connected(self):
        """Reconnect if the underlying connection was dropped."""
        try:
            if self._conn.closed != 0:
                self._conn = psycopg2.connect(self._dsn)
                self._conn.autocommit = True
        except Exception:
            self._conn = psycopg2.connect(self._dsn)
            self._conn.autocommit = True

    def execute(self, query, params=()) -> "Any":
        q_strip = query.strip().upper()
        if q_strip in ("BEGIN IMMEDIATE", "BEGIN TRANSACTION", "BEGIN"):
            self._conn.autocommit = False  # enter explicit transaction
            return self

        query = query.replace("?", "%s").replace("date('now')", "CURRENT_DATE")
        self._ensure_connected()
        try:
            cur = self._conn.cursor()
            cur.execute(query, params)
            return cur
        except Exception:
            # rollback and retry once with a fresh connection
            try:
                self._conn.rollback()
            except Exception:
                pass
            try:
                self._conn = psycopg2.connect(self._dsn)
                self._conn.autocommit = True
                cur = self._conn.cursor()
                cur.execute(query, params)
                return cur
            except Exception:
                raise

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self):
        self._conn.commit()
        self._conn.autocommit = True  # back to autocommit after explicit txn

    def rollback(self):
        self._conn.rollback()
        self._conn.autocommit = True  # back to autocommit after explicit txn


bookings_conn = _SqliteStyleConn(DATABASE_URL)

# PostgresSaver manages LangGraph thread checkpoints in Supabase
checkpointer_cm = PostgresSaver.from_conn_string(DATABASE_URL)
checkpointer = checkpointer_cm.__enter__()
checkpointer.setup()  # auto-creates checkpoint tables on first run
