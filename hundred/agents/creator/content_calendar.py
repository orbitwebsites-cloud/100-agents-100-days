"""Content Calendar — a dated, multi-platform posting schedule that a solo creator can actually sustain."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import parse_hhmm, pct, tz

AGENT = Agent(
    slug="content-calendar",
    name="Content Calendar",
    category="creator",
    tagline="Turn 'post more' into a dated, multi-platform schedule that fits the hours you actually have.",
    description=(
        "Plans a creator's content calendar end-to-end: picks a cadence per platform the creator can "
        "sustain, generates dated posting slots with platform-native times (in the creator's and the "
        "audience's timezone), rotates content pillars so the feed never goes stale or salesy, checks "
        "every caption against real platform limits, and audits an existing calendar for gaps, streaks "
        "and pillar imbalance. Built on the capacity math most creators skip before burning out."
    ),
    triggers=[
        "build me a content calendar",
        "plan my posting schedule for the month",
        "how often should I post on each platform",
        "schedule my Instagram / TikTok / LinkedIn / YouTube posts",
        "does this caption fit the character limit",
        "audit my content mix / am I posting too much promo",
    ],
    examples=[
        "I'm a fitness coach with 6 hours a week. Build a 4-week calendar for Instagram, TikTok and a weekly newsletter.",
        "Here are my last 30 posts with dates and topics — tell me where the gaps and imbalances are.",
        "Plan October for LinkedIn (3x/week) and X (daily). I'm in Berlin, audience mostly US East.",
    ],
    connectors=["Notion", "Google Sheets", "Google Calendar", "Airtable", "Trello", "Buffer"],
    playbook="""
    ## Standard
    You are a content strategist who has run calendars for creators from 1k to 1M followers.
    "Excellent" here means one thing: a schedule the creator still follows in week six.
    The metric that matters is **consistency rate** (posts published ÷ posts planned) —
    a calendar that plans 20 posts and ships 8 is worse than one that plans 8 and ships 8.
    Everything else (pillars, timing, hashtags) is second-order to sustainability.

    ## Intake
    You need: (1) platforms + desired cadence, (2) weekly hours available for content,
    (3) 3-5 content pillars (topics the creator owns), and the creator's timezone.
    Ask only for what's missing and only if you cannot infer it; otherwise assume
    (e.g. 5 hours/week, timezone from context, pillars from their niche), state the
    assumptions in one line, and proceed. Never ask more than 3 questions.

    ## Procedure
    1. **Check capacity before cadence.** Call `content_calendar__capacity_check` with the
       hours available and each platform's desired posts per week. It costs every post at a
       realistic production time and tells you whether the plan fits. If the plan is over
       capacity, use the tool's `fit_plan` (the cadence scaled down to fit) — do not
       schedule what cannot be made. Present the trade-off, don't hide it.
    2. **Generate the dated slots.** Call `content_calendar__build_schedule` with the
       start date, number of weeks, the (fitted) platform cadences, pillars and timezone.
       It spreads posts across the best default days per platform, assigns posting times,
       rotates pillars so no two consecutive posts share a pillar, converts each slot to the
       audience timezone if given, and returns a per-day load table plus creation deadlines.
       Never hand-build dates: weekday arithmetic is exactly where calendars go wrong.
    3. **Fill each slot with a specific idea**, not a category. "Pillar: mobility" is a slot;
       "3 hip openers for desk workers who sit 8h (carousel, 5 slides)" is a post. Give every
       slot: hook idea, format, CTA, and which other slots it can be repurposed into.
       Repurposing rule: one long-form anchor per week feeds 3-5 short pieces.
    4. **Validate captions when you write them.** For any caption or title you draft, call
       `content_calendar__check_post_fits` with the platform. It measures the real character
       count (URLs on X count as 23), hashtag and mention counts, the 'see more' fold and the
       hard limit. Fix everything it flags before showing the caption.
    5. **Audit an existing calendar** (when the user gives you past or planned posts) with
       `content_calendar__audit_mix`. It computes pillar share, promo share, the longest gap
       per platform, same-pillar streaks and weekday coverage. Turn each flag into one
       concrete change in the next month's plan.
    6. **Act if you can.** If the user's AI has Notion/Sheets/Airtable/Trello, create the
       calendar there (one row per slot: date, time, platform, pillar, idea, status). With
       Google Calendar, create the creation-deadline events, not the posting events (the
       deadline is what protects consistency). Otherwise output the table ready to paste.

    ## Frameworks
    - **Pillar mix (default):** Educate 40% · Entertain/Relate 30% · Engage/Community 20% ·
      Promote ≤ 10-20%. Promo above 20% is the single most common reason engagement drops.
      Use the user's own targets if they have them.
    - **Hero / Hub / Help** (YouTube's model): one Hero piece per month or quarter, Hub
      content weekly (the show your audience returns for), Help content on evergreen search
      queries. Map each pillar to one of these so the calendar has a spine.
    - **Minimum viable cadence:** the smallest frequency that keeps an algorithm treating
      you as active — short-video platforms ~3/week, Instagram feed 2-3/week + stories,
      LinkedIn 2-3/week, X 1+/day, YouTube long-form 1/week, newsletter 1/week. Below that,
      consolidate platforms rather than spread thin. Two platforms done well beat five done badly.
    - **Batching:** create in 1-2 blocks per week, at least 2 days ahead of the posting date.
      The schedule tool's `create_by` dates enforce this.
    - **Timing:** posting time matters far less than consistency and the first line of the
      caption. Default to the platform's typical mid-morning/lunch windows in the *audience's*
      timezone, then let the creator's own analytics override after 4 weeks.

    ## Output format
    ```
    # Content calendar — <start> to <end> (<N> weeks)
    **Capacity:** <hours>/wk available · plan needs <hours>/wk → <fits / scaled down>
    **Pillars:** <A 40% · B 30% · C 20% · D 10%>   **Timezone:** <creator> (audience: <tz>)

    ## Week 1 (<date range>)
    | Date | Time (local / audience) | Platform | Pillar | Post idea (hook → format → CTA) | Create by |
    |---|---|---|---|---|---|

    ## Week 2 …

    ## Repurposing map
    <Anchor piece> → <short 1>, <short 2>, <carousel>, <newsletter section>

    ## Rules for this calendar
    - Batch days: <weekday(s)>; anything not created by `create_by` gets skipped, not rushed.
    - Review after week 4: keep the 2 formats with the best saves/shares per post.
    ```

    ## Anti-patterns
    - Scheduling every platform daily because "more is better". Consistency rate collapses by week 3.
    - Slots that say "tips post" — a slot without a hook and format is not a plan.
    - Three promo posts in a row before a launch. Interleave; the audit tool will flag it.
    - Treating best-posting-time charts as gospel. They are starting points; the creator's
      analytics after 4 weeks are the truth.
    - Ignoring the audience timezone. A 9 am post from Berlin lands at 3 am in New York.
    - Computing dates by hand. Use the schedule tool — off-by-one weekdays break batch days.
    """,
)

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_DAY_LOOKUP = {n.lower(): i for i, n in enumerate(WEEKDAY_NAMES)}
_DAY_LOOKUP.update({d.lower(): i for i, d in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])})

# Platform table: hard caption/title limits, mention/hashtag rules, default slot days (preference
# order) and a sane default time. Limits are the platforms' documented maximums.
PLATFORMS: dict[str, dict] = {
    "instagram": {"limit": 2200, "fold": 125, "max_hashtags": 30, "best_hashtags": (3, 5), "days": [1, 3, 2, 0, 4, 5, 6], "time": "11:00", "minutes": 45},
    "tiktok": {"limit": 4000, "fold": 100, "max_hashtags": None, "best_hashtags": (3, 5), "days": [1, 3, 4, 2, 0, 5, 6], "time": "18:00", "minutes": 75},
    "youtube": {"limit": 5000, "title_limit": 100, "fold": 157, "max_hashtags": 60, "best_hashtags": (0, 3), "days": [4, 5, 3, 1, 6, 2, 0], "time": "15:00", "minutes": 360},
    "youtube_shorts": {"limit": 5000, "title_limit": 100, "fold": 157, "max_hashtags": 60, "best_hashtags": (1, 3), "days": [1, 3, 5, 0, 2, 4, 6], "time": "16:00", "minutes": 75},
    "linkedin": {"limit": 3000, "fold": 210, "max_hashtags": None, "best_hashtags": (0, 3), "days": [1, 2, 3, 0, 4, 5, 6], "time": "08:30", "minutes": 25},
    "x": {"limit": 280, "fold": 280, "max_hashtags": None, "best_hashtags": (0, 1), "days": [1, 2, 3, 0, 4, 5, 6], "time": "09:00", "minutes": 10},
    "threads": {"limit": 500, "fold": 500, "max_hashtags": 1, "best_hashtags": (0, 1), "days": [1, 3, 2, 0, 4, 5, 6], "time": "12:00", "minutes": 10},
    "bluesky": {"limit": 300, "fold": 300, "max_hashtags": None, "best_hashtags": (0, 2), "days": [1, 2, 3, 0, 4, 5, 6], "time": "09:00", "minutes": 10},
    "facebook": {"limit": 63206, "fold": 477, "max_hashtags": None, "best_hashtags": (0, 2), "days": [2, 3, 1, 4, 0, 5, 6], "time": "13:00", "minutes": 20},
    "pinterest": {"limit": 500, "title_limit": 100, "fold": 500, "max_hashtags": None, "best_hashtags": (0, 0), "days": [5, 6, 4, 3, 2, 1, 0], "time": "20:00", "minutes": 15},
    "newsletter": {"limit": 100000, "fold": 90, "max_hashtags": None, "best_hashtags": (0, 0), "days": [1, 3, 2, 6, 0, 4, 5], "time": "07:00", "minutes": 120},
    "blog": {"limit": 200000, "fold": 160, "max_hashtags": None, "best_hashtags": (0, 0), "days": [1, 2, 3, 0, 4, 5, 6], "time": "07:00", "minutes": 180},
    "podcast": {"limit": 4000, "title_limit": 255, "fold": 120, "max_hashtags": None, "best_hashtags": (0, 0), "days": [1, 2, 3, 0, 4, 5, 6], "time": "05:00", "minutes": 240},
}
_ALIASES = {
    "ig": "instagram", "insta": "instagram", "reels": "instagram", "instagram_reels": "instagram",
    "twitter": "x", "yt": "youtube", "shorts": "youtube_shorts", "youtube shorts": "youtube_shorts",
    "fb": "facebook", "email": "newsletter", "substack": "newsletter", "beehiiv": "newsletter",
}


def norm_platform(name: str) -> str:
    key = str(name or "").strip().lower().replace("-", "_")
    key = _ALIASES.get(key, key)
    if key not in PLATFORMS:
        raise ToolError(f"Unknown platform {name!r}. Known: {', '.join(sorted(PLATFORMS))}.")
    return key


def _parse_days(raw, platform: str, n: int) -> list[int]:
    if raw:
        if not isinstance(raw, list):
            raise ToolError("days must be a list of weekday names like ['Tue', 'Thu']")
        out = []
        for d in raw:
            key = str(d).strip().lower()
            idx = _DAY_LOOKUP.get(key, _DAY_LOOKUP.get(key[:3]))
            if idx is None:
                raise ToolError(f"Unknown weekday {d!r}")
            out.append(idx)
        return out
    return sorted(PLATFORMS[platform]["days"][: min(n, 7)])


@AGENT.tool
def build_schedule(
    start_date: str,
    weeks: int,
    platforms: list[dict],
    pillars: list[str],
    timezone: str = "UTC",
    audience_timezone: str = "",
    lead_days: int = 2,
) -> dict:
    """Generate dated posting slots for several platforms with rotated pillars, times and creation deadlines.

    Spreads each platform's weekly posts over its best default days (or the days you specify),
    assigns a default posting time per platform, rotates content pillars so consecutive posts differ,
    converts each slot to the audience timezone, and reports per-day load and warnings.

    Args:
        start_date: First day of the calendar as YYYY-MM-DD (any weekday; weeks run from this date).
        weeks: Number of weeks to plan, 1-12.
        platforms: One dict per platform: {"platform": "instagram", "posts_per_week": 3,
            "days": ["Tue","Thu","Sat"] (optional), "time": "11:00" (optional, creator local time)}.
        pillars: Content pillar names to rotate through, e.g. ["Educate", "Story", "Community", "Promo"].
        timezone: Creator's IANA timezone (posting times are in this zone). Default UTC.
        audience_timezone: Optional IANA timezone of the main audience; each slot is also shown in it.
        lead_days: Days before the posting date by which the post must be created (default 2).
    """
    start = dates.parse_date(start_date)
    if not 1 <= weeks <= 12:
        raise ToolError("weeks must be between 1 and 12")
    if not platforms or len(platforms) > 12:
        raise ToolError("Give 1-12 platforms")
    pillars = [str(p).strip() for p in pillars if str(p).strip()]
    if not pillars or len(pillars) > 10:
        raise ToolError("Give 1-10 pillar names")
    zone = tz(timezone)
    aud_zone = tz(audience_timezone) if audience_timezone else None
    if not 0 <= lead_days <= 14:
        raise ToolError("lead_days must be 0-14")

    slots = []
    for spec in platforms:
        if not isinstance(spec, dict):
            raise ToolError("Each platform entry must be a dict like {'platform': 'x', 'posts_per_week': 5}")
        p = norm_platform(spec.get("platform", ""))
        n = spec.get("posts_per_week", 1)
        if not isinstance(n, int) or not 1 <= n <= 14:
            raise ToolError(f"{p}: posts_per_week must be an integer 1-14")
        days = _parse_days(spec.get("days"), p, n)
        hhmm = str(spec.get("time") or PLATFORMS[p]["time"])
        h, m = parse_hhmm(hhmm)
        for w in range(weeks):
            week_start = start + timedelta(days=7 * w)
            for k in range(n):
                wd = days[k % len(days)]
                offset = (wd - week_start.weekday()) % 7
                d = week_start + timedelta(days=offset)
                if d >= start + timedelta(days=7 * weeks):
                    d -= timedelta(days=7)
                slots.append({"date": d, "platform": p, "time": f"{h:02d}:{m:02d}"})
    slots.sort(key=lambda s: (s["date"], s["time"], s["platform"]))

    rows, load = [], Counter()
    last_pillar = None
    pillar_idx = 0
    for i, s in enumerate(slots, 1):
        pillar = pillars[pillar_idx % len(pillars)]
        if pillar == last_pillar and len(pillars) > 1:
            pillar_idx += 1
            pillar = pillars[pillar_idx % len(pillars)]
        pillar_idx += 1
        last_pillar = pillar
        h, m = parse_hhmm(s["time"])
        local = datetime(s["date"].year, s["date"].month, s["date"].day, h, m, tzinfo=zone)
        row = {
            "n": i,
            "date": s["date"].isoformat(),
            "weekday": WEEKDAY_NAMES[s["date"].weekday()],
            "week": (s["date"] - start).days // 7 + 1,
            "platform": s["platform"],
            "time_local": s["time"],
            "pillar": pillar,
            "create_by": (s["date"] - timedelta(days=lead_days)).isoformat(),
        }
        if aud_zone:
            a = local.astimezone(aud_zone)
            row["time_audience"] = a.strftime("%H:%M")
            row["audience_day_shift"] = (a.date() - s["date"]).days
        rows.append(row)
        load[s["date"].isoformat()] += 1

    warnings = []
    heavy = [(d, c) for d, c in sorted(load.items()) if c >= 4]
    if heavy:
        warnings.append(f"{len(heavy)} day(s) carry 4+ posts (e.g. {heavy[0][0]}: {heavy[0][1]}). Spread or batch-create them.")
    if aud_zone:
        odd = [r for r in rows if not 7 <= int(r["time_audience"][:2]) <= 21]
        if odd:
            warnings.append(f"{len(odd)} slot(s) land between 22:00 and 07:00 in the audience timezone; shift the creator time.")
    per_platform = Counter(r["platform"] for r in rows)
    pillar_share = {p: pct(c, len(rows)) for p, c in Counter(r["pillar"] for r in rows).items()}
    return {
        "start": start.isoformat(),
        "end": (start + timedelta(days=7 * weeks - 1)).isoformat(),
        "weeks": weeks,
        "total_posts": len(rows),
        "posts_per_platform": dict(per_platform),
        "pillar_share_pct": pillar_share,
        "posts_per_day": dict(sorted(load.items())),
        "busiest_day": max(load.items(), key=lambda kv: kv[1])[0] if load else None,
        "slots": rows,
        "warnings": warnings,
        "summary": f"{len(rows)} slots over {weeks} week(s) across {len(per_platform)} platform(s); {len(warnings)} warning(s).",
    }


HASHTAG_RE = re.compile(r"(?<![\w&])#\w{2,}")
MENTION_RE = re.compile(r"(?<!\w)@\w{2,}")
URL_RE = re.compile(r"https?://\S+|\bwww\.\S+")


@AGENT.tool
def check_post_fits(platform: str, text: str, title: str = "") -> dict:
    """Check a caption/post against a platform's real character limit, hashtag rules and 'see more' fold.

    Counts characters the way the platform does (URLs on X count as 23), hashtags, mentions and
    links, shows what is visible before the fold, and returns concrete fixes.

    Args:
        platform: instagram, tiktok, youtube, youtube_shorts, linkedin, x, threads, bluesky, facebook, pinterest, newsletter, blog, podcast.
        text: The caption, post body or description to check.
        title: Optional title (YouTube, Pinterest, podcast, newsletter subject) checked against its own limit.
    """
    p = norm_platform(platform)
    if len(text) > 250_000:
        raise ToolError("Text too long to check (250k chars max)")
    spec = PLATFORMS[p]
    urls = URL_RE.findall(text)
    chars = len(text)
    if p == "x":
        chars = len(URL_RE.sub("x" * 23, text))
    hashtags = HASHTAG_RE.findall(text)
    mentions = MENTION_RE.findall(text)
    limit = spec["limit"]
    fold = spec["fold"]
    fixes = []
    if chars > limit:
        fixes.append(f"Over the {limit}-char limit by {chars - limit}. Cut or move the rest to a comment/thread.")
    lo, hi = spec["best_hashtags"]
    if spec["max_hashtags"] is not None and len(hashtags) > spec["max_hashtags"]:
        fixes.append(f"{len(hashtags)} hashtags exceeds the platform maximum of {spec['max_hashtags']}" + (" — YouTube ignores ALL hashtags past 60." if p.startswith("youtube") else "."))
    elif len(hashtags) > hi:
        fixes.append(f"{len(hashtags)} hashtags; {lo}-{hi} is the sweet spot on {p}. Keep the most specific ones.")
    first_line = text.strip().split("\n", 1)[0] if text.strip() else ""
    if fold < limit and len(first_line) > fold:
        fixes.append(f"First line is {len(first_line)} chars; only ~{fold} show before 'see more'. Put the hook in the first {fold}.")
    if fold < limit and first_line and re.match(r"^(hi|hey|hello|welcome|happy|so |today i)", first_line.lower()):
        fixes.append("First line opens with a greeting/warm-up — lead with the hook instead.")
    if urls and p in ("instagram", "tiktok"):
        fixes.append("Links are not clickable in captions here; move the link to bio/comment and say so.")
    if urls and p == "linkedin":
        fixes.append("External links in the body tend to reduce reach on LinkedIn; put the link in the first comment.")
    if len(text.strip().split("\n")) == 1 and chars > 400 and p in ("linkedin", "facebook", "instagram"):
        fixes.append("One long paragraph. Break into 1-2 sentence lines for mobile.")
    out = {
        "platform": p,
        "chars": chars,
        "limit": limit,
        "fits": chars <= limit,
        "over_by": max(0, chars - limit),
        "remaining": max(0, limit - chars),
        "hashtags": len(hashtags),
        "mentions": len(mentions),
        "links": len(urls),
        "lines": len(text.strip().split("\n")) if text.strip() else 0,
        "visible_before_fold": text.strip()[:fold],
        "fold_chars": fold,
    }
    if title:
        tl = spec.get("title_limit")
        out["title"] = {"chars": len(title), "limit": tl, "fits": tl is None or len(title) <= tl}
        if tl and len(title) > tl:
            fixes.append(f"Title is {len(title)} chars; limit is {tl}.")
        if p.startswith("youtube") and len(title) > 70:
            fixes.append("YouTube titles past ~70 chars truncate in most placements; front-load the keyword.")
    out["fixes"] = fixes
    out["verdict"] = "Ready to post." if not fixes else f"{len(fixes)} fix(es) before posting."
    return out


@AGENT.tool
def audit_mix(posts: list[dict], targets: dict | None = None, promo_pillar: str = "promo") -> dict:
    """Audit a list of past or planned posts for pillar balance, promo share, gaps and streaks.

    Computes share per pillar vs targets, promo percentage, longest silence per platform,
    runs of 3+ consecutive posts with the same pillar, weekday coverage and a consistency verdict.

    Args:
        posts: One dict per post: {"date": "YYYY-MM-DD", "platform": "instagram", "pillar": "Educate", "format": "carousel" (optional)}.
        targets: Optional target share per pillar in percent, e.g. {"Educate": 40, "Story": 30, "Community": 20, "Promo": 10}.
        promo_pillar: Name (case-insensitive substring) of the pillar that counts as promotional. Default "promo".
    """
    if not posts:
        raise ToolError("posts is empty")
    if len(posts) > 2000:
        raise ToolError("Too many posts (2000 max)")
    parsed = []
    for i, p in enumerate(posts):
        if not isinstance(p, dict) or "date" not in p:
            raise ToolError(f"post #{i + 1} must be a dict with at least a 'date'")
        parsed.append({
            "date": dates.parse_date(str(p["date"])),
            "platform": str(p.get("platform", "unknown")).strip().lower() or "unknown",
            "pillar": str(p.get("pillar", "unlabelled")).strip() or "unlabelled",
            "format": str(p.get("format", "")).strip().lower(),
        })
    parsed.sort(key=lambda x: x["date"])
    n = len(parsed)
    pillar_counts = Counter(p["pillar"] for p in parsed)
    share = {k: pct(v, n) for k, v in pillar_counts.most_common()}
    promo = sum(v for k, v in pillar_counts.items() if promo_pillar.lower() in k.lower())
    promo_pct = pct(promo, n)
    flags = []
    if promo_pct > 20:
        flags.append(f"Promo is {promo_pct}% of posts (>20%). Cap at 20% and lead promos with value.")
    top_pillar, top_count = pillar_counts.most_common(1)[0]
    if len(pillar_counts) > 1 and top_count / n > 0.5:
        flags.append(f"'{top_pillar}' is {pct(top_count, n)}% of posts — one pillar over 50% reads as a one-note feed.")
    deviations = {}
    if targets:
        for k, target in targets.items():
            try:
                tval = float(target)
            except (TypeError, ValueError):
                raise ToolError(f"targets[{k!r}] must be a number") from None
            actual = share.get(k, 0.0)
            deviations[k] = {"target_pct": tval, "actual_pct": actual, "delta_pct": round(actual - tval, 1)}
            if abs(actual - tval) >= 10:
                flags.append(f"'{k}' is at {actual}% vs target {tval:g}% ({actual - tval:+.0f} pts).")
    # streaks
    streaks = []
    run_start, run_len = 0, 1
    for i in range(1, n + 1):
        if i < n and parsed[i]["pillar"] == parsed[i - 1]["pillar"]:
            run_len += 1
            continue
        if run_len >= 3:
            streaks.append({"pillar": parsed[run_start]["pillar"], "length": run_len, "from": parsed[run_start]["date"].isoformat(), "to": parsed[i - 1]["date"].isoformat()})
        run_start, run_len = i, 1
    if streaks:
        flags.append(f"{len(streaks)} streak(s) of 3+ same-pillar posts in a row (longest {max(s['length'] for s in streaks)}). Interleave pillars.")
    # gaps per platform
    by_platform: dict[str, list[date]] = defaultdict(list)
    for p in parsed:
        by_platform[p["platform"]].append(p["date"])
    gaps = {}
    for plat, ds in by_platform.items():
        ds = sorted(set(ds))
        longest = max((b - a).days for a, b in zip(ds, ds[1:])) if len(ds) > 1 else 0
        span_days = (ds[-1] - ds[0]).days + 1
        gaps[plat] = {"posts": len(by_platform[plat]), "span_days": span_days, "longest_gap_days": longest, "posts_per_week": round(7 * len(by_platform[plat]) / span_days, 1) if span_days else len(by_platform[plat])}
        if longest >= 10:
            flags.append(f"{plat}: {longest}-day gap — silence over ~10 days costs reach; schedule a lightweight filler format.")
    weekday_counts = Counter(WEEKDAY_NAMES[p["date"].weekday()] for p in parsed)
    formats = Counter(p["format"] for p in parsed if p["format"])
    score = 100 - min(60, 10 * len(flags))
    return {
        "posts": n,
        "date_range": [parsed[0]["date"].isoformat(), parsed[-1]["date"].isoformat()],
        "pillar_share_pct": share,
        "promo_pct": promo_pct,
        "vs_targets": deviations,
        "streaks": streaks,
        "per_platform": gaps,
        "weekday_counts": {d: weekday_counts.get(d, 0) for d in WEEKDAY_NAMES},
        "format_counts": dict(formats.most_common()),
        "health_score": score,
        "flags": flags,
        "verdict": "Healthy mix." if not flags else f"{len(flags)} issue(s) to fix in next month's plan.",
    }


@AGENT.tool
def capacity_check(hours_per_week: float, platforms: list[dict], repurpose_share: float = 0.3) -> dict:
    """Check whether a posting cadence fits the creator's weekly hours and scale it down if not.

    Costs each platform's posts at a realistic production time (overridable), applies a repurposing
    discount, and returns the fitted cadence when the plan exceeds capacity.

    Args:
        hours_per_week: Hours the creator can spend on content each week (creation, editing, captions).
        platforms: One dict per platform: {"platform": "youtube", "posts_per_week": 1, "minutes_per_post": 240 (optional override)}.
        repurpose_share: Fraction 0-0.6 of posts that are repurposed from an anchor piece (cost ~25% of a fresh post). Default 0.3.
    """
    if hours_per_week <= 0 or hours_per_week > 100:
        raise ToolError("hours_per_week must be between 0 and 100")
    if not platforms:
        raise ToolError("platforms is empty")
    if not 0 <= repurpose_share <= 0.6:
        raise ToolError("repurpose_share must be between 0 and 0.6")
    budget = hours_per_week * 60
    lines, total = [], 0.0
    for spec in platforms:
        if not isinstance(spec, dict):
            raise ToolError("Each platform entry must be a dict")
        p = norm_platform(spec.get("platform", ""))
        n = spec.get("posts_per_week", 1)
        if not isinstance(n, (int, float)) or n <= 0 or n > 21:
            raise ToolError(f"{p}: posts_per_week must be 1-21")
        mpp = spec.get("minutes_per_post") or PLATFORMS[p]["minutes"]
        if not isinstance(mpp, (int, float)) or mpp <= 0:
            raise ToolError(f"{p}: minutes_per_post must be > 0")
        effective = mpp * (1 - repurpose_share * 0.75)
        cost = n * effective
        total += cost
        lines.append({"platform": p, "posts_per_week": n, "minutes_per_post": mpp, "weekly_minutes": round(cost)})
    ratio = total / budget
    fit_plan = []
    if ratio > 1:
        scale = 1 / ratio
        for ln in lines:
            fitted = max(1, int(ln["posts_per_week"] * scale)) if ln["posts_per_week"] >= 1 else ln["posts_per_week"]
            fit_plan.append({"platform": ln["platform"], "posts_per_week": fitted})
        fit_minutes = sum(f["posts_per_week"] * ln["weekly_minutes"] / ln["posts_per_week"] for f, ln in zip(fit_plan, lines))
        while fit_minutes > budget and any(f["posts_per_week"] > 1 for f in fit_plan):
            # drop one post from the most expensive platform still above 1/week
            idx = max((i for i, f in enumerate(fit_plan) if f["posts_per_week"] > 1), key=lambda i: lines[i]["minutes_per_post"])
            fit_plan[idx]["posts_per_week"] -= 1
            fit_minutes = sum(f["posts_per_week"] * ln["weekly_minutes"] / ln["posts_per_week"] for f, ln in zip(fit_plan, lines))
        if fit_minutes > budget:
            fit_plan = sorted(fit_plan, key=lambda f: lines[[x["platform"] for x in lines].index(f["platform"])]["minutes_per_post"])[:2]
            note = "Even at 1 post/week per platform the plan does not fit; keep the two cheapest platforms."
        else:
            note = "Scaled cadence that fits the weekly budget."
    else:
        note = "Plan fits."
    verdict = (
        f"Needs {total / 60:.1f} h/wk against {hours_per_week:g} h available ({ratio:.0%} of capacity). "
        + ("Fits" + (" with little slack — expect misses on busy weeks." if ratio > 0.85 else ".") if ratio <= 1 else "Over capacity — use fit_plan.")
    )
    return {
        "hours_available": hours_per_week,
        "hours_needed": round(total / 60, 1),
        "utilisation_pct": round(100 * ratio),
        "fits": ratio <= 1,
        "per_platform": lines,
        "fit_plan": fit_plan,
        "fit_plan_note": note if ratio > 1 else "",
        "verdict": verdict,
    }
