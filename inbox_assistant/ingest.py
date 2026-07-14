"""Ingestion — pull raw emails, extract structured fields, store them.

In prod this polls Gmail every 15-30 min (see connectors/gmail.py). For the
local demo it reads the bundled sample inbox. Either way, extraction works
the same: Claude reads the raw subject/body and pulls out the fields the
agent's tools query against (category, entity, order_id, tracking_number,
expiry_date, amount, status) — a JSON-mode call, not agentic tool use.
"""

import json

import anthropic

from . import config, store
from .connectors import gmail

EXTRACT_PROMPT = """Extract structured fields from this email as JSON only, no prose.

Fields:
- category: one of "order", "delivery", "travel-doc", "bill", "other"
- entity: the sender organization, e.g. "Amazon", "UPS", "Passport Office"
- order_id: order number if present, else null
- tracking_number: shipment tracking number if present, else null
- expiry_date: an ISO date (YYYY-MM-DD) if the email mentions something expiring, else null
- amount: a number (no currency symbol) if a dollar amount is charged/due, else null
- status: a short status phrase, e.g. "shipped", "out for delivery", "due", "expiring"

From: {sender}
Subject: {subject}
Body: {body}

Respond with a single JSON object using exactly those six keys."""


def extract_fields(sender: str, subject: str, body: str) -> dict:
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=config.MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(sender=sender, subject=subject, body=body)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        fields = json.loads(text)
    except json.JSONDecodeError:
        fields = {}
    return {
        "category": fields.get("category") or "other",
        "entity": fields.get("entity"),
        "order_id": fields.get("order_id"),
        "tracking_number": fields.get("tracking_number"),
        "expiry_date": fields.get("expiry_date"),
        "amount": fields.get("amount"),
        "status": fields.get("status"),
    }


def run(limit: int = 50) -> int:
    """Pull raw emails, extract fields, upsert into the store. Returns count ingested."""
    raw_emails = gmail.fetch_recent(limit=limit)
    count = 0
    for raw in raw_emails:
        fields = extract_fields(raw["from"], raw["subject"], raw["body"])
        store.upsert_email(
            {
                "message_id": raw["message_id"],
                "received_at": raw["received_at"],
                "sender": raw["from"],
                "subject": raw["subject"],
                "body": raw["body"],
                **fields,
            }
        )
        count += 1
        print(f"   📥 {raw['subject'][:60]!r:62} → {fields['category']} / {fields.get('entity')}")
    return count
