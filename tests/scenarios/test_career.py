"""Career & HR — replayable evaluation scenarios (see evals/career.md).

Each test replays one realistic customer request through the agent's tools exactly as the
customer's AI would call them, and asserts on values that were verified BY HAND or with the
independent stdlib helpers at the top of this file (they never import `hundred`).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from hundred import registry

# ── independent reference math (no `hundred` imports) ──────────────────────────


def months_inclusive(start: tuple[int, int], end: tuple[int, int]) -> int:
    """Calendar months from start month to end month, both inclusive (LinkedIn convention)."""
    return (end[0] - start[0]) * 12 + (end[1] - start[1]) + 1


def is_business_day(d: date, holidays: set[date]) -> bool:
    return d.weekday() < 5 and d not in holidays


def next_business_day(d: date, holidays: set[date]) -> date:
    while not is_business_day(d, holidays):
        d += timedelta(days=1)
    return d


def business_days_back(d: date, n: int, holidays: set[date]) -> date:
    while n:
        d -= timedelta(days=1)
        if is_business_day(d, holidays):
            n -= 1
    return d


def count_business_days(a: date, b: date, holidays: set[date]) -> int:
    """Inclusive count of business days in [a, b]."""
    return sum(1 for i in range((b - a).days + 1) if is_business_day(a + timedelta(days=i), holidays))


def call(slug: str, tool: str, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ── 1. Resume Optimizer: mid-level PM resume vs a Growth PM JD with planted gaps ─────

RESUME = """Maya Chen
maya.chen@example.com | (646) 555-0142 | linkedin.com/in/mayachen-pm | Brooklyn, NY

Summary
Product manager with 6+ years building consumer and small-business products. Comfortable with data and working across teams.

Experience
Product Manager, Cartwheel Logistics — Feb 2023 – Present
- Responsible for the driver onboarding roadmap and backlog in Jira
- Led redesign of the carrier sign-up flow, increasing completed sign-ups 23% in two quarters by cutting the form from 14 fields to 6
- Wrote SQL queries in Looker to build weekly funnel dashboards for the leadership team
- Worked with engineering and design on various improvements to the dispatch app
- Ran experiments on pricing page copy that lifted paid conversion from 3.1% to 3.8%

Product Manager, Brightpath Health — Apr 2020 – Dec 2022
- Launched appointment reminders via SMS, reducing no-shows 18% across 40 clinics
- Helped the team with user research and usability testing for the patient portal
- Managed the product roadmap for the scheduling squad of 7 engineers
- Partnered with sales to define packaging for the clinic tier, adding $1.2M ARR in year one

Associate Product Manager, Nimbus Media — Jun 2017 – Aug 2019
- Supported the PM team with competitive analysis and release notes
- Built Figma prototypes for the onboarding checklist tested with 25 users

Education
B.A. Economics, University of Michigan, 2017

Skills
SQL, Looker, Jira, Figma, user research, roadmapping, Google Analytics
"""

JD_PM = """Product Manager II, Growth — Ledgerly
New York, NY (hybrid) · $150,000 – $175,000 + equity

About the role
Ledgerly is the finance back office for 20,000 small businesses. The Growth team owns activation and expansion revenue across our B2B SaaS product.

What you'll do
- Own the activation funnel from sign-up to first invoice paid
- Size opportunities with SQL and run A/B testing to validate them
- Set quarterly OKRs with engineering and design and report progress to leadership

Requirements
- 4+ years of product management experience, ideally in B2B SaaS
- Hands-on SQL and A/B testing; you design experiments and read the results yourself
- Experience with Amplitude or Mixpanel for product analytics
- Strong stakeholder management across engineering, design and go-to-market teams
- Roadmap prioritization tied to OKRs

Nice to have
- Payments or fintech experience; familiarity with Stripe APIs
- Figma prototyping
- Python for analysis
"""

# Ground truth written before running the tool.
PLANTED_MUST_MISSING = {"a/b testing", "okr", "amplitude", "stakeholder management", "prioritization", "go-to-market"}
PLANTED_NICE_MISSING = {"b2b", "saas", "stripe", "python", "payments"}
PRESENT_MUST = {"product management", "sql", "roadmap", "analytics"}  # "analytics" is literally in "Google Analytics"


def test_resume_keyword_gaps_recall_and_precision():
    out = call("resume-optimizer", "match_keywords", resume=RESUME, job_description=JD_PM, job_title="Product Manager II")
    missing = {r["term"]: r["tier"] for r in out["missing"]}
    matched = {r["term"]: r["tier"] for r in out["matched"]}
    # Recall: every planted must-have gap is reported as a must-have.
    assert all(missing.get(t) == "must" for t in PLANTED_MUST_MISSING)
    assert all(missing.get(t) == "nice" for t in PLANTED_NICE_MISSING)
    # "4+ years of PM experience, ideally in B2B SaaS" — PM stays must, B2B SaaS is the nice qualifier.
    assert matched["product management"] == "must"
    assert all(matched.get(t) == "must" for t in PRESENT_MUST)
    # Precision: no roman numerals / state codes as keywords; the team name is context, not a must.
    assert "ii" not in missing and "ny" not in matched and missing.get("growth") == "context"
    # "Amplitude or Mixpanel" is one requirement, not two.
    assert {"either": "amplitude", "or": "mixpanel"} in out["alternatives"]
    assert out["counts"]["must"] == [4, 10] and out["must_have_coverage_pct"] == 40.0
    assert out["title_in_resume"] is False and out["years_required"] == 4


def test_resume_tenure_and_gap_match_hand_count():
    roles = [
        {"title": "Product Manager", "company": "Cartwheel Logistics", "start": "Feb 2023", "end": "present"},
        {"title": "Product Manager", "company": "Brightpath Health", "start": "Apr 2020", "end": "Dec 2022"},
        {"title": "Associate Product Manager", "company": "Nimbus Media", "start": "Jun 2017", "end": "Aug 2019"},
    ]
    out = call("resume-optimizer", "compute_tenure", roles=roles, as_of="2026-09-27")
    m1, m2, m3 = months_inclusive((2017, 6), (2019, 8)), months_inclusive((2020, 4), (2022, 12)), months_inclusive((2023, 2), (2026, 9))
    assert (m1, m2, m3) == (27, 33, 44)
    assert [t["months"] for t in out["timeline"]] == [m1, m2, m3]
    assert out["total_months"] == m1 + m2 + m3 == 104 and out["total_experience"] == "8 yrs 8 mo"
    gap = months_inclusive((2019, 9), (2020, 3))  # Sep 2019 – Mar 2020
    assert out["gaps"] == [{"months": gap, "from": "2019-09", "to": "2020-03", "label": "7 mo"}]
    assert out["median_tenure_months"] == 33  # the one-month Jan 2023 gap is under the 3-month threshold


def test_resume_bullets_flag_duty_bullets_and_accept_irregular_verbs():
    bullets = [l[2:] for l in RESUME.splitlines() if l.startswith("- ")]
    out = call("resume-optimizer", "score_bullets", bullets=bullets)
    weak = {i for i, b in enumerate(bullets) if re.match(r"(Responsible for|Worked with|Helped|Supported)", b)}
    assert weak <= set(out["needs_rewrite"])
    ran = next(r for r in out["bullets"] if r["bullet"].startswith("Ran experiments"))
    assert "does not start with an action verb" not in ran["issues"] and ran["score"] == 100


def test_resume_ats_format_clean_and_one_page():
    out = call("resume-optimizer", "check_ats_format", resume=RESUME, years_experience=8.7)
    assert out["parse_risks"] == [] and out["page_rule"]["target_pages"] == 1


# ── 2. Cover Letter: a generic draft with planted clichés vs a tailored letter ─────

LETTER_BAD = """To Whom It May Concern,

I am writing to apply for the Product Manager II position at Ledgerly. I am a passionate, results-driven product manager and a team player with a proven track record. I believe I would be the perfect fit for your innovative company.

I have worked on many products over the years. I have used SQL. I have worked with engineers and designers. I am a fast learner who can hit the ground running in a fast-paced environment.

I look forward to hearing from you.

Sincerely,
Maya Chen
"""
PLANTED_CLICHES = {
    "to whom it may concern", "i am writing to", "passionate", "results-driven", "team player", "proven track record",
    "perfect fit", "your innovative company", "fast learner", "hit the ground running", "fast-paced environment",
    "i look forward to hearing from you",
}
LETTER_GOOD = """Dear Ledgerly Growth Hiring Team,

Twenty thousand small businesses trust Ledgerly with their back office, and the moment that decides whether a new one stays is the first invoice paid. That activation moment is what I have spent eight years improving, which is why the Product Manager II, Growth role stands out to me.

At Cartwheel Logistics, a B2B SaaS platform for freight carriers, I own the carrier sign-up funnel. Cutting the form from 14 fields to 6 raised completed sign-ups 23% in two quarters. That result came from my own analysis: I size opportunities in SQL, design the A/B tests, and read the results myself. One pricing-page test lifted paid conversion from 3.1% to 3.8%.

Prioritization is where growth teams win or stall. At Brightpath Health I ran roadmap prioritization for a squad of 7 engineers, and the top-ranked bet, clinic-tier packaging built with sales, added $1.2M ARR in year one. I have not used OKRs formally, but every quarter I tied our roadmap to two measurable targets and reported progress to leadership.

Your posting also asks for Amplitude or Mixpanel. My analytics work has been in Looker and SQL, and I would get fluent in your stack during my first two weeks. In my first 90 days I would map the drop-off between sign-up and first invoice, pick the two largest leaks, and ship one test against each.

Could we find thirty minutes to talk? I would like to walk you through the sign-up redesign and hear where activation stalls for Ledgerly today. Thank you for considering my application.

Maya Chen · (646) 555-0142 · maya.chen@example.com · linkedin.com/in/mayachen-pm
"""
TOP3 = [
    "Hands-on SQL and A/B testing; you design experiments and read the results yourself",
    "Roadmap prioritization tied to OKRs",
    "Experience with Amplitude or Mixpanel for product analytics",
]


def test_cover_letter_cliche_recall_and_scores():
    bad = call("cover-letter", "check_letter", letter=LETTER_BAD, job_description=JD_PM, company="Ledgerly", role="Product Manager II")
    assert {c["term"] for c in bad["cliches"]} == PLANTED_CLICHES  # 12/12 recall, 0 false positives
    assert bad["score"] < 50 and bad["words"] < 250
    good = call("cover-letter", "check_letter", letter=LETTER_GOOD, job_description=JD_PM, company="Ledgerly", role="Product Manager II")
    assert good["cliches"] == [] and good["issues"] == [] and good["score"] == 100
    assert 250 <= good["words"] <= 350 and good["paragraphs"] == 5  # greeting and contact line are not paragraphs


def test_cover_letter_priority_and_coverage():
    ex = call("cover-letter", "extract_requirements", job_description=JD_PM)
    assert [p["text"] for p in ex["priority"]] == TOP3
    assert ex["counts"] == {"must": 5, "nice": 3, "unclear": 0, "duties": 3}
    good = call("cover-letter", "requirement_coverage", letter=LETTER_GOOD, requirements=TOP3)
    assert good["covered"] == 3 and good["quantified_answers"] == 2 and "Ready" in good["verdict"]  # Amplitude answer is an honest gap, no number
    bad = call("cover-letter", "requirement_coverage", letter=LETTER_BAD, requirements=TOP3)
    # Naming the job title or one of two skills is a mention, not an answer.
    assert [r["status"] for r in bad["requirements"]] == ["partial", "missing", "missing"] and bad["covered"] == 0
    assert bad["requirements"][0]["skills_missing"] == ["a/b testing"]  # "I have used SQL." names one of two skills


# ── 3. Interview Coach: an all-"we" STAR answer ────────────────────────────────

STAR_WE = (
    "At Cartwheel Logistics last year our carrier sign-up conversion was stuck at around 40 percent and leadership was worried "
    "about the Q3 target. We needed to figure out why carriers were dropping off. So we pulled the funnel data and we looked at "
    "session recordings. We found that the form was way too long. We decided to cut the form down and we ran a test on the new "
    "version. The team rebuilt the flow in about six weeks and we launched it to everyone after the test. In the end we increased "
    "completed sign-ups by 23 percent and we hit the Q3 target. It was a great team effort and everyone was really happy with the result."
)
STAR_I = (
    "At Cartwheel Logistics last year, carrier sign-up conversion was stuck at 40 percent and we were at risk of missing the Q3 "
    "activation target. My job was to find the drop-off and fix it before the quarter closed. First, I pulled the funnel data in SQL "
    "and found that 60 percent of abandons happened on the second page of a 14-field form. I then watched 30 session recordings and "
    "saw carriers leaving to look up their insurance number. I proposed cutting the form to 6 fields and collecting insurance after "
    "activation. Compliance pushed back, so I met with their lead and agreed to a 7-day grace period with automated reminders. I "
    "designed an A/B test with a two-week run and a pre-set success metric of plus 10 percent completion. As a result, completed "
    "sign-ups rose 23 percent, we hit the Q3 target a month early, and support tickets about sign-up fell by a third. What I learned "
    "is to talk to the blocking team before the test, not after; I now book that meeting in week one."
)


def test_star_we_story_flags_ownership():
    out = call("interview-coach", "check_star_story", story=STAR_WE)
    words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?", STAR_WE)
    we_hand = len(re.findall(r"\b(?:we|our|us)\b|\bthe team\b", STAR_WE, re.I))
    i_hand = len(re.findall(r"\bI\b|\bmy\b|\bme\b", STAR_WE))
    assert (we_hand, i_hand) == (11, 0)
    assert out["ownership"]["we_total"] == we_hand and out["ownership"]["i_total"] == 0
    assert out["ownership"]["we_in_action"] == 7 and out["ownership"]["i_in_action"] == 0
    assert any("'we' 7× vs 'I' 0×" in i for i in out["issues"])
    assert out["words"] == len(words) == 120 and out["spoken_seconds"] == round(120 / 150 * 60) == 48
    assert out["score"] < 80
    fixed = call("interview-coach", "check_star_story", story=STAR_I)
    assert fixed["score"] == 100 and fixed["ownership"]["i_in_action"] > fixed["ownership"]["we_in_action"]


def test_lint_answer_fillers_without_counting_the_verb_like():
    ans = ("So, um, basically I think I am kind of a product person who, like, really loves data and, you know, I have worked at "
           "Cartwheel and Brightpath and honestly I just really like growth stuff and things like that.")
    out = call("interview-coach", "lint_answer", answer=ans, question="Tell me about yourself", max_seconds=90)
    f = {x["term"]: x["count"] for x in out["fillers"]}
    # Hand count: "who, like," and "things like that" are fillers; "I really like growth" is the verb.
    assert f["like"] == 2 and f["really"] == 2 and f["um"] == 1 and f["i think"] == 1
    assert out["restates_question"] is False and "no number anywhere in the answer" in out["issues"]


def test_prep_schedule_spreads_work_and_keeps_light_day():
    out = call("interview-coach", "plan_prep_schedule", interview_date="2026-10-08", start_date="2026-09-28", hours_per_day=2)
    sched = out["schedule"]
    assert out["days_before_interview"] == (date(2026, 10, 8) - date(2026, 9, 28)).days == 10
    assert sched[-1]["date"] == "2026-10-08" and sched[-2]["date"] == "2026-10-07" and sched[-2]["focus"].startswith("Light review")
    assert out["total_prep_hours"] == 11 + 1 + 0.5  # five phases (2+3+2.5+2+1.5) + light day + interview day
    rest = [s["date"] for s in sched if s["focus"] == "Rest / buffer"]
    assert len(rest) <= 1  # no three idle days right before the interview


# ── 4. Salary Negotiator: Amazon-style 5/15/40/40 RSUs + sign-on vs an even vest ─

OFFERS = [
    {"name": "A", "base": 165000, "signing_bonus": 60000, "signing_bonus_year2": 45000, "equity_value": 240000, "schedule": "amazon"},
    {"name": "B", "base": 175000, "bonus_pct": 10, "signing_bonus": 25000, "equity_value": 200000, "schedule": "even"},
    {"name": "Stay", "base": 150000, "bonus_pct": 8},
]


def test_offer_math_matches_hand_calculation():
    out = call("salary-negotiator", "compare_offers", offers=OFFERS, years=4)
    rows = {o["name"]: o for o in out["offers"]}
    a = [165000 + 60000 + 240000 * 0.05, 165000 + 45000 + 240000 * 0.15, 165000 + 240000 * 0.40, 165000 + 240000 * 0.40]
    b = [175000 * 1.10 + 25000 + 50000] + [175000 * 1.10 + 50000] * 3
    assert [y["total"] for y in rows["A"]["by_year"]] == a == [237000, 246000, 261000, 261000]
    assert [y["total"] for y in rows["B"]["by_year"]] == pytest.approx(b) and b[0] == pytest.approx(267500)
    assert rows["A"]["average_annual"] == sum(a) / 4 == 251250 and rows["B"]["average_annual"] == pytest.approx(248750)
    assert rows["A"]["year_1_cash"] == 225000 and rows["B"]["year_1_cash"] == pytest.approx(217500)
    assert rows["Stay"]["total_over_horizon"] == 150000 * 1.08 * 4
    assert out["ranking"] == ["A", "B", "Stay"]
    # Cumulative: A 237k/483k/744k/1005k vs B 267.5k/510k/752.5k/995k — B leads unless you stay 4 years.
    assert out["crossover"] == {"leader_by_year": ["B", "B", "B", "A"], "early_leader": "B", "overtaken_in_year": 4, "final_leader": "A"}


def test_amazon_vesting_calendar_and_leave_at_24_months():
    out = call("salary-negotiator", "vesting_schedule", grant_value=240000, start_date="2026-11-02", schedule="amazon", frequency="semiannual", leave_date="2028-11-02")
    assert [(e["date"], e["amount"]) for e in out["events"]] == [
        ("2027-11-02", 12000), ("2028-05-02", 18000), ("2028-11-02", 18000),
        ("2029-05-02", 48000), ("2029-11-02", 48000), ("2030-05-02", 48000), ("2030-11-02", 48000),
    ]
    assert out["if_leave"]["vested"] == 240000 * 0.20 and out["if_leave"]["forfeited"] == 192000
    even = call("salary-negotiator", "vesting_schedule", grant_value=200000, start_date="2026-11-02", leave_date="2028-11-02")
    assert even["cliff"] == {"months": 12, "date": "2027-11-02", "amount": 50000}  # 4-yr / 1-yr cliff
    assert even["event_count"] == 1 + 12 and even["if_leave"]["vested"] == 100000


def test_counter_and_raise_value():
    c = call("salary-negotiator", "plan_counter", offer_base=165000, walk_away_base=170000, market_p50=170000, market_p75=185000, competing_offer_base=175000)
    assert c["ask_base"] == 185000 and c["ask_pct_above_offer"] == 12.1 and c["expected_landing"] == 175000
    v = call("salary-negotiator", "raise_value", base_before=165000, base_after=175000)
    assert v["total_difference"] == pytest.approx(10000 * sum(1.03**k for k in range(10)), abs=0.01)


# ── 5. Job Description: planted gendered & exclusionary language ─────────────

JD_BIASED = """Enterprise Sales Rockstar (Account Executive)
Austin, TX (on-site)

About the role
Northbeam sells workflow software to mid-market manufacturers. We're a young and energetic team of digital natives, and we're looking for an aggressive, competitive closer who wants to dominate the Texas market. He will own a $1.2M quota and crush it. We work hard, play hard, and we're a family.

What you'll do
- Run the full sales cycle from discovery to close for 40 named accounts
- Lead demos with plant managers and operations leaders
- Forecast your pipeline weekly in Salesforce

Requirements
- Recent graduates welcome; 3-5 years of B2B SaaS sales experience
- Ambitious and assertive, with a self-reliant, decisive style
- Native English speaker
- Strong culture fit with our sales guys
- Must be able to lift 50 lbs
- Bachelor's degree required
- Supportive of teammates during month-end pushes

What we offer
- Base plus uncapped commission, paid family leave, 401k match
- A mature product line that customers already trust

Equal opportunity employer.
"""
# Gaucher, Friesen & Kay (2011) masculine stems planted: aggress*, compet*, domina*, ambitio*, assert*, self-relian*, decisive.
PLANTED_GFK_MASC = {"aggressive", "competitive", "dominate", "ambitious", "assertive", "self-reliant", "decisive"}
PLANTED_SLANG = {"rockstar", "crush"}
PLANTED_EXCL = {
    "young", "energetic", "digital natives", "he will", "work hard, play hard", "family", "recent graduates",
    "native english speaker", "culture fit", "guys", "must be able to lift",
}


def test_jd_gendered_and_exclusionary_recall_precision():
    out = call("job-description", "check_inclusive_language", job_description=JD_BIASED)
    gfk = {f for h in out["masculine_coded"] if h["source"] == "GFK 2011" for f in h["matched"]}
    slang = {f for h in out["masculine_coded"] if h["source"] != "GFK 2011" for f in h["matched"]}
    excl = {f for h in out["exclusionary"] for f in h["matched"]}
    assert gfk == PLANTED_GFK_MASC and slang == PLANTED_SLANG and excl == PLANTED_EXCL  # recall and precision 100%
    assert [h["term"] for h in out["feminine_coded"]] == ["supportive"]
    # Decoys: "paid family leave" and "mature product line" are benefits/product language, not flagged;
    # "Lead demos" / "leaders" are GFK-listed but functional — reported as weak, not penalised.
    assert next(h for h in out["exclusionary"] if h["term"] == "family")["count"] == 1
    assert "mature" not in {h["term"] for h in out["exclusionary"]}
    assert {h["term"] for h in out["weak_coded"]} >= {"lead*"}
    assert out["lean"] == "masculine" and out["masculine_count"] == 9 and out["score"] == 0


def test_jd_structure_and_requirement_audit():
    s = call("job-description", "check_structure", job_description=JD_BIASED)
    assert s["salary_range"] is None and "no salary range found" in s["issues"]
    assert s["requirements"]["nice"] == 0  # "Base plus commission" is an offer line, not a nice-to-have
    reqs = [l[2:] for l in JD_BIASED.split("Requirements\n")[1].split("\n\nWhat we offer")[0].splitlines()]
    a = call("job-description", "audit_requirements", requirements=reqs, role_level="mid")
    assert a["recommend_cut"] == [2, 4] and a["recommend_rewrite"] == [1, 3, 5]
    assert a["degree_requirements"] == 1 and a["years_proxies"] == 1
    band = call("job-description", "build_salary_band", band_min=80000, band_max=110000, candidate_salary=98000)
    assert band["band"] == {"min": 80000, "q1": 87500, "midpoint": 95000, "q3": 102500, "max": 110000}
    assert band["spread_pct"] == round(100 * 30000 / 80000, 1) and band["candidate"]["compa_ratio"] == round(98000 / 95000, 3)


# ── 6. Hiring Scorecard: protected criteria refused; 4 interviewers with one outlier ─

LEGIT = [
    {"name": "SQL and data modeling", "weight": 30, "must_have": True, "description": "writes correct, performant SQL and models messy data"},
    {"name": "Experimentation and statistics", "weight": 25, "must_have": True, "description": "designs and reads A/B tests correctly"},
    {"name": "Stakeholder communication", "weight": 20, "description": "turns analysis into a decision for non-analysts"},
    {"name": "Ownership", "weight": 15, "description": "drives analyses to a decision without being chased"},
    {"name": "Problem solving", "weight": 10, "description": "breaks ambiguous questions into testable pieces"},
]
PROTECTED = ["Culture fit", "Under 35 years old", "Christian values", "No childcare constraints", "Male leadership presence", "Pregnancy plans", "Speaks without an accent"]


def test_scorecard_refuses_protected_characteristic_criteria():
    comps = LEGIT + [{"name": n, "weight": 5} for n in PROTECTED]
    out = call("hiring-scorecard", "build_scorecard", role="Senior Data Analyst", competencies=comps, interviewers=["Priya", "Tom", "Alex", "Jordan"])
    assert [r["name"] for r in out["rejected"]] == PROTECTED and all(r["refused"] for r in out["rejected"])
    assert [c["name"] for c in out["competencies"]] == [c["name"] for c in LEGIT]  # no job-related item refused
    assert out["weights_sum_to"] == 100.0 and all(len(v) == 2 for v in out["coverage"].values())


RATINGS = {
    "Dana": {"Priya": {"SQL and data modeling": 3, "Stakeholder communication": 3, "Problem solving": 3},
             "Tom": {"SQL and data modeling": 3, "Stakeholder communication": 4, "Problem solving": 3},
             "Alex": {"Experimentation and statistics": 4, "Ownership": 3},
             "Jordan": {"Experimentation and statistics": 1, "Ownership": 1}},
    "Luis": {"Priya": {"SQL and data modeling": 2, "Stakeholder communication": 3, "Problem solving": 3},
             "Tom": {"SQL and data modeling": 2, "Stakeholder communication": 3, "Problem solving": 2},
             "Alex": {"Experimentation and statistics": 3, "Ownership": 3},
             "Jordan": {"Experimentation and statistics": 1, "Ownership": 2}},
}
WEIGHTS = {c["name"]: c["weight"] for c in LEGIT}


def _hand_score(ratings: dict, drop: str | None = None) -> float:
    by_comp: dict[str, list[int]] = {}
    for rater, scores in ratings.items():
        if rater == drop:
            continue
        for comp, s in scores.items():
            by_comp.setdefault(comp, []).append(s)
    covered = {c: sum(v) / len(v) for c, v in by_comp.items()}
    return round(100 * sum(WEIGHTS[c] * m for c, m in covered.items()) / (sum(WEIGHTS[c] for c in covered) * 4), 1)


def test_scores_outlier_interviewer_and_decision_sensitivity():
    cands = [{"name": n, "ratings": r} for n, r in RATINGS.items()]
    out = call("hiring-scorecard", "score_candidates", candidates=cands, weights=WEIGHTS, must_haves=["SQL and data modeling", "Experimentation and statistics"])
    dana, luis = out["candidates"]
    assert dana["weighted_score"] == _hand_score(RATINGS["Dana"]) == 70.6 and dana["decision"] == "hire"
    assert luis["weighted_score"] == _hand_score(RATINGS["Luis"]) == 58.1 and luis["decision"].startswith("no hire (must-have")
    assert {d["competency"] for d in dana["disagreements"]} == {"Experimentation and statistics", "Ownership"}
    sens = {x["without"]: x for x in dana["rater_sensitivity"]}
    assert sens["Jordan"]["weighted_score"] == _hand_score(RATINGS["Dana"], "Jordan") == 83.8 and sens["Jordan"]["decision"] == "strong hire"
    assert sens["Alex"]["decision"].startswith("no hire (must-have")  # Exp would average 1.0
    assert dana["decision_hinges_on"] == ["Alex", "Jordan"]
    # Only the outlier is a calibration flag (vs the panel MEAN, Alex would also have been flagged at +0.65).
    assert out["calibration_flags"] == ["Jordan"] and out["interviewer_leniency"]["Jordan"]["delta_vs_median_rater"] == round(1.25 - 17 / 6, 2)
    assert out["interviewer_leniency"]["Alex"]["delta_vs_panel"] == round(13 / 4 - 52 / 20, 2) == 0.65


def test_feedback_audit_strikes_protected_remarks():
    fb = ("Honestly not sure about Dana. She seemed nervous and her accent made her hard to follow at times. Great energy but I don't "
          "think she's a culture fit for our team. She mentioned she has two kids, so I worry about the late-night launches. When I asked "
          "about the checkout experiment she said the result was significant but could not explain how she picked the sample size. She "
          "walked me through the race condition in her ETL job and fixed it in 10 minutes. Rating: 1/4.")
    out = call("hiring-scorecard", "check_feedback_bias", feedback=fb, interviewer="Jordan")
    assert {h["term"] for h in out["protected_or_proxy_terms"]} == {"nervous", "accent", "energy", "culture fit", "kids"}
    assert out["strike_before_filing"] is True and out["evidence_ratio_pct"] == round(100 * 3 / 7, 1)  # "race condition" is not "race"


# ── 7. Performance Review: biased phrasing, recency and goal math ─────────────

REVIEW = ("Priya had a solid year and is a pleasure to work with. She is always helpful and pleasant with customers, but she can be "
          "abrasive and emotional in planning meetings, and she never accepts pushback. Since coming back from maternity leave she seems "
          "less committed. Unlike Tom, she rarely speaks up in architecture reviews. Great job on billing v2, which shipped in November. In "
          "December she led the incident review for the payments outage. She has potential but needs to improve her communication skills.")


def test_review_language_catches_every_planted_bias():
    out = call("performance-review", "check_review_language", review=REVIEW, cycle_start="2026-01-01", cycle_end="2026-12-31")
    assert {h["term"] for h in out["personality_terms"]} == {"pleasure to work with", "helpful", "pleasant", "abrasive", "emotional", "maternity", "committed"}
    assert {h["term"] for h in out["vague_terms"]} == {"solid", "seems", "great job", "has potential", "needs to improve", "communication skills"}
    assert out["absolutes"] == ["always", "never"] and out["peer_comparisons"] == 1
    assert out["recency"]["flag"] is True and out["recency"]["months_covered"] == ["2026-11", "2026-12"]
    assert any("maternity" in i for i in out["issues"]) and out["score"] == 0
    abrasive = next(h for h in out["personality_terms"] if h["term"] == "abrasive")
    assert "Snyder 2014" in abrasive["suggestion"]


REVIEW_FIXED = """Priya delivered 97% weighted goal attainment in 2026 (meets expectations): billing v2 shipped, NPS moved from 40 to 47 against a target of 50, and P1 incidents finished at 5 against a target of 4.

In March, during the invoicing migration, you wrote the data-validation checklist that caught 312 mismatched invoices before cutover, which avoided an estimated $40k in credits. In July you mentored two new engineers through their first on-call rotation; both closed P2 tickets solo by week 3.

In the June and September planning meetings, you rejected three proposals before their owners finished presenting, which meant two of them were not raised again. Expectation: in Q1 2027 planning, ask one clarifying question before giving a view; we will review this in the February 1:1.

During the November billing v2 launch, you wrote the rollback runbook and ran two dry runs with support, which meant cutover finished with zero customer-facing errors and 3 hours ahead of schedule.
"""


def test_rewritten_review_is_clean_and_out_of_cycle_quarters_ignored():
    out = call("performance-review", "check_review_language", review=REVIEW_FIXED, cycle_start="2026-01-01", cycle_end="2026-12-31")
    assert out["score"] == 100 and out["issues"] == [] and out["recency"]["flag"] is False
    assert "2027" not in " ".join(out["recency"]["months_covered"])  # "Q1 2027" is the next cycle, not this one


def test_goal_attainment_matches_hand_math():
    goals = [
        {"name": "Ship billing v2", "target": 1, "actual": 1, "weight": 30},
        {"name": "NPS 40 to 50", "target": 50, "actual": 47, "baseline": 40, "weight": 30},
        {"name": "P1 incidents <= 4", "target": 4, "actual": 5, "direction": "lower", "weight": 20},
        {"name": "Onboard 2 engineers", "target": 2, "actual": 3, "weight": 20},
    ]
    out = call("performance-review", "goal_attainment", goals=goals)
    hand = [100.0, 100 * (47 - 40) / (50 - 40), 100 * 4 / 5, min(150.0, 100 * 3 / 2)]
    assert [g["attainment_pct"] for g in out["goals"]] == hand == [100.0, 70.0, 80.0, 150.0]
    assert out["weighted_attainment_pct"] == sum(h * g["weight"] for h, g in zip(hand, goals)) / 100 == 97.0
    assert out["rating_band"] == "meets" and out["missed_goals"] == ["NPS 40 to 50", "P1 incidents <= 4"]


def test_sbi_never_launders_a_trait():
    out = call("performance-review", "format_sbi", items=[{"situation": "planning meetings", "behavior": "is abrasive and always shoots down ideas", "impact": "people stop talking"}])
    row = out["items"][0]
    assert "you abrasive" not in row["sbi"] and "not 'abrasive'" in row["sbi"] and out["ready"] == []


def test_calibration_uses_median_manager():
    r = [("Ana", 5), ("Ana", 5), ("Ana", 4), ("Ana", 5), ("Ben", 3), ("Ben", 3), ("Ben", 4), ("Ben", 2), ("Cal", 3), ("Cal", 3), ("Cal", 3), ("Cal", 4)]
    out = call("performance-review", "calibrate_ratings", ratings=[{"employee": f"e{i}", "manager": m, "rating": v} for i, (m, v) in enumerate(r)])
    assert out["managers"]["Ana"]["flag"] == "lenient" and out["managers"]["Ben"]["flag"] is None  # vs org mean Ben would read "harsh"
    assert out["managers"]["Ben"]["delta_vs_org"] == round(3.0 - 44 / 12, 2)


# ── 8. Onboarding Planner: a Monday start right before Thanksgiving ─────────────

HOL = ["2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15"]
HOLS = {date.fromisoformat(h) for h in HOL}
START = date(2026, 11, 23)


def test_30_60_90_dates_and_holiday_week():
    out = call("onboarding-planner", "build_30_60_90", start_date="2026-11-23", role="Senior Product Manager", manager="Lena Ortiz", holidays=HOL)
    d30, d60, d90 = (next_business_day(START + timedelta(days=n - 1), HOLS) for n in (30, 60, 90))
    assert (d30, d60, d90) == (date(2026, 12, 22), date(2027, 1, 21), date(2027, 2, 22))  # day 90 is Sat Feb 20 → Mon
    assert [out[k]["date"] for k in ("day_30", "day_60", "day_90")] == [d.isoformat() for d in (d30, d60, d90)]
    assert out["day_90"]["moved"] is True
    assert out["week_1_end"] == {"date": "2026-11-25", "weekday": "Wed", "working_days": 3}
    assert out["day_5"]["date"] == "2026-12-01" and any("only 3 working day" in w for w in out["warnings"])
    ph = {p["phase"]: p["business_days"] for p in out["phases"]}
    assert ph["Learn"] == count_business_days(START, d30, HOLS) == 20
    assert ph["Contribute"] == count_business_days(d30 + timedelta(days=1), d60, HOLS) == 18
    assert ph["Own"] == count_business_days(d60 + timedelta(days=1), d90, HOLS) == 21
    ones = [o["date"] for o in out["one_on_ones"]]
    assert ones[0] == "2026-11-24" and "2027-01-19" in ones and ones[-1] == "2027-02-16"  # MLK and Presidents' Day skipped
    assert all(is_business_day(date.fromisoformat(d), HOLS) for d in ones)


def test_preboarding_due_dates_and_overdue():
    out = call("onboarding-planner", "preboarding_checklist", start_date="2026-11-23", holidays=HOL, today="2026-11-12")
    due = {i["lead_business_days"]: i["due"] for i in out["items"]}
    for lead in (15, 14, 10, 8, 5, 3, 2, 1):
        assert due[lead] == business_days_back(START, lead, HOLS).isoformat()
    assert due[15] == "2026-11-02" and due[1] == "2026-11-20"
    assert len(out["overdue"]) == 4 and out["business_days_until_start"] == 7


def test_intro_schedule_respects_short_holiday_week():
    people = [{"name": f"P1-{i}", "priority": 1} for i in range(7)] + [{"name": "Skip", "priority": 2}]
    out = call("onboarding-planner", "intro_meeting_schedule", start_date="2026-11-23", stakeholders=people, holidays=HOL)
    wk1 = [m for m in out["meetings"] if m["week"] == 1]
    assert {m["date"] for m in wk1} == {"2026-11-24", "2026-11-25"} and len(wk1) == 6  # 2 working days × 3/day
    assert all(is_business_day(date.fromisoformat(m["date"]), HOLS) for m in out["meetings"])


def test_plan_lint_catches_holiday_weekend_and_missing_owner():
    items = [
        {"task": "Laptop, SSO and Jira access working", "owner": "IT", "due": "2026-11-23", "phase": 30, "category": "access"},
        {"task": "Meet buddy and product trio", "owner": "Lena", "due": "2026-11-24", "phase": 30, "category": "people"},
        {"task": "Read last two quarters of activation research", "owner": "New hire", "due": "2026-11-26", "phase": 30, "category": "learning"},
        {"task": "Ship the onboarding-checklist copy fix and demo it", "owner": "New hire", "due": "2026-12-16", "phase": 30, "category": "deliverable"},
        {"task": "Day-30 check-in", "owner": "Lena", "due": "2026-12-22", "phase": 30, "category": "feedback"},
        {"task": "Own the Q1 activation experiment backlog", "owner": "New hire", "due": "2026-12-25", "phase": 60, "category": "deliverable"},
        {"task": "Propose one pricing-page change with evidence", "owner": "", "due": "2027-02-05", "phase": 90, "category": "deliverable"},
        {"task": "Day-90 written two-way review", "owner": "Lena", "due": "2027-02-20", "phase": 90, "category": "feedback"},
    ]
    out = call("onboarding-planner", "check_plan", items=items, start_date="2026-11-23", holidays=HOL)
    flagged = {r["due"]: r["issues"] for r in out["items"] if r["issues"]}
    assert set(flagged) == {"2026-11-26", "2026-12-25", "2027-02-05", "2027-02-20"}
    assert "move to 2026-11-30" in flagged["2026-11-26"][0] and "move to 2026-12-28" in flagged["2026-12-25"][0]
    assert out["first_deliverable_day"] == (date(2026, 12, 16) - START).days + 1 == 24
