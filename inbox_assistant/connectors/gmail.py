"""Gmail connector — reads the inbox, archives messages.

Dry-run in this episode, same as Meeting Ops's Gmail draft connector: without
GMAIL_TOKEN set, fetch_recent() serves the bundled sample inbox and archive()
just prints what it would do. Real Gmail OAuth (the onboarding flow in the
MVP plan) is a later episode; the ingestion worker and agent tools don't need
to change when it lands — only this file does.
"""

import json

from .. import config


def fetch_recent(limit: int = 50) -> list[dict]:
    """Return recent raw emails as dicts with from/subject/body/received_at."""
    if not config.gmail_live():
        print(f"   📬 [Gmail · DRY-RUN] reading bundled sample inbox ({config.SAMPLE_INBOX.name})")
        emails = json.loads(config.SAMPLE_INBOX.read_text(encoding="utf-8"))
        return emails[:limit]

    raise NotImplementedError(
        "Gmail OAuth isn't wired up yet — unset GMAIL_TOKEN to use the sample inbox."
    )


def archive_message(message_id: str) -> str:
    """Archive a message in Gmail (remove INBOX label). Returns a status string."""
    if not config.gmail_live():
        print(f"   🗄️  [Gmail · DRY-RUN] would archive message {message_id}")
        return f"gmail:dry-run://archived/{message_id}"

    raise NotImplementedError(
        "Gmail OAuth isn't wired up yet — unset GMAIL_TOKEN to use the sample inbox."
    )
