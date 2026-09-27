"""Pricing: what a customer can buy, and what each purchase unlocks.

Every plan maps to one Stripe Price (found by ``lookup_key``, created by
``python -m hundred.admin stripe-setup``). What a subscription *unlocks* is
computed from its prices plus the choices saved in its metadata — so adding an
agent to a subscription is just "bump quantity + update metadata".

    single    $4.99/mo per agent          quantity = number of agents picked
    pick5     $14.99/mo for any 5         ($3.00/agent)
    pack      $14.99/mo per category      every agent in that category, incl. new ones
    all       $29.99/mo everything        every agent, every future agent
    founder   $14.99/mo everything        first 500 seats, price locked for life
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import registry


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    lookup_key: str
    unit_amount: int  # cents
    interval: str  # "month" | "year"
    pitch: str
    unlock: str  # "agents" | "categories" | "all"
    pick: int | None = None  # exact number of agents to choose (pick-N plans)
    per_unit: bool = False  # quantity scales with the number of choices
    seat_cap: int | None = None  # founder pricing: limited seats
    highlight: bool = False
    bullets: tuple[str, ...] = field(default_factory=tuple)

    @property
    def price(self) -> str:
        dollars = self.unit_amount / 100
        return f"${dollars:,.2f}"


PLANS: dict[str, Plan] = {
    p.code: p
    for p in [
        Plan(
            code="single",
            name="Single Agent",
            lookup_key="hundred_single_monthly",
            unit_amount=499,
            interval="month",
            unlock="agents",
            per_unit=True,
            pitch="Pick exactly the agents you need. $4.99/mo each.",
            bullets=("Any agent, $4.99/mo each", "Add or drop agents anytime", "Works in Claude, ChatGPT, Cursor & more"),
        ),
        Plan(
            code="single_annual",
            name="Single Agent (annual)",
            lookup_key="hundred_single_annual",
            unit_amount=4990,
            interval="year",
            unlock="agents",
            per_unit=True,
            pitch="Two months free on any agent.",
            bullets=("$49.90/yr per agent", "2 months free"),
        ),
        Plan(
            code="pick5",
            name="Starter Stack",
            lookup_key="hundred_pick5_monthly",
            unit_amount=1499,
            interval="month",
            unlock="agents",
            pick=5,
            pitch="Any 5 agents for the price of 3.",
            bullets=("Choose any 5 agents", "$3.00 per agent", "Swap agents monthly"),
        ),
        Plan(
            code="pack",
            name="Category Pack",
            lookup_key="hundred_pack_monthly",
            unit_amount=1499,
            interval="month",
            unlock="categories",
            per_unit=True,
            pitch="Every agent in a category — including the ones we ship next.",
            bullets=("All Sales, all Marketing, etc.", "New agents in the pack added free", "$14.99/mo per pack"),
        ),
        Plan(
            code="all",
            name="All-Access",
            lookup_key="hundred_all_monthly",
            unit_amount=2999,
            interval="month",
            unlock="all",
            highlight=True,
            pitch="Every agent we've built and every agent we ship next.",
            bullets=("All agents, all categories", "Every new agent, day one", "Priority agent requests"),
        ),
        Plan(
            code="all_annual",
            name="All-Access (annual)",
            lookup_key="hundred_all_annual",
            unit_amount=29900,
            interval="year",
            unlock="all",
            pitch="Everything, two months free.",
            bullets=("All agents", "2 months free"),
        ),
        Plan(
            code="founder",
            name="Founding Member",
            lookup_key="hundred_founder_monthly",
            unit_amount=1499,
            interval="month",
            unlock="all",
            seat_cap=500,
            pitch="All-Access at half price, locked for life. First 500 members only.",
            bullets=("Everything in All-Access", "Price locked forever", "Founder badge + roadmap vote"),
        ),
    ]
}

LOOKUP_TO_PLAN = {p.lookup_key: p for p in PLANS.values()}


class PlanError(ValueError):
    pass


def validate_selection(plan: Plan, agents: list[str], categories: list[str]) -> tuple[list[str], list[str], int]:
    """Check a checkout request. Returns (agents, categories, quantity)."""
    catalog = registry.all_agents()
    agents = sorted({a.strip() for a in agents if a.strip()})
    categories = sorted({c.strip() for c in categories if c.strip()})
    if plan.unlock == "agents":
        unknown = [a for a in agents if a not in catalog]
        if unknown:
            raise PlanError(f"Unknown agents: {', '.join(unknown)}")
        if not agents:
            raise PlanError("Pick at least one agent.")
        if plan.pick is not None and len(agents) != plan.pick:
            raise PlanError(f"{plan.name} needs exactly {plan.pick} agents (you picked {len(agents)}).")
        return agents, [], (len(agents) if plan.per_unit else 1)
    if plan.unlock == "categories":
        cats = registry.by_category()
        unknown = [c for c in categories if c not in cats]
        if unknown or not categories:
            raise PlanError("Pick at least one valid category." if not unknown else f"Unknown: {unknown}")
        return [], categories, len(categories)
    return [], [], 1


@dataclass
class Entitlement:
    """What a license can use right now."""

    all_access: bool = False
    agents: set[str] = field(default_factory=set)
    categories: set[str] = field(default_factory=set)

    def allows(self, slug: str) -> bool:
        agent = registry.get(slug)
        if agent is None:
            return False
        return agent.free or self.all_access or slug in self.agents or agent.category in self.categories

    def slugs(self) -> list[str]:
        return [s for s in registry.all_agents() if self.allows(s)]


def entitlement_from_items(lookup_keys: list[str], agents: list[str], categories: list[str]) -> Entitlement:
    """Compute what a Stripe subscription unlocks from its prices + metadata."""
    ent = Entitlement()
    for key in lookup_keys:
        plan = LOOKUP_TO_PLAN.get(key)
        if plan is None:
            continue
        if plan.unlock == "all":
            ent.all_access = True
        elif plan.unlock == "categories":
            ent.categories.update(categories)
        else:
            ent.agents.update(agents)
    return ent
