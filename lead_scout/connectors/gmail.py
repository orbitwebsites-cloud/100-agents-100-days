"""Gmail connector — drafts the pitch email.

Dry-run in this episode, same as Agent #1: it prints the draft it would place
in your drafts folder. The agent's job is a send-ready email grounded in the
audit — never auto-sent, because a pitch that goes out unread is how you lose
a lead.
"""


def create_draft(to: str, subject: str, body: str) -> str:
    """Stage a pitch email draft. Returns a draft id."""
    print("   ✉️  [Gmail · DRY-RUN] would draft pitch")
    print(f"      │ To: {to}")
    print(f"      │ Subject: {subject}")
    for line in body.splitlines():
        print(f"      │ {line}")
    return "gmail:dry-run://draft/pitch"
