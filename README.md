# 100 Agents · 100 Days

Building 24 genuinely-agentic tools in public — the kind with a real trigger, a
real integration, and a real action, not a ChatGPT prompt in a trenchcoat.

> The test every agent here has to pass: **could you get the same result by typing
> one prompt into ChatGPT?** If yes, it's not an agent. If it needs to fire on its
> own, read live data, and change something in the world — it's in.

## Agent #1 — Meeting Ops

When a meeting ends, Meeting Ops runs the whole post-meeting workflow:

1. **Files the notes** — a clean summary + decisions, into **Notion**
2. **Creates the tasks** — one **Linear** issue per action item, with owners
3. **Drafts the follow-up** — a send-ready email to the attendees, in **Gmail**

It's a real agent loop: the model reads the transcript and *calls the tools
itself* until the work is done — it doesn't just describe the notes, it takes the
actions. Runs on either brain:

- **Cerebras** (free tier — Llama/Qwen) via the OpenAI-compatible API
- **Anthropic** (`claude-opus-4-8`) via the Tool Runner

Whichever key you put in `.env` is the one it uses (Cerebras wins if both are set).

### Run it in 30 seconds

```bash
pip install -r requirements.txt
cp .env.example .env          # add CEREBRAS_API_KEY (free) or ANTHROPIC_API_KEY
python run.py                 # runs on the bundled sample transcript
```

Free key: sign up at [cloud.cerebras.ai](https://cloud.cerebras.ai), drop the key in
`CEREBRAS_API_KEY`. With just that, the Notion / Linear / Gmail connectors run in
**dry-run**: they print exactly what they *would* do and return a fake id. So the
whole agent works end-to-end before you connect a single external account —
perfect for a first look (and for filming).

```bash
python run.py --selftest                    # check the plumbing, no API key needed
python run.py --transcript path/to/your.txt # your own meeting
```

### Go live

Fill in the optional keys in `.env` and that connector flips from dry-run to real:

| Connector | Keys | What it does |
|-----------|------|--------------|
| Notion | `NOTION_API_KEY`, `NOTION_DATABASE_ID` | Files the meeting notes as a page |
| Linear | `LINEAR_API_KEY`, `LINEAR_TEAM_ID` | Creates an issue per action item |
| Gmail | *(dry-run for now)* | Drafts the follow-up email |

### How it's built

```
run.py                     CLI entry point (--transcript / --selftest)
meeting_ops/
  agent.py                 Anthropic Tool Runner loop
  cerebras_agent.py        Cerebras / OpenAI-compatible loop (same tools)
  prompts.py               the shared system prompt
  tools.py                 the 3 tools + schemas both backends share
  config.py                env keys, provider pick, dry-run switch
  connectors/
    notion.py              real Notion REST, dry-run fallback
    linear.py              real Linear GraphQL, dry-run fallback
    gmail.py               drafts the follow-up (OAuth: a later episode)
samples/standup_transcript.txt
```

## Agent #2 — Inbox Assistant

A chat-based assistant that reads your email and answers plain-language
questions — "what did I order from Amazon?", "when does my passport
expire?", "what's my delivery status?" — and archives clutter when you ask
it to. Built for non-technical people: no dashboards, no config files.

It's a real agent loop: given a question, the model decides whether to
search, look up an order, or archive an email, calls the tool, reads the
result, and either answers or calls another tool — same Tool Runner pattern
as Meeting Ops, on either brain (Cerebras or Anthropic).

Two things push this past "search box with a chat UI": it runs against a
**real Gmail inbox** over OAuth (not just the bundled sample), and it can
**message you first** — a proactive digest that flags an expiring passport,
a bill due, or a package out for delivery over **Telegram**, without you
ever asking. That's a real trigger (a Telegram message, or a timer) and a
real unprompted action — the bar the top of this README sets for what
counts as an agent.

### Run it in 30 seconds

```bash
pip install -r requirements.txt
cp .env.example .env                 # add CEREBRAS_API_KEY (free) or ANTHROPIC_API_KEY
python run_inbox.py --ingest          # extracts structured fields from the sample inbox
python run_inbox.py --ask "what's out for delivery?"
```

```bash
python run_inbox.py --web             # a little chat window at http://127.0.0.1:5050
python run_inbox.py --selftest        # check the plumbing, no API key needed
python run_inbox.py                   # interactive terminal chat
```

Without a Gmail token, the assistant reads and "archives" against a bundled
sample inbox (`samples/sample_inbox.json`) — the whole agent works
end-to-end before you connect a real Gmail account. Archiving is always
reversible; there's no hard delete in this build.

### Go live

```bash
python run_inbox.py --gmail-auth      # one-time OAuth flow against a real Gmail inbox
python run_inbox.py --telegram        # chat with the agent over Telegram instead of the terminal
python run_inbox.py --digest          # check the inbox once, push a proactive alert if anything's due
python run_inbox.py --watch           # ingest + digest on a timer, forever — the "fires on its own" mode
```

| Connector | Keys | What it does |
|-----------|------|---------------|
| Gmail | `GMAIL_CREDENTIALS_FILE` (OAuth Desktop client JSON) | `--gmail-auth` saves a refreshable token; after that, real reads/archives replace the sample inbox |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Real trigger — message the bot for answers; `--watch` pushes proactive alerts to the same chat |

Leave either blank and that piece stays in dry-run, same as every other
connector in this repo: it prints exactly what it would do.

### How it's built

```
run_inbox.py                CLI entry point (--ingest / --web / --ask / --selftest /
                             --gmail-auth / --telegram / --digest / --watch)
inbox_assistant/
  agent.py                  Anthropic Tool Runner loop
  cerebras_agent.py         Cerebras / OpenAI-compatible loop (same tools)
  web.py                    tiny Flask chat window (same agent, browser instead of terminal)
  telegram_bot.py           long-poll loop — the real trigger, same agent, replies in Telegram
  digest.py                 proactive scan (expiring docs / bills due / out-for-delivery) → Telegram
  templates/chat.html       the chat window's UI
  ingest.py                 pulls raw email, extracts fields via Claude, stores them
  prompts.py                the shared system prompt
  tools.py                  search_emails / get_order_status / archive_email
  store.py                  local SQLite store (stand-in for Supabase + pgvector)
  config.py                 env keys, provider pick, dry-run switch
  connectors/
    gmail.py                real Gmail OAuth read/archive, dry-run against the sample inbox
    telegram.py              real Telegram send/poll, dry-run (prints) without a bot token
samples/sample_inbox.json
```

`store.py` mirrors the `emails` table from the MVP plan (category, entity,
order_id, tracking_number, expiry_date, amount, status, plus an `alerted`
flag so the digest never repeats itself) with keyword search standing in for
pgvector — swapping in Supabase is a connector change, not a rewrite of the
agent or its tools.

---

The build plan for all 24 agents lives in the 6-week launch spreadsheet. Meeting
Ops is Sprint 1, Day 1 — the flagship.
