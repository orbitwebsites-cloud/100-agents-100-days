"""NDA Drafter — market-standard mutual/one-way NDAs, term math, and a clause-level check of NDAs you receive."""

from __future__ import annotations

import re
from datetime import timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import SCOPE_NOTE, check_text, excerpt, parse_date
from ._common import term_end as _term_end

AGENT = Agent(
    slug="nda-drafter",
    name="NDA Drafter",
    category="legal",
    tagline="Draft a market-standard NDA in minutes, get every date right, and spot the traps in the one they sent you.",
    description=(
        "Drafts mutual and one-way NDAs from a clause library that mirrors what experienced tech lawyers "
        "actually sign (standard exclusions, compelled-disclosure carve-out, no-licence, return/destroy, "
        "injunctive relief, survival for trade secrets), computes every date (term, survival, return "
        "deadline), and reviews incoming NDAs clause-by-clause against market positions from your side of "
        "the table — flagging residuals clauses, non-solicits, one-way obligations dressed as mutual, "
        "perpetual terms and missing exclusions, with fallback language. Drafting aid, not legal advice."
    ),
    triggers=[
        "draft an NDA / non-disclosure agreement / confidentiality agreement",
        "mutual vs one-way NDA — which do I need",
        "review this NDA before I sign it",
        "how long should the confidentiality term be",
        "NDA for a contractor / investor / vendor / partnership",
        "is a residuals clause or non-solicit normal in an NDA",
    ],
    examples=[
        "Draft a mutual NDA between Acme Inc (Delaware) and Beta Ltd (England) for evaluating a partnership; 2-year term.",
        "A prospective customer sent us their NDA — we're the disclosing party. Anything I should push back on?",
        "We're hiring a freelance designer who'll see unreleased product. One-way NDA, please, governed by California law.",
    ],
    connectors=["Google Docs", "DocuSign", "Notion", "Gmail", "PandaDoc"],
    playbook="""
    ## Standard
    You are a commercial lawyer who has drafted and negotiated hundreds of NDAs. Excellent work is
    fast (an NDA should never hold up a deal), balanced (a mutual NDA that is secretly one-way gets
    caught and costs trust), and precise about dates and definitions. The one metric that matters
    is **signed without a second round of redlines** — market-standard terms, nothing exotic, no
    trap for either side.

    **Scope note (include once in every output):** this is a drafting aid, not legal advice.
    Enforceability of confidentiality, non-solicit and choice-of-law terms varies by jurisdiction;
    have a licensed lawyer review NDAs tied to M&A, fundraising, employment, or regulated data.

    ## Intake
    Proceed with what you have. Ask (max 3) only if you cannot infer: (1) who discloses — one side
    or both (mutual vs one-way), (2) the purpose (evaluation of a deal, services, investment,
    employment), (3) governing law / the parties' locations. Defaults if unstated: mutual, 2-year
    term, 3-year survival (perpetual for trade secrets), governing law = the drafting party's home
    jurisdiction — state the defaults as assumptions.

    ## Procedure
    1. **Decide the shape.** Mutual when both sides will share anything non-public (partnerships,
       M&A, most vendor evaluations). One-way when only one side discloses (contractor, candidate,
       investor pitch — though investors rarely sign NDAs; say so). If the user is the recipient
       only, a one-way in their favour is fine; if they will disclose too, insist on mutual.
    2. **Compute the dates.** Call `nda_drafter__calculate_terms` with the effective date, term,
       survival period and return/destroy window. It returns the agreement expiry, the date
       confidentiality obligations end for ordinary information, the trade-secret note (perpetual
       while it remains a trade secret), the return/destroy deadline after termination, and the
       disclosure cut-off. Never compute these in your head.
    3. **Draft.** Call `nda_drafter__build_nda` with parties, purpose, type, dates, governing law
       and options (non-solicit, residuals, marking requirement, injunctive relief, no-licence,
       feedback clause). It assembles numbered clauses from the market-standard library with defined
       terms, the five standard exclusions, the compelled-disclosure procedure, and a list of every
       [BRACKETED] item the user must confirm. Review the output for fit; do not rewrite clauses the
       tool produced unless the deal needs it — consistency is a feature.
    4. **If reviewing an incoming NDA,** call `nda_drafter__review_nda` with the text and the user's
       role (discloser / recipient / both). It checks for: the standard exclusions (public, already
       known, independently developed, third-party source, compelled by law), definition breadth
       (all information vs marked only), term and survival (flags perpetual for non-trade-secrets
       and < 1 year), residuals clauses (bad for disclosers), non-solicit / non-compete (unusual in
       an NDA), one-way obligations in a "mutual" document, assignment, injunctive relief without
       bond, liquidated damages, governing law/venue, DTSA whistleblower notice (US, if individuals
       sign), and return/destroy. Each finding comes with market position and fallback.
    5. **Explain in plain English** what each party can and cannot do, in ≤ 6 bullets — the
       business owner will read that, not the clauses.
    6. **Deliver** in the output format. If DocuSign/PandaDoc/Docs is connected, create the
       document for signature; otherwise output ready to paste.

    ## Frameworks
    - **Market terms (tech/commercial):** term 1-3 years (evaluations) or 2-5 (partnerships);
      survival 2-5 years after expiry, perpetual for trade secrets; return/destroy within 30 days
      of request or termination, with one archival copy for legal/compliance; standard of care =
      reasonable care, no less than own information; disclosure to employees/advisors with a need to
      know who are bound by equivalent obligations.
    - **Five standard exclusions:** (a) public through no fault of recipient, (b) already known
      without restriction, (c) independently developed without use of the information, (d) received
      from a third party without restriction, (e) required by law/court (with prompt notice and
      cooperation, disclosing only what is required).
    - **Residuals clause:** lets the recipient use what stays in unaided memory. Fine for large
      vendors receiving lots of information; dangerous for a startup disclosing its core idea. As
      discloser: delete or limit to general skills/know-how excluding specifics.
    - **Non-solicit in an NDA:** unusual; if included, mutual, 12 months, carve out general
      advertising and unsolicited applications.
    - **DTSA notice (18 U.S.C. §1833(b)):** if any US individual signs, include the whistleblower
      immunity notice or lose exemplary damages/attorney fees against them.

    ## Output format
    ```
    # NDA — <Mutual/One-way> — <Party A> & <Party B> — effective <YYYY-MM-DD>
    **Key dates:** term ends <date> · obligations end <date> (trade secrets: perpetual) · return/destroy within <n> days
    **Scope note:** drafting aid, not legal advice; …

    ## In plain English
    - Both sides can share info for <purpose> only. …
    - Confidential = <everything disclosed / marked + reasonably understood>. …

    ## Items to confirm before sending
    - [GOVERNING LAW: Delaware] · [NOTICE ADDRESS: …] · …

    ## Agreement
    <numbered clauses from nda_drafter__build_nda>

    (For reviews instead:)
    ## Findings (from <role>'s side)
    | # | Clause | Issue | Severity | Market position | Ask / fallback |
    ```

    ## Anti-patterns
    - Perpetual confidentiality for everything. Courts in some jurisdictions void it; use perpetual for trade secrets only.
    - "All information disclosed" with no exclusions. Unenforceable and unfair — include the five.
    - A mutual title with recipient-only obligations in the body. Read every "Receiving Party".
    - Marking requirements as the only test. Oral disclosures get lost; use "marked or reasonably understood to be confidential".
    - Adding non-competes, exclusivity or IP assignment to an NDA. Those belong in the commercial agreement.
    - Investors and NDAs: VCs don't sign them; don't lose the meeting over it.
    """,
)


@AGENT.tool
def calculate_terms(effective_date: str, term_months: int = 24, survival_months: int = 36, return_within_days: int = 30, termination_notice_days: int = 30, trade_secrets_perpetual: bool = True) -> dict:
    """Compute the NDA's key dates: term end, confidentiality end for ordinary information, return/destroy and notice deadlines.

    Args:
        effective_date: YYYY-MM-DD the NDA takes effect.
        term_months: Disclosure period / agreement term in months (default 24).
        survival_months: How long obligations survive after the term ends (default 36); 0 means obligations end with the term.
        return_within_days: Days after termination/request to return or destroy materials (default 30).
        termination_notice_days: Notice needed to terminate early (default 30).
        trade_secrets_perpetual: Whether trade secrets stay protected while they remain trade secrets (default true, market standard).
    """
    start = parse_date(effective_date, "effective_date")
    for name, v, lo, hi in (("term_months", term_months, 1, 120), ("survival_months", survival_months, 0, 240), ("return_within_days", return_within_days, 1, 180), ("termination_notice_days", termination_notice_days, 0, 180)):
        if not isinstance(v, int) or not lo <= v <= hi:
            raise ToolError(f"{name} must be an integer between {lo} and {hi}.")
    term_end = _term_end(start, term_months)
    obligations_end = _term_end(term_end + timedelta(days=1), survival_months) if survival_months else term_end
    return_deadline = term_end + timedelta(days=return_within_days)
    early_term_earliest = start + timedelta(days=termination_notice_days)
    total_years = round((obligations_end - start).days / 365.25, 1)
    notes = []
    if total_years > 7 and survival_months:
        notes.append(f"Obligations run {total_years} years in total — longer than the usual 3-5; some courts read very long terms as unreasonable for non-trade-secret information")
    if survival_months and survival_months < 12:
        notes.append("Survival under 12 months is short for a discloser; 2-5 years is market")
    if not survival_months:
        notes.append("No survival: obligations end with the term — information disclosed on the last day is protected for zero days. Add survival.")
    return {
        "effective_date": start.isoformat(),
        "term_end": dates.fmt(term_end),
        "last_day_to_disclose_under_nda": dates.fmt(term_end),
        "obligations_end_ordinary_information": dates.fmt(obligations_end),
        "trade_secrets": "perpetual — for as long as the information qualifies as a trade secret under applicable law" if trade_secrets_perpetual else "same as ordinary information",
        "return_or_destroy_by": dates.fmt(return_deadline),
        "earliest_early_termination": dates.fmt(early_term_earliest),
        "total_protection_years": total_years,
        "calendar_entries": [
            {"title": "NDA term ends — stop disclosing under this NDA", "date": term_end.isoformat()},
            {"title": "Return/destroy Confidential Information deadline", "date": return_deadline.isoformat()},
            {"title": "Confidentiality obligations end (non-trade-secret info)", "date": obligations_end.isoformat()},
        ],
        "notes": notes,
        "verdict": f"Term ends {term_end.isoformat()}; obligations survive to {obligations_end.isoformat()}" + ("; trade secrets perpetual" if trade_secrets_perpetual else ""),
    }


def _party(p: dict, label: str) -> dict:
    if not isinstance(p, dict) or not str(p.get("name", "")).strip():
        raise ToolError(f"{label} must be an object with at least a 'name'.")
    return {
        "name": str(p["name"]).strip(),
        "entity": str(p.get("entity", "")).strip() or "[ENTITY TYPE, e.g. a Delaware corporation]",
        "address": str(p.get("address", "")).strip() or "[NOTICE ADDRESS]",
        "signatory": str(p.get("signatory", "")).strip() or "[NAME, TITLE]",
    }


@AGENT.tool
def build_nda(party_a: dict, party_b: dict, purpose: str, effective_date: str, mutual: bool = True, term_months: int = 24, survival_months: int = 36, governing_law: str = "", venue: str = "", return_within_days: int = 30, include_non_solicit: bool = False, include_residuals: bool = False, marking_required: bool = False, include_feedback_clause: bool = False, individuals_signing: bool = False) -> dict:
    """Assemble a complete, numbered NDA from a market-standard clause library with every open item bracketed.

    Args:
        party_a: {"name": str, "entity": "a Delaware corporation", "address": str, "signatory": "Name, Title"} — the disclosing party in a one-way NDA.
        party_b: Same shape — the receiving party in a one-way NDA.
        purpose: The permitted purpose, e.g. "evaluating a potential commercial partnership".
        effective_date: YYYY-MM-DD.
        mutual: True for a mutual NDA (default); False for one-way (party_a discloses to party_b).
        term_months: Agreement term in months (default 24).
        survival_months: Survival of obligations after the term (default 36).
        governing_law: e.g. "the State of Delaware" or "England and Wales". Bracketed if empty.
        venue: Courts with jurisdiction, e.g. "the state and federal courts located in Wilmington, Delaware". Defaults to the governing-law jurisdiction.
        return_within_days: Days to return/destroy on request or termination (default 30).
        include_non_solicit: Add a mutual 12-month employee non-solicit (default false; unusual in NDAs).
        include_residuals: Add a residuals clause (default false; favours recipients — disclosers should decline).
        marking_required: If true, only marked/designated information is confidential (default false: marked OR reasonably understood).
        include_feedback_clause: Add a clause letting the recipient use voluntarily provided feedback (default false).
        individuals_signing: True if a natural person in the US signs — adds the DTSA whistleblower notice.
    """
    a, b = _party(party_a, "party_a"), _party(party_b, "party_b")
    if not isinstance(purpose, str) or not purpose.strip():
        raise ToolError("purpose is required, e.g. 'evaluating a potential commercial relationship'.")
    start = parse_date(effective_date, "effective_date")
    for name, v, lo, hi in (("term_months", term_months, 1, 120), ("survival_months", survival_months, 0, 240), ("return_within_days", return_within_days, 1, 180)):
        if not isinstance(v, int) or not lo <= v <= hi:
            raise ToolError(f"{name} must be an integer between {lo} and {hi}.")
    law = governing_law.strip() or "[GOVERNING LAW JURISDICTION]"
    ven = venue.strip() or f"the courts of {law}"
    to_confirm = [x for x in [a["entity"], a["address"], a["signatory"], b["entity"], b["address"], b["signatory"]] if x.startswith("[")]
    if law.startswith("["):
        to_confirm.append(law)
    disc = "the Disclosing Party" if mutual else a["name"]
    recv = "the Receiving Party" if mutual else b["name"]
    conf_def = (
        f"all non-public information disclosed by {disc} to {recv}, whether before or after the Effective Date, in any form, that is marked or designated as confidential at the time of disclosure or, if disclosed orally or visually, is identified as confidential in writing within thirty (30) days"
        if marking_required
        else f"all non-public information disclosed by {disc} to {recv}, whether before or after the Effective Date, in any form, that is marked or designated as confidential or that a reasonable person would understand to be confidential given the nature of the information and the circumstances of disclosure, including business plans, product roadmaps, technical data, source code, customer and pricing information, and the existence and terms of the discussions between the parties"
    )
    n = [0]

    def clause(title: str, body: str) -> str:
        n[0] += 1
        return f"{n[0]}. **{title}.** {body}"

    survival_text = (
        f"The obligations in Sections 3 through 6 survive for {survival_months} months after expiry or termination of this Agreement"
        if survival_months
        else "The obligations in Sections 3 through 6 end on expiry or termination of this Agreement [CONFIRM — no survival is unusual]"
    )
    clauses = [
        f"**{'MUTUAL ' if mutual else ''}NON-DISCLOSURE AGREEMENT**\n\nThis {'Mutual ' if mutual else ''}Non-Disclosure Agreement (the \"Agreement\") is entered into as of {start.isoformat()} (the \"Effective Date\") between {a['name']}, {a['entity']}, with its notice address at {a['address']} (\"{a['name'] if not mutual else a['name']}\"), and {b['name']}, {b['entity']}, with its notice address at {b['address']} (\"{b['name']}\")"
        + (" (each a \"Party\" and together the \"Parties\"; a Party disclosing Confidential Information is the \"Disclosing Party\" and a Party receiving it is the \"Receiving Party\")." if mutual else "."),
        clause("Purpose", f"The Parties wish to exchange certain confidential information solely for the purpose of {purpose.strip().rstrip('.')} (the \"Purpose\")." if mutual else f"{a['name']} wishes to disclose certain confidential information to {b['name']} solely for the purpose of {purpose.strip().rstrip('.')} (the \"Purpose\")."),
        clause("Confidential Information", f"\"Confidential Information\" means {conf_def}. Confidential Information does not include information that {recv} can demonstrate by written records: (a) is or becomes publicly available through no breach of this Agreement; (b) was rightfully known to {recv} without restriction before disclosure; (c) is independently developed by {recv} without use of or reference to the Confidential Information; or (d) is rightfully received from a third party without a duty of confidentiality."),
        clause("Obligations", f"{recv} shall: (a) use the Confidential Information only for the Purpose; (b) not disclose it to any third party except to its employees, officers, professional advisers, and contractors who need to know it for the Purpose and are bound by written confidentiality obligations at least as protective as this Agreement (\"Representatives\"), and {recv} is responsible for its Representatives' compliance; (c) protect it using at least the same degree of care it uses for its own confidential information of similar nature, and no less than reasonable care; and (d) not reverse engineer, decompile or disassemble any software, prototypes or samples provided."),
        clause("Compelled Disclosure", f"If {recv} is required by law, regulation or court order to disclose Confidential Information, it shall (to the extent legally permitted) give {disc} prompt written notice, cooperate reasonably with any effort to seek a protective order at {disc}'s expense, and disclose only the portion legally required."),
        clause("Return or Destruction", f"Within {return_within_days} days after the earlier of {disc}'s written request or termination or expiry of this Agreement, {recv} shall return or destroy all Confidential Information and certify destruction in writing on request, except that {recv} may retain one archival copy solely for legal or compliance purposes and copies in routine backup systems, which remain subject to this Agreement."),
        clause("No Licence; No Warranty", f"All Confidential Information remains the property of {disc}. No licence or other right under any patent, copyright, trade secret or other intellectual property is granted except the limited right to use the Confidential Information for the Purpose. Confidential Information is provided \"AS IS\"; {disc} makes no warranty as to its accuracy or completeness."),
        clause("Term and Survival", f"This Agreement runs for {term_months} months from the Effective Date unless terminated earlier by either Party on thirty (30) days' written notice. {survival_text}; provided that obligations concerning any Confidential Information that constitutes a trade secret under applicable law continue for as long as it remains a trade secret."),
        clause("Remedies", f"{recv} acknowledges that unauthorised use or disclosure of Confidential Information may cause irreparable harm for which damages would be an inadequate remedy, and that {disc} is entitled to seek injunctive or other equitable relief, without the need to post a bond, in addition to any other remedies available at law."),
        clause("No Obligation to Proceed", "Nothing in this Agreement obliges either Party to disclose any particular information or to enter into any further agreement. Each Party remains free to develop, acquire or market products or services that compete with the other's, provided it does not use the other's Confidential Information in breach of this Agreement."),
    ]
    if include_residuals:
        clauses.append(clause("Residuals", f"{recv} may use Residuals for any purpose, provided it does not disclose the Confidential Information itself. \"Residuals\" means general skills, knowledge and experience retained in the unaided memory of {recv}'s personnel who had authorised access, excluding any information intentionally memorised for the purpose of retaining and later using it, and excluding any patent or copyright of {disc}. [DISCLOSER: consider deleting this clause — it is recipient-favourable]"))
    if include_non_solicit:
        clauses.append(clause("Non-Solicitation", "For twelve (12) months from the Effective Date, neither Party shall directly solicit for employment any employee of the other Party with whom it had contact in connection with the Purpose; general advertisements and unsolicited applications are not solicitation. [CONFIRM enforceability in the governing-law jurisdiction]"))
    if include_feedback_clause:
        clauses.append(clause("Feedback", f"If {recv} voluntarily provides suggestions or feedback about {disc}'s products or services, {disc} may use that feedback without restriction or compensation, provided that feedback does not include {recv}'s Confidential Information."))
    if individuals_signing:
        clauses.append(clause("Defend Trade Secrets Act Notice", "Under 18 U.S.C. §1833(b), an individual shall not be held criminally or civilly liable under any federal or state trade secret law for the disclosure of a trade secret that is made (i) in confidence to a federal, state or local government official or to an attorney solely for the purpose of reporting or investigating a suspected violation of law, or (ii) in a complaint or other document filed in a lawsuit or other proceeding, if such filing is made under seal."))
    clauses += [
        clause("Governing Law and Venue", f"This Agreement is governed by the laws of {law}, without regard to conflict-of-laws rules. The Parties submit to the exclusive jurisdiction of {ven}, except that either Party may seek injunctive relief in any court of competent jurisdiction."),
        clause("General", "This Agreement is the entire agreement between the Parties about its subject matter and supersedes all prior discussions. It may be amended only in a writing signed by both Parties. Neither Party may assign this Agreement without the other's prior written consent, not to be unreasonably withheld, except to a successor in a merger or sale of substantially all its assets. If any provision is unenforceable, the remainder stays in effect. Notices must be in writing to the addresses above (or by email with confirmation of receipt). This Agreement may be signed in counterparts and electronically."),
        f"**SIGNATURES**\n\n{a['name']}\nBy: ____________________  Name/Title: {a['signatory']}  Date: ________\n\n{b['name']}\nBy: ____________________  Name/Title: {b['signatory']}  Date: ________",
    ]
    text = "\n\n".join(clauses)
    brackets = sorted(set(re.findall(r"\[[^\]]+\]", text)))
    end = _term_end(start, term_months)
    return {
        "type": "mutual" if mutual else "one-way",
        "agreement_text": text,
        "clause_count": n[0],
        "words": len(text.split()),
        "to_confirm": brackets,
        "key_dates": {"effective": start.isoformat(), "term_end": end.isoformat(), "obligations_end": _term_end(end + timedelta(days=1), survival_months).isoformat() if survival_months else end.isoformat()},
        "options_applied": {"residuals": include_residuals, "non_solicit": include_non_solicit, "marking_required": marking_required, "feedback": include_feedback_clause, "dtsa_notice": individuals_signing},
        "plain_english": [
            f"{'Each side' if mutual else b['name']} may use what it learns only for: {purpose.strip()}.",
            "Confidential = " + ("only information marked confidential (or confirmed in writing within 30 days if oral)." if marking_required else "anything marked confidential or that a reasonable person would treat as confidential."),
            "Public, already-known, independently developed, or third-party-sourced information is not covered.",
            f"Obligations last {term_months} months plus {survival_months} months of survival; trade secrets stay protected as long as they are trade secrets.",
            f"Return or destroy materials within {return_within_days} days of a request or the end of the agreement (one archival copy allowed).",
            "No licence to anything; nobody is obliged to do a deal; either side can still build competing products without using the other's information.",
        ],
        "scope_note": SCOPE_NOTE,
    }


NDA_CHECKS: list[dict] = [
    {"key": "exclusion_public", "label": "Exclusion: publicly available", "rx": r"public(?:ly)? (?:available|known|domain)|becomes? (?:generally )?(?:available|known) to the public", "missing_sev": {"recipient": 3, "discloser": 1, "both": 2}, "market": "all five standard exclusions", "ask": "add: information that is or becomes public through no breach"},
    {"key": "exclusion_known", "label": "Exclusion: already known", "rx": r"(?:already|previously|rightfully) (?:known|in (?:its|the) possession)|known to .{0,40}(?:prior to|before) (?:disclosure|receipt)", "missing_sev": {"recipient": 3, "discloser": 1, "both": 2}, "market": "standard", "ask": "add: information rightfully known before disclosure"},
    {"key": "exclusion_independent", "label": "Exclusion: independently developed", "rx": r"independently developed|independent development", "missing_sev": {"recipient": 3, "discloser": 1, "both": 2}, "market": "standard", "ask": "add: independently developed without use of the Confidential Information"},
    {"key": "exclusion_third_party", "label": "Exclusion: received from third party", "rx": r"(?:received|obtained) from a third party|third party .{0,40}without (?:restriction|breach|obligation)", "missing_sev": {"recipient": 2, "discloser": 1, "both": 2}, "market": "standard", "ask": "add: rightfully received from a third party without restriction"},
    {"key": "compelled", "label": "Compelled disclosure carve-out (law / court order) with notice", "rx": r"required by law|court order|subpoena|compelled|legal process|governmental (?:authority|order)", "missing_sev": {"recipient": 3, "discloser": 1, "both": 2}, "market": "standard: notice, cooperate, disclose only what is required", "ask": "add compelled-disclosure clause with prompt notice and minimum disclosure"},
    {"key": "standard_of_care", "label": "Standard of care (reasonable care / same as own)", "rx": r"reasonable care|same degree of care|reasonable (?:measures|steps|precautions)|degree of care", "missing_sev": {"recipient": 1, "discloser": 2, "both": 2}, "market": "at least reasonable care and no less than own information", "ask": "add an objective standard of care"},
    {"key": "representatives", "label": "Disclosure to employees/advisers with need to know", "rx": r"need[- ]to[- ]know|representatives|employees,? (?:officers|agents|advis[eo]rs)|affiliates .{0,40}(?:bound|subject)", "missing_sev": {"recipient": 2, "discloser": 0, "both": 1}, "market": "need-to-know representatives bound by equivalent obligations", "ask": "add representatives clause"},
    {"key": "return_destroy", "label": "Return or destroy on request/termination", "rx": r"return(?:ed)? or destroy|destroy(?:ed)? or return|return .{0,40}confidential information|destruction", "missing_sev": {"recipient": 0, "discloser": 2, "both": 1}, "market": "within 30 days, with archival/backup exception", "ask": "add return/destroy with certification"},
    {"key": "term", "label": "Term / duration stated", "rx": r"term of (?:this )?agreement|for a period of|\d+ (?:\(\d+\) )?(?:years?|months?)|expire|anniversary", "missing_sev": {"recipient": 2, "discloser": 1, "both": 2}, "market": "1-5 years, survival 2-5 years", "ask": "add a term and survival period"},
    {"key": "no_licence", "label": "No licence / IP remains with discloser", "rx": r"no licen[cs]e|no (?:right|licence|license) .{0,40}(?:granted|conveyed)|remain(?:s)? the (?:sole )?property", "missing_sev": {"recipient": 0, "discloser": 2, "both": 1}, "market": "standard", "ask": "add: no licence granted; information remains discloser's property"},
    {"key": "injunctive", "label": "Injunctive / equitable relief", "rx": r"injunctive|equitable relief|irreparable (?:harm|injury)|specific performance", "missing_sev": {"recipient": 0, "discloser": 2, "both": 1}, "market": "standard; 'seek' rather than 'entitled to' if you are the recipient; no bond requirement is common", "ask": "add right to seek injunctive relief"},
    {"key": "governing_law", "label": "Governing law and venue", "rx": r"governed by|governing law|laws of|jurisdiction|venue", "missing_sev": {"recipient": 1, "discloser": 1, "both": 1}, "market": "home jurisdiction of the drafting party; neutral for cross-border", "ask": "add governing law and venue"},
]
NDA_RED_FLAGS: list[dict] = [
    {"rx": r"residual|unaided memory|retained in (?:the )?(?:memory|minds)", "sev": {"discloser": 3, "recipient": 0, "both": 2}, "flag": "Residuals clause — recipient may use whatever its people remember", "ask": "delete; or limit to general skills/know-how, exclude specifics and any IP, exclude intentionally memorised information"},
    {"rx": r"non-?solicit|solicit .{0,40}(?:employees|personnel|customers)", "sev": {"discloser": 1, "recipient": 2, "both": 2}, "flag": "Non-solicitation in an NDA", "ask": "delete (belongs in the commercial agreement); if kept: mutual, 12 months, carve out general advertising"},
    {"rx": r"non-?compet|shall not .{0,40}compet|refrain from (?:developing|marketing)", "sev": {"discloser": 1, "recipient": 3, "both": 3}, "flag": "Non-compete / restriction on competing", "ask": "delete — an NDA should not restrict what you build; add 'free to develop competing products without using Confidential Information'"},
    {"rx": r"perpetual|in perpetuity|indefinitely|no expiration|without limitation (?:as to|of) time|survive indefinitely", "sev": {"discloser": 0, "recipient": 2, "both": 1}, "flag": "Perpetual obligations for all information", "ask": "survival of 2-5 years for ordinary information; perpetual only for trade secrets"},
    {"rx": r"all information(?! .{0,80}(?:marked|designated|reasonably|confidential))|any and all information|regardless of whether .{0,40}(?:marked|confidential)", "sev": {"discloser": 0, "recipient": 2, "both": 1}, "flag": "Confidential Information defined as all information without limit", "ask": "'marked or reasonably understood to be confidential', with the five standard exclusions"},
    {"rx": r"liquidated damages|penalt(?:y|ies) of|shall pay .{0,40}(?:\$|usd|eur|£)\s?[\d,]+ (?:per|for each) (?:breach|disclosure)", "sev": {"discloser": 0, "recipient": 3, "both": 2}, "flag": "Liquidated damages / penalty for breach", "ask": "delete; actual damages plus injunctive relief is market"},
    {"rx": r"assign(?:ment|s)? .{0,60}(?:hereby|all rights|inventions|improvements|derivative)|work (?:made )?for hire|shall (?:own|be the owner of) .{0,40}(?:improvements|derivatives|developments)", "sev": {"discloser": 0, "recipient": 3, "both": 2}, "flag": "IP assignment / ownership of improvements inside an NDA", "ask": "delete; IP terms belong in the commercial agreement; NDA should say 'no licence granted' only"},
    {"rx": r"attorneys?'? fees|legal fees|costs of enforcement", "sev": {"discloser": 0, "recipient": 1, "both": 1}, "flag": "One-way attorneys' fees", "ask": "make it prevailing-party (mutual) or delete"},
    {"rx": r"(?:sole|absolute) discretion", "sev": {"discloser": 1, "recipient": 2, "both": 1}, "flag": "'Sole discretion' standard", "ask": "'reasonable' or objective test"},
    {"rx": r"indemnif|hold harmless", "sev": {"discloser": 0, "recipient": 2, "both": 2}, "flag": "Indemnity in an NDA", "ask": "delete; NDAs normally rely on damages and injunctive relief, not indemnities"},
    {"rx": r"(?:notify|notice) .{0,40}within (?:twenty-four|24|forty-eight|48) hours", "sev": {"discloser": 0, "recipient": 1, "both": 1}, "flag": "Breach notification within 24-48 hours", "ask": "'promptly' or within 5 business days of becoming aware"},
    {"rx": r"exclusiv(?:e|ity)|shall not .{0,40}(?:negotiate|discuss) with (?:any )?(?:other|third)", "sev": {"discloser": 1, "recipient": 2, "both": 2}, "flag": "Exclusivity / no-shop obligation", "ask": "delete or move to a separate, time-limited exclusivity letter"},
    {"rx": r"post(?:ing)? (?:a |of )?bond|security for", "sev": {"discloser": 1, "recipient": 0, "both": 0}, "flag": "Bond required before injunctive relief", "ask": "as discloser: 'without the need to post a bond'"},
]


@AGENT.tool
def review_nda(nda_text: str, my_role: str = "both") -> dict:
    """Review an incoming NDA clause-by-clause from your side: missing standard protections, red flags, market position, fallback language.

    Args:
        nda_text: The full NDA text (up to 300k chars).
        my_role: "discloser" (you share information), "recipient" (you receive it), or "both" (mutual exchange).
    """
    text = check_text(nda_text, "nda_text")
    role = str(my_role).strip().lower()
    role = {"disclosing": "discloser", "disclosing party": "discloser", "receiving": "recipient", "receiving party": "recipient", "mutual": "both"}.get(role, role)
    if role not in {"discloser", "recipient", "both"}:
        raise ToolError("my_role must be 'discloser', 'recipient' or 'both'.")
    lower = text.lower()
    title_mutual = bool(re.search(r"mutual", text[:600], re.I))
    findings, present, score = [], [], 0
    for c in NDA_CHECKS:
        m = re.search(c["rx"], text, re.I | re.S)
        if m:
            present.append({"check": c["label"], "excerpt": excerpt(text, m, 140)})
        else:
            sev = c["missing_sev"][role]
            if sev:
                findings.append({"severity": sev, "clause": c["label"], "issue": "MISSING", "market_position": c["market"], "ask": c["ask"]})
                score += {1: 4, 2: 8, 3: 15}[sev]
    for rf in NDA_RED_FLAGS:
        sev = rf["sev"][role]
        if not sev:
            continue
        m = re.search(rf["rx"], text, re.I | re.S)
        if m:
            findings.append({"severity": sev, "clause": rf["flag"], "issue": excerpt(text, m, 160), "market_position": "unusual / off-market" if sev >= 2 else "negotiable", "ask": rf["ask"]})
            score += {1: 4, 2: 8, 3: 15}[sev]
    # one-way-in-disguise check
    recv_mentions = len(re.findall(r"receiving party|recipient", lower))
    disc_mentions = len(re.findall(r"disclosing party|discloser", lower))
    if title_mutual and recv_mentions and disc_mentions and re.search(r"\b(?:company|customer|client|licensor)\b\s+(?:shall|may|will)\s+(?:not )?(?:be entitled|have the right|own)", lower):
        findings.append({"severity": 2, "clause": "Mutuality", "issue": "titled mutual but some obligations/rights are written for a named party only", "market_position": "true mutuality", "ask": "make every obligation run to 'the Receiving Party' and every right to 'the Disclosing Party'"})
        score += 8
    dur = re.search(r"(\d+|one|two|three|four|five|ten)\s*(?:\(\d+\)\s*)?(years?|months?)", lower)
    term_note = None
    if dur:
        n = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ten": 10}.get(dur.group(1)) or int(dur.group(1))
        years = n if dur.group(2).startswith("year") else n / 12
        term_note = f"term/survival language found: {n} {dur.group(2)}"
        if years > 5 and role != "discloser":
            findings.append({"severity": 1, "clause": "Term length", "issue": f"{n} {dur.group(2)} — over the usual 2-5 years for ordinary information", "market_position": "2-5 years; perpetual for trade secrets only", "ask": "reduce to 3 years survival with trade-secret carve-out"})
            score += 4
        if years < 1 and role != "recipient":
            findings.append({"severity": 2, "clause": "Term length", "issue": f"{n} {dur.group(2)} — short for a discloser", "market_position": "2-5 years survival", "ask": "3 years survival"})
            score += 8
    dtsa = bool(re.search(r"1833|defend trade secrets act|whistleblower", lower))
    findings.sort(key=lambda f: -f["severity"])
    score = min(100, score)
    return {
        "role": role,
        "titled_mutual": title_mutual,
        "present": present,
        "findings": findings,
        "risk_score": score,
        "term_note": term_note,
        "dtsa_notice_present": dtsa,
        "verdict": "Sign — standard NDA" if score < 15 else "Negotiate the flagged points" if score < 40 else "Do not sign as-is",
        "next_step": "Send the 'ask' column as redlines; fall back to the market position if refused." if findings else "No issues from your side; confirm dates with nda_drafter__calculate_terms.",
        "scope_note": SCOPE_NOTE,
    }
