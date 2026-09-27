"""Freelance Tax Estimator — quarterly estimates, safe harbor, deductions and deadlines for the self-employed (US)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from ...core import Agent, ToolError
from ._common import D, as_pct, ZERO, as_rate, bound_rows, money, parse_iso, ratio_to_pct, require_nonneg, require_positive

DEFAULTS_YEAR = 2026
SCOPE_NOTE = (
    "Estimate only, not tax advice. Default brackets, standard deduction, SS wage base and mileage rate "
    f"are the published {DEFAULTS_YEAR} US federal figures (IRS Rev. Proc. 2025-32, SSA 2026 wage base, "
    "IRS Notice 2026-10 / Announcement 2026-11) as transcribed by us — verify them on IRS.gov (Pub 505, "
    "Schedule SE, Form 1040-ES) and pass the correct year's values as parameters for any other year. "
    "State tax is a flat placeholder. Consult a CPA or EA for anything unusual."
)

# Clearly-labelled defaults: tax year 2026 federal figures (IRS Rev. Proc. 2025-32 incl. OBBBA changes;
# SSA wage base announced 2025-10-24). Every one can be overridden by parameter. Verify before relying on them.
DEFAULT_BRACKETS = {
    "single": [[0, 10], [12400, 12], [50400, 22], [105700, 24], [201775, 32], [256225, 35], [640600, 37]],
    "married_joint": [[0, 10], [24800, 12], [100800, 22], [211400, 24], [403550, 32], [512450, 35], [768700, 37]],
    "head_of_household": [[0, 10], [17700, 12], [67450, 22], [105700, 24], [201775, 32], [256200, 35], [640600, 37]],
}
DEFAULT_STANDARD_DEDUCTION = {"single": 16100, "married_joint": 32200, "head_of_household": 24150}
DEFAULT_SS_WAGE_BASE = 184500
QBI_THRESHOLD = {"single": 201775, "married_joint": 403550, "head_of_household": 201775}  # 2026 taxable-income threshold where §199A limits begin
DEFAULT_MILEAGE_RATE = 0.725  # 2026 Jan 1–Jun 30; 76¢ for miles driven Jul 1–Dec 31 2026 (IRS Announcement 2026-11)
SE_NET_FACTOR = Decimal("0.9235")
SS_RATE = Decimal("0.124")
MEDICARE_RATE = Decimal("0.029")
ADDL_MEDICARE_RATE = Decimal("0.009")
ADDL_MEDICARE_THRESHOLD = {"single": 200000, "married_joint": 250000, "head_of_household": 200000}

AGENT = Agent(
    slug="freelance-tax",
    name="Freelance Tax Estimator",
    category="finance",
    tagline="Know what to set aside: quarterly estimates with SE tax, safe-harbor targets, deduction math and the real IRS deadlines.",
    description=(
        "Runs the self-employed tax workflow a good CPA runs for freelancers and solo founders: projects "
        "the year's self-employment tax (with the SS wage base and the half-SE deduction done right), "
        "federal income tax through configurable brackets with the QBI deduction, turns it into quarterly "
        "payments and a set-aside percentage per invoice, checks the safe-harbor rule so you never owe a "
        "penalty, values deductions (home office, mileage, meals at 50%) at your marginal rate, and lists "
        "the estimated-tax deadlines with days remaining. Rates and brackets are parameters with labelled "
        "defaults — estimates, not tax advice."
    ),
    triggers=[
        "how much should I set aside for taxes as a freelancer",
        "estimate my quarterly taxes / 1040-ES payments",
        "self-employment tax calculation",
        "safe harbor rule — how much do I need to pay to avoid a penalty",
        "what can I deduct as a freelancer / home office deduction",
        "when are estimated taxes due",
    ],
    examples=[
        "I'm a freelance designer, single, expecting about $95k net this year. What are my quarterly payments?",
        "Last year my total tax was $18,400 and AGI was $140k. I've paid $6,000 so far this year — am I safe from penalties?",
        "I drive 4,000 business miles, have a 200 sq ft home office and spent $2,800 on client meals. What are these worth in tax saved?",
    ],
    connectors=["QuickBooks", "Stripe", "Google Sheets", "Gusto"],
    playbook="""
    ## Standard
    You are a CPA who specialises in solo businesses. Excellent means: the client knows the exact
    dollar amount to move into a tax account from every payment, the four payment dates, and whether
    they are protected from an underpayment penalty. The metric is **zero surprises in April**: no
    penalty, no scramble. Scope: US federal estimates with a flat state placeholder; estimates only,
    not tax advice; defaults are the tax-year-2026 IRS figures as we transcribed them, must be
    verified, and must be overridden for any other year; hand off to a CPA for S-corp elections, multi-state, foreign income or anything odd.

    ## Intake
    Needed: expected net self-employment profit for the year (revenue minus expenses), filing status,
    any W-2 wages and withholding (own or spouse's), last year's total tax and AGI (for safe harbor),
    payments made so far, and state. Ask at most 3 questions, only if net profit or filing status is
    missing. If the user gives only revenue, ask for expenses or assume 20% and say so.

    ## Procedure
    1. **Confirm figures.** If the user supplies this year's brackets, standard deduction or wage
       base, pass them as parameters; otherwise use the tool defaults (tax year 2026) and state in the
       output that they are estimates to verify against current IRS publications. For any tax year
       other than 2026, the defaults are wrong: pass that year's figures.
    2. **Project the year.** Call `freelance_tax__quarterly_estimate` with net SE profit, filing
       status, W-2 wages/withholding and any overrides. It computes SE tax on 92.35% of net profit
       (Social Security up to the wage base, Medicare with the 0.9% surtax above the threshold), the
       half-SE deduction, the standard deduction, the 20% QBI deduction (when enabled), income tax
       through the brackets, the total, four equal quarterly payments, the effective rate and the
       set-aside percentage per dollar of net profit.
    3. **Check safe harbor.** Call `freelance_tax__safe_harbor` with last year's total tax and AGI,
       this year's projected tax and payments/withholding to date. The required annual payment is
       the smaller of 90% of this year's tax and 100% of last year's (110% if prior AGI was over
       the threshold, default $150,000). Recommend paying to the safe-harbor number when income is
       rising and to 90% of current when it is falling — never less than safe harbor if cash allows.
    4. **Value deductions.** Call `freelance_tax__deduction_value` with the expense list and the
       two rates from step 2's `for_deduction_value` (never the raw bracket rate: the half-SE and QBI
       deductions shrink what a deduction saves). It applies the rules (meals 50%, home office simplified method at
       the per-square-foot rate up to the cap, standard mileage rate, business-use percentage) and
       returns the deductible amount and tax saved (income tax + SE tax effect). Remind the user that
       a deduction saves tax at the marginal rate, not dollar for dollar.
    5. **Set the calendar.** Call `freelance_tax__payment_deadlines` with the tax year and today's
       date. It returns the four due dates (weekend-adjusted), the income period each covers, days
       remaining and which payment is next. Put the next date in the first line of the output with
       the amount from step 3's `per_remaining_quarter` (it includes any catch-up), not the even
       annual ÷ 4 split, whenever a quarter has already been missed or underpaid.
    6. **Write the plan.** Include the per-invoice set-aside rule ("move X% of every deposit to the
       tax account the day it lands"), a separate tax account recommendation, and the annualised-income
       method note for lumpy income (Form 2210 Schedule AI) as a CPA question.

    ## Frameworks
    - **SE tax**: net profit × 0.9235 × 15.3% (12.4% SS to the wage base + 2.9% Medicare); half is
      deductible above the line.
    - **Safe harbor**: min(90% current-year tax, 100%/110% prior-year tax), paid evenly by quarter.
    - **Set-aside rule of thumb**: 25-30% of net profit for most freelancers under six figures;
      compute the exact figure, do not quote the rule of thumb.
    - **Quarter periods are uneven**: Jan-Mar, Apr-May, Jun-Aug, Sep-Dec; due Apr 15, Jun 15,
      Sep 15, Jan 15 (next year), moved to the next business day when on a weekend or holiday.
    - **Deduction rules**: meals 50%; home office simplified $5/sq ft up to 300 sq ft (default;
      verify); mileage at the standard rate (2026 default 72.5¢ Jan-Jun, 76¢ Jul-Dec — split the miles;
      verify); phone/internet at business-use %.

    ## Output format
    ```
    # Tax estimate — <tax year> — <filing status>
    **Next payment:** $X due <date> (N days) · **Set aside:** Y% of every net dollar · **Safe harbor:** met|short by $Z

    ## Projection
    | Line | Amount |
    | Net SE profit | |
    | SE tax | |
    | Taxable income | |
    | Federal income tax | |
    | State (flat placeholder) | |
    | Total | |
    | Quarterly payment | |

    ## Deductions
    | Item | Claimed | Deductible | Tax saved |

    ## Deadlines
    | Q | Period | Due | Days left | Amount |

    ## Assumptions & verify list
    - <every default used, with "verify current IRS figure">
    Estimate only, not tax advice.
    ```

    ## Anti-patterns
    - Quoting "set aside 30%" without computing it. The number is often 22% or 38%.
    - Applying SE tax to 100% of profit, or forgetting the SS wage base and the half-SE deduction.
    - Treating bracket defaults as this year's law. Label them; verify them.
    - Paying 25% of the projected tax each quarter when income arrived unevenly, without mentioning
      the annualised method.
    - Valuing a $1,000 deduction as $1,000 saved.
    """,
)


def _tax_from_brackets(taxable: Decimal, brackets: list[list]) -> tuple[Decimal, Decimal]:
    """Return (tax, marginal_rate_pct) for progressive brackets [[threshold, rate_pct], ...]."""
    tax, marginal = ZERO, ZERO
    for i, (lo, rate) in enumerate(brackets):
        lo, rate = D(lo, "bracket threshold"), D(rate, "bracket rate")
        hi = D(brackets[i + 1][0], "bracket threshold") if i + 1 < len(brackets) else None
        if taxable <= lo:
            break
        span = (min(taxable, hi) if hi is not None else taxable) - lo
        tax += span * rate / 100
        marginal = rate
    return tax, marginal


def _validate_brackets(brackets: list[list]) -> list[list]:
    if not isinstance(brackets, list) or len(brackets) < 1 or len(brackets) > 12:
        raise ToolError("brackets must be a list of 1-12 [threshold, rate_pct] pairs")
    prev = -1
    for b in brackets:
        if not isinstance(b, list) or len(b) != 2:
            raise ToolError("each bracket must be [threshold, rate_pct]")
        lo, rate = D(b[0], "bracket threshold"), D(b[1], "bracket rate")
        if lo <= prev or not 0 <= rate <= 100:
            raise ToolError("brackets must have ascending thresholds and rates 0-100")
        prev = lo
    return brackets


@AGENT.tool
def quarterly_estimate(
    net_se_income: float,
    filing_status: Literal["single", "married_joint", "head_of_household"] = "single",
    w2_wages: float = 0,
    w2_withholding: float = 0,
    other_income: float = 0,
    apply_qbi_deduction: bool = True,
    state_rate_pct: float = 0,
    brackets: list[list] | None = None,
    standard_deduction: float = 0,
    ss_wage_base: float = 0,
    payments_made: float = 0,
) -> dict:
    """Project the year's SE tax + federal income tax and turn it into quarterly payments and a set-aside percentage.

    Uses labelled default brackets, standard deduction and SS wage base (approximate recent
    federal figures) unless you pass this year's values. Estimate only, not tax advice.

    Args:
        net_se_income: Expected net self-employment profit for the year (revenue minus business expenses).
        filing_status: "single", "married_joint" or "head_of_household".
        w2_wages: W-2 wages for the household (yours or spouse's) — affects the SS wage base and brackets.
        w2_withholding: Federal tax already being withheld from W-2 wages this year.
        other_income: Other taxable income (interest, dividends, spouse's non-W-2 income).
        apply_qbi_deduction: Apply the 20% qualified business income deduction (simplified; phase-outs ignored above ~$190k single / ~$380k joint taxable — flag for a CPA).
        state_rate_pct: Flat state income tax placeholder, e.g. 5 (0 for no-income-tax states).
        brackets: Override brackets as [[threshold, rate_pct], ...] ascending, e.g. [[0,10],[11925,12],...].
        standard_deduction: Override the standard deduction (0 = use default for status).
        ss_wage_base: Override the Social Security wage base (0 = use default).
        payments_made: Estimated payments already made this year.
    """
    net = D(net_se_income, "net_se_income")
    if net < 0:
        raise ToolError("net_se_income cannot be negative — a loss year needs a CPA, not an estimate")
    if net > 50_000_000:
        raise ToolError("net_se_income looks unrealistic")
    wages = require_nonneg(D(w2_wages, "w2_wages"), "w2_wages")
    withheld = require_nonneg(D(w2_withholding, "w2_withholding"), "w2_withholding")
    other = require_nonneg(D(other_income, "other_income"), "other_income")
    paid = require_nonneg(D(payments_made, "payments_made"), "payments_made")
    state = as_pct(state_rate_pct, "state_rate_pct")
    if not 0 <= state <= Decimal("0.2"):
        raise ToolError("state_rate_pct must be 0-20")
    br = _validate_brackets(brackets) if brackets else DEFAULT_BRACKETS[filing_status]
    std = D(standard_deduction, "standard_deduction") if standard_deduction else D(DEFAULT_STANDARD_DEDUCTION[filing_status])
    base = D(ss_wage_base, "ss_wage_base") if ss_wage_base else D(DEFAULT_SS_WAGE_BASE)
    defaults_used = []
    if not brackets:
        defaults_used.append(f"federal brackets: {DEFAULTS_YEAR} tables (Rev. Proc. 2025-32) — estimate; verify current IRS figure")
    if not standard_deduction:
        defaults_used.append(f"standard deduction ${money(std):,.0f} ({DEFAULTS_YEAR}) — estimate; verify current IRS figure")
    if not ss_wage_base:
        defaults_used.append(f"SS wage base ${money(base):,.0f} ({DEFAULTS_YEAR}) — estimate; verify current SSA figure")
    # SE tax
    se_base = (net * SE_NET_FACTOR).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    ss_room = max(base - wages, ZERO)
    ss_tax = min(se_base, ss_room) * SS_RATE
    medicare = se_base * MEDICARE_RATE
    addl_thr = D(ADDL_MEDICARE_THRESHOLD[filing_status])
    # Form 8959: the threshold is reduced (not below zero) by wages; the surtax applies to SE income above the rest
    addl = max(se_base - max(addl_thr - wages, ZERO), ZERO) * ADDL_MEDICARE_RATE
    se_tax = ss_tax + medicare + addl
    half_se = (ss_tax + medicare) / 2  # Schedule SE: the deduction is half of SE tax; the 0.9% surtax is not deductible
    # income tax
    agi = net + wages + other - half_se
    qbi = min(net - half_se, ZERO.max(agi - std)) * Decimal("0.2") if apply_qbi_deduction and net > 0 else ZERO
    qbi = max(qbi, ZERO)
    taxable = max(agi - std - qbi, ZERO)
    income_tax, marginal = _tax_from_brackets(taxable, br)
    state_tax = taxable * state
    total = se_tax + income_tax + state_tax
    remaining = max(total - withheld - paid, ZERO)
    quarterly = (total - withheld) / 4
    set_aside = (se_tax + income_tax + state_tax - (_tax_from_brackets(max(wages + other - std, ZERO), br)[0] if (wages or other) else ZERO)) / net if net > 0 else ZERO
    # Marginal effect of one more (or one fewer, for a deduction) dollar of net SE profit:
    se_rate = (SS_RATE + MEDICARE_RATE if se_base < ss_room else MEDICARE_RATE) * SE_NET_FACTOR  # 14.13% or 2.68%
    deductible_se = se_rate / 2
    if se_base + wages > addl_thr:
        se_rate += ADDL_MEDICARE_RATE * SE_NET_FACTOR
    qbi_factor = Decimal("0.8") if (apply_qbi_deduction and qbi > 0) else Decimal(1)
    income_rate_per_dollar = (marginal / 100 + state) * (1 - deductible_se) * qbi_factor
    combined_marginal = se_rate + income_rate_per_dollar
    qbi_flag = taxable > QBI_THRESHOLD[filing_status] and apply_qbi_deduction
    return {
        "inputs": {"net_se_income": money(net), "filing_status": filing_status, "w2_wages": money(wages), "other_income": money(other)},
        "se_tax": {"se_base_92_35pct": money(se_base), "social_security": money(ss_tax), "medicare": money(medicare), "additional_medicare": money(addl), "total": money(se_tax), "half_se_deduction": money(half_se)},
        "income_tax": {"agi": money(agi), "standard_deduction": money(std), "qbi_deduction": money(qbi), "taxable_income": money(taxable), "federal_income_tax": money(income_tax), "marginal_rate_pct": float(marginal)},
        "state_tax_placeholder": money(state_tax),
        "total_tax": money(total),
        "effective_rate_on_net_pct": ratio_to_pct(total / (net + wages + other)) if (net + wages + other) else 0.0,
        "already_covered": {"w2_withholding": money(withheld), "payments_made": money(paid)},
        "remaining_to_pay": money(remaining),
        "quarterly_payment": money(max(quarterly, ZERO)),
        "set_aside_pct_of_net": ratio_to_pct(set_aside),
        "combined_marginal_rate_pct": ratio_to_pct(combined_marginal),
        "for_deduction_value": {
            "marginal_income_rate_pct": ratio_to_pct(income_rate_per_dollar, 2),
            "se_rate_effective_pct": ratio_to_pct(se_rate, 2),
            "note": "income-tax saving per $1 of deduction after the half-SE and 20% QBI effects; pass both to deduction_value",
        },
        "defaults_used": defaults_used,
        "flags": (["taxable income above the §199A threshold — QBI deduction may be limited (W-2 wage/SSTB rules); CPA review"] if qbi_flag else []),
        "verdict": f"Projected total ${money(total):,.0f} (SE ${money(se_tax):,.0f} + federal ${money(income_tax):,.0f}" + (f" + state ${money(state_tax):,.0f}" if state_tax else "") + f"); pay ${money(max(quarterly, ZERO)):,.0f} per quarter and set aside {ratio_to_pct(set_aside)}% of every net dollar. Marginal rate {float(marginal)}% federal.",
        "scope_note": SCOPE_NOTE,
    }


@AGENT.tool
def safe_harbor(
    prior_year_total_tax: float,
    prior_year_agi: float,
    current_year_projected_tax: float,
    paid_to_date: float = 0,
    quarters_elapsed: int = 0,
    high_income_threshold: float = 150000,
    high_income_pct: float = 110,
    withholding: float = 0,
) -> dict:
    """Required annual payment under the safe-harbor rule, and whether payments to date are on track.

    Required = min(90% of current-year tax, 100% of prior-year tax — 110% if prior AGI exceeded the
    threshold). Paid evenly by quarter. Estimate only; penalty computation itself is on Form 2210.

    Args:
        prior_year_total_tax: Total tax on last year's return (Form 1040 total tax line).
        prior_year_agi: Last year's adjusted gross income.
        current_year_projected_tax: This year's projected total tax (from quarterly_estimate).
        paid_to_date: Estimated payments plus withholding so far this year.
        quarters_elapsed: How many quarterly due dates have passed (0-4) to judge on-track status.
        high_income_threshold: Prior-year AGI above which the higher percentage applies (default 150000; verify; 75000 if married filing separately).
        high_income_pct: Percentage of prior-year tax required above the threshold (default 110).
        withholding: W-2 withholding expected for the year (already included in paid_to_date if withheld so far); used for the under-$1,000 test.
    """
    prior = require_nonneg(D(prior_year_total_tax, "prior_year_total_tax"), "prior_year_total_tax")
    agi = require_nonneg(D(prior_year_agi, "prior_year_agi"), "prior_year_agi")
    cur = require_nonneg(D(current_year_projected_tax, "current_year_projected_tax"), "current_year_projected_tax")
    paid = require_nonneg(D(paid_to_date, "paid_to_date"), "paid_to_date")
    if not 0 <= quarters_elapsed <= 4:
        raise ToolError("quarters_elapsed must be 0-4")
    thr = D(high_income_threshold, "high_income_threshold")
    hp = D(high_income_pct, "high_income_pct") / 100
    prior_pct = hp if agi > thr else Decimal(1)
    prior_based = prior * prior_pct
    current_based = cur * Decimal("0.9")
    required = min(prior_based, current_based)
    basis = "prior-year" if prior_based <= current_based else "current-year 90%"
    wh = require_nonneg(D(withholding, "withholding"), "withholding")
    if cur - wh < 1000:
        required = ZERO
        basis = "no estimated tax required (projected tax minus withholding is under $1,000 — verify)"
    per_q = required / 4
    should_have_paid = per_q * quarters_elapsed
    shortfall = max(should_have_paid - paid, ZERO)
    remaining = max(required - paid, ZERO)
    q_left = 4 - quarters_elapsed
    return {
        "prior_year_basis": {"pct": float(prior_pct * 100), "amount": money(prior_based), "high_income_rule_applied": agi > thr},
        "current_year_basis": {"pct": 90, "amount": money(current_based)},
        "required_annual_payment": money(required),
        "basis": basis,
        "per_quarter": money(per_q),
        "paid_to_date": money(paid),
        "should_have_paid_by_now": money(should_have_paid),
        "shortfall_now": money(shortfall),
        "remaining_to_reach_safe_harbor": money(remaining),
        "per_remaining_quarter": money(remaining / q_left) if q_left else None,
        "on_track": shortfall == 0,
        "gap_to_full_current_year": money(max(cur - required, ZERO)),
        "verdict": (
            f"Safe harbor = ${money(required):,.0f} ({basis}); ${money(per_q):,.0f}/quarter. "
            + ("On track — " if shortfall == 0 else f"Behind by ${money(shortfall):,.0f} — catch up with the next payment; ")
            + (f"pay ${money(remaining / q_left):,.0f} in each of the {q_left} remaining quarter(s)." if q_left else "all quarters passed.")
            + (f" Note: safe harbor leaves ${money(max(cur - required, ZERO)):,.0f} of this year's tax due in April — budget for it." if cur > required else "")
        ),
        "scope_note": SCOPE_NOTE,
    }


DEDUCTION_RULES = {
    "meals": ("50% deductible (business meals)", Decimal("0.5")),
    "entertainment": ("not deductible", ZERO),
    "home_office": ("simplified method: rate per sq ft up to the cap", None),
    "mileage": ("standard mileage rate x business miles", None),
    "equipment": ("100% (Section 179 / de minimis, within limits)", Decimal(1)),
    "software": ("100%", Decimal(1)),
    "phone": ("business-use % of the bill", Decimal(1)),
    "internet": ("business-use % of the bill", Decimal(1)),
    "health_insurance": ("100% above the line (self-employed health insurance, within net-profit limit)", Decimal(1)),
    "retirement": ("SEP/Solo 401k contribution within limits", Decimal(1)),
    "education": ("100% if it maintains/improves current skills", Decimal(1)),
    "travel": ("100% (lodging, airfare); meals on the road at 50%", Decimal(1)),
    "other": ("100% if ordinary and necessary", Decimal(1)),
}


@AGENT.tool
def deduction_value(
    expenses: list[dict],
    marginal_income_rate_pct: float,
    se_rate_effective_pct: float = 14.13,
    home_office_rate_per_sqft: float = 5,
    home_office_max_sqft: int = 300,
    mileage_rate: float = DEFAULT_MILEAGE_RATE,
) -> dict:
    """Apply deduction rules to a list of expenses and value each at the marginal income + SE rate.

    Types: meals (50%), entertainment (0%), home_office (sq ft × rate, capped), mileage (miles × rate),
    equipment, software, phone/internet (× business_use_pct), health_insurance, retirement, education,
    travel, other. Tax saved = deductible × (marginal income rate + effective SE rate).

    Args:
        expenses: List of {"type": str, "amount": n, "description": str (optional), "business_use_pct": n (optional, default 100), "sqft": n (home_office), "miles": n (mileage), "rate": n (mileage only, $/mile override for that row)}.
        marginal_income_rate_pct: Income-tax saving per deductible dollar — use quarterly_estimate's for_deduction_value.marginal_income_rate_pct (bracket rate after the half-SE and 20% QBI effects, e.g. 16.36 in the 22% bracket), not the raw bracket rate.
        se_rate_effective_pct: Effective SE tax saved per deductible dollar (15.3% × 0.9235 ≈ 14.13%; 2.68 above the SS wage base) — use quarterly_estimate's for_deduction_value.se_rate_effective_pct.
        home_office_rate_per_sqft: Simplified-method rate per square foot (default 5; verify current IRS figure).
        home_office_max_sqft: Simplified-method cap in square feet (default 300; verify).
        mileage_rate: Standard mileage rate in dollars per mile (default 0.725 = 2026 Jan-Jun rate; 0.76 applies Jul-Dec 2026 — give a mileage item its own "rate" to split; verify current IRS figure).
    """
    rows = bound_rows(expenses, "expenses", limit=300)
    inc = as_pct(marginal_income_rate_pct, "marginal_income_rate_pct")
    se = as_pct(se_rate_effective_pct, "se_rate_effective_pct")
    if not 0 <= inc <= Decimal("0.6") or not 0 <= se <= Decimal("0.2"):
        raise ToolError("marginal_income_rate_pct must be 0-60 and se_rate_effective_pct 0-20")
    ho_rate = D(home_office_rate_per_sqft, "home_office_rate_per_sqft")
    mi_rate = D(mileage_rate, "mileage_rate")
    combined = inc + se
    out, total_claimed, total_ded = [], ZERO, ZERO
    for i, e in enumerate(rows, 1):
        if not isinstance(e, dict):
            raise ToolError(f"expenses[{i}] must be an object")
        etype = str(e.get("type", "other")).lower().strip().replace(" ", "_")
        if etype not in DEDUCTION_RULES:
            raise ToolError(f"expenses[{i}]: unknown type {etype!r}; use one of {sorted(DEDUCTION_RULES)}")
        rule, factor = DEDUCTION_RULES[etype]
        use = as_rate(e.get("business_use_pct", 100), f"expenses[{i}].business_use_pct")
        if not 0 <= use <= 1:
            raise ToolError(f"expenses[{i}]: business_use_pct must be 0-100")
        amount = require_nonneg(D(e.get("amount", 0), f"expenses[{i}].amount"), f"expenses[{i}].amount")
        note = rule
        if etype == "home_office":
            sqft = int(e.get("sqft", 0))
            if sqft <= 0:
                raise ToolError(f"expenses[{i}]: home_office needs 'sqft'")
            used = min(sqft, home_office_max_sqft)
            deductible = ho_rate * used
            amount = deductible
            if sqft > home_office_max_sqft:
                note += f" (capped at {home_office_max_sqft} sq ft)"
        elif etype == "mileage":
            miles = D(e.get("miles", 0), f"expenses[{i}].miles")
            if miles <= 0:
                raise ToolError(f"expenses[{i}]: mileage needs 'miles'")
            row_rate = D(e["rate"], f"expenses[{i}].rate") if e.get("rate") not in (None, "") else mi_rate
            if not 0 < row_rate < 5:
                raise ToolError(f"expenses[{i}]: mileage rate looks wrong ({row_rate}); give dollars per mile like 0.725")
            deductible = miles * row_rate * use
            amount = deductible
            note = f"{rule} ({money(miles):,.0f} mi x ${row_rate}/mi)"
        else:
            deductible = amount * factor * use
            if use < 1:
                note += f" at {ratio_to_pct(use)}% business use"
        # above-the-line items do not reduce SE tax (nor the half-SE deduction), so their income-tax rate is inc / (1 - se/2)
        saved = deductible * combined if etype not in ("health_insurance", "retirement") else deductible * inc / (1 - se / 2)
        if etype in ("health_insurance", "retirement"):
            note += " — reduces income tax only, not SE tax"
        out.append({"type": etype, "description": e.get("description", ""), "claimed": money(amount), "deductible": money(deductible), "tax_saved": money(saved), "rule": note})
        total_claimed += amount
        total_ded += deductible
    total_saved = sum(Decimal(str(r["tax_saved"])) for r in out)
    return {
        "items": out,
        "total_claimed": money(total_claimed),
        "total_deductible": money(total_ded),
        "total_tax_saved": money(total_saved),
        "rate_used_pct": ratio_to_pct(combined),
        "verdict": f"${money(total_ded):,.0f} deductible of ${money(total_claimed):,.0f} claimed → about ${money(total_saved):,.0f} in tax saved at a {ratio_to_pct(combined)}% combined marginal rate (not dollar-for-dollar).",
        "scope_note": SCOPE_NOTE,
    }


def _observed(d: date) -> date:
    """Federal observance: a Saturday holiday is observed Friday, a Sunday holiday Monday."""
    return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d


def _holidays(year: int) -> set[date]:
    """Holidays that can move a 1040-ES due date: DC Emancipation Day (Apr 16, observed) and MLK Day (3rd Monday of January)."""
    jan1 = date(year, 1, 1)
    first_monday = jan1 + timedelta(days=(7 - jan1.weekday()) % 7)
    return {_observed(date(year, 4, 16)), first_monday + timedelta(days=14)}


def _next_business_day(d: date) -> date:
    hol = _holidays(d.year)
    while d.weekday() >= 5 or d in hol:
        d += timedelta(days=1)
    return d


@AGENT.tool
def payment_deadlines(tax_year: int, as_of: str = "", annual_amount: float = 0) -> dict:
    """The four federal estimated-tax due dates for a tax year (weekend-adjusted), periods covered, and days remaining.

    Due dates: Apr 15, Jun 15, Sep 15 of the tax year and Jan 15 of the next, rolled to the next
    business day past weekends, DC Emancipation Day (observed) and MLK Day — verify with the IRS
    (disaster-area postponements are not modelled).

    Args:
        tax_year: The tax year, e.g. 2026.
        as_of: Today's date YYYY-MM-DD; defaults to today.
        annual_amount: Optional total estimated payment for the year, split into four for the table.
    """
    if not 2000 <= tax_year <= 2100:
        raise ToolError("tax_year must be between 2000 and 2100")
    today = parse_iso(as_of, "as_of") if as_of else date.today()
    amt = require_nonneg(D(annual_amount, "annual_amount"), "annual_amount")
    spec = [
        (1, date(tax_year, 4, 15), f"Jan 1 – Mar 31 {tax_year}"),
        (2, date(tax_year, 6, 15), f"Apr 1 – May 31 {tax_year}"),
        (3, date(tax_year, 9, 15), f"Jun 1 – Aug 31 {tax_year}"),
        (4, date(tax_year + 1, 1, 15), f"Sep 1 – Dec 31 {tax_year}"),
    ]
    rows, nxt = [], None
    for q, d, period in spec:
        due = _next_business_day(d)
        days = (due - today).days
        status = "past" if days < 0 else "due today" if days == 0 else "upcoming"
        row = {"quarter": q, "period": period, "due": due.isoformat(), "weekday": due.strftime("%a"), "days_remaining": days, "status": status, "amount": money(amt / 4) if amt else None, "adjusted_from_15th": due != d}
        rows.append(row)
        if nxt is None and days >= 0:
            nxt = row
    passed = sum(1 for r in rows if r["status"] == "past")
    return {
        "tax_year": tax_year,
        "as_of": today.isoformat(),
        "deadlines": rows,
        "next": nxt,
        "quarters_elapsed": passed,
        "note": "Weekends, DC Emancipation Day and MLK Day are applied; disaster postponements are not — verify the exact date on IRS.gov. Income earned in each period is what the payment covers; use the annualised method if income is lumpy.",
        "verdict": (f"Next: Q{nxt['quarter']} due {nxt['due']} ({nxt['weekday']}), {nxt['days_remaining']} days away" + (f", ${nxt['amount']:,.0f}" if nxt["amount"] else "") + f". {passed} of 4 deadlines passed.") if nxt else f"All four {tax_year} deadlines have passed; file and pay any balance with the return.",
    }
