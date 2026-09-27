"""YouTube Scripter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("youtube-scripter")

SCRIPT = (
    "## HOOK\nThis one email got 14 replies from 20 sends. [B-ROLL: inbox] By the end you'll have the template.\n\n"
    "## Why emails get ignored\n" + "Here is a sentence about why. " * 120 + "\n\n"
    "## The fix\n" + "Do this. " * 40 + "\n\n## CLOSE\nGo watch the next video."
)


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_script_timing_counts_spoken_words_and_sections():
    out = call("script_timing", script=SCRIPT, wpm=150, target_minutes=8)
    assert out["spoken_words"] == 17 + 720 + 80 + 5
    assert out["runtime"] == "5:28"
    assert out["hook_seconds"] == 7 and out["hook_fits_30s"] is True
    secs = {s["section"]: s for s in out["sections"]}
    assert secs["Why emails get ignored"]["start"] == "0:07" and secs["Why emails get ignored"]["seconds"] == 288
    assert secs["The fix"]["start"] == "4:55"
    assert any("no B-roll/interrupt marker" in f for f in out["flags"])
    assert out["words_vs_target"] == 822 - 1200


def test_script_timing_rejects_bad_pace():
    with pytest.raises(ToolError):
        call("script_timing", script=SCRIPT, wpm=20)
    with pytest.raises(ToolError):
        call("script_timing", script="[B-ROLL: only directions]")


def test_retention_beats_timeline():
    out = call("retention_beats", target_minutes=8, format="listicle", items=5)
    beats = {b["beat"]: b["at"] for b in out["beats"]}
    assert beats["Cold open"] == "0:00"
    assert out["hook_window"] == "0:00-0:24"
    assert beats["Item 1"] == "0:24" and beats["Item 5"] == "5:53"
    assert out["interrupts"] == 5
    assert beats["End screen"] == "7:40"
    assert out["script_words_at_150wpm"] == 1200
    short = call("retention_beats", target_minutes=1, format="vlog")
    assert short["cta_at"] == "end only (short video)"


def test_retention_beats_rejects_out_of_range():
    with pytest.raises(ToolError):
        call("retention_beats", target_minutes=0.1)
    with pytest.raises(ToolError):
        call("retention_beats", target_minutes=5, interrupt_every_seconds=5)


def test_title_check_ranks_and_flags():
    out = call("title_check", titles=[
        "Why Your Cold Emails Get Ignored (And The 3 Fixes)",
        "YOU WON'T BELIEVE THIS INSANE EMAIL TRICK!!!",
        "A very long title that goes on and on and on and on and on and on and on and on forever",
    ], keyword="cold emails")
    assert out["recommended"] == "Why Your Cold Emails Get Ignored (And The 3 Fixes)"
    assert out["ranked"][0]["score"] >= 85 and out["ranked"][0]["chars"] == 50
    assert out["truncating"] == ["A very long title that goes on and on and on and on and on and on and on and on forever"]
    caps = next(r for r in out["ranked"] if r["title"].startswith("YOU"))
    assert any("ALL-CAPS" in x for x in caps["reasons"]) and any("clickbait" in x for x in caps["reasons"])
    assert out["ranked"][-1]["sidebar_preview"].endswith("…")


def test_title_check_rejects_empty():
    with pytest.raises(ToolError):
        call("title_check", titles=[])
    with pytest.raises(ToolError):
        call("title_check", titles=["ok", ""])


def test_build_chapters_cumulative_and_rules():
    out = call("build_chapters", chapters=[{"title": "Hook", "duration": 30}, {"title": "Why", "duration": "2:10"}, {"title": "Fix", "duration": "3m 5s"}, {"title": "Close", "duration": 8}], description="In this video I show you cold emails.", keyword="cold emails")
    assert out["chapter_block"] == "0:00 Hook\n0:30 Why\n2:40 Fix\n5:45 Close"
    assert out["total_runtime"] == "5:53"
    assert out["valid"] is True
    assert any("In this video" in f for f in out["description"]["flags"])
    bad = call("build_chapters", chapters=[{"title": "A", "start": "0:10"}, {"title": "B", "start": "0:15"}])
    assert bad["valid"] is False
    assert any("0:00" in f for f in bad["flags"]) and any("at least 3" in f for f in bad["flags"]) and any("under 10 s" in f for f in bad["flags"])


def test_build_chapters_rejects_bad_duration():
    with pytest.raises(ToolError):
        call("build_chapters", chapters=[{"title": "A", "duration": "soon"}])
    with pytest.raises(ToolError):
        call("build_chapters", chapters=[{"title": ""}])
