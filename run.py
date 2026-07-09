#!/usr/bin/env python3
"""Run Meeting Ops on a meeting transcript.

    python run.py                              # uses the bundled sample
    python run.py --transcript path/to.txt     # your own transcript
    python run.py --selftest                   # no API key needed; checks the plumbing

With only ANTHROPIC_API_KEY set, Notion/Linear/Gmail run in dry-run mode and
print what they would do — so the whole agent is demoable before you connect
a single external account.
"""

import argparse
import sys
from pathlib import Path

SAMPLE = Path(__file__).parent / "samples" / "standup_transcript.txt"


def selftest() -> int:
    """Exercise the connectors in dry-run without calling the model."""
    from meeting_ops import config
    from meeting_ops.connectors import gmail, linear, notion

    print("Self-test — connector plumbing (dry-run)\n")
    print(f"  model            : {config.MODEL}")
    print(f"  anthropic key    : {'set' if config.ANTHROPIC_API_KEY else 'MISSING'}")
    print(f"  notion live?     : {config.notion_live()}")
    print(f"  linear live?     : {config.linear_live()}\n")

    notion.create_page("Self-test notes", "## Summary\nPlumbing works.\n## Decisions\n- Ship it")
    linear.create_issue("Verify the pipe", "Self-test task", assignee="Claude")
    gmail.create_draft("team@example.com", "Self-test", "Recap: it works.\n— Meeting Ops")
    print("\n✅ Connectors reachable. Add keys in .env to go live.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Meeting Ops — the meeting-end agent.")
    parser.add_argument("--transcript", type=Path, default=SAMPLE, help="Path to a transcript .txt")
    parser.add_argument("--selftest", action="store_true", help="Check plumbing without the API")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not args.transcript.exists():
        print(f"Transcript not found: {args.transcript}", file=sys.stderr)
        return 1

    from meeting_ops import agent, config

    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key,")
        print("or run `python run.py --selftest` to check the plumbing without it.", file=sys.stderr)
        return 1

    transcript = args.transcript.read_text()
    banner = "live" if (config.notion_live() or config.linear_live()) else "dry-run"
    print(f"▶ Meeting Ops on {args.transcript.name}  (integrations: {banner})")
    print("─" * 60)
    agent.run(transcript)
    print("─" * 60)
    print("Done. Notes filed, tasks created, follow-up drafted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
