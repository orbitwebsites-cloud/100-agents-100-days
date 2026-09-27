"""Lead Qualifier — scores leads against a weighted ICP, grades qualification (BANT/CHAMP/MEDDIC-lite) and routes with an SLA."""

from __future__ import annotations

import re
from collections import Counter

from ...core import Agent, ToolError
from . import _common as c

AGENT = Agent(
    slug="lead-qualifier",
    name="Lead Qualifier",
    category="sales",
    tagline="Stop guessing which leads deserve a call: weighted ICP fit scores, BANT/CHAMP grades and a routing decision with an SLA.",
    description=(
        "Qualifies inbound and outbound leads the way a revenue-ops team would: parses job titles into seniority "
        "and function, scores each lead against a weighted ideal-customer profile (industry, size, geography, "
        "tech, title) with transparent reasons, grades qualification evidence on BANT or CHAMP, and turns "
        "fit × intent into a routing decision — AE now, SDR sequence, nurture, or disqualify — with the "
        "response deadline. Handles single leads or a list of hundreds."
    ),
    triggers=[
        "qualify this lead / is this lead worth pursuing",
        "score these leads against our ICP",
        "which of these leads should sales call first",
        "BANT / CHAMP qualify this prospect",
        "build a lead scoring model",
        "route this inbound lead — sales or nurture",
    ],
    examples=[
        "Here are 60 inbound sign-ups (title, company, size, industry). Rank them for my AEs.",
        "Our ICP is B2B SaaS, 50-500 employees, US/UK, using Salesforce. Score this lead: Ops Manager at a 120-person fintech in London.",
        "From these discovery notes, BANT-grade the opportunity and tell me if it's real.",
        "Someone from a 2,000-person bank booked a demo from the pricing page. Who should get it and how fast?",
    ],
    connectors=["HubSpot", "Salesforce", "Apollo", "Clearbit", "Slack", "Google Sheets"],
    playbook="""
    ## Standard
    You are the revenue-operations lead who decides where selling time goes. Excellent
    qualification is transparent (every score has reasons a rep can read in 5 seconds),
    consistent (the same lead gets the same score tomorrow), and decisive (a route and a
    deadline, not a maybe). The one metric: **qualified-lead-to-opportunity conversion**
    — the score must predict who buys, not who looks impressive.

    ## Intake
    You need the ICP (or enough to infer it: best current customers, target industries,
    size band, geography, must-have tech or triggers) and the leads (fields: title,
    company, industry, employees, country, tech, source, intent signals). If the ICP is
    missing, ask one question: "Describe your 3 best customers"— then build the ICP from
    that and state it. Never ask for a data field the tool can work without.

    ## Procedure
    1. **Normalise titles.** Call `lead_qualifier__parse_titles` with every job title.
       It returns seniority (c_level / vp / director / manager / ic / other), function
       (sales, marketing, engineering, ops, finance, hr, product, it, exec, other) and
       whether the title is a buyer, influencer or user for the stated product function.
       Titles are the field LLMs misread most ("VP Sales Engineering" is engineering).
    2. **Write the ICP as weights.** Build the criteria dict: for each attribute, the
       ideal values and a weight 1-5. Typical: industry 4, employees 4, title seniority 3,
       geography 2, tech/trigger 3. Show the ICP to the user in the output so they can
       tune it. Always include a **function** criterion (the buying functions from step 1,
       weight 3): seniority alone lets "VP Sales Engineering" score like "VP Sales".
    3. **Score fit.** Call `lead_qualifier__icp_fit_score` with the ICP and the lead(s)
       (up to 500). It returns a 0-100 fit score, tier (A ≥ 75, B 55-74, C 35-54, D < 35),
       matched/missed criteria with points, and the ranked list. Never adjust a score by
       hand; adjust the weights and re-run.
    4. **Grade qualification evidence** for any lead you have spoken with or have notes
       on: call `lead_qualifier__qualification_grade` with BANT or CHAMP ratings (0-3 per
       element with the evidence) — it returns the grade, the blocking gaps, and the
       question to ask next. Evidence must be the prospect's words; rep hope scores 1.
    5. **Route.** Call `lead_qualifier__route_lead` with fit score, intent level and the
       source. It applies the fit × intent matrix and returns owner type, response SLA and
       the first action. High-intent + high-fit gets a human within minutes; low-fit
       high-intent gets a polite self-serve path, not an AE.
    6. **Calibrate on history** when the user can export past leads with outcomes
       (won/lost, or converted to opportunity yes/no): call
       `lead_qualifier__calibrate_weights` with the ICP and those leads. It measures, per
       criterion, the win rate when the criterion matched vs. when it didn't, turns the
       lift into suggested 1-5 weights, and checks whether the current score actually
       separates winners from losers. Re-run step 3 with the suggested weights and say so.
    7. **Report** in the output format: ranked table, top 5 with reasons, disqualified
       with the single reason, and the ICP used. For lists, add the distribution
       (how many A/B/C/D) so the user knows if the list or the ICP is the problem.

    ## Frameworks
    - **Fit × intent matrix:** Fit A/B + high intent (demo request, pricing page,
      reply) → AE within 5 minutes during business hours (speed-to-lead: conversion drops
      sharply after the first hour). Fit A/B + low intent → SDR sequence within 1 business
      day. Fit C + high intent → self-serve / SDR triage within 1 day. Fit D → nurture or
      polite decline; never burn AE time.
    - **BANT** (Budget, Authority, Need, Timeline) — fine for transactional; **CHAMP**
      (Challenges, Authority, Money, Prioritisation) — better for consultative because it
      leads with the problem. Score 0-3 each; ≥ 8/12 with Need/Challenges ≥ 2 = SQL.
    - **Firmographic bands:** employees 1-10 / 11-50 / 51-200 / 201-1000 / 1001-5000 /
      5000+; the tool treats a band as a range, so "150 employees" matches "51-500".
    - **Negative signals** (auto-disqualify or cap at tier C): student/personal email,
      competitor domain, country you can't sell into, title = student/intern/consultant
      with no company, employee count far outside band.
    - **Well-established benchmarks:** MQL→SQL conversion typically 10-20%; responding to
      an inbound lead within 5 minutes vs 30 minutes improves contact rates dramatically
      (Harvard Business Review / InsideSales research).

    ## Output format
    ```
    ## ICP used (weights)
    industry: <values> (w4) · size: <band> (w4) · seniority: <levels> (w3) · function: <buying functions> (w3) · geo: … · tech/trigger: …

    ## Ranked leads
    | # | Lead | Company | Fit | Tier | Intent | Route | SLA | Why |
    |---|---|---|---|---|---|---|---|---|

    ## Top 5 — why they're first
    1. <lead> — <matched criteria with points>; <first action>

    ## Disqualified / nurture
    - <lead> — <one reason>

    ## Distribution
    A: n · B: n · C: n · D: n → <what this says about the list or the ICP>

    ## Qualification grade (if notes given)
    <BANT/CHAMP table, grade, gaps, next question>
    ```

    ## Anti-patterns
    - Scoring on company fame. A Fortune 500 lead with the wrong title is a D, not an A.
    - Letting "VP" in a title mean seniority regardless of function.
    - Binary qualification. Fit is a gradient; routing is the binary.
    - Ignoring speed. A perfect score routed tomorrow is worth less than a B routed now.
    - Hand-tuning individual scores to match a gut feel — change the weights instead.
    - Treating "opened an email" as intent. Intent is a demo request, a reply, a pricing-page visit, a trial.
    """,
)

SENIORITY = [
    ("c_level", re.compile(r"\b(ceo|cto|cfo|coo|cmo|cro|cio|ciso|cpo|chro|chief|founder|co-?founder|owner|president|managing director|general manager|partner)\b", re.I)),
    ("vp", re.compile(r"\b(vp|vice president|svp|evp|head of|global head)\b", re.I)),
    ("director", re.compile(r"\b(director|principal|group lead)\b", re.I)),
    ("manager", re.compile(r"\b(manager|lead|supervisor|team lead|mgr)\b", re.I)),
    ("ic", re.compile(r"\b(engineer|developer|analyst|specialist|associate|coordinator|representative|rep|executive|consultant|designer|scientist|administrator|assistant|architect|accountant|recruiter|marketer|writer|sdr|bdr|ae|account executive)\b", re.I)),
]
FUNCTION = [
    ("sales", re.compile(r"\b(sales|revenue|account executive|business development|bdr|sdr|cro|commercial|growth)\b", re.I)),
    ("marketing", re.compile(r"\b(marketing|cmo|brand|demand gen|content|communications|pr|seo|growth marketing)\b", re.I)),
    ("engineering", re.compile(r"\b(engineer|engineering|developer|software|cto|devops|sre|platform|architect|data scientist|machine learning|ml)\b", re.I)),
    ("product", re.compile(r"\b(product|cpo|ux|design)\b", re.I)),
    ("ops", re.compile(r"\b(operations|ops|coo|supply chain|logistics|procurement|revops|revenue operations|program)\b", re.I)),
    ("finance", re.compile(r"\b(finance|cfo|financial|accounting|controller|treasury|fp&a)\b", re.I)),
    ("hr", re.compile(r"\b(hr|people|human resources|talent|recruit|chro|learning)\b", re.I)),
    ("it", re.compile(r"\b(\bit\b|information technology|cio|ciso|security|infrastructure|systems)\b", re.I)),
    ("customer", re.compile(r"\b(customer success|support|customer experience|cx|account management|onboarding)\b", re.I)),
    ("exec", re.compile(r"\b(ceo|founder|owner|president|managing director|general manager)\b", re.I)),
]
NEGATIVE_TITLE = re.compile(r"\b(student|intern|retired|unemployed|looking for|seeking|freelance|self-employed)\b", re.I)


def _parse_title(title: str) -> dict:
    t = title.strip()
    sen = next((lvl for lvl, rx in SENIORITY if rx.search(t)), "other")
    # "VP of Sales Engineering" → engineering wins over sales when both match and engineering appears last
    funcs = [(f, m.start(), len(m.group(0))) for f, rx in FUNCTION for m in [rx.search(t)] if m]
    if funcs:
        # prefer the function mentioned last (the noun the title is actually about), except exec
        non_exec = [f for f in funcs if f[0] != "exec"]
        # prefer the function mentioned last; on a tie ("Revenue Operations" matches sales at "revenue"
        # and ops at "revenue operations") prefer the longer, more specific match
        func = max(non_exec, key=lambda x: (x[1], x[2]))[0] if non_exec else "exec"
    else:
        func = "exec" if sen == "c_level" else "other"
    if sen == "c_level" and func == "other":
        func = "exec"
    negative = bool(NEGATIVE_TITLE.search(t))
    return {"title": t, "seniority": sen, "function": func, "negative_signal": negative}


@AGENT.tool
def parse_titles(titles: list[str], buying_functions: list[str] | None = None) -> dict:
    """Parse job titles into seniority and function, and tag each as buyer / influencer / user for your product.

    Call first for every lead list. Seniority: c_level, vp, director, manager, ic, other.
    Function: sales, marketing, engineering, product, ops, finance, hr, it, customer, exec, other.

    Args:
        titles: Job titles as written (max 500).
        buying_functions: Functions that own the budget for your product (e.g. ["sales", "ops"]). Exec always counts.
    """
    if not titles:
        raise ToolError("titles is empty.")
    if len(titles) > 500:
        raise ToolError("Max 500 titles per call.")
    buyers = {f.strip().lower() for f in (buying_functions or [])} | {"exec"}
    rows, sen_count, fn_count = [], Counter(), Counter()
    for t in titles:
        t = str(t)
        if len(t) > 200:
            raise ToolError("A title over 200 chars is not a title.")
        p = _parse_title(t) if t.strip() else {"title": t, "seniority": "other", "function": "other", "negative_signal": False}
        if p["negative_signal"]:
            role = "none"
        elif p["function"] in buyers and p["seniority"] in ("c_level", "vp", "director"):
            role = "buyer"
        elif p["function"] in buyers and p["seniority"] == "manager":
            role = "influencer"
        elif p["function"] in buyers:
            role = "user"
        elif p["seniority"] in ("c_level", "vp"):
            role = "influencer"
        else:
            role = "none"
        p["role"] = role
        rows.append(p)
        sen_count[p["seniority"]] += 1
        fn_count[p["function"]] += 1
    n_buyers = sum(1 for r in rows if r["role"] == "buyer")
    return {
        "titles": rows,
        "seniority_distribution": dict(sen_count.most_common()),
        "function_distribution": dict(fn_count.most_common()),
        "buyers": n_buyers,
        "influencers": sum(1 for r in rows if r["role"] == "influencer"),
        "users": sum(1 for r in rows if r["role"] == "user"),
        "verdict": f"{len(rows)} titles: {n_buyers} buyer-level, {sum(1 for r in rows if r['role'] == 'influencer')} influencers, {sum(1 for r in rows if r['negative_signal'])} negative-signal.",
    }


SIZE_BANDS = {"1-10": (1, 10), "11-50": (11, 50), "51-200": (51, 200), "201-500": (201, 500), "501-1000": (501, 1000), "1001-5000": (1001, 5000), "5001-10000": (5001, 10000), "10000+": (10001, 10**9)}
SENIORITY_ORDER = ["ic", "manager", "director", "vp", "c_level"]


def _parse_range(v) -> tuple[int, int] | None:
    if v is None:
        return None
    s = str(v).strip().lower().replace(",", "")
    if s in SIZE_BANDS:
        return SIZE_BANDS[s]
    m = re.match(r"^(\d+)\s*[-–to]+\s*(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(\d+)\s*\+$", s)
    if m:
        return int(m.group(1)), 10**9
    m = re.match(r"^(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None


COUNTRY_KEYS = ("country", "geo", "geography", "region", "location", "hq_country")
_COUNTRY_ALIASES = {
    "us": ("us", "usa", "u.s.", "u.s.a.", "united states", "united states of america", "america"),
    "uk": ("uk", "u.k.", "united kingdom", "great britain", "gb", "britain", "england", "scotland", "wales", "northern ireland"),
    "uae": ("uae", "united arab emirates"),
    "de": ("de", "germany", "deutschland"),
}


def _country(v: str) -> str:
    v = v.strip().lower()
    for code, names in _COUNTRY_ALIASES.items():
        if v in names:
            return code
    return v


def _term_match(target: str, lead_value: str) -> bool:
    """Whole-word match either way: "saas" matches "b2b saas", but "us" never matches "australia"."""
    if not target or not lead_value:
        return False
    if target == lead_value:
        return True
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(target)}(?![a-z0-9])", lead_value) or re.search(rf"(?<![a-z0-9]){re.escape(lead_value)}(?![a-z0-9])", target))


def _score_lead(lead: dict, icp: dict) -> dict:
    total_w, got, matched, missed = 0.0, 0.0, [], []
    caps: list[str] = []
    for crit, spec in icp.items():
        if not isinstance(spec, dict):
            raise ToolError(f"ICP criterion {crit!r} must be a dict with 'values' and 'weight'.")
        weight = float(spec.get("weight", 1))
        if weight <= 0 or weight > 10:
            raise ToolError(f"ICP criterion {crit!r}: weight must be 1-10.")
        values = spec.get("values", spec.get("value", []))
        if not isinstance(values, list):
            values = [values]
        values = [str(v).strip().lower() for v in values if str(v).strip()]
        lead_val = lead.get(crit)
        total_w += weight
        pts = 0.0
        reason = ""
        if lead_val is None or str(lead_val).strip() == "":
            reason = "unknown"
            pts = weight * float(spec.get("unknown_credit", 0.25))
        elif crit in ("employees", "size", "company_size", "headcount", "revenue", "arr"):
            lr = _parse_range(lead_val)
            ranges = [r for r in (_parse_range(v) for v in values) if r]
            if lr and ranges:
                lo, hi = min(r[0] for r in ranges), max(r[1] for r in ranges)
                mid = (lr[0] + lr[1]) / 2
                if lo <= mid <= hi:
                    pts, reason = weight, f"{lead_val} within {lo}-{hi if hi < 10**9 else '∞'}"
                else:
                    # partial credit within 2× of the band edge
                    dist = (lo / mid) if mid < lo else (mid / hi)
                    pts = weight * 0.5 if dist <= 2 else 0.0
                    if dist > 3:
                        caps.append(f"{crit} {lead_val} is {dist:.1f}× outside the {lo}-{hi if hi < 10**9 else '∞'} band — capped at tier C")
                    reason = f"{lead_val} outside {lo}-{hi if hi < 10**9 else '∞'}" + (" (near)" if pts else "")
            else:
                reason = "unparseable size"
                pts = weight * 0.25
        elif crit in ("seniority", "title_seniority"):
            lv = str(lead_val).strip().lower()
            if lv in values:
                pts, reason = weight, f"{lv} in target"
            elif lv in SENIORITY_ORDER and any(v in SENIORITY_ORDER for v in values):
                target_idx = [SENIORITY_ORDER.index(v) for v in values if v in SENIORITY_ORDER]
                d = min(abs(SENIORITY_ORDER.index(lv) - i) for i in target_idx)
                pts = weight * (0.5 if d == 1 else 0.0)
                reason = f"{lv} is {d} level(s) from target"
            else:
                reason = f"{lv} not in target"
        else:
            lv = str(lead_val).strip().lower()
            lead_list = [x.strip() for x in re.split(r"[,;|/]", lv) if x.strip()] if crit in ("tech", "tech_stack", "tools", "signals", "triggers") else [lv]
            if crit in COUNTRY_KEYS:
                values = [_country(v) for v in values]
                lead_list = [_country(x) for x in lead_list]
            hits = [v for v in values if any(_term_match(v, x) for x in lead_list)]
            if not hits and crit == "function" and lv == "exec":
                hits = ["exec (founders/C-level always count as buyers)"]
            if hits:
                pts, reason = weight, f"{crit} matches {hits[0]}"
            else:
                reason = f"{crit} '{lead_val}' not in {values[:4]}"
        got += pts
        (matched if pts >= weight * 0.99 else missed).append({"criterion": crit, "points": round(pts, 2), "of": weight, "reason": reason})
    title = str(lead.get("title", "")).strip()
    if title and NEGATIVE_TITLE.search(title):
        caps.append("negative title signal (student/intern/seeking) — capped at tier D")
    email = str(lead.get("email", "")).strip().lower()
    if email and re.search(r"@(gmail|yahoo|hotmail|outlook|icloud|proton|aol)\.", email):
        caps.append("personal email domain — capped at tier C")
    score = round(100 * got / total_w) if total_w else 0
    if any("tier D" in x for x in caps):
        score = min(score, 34)
    elif any("tier C" in x for x in caps):
        score = min(score, 54)
    tier = "A" if score >= 75 else "B" if score >= 55 else "C" if score >= 35 else "D"
    return {"score": score, "tier": tier, "matched": matched, "missed": missed, "caps": caps}


@AGENT.tool
def icp_fit_score(icp: dict, leads: list[dict]) -> dict:
    """Score leads 0-100 against a weighted ICP and rank them into tiers A/B/C/D with per-criterion reasons.

    Call after parsing titles. ICP: {"industry": {"values": ["saas", "fintech"], "weight": 4},
    "employees": {"values": ["51-500"], "weight": 4}, "seniority": {"values": ["vp", "director"], "weight": 3},
    "function": {"values": ["sales", "ops"], "weight": 3},
    "country": {"values": ["us", "uk"], "weight": 2}, "tech": {"values": ["salesforce"], "weight": 3}}.
    Lead keys must match ICP keys (plus optional name, company, title, email).

    Args:
        icp: Criteria dict; each criterion has values (list) and weight (1-10). Optional unknown_credit (0-1, default 0.25) for missing lead fields.
        leads: 1-500 lead dicts with the same keys as the ICP plus name/company/title/email. Seniority and function are derived from the title when the lead has no such field. Countries match on whole words and common aliases (US/USA/United States, UK/United Kingdom/England).
    """
    if not isinstance(icp, dict) or not icp:
        raise ToolError("icp must be a non-empty dict of criteria.")
    if not leads or len(leads) > 500:
        raise ToolError("Give 1-500 leads.")
    results = []
    for i, lead in enumerate(leads, 1):
        if not isinstance(lead, dict):
            raise ToolError(f"Lead {i} is not a dict.")
        lead = {str(k).strip().lower(): v for k, v in lead.items()}
        if lead.get("title"):
            parsed = _parse_title(str(lead["title"]))
            if "seniority" in icp and "seniority" not in lead:
                lead["seniority"] = parsed["seniority"]
            if "function" in icp and "function" not in lead:
                lead["function"] = parsed["function"]
        r = _score_lead(lead, icp)
        results.append({
            "n": i,
            "name": lead.get("name") or lead.get("email") or f"Lead {i}",
            "company": lead.get("company"),
            "title": lead.get("title"),
            **r,
            "why": "; ".join(m["reason"] for m in r["matched"][:3]) or "no criteria matched",
            "gaps": "; ".join(m["reason"] for m in r["missed"][:3]),
        })
    ranked = sorted(results, key=lambda r: (-r["score"], r["n"]))
    dist = Counter(r["tier"] for r in results)
    n = len(results)
    diag = ""
    if n >= 10:
        if dist["D"] / n >= 0.6:
            diag = "≥ 60% tier D — the list source doesn't match the ICP (or the ICP is too narrow)."
        elif dist["A"] / n >= 0.6:
            diag = "≥ 60% tier A — the ICP is too loose to prioritise; raise weights on the criteria that actually separate buyers."
    return {
        "ranked": ranked,
        "distribution": {t: dist.get(t, 0) for t in "ABCD"},
        "top": [r["name"] for r in ranked[:5]],
        "diagnosis": diag or "Distribution looks usable.",
        "verdict": f"{n} lead(s): A {dist.get('A', 0)} · B {dist.get('B', 0)} · C {dist.get('C', 0)} · D {dist.get('D', 0)}. Top: {ranked[0]['name']} ({ranked[0]['score']}).",
    }


FRAMEWORKS = {
    "bant": [("budget", "Is there money set aside, and what's the range?"), ("authority", "Who signs, and are they aware of this evaluation?"), ("need", "What breaks if you do nothing for two more quarters?"), ("timeline", "What's driving the date — an event, a contract, a goal?")],
    "champ": [("challenges", "What's the specific problem, and what has it cost so far?"), ("authority", "Who else weighs in, and who has the final say?"), ("money", "How are projects like this funded — existing budget or new approval?"), ("prioritization", "Where does this sit versus the other things on your plate this quarter?")],
}
CORE = {"bant": "need", "champ": "challenges"}


@AGENT.tool
def qualification_grade(framework: str, ratings: dict) -> dict:
    """Grade qualification evidence on BANT or CHAMP (0-3 per element) into SQL / working / unqualified with next questions.

    Call when you have call notes or a conversation. 0 = unknown, 1 = rep assumption,
    2 = prospect stated, 3 = stated and specific (number, name, date).

    Args:
        framework: "BANT" or "CHAMP".
        ratings: Dict keyed by element (budget/authority/need/timeline or challenges/authority/money/prioritization), each an int 0-3 or {"score": int, "evidence": str}.
    """
    fw = framework.strip().lower()
    if fw not in FRAMEWORKS:
        raise ToolError("framework must be BANT or CHAMP.")
    if not isinstance(ratings, dict) or not ratings:
        raise ToolError("ratings must be a non-empty dict.")
    elements = FRAMEWORKS[fw]
    valid = {e for e, _ in elements}
    norm = {}
    for k, v in ratings.items():
        key = str(k).strip().lower()
        key = {"b": "budget", "a": "authority", "n": "need", "t": "timeline", "c": "challenges", "m": "money", "p": "prioritization", "prioritisation": "prioritization", "priority": "prioritization"}.get(key, key)
        if key not in valid:
            raise ToolError(f"Unknown element {k!r} for {fw.upper()}; use {', '.join(sorted(valid))}.")
        score, ev = (v.get("score", 0), str(v.get("evidence", "")).strip()) if isinstance(v, dict) else (v, "")
        try:
            score = int(score)
        except (TypeError, ValueError):
            raise ToolError(f"{key}: score must be an integer 0-3.") from None
        if not 0 <= score <= 3:
            raise ToolError(f"{key}: score must be 0-3.")
        norm[key] = (score, ev)
    rows, total, gaps = [], 0, []
    for el, q in elements:
        s, ev = norm.get(el, (0, ""))
        total += s
        if s < 2:
            gaps.append({"element": el, "score": s, "next_question": q})
        rows.append({"element": el, "score": s, "evidence": ev or ("—" if s == 0 else "(no evidence recorded)")})
    core = CORE[fw]
    core_score = norm.get(core, (0, ""))[0]
    if total >= 8 and core_score >= 2 and norm.get("authority", (0, ""))[0] >= 1:
        grade = "SQL"
    elif total >= 5 and core_score >= 1:
        grade = "working"
    else:
        grade = "unqualified"
    return {
        "framework": fw.upper(),
        "elements": rows,
        "total": total,
        "max": 12,
        "grade": grade,
        "gaps": gaps,
        "rule": f"SQL needs ≥ 8/12 with {core} ≥ 2 and authority ≥ 1.",
        "verdict": f"{fw.upper()} {total}/12 → {grade}." + (f" Close the gaps: {', '.join(g['element'] for g in gaps)}." if gaps else " Fully qualified."),
    }


@AGENT.tool
def route_lead(fit_score: int, intent: str, source: str = "inbound", business_hours: bool = True) -> dict:
    """Apply the fit × intent matrix: returns owner (AE / SDR / self-serve / nurture / decline), SLA and first action.

    Call for every lead after scoring. Intent levels: high (demo/pricing/trial/reply), medium
    (content download, webinar, repeat visits), low (list import, single visit, no signal).

    Args:
        fit_score: ICP fit score 0-100 from icp_fit_score.
        intent: high, medium or low.
        source: inbound, outbound, referral, partner or event (referral/partner get a bump).
        business_hours: Whether the lead arrived during business hours (affects the SLA clock).
    """
    if not 0 <= fit_score <= 100:
        raise ToolError("fit_score must be 0-100.")
    it = intent.strip().lower()
    if it not in ("high", "medium", "low"):
        raise ToolError("intent must be high, medium or low.")
    src = source.strip().lower()
    if src not in ("inbound", "outbound", "referral", "partner", "event"):
        raise ToolError("source must be inbound, outbound, referral, partner or event.")
    adj = fit_score + (10 if src in ("referral", "partner") else 0)
    tier = "A" if adj >= 75 else "B" if adj >= 55 else "C" if adj >= 35 else "D"
    matrix = {
        ("A", "high"): ("AE", "5 minutes" if business_hours else "first 15 minutes of next business day", "Call, then email with a calendar link; if no answer, call again in 30 min.", 1),
        ("B", "high"): ("AE", "15 minutes" if business_hours else "first hour of next business day", "Call + personalised email referencing what they did.", 1),
        ("A", "medium"): ("SDR", "4 business hours", "Personalised sequence step 1 (trigger-based), phone within 24h.", 2),
        ("B", "medium"): ("SDR", "1 business day", "Sequence enrolment with a relevant asset.", 2),
        ("A", "low"): ("SDR", "2 business days", "Research + trigger-led outbound; no generic sequence.", 3),
        ("B", "low"): ("nurture", "n/a", "Marketing nurture; re-score on next signal.", 4),
        ("C", "high"): ("self-serve / SDR triage", "1 business day", "Point to self-serve or trial; SDR checks for a hidden buyer.", 3),
        ("C", "medium"): ("nurture", "n/a", "Nurture; re-route if intent rises.", 4),
        ("C", "low"): ("nurture", "n/a", "Low-touch nurture only.", 5),
        ("D", "high"): ("decline / self-serve", "1 business day (courtesy)", "Polite reply with self-serve or partner referral. No AE time.", 5),
        ("D", "medium"): ("decline", "n/a", "No action; suppress from sales sequences.", 6),
        ("D", "low"): ("decline", "n/a", "Disqualify.", 6),
    }
    owner, sla, action, priority = matrix[(tier, it)]
    return {
        "fit_score": fit_score,
        "adjusted_fit": adj,
        "tier": tier,
        "intent": it,
        "source": src,
        "owner": owner,
        "response_sla": sla,
        "first_action": action,
        "priority": priority,
        "priority_scale": "1 = drop everything … 6 = disqualify",
        "verdict": f"Tier {tier} × {it} intent → {owner}, respond within {sla}. {action}",
    }


@AGENT.tool
def calibrate_weights(icp: dict, history: list[dict], min_leads: int = 20) -> dict:
    """Learn ICP weights from past leads with outcomes: per-criterion win-rate lift, suggested 1-5 weights, and score separation.

    Call when the user has historical leads with a known result. Each history row has the ICP
    fields plus "outcome": "won"/"lost" (or converted: true/false). Uses the same matching
    rules as icp_fit_score. Deterministic; no data leaves the conversation.

    Args:
        icp: The ICP criteria dict you score with (values + weight per criterion).
        history: 10-5000 past leads, each with the ICP fields and an outcome.
        min_leads: Minimum leads on each side of a criterion before its lift is trusted (default 20 total rows).
    """
    if not isinstance(icp, dict) or not icp:
        raise ToolError("icp must be a non-empty dict of criteria.")
    if not history or len(history) < 10 or len(history) > 5000:
        raise ToolError("Give 10-5000 historical leads with outcomes.")
    rows = []
    for i, h in enumerate(history, 1):
        if not isinstance(h, dict):
            raise ToolError(f"History row {i} is not a dict.")
        lead = {str(k).strip().lower(): v for k, v in h.items()}
        oc = lead.get("outcome", lead.get("converted"))
        if isinstance(oc, str):
            oc = oc.strip().lower()
            if oc not in ("won", "lost", "true", "false", "yes", "no"):
                raise ToolError(f"History row {i}: outcome must be won/lost (or converted true/false).")
            won = oc in ("won", "true", "yes")
        elif isinstance(oc, bool):
            won = oc
        else:
            raise ToolError(f"History row {i} has no outcome.")
        if lead.get("title"):
            parsed = _parse_title(str(lead["title"]))
            lead.setdefault("seniority", parsed["seniority"])
            lead.setdefault("function", parsed["function"])
        full = _score_lead(lead, icp)
        per = {m["criterion"]: m["points"] >= m["of"] * 0.99 for m in full["matched"] + full["missed"]}
        rows.append((won, full["score"], per))
    n = len(rows)
    n_won = sum(1 for r in rows if r[0])
    if n_won == 0 or n_won == n:
        raise ToolError("History needs both won and lost outcomes to measure lift.")
    base = n_won / n
    crits = []
    for crit in icp:
        hit = [r for r in rows if r[2].get(crit)]
        miss = [r for r in rows if not r[2].get(crit)]
        wr_hit = sum(1 for r in hit if r[0]) / len(hit) if hit else None
        wr_miss = sum(1 for r in miss if r[0]) / len(miss) if miss else None
        lift = (wr_hit - wr_miss) if (wr_hit is not None and wr_miss is not None) else None
        crits.append({"criterion": crit, "current_weight": float(icp[crit].get("weight", 1)), "matched_leads": len(hit), "unmatched_leads": len(miss),
                      "win_rate_matched_pct": round(100 * wr_hit, 1) if wr_hit is not None else None,
                      "win_rate_unmatched_pct": round(100 * wr_miss, 1) if wr_miss is not None else None,
                      "lift_pts": round(100 * lift, 1) if lift is not None else None,
                      "reliable": bool(hit) and bool(miss) and min(len(hit), len(miss)) >= max(5, min_leads // 4)})
    max_lift = max((c_["lift_pts"] for c_ in crits if c_["lift_pts"] and c_["lift_pts"] > 0), default=0)
    for c_ in crits:
        lp = c_["lift_pts"]
        if lp is None:
            c_["suggested_weight"], c_["note"] = c_["current_weight"], "every lead matched (or none did) — no contrast to learn from"
        elif lp <= 0:
            c_["suggested_weight"], c_["note"] = 1, "matching this did not raise the win rate — drop it or weight it 1"
        else:
            c_["suggested_weight"] = 1 + round(4 * lp / max_lift)
            c_["note"] = f"matched leads won {lp} pts more often"
        if not c_["reliable"]:
            c_["note"] += " (small sample — treat as directional)"
    won_scores = [r[1] for r in rows if r[0]]
    lost_scores = [r[1] for r in rows if not r[0]]
    # probability a random winner outscores a random loser (ties count half) — 0.5 = the score is noise
    pairs = sum((1.0 if w > l else 0.5 if w == l else 0.0) for w in won_scores for l in lost_scores)
    separation = round(pairs / (len(won_scores) * len(lost_scores)), 3)
    suggested_icp = {c_["criterion"]: {**icp[c_["criterion"]], "weight": c_["suggested_weight"]} for c_ in crits}
    warnings = []
    if n < min_leads:
        warnings.append(f"only {n} historical leads — weights are directional; revisit at {min_leads}+")
    if separation < 0.6:
        warnings.append(f"current score barely separates winners from losers (AUC {separation}) — the ICP is missing what actually predicts a win")
    return {
        "leads": n,
        "won": n_won,
        "base_win_rate_pct": round(100 * base, 1),
        "criteria": sorted(crits, key=lambda c_: -(c_["lift_pts"] or -999)),
        "suggested_icp": suggested_icp,
        "avg_score_won": round(sum(won_scores) / len(won_scores), 1),
        "avg_score_lost": round(sum(lost_scores) / len(lost_scores), 1),
        "score_separation_auc": separation,
        "warnings": warnings,
        "verdict": f"{n} past leads ({round(100 * base, 1)}% won). Current score AUC {separation} (0.5 = noise, 1.0 = perfect). "
        + "Strongest signal: " + next((f"{c_['criterion']} (+{c_['lift_pts']} pts)" for c_ in sorted(crits, key=lambda c_: -(c_["lift_pts"] or -999)) if c_["lift_pts"] and c_["lift_pts"] > 0), "none")
        + ".",
    }
