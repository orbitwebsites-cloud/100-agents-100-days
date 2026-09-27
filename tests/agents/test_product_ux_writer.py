"""UX Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("ux-writer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_check_microcopy_budgets_and_casing():
    out = call(
        "check_microcopy",
        strings=[
            {"key": "save", "text": "Save changes", "component": "button"},
            {"key": "save2", "text": "Click Here To Save Your Changes Now!", "component": "button"},
            {"key": "tip", "text": "Please configure the API endpoint parameter before initialising the session token.", "component": "tooltip"},
        ],
        localised=True,
    )
    s = {r["key"]: r for r in out["strings"]}
    assert s["save"]["issues"] == [] and s["save"]["budget"] == 18
    bad = " ".join(s["save2"]["issues"])
    assert "Title Case" in bad and "exclamation" in bad and "chars >" in bad and "click" in bad.lower()
    tip = " ".join(s["tip"]["issues"])
    assert "jargon" in tip and "please" in tip
    assert out["passing"] == 1


def test_check_microcopy_rejects_unknown_component():
    with pytest.raises(ToolError):
        call("check_microcopy", strings=[{"text": "Hi", "component": "banner"}])


def test_lint_error_message_scores_structure():
    bad = call("lint_error_message", message="Error 403: Request failed. Invalid permissions.")
    good = call("lint_error_message", message="Couldn't save your changes because you're offline. Reconnect and try again.")
    assert bad["score"] < 40 and bad["verdict"] == "Rewrite"
    assert bad["parts"]["how"] is False
    assert any("blame" in i for i in bad["issues"]) and any("error code" in i for i in bad["issues"])
    assert good["score"] >= 85 and good["parts"] == {"what": True, "why": True, "how": True}


def test_lint_error_message_rejects_empty():
    with pytest.raises(ToolError):
        call("lint_error_message", message="  ")


def test_check_consistency_finds_synonym_conflicts():
    out = call("check_consistency", strings=["Log in", "Sign in", "Sign in to continue", "Delete file", "Remove file", "Save Your Draft"])
    concepts = {c["concept"]: c for c in out["terminology_conflicts"]}
    assert concepts["sign in"]["standardise_on"] == "sign in"
    assert concepts["sign in"]["variants"] == {"sign in": 2, "log in": 1}
    assert "delete" in concepts
    assert out["title_case_examples"] == ["Save Your Draft"]
    assert out["verdict"] != "Consistent"


def test_check_consistency_rejects_empty_list():
    with pytest.raises(ToolError):
        call("check_consistency", strings=["", "  "])


def test_localization_expansion_flags_overflow():
    out = call("localization_expansion", text_value="Continue to payment", container_chars=24, locales=["de", "ja", "fr"])
    rows = {r["locale"]: r for r in out["locales"]}
    assert rows["de"]["estimated_chars"] == 28 and rows["de"]["fits"] is False
    assert rows["ja"]["estimated_chars"] == 17 and rows["ja"]["fits"] is True
    assert out["overflow"] == ["de", "fr"]
    assert out["safe_source_length"] == 16


def test_localization_expansion_rejects_unknown_locale():
    with pytest.raises(ToolError):
        call("localization_expansion", text_value="Save", container_chars=10, locales=["xx"])
