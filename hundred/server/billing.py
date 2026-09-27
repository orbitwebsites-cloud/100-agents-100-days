"""Stripe billing: checkout, webhooks, and the rule that access follows payment.

Access rule (what the customer was promised):
  * trialing / active            → agents on
  * invoice.payment_failed       → agents OFF immediately (payment_failed flag)
  * invoice.paid                 → flag cleared, agents back ON the moment the card works
  * subscription canceled/unpaid → agents off

Stripe is the source of truth. Webhooks keep our copy fresh; ``reconcile()``
(``python -m hundred.admin reconcile``, run on a cron) repairs anything a missed
webhook left stale.
"""

from __future__ import annotations

import logging
from typing import Any

import stripe

from .. import plans
from . import emailer
from .settings import settings
from .store import Store

log = logging.getLogger("hundred.billing")

META_CHUNK = 450  # Stripe metadata values max out at 500 chars


class BillingError(Exception):
    pass


def client() -> stripe.StripeClient:
    if not settings.stripe_secret_key:
        raise BillingError("Stripe isn't configured (set STRIPE_SECRET_KEY).")
    return stripe.StripeClient(settings.stripe_secret_key)


def as_dict(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return obj


# ── metadata packing (lists can outgrow one 500-char value) ─────────
def pack_list(name: str, values: list[str]) -> dict[str, str]:
    joined = ",".join(values)
    chunks = [joined[i : i + META_CHUNK] for i in range(0, len(joined), META_CHUNK)] or [""]
    return {f"{name}_{i}": c for i, c in enumerate(chunks)}


def unpack_list(name: str, metadata: dict[str, str]) -> list[str]:
    parts = [metadata[k] for k in sorted((k for k in metadata if k.startswith(f"{name}_")), key=lambda k: int(k.rsplit("_", 1)[1]))]
    joined = "".join(parts) or metadata.get(name, "")
    return [v for v in joined.split(",") if v]


# ── prices ──────────────────────────────────────────────────
_price_cache: dict[str, str] = {}


def price_id(lookup_key: str) -> str:
    if lookup_key not in _price_cache:
        prices = client().v1.prices.list(params={"lookup_keys": [lookup_key], "active": True, "limit": 1})
        if not prices.data:
            raise BillingError(f"No Stripe price with lookup_key {lookup_key!r}. Run: python -m hundred.admin stripe-setup")
        _price_cache[lookup_key] = prices.data[0].id
    return _price_cache[lookup_key]


def ensure_prices() -> list[str]:
    """Create any missing product/price for every plan (idempotent via lookup_key)."""
    c = client()
    report = []
    for plan in plans.PLANS.values():
        existing = c.v1.prices.list(params={"lookup_keys": [plan.lookup_key], "limit": 1})
        if existing.data:
            report.append(f"exists  {plan.lookup_key} → {existing.data[0].id}")
            continue
        product = c.v1.products.create(params={"name": f"{settings.brand} — {plan.name}", "description": plan.pitch,
                                               "metadata": {"plan": plan.code}})
        price = c.v1.prices.create(params={
            "product": product.id,
            "currency": "usd",
            "unit_amount": plan.unit_amount,
            "recurring": {"interval": plan.interval},
            "lookup_key": plan.lookup_key,
            "metadata": {"plan": plan.code},
        })
        report.append(f"created {plan.lookup_key} → {price.id} ({plan.price}/{plan.interval})")
    return report


# ── checkout ────────────────────────────────────────────────
def create_checkout(store: Store, plan_code: str, agents: list[str], categories: list[str], email: str = "",
                    referral: str = "") -> str:
    plan = plans.PLANS.get(plan_code)
    if plan is None:
        raise plans.PlanError(f"Unknown plan {plan_code!r}")
    agents, categories, quantity = plans.validate_selection(plan, agents, categories)
    if plan.seat_cap is not None and store.count_active(plan.code) >= plan.seat_cap:
        raise plans.PlanError(f"{plan.name} is sold out — all {plan.seat_cap} seats are taken.")
    metadata = {"plan": plan.code, **pack_list("agents", agents), **pack_list("categories", categories)}
    if referral:
        metadata["referral"] = referral[:100]
    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id(plan.lookup_key), "quantity": quantity}],
        "subscription_data": {"metadata": metadata},
        "metadata": metadata,
        "allow_promotion_codes": True,
        "success_url": f"{settings.public_url}/welcome?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.public_url}/pricing?canceled=1",
    }
    if settings.trial_days > 0:
        params["subscription_data"]["trial_period_days"] = settings.trial_days
    if referral:
        params["client_reference_id"] = referral[:200]
    if email:
        params["customer_email"] = email
    session = client().v1.checkout.sessions.create(params=params)
    return session.url


def portal_url(customer_id: str) -> str:
    session = client().v1.billing_portal.sessions.create(
        params={"customer": customer_id, "return_url": f"{settings.public_url}/account"}
    )
    return session.url


# ── subscription → license ──────────────────────────────────
def _period_end(sub: dict) -> int | None:
    if sub.get("current_period_end"):
        return sub["current_period_end"]
    ends = [i.get("current_period_end") for i in (sub.get("items") or {}).get("data", []) if i.get("current_period_end")]
    return max(ends) if ends else None


def subscription_entitlement(sub: dict) -> tuple[str, plans.Entitlement, list[str], list[str]]:
    items = (sub.get("items") or {}).get("data", [])
    lookup_keys = [((i.get("price") or {}).get("lookup_key") or "") for i in items]
    meta = sub.get("metadata") or {}
    agents = unpack_list("agents", meta)
    categories = unpack_list("categories", meta)
    ent = plans.entitlement_from_items(lookup_keys, agents, categories)
    plan_code = meta.get("plan") or next(
        (plans.LOOKUP_TO_PLAN[k].code for k in lookup_keys if k in plans.LOOKUP_TO_PLAN), "unknown"
    )
    return plan_code, ent, agents, categories


def sync_subscription(store: Store, sub: Any, email: str = "", session_id: str = "") -> tuple[Any, str | None]:
    """Create or update the license for a Stripe subscription. Returns (license, new_plaintext_key|None)."""
    sub = as_dict(sub)
    plan_code, ent, _, _ = subscription_entitlement(sub)
    status = sub.get("status", "incomplete")
    fields = dict(
        status=status,
        plan=plan_code,
        all_access=ent.all_access,
        agents=sorted(ent.agents),
        categories=sorted(ent.categories),
        period_end=_period_end(sub),
        customer_id=sub.get("customer") if isinstance(sub.get("customer"), str) else (sub.get("customer") or {}).get("id"),
    )
    existing = store.by_subscription(sub["id"])
    if existing is not None:
        return store.update_subscription(sub["id"], **fields), None
    if not email:
        email = _customer_email(fields["customer_id"])
    key, lic = store.create_license(email=email or "unknown@unknown", source="stripe", subscription_id=sub["id"],
                                    live=settings.stripe_secret_key.startswith("sk_live"), **fields)
    if session_id:
        store.put_reveal(session_id, key)
    plan = plans.PLANS.get(plan_code)
    emailer.send_welcome(lic.email, key, plan.name if plan else plan_code)
    return lic, key


def _customer_email(customer_id: str | None) -> str:
    if not customer_id or not settings.stripe_live:
        return ""
    try:
        return client().v1.customers.retrieve(customer_id).email or ""
    except stripe.StripeError:
        return ""


def _fetch_subscription(sub_id: str) -> dict:
    return as_dict(client().v1.subscriptions.retrieve(sub_id, params={"expand": ["items.data.price"]}))


def _invoice_subscription_id(invoice: dict) -> str | None:
    sub = invoice.get("subscription")
    if isinstance(sub, dict):
        return sub.get("id")
    if sub:
        return sub
    details = ((invoice.get("parent") or {}).get("subscription_details") or {})
    sub = details.get("subscription")
    return sub.get("id") if isinstance(sub, dict) else sub


# ── webhooks ────────────────────────────────────────────────
def verify_event(payload: bytes, signature: str) -> dict:
    if not settings.stripe_webhook_secret:
        raise BillingError("STRIPE_WEBHOOK_SECRET is not set")
    event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    return as_dict(event)


def handle_event(store: Store, event: dict, fetch=None) -> str:
    """Apply one Stripe event. ``fetch(sub_id)`` retrieves a subscription (injectable for tests)."""
    fetch = fetch or _fetch_subscription
    etype, obj = event["type"], event["data"]["object"]
    if store.seen_event(event["id"], etype):
        return "duplicate"
    try:
        return _apply(store, etype, obj, fetch)
    except Exception:
        store.forget_event(event["id"])  # let Stripe's retry reprocess it
        raise


def _apply(store: Store, etype: str, obj: dict, fetch) -> str:
    if etype == "checkout.session.completed":
        if obj.get("mode") != "subscription" or not obj.get("subscription"):
            return "ignored"
        sub_id = obj["subscription"] if isinstance(obj["subscription"], str) else obj["subscription"]["id"]
        email = (obj.get("customer_details") or {}).get("email") or obj.get("customer_email") or ""
        _, key = sync_subscription(store, fetch(sub_id), email=email, session_id=obj["id"])
        return "provisioned" if key else "synced"

    if etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.resumed",
                 "customer.subscription.paused"):
        if etype == "customer.subscription.created" and store.by_subscription(obj["id"]) is None:
            # Checkout provisions (it has the session id for the key reveal). Only
            # provision here for subscriptions created outside Checkout.
            if (obj.get("metadata") or {}).get("plan"):
                return "deferred-to-checkout"
        sync_subscription(store, fetch(obj["id"]))
        return "synced"

    if etype == "customer.subscription.deleted":
        lic = store.update_subscription(obj["id"], status="canceled")
        if lic:
            emailer.send_canceled(lic.email)
        return "canceled"

    if etype == "invoice.payment_failed":
        sub_id = _invoice_subscription_id(obj)
        if not sub_id:
            return "ignored"
        lic = store.by_subscription(sub_id)
        if lic is None:
            return "ignored"
        was_active = lic.active
        store.update_subscription(sub_id, payment_failed=True)
        if was_active:
            emailer.send_payment_failed(lic.email)
        return "access-cut"

    if etype in ("invoice.paid", "invoice.payment_succeeded"):
        sub_id = _invoice_subscription_id(obj)
        if not sub_id:
            return "ignored"
        lic = store.by_subscription(sub_id)
        if lic is None:
            return "ignored"  # first invoice: checkout.session.completed provisions
        was_active = lic.active
        store.update_subscription(sub_id, payment_failed=False)
        lic, _ = sync_subscription(store, fetch(sub_id))
        if lic and lic.active and not was_active:
            emailer.send_restored(lic.email)
        return "access-restored"

    return "ignored"


def reconcile(store: Store) -> list[str]:
    """Re-pull every Stripe-backed license from Stripe and fix drift."""
    out = []
    for lic in store.all_licenses():
        if lic.source != "stripe" or not lic.subscription_id:
            continue
        try:
            sub = _fetch_subscription(lic.subscription_id)
        except stripe.InvalidRequestError:
            store.update_subscription(lic.subscription_id, status="canceled")
            out.append(f"{lic.key_prefix}… missing in Stripe → canceled")
            continue
        before = lic.status
        new, _ = sync_subscription(store, sub)
        if new and new.status != before:
            out.append(f"{lic.key_prefix}… {before} → {new.status}")
    return out
