"""The whole business in one ASGI app.

    /                    storefront (landing + pricing + catalog)
    /agents/<slug>       one SEO landing page per agent
    /checkout            → Stripe Checkout (subscription, 7-day trial)
    /welcome             post-checkout: one-time key reveal + setup
    /account             update card / cancel (Stripe portal), recover a lost key
    /setup               connect guide for Claude, ChatGPT, Cursor, VS Code, Claude Code…
    /stripe/webhook      Stripe events → licenses (access follows payment)
    /mcp                 the MCP endpoint (key via ?key=, Bearer header, or /k/<key>/mcp)
    /catalog.json        machine-readable catalog

Run:  uvicorn hundred.server.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route

from .. import plans, registry
from . import billing, emailer, web
from .mcp_server import build_server
from .settings import settings
from .store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hundred.app")

store = Store(settings.database_path)


async def home(request: Request) -> Response:
    founder_left = max(0, (plans.PLANS["founder"].seat_cap or 0) - store.count_active("founder"))
    return HTMLResponse(web.home_page(founder_left, canceled=bool(request.query_params.get("canceled"))))


async def agent_page(request: Request) -> Response:
    agent = registry.get(request.path_params["slug"])
    if agent is None:
        return HTMLResponse(web.message_page("Not found", "That agent doesn't exist (yet)."), status_code=404)
    return HTMLResponse(web.agent_page(agent))


async def catalog_json(request: Request) -> Response:
    return JSONResponse({
        "agents": [a.summary() for a in registry.all_agents().values()],
        "plans": [{"code": p.code, "name": p.name, "price_cents": p.unit_amount, "interval": p.interval,
                   "pitch": p.pitch} for p in plans.PLANS.values()],
        "mcp_url": settings.mcp_url,
    })


async def checkout(request: Request) -> Response:
    if request.method == "POST":
        form = await request.form()
        plan_code = str(form.get("plan", ""))
        agents = [str(v) for v in form.getlist("agents")]
        categories = [str(v) for v in form.getlist("categories")]
        email = str(form.get("email", ""))
    else:
        q = request.query_params
        plan_code = q.get("plan", "")
        agents = [a for a in q.get("agents", "").split(",") if a]
        categories = [c for c in q.get("categories", "").split(",") if c]
        email = q.get("email", "")
    referral = request.cookies.get("ref", "") or request.query_params.get("ref", "")
    try:
        url = billing.create_checkout(store, plan_code, agents, categories, email=email, referral=referral)
    except plans.PlanError as e:
        return HTMLResponse(web.message_page("Almost", str(e), back="/#pricing"), status_code=400)
    except billing.BillingError as e:
        log.error("checkout unavailable: %s", e)
        return HTMLResponse(web.message_page("Checkout is offline", "Payments aren't configured yet. Try again soon."),
                            status_code=503)
    return RedirectResponse(url, status_code=303)


async def welcome(request: Request) -> Response:
    session_id = request.query_params.get("session_id", "")
    if not session_id:
        return RedirectResponse("/", status_code=303)
    key = store.take_reveal(session_id)
    if key is None and settings.stripe_live:
        # Webhook may not have landed yet: provision from the session directly (idempotent).
        try:
            session = billing.as_dict(billing.client().v1.checkout.sessions.retrieve(session_id))
            sub_id = session.get("subscription")
            if sub_id and session.get("status") == "complete":
                email = (session.get("customer_details") or {}).get("email", "")
                if store.by_subscription(sub_id) is None:
                    billing.sync_subscription(store, billing._fetch_subscription(sub_id), email=email,
                                              session_id=session_id)
                    key = store.take_reveal(session_id)
        except Exception:
            log.exception("welcome: could not provision from session")
    return HTMLResponse(web.welcome_page(key))


async def account(request: Request) -> Response:
    if request.method == "GET":
        return HTMLResponse(web.account_page())
    form = await request.form()
    action = form.get("action")
    if action == "portal":
        lic = store.by_key(str(form.get("key", "")))
        if lic is None or not lic.customer_id:
            return HTMLResponse(web.account_page(error="That key isn't linked to a paid subscription."), status_code=400)
        return RedirectResponse(billing.portal_url(lic.customer_id), status_code=303)
    if action == "recover":
        email = str(form.get("email", "")).strip().lower()
        for lic in store.by_email(email):
            if lic.subscription_id:
                new_key = store.rotate_key_for_subscription(lic.subscription_id)
                if new_key:
                    emailer.send(email, f"Your new {settings.brand} key",
                                 "Here's a fresh key (the old one no longer works).\n\n"
                                 + emailer.connect_instructions(new_key))
        # Same answer either way: don't reveal which emails are customers.
        return HTMLResponse(web.account_page(notice="If that email has a subscription, a new key is on its way."))
    return RedirectResponse("/account", status_code=303)


async def setup_page(request: Request) -> Response:
    return HTMLResponse(web.setup_page())


async def stripe_webhook(request: Request) -> Response:
    payload = await request.body()
    try:
        event = billing.verify_event(payload, request.headers.get("stripe-signature", ""))
    except Exception as e:
        log.warning("webhook rejected: %s", e)
        return PlainTextResponse("bad signature", status_code=400)
    try:
        result = billing.handle_event(store, event)
    except Exception:
        log.exception("webhook %s failed", event.get("type"))
        return PlainTextResponse("error", status_code=500)  # Stripe retries
    log.info("stripe %s %s → %s", event.get("type"), event.get("id"), result)
    return JSONResponse({"ok": True, "result": result})


async def healthz(request: Request) -> Response:
    return JSONResponse({"ok": True, "agents": len(registry.all_agents())})


async def ref(request: Request) -> Response:
    """Affiliate/referral links: /r/<code> sets a 60-day cookie then lands on the home page."""
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie("ref", request.path_params["code"][:100], max_age=60 * 86400, samesite="lax")
    return resp


ROUTES = [
    Route("/", home),
    Route("/pricing", home),
    Route("/agents/{slug}", agent_page),
    Route("/catalog.json", catalog_json),
    Route("/checkout", checkout, methods=["GET", "POST"]),
    Route("/welcome", welcome),
    Route("/account", account, methods=["GET", "POST"]),
    Route("/setup", setup_page),
    Route("/stripe/webhook", stripe_webhook, methods=["POST"]),
    Route("/healthz", healthz),
    Route("/r/{code}", ref),
]

mcp_server = build_server(store)
_inner = mcp_server.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    custom_starlette_routes=ROUTES,
)


async def app(scope, receive, send):
    """Accept /k/<key>/mcp for clients that drop query strings or can't set headers."""
    if scope["type"] == "http" and scope["path"].startswith("/k/"):
        parts = scope["path"].split("/", 3)  # ['', 'k', '<key>', 'mcp...']
        if len(parts) == 4 and parts[3].startswith("mcp"):
            scope = dict(scope, path="/" + parts[3], raw_path=("/" + parts[3]).encode(), hundred_key=parts[2])
    await _inner(scope, receive, send)
