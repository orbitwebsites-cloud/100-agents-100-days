"""Tests for the proactive digest — the piece that pushes an alert without
being asked. Uses the seeded_db fixture (patches config.DB_PATH) so
digest.build_digest()/run_digest_once() resolve against the tmp db.
"""

from datetime import date

from inbox_assistant import config, digest


def test_build_digest_empty_store_returns_nothing(patched_db_path):
    message, ids = digest.build_digest()
    assert message is None
    assert ids == []


def test_build_digest_flags_bill_due_and_delivery_but_not_far_off_expiry(seeded_db):
    # gov-001 expires 2026-11-03; "today" here is well before the lookahead window.
    message, ids = digest.build_digest(lookahead_days=3, today=date(2026, 7, 29))

    assert message is not None
    assert "City Power" in message  # bill-001
    assert "UPS" in message  # ups-001, out for delivery
    assert "Passport Office" not in message  # gov-001 too far out
    assert set(ids) == {"bill-001", "ups-001"}


def test_build_digest_includes_expiring_doc_within_lookahead(seeded_db):
    message, ids = digest.build_digest(lookahead_days=200, today=date(2026, 7, 29))

    assert "Passport Office" in message
    assert "2026-11-03" in message
    assert "gov-001" in ids


def test_build_digest_excludes_shipped_order_and_promo(seeded_db):
    message, _ids = digest.build_digest(lookahead_days=200, today=date(2026, 7, 29))
    assert "50% off" not in message  # promo-001
    assert "USB-C Hub" not in message  # amz-001 is category=order/shipped, not a digest candidate


def test_build_digest_excludes_archived_emails(seeded_db):
    from inbox_assistant import store
    store.archive("bill-001")

    message, ids = digest.build_digest(lookahead_days=3, today=date(2026, 7, 29))

    assert "bill-001" not in ids
    assert "City Power" not in (message or "")


def test_run_digest_once_marks_emails_alerted_and_dedupes(seeded_db, monkeypatch):
    sent = []
    monkeypatch.setattr(digest.telegram, "send_message", lambda text, chat_id=None: sent.append(text))

    first = digest.run_digest_once(lookahead_days=3)
    assert first is not None
    assert len(sent) == 1

    # Second run: same candidates were already marked alerted, so nothing new to send.
    second = digest.run_digest_once(lookahead_days=3)
    assert second is None
    assert len(sent) == 1


def test_run_digest_once_returns_none_and_sends_nothing_when_store_empty(patched_db_path, monkeypatch):
    sent = []
    monkeypatch.setattr(digest.telegram, "send_message", lambda text, chat_id=None: sent.append(text))

    result = digest.run_digest_once()

    assert result is None
    assert sent == []


def test_build_digest_default_lookahead_comes_from_config(seeded_db, monkeypatch):
    monkeypatch.setattr(config, "DIGEST_LOOKAHEAD_DAYS", 200)
    message, ids = digest.build_digest(today=date(2026, 7, 29))
    assert "gov-001" in ids
    assert message is not None
