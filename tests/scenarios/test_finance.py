"""Finance scenario regression tests — replay of the evals/finance.md scenarios.

Every expected value below was recomputed independently (plain Decimal/Fraction scripts that do not
import hundred.*) before being pinned here. Figures are to the cent where the tool reports cents.
Calls go through AgentTool.call exactly as the MCP server calls them.
"""

import pytest

from hundred import registry


def run(slug, tool, **args):
    return registry.get(slug).get_tool(tool).call(args)


# ---------------------------------------------------------------- cashflow-forecaster
CF_FORECAST = {'opening_cash': 412500,
 'start_date': '2026-09-28',
 'min_cash_buffer': 136800,
 'inflows': [{'name': 'Stripe self-serve payouts',
              'amount': 9800,
              'frequency': 'weekly',
              'date': '2026-10-01'},
             {'name': 'collections wk1', 'amount': 39140, 'frequency': 'once', 'week': 1},
             {'name': 'collections wk2', 'amount': 17575, 'frequency': 'once', 'week': 2},
             {'name': 'collections wk4', 'amount': 37730, 'frequency': 'once', 'week': 4},
             {'name': 'collections wk6', 'amount': 22295, 'frequency': 'once', 'week': 6},
             {'name': 'collections wk8', 'amount': 54880, 'frequency': 'once', 'week': 8},
             {'name': 'collections wk10', 'amount': 12152, 'frequency': 'once', 'week': 10},
             {'name': 'collections wk13', 'amount': 63014, 'frequency': 'once', 'week': 13},
             {'name': 'Acme annual prepay (signed)',
              'amount': 45000,
              'frequency': 'once',
              'date': '2026-11-25'}],
 'outflows': [{'name': 'Payroll', 'amount': 68400, 'frequency': 'semimonthly', 'days': [15, 31]},
              {'name': 'Office rent', 'amount': 11200, 'frequency': 'monthly', 'day': 1},
              {'name': 'AWS', 'amount': 6850, 'frequency': 'monthly', 'day': 5},
              {'name': 'Loan repayment', 'amount': 3750, 'frequency': 'monthly', 'day': 10},
              {'name': 'SaaS tools', 'amount': 2900, 'frequency': 'monthly', 'day': 20},
              {'name': 'Contractors', 'amount': 4200, 'frequency': 'biweekly', 'date': '2026-10-02'},
              {'name': 'Annual D&O insurance', 'amount': 14600, 'frequency': 'once', 'date': '2026-11-03'},
              {'name': 'Q4 bonus', 'amount': 22000, 'frequency': 'once', 'date': '2026-12-18'}]}
CF_COLLECTIONS = {'start_date': '2026-09-28',
 'avg_days_late': 12,
 'invoices': [{'id': 'INV-2031', 'amount': 38500, 'due': '2026-10-09'},
              {'id': 'INV-2032', 'amount': 22750, 'due': '2026-10-23'},
              {'id': 'INV-2027', 'amount': 41200, 'due': '2026-09-15'},
              {'id': 'INV-2019', 'amount': 18900, 'due': '2026-08-10', 'paid': 5000},
              {'id': 'INV-2034', 'amount': 56000, 'due': '2026-11-06'},
              {'id': 'INV-2035', 'amount': 12400, 'due': '2026-11-20'},
              {'id': 'INV-2036', 'amount': 64300, 'due': '2026-12-15'},
              {'id': 'INV-2008', 'amount': 9600, 'due': '2026-06-30'}]}
CF_VARIANCE = {'rows': [{'week': '2026-09-21',
           'line': 'Customer collections',
           'forecast_inflow': 52000,
           'actual_inflow': 38450,
           'forecast_outflow': 0,
           'actual_outflow': 0},
          {'week': '2026-09-21',
           'line': 'Stripe payouts',
           'forecast_inflow': 9800,
           'actual_inflow': 10340,
           'forecast_outflow': 0,
           'actual_outflow': 0},
          {'week': '2026-09-21',
           'line': 'Payroll',
           'forecast_inflow': 0,
           'actual_inflow': 0,
           'forecast_outflow': 68400,
           'actual_outflow': 68400},
          {'week': '2026-09-21',
           'line': 'Vendors & SaaS',
           'forecast_inflow': 0,
           'actual_inflow': 0,
           'forecast_outflow': 9500,
           'actual_outflow': 12880},
          {'week': '2026-09-21',
           'line': 'Contractors',
           'forecast_inflow': 0,
           'actual_inflow': 0,
           'forecast_outflow': 4200,
           'actual_outflow': 4200}]}


def test_cashflow_13_week_scenario():
    col = run("cashflow-forecaster", "collections_forecast", **CF_COLLECTIONS)
    assert col["face_value"] == 258650.0 and col["expected_in_horizon"] == 246786.0
    assert [(i["amount"], i["week"]) for i in col["weekly_inflows"]] == [
        (39140.0, 1), (17575.0, 2), (37730.0, 4), (22295.0, 6), (54880.0, 8), (12152.0, 10), (63014.0, 13)]
    by = {i["id"]: i for i in col["invoices"]}
    assert by["INV-2008"]["bucket"] == "61-90" and by["INV-2008"]["expected_amount"] == 5760.0  # 90 days late x 60%
    assert by["INV-2036"]["expected_date"] == "2026-12-27" and by["INV-2036"]["expected_week"] == 13

    fc = run("cashflow-forecaster", "thirteen_week_forecast", **CF_FORECAST)
    assert [w["closing_cash"] for w in fc["weekly"]] == [
        377640.0, 394415.0, 331615.0, 376245.0, 302245.0, 312890.0, 246340.0, 308120.0, 358720.0, 294222.0, 296072.0, 212572.0, 281186.0]
    # semimonthly payroll on the 15th and month-end (Sep 31 clamps to Sep 30; Dec 31 is past the horizon)
    assert [w["week"] for w in fc["weekly"] if "Payroll" in w["items"]["out"]] == [1, 3, 5, 7, 10, 12]
    assert fc["total_inflows"] == 419186.0 and fc["total_outflows"] == 550500.0
    assert fc["low_point"] == {"week": 12, "week_of": "2026-12-14", "cash": 212572.0}
    assert fc["first_breach_week"] is None

    st = run("cashflow-forecaster", "stress_test", opening_cash=412500,
             weekly_inflows=[w["inflows"] for w in fc["weekly"]], weekly_outflows=[w["outflows"] for w in fc["weekly"]],
             collections_delay_weeks=3, revenue_drop_pct=25, surprise_cost=68400, surprise_cost_week=4, min_cash_buffer=136800)
    sc = st["scenarios"]
    assert (sc["collections_delayed_3w"]["min_cash"], sc["collections_delayed_3w"]["min_week"]) == (152790.0, 10)
    assert (sc["revenue_down_25pct"]["min_cash"], sc["revenue_down_25pct"]["buffer_breach_week"]) == (125979.0, 12)
    assert (sc["surprise_cost"]["min_cash"], sc["surprise_cost"]["ending_cash"]) == (144172.0, 212786.0)
    assert (sc["combined"]["min_cash"], sc["combined"]["min_week"], sc["combined"]["buffer_breach_week"]) == (26415.0, 12, 6)
    assert st["scenarios_breaching_zero"] == [] and st["scenarios_below_buffer"] == ["revenue_down_25pct", "combined"]

    rw = run("cashflow-forecaster", "runway", cash=412500, monthly_revenue=128000, monthly_expenses=170600,
             revenue_growth_pct=4, expense_growth_pct=1, start_month="2026-10-01")
    assert rw["runway_months_simple"] == 9.7 and rw["status"] == "default alive"
    assert rw["breakeven_month"] == "2027-08"  # month 11, counting Oct 2026 as month 1
    assert rw["path"][10] == {"month": "2027-08", "revenue": 189471.27, "expenses": 188448.53, "net_burn": -1022.73, "cash": 165450.99}

    vr = run("cashflow-forecaster", "variance_review", **CF_VARIANCE)
    assert vr["totals"]["net_variance"] == -16390.0
    assert vr["accuracy"]["inflow_pct"] == 77.2 and vr["accuracy"]["outflow_pct"] == 95.9
    assert [f["line"] for f in vr["flagged"]] == ["Customer collections", "Vendors & SaaS"]
    assert vr["flagged"][1]["issues"] == ["outflow over forecast by $3,380.00 (35.6%)"]


def test_cashflow_26_week_horizon_keeps_every_monthly_item():
    fc = run("cashflow-forecaster", "thirteen_week_forecast", opening_cash=100000, start_date="2026-09-28", weeks=26,
             inflows=[], outflows=[{"name": "rent", "amount": 1000, "frequency": "monthly", "day": 1}])
    assert [w["week_of"] for w in fc["weekly"] if w["outflows"]] == [
        "2026-09-28", "2026-10-26", "2026-11-30", "2026-12-28", "2027-02-01", "2027-03-01"]  # 6 rents, not 4


# ---------------------------------------------------------------- budget-coach
BC_DEBTS = {'debts': [{'name': 'Chase Sapphire', 'balance': 6840, 'apr': 27.49, 'min_payment': 205},
           {'name': 'Discover It', 'balance': 2315, 'apr': 22.99, 'min_payment': 70},
           {'name': 'Honda auto loan', 'balance': 14200, 'apr': 7.9, 'min_payment': 385},
           {'name': 'Federal student loan', 'balance': 22600, 'apr': 5.5, 'min_payment': 245}],
 'extra_monthly': 450,
 'method': 'avalanche',
 'start_date': '2026-10-01'}
BC_BUDGET = {'take_home_monthly': 5850,
 'expenses': [{'name': 'Rent', 'amount': 1950, 'bucket': 'needs'},
              {'name': 'Utilities', 'amount': 185, 'bucket': 'needs'},
              {'name': 'Groceries', 'amount': 640, 'bucket': 'needs'},
              {'name': 'Car insurance', 'amount': 164, 'bucket': 'needs'},
              {'name': 'Phone', 'amount': 85, 'bucket': 'needs'},
              {'name': 'Gas & transit', 'amount': 210, 'bucket': 'needs'},
              {'name': 'Debt minimums (4)', 'amount': 905, 'bucket': 'needs'},
              {'name': 'Dining out & delivery', 'amount': 420, 'bucket': 'wants'},
              {'name': 'Subscriptions', 'amount': 96, 'bucket': 'wants'},
              {'name': 'Shopping', 'amount': 310, 'bucket': 'wants'},
              {'name': 'Gym', 'amount': 55, 'bucket': 'wants'},
              {'name': 'Travel fund', 'amount': 150, 'bucket': 'wants'},
              {'name': 'Emergency fund', 'amount': 200, 'bucket': 'savings'}]}


def test_budget_coach_four_debt_scenario():
    av = run("budget-coach", "debt_payoff", **BC_DEBTS)
    sn = run("budget-coach", "debt_payoff", **{**BC_DEBTS, "method": "snowball"})
    assert (av["months_to_debt_free"], av["total_interest"], av["debt_free_date"]) == (39, 6125.03, "2029-12")
    assert {d["name"]: (d["paid_off_month"], d["interest_paid"]) for d in av["debts"]} == {
        "Chase Sapphire": (13, 1067.36), "Discover It": (15, 573.08), "Honda auto loan": (24, 1508.09), "Federal student loan": (39, 2976.5)}
    assert (sn["months_to_debt_free"], sn["total_interest"]) == (39, 6239.49)
    assert {d["name"]: d["paid_off_month"] for d in sn["debts"]} == {
        "Chase Sapphire": 16, "Discover It": 5, "Honda auto loan": 24, "Federal student loan": 39}
    assert av["minimums_only"] == {"pays_off": True, "months": 121, "total_interest": 16594.45}
    assert av["interest_saved_vs_minimums"] == 10469.42 and sn["interest_saved_vs_minimums"] == 10354.96

    b = run("budget-coach", "budget_50_30_20", **BC_BUDGET)
    assert (b["buckets"]["needs"]["actual"], b["buckets"]["needs"]["actual_pct"], b["buckets"]["needs"]["gap"]) == (4139.0, 70.8, 1214.0)
    assert (b["buckets"]["wants"]["actual"], b["buckets"]["savings"]["gap"], b["surplus"]) == (1031.0, -970.0, 480.0)

    sg = run("budget-coach", "savings_goal", target=12417, current=2400, monthly_contribution=230, apy=4.2, start_date="2026-10-01")
    assert (sg["months"], sg["funded_by"], sg["interest_earned"]) == (40, "2030-02", 1016.62)

    ln = run("budget-coach", "loan_payment", principal=28500, apr=6.9, months=60, extra_payment=100)
    assert (ln["monthly_payment"], ln["final_payment"], ln["total_interest"], ln["total_paid"]) == (562.99, 563.05, 5279.46, 33779.46)
    assert ln["with_extra"] == {"payment": 662.99, "months": 50, "months_saved": 10, "total_interest": 4331.64, "interest_saved": 947.82}

    dti = run("budget-coach", "debt_to_income", gross_monthly_income=8100, housing_payment=0, other_debt_payments=905, proposed_new_payment=2350)
    assert dti["with_proposed"] == {"front_end_pct": 29.0, "back_end_pct": 40.2}
    assert (dti["front_end_over_by"], dti["back_end_over_by"]) == (82.0, 339.0)


def test_budget_coach_front_end_only_breach_is_not_reported_as_back_end():
    out = run("budget-coach", "debt_to_income", gross_monthly_income=9000, housing_payment=2700, other_debt_payments=300)
    assert "front-end 30.0% is over 28%" in out["verdict"] and "back-end" not in out["verdict"].split("Lenders")[0]
    assert out["front_end_over_by"] == 180.0 and out["back_end_over_by"] == 0.0


def test_budget_coach_sub_one_percent_apr_is_a_percent():
    out = run("budget-coach", "loan_payment", principal=24000, apr=0.9, months=48)
    assert out["monthly_payment"] == 509.24  # annuity formula: 24000 x 0.00075 / (1 - 1.00075^-48) = 509.2415; 0.9% promo APR, not 90%


# ---------------------------------------------------------------- freelance-tax (2026 defaults)
FT_DEDUCTIONS = {'marginal_income_rate_pct': 16.36,
 'se_rate_effective_pct': 14.13,
 'expenses': [{'type': 'mileage', 'miles': 2100, 'rate': 0.725, 'description': 'Client visits Jan-Jun'},
              {'type': 'mileage', 'miles': 1900, 'rate': 0.76, 'description': 'Client visits Jul-Dec'},
              {'type': 'home_office', 'sqft': 200},
              {'type': 'meals', 'amount': 2800, 'description': 'Client meals'},
              {'type': 'equipment', 'amount': 2400, 'description': 'MacBook Pro'},
              {'type': 'phone', 'amount': 1200, 'business_use_pct': 60},
              {'type': 'health_insurance', 'amount': 5400}]}


def test_freelance_tax_95k_single_scenario():
    q = run("freelance-tax", "quarterly_estimate", net_se_income=95000, filing_status="single", payments_made=12000)
    assert q["se_tax"] == {"se_base_92_35pct": 87732.5, "social_security": 10878.83, "medicare": 2544.24,
                           "additional_medicare": 0.0, "total": 13423.07, "half_se_deduction": 6711.54}
    assert q["income_tax"] == {"agi": 88288.46, "standard_deduction": 16100.0, "qbi_deduction": 14437.69,
                               "taxable_income": 57750.77, "federal_income_tax": 7417.17, "marginal_rate_pct": 22.0}
    assert (q["total_tax"], q["quarterly_payment"], q["remaining_to_pay"], q["set_aside_pct_of_net"]) == (20840.24, 5210.06, 8840.24, 21.9)
    assert q["combined_marginal_rate_pct"] == 30.5  # finite difference of the full computation: 30.49%
    assert all("verify" in d for d in q["defaults_used"]) and "Estimate only, not tax advice" in q["scope_note"]

    sh = run("freelance-tax", "safe_harbor", prior_year_total_tax=17900, prior_year_agi=88000,
             current_year_projected_tax=q["total_tax"], paid_to_date=12000, quarters_elapsed=3)
    assert (sh["required_annual_payment"], sh["basis"], sh["shortfall_now"], sh["per_remaining_quarter"]) == (17900.0, "prior-year", 1425.0, 5900.0)
    assert sh["gap_to_full_current_year"] == 2940.24

    fd = q["for_deduction_value"]
    ded = run("freelance-tax", "deduction_value", **{**FT_DEDUCTIONS, "marginal_income_rate_pct": fd["marginal_income_rate_pct"],
                                                    "se_rate_effective_pct": fd["se_rate_effective_pct"]})
    assert [i["deductible"] for i in ded["items"]] == [1522.5, 1444.0, 1000.0, 1400.0, 2400.0, 720.0, 5400.0]
    business_saved = sum(i["tax_saved"] for i in ded["items"][:6])
    assert abs(business_saved - 2587.21) < 1.0  # re-running the whole return with $8,486.50 less profit saves $2,587.21

    dl = run("freelance-tax", "payment_deadlines", tax_year=2026, as_of="2026-09-27", annual_amount=17900)
    assert [d["due"] for d in dl["deadlines"]] == ["2026-04-15", "2026-06-15", "2026-09-15", "2027-01-15"]
    assert (dl["next"]["quarter"], dl["next"]["days_remaining"], dl["quarters_elapsed"]) == (4, 110, 3)


# ---------------------------------------------------------------- unit-economics
UE_COHORTS = {'cohorts': [{'cohort': '2026-01', 'values': [64, 58, 54, 51, 50, 49, 48, 48, 47]},
             {'cohort': '2026-02', 'values': [71, 63, 59, 56, 55, 54, 53, 53]},
             {'cohort': '2026-03', 'values': [58, 52, 49, 47, 46, 45, 45]},
             {'cohort': '2026-04', 'values': [83, 74, 69, 66, 64, 63]},
             {'cohort': '2026-05', 'values': [77, 70, 65, 62, 61]},
             {'cohort': '2026-06', 'values': [90, 81, 76, 73]}]}


def test_unit_economics_scenario():
    lc = run("unit-economics", "ltv_cac", arpa_monthly=412, gross_margin_pct=81, monthly_churn_pct=1.8, cac=6240,
             monthly_expansion_pct=0.6, annual_discount_rate_pct=12, segment="mid-market")
    assert (lc["gross_profit_per_month"], lc["customer_lifetime_months"], lc["lifetime_capped_at_120_months"]) == (333.72, 83.3, False)
    assert (lc["ltv_gross_margin"], lc["ltv_to_cac"], lc["cac_payback_months"]) == (27810.0, 4.46, 18.7)
    assert (lc["ltv_discounted"], lc["ltv_to_cac_discounted"]) == (15169.09, 2.43)
    # ChartMogul's published example: ARPA $100 / 5% churn = LTV $2,000 (revenue basis = 100% margin)
    assert run("unit-economics", "ltv_cac", arpa_monthly=100, gross_margin_pct=100, monthly_churn_pct=5, cac=500)["ltv_gross_margin"] == 2000.0

    rt = run("unit-economics", "retention_metrics", starting_revenue=4860000, churned=388800, contraction=97200,
             expansion=631800, new=1215000, starting_logos=980, churned_logos=212)
    assert (rt["grr_pct"], rt["nrr_pct"], rt["quick_ratio"], rt["logo_churn_pct"], rt["ending_revenue"]) == (90.0, 103.0, 3.8, 21.6, 6220800.0)

    co = run("unit-economics", "cohort_analysis", **UE_COHORTS)
    assert co["retention_at"] == {"m1": 89.9, "m3": 80.1, "m6": 75.7, "m12": None}

    cm = run("unit-economics", "contribution_margin", price=412, variable_costs=[{"name": "hosting", "amount": 38}, {"name": "support", "amount": 29},
             {"name": "sales commission", "pct": 8}], payment_fee_pct=2.9, fixed_costs_monthly=310000, units_per_month=1060)
    assert (cm["contribution_per_unit"], cm["contribution_margin_pct"], cm["breakeven_units_monthly"], cm["operating_profit_monthly"]) == (300.09, 72.8, 1034.0, 8097.52)

    ef = run("unit-economics", "efficiency_metrics", net_new_arr=285000, sales_marketing_spend=1460000, net_burn=620000,
             revenue_growth_pct=48, profit_margin_pct=-22, period="quarter")
    assert (ef["magic_number"], ef["burn_multiple"], ef["rule_of_40"]) == (0.78, 2.18, 26.0)


def test_unit_economics_sub_one_percent_rates_are_percents():
    ent = run("unit-economics", "ltv_cac", arpa_monthly=2000, gross_margin_pct=80, monthly_churn_pct=0.8, cac=20000)
    # 0.8% monthly churn -> 125-month lifetime, capped at 120 (before the fix 0.8 was read as 80%: a 1.25-month lifetime)
    assert (ent["customer_lifetime_months"], ent["lifetime_capped_at_120_months"], ent["ltv_gross_margin"]) == (120.0, True, 192000.0)
    exp = run("unit-economics", "ltv_cac", arpa_monthly=412, gross_margin_pct=81, monthly_churn_pct=1.8, cac=6240, monthly_expansion_pct=0.6)
    assert exp["ltv_gross_margin"] == 27810.0  # 0.6% expansion, not 60% (which capped lifetime and gave $40,046)


# ---------------------------------------------------------------- startup-model
SM_HIRES = {'months': 24,
 'load_factor': 1.3,
 'existing_monthly_costs': 21000,
 'existing_headcount': 6,
 'existing_payroll_monthly': 78000,
 'start_month': '2026-10-01',
 'hires': [{'role': 'Senior engineer', 'start_month': 2, 'annual_salary': 165000, 'count': 2},
           {'role': 'Account executive', 'start_month': 4, 'annual_salary': 120000, 'monthly_extra': 3000},
           {'role': 'Product designer', 'start_month': 7, 'annual_salary': 130000},
           {'role': 'Customer success lead', 'start_month': 10, 'annual_salary': 95000},
           {'role': 'Engineer', 'start_month': 13, 'annual_salary': 150000, 'count': 2}]}


def test_startup_model_scenario():
    base = dict(starting_mrr=42000, months=24, new_mrr_monthly=6000, new_mrr_growth_pct=5, churn_pct=2.5, expansion_pct=1,
                target_mrr=100000, start_month="2026-10-01")
    m = run("startup-model", "mrr_projection", **base)
    assert (m["ending_mrr"], m["ending_arr"], m["cmgr_pct"]) == (262698.64, 3152383.7, 7.9)
    assert (m["target_reached_month"], m["target_reached_label"], m["monthly"][0]["label"]) == (10, "2027-07", "2026-10")
    assert m["steady_state_mrr_if_new_flat"] == 1290039.98  # N / (churn - expansion) = 19,350.60 / 1.5%
    h = run("startup-model", "hiring_plan_burn", **SM_HIRES)
    assert (h["starting_burn"], h["ending_burn"], h["cumulative_burn"], h["ending_headcount"]) == (99000.0, 207625.0, 4332125.0, 13)
    rp = run("startup-model", "runway_projection", cash=1200000, monthly_revenue=[r["ending_mrr"] for r in m["monthly"]],
             monthly_costs=h["burn_series"], gross_margin_pct=80, milestone_month=18, start_month="2026-10-01")
    assert (rp["zero_cash_month"], rp["zero_cash_label"], rp["breakeven_month"]) == (14, "2027-11", 24)
    assert rp["lowest_cash"] == {"month": 23, "amount": -488054.53} and rp["milestone_covered_with_buffer"] is False
    sens = run("startup-model", "mrr_projection", **{**base, "new_mrr_monthly": 4500, "churn_pct": 4.5})
    assert (sens["ending_mrr"], sens["target_reached_month"]) == (166087.73, 15)
    rs = run("startup-model", "runway_projection", cash=1200000, monthly_revenue=[r["ending_mrr"] for r in sens["monthly"]],
             monthly_costs=h["burn_series"], gross_margin_pct=80, start_month="2026-10-01")
    assert (rs["zero_cash_month"], rs["breakeven_month"], rs["additional_cash_needed"]) == (12, None, 1291797.31)
    f = run("startup-model", "fundraise_sizing", monthly_burn=95000, runway_months_target=24, buffer_months=6, pre_money_valuation=12000000,
            option_pool_pct=10, founder_ownership_pct=78, burn_growth_pct_monthly=2)
    assert (f["cumulative_burn"], f["raise_amount"], f["post_money"]) == (3853967.52, 3854000.0, 15854000.0)
    assert (f["investor_ownership_pct"], f["founders_after_pct"], f["ending_monthly_burn"]) == (24.3, 51.2, 168705.25)


# ---------------------------------------------------------------- pricing-strategist
PS_SURVEY = [(10, 25, 49, 79), (15, 29, 59, 99), (9, 19, 39, 59), (20, 35, 69, 120), (12, 25, 45, 75), (19, 39, 59, 89),
 (10, 20, 40, 60), (15, 30, 50, 80), (25, 45, 79, 129), (9, 19, 35, 49), (14, 29, 49, 79), (19, 29, 49, 69),
 (10, 25, 55, 99), (20, 40, 60, 100), (15, 25, 45, 65), (29, 49, 79, 99), (12, 24, 39, 59), (9, 15, 29, 49),
 (19, 35, 59, 99), (15, 29, 45, 69), (20, 30, 50, 75), (10, 19, 39, 69), (25, 39, 59, 89), (15, 35, 65, 110),
 (19, 29, 55, 85), (12, 22, 40, 60), (9, 20, 35, 55), (29, 45, 69, 99), (15, 30, 49, 79), (20, 35, 55, 79),
 (10, 25, 45, 69), (14, 24, 44, 74), (25, 49, 89, 149), (19, 39, 69, 99), (15, 25, 39, 59), (12, 29, 49, 89),
 (9, 19, 29, 39), (20, 29, 49, 79), (49, 29, 59, 99), (30, 20, 40, 50)]  # (too_cheap, bargain, expensive, too_expensive); last two inconsistent


def test_pricing_strategist_scenario():
    responses = [dict(zip(("too_cheap", "bargain", "expensive", "too_expensive"), r)) for r in PS_SURVEY]
    vw = run("pricing-strategist", "van_westendorp", responses=responses)
    assert (vw["n_valid"], vw["n_dropped_inconsistent"], vw["confidence"]) == (38, 2, "medium")
    assert vw["points"] == {"pmc": 29.0, "opp": 30.0, "ipp": 39.0, "pme": 48.0}
    orig = run("pricing-strategist", "van_westendorp", responses=responses, convention="not_cheap_not_expensive")
    assert orig["points"] == {"pmc": 21.43, "opp": 30.0, "ipp": 39.0, "pme": 59.33}
    el = run("pricing-strategist", "elasticity", unit_cost=10.8, observations=[
        {"price": 29, "quantity": 412}, {"price": 39, "quantity": 355}, {"price": 49, "quantity": 290}, {"price": 59, "quantity": 221}])
    assert [s["arc_elasticity"] for s in el["segments"]] == [-0.51, -0.89, -1.46]
    assert el["elastic_from_price"] == 49.0 and el["revenue_max"]["price"] == 49.0 and el["profit_max"]["price"] == 49.0
    assert "elastic above it" in el["verdict"] and "loses revenue" in el["verdict"]
    be = run("pricing-strategist", "price_change_breakeven", current_price=49, price_change_pct=20.4, gross_margin_pct=78, current_units=1180)
    assert (be["breakeven_volume_change_pct"], be["breakeven_units"], be["units_can_lose"]) == (-20.7, 935.4, 244.6)
    tb = run("pricing-strategist", "tier_builder", anchor_price=59, tiers=3)
    assert [(t["monthly"], t["annual_per_month"]) for t in tb["tiers"]] == [(29.0, 24.0), (59.0, 49.0), (129.0, 107.0)]


# ---------------------------------------------------------------- investor-update
IU_METRICS = {'period_label': 'Sep 2026',
 'metrics': [{'name': 'MRR', 'current': 84200, 'prior_month': 78100, 'prior_year': 41300, 'unit': '$'},
             {'name': 'Customers', 'current': 312, 'prior_month': 298, 'prior_year': 160, 'unit': 'count'},
             {'name': 'Logo churn (monthly)',
              'current': 2.4,
              'prior_month': 2.1,
              'prior_year': 3.0,
              'unit': '%',
              'higher_is_better': False},
             {'name': 'Net burn',
              'current': 118000,
              'prior_month': 104000,
              'prior_year': 92000,
              'unit': '$',
              'higher_is_better': False},
             {'name': 'Gross margin', 'current': 78.5, 'prior_month': 77.9, 'prior_year': 71.0, 'unit': '%'},
             {'name': 'Pipeline (qualified)', 'current': 610000, 'prior_month': 655000, 'unit': '$'}]}
IU_DRAFT = 'Subject: Loomwise — September 2026 update\n\n**TL;DR:** MRR $84,200 (+7.8% MoM, +103.9% YoY) · Closed Northwind, our largest logo ($4,900 MRR) · Logo churn rose to 2.4% from 2.1%.\n\n## KPIs\n| Metric | Sep 2026 | MoM | YoY | Note |\n|---|---|---|---|---|\n| MRR | $84,200 | ▲ +7.8% (+$6,100) ✓ | ▲ +103.9% (+$42,900) ✓ |  |\n| Customers | 312 | ▲ +4.7% (+14) ✓ | ▲ +95.0% (+152) ✓ |  |\n| Logo churn (monthly) | 2.4% | ▲ +0.3 pts ✗ | ▼ -0.6 pts ✓ | 5 of 7 churned accounts were sub-10-seat teams on monthly plans |\n| Net burn | $118,000 | ▲ +13.5% (+$14,000) ✗ | ▲ +28.3% (+$26,000) ✗ | $9,000 of it is the annual SOC 2 audit, paid once |\n| Gross margin | 78.5% | ▲ +0.6 pts ✓ | ▲ +7.5 pts ✓ |  |\n| Pipeline (qualified) | $610,000 | ▼ -6.9% (-$45,000) ✗ | — |  |\n\nGrowth: MRR CMGR over the last 12 months is 6.1%; the last 3 months averaged 6.5% against 5.8% in the 3 before, so growth is accelerating. Run-rate ARR is $1,010,400 — we crossed $1M ARR on 26 September.\n\n## Highlights\n- Closed Northwind Logistics at $4,900 MRR on an annual prepay, our largest contract; 11 of 14 new logos came from the partner channel launched in June.\n- Gross margin reached 78.5% (+7.5 pts YoY) after moving inference to reserved instances, saving $3,200 a month.\n- Shipped the audit-log export; 38 enterprise trials used it in the first 2 weeks.\n\n## Lowlights\n- Logo churn rose to 2.4% from 2.1%. 5 of the 7 lost accounts were teams under 10 seats that never invited a second admin; we start a 14-day onboarding call for every new team on 6 October.\n- Qualified pipeline fell 6.9% to $610,000 because 2 of our 3 AEs spent 3 weeks on the Northwind security review.\n- Net burn rose 13.5% to $118,000, $9,000 of which is the one-off SOC 2 audit.\n\n## Asks\n- Intro to a VP Sales who has taken a product-led SaaS company from $1M to $5M ARR — we are hiring one in Q4.\n- Intros to heads of operations at 3PL companies with 200+ employees; our win rate there is 41%.\n- Looking for a SOC 2 Type II auditor recommendation for the 2027 cycle with a quote under $30,000.\n\n## Runway & team\nCash $1,910,000, net burn $106,667/mo (average of the last 3 months) → 17.9 months of runway (cash-out ~March 2028). After the 2 planned Q4 hires: 13.8 months. Team: 24 (+2 this month). We plan to open the Series A process in Q1 2027 from $1.4M ARR.\n\nThanks to Priya Raman for the Northwind intro and to Tom Ellis for the pricing review that led to our annual-prepay discount.\n'


def test_investor_update_scenario():
    d = run("investor-update", "metric_deltas", **IU_METRICS)
    by = {m["name"]: m for m in d["metrics"]}
    assert (by["MRR"]["mom"]["pct"], by["MRR"]["yoy"]["pct"]) == (7.8, 103.9)
    assert (by["Net burn"]["mom"]["pct"], by["Net burn"]["yoy"]["pct"]) == (13.5, 28.3)
    assert [f["name"] for f in d["flags"]] == ["Logo churn (monthly)", "Net burn"]
    assert "| Logo churn (monthly) | 2.4% | ▲ +0.3 pts ✗ | ▼ -0.6 pts ✓ | explain |" in d["markdown_table"]
    assert "▼ -6.9% (-$45,000) ✗" in d["markdown_table"]
    g = run("investor-update", "growth_series", values=[41300, 44100, 46800, 49900, 52600, 55200, 58900, 62400, 66000, 69800, 73500, 78100, 84200])
    assert (g["cmgr_pct"], g["last_3_avg_mom_pct"], g["prior_3_avg_mom_pct"], g["trend"], g["months_to_double_at_cmgr"]) == (6.1, 6.5, 5.8, "accelerating", 11.7)
    r = run("investor-update", "runway_line", cash=1910000, net_burn_months=[98000, 104000, 118000], as_of="2026-09-30", hires_planned_monthly_cost=32000)
    assert (r["avg_net_burn"], r["runway_months"], r["cash_out_month"]) == (106666.67, 17.9, "2028-03")
    assert r["with_planned_hires"] == {"net_burn": 138666.67, "runway_months": 13.8, "cash_out_month": "2027-11"}
    lint = run("investor-update", "update_lint", draft=IU_DRAFT)
    assert lint["score"] == 100 and lint["ready_to_send"] is True and 350 <= lint["words"] <= 700


# ---------------------------------------------------------------- invoice-chaser
IC_AGING = {'as_of': '2026-09-28',
 'revenue_last_90_days': 412000,
 'payment_terms_days': 30,
 'invoices': [{'id': 'INV-1042', 'customer': 'Brightline Media', 'amount': 8500, 'due': '2026-08-15'},
              {'id': 'INV-1051',
               'customer': 'Harbor & Finch',
               'amount': 23400,
               'due': '2026-09-05',
               'paid': 10000},
              {'id': 'INV-1038', 'customer': 'Oakridge Dental Group', 'amount': 4200, 'due': '2026-07-10'},
              {'id': 'INV-1029', 'customer': 'Brightline Media', 'amount': 3150, 'due': '2026-06-20'},
              {'id': 'INV-1057', 'customer': 'Kestrel Outdoor', 'amount': 31750, 'due': '2026-09-20'},
              {'id': 'INV-1060', 'customer': 'Northwind Logistics', 'amount': 18900, 'due': '2026-10-12'},
              {'id': 'INV-1061', 'customer': 'Harbor & Finch', 'amount': 9600, 'due': '2026-10-20'},
              {'id': 'INV-1033',
               'customer': 'Velo Labs',
               'amount': 12800,
               'due': '2026-07-31',
               'paid': 12800},
              {'id': 'INV-1046', 'customer': 'Oakridge Dental Group', 'amount': 650, 'due': '2026-05-30'}]}
IC_MESSAGE = 'Subject: Overdue: invoice INV-1042 ($8,500.00) — 44 days past due\n\nHi Dana,\n\nInvoice INV-1042 for $8,500.00 was due on 2026-08-15 and is now 44 days past due. Our records show no payment and no dispute on it.\n\nPlease remit $8,500.00 by Friday 2 October using the payment link below, or reply with the date the payment is scheduled.\n\nPay online: https://pay.loomwise.io/i/INV-1042\nACH: account details are on the invoice PDF.\n\nUnder the agreement, late interest of 1.5% per month applies after a 10-day grace period ($144.50 as of today); we will waive it if payment arrives by 2 October.\n\nThank you,\nSam Ortiz, Accounts Receivable, Loomwise\n'


def test_invoice_chaser_scenario():
    a = run("invoice-chaser", "aging_report", **IC_AGING)
    assert (a["total_outstanding"], a["overdue_total"], a["over_60_pct"], a["dso_days"]) == (90150.0, 61650.0, 8.9, 19.7)
    assert {k: v["amount"] for k, v in a["buckets"].items()} == {"current": 28500.0, "1-30": 45150.0, "31-60": 8500.0, "61-90": 4200.0, "90+": 3800.0}
    assert [c["id"] for c in a["chase_list"]] == ["INV-1042", "INV-1038", "INV-1029", "INV-1051", "INV-1057", "INV-1046"]
    fee = dict(amount=8500, due_date="2026-08-15", as_of="2026-09-28")
    assert run("invoice-chaser", "late_fee", **fee, rate=1.5, grace_days=10)["fee"] == 144.5
    assert run("invoice-chaser", "late_fee", **fee, fee_type="annual_pct", rate=18)["fee"] == 184.44
    assert run("invoice-chaser", "late_fee", **fee, rate=1.5, compounding=True)["fee"] == 187.89
    dn = run("invoice-chaser", "dunning_schedule", due_date="2026-08-15", amount=8500, invoice_id="INV-1042", as_of="2026-09-28", touches_sent=2)
    assert dn["current_touch"]["name"] == "second notice" and dn["current_touch"]["date"] == "2026-09-28"
    assert [t["date"] for t in dn["touches"][2:]] == ["2026-09-28", "2026-10-05", "2026-10-12", "2026-10-19"]
    assert dn["touches"][2]["subject"].endswith("44 days past due") and dn["touches"][5]["subject"].endswith("2026-11-03")
    cal = run("invoice-chaser", "dunning_schedule", due_date="2026-08-15", amount=8500, invoice_id="INV-1042", as_of="2026-09-28")
    assert cal["current_touch"]["name"] == "final notice"  # calendar-only view when nothing is known about what was sent
    lint = run("invoice-chaser", "chase_message_lint", message=IC_MESSAGE, invoice_id="INV-1042", amount=8500, due_date="2026-08-15", touch=3)
    assert lint["score"] == 100 and lint["ready_to_send"] is True


# ---------------------------------------------------------------- expense-categorizer
EC_CSV = 'Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n07/01/2026,07/02/2026,WEWORK 0441 NEW YORK NY,Bills & Utilities,Sale,-1850.00,\n07/02/2026,07/03/2026,GOOGLE *GSUITE_loomwis,Professional Services,Sale,-72.00,\n07/03/2026,07/05/2026,AMAZON WEB SERVICES AWS.AMAZON.CO,Professional Services,Sale,-2412.37,\n07/03/2026,07/05/2026,SQ *BLUE BOTTLE COFFEE,Food & Drink,Sale,-14.75,\n07/05/2026,07/06/2026,SLACK T0231ABC,Professional Services,Sale,-87.50,\n07/07/2026,07/08/2026,FIGMA,Professional Services,Sale,-45.00,\n07/08/2026,07/09/2026,AMZN Mktp US*2K4L81,Shopping,Sale,-63.18,\n07/09/2026,07/10/2026,UBER *TRIP HELP.UBER.COM,Travel,Sale,-28.40,\n07/10/2026,07/12/2026,LINKEDIN ADS 7788123,Professional Services,Sale,-1500.00,\n07/11/2026,07/13/2026,TST* JOES DINER,Food & Drink,Sale,-86.20,\n07/12/2026,07/13/2026,PAYPAL *ADOBE,Shopping,Sale,-59.99,\n07/14/2026,07/15/2026,DELTA AIR 0062345118,Travel,Sale,-412.60,\n07/15/2026,07/15/2026,Payment Thank You-Mobile,,Payment,4200.00,\n07/15/2026,07/16/2026,COMCAST BUSINESS,Bills & Utilities,Sale,-189.99,\n07/18/2026,07/19/2026,UBER *EATS PENDING,Food & Drink,Sale,-42.10,\n07/20/2026,07/21/2026,NOTION LABS INC,Professional Services,Sale,-96.00,\n07/22/2026,07/23/2026,ENTERPRISE RENT-A-CAR,Travel,Sale,-268.44,\n07/25/2026,07/27/2026,STAPLES 00123,Shopping,Sale,-54.32,\n07/28/2026,07/29/2026,CHEVRON 0098765,Gas,Sale,-61.05,\n07/30/2026,07/31/2026,DELTA DENTAL INS,Health & Wellness,Sale,-48.00,\n08/01/2026,08/02/2026,WEWORK 0441 NEW YORK NY,Bills & Utilities,Sale,-1850.00,\n08/02/2026,08/03/2026,GOOGLE *GSUITE_loomwis,Professional Services,Sale,-72.00,\n08/03/2026,08/05/2026,AMAZON WEB SERVICES AWS.AMAZON.CO,Professional Services,Sale,-2698.11,\n08/04/2026,08/05/2026,SQ *BLUE BOTTLE COFFEE,Food & Drink,Sale,-11.25,\n08/05/2026,08/06/2026,SLACK T0231ABC,Professional Services,Sale,-87.50,\n08/07/2026,08/08/2026,FIGMA,Professional Services,Sale,-45.00,\n08/08/2026,08/10/2026,LINKEDIN ADS 7788123,Professional Services,Sale,-1500.00,\n08/09/2026,08/10/2026,UBER *TRIP HELP.UBER.COM,Travel,Sale,-31.90,\n08/12/2026,08/13/2026,PAYPAL *ADOBE,Shopping,Sale,-59.99,\n08/13/2026,08/14/2026,UNITED 0162345678,Travel,Sale,-389.20,\n08/15/2026,08/15/2026,Payment Thank You-Mobile,,Payment,5600.00,\n08/15/2026,08/16/2026,COMCAST BUSINESS,Bills & Utilities,Sale,-189.99,\n08/16/2026,08/17/2026,MARRIOTT CHICAGO,Travel,Sale,-624.18,\n08/17/2026,08/18/2026,TST* JOES DINER,Food & Drink,Sale,-112.40,\n08/20/2026,08/21/2026,NOTION LABS INC,Professional Services,Sale,-96.00,\n08/21/2026,08/22/2026,AMZN Mktp US*7H2PQ0,Shopping,Sale,-129.99,\n08/22/2026,08/24/2026,AMZN Mktp US*7H2PQ0,Shopping,Sale,-129.99,\n08/24/2026,08/25/2026,HISCOX INSURANCE,Bills & Utilities,Sale,-142.00,\n08/27/2026,08/28/2026,UBER *EATS PENDING,Food & Drink,Sale,-38.60,\n08/29/2026,08/31/2026,APPLE.COM/BILL,Shopping,Sale,-9.99,\n08/30/2026,08/31/2026,UNITEDHEALTHCARE PREM,Health & Wellness,Sale,-612.00,\n09/01/2026,09/02/2026,WEWORK 0441 NEW YORK NY,Bills & Utilities,Sale,-1850.00,\n09/02/2026,09/03/2026,GOOGLE *GSUITE_loomwis,Professional Services,Sale,-72.00,\n09/03/2026,09/05/2026,AMAZON WEB SERVICES AWS.AMAZON.CO,Professional Services,Sale,-9871.44,\n09/04/2026,09/05/2026,SQ *BLUE BOTTLE COFFEE,Food & Drink,Sale,-16.50,\n09/05/2026,09/06/2026,SLACK T0231ABC,Professional Services,Sale,-87.50,\n09/07/2026,09/08/2026,FIGMA,Professional Services,Sale,-45.00,\n09/08/2026,09/09/2026,LINKEDIN ADS 7788123,Professional Services,Sale,-1500.00,\n09/10/2026,09/11/2026,LYFT *RIDE THU 8PM,Travel,Sale,-24.75,\n09/12/2026,09/13/2026,PAYPAL *ADOBE,Shopping,Sale,-59.99,\n09/13/2026,09/14/2026,BEST BUY 00012345,Shopping,Sale,-1299.00,\n09/15/2026,09/15/2026,Payment Thank You-Mobile,,Payment,6100.00,\n09/15/2026,09/16/2026,COMCAST BUSINESS,Bills & Utilities,Sale,-189.99,\n09/18/2026,09/19/2026,KWIK TRIP 441,Gas,Sale,-48.12,\n09/19/2026,09/20/2026,STRIPE FEE SEP,Professional Services,Sale,-3.20,\n09/20/2026,09/21/2026,NOTION LABS INC,Professional Services,Sale,-96.00,\n09/22/2026,09/23/2026,GUSTO FEE 441,Professional Services,Sale,-80.00,\n09/24/2026,09/25/2026,TST* JOES DINER,Food & Drink,Sale,-94.30,\n09/26/2026,09/28/2026,LEGALZOOM*ANNUAL,Professional Services,Sale,-299.00,\n09/27/2026,09/28/2026,AMZN Mktp US*9Z1XX3,Shopping,Sale,1200.00,\n'


def test_expense_categorizer_messy_card_export():
    p = run("expense-categorizer", "parse_transactions", csv_text=EC_CSV)
    assert (p["count"], p["failed_count"], p["total_spend"], p["total_income"]) == (60, 0, 31858.77, 17100.0)
    merchants = {r["description"]: r["merchant"] for r in p["rows"]}
    assert merchants["SQ *BLUE BOTTLE COFFEE"] == "Blue Bottle Coffee"
    assert merchants["PAYPAL *ADOBE"] == "Adobe" and merchants["UBER *EATS PENDING"] == "Uber Eats"
    assert merchants["AMZN Mktp US*7H2PQ0"] == "Amazon Marketplace" and merchants["SLACK T0231ABC"] == "Slack"
    c = run("expense-categorizer", "categorize", transactions=p["rows"])
    cats = {r["description"]: r["category"] for r in c["rows"]}
    assert c["uncategorised_count"] == 0
    assert cats["UBER *EATS PENDING"] == "Meals" and cats["UBER *TRIP HELP.UBER.COM"] == "Travel"
    assert cats["ENTERPRISE RENT-A-CAR"] == "Travel" and cats["WEWORK 0441 NEW YORK NY"] == "Rent"
    assert cats["DELTA DENTAL INS"] == "Insurance" and cats["DELTA AIR 0062345118"] == "Travel"
    assert cats["UNITEDHEALTHCARE PREM"] == "Insurance" and cats["UNITED 0162345678"] == "Travel"
    assert cats["GOOGLE *GSUITE_loomwis"] == "Software" and cats["Payment Thank You-Mobile"] == "Transfers"
    rows = [{k: r[k] for k in ("date", "description", "merchant", "amount", "category")} for r in c["rows"]]
    t = run("expense-categorizer", "totals_by_category_month", transactions=rows)
    assert t["spend_by_month"] == {"2026-07": 7391.89, "2026-08": 8830.09, "2026-09": 14436.79}
    assert (t["total_spend"], t["transfers_excluded"], t["refunds_netted"]) == (30658.77, 15900.0, 1200.0)
    assert t["top_movers"][0] == {"category": "Software", "this_month": 10231.93, "prior_month": 3068.59, "change": 7163.34, "change_pct": 233.4}
    rec = run("expense-categorizer", "detect_recurring", transactions=rows)
    ann = {x["merchant"]: (x["annualised"], x["variable_amount"]) for x in rec["recurring"]}
    assert ann["Amazon Web Services"] == (32377.32, True) and ann["Wework New York"] == (22200.0, False)
    assert len(ann) == 9 and rec["annualised_total_active"] == 79183.08
    assert "Joes Diner" not in ann and "Blue Bottle Coffee" not in ann  # restaurants at a monthly rhythm are not bills
    an = run("expense-categorizer", "flag_anomalies", transactions=rows, business=True)
    assert an["by_type"] == {"outlier": 1, "duplicate": 1, "weekend": 7}
    assert {(f["type"], f["merchant"], f["amount"]) for f in an["flags"] if f["type"] != "weekend"} == {
        ("outlier", "Amazon Web Services", 9871.44), ("duplicate", "Amazon Marketplace", 129.99)}
