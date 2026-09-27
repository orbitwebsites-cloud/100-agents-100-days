"""Short Video Scripter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("short-video-scripter")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


SCRIPT = """Your morning routine is backwards.
[TEXT: backwards?]
Most people drink coffee first and it wrecks their cortisol.
[B-ROLL: pouring coffee]
Here is what to do instead.
Wait ninety minutes, get sunlight, then drink it.
Follow for part two.
"""


def test_time_script_counts_only_spoken_words():
    out = call("time_script", script=SCRIPT, pace="natural", platform="reels", target_seconds=15)
    assert out["spoken_lines"] == 5
    assert out["spoken_words"] == 5 + 10 + 6 + 8 + 4
    assert out["total_seconds"] == round(33 / 2.5, 1)
    assert out["hook_words"] == 5 and out["hook_seconds"] == 2.0
    assert out["lines"][1]["starts_at"] == "0:02"
    assert out["fits_platform"] is True
    assert out["words_for_target"] == 37
    assert len(out["directions"]) == 2


def test_time_script_flags_long_hook_and_overrun():
    long_hook = "So today I am going to talk to you about all of the reasons why your routine is wrong. " + "Blah blah. " * 40
    out = call("time_script", script=long_hook, pace="fast", platform="x", target_seconds=20)
    assert any("Hook is" in f for f in out["flags"])
    assert any("over target" in f for f in out["flags"])


def test_time_script_bad_input():
    with pytest.raises(ToolError):
        call("time_script", script="   ")
    with pytest.raises(ToolError):
        call("time_script", script="hi there", platform="vimeo")
    with pytest.raises(ToolError):
        call("time_script", script="[TEXT: only a card]")


def test_score_hook_prefers_specific_second_person():
    good = call("score_hook", hook="3 landlord mistakes that cost you $11k")
    bad = call("score_hook", hook="Hey guys, welcome back, today I want to talk about some really amazing stuff")
    assert good["score"] >= 75 and good["grade"] == "strong"
    assert "specific number" in good["hook_types_detected"]
    assert bad["score"] < 40 and bad["grade"] == "rewrite"
    assert any("greeting" in f for f in bad["fixes"])
    assert any("Vague" in f for f in bad["fixes"])


def test_score_hook_rejects_empty():
    with pytest.raises(ToolError):
        call("score_hook", hook="")


def test_plan_beats_budgets_sum_to_runtime():
    out = call("plan_beats", duration_seconds=30, format="listicle", pace="natural")
    assert out["total_word_budget"] == 75
    assert out["beats"][0]["beat"].startswith("Hook") and out["beats"][0]["seconds"] == 3.0
    assert abs(sum(b["seconds"] for b in out["beats"]) - 30) < 0.2
    assert out["beats"][-1]["start_s"] == 24.6 and out["beats"][-1]["starts_at"] == "0:25"
    assert out["beats"][1]["starts_at"] == "0:03"
    short = call("plan_beats", duration_seconds=15)
    assert any("loop" in n for n in short["notes"])


def test_plan_beats_bad_duration():
    with pytest.raises(ToolError):
        call("plan_beats", duration_seconds=2)
    with pytest.raises(ToolError):
        A.get_tool("plan_beats").call({"duration_seconds": 30, "format": "musical"})


def test_lint_script_strips_fillers_and_flags_cta():
    script = "Hey guys, so basically your routine is literally wrong.\nThis sentence goes on and on and on with so many words that you would run out of breath before you finished saying it.\nLike this, follow me, comment below and share it and subscribe."
    out = call("lint_script", script=script)
    types = {i["type"] for i in out["issues"]}
    assert {"filler", "warm-up intro", "long sentence", "CTA pile-up"} <= types
    assert out["filler_count"] >= 3
    assert out["cleaned_script"].splitlines()[0] == "your routine is wrong."
    none = call("lint_script", script="Your routine is wrong.\nFix it by waiting ninety minutes.")
    assert any(i["type"] == "no CTA" for i in none["issues"])


def test_lint_script_bad_input():
    with pytest.raises(ToolError):
        call("lint_script", script="")


def test_time_script_reads_numbers_aloud():
    out = call("time_script", script="Save $250,000 by 2035 at 4.5% a year.", pace="natural")
    # save | two hundred fifty thousand dollars | by | twenty thirty five | at | four point five percent | a year
    assert out["written_words"] == 10 and out["spoken_words"] == 1 + 5 + 1 + 3 + 1 + 4 + 2
