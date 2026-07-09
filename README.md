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

The build plan for all 24 agents lives in the 6-week launch spreadsheet. Meeting
Ops is Sprint 1, Day 1 — the flagship.
