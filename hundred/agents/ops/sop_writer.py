"""SOP Writer — turns tribal knowledge into procedures a new hire can follow on day one, with RACI and cycle-time math."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import as_float, as_str, as_str_list, clamp, md_table, require_list

AGENT = Agent(
    slug="sop-writer",
    name="SOP Writer",
    category="ops",
    tagline="Turn how-we-do-it-here into a numbered, testable SOP with a RACI, cycle time and a review date.",
    description=(
        "Writes standard operating procedures the way a top operations lead does: one action per numbered "
        "step in the imperative, decision points with both branches, verification steps, roles that exist, "
        "and a document-control header with version and next review date. Tools lint every step for the "
        "mistakes that make SOPs unusable, validate the RACI (exactly one Accountable), compute touch time "
        "vs lead time and process efficiency, and generate the control block."
    ),
    triggers=[
        "write an SOP / standard operating procedure",
        "document this process / turn these notes into a procedure",
        "review my SOP / is this procedure clear enough",
        "build a RACI for this process",
        "how long does this process take end to end",
        "create a checklist / runbook for onboarding, refunds, deployments",
    ],
    examples=[
        "Here's how we process refunds (voice-memo transcript). Turn it into an SOP for the support team.",
        "Review this onboarding SOP — new hires keep getting step 6 wrong.",
        "Build a RACI for our monthly close: controller, AP clerk, CFO, auditors.",
        "Steps and time per step for our vendor onboarding — how long does it really take, and where's the waste?",
    ],
    connectors=["Notion", "Confluence", "Google Docs", "Slack", "Asana", "Trello", "Jira"],
    playbook="""
    ## Standard
    You are the operations lead who has written the procedures that let a company run
    without its founders. An excellent SOP passes the "new-hire test": a competent person
    who has never done the task can follow it start to finish, know when they are done,
    and know what to do when something goes wrong — without asking anyone. The one metric:
    **first-time-right rate** when someone new follows it.

    ## Intake
    Need: what the process is, who does it, the trigger (what starts it), the end state
    (what "done" is), and the raw steps in any form (notes, transcript, screenshots
    described). Ask at most 2 questions, only if the trigger or the end state is unknown.
    Missing tool names or role titles → use placeholders like `<ticketing system>` and list
    them under Open items rather than stopping.

    ## Procedure
    1. **Fix the boundaries.** Write Purpose (one sentence: why this SOP exists and the
       risk of doing it wrong), Scope (when it applies / does not apply), Trigger, and End
       state (the observable result). Define every role in a Roles table before step 1.
    2. **Draft the steps** as numbered imperatives: one action per step, the actor named
       if it changes ("Support agent: …"), the system named ("in Stripe → Payments"), and
       the expected result when it isn't obvious ("Status shows *Refunded*"). Decision
       points are written as "If X: go to step N. Otherwise: go to step M." — both branches,
       always. Add a verification step after any irreversible action.
    3. **Lint with `sop_writer__lint_steps`** (pass the steps and the role names). It flags
       non-imperative openings, gerunds, third-person narration, multiple actions in one
       step, vague qualifiers ("as needed", "appropriately"), passive voice, steps over 25
       words, decision steps missing the else-branch, undefined roles, and missing
       verification. Fix every flag and re-lint until the score is ≥ 85.
    4. **Assign ownership.** Build the RACI for the 5-12 key activities and call
       `sop_writer__build_raci`. Exactly one Accountable per activity; at least one
       Responsible; no one Consulted and Informed on the same row; nobody Accountable for
       more than ~40% of activities unless they own the process. Render the matrix.
    5. **Measure it.** Estimate touch time and wait time per step (ask, or use typical
       values and mark them as estimates) and call `sop_writer__cycle_time`. Report lead
       time, touch time, process cycle efficiency, handoffs and the biggest wait. PCE below
       25% or more than 4 handoffs → propose the specific consolidation.
    6. **Control block.** Call `sop_writer__sop_control_block` with title, owner, version,
       effective date and review cadence (12 months default; 6 for regulated or fast-changing
       processes). Put its output at the top of the document.
    7. **Add the safety net**: Exceptions & escalation (what to do when a step fails, who to
       call, within how long), Related documents, Change log. Then a one-page checklist
       version of the steps for daily use.
    8. **File** to Notion/Confluence/Docs if connected; create the review-date reminder in
       the task tool. Otherwise output ready to paste.

    ## Frameworks
    - **Step grammar**: `[Actor:] <Verb> <object> [in <system>] [→ expected result]`. Verb
      first, present tense, second person implied. 7-15 steps per procedure; > 20 → split
      into sub-procedures.
    - **Decision steps**: always two named branches with step numbers; never "handle
      accordingly".
    - **Poka-yoke**: after every irreversible or costly action (send, delete, pay, deploy)
      insert a verify step with the exact thing to look at.
    - **RACI rules**: one A per row; R does the work; C is two-way before the fact; I is
      one-way after. If a row has 4+ R's, the activity is really two activities.
    - **Lean process metrics**: Lead time = touch + wait. PCE = touch / lead. World-class
      transactional processes run 25-50% PCE; most un-designed processes sit under 10%.
      Handoffs are where errors and waits live — each one costs on average a day of wait.
    - **Readability**: target grade ≤ 8 (Flesch-Kincaid). Short sentences, concrete nouns,
      no "should" — SOPs say "do".
    - **Review cadence**: 12 months default; 6 months if regulated, tooling changes often, or
      the process is < 3 months old.

    ## Output format
    ```
    # SOP-<ID>: <Title>                           v<X.Y> · Owner: <role> · Effective: <date> · Review by: <date>

    **Purpose** <one sentence + the risk of doing it wrong>
    **Scope** applies to … / does not apply to …
    **Trigger** <what starts it> → **End state** <observable result>

    ## Roles
    | Role | Does | Backup |

    ## Procedure
    1. <Actor:> <Verb object in system → expected result>
    2. If <condition>: go to step N. Otherwise: go to step M.
    …
    N. Verify <exact thing>. If wrong → Exceptions.

    ## RACI
    | Activity | <Role A> | <Role B> | … |

    ## Exceptions & escalation
    | If this happens | Do this | Escalate to | Within |

    ## Cycle time
    Lead time ~X (touch Y, wait Z, PCE N%, H handoffs). Biggest wait: step K.

    ## Checklist version
    - [ ] …

    ## Related docs · Change log
    ```

    ## Anti-patterns
    - Narrative ("The agent then goes into the system and…"). Steps are commands.
    - "Handle appropriately", "as needed", "escalate if necessary" — the reader has no idea
      what that means. Give the rule.
    - Two actions in one step ("Export the report and email it to finance"). Split; each
      gets verified separately.
    - Decision steps with only the happy path.
    - Roles that don't exist in the org chart, or "someone".
    - A 40-step wall. Split into sub-procedures with their own triggers.
    - No review date. An SOP nobody re-reads is wrong within a year.
    """,
)

_NON_IMPERATIVE_STARTS = {"the", "a", "an", "you", "we", "they", "he", "she", "it", "this", "that", "there", "our", "your", "then", "and", "also", "once", "after", "before", "when", "while", "next", "now", "please", "should", "must", "will", "can", "may", "always", "never", "make sure", "ensure that"}
_OK_S_VERBS = {"process", "pass", "press", "access", "address", "discuss", "assess", "focus", "compress", "cross", "dismiss", "express", "toss", "guess", "bless", "miss", "class", "harness", "witness"}
_VAGUE = re.compile(r"\b(appropriately|as needed|as necessary|as required|properly|correctly|accordingly|if applicable|where appropriate|if necessary|etc\.?|regularly|timely|in a timely manner|some|various|relevant|suitable|reasonable|adequate|sufficient|handle|deal with|take care of)\b", re.I)
_COND = re.compile(r"^\s*(if|when|in case|should)\b", re.I)
_ELSE = re.compile(r"\b(otherwise|else|if not|if no|if yes|in all other cases)\b", re.I)
_VERIFY = re.compile(r"\b(verify|confirm|check that|check the|ensure|validate|double-check|review that|inspect)\b", re.I)
_IRREVERSIBLE = re.compile(r"\b(send|delete|remove|pay|refund|deploy|publish|submit|approve|charge|wire|transfer|release|terminate|cancel|purge|drop|overwrite)\b", re.I)
_SYSTEM = re.compile(r"\b(in|on|via|using|open|from)\s+[A-Z][\w-]+|<[^>]+>", re.I)
_ROLE_TOKEN = re.compile(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s*:")
_ACTION_VERBS = {"send", "email", "click", "open", "update", "save", "export", "notify", "create", "delete", "close", "submit", "record", "log", "check", "verify", "attach", "upload", "download", "file", "forward", "call", "review", "approve", "assign", "add", "remove", "enter", "select", "print", "copy", "paste", "move", "mark", "set", "run", "start", "stop", "restart", "archive", "escalate", "post", "reply", "confirm", "schedule", "book", "cancel", "refund", "charge", "pay", "ship", "deploy", "merge", "tag", "label", "flag", "import", "sync", "scan", "sign"}


@AGENT.tool
def lint_steps(steps: list[str], roles: list[str] = []) -> dict:
    """Lint SOP steps: imperative voice, one action per step, vague words, passive, else-branches, roles, verification. Score 0-100.

    Args:
        steps: The procedure steps in order, one string each (numbering optional).
        roles: Role titles defined in the SOP (e.g. ["Support agent", "Finance"]); actors in steps not in this list are flagged.
    """
    steps = [as_str(s, "step", required=False, max_len=2000) for s in require_list(steps, "steps", 200)]
    steps = [re.sub(r"^\s*(?:step\s*)?\d+[.):]\s*", "", s, flags=re.I).strip() for s in steps]
    role_set = {r.lower() for r in as_str_list(roles, "roles", 50)}
    rows, deduct = [], 0
    has_verify = has_irreversible = False
    for i, s in enumerate(steps, 1):
        issues = []
        if not s:
            rows.append({"n": i, "step": s, "issues": ["empty step"], "ok": False})
            deduct += 5
            continue
        body = s
        actor = None
        m = _ROLE_TOKEN.match(s)
        if m:
            actor = m.group(1)
            body = s[m.end():].strip()
            if role_set and actor.lower() not in role_set:
                issues.append(f"actor '{actor}' is not a defined role — add it to the Roles table or use an existing one")
        first = text.words(body)[:2]
        first1 = first[0].lower() if first else ""
        first2 = " ".join(w.lower() for w in first)
        n = len(text.words(body))
        if first2 in _NON_IMPERATIVE_STARTS or first1 in _NON_IMPERATIVE_STARTS:
            if not _COND.match(body):
                issues.append(f"does not open with a verb ('{first1}…') — rewrite as a command")
        elif first1.endswith("ing") and first1 not in ("bring", "ping", "string", "ring", "sing", "swing"):
            issues.append("opens with a gerund — use the imperative ('Export…', not 'Exporting…')")
        elif first1.endswith("s") and first1 not in _OK_S_VERBS and len(first1) > 3 and not first1.endswith("ss"):
            issues.append("third-person narration ('…s') — write it as a command to the reader")
        if _COND.match(body):
            nxt = steps[i] if i < len(steps) else ""
            if not (_ELSE.search(body) or _ELSE.search(nxt[:40]) or re.search(r"\bgo to step \d+\b.*\bgo to step \d+\b|\bstep \d+\b.*\bstep \d+\b", body, re.I)):
                issues.append("decision step with no else-branch — add 'Otherwise: go to step N'")
        conj = len(re.findall(r"\b(and then|then|, and|; and| and )\b", body, re.I))
        verbs_after_and = [v.lower() for v in re.findall(r"\b(?:and|then)\s+(\w+)", body, re.I)]
        chained_verb = any(v in _ACTION_VERBS or (v.endswith("ing") and v not in text.STOPWORDS and len(v) > 5) for v in verbs_after_and)
        if conj >= 2 or chained_verb or (conj >= 1 and any(v not in text.STOPWORDS and not v.endswith("ed") and len(v) > 3 for v in verbs_after_and) and n > 12):
            issues.append("more than one action — split into separate steps so each can be verified")
        vague = sorted({v.lower() for v in _VAGUE.findall(body)})
        if vague:
            issues.append("vague: " + ", ".join(f"'{v}'" for v in vague) + " — state the rule or the exact value")
        if text.PASSIVE_RE.search(body):
            issues.append("passive voice — say who does it")
        if n > 25:
            issues.append(f"{n} words — split or move detail to a note (≤ 25)")
        if re.search(r"\b(should|may|might|could|try to)\b", body, re.I):
            issues.append("'should/may/try' — SOPs say 'do' or give the condition")
        if _VERIFY.search(body):
            has_verify = True
        if _IRREVERSIBLE.match(body):  # leading verb only — "Open the refund request" is not a refund
            has_irreversible = True
            nxt = steps[i] if i < len(steps) else ""
            if not (_VERIFY.search(nxt) or _VERIFY.search(body)):
                issues.append("irreversible action with no verification step right after it")
        deduct += 4 * len(issues)
        rows.append({"n": i, "actor": actor, "step": s, "issues": issues, "ok": not issues})
    doc_issues = []
    if len(steps) > 20:
        doc_issues.append(f"{len(steps)} steps — split into sub-procedures (7-15 each)")
        deduct += 8
    if len(steps) < 3:
        doc_issues.append("fewer than 3 steps — is this a procedure or a single instruction?")
        deduct += 5
    if has_irreversible and not has_verify and len(steps) >= 3:
        doc_issues.append("no verification step anywhere, yet the procedure has irreversible actions")
        deduct += 8
    if not any(_SYSTEM.search(s) for s in steps):
        doc_issues.append("no system/tool named in any step — say where each action happens")
        deduct += 5
    joined = "\n".join(steps)
    rd = text.readability(joined)
    if rd.get("fk_grade") and rd["fk_grade"] > 10:
        doc_issues.append(f"reading grade {rd['fk_grade']} — target ≤ 8; shorten sentences and words")
        deduct += 5
    score = int(clamp(100 - deduct, 0, 100))
    flagged = [r for r in rows if not r["ok"]]
    return {
        "score": score,
        "grade": "ready" if score >= 85 else "fix flags" if score >= 60 else "rewrite",
        "steps": rows,
        "document_issues": doc_issues,
        "counts": {"steps": len(steps), "flagged_steps": len(flagged), "issues": sum(len(r["issues"]) for r in rows) + len(doc_issues)},
        "readability": rd,
        "step_grammar": "[Actor:] <Verb> <object> [in <system>] [→ expected result]; decisions: 'If X: go to step N. Otherwise: go to step M.'",
        "verdict": f"Lint {score}/100: {len(flagged)} of {len(steps)} steps flagged, {len(doc_issues)} document-level issue(s), reading grade {rd.get('fk_grade')}.",
    }


@AGENT.tool
def build_raci(activities: list[dict]) -> dict:
    """Validate and render a RACI matrix: exactly one Accountable per activity, ≥1 Responsible, workload and bottleneck checks.

    Args:
        activities: List of {"activity": str, "responsible": [names], "accountable": [names], "consulted": [names], "informed": [names]}.
    """
    activities = require_list(activities, "activities", 100)
    rows, flags = [], []
    load: dict[str, Counter] = defaultdict(Counter)
    people: list[str] = []
    for i, a in enumerate(activities, 1):
        if not isinstance(a, dict):
            raise ToolError(f"activities[{i}] must be {{'activity','responsible','accountable','consulted','informed'}}.")
        name = as_str(a.get("activity") or a.get("name"), f"activities[{i}].activity", max_len=150)
        r = as_str_list(a.get("responsible", a.get("R", [])), "responsible", 20)
        acc = as_str_list(a.get("accountable", a.get("A", [])), "accountable", 20)
        c = as_str_list(a.get("consulted", a.get("C", [])), "consulted", 20)
        inf = as_str_list(a.get("informed", a.get("I", [])), "informed", 20)
        issues = []
        if len(acc) == 0:
            issues.append("no Accountable — every activity needs exactly one")
        elif len(acc) > 1:
            issues.append(f"{len(acc)} Accountable ({', '.join(acc)}) — pick one; shared accountability is none")
        if not r:
            issues.append("no Responsible — who does the work?")
        if len(r) >= 4:
            issues.append(f"{len(r)} Responsible — probably two activities; split")
        both = sorted({x.lower() for x in c} & {x.lower() for x in inf})
        if both:
            issues.append("Consulted and Informed on the same row: " + ", ".join(both))
        cell: dict[str, str] = {}
        for letter, group in (("R", r), ("A", acc), ("C", c), ("I", inf)):
            for p in group:
                cell[p] = cell[p] + "/" + letter if p in cell and letter not in cell[p] else cell.get(p, letter)
                load[p][letter] += 1
                if p not in people:
                    people.append(p)
        rows.append({"activity": name, "cells": cell, "issues": issues})
        flags.extend(f"{name}: {x}" for x in issues)
    n = len(rows)
    a_counts = {p: load[p]["A"] for p in people}
    top_a = max(a_counts, key=a_counts.get) if a_counts else None
    if top_a and n >= 3 and a_counts[top_a] / n > 0.4 and a_counts[top_a] > 1:
        flags.append(f"{top_a} is Accountable for {a_counts[top_a]} of {n} activities ({round(100 * a_counts[top_a] / n)}%) — bottleneck unless they own the whole process")
    idle = [p for p in people if load[p]["R"] + load[p]["A"] == 0]
    if idle:
        flags.append("only Consulted/Informed, never R or A: " + ", ".join(idle) + " — do they belong in this process?")
    matrix = md_table(["Activity"] + people, [[r["activity"]] + [r["cells"].get(p, "") for p in people] for r in rows])
    workload = {p: {"R": load[p]["R"], "A": load[p]["A"], "C": load[p]["C"], "I": load[p]["I"], "hands_on": load[p]["R"] + load[p]["A"]} for p in people}
    valid = not any(r["issues"] for r in rows)
    return {
        "valid": valid,
        "activities": rows,
        "people": people,
        "workload": workload,
        "flags": flags,
        "markdown_matrix": matrix,
        "verdict": ("RACI is valid" if valid else f"RACI has {sum(1 for r in rows if r['issues'])} invalid row(s)") + f": {n} activities, {len(people)} people. " + (flags[0] + "." if flags else "No workload concerns."),
    }


@AGENT.tool
def cycle_time(steps: list[dict]) -> dict:
    """Compute lead time, touch time, process cycle efficiency, handoffs, the biggest wait and per-role load for a process.

    Args:
        steps: Ordered list of {"step": str, "touch_minutes": number (hands-on work), "wait_minutes": number (queue/waiting before or after), "role": str}.
    """
    steps = require_list(steps, "steps", 200)
    rows, touch_total, wait_total = [], 0.0, 0.0
    by_role: dict[str, float] = defaultdict(float)
    handoffs, prev_role = 0, None
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict):
            raise ToolError(f"steps[{i}] must be {{'step','touch_minutes','wait_minutes','role'}}.")
        name = as_str(s.get("step") or s.get("name") or f"Step {i}", "step", max_len=150)
        touch = as_float(s.get("touch_minutes", 0), f"{name}.touch_minutes", lo=0, hi=1e6, default=0.0)
        wait = as_float(s.get("wait_minutes", 0), f"{name}.wait_minutes", lo=0, hi=1e7, default=0.0)
        role = as_str(s.get("role", ""), "role", required=False, max_len=60)
        if role and prev_role and role.lower() != prev_role.lower():
            handoffs += 1
        if role:
            prev_role = role
            by_role[role] += touch
        touch_total += touch
        wait_total += wait
        rows.append({"n": i, "step": name, "role": role or None, "touch_minutes": touch, "wait_minutes": wait, "lead_minutes": touch + wait})
    lead = touch_total + wait_total
    if lead <= 0:
        raise ToolError("All steps have zero time — add touch_minutes / wait_minutes.")
    pce = round(100 * touch_total / lead, 1)
    for r in rows:
        r["share_of_lead_pct"] = round(100 * r["lead_minutes"] / lead, 1)
    biggest_wait = max(rows, key=lambda r: r["wait_minutes"])
    bottleneck = max(rows, key=lambda r: r["touch_minutes"])
    recs = []
    if pce < 10:
        recs.append(f"PCE {pce}% — under 10%: the process is mostly waiting. Attack the top wait first ({biggest_wait['step']}: {biggest_wait['wait_minutes']:g} min).")
    elif pce < 25:
        recs.append(f"PCE {pce}% — below the 25% mark for a well-designed transactional process; remove the top two waits.")
    if handoffs > 4:
        recs.append(f"{handoffs} handoffs — consolidate consecutive steps under one role where possible; each handoff adds queue time and error risk.")
    top3_wait = sum(sorted((r["wait_minutes"] for r in rows), reverse=True)[:3])
    if top3_wait / lead > 0.5:
        recs.append(f"Top 3 waits are {round(100 * top3_wait / lead)}% of lead time — fixing those alone would cut lead time by ~{round(top3_wait / 60, 1)} h.")
    if not recs:
        recs.append("Process is lean for its type; keep measuring.")

    def fmt(m: float) -> str:
        if m >= 60 * 8:
            return f"{m / 60 / 8:.1f} workdays"
        if m >= 60:
            return f"{m / 60:.1f} h"
        return f"{m:g} min"

    return {
        "lead_time_minutes": round(lead, 1),
        "touch_time_minutes": round(touch_total, 1),
        "wait_time_minutes": round(wait_total, 1),
        "lead_time_human": fmt(lead),
        "touch_time_human": fmt(touch_total),
        "process_cycle_efficiency_pct": pce,
        "handoffs": handoffs,
        "biggest_wait": {"step": biggest_wait["step"], "minutes": biggest_wait["wait_minutes"]},
        "bottleneck_touch": {"step": bottleneck["step"], "minutes": bottleneck["touch_minutes"], "role": bottleneck["role"]},
        "by_role_touch_minutes": dict(by_role),
        "steps": rows,
        "recommendations": recs,
        "markdown_table": md_table(["#", "Step", "Role", "Touch", "Wait", "% of lead"], [[r["n"], r["step"], r["role"] or "", r["touch_minutes"], r["wait_minutes"], r["share_of_lead_pct"]] for r in rows]),
        "verdict": f"Lead time {fmt(lead)} = touch {fmt(touch_total)} + wait {fmt(wait_total)} (PCE {pce}%), {handoffs} handoffs. Biggest wait: {biggest_wait['step']} ({fmt(biggest_wait['wait_minutes'])}).",
    }


@AGENT.tool
def sop_control_block(title: str, owner: str, effective_date: str, version: str = "1.0", review_months: int = 12, change_type: str = "none", department: str = "", as_of: str = "") -> dict:
    """Generate the document-control header: SOP ID, (bumped) version, next review date, status vs today, change-log line.

    Args:
        title: The SOP title, e.g. "Customer refund processing".
        owner: Role or person who owns the SOP.
        effective_date: Date this version takes effect (YYYY-MM-DD).
        version: Current version like "1.0" or "2.3".
        review_months: Months between scheduled reviews (1-36; 12 default, 6 for regulated/fast-changing).
        change_type: "none" (keep version), "minor" (1.0 -> 1.1: clarifications), "major" (1.3 -> 2.0: process change).
        department: Optional department code for the ID, e.g. "FIN", "CS".
        as_of: Today's date (YYYY-MM-DD) for status; defaults to today.
    """
    title = as_str(title, "title", max_len=120)
    owner = as_str(owner, "owner", max_len=80)
    eff = dates.parse_date(effective_date)
    today = dates.parse_date(as_of) if as_of else date.today()
    if not (1 <= review_months <= 36):
        raise ToolError("review_months must be 1-36.")
    m = re.fullmatch(r"\s*v?(\d+)\.(\d+)\s*", version or "")
    if not m:
        raise ToolError(f"version must look like '1.0' or '2.3', got {version!r}.")
    major, minor = int(m.group(1)), int(m.group(2))
    ct = change_type.lower().strip()
    if ct not in ("none", "minor", "major"):
        raise ToolError("change_type must be 'none', 'minor' or 'major'.")
    if ct == "minor":
        minor += 1
    elif ct == "major":
        major, minor = major + 1, 0
    new_version = f"{major}.{minor}"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(slug) > 32:  # cut at a word boundary
        slug = slug[:32].rsplit("-", 1)[0] if "-" in slug[:32] else slug[:32]
    dept = re.sub(r"[^A-Z0-9]", "", department.upper())[:6]
    sop_id = f"SOP-{dept + '-' if dept else ''}{slug.upper()}"
    y, mo = divmod(eff.month - 1 + review_months, 12)
    try:
        next_review = eff.replace(year=eff.year + y, month=mo + 1)
    except ValueError:
        next_review = (eff.replace(year=eff.year + y, month=mo + 1, day=1) + __import__("datetime").timedelta(days=31)).replace(day=1) - __import__("datetime").timedelta(days=1)
    days_to_review = (next_review - today).days
    if eff > today:
        status = "scheduled (not yet effective)"
    elif days_to_review < 0:
        status = f"OVERDUE FOR REVIEW by {-days_to_review} days"
    elif days_to_review <= 30:
        status = "review due within 30 days"
    else:
        status = "active"
    header = md_table(
        ["Field", "Value"],
        [["SOP ID", sop_id], ["Title", title], ["Version", new_version], ["Owner", owner], ["Effective", eff.isoformat()], ["Review cadence", f"every {review_months} months"], ["Next review", next_review.isoformat()], ["Status", status]],
    )
    change_line = f"| {new_version} | {eff.isoformat()} | {owner} | " + {"none": "Initial release" if new_version == "1.0" else "No change", "minor": "Minor: clarifications, no process change", "major": "Major: process change — re-train all roles"}[ct] + " |"
    return {
        "sop_id": sop_id,
        "title": title,
        "version": new_version,
        "previous_version": version.strip().lstrip("v") if ct != "none" else None,
        "owner": owner,
        "effective_date": eff.isoformat(),
        "next_review_date": next_review.isoformat(),
        "days_until_review": days_to_review,
        "status": status,
        "requires_retraining": ct == "major",
        "header_markdown": header,
        "change_log_line": "| Version | Date | Author | Change |\n|---|---|---|---|\n" + change_line,
        "verdict": f"{sop_id} v{new_version}, effective {eff.isoformat()}, next review {next_review.isoformat()} ({days_to_review} days) — {status}." + (" Major change: schedule re-training." if ct == "major" else ""),
    }
