"""Gmail connector — drafts the follow-up email.

Dry-run in this episode: it prints the draft it would place in your Gmail
drafts folder. Wiring up Gmail OAuth is a later build; the agent's job here is
to produce a send-ready draft grounded in the meeting.
"""


def create_draft(to: str, subject: str, body: str) -> str:
    """Stage a follow-up email draft. Returns a draft id."""
    print(f"   ✉️  [Gmail · DRY-RUN] would draft follow-up")
    print(f"      │ To: {to}")
    print(f"      │ Subject: {subject}")
    for line in body.splitlines():
        print(f"      │ {line}")
    return "gmail:dry-run://draft/followup"
