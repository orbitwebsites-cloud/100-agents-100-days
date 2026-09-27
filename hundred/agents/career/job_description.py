"""Job Description Writer — postings that widen the top of the funnel and pass a candidate's 30-second scan."""

from __future__ import annotations

import re

from ...core import Agent, ToolError
from ...lib import text
from ._common import MUST_CUES, NICE_CUES, YEARS_RE, DEGREE_RE, pct, require_list, require_number, require_text, scan_lexicon, split_requirements

AGENT = Agent(
    slug="job-description",
    name="Job Description Writer",
    category="career",
    tagline="Write job posts that convert: inclusive language, 5-7 real requirements, a posted salary band, and a readable structure.",
    description=(
        "Drafts and audits job descriptions the way a head of talent does: checks for gendered and "
        "exclusionary language (with the research-backed word lists and swaps), trims requirement laundry "
        "lists to the must-haves that actually predict performance, validates structure and readability "
        "against what candidates scan for, and computes a salary band with quartiles and a posting range "
        "for pay-transparency jurisdictions. Output is a posting ready for the ATS, LinkedIn or a careers page."
    ),
    triggers=[
        "write a job description for a …",
        "review this job posting for bias / inclusive language",
        "our job ad isn't getting applicants",
        "trim these requirements / is this too many requirements",
        "what salary range should we post",
        "rewrite this JD to attract more diverse candidates",
    ],
    examples=[
        "Write a job description for a Senior Backend Engineer, Series B fintech, remote US, $170-210k.",
        "Here's our Marketing Manager posting — it's had 4 applicants in two weeks. Fix it.",
        "Check this JD for gendered language and cut the requirements list down.",
    ],
    connectors=["Greenhouse", "Lever", "Workable", "LinkedIn", "Notion", "Google Docs"],
    playbook="""
    ## Standard
    You are a head of talent who has written postings that fill senior roles in weeks, not
    quarters. A great job description is a marketing document with a legal spine: it sells the
    problem, the team and the growth to the candidate you want, lists only the requirements
    that predict success, and posts the pay. The metric: qualified applicants per week, with
    an applicant pool that reflects the labour market for the role.

    ## Intake
    You need: title, level, team/manager, location/remote policy, the 3-5 outcomes the person
    must deliver in year one, and the salary band. Ask only for what's missing among: the
    year-one outcomes and the band — those two make or break the posting. Everything else you
    can draft with clearly labelled placeholders.

    ## Procedure
    1. **Audit first if a draft exists.** Call `job_description__check_inclusive_language`
       and `job_description__check_structure` on it. Report the masculine/feminine lean, the
       exclusionary terms, the requirement count, word count, salary presence and readability.
       Fix the flagged terms with the tool's swaps, not your own synonyms.
    2. **Rebuild the requirements.** Take every requirement (yours or theirs) and call
       `job_description__audit_requirements`. Keep must-haves to 5-7; move the rest to
       "nice to have" or delete. Replace degree requirements with "or equivalent experience"
       unless legally required. Replace "N+ years" with the capability the years are a proxy
       for ("has shipped X end-to-end at least twice"). Cut duplicates the tool flags.
    3. **Set the pay.** Call `job_description__build_salary_band` with the midpoint (or
       min/max) and spread. Post the range. If the user is in a pay-transparency jurisdiction
       (e.g. California, Colorado, New York, Washington, the EU Pay Transparency Directive from
       2026) posting a good-faith range is required; elsewhere it still roughly doubles apply
       rates on major job boards. Not legal advice — confirm the jurisdiction's rule.
    4. **Write the posting** in the structure below: hook (the problem and why it matters) →
       what you'll do (5-7 outcome bullets, "you will" voice) → what you bring (must-haves) →
       nice to have → what we offer (pay, benefits, growth) → process (stages, timeline) → EEO.
       300-700 words. Grade 8-10 readability. Second person throughout.
    5. **Re-run** `job_description__check_inclusive_language` and `job_description__check_structure`
       on the final and deliver only when structure score ≥ 80 and lean is neutral or the
       masculine count is ≤ 2 with no exclusionary hits.
    6. **Self-check:** no requirement appears twice; every "you will" bullet is an outcome, not
       a task; pay range and location are explicit; no internal jargon or unexplained acronyms.

    ## Frameworks
    - **Gendered wording (Gaucher, Friesen & Kay, 2011):** masculine-coded words (competitive,
      dominant, aggressive, ninja, rockstar, fearless) reduce women's sense of belonging and
      apply rates; feminine-coded words do not deter men. Aim neutral; when in doubt, swap for
      the concrete behaviour.
    - **Requirement inflation:** each must-have beyond ~7 shrinks the pool; long lists deter
      candidates who apply only when they meet every line, which skews the pool. Ask of each
      requirement: "would we reject an otherwise great candidate for lacking this?" If no,
      it's nice-to-have.
    - **Structure candidates scan (in order):** title → pay → location/remote → what you'll
      do → requirements. Put pay and location above the fold.
    - **Title rules:** searchable and standard ("Senior Backend Engineer", not "Backend
      Wizard"); level in the title; no internal codes.
    - **Band math:** spread = (max − min) / min; typical 30-50% for professional roles, 50-70%
      for senior/exec. Post the full band or the hiring range (min → midpoint) and be prepared
      to explain placement: new-to-level near min, fully performing at midpoint.
    - **Length:** 300-700 words. Under 300 reads as low-effort; over 700 loses mobile readers.

    ## Output format
    ```
    # <Title> · <Team> · <Location / Remote policy> · <$min–$max + equity/bonus if any>

    **Why this role exists** — <2-3 sentences: the problem, the stakes, the team>

    **What you'll do**
    - <outcome bullet: "Ship X so that Y" — 5-7 total>

    **What you bring (must-haves)**
    - <5-7 capabilities, evidence-based, no years/degrees unless required>

    **Nice to have**
    - <2-4>

    **What we offer** — pay range, bonus/equity, benefits, growth, working model
    **How we hire** — <stages, total time, who you'll meet>
    **Equal opportunity** — <EEO statement; accommodations contact>

    ---
    Audit: lean <neutral/masculine/feminine> · exclusionary 0 · requirements N must / M nice · NNN words · grade N · pay posted ✓
    ```

    ## Anti-patterns
    - "Rockstar/ninja/guru", "work hard play hard", "fast-paced" — signals culture over craft and skews the pool.
    - 15 must-haves. Nobody is that candidate; the ones who apply anyway are the over-confident.
    - Degree + years requirements as proxies for skill. Name the skill.
    - No salary. Candidates skip it; some jurisdictions fine it.
    - Company boilerplate first. Lead with the problem the hire solves.
    - "Native English speaker", "digital native", "recent graduate", "young and energetic" — exclusionary and, in many places, unlawful.
    """,
)

# Gaucher, Friesen & Kay (2011), "Evidence That Gendered Wording in Job Advertisements Exists and
# Sustains Gender Inequality", JPSP 101(1):109-128, Appendix A — the published stems ("*" = any
# ending), as reproduced in the open-source Gender Decoder. STRONG stems describe traits and drive
# the lean and the score; WEAK stems are on the list too but are usually functional in a job ad
# ("lead the roadmap", "analytics", "responsibilities"), so they are reported, not penalised.
GFK_MASCULINE_STRONG = {
    "adventurous": "curious about new problems", "aggress*": "proactive / direct", "ambitio*": "motivated to grow / high-impact",
    "assert*": "clear and confident in your reasoning", "athlet*": "remove unless the job is physical", "autonom*": "self-directed",
    "boast*": "remove", "compet*": "results-focused / strong (for pay: 'market-rate')", "confident": "sure of your reasoning",
    "courag*": "willing to take calculated risks", "decisive": "makes clear calls with the data available", "dominant": "leading",
    "domina*": "lead / grow share in", "greedy": "remove", "headstrong": "determined", "head-strong": "determined",
    "hierarch*": "structure / reporting lines", "hostil*": "remove", "impulsive": "remove", "intellect*": "curious / thoughtful",
    "masculine": "remove", "outspoken": "candid", "persist": "keep going / follow through", "reckless": "remove",
    "stubborn": "persistent", "superior": "excellent", "self-confiden*": "sure of your reasoning", "self-relian*": "self-directed",
    "self-sufficien*": "self-directed",
}
GFK_MASCULINE_WEAK = {
    "active": "", "analy*": "", "challeng*": "", "decide": "", "decision*": "", "determin*": "", "force*": "", "independen*": "",
    "individual*": "", "lead*": "", "logic": "", "objective": "", "opinion": "", "principle*": "",
}
GFK_FEMININE_STRONG = {
    "supportive": "", "affectionate": "", "cheer*": "", "communal": "", "compassion*": "", "considerate": "", "cooperat*": "", "emotiona*": "",
    "empath*": "", "feminine": "", "flatterable": "", "gentle": "", "honest": "", "interpersonal": "", "interdependen*": "",
    "interpersona*": "", "kinship": "", "loyal*": "", "modesty": "", "nag": "", "nurtur*": "", "pleasant*": "", "polite": "",
    "quiet*": "", "sensitiv*": "", "submissive": "", "sympath*": "", "tender*": "", "warm*": "", "whin*": "", "yield*": "",
}
GFK_FEMININE_WEAK = {"child*": "", "commit*": "", "connect*": "", "depend*": "", "kind": "", "respon*": "", "support*": "", "together*": "", "trust*": "", "understand*": ""}
# Not in GFK: tech-hiring slang and pace clichés that code masculine (Gender Decoder additions + common usage).
MASCULINE_SLANG = {
    "fearless": "willing to take calculated risks", "driven": "motivated", "battle-tested": "proven", "fight*": "advocate / work for",
    "ninja": "specialist", "rockstar": "expert", "guru": "expert", "superhero": "expert", "hacker": "engineer", "wizard": "specialist",
    "crush": "exceed", "crushing": "exceeding", "kill it": "excel", "warrior": "advocate", "hustle": "work with urgency",
    "hustler": "self-starter", "boss": "lead", "hard-charging": "energetic", "work hard play hard": "we care about sustainable pace",
    "fast-paced": "we ship every two weeks (say what fast means)", "high-pressure": "describe the actual demands",
}
MASCULINE = {**GFK_MASCULINE_STRONG, **MASCULINE_SLANG}
FEMININE = dict(GFK_FEMININE_STRONG)
WEAK_CODED = {**{k: "masculine (GFK, often functional)" for k in GFK_MASCULINE_WEAK}, **{k: "feminine (GFK, often functional)" for k in GFK_FEMININE_WEAK}}
FEMININE_NOTE = "no swap needed — GFK found feminine wording does not reduce men's interest; keep it if it's accurate"
CODED_SKIP = {
    "compet*": re.compile(r"competen"),  # competency / competent are not the trait "competitive"
    "kind": re.compile(r"kind of\b|kinds?\s+of"),
    "lead*": re.compile(r"lead(?:s)?\s+(?:generation|gen|time)"),
    "force*": re.compile(r"forces?\b"),
    "support*": re.compile(r"supportive"),  # the trait form is scored as strong feminine
}
EXCLUSIONARY = {
    "native english speaker": "'fluent/professional English' — national-origin discrimination risk",
    "native speaker*": "'fluent/professional proficiency' — national-origin discrimination risk",
    "digital native*": "'comfortable with modern tools' — age-coded",
    "recent grad*": "'early-career' — age-coded",
    "young": "remove — age-coded",
    "youthful": "remove — age-coded",
    "energetic": "'brings momentum to projects' — age-coded",
    "mature": "'experienced' — age-coded (product/market uses are skipped)",
    "culture fit": "'values alignment: <named behaviours>' — invites bias",
    "cultural fit": "'values alignment: <named behaviours>' — invites bias",
    "able-bodied": "remove; state the essential physical function if any — disability discrimination risk",
    "must be able to lift": "keep only if an essential function; add 'with or without reasonable accommodation'",
    "stand for long periods": "keep only if essential; add 'with or without reasonable accommodation'",
    "clean-cut": "remove — appearance-coded",
    "attractive": "remove — appearance-coded",
    "no visible tattoos": "remove unless a documented safety rule",
    "unemployed need not apply": "remove — unlawful in several jurisdictions",
    "must have a car": "'reliable transportation' unless driving is the job",
    "he will": "'you will' / 'they will'",
    "he/she": "'they' or 'you'",
    "his/her": "'their' or 'your'",
    "manpower": "workforce / staffing",
    "man-hours": "person-hours / hours",
    "chairman": "chair",
    "salesman": "salesperson",
    "guys": "team / everyone",
    "brotherhood": "community",
    "family": "team (if used as 'we're a family' — signals boundary issues; benefit uses like 'family leave' are skipped)",
    "high energy": "'brings momentum to projects' — age-coded",
    "high-energy": "'brings momentum to projects' — age-coded",
    "overqualified": "remove — age-coded screening",
    "new grad*": "'early-career' — age-coded",
    "physically fit": "state the essential physical function, 'with or without reasonable accommodation'",
    "english as a first language": "'fluent/professional English' — national-origin risk",
    "mother tongue": "'fluent/professional proficiency' — national-origin risk",
    "citizens only": "state the actual work-authorization requirement; citizenship limits need a legal basis",
    "no criminal record": "follow fair-chance hiring laws; assess individually after an offer where required",
    "work hard, play hard": "state the actual pace and hours",
    "ivy league": "state the capability, not the pedigree",
    "top-tier university": "state the capability, not the pedigree",
    "blind spot": "'gap' — ableist idiom",
    "crazy": "'ambitious' / 'unusual' — ableist",
    "insane": "'exceptional' — ableist",
    "tone deaf": "'unaware' — ableist idiom",
    "sanity check": "'quick check' — ableist",
    "dummy": "'placeholder' — ableist",
    "whitelist": "allowlist",
    "blacklist": "blocklist",
    "master/slave": "primary/replica",
}
EXCL_SKIP = {
    "family": re.compile(r"family\s+(?:leave|medical|planning|members?|friendly|coverage|health|plan|care|building|business|office|dollar)"),
    "mature": re.compile(r"mature\s+(?:product|market|codebase|platform|company|business|technology|process|processes|stack|industry|org|organi[sz]ation)"),
    "young": re.compile(r"young\s+(?:company|startup|product|team of products|brand)"),
}
JARGON = {
    "synergy": "say what the collaboration produces", "leverage": "use", "utilize": "use", "best-in-class": "cut", "world-class": "cut",
    "cutting-edge": "name the technology", "disruptive": "cut", "game-changing": "cut", "wear many hats": "list the actual scope",
    "hit the ground running": "state the ramp expectation", "self-starter": "state the ownership expected", "go-getter": "cut",
    "thought leader": "cut", "move the needle": "state the metric", "low-hanging fruit": "cut", "circle back": "follow up",
    "bandwidth": "capacity", "unicorn": "cut", "10x": "cut",
}


@AGENT.tool
def check_inclusive_language(job_description: str) -> dict:
    """Scan a job description for gender-coded, exclusionary (age/ability/origin/appearance) and jargon terms, with swaps for each.

    Uses the Gaucher-Friesen-Kay masculine/feminine word lists plus an exclusionary-terms list.
    Reports lean (masculine/feminine/neutral), each hit with a replacement, and a 0-100 score.

    Args:
        job_description: The full posting text.
    """
    require_text(job_description, "job_description", max_chars=60_000)
    masc = scan_lexicon(job_description, MASCULINE, CODED_SKIP)
    fem = scan_lexicon(job_description, FEMININE, CODED_SKIP)
    weak = scan_lexicon(job_description, WEAK_CODED, CODED_SKIP)
    excl = scan_lexicon(job_description, EXCLUSIONARY, EXCL_SKIP)
    jargon = scan_lexicon(job_description, JARGON)
    for h in masc:
        h["source"] = "industry slang (not in GFK)" if h["term"] in MASCULINE_SLANG else "GFK 2011"
    for h in fem:
        h["source"], h["suggestion"] = "GFK 2011", FEMININE_NOTE
    m_n, f_n = sum(h["count"] for h in masc), sum(h["count"] for h in fem)

    def _lean(m: int, f: int) -> str:
        if m > f * 1.5 and m >= 2:
            return "masculine"
        if f > m * 1.5 and f >= 2:
            return "feminine"
        return "neutral"

    lean = _lean(m_n, f_n)
    wm = sum(h["count"] for h in weak if h["suggestion"].startswith("masculine"))
    wf = sum(h["count"] for h in weak if h["suggestion"].startswith("feminine"))
    gfk_m = sum(h["count"] for h in masc if h["source"] == "GFK 2011") + wm
    full_lean = _lean(gfk_m, f_n + wf)
    pronouns = len(re.findall(r"\b(he|his|him|she|her|hers)\b", job_description, re.I))
    you = len(re.findall(r"\byou(?:'ll|r|)\b", job_description, re.I))
    cand = len(re.findall(r"\b(the (?:ideal |successful |right )?candidate|the applicant|the successful applicant)\b", job_description, re.I))
    score = 100 - 6 * m_n - 12 * sum(h["count"] for h in excl) - 3 * sum(h["count"] for h in jargon) - 4 * pronouns
    score = max(0, min(100, score))
    fixes = [f"'{'/'.join(h['matched'])}' → {h['suggestion']}" for h in excl] + [f"'{'/'.join(h['matched'])}' → {h['suggestion']}" for h in masc[:8]] + [f"'{h['term']}' → {h['suggestion']}" for h in jargon[:5]]
    if cand > you:
        fixes.append("write in second person ('you will') instead of 'the candidate' — reads warmer and tests better")
    if pronouns:
        fixes.append("replace he/she pronouns with 'you' or 'they'")
    return {
        "score": score,
        "lean": lean,
        "masculine_coded": masc,
        "feminine_coded": fem,
        "masculine_count": m_n,
        "feminine_count": f_n,
        "weak_coded": weak,
        "gfk_full_list_lean": {"lean": full_lean, "masculine": gfk_m, "feminine": f_n + wf, "note": "all GFK stems incl. functional ones (lead*, analy*, respon*) — how the Gender Decoder counts; informational"},
        "exclusionary": excl,
        "jargon": jargon,
        "gendered_pronouns": pronouns,
        "voice": {"you": you, "the_candidate": cand},
        "fixes": fixes,
        "verdict": f"Lean {lean} ({m_n} masculine / {f_n} feminine), {len(excl)} exclusionary term(s), {len(jargon)} jargon. "
        + ("Clean." if not excl and lean != "masculine" else "Fix exclusionary terms first, then masculine-coded words."),
    }


GENERIC_REQ_WORDS = frozenset("experience experienced strong excellent skills skill ability knowledge working proficiency proficient familiarity familiar years year plus required must have demonstrated background understanding".split())
SALARY_RE = re.compile(r"(?:[$£€]\s?\d{2,3}(?:,\d{3})?(?:k|,000)?\s*(?:-|–|—|to)\s*[$£€]?\s?\d{2,3}(?:,\d{3})?(?:k|,000)?)|(?:\d{2,3}k\s*(?:-|–|to)\s*\d{2,3}k)", re.I)
SECTION_CUES = {
    "about_role": r"(about (?:the|this) role|why this role|the opportunity|the role|overview|role summary)",
    "responsibilities": r"(what you.ll do|what you will do|responsibilities|you will|in this role|day[- ]to[- ]day|what you.ll be doing)",
    "requirements": r"(what you bring|requirements|qualifications|what we.re looking for|about you|you have|must[- ]have|skills)",
    "nice_to_have": r"(nice[- ]to[- ]have|bonus points|preferred|it.s a plus|ideally)",
    "benefits": r"(what we offer|benefits|perks|compensation|why join|what.s in it for you)",
    "process": r"(how we hire|hiring process|interview process|our process|what to expect|next steps)",
    "eeo": r"(equal opportunity|equal employment|we are an equal|eeo|without regard to|reasonable accommodation)",
}


@AGENT.tool
def check_structure(job_description: str) -> dict:
    """Audit a job description's structure: sections, word count vs 300-700, requirement counts, salary/location presence, readability and voice.

    Args:
        job_description: The full posting text.
    """
    require_text(job_description, "job_description", max_chars=60_000)
    jd = job_description
    low = jd.lower()
    n_words = len(text.words(jd))
    read = text.readability(jd)
    sections = {k: bool(re.search(p, low)) for k, p in SECTION_CUES.items()}
    reqs = split_requirements(jd)
    must = [r for r in reqs if r["tier"] == "must"]
    nice = [r for r in reqs if r["tier"] == "nice"]
    duties = [r for r in reqs if r["tier"] == "duty"]
    salary = SALARY_RE.search(jd)
    location = bool(re.search(r"\b(remote|hybrid|on-?site|in-?office|located in|based in|location:)\b", low))
    bullets = sum(1 for ln in jd.splitlines() if re.match(r"^\s*(?:[-*•·]|\d+[.)])\s+", ln))
    you = len(re.findall(r"\byou(?:'ll|r|)\b", jd, re.I))
    long_sents = [s[:120] for s in text.sentences(jd) if len(text.words(s)) > 30]
    first_200 = " ".join(text.words(jd)[:200]).lower()
    pay_above_fold = bool(SALARY_RE.search(first_200)) or (salary is not None and salary.start() < len(jd) * 0.25)
    issues, fixes = [], []
    score = 100
    if n_words < 300:
        issues.append(f"{n_words} words — under 300 reads as low effort")
        score -= 10
    elif n_words > 700:
        issues.append(f"{n_words} words — over 700 loses mobile readers")
        fixes.append("cut company boilerplate and duplicate requirements")
        score -= 10
    if not salary:
        issues.append("no salary range found")
        fixes.append("post a range (required in several US states and the EU from 2026; roughly doubles apply rates elsewhere)")
        score -= 20
    elif not pay_above_fold:
        issues.append("salary appears late — move it under the title")
        score -= 5
    if not location:
        issues.append("no location / remote policy statement")
        score -= 10
    if not sections["responsibilities"]:
        issues.append("no 'what you'll do' section")
        score -= 10
    if not sections["requirements"]:
        issues.append("no requirements section")
        score -= 10
    if len(must) > 7:
        issues.append(f"{len(must)} must-have requirements (max 7)")
        fixes.append("run audit_requirements and demote to nice-to-have")
        score -= 10
    if len(must) == 0 and reqs:
        issues.append("requirements aren't tagged must/nice — label the sections")
        score -= 5
    if not sections["benefits"]:
        issues.append("no 'what we offer' section")
        score -= 5
    if not sections["process"]:
        issues.append("no hiring-process section (stages, timeline)")
        score -= 5
    if not sections["eeo"]:
        issues.append("no equal-opportunity / accommodations statement")
        score -= 5
    if read["fk_grade"] is not None and read["fk_grade"] > 11:
        issues.append(f"reading grade {read['fk_grade']} (aim 8-10)")
        score -= 5
    if long_sents:
        issues.append(f"{len(long_sents)} sentence(s) over 30 words")
        score -= 3
    if you < 3:
        issues.append("barely addresses the reader as 'you'")
        fixes.append("write in second person: 'You will…', 'You bring…'")
        score -= 5
    if bullets < 6:
        issues.append(f"only {bullets} bullet lines — scanners need bullets for duties and requirements")
        score -= 5
    score = max(0, score)
    return {
        "score": score,
        "words": n_words,
        "readability": {"fk_grade": read["fk_grade"], "flesch_reading_ease": read["flesch_reading_ease"]},
        "sections": sections,
        "requirements": {"must": len(must), "nice": len(nice), "duties": len(duties), "years_mentions": sum(1 for r in reqs if r["years"]), "degree_mentions": sum(1 for r in reqs if r["degree"])},
        "salary_range": salary.group(0) if salary else None,
        "salary_above_fold": pay_above_fold,
        "location_stated": location,
        "bullets": bullets,
        "you_count": you,
        "long_sentences": long_sents[:5],
        "issues": issues,
        "fixes": fixes,
        "verdict": ("Structure is solid." if score >= 80 else f"Structure score {score}/100 — {len(issues)} issue(s).") + f" {n_words} words, {len(must)} must-haves, pay {'posted' if salary else 'missing'}.",
    }


@AGENT.tool
def audit_requirements(requirements: list[str], role_level: str = "") -> dict:
    """Classify requirements as must-have vs nice-to-have, flag years/degree proxies, duplicates and inflation, and recommend the cut list.

    Args:
        requirements: Requirement lines as written in the posting (one string each).
        role_level: Optional level hint (e.g. "junior", "senior") to flag mismatched years demands.
    """
    require_list(requirements, "requirements", max_items=100)
    rows = []
    seen: list[tuple[int, set[str]]] = []
    lvl = role_level.strip().lower()
    for i, raw in enumerate(requirements, 1):
        r = str(raw).strip()
        if not r:
            raise ToolError(f"requirement #{i} is empty.")
        tier = "nice" if NICE_CUES.search(r) else "must" if MUST_CUES.search(r) else "must"
        ym = YEARS_RE.search(r)
        years = int(ym.group(1)) if ym else None
        degree = bool(DEGREE_RE.search(r))
        key = {w.lower() for w in text.words(r) if w.lower() not in text.STOPWORDS and w.lower() not in GENERIC_REQ_WORDS and len(w) > 2}
        dup = next((n for n, k in seen if key and k and (len(key & k) / len(key | k) >= 0.6 or key <= k or k <= key)), None)
        seen.append((i, key))
        flags, rewrite = [], None
        if years is not None:
            flags.append(f"{years}+ years is a proxy — name the capability")
            rewrite = re.sub(YEARS_RE, "demonstrated", r)
            rewrite = re.sub(r"\bdemonstrated\s+(of|in)\b", "demonstrated", rewrite)
            if lvl and re.search(r"\b(junior|entry|associate|graduate)\b", lvl) and years >= 3:
                flags.append(f"{years} years for a {lvl} role contradicts the level")
        if degree and not re.search(r"equivalent", r, re.I):
            flags.append("degree requirement — add 'or equivalent experience' unless legally required")
        if re.search(r"\b(excellent|strong|outstanding|exceptional|superior)\s+(communication|interpersonal|organi[sz]ational|problem[- ]solving)\b", r, re.I):
            flags.append("generic soft-skill line — cut or make it observable ('has presented to executives')")
        if re.search(r"\b(passion(ate)?|rockstar|ninja|guru|self-starter|team player|culture fit)\b", r, re.I):
            flags.append("buzzword — cut")
        excl_hits = scan_lexicon(r, EXCLUSIONARY, EXCL_SKIP)
        if excl_hits:
            flags.append("exclusionary: " + ", ".join(f"'{'/'.join(h['matched'])}' ({h['suggestion']})" for h in excl_hits))
        trait_hits = [h for h in scan_lexicon(r, MASCULINE, CODED_SKIP) if h["term"] in GFK_MASCULINE_STRONG]
        if trait_hits:
            flags.append("personality trait, not a capability (masculine-coded, GFK): " + ", ".join("/".join(h["matched"]) for h in trait_hits) + " — name the behaviour or cut")
        if dup:
            flags.append(f"duplicates #{dup}")
        if len(text.words(r)) > 25:
            flags.append("over 25 words — split or trim")
        rows.append({"n": i, "text": r[:300], "tier": tier, "years": years, "degree": degree, "flags": flags, "rewrite": rewrite})
    must = [r for r in rows if r["tier"] == "must"]
    nice = [r for r in rows if r["tier"] == "nice"]
    over = max(0, len(must) - 7)
    # Recommend demotions: flagged/generic must-haves first, then the last ones listed.
    demote = sorted(must, key=lambda r: (-len(r["flags"]), -r["n"]))[:over] if over else []
    cut_ids = [r["n"] for r in rows if any("duplicates" in f or "buzzword" in f or f.startswith("personality trait") for f in r["flags"])]
    rewrite_ids = [r["n"] for r in rows if r["n"] not in cut_ids and any(f.startswith("exclusionary") for f in r["flags"])]
    return {
        "count": len(rows),
        "must_have": len(must),
        "nice_to_have": len(nice),
        "over_limit_by": over,
        "requirements": rows,
        "recommend_demote": [r["n"] for r in demote],
        "recommend_cut": cut_ids,
        "recommend_rewrite": rewrite_ids,
        "years_proxies": sum(1 for r in rows if r["years"] is not None),
        "degree_requirements": sum(1 for r in rows if r["degree"]),
        "verdict": f"{len(must)} must-haves ({'ok' if not over else f'{over} over the limit of 7'}), {len(nice)} nice-to-haves; "
        f"{sum(1 for r in rows if r['years'] is not None)} years-proxies, {sum(1 for r in rows if r['degree'])} degree lines, {len(cut_ids)} to cut, {len(rewrite_ids)} to rewrite (exclusionary wording).",
    }


@AGENT.tool
def build_salary_band(midpoint: float = 0, band_min: float = 0, band_max: float = 0, spread_pct: float = 40, candidate_salary: float = 0, currency: str = "$") -> dict:
    """Compute a salary band (min/mid/max, quartiles, hiring range) from a midpoint and spread or from min/max, plus compa-ratio for a candidate ask.

    spread = (max − min) / min. Give either midpoint + spread_pct, or band_min + band_max.

    Args:
        midpoint: Target midpoint (market rate for a fully performing employee). Use with spread_pct.
        band_min: Band minimum, if you already have a band (use with band_max).
        band_max: Band maximum, if you already have a band (use with band_min).
        spread_pct: Band spread as (max−min)/min in percent. Typical: 30-50 professional, 50-70 senior/executive.
        candidate_salary: Optional candidate's ask or current salary, to compute compa-ratio and placement.
        currency: Currency symbol for the formatted strings.
    """
    mid = require_number(midpoint, "midpoint", 0)
    lo = require_number(band_min, "band_min", 0)
    hi = require_number(band_max, "band_max", 0)
    spread = require_number(spread_pct, "spread_pct", 5, 200) / 100
    if lo and hi:
        if hi <= lo:
            raise ToolError("band_max must be greater than band_min.")
        mid = (lo + hi) / 2
        spread = (hi - lo) / lo
    elif mid:
        lo = mid / (1 + spread / 2)
        hi = lo * (1 + spread)
    else:
        raise ToolError("Give either midpoint (+ spread_pct) or band_min and band_max.")
    q1 = lo + (hi - lo) * 0.25
    q3 = lo + (hi - lo) * 0.75
    rnd = lambda x: round(x / 100) * 100  # noqa: E731
    fmt = lambda x: f"{currency}{rnd(x):,.0f}"  # noqa: E731
    placement = None
    if candidate_salary:
        cs = require_number(candidate_salary, "candidate_salary", 1)
        cr = cs / mid
        pos = (cs - lo) / (hi - lo)
        zone = "below band" if cs < lo else "Q1 — new to level" if pos < 0.25 else "Q2 — developing" if pos < 0.5 else "Q3 — fully performing" if pos < 0.75 else "Q4 — expert / at ceiling" if cs <= hi else "above band"
        placement = {"salary": cs, "compa_ratio": round(cr, 3), "range_penetration_pct": round(100 * pos, 1), "zone": zone, "note": ("compa-ratio 0.80-1.20 is the normal band; outside it needs a written reason" if 0.8 <= cr <= 1.2 else "outside the 0.80-1.20 compa-ratio norm — needs a written exception or a different level")}
    return {
        "band": {"min": rnd(lo), "q1": rnd(q1), "midpoint": rnd(mid), "q3": rnd(q3), "max": rnd(hi)},
        "spread_pct": round(spread * 100, 1),
        "posting_range_full": f"{fmt(lo)} – {fmt(hi)}",
        "posting_range_hiring": f"{fmt(lo)} – {fmt(mid)}",
        "placement_guide": {"min_to_q1": "new to the level / meets some requirements", "q1_to_mid": "meets requirements, building", "mid_to_q3": "fully performing", "q3_to_max": "consistently exceeds; ready for next level"},
        "candidate": placement,
        "verdict": f"Band {fmt(lo)} – {fmt(hi)} (mid {fmt(mid)}, spread {round(spread * 100)}%). Post the full band or the hiring range {fmt(lo)} – {fmt(mid)}."
        + (f" Candidate at compa-ratio {placement['compa_ratio']} → {placement['zone']}." if placement else ""),
    }
