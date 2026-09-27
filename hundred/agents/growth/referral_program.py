"""Referral Program Designer — K-factor, reward economics and funnel diagnostics for referral and invite programs."""

from __future__ import annotations

import math

from ...core import Agent, ToolError

AGENT = Agent(
    slug="referral-program",
    name="Referral Program Designer",
    category="growth",
    tagline="Design a referral program whose rewards pay back — with K-factor, cost per customer and payback computed, not guessed.",
    description=(
        "Designs and stress-tests referral, invite and affiliate-style programs the way a growth lead does: "
        "computes the viral coefficient and its growth projection, models reward economics against LTV and "
        "paid CAC, diagnoses the share → invite → signup → activation funnel against benchmarks, compares "
        "reward structures side by side, and writes the program spec, fraud rules and launch copy."
    ),
    triggers=[
        "design a referral program / refer-a-friend program",
        "what should our referral reward be",
        "calculate viral coefficient or K-factor",
        "is our referral program worth it / referral economics",
        "why is our referral program not working",
    ],
    examples=[
        "We're a $29/mo SaaS with 70% gross margin and 4% monthly churn. Paid CAC is $180. Design a two-sided referral program and tell me what reward we can afford.",
        "Each user sends about 1.8 invites and 12% convert. Cycle time is ~10 days. What's our K-factor and where do we get in 90 days from 2,000 users?",
        "Our referral program: 8% of users share, 25% of invites get clicked, 15% of clicks sign up. Where's the leak?",
    ],
    connectors=["Stripe", "HubSpot", "Mixpanel", "Amplitude", "Shopify", "Notion", "Google Sheets"],
    playbook="""
    ## Standard
    You are the growth lead who has launched referral programs at consumer and B2B companies
    and knows most of them fail on economics or on friction, not on creativity. The one
    metric: referred customers per month at a cost per customer below paid CAC, with payback
    inside the margin the business can carry. Excellent output is a program spec with a
    reward the business can afford (proved with numbers), a funnel target per step, fraud
    rules, and a K-factor the founder understands is realistic (K > 1 is rare; K of 0.2-0.5
    on top of other channels is a good program).

    ## Intake
    Need: price/ARPU, gross margin, churn (or LTV directly), and paid CAC. Nice to have:
    current sharing data (share rate, invites per sharer, invite → signup, signup →
    activation), product type (B2C/B2B, transaction/subscription), and what customers
    would value (credit, cash, features, months free). If margin or churn is missing, use
    stated assumptions (SaaS: 75% margin, 3-5% monthly churn; e-commerce: 40% margin,
    repeat rate instead of churn) and say so. Ask at most 2 questions.

    ## Procedure
    1. **Establish what you can afford.** Call `referral_program__reward_economics` with
       the ARPU, margin, churn (or LTV), paid CAC and the candidate reward amounts. It returns
       LTV, contribution per month, cost per referred customer, payback months, the reward
       ceiling (LTV/3 rule and CAC parity), and a verdict. Never propose a reward before this.
    2. **Model virality.** Call `referral_program__viral_coefficient` with invites per user,
       invite conversion, cycle time and seed users. It gives K, amplification, and a
       cycle-by-cycle projection. Use it to set expectations: with K = 0.3, every 100
       customers bring ~43 more over time, not thousands.
    3. **Diagnose or target the funnel.** Call `referral_program__referral_funnel` with the
       step rates you have (or leave blanks for benchmarks). It computes referred customers
       per 1,000 users, K implied by the funnel, and the step with the biggest lift
       potential — fix that step first.
    4. **Compare structures.** Call `referral_program__compare_rewards` with 2-5 candidate
       structures (one-sided, two-sided, tiered, credit vs cash). It ranks them by expected
       cost per customer and payback given assumed conversion rates per structure.
    5. **Write the spec:** mechanics (trigger moment, share surfaces, reward timing —
       reward on *activation/payment*, never on signup), rewards, caps, fraud rules,
       messaging (ask copy ≤ 15 words, benefit-first), tracking plan, and the 30/60/90-day
       targets from the funnel tool.
    6. **Self-check:** reward cost per referred customer < paid CAC; payback ≤ 6 months
       (SaaS) or ≤ 1 order margin (e-commerce); rewards paid only after a qualifying event;
       K stated with its assumptions.

    ## Frameworks
    - **K = invites per user × conversion per invite.** Amplification = 1/(1−K) for K < 1
      (K 0.5 → every customer is worth 2 over time). K ≥ 1 is self-sustaining; treat any
      claim of K > 0.7 for a non-social product as a modelling error until measured.
    - **LTV = ARPU × gross margin ÷ monthly churn.** Reward ceiling: total reward (both sides)
      ≤ LTV/3 and ≤ paid CAC. Reward floor: it must be worth a friend's 30 seconds
      (≥ 1 month's value or ≥ $10-20 for B2C).
    - **Two-sided beats one-sided** for conversion in most published cases (Dropbox, Uber,
      PayPal patterns) because the invitee gets a reason too; cash beats credit for the
      referrer in B2C, credit/months-free is fine for SaaS with high retention.
    - **Funnel benchmarks (rough, cross-industry):** share rate 5-15% of active users;
      invites per sharer 2-5; invite → click 20-40%; click → signup 15-35%; signup →
      qualified 30-60%. Referred users typically retain better than paid.
    - **Fraud rules:** reward on payment/activation, one reward per unique payment method
      + email + device, cap per referrer per month, hold period ≥ refund window, no
      self-referral (same card/domain), manual review above a threshold.
    - **Ask moment:** right after a success event (first value delivered, order received,
      milestone hit), never at signup.

    ## Output format
    ```
    # Referral program — <product>
    **Economics:** LTV $… · paid CAC $… · reward ceiling $… · proposed reward $… (+$… to friend)
    → cost per referred customer $… · payback … months · <fits / doesn't fit>

    ## Mechanics
    - Trigger moment: … · Surfaces: … · Reward timing: on <qualifying event>
    - Referrer gets … · Friend gets … · Caps: … · Hold: … days

    ## Targets (per 1,000 active users / month)
    | Step | Benchmark | Target | → |
    |---|---|---|---|
    Referred customers/month: … · Implied K: … · 12-month contribution: …

    ## Fraud & abuse rules
    - …

    ## Copy
    Ask (in-app): "…" · Invite message: "…" · Landing headline: "…"

    ## 90-day plan & metrics to track
    …
    ```

    ## Anti-patterns
    - Copying Dropbox's "500MB free" without checking whether your reward has value to a friend.
    - Rewarding at signup — it is an invitation to fraud and inflates the funnel.
    - Promising viral growth from K = 0.2. State amplification honestly (1.25×).
    - Rewards above LTV/3 "to get it going" — you are buying customers at a loss twice.
    - One giant "Refer a friend" button in the footer and no ask moment.
    - Ignoring the friend's side. The invitee converts on their benefit, not the referrer's.
    """,
)


def _num(v, name, lo=None, hi=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be a number (got {v!r}).") from None
    if math.isnan(x) or math.isinf(x):
        raise ToolError(f"{name} must be finite.")
    if lo is not None and x < lo or hi is not None and x > hi:
        raise ToolError(f"{name} must be between {lo} and {hi} (got {x:g}).")
    return x


def _rate(v, name):
    x = _num(v, name, 0, 100)
    return x / 100 if x > 1 else x


@AGENT.tool
def viral_coefficient(invites_per_user: float, invite_conversion_rate: float, seed_users: int = 1000, cycle_time_days: float = 14, horizon_days: int = 180, organic_new_users_per_cycle: int = 0) -> dict:
    """Compute the viral coefficient (K), amplification factor and a cycle-by-cycle growth projection.

    K = invites per user × conversion per invite. Projection starts from seed users and adds each
    generation of referred users per cycle, optionally on top of a flat organic inflow.

    Args:
        invites_per_user: Average invites sent per user (all users, not just sharers), e.g. 1.8.
        invite_conversion_rate: Share of invites that become qualified users (0.12 or 12 for 12%).
        seed_users: Starting user base for the projection.
        cycle_time_days: Days from a user joining to their invitees joining (viral cycle time).
        horizon_days: Projection horizon in days (7-1095).
        organic_new_users_per_cycle: New users per cycle from other channels, each of whom also refers.
    """
    inv = _num(invites_per_user, "invites_per_user", 0, 1000)
    conv = _rate(invite_conversion_rate, "invite_conversion_rate")
    seed = int(_num(seed_users, "seed_users", 1, 1e9))
    cycle = _num(cycle_time_days, "cycle_time_days", 0.5, 365)
    horizon = int(_num(horizon_days, "horizon_days", 7, 1095))
    organic = int(_num(organic_new_users_per_cycle, "organic_new_users_per_cycle", 0, 1e9))
    k = inv * conv
    cycles = int(horizon // cycle)
    amplification = round(1 / (1 - k), 2) if k < 1 else None
    rows = []
    total = seed
    new_gen = float(seed)
    referred_total = 0.0
    for n in range(1, cycles + 1):
        referred = new_gen * k
        referred_total += referred
        new_gen = referred + organic
        total += new_gen
        rows.append({"cycle": n, "day": round(n * cycle), "referred_this_cycle": round(referred), "organic_this_cycle": organic, "total_users": round(total)})
        if total > 1e12:
            break
    if k >= 1:
        verdict = f"K = {k:.2f} ≥ 1: self-sustaining growth on paper. This is extremely rare — verify invites and conversion are measured on *all* users, not just sharers."
    elif k >= 0.5:
        verdict = f"K = {k:.2f}: strong. Every 100 users bring ~{round(100 * (amplification - 1))} more over time ({amplification}× amplification)."
    elif k >= 0.2:
        verdict = f"K = {k:.2f}: a healthy referral channel — {amplification}× amplification on every other channel, not standalone growth."
    else:
        verdict = f"K = {k:.2f}: weak. Amplification {amplification}×. Fix the funnel (share rate / invite conversion) before scaling rewards."
    # what it would take to reach K=1 / 0.5
    return {
        "k_factor": round(k, 3),
        "invites_per_user": inv,
        "invite_conversion_rate": conv,
        "amplification": amplification,
        "cycle_time_days": cycle,
        "cycles_in_horizon": cycles,
        "seed_users": seed,
        "users_at_horizon": rows[-1]["total_users"] if rows else seed,
        "referred_users_total": round(referred_total),
        "doubling_cycles": (round(math.log(2) / math.log(k), 1) if k > 1 else None),
        "to_reach_k_0_5": {"invites_needed_at_current_conversion": round(0.5 / conv, 2) if conv else None, "conversion_needed_at_current_invites": round(0.5 / inv, 3) if inv else None},
        "projection": rows[:60],
        "verdict": verdict,
    }


@AGENT.tool
def reward_economics(arpu_monthly: float, gross_margin_pct: float, monthly_churn_pct: float, paid_cac: float, referrer_reward: float, referee_reward: float = 0, reward_conversion_rate: float = 1.0, ltv_override: float = 0) -> dict:
    """Model whether a referral reward pays back: LTV, cost per referred customer, payback months, reward ceilings vs LTV/3 and paid CAC.

    Args:
        arpu_monthly: Average revenue per customer per month (for e-commerce, use average order value × orders per month).
        gross_margin_pct: Gross margin as a percent (70) or fraction (0.7).
        monthly_churn_pct: Monthly customer churn as a percent (4) or fraction (0.04); ignored if ltv_override is set.
        paid_cac: Blended paid customer acquisition cost in currency units.
        referrer_reward: Reward paid to the referrer per qualified referral.
        referee_reward: Reward or discount given to the referred friend (0 for one-sided).
        reward_conversion_rate: Share of rewarded referrals that become paying customers (1.0 if rewards are paid only on payment; lower if paid at signup).
        ltv_override: Known customer lifetime value in currency; if > 0 it replaces the ARPU/margin/churn calculation.
    """
    arpu = _num(arpu_monthly, "arpu_monthly", 0.01)
    margin = _rate(gross_margin_pct, "gross_margin_pct")
    churn = _rate(monthly_churn_pct, "monthly_churn_pct")
    cac = _num(paid_cac, "paid_cac", 0)
    r1 = _num(referrer_reward, "referrer_reward", 0)
    r2 = _num(referee_reward, "referee_reward", 0)
    rc = _rate(reward_conversion_rate, "reward_conversion_rate")
    ltv_o = _num(ltv_override, "ltv_override", 0)
    if rc <= 0:
        raise ToolError("reward_conversion_rate must be > 0.")
    contribution = arpu * margin
    if ltv_o > 0:
        ltv = ltv_o
        lifetime_months = ltv / contribution if contribution else None
    else:
        if churn <= 0:
            raise ToolError("monthly_churn_pct must be > 0 (or pass ltv_override).")
        lifetime_months = 1 / churn
        ltv = contribution * lifetime_months
    reward_total = r1 + r2
    cost_per_customer = reward_total / rc  # rewards paid per paying customer
    payback = cost_per_customer / contribution if contribution else None
    ceiling_ltv = ltv / 3
    ceiling = min(ceiling_ltv, cac) if cac > 0 else ceiling_ltv
    ltv_to_cost = ltv / cost_per_customer if cost_per_customer else None
    checks = {
        "below_paid_cac": cost_per_customer < cac if cac > 0 else None,
        "within_ltv_third": cost_per_customer <= ceiling_ltv,
        "payback_under_6_months": payback is not None and payback <= 6,
    }
    fixes = []
    if cac > 0 and cost_per_customer >= cac:
        fixes.append(f"Cost per referred customer ${cost_per_customer:,.0f} ≥ paid CAC ${cac:,.0f} — cut total reward to ≤ ${ceiling:,.0f} or pay only on payment.")
    if cost_per_customer > ceiling_ltv:
        fixes.append(f"Reward exceeds LTV/3 (${ceiling_ltv:,.0f}).")
    if payback and payback > 6:
        fixes.append(f"Payback {payback:.1f} months — long for a referral reward; consider credit instead of cash or a tiered payout.")
    if rc < 1:
        fixes.append(f"Only {rc:.0%} of rewarded referrals pay — move the reward trigger to first payment to cut cost per customer to ${reward_total:,.0f}.")
    if reward_total < max(10.0, arpu * 0.5):
        fixes.append(f"Total reward ${reward_total:,.0f} may be too small to motivate a share (floor ≈ one month's value or $10-20).")
    works = checks["within_ltv_third"] and checks["below_paid_cac"] is not False and checks["payback_under_6_months"]
    verdict = "Economics work: " if works else "Economics do not work as designed: "
    verdict += f"${cost_per_customer:,.0f} per referred customer vs LTV ${ltv:,.0f} ({ltv_to_cost:.1f}× return), payback {payback:.1f} months." if payback is not None else f"${cost_per_customer:,.0f} per referred customer vs LTV ${ltv:,.0f}."
    return {
        "ltv": round(ltv, 2),
        "contribution_per_month": round(contribution, 2),
        "expected_lifetime_months": round(lifetime_months, 1) if lifetime_months else None,
        "reward_total": reward_total,
        "cost_per_referred_customer": round(cost_per_customer, 2),
        "payback_months": round(payback, 2) if payback is not None else None,
        "ltv_to_cost_ratio": round(ltv_to_cost, 2) if ltv_to_cost else None,
        "reward_ceiling": {"ltv_third": round(ceiling_ltv, 2), "paid_cac": cac or None, "recommended_max_total": round(ceiling, 2)},
        "suggested_split": {"referrer": round(ceiling * 0.5, 2), "referee": round(ceiling * 0.5, 2), "note": "Start ~50/50; shift toward the friend if invite→signup is the weak step."},
        "checks": checks,
        "fixes": fixes,
        "verdict": verdict,
    }


BENCH = {"share_rate": 0.08, "invites_per_sharer": 3.0, "invite_click_rate": 0.30, "click_signup_rate": 0.25, "signup_qualified_rate": 0.45}
BENCH_RANGE = {"share_rate": "5-15%", "invites_per_sharer": "2-5", "invite_click_rate": "20-40%", "click_signup_rate": "15-35%", "signup_qualified_rate": "30-60%"}


@AGENT.tool
def referral_funnel(active_users: int = 1000, share_rate: float = -1, invites_per_sharer: float = -1, invite_click_rate: float = -1, click_signup_rate: float = -1, signup_qualified_rate: float = -1) -> dict:
    """Diagnose a referral funnel step by step (share → invite → click → signup → qualified), compute the implied K, and find the step with the most upside.

    Any step left at -1 uses a cross-industry benchmark and is marked as assumed. Upside per step is the
    extra qualified customers from lifting that step to the benchmark's top of range.

    Args:
        active_users: Active users in the period (the base for the funnel).
        share_rate: Share of active users who send at least one invite (0.08 or 8 for 8%); -1 = benchmark.
        invites_per_sharer: Average invites per sharing user; -1 = benchmark.
        invite_click_rate: Share of invites that are clicked/opened; -1 = benchmark.
        click_signup_rate: Share of clicks that sign up; -1 = benchmark.
        signup_qualified_rate: Share of signups that reach the qualifying event (activation/payment); -1 = benchmark.
    """
    users = int(_num(active_users, "active_users", 1, 1e9))
    given = {"share_rate": share_rate, "invites_per_sharer": invites_per_sharer, "invite_click_rate": invite_click_rate, "click_signup_rate": click_signup_rate, "signup_qualified_rate": signup_qualified_rate}
    vals, assumed = {}, []
    for k, v in given.items():
        if v is None or float(v) < 0:
            vals[k] = BENCH[k]
            assumed.append(k)
        elif k == "invites_per_sharer":
            vals[k] = _num(v, k, 0, 1000)
        else:
            vals[k] = _rate(v, k)
    tops = {"share_rate": 0.15, "invites_per_sharer": 5.0, "invite_click_rate": 0.40, "click_signup_rate": 0.35, "signup_qualified_rate": 0.60}

    def run(v):
        sharers = users * v["share_rate"]
        invites = sharers * v["invites_per_sharer"]
        clicks = invites * v["invite_click_rate"]
        signups = clicks * v["click_signup_rate"]
        qualified = signups * v["signup_qualified_rate"]
        return {"sharers": sharers, "invites": invites, "clicks": clicks, "signups": signups, "qualified": qualified}

    base = run(vals)
    k = base["qualified"] / users
    upside = []
    for step in vals:
        if vals[step] >= tops[step]:
            continue
        alt = dict(vals)
        alt[step] = tops[step]
        gain = run(alt)["qualified"] - base["qualified"]
        upside.append({"step": step, "current": round(vals[step], 3), "benchmark_range": BENCH_RANGE[step], "lift_to_top_of_range_adds": round(gain), "assumed": step in assumed})
    upside.sort(key=lambda u: -u["lift_to_top_of_range_adds"])
    weakest = next((u for u in upside if not u["assumed"]), upside[0] if upside else None)
    return {
        "active_users": users,
        "rates": {k: round(v, 3) for k, v in vals.items()},
        "assumed_from_benchmark": assumed,
        "funnel": {k: round(v, 1) for k, v in base.items()},
        "qualified_per_1000_users": round(1000 * base["qualified"] / users, 1),
        "implied_k": round(k, 3),
        "upside_by_step": upside,
        "fix_first": weakest["step"] if weakest else None,
        "verdict": (
            f"{base['qualified']:.0f} referred customers from {users:,} users (K ≈ {k:.2f}). "
            + (f"Biggest lever: {weakest['step']} ({weakest['current']:g} vs benchmark {weakest['benchmark_range']}) — worth +{weakest['lift_to_top_of_range_adds']} customers." if weakest else "All steps at or above top-of-range benchmarks.")
            + (f" {len(assumed)} step(s) assumed from benchmarks — replace with measured data." if assumed else "")
        ),
    }


@AGENT.tool
def compare_rewards(structures: list[dict], ltv: float, paid_cac: float, contribution_per_month: float = 0) -> dict:
    """Rank candidate reward structures by cost per referred customer, LTV return and payback, given each one's expected conversion.

    Args:
        structures: 2-8 dicts like {"name": "two-sided $20/$20", "referrer_reward": 20, "referee_reward": 20, "expected_conversion": 0.12, "paid_on": "payment"|"signup"}; expected_conversion is invite→qualified, and paid_on "signup" assumes 50% of rewarded signups pay unless "signup_to_paid" is given.
        ltv: Customer lifetime value (contribution basis).
        paid_cac: Paid customer acquisition cost for comparison.
        contribution_per_month: Contribution margin per customer per month, for payback months (0 = skip).
    """
    if not structures or len(structures) < 2:
        raise ToolError("Give at least 2 structures to compare.")
    if len(structures) > 8:
        raise ToolError("Max 8 structures.")
    ltv_v = _num(ltv, "ltv", 0.01)
    cac = _num(paid_cac, "paid_cac", 0)
    contrib = _num(contribution_per_month, "contribution_per_month", 0)
    rows = []
    for i, s in enumerate(structures, 1):
        name = str(s.get("name") or f"structure {i}")
        r1 = _num(s.get("referrer_reward", 0), f"{name}: referrer_reward", 0)
        r2 = _num(s.get("referee_reward", 0), f"{name}: referee_reward", 0)
        conv = _rate(s.get("expected_conversion", 0.1), f"{name}: expected_conversion")
        paid_on = str(s.get("paid_on") or "payment").lower()
        s2p = _rate(s.get("signup_to_paid", 0.5), f"{name}: signup_to_paid") if paid_on == "signup" else 1.0
        cost = (r1 + r2) / s2p
        rows.append(
            {
                "name": name,
                "referrer_reward": r1,
                "referee_reward": r2,
                "two_sided": r2 > 0 and r1 > 0,
                "paid_on": paid_on,
                "expected_conversion": conv,
                "cost_per_customer": round(cost, 2),
                "ltv_return": round(ltv_v / cost, 2) if cost else None,
                "payback_months": round(cost / contrib, 1) if contrib else None,
                "customers_per_100_invites": round(100 * conv, 1),
                "cost_per_100_invites": round(100 * conv * cost, 2),
                "beats_paid_cac": cost < cac if cac else None,
                "within_ltv_third": cost <= ltv_v / 3,
            }
        )
    # rank by net value per 100 invites = customers × (LTV − cost); structures over LTV/3 sink to the bottom
    for r in rows:
        r["net_value_per_100_invites"] = round(100 * r["expected_conversion"] * (ltv_v - r["cost_per_customer"]), 2)
    rows.sort(key=lambda r: (not r["within_ltv_third"], -r["net_value_per_100_invites"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    best = rows[0]
    return {
        "ranked": rows,
        "recommended": best["name"],
        "summary": f"'{best['name']}' wins: ${best['cost_per_customer']:,.0f} per customer ({best['ltv_return']}× LTV" + (f", payback {best['payback_months']} mo" if best["payback_months"] else "") + f") at {best['expected_conversion']:.0%} invite→customer → net ${best['net_value_per_100_invites']:,.0f} per 100 invites. Ranked by net value per 100 invites; structures over LTV/3 sink to the bottom.",
    }
