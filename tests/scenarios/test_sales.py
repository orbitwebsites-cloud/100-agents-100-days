"""Sales category — replayable customer scenarios (see evals/sales.md).

Each test replays the exact tool calls the customer's AI made while following the agent's
playbook on a realistic request, and asserts on values that were verified independently of
our code: by hand, or with the small stdlib helpers below (which deliberately do NOT import
anything from hundred.lib or the agents).
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta

from hundred import registry


def run(slug: str, tool: str, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ── independent reference helpers (stdlib only) ────────────────────────────────
def ref_business_days_between(a: str, b: str, holidays: tuple[str, ...] = ()) -> int:
    """Weekdays after `a` up to and including `b`, skipping holidays."""
    d, end, hol, n = date.fromisoformat(a), date.fromisoformat(b), {date.fromisoformat(h) for h in holidays}, 0
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in hol:
            n += 1
    return n


def ref_add_business_days(a: str, n: int, holidays: tuple[str, ...] = ()) -> str:
    d, hol = date.fromisoformat(a), {date.fromisoformat(h) for h in holidays}
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in hol:
            n -= 1
    return d.isoformat()


def ref_word_count(t: str) -> int:
    """How a person / word processor counts: whitespace tokens containing a letter or digit."""
    return sum(1 for tok in t.split() if re.search(r"[A-Za-z0-9]", tok))


def ref_speaker_share(transcript: str) -> dict[str, float]:
    words: dict[str, int] = {}
    for line in transcript.strip().splitlines():
        m = re.match(r"^(?:\[[\d:]+\]\s*)?([^:]+):\s(.*)$", line)
        words[m.group(1)] = words.get(m.group(1), 0) + ref_word_count(m.group(2))
    total = sum(words.values())
    return {k: 100 * v / total for k, v in words.items()}


def cents_half_up(x: float) -> float:
    from decimal import ROUND_HALF_UP, Decimal

    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ═══ 1. cold-email — vs Lavender Email Coach ═══════════════════════════════════
DRAFT = (
    "Hi {{first_name}},\n\nI hope this email finds you well. My name is Jordan and I'm reaching out from DockPilot. "
    "We are a leading provider of cutting-edge dock scheduling software that helps logistics companies streamline their "
    "operations and boost your efficiency.\n\nOur platform offers real-time dock visibility, automated carrier appointment "
    "booking, yard management integrations, detention tracking, and customizable reporting dashboards. We've worked with "
    "dozens of companies in the freight space and our customers love us.\n\nI'd love to set up a 30-minute demo to show "
    "you how DockPilot can help Fernbrook. You can book time on my calendar here: https://calendly.com/jordan-dockpilot/30min "
    "or just reply and let me know what works. You can also check out our website at www.dockpilot.io.\n\nThanks,\nJordan"
)
FINAL = (
    "Hi Priya,\n\nSaw Fernbrook posted three dispatcher openings this month. When a dock team grows that fast, missed "
    "appointments tend to show up as detention fees.\n\nHarlow Logistics had the same problem. After they moved dock booking "
    "into DockPilot, they cut detention fees 31% in eight weeks.\n\nWould it make sense to compare your numbers with theirs?\n\nJordan"
)


def test_cold_email_scenario():
    bad = run("cold-email", "audit_email_body", body=DRAFT, step=1)
    assert bad["words"] == ref_word_count(DRAFT) == 119  # URLs count as one word each
    assert bad["score"] < 40 and bad["links"] == 2 and bad["unresolved_tokens"] == ["{{first_name}}"]
    assert {"boost your", "cutting-edge", "leading provider"} <= set(bad["spam_words"])
    assert "i hope this email finds you well" in bad["fluff_phrases"]

    subj = run("cold-email", "score_subject_line", subjects=["Quick question about Fernbrook's dock operations!", "dispatcher hiring at Fernbrook", "Re: dock scheduling"])
    by = {r["subject"]: r for r in subj["results"]}
    assert by["dispatcher hiring at Fernbrook"]["chars"] == len("dispatcher hiring at Fernbrook") == 30
    assert by["Quick question about Fernbrook's dock operations!"]["score"] < 70 and by["Re: dock scheduling"]["score"] < 70

    good = run("cold-email", "audit_email_body", body=FINAL, step=1)
    assert good["words"] == ref_word_count(FINAL) == 58
    assert good["score"] >= 80 and good["cta_count"] == 1 and good["cta_type"] == "interest" and good["links"] == 0
    # FRE with dictionary syllable counts (hand-counted: 85 syllables, 7 sentence units incl. greeting/sign-off)
    ref_fre = 206.835 - 1.015 * (58 / 7) - 84.6 * (85 / 58)
    assert abs(good["flesch_reading_ease"] - ref_fre) <= 5 and good["flesch_reading_ease"] >= 60 and ref_fre >= 60

    pers = run("cold-email", "check_personalization", email="Subject: dispatcher hiring at Fernbrook\n" + FINAL,
               prospect={"first_name": "Priya", "company": "Fernbrook", "trigger": "three dispatcher openings"})
    assert pers["ready"] is True and pers["personalization_level"] == "deep"

    step2 = "Hi Priya,\n\nOne number from Harlow that may matter while you hire three dispatchers: carriers waited 41 minutes less per load once every dock slot was booked online.\n\nWant the one-page before/after for your team?\n\nJordan"
    s2 = run("cold-email", "audit_email_body", body=step2, step=2)
    assert s2["cta_count"] == 1 and s2["score"] >= 80  # a plain closing question counts as the ask

    sched = run("cold-email", "schedule_sequence", start_date="2026-10-06", gaps_days=[0, 3, 4, 5], holidays=["2026-10-12"])
    # hand-checked: Tue 6 → +3 = Fri 9 nudged to Thu 8 → +4 = Mon 12 (holiday) → Tue 13 → +5 = Sun 18 → Mon 19 → Tue 20
    assert [s["date"] for s in sched["steps"]] == ["2026-10-06", "2026-10-08", "2026-10-13", "2026-10-20"]
    assert all(date.fromisoformat(s["date"]).weekday() in (1, 2, 3) for s in sched["steps"])

    est = run("cold-email", "estimate_outreach", target_meetings=15, steps=4, days_available=20, sequence_span_days=14)
    p = 0.02 * 0.5 * 0.6
    assert est["prospects_needed"] == math.ceil(15 / p) == 2500
    assert est["list_size_incl_bounces"] == math.ceil(2500 / 0.97) == 2578
    assert est["total_sends"] == 10000 and est["mailboxes_needed"] == math.ceil(10000 / (50 * 20)) == 10
    # finishing every step inside 20 business days with a 10-business-day sequence: enrol in 10 days
    assert est["finish_inside_window"]["mailboxes_needed"] == math.ceil(math.ceil(2500 / 10) * 4 / 50) == 20


# ═══ 2. follow-up-machine — vs Regie.ai ═══════════════════════════════════════
def test_follow_up_scenario():
    dec = run("follow-up-machine", "next_touch_decision", stage="proposal", last_contact="2026-09-21", last_reply="2026-09-17",
              touches_since_reply=1, today="2026-09-28", promised_date="2026-09-24", deal_amount=42000)
    assert dec["decision"] == "follow_up_now"
    assert dec["business_days_since_last_touch"] == ref_business_days_between("2026-09-21", "2026-09-28") == 5
    assert dec["silent_days"] == (date(2026, 9, 28) - date(2026, 9, 17)).days == 11
    assert dec["channel"] == "phone" and "effort" in dec  # $42k → call/video before email

    cad = run("follow-up-machine", "cadence_dates", last_contact="2026-09-21", stage="proposal", touches=3,
              promised_date="2026-09-24", today="2026-09-28", touches_done=1)
    d = [t["date"] for t in cad["touches"]]
    assert d[0] == "2026-09-28"  # overdue since Fri 25th → today, never in the past
    assert d[1] == ref_add_business_days("2026-09-28", 7) == "2026-10-07"
    assert d[2] == ref_add_business_days("2026-10-07", 12) == "2026-10-23"
    assert [t["touch"] for t in cad["touches"]] == [2, 3, 4] and cad["touches"][-1]["channel"] == "breakup email"

    bad = run("follow-up-machine", "score_follow_up", email=(
        "Subject: Following up\nHi Tom,\n\nJust checking in to see if you had a chance to look at the proposal I sent over. "
        "I haven't heard back from you and wanted to make sure it didn't get lost in your inbox. Let me know if you have any "
        "questions! Happy to hop on a call anytime this week or next if that's easier. Would Tuesday or Wednesday work?\n\nThanks,\nSam"))
    assert bad["score"] < 40 and bad["asks"] == 3 and bad["guilt_phrases"] == ["haven't heard back"]
    good_text = ("Subject: Re: Kestrel proposal\nHi Tom,\n\nHope the board meeting on the 24th went well. You asked how long rollout "
                 "takes across 9 clinics: our last 8-clinic group went live in 19 days, one clinic per day after training.\n\n"
                 "If it helps your CFO review, I can send a one-page rollout calendar for Kestrel. Should I send it over?\n\nSam")
    good = run("follow-up-machine", "score_follow_up", email=good_text)
    assert good["score"] >= 80 and good["words"] == ref_word_count(good_text.split("\n", 1)[1]) == 56

    deals = [
        {"name": "Kestrel Dental Group", "stage": "Proposal", "amount": "42,000", "last_activity": "2026-09-21", "touches_since_reply": 1},
        {"name": "Oakline Clinics", "stage": "Negotiation", "amount": "68000", "last_activity": "2026-09-22"},
        {"name": "Brightwater Ortho", "stage": "Discovery", "amount": "15000", "last_activity": "2026-09-01"},
        {"name": "Maple Street Vets", "stage": "Demo", "amount": "9500", "last_activity": "2026-09-24"},
        {"name": "Summit Smiles", "stage": "Proposal", "amount": "$23,500", "last_activity": "2026-09-04", "touches_since_reply": 4, "close_date": "2026-09-25"},
        {"name": "Harbor Pediatric", "stage": "Qualification", "amount": "12000", "last_activity": "2026-09-10"},
    ]
    radar = run("follow-up-machine", "stale_deals", deals=deals, today="2026-09-28")
    rows = {r["name"]: r for r in radar["deals"]}
    for name, la, th in [("Kestrel Dental Group", "2026-09-21", 5), ("Oakline Clinics", "2026-09-22", 3), ("Brightwater Ortho", "2026-09-01", 10),
                         ("Maple Street Vets", "2026-09-24", 7), ("Summit Smiles", "2026-09-04", 5), ("Harbor Pediatric", "2026-09-10", 14)]:
        q = ref_business_days_between(la, "2026-09-28")
        assert rows[name]["quiet_business_days"] == q and rows[name]["staleness_x"] == round(q / th, 2)
    assert [r["name"] for r in radar["chase_today"]] == ["Oakline Clinics", "Summit Smiles", "Kestrel Dental Group", "Brightwater Ortho"]
    assert rows["Summit Smiles"]["action"] == "breakup email" and rows["Harbor Pediatric"]["status"] == "warm"
    assert radar["stale_amount"] == 68000 + 23500 + 42000 + 15000
    assert radar["stale_share_pct"] == round(100 * 148500 / 170000, 1) == 87.4


# ═══ 3. lead-qualifier — vs Apollo.io Scores ═══════════════════════════════════
ICP = {
    "industry": {"values": ["saas", "fintech"], "weight": 4},
    "employees": {"values": ["51-500"], "weight": 4},
    "seniority": {"values": ["vp", "director"], "weight": 3},
    "function": {"values": ["sales", "ops"], "weight": 3},
    "country": {"values": ["us", "uk"], "weight": 2},
    "tech": {"values": ["salesforce"], "weight": 3},
}
LEADS = [
    {"name": "Maya Chen", "title": "VP Revenue Operations", "industry": "Fintech", "employees": "180", "country": "US", "tech": "Salesforce, Outreach", "email": "maya@ledgerly.com"},
    {"name": "Tom Okafor", "title": "Director of Sales", "industry": "SaaS", "employees": "620", "country": "UK", "tech": "HubSpot", "email": "tom@brightpath.io"},
    {"name": "Liam Walsh", "title": "Head of Sales", "industry": "SaaS", "employees": "140", "country": "Australia", "tech": "Salesforce", "email": "liam@koalapayroll.com.au"},
    {"name": "Olena Kovalenko", "title": "Sales Operations Manager", "industry": "SaaS", "employees": "90", "country": "Ukraine", "tech": "Pipedrive", "email": "olena@dniprosoft.ua"},
    {"name": "Raj Patel", "title": "CEO", "industry": "SaaS", "employees": "8", "country": "US", "tech": "", "email": "raj@tinybooks.co"},
    {"name": "Emily Stone", "title": "Marketing Intern", "industry": "Fintech", "employees": "300", "country": "US", "tech": "Salesforce", "email": "emily.stone@gmail.com"},
    {"name": "Carlos Ruiz", "title": "VP Sales Engineering", "industry": "SaaS", "employees": "250", "country": "US", "tech": "Salesforce", "email": "carlos@stackwise.com"},
    {"name": "Hannah Berg", "title": "Senior Director, RevOps", "industry": "Banking", "employees": "4200", "country": "US", "tech": "Salesforce", "email": "hberg@northbank.com"},
]


def test_lead_qualifier_scenario():
    titles = run("lead-qualifier", "parse_titles", titles=[l["title"] for l in LEADS], buying_functions=["sales", "ops"])
    fn = {t["title"]: (t["seniority"], t["function"], t["role"]) for t in titles["titles"]}
    assert fn["VP Sales Engineering"] == ("vp", "engineering", "influencer")
    assert fn["VP Revenue Operations"][1] == "ops" and fn["Head of Sales"][0] == "vp" and fn["Marketing Intern"][2] == "none"

    out = run("lead-qualifier", "icp_fit_score", icp=ICP, leads=LEADS)
    got = {r["name"]: (r["score"], r["tier"]) for r in out["ranked"]}
    W = 19  # 4+4+3+3+2+3
    # hand-scored per criterion (points earned / 19); size "near" band = half weight, 1 seniority level off = half
    expected_raw = {
        "Maya Chen": 19,                         # all six
        "Liam Walsh": 4 + 4 + 3 + 3 + 0 + 3,     # Australia is NOT "us"
        "Carlos Ruiz": 4 + 4 + 3 + 0 + 2 + 3,    # function = engineering
        "Tom Okafor": 4 + 2 + 3 + 3 + 2 + 0,     # 620 employees = near band
        "Olena Kovalenko": 4 + 4 + 1.5 + 3 + 0 + 0,  # Ukraine is NOT "uk"; manager is 1 level off
    }
    for name, pts in expected_raw.items():
        assert got[name][0] == round(100 * pts / W), name
    assert got["Liam Walsh"] == (89, "A") and got["Olena Kovalenko"] == (66, "B")
    # caps: 8 and 4,200 employees are > 3x outside 51-500 → tier C; intern + gmail → tier D
    assert got["Raj Patel"] == (54, "C") and got["Hannah Berg"] == (54, "C") and got["Emily Stone"] == (34, "D")
    assert out["distribution"] == {"A": 3, "B": 2, "C": 2, "D": 1}

    maya = run("lead-qualifier", "route_lead", fit_score=100, intent="high", source="inbound")
    assert maya["owner"] == "AE" and maya["response_sla"] == "5 minutes"
    raj = run("lead-qualifier", "route_lead", fit_score=54, intent="high")
    assert raj["owner"] == "self-serve / SDR triage"
    emily = run("lead-qualifier", "route_lead", fit_score=34, intent="high")
    assert emily["owner"].startswith("decline")

    bant = run("lead-qualifier", "qualification_grade", framework="BANT", ratings={
        "budget": {"score": 2, "evidence": "set aside about $40k for pipeline tooling this fiscal year"},
        "authority": {"score": 1, "evidence": "rep assumes Maya signs"},
        "need": {"score": 3, "evidence": "forecast calls take 6 hours a week; missed Q2 by 18%"},
        "timeline": {"score": 2, "evidence": "live before Q1 planning"}})
    assert bant["total"] == 8 and bant["grade"] == "SQL" and [g["element"] for g in bant["gaps"]] == ["authority"]


# ═══ 4. pipeline-forecaster — vs Clari ════════════════════════════════════════
OPEN = [
    {"name": "Atlas Freight", "owner": "Dana", "stage": "Negotiation", "amount": "120,000", "close_date": "2026-09-18", "last_activity": "2026-08-28", "next_step": "Legal redlines call 9/3"},
    {"name": "Birchwood Health", "owner": "Dana", "stage": "Proposal", "amount": "60000", "close_date": "2026-09-25", "last_activity": "2026-08-25", "next_step": "CFO review of pricing"},
    {"name": "Cobalt Retail", "owner": "Luis", "stage": "Negotiation", "amount": "45000", "close_date": "2026-09-12", "last_activity": "2026-08-06", "next_step": "Send order form"},
    {"name": "Delta Dental Partners", "owner": "Luis", "stage": "Contract", "amount": "38000", "close_date": "2026-09-05", "last_activity": "2026-08-31", "next_step": "Countersign"},
    {"name": "Evergreen Schools", "owner": "Dana", "stage": "Demo", "amount": "80000", "close_date": "2026-09-29", "last_activity": "2026-08-27", "next_step": "Technical deep-dive"},
    {"name": "Fjord Analytics", "owner": "Priya", "stage": "Discovery", "amount": "25000", "close_date": "2026-10-15", "last_activity": "2026-08-20", "next_step": ""},
    {"name": "Granite Insurance", "owner": "Priya", "stage": "Proposal", "amount": "150000", "close_date": "2026-08-28", "last_activity": "2026-08-14", "slips": 2, "next_step": "Exec sponsor call"},
    {"name": "Harbor Logistics", "owner": "Luis", "stage": "Negotiation", "amount": "52000", "close_date": "2026-09-24", "last_activity": "2026-08-30", "next_step": ""},
    {"name": "Iris Media", "owner": "Priya", "stage": "Qualification", "amount": "18000", "close_date": "2026-11-30", "last_activity": "2026-08-29", "next_step": "Discovery call"},
    {"name": "Juniper Labs", "owner": "Dana", "stage": "Closed Won", "amount": "40000", "close_date": "2026-08-20", "last_activity": "2026-08-20", "next_step": ""},
]
CLOSED = [
    ("won", 48000, "2026-01-12", "2026-03-20", None), ("won", 36000, "2026-02-02", "2026-04-15", None),
    ("won", 90000, "2026-01-20", "2026-05-29", None), ("won", 22000, "2026-03-03", "2026-04-24", None),
    ("won", 61000, "2026-04-06", "2026-06-30", None), ("lost", 30000, "2026-01-05", "2026-02-10", "discovery"),
    ("lost", 55000, "2026-01-15", "2026-03-02", "discovery"), ("lost", 40000, "2026-02-10", "2026-04-01", "demo"),
    ("lost", 75000, "2026-02-20", "2026-05-15", "proposal"), ("lost", 28000, "2026-03-01", "2026-03-25", "qualification"),
    ("lost", 64000, "2026-03-10", "2026-06-12", "negotiation"), ("lost", 19000, "2026-04-01", "2026-04-20", "qualification"),
]


def test_pipeline_forecaster_scenario():
    hist = run("pipeline-forecaster", "stage_conversion", closed_deals=[
        {"outcome": o, "amount": a, "created": c_, "closed": cl, **({"furthest_stage": fs} if fs else {})} for o, a, c_, cl, fs in CLOSED])
    assert hist["win_rate_pct"] == round(100 * 5 / 12, 1) == 41.7
    won_cycles = sorted((date.fromisoformat(cl) - date.fromisoformat(c_)).days for o, _, c_, cl, _ in CLOSED if o == "won")
    assert won_cycles == [52, 67, 72, 85, 129] and hist["cycle_days"]["won_median"] == 72 and hist["cycle_days"]["won_avg"] == 81.0
    # reached counts: every deal reaches qualification (12); lost at qualification ×2 → 10 reach discovery; etc.
    assert hist["measured_probabilities"] == {"qualification": round(5 / 12, 3), "discovery": 0.5, "demo": 0.625, "proposal": round(5 / 7, 3), "negotiation": round(5 / 6, 3), "closed won": 1.0}

    probs = {k: v for k, v in hist["measured_probabilities"].items() if k != "closed won"}
    wp = run("pipeline-forecaster", "weighted_pipeline", deals=OPEN, stage_probabilities=probs, today="2026-09-01", period_end="2026-09-30")
    cat = {d["name"]: d["category"] for d in wp["deals"]}
    assert cat == {"Atlas Freight": "commit", "Delta Dental Partners": "commit", "Birchwood Health": "best_case",
                   "Cobalt Retail": "best_case", "Harbor Logistics": "best_case", "Evergreen Schools": "pipeline",
                   "Fjord Analytics": "pipeline", "Iris Media": "pipeline", "Granite Insurance": "slipped"}
    commit, best = 120000 + 38000, 60000 + 45000 + 52000
    assert (wp["commit"], wp["best_case"], wp["forecast"]) == (commit, best, commit + best / 2) == (158000, 157000, 236500)
    assert wp["open_in_period"] == 120000 + 60000 + 45000 + 38000 + 80000 + 52000 == 395000
    ref_weighted = 120000 * 0.833 + 60000 * 0.714 + 45000 * 0.833 + 38000 * 0.85 + 80000 * 0.625 + 52000 * 0.833
    assert abs(wp["weighted_in_period"] - ref_weighted) < 0.01
    assert wp["concentration"] == {"deal": "Atlas Freight", "share_of_forecast_pct": round(100 * 120000 / 236500, 1)}
    assert {d["name"]: d["probability"] for d in wp["deals"]}["Granite Insurance"] == round(0.714 / 2, 3)  # slipped twice
    assert wp["by_owner"]["Luis"]["forecast"] == 38000 + 0.5 * (45000 + 52000)

    cov = run("pipeline-forecaster", "coverage_ratio", quota=600000, closed_to_date=310000, open_pipeline=wp["open_in_period"],
              weighted_pipeline=wp["weighted_in_period"], days_left=ref_business_days_between("2026-08-31", "2026-09-30", ("2026-09-07",)),
              days_in_period=ref_business_days_between("2026-06-30", "2026-09-30", ("2026-07-03", "2026-09-07")),
              avg_deal_size=hist["avg_won_deal"], win_rate_pct=hist["win_rate_pct"], median_cycle_days=72)
    assert cov["gap"] == 290000 and cov["coverage_x"] == round(395000 / 290000, 2) == 1.36
    assert cov["required_win_rate_pct"] == round(100 * 290000 / 395000, 1) == 73.4
    assert cov["deals_needed_at_avg_size"] == math.ceil(290000 / 51400) == 6
    assert cov["new_pipeline_can_land"] is False and cov["status"] == "at risk"

    acc = run("pipeline-forecaster", "forecast_accuracy", forecasts=[
        {"period": "2025-Q3", "forecast": 520000, "actual": 455000}, {"period": "2025-Q4", "forecast": 610000, "actual": 580000},
        {"period": "2026-Q1", "forecast": 480000, "actual": 402000}, {"period": "2026-Q2", "forecast": 560000, "actual": 531000}])
    errs = [(520 - 455) / 455, (610 - 580) / 580, (480 - 402) / 402, (560 - 531) / 531]
    assert acc["mape_pct"] == round(100 * sum(abs(e) for e in errs) / 4, 1) == 11.1
    assert acc["calibration_multiplier"] == round(1968000 / 2170000, 3) == 0.907 and acc["direction"] == "over-forecasting"

    prev = [
        {"name": "Atlas Freight", "stage": "Negotiation", "amount": 110000, "close_date": "2026-09-18"},
        {"name": "Birchwood Health", "stage": "Demo", "amount": 60000, "close_date": "2026-09-25"},
        {"name": "Cobalt Retail", "stage": "Negotiation", "amount": 45000, "close_date": "2026-09-12"},
        {"name": "Delta Dental Partners", "stage": "Contract", "amount": 38000, "close_date": "2026-09-05"},
        {"name": "Evergreen Schools", "stage": "Demo", "amount": 80000, "close_date": "2026-09-29"},
        {"name": "Granite Insurance", "stage": "Proposal", "amount": 150000, "close_date": "2026-08-28"},
        {"name": "Harbor Logistics", "stage": "Negotiation", "amount": 52000, "close_date": "2026-10-10"},
        {"name": "Juniper Labs", "stage": "Negotiation", "amount": 40000, "close_date": "2026-08-20"},
        {"name": "Lumen Bank", "stage": "Negotiation", "amount": 70000, "close_date": "2026-09-20"},
        {"name": "Oriole Travel", "stage": "Proposal", "amount": 30000, "close_date": "2026-09-15"},
        {"name": "Pax Retail", "stage": "Discovery", "amount": 22000, "close_date": "2026-09-30"},
    ]
    cur = [{k: d[k] for k in ("name", "stage", "amount", "close_date")} for d in OPEN] + [
        {"name": "Lumen Bank", "stage": "Closed Lost", "amount": 70000, "close_date": "2026-08-31"},
        {"name": "Oriole Travel", "stage": "Proposal", "amount": 30000, "close_date": "2026-10-20"}]
    ch = run("pipeline-forecaster", "pipeline_changes", previous=prev, current=cur, period_start="2026-07-01", period_end="2026-09-30")
    s = ch["summary"]
    before = 110000 + 60000 + 45000 + 38000 + 80000 + 150000 + 40000 + 70000 + 30000 + 22000
    after = 120000 + 60000 + 45000 + 38000 + 80000 + 150000 + 52000
    assert (s["open_in_period_before"], s["open_in_period_now"]) == (before, after) == (645000, 545000)
    assert before - 40000 - 70000 - 30000 + 52000 - 22000 + 10000 == after  # won, lost, pushed, pulled, removed, upsized
    assert (s["won"], s["lost"], s["pushed_out_of_period"], s["pulled_into_period"], s["removed_without_outcome"], s["new"]) == (40000, 70000, 30000, 52000, 22000, 43000)


# ═══ 5. proposal-builder — vs PandaDoc ════════════════════════════════════════
def test_proposal_builder_scenario():
    better = run("proposal-builder", "pricing_table", line_items=[
        {"name": "Platform seat", "qty": 40, "unit_price": 65, "period": "month"},
        {"name": "Onboarding & data migration", "qty": 1, "unit_price": 3500, "period": "one_time"},
        {"name": "Premium support", "qty": 1, "unit_price": 2400, "period": "year"}], discount_pct=15, tax_rate_pct=8.875, term_months=12, seats=40)
    recurring = 40 * 65 * 12 + 2400
    sub = recurring * 0.85 + 3500
    tax = cents_half_up(sub * 0.08875)  # 2,845.325 → 2,845.33
    assert (better["discount_amount"], better["subtotal_after_discount"]) == (recurring * 0.15, sub) == (5040, 32060)
    assert better["tax_amount"] == tax == 2845.33 and better["grand_total"] == sub + tax == 34905.33
    assert "Tax (8.875%): USD 2,845.33" in better["display_rows"] and better["display_rows"][-1] == "Total for 12 months: USD 34,905.33"
    assert better["per_seat_per_month"] == round(recurring * 0.85 / 12 / 40, 2) == 59.5

    good = run("proposal-builder", "pricing_table", line_items=[{"name": "Platform seat", "qty": 25, "unit_price": 65, "period": "month"}, {"name": "Onboarding", "qty": 1, "unit_price": 2000, "period": "one_time"}], discount_pct=15, tax_rate_pct=8.875)
    best = run("proposal-builder", "pricing_table", line_items=[{"name": "Platform seat", "qty": 60, "unit_price": 65, "period": "month"}, {"name": "Onboarding", "qty": 1, "unit_price": 5000, "period": "one_time"}, {"name": "Premium support", "qty": 1, "unit_price": 2400, "period": "year"}, {"name": "Dedicated CSM", "qty": 1, "unit_price": 1000, "period": "month"}], discount_pct=15, tax_rate_pct=8.875)
    assert good["subtotal_after_discount"] == 25 * 65 * 12 * 0.85 + 2000 == 18575 and good["grand_total"] == 18575 + cents_half_up(18575 * 0.08875)
    assert best["subtotal_after_discount"] == (60 * 65 * 12 + 2400 + 12000) * 0.85 + 5000 == 57020 and best["grand_total"] == 57020 + cents_half_up(57020 * 0.08875)

    tiers = run("proposal-builder", "tier_comparison", tiers=[{"name": "Good", "price": 18575, "units": 25}, {"name": "Better", "price": 32060, "units": 40, "recommended": True}, {"name": "Best", "price": 57020, "units": 60}])
    t = {r["name"]: r for r in tiers["tiers"]}
    assert t["Best"]["multiple_of_lowest"] == round(57020 / 18575, 2) and t["Better"]["per_unit"] == 801.5
    assert tiers["recommended"] == "Better"

    hol = ("2026-11-26", "2026-11-27")
    tl = run("proposal-builder", "milestone_timeline", start_date="2026-10-05", total_price=3500, deposit_pct=30, holidays=list(hol), milestones=[
        {"name": "Kickoff & data audit", "business_days": 5}, {"name": "Migration & configuration", "business_days": 15, "payment_pct": 40},
        {"name": "Training", "business_days": 5}, {"name": "Go-live & hypercare", "business_days": 20, "payment_pct": 30}])
    ends, cursor = [], "2026-10-05"
    for n in (5, 15, 5, 20):  # a phase of n business days starting on `cursor` ends n-1 business days later
        end = ref_add_business_days(cursor, n - 1, hol)
        ends.append(end)
        cursor = ref_add_business_days(end, 1, hol)
    assert [m["end"] for m in tl["milestones"]] == ends == ["2026-10-09", "2026-10-30", "2026-11-06", "2026-12-08"]
    assert [p["amount"] for p in tl["payment_schedule"]] == [1050, 1400, 1050] and tl["payment_total_pct"] == 100

    audit = run("proposal-builder", "proposal_audit", deal_value=32060, proposal_text=(
        "# Proposal: One schedule for all nine clinics\nValid until 2026-10-28\n## Summary\nThe recommended Better option is USD 34,905.33 including tax.\n"
        "## Your situation\nNo-shows cost about USD 10,800 a week.\n## Objectives\n1. Cut no-shows under 8%.\n## Approach & deliverables\nMigration, training.\n"
        "## Timeline\n2026-10-05 to 2026-12-08.\n## Investment\n| Good | Better | Best |\n| USD 18,575.00 | USD 32,060.00 | USD 57,020.00 |\n"
        "## Why us\n- 400 practices live.\n## Assumptions & exclusions\n- Not included: hardware.\n## Terms\nNet 30.\n"
        "## Next step\nReply with the option you prefer by 2026-10-02 and we will send the order form to sign.\n" + "Detail. " * 250))
    assert audit["sections_missing"] == [] and audit["price_mentions"] >= 4 and not any("no prices" in f for f in audit["fixes"])


# ═══ 6. discovery-call — vs Fathom Business (coaching metrics + MEDDPICC template) ═══
DISCOVERY = """[00:00] Sam Ortiz: Thanks for making time, Dana. I have us down for 30 minutes. Is that still okay?
[00:05] Dana Whitfield: Yes, that works.
[00:08] Sam Ortiz: Great. So before we start, let me give you a quick overview of Northstar. We're a scheduling and patient communication platform for multi-location dental groups. We have about 400 practices on the platform, we integrate with Dentrix and Eaglesoft, and our customers typically see fewer no-shows within the first quarter. We also have automated recalls, two-way texting, online booking, and a reporting dashboard that rolls up every location. I think you'll really like the dashboard.
[01:40] Dana Whitfield: Okay.
[01:42] Sam Ortiz: So how are you handling appointment reminders today?
[01:45] Dana Whitfield: Right now each of our nine clinics does it differently. Some front desks call patients the day before, two clinics use the texting feature in Dentrix, and one just relies on a paper card. It's honestly a mess, and when someone is out sick the calls just don't happen. Our no-show rate across the group was about 14% last quarter, and in hygiene that's roughly 60 empty chairs a week at around 180 dollars each.
[02:40] Sam Ortiz: Wow. Is that a problem for you?
[02:43] Dana Whitfield: Yes, obviously.
[02:45] Sam Ortiz: You'd agree that automated reminders would fix most of that, right?
[02:48] Dana Whitfield: Probably some of it.
[02:50] Sam Ortiz: Do you use Dentrix in every location?
[02:52] Dana Whitfield: Seven on Dentrix, two on Eaglesoft from the acquisition last year.
[02:58] Sam Ortiz: Perfect, we support both. What happens when the front desk is short-staffed?
[03:03] Dana Whitfield: Reminders are the first thing to drop. The office managers have told me they spend three or four hours a day on the phone, and they hate it. We lost two front-desk people this summer and I think the phone load was part of it.
[03:30] Sam Ortiz: Who else would be involved in choosing a tool like this, and what's your timeline?
[03:34] Dana Whitfield: Our COO, Mark Feld, would sign off on anything over 20 thousand. I'd want something live before the January insurance reset.
[03:45] Sam Ortiz: Got it. Are you looking at anyone else?
[03:47] Dana Whitfield: We had a demo from Weave in the spring but didn't move forward.
[03:52] Sam Ortiz: Okay. Well, I think we'd be a great fit. Can I send you a proposal?
[03:55] Dana Whitfield: Sure, send it over.
"""


def test_discovery_call_scenario():
    out = run("discovery-call", "analyze_transcript", transcript=DISCOVERY, rep_name="Sam Ortiz")
    ref = ref_speaker_share(DISCOVERY)
    assert abs(out["rep_talk_pct"] - ref["Sam Ortiz"]) <= 1.0  # ref 49.3 (hyphenated words counted once)
    assert out["estimated_minutes"] == round((3 * 60 + 55) / 60, 1) and out["minutes_source"] == "timestamps"
    # hand classification of the 9 rep questions: 5 closed, 1 leading ("You'd agree … right?"),
    # 1 double-barrelled ("Who else …, and what's your timeline?"), 2 open ("how are you handling", "what happens")
    assert out["rep_questions"] == 9
    assert out["question_types"] == {"closed": 5, "open": 2, "leading": 1, "multi": 1}
    assert out["open_question_pct"] == round(100 * 2 / 9, 1)
    # the prospect DID cover pain, impact, timeline, competition and decision process; budget was never discussed
    assert set(out["topics_missed"]) == {"budget"}
    assert out["rep_fillers"] == {}  # "you'll really like the dashboard" is a verb, not a filler

    sc = run("discovery-call", "meddpicc_scorecard", target_stage="proposal", ratings={
        "metrics": {"score": 2, "evidence": "no-show ~14%; ~60 empty hygiene chairs/week at ~$180"},
        "economic_buyer": {"score": 2, "evidence": "COO Mark Feld signs anything over $20k"},
        "decision_criteria": 0, "decision_process": {"score": 1, "evidence": "only the signer is known"}, "paper_process": 0,
        "identify_pain": {"score": 3, "evidence": "reminders drop when short-staffed; 3-4 h/day on phones; lost two staff"},
        "champion": {"score": 1, "evidence": "Dana engaged but untested"},
        "competition": {"score": 2, "evidence": "Weave demo in spring, did not move forward"}})
    weights = {"metrics": 1.5, "economic_buyer": 1.5, "decision_criteria": 1, "decision_process": 1, "paper_process": 0.75, "identify_pain": 1.5, "champion": 1.5, "competition": 0.75}
    scores = {"metrics": 2, "economic_buyer": 2, "decision_criteria": 0, "decision_process": 1, "paper_process": 0, "identify_pain": 3, "champion": 1, "competition": 2}
    assert sc["raw_score"] == sum(scores.values()) == 11
    assert sc["weighted_pct"] == round(100 * sum(scores[k] * w for k, w in weights.items()) / (3 * sum(weights.values())), 1) == 50.9
    assert sc["gate_passed"] is False and sc["blockers"] == ["Champion is 1, needs ≥ 2 for proposal"]

    qs = run("discovery-call", "grade_questions", questions=[
        "Walk me through what happened to reminders the week your two front-desk staff left.",
        "What did last quarter's 14% no-show rate cost the group in hygiene revenue?",
        "How does Mark decide on spend over $20k, and who does he ask first?",
        "What would have to be true by the January insurance reset for this to count as a win?"])
    assert [q["type"] for q in qs["questions"]] == ["open", "open", "multi", "open"]


# ═══ 7. sales-call-debrief — vs Fathom Business (summaries, action items, CRM sync) ═══
DEBRIEF = """[24:02] Priya Nair: Thanks everyone for joining. Today I want to show you the approval workflow and the Netsuite sync, since those were the two things Leo raised last time.
[24:14] Leo Grant: Yes, the Netsuite piece is the big one for us.
[24:20] Priya Nair: Great. So here's the invoice inbox. Every invoice that lands in ap@ gets captured, coded against your chart of accounts, and routed to the approver based on amount and department. Under five thousand goes to the department head, over five thousand adds the controller, and anything over fifty thousand adds the CFO. You can change those thresholds yourself without calling us. Once it's approved it syncs to Netsuite as a vendor bill with the PDF attached, usually within two minutes.
[24:58] Leo Grant: How long does implementation take with Netsuite? Our last vendor took four months.
[25:06] Priya Nair: Typically three to four weeks, including the Netsuite connector and training.
[25:12] Aisha Karim: What does onboarding look like for the AP team? We have six clerks and two of them are brand new.
[25:22] Priya Nair: Two live sessions plus recorded modules. Most clerks are comfortable within a week.
[25:31] Leo Grant: Right now we lose about 20 hours a week keying invoices by hand, and we paid a duplicate invoice twice last quarter. That's the pain.
[25:48] Aisha Karim: When we roll this out I'd want the controller in the pilot group too.
[25:57] Leo Grant: What would pricing look like for about 1,800 invoices a month?
[26:07] Priya Nair: For that volume you'd be on the Growth plan, around 2,900 a month billed annually. I can put the exact numbers in a proposal.
[26:18] Leo Grant: That's a bit more than we budgeted, honestly. I'll need to run it by our CFO, Dan.
[26:28] Priya Nair: Makes sense. Could we get Dan on a 30-minute call next Tuesday to walk through the ROI?
[26:36] Leo Grant: Tuesday works. I'll send the invite to Dan and loop in Aisha.
[26:44] Priya Nair: Perfect. And I'll send the proposal and a Netsuite security overview by end of next week.
[26:52] Aisha Karim: Sounds good.
"""


def test_sales_call_debrief_scenario():
    m = run("sales-call-debrief", "call_metrics", transcript=DEBRIEF, rep_name="Priya Nair", call_type="demo")
    ref = ref_speaker_share(DEBRIEF)
    for spk in ("Priya Nair", "Leo Grant", "Aisha Karim"):
        assert abs(m["talk_share_pct"][spk] - ref[spk]) <= 0.5  # ref 60.3 / 28.2 / 11.5
    assert m["estimated_minutes"] == round(170 / 60, 1) and m["rep_questions"] == 1
    assert m["longest_monologue"]["Priya Nair"]["words"] == 80

    ns = run("sales-call-debrief", "detect_next_steps", transcript=DEBRIEF, call_date="2026-09-24", rep_name="Priya Nair")  # Thursday
    by_line = {c_["line"]: c_ for c_ in ns["candidates"]}
    assert by_line[13]["resolved_date"] == "2026-09-29"  # "next Tuesday" said on Thu 24 Sep
    assert by_line[15]["resolved_date"] == "2026-10-02"  # "end of next week" = Friday of next week
    assert ns["next_step_agreed"] is True and ns["agreed_next_steps"][0]["resolved_date"] == "2026-09-29"

    sig = run("sales-call-debrief", "buying_signals", transcript=DEBRIEF, rep_name="Priya Nair")
    assert sig["temperature"] == "warm" and sig["negative_types"] == ["price concern"]  # "a bit more than we budgeted"
    assert {"implementation questions", "pricing/terms asked", "pain quantified", "future-state language", "stakeholders introduced"} == set(sig["positive_types"])

    crm = run("sales-call-debrief", "map_crm_fields", crm="hubspot", call_date="2026-09-24", fields={
        "name": "Harbourline Foods - AP automation", "stage": "Demo", "amount": "34.8k", "close_date": "2026-10-30",
        "next_step": "Hold ROI review with CFO Dan Reyes on Tue Sep 29", "next_step_date": "2026-09-29",
        "champion": "Leo Grant", "risks": ["price above budget", "CFO not yet engaged"], "probability": 0.35})
    assert crm["payload"]["amount"] == 2900 * 12 == 34800 and crm["payload"]["dealstage"] == "presentationscheduled"
    assert "champion" not in crm["payload"] and set(crm["custom_properties"]) == {"champion", "risks"}
    assert crm["payload"]["hs_forecast_probability"] == 0.35 and crm["next_step_task_due"] == "2026-09-29"


# ═══ 8. objection-handler — vs Crystal (personality-based selling) ═══════════════
def test_objection_handler_scenario():
    cl = run("objection-handler", "classify_objection", stage="proposal",
             objection="Honestly the price is almost double what we pay for Tipalti today, and I can't justify $38k a year to our CFO right now.")
    assert cl["primary"] == "price" and cl["price_subtypes"] == ["competitor_cheaper", "value_gap"] and cl["smokescreen"] is False

    roi = run("objection-handler", "roi_rebuttal", annual_price=38400, hours_saved_per_week=4, people_affected=12, hourly_cost=38,
              annual_risk_or_error_cost_avoided=9000, implementation_cost=4000)
    value = 4 * 12 * 48 * 38 + 9000
    assert roi["annual_value"] == value == 96552
    assert roi["roi_pct_year1"] == round(100 * (value - 42400) / 42400, 1) == 127.7
    assert roi["roi_pct_steady_state"] == round(100 * (value - 38400) / 38400, 1) == 151.4
    assert roi["payback_months"] == round(42400 / (value / 12), 1) == 5.3
    assert roi["breakeven_hours_saved_per_person_per_week"] == round(38400 / (38 * 12 * 48), 2) == 1.75
    assert roi["three_year_net"] == 3 * value - 3 * 38400 - 4000 == 170456

    rf = run("objection-handler", "reframe_price", annual_price=38400, users=12, fte_annual_cost=65000, alternative_annual_cost=19800)
    assert rf["per_user_per_day"] == round(38400 / 12 / 250, 2) == 12.8
    assert rf["delta_vs_alternative"] == 18600 and rf["delta_pct_vs_alternative"] == round(100 * 18600 / 19800, 1) == 93.9
    assert rf["share_of_one_fte"] == round(38400 / 65000, 3)


# ═══ 9. negotiation-coach — vs Crystal (negotiation playbooks) ═══════════════════
def ref_pv(yearly: list[float], rate: float, offset: float) -> float:
    return sum(p / (1 + rate) ** (y + offset) for y, p in enumerate(yearly))


def test_negotiation_coach_scenario():
    z = run("negotiation-coach", "zopa_batna", our_walkaway=96000, our_target=110000, their_walkaway_estimate=115000,
            their_target_estimate=90000, our_batna_value=60000, their_batna_value=98000, current_offer=120000)
    assert (z["zopa_low"], z["zopa_high"], z["zopa_width"], z["midpoint"]) == (96000, 115000, 19000, 105500)
    assert z["recommended_anchor"] == 120000 and z["anchor_is_current_offer"] is True  # never re-anchor above the sent proposal
    assert z["power"] == "theirs" and z["target_position_in_zopa"] == round((110000 - 96000) / 19000, 2)

    lad = run("negotiation-coach", "concession_ladder", opening_price=120000, floor_price=96000, steps=3, gets=["annual prepayment", "3-year term", "signature by Oct 30"])
    usable = 24000 * 0.95
    raw = [120000 - usable * 0.5, 120000 - usable * 0.8, 120000 - usable * 1.0]
    assert [s["price"] for s in lad["ladder"]] == [round(p / 10) * 10 + 3 for p in raw] == [108603, 101763, 97203]
    moves = [s["move"] for s in lad["ladder"]]
    assert moves[0] > moves[1] > moves[2] and lad["held_in_reserve"] == 97203 - 96000

    pk = run("negotiation-coach", "compare_packages", cost_of_capital_pct=12, packages=[
        {"name": "1y", "annual_price": 120000, "term_years": 1, "discount_pct": 10, "payment": "annual_upfront"},
        {"name": "3y-upfront", "annual_price": 120000, "term_years": 3, "discount_pct": 18, "payment": "annual_upfront"},
        {"name": "2y-quarterly", "annual_price": 120000, "term_years": 2, "discount_pct": 12, "payment": "quarterly"},
        {"name": "3y-esc-monthly", "annual_price": 120000, "term_years": 3, "discount_pct": 15, "escalator_pct": 5, "payment": "monthly"}])
    p = {x["name"]: x for x in pk["packages"]}
    assert abs(p["3y-upfront"]["present_value"] - ref_pv([98400] * 3, 0.12, 0)) < 0.01  # 264,701.02
    assert abs(p["2y-quarterly"]["present_value"] - ref_pv([105600] * 2, 0.12, 0.375)) < 1  # quarterly ≈ mean arrival 0.375 y
    esc = [120000 * 0.85 * 1.05 ** y for y in range(3)]
    assert p["3y-esc-monthly"]["yearly_prices"] == [round(x, 2) for x in esc] and abs(p["3y-esc-monthly"]["present_value"] - ref_pv(esc, 0.12, 0.458)) < 1
    assert pk["highest_pv"] == "3y-esc-monthly"
    # all four quarterly / twelve monthly year-1 instalments land inside the first 12 months
    assert p["2y-quarterly"]["cash_in_first_12_months"] == 105600 and p["3y-esc-monthly"]["cash_in_first_12_months"] == 102000

    tr = run("negotiation-coach", "trade_ranker", trades=[
        {"item": "net-60 payment terms", "side": "give", "cost_to_us": 2, "value_to_them": 4},
        {"item": "price lock for 3 years", "side": "give", "cost_to_us": 3, "value_to_them": 4},
        {"item": "10 extra seats free", "side": "give", "cost_to_us": 1, "value_to_them": 3},
        {"item": "99.95% SLA", "side": "give", "cost_to_us": 4, "value_to_them": 3},
        {"item": "annual prepayment", "side": "get", "value_to_us": 5, "cost_to_them": 3},
        {"item": "case study + reference call", "side": "get", "value_to_us": 4, "cost_to_them": 1},
        {"item": "3-year term", "side": "get", "value_to_us": 5, "cost_to_them": 4}])
    assert tr["cheap_gives"] == ["10 extra seats free", "net-60 payment terms"] and tr["protect"] == ["99.95% SLA"]


# ═══ 10. linkedin-prospector — vs LinkedIn Sales Navigator Core ═══════════════════
PROFILE = """Rachel Okonkwo
Helping mid-market SaaS teams build pipeline that actually converts | VP Marketing at Quillbase
Denver, Colorado · 500+ connections
12 mutual connections

Activity
Posted: MQLs are a vanity metric. We cut our MQL target by 40% this quarter and pipeline went up. Here's what we measure instead...
Posted: We're hiring two SDRs in Denver. DM me if you know great people.

Experience
VP Marketing
Quillbase · Full-time
Jul 2026 - Present · 3 mos

Senior Director, Demand Generation
Tallyhop
Mar 2021 - Jun 2026 · 5 yrs 4 mos
"""


def test_linkedin_prospector_scenario():
    hooks = run("linkedin-prospector", "extract_hooks", profile_text=PROFILE, today="2026-09-28")
    assert hooks["months_in_current_role"] == (2026 - 2026) * 12 + (9 - 7) == 2  # calendar-month difference; LinkedIn shows "3 mos" (inclusive)
    assert hooks["best_hook"]["type"] == "new_role" and hooks["recent_posts_found"] == 2
    assert any(h["type"] == "headline_claim" for h in hooks["hooks"])

    pitchy = ("Hi Rachel, I came across your profile and would love to connect! We help SaaS marketing teams like Quillbase turn "
              "MQLs into pipeline with our AI platform - would you be open to a quick call next week to see a demo?")
    assert len(pitchy) == 214
    free = run("linkedin-prospector", "check_message", message=pitchy, kind="connection_note", premium=False)
    prem = run("linkedin-prospector", "check_message", message=pitchy, kind="connection_note", premium=True)
    assert free["fits"] is False and free["over_by"] == 14 and prem["fits"] is True and prem["score"] < 40
    note = "Rachel, your post on cutting the MQL target 40% and still growing pipeline stuck with me. Curious what replaced MQLs on your dashboard at Quillbase."
    ok = run("linkedin-prospector", "check_message", message=note, kind="connection_note", premium=False)
    assert ok["chars"] == len(note) <= 200 and ok["score"] >= 80

    plan = run("linkedin-prospector", "plan_sequence", start_date="2026-10-05", prospects=140, holidays=["2026-10-12"])
    hol = {date(2026, 10, 12)}

    def roll(off: int) -> str:
        d = date(2026, 10, 5) + timedelta(days=off)
        while d.weekday() >= 5 or d in hol:
            d += timedelta(days=1)
        return d.isoformat()

    assert [t["date"] for t in plan["touches"]] == [roll(o) for o in (0, 1, 3, 6, 10, 14, 18, 21)]
    assert plan["invites_per_day"] == 20 and plan["business_days_to_enrol_all"] == math.ceil(140 / 20) == 7
    assert plan["last_cohort_enrols"] == "2026-10-14"  # Oct 5-9, (12 holiday), 13, 14

    cap = run("linkedin-prospector", "capacity_plan", target_meetings=12)
    p = 0.35 * 0.25 * 0.30
    assert cap["invites_needed"] == math.ceil(12 / p) == 458 and cap["weeks_needed"] == math.ceil(458 / 100) == 5
    assert cap["accounts_for_one_month"] == math.ceil(458 / 400) == 2
