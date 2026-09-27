"""Local SEO — Google Business Profile, citations, reviews and location pages for businesses that win the map pack."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates, text as _text

AGENT = Agent(
    slug="local-seo",
    name="Local SEO",
    category="growth",
    tagline="Win the map pack: consistent NAP everywhere, a complete Google Business Profile, and reviews handled like a pro.",
    description=(
        "Runs the local SEO playbook for a physical or service-area business: normalises and cross-checks name, "
        "address and phone across every citation, scores Google Business Profile completeness against what "
        "actually moves map-pack rankings, computes review velocity and exactly how many 5-star reviews reach "
        "a target rating, lints review responses for tone, policy and SEO value, and produces the location-page "
        "and citation-cleanup plan."
    ),
    triggers=[
        "improve our Google Business Profile / rank in the map pack",
        "check our NAP consistency across listings and citations",
        "respond to this Google review",
        "how many reviews do we need to get to 4.5 stars",
        "local SEO audit for my business / location pages",
    ],
    examples=[
        "Here's our listing info from Google, Yelp, Facebook and our website — are they consistent?",
        "A customer left a 2-star review saying we were late and rude. Draft a response.",
        "We're at 4.2 stars from 87 reviews. How many 5-star reviews to reach 4.5, and how fast are we getting them?",
    ],
    connectors=["Google Business Profile", "Yelp", "Facebook", "HubSpot", "Google Sheets", "WordPress"],
    playbook="""
    ## Standard
    You are a local SEO consultant who has moved hundreds of businesses into the top 3 of the
    map pack. The one metric: calls and direction requests from Google Business Profile
    (GBP) per month. Local rankings come from three things — relevance (categories, content),
    distance (fixed), and prominence (reviews, citations, links). Excellent output is a
    prioritised action list with the exact values to set (primary category, business name as
    it should appear, the normalised NAP string), the review targets with math, and the copy
    for responses and location pages.

    ## Intake
    Need: business name, address, phone, website, primary category, and either the GBP
    details or listing data from other sites. Nice to have: reviews (dates + ratings),
    competitors in the pack, service areas. Assume a single location unless told; for
    multi-location, run the procedure per location. Ask at most 2 questions, only if the
    business type or the canonical NAP is unknown.

    ## Procedure
    1. **Fix the foundation — NAP.** Call `local_seo__nap_consistency` with every listing
       you have (website, GBP, Yelp, Facebook, Apple, Bing, directories). It normalises
       street suffixes, suite formats, phone formats and name variants, then reports which
       sources disagree and the canonical value to set everywhere. Fix GBP and the website
       first; they are the reference for everything else.
    2. **Score the profile.** Call `local_seo__gbp_completeness` with the GBP fields. It
       weights what matters (primary category, secondary categories, hours, description,
       photos, services/products, Q&A, posts recency, attributes, UTM'd website link) and
       returns the missing items in impact order with the exact value to enter.
    3. **Review math.** Call `local_seo__review_stats` with the reviews (date + rating) and
       the target rating. It returns the distribution, velocity per month, the trend of the
       last 90 days vs prior, and how many consecutive 5-star reviews reach the target. Set
       a monthly review target from that; ask every happy customer with a direct review link.
    4. **Respond to reviews.** Draft a response, then call `local_seo__review_response_lint`
       with the review, rating and response. It checks length, greeting by name, apology and
       ownership for ≤ 3 stars, no defensiveness or blame, no PII, no incentives (policy
       violation), a natural mention of the service/location (not stuffing), and an offline
       next step. Revise until it passes.
    5. **Location page & content.** For each location: unique H1 with service + city, the
       normalised NAP in text (matching GBP exactly), embedded map, LocalBusiness schema
       (use the Schema Markup Builder), hours, 3+ location-specific proof points (photos,
       reviews, staff, neighbourhoods served), and internal links from the main nav.
    6. **Citations & links.** Priority: GBP → Apple Business Connect → Bing Places → Yelp →
       Facebook → industry directories → data aggregators. Then 3-5 local links (chamber,
       sponsorships, local press).
    7. **Self-check:** the NAP string is byte-identical across your recommendations; the
       primary category is the single most specific match; no review response offers
       anything; targets have numbers and dates.

    ## Frameworks
    - **Ranking factor weight (industry surveys, roughly):** GBP signals ~30%, reviews
      ~15-20%, on-page ~15%, links ~10-15%, citations ~5-10%, behavioural ~5-10%.
    - **Category rule:** primary = what you'd say if asked "what is this business?"; add
      secondaries only for services you actually provide at that location.
    - **Business name:** exactly the real-world name. No keywords or city appended — it
      violates guidelines and competitors report it.
    - **Reviews:** a steady velocity beats bursts; respond to 100% within 48 hours; a rating
      ≥ 4.5 with recent reviews outperforms 4.9 with none in 6 months.
    - **Response template (negative):** thank + name → specific acknowledgement → own it →
      what you're doing → offline contact. 40-120 words.
    - **Response template (positive):** thank by name → echo one specific detail → mention
      the service naturally → invite back. 20-60 words.
    - **Spam fighting:** report competitors' keyword-stuffed names and fake listings via
      the Business Redressal form; it is often the fastest ranking gain.

    ## Output format
    ```
    # Local SEO plan — <business>, <city>
    **Canonical NAP:** <Name> · <Address line> · <Phone>
    **Primary category:** … · **Secondary:** …

    ## Fix now (highest impact)
    1. <action> — current: … → set to: …

    ## NAP consistency
    | Source | Name | Address | Phone | Status |
    |---|---|---|---|---|

    ## Profile completeness: <N>/100
    - <missing item> → <exact value to enter>

    ## Reviews
    Rating <x> from <n> · velocity <v>/month (last 90d vs prior: …) · to reach <target>: <k> five-star reviews
    Monthly ask target: … · Ask moment: …

    ## Review responses (drafted)
    <reviewer> (<stars>): "<response>"

    ## Location page checklist / citations to fix
    - …
    ```

    ## Anti-patterns
    - Stuffing keywords into the business name ("Joe's Plumbing – Best Plumber Austin").
    - Different phone numbers per listing for call tracking without a consistent primary.
    - Responding to negative reviews by arguing the facts in public.
    - Offering a discount for reviews or "in exchange for removing the review" — policy violation.
    - Ten location pages that differ only in the city name; each needs local proof.
    - Chasing 500 directory citations. The top 10 sources and consistency matter; the rest is noise.
    """,
)

STREET_ABBR = {
    "street": "st", "st.": "st", "avenue": "ave", "ave.": "ave", "av": "ave", "boulevard": "blvd", "blvd.": "blvd", "road": "rd", "rd.": "rd",
    "drive": "dr", "dr.": "dr", "lane": "ln", "ln.": "ln", "court": "ct", "ct.": "ct", "place": "pl", "pl.": "pl", "square": "sq", "highway": "hwy",
    "parkway": "pkwy", "circle": "cir", "terrace": "ter", "way": "way", "north": "n", "south": "s", "east": "e", "west": "w", "n.": "n", "s.": "s", "e.": "e", "w.": "w",
    "suite": "ste", "ste.": "ste", "unit": "ste", "apt": "ste", "apartment": "ste", "#": "ste", "floor": "fl", "fl.": "fl", "building": "bldg",
    "first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th",
}
NAME_NOISE = re.compile(r"\b(llc|inc|incorporated|ltd|limited|co|corp|corporation|the)\b\.?", re.I)


def _norm_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def _fmt_phone(digits: str) -> str:
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return digits


def _norm_address(a: str) -> str:
    s = (a or "").lower().replace(",", " ").replace(".", " ")
    s = re.sub(r"#\s*", " ste ", s)
    toks = [STREET_ABBR.get(t, STREET_ABBR.get(t + ".", t)) for t in s.split()]
    s = " ".join(toks)
    s = re.sub(r"\b(\d{5})-\d{4}\b", r"\1", s)  # zip+4 → zip
    return re.sub(r"\s+", " ", s).strip()


def _norm_name(n: str) -> str:
    s = re.sub(r"['’]", "", (n or "").lower())
    s = NAME_NOISE.sub(" ", s)
    s = s.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@AGENT.tool
def nap_consistency(listings: list[dict]) -> dict:
    """Cross-check name, address and phone across listings after normalising abbreviations, suites, punctuation and phone formats; report every mismatch and the canonical value.

    The canonical value is the most common normalised form (ties go to the source named "gbp"/"google" or
    "website"). Name mismatches ignore LLC/Inc/The; address mismatches ignore St/Street, Ste/#, ZIP+4.

    Args:
        listings: 2-100 dicts like {"source": "gbp", "name": str, "address": str, "phone": str, "website": str}.
    """
    if not listings or len(listings) < 2:
        raise ToolError("Give at least 2 listings to compare.")
    if len(listings) > 100:
        raise ToolError("Max 100 listings.")
    rows = []
    for i, l in enumerate(listings):
        src = str(l.get("source") or f"listing {i + 1}").strip()
        rows.append(
            {
                "source": src,
                "name": str(l.get("name") or "").strip(),
                "address": str(l.get("address") or "").strip(),
                "phone": str(l.get("phone") or "").strip(),
                "website": str(l.get("website") or "").strip().lower().rstrip("/").replace("http://", "https://").replace("https://www.", "https://"),
                "_n": _norm_name(l.get("name") or ""),
                "_a": _norm_address(l.get("address") or ""),
                "_p": _norm_phone(l.get("phone") or ""),
            }
        )
    priority = {"gbp": 0, "google": 0, "google business profile": 0, "website": 1, "site": 1}

    def canonical(key, raw_key):
        vals = [r[key] for r in rows if r[key]]
        if not vals:
            return None, None
        top = Counter(vals).most_common()
        best_n = top[0][1]
        cands = [v for v, n in top if n == best_n]
        chosen = min(cands, key=lambda v: min(priority.get(r["source"].lower(), 5) for r in rows if r[key] == v))
        raw = min((r for r in rows if r[key] == chosen), key=lambda r: priority.get(r["source"].lower(), 5))[raw_key]
        return chosen, raw

    cn, cn_raw = canonical("_n", "name")
    ca, ca_raw = canonical("_a", "address")
    cp, cp_raw = canonical("_p", "phone")
    mismatches = []
    table = []
    for r in rows:
        status = []
        if r["name"] and cn and r["_n"] != cn:
            status.append("name")
            mismatches.append({"source": r["source"], "field": "name", "value": r["name"], "canonical": cn_raw})
        elif not r["name"]:
            status.append("name missing")
        if r["address"] and ca and r["_a"] != ca:
            status.append("address")
            mismatches.append({"source": r["source"], "field": "address", "value": r["address"], "canonical": ca_raw})
        elif not r["address"]:
            status.append("address missing")
        if r["phone"] and cp and r["_p"] != cp:
            status.append("phone")
            mismatches.append({"source": r["source"], "field": "phone", "value": r["phone"], "canonical": _fmt_phone(cp)})
        elif not r["phone"]:
            status.append("phone missing")
        if r["phone"] and len(r["_p"]) not in (0, 10) and not r["_p"].startswith("00"):
            status.append(f"phone has {len(r['_p'])} digits")
        table.append({"source": r["source"], "name": r["name"], "address": r["address"], "phone": r["phone"], "website": r["website"], "status": "ok" if not status else ", ".join(status)})
    # cosmetic differences (same normalised, different raw) — worth aligning too
    cosmetic = []
    for field, key in (("name", "_n"), ("address", "_a"), ("phone", "_p")):
        raws = {r[field] for r in rows if r[field] and r[key] == {"_n": cn, "_a": ca, "_p": cp}[key]}
        if len(raws) > 1:
            cosmetic.append({"field": field, "variants": sorted(raws)})
    sites = {r["website"] for r in rows if r["website"]}
    if len(sites) > 1:
        mismatches.append({"source": "multiple", "field": "website", "value": " | ".join(sorted(sites)), "canonical": "pick one (https, no www vs www consistent)"})
    consistent = not mismatches
    return {
        "canonical": {"name": cn_raw, "address": ca_raw, "phone": _fmt_phone(cp) if cp else None, "phone_digits": cp},
        "table": table,
        "mismatches": mismatches,
        "cosmetic_variants": cosmetic,
        "consistency_pct": round(100 * sum(1 for t in table if t["status"] == "ok") / len(table)),
        "verdict": ("NAP is consistent across all sources." if consistent else f"{len(mismatches)} real mismatch(es) across {len({m['source'] for m in mismatches})} source(s) — update them to the canonical values.") + (f" {len(cosmetic)} field(s) differ only in formatting; align them for safety." if cosmetic else ""),
    }


GBP_WEIGHTS = [
    # (field, weight, check, how-to)
    ("primary_category", 15, lambda v: bool(v), "Set the single most specific category (e.g. 'Emergency plumber' not 'Plumber' if that's the business)."),
    ("secondary_categories", 6, lambda v: isinstance(v, list) and len(v) >= 1, "Add 2-5 secondary categories for services you actually provide."),
    ("name_clean", 8, lambda v: v is True, "Business name must be the real-world name — no keywords/city appended."),
    ("address_or_service_area", 6, lambda v: bool(v), "Verified address, or service areas listed (hide address for SABs)."),
    ("phone", 5, lambda v: bool(v), "Primary local phone number matching the website."),
    ("website", 4, lambda v: bool(v), "Link to the location page (add ?utm_source=google&utm_medium=organic&utm_campaign=gbp)."),
    ("hours", 8, lambda v: bool(v), "Set regular hours and keep special hours updated for holidays."),
    ("description", 6, lambda v: isinstance(v, str) and 250 <= len(v) <= 750, "Write 250-750 characters: what you do, for whom, where, since when. Key services in the first 250."),
    ("photos", 8, lambda v: isinstance(v, (int, float)) and v >= 10, "Upload ≥ 10 photos (exterior, interior, team, work) and add 1-2 per week."),
    ("services_or_products", 8, lambda v: isinstance(v, (int, float)) and v >= 5, "List ≥ 5 services/products with descriptions and prices where possible."),
    ("attributes", 4, lambda v: isinstance(v, (int, float)) and v >= 3, "Fill attributes (accessibility, payments, amenities, identity)."),
    ("posts_days_since_last", 6, lambda v: isinstance(v, (int, float)) and v <= 14, "Post at least every 2 weeks (offers, updates, events)."),
    ("qa_seeded", 4, lambda v: v is True, "Seed 3-5 Q&As with the questions customers actually ask."),
    ("reviews_count", 6, lambda v: isinstance(v, (int, float)) and v >= 20, "Get to ≥ 20 reviews; then keep a steady velocity."),
    ("review_response_rate", 6, lambda v: isinstance(v, (int, float)) and v >= 0.9, "Respond to every review within 48 hours (≥ 90% response rate)."),
]


@AGENT.tool
def gbp_completeness(profile: dict) -> dict:
    """Score a Google Business Profile 0-100 on the fields that move map-pack rankings and list the missing items in impact order with the exact fix.

    Args:
        profile: Dict with any of: primary_category (str), secondary_categories (list), name_clean (bool: name has no added keywords), address_or_service_area (str), phone (str), website (str), hours (bool/str), description (str), photos (int), services_or_products (int), attributes (int), posts_days_since_last (int), qa_seeded (bool), reviews_count (int), review_response_rate (0-1).
    """
    if not isinstance(profile, dict) or not profile:
        raise ToolError("profile must be a non-empty dict of GBP fields.")
    known = {f for f, *_ in GBP_WEIGHTS}
    unknown = sorted(set(profile) - known)
    score, missing, present = 0, [], []
    for field, w, check, howto in GBP_WEIGHTS:
        v = profile.get(field)
        if field == "review_response_rate" and isinstance(v, (int, float)) and v > 1:
            v = v / 100
        ok = False
        try:
            ok = bool(check(v))
        except Exception:
            ok = False
        if ok:
            score += w
            present.append(field)
        else:
            missing.append({"field": field, "weight": w, "current": v, "fix": howto})
    missing.sort(key=lambda m: -m["weight"])
    desc = profile.get("description")
    notes = []
    if isinstance(desc, str) and desc:
        notes.append(f"description is {len(desc)} chars" + (" (max 750)" if len(desc) > 750 else ""))
    if profile.get("name_clean") is False:
        notes.append("Keyword-stuffed name: fix first — it risks suspension and competitors can report it.")
    return {
        "score": score,
        "grade": "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 55 else "D",
        "present": present,
        "missing": missing,
        "unknown_fields_ignored": unknown,
        "notes": notes,
        "top_3_fixes": [f"{m['field']}: {m['fix']}" for m in missing[:3]],
        "verdict": f"{score}/100. " + (f"Biggest gaps: {', '.join(m['field'] for m in missing[:3])}." if missing else "Profile is complete — focus on reviews and posts cadence."),
    }


@AGENT.tool
def review_stats(reviews: list[dict], target_rating: float = 4.5, today: str = "") -> dict:
    """Compute rating average and distribution, review velocity per month, 90-day trend, and how many consecutive 5-star reviews reach a target rating.

    Args:
        reviews: List of {"date": "YYYY-MM-DD", "rating": 1-5} (up to 5000); date optional but needed for velocity.
        target_rating: The star rating you want to reach (1-5).
        today: Reference date YYYY-MM-DD for velocity windows; defaults to today.
    """
    if not reviews:
        raise ToolError("reviews is empty.")
    if len(reviews) > 5000:
        raise ToolError("Max 5000 reviews.")
    tgt = float(target_rating)
    if not 1 <= tgt <= 5:
        raise ToolError("target_rating must be 1-5.")
    ref = dates.parse_date(today) if today else date.today()
    ratings, dated = [], []
    for i, r in enumerate(reviews):
        try:
            rt = float(r.get("rating"))
        except (TypeError, ValueError):
            raise ToolError(f"reviews[{i}]: rating must be a number 1-5.") from None
        if not 1 <= rt <= 5:
            raise ToolError(f"reviews[{i}]: rating {rt} outside 1-5.")
        ratings.append(rt)
        if r.get("date"):
            dated.append((dates.parse_date(str(r["date"])), rt))
    n = len(ratings)
    total = sum(ratings)
    avg = total / n
    dist = {str(s): sum(1 for r in ratings if int(round(r)) == s) for s in range(5, 0, -1)}
    # k five-star reviews so that (total + 5k)/(n + k) >= tgt  →  k >= (tgt*n - total)/(5 - tgt)
    if avg >= tgt:
        needed = 0
    elif tgt >= 5:
        needed = None
    else:
        needed = max(0, math.ceil((tgt * n - total) / (5 - tgt) - 1e-9))
    # displayed rating rounds to 1 decimal on Google
    displayed = round(avg + 1e-9, 1)
    out = {
        "count": n,
        "average": round(avg, 3),
        "displayed_rating": displayed,
        "distribution": dist,
        "pct_5_star": round(100 * dist["5"] / n, 1),
        "pct_1_2_star": round(100 * (dist["1"] + dist["2"]) / n, 1),
        "target_rating": tgt,
        "five_star_reviews_needed_for_target": needed,
    }
    if dated:
        dated.sort()
        first, last = dated[0][0], dated[-1][0]
        span_months = max(1.0, (ref - first).days / 30.44)
        last90 = [rt for d, rt in dated if d > ref - timedelta(days=90)]
        prior90 = [rt for d, rt in dated if ref - timedelta(days=180) < d <= ref - timedelta(days=90)]
        last12 = [rt for d, rt in dated if d > ref - timedelta(days=365)]
        out.update(
            {
                "first_review": first.isoformat(),
                "last_review": last.isoformat(),
                "days_since_last_review": (ref - last).days,
                "velocity_per_month_all_time": round(len(dated) / span_months, 2),
                "velocity_per_month_last_90d": round(len(last90) / 3, 2),
                "velocity_per_month_prior_90d": round(len(prior90) / 3, 2),
                "avg_last_90d": round(sum(last90) / len(last90), 2) if last90 else None,
                "avg_prior_90d": round(sum(prior90) / len(prior90), 2) if prior90 else None,
                "reviews_last_12_months": len(last12),
                "trend": ("accelerating" if len(last90) > len(prior90) * 1.2 else "slowing" if len(last90) < len(prior90) * 0.8 else "steady"),
            }
        )
        if needed:
            v = max(out["velocity_per_month_last_90d"], 0.1)
            out["months_to_target_at_current_velocity_if_all_5_star"] = round(needed / v, 1)
    stale = out.get("days_since_last_review", 0) > 60
    verdict = f"{displayed}★ from {n} reviews."
    if needed:
        verdict += f" {needed} consecutive 5★ reviews reach {tgt:g}★."
    elif needed == 0:
        verdict += f" Already at or above {tgt:g}★ — protect it with steady velocity."
    if dated:
        verdict += f" Velocity {out['velocity_per_month_last_90d']}/month (last 90d), {out['trend']}."
        if stale:
            verdict += f" No review in {out['days_since_last_review']} days — recency matters; start asking this week."
    out["verdict"] = verdict
    out["monthly_ask_target"] = max(4, math.ceil((needed or 0) / 3)) if needed is not None else 4
    return out


DEFENSIVE = re.compile(r"\b(you failed|you didn'?t|your fault|not our fault|you should have|never happened|(?:that|this)(?:'?s| is) not true|you are (?:wrong|lying|mistaken)|as we told you|unfortunately you|we disagree|frankly|actually,)\b", re.I)
INCENTIVE = re.compile(r"\b(discount|coupon|free|refund|credit|gift card|% off|compensat|in exchange|if you (?:remove|change|update|delete) (?:the|your) review)\b", re.I)
APOLOGY = re.compile(r"\b(sorry|apologi[sz]e|apologies|regret)\b", re.I)
OWNERSHIP = re.compile(r"\b(we (?:fell short|missed|got it wrong|should have|let you down|dropped the ball|take (?:this|that|full) (?:seriously|responsibility))|(?:that|this)(?:'?s| is) on us|our mistake|we own)\b", re.I)
OFFLINE = re.compile(r"(\bcall\b|\bemail\b|\breach (?:out|me)\b|\bcontact\b|@|\(\d{3}\)|\d{3}[-.\s]\d{3}[-.\s]\d{4}|\bdm\b|\bmessage (?:us|me)\b)", re.I)
PII = re.compile(r"\b(invoice|order|account|patient|case) ?#?\s?\d{3,}|\b\d{1,5}\s+\w+\s+(?:st|street|ave|avenue|rd|road|dr|drive)\b|\b\d{2}/\d{2}/\d{4}\b", re.I)
TEMPLATE_SMELL = re.compile(r"\b(valued customer|we strive to|feedback is important to us|we take all feedback seriously|thank you for your feedback)\b", re.I)


@AGENT.tool
def review_response_lint(review: str, rating: int, response: str, reviewer_name: str = "", business_keywords: list[str] | None = None) -> dict:
    """Lint a draft reply to a customer review: length, personalisation, apology/ownership for negatives, no defensiveness, no incentives (policy), no PII, natural service/location mention, offline next step.

    Args:
        review: The customer's review text.
        rating: The star rating given (1-5).
        response: Your draft response.
        reviewer_name: The reviewer's display first name, if shown (used to check personalisation).
        business_keywords: Service/location words worth mentioning once, e.g. ["plumbing", "Austin"] (optional).
    """
    rv = " ".join((review or "").split())
    rs = " ".join((response or "").split())
    try:
        stars = int(rating)
    except (TypeError, ValueError):
        raise ToolError("rating must be an integer 1-5.") from None
    if not 1 <= stars <= 5:
        raise ToolError("rating must be 1-5.")
    if not rs:
        raise ToolError("response is empty.")
    if len(rs) > 5000 or len(rv) > 10000:
        raise ToolError("response max 5000 chars, review max 10000 chars.")
    negative = stars <= 3
    wc = len(_text.words(rs))
    lo, hi = (40, 120) if negative else (20, 60)
    issues, good = [], []
    if wc < lo:
        issues.append(f"{wc} words — too short for a {stars}★ review (aim {lo}-{hi}).")
    elif wc > hi * 1.5:
        issues.append(f"{wc} words — too long (aim {lo}-{hi}); long replies read as defensive.")
    else:
        good.append(f"length {wc} words")
    name = reviewer_name.strip()
    if name and name.lower() not in rs.lower():
        issues.append(f"Doesn't greet the reviewer by name ({name}).")
    elif name:
        good.append("greets by name")
    if TEMPLATE_SMELL.search(rs):
        issues.append(f"Template phrase '{TEMPLATE_SMELL.search(rs).group(0)}' — readers spot canned replies.")
    # specificity: echo a detail from the review
    rv_terms = {t for t in _text.words(rv.lower()) if t not in _text.STOPWORDS and len(t) > 3}
    rs_terms = {t for t in _text.words(rs.lower())}
    echoed = sorted(rv_terms & rs_terms)
    if rv and not echoed:
        issues.append("Doesn't reference anything specific from the review — echo one detail.")
    else:
        good.append(f"references review detail(s): {', '.join(echoed[:3])}")
    if negative:
        if not APOLOGY.search(rs):
            issues.append("No apology for a negative review.")
        else:
            good.append("apologises")
        if not OWNERSHIP.search(rs):
            issues.append("No ownership language ('we fell short', 'that's on us').")
        else:
            good.append("takes ownership")
        if not OFFLINE.search(rs):
            issues.append("No offline next step (name + phone/email to continue privately).")
        else:
            good.append("moves it offline")
    if DEFENSIVE.search(rs):
        issues.append(f"Defensive/blaming phrase: '{DEFENSIVE.search(rs).group(0)}' — remove; you are writing for future readers, not the reviewer.")
    if INCENTIVE.search(rs):
        issues.append(f"Incentive or conditional offer ('{INCENTIVE.search(rs).group(0)}') — violates Google's review policy and invites more complaints. Handle compensation offline.")
    if PII.search(rs):
        issues.append("Contains what looks like personal/account details — never confirm a person was a customer with specifics (HIPAA/privacy).")
    if re.search(r"\b(legal|lawyer|attorney|sue|defamation)\b", rs, re.I):
        issues.append("Legal threats in a public reply always backfire.")
    kws = [k.strip().lower() for k in (business_keywords or []) if k.strip()]
    mentioned = [k for k in kws if k in rs.lower()]
    stuffed = [k for k in kws if rs.lower().count(k) > 2]
    if kws and not mentioned:
        issues.append(f"Mention the service/location once naturally ({', '.join(kws[:3])}) — review replies are indexed.")
    if stuffed:
        issues.append(f"Keyword stuffed: {', '.join(stuffed)} appears 3+ times.")
    if not negative and not re.search(r"\b(see you|welcome back|next time|again soon|come back|look forward)\b", rs, re.I):
        issues.append("Positive reply without an invitation to return.")
    excl = rs.count("!")
    if excl > 2:
        issues.append(f"{excl} exclamation marks — tone down.")
    blocking = any(k in i for i in issues for k in ("Incentive", "Defensive", "personal/account", "Legal"))
    score = max(0, 100 - 12 * len(issues) - (30 if blocking else 0))
    return {
        "rating": stars,
        "sentiment": "negative" if negative else "positive",
        "words": wc,
        "target_words": f"{lo}-{hi}",
        "passes": score >= 70 and not blocking,
        "score": score,
        "blocking": blocking,
        "good": good,
        "issues": issues,
        "verdict": ("Ready to post." if score >= 70 and not blocking else "Revise before posting" + (" — policy/tone problem." if blocking else ".")),
    }
