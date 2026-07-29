"""Tests for telegram_bot.handle_update — the per-message dispatch used by
the long-poll loop. No real HTTP or model calls: telegram.send_message stays
in dry-run (no bot token in tests) and the backend is a stub.
"""

from inbox_assistant import config, telegram_bot


class _FakeBackend:
    def __init__(self, answer="the answer"):
        self.answer = answer
        self.calls = []

    def ask(self, question, history=None):
        self.calls.append((question, history))
        return self.answer


def test_handle_update_ignores_message_from_unconfigured_chat(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", None)
    backend = _FakeBackend()
    update = {"message": {"chat": {"id": 123}, "text": "hi"}}

    result = telegram_bot.handle_update(update, backend, history=[])

    assert result is None
    assert backend.calls == []


def test_handle_update_ignores_message_from_other_chat(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "999")
    backend = _FakeBackend()
    update = {"message": {"chat": {"id": 123}, "text": "hi"}}

    result = telegram_bot.handle_update(update, backend, history=[])

    assert result is None
    assert backend.calls == []


def test_handle_update_answers_allowed_chat_and_updates_history(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "123")
    backend = _FakeBackend(answer="here's your answer")
    history = []
    update = {"message": {"chat": {"id": 123}, "text": "what did I order?"}}

    result = telegram_bot.handle_update(update, backend, history)

    assert result == "here's your answer"
    assert backend.calls == [("what did I order?", None)]
    assert history == [
        {"role": "user", "content": "what did I order?"},
        {"role": "assistant", "content": "here's your answer"},
    ]


def test_handle_update_ignores_empty_text(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "123")
    backend = _FakeBackend()
    update = {"message": {"chat": {"id": 123}, "text": "   "}}

    result = telegram_bot.handle_update(update, backend, history=[])

    assert result is None
    assert backend.calls == []


def test_handle_update_ignores_non_message_update(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "123")
    backend = _FakeBackend()

    result = telegram_bot.handle_update({"edited_message": {}}, backend, history=[])

    assert result is None
    assert backend.calls == []


def test_handle_update_trims_history_to_max_entries(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "123")
    backend = _FakeBackend(answer="ok")
    history = [{"role": "user", "content": f"msg {i}"} for i in range(25)]
    update = {"message": {"chat": {"id": 123}, "text": "new question"}}

    telegram_bot.handle_update(update, backend, history)

    assert len(history) == telegram_bot.MAX_HISTORY_ENTRIES
    assert history[-2]["content"] == "new question"
