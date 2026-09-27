"""NDA Drafter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("nda-drafter")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_calculate_terms_dates():
    out = call("calculate_terms", effective_date="2026-10-01", term_months=24, survival_months=36, return_within_days=30)
    assert out["term_end"].startswith("2028-09-30")
    assert out["obligations_end_ordinary_information"].startswith("2031-09-30")
    assert out["return_or_destroy_by"].startswith("2028-10-30")
    assert out["total_protection_years"] == 5.0
    assert "perpetual" in out["trade_secrets"]
    none = call("calculate_terms", effective_date="2026-01-31", term_months=1, survival_months=0)
    assert none["term_end"].startswith("2026-02-28") and any("No survival" in n for n in none["notes"])


def test_calculate_terms_rejects_bad_months():
    with pytest.raises(ToolError):
        call("calculate_terms", effective_date="2026-10-01", term_months=0)


def test_build_nda_assembles_clauses_and_brackets():
    out = call(
        "build_nda",
        party_a={"name": "Acme Inc", "entity": "a Delaware corporation", "address": "1 Main St, Wilmington, DE", "signatory": "Jane Doe, CEO"},
        party_b={"name": "Beta Ltd"},
        purpose="evaluating a potential commercial partnership",
        effective_date="2026-10-01",
        governing_law="the State of Delaware",
        include_residuals=True,
        individuals_signing=True,
    )
    text = out["agreement_text"]
    assert out["type"] == "mutual" and out["clause_count"] == 13
    assert "MUTUAL NON-DISCLOSURE AGREEMENT" in text
    assert "1833" in text and "Residuals" in text
    assert "independently developed" in text and "required by law" in text
    assert out["to_confirm"] == ["[ENTITY TYPE, e.g. a Delaware corporation]", "[NAME, TITLE]", "[NOTICE ADDRESS]"]
    assert out["key_dates"] == {"effective": "2026-10-01", "term_end": "2028-09-30", "obligations_end": "2031-09-30"}
    one_way = call("build_nda", party_a={"name": "A"}, party_b={"name": "B"}, purpose="services", effective_date="2026-10-01", mutual=False)
    assert one_way["type"] == "one-way" and "Receiving Party" not in one_way["agreement_text"]
    assert "[GOVERNING LAW JURISDICTION]" in one_way["to_confirm"]


def test_build_nda_rejects_missing_purpose():
    with pytest.raises(ToolError):
        call("build_nda", party_a={"name": "A"}, party_b={"name": "B"}, purpose="", effective_date="2026-10-01")


BAD_NDA = """MUTUAL NON-DISCLOSURE AGREEMENT. Confidential Information means any and all information disclosed by either party.
The Receiving Party may use Residuals retained in the unaided memory of its personnel. The obligations herein shall survive
in perpetuity. The Receiving Party shall pay liquidated damages of $50,000 per breach. Neither party shall solicit the other's
employees. This Agreement is governed by the laws of the State of Texas."""

GOOD_NDA = """MUTUAL NON-DISCLOSURE AGREEMENT. Confidential Information means information marked confidential or that a reasonable person would
understand to be confidential, excluding information that is publicly available, already known to the recipient, independently developed,
or received from a third party without restriction. If required by law or court order the Receiving Party will give prompt notice.
The Receiving Party shall use reasonable care and may disclose only to Representatives with a need to know. On request the Receiving Party
shall return or destroy all Confidential Information. This Agreement has a term of two (2) years. No license is granted. The Disclosing Party
may seek injunctive relief. This Agreement is governed by the laws of Delaware."""


def test_review_nda_flags_from_discloser_side():
    out = call("review_nda", nda_text=BAD_NDA, my_role="discloser")
    clauses = [f["clause"] for f in out["findings"]]
    assert "Residuals clause — recipient may use whatever its people remember" in clauses
    assert "Exclusion: publicly available" in clauses
    assert out["risk_score"] >= 40 and "Do not sign" in out["verdict"]
    recipient = call("review_nda", nda_text=BAD_NDA, my_role="recipient")
    rclauses = [f["clause"] for f in recipient["findings"]]
    assert "Liquidated damages / penalty for breach" in rclauses and "Perpetual obligations for all information" in rclauses
    assert "Residuals clause — recipient may use whatever its people remember" not in rclauses


def test_review_nda_passes_clean_document():
    out = call("review_nda", nda_text=GOOD_NDA, my_role="both")
    assert out["risk_score"] < 15 and out["verdict"].startswith("Sign")
    assert len(out["present"]) >= 10


def test_review_nda_rejects_bad_role():
    with pytest.raises(ToolError):
        call("review_nda", nda_text=GOOD_NDA, my_role="lawyer")
