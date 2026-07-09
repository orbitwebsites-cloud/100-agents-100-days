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
    prov = config.provider()
    model = config.CEREBRAS_MODEL if prov == "cerebras" else config.MODEL
    print(f"  provider         : {prov or 'NONE (set a key)'}")
    print(f"  model            : {model}")
    print(f"  anthropic key    : {'set' if config.ANTHROPIC_API_KEY else '-'}")
    print(f"  cerebras key     : {'set' if config.CEREBRAS_API_KEY else '-'}")
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

    from meeting_ops import config

    prov = config.provider()
    if prov is None:
        print("No model key set. Copy .env.example to .env and add ONE of:")
        print("  • CEREBRAS_API_KEY   (free tier — Llama/Qwen)")
        print("  • ANTHROPIC_API_KEY  (claude-opus-4-8)")
        print("Or run `python run.py --selftest` to check the plumbing without a key.", file=sys.stderr)
        return 1

    if prov == "cerebras":
        from meeting_ops import cerebras_agent as backend
        model = config.CEREBRAS_MODEL
    else:
        from meeting_ops import agent as backend
        model = config.MODEL

    transcript = args.transcript.read_text(encoding="utf-8")
    banner = "live" if (config.notion_live() or config.linear_live()) else "dry-run"
    print(f"▶ Meeting Ops on {args.transcript.name}")
    print(f"  brain: {prov} ({model})   integrations: {banner}")
    print("─" * 60)
    backend.run(transcript)
    print("─" * 60)
    print("Done. Notes filed, tasks created, follow-up drafted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
