# Finance & Money — parity evals

**Date:** 2026-09-27 · **Scope:** all 9 agents in `hundred/agents/finance/` · **Regression suite:** `tests/scenarios/test_finance.py` (13 scenario tests), plus updated and new unit tests in `tests/agents/test_finance_*.py`.

**How to read this.** We can't run the competitors, so each agent is compared with the **documented** capabilities of the paid tool whose job overlaps most. Sources are cited in each section. For each agent I wrote a realistic scenario, ran it the way a customer's AI would, and produced the deliverable in the playbook's Output format. The run order was `hundred.admin brief <slug>`, then the playbook's procedure, then `hundred.admin run <slug> <tool> -` for each step.

Every figure was then recomputed independently with scripts that don't import `hundred`. They use plain `Decimal`/`Fraction` code:
- the annuity formula and month-by-month debt rollover;
- hand placement of calendar dates into 13 weekly buckets;
- the IRS 2026 brackets typed in from Rev. Proc. 2025-32;
- Van Westendorp empirical CDFs, with a 1-cent step-curve brute force as a cross-check;
- a hand-labelled ground truth for the 60-row bank export.

"Out of scope" (OOS) means the check needs a bank or ledger feed, auto-sync, sending, a hosted dashboard over time, or filing. These aren't counted as failures.

Prices come from `marketing/pricing_research/ops_finance_legal.md` (seen 2026-09-27), except Conjointly, which I fetched.

## Overview

Checklist columns: M = matches · P = partial · X = missing · OOS = out of scope.

| Agent | Comparable & price | Checklist (M / P / X / OOS) | Correctness checks (after fixes) | Verdict on the overlapping job | Fixes shipped |
|---|---|---|---|---|---|
| cashflow-forecaster | Float Essentials, $130/mo | 4 / 2 / 1 / 2 | 66/66. That's 39 weekly cells, the low point, 5 stress scenarios × 4 fields, runway/break-even and variance. | **AT PAR** | A 26-week horizon dropped every monthly item after month 5 (4 of 6 rents). Runway calendar labels were one month late. Stress test now reports buffer breaches. "Outflow short" wording for overspend |
| invoice-chaser | Chaser Compact, $259/mo | 2 / 3 / 1 / 2 | 11/11: aging buckets, DSO, chase order, 3 fee methods to the cent | **AT PAR** on deciding who to chase, what to charge and what to send. Automation is OOS | The dunning tool told the AI to open with the **final notice** when nothing had been sent. Added `touches_sent` and catch-up compression; fixed stale subject lines |
| pricing-strategist | Conjointly Van Westendorp, Professional $2,895/yr (≈ $241/mo) | 2 / 3 / 1 / 1 | 12/12. That's 4 PSM points (plus 4 step-curve cross-checks), 3 arc elasticities and the break-even. | **AT PAR** on the PSM band. **BELOW** on the Newton-Miller-Smith extension | PMC/PME used the inverted reading while Conjointly/Wikipedia use expensive/cheap. The band was $21.43–59.33 instead of $29–48; the default now matches, and the original stays as an option. The elasticity verdict said "price rises grow revenue" through an elastic segment. `price_change_pct` below 1 was read as a fraction |
| unit-economics | ChartMogul Pro, $99/mo (annual) | 4 / 1 / 0 / 1 | 26/26, including ChartMogul's published LTV example ($100 / 5% = $2,000) | **AT PAR** | **Expansion of 0.6% was read as 60%.** That capped lifetime and overstated LTV by 44% ($40,046 vs $27,810; LTV/CAC 6.42 vs 4.46). Any churn or discount rate below 1% had the same bug |
| budget-coach | YNAB, $14.99/mo (+ Undebt.it for the snowball/avalanche comparison) | 5 / 1 / 0 / 2 | 41/41: both payoff methods month by month, the annuity check, the 50/30/20 buckets, savings and DTI | **AT PAR** | Payoff dates were one month late. The DTI verdict was wrong when only the front-end ratio failed ("back-end 33.3% is over 36% … cut $-240"). Loan `total_paid` was overstated by a full payment. APR/APY below 1% (0.9% promo) was read as 90%. Savings goal now takes a `start_date` |
| startup-model | LivePlan Standard, $20/mo | 4 / 1 / 2 / 1 | 63/63: 24 MRR months, 24 burn months, runway, sensitivity, raise | **AT PAR** on the driver model → runway → raise. **BELOW** on three-statement output | Month labels were one month late. Steady-state MRR ignored expansion ($774k vs $1.29M). Churn/expansion/growth below 1% were misread |
| expense-categorizer | Monarch Money, $14.99/mo (Keeper and QuickBooks Solopreneur for categorisation) | 3 / 3 / 0 / 2 | 110/110 on the scenario. Held-out library coverage is **24/32 (75%)**, and the 8 misses were all sent to review, none confidently wrong | **AT PAR** with the playbook's review-and-rule loop. **BELOW** unattended on unknown merchants (no merchant database) | 5 confident mis-categorisations and 6 misses out of 60, from regex order and word boundaries (Uber Eats→Travel, Enterprise Rent-A-Car→Rent, Delta Dental→Travel). Merchant names lost the real merchant behind `SQ *`/`PAYPAL *`. Refunds were counted as income. Usage-billed AWS wasn't recurring. 14 of 23 anomaly flags were auto-billed SaaS noise |
| freelance-tax | Keeper, $20/mo (quarterly tax calculator) | 5 / 2 / 2 / 1 | 23/23. Deduction value is within $0.33 of a full re-run of the return | **AT PAR** federal. **BELOW** on state tax (flat placeholder) | Defaults were 2025 pre-OBBBA figures; they're now the **2026** IRS/SSA figures, labelled "estimate; verify". For $95k single the old total was $21,235.84 against a correct $20,840.24. Deduction value was overstated by about 18% (bracket + 14.13% ignored the half-SE and QBI effects). Additional Medicare was wrongly in the half-SE deduction. Holiday-aware deadlines (Emancipation Day, MLK). Mileage 72.5¢/76¢ split |
| investor-update | Visible.vc Base, $69/mo | 3 / 1 / 0 / 3 | 14/14: MoM/YoY deltas, CMGR, trend, runway and cash-out month | **AT PAR** on writing the update. Sending, tracking and data room are OOS | The cash-out month was truncated a month early (2028-02 vs 2028-03). `$-45,000` formatting. ▲ was used for a *falling* churn number (arrow meant favourable). The playbook said 9 months where the tool says 12 |

**Test summary (final run):**
- `python -m pytest -q tests/agents -k finance tests/scenarios/test_finance.py`: **72 passed**
- `python -m pytest -q tests/test_library.py`: **303 passed**
- Full suite `python -m pytest -q tests`: 1688 passed

**Category-wide finding.** The root cause of the worst bugs sat in `_common.as_rate`. Its rule was "values below 1 are fractions", so 0.6 meant 60%. Six agents used it for rates where sub-1% values are normal: monthly churn and expansion, MoM growth, promo APRs, savings APYs, fees and discount rates. I added `_common.as_pct`, where the value is always a percent, and moved every such parameter to it. `as_rate` stays only for shares where a sub-1% value is implausible: gross margin, business-use %, ownership, drop %.

**Outside my edit scope (not changed).** Nothing in `hundred/core.py` or `hundred/lib/` produced a wrong number. One cosmetic issue: `hundred/admin.py brief` raises `BrokenPipeError` when piped into `head`.

---

## 1. Cash Flow Forecaster — vs Float

**Scenario.** "Loomwise" is a 24-person B2B SaaS. Week 1 starts Mon 2026-09-28, with $412,500 of opening cash and a buffer of one month of payroll ($136,800). Outflows:
- semimonthly payroll of $68,400 on the 15th and the month-end (the 31st clamps to the 30th);
- rent of $11,200 on the 1st;
- AWS $6,850 on the 5th, loan $3,750 on the 10th, SaaS tools $2,900 on the 20th;
- biweekly contractors, $4,200;
- one-offs: D&O insurance $14,600 and a Q4 bonus of $22,000.

Inflows:
- weekly Stripe payouts of $9,800;
- a signed $45,000 prepay;
- eight open AR invoices, from 90 days overdue to not yet due, run through `collections_forecast` with customers paying 12 days late on average.

Then I ran runway (revenue $128k growing 4%/mo, expenses $170.6k growing 1%/mo), a stress test and last week's variance review.

**Checklist** (Float: <https://floatapp.com/features/>).

| Float capability (documented) | Status | Notes |
|---|---|---|
| "Monthly and Weekly views", with 13-week operational planning | M | Direct-method weekly table, 4–26 weeks |
| "Lowest projected cash balance across the forecast window" | M | `low_point`, plus buffer-breach weeks and weeks of visibility |
| Scenario toggling ("see the cash impact of any decision") | M | Five standard shocks, plus a re-run of the forecast with any edited item |
| AR "expected… payment dates reflecting actual client behavior" | P | `collections_forecast` uses one average days-late figure and aging-bucket probabilities. Float learns this per client |
| Budget vs actuals | M | `variance_review` with dual tolerances and accuracy score |
| CSV/PDF export | P | Markdown table; the AI can emit CSV. No PDF |
| Multi-entity consolidation | X | One entity per run |
| Automatic identification of recurring costs from the ledger | OOS | Ledger feed |
| Auto-updating sync every 24h | OOS | Ledger feed |

**Correctness (independent recompute: `verify_cashflow.py`, no `hundred` imports).**

| Check | Result |
|---|---|
| All 39 weekly cells (in / out / closing), with every calendar date placed by hand | 39/39 exact. Payroll lands in weeks 1, 3, 5, 7, 10, 12; Sep "31st" → Sep 30; Dec 31 is outside the horizon |
| Low point | Week 12 (2026-12-14), $212,572.00 ✓ |
| Collections | $246,786.00 of $258,650.00 face value expected in horizon. The 90-day-late INV-2008 (61–90 bucket × 60%) gives $5,760 ✓ |
| Stress, 5 scenarios × (min, week, ending, first week under buffer) | 20/20. Combined: min $26,415.00 in week 12, under the buffer from week 6 |
| Runway, month-by-month compounding | Simple runway 9.7 months ✓. Break-even in month 11 = **2027-08** (the tool said 2027-09 before the fix) |
| Variance | Net −$16,390.00; inflow accuracy 77.2%, outflow accuracy 95.9% ✓ |
| 26-week horizon | **Failed before the fix:** only 4 of 6 monthly rents were placed. Now 6/6 |

**Deliverable excerpt.**
```
# 13-week cash forecast — week of 2026-09-28
**Opening cash:** $412,500 · **Low point:** $212,572 in week 12 (2026-12-14) · **Buffer:** $136,800 · **Runway:** 9.7 months on net burn of $42,600 (gross $170,600) · **Default:** alive (break-even 2027-08)

## Weekly view
| Wk | Week of | Inflows | Outflows | Net | Closing | vs buffer |
| 1 | 2026-09-28 | 48,940 | 83,800 | -34,860 | 377,640 | +240,840 |
| 3 | 2026-10-12 | 9,800 | 72,600 | -62,800 | 331,615 | +194,815 |
| 7 | 2026-11-09 | 9,800 | 76,350 | -66,550 | 246,340 | +109,540 |
| 12 | 2026-12-14 | 9,800 | 93,300 | -83,500 | 212,572 | +75,772 |
| 13 | 2026-12-21 | 72,814 | 4,200 | +68,614 | 281,186 | +144,386 |

## Stress scenarios
| Scenario | Min cash | Week | Under buffer from | Below zero? |
| Collections +3 wks | 152,790 | 10 | — | no |
| Revenue −25% | 125,979 | 12 | wk 12 | no |
| Surprise payroll (wk 4) | 144,172 | 12 | — | no |
| Combined | 26,415 | 12 | wk 6 | no |

## Variance (w/c 2026-09-21)
Collections came in $13,550 short (26.1%) and vendors ran $3,380 over forecast (35.6%). Net −$16,390. Collections assumption moved from due date to +12 days.

## Levers (ranked by speed)
1. Chase INV-2027/INV-2019 now: $50,955 expected in wk 1–2 → protects the wk-6 buffer in the combined case
```

**Traps in this scenario the tools handled** (no plain-AI run; these are traps in the data):
- a month-end payroll on a 30-day month;
- the Nov 15 payroll and the Nov 1 rent both fall on a Sunday, which keeps them in the same week;
- a 90-day-late invoice that shouldn't be counted at face value;
- a combined shock that stays above zero but breaches the one-payroll buffer from week 6. Before the fix the stress verdict said "Base plan survives every shock".

**Honest gaps.**
- There are no per-customer payment patterns and no weekend or holiday shift for payroll dates. Both Sunday dates above stay in the same week, but a Saturday month-end could move a payroll across a week boundary.
- Multi-entity consolidation isn't modelled.

---

## 2. Invoice Chaser — vs Chaser

**Scenario.** As of 2026-09-28 there are nine open invoices. One is fully paid, one partly paid, and they run from 121 days overdue to not yet due. Trailing 90-day credit sales are $412,000 on net-30. The top chase is INV-1042: $8,500, due 2026-08-15, 1.5%/month late fee with a 10-day grace. Two of six reminders have gone out.

**Checklist** (Chaser: <https://www.chaserhq.com/features>, late fees: <https://help.chaserhq.com/apply-late-fees>).

| Chaser capability (documented) | Status | Notes |
|---|---|---|
| Multi-touch escalation with customisable templates | M | Dated ladder (business-day adjusted), tone per touch, subject lines, plus a lint for every message |
| "Custom cadences based on individual customer payment habits" | P | Custom offsets per invoice; no learning from history |
| Aged debt reports | M | Buckets, concentration, and a chase list ranked by amount × days |
| DSO tracking | P | Point-in-time DSO against terms. The trend over time is OOS |
| Late fees: "fixed, percentage, interest-accruing, benchmark-based"; from due date or issue date | P | Flat, monthly %, annual % daily, compounding, grace and cap. There's no issue-date basis and no automatic base-rate tracking, and UK statutory fixed compensation isn't modelled |
| AI late-payment prediction | X | We only rank by exposure |
| Automated email, SMS and calls; payment portal/links | OOS | Sending and payments |

**Correctness (`verify_ic.py`).**
- Buckets: current $28,500 / 1–30 $45,150 / 31–60 $8,500 / 61–90 $4,200 / 90+ $3,800. Total $90,150.00 ✓.
- DSO 19.7 days ✓.
- Chase order: 6/6 ✓.
- Late fee, simple over 34 chargeable days: $144.50. At 18% p.a. over 44 days: $184.44. Compounded (1 month + 14 days): $187.89. All ✓ to the cent.

**The bug that mattered.** `dunning_schedule` only knew the calendar, and at 44 days late the calendar says "final notice". The playbook says "a final notice as the first message destroys goodwill", but the tool had no way to know what had actually been sent. With the new `touches_sent=2`, it sends touch 3 ("second notice, firm") today and re-spaces the rest a week apart: Oct 5, 12 and 19. It also rewrites the subject lines: "44 days past due" instead of the hard-coded "7 days", and a referral date after the escalation email instead of before it.

**Deliverable excerpt.**
```
# Collections brief — 2026-09-28
**Open AR:** $90,150 across 8 invoices · **Over 60 days:** 8.9% · **DSO:** 19.7 days (terms: net-30)

## Chase list (today)
| # | Customer | Invoice | Amount | Days late | Touch due | Late fee |
| 1 | Brightline Media | INV-1042 | $8,500 | 44 | 3 of 6 (catch-up) | $144.50 per agreement |
| 2 | Oakridge Dental | INV-1038 | $4,200 | 80 | call | per agreement |
| 3 | Brightline Media | INV-1029 | $3,150 | 100 | call (90+: write-off risk) | per agreement |

## Message — second notice for INV-1042   (lint 100/100, 111 words)
Subject: Overdue: invoice INV-1042 ($8,500.00) — 44 days past due
Invoice INV-1042 for $8,500.00 was due on 2026-08-15 and is now 44 days past due…
Please remit $8,500.00 by Friday 2 October using the payment link below…

## Schedule for INV-1042
| Touch | Date | Channel | Tone |
| 3 second notice | 2026-09-28 | email | firm |
| 4 call + email | 2026-10-05 | phone | firm |
| 5 final notice | 2026-10-12 | email | formal |
| 6 escalation (referral 2026-11-03) | 2026-10-19 | email | consequence |
```

**Honest gaps.**
- Chaser's value is the automation: it sends from the AR ledger, runs a payment portal and predicts late payers. We draft and schedule; the customer sends.
- There are no statutory UK fixed-sum late fees and no issue-date fee basis.

---

## 3. Pricing Strategist — vs Conjointly Van Westendorp

**Scenario.** A project-management SaaS at $49/month with a 78% gross margin and 1,180 customers.
- **Survey:** 40 Van Westendorp responses, 2 of them inconsistent.
- **Price history:** $29 → 412 signups/mo, $39 → 355, $49 → 290, and a $59 test cell → 221. Unit cost is $10.80.
- **Question:** raise to $59 (+20.4%)? Build the tier ladder.

**Checklist** (Conjointly product page: <https://conjointly.com/products/van-westendorp/>; pricing: <https://conjointly.com/pricing/>; definitions: <https://en.wikipedia.org/wiki/Van_Westendorp%27s_Price_Sensitivity_Meter>).

| Conjointly capability (documented) | Status | Notes |
|---|---|---|
| PMC, PME, OPP, IPP from the four questions | M | **After the fix.** Conjointly uses "non-inverted cumulative frequency lines" (PMC = too cheap × expensive, PME = too expensive × cheap). We used the original inverted reading. The default now matches, and `convention="not_cheap_not_expensive"` keeps the original |
| Acceptable price range | M | PMC–PME |
| PSM chart | P | Tables only; the AI can chart them |
| Price elasticity chart and revenue vs price chart | P | From observed price/volume history, not from the survey |
| Segmentation and comparison | P | One run per segment |
| Newton-Miller-Smith extension (purchase likelihood → revenue-max price) | X | Not implemented |
| Survey fielding, 30+ languages, panel | OOS | |

**Correctness (`verify_ps.py`, exact `Fraction` arithmetic).**

| Point | Tool | Independent | 1¢ step-curve crossing |
|---|---|---|---|
| PMC | 29.00 | 29 | 29.00 |
| OPP | 30.00 | 30 | 29.01 |
| IPP | 39.00 | 39 | 39.00 |
| PME | 48.00 | 48 | 49.00 (the step curves cross at the next quoted price; interpolation gives 48. Both are defensible, so readings differ by up to one price step) |

The original inverted reading gives $21.43–59.33. That's the band the tool **used to report as the answer**, and it's 2.3× wider than Conjointly's reading of the same data.

The rest also checks out:
- Arc elasticities: −0.51, −0.89, −1.46 ✓.
- Break-even volume change for +20.4% at a 78% margin: −20.73% (935.4 units) ✓.

**The bug that mattered.** The elasticity verdict averaged the segments (−0.95) and said "Demand is inelastic… price rises grow revenue". But the move under discussion, $49 → $59, crosses the elastic segment (−1.46), and revenue fell from $14,210 to $13,039. The verdict now reports where demand turns elastic. The playbook tells the AI to judge a change by the segment it crosses.

**Deliverable excerpt.**
```
# Pricing recommendation — Loomwise Projects
**Recommended:** hold $49/workspace/month · **Acceptable band:** $29–$48 (OPP $30, IPP $39; expensive/cheap reading) · **Confidence:** medium (n=38)

## Ladder
| Tier | Monthly | Annual (per month) | For whom |
| Starter | $19 | $15 | solo / trial-to-paid |
| Pro | $49 | $40 | teams (target tier) |
| Business | $109 | $90 | multi-team, SSO/audit |

## The bet
Change: +20.4% to $59 · Break-even volume change: −20.7% (keep ≥ 935 of 1,180 customers)
Evidence: the $59 test cell lost 23.8% of volume (290 → 221) — past break-even; demand turns elastic above $49.
Gross profit impact of the raise at the observed loss: negative. Do not ship.

## Rollout & test
- Launch the ladder to new customers 2026-10-15; existing Pro customers keep $49.
- Test Business at $109 vs $129 on new signups; ship $129 only if Business mix stays ≥ 15%.
```

**Honest gaps.**
- There's no Newton-Miller-Smith extension, which Conjointly recommends turning on.
- Below 30 responses the band is directional only; the playbook says so.

---

## 4. Unit Economics — vs ChartMogul

**Scenario.**
- A mid-market SaaS: ARPA $412, gross margin 81%, monthly logo churn 1.8%, expansion 0.6%/mo, CAC $6,240, discount rate 12%.
- Year retention: start ARR $4.86M, churned $388.8k, contraction $97.2k, expansion $631.8k, new $1.215M. Logos: 980 at start, 212 churned.
- Six monthly cohorts.
- Contribution per account and break-even against $310k/mo fixed costs.
- Quarterly efficiency: net new ARR $285k, prior-quarter S&M $1.46M, burn $620k.

**Checklist** (ChartMogul help: LTV <https://help.chartmogul.com/hc/en-us/articles/203359061-Chart-Customer-Lifetime-Value-LTV>, Net MRR retention <https://help.chartmogul.com/article/143-chart-net-mrr-retention>, Gross MRR retention <https://help.chartmogul.com/hc/en-us/articles/6886621218332-Chart-Gross-MRR-Retention>, cohorts <https://help.chartmogul.com/article/161-cohort-analysis>).

| ChartMogul capability (documented) | Status | Notes |
|---|---|---|
| LTV = ARPA ÷ churn rate (6-month trailing churn) | M | Reproduces the published example exactly ($100 / 5% = $2,000). We also give gross-margin LTV and discounted LTV. The trailing average must be supplied |
| Net MRR retention = (start + expansion + reactivation − contraction − churn) ÷ start | P | There's no separate reactivation input; it has to be added to expansion |
| Gross MRR retention | M | |
| Cohort retention tables | M | Plus an average curve and a flattening test |
| Customer churn rate | M | Logo churn % |
| Metrics computed automatically from billing data | OOS | Billing sync |

**Correctness (`verify_ue.py`).**
- LTV (gross margin) = 333.72 / (1.8% − 0.6%) = **$27,810.00**. LTV/CAC is 4.46×, and payback is 18.7 months.
- Discounted LTV is $15,169.09. It matches a 20,000-term brute-force series to within $0.01.
- GRR 90.0%, NRR 103.0%, quick ratio 3.8, logo churn 21.6%.
- Contribution $300.09 (72.8%), break-even 1,034 units, operating profit $8,097.52.
- Magic number 0.78, burn multiple 2.18, Rule of 40 = 26.
- Cohort averages m1/m3/m6 are 89.9/80.1/75.7.

All 26 match.

**Before the fix** `monthly_expansion_pct=0.6` was parsed as 60%. That made net churn negative and capped lifetime at 120 months, so the tool reported LTV $40,046 and LTV/CAC 6.42× with a "Healthy" verdict. That's 44% too high. The same bug turned 0.8% enterprise churn into 80% (a 1.25-month lifetime).

**Deliverable excerpt.**
```
# Unit economics — Loomwise mid-market — FY to Sep 2026
| Metric | Value | Formula | Benchmark | Status |
| LTV (GM) | $27,810 | ARPA×GM÷(churn−expansion) | — | |
| LTV/CAC | 4.46x (2.43x discounted @12%) | | ≥3x | ✓ (✗ discounted) |
| CAC payback | 18.7 mo | CAC÷(ARPA×GM) | ≤18 | ✗ |
| GRR / NRR | 90.0% / 103.0% | | ≥85% / ≥110% | ✓ / ✗ |
| Burn multiple | 2.18x | burn÷net new ARR | <2 | ✗ |

## Diagnosis
Payback (18.7 mo) and burn multiple (2.18) are the constraint, not retention: GRR is 90% and cohorts
still lose ~1 pt/month after month 5. CAC of $6,240 against $334/mo gross profit is the lever.

## Levers
1. Annual prepay at 2 months free — moves payback from 18.7 toward ~7 months of cash
2. Expansion packaging — NRR 103% → 110% needs +$340k expansion/yr
```

**Honest gaps.**
- There's no reactivation field, and nothing is computed from raw subscription data.
- The cohort late-slope uses the average curve, and the oldest months rest on 1–2 cohorts.

---

## 5. Budget Coach — vs YNAB (and Undebt.it for multi-debt strategy)

**Scenario.**
- **Income and spending:** $5,850 take-home; 13 expense lines, needs at 70.8%.
- **Debts, $450/mo extra, first payment 2026-10-01:** Chase Sapphire $6,840 @ 27.49% (min $205), Discover $2,315 @ 22.99% (min $70), Honda auto $14,200 @ 7.9% (min $385), federal student loan $22,600 @ 5.5% (min $245).
- **Emergency fund:** $12,417 target (3× needs), starting from $2,400, at 4.2% APY.
- **Car loan question:** $28,500 @ 6.9% for 60 months, and what $100 extra a month does.
- **Mortgage question:** is a $2,350 PITI affordable on $8,100 gross?

**Checklist** (YNAB: <https://www.ynab.com/features/debt-management>, <https://www.ynab.com/blog/ynab-loan-planner>; Undebt.it: <https://undebt.it/pricing-features-reviews.php>).

| Capability (documented) | Status | Notes |
|---|---|---|
| YNAB Loan Planner: extra payment → time and interest saved | M | `loan_payment.with_extra`: 10 months and $947.82 saved |
| Payoff dates and remaining-balance projection | M | Per-debt payoff month plus a balance curve |
| YNAB Targets: savings goals with guidance | M | Solves for months or for the contribution, with monthly compounding |
| Undebt.it: snowball vs avalanche side by side with interest and dates | M | Both methods plus minimums-only |
| Budgeting method | P | 50/30/20 scoring with dollar gaps. YNAB's zero-based envelope assignment isn't modelled |
| Credit-card payment category mechanics | OOS | Ledger mechanics |
| Net worth and reports over time | OOS | Dashboards |

**Correctness (`verify_budget.py`).** An independent month-by-month rollover sim, written with a different structure (a fixed budget pool), agrees to the cent:

| Output | Avalanche | Snowball |
|---|---|---|
| Months / total interest | 39 / $6,125.03 | 39 / $6,239.49 |
| Paid off (month) | Chase 13, Discover 15, Honda 24, Student 39 | Discover 5, Chase 16, Honda 24, Student 39 |
| Minimums only | 121 months / $16,594.45 | same |
| Debt-free date (payment 39) | **2029-12** (the tool said 2030-01 before the fix) | 2029-12 |

The other tools:
- **Loan:** the annuity formula gives $562.99 ✓. Total interest $5,279.46 with a final payment of $563.05. **Before the fix** `total_paid` was $34,342.39 (61 payments) instead of $33,779.46.
- **Savings:** 40 months ✓. The closed form gives n = 39.27, so the goal is reached in month 40.
- **DTI:** front-end 29.0%, back-end 40.2%, over by $82 and $339 ✓. **Before the fix**, a 30%/33.3% case printed "back-end 33.3% is over 36% … cut $-240.00".

**Deliverable excerpt.**
```
# Budget plan — October 2026
**Take-home:** $5,850 · **Needs:** $4,139 (70.8% vs 50%) · **Wants:** $1,031 (17.6% vs 30%) · **Savings/debt:** $200 (3.4% vs 20%)
**Verdict:** $480/month unallocated; needs are a fixed-cost problem (rent + $905 of minimums), so the lever is the debt, not the coffee.

## Debt plan — avalanche  (snowball costs $114.46 more, 1.9% — within 10%, so snowball is acceptable if motivation matters)
Extra payment: $450/month → debt-free 2029-12, total interest $6,125.03 (vs $16,594.45 paying minimums for 121 months)
| # | Debt | Balance | APR | Paid off |
| 1 | Chase Sapphire | $6,840 | 27.49% | 2027-10 |
| 2 | Discover It | $2,315 | 22.99% | 2027-12 |
| 3 | Honda auto loan | $14,200 | 7.90% | 2028-09 |
| 4 | Federal student loan | $22,600 | 5.50% | 2029-12 |

## Savings
Emergency fund target $12,417 (3 months of essentials) → funded 2030-02 at $230/month (4.2% APY); $1,000 starter first

## Next 30 days
1. 2026-10-01: pay $655 to Chase Sapphire ($205 min + $450 extra), minimums elsewhere
2. Mortgage at $2,350 PITI: not yet — 29.0% / 40.2% vs 28/36; cut $339/month of debt payments first (Discover gone 2027-12 frees $70)
```

**Honest gaps.**
- Card minimums are fixed dollar amounts, not the lender's percentage-of-balance formula. That's disclosed, but real minimums-only timelines can run longer.
- Interest is APR/12 each month, not daily.

---

## 6. Startup Financial Model — vs LivePlan

**Scenario.**
- **Revenue:** MRR $42k; new MRR $6k/mo growing 5%; churn 2.5%; expansion 1%; 24 months from Oct 2026; target $100k MRR.
- **Team:** 6 staff at $78k/mo payroll plus $21k/mo other costs. Hires: 2 senior engineers in month 2, an AE with commission in month 4, a designer in month 7, CS in month 10, 2 engineers in month 13. Load factor 1.3.
- **Runway:** $1.2M cash at an 80% margin, milestone at month 18.
- **Sensitivity:** churn +2 pts and new MRR −25%.
- **Raise:** $95k burn growing 2%/mo, 24 + 6 months, $12M pre, 10% new pool, founders at 78%.

**Checklist** (LivePlan help: subscription revenue <https://help.liveplan.com/understanding-the-numbers/forecasting-revenue-expenses-direct-costs-personnel/entering-recurring-charges-subscription-revenue-streams>, employee taxes and benefits <https://help.liveplan.com/understanding-the-numbers/forecasting-revenue-expenses-direct-costs-personnel/learn-more-employee-taxes-and-benefits>, runway <https://www.liveplan.com/blog/planning/cash-runway-explained>).

| LivePlan capability (documented) | Status | Notes |
|---|---|---|
| Subscription stream: "churn rate is applied to… customers at the beginning of each month, before any new signups" | M | Same convention |
| Renewal period (monthly/quarterly/annual billing) | X | MRR only; annual-prepay cash timing isn't modelled |
| Personnel with a taxes-and-benefits % (or itemised) | M | Load factor, plus monthly extras for commission. Itemising isn't supported |
| Burn rate and runway | M | Zero-cash month, lowest cash, milestone + 6-month check |
| Multiple forecasts/scenarios | M | Sensitivity re-runs |
| Funding entries (loans, investment) | P | Round sizing, dilution and pool. Loans aren't modelled |
| P&L / balance sheet / cash-flow statements | X | Driver model only |
| Business-plan writing, charts, dashboards | OOS | |

**Correctness (`verify_sm.py`).**
- All 24 MRR months are exact. Ending MRR $262,698.64, ARR $3,152,383.70, CMGR 7.9%.
- The $100k target is reached in month 10 = **2027-07** (the tool said 2027-08 before the fix).
- Steady state is N/(churn − expansion) = **$1,290,039.98**. The tool said $774,023.99 before the fix, because it ignored expansion.
- All 24 burn months are exact. Cumulative burn is $4,332,125.
- Runway: cash hits zero in month 14 (2027-11), the lowest point is −$488,054.53 in month 23, and break-even is month 24.
- Sensitivity: ending MRR $166,087.73, zero cash in month 12, no break-even.
- Raise: cumulative burn $3,853,967.52 → raise $3,854,000. Investors get 24.3%; founders go from 78% to 51.2%.

**Deliverable excerpt.**
```
# Model summary — Loomwise — Oct 2026 to Sep 2028
**Today:** MRR $42,000 · burn $99,000/mo gross, $61,104 net · cash $1,200,000
**Plan:** MRR $42,000 → $262,699 in 24 months (CMGR 7.9%) · peak burn $207,625 · zero-cash 2027-11 · break-even 2028-09

## Raise
Raise $3,854,000 for 24 + 6 months → post-money $15,854,000, investors 24.3%, founders 78.0% → 51.2% after a new 10% pool
(dilution incl. pool 34.3% — over the 30% red-flag line: negotiate the pool into the post or raise less)

## Sensitivity
| Case | Ending ARR | Zero-cash | Break-even |
| Base | $3,152,384 | 2027-11 (month 14) | 2028-09 |
| Churn +2 pts, new MRR −25% | $1,993,053 | 2027-09 (month 12) | not in horizon |

## Assumptions
- Churn applied to opening MRR before new MRR; expansion 1%/mo; load factor 1.3; revenue collected = ending MRR × 80% GM
```

**Honest gaps.**
- There are no three-statement financials and no billing-period cash timing (annual prepay).
- The option pool is treated as entirely new shares; the docstring now says so.

---

## 7. Expense Categorizer — vs Monarch Money

**Scenario.** A 60-row Chase-format card export for a small business, Jul–Sep 2026. The descriptors are messy: `SQ *BLUE BOTTLE COFFEE`, `PAYPAL *ADOBE`, `UBER *EATS PENDING` vs `UBER *TRIP`, `GOOGLE *GSUITE_loomwis`, `DELTA DENTAL INS` vs `DELTA AIR`, `UNITEDHEALTHCARE PREM` vs `UNITED 0162…`, `ENTERPRISE RENT-A-CAR`, `AMZN Mktp US*…`. Three rows are card payments.

I planted:
- a double charge (Amazon $129.99 on consecutive days);
- a usage spike (AWS $9,871.44 against ~$2,500);
- a $1,200 Amazon return.

**Checklist** (Monarch: <https://www.monarch.com/blog/track-recurring-bills-and-subscriptions>, CSV import <https://help.monarch.com/hc/en-us/articles/4409682789908-Importing-Transactions-Manually> (search snippet; the page itself returned 403)).

| Monarch capability (documented) | Status | Notes |
|---|---|---|
| CSV import with automatic column detection | M | Delimiter, header, date format, signed vs debit/credit, sign convention |
| Merchant cleanup ("WHOLEFDSMRKT → Whole Foods") | P | Processor prefixes and aliases after the fix. There's no merchant database: "WHOLEFDS MKT" stays "Wholefds Mkt" |
| Auto-categorisation | P | Scenario: 60/60 after the fixes. **Held-out** set of 32 descriptors I didn't tune on: 24/32, with all 8 misses sent to review and none confidently wrong |
| Rules that recategorise future transactions | M | User regex rules, which take priority |
| Automatic recurring detection | M | Weekly → annual cadences, fixed and usage-priced amounts, annualised, possibly-cancelled |
| Duplicate-merchant management | P | Normalised merchant keys; no manual merge UI |
| Upcoming-bill calendar and alerts 3 days before | OOS | |
| Bank sync | OOS | |

**Correctness (`verify_ec.py`, hand-labelled ground truth).**
- **Categories:** 60/60 agree after the fixes. Before the fixes it was 49/60: 5 confidently wrong and 6 uncategorised.
- **Pivot:** all 39 category×month cells are exact. Spend is $7,391.89 / $8,830.09 / $14,436.79, total $30,658.77.
- **Exclusions:** transfers excluded $15,900; the $1,200 refund is netted against Office. Before the fix the refund was counted as income.
- **Recurring:** 9 bills, $79,183.08/yr, all 9 exact. AWS is now included as variable (median $2,698.11 × 12); before the fix it was missed.
- **Anomalies:** AWS outlier at 3.66× median ✓ and the Amazon duplicate ✓. Weekend flags dropped from 18 to 7: auto-billed SaaS on a Saturday is no longer flagged, and neither are repeat LinkedIn budget caps flagged as "round amounts".

**Deliverable excerpt.**
```
# Expense summary — Jul–Sep 2026 (60 transactions, USD)
**Spend:** $30,658.77 · **Income:** $0 · **Transfers excluded:** $15,900 · **Refunds netted:** $1,200 · **Uncategorised:** 0 (0%)

## Biggest movers vs prior month
| Category | Sep | Aug | Change |
| Software | 10,231.93 | 3,068.59 | +7,163.34 (AWS spike) |
| Office | −1,200.00 | 259.98 | −1,459.98 (Amazon return) |
| Equipment | 1,299.00 | 0 | +1,299.00 (Best Buy) |

## Subscriptions (9, $79,183.08/year)
| Merchant | Amount | Cadence | Last charged | Annualised |
| Amazon Web Services | ~$2,698 (variable $2,412–9,871) | monthly | 2026-09-03 | $32,377.32 |
| Wework New York | $1,850.00 | monthly | 2026-09-01 | $22,200.00 |
| Linkedin Ads | $1,500.00 | monthly | 2026-09-08 | $18,000.00 |

## Review
| Date | Merchant | Amount | Flag | Suggested disposition |
| 2026-09-03 | Amazon Web Services | 9,871.44 | outlier 3.7× median | explain: usage spike or runaway resource? |
| 2026-08-21/22 | Amazon Marketplace | 129.99 | duplicate | confirm not double-charged; request refund |
```

**Honest gaps.**
- There's no merchant database, so library coverage of unfamiliar descriptors is about 75% on my held-out sample (for example "WHOLEFDS MKT", "MSFT *", "SOUTHWES", "ATT*BILL"). Those go to the uncategorised list and the playbook's rule loop, so the customer's AI has to categorise them.
- Annual renewals need 2 charges in the file; the single LegalZoom annual charge isn't a detected subscription.

---

## 8. Freelance Tax Estimator — vs Keeper

**Scenario.** A single freelance designer with no state income tax (TX).
- Net SE profit $95,000; $12,000 paid so far.
- Prior-year tax $17,900 on an AGI of $88,000.
- As of 2026-09-27, three quarterly deadlines have passed.
- Deductions: 2,100 miles Jan–Jun and 1,900 miles Jul–Dec, a 200 sq ft home office, $2,800 of client meals, a $2,400 laptop, a $1,200 phone at 60% business use, and $5,400 of health insurance.

**Checklist** (Keeper calculator: <https://www.keepertax.com/quarterly-tax-calculator>; 2026 figures: IRS <https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill>, Tax Foundation HoH/QBI <https://taxfoundation.org/data/all/federal/2026-tax-brackets/>, SSA wage base <https://payroll.org/news-resources/news/news-detail/2025/10/24/social-security-wage-base-increases-to-$184-500-for-2026>, mileage <https://www.journalofaccountancy.com/news/2026/jul/irs-raises-standard-mileage-rates-for-remainder-of-2026/>).

| Keeper capability (documented) | Status | Notes |
|---|---|---|
| Inputs: filing status, state, W-2 + 1099 income, withholdings | P | The state is a flat-rate placeholder |
| Federal quarterly payment amount | M | Plus a safe-harbor catch-up amount |
| State quarterly payment amount | P | Flat placeholder only |
| Breakdown: SE-tax deduction, AGI, standard deduction, QBI, taxable income, SE tax, federal liability | M | Line for line |
| Uses 2026 figures (standard deduction $16,100 / $32,200 / $24,150) | M | **After the fix.** Before, it used 2025 pre-OBBBA figures ($15,000 standard deduction, $176,100 wage base) |
| "Whether quarterly payments are needed" | M | The $1,000 rule, now net of withholding |
| Credits | X | Not modelled |
| Estimated-tax penalty calculator | X | We compute the safe-harbor target, not the Form 2210 penalty |
| Filing / tax-pro-signed return | OOS | |

**Correctness (`verify_tax.py`, 2026 single brackets typed by hand).**

| Line | Tool = independent |
|---|---|
| SE base 92.35% | $87,732.50 |
| SS 12.4% / Medicare 2.9% / SE total | $10,878.83 / $2,544.24 / $13,423.07 |
| Half-SE / AGI | $6,711.54 / $88,288.46 |
| QBI 20% × min(QBI, TI before QBI) | $14,437.69 |
| Taxable income / federal tax | $57,750.77 / $7,417.17 (1,240 + 4,560 + 1,617.17) |
| Total / quarterly | $20,840.24 / $5,210.06 |
| Combined marginal | 30.5% (a +$100 finite difference of the full computation gives 30.49%) |
| Safe harbor | $17,900 on the prior-year basis; behind by $1,425; Q4 = $5,900 |
| Deductions | 7/7 deductible amounts. The tool's tax saved on business items is $2,587.54 against **$2,587.21** from re-running the whole return with $8,486.50 less profit |
| Deadlines | 2026: Apr 15, Jun 15, Sep 15, Jan 15 2027 (110 days away) ✓. IRS-published holiday cases pinned in tests: 2022 Q1 → Apr 18, 2022 Q4 → Jan 17 2023, 2023 Q4 → Jan 16 2024 |

**What was wrong before.**
- **Stale defaults.** The defaults were 2025 pre-OBBBA figures, so this $95k return came out at $21,235.84 instead of $20,840.24, and $5,308.96 a quarter instead of $5,210.06.
- **Deductions overstated.** Tax saved was valued at bracket + 14.13% (36.13%). The true effect is 30.5%, because a deduction also shrinks the half-SE and QBI deductions, so savings were overstated by about 18% ($3,066 against $2,587).
- **Additional Medicare.** The 0.9% Additional Medicare tax was wrongly counted in the half-SE deduction. Its threshold was also mishandled when W-2 wages exceed $200k: for W-2 $250k + SE $100k the tool now charges $831.15 on the SE base only.
- **Deadlines.** Holiday shifts weren't modelled; for example it gave 2028 Q1 as Apr 17 instead of Apr 18.

**Estimate labelling (checked).**
- Every output carries `scope_note`: "Estimate only, not tax advice… verify them on IRS.gov… pass the correct year's values… for any other year… Consult a CPA or EA".
- `defaults_used` lists each default as "(2026) — estimate; verify current IRS figure".
- The playbook's Output format ends with an "Assumptions & verify list" and "Estimate only, not tax advice."

**Deliverable excerpt.**
```
# Tax estimate — 2026 — single
**Next payment:** $5,900 due 2027-01-15 (110 days; includes $1,425 catch-up) · **Set aside:** 21.9% of every net dollar · **Safe harbor:** short by $1,425 today

## Projection
| Net SE profit | $95,000.00 |
| SE tax | $13,423.07 |
| Taxable income | $57,750.77 (after $16,100 standard + $14,437.69 QBI) |
| Federal income tax | $7,417.17 |
| State (TX, none) | $0 |
| Total | $20,840.24 |
| Quarterly payment (even split) | $5,210.06 |

## Deductions (at 16.36% income + 14.13% SE per $1, not 36%)
| Mileage 2,100 mi × $0.725 + 1,900 mi × $0.76 | $2,966.50 | tax saved $904.49 |
| Home office 200 sq ft × $5 | $1,000.00 | $304.90 |
| Meals $2,800 × 50% | $1,400.00 | $426.86 |

## Assumptions & verify list
- 2026 brackets, $16,100 standard deduction, $184,500 SS wage base, 72.5¢/76¢ mileage — verify current IRS figures
- Paying to safe harbor leaves $2,940.24 due in April 2027 — budget for it
Estimate only, not tax advice.
```

**Honest gaps.**
- State tax is a flat placeholder, while Keeper applies each state's rules.
- There are no credits, no penalty amount, and no QBI phase-out math above $201,775 (flagged for a CPA).
- Above-the-line items use the approximation `inc ÷ (1 − SE/2)`: $950.60 against an exact $950.40 for the $5,400 of health insurance.

---

## 9. Investor Update Writer — vs Visible.vc

**Scenario.** The September 2026 update.
- **Metrics:** MRR $84.2k (prior month $78.1k, a year ago $41.3k); customers 312/298/160; logo churn 2.4%/2.1%/3.0%; net burn $118k/$104k/$92k; gross margin 78.5/77.9/71.0; pipeline $610k/$655k.
- **History:** 13 months of MRR.
- **Cash:** $1.91M, with burn over the last 3 months of 98/104/118k and $32k/mo of planned hires.
- **Draft:** written in the playbook format, then linted.

**Checklist** (Visible: <https://visible.vc/investor-updates/>).

| Visible capability (documented) | Status | Notes |
|---|---|---|
| Templates ("Visible Standard", Y Combinator) | M | YC/Sequoia structure in the Output format |
| KPI tables and charts inside the update | P | Ready-to-paste markdown KPI table with MoM/YoY; no charts |
| AI drafting | M | The customer's AI drafts, and `update_lint` gates it |
| Metric numbers "clear at a glance" | M | Exact deltas, a direction arrow plus ✓/✗ favourability, and flags on moves over 10% |
| Send via email/Slack/PDF; open and click tracking | OOS | |
| Data integrations; data room | OOS | |

**Correctness (`verify_iu.py`).**
- MoM/YoY: MRR +7.8% / +103.9%; customers +4.7% / +95.0%; net burn +13.5% / +28.3%; pipeline −6.9% ✓.
- CMGR 6.1%. The last 3 months average 6.5% against 5.8% for the 3 before, so growth is accelerating ✓. It doubles in 11.7 months.
- Runway 17.9 months, cash-out **2028-03** (Sep 30 + 17.9 months ≈ Mar 27). With hires it's 13.8 months, cash-out **2027-11**. Before the fix the tool truncated these to 2028-02 and 2027-10.

**Deliverable excerpt** (lint 100/100, 452 words, 19.5 numbers per 100 words).
```
Subject: Loomwise — September 2026 update

**TL;DR:** MRR $84,200 (+7.8% MoM, +103.9% YoY) · Closed Northwind, our largest logo ($4,900 MRR) · Logo churn rose to 2.4% from 2.1%.

## KPIs
| Metric | Sep 2026 | MoM | YoY | Note |
| MRR | $84,200 | ▲ +7.8% (+$6,100) ✓ | ▲ +103.9% (+$42,900) ✓ |  |
| Logo churn (monthly) | 2.4% | ▲ +0.3 pts ✗ | ▼ -0.6 pts ✓ | 5 of 7 churned accounts were sub-10-seat teams |
| Net burn | $118,000 | ▲ +13.5% (+$14,000) ✗ | ▲ +28.3% (+$26,000) ✗ | $9,000 one-off SOC 2 audit |
| Pipeline (qualified) | $610,000 | ▼ -6.9% (-$45,000) ✗ | — |  |

## Asks
- Intro to a VP Sales who has taken a product-led SaaS company from $1M to $5M ARR — we are hiring one in Q4.

## Runway & team
Cash $1,910,000, net burn $106,667/mo (average of the last 3 months) → 17.9 months of runway (cash-out ~March 2028).
After the 2 planned Q4 hires: 13.8 months.
```

Before the fix, the same churn cell read `▲ -0.6 pts`, an up-arrow on a number that fell, and the pipeline cell read `($-45,000)`.

**Honest gaps.**
- There are no charts, no sending and no open tracking.
- The lint checks structure, density and vague words; it can't check whether the numbers are true, which is the founder's job.
