"""Local email store — a stand-in for the Supabase/pgvector table in prod.

Same schema as the MVP plan's `emails` table, minus the vector column: for a
single-user local demo, keyword search over the extracted fields + body is
plenty. Swapping this module for a Supabase-backed one (structured columns +
pgvector) is the multi-user step, not a rewrite of the agent or its tools.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    message_id      TEXT PRIMARY KEY,
    received_at     TEXT NOT NULL,
    sender          TEXT NOT NULL,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    category        TEXT,
    entity          TEXT,
    order_id        TEXT,
    tracking_number TEXT,
    expiry_date     TEXT,
    amount          REAL,
    status          TEXT,
    archived        INTEGER NOT NULL DEFAULT 0,
    alerted         INTEGER NOT NULL DEFAULT 0
);
"""


@contextmanager
def _connect(db_path: Path | None = None):
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(SCHEMA)
        try:
            conn.execute("ALTER TABLE emails ADD COLUMN alerted INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # already migrated
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_email(record: dict, db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO emails (message_id, received_at, sender, subject, body,
                                 category, entity, order_id, tracking_number,
                                 expiry_date, amount, status, archived)
            VALUES (:message_id, :received_at, :sender, :subject, :body,
                     :category, :entity, :order_id, :tracking_number,
                     :expiry_date, :amount, :status, 0)
            ON CONFLICT(message_id) DO UPDATE SET
                category=excluded.category, entity=excluded.entity,
                order_id=excluded.order_id, tracking_number=excluded.tracking_number,
                expiry_date=excluded.expiry_date, amount=excluded.amount,
                status=excluded.status
            """,
            record,
        )


def has_message(message_id: str, db_path: Path | None = None) -> bool:
    """True if message_id is already in the store (used to skip re-ingesting)."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM emails WHERE message_id = ?", (message_id,)).fetchone()
    return row is not None


def search(query: str = "", category: str = "", include_archived: bool = False,
           limit: int = 10, db_path: Path | None = None) -> list[dict]:
    """Keyword search over subject/body/entity, newest first."""
    limit = max(1, min(int(limit), 100))
    clauses, params = [], {}
    if query:
        clauses.append("(subject LIKE :q OR body LIKE :q OR entity LIKE :q)")
        params["q"] = f"%{query}%"
    if category:
        clauses.append("category = :category")
        params["category"] = category
    if not include_archived:
        clauses.append("archived = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM emails {where} ORDER BY received_at DESC LIMIT :limit",
            {**params, "limit": limit},
        ).fetchall()
    return [dict(r) for r in rows]


def archive(message_id: str, db_path: Path | None = None) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute("UPDATE emails SET archived = 1 WHERE message_id = ?", (message_id,))
        return cur.rowcount > 0


def get_by_id(message_id: str, db_path: Path | None = None) -> dict | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM emails WHERE message_id = ?", (message_id,)).fetchone()
    return dict(row) if row else None


def mark_alerted(message_id: str, db_path: Path | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute("UPDATE emails SET alerted = 1 WHERE message_id = ?", (message_id,))


def digest_candidates(cutoff_date: str, db_path: Path | None = None) -> list[dict]:
    """Not-yet-alerted, not-archived rows worth a proactive nudge.

    Covers: travel docs expiring on/before `cutoff_date` (an ISO date),
    bills due, and packages out for delivery.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM emails
            WHERE archived = 0 AND alerted = 0 AND (
                (category = 'travel-doc' AND expiry_date IS NOT NULL AND expiry_date <= :cutoff)
                OR (category = 'bill' AND status = 'due')
                OR (category = 'delivery' AND status = 'out for delivery')
            )
            ORDER BY received_at DESC
            """,
            {"cutoff": cutoff_date},
        ).fetchall()
    return [dict(r) for r in rows]
