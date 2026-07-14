"""Tests for inbox_assistant.store — plain sqlite CRUD/search, no mocking needed.

Every test passes db_path explicitly (tmp_path-based) so nothing ever touches
the repo's real inbox.db.
"""

from inbox_assistant import store

from conftest import SAMPLE_RECORDS


def _record(**overrides):
    base = dict(SAMPLE_RECORDS[0])
    base.update(overrides)
    return base


def test_upsert_then_get_by_id(db_path):
    store.upsert_email(_record(), db_path=db_path)
    got = store.get_by_id("amz-001", db_path=db_path)
    assert got is not None
    assert got["message_id"] == "amz-001"
    assert got["subject"] == "Your Amazon.com order has shipped"
    assert got["archived"] == 0


def test_get_by_id_missing_returns_none(db_path):
    store.upsert_email(_record(), db_path=db_path)
    assert store.get_by_id("does-not-exist", db_path=db_path) is None


def test_upsert_conflict_updates_extracted_fields_only(db_path):
    store.upsert_email(_record(category="order", status="shipped"), db_path=db_path)
    # Re-upsert same message_id: subject/body/sender/received_at are the raw
    # content and are NOT in the ON CONFLICT DO UPDATE SET clause, only the
    # extracted fields are.
    store.upsert_email(
        _record(subject="a different subject", category="delivery", status="out for delivery"),
        db_path=db_path,
    )
    got = store.get_by_id("amz-001", db_path=db_path)
    assert got["category"] == "delivery"
    assert got["status"] == "out for delivery"
    assert got["subject"] == "Your Amazon.com order has shipped"  # unchanged


def test_upsert_does_not_reset_archived_flag(db_path):
    store.upsert_email(_record(), db_path=db_path)
    store.archive("amz-001", db_path=db_path)
    store.upsert_email(_record(status="delivered"), db_path=db_path)
    got = store.get_by_id("amz-001", db_path=db_path)
    assert got["status"] == "delivered"
    assert got["archived"] == 1


def test_search_by_query_matches_subject_body_entity(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    hits = store.search(query="Amazon", db_path=db_path)
    assert {h["message_id"] for h in hits} == {"amz-001"}

    hits = store.search(query="passport", db_path=db_path)
    assert {h["message_id"] for h in hits} == {"gov-001"}


def test_search_by_category(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    hits = store.search(category="bill", db_path=db_path)
    assert {h["message_id"] for h in hits} == {"bill-001"}


def test_search_no_filters_returns_all_non_archived(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    hits = store.search(db_path=db_path)
    assert len(hits) == len(SAMPLE_RECORDS)


def test_search_excludes_archived_by_default(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    store.archive("promo-001", db_path=db_path)

    hits = store.search(db_path=db_path)
    assert "promo-001" not in {h["message_id"] for h in hits}

    hits_all = store.search(include_archived=True, db_path=db_path)
    assert "promo-001" in {h["message_id"] for h in hits_all}


def test_search_respects_limit(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    hits = store.search(limit=2, db_path=db_path)
    assert len(hits) == 2


def test_search_orders_newest_first(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    hits = store.search(limit=len(SAMPLE_RECORDS), db_path=db_path)
    received = [h["received_at"] for h in hits]
    assert received == sorted(received, reverse=True)


def test_archive_known_id_returns_true(db_path):
    store.upsert_email(_record(), db_path=db_path)
    assert store.archive("amz-001", db_path=db_path) is True
    got = store.get_by_id("amz-001", db_path=db_path)
    assert got["archived"] == 1


def test_archive_unknown_id_returns_false(db_path):
    store.upsert_email(_record(), db_path=db_path)
    assert store.archive("no-such-id", db_path=db_path) is False


def test_has_message_true_after_upsert(db_path):
    store.upsert_email(_record(), db_path=db_path)
    assert store.has_message("amz-001", db_path=db_path) is True


def test_has_message_false_when_absent(db_path):
    store.upsert_email(_record(), db_path=db_path)
    assert store.has_message("no-such-id", db_path=db_path) is False


def test_search_limit_clamped_to_upper_bound(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    # Requesting an absurd limit should not error, and should clamp to 100.
    hits = store.search(limit=10_000, db_path=db_path)
    assert len(hits) == len(SAMPLE_RECORDS)


def test_search_limit_clamped_to_lower_bound(db_path):
    for rec in SAMPLE_RECORDS:
        store.upsert_email(rec, db_path=db_path)
    # limit=0 (or negative) should clamp up to at least 1, not return everything/nothing weird.
    hits = store.search(limit=0, db_path=db_path)
    assert len(hits) == 1
