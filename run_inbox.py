#!/usr/bin/env python3
"""Run the Inbox Assistant — ingest the sample inbox, then ask it questions.

    python run_inbox.py --ingest                         # load the sample inbox
    python run_inbox.py --web                             # chat window in your browser
    python run_inbox.py --ask "what did I order from Amazon?"
    python run_inbox.py                                   # interactive terminal chat
    python run_inbox.py --selftest                        # no API key needed

With only ANTHROPIC_API_KEY set, Gmail stays in dry-run mode and the agent
answers from the bundled sample inbox — so it's demoable before you connect a
real Gmail account (a later episode; see inbox_assistant/connectors/gmail.py).
"""

import argparse
import sys


def selftest() -> int:
    """Exercise the store + connector plumbing in dry-run, without calling the model."""
    from inbox_assistant import config, store
    from inbox_assistant.connectors import gmail

    print("Self-test — Inbox Assistant plumbing (dry-run)\n")
    prov = config.provider()
    model = config.CEREBRAS_MODEL if prov == "cerebras" else config.MODEL
    print(f"  provider    : {prov or 'NONE (set a key)'}")
    print(f"  model       : {model}")
    print(f"  gmail live? : {config.gmail_live()}\n")

    emails = gmail.fetch_recent(limit=3)
    for e in emails:
        store.upsert_email(
            {
                "message_id": e["message_id"],
                "received_at": e["received_at"],
                "sender": e["from"],
                "subject": e["subject"],
                "body": e["body"],
                "category": "other",
                "entity": None,
                "order_id": None,
                "tracking_number": None,
                "expiry_date": None,
                "amount": None,
                "status": None,
            }
        )
    hits = store.search(limit=10)
    print(f"\n  stored {len(hits)} sample email(s) in {config.DB_PATH}")
    if hits:
        gmail.archive_message(hits[0]["message_id"])
    print("\n✅ Store + Gmail connector reachable. Run --ingest to extract real fields.")
    return 0


def ingest() -> int:
    from inbox_assistant import config, ingest as ingest_mod

    if config.provider() is None:
        print("No model key set — extraction needs CEREBRAS_API_KEY or ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1
    print("▶ Ingesting inbox (extracting structured fields with Claude)")
    print("─" * 60)
    count = ingest_mod.run()
    print("─" * 60)
    print(f"Done. {count} email(s) ingested.")
    return 0


def chat(backend, question: str) -> None:
    backend.ask(question)


def web(port: int) -> int:
    from inbox_assistant import config, web as web_mod

    if config.provider() is None:
        print("No model key set. Copy .env.example to .env and add ONE of:")
        print("  • CEREBRAS_API_KEY   (free tier — Llama/Qwen)")
        print("  • ANTHROPIC_API_KEY  (claude-opus-4-8)")
        return 1

    print(f"▶ Inbox Assistant chat window: http://127.0.0.1:{port}")
    print("  Ctrl+C to stop.")
    web_mod.run(port=port)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inbox Assistant — ask your email questions.")
    parser.add_argument("--ask", type=str, default=None, help="Ask a single question and exit")
    parser.add_argument("--ingest", action="store_true", help="Pull + extract + store the sample inbox")
    parser.add_argument("--web", action="store_true", help="Open a chat window in your browser")
    parser.add_argument("--port", type=int, default=5050, help="Port for --web (default 5050)")
    parser.add_argument("--selftest", action="store_true", help="Check plumbing without the API")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if args.ingest:
        return ingest()

    if args.web:
        return web(args.port)

    from inbox_assistant import config

    prov = config.provider()
    if prov is None:
        print("No model key set. Copy .env.example to .env and add ONE of:")
        print("  • CEREBRAS_API_KEY   (free tier — Llama/Qwen)")
        print("  • ANTHROPIC_API_KEY  (claude-opus-4-8)")
        print("Or run `python run_inbox.py --selftest` to check the plumbing without a key.", file=sys.stderr)
        return 1

    if prov == "cerebras":
        from inbox_assistant import cerebras_agent as backend
        model = config.CEREBRAS_MODEL
    else:
        from inbox_assistant import agent as backend
        model = config.MODEL

    banner = "live" if config.gmail_live() else "dry-run (sample inbox)"
    print(f"▶ Inbox Assistant   brain: {prov} ({model})   gmail: {banner}")
    print("  Run --ingest first if you haven't loaded any email yet.")
    print("─" * 60)

    if args.ask:
        chat(backend, args.ask)
        return 0

    print("Interactive mode — ask a question, or Ctrl+C to quit.")
    try:
        while True:
            question = input("\nyou> ").strip()
            if not question:
                continue
            chat(backend, question)
    except (KeyboardInterrupt, EOFError):
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
