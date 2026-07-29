"""Tests for the Gmail connector — pure message parsing (no API calls needed)
plus the dry-run/live branches of fetch_recent/archive_message.

The googleapiclient/google-auth-oauthlib packages are never imported here:
dry-run tests hit config.gmail_live() == False (the default, no token file),
and "live" tests monkeypatch gmail._get_service / gmail.config.gmail_live
directly instead of touching real Google API client code.
"""

import base64
import json

import pytest

from inbox_assistant import config
from inbox_assistant.connectors import gmail


def _b64url(text: str) -> str:
    """Base64url-encode without padding, matching Gmail API's own encoding."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def _raw_message(**overrides):
    base = {
        "id": "18abcd1234",
        "internalDate": "1751328000000",  # 2025-07-01T00:00:00Z
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "Amazon <ship-confirm@amazon.com>"},
                {"name": "Subject", "value": "Your order has shipped"},
            ],
            "body": {"data": _b64url("Your package is on the way.")},
        },
    }
    base.update(overrides)
    return base


# ── pure parsing ──────────────────────────────────────────────────────────


def test_header_is_case_insensitive():
    headers = [{"name": "Subject", "value": "Hello"}]
    assert gmail._header(headers, "subject") == "Hello"


def test_header_missing_returns_empty_string():
    assert gmail._header([], "Subject") == ""


def test_decode_part_handles_missing_padding():
    encoded = _b64url("hello world")
    assert gmail._decode_part(encoded) == "hello world"


def test_extract_body_simple_text_plain():
    payload = {"mimeType": "text/plain", "body": {"data": _b64url("plain body text")}}
    assert gmail._extract_body(payload) == "plain body text"


def test_extract_body_multipart_prefers_text_plain():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": _b64url("<p>html</p>")}},
            {"mimeType": "text/plain", "body": {"data": _b64url("plain wins")}},
        ],
    }
    assert gmail._extract_body(payload) == "plain wins"


def test_extract_body_nested_multipart():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "text/plain", "body": {"data": _b64url("nested body")}}],
            }
        ],
    }
    assert gmail._extract_body(payload) == "nested body"


def test_extract_body_no_text_returns_empty_string():
    payload = {"mimeType": "multipart/mixed", "parts": [{"mimeType": "image/png", "body": {}}]}
    assert gmail._extract_body(payload) == ""


def test_parse_message_extracts_expected_fields():
    parsed = gmail.parse_message(_raw_message())
    assert parsed["message_id"] == "18abcd1234"
    assert parsed["from"] == "ship-confirm@amazon.com"
    assert parsed["subject"] == "Your order has shipped"
    assert parsed["body"] == "Your package is on the way."
    assert parsed["received_at"].startswith("2025-06-30") or parsed["received_at"].startswith("2025-07-01")


def test_parse_message_falls_back_to_raw_from_header_without_angle_brackets():
    raw = _raw_message()
    raw["payload"]["headers"] = [{"name": "From", "value": "not-an-email-address"}]
    parsed = gmail.parse_message(raw)
    assert parsed["from"] == "not-an-email-address"


# ── dry-run (default: no GMAIL_TOKEN_FILE) ───────────────────────────────


def test_fetch_recent_dry_run_reads_sample_inbox(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GMAIL_TOKEN_FILE", tmp_path / "no-token-here.json")
    monkeypatch.setattr(config, "GMAIL_TOKEN", None)
    sample = json.loads(config.SAMPLE_INBOX.read_text(encoding="utf-8"))
    result = gmail.fetch_recent(limit=2)
    assert result == sample[:2]


def test_archive_message_dry_run_does_not_call_api(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GMAIL_TOKEN_FILE", tmp_path / "no-token-here.json")
    monkeypatch.setattr(config, "GMAIL_TOKEN", None)
    result = gmail.archive_message("amz-001")
    assert result == "gmail:dry-run://archived/amz-001"


def test_authorize_raises_when_credentials_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GMAIL_CREDENTIALS_FILE", tmp_path / "missing_credentials.json")
    with pytest.raises(FileNotFoundError):
        gmail.authorize()


# ── live path (mocked service, no real Google API client involved) ──────


class _FakeMessagesResource:
    def __init__(self, listing: dict, get_by_id: dict):
        self._listing = listing
        self._get_by_id = get_by_id
        self.modify_calls = []

    def list(self, **kwargs):
        return _FakeExecutable(self._listing)

    def get(self, id, **kwargs):
        return _FakeExecutable(self._get_by_id[id])

    def modify(self, id, body, **kwargs):
        self.modify_calls.append((id, body))
        return _FakeExecutable({})


class _FakeExecutable:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeUsers:
    def __init__(self, messages_resource):
        self._messages = messages_resource

    def messages(self):
        return self._messages


class _FakeService:
    def __init__(self, messages_resource):
        self._users = _FakeUsers(messages_resource)

    def users(self):
        return self._users


def test_fetch_recent_live_uses_service_and_parses_messages(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_TOKEN", "fake-token")  # gmail_live() -> True
    raw = _raw_message()
    messages = _FakeMessagesResource(listing={"messages": [{"id": raw["id"]}]}, get_by_id={raw["id"]: raw})
    monkeypatch.setattr(gmail, "_get_service", lambda: _FakeService(messages))

    result = gmail.fetch_recent(limit=10)

    assert len(result) == 1
    assert result[0]["message_id"] == raw["id"]
    assert result[0]["subject"] == "Your order has shipped"


def test_archive_message_live_calls_modify_with_remove_inbox_label(monkeypatch):
    monkeypatch.setattr(config, "GMAIL_TOKEN", "fake-token")
    messages = _FakeMessagesResource(listing={}, get_by_id={})
    monkeypatch.setattr(gmail, "_get_service", lambda: _FakeService(messages))

    result = gmail.archive_message("m1")

    assert result == "gmail://archived/m1"
    assert messages.modify_calls == [("m1", {"removeLabelIds": ["INBOX"]})]
