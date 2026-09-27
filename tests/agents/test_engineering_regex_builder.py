"""Regex Builder tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("regex-builder")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


@pytest.mark.parametrize(
    "pattern,risk",
    [
        (r"^(\w+\s?)*$", "dangerous"),
        (r"(a|a)*", "dangerous"),
        (r"(\d+)+x", "dangerous"),
        (r"(\w|\d)+", "dangerous"),
        (r"\s*\s*x", "warning"),
        (r".*=.*", "warning"),
        (r"^\d{3}-\d{4}$", "safe"),
        (r"^(?P<user>[^@]+)@(?P<host>[\w.-]+)$", "safe"),
        (r"^(?:\w+(?:\s\w+)*)$", "safe"),
    ],
)
def test_check_regex_safety_levels(pattern, risk):
    assert call("check_regex_safety", pattern=pattern)["risk"] == risk


def test_check_regex_safety_rejects_bad_syntax():
    with pytest.raises(ToolError):
        call("check_regex_safety", pattern="(abc")
    with pytest.raises(ToolError):
        call("check_regex_safety", pattern="a" * 501)


def test_explain_regex_tokens_and_groups():
    out = call("explain_regex", pattern=r"^(?P<area>\(\d{3}\)|\d{3})[- ]?\d{3}-\d{4}$")
    assert out["capturing_groups"] == 1 and out["named_groups"] == ["area"]
    assert out["fully_anchored"] is True
    toks = out["tokens"]
    assert toks[0]["token"] == "^"
    assert any(t["token"] == r"\d{3}" and "exactly 3 times" in t["meaning"] for t in toks)
    assert any(t["token"] == "[- ]?" and t["meaning"].startswith("one character from") for t in toks)
    assert any("alternative 2 of 2" in t["meaning"] for t in toks)
    assert any(t["depth"] == 1 for t in toks)


def test_explain_regex_unanchored_note():
    out = call("explain_regex", pattern=r"\d+")
    assert out["fully_anchored"] is False and any("Not fully anchored" in n for n in out["notes"])


def test_test_regex_results_and_hints():
    out = call(
        "test_regex",
        pattern=r"\(?(\d{3})\)?[- ]?(\d{3})-(\d{4})",
        should_match=["(555) 123-4567", "555-123-4567", "  555-123-4567", "ABC-123-4567"],
        should_not_match=["5551234567", "555-123-4567x"],
    )
    assert out["passed"] == 4 and out["total"] == 6 and out["all_pass"] is False
    ok = out["results"][0]
    assert ok["matched"] and ok["groups"] == ["555", "123", "4567"]
    ws = next(f for f in out["failures"] if f["sample"].startswith("  "))
    assert any("stripping whitespace" in h for h in ws["hints"])
    assert any("substring" in h for h in ws["hints"])
    abc = next(f for f in out["failures"] if f["sample"].startswith("ABC"))
    assert any("no match at all" in h for h in abc["hints"])


def test_test_regex_search_and_findall_modes():
    s = call("test_regex", pattern=r"\d+", should_match=["order 42"], should_not_match=["none"], mode="search")
    assert s["all_pass"] and s["results"][0]["match"] == "42"
    f = call("test_regex", pattern=r"\d+", should_match=["1 and 22 and 333"], mode="findall")
    assert f["results"][0]["found"] == ["1", "22", "333"] and f["results"][0]["count"] == 3
    i = call("test_regex", pattern=r"abc", should_match=["ABC"], flags="i")
    assert i["all_pass"]


def test_test_regex_refuses_dangerous_and_invalid():
    with pytest.raises(ToolError, match="dangerous"):
        call("test_regex", pattern=r"^(\w+\s?)*$", should_match=["a" * 30 + "!"])
    with pytest.raises(ToolError):
        call("test_regex", pattern=r"(unclosed", should_match=["x"])
    with pytest.raises(ToolError):
        call("test_regex", pattern=r"x", should_match=["x"], flags="q")


def test_convert_flavor_python_to_javascript_and_go():
    js = call("convert_flavor", pattern=r"(?i)\A(?P<u>\w+)(?P=u)\Z", target="javascript")
    assert js["pattern"] == r"^(?<u>\w+)\k<u>$"
    assert any("inline flags" in c for c in js["changes"])
    go = call("convert_flavor", pattern=r"(?<=x)(?P<u>\w+)\1\Z", target="go")
    assert go["pattern"].endswith(r"\z")
    assert len(go["unsupported"]) == 2
    py = call("convert_flavor", pattern=r"(?<year>\d{4})\k<year>\z", source="javascript", target="python")
    assert py["pattern"] == r"(?P<year>\d{4})(?P=year)\Z"


def test_convert_flavor_rejects_empty():
    with pytest.raises(ToolError):
        call("convert_flavor", pattern="", target="go")


def test_optional_leading_separator_still_counts_as_overlap():
    # OWASP's ReGexLib email regex: the separator group is optional, so iterations can start with [a-zA-Z0-9]
    p = r"^([a-zA-Z0-9])(([\-.]|[_]+)?([a-zA-Z0-9]+))*(@){1}[a-z0-9]+[.]{1}(([a-z]{2,3})|([a-z]{2,3}[.]{1}[a-z]{2,3}))$"
    assert call("check_regex_safety", pattern=p)["risk"] == "dangerous"
    assert call("check_regex_safety", pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,24}$")["risk"] == "safe"
