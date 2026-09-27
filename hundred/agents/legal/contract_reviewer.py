"""Contract Reviewer — clause-by-clause risk review, deadline extraction, renewal calendar, liability math."""

from __future__ import annotations

import re
from datetime import timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import DURATION_RE, SCOPE_NOTE, add_months, check_text, duration_days, excerpt, money, parse_date, parse_number
from ._common import term_end as _term_end
from ._common import to_float

AGENT = Agent(
    slug="contract-reviewer",
    name="Contract Reviewer",
    category="legal",
    tagline="Clause-by-clause red flags, every deadline on a calendar, and the redlines to ask for — before you sign.",
    description=(
        "Reviews commercial contracts (SaaS, MSA, services, licensing, vendor) the way an experienced "
        "commercial lawyer triages them: detects 26 clause types and scores red flags from your side of the "
        "table (customer or vendor), extracts every deadline, notice period and auto-renewal trap, builds the "
        "renewal/notice calendar with reminder dates, quantifies liability-cap exposure against market norms, "
        "and produces a prioritised issues list with market-standard fallback language. Drafting aid, not legal advice."
    ),
    triggers=[
        "review this contract / agreement / terms",
        "what are the red flags in this MSA / SaaS agreement",
        "when do I have to give notice to cancel / auto-renewal date",
        "is this liability cap normal",
        "redline suggestions for this vendor contract",
        "summarise the key terms and deadlines in this agreement",
    ],
    examples=[
        "Here's the SaaS agreement a vendor sent us — we're the customer. What should we push back on?",
        "Pull every deadline and notice period out of this MSA; the effective date is 2026-10-01.",
        "Contract value is $240k/yr, liability capped at 3 months of fees with no carve-outs. Is that market?",
    ],
    connectors=["Google Docs", "Notion", "DocuSign", "Google Calendar", "Slack", "Gmail"],
    playbook="""
    ## Standard
    You are a senior commercial lawyer doing a first-pass review for a business client. Excellent
    work is prioritised (the three things that could actually hurt them, first), specific (clause,
    quote, why it matters, what to ask for instead), and calendar-ready (every date computed, not
    described). The one metric that matters is **no surprise after signature** — no unexpected
    renewal, no uncapped exposure, no missed notice window.

    **Scope note (say this once in every output):** this is a drafting/review aid, not legal
    advice. Jurisdiction and governing law change the analysis. Recommend a licensed lawyer for
    contracts above ~$100k, anything cross-border, IP assignments, employment terms, or regulated
    data — and say so in the output.

    ## Intake
    Proceed with the text you have. Ask (max 3) only if you cannot infer: (1) which party the user
    is (customer/buyer vs vendor/seller — it flips every red flag), (2) contract value and term
    (needed for exposure math), (3) effective date (needed for the calendar). If not given, assume
    the user is the customer, state it, and continue.

    ## Procedure
    1. **Detect and score.** Call `contract_reviewer__detect_clauses` with the full text, the
       user's role and their home state/country as `my_jurisdiction` (flags a far-away governing
       law or venue). It finds 26 clause types (limitation of liability, indemnity, IP, termination,
       auto-renewal, non-compete, exclusivity, assignment, governing law, data protection, SLA,
       payment, price increases, audit, insurance, etc.), quotes the excerpt, and scores red flags
       0-100 from the user's side. Missing protective clauses count as flags too. It also reads
       the liability cap (`liability_cap`: who is capped, months of fees) — feed that straight
       into step 4 — and checks termination symmetry, data ownership and indemnity mutuality.
       Regex detection can miss unusual drafting: still read definitions, fees, term,
       termination, liability, indemnity and data clauses yourself (step 5).
    2. **Extract deadlines.** Call `contract_reviewer__extract_deadlines` with the text and the
       effective date. It returns every "within N days", notice period, cure period, payment term
       and explicit date, and what each one counts from (`counts_from`). Only durations that run
       from the effective date get a `from_effective_date`; a "90 days prior to the end of the
       term" window gets `deadline_in_initial_term`. Never present an event-anchored duration
       ("30 days after notice") as a calendar date. Never compute dates yourself.
    3. **Build the renewal calendar.** If the contract has a term, call
       `contract_reviewer__renewal_calendar` with effective date, initial term, notice window and
       renewal term. It returns the term end, the last day to give notice, a reminder date
       (30 days earlier), and the next three renewal dates; if the deadline falls on a weekend
       `weekend_note` gives the last safe business day. Put these in the user's calendar if
       Google Calendar is connected.
    4. **Quantify liability.** Call `contract_reviewer__liability_exposure` with contract value,
       the cap as written (multiple of fees or fixed amount), carve-outs, and whether consequential
       damages are excluded. It computes the cap in dollars, compares it to market (12 months'
       fees for general liability; higher or uncapped for data breach/IP/confidentiality carve-outs
       is common), and states the uncapped exposure the user carries.
    5. **Read the flagged clauses yourself.** The tools find and score; you judge. For each red
       flag write: **Clause** → **What it says** (quote) → **Why it matters to you** → **Ask for**
       (market-standard position) → **Fallback** (what to accept if they refuse).
    6. **Rank** into Deal-breakers (uncapped liability for the user, one-way indemnity against them,
       broad non-compete, IP assignment of pre-existing work, unilateral price increases with no
       cap), Negotiate (auto-renewal without notice reminder, short cure periods, broad audit
       rights, assignment without consent), and Accept (standard boilerplate).
    7. **Deliver** in the output format. If DocuSign/Docs is connected, add comments to the
       document at each flagged clause; otherwise output the redline list ready to send.

    ## Frameworks
    - **Market positions (mid-market SaaS/services):** liability cap = 12 months' fees, mutual;
      super-cap (2-3× or uncapped) for breach of confidentiality, data protection, IP indemnity,
      gross negligence/wilful misconduct. Consequential damages excluded mutually. Termination for
      convenience: 30-90 days' notice. Cure period 30 days. Auto-renewal notice 30-60 days.
      Price increases capped at CPI or 3-5%/yr with 60+ days' notice. Payment net 30.
    - **Indemnity symmetry:** vendor indemnifies for IP infringement and data breach; customer for
      misuse of the service and its own content. One-way indemnity = flag.
    - **Assignment:** consent not to be unreasonably withheld; free assignment on change of control
      is acceptable if mutual.
    - **Governing law / venue:** far-away venue is a cost, not just a legal risk; arbitration clauses
      waive jury trial and class actions — note both.
    - **Reading order:** definitions → term/termination → fees → liability/indemnity → IP → data →
      everything else. Definitions change the meaning of every later clause.

    ## Output format
    ```
    # Contract review: <title> — reviewing as <customer/vendor> — <date>
    **Verdict:** <sign / negotiate N points / do not sign as-is> · Risk score <n>/100
    **Scope:** Drafting/review aid, not legal advice; recommend counsel because <reason, if any>.

    ## Deal-breakers
    1. **<Clause §x — name>** — "<quote>"
       Why it matters: … · Ask for: … · Fallback: …
    ## Negotiate
    …
    ## Accept (standard)
    - <clause list>

    ## Key dates
    | Event | Date | Days from today | Action |
    | Notice deadline to avoid renewal | 2027-08-02 | 309 | calendar reminder 2027-07-03 |

    ## Liability snapshot
    Cap: <$X (12 mo fees)> · Carve-outs: … · Your uncapped exposure: … · Market: …

    ## Redline requests (paste to the other side)
    1. §x: replace "…" with "…"
    ```

    ## Anti-patterns
    - Listing every clause. Rank by harm; three real problems beat thirty observations.
    - "This clause is unfavourable" with no alternative language. Always give the ask and the fallback.
    - Reviewing from the wrong side. A customer-friendly cap is vendor-hostile; confirm the role.
    - Describing dates ("30 days before the end of term") instead of computing them.
    - Missing the definitions section. "Confidential Information", "Fees" and "Services" decide the case.
    - Silent on the missing clauses. No liability cap at all means uncapped — say it.
    """,
)

# (key, label, regex, protective_for, risk_when_present_for) — role sensitivity
CLAUSES: list[dict] = [
    {"key": "limitation_of_liability", "label": "Limitation of liability", "rx": r"limitation of liability|limit(?:ed|s)? (?:its |their |our )?liability(?! (?:company|partnership|limited))|in no event shall .{0,60}liab|aggregate liability|liability .{0,40}(?:shall not|will not) exceed", "missing_flag": "No liability cap found — liability may be uncapped for both sides"},
    {"key": "consequential_exclusion", "label": "Exclusion of consequential damages", "rx": r"consequential|indirect(?:,| or)? (?:special|incidental)|loss of profits?|lost profits|special, incidental", "missing_flag": "No consequential-damages exclusion — lost-profit claims are open"},
    {"key": "indemnity", "label": "Indemnification", "rx": r"indemnif(?:y|ies|ication)|hold (?:\w+ )?harmless|defend,? indemnify", "missing_flag": "No indemnity — you have no contractual protection for third-party IP or data claims"},
    {"key": "ip_ownership", "label": "IP ownership / assignment", "rx": r"intellectual property|work (?:made )?for hire|hereby assigns?|assignment of (?:rights|inventions)|all right, title,? and interest|ownership of (?:deliverables|work product)", "missing_flag": "No IP clause — ownership of deliverables/work product is undefined"},
    {"key": "license_grant", "label": "License grant / scope", "rx": r"grants? .{0,40}(?:non-?exclusive|exclusive|worldwide|perpetual|irrevocable|revocable)? ?licen[cs]e|right to (?:use|access)", "missing_flag": None},
    {"key": "term", "label": "Term", "rx": r"\bterm of (?:this|the) agreement|initial term|shall commence|commencement date|effective date|for a period of", "missing_flag": "No term stated — is this perpetual?"},
    {"key": "auto_renewal", "label": "Auto-renewal", "rx": r"automatically renew|auto-?renew|renew(?:s|al)? (?:automatically|for successive|for additional)|successive (?:renewal )?(?:terms?|periods?)|evergreen", "missing_flag": None},
    {"key": "termination_convenience", "label": "Termination for convenience", "rx": r"terminat\w+ .{0,40}(?:for convenience|without cause|for any reason|at any time)|for convenience", "missing_flag": "No termination for convenience — you may be locked in for the full term"},
    {"key": "termination_cause", "label": "Termination for cause / cure period", "rx": r"material breach|terminat\w+ .{0,60}(?:for cause|breach)|cure (?:period|such breach)|fails? to cure|opportunity to cure", "missing_flag": "No termination-for-cause / cure mechanism"},
    {"key": "payment_terms", "label": "Payment terms", "rx": r"net (?:\d{1,3}|thirty|sixty|ninety)|payable within|due (?:and payable )?within|invoice[sd]? .{0,40}(?:days|monthly|annually)|payment terms", "missing_flag": "No payment terms — when are invoices due?"},
    {"key": "late_fees", "label": "Late fees / interest", "rx": r"late (?:fee|charge|payment)|interest .{0,30}(?:per (?:month|annum)|%)|1\.5% per month|overdue", "missing_flag": None},
    {"key": "price_increase", "label": "Price increases", "rx": r"increase .{0,40}(?:fees|prices|rates)|price (?:increase|adjustment)|(?:fees|prices) .{0,30}(?:may|will) (?:be )?(?:increase|adjust)|(?:may|reserves? the right to) (?:change|increase|modify|adjust|revise) (?:the |its )?(?:fees|prices|pricing|rates)|\bcpi\b|consumer price index", "missing_flag": None},
    {"key": "non_compete", "label": "Non-compete / exclusivity", "rx": r"non-?compet\w*|shall not .{0,40}compet\w*|exclusiv(?:e|ity) (?:supplier|provider|partner|right)|sole (?:and exclusive )?(?:supplier|provider)", "missing_flag": None},
    {"key": "non_solicit", "label": "Non-solicitation", "rx": r"non-?solicit\w*|shall not .{0,40}solicit|solicit .{0,40}(?:employees|personnel|customers)", "missing_flag": None},
    {"key": "confidentiality", "label": "Confidentiality", "rx": r"confidential(?:ity| information)|non-?disclosure|proprietary information", "missing_flag": "No confidentiality clause"},
    {"key": "data_protection", "label": "Data protection / privacy", "rx": r"personal data|personal information|data processing|gdpr|ccpa|data protection|privacy|dpa\b|sub-?processors?|security incident|data breach", "missing_flag": "No data-protection terms — required if any personal data is processed"},
    {"key": "sla", "label": "Service levels / SLA", "rx": r"service level|sla\b|uptime|availability of \d|\d{2}\.\d+%|service credits?|response time", "missing_flag": None},
    {"key": "warranty", "label": "Warranties / disclaimers", "rx": r"warrant(?:y|ies|s)|as is|as-is|disclaims? all|merchantability|fitness for a particular purpose", "missing_flag": None},
    {"key": "assignment", "label": "Assignment / change of control", "rx": r"assign(?:ment|ed|s)? .{0,60}(?:consent|without|prior written)|change of control|may not assign|shall not assign", "missing_flag": None},
    {"key": "governing_law", "label": "Governing law / venue", "rx": r"governed by|governing law|laws of (?:the )?(?:state|commonwealth|province|republic|england)|exclusive jurisdiction|\bvenue\b|courts? (?:of|located in)", "missing_flag": "No governing law — disputes will start with an argument about where to argue"},
    {"key": "arbitration", "label": "Arbitration / dispute resolution", "rx": r"arbitrat\w+|binding arbitration|jury trial|class action|mediation|dispute resolution", "missing_flag": None},
    {"key": "audit", "label": "Audit rights", "rx": r"audit|inspect(?:ion)? .{0,30}(?:records|books|premises)|right to (?:examine|verify)", "missing_flag": None},
    {"key": "insurance", "label": "Insurance", "rx": r"insurance|coverage of not less than|certificate of insurance|errors and omissions|cyber liability", "missing_flag": None},
    {"key": "force_majeure", "label": "Force majeure", "rx": r"force majeure|acts? of god|beyond (?:its|their|the) reasonable control", "missing_flag": None},
    {"key": "entire_agreement", "label": "Entire agreement / amendments", "rx": r"entire agreement|supersedes all|amend(?:ed|ment)s? .{0,40}in writing|signed by both", "missing_flag": None},
    {"key": "survival", "label": "Survival", "rx": r"surviv(?:e|al)s? .{0,40}(?:termination|expiration)", "missing_flag": None},
]

# red-flag patterns evaluated on the matched excerpts / whole text, with (role → severity 1-3, message, ask)
RED_FLAGS: list[dict] = [
    {"rx": r"unlimited|without limit|no (?:cap|limit) on|shall be liable for all", "roles": {"customer": 3, "vendor": 3}, "msg": "language suggesting unlimited liability", "ask": "mutual cap at 12 months' fees with super-cap carve-outs for confidentiality, data and IP indemnity"},
    {"rx": r"automatically renew|auto-?renew|successive (?:renewal )?(?:terms?|periods?)", "roles": {"customer": 2, "vendor": 1}, "msg": "auto-renewal — check the notice window", "ask": "renewal only on written agreement, or notice window ≤ 30 days with a reminder obligation on the vendor"},
    {"rx": r"(?:at least|not less than|no less than|minimum of)\s+(?:ninety|one hundred twenty|one hundred eighty|9\d|1[0-9]\d|180)\s*(?:\(\d+\)\s*)?days?.{0,80}(?:notice|prior)", "roles": {"customer": 2}, "msg": "notice period of 90+ days", "ask": "30-60 days' notice"},
    {"rx": r"non-?compet\w*|shall not .{0,40}(?:develop|market|sell|offer) .{0,40}(?:compet|similar)", "roles": {"customer": 3, "vendor": 2}, "msg": "non-compete / restriction on competing products", "ask": "delete; a commercial contract should not restrict what either party builds or buys"},
    {"rx": r"exclusiv(?:e|ity) (?:supplier|provider|partner|right)|sole (?:and exclusive )?(?:supplier|provider)|exclusively (?:from|through)", "roles": {"customer": 3, "vendor": 1}, "msg": "exclusivity obligation", "ask": "non-exclusive, or exclusivity limited in scope, territory and time with minimum-performance conditions"},
    {"rx": r"(?:fees|prices|rates) .{0,60}(?:may|will|shall) (?:be )?(?:increase|adjust|chang|modif)(?!.{0,120}(?:cpi|consumer price|\d{1,2}\s?%|percent))", "roles": {"customer": 2}, "msg": "price increases with no stated cap", "ask": "increases capped at the greater of CPI or 3-5% per year, on 60+ days' notice, at renewal only"},
    {"rx": r"(?:all|any|each) (?:deliverables?|work product|inventions?|developments?|improvements?|feedback|modifications?|derivative works?) .{0,80}(?:shall (?:be|become) (?:the )?(?:sole )?(?:and exclusive )?property|hereby assign|owned by)", "roles": {"vendor": 3, "customer": 1}, "msg": "broad assignment of deliverables/inventions/improvements", "ask": "assignment limited to deliverables specifically created for and paid for; you retain pre-existing IP, tools and general know-how with a licence-back"},
    {"rx": r"work (?:made )?for hire", "roles": {"vendor": 2}, "msg": "work-for-hire designation", "ask": "assignment conditioned on full payment; carve out pre-existing materials"},
    {"rx": r"terminat\w+ .{0,60}(?:immediately|at any time|for any reason|without (?:cause|notice))(?!.{0,80}(?:either party|both parties|each party))", "roles": {"customer": 2, "vendor": 2}, "msg": "one-sided immediate/any-reason termination right", "ask": "mutual termination for convenience on 30-90 days' notice, with pro-rata refund of prepaid fees"},
    {"rx": r"cure\w*[^.;]{0,40}?within\s+(?:five|seven|ten|5|7|10)\s*(?:\(\d+\)\s*)?(?:business\s+)?days|within\s+(?:five|seven|ten|5|7|10)\s*(?:\(\d+\)\s*)?(?:business\s+)?days[^.;]{0,40}?(?:to )?cure", "roles": {"customer": 2, "vendor": 2}, "msg": "cure period of 10 days or less", "ask": "30-day cure period"},
    {"rx": r"net (?:sixty|ninety|60|90|120)\b|(?:pay|paid|payable|due)[^.;]{0,40}?within (?:sixty|ninety|60|90|120)\s*(?:\(\d+\)\s*)?days", "roles": {"vendor": 2}, "msg": "long payment terms (net 60+)", "ask": "net 30 with 1.5%/month late interest"},
    {"rx": r"pay(?:ment)?[- ]when[- ]paid|paid only (?:when|if|after) .{0,40}(?:receives|received) payment", "roles": {"vendor": 3}, "msg": "pay-when-paid — your payment depends on their customer paying", "ask": "delete; payment due on invoice regardless of their downstream receipts"},
    {"rx": r"may not assign|shall not assign|without (?:the )?prior written consent(?!.{0,60}(?:not (?:to )?be unreasonably withheld|not unreasonably))", "roles": {"customer": 1, "vendor": 1}, "msg": "assignment needs consent with no 'not unreasonably withheld' qualifier", "ask": "add 'not to be unreasonably withheld' and free assignment on change of control / to affiliates"},
    {"rx": r"(?:sole|absolute|complete) discretion", "roles": {"customer": 2, "vendor": 2}, "msg": "'sole discretion' standard for the other side's decisions", "ask": "'reasonable discretion' or objective criteria"},
    {"rx": r"binding arbitration|waive[sd]? .{0,30}(?:right to a )?jury|class action waiver", "roles": {"customer": 1, "vendor": 1}, "msg": "arbitration / jury or class-action waiver", "ask": "acceptable if mutual and venue is convenient; otherwise courts of your home jurisdiction"},
    {"rx": r"audit .{0,80}(?:at any time|without notice|unlimited|as often as)", "roles": {"customer": 2, "vendor": 2}, "msg": "broad audit right (any time / no notice)", "ask": "once per year, 30 days' notice, business hours, at auditor's cost unless underpayment > 5%"},
    {"rx": r"as is|as-is|without (?:any )?warrant(?:y|ies)|disclaims? all warranties", "roles": {"customer": 2}, "msg": "service provided 'as is' with warranties disclaimed", "ask": "warranty that the service performs materially per documentation, with a re-perform/refund remedy"},
    {"rx": r"liquidated damages|penalt(?:y|ies) of", "roles": {"customer": 2, "vendor": 2}, "msg": "liquidated damages / penalties", "ask": "delete or cap at a small percentage of the affected fees"},
    {"rx": r"(?:perpetual|irrevocable)(?:,| and)? .{0,20}licen[cs]e .{0,120}(?:feedback|suggestions|name|logo|marks)", "roles": {"customer": 1}, "msg": "perpetual licence to your feedback/name/marks", "ask": "limit to feedback only, or delete the marketing-use right"},
    {"rx": r"(?:perpetual|irrevocable)[^.]{0,80}licen[cs]e[^.]{0,80}(?:customer|client|licensee|your) (?:data|content)", "roles": {"customer": 3}, "msg": "perpetual, irrevocable licence to your data (survives termination; reaches beyond providing the service)", "ask": "licence to Customer Data limited to providing the Services during the Term; Customer owns Customer Data; aggregated data only if de-identified and not used to identify you"},
    {"rx": r"(?:provider|vendor|supplier|licensor|company) (?:owns|shall own|retains?)[^.]{0,200}(?:derived from|based on|generated from) (?:the )?(?:customer|client|licensee|your) (?:data|content)", "roles": {"customer": 2}, "msg": "vendor claims ownership of data derived from your data", "ask": "vendor may use only aggregated, de-identified statistics that cannot identify you or your customers; everything else derived from Customer Data belongs to you"},
    {"rx": r"(?:provider|vendor|supplier|licensor|company)\s+(?:may|reserves the right to|can)\s+(?:at any time\s+)?(?:change|increase|modify|adjust|revise)\s+(?:the\s+|its\s+)?(?:fees|prices|pricing|rates|subscription fees)(?![^.]{0,160}(?:cpi|consumer price|\d{1,2}\s?%|percent|upon renewal|at renewal|renewal term))", "roles": {"customer": 3, "vendor": 0}, "msg": "unilateral right to change fees mid-term with no cap", "ask": "fees fixed for the Initial Term; increases only at renewal, capped at the greater of CPI or 3-5%, on 60+ days' notice so you can non-renew"},
    {"rx": r"(?:customer|client|licensee|buyer)'?s? (?:obligations|liability|indemnit\w+)(?:[^.]|\.(?=\d)){0,120}(?:(?:are|is|shall) not (?:be )?subject to|excluded from|shall not apply to)[^.]{0,40}(?:any )?(?:limitation|cap)", "roles": {"customer": 3}, "msg": "your indemnity/liability is expressly carved out of the cap — uncapped exposure for you", "ask": "your indemnity capped at the same amount as the vendor's (or a mutual super-cap); only fraud / wilful misconduct uncapped"},
    {"rx": r"third[- ]party (?:beneficiar|rights)|benefit of any third", "roles": {"customer": 1, "vendor": 1}, "msg": "third-party beneficiary language — check who can enforce", "ask": "no third-party beneficiaries except affiliates named"},
]
ROLE_ALIASES = {"customer": "customer", "client": "customer", "buyer": "customer", "licensee": "customer", "vendor": "vendor", "supplier": "vendor", "provider": "vendor", "seller": "vendor", "contractor": "vendor", "licensor": "vendor", "freelancer": "vendor"}


def _norm(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace(" ", " "))



_VENDOR = r"(?:provider|vendor|supplier|licensor|company|contractor|seller)"
_CUSTOMER = r"(?:customer|client|licensee|buyer|subscriber)"
_CAP_RX = re.compile(
    rf"(?P<who>(?:(?:either|each|neither) party|the parties|{_VENDOR}|{_CUSTOMER})(?:'s|’s|s')?)\s+(?:(?:total|aggregate|cumulative|entire|maximum)\s+(?:and\s+\w+\s+)?)*liability"
    r"(?P<mid>[^.]{0,200}?)(?:(?:shall|will|may|does)\s+not\s+exceed|(?:is|are|shall be|will be)\s+limited\s+to|capped\s+at)(?P<what>[^.]{0,220})",
    re.I,
)
_TFC_RX = re.compile(rf"(?P<who>either party|each party|{_VENDOR}|{_CUSTOMER})\s+may\s+(?:at any time\s+)?terminate[^.]{{0,100}}?(?:for convenience|without cause|for any reason|for no reason|at any time)", re.I)
_LOCKIN_RX = re.compile(rf"{_CUSTOMER}\s+(?:shall|will)\s+have\s+no\s+right\s+to\s+terminate|non-?cancell?able", re.I)
_OWN_DATA_RX = re.compile(rf"{_CUSTOMER}\s+(?:owns|shall own|will own|retains|shall retain|will retain)[^.]{{0,80}}(?:data|content|right, title)|as between the parties,? {_CUSTOMER}[^.]{{0,60}}own|(?:customer|client) data (?:is|remains|shall remain|will remain) (?:the )?(?:sole |exclusive )?property of", re.I)
_GL_RX = re.compile(r"(?:governed by|governing law)[^.]{0,60}?laws? of (?:the )?(?:state of |commonwealth of |province of |republic of )?(?P<j>[a-z][a-z]+(?: (?!without|and|excluding|applicable|in|to|as|that|which|except)[a-z]+){0,2})", re.I)
_VENUE_RX = re.compile(r"courts?\s+(?:(?:located|sitting|situated)\s+)?in\s+(?P<v>[A-Z][\w.-]*(?:,?\s+[A-Z][\w.-]*){0,4})")


def _structural_flags(text: str, role: str, my_jurisdiction: str) -> tuple[list[dict], dict]:
    """Checks that need more than one regex: cap size and mutuality, termination symmetry, data ownership, forum."""
    flags: list[dict] = []
    facts: dict = {"liability_cap": None, "governing_law": None, "venue": None}

    def add(sev: int, msg: str, m, ask: str) -> None:
        if sev:
            flags.append({"severity": sev, "flag": msg, "excerpt": excerpt(text, m) if m is not None else None, "ask_for": ask})

    cust_ind = re.search(rf"{_CUSTOMER}\s+(?:shall|agrees to|will)\s+(?:defend,?\s+(?:and\s+)?)?indemnif", text, re.I)
    vend_ind = re.search(rf"{_VENDOR}\s+(?:shall|agrees to|will)\s+(?:defend|indemnif)", text, re.I)
    if cust_ind and not vend_ind:
        add({"customer": 3, "vendor": 0}[role], "one-way (or lopsided) indemnity running from you to the vendor", cust_ind, "mutual indemnity: vendor covers IP infringement and data breach; you cover misuse and your content")
    elif vend_ind and not cust_ind:
        add({"customer": 0, "vendor": 2}[role], "one-way indemnity running from you to the customer", vend_ind, "mutual indemnity limited to third-party claims, with the cap applying except for IP")
    cap = _CAP_RX.search(text)
    if cap:
        who = cap.group("who").lower()
        mutual = bool(re.search(r"either|each|neither|parties", who))
        capped = "both" if mutual else ("vendor" if re.match(_VENDOR, who, re.I) else "customer")
        what = cap.group("what")
        months = None
        mm = re.search(r"\b([a-z]+|\d{1,3})\s*(?:\((\d{1,3})\)\s*)?[\s-]*months?\b", what, re.I)
        if mm:
            months = int(mm.group(2)) if mm.group(2) else parse_number(mm.group(1))
        elif re.search(r"(?:twelve|12)\s*(?:\(\d+\)\s*)?-?\s*month|one year|1 year|annual fees", what, re.I):
            months = 12
        fixed = re.search(r"\$\s?([\d,]{3,})", what)
        facts["liability_cap"] = {"capped_party": capped, "mutual": mutual, "months_of_fees": months, "fixed_amount": float(fixed.group(1).replace(",", "")) if fixed and months is None else None, "excerpt": excerpt(text, cap)}
        if capped == "vendor":
            add({"customer": 3, "vendor": 0}[role], "liability cap protects only the vendor — your own liability (incl. indemnities) is uncapped", cap, "mutual cap: 'each party's aggregate liability shall not exceed…'")
        elif capped == "customer":
            add({"customer": 0, "vendor": 3}[role], "liability cap protects only the customer — your liability as vendor is uncapped", cap, "mutual cap at 12 months' fees")
        if months is not None and months < 12 and capped in ("vendor", "both") and role == "customer":
            add(3 if months <= 3 else 2, f"liability cap = {months} month(s) of fees — market is 12 months", cap, "cap at 12 months' fees (fees paid or payable in the 12 months before the claim), with a 2-3× super-cap for data breach, confidentiality and IP indemnity")
    whos = [m.group("who").lower() for m in _TFC_RX.finditer(text)]
    tfc = _TFC_RX.search(text)
    if whos and not any(w in ("either party", "each party") for w in whos):
        vendor_can = any(re.fullmatch(_VENDOR, w, re.I) for w in whos)
        cust_can = any(re.fullmatch(_CUSTOMER, w, re.I) for w in whos)
        lock = _LOCKIN_RX.search(text)
        if vendor_can and not cust_can and role == "customer":
            add(3 if lock else 2, "only the vendor may terminate for convenience" + (" — you are locked in and fees are non-cancellable" if lock else ""), tfc, "mutual termination for convenience on 30-90 days' notice, or delete the vendor's right; if the vendor terminates for convenience, pro-rata refund of prepaid fees plus transition assistance")
        elif cust_can and not vendor_can and role == "vendor":
            add(2, "only the customer may terminate for convenience", tfc, "mutual termination for convenience, or a minimum commitment / early-termination fee")
    if role == "customer" and re.search(r"(?:customer|client|your) (?:data|content)", text, re.I) and not _OWN_DATA_RX.search(text):
        add(2, "no statement that you own your data — ownership of Customer Data is ambiguous", None, "add: 'As between the parties, Customer owns all right, title and interest in Customer Data'; vendor licence limited to providing the Services")
    gl = _GL_RX.search(text)
    ven = _VENUE_RX.search(text)
    facts["governing_law"] = gl.group("j").strip().title() if gl else None
    facts["venue"] = ven.group("v").strip() if ven else None
    mj = str(my_jurisdiction or "").strip().lower()
    if mj and (gl or ven):
        forum = " ".join(x for x in (facts["governing_law"], facts["venue"]) if x).lower()
        if mj not in forum:
            add(2, f"governing law / venue is {facts['governing_law'] or '?'}{' — courts in ' + facts['venue'] if facts['venue'] else ''}, not your home jurisdiction ({my_jurisdiction.strip()})", gl or ven, f"your home courts ({my_jurisdiction.strip()}), the defendant's home courts, or a neutral forum; at minimum non-exclusive jurisdiction")
    return flags, facts

@AGENT.tool
def detect_clauses(contract_text: str, my_role: str = "customer", my_jurisdiction: str = "") -> dict:
    """Detect 26 clause types in a contract, quote each, and score red flags from your side (customer or vendor).

    Missing protective clauses are flagged too (no liability cap = uncapped). Also reads the liability
    cap (who is capped, months of fees / fixed amount), one-sided termination-for-convenience, data
    ownership, and governing law/venue vs your home jurisdiction. Score 0-100: under 25 is routine
    paper, 25-50 negotiate, over 50 do not sign as-is.

    Args:
        contract_text: The full contract text (plain text; up to 300k chars).
        my_role: "customer" (buyer/licensee/client) or "vendor" (supplier/provider/contractor).
        my_jurisdiction: Your home state/country, e.g. "Oregon" — flags governing law or venue elsewhere (optional).
    """
    text = _norm(check_text(contract_text, "contract_text"))
    role = ROLE_ALIASES.get(str(my_role).strip().lower())
    if not role:
        raise ToolError("my_role must be 'customer' or 'vendor' (or client/buyer/licensee, supplier/provider/contractor).")
    found, missing = [], []
    for c in CLAUSES:
        m = re.search(c["rx"], text, re.I | re.S)
        if m:
            found.append({"clause": c["label"], "key": c["key"], "excerpt": excerpt(text, m), "position_pct": round(100 * m.start() / len(text))})
        elif c["missing_flag"]:
            missing.append({"clause": c["label"], "key": c["key"], "flag": c["missing_flag"]})
    flags, score = [], 0
    structural, facts = _structural_flags(text, role, my_jurisdiction)
    skip = {"one-sided immediate/any-reason termination right"} if any("terminate for convenience" in f["flag"] for f in structural) else set()
    for rf in RED_FLAGS:
        sev = rf["roles"].get(role)
        if not sev or rf["msg"] in skip:
            continue
        m = re.search(rf["rx"], text, re.I | re.S)
        if m:
            flags.append({"severity": sev, "flag": rf["msg"], "excerpt": excerpt(text, m), "ask_for": rf["ask"]})
            score += {1: 5, 2: 10, 3: 20}[sev]
    for f in structural:
        flags.append(f)
        score += {1: 5, 2: 10, 3: 20}[f["severity"]]
    if not any(f["flag"] == "notice period of 90+ days" for f in flags):
        for f in flags:  # auto-renewal with a market notice window (<= 60-89 days) is a calendar item, not a negotiation point
            if f["flag"].startswith("auto-renewal") and f["severity"] == 2:
                f["severity"], f["flag"] = 1, "auto-renewal with a market-length notice window — put the notice deadline in the calendar"
                score -= 5
    for mflag in missing:
        sev = 3 if mflag["key"] in ("limitation_of_liability",) else 2 if mflag["key"] in ("indemnity", "ip_ownership", "term", "governing_law", "data_protection", "termination_convenience") else 1
        flags.append({"severity": sev, "flag": "MISSING: " + mflag["flag"], "excerpt": None, "ask_for": f"add a {mflag['clause'].lower()} clause on market-standard terms"})
        score += {1: 3, 2: 6, 3: 12}[sev]
    flags.sort(key=lambda f: -f["severity"])
    score = min(100, score)
    verdict = "Routine — sign after confirming key dates" if score < 25 else "Negotiate the flagged points" if score < 50 else "Do not sign as-is — deal-breakers present"
    return {
        "role": role,
        "clauses_found": found,
        "clauses_missing": missing,
        "red_flags": flags,
        "risk_score": score,
        "deal_breakers": [f["flag"] for f in flags if f["severity"] == 3],
        "verdict": verdict,
        "liability_cap": facts["liability_cap"],
        "governing_law": facts["governing_law"],
        "venue": facts["venue"],
        "words": len(text.split()),
        "scope_note": SCOPE_NOTE,
    }


_DEADLINE_CTX = re.compile(rf"(?P<before>[^.;\n]{{0,120}}?\b(?:within|no later than|not later than|at least|not less than|no less than|prior to|before|after|following|upon|net|for a period of|term of|minimum of)\b[^.;\n]{{0,40}}?)?(?P<dur>{DURATION_RE.pattern})(?P<after>[^.;\n]{{0,100}})", re.I)
_EXPLICIT_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b|\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b|\b(\d{1,2}/\d{1,2}/\d{4})\b", re.I)
_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}


def _classify_ctx(ctx: str) -> str:
    c = ctx.lower()
    if re.search(r"cure|remedy", c):
        return "cure period"
    if re.search(r"surviv", c):
        return "confidentiality / survival"
    if re.search(r"export|retriev|make .{0,40}available|return .{0,20}data", c):
        return "post-termination (data export / return)"
    if re.search(r"notice|notify|terminat|non-?renew|cancel", c):
        return "notice / termination"
    if re.search(r"invoice|pay|net\b|fees|due", c):
        return "payment"
    if re.search(r"renew", c):
        return "renewal"
    if re.search(r"term of|initial term|commenc|period of|expire", c):
        return "term"
    if re.search(r"deliver|complete|milestone|respond|response", c):
        return "delivery / performance"
    if re.search(r"return|destroy|confiden|surviv", c):
        return "confidentiality / survival"
    if re.search(r"warrant|defect|claim|dispute", c):
        return "warranty / claims"
    return "other"


def _classify(before: str, dur_after: str) -> str:
    """Classify by the words *before* the duration first (they carry the trigger), then what follows."""
    if re.search(r"initial term|term of (?:this|the)|for a period of|commenc\w+ on", before[-60:], re.I):
        return "term"
    if re.search(r"successive|renewal (?:term|period)|renew(?:al|s)? for", before[-40:] + " " + dur_after[:40], re.I):
        return "renewal"
    for ctx in (before, dur_after):
        t = _classify_ctx(ctx)
        if t != "other":
            return t
    return "other"


def _anchor(pre: str, after: str, typ: str) -> str:
    """What a duration counts from. Only 'effective date' / 'term' durations can be resolved from the effective date."""
    a, b = after[:90].lower(), pre[-80:].lower()
    if re.search(r"(?:prior to|before) (?:the )?(?:end|expir|renewal)", a):
        return "before end of term"
    if re.search(r"(?:after|following|of|from) (?:the )?(?:date of )?(?:termination|expiration|expiry)", a) or re.search(r"(?:upon|after|following) (?:termination|expiration)", b):
        return "after termination / expiry"
    if re.search(r"(?:of|after|from|following) (?:the |receipt of (?:the |an )?)?(?:invoice|date of invoice)", a):
        return "from invoice date"
    if re.search(r"(?:after|following|of) (?:receiving |receipt of |the date of )?(?:such |written |the )?notice|notice (?:to|from)|'?s?\s+(?:prior\s+)?(?:written\s+)?notice", a):
        return "from notice"
    if re.search(r"after the end of|after the close of|preceding", a):
        return "relative to another period (see context)"
    if typ in ("term", "renewal"):
        return "effective date" if typ == "term" else "start of each renewal"
    if re.search(r"effective date|commenc|signature|execution", a + " " + b):
        return "effective date"
    return "triggering event in context"


@AGENT.tool
def extract_deadlines(contract_text: str, effective_date: str = "") -> dict:
    """Extract every duration ("within thirty (30) days"), notice period and explicit date, resolved to calendar dates.

    Args:
        contract_text: The full contract text.
        effective_date: YYYY-MM-DD the agreement takes effect; when given, durations are resolved to dates.
    """
    # PDFs paste with line breaks mid-sentence; collapse them so context windows span the whole clause
    text = re.sub(r"\s*\n\s*", " ", _norm(check_text(contract_text, "contract_text")))
    base = parse_date(effective_date, "effective_date") if effective_date else None
    items, seen = [], set()
    for m in _DEADLINE_CTX.finditer(text):
        before, dur, after = m.group("before") or "", m.group("dur"), m.group("after") or ""
        # classify on the whole clause up to the duration, not only the matched trigger word
        pre = re.split(r"(?<=[a-z0-9)\"])\.\s|;", text[max(0, m.start("dur") - 160) : m.start("dur")])[-1]
        dm = DURATION_RE.search(dur)
        if not dm:
            continue
        n = parse_number(dm.group(1))
        if n is None:
            continue
        business = bool(dm.group(2) and "business" in dm.group(2).lower() or dm.group(2) and "working" in dm.group(2).lower())
        unit = dm.group(3)
        ctx = re.sub(r"\s+", " ", (before + dur + after)).strip()
        key = (n, unit.lower().rstrip("s"), ctx[:60].lower())
        if key in seen:
            continue
        seen.add(key)
        days = duration_days(n, unit, business)
        typ = _classify(pre or before, dur + after)
        anchor = _anchor(pre or before, after, typ)
        resolved = None
        u = unit.lower()
        if base and anchor == "effective date":
            if typ == "term" and (u.startswith("month") or u.startswith("year")):
                resolved = _term_end(base, n if u.startswith("month") else 12 * n).isoformat()  # last day of the term
            elif business and u.startswith("day"):
                resolved = dates.add_business_days(base, n).isoformat()
            elif u.startswith("month"):
                resolved = add_months(base, n).isoformat()
            elif u.startswith("year"):
                resolved = add_months(base, 12 * n).isoformat()
            else:
                resolved = (base + timedelta(days=days)).isoformat()
        items.append({"duration": f"{n} {'business ' if business else ''}{u.rstrip('s')}{'s' if n != 1 else ''}", "days": days, "type": typ, "counts_from": anchor, "context": ctx[:220], "from_effective_date": resolved})
    # a notice window "N days prior to the end of the term" resolves against the initial term end, not the effective date
    term_item = next((i for i in items if i["type"] == "term" and i["from_effective_date"]), None)
    for i in items:
        if i["counts_from"] == "before end of term" and term_item and not i["duration"].split()[1].startswith(("month", "year", "business")):
            i["deadline_in_initial_term"] = (dates.parse_date(term_item["from_effective_date"]) - timedelta(days=i["days"])).isoformat()
    explicit = []
    for m in _EXPLICIT_DATE.finditer(text):
        raw = m.group(0)
        iso = None
        try:
            if m.group(1):
                iso = dates.parse_date(m.group(1)).isoformat()
            elif m.group(2):
                mo, d, y = re.match(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", m.group(2), re.I).groups()
                iso = f"{int(y):04d}-{_MONTHS[mo.lower()]:02d}-{int(d):02d}"
            elif m.group(3):
                a, b, y = m.group(3).split("/")
                iso = f"{int(y):04d}-{int(a):02d}-{int(b):02d}"
        except (ToolError, ValueError, AttributeError):
            iso = None
        explicit.append({"text": raw, "iso": iso, "context": excerpt(text, m, 120)})
    notice = [i for i in items if i["type"] == "notice / termination"]
    longest_notice = max((i["days"] for i in notice), default=None)
    return {
        "effective_date": base.isoformat() if base else None,
        "durations": items,
        "explicit_dates": explicit[:50],
        "notice_periods_days": sorted({i["days"] for i in notice}),
        "longest_notice_days": longest_notice,
        "auto_renewal_language": bool(re.search(r"automatically renew|auto-?renew|successive (?:renewal )?(?:terms?|periods?)|evergreen", text, re.I)),
        "initial_term_ends": term_item["from_effective_date"] if term_item else None,
        "summary": f"{len(items)} duration(s), {len(explicit)} explicit date(s)" + (f"; longest notice period {longest_notice} days" if longest_notice else "") + ("; auto-renewal present — run contract_reviewer__renewal_calendar" if re.search(r"auto-?renew|automatically renew", text, re.I) else ""),
        "how_to_read": "from_effective_date is filled only for durations that run from the Effective Date (the term shows its last day). Other durations count from the event in counts_from (notice, invoice, termination) — they are not dates yet. Notice windows before the end of the term show deadline_in_initial_term; use renewal_calendar for later cycles.",
        "scope_note": SCOPE_NOTE,
    }


@AGENT.tool
def renewal_calendar(effective_date: str, initial_term_months: int, notice_days: int = 30, renewal_term_months: int = 12, auto_renews: bool = True, reminder_days_before_notice: int = 30, renewals_to_show: int = 3) -> dict:
    """Compute term end, last day to give non-renewal notice, reminder date, and upcoming renewal dates.

    Args:
        effective_date: YYYY-MM-DD the term starts.
        initial_term_months: Length of the initial term in months.
        notice_days: Days before term end by which non-renewal notice must be received (default 30).
        renewal_term_months: Length of each renewal term (default 12).
        auto_renews: Whether the contract auto-renews (default true).
        reminder_days_before_notice: How many days before the notice deadline to set a reminder (default 30).
        renewals_to_show: How many future renewal cycles to list (default 3, max 10).
    """
    start = parse_date(effective_date, "effective_date")
    for name, v, lo, hi in (("initial_term_months", initial_term_months, 1, 240), ("notice_days", notice_days, 0, 365), ("renewal_term_months", renewal_term_months, 1, 240), ("reminder_days_before_notice", reminder_days_before_notice, 0, 180), ("renewals_to_show", renewals_to_show, 0, 10)):
        if not isinstance(v, int) or not lo <= v <= hi:
            raise ToolError(f"{name} must be an integer between {lo} and {hi}.")
    term_end = _term_end(start, initial_term_months)
    notice_deadline = term_end - timedelta(days=notice_days)
    reminder = notice_deadline - timedelta(days=reminder_days_before_notice)
    today = dates.date.today()
    cycles = []
    if auto_renews:
        cur_start, cur_end = start, term_end
        for i in range(renewals_to_show):
            nxt_start = cur_end + timedelta(days=1)
            nxt_end = _term_end(nxt_start, renewal_term_months)
            cycles.append({"renewal": i + 1, "starts": nxt_start.isoformat(), "ends": nxt_end.isoformat(), "notice_deadline": (nxt_end - timedelta(days=notice_days)).isoformat()})
            cur_start, cur_end = nxt_start, nxt_end
    days_to_notice = (notice_deadline - today).days
    status = "notice deadline has passed — contract will renew unless the other side agrees otherwise" if days_to_notice < 0 else f"{days_to_notice} days until the notice deadline"
    return {
        "effective_date": start.isoformat(),
        "initial_term_end": dates.fmt(term_end),
        "notice_deadline": dates.fmt(notice_deadline),
        "reminder_date": dates.fmt(reminder),
        "days_until_notice_deadline": days_to_notice,
        "auto_renews": auto_renews,
        "renewal_cycles": cycles,
        "calendar_entries": [
            {"title": "Reminder: decide on renewal", "date": reminder.isoformat()},
            {"title": f"LAST DAY to send non-renewal notice ({notice_days}d before term end)", "date": notice_deadline.isoformat()},
            {"title": "Contract term ends" + (" (auto-renews)" if auto_renews else ""), "date": term_end.isoformat()},
        ],
        "weekend_note": (f"The notice deadline falls on a {notice_deadline.strftime('%A')} — send notice by {(notice_deadline - timedelta(days=notice_deadline.weekday() - 4)).isoformat()} (the Friday before) so it is received in time." if notice_deadline.weekday() >= 5 else None),
        "verdict": f"Term ends {term_end.isoformat()}; notice must be received by {notice_deadline.isoformat()} — {status}.",
        "scope_note": SCOPE_NOTE,
    }


@AGENT.tool
def liability_exposure(annual_contract_value: float, cap_type: str = "months_of_fees", cap_value: float = 12, carve_outs: list[str] | None = None, consequential_excluded: bool = True, mutual: bool = True, term_years: float = 1) -> dict:
    """Quantify a liability cap in dollars, compare to market norms, and state the uncapped exposure.

    Args:
        annual_contract_value: Fees per year under the contract (dollars).
        cap_type: "months_of_fees" (cap = N months of fees), "multiple_of_fees" (N × annual fees), "fixed" (dollars), or "uncapped".
        cap_value: The N or dollar amount for the cap type (ignored for "uncapped").
        carve_outs: Items excluded from the cap, e.g. ["confidentiality", "data breach", "IP indemnity", "gross negligence", "payment obligations"].
        consequential_excluded: Whether indirect/consequential damages are excluded (default true).
        mutual: Whether the cap applies to both parties equally (default true).
        term_years: Contract length in years, for total-contract-value context (default 1).
    """
    acv = to_float(annual_contract_value, "annual_contract_value", 0)
    ct = str(cap_type).strip().lower()
    if ct not in {"months_of_fees", "multiple_of_fees", "fixed", "uncapped"}:
        raise ToolError("cap_type must be months_of_fees, multiple_of_fees, fixed or uncapped.")
    cv = to_float(cap_value, "cap_value", 0)
    ty = to_float(term_years, "term_years", 0.1, 30)
    carve = [str(c).strip().lower() for c in (carve_outs or []) if str(c).strip()]
    if ct == "months_of_fees":
        cap = acv * cv / 12
        cap_desc = f"{cv:g} month{'' if cv == 1 else 's'} of fees"
    elif ct == "multiple_of_fees":
        cap = acv * cv
        cap_desc = f"{cv:g}× annual fees"
    elif ct == "fixed":
        cap = cv
        cap_desc = f"fixed {money(cv)}"
    else:
        cap = None
        cap_desc = "uncapped"
    tcv = acv * ty
    market_cap = acv  # 12 months' fees
    standard_carve = {"confidentiality", "data breach", "data protection", "ip indemnity", "indemnity", "gross negligence", "wilful misconduct", "willful misconduct", "fraud", "payment obligations", "breach of confidentiality"}
    findings, position = [], "market"
    if cap is None:
        findings.append("Liability is uncapped — exposure is unlimited for the capped party; market is a cap at 12 months' fees")
        position = "off-market (uncapped)"
    else:
        ratio_to_market = cap / market_cap if market_cap else 0
        if ratio_to_market < 0.5:
            findings.append(f"Cap of {money(cap)} ({cap_desc}) is under half the market norm of 12 months' fees ({money(market_cap)})")
            position = "below market (favours the party being sued)"
        elif ratio_to_market > 3:
            findings.append(f"Cap of {money(cap)} ({cap_desc}) is over 3× the market norm — generous; check it is mutual")
            position = "above market"
    if not consequential_excluded:
        findings.append("Consequential/indirect damages are not excluded — lost-profit claims can exceed the cap in practice")
    if not mutual:
        findings.append("Cap is not mutual — one party is capped and the other is not")
    if not carve:
        findings.append("No carve-outs listed — unusual; most deals carve out confidentiality, data breach, IP indemnity and gross negligence/fraud (often with a super-cap)")
    unusual = [c for c in carve if not any(s in c for s in standard_carve)]
    if unusual:
        findings.append(f"Unusual carve-outs (uncapped): {', '.join(unusual)} — ask for a super-cap (2-3× fees) instead of unlimited")
    uncapped_exposure = ("everything" if cap is None else (", ".join(carve) if carve else "nothing beyond the cap"))
    if not mutual and cap is not None:
        uncapped_exposure = "the non-capped party's entire liability, including its indemnities (if that is you: everything)" + (f"; plus carve-outs: {', '.join(carve)}" if carve else "")
    return {
        "annual_contract_value": acv,
        "total_contract_value": round(tcv),
        "cap_dollars": None if cap is None else round(cap),
        "cap_description": cap_desc,
        "cap_pct_of_total_contract_value": None if cap is None or not tcv else round(100 * cap / tcv, 1),
        "market_reference_cap": round(market_cap),
        "market_position": position,
        "carve_outs": carve,
        "uncapped_exposure": uncapped_exposure,
        "findings": findings,
        "ask_for": "Mutual cap at 12 months' fees; consequential damages excluded; super-cap (2-3× fees) for confidentiality/data/IP; unlimited only for fraud and wilful misconduct.",
        "verdict": findings[0] if findings else f"Cap of {money(cap)} ({cap_desc}) is within market norms",
        "scope_note": SCOPE_NOTE,
    }
