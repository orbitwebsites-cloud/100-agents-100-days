"""Launch Planner — a dated countdown, per-channel asset checklist, go/no-go gate and launch-day runbook."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from ...core import Agent, ToolError
from ...lib import dates

AGENT = Agent(
    slug="launch-planner",
    name="Launch Planner",
    category="marketing",
    tagline="Work back from launch day to a dated plan: milestones on real business days, channel assets, and a go/no-go gate.",
    description=(
        "Plans product, feature and campaign launches the way a seasoned product marketer does: "
        "a T-minus countdown computed on business days from the launch date (compressed and flagged "
        "when time is short), a per-channel checklist with the exact assets, specs and lead times, "
        "a weighted go/no-go readiness score, a launch-day hour-by-hour runbook across time zones, "
        "and a target model that shows whether the channel mix can actually hit the signup goal."
    ),
    triggers=[
        "plan a product launch / feature launch",
        "launch timeline or countdown checklist",
        "what do I need to prepare before launch day",
        "Product Hunt launch plan",
        "go/no-go checklist for the launch",
        "launch day schedule",
    ],
    examples=[
        "We launch v2 on November 12. It's a medium-size launch: blog, email, Product Hunt, LinkedIn, and a press push. Build the plan.",
        "Here's our checklist with statuses — are we ready to launch Thursday?",
        "Goal is 1,500 signups in launch week. Email list 20k, LinkedIn 8k followers, PH, and a $3k ad budget. Realistic?",
    ],
    connectors=["Notion", "Asana", "Linear", "Google Calendar", "Slack", "HubSpot", "Google Sheets"],
    playbook="""
    ## Standard
    You are a launch lead who has shipped dozens of releases without a missed embargo or a
    dead link on launch morning. Excellent means: every milestone has a date that respects
    weekends and real lead times, every channel has its assets listed to the spec, the
    go/no-go decision is made on a checklist not a feeling, and the goal is a number the
    channel mix can plausibly deliver. The metric that matters is launch-week activation
    (signups that do the key action), not impressions.

    ## Intake
    Need: launch date, what's launching (new product / major feature / minor feature /
    campaign), channels available, and the goal (signups, revenue, coverage). If the date
    is missing, ask. If size is unclear, infer from the description (new product = large,
    headline feature = medium, improvement = small), state it, and continue. Ask at most 3
    questions.

    ## Procedure
    1. **Build the countdown.** Call `launch_planner__countdown_timeline` with the launch
       date, size and today's date. It returns dated milestones on business days and flags
       when the runway is shorter than the size needs — if flagged, either cut scope (drop
       press, shrink to a "soft launch") or move the date; say which and why.
    2. **List the channel work.** Call `launch_planner__channel_checklist` with the channels
       and launch date. It returns the assets per channel with specs and the date each must
       be final. Assign an owner to every asset in your plan; unowned assets don't ship.
    3. **Model the goal.** Call `launch_planner__launch_targets` with the goal and each
       channel's reach and expected conversion. If the projection is under goal, say what
       closes the gap (bigger list, paid budget, partners) or lower the goal — don't leave
       a plan that promises what the math denies.
    4. **Run the gate.** Before launch (and whenever the user shares statuses) call
       `launch_planner__readiness_score` with the checklist items and their status. P0 items
       not done = NO-GO, no exceptions. Report the score and the blockers.
    5. **Write the launch-day runbook** with `launch_planner__launch_day_schedule` using the
       launch time and the audience time zones, so posts land in working hours everywhere
       that matters.
    6. **Deliver** in the output format. Include the T+1 and T+7 steps — the retro and the
       second-wave content are where most launches leak value.

    ## Frameworks
    - **Launch sizes → runway:** small ≥ 2 weeks, medium ≥ 6 weeks, large ≥ 10 weeks.
      Below that, compress by dropping press (needs 2-3 weeks of embargo lead), then
      partners, then paid.
    - **Tiered launch (Apple/Stripe style):** Tier 1 gets the full stack (press, PH, email,
      all social, paid, partner co-marketing); Tier 2 gets blog + email + social; Tier 3
      gets changelog + in-app. Decide the tier first; it sets the asset list.
    - **Message hierarchy:** one headline promise → three proof points → the "what changed
      for you" line per persona. Every asset is derived from it; lock it before assets.
    - **Product Hunt:** launch 12:01 AM PT, Tuesday-Thursday; hunter and first 20 comments
      lined up; maker comment ready; no upvote begging.
    - **Press:** embargoed pitch T-10 business days, follow-up T-5, assets folder (logo,
      screenshots, founder headshot, quote) ready before pitching.
    - **Go/no-go gate P0s:** product works on prod, pricing/billing tested, landing page
      live with tracking verified, support briefed with FAQ, rollback plan exists.
    - **Post-launch:** T+1 thank-you + numbers to team, T+2 "what people are saying", T+7
      retro with the goal vs actual, T+14 second-wave content (tutorials, customer story).

    ## Output format
    ```
    # Launch plan — <what> · <YYYY-MM-DD> (<weekday>) · tier <1/2/3>
    **Goal:** <n signups / $> · **Projected:** <n> (<gap>) · **Runway:** <n> business days (<ok / compressed>)
    **Message:** <headline promise> — proof: <1> · <2> · <3>

    ## Countdown
    | When | Date | Milestone | Owner | Status |
    |---|---|---|---|---|

    ## Channel checklist
    ### <Channel> — final by <date>
    - [ ] <asset> (<spec>) — owner

    ## Launch day (times in <tz>)
    | Time | Action | Owner |
    |---|---|---|

    ## Go/no-go
    Score <n>/100 · P0 blockers: <list or none> · Decision: <GO / NO-GO until …>

    ## After launch
    T+1 … · T+7 … · T+14 …
    ```

    ## Anti-patterns
    - Milestones on Saturdays because someone counted calendar days.
    - Writing assets before the message hierarchy is locked (everything gets rewritten).
    - Launching on a Monday (no one's read email) or Friday (no follow-up window).
    - "We'll do press" with 4 days of runway.
    - A goal with no channel math behind it.
    - Shipping without a rollback plan or a support FAQ.
    - Going quiet after launch day; the second wave is free reach.
    """,
)

Size = Literal["small", "medium", "large"]

# (business days before launch, milestone, sizes it applies to, is_p0)
MILESTONES = [
    (50, "Positioning, message hierarchy and launch tier locked", ("large",), True),
    (40, "Beta / early-access customers recruited for quotes", ("large",), False),
    (30, "Positioning, message hierarchy and launch tier locked", ("medium",), True),
    (30, "Asset brief: landing page, blog, email, social, video, press kit", ("large",), False),
    (25, "Pricing / packaging final; billing tested in staging", ("large", "medium"), True),
    (20, "Asset brief: landing page, blog, email, social", ("medium",), False),
    (20, "Landing page copy + design draft", ("large",), False),
    (15, "Press list built; embargoed pitch sent (T-10 to T-15 business days)", ("large",), False),
    (12, "Landing page copy + design draft", ("medium",), False),
    (10, "Positioning and message locked", ("small",), True),
    (10, "Customer quotes / case study secured", ("large", "medium"), False),
    (10, "Embargoed press pitch sent", ("medium",), False),
    (8, "Blog post, email and social drafts complete", ("large", "medium"), False),
    (7, "Assets drafted: changelog, email, social", ("small",), False),
    (5, "Press follow-up; Product Hunt hunter + first-comment squad confirmed", ("large", "medium"), False),
    (5, "Landing page live on prod (noindex), analytics + conversion tracking verified", ("large", "medium", "small"), True),
    (4, "Support / sales briefed with FAQ and demo", ("large", "medium"), True),
    (3, "Feature flag / release verified on production; rollback plan written", ("large", "medium", "small"), True),
    (2, "Final QA of every link, UTM and form; emails scheduled", ("large", "medium", "small"), True),
    (1, "Social posts scheduled; team launch-day roles assigned", ("large", "medium", "small"), False),
    (0, "LAUNCH", ("large", "medium", "small"), True),
    (-1, "T+1: thank-you post, numbers to team, reply to every comment", ("large", "medium", "small"), False),
    (-5, "T+7: retro — goal vs actual, what to fix, second-wave content brief", ("large", "medium", "small"), False),
    (-10, "T+14: second wave — tutorial, customer story, comparison page", ("large", "medium"), False),
]
MIN_RUNWAY = {"small": 10, "medium": 30, "large": 50}


@AGENT.tool
def countdown_timeline(launch_date: str, size: Size = "medium", today: str = "", plan_start: str = "", holidays: list[str] = []) -> dict:
    """Dated T-minus milestones for a launch, computed on business days from the launch date and flagged when runway is short.

    Call first. Runway is measured from plan_start (the day the plan was made; defaults to today) and milestones are
    compressed if it is below the size's minimum. Re-run later with the same plan_start and a new today to see what is overdue.

    Args:
        launch_date: Launch date as YYYY-MM-DD.
        size: small (minor feature), medium (headline feature), large (new product / big campaign).
        today: Today's date as YYYY-MM-DD (defaults to the real today); milestones before it are marked overdue.
        plan_start: The date the plan was first built, YYYY-MM-DD (defaults to today). Keeps milestones fixed on re-runs.
        holidays: Dates to treat as non-working days (YYYY-MM-DD).
    """
    launch = dates.parse_date(launch_date)
    base = dates.parse_date(today) if today else date.today()
    anchor = dates.parse_date(plan_start) if plan_start else base
    if anchor > base:
        raise ToolError("plan_start cannot be after today.")
    hol = {dates.parse_date(h) for h in holidays}
    if size not in MIN_RUNWAY:
        raise ToolError("size must be small, medium or large.")
    runway = dates.business_days_between(anchor, launch, hol)
    if launch < base:
        raise ToolError(f"Launch date {launch_date} is before today ({base.isoformat()}).")
    need = MIN_RUNWAY[size]
    warnings = []
    if launch.weekday() >= 5:
        warnings.append(f"{launch.isoformat()} is a {launch.strftime('%A')} — move to Tuesday-Thursday.")
    elif launch.weekday() == 0:
        warnings.append("Monday launch: inboxes are full and there's no prep day — Tuesday is safer.")
    elif launch.weekday() == 4:
        warnings.append("Friday launch: no follow-up window before the weekend — Thursday is safer.")
    if launch in hol:
        warnings.append("Launch date is a holiday.")
    compressed = runway < need
    scale = runway / need if compressed and need else 1.0
    if compressed:
        warnings.append(
            f"Only {runway} business days of runway; a {size} launch wants ≥ {need}. Milestones are compressed ×{scale:.2f}. "
            + ("Drop press (needs ≥ 10 business days of embargo lead) and partners; consider a soft launch." if runway < 10 else "Drop press if not already pitched; parallelise asset work.")
        )
    rows = []
    for offset, name, sizes, p0 in MILESTONES:
        if size not in sizes:
            continue
        eff = round(offset * scale) if offset > 0 else offset
        d = dates.add_business_days(launch, -eff, hol)
        status = "overdue" if d < base and offset > 0 else "today" if d == base else "upcoming"
        rows.append({"t_minus_business_days": eff, "date": d.isoformat(), "weekday": d.strftime("%a"), "milestone": name, "p0": p0, "status": status})
    rows.sort(key=lambda r: r["date"])
    overdue = [r["milestone"] for r in rows if r["status"] == "overdue"]
    return {
        "launch_date": launch.isoformat(),
        "launch_weekday": launch.strftime("%A"),
        "today": base.isoformat(),
        "size": size,
        "runway_business_days": runway,
        "runway_calendar_days": (launch - base).days,
        "compressed": compressed,
        "milestones": rows,
        "overdue": overdue,
        "warnings": warnings,
        "summary": f"{size} launch on {launch.isoformat()} ({launch.strftime('%a')}): {runway} business days of runway ({'compressed' if compressed else 'ok'}), {len(rows)} milestones, {len(overdue)} overdue.",
    }


CHANNELS: dict[str, dict] = {
    "landing_page": {"lead_days": 7, "assets": [("hero headline + subhead + CTA", "≤ 10 words / ≤ 25 words / verb-first"), ("3 proof points with numbers", ""), ("screenshots or 30-60s demo video", "1920×1080, captions"), ("FAQ (5-8 questions)", ""), ("UTM + conversion tracking test", "")]},
    "blog": {"lead_days": 5, "assets": [("announcement post", "600-1,200 words, problem → what's new → how it works → proof → CTA"), ("OG image", "1200×630"), ("3 in-line screenshots/GIFs", "")]},
    "email": {"lead_days": 3, "assets": [("announcement email", "≤ 200 words, 1 CTA, subject ≤ 41 chars"), ("segment list (customers / trials / leads)", ""), ("follow-up email T+3", "story or FAQ angle")]},
    "product_hunt": {"lead_days": 7, "assets": [("tagline", "≤ 60 chars"), ("description", "≤ 260 chars"), ("gallery: 5-8 images", "1270×760"), ("first comment (maker story)", "150-300 words"), ("hunter + 20 supporters lined up", ""), ("launch 12:01 AM PT Tue-Thu", "")]},
    "linkedin": {"lead_days": 2, "assets": [("founder post", "≤ 3,000 chars; hook in first 210"), ("company page post", ""), ("carousel or 1 image", "1080×1080 / PDF ≤ 10 slides"), ("employee share kit (3 variants)", "")]},
    "x": {"lead_days": 2, "assets": [("announcement thread", "5-8 posts, ≤ 280 chars each, image on post 1"), ("demo GIF/video", "≤ 2:20, MP4"), ("reply kit for common questions", "")]},
    "press": {"lead_days": 15, "assets": [("press release", "≤ 500 words, AP style, quote from CEO + customer"), ("embargoed pitch", "≤ 150 words, 3 journalists per outlet tier"), ("press kit folder", "logo SVG/PNG, 5 screenshots, headshots, boilerplate"), ("exclusive offer decided", "")]},
    "paid": {"lead_days": 5, "assets": [("ad creative (3 angles × 2 formats)", "per-platform limits"), ("audiences + budget + bids", ""), ("landing page variant with message match", "")]},
    "in_app": {"lead_days": 3, "assets": [("announcement banner / modal", "≤ 25 words + CTA"), ("changelog entry", ""), ("tooltip / empty-state copy", "")]},
    "youtube": {"lead_days": 7, "assets": [("launch video", "60-180s, hook in 5s, captions"), ("thumbnail", "1280×720, ≤ 4 words"), ("title + description with timestamps", "title ≤ 60 chars")]},
    "partners": {"lead_days": 10, "assets": [("partner brief + co-marketing asks", ""), ("swipe copy (email + social)", ""), ("shared tracking links", "")]},
    "community": {"lead_days": 2, "assets": [("Slack/Discord announcement", "≤ 120 words"), ("Reddit / forum posts (value-first, no link-dropping)", ""), ("AMA slot booked", "")]},
    "webinar": {"lead_days": 14, "assets": [("registration page", ""), ("invite sequence (T-14, T-7, T-1, T-0)", ""), ("deck + demo script", "30 min + 15 Q&A"), ("replay email", "")]},
    "sales": {"lead_days": 4, "assets": [("battlecard + FAQ", ""), ("demo script update", ""), ("outbound sequence for target accounts", "")]},
    "support": {"lead_days": 4, "assets": [("help-center article", ""), ("macro / canned responses", ""), ("known-issues doc + escalation path", "")]},
}


@AGENT.tool
def channel_checklist(channels: list[str], launch_date: str, holidays: list[str] = []) -> dict:
    """Per-channel asset checklist with specs, lead times and the business-day deadline each asset must be final by.

    Call after the countdown. Unknown channel names are reported, not silently dropped.

    Args:
        channels: Channel keys, e.g. ["landing_page", "blog", "email", "product_hunt", "linkedin", "x", "press", "paid", "in_app", "youtube", "partners", "community", "webinar", "sales", "support"].
        launch_date: Launch date as YYYY-MM-DD.
        holidays: Non-working dates (YYYY-MM-DD).
    """
    if not channels:
        raise ToolError("channels is empty.")
    if len(channels) > 30:
        raise ToolError("Max 30 channels.")
    launch = dates.parse_date(launch_date)
    hol = {dates.parse_date(h) for h in holidays}
    plan, unknown = [], []
    total_assets = 0
    for raw in channels:
        key = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {"twitter": "x", "pr": "press", "ads": "paid", "ph": "product_hunt", "website": "landing_page", "newsletter": "email", "producthunt": "product_hunt", "discord": "community", "slack": "community"}
        key = aliases.get(key, key)
        spec = CHANNELS.get(key)
        if not spec:
            unknown.append(str(raw))
            continue
        deadline = dates.add_business_days(launch, -spec["lead_days"], hol)
        assets = [{"asset": a, "spec": s} for a, s in spec["assets"]]
        total_assets += len(assets)
        plan.append({"channel": key, "final_by": deadline.isoformat(), "final_by_weekday": deadline.strftime("%a"), "lead_business_days": spec["lead_days"], "assets": assets})
    plan.sort(key=lambda p: p["final_by"])
    if not plan:
        raise ToolError(f"No known channels in {channels}. Known: {', '.join(CHANNELS)}.")
    earliest = plan[0]
    return {
        "launch_date": launch.isoformat(),
        "channels": plan,
        "unknown_channels": unknown,
        "total_assets": total_assets,
        "first_deadline": {"channel": earliest["channel"], "date": earliest["final_by"]},
        "summary": f"{len(plan)} channels, {total_assets} assets. First deadline: {earliest['channel']} final by {earliest['final_by']} ({earliest['final_by_weekday']}).",
    }


P0_HINTS = ("prod", "production", "billing", "pricing", "tracking", "analytics", "rollback", "support", "faq", "landing page live", "legal", "security", "load test")


@AGENT.tool
def readiness_score(items: list[dict]) -> dict:
    """Weighted go/no-go score from a checklist of items with priority and status; any unfinished P0 forces NO-GO.

    Call whenever statuses are shared, and always the day before launch.

    Args:
        items: List of {"item": str, "priority": "P0"|"P1"|"P2", "status": "done"|"in_progress"|"not_started"|"blocked", "owner": str}. Priority defaults to P1 (P0 inferred for prod/billing/tracking/rollback/support items).
    """
    if not items:
        raise ToolError("items is empty.")
    if len(items) > 300:
        raise ToolError("Max 300 items.")
    weights = {"P0": 5, "P1": 3, "P2": 1}
    credit = {"done": 1.0, "in_progress": 0.5, "not_started": 0.0, "blocked": 0.0}
    rows, blockers, unowned = [], [], []
    earned = possible = 0.0
    for raw in items:
        if not isinstance(raw, dict):
            raise ToolError("Each item must be an object with item/priority/status.")
        name = str(raw.get("item", "")).strip()
        if not name:
            raise ToolError("An item has no 'item' text.")
        pr = str(raw.get("priority", "")).upper().strip()
        if pr not in weights:
            pr = "P0" if any(h in name.lower() for h in P0_HINTS) else "P1"
        st = str(raw.get("status", "not_started")).lower().replace(" ", "_").replace("-", "_")
        if st in ("complete", "completed", "shipped", "yes", "true"):
            st = "done"
        if st in ("wip", "started", "in_review"):
            st = "in_progress"
        if st in ("todo", "no", "false", "pending", "open"):
            st = "not_started"
        if st not in credit:
            raise ToolError(f"Unknown status {raw.get('status')!r} for {name!r}; use done / in_progress / not_started / blocked.")
        w = weights[pr]
        possible += w
        earned += w * credit[st]
        owner = str(raw.get("owner", "")).strip()
        if not owner and st != "done":
            unowned.append(name)
        if pr == "P0" and st != "done":
            blockers.append({"item": name, "status": st, "owner": owner or None})
        rows.append({"item": name, "priority": pr, "status": st, "owner": owner or None})
    score = round(100 * earned / possible) if possible else 0
    done = sum(1 for r in rows if r["status"] == "done")
    if blockers:
        decision = "NO-GO"
        reason = f"{len(blockers)} P0 item(s) not done: " + "; ".join(b["item"] for b in blockers[:5])
    elif score < 85:
        decision = "GO WITH CAUTION"
        reason = f"P0s clear but score {score} < 85 — accept the P1/P2 gaps explicitly or slip a day."
    else:
        decision = "GO"
        reason = f"All P0s done, score {score}/100."
    return {
        "score": score,
        "decision": decision,
        "reason": reason,
        "done": f"{done}/{len(rows)}",
        "p0_blockers": blockers,
        "unowned_open_items": unowned,
        "items": rows,
        "summary": f"{decision} — {reason}" + (f" {len(unowned)} open item(s) have no owner." if unowned else ""),
    }


@AGENT.tool
def launch_targets(goal: int, channels: list[dict]) -> dict:
    """Project launch-week signups per channel from reach × engagement × conversion, and the gap to the goal.

    Call to sanity-check the goal against the channel mix before promising it.

    Args:
        goal: Target number of signups (or the primary conversion) for launch week.
        channels: List of {"channel": str, "reach": int, "engagement_pct": float, "conversion_pct": float, "cost": float}. reach = people who can see it (list size, followers, impressions); engagement_pct = share who click/visit; conversion_pct = share of visitors who sign up.
    """
    if goal <= 0:
        raise ToolError("goal must be > 0.")
    if not channels or len(channels) > 50:
        raise ToolError("Provide 1-50 channels.")
    rows = []
    total = 0.0
    total_cost = 0.0
    for raw in channels:
        try:
            name = str(raw.get("channel", "channel"))
            reach = float(raw.get("reach", 0))
            eng = float(raw.get("engagement_pct", 0))
            cvr = float(raw.get("conversion_pct", 0))
            cost = float(raw.get("cost", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            raise ToolError("Each channel needs channel, reach, engagement_pct, conversion_pct (numbers).") from None
        if reach < 0 or not 0 <= eng <= 100 or not 0 <= cvr <= 100 or cost < 0:
            raise ToolError(f"{name}: reach ≥ 0, percentages 0-100, cost ≥ 0.")
        visitors = reach * eng / 100
        signups = visitors * cvr / 100
        total += signups
        total_cost += cost
        rows.append({"channel": name, "reach": int(reach), "visitors": round(visitors), "signups": round(signups, 1), "cost": cost, "cost_per_signup": round(cost / signups, 2) if cost and signups else None})
    rows.sort(key=lambda r: -r["signups"])
    gap = goal - total
    share = [{"channel": r["channel"], "share_pct": round(100 * r["signups"] / total, 1)} for r in rows] if total else []
    top = rows[0]
    if gap <= 0:
        verdict = f"On track: projected {total:.0f} vs goal {goal} ({-gap:.0f} buffer)."
    else:
        needed_visitors = gap / (max(r["signups"] / r["visitors"] for r in rows if r["visitors"]) if any(r["visitors"] for r in rows) else 0.02)
        verdict = f"Short by {gap:.0f} ({100 * gap / goal:.0f}% of goal). Options: ~{needed_visitors:.0f} more visitors at your best channel's conversion, add paid/partners, or reset the goal to ~{total * 0.9:.0f}."
    return {
        "goal": goal,
        "projected_signups": round(total, 1),
        "gap": round(gap, 1),
        "on_track": gap <= 0,
        "channels": rows,
        "share_of_signups": share,
        "total_cost": total_cost,
        "blended_cost_per_signup": round(total_cost / total, 2) if total_cost and total else None,
        "concentration_warning": f"{top['channel']} delivers {100 * top['signups'] / total:.0f}% of signups — a single point of failure." if total and top["signups"] / total > 0.6 else None,
        "verdict": verdict,
    }


LAUNCH_DAY = [
    (-120, "Final smoke test on production; confirm feature flag, pricing page, tracking", "eng + pmm"),
    (-60, "Publish landing page + blog (remove noindex); verify links, OG image", "pmm"),
    (-30, "Press embargo lifts / release goes to wire (if press)", "comms"),
    (0, "Send announcement email; post founder LinkedIn + X thread; in-app banner on", "pmm + founder"),
    (15, "Team share kit goes to Slack — everyone reposts with their own line", "all"),
    (60, "Reply to every comment / DM; watch support queue and error rates", "founder + support"),
    (120, "Post first proof ('200 teams turned it on in 2 hours') on social", "pmm"),
    (240, "Partner / community posts; paid campaigns switched on", "growth"),
    (480, "End-of-day numbers to team; log bugs; schedule T+1 thank-you post", "pmm"),
]


@AGENT.tool
def launch_day_schedule(launch_datetime: str, audience_utc_offsets: list[float] = [0.0], product_hunt: bool = False) -> dict:
    """Hour-by-hour launch-day runbook from the go-live time, with each step shown in every audience time zone.

    Call last. Warns when go-live lands outside 08:00-17:00 for an audience.

    Args:
        launch_datetime: Go-live moment as ISO datetime with offset, e.g. 2026-11-12T09:00:00-05:00.
        audience_utc_offsets: UTC offsets (hours) of key audiences, e.g. [-8, -5, 0, 1, 5.5].
        product_hunt: If True, prepends the 12:01 AM PT Product Hunt post and the maker-comment step.
    """
    try:
        go = datetime.fromisoformat(launch_datetime.strip())
    except (ValueError, AttributeError):
        raise ToolError("launch_datetime must be an ISO datetime with offset, e.g. 2026-11-12T09:00:00-05:00.") from None
    if go.tzinfo is None:
        raise ToolError("launch_datetime needs a UTC offset (e.g. -05:00) so audience times can be computed.")
    if not audience_utc_offsets or len(audience_utc_offsets) > 12:
        raise ToolError("Provide 1-12 audience UTC offsets.")
    if any(o < -12 or o > 14 for o in audience_utc_offsets):
        raise ToolError("UTC offsets must be between -12 and +14.")
    steps = list(LAUNCH_DAY)
    if product_hunt:
        # 12:01 AM Pacific on launch date; Pacific is UTC-7 (PDT) Mar-Nov else UTC-8.
        pacific = _tz(-7 if 3 <= go.month <= 10 else -8)
        ph_dt = datetime(go.year, go.month, go.day, 0, 1, tzinfo=pacific)
        ph_minutes = round((ph_dt - go).total_seconds() / 60)
        steps = [(ph_minutes, "Product Hunt goes live (12:01 AM PT); post maker comment within 5 min; notify hunter", "founder"), (ph_minutes + 30, "First 20 supporters comment (no upvote asks); reply to each", "team")] + steps
    steps.sort(key=lambda s: s[0])
    rows, warnings = [], []
    for minutes, action, owner in steps:
        t = go + timedelta(minutes=minutes)
        local = {f"UTC{o:+g}": (t.astimezone(_tz(o))).strftime("%H:%M") for o in audience_utc_offsets}
        rows.append({"offset_minutes": minutes, "launch_tz_time": t.strftime("%H:%M"), "audience_times": local, "action": action, "owner": owner})
    for o in audience_utc_offsets:
        h = go.astimezone(_tz(o)).hour
        if h < 8 or h >= 17:
            warnings.append(f"Go-live is {go.astimezone(_tz(o)).strftime('%H:%M')} for UTC{o:+g} — outside working hours; schedule that audience's email/social for 09:00-11:00 local.")
    return {
        "go_live": go.isoformat(),
        "go_live_weekday": go.strftime("%A"),
        "steps": rows,
        "warnings": warnings,
        "summary": f"{len(rows)} steps from T{rows[0]['offset_minutes']:+d} min to T+{rows[-1]['offset_minutes']} min; {len(warnings)} time-zone warning(s).",
    }


def _tz(offset_hours: float):
    from datetime import timezone

    return timezone(timedelta(hours=offset_hours))
