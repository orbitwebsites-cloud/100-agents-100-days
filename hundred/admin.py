"""Operator CLI.

    python -m hundred.admin catalog                         # what's in the library
    python -m hundred.admin stripe-setup                    # create Stripe products/prices (idempotent)
    python -m hundred.admin issue-key --email a@b.co --plan all --note "podcast guest"
    python -m hundred.admin issue-key --email a@b.co --plan single --agents cold-email,seo-auditor
    python -m hundred.admin revoke --key hnd_live_...
    python -m hundred.admin reconcile                       # re-sync every license from Stripe (cron this)
    python -m hundred.admin licenses                        # list licenses
    python -m hundred.admin brief cold-email "task"          # what the customer's AI receives
    python -m hundred.admin run cold-email score_subject_line '{"subjects": ["quick q"]}'
    python -m hundred.admin serve                           # run the web + MCP server
"""

from __future__ import annotations

import argparse
import sys

from . import plans, registry


def cmd_catalog(_: argparse.Namespace) -> int:
    agents = registry.all_agents()
    tools = sum(len(a.tools) for a in agents.values())
    print(f"{len(agents)} agents · {tools} tools\n")
    for cat, group in registry.by_category().items():
        print(f"{cat} ({len(group)})")
        for a in group:
            print(f"  {'★' if a.free else ' '} {a.slug:<24} {len(a.tools)} tools  {a.tagline}")
    return 0


def _store():
    from .server.settings import settings
    from .server.store import Store

    return Store(settings.database_path)


def cmd_stripe_setup(_: argparse.Namespace) -> int:
    from .server import billing

    for line in billing.ensure_prices():
        print(line)
    return 0


def cmd_issue_key(args: argparse.Namespace) -> int:
    plan = plans.PLANS.get(args.plan)
    if plan is None:
        print(f"unknown plan; choose from {', '.join(plans.PLANS)}", file=sys.stderr)
        return 2
    agents = [a for a in (args.agents or "").split(",") if a]
    cats = [c for c in (args.categories or "").split(",") if c]
    if plan.unlock == "agents":
        agents, _, _ = plans.validate_selection(plans.PLANS["single"], agents, [])
    elif plan.unlock == "categories":
        _, cats, _ = plans.validate_selection(plan, [], cats)
    key, lic = _store().create_license(
        email=args.email, plan=plan.code, status="active", source="comp", all_access=plan.unlock == "all",
        agents=agents, categories=cats, note=args.note,
    )
    from .server.emailer import connect_instructions

    print(f"Issued {plan.name} comp key for {lic.email}\n")
    print(connect_instructions(key))
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    store = _store()
    lic = store.by_key(args.key)
    if lic is None:
        print("no such key", file=sys.stderr)
        return 1
    store.set_status_by_key_hash(lic.key_hash, "canceled")
    print(f"revoked {lic.key_prefix}… ({lic.email})")
    return 0


def cmd_reconcile(_: argparse.Namespace) -> int:
    from .server import billing

    changes = billing.reconcile(_store())
    print("\n".join(changes) or "all licenses in sync")
    return 0


def cmd_licenses(_: argparse.Namespace) -> int:
    for lic in _store().all_licenses():
        scope = "ALL" if lic.all_access else ",".join(lic.agents + lic.categories)
        flag = " CARD-DECLINED" if lic.payment_failed else ""
        print(f"{lic.key_prefix}…  {lic.status:<9}{flag} {lic.source:<6} {lic.plan:<12} {lic.email:<32} {scope[:60]}")
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    """Print exactly what a customer's AI receives from <agent>__start."""
    agent = registry.get(args.agent)
    if agent is None:
        print(f"unknown agent {args.agent!r}", file=sys.stderr)
        return 1
    print(agent.briefing(args.task or ""))
    for t in agent.tools:
        import json

        print(f"\n### {t.name} arguments\n" + json.dumps(t.input_schema(), indent=1))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Call one agent tool with JSON arguments, exactly as the MCP server would."""
    import json

    from .core import ToolError, render_result

    agent = registry.get(args.agent)
    tool = agent.get_tool(args.tool) if agent else None
    if tool is None:
        print(f"unknown agent/tool {args.agent}/{args.tool}", file=sys.stderr)
        return 1
    raw = sys.stdin.read() if args.json == "-" else args.json
    try:
        print(render_result(tool.call(json.loads(raw or "{}"))))
    except ToolError as e:
        print(f"ToolError: {e}")
        return 3
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("hundred.server.app:app", host=args.host, port=args.port, proxy_headers=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m hundred.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalog").set_defaults(fn=cmd_catalog)
    sub.add_parser("stripe-setup").set_defaults(fn=cmd_stripe_setup)
    k = sub.add_parser("issue-key")
    k.add_argument("--email", required=True)
    k.add_argument("--plan", default="all")
    k.add_argument("--agents")
    k.add_argument("--categories")
    k.add_argument("--note")
    k.set_defaults(fn=cmd_issue_key)
    r = sub.add_parser("revoke")
    r.add_argument("--key", required=True)
    r.set_defaults(fn=cmd_revoke)
    sub.add_parser("reconcile").set_defaults(fn=cmd_reconcile)
    sub.add_parser("licenses").set_defaults(fn=cmd_licenses)
    b = sub.add_parser("brief")
    b.add_argument("agent")
    b.add_argument("task", nargs="?")
    b.set_defaults(fn=cmd_brief)
    rn = sub.add_parser("run")
    rn.add_argument("agent")
    rn.add_argument("tool")
    rn.add_argument("json", nargs="?", default="{}", help="JSON arguments, or - to read stdin")
    rn.set_defaults(fn=cmd_run)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except plans.PlanError as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    import signal

    if hasattr(signal, "SIGPIPE"):  # `... | head` shouldn't print a BrokenPipe traceback
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    raise SystemExit(main())
