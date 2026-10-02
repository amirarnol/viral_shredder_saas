"""SQLite persistence layer.

A thin, dependency-free wrapper around sqlite3. Every public helper opens its
own short-lived connection so the code is safe across threads/async tasks.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import settings

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not already exist."""
    with _lock:
        with get_conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    email         TEXT UNIQUE NOT NULL,
                    plan          TEXT NOT NULL DEFAULT 'free',
                    credits_used  INTEGER NOT NULL DEFAULT 0,
                    created_at    TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL REFERENCES users(id),
                    source_url    TEXT NOT NULL,
                    platform      TEXT,
                    title         TEXT,
                    status        TEXT NOT NULL DEFAULT 'pending',
                    outputs       TEXT NOT NULL DEFAULT '[]',
                    created_at    TEXT NOT NULL,
                    completed_at  TEXT
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL REFERENCES users(id),
                    order_ref     TEXT UNIQUE NOT NULL,
                    amount_usd    REAL NOT NULL,
                    currency      TEXT NOT NULL DEFAULT 'USDT',
                    network       TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT 'pending',
                    tx_hash       TEXT,
                    created_at    TEXT NOT NULL,
                    confirmed_at  TEXT
                );

                CREATE TABLE IF NOT EXISTS submissions (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    directory     TEXT NOT NULL,
                    site_url      TEXT NOT NULL,
                    status        TEXT NOT NULL,
                    payload       TEXT NOT NULL DEFAULT '{}',
                    submitted_at  TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
                CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
                CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
                """
            )


# ------------------------------------------------------------------ users
def get_or_create_user(email: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        if row:
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO users (email, created_at) VALUES (?, ?)",
            (email.strip().lower(), _now()),
        )
        return int(cur.lastrowid)


def get_user(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def set_user_plan(user_id: int, plan: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))


def record_credit_use(user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET credits_used = credits_used + 1 WHERE id = ?", (user_id,)
        )


# ------------------------------------------------------------------- jobs
def create_job(user_id: int, source_url: str, platform: str, title: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO jobs (user_id, source_url, platform, title, status, created_at)
               VALUES (?, ?, ?, ?, 'processing', ?)""",
            (user_id, source_url, platform, title, _now()),
        )
        return int(cur.lastrowid)


def complete_job(job_id: int, outputs: dict[str, str]) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'completed', outputs = ?, completed_at = ? WHERE id = ?",
            (json.dumps(outputs), _now(), job_id),
        )


def fail_job(job_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'failed', completed_at = ? WHERE id = ?",
            (_now(), job_id),
        )


def get_job(job_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def recent_jobs(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, source_url, platform, title, status, created_at, completed_at
               FROM jobs WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------------------------------- payments
def create_payment(
    user_id: int, order_ref: str, amount_usd: float, currency: str, network: str
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO payments
                 (user_id, order_ref, amount_usd, currency, network, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (user_id, order_ref, amount_usd, currency, network, _now()),
        )
        return int(cur.lastrowid)


def confirm_payment(payment_id: int, tx_hash: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE payments
               SET status = 'paid', tx_hash = ?, confirmed_at = ?
               WHERE id = ? AND status = 'pending'""",
            (tx_hash, _now(), payment_id),
        )


def get_payment(payment_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        return dict(row) if row else None


def get_payment_by_ref(order_ref: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM payments WHERE order_ref = ?", (order_ref,)
        ).fetchone()
        return dict(row) if row else None


def pending_payments() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM payments WHERE status = 'pending' ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


# ------------------------------------------------------------- submissions
def record_submission(directory: str, site_url: str, status: str, payload: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO submissions (directory, site_url, status, payload, submitted_at)
               VALUES (?, ?, ?, ?, ?)""",
            (directory, site_url, status, json.dumps(payload), _now()),
        )


def recent_submissions(limit: int = 25) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
