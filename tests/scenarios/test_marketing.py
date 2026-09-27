"""Marketing — replayable evaluation scenarios (see evals/marketing.md).

Each test replays the tool calls a customer's AI made while following the agent's playbook on a
realistic request, and asserts the numbers the deliverable relied on. Every expected value below was
computed independently of this codebase (scipy / statsmodels / numpy / zoneinfo / hand arithmetic,
or a published reference value) — the comment next to each says how.
"""

import pytest

from hundred import registry


def run(slug, tool, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ─────────────────────────────── ab-test-analyst ───────────────────────────────
# Checkout redesign, 50/50, 14 daily looks, pre-planned MDE +10 %, 2,600 visitors/day, started 2026-09-14.


def test_ab_scenario_split_and_primary_test():
    srm = run("ab-test-analyst", "srm_check", expected_split_pct=[50, 50], observed_visitors=[18240, 18106])
    assert srm["chi_square"] == pytest.approx(0.494, abs=1e-3)  # scipy.stats.chisquare: 0.49403
    assert srm["p_value"] == pytest.approx(0.482135, abs=1e-5)  # scipy: 0.482135
    assert srm["srm_detected"] is False

    sig = run("ab-test-analyst", "significance_test", control_visitors=18240, control_conversions=612, variant_visitors=18106, variant_conversions=689)
    assert sig["z"] == pytest.approx(2.3095, abs=1e-4)  # hand pooled z: 2.309481
    assert sig["p_value"] == pytest.approx(0.020917, abs=1e-6)  # scipy chi2_contingency(correction=False): 0.0209169
    assert sig["relative_lift_pct"] == pytest.approx(13.41, abs=0.01)  # 13.4149
    assert sig["absolute_lift_ci_pp"] == pytest.approx([0.068, 0.832], abs=1e-3)  # unpooled Wald: 0.06806, 0.83215
    assert sig["relative_lift_ci_pct"] == pytest.approx([1.92, 26.21], abs=0.01)  # log-ratio delta: 1.9155, 26.2118
    assert sig["prob_variant_beats_control_pct"] == 99.0  # Φ(diff/se_unpooled) = 0.98953
    # Per-arm Wilson intervals (parity with Evan Miller's chi-squared tool): statsmodels proportion_confint(method="wilson")
    assert sig["control"]["rate_ci_pct"] == pytest.approx([3.104, 3.627], abs=1e-3)  # 3.1036, 3.6266
    assert sig["variant"]["rate_ci_pct"] == pytest.approx([3.536, 4.094], abs=1e-3)  # 3.5363, 4.0940


def test_ab_scenario_power_peeking_and_revenue():
    ss = run("ab-test-analyst", "sample_size", baseline_rate_pct=3.355, mde_relative_pct=10, daily_visitors=2600, start_date="2026-09-14")
    assert ss["visitors_per_arm"] == 47397  # Fleiss pooled formula by hand: 47,396.75 → 47,397
    assert ss["days_needed"] == 37 and ss["recommended_runtime_days"] == 42  # 94,794 / 2,600 = 36.46 → 37 → 6 weeks
    assert ss["sample_reached_date"] == "2026-10-20" and ss["stop_date"] == "2026-10-25"  # datetime: start + 36 / + 41 days

    peek = run("ab-test-analyst", "alpha_correction", looks=14, variants=2)
    # Recursive numerical integration (numpy grid, h=0.025) of the Armitage–McPherson–Rowe peeking problem:
    # Pocock constant for K=14 at α=0.05 → nominal 0.0089; naive p<0.05 on 14 looks → 22.0 % false positives.
    assert peek["pocock_alpha_per_look"] == pytest.approx(0.0089, abs=2e-4)
    assert peek["naive_false_positive_rate_pct"] == pytest.approx(22.0, abs=0.3)
    assert peek["recommended_alpha"] == pytest.approx(0.0089, abs=2e-4)
    assert 0.020917 > peek["recommended_alpha"]  # the day-14 "win" is not a win after peeking

    rev = run("ab-test-analyst", "continuous_metric_test", control_mean=84.2, control_sd=61.5, control_n=612, variant_mean=81.9, variant_sd=58.8, variant_n=689)
    assert rev["t"] == pytest.approx(-0.6873, abs=1e-4)  # scipy ttest_ind_from_stats(equal_var=False): -0.687312
    assert rev["p_value"] == pytest.approx(0.492012, abs=1e-5)  # scipy: 0.4920123
    assert rev["df"] == pytest.approx(1265.2, abs=0.1)  # Welch–Satterthwaite: 1265.24
    assert rev["difference_ci"] == pytest.approx([-8.865, 4.265], abs=1e-3)  # scipy t.ppf: -8.86505, 4.26505


def test_ab_sample_size_vs_evan_miller_reference():
    # Evan Miller's published defaults (defaults.js: 20 % baseline, 5 pp absolute MDE, α 0.05, power 0.8) → 1,030.
    # Our pooled-variance formula gives 1,094; a 400k-run simulation of the pooled z-test gives power 0.800 at 1,094
    # and 0.778 at 1,030, so 1,094 is the size that actually delivers the promised 80 %.
    out = run("ab-test-analyst", "sample_size", baseline_rate_pct=20, mde_absolute_pp=5)
    assert out["visitors_per_arm"] == 1094
    assert "1,030" in out["method"]


# ─────────────────────────────── ad-copy-lab ───────────────────────────────
RSA_HEADLINES = [
    "Freelance Invoicing Made Fast", "Freelance Invoicing, 2 Clicks", "Tallyo Freelance Invoicing", "Get Paid 9 Days Sooner",
    "Auto Payment Reminders", "Trusted by 41,000 Freelancers", "Rated 4.8 by 2,300 Reviews", "No Credit Card to Start",
    "Import Clients From Excel", "Tired of Chasing Late Pay?", "Built for Freelancers", "Cheaper Than FreshBooks",
    "Try Tallyo Free for 30 Days", "Start Your Free Trial Today", "Send Invoices From Your Phone",
]
RSA_DESCRIPTIONS = [
    "Create a branded invoice in 60 seconds and let Tallyo chase late payers for you.",
    "41,000 freelancers get paid 9 days sooner on average. Start free, no card needed.",
    "Cards, bank transfer and Apple Pay on every invoice. Taxes calculated automatically.",
    "Switch from spreadsheets in 5 minutes: import clients and past invoices in one go.",
]


def test_ad_scenario_economics():
    m = run("ad-copy-lab", "ad_math", daily_budget=120, cpc=3.10, cvr_pct=4.2, aov=180, margin_pct=85, ctr_pct=5, target_profit_share_pct=20)
    # Hand: clicks 120/3.1 = 38.71; conv 1.6258; CPA 3.1/0.042 = 73.81; ROAS 292.65/120 = 2.4387; BE ROAS 1/0.85 = 1.176;
    # BE CPA 153; target CPA 122.4; max CPC 5.1408; net 128.748/day; ceil(50/1.6258) = 31 days; impressions 774.
    assert m["daily"]["clicks"] == 38.7 and m["daily"]["conversions"] == 1.63 and m["daily"]["net_after_ads"] == 128.75
    assert (m["cpa"], m["roas"], m["break_even_roas"], m["break_even_cpa"]) == (73.81, 2.44, 1.18, 153.0)
    assert (m["target_cpa"], m["max_cpc_for_target"], m["days_to_50_conversions"]) == (122.4, 5.14, 31)
    assert m["break_even_cpc"] == pytest.approx(6.43, abs=0.01)  # 153 × 0.042 = 6.426
    assert m["daily"]["impressions"] == 774 and m["profitable"] is True


def test_ad_scenario_limits_pins_angles():
    v = run("ad-copy-lab", "validate_platform_copy", platform="google_rsa", headlines=RSA_HEADLINES, descriptions=RSA_DESCRIPTIONS,
            paths=["invoicing", "freelancers"], pins={"h1": [1], "h3": [1]}, keyword="freelance invoicing")
    assert v["ready"] is True and v["issues"] == []
    assert max(r["chars"] for r in v["headlines"]) == 29  # len() of the longest headline
    # itertools.permutations: position 1 ∈ {h1, h3}, positions 2-3 from the 13 unpinned → 2·13·12 = 312; × 4·3 descriptions
    assert v["rsa_combinations"] == 3744 and v["rsa_combinations_unpinned"] == 32760
    assert v["headlines_with_keyword"] == [1, 2, 3]
    # A single pinned asset gets Google's "pin 2-3 per position" advice.
    one = run("ad-copy-lab", "validate_platform_copy", platform="google_rsa", headlines=RSA_HEADLINES, descriptions=RSA_DESCRIPTIONS, pins={"h1": [1]})
    assert any("2-3 unique assets" in i for i in one["issues"])

    a = run("ad-copy-lab", "angle_coverage", lines=RSA_HEADLINES, keyword="freelance invoicing", brand="Tallyo")
    assert a["angle_counts"].get("generic", 0) == 0 and a["meets_bar"] is True
    assert a["angles_covered"] >= 5


def test_ad_scoring_does_not_apply_email_spam_words_to_ads():
    ok = run("ad-copy-lab", "score_ad_copy", line="No Credit Card to Start", max_chars=30)
    assert not any("risk" in r for r in ok["reasons"])
    risky = run("ad-copy-lab", "score_ad_copy", line="Guaranteed Paid in 24 Hours", max_chars=30)
    assert risky["grade"] != "ship" and any("claim risk" in r for r in risky["reasons"])


# ─────────────────────────────── brand-voice ───────────────────────────────
BV_SAMPLES = [
    "Your books shouldn't eat your Sunday. That's the whole idea behind Fernhill. You snap a receipt, we match it to the bank line, and the category is already there when you look. No shoebox. No spreadsheet with seven tabs. If something doesn't match, you'll see it in one list, not buried in a report. Most cafés we work with close their month in under an hour. That's not magic. It's just fewer steps.",
    "Here's what changed this month. You can now split a single receipt across two categories. Bought milk and a new grinder on one card swipe? Split it in two taps. We also made the cash-up screen faster on older phones. It loads in about a second now. If you run more than one site, you'll find each one has its own tab. Your accountant sees the same numbers you do.",
    "Tax day doesn't have to be a scramble. Start with the checklist in your dashboard. It tells you what's missing, in plain words. Then send your accountant one link instead of forty attachments. They'll see every receipt, every bank line and every note you left. You won't have to explain the same coffee order twice. And if you're not sure what counts as an expense, ask us. We answer within a day.",
    "We don't think bookkeeping should need a course. So we cut the jargon. You'll never see the word ledger on your home screen. You'll see money in, money out, and what you owe. Behind that, the numbers still add up the way your accountant expects. Try it for a month. If it doesn't save you an evening, cancel in two clicks and keep your data.",
]
BV_DRAFT = (
    "Fernhill is pleased to announce a robust new reporting solution that will enable users to leverage their financial data more "
    "effectively. The reports have been redesigned by our team in order to facilitate a comprehensive understanding of business "
    "performance. It is recommended that users explore the new functionality at their earliest convenience! Fernhill remains "
    "committed to delivering innovative tools for hospitality businesses."
)
BV_REWRITE = (
    "Your reports just got simpler. We rebuilt them so money in, money out and what you owe sit on one screen. Tap any number and "
    "you'll see the receipts behind it. No export, no pivot table. It's in your dashboard today. Take a look when you close this "
    "month, and tell us what's missing."
)


def test_brand_voice_scenario():
    prof = run("brand-voice", "extract_voice_profile", samples=BV_SAMPLES, brand_name="Fernhill")
    p = prof["profile"]
    # Independent count (whitespace tokens, sentences split on . ? !): 280 tokens — the shared tokenizer now counts
    # "cash-up"/"one-card" as one word each, like Word, so the tool matches it exactly;
    # 32 sentences, 17 contractions and 0 expandable forms → 100 %; "you"-family incl. you'll/you're = 23 → 8.2 per 100.
    assert p["sentences"] == 32 and p["words"] == 280
    assert p["avg_sentence_words"] == pytest.approx(8.75, abs=0.06)  # 280/32
    assert p["contraction_rate_pct"] == 100.0
    assert p["pronouns_per_100"]["you"] == pytest.approx(8.2, abs=0.1)
    assert max(p["pronouns_per_100"], key=p["pronouns_per_100"].get) == "you"
    assert not any("'" in w for w in prof["signature_words"])  # contractions are not "signature vocabulary"

    before = run("brand-voice", "score_against_profile", draft=BV_DRAFT, profile=p, banned_terms=["leverage", "solution", "robust"])
    dm = before["draft_metrics"]
    assert (dm["words"], dm["sentences"], dm["avg_sentence_words"]) == (62, 4, 15.5)  # independent: 62 tokens / 4 sentences
    assert dm["contraction_rate_pct"] == 0.0 and dm["pronouns_per_100"]["they"] == pytest.approx(3.23, abs=0.01)  # 2/62
    assert before["grade"] == "off-brand" and {b["term"] for b in before["banned_hits"]} == {"leverage", "solution", "robust"}
    after = run("brand-voice", "score_against_profile", draft=BV_REWRITE, profile=p, banned_terms=["leverage", "solution", "robust"])
    assert after["score"] >= 80 and after["grade"] == "on-voice"

    lex = run("brand-voice", "lexicon_check", content=BV_DRAFT, banned_terms=["leverage", "solution", "robust"], preferred_terms={"users": "you"},
              proper_casing=["Fernhill"], use_carefully={"innovative": "only with a named first"})
    pos = [(f["type"], f["term"], f["position"]) for f in lex["findings"]]
    # re.finditer on the lower-cased draft: robust@34, solution@55, users@81, leverage@90, users@284; innovative@372
    assert ("banned", "robust", 34) in pos and ("banned", "solution", 55) in pos and ("banned", "leverage", 90) in pos
    assert ("preferred", "users", 81) in pos and ("preferred", "users", 284) in pos
    assert any(t == "use_carefully" and term == "innovative" for t, term, _ in pos)
    inc = run("brand-voice", "lexicon_check", content="Hey guys, add the domain to the whitelist.")
    assert {f["term"].lower() for f in inc["findings"] if f["type"] == "inclusive"} == {"guys", "whitelist"}


# ─────────────────────────────── email-campaign ───────────────────────────────
EMAIL_BODY = (
    "Hi {{first_name|there}},\n\nIf you run more than one café, you probably close each site on its own and then stitch the numbers "
    "together in a spreadsheet. That's the part we just deleted.\n\nMulti-site reports put money in, money out and what you owe for every "
    "location on one screen. Tap a site to see its receipts. Tap a number to see where it came from. Your accountant gets the same view "
    "with one link.\n\nOwners in our beta closed three sites in 41 minutes on average, down from about two hours.\n\n[Open multi-site reports]"
    "\n\nOr paste this into your browser: https://app.fernhill.example/reports/sites\n\nP.S. It's included in your current plan. Nothing to "
    "switch on.\n\nFernhill, 214 Harbor Street, Suite 5, Portland, OR 97204\nManage preferences or unsubscribe: https://app.fernhill.example/unsubscribe"
)


def test_email_scenario():
    subj = run("email-campaign", "test_subject_line", subject="Every café, one report",
               preheader="See money in, money out and what you owe for all your sites on one screen.",
               alternatives=["New: multi-site reports are here!", "Close 3 sites in the time it took for 1", "Is site #2 quietly losing money?",
                             "FREE multi-site reporting for your cafés", "{{first_name}}, your sites in one view"])
    assert subj["primary"]["chars"] == 22 and subj["primary"]["preheader"]["chars"] == 74  # len()
    assert subj["recommended_ab_pair"] == ["Is site #2 quietly losing money?", "Close 3 sites in the time it took for 1"]
    free = next(r for r in subj["ranked"] if r["subject"].startswith("FREE"))
    assert any("ALL-CAPS word" in f for f in free["flags"])
    tok = next(r for r in subj["ranked"] if r["subject"].startswith("{{"))
    assert tok["chars"] == len("Jessica, your sites in one view")  # tokens measured as a rendered 7-char name

    scan = run("email-campaign", "scan_email_body", body=EMAIL_BODY, available_fields=["first_name", "company"])
    assert scan["merge_tokens"] == ["first_name"]  # the {{name|fallback}} form is recognised
    assert scan["undefined_tokens"] == [] and scan["issues"] == [] and scan["deliverability_risk"] == "low"
    bad = run("email-campaign", "scan_email_body", body=EMAIL_BODY.replace("{{first_name|there}}", "{{frist_name|there}}"), available_fields=["first_name"])
    assert bad["undefined_tokens"] == ["frist_name"]

    sched = run("email-campaign", "send_schedule", first_send_date="2026-10-13", pattern="launch", email_count=3, audience="b2b")
    # calendar.day_name: 10-13 Tue, 10-15 Thu, 10-18 Sun → shifted to Mon 10-19
    assert [(s["send"], s["weekday"]) for s in sched["sends"]] == [("2026-10-13", "Tuesday"), ("2026-10-15", "Thursday"), ("2026-10-19", "Monday")]
    assert sched["sends"][2]["shifted_because"] == ["weekend"]

    m = run("email-campaign", "campaign_metrics", sent=8400, delivered=8232, unique_opens=3120, unique_clicks=402, unsubscribes=19, spam_complaints=3, conversions=57)
    r = m["rates"]
    # Hand: 8232/8400 = 98.0; 3120/8232 = 37.90; 402/8232 = 4.883; 402/3120 = 12.885; 19/8232 = 0.2308; 3/8232 = 0.0364; 57/402 = 14.18
    assert (r["delivery_rate_pct"], r["open_rate_pct"], r["click_rate_pct"], r["click_to_open_rate_pct"]) == (98.0, 37.9, 4.88, 12.88)
    assert (r["unsubscribe_rate_pct"], r["complaint_rate_pct"], r["click_to_conversion_pct"]) == (0.231, 0.036, 14.18)


# ─────────────────────────────── landing-page-cro ───────────────────────────────
LP_PAGE = (
    "Reimagining workforce management for modern hospitality\n"
    "Our innovative platform empowers teams with seamless, end-to-end scheduling solutions.\n"
    "[Get started] [Book a demo] [Watch video]\nWhy Shiftly?\n"
    "We built Shiftly because we believe scheduling should be effortless. Our AI-powered engine leverages historical sales data to "
    "optimize labor allocation across locations. We integrate with leading POS systems and our dashboard provides real-time insights.\n"
    "Features\nDrag-and-drop rota builder. Shift swaps approved from your phone. Labor cost shown against forecast sales. Tip pooling and overtime alerts.\n"
    "Trusted by 1,200 restaurants\n\"We cut our weekly scheduling time from 5 hours to 40 minutes.\" Dana Ruiz, GM, Harbor Grill\n"
    "Pricing from $4 per staff member per month. Free trial.\n[Get started]"
)


def test_landing_page_scenario():
    audit = run("landing-page-cro", "audit_page", page_text=LP_PAGE, form_fields=7, nav_links=6, load_time_seconds=3.8, has_video=True,
                traffic_source="google ads: restaurant staff scheduling app")
    assert audit["grade"] == "D"
    assert audit["stats"]["message_match_ratio"] == 0.25  # {restaurant, staff, scheduling, app} ∩ hero = {scheduling} → 1/4
    assert audit["stats"]["ctas_detected"] == ["book a demo", "get started", "watch video"]
    assert audit["fixes"][0].startswith("Speed: 3.8s")

    old = run("landing-page-cro", "headline_clarity", headline="Reimagining workforce management for modern hospitality",
              subheadline="Our innovative platform empowers teams with seamless, end-to-end scheduling solutions.", cta_label="Get started")
    new = run("landing-page-cro", "headline_clarity", headline="Build next week’s restaurant rota in 20 minutes",
              subheadline="Shiftly is a rota app that shows labor cost next to forecast sales. 1,200 restaurants use it to stay on budget.",
              cta_label="Start my free trial")
    assert old["grade"] == "F" and new["grade"] == "A" and new["passed"] == "10/10"

    f = run("landing-page-cro", "funnel_leaks", steps=[{"name": "visits", "count": 22000}, {"name": "pricing views", "count": 5300},
                                                       {"name": "trial starts", "count": 528}, {"name": "paid", "count": 118}], value_per_final_conversion=190)
    # Hand: 5300/22000 = 24.09 %; 528/5300 = 9.96 %; 118/528 = 22.35 %; overall 0.536 %; 4772 × 118/528 = 1066.5; 10 % fix = 11.8 → $2,242
    assert [s.get("step_conversion_pct") for s in f["steps"][1:]] == [24.09, 9.96, 22.35]
    assert f["overall_conversion_pct"] == 0.536
    assert f["biggest_leak_by_lost_conversions"] == {"step": "trial starts", "lost_users": 4772, "final_conversions_lost": 1066.5}
    assert f["value_of_10pct_fix_at_biggest_leak"] == {"extra_final_conversions": 11.8, "extra_value": 2242.0}

    lv = run("landing-page-cro", "lift_value", monthly_visitors=22000, current_cvr_pct=2.4, target_cvr_pct=2.9, value_per_conversion=42.5)
    assert (lv["extra_conversions_per_month"], lv["extra_revenue_per_month"], lv["extra_revenue_over_horizon"]) == (110.0, 4675.0, 56100.0)

    ts = run("landing-page-cro", "test_sample_size", baseline_cvr_pct=2.4, expected_relative_lift_pct=20, monthly_visitors=22000)
    assert ts["visitors_per_variant"] == 17511  # Fleiss by hand: 17,510.98
    assert ts["weeks_needed"] == 7  # 35,022 / (22,000 / 4.345) = 6.92
    assert "≥ 22% lift" in ts["recommendation"]  # ceil(20 × √(6.92/6)) = 22


# ─────────────────────────────── launch-planner ───────────────────────────────


def test_launch_scenario():
    cd = run("launch-planner", "countdown_timeline", launch_date="2026-11-10", size="medium", today="2026-09-28")
    assert cd["runway_business_days"] == 31 and cd["runway_calendar_days"] == 43  # numpy.busday_count(09-29, 11-11) = 31
    assert cd["compressed"] is False and cd["warnings"] == []
    by = {m["milestone"][:30]: m["date"] for m in cd["milestones"]}
    # numpy.busday_offset(2026-11-10, -k, roll="backward"): T-30 09-29, T-25 10-06, T-10 10-27, T-5 11-03, T-2 11-06, T-1 11-09; T+5 11-17
    assert by["Positioning, message hierarchy"] == "2026-09-29"
    assert by["Pricing / packaging final; bil"] == "2026-10-06"
    assert by["Embargoed press pitch sent"] == "2026-10-27"
    assert by["Final QA of every link, UTM an"] == "2026-11-06"
    assert by["T+7: retro — goal vs actual, w"] == "2026-11-17"

    ch = run("launch-planner", "channel_checklist", channels=["landing_page", "blog", "email", "product_hunt", "linkedin", "press", "in_app", "support"], launch_date="2026-11-10")
    finals = {c["channel"]: c["final_by"] for c in ch["channels"]}
    assert finals["press"] == "2026-10-20" and finals["landing_page"] == "2026-10-30" and finals["linkedin"] == "2026-11-06"  # T-15, T-7, T-2
    assert ch["total_assets"] == 31

    tg = run("launch-planner", "launch_targets", goal=900, channels=[
        {"channel": "email", "reach": 14000, "engagement_pct": 4.5, "conversion_pct": 22},
        {"channel": "product_hunt", "reach": 9000, "engagement_pct": 30, "conversion_pct": 6},
        {"channel": "linkedin", "reach": 6500, "engagement_pct": 1.8, "conversion_pct": 9},
        {"channel": "press", "reach": 40000, "engagement_pct": 0.8, "conversion_pct": 8},
        {"channel": "in_app", "reach": 3100, "engagement_pct": 12, "conversion_pct": 35}])
    assert tg["projected_signups"] == 466.9 and tg["gap"] == 433.1  # hand: 138.6 + 162 + 10.53 + 25.6 + 130.2 = 466.93

    rd = run("launch-planner", "readiness_score", items=[
        {"item": "Multi-site reports on production behind flag", "priority": "P0", "status": "done", "owner": "Ana"},
        {"item": "Billing: per-site add-on tested", "priority": "P0", "status": "in_progress", "owner": "Raj"},
        {"item": "Landing page live with tracking verified", "priority": "P0", "status": "done", "owner": "Mei"},
        {"item": "Support FAQ + macros", "priority": "P0", "status": "done", "owner": "Tom"},
        {"item": "Rollback plan written", "priority": "P0", "status": "not_started", "owner": ""},
        {"item": "PH gallery images", "priority": "P1", "status": "done", "owner": "Mei"},
        {"item": "Customer quote (Harbor Grill)", "priority": "P1", "status": "in_progress", "owner": "Sam"},
        {"item": "LinkedIn carousel", "priority": "P2", "status": "not_started", "owner": "Sam"},
        {"item": "Launch email scheduled", "priority": "P1", "status": "done", "owner": "Mei"}])
    assert rd["score"] == 71 and rd["decision"] == "NO-GO"  # (15 + 2.5 + 7.5) / 35 = 71.4 %
    assert rd["unowned_open_items"] == ["Rollback plan written"]


def test_launch_day_product_hunt_time_follows_real_dst():
    # zoneinfo: 12:01 AM PT on 2026-11-10 (PST) is 03:01 ET → 359 min before a 09:00 ET go-live.
    nov = run("launch-planner", "launch_day_schedule", launch_datetime="2026-11-10T09:00:00-05:00", audience_utc_offsets=[-8, -5, 0, 1], product_hunt=True)
    assert nov["steps"][0]["offset_minutes"] == -359 and nov["steps"][0]["launch_tz_time"] == "03:01"
    # 2027-03-03 is before DST starts (2027-03-14): still PST, so still 03:01 ET. The old month-based rule said PDT (02:01).
    mar = run("launch-planner", "launch_day_schedule", launch_datetime="2027-03-03T09:00:00-05:00", product_hunt=True)
    assert mar["steps"][0]["offset_minutes"] == -359


# ─────────────────────────────── marketing-budget ───────────────────────────────


def test_budget_scenario():
    c = run("marketing-budget", "ltv_and_cac_ceiling", arpu_monthly=79, gross_margin_pct=78, monthly_churn_pct=3.5, current_cac=212)
    # Hand: 79 × 0.78 / 0.035 = 1760.57; /3 = 586.86; 212 / 61.62 = 3.44 mo; 1760.57/212 = 8.30
    assert (c["ltv"], c["max_cac_at_target_ratio"], c["payback_months"], c["ltv_to_cac"]) == (1760.57, 586.86, 3.4, 8.3)

    e = run("marketing-budget", "channel_economics", ltv=1760.57, gross_margin_pct=78, arpu_monthly=79, channels=[
        {"channel": "Google Search", "spend": 18000, "customers": 120, "tag": "core"},
        {"channel": "Meta", "spend": 10000, "customers": 45, "tag": "core"},
        {"channel": "LinkedIn", "spend": 6000, "customers": 12, "tag": "emerging"},
        {"channel": "Content/SEO", "spend": 2000, "fixed_costs": 4000, "customers": 30, "tag": "emerging"}])
    cac = {r["channel"]: r["cac_fully_loaded"] for r in e["channels"]}
    assert cac == {"Google Search": 150.0, "Meta": 222.22, "LinkedIn": 500.0, "Content/SEO": 200.0}
    assert e["totals"]["blended_cac"] == 193.24  # 40,000 / 207
    assert e["reallocation"] == {"from": "LinkedIn", "to": "Google Search", "amount": 1800.0, "expected_extra_customers": 8.4,
                                 "note": e["reallocation"]["note"]}  # 1800/150 − 1800/500 = 8.4

    # Proportional-with-bounds: scipy brentq on Σ clamp(λ·w, min, max) = total → G 14,937.08 · M 10,082.02 · L 4,480.90 · C 8,000
    a = run("marketing-budget", "allocate_budget", total=40000, channels=[
        {"channel": "Google Search", "weight": 0.006667, "max": 24000, "tag": "core"},
        {"channel": "Meta", "weight": 0.0045, "max": 13000, "tag": "core"},
        {"channel": "LinkedIn", "weight": 0.002, "min": 3000, "max": 6000, "tag": "emerging"},
        {"channel": "Content/SEO", "weight": 0.005, "min": 6000, "max": 8000, "tag": "emerging"},
        {"channel": "TikTok test", "weight": 0, "min": 2500, "max": 2500, "tag": "experimental"}])
    amt = {r["channel"]: r["amount"] for r in a["allocation"]}
    assert amt["Google Search"] == pytest.approx(14937.08, abs=0.02) and amt["Meta"] == pytest.approx(10082.02, abs=0.02)
    assert amt["LinkedIn"] == pytest.approx(4480.90, abs=0.02) and amt["Content/SEO"] == 8000.0 and amt["TikTok test"] == 2500.0
    assert sum(amt.values()) == pytest.approx(40000, abs=0.01)

    p = run("marketing-budget", "pacing_check", budget=40000, spent_to_date=21300, period_start="2026-10-01", period_end="2026-10-31", as_of="2026-10-14")
    # Hand: expected 40,000 × 14/31 = 18,064.52; pace 1.179; projected 47,164.29; (40,000 − 21,300)/17 = 1,100/day
    assert (p["expected_spend_to_date"], p["pace_ratio"], p["projected_end_spend"], p["daily_budget_to_land_on_plan"]) == (18064.52, 1.179, 47164.29, 1100.0)
    assert p["status"] == "over pace"

    g = run("marketing-budget", "growth_projection", monthly_budget=40000, cac=193.24, arpu_monthly=79, gross_margin_pct=78,
            monthly_churn_pct=3.5, months=12, starting_customers=1450, cac_inflation_pct_per_month=2)
    # Independent month loop: month-1 cumulative +58,976.91 (so break-even is month 1, not 2); month 12: 2,779.54 customers,
    # MRR 219,583.70, cumulative 1,192,248.76; the budget's own cohort pays back in month 6 (cohort cum. 335,254.38 at m12).
    assert g["breakeven_month"] == 1
    assert g["end_customers"] == pytest.approx(2779.5, abs=0.1) and g["end_mrr"] == pytest.approx(219583.70, abs=0.05)
    assert g["cumulative_contribution"] == pytest.approx(1192248.76, abs=0.05)
    assert g["acquired_cohort_breakeven_month"] == 6
    assert g["acquired_cohort_cumulative_contribution"] == pytest.approx(335254.38, abs=0.05)


# ─────────────────────────────── persona-builder ───────────────────────────────
PAIN_TABLE = {"1 site": {"cash-up": 30, "staff rota": 12, "multi-site reporting": 10, "tax prep": 18},
              "2-5 sites": {"cash-up": 12, "staff rota": 10, "multi-site reporting": 25, "tax prep": 8},
              "6+ sites": {"cash-up": 3, "staff rota": 7, "multi-site reporting": 12, "tax prep": 3}}


def _survey_rows():
    tools = ["Excel;QuickBooks", "Excel", "QuickBooks;Square", "Square", "Xero;Excel"]
    roles = ["Owner", "Owner", "GM", "Owner", "Finance lead"]
    rows, i = [], 0
    for size, pains in PAIN_TABLE.items():
        for pain, n in pains.items():
            for _ in range(n):
                rows.append({"sites": size, "top_pain": pain, "role": roles[i % 5], "tools": tools[i % 5], "hours_on_books_per_week": 2 + (i * 7) % 11})
                i += 1
    return rows


def test_persona_scenario():
    rows = _survey_rows()
    t = run("persona-builder", "tally_survey", responses=rows)
    assert t["responses"] == 150
    tools = {x["answer"]: x["pct"] for x in t["fields"]["tools"]["top"]}
    assert tools == {"Excel": 60.0, "QuickBooks": 40.0, "Square": 40.0, "Xero": 20.0}  # 3/5, 2/5, 2/5, 1/5 of respondents
    assert t["fields"]["role"]["top"][0] == {"answer": "Owner", "count": 90, "pct": 60.0}

    x = run("persona-builder", "cross_tab", responses=rows, row_field="sites", col_field="top_pain")
    # scipy.stats.chi2_contingency(correction=False): χ² 23.998, df 6, p 0.000523, 2 expected cells < 5; Cramér's V 0.2828
    assert x["chi_square"] == pytest.approx(23.998, abs=1e-3) and x["df"] == 6
    assert x["p_value"] == pytest.approx(0.00052, abs=1e-5) and x["cramers_v"] == pytest.approx(0.283, abs=1e-3)
    assert x["significant_at_05"] is True
    # Adjusted standardised residuals (numpy): 1 site × reporting −4.21, 1 site × cash-up +3.21, 2-5 × reporting +2.84,
    # 6+ × cash-up −2.15, 6+ × reporting +1.97 — the five |r| > 1.96 cells.
    cells = {(c["row"], c["col"]): c["adjusted_residual"] for c in x["significant_cells"]}
    assert cells == {("1 site", "multi-site reporting"): -4.21, ("1 site", "cash-up"): 3.21, ("2-5 sites", "multi-site reporting"): 2.84,
                     ("6+ sites", "cash-up"): -2.15, ("6+ sites", "multi-site reporting"): 1.97}
    first = next(r for r in x["table"] if r["row"] == "1 site")
    assert first["col_pct"]["cash-up"] == 66.7 and first["pct_of_total"]["cash-up"] == 20.0  # 30/45, 30/150

    j = run("persona-builder", "format_jtbd", situation="when I close the month across my three cafés", motivation="see every site side by side",
            outcome="spot the losing site before it costs me another month", persona="Maya", product_names=["Fernhill"])
    assert j["jtbd_statement"].startswith("When I close the month")  # not "When i close"
    assert j["job_story"] == "When they close the month across their three cafés, Maya wants to see every site side by side, so they can spot the losing site before it costs them another month."
    assert j["ready"] is True


# ─────────────────────────────── positioning-strategist ───────────────────────────────


def test_positioning_scenario():
    cv = run("positioning-strategist", "canvas_check", canvas={
        "competitive_alternatives": ["Spreadsheet rota shared on WhatsApp", "Scheduling module bundled with the POS", "Enterprise workforce-management suites"],
        "unique_attributes": ["Shows labor cost against forecast sales while you build the rota", "Reads sales history directly from the POS, no CSV export",
                              "Shift swaps approved from the phone in one tap", "Easy to use"],
        "value": ["Managers keep labor at target % of sales: pilot sites cut labor cost 2.1 points in 8 weeks", "Rota built in 40 minutes instead of 5 hours (Harbor Grill)"],
        "best_fit_customers": ["Independent restaurant groups with 2-15 sites who already track labor % weekly", "GMs who build rotas themselves and use a cloud POS"],
        "market_category": "Labor-cost scheduling for independent restaurant groups"})
    assert cv["category_kind"] == "subsegment" and cv["gaps"] == [] and [v["item"] for v in cv["vague_claims"]] == ["Easy to use"]

    dm = run("positioning-strategist", "differentiation_matrix", competitors=["Spreadsheet", "POS module", "Enterprise suite"], attributes=[
        {"attribute": "Labor cost vs forecast while scheduling", "us": 5, "competitors": {"Spreadsheet": 1, "POS module": 2, "Enterprise suite": 4}, "importance": 5},
        {"attribute": "POS sales history read directly", "us": 5, "competitors": {"Spreadsheet": 0, "POS module": 5, "Enterprise suite": 3}, "importance": 4},
        {"attribute": "Multi-site labor reporting", "us": 4, "competitors": {"Spreadsheet": 1, "POS module": 1, "Enterprise suite": 5}, "importance": 5},
        {"attribute": "Payroll built in", "us": 0, "competitors": {"Spreadsheet": 0, "POS module": 2, "Enterprise suite": 5}, "importance": 2}])
    cls = {r["attribute"]: r["class"] for r in dm["matrix"]}
    # Hand, per the Dunford rules in the playbook: gap vs best alternative +1 & importance 5 → lead; 0 & 4 → table stakes;
    # −1 & 5 → fix or reframe; −5 & 2 → irrelevant. Index = Σ imp·max(0,gap)/5 ÷ Σ imp = 1 / 16 → 6.
    assert cls == {"Labor cost vs forecast while scheduling": "lead", "POS sales history read directly": "table stakes",
                   "Multi-site labor reporting": "fix or reframe", "Payroll built in": "irrelevant"}
    assert dm["differentiation_index"] == 6

    st = run("positioning-strategist", "positioning_statement", target="restaurant groups with 2-15 sites who track labor % weekly",
             need="need to hit their labor target without a spreadsheet", product="Shiftly", category="labor-cost scheduling app",
             key_benefit="keeps labor within 1 point of target", primary_alternative="spreadsheet rotas and POS add-ons",
             differentiator="read sales straight from your POS and price every shift before you publish")
    assert st["moore_statement"].startswith("For restaurant groups with 2-15 sites who track labor % weekly and need to hit")
    assert st["x_for_y"] == "Shiftly is a labor-cost scheduling app for restaurant groups with 2-15 sites who track labor % weekly."
    assert st["word_counts"]["moore"] <= 60

    mc = run("positioning-strategist", "message_clarity", messages=["The all-in-one workforce platform for modern hospitality",
                                                                  "Shiftly: the labor-cost scheduling app for restaurant groups"])
    assert mc["best"] == "Shiftly: the labor-cost scheduling app for restaurant groups"
    assert next(r for r in mc["ranked"] if r["message"].startswith("The all-in-one"))["competitor_could_say_it"] is True


# ─────────────────────────────── press-release ───────────────────────────────
PR_DRAFT = """Fernhill Raises $6.5 Million to Help Independent Cafés Close Their Books Faster
PORTLAND, Oregon, October 13, 2026 — Fernhill, the bookkeeping app for independent cafés, today announced a $6.5 million seed round led by Harbor Light Ventures to expand its multi-site reporting to restaurant groups across the U.S.

More than 4,800 cafés use Fernhill to match receipts to bank lines automatically. The company will use the funding to double its team to twenty-four people.

"Café owners shouldn't lose a Sunday every month to spreadsheets," stated Priya Nair, Chief Executive Officer of Fernhill. "This round lets us build the reporting multi-site owners have been asking for!"

The company has customers in Portland, OR, Austin, Texas, and Denver.
"""


def test_press_release_scenario():
    lint = run("press-release", "ap_style_check", content=PR_DRAFT)
    found = {(f["rule"], f["found"]) for f in lint["findings"]}
    assert ("dateline: abbreviate the state", "PORTLAND, Oregon") in found  # AP: Ore. in datelines
    assert ("dates: abbreviate month with a date", "October 13") in found
    assert ("numerals: use figures for 10 and above", "twenty") in found
    assert ("attribution: use 'said'", '" stated') in found
    assert ("punctuation: no exclamation marks", "!") in found
    assert ("states: no postal codes in text", "Portland, OR") in found
    # "Austin, Texas, and Denver": the comma closes "City, State," — not an Oxford comma; Texas is never abbreviated.
    assert not any(r.startswith("punctuation: no Oxford") for r, _ in found)
    assert not any("Texas" in f and r.startswith(("states", "dateline")) for r, f in found)

    sf = run("press-release", "ap_style_check", content="SAN FRANCISCO, Calif., Oct. 13, 2026 — Fernhill opened an office in Portland, Ore. today.")
    rules = {f["rule"] for f in sf["findings"]}
    assert rules == {"dateline: this city stands alone", "states: spell out the state in body text"}  # AP 2014 rule

    emb = run("press-release", "embargo_timing", embargo_lift="2026-10-13T06:00:00-04:00", audience_utc_offsets=[-4, -7, 1])
    steps = {s["step"][:20]: s["date"] for s in emb["schedule"]}
    # numpy.busday_offset(2026-10-13, −6 / −2 / −9): 10-05 Mon, 10-09 Fri, 09-30 Wed; zoneinfo: 03:00 PT, 11:00 London
    assert steps["Send embargoed pitch"] == "2026-10-05" and steps["Single follow-up (re"] == "2026-10-09"
    assert steps["Offer exclusive to t"] == "2026-09-30"
    assert emb["lift_in_audience_zones"] == {"UTC-4": "Tue 2026-10-13 06:00", "UTC-7": "Tue 2026-10-13 03:00", "UTC+1": "Tue 2026-10-13 11:00"}
    assert not any("ET —" in w for w in emb["warnings"])  # 06:00 EDT is inside the 6-10 a.m. ET window

    pitch = run("press-release", "pitch_email_check", subject="Embargoed: café bookkeeping app Fernhill raises $6.5M",
                body="Hi Maria,\n\nYour piece on how independent coffee shops are coping with card fees stuck with me.\n\nFernhill, a bookkeeping app "
                     "used by 4,800 independent cafés, has raised a $6.5 million seed round. For your readers who run small food businesses, it is a "
                     "concrete look at where the admin time goes.\n\nThe news is embargoed until Tuesday, Oct. 13, at 6 a.m. ET. Would you be "
                     "interested in a 20-minute briefing with CEO Priya Nair?\n\nLena Brooks", journalist_name="Maria Chen", outlet="Plate & Pour")
    assert pitch["subject_chars"] == 53 and pitch["grade"] == "send"  # len(subject) = 53
