"""Transactional email goes out through Brevo when a key is set, and never crashes the caller."""

from __future__ import annotations

import dataclasses

import pytest
import requests

from hundred.server import emailer


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self._body = body
        self.content = b"{}" if body else b""
        self.text = str(body)

    def json(self):
        return self._body


@pytest.fixture
def configure(monkeypatch):
    def _configure(**overrides):
        monkeypatch.setattr(emailer, "settings", dataclasses.replace(emailer.settings, **overrides))

    return _configure


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json})
        return FakeResponse(201, {"messageId": "<abc@smtp-relay.brevo.com>"})

    monkeypatch.setattr(emailer.requests, "post", fake_post)
    return calls


def test_no_key_is_dry_run(configure, sent):
    configure(brevo_api_key="", resend_api_key="")
    assert emailer.send("a@b.co", "hi", "body") == "email:dry-run"
    assert sent == []


def test_brevo_payload(configure, sent):
    configure(brevo_api_key="xkeysib-test", resend_api_key="re_x",
              email_from="Hundred <alex@orbitboyzz.me>", support_email="help@orbitboyzz.me")
    assert emailer.send("buyer@example.com", "Your agents are ready", "text") == "<abc@smtp-relay.brevo.com>"
    call = sent[0]
    assert call["url"] == emailer.BREVO_URL
    assert call["headers"]["api-key"] == "xkeysib-test"
    assert call["json"] == {
        "sender": {"name": "Hundred", "email": "alex@orbitboyzz.me"},
        "to": [{"email": "buyer@example.com"}],
        "subject": "Your agents are ready",
        "textContent": "text",
        "replyTo": {"email": "help@orbitboyzz.me"},
    }


def test_bare_sender_address_gets_brand_name(configure, sent):
    configure(brevo_api_key="k", email_from="alex@orbitboyzz.me")
    emailer.send("a@b.co", "s", "t")
    assert sent[0]["json"]["sender"] == {"name": emailer.settings.brand, "email": "alex@orbitboyzz.me"}


def test_resend_still_works_without_brevo(configure, sent):
    configure(brevo_api_key="", resend_api_key="re_x")
    emailer.send("a@b.co", "s", "t")
    assert sent[0]["url"] == emailer.RESEND_URL and sent[0]["headers"]["Authorization"] == "Bearer re_x"


def test_rejected_and_unreachable_sends_fail_softly(configure, monkeypatch):
    configure(brevo_api_key="k")
    monkeypatch.setattr(emailer.requests, "post", lambda *a, **k: FakeResponse(401, {"code": "unauthorized"}))
    assert emailer.send("a@b.co", "s", "t") == "email:failed"

    def down(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(emailer.requests, "post", down)
    assert emailer.send("a@b.co", "s", "t") == "email:failed"


def test_sign_in_code_email(configure, sent):
    configure(brevo_api_key="k")
    emailer.send_sign_in_code("a@b.co", "123456", "Claude")
    body = sent[0]["json"]
    assert body["subject"].startswith("123456") and "Claude" in body["textContent"]
