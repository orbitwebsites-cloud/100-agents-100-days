"""System Design Advisor tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("system-design")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_estimate_capacity_numbers():
    out = call("estimate_capacity", daily_active_users=5_000_000, actions_per_user_per_day=20, read_write_ratio=10, avg_record_bytes=512, growth_pct_per_year=50, years=3)
    assert out["requests_per_day"] == 100_000_000
    assert out["avg_qps"] == 1157.4 and out["peak_qps"] == 3472.2
    assert out["write_qps"]["peak"] == 315.7 and out["read_qps"]["peak"] == 3156.6
    assert out["writes_per_day"] == 9_090_909
    assert out["storage_per_day"] == "4.65 GB"
    assert out["projection"][2]["dau"] == 11_250_000 and out["projection"][2]["peak_qps"] == 7812.5
    assert out["projection"][2]["storage_replicated"] == "11.47 TB"


def test_estimate_capacity_rejects_zero_users():
    with pytest.raises(ToolError):
        call("estimate_capacity", daily_active_users=0, actions_per_user_per_day=5)


def test_latency_budget_sequential_parallel_fanout():
    out = call("latency_budget", target_p99_ms=300, hops=[
        {"name": "auth", "p50_ms": 5, "p99_ms": 30},
        {"name": "search", "p50_ms": 20, "p99_ms": 120, "fanout": 40},
        {"name": "db", "p50_ms": 8, "p99_ms": 60},
        {"name": "render", "p50_ms": 10, "p99_ms": 40, "parallel_group": "x"},
        {"name": "ads", "p50_ms": 15, "p99_ms": 90, "parallel_group": "x"},
    ])
    assert out["p99_upper_bound_ms"] == 300.0 and out["meets_target"] is True
    assert out["dominant_hop"] == "search"
    search = out["hops"][1]
    assert search["p_any_straggler_pct"] == 33.1
    assert out["total_p50_ms"] == 81.1  # 5 + (20 + 100*0.331) + 8 + max(10, 15)
    assert any("fans out to 40" in r for r in out["recommendations"])
    over = call("latency_budget", target_p99_ms=100, hops=[{"name": "a", "p50_ms": 50, "p99_ms": 150}])
    assert over["meets_target"] is False and "OVER by 50ms" in over["verdict"]


def test_latency_budget_rejects_p99_below_p50():
    with pytest.raises(ToolError):
        call("latency_budget", target_p99_ms=100, hops=[{"name": "a", "p50_ms": 50, "p99_ms": 20}])


def test_availability_math_series_and_redundancy():
    out = call("availability_math", components=[
        {"name": "lb", "availability_pct": 99.99},
        {"name": "api", "availability_pct": 99.9, "redundancy": 3},
        {"name": "db", "availability_pct": 99.95},
        {"name": "payments api", "availability_pct": 99.9},
    ], target_pct=99.95)
    assert out["composite_pct"] == 99.8401
    assert out["weakest_link"] == "payments api"
    assert out["meets_target"] is False
    api = next(c for c in out["components"] if c["name"] == "api")
    assert api["effective_pct"] == 100.0 or api["effective_pct"] > 99.9999
    assert out["downtime"]["per_month"] == "69.1 min"
    assert out["if_weakest_gets_one_more_replica"]["composite_pct"] == 99.9399


def test_availability_math_rejects_over_100():
    with pytest.raises(ToolError):
        call("availability_math", components=[{"name": "x", "availability_pct": 101}])


def test_size_fleet():
    out = call("size_fleet", peak_rps=12000, per_instance_rps=500, target_utilization_pct=60, zones=3, n_plus=1, growth_headroom_pct=20, instance_cost_per_month=150)
    assert out["instances_for_demand"] == 48
    assert out["instances_for_zone_loss"] == 72
    assert out["instances_total"] == 75 and out["per_zone"] == 25
    assert out["capacity_rps_after_zone_loss"] == 15000.0
    assert out["monthly_cost"] == 11250.0
    assert out["utilisation_at_peak_pct"] == 32.0


def test_size_fleet_rejects_zero_zones():
    with pytest.raises(ToolError):
        call("size_fleet", peak_rps=100, per_instance_rps=10, zones=0)


def test_cache_math():
    out = call("cache_math", request_rps=10000, hit_rate_pct=90, cache_latency_ms=1, origin_latency_ms=50, working_set_items=5_000_000, avg_item_bytes=2000, ttl_seconds=60)
    assert out["current"] == {"hit_rate_pct": 90.0, "origin_rps": 1000.0, "origin_load_reduction_x": 10.0, "avg_latency_ms": 6.0, "p_miss_pct": 10.0}
    assert out["memory_estimate"] == "13.00 GB"
    assert out["ttl_refill_rps"] == 83333.3
    assert out["sensitivity"][-1]["origin_rps"] == 100.0
    assert any("stampede" in n for n in out["notes"])


def test_cache_math_rejects_bad_hit_rate():
    with pytest.raises(ToolError):
        call("cache_math", request_rps=100, hit_rate_pct=120)


def test_capacity_id_space_for_short_codes():
    out = call("estimate_capacity", daily_active_users=100_000_000, actions_per_user_per_day=11, read_write_ratio=10,
               avg_record_bytes=100, retention_days=0, peak_multiplier=1, replication_factor=1, years=10)
    assert out["id_space"] == {"records_over_horizon": 365_000_000_000, "base62_chars": 7, "base36_chars": 8, "hex_chars": 10,
                               "fits_int32": False, "fits_int64": True}
