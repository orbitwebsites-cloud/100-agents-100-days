"""Environment configuration and the dry-run switch.

Same pattern as Meeting Ops: every connector reads its keys from here. With
nothing but an ANTHROPIC_API_KEY (or CEREBRAS_API_KEY) set, the assistant
runs end-to-end against the bundled sample inbox — Gmail stays DRY-RUN until
OAuth is wired up (a later episode), and it prints exactly what it would do.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-opus-4-8"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")

GMAIL_TOKEN = os.getenv("GMAIL_TOKEN")  # unused until Gmail OAuth ships; dry-run otherwise

DB_PATH = Path(os.getenv("INBOX_DB_PATH", Path(__file__).parent.parent / "inbox.db"))
SAMPLE_INBOX = Path(__file__).parent.parent / "samples" / "sample_inbox.json"


def provider() -> str | None:
    """Which model backend to use, based on which key is set."""
    if CEREBRAS_API_KEY:
        return "cerebras"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return None


def gmail_live() -> bool:
    return bool(GMAIL_TOKEN)
