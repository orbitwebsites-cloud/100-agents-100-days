"""Test Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("test-writer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


SRC = '''
import requests, time

def parse_duration(text: str, default: int = 0) -> int:
    """Parse '1h30m'."""
    if not text:
        raise ValueError("empty")
    if text.endswith("h") or text.endswith("m"):
        return 1
    time.sleep(1)
    return requests.get("x").json()

class Cart:
    def total(self, items: list[dict]) -> float:
        return sum(i["p"] for i in items)

    def _private(self):
        yield 1
'''


def test_extract_signatures_values():
    out = call("extract_signatures", source=SRC, module_name="app.util")
    fn = out["functions"][0]
    assert fn["name"] == "parse_duration"
    assert [p["name"] for p in fn["params"]] == ["text", "default"]
    assert fn["params"][1]["default"] == "0" and fn["params"][0]["type"] == "str"
    assert fn["returns"] == "int"
    assert fn["raises"] == ["ValueError"]
    assert fn["branches"] == 3 and fn["min_tests"] == 5
    assert fn["side_effects"]["time.sleep"] == "clock/sleep"
    assert "network" in fn["side_effects"].values()
    assert "test_parse_duration_raises_value_error" in fn["suggested_tests"]
    method = next(f for f in out["functions"] if f["name"] == "Cart.total")
    assert [p["name"] for p in method["params"]] == ["items"]
    priv = next(f for f in out["functions"] if f["name"] == "Cart._private")
    assert priv["is_generator"] and not priv["is_public"]
    assert out["suggested_test_file"] == "tests/test_util.py"
    assert out["public_functions"] == 2


def test_extract_signatures_rejects_bad_python():
    with pytest.raises(ToolError):
        call("extract_signatures", source="def (:")


def test_edge_case_matrix_boundaries_and_counts():
    out = call("edge_case_matrix", params=[{"name": "age", "type": "int", "min": 0, "max": 120}, {"name": "email", "type": "email"}, {"name": "tags", "type": "list[str]", "nullable": True}])
    age = out["matrix"][0]
    values = [c["value"] for c in age["cases"]]
    assert values[:6] == ["120", "121", "119", "0", "-1", "1"]
    assert age["type"] == "int"
    assert out["matrix"][2]["type"] == "list" and out["matrix"][2]["cases"][0]["value"] == "None"
    assert out["counts"]["full_cartesian"] == out["matrix"][0]["must"] * out["matrix"][1]["must"] * out["matrix"][2]["must"]
    assert out["counts"]["must_cases_total"] == sum(m["must"] for m in out["matrix"])


def test_edge_case_matrix_rejects_nameless():
    with pytest.raises(ToolError):
        call("edge_case_matrix", params=[{"type": "int"}])


TESTS = '''
import pytest
from app.util import parse_duration

def test_parse_duration_basic():
    assert parse_duration("1h") == 1

def test_parse_duration_empty():
    with pytest.raises(ValueError):
        parse_duration("")

def test_nothing():
    parse_duration("2m")
'''


def test_coverage_gaps_finds_untested_and_no_assert():
    out = call("coverage_gaps", source=SRC, tests=TESTS)
    assert out["untested_functions"] == ["Cart.total"]
    assert out["tests_without_assertions"] == ["test_nothing"]
    row = next(r for r in out["rows"] if r["function"] == "parse_duration")
    assert row["test_count"] == 3 and row["untested_raises"] == []
    assert row["gap"] == 2  # needs 5, has 3
    assert out["test_functions"] == 3


def test_coverage_gaps_rejects_test_module_without_tests():
    with pytest.raises(ToolError):
        call("coverage_gaps", source=SRC, tests="x = 1")


def test_parametrize_block_generates_valid_code():
    out = call(
        "parametrize_block",
        function_name="parse_duration",
        arg_names=["text"],
        cases=[{"text": "1h", "expected": 3600}, {"text": "1h", "expected": 3600}, {"text": "", "raises": "ValueError", "match": "empty"}, {"text": "raw:'x' * 3", "expected": None}],
    )
    code = out["code"]
    assert "pytest.param('1h', 3600, id='1h')" in code
    assert "pytest.param('1h', 3600, id='1h-2')" in code
    assert "pytest.param('x' * 3, None, id=" in code
    assert "def test_parse_duration_raises(text, exc, match):" in code
    assert "with pytest.raises(exc, match=match):" in code
    assert out["duplicate_inputs"] == ["case #2 repeats the inputs of '1h'"]
    assert out["value_cases"] == 3 and out["error_cases"] == 1


def test_parametrize_block_rejects_missing_arg():
    with pytest.raises(ToolError):
        call("parametrize_block", function_name="f", arg_names=["a", "b"], cases=[{"a": 1, "expected": 2}])


SRC_MULTI = """def f(x):
    if x is None:
        raise ValueError("missing value")
    if x < 0:
        raise ValueError("negative value")
    return x
"""


def test_coverage_gaps_resolves_parametrized_exception_classes():
    tests = """import pytest
from m import f


@pytest.mark.parametrize("x, exc, match", [pytest.param(None, ValueError, "missing"), pytest.param(-1, ValueError, "negative")])
def test_f_raises(x, exc, match):
    with pytest.raises(exc, match=match):
        f(x)
"""
    row = call("coverage_gaps", source=SRC_MULTI, tests=tests)["rows"][0]
    assert row["untested_raises"] == [] and row["unpinned_raise_sites"] == []


def test_coverage_gaps_flags_raise_sites_no_message_pins():
    tests = """import pytest
from m import f


def test_f_raises():
    with pytest.raises(ValueError):
        f(None)
"""
    row = call("coverage_gaps", source=SRC_MULTI, tests=tests)["rows"][0]
    assert [s["line"] for s in row["unpinned_raise_sites"]] == [3, 5]
