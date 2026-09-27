# Live model runs

`python -m hundred.live_eval` connects the agents to a real model, exactly as a customer's AI sees them,
and grades what the model **does**:

| Check | Pass means |
|---|---|
| Routed | it started the agent we'd expect for the request (or, for an off-topic question, started none) |
| Used a tool | it ran at least one of that agent's tools — the math and validation customers pay for |
| Recovered | any tool error was followed by a successful retry |
| Answered | it finished with a reply to the user |

Two setups per model:
- **router**: All-Access, where the model sees 6 meta-tools and must find the agent itself.
- **pick5**: a Pick-5 customer, where the model sees the direct tools of 5 agents, 4 of them unrelated.

There are 20 scenarios in `hundred/live_eval.py` (`SCENARIOS`). Each one is a real request with real
numbers in it.

## Run it

Keys are read from environment variables (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`). Set them in the
environment's settings, never in the repo.

```bash
# What ChatGPT users get
python -m hundred.live_eval --provider openai --model gpt-5-mini --budget 1

# Everyone else, through OpenRouter (several models, one capped budget)
python -m hundred.live_eval --provider openrouter --budget 2 \
  --model google/gemini-3-flash-preview --model anthropic/claude-haiku-4.5 \
  --model deepseek/deepseek-v4-pro --model meta-llama/llama-4-maverick

# Clients that ignore MCP server instructions
python -m hundred.live_eval --provider openrouter --model openai/gpt-5-mini --no-instructions --mode router
```

`--budget` is a hard cap in dollars for the whole run: the harness checks it before every call and stops
once it's reached. Costs are taken from OpenRouter's `usage.cost`, or calculated from OpenRouter's public
price list for OpenAI models.

A scenario is about 10–15k input tokens, so a full run (20 router + 19 pick5) costs roughly **$0.30–0.60
per small model** and a few dollars per frontier model.

Reports land here as `<timestamp>-<provider>.md` (a summary table plus every scenario) with the raw
`.json` beside them.
