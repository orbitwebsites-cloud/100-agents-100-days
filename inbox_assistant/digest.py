"""Proactive digest — the piece that makes this an agent, not a search box.

Q&A only fires when you ask. This scans the store for things you'd want to
know about even if you never asked — a passport expiring soon, a bill due, a
package out for delivery — and pushes a Telegram message on its own. Each
matching email is only ever alerted on once (see `alerted` in store.py).
"""

from datetime import date, timedelta

from . import config, store
from .connectors import telegram


def _format_line(email: dict) -> str:
    bits = [email["subject"]]
    if email["category"] == "travel-doc" and email.get("expiry_date"):
        bits = [f"{email.get('entity') or 'Document'} expires {email['expiry_date']}"]
    elif email["category"] == "bill":
        amount = f"${email['amount']}" if email.get("amount") is not None else "amount due"
        bits = [f"{email.get('entity') or 'Bill'} — {amount} due"]
    elif email["category"] == "delivery":
        bits = [f"{email.get('entity') or 'Package'} out for delivery" + (
            f" (tracking {email['tracking_number']})" if email.get("tracking_number") else ""
        )]
    return "• " + bits[0]


def build_digest(lookahead_days: int | None = None, today: date | None = None) -> tuple[str | None, list[str]]:
    """Return (message, message_ids) for anything new worth a proactive nudge.

    message is None if there's nothing to alert on. message_ids is the list
    of emails the caller should mark as alerted once the message is sent.
    """
    lookahead_days = config.DIGEST_LOOKAHEAD_DAYS if lookahead_days is None else lookahead_days
    today = today or date.today()
    cutoff = (today + timedelta(days=lookahead_days)).isoformat()

    candidates = store.digest_candidates(cutoff_date=cutoff)
    if not candidates:
        return None, []

    lines = [_format_line(e) for e in candidates]
    header = "📋 Heads up — from your inbox:"
    message = header + "\n" + "\n".join(lines)
    return message, [e["message_id"] for e in candidates]


def run_digest_once(lookahead_days: int | None = None) -> str | None:
    """Build the digest, push it via Telegram if non-empty, and mark those emails alerted.

    Returns the message that was sent (or None if there was nothing to say).
    """
    message, message_ids = build_digest(lookahead_days=lookahead_days)
    if not message:
        return None

    telegram.send_message(message)
    for message_id in message_ids:
        store.mark_alerted(message_id)
    return message
