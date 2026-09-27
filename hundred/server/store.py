"""License storage (SQLite).

Keys are never stored in plaintext: we keep a SHA-256 hash and a short display
prefix. The plaintext exists exactly twice — in the welcome email and on the
checkout success page (a one-time reveal that expires after 24h).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..plans import Entitlement

ACTIVE_STATUSES = {"active", "trialing"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    key_hash        TEXT PRIMARY KEY,
    key_prefix      TEXT NOT NULL,
    email           TEXT NOT NULL,
    status          TEXT NOT NULL,
    source          TEXT NOT NULL,          -- stripe | comp
    plan            TEXT NOT NULL,
    all_access      INTEGER NOT NULL DEFAULT 0,
    agents          TEXT NOT NULL DEFAULT '[]',
    categories      TEXT NOT NULL DEFAULT '[]',
    customer_id     TEXT,
    subscription_id TEXT UNIQUE,
    period_end      INTEGER,
    payment_failed  INTEGER NOT NULL DEFAULT 0,  -- card declined: access off until an invoice is paid
    note            TEXT,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS licenses_email ON licenses(email);
CREATE INDEX IF NOT EXISTS licenses_customer ON licenses(customer_id);

CREATE TABLE IF NOT EXISTS reveals (
    checkout_session_id TEXT PRIMARY KEY,
    plaintext_key       TEXT NOT NULL,
    expires_at          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS stripe_events (
    event_id    TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    received_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    key_hash TEXT NOT NULL,
    day      TEXT NOT NULL,
    agent    TEXT NOT NULL,
    calls    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key_hash, day, agent)
);

CREATE TABLE IF NOT EXISTS memory (
    key_hash   TEXT NOT NULL,
    name       TEXT NOT NULL,
    value      TEXT NOT NULL,          -- JSON, saved only when the customer's AI asks
    note       TEXT,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (key_hash, name)
);

CREATE TABLE IF NOT EXISTS leads (
    email      TEXT PRIMARY KEY,
    source     TEXT,
    created_at INTEGER NOT NULL
);
"""


def new_key(live: bool = True) -> str:
    return ("hnd_live_" if live else "hnd_test_") + secrets.token_urlsafe(24)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.strip().encode()).hexdigest()


@dataclass
class License:
    key_hash: str
    key_prefix: str
    email: str
    status: str
    source: str
    plan: str
    all_access: bool = False
    agents: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    customer_id: str | None = None
    subscription_id: str | None = None
    period_end: int | None = None
    payment_failed: bool = False
    note: str | None = None

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_STATUSES and not self.payment_failed

    def entitlement(self) -> Entitlement:
        if not self.active:
            return Entitlement()
        return Entitlement(all_access=self.all_access, agents=set(self.agents), categories=set(self.categories))

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "License":
        return cls(
            key_hash=row["key_hash"],
            key_prefix=row["key_prefix"],
            email=row["email"],
            status=row["status"],
            source=row["source"],
            plan=row["plan"],
            all_access=bool(row["all_access"]),
            agents=json.loads(row["agents"]),
            categories=json.loads(row["categories"]),
            customer_id=row["customer_id"],
            subscription_id=row["subscription_id"],
            period_end=row["period_end"],
            payment_failed=bool(row["payment_failed"]),
            note=row["note"],
        )


class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)

    def _exec(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._db.execute(sql, params)

    # ── licenses ──────────────────────────────────────────────
    def create_license(
        self,
        *,
        email: str,
        plan: str,
        status: str,
        source: str,
        all_access: bool = False,
        agents: list[str] | None = None,
        categories: list[str] | None = None,
        customer_id: str | None = None,
        subscription_id: str | None = None,
        period_end: int | None = None,
        note: str | None = None,
        live: bool = True,
    ) -> tuple[str, License]:
        key = new_key(live)
        now = int(time.time())
        self._exec(
            """INSERT INTO licenses (key_hash, key_prefix, email, status, source, plan, all_access, agents,
               categories, customer_id, subscription_id, period_end, note, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                hash_key(key),
                key[:14],
                email.lower().strip(),
                status,
                source,
                plan,
                int(all_access),
                json.dumps(sorted(agents or [])),
                json.dumps(sorted(categories or [])),
                customer_id,
                subscription_id,
                period_end,
                note,
                now,
                now,
            ),
        )
        lic = self.by_key(key)
        assert lic is not None
        return key, lic

    def by_key(self, key: str) -> License | None:
        if not key:
            return None
        row = self._exec("SELECT * FROM licenses WHERE key_hash=?", (hash_key(key),)).fetchone()
        return License.from_row(row) if row else None

    def by_key_hash(self, key_hash: str) -> License | None:
        row = self._exec("SELECT * FROM licenses WHERE key_hash=?", (key_hash,)).fetchone()
        return License.from_row(row) if row else None

    def by_subscription(self, subscription_id: str) -> License | None:
        row = self._exec("SELECT * FROM licenses WHERE subscription_id=?", (subscription_id,)).fetchone()
        return License.from_row(row) if row else None

    def by_email(self, email: str) -> list[License]:
        rows = self._exec("SELECT * FROM licenses WHERE email=? ORDER BY created_at DESC", (email.lower().strip(),))
        return [License.from_row(r) for r in rows.fetchall()]

    def update_subscription(self, subscription_id: str, **fields: Any) -> License | None:
        allowed = {"status", "plan", "all_access", "agents", "categories", "period_end", "email", "customer_id",
                   "payment_failed"}
        sets, params = [], []
        for k, v in fields.items():
            if k not in allowed or v is None:
                continue
            if k in ("agents", "categories"):
                v = json.dumps(sorted(v))
            if k in ("all_access", "payment_failed"):
                v = int(v)
            sets.append(f"{k}=?")
            params.append(v)
        if sets:
            sets.append("updated_at=?")
            params.append(int(time.time()))
            self._exec(f"UPDATE licenses SET {', '.join(sets)} WHERE subscription_id=?", (*params, subscription_id))
        return self.by_subscription(subscription_id)

    def set_status_by_key_hash(self, key_hash: str, status: str) -> None:
        self._exec("UPDATE licenses SET status=?, updated_at=? WHERE key_hash=?", (status, int(time.time()), key_hash))

    def rotate_key(self, old_key: str) -> str | None:
        lic = self.by_key(old_key)
        if lic is None:
            return None
        key = new_key(old_key.startswith("hnd_live_"))
        self._rekey(lic.key_hash, key)
        return key

    def rotate_key_for_subscription(self, subscription_id: str) -> str | None:
        lic = self.by_subscription(subscription_id)
        if lic is None:
            return None
        key = new_key(True)
        self._rekey(lic.key_hash, key)
        return key

    def _rekey(self, old_hash: str, key: str) -> None:
        """Swap a license to a new key, carrying its memory and usage with it."""
        new_hash = hash_key(key)
        self._exec("UPDATE licenses SET key_hash=?, key_prefix=?, updated_at=? WHERE key_hash=?",
                   (new_hash, key[:14], int(time.time()), old_hash))
        self._exec("UPDATE memory SET key_hash=? WHERE key_hash=?", (new_hash, old_hash))
        self._exec("UPDATE usage SET key_hash=? WHERE key_hash=?", (new_hash, old_hash))

    def count_active(self, plan: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM licenses WHERE status IN ('active','trialing')"
        params: tuple[Any, ...] = ()
        if plan:
            sql += " AND plan=?"
            params = (plan,)
        return int(self._exec(sql, params).fetchone()[0])

    def all_licenses(self) -> list[License]:
        return [License.from_row(r) for r in self._exec("SELECT * FROM licenses ORDER BY created_at").fetchall()]

    # ── one-time key reveal after checkout ────────────────────
    def put_reveal(self, checkout_session_id: str, key: str, ttl: int = 86400) -> None:
        self._exec(
            "INSERT OR REPLACE INTO reveals VALUES (?,?,?)", (checkout_session_id, key, int(time.time()) + ttl)
        )

    def take_reveal(self, checkout_session_id: str) -> str | None:
        self._exec("DELETE FROM reveals WHERE expires_at < ?", (int(time.time()),))
        row = self._exec("SELECT plaintext_key FROM reveals WHERE checkout_session_id=?", (checkout_session_id,)).fetchone()
        if not row:
            return None
        self._exec("DELETE FROM reveals WHERE checkout_session_id=?", (checkout_session_id,))
        return row[0]

    # ── webhook idempotency ───────────────────────────────────
    def seen_event(self, event_id: str, type_: str) -> bool:
        """Record a Stripe event; True if we've processed it before."""
        cur = self._exec(
            "INSERT OR IGNORE INTO stripe_events VALUES (?,?,?)", (event_id, type_, int(time.time()))
        )
        return cur.rowcount == 0

    def forget_event(self, event_id: str) -> None:
        self._exec("DELETE FROM stripe_events WHERE event_id=?", (event_id,))

    # ── metering + leads ──────────────────────────────────────
    def record_call(self, key_hash: str, agent: str) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        self._exec(
            """INSERT INTO usage VALUES (?,?,?,1)
               ON CONFLICT(key_hash, day, agent) DO UPDATE SET calls = calls + 1""",
            (key_hash, day, agent),
        )

    def calls_today(self, key_hash: str) -> int:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        row = self._exec("SELECT COALESCE(SUM(calls),0) FROM usage WHERE key_hash=? AND day=?", (key_hash, day)).fetchone()
        return int(row[0])

    # ── memory: small JSON notes a customer's AI saves for its agents ──
    def memory_save(self, key_hash: str, name: str, value: Any, note: str = "") -> None:
        self._exec(
            """INSERT INTO memory VALUES (?,?,?,?,?)
               ON CONFLICT(key_hash, name) DO UPDATE SET value=excluded.value, note=excluded.note,
               updated_at=excluded.updated_at""",
            (key_hash, name, json.dumps(value, ensure_ascii=False), note, int(time.time())),
        )

    def memory_get(self, key_hash: str, name: str) -> dict | None:
        row = self._exec("SELECT * FROM memory WHERE key_hash=? AND name=?", (key_hash, name)).fetchone()
        if not row:
            return None
        return {"name": row["name"], "value": json.loads(row["value"]), "note": row["note"],
                "updated_at": row["updated_at"]}

    def memory_list(self, key_hash: str, prefix: str = "") -> list[dict]:
        rows = self._exec(
            "SELECT name, note, updated_at, length(value) AS size FROM memory "
            "WHERE key_hash=? AND substr(name, 1, ?) = ? ORDER BY name",
            (key_hash, len(prefix), prefix),
        ).fetchall()
        return [{"name": r["name"], "note": r["note"], "updated_at": r["updated_at"], "bytes": r["size"]} for r in rows]

    def memory_count(self, key_hash: str) -> int:
        return int(self._exec("SELECT COUNT(*) FROM memory WHERE key_hash=?", (key_hash,)).fetchone()[0])

    def memory_delete(self, key_hash: str, name: str) -> bool:
        if name == "*":
            return self._exec("DELETE FROM memory WHERE key_hash=?", (key_hash,)).rowcount > 0
        return self._exec("DELETE FROM memory WHERE key_hash=? AND name=?", (key_hash, name)).rowcount > 0

    def add_lead(self, email: str, source: str = "") -> None:
        self._exec("INSERT OR IGNORE INTO leads VALUES (?,?,?)", (email.lower().strip(), source, int(time.time())))
