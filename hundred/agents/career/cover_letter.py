"""Cover Letter Writer — a letter that maps the JD's top requirements to specific evidence, in under 350 words."""

from __future__ import annotations

import re

from ...core import Agent, ToolError
from ...lib import text
from ._common import extract_skill_terms, pct, require_list, require_text, scan_lexicon, split_requirements

AGENT = Agent(
    slug="cover-letter",
    name="Cover Letter Writer",
    category="career",
    tagline="A cover letter that answers the job's top three requirements with proof — 250-350 words, zero clichés.",
    description=(
        "Writes cover letters the way hiring managers wish they were written: it pulls the must-have "
        "requirements out of the job description, maps each to one concrete piece of evidence from your "
        "background, and drafts a letter that opens with a specific hook instead of 'I am writing to apply'. "
        "Tools extract and rank the JD's requirements, check the draft for length, clichés, 'I'-heavy "
        "sentences and readability, and verify every top requirement is actually answered in the letter."
    ),
    triggers=[
        "write a cover letter for this job",
        "improve / review my cover letter",
        "what should my cover letter say for this role",
        "is my cover letter too long or generic",
        "tailor my cover letter to this job description",
    ],
    examples=[
        "Write a cover letter for this Customer Success Manager posting. Here's my resume and the JD.",
        "Here's my draft cover letter — it feels generic. Make it specific to the job.",
        "I'm switching from teaching to instructional design; help me write a letter that bridges the gap.",
    ],
    connectors=["Google Docs", "Gmail", "Notion"],
    playbook="""
    ## Standard
    You are a career coach whose clients get interviews at a rate hiring managers notice. A
    great cover letter is not a resume in prose. It is a 250-350 word argument with exactly one
    job: make the reader think "this person understood what we need and has already done it".
    The metric: every top-3 must-have requirement in the JD is answered with one specific,
    verifiable example — and the letter can only have been written for this company.

    ## Intake
    You need the job description and the candidate's background (resume, LinkedIn text, or a
    few bullet points). If you have neither, ask for both in one message. If you have the JD
    but only thin background, ask ONE question: "Give me your two proudest, most relevant
    results for this role, with numbers." Do not ask about tone or length — the defaults below
    are correct. If a hiring manager's name is unknown, address it "Dear <Team> Hiring Team"
    (never "To Whom It May Concern").

    ## Procedure
    1. **Extract what the job is really asking for.** Call `cover_letter__extract_requirements`
       with the JD. It returns requirements ranked by tier (must/nice), with years and degree
       flags and the skill terms in each. Pick the top three must-haves by rank — those are
       the letter's spine. If the JD is a laundry list, the tool's `priority` list tells you
       which three matter most (mentioned most, earliest, in must-have sections). Its
       `responsibilities` list is separate — use one of those for the bridge paragraph.
    2. **Map evidence.** For each of the three, choose ONE example from the candidate's
       background with a number, a scope, or a named outcome. If no evidence exists for one,
       choose the nearest transferable example and say so honestly in the letter ("I haven't
       run paid social at your scale, but…"). Never fabricate.
    3. **Draft** using the structure in Frameworks. Write the hook first and last: the opening
       sentence must contain something only true of this company (product, recent launch,
       stated mission, a metric from the posting). Ban the phrase "I am writing to".
    4. **Lint the draft.** Call `cover_letter__check_letter` with the letter, JD, company and
       role. Fix everything it flags: clichés, sentences starting with "I" over 40%, word
       count outside 250-350, missing company/role mention, passive voice, reading grade
       above 11. Then call `cover_letter__requirement_coverage` with the letter and the top
       three requirement texts. Any requirement with `status` "missing" or "partial" gets an
       evidence sentence that names its `skills_missing` (or says honestly you lack them).
    5. **Iterate once**, re-run `cover_letter__check_letter`, and only deliver a draft that
       scores ≥ 80. Report the score.
    6. **Deliver** the letter plus a 2-line "why this works" note and the subject line to use
       if it's going by email.

    ## Frameworks
    - **Structure (4 paragraphs, ~300 words):**
      1. Hook (2-3 sentences): the company-specific observation + the role + the one-line
         thesis of why you're the fit.
      2. Proof (the longest paragraph, or two short ones): requirement → evidence, three times.
         Each proof = what you did, the number, why it matters to THEM.
      3. Bridge (2-3 sentences): the thing you'd do in the first 90 days, or the gap you'd
         close for them. Shows you read the role, not just the requirements.
      4. Close (2 sentences): direct ask for a conversation; thanks. No "I look forward to
         hearing from you" filler — say what you'd bring to the first call.
    - **"I" discipline:** ≤ 40% of sentences start with "I". Rewrite alternate sentences to
      lead with the company, the result, or the action ("At Acme, churn fell 18% after…").
    - **Readability:** Flesch-Kincaid grade 8-11. Short sentences beat elegant ones.
    - **Length rule:** 250-350 words. Under 200 reads as low effort; over 400 doesn't get read.
    - **Career changers:** name the change in sentence two, then spend the proof paragraph
      on transferable results — not on explaining the old career.

    ## Output format
    ```
    **Subject (if emailed):** Application — <Role> — <Full Name>

    Dear <Name / Team> Hiring Team,

    <Paragraph 1: hook + thesis>

    <Paragraph 2: requirement 1 → evidence; requirement 2 → evidence; requirement 3 → evidence>

    <Paragraph 3: bridge — first-90-days idea or gap you'd close>

    <Paragraph 4: close with a direct ask>

    <Full Name> · <phone> · <email> · <LinkedIn>

    ---
    Score: NN/100 · Words: NNN · Requirements covered: 3/3 · "I" sentences: NN%
    Why this works: <two lines>
    ```

    ## Anti-patterns
    - Opening with "I am writing to apply for…" or "I was excited to see…". The reader knows.
    - Re-listing the resume. The letter argues; the resume documents.
    - Adjectives about yourself ("passionate", "hard-working", "detail-oriented"). Show results.
    - Generic flattery ("your innovative company"). If the sentence fits any company, cut it.
    - Covering all ten requirements in one sentence each. Three, deeply.
    - Ending on "I look forward to hearing from you." End on what you'll bring to the call.
    - Exceeding one page / 350 words, or using 10-point font to cheat the limit.
    """,
)

CLICHES = {
    "i am writing to": "delete — open with a company-specific hook",
    "i am writing in regards": "delete — open with a company-specific hook",
    "to whom it may concern": "use 'Dear <Team> Hiring Team'",
    "dear sir or madam": "use 'Dear <Team> Hiring Team'",
    "i was excited to see": "delete — go straight to the hook",
    "i am excited": "cut or replace with a specific reason",
    "team player": "cut — show a collaboration result",
    "hard-working": "cut — show output",
    "hard worker": "cut — show output",
    "detail-oriented": "cut — show it ('zero defects across 40 releases')",
    "passionate": "cut — passion is evidenced, not declared",
    "self-starter": "cut — describe what you started",
    "go-getter": "cut",
    "think outside the box": "cut",
    "hit the ground running": "replace with the first-90-days idea",
    "perfect fit": "cut — let the evidence say it",
    "ideal candidate": "cut — let the evidence say it",
    "proven track record": "cut — cite the record",
    "fast-paced environment": "cut",
    "wear many hats": "cut",
    "i look forward to hearing from you": "replace with what you'll bring to the first call",
    "thank you for your time and consideration": "shorten to one specific thank-you",
    "please find attached": "cut",
    "references available upon request": "cut",
    "dynamic": "cut",
    "synergy": "cut",
    "leverage my skills": "say which skill does what",
    "unique opportunity": "cut",
    "your innovative company": "name the actual product/launch",
    "results-driven": "cut — show results",
    "fast learner": "cut — show something you learned fast and what it produced",
    "quick learner": "cut — show something you learned fast and what it produced",
}
I_START_RE = re.compile(r"^\W*I\b", re.I)


@AGENT.tool
def extract_requirements(job_description: str, top_n: int = 3) -> dict:
    """Extract and rank a job description's requirements into must-have vs nice-to-have, with years/degree flags and the top-N to answer.

    Call first. The `priority` list is the spine of the letter: it ranks must-haves by how
    often their skills recur in the JD and how early they appear.

    Args:
        job_description: Full job description text.
        top_n: How many requirements the letter should answer directly (default 3, max 5).
    """
    require_text(job_description, "job_description", max_chars=60_000)
    if not 1 <= top_n <= 5:
        raise ToolError("top_n must be between 1 and 5 — a letter can't answer more than five deeply.")
    reqs = split_requirements(job_description)
    if not reqs:
        raise ToolError("No requirement lines found — paste the full posting including the requirements/qualifications section.")
    freq = extract_skill_terms(job_description)
    for r in reqs:
        term_weight = sum(freq.get(t, 0) for t in r["skills"] if t not in r.get("nice_skills", []))
        tier_weight = {"must": 3.0, "unclear": 1.5, "nice": 0.5, "duty": 0.0}[r["tier"]]
        r["rank_score"] = round(tier_weight * (1 + term_weight) - 0.02 * r["n"], 2)
    must = [r for r in reqs if r["tier"] == "must"]
    nice = [r for r in reqs if r["tier"] == "nice"]
    unclear = [r for r in reqs if r["tier"] == "unclear"]
    duties = [r for r in reqs if r["tier"] == "duty"]
    priority = sorted([r for r in reqs if r["tier"] in ("must", "unclear")], key=lambda r: -r["rank_score"])[:top_n]
    years = [r["years"] for r in reqs if r["years"]]
    return {
        "counts": {"must": len(must), "nice": len(nice), "unclear": len(unclear), "duties": len(duties)},
        "priority": [{"n": r["n"], "text": r["text"], "tier": r["tier"], "skills": r["skills"], "rank_score": r["rank_score"]} for r in priority],
        "must_have": [{"n": r["n"], "text": r["text"], "years": r["years"], "degree": r["degree"], "skills": r["skills"]} for r in must],
        "nice_to_have": [{"n": r["n"], "text": r["text"], "skills": r["skills"]} for r in nice],
        "unclear": [{"n": r["n"], "text": r["text"]} for r in unclear],
        "responsibilities": [{"n": r["n"], "text": r["text"]} for r in duties],
        "years_required": max(years) if years else None,
        "degree_mentioned": any(r["degree"] for r in reqs),
        "top_terms": [t for t, _ in freq.most_common(12)],
        "verdict": f"{len(must) + len(nice) + len(unclear)} requirements ({len(must)} must-have) and {len(duties)} responsibilities. "
        f"Answer the {len(priority)} in `priority` with one concrete example each; use a responsibility for the bridge paragraph.",
    }


def _coverage(letter: str, requirements: list[str]) -> list[dict]:
    sents = text.sentences(letter)
    sent_terms = [(s, set(extract_skill_terms(s)) | {w.lower() for w in text.words(s) if w.lower() not in text.STOPWORDS and len(w) > 3}) for s in sents]
    letter_skills = set(extract_skill_terms(letter)).union(*(st for _, st in sent_terms)) if sent_terms else set()
    rows = []
    for i, req in enumerate(requirements, 1):
        rq_skills = set(extract_skill_terms(req))
        rq_words = {w.lower() for w in text.words(req) if w.lower() not in text.STOPWORDS and len(w) > 3}
        best, best_i, best_score, best_hits = None, -1, 0.0, []
        for j, (s, st) in enumerate(sent_terms):
            skill_hits = rq_skills & st
            word_hits = rq_words & st
            score = 2.0 * len(skill_hits) + len(word_hits)
            if score > best_score:
                best, best_i, best_score, best_hits = s, j, score, sorted(skill_hits | word_hits)
        # A requirement is answered only when MORE than half of its skill terms appear:
        # naming the job title ("Product Manager position") or one of two skills is a mention, not an answer.
        skills_hit = sorted(rq_skills & letter_skills)
        if rq_skills:
            share = len(skills_hit) / len(rq_skills)
            status = "covered" if share > 0.5 and best_score >= 2 else "partial" if skills_hit else "missing"
        else:
            status = "covered" if best_score >= 2 else "missing"
        # Evidence often spans two sentences ("I design the tests. One lifted conversion 23%.").
        window = " ".join(s for s, _ in sent_terms[best_i : best_i + 2]) if best_i >= 0 else ""
        has_number = bool(re.search(r"\d", window))
        rows.append(
            {
                "n": i,
                "requirement": req[:300],
                "covered": status == "covered",
                "status": status,
                "skills_in_letter": skills_hit,
                "skills_missing": sorted(rq_skills - letter_skills),
                "evidence_sentence": best[:300] if best else None,
                "matched_terms": best_hits,
                "quantified": has_number,
            }
        )
    return rows


@AGENT.tool
def requirement_coverage(letter: str, requirements: list[str]) -> dict:
    """Check which of the target requirements the letter actually answers, and whether each answer carries a number.

    Matches each requirement's skill terms and key words to the letter's sentences.
    Call after drafting; add an evidence sentence for anything with status "partial" or "missing"
    (partial = the letter names some of the requirement's skills but not most of them).

    Args:
        letter: The cover letter draft.
        requirements: The requirement texts to check (the top 3-5 from extract_requirements).
    """
    require_text(letter, "letter", max_chars=20_000)
    require_list(requirements, "requirements", max_items=20)
    reqs = [str(r) for r in requirements if str(r).strip()]
    if not reqs:
        raise ToolError("requirements list is empty.")
    rows = _coverage(letter, reqs)
    covered = sum(1 for r in rows if r["covered"])
    quantified = sum(1 for r in rows if r["covered"] and r["quantified"])
    partial = [r["n"] for r in rows if r["status"] == "partial"]
    return {
        "requirements": rows,
        "covered": covered,
        "partial": partial,
        "total": len(rows),
        "coverage_pct": pct(covered, len(rows)),
        "quantified_answers": quantified,
        "verdict": f"{covered}/{len(rows)} requirements answered, {quantified} with a number"
        + (f"; {len(partial)} only mentioned (see skills_missing)" if partial else "")
        + ". "
        + ("Ready." if covered == len(rows) and quantified >= min(2, len(rows)) else "Add evidence sentences for the gaps and a number to each answer."),
    }


@AGENT.tool
def check_letter(letter: str, job_description: str = "", company: str = "", role: str = "") -> dict:
    """Lint a cover letter: word count vs 250-350, clichés, 'I'-sentence share, readability, passive voice, company/role mentions, and a 0-100 score.

    Args:
        letter: The cover letter draft (greeting through sign-off).
        job_description: The JD, to check that the letter's terms overlap the posting (optional).
        company: Company name as it should appear (optional; checked for presence).
        role: Job title as posted (optional; checked for presence).
    """
    require_text(letter, "letter", max_chars=20_000)
    sents = text.sentences(letter)
    n_words = len(text.words(letter))
    i_starts = sum(1 for s in sents if I_START_RE.match(s))
    i_pct = pct(i_starts, len(sents))
    cliches = scan_lexicon(letter, CLICHES)
    passive = text.passive_sentences(letter)
    read = text.readability(letter)
    # Body paragraphs only: the greeting line and the sign-off/contact block are not paragraphs.
    paragraphs = [
        p
        for p in re.split(r"\n\s*\n", letter.strip())
        if len(text.words(p)) >= 4
        and not re.match(r"^\s*(dear|hi|hello|to whom|greetings)\b", p, re.I)
        and not (re.search(r"@|\(\d{3}\)|linkedin\.com", p) and len(text.words(p)) <= 25)
        and not re.match(r"^\s*(sincerely|best|regards|kind regards|warm regards|thank you|thanks|yours)\b[^.!?]*$", p, re.I)
    ]
    low = letter.lower()
    company_mentions = low.count(company.lower()) if company.strip() else None
    role_found = (role.lower() in low) if role.strip() else None
    opening = sents[0] if sents else ""
    greeting = re.search(r"^\s*(dear|hi|hello|to whom)\b.*$", letter.strip(), re.I | re.M)
    jd_overlap = None
    if job_description.strip():
        jd_terms = set(extract_skill_terms(job_description))
        if jd_terms:
            hit = jd_terms & set(extract_skill_terms(letter))
            jd_overlap = {"jd_terms": len(jd_terms), "in_letter": sorted(hit), "pct": pct(len(hit), len(jd_terms))}
    issues, fixes = [], []
    score = 100
    if n_words < 250:
        issues.append(f"{n_words} words — under 250 reads as low effort")
        score -= 10 if n_words >= 200 else 20
    elif n_words > 350:
        over = n_words - 350
        issues.append(f"{n_words} words — {over} over the 350 ceiling")
        score -= 10 if over <= 50 else 20
        fixes.append("cut the weakest proof or the flattery; keep three proofs")
    if cliches:
        issues.append("clichés: " + ", ".join(f"'{h['term']}'" for h in cliches))
        fixes.extend(f"'{h['term']}' → {h['suggestion']}" for h in cliches[:5])
        score -= min(30, 8 * len(cliches))
    if i_pct > 40:
        issues.append(f"{i_pct}% of sentences start with 'I' (max 40%)")
        fixes.append("lead alternate sentences with the company, the result, or the action")
        score -= 10
    if passive:
        issues.append(f"{len(passive)} passive sentence(s)")
        score -= min(10, 3 * len(passive))
    if read["fk_grade"] is not None and read["fk_grade"] > 11:
        issues.append(f"reading grade {read['fk_grade']} — over 11, shorten sentences")
        score -= 8
    if company.strip() and not company_mentions:
        issues.append(f"company name '{company}' never appears")
        score -= 10
    if role.strip() and not role_found:
        issues.append(f"role title '{role}' never appears")
        score -= 8
    if not greeting:
        issues.append("no greeting line found")
        score -= 5
    if re.match(r"^\W*I\s+(am|was|would like to)\b", opening, re.I):
        issues.append("opening sentence starts with 'I am/was…' — no hook")
        fixes.append("open with something only true of this company")
        score -= 8
    if len(paragraphs) < 3 or len(paragraphs) > 5:
        issues.append(f"{len(paragraphs)} paragraphs — use 4 (hook, proof, bridge, close)")
        score -= 5
    if jd_overlap and jd_overlap["pct"] < 25:
        issues.append(f"only {jd_overlap['pct']}% of the JD's key terms appear in the letter")
        score -= 8
    score = max(0, score)
    return {
        "score": score,
        "words": n_words,
        "sentences": len(sents),
        "paragraphs": len(paragraphs),
        "i_sentence_pct": i_pct,
        "cliches": cliches,
        "passive_sentences": passive[:5],
        "readability": {"fk_grade": read["fk_grade"], "flesch_reading_ease": read["flesch_reading_ease"], "avg_words_per_sentence": read.get("avg_words_per_sentence")},
        "company_mentions": company_mentions,
        "role_mentioned": role_found,
        "opening_sentence": opening[:200],
        "jd_term_overlap": jd_overlap,
        "issues": issues,
        "fixes": fixes,
        "verdict": ("Ready to send." if score >= 80 and not issues else f"Score {score}/100 — fix {len(issues)} issue(s) before sending."),
    }
