"""The agent's tools — search, order status, and archive.

This is what makes it an agent and not a search box: the model decides which
tool to call (and with what query) based on the question, reads the results,
and either answers or calls another tool. archive_email is the one tool with
a side effect, and it's deliberately reversible-only (see prompts.py).
"""

from anthropic import beta_tool

from . import store
from .connectors import gmail


def _format_hits(hits: list[dict]) -> str:
    if not hits:
        return "No matching emails found."
    lines = []
    for h in hits:
        bits = [f"[{h['message_id']}]", h["received_at"][:10], f"({h['category']})", h["subject"]]
        if h.get("entity"):
            bits.append(f"from {h['entity']}")
        if h.get("order_id"):
            bits.append(f"order {h['order_id']}")
        if h.get("tracking_number"):
            bits.append(f"tracking {h['tracking_number']}")
        if h.get("expiry_date"):
            bits.append(f"expires {h['expiry_date']}")
        if h.get("amount") is not None:
            bits.append(f"${h['amount']}")
        if h.get("status"):
            bits.append(f"status: {h['status']}")
        lines.append(" · ".join(bits))
    return "\n".join(lines)


@beta_tool
def search_emails(query: str = "", category: str = "", limit: int = 10) -> str:
    """Search the user's email by keyword and/or category.

    Args:
        query: Keywords to match against subject, body, and sender/entity.
            Leave blank to just filter by category.
        category: Optional filter — one of "order", "delivery", "travel-doc",
            "bill", "other". Leave blank to search all categories.
        limit: Max results to return, most recent first.
    """
    return _do_search(query=query, category=category, limit=limit)


@beta_tool
def get_order_status(order_query: str) -> str:
    """Look up the status of an order or delivery by order number, entity, or item name.

    Args:
        order_query: What to search for, e.g. an order number, "Amazon", or an
            item name like "standing desk mat".
    """
    return _do_order_status(order_query)


@beta_tool
def archive_email(message_id: str) -> str:
    """Archive one email by its message_id. Always reversible; never a hard delete.

    Only call this after the user has clearly asked to archive/clean up a
    specific email you already found via search_emails.

    Args:
        message_id: The message_id shown in search results, e.g. "amz-001".
    """
    return _do_archive(message_id)


ALL_TOOLS = [search_emails, get_order_status, archive_email]


# ── Provider-agnostic tool interface (used by the Cerebras/OpenAI backend) ──

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search the user's email by keyword and/or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords to match."},
                    "category": {
                        "type": "string",
                        "description": "One of order, delivery, travel-doc, bill, other.",
                    },
                    "limit": {"type": "integer", "description": "Max results, default 10."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Look up order/delivery status by order number, entity, or item name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_query": {"type": "string", "description": "Order number, sender, or item name."},
                },
                "required": ["order_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "archive_email",
            "description": "Archive one email by message_id. Reversible; never a hard delete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "The email's message_id."},
                },
                "required": ["message_id"],
            },
        },
    },
]


def _do_search(query: str = "", category: str = "", limit: int = 10) -> str:
    return _format_hits(store.search(query=query, category=category, limit=limit))


def _do_order_status(order_query: str) -> str:
    hits = store.search(query=order_query, category="order", limit=5)
    hits += store.search(query=order_query, category="delivery", limit=5)
    return _format_hits(hits)


def _do_archive(message_id: str) -> str:
    email = store.get_by_id(message_id)
    if not email:
        return f"No email found with id {message_id!r}."
    gmail.archive_message(message_id)
    store.archive(message_id)
    return f"Archived: {email['subject']!r} ({email['received_at'][:10]})"


def dispatch(name: str, args: dict) -> str:
    """Execute a tool call by name — the same store/connector the Anthropic tools use."""
    if name == "search_emails":
        return _do_search(
            query=args.get("query", ""), category=args.get("category", ""), limit=args.get("limit", 10)
        )
    if name == "get_order_status":
        return _do_order_status(order_query=args.get("order_query", ""))
    if name == "archive_email":
        return _do_archive(message_id=args.get("message_id", ""))
    return f"Error: unknown tool {name!r}"
