"""Email Campaign Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("email-campaign")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_subject_line_scoring_and_ranking():
    out = call(
        "test_subject_line",
        subject="Your dashboard just got 3x faster",
        preheader="See what changed and how to turn it on in 2 minutes",
        alternatives=["FREE UPGRADE!!! Act now", "Our October newsletter", "Re: quick question"],
    )
    p = out["primary"]
    assert p["chars"] == 33 and p["score"] >= 80
    assert p["preheader"]["ok"] is True
    ranked = {r["subject"]: r for r in out["ranked"]}
    assert ranked["FREE UPGRADE!!! Act now"]["score"] == 0
    assert any("spam triggers" in f for f in ranked["FREE UPGRADE!!! Act now"]["flags"])
    assert any("fake reply" in f for f in ranked["Re: quick question"]["flags"])
    assert out["recommended_ab_pair"][0] == "Your dashboard just got 3x faster"


def test_subject_line_mobile_truncation_and_preheader_repeat():
    out = call("test_subject_line", subject="An extremely long subject line that keeps going past the phone screen", preheader="An extremely long subject line that keeps going")
    assert out["primary"]["chars"] > 60
    assert any("clipped" in f for f in out["primary"]["flags"])
    assert any("repeats the subject" in f or "same words" in f for f in out["primary"]["preheader"]["flags"])


def test_subject_line_rejects_empty():
    with pytest.raises(ToolError):
        call("test_subject_line", subject="")


BODY = """Hi {{first_name}},
Your dashboard just got 3x faster. Click here to see it — 100% free for {{company_name}}.
[See the new dashboard]
Also https://bit.ly/x and https://example.com/a and https://example.com/b and https://example.com/c
P.S. Unsubscribe anytime. 123 Main Street, Austin TX
"""


def test_scan_email_body_finds_risks():
    out = call("scan_email_body", body=BODY, available_fields=["first_name"])
    assert out["deliverability_risk"] == "high"
    assert "click here" in out["spam_hits"]
    assert out["undefined_tokens"] == ["company_name"]
    assert out["content_links"] == 4
    assert out["has_unsubscribe"] is True and out["has_postal_address"] is True
    assert out["ctas"] == ["See the new dashboard"]
    assert any("shortener" in i for i in out["issues"])


def test_scan_email_body_clean_case():
    body = "Hi there,\n\nWe moved exports to a faster engine, so a 50,000-row file now takes 4 seconds.\n\n[Try the new export]\n\nUnsubscribe · 12 Market Street, Denver CO" + " word" * 40
    out = call("scan_email_body", body=body)
    assert out["deliverability_risk"] == "low" and out["spam_hits"] == []


def test_scan_email_body_rejects_empty():
    with pytest.raises(ToolError):
        call("scan_email_body", body=" ")


def test_send_schedule_skips_weekends_and_blocked_days():
    out = call("send_schedule", first_send_date="2026-10-01", pattern="launch", avoid_dates=["2026-10-06"])
    sends = [(s["send"], s["weekday"]) for s in out["sends"]]
    assert sends == [("2026-10-01", "Thursday"), ("2026-10-05", "Monday"), ("2026-10-07", "Wednesday"), ("2026-10-08", "Thursday")]
    assert out["sends"][1]["shifted_because"] == ["weekend", "weekend"]
    assert out["sends"][2]["shifted_because"] == ["blocked"]
    assert out["span_days"] == 7
    custom = call("send_schedule", first_send_date="2026-10-05", pattern="custom", custom_offsets_days=[0, 1, 1], email_count=3)
    assert len({s["send"] for s in custom["sends"]}) == 3  # collisions resolved


def test_send_schedule_rejects_unknown_pattern():
    with pytest.raises(ToolError):
        call("send_schedule", first_send_date="2026-10-01", pattern="weird")
    with pytest.raises(ToolError):
        call("send_schedule", first_send_date="next tuesday")


def test_campaign_metrics_rates_and_grades():
    out = call("campaign_metrics", sent=20000, delivered=19650, unique_opens=4900, unique_clicks=610, unsubscribes=42, spam_complaints=3, conversions=61, revenue=6100)
    r = out["rates"]
    assert r["delivery_rate_pct"] == 98.25
    assert r["open_rate_pct"] == 24.94
    assert r["click_rate_pct"] == 3.1
    assert r["click_to_open_rate_pct"] == 12.45
    assert r["unsubscribe_rate_pct"] == 0.214
    assert r["click_to_conversion_pct"] == 10.0
    assert r["revenue_per_email"] == round(6100 / 19650, 4)
    assert out["grades"]["click"] == "good" and out["grades"]["unsubscribe"] == "good"
    weak = call("campaign_metrics", sent=10000, delivered=9000, unique_opens=2500, unique_clicks=50, unsubscribes=80)
    assert weak["grades"]["delivery"] == "bad" and weak["grades"]["ctor"] == "bad"
    assert any("Body problem" in d for d in weak["diagnosis"])


def test_campaign_metrics_rejects_impossible_counts():
    with pytest.raises(ToolError):
        call("campaign_metrics", sent=100, delivered=120)


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("campaign_metrics").call({"sent": "many", "delivered": 1})


def test_subject_punctuation_and_caps_words_flagged():
    out = call("test_subject_line", subject="Hey! Big news: new plans, new prices?")
    assert any("punctuation marks" in f for f in out["primary"]["flags"])  # ! : , ? = 4 > 3 (Mailchimp: ≤ 3)
    caps = call("test_subject_line", subject="Your FREE guide to cafe margins")
    assert any("ALL-CAPS word: FREE" in f for f in caps["primary"]["flags"])
    assert not any("ALL-CAPS" in f for f in call("test_subject_line", subject="Our FAQ on ROI for SaaS teams")["primary"]["flags"])


def test_merge_tokens_with_fallbacks_are_parsed():
    out = call("scan_email_body", body="Hi {{ frist_name | default: \"there\" }} and *|FNAME|*. [Go] unsubscribe 1 Main Street", available_fields=["first_name", "fname"])
    assert out["merge_tokens"] == ["FNAME", "frist_name"] and out["undefined_tokens"] == ["frist_name"]
