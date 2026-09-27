"""Press Release Pro tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("press-release")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


MESSY = """Acme Launches Clinic Scheduling Software That Fills Cancelled Slots
AUSTIN, Texas, October 5, 2026 — Acme today launched Slotly, a scheduling tool that fills 80% of cancelled clinic appointments within 2 hours. The software connects to 15 percent of EHR systems and is used by twenty-five clinics.

"Front desks spend three hours a day on the phone," stated Jane Doe, CEO of Acme. "We think that time belongs with patients."

The launch is at 9 AM on Oct 6th in San Francisco, California! Our revolutionary Chief Executive Officer will present in 3 states.
"""

CLEAN = """Acme Launches Clinic Scheduling Software That Fills Cancelled Slots
AUSTIN, Texas, Oct. 5, 2026 — Acme today launched Slotly, a scheduling tool that fills 80% of cancelled clinic appointments within 2 hours. The software connects to 15% of EHR systems and is used by 25 clinics.

"Front desks spend three hours a day on the phone," said Jane Doe, CEO of Acme. "We think that time belongs with patients."

The launch is at 9 a.m. on Oct. 6 in San Francisco. The chief executive officer will present.

"Slotly cut our no-shows in half," said Sam Lee, practice manager at Lakeside Clinic.

## About Acme
Acme builds scheduling software for clinics. Founded in 2021, it serves 25 clinics across three states.

Media contact: Ana Ruiz, press@acme.com, 555-0100
###"""


def test_ap_style_check_catches_the_classics():
    out = call("ap_style_check", content=MESSY)
    found = {(f["rule"], f["found"]) for f in out["findings"]}
    assert ("dates: abbreviate month with a date", "October 5") in found
    assert ("percent: use % with figures", "15 percent") in found
    assert ("numerals: use figures for 10 and above", "twenty") in found
    assert ("attribution: use 'said'", '" stated') in found
    assert ("time: use 'a.m.' / 'p.m.'", "9 AM") in found
    assert ("states: abbreviate state after a city", "San Francisco, California") in found
    assert ("punctuation: no exclamation marks", "!") in found
    assert ("numerals: spell out one through nine", "3") in found
    assert any(r == "dates: month abbreviation needs a period" for r, _ in found)
    assert any(r == "dates: no ordinal suffixes" for r, _ in found)
    assert any(r == "hype: journalists cut this" for r, _ in found)
    assert out["must_fix"] >= 6
    assert out["findings"] == sorted(out["findings"], key=lambda f: f["position"])
    assert call("ap_style_check", content=CLEAN)["clean"] is True  # "three hours", "Oct. 6", "25 clinics" all pass


def test_ap_style_check_rejects_empty():
    with pytest.raises(ToolError):
        call("ap_style_check", content="   ")


def test_release_structure_scores():
    out = call("release_structure", content=CLEAN)
    assert out["headline_chars"] == 67 and out["checks"]["headline_length"] is True
    assert out["checks"]["dateline"] is True
    assert out["lede_words"] == 17 and out["checks"]["lede_length"] is True
    assert out["quotes"] == 3 and out["attributed_quotes"] == 2
    assert out["checks"]["two_sources"] is True and out["checks"]["boilerplate"] is True
    assert out["checks"]["media_contact"] is True and out["checks"]["end_mark"] is True
    assert out["checks"]["length_ok"] is False  # short test text
    assert out["grade"] in ("A", "B")
    bare = call("release_structure", content="We Are Excited To Announce Our Revolutionary Leading Platform Was Launched\n\nFounded in 2010, Acme has always believed in innovation. " * 3)
    assert bare["checks"]["dateline"] is False and bare["checks"]["headline_no_hype"] is False
    assert bare["checks"]["has_quote"] is False and bare["grade"] == "D"


def test_release_structure_rejects_empty():
    with pytest.raises(ToolError):
        call("release_structure", content="")


def test_pitch_email_check_bad_and_good():
    bad = call("pitch_email_check", subject="Press release: Acme launches Slotly", body="Hi Sarah, hope you are well. We are excited to announce our revolutionary product. Please see attached.", journalist_name="Sarah")
    assert bad["grade"] == "rewrite" and bad["personalised"] is False and bad["has_ask"] is False
    assert any("attachment" in i for i in bad["issues"]) and any("press release" in i for i in bad["issues"])
    assert any("names them" in i for i in bad["issues"])
    good = call(
        "pitch_email_check",
        subject="Embargoed: clinics fill 80% of cancelled slots in 2 hours",
        body="Sarah — your piece on no-show costs last week is exactly why I'm writing. Acme launches Slotly Tuesday: it fills 80% of cancelled clinic slots within 2 hours across 25 clinics. Your readers running small practices lose 12% of revenue to no-shows. Would you be interested in an embargoed briefing with our CEO this week? Release below my signature. https://acme.com/press",
        journalist_name="Sarah",
    )
    assert good["grade"] == "send" and good["personalised"] is True and good["has_ask"] is True
    assert good["words"] <= 150 and good["links"] == 1


def test_pitch_email_check_rejects_empty_body():
    with pytest.raises(ToolError):
        call("pitch_email_check", subject="x", body="")


def test_embargo_timing_business_days_and_zones():
    out = call("embargo_timing", embargo_lift="2026-10-13T09:00:00-04:00", audience_utc_offsets=[-4, -7, 1])
    steps = {s["step"]: s for s in out["schedule"]}
    assert steps["Send embargoed pitch to tier-2 list"]["date"] == "2026-10-05"  # 6 business days before Tue Oct 13
    assert steps["Single follow-up (reply in same thread)"]["date"] == "2026-10-09"
    assert steps["Post-lift: send 'it's live' note with link to those who covered"]["date"] == "2026-10-14"
    assert out["business_days_pitch_to_lift"] == 6
    assert out["lift_in_audience_zones"]["UTC-7"] == "Tue 2026-10-13 06:00"
    assert out["lift_in_audience_zones"]["UTC+1"] == "Tue 2026-10-13 14:00"
    assert out["warnings"] == []
    bad = call("embargo_timing", embargo_lift="2026-10-16T16:00:00-04:00", audience_utc_offsets=[1])
    assert any("Friday-afternoon" in w for w in bad["warnings"])
    assert any("outside newsroom hours" in w for w in bad["warnings"])
    assert any("6-10 a.m. ET" in w for w in bad["warnings"])


def test_embargo_timing_rejects_naive_datetime():
    with pytest.raises(ToolError):
        call("embargo_timing", embargo_lift="2026-10-13T09:00:00")


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("embargo_timing").call({"embargo_lift": 20261013})
