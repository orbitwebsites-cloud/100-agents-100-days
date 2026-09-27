"""Speechwriter — speeches timed to the minute, built on rhetoric that lands out loud."""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="speechwriter",
    name="Speechwriter",
    category="content",
    tagline="Write speeches and talks that land out loud: timed to the minute, built on rhetorical devices, and easy to deliver.",
    description=(
        "Writes keynotes, toasts, eulogies, TEDx talks, all-hands and commencement speeches the way a "
        "professional speechwriter does: one message, a structure the audience can feel, and the devices "
        "that make lines memorable — tricolon, anaphora, antithesis, callbacks. Times the script at the "
        "speaker's pace with pauses, maps the opening/body/close proportions, counts the rhetorical devices "
        "and flags where they're missing, and checks speakability (breath-length sentences, hard numbers, "
        "tongue-twisters) so the speaker never trips."
    ),
    triggers=[
        "write a speech / keynote / toast / eulogy / talk",
        "how long will this speech take to deliver",
        "make this talk more memorable or punchier",
        "check my speech for rhetorical devices and structure",
        "cut this speech to 10 minutes",
        "write a wedding / retirement / all-hands speech",
    ],
    examples=[
        "Write a 12-minute keynote for a fintech conference on 'why compliance is a product feature'. Speaker is our CEO, dry humour.",
        "Here's my best-man speech draft. Time it at my pace (I talk fast), find the laughs, and tighten it to 5 minutes.",
        "This all-hands talk feels flat. Where are the rhetorical devices missing and what should the close be?",
    ],
    connectors=["Google Docs", "Notion", "Microsoft Word"],
    playbook="""
    ## Standard
    You are a professional speechwriter — the kind who writes for people who are judged on
    what they say in a room. Excellent means: one message the audience can repeat at dinner,
    an opening that earns silence in ten seconds, a close the audience feels coming and still
    applauds, and a script the speaker can deliver without reading. The one metric: **the
    message survives the walk to the car.**

    ## Intake
    You need: the occasion, the speaker (who they are to the audience, how they talk), the
    audience, the time slot, and the one thing they want the room to think, feel or do. Assume
    130 wpm conversational delivery, a 10-15% opening, 70-80% body, 10-15% close, and a written
    style meant to be spoken (contractions, short sentences, no semicolons). Ask at most one
    question: "What's the one sentence you want them to remember?" — only if it isn't obvious.

    ## Procedure
    1. **Write the message sentence first.** One line, ≤ 15 words, in the speaker's voice. Every
       section must serve it; anything that doesn't gets cut. Then choose the structure:
       problem → turn → resolution (keynotes); past → present → future (retirement,
       anniversaries); story → meaning → charge (commencement, all-hands); three toasts
       (wedding: who they were, who they became, who they'll be together).
    2. **Draft out loud.** Write in spoken English: one clause per breath (≤ 20 words), verbs
       over nouns, concrete nouns over abstractions, numbers rounded to what a listener can
       hold ("about a third", not "34.7%"). Mark pauses as [pause], laughs as [beat], and
       applause lines as [applause]. Put the message sentence in the opening (by 15%), the
       middle (as a variation) and the close (verbatim — the callback).
    3. **Build the devices in on purpose.** Then call `speechwriter__rhetoric_check` on the
       draft. It counts tricolons, anaphora, epistrophe, antithesis, rhetorical questions,
       alliteration, refrains and callbacks with locations, and says which part of the speech
       has none. Targets: at least one tricolon in the close; one anaphora run of 3; one
       antithesis near the message; a callback from opening to close; a rhetorical question in
       the opening. Add what's missing where it says; don't stack devices in one paragraph.
    4. **Map the structure.** Call `speechwriter__structure_map`. It measures opening/body/close
       shares against the 10-15 / 70-80 / 10-15 ideal, names the opening hook type and the
       closing move, and checks the callback. Rebalance: a long opening is the most common
       failure; a close that introduces new information is the second.
    5. **Time it.** Call `speechwriter__timing` with the script, the speaker's pace and the
       slot. It counts spoken words (stage directions excluded), adds pause time, gives
       per-section timestamps and tells you how many words to cut or add. Deliver at 90% of
       the slot — rooms run long, never short.
    6. **Speakability pass.** Call `speechwriter__speakability`. Fix every flag: sentences over
       20 words (split), 4+ syllable words (swap), precise numbers (round and say how), acronyms
       (spell out or cut), tongue-twisters and sibilant runs (rephrase), parentheticals (cut).
    7. **Deliver** the script in the output format with delivery marks, plus the timing table
       and a one-page speaker card (message sentence, three beats, the last line). If a Docs
       connector exists, file it double-spaced in a large font.

    ## Frameworks
    - **Tricolon**: three parallel items, the third longest or strongest ("we came, we saw,
      we conquered"). **Anaphora**: the same opening words for 3+ successive sentences or
      clauses. **Epistrophe**: same ending words. **Antithesis**: "not X, but Y"; "ask not
      what… ask what…". **Callback**: a phrase from the opening returned in the close.
      **Refrain**: a line repeated 3+ times across the speech as a spine.
    - **Opening hooks**: a question; a story that starts mid-action; a startling number; a
      quote (only if genuinely apt); "Imagine…". Never "Thank you for having me" as line one.
    - **Closes**: the callback; the charge (imperative: "Go and…"); the vision; the toast.
      New information in the close is a bug.
    - **Pace presets**: ceremonial/eulogy 100-115 wpm; conversational 125-140; energetic
      keynote 150-165. Laugh lines add ~3 s each; applause lines ~8 s.
    - **Aristotle**: ethos in the first minute (why you), pathos through the stories, logos
      through the one number that matters.

    ## Output format
    ```
    **Occasion:** … · **Speaker:** … · **Slot:** N min · **Runs:** N:SS at N wpm
    **Message sentence:** "<≤ 15 words>"

    ## Script
    ### OPENING (0:00-1:20)
    <lines, one breath each>  [pause]  [beat]
    ### BODY
    …
    ### CLOSE (N:SS)
    <callback → charge → last line>  [applause]

    ## Speaker card
    - Message: "…"
    - Three beats: 1) … 2) … 3) …
    - Last line: "…"

    **Devices:** tricolon ×N · anaphora ×N · antithesis ×N · callback ✅
    **Timing table:** <section · start · duration · words>
    ```

    ## Anti-patterns
    - Opening with thanks, logistics, or "I was asked to speak about…".
    - Written English read aloud: semicolons, subordinate clauses, 35-word sentences.
    - Three messages instead of one; a "summary" close that lists them.
    - Jokes the speaker wouldn't tell; quotes from Einstein/Churchill that aren't theirs.
    - Precise numbers the ear can't hold; acronyms the audience has to decode.
    - Filling the slot exactly — leave 10% for laughs, pauses and nerves.
    - Devices stacked in one paragraph, then nothing for five minutes.
    """,
)

ANTITHESIS_RE = re.compile(
    r"\bnot\b[^.,;]{1,60},?\s+but\b|\bnot because\b[^.]{1,60}\bbut because\b|\bask not\b"
    r"|\b(?:it'?s|it is|this is|that'?s|that is|we'?re|we are|you'?re|you are)\s+not\b[^.;!?]{1,80}[,;—–-]\s*(?:it'?s|it is|this is|that'?s|that is|we'?re|we are|you'?re|you are)\b"
    r"|\bless\b[^.]{1,40}\bmore\b|\b(never|nothing)\b[^.]{1,40}\b(always|everything)\b",
    re.I,
)
# "It is not X. It is Y." — the antithesis split over two sentences for the pause
_SUBJ = r"(?:it'?s|it is|this is|that'?s|that is|we'?re|we are|you'?re|you are)"
ANTITHESIS_PAIR_RE = re.compile(r"\b" + _SUBJ + r"\s+not\b[^.;!?]{1,80}[.;!]\s+" + _SUBJ + r"\b", re.I)
PAUSE_MARKS = [
    (re.compile(r"\[(long pause|silence)\]", re.I), 4.0),
    (re.compile(r"\[(pause|beat|breath)\]", re.I), 2.0),
    (re.compile(r"\[(laugh(ter)?|laugh line)\]", re.I), 3.0),
    (re.compile(r"\[(applause|clap)\]", re.I), 8.0),
    (re.compile(r"\[(slide|next slide|click)\]", re.I), 1.5),
]
PACE = {"ceremonial": 110, "conversational": 130, "energetic": 155}
HEADING_LINE = re.compile(r"^\s{0,3}#{1,6}\s+.*$|^\s*[A-Z][A-Z0-9 &/_-]{2,40}:?\s*$|^\s*\[(?:OPENING|BODY|CLOSE|CLOSING|INTRO|PART \d+|SECTION \d+|STORY|ASK|TOAST)[^\]]{0,40}\]\s*$", re.M)


def _spoken_text(script: str) -> str:
    """The words the room hears: no section headings, no stage directions, no markdown."""
    return c.STAGE_DIR_RE.sub(" ", c.strip_markdown(HEADING_LINE.sub("", script)))


def _script_sections(script: str) -> list[dict]:
    secs = c.sections(script)
    if len([s for s in secs if s["level"] > 0]) == 0:
        # try ALL-CAPS or bracketed section lines
        out, cur = [], {"level": 0, "title": "(opening)", "body": []}
        for ln in script.splitlines():
            st = ln.strip()
            if st and (re.fullmatch(r"[A-Z][A-Z0-9 &/_-]{2,40}:?", st) or re.fullmatch(r"\[(?:OPENING|BODY|CLOSE|CLOSING|INTRO|PART \d+|SECTION \d+|STORY|ASK|TOAST)[^\]]{0,40}\]", st, re.I)):
                if cur["body"] or cur["title"] != "(opening)":
                    out.append(cur)
                cur = {"level": 2, "title": st.strip("[]:").strip(), "body": []}
            else:
                cur["body"].append(ln)
        out.append(cur)
        secs = [{"level": s["level"], "title": s["title"], "line": 0, "body": "\n".join(s["body"]), "words": len(c.spoken_words("\n".join(s["body"])))} for s in out if "\n".join(s["body"]).strip()]
    else:
        for s in secs:
            s["words"] = len(c.spoken_words(s["body"]))
    return secs


@AGENT.tool
def timing(script: str, wpm: int = 130, slot_minutes: float = 0.0, pace: Literal["custom", "ceremonial", "conversational", "energetic"] = "custom") -> dict:
    """Time a speech: spoken words (stage directions excluded), pause/laugh/applause time added, per-section timestamps, breath-length check, and words to cut or add for the slot.

    Call after drafting and after every cut. Marks recognised: [pause] 2s, [long pause] 4s,
    [laugh] 3s, [applause] 8s, [slide] 1.5s. Paragraph breaks add 0.5s each.

    Args:
        script: The full speech text (markdown headings or ALL-CAPS lines mark sections).
        wpm: Words per minute if pace is "custom" (80-200). Ceremonial ≈ 110, conversational ≈ 130, energetic ≈ 155.
        slot_minutes: The time slot in minutes (0 = none). The tool targets 90% of it.
        pace: Preset that overrides wpm: ceremonial, conversational or energetic.
    """
    c.guard(script, "Script")
    if pace != "custom":
        wpm = PACE[pace]
    if not 80 <= wpm <= 200:
        raise ToolError("wpm must be 80-200.")
    if slot_minutes < 0 or slot_minutes > 180:
        raise ToolError("slot_minutes must be 0-180.")
    secs = _script_sections(script)
    words = text.words(_spoken_text(script))
    if len(words) < 10:
        raise ToolError("Fewer than 10 spoken words.")
    pause_s = 0.0
    marks: dict[str, int] = {}
    for rx, secs_each in PAUSE_MARKS:
        n = len(rx.findall(script))
        if n:
            marks[rx.pattern.split("(")[1].split("|")[0]] = n
            pause_s += n * secs_each
    para_breaks = max(0, len(c.paragraphs(script)) - 1)
    pause_s += para_breaks * 0.5
    speech_s = len(words) / wpm * 60
    total_s = speech_s + pause_s
    rows = []
    t = 0.0
    for i, s in enumerate(secs):
        dur = s["words"] / wpm * 60
        for rx, secs_each in PAUSE_MARKS:
            dur += len(rx.findall(s["body"])) * secs_each
        # the same 0.5 s per paragraph break the total uses: breaks inside the section plus the one after it
        dur += 0.5 * (max(0, len(c.paragraphs(s["body"])) - 1) + (1 if i < len(secs) - 1 else 0))
        rows.append({"section": s["title"][:50], "start": c.mmss(t), "duration": c.mmss(dur), "words": s["words"], "share_pct": c.pct(s["words"], len(words))})
        t += dur
    sents = text.sentences(_spoken_text(script))
    long_breath =[{"words": len(text.words(x)), "sentence": x[:160]} for x in sents if len(text.words(x)) > 20]
    flags: list[str] = []
    delta = None
    target_s = None
    if slot_minutes:
        target_s = slot_minutes * 60 * 0.9
        delta_s = total_s - target_s
        delta = round(delta_s / 60 * wpm)
        if delta_s > 30:
            flags.append(f"Runs {c.mmss(total_s)} vs {c.mmss(target_s)} target (90% of the {slot_minutes:g}-min slot) — cut ~{delta} words.")
        elif delta_s < -60:
            flags.append(f"Runs {c.mmss(total_s)} vs {c.mmss(target_s)} target — room for ~{-delta} more words (or a longer pause after the big line).")
    if long_breath:
        flags.append(f"{len(long_breath)} sentences over 20 words — one breath each; split them.")
    if not marks:
        flags.append("No [pause]/[beat] marks — mark at least one pause after the message sentence and before the close.")
    return {
        "spoken_words": len(words),
        "wpm": wpm,
        "speaking_time": c.mmss(speech_s),
        "pause_time": c.mmss(pause_s),
        "total": c.mmss(total_s),
        "total_seconds": round(total_s),
        "total_minutes": round(total_s / 60, 1),
        "marks": marks,
        "sections": rows,
        "slot_minutes": slot_minutes or None,
        "target": c.mmss(target_s) if target_s else None,
        "words_vs_target": delta,
        "long_breath_sentences": long_breath[:12],
        "flags": flags,
        "verdict": f"{c.mmss(total_s)} at {wpm} wpm ({len(words)} words + {c.mmss(pause_s)} of pauses)." + (" On target." if slot_minutes and not any(f.startswith('Runs') for f in flags) else ""),
    }


def _norm_words(s: str) -> list[str]:
    return [w.lower() for w in text.words(s)]


@AGENT.tool
def rhetoric_check(script: str) -> dict:
    """Count and locate rhetorical devices: tricolons, anaphora, epistrophe, antithesis, rhetorical questions, alliteration, refrains and opening→close callbacks; says which part of the speech has none.

    Call after the draft; add devices where it reports gaps, not everywhere.

    Args:
        script: The speech text.
    """
    c.guard(script, "Script")
    plain = _spoken_text(script)
    sents = text.sentences(plain)
    if len(sents) < 3:
        raise ToolError("Need at least 3 sentences.")
    found: dict[str, list[dict]] = {k: [] for k in ("tricolon", "anaphora", "epistrophe", "antithesis", "rhetorical_question", "alliteration", "refrain", "callback")}
    # units: sentences plus clause/line splits (so anaphora across lines is caught); part = by word position
    units = [u for u in re.split(r"(?<=[.!?;:])\s+|\n+", plain) if len(text.words(u)) >= 2]
    n = len(units)
    unit_words = [len(text.words(u)) for u in units]
    total_words = sum(unit_words) or 1
    offsets, acc = [], 0
    for w in unit_words:
        offsets.append(acc)
        acc += w

    def part(i: int) -> str:
        frac = offsets[i] / total_words
        return "opening" if frac < 0.15 else "close" if frac >= 0.85 else "body"

    for i, s in enumerate(units):
        items = [x.strip() for x in re.split(r",\s*(?:and\s+|or\s+|but\s+)?|\s+(?:and|or)\s+(?=to\b|with\b|for\b|the\b)", s) if x.strip()]
        openers = [" ".join(_norm_words(x)[:1]) for x in items]
        parallel_run = any(openers[k] and openers[k] == openers[k + 1] == openers[k + 2] for k in range(len(openers) - 2))
        if (re.search(r"\b\w[\w' -]{0,40}, \w[\w' -]{0,40},? (and|or|but) \w[\w' -]{0,60}", s) and s.count(",") in (1, 2)) or parallel_run:
            found["tricolon"].append({"sentence": i + 1, "part": part(i), "text": s[:160]})
        if s.rstrip().endswith("?"):
            found["rhetorical_question"].append({"sentence": i + 1, "part": part(i), "text": s[:160]})
        pair = s + " " + units[i + 1] if i + 1 < n else s
        if ANTITHESIS_RE.search(s) or ANTITHESIS_PAIR_RE.search(pair):
            found["antithesis"].append({"sentence": i + 1, "part": part(i), "text": s[:160]})
        ws = [w for w in text.words(s) if w.lower() not in text.STOPWORDS and len(w) > 2]
        run = 1
        for a, b in zip(ws, ws[1:]):
            if a[0].lower() == b[0].lower():
                run += 1
                if run == 3:
                    found["alliteration"].append({"sentence": i + 1, "part": part(i), "text": s[:160]})
            else:
                run = 1
    # a leading conjunction doesn't break the parallel ("To the man… To the woman… And to the…")
    starts = [" ".join([w for w in _norm_words(u)][1:3] if _norm_words(u)[:1] in (["and"], ["but"], ["or"], ["so"]) else _norm_words(u)[:2]) for u in units]
    ends = [" ".join(_norm_words(u)[-2:]) for u in units]
    # sentence-level tricolon: three consecutive short, distinct units with parallel shape (same opener or same ending)
    i = 0
    while i + 2 < n:
        trio = units[i:i + 3]
        short = all(len(text.words(u)) <= 14 for u in trio) and len({" ".join(_norm_words(u)) for u in trio}) == 3
        parallel = (starts[i] == starts[i + 1] == starts[i + 2] and starts[i]) or (ends[i] == ends[i + 1] == ends[i + 2] and ends[i])
        if short and parallel:
            found["tricolon"].append({"sentence": i + 1, "part": part(i), "text": " ".join(trio)[:160]})
            i += 3
        else:
            i += 1
    i = 0
    while i < n:
        j = i
        while j + 1 < n and starts[j + 1] == starts[i] and starts[i]:
            j += 1
        if j - i + 1 >= 3:
            found["anaphora"].append({"sentence": i + 1, "part": part(i), "text": f"'{starts[i]}…' ×{j - i + 1}"})
            i = j + 1
        else:
            i += 1
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ends[j + 1] == ends[i] and ends[i]:
            j += 1
        if j - i + 1 >= 3:
            found["epistrophe"].append({"sentence": i + 1, "part": part(i), "text": f"'…{ends[i]}' ×{j - i + 1}"})
            i = j + 1
        else:
            i += 1
    # refrains: 4-grams appearing 3+ times across the speech
    all_w = _norm_words(plain)
    grams = Counter(" ".join(all_w[k:k + 4]) for k in range(len(all_w) - 3))
    for g, cnt in grams.most_common(40):
        if cnt >= 3 and not all(w in text.STOPWORDS for w in g.split()):
            found["refrain"].append({"phrase": g, "count": cnt})
    found["refrain"] = found["refrain"][:5]
    # callbacks: 3-grams shared by opening (first 15%) and close (last 15%)
    open_w = all_w[: max(12, int(len(all_w) * 0.15))]
    close_w = all_w[-max(12, int(len(all_w) * 0.15)):]
    og = {" ".join(open_w[k:k + 3]) for k in range(len(open_w) - 2)}
    cg = {" ".join(close_w[k:k + 3]) for k in range(len(close_w) - 2)}
    shared = [g for g in og & cg if not all(w in text.STOPWORDS for w in g.split())]
    for g in sorted(shared)[:5]:
        found["callback"].append({"phrase": g})
    counts = {k: len(v) for k, v in found.items()}
    gaps = []
    if not any(d["part"] == "opening" for d in found["rhetorical_question"]) and not any(d["part"] == "opening" for d in found["antithesis"]):
        gaps.append("Opening: no question or antithesis — earn attention in the first 15%.")
    if not any(d["part"] == "close" for d in found["tricolon"]):
        gaps.append("Close: no tricolon — the last movement wants a three-part line.")
    if counts["anaphora"] == 0:
        gaps.append("No anaphora anywhere — a run of three sentences with the same opening words is the cheapest applause line there is.")
    if counts["antithesis"] == 0:
        gaps.append("No antithesis — frame the message as 'not X, but Y' once.")
    if counts["callback"] == 0:
        gaps.append("No callback — bring a phrase from the opening back in the close.")
    if counts["refrain"] == 0 and n >= 40:
        gaps.append("No refrain — a line repeated 3+ times gives a long speech a spine.")
    body_devices = sum(1 for k in ("tricolon", "anaphora", "antithesis", "rhetorical_question") for d in found[k] if d["part"] == "body")
    if n >= 30 and body_devices == 0:
        gaps.append("Body: no devices at all — the middle will sag; one every ~90 seconds.")
    stacked = Counter(d["sentence"] // 5 for k in ("tricolon", "anaphora", "antithesis", "alliteration") for d in found[k] if "sentence" in d)
    if stacked and max(stacked.values()) >= 4:
        gaps.append("Devices are stacked in one stretch — spread them out.")
    density = round(sum(counts[k] for k in ("tricolon", "anaphora", "epistrophe", "antithesis", "rhetorical_question")) / n * 100, 1)
    return {
        "sentences": n,
        "counts": counts,
        "devices_per_100_sentences": density,
        "found": found,
        "gaps": gaps,
        "verdict": ("Rhetorically complete." if not gaps else f"{len(gaps)} gap(s) to fill.") + f" Device density {density}/100 sentences.",
    }


HOOK_TYPES = [
    ("question", re.compile(r"\?")),
    ("imagine", re.compile(r"^\s*(imagine|picture this|think about)\b", re.I)),
    ("story", re.compile(r"\b(when i was|years ago|in (19|20)\d{2}|last (week|month|year)|i remember|the first time|it was|there was|once)\b", re.I)),
    ("number", re.compile(r"\d")),
    ("quote", re.compile(r"^\s*[\"“]|\b(once said|wrote|said)\b", re.I)),
    ("bold claim", re.compile(r"\b(everything you|is wrong|is dead|is a lie|nobody|never|always)\b", re.I)),
]
CLOSE_TYPES = [
    ("toast", re.compile(r"\b(raise (your|a|our) glass(es)?|to the (bride|groom|couple|happy|newlyweds)|cheers|here's to)\b|^\s*to [A-Z][\w'-]+(?: and [A-Z][\w'-]+)?\s*[!.]", re.I | re.M)),
    ("charge", re.compile(r"^\s*(go|let's|let us|build|make|choose|be|start|stop|remember|take|join|don't|never|ask)\b", re.I | re.M)),
    ("vision", re.compile(r"\b(imagine|one day|a world where|the future|will be|we will)\b", re.I)),
    ("thanks", re.compile(r"\b(thank you|thanks)\b\s*[.!]?\s*$", re.I)),
]


@AGENT.tool
def structure_map(script: str, wpm: int = 130) -> dict:
    """Map the speech's shape: opening/body/close word shares vs the 10-15 / 70-80 / 10-15 ideal, opening hook type, closing move, message-sentence position, callback presence, and a timeline.

    Call after rhetoric_check. Rebalance a long opening first; then fix a close that adds new
    information or ends on 'thank you'.

    Args:
        script: The speech text (headings or ALL-CAPS lines mark sections; otherwise the first and last paragraphs are opening and close).
        wpm: Speaking pace for the timeline (80-200).
    """
    c.guard(script, "Script")
    if not 80 <= wpm <= 200:
        raise ToolError("wpm must be 80-200.")
    secs = _script_sections(script)
    total = sum(s["words"] for s in secs)
    if total < 30:
        raise ToolError("Fewer than 30 spoken words.")
    titled = [s for s in secs if s["level"] > 0]
    if len(titled) >= 3:
        opening, close = titled[0], titled[-1]
        body_words = total - opening["words"] - close["words"]
        open_w, close_w = opening["words"], close["words"]
        open_text, close_text = c.strip_markdown(opening["body"]), c.strip_markdown(close["body"])
    else:
        paras = c.paragraphs(_spoken_text(script))
        if len(paras) < 3:
            raise ToolError("Need headings or at least 3 paragraphs to map opening / body / close.")
        open_text, close_text = paras[0], paras[-1]
        open_w, close_w = len(text.words(open_text)), len(text.words(close_text))
        body_words = total - open_w - close_w
    shares = {"opening_pct": c.pct(open_w, total), "body_pct": c.pct(body_words, total), "close_pct": c.pct(close_w, total)}
    flags: list[str] = []
    if shares["opening_pct"] > 18:
        flags.append(f"Opening is {shares['opening_pct']}% of the speech (ideal 10-15%) — cut set-up; start mid-action.")
    elif shares["opening_pct"] < 6:
        flags.append(f"Opening is only {shares['opening_pct']}% — too abrupt to build ethos; add the 'why you' line.")
    if shares["close_pct"] > 18:
        flags.append(f"Close is {shares['close_pct']}% — a close over 15% is a second body; cut to the callback + charge.")
    elif shares["close_pct"] < 6:
        flags.append(f"Close is only {shares['close_pct']}% — give the landing room: callback, charge, last line.")
    first_sent = (text.sentences(open_text) or [open_text])[0]
    hook = next((name for name, rx in HOOK_TYPES if rx.search(first_sent)), "statement")
    if re.match(r"^\s*(thank you|thanks|good (morning|afternoon|evening)|hello|hi everyone|it's (great|an honou?r|a pleasure)|i was asked|my name is)\b", first_sent, re.I):
        flags.append(f"Line 1 is '{first_sent[:50]}…' — thanks/greeting/logistics. Open with the hook.")
        hook = "greeting (weak)"
    close_sents = text.sentences(close_text)
    last_sent = close_sents[-1] if close_sents else close_text
    charge_rx = dict(CLOSE_TYPES)["charge"]
    if dict(CLOSE_TYPES)["thanks"].search(last_sent):
        close_move = "thanks"
    elif dict(CLOSE_TYPES)["toast"].search(close_text):
        close_move = "toast"
    elif any(charge_rx.match(s) for s in close_sents[-4:]):
        close_move = "charge"
    elif dict(CLOSE_TYPES)["vision"].search(last_sent):
        close_move = "vision"
    else:
        close_move = "statement"
    if close_move == "thanks":
        flags.append("Last line is 'thank you' — end on the last line of the speech; the thanks can follow the applause.")
    if re.search(r"\b(to summari[sz]e|in summary|in conclusion|to sum up|three things i|let me recap)\b", close_text, re.I):
        flags.append("Close is a summary — replace with the callback + charge; the audience remembers one thing, not a list.")
    ow, cw = _norm_words(open_text), _norm_words(close_text)
    og = {" ".join(ow[k:k + 3]) for k in range(len(ow) - 2)}
    cg = {" ".join(cw[k:k + 3]) for k in range(len(cw) - 2)}
    callbacks = sorted(g for g in og & cg if not all(w in text.STOPWORDS for w in g.split()))
    if not callbacks:
        flags.append("No callback: no phrase from the opening returns in the close.")
    close_nums = set(re.findall(r"\d[\d,.]*", close_text))
    body_nums = set(re.findall(r"\d[\d,.]*", _spoken_text(script)[: -len(close_text) or None]))
    new_in_close = sorted(close_nums - body_nums)
    if new_in_close:
        flags.append(f"New numbers appear only in the close ({', '.join(new_in_close[:4])}) — the close shouldn't introduce information.")
    timeline = []
    t = 0.0
    for s in secs:
        dur = s["words"] / wpm * 60
        timeline.append({"section": s["title"][:50], "start": c.mmss(t), "words": s["words"], "share_pct": c.pct(s["words"], total)})
        t += dur
    return {
        "spoken_words": total,
        "runtime": c.mmss(total / wpm * 60),
        "shares": shares,
        "ideal": {"opening_pct": "10-15", "body_pct": "70-80", "close_pct": "10-15"},
        "opening_hook": hook,
        "first_sentence": first_sent[:200],
        "closing_move": close_move,
        "last_sentence": last_sent[:200],
        "callbacks": callbacks[:5],
        "timeline": timeline,
        "flags": flags,
        "verdict": "Structure is sound." if not flags else f"{len(flags)} structural fix(es).",
    }


def _spoken_number(raw: str) -> str:
    s = raw.replace(",", "")
    pct = s.endswith("%")
    s = s.rstrip("%")
    try:
        v = float(s)
    except ValueError:
        return raw
    if pct:
        if abs(v - 50) <= 3:
            return "about half"
        if abs(v - 33) <= 3:
            return "about a third"
        if abs(v - 25) <= 3:
            return "about a quarter"
        if abs(v - 75) <= 3:
            return "about three quarters"
        if v >= 97:
            return "almost all"
        if v >= 88:
            return "nine in ten"
        return f"about {int(round(v / 5.0) * 5)} percent"
    if v >= 1_000_000_000:
        return f"about {round(v / 1e9, 1):g} billion"
    if v >= 1_000_000:
        return f"about {round(v / 1e6, 1):g} million"
    if v >= 1000:
        return f"about {int(round(v / 100.0) * 100):,}" if v < 20000 else f"about {int(round(v / 1000.0)):,} thousand"
    if v != int(v):
        return f"about {int(round(v))}"
    return raw


@AGENT.tool
def speakability(script: str) -> dict:
    """Flag what trips a speaker: sentences over 20 words, 4+ syllable words, precise numbers (with a spoken rounding), acronyms, tongue-twisters, sibilant runs, parentheticals; scores 0-100.

    Call as the last pass before delivery. Fix every flagged line — the speaker should never
    have to read.

    Args:
        script: The speech text.
    """
    c.guard(script, "Script")
    plain = _spoken_text(script)
    ws = text.words(plain)
    if len(ws) < 10:
        raise ToolError("Fewer than 10 spoken words.")
    sents = text.sentences(plain)
    long_s =[{"words": len(text.words(s)), "sentence": s[:160]} for s in sents if len(text.words(s)) > 20]
    hard_words = sorted({w.lower() for w in ws if not any(ch.isdigit() for ch in w) and text.syllables(w) >= 4 and not w.isupper()})
    numbers = []
    for m in re.finditer(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?(?![\w])", plain):
        raw = m.group(0)
        if re.fullmatch(r"(1[5-9]|20)\d\d", raw):
            continue  # a year is said as a year ("twenty oh-nine"), not rounded
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 4 or "." in raw or (raw.endswith("%") and not re.fullmatch(r"(10|20|25|50|75|90|100)%", raw)):
            spoken = _spoken_number(raw)
            if spoken != raw:
                numbers.append({"number": raw, "say": spoken, "context": c.context(plain, m.start(), 25)})
    acronyms = sorted({w for w in ws if len(w) >= 3 and w.isupper() and not w.isdigit()})
    twisters = []
    for s in sents:
        toks = [w.lower() for w in text.words(s) if len(w) > 3]
        for a, b, d in zip(toks, toks[1:], toks[2:]):
            if a[:2] == b[:2] == d[:2]:
                twisters.append({"words": f"{a} {b} {d}", "sentence": s[:120]})
                break
        if re.search(r"\b\w*(?:sts|xths|sks|ths)\b\s+\w*(?:sts|xths|sks|ths)\b", s, re.I):
            twisters.append({"words": "consonant cluster run", "sentence": s[:120]})
    sibilant = []
    for s in sents:
        toks = text.words(s)
        if len(toks) >= 6 and sum(1 for w in toks if w[0].lower() in "sz" or w.lower().endswith("s")) / len(toks) > 0.55:
            sibilant.append(s[:120])
    parens = re.findall(r"\([^)]{8,}\)|—[^—]{8,80}—", plain)
    semicolons = plain.count(";")
    rd = text.readability(plain)
    per100 = lambda n: round(100.0 * n / len(ws), 2)  # noqa: E731
    score = 100
    score -= min(30, len(long_s) * 3)
    score -= min(20, int(per100(len(hard_words)) * 3))
    score -= min(15, len(numbers) * 3)
    score -= min(10, len(acronyms) * 2)
    score -= min(10, len(twisters) * 3)
    score -= min(8, len(sibilant) * 2)
    score -= min(8, len(parens) * 2)
    score -= min(6, semicolons * 2)
    score = max(0, score)
    fixes = []
    if long_s:
        fixes.append(f"{len(long_s)} sentences over 20 words — split at the conjunction; one breath each.")
    if hard_words:
        fixes.append(f"{len(hard_words)} four-syllable+ words ({', '.join(hard_words[:6])}) — swap for shorter ones.")
    if numbers:
        fixes.append(f"{len(numbers)} numbers to round for the ear (see `numbers`).")
    if acronyms:
        fixes.append(f"Acronyms: {', '.join(acronyms[:6])} — say the words or cut.")
    if twisters:
        fixes.append(f"{len(twisters)} tongue-twister(s) — rephrase.")
    if sibilant:
        fixes.append(f"{len(sibilant)} hissing sentence(s) (too many s-sounds) — rephrase for the mic.")
    if parens:
        fixes.append(f"{len(parens)} parenthetical aside(s) — cut or make them their own sentence.")
    if semicolons:
        fixes.append(f"{semicolons} semicolon(s) — nobody can hear one; use a full stop.")
    return {
        "score": score,
        "words": len(ws),
        "sentences": len(sents),
        "avg_sentence_words": rd["avg_words_per_sentence"],
        "fk_grade": rd["fk_grade"],
        "long_sentences": long_s[:15],
        "hard_words": hard_words[:30],
        "numbers": numbers[:20],
        "acronyms": acronyms[:20],
        "tongue_twisters": twisters[:10],
        "sibilant_sentences": sibilant[:8],
        "parentheticals": len(parens),
        "semicolons": semicolons,
        "fixes": fixes,
        "verdict": ("Speakable as written." if score >= 85 else "Deliverable with fixes." if score >= 60 else "Written English — rewrite for the ear.") + f" Score {score}/100.",
    }
