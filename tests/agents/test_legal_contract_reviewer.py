"""Contract Reviewer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("contract-reviewer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


SAAS = """MASTER SUBSCRIPTION AGREEMENT. 1. Term. This Agreement commences on the Effective Date and continues for an
initial term of twelve (12) months and shall automatically renew for successive twelve (12) month periods unless
either party gives written notice of non-renewal at least ninety (90) days prior to the end of the then-current term.
2. Fees. Customer shall pay all invoices within sixty (60) days of receipt. Provider may increase fees upon renewal.
3. Limitation of Liability. In no event shall Provider's aggregate liability exceed the fees paid in the three (3)
months preceding the claim. Neither party shall be liable for consequential damages. 4. Indemnification. Customer
shall defend, indemnify and hold harmless Provider from any third-party claims. 5. Customer shall not develop or
market any product that competes with the Service during the term. 6. Governing Law. This Agreement is governed by
the laws of the State of New York. 7. Either party may terminate for material breach if the breach is not cured
within ten (10) days of notice. 8. Provider may audit Customer's use at any time. Signed March 3, 2026."""


def test_detect_clauses_scores_customer_side():
    out = call("detect_clauses", contract_text=SAAS, my_role="customer")
    keys = {c["key"] for c in out["clauses_found"]}
    assert {"limitation_of_liability", "consequential_exclusion", "indemnity", "auto_renewal", "governing_law", "audit", "payment_terms", "non_compete"} <= keys
    flags = [f["flag"] for f in out["red_flags"]]
    assert "one-way indemnity running from you to the vendor" in flags
    assert "non-compete / restriction on competing products" in flags
    assert any("notice period of 90+" in f for f in flags)
    assert any("cure period" in f for f in flags)
    assert out["risk_score"] >= 50 and "Do not sign" in out["verdict"]
    assert "scope_note" in out


def test_detect_clauses_vendor_side_differs():
    out = call("detect_clauses", contract_text=SAAS, my_role="vendor")
    flags = [f["flag"] for f in out["red_flags"]]
    assert "one-way indemnity running from you to the vendor" not in flags
    assert any("net 60" in f for f in flags)


def test_detect_clauses_rejects_bad_role():
    with pytest.raises(ToolError):
        call("detect_clauses", contract_text=SAAS, my_role="bystander")


def test_extract_deadlines_resolves_durations_and_dates():
    out = call("extract_deadlines", contract_text=SAAS, effective_date="2026-10-01")
    by = {d["duration"]: d for d in out["durations"]}
    assert by["12 months"]["from_effective_date"] == "2027-10-01" and by["12 months"]["type"] == "term"
    assert by["90 days"]["from_effective_date"] == "2026-12-30" and by["90 days"]["type"] == "notice / termination"
    assert by["60 days"]["type"] == "payment"
    assert by["10 days"]["type"] == "cure period"
    assert "twelve (12) monthstwelve" not in by["12 months"]["context"]
    assert out["longest_notice_days"] == 90 and out["auto_renewal_language"] is True
    assert out["explicit_dates"][0]["iso"] == "2026-03-03"


def test_extract_deadlines_rejects_bad_date():
    with pytest.raises(ToolError):
        call("extract_deadlines", contract_text=SAAS, effective_date="next week")


def test_renewal_calendar_dates():
    out = call("renewal_calendar", effective_date="2026-10-01", initial_term_months=12, notice_days=90, renewal_term_months=12, reminder_days_before_notice=30, renewals_to_show=2)
    assert out["initial_term_end"].startswith("2027-09-30")
    assert out["notice_deadline"].startswith("2027-07-02")
    assert out["reminder_date"].startswith("2027-06-02")
    assert out["renewal_cycles"][0] == {"renewal": 1, "starts": "2027-10-01", "ends": "2028-09-30", "notice_deadline": "2028-07-02"}
    assert len(out["calendar_entries"]) == 3


def test_renewal_calendar_rejects_bad_term():
    with pytest.raises(ToolError):
        call("renewal_calendar", effective_date="2026-10-01", initial_term_months=0)


def test_liability_exposure_math_and_market():
    out = call("liability_exposure", annual_contract_value=240_000, cap_type="months_of_fees", cap_value=3, term_years=3)
    assert out["cap_dollars"] == 60_000 and out["total_contract_value"] == 720_000
    assert out["cap_pct_of_total_contract_value"] == 8.3
    assert "below market" in out["market_position"]
    uncapped = call("liability_exposure", annual_contract_value=100_000, cap_type="uncapped", carve_outs=["confidentiality", "marketing spend"])
    assert uncapped["cap_dollars"] is None and "uncapped" in uncapped["market_position"]
    assert any("Unusual carve-outs" in f and "marketing spend" in f for f in uncapped["findings"])


def test_liability_exposure_rejects_bad_cap_type():
    with pytest.raises(ToolError):
        call("liability_exposure", annual_contract_value=1000, cap_type="whatever")
