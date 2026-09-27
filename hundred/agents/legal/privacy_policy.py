"""Privacy Policy Drafter — data inventory → applicable laws → required sections → plain-language policy."""

from __future__ import annotations

import re

from ...core import Agent, ToolError
from ...lib import text as textlib
from ._common import SCOPE_NOTE, check_rows, check_text, to_float

AGENT = Agent(
    slug="privacy-policy",
    name="Privacy Policy Drafter",
    category="legal",
    tagline="Map what data you collect to the laws that apply, then draft or audit a policy that actually covers it.",
    description=(
        "Builds privacy policies from the inside out: classifies your data inventory (special categories, "
        "children's data, sensitive PI), works out which regimes apply from real thresholds (GDPR/UK GDPR, "
        "CCPA/CPRA, other US state laws, COPPA, PIPEDA, LGPD), generates the exact section checklist each "
        "regime requires, audits an existing policy for missing disclosures and vague weasel-language, and "
        "checks readability against the 'clear and plain language' standard. Drafting aid, not legal advice."
    ),
    triggers=[
        "write / draft a privacy policy",
        "does GDPR or CCPA apply to my app / website",
        "review my privacy policy for compliance gaps",
        "what must a privacy policy include",
        "privacy notice for a mobile app / SaaS / e-commerce store",
        "cookie and tracking disclosures",
    ],
    examples=[
        "We're a US SaaS with EU customers; we collect email, name, IP, usage analytics and Stripe payments. Draft the privacy policy.",
        "Here's our current privacy policy — what's missing for CCPA and GDPR?",
        "Our app is for teens 13+, collects location and photos, and uses Firebase + Mixpanel. Which laws apply and what do we need to disclose?",
    ],
    connectors=["Notion", "Google Docs", "GitHub", "Webflow", "Shopify"],
    playbook="""
    ## Standard
    You are a privacy counsel who drafts notices that are accurate first and readable second — and
    both are mandatory. Excellent work starts from the actual data flows (not a template), names
    every category, purpose, basis, recipient and retention period, and reads at a grade 8-10 level
    because GDPR Art. 12 and CPRA regulations require "clear and plain language". The one metric
    that matters is **every real data flow is disclosed** — an accurate short policy beats a long
    copied one that describes data you don't collect.

    **Scope note (include in every output):** drafting aid, not legal advice. Privacy law changes
    frequently and varies by jurisdiction and sector (health, finance, children, employees).
    Thresholds cited are the widely published ones — verify current figures. Recommend counsel for
    regulated sectors, children's data, biometrics, cross-border transfers, or any enforcement risk.

    ## Intake
    Proceed with what you have. Ask (max 3) only if you cannot infer: (1) what data is collected
    and from whom (users, visitors, employees, children?), (2) where users are and where the
    company is established, (3) which third-party services touch the data (analytics, payments,
    ads, cloud). If the user gives you a product description, derive the likely inventory (e.g.
    "mobile app with login" → email, password hash, device ID, IP, crash logs) and list it as
    assumptions to confirm.

    ## Procedure
    1. **Build the data inventory.** List every data element with source, purpose, and third-party
       recipient. Call `privacy_policy__classify_data_inventory` with the list. It categorises each
       element (identifiers, contact, financial, precise location, biometric, health, etc.), flags
       GDPR Art. 9 special categories and CPRA "sensitive personal information", suggests a lawful
       basis per purpose, and flags elements that need extra treatment (children, biometrics,
       precise geolocation, sale/sharing for ads).
    2. **Determine applicable laws.** Call `privacy_policy__check_applicability` with company
       location, user locations, revenue, consumer counts, data-sale/share status, and audience age.
       It applies the thresholds (CCPA: > $25M revenue as adjusted, or 100k+ consumers/households,
       or ≥ 50% revenue from selling/sharing PI; GDPR: EU establishment or offering to / monitoring
       EU residents; COPPA: directed to or actual knowledge of under-13s; other US states at their
       consumer thresholds) and returns the regimes in force, with what each one adds.
    3. **Generate the section checklist.** Call `privacy_policy__required_sections` with the
       regimes and inventory flags (children, sensitive data, sale/share, automated decisions,
       international transfers). It returns every required disclosure per regime with the source
       article/section, merged into one ordered outline. If the user already has a policy, pass its
       text too: the tool marks each section present/missing.
    4. **Draft or repair.** Write the policy section by section from the outline. Every "we may
       share" becomes "we share X with Y for Z". Every retention says a period or the rule that
       determines it. Rights sections name the mechanism (email, form, toggle) and the response
       deadline (GDPR 1 month; CCPA 45 days).
    5. **Lint the language.** Call `privacy_policy__lint_policy_text` on the draft. It checks
       readability (target FK grade ≤ 10), vague phrases ("from time to time", "may share with
       partners", "as necessary", "including but not limited to" ×N), missing effective date,
       missing contact channel, undefined "third parties", "sell" used without a CCPA-consistent
       statement, and "we take your privacy seriously" filler. Fix everything before delivering.
    6. **Deliver** in the output format. Include a **Data map table** the user must confirm — that
       table is the source of truth; the policy is its prose. If Notion/Docs/GitHub is connected,
       file the policy and the data map separately.

    ## Frameworks
    - **GDPR Art. 13/14 disclosures:** controller identity + contact; DPO (if any); purposes and
      lawful basis per purpose; legitimate interests named; recipients/categories; international
      transfers + safeguards; retention period or criteria; rights (access, rectification, erasure,
      restriction, portability, objection, withdraw consent, complain to a supervisory authority);
      whether provision is statutory/contractual; automated decision-making logic.
    - **CCPA/CPRA notice at collection:** categories collected (using the statutory categories),
      purposes, whether sold/shared, retention per category, rights (know, delete, correct, opt-out
      of sale/sharing, limit use of sensitive PI, non-discrimination), "Do Not Sell or Share" link,
      GPC signal honouring, 12-month lookback, metrics for large businesses.
    - **COPPA:** verifiable parental consent, what is collected from children, parental rights;
      no behavioural ads to under-13s.
    - **Lawful basis heuristic:** account/service delivery → contract; security/fraud/analytics
      (first-party) → legitimate interests (name it); marketing emails/cookies for ads →
      consent; tax/legal records → legal obligation.
    - **Layering:** short notice (≤ 300 words) + full policy; just-in-time notices at collection
      points (location prompt, camera, contacts).

    ## Output format
    ```
    # Privacy Policy — <Company> — Effective <YYYY-MM-DD>   (Readability: grade <n>)
    **Applies:** GDPR · UK GDPR · CCPA/CPRA · <…>   **Scope note:** drafting aid, not legal advice; …

    ## Data map (confirm this first)
    | Data | Source | Purpose | Legal basis (GDPR) | Shared with | Retention | Sensitive? |

    ## Policy
    1. Who we are and how to contact us
    2. What we collect and where it comes from
    3. Why we use it and our legal bases
    4. Who we share it with (named categories + named processors where practical)
    5. International transfers
    6. How long we keep it
    7. Your rights and how to exercise them (per region)
    8. Cookies and tracking (link to cookie policy / preferences)
    9. Children
    10. Security
    11. Changes to this policy
    12. Region-specific disclosures (California, EEA/UK, <others>)

    ## Open items for the company
    - <fact to confirm, e.g. "Do you use Meta Pixel? That is 'sharing' under CPRA.">
    ```

    ## Anti-patterns
    - Copying a competitor's policy. It describes their data flows, not yours — and it's a public admission if wrong.
    - "We may collect… we may share… with partners." Say what, with whom, why.
    - A single global rights section. EEA, UK, California and Brazil have different rights and deadlines.
    - Forgetting the analytics SDK. Firebase, Mixpanel, Meta Pixel and Hotjar are recipients — and often "sharing".
    - No retention periods. "As long as necessary" alone fails Art. 13(2)(a).
    - Burying the policy at grade 14 legalese. Regulators explicitly require plain language.
    """,
)

DATA_CATEGORIES: list[tuple[str, str, bool, bool]] = [
    # key, regex, gdpr_special, cpra_sensitive
    ("government_id", r"ssn|social security|passport|driver'?s? licen[cs]e|national id|tax id|ein\b", False, True),
    ("financial", r"credit card|debit card|card number|bank account|iban|routing|payment (?:details|information|info)|billing|stripe|paypal|transaction", False, True),
    ("precise_location", r"gps|precise (?:geo)?location|lat(?:itude)?/?long|coordinates|geolocation", False, True),
    ("coarse_location", r"\blocation\b|city|country|postal code|zip code|region|time ?zone", False, False),
    ("health", r"health|medical|diagnos|prescription|symptom|fitness data|heart rate|mental|disability|pregnan", True, True),
    ("biometric", r"biometric|fingerprint|face(?:print| id| recognition| geometry)|voiceprint|iris|retina", True, True),
    ("genetic", r"genetic|dna|genome", True, True),
    ("race_ethnicity", r"race|racial|ethnic", True, True),
    ("religion_beliefs", r"religio|philosophical belief|political opinion|political affiliation", True, True),
    ("sexual", r"sexual orientation|sex life|gender identity", True, True),
    ("union", r"trade union|union membership", True, False),
    ("credentials", r"password|passcode|pin\b|security question|login credentials|account credentials", False, True),
    ("communications_content", r"messages?|chat|emails? content|contents? of (?:mail|messages)|dm|conversation|call recording", False, True),
    ("children", r"child|children|minor|under (?:13|16|18)|kid|student|parent", False, False),
    ("contact", r"\bemail\b|e-mail|phone|mobile number|telephone|address|contact", False, False),
    ("identity", r"\bname\b|first name|last name|username|user ?name|date of birth|dob|birthday|age|gender|photo|avatar|profile picture", False, False),
    ("device_network", r"ip address|\bip\b|device id|idfa|gaid|advertising id|mac address|user agent|browser|operating system|device (?:type|model|information)", False, False),
    ("usage_analytics", r"analytics|usage|events?|clicks?|page views?|session|telemetry|crash|logs?|behavio(?:u)?r|interactions?|features? used", False, False),
    ("cookies_tracking", r"cookie|pixel|tracking|beacon|tag manager|fingerprint(?:ing)?|local storage", False, False),
    ("employment", r"employ|salary|job title|employer|resume|cv\b|work history", False, False),
    ("inferences", r"inference|profile|preferences?|interests|segments?|score", False, False),
    ("user_content", r"uploads?|files?|documents?|images?|videos?|posts?|comments?|reviews?|content", False, False),
]
PURPOSE_BASIS: list[tuple[str, str, str]] = [
    (r"account|login|sign ?in|authenticat|deliver|provide|service|order|fulfil|support|billing|payment", "contract (Art. 6(1)(b))", "necessary to provide the service you asked for"),
    (r"fraud|security|abuse|protect|safety|debug|crash|reliab", "legitimate interests (Art. 6(1)(f)) — security", "keeping the service secure"),
    (r"analytics|improve|product research|usage|measure|performance", "legitimate interests (Art. 6(1)(f)) — product improvement; consent if via third-party cookies/SDKs", "understanding how the service is used"),
    (r"marketing|newsletter|promot|advertis|ads?\b|retarget|personali[sz]ed offers", "consent (Art. 6(1)(a)) — and CPRA opt-out of sale/sharing", "marketing"),
    (r"tax|legal|regulat|comply|record[- ]?keeping|kyc|aml", "legal obligation (Art. 6(1)(c))", "meeting legal requirements"),
    (r"recruit|hiring|employ|payroll", "contract / legal obligation (employment context)", "employment administration"),
]


@AGENT.tool
def classify_data_inventory(data_items: list[dict]) -> dict:
    """Classify each collected data element: category, GDPR special-category / CPRA-sensitive status, suggested lawful basis, flags.

    Args:
        data_items: List of {"data": "email address", "purpose": "account login, marketing", "source": "user" (optional),
            "shared_with": "Stripe, Mixpanel" (optional), "retention": "2 years" (optional)}.
    """
    rows = check_rows(data_items, "data_items")
    out, flags, special, sensitive = [], set(), [], []
    purposes_needing_consent, recipients = [], set()
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("data", "")).strip():
            raise ToolError(f"data_items[{i}] needs a 'data' description.")
        d = str(raw["data"]).strip()
        purpose = str(raw.get("purpose", "")).strip()
        shared = str(raw.get("shared_with", "")).strip()
        retention = str(raw.get("retention", "")).strip()
        cats = [k for k, rx, _, _ in DATA_CATEGORIES if re.search(rx, d, re.I)]
        if not cats:
            cats = ["other"]
        gdpr_special = any(sp for k, _, sp, _ in DATA_CATEGORIES if k in cats)
        cpra_sens = any(cs for k, _, _, cs in DATA_CATEGORIES if k in cats)
        bases = []
        for rx, basis, plain in PURPOSE_BASIS:
            if re.search(rx, purpose, re.I):
                bases.append({"basis": basis, "plain": plain})
        if not bases:
            bases.append({"basis": "UNSPECIFIED — state the purpose to pick a basis", "plain": ""})
        if gdpr_special:
            bases.append({"basis": "Art. 9 condition needed too (explicit consent is the usual one)", "plain": "special category"})
        item_flags = []
        if gdpr_special:
            item_flags.append("GDPR Art. 9 special category — explicit consent or another Art. 9 condition; DPIA likely")
            special.append(d)
        if cpra_sens:
            item_flags.append("CPRA sensitive personal information — offer 'Limit the use of my sensitive PI' if used beyond permitted purposes")
            sensitive.append(d)
        if "children" in cats:
            item_flags.append("children's data — COPPA (under 13) / GDPR Art. 8 age of consent (13-16 by member state); parental consent flow")
        if "precise_location" in cats:
            item_flags.append("precise geolocation — just-in-time prompt and opt-in required on mobile platforms")
        if "biometric" in cats:
            item_flags.append("biometric — BIPA (Illinois) written consent and retention schedule; high-risk under GDPR")
        if re.search(r"advertis|ads?\b|retarget|marketing partners|data broker", purpose + " " + shared, re.I):
            item_flags.append("likely 'sale' or 'sharing' under CPRA — Do Not Sell or Share link + GPC required")
            purposes_needing_consent.append(d)
        if not retention:
            item_flags.append("no retention period stated")
        if shared:
            for r in re.split(r"[,;/]| and ", shared):
                if r.strip():
                    recipients.add(r.strip())
        flags.update(item_flags)
        out.append({"data": d, "categories": cats, "gdpr_special_category": gdpr_special, "cpra_sensitive": cpra_sens, "lawful_bases": bases, "shared_with": shared or None, "retention": retention or None, "flags": item_flags})
    needs_dpia = bool(special) or any("children" in o["categories"] or "precise_location" in o["categories"] for o in out) or len(out) >= 15
    return {
        "items": out,
        "count": len(out),
        "special_category_data": special,
        "cpra_sensitive_data": sensitive,
        "sale_or_share_candidates": purposes_needing_consent,
        "recipients": sorted(recipients),
        "dpia_recommended": needs_dpia,
        "flags": sorted(flags),
        "verdict": f"{len(out)} elements; {len(special)} GDPR special-category, {len(sensitive)} CPRA-sensitive, {len(purposes_needing_consent)} likely sold/shared"
        + ("; DPIA recommended" if needs_dpia else ""),
        "scope_note": SCOPE_NOTE,
    }


# thresholds as widely published; the tool output tells the user to verify current figures
US_STATE_LAWS = {
    "california": {"name": "CCPA/CPRA", "consumers": 100_000, "revenue": 26_625_000, "share_pct": 50, "note": "revenue threshold is CPI-adjusted (~$26.6M for 2025-26); applies to for-profit businesses"},
    "virginia": {"name": "VCDPA", "consumers": 100_000, "revenue": None, "share_pct": 50, "note": "or 25k consumers + >50% revenue from sale"},
    "colorado": {"name": "CPA", "consumers": 100_000, "revenue": None, "share_pct": None, "note": "or 25k consumers + any revenue from sale"},
    "connecticut": {"name": "CTDPA", "consumers": 100_000, "revenue": None, "share_pct": None, "note": "or 25k consumers + >25% revenue from sale"},
    "utah": {"name": "UCPA", "consumers": 100_000, "revenue": 25_000_000, "share_pct": None, "note": "requires BOTH $25M revenue AND (100k consumers or 25k + 50% revenue from sale)"},
    "texas": {"name": "TDPSA", "consumers": 0, "revenue": None, "share_pct": None, "note": "no numeric threshold — applies unless a small business (SBA definition), which still needs consent to sell sensitive data"},
    "oregon": {"name": "OCPA", "consumers": 100_000, "revenue": None, "share_pct": None, "note": "or 25k consumers + >25% revenue from sale"},
    "montana": {"name": "MCDPA", "consumers": 50_000, "revenue": None, "share_pct": None, "note": "or 25k consumers + >25% revenue from sale"},
    "new jersey": {"name": "NJDPA", "consumers": 100_000, "revenue": None, "share_pct": None, "note": "or 25k consumers + revenue from sale"},
}
EU_EEA = {"eu", "eea", "europe", "european union", "germany", "france", "spain", "italy", "netherlands", "ireland", "sweden", "poland", "belgium", "austria", "denmark", "finland", "portugal", "czech republic", "czechia", "greece", "romania", "hungary", "norway", "iceland", "liechtenstein"}


@AGENT.tool
def check_applicability(company_country: str, user_regions: list[str], annual_revenue_usd: float = 0, consumers_per_year: int = 0, sells_or_shares_data: bool = False, revenue_pct_from_data_sales: float = 0, audience: str = "general", processes_sensitive_data: bool = False) -> dict:
    """Decide which privacy laws apply (GDPR/UK GDPR, CCPA/CPRA + other US states, COPPA, PIPEDA, LGPD, etc.) from real thresholds.

    Args:
        company_country: Where the company is established, e.g. "US", "Germany", "UK".
        user_regions: Regions/countries/states where users are located, e.g. ["US", "California", "EU", "UK", "Brazil"].
        annual_revenue_usd: Gross annual revenue in USD (for US state thresholds).
        consumers_per_year: Number of consumers/households whose data you handle per year (US thresholds).
        sells_or_shares_data: True if personal data is sold or shared for cross-context behavioural advertising (incl. ad pixels/SDKs).
        revenue_pct_from_data_sales: Share of revenue derived from selling/sharing personal data (0-100).
        audience: "general", "children" (under 13), "teens" (13-17) or "mixed".
        processes_sensitive_data: True if health, biometric, precise location, financial account or similar data is processed.
    """
    company = str(company_country).strip().lower()
    if not company:
        raise ToolError("company_country is required.")
    regions = [str(r).strip().lower() for r in (user_regions or []) if str(r).strip()]
    if not regions:
        raise ToolError("user_regions must list at least one region (e.g. ['US', 'EU']).")
    rev = to_float(annual_revenue_usd, "annual_revenue_usd", 0)
    if not isinstance(consumers_per_year, int) or consumers_per_year < 0:
        raise ToolError("consumers_per_year must be a non-negative integer.")
    share_pct = to_float(revenue_pct_from_data_sales, "revenue_pct_from_data_sales", 0, 100)
    aud = str(audience).strip().lower()
    if aud not in {"general", "children", "teens", "mixed"}:
        raise ToolError("audience must be general, children, teens or mixed.")
    regimes = []

    def has(*names: str) -> bool:
        return any(any(n in r for n in names) for r in regions)

    us_users = has("us", "united states", "usa", "america") or any(s in regions for s in US_STATE_LAWS)
    eu_users = any(r in EU_EEA or "eu" == r for r in regions) or has("europe")
    uk_users = has("uk", "united kingdom", "england", "britain", "scotland", "wales")
    if company in EU_EEA or eu_users:
        regimes.append({"regime": "GDPR (EU/EEA)", "why": "EU establishment" if company in EU_EEA else "offering services to or monitoring EU/EEA residents (Art. 3(2))", "adds": "Art. 13/14 disclosures, lawful basis per purpose, DPO assessment, EU representative if no EU establishment (Art. 27), transfer mechanism (SCCs/DPF), 1-month rights deadline, records of processing"})
    if company in {"uk", "united kingdom"} or uk_users:
        regimes.append({"regime": "UK GDPR + DPA 2018", "why": "UK establishment or UK users", "adds": "same as GDPR with ICO as regulator; UK representative if no UK establishment; UK IDTA/Addendum for transfers; ICO fee registration"})
    state_hits = []
    if us_users:
        for state, law in US_STATE_LAWS.items():
            named = state in regions or "california" in regions and state == "california"
            all_us = has("us", "united states", "usa", "america")
            if not (named or all_us):
                continue
            meets = False
            reasons = []
            if state == "california":
                if rev > law["revenue"]:
                    meets, reasons = True, reasons + [f"revenue > ${law['revenue']:,}"]
                if consumers_per_year >= law["consumers"]:
                    meets, reasons = True, reasons + [f"≥ {law['consumers']:,} consumers/households"]
                if sells_or_shares_data and share_pct >= 50:
                    meets, reasons = True, reasons + ["≥ 50% revenue from selling/sharing"]
            elif state == "utah":
                if rev >= law["revenue"] and (consumers_per_year >= law["consumers"] or (consumers_per_year >= 25_000 and share_pct >= 50)):
                    meets, reasons = True, ["$25M revenue AND consumer threshold"]
            elif state == "texas":
                # no numeric threshold, but small businesses (SBA size standards) are exempt; use $25M revenue as a proxy unless Texas is named explicitly
                if named or rev >= 25_000_000:
                    meets, reasons = True, ["no numeric threshold — applies unless you are an SBA small business (verify size standard)"]
            else:
                if consumers_per_year >= law["consumers"]:
                    meets, reasons = True, [f"≥ {law['consumers']:,} consumers"]
                elif consumers_per_year >= 25_000 and sells_or_shares_data:
                    meets, reasons = True, ["≥ 25k consumers + revenue from sale"]
            if meets:
                state_hits.append({"law": law["name"], "state": state.title(), "because": "; ".join(reasons), "note": law["note"]})
    if state_hits:
        regimes.append({"regime": "US state privacy laws", "why": ", ".join(f"{s['law']} ({s['because']})" for s in state_hits), "adds": "notice at collection with statutory categories, rights to know/delete/correct/opt-out, 45-day response, 'Do Not Sell or Share' link + GPC (CA), universal opt-out signals (CO/CT/others), data protection assessments for targeted ads/sale/sensitive data", "states": state_hits})
    elif us_users:
        regimes.append({"regime": "US — below state thresholds (verify)", "why": f"revenue ${rev:,.0f}, {consumers_per_year:,} consumers, sells/shares={sells_or_shares_data}", "adds": "FTC Act §5 still applies: the policy must be accurate; state breach-notification laws apply everywhere; CalOPPA requires a posted policy for any site collecting PI from Californians"})
    if aud in {"children", "mixed"} or (aud == "teens" and us_users):
        regimes.append({"regime": "COPPA (US, under 13)" if aud != "teens" else "Teen-related rules (CPRA opt-in for under-16 sale; state age-appropriate design codes)", "why": f"audience = {aud}", "adds": "verifiable parental consent, direct notice to parents, no behavioural ads to children, data minimisation, deletion on request" if aud != "teens" else "opt-in consent before selling/sharing data of 13-15s (CPRA); check state minors' codes"})
    if has("canada", "ca"):
        regimes.append({"regime": "PIPEDA (Canada) + Quebec Law 25", "why": "Canadian users", "adds": "meaningful consent, privacy officer named, breach reporting, Quebec: French-language notice and privacy impact assessments"})
    if has("brazil", "br"):
        regimes.append({"regime": "LGPD (Brazil)", "why": "Brazilian users", "adds": "10 legal bases, DPO (encarregado) named, ANPD as regulator, rights similar to GDPR"})
    if has("australia", "au"):
        regimes.append({"regime": "Privacy Act 1988 (Australia)", "why": "Australian users", "adds": "APP 1 open and transparent policy, APP 5 notification at collection, cross-border disclosure statement"})
    if has("switzerland", "ch"):
        regimes.append({"regime": "Swiss FADP (revised 2023)", "why": "Swiss users", "adds": "similar to GDPR; list countries of transfer"})
    extras = []
    if processes_sensitive_data:
        extras.append("Sensitive data: DPIA under GDPR Art. 35; CPRA 'limit use' right; sector rules may apply (HIPAA if a covered entity/business associate, GLBA for financial institutions, BIPA for biometrics in Illinois)")
    if sells_or_shares_data:
        extras.append("Sale/sharing: 'Do Not Sell or Share My Personal Information' link, honour Global Privacy Control, opt-in for minors; under GDPR ad-tech sharing needs consent (ePrivacy/cookie rules)")
    return {
        "regimes": regimes,
        "regime_names": [r["regime"] for r in regimes],
        "additional_obligations": extras,
        "inputs": {"company_country": company, "user_regions": regions, "annual_revenue_usd": rev, "consumers_per_year": consumers_per_year, "sells_or_shares_data": sells_or_shares_data, "audience": aud},
        "verdict": ("Applies: " + "; ".join(r["regime"] for r in regimes)) if regimes else "No specific regime matched — an accurate policy is still required (FTC Act / consumer-protection law)",
        "scope_note": SCOPE_NOTE + " Thresholds are as widely published (e.g. CCPA revenue threshold is CPI-adjusted) — verify current figures.",
    }


REQUIRED: dict[str, list[tuple[str, str, str]]] = {
    # regime → (section key, label, regex that shows it is present)
    "core": [
        ("identity", "Controller / business identity and contact details", r"contact us|contact (?:information|details)|who we are|data controller|we are [A-Z][\w ]+(?:,|\.| inc| ltd| llc| gmbh)|our address|@[\w.-]+\.\w{2,}"),
        ("effective_date", "Effective / last-updated date", r"effective (?:date|as of)|last (?:updated|modified|revised)|updated on|\b20\d{2}-\d{2}-\d{2}\b|(?:january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2},? 20\d{2}"),
        ("categories", "Categories of personal data collected", r"(?:information|data) we collect|categories of (?:personal )?(?:information|data)|what we collect|personal (?:data|information) (?:we|that we) (?:collect|process)"),
        ("sources", "Sources of the data (you, devices, third parties)", r"sources?|collect(?:ed)? (?:directly )?from you|automatically collect|from third parties|information from other sources"),
        ("purposes", "Purposes of processing", r"how we use|why we (?:use|process|collect)|purposes?|use (?:your|the) (?:information|data) (?:to|for)"),
        ("recipients", "Recipients / who we share with", r"share|disclos|recipients?|service providers?|processors?|third parties"),
        ("retention", "Retention periods or criteria", r"retain|retention|how long|keep (?:your|the) (?:information|data)|delete[sd]? (?:your|the) (?:data|information) (?:after|when)"),
        ("security", "Security measures", r"security|safeguards?|encrypt|protect (?:your|the) (?:information|data)"),
        ("children", "Children's data statement", r"children|under (?:the age of )?(?:13|16|18)|minors?|coppa"),
        ("changes", "Changes to the policy", r"changes? to this (?:policy|notice)|update this (?:policy|notice)|modify this (?:policy|notice)|revise this"),
        ("cookies", "Cookies and tracking technologies", r"cookies?|tracking technolog|pixels?|web beacons?|local storage|sdk"),
        ("rights_general", "Rights and how to exercise them", r"your (?:rights|choices)|right to (?:access|delete|erasure|correct|rectif|object|opt[- ]out|portab)|exercise (?:your|these) rights"),
    ],
    "gdpr": [
        ("lawful_basis", "Lawful basis for each purpose (Art. 6) — and Art. 9 condition for special categories", r"lawful basis|legal basis|legitimate interests?|performance of a contract|article 6|art\.? 6|consent"),
        ("legitimate_interests", "Legitimate interests named where relied on", r"legitimate interests? (?:in|of|include|are)|our legitimate interests?"),
        ("transfers", "International transfers and safeguards (SCCs, adequacy, DPF)", r"international transfers?|outside (?:the )?(?:eea|eu|european|uk)|standard contractual clauses|sccs?|adequacy|data privacy framework|transfer(?:red)? .{0,40}(?:countries|abroad|outside)"),
        ("dpo", "DPO or EU/UK representative (if required)", r"data protection officer|dpo|eu representative|uk representative|article 27|art\.? 27"),
        ("rights_gdpr", "GDPR rights: access, rectification, erasure, restriction, portability, objection, withdraw consent", r"(?:rectif|correct).{0,300}(?:eras|delet).{0,300}(?:restrict|portab|object)|portability|restriction of processing|withdraw (?:your )?consent"),
        ("complaint", "Right to lodge a complaint with a supervisory authority", r"supervisory authority|data protection authority|lodge a complaint|ico\b|information commissioner"),
        ("automated", "Automated decision-making / profiling (if any)", r"automated decision|profiling|automated processing|algorithm"),
        ("statutory", "Whether provision is required and consequences of not providing", r"required to provide|consequences? of not providing|you are not obliged|if you do not provide|failure to provide"),
        ("response_time", "Response within one month", r"one month|1 month|30 days|within a month"),
    ],
    "ccpa": [
        ("cpra_categories", "Statutory categories (identifiers, commercial info, internet activity, geolocation, inferences, sensitive PI…)", r"identifiers|commercial information|internet (?:or other electronic network )?activity|geolocation data|inferences|sensitive personal information|protected classification|biometric information|professional or employment"),
        ("sale_share", "Whether PI is sold or shared, and Do Not Sell or Share link", r"do not sell|do not share|sell(?:ing)? (?:your |of )?personal information|share[sd]? .{0,40}cross-context|behavio(?:u)?ral advertising|opt[- ]out of (?:the )?sale"),
        ("gpc", "Global Privacy Control / opt-out preference signals honoured", r"global privacy control|gpc|opt[- ]out preference signal|universal opt[- ]out"),
        ("rights_ccpa", "CCPA rights: know, delete, correct, opt-out, limit sensitive PI, non-discrimination", r"right to know|right to delete|right to correct|limit the use|non-?discriminat|not discriminate"),
        ("lookback", "12-month lookback / categories collected in the preceding 12 months", r"preceding (?:12|twelve) months|past (?:12|twelve) months|last (?:12|twelve) months"),
        ("verification", "How requests are verified and authorised agents", r"verif(?:y|ication)|authori[sz]ed agent"),
        ("response_45", "45-day response window", r"45 days|forty-five days"),
        ("retention_per_category", "Retention period per category", r"retain .{0,80}(?:category|categories)|for each category"),
        ("financial_incentive", "Notice of financial incentive (if loyalty/discounts for data)", r"financial incentive|loyalty|discount|reward"),
    ],
    "coppa": [
        ("parental_consent", "Verifiable parental consent mechanism", r"parental consent|parent'?s? (?:consent|permission)|verifiable"),
        ("parent_rights", "Parents' rights to review/delete and refuse further collection", r"parents? (?:may|can) (?:review|request|delete|refuse)|parents?'? rights"),
        ("child_data", "What is collected from children and how it is used", r"collect(?:ed)? from (?:a )?child|children'?s? (?:personal )?information"),
        ("operators", "Operators collecting data through the service", r"operators?|third[- ]party (?:services|sdks?) .{0,60}child"),
    ],
}
REGIME_ALIASES = {"gdpr": "gdpr", "uk gdpr": "gdpr", "eu": "gdpr", "ccpa": "ccpa", "cpra": "ccpa", "california": "ccpa", "us state": "ccpa", "coppa": "coppa", "children": "coppa"}


@AGENT.tool
def required_sections(regimes: list[str], policy_text: str = "", sells_or_shares: bool = False, has_sensitive_data: bool = False, international_transfers: bool = True, automated_decisions: bool = False) -> dict:
    """Build the required-disclosure checklist for the regimes in force and (optionally) mark which an existing policy covers.

    Args:
        regimes: Regime names, e.g. ["GDPR", "CCPA", "COPPA"]. Core sections are always included.
        policy_text: Existing policy text to audit (optional; up to 300k chars).
        sells_or_shares: Whether PI is sold or shared for targeted advertising (adds opt-out sections).
        has_sensitive_data: Whether special-category / sensitive PI is processed.
        international_transfers: Whether data leaves the user's region (default true — almost always with cloud vendors).
        automated_decisions: Whether solely automated decisions with legal/significant effects are made.
    """
    if not isinstance(regimes, list):
        raise ToolError("regimes must be a list of regime names.")
    keys = {"core"}
    unknown = []
    for r in regimes:
        rl = str(r).strip().lower()
        hit = next((v for k, v in REGIME_ALIASES.items() if k in rl), None)
        if hit:
            keys.add(hit)
        elif rl:
            unknown.append(str(r))
    body = None
    if policy_text and policy_text.strip():
        body = check_text(policy_text, "policy_text")
    checklist, missing, present = [], [], 0
    for regime in ("core", "gdpr", "ccpa", "coppa"):
        if regime not in keys:
            continue
        for key, label, rx in REQUIRED[regime]:
            if key == "sale_share" and not sells_or_shares:
                label += " (state that you do NOT sell or share, if true)"
            if key == "automated" and not automated_decisions:
                label += " (state 'none' if not applicable)"
            if key == "transfers" and not international_transfers:
                continue
            entry = {"regime": regime.upper() if regime != "core" else "ALL", "section": key, "required": label}
            if body is not None:
                ok = bool(re.search(rx, body, re.I | re.S))
                entry["present"] = ok
                if ok:
                    present += 1
                else:
                    missing.append(entry)
            checklist.append(entry)
    if has_sensitive_data:
        checklist.append({"regime": "ALL", "section": "sensitive_handling", "required": "Sensitive data: explicit consent / Art. 9 condition, CPRA 'limit use' right, extra security"})
    coverage = round(100 * present / len(checklist)) if body is not None and checklist else None
    outline = [
        "1. Who we are and how to contact us", "2. What we collect and where it comes from", "3. Why we use it and our legal bases",
        "4. Who we share it with", "5. International transfers", "6. How long we keep it", "7. Your rights and how to exercise them",
        "8. Cookies and tracking", "9. Children", "10. Security", "11. Changes to this policy", "12. Region-specific disclosures",
    ]
    return {
        "regimes_applied": sorted(k.upper() for k in keys if k != "core"),
        "unknown_regimes": unknown,
        "checklist": checklist,
        "required_count": len(checklist),
        "present": present if body is not None else None,
        "missing": missing,
        "coverage_pct": coverage,
        "outline": outline,
        "verdict": (f"{coverage}% of required disclosures found; {len(missing)} missing" if coverage is not None else f"{len(checklist)} required disclosures for {', '.join(sorted(k.upper() for k in keys if k != 'core')) or 'baseline'}"),
        "scope_note": SCOPE_NOTE,
    }


VAGUE_PHRASES = [
    (r"from time to time", "say when or how often"),
    (r"(?:may|might) (?:share|disclose|sell|transfer) .{0,40}(?:partners|third parties|affiliates)(?! (?:such as|including|listed|named|who))", "name the categories of recipients and the purpose"),
    (r"as (?:we deem )?necessary|as (?:deemed )?appropriate|where appropriate", "state the rule that decides"),
    (r"including,? but not limited to", "list is open-ended — either close it or say 'for example'"),
    (r"we take (?:your )?privacy (?:very )?seriously|your privacy is important to us", "filler — delete; regulators read it as a red flag"),
    (r"as long as (?:necessary|needed|required)(?! (?:to|for) .{0,60}(?:\d+ (?:days|months|years)|until))", "give a period or the criteria that set it (Art. 13(2)(a))"),
    (r"third parties(?! (?:such as|including|listed|named|who|that|acting))", "'third parties' undefined — categorise them (processors, advertisers, authorities)"),
    (r"for (?:business|legitimate|internal) purposes(?! (?:such as|including|namely))", "purpose too vague — list them"),
    (r"(?:other|various|certain|some) (?:information|data|purposes|parties)", "'other/various/certain' hides specifics"),
    (r"we do not sell(?! (?:or share|your))", "'do not sell' without 'or share' — CPRA covers sharing for targeted ads too"),
    (r"by using (?:our|this|the) (?:site|service|app|website),? you (?:consent|agree)", "implied consent by use is not valid consent under GDPR"),
    (r"automatically", "say what is collected automatically (IP, device, cookies)"),
]


@AGENT.tool
def lint_policy_text(policy_text: str, target_grade: float = 10.0) -> dict:
    """Lint a privacy policy for readability (GDPR Art. 12 plain language), vague phrases, and missing basics.

    Args:
        policy_text: The policy text to lint.
        target_grade: Maximum acceptable Flesch-Kincaid grade (default 10).
    """
    body = check_text(policy_text, "policy_text")
    if not isinstance(target_grade, (int, float)) or not 4 <= target_grade <= 16:
        raise ToolError("target_grade must be between 4 and 16.")
    r = textlib.readability(body)
    findings = []
    for rx, why in VAGUE_PHRASES:
        hits = list(re.finditer(rx, body, re.I))
        if hits:
            findings.append({"phrase": hits[0].group(0)[:60], "count": len(hits), "fix": why, "example": re.sub(r"\s+", " ", body[max(0, hits[0].start() - 60) : hits[0].end() + 60]).strip()})
    basics = {
        "effective_date": bool(re.search(r"effective|last updated|updated on", body, re.I)),
        "contact_channel": bool(re.search(r"@[\w.-]+\.\w{2,}|contact (?:us|form)|privacy@|dpo@|\+?\d[\d ()-]{7,}", body, re.I)),
        "retention_period_stated": bool(re.search(r"\d+\s*(?:days|months|years)|until (?:you|your account)|for the (?:duration|life) of", body, re.I)),
        "rights_mechanism": bool(re.search(r"(?:email|write to|contact|submit|use the|settings|form|toggle|link).{0,80}(?:request|exercise|rights|delete|access)", body, re.I | re.S)),
        "named_processors_or_categories": bool(re.search(r"such as|including|for example|e\.g\.|namely|(?:stripe|google|amazon|aws|microsoft|mailchimp|hubspot|salesforce|mixpanel|segment|firebase|cloudflare|intercom|zendesk)", body, re.I)),
    }
    missing_basics = [k for k, v in basics.items() if not v]
    long_sentences = [s[:140] for s in textlib.sentences(body) if len(textlib.words(s)) > 35][:5]
    passive = len(textlib.passive_sentences(body))
    score = 100
    score -= min(30, 5 * len(findings))
    score -= 8 * len(missing_basics)
    if r["fk_grade"] and r["fk_grade"] > target_grade:
        score -= min(20, int((r["fk_grade"] - target_grade) * 5))
    score -= min(10, 2 * len(long_sentences))
    score = max(0, score)
    return {
        "score": score,
        "readability": {"fk_grade": r["fk_grade"], "flesch_reading_ease": r["flesch_reading_ease"], "words": r["words"], "avg_words_per_sentence": r.get("avg_words_per_sentence"), "target_grade": target_grade, "passes": bool(r["fk_grade"] is not None and r["fk_grade"] <= target_grade)},
        "vague_phrases": findings,
        "basics": basics,
        "missing_basics": missing_basics,
        "long_sentences": long_sentences,
        "passive_sentences": passive,
        "verdict": ("Clear and specific" if score >= 85 else "Needs tightening" if score >= 60 else "Vague / hard to read — rewrite with the data map as the source of truth"),
        "fixes": [f"Replace '{f['phrase']}' ×{f['count']}: {f['fix']}" for f in findings[:6]] + [f"Add: {m.replace('_', ' ')}" for m in missing_basics],
        "scope_note": SCOPE_NOTE,
    }
