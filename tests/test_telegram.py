"""Tests for the Telegram connector — dry-run by default (no bot token),
real HTTP calls mocked out for the live path (no network in tests).
"""

from inbox_assistant import config
from inbox_assistant.connectors import telegram


def test_send_message_dry_run_by_default(capsys):
    result = telegram.send_message("hello", chat_id="123")
    assert result == "telegram:dry-run://sent"
    assert "DRY-RUN" in capsys.readouterr().out


def test_get_updates_dry_run_returns_empty_list():
    assert telegram.get_updates() == []


def test_send_message_live_posts_to_telegram_api(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "999")

    calls = []

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return _FakeResponse()

    monkeypatch.setattr(telegram.requests, "post", fake_post)

    result = telegram.send_message("hi there")

    assert result == "telegram://sent"
    assert len(calls) == 1
    url, payload, _ = calls[0]
    assert url == "https://api.telegram.org/botfake-token/sendMessage"
    assert payload == {"chat_id": "999", "text": "hi there"}


def test_send_message_live_uses_explicit_chat_id_over_default(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "999")

    calls = []

    class _FakeResponse:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        telegram.requests, "post",
        lambda url, json, timeout: calls.append(json) or _FakeResponse(),
    )

    telegram.send_message("hi", chat_id="42")

    assert calls[0]["chat_id"] == "42"


def test_get_updates_live_passes_offset_and_returns_results(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "fake-token")

    calls = []

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": [{"update_id": 1, "message": {"text": "hi"}}]}

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return _FakeResponse()

    monkeypatch.setattr(telegram.requests, "get", fake_get)

    result = telegram.get_updates(offset=5, timeout=10)

    assert result == [{"update_id": 1, "message": {"text": "hi"}}]
    url, params = calls[0]
    assert url == "https://api.telegram.org/botfake-token/getUpdates"
    assert params == {"timeout": 10, "offset": 5}
