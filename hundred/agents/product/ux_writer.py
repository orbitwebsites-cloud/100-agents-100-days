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
       fixed-width component. It applies long-text expansion factors (German +35%, French +20%,
       Finnish +30%, Russian +15%, Japanese −10%, etc.) with a short-string uplift for the typical
       length, plus a conservative budget from the W3C/IBM length bands (a 10-char label can reach
       200-300% of its English length). Report `overflow` locales as defects and `at_risk` locales
       as "verify with a real translation". The typical estimate alone under-called real German/
       French/Finnish UI translations about half the time in our checks — never promise a fit from it.
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
    - checkout.cta "Continue to payment" (19 ch) → de typical 28 ch / budget 37 ch; container 24 ch → overflow. Suggest "Pay now".

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
BLAME = re.compile(r"\b(you (?:entered|typed|provided|submitted|gave|made)|your (?:input|entry|mistake)|invalid|illegal|forbidden|not allowed|wrong (?:password|email|code|format|number|value|details)|bad (?:input|request|format|password)|failure|you failed|you must|you need to)\b", re.I)
VAGUE = re.compile(r"\b(something went wrong|an error (?:has )?occurred|unknown error|oops|whoops|unexpected error|try again later|problem occurred|unable to process)\b", re.I)
ACTION_VERB = re.compile(r"\b(try|retry|check|reconnect|refresh|reload|sign in|log in|contact|update|enter|choose|select|remove|add|wait|upgrade|verify|confirm|use|switch|turn on|enable|allow|go to|open|change|reset|resend|shorten|pick|fix|review)\b", re.I)


def _casing(s: str) -> str:
    ws = [w for w in text.words(s) if w.isalpha()]
    if len(ws) < 2:
        return "n/a"
    if s.isupper():
        return "ALL CAPS"
    # judge only non-initial words of each sentence ("New here? Create an account" is sentence case);
    # short particles count too ("Log In", "Sign Up"); all-caps acronyms (PDF, API) are ignored
    later = [w for sent in (text.sentences(s) or [s]) for w in [x for x in text.words(sent) if x.isalpha()][1:] if not (w.isupper() and len(w) > 1)]
    if not later:
        return "n/a"
    caps = sum(1 for w in later if w[0].isupper())
    return "Title Case" if caps >= max(1, len(later) * 0.6) else "sentence case"


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
        if comp in {"button", "link", "menu_item"} and re.match(r"^(login|logout|signin|signout|signup|setup|checkout|backup)$", s.strip(), re.I):
            issues.append("noun used as a verb — buttons take the verb form ('Log out', 'Sign up', 'Set up'), not 'Logout'")
        if comp in {"dialog_title", "heading"} and re.match(r"^(are you sure|confirm|warning|attention)\b", s, re.I):
            issues.append("vague confirmation — name the action and object: 'Delete account?'")
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
    if re.search(r"\b(couldn'?t|can'?t|didn'?t|failed to|unable to|isn'?t|wasn'?t|not (?:saved|sent|found|available)|no (?:connection|internet|results)|too (?:large|long|many)|expired|already|missing|doesn'?t|locked|declined|suspended|blocked|(?:has|have) been \w+(?:ed|en)|(?:was|were) \w+(?:ed|en))\b", s, re.I):
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
    # a code needs a prefix ("Error 401", "code: 5003", "#4012"), a hex value, or an ERRNO-style token (ENOENT);
    # bare numbers ("under 100 MB") and ordinary words ("expired") are not codes
    codes = re.findall(r"(?:\b(?:error|err|code|status)\s*[#:]?\s*[A-Z]*-?\d{2,5}\b|#\d{3,6}\b|\b0x[0-9a-f]+\b|(?-i:\bE[A-Z]{3,}\d*\b))", s, re.I)
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
    ["save", "apply", "submit"],
    ["edit", "modify", "change"],
    ["settings", "preferences", "options", "configuration"],
    ["email", "e-mail", "mail"],
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

    def term_rx(term: str) -> re.Pattern:
        # whole term with inflections (delete → deletes/deleted/deleting); a hyphen counts as part of the
        # word, so "mail" never matches inside "e-mail"
        if term.endswith("e") and " " not in term:
            base = re.escape(term[:-1]) + r"(?:e|es|ed|ing)"
        else:
            base = re.escape(term) + r"(?:s|es|ed|ing)?"
        return re.compile(r"(?<![\w-])" + base + r"(?![\w-])", re.I)

    chosen: dict[str, str] = {}
    for group in SYNONYM_GROUPS:
        found: dict[str, int] = {}
        masked = list(lowered)
        # longest variants first; a span claimed by "log in" can't also be counted again by a shorter variant
        for term in sorted(group, key=len, reverse=True):
            rx = term_rx(term)
            n = 0
            for idx in range(len(masked)):
                if rx.search(masked[idx]):
                    n += 1
                    masked[idx] = rx.sub(" ", masked[idx])
            if n:
                found[term] = n
        if found:
            chosen[group[0]] = max(found.items(), key=lambda kv: (kv[1], -group.index(kv[0])))[0]
        if len(found) > 1:
            conflicts.append({"concept": group[0], "variants": found, "standardise_on": chosen[group[0]], "affected": sum(found.values())})
    # paired terms must share a verb: "Sign in" pairs with "Sign out", "Log in" with "Log out"
    fam = lambda t: "log" if t.startswith("log") else "sign"  # noqa: E731
    if "sign in" in chosen and "sign out" in chosen and fam(chosen["sign in"]) != fam(chosen["sign out"]):
        want = fam(chosen["sign in"])
        conflicts.append({"concept": "sign in / sign out pair", "variants": {chosen["sign in"]: 1, chosen["sign out"]: 1}, "standardise_on": f"{want} in / {want} out", "affected": 2})
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


# Long-text expansion factors vs English (common localisation rules of thumb). Short strings expand more —
# see the W3C/IBM length bands applied in localization_expansion.
EXPANSION: dict[str, float] = {
    "de": 1.35, "fr": 1.20, "es": 1.25, "it": 1.20, "pt": 1.25, "nl": 1.30, "sv": 1.15, "da": 1.15,
    "fi": 1.30, "pl": 1.25, "ru": 1.15, "uk": 1.20, "hu": 1.30, "cs": 1.20, "el": 1.25, "tr": 1.20,
    "ar": 1.25, "he": 1.10, "hi": 1.30, "th": 1.15, "vi": 1.30, "id": 1.20, "ja": 0.90, "ko": 0.95, "zh": 0.70,
}


@AGENT.tool
def localization_expansion(text_value: str, container_chars: int, locales: list[str] | None = None) -> dict:
    """Estimate translated string length per locale (typical and worst-case budget) and flag overflow.

    Two numbers per locale. `estimated_chars` is the typical length (long-text language factor with a
    modest short-string uplift). `budget_chars` is the conservative layout budget from IBM's length
    bands as published by W3C ("Text size in translation": ~200-300% of English up to 10 chars,
    180-200% for 11-20, 160-180% for 21-30, 140-160% for 31-50, 151-170% for 51-70, ~130% above 70),
    scaled per language. A string whose typical length overflows is `overflow`; one that fits typically
    but not within the budget is `at_risk` — check it against a real translation before shipping.

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
    typical_uplift = 1.6 if n <= 10 else 1.3 if n <= 20 else 1.1 if n <= 30 else 1.0
    # IBM/W3C band (lower end of each published range), each language scaled relative to the >70-char band (1.30)
    band = 2.0 if n <= 10 else 1.8 if n <= 20 else 1.6 if n <= 30 else 1.4 if n <= 50 else 1.51 if n <= 70 else 1.3
    budget_uplift = (band - 1) / 0.30
    rows, overflow, at_risk = [], [], []
    for loc in locs:
        base = EXPANSION[loc]
        typ = 1 + (base - 1) * typical_uplift if base > 1 else base
        bud = 1 + (base - 1) * budget_uplift if base > 1 else base
        est, budget = max(1, round(n * typ)), max(1, round(n * bud))
        fits = est <= container_chars
        rows.append({"locale": loc, "factor": round(typ, 2), "estimated_chars": est, "budget_factor": round(bud, 2), "budget_chars": budget, "fits": fits, "fits_budget": budget <= container_chars})
        if not fits:
            overflow.append(loc)
        elif budget > container_chars:
            at_risk.append(loc)
    worst = max(rows, key=lambda r: r["budget_chars"])
    safe_source = int(container_chars / worst["budget_factor"])
    if overflow:
        verdict = f"Overflows in {', '.join(overflow)}" + (f"; at risk in {', '.join(at_risk)}" if at_risk else "") + f" — shorten source to ≤ {safe_source} chars or widen the container to {worst['budget_chars']}"
    elif at_risk:
        verdict = f"Fits typically; at risk in {', '.join(at_risk)} under the W3C/IBM budget — verify with a real translation or allow {worst['budget_chars']} chars"
    else:
        verdict = "Fits in all checked locales, even at the W3C/IBM budget"
    return {
        "source_chars": n,
        "container_chars": container_chars,
        "locales": rows,
        "overflow": overflow,
        "at_risk": at_risk,
        "safe_source_length": safe_source,
        "verdict": verdict,
    }
