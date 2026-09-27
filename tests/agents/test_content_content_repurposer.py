"""Content Repurposer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("content-repurposer")

SRC = (
    "# Pricing mistakes\n\nMost founders price too low. But the real mistake is not raising prices. We raised prices 40% and churn fell 2 points. "
    "Is your price a signal?\n\n## Three rules\n\n- Anchor high\n- Charge annually\n- Test every quarter\n\nPricing is positioning. "
    "\"The price is the product,\" as one customer told us. " + "Some filler words about pricing strategy here. " * 20
)


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_atomize_extracts_and_ranks():
    out = call("atomize", source=SRC)
    types = {a["type"]: a for a in out["atoms"]}
    assert out["atoms"][0]["type"] == "stat" and "40%" in out["atoms"][0]["text"]
    assert "contrast" in types and types["contrast"]["text"].startswith("But the real mistake")
    assert types["list"]["text"] == "Anchor high / Charge annually / Test every quarter"
    assert "carousel (3 slides)" in types["list"]["suggested_format"]
    assert types["question"]["text"] == "Is your price a signal?"
    assert out["supports"]["threads_or_carousels"] >= 1


def test_atomize_rejects_short_source():
    with pytest.raises(ToolError):
        call("atomize", source="Too short to atomise.")


def test_platform_limits_resolves_aliases():
    out = call("platform_limits", platforms=["twitter", "LinkedIn"])
    assert [r["platform"] for r in out["platforms"]] == ["x", "linkedin"]
    assert out["platforms"][0]["max_chars"] == 280 and out["platforms"][1]["max_chars"] == 3000
    assert call("platform_limits")["count"] >= 15


def test_platform_limits_rejects_unknown():
    with pytest.raises(ToolError):
        call("platform_limits", platforms=["myspace"])


def test_fit_check_trims_at_sentence_boundary():
    out = call("fit_check", piece="We raised prices 40%. " * 20 + "https://a.com", platform="x")
    assert out["chars"] == 20 * 22 + 23
    assert out["fits"] is False and out["over_by"] == 183
    assert out["trimmed_chars"] <= 280 and out["trimmed"].endswith("40%.")
    ig = call("fit_check", piece="Hello everyone this is my post about something nice and it goes on for a while without any hook at all in the first part which is a problem. " * 2 + "#a #b #c #d #e #f", platform="instagram")
    assert ig["fits"] is True
    assert any("first 125 chars" in f for f in ig["flags"]) and any("6 hashtags" in f for f in ig["flags"])
    assert ig["fold_chars"] == 125


def test_fit_check_rejects_unknown_platform():
    with pytest.raises(ToolError):
        call("fit_check", piece="hi there", platform="friendster")


def test_repurpose_plan_schedules_with_spacing():
    out = call("repurpose_plan", source_type="article", source_words=2000, platforms=["x", "linkedin", "instagram", "newsletter"], start_date="2026-10-05", weeks=2)
    assert out["pieces_per_platform"] == {"x": 7, "linkedin": 3, "instagram": 2, "newsletter": 1}
    assert out["start_date"] == "2026-10-05"
    cal = out["calendar"]
    assert all(s["weekday"] not in ("Sat", "Sun") for s in cal)
    per_day = {}
    for s in cal:
        per_day.setdefault(s["date"], []).append(s["platform"])
    assert all(len(v) == len(set(v)) for v in per_day.values())
    x_days = sorted(s["date"] for s in cal if s["platform"] == "x")
    from datetime import date
    gaps = [(date.fromisoformat(b) - date.fromisoformat(a)).days for a, b in zip(x_days, x_days[1:])]
    assert all(g >= 2 for g in gaps)
    assert any(s["piece"] == "thread (lead)" and s["weekday"] in ("Tue", "Wed", "Thu") for s in cal)
    assert out["unscheduled"] == {"x": 2}


def test_repurpose_plan_rejects_bad_input():
    with pytest.raises(ToolError):
        call("repurpose_plan", source_type="article", source_words=50, platforms=["x"])
    with pytest.raises(ToolError):
        call("repurpose_plan", source_type="article", source_words=1000, platforms=["x"], start_date="next monday")


def test_plan_puts_big_pieces_midweek_and_leads_on_different_days():
    out = call("repurpose_plan", source_type="article", source_words=1400, platforms=["x", "linkedin", "instagram"], start_date="2026-10-05", weeks=2)
    leads = [s for s in out["calendar"] if s["atom_hint"] == "strongest atom"]
    assert len({s["date"] for s in leads}) == len(leads) == 3
    assert all(s["weekday"] in ("Tue", "Wed", "Thu") for s in leads if s["piece"].endswith("(lead)"))


def test_fit_check_instagram_catches_bare_domain():
    out = call("fit_check", piece="Our full pricing breakdown is at pricingnotes.io/raise — 40% up, 11 customers lost.", platform="instagram")
    assert any("link in bio" in f for f in out["flags"])
