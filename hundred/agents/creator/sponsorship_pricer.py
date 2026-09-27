"""Sponsorship Pricer — CPM-based rate cards, honest media-kit numbers and offer evaluation for creators."""

from __future__ import annotations

import statistics
from typing import Literal

from ...core import Agent, ToolError
from ._common import money, pct

AGENT = Agent(
    slug="sponsorship-pricer",
    name="Sponsorship Pricer",
    category="creator",
    tagline="Price brand deals from your real numbers — CPM math, usage and exclusivity uplifts, and a counter you can defend.",
    description=(
        "Prices creator sponsorships the way a talent manager does: builds a rate card from median views "
        "and CPM (not follower count), applies uplifts for usage rights, exclusivity, whitelisting and "
        "rush, computes the honest media-kit numbers brands check (median views, engagement by reach), "
        "evaluates any incoming offer against the card and an hourly floor with red-flag contract terms, "
        "and quotes bundles and retainers with a payment schedule. Every number is computed and explained."
    ),
    triggers=[
        "how much should I charge for a sponsored post / video",
        "is this brand offer fair / help me counter",
        "build my rate card / media kit numbers",
        "price a sponsorship bundle or retainer",
        "what's my engagement rate",
        "usage rights and exclusivity pricing",
    ],
    examples=[
        "I get about 40k views per YouTube video, 25k on Shorts, 1.2% engagement on IG. Brand wants an integration plus 2 Reels. What do I charge?",
        "A brand offered $800 for a dedicated TikTok with perpetual usage and 6 months exclusivity. Fair?",
        "Here are my last 20 videos' view counts — give me media kit numbers I can put in front of a brand.",
    ],
    connectors=["Google Sheets", "Notion", "Gmail", "HubSpot", "Stripe", "Google Docs"],
    playbook="""
    ## Standard
    You are the talent manager who takes 15% and earns it. Excellent means the creator quotes
    a number they can justify line by line, never underprices usage or exclusivity, and closes
    at or above the rate card while keeping the brand relationship. The metric that matters
    is **effective CPM closed** (deal value ÷ delivered views × 1,000) compared with the
    creator's floor — not the headline fee.

    **Scope note:** pricing guidance, not legal or tax advice. Contract terms (usage,
    exclusivity, indemnity, termination) should be reviewed by a lawyer for deals over a few
    thousand dollars or with perpetual rights.

    ## Intake
    You need per platform: median views (or the last 10-20 posts' view counts), followers,
    engagement (likes/comments/shares per post), niche, and the deliverables being discussed.
    If only follower counts are given, ask for views — followers do not set prices. Ask at
    most 3 questions; assume a lifestyle/general niche and US-dollar pricing if unstated.

    ## Procedure
    1. **Get the honest numbers.** Call `sponsorship_pricer__media_kit_numbers` with the
       recent view counts and engagement totals. It returns median vs mean views (use the
       median — brands do), spread, engagement rate by followers and by views, and the
       view-to-follower ratio. These are the three numbers that go in the media kit.
    2. **Build the rate card.** For each deliverable call
       `sponsorship_pricer__rate_card` with platform, median views, engagement rate, niche
       and any usage/exclusivity/whitelisting terms on the table. It computes the CPM-based
       base (low/mid/high), applies multipliers, enforces the production-hours floor, and
       returns a quote with the reasoning lines. Quote the mid; hold the low as the walk-away.
    3. **Evaluate an incoming offer** with `sponsorship_pricer__evaluate_offer`: it derives
       the offer's implied CPM and effective hourly rate, compares against the rate-card
       value, flags red-line terms (perpetual usage, > 3 months exclusivity, net-60+, unlimited
       revisions, no kill fee) and proposes a counter number. Present the gap in the brand's
       language: CPM and reach, not "I feel undervalued".
    4. **Package** multi-deliverable or ongoing deals with `sponsorship_pricer__bundle_quote`.
       It prices the bundle, caps the discount at 15%, computes a monthly retainer, and lays
       out the payment schedule (50% on signature, 50% on delivery; or net-30 with a late fee).
       Bundles are how you give a brand a lower number without lowering your rate.
    5. **Write the reply** (email-ready): thank, restate deliverables precisely, give the
       number with 2-3 justification lines (median reach, engagement vs platform norm, usage
       term), the terms, and one alternative package. If Gmail is connected, create a draft.
    6. **Self-check:** every deliverable has a defined format, length, posting window and
       revision count; usage and exclusivity have durations and prices; payment terms are
       stated; the quote is ≥ the hourly floor.

    ## Frameworks
    - **Price on reach, not followers:** rate ≈ (median views ÷ 1,000) × CPM × multipliers.
      The CPM ranges in the tool are commonly quoted creator-market starting points — replace
      them with the creator's closed-deal CPMs as soon as three deals exist.
    - **Multipliers:** engagement above ~5% (by views) +20%; below 1% −20%. Niches with
      high-value audiences (finance, B2B software, health professionals) 1.3-1.5×; broad
      entertainment 0.8-1×.
    - **Usage rights** (brand runs the content as its own ads): +30% for 30 days, +50% for
      90 days, +75% for 6 months, +100% for 12 months; perpetual = 12-month price × 2 or
      refuse. **Whitelisting / Spark Ads** (paid media from the creator's handle): +30-50%
      per 30 days. **Exclusivity** (no competitor deals): +15% per month of category
      lock-out, capped at 6 months; total exclusivity ("no other brands") is 2-3× that.
    - **Floors:** never below production hours × the creator's hourly value; never below the
      low CPM on median views. Rush (< 7 days) +25%.
    - **Terms:** 50% upfront for new brands; net-30 max; one round of revisions on script,
      one on cut; kill fee 50% after script approval; the creator keeps approval of final
      copy and the disclosure (#ad / paid partnership label) is non-negotiable.
    - **Negotiation:** anchor with the mid quote and a reason; when they push, trade scope
      (shorter usage, fewer revisions, one fewer deliverable) before price; if you must move
      on price, get something back (testimonial, longer term, faster payment).

    ## Output format
    ```
    # Sponsorship pricing — <creator/platform> · <date>
    **Media kit numbers:** median views N (mean N) · ER by views N% · ER by followers N% · views/follower N.N

    ## Rate card
    | Deliverable | Base (median views × CPM) | Multipliers | Quote (low / mid / high) |
    |---|---|---|---|
    Usage: +N% per term · Exclusivity: +N%/month · Whitelisting: +N%/30 days · Rush +25%

    ## Offer evaluation (if any)
    Offer $N → implied CPM $N, $N/hour · Rate card mid $N · Gap N% · Red flags: …
    **Counter:** $N with <terms>; fallback $N with <reduced scope>

    ## Reply draft
    Subject: …
    <5-8 lines: thanks, deliverables, number + why, terms, alternative package, next step>
    ```

    ## Anti-patterns
    - Quoting from follower count ("$100 per 10k followers"). Reach is what brands buy.
    - Using average views inflated by one viral hit. Median, always.
    - Giving away usage rights or exclusivity "as part of the package". They are separate line items.
    - Saying a number without a reason. Every quote gets two justification lines.
    - Accepting net-60/90 with no deposit from a brand you have never worked with.
    - Discounting instead of bundling. A 20% discount is a 20% pay cut on every future deal.
    """,
)

# Commonly quoted creator-market CPM starting points (USD per 1,000 views), low / mid / high.
# These are defaults to be overridden by the creator's own closed deals.
CPM_TABLE: dict[str, dict[str, tuple[float, float, float]]] = {
    "youtube": {"integration": (20, 30, 40), "dedicated": (40, 55, 75), "short": (10, 15, 20), "mention": (10, 15, 20)},
    "youtube_shorts": {"short": (10, 15, 20), "integration": (10, 15, 20), "dedicated": (15, 20, 30), "mention": (5, 8, 12)},
    "instagram": {"reel": (12, 18, 25), "post": (10, 15, 20), "story": (6, 10, 15), "carousel": (10, 15, 20), "integration": (12, 18, 25), "dedicated": (15, 22, 30), "mention": (6, 10, 15)},
    "tiktok": {"video": (12, 18, 25), "dedicated": (15, 22, 30), "integration": (12, 18, 25), "mention": (6, 10, 15)},
    "podcast": {"pre_roll": (15, 20, 25), "mid_roll": (22, 28, 35), "post_roll": (10, 15, 20), "dedicated": (30, 40, 55), "integration": (22, 28, 35), "mention": (10, 15, 20)},
    "newsletter": {"primary": (30, 45, 60), "secondary": (15, 25, 35), "dedicated": (50, 75, 100), "integration": (30, 45, 60), "mention": (15, 25, 35)},
    "x": {"post": (5, 8, 12), "thread": (8, 12, 18), "integration": (8, 12, 18), "dedicated": (10, 15, 20), "mention": (4, 6, 10)},
    "linkedin": {"post": (18, 28, 40), "integration": (18, 28, 40), "dedicated": (25, 35, 50), "mention": (10, 15, 22)},
    "twitch": {"stream_integration": (8, 12, 18), "integration": (8, 12, 18), "dedicated": (15, 20, 30), "mention": (5, 8, 12)},
    "blog": {"sponsored_post": (20, 30, 45), "integration": (20, 30, 45), "dedicated": (30, 45, 60), "mention": (10, 15, 20)},
}
_ALIASES = {"ig": "instagram", "reels": "instagram", "yt": "youtube", "shorts": "youtube_shorts", "twitter": "x", "substack": "newsletter", "email": "newsletter", "beehiiv": "newsletter"}
NICHE_MULT = {"general": 1.0, "lifestyle": 1.0, "entertainment": 0.85, "gaming": 0.85, "beauty": 1.1, "fitness": 1.1, "parenting": 1.1, "food": 1.0, "travel": 1.0, "tech": 1.25, "finance": 1.5, "b2b": 1.5, "software": 1.4, "health_professional": 1.4, "education": 1.1, "luxury": 1.3}
USAGE_UPLIFT = [(0, 0.0), (30, 0.30), (90, 0.50), (180, 0.75), (365, 1.00)]


def _platform(p: str) -> str:
    key = str(p or "").strip().lower().replace(" ", "_").replace("-", "_")
    key = _ALIASES.get(key, key)
    if key not in CPM_TABLE:
        raise ToolError(f"Unknown platform {p!r}. Known: {', '.join(CPM_TABLE)}.")
    return key


def _deliverable(platform: str, d: str) -> str:
    key = str(d or "integration").strip().lower().replace(" ", "_").replace("-", "_")
    table = CPM_TABLE[platform]
    if key in table:
        return key
    raise ToolError(f"Unknown deliverable {d!r} for {platform}. Options: {', '.join(table)}.")


def _usage_uplift(days: int, perpetual: bool) -> float:
    if perpetual:
        return 2.0  # 12-month price × 2, i.e. +200% over base
    up = 0.0
    for threshold, pct_ in USAGE_UPLIFT:
        if days >= threshold:
            up = pct_
    return up


def _price(platform: str, deliverable: str, views: float, engagement_rate_pct: float, niche: str, usage_days: int, perpetual_usage: bool, exclusivity_months: int, whitelisting_days: int, rush: bool, production_hours: float, hourly_floor: float) -> dict:
    lo, mid, hi = CPM_TABLE[platform][deliverable]
    base = {"low": views / 1000 * lo, "mid": views / 1000 * mid, "high": views / 1000 * hi}
    mult, lines = 1.0, []
    nm = NICHE_MULT.get(niche.strip().lower().replace(" ", "_"), None)
    if nm is None:
        nm = 1.0
        lines.append(f"niche '{niche}' not in table → ×1.0 (known: {', '.join(NICHE_MULT)})")
    elif nm != 1.0:
        lines.append(f"niche {niche} ×{nm}")
    mult *= nm
    if engagement_rate_pct >= 5:
        mult *= 1.2
        lines.append(f"engagement {engagement_rate_pct:g}% (≥ 5%) ×1.2")
    elif engagement_rate_pct and engagement_rate_pct < 1:
        mult *= 0.8
        lines.append(f"engagement {engagement_rate_pct:g}% (< 1%) ×0.8")
    usage = _usage_uplift(usage_days, perpetual_usage)
    if usage:
        lines.append(("perpetual usage +200% (or refuse)" if perpetual_usage else f"usage rights {usage_days} days +{usage:.0%}"))
    excl = min(exclusivity_months, 6) * 0.15
    if exclusivity_months:
        lines.append(f"category exclusivity {exclusivity_months} mo +{excl:.0%}" + (" (capped at 6 months)" if exclusivity_months > 6 else ""))
    wl = 0.0
    if whitelisting_days:
        wl = 0.4 * max(1, -(-whitelisting_days // 30))
        lines.append(f"whitelisting {whitelisting_days} days +{wl:.0%}")
    rush_up = 0.25 if rush else 0.0
    if rush:
        lines.append("rush (< 7 days) +25%")
    adders = 1 + usage + excl + wl + rush_up
    quote = {k: v * mult * adders for k, v in base.items()}
    floor = production_hours * hourly_floor if production_hours and hourly_floor else 0.0
    floor_applied = False
    if floor and quote["low"] < floor:
        floor_applied = True
        lines.append(f"production floor {production_hours:g} h × {hourly_floor:g}/h = {floor:.0f} raises the low quote")
        quote["low"] = floor
        quote["mid"] = max(quote["mid"], floor * 1.15)
        quote["high"] = max(quote["high"], floor * 1.4)
    return {
        "platform": platform,
        "deliverable": deliverable,
        "views_basis": views,
        "cpm_low_mid_high": [lo, mid, hi],
        "base_low_mid_high": [money(base["low"]), money(base["mid"]), money(base["high"])],
        "audience_multiplier": round(mult, 2),
        "term_adders_pct": round(100 * (adders - 1)),
        "quote_low": money(quote["low"]),
        "quote_mid": money(quote["mid"]),
        "quote_high": money(quote["high"]),
        "effective_cpm_mid": money(quote["mid"] / views * 1000) if views else None,
        "production_floor": money(floor) if floor else None,
        "floor_applied": floor_applied,
        "reasoning": lines,
    }


@AGENT.tool
def rate_card(
    platform: str,
    median_views: float,
    deliverable: str = "integration",
    engagement_rate_pct: float = 0,
    niche: str = "general",
    usage_days: int = 0,
    perpetual_usage: bool = False,
    exclusivity_months: int = 0,
    whitelisting_days: int = 0,
    rush: bool = False,
    production_hours: float = 0,
    hourly_floor: float = 0,
    cpm_override: float = 0,
) -> dict:
    """Price one sponsored deliverable from median views × CPM with niche, engagement, usage, exclusivity, whitelisting and rush uplifts.

    Returns low/mid/high quotes, the effective CPM, and each multiplier as a reasoning line
    to paste into the brand reply. Default CPMs are market starting points; pass cpm_override
    once you have your own closed-deal CPM.

    Args:
        platform: youtube, youtube_shorts, instagram, tiktok, podcast, newsletter, x, linkedin, twitch or blog.
        median_views: Median views (or downloads/opens) per post over the last 10-20 posts — not followers.
        deliverable: e.g. integration, dedicated, short, reel, story, post, mid_roll, primary (newsletter), thread.
        engagement_rate_pct: Engagement rate by views in percent (0 = unknown, no adjustment).
        niche: Audience niche (finance, b2b, tech, fitness, beauty, gaming, entertainment, general…).
        usage_days: Days the brand may run the content as its own ads (0 = organic only).
        perpetual_usage: Brand wants unlimited/perpetual usage rights.
        exclusivity_months: Months of category exclusivity requested.
        whitelisting_days: Days of whitelisting / Spark Ads from the creator's handle.
        rush: Delivery required in under 7 days.
        production_hours: Hours to produce the deliverable (for the hourly floor).
        hourly_floor: The creator's minimum hourly value (for the floor).
        cpm_override: Use this mid CPM instead of the table (low = 0.75×, high = 1.35×).
    """
    p = _platform(platform)
    d = _deliverable(p, deliverable)
    if median_views <= 0 or median_views > 500_000_000:
        raise ToolError("median_views must be > 0 (use real view counts, not followers)")
    if engagement_rate_pct < 0 or engagement_rate_pct > 100:
        raise ToolError("engagement_rate_pct must be 0-100")
    if usage_days < 0 or exclusivity_months < 0 or whitelisting_days < 0 or production_hours < 0 or hourly_floor < 0 or cpm_override < 0:
        raise ToolError("Days, months, hours and rates cannot be negative")
    if cpm_override:
        CPM_TABLE[p][d]  # validate
        saved = CPM_TABLE[p][d]
        CPM_TABLE[p][d] = (cpm_override * 0.75, cpm_override, cpm_override * 1.35)
        try:
            out = _price(p, d, median_views, engagement_rate_pct, niche, usage_days, perpetual_usage, exclusivity_months, whitelisting_days, rush, production_hours, hourly_floor)
        finally:
            CPM_TABLE[p][d] = saved
        out["cpm_source"] = "creator override"
    else:
        out = _price(p, d, median_views, engagement_rate_pct, niche, usage_days, perpetual_usage, exclusivity_months, whitelisting_days, rush, production_hours, hourly_floor)
        out["cpm_source"] = "market starting point — replace with closed-deal CPMs"
    out["verdict"] = f"Quote {out['quote_mid']:,.0f} (walk-away {out['quote_low']:,.0f}, stretch {out['quote_high']:,.0f}) for a {p} {d} on {median_views:,.0f} median views; effective CPM {out['effective_cpm_mid']:.0f}."
    return out


@AGENT.tool
def media_kit_numbers(views: list[float], followers: int = 0, likes: float = 0, comments: float = 0, shares: float = 0, saves: float = 0, previous_followers: int = 0, period_days: int = 30) -> dict:
    """Compute the honest media-kit statistics brands check: median vs mean views, spread, engagement by views and by followers, growth.

    Args:
        views: View counts of the last 10-20 posts (most recent first or any order).
        followers: Current follower/subscriber count (0 = skip follower-based metrics).
        likes: Total likes across those posts.
        comments: Total comments across those posts.
        shares: Total shares/reposts across those posts.
        saves: Total saves/bookmarks across those posts.
        previous_followers: Follower count period_days ago, for growth rate (0 = skip).
        period_days: Days between previous_followers and followers (default 30).
    """
    if not views or len(views) > 1000:
        raise ToolError("Give 1-1000 view counts")
    vals = []
    for v in views:
        if not isinstance(v, (int, float)) or v < 0:
            raise ToolError("views must be non-negative numbers")
        vals.append(float(v))
    if followers < 0 or previous_followers < 0 or period_days <= 0 or min(likes, comments, shares, saves) < 0:
        raise ToolError("followers, interactions and period_days must be non-negative (period_days > 0)")
    n = len(vals)
    median = statistics.median(vals)
    mean = statistics.fmean(vals)
    s = sorted(vals)
    p25 = s[int(0.25 * (n - 1))]
    p75 = s[int(0.75 * (n - 1))]
    cv = round(statistics.pstdev(vals) / mean, 2) if mean else 0.0
    total_views = sum(vals)
    interactions = likes + comments + shares + saves
    er_views = pct(interactions, total_views) if total_views else 0.0
    er_followers = pct(interactions / n, followers) if followers else None
    v2f = round(median / followers, 2) if followers else None
    growth = pct(followers - previous_followers, previous_followers) if previous_followers else None
    notes = []
    if mean > 1.3 * median:
        notes.append(f"Mean ({mean:,.0f}) is {mean / median:.1f}× the median ({median:,.0f}) — a few outliers inflate it. Put the median in the kit; brands recompute it.")
    if cv > 0.8:
        notes.append("High view variance (CV > 0.8): quote on the median and offer a view guarantee only at the 25th percentile.")
    if v2f is not None and v2f < 0.1:
        notes.append("Median views under 10% of followers — the follower number will hurt more than help; lead with views and engagement.")
    if er_followers is not None and er_followers >= 3:
        notes.append(f"Engagement by followers {er_followers}% is strong for most platforms; feature it.")
    if n < 10:
        notes.append(f"Only {n} posts — use 10-20 for a stable median.")
    return {
        "posts": n,
        "median_views": round(median),
        "mean_views": round(mean),
        "p25_views": round(p25),
        "p75_views": round(p75),
        "min_views": round(s[0]),
        "max_views": round(s[-1]),
        "coefficient_of_variation": cv,
        "total_interactions": interactions,
        "engagement_rate_by_views_pct": er_views,
        "engagement_rate_by_followers_pct": er_followers,
        "views_per_follower": v2f,
        "follower_growth_pct": growth,
        "growth_period_days": period_days if growth is not None else None,
        "media_kit_line": f"Median {median:,.0f} views/post (n={n}) · {er_views}% engagement by views" + (f" · {er_followers}% by followers" if er_followers is not None else "") + (f" · +{growth}% followers/{period_days}d" if growth is not None and growth > 0 else ""),
        "notes": notes,
        "summary": f"Use median {median:,.0f} views (not mean {mean:,.0f}); ER by views {er_views}%." + (" " + notes[0] if notes else ""),
    }


@AGENT.tool
def evaluate_offer(
    offer_amount: float,
    platform: str,
    median_views: float,
    deliverables: int = 1,
    deliverable: str = "integration",
    production_hours: float = 0,
    hourly_floor: float = 0,
    usage_days: int = 0,
    perpetual_usage: bool = False,
    exclusivity_months: int = 0,
    whitelisting_days: int = 0,
    payment_terms_days: int = 30,
    deposit_pct: float = 0,
    revision_rounds: int = 1,
    kill_fee: bool = True,
    engagement_rate_pct: float = 0,
    niche: str = "general",
) -> dict:
    """Judge a brand's offer: implied CPM, effective hourly rate, gap vs the rate card, red-flag terms, and a counter number.

    Args:
        offer_amount: Total fee offered for all deliverables.
        platform: Platform of the deliverables (youtube, instagram, tiktok, podcast, newsletter, x, linkedin, twitch, blog).
        median_views: Median views per post on that platform.
        deliverables: Number of posts/videos included (default 1).
        deliverable: Deliverable type used for the rate-card comparison (default integration).
        production_hours: Total hours to produce everything (for the hourly rate).
        hourly_floor: Creator's minimum hourly value.
        usage_days: Usage rights requested in days.
        perpetual_usage: Brand asks for perpetual/unlimited usage.
        exclusivity_months: Category exclusivity requested in months.
        whitelisting_days: Whitelisting / Spark Ads days requested.
        payment_terms_days: Net payment terms in days (default 30).
        deposit_pct: Deposit paid upfront in percent (0 = none).
        revision_rounds: Revision rounds the brand expects (default 1).
        kill_fee: Whether the contract includes a kill fee after script approval.
        engagement_rate_pct: Engagement rate by views, percent (0 = unknown).
        niche: Audience niche for the rate-card multiplier.
    """
    if offer_amount < 0:
        raise ToolError("offer_amount cannot be negative")
    if deliverables < 1 or deliverables > 100:
        raise ToolError("deliverables must be 1-100")
    p = _platform(platform)
    d = _deliverable(p, deliverable)
    if median_views <= 0:
        raise ToolError("median_views must be > 0")
    if payment_terms_days < 0 or deposit_pct < 0 or deposit_pct > 100 or revision_rounds < 0:
        raise ToolError("payment_terms_days, deposit_pct (0-100) and revision_rounds must be valid")
    card = _price(p, d, median_views, engagement_rate_pct, niche, usage_days, perpetual_usage, exclusivity_months, whitelisting_days, False, production_hours / deliverables if production_hours else 0, hourly_floor)
    card_mid = card["quote_mid"] * deliverables
    card_low = card["quote_low"] * deliverables
    expected_views = median_views * deliverables
    implied_cpm = offer_amount / expected_views * 1000
    hourly = offer_amount / production_hours if production_hours else None
    gap_pct = round(100 * (offer_amount - card_mid) / card_mid, 1) if card_mid else 0.0
    red, amber = [], []
    if perpetual_usage:
        red.append("Perpetual usage rights — price at 2× the 12-month rate or strike it; offer 90 days instead.")
    elif usage_days > 365:
        red.append(f"Usage {usage_days} days (> 12 months) — cap at 12 months.")
    if exclusivity_months > 3:
        red.append(f"{exclusivity_months} months category exclusivity — cap at 3 unless paid per month (+15%/month).")
    if payment_terms_days > 45:
        red.append(f"Net-{payment_terms_days} payment — counter with net-30 and a {'50%' if not deposit_pct else f'{deposit_pct:g}%'} deposit.")
    if not deposit_pct and offer_amount >= 1000:
        amber.append("No deposit on a four-figure deal — ask for 50% on signature.")
    if revision_rounds > 2:
        red.append(f"{revision_rounds} revision rounds — cap at 1 on script + 1 on cut; extra rounds billed.")
    if not kill_fee:
        amber.append("No kill fee — add 50% after script approval, 100% after delivery.")
    if hourly is not None and hourly_floor and hourly < hourly_floor:
        red.append(f"Effective rate {hourly:,.0f}/h is under your {hourly_floor:g}/h floor.")
    if whitelisting_days and not any("whitelist" in r for r in card["reasoning"]):
        amber.append("Whitelisting requested — confirm it is priced separately.")
    if offer_amount < card_low:
        verdict_word = "Underpriced"
    elif offer_amount < card_mid:
        verdict_word = "Below your mid quote"
    else:
        verdict_word = "At or above rate card"
    counter = max(card_mid, offer_amount * 1.15) if offer_amount < card_mid else offer_amount
    counter = money(round(counter / 25) * 25)
    fallback = money(round(max(card_low, offer_amount) / 25) * 25)
    return {
        "offer": money(offer_amount),
        "deliverables": deliverables,
        "expected_views": round(expected_views),
        "implied_cpm": money(implied_cpm),
        "effective_hourly": money(hourly) if hourly is not None else None,
        "rate_card_low": money(card_low),
        "rate_card_mid": money(card_mid),
        "rate_card_high": money(card["quote_high"] * deliverables),
        "gap_vs_mid_pct": gap_pct,
        "red_flags": red,
        "amber_flags": amber,
        "counter": counter,
        "fallback_with_reduced_scope": fallback,
        "counter_script": (
            f"Thanks — for {deliverables} × {d} on {p} at a median {median_views:,.0f} views each, my rate is {counter:,.0f} "
            f"(≈ {counter / expected_views * 1000:.0f} CPM){', including ' + str(usage_days) + ' days usage' if usage_days else ''}"
            f"{', ' + str(exclusivity_months) + ' months exclusivity' if exclusivity_months else ''}. "
            f"If budget is fixed at {offer_amount:,.0f}, I can do it at {fallback:,.0f} with organic-only posting and one revision round."
        ),
        "rate_card_reasoning": card["reasoning"],
        "verdict": f"{verdict_word}: {offer_amount:,.0f} is {gap_pct:+.0f}% vs the {card_mid:,.0f} mid quote (implied CPM {implied_cpm:.0f}). {len(red)} red flag(s), {len(amber)} amber." + (" Counter at " + f"{counter:,.0f}." if counter > offer_amount else " Accept, fix the terms."),
    }


@AGENT.tool
def bundle_quote(items: list[dict], bundle_discount_pct: float = 10, months: int = 1, deposit_pct: float = 50, net_days: int = 30, late_fee_pct_per_month: float = 1.5) -> dict:
    """Price a multi-deliverable package or retainer: line totals, capped bundle discount, monthly figure and payment schedule.

    Args:
        items: Lines like {"deliverable": "YouTube integration", "rate": 1800, "quantity": 2}.
        bundle_discount_pct: Discount for the bundle, percent; anything over 15 is flagged and capped (default 10).
        months: Retainer length in months (1 = one-off package).
        deposit_pct: Percent due on signature (default 50).
        net_days: Days to pay the balance after delivery/invoice (default 30).
        late_fee_pct_per_month: Late fee per month on overdue balances (default 1.5).
    """
    if not items or len(items) > 50:
        raise ToolError("Give 1-50 line items")
    if bundle_discount_pct < 0 or bundle_discount_pct > 100:
        raise ToolError("bundle_discount_pct must be 0-100")
    if months < 1 or months > 24:
        raise ToolError("months must be 1-24")
    if not 0 <= deposit_pct <= 100 or net_days < 0 or late_fee_pct_per_month < 0:
        raise ToolError("deposit_pct 0-100, net_days ≥ 0, late fee ≥ 0")
    lines, subtotal = [], 0.0
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict) or not it.get("deliverable"):
            raise ToolError(f"line #{i} needs a 'deliverable'")
        try:
            rate = float(it.get("rate", 0))
            qty = float(it.get("quantity", 1))
        except (TypeError, ValueError):
            raise ToolError(f"{it['deliverable']}: rate and quantity must be numbers") from None
        if rate < 0 or qty <= 0:
            raise ToolError(f"{it['deliverable']}: rate ≥ 0 and quantity > 0")
        total = rate * qty
        subtotal += total
        lines.append({"deliverable": str(it["deliverable"]), "rate": money(rate), "quantity": qty, "line_total": money(total)})
    flags = []
    disc = bundle_discount_pct
    if disc > 15:
        flags.append(f"{disc:g}% bundle discount exceeds the 15% cap — capped. Give scope, not price.")
        disc = 15.0
    discount = subtotal * disc / 100
    per_period = subtotal - discount
    contract_total = per_period * months
    deposit = contract_total * deposit_pct / 100 if months == 1 else per_period * deposit_pct / 100
    schedule = []
    if months == 1:
        schedule.append({"milestone": "On signature", "amount": money(deposit)})
        schedule.append({"milestone": f"On delivery, net-{net_days}", "amount": money(contract_total - deposit)})
    else:
        schedule.append({"milestone": "Month 1 deposit on signature", "amount": money(deposit)})
        schedule.append({"milestone": f"Month 1 balance, net-{net_days} after delivery", "amount": money(per_period - deposit)})
        for m in range(2, months + 1):
            schedule.append({"milestone": f"Month {m}, invoiced on the 1st, net-{net_days}", "amount": money(per_period)})
    if months >= 3 and disc < 10:
        flags.append("Retainers of 3+ months usually carry a 10-15% rate in exchange for commitment — consider it; ask for a 30-day cancellation clause in return.")
    value_stack = [f"{ln['quantity']:g} × {ln['deliverable']} @ {ln['rate']:,.0f}" for ln in lines]
    return {
        "lines": lines,
        "list_price": money(subtotal),
        "bundle_discount_pct": disc,
        "discount": money(discount),
        "package_price": money(per_period),
        "months": months,
        "contract_total": money(contract_total),
        "monthly": money(per_period) if months > 1 else None,
        "payment_schedule": schedule,
        "terms": f"{deposit_pct:g}% deposit on signature; balance net-{net_days}; {late_fee_pct_per_month:g}%/month late fee; 1 script + 1 cut revision; kill fee 50% after script approval; #ad disclosure non-negotiable.",
        "value_stack": value_stack,
        "flags": flags,
        "verdict": f"Package {per_period:,.0f}" + (f"/month × {months} = {contract_total:,.0f}" if months > 1 else "") + f" (list {subtotal:,.0f}, {disc:g}% bundle); {deposit:,.0f} due on signature.",
    }
