#!/usr/bin/env python3
"""Run Lead Scout — the inbound-lead agent.

    python scout.py --watch                    # poll for new leads, forever (the real trigger)
    python scout.py --once                     # poll once, work any new leads
    python scout.py --url acme.com             # work one prospect now (the demo)
    python scout.py --audit-only acme.com      # just the audit, no model, no API key
    python scout.py --selftest                 # check the plumbing, no API key needed

With only a model key set, HubSpot runs in dry-run: it prints exactly what it
would write and returns a fake id. The audit is never dry-run — it always goes
and measures the real site.
"""

import argparse
import sys
import time

from lead_scout import audit as audit_engine
from lead_scout import config, leads, state


def _backend():
    """Import the right agent backend for whichever key is set."""
    prov = config.provider()
    if prov == "cerebras":
        from lead_scout import cerebras_agent as backend

        return prov, backend, config.CEREBRAS_MODEL
    if prov == "anthropic":
        from lead_scout import agent as backend

        return prov, backend, config.MODEL
    return None, None, None


def selftest() -> int:
    """Exercise the plumbing without calling the model."""
    from lead_scout.connectors import gmail, hubspot, onepager

    print("Self-test — Lead Scout plumbing (dry-run)\n")
    prov = config.provider()
    model = config.CEREBRAS_MODEL if prov == "cerebras" else config.MODEL
    print(f"  provider         : {prov or 'NONE (set a key)'}")
    print(f"  model            : {model}")
    print(f"  anthropic key    : {'set' if config.ANTHROPIC_API_KEY else '-'}")
    print(f"  cerebras key     : {'set' if config.CEREBRAS_API_KEY else '-'}")
    print(f"  hubspot live?    : {config.hubspot_live()}")
    print(f"  pagespeed live?  : {config.pagespeed_live()}")
    print(f"  agency           : {config.AGENCY_NAME}")

    pending = leads.fetch_new(include_seen=True)
    source = "HubSpot" if config.hubspot_live() else "bundled samples"
    print(f"  lead source      : {source} ({len(pending)} auditable lead(s))\n")

    hubspot.log_audit("selftest-contact", "Site audit: 55/100 — plumbing check", "- Everything wired up")
    hubspot.create_deal("selftest-contact", "Self-test — site rebuild", "1000")
    onepager.create_onepager(
        "Self Test Ltd",
        "https://example.com",
        55,
        "Plumbing works.",
        [{"severity": "warning", "message": "This is a sample finding."}],
    )
    gmail.create_draft("team@example.com", "Self-test", "Recap: it works.\n— Lead Scout")
    print("\n✅ Connectors reachable. Add keys in .env to go live.")
    return 0


def audit_only(url: str) -> int:
    """Run the audit engine on its own — no model, no key, no CRM."""
    print(f"▶ Auditing {url}\n")
    print(audit_engine.format_report(audit_engine.audit_site(url)))
    return 0


def work_lead(lead: dict, backend, banner: str) -> None:
    who = lead.get("company") or lead.get("name") or lead.get("website")
    print(f"\n▶ New lead: {who}  →  {lead.get('website')}")
    print(f"  integrations: {banner}")
    print("─" * 60)
    backend.run(lead)
    print("─" * 60)
    state.mark_seen(lead["id"])
    print("Done. Audited, logged to CRM, one-pager written, pitch drafted.")


def poll_once(backend, banner: str) -> int:
    """Check for new leads and work each one. Returns how many were worked."""
    pending = leads.fetch_new()
    if not pending:
        return 0
    for lead in pending:
        work_lead(lead, backend, banner)
    return len(pending)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lead Scout — the inbound-lead agent.")
    parser.add_argument("--watch", action="store_true", help="Poll for new leads and work them as they arrive")
    parser.add_argument("--once", action="store_true", help="Poll once and work any new leads")
    parser.add_argument("--url", help="Work one prospect's site right now (demo mode)")
    parser.add_argument("--audit-only", metavar="URL", help="Run just the audit — no model needed")
    parser.add_argument("--selftest", action="store_true", help="Check plumbing without the API")
    parser.add_argument("--models", action="store_true", help="List models your key can reach")
    parser.add_argument("--reset", action="store_true", help="Forget which leads were already worked")
    parser.add_argument(
        "--interval", type=int, default=config.POLL_INTERVAL, help="Seconds between polls with --watch"
    )
    args = parser.parse_args()

    if args.reset:
        state.reset()
        print("State cleared — every lead looks new again.")
        if not (args.watch or args.once or args.url or args.selftest or args.audit_only):
            return 0

    if args.models:
        if not config.CEREBRAS_API_KEY:
            print("Set CEREBRAS_API_KEY in .env first — this lists what that key can reach.")
            return 1
        models = config.available_models()
        print(f"Models available to your Cerebras key ({len(models)}):\n")
        for m in models:
            print(f"  {m}{'   ← currently configured' if m == config.CEREBRAS_MODEL else ''}")
        if config.CEREBRAS_MODEL not in models:
            print(f"\n⚠️  Your CEREBRAS_MODEL is {config.CEREBRAS_MODEL!r}, which isn't in that list.")
            print("   Put one of the above in .env as CEREBRAS_MODEL= and restart.")
        return 0

    if args.selftest:
        return selftest()

    if args.audit_only:
        return audit_only(args.audit_only)

    prov, backend, model = _backend()
    if prov is None:
        print("No model key set. Copy .env.example to .env and add ONE of:")
        print("  • CEREBRAS_API_KEY   (free tier — open models)")
        print("  • ANTHROPIC_API_KEY  (claude-opus-5)")
        print("Or run `python scout.py --audit-only acme.com` to see the audit with no key.", file=sys.stderr)
        return 1

    banner = "live" if config.hubspot_live() else "dry-run"
    print(f"Lead Scout — brain: {prov} ({model})   integrations: {banner}")

    if args.url:
        lead = {
            "id": f"manual:{args.url}",
            "name": "there",
            "email": "",
            "company": "",
            "website": args.url,
        }
        work_lead(lead, backend, banner)
        return 0

    if args.once:
        n = poll_once(backend, banner)
        print(f"\nPolled once — {n} new lead(s) worked.")
        return 0

    if args.watch:
        source = "HubSpot" if config.hubspot_live() else "bundled samples"
        print(f"Watching {source} every {args.interval}s. Ctrl-C to stop.\n")
        try:
            while True:
                worked = poll_once(backend, banner)
                if not worked:
                    print(f"  · no new leads ({time.strftime('%H:%M:%S')})")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped watching.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
