"""The agent's tools.

Same idea as Agent #1: the model doesn't describe the audit, the note, the
deal, and the pitch — it *takes* those actions by calling these functions.

One difference worth noting. `audit_website` is the tool that makes this agent
impossible to replicate with a chat prompt: it goes out over the network and
measures a stranger's website. Everything downstream is grounded in what it
brings back, and the tools deliberately re-use the stored audit rather than
letting the model retype numbers it might drift on.
"""

import json

from anthropic import beta_tool

from . import audit as audit_engine
from .connectors import gmail, hubspot, onepager

# ── Active-lead context ──────────────────────────────────────
# Set by the runner before each lead. Tools read the contact id and the audit
# from here rather than trusting the model to carry ids around correctly.
_LEAD: dict = {}
_AUDIT: dict = {}


def set_lead(lead: dict) -> None:
    global _LEAD, _AUDIT
    _LEAD = dict(lead)
    _AUDIT = {}


def current_audit() -> dict:
    return dict(_AUDIT)


# ── Tools ────────────────────────────────────────────────────


@beta_tool
def audit_website(url: str) -> str:
    """Run a real, measured audit of the prospect's website.

    This actually fetches the site: load time, page weight, SSL certificate,
    mobile viewport, SEO tags, analytics, contact paths, and broken links.
    Call this first, once, and base everything else on what it returns.

    Args:
        url: The prospect's website, e.g. "https://acme.com".
    """
    global _AUDIT
    _AUDIT = audit_engine.audit_site(url)
    print(audit_engine.format_report(_AUDIT))
    return json.dumps(_AUDIT, indent=2)


@beta_tool
def log_audit_to_crm(headline: str, findings_markdown: str) -> str:
    """Write the audit findings onto the lead's CRM record as a note.

    Call this exactly once, after the audit.

    Args:
        headline: One line with the score and the headline problem, e.g.
            "Site audit: 42/100 — 4.6s load, no mobile layout".
        findings_markdown: The issues worth their attention, worst first, as a
            short bulleted list. Consequences in plain language.
    """
    return hubspot.log_audit(_LEAD.get("id", "unknown"), headline, findings_markdown)


@beta_tool
def create_onepager(summary: str) -> str:
    """Render the audit as a branded one-pager you can send to the prospect.

    Call this exactly once. Score and findings come from the audit
    automatically — you only write the summary paragraph.

    Args:
        summary: Two or three sentences on the state of the site and what
            fixing it would change for their business.
    """
    return onepager.create_onepager(
        _LEAD.get("company", "") or _LEAD.get("name", ""),
        _AUDIT.get("final_url") or _AUDIT.get("url", ""),
        _AUDIT.get("score", 0),
        summary,
        _AUDIT.get("findings", []),
    )


@beta_tool
def open_deal(name: str, amount: str = "") -> str:
    """Open a deal on the lead so it enters the pipeline.

    Call this once, only if the audit turned up at least one critical issue.

    Args:
        name: The deal name, e.g. "Acme Ltd — site rebuild".
        amount: Optional ballpark value in whole currency units, e.g. "2500".
    """
    return hubspot.create_deal(_LEAD.get("id", "unknown"), name, amount)


@beta_tool
def draft_pitch_email(subject: str, body: str) -> str:
    """Draft the pitch email to the lead.

    Call this exactly once, last. Ground every claim in the audit and keep it
    under 180 words.

    Args:
        subject: A specific subject line referencing their site.
        body: The email body — a specific opening line, the two or three
            problems that cost them customers, one low-friction ask, sign-off.
    """
    return gmail.create_draft(_LEAD.get("email", "") or "unknown@example.com", subject, body)


ALL_TOOLS = [audit_website, log_audit_to_crm, create_onepager, open_deal, draft_pitch_email]


# ── Provider-agnostic tool interface (used by the Cerebras/OpenAI backend) ──

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "audit_website",
            "description": "Run a real, measured audit of the prospect's website. Call first, once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The prospect's website URL."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_audit_to_crm",
            "description": "Write the audit findings onto the lead's CRM record. Call once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string", "description": "One line with the score and headline problem."},
                    "findings_markdown": {"type": "string", "description": "Short bulleted list, worst first."},
                },
                "required": ["headline", "findings_markdown"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_onepager",
            "description": "Render the audit as a branded one-pager. Call once. Score/findings are filled in automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Two or three sentences on the state of the site."},
                },
                "required": ["summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_deal",
            "description": "Open a deal on the lead. Only if the audit found a critical issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Deal name."},
                    "amount": {"type": "string", "description": "Optional ballpark value, digits only."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_pitch_email",
            "description": "Draft the pitch email to the lead. Call once, last.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Specific subject line referencing their site."},
                    "body": {"type": "string", "description": "Under 180 words, grounded in the audit."},
                },
                "required": ["subject", "body"],
            },
        },
    },
]


def dispatch(name: str, args: dict) -> str:
    """Execute a tool call by name — the same connectors the Anthropic tools use."""
    global _AUDIT
    if name == "audit_website":
        _AUDIT = audit_engine.audit_site(args.get("url", ""))
        print(audit_engine.format_report(_AUDIT))
        return json.dumps(_AUDIT, indent=2)
    if name == "log_audit_to_crm":
        return hubspot.log_audit(
            _LEAD.get("id", "unknown"), args.get("headline", ""), args.get("findings_markdown", "")
        )
    if name == "create_onepager":
        return onepager.create_onepager(
            _LEAD.get("company", "") or _LEAD.get("name", ""),
            _AUDIT.get("final_url") or _AUDIT.get("url", ""),
            _AUDIT.get("score", 0),
            args.get("summary", ""),
            _AUDIT.get("findings", []),
        )
    if name == "open_deal":
        return hubspot.create_deal(_LEAD.get("id", "unknown"), args.get("name", ""), args.get("amount", ""))
    if name == "draft_pitch_email":
        return gmail.create_draft(
            _LEAD.get("email", "") or "unknown@example.com", args.get("subject", ""), args.get("body", "")
        )
    return f"Error: unknown tool {name!r}"
