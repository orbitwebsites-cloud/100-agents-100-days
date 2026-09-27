"""Interview Synthesizer — turns raw user-interview notes into evidence-backed themes and insights."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from ...core import Agent, ToolError
from ...lib import text
from ._common import check_rows, check_text, jaccard, pct, term_set

AGENT = Agent(
    slug="interview-synthesizer",
    name="Interview Synthesizer",
    category="product",
    tagline="Turn a pile of user interviews into counted themes, verbatim evidence, and decisions you can defend.",
    description=(
        "Runs a research synthesis the way a lead UX researcher does: pulls high-signal quotes (pain, "
        "workarounds, wishes, money, frequency) out of raw notes, counts how many *interviews* — not "
        "mentions — support each theme, splits by segment, clusters similar observations by keyword "
        "affinity, and tells you whether you have reached saturation or need more sessions. Every "
        "insight ships with its evidence count and verbatim quotes, so nobody can dismiss it as anecdote."
    ),
    triggers=[
        "synthesize these user interviews",
        "find themes in customer research notes",
        "affinity map / cluster these observations",
        "how many users mentioned this problem",
        "do we need more interviews (saturation)",
        "pull the best quotes from these transcripts",
    ],
    examples=[
        "Here are notes from 8 customer interviews about onboarding — what are the top themes and how strong is the evidence?",
        "Cluster these 60 sticky-note observations from our discovery sprint into insights.",
        "I've tagged 12 interviews with pain points; count the tags by segment (SMB vs enterprise) and tell me if we've hit saturation.",
    ],
    connectors=["Notion", "Google Docs", "Dovetail", "Airtable", "Google Sheets"],
    playbook="""
    ## Standard
    You are a lead user researcher. Excellent synthesis has three properties: every insight is
    stated as a *finding about users*, not a feature request; every finding carries an evidence
    count ("6 of 8 interviews, all SMB") and 2-3 verbatim quotes; and the reader knows what to do
    next. The one metric that matters is **decisions made from the research** — so the output ends
    with recommended decisions, ranked by evidence strength.

    ## Intake
    Work with whatever you have. Ask (max 3) only if missing: (1) the research question the study
    was meant to answer, (2) how many interviews and which segments, (3) whether the notes are
    verbatim transcripts or interviewer summaries (summaries carry interviewer bias — say so).
    If interviews are not clearly delimited, split on obvious headers ("Interview 3", "P4", names)
    and state how you split.

    ## Procedure
    1. **Mine each interview for signal.** Call `interview_synthesizer__extract_signals` with each
       interview's text (or all, delimited). It returns candidate quotes ranked by signal type:
       pain ("frustrating", "hate", "waste"), workaround ("I just export to Excel"), wish ("I wish",
       "if only"), money/frequency ("every week", "$400/month"), and switching intent. Read each in
       context; a quote is only evidence if it describes the user's actual behaviour, not a
       hypothetical ("I would probably…").
    2. **Tag observations.** Write one observation per sticky note: a single behaviour or belief, in
       the user's words where possible, tagged with interview ID and segment. 20-40 per interview
       is normal for a 45-minute session.
    3. **Cluster.** Call `interview_synthesizer__cluster_observations` with the observations. It
       groups them by keyword affinity (Jaccard on content words, threshold 0.25 by default) and
       returns clusters with member counts and the distinct interviews backing each. Rename every
       cluster as an insight sentence ("Ops managers rebuild the same report weekly because exports
       lose formatting"), never a topic label ("Exports").
    4. **Count properly.** Call `interview_synthesizer__tag_frequency` with your tagged observations.
       It counts *interviews mentioning* each tag (the number that matters) separately from total
       mentions (which one talkative user can inflate), breaks it down by segment, and computes
       co-occurrence so you can see which pains travel together.
    5. **Check saturation.** Call `interview_synthesizer__saturation_check` with the ordered list of
       tags-per-interview. It computes new-theme discovery per session: when the last 3 interviews
       each surfaced < 1 new theme, you have saturated for this segment (Guest et al. found ~12
       interviews reach ~92% of themes in homogeneous groups; 5-6 for narrow usability questions).
       If not saturated, say how many more sessions and in which segment.
    6. **Rank findings** by evidence strength: strong = ≥ 50% of interviews across ≥ 2 segments;
       moderate = ≥ 30% or concentrated in one segment; weak = < 30% (report as "signal to watch").
    7. **Write the synthesis** in the output format. Findings first, quotes attached, then
       recommended decisions with the evidence that supports each, then what you still don't know.
    8. **File it** if Notion/Docs/Dovetail is connected; otherwise output ready to paste.

    ## Frameworks
    - **Observation → Insight → Opportunity:** observation is what you saw; insight is why (a
      tension, a motivation); opportunity is a "How might we…". Never skip the insight step.
    - **Evidence hierarchy:** observed behaviour > described past behaviour > stated preference >
      hypothetical future behaviour. Weight quotes accordingly.
    - **Jobs-to-be-done phrasing** for insights: "When [situation], I want to [motivation], so I can
      [outcome] — but [obstacle]."
    - **Interviewer-bias check:** if an insight appears only in interviews run by one interviewer,
      flag it.

    ## Output format
    ```
    # Research synthesis: <study name> — <date>
    **Sessions:** N interviews · **Segments:** A (n), B (n) · **Saturation:** reached / not reached (+k sessions in <segment>)
    **Research question:** <one sentence>

    ## Top findings (ranked by evidence)
    ### 1. <Insight sentence>                                  Evidence: strong — 6/8 interviews, SMB 4/4, ENT 2/4
    - Observation: <what users do today>
    - Why it matters: <consequence / cost>
    - "<verbatim quote>" — P3, SMB
    - "<verbatim quote>" — P7, ENT
    - Opportunity: How might we <…>?
    ### 2. …

    ## Signals to watch (weak evidence)
    - <finding> — 2/8, one segment

    ## Recommended decisions
    | # | Decision | Backed by finding | Confidence |

    ## What we still don't know
    - <question> → next study
    ```

    ## Anti-patterns
    - Counting mentions instead of interviews. One user saying it five times is one data point.
    - Topic labels as findings ("Pricing", "Onboarding"). A finding is a sentence with a verb.
    - Treating "I would use that" as evidence. Only past/current behaviour counts.
    - Reporting every theme. Rank; cut anything below 2 interviews unless it's a critical risk.
    - Dropping the segment split. A pain that is 100% enterprise / 0% SMB is a different product decision.
    - Insights without quotes. Stakeholders trust users, not researchers.
    """,
)

SIGNALS: dict[str, re.Pattern] = {
    "pain": re.compile(r"\b(frustrat|annoy|hate|painful|pain\b|waste|wasting|nightmare|confus|struggl|difficult|hard to|can'?t|cannot|impossible|broken|slow|tedious|manual|error|fail|lost|worst|terrible|ugh)", re.I),
    "workaround": re.compile(r"\b(workaround|work around|i just|so i|instead i|hack|spreadsheet|excel|manually|copy[- ]paste|by hand|export(?:ed)? to|end up|ended up)\b", re.I),
    "wish": re.compile(r"\b(i wish|if only|would love|would be (?:great|nice|amazing)|it'?d be|should be able|why can'?t|i'?d like|ideally|dream)\b", re.I),
    "money_frequency": re.compile(r"(\$\s?\d[\d,.]*k?|\d+\s?(?:dollars|usd|eur|gbp|€|£)|\b(?:every|each|per)\s+(?:day|week|month|hour|morning|sprint)|\b(?:daily|weekly|monthly|hourly)\b|\b\d+\s*(?:hours?|minutes?|mins?|times|x)\s+(?:a|per|each)\s+(?:day|week|month))", re.I),
    "switching": re.compile(r"\b(switch(?:ed|ing)?|cancel(?:led|ing)?|churn|moved to|left|tried \w+ instead|competitor|alternative|looking at|evaluat)", re.I),
    "hypothetical": re.compile(r"\b(i would (?:probably|maybe|definitely)?\s?(?:use|try|pay|buy|want)|might use|could see myself|in theory|hypothetically|if you built)\b", re.I),
}
_SPLIT_RE = re.compile(r"(?m)^\s*(?:#+\s*)?(?:interview|participant|session|user)\s*#?\s*(\d+|[A-Z])\b[^\n]*$|(?m)^\s*(P\d{1,3})\b[^\n]*$", re.I)


def _split_interviews(notes: str) -> list[tuple[str, str]]:
    marks = list(_SPLIT_RE.finditer(notes))
    if len(marks) < 2:
        return [("all", notes)]
    out = []
    for i, m in enumerate(marks):
        label = (m.group(1) or m.group(2) or str(i + 1)).strip()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(notes)
        out.append((f"P{label}" if label.isdigit() else label.upper(), notes[m.end():end]))
    return out


@AGENT.tool
def extract_signals(notes: str, max_quotes: int = 40) -> dict:
    """Pull high-signal quotes (pain, workaround, wish, money/frequency, switching) out of interview notes.

    Splits on "Interview N" / "P4" headers when present. Scores each sentence by signal type and
    marks hypotheticals ("I would probably use…") so you don't count them as evidence.

    Args:
        notes: Raw interview notes or transcript(s); multiple interviews may be delimited by headers.
        max_quotes: Maximum quotes to return, best first (default 40, max 200).
    """
    body = check_text(notes, "notes")
    if not isinstance(max_quotes, int) or not 1 <= max_quotes <= 200:
        raise ToolError("max_quotes must be an integer between 1 and 200.")
    interviews = _split_interviews(body)
    quotes, per_type = [], Counter()
    for label, chunk in interviews:
        for sent in text.sentences(chunk):
            if len(text.words(sent)) < 4:
                continue
            hits = [k for k, rx in SIGNALS.items() if k != "hypothetical" and rx.search(sent)]
            if not hits:
                continue
            hypothetical = bool(SIGNALS["hypothetical"].search(sent))
            score = len(hits) * 2 + (1 if SIGNALS["money_frequency"].search(sent) else 0) - (3 if hypothetical else 0)
            for h in hits:
                per_type[h] += 1
            quotes.append({"interview": label, "quote": sent.strip()[:300], "signals": hits, "hypothetical": hypothetical, "score": score})
    quotes.sort(key=lambda q: (-q["score"], q["interview"]))
    kept = quotes[:max_quotes]
    return {
        "interviews_detected": [lbl for lbl, _ in interviews],
        "interview_count": len(interviews),
        "total_candidates": len(quotes),
        "by_signal": dict(per_type),
        "hypothetical_count": sum(1 for q in quotes if q["hypothetical"]),
        "quotes": kept,
        "summary": f"{len(quotes)} signal sentences across {len(interviews)} interview(s); top signal: "
        + (per_type.most_common(1)[0][0] if per_type else "none"),
        "next_step": "Read each quote in context; drop hypotheticals; write one observation per real behaviour.",
    }


@AGENT.tool
def cluster_observations(observations: list[dict], threshold: float = 0.25) -> dict:
    """Group observations into affinity clusters by keyword overlap, with distinct-interview counts.

    Single-link clustering on Jaccard similarity of content words. Returns clusters (largest first)
    with member texts, interviews backing each, and shared keywords to help you name the insight.

    Args:
        observations: List of {"text": str, "interview": str, "segment": str (optional)}; up to 500.
        threshold: Jaccard similarity needed to link two observations (0.1-0.9; default 0.25).
    """
    rows = check_rows(observations, "observations")
    if not isinstance(threshold, (int, float)) or not 0.1 <= threshold <= 0.9:
        raise ToolError("threshold must be between 0.1 and 0.9.")
    items = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("text", "")).strip():
            raise ToolError(f"observations[{i}] needs a non-empty 'text'.")
        items.append({"text": str(raw["text"]).strip(), "interview": str(raw.get("interview", "?")), "segment": str(raw.get("segment", "")) or None, "terms": term_set(str(raw["text"]))})
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if jaccard(items[i]["terms"], items[j]["terms"]) >= threshold:
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    clusters = []
    for members in sorted(groups.values(), key=lambda g: (-len(g), g[0])):
        shared = Counter(w for m in members for w in items[m]["terms"])
        interviews = sorted({items[m]["interview"] for m in members})
        segs = Counter(items[m]["segment"] for m in members if items[m]["segment"])
        clusters.append({
            "size": len(members),
            "interviews": interviews,
            "interview_count": len(interviews),
            "segments": dict(segs),
            "keywords": [w for w, c in shared.most_common(6) if c >= max(2, len(members) // 2) or len(members) == 1][:6],
            "members": [items[m]["text"] for m in members][:25],
        })
    singletons = sum(1 for c in clusters if c["size"] == 1)
    return {
        "clusters": clusters,
        "cluster_count": len(clusters),
        "singletons": singletons,
        "threshold": threshold,
        "summary": f"{n} observations → {len(clusters)} clusters ({singletons} singletons). "
        + ("Lower the threshold if too fragmented; raise it if clusters mix topics." if singletons > n / 2 else "Name each cluster as an insight sentence."),
    }


@AGENT.tool
def tag_frequency(tagged: list[dict]) -> dict:
    """Count how many interviews mention each tag (not raw mentions), split by segment, with co-occurrence.

    Args:
        tagged: List of {"interview": str, "tags": [str, ...], "segment": str (optional)} — one row per observation or per interview.
    """
    rows = check_rows(tagged, "tagged")
    interviews_by_tag: dict[str, set] = defaultdict(set)
    mentions: Counter = Counter()
    seg_by_tag: dict[str, Counter] = defaultdict(Counter)
    tags_by_interview: dict[str, set] = defaultdict(set)
    seg_of: dict[str, str] = {}
    all_interviews: set = set()
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not raw.get("interview"):
            raise ToolError(f"tagged[{i}] needs an 'interview' id and a 'tags' list.")
        tags = raw.get("tags") or []
        if not isinstance(tags, list):
            raise ToolError(f"tagged[{i}].tags must be a list of strings.")
        iv = str(raw["interview"]).strip()
        seg = str(raw.get("segment", "")).strip() or None
        all_interviews.add(iv)
        if seg:
            seg_of[iv] = seg
        for t in tags:
            tag = str(t).strip().lower()
            if not tag:
                continue
            mentions[tag] += 1
            interviews_by_tag[tag].add(iv)
            tags_by_interview[iv].add(tag)
    n_iv = len(all_interviews)
    seg_sizes = Counter(seg_of.values())
    for tag, ivs in interviews_by_tag.items():
        for iv in ivs:
            if iv in seg_of:
                seg_by_tag[tag][seg_of[iv]] += 1
    table = []
    for tag, ivs in sorted(interviews_by_tag.items(), key=lambda kv: (-len(kv[1]), -mentions[kv[0]], kv[0])):
        share = pct(len(ivs), n_iv)
        segs = {s: f"{c}/{seg_sizes[s]}" for s, c in seg_by_tag[tag].items()}
        strength = "strong" if share >= 50 and len(segs) >= 2 else "strong (single segment)" if share >= 50 else "moderate" if share >= 30 else "weak"
        table.append({"tag": tag, "interviews": len(ivs), "interview_pct": share, "mentions": mentions[tag], "by_segment": segs, "strength": strength})
    pairs: Counter = Counter()
    for tags in tags_by_interview.values():
        ts = sorted(tags)
        for a in range(len(ts)):
            for b in range(a + 1, len(ts)):
                pairs[(ts[a], ts[b])] += 1
    cooc = [{"tags": list(k), "interviews": v} for k, v in pairs.most_common(10) if v >= 2]
    return {
        "interview_count": n_iv,
        "segment_sizes": dict(seg_sizes),
        "tags": table,
        "co_occurrence": cooc,
        "summary": f"{len(table)} tags across {n_iv} interviews; "
        + (f"top: '{table[0]['tag']}' in {table[0]['interviews']}/{n_iv}" if table else "no tags"),
    }


@AGENT.tool
def saturation_check(tags_per_interview: list[list[str]], window: int = 3) -> dict:
    """Compute new-theme discovery per interview to decide whether you've reached saturation.

    Args:
        tags_per_interview: Ordered list (chronological) of the tags/themes surfaced in each interview.
        window: How many trailing interviews must each add < 1 new theme to call saturation (default 3).
    """
    rows = check_rows(tags_per_interview, "tags_per_interview")
    if not isinstance(window, int) or not 2 <= window <= 10:
        raise ToolError("window must be an integer between 2 and 10.")
    seen: set = set()
    curve = []
    for i, tags in enumerate(rows, 1):
        if not isinstance(tags, list):
            raise ToolError(f"tags_per_interview[{i - 1}] must be a list of strings.")
        ts = {str(t).strip().lower() for t in tags if str(t).strip()}
        new = ts - seen
        seen |= ts
        curve.append({"interview": i, "new_themes": len(new), "cumulative": len(seen), "new_list": sorted(new)[:10]})
    total = len(seen)
    tail = curve[-window:]
    saturated = len(curve) >= window and all(c["new_themes"] == 0 for c in tail)
    near = len(curve) >= window and sum(c["new_themes"] for c in tail) <= 1
    tail_rate = sum(c["new_themes"] for c in tail) / max(1, len(tail))
    if saturated:
        rec, more = "Saturated for this population — stop recruiting, start synthesis.", 0
    elif near:
        rec, more = "Nearly saturated — run 1-2 more to confirm, then stop.", 2
    else:
        # estimate: remaining themes ~ tail_rate decays; recommend sessions until rate < 0.5
        more = max(3, min(8, round(tail_rate * 3)))
        rec = f"Not saturated — themes still appearing at ~{tail_rate:.1f}/interview; plan ~{more} more sessions."
    return {
        "interviews": len(curve),
        "total_themes": total,
        "curve": curve,
        "trailing_new_per_interview": round(tail_rate, 2),
        "saturated": saturated,
        "recommended_additional_interviews": more,
        "verdict": rec,
        "benchmark": "Homogeneous group: ~6 interviews find ~80% of themes, ~12 find ~92% (Guest, Bunce & Johnson 2006).",
    }
