"""Podcast Producer — chapters, show notes, ad breaks, metadata and a release calendar a real producer would sign off."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Literal

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import FILLER_RE, fmt_minutes, fmt_timestamp, parse_hhmm, parse_timestamp, tz

AGENT = Agent(
    slug="podcast-producer",
    name="Podcast Producer",
    category="creator",
    tagline="Turn a raw episode into chapters, show notes, ad breaks and metadata that pass Apple, Spotify and YouTube rules.",
    description=(
        "Runs post-production the way a senior podcast producer does: profiles the transcript (host vs "
        "guest talk share, fillers per minute, monologues to trim), builds valid YouTube chapters and "
        "Apple/Spotify timestamps, structures show notes around what listeners search for, places "
        "pre/mid/post-roll ad breaks at retention-safe points with a revenue estimate, checks titles and "
        "descriptions against platform limits, and schedules the release with record/edit deadlines."
    ),
    triggers=[
        "write show notes for this episode",
        "make chapters / timestamps for my podcast",
        "where should I put the ad breaks",
        "episode title and description for Apple / Spotify",
        "plan my podcast release schedule",
        "analyze this podcast transcript",
    ],
    examples=[
        "Here's the transcript of episode 42 with my guest — chapters, show notes and a title please.",
        "58-minute episode, 12k downloads per episode. Where do the two mid-rolls go and what's it worth?",
        "Plan a weekly Tuesday release for 12 episodes starting Oct 6, with recording deadlines.",
    ],
    connectors=["Notion", "Google Docs", "YouTube", "Spotify for Podcasters", "Descript", "Transistor", "Buzzsprout"],
    playbook="""
    ## Standard
    You are the producer a top-100 show hires after its host stops having time. Excellent
    means: a listener can decide in 10 seconds whether this episode is for them, jump
    straight to the part they want, and the host never has to redo a deliverable. The metric
    that matters is **completion rate** (Apple 'average consumption', Spotify 'completion'):
    chapters, ad placement and the cold open exist to keep it above ~70% on sub-60-minute
    episodes.

    ## Intake
    You need the transcript (with speaker labels if possible) or at minimum the episode
    length, guest, and 3-5 topics. Ask for the transcript only if nothing else was given; if
    you have the audio description but no transcript, produce notes marked "from summary,
    verify timestamps". Assume a weekly show, single host, and an interview format unless told.

    ## Procedure
    1. **Profile the transcript.** Call `podcast_producer__analyze_transcript` first. It
       returns speakers with talk share, questions asked per speaker, fillers per minute,
       longest monologues and the passages with the densest filler. Use talk share to judge
       the interview (host > 40% in an interview show is a flag), and the dense-filler
       passages as edit candidates.
    2. **Draft chapters** from topic shifts — 5-10 for a 45-60 min episode, each a listener
       would jump to. Then call `podcast_producer__format_chapters` with the start times and
       titles. It validates YouTube rules (must start at 0:00, ≥ 3 chapters, ≥ 10 s each,
       ascending), computes each chapter's length, and returns the description-ready block.
       Titles: 3-8 words, benefit or question, no "Part 1 / Intro".
    3. **Place the ads** if the show is monetised: call `podcast_producer__plan_ad_breaks`
       with the duration, ad load and downloads (and the CPM the show actually gets, if
       known). It places pre/mid/post-rolls at retention-safe points (never inside the cold
       open, never in the last 10%, mid-rolls at natural thirds) and estimates revenue. Then
       snap each mid-roll to the nearest chapter boundary from step 2.
    4. **Write show notes** in the output format: a 2-sentence hook, 3-5 "you'll learn"
       bullets with timestamps, guest bio + links, resources mentioned (every book, tool,
       person named in the transcript — no omissions), and a transcript-grounded quote.
    5. **Title and description.** Write 3 title options; call
       `podcast_producer__check_metadata` on the winner with the description. It checks Apple
       (255-char title, 4000-char description, no episode numbers/show name in the title —
       those belong in the episode-number field), Spotify/Apple truncation (~60 visible chars),
       YouTube (100-char title), keyword stuffing and a weak first 120 characters.
    6. **Schedule.** For a new show or a season, call
       `podcast_producer__plan_release_calendar` with the first publish date, cadence and
       count. It returns publish dates with record-by, edit-by and notes-by deadlines so the
       pipeline never slips. Push these to Notion/Calendar if connected.
    7. **Self-check:** every timestamp exists in the transcript; every resource mentioned is
       listed; the description's first 120 chars sell the episode without the show name.

    ## Frameworks
    - **Cold open:** 20-45 s of the best moment, before the intro music. Chapters start at
      0:00 "Cold open", not "Intro".
    - **Interview balance:** guest 60-75% of words; host asks 12-25 questions/hour; a
      monologue over 400 words by either person is an edit candidate.
    - **Filler benchmark:** under 2 fillers/min is clean; 2-5 edit the worst passages; over 5
      needs a de-um pass (Descript/Riverside) before release.
    - **Ad load:** industry norm is one break per ~15-20 min and total ads ≤ 10% of runtime.
      Host-read mid-rolls are typically quoted at a higher CPM than pre/post-roll; use the
      show's own CPM when known and label estimates as estimates.
    - **Search-first titles:** guest name + the specific claim ("Andrew Chen on why 90% of
      growth teams measure the wrong thing"), not "Ep. 42 — A conversation with…".
    - **Release cadence:** same weekday, same hour, every time. Tuesday-Thursday early
      morning in the audience's timezone is the safe default; consistency beats the slot.

    ## Output format
    ```
    # Ep <N>: <title> (<duration>)
    **Guest:** <name, one-line credential> · **Talk share:** host NN% / guest NN%

    ## Hook (for description, ≤ 120 chars first)
    <2 sentences>

    ## Chapters
    0:00 Cold open
    <m:ss> <chapter title>
    …

    ## You'll learn
    - (<m:ss>) <specific takeaway>

    ## Resources mentioned
    - <Book/tool/person> — <link or "add link">

    ## Quote
    "<verbatim, ≤ 30 words>" — <speaker> (<m:ss>)

    ## Ad breaks
    Pre-roll 0:00 · Mid-roll 1 <m:ss> (after "<chapter>") · … · Post-roll <m:ss> — est. $<n>/episode

    ## Metadata
    Title (<n> chars): … · Description check: <passes / fixes> · Tags: …
    ```

    ## Anti-patterns
    - Chapters called "Intro", "Main discussion", "Wrap-up". Name what is said, not where it is.
    - Show notes that summarise chronologically. Lead with what the listener gets.
    - Mid-rolls at exactly 33% and 66% with no regard to the conversation — snap to a topic boundary.
    - Titles starting with the episode number or show name — wasted characters in every app.
    - Omitting a resource the guest mentioned. Listeners email about it; the host gets blamed.
    - Timestamps guessed from vibes. Every one comes from the transcript or the tool.
    """,
)

SPEAKER_RE = re.compile(r"^\s*(?:\[?[\d:]{4,8}\]?\s*)?([A-Z][\w .'-]{0,40}?)\s*(?:\([^)]*\))?\s*:\s+(.+)$")
TIMESTAMP_PREFIX_RE = re.compile(r"^\s*\[?((?:\d{1,2}:)?\d{1,2}:\d{2})\]?")


@AGENT.tool
def analyze_transcript(transcript: str, host: str = "") -> dict:
    """Profile a podcast transcript: talk share, questions per speaker, fillers per minute, long monologues, edit candidates.

    Expects "Name: text" lines (optionally prefixed with [mm:ss]). Estimates duration from
    timestamps when present, otherwise from word count at 150 wpm.

    Args:
        transcript: The raw transcript with speaker labels.
        host: Optional host name to judge interview balance (host share > 40% is flagged).
    """
    if not transcript.strip():
        raise ToolError("Transcript is empty.")
    if len(transcript) > 600_000:
        raise ToolError("Transcript too long (600k chars max). Split by segment.")
    words_by: Counter[str] = Counter()
    questions: Counter[str] = Counter()
    fillers_by: Counter[str] = Counter()
    monologues: list[dict] = []
    dense: list[dict] = []
    last_ts = None
    unattributed = 0
    for n, line in enumerate(transcript.splitlines(), 1):
        if not line.strip():
            continue
        m = SPEAKER_RE.match(line)
        tsm = TIMESTAMP_PREFIX_RE.match(line)
        if tsm:
            try:
                last_ts = parse_timestamp(tsm.group(1))
            except ToolError:
                pass
        if not m:
            unattributed += 1
            continue
        speaker, said = m.group(1).strip(), m.group(2)
        wc = len(text.words(said))
        words_by[speaker] += wc
        questions[speaker] += said.count("?")
        f = len(FILLER_RE.findall(said))
        fillers_by[speaker] += f
        if wc >= 400:
            monologues.append({"line": n, "speaker": speaker, "words": wc, "preview": said[:120]})
        if wc >= 12 and f / wc >= 0.06:
            dense.append({"line": n, "speaker": speaker, "fillers": f, "words": wc, "preview": said[:120]})
    total_words = sum(words_by.values())
    if not total_words:
        raise ToolError("No 'Name: text' lines found — add speaker labels or use a transcript export with them.")
    minutes = round(last_ts / 60, 1) if last_ts and last_ts > 60 else round(total_words / 150, 1)
    share = {s: round(100 * w / total_words, 1) for s, w in words_by.most_common()}
    total_fillers = sum(fillers_by.values())
    fpm = round(total_fillers / minutes, 1) if minutes else 0.0
    flags = []
    if host:
        hkey = next((s for s in share if s.lower() == host.strip().lower()), None)
        if hkey is None:
            flags.append(f"Host {host!r} not found among speakers {list(share)}.")
        elif len(share) > 1 and share[hkey] > 40:
            flags.append(f"Host talks {share[hkey]}% — over the 40% interview ceiling. Trim host preambles.")
        if hkey and minutes and not 12 <= questions[hkey] / (minutes / 60) <= 25 and len(share) > 1:
            flags.append(f"Host asked {questions[hkey]} questions in {minutes} min ({questions[hkey] / (minutes / 60):.0f}/hour; 12-25 is the interview range).")
    if fpm > 5:
        flags.append(f"{fpm} fillers/min — needs a de-um pass before release.")
    elif fpm > 2:
        flags.append(f"{fpm} fillers/min — edit the {len(dense)} densest passages.")
    if monologues:
        flags.append(f"{len(monologues)} monologue(s) over 400 words — candidates to tighten or chapter.")
    return {
        "speakers": list(share),
        "talk_share_pct": share,
        "total_words": total_words,
        "estimated_minutes": minutes,
        "duration_source": "timestamps" if last_ts and last_ts > 60 else "word count @150wpm",
        "questions_by_speaker": dict(questions),
        "fillers_by_speaker": dict(fillers_by),
        "fillers_per_minute": fpm,
        "long_monologues": monologues[:20],
        "filler_dense_passages": sorted(dense, key=lambda d: -d["fillers"] / d["words"])[:15],
        "unattributed_lines": unattributed,
        "flags": flags,
        "verdict": f"{minutes} min, {len(share)} speakers, {fpm} fillers/min; {len(flags)} flag(s).",
    }


@AGENT.tool
def format_chapters(chapters: list[dict], total_duration: str = "") -> dict:
    """Validate and format episode chapters for YouTube (0:00 start, ≥3, ≥10 s each, ascending) and Apple/Spotify.

    Returns each chapter's length, the rule violations that would make YouTube ignore the
    chapters entirely, and ready-to-paste text blocks.

    Args:
        chapters: List of {"start": "mm:ss" | "h:mm:ss" | seconds, "title": str} in order.
        total_duration: Optional episode length ("58:20" or seconds) to compute the last chapter's length and catch overruns.
    """
    if not chapters:
        raise ToolError("chapters is empty")
    if len(chapters) > 300:
        raise ToolError("Too many chapters (300 max)")
    parsed = []
    for i, c in enumerate(chapters, 1):
        if not isinstance(c, dict) or "start" not in c:
            raise ToolError(f"chapter #{i} must be {{'start': 'mm:ss', 'title': ...}}")
        title = str(c.get("title", "")).strip()
        if not title:
            raise ToolError(f"chapter #{i} has no title")
        parsed.append({"start_s": parse_timestamp(c["start"]), "title": title})
    total = parse_timestamp(total_duration) if total_duration else None
    issues = []
    if parsed[0]["start_s"] != 0:
        issues.append("First chapter must start at 0:00 or YouTube shows no chapters at all.")
    if len(parsed) < 3:
        issues.append("YouTube needs at least 3 chapters.")
    rows = []
    for i, ch in enumerate(parsed):
        nxt = parsed[i + 1]["start_s"] if i + 1 < len(parsed) else total
        length = (nxt - ch["start_s"]) if nxt is not None else None
        row = {"n": i + 1, "start": fmt_timestamp(ch["start_s"]), "start_s": ch["start_s"], "title": ch["title"], "length_s": length, "length": fmt_minutes(length) if length is not None else "to end"}
        if i and ch["start_s"] <= parsed[i - 1]["start_s"]:
            issues.append(f"Chapter {i + 1} ({ch['title']}) starts at or before chapter {i} — timestamps must ascend.")
        if length is not None and length < 10:
            issues.append(f"Chapter {i + 1} ({ch['title']}) is {length}s — YouTube requires ≥ 10 s.")
        if length is not None and length < 0:
            issues.append(f"Chapter {i + 1} starts after the episode ends ({fmt_timestamp(ch['start_s'])} > {fmt_timestamp(total)}).")
        if re.fullmatch(r"(intro|introduction|outro|wrap.?up|conclusion|main (topic|discussion)|part \d+)", ch["title"], re.I):
            issues.append(f"Chapter {i + 1} title '{ch['title']}' says where, not what — name the content.")
        wc = len(text.words(ch["title"]))
        if wc > 10:
            issues.append(f"Chapter {i + 1} title is {wc} words; keep to 3-8.")
        rows.append(row)
    lengths = [r["length_s"] for r in rows if r["length_s"] is not None and r["length_s"] > 0]
    if lengths and max(lengths) > 1500 and len(rows) >= 3:
        longest = max(rows, key=lambda r: r["length_s"] or 0)
        issues.append(f"Chapter '{longest['title']}' runs {fmt_minutes(longest['length_s'])} — over 25 min; split it.")
    hard = [i for i in issues if "YouTube" in i or "ascend" in i or "after the episode" in i]
    yt_block = "\n".join(f"{r['start']} {r['title']}" for r in rows)
    apple_block = "\n".join(f"({r['start']}) {r['title']}" for r in rows)
    return {
        "chapters": rows,
        "count": len(rows),
        "total_duration": fmt_timestamp(total) if total is not None else None,
        "average_length_s": round(sum(lengths) / len(lengths)) if lengths else None,
        "youtube_valid": not hard,
        "issues": issues,
        "youtube_block": yt_block,
        "apple_spotify_block": apple_block,
        "verdict": ("YouTube-valid chapters." if not hard else "YouTube will ignore these chapters until fixed.") + (f" {len(issues)} note(s)." if issues else ""),
    }


@AGENT.tool
def plan_ad_breaks(
    duration: str,
    ad_load: Literal["none", "light", "standard", "heavy"] = "standard",
    downloads_per_episode: int = 0,
    cpm: float = 25.0,
    cold_open_seconds: int = 60,
) -> dict:
    """Place pre/mid/post-roll ad breaks at retention-safe points and estimate per-episode revenue.

    Light = pre + 1 mid, standard = pre + mids every ~20 min, heavy = pre + mids every ~12 min + post.
    Mid-rolls never land inside the cold open/intro or the last 10% of the episode.

    Args:
        duration: Episode length as "58:20", "1:02:10" or seconds.
        ad_load: none, light, standard (default) or heavy.
        downloads_per_episode: Expected downloads in the first 30 days (0 to skip revenue).
        cpm: Revenue per 1,000 downloads per ad slot in your currency; default 25 (a commonly cited host-read benchmark — use your own).
        cold_open_seconds: Length of cold open + intro that mid-rolls must not interrupt (default 60).
    """
    total = parse_timestamp(duration)
    if total < 120:
        raise ToolError("Episode must be at least 2 minutes to place ads.")
    if total > 6 * 3600:
        raise ToolError("Duration over 6 hours — check the format.")
    if downloads_per_episode < 0 or cpm < 0:
        raise ToolError("downloads_per_episode and cpm must be ≥ 0")
    if ad_load == "none":
        return {"duration": fmt_timestamp(total), "breaks": [], "ad_seconds": 0, "ad_load_pct": 0.0, "estimated_revenue": 0.0, "verdict": "No ads placed."}
    spacing = {"light": None, "standard": 20 * 60, "heavy": 12 * 60}[ad_load]
    earliest = max(cold_open_seconds, 8 * 60) if total >= 20 * 60 else max(cold_open_seconds, int(0.25 * total))
    latest = int(total * 0.9)
    if spacing is None:
        n_mid = 1 if total >= 15 * 60 else 0
    else:
        n_mid = max(1, int(total // spacing)) if total >= 15 * 60 else 0
        n_mid = min(n_mid, 6)
    breaks = [{"type": "pre-roll", "at": "0:00", "at_s": 0, "seconds": 30, "note": "Before the cold open or right after it — never over it."}]
    if n_mid:
        window = latest - earliest
        for k in range(1, n_mid + 1):
            pos = earliest + int(window * k / (n_mid + 1))
            breaks.append({"type": f"mid-roll {k}", "at": fmt_timestamp(pos), "at_s": pos, "seconds": 60, "note": "Snap to the nearest chapter boundary after this point."})
    if ad_load == "heavy" or total >= 40 * 60:
        breaks.append({"type": "post-roll", "at": fmt_timestamp(total - 20), "at_s": total - 20, "seconds": 30, "note": "After the outro CTA; lowest completion, price accordingly."})
    ad_seconds = sum(b["seconds"] for b in breaks)
    load_pct = round(100 * ad_seconds / total, 1)
    slots = len(breaks)
    revenue = round(downloads_per_episode / 1000 * cpm * slots, 2) if downloads_per_episode else None
    flags = []
    if load_pct > 10:
        flags.append(f"Ad load {load_pct}% exceeds the ~10% norm; drop a slot or shorten reads.")
    if downloads_per_episode and downloads_per_episode < 1000:
        flags.append("Under 1,000 downloads/episode most networks will not sell CPM ads — pitch flat-fee sponsors or affiliates instead.")
    return {
        "duration": fmt_timestamp(total),
        "ad_load": ad_load,
        "breaks": breaks,
        "slots": slots,
        "ad_seconds": ad_seconds,
        "ad_load_pct": load_pct,
        "mid_roll_window": [fmt_timestamp(earliest), fmt_timestamp(latest)],
        "estimated_revenue": revenue,
        "revenue_basis": f"{downloads_per_episode} downloads × {cpm} CPM × {slots} slots" if revenue is not None else "no downloads given",
        "flags": flags,
        "verdict": f"{slots} slot(s), {load_pct}% ad load" + (f", ≈{revenue:,.0f} per episode" if revenue else "") + ("; " + " ".join(flags) if flags else "."),
    }


NUMBER_PREFIX_RE = re.compile(r"^\s*(ep(isode)?\.?\s*#?\s*\d+|#\d+|\d+\s*[:\-–|.])", re.I)


@AGENT.tool
def check_metadata(title: str, description: str, show_name: str = "", guest: str = "") -> dict:
    """Check an episode title and description against Apple Podcasts, Spotify and YouTube rules and truncation.

    Flags episode numbers or show names in the title (Apple wants them in the episode fields),
    titles that truncate in apps, a weak first 120 characters, missing guest name, keyword
    stuffing and description overruns.

    Args:
        title: Proposed episode title.
        description: Proposed episode description / show notes text.
        show_name: The podcast's name, to detect it being wasted inside the episode title.
        guest: Guest name, to check it appears in the title or the first 120 chars.
    """
    if not title.strip():
        raise ToolError("Title is empty.")
    if len(description) > 100_000:
        raise ToolError("Description too long to check.")
    t = title.strip()
    fixes = []
    if len(t) > 255:
        fixes.append(f"Title is {len(t)} chars; Apple's hard limit is 255.")
    if len(t) > 100:
        fixes.append(f"Title is {len(t)} chars; YouTube's limit is 100.")
    if len(t) > 60:
        fixes.append(f"Title is {len(t)} chars; Apple/Spotify show ~60 in lists — front-load the payoff.")
    if NUMBER_PREFIX_RE.match(t):
        fixes.append("Title starts with an episode number — put it in the episode-number field, not the title.")
    if show_name and show_name.strip().lower() in t.lower():
        fixes.append("Show name inside the episode title wastes characters; apps already display it.")
    if guest and guest.strip().lower() not in t.lower() and guest.strip().lower() not in description[:120].lower():
        fixes.append("Guest name is neither in the title nor the first 120 chars of the description — searchers won't find it.")
    if t.isupper():
        fixes.append("ALL CAPS title — Apple rejects shouty titles; use sentence or title case.")
    if re.search(r"\b(with|ft\.?|featuring)\s+\w+\s*$", t, re.I) and len(text.words(t)) <= 5:
        fixes.append("'A conversation with X' style title — say what the episode claims or answers.")
    d = description.strip()
    dlen = len(d)
    if dlen > 4000:
        fixes.append(f"Description is {dlen} chars; Apple's limit is 4000.")
    if dlen < 150:
        fixes.append("Description under 150 chars — add the takeaways and resources for search.")
    first = d[:120]
    if first and (first.lower().startswith(("in this episode", "welcome", "today", "on this episode", "join us"))):
        fixes.append("First 120 chars open with 'In this episode…' — that's the preview text; lead with the hook.")
    ws = [w.lower() for w in text.words(d) if w.lower() not in text.STOPWORDS and len(w) > 3]
    if ws:
        top, cnt = Counter(ws).most_common(1)[0]
        if cnt / len(ws) > 0.06 and cnt >= 6:
            fixes.append(f"'{top}' appears {cnt}× — reads as keyword stuffing; Apple penalises it.")
    ts = re.findall(r"\b\d{1,2}:\d{2}\b", d)
    links = re.findall(r"https?://", d)
    score = max(0, 100 - 12 * len(fixes))
    return {
        "title": {"chars": len(t), "words": len(text.words(t)), "visible_in_apps": t[:60], "truncates": len(t) > 60},
        "description": {"chars": dlen, "preview_120": first, "timestamps": len(ts), "links": len(links)},
        "score": score,
        "fixes": fixes,
        "verdict": "Metadata passes." if not fixes else f"{len(fixes)} fix(es).",
    }


CADENCE_DAYS = {"weekly": 7, "biweekly": 14, "monthly": None, "twice_weekly": 3.5, "daily_weekdays": 1}


@AGENT.tool
def plan_release_calendar(
    first_publish: str,
    count: int,
    cadence: Literal["weekly", "biweekly", "twice_weekly", "daily_weekdays", "monthly"] = "weekly",
    publish_time: str = "05:00",
    timezone: str = "UTC",
    record_lead_days: int = 7,
    edit_lead_days: int = 3,
    second_weekday: str = "Thu",
) -> dict:
    """Generate publish dates with record-by, edit-by and notes-by deadlines for a season of episodes.

    Keeps the same weekday and hour every time, skips weekends for daily shows, and warns when
    the recording deadline is already in the past relative to the first publish date's week.

    Args:
        first_publish: Date of episode 1 as YYYY-MM-DD; its weekday becomes the show's day.
        count: Number of episodes to schedule, 1-104.
        cadence: weekly (default), biweekly, twice_weekly, daily_weekdays or monthly (same day-of-month).
        publish_time: Local time of publication as HH:MM (default 05:00, ahead of morning commutes).
        timezone: IANA timezone of the audience for the publish time (also shown in UTC).
        record_lead_days: Days before publish by which recording must be done (default 7).
        edit_lead_days: Days before publish by which the edit must be locked (default 3).
        second_weekday: For twice_weekly, the second publishing weekday (e.g. Thu).
    """
    start = dates.parse_date(first_publish)
    if not 1 <= count <= 104:
        raise ToolError("count must be 1-104")
    if not 0 <= edit_lead_days <= record_lead_days <= 60:
        raise ToolError("Need 0 ≤ edit_lead_days ≤ record_lead_days ≤ 60")
    h, m = parse_hhmm(publish_time)
    zone = tz(timezone)
    days_lookup = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    publish_dates = []
    if cadence == "weekly" or cadence == "biweekly":
        step = 7 if cadence == "weekly" else 14
        publish_dates = [start + timedelta(days=step * i) for i in range(count)]
    elif cadence == "twice_weekly":
        wd2 = days_lookup.get(second_weekday.strip().lower()[:3])
        if wd2 is None or wd2 == start.weekday():
            raise ToolError("second_weekday must be a different weekday from first_publish")
        offset = (wd2 - start.weekday()) % 7
        i = 0
        while len(publish_dates) < count:
            base = start + timedelta(days=7 * i)
            publish_dates.append(base)
            if len(publish_dates) < count:
                publish_dates.append(base + timedelta(days=offset))
            i += 1
    elif cadence == "daily_weekdays":
        d = start
        while len(publish_dates) < count:
            if d.weekday() < 5:
                publish_dates.append(d)
            d += timedelta(days=1)
    else:  # monthly
        for i in range(count):
            month = (start.month - 1 + i) % 12 + 1
            year = start.year + (start.month - 1 + i) // 12
            day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
            publish_dates.append(start.replace(year=year, month=month, day=day))
    rows = []
    from datetime import datetime, timezone as _tz

    for i, d in enumerate(publish_dates, 1):
        local = datetime(d.year, d.month, d.day, h, m, tzinfo=zone)
        rows.append({
            "episode": i,
            "publish": d.isoformat(),
            "weekday": d.strftime("%a"),
            "publish_local": local.strftime("%Y-%m-%d %H:%M %Z"),
            "publish_utc": local.astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "record_by": (d - timedelta(days=record_lead_days)).isoformat(),
            "edit_locked_by": (d - timedelta(days=edit_lead_days)).isoformat(),
            "notes_and_art_by": (d - timedelta(days=max(1, edit_lead_days - 1))).isoformat(),
        })
    warnings = []
    if start.weekday() >= 5 and cadence != "daily_weekdays":
        warnings.append("Publishing on a weekend — weekday mornings see more first-day listens for most shows.")
    if cadence == "daily_weekdays" and record_lead_days >= 7:
        warnings.append("Daily show with a 7-day record lead means batching a full week; confirm the host can.")
    return {
        "cadence": cadence,
        "episodes": count,
        "show_day": start.strftime("%A") if cadence not in ("daily_weekdays", "monthly") else None,
        "first_publish": rows[0]["publish"],
        "last_publish": rows[-1]["publish"],
        "season_span_days": (publish_dates[-1] - publish_dates[0]).days,
        "schedule": rows,
        "warnings": warnings,
        "summary": f"{count} episodes, {cadence}, {rows[0]['publish']} → {rows[-1]['publish']}; record {record_lead_days}d ahead, edit locked {edit_lead_days}d ahead.",
    }
