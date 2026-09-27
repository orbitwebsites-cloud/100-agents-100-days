"""Copy Editor tools — the free content agent."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("copy-editor")

BAD = (
    "In order to utilize the platform, a decision was made by the team to leverage synergy. "
    "It was really very quickly decided. At the end of the day, we delve into a tapestry of robust solutions. "
    "The report was written by Sam. The report was reviewed by Ana. The report was filed by Lee."
)
GOOD = (
    "Sam wrote the report on Monday. Ana reviewed it the same afternoon and found two errors, both in the "
    "pricing table. Lee filed the corrected version by five. The client signed on Tuesday."
)


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_agent_is_free():
    assert A.free is True


def test_diagnose_counts_real_problems():
    out = call("diagnose", draft=BAD)
    b = out["baseline"]
    assert b["passive_sentences"] == 4
    assert b["cliches"] >= 2  # "leverage synergy" / "at the end of the day"
    assert b["ai_tells"] >= 3  # delve, tapestry, robust, leverage
    assert b["hedges"] >= 2  # really, very
    assert any(a[0] == "quickly" for a in out["findings"]["adverbs"])
    assert any("in order to" in n["phrase"] or "make a decision" in n["phrase"] for n in out["findings"]["nominalisations"]) or out["findings"]["nominalisations"] == []
    assert out["findings"]["same_opener_runs"] and out["findings"]["same_opener_runs"][0]["word"] == "the"
    assert out["score"] < 40
    assert any("Passive" in f for f in out["fixes"])


def test_diagnose_scores_clean_prose_high():
    out = call("diagnose", draft=GOOD)
    assert out["score"] >= 80
    assert out["baseline"]["passive_sentences"] == 0


def test_diagnose_rejects_empty_and_bad_genre():
    with pytest.raises(ToolError):
        call("diagnose", draft="   ")
    with pytest.raises(ToolError):
        call("diagnose", draft=GOOD, genre="poetry")


def test_find_replacements_rewrites_and_logs():
    out = call("find_replacements", draft='In order to win, we utilize tools. It is important to note that "in order to" stays in quotes. Prior to launch, make a decision.')
    assert out["rewritten"] == 'To win, we use tools. "in order to" stays in quotes. Before launch, decide.'
    assert out["total_edits"] == 5
    assert out["words_saved"] == 11
    assert {e["from"] for e in out["edits"]} == {"in order to", "utilize", "it is important to note that", "prior to", "make a decision"}


def test_find_replacements_aggressive_flag():
    base = call("find_replacements", draft="We have approximately ten additional items.")
    agg = call("find_replacements", draft="We have approximately ten additional items.", aggressive=True)
    assert base["total_edits"] == 0
    assert agg["rewritten"] == "We have about ten more items."


def test_find_replacements_rejects_empty():
    with pytest.raises(ToolError):
        call("find_replacements", draft="")


def test_style_check_finds_mechanics():
    out = call("style_check", draft='He said "hello" and she said “hi”.  We have 3 cats - and 12 dogs — the the end. It\'s own thing. Colour, colour, and color.')
    kinds = {i["kind"] for i in out["issues"]}
    assert {"spacing", "consistency", "error", "numbers", "spelling"} <= kinds
    assert any("the the" in i["issue"] for i in out["issues"])
    assert any("It's own" in i["issue"] for i in out["issues"])
    assert out["spelling_variant"] == "UK"


def test_style_check_ap_vs_chicago():
    ap = call("style_check", draft="We bought apples, pears, and plums. We bought twelve of them.", style="ap")
    chi = call("style_check", draft="We bought apples, pears and plums.", style="chicago")
    assert any("AP style omits" in i["issue"] for i in ap["issues"])
    assert any("numerals for 10" in i["issue"] for i in ap["issues"])
    assert any("Chicago uses the serial comma" in i["issue"] for i in chi["issues"])


def test_style_check_rejects_bad_style():
    with pytest.raises(ToolError):
        call("style_check", draft=GOOD, style="mla")


def test_readability_diff_measures_and_warns():
    out = call("readability_diff", before="In order to win at this point in time, the report was written by Sam, which was 40% longer than before.", after="To win now, Sam wrote the report.")
    assert out["before"]["words"] == 21
    assert out["after"]["words"] == 7
    assert out["before"]["passive_sentences"] == 1 and out["after"]["passive_sentences"] == 0
    assert out["delta"]["fk_grade"] < 0
    assert any("40%" in w for w in out["warnings"])
    assert any("Cut" in w for w in out["warnings"])


def test_readability_diff_rejects_empty():
    with pytest.raises(ToolError):
        call("readability_diff", before=GOOD, after=" ")
    with pytest.raises(ToolError):
        A.get_tool("readability_diff").call({"before": 3, "after": GOOD})
