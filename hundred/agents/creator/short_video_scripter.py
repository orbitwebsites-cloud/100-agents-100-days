"""Short Video Scripter — TikTok / Reels / Shorts scripts timed to the second with hooks that stop the scroll."""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal

from ...core import Agent, ToolError
from ...lib import text
from ._common import FILLER_RE, fmt_timestamp

AGENT = Agent(
    slug="short-video-scripter",
    name="Short Video Scripter",
    category="creator",
    tagline="Scripts for TikTok, Reels and Shorts timed to the second, with a hook that survives the first 2 seconds.",
    description=(
        "Writes and fixes short-form video scripts the way a top short-form editor does: a scored hook "
        "in the first 1-3 seconds, a beat sheet with a word budget per beat, spoken-word timing at a "
        "realistic pace so a '30-second' script is actually 30 seconds, a lint pass that strips "
        "throat-clearing and fillers, and platform length rules for TikTok, Instagram Reels and "
        "YouTube Shorts. Every draft comes back with timestamps, on-screen text and a retention plan."
    ),
    triggers=[
        "write a TikTok / Reel / Short script",
        "give me a hook for this video",
        "how long will this script take to say",
        "make this script tighter / more retentive",
        "turn this idea into a 30-second video",
        "beat sheet for a short video",
    ],
    examples=[
        "Write a 30-second TikTok about why most people's morning routine is backwards. I'm a sleep coach.",
        "Here's my script — it feels slow. Time it and tell me what to cut.",
        "Give me 5 hooks for a Reel on the 3 mistakes first-time landlords make.",
    ],
    connectors=["Notion", "Google Docs", "CapCut", "YouTube", "TikTok"],
    playbook="""
    ## Standard
    You are a short-form producer whose videos are judged by one number: **3-second hold rate**
    (viewers still watching at 3 s) and, behind it, average watch time as a % of length.
    A script is excellent when the first line makes stopping cheaper than scrolling, every
    sentence earns the next one, and the runtime matches the promise. Aim for ≥ 60% of
    viewers past 3 s and ≥ 50% average view duration on sub-45-second videos.

    ## Intake
    You need the topic, the creator's niche/voice, the platform and the target length.
    If length is missing assume 30 s; if platform is missing assume it will be cross-posted
    (so respect the strictest rule: Reels/Shorts style, 9:16, safe-zone captions). State
    assumptions in one line and proceed. Ask only if the topic itself is unclear.

    ## Procedure
    1. **Plan the beats first.** Call `short_video_scripter__plan_beats` with the target
       duration, the format (talking_head, tutorial, listicle, story, product, reaction) and
       pace. It returns time-coded beats with a word budget for each. Write into the budget;
       do not write first and hope it fits.
    2. **Write 3-5 candidate hooks** (≤ 12 words each) using distinct hook types (see
       Frameworks). Call `short_video_scripter__score_hook` on each and keep the top two. A
       hook below 60 is not shown to the user; rewrite it.
    3. **Draft the script** as spoken lines, one sentence per line. Mark on-screen text as
       `[TEXT: …]` and cutaways as `[B-ROLL: …]` on their own lines — they are not spoken.
       The first spoken line is the hook verbatim. Deliver the payoff before the last 20% of
       the runtime; the CTA is one line, never a paragraph.
    4. **Time it.** Call `short_video_scripter__time_script` with the script, pace and
       platform. It counts only spoken words — numbers as they are said aloud ("$250,000" is
       five words, "0.01%" is five) — gives cumulative timestamps per line, the hook length in
       seconds, and checks the platform limit. If the hook exceeds 3 s or the
       total is more than 10% over target, cut — never speed the delivery to fix a script.
    5. **Lint it.** Call `short_video_scripter__lint_script`. It flags fillers, warm-up
       intros ("hey guys", "in this video"), sentences too long to say in one breath, a
       missing or bloated CTA, on-screen text over 8 words, and repeated words. Apply every
       fix that does not change the meaning, then re-time if you cut more than 10 words.
    6. **Deliver** in the output format: timed script, on-screen text plan, cover/caption
       suggestion, and the two alternate hooks so the creator can A/B test.

    ## Frameworks
    - **Hook types that work** (pick different types for the alternates): the contrarian
      claim ("Your morning routine is backwards"), the specific number ("3 landlord mistakes
      that cost me $11k"), the direct-address question ("Why does your back hurt at 3 pm?"),
      the outcome-first ("I doubled my sleep score doing this"), the pattern interrupt
      (start mid-action), and the "stop doing X". Avoid generic curiosity bait with no payoff.
    - **Re-hook at 3-5 s**: after the hook, add one line that tells them why staying is
      worth it ("the third one is the one everyone gets wrong").
    - **Pace:** conversational speech is ~2.0-2.5 words/s; energetic short-form runs 2.7-3.2.
      Default to 2.5 and let the creator's real pace override once measured.
    - **Length:** default to the shortest runtime that delivers the payoff. Platform caps —
      Shorts 180 s, Reels 180 s, TikTok 600 s — are ceilings, not targets. Most non-story
      content performs best under 45 s; stories and tutorials earn 60-90 s.
    - **On-screen text:** ≤ 8 words per card, mirrors the spoken hook in the first frame,
      stays inside the 9:16 safe zone (avoid bottom 20% and right edge where UI overlays sit).
    - **Loop:** for sub-20 s videos, write the last line so it flows into the first (loop
      replay lifts watch time above 100%).

    ## Output format
    ```
    # <Working title> — <platform> · target <N>s · actual <N.N>s at <pace>
    **Hook (score NN):** <hook line>
    **Alternates:** <hook 2 (score)> · <hook 3 (score)>

    | Time | Spoken line | On-screen text / B-roll |
    |---|---|---|
    | 0:00 | <hook> | [TEXT: …] |
    | 0:03 | <re-hook> | |
    | … | | |

    **CTA (0:NN):** <one line>
    **Cover text:** <≤ 6 words>   **Caption:** <first line = hook restated, then 1-3 hashtags>
    **Retention notes:** <where the payoff lands, where to cut on screen, loop point if any>
    ```

    ## Anti-patterns
    - Opening with "Hey guys", "Welcome back", "In this video", or your name. The hook is line one.
    - Explaining the context before the hook. Context comes after they've decided to stay.
    - Writing a 30 s script that is 68 words of spoken text plus 40 words of "and also".
      Time it; the tool exists because everyone underestimates by 30-50%.
    - Three CTAs ("like, follow, comment, share, link in bio"). One ask, tied to the content.
    - Sentences over 18 words. They cannot be said in one breath and they read as a lecture.
    - Saving the payoff for the end "to keep them watching". They leave; deliver, then extend.
    """,
)

DIRECTION_RE = re.compile(r"^\s*[\[(](?:TEXT|B-?ROLL|ON[- ]SCREEN|CUT|SFX|MUSIC|VISUAL|NOTE|CAPTION)\b[^\]\)]*[\])]\s*$", re.I)
TEXT_CARD_RE = re.compile(r"[\[(]\s*(?:TEXT|ON[- ]SCREEN|CAPTION)\s*:\s*([^\]\)]+)[\])]", re.I)
INLINE_DIRECTION_RE = re.compile(r"[\[(][^\])]{0,200}[\])]")
PACE_WPS = {"slow": 2.0, "natural": 2.5, "fast": 3.0}
PLATFORM_MAX = {"tiktok": 600, "reels": 180, "instagram": 180, "shorts": 180, "youtube_shorts": 180, "youtube": 180, "any": 180, "linkedin": 600, "x": 140}
LEAD_FILLER_RE = re.compile(r"^\s*(so|okay|ok|alright|well|now|anyway)\b,?\s+", re.I)
INTRO_RE = re.compile(r"^\s*(hey|hi|hello|what's up|welcome|so today|today i|in this video|my name is|i'm going to (show|tell))", re.I)
CTA_RE = re.compile(r"\b(follow|subscribe|comment|like this|share this|save this|link in (my )?bio|dm me|sign up|download|part (2|two)|tag someone)\b", re.I)


# Numbers are read aloud as several words ("$250,000" = "two hundred fifty thousand dollars"),
# so a script full of figures runs longer than its written word count suggests.
NUM_RE = re.compile(r"([$£€])?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?(?:%|percent\b)|(?:k|K|m|M|bn|x)\b)?")


def _int_words(n: int) -> int:
    """How many words it takes to say a whole number in English (twenty-one = 2)."""
    if n < 21:
        return 1
    if n < 100:
        return 1 if n % 10 == 0 else 2
    if n < 1000:
        return 2 + (_int_words(n % 100) if n % 100 else 0)
    for scale in (10**12, 10**9, 10**6, 10**3):
        if n >= scale:
            return _int_words(n // scale) + 1 + (_int_words(n % scale) if n % scale else 0)
    return 1


def _number_words(m: re.Match) -> int:
    cur, whole, dec, suffix = m.group(1), m.group(2), m.group(3), (m.group(4) or "").strip()
    n = int(whole.replace(",", ""))
    if not cur and not dec and not suffix and "," not in whole and 1100 <= n <= 2099 and len(whole) == 4:
        count = 3 if 2000 <= n <= 2009 else _int_words(n // 100) + (_int_words(n % 100) if n % 100 else 1)  # years
    else:
        count = _int_words(n)
    if dec:
        count += 1 + len(dec) - 1  # "point" + one word per digit
    if suffix and suffix.lower() != "percent":
        count += 1  # percent / thousand / million / billion / times
    if cur:
        count += 1  # dollars / pounds / euros
    return count


def spoken_word_count(line: str) -> int:
    """Words as they will be spoken: numbers, currency and % expanded; everything else as written."""
    extra = sum(_number_words(m) for m in NUM_RE.finditer(line))
    return len(text.words(NUM_RE.sub(" ", line))) + extra


def _spoken_lines(script: str) -> tuple[list[str], list[str]]:
    spoken, directions = [], []
    for raw in script.splitlines():
        line = raw.strip()
        if not line:
            continue
        if DIRECTION_RE.match(line):
            directions.append(line)
            continue
        cleaned = INLINE_DIRECTION_RE.sub("", line).strip()
        if cleaned:
            spoken.append(cleaned)
        for m in INLINE_DIRECTION_RE.findall(line):
            directions.append(m)
    return spoken, directions


@AGENT.tool
def time_script(
    script: str,
    pace: Literal["slow", "natural", "fast"] = "natural",
    platform: str = "any",
    target_seconds: float = 0,
) -> dict:
    """Time a short-video script line by line at a realistic speaking pace and check platform limits.

    Counts only spoken words (ignores [TEXT: …] and [B-ROLL: …] directions) and counts numbers as
    they are said aloud ("$250,000" = 5 words, "4%" = 2), returns cumulative timestamps, hook
    duration, and whether the runtime fits the target and the platform maximum.

    Args:
        script: The script, one spoken line per line; directions in [brackets] are not timed.
        pace: slow (2.0 words/s), natural (2.5 words/s, default), fast (3.0 words/s).
        platform: tiktok, reels, shorts, youtube, linkedin, x or any (default any = 180 s cap).
        target_seconds: Intended runtime in seconds; 0 to skip the target check.
    """
    if not script.strip():
        raise ToolError("Script is empty.")
    if len(script) > 60_000:
        raise ToolError("Script too long for a short video (60k chars max).")
    if target_seconds < 0 or target_seconds > 3600:
        raise ToolError("target_seconds must be between 0 and 3600")
    key = platform.strip().lower().replace(" ", "_")
    if key not in PLATFORM_MAX:
        raise ToolError(f"Unknown platform {platform!r}. Use one of: {', '.join(PLATFORM_MAX)}.")
    wps = PACE_WPS[pace]
    spoken, directions = _spoken_lines(script)
    if not spoken:
        raise ToolError("No spoken lines found — only directions in brackets.")
    rows, t = [], 0.0
    written_total = 0
    for i, line in enumerate(spoken, 1):
        n = spoken_word_count(line)
        written_total += len(text.words(line))
        secs = n / wps
        rows.append({"n": i, "starts_at": fmt_timestamp(t), "start_s": round(t, 1), "words": n, "seconds": round(secs, 1), "line": line[:300]})
        t += secs
    total_words = sum(r["words"] for r in rows)
    total = total_words / wps
    hook_words = rows[0]["words"]
    hook_secs = hook_words / wps
    cap = PLATFORM_MAX[key]
    flags = []
    if hook_secs > 3:
        flags.append(f"Hook is {hook_secs:.1f}s ({hook_words} words); cut to ≤ 7-8 words so it lands under 3s.")
    if total > cap:
        flags.append(f"Runtime {total:.0f}s exceeds the {cap}s cap for {key}.")
    if target_seconds:
        delta = total - target_seconds
        if delta > 0.1 * target_seconds:
            flags.append(f"{delta:.0f}s over target — cut about {int(delta * wps)} words.")
        elif delta < -0.25 * target_seconds:
            flags.append(f"{-delta:.0f}s under target — fine if the payoff is complete; do not pad.")
    payoff_zone = int(0.8 * len(rows))
    cta_lines = [r["n"] for r in rows if CTA_RE.search(r["line"])]
    if cta_lines and cta_lines[0] <= max(1, payoff_zone // 2):
        flags.append(f"CTA appears at line {cta_lines[0]} — before the payoff. Move it to the last 20%.")
    return {
        "pace_words_per_second": wps,
        "spoken_words": total_words,
        "written_words": written_total,
        "spoken_lines": len(rows),
        "total_seconds": round(total, 1),
        "total_timestamp": fmt_timestamp(total),
        "hook_seconds": round(hook_secs, 1),
        "hook_words": hook_words,
        "platform_cap_seconds": cap,
        "fits_platform": total <= cap,
        "target_seconds": target_seconds or None,
        "words_for_target": int(target_seconds * wps) if target_seconds else None,
        "lines": rows,
        "directions": directions[:100],
        "flags": flags,
        "verdict": f"{total:.0f}s of speech at {pace} pace" + (f" (target {target_seconds:g}s)" if target_seconds else "") + ("; " + " ".join(flags) if flags else "; timing is clean."),
    }


HOOK_PATTERNS = [
    (re.compile(r"^\s*(stop|never|don'?t|quit)\b", re.I), "command / pattern interrupt", 18),
    (re.compile(r"\b\d+([.,]\d+)?\s*(%|k|x|\$|£|€|days?|hours?|minutes?|seconds?|weeks?|months?|years?|mistakes?|ways?|things?|reasons?|steps?|rules?|signs?)\b|^\s*\d+\b|[\$£€]\d", re.I), "specific number", 18),
    (re.compile(r"\?\s*$"), "direct question", 12),
    (re.compile(r"\b(you|your|you're|you've)\b", re.I), "second person", 14),
    (re.compile(r"\b(nobody|no one|everyone|most people|wrong|backwards|myth|lie|secret|actually|truth|mistakes?|worst|instead|losing|lose|losses|costing|wasting|broke|never)\b", re.I), "contrarian / tension word", 16),
    (re.compile(r"\b(i|we) (did|tried|tested|spent|lost|made|doubled|quit|built|failed)\b", re.I), "outcome-first / proof", 14),
    (re.compile(r"\b(how|why|what)\b", re.I), "curiosity frame", 8),
]
WEAK_HOOK_RE = re.compile(r"^\s*(hey|hi|hello|welcome|so,?\s|today|in this video|my name|i'?m going to|let'?s talk about|i want to talk)", re.I)
VAGUE_RE = re.compile(r"\b(some|things|stuff|a lot|very|really|amazing|awesome|incredible|game.?changer|mind.?blowing)\b", re.I)


@AGENT.tool
def score_hook(hook: str) -> dict:
    """Score a short-video opening line 0-100 on stop-the-scroll criteria and return specific fixes.

    Rewards brevity (≤ 12 words), specificity (numbers), second person, tension/contrarian framing
    and a clear promise; penalises greetings, throat-clearing, vagueness and hype adjectives.

    Args:
        hook: The first spoken line of the video (one sentence).
    """
    if not hook.strip():
        raise ToolError("Hook is empty.")
    if len(hook) > 500:
        raise ToolError("A hook is one line; this is over 500 chars.")
    n = spoken_word_count(hook)
    score = 30
    reasons, fixes = [], []
    if n <= 8:
        score += 20
        reasons.append(f"{n} words — lands under 3s")
    elif n <= 12:
        score += 12
        reasons.append(f"{n} words — OK, under ~5s")
    else:
        score -= min(20, (n - 12) * 3)
        fixes.append(f"{n} words is too long for a hook; cut to ≤ 8-12.")
    matched = []
    for rx, label, pts in HOOK_PATTERNS:
        if rx.search(hook):
            matched.append(label)
            score += pts
    if WEAK_HOOK_RE.search(hook):
        score -= 30
        fixes.append("Starts with a greeting/warm-up — delete everything before the actual claim.")
    vague = VAGUE_RE.findall(hook)
    if vague:
        score -= 6 * min(3, len(vague))
        fixes.append(f"Vague/hype words ({', '.join(sorted(set(v.lower() for v in vague)))}) — replace with a specific noun or number.")
    if not any(l in matched for l in ("specific number", "contrarian / tension word", "outcome-first / proof", "direct question", "command / pattern interrupt")):
        fixes.append("No tension, number, question or proof — the viewer has no reason to stay. Add one.")
    if "second person" not in matched and "outcome-first / proof" not in matched:
        fixes.append("Not addressed to the viewer — add 'you'/'your' or make it a first-person result.")
    if hook.strip().endswith(("...", "…")):
        score -= 5
        fixes.append("Trailing ellipsis reads as clickbait; end on the claim.")
    score = max(0, min(100, score))
    grade = "strong" if score >= 75 else "usable" if score >= 60 else "rewrite"
    return {
        "hook": hook.strip(),
        "words": n,
        "seconds_at_natural_pace": round(n / 2.5, 1),
        "score": score,
        "grade": grade,
        "hook_types_detected": matched,
        "strengths": reasons + [f"uses {m}" for m in matched],
        "fixes": fixes,
        "verdict": f"{score}/100 — {grade}." + (" " + fixes[0] if fixes else ""),
    }


BEAT_TEMPLATES: dict[str, list[tuple[str, float, str]]] = {
    # (beat name, share of runtime, purpose)
    "talking_head": [("Hook", 0.10, "One claim that makes scrolling cost something"), ("Re-hook / stakes", 0.10, "Why this matters to them, why stay"), ("Point 1", 0.22, "First idea with a concrete example"), ("Point 2", 0.22, "Second idea, escalate specificity"), ("Point 3 / twist", 0.22, "The one they didn't expect"), ("Payoff + CTA", 0.14, "Land the takeaway, one ask")],
    "tutorial": [("Hook (result first)", 0.10, "Show the finished result"), ("Setup", 0.10, "What you need, in one line"), ("Step 1", 0.20, "Do it on screen, narrate the why"), ("Step 2", 0.20, "The step people get wrong"), ("Step 3", 0.20, "Finish"), ("Result + CTA", 0.20, "Show it again, one ask")],
    "listicle": [("Hook (the number)", 0.10, "'N things …' with a stake"), ("#1", 0.18, "Strongest first"), ("#2", 0.18, ""), ("#3", 0.18, "Save a surprising one for here"), ("#4 / bonus", 0.18, "Optional"), ("Wrap + CTA", 0.18, "Which one to do today")],
    "story": [("Hook (the moment)", 0.10, "Start at the peak of tension"), ("Context", 0.15, "Only what the ending needs"), ("Escalation", 0.30, "Stakes rise, one beat at a time"), ("Turn", 0.20, "What changed"), ("Resolution + lesson", 0.15, "What it means for the viewer"), ("CTA", 0.10, "One ask")],
    "product": [("Hook (pain)", 0.12, "The problem, in the viewer's words"), ("Demo", 0.35, "Show it solving the problem, no adjectives"), ("Proof", 0.20, "Number, before/after or testimonial"), ("Objection", 0.15, "Kill the #1 objection"), ("Offer + CTA", 0.18, "What to do, what they get")],
    "reaction": [("Hook (the clip + your take)", 0.15, "Set up what they're about to see"), ("Clip / claim", 0.25, "The thing you're reacting to"), ("Reaction 1", 0.25, "Your first correction or agreement with reasons"), ("Reaction 2", 0.20, "The deeper point"), ("Verdict + CTA", 0.15, "Your call in one line")],
}


@AGENT.tool
def plan_beats(
    duration_seconds: float,
    format: Literal["talking_head", "tutorial", "listicle", "story", "product", "reaction"] = "talking_head",
    pace: Literal["slow", "natural", "fast"] = "natural",
) -> dict:
    """Build a time-coded beat sheet with a spoken-word budget per beat for a given runtime and format.

    Call before writing so every beat has a word budget at the chosen pace; the hook is always
    capped at 3 seconds regardless of runtime.

    Args:
        duration_seconds: Target runtime in seconds (5-600).
        format: talking_head, tutorial, listicle, story, product or reaction.
        pace: slow (2.0 words/s), natural (2.5, default), fast (3.0).
    """
    if not 5 <= duration_seconds <= 600:
        raise ToolError("duration_seconds must be between 5 and 600")
    wps = PACE_WPS[pace]
    template = BEAT_TEMPLATES[format]
    beats, t = [], 0.0
    hook_cap = 3.0
    for i, (name, share, purpose) in enumerate(template):
        secs = duration_seconds * share
        if i == 0:
            secs = min(secs, hook_cap)
        beats.append({"beat": name, "starts_at": fmt_timestamp(t), "start_s": round(t, 1), "seconds": round(secs, 1), "word_budget": int(secs * wps), "purpose": purpose})
        t += secs
    # give leftover from hook cap to the last content beat
    leftover = duration_seconds - t
    if leftover > 0.05:
        beats[-2]["seconds"] = round(beats[-2]["seconds"] + leftover, 1)
        beats[-2]["word_budget"] = int(beats[-2]["seconds"] * wps)
        beats[-1]["start_s"] = round(beats[-1]["start_s"] + leftover, 1)
        beats[-1]["starts_at"] = fmt_timestamp(beats[-1]["start_s"])
    total_words = int(duration_seconds * wps)
    notes = []
    if duration_seconds > 60 and format in ("talking_head", "listicle"):
        notes.append("Over 60s for a talking-head/listicle: add a visual change every 3-5s or split into a series.")
    if duration_seconds <= 20:
        notes.append("Under 20s: write the last line to loop into the hook.")
    if duration_seconds > 180:
        notes.append("Exceeds Reels/Shorts 180s cap — TikTok/LinkedIn/YouTube long-form only.")
    return {
        "duration_seconds": duration_seconds,
        "format": format,
        "pace_words_per_second": wps,
        "total_word_budget": total_words,
        "beats": beats,
        "notes": notes,
        "summary": f"{len(beats)} beats, {total_words} spoken words max at {pace} pace; hook ≤ {int(hook_cap * wps)} words.",
    }


@AGENT.tool
def lint_script(script: str) -> dict:
    """Lint a short-video script for fillers, warm-up intros, unspeakable sentences, CTA problems and long on-screen text.

    Returns line-level issues with a cleaned version where the fix is mechanical (fillers and
    greetings removed), so the creator gets a tighter script, not just a list of complaints.

    Args:
        script: The script, one spoken line per line; [TEXT: …] cards are checked for length.
    """
    if not script.strip():
        raise ToolError("Script is empty.")
    if len(script) > 60_000:
        raise ToolError("Script too long (60k chars max).")
    spoken, directions = _spoken_lines(script)
    if not spoken:
        raise ToolError("No spoken lines found.")
    issues, cleaned = [], []
    filler_total = 0
    long_lines = 0
    for i, line in enumerate(spoken, 1):
        fixed = line
        fillers = FILLER_RE.findall(line)
        lead = LEAD_FILLER_RE.match(re.sub(r"^\s*(hey|hi|hello|what's up)\b[^.!?,]*[.!?,]?\s*", "", line, flags=re.I))
        if lead:
            fillers.append(lead.group(1))
        if fillers:
            filler_total += len(fillers)
            fixed = FILLER_RE.sub("", fixed)
            fixed = re.sub(r"\s{2,}", " ", fixed).replace(" ,", ",").strip()
            issues.append({"line": i, "type": "filler", "detail": f"{len(fillers)} filler(s): {', '.join(f.lower() for f in fillers[:4])}"})
        if i == 1 and INTRO_RE.search(line):
            issues.append({"line": 1, "type": "warm-up intro", "detail": "Opens with a greeting/preamble — the hook must be line 1."})
            fixed = re.sub(r"^\s*(hey|hi|hello|what's up)\b[^.!?,]*[.!?,]?\s*", "", fixed, flags=re.I)
        fixed = LEAD_FILLER_RE.sub("", fixed)
        if i > 1 and INTRO_RE.search(line):
            issues.append({"line": i, "type": "throat-clearing", "detail": "Preamble mid-script ('in this video', 'today I') — delete."})
        n = len(text.words(line))
        if n > 18:
            long_lines += 1
            issues.append({"line": i, "type": "long sentence", "detail": f"{n} words — cannot be said in one breath; split at the conjunction."})
        if text.PASSIVE_RE.search(line):
            issues.append({"line": i, "type": "passive voice", "detail": "Passive construction — say who does what."})
        cleaned.append(fixed if fixed else line)
    cta_hits = [i for i, l in enumerate(spoken, 1) if CTA_RE.search(l)]
    cta_asks = sum(len(CTA_RE.findall(l)) for l in spoken)
    if not cta_hits:
        issues.append({"line": len(spoken), "type": "no CTA", "detail": "No call to action found — add one line tied to the content (follow for part 2, save this, comment X)."})
    elif cta_asks > 2:
        issues.append({"line": cta_hits[-1], "type": "CTA pile-up", "detail": f"{cta_asks} separate asks — keep exactly one."})
    for card in TEXT_CARD_RE.findall(script):
        wc = len(text.words(card))
        if wc > 8:
            issues.append({"line": 0, "type": "on-screen text too long", "detail": f"'{card.strip()[:60]}' is {wc} words; cap cards at 8."})
    ws = [w.lower() for w in text.words(" ".join(spoken)) if w.lower() not in text.STOPWORDS and len(w) > 3]
    repeats = [(w, c) for w, c in Counter(ws).most_common(5) if c >= 4 and len(ws) >= 40]
    if repeats:
        issues.append({"line": 0, "type": "repetition", "detail": "Overused: " + ", ".join(f"{w} ×{c}" for w, c in repeats)})
    total_words = len(text.words(" ".join(spoken)))
    filler_rate = round(100 * filler_total / total_words, 1) if total_words else 0.0
    score = max(0, 100 - 8 * len(issues))
    return {
        "spoken_words": total_words,
        "filler_count": filler_total,
        "filler_rate_pct": filler_rate,
        "long_sentences": long_lines,
        "cta_lines": cta_hits,
        "issues": issues,
        "cleaned_script": "\n".join(cleaned),
        "score": score,
        "verdict": "Clean." if not issues else f"{len(issues)} issue(s); cleaned_script has the mechanical fixes applied.",
    }
