"""Helpers shared by the Career & HR agents (skipped by the registry: underscore module).

Skill-term extraction, requirement classification, lexicon scanning and small
validators. Everything is stdlib, deterministic and bounded.
"""

from __future__ import annotations

import re
from collections import Counter

from ...core import ToolError
from ...lib import text

MAX_TEXT = 200_000

# ── validation ────────────────────────────────────────────────────────────


def require_text(value: str, name: str, max_chars: int = MAX_TEXT, min_chars: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < min_chars:
        raise ToolError(f"{name} is empty — paste the full text.")
    if len(value) > max_chars:
        raise ToolError(f"{name} too long ({len(value):,} chars; max {max_chars:,}). Trim it and retry.")
    return value


def require_list(value: list, name: str, max_items: int = 500, min_items: int = 1) -> list:
    if not isinstance(value, list) or len(value) < min_items:
        raise ToolError(f"{name} must be a list with at least {min_items} item(s).")
    if len(value) > max_items:
        raise ToolError(f"{name} has {len(value)} items; max {max_items}.")
    return value


def require_number(value, name: str, lo: float | None = None, hi: float | None = None) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be a number, got {value!r}.") from None
    if f != f:  # NaN
        raise ToolError(f"{name} must be a number.")
    if lo is not None and f < lo:
        raise ToolError(f"{name} must be >= {lo}, got {value}.")
    if hi is not None and f > hi:
        raise ToolError(f"{name} must be <= {hi}, got {value}.")
    return f


def pct(part: float, whole: float, nd: int = 1) -> float:
    return round(100.0 * part / whole, nd) if whole else 0.0


def money(x: float) -> float:
    return round(float(x) + 0.0, 2)


# ── lexicon scanning ──────────────────────────────────────────────────────


def scan_lexicon(body: str, lexicon: dict[str, str]) -> list[dict]:
    """Find every lexicon term (word-bounded, case-insensitive) in body.

    lexicon maps term -> suggestion/reason. Terms are ours (not user input), so
    the compiled regex is safe. Returns [{term, count, suggestion, sample}] sorted by count.
    """
    if not body or not lexicon:
        return []
    hits = []
    for term, why in lexicon.items():
        pat = re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", re.I)
        found = list(pat.finditer(body))
        if found:
            m = found[0]
            lo, hi = max(0, m.start() - 40), min(len(body), m.end() + 40)
            sample = re.sub(r"\s+", " ", body[lo:hi]).strip()
            hits.append({"term": term, "count": len(found), "suggestion": why, "sample": f"…{sample}…"})
    hits.sort(key=lambda h: (-h["count"], h["term"]))
    return hits


# ── skills & requirements ─────────────────────────────────────────────────

# Canonical spellings for common aliases (lower-case in → canonical out).
SKILL_ALIASES: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "amazon web services": "aws",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "ci/cd": "ci/cd",
    "continuous integration": "ci/cd",
    "ga4": "google analytics",
    "seo/sem": "seo",
    "crm": "crm",
    "salesforce.com": "salesforce",
    "sfdc": "salesforce",
    "p&l": "p&l",
    "pnl": "p&l",
    "okrs": "okr",
    "kpis": "kpi",
    "a/b tests": "a/b testing",
    "ab testing": "a/b testing",
    "product management": "product management",
    "product manager": "product management",
    "product managers": "product management",
    "pm": "product management",
    "project manager": "project management",
    "program manager": "program management",
    "people manager": "people management",
    "engineering manager": "engineering management",
    "ux": "user experience",
    "ui/ux": "user experience",
    "people management": "people management",
    "stakeholder mgmt": "stakeholder management",
    "excel": "excel",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "powerpoint": "powerpoint",
    "gsuite": "google workspace",
    "g suite": "google workspace",
}

_SKILL_LINES = """
python|java|javascript|typescript|c++|c#|go|golang|rust|ruby|php|swift|kotlin|scala|sql|nosql|html|css
react|angular|vue|svelte|next.js|node.js|django|flask|fastapi|spring|rails|.net|graphql|rest api|rest apis|apis
postgresql|mysql|mongodb|redis|elasticsearch|snowflake|bigquery|redshift|databricks|spark|hadoop|kafka
airflow|dbt|tableau|looker|power bi|excel|google sheets|pandas|numpy|pytorch|tensorflow|scikit-learn
machine learning|deep learning|artificial intelligence|natural language processing|computer vision
llm|llms|generative ai|prompt engineering|data science|data analysis|data engineering|data modeling
statistics|experimentation|a/b testing|analytics|google analytics|mixpanel|amplitude|segment
aws|azure|google cloud|kubernetes|docker|terraform|ansible|linux|bash|ci/cd|github|gitlab|jenkins
devops|sre|observability|datadog|grafana|prometheus|security|iam|soc 2|iso 27001|gdpr|hipaa|pci
microservices|distributed systems|system design|scalability|performance testing|qa automation|selenium
cypress|playwright|jest|pytest|agile|scrum|kanban|jira|confluence|roadmap|roadmapping|prioritization
product management|product strategy|product discovery|user research|usability testing|wireframing
figma|sketch|prototyping|design systems|user experience|ui design|visual design|interaction design
accessibility|wcag|content design|copywriting|seo|sem|ppc|google ads|meta ads|linkedin ads|paid social
paid search|email marketing|marketing automation|hubspot|marketo|salesforce|pardot|crm|demand generation
lead generation|abm|account-based marketing|brand marketing|content marketing|growth marketing
lifecycle marketing|product marketing|go-to-market|positioning|messaging|pricing|packaging
sales enablement|pipeline management|forecasting|quota|prospecting|cold calling|cold outreach
discovery|negotiation|closing|enterprise sales|smb|mid-market|saas|b2b|b2c|renewals|upsell|cross-sell
customer success|account management|onboarding|retention|churn|nps|customer support|zendesk
financial modeling|fp&a|budgeting|variance analysis|gaap|ifrs|audit|tax|treasury
accounts payable|accounts receivable|quickbooks|netsuite|sap|oracle|workday|erp|p&l|cash flow
valuation|dcf|m&a|due diligence|fundraising|investor relations|bookkeeping|payroll
project management|program management|pmp|prince2|stakeholder management|change management
operations|supply chain|logistics|procurement|inventory management|vendor management|lean|six sigma
process improvement|people management|team leadership|hiring|recruiting|talent acquisition
performance management|compensation|benefits|hris|employee relations|learning and development
dei|coaching|mentoring|executive presence|public speaking|communication
written communication|presentation skills|cross-functional collaboration|okr|kpi|reporting|dashboards
problem solving|critical thinking|strategic planning|business development|partnerships
legal|contracts|compliance|risk management|regulatory|privacy|intellectual property
clinical research|healthcare|pharma|biotech|medical devices|nursing|patient care
teaching|curriculum|instructional design|e-learning|lms|training|facilitation
video editing|photoshop|illustrator|premiere|after effects|canva|social media|community management
powerpoint|google workspace|microsoft office|notion|asana|trello|slack
spanish|french|german|mandarin|portuguese|japanese|bilingual
"""
# Curated skill lexicon: the terms ATS keyword matching actually keys on.
SKILL_LEXICON: frozenset[str] = frozenset(t.strip() for line in _SKILL_LINES.strip().splitlines() for t in line.split("|") if t.strip())

_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9&/+#.]{1,7}\b")
_TECH_TOKEN_RE = re.compile(r"(?<![\w.])(?:[A-Za-z]+[#+]{1,2}|\.[A-Za-z]{2,}|[A-Za-z]+\.(?:js|py|net|io))(?![\w])")
_CAMEL_RE = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")
_GENERIC_ACRONYMS = frozenset("THE AND FOR YOU OUR ARE NOT WITH FROM THIS THAT WILL EEO USA US UK EU".split())
# Capitalised word mid-sentence (after a lowercase word) — catches product/company names like "Stripe".
_PROPER_RE = re.compile(r"(?<=[a-z,;] )([A-Z][a-z]{2,})(?![\w.])")
_COMMON_CAPS = frozenset(
    """Bachelor Bachelors Master Masters Degree Experience Senior Junior Strong Ability Company Team Role
    January February March April May June July August September October November December Monday Tuesday
    Wednesday Thursday Friday Saturday Sunday United States America English North South East West New York
    San Francisco London Europe Asia Remote Hybrid Full Part Time Equal Opportunity Employer Inc Ltd LLC
    Please Apply About Requirements Responsibilities Benefits Salary Location Department Reports Director
    Manager Engineer Analyst Associate Lead Head Vice President Chief Officer Specialist Coordinator
    Science Arts Business Administration University College School Computer Engineering Marketing Sales
    Finance Operations Product Design Data Customer Success Support Human Resources""".split()
)


_ALL_TERMS: tuple[str, ...] = tuple(sorted(SKILL_LEXICON | frozenset(SKILL_ALIASES), key=len, reverse=True))


def canonical_term(term: str) -> str:
    t = re.sub(r"\s+", " ", term.strip().lower())
    return SKILL_ALIASES.get(t, t)


def _build_lexicon_regex() -> re.Pattern:
    # One alternation, longest-first, so a single pass finds every term. Terms that end
    # in a symbol (c++, c#) get no trailing boundary; alphanumeric ones do.
    alnum = [re.escape(t) for t in _ALL_TERMS if t[-1].isalnum()]
    sym = [re.escape(t) for t in _ALL_TERMS if not t[-1].isalnum()]
    parts = []
    if alnum:
        parts.append("(?:" + "|".join(alnum) + r")(?![\w])")
    if sym:
        parts.append("(?:" + "|".join(sym) + ")")
    return re.compile(r"(?<![\w])(?:" + "|".join(parts) + ")", re.I)


_LEXICON_RE = _build_lexicon_regex()


def extract_skill_terms(body: str) -> Counter:
    """Return Counter of canonical skill terms found in a text.

    Sources: curated lexicon (multi-word aware), alias table, ALL-CAPS acronyms,
    tech tokens (C++, .NET, Node.js) and CamelCase product names. Overlapping
    matches resolve to the longest span so "Node.js" counts once, not three times.
    """
    body = body or ""
    spans: list[tuple[int, int, str]] = []
    for m in _LEXICON_RE.finditer(body):
        spans.append((m.start(), m.end(), canonical_term(m.group(0))))
    for m in _ACRONYM_RE.finditer(body):
        if m.group(0) in _GENERIC_ACRONYMS:
            continue
        spans.append((m.start(), m.end(), canonical_term(m.group(0))))
    for m in _TECH_TOKEN_RE.finditer(body):
        spans.append((m.start(), m.end(), canonical_term(m.group(0))))
    for m in _CAMEL_RE.finditer(body):
        spans.append((m.start(), m.end(), canonical_term(m.group(0))))
    for m in _PROPER_RE.finditer(body):
        if m.group(1) not in _COMMON_CAPS:
            spans.append((m.start(1), m.end(1), canonical_term(m.group(1))))
    # Longest span wins; ties broken by earliest start.
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    counts: Counter = Counter()
    cursor = -1
    for start, end, term in spans:
        if start < cursor:
            continue
        counts[term] += 1
        cursor = end
    return counts


MUST_CUES = re.compile(
    r"\b(required|requirements?|must[- ]haves?|must have|must be|essential|minimum|mandatory|non[- ]negotiable|you have|you bring|qualifications)\b",
    re.I,
)
NICE_CUES = re.compile(r"\b(preferred|nice[- ]to[- ]have|bonus|plus|ideally|desirable|a plus|good to have|not required|optional)\b", re.I)
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b", re.I)
DEGREE_RE = re.compile(r"\b(bachelor'?s?|master'?s?|mba|ph\.?d|doctorate|b\.?s\.?|b\.?a\.?|m\.?s\.?|degree)\b", re.I)
BULLET_RE = re.compile(r"^\s*(?:[-*•·▪◦o]|\d{1,2}[.)])\s+")


def split_requirements(jd: str) -> list[dict]:
    """Split a job description into requirement lines tagged must/nice.

    Uses section headings ("Requirements", "Nice to have") to set a running
    default, and per-line cue words to override it. Returns
    [{"n", "text", "tier": "must"|"nice"|"duty"|"unclear", "years", "degree", "section"}].
    "duty" lines come from a Responsibilities section — what the job does, not what it requires.
    """
    out = []
    current_tier = "unclear"
    section = ""
    n = 0
    for raw in jd.splitlines():
        line = raw.strip()
        if not line:
            continue
        is_bullet = bool(BULLET_RE.match(raw))
        is_heading = (not is_bullet) and len(line) <= 60 and not line.endswith(".") and (line.endswith(":") or line.istitle() or line.isupper())
        if is_heading:
            section = line.rstrip(":")
            if NICE_CUES.search(line):
                current_tier = "nice"
            elif MUST_CUES.search(line):
                current_tier = "must"
            elif re.search(r"\b(responsibilit|what you.ll do|what you will do|you will|day[- ]to[- ]day|duties|the role|in this role)", line, re.I):
                current_tier = "duty"
            elif re.search(r"\b(about|benefits|perks|we offer|compensation|why join|our team)", line, re.I):
                current_tier = "unclear"
            continue
        if not is_bullet and len(text.words(line)) < 4:
            continue
        body = BULLET_RE.sub("", raw).strip() if is_bullet else line
        tier = current_tier
        if tier != "duty":
            if NICE_CUES.search(body):
                tier = "nice"
            elif MUST_CUES.search(body):
                tier = "must"
        if not is_bullet and tier == "unclear":
            continue  # prose outside a requirements section
        n += 1
        ym = YEARS_RE.search(body)
        years = int(ym.group(1)) if ym else None
        out.append(
            {
                "n": n,
                "text": body[:300],
                "tier": tier,
                "years": years,
                "degree": bool(DEGREE_RE.search(body)),
                "section": section,
                "skills": sorted(extract_skill_terms(body)),
            }
        )
        if len(out) >= 200:
            break
    return out
