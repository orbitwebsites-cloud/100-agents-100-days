"""Call Debrief — measures the call, extracts the real next step and buying signals, and writes the CRM update so it actually gets logged."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates, text
from . import _common as c

AGENT = Agent(
    slug="sales-call-debrief",
    name="Call Debrief",
    category="sales",
    tagline="Paste a sales call; get the talk metrics, the buying temperature, the real next step, and a CRM update ready to log.",
    description=(
        "Turns any sales call transcript into a two-minute debrief and a clean CRM record: talk ratio, "
        "monologues, filler and pace per speaker; every next-step candidate with owner and resolved date; "
        "positive and negative buying signals scored into a temperature; and the deal fields (stage, amount, "
        "close date, next step, competitors, risks) validated and mapped to HubSpot, Salesforce or Pipedrive "
        "property names so the update can be pushed, not retyped."
    ),
    triggers=[
        "debrief this sales call / demo",
        "summarize this call for the CRM",
        "what was the next step from this call",
        "how did the prospect sound — are they going to buy",
        "update the deal in HubSpot / Salesforce from this transcript",
        "how much did I talk on this call",
    ],
    examples=[
        "Here's the Gong transcript from today's demo with Acme. Debrief it and give me the HubSpot update.",
        "Did we actually agree a next step on this call? Transcript attached.",
        "Score the buying signals in this call — the rep thinks it's a lock, I'm not sure.",
        "Turn these call notes into Salesforce fields: stage, amount, close date, next step.",
    ],
    connectors=["HubSpot", "Salesforce", "Pipedrive", "Gong", "Chorus", "Slack", "Notion"],
    playbook="""
    ## Standard
    You are the sales manager who listens to every call and writes the note the rep
    should have written. Excellent means: numbers, not impressions ("rep talked 61%, 4
    questions" not "a bit talky"); a next step that has a date and a name or an honest
    "none agreed"; a buying temperature backed by quotes; and a CRM update with valid
    field values. The one metric: **the deal record after the call is true** — stage,
    amount, close date and next step reflect what the prospect actually said.

    ## Intake
    You need the transcript (or detailed notes), the rep's name as it appears, the
    call date, and the CRM (HubSpot / Salesforce / Pipedrive) if an update is wanted.
    If the rep's name is unclear, assume the first speaker and say so. Ask at most one
    question, and only if there is no transcript at all.

    ## Procedure
    1. **Measure.** Call `sales_call_debrief__call_metrics` with the transcript and rep
       name. Read: talk share per speaker, longest monologue, rep questions, filler words
       per minute, words per minute (> 180 = rushing), interruptions proxy (very short
       turns after long ones), and the share of the call the prospect spent in answers
       over 40 words (stories = engagement).
    2. **Find the next step.** Call `sales_call_debrief__detect_next_steps` with the
       transcript and call date. It returns every commitment line with the speaker, the
       resolved date (from "Thursday", "end of next week") and whether it is a real next
       step (both parties, a date, a named owner) or just an intention. If none qualifies,
       the debrief says "No next step agreed" in bold — that is the most useful line you
       can write.
    3. **Take the temperature.** Call `sales_call_debrief__buying_signals`. It counts
       positive signals (budget confirmed, timeline, stakeholders introduced, "when we
       roll this out", implementation questions) and negative ones (just exploring,
       no budget, "send me info", competitor praise, decision far away) and gives a
       temperature (hot / warm / cool / cold) with the quotes. Trust it over the rep's
       optimism; check the quotes yourself for sarcasm or context.
    4. **Map the CRM update.** Build the field dict (stage, amount, close date, next
       step + date, competitors, champion, risks, notes) from steps 1-3 and call
       `sales_call_debrief__map_crm_fields` with the CRM name. It validates dates and
       amounts, checks the stage against the CRM's standard stages, flags required
       fields that are missing, and returns the property payload. If a connector is
       available, push it; otherwise output it ready to paste.
    5. **Write the debrief** in the output format. Quotes for every claim; ≤ 250 words
       before the CRM block. Post to Slack/Notion if connected.

    ## Frameworks
    - **Call-metric benchmarks (call-analytics research, Gong/Chorus):** top reps talk
      ~43-46% on discovery and ~65% on demos (demos are meant to be shown); longest
      monologue ≤ 60-90 seconds on discovery; 11-14 questions per 30 minutes; the
      prospect's longest story ≥ 2 minutes signals engagement.
    - **Next-step test:** a real next step has (1) a specific action, (2) a date or day,
      (3) the prospect's involvement (they agreed to attend/send/introduce). Two out of
      three is an intention — log it, but don't move the stage.
    - **Buying temperature:** hot = ≥ 3 positive and 0 strong negative; warm = positives
      outnumber negatives; cool = balanced or "exploring"; cold = a strong negative
      (no budget, chose competitor, no authority and no path). Strong negatives
      override counts.
    - **Stage movement rules:** move to proposal only with a confirmed next step and
      a named economic buyer; move to negotiation only after pricing was discussed and
      the prospect asked about terms; never move a stage on rep sentiment.
    - **CRM hygiene:** close date = the prospect's stated timeline (+ 2 weeks for paper
      process), not the rep's hope; amount = quoted or estimated with "est." flag; next
      step ≤ 80 chars, starts with a verb, includes the date.

    ## Output format
    ```
    # Call debrief — <company> · <date> · <type: discovery/demo/negotiation>
    **Metrics:** rep <x>% talk · <n> questions · longest monologue <n>s · fillers <n>/min
    **Temperature:** <hot/warm/cool/cold> — <one line why>

    ## What we learned (with quotes)
    - <fact> — "<quote>"

    ## Next step
    **<Action> — <owner> — <date>**  (or **No next step agreed** — propose: <…>)

    ## Risks / open questions
    - …

    ## CRM update (<HubSpot/Salesforce/Pipedrive>)
    | Field | Value |
    |---|---|
    | Stage | … |
    | Amount | … |
    | Close date | … |
    | Next step | … |
    ```

    ## Anti-patterns
    - "Great call, very positive" — no quotes, no numbers.
    - Logging "follow up next week" as a next step. Whose action? Which day?
    - Moving the stage because the rep felt good.
    - Close dates copied from last quarter's forecast instead of the prospect's words.
    - Ignoring the negative signals because the positives were louder.
    - Debriefs longer than the call summary a VP would read on a phone.
    """,
)

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DATE_PHRASE_RE = re.compile(
    r"\b(today|tomorrow|eod|end of (?:the )?(?:day|week|month|quarter)|end of next (?:week|month)|eow|eom|this week|next week|next month|"
    r"(?:next |this )?(?:mon|tues|wednes|thurs|fri|satur|sun)day|in (?:a|one|two|three|four|\d+) (?:days?|weeks?|months?)|"
    r"by (?:the )?\d{1,2}(?:st|nd|rd|th)?|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2}|\d{1,2}/\d{1,2}|q[1-4])\b",
    re.I,
)
COMMIT_RE = re.compile(r"\b(i'?ll|i will|we'?ll|we will|let'?s|can you|could you|will you|can we|could we|shall we|should we|you'?ll|send (?:you|over|me)|schedule|set up|book|calendar|invite|loop in|introduce|intro|share|get back|circle back|follow up|next step|pilot|trial|proposal|pricing|quote|contract|redline|legal|procurement|sign)\b", re.I)
AGREE_RE = re.compile(r"\b(sounds good|works for me|perfect|great|yes|sure|let'?s do (?:that|it)|deal|agreed|that works|ok(?:ay)?|i'?ll be there|i'?ll join|i'?ll make sure)\b", re.I)


def _resolve_phrase(phrase: str, base: date) -> date | None:
    p = phrase.lower().strip()
    if p in ("today", "eod", "end of the day", "end of day"):
        return base
    if p == "tomorrow":
        return base + timedelta(days=1)
    if p in ("eow", "end of week", "end of the week", "this week"):
        return base + (timedelta(days=1) * ((4 - base.weekday()) % 7))
    if p in ("next week",):
        return base + timedelta(days=1) * (7 - base.weekday())
    if p == "end of next week":
        # Friday of the following calendar week
        return base + timedelta(days=1) * (7 - base.weekday() + 4)
    if p == "end of next month":
        first_next = (base.replace(day=28) + timedelta(days=1) * 4).replace(day=1)
        return (first_next.replace(day=28) + timedelta(days=1) * 4).replace(day=1) - timedelta(days=1)
    m = re.match(r"in (a|one|two|three|four|\d+) (day|week|month)s?", p)
    if m:
        n = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4}.get(m.group(1)) or int(m.group(1))
        return base + timedelta(days=1) * (n * {"day": 1, "week": 7, "month": 30}[m.group(2)])
    if p in ("end of month", "end of the month", "eom"):
        nxt = (base.replace(day=28) + timedelta(days=1) * 4).replace(day=1)
        return nxt - timedelta(days=1)
    if p in ("next month",):
        return (base.replace(day=28) + timedelta(days=1) * 4).replace(day=1)
    if p in ("end of quarter", "end of the quarter"):
        qm = ((base.month - 1) // 3 + 1) * 3
        d = date(base.year, qm, 1)
        return (d.replace(day=28) + timedelta(days=1) * 4).replace(day=1) - timedelta(days=1)
    for i, day in enumerate(WEEKDAYS):
        if re.search(rf"\b{day[:3]}", p):
            if p.startswith("next"):
                # "next Tuesday" = the Tuesday of the following calendar week (said on a Thursday
                # that is 5 days away, said on a Monday it is 8 days away) — never 12+ days out
                return base + timedelta(days=1) * (7 - base.weekday() + i)
            ahead = (i - base.weekday()) % 7 or 7
            return base + timedelta(days=1) * ahead
    m = re.match(r"q([1-4])", p)
    if m:
        q = int(m.group(1))
        d = date(base.year if q * 3 >= base.month else base.year + 1, q * 3, 1)
        return (d.replace(day=28) + timedelta(days=1) * 4).replace(day=1) - timedelta(days=1)
    m = re.match(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2})", p)
    if m:
        mon = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(m.group(1)) + 1
        try:
            d = date(base.year, mon, int(m.group(2)))
        except ValueError:
            return None
        return d if d >= base else date(base.year + 1, mon, int(m.group(2)))
    m = re.match(r"(\d{1,2})/(\d{1,2})", p)
    if m:
        try:
            d = date(base.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        return d if d >= base else date(base.year + 1, int(m.group(1)), int(m.group(2)))
    m = re.match(r"by (?:the )?(\d{1,2})", p)
    if m:
        day = int(m.group(1))
        try:
            d = base.replace(day=day)
        except ValueError:
            return None
        if d < base:
            nxt = (base.replace(day=28) + timedelta(days=1) * 4).replace(day=1)
            try:
                d = nxt.replace(day=day)
            except ValueError:
                return None
        return d
    return None


@AGENT.tool
def call_metrics(transcript: str, rep_name: str = "", call_minutes: int = 0, call_type: str = "discovery") -> dict:
    """Measure a sales call: talk share, longest monologue, questions, fillers/min, words/min, interruptions, prospect story share.

    Call first. Transcript lines look like "Name: text" (timestamps optional). If rep_name is blank
    the first speaker is treated as the rep. Benchmarks differ for discovery vs demo.

    Args:
        transcript: Raw transcript text.
        rep_name: The seller's name as labelled in the transcript.
        call_minutes: Actual call length in minutes (0 = from line timestamps if present, else estimated at 150 wpm).
        call_type: discovery (default), demo or negotiation — sets the talk-ratio benchmark.
    """
    ct = call_type.strip().lower()
    if ct not in ("discovery", "demo", "negotiation"):
        raise ToolError("call_type must be discovery, demo or negotiation.")
    turns = c.parse_transcript(transcript)
    labelled = [(s, t) for s, t in turns if s]
    if not labelled:
        raise ToolError("No 'Name: text' lines found — label each line with the speaker.")
    order = list(dict.fromkeys(s for s, _ in labelled))
    rep = c.match_speaker(rep_name, order) if rep_name else None
    if rep_name and rep is None:
        raise ToolError(f"rep_name {rep_name!r} not found among speakers {order}.")
    rep = rep or order[0]
    words_by, turns_by = Counter(), Counter()
    longest = {}
    fillers_by: dict[str, Counter] = {s: Counter() for s in order}
    rep_questions = 0
    prospect_story_words = 0
    interruptions = 0
    prev_len, prev_spk = 0, None
    for spk, said in labelled:
        n = len(text.words(said))
        words_by[spk] += n
        turns_by[spk] += 1
        fillers_by[spk].update(c.count_fillers(said))
        if n > longest.get(spk, ("", 0))[1]:
            longest[spk] = (said[:140], n)
        if spk == rep:
            rep_questions += len(c.questions_in(said))
        else:
            if n >= 40:
                prospect_story_words += n
        # interruption proxy: a speaker change where the previous turn was cut short (< 8 words) after they'd been talking
        if prev_spk and prev_spk != spk and prev_len <= 7 and spk == rep and n > 20:
            interruptions += 1
        prev_len, prev_spk = n, spk
    total = sum(words_by.values()) or 1
    minutes, minutes_source, duration_warnings = c.call_minutes_for(transcript, total, call_minutes)
    rep_pct = c.pct(words_by[rep], total)
    bench = {"discovery": (43, 46, 55), "demo": (60, 65, 75), "negotiation": (45, 50, 60)}[ct]
    prospect_words = total - words_by[rep]
    story_share = c.pct(prospect_story_words, prospect_words) if prospect_words else 0.0
    rep_fill = sum(fillers_by[rep].values())
    flags = list(duration_warnings)
    if rep_pct > bench[2]:
        flags.append(f"rep talk {rep_pct}% — well above the {bench[0]}-{bench[1]}% benchmark for a {ct} call")
    elif rep_pct > bench[1] + 5:
        flags.append(f"rep talk {rep_pct}% — above the {bench[0]}-{bench[1]}% benchmark")
    lr = longest.get(rep, ("", 0))
    cap = 150 if ct == "discovery" else 300
    if lr[1] > cap:
        flags.append(f"longest rep monologue {lr[1]} words (~{round(lr[1] / 150 * 60)}s) — cap ≈ {round(cap / 150 * 60)}s")
    q30 = round(rep_questions * 30 / minutes, 1)
    if ct == "discovery" and q30 < 10:
        flags.append(f"{rep_questions} questions ({q30}/30 min) — target 11-14")
    if rep_fill / minutes > 3:
        flags.append(f"{round(rep_fill / minutes, 1)} fillers/min — top: {', '.join(k for k, _ in fillers_by[rep].most_common(3))}")
    if interruptions >= 3:
        flags.append(f"{interruptions} probable interruptions by the rep — let answers finish")
    if story_share < 25 and prospect_words > 100:
        flags.append(f"only {story_share}% of prospect words came in answers ≥ 40 words — you got facts, not stories")
    return {
        "rep": rep,
        "call_type": ct,
        "speakers": order,
        "estimated_minutes": minutes,
        "minutes_source": minutes_source,
        "total_words": total,
        "talk_share_pct": {s: c.pct(w, total) for s, w in words_by.most_common()},
        "turns": dict(turns_by),
        "avg_words_per_turn": {s: round(words_by[s] / turns_by[s], 1) for s in order},
        "rep_talk_pct": rep_pct,
        "benchmark_rep_talk_pct": f"{bench[0]}-{bench[1]}",
        "rep_questions": rep_questions,
        "rep_questions_per_30min": q30,
        "longest_monologue": {s: {"words": v[1], "approx_seconds": round(v[1] / 150 * 60), "starts": v[0]} for s, v in longest.items()},
        "fillers_per_minute_rep": round(rep_fill / minutes, 1),
        "rep_top_fillers": dict(fillers_by[rep].most_common(3)),
        "rep_words_per_minute_while_talking": round(words_by[rep] / max(0.1, minutes * words_by[rep] / total)) if words_by[rep] else 0,
        "probable_interruptions_by_rep": interruptions,
        "prospect_story_share_pct": story_share,
        "flags": flags,
        "verdict": f"Rep {rep_pct}% talk (benchmark {bench[0]}-{bench[1]}%), {rep_questions} questions, longest monologue {lr[1]} words. " + (flags[0] if flags else "Mechanics within benchmark."),
    }


@AGENT.tool
def detect_next_steps(transcript: str, call_date: str = "", rep_name: str = "") -> dict:
    """Find every commitment in a call, resolve its date, and judge whether a real next step (action + date + prospect buy-in) was agreed.

    Call after call_metrics. Returns candidates with speaker, resolved due date, and the verdict
    "next step agreed" or "no next step agreed" with what to propose.

    Args:
        transcript: Raw transcript text with "Name: text" lines.
        call_date: Date of the call YYYY-MM-DD (default today) — relative dates resolve against it.
        rep_name: The seller's name (default: first speaker).
    """
    base = c.to_date(call_date)
    turns = c.parse_transcript(transcript)
    labelled = [(s, t) for s, t in turns if s]
    if not labelled:
        raise ToolError("No 'Name: text' lines found.")
    order = list(dict.fromkeys(s for s, _ in labelled))
    rep = (c.match_speaker(rep_name, order) if rep_name else None) or order[0]
    cands = []
    for idx, (spk, said) in enumerate(labelled):
        if not COMMIT_RE.search(said):
            continue
        phrases = [m.group(0) for m in DATE_PHRASE_RE.finditer(said)]
        resolved_all = [d for d in (_resolve_phrase(ph, base) for ph in phrases) if d]
        resolved = min(resolved_all) if resolved_all else None
        # prospect agreement in the next two turns
        agreed_by_prospect = spk != rep
        if not agreed_by_prospect:
            for s2, t2 in labelled[idx + 1: idx + 3]:
                if s2 != rep and AGREE_RE.search(t2) and not re.search(r"\b(not|no|can'?t|won'?t|don'?t)\b", t2, re.I):
                    agreed_by_prospect = True
                    break
        has_action = bool(re.search(r"\b(send|schedule|set up|book|invite|intro(?:duce)?|loop in|share|review|sign|demo|pilot|trial|proposal|pricing|quote|call|meet(?:ing)?|workshop|reference)\b", said, re.I))
        score = int(has_action) + int(resolved is not None) + int(agreed_by_prospect)
        cands.append({
            "line": idx + 1,
            "speaker": spk,
            "text": said[:300],
            "date_phrases": phrases,
            "resolved_date": resolved.isoformat() if resolved else None,
            "resolved_weekday": resolved.strftime("%a") if resolved else None,
            "all_resolved_dates": [d.isoformat() for d in resolved_all],
            "has_action": has_action,
            "prospect_agreed": agreed_by_prospect,
            "quality": "next step" if score == 3 else "intention" if score == 2 else "mention",
        })
    real = sorted((x for x in cands if x["quality"] == "next step"), key=lambda x: x["resolved_date"])
    intentions = [x for x in cands if x["quality"] == "intention"]
    if real:
        best = real[0]
        verdict = f"Next step agreed: '{best['text'][:80]}' ({best['speaker']}, {best['resolved_date']})."
    elif intentions:
        best = intentions[0]
        missing = [k for k, v in (("a date", best["resolved_date"]), ("prospect agreement", best["prospect_agreed"]), ("a concrete action", best["has_action"])) if not v]
        verdict = f"No next step agreed — closest is '{best['text'][:80]}' but it lacks {' and '.join(missing)}. Propose a dated meeting in the follow-up."
    else:
        verdict = "No next step agreed and no commitment language found. The follow-up email must propose one with a date."
    return {
        "call_date": base.isoformat(),
        "rep": rep,
        "candidates": cands,
        "next_step_agreed": bool(real),
        "agreed_next_steps": real,
        "intentions": intentions,
        "verdict": verdict,
    }


POSITIVE = {
    "budget confirmed": r"\b(budget (?:is )?(?:approved|allocated|set aside|there)|we have budget|got budget|funding (?:is )?(?:approved|in place))\b",
    "timeline stated": r"\b(need (?:this|it) (?:by|before|live)|go[- ]live|by (?:end of )?q[1-4]|this quarter|before (?:the )?(?:renewal|contract ends|year end))\b",
    "stakeholders introduced": r"\b(loop in|bring in|introduce you to|i'?ll get (?:my|our) (?:cfo|cto|ceo|vp|boss|team|director)|my (?:boss|manager|cfo|cto|ceo) (?:wants|would like|should)|(?:cfo|cto|ceo|vp) (?:is|will be) (?:on|joining))\b",
    "implementation questions": r"\b(how long (?:does|would) (?:it|implementation|onboarding|setup) take|what does onboarding|migration|integrat(?:e|ion) with|training|rollout|roll out|who (?:would|will) (?:be )?(?:our|the) (?:point of contact|csm|account manager))\b",
    "future-state language": r"\b(when we (?:roll|go|switch|start|launch|move)|once we'?re (?:live|on|using)|after we (?:sign|start|switch)|our team (?:will|would) (?:use|love|be able))\b",
    "pricing/terms asked": r"\b(what (?:does|would) (?:it|this) cost|pricing|how much|discount|contract length|payment terms|annual|monthly|per seat|net ?30|msa|order form)\b",
    "pain quantified": r"\b(\d+\s?(?:hours?|%|percent|k|thousand|million|days?) (?:a|per|each) (?:week|month|quarter|year)|costs? us|losing|we lose)\b",
    "explicit interest": r"\b(this is (?:exactly|great|what we need)|love (?:this|it|that)|impressive|makes sense|i'?m (?:sold|convinced|excited)|let'?s move (?:forward|ahead)|next steps?)\b",
}
NEGATIVE = {
    "no budget (strong)": r"\b(no budget|don'?t have (?:the )?budget|budget (?:is )?(?:frozen|cut|gone)|can'?t afford|no money)\b",
    "chose competitor (strong)": r"\b(going with|signed with|chose|decided on|already (?:bought|signed)|moving forward with) [A-Z][\w]+\b",
    "no authority + no path (strong)": r"\b(not my (?:decision|call)|i can'?t (?:make|approve)|above my pay grade|i don'?t know who (?:decides|would sign))\b",
    "just exploring": r"\b(just (?:exploring|looking|curious|researching|browsing)|early (?:days|stage)|no (?:rush|urgency|timeline)|not (?:a )?priority|someday|down the road|nothing (?:planned|decided))\b",
    "send info / stall": r"\b(send (?:me|us|over) (?:some|more|the) (?:info|information|details|material)|think about it|get back to you|circle back|revisit (?:next|in)|let me think)\b",
    "competitor praise": r"\b(happy with|works (?:well|fine|great) for us|love (?:our current|the current|what we have)|no complaints|why (?:would|should) we (?:switch|change))\b",
    "price concern": r"\b(too expensive|way more than|(?:a bit |a little |bit |much )?(?:more|higher) than (?:we|our|what we) ?(?:budget(?:ed)?|planned|expected|pay|were expecting)|over (?:our )?budget|out of (?:our )?(?:budget|range)|can'?t justify|double what|sticker shock|(?:a bit|pretty|quite) (?:steep|pricey|expensive))\b",
    "decision far away": r"\b(next year|next fiscal|in (?:6|six|9|nine|12|twelve) months|after (?:the )?(?:reorg|merger|acquisition|audit|budget cycle)|when (?:we|things) (?:settle|calm))\b",
}
_POS = {k: re.compile(v, re.I) for k, v in POSITIVE.items()}
_NEG = {k: re.compile(v, re.I) for k, v in NEGATIVE.items()}


@AGENT.tool
def buying_signals(transcript: str, rep_name: str = "") -> dict:
    """Count positive and negative buying signals in the prospect's words and return a temperature (hot/warm/cool/cold) with quotes.

    Call after the metrics. Only prospect-side lines are scanned; strong negatives
    (no budget, chose competitor, no authority) override the count.

    Args:
        transcript: Raw transcript with "Name: text" lines.
        rep_name: The seller's name (default: first speaker); their lines are excluded.
    """
    turns = c.parse_transcript(transcript)
    labelled = [(s, t) for s, t in turns if s]
    if not labelled:
        raise ToolError("No 'Name: text' lines found.")
    order = list(dict.fromkeys(s for s, _ in labelled))
    rep = (c.match_speaker(rep_name, order) if rep_name else None) or order[0]
    pos, neg = [], []
    for idx, (spk, said) in enumerate(labelled):
        if spk == rep:
            continue
        for k, rx in _POS.items():
            m = rx.search(said)
            if m:
                pos.append({"signal": k, "speaker": spk, "line": idx + 1, "quote": said[max(0, m.start() - 60): m.end() + 60].strip()[:200]})
        for k, rx in _NEG.items():
            m = rx.search(said)
            if m:
                neg.append({"signal": k, "speaker": spk, "line": idx + 1, "quote": said[max(0, m.start() - 60): m.end() + 60].strip()[:200]})
    pos_types = {p["signal"] for p in pos}
    neg_types = {n["signal"] for n in neg}
    strong = [n for n in neg_types if "(strong)" in n]
    if strong:
        temp = "cold"
    elif len(pos_types) >= 3 and not neg_types:
        temp = "hot"
    elif len(pos_types) > len(neg_types):
        temp = "warm"
    elif len(pos_types) == 0 and len(neg_types) == 0:
        temp = "cool"
    else:
        temp = "cool"
    score = max(-10, min(10, len(pos_types) - 2 * len(strong) - len(neg_types - set(strong))))
    why = (
        f"strong negative: {', '.join(strong)}" if strong
        else f"{len(pos_types)} positive signal type(s) ({', '.join(sorted(pos_types))}) vs {len(neg_types)} negative" if pos_types or neg_types
        else "no buying language either way — the call stayed informational"
    )
    return {
        "rep_excluded": rep,
        "temperature": temp,
        "score": score,
        "positive_signals": pos,
        "negative_signals": neg,
        "positive_types": sorted(pos_types),
        "negative_types": sorted(neg_types),
        "strong_negatives": sorted(strong),
        "verdict": f"{temp.upper()} — {why}.",
    }


CRM_SCHEMAS = {
    "hubspot": {
        "object": "deal",
        "fields": {"stage": "dealstage", "amount": "amount", "close_date": "closedate", "next_step": "hs_next_step", "name": "dealname", "notes": "description", "owner": "hubspot_owner_id", "competitors": "competitors", "champion": "champion", "risks": "risks", "pipeline": "pipeline", "probability": "hs_forecast_probability"},
        # not HubSpot default deal properties — they must be created in the portal first
        "custom": {"competitors", "champion", "risks"},
        "stages": ["appointmentscheduled", "qualifiedtobuy", "presentationscheduled", "decisionmakerboughtin", "contractsent", "closedwon", "closedlost"],
        "stage_aliases": {"appointment": "appointmentscheduled", "qualified": "qualifiedtobuy", "discovery": "qualifiedtobuy", "demo": "presentationscheduled", "presentation": "presentationscheduled", "evaluation": "presentationscheduled", "proposal": "decisionmakerboughtin", "decision": "decisionmakerboughtin", "negotiation": "contractsent", "contract": "contractsent", "won": "closedwon", "lost": "closedlost"},
        "required": ["dealname", "dealstage", "amount", "closedate"],
        "date_format": "YYYY-MM-DD (HubSpot API accepts ISO 8601 midnight UTC)",
    },
    "salesforce": {
        "object": "Opportunity",
        "fields": {"stage": "StageName", "amount": "Amount", "close_date": "CloseDate", "next_step": "NextStep", "name": "Name", "notes": "Description", "owner": "OwnerId", "competitors": "Competitor__c", "champion": "Champion__c", "risks": "Risks__c", "probability": "Probability"},
        "custom": {"competitors", "champion", "risks"},
        "stages": ["Prospecting", "Qualification", "Needs Analysis", "Value Proposition", "Id. Decision Makers", "Perception Analysis", "Proposal/Price Quote", "Negotiation/Review", "Closed Won", "Closed Lost"],
        "stage_aliases": {"prospecting": "Prospecting", "qualification": "Qualification", "qualified": "Qualification", "discovery": "Needs Analysis", "demo": "Value Proposition", "evaluation": "Perception Analysis", "decision": "Id. Decision Makers", "proposal": "Proposal/Price Quote", "negotiation": "Negotiation/Review", "contract": "Negotiation/Review", "won": "Closed Won", "lost": "Closed Lost"},
        "required": ["Name", "StageName", "CloseDate"],
        "date_format": "YYYY-MM-DD",
    },
    "pipedrive": {
        "object": "deal",
        "fields": {"stage": "stage_id", "amount": "value", "close_date": "expected_close_date", "next_step": "next_activity_subject", "name": "title", "notes": "note", "owner": "user_id", "competitors": "competitors", "champion": "champion", "risks": "risks", "currency": "currency", "probability": "probability"},
        "custom": {"competitors", "champion", "risks"},
        "stages": ["Qualified", "Contact Made", "Demo Scheduled", "Proposal Made", "Negotiations Started", "Won", "Lost"],
        "stage_aliases": {"qualified": "Qualified", "qualification": "Qualified", "discovery": "Contact Made", "demo": "Demo Scheduled", "evaluation": "Demo Scheduled", "proposal": "Proposal Made", "negotiation": "Negotiations Started", "contract": "Negotiations Started", "won": "Won", "lost": "Lost"},
        "required": ["title", "stage_id", "value"],
        "date_format": "YYYY-MM-DD",
    },
}


@AGENT.tool
def map_crm_fields(fields: dict, crm: str = "hubspot", call_date: str = "") -> dict:
    """Validate debrief fields (stage, amount, close date, next step…) and map them to HubSpot, Salesforce or Pipedrive property names.

    Call last, with the values decided in the debrief. Checks stage names against the CRM's
    standard pipeline, date formats, amount parsing, next-step length/verb, and required fields.

    Args:
        fields: Dict with any of: name, stage, amount, close_date, next_step, next_step_date, notes, owner, competitors (list or str), champion, risks (list or str), probability, currency.
        crm: hubspot (default), salesforce or pipedrive.
        call_date: Date of the call YYYY-MM-DD; close dates before this are rejected.
    """
    crm_key = crm.strip().lower()
    if crm_key not in CRM_SCHEMAS:
        raise ToolError("crm must be hubspot, salesforce or pipedrive.")
    if not isinstance(fields, dict) or not fields:
        raise ToolError("fields must be a non-empty dict.")
    schema = CRM_SCHEMAS[crm_key]
    base = c.to_date(call_date)
    payload, issues, notes = {}, [], []
    custom_props: dict = {}
    next_due: str | None = None
    fmap = schema["fields"]
    for key, val in fields.items():
        k = str(key).strip().lower()
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        if k == "stage":
            raw = str(val).strip()
            low = raw.lower()
            match = next((s for s in schema["stages"] if s.lower() == low), None)
            if not match:
                alias_hit = next((v for a, v in schema["stage_aliases"].items() if a in low), None)
                if alias_hit:
                    match = alias_hit
                    notes.append(f"stage '{raw}' mapped to '{match}'")
            if not match:
                issues.append(f"stage '{raw}' is not a standard {crm_key} stage ({', '.join(schema['stages'][:5])}…); confirm the pipeline's custom stage")
                payload[fmap["stage"]] = raw
            else:
                payload[fmap["stage"]] = match
        elif k == "amount":
            raw_amt = str(val).replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip().lower()
            mult = 1.0
            m_suffix = re.match(r"^([\d.]+)\s*(k|m|mm|million|thousand)?$", raw_amt)
            if m_suffix and m_suffix.group(2):
                mult = 1_000.0 if m_suffix.group(2) in ("k", "thousand") else 1_000_000.0
                raw_amt = m_suffix.group(1)
            try:
                amt = float(raw_amt) * mult
            except ValueError:
                issues.append(f"amount {val!r} is not a number")
                continue
            if amt < 0:
                issues.append("amount is negative")
            payload[fmap["amount"]] = round(amt, 2)
        elif k in ("close_date", "next_step_date"):
            try:
                d = dates.parse_date(str(val))
            except ToolError:
                issues.append(f"{k} {val!r} is not YYYY-MM-DD")
                continue
            if d < base:
                issues.append(f"{k} {d.isoformat()} is before the call date {base.isoformat()}")
            if k == "close_date":
                payload[fmap["close_date"]] = d.isoformat()
                if (d - base).days > 365:
                    issues.append("close date more than a year out — is this real pipeline?")
            else:
                next_due = d.isoformat()
        elif k == "next_step":
            ns = str(val).strip()
            if len(ns) > 80:
                issues.append(f"next step is {len(ns)} chars — cut to ≤ 80")
            if not re.match(r"^(send|schedule|book|review|intro|introduce|share|confirm|call|meet|present|demo|sign|draft|follow|prepare|deliver|loop|set|get|agree|run|hold|complete|finalise|finalize)\b", ns, re.I):
                issues.append("next step should start with a verb (Send…, Schedule…, Introduce…)")
            if not re.search(r"\d", ns) and not fields.get("next_step_date"):
                issues.append("next step has no date — add next_step_date")
            payload[fmap["next_step"]] = ns
        elif k in ("competitors", "risks"):
            items = val if isinstance(val, list) else [x.strip() for x in re.split(r"[,;]", str(val)) if x.strip()]
            custom_props[fmap[k]] = "; ".join(str(x) for x in items)
        elif k in schema["custom"]:
            custom_props[fmap[k]] = str(val).strip()
        elif k == "probability":
            try:
                p = float(val)
            except (TypeError, ValueError):
                issues.append("probability must be a number")
                continue
            if p <= 1:
                p *= 100
            if not 0 <= p <= 100:
                issues.append("probability must be 0-100")
            if crm_key == "hubspot":
                # HubSpot's "Forecast probability" is a 0-1 number; "Deal probability" is set by the stage and can't be written
                payload[fmap["probability"]] = round(p / 100, 2)
                notes.append("probability written to hs_forecast_probability (0-1); HubSpot's deal-stage probability follows the stage")
            else:
                payload[fmap.get("probability", "probability")] = round(p)
        elif k in fmap:
            payload[fmap[k]] = str(val).strip()
        else:
            payload[f"custom:{k}"] = val
            notes.append(f"'{k}' has no standard {crm_key} property — mapped as custom")
    missing = [r for r in schema["required"] if r not in payload]
    if missing:
        issues.append(f"required for {crm_key}: {', '.join(missing)}")
    if custom_props:
        notes.append(
            f"{', '.join(sorted(custom_props))} are not standard {crm_key} fields — create them as custom properties "
            "(or append them to the notes/description) before pushing, or the API rejects the update"
        )
    if next_due:
        notes.append(f"next-step date {next_due} is not a deal field in {crm_key} — create a task/activity due that day")
    return {
        "crm": crm_key,
        "object": schema["object"],
        "payload": payload,
        "custom_properties": custom_props,
        "next_step_task_due": next_due,
        "missing_required": missing,
        "issues": issues,
        "notes": notes,
        "date_format": schema["date_format"],
        "ready": not issues,
        "verdict": f"{len(payload)} standard {crm_key} propert(ies) mapped" + (f" + {len(custom_props)} custom" if custom_props else "") + "; " + (f"{len(issues)} issue(s): {issues[0]}" if issues else ("valid; push once the custom properties exist." if custom_props else "valid and ready to push.")),
    }
