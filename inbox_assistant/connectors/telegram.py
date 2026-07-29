"""Telegram connector — the real trigger.

Meeting Ops fires when a meeting ends; Inbox Assistant fires when you message
it on Telegram, and can also push a message on its own (see digest.py) —
without you asking first. Dry-run without a bot token: send_message() prints
instead of calling the API, and get_updates() returns nothing to poll.
"""

import requests

from .. import config

API_ROOT = "https://api.telegram.org"
REQUEST_TIMEOUT = 35  # a little above the long-poll timeout we pass to getUpdates


def send_message(text: str, chat_id: str | None = None) -> str:
    """Send a message via the bot. Returns a status string."""
    chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not config.telegram_live():
        print(f"   📨 [Telegram · DRY-RUN] would send to {chat_id or '(no chat id)'}: {text[:200]!r}")
        return "telegram:dry-run://sent"

    resp = requests.post(
        f"{API_ROOT}/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return "telegram://sent"


def get_updates(offset: int | None = None, timeout: int = 30) -> list[dict]:
    """Long-poll for new messages. Returns Telegram's raw `result` list."""
    if not config.telegram_live():
        return []

    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(
        f"{API_ROOT}/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates",
        params=params,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])
