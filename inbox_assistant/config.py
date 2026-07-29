"""Environment configuration and the dry-run switch.

Same pattern as Meeting Ops: every connector reads its keys from here. With
nothing but an ANTHROPIC_API_KEY (or CEREBRAS_API_KEY) set, the assistant
runs end-to-end against the bundled sample inbox — Gmail and Telegram stay
DRY-RUN until you run `--gmail-auth` / set a bot token, and print exactly
what they would do.
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

# Gmail OAuth — run `python run_inbox.py --gmail-auth` once to create the
# token file from a Google Cloud OAuth client secrets file. Until that token
# file exists, the connector stays in dry-run mode against the sample inbox.
GMAIL_TOKEN = os.getenv("GMAIL_TOKEN")  # legacy override, kept for tests/back-compat
GMAIL_CREDENTIALS_FILE = Path(
    os.getenv("GMAIL_CREDENTIALS_FILE", Path(__file__).parent.parent / "credentials" / "gmail_credentials.json")
)
GMAIL_TOKEN_FILE = Path(
    os.getenv("GMAIL_TOKEN_FILE", Path(__file__).parent.parent / "credentials" / "gmail_token.json")
)
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Telegram — the real trigger. Message the bot, the agent answers; it can
# also push proactive alerts (see digest.py) without being asked first.
# TELEGRAM_BOT_TOKEN: from @BotFather.
# TELEGRAM_CHAT_ID: your own chat id (from @userinfobot) — restricts the bot
# to you; without it the bot stays in dry-run (it won't relay to strangers).
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Proactive digest — how far ahead to look for expiring docs/bills due, and
# how often --watch mode re-checks the inbox.
DIGEST_LOOKAHEAD_DAYS = int(os.getenv("DIGEST_LOOKAHEAD_DAYS", "3"))
WATCH_INTERVAL_MINUTES = int(os.getenv("WATCH_INTERVAL_MINUTES", "30"))

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
    return bool(GMAIL_TOKEN) or GMAIL_TOKEN_FILE.exists()


def telegram_live() -> bool:
    return bool(TELEGRAM_BOT_TOKEN)
