"""UX Writer — microcopy that fits the box, reads at grade 6, and tells the user what to do next."""

from __future__ import annotations

import re
from collections import defaultdict

from ...core import Agent, ToolError
from ...lib import text
from ._common import check_rows, check_text

AGENT = Agent(
    slug="ux-writer",
    name="UX Writer",
    category="product",
    tagline="Microcopy that fits the component, reads at grade 6, and turns errors into next steps.",
    description=(
        "Writes and lints interface copy like a senior content designer: enforces per-component length "
        "limits (buttons, labels, tooltips, toasts, empty states, error messages, push notifications), "
        "checks readability against a grade-6 target, lints error messages for the what/why/how-to-fix "
        "structure and blame words, audits terminology consistency across a whole string table "
        "(Sign in vs Log in), and estimates localisation expansion so German and Finnish don't break your layout."
    ),
    triggers=[
        "write microcopy / UI copy / button text",
        "rewrite this error message",
        "review these interface strings",
        "write an empty state / onboarding tooltip / push notification",
        "check my copy for consistency (sign in vs log in)",
        "will this text fit after translation",
    ],
    examples=[
        "Rewrite this error: 'Error 403: Request failed. Invalid permissions.'",
        "Here's our string table for the settings page (40 strings) — lint it for length, tone and consistency.",
        "Write the empty state, primary button and tooltip for a brand-new 'Integrations' page.",
    ],
    connectors=["Figma", "Notion", "GitHub", "Google Sheets", "Lokalise"],
    playbook="""
    ## Standard
    You are a senior content designer. Excellent microcopy is invisible: the user knows what will
    happen, what happened, and what to do next without noticing the words. The one metric that
    matters is **task completion without confusion** — every string is judged by whether a first-time
    user on a phone in a hurry gets it. Clear beats clever, every time.

    ## Intake
    Work from what you have. Ask (max 3) only if missing: (1) the component and its context
    (button in a modal? inline field error?), (2) the product's voice in three words (or infer from
    existing strings), (3) whether copy will be localised (changes length budgets). Assume sentence
    case, US English, and localisation unless told otherwise; say so.

    ## Procedure
    1. **Lint the strings.** Call `ux_writer__check_microcopy` with each string and its component
       type. It checks the length budget per component (button ≤ 3 words/25 chars, label ≤ 3 words,
       tooltip ≤ 120 chars, toast ≤ 80, error ≤ 140, empty-state body ≤ 200, push ≤ 40-title/90-body),
       title-case vs sentence-case, ending punctuation rules (buttons/labels: none; sentences: period),
       jargon and blame words, readability (target FK grade ≤ 6), and double spaces / smart-quote
       mix. Fix everything it flags before you write anything new.
    2. **For every error message** call `ux_writer__lint_error_message`. A good error has three
       parts: **what happened** (plain language), **why** (only if it helps), **what to do now** (a
       verb the user can act on). The tool checks for those parts, error codes shown to humans,
       blame ("you entered an invalid…"), "please", ALL CAPS, exclamation marks, and vague phrases
       ("something went wrong") without a next step. Rewrite until it passes.
    3. **Audit consistency** across the whole table with `ux_writer__check_consistency`. It finds
       synonym conflicts (Sign in / Log in / Login; Delete / Remove / Trash; Cancel / Dismiss;
       OK / Okay / Got it), casing drift for the same term, mixed punctuation habits, and reports
       the majority form so you can standardise. One concept = one word.
    4. **Estimate localisation fit** with `ux_writer__localization_expansion` for any string in a
       fixed-width component. It applies established expansion factors (German +35%, French +20%,
       Finnish +30%, Russian +15%, Japanese −10%, etc.; short strings expand more) and tells you
       which locales overflow the container width in characters.
    5. **Write the copy.** Buttons: verb + object ("Save changes", not "OK"); labels: nouns; empty
       states: what this is + why it's empty + one action; confirmations: name the consequence
       ("Delete 12 files?" / "Delete" not "Are you sure?" / "Yes"); success: confirm what changed.
       Write two variants when tone is uncertain: neutral and warmer.
    6. **Re-run steps 1-2** on your own output. Deliver only strings that pass.
    7. If Figma/Lokalise/GitHub is connected, update the strings in place; otherwise output a key →
       string table ready to paste.

    ## Frameworks
    - **Clear / Concise / Useful** (Google's material writing principles): can the user act on it?
      is every word doing work? does it say what happens next?
    - **Error = What + Why + How:** "Couldn't save your changes. You're offline. Reconnect and try
      again." No error codes unless support needs them — then put them last in smaller text.
    - **Front-load:** the first two words carry the meaning ("Delete account" not "Click here to…").
    - **Readability:** FK grade ≤ 6 for consumer, ≤ 8 for pro tools. Sentences ≤ 15 words.
    - **Casing:** sentence case for everything except proper nouns (Apple, Google, Material, GOV.UK
      all agree); Title Case makes strings 5-10% harder to scan.

    ## Output format
    ```
    # Copy review: <screen / flow>
    Voice: <3 words> · Case: sentence · Locale: en-US · Localised: yes (budget −25%)

    | Key | Component | Before | After | Why |
    |---|---|---|---|---|
    | settings.save | button | Save Your Changes! | Save changes | verb+object, sentence case, no ! |

    ## Error messages
    | Key | Before | After (what · why · how) |

    ## Consistency fixes
    - "Log in" (3) / "Sign in" (9) → standardise on "Sign in"

    ## Localisation risks
    - checkout.cta "Continue to payment" (19 ch) → de +35% = 26 ch; container 24 ch → overflow. Suggest "Pay now".

    ## Open decisions
    - <tone/terminology decision the team must make>
    ```

    ## Anti-patterns
    - "Are you sure?" / "OK" / "Yes" confirmations. Name the action and consequence in the button.
    - Error messages that describe the system ("Null reference in handler") instead of the user's situation.
    - "Please" and "Sorry" padding. Say what happened and what to do.
    - Cute copy in high-stakes moments (payments, deletion, security). Be boring where it matters.
    - Title Case Everything. Sentence case, always, except proper nouns.
    - Writing for the ideal case only. Every screen has empty, loading, error and partial states — write all four.
    """,
)

COMPONENT_LIMITS: dict[str, dict] = {
    # chars, words, ending punctuation allowed, sentence expected
    "button": {"chars": 25, "words": 3, "punct": False},
    "link": {"chars": 40, "words": 5, "punct": False},
    "label": {"chars": 30, "words": 3, "punct": False},
    "placeholder": {"chars": 40, "words": 6, "punct": False},
    "menu_item": {"chars": 30, "words": 4, "punct": False},
    "tab": {"chars": 20, "words": 2, "punct": False},
    "heading": {"chars": 60, "words": 8, "punct": False},
    "tooltip": {"chars": 120, "words": 20, "punct": True},
    "helper_text": {"chars": 120, "words": 20, "punct": True},
    "toast": {"chars": 80, "words": 14, "punct": True},
    "error": {"chars": 140, "words": 25, "punct": True},
    "empty_state_title": {"chars": 40, "words": 6, "punct": False},
    "empty_state_body": {"chars": 200, "words": 35, "punct": True},
    "dialog_title": {"chars": 50, "words": 8, "punct": False},
    "dialog_body": {"chars": 220, "words": 40, "punct": True},
    "push_title": {"chars": 40, "words": 6, "punct": False},
    "push_body": {"chars": 90, "words": 16, "punct": True},
    "email_subject": {"chars": 45, "words": 8, "punct": False},
    "onboarding_step": {"chars": 160, "words": 28, "punct": True},
}
JARGON = re.compile(r"\b(null|undefined|exception|token|payload|backend|endpoint|api|sync failed|invalid input|parameter|instance|config|auth|cache|session expired|timeout|error code|stack|latency|deprecated|entity|record|object|abort(?:ed)?|terminate[ds]?|execute[ds]?|initiali[sz]e[ds]?|utili[sz]e)\b", re.I)
BLAME = re.compile(r"\b(you (?:entered|typed|provided|submitted|gave|made)|your (?:input|entry|mistake)|invalid|illegal|forbidden|not allowed|wrong|bad|failure|you failed|you must|you need to)\b", re.I)
VAGUE = re.compile(r"\b(something went wrong|an error (?:has )?occurred|unknown error|oops|whoops|unexpected error|try again later|problem occurred|unable to process)\b", re.I)
ACTION_VERB = re.compile(r"\b(try|retry|check|reconnect|refresh|reload|sign in|log in|contact|update|enter|choose|select|remove|add|wait|upgrade|verify|confirm|use|switch|turn on|enable|allow|go to|open|change|reset|resend|shorten|pick|fix|review)\b", re.I)


def _casing(s: str) -> str:
    ws = [w for w in text.words(s) if w.isalpha()]
    if len(ws) < 2:
        return "n/a"
    caps = sum(1 for w in ws[1:] if w[0].isupper() and len(w) > 3)
    if s.isupper():
        return "ALL CAPS"
    return "Title Case" if caps >= max(1, (len(ws) - 1) * 0.6) else "sentence case"


@AGENT.tool
def check_microcopy(strings: list[dict], target_grade: float = 6.0, localised: bool = True) -> dict:
    """Lint UI strings against per-component length budgets, casing, punctuation, jargon and readability.

    Args:
        strings: List of {"key": str, "text": str, "component": one of button, link, label, placeholder,
            menu_item, tab, heading, tooltip, helper_text, toast, error, empty_state_title, empty_state_body,
            dialog_title, dialog_body, push_title, push_body, email_subject, onboarding_step}.
        target_grade: Maximum Flesch-Kincaid grade for sentence-length strings (default 6).
        localised: If true, shrink length budgets by 25% to leave room for translation expansion.
    """
    rows = check_rows(strings, "strings")
    if not isinstance(target_grade, (int, float)) or not 1 <= target_grade <= 14:
        raise ToolError("target_grade must be between 1 and 14.")
    results, passing = [], 0
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("text", "")).strip():
            raise ToolError(f"strings[{i}] needs non-empty 'text' and a 'component'.")
        comp = str(raw.get("component", "")).strip().lower().replace(" ", "_").replace("-", "_")
        if comp not in COMPONENT_LIMITS:
            raise ToolError(f"strings[{i}]: unknown component {comp!r}. Use one of: {', '.join(COMPONENT_LIMITS)}.")
        s = str(raw["text"]).strip()
        lim = COMPONENT_LIMITS[comp]
        budget = int(lim["chars"] * (0.75 if localised else 1))
        chars, nwords = len(s), len(text.words(s))
        issues, fixes = [], []
        if chars > budget:
            issues.append(f"{chars} chars > {budget} budget ({lim['chars']} × 0.75 for localisation)" if localised else f"{chars} chars > {budget} budget")
        if nwords > lim["words"]:
            issues.append(f"{nwords} words > {lim['words']} for a {comp}")
        case = _casing(s)
        if case == "Title Case":
            issues.append("Title Case — use sentence case")
            fixes.append(s[:1].upper() + s[1:].lower())
        elif case == "ALL CAPS":
            issues.append("ALL CAPS — reads as shouting and is harder to scan")
        if not lim["punct"] and re.search(r"[.!]$", s):
            issues.append("ends with punctuation — buttons/labels/titles take none")
        if lim["punct"] and nwords >= 6 and not re.search(r"[.!?…]$", s):
            issues.append("full sentence without ending period")
        if "!" in s:
            issues.append("exclamation mark — drop it unless it's a genuine celebration")
        if "  " in s:
            issues.append("double space")
        if re.search(r"[\"']", s) and re.search(r"[“”‘’]", s):
            issues.append("mixed straight and curly quotes")
        if comp == "button" and re.match(r"^(ok|okay|yes|no|submit|click here|continue)$", s, re.I):
            issues.append("generic button — use verb + object (e.g. 'Save changes')")
        if comp == "button" and re.match(r"^(click|tap|press)\b", s, re.I):
            issues.append("starts with 'click/tap' — the user knows it's a button")
        j = sorted({m.group(0).lower() for m in JARGON.finditer(s)})
        if j:
            issues.append(f"jargon: {', '.join(j)}")
        if re.search(r"\bplease\b", s, re.I):
            issues.append("'please' — remove; state the action")
        if lim["punct"] and nwords >= 6:
            r = text.readability(s)
            if r["fk_grade"] is not None and r["fk_grade"] > target_grade:
                issues.append(f"FK grade {r['fk_grade']} > {target_grade} — shorter words/sentences")
            if r["avg_words_per_sentence"] > 15:
                issues.append(f"{r['avg_words_per_sentence']} words/sentence — split")
        if not issues:
            passing += 1
        results.append({"key": raw.get("key") or f"s{i + 1}", "component": comp, "text": s, "chars": chars, "budget": budget, "words": nwords, "case": case, "issues": issues, "suggested": fixes[0] if fixes else None})
    return {"strings": results, "passing": passing, "count": len(results), "verdict": f"{passing}/{len(results)} strings pass", "next_step": "Fix flagged strings, then run ux_writer__lint_error_message on every error."}


@AGENT.tool
def lint_error_message(message: str, has_action_button: bool = False) -> dict:
    """Score an error message 0-100 on the what / why / how-to-fix structure, tone, and jargon.

    Args:
        message: The error message text exactly as the user would see it.
        has_action_button: True if a button (e.g. "Retry") accompanies the message, so the text itself need not contain the action.
    """
    s = check_text(message, "message", 2000).strip()
    sents = text.sentences(s) or [s]
    score, issues, parts = 100, [], {"what": False, "why": False, "how": False}
    if re.search(r"\b(couldn'?t|can'?t|didn'?t|failed to|unable to|isn'?t|wasn'?t|not (?:saved|sent|found|available)|no (?:connection|internet|results)|too (?:large|long|many)|expired|already|missing|doesn'?t)\b", s, re.I):
        parts["what"] = True
    if re.search(r"\b(because|since|as|due to|you'?re offline|is full|too large|expired|doesn'?t (?:exist|match)|already (?:exists|in use|taken)|must be|needs to be|has to be|over the|limit)\b", s, re.I):
        parts["why"] = True
    if ACTION_VERB.search(s) or has_action_button:
        parts["how"] = True
    if not parts["what"]:
        score -= 30
        issues.append("no plain statement of what happened (e.g. 'Couldn't save your changes')")
    if not parts["how"]:
        score -= 30
        issues.append("no next step — end with an action verb ('Reconnect and try again')")
    if VAGUE.search(s) and not parts["how"]:
        score -= 10
        issues.append("vague phrase with no next step")
    codes = re.findall(r"\b(?:error|err|code)?\s?[#:]?\s?(?:[0-9]{3,5}|0x[0-9a-f]+|E[A-Z]{2,}[0-9]*)\b", s, re.I)
    if codes and not re.search(r"\(.*(?:code|ref).*\)\s*$", s, re.I):
        score -= 10
        issues.append("error code in the main text — move to the end in parentheses, or drop it")
    b = sorted({m.group(0).lower() for m in BLAME.finditer(s)})
    if b:
        score -= 10
        issues.append(f"blame language: {', '.join(b)} — describe the situation, not the user's fault")
    j = sorted({m.group(0).lower() for m in JARGON.finditer(s)})
    if j:
        score -= 10
        issues.append(f"jargon: {', '.join(j)}")
    if "!" in s:
        score -= 5
        issues.append("exclamation mark")
    if s.isupper() or re.search(r"\b[A-Z]{5,}\b", s):
        score -= 5
        issues.append("ALL-CAPS words")
    if re.search(r"\b(please|sorry|apologi[sz]e|oops|whoops)\b", s, re.I):
        score -= 5
        issues.append("apology/please padding — cut it")
    r = text.readability(s)
    if r["fk_grade"] is not None and r["fk_grade"] > 8:
        score -= 10
        issues.append(f"FK grade {r['fk_grade']} — aim ≤ 6")
    if len(s) > 140:
        score -= 5
        issues.append(f"{len(s)} chars — keep errors ≤ 140")
    if len(sents) > 3:
        score -= 5
        issues.append(f"{len(sents)} sentences — max 3 (what · why · how)")
    score = max(0, score)
    return {
        "score": score,
        "parts": parts,
        "chars": len(s),
        "sentences": len(sents),
        "fk_grade": r["fk_grade"],
        "issues": issues,
        "verdict": "Ship it" if score >= 85 else "Rewrite" if score < 60 else "Tighten",
        "template": "<What happened>. <Why, only if it helps>. <What to do now: verb first>.",
    }


SYNONYM_GROUPS: list[list[str]] = [
    ["sign in", "log in", "login", "signin", "log on"],
    ["sign out", "log out", "logout", "signout"],
    ["sign up", "register", "create account", "join"],
    ["delete", "remove", "trash", "erase"],
    ["cancel", "dismiss", "close", "never mind"],
    ["ok", "okay", "got it", "done", "understood"],
    ["save", "apply", "update", "submit"],
    ["edit", "modify", "change"],
    ["settings", "preferences", "options", "configuration"],
    ["email", "e-mail", "email address", "mail"],
    ["phone", "mobile", "cell", "telephone"],
    ["search", "find", "look up"],
    ["next", "continue", "proceed"],
    ["back", "previous", "return"],
    ["error", "problem", "issue", "failure"],
    ["turn on", "enable", "activate", "switch on"],
    ["turn off", "disable", "deactivate", "switch off"],
    ["workspace", "team", "organization", "organisation", "org"],
    ["user", "member", "person", "account"],
]


@AGENT.tool
def check_consistency(strings: list[str]) -> dict:
    """Find terminology, casing and punctuation inconsistencies across a string table and pick a standard.

    Args:
        strings: All UI strings from the screen/product (plain list; up to 500).
    """
    rows = check_rows(strings, "strings")
    lowered = [str(s).strip() for s in rows if str(s).strip()]
    if not lowered:
        raise ToolError("strings contains no non-empty text.")
    conflicts = []
    for group in SYNONYM_GROUPS:
        found: dict[str, int] = {}
        for term in group:
            rx = re.compile(r"\b" + re.escape(term) + r"\b", re.I)
            n = sum(1 for s in lowered if rx.search(s))
            if n:
                found[term] = n
        if len(found) > 1:
            majority = max(found.items(), key=lambda kv: (kv[1], -group.index(kv[0])))[0]
            conflicts.append({"concept": group[0], "variants": found, "standardise_on": majority, "affected": sum(found.values())})
    # casing drift: same lowercase term appearing with different capitalisation (mid-string)
    forms: dict[str, set] = defaultdict(set)
    for s in lowered:
        for w in text.words(s)[1:]:
            if w.isalpha() and len(w) > 2:
                forms[w.lower()].add(w)
    casing_drift = [{"term": k, "forms": sorted(v)} for k, v in forms.items() if len(v) > 1][:20]
    ending = {"period": sum(1 for s in lowered if s.endswith(".")), "none": sum(1 for s in lowered if not re.search(r"[.!?…]$", s)), "exclamation": sum(1 for s in lowered if s.endswith("!"))}
    cases = defaultdict(int)
    for s in lowered:
        cases[_casing(s)] += 1
    title_case = [s for s in lowered if _casing(s) == "Title Case"][:15]
    fixes = [f"'{c['concept']}': use '{c['standardise_on']}' everywhere ({c['affected']} strings)" for c in conflicts]
    if title_case:
        fixes.append(f"{len(title_case)} Title Case strings → sentence case")
    return {
        "strings_checked": len(lowered),
        "terminology_conflicts": conflicts,
        "casing_drift": casing_drift,
        "case_mix": dict(cases),
        "title_case_examples": title_case,
        "ending_punctuation": ending,
        "fixes": fixes,
        "verdict": "Consistent" if not conflicts and not title_case else f"{len(conflicts)} terminology conflict(s), {len(title_case)} Title Case string(s)",
    }


# Expansion factors vs English, from widely published localisation guidance (IBM/W3C). Short strings expand more.
EXPANSION: dict[str, float] = {
    "de": 1.35, "fr": 1.20, "es": 1.25, "it": 1.20, "pt": 1.25, "nl": 1.30, "sv": 1.15, "da": 1.15,
    "fi": 1.30, "pl": 1.25, "ru": 1.15, "uk": 1.20, "hu": 1.30, "cs": 1.20, "el": 1.25, "tr": 1.20,
    "ar": 1.25, "he": 1.10, "hi": 1.30, "th": 1.15, "vi": 1.30, "id": 1.20, "ja": 0.90, "ko": 0.95, "zh": 0.70,
}


@AGENT.tool
def localization_expansion(text_value: str, container_chars: int, locales: list[str] | None = None) -> dict:
    """Estimate translated string length per locale and flag which ones overflow a container width.

    Uses published expansion factors plus the short-string penalty (strings under 10 chars expand up to +100%).

    Args:
        text_value: The English source string.
        container_chars: Maximum characters that fit in the component at the smallest supported width.
        locales: ISO 639-1 codes to check (default: de, fr, es, pt, ja, fi, ru).
    """
    s = check_text(text_value, "text_value", 1000).strip()
    if not isinstance(container_chars, int) or container_chars < 1:
        raise ToolError("container_chars must be a positive integer.")
    locs = [str(l).lower()[:2] for l in (locales or ["de", "fr", "es", "pt", "ja", "fi", "ru"])]
    unknown = [l for l in locs if l not in EXPANSION]
    if unknown:
        raise ToolError(f"Unknown locale(s): {', '.join(unknown)}. Supported: {', '.join(sorted(EXPANSION))}.")
    n = len(s)
    # IBM guidance: <=10 chars → up to +200% ... use graded factors
    short_bonus = 1.6 if n <= 10 else 1.3 if n <= 20 else 1.1 if n <= 30 else 1.0
    rows, overflow = [], []
    for loc in locs:
        factor = EXPANSION[loc]
        if factor > 1:
            factor = 1 + (factor - 1) * short_bonus
        est = max(1, round(n * factor))
        fits = est <= container_chars
        rows.append({"locale": loc, "factor": round(factor, 2), "estimated_chars": est, "fits": fits})
        if not fits:
            overflow.append(loc)
    worst = max(rows, key=lambda r: r["estimated_chars"])
    safe_source = int(container_chars / worst["factor"])
    return {
        "source_chars": n,
        "container_chars": container_chars,
        "locales": rows,
        "overflow": overflow,
        "safe_source_length": safe_source,
        "verdict": ("Fits in all checked locales" if not overflow else f"Overflows in {', '.join(overflow)} — shorten source to ≤ {safe_source} chars or widen the container to {worst['estimated_chars']}"),
    }
