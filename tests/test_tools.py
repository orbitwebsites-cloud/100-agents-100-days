"""Tests for inbox_assistant.tools — the search/order-status/archive helpers
and the dispatch() router used by the OpenAI-compatible (Cerebras) backend.

tools.py calls store.* without a db_path, so it always resolves against
config.DB_PATH at call time. The `seeded_db` fixture (from conftest) already
monkeypatches config.DB_PATH to a tmp_path db and seeds it.
"""

from inbox_assistant import tools


def test_do_search_formats_hits_with_key_fields(seeded_db):
    result = tools._do_search(query="Amazon")
    assert "amz-001" in result
    assert "112-4589621-7743108" in result  # order id
    assert "1Z999AA10123456784" in result  # tracking number
    assert "Amazon" in result


def test_do_search_no_hits_returns_message(seeded_db):
    result = tools._do_search(query="nonexistent-keyword-xyz")
    assert result == "No matching emails found."


def test_do_search_by_category(seeded_db):
    result = tools._do_search(category="bill")
    assert "bill-001" in result
    assert "amz-001" not in result


def test_do_order_status_merges_order_and_delivery_categories(seeded_db):
    result = tools._do_order_status("Amazon")
    # amz-001 is category=order, ups-001 is category=delivery — get_order_status
    # searches both categories for the same query.
    assert "amz-001" in result


def test_do_order_status_no_match(seeded_db):
    result = tools._do_order_status("totally-unrelated-query-zzz")
    assert result == "No matching emails found."


def test_do_archive_known_id(seeded_db):
    result = tools._do_archive("amz-001")
    assert "Archived:" in result
    assert "Your Amazon.com order has shipped" in result
    # And it's actually archived in the store now.
    assert tools._do_search(query="Amazon") == "No matching emails found."


def test_do_archive_unknown_id_returns_not_found_message(seeded_db):
    result = tools._do_archive("no-such-id")
    assert result == "No email found with id 'no-such-id'."


def test_dispatch_search_emails(seeded_db):
    result = tools.dispatch("search_emails", {"query": "Amazon"})
    assert "amz-001" in result


def test_dispatch_get_order_status(seeded_db):
    result = tools.dispatch("get_order_status", {"order_query": "UPS"})
    assert "ups-001" in result


def test_dispatch_archive_email(seeded_db):
    result = tools.dispatch("archive_email", {"message_id": "bill-001"})
    assert "Archived:" in result


def test_dispatch_unknown_tool_name(seeded_db):
    result = tools.dispatch("not_a_real_tool", {})
    assert result == "Error: unknown tool 'not_a_real_tool'"


def test_dispatch_search_defaults_when_args_missing(seeded_db):
    # dispatch() uses .get() with defaults, so a bare {} shouldn't blow up.
    result = tools.dispatch("search_emails", {})
    assert isinstance(result, str)


def test_openai_tools_names_match_all_tools():
    all_tool_names = {t.name for t in tools.ALL_TOOLS}
    openai_tool_names = {t["function"]["name"] for t in tools.OPENAI_TOOLS}
    assert all_tool_names == openai_tool_names == {
        "search_emails", "get_order_status", "archive_email",
    }
