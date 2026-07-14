"""Tests for inbox_assistant.ingest — field extraction (fake Anthropic client)
and the end-to-end dry-run ingest into a tmp db.

extract_fields(client, sender, subject, body) takes the Anthropic client as
an explicit argument (run() constructs one client and reuses it per email),
so these tests build a fake client and pass it in directly — no need to
monkeypatch the anthropic module for the extract_fields tests.
"""

import json

from inbox_assistant import config, ingest, store


class FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeAnthropicResponse:
    def __init__(self, text):
        self.content = [FakeTextBlock(text)]


class FakeAnthropicMessages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeAnthropicResponse(self._text)


class FakeAnthropicClient:
    def __init__(self, text):
        self.messages = FakeAnthropicMessages(text)


def test_extract_fields_plain_json():
    payload = {
        "category": "order",
        "entity": "Amazon",
        "order_id": "112-4589621-7743108",
        "tracking_number": "1Z999AA10123456784",
        "expiry_date": None,
        "amount": 47.98,
        "status": "shipped",
    }
    client = FakeAnthropicClient(json.dumps(payload))

    fields = ingest.extract_fields(client, "ship-confirm@amazon.com", "Your order has shipped", "body text")

    assert fields["category"] == "order"
    assert fields["entity"] == "Amazon"
    assert fields["order_id"] == "112-4589621-7743108"
    assert fields["tracking_number"] == "1Z999AA10123456784"
    assert fields["amount"] == 47.98
    assert fields["status"] == "shipped"
    assert client.messages.calls[0]["model"] == config.MODEL


def test_extract_fields_strips_json_code_fence():
    payload = {
        "category": "bill",
        "entity": "City Power",
        "order_id": None,
        "tracking_number": None,
        "expiry_date": None,
        "amount": 84.32,
        "status": "due",
    }
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    client = FakeAnthropicClient(fenced)

    fields = ingest.extract_fields(client, "billing@citypower.com", "Your bill is ready", "body text")

    assert fields["category"] == "bill"
    assert fields["amount"] == 84.32


def test_extract_fields_invalid_json_falls_back_to_other():
    client = FakeAnthropicClient("this is not json at all")

    fields = ingest.extract_fields(client, "someone@example.com", "subject", "body")

    assert fields["category"] == "other"
    assert fields["entity"] is None
    assert fields["order_id"] is None
    assert fields["amount"] is None


def test_extract_fields_unknown_category_falls_back_to_other():
    client = FakeAnthropicClient(json.dumps({"category": "spam", "entity": "Someone"}))

    fields = ingest.extract_fields(client, "someone@example.com", "subject", "body")

    # validate_fields() only accepts KNOWN_CATEGORIES; anything else -> "other".
    assert fields["category"] == "other"
    assert fields["entity"] == "Someone"


def test_extract_fields_invalid_expiry_date_becomes_none():
    client = FakeAnthropicClient(json.dumps({"category": "bill", "expiry_date": "not-a-date"}))

    fields = ingest.extract_fields(client, "s@example.com", "subject", "body")

    assert fields["expiry_date"] is None


def test_extract_fields_non_numeric_amount_becomes_none():
    client = FakeAnthropicClient(json.dumps({"category": "bill", "amount": "lots"}))

    fields = ingest.extract_fields(client, "s@example.com", "subject", "body")

    assert fields["amount"] is None


def test_run_ingests_sample_inbox_dry_run(monkeypatch, patched_db_path):
    """End to end: gmail dry-run (GMAIL_TOKEN unset) -> extract_fields (faked) -> store."""
    monkeypatch.delenv("GMAIL_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")

    def fake_extract_fields(client, sender, subject, body):
        return {
            "category": "other",
            "entity": "Fake Entity",
            "order_id": None,
            "tracking_number": None,
            "expiry_date": None,
            "amount": None,
            "status": None,
        }

    monkeypatch.setattr(ingest, "extract_fields", fake_extract_fields)

    sample_emails = json.loads(config.SAMPLE_INBOX.read_text(encoding="utf-8"))
    count = ingest.run(limit=50)

    assert count == len(sample_emails)
    for raw in sample_emails:
        stored = store.get_by_id(raw["message_id"], db_path=patched_db_path)
        assert stored is not None
        assert stored["subject"] == raw["subject"]
        assert stored["entity"] == "Fake Entity"


def test_run_respects_limit(monkeypatch, patched_db_path):
    monkeypatch.delenv("GMAIL_TOKEN", raising=False)
    monkeypatch.setattr(
        ingest, "extract_fields",
        lambda client, sender, subject, body: {
            "category": "other", "entity": None, "order_id": None,
            "tracking_number": None, "expiry_date": None, "amount": None, "status": None,
        },
    )
    count = ingest.run(limit=2)
    assert count == 2


def test_run_skips_already_ingested_messages(monkeypatch, patched_db_path):
    monkeypatch.delenv("GMAIL_TOKEN", raising=False)
    calls = []

    def fake_extract_fields(client, sender, subject, body):
        calls.append(subject)
        return {
            "category": "other", "entity": None, "order_id": None,
            "tracking_number": None, "expiry_date": None, "amount": None, "status": None,
        }

    monkeypatch.setattr(ingest, "extract_fields", fake_extract_fields)

    first_count = ingest.run(limit=50)
    second_count = ingest.run(limit=50)

    assert first_count == len(calls)
    assert second_count == 0  # everything already in the store -> has_message() skips it
