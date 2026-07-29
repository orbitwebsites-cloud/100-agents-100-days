"""Long-poll Telegram loop — the real trigger for Inbox Assistant.

Message the bot, it calls the same agent (search_emails / get_order_status /
archive_email) as --web and the terminal chat, and replies in the same chat.
Restricted to `TELEGRAM_CHAT_ID` by default: an unrestricted bot would answer
anyone who finds it, including the archive_email tool's side effect, so we
refuse to relay a stranger's chat instead of guessing at authorization.
"""

import logging

from . import config
from .connectors import telegram

log = logging.getLogger(__name__)

MAX_HISTORY_ENTRIES = 20


def _backend():
    prov = config.provider()
    if prov == "cerebras":
        from . import cerebras_agent as backend
        return backend
    if prov == "anthropic":
        from . import agent as backend
        return backend
    return None


def _allowed(chat_id: str) -> bool:
    if not config.TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID is not set — refusing message from chat %s. Set it in .env.", chat_id)
        return False
    return str(chat_id) == str(config.TELEGRAM_CHAT_ID)


def handle_update(update: dict, backend, history: list[dict]) -> str | None:
    """Process one Telegram update; returns the reply text, or None if skipped."""
    message = update.get("message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()
    if not text or not chat_id:
        return None
    if not _allowed(chat_id):
        return None

    answer = backend.ask(text, history=history or None)
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": answer})
    history[:] = history[-MAX_HISTORY_ENTRIES:]
    telegram.send_message(answer or "(no answer)", chat_id=chat_id)
    return answer


def run() -> None:
    """Block, long-polling Telegram for messages and replying with the agent's answers."""
    backend = _backend()
    if backend is None:
        print("No model key set. Add CEREBRAS_API_KEY or ANTHROPIC_API_KEY to .env and restart.")
        return
    if not config.telegram_live():
        print("TELEGRAM_BOT_TOKEN is not set — nothing to poll. Add it to .env and restart.")
        return

    print("▶ Inbox Assistant is listening on Telegram. Ctrl+C to stop.")
    history: list[dict] = []
    offset = None
    try:
        while True:
            updates = telegram.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update["update_id"] + 1
                handle_update(update, backend, history)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
