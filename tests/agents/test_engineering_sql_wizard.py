"""SQL Wizard tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("sql-wizard")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


Q = """select u.id, count(*) as n from users u left join orders o on o.user_id = u.id
where lower(u.email) like '%@acme.com' and o.status = 'paid' and u.id not in (select user_id from bans where x = 1)
group by u.id order by n desc limit 10 offset 20000;"""


def test_format_sql_layout():
    out = call("format_sql", sql=Q)
    f = out["formatted"]
    lines = f.splitlines()
    assert lines[0] == "SELECT"
    assert lines[1] == "    u.id,"
    assert lines[2] == "    COUNT(*) AS n"
    assert "LEFT JOIN orders o\n    ON o.user_id = u.id" in f
    assert "WHERE LOWER(u.email) LIKE '%@acme.com'\n    AND o.status = 'paid'" in f
    assert "    AND u.id NOT IN (\n        SELECT\n            user_id\n        FROM bans" in f
    assert f.endswith("OFFSET 20000;")
    assert out["statements"] == 1


def test_format_sql_lowercase_and_strings_untouched():
    out = call("format_sql", sql="SELECT 'KEEP Me' AS x FROM T WHERE A = 1", keyword_case="lower")
    assert "select" in out["formatted"] and "'KEEP Me'" in out["formatted"] and "from T" in out["formatted"]


def test_format_sql_rejects_unterminated_string():
    with pytest.raises(ToolError):
        call("format_sql", sql="select 'oops from t")


def test_explain_structure_counts():
    s = call("explain_structure", sql=Q)["statements"][0]
    assert s["statement_type"] == "SELECT"
    assert s["join_count"] == 1 and s["joins"][0]["type"] == "LEFT JOIN" and s["joins"][0]["on"] == "o.user_id = u.id"
    assert s["subqueries"] == 1 and s["max_subquery_depth"] == 1
    assert s["select_items"] == 2
    assert s["aggregates"] == {"COUNT": 1}
    assert s["has_group_by"] and s["has_limit"] and s["has_order_by"]
    assert s["select_star"] is False
    assert {"table": "users", "alias": "u"} in s["tables"]
    assert s["grain_hint"] == "one row per GROUP BY key"


def test_explain_structure_ctes():
    s = call("explain_structure", sql="with a as (select 1 as x), b as (select x from a) select * from b")["statements"][0]
    assert s["ctes"] == ["a", "b"]
    assert s["select_star"] is True


def test_explain_structure_rejects_empty():
    with pytest.raises(ToolError):
        call("explain_structure", sql="-- nothing here")


def test_lint_sql_finds_classic_traps():
    out = call("lint_sql", sql=Q)
    rules = [f["rule"] for f in out["findings"]]
    # lower(u.email) is lowercase in the query — it must still be caught as non-sargable
    assert rules[:4] == ["not-in-subquery", "leading-wildcard", "non-sargable", "left-join-cancelled"]
    assert "deep-offset" in rules
    assert out["score"] == 12
    assert out["verdict"].startswith("Likely wrong or slow")


def test_lint_sql_critical_delete_without_where():
    out = call("lint_sql", sql="DELETE FROM users; SELECT a FROM t WHERE b = NULL LIMIT 5")
    rules = {f["rule"] for f in out["findings"]}
    assert {"no-where-on-write", "null-equality", "limit-without-order"} <= rules
    assert out["counts"]["critical"] == 2
    assert out["verdict"].startswith("Do not run")


def test_lint_sql_clean_query():
    out = call("lint_sql", sql="SELECT id, name FROM users WHERE id = 5")
    assert out["findings"] == [] and out["score"] == 100


def test_lint_sql_rejects_empty():
    with pytest.raises(ToolError):
        call("lint_sql", sql="   ")


def test_suggest_indexes_esr_order():
    out = call("suggest_indexes", sql="select * from events where user_id = 1 and kind = 'click' and ts >= '2026-01-01' order by ts desc")
    assert out["indexes"][0]["columns"] == ["user_id", "kind", "ts"]
    assert out["indexes"][0]["statement"] == "CREATE INDEX CONCURRENTLY idx_events_user_id_kind_ts ON events (user_id, kind, ts);"
    out2 = call("suggest_indexes", sql=Q, dialect="mysql")
    stmts = [i["statement"] for i in out2["indexes"]]
    assert "CREATE INDEX idx_orders_status_user_id ON orders (status, user_id);" in stmts
    assert any("function-wrapped" in n for n in out2["notes"])


def test_suggest_indexes_rejects_multi_statement():
    with pytest.raises(ToolError):
        call("suggest_indexes", sql="select 1 from a; select 2 from b")
