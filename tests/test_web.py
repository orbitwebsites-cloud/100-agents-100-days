"""Tests for inbox_assistant.web — the Flask chat UI/API.

The backend (Anthropic/Cerebras agent) is always faked via monkeypatching
web._backend, so nothing here ever makes a network call. web.py is being
hardened concurrently (security headers, length caps) elsewhere, so these
tests deliberately avoid asserting header absence or exercising the exact
length-cap boundary — just the core request/response contract.
"""

import pytest

from inbox_assistant import web


@pytest.fixture
def client():
    # CSRF is exercised by the real browser flow (meta tag → X-CSRFToken header);
    # here we disable it so the API contract can be tested directly.
    web.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return web.app.test_client()


class FakeBackend:
    def __init__(self, answer="canned answer", raise_error=False):
        self.answer = answer
        self.raise_error = raise_error
        self.calls = []

    def ask(self, question, history=None):
        self.calls.append((question, history))
        if self.raise_error:
            raise RuntimeError("boom")
        return self.answer


def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_ask_empty_question_returns_400(client):
    resp = client.post("/api/ask", json={"question": ""})
    assert resp.status_code == 400
    assert resp.get_json()["answer"]


def test_ask_whitespace_only_question_returns_400(client):
    resp = client.post("/api/ask", json={"question": "   "})
    assert resp.status_code == 400


def test_ask_missing_body_returns_400(client):
    resp = client.post("/api/ask")
    assert resp.status_code == 400


def test_ask_no_backend_configured_returns_200_with_notice(client, monkeypatch):
    monkeypatch.setattr(web, "_backend", lambda: (None, None, None))
    resp = client.post("/api/ask", json={"question": "hi"})
    assert resp.status_code == 200
    assert "No model key set" in resp.get_json()["answer"]


def test_ask_happy_path_returns_backend_answer(client, monkeypatch):
    fake = FakeBackend(answer="Your package is out for delivery.")
    monkeypatch.setattr(web, "_backend", lambda: (fake, "fake-model", "fake-provider"))

    resp = client.post("/api/ask", json={"question": "where is my package?"})

    assert resp.status_code == 200
    assert resp.get_json()["answer"] == "Your package is out for delivery."
    assert fake.calls[0][0] == "where is my package?"


def test_ask_passes_history_to_backend(client, monkeypatch):
    fake = FakeBackend(answer="ok")
    monkeypatch.setattr(web, "_backend", lambda: (fake, "fake-model", "fake-provider"))

    history = [{"role": "user", "content": "earlier q"}, {"role": "assistant", "content": "earlier a"}]
    resp = client.post("/api/ask", json={"question": "follow up", "history": history})

    assert resp.status_code == 200
    _, passed_history = fake.calls[0]
    assert passed_history == history


def test_ask_backend_exception_returns_500(client, monkeypatch):
    fake = FakeBackend(raise_error=True)
    monkeypatch.setattr(web, "_backend", lambda: (fake, "fake-model", "fake-provider"))

    resp = client.post("/api/ask", json={"question": "hi"})

    assert resp.status_code == 500
    assert "went wrong" in resp.get_json()["answer"].lower()


def test_ask_no_answer_falls_back_to_placeholder(client, monkeypatch):
    fake = FakeBackend(answer="")
    monkeypatch.setattr(web, "_backend", lambda: (fake, "fake-model", "fake-provider"))

    resp = client.post("/api/ask", json={"question": "hi"})

    assert resp.status_code == 200
    assert resp.get_json()["answer"] == "(no answer)"


def test_clean_history_drops_malformed_entries():
    raw = [
        {"role": "user", "content": "good"},
        {"role": "system", "content": "dropped - bad role"},
        {"role": "assistant", "content": 12345},  # dropped - not a string
        "not even a dict",
        {"role": "assistant", "content": "also good"},
    ]
    cleaned = web._clean_history(raw)
    assert cleaned == [
        {"role": "user", "content": "good"},
        {"role": "assistant", "content": "also good"},
    ]


def test_clean_history_non_list_returns_empty():
    assert web._clean_history("not a list") == []
    assert web._clean_history(None) == []
