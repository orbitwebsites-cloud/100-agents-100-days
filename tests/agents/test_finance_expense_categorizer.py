"""Expense Categorizer tools — CSV parsing, rules, pivots, recurring detection, anomalies."""

import pytest

from hundred.agents.finance.expense_categorizer import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


CSV = """Date,Description,Amount
2026-07-03,NETFLIX.COM 866-579-7172,-15.49
2026-07-05,AWS EMEA aws.amazon.com,-212.30
2026-07-05,AWS EMEA aws.amazon.com,-212.30
2026-07-10,STRIPE PAYOUT,4200.00
2026-07-12,WHOLE FOODS MKT #123,-84.12
2026-07-15,ZELLE TRANSFER TO SAVINGS,-1000.00
2026-08-03,NETFLIX.COM 866-579-7172,-15.49
2026-08-06,AWS EMEA aws.amazon.com,-230.10
2026-08-14,WHOLE FOODS MKT #123,-91.50
2026-08-20,ACME CONSULTING LLC,-2500.00
2026-09-03,NETFLIX.COM 866-579-7172,-15.49
2026-09-05,AWS EMEA aws.amazon.com,-1900.00
2026-09-11,WHOLE FOODS MKT #123,-79.00
2026-09-12,SOME RANDOM VENDOR,-45.00
"""


def _rows():
    return call("parse_transactions", csv_text=CSV)["rows"]


def test_parse_transactions_signed_layout():
    out = call("parse_transactions", csv_text=CSV)
    assert out["count"] == 14 and out["failed_count"] == 0
    assert out["date_range"] == {"from": "2026-07-03", "to": "2026-09-12"}
    assert out["total_spend"] == 6400.79 and out["total_income"] == 4200.0
    assert out["rows"][0]["merchant"] == "Netflix"
    assert out["rows"][4]["merchant"] == "Whole Foods Mkt"


def test_parse_transactions_debit_credit_layout_and_errors():
    out = call("parse_transactions", csv_text="Posted Date;Details;Debit;Credit\n07/01/2026;COFFEE SHOP;4.50;\n07/02/2026;PAYROLL DEP;;3000.00\nbad row;;;\n")
    assert out["layout"]["amounts"] == "debit/credit"
    assert [r["amount"] for r in out["rows"]] == [-4.5, 3000.0]
    assert out["failed_count"] == 1
    with pytest.raises(ToolError):
        call("parse_transactions", csv_text="   ")


def test_categorize_rules_library_and_uncategorised():
    out = call("categorize", transactions=_rows(), rules=[{"pattern": "ACME CONSULTING", "category": "Contractors"}])
    cats = {r["description"]: r["category"] for r in out["rows"]}
    assert cats["ACME CONSULTING LLC"] == "Contractors"
    assert cats["AWS EMEA aws.amazon.com"] == "Software"
    assert cats["ZELLE TRANSFER TO SAVINGS"] == "Transfers"
    assert cats["STRIPE PAYOUT"] == "Revenue"
    assert cats["SOME RANDOM VENDOR"] == "Uncategorised"
    assert out["uncategorised_count"] == 1 and out["uncategorised_pct"] == 7.1
    assert out["spend_by_category"]["Software"] == 2554.7
    assert "Transfers" not in out["spend_by_category"]
    income = call("categorize", transactions=[{"date": "2026-07-02", "description": "PAYROLL DEP", "amount": 3000}])
    assert income["rows"][0]["category"] == "Income"
    with pytest.raises(ToolError):
        call("categorize", transactions=_rows(), rules=[{"pattern": "x"}])


def test_totals_by_category_month_pivot_and_movers():
    rows = call("categorize", transactions=_rows())["rows"]
    out = call("totals_by_category_month", transactions=rows, include_income=True)
    assert out["months"] == ["2026-07", "2026-08", "2026-09"]
    assert out["spend_by_month"]["2026-07"] == 524.21  # transfer excluded
    assert out["transfers_excluded"] == 1000.0
    assert out["total_income"] == 4200.0
    assert out["categories"][0]["category"] == "Software"
    mover = next(m for m in out["top_movers"] if m["category"] == "Software")
    assert mover["change"] == 1669.9 and mover["change_pct"] == 725.7
    with pytest.raises(ToolError):
        call("totals_by_category_month", transactions=[{"date": "nope", "amount": -1, "category": "x"}])


def test_detect_recurring_subscriptions():
    out = call("detect_recurring", transactions=_rows())
    by = {r["merchant"]: r for r in out["recurring"]}
    assert by["Netflix"]["cadence"] == "monthly" and by["Netflix"]["annualised"] == 185.88
    assert by["Netflix"]["occurrences"] == 3
    assert "Aws Emea Aws" in by  # amounts within tolerance on 3 of 4 charges
    assert "Acme Consulting" not in by
    with pytest.raises(ToolError):
        call("detect_recurring", transactions=_rows(), min_occurrences=1)


def test_flag_anomalies_duplicates_outliers_round():
    out = call("flag_anomalies", transactions=_rows())
    types = {(f["type"], f["merchant"], f["amount"]) for f in out["flags"]}
    assert ("duplicate", "Aws Emea Aws", 212.3) in types
    assert ("outlier", "Aws Emea Aws", 1900.0) in types
    assert ("round_amount", "Acme Consulting", 2500.0) in types
    assert out["by_type"]["duplicate"] == 1
    assert out["amount_at_risk"] == 2112.3
    with pytest.raises(ToolError):
        call("flag_anomalies", transactions=_rows(), outlier_multiple=0.5)
