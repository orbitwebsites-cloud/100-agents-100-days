"""Email Flows — abandoned-cart, welcome, post-purchase and win-back automations timed from your own purchase cycle."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from ...core import Agent, ToolError
from ...lib import text
from ._common import mean, median, money, pct, percentile, require_positive

AGENT = Agent(
    slug="email-flows",
    name="Email Flows",
    category="ecommerce",
    tagline="Build the five revenue flows every store needs, timed to your purchase cycle, with copy that clears the spam filter.",
    description=(
        "Designs and audits the lifecycle email automations that make 25-40% of a healthy DTC brand's email "
        "revenue: abandoned cart/checkout, browse abandonment, welcome, post-purchase and win-back. Computes "
        "exact send timestamps around quiet hours, derives win-back and replenishment timing from real "
        "inter-order gaps instead of guesses, lints subject lines for length and spam triggers, diagnoses "
        "underperforming flows step by step against benchmarks, and sizes the revenue each flow should produce."
    ),
    triggers=[
        "set up an abandoned cart email flow",
        "write a welcome series / welcome email sequence",
        "when should win-back emails go out",
        "audit my Klaviyo flows / why is my abandoned cart flow underperforming",
        "post-purchase email sequence",
        "email subject lines for my flow",
        "how much revenue should my flows make",
    ],
    examples=[
        "Set up a 3-email abandoned checkout flow for a skincare brand; carts are worth ~$62 and our margin is 55%.",
        "Here are order histories for 300 customers — when should our win-back and replenishment emails trigger?",
        "Our abandoned cart flow: 4,100 sent, 1,650 opens, 210 clicks, 61 orders, 22 unsubs. What's broken?",
    ],
    connectors=["Klaviyo", "Shopify", "Mailchimp", "HubSpot", "Google Sheets"],
    playbook="""
    ## Standard
    You are a retention marketer who has built flows for eight-figure DTC brands. The one
    metric that matters is **revenue per recipient (RPR)** per flow — sends are free, attention
    is not. Excellent output is a complete flow spec a Klaviyo/Mailchimp operator can build
    in an hour: trigger, filters, exact delays and send windows, per-email goal, subject line
    + preview text, body outline, and the exit/suppression rules. Timing comes from data
    (the store's purchase cycle), never from generic "day 30/60/90" advice.

    ## Intake
    You need: which flow(s), the product category and price point, margin (decides whether
    an incentive is allowed), and — for win-back/replenishment — order histories or the
    average time between orders. Ask at most 3 questions only if you cannot proceed; otherwise
    assume and state (e.g. "assuming 45% margin, so no discount in email 1 or 2").

    ## Procedure
    1. **Derive the purchase cycle** when you have order histories: call
       `email_flows__purchase_cycle`. It returns median/p75 inter-order days, the repeat
       rate, and the exact day offsets for replenishment (before they run out), win-back
       (when they are overdue) and sunset. Without histories, use the category default and
       say so (consumables 30-45 days, apparel 60-90, durables 180+).
    2. **Schedule every email** with `email_flows__flow_schedule`: pass the flow type, the
       trigger time and the customer's timezone offset. It applies the proven delays,
       moves sends out of quiet hours, snaps non-urgent emails to the preferred send hour,
       and returns exact timestamps plus the goal of each email. Never hand-compute delays.
    3. **Write each email** to its goal (Frameworks). One idea per email, one CTA, plain-text
       feel for abandoned cart email 1, brand-designed for welcome. Draft 3 subject lines
       per email and run `email_flows__subject_line_check` on all of them; keep the winner
       and one variant for an A/B split.
    4. **Size the flow** with `email_flows__flow_revenue_model` (monthly triggers, AOV,
       current conversion if any) so the user knows the revenue at stake and the gap to
       benchmark.
    5. **Audit an existing flow** with `email_flows__flow_diagnostics`: give it sends, opens,
       clicks, orders, revenue, unsubscribes and spam complaints per flow. It finds the
       weakest step (deliverability, open, click-through, conversion, list health) and you
       fix that step first. Do not redesign a flow whose only problem is the offer.
    6. **Specify exits and filters**: exit on purchase; skip abandoned-cart if the customer
       ordered in the last 7 days; suppress win-back for customers in an active cart flow;
       exclude unengaged 180+ day profiles from anything but sunset.
    7. **Self-check**: every email has a goal, a subject ≤ 45 chars, a single CTA, an exit
       rule; incentives appear only where margin allows and never in email 1.

    ## Frameworks
    - **Abandoned checkout (3 emails: 1h / 24h / 72h):** 1 = reminder with cart contents,
      no offer, plain text; 2 = objections (shipping, returns, reviews, UGC); 3 = last call,
      scarcity or a small incentive if margin ≥ 50%. Browse abandonment: 2 emails (2h / 24h).
    - **Welcome (5 emails over 14 days):** 0h deliver the promised offer + brand promise;
      48h founder story/why; 96h best sellers with social proof; day 7 objection handling
      + offer reminder; day 14 last chance / content. New-subscriber offer expiry = 7-10 days.
    - **Post-purchase:** 30min thank-you (not the receipt); day 3 how-to/what to expect;
      delivered + 3 days review/UGC request; day 21 cross-sell; replenishment at 0.8× cycle.
    - **Win-back:** trigger at the p75 inter-order gap (≈ 1.5× median), three touches at
      1.0×, 1.3× and 2.0× of that offset; escalate incentive per touch; sunset at ~3× median
      with a "still want to hear from us?" then suppress. Suppressing the unengaged
      protects deliverability, which is worth more than the last 0.2% who might convert.
    - **Subject lines:** ≤ 45 characters (mobile truncation ~35-45), no spam trigger words
      ("free", "guaranteed", "act now", "$$$"), ≤ 1 emoji, no ALL CAPS words, personalise
      only when the data is reliable. Preview text 40-90 chars, never "View in browser".
    - **Health thresholds:** unsubscribe rate > 0.5% per send or spam complaint rate > 0.1%
      is a list-quality/frequency problem (Gmail and Yahoo enforce < 0.3% spam rate).
    - **Benchmarks for automated flows (typical, verify in your account):** open 35-50%,
      click 3-8%, click-to-open ≥ 10%; placed-order rate: abandoned cart 3-5%, welcome
      1.5-3%, browse 1-2%, post-purchase 1-2%, win-back 0.5-1.5%.

    ## Output format
    ```
    # <Flow name> — trigger: <event> · exit: purchased · filters: <…>
    | # | Send (local) | Delay | Goal | Subject (≤45) | Preview | CTA |
    ## Email 1 — <goal>
    Subject: … / Preview: …
    <body outline: hook, proof, CTA — 60-120 words>
    ## Email 2 … (repeat)
    ## Revenue at stake
    <triggers/mo × placed-order rate × AOV = $/mo; gap to benchmark>
    ## Build checklist
    - [ ] trigger + filters · [ ] delays as above · [ ] quiet hours · [ ] A/B subject on email 1
    ```

    ## Anti-patterns
    - Leading with a discount in abandoned-cart email 1 — trains customers to abandon.
    - Day 30/60/90 win-back for a product people rebuy every 3 weeks (or every year).
    - Five links and three CTAs per email. One job per email.
    - Emailing unengaged 180-day profiles to "get them back" and torching deliverability.
    - Judging flows by open rate (inflated by Apple Mail Privacy Protection). Use clicks,
      placed-order rate and RPR.
    - Copy that starts with "We noticed you left something in your cart."
    """,
)

# (delay_hours, goal, incentive_allowed) per flow. Delays that depend on the purchase cycle use "C" multipliers.
FLOWS: dict[str, dict] = {
    "abandoned_checkout": {"steps": [(1, "reminder: cart contents, plain text, no offer", False), (24, "handle objections: shipping/returns/reviews/UGC", False), (72, "last call: scarcity or small incentive if margin allows", True)], "trigger": "checkout started, no order"},
    "abandoned_cart": {"steps": [(2, "reminder: cart contents, plain text, no offer", False), (24, "handle objections: shipping/returns/reviews/UGC", False), (72, "last call: scarcity or small incentive if margin allows", True)], "trigger": "added to cart, no checkout"},
    "browse_abandonment": {"steps": [(2, "product viewed + 3 related, soft tone", False), (24, "social proof for the category, one CTA", False)], "trigger": "viewed product, no add to cart"},
    "welcome": {"steps": [(0, "deliver the promised offer + brand promise", True), (48, "founder story / why we exist", False), (96, "best sellers with reviews", False), (168, "objection handling + offer reminder", True), (336, "last chance / educational content", True)], "trigger": "subscribed to list"},
    "post_purchase": {"steps": [(0.5, "thank you (not the receipt): what happens next", False), (72, "how to use / what to expect", False), ("delivered+72", "review / UGC request", False), (504, "cross-sell based on what they bought", False), ("C*0.8", "replenishment reminder", False)], "trigger": "placed order"},
    "win_back": {"steps": [("W*1.0", "we miss you: what's new, no offer", False), ("W*1.3", "best of what they bought before + offer", True), ("W*2.0", "last chance offer, then sunset", True)], "trigger": "no order for the win-back offset"},
    "replenishment": {"steps": [("C*0.8", "running low? reorder in one click", False), ("C*1.0", "reorder reminder + subscribe & save", True), ("C*1.2", "you're probably out — offer", True)], "trigger": "order of a consumable"},
    "sunset": {"steps": [("S*1.0", "still want to hear from us? (re-permission)", False), ("S+168", "final: we'll stop emailing you", False)], "trigger": "no opens/clicks for the sunset offset"},
}


def _resolve_hours(spec, cycle_days: float, delivery_days: float) -> float:
    if isinstance(spec, (int, float)):
        return float(spec)
    winback_offset = cycle_days * 1.5
    sunset_offset = cycle_days * 3.0
    m = re.match(r"^(C|W|S)([*+])([\d.]+)$", spec)
    if m:
        base = {"C": cycle_days, "W": winback_offset, "S": sunset_offset}[m.group(1)] * 24
        val = float(m.group(3))
        return base * val if m.group(2) == "*" else base + val
    if spec.startswith("delivered+"):
        return delivery_days * 24 + float(spec.split("+")[1])
    raise ToolError(f"bad delay spec {spec!r}")


@AGENT.tool
def flow_schedule(
    flow: str,
    trigger_at: str,
    quiet_start_hour: int = 21,
    quiet_end_hour: int = 8,
    preferred_send_hour: int = 10,
    cycle_days: float = 60.0,
    delivery_days: float = 5.0,
) -> dict:
    """Produce exact send timestamps for a lifecycle flow from its trigger time, respecting quiet hours and the store's purchase cycle.

    Args:
        flow: One of abandoned_checkout, abandoned_cart, browse_abandonment, welcome, post_purchase, win_back, replenishment, sunset.
        trigger_at: When the trigger event happened, in the customer's local time, e.g. "2026-10-03T22:15".
        quiet_start_hour: Local hour after which nothing non-urgent is sent (21 = 9pm).
        quiet_end_hour: Local hour from which sending resumes (8 = 8am).
        preferred_send_hour: Hour to send day-scale emails at when the natural time falls in quiet hours (10 = 10am).
        cycle_days: Median days between orders (from purchase_cycle); drives win-back, replenishment and sunset offsets.
        delivery_days: Typical days from order to delivery; drives the review-request timing in post_purchase.
    """
    if flow not in FLOWS:
        raise ToolError(f"Unknown flow {flow!r}. Choose from: {', '.join(FLOWS)}.")
    try:
        t0 = datetime.fromisoformat(trigger_at.strip())
    except ValueError:
        raise ToolError(f"trigger_at must be ISO like 2026-10-03T22:15, got {trigger_at!r}") from None
    for name, h in (("quiet_start_hour", quiet_start_hour), ("quiet_end_hour", quiet_end_hour), ("preferred_send_hour", preferred_send_hour)):
        if not 0 <= h <= 23:
            raise ToolError(f"{name} must be 0-23.")
    require_positive("cycle_days", cycle_days)
    require_positive("delivery_days", delivery_days, allow_zero=True)

    def in_quiet(dt: datetime) -> bool:
        h = dt.hour
        return (h >= quiet_start_hour or h < quiet_end_hour) if quiet_start_hour > quiet_end_hour else (quiet_end_hour > h >= quiet_start_hour)

    def next_window(dt: datetime) -> datetime:
        d = dt.replace(hour=quiet_end_hour, minute=0, second=0, microsecond=0)
        return d if d > dt else d + timedelta(days=1)

    rows, prev = [], None
    for n, (spec, goal, incentive) in enumerate(FLOWS[flow]["steps"], 1):
        hours = _resolve_hours(spec, cycle_days, delivery_days)
        raw = t0 + timedelta(hours=hours)
        send = raw
        adjust = "none"
        urgent = hours <= 2
        if in_quiet(raw) and urgent:
            adjust = "sent in quiet hours (time-sensitive)"
        elif in_quiet(raw) and hours >= 20:
            # day-scale delays: land on the preferred hour of the next sending day
            snapped = raw.replace(hour=preferred_send_hour, minute=0, second=0, microsecond=0)
            if snapped <= raw or in_quiet(snapped):
                snapped = next_window(raw).replace(hour=max(preferred_send_hour, quiet_end_hour), minute=0)
            send, adjust = snapped, f"quiet hours → {preferred_send_hour:02d}:00 next sending day"
        elif in_quiet(raw):
            send, adjust = next_window(raw), "moved out of quiet hours"
        else:
            adjust = "kept at the customer's active hour"
        if prev and send - prev < timedelta(hours=12) and n > 1 and not urgent:
            send, adjust = prev + timedelta(hours=12), "spaced ≥12h from previous email"
            if in_quiet(send):
                send = next_window(send)
        rows.append(
            {
                "email": n,
                "delay_hours": round(hours, 1),
                "delay_label": f"{hours / 24:.1f} days" if hours >= 24 else f"{hours:g} h",
                "send_at_local": send.strftime("%Y-%m-%d %H:%M (%a)"),
                "goal": goal,
                "incentive_allowed": incentive,
                "adjustment": adjust,
            }
        )
        prev = send
    return {
        "flow": flow,
        "trigger": FLOWS[flow]["trigger"],
        "trigger_at": t0.strftime("%Y-%m-%d %H:%M (%a)"),
        "emails": rows,
        "flow_ends_at": prev.strftime("%Y-%m-%d %H:%M (%a)") if prev else None,
        "exit_rules": ["exit immediately on order placed", "skip if ordered in last 7 days (cart/browse)", "suppress if in another active flow of higher intent", "exclude profiles unengaged 180+ days except sunset"],
        "summary": f"{len(rows)} emails from {rows[0]['send_at_local']} to {rows[-1]['send_at_local']}; quiet hours {quiet_start_hour:02d}:00-{quiet_end_hour:02d}:00 respected for non-urgent sends.",
    }


@AGENT.tool
def purchase_cycle(customers: list[dict], category_default_days: float = 60.0) -> dict:
    """Derive the store's inter-order cycle from order histories and the exact day offsets for replenishment, win-back and sunset emails.

    Args:
        customers: List of {"customer": id, "order_dates": ["YYYY-MM-DD", ...]} (one entry per customer; single-order customers count toward repeat rate).
        category_default_days: Fallback cycle when fewer than 10 repeat gaps exist.
    """
    if not customers:
        raise ToolError("customers is empty.")
    if len(customers) > 20000:
        raise ToolError("Too many customers (20,000 max).")
    gaps: list[float] = []
    repeaters = 0
    for cust in customers:
        raw = cust.get("order_dates") or []
        ds = []
        for v in raw[:200]:
            try:
                ds.append(datetime.fromisoformat(str(v).strip()[:19]).date())
            except ValueError:
                raise ToolError(f"order_dates must be YYYY-MM-DD; got {v!r} for customer {cust.get('customer')!r}") from None
        ds = sorted(set(ds))
        if len(ds) >= 2:
            repeaters += 1
            gaps.extend((b - a).days for a, b in zip(ds, ds[1:]))
    n_cust = len(customers)
    repeat_rate = repeaters / n_cust
    reliable = len(gaps) >= 10
    med = median(gaps) if reliable else category_default_days
    p25 = percentile(gaps, 25) if reliable else med * 0.6
    p75 = percentile(gaps, 75) if reliable else med * 1.5
    return {
        "customers": n_cust,
        "repeat_customers": repeaters,
        "repeat_rate_pct": pct(repeat_rate),
        "gaps_observed": len(gaps),
        "reliable": reliable,
        "median_gap_days": round(med, 1),
        "mean_gap_days": round(mean(gaps), 1) if gaps else None,
        "p25_gap_days": round(p25, 1),
        "p75_gap_days": round(p75, 1),
        "offsets_days": {
            "replenishment_reminder": round(med * 0.8),
            "winback_start": round(p75),
            "winback_touch_2": round(p75 * 1.3),
            "winback_touch_3": round(p75 * 2.0),
            "sunset": round(med * 3),
        },
        "cycle_days_for_flow_schedule": round(med, 1),
        "verdict": (
            f"Median reorder gap {med:.0f} days (p25 {p25:.0f}, p75 {p75:.0f}); repeat rate {100 * repeat_rate:.0f}%. "
            f"Replenish at day {round(med * 0.8)}, win-back from day {round(p75)}, sunset at day {round(med * 3)}."
            + ("" if reliable else f" Fewer than 10 gaps — using the category default of {category_default_days:g} days.")
        ),
    }


SPAM_TRIGGERS = [
    "free", "free!!", "act now", "buy now", "limited time", "guaranteed", "100%", "risk-free", "no obligation",
    "click here", "winner", "congratulations", "cash", "$$$", "earn money", "make money", "urgent", "don't miss",
    "once in a lifetime", "cheap", "clearance", "lowest price", "order now", "last chance", "exclusive deal", "prize",
]
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")


@AGENT.tool
def subject_line_check(subjects: list[str], preview_texts: list[str] | None = None) -> dict:
    """Score subject lines (and optional preview text) for mobile length, spam triggers, caps, punctuation, emoji and personalisation.

    Args:
        subjects: Candidate subject lines (up to 50).
        preview_texts: Optional preview/preheader text aligned by index with subjects ("" for none).
    """
    if not subjects:
        raise ToolError("subjects is empty.")
    if len(subjects) > 50:
        raise ToolError("Max 50 subject lines per call.")
    previews = preview_texts or []
    rows = []
    for i, s in enumerate(subjects):
        s = str(s)
        if len(s) > 500:
            raise ToolError("A subject line over 500 characters is not a subject line.")
        issues, score = [], 100
        n = len(s)
        if n == 0:
            issues.append("empty")
            score = 0
        if n > 60:
            issues.append(f"{n} chars — truncated on every client (≤ 45 mobile-safe, 60 max)")
            score -= 30
        elif n > 45:
            issues.append(f"{n} chars — truncated on mobile (≤ 45)")
            score -= 12
        low = s.lower()
        hits = [w for w in SPAM_TRIGGERS if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low)]
        if hits:
            issues.append(f"spam triggers: {', '.join(hits)}")
            score -= 15 * len(hits)
        caps_words = [w for w in text.words(s) if len(w) >= 3 and w.isupper() and not w.isdigit()]
        if caps_words:
            issues.append(f"ALL CAPS: {', '.join(caps_words[:3])}")
            score -= 10
        if s.count("!") > 1:
            issues.append("multiple exclamation marks")
            score -= 10
        if "!!" in s or "??" in s or "$$" in s:
            issues.append("repeated punctuation")
            score -= 10
        emojis = EMOJI_RE.findall(s)
        if len(emojis) > 1:
            issues.append(f"{len(emojis)} emoji (max 1)")
            score -= 8
        tokens = re.findall(r"\{\{[^}]+\}\}|\{[^}]+\}|\*\|[^|]+\|\*|%%[^%]+%%", s)
        if tokens:
            issues.append(f"personalisation token {tokens[0]} — only if the data is reliable, set a fallback")
        if re.search(r"\bre:|\bfwd:", low):
            issues.append("fake RE:/FWD: — deceptive, hurts trust and deliverability")
            score -= 25
        strengths = []
        if re.search(r"\d", s):
            strengths.append("contains a number")
        if s.rstrip().endswith("?"):
            strengths.append("question")
        if 20 <= n <= 45:
            strengths.append("length ideal")
        row = {"subject": s, "chars": n, "words": len(text.words(s)), "score": max(0, score), "issues": issues, "strengths": strengths}
        if i < len(previews) and str(previews[i]).strip():
            p = str(previews[i])
            pi = []
            if not 40 <= len(p) <= 90:
                pi.append(f"preview {len(p)} chars (aim 40-90)")
            if "view in browser" in p.lower() or "unsubscribe" in p.lower():
                pi.append("preview shows boilerplate — set explicit preview text")
            if p.strip().lower() == s.strip().lower():
                pi.append("preview repeats the subject — use it to add the second hook")
            row["preview"] = p
            row["preview_issues"] = pi
            row["score"] = max(0, row["score"] - 5 * len(pi))
        rows.append(row)
    ranked = sorted(rows, key=lambda r: -r["score"])
    return {
        "results": rows,
        "best": ranked[0]["subject"],
        "ab_pair": [r["subject"] for r in ranked[:2]],
        "summary": f"Best: “{ranked[0]['subject']}” ({ranked[0]['score']}/100). {sum(1 for r in rows if r['issues'])} of {len(rows)} have issues.",
    }


BENCH = {  # placed-order rate (orders / delivered) typical band for automated flows — verify per account
    "abandoned_checkout": (0.03, 0.05), "abandoned_cart": (0.03, 0.05), "browse_abandonment": (0.01, 0.02), "welcome": (0.015, 0.03),
    "post_purchase": (0.01, 0.02), "win_back": (0.005, 0.015), "replenishment": (0.02, 0.04), "sunset": (0.0, 0.005), "other": (0.01, 0.02),
}


@AGENT.tool
def flow_diagnostics(flows: list[dict]) -> dict:
    """Compute every flow's rates (delivery, open, click, CTOR, placed order, RPR, unsub, spam) and name the weakest step to fix first.

    Args:
        flows: List of {"name": str, "type": one of the flow types or "other", "sent": int, "delivered": int (optional), "opens": int, "clicks": int, "orders": int, "revenue": float, "unsubscribes": int, "spam_complaints": int}.
    """
    if not flows:
        raise ToolError("flows is empty.")
    if len(flows) > 100:
        raise ToolError("Max 100 flows per call.")
    out = []
    for f in flows:
        name = str(f.get("name", f.get("type", "flow")))
        ftype = str(f.get("type", "other"))
        if ftype not in BENCH:
            ftype = "other"
        try:
            sent = int(f.get("sent", 0))
            delivered = int(f.get("delivered") or sent)
            opens, clicks, orders = int(f.get("opens", 0)), int(f.get("clicks", 0)), int(f.get("orders", 0))
            revenue = float(f.get("revenue", 0) or 0)
            unsubs, spam = int(f.get("unsubscribes", 0) or 0), int(f.get("spam_complaints", 0) or 0)
        except (TypeError, ValueError):
            raise ToolError(f"{name}: counts must be numbers.") from None
        if sent <= 0:
            raise ToolError(f"{name}: sent must be > 0.")
        if delivered > sent or opens > delivered or clicks > delivered or orders > delivered:
            raise ToolError(f"{name}: counts are inconsistent (delivered ≤ sent; opens, clicks, orders ≤ delivered).")
        dr = delivered / sent
        orate = opens / delivered
        crate = clicks / delivered
        ctor = clicks / opens if opens else 0.0
        por = orders / delivered
        rpr = revenue / delivered
        ur, sr = unsubs / delivered, spam / delivered
        lo, hi = BENCH[ftype]
        problems = []
        if dr < 0.97:
            problems.append(("deliverability", f"delivery {100 * dr:.1f}% < 97% — list hygiene / sender reputation"))
        if sr > 0.001:
            problems.append(("list health", f"spam rate {100 * sr:.2f}% > 0.1% (Gmail/Yahoo limit 0.3%) — cut frequency, suppress unengaged"))
        if ur > 0.005:
            problems.append(("list health", f"unsub rate {100 * ur:.2f}% > 0.5% — expectation mismatch or frequency"))
        if orate < 0.35:
            problems.append(("open", f"open {100 * orate:.1f}% < 35% — subject line / send time / sender name"))
        if ctor < 0.10:
            problems.append(("click-through", f"CTOR {100 * ctor:.1f}% < 10% — content does not pay off the subject; one CTA, clearer offer"))
        if por < lo:
            problems.append(("conversion", f"placed-order {100 * por:.2f}% < {100 * lo:.1f}% band — landing page, offer, timing"))
        weakest = problems[0][0] if problems else None
        out.append(
            {
                "flow": name,
                "type": ftype,
                "delivery_rate_pct": pct(dr, 2),
                "open_rate_pct": pct(orate),
                "click_rate_pct": pct(crate, 2),
                "click_to_open_pct": pct(ctor),
                "placed_order_rate_pct": pct(por, 2),
                "benchmark_placed_order_pct": [pct(lo, 1), pct(hi, 1)],
                "revenue_per_recipient": money(rpr),
                "aov_from_flow": money(revenue / orders) if orders else None,
                "unsubscribe_rate_pct": pct(ur, 2),
                "spam_rate_pct": pct(sr, 3),
                "problems": [p[1] for p in problems],
                "fix_first": weakest,
                "upside_if_at_benchmark_low": money(max(0.0, lo - por) * delivered * (revenue / orders if orders else 0)),
            }
        )
    out.sort(key=lambda r: -r["upside_if_at_benchmark_low"])
    return {
        "flows": out,
        "summary": "; ".join(f"{r['flow']}: fix {r['fix_first'] or 'nothing — healthy'} (RPR {r['revenue_per_recipient']:.2f})" for r in out),
    }


@AGENT.tool
def flow_revenue_model(flow: str, monthly_triggers: int, aov: float, current_placed_order_rate_pct: float = -1.0, gross_margin_pct: float = 0.0) -> dict:
    """Size what a flow should earn per month at benchmark placed-order rates, the gap to today, and the per-email revenue split.

    Args:
        flow: Flow type (abandoned_checkout, abandoned_cart, browse_abandonment, welcome, post_purchase, win_back, replenishment).
        monthly_triggers: Profiles entering the flow per month (e.g. abandoned checkouts with an email).
        aov: Average order value for orders from this flow.
        current_placed_order_rate_pct: Current orders ÷ delivered as percent; -1 if the flow does not exist yet.
        gross_margin_pct: Optional margin to express the upside as contribution.
    """
    if flow not in BENCH or flow in ("other", "sunset"):
        raise ToolError(f"flow must be one of {', '.join(k for k in BENCH if k not in ('other', 'sunset'))}.")
    if monthly_triggers <= 0:
        raise ToolError("monthly_triggers must be > 0.")
    a = require_positive("aov", aov)
    lo, hi = BENCH[flow]
    n_emails = len(FLOWS[flow]["steps"])
    split = {3: [0.55, 0.30, 0.15], 2: [0.65, 0.35], 5: [0.45, 0.20, 0.15, 0.12, 0.08]}.get(n_emails, [1 / n_emails] * n_emails)
    low_rev, high_rev = monthly_triggers * lo * a, monthly_triggers * hi * a
    cur = None
    if current_placed_order_rate_pct >= 0:
        cur_rate = current_placed_order_rate_pct / 100
        cur = monthly_triggers * cur_rate * a
    margin = gross_margin_pct / 100 if gross_margin_pct > 1 else gross_margin_pct
    gap = (low_rev - cur) if cur is not None else low_rev
    return {
        "flow": flow,
        "monthly_triggers": monthly_triggers,
        "benchmark_placed_order_pct": [pct(lo, 1), pct(hi, 1)],
        "orders_per_month_at_benchmark": [round(monthly_triggers * lo), round(monthly_triggers * hi)],
        "revenue_per_month_at_benchmark": [money(low_rev), money(high_rev)],
        "current_revenue_per_month": money(cur) if cur is not None else None,
        "gap_to_benchmark_low": money(max(0.0, gap)),
        "gap_contribution": money(max(0.0, gap) * margin) if margin else None,
        "annual_gap": money(max(0.0, gap) * 12),
        "per_email_revenue_split_at_low": [{"email": i + 1, "share_pct": round(100 * s), "revenue": money(low_rev * s)} for i, s in enumerate(split)],
        "verdict": (
            f"{flow}: {monthly_triggers:,} triggers × {100 * lo:.1f}-{100 * hi:.1f}% × {a:.0f} = {low_rev:,.0f}-{high_rev:,.0f}/month at benchmark"
            + (f"; today {cur:,.0f} → gap {max(0.0, gap):,.0f}/month ({max(0.0, gap) * 12:,.0f}/yr)." if cur is not None else f"; the flow does not exist yet — {low_rev * 12:,.0f}+/yr on the table.")
        ),
    }
