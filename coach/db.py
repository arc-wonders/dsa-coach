"""Database layer. SQLite locally; Postgres when DATABASE_URL is set (Vercel).

Queries are written in SQLite style (`?` placeholders, INSERT OR IGNORE) and
translated for Postgres in Conn.execute.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    slug TEXT PRIMARY KEY,
    title TEXT,
    difficulty TEXT,
    pattern TEXT NOT NULL,
    in_list INTEGER NOT NULL DEFAULT 0,
    list_order INTEGER,
    tags TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS attempts (
    id {pk},
    slug TEXT NOT NULL,
    ts BIGINT NOT NULL,
    outcome TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE(slug, ts, outcome)
);
CREATE TABLE IF NOT EXISTS srs (
    slug TEXT PRIMARY KEY,
    first_solved BIGINT,
    last_solved BIGINT,
    last_attempt BIGINT,
    step INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 0,
    due BIGINT,
    solves INTEGER NOT NULL DEFAULT 0,
    fails INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS plan_items (
    id {pk},
    day TEXT NOT NULL,
    slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    updated_at BIGINT,
    UNIQUE(day, slug)
);
CREATE TABLE IF NOT EXISTS plans (
    day TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    note TEXT,
    emailed_at BIGINT
);
CREATE TABLE IF NOT EXISTS availability (
    id {pk},
    start_day TEXT NOT NULL,
    end_day TEXT NOT NULL,
    mode TEXT NOT NULL,
    note TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS day_load (day TEXT PRIMARY KEY, level INTEGER NOT NULL);
"""
# Columns added after the first release: (table, column, type)
MIGRATIONS = [
    ("problems", "striver", "INTEGER NOT NULL DEFAULT 0"),
    ("plans", "level", "INTEGER"),
    ("plan_items", "est_min", "INTEGER"),
]
TABLES = ["problems", "attempts", "srs", "plan_items", "plans", "availability", "settings", "day_load"]

DEFAULT_SETTINGS = {
    "goal_end": "",
    "goal_total": "",
    "default_mode": "normal",
    "weekend_mode": "free",
    # default effort level (0 off .. 4 deep) for each mode
    "mode_levels": {"off": 0, "exam": 1, "normal": 2, "free": 3},
    # minutes per level
    "level_minutes": [0, 15, 35, 60, 120],
    "start_date": "",
    "last_auto_run": "",
    "last_sync": 0,
}

IS_PG = config.DATABASE_URL.startswith(("postgres://", "postgresql://"))


class Row(dict):
    """dict that also supports row[0], like sqlite3.Row."""

    def __init__(self, cols, vals):
        super().__init__(zip(cols, vals))
        self._vals = vals

    def __getitem__(self, k):
        return self._vals[k] if isinstance(k, int) else super().__getitem__(k)


def _pg_sql(sql: str) -> str:
    sql = sql.replace("?", "%s")
    if "INSERT OR IGNORE" in sql:
        sql = sql.replace("INSERT OR IGNORE", "INSERT") + " ON CONFLICT DO NOTHING"
    return sql


class Conn:
    """Thin wrapper so both backends look the same, plus a per-connection cache."""

    def __init__(self):
        self.cache: dict = {}
        if IS_PG:
            import psycopg

            def factory(cursor):
                cols = [d.name for d in cursor.description] if cursor.description else []
                return lambda vals: Row(cols, vals)

            self.raw = psycopg.connect(config.DATABASE_URL, row_factory=factory, connect_timeout=15,
                                       prepare_threshold=None)  # safe behind Neon's pooler
        else:
            self.raw = sqlite3.connect(config.DB_PATH, timeout=30)
            self.raw.row_factory = sqlite3.Row
            self.raw.execute("PRAGMA journal_mode=WAL")

    def execute(self, sql: str, params=()):
        if IS_PG:
            return self.raw.execute(_pg_sql(sql), params)
        return self.raw.execute(sql, params)

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()


def connect() -> Conn:
    return Conn()


@contextmanager
def tx():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema() -> None:
    pk = "BIGSERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with tx() as c:
        for stmt in SCHEMA.format(pk=pk).split(";"):
            if stmt.strip():
                c.execute(stmt)
        for table, col, typ in MIGRATIONS:
            if IS_PG:
                c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}")
            elif col not in [r[1] for r in c.execute(f"PRAGMA table_info({table})")]:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, json.dumps(v)))


def _all_settings(conn: Conn) -> dict:
    if "settings" not in conn.cache:
        s = dict(DEFAULT_SETTINGS)
        s.update({r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM settings")})
        conn.cache["settings"] = s
    return conn.cache["settings"]


def get_setting(key: str, conn: Conn | None = None):
    if conn is None:
        with tx() as c:
            return get_setting(key, c)
    return _all_settings(conn).get(key)


def set_setting(key: str, value, conn: Conn | None = None) -> None:
    if conn is None:
        with tx() as c:
            set_setting(key, value, c)
        return
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)),
    )
    conn.cache.pop("settings", None)


def now_ts() -> int:
    return int(datetime.now(config.TZ).timestamp())


def today() -> date:
    return datetime.now(config.TZ).date()


def ts_to_date(ts: int) -> date:
    return datetime.fromtimestamp(ts, config.TZ).date()


def copy_from_sqlite(path: str) -> dict:
    """Copy every table from a local SQLite file into the configured database."""
    src = sqlite3.connect(path)
    src.row_factory = sqlite3.Row
    init_schema()
    counts = {}
    with tx() as c:
        for t in TABLES:
            rows = src.execute(f"SELECT * FROM {t}").fetchall()
            if t == "settings":
                for r in rows:
                    c.execute("INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                              (r["key"], r["value"]))
            elif rows:
                cols = rows[0].keys()
                sql = f"INSERT OR IGNORE INTO {t}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
                for r in rows:
                    c.execute(sql, tuple(r))
            counts[t] = len(rows)
        if IS_PG:
            for t in ("attempts", "plan_items", "availability"):
                c.execute(f"SELECT setval(pg_get_serial_sequence('{t}','id'), COALESCE((SELECT MAX(id) FROM {t}), 0) + 1, false)")
    return counts
