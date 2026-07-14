"""Shared fixtures for the inbox_assistant test suite.

No network calls, no real API keys, and never a write to the repo's real
inbox.db — every test that touches storage gets its own throwaway SQLite
file under pytest's tmp_path.
"""

import sys
from pathlib import Path

import pytest

# Make sure `import inbox_assistant` / `import agent_loop` resolve to the repo
# root regardless of how pytest was invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inbox_assistant import config, store  # noqa: E402

# A small, deterministic inbox covering every category the tools/prompts
# care about (order, delivery, travel-doc, bill, other), mirroring
# samples/sample_inbox.json but with fields already "extracted".
SAMPLE_RECORDS = [
    {
        "message_id": "amz-001",
        "received_at": "2026-07-12T14:03:00",
        "sender": "ship-confirm@amazon.com",
        "subject": "Your Amazon.com order has shipped",
        "body": (
            "Your package with USB-C Hub, Wireless Mouse is on the way. "
            "Order #112-4589621-7743108. Carrier: UPS, tracking "
            "1Z999AA10123456784. Total charged: $47.98."
        ),
        "category": "order",
        "entity": "Amazon",
        "order_id": "112-4589621-7743108",
        "tracking_number": "1Z999AA10123456784",
        "expiry_date": None,
        "amount": 47.98,
        "status": "shipped",
    },
    {
        "message_id": "ups-001",
        "received_at": "2026-07-14T07:15:00",
        "sender": "mcinfo@ups.com",
        "subject": "UPS: Your package is out for delivery",
        "body": "Tracking 1Z999AA10123456784 is out for delivery today.",
        "category": "delivery",
        "entity": "UPS",
        "order_id": None,
        "tracking_number": "1Z999AA10123456784",
        "expiry_date": None,
        "amount": None,
        "status": "out for delivery",
    },
    {
        "message_id": "gov-001",
        "received_at": "2026-06-01T08:00:00",
        "sender": "no-reply@passportoffice.gov",
        "subject": "Passport renewal reminder",
        "body": "Your passport (ending in 4821) is due to expire on 2026-11-03.",
        "category": "travel-doc",
        "entity": "Passport Office",
        "order_id": None,
        "tracking_number": None,
        "expiry_date": "2026-11-03",
        "amount": None,
        "status": "expiring",
    },
    {
        "message_id": "bill-001",
        "received_at": "2026-07-10T11:00:00",
        "sender": "billing@citypower.com",
        "subject": "Your July electricity bill is ready",
        "body": "Your City Power bill for account ending 5521 is $84.32, due July 28.",
        "category": "bill",
        "entity": "City Power",
        "order_id": None,
        "tracking_number": None,
        "expiry_date": None,
        "amount": 84.32,
        "status": "due",
    },
    {
        "message_id": "promo-001",
        "received_at": "2026-07-11T16:45:00",
        "sender": "deals@retailer.com",
        "subject": "50% off everything this weekend only!!",
        "body": "Huge weekend sale, shop now for massive discounts.",
        "category": "other",
        "entity": None,
        "order_id": None,
        "tracking_number": None,
        "expiry_date": None,
        "amount": None,
        "status": None,
    },
]


@pytest.fixture
def db_path(tmp_path):
    """A throwaway sqlite path — never the repo's inbox.db."""
    return tmp_path / "test.db"


@pytest.fixture
def patched_db_path(monkeypatch, db_path):
    """Point config.DB_PATH at the tmp db.

    store.py's functions default to config.DB_PATH when called without an
    explicit db_path (that's how tools.py calls them), and store reads
    config.DB_PATH at call time — so monkeypatching this attribute is enough
    to redirect tools.py's calls into the tmp db too.
    """
    monkeypatch.setattr(config, "DB_PATH", db_path)
    return db_path


@pytest.fixture
def seeded_db(patched_db_path):
    """A tmp db pre-loaded with SAMPLE_RECORDS, with config.DB_PATH pointed at it."""
    for record in SAMPLE_RECORDS:
        store.upsert_email(record, db_path=patched_db_path)
    return patched_db_path
