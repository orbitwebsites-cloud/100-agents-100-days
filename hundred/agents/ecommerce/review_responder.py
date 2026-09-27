"""Review Responder — tags every review by issue, prioritises the queue, lints replies, and does the star-rating math."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime

from ...core import Agent, ToolError
from ...lib import text
from ._common import pct

AGENT = Agent(
    slug="review-responder",
    name="Review Responder",
    category="ecommerce",
    tagline="Answer every review like a brand people trust — tagged by issue, prioritised, linted, and with the rating math done.",
    description=(
        "Handles product and store reviews end to end: tags each review by sentiment and issue (shipping, "
        "quality, sizing, service, wrong item…), builds the response queue by urgency, checks each drafted "
        "reply against the rules that separate trusted brands from defensive ones (specific acknowledgement, "
        "offline path, no public refunds, no legal admissions, no template smell), flags reviews that violate "
        "platform policy, and computes exactly how many new reviews move the average to your target."
    ),
    triggers=[
        "respond to this review / write a reply to a 1-star review",
        "reply to customer reviews on Amazon / Google / Etsy / Shopify / Trustpilot",
        "what are customers complaining about in these reviews",
        "how many 5-star reviews do I need to get to 4.5",
        "can I get this review removed / does it violate policy",
        "review response templates for my store",
    ],
    examples=[
        "Here are 60 reviews from last month. What are the top issues and which ones should I reply to first?",
        "Reply to this 2-star: 'Took 3 weeks to arrive and the lid was cracked. Support never answered.' Reviewer is Dana.",
        "We're at 4.2 stars from 180 reviews on Amazon. How many 5-stars to reach 4.5?",
    ],
    connectors=["Shopify", "Amazon Seller Central", "Google Business Profile", "Trustpilot", "Yotpo", "Judge.me", "Gorgias"],
    playbook="""
    ## Standard
    You are the CX lead whose review replies get screenshotted as examples of how to do it.
    The one metric that matters is **future-buyer trust**: every public reply is read by 10-100
    prospects for each reviewer. Excellent replies are specific (they prove the review was
    read), accountable (they say what changed), short, and move any negotiation offline.
    Nothing generic, nothing defensive, no template smell.

    ## Intake
    You need the review text(s), star rating, platform, reviewer name if shown, and the
    brand's sign-off (name + role). Optional but valuable: order context (was it late, was
    a replacement sent), what the agent may offer, and current average rating + count.
    Ask at most 3 questions only if you cannot proceed (e.g. no platform stated — it
    changes what you may say). Otherwise assume and state.

    ## Procedure
    1. **Tag and prioritise.** For a batch, call `review_responder__tag_reviews`. It returns
       per-review sentiment, issue tags, urgency, the aggregated issue table (share of reviews
       and average rating per issue) and the order to reply in. Reply to the queue in that
       order: 1-2 stars with a service/defect issue first, recent before old, 5-stars last.
    2. **Draft the reply** using the rating-specific structure (Frameworks). Mirror the
       reviewer's exact issue words. For ≤ 3 stars give the offline path with a real
       address/handle. For 4-5 stars, thank for the specific praise and add one useful line
       (care tip, how others use it). Never mention refunds, discounts or coupon codes in
       public.
    3. **Lint before posting.** Call `review_responder__lint_response` with the draft, the
       review, the rating and the reviewer name. Fix anything it flags; re-run until it
       says post-ready. Aim ≤ 120 words for negatives, ≤ 60 for positives.
    4. **Check policy** when a review looks off-topic, abusive, contains personal data or
       is about the courier rather than the product: call `review_responder__check_reportable`.
       If reportable, reply anyway (briefly, gracious) and file the report — removal is not
       guaranteed and the reply protects you meanwhile.
    5. **Do the rating math** when the user asks about their star rating: call
       `review_responder__rating_math`. Give the number of 5-stars needed, what one more
       1-star does, and the review-request velocity needed to get there in the time they
       want.
    6. **Close the loop internally**: from the issue table, name the top 2 root causes and
       the owner (ops, product, support) — replies fix perception; only operations fixes
       the next review.
    7. **Self-check**: each reply names the specific issue, has one apology max, one
       concrete action, an offline path (≤ 3 stars), a signed name, no refund/discount words,
       no "sorry you feel", no "however/but" pivot to defence.

    ## Frameworks
    - **Negative (1-3★) — AAO:** Acknowledge the specific issue in their words → Account
      (what you found / changed, one line; no excuses) → Offline (name + channel + "we'll make
      it right"). 60-120 words. One apology. Sign with a first name and role.
    - **Positive (4-5★) — TSA:** Thank by name → Specific (echo the detail they praised) →
      Add value (a tip, a use, a pairing). 20-60 words. No hard upsell, no "check out our…".
    - **Mixed (3-4★):** thank for the balanced view, address the one criticism concretely.
    - **Never in public:** refund amounts, coupon/discount codes, order numbers, the
      customer's email, blaming the carrier, "known issue", "defective batch", any admission
      that reads as liability. Not legal advice; involve counsel for injury or safety claims.
    - **Response timing:** reply to ≤ 3★ within 24-48h, to 5★ within a week. Respond to at
      least every review ≤ 3★ and a sample of 5★ — 100% reply rate on negatives.
    - **Rating math:** to move an average A over n reviews to target T with only new 5★:
      k = n·(T − A) ÷ (5 − T). Platforms display to 0.1 (Amazon rounds to nearest 0.1 with
      weighting; Google to 0.1), so target 4.45+ to show 4.5.
    - **Issue tags that predict returns:** sizing/fit, not-as-described and defect. Anything
      > 10% of reviews goes to product/ops with the quotes.

    ## Output format
    ```
    # Review replies — <platform> · <n> reviews · avg <A> (<distribution>)
    ## Priority queue
    | # | Rating | Issue tags | Urgency | Reviewer |
    ## Replies
    ### <#> — <rating>★ <reviewer> — <issue tags>
    <reply, mirroring their words, signed>
    _(lint: score/100 · ready)_
    ## Issues to fix upstream
    | Issue | % of reviews | Avg rating | Owner | Evidence quote |
    ## Rating plan
    <k 5★ reviews to reach T; suggested review-request tactic and velocity>
    ```

    ## Anti-patterns
    - "We're sorry you feel that way" / "We're sorry for any inconvenience" — non-apologies.
    - "Thank you for your feedback! We appreciate your business!" on a 1-star.
    - Explaining why the customer is wrong, or citing policy, in public.
    - Offering a refund or code in the reply (invites bad-faith reviews; violates Amazon/Google
      incentive rules in some cases).
    - Same paragraph pasted under ten reviews — prospects notice, and so do platforms.
    - Replying to every 5-star with three sentences of thanks and no substance.
    """,
)

ISSUE_TAGS: list[tuple[str, str]] = [
    ("shipping_delay", r"\b(late|delay|took (\d+|two|three|four|five) (weeks?|days?)|slow (shipping|delivery)|never (arrived|came|received)|still waiting|weeks to arrive|shipping (was|took))\b"),
    ("damaged_on_arrival", r"\b(arrived (broken|damaged|cracked|dented|leaking|shattered)|broken (on arrival|when it arrived)|damaged (box|package|in transit)|cracked|shattered|dented)\b"),
    ("defect_quality", r"\b(stopped working|doesn'?t work|broke (after|within)|fell apart|cheap(ly made)?|flimsy|poor quality|low quality|faulty|defective|peeling|ripped|tore|malfunction)\b"),
    ("sizing_fit", r"\b(runs? (small|large|big)|too (small|big|large|tight|loose|short|long)|doesn'?t fit|size (up|down)|wrong size|fits? (perfectly|great|true to size)|true to size)\b"),
    ("not_as_described", r"\b(not as (described|pictured|advertised|shown)|looks nothing like|different (from|than) (the )?(picture|photo|listing)|misleading|false advertising|smaller than (expected|it looks))\b"),
    ("wrong_item", r"\b(wrong (item|product|colou?r|size)|received (the )?wrong|not what i ordered|missing (item|part|piece)s?)\b"),
    ("customer_service", r"\b(customer (service|support)|support (never|didn'?t|hasn'?t)|no (response|reply|one (answered|responded))|never (responded|replied|answered)|ignored|rude|unhelpful|helpful (support|team|service))\b"),
    ("price_value", r"\b(overpriced|not worth|waste of money|too expensive|rip[- ]?off|great value|worth (every penny|the money|it)|good value|for the price)\b"),
    ("packaging", r"\b(packaging|packaged|box was|wrapped|unboxing)\b"),
    ("returns_refund", r"\b(refund|return(ed|ing)? (it|this|process|policy)|money back|restocking fee)\b"),
    ("smell_taste_texture", r"\b(smell(s|ed)?|odou?r|taste[sd]?|texture|sticky|greasy)\b"),
    ("praise_quality", r"\b(love (it|this|them)|excellent|amazing|perfect|high quality|well made|sturdy|durable|works (great|perfectly)|exceeded (my )?expectations|highly recommend|best (purchase|buy))\b"),
]
NEG_WORDS = re.compile(r"\b(terrible|awful|horrible|worst|disappoint(ed|ing)|useless|garbage|junk|never again|regret|frustrat(ed|ing)|angry|scam|broken|cheap|flimsy|poor|bad|hate|waste|returned|refund)\b", re.I)
POS_WORDS = re.compile(r"\b(love|great|excellent|amazing|perfect|fantastic|wonderful|awesome|recommend|happy|pleased|impressed|best|quality|sturdy|beautiful|fast|easy|works)\b", re.I)


def _sentiment(txt: str, rating: float | None) -> str:
    neg, pos = len(NEG_WORDS.findall(txt)), len(POS_WORDS.findall(txt))
    lex = "negative" if neg > pos else ("positive" if pos > neg else "neutral")
    if rating is None:
        return lex
    if rating <= 2:
        return "negative"
    if rating >= 4:
        return "mixed" if neg >= 2 and neg >= pos else "positive"
    return "mixed" if pos and neg else lex


@AGENT.tool
def tag_reviews(reviews: list[dict], today: str = "") -> dict:
    """Tag reviews by sentiment and issue, build the reply-priority queue, and aggregate the issue table (share and average rating per issue).

    Args:
        reviews: List of {"id": str, "rating": 1-5, "text": str, "reviewer": str (optional), "date": "YYYY-MM-DD" (optional), "verified": bool (optional)}.
        today: Today's date (YYYY-MM-DD) for recency; defaults to the real today.
    """
    if not reviews:
        raise ToolError("reviews is empty.")
    if len(reviews) > 500:
        raise ToolError("Max 500 reviews per call.")
    ref = date.fromisoformat(today) if today else date.today()
    rows, dist = [], Counter()
    issue_ratings: dict[str, list[float]] = defaultdict(list)
    issue_quotes: dict[str, str] = {}
    for i, r in enumerate(reviews, 1):
        txt = str(r.get("text", "") or "")
        if len(txt) > 10000:
            raise ToolError(f"review {r.get('id', i)}: text too long (10k chars max).")
        rating = r.get("rating")
        try:
            rating = float(rating) if rating is not None else None
        except (TypeError, ValueError):
            raise ToolError(f"review {r.get('id', i)}: rating must be a number 1-5.") from None
        if rating is not None and not 1 <= rating <= 5:
            raise ToolError(f"review {r.get('id', i)}: rating must be 1-5.")
        low = txt.lower()
        tags = [tag for tag, rx in ISSUE_TAGS if re.search(rx, low)]
        sent = _sentiment(txt, rating)
        days_old = None
        if r.get("date"):
            try:
                days_old = (ref - datetime.fromisoformat(str(r["date"])[:19]).date()).days
            except ValueError:
                raise ToolError(f"review {r.get('id', i)}: date must be YYYY-MM-DD.") from None
        urgency = 0
        if rating is not None:
            urgency += {1: 50, 2: 40, 3: 25, 4: 8, 5: 3}[int(round(rating))]
        elif sent == "negative":
            urgency += 35
        service_or_defect = {"customer_service", "defect_quality", "damaged_on_arrival", "wrong_item", "not_as_described"} & set(tags)
        urgency += 10 * len(service_or_defect)
        if "returns_refund" in tags:
            urgency += 8
        if days_old is not None and days_old <= 7:
            urgency += 10
        if len(text.words(txt)) >= 60:
            urgency += 5  # long reviews get read by more prospects
        if urgency >= 60:
            level = "reply today"
        elif urgency >= 35:
            level = "reply within 48h"
        elif urgency >= 12:
            level = "reply this week"
        else:
            level = "optional / sample"
        if rating is not None:
            dist[int(round(rating))] += 1
        for t in tags:
            if rating is not None:
                issue_ratings[t].append(rating)
            issue_quotes.setdefault(t, txt[:160])
        rows.append(
            {
                "id": str(r.get("id", i)),
                "rating": rating,
                "reviewer": r.get("reviewer"),
                "sentiment": sent,
                "issue_tags": tags,
                "days_old": days_old,
                "urgency_score": urgency,
                "urgency": level,
                "words": len(text.words(txt)),
                "reply_structure": "AAO (acknowledge, account, offline)" if (rating is not None and rating <= 3) or sent == "negative" else "TSA (thank, specific, add value)",
            }
        )
    n = len(rows)
    rated = [r["rating"] for r in rows if r["rating"] is not None]
    avg = sum(rated) / len(rated) if rated else None
    issues = []
    for t, rs in sorted(issue_ratings.items(), key=lambda kv: -len(kv[1])):
        issues.append({"issue": t, "reviews": len(rs), "share_pct": pct(len(rs) / n), "avg_rating": round(sum(rs) / len(rs), 2), "evidence": issue_quotes.get(t, "")})
    untagged = [r["id"] for r in rows if not r["issue_tags"]]
    queue = sorted(rows, key=lambda r: -r["urgency_score"])
    upstream = [i for i in issues if i["share_pct"] >= 10 and i["issue"] != "praise_quality" and i["avg_rating"] <= 3.5]
    return {
        "reviews": rows,
        "queue_order": [r["id"] for r in queue],
        "average_rating": round(avg, 2) if avg is not None else None,
        "distribution": {str(k): dist[k] for k in sorted(dist)},
        "negative_share_pct": pct(sum(dist[k] for k in (1, 2)) / len(rated)) if rated else None,
        "issues": issues,
        "escalate_upstream": upstream,
        "untagged_ids": untagged,
        "summary": (
            f"{n} reviews, avg {avg:.2f}" if avg is not None else f"{n} reviews"
        ) + f"; {len([r for r in rows if r['urgency'] == 'reply today'])} need a reply today. Top issues: " + ", ".join(f"{i['issue']} ({i['share_pct']}%)" for i in issues[:3]) + ".",
    }


NON_APOLOGY = ["sorry you feel", "sorry that you feel", "sorry for any inconvenience", "sorry for the inconvenience", "regret any inconvenience", "we apologize for any"]
DEFENSIVE = re.compile(r"\b(however|but our|but we|we never|you should have|you didn'?t|as (stated|mentioned|noted) (in|on)|our policy|per our|clearly (states|stated)|it is not our|not our fault|the carrier|usps|fedex|ups|dhl|out of our (control|hands)|beyond our control)\b", re.I)
PUBLIC_MONEY = re.compile(r"\b(refund(ed|ing)?|discount|coupon|promo code|voucher|store credit|\d+% off|free (product|replacement|gift)|gift card)\b", re.I)
ADMISSION = re.compile(r"\b(known issue|defective batch|bad batch|quality control (issue|failure)|our (fault|mistake|error)|liab(le|ility)|recall(ed)?|design flaw|manufacturing defect)\b", re.I)
PII = re.compile(r"(order\s*#?\s*\d{3,}|[\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{8,}\d)", re.I)
OFFLINE = re.compile(r"\b(email|e-mail|dm|message us|reach (me|us)|contact (me|us)|call us|text us|support@|help@|care@|@[\w.]+|\.com|whatsapp|phone)\b", re.I)
TEMPLATE_SMELL = ["we appreciate your business", "thank you for your feedback", "your feedback is important", "we value your", "we strive to", "we take (this|all) (feedback|concerns) seriously", "please accept our", "we hope to serve you again", "valued customer", "we're glad to hear", "thanks for the review"]


@AGENT.tool
def lint_response(response: str, review_text: str, rating: float, reviewer_name: str = "", platform: str = "generic") -> dict:
    """Check a drafted review reply against the rules that make it trustworthy in public: specificity, apology, offline path, no refunds/PII/admissions/defensiveness, length, sign-off.

    Args:
        response: The drafted public reply.
        review_text: The customer's review text.
        rating: The review's star rating 1-5.
        reviewer_name: Reviewer's display name as shown on the platform ("" if anonymous).
        platform: amazon, google, etsy, shopify, trustpilot, yelp, app_store or generic (affects a few rules).
    """
    if not response.strip():
        raise ToolError("response is empty.")
    if len(response) > 10000 or len(review_text) > 10000:
        raise ToolError("Text too long (10k chars max each).")
    if not 1 <= rating <= 5:
        raise ToolError("rating must be 1-5.")
    negative = rating <= 3
    low = response.lower()
    words = len(text.words(response))
    issues, score = [], 100
    lo, hi = (50, 120) if negative else (15, 60)
    if words < lo:
        issues.append(f"{words} words — too short for a {rating:g}★ reply (aim {lo}-{hi})")
        score -= 10
    elif words > hi:
        issues.append(f"{words} words — too long (aim {lo}-{hi}); prospects skim")
        score -= 10
    # specificity: mirror the review's key terms
    key = [w for w, _ in text.top_terms(review_text, 8)]
    mirrored = [w for w in key if re.search(r"\b" + re.escape(w) + r"\w*", low)]
    if key and len(mirrored) < max(1, math.ceil(len(key) * 0.25)):
        issues.append(f"generic — mirrors none of the reviewer's words ({', '.join(key[:5])})")
        score -= 20
    if reviewer_name.strip():
        first = reviewer_name.strip().split()[0].lower()
        if first not in low and len(first) > 1:
            issues.append(f"does not address {reviewer_name.strip().split()[0]} by name")
            score -= 8
    apol = len(re.findall(r"\b(sorry|apologi[sz]e|apologies)\b", low))
    if negative and apol == 0:
        issues.append("no apology on a negative review")
        score -= 12
    if apol > 1:
        issues.append(f"{apol} apologies — one, specific")
        score -= 6
    na = [p for p in NON_APOLOGY if p in low]
    if na:
        issues.append(f"non-apology: “{na[0]}”")
        score -= 15
    d = DEFENSIVE.search(response)
    if d:
        issues.append(f"defensive/deflecting: “{d.group(0)}”")
        score -= 15
    m = PUBLIC_MONEY.search(response)
    if m:
        issues.append(f"public money talk: “{m.group(0)}” — take it offline (Amazon/Google treat public incentives as policy risk)")
        score -= 15
    a = ADMISSION.search(response)
    if a:
        issues.append(f"liability-style admission: “{a.group(0)}” — describe the fix, not the failure category")
        score -= 12
    p = PII.search(response)
    if p and not re.search(r"(support|help|care|hello|team)@", p.group(0), re.I):
        issues.append(f"personal/order data in public: “{p.group(0).strip()}”")
        score -= 12
    if negative and not OFFLINE.search(response):
        issues.append("no offline path (email/DM/phone) to resolve it")
        score -= 15
    if negative and not re.search(r"\b(i'?ve|we'?ve|i'?ll|we'?ll|i have|we have|already|sent|replaced|changed|fixed|updated|shipped)\b", low):
        issues.append("no concrete action stated (what you did or will do)")
        score -= 12
    smell = [t for t in TEMPLATE_SMELL if re.search(t, low)]
    if smell:
        issues.append(f"template smell: “{smell[0]}”")
        score -= 8
    if response.count("!") > (0 if negative else 1):
        issues.append("exclamation marks — none on negatives, max one on positives")
        score -= 5
    caps = [w for w in text.words(response) if len(w) > 3 and w.isupper()]
    if caps:
        issues.append(f"ALL CAPS: {', '.join(caps[:3])}")
        score -= 5
    if not re.search(r"(—|-|–|\n)\s*[A-Z][a-z]+(\s*,\s*[\w &]+)?\s*$", response.strip()) and not re.search(r"\b(best|thanks|regards|cheers|warmly)[,]?\s*\n?\s*[A-Z][a-z]+", response):
        issues.append("no signed name/role at the end (e.g. “— Maya, Customer Care”)")
        score -= 6
    if platform.lower() == "amazon" and re.search(r"\b(leave|update|change|edit) (your|the) review\b", low):
        issues.append("asking to change the review — prohibited on Amazon")
        score -= 20
    if not negative and re.search(r"\b(check out|shop our|browse our|use code|don'?t forget to)\b", low):
        issues.append("hard upsell on a positive review — one useful line, not a pitch")
        score -= 8
    score = max(0, score)
    return {
        "score": score,
        "words": words,
        "target_words": [lo, hi],
        "mirrored_terms": mirrored,
        "issues": issues,
        "ready_to_post": score >= 80 and not any(k in " ".join(issues) for k in ("public money", "personal/order data", "prohibited")),
        "verdict": ("Post-ready." if score >= 80 else f"Fix {len(issues)} issue(s) first.") + f" ({score}/100)",
    }


@AGENT.tool
def rating_math(current_average: float, review_count: int, target_average: float, new_rating: float = 5.0, monthly_reviews: int = 0, positive_share_pct: float = 85.0) -> dict:
    """Compute how many new reviews at a given star level move the average to the target, the damage one 1-star does, and the months it takes at your review velocity.

    Args:
        current_average: Current average rating (e.g. 4.21).
        review_count: Number of reviews behind that average.
        target_average: The average you want to display (e.g. 4.5; platforms round to 0.1 so 4.45 shows as 4.5).
        new_rating: The rating assumed for new reviews (5 for a best case; use your actual positive average like 4.8 for a realistic case).
        monthly_reviews: Reviews you currently collect per month (0 to skip the time estimate).
        positive_share_pct: Share of new reviews that land at new_rating; the rest are assumed to average 2.5.
    """
    if not 1 <= current_average <= 5 or not 1 <= target_average <= 5 or not 1 <= new_rating <= 5:
        raise ToolError("Averages and ratings must be between 1 and 5.")
    if review_count < 0:
        raise ToolError("review_count must be >= 0.")
    if target_average <= current_average:
        return {"reviews_needed": 0, "verdict": f"Already at {current_average:.2f} ≥ target {target_average:.2f}."}
    if new_rating <= target_average:
        raise ToolError(f"New reviews at {new_rating} can never lift the average to {target_average}.")
    total = current_average * review_count
    k_pure = review_count * (target_average - current_average) / (new_rating - target_average)
    k_pure = math.ceil(k_pure)
    share = positive_share_pct / 100 if positive_share_pct > 1 else positive_share_pct
    if not 0 < share <= 1:
        raise ToolError("positive_share_pct must be between 1 and 100.")
    blended = share * new_rating + (1 - share) * 2.5
    k_real = math.ceil(review_count * (target_average - current_average) / (blended - target_average)) if blended > target_average else None
    one_star = (total + 1) / (review_count + 1) if review_count >= 0 else None
    one_five = (total + 5) / (review_count + 1)
    out = {
        "current": {"average": current_average, "count": review_count},
        "target": target_average,
        "reviews_needed_if_all_new_rating": k_pure,
        "blended_new_rating": round(blended, 2),
        "reviews_needed_realistic": k_real,
        "average_after_one_1_star": round(one_star, 3),
        "average_after_one_5_star": round(one_five, 3),
        "five_stars_to_offset_one_1_star": math.ceil((current_average - 1) / (5 - current_average)) if current_average < 5 else None,
        "formula": "k = n·(T − A) ÷ (R − T)",
        "verdict": f"{k_pure} straight {new_rating:g}★ reviews (or ~{k_real} at a realistic {blended:.2f} blend) take {current_average:.2f} → {target_average:.2f}. One more 1★ drops you to {one_star:.2f}.",
    }
    if monthly_reviews > 0 and k_real:
        months = k_real / monthly_reviews
        out["months_at_current_velocity"] = round(months, 1)
        out["monthly_reviews_to_hit_in_3_months"] = math.ceil(k_real / 3)
        out["verdict"] += f" At {monthly_reviews}/month that is {months:.1f} months; to do it in 3 months you need {math.ceil(k_real / 3)}/month."
    return out


PROFANITY = re.compile(r"\b(fuck\w*|shit\w*|bitch\w*|asshole|bastard|damn|crap|wtf|bullshit)\b", re.I)
COMPETITOR = re.compile(r"\b(cheaper (on|at)|buy (it )?(from|on|at) \w+ instead|go with \w+ instead|better (on|at) (amazon|walmart|temu|aliexpress|ebay)|\b(temu|aliexpress|shein)\b)\b", re.I)
WRONG_PRODUCT = re.compile(r"\b(this (isn'?t|is not) the (product|item) i (reviewed|ordered|bought)|reviewing the wrong|meant to review|different product|wrong listing)\b", re.I)
COURIER_ONLY = re.compile(r"\b(courier|carrier|delivery driver|postman|mailman|usps|fedex|ups|dhl|royal mail|left (it )?(at|on|in) the|porch|stolen)\b", re.I)
PRODUCT_WORDS = re.compile(r"\b(quality|works?|fit|size|material|colou?r|taste|smell|feel|texture|design|battery|fabric|sound|comfortable|durable|broke|use[ds]?|using)\b", re.I)
THREAT = re.compile(r"\b(i will (find|hurt|kill)|threat\w*|you'?ll (regret|pay)|watch your back|kill (you|yourself))\b", re.I)
PRIVATE_INFO = re.compile(r"([\w.+-]+@[\w-]+\.[\w.]+|\+?\d[\d\s().-]{8,}\d|\b\d{1,5} [A-Z][a-z]+ (street|st|ave|avenue|road|rd|lane|ln|drive|dr)\b)", re.I)
POLICY_NOTES = {
    "amazon": "Report via 'Report abuse' / Seller Central → Customer reviews. Amazon removes reviews that are about seller/shipping service on FBA orders, contain profanity/PII/promotional content, or are for a different product. Reviews about the product itself are never removed for being negative.",
    "google": "Flag in Google Business Profile → Reviews. Removable: spam/fake, off-topic, restricted content, conflict of interest (competitor/ex-employee), harassment, personal information. Negative but honest experiences stay.",
    "etsy": "Etsy removes reviews containing private info, obscenity, harassment, or that are about a different shop; reviews about shipping delays generally stay. Report via the review's flag menu.",
    "trustpilot": "Flag via the business dashboard: no genuine experience, harmful/illegal content, personal information, or conflict of interest. Trustpilot requires evidence and the review stays visible while assessed.",
    "shopify": "Reviews live in your app (Judge.me, Yotpo, Loox…): you may hide reviews under the app's rules, but hiding honest negatives erodes trust and some apps show 'store hid reviews'.",
    "generic": "Check the platform's content policy; the usual removable categories are personal info, profanity/harassment, off-topic, wrong product, competitor promotion and conflict of interest.",
}


@AGENT.tool
def check_reportable(review_text: str, platform: str = "generic", fulfilled_by_platform: bool = False) -> dict:
    """Check whether a review likely violates the platform's review policy (profanity, personal info, threats, competitor promotion, wrong product, courier-only complaint) and how to report it.

    Args:
        review_text: The review text.
        platform: amazon, google, etsy, trustpilot, shopify or generic.
        fulfilled_by_platform: True if the platform shipped the order (e.g. Amazon FBA) — shipping-only complaints are then reportable as not about the product.
    """
    if not review_text.strip():
        raise ToolError("review_text is empty.")
    if len(review_text) > 10000:
        raise ToolError("review_text too long (10k chars max).")
    pf = platform.lower().strip() or "generic"
    if pf not in POLICY_NOTES:
        pf = "generic"
    reasons = []
    if THREAT.search(review_text):
        reasons.append({"reason": "threat / harassment", "confidence": "high", "evidence": THREAT.search(review_text).group(0)})
    if PROFANITY.search(review_text):
        reasons.append({"reason": "profanity / obscene language", "confidence": "high" if pf in ("amazon", "google") else "medium", "evidence": PROFANITY.search(review_text).group(0)})
    if PRIVATE_INFO.search(review_text):
        reasons.append({"reason": "personal information (email/phone/address)", "confidence": "high", "evidence": PRIVATE_INFO.search(review_text).group(0).strip()})
    if COMPETITOR.search(review_text):
        reasons.append({"reason": "promotes a competitor / other retailer", "confidence": "medium", "evidence": COMPETITOR.search(review_text).group(0)})
    if WRONG_PRODUCT.search(review_text):
        reasons.append({"reason": "review is for a different product", "confidence": "high", "evidence": WRONG_PRODUCT.search(review_text).group(0)})
    courier = COURIER_ONLY.search(review_text)
    product = PRODUCT_WORDS.search(review_text)
    if courier and not product:
        conf = "high" if (pf == "amazon" and fulfilled_by_platform) else ("medium" if pf in ("amazon", "google") else "low")
        reasons.append({"reason": "about delivery/courier only, not the product or seller", "confidence": conf, "evidence": courier.group(0)})
    likely = any(r["confidence"] == "high" for r in reasons)
    return {
        "platform": pf,
        "reportable_reasons": reasons,
        "likely_removable": likely,
        "how_to_report": POLICY_NOTES[pf],
        "reply_anyway": True,
        "verdict": (f"Report it: {reasons[0]['reason']} ({reasons[0]['confidence']} confidence). " if reasons else "No policy violation detected — an honest negative review is not removable. ")
        + "Reply publicly either way; removal takes days and is not guaranteed.",
    }
