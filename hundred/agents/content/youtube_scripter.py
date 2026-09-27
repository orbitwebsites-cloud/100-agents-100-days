"""YouTube Scripter — scripts timed to the second, built around retention beats."""

from __future__ import annotations

import re
from typing import Literal

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="youtube-scripter",
    name="YouTube Scripter",
    category="content",
    tagline="Write YouTube scripts timed to the second, with retention beats placed where viewers drop and titles that fit the sidebar.",
    description=(
        "Scripts videos the way retention-obsessed channels do: a hook that pays off in the first 30 seconds, "
        "an open loop, pattern interrupts every 60-90 seconds, a mid-video re-hook and a payoff before the "
        "CTA — with every section timed from word count at your speaking pace, chapter timestamps computed "
        "(not guessed), and titles checked against the 100-char limit and the ~60-char sidebar truncation. "
        "Delivers the script, the beat sheet, title options, and the description block with chapters."
    ),
    triggers=[
        "write a YouTube script about X",
        "how long will this script run / time my script",
        "plan the retention beats for a 10-minute video",
        "check or improve my YouTube title",
        "build chapter timestamps for my video description",
        "turn this blog post into a video script",
    ],
    examples=[
        "Write an 8-minute script: 'Why your cold emails get ignored' for founders. Talking-head with B-roll notes.",
        "Here's my script — how long does it run at my pace (about 160 wpm) and where should the pattern interrupts go?",
        "Give me 10 title options for a video about Notion vs Obsidian and tell me which ones truncate.",
        "My sections run 0:45, 2:10, 3:05, 1:50 — build the chapter list for the description.",
    ],
    connectors=["YouTube", "Google Docs", "Notion", "Descript"],
    playbook="""
    ## Standard
    You are a script lead for channels that win on audience retention, not just clicks.
    Excellent means the viewer knows within 15 seconds why they should stay, gets a reason
    to keep watching every minute, and reaches the end feeling the title's promise was kept.
    The one metric: **average view duration as a share of length** — the hook earns the
    first 30 seconds, the beats earn the rest.

    ## Intake
    You need the topic, target length, and format (tutorial, essay, listicle, review, vlog).
    Assume a talking-head with B-roll, a conversational pace of 150 wpm, and a 30-second
    hook unless told otherwise. If the creator gave sample scripts or a pace, use it. Ask
    only when the target length or the audience is genuinely unknown — both change the
    script's shape.

    ## Procedure
    1. **Plan the beats before writing.** Call `youtube_scripter__retention_beats` with the
       target minutes and format (and the number of items for a listicle/tutorial). It
       returns a timestamped beat sheet: hook window, promise, open loop, pattern-interrupt
       positions, mid-point re-hook, CTA placement, payoff and end-screen window. Write to
       that sheet — it is the skeleton.
    2. **Write the hook (0:00-0:30).** Three moves in order: the visual/verbal cold open
       that shows the outcome or the stakes; the promise ("by the end you'll…"); the reason
       to trust you (one line). Never open with "Hey guys, welcome back" or a channel intro.
       No "in this video I'm going to" — show, don't announce.
    3. **Write the body to the beats.** One idea per section, each section opening with its
       point. At every pattern-interrupt timestamp change something: a B-roll cut, an
       on-screen text, a question to the viewer, a story, a change of location or angle.
       Mark it in the script as `[INTERRUPT: …]`. Plant the open loop early ("the third
       mistake cost me a client — that's coming up") and pay it off where the sheet says.
    4. **Place the CTA where the beats say** (after the first big payoff, ~40% in), not in
       the first minute. One CTA in the body, one at the end. Keep each under 10 seconds.
    5. **Time it.** Call `youtube_scripter__script_timing` with the script and pace. It strips
       stage directions and returns total runtime, per-section timestamps and durations,
       whether the hook fits 30 seconds, and which sections run longer than 3 minutes
       without a beat. Cut or add until the total is within ±10% of target.
    6. **Titles.** Draft 8-10; call `youtube_scripter__title_check` on the list. Rules:
       ≤ 60 chars to survive the sidebar, keyword in the first 40 chars, a number or a
       specific noun, no ALL-CAPS beyond one word, no clickbait phrases you can't pay off.
       Recommend two and say what the thumbnail must show to complement each (the title
       and thumbnail should not say the same thing).
    7. **Description and chapters.** Call `youtube_scripter__build_chapters` with the
       section titles and durations from the timing tool. It computes cumulative
       timestamps (first must be 0:00, ≥ 3 chapters, each ≥ 10 s), and checks the
       description's first 150 characters — the part shown above "Show more" — for the
       promise and the keyword. Deliver the description block ready to paste.
    8. **Deliver** the script with beat markers, the beat sheet, the timing table, the
       titles with scores and the description. If a Docs/Notion connector exists, file it.

    ## Frameworks
    - **Retention curve shape**: the steepest drop is 0-30 s (hook), then a slow decline
      with cliffs at boring transitions; a good video re-lifts at the mid-point re-hook.
    - **Hook formulas**: result-first ("This one email got 14 replies from 20 sends");
      stakes ("I lost $30k before I learned this"); contrarian ("Stop making thumbnails
      first"); question with a promise ("Why do 90% of channels stall at 1k subs? Three
      reasons, and the fix for each").
    - **Beat spacing**: interrupt every 60-90 s for talking-head; every 30-45 s for
      shorts-style fast edits; every 2-3 min for long tutorials where the screen is
      already changing.
    - **Pace presets**: calm narration 130 wpm; conversational 150; energetic 170.
    - **Title rules**: 40-60 chars ideal; numbers as digits; front-load the search term;
      brackets for format hints ("[Full Tutorial]") sparingly; no more than one power word.
    - **End**: the last 20 seconds is end-screen space — spoken CTA to the next video, no
      new information, no "thanks for watching" fade.

    ## Output format
    ```
    **Title (recommended):** <≤ 60 chars> — score N/100 · **Alt:** <title> — N/100
    **Runtime:** N:SS at 150 wpm (N words) · target N:00

    ## Beat sheet
    | Time | Beat | What happens |
    |---|---|---|

    ## Script
    ### [0:00] HOOK
    <lines> [B-ROLL: …] [ON-SCREEN: …]
    ### [0:32] <Section title>
    …
    [INTERRUPT: …] where the beat sheet says
    ### [N:SS] CLOSE + END SCREEN

    ## Description (paste-ready)
    <first 150 chars = promise + keyword>
    <chapters: 0:00 …>
    <links, CTA>

    **Titles tried:** <list with scores and truncation flags>
    ```

    ## Anti-patterns
    - "Hey guys, welcome back to the channel" — 5 seconds of nothing at the moment of maximum drop-off.
    - Announcing the video instead of starting it ("In this video I'll…").
    - Subscribe ask before any value has been delivered.
    - Sections that summarise the previous one; every restatement is a cliff.
    - Titles the thumbnail repeats word for word.
    - Guessing runtime from page count; guessing chapter timestamps by adding in your head.
    - Ending with "so yeah, that's it" — end on the payoff and the next-video CTA.
    """,
)

SECTION_LINE = re.compile(r"^\s*(?:#{1,6}\s+(?P<h>.+?)\s*#*|\[(?P<b>[A-Z][A-Z0-9 :/_-]{1,60})\]|(?P<caps>[A-Z][A-Z0-9 &/_-]{2,50}):?)\s*$")
STAGE = re.compile(r"\[[^\]\n]{0,300}\]|\((?:b-?roll|on[- ]screen|cut|sfx|music|graphic|visual|text|insert|pause|beat)[^)\n]{0,300}\)", re.I)


def _split_script(script: str) -> list[dict]:
    secs: list[dict] = []
    cur = {"title": "(untitled)", "lines": []}
    for line in script.splitlines():
        m = SECTION_LINE.match(line)
        if m and (m.group("h") or m.group("b") or m.group("caps")):
            title = (m.group("h") or m.group("b") or m.group("caps")).strip().rstrip(":")
            if m.group("b") and re.match(r"^(B-?ROLL|ON[- ]SCREEN|CUT|SFX|MUSIC|GRAPHIC|VISUAL|TEXT|INSERT|PAUSE|BEAT|INTERRUPT)\b", title, re.I):
                cur["lines"].append(line)
                continue
            if cur["lines"] or cur["title"] != "(untitled)":
                secs.append(cur)
            cur = {"title": title, "lines": []}
        else:
            cur["lines"].append(line)
    secs.append(cur)
    out = []
    for s in secs:
        body = "\n".join(s["lines"])
        spoken = text.words(STAGE.sub(" ", c.strip_markdown(body)))
        if not spoken and s["title"] == "(untitled)":
            continue
        out.append({"title": s["title"], "words": len(spoken), "directions": len(STAGE.findall(body))})
    return out


@AGENT.tool
def script_timing(script: str, wpm: int = 150, target_minutes: float = 0.0) -> dict:
    """Time a script: spoken words (stage directions stripped), total runtime, per-section start timestamps and durations, hook length, and sections that run too long without a beat.

    Call after drafting and after every cut. Sections are markdown headings, [BRACKET]
    lines or ALL-CAPS lines; [B-ROLL: …] and (on-screen …) notes are not counted as speech.

    Args:
        script: The full script text.
        wpm: Speaking pace in words per minute (130 calm, 150 conversational, 170 energetic).
        target_minutes: Target runtime, to compute how many words to cut or add (0 = no target).
    """
    c.guard(script, "Script")
    if not 80 <= wpm <= 250:
        raise ToolError("wpm must be between 80 and 250.")
    if target_minutes < 0 or target_minutes > 240:
        raise ToolError("target_minutes must be 0-240.")
    secs = _split_script(script)
    total_words = sum(s["words"] for s in secs)
    if total_words < 10:
        raise ToolError("Fewer than 10 spoken words found — is the whole script stage directions?")
    total_sec = total_words / wpm * 60
    rows = []
    t = 0.0
    flags: list[str] = []
    for i, s in enumerate(secs):
        dur = s["words"] / wpm * 60
        rows.append({"section": s["title"][:60], "start": c.mmss(t), "duration": c.mmss(dur), "seconds": round(dur), "words": s["words"], "share_pct": c.pct(s["words"], total_words), "directions": s["directions"]})
        if dur > 180 and s["directions"] == 0:
            flags.append(f"'{s['title'][:40]}' runs {c.mmss(dur)} with no B-roll/interrupt marker — add a beat every 60-90 s.")
        t += dur
    hook_words = secs[0]["words"] if secs else 0
    hook_sec = hook_words / wpm * 60
    if hook_sec > 35:
        flags.append(f"Hook/first section runs {c.mmss(hook_sec)} — get the promise inside 30 s.")
    all_spoken = " ".join(text.words(STAGE.sub(" ", c.strip_markdown(script)))[:80])
    if re.search(r"\b(hey guys|welcome back|what's up guys|welcome to (my|the) channel|in this video i)\b", all_spoken, re.I):
        flags.append("Opens with a channel greeting/announcement — cut straight to the cold open.")
    delta = None
    if target_minutes:
        target_words = int(target_minutes * wpm)
        delta = total_words - target_words
        tol = target_words * 0.10
        if delta > tol:
            flags.append(f"{c.mmss(total_sec)} vs {c.mmss(target_minutes * 60)} target — cut ~{delta} words.")
        elif delta < -tol:
            flags.append(f"{c.mmss(total_sec)} vs {c.mmss(target_minutes * 60)} target — add ~{-delta} words or slow the pace.")
    return {
        "spoken_words": total_words,
        "wpm": wpm,
        "runtime": c.mmss(total_sec),
        "runtime_seconds": round(total_sec),
        "runtime_minutes": round(total_sec / 60, 1),
        "sections": rows,
        "hook_seconds": round(hook_sec),
        "hook_fits_30s": hook_sec <= 30,
        "target_minutes": target_minutes or None,
        "words_vs_target": delta,
        "flags": flags,
        "verdict": f"{c.mmss(total_sec)} at {wpm} wpm ({total_words} spoken words)." + (" On target." if target_minutes and not delta is None and abs(delta) <= target_minutes * wpm * 0.1 else ""),
    }


@AGENT.tool
def retention_beats(target_minutes: float, format: Literal["tutorial", "essay", "listicle", "review", "vlog", "interview"] = "essay", items: int = 0, interrupt_every_seconds: int = 75) -> dict:
    """Build a timestamped retention beat sheet for a video: hook window, promise, open loop, pattern interrupts, mid-point re-hook, CTA placement, payoff, end screen.

    Call before writing. Returns the timeline to write against; for listicles/tutorials it
    also allocates seconds per item/step.

    Args:
        target_minutes: Planned runtime in minutes (0.5-180).
        format: tutorial, essay, listicle, review, vlog or interview — changes the beat mix.
        items: Number of list items or steps (listicle/tutorial); 0 = not applicable.
        interrupt_every_seconds: Spacing of pattern interrupts (60-90 for talking-head; 30-45 for fast edits; 120-180 for screen tutorials).
    """
    if not 0.5 <= target_minutes <= 180:
        raise ToolError("target_minutes must be between 0.5 and 180.")
    if not 20 <= interrupt_every_seconds <= 300:
        raise ToolError("interrupt_every_seconds must be 20-300.")
    if items < 0 or items > 50:
        raise ToolError("items must be 0-50.")
    total = target_minutes * 60
    short = total <= 90
    hook_end = min(30, max(5, round(total * (0.12 if short else 0.05))))
    beats: list[dict] = [
        {"at": c.mmss(0), "beat": "Cold open", "do": "Show the outcome or the stakes in the first 3-5 s. No greeting, no logo."},
        {"at": c.mmss(hook_end * 0.4), "beat": "Promise", "do": "'By the end you'll…' — one sentence, specific."},
        {"at": c.mmss(hook_end * 0.75), "beat": "Credibility", "do": "One line on why you: a number, a result, a role."},
        {"at": c.mmss(hook_end), "beat": "Open loop", "do": "Plant the thing you'll pay off late ('the third one cost me a client — coming up')."},
    ]
    body_start = hook_end
    end_screen = 20 if total >= 120 else 5
    body_end = total - end_screen - (25 if total >= 240 else 10)
    cta_at = body_start + (body_end - body_start) * 0.4
    mid = body_start + (body_end - body_start) * 0.5
    payoff_at = body_start + (body_end - body_start) * 0.85
    if items and format in ("listicle", "tutorial", "review"):
        per = (body_end - body_start) / items
        for i in range(items):
            label = "Step" if format == "tutorial" else "Item" if format == "listicle" else "Criterion"
            beats.append({"at": c.mmss(body_start + per * i), "beat": f"{label} {i + 1}", "do": f"Point first, then proof. ~{c.mmss(per)} each." + (" Best-known item here to anchor the list." if i == 0 else " Save the strongest item for here." if i == items - 1 else "")})
    else:
        n_sections = max(2, min(8, round((body_end - body_start) / 120)))
        per = (body_end - body_start) / n_sections
        for i in range(n_sections):
            beats.append({"at": c.mmss(body_start + per * i), "beat": f"Section {i + 1}", "do": f"One idea, opens with its point. ~{c.mmss(per)}."})
    t = body_start + interrupt_every_seconds
    n_int = 0
    while t < body_end - 15:
        n_int += 1
        beats.append({"at": c.mmss(t), "beat": f"Pattern interrupt {n_int}", "do": "Change something: B-roll cut, on-screen text, a question, a story, a new angle."})
        t += interrupt_every_seconds
    if total >= 180:
        beats.append({"at": c.mmss(cta_at), "beat": "CTA (in-body)", "do": "After the first big payoff: ≤ 10 s subscribe/like ask, tied to the value just delivered."})
        beats.append({"at": c.mmss(mid), "beat": "Mid-point re-hook", "do": "Re-state what's still coming; tease the open loop's payoff."})
    beats.append({"at": c.mmss(payoff_at), "beat": "Open-loop payoff", "do": "Deliver what you planted at the hook. The strongest material lives here."})
    beats.append({"at": c.mmss(body_end), "beat": "Close", "do": "One-line recap of the promise kept. No 'so yeah'."})
    beats.append({"at": c.mmss(total - end_screen), "beat": "End screen", "do": f"Last {end_screen} s: spoken CTA to the next video; no new information."})
    beats.sort(key=lambda b: [int(x) for x in b["at"].split(":")])
    words_at_150 = int(total / 60 * 150)
    return {
        "target": c.mmss(total),
        "format": format,
        "hook_window": f"0:00-{c.mmss(hook_end)}",
        "body_window": f"{c.mmss(body_start)}-{c.mmss(body_end)}",
        "interrupts": n_int,
        "interrupt_spacing_seconds": interrupt_every_seconds,
        "cta_at": c.mmss(cta_at) if total >= 180 else "end only (short video)",
        "beats": beats,
        "script_words_at_150wpm": words_at_150,
        "summary": f"{c.mmss(total)} {format}: hook by {c.mmss(hook_end)}, {n_int} interrupts every {interrupt_every_seconds}s, payoff at {c.mmss(payoff_at)}, ~{words_at_150} words at 150 wpm.",
    }


CLICKBAIT = ["you won't believe", "gone wrong", "shocking", "insane", "mind-blowing", "mind blowing", "must watch", "must see", "will change your life", "the truth about", "exposed", "destroyed", "breaks the internet", "not clickbait", "(not clickbait)", "gone sexual", "3am"]
POWER = ["secret", "mistake", "mistakes", "wrong", "stop", "never", "why", "how", "truth", "nobody", "actually", "honest", "real", "best", "worst", "fastest", "easiest", "simple", "ultimate", "complete", "proven", "brutal"]


def _title_score(t: str, keyword: str) -> dict:
    n = len(t)
    score = 55
    reasons = []
    if n > 100:
        score -= 40
        reasons.append(f"-40 {n} chars: over YouTube's 100-char limit")
    elif n > 70:
        score -= 15
        reasons.append(f"-15 {n} chars: truncates in the sidebar and on mobile")
    elif n > 60:
        score -= 5
        reasons.append(f"-5 {n} chars: may truncate in suggested videos")
    elif 40 <= n <= 60:
        score += 10
        reasons.append(f"+10 {n} chars: fits everywhere")
    elif n < 20:
        score -= 8
        reasons.append(f"-8 {n} chars: too short to carry a promise")
    if re.search(r"\d", t):
        score += 10
        reasons.append("+10 contains a number")
    caps = [w for w in text.words(t) if len(w) > 1 and w.isupper() and not w.isdigit()]
    if len(caps) > 1:
        score -= 6 * min(3, len(caps) - 1)
        reasons.append(f"-{6 * min(3, len(caps) - 1)} {len(caps)} ALL-CAPS words (one is the max)")
    cb = c.find_phrases(t, CLICKBAIT)
    if cb:
        score -= 12
        reasons.append(f"-12 clickbait phrase ({cb[0]['phrase']}) — only if the video pays it off")
    pw = c.find_phrases(t, POWER)
    if pw:
        score += min(8, 4 * len(pw))
        reasons.append(f"+{min(8, 4 * len(pw))} curiosity/power word ({pw[0]['phrase']})")
    if keyword:
        pos = t.lower().find(keyword.lower())
        if pos < 0:
            score -= 10
            reasons.append("-10 keyword missing")
        elif pos <= 40:
            score += 8
            reasons.append("+8 keyword in the first 40 chars")
        else:
            score += 2
            reasons.append("+2 keyword present but late")
    if c.count_emoji(t) > 1:
        score -= 5
        reasons.append("-5 more than one emoji")
    if t.count("!") > 1 or "!!" in t:
        score -= 5
        reasons.append("-5 stacked exclamation marks")
    if re.search(r"\b(you|your)\b", t, re.I):
        score += 4
        reasons.append("+4 speaks to the viewer")
    if len(set(w.lower() for w in text.words(t))) < len(text.words(t)) - 1:
        score -= 3
        reasons.append("-3 repeated words")
    if re.search(r"\[[^\]]+\]|\([^)]+\)", t):
        score += 2
        reasons.append("+2 format hint in brackets")
    return {"title": t, "chars": n, "fits_100": n <= 100, "sidebar_safe": n <= 60, "score": max(0, min(100, score)), "reasons": reasons}


@AGENT.tool
def title_check(titles: list[str], keyword: str = "") -> dict:
    """Score and rank YouTube title candidates: 100-char limit, ~60-char sidebar truncation, keyword position, numbers, caps, clickbait and power words.

    Call with 3-10 candidates; recommend the top two. Also returns each title's truncated
    preview so you can see what a viewer sees in suggested videos.

    Args:
        titles: Candidate titles (1-20).
        keyword: The main search term the title should front-load (optional).
    """
    if not isinstance(titles, list) or not titles:
        raise ToolError("titles must be a non-empty list.")
    if len(titles) > 20:
        raise ToolError("Max 20 titles per call.")
    cleaned = [str(t or "").strip() for t in titles]
    if any(not t for t in cleaned):
        raise ToolError("Every title must be non-empty.")
    scored = [_title_score(t, keyword.strip()) for t in cleaned]
    for s in scored:
        s["sidebar_preview"] = s["title"] if s["chars"] <= 60 else s["title"][:57].rstrip() + "…"
    ranked = sorted(scored, key=lambda s: -s["score"])
    return {
        "ranked": ranked,
        "recommended": ranked[0]["title"],
        "runner_up": ranked[1]["title"] if len(ranked) > 1 else None,
        "over_limit": [s["title"] for s in scored if not s["fits_100"]],
        "truncating": [s["title"] for s in scored if s["fits_100"] and not s["sidebar_safe"]],
        "verdict": f"Top: '{ranked[0]['title']}' ({ranked[0]['score']}/100, {ranked[0]['chars']} chars).",
    }


def _parse_duration(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").strip()
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", s)
    if m:
        h = int(m.group(1) or 0)
        return h * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.fullmatch(r"(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?", s, re.I)
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    raise ToolError(f"Can't read duration {v!r} — use seconds (95), m:ss (1:35) or '1m 35s'.")


@AGENT.tool
def build_chapters(chapters: list[dict], description: str = "", keyword: str = "") -> dict:
    """Compute cumulative chapter timestamps from section durations and validate YouTube's rules (first at 0:00, ≥ 3 chapters, each ≥ 10 s, ascending); check the description's above-the-fold 150 chars.

    Call with the sections from script_timing (or your own titles + durations). Returns the
    paste-ready chapter block and description flags.

    Args:
        chapters: List of {"title": str, "duration": seconds | "m:ss"} in order. Or {"title", "start": "m:ss"} if you already have start times.
        description: The video description text (optional) — checked for the 5,000-char limit and the first 150 chars.
        keyword: Main search term to look for in the first 150 chars of the description (optional).
    """
    if not isinstance(chapters, list) or not chapters:
        raise ToolError("chapters must be a non-empty list of {title, duration} objects.")
    if len(chapters) > 100:
        raise ToolError("Max 100 chapters.")
    rows = []
    t = 0.0
    flags: list[str] = []
    for i, ch in enumerate(chapters, 1):
        if not isinstance(ch, dict) or not str(ch.get("title", "")).strip():
            raise ToolError(f"Chapter {i} needs a non-empty title.")
        title = str(ch["title"]).strip()
        if "start" in ch and ch.get("start") not in (None, ""):
            start = _parse_duration(ch["start"])
            if rows and start <= rows[-1]["seconds"]:
                flags.append(f"Chapter {i} '{title[:30]}' starts at {c.mmss(start)}, not after the previous one.")
            t = start
        elif "duration" in ch and ch.get("duration") not in (None, ""):
            start = t
            t = t + _parse_duration(ch["duration"])
        else:
            raise ToolError(f"Chapter {i} needs a 'duration' or a 'start'.")
        rows.append({"n": i, "timestamp": c.mmss(start), "seconds": round(start), "title": title})
    if rows[0]["seconds"] != 0:
        flags.append("First chapter must start at 0:00 or YouTube ignores all chapters.")
    if len(rows) < 3:
        flags.append(f"Only {len(rows)} chapters — YouTube needs at least 3.")
    for a, b in zip(rows, rows[1:]):
        if b["seconds"] - a["seconds"] < 10:
            flags.append(f"Chapter '{a['title'][:30]}' is under 10 s — YouTube requires ≥ 10 s per chapter.")
    total = t if "duration" in chapters[-1] else None
    if len(rows) > 20:
        flags.append(f"{len(rows)} chapters — over ~20 the list becomes noise; merge.")
    block = "\n".join(f"{r['timestamp']} {r['title']}" for r in rows)
    desc_report = None
    if description:
        d = description.strip()
        fold = d[:150]
        dflags = []
        if len(d) > 5000:
            dflags.append(f"{len(d)} chars — over the 5,000 limit.")
        if keyword and keyword.lower() not in fold.lower():
            dflags.append("Keyword not in the first 150 chars (what shows above 'Show more').")
        if re.match(r"^\s*(https?://|subscribe|follow me|in this video)", d, re.I):
            dflags.append("Description opens with a link/CTA/'In this video' — open with the promise.")
        if len(fold) < 100:
            dflags.append("Fewer than 100 chars above the fold — use the space.")
        if "0:00" not in d and block not in d:
            dflags.append("Chapter block not in the description yet — paste it in.")
        desc_report = {"chars": len(d), "fits_5000": len(d) <= 5000, "above_fold": fold, "flags": dflags}
        flags.extend(dflags)
    return {
        "chapters": rows,
        "chapter_block": block,
        "count": len(rows),
        "total_runtime": c.mmss(total) if total is not None else None,
        "description": desc_report,
        "flags": flags,
        "valid": not any(f.startswith(("First chapter", "Only", "Chapter '")) for f in flags),
        "verdict": "Chapters valid." if not flags else f"{len(flags)} issue(s) with chapters/description.",
    }
