# Agent spec — the bar every Hundred agent clears

A customer pays $4.99/month for an agent. It has to be obviously better than
typing the same request into their AI with no agent. Two things make it better:

1. **The playbook** — the procedure a top-1% practitioner actually follows,
   written as instructions to an AI. Named frameworks, concrete thresholds,
   decision rules, an exact output template, and the mistakes amateurs make.
2. **The tools** — deterministic code for the parts LLMs get wrong: arithmetic,
   dates, counting, scoring against a rubric, character limits, parsing,
   statistics. The playbook tells the AI exactly when to call each one.

Reference implementation: `hundred/agents/ops/meeting_ops.py` and
`tests/agents/test_ops_meeting_ops.py`. Copy that shape.

## File layout

- One agent per module: `hundred/agents/<category>/<slug_with_underscores>.py`
- Module defines `AGENT = Agent(...)` and registers tools with `@AGENT.tool`.
- Tests: `tests/agents/test_<category>_<slug_with_underscores>.py`.
- Stdlib + pydantic only. No network calls, no file I/O, no randomness
  (or seed it), no LLM calls. Everything runs in < 100 ms.
- Shared helpers live in `hundred/lib/` (`text.py`: words, sentences,
  syllables, readability, keyword density, passive voice; `dates.py`: parse,
  business days). Reuse them; add to them only if genuinely shared.

## Metadata (enforced by `tests/test_library.py`)

| Field | Rule |
|---|---|
| `slug` | kebab-case, unique, matches the roster |
| `name` | 2-4 words, memorable, sells the outcome ("Cold Email Closer") |
| `category` | the folder it lives in |
| `tagline` | 20-140 chars, one sentence, outcome-first |
| `description` | ≥ 120 chars: what it does end-to-end, what makes it better |
| `triggers` | ≥ 4 phrasings of what a user would ask — the host AI routes on these |
| `examples` | ≥ 3 realistic first messages a customer would send |
| `connectors` | services the agent should *act* through if the user's AI has them (Gmail, HubSpot, Notion, Shopify, GitHub…) |

## Playbook (≥ 450 words; required headings)

```
## Standard       — who you are, what "excellent" means here, the one metric that matters
## Intake         — what you need; ask at most 3 questions, ONLY if you can't proceed;
                    otherwise assume, state assumptions, and continue
## Procedure      — numbered steps; each tool call named with its wire name
                    `<slug_underscored>__<tool>` and exactly when/why to call it
## Frameworks     — (optional but usual) the named methods, thresholds, benchmarks
## Output format  — an exact template in a fenced block
## Anti-patterns  — the specific mistakes that make output mediocre
```

Write it as direct instructions to the AI. Specific beats general:
"subject lines ≤ 45 chars, no spam triggers, lowercase test variant" beats
"write compelling subject lines". Include real benchmarks (reply rates,
conversion ranges, word counts) where they exist and are well-established;
never invent statistics. Where advice has legal/medical/financial risk, add a
one-line scope note (e.g. "not legal advice; flag for a lawyer when X").

## Tools (3-7 per agent)

- Google-style docstring: first paragraph = what it does and when to call it
  (≥ 40 chars); `Args:` section describing **every** parameter.
- Type-hinted params; use `list[str]`, `list[dict]`, `float`, `int`, `bool`,
  `str`, `Literal[...]`. Defaults for optional params.
- Return a `dict` (JSON-serialisable) with structured data **plus** a
  human-readable `verdict`/`summary` and, where useful, `fixes` or `next_step`.
- Validate inputs; raise `ToolError("clear message")` for bad input. Bound
  sizes (e.g. reject > 200k chars, > 500 rows). Guard regex from user input
  against catastrophic backtracking (length limits; see regex-builder).
- No tool may be a thin wrapper that returns the LLM's own input. Each must
  compute something the model would otherwise get wrong or skip.
- Tool names are snake_case; wire name `<prefix>__<tool>` must be ≤ 64 chars.

## Tests

Every tool gets at least one test asserting real computed values (not just
"returns a dict"), plus a bad-input test that expects `ToolError`. Run:

```
python -m pytest -q tests
```

All tests, including `tests/test_library.py` quality gates, must pass.
