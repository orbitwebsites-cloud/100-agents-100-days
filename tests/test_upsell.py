"""Post-purchase All-Access offer: always raises revenue, always a huge discount, never forgeable."""

from __future__ import annotations

import pytest

from hundred import registry
from hundred.server import billing, upsell, web
from hundred.server.store import Store

PAID = [a.slug for a in registry.all_agents().values() if not a.free]
CATS = sorted({a.category for a in registry.all_agents().values()})


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "u.db"))


def lic(store, plan, agents=(), categories=(), status="trialing", sub="sub_u", all_access=False, source="stripe"):
    _, license_ = store.create_license(email="b@x.co", plan=plan, status=status, source=source, agents=list(agents),
                                       categories=list(categories), subscription_id=sub, all_access=all_access)
    return license_


@pytest.mark.parametrize(
    "plan,n_agents,n_cats,paying,offer",
    [
        ("single", 1, 0, 499, 1499),  # $4.99 → all 100 for $14.99 (50% off list)
        ("single", 2, 0, 998, 1499),
        ("single", 3, 0, 1497, 1999),  # floor: +$5
        ("single", 4, 0, 1996, 2499),
        ("single", 6, 0, 2994, 2999),  # already ~list: same money, 100 agents
        ("pick5", 5, 0, 1499, 1999),
        ("pack", 0, 1, 1499, 1999),
        ("pack", 0, 2, 2998, 2999),
    ],
)
def test_offer_prices(store, plan, n_agents, n_cats, paying, offer):
    o = upsell.offer_for(lic(store, plan, PAID[:n_agents], CATS[:n_cats]))
    assert o.current_cents == paying
    assert o.offer_cents == offer
    assert o.offer_cents >= o.current_cents, "never asks for less than they already pay"
    assert o.offer_cents <= o.list_cents
    assert o.offer_cents <= o.current_cents + 1500, "jump stays impulse-sized"
    assert str(o.offer_cents).endswith("99")


def test_every_acceptance_raises_revenue_until_list(store):
    for n in range(1, 6):
        o = upsell.offer_for(lic(store, "single", PAID[:n], sub=f"sub_{n}"))
        assert o.offer_cents - o.current_cents >= min(500, o.list_cents - o.current_cents)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(plan="all", all_access=True),
        dict(plan="founder", all_access=True),
        dict(plan="single", agents=["x"], status="past_due"),
        dict(plan="single_annual", agents=["x"]),
        dict(plan="single", agents=["x"], source="comp"),
    ],
)
def test_no_offer_when_it_makes_no_sense(store, kwargs):
    kwargs.setdefault("agents", PAID[:1])
    assert upsell.offer_for(lic(store, **kwargs)) is None


def test_tokens_cannot_be_forged_repriced_or_reused_late():
    exp = 2_000_000_000
    sig = upsell.sign("sub_1", 1499, exp)
    assert upsell.verify("sub_1", 1499, exp, sig, now=exp - 10)
    assert not upsell.verify("sub_1", 99, exp, sig, now=exp - 10), "price tampering"
    assert not upsell.verify("sub_2", 1499, exp, sig, now=exp - 10), "someone else's subscription"
    assert not upsell.verify("sub_1", 1499, exp, sig, now=exp + 1), "expired"
    assert not upsell.verify("sub_1", 1499, exp, "", now=exp - 10)


class FakeStripe:
    """Records the calls apply_upsell makes."""

    def __init__(self):
        self.updates, self.coupons = [], []
        outer = self

        class Coupons:
            def retrieve(self, cid):
                import stripe

                raise stripe.InvalidRequestError("no such coupon", "id")

            def create(self, params):
                outer.coupons.append(params)

        class Subs:
            def update(self, sub_id, params):
                outer.updates.append((sub_id, params))

        self.v1 = type("V1", (), {"coupons": Coupons(), "subscriptions": Subs()})()


def test_apply_upsell_swaps_plan_with_forever_coupon(store, monkeypatch):
    lic(store, "single", PAID[:1], sub="sub_up")
    monkeypatch.setattr(billing, "price_id", lambda key: f"price_{key}")
    before = {"id": "sub_up", "status": "trialing", "customer": "cus_1", "metadata": {"plan": "single"},
              "items": {"data": [{"id": "si_old", "price": {"lookup_key": "hundred_single_monthly"}}]}}
    after = {**before, "metadata": {"plan": "all"},
             "items": {"data": [{"id": "si_new", "price": {"lookup_key": "hundred_all_monthly"}}]}}
    calls = iter([before, after])
    fake = FakeStripe()

    new = billing.apply_upsell(store, "sub_up", 1499, stripe_client=fake, fetch=lambda _id: next(calls))

    sub_id, params = fake.updates[0]
    assert sub_id == "sub_up"
    assert {"id": "si_old", "deleted": True} in params["items"]
    assert {"price": "price_hundred_all_monthly", "quantity": 1} in params["items"]
    assert params["proration_behavior"] == "none", "still in trial: nothing charged today"
    assert fake.coupons[0]["amount_off"] == 1500 and fake.coupons[0]["duration"] == "forever"
    assert new.all_access and new.active


def test_apply_upsell_refuses_stale_price(store):
    lic(store, "single", PAID[:1], sub="sub_stale")
    with pytest.raises(billing.BillingError):
        billing.apply_upsell(store, "sub_stale", 999, stripe_client=FakeStripe(), fetch=lambda _id: {})


def test_offer_card_states_price_terms_and_consent(store):
    o = upsell.offer_for(lic(store, "single", PAID[:1]))
    html = web.welcome_page("hnd_live_x", o, upsell.token_fields(o))
    for must in ("$14.99", "$29.99", "every month", "Cancel anytime", "free trial ends", "No thanks",
                 "Replaces your current plan"):
        assert must in html


def test_http_offer_rejects_forged_links(live_server):
    import httpx

    base, _ = live_server
    assert httpx.get(f"{base}/offer?sub=sub_x&offer=99&exp=9999999999&sig=bad").status_code == 410
    r = httpx.post(f"{base}/upsell/accept", data={"sub": "sub_x", "offer": "99", "exp": "9999999999", "sig": "bad"})
    assert r.status_code == 400
