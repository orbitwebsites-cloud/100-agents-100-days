"""Transactional email: license keys, sign-in codes, dunning, access restored.

Live through Brevo when BREVO_API_KEY is set (Resend still works via
RESEND_API_KEY); otherwise dry-run (prints the email) — same pattern as the
Meeting Ops connectors.
"""

from __future__ import annotations

import logging
from email.utils import parseaddr

import requests

from .settings import settings

log = logging.getLogger("hundred.email")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
RESEND_URL = "https://api.resend.com/emails"


def provider() -> str:
    if settings.brevo_api_key:
        return "brevo"
    if settings.resend_api_key:
        return "resend"
    return "dry-run"


def _sender() -> dict:
    name, address = parseaddr(settings.email_from)
    return {"name": name or settings.brand, "email": address or settings.email_from}


def _post(to: str, subject: str, text: str) -> requests.Response:
    if provider() == "brevo":
        return requests.post(
            BREVO_URL,
            headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
            json={"sender": _sender(), "to": [{"email": to}], "subject": subject, "textContent": text,
                  "replyTo": {"email": settings.support_email}},
            timeout=15,
        )
    return requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={"from": settings.email_from, "to": [to], "subject": subject, "text": text,
              "reply_to": settings.support_email},
        timeout=15,
    )


def send(to: str, subject: str, text: str) -> str:
    if provider() == "dry-run":
        log.warning("[email · DRY-RUN] to=%s subject=%r\n%s", to, subject, text)
        return "email:dry-run"
    try:
        resp = _post(to, subject, text)
    except requests.RequestException as exc:
        log.error("email send failed (%s): %s", provider(), exc)
        return "email:failed"
    if resp.status_code >= 300:
        log.error("email send failed %s %s: %s", provider(), resp.status_code, resp.text[:300])
        return "email:failed"
    body = resp.json() if resp.content else {}
    return body.get("messageId") or body.get("id") or "email:sent"


def connect_instructions(key: str) -> str:
    url = f"{settings.mcp_url}?key={key}"
    return f"""Your MCP link (keep it private — it's your key):

  {url}

Add it once to the AI you already use:

  • Claude (claude.ai / Desktop): Settings → Connectors → Add custom connector → paste the link.
  • ChatGPT: Settings → Apps & Connectors → Advanced → Developer mode → Create → paste the link.
  • Claude Code:  claude mcp add --transport http hundred "{url}"
  • Cursor / Windsurf / VS Code: add to your MCP config:
      {{"mcpServers": {{"hundred": {{"url": "{url}"}}}}}}

Then just ask for what you need ("write a cold email sequence for…") — your AI
will pick the right agent. Full setup guide: {settings.public_url}/setup
"""


def send_welcome(to: str, key: str, plan_name: str, offer_line: str = "") -> str:
    return send(
        to,
        f"Your {settings.brand} agents are ready",
        f"Welcome to {settings.brand} — {plan_name}.\n\n{connect_instructions(key)}\n"
        + (f"{offer_line}\n\n" if offer_line else "")
        + f"Manage billing anytime: {settings.public_url}/account\n",
    )


def send_payment_failed(to: str) -> str:
    return send(
        to,
        f"Action needed: your card was declined — {settings.brand} agents paused",
        "Your latest payment didn't go through, so your agents are paused.\n\n"
        f"Update your card here and access comes back instantly: {settings.public_url}/account\n\n"
        "Nothing is lost — your key and your agents stay exactly as they were.\n",
    )


def send_restored(to: str) -> str:
    return send(
        to,
        f"You're back — {settings.brand} agents restored",
        "Payment received. Your agents are live again, same link as before.\n",
    )


def send_canceled(to: str) -> str:
    return send(
        to,
        f"Your {settings.brand} subscription has ended",
        "Your subscription ended and your agents are now off. The free agents keep working.\n\n"
        f"Come back anytime: {settings.public_url}/pricing\n",
    )


def send_sign_in_code(to: str, code: str, client_name: str) -> str:
    return send(
        to,
        f"{code} is your {settings.brand} sign-in code",
        f"Enter {code} to connect {settings.brand} to {client_name}. It expires in 10 minutes.\n\n"
        "If you didn't try to sign in, ignore this email.\n",
    )
