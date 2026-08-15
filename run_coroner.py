#!/usr/bin/env python3
"""Run Commit Coroner on a CI failure report.

    python run_coroner.py                            # uses the bundled sample
    python run_coroner.py --failure path/to/report.txt
    python run_coroner.py --selftest                  # no API key needed; checks the plumbing

With only ANTHROPIC_API_KEY set, GitHub/Slack run in dry-run mode and print
what they would do. Git forensics always run live — it's your repo, on disk,
no key required.
"""

import argparse
import sys
from pathlib import Path

SAMPLE = Path(__file__).parent / "samples" / "ci_failure_report.txt"


def selftest() -> int:
    """Exercise git forensics for real, and the GitHub/Slack connectors in dry-run."""
    from commit_coroner import config
    from commit_coroner.connectors import git_forensics, github, slack

    print("Self-test — connector plumbing\n")
    prov = config.provider()
    model = config.CEREBRAS_MODEL if prov == "cerebras" else config.MODEL
    print(f"  provider         : {prov or 'NONE (set a key)'}")
    print(f"  model            : {model}")
    print(f"  github live?     : {config.github_live()}")
    print(f"  slack live?      : {config.slack_live()}\n")

    print("Git forensics (live, real repo):")
    print(git_forensics.recent_commits_touching("meeting_ops/connectors/linear.py", limit=3))
    print()

    github.open_issue(
        "Self-test autopsy", "## Verdict\nPlumbing works.", labels=["self-test"]
    )
    slack.post_alert("Self-test: Commit Coroner plumbing works.")
    print("\n✅ Connectors reachable. Add keys in .env to go live.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit Coroner — the CI-failure autopsy agent.")
    parser.add_argument("--failure", type=Path, default=SAMPLE, help="Path to a CI failure report .txt")
    parser.add_argument("--selftest", action="store_true", help="Check plumbing without the API")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not args.failure.exists():
        print(f"Failure report not found: {args.failure}", file=sys.stderr)
        return 1

    from commit_coroner import config

    prov = config.provider()
    if prov is None:
        print("No model key set. Copy .env.example to .env and add ONE of:")
        print("  • CEREBRAS_API_KEY   (free tier — Llama/Qwen)")
        print("  • ANTHROPIC_API_KEY  (claude-opus-4-8)")
        print("Or run `python run_coroner.py --selftest` to check the plumbing without a key.", file=sys.stderr)
        return 1

    if prov == "cerebras":
        from commit_coroner import cerebras_agent as backend
        model = config.CEREBRAS_MODEL
    else:
        from commit_coroner import agent as backend
        model = config.MODEL

    report = args.failure.read_text(encoding="utf-8")
    banner = "live" if (config.github_live() or config.slack_live()) else "dry-run"
    print(f"▶ Commit Coroner on {args.failure.name}")
    print(f"  brain: {prov} ({model})   integrations: {banner}   git forensics: live")
    print("─" * 60)
    backend.run(report)
    print("─" * 60)
    print("Done. Culprit named, autopsy filed, incident raised.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
