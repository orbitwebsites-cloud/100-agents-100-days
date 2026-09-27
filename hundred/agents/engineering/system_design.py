"""System Design Advisor — back-of-the-envelope numbers before the whiteboard.

Tools compute capacity (QPS, storage, bandwidth with growth), latency budgets
with fan-out tail effects, composite availability, fleet sizing with AZ loss,
and cache economics — the arithmetic interviews and design reviews get wrong.
"""

from __future__ import annotations

import math

from ...core import Agent, ToolError
from ._common import bound_list, human_bytes, human_number

AGENT = Agent(
    slug="system-design",
    name="System Design Advisor",
    category="engineering",
    tagline="Design systems with numbers: capacity, latency budgets, availability math and fleet sizing computed, then the architecture that fits them.",
    description=(
        "Runs a system-design review the way a principal engineer does: requirements → numbers → "
        "architecture → trade-offs → failure modes. Computes QPS, storage and bandwidth with peaks, "
        "replication and growth; allocates a latency budget across hops with fan-out tail math; "
        "derives composite availability and downtime from component SLAs; sizes a fleet for AZ loss and "
        "headroom; and prices cache hit rates against origin load. Works for design docs, interviews "
        "and capacity plans."
    ),
    triggers=[
        "design a system for … / how would you architect …",
        "how many servers / how much storage do we need",
        "estimate QPS / capacity / bandwidth for …",
        "what availability can we promise with these components",
        "latency budget for this request path",
        "system design interview practice / review my design doc",
    ],
    examples=[
        "Design a URL shortener for 100M new links a month and 10:1 read/write — with the numbers.",
        "We have 5M DAU each doing 20 actions a day; what's peak QPS and storage after 3 years?",
        "Our API calls 3 services in sequence and fans out to 40 shards; can we hit a 300ms p99?",
    ],
    connectors=["Notion", "Google Docs", "Confluence", "GitHub", "Linear", "Jira"],
    playbook="""
    ## Standard
    You are a principal engineer reviewing a design. Excellent means: every architectural
    choice is justified by a number (QPS, bytes, ms, nines) or a named failure mode, the
    design is the simplest one that meets the numbers with 3-5× headroom, and the reader
    knows what breaks first when load doubles. The one metric: **does the design survive the
    stated scale and the top three failure modes, with no unexplained component?**

    ## Intake
    You need: functional requirements (the 3-5 core operations), scale (users, actions per
    user, data size, growth), and non-functional targets (latency p99, availability,
    consistency, durability, cost sensitivity). Missing numbers: assume typical values, state
    them in an "Assumptions" block, and continue — ask at most 3 questions only if the core
    operations themselves are unclear.

    ## Procedure
    1. **Pin the requirements** in one table: operations, read/write mix, latency target per
       operation, consistency need (strong vs eventual, per operation, not globally), and
       durability. Note what is explicitly out of scope.
    2. **Compute the envelope.** Call `system_design__estimate_capacity` with DAU, actions/user
       /day, read:write ratio, payload sizes, retention, peak multiplier (3× default; 10× for
       spiky consumer traffic), replication factor and growth. Use the peak QPS, storage at
       year 3 and egress numbers everywhere below; never estimate them in your head. Its
       `id_space` gives the key length for short codes/ids (e.g. 365B records → 7 base62
       chars) and whether an int32 primary key overflows within the horizon.
    3. **Sketch the simplest architecture** that handles the envelope: client → LB → stateless
       API → primary datastore, plus a cache and a queue only if the numbers demand them.
       Add a component only when you can name the number that forces it (e.g. "peak read QPS
       48k exceeds a single primary's comfortable range → read replicas + cache").
    4. **Budget the latency** of the critical path with `system_design__latency_budget`: list
       each hop's p50/p99 and any fan-out. If the p99 upper bound exceeds the target, cut
       hops, parallelise, cache, or hedge; if fan-out is > 10, the tool's tail probability
       tells you why the p99 of the whole is worse than any component's.
    5. **Do the availability math** with `system_design__availability_math` for the serial
       chain of dependencies (each with its redundancy). If the composite is below target,
       the tool names the dominant component — fix that one (redundancy, degrade gracefully,
       remove it from the critical path) rather than gold-plating everything.
    6. **Size the fleet** with `system_design__size_fleet` (peak RPS, per-instance RPS at the
       target utilisation, zones, N+1, growth headroom). For caches, run
       `system_design__cache_math` to show origin load and latency at candidate hit rates and
       the memory required for the working set.
    7. **Walk the failure modes**: for each component, what happens when it is slow, down, or
       partitioned; what the user sees; how it recovers. Name the three most likely and the
       single point of failure if one remains.
    8. **Write the trade-offs** you rejected and why (e.g. "Cassandra rejected: strong
       consistency needed on balance reads"). A design doc without rejected alternatives
       hasn't been designed.
    9. **Deliver** in the output format, numbers first.

    ## Frameworks
    - **Back-of-the-envelope**: seconds/day ≈ 86,400 (≈ 10⁵ for mental math); 1M requests/day
      ≈ 12 QPS; peak = 2-3× average for B2B, 5-10× for consumer/media. Storage/year = writes/
      day × bytes × 365 × replication.
    - **Latency numbers to internalise**: memory ~100 ns, SSD read ~100 µs, same-DC RTT
      ~0.5 ms, cross-region ~50-150 ms, disk seek ~10 ms. Every network hop adds RTT plus the
      dependency's own tail.
    - **Tail at scale** (Dean & Barroso): with fan-out n, P(at least one p99 straggler) =
      1 − 0.99ⁿ; n=100 → 63%. Fixes: hedged requests, tied requests, partial results,
      smaller fan-out, per-hop timeouts below the remaining budget.
    - **Availability**: serial components multiply (0.999 × 0.999 = 0.998); parallel
      redundancy: 1 − (1 − a)ⁿ. 99.9% = 43.8 min/month down; 99.99% = 4.4 min.
    - **CAP/PACELC**: under partition choose availability or consistency *per operation*;
      else trade latency for consistency. Money and inventory: strong; feeds and counters: eventual.
    - **Scaling ladder**: vertical → read replicas → cache → sharding (choose the key by access
      pattern; avoid hot keys; plan resharding) → CQRS/event streaming only when read and
      write models truly diverge.
    - **Headroom rule**: design for 3-5× current peak; alert at 60-70% utilisation.

    ## Output format
    ```
    # <System> — design
    **Requirements:** <ops, latency, availability, consistency> · **Assumptions:** <stated>

    ## Numbers
    | Metric | Value | Notes |  (peak QPS r/w, storage y1/y3, egress, fleet size, cache size)

    ## Architecture
    <component list with the number that justifies each> + text diagram
    client → LB → API (n instances) → cache → primary/replicas ; queue → workers

    ## Data model & storage choice
    <key entities, access patterns, partition key, why this store>

    ## Critical path latency budget
    | Hop | p50 | p99 | Notes |  → total vs target

    ## Availability & failure modes
    | Component | Redundancy | Effective | Failure mode | User sees | Recovery |

    ## Trade-offs and rejected alternatives
    ## Scaling plan (what breaks first at 10×, and the fix)
    ## Open questions
    ```

    ## Anti-patterns
    - Drawing Kafka, Redis, Elasticsearch and Cassandra before computing a single QPS.
    - Global "strong consistency" or "eventual consistency" instead of per-operation choices.
    - Summing p50s and calling it the p99. Or ignoring fan-out tail.
    - Announcing 99.99% while depending serially on a 99.9% third party.
    - Sharding by a key that puts every hot customer on one shard.
    - Designing for today's load with no headroom, or for 1000× with no budget.
    - No rejected alternatives, no failure modes, no "what breaks first".
    """,
)


def _pos(name: str, value: float, allow_zero: bool = False) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be a number.") from None
    if v < 0 or (v == 0 and not allow_zero):
        raise ToolError(f"{name} must be {'≥' if allow_zero else '>'} 0.")
    if math.isnan(v) or math.isinf(v):
        raise ToolError(f"{name} must be finite.")
    return v


def _key_len(records: float, base: int) -> int:
    """Smallest n with base**n >= records (integer arithmetic — no float log rounding)."""
    n, cap, need = 1, base, math.ceil(records)
    while cap < need:
        n += 1
        cap *= base
    return n


@AGENT.tool
def estimate_capacity(
    daily_active_users: float,
    actions_per_user_per_day: float,
    read_write_ratio: float = 10,
    avg_request_bytes: float = 1024,
    avg_record_bytes: float = 512,
    retention_days: int = 365,
    peak_multiplier: float = 3,
    replication_factor: int = 3,
    growth_pct_per_year: float = 0,
    years: int = 3,
) -> dict:
    """Compute the capacity envelope: requests/day, average and peak QPS split into reads and writes, storage per day/year with retention and replication, growth projections, peak ingress/egress bandwidth, and the ID space (records over the horizon → base62/base36/hex key length, int32/int64 fit).

    Call before drawing any architecture; use its peak numbers everywhere.

    Args:
        daily_active_users: Daily active users (or clients).
        actions_per_user_per_day: Requests each user makes per day on average.
        read_write_ratio: Reads per write (10 means 10:1).
        avg_request_bytes: Average bytes per request/response payload on the wire.
        avg_record_bytes: Average bytes stored per write (row/object incl. indexes).
        retention_days: How long written data is kept (0 = forever, projected over `years`).
        peak_multiplier: Peak QPS as a multiple of average (3 typical; 5-10 for spiky consumer traffic).
        replication_factor: Copies of each stored byte (3 typical).
        growth_pct_per_year: Compound growth of users per year, e.g. 50 for +50%/year.
        years: Projection horizon in years (1-10).
    """
    dau = _pos("daily_active_users", daily_active_users)
    apu = _pos("actions_per_user_per_day", actions_per_user_per_day)
    rw = _pos("read_write_ratio", read_write_ratio, allow_zero=True)
    req_b = _pos("avg_request_bytes", avg_request_bytes)
    rec_b = _pos("avg_record_bytes", avg_record_bytes)
    peak = _pos("peak_multiplier", peak_multiplier)
    rf = int(_pos("replication_factor", replication_factor))
    growth = _pos("growth_pct_per_year", growth_pct_per_year, allow_zero=True) / 100
    years = int(years)
    if not 1 <= years <= 10:
        raise ToolError("years must be 1-10.")
    if retention_days < 0:
        raise ToolError("retention_days cannot be negative.")
    per_day = dau * apu
    avg_qps = per_day / 86400
    write_frac = 1 / (1 + rw)
    writes_day = per_day * write_frac
    reads_day = per_day - writes_day
    w_qps, r_qps = avg_qps * write_frac, avg_qps * (1 - write_frac)
    storage_day = writes_day * rec_b
    horizon_days = years * 365
    effective_retention = min(retention_days, horizon_days) if retention_days else horizon_days
    projections = []
    cumulative_raw = 0.0
    for y in range(1, years + 1):
        factor = (1 + growth) ** (y - 1)
        year_writes = writes_day * factor * 365
        cumulative_raw += year_writes * rec_b
        # data retained at end of year y: last `effective_retention` days of writes (approximate with current-year rate)
        if retention_days and retention_days < 365 * y:
            retained = writes_day * factor * effective_retention * rec_b
        else:
            retained = cumulative_raw
        projections.append({
            "year": y, "dau": round(dau * factor), "avg_qps": round(avg_qps * factor, 1), "peak_qps": round(avg_qps * factor * peak, 1),
            "storage_raw": human_bytes(retained), "storage_replicated": human_bytes(retained * rf), "storage_raw_bytes": round(retained),
        })
    total_records = sum(writes_day * (1 + growth) ** (y - 1) * 365 for y in range(1, years + 1))
    id_space = {
        "records_over_horizon": round(total_records),
        "base62_chars": _key_len(total_records, 62),
        "base36_chars": _key_len(total_records, 36),
        "hex_chars": _key_len(total_records, 16),
        "fits_int32": total_records < 2**31,
        "fits_int64": total_records < 2**63,
    }
    peak_w, peak_r = w_qps * peak, r_qps * peak
    ingress_bps = peak_w * req_b * 8
    egress_bps = peak_r * req_b * 8
    notes = []
    last = projections[-1]
    if last["peak_qps"] >= 10_000:
        notes.append(f"Peak {human_number(last['peak_qps'])} QPS in year {years}: stateless tier must be horizontally scaled; a single relational primary is usually uncomfortable above low-thousands of writes/s — plan replicas/cache/sharding by write rate ({human_number(peak_w * (1 + growth) ** (years - 1))} writes/s at peak).")
    if last["storage_raw_bytes"] * rf > 10 * 1000**4:
        notes.append("Replicated storage exceeds 10 TB by the horizon — plan partitioning/tiering (hot vs cold) and a retention policy.")
    if egress_bps > 1e9:
        notes.append(f"Peak egress {egress_bps / 1e9:.1f} Gbps — a CDN/edge cache for static or cacheable responses pays for itself.")
    if peak >= 5:
        notes.append("High peak multiplier: autoscaling reacts in minutes; pre-provision or queue-buffer the spike.")
    return {
        "inputs": {"dau": dau, "actions_per_user_per_day": apu, "read_write_ratio": rw, "peak_multiplier": peak, "replication_factor": rf, "retention_days": retention_days, "growth_pct_per_year": growth * 100},
        "requests_per_day": round(per_day),
        "writes_per_day": round(writes_day),
        "reads_per_day": round(reads_day),
        "avg_qps": round(avg_qps, 1),
        "peak_qps": round(avg_qps * peak, 1),
        "write_qps": {"avg": round(w_qps, 2), "peak": round(peak_w, 1)},
        "read_qps": {"avg": round(r_qps, 2), "peak": round(peak_r, 1)},
        "storage_per_day": human_bytes(storage_day),
        "storage_per_year_raw": human_bytes(storage_day * 365),
        "storage_per_year_replicated": human_bytes(storage_day * 365 * rf),
        "projection": projections,
        "id_space": id_space,
        "bandwidth_peak": {"ingress": f"{ingress_bps / 1e6:.1f} Mbps", "egress": f"{egress_bps / 1e6:.1f} Mbps", "ingress_bytes_per_s": round(peak_w * req_b), "egress_bytes_per_s": round(peak_r * req_b)},
        "notes": notes,
        "summary": (f"{human_number(per_day)} req/day → avg {avg_qps:,.0f} QPS, peak {avg_qps * peak:,.0f} QPS ({peak_r:,.0f} r / {peak_w:,.0f} w). "
                    f"Storage {human_bytes(storage_day)}/day, {last['storage_replicated']} replicated by year {years}. Peak egress {egress_bps / 1e6:.0f} Mbps."),
    }


@AGENT.tool
def latency_budget(target_p99_ms: float, hops: list[dict]) -> dict:
    """Allocate a latency budget across the hops of a request path: sequential p50 and p99 totals (parallel groups take the max), fan-out tail probability, remaining budget, the dominant hop, and per-hop timeout suggestions.

    Call for the critical path of every design; if the p99 bound exceeds the target, restructure.

    Args:
        target_p99_ms: The end-to-end p99 target in milliseconds.
        hops: Each {"name": str, "p50_ms": number, "p99_ms": number, "parallel_group": str (optional; hops sharing a group run concurrently), "fanout": int (optional; calls made in parallel to N shards/backends)}.
    """
    target = _pos("target_p99_ms", target_p99_ms)
    hops = bound_list(hops, "hops", 50)
    groups: dict[str, list[dict]] = {}
    ordered: list[tuple[str, list[dict]]] = []
    rows = []
    for i, h in enumerate(hops, 1):
        if not isinstance(h, dict) or not h.get("name"):
            raise ToolError(f"hop #{i} needs a name.")
        p50 = _pos(f"hop {h['name']} p50_ms", h.get("p50_ms", 0), allow_zero=True)
        p99 = _pos(f"hop {h['name']} p99_ms", h.get("p99_ms", p50), allow_zero=True)
        if p99 < p50:
            raise ToolError(f"hop {h['name']}: p99 ({p99}) cannot be below p50 ({p50}).")
        fan = int(h.get("fanout") or 1)
        if fan < 1:
            raise ToolError(f"hop {h['name']}: fanout must be ≥ 1.")
        tail_prob = 1 - 0.99 ** fan
        # with fan-out, the effective p50 of "wait for all" moves toward p99 as n grows
        eff_p50 = p50 if fan == 1 else p50 + (p99 - p50) * min(1.0, tail_prob)
        row = {"name": h["name"], "p50_ms": p50, "p99_ms": p99, "fanout": fan, "p_any_straggler_pct": round(100 * tail_prob, 1) if fan > 1 else None, "effective_p50_ms": round(eff_p50, 1), "effective_p99_ms": p99}
        key = str(h.get("parallel_group") or f"__seq_{i}")
        if key not in groups:
            groups[key] = []
            ordered.append((key, groups[key]))
        groups[key].append(row)
        rows.append(row)
    total_p50 = sum(max(r["effective_p50_ms"] for r in g) for _, g in ordered)
    total_p99 = sum(max(r["effective_p99_ms"] for r in g) for _, g in ordered)
    # a more realistic p99 for a chain: p50s plus the largest tail (straggling in several hops at once is rarer)
    tails = sorted((max(r["effective_p99_ms"] for r in g) - max(r["effective_p50_ms"] for r in g) for _, g in ordered), reverse=True)
    likely_p99 = total_p50 + (tails[0] if tails else 0) + 0.5 * sum(tails[1:3])
    for r in rows:
        r["share_of_p99_pct"] = round(100 * r["effective_p99_ms"] / total_p99, 1) if total_p99 else 0
        r["suggested_timeout_ms"] = round(min(r["p99_ms"] * 1.5, target * 0.8), 0)
    dominant = max(rows, key=lambda r: r["effective_p99_ms"])
    remaining = target - total_p99
    utilisation = round(100 * total_p99 / target, 1)
    recommendations = []
    if total_p99 > target:
        recommendations.append(f"p99 upper bound {total_p99:.0f}ms exceeds the {target:.0f}ms target by {total_p99 - target:.0f}ms — start with '{dominant['name']}' ({dominant['share_of_p99_pct']}% of the bound).")
    if likely_p99 > target:
        recommendations.append(f"Even the optimistic estimate ({likely_p99:.0f}ms) misses the target; a structural change is needed (remove a hop, cache, or parallelise).")
    seq_groups = [g for _, g in ordered if len(g) == 1]
    if len(seq_groups) >= 3:
        recommendations.append(f"{len(seq_groups)} sequential hops — check which are independent and run them concurrently (parallel_group).")
    big_fan = [r for r in rows if r["fanout"] >= 10]
    for r in big_fan:
        recommendations.append(f"'{r['name']}' fans out to {r['fanout']}: {r['p_any_straggler_pct']}% of requests hit at least one p99 straggler — use hedged requests after ~p95, or return partial results.")
    if remaining > 0.4 * target:
        recommendations.append(f"{remaining:.0f}ms of headroom ({100 - utilisation:.0f}%) — comfortable; keep per-hop timeouts inside the budget so a slow dependency can't consume it all.")
    return {
        "target_p99_ms": target,
        "hops": rows,
        "total_p50_ms": round(total_p50, 1),
        "p99_upper_bound_ms": round(total_p99, 1),
        "p99_likely_ms": round(likely_p99, 1),
        "remaining_ms": round(remaining, 1),
        "budget_utilisation_pct": utilisation,
        "dominant_hop": dominant["name"],
        "meets_target": total_p99 <= target,
        "recommendations": recommendations,
        "verdict": (f"p50 {total_p50:.0f}ms, p99 bound {total_p99:.0f}ms (likely ~{likely_p99:.0f}ms) vs target {target:.0f}ms — "
                    + ("within budget" if total_p99 <= target else f"OVER by {total_p99 - target:.0f}ms") + f"; dominant hop: {dominant['name']}."),
    }


@AGENT.tool
def availability_math(components: list[dict], target_pct: float = 99.9) -> dict:
    """Compute composite availability of a dependency chain: each component's effective availability with N redundant instances (1 − (1 − a)^n), the serial product, downtime per year/month/week, the dominant weak link, and what one more replica of it would buy.

    Call for every design that promises an SLA; the third-party dependency usually decides it.

    Args:
        components: Each {"name": str, "availability_pct": number, "redundancy": int (independent instances, default 1)}. All are assumed in series (all needed).
        target_pct: The availability you want to promise, e.g. 99.9.
    """
    components = bound_list(components, "components", 100)
    if not 0 < target_pct < 100:
        raise ToolError("target_pct must be between 0 and 100.")
    rows = []
    total = 1.0
    for i, c in enumerate(components, 1):
        if not isinstance(c, dict) or not c.get("name"):
            raise ToolError(f"component #{i} needs a name.")
        a = _pos(f"{c['name']} availability_pct", c.get("availability_pct", 0)) / 100
        if a > 1:
            raise ToolError(f"{c['name']}: availability_pct cannot exceed 100.")
        n = int(c.get("redundancy") or 1)
        if n < 1:
            raise ToolError(f"{c['name']}: redundancy must be ≥ 1.")
        eff = 1 - (1 - a) ** n
        total *= eff
        rows.append({"name": c["name"], "availability_pct": round(a * 100, 4), "redundancy": n, "effective_pct": round(eff * 100, 5), "downtime_per_month_min": round((1 - eff) * 30 * 1440, 1)})
    weakest = min(rows, key=lambda r: r["effective_pct"])
    year_min = (1 - total) * 365 * 1440
    nines = -math.log10(1 - total) if total < 1 else float("inf")
    improved = None
    w = next(c for c in components if c["name"] == weakest["name"])
    a_w = float(w.get("availability_pct")) / 100
    n_w = int(w.get("redundancy") or 1)
    eff_w_new = 1 - (1 - a_w) ** (n_w + 1)
    total_new = total / (weakest["effective_pct"] / 100) * eff_w_new
    improved = {"component": weakest["name"], "redundancy": n_w + 1, "composite_pct": round(total_new * 100, 4), "downtime_per_month_min": round((1 - total_new) * 30 * 1440, 1)}
    meets = total * 100 >= target_pct
    notes = []
    if not meets:
        notes.append(f"Composite {total * 100:.3f}% is below the {target_pct}% target; the weakest link is {weakest['name']} at {weakest['effective_pct']}%.")
        if total_new * 100 >= target_pct:
            notes.append(f"Adding one independent instance of {weakest['name']} (→ {improved['composite_pct']}%) would meet the target — only if failures are independent (different AZ/provider).")
        else:
            notes.append("Redundancy on the weakest link alone is not enough — remove a dependency from the critical path or degrade gracefully when it fails.")
    if any(r["redundancy"] > 1 for r in rows):
        notes.append("Redundancy math assumes independent failures; shared power, deploys, config or a common upstream break the assumption.")
    return {
        "components": rows,
        "composite_pct": round(total * 100, 4),
        "nines": round(nines, 2) if nines != float("inf") else None,
        "downtime": {"per_year": f"{year_min / 60:.1f} h", "per_month": f"{(1 - total) * 30 * 1440:.1f} min", "per_week": f"{(1 - total) * 7 * 1440:.1f} min", "per_year_minutes": round(year_min, 1)},
        "target_pct": target_pct,
        "meets_target": meets,
        "weakest_link": weakest["name"],
        "if_weakest_gets_one_more_replica": improved,
        "notes": notes,
        "verdict": f"Composite {total * 100:.3f}% ({(1 - total) * 30 * 1440:.1f} min/month down) — {'meets' if meets else 'MISSES'} {target_pct}%; weakest link: {weakest['name']}.",
    }


@AGENT.tool
def size_fleet(peak_rps: float, per_instance_rps: float, target_utilization_pct: float = 60, zones: int = 3, n_plus: int = 1, growth_headroom_pct: float = 20, instance_cost_per_month: float = 0) -> dict:
    """Size a stateless fleet: instances for peak at target utilisation plus growth headroom, enough to survive losing one zone, plus N+k spares, spread per zone, with monthly cost.

    Call once peak RPS (from estimate_capacity) and a measured per-instance throughput exist.

    Args:
        peak_rps: Peak requests per second the fleet must serve.
        per_instance_rps: Throughput of one instance at 100% (from a load test).
        target_utilization_pct: Utilisation you run at under peak (60-70% typical; lower for latency-sensitive).
        zones: Availability zones the fleet spans (1 = no zone redundancy).
        n_plus: Extra spare instances beyond zone-loss capacity (N+1 typical).
        growth_headroom_pct: Extra capacity for growth before the next resize.
        instance_cost_per_month: Cost of one instance per month, for the total.
    """
    peak = _pos("peak_rps", peak_rps)
    per = _pos("per_instance_rps", per_instance_rps)
    util = _pos("target_utilization_pct", target_utilization_pct) / 100
    if util > 1:
        raise ToolError("target_utilization_pct cannot exceed 100.")
    zones = int(zones)
    if zones < 1:
        raise ToolError("zones must be ≥ 1.")
    if n_plus < 0:
        raise ToolError("n_plus cannot be negative.")
    growth = _pos("growth_headroom_pct", growth_headroom_pct, allow_zero=True) / 100
    cost = _pos("instance_cost_per_month", instance_cost_per_month, allow_zero=True)
    demand = peak * (1 + growth)
    base = math.ceil(demand / (per * util))
    zone_loss = math.ceil(base * zones / (zones - 1)) if zones > 1 else base
    total = zone_loss + int(n_plus)
    per_zone = math.ceil(total / zones)
    total = per_zone * zones  # even spread
    capacity = total * per * util
    surviving = (total - per_zone) * per * util if zones > 1 else capacity
    notes = []
    if zones == 1:
        notes.append("Single zone: any zone incident is a full outage — the fleet sizing gives no availability.")
    if per_zone < 2 and zones > 1:
        notes.append("Fewer than 2 instances per zone: a single instance failure removes a whole zone's share; consider smaller instances.")
    if base <= 2:
        notes.append("Tiny fleet — rounding dominates; the cost of N+1 and zone loss is proportionally large but still cheaper than an outage.")
    return {
        "demand_rps_with_headroom": round(demand, 1),
        "instances_for_demand": base,
        "instances_for_zone_loss": zone_loss,
        "instances_total": total,
        "per_zone": per_zone,
        "capacity_rps_at_target_util": round(capacity, 1),
        "capacity_rps_after_zone_loss": round(surviving, 1),
        "utilisation_at_peak_pct": round(100 * peak / (total * per), 1),
        "monthly_cost": round(total * cost, 2) if cost else None,
        "notes": notes,
        "verdict": (f"{total} instances ({per_zone} × {zones} zones): {base} for {demand:,.0f} rps at {util * 100:.0f}% util, {zone_loss - base} for zone loss, +{int(n_plus)} spare. "
                    f"Runs at {100 * peak / (total * per):.0f}% at today's peak" + (f"; ~{total * cost:,.0f}/month." if cost else ".")),
    }


@AGENT.tool
def cache_math(request_rps: float, hit_rate_pct: float, cache_latency_ms: float = 1, origin_latency_ms: float = 50, working_set_items: float = 0, avg_item_bytes: float = 0, ttl_seconds: float = 0) -> dict:
    """Quantify a cache: origin load after caching, average latency (misses pay both), sensitivity at 50/80/90/95/99% hit rates, memory for the working set, and TTL refill/stampede rate.

    Call when proposing a cache; show the origin-load reduction, not just "add Redis".

    Args:
        request_rps: Requests per second hitting the cache layer (peak).
        hit_rate_pct: Expected cache hit rate, 0-100.
        cache_latency_ms: Latency of a cache hit (0.5-2 ms typical for Redis in-DC).
        origin_latency_ms: Latency of the origin (database/service) on a miss.
        working_set_items: Number of distinct hot items to hold (0 = unknown).
        avg_item_bytes: Average serialized size of one item (0 = unknown).
        ttl_seconds: TTL per item, for refill-rate math (0 = no TTL).
    """
    rps = _pos("request_rps", request_rps)
    hit = _pos("hit_rate_pct", hit_rate_pct, allow_zero=True) / 100
    if hit > 1:
        raise ToolError("hit_rate_pct cannot exceed 100.")
    cl = _pos("cache_latency_ms", cache_latency_ms, allow_zero=True)
    ol = _pos("origin_latency_ms", origin_latency_ms)
    items = _pos("working_set_items", working_set_items, allow_zero=True)
    ib = _pos("avg_item_bytes", avg_item_bytes, allow_zero=True)
    ttl = _pos("ttl_seconds", ttl_seconds, allow_zero=True)

    def row(h: float) -> dict:
        origin = rps * (1 - h)
        avg = h * cl + (1 - h) * (cl + ol)
        return {"hit_rate_pct": round(h * 100, 1), "origin_rps": round(origin, 1), "origin_load_reduction_x": round(rps / origin, 1) if origin else None, "avg_latency_ms": round(avg, 2), "p_miss_pct": round(100 * (1 - h), 1)}

    current = row(hit)
    table = [row(h) for h in (0.5, 0.8, 0.9, 0.95, 0.99)]
    memory = items * ib * 1.3 if items and ib else None  # ~30% overhead for keys/metadata
    refill = items / ttl if items and ttl else None
    notes = []
    if hit < 0.8:
        notes.append("Hit rate below 80%: the cache barely halves origin load — check key cardinality, TTL and whether the traffic is cacheable at all.")
    if memory and memory > 32 * 1000**3:
        notes.append(f"Working set needs ~{human_bytes(memory)} — beyond a single large node; plan a cluster or reduce item size/TTL.")
    if refill and refill > rps * (1 - hit):
        notes.append("TTL expiry alone drives more origin traffic than misses; stagger TTLs (jitter) and use request coalescing to avoid stampedes.")
    if ttl == 0 and items:
        notes.append("No TTL: define invalidation explicitly or the cache serves stale data forever.")
    notes.append("Misses pay cache + origin latency; tail latency is set by the origin, so the cache improves averages more than p99s.")
    return {
        "current": current,
        "sensitivity": table,
        "memory_estimate": human_bytes(memory) if memory else None,
        "memory_bytes": round(memory) if memory else None,
        "ttl_refill_rps": round(refill, 1) if refill else None,
        "notes": notes,
        "verdict": (f"At {hit * 100:.0f}% hits: origin sees {current['origin_rps']:,.0f} rps ({current['origin_load_reduction_x']}× less), avg latency {current['avg_latency_ms']} ms"
                    + (f"; ~{human_bytes(memory)} of cache memory" if memory else "") + "."),
    }
