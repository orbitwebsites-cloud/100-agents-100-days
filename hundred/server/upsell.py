"""The post-purchase upgrade offer: hit every cheaper purchase with All-Access at a price
that's hard to refuse.

Shown once, right after checkout (welcome page + welcome email), valid 48 hours,
one click, charged to the card they just used, starting when their trial ends.

Offer price, per buyer:
    offer = max(half of All-Access list, what they pay now + $5)
            capped at what they pay now + $15, and never above All-Access list
            rounded up to a .99 ending

    1 agent   ($4.99)  → all 100 for $14.99/mo, locked for life   (list $29.99)
    3 agents  ($14.97) → all 100 for $19.99/mo
    1 pack    ($14.99) → all 100 for $19.99/mo
    6 agents  ($29.94) → all 100 for $29.99/mo  (same money, 100 agents)

Why this shape: the +$5 floor means every acceptance raises revenue; the 50%-off
ceiling makes the value gap enormous (a $4.99 buyer gets 20× the agents for 3× the
price); the +$15 cap keeps the jump small enough to say yes to on impulse.

Consent: the price, "every month, cancel anytime" and the card it's charged to are
stated next to the button (ROSCA / FTC negative-option rules require clear
disclosure + express consent for recurring charges). The offer is great, the terms
are never hidden.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from dataclasses import dataclass
from urllib.parse import urlencode

from .. import plans
from .settings import settings
from .store import License

OFFER_TTL = 48 * 3600
UPSELLABLE = {"single", "pick5", "pack"}  # monthly plans below All-Access


@dataclass(frozen=True)
class Offer:
    subscription_id: str
    current_cents: int
    offer_cents: int
    list_cents: int
    expires_at: int

    @property
    def discount_cents(self) -> int:
        return self.list_cents - self.offer_cents

    @property
    def extra_cents(self) -> int:
        return self.offer_cents - self.current_cents

    @property
    def percent_off(self) -> int:
        return round(100 * self.discount_cents / self.list_cents)


def _charm(cents: int) -> int:
    """Round up to the next price ending in .99 (1450 → 1499, 1999 → 1999)."""
    return max(99, math.ceil((cents - 99) / 100) * 100 + 99)


def current_monthly_cents(lic: License) -> int | None:
    plan = plans.PLANS.get(lic.plan)
    if plan is None or plan.code not in UPSELLABLE:
        return None
    if plan.code == "single":
        return plan.unit_amount * max(1, len(lic.agents))
    if plan.code == "pack":
        return plan.unit_amount * max(1, len(lic.categories))
    return plan.unit_amount


def offer_for(lic: License | None, now: int | None = None) -> Offer | None:
    """The All-Access offer for this license, or None if it shouldn't get one."""
    if lic is None or not lic.active or lic.all_access or not lic.subscription_id or lic.source != "stripe":
        return None
    paying = current_monthly_cents(lic)
    if paying is None:
        return None
    list_cents = plans.PLANS["all"].unit_amount
    target = max(list_cents // 2, paying + 500)
    target = min(target, paying + 1500)
    offer = min(_charm(target), list_cents)
    offer = max(offer, min(paying, list_cents))  # never below what they already pay
    return Offer(lic.subscription_id, paying, offer, list_cents, (now or int(time.time())) + OFFER_TTL)


# ── signed one-click tokens (no login needed; can't be forged or re-priced) ──
def _secret() -> bytes:
    # APP_SECRET if set; otherwise derived from the Stripe key so production is never
    # left on a guessable default. (Dev with neither: a fixed local-only value.)
    if settings.app_secret:
        return settings.app_secret.encode()
    return hashlib.sha256(b"hundred-upsell:" + (settings.stripe_secret_key or "dev-only").encode()).digest()


def sign(sub_id: str, offer_cents: int, expires_at: int) -> str:
    msg = f"{sub_id}:{offer_cents}:{expires_at}".encode()
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def verify(sub_id: str, offer_cents: int, expires_at: int, sig: str, now: int | None = None) -> bool:
    if (now or int(time.time())) > expires_at:
        return False
    return hmac.compare_digest(sign(sub_id, offer_cents, expires_at), sig or "")


def token_fields(offer: Offer) -> dict[str, str]:
    return {
        "sub": offer.subscription_id,
        "offer": str(offer.offer_cents),
        "exp": str(offer.expires_at),
        "sig": sign(offer.subscription_id, offer.offer_cents, offer.expires_at),
    }


def offer_url(offer: Offer) -> str:
    return f"{settings.public_url}/offer?{urlencode(token_fields(offer))}"


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"
