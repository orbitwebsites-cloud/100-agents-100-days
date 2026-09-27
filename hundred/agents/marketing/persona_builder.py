"""Persona Builder — evidence-based personas: survey tallies, cross-tabs, JTBD statements and a completeness scorecard."""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

from ...core import Agent, ToolError
from ...lib import text
from ._common import chi2_sf

AGENT = Agent(
    slug="persona-builder",
    name="Persona Builder",
    category="marketing",
    tagline="Build personas from evidence, not vibes: tally the research, find the segments that differ, and write jobs-to-be-done.",
    description=(
        "Turns interview notes and survey exports into personas a team will actually use. Tallies "
        "single- and multi-select answers with percentages, summarises numeric fields, cross-tabs "
        "any two questions with a chi-square test so you know which differences are real, formats "
        "jobs-to-be-done statements and job stories with a lint for solution-speak, and scores each "
        "persona for completeness and evidence so demographic fan-fiction never ships."
    ),
    triggers=[
        "build a customer persona / buyer persona",
        "analyze survey results or interview notes",
        "jobs to be done statement",
        "segment our users",
        "which persona should we target",
        "ideal customer profile",
    ],
    examples=[
        "Here's a CSV export of 140 survey responses. Tally it and tell me what segments exist.",
        "From these 12 interview notes, write 2 personas with JTBD statements.",
        "Do enterprise respondents care more about SSO than SMB ones? Here's the data.",
    ],
    connectors=["Google Sheets", "Notion", "HubSpot", "Typeform", "Airtable"],
    playbook="""
    ## Standard
    You are a customer researcher who has built personas that sales and product both used.
    Excellent means: every trait on the persona traces to a count, a quote or an interview;
    segments are separated by behaviour and job, not by demographics; the job-to-be-done is
    written without the product in it; and the persona says what to build, say and where
    to find them. The metric that matters is whether a team member can make a decision with
    it ("would Priya buy this?") without asking you.

    ## Intake
    Need: raw evidence (survey rows, interview notes, support tickets, CRM fields) and the
    decision the persona is for (messaging, roadmap, targeting). If there's no evidence at
    all, say you'll produce a *provisional* persona labelled as hypotheses with a research
    plan — never present guesses as findings. Ask at most 3 questions.

    ## Procedure
    1. **Tally the data.** Call `persona_builder__tally_survey` with the rows. Read the
       distributions; note fields where one answer dominates (> 60 %) and fields that split
       (no answer > 40 %) — splits are candidate segment boundaries.
    2. **Find real differences.** For each candidate split, call
       `persona_builder__cross_tab` against the outcome you care about (pain, willingness
       to pay, tool used). Only differences with p < 0.05 and n ≥ 30 per group earn a
       separate persona; otherwise merge.
    3. **Write the job.** For each persona call `persona_builder__format_jtbd` with the
       situation, motivation and outcome pulled from quotes. Remove solution words the tool
       flags; the job must be true even if your product vanished.
    4. **Draft the persona** using the template, one page max. Every claim gets an
       evidence tag: (n=42, 61 %) or a quote with the interview ID.
    5. **Score it.** Call `persona_builder__persona_scorecard` with the persona fields. Fix
       anything below "complete"; never ship a persona with < 5 interviews or 30 survey
       rows behind it without a "provisional" label.
    6. **Deliver** in the output format, with the "how to use this" line: which messages,
       channels and roadmap bets follow from it.

    ## Frameworks
    - **JTBD statement:** When [situation], I want to [motivation], so I can [outcome].
      Job story variant for product teams. Include the four forces: push (of the current
      situation), pull (of the new solution), anxiety (about the new), habit (of the old).
    - **Segment by job and behaviour** (tools used, frequency, trigger event, budget
      authority), not by age/gender unless the data proves they change behaviour.
    - **Evidence floor:** 5-8 interviews per segment reaches saturation; surveys need
      ≥ 30 per group before percentages mean anything; cross-tab cells < 5 make chi-square
      unreliable (the tool warns).
    - **Buying roles:** champion, economic buyer, user, blocker — a B2B persona says which.
    - **Persona anatomy (one page):** name + role, JTBD, trigger event, current alternative,
      top 3 pains (with quotes), success metric, objections, buying role, channels/
      watering holes, a verbatim quote, evidence count.
    - **Anti-persona:** one paragraph on who looks similar but is a bad fit and why.

    ## Output format
    ```
    # Persona — <Name>, <role> (<segment>) · evidence: <n> interviews, <n> survey rows
    **Job:** When <situation>, I want to <motivation>, so I can <outcome>.
    **Trigger:** <event> · **Today they use:** <alternative> · **Buying role:** <role>

    | Trait | Finding | Evidence |
    |---|---|---|
    | Top pains | 1… 2… 3… | (n=…, %) / quote #id |
    | Success looks like | … | … |
    | Objections | … | … |
    | Where to reach | … | … |

    **In their words:** "<verbatim quote>" — <interview id>
    **Anti-persona:** <who looks similar but isn't a fit>
    **How to use this:** message → …, channel → …, roadmap → …
    ```

    ## Anti-patterns
    - Stock-photo personas with a favourite coffee and no job.
    - Percentages from 9 responses.
    - Segments that don't behave differently (same pains, same tools) — merge them.
    - JTBD that contains the product ("I want to use <Product> to…").
    - Four personas when the team can act on one.
    - Quoting the loudest interview as if it were the median.
    """,
)


def _is_number(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    try:
        float(str(v).replace(",", "").replace("%", "").strip())
        return True
    except ValueError:
        return False


def _split_multi(v) -> list[str]:
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v)
    if ";" in s or "|" in s:
        return [p.strip() for p in re.split(r"[;|]", s) if p.strip()]
    return [s.strip()] if s.strip() else []


@AGENT.tool
def tally_survey(responses: list[dict], multi_select_fields: list[str] = [], numeric_fields: list[str] = [], top_n: int = 8) -> dict:
    """Tally survey responses per field: counts and percentages for choices, mean/median/range for numbers, missing rates, and which fields split the sample.

    Call first with the rows (one dict per respondent). Multi-select answers may be lists or ';'-separated strings.

    Args:
        responses: List of respondent dicts, e.g. [{"role": "Ops", "tools": "Slack;Asana", "team_size": 12}, ...]. Max 5,000 rows.
        multi_select_fields: Fields whose answers are multi-select (auto-detected when values are lists or contain ';').
        numeric_fields: Fields to summarise as numbers (auto-detected when ≥ 80% of values are numeric).
        top_n: Number of top answers to return per field (default 8).
    """
    if not responses:
        raise ToolError("responses is empty.")
    if len(responses) > 5000:
        raise ToolError("Max 5,000 responses per call.")
    if not all(isinstance(r, dict) for r in responses):
        raise ToolError("Each response must be an object of field → answer.")
    if not 1 <= top_n <= 50:
        raise ToolError("top_n must be 1-50.")
    n = len(responses)
    fields: list[str] = []
    for r in responses:
        for k in r:
            if k not in fields:
                fields.append(k)
    if len(fields) > 200:
        raise ToolError("Max 200 fields.")
    multi = set(multi_select_fields)
    numeric = set(numeric_fields)
    out_fields = {}
    splits, dominants = [], []
    for f in fields:
        vals = [r.get(f) for r in responses]
        present = [v for v in vals if v is not None and str(v).strip() != ""]
        missing = n - len(present)
        if not present:
            out_fields[f] = {"type": "empty", "missing": missing}
            continue
        is_multi = f in multi or any(isinstance(v, (list, tuple)) or (isinstance(v, str) and ";" in v) for v in present)
        is_num = f in numeric or (not is_multi and sum(1 for v in present if _is_number(v)) >= 0.8 * len(present) and len({str(v) for v in present}) > 2)
        if is_num:
            nums = [float(str(v).replace(",", "").replace("%", "")) for v in present if _is_number(v)]
            q = statistics.quantiles(nums, n=4) if len(nums) >= 4 else [min(nums), statistics.median(nums), max(nums)]
            out_fields[f] = {"type": "numeric", "n": len(nums), "missing": missing, "mean": round(statistics.fmean(nums), 2), "median": round(statistics.median(nums), 2), "min": min(nums), "max": max(nums), "p25": round(q[0], 2), "p75": round(q[-1], 2), "stdev": round(statistics.pstdev(nums), 2) if len(nums) > 1 else 0.0}
            continue
        counter: Counter[str] = Counter()
        for v in present:
            for a in (_split_multi(v) if is_multi else [str(v).strip()]):
                counter[a] += 1
        base = len(present)
        top = [{"answer": a, "count": c, "pct": round(100 * c / base, 1)} for a, c in counter.most_common(top_n)]
        out_fields[f] = {"type": "multi_select" if is_multi else "single_choice", "n": base, "missing": missing, "distinct": len(counter), "top": top, "pct_base": "respondents who answered"}
        if not is_multi and top:
            if top[0]["pct"] >= 60:
                dominants.append(f"{f}: {top[0]['answer']} ({top[0]['pct']}%)")
            elif top[0]["pct"] <= 40 and len(counter) <= 8:
                splits.append(f"{f}: top answer only {top[0]['pct']}% across {len(counter)} options")
    warn = []
    if n < 30:
        warn.append(f"Only {n} responses — percentages are indicative; don't split into segments below 30 per group.")
    return {
        "responses": n,
        "fields": out_fields,
        "dominant_answers": dominants,
        "split_fields": splits,
        "warnings": warn,
        "summary": f"{n} responses, {len(fields)} fields. {len(splits)} field(s) split the sample (segment candidates); {len(dominants)} dominated by one answer.",
    }


@AGENT.tool
def cross_tab(responses: list[dict], row_field: str, col_field: str, max_categories: int = 8) -> dict:
    """Cross-tabulate two survey fields with row percentages and a chi-square test of independence (is the difference real?).

    Call to confirm a segment candidate actually behaves differently on an outcome field.

    Args:
        responses: List of respondent dicts.
        row_field: The segment field (e.g. "company_size").
        col_field: The outcome field (e.g. "top_pain").
        max_categories: Keep only the most common categories per field (others grouped as "other").
    """
    if not responses or len(responses) > 5000:
        raise ToolError("Provide 1-5,000 responses.")
    if not 2 <= max_categories <= 20:
        raise ToolError("max_categories must be 2-20.")
    pairs = []
    for r in responses:
        if not isinstance(r, dict):
            raise ToolError("Each response must be an object.")
        a, b = r.get(row_field), r.get(col_field)
        if a is None or b is None or str(a).strip() == "" or str(b).strip() == "":
            continue
        pairs.append((str(a).strip(), str(b).strip()))
    if len(pairs) < 4:
        raise ToolError(f"Need at least 4 responses with both '{row_field}' and '{col_field}' answered; got {len(pairs)}.")
    rc, cc = Counter(p[0] for p in pairs), Counter(p[1] for p in pairs)
    keep_r = [k for k, _ in rc.most_common(max_categories)]
    keep_c = [k for k, _ in cc.most_common(max_categories)]
    table: dict[str, Counter] = defaultdict(Counter)
    for a, b in pairs:
        ra = a if a in keep_r else "other"
        cb = b if b in keep_c else "other"
        table[ra][cb] += 1
    rows = list(table)
    cols = sorted({c for r in rows for c in table[r]}, key=lambda c: -sum(table[r][c] for r in rows))
    N = len(pairs)
    matrix, small_cells = [], 0
    for r in rows:
        tot = sum(table[r].values())
        matrix.append({"row": r, "n": tot, "counts": {c: table[r][c] for c in cols}, "row_pct": {c: round(100 * table[r][c] / tot, 1) for c in cols}})
    chi2 = 0.0
    for r in rows:
        rt = sum(table[r].values())
        for c in cols:
            ct = sum(table[x][c] for x in rows)
            e = rt * ct / N
            if e < 5:
                small_cells += 1
            if e > 0:
                chi2 += (table[r][c] - e) ** 2 / e
    df = (len(rows) - 1) * (len(cols) - 1)
    p = chi2_sf(chi2, df) if df >= 1 else 1.0
    cramers_v = (chi2 / (N * (min(len(rows), len(cols)) - 1))) ** 0.5 if min(len(rows), len(cols)) > 1 and N else 0.0
    # Largest difference: the (row, col) with biggest deviation in row pct from the overall col pct.
    overall = {c: 100 * sum(table[r][c] for r in rows) / N for c in cols}
    biggest = max(((m["row"], c, m["row_pct"][c] - overall[c]) for m in matrix for c in cols), key=lambda t: abs(t[2]))
    warnings = []
    if small_cells:
        warnings.append(f"{small_cells} cell(s) have expected count < 5 — chi-square is unreliable; merge categories or collect more data.")
    small_groups = [m["row"] for m in matrix if m["n"] < 30]
    if small_groups:
        warnings.append(f"Groups under 30 responses: {', '.join(small_groups)} — treat their percentages as directional.")
    significant = p < 0.05
    return {
        "row_field": row_field,
        "col_field": col_field,
        "n": N,
        "table": matrix,
        "columns": cols,
        "overall_col_pct": {c: round(v, 1) for c, v in overall.items()},
        "chi_square": round(chi2, 3),
        "df": df,
        "p_value": round(p, 5),
        "cramers_v": round(cramers_v, 3),
        "significant_at_05": significant,
        "biggest_difference": {"row": biggest[0], "col": biggest[1], "pct_points_vs_overall": round(biggest[2], 1)},
        "warnings": warnings,
        "summary": (f"{'Real difference' if significant else 'No significant difference'} between {row_field} groups on {col_field} (χ²={chi2:.2f}, df={df}, p={p:.3f}, V={cramers_v:.2f}). Biggest: '{biggest[0]}' is {biggest[2]:+.1f} pts on '{biggest[1]}'."),
    }


SOLUTION_WORDS = re.compile(r"\b(app|software|tool|platform|dashboard|feature|button|plugin|integration|ai|automation|our product|the product|subscription|login|interface|template)\b", re.I)
SITUATION_CUES = re.compile(r"\b(when|after|before|during|every|each|while|at the (start|end)|first time|once|whenever|as soon as|the moment|on (monday|friday)|quarter|month|week|morning|deadline)\b", re.I)


@AGENT.tool
def format_jtbd(situation: str, motivation: str, outcome: str, persona: str = "", product_names: list[str] = []) -> dict:
    """Format a jobs-to-be-done statement and job story, and lint them for solution-speak, weak situations and restated outcomes.

    Call per persona once quotes are gathered. The job must stay true if your product vanished.

    Args:
        situation: The context / trigger ("When …").
        motivation: What they want to do ("I want to …"), verb-first.
        outcome: The result they're after ("so I can …").
        persona: Optional persona name for the job story.
        product_names: Your product/feature names; flagged if they appear in the job.
    """
    for k, v in (("situation", situation), ("motivation", motivation), ("outcome", outcome)):
        if not str(v or "").strip():
            raise ToolError(f"{k} is empty.")
        if len(str(v)) > 500:
            raise ToolError(f"{k} is over 500 chars.")

    def strip_lead(s: str, prefixes: tuple[str, ...]) -> str:
        t = s.strip().rstrip(".,;")
        for p in prefixes:
            if t.lower().startswith(p):
                t = t[len(p) :].strip()
        return t[:1].lower() + t[1:] if t else t

    sit = strip_lead(situation, ("when ", "whenever "))
    mot = strip_lead(motivation, ("i want to ", "want to ", "i want ", "to "))
    out = strip_lead(outcome, ("so i can ", "so that i can ", "so that ", "so i ", "so "))
    statement = f"When {sit}, I want to {mot}, so I can {out}."
    who = persona.strip() or "I"
    story = f"When {sit}, {who} want{'s' if who != 'I' else ''} to {mot}, so {'they' if who != 'I' else 'I'} can {out}."
    lint = []
    joined = f"{sit} {mot} {out}"
    for pn in product_names[:50]:
        if pn and re.search(rf"\b{re.escape(str(pn))}\b", joined, re.I):
            lint.append(f"Product name '{pn}' inside the job — the job must exist without your product.")
    sol = sorted({m.lower() for m in SOLUTION_WORDS.findall(mot)})
    if sol:
        lint.append(f"Motivation contains solution words ({', '.join(sol)}) — describe the progress they want, not the tool.")
    if not SITUATION_CUES.search(sit) and len(text.words(sit)) < 4:
        lint.append("Situation is thin — add the trigger (a moment, event or recurring time).")
    mw = text.words(mot)
    if mw and mw[0].lower().endswith("ing"):
        lint.append("Motivation should start with a base verb ('reconcile', not 'reconciling').")
    def stem(w: str) -> str:
        w = w.lower()
        for suf in ("ing", "ed", "es", "s"):
            if len(w) > len(suf) + 3 and w.endswith(suf):
                return w[: -len(suf)]
        return w

    ow = {stem(w) for w in text.words(out) if w.lower() not in text.STOPWORDS}
    mwset = {stem(w) for w in mw if w.lower() not in text.STOPWORDS}
    if ow and mwset and len(ow & mwset) / len(ow | mwset) > 0.5:
        lint.append("Outcome restates the motivation — the outcome is the bigger progress (why it matters).")
    if not re.search(r"\b(without|before|faster|less|more|confident|sure|avoid|stop|never|keep|show|prove|hit|on time|in time)\b", out, re.I) and not re.search(r"\d", out):
        lint.append("Outcome has no stakes — add what changes (time, risk, money, standing).")
    words_total = len(text.words(statement))
    if words_total > 40:
        lint.append(f"{words_total} words — trim to ≤ 40 so it fits on the persona card.")
    return {
        "jtbd_statement": statement,
        "job_story": story,
        "forces_prompts": {
            "push": f"What about '{sit}' makes the current way painful?",
            "pull": f"What would make '{mot}' feel obviously better?",
            "anxiety": "What could go wrong if they switch (data, learning curve, looking bad)?",
            "habit": "What keeps them on the current way (comfort, sunk cost, colleagues)?",
        },
        "words": words_total,
        "lint": lint,
        "ready": not lint,
        "summary": ("Job statement clean." if not lint else f"{len(lint)} issue(s): {lint[0]}"),
    }


REQUIRED = {
    "name": 1, "role": 2, "segment": 1, "jtbd": 3, "trigger_event": 2, "current_alternative": 2, "pains": 3, "success_metric": 2,
    "objections": 2, "buying_role": 1, "channels": 2, "quote": 2, "anti_persona": 1, "interviews": 3, "survey_n": 2,
}


@AGENT.tool
def persona_scorecard(persona: dict) -> dict:
    """Score a persona 0-100 for completeness and evidence; lists what's missing and whether it must be labelled provisional.

    Call before shipping any persona. Fields: name, role, segment, jtbd, trigger_event, current_alternative, pains (list), success_metric, objections (list), buying_role, channels (list), quote, anti_persona, interviews (int), survey_n (int), demographics (optional).

    Args:
        persona: The persona as an object with the fields listed above (lists for pains/objections/channels; ints for interviews/survey_n).
    """
    if not isinstance(persona, dict) or not persona:
        raise ToolError("persona must be a non-empty object.")
    missing, weak = [], []
    earned = total = 0
    for field, w in REQUIRED.items():
        total += w
        if field in ("interviews", "survey_n"):
            continue  # scored below from the evidence counts
        v = persona.get(field)
        if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, tuple)) and not v):
            missing.append(field)
            continue
        if field in ("pains", "objections", "channels") and isinstance(v, (list, tuple)) and len(v) < (3 if field == "pains" else 2):
            weak.append(f"{field}: only {len(v)} — want ≥ {3 if field == 'pains' else 2}")
            earned += w / 2
            continue
        if field == "jtbd" and (not re.search(r"\bwhen\b", str(v), re.I) or not re.search(r"\bso (i|they|we) can\b|\bso that\b", str(v), re.I)):
            weak.append("jtbd: not in 'When …, I want to …, so I can …' form")
            earned += w / 2
            continue
        if field == "quote" and len(text.words(str(v))) < 6:
            weak.append("quote: too short to be verbatim")
            earned += w / 2
            continue
        if field == "buying_role" and not re.search(r"champion|economic|buyer|user|blocker|influencer|decision", str(v), re.I):
            weak.append("buying_role: use champion / economic buyer / user / blocker")
            earned += w / 2
            continue
        earned += w
    try:
        interviews = int(persona.get("interviews") or 0)
        survey_n = int(persona.get("survey_n") or 0)
    except (TypeError, ValueError):
        raise ToolError("interviews and survey_n must be integers.") from None
    if interviews >= 5:
        earned += REQUIRED["interviews"]
    elif interviews > 0:
        earned += REQUIRED["interviews"] / 2
        weak.append(f"interviews: {interviews} (< 5 — below saturation)")
    if survey_n >= 30:
        earned += REQUIRED["survey_n"]
    elif survey_n > 0:
        earned += REQUIRED["survey_n"] / 2
        weak.append(f"survey_n: {survey_n} (< 30 per segment)")
    demographics_only = bool(persona.get("demographics")) and not persona.get("pains") and not persona.get("jtbd")
    if demographics_only:
        weak.append("demographics present but no job/pains — that's a stock photo, not a persona")
    provisional = interviews < 5 and survey_n < 30
    score = round(100 * earned / total)
    status = "complete" if score >= 85 and not provisional else "usable with gaps" if score >= 65 else "draft"
    return {
        "score": score,
        "status": status,
        "provisional": provisional,
        "missing": missing,
        "weak": weak,
        "evidence": {"interviews": interviews, "survey_n": survey_n},
        "summary": f"{score}/100 — {status}" + (" — label PROVISIONAL (evidence below floor: 5 interviews or 30 survey rows)." if provisional else ".") + (f" Missing: {', '.join(missing)}." if missing else ""),
    }
