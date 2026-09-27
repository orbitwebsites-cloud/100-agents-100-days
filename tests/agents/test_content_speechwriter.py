"""Speechwriter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("speechwriter")

SPEECH = (
    "## OPENING\nWhat do you do when the thing you built stops working? [pause] Twelve years ago I stood in a warehouse "
    "with nothing but a broken forklift and a plan.\n\n"
    "## BODY\nWe tried. We failed. We tried again. Not because we were brave, but because we had no choice. "
    "We learned that speed matters, that people matter, and that the truth matters most. "
    + "The market moved and so did we, one customer at a time, without ever losing sight of what we owed the people who trusted us first. " * 10
    + "Approximately 34.7% of our revenue came from three accounts. We used the API and the SLA.\n\n"
    "## CLOSE\nSo here is what I ask of you. Build the thing. Fix the thing. Share the thing. [applause] "
    "When the thing you built stops working, remember the forklift."
)


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_timing_counts_words_pauses_and_sections():
    out = call("timing", script=SPEECH, wpm=130, slot_minutes=5)
    assert out["spoken_words"] == 28 + 275 + 26
    assert out["marks"] == {"pause": 1, "applause": 1}
    assert out["pause_time"] == "0:11"  # 2 + 8 + 2 paragraph breaks × 0.5
    assert out["total"] == "2:43"
    secs = {s["section"]: s for s in out["sections"]}
    assert secs["OPENING"]["words"] == 28 and secs["BODY"]["start"] == "0:15"
    assert out["target"] == "4:30"
    assert any("more words" in f for f in out["flags"])
    assert out["long_breath_sentences"][0]["words"] == 24
    preset = call("timing", script=SPEECH, pace="ceremonial")
    assert preset["wpm"] == 110


def test_timing_rejects_bad_pace():
    with pytest.raises(ToolError):
        call("timing", script=SPEECH, wpm=10)
    with pytest.raises(ToolError):
        call("timing", script="[pause]")


def test_rhetoric_check_finds_devices():
    out = call("rhetoric_check", script=SPEECH)
    c = out["counts"]
    assert c["rhetorical_question"] == 1 and out["found"]["rhetorical_question"][0]["part"] == "opening"
    assert c["antithesis"] >= 1 and "Not because we were brave" in out["found"]["antithesis"][0]["text"]
    assert any(d["part"] == "close" for d in out["found"]["tricolon"])
    assert any("speed matters" in d["text"] for d in out["found"]["tricolon"])
    assert c["callback"] >= 1 and any("built stops working" in d["phrase"] for d in out["found"]["callback"])
    assert c["epistrophe"] >= 1
    assert "Close: no tricolon" not in " ".join(out["gaps"])


def test_rhetoric_check_reports_gaps():
    flat = "We had a good year. Revenue grew. Costs fell. The team is bigger. Next year will be similar. Thank you all for coming today."
    out = call("rhetoric_check", script=flat)
    gaps = " ".join(out["gaps"])
    assert "No antithesis" in gaps and "No callback" in gaps and "no question or antithesis" in gaps


def test_rhetoric_check_rejects_tiny():
    with pytest.raises(ToolError):
        call("rhetoric_check", script="One sentence only.")


def test_structure_map_shares_and_moves():
    out = call("structure_map", script=SPEECH)
    assert out["shares"]["opening_pct"] == 8.5 and out["shares"]["close_pct"] == 7.9
    assert out["opening_hook"] == "question"
    assert out["closing_move"] == "charge"
    assert "built stops working" in out["callbacks"]
    assert out["timeline"][0]["section"] == "OPENING"
    weak = call("structure_map", script="Thank you for having me.\n\nThe middle part is here and it is long enough to count as a body paragraph.\n\nIn summary, three things. Thank you.")
    assert weak["opening_hook"] == "greeting (weak)"
    assert any("summary" in f for f in weak["flags"]) and any("thank you" in f for f in weak["flags"])


def test_structure_map_rejects_unmappable():
    with pytest.raises(ToolError):
        call("structure_map", script="Only one paragraph here with enough words to pass the minimum count of thirty spoken words, so we keep typing until we get there and beyond.")


def test_speakability_flags_numbers_acronyms_long_sentences():
    out = call("speakability", script=SPEECH)
    assert out["acronyms"] == ["API", "SLA"]
    assert out["numbers"][0]["number"] == "34.7%" and out["numbers"][0]["say"] == "about a third"
    assert "approximately" in out["hard_words"]
    assert len(out["long_sentences"]) == 10
    assert out["score"] < 85
    assert any("semicolon" not in f for f in out["fixes"])


def test_speakability_rejects_empty():
    with pytest.raises(ToolError):
        call("speakability", script="")
