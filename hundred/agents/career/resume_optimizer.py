"""Resume Optimizer — tailors a resume to a specific job description the way an executive recruiter would.

Honest about ATS: applicant tracking systems parse and keyword-match; they do not
"auto-reject 75% of resumes". The win is recruiter search hits + a human scan that
lands on quantified, verb-led bullets.
"""

from __future__ import annotations

import re
import statistics
from datetime import date

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import (
    extract_skill_terms,
    pct,
    require_list,
    require_text,
    scan_lexicon,
    split_requirements,
)

AGENT = Agent(
    slug="resume-optimizer",
    name="Resume Optimizer",
    category="career",
    tagline="Tailor your resume to one job: real keyword-match against the JD, bullet rewrites that quantify, and honest ATS checks.",
    description=(
        "Takes your resume and a target job description and does what a top executive recruiter does before "
        "submitting a candidate: measures true keyword coverage against the JD's must-have vs nice-to-have "
        "requirements, scores every bullet for verb strength, quantification and length, checks the file for "
        "real ATS parsing risks (columns, tables, missing sections, unparseable dates), computes tenure and "
        "gaps exactly, then rewrites the weak bullets in the Google XYZ format. No ATS myths — just what "
        "parsers and recruiter keyword searches actually reward."
    ),
    triggers=[
        "tailor my resume to this job description",
        "is my resume ATS friendly / will it pass the ATS",
        "rewrite my resume bullets to be stronger",
        "which keywords am I missing for this role",
        "review my resume / CV for this position",
        "optimize my LinkedIn experience section",
    ],
    examples=[
        "Here's my resume and the JD for a Senior Product Manager role at Stripe — tailor it.",
        "My resume isn't getting callbacks. Here it is with a job posting I applied to. What's wrong?",
        "Rewrite these six bullets from my last job so they show impact, not duties.",
    ],
    connectors=["Google Docs", "Notion", "LinkedIn"],
    playbook="""
    ## Standard
    You are an executive recruiter who has read 50,000 resumes and placed hundreds of candidates.
    Excellence here means one thing: the resume gets the candidate a recruiter screen for THIS
    job. That happens when (a) a recruiter's keyword search in the ATS surfaces it, and (b) the
    6-10 second first human scan lands on the title, company, and two or three quantified results.
    Everything you do serves those two moments. The metric that matters: must-have keyword
    coverage ≥ 80% with every claim true, and ≥ 50% of bullets quantified.

    ## Intake
    You need: the resume text and the target job description. If there is no JD, ask for one
    (or the target title + 3 postings) — you cannot tailor to nothing. Do not ask anything
    else; assume the user wants a tailored version of the same resume, state the assumption,
    and proceed. Never invent experience: every keyword you add must map to something the
    candidate actually did. If a must-have keyword has no basis, say so and suggest the
    closest honest phrasing or a skills-section entry only if it is genuinely true.

    ## Procedure
    1. **Measure the gap first.** Call `resume_optimizer__match_keywords` with the resume and
       JD (pass the job title if you know it). Read `must_have_coverage_pct` and `missing`:
       missing must-haves are your priority list; nice-to-haves are second. Note the
       `phrasing` hints — ATS search is literal, so use the JD's exact term (and the acronym
       AND the long form once each, e.g. "Search Engine Optimization (SEO)").
    2. **Check parseability.** Call `resume_optimizer__check_ats_format` with the resume.
       Fix every `parse_risk` before touching wording: two-column layouts, tables, text in
       headers/footers, missing standard section headings, and dates a parser can't read
       ("Summer '19") are the real ATS failures. Page estimate: 1 page under ~10 years of
       experience, 2 pages otherwise; never 3.
    3. **Verify the timeline.** Call `resume_optimizer__compute_tenure` with each role's
       start/end. Use its exact tenure strings in the resume. Gaps > 6 months: never hide them;
       decide with the user whether to add a one-line honest entry (career break, caregiving,
       study) — modern recruiters accept these, and unexplained gaps read worse than explained ones.
    4. **Score the bullets.** Call `resume_optimizer__score_bullets` with every experience
       bullet. Rewrite any bullet scoring < 70 using the Google XYZ formula:
       "Accomplished [X] as measured by [Y], by doing [Z]". Lead with a strong past-tense
       verb, one metric (%, $, time, volume, rank), then the method. 12-24 words. No "I",
       no "responsible for", no adjectives about yourself.
    5. **Tailor the top third.** Headline = the target title (or nearest honest equivalent).
       Summary = 2-3 lines, dense with must-have terms, no fluff. Skills section = grouped,
       JD terms first, exact spellings. Reorder bullets within each role so the ones that
       match the JD come first — recruiters read the first two bullets of each role.
    6. **Re-run `resume_optimizer__match_keywords` on your draft** to prove the coverage
       moved. Report before/after numbers. If must-have coverage is still < 60%, tell the
       user plainly the role may be a stretch and what would close the gap.
    7. **Self-check:** every number you wrote is from the candidate; every keyword added is
       true; no bullet starts with a pronoun; dates are consistent with the tenure tool.

    ## Frameworks
    - **What ATS actually does:** parses the file into fields (contact, titles, companies,
      dates, skills), stores it, and lets recruiters search/filter by keywords, titles,
      years, location. Some vendors show a match % against the JD; none silently reject on a
      score. Knockout questions (work authorization, must-have certs) do reject — answer them
      truthfully. Fonts, colors, and "keyword stuffing in white text" do nothing; the last one
      gets you flagged by humans.
    - **XYZ formula (Google):** "Increased [X] by [Y] by doing [Z]." Every bullet is a result,
      not a duty.
    - **Bullet score bands:** ≥ 80 strong; 60-79 rewrite for a metric; < 60 rewrite entirely.
    - **Quantification menu when the candidate "has no numbers":** team size, budget, users
      served, tickets/week, time saved, error rate, frequency, scope (countries, products),
      rank ("first", "only"), before/after comparisons. Estimates are fine if labelled ("~").
    - **Coverage thresholds:** must-have ≥ 80% = submit; 60-79% = tailor harder or add a
      skills line; < 60% = honest stretch.

    ## Output format
    ```
    ## Fit snapshot
    Must-have coverage: before N% → after M% · Nice-to-have: N% → M% · Pages: ~X · Parse risks: N fixed
    Missing (cannot honestly claim): term, term

    ## Fixes applied
    - <parse/format fix> · <ordering change> · <headline/summary change>

    ## Tailored resume
    <full resume text, ready to paste, standard headings: Summary · Skills · Experience · Education · (Certifications)>

    ## Bullet rewrites (before → after, score)
    - "<old>" (42) → "<new>" (88)

    ## Timeline check
    Total experience: X yrs Y mo · Median tenure: … · Gaps: none / <period> (suggest: …)

    ## Before you send
    1. Confirm every number above is accurate.
    2. Save as .docx or text-based PDF, filename "Firstname-Lastname-Resume.pdf".
    3. Answer knockout questions truthfully; your resume and application must match.
    ```

    ## Anti-patterns
    - Repeating ATS myths ("75% are rejected by robots", "PDF breaks the ATS", "use Arial or
      you fail"). State what parsers and keyword search do; nothing more.
    - Keyword stuffing: a skills section listing 40 terms, or bullets that read like a JD.
      Recruiters spot it instantly. Each keyword lives where it was actually used.
    - Duty bullets: "Responsible for managing the sales pipeline." Rewrite to the result.
    - Objective statements, photos, "References available on request", full addresses.
    - Inventing metrics or seniority to hit coverage. A stretch flagged honestly beats a
      fabrication caught in a reference check.
    - Rewriting every bullet identically ("Spearheaded… Spearheaded… Spearheaded"). Vary verbs.
    """,
)

STRONG_VERBS = frozenset(
    """accelerated achieved acquired architected automated boosted built championed closed coached consolidated
    created cut decreased delivered designed developed directed doubled drove earned eliminated engineered
    established exceeded expanded generated grew hired implemented improved increased influenced initiated
    launched led managed mentored migrated modernized negotiated optimized orchestrated outperformed owned
    partnered pioneered produced published raised rebuilt reduced redesigned refactored repaired replaced
    rescued restructured saved scaled secured shipped simplified slashed sold spearheaded standardized
    streamlined strengthened supervised surpassed transformed tripled turned unified won wrote""".split()
)
WEAK_STARTS = {
    "responsible for": "start with the result, not the responsibility",
    "duties included": "delete — list the outcome instead",
    "helped": "say what YOU did: 'built', 'led', 'cut'",
    "assisted": "specify your own contribution with a strong verb",
    "worked on": "name the deliverable and its impact",
    "worked with": "lead with what you delivered, then who with",
    "participated in": "what did you own inside it?",
    "involved in": "what did you own inside it?",
    "tasked with": "delete — give the outcome",
    "was part of": "what did you own inside it?",
    "supported": "specify: 'delivered X for Y'",
    "handled": "replace with a precise verb: 'resolved', 'processed'",
    "utilized": "replace with 'used' or restructure around the result",
    "various": "name them",
    "successfully": "delete — the metric proves it",
}
BUZZWORDS = {
    "team player": "cut — show it with a collaboration result",
    "hard-working": "cut — show it with output numbers",
    "hard working": "cut — show it with output numbers",
    "detail-oriented": "cut — show it: 'zero audit findings'",
    "results-driven": "cut — show the results",
    "results-oriented": "cut — show the results",
    "self-starter": "cut — describe what you started",
    "go-getter": "cut",
    "synergy": "cut",
    "think outside the box": "cut",
    "passionate": "cut — passion is shown by what you built",
    "dynamic": "cut",
    "proven track record": "cut — the bullets are the track record",
    "excellent communication skills": "cut — show it: 'presented to 40 execs'",
    "motivated": "cut",
    "seasoned": "cut",
    "guru": "cut",
    "ninja": "cut",
    "rockstar": "cut",
}
PRONOUN_RE = re.compile(r"\b(I|me|my|mine|we|our|us)\b")
QUANT_RE = re.compile(r"(?:[$€£¥]\s?\d|\d+(?:\.\d+)?\s?(?:%|percent|x\b|k\b|m\b|mm\b|bn\b|million|billion|thousand|hours?|days?|weeks?|months?|users?|customers?|clients?|people|engineers|reps|accounts|countries|markets|stores|tickets|leads|deals)|\b\d{2,}\b|\b(?:doubled|tripled|halved|first|only|#1|top \d)\b)", re.I)
METHOD_RE = re.compile(r"\b(by|through|via|using|with|after|leading|building|launching|introducing|migrating|automating)\b", re.I)


@AGENT.tool
def match_keywords(resume: str, job_description: str, job_title: str = "") -> dict:
    """Measure real keyword coverage of a resume against a job description, split by must-have vs nice-to-have.

    Extracts skills/tools/terms from the JD, tags each as must-have or nice-to-have from the
    JD's own structure, and checks which appear in the resume (alias-aware: "k8s" = "Kubernetes").
    Call before tailoring and again after to prove coverage moved. Also checks whether the
    target title appears.

    Args:
        resume: Full resume text.
        job_description: Full job description text.
        job_title: The posting's title, e.g. "Senior Product Manager" (optional; used for the title check).
    """
    require_text(resume, "resume", max_chars=60_000)
    require_text(job_description, "job_description", max_chars=60_000)
    jd_terms = extract_skill_terms(job_description)
    if not jd_terms:
        raise ToolError("No skill/keyword terms found in the job description — paste the full posting, including requirements.")
    res_terms = extract_skill_terms(resume)
    reqs = split_requirements(job_description)
    must_terms = {t for r in reqs if r["tier"] == "must" for t in r["skills"]}
    nice_terms = {t for r in reqs if r["tier"] == "nice" for t in r["skills"]} - must_terms
    # Terms mentioned 2+ times in the JD but not inside a tagged requirement are treated as must.
    for t, n in jd_terms.items():
        if t not in must_terms and t not in nice_terms and n >= 2:
            must_terms.add(t)
    matched, missing = [], []
    for term, n in jd_terms.most_common():
        tier = "must" if term in must_terms else "nice" if term in nice_terms else "context"
        row = {"term": term, "tier": tier, "jd_mentions": n, "resume_mentions": res_terms.get(term, 0)}
        (matched if res_terms.get(term) else missing).append(row)
    tier_order = {"must": 0, "nice": 1, "context": 2}
    missing.sort(key=lambda r: (tier_order[r["tier"]], -r["jd_mentions"], r["term"]))

    def cov(tier: str) -> tuple[int, int]:
        tot = [r for r in matched + missing if r["tier"] == tier]
        return sum(1 for r in tot if r["resume_mentions"]), len(tot)

    m_hit, m_tot = cov("must")
    n_hit, n_tot = cov("nice")
    all_hit, all_tot = len(matched), len(matched) + len(missing)
    must_cov = pct(m_hit, m_tot)
    title_found = bool(job_title.strip()) and job_title.strip().lower() in resume.lower()
    phrasing = [
        {"term": r["term"], "hint": "Use the JD's exact spelling; if it is an acronym, write the long form once too (e.g. 'Search Engine Optimization (SEO)')."}
        for r in missing[:8]
    ]
    if must_cov >= 80:
        verdict = f"Must-have coverage {must_cov}% — submit-ready on keywords; polish bullets and ordering."
    elif must_cov >= 60:
        verdict = f"Must-have coverage {must_cov}% — tailor: add the {m_tot - m_hit} missing must-haves where they were genuinely used."
    else:
        verdict = f"Must-have coverage {must_cov}% — this reads as a stretch; close the gap honestly or expect a low recruiter-search hit rate."
    return {
        "must_have_coverage_pct": must_cov,
        "nice_to_have_coverage_pct": pct(n_hit, n_tot),
        "overall_coverage_pct": pct(all_hit, all_tot),
        "counts": {"must": [m_hit, m_tot], "nice": [n_hit, n_tot], "all": [all_hit, all_tot]},
        "title_in_resume": title_found if job_title.strip() else None,
        "matched": matched,
        "missing": missing,
        "phrasing": phrasing,
        "requirements_parsed": len(reqs),
        "ats_truth": "ATS parse fields and let recruiters keyword-search; they do not auto-reject on a score. Exact spelling of the JD's terms is what makes a search hit.",
        "verdict": verdict,
    }


def _score_bullet(b: str) -> dict:
    words = text.words(b)
    n = len(words)
    low = b.lower().strip()
    first = (words[0].lower() if words else "")
    issues, fixes = [], []
    score = 0
    # Verb strength (25)
    weak_hit = next((w for w in WEAK_STARTS if low.startswith(w)), None)
    if weak_hit:
        issues.append(f"weak opener '{weak_hit}'")
        fixes.append(WEAK_STARTS[weak_hit])
    elif first in STRONG_VERBS:
        score += 25
    elif first.endswith("ed") and first not in ("used", "needed", "tasked"):
        score += 18
        fixes.append(f"'{first}' is fine; a sharper verb (led, cut, built, launched) scores higher")
    elif first.endswith("ing"):
        issues.append("starts with a gerund — use past tense ('Managed', not 'Managing')")
    else:
        issues.append("does not start with an action verb")
        fixes.append("open with a past-tense result verb")
    # Quantification (35)
    quant = bool(QUANT_RE.search(b))
    if quant:
        score += 35
    else:
        issues.append("no metric")
        fixes.append("add one number: %, $, time saved, volume, team size, rank — estimates marked '~' are fine")
    # Length (15)
    if 12 <= n <= 24:
        score += 15
    elif 8 <= n < 12 or 24 < n <= 30:
        score += 8
        fixes.append("aim for 12-24 words")
    else:
        issues.append(f"{n} words ({'too short' if n < 8 else 'too long — split it'})")
    # Buzzwords / weak filler (15)
    buzz = scan_lexicon(b, BUZZWORDS)
    if buzz:
        issues.append("buzzwords: " + ", ".join(h["term"] for h in buzz))
        fixes.extend(f"'{h['term']}': {h['suggestion']}" for h in buzz[:2])
    else:
        score += 15
    # Pronouns (5)
    if PRONOUN_RE.search(b):
        issues.append("first-person pronoun")
        fixes.append("drop 'I/we/my' — resumes are written in implied first person")
    else:
        score += 5
    # Active voice (5)
    if text.passive_sentences(b):
        issues.append("passive voice")
    else:
        score += 5
    xyz = quant and (first in STRONG_VERBS) and bool(METHOD_RE.search(b))
    band = "strong" if score >= 80 else "rewrite for a metric" if score >= 60 else "rewrite"
    return {"bullet": b[:300], "score": score, "band": band, "words": n, "quantified": quant, "xyz_structure": xyz, "issues": issues, "fixes": fixes}


@AGENT.tool
def score_bullets(bullets: list[str]) -> dict:
    """Score resume bullets 0-100 for verb strength, quantification, length, buzzwords and voice; returns fixes per bullet.

    Rewrite anything under 70. Also reports the share of bullets that carry a metric
    (target: at least half) and repeated opening verbs.

    Args:
        bullets: The experience bullets, one string each (max 150).
    """
    require_list(bullets, "bullets", max_items=150)
    rows = []
    for b in bullets:
        if not isinstance(b, str) or not b.strip():
            raise ToolError("Every bullet must be a non-empty string.")
        if len(b) > 1000:
            raise ToolError("A bullet is over 1000 chars — that is a paragraph, not a bullet.")
        rows.append(_score_bullet(b.strip().lstrip("-•* ").strip()))
    scores = [r["score"] for r in rows]
    quantified = sum(1 for r in rows if r["quantified"])
    openers = [text.words(r["bullet"])[0].lower() for r in rows if text.words(r["bullet"])]
    repeats = {v: openers.count(v) for v in set(openers) if openers.count(v) >= 3}
    avg = round(statistics.mean(scores), 1)
    return {
        "bullets": rows,
        "average_score": avg,
        "quantified_pct": pct(quantified, len(rows)),
        "needs_rewrite": [i for i, r in enumerate(rows) if r["score"] < 70],
        "repeated_openers": repeats,
        "verdict": (
            f"Average {avg}/100; {pct(quantified, len(rows))}% quantified (target ≥ 50%). "
            f"{sum(1 for s in scores if s < 70)} of {len(rows)} bullets need a rewrite."
        ),
    }


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w-]+", re.I)
SECTIONS = {
    "experience": r"^\s*(?:work |professional |relevant )?(?:experience|employment(?: history)?|work history)\s*:?\s*$",
    "education": r"^\s*education(?: (?:&|and) training)?\s*:?\s*$",
    "skills": r"^\s*(?:core |technical |key )?(?:skills|competencies|technologies|tech stack)\s*(?:&|and)?\s*\w*\s*:?\s*$",
    "summary": r"^\s*(?:professional |executive )?(?:summary|profile|about(?: me)?)\s*:?\s*$",
}
GOOD_DATE_RE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}\b|\b(?:0?[1-9]|1[0-2])/\d{4}\b|\b(?:19|20)\d{2}\s*(?:-|–|—|to)\s*(?:(?:19|20)\d{2}|present|current|now)\b", re.I)
BAD_DATE_RE = re.compile(r"\b(?:summer|spring|fall|winter|autumn)\s*'?\d{2,4}\b|\b'\d{2}\s*(?:-|–)\s*'\d{2}\b", re.I)
ODD_SYMBOL_RE = re.compile(r"[★☆✔✓✗➤➔➢►▶◆◇■□●○♦♥♠♣☎✉➜⇒]|[\U0001F300-\U0001FAFF]")
COLUMN_GAP_RE = re.compile(r"\S {4,}\S")


@AGENT.tool
def check_ats_format(resume: str, years_experience: float = -1) -> dict:
    """Check a resume for real ATS parsing risks: sections, contact fields, date formats, columns/tables, symbols, length.

    Flags what parsers genuinely trip on (multi-column layout, tables, unusual date formats,
    missing standard headings) and estimates page count against the 1-page/2-page rule.

    Args:
        resume: Full resume text, pasted as plain text (copy from the document).
        years_experience: Candidate's total years of experience, for the page-count rule. Omit if unknown.
    """
    require_text(resume, "resume", max_chars=60_000)
    lines = [ln for ln in resume.splitlines()]
    n_words = len(text.words(resume))
    pages = round(n_words / 550, 1)
    found_sections = {k: any(re.match(p, ln, re.I) for ln in lines) for k, p in SECTIONS.items()}
    contact = {
        "email": bool(EMAIL_RE.search(resume)),
        "phone": bool(PHONE_RE.search(resume)),
        "linkedin": bool(LINKEDIN_RE.search(resume)),
    }
    good_dates = len(GOOD_DATE_RE.findall(resume))
    bad_dates = BAD_DATE_RE.findall(resume)
    tabs = resume.count("\t")
    pipes = resume.count("|")
    column_lines = sum(1 for ln in lines if COLUMN_GAP_RE.search(ln))
    odd = ODD_SYMBOL_RE.findall(resume)
    caps_lines = sum(1 for ln in lines if len(ln.strip()) > 12 and ln.strip().isupper())
    risks, fixes = [], []
    for k, ok in found_sections.items():
        if not ok and k != "summary":
            risks.append(f"no standard '{k.title()}' heading")
            fixes.append(f"add a plain heading named exactly '{k.title()}' — parsers map fields by these words")
    if not contact["email"]:
        risks.append("no email found")
    if not contact["phone"]:
        risks.append("no phone found")
    if bad_dates:
        risks.append(f"unparseable dates: {', '.join(bad_dates[:3])}")
        fixes.append("write dates as 'Mon YYYY – Mon YYYY' or 'MM/YYYY'")
    if good_dates == 0:
        risks.append("no parseable dates (Mon YYYY / MM/YYYY)")
    if tabs > 5 or column_lines > 5:
        risks.append(f"column/table layout signals ({tabs} tabs, {column_lines} wide-gap lines)")
        fixes.append("single column, no tables/text boxes — parsers read left-to-right across columns and scramble them")
    if pipes > 6:
        risks.append(f"{pipes} pipe characters — possible table or decorative separators")
    if odd:
        risks.append(f"{len(odd)} decorative symbols/emoji (e.g. {odd[0]})")
        fixes.append("use plain round bullets (•) or hyphens only")
    if caps_lines > 6:
        risks.append(f"{caps_lines} ALL-CAPS lines — hard to scan; keep caps for headings only")
    page_rule = None
    if years_experience >= 0:
        target = 1 if years_experience < 10 else 2
        page_rule = {"target_pages": target, "estimated_pages": pages, "ok": pages <= target + 0.2}
        if pages > target + 0.2:
            risks.append(f"~{pages} pages vs target {target} for {years_experience:g} yrs experience")
            fixes.append("cut oldest roles to one line each; drop bullets scoring < 60")
    if pages > 2.2:
        risks.append(f"~{pages} pages — never exceed 2")
    score = max(0, 100 - 15 * len(risks))
    return {
        "words": n_words,
        "estimated_pages": pages,
        "sections_found": found_sections,
        "contact": contact,
        "date_formats": {"parseable": good_dates, "unparseable": bad_dates},
        "layout_signals": {"tabs": tabs, "pipes": pipes, "wide_gap_lines": column_lines, "odd_symbols": len(odd), "all_caps_lines": caps_lines},
        "page_rule": page_rule,
        "parse_risks": risks,
        "fixes": fixes,
        "parse_score": score,
        "file_advice": "Submit .docx or a text-based PDF (not scanned). Filename: Firstname-Lastname-Resume. No headers/footers for contact info.",
        "verdict": ("Clean parse expected." if not risks else f"{len(risks)} parse risk(s) — fix these before wording work."),
    }


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _parse_ym(value: str, as_of: date, label: str) -> tuple[int, int]:
    v = str(value).strip().lower()
    if v in ("present", "current", "now", "today", ""):
        return as_of.year, as_of.month
    m = re.match(r"^(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?$", v)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
    else:
        m = re.match(r"^([a-z]{3})[a-z]*\.?\s+(\d{4})$", v)
        if m and m.group(1) in MONTHS:
            y, mo = int(m.group(2)), MONTHS[m.group(1)]
        else:
            m = re.match(r"^(\d{1,2})/(\d{4})$", v)
            if m:
                y, mo = int(m.group(2)), int(m.group(1))
            elif re.match(r"^\d{4}$", v):
                y, mo = int(v), 1
            else:
                raise ToolError(f"{label}: can't read date {value!r}. Use 'YYYY-MM', 'Mon YYYY', 'MM/YYYY' or 'present'.")
    if not 1 <= mo <= 12 or not 1950 <= y <= 2100:
        raise ToolError(f"{label}: date {value!r} out of range.")
    return y, mo


def _fmt_months(m: int) -> str:
    y, r = divmod(m, 12)
    parts = [f"{y} yr{'s' if y != 1 else ''}"] if y else []
    if r or not parts:
        parts.append(f"{r} mo")
    return " ".join(parts)


@AGENT.tool
def compute_tenure(roles: list[dict], as_of: str = "") -> dict:
    """Compute exact tenure per role, total experience (overlaps deduped), gaps over 3 months and job-hopping signals.

    Args:
        roles: List of {"title": str, "company": str, "start": "YYYY-MM" | "Mon YYYY", "end": "YYYY-MM" | "present"}.
        as_of: Date for "present" as YYYY-MM-DD. Defaults to today.
    """
    require_list(roles, "roles", max_items=100)
    today = dates.parse_date(as_of) if as_of else date.today()
    parsed = []
    for i, r in enumerate(roles, 1):
        if not isinstance(r, dict) or "start" not in r:
            raise ToolError(f"role #{i} needs at least a 'start' date.")
        sy, sm = _parse_ym(r["start"], today, f"role #{i} start")
        ey, em = _parse_ym(r.get("end", "present"), today, f"role #{i} end")
        s_idx, e_idx = sy * 12 + sm - 1, ey * 12 + em - 1
        if e_idx < s_idx:
            raise ToolError(f"role #{i}: end ({r.get('end')}) is before start ({r['start']}).")
        months = e_idx - s_idx + 1
        parsed.append({"n": i, "title": str(r.get("title", ""))[:120], "company": str(r.get("company", ""))[:120], "s": s_idx, "e": e_idx, "months": months})
    parsed.sort(key=lambda p: p["s"])
    # Total months with overlaps merged.
    covered: list[list[int]] = []
    for p in parsed:
        if covered and p["s"] <= covered[-1][1] + 1:
            covered[-1][1] = max(covered[-1][1], p["e"])
        else:
            covered.append([p["s"], p["e"]])
    total = sum(e - s + 1 for s, e in covered)
    gaps = []
    for (s1, e1), (s2, e2) in zip(covered, covered[1:]):
        gap = s2 - e1 - 1
        if gap > 3:
            gaps.append({"months": gap, "from": f"{(e1 + 1) // 12}-{(e1 + 1) % 12 + 1:02d}", "to": f"{(s2 - 1) // 12}-{(s2 - 1) % 12 + 1:02d}", "label": _fmt_months(gap)})
    overlaps = [
        {"a": a["title"] or f"role #{a['n']}", "b": b["title"] or f"role #{b['n']}", "months": min(a["e"], b["e"]) - b["s"] + 1}
        for i, a in enumerate(parsed)
        for b in parsed[i + 1 :]
        if b["s"] <= a["e"]
    ]
    tenures = [p["months"] for p in parsed]
    median = statistics.median(tenures)
    recent_cut = today.year * 12 + today.month - 1 - 60
    short_recent = [p for p in parsed if p["months"] < 12 and p["e"] >= recent_cut]
    hop_flag = len(short_recent) >= 3
    timeline = [
        {
            "title": p["title"],
            "company": p["company"],
            "start": f"{p['s'] // 12}-{p['s'] % 12 + 1:02d}",
            "end": f"{p['e'] // 12}-{p['e'] % 12 + 1:02d}",
            "months": p["months"],
            "tenure": _fmt_months(p["months"]),
        }
        for p in parsed
    ]
    flags = []
    if gaps:
        flags.append(f"{len(gaps)} gap(s) over 3 months — decide with the user how to present them")
    if hop_flag:
        flags.append(f"{len(short_recent)} roles under 12 months in the last 5 years — expect a 'why so many moves' question; prepare a one-line reason each")
    if overlaps:
        flags.append("overlapping roles — label the concurrent one (contract/part-time) so it doesn't look like a typo")
    return {
        "as_of": today.isoformat(),
        "timeline": timeline,
        "total_months": total,
        "total_experience": _fmt_months(total),
        "median_tenure_months": median,
        "average_tenure_months": round(statistics.mean(tenures), 1),
        "longest_tenure_months": max(tenures),
        "gaps": gaps,
        "overlaps": overlaps,
        "job_hopping_flag": hop_flag,
        "flags": flags,
        "verdict": f"{_fmt_months(total)} total across {len(parsed)} role(s); median tenure {_fmt_months(int(median))}."
        + (f" {len(gaps)} gap(s) to address." if gaps else " No gaps over 3 months."),
    }
