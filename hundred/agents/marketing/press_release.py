"""Press Release Pro — AP-style linting, release structure scoring, pitch-email check and embargo timing."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import require_text, us_utc_offset

AGENT = Agent(
    slug="press-release",
    name="Press Release Pro",
    category="marketing",
    tagline="Write releases journalists can run as-is: AP style, inverted pyramid, a 120-word pitch, and embargo timing that lands.",
    description=(
        "Drafts and edits press releases and media pitches to newsroom standards. Lints for AP style "
        "(numerals, dates, months, percent, titles, 'said', state abbreviations, times), scores the "
        "structure (headline length, dateline, 35-word lede, quotes with attribution, boilerplate, "
        "contact, end mark), checks the pitch email for length, personalisation and a clear ask, and "
        "works out embargo lift, pitch and follow-up dates across time zones on business days."
    ),
    triggers=[
        "write a press release",
        "edit this press release for AP style",
        "pitch email to journalists",
        "when should we send the embargoed release",
        "media pitch / PR announcement",
        "press release headline and boilerplate",
    ],
    examples=[
        "Write a press release: we raised a $6M seed led by Acme Ventures to expand our clinic scheduling software.",
        "Check this release for AP style and structure before it goes to the wire.",
        "Embargo lifts Tuesday 9 a.m. ET. When do we pitch, follow up, and what time is that in London?",
    ],
    connectors=["Gmail", "Google Docs", "Notion", "HubSpot", "Slack"],
    playbook="""
    ## Standard
    You are a former newswire editor who now runs comms for startups. Excellent means: a
    journalist could paste the release into their CMS and publish, the lede answers who /
    what / when / where / why in ≤ 35 words, every number and date is in AP style, the
    quotes say something a person would actually say, and the pitch is under 150 words
    with one clear ask. The metric that matters is pickups (stories written), not sends.

    ## Intake
    Need: the news (what's actually new), the numbers you can state on record, the
    spokesperson(s) and titles, the date/embargo, boilerplate and media contact. If the
    "news" isn't news (a feature nobody outside will care about), say so and propose the
    angle that is (customer result, data, trend). If the spokesperson or contact is
    missing, use placeholders in [brackets] and flag them. Ask at most 3 questions.

    ## Procedure
    1. **Find the angle** using the newsworthiness test in Frameworks. State it in one
       line before drafting; if it fails, propose a data or customer-story angle instead.
    2. **Draft the release** to the structure in Output format: headline ≤ 80 chars (≤ 10
       words, present tense, no hype), optional subhead, dateline, 35-word lede, two
       supporting paragraphs with numbers, one quote each from the company and (ideally) a
       customer/investor, availability/pricing, boilerplate, media contact, "###".
    3. **Lint style.** Call `press_release__ap_style_check` with the full text. Apply every
       fix (numerals, month abbreviations, percent, "said", title capitalisation, times,
       state names: abbreviated in the dateline, spelled out in the body). Re-run until clean.
    4. **Score structure.** Call `press_release__release_structure` with the text. Fix
       anything flagged: lede length, missing dateline, quote without attribution, no
       boilerplate/contact/end mark, too many superlatives.
    5. **Write the pitch** (≤ 150 words): one personal line that proves you read their
       work, the news in one sentence, why their readers care, the ask (embargoed
       briefing / exclusive / assets), the release pasted below the signature — no
       attachments. Call `press_release__pitch_email_check` and fix the flags.
    6. **Time it.** Call `press_release__embargo_timing` with the lift moment and the
       audience time zones. Use the returned pitch, follow-up and lift dates; never pitch on
       a Friday afternoon or lift on a Monday morning if you can help it.
    7. **Deliver** in the output format, with the distribution list plan (tier 1 exclusives
       → tier 2 embargoed → wire on lift) and the assets folder checklist.

    ## Frameworks
    - **Newsworthiness test** (pass ≥ 2): timeliness, magnitude (numbers), novelty (first/
      only), conflict/tension, human impact, prominence (known names), trend relevance.
    - **Inverted pyramid:** most important fact first; each paragraph less essential than
      the last; a sub-editor can cut from the bottom.
    - **AP style essentials:** spell out one–nine, numerals 10+ (always numerals for ages,
      money, percent, dates); abbreviate Jan., Feb., Aug., Sept., Oct., Nov., Dec. when
      with a date, never March–July; "%" with numerals; "said" (not "stated/exclaimed");
      capitalise titles only directly before a name; times as "9 a.m."/"noon"; states
      abbreviated in datelines (Calif., N.Y.) but spelled out in body text, and 30 big
      cities (SAN FRANCISCO, NEW YORK, CHICAGO…) take no state; no Oxford comma in simple
      series; no exclamation marks.
    - **Quotes:** 1-2 sentences, opinion or forward-looking (facts go in the body), no
      "we're thrilled/excited".
    - **Pitch rules:** subject ≤ 60 chars, no "Press release:" in the subject, ≤ 150
      words, one ask, one link, no attachments, personalised first line.
    - **Timing:** pitch 5-7 business days before lift; follow up once, 2 business days
      before; lift Tue-Thu 6-10 a.m. ET for U.S. media; avoid the hours around big events.
    - Not legal advice: material financial claims for public companies need legal review.

    ## Output format
    ```
    # <Headline ≤ 80 chars>
    *<Subhead, one sentence, optional>*

    CITY, State, Mon. D, YYYY — <Lede ≤ 35 words: who, what, when, where, why>.

    <Paragraph 2: the numbers / how it works.>

    "<Quote>," said <Name>, <title> at <Company>. "<Second sentence.>"

    <Paragraph 3: context, customer, availability, pricing.>

    "<Customer/investor quote>," said <Name>, <title>, <Org>.

    ## About <Company>
    <Boilerplate ≤ 100 words.>

    Media contact: <Name>, <email>, <phone>
    ###

    ---
    ## Pitch (≤ 150 words)
    Subject: <≤ 60 chars>
    <body>

    ## Timing
    Pitch <date> · Follow-up <date> · Embargo lifts <date time ET / PT / GMT>
    ```

    ## Anti-patterns
    - Headlines with "revolutionary", "leading", "excited to announce".
    - Ledes that start with the company's founding story.
    - Quotes that restate the lede in marketing voice.
    - Pitching the whole list with the same email and "Hope you're well".
    - Attaching a PDF; sending on Friday at 4 p.m.
    - Wire distribution as the strategy (it's a compliance step, not outreach).
    """,
)

NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
MONTHS_ABBR = {"january": "Jan.", "february": "Feb.", "august": "Aug.", "september": "Sept.", "october": "Oct.", "november": "Nov.", "december": "Dec."}
MONTHS_FULL = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
STATES = {
    "alabama": "Ala.", "arizona": "Ariz.", "arkansas": "Ark.", "california": "Calif.", "colorado": "Colo.", "connecticut": "Conn.", "delaware": "Del.", "florida": "Fla.", "georgia": "Ga.", "illinois": "Ill.", "indiana": "Ind.", "kansas": "Kan.", "kentucky": "Ky.", "louisiana": "La.", "maryland": "Md.", "massachusetts": "Mass.", "michigan": "Mich.", "minnesota": "Minn.", "mississippi": "Miss.", "missouri": "Mo.", "montana": "Mont.", "nebraska": "Neb.", "nevada": "Nev.", "new hampshire": "N.H.", "new jersey": "N.J.", "new mexico": "N.M.", "new york": "N.Y.", "north carolina": "N.C.", "north dakota": "N.D.", "oklahoma": "Okla.", "oregon": "Ore.", "pennsylvania": "Pa.", "rhode island": "R.I.", "south carolina": "S.C.", "south dakota": "S.D.", "tennessee": "Tenn.", "vermont": "Vt.", "virginia": "Va.", "washington": "Wash.", "west virginia": "W.Va.", "wisconsin": "Wis.", "wyoming": "Wyo.",
}
POSTAL = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
# AP datelines: these cities stand alone, without a state.
STANDALONE_CITIES = frozenset(
    """Atlanta|Baltimore|Boston|Chicago|Cincinnati|Cleveland|Dallas|Denver|Detroit|Honolulu|Houston|Indianapolis|Las Vegas|
    Los Angeles|Miami|Milwaukee|Minneapolis|New Orleans|New York|Oklahoma City|Philadelphia|Phoenix|Pittsburgh|St. Louis|
    Salt Lake City|San Antonio|San Diego|San Francisco|Seattle|Washington""".replace("\n", "").replace("    ", "").split("|")
)
DATELINE_RE = re.compile(
    r"^(?P<city>[A-Z][A-Z .'-]+?),\s*(?:(?P<state>[A-Z][A-Za-z. ]+?),\s*)?(?:[A-Z][a-z]+\.?\s+\d{1,2},\s*\d{4})\s*[—–-]{1,2}",
    re.M,
)
HYPE = re.compile(r"\b(revolutionary|groundbreaking|game-chang\w+|world-class|best-in-class|leading|cutting-edge|state-of-the-art|unique|innovative|disruptive|excited to announce|thrilled|proud to announce|pleased to announce|first-ever|unprecedented|next-generation|seamless|robust)\b", re.I)
ATTRIB_VERBS = re.compile(r"\b(stated|exclaimed|noted|commented|remarked|explained|added|shared|expressed|enthused|affirmed|announced)\b(?=[^.]{0,80}\b(CEO|founder|chief|president|director|head|vp|officer|manager|partner)\b|\s*[A-Z])", re.I)
TITLE_WORDS = r"(?:Chief\s+\w+\s+Officer|CEO|CTO|CFO|COO|CMO|President|Vice\s+President|Founder|Co-founder|Director|Manager|Head\s+of\s+\w+)"


def _pos_ctx(t: str, m: re.Match) -> dict:
    return {"position": m.start(), "found": m.group(0), "context": t[max(0, m.start() - 25) : m.end() + 25].replace("\n", " ")}


@AGENT.tool
def ap_style_check(content: str) -> dict:
    """Lint a press release for AP style: numerals, month abbreviations, percent, 'said', title capitalisation, times, states, hype, punctuation.

    Call after drafting and re-run until clean.

    Args:
        content: The full press release text.
    """
    t = require_text(content, "content")
    findings = []

    def add(rule: str, m: re.Match, fix: str, severity: str = "fix") -> None:
        findings.append({"rule": rule, "severity": severity, "fix": fix, **_pos_ctx(t, m)})

    # Numerals 10+ spelled out
    for m in re.finditer(r"\b(ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\b", t, re.I):
        # allow sentence-initial spelled numbers (AP spells out numbers starting a sentence)
        before = t[: m.start()].rstrip()
        if before and before[-1] not in ".!?\n" and not (before.endswith('"') and len(before) > 1 and before[-2] in ".!?"):
            add("numerals: use figures for 10 and above", m, "Use the numeral (e.g. 'twenty' → '20') unless it starts the sentence.")
    # One–nine as digits (except with %, $, ages, dates, times, decimals, versions)
    for m in re.finditer(r"(?<![\d.,$€£:/-])\b([1-9])\b(?![\d.,:%/-])(?!\s*(%|percent|a\.m\.|p\.m\.|am\b|pm\b|years?\b|-year|million|billion|trillion|x\b|st\b|nd\b|rd\b|th\b|pounds?\b|inches|feet|miles|hours?\b|minutes?\b|seconds?\b|days?\b|weeks?\b|months?\b|out of|of \d|to \d|and \d|,))", t, re.I):
        prev = t[max(0, m.start() - 12) : m.start()].lower()
        if re.search(r"(version|v|series|q|fy|phase|round|tier|step|chapter|page|figure|table|no\.|#|\$|room|suite|floor|grade|age|aged)\s*$", prev):
            continue
        if re.search(r"\b(jan|feb|march|april|may|june|july|aug|sept|sep|oct|nov|dec)\.?\s$", prev):
            continue  # dates keep figures
        add("numerals: spell out one through nine", m, f"'{m.group(1)}' → '{['zero','one','two','three','four','five','six','seven','eight','nine'][int(m.group(1))]}' (keep figures for ages, money, percent, dates, times, dimensions).", "check")
    # Months with a date should be abbreviated (Jan., Feb., Aug., Sept., Oct., Nov., Dec.)
    for m in re.finditer(r"\b(January|February|August|September|October|November|December)\s+\d{1,2}\b", t):
        add("dates: abbreviate month with a date", m, f"'{m.group(1)}' → '{MONTHS_ABBR[m.group(1).lower()]}'")
    for m in re.finditer(r"\b(Jan|Feb|Aug|Sept|Sep|Oct|Nov|Dec)\b(?!\.)\s+\d{1,2}(?:st|nd|rd|th)?\b", t):
        add("dates: month abbreviation needs a period", m, f"'{m.group(1)}' → '{m.group(1)}.'")
    for m in re.finditer(r"\b(Mar|Apr|Jun|Jul)\.?\s+\d{1,2}(?:st|nd|rd|th)?\b", t):
        add("dates: March, April, June, July are never abbreviated", m, "Spell out the month.")
    for m in re.finditer(r"\b(Jan|Feb|Aug|Sept|Sep|Oct|Nov|Dec|March|April|May|June|July)\.?\s+(\d{1,2})(st|nd|rd|th)\b", t):
        add("dates: no ordinal suffixes", m, f"'{m.group(2)}{m.group(3)}' → '{m.group(2)}'")
    for m in re.finditer(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", t):
        add("dates: write out the date", m, "Use 'Oct. 5, 2026' style, not 10/5/2026.")
    # Percent
    for m in re.finditer(r"\b\d+(\.\d+)?\s+percent\b", t):
        add("percent: use % with figures", m, "'15 percent' → '15%' (AP 2019).")
    for m in re.finditer(r"\b(?:one|two|three|four|five|six|seven|eight|nine)\s*(%|percent)", t, re.I):
        add("percent: use figures with %", m, "Write the number as a figure: 'five percent' → '5%'.")
    # Attribution verbs
    for m in re.finditer(r"[\"”][,.]?\s*(stated|exclaimed|commented|remarked|noted|enthused|expressed|shared|affirmed|explained|added)\b", t, re.I):
        add("attribution: use 'said'", m, f"'{m.group(1)}' → 'said'")
    for m in re.finditer(r"\b(according to|says)\s+[A-Z][a-z]+\s+[A-Z][a-z]+", t):
        if m.group(1) == "says":
            add("attribution: past tense 'said' in releases", m, "'says' → 'said'", "check")
    # Titles capitalised after a name / standalone
    for m in re.finditer(rf"\b([A-Z][a-z]+ [A-Z][a-z]+),\s+({TITLE_WORDS})\b", t):
        title = m.group(2)
        if title.isupper() or title.lower() in ("president",) or " " in title:
            if not title.isupper():
                add("titles: lowercase a title that follows the name", m, f"'{title}' → '{title.lower()}' (capitalise only directly before a name; acronyms like CEO stay).", "check")
    for m in re.finditer(r"\b(the|our|its|their|as)\s+(Chief\s+\w+\s+Officer|Founder|Co-Founder|President|Vice\s+President|Director)\b", t):
        add("titles: lowercase titles not directly before a name", m, f"'{m.group(2)}' → '{m.group(2).lower()}'")
    # Times
    for m in re.finditer(r"\b\d{1,2}(:\d{2})?\s*(AM|PM|A\.M|P\.M|am|pm)\b(?!\.)", t):
        add("time: use 'a.m.' / 'p.m.'", m, "'9 AM' → '9 a.m.'")
    for m in re.finditer(r"\b(\d{1,2}):00\s*(a\.m\.|p\.m\.)", t):
        add("time: drop ':00' on the hour", m, f"'{m.group(1)}:00 {m.group(2)}' → '{m.group(1)} {m.group(2)}'")
    for m in re.finditer(r"\b12\s*(a\.m\.|p\.m\.|noon|midnight)\b", t):
        if m.group(1) in ("a.m.", "p.m."):
            add("time: use 'noon' / 'midnight'", m, "'12 p.m.' → 'noon'; '12 a.m.' → 'midnight'")
    # States. AP (since 2014): abbreviate the state in the DATELINE only; spell it out in body text.
    # Thirty major cities stand alone in datelines with no state at all.
    dl = DATELINE_RE.search(t)
    dl_span = (dl.start(), dl.end()) if dl else (-1, -1)

    def in_dateline(m: re.Match) -> bool:
        return dl_span[0] <= m.start() < dl_span[1]

    if dl:
        city = dl.group("city").strip().title()
        if city in STANDALONE_CITIES and dl.group("state"):
            add("dateline: this city stands alone", dl, f"AP datelines use '{city.upper()}' with no state.", "fix")
    for full, abbr in STATES.items():
        for m in re.finditer(rf"\b([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?),\s+({full.title()})\b", t):
            if in_dateline(m):
                add("dateline: abbreviate the state", m, f"'{m.group(2)}' → '{abbr}' in the dateline", "fix")
        for m in re.finditer(rf"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?),\s+({re.escape(abbr)})(?=\W)", t):
            if not in_dateline(m):
                add("states: spell out the state in body text", m, f"'{m.group(2)}' → '{full.title()}' (AP abbreviates only in datelines)")
    for m in re.finditer(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?),\s+([A-Z]{2})\b(?!\s*\d{5})", t):
        code = m.group(2)
        if code in POSTAL and not in_dateline(m):
            add("states: no postal codes in text", m, f"'{code}' → '{POSTAL[code]}'")
        elif code in POSTAL and in_dateline(m):
            full = POSTAL[code].lower()
            add("dateline: use AP state abbreviation, not postal code", m, f"'{code}' → '{STATES.get(full, POSTAL[code])}'")
    # Miscellaneous AP preferences
    misc = [
        (r"\btowards\b", "'towards' → 'toward'"), (r"\be-mail\b", "'e-mail' → 'email'"), (r"\bWeb site\b|\bWebsite\b(?!\s+[A-Z])", "'website' is lowercase"),
        (r"\bInternet\b", "'internet' is lowercase"), (r"\bokay\b", "'okay' → 'OK'"), (r"\badvisor\b", "'advisor' → 'adviser'"), (r"\bUS\b(?=\s+(?:company|market|customers|based|and|team))", "'US' → 'U.S.'"),
        (r"\bover\s+\$?\d", "'over 500' → 'more than 500' (AP allows both; 'more than' is safer with quantities)"), (r"\bUtilize\b|\butilize\b", "'utilize' → 'use'"), (r"\bhealthcare\b", "'healthcare' → 'health care'"),
        (r"\bnon-profit\b", "'non-profit' → 'nonprofit'"), (r"\bstart-up\b", "'start-up' → 'startup'"), (r"\bon-line\b", "'on-line' → 'online'"), (r"\bTwitter\b(?=\s+\()", "check platform naming"),
    ]
    for pat, fix in misc:
        for m in re.finditer(pat, t):
            add("usage", m, fix, "check")
    # Punctuation / hype
    for m in re.finditer(r"!", t):
        add("punctuation: no exclamation marks", m, "Replace with a period.")
    for m in re.finditer(r"\b(\w+), (\w+), and (\w+)\b", t):
        if m.group(2).lower() in STATES or m.group(2) in POSTAL.values():
            continue  # "Austin, Texas, and Denver": the comma closes "City, State," — not an Oxford comma
        add("punctuation: no Oxford comma in a simple series", m, f"'{m.group(1)}, {m.group(2)}, and {m.group(3)}' → '{m.group(1)}, {m.group(2)} and {m.group(3)}'", "check")
    for m in HYPE.finditer(t):
        add("hype: journalists cut this", m, f"Delete '{m.group(0)}' or replace with a fact/number.", "check")
    findings.sort(key=lambda f: f["position"])
    by_rule = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    must = sum(1 for f in findings if f["severity"] == "fix")
    return {
        "findings": findings,
        "counts_by_rule": by_rule,
        "must_fix": must,
        "check": len(findings) - must,
        "clean": not findings,
        "summary": "AP style clean." if not findings else f"{must} must-fix and {len(findings) - must} check item(s) across {len(by_rule)} rule(s).",
    }


@AGENT.tool
def release_structure(content: str) -> dict:
    """Score a press release's structure: headline, dateline, lede length and 5 Ws, quotes with attribution, boilerplate, contact, end mark, length, hype.

    Call after the AP lint; ship at grade A/B only.

    Args:
        content: The full press release text (headline first).
    """
    t = require_text(content, "content")
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    headline = lines[0].lstrip("# ").strip("*_ ") if lines else ""
    hw = text.words(headline)
    checks: dict[str, bool] = {}
    notes: list[str] = []
    checks["headline_length"] = 0 < len(headline) <= 80 and len(hw) <= 12
    if not checks["headline_length"]:
        notes.append(f"Headline is {len(headline)} chars / {len(hw)} words — keep ≤ 80 chars, ≤ 12 words.")
    checks["headline_no_hype"] = not HYPE.search(headline)
    if not checks["headline_no_hype"]:
        notes.append("Headline contains hype words.")
    checks["headline_present_tense"] = not re.search(r"\b(announced|launched|released|unveiled|was|were)\b", headline, re.I)
    if not checks["headline_present_tense"]:
        notes.append("Headline should be present tense ('Acme launches…').")
    dateline = re.search(r"^([A-Z][A-Z .]+),?\s*(?:[A-Z][a-zA-Z.]+,?\s*)?(?:[A-Z][a-z]+\.?\s+\d{1,2},\s*\d{4})\s*[—–-]{1,2}\s*", t, re.M)
    checks["dateline"] = bool(dateline)
    if not dateline:
        notes.append("No dateline found — start the body with 'CITY, State, Mon. D, YYYY — '.")
    # Lede: the paragraph that starts at the dateline; otherwise the first body paragraph after the headline.
    if dateline:
        rest = t[dateline.end() :]
        lede_text = re.split(r"\n\s*\n|\n", rest, maxsplit=1)[0].strip()
        lede = dateline.group(0) + lede_text
        after = rest[len(lede_text) :]
        body_paras = [lede] + [p.strip() for p in re.split(r"\n\s*\n", after) if p.strip()]
    else:
        body_lines = lines[1:]
        body_paras = [p.strip() for p in re.split(r"\n\s*\n", "\n".join(body_lines)) if p.strip()]
        body_paras = [p for p in body_paras if not p.startswith(("*", "_", "#"))] or body_paras
        lede = body_paras[0] if body_paras else ""
        lede_text = lede
    lede_sentences = text.sentences(lede_text)
    first_sentence = lede_sentences[0] if lede_sentences else lede_text
    lw = len(text.words(first_sentence))
    checks["lede_length"] = 0 < lw <= 35
    if not checks["lede_length"]:
        notes.append(f"Lede sentence is {lw} words — cut to ≤ 35.")
    checks["lede_has_who_what"] = bool(re.search(r"\b(today|announced|launch|launches|introduc|releas|raise|raised|partner|acquir|report|open|expand|names|appoint)\w*\b", lede_text, re.I))
    if not checks["lede_has_who_what"]:
        notes.append("Lede doesn't state the news action (launches / raises / announces).")
    checks["lede_has_when"] = bool(re.search(r"\btoday\b|\b\d{4}\b|\b(Jan\.|Feb\.|March|April|May|June|July|Aug\.|Sept\.|Oct\.|Nov\.|Dec\.)\b", lede, re.I))
    if not checks["lede_has_when"]:
        notes.append("Lede has no 'when' (today / date).")
    checks["lede_no_founding_story"] = not re.search(r"\b(founded in|was founded|since \d{4}|began as)\b", lede_text, re.I)
    if not checks["lede_no_founding_story"]:
        notes.append("Lede starts with history — lead with the news.")
    quotes = re.findall(r"[\"“]([^\"”]{20,600})[\"”]", t)
    attributed = re.findall(r"[\"”][,.]?\s*(?:said|says)\s+[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+)*,\s*[^.\n]{3,80}", t)
    checks["has_quote"] = len(quotes) >= 1
    checks["quotes_attributed"] = len(quotes) >= 1 and len(attributed) >= min(len(quotes), 1)
    if not checks["has_quote"]:
        notes.append("No quote — add one from the spokesperson and ideally one from a customer/investor.")
    elif not checks["quotes_attributed"]:
        notes.append("Quote lacks attribution with a title ('said Jane Doe, CEO of Acme').")
    checks["two_sources"] = len(attributed) >= 2
    if not checks["two_sources"]:
        notes.append("Only one attributed voice — a second (customer, partner, investor) adds credibility.")
    checks["quote_not_first_para"] = not (body_paras and body_paras[0].lstrip().startswith(('"', "“")))
    boiler = re.search(r"^#*\s*About\s+\S+", t, re.M | re.I)
    checks["boilerplate"] = bool(boiler)
    if not boiler:
        notes.append("No 'About <Company>' boilerplate.")
    contact = re.search(r"(media|press)\s+contact|contact:", t, re.I)
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", t)
    checks["media_contact"] = bool(contact and email)
    if not checks["media_contact"]:
        notes.append("Missing media contact with an email.")
    checks["end_mark"] = bool(re.search(r"^\s*(###|-30-|ENDS)\s*$", t, re.M))
    if not checks["end_mark"]:
        notes.append("Add '###' on its own line at the end.")
    n_words = len(text.words(t))
    checks["length_ok"] = 300 <= n_words <= 800
    if not checks["length_ok"]:
        notes.append(f"{n_words} words — aim for 300-600 (800 max).")
    numbers = len(re.findall(r"\d[\d,.]*", t))
    checks["has_numbers"] = numbers >= 3
    if not checks["has_numbers"]:
        notes.append("Fewer than 3 figures — add numbers (customers, funding, growth, dates).")
    hype = [m.group(0) for m in HYPE.finditer(t)]
    checks["low_hype"] = len(hype) <= 1
    if not checks["low_hype"]:
        notes.append(f"{len(hype)} hype words: {', '.join(sorted(set(h.lower() for h in hype))[:5])}.")
    rd = text.readability(t)
    checks["readable"] = (rd["fk_grade"] or 0) <= 12
    if not checks["readable"]:
        notes.append(f"Reading grade {rd['fk_grade']} — newsroom copy sits around grade 9-11.")
    passed = sum(checks.values())
    score = round(100 * passed / len(checks))
    grade = "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 60 else "D"
    return {
        "headline": headline,
        "headline_chars": len(headline),
        "lede_words": lw,
        "words": n_words,
        "quotes": len(quotes),
        "attributed_quotes": len(attributed),
        "fk_grade": rd["fk_grade"],
        "checks": checks,
        "passed": f"{passed}/{len(checks)}",
        "score": score,
        "grade": grade,
        "notes": notes,
        "summary": f"Grade {grade} ({passed}/{len(checks)})." + (" Ready for the wire." if grade in "AB" and not notes else f" Fix: {notes[0]}" if notes else ""),
    }


@AGENT.tool
def pitch_email_check(subject: str, body: str, journalist_name: str = "", outlet: str = "") -> dict:
    """Check a media pitch: subject length, word count (≤ 150), personalised first line, one clear ask, links, attachments, clichés.

    Call on every pitch before sending; a pitch that fails personalisation goes to nobody.

    Args:
        subject: The email subject line.
        body: The pitch body (without the pasted release).
        journalist_name: The journalist's first or full name, to check personalisation.
        outlet: The outlet name, to check personalisation.
    """
    s = require_text(subject, "subject", 500).strip()
    b = require_text(body, "body")
    ws = text.words(b)
    n = len(ws)
    issues, fixes = [], []
    score = 100
    if len(s) > 60:
        score -= 10
        issues.append(f"subject {len(s)} chars — keep ≤ 60")
    if re.search(r"press release|for immediate release|announcement", s, re.I):
        score -= 15
        issues.append("subject says 'press release/announcement' — reads like a blast")
        fixes.append("Subject = the news as a headline a reader would click, or 'Exclusive: …' / 'Embargoed: …'.")
    if re.search(r"\b(exclusive|embargo)\b", s, re.I):
        score += 5
    if n > 150:
        score -= min(30, (n - 150) // 5 * 3 + 5)
        issues.append(f"{n} words — cut to ≤ 150")
        fixes.append("Three short paragraphs: personal line, the news + why their readers care, the ask.")
    first_para = re.split(r"\n\s*\n|\n", b.strip())[0]
    named = bool(journalist_name and re.search(rf"\b{re.escape(journalist_name.split()[0])}\b", first_para))
    personal = bool(re.search(r"\b(your (piece|story|article|coverage|column|newsletter|reporting|post|episode|interview)|you wrote|you covered|you reported|loved your|read your)\b", b, re.I))
    if outlet and re.search(rf"\b{re.escape(outlet)}\b", b, re.I):
        personal = True
    if not personal:
        score -= 12 if named else 25
        issues.append("names them but nothing shows you read their work" if named else "no personalisation — nothing shows you read their work")
        fixes.append("First line: reference a specific recent piece and why this fits it.")
    if re.search(r"\b(hope (this|you)|i hope you're well|hope you are well|to whom it may concern|dear (sir|madam|journalist|editor))\b", b, re.I):
        score -= 10
        issues.append("opens with a cliché greeting")
    ask = re.search(r"\b(would you (be )?(interested|like|want)|can i (send|share|offer)|happy to (arrange|set up|share|offer)|interview|briefing|exclusive|embargo|demo|early access|let me know if)\b", b, re.I)
    if not ask:
        score -= 20
        issues.append("no clear ask")
        fixes.append("End with one ask: exclusive, embargoed briefing, interview slot, or assets.")
    links = re.findall(r"https?://\S+", b)
    if len(links) > 2:
        score -= 10
        issues.append(f"{len(links)} links — keep to 1-2")
    if re.search(r"\b(attached|attachment|see attached|pdf attached)\b", b, re.I):
        score -= 15
        issues.append("mentions an attachment — paste the release below your signature instead")
    hype = sorted({m.group(0).lower() for m in HYPE.finditer(b)})
    if hype:
        score -= min(15, 5 * len(hype))
        issues.append(f"hype words: {', '.join(hype[:4])}")
    if not re.search(r"\d", b):
        score -= 10
        issues.append("no numbers — give the journalist a fact to hang the story on")
    why_readers = bool(re.search(r"\b(your readers|your audience|your listeners|for readers|relevant to)\b", b, re.I))
    if not why_readers:
        score -= 5
        issues.append("doesn't say why their readers care")
    score = max(0, min(100, score))
    grade = "send" if score >= 75 else "revise" if score >= 55 else "rewrite"
    return {
        "subject_chars": len(s),
        "words": n,
        "personalised": personal,
        "has_ask": bool(ask),
        "links": len(links),
        "score": score,
        "grade": grade,
        "issues": issues,
        "fixes": fixes,
        "summary": f"{score}/100 — {grade}. " + (issues[0] if issues else "Clean pitch."),
    }


@AGENT.tool
def embargo_timing(embargo_lift: str, audience_utc_offsets: list[float] = [-5.0, -8.0, 0.0], pitch_lead_business_days: int = 6, holidays: list[str] = []) -> dict:
    """From the embargo lift moment, compute pitch date, follow-up date and lift time in each audience time zone, with weekday/hour warnings.

    Call once the lift is set. Pitch 5-7 business days ahead; one follow-up 2 business days before lift.

    Args:
        embargo_lift: Lift moment as ISO datetime with offset, e.g. 2026-10-13T09:00:00-04:00.
        audience_utc_offsets: UTC offsets (hours) of the newsrooms you're pitching, e.g. [-4, -7, 1].
        pitch_lead_business_days: Business days before lift to send the pitch (default 6; 5-7 recommended).
        holidays: Non-working dates (YYYY-MM-DD) to skip.
    """
    try:
        lift = datetime.fromisoformat(embargo_lift.strip())
    except (ValueError, AttributeError):
        raise ToolError("embargo_lift must be an ISO datetime with offset, e.g. 2026-10-13T09:00:00-04:00.") from None
    if lift.tzinfo is None:
        raise ToolError("embargo_lift needs a UTC offset (e.g. -04:00).")
    if not 1 <= pitch_lead_business_days <= 30:
        raise ToolError("pitch_lead_business_days must be 1-30.")
    if not audience_utc_offsets or len(audience_utc_offsets) > 12 or any(o < -12 or o > 14 for o in audience_utc_offsets):
        raise ToolError("Provide 1-12 UTC offsets between -12 and +14.")
    hol = {dates.parse_date(h) for h in holidays}
    lift_date = lift.date()
    pitch = dates.add_business_days(lift_date, -pitch_lead_business_days, hol)
    follow = dates.add_business_days(lift_date, -2, hol)
    exclusive_offer = dates.add_business_days(lift_date, -(pitch_lead_business_days + 3), hol)
    warnings = []
    if lift.weekday() >= 5:
        warnings.append(f"Lift is on a {lift.strftime('%A')} — move to Tuesday-Thursday.")
    elif lift.weekday() == 0 and lift.hour < 10:
        warnings.append("Monday-morning lift competes with the weekend backlog; Tuesday is stronger.")
    elif lift.weekday() == 4 and lift.hour >= 12:
        warnings.append("Friday-afternoon lift is where news goes to die.")
    if lift_date in hol:
        warnings.append("Lift date is a holiday.")
    if pitch.weekday() == 4:
        warnings.append("Pitch lands on a Friday — send before noon or move to Thursday.")
    local_times = {}
    for o in audience_utc_offsets:
        lt = lift.astimezone(timezone(timedelta(hours=o)))
        key = f"UTC{o:+g}"
        local_times[key] = lt.strftime("%a %Y-%m-%d %H:%M")
        if lt.hour < 6 or lt.hour >= 18:
            warnings.append(f"Lift is {lt.strftime('%H:%M')} for {key} — outside newsroom hours; those outlets will run it later or not at all.")
    lift_utc = lift.astimezone(timezone.utc).replace(tzinfo=None)
    et_offset = us_utc_offset(lift_utc + timedelta(hours=-5), -5)  # EDT (UTC-4) 2nd Sun Mar → 1st Sun Nov
    et = lift.astimezone(timezone(timedelta(hours=et_offset)))
    if not (6 <= et.hour <= 10):
        warnings.append(f"Lift is {et.strftime('%H:%M')} ET — U.S. tech/business media prefer 6-10 a.m. ET.")
    return {
        "embargo_lift": lift.isoformat(),
        "lift_weekday": lift.strftime("%A"),
        "lift_in_audience_zones": local_times,
        "schedule": [
            {"step": "Offer exclusive to tier-1 target (optional)", "date": exclusive_offer.isoformat(), "weekday": exclusive_offer.strftime("%a")},
            {"step": "Send embargoed pitch to tier-2 list", "date": pitch.isoformat(), "weekday": pitch.strftime("%a")},
            {"step": "Single follow-up (reply in same thread)", "date": follow.isoformat(), "weekday": follow.strftime("%a")},
            {"step": "Embargo lifts; wire distribution + social + blog", "date": lift_date.isoformat(), "weekday": lift.strftime("%a")},
            {"step": "Post-lift: send 'it's live' note with link to those who covered", "date": dates.add_business_days(lift_date, 1, hol).isoformat(), "weekday": dates.add_business_days(lift_date, 1, hol).strftime("%a")},
        ],
        "business_days_pitch_to_lift": dates.business_days_between(pitch, lift_date, hol),
        "warnings": warnings,
        "summary": f"Pitch {pitch.isoformat()} ({pitch.strftime('%a')}), follow up {follow.isoformat()} ({follow.strftime('%a')}), lift {lift_date.isoformat()} ({lift.strftime('%a')}) {lift.strftime('%H:%M')} {lift.strftime('%z')}; {len(warnings)} warning(s).",
    }
