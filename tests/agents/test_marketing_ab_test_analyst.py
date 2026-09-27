"""A/B Test Analyst — statistics checked against textbook values."""

import math

import pytest

from hundred import registry
from hundred.agents.marketing._common import chi2_sf, norm_cdf, norm_ppf
from hundred.agents.marketing.ab_test_analyst import t_ppf, t_sf
from hundred.core import ToolError

A = registry.get("ab-test-analyst")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_normal_functions_match_tables():
    assert abs(norm_ppf(0.975) - 1.959964) < 1e-5
    assert abs(norm_ppf(0.8) - 0.841621) < 1e-5
    assert abs(norm_ppf(0.001) - (-3.090232)) < 1e-5
    assert abs(norm_cdf(1.96) - 0.9750021) < 1e-6
    assert abs(chi2_sf(3.841, 1) - 0.05) < 1e-3
    assert abs(chi2_sf(5.991, 2) - 0.05) < 1e-3
    assert abs(t_ppf(0.975, 10) - 2.228139) < 1e-4
    assert abs(2 * t_sf(2.0, 10) - 0.0734) < 1e-3


def test_significance_test_known_case():
    out = call("significance_test", control_visitors=12400, control_conversions=310, variant_visitors=12550, variant_conversions=362)
    assert abs(out["z"] - 1.8756) < 1e-3
    assert abs(out["p_value"] - 0.0607) < 1e-3
    assert out["significant"] is False
    assert abs(out["relative_lift_pct"] - 15.38) < 0.01
    assert out["relative_lift_ci_pct"][0] < 0 < out["relative_lift_ci_pct"][1]
    assert out["prob_variant_beats_control_pct"] == 97.0


def test_significance_test_one_sided_and_clear_win():
    out = call("significance_test", control_visitors=10000, control_conversions=300, variant_visitors=10000, variant_conversions=400, two_sided=False)
    assert out["significant"] is True
    assert out["p_value"] < 0.001
    assert "Twyman" in out["verdict"]  # +33% relative lift triggers the sanity warning


def test_significance_test_rejects_bad_counts():
    with pytest.raises(ToolError):
        call("significance_test", control_visitors=100, control_conversions=150, variant_visitors=100, variant_conversions=10)


def test_sample_size_matches_standard_formula():
    out = call("sample_size", baseline_rate_pct=3.2, mde_relative_pct=10, daily_visitors=4000)
    assert out["visitors_per_arm"] == 49777
    assert out["visitors_total"] == 99554
    assert out["days_needed"] == 25
    assert out["recommended_runtime_days"] == 28
    # Larger MDE → fewer visitors; three arms → more total
    assert call("sample_size", baseline_rate_pct=3.2, mde_relative_pct=20)["visitors_per_arm"] < 49777
    assert call("sample_size", baseline_rate_pct=3.2, mde_relative_pct=10, variants=3)["visitors_total"] == 3 * 49777


def test_sample_size_rejects_impossible_target():
    with pytest.raises(ToolError):
        call("sample_size", baseline_rate_pct=60, mde_relative_pct=80)


def test_alpha_correction_pocock_and_bonferroni():
    out = call("alpha_correction", looks=10)
    assert out["bonferroni_alpha_per_test"] == 0.005
    assert out["pocock_alpha_per_look"] == 0.0106
    assert out["naive_false_positive_rate_pct"] == 19.3
    multi = call("alpha_correction", looks=1, variants=4)
    assert abs(multi["bonferroni_alpha_per_test"] - 0.05 / 3) < 1e-5
    assert abs(multi["sidak_alpha_per_test"] - (1 - 0.95 ** (1 / 3))) < 1e-5


def test_alpha_correction_rejects_bad_looks():
    with pytest.raises(ToolError):
        call("alpha_correction", looks=0)


def test_srm_check_detects_mismatch():
    ok = call("srm_check", expected_split_pct=[50, 50], observed_visitors=[10000, 10100])
    assert ok["srm_detected"] is False
    bad = call("srm_check", expected_split_pct=[50, 50], observed_visitors=[10000, 11000])
    assert bad["srm_detected"] is True
    assert abs(bad["chi_square"] - 47.619) < 0.01
    assert bad["p_value"] < 1e-6


def test_srm_check_rejects_length_mismatch():
    with pytest.raises(ToolError):
        call("srm_check", expected_split_pct=[50, 50], observed_visitors=[100])


def test_continuous_metric_test_welch():
    out = call("continuous_metric_test", control_mean=50, control_sd=20, control_n=100, variant_mean=55, variant_sd=22, variant_n=100)
    assert abs(out["t"] - 1.6817) < 1e-3
    assert abs(out["df"] - 196.2) < 0.2
    assert abs(out["p_value"] - 0.0942) < 1e-3
    assert out["significant"] is False
    assert out["relative_lift_pct"] == 10.0
    assert math.isclose(out["difference_ci"][1] - out["difference_ci"][0], 2 * 1.9721 * math.sqrt(4 + 4.84), rel_tol=1e-3)


def test_continuous_metric_test_rejects_tiny_arm():
    with pytest.raises(ToolError):
        call("continuous_metric_test", control_mean=1, control_sd=1, control_n=1, variant_mean=2, variant_sd=1, variant_n=10)


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("srm_check").call({"expected_split_pct": "half", "observed_visitors": [1, 2]})
