# 100 Agents · 100 Days → **Hundred**

100 expert AI agents, sold as a subscription, delivered as **one MCP link** that
customers paste into the AI they already use — Claude, ChatGPT, Cursor, VS Code,
Claude Code, Windsurf, Gemini CLI.

- **$4.99/mo per agent**, or bundles: any 5 for $14.99 · a whole category for $14.99 ·
  everything for $29.99 · Founding Member everything for $14.99 locked for life (first 500).
- **7-day free trial**, card required. Two agents are free forever (Meeting Ops, Copy Editor).
- **Access follows payment.** Card declines → agents switch off on the next call.
  Payment succeeds → they're back instantly, same link, nothing to reinstall.
- **No LLM runs on our side.** The customer's AI does the reasoning; we supply the expert
  playbook and the deterministic tools. Inference cost is zero, so margin is ~all of it.

> The test every agent has to pass: **is it obviously better than typing the same
> request into your AI with no agent?** Each one ships a top-1% practitioner's
> operating procedure plus real code for the parts AI gets wrong — math, dates,
> statistics, character limits, parsing, scoring.

## What an agent is

```
hundred/agents/sales/cold_email.py
  AGENT = Agent(slug="cold-email", name="Cold Email Closer", playbook="""…expert procedure…""")
  @AGENT.tool def score_subject_line(...)      ← deterministic, tested, exposed as an MCP tool
  @AGENT.tool def schedule_sequence(...)
```

Over MCP each owned agent appears as `<agent>__start` (returns the playbook — the AI
follows it) plus its tools (`cold_email__score_subject_line`, …). Keys that own more
than ~40 tools automatically get **router mode**: three meta-tools
(`hundred_find_agent`, `hundred_start`, `hundred_run`) that reach every agent, so
All-Access works in clients that cap tool counts. Every tool is annotated read-only,
so clients can auto-approve them.

The quality bar is enforced in code: `tests/test_library.py` fails any agent with a thin
playbook, missing sections, a tool the playbook never tells the AI to call, or an
undocumented parameter. The full bar is in [docs/AGENT_SPEC.md](docs/AGENT_SPEC.md); the
roster in [docs/ROSTER.md](docs/ROSTER.md).

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q                         # library quality gates + billing + MCP end-to-end
python -m hundred.admin catalog             # list the agents
python -m hundred.admin serve               # storefront + MCP on http://localhost:8000
```

Try it in Claude Code without paying anything:

```bash
claude mcp add --transport http hundred "http://localhost:8000/mcp"            # free agents
python -m hundred.admin issue-key --email you@example.com --plan all            # comp key for everything
claude mcp add --transport http hundred-all "http://localhost:8000/mcp?key=hnd_live_…"
```

## How the business runs

| Piece | Where |
|---|---|
| Storefront, per-agent SEO pages, pick-your-agents checkout | `hundred/server/web.py`, `app.py` |
| Stripe Checkout, webhooks, portal, reconcile | `hundred/server/billing.py` |
| Licenses (hashed keys, one-time reveal, usage metering) | `hundred/server/store.py` |
| Entitlement-gated MCP endpoint | `hundred/server/mcp_server.py` |
| Pricing & what each plan unlocks | `hundred/plans.py` |
| Operator CLI (stripe-setup, comp keys, revoke, reconcile) | `hundred/admin.py` |
| Deploy | `Dockerfile`, `fly.toml`, [docs/LAUNCH_CHECKLIST.md](docs/LAUNCH_CHECKLIST.md) |
| Go-to-market, launch copy, email sequences, directories | [`marketing/`](marketing/) |

**Connecting is: add one URL, sign in, ask.** `/mcp` answers 401 with OAuth discovery metadata, so
Claude, ChatGPT, Cursor and VS Code open the `/connect` sign-in page (email + 6-digit code, or a
license key). Signing in with an email that has no subscription connects the free agents and records a
lead. Then the customer just types: `hundred_start` picks the right agent from their words, and if the
best agent isn't in their plan it says which one and how to add it. `hundred_memory` keeps context
across chats and `hundred_recipes` chains agents for whole jobs.

Keys still work too, as `?key=`, `Authorization: Bearer`, or path-style
`/k/<key>/mcp` for clients that drop query strings. `&agents=a,b` scopes a
connection to a few agents; `&mode=direct|router` forces a mode.

---

## Agent #1 — Meeting Ops (standalone version)

The original day-1 build still lives here as a standalone script that takes real
actions (Notion page, Linear issues, Gmail draft) with its own model loop:

```bash
python run.py --selftest                    # check the plumbing, no API key needed
python run.py                               # runs on the bundled sample (Cerebras or Anthropic key)
```

```
run.py                     CLI entry point (--transcript / --selftest)
meeting_ops/               agent loop (Anthropic Tool Runner or Cerebras), prompts, tools, connectors
samples/standup_transcript.txt
```

The MCP version (`hundred/agents/ops/meeting_ops.py`) is the free lead-magnet agent in
the store: same job, but it runs inside the customer's own AI and uses *their* Notion /
Linear / Gmail connectors.
