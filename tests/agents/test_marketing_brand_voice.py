"""Brand Voice Guardian tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("brand-voice")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


SAMPLES = [
    "You've got enough on your plate. So we built the dashboard to load in under a second, and we cut the setup to 4 minutes. No tickets, no waiting. Want to see it? Open your workspace and click Insights.",
    "Here's the thing about reports: nobody reads them. We didn't want to build another one. Instead, you get one number every morning and a reason it moved. That's it. Try it for a week and tell us what you think.",
    "We shipped 14 fixes this week. The big one: exports don't time out anymore. You asked, we listened. If something's still slow, reply to this email and we'll look at it today.",
]
CORPORATE = (
    "Our organization is pleased to announce that a comprehensive enhancement of the reporting infrastructure has been implemented. "
    "Utilizing state-of-the-art technology, the platform has been optimized to facilitate seamless synergy between stakeholders. "
    "It is recommended that users leverage the new capabilities."
)


def test_extract_voice_profile_measures_habits():
    out = call("extract_voice_profile", samples=SAMPLES, brand_name="Acme")
    p = out["profile"]
    assert out["samples"] == 3 and out["total_words"] == 111
    assert p["avg_sentence_words"] < 10
    assert p["contraction_rate_pct"] == 100.0
    assert p["jargon_per_100"] == 0.0
    assert p["questions_per_100"] > 0
    assert p["pronouns_per_100"]["you"] > 0 and p["pronouns_per_100"]["we"] > 0
    assert "short, punchy sentences" in out["voice_in_words"]
    assert any("noisy" in w for w in out["warnings"])


def test_extract_voice_profile_rejects_empty():
    with pytest.raises(ToolError):
        call("extract_voice_profile", samples=["", "  "])


def test_score_against_profile_flags_drift_and_banned():
    profile = call("extract_voice_profile", samples=SAMPLES)["profile"]
    off = call("score_against_profile", draft=CORPORATE, profile=profile, banned_terms=["leverage", "synergy"])
    assert off["score"] < 60 and off["grade"] == "off-brand"
    metrics = {d["metric"] for d in off["drifts"]}
    assert {"sentence length", "reading grade", "jargon", "passive voice"} <= metrics
    assert [b["term"] for b in off["banned_hits"]] == ["leverage", "synergy"]
    on = call("score_against_profile", draft="You asked for faster exports. We shipped them: a 50,000-row file now takes 4 seconds. Try it and tell us what breaks?", profile=profile)
    assert on["score"] >= 80 and on["grade"] == "on-voice"


def test_score_against_profile_rejects_bad_profile():
    with pytest.raises(ToolError):
        call("score_against_profile", draft="hello there", profile={"foo": 1})


def test_lexicon_check_finds_banned_preferred_and_casing():
    out = call("lexicon_check", content="We love github and our users utilize Github daily.", banned_terms=["love"], preferred_terms={"users": "customers", "utilize": "use"}, proper_casing=["GitHub"])
    assert out["counts"] == {"banned": 1, "preferred": 2, "casing": 2}
    casing = [f for f in out["findings"] if f["type"] == "casing"]
    assert {f["term"] for f in casing} == {"github", "Github"}
    assert casing[0]["fix"] == "write 'GitHub'"
    assert out["findings"] == sorted(out["findings"], key=lambda f: f["position"])
    assert call("lexicon_check", content="Clean copy.", banned_terms=["bad"])["clean"] is True


def test_lexicon_check_rejects_empty():
    with pytest.raises(ToolError):
        call("lexicon_check", content="")


def test_tone_dimensions_separates_casual_from_formal():
    casual = call("tone_dimensions", content=" ".join(SAMPLES))
    formal = call("tone_dimensions", content=CORPORATE)
    assert casual["dimensions"]["formal_casual"]["score"] > formal["dimensions"]["formal_casual"]["score"]
    assert casual["dimensions"]["formal_casual"]["reads_as"] == "casual"
    assert formal["dimensions"]["formal_casual"]["reads_as"] == "formal"
    assert formal["warning"].startswith("Under 50 words")
    for d in casual["dimensions"].values():
        assert -1 <= d["score"] <= 1


def test_tone_dimensions_rejects_empty():
    with pytest.raises(ToolError):
        call("tone_dimensions", content="  ")


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("extract_voice_profile").call({"samples": "one string"})
