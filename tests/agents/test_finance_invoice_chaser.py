"""Invoice Chaser tools — aging buckets, exact late fees, dunning dates, message lint."""

import pytest

from hundred.agents.finance.invoice_chaser import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


INVOICES = [
    {"id": "1042", "customer": "Acme", "amount": 8500, "due": "2026-08-15"},
    {"id": "1050", "customer": "Beta", "amount": 2000, "due": "2026-09-20"},
    {"id": "1060", "customer": "Acme", "amount": 3000, "due": "2026-10-10", "paid": 1000},
]


def test_aging_report_buckets_dso_and_priority():
    out = call("aging_report", invoices=INVOICES, as_of="2026-09-27", revenue_last_90_days=60000)
    assert out["total_outstanding"] == 12500.0
    assert out["buckets"]["31-60"]["amount"] == 8500.0
    assert out["buckets"]["1-30"]["count"] == 1
    assert out["buckets"]["current"]["amount"] == 2000.0
    assert out["dso_days"] == 18.8  # 12500 / 60000 * 90
    assert out["chase_list"][0]["id"] == "1042"
    assert out["chase_list"][0]["days_late"] == 43
    assert out["customer_concentration"][0]["customer"] == "Acme"


def test_aging_report_rejects_fully_paid():
    with pytest.raises(ToolError):
        call("aging_report", invoices=[{"id": "1", "amount": 100, "paid": 100, "due": "2026-01-01"}])


@pytest.mark.parametrize(
    "kwargs,fee",
    [
        (dict(fee_type="monthly_pct", rate=1.5), 182.75),  # 8500 * 1.5% * 43/30
        (dict(fee_type="monthly_pct", rate=1.5, compounding=True), 183.58),
        (dict(fee_type="annual_pct", rate=8), 80.11),  # 8500 * 8% * 43/365
        (dict(fee_type="flat", rate=50), 50.0),
        (dict(fee_type="monthly_pct", rate=1.5, grace_days=10), 140.25),
        (dict(fee_type="monthly_pct", rate=1.5, cap_pct=1), 85.0),
    ],
)
def test_late_fee_variants(kwargs, fee):
    out = call("late_fee", amount=8500, due_date="2026-08-15", as_of="2026-09-27", **kwargs)
    assert out["days_late"] == 43
    assert out["fee"] == fee
    assert out["total_due"] == round(8500 + fee, 2)


def test_late_fee_not_yet_due_and_bad_input():
    out = call("late_fee", amount=100, due_date="2026-10-15", as_of="2026-09-27")
    assert out["fee"] == 0.0
    with pytest.raises(ToolError):
        call("late_fee", amount=100, due_date="not-a-date")


def test_dunning_schedule_business_day_rollover_and_current_touch():
    out = call("dunning_schedule", due_date="2026-09-15", amount=12000, invoice_id="1042", as_of="2026-09-27")
    dates = [t["date"] for t in out["touches"]]
    assert dates[0] == "2026-09-08"  # T-7 Tue
    assert dates[1] == "2026-09-16"
    assert dates[2] == "2026-09-22"
    assert dates[4] == "2026-10-15"
    assert all(t["weekday"] not in ("Sat", "Sun") for t in out["touches"])
    assert out["current_touch"]["touch"] == 3
    assert out["next_touch"]["name"] == "call + email"
    assert "$12,000.00" in out["touches"][0]["subject"]


def test_dunning_schedule_custom_offsets_and_bad_input():
    out = call("dunning_schedule", due_date="2026-09-15", amount=100, offsets_days=[-3, 5, 20], as_of="2026-09-01")
    assert [t["offset_days"] for t in out["touches"]] == [-3, 5, 20]
    assert out["current_touch"] is None
    with pytest.raises(ToolError):
        call("dunning_schedule", due_date="2026-09-15", amount=100, offsets_days=[999])


GOOD = (
    "Subject: Invoice 1042 ($8,500.00) — 43 days past due\n\n"
    "Hi Dana,\nInvoice 1042 for $8,500.00 was due 2026-08-15 and is now 43 days past due. "
    "Please remit by Friday 2026-10-02 via the payment link: https://pay.example/1042.\nThanks,\nSam"
)


def test_chase_message_lint_scores_and_flags():
    good = call("chase_message_lint", message=GOOD, invoice_id="1042", amount=8500, due_date="2026-08-15", touch=3)
    assert good["score"] == 100 and good["ready_to_send"] is True
    bad = call("chase_message_lint", message="Hi, just checking in on that invoice, no rush!", invoice_id="1042", amount=8500, due_date="2026-08-15")
    assert bad["ready_to_send"] is False
    assert any("invoice number" in i for i in bad["issues"])
    assert any("apologetic" in i for i in bad["issues"])
    aggressive = call("chase_message_lint", message=GOOD + " This is unacceptable.", invoice_id="1042", amount=8500, due_date="2026-08-15", touch=2)
    assert any("aggressive" in i for i in aggressive["issues"])


def test_chase_message_lint_bad_input():
    with pytest.raises(ToolError):
        call("chase_message_lint", message="   ", invoice_id="1", amount=10, due_date="2026-01-01")
    with pytest.raises(ToolError):
        call("chase_message_lint", message="x", invoice_id="1", amount=10, due_date="2026-01-01", touch=9)
