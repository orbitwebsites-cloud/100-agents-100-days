"""Ingestion — pull raw emails, extract structured fields, store them.

In prod this polls Gmail every 15-30 min (see connectors/gmail.py). For the
local demo it reads the bundled sample inbox. Either way, extraction works
the same: Claude reads the raw subject/body and pulls out the fields the
agent's tools query against (category, entity, order_id, tracking_number,
expiry_date, amount, status) — a JSON-mode call, not agentic tool use.
"""

import json
import logging
import re
from datetime import date

import anthropic

from . import config, store
from .connectors import gmail

log = logging.getLogger(__name__)

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

KNOWN_CATEGORIES = {"order", "delivery", "travel-doc", "bill", "other"}
MAX_FIELD_LEN = 500

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_json_fence(text: str) -> str:
    """Strip a ```json ... ``` (or bare ```) fence around a model reply, if present."""
    text = text.strip()
    if text.startswith("```"):
        text = _FENCE_RE.sub("", text).strip()
    return text


def _clean_str(value, max_len: int = MAX_FIELD_LEN):
    if value is None:
        return None
    value = str(value)
    return value[:max_len] if len(value) > max_len else value


def _clean_amount(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_expiry(value):
    if not value:
        return None
    value = str(value)
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def validate_fields(fields: dict) -> dict:
    """Coerce/sanitize model-extracted fields before they hit the store."""
    category = fields.get("category")
    if category not in KNOWN_CATEGORIES:
        category = "other"
    return {
        "category": category,
        "entity": _clean_str(fields.get("entity")),
        "order_id": _clean_str(fields.get("order_id")),
        "tracking_number": _clean_str(fields.get("tracking_number")),
        "expiry_date": _clean_expiry(fields.get("expiry_date")),
        "amount": _clean_amount(fields.get("amount")),
        "status": _clean_str(fields.get("status")),
    }


def extract_fields(client: anthropic.Anthropic, sender: str, subject: str, body: str) -> dict:
    resp = client.messages.create(
        model=config.MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(sender=sender, subject=subject, body=body)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = _strip_json_fence(text)
    try:
        fields = json.loads(text)
    except json.JSONDecodeError:
        fields = {}
    return validate_fields(fields)


def run(limit: int = 50) -> int:
    """Pull raw emails, extract fields, upsert into the store. Returns count ingested."""
    raw_emails = gmail.fetch_recent(limit=limit)
    client = anthropic.Anthropic()
    count = 0
    skipped = 0
    failed = 0
    for raw in raw_emails:
        if store.has_message(raw["message_id"]):
            skipped += 1
            continue
        try:
            fields = extract_fields(client, raw["from"], raw["subject"], raw["body"])
        except Exception:
            log.exception("extraction failed for message_id=%s", raw["message_id"])
            failed += 1
            continue
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
    if skipped:
        print(f"   ⏭️  skipped {skipped} already-ingested")
    if failed:
        print(f"   ⚠️  {failed} email(s) failed extraction (see logs)")
    return count
