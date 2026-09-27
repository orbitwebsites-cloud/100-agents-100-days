"""Content Calendar tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("content-calendar")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_build_schedule_dates_pillars_and_audience_tz():
    out = call(
        "build_schedule",
        start_date="2026-10-05",  # Monday
        weeks=2,
        platforms=[
            {"platform": "instagram", "posts_per_week": 3, "days": ["Tue", "Thu", "Sat"], "time": "11:00"},
            {"platform": "x", "posts_per_week": 1, "days": ["Mon"], "time": "09:00"},
        ],
        pillars=["Educate", "Story"],
        timezone="Europe/Berlin",
        audience_timezone="America/New_York",
    )
    assert out["total_posts"] == 8
    assert out["posts_per_platform"] == {"instagram": 6, "x": 2}
    first = out["slots"][0]
    assert first["date"] == "2026-10-05" and first["weekday"] == "Mon" and first["platform"] == "x"
    assert first["time_audience"] == "03:00"  # Berlin 09:00 → New York 03:00 (both on DST)
    assert first["create_by"] == "2026-10-03"
    ig = [s for s in out["slots"] if s["platform"] == "instagram"]
    assert [s["weekday"] for s in ig[:3]] == ["Tue", "Thu", "Sat"]
    assert ig[0]["time_audience"] == "05:00"
    # pillars alternate: no two consecutive slots share a pillar
    pillars = [s["pillar"] for s in out["slots"]]
    assert all(a != b for a, b in zip(pillars, pillars[1:]))
    assert out["end"] == "2026-10-18"
    assert any("audience timezone" in w for w in out["warnings"])


def test_build_schedule_rejects_bad_platform_and_weeks():
    with pytest.raises(ToolError):
        call("build_schedule", start_date="2026-10-05", weeks=2, platforms=[{"platform": "myspace", "posts_per_week": 1}], pillars=["A"])
    with pytest.raises(ToolError):
        call("build_schedule", start_date="2026-10-05", weeks=0, platforms=[{"platform": "x", "posts_per_week": 1}], pillars=["A"])


def test_check_post_fits_counts_x_urls_as_23():
    url = "https://example.com/a/very/long/path/that/goes/on/and/on/forever/and/ever"
    out = call("check_post_fits", platform="twitter", text="Read this: " + url)
    assert out["platform"] == "x"
    assert out["chars"] == len("Read this: ") + 23
    assert out["fits"] is True and out["links"] == 1


def test_check_post_fits_flags_limit_fold_and_hashtags():
    text = "Hey everyone, welcome back! " + "x" * 250 + "\n" + " ".join(f"#tag{i}" for i in range(8))
    out = call("check_post_fits", platform="linkedin", text=text)
    assert out["hashtags"] == 8
    assert any("hashtags" in f for f in out["fixes"])
    assert any("see more" in f for f in out["fixes"])
    assert any("greeting" in f for f in out["fixes"])
    over = call("check_post_fits", platform="x", text="a" * 300)
    assert over["fits"] is False and over["over_by"] == 20
    yt = call("check_post_fits", platform="youtube", text="desc", title="t" * 101)
    assert yt["title"]["fits"] is False


def test_check_post_fits_bad_platform():
    with pytest.raises(ToolError):
        call("check_post_fits", platform="vine", text="hi")


def test_audit_mix_finds_promo_streaks_and_gaps():
    posts = [
        {"date": "2026-09-01", "platform": "instagram", "pillar": "Promo"},
        {"date": "2026-09-02", "platform": "instagram", "pillar": "Promo"},
        {"date": "2026-09-03", "platform": "instagram", "pillar": "Promo"},
        {"date": "2026-09-04", "platform": "instagram", "pillar": "Educate"},
        {"date": "2026-09-20", "platform": "instagram", "pillar": "Educate"},
        {"date": "2026-09-21", "platform": "x", "pillar": "Story"},
    ]
    out = call("audit_mix", posts=posts, targets={"Educate": 40, "Promo": 10})
    assert out["promo_pct"] == 50.0
    assert out["streaks"][0] == {"pillar": "Promo", "length": 3, "from": "2026-09-01", "to": "2026-09-03"}
    assert out["per_platform"]["instagram"]["longest_gap_days"] == 16
    assert out["vs_targets"]["Promo"]["delta_pct"] == 40.0
    assert any("gap" in f for f in out["flags"]) and any("Promo is" in f for f in out["flags"])
    assert out["health_score"] < 100


def test_audit_mix_rejects_empty_and_bad_dates():
    with pytest.raises(ToolError):
        call("audit_mix", posts=[])
    with pytest.raises(ToolError):
        call("audit_mix", posts=[{"date": "next tuesday", "pillar": "x"}])


def test_capacity_check_scales_plan_down():
    out = call(
        "capacity_check",
        hours_per_week=5,
        platforms=[{"platform": "youtube", "posts_per_week": 2}, {"platform": "tiktok", "posts_per_week": 5}],
        repurpose_share=0.0,
    )
    assert out["fits"] is False
    assert out["hours_needed"] == round((2 * 360 + 5 * 75) / 60, 1)
    fitted = {f["platform"]: f["posts_per_week"] for f in out["fit_plan"]}
    # one 360-min video alone exceeds the 300-min week, so YouTube goes every other week and TikTok fills the rest
    assert fitted["youtube"] == 0.5 and fitted["tiktok"] == 1 and out["fit_plan_hours"] <= 5
    ok = call("capacity_check", hours_per_week=5, platforms=[{"platform": "x", "posts_per_week": 5, "minutes_per_post": 12}])
    assert ok["fits"] is True and ok["hours_needed"] == round(5 * 12 * (1 - 0.3 * 0.75) / 60, 1)


def test_capacity_check_bad_input():
    with pytest.raises(ToolError):
        call("capacity_check", hours_per_week=0, platforms=[{"platform": "x", "posts_per_week": 1}])
    with pytest.raises(ToolError):
        A.get_tool("capacity_check").call({"hours_per_week": "lots", "platforms": []})
