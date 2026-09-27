# Engineering pack: parity evaluation

Evaluated 2026-09-27, covering all 10 agents in `hundred/agents/engineering/`.

**Method.** For each agent I chose the paid (or de-facto standard) product that overlaps most. From that product's own documentation I wrote a parity checklist. I then wrote a realistic request with planted defects and ran it the way a customer's AI would: `python -m hundred.admin brief <slug>`, then each tool through `hundred.admin run`. Every number was checked by hand, against a published reference (NVD, OWASP, ByteByteGo, the specs), or with independent stdlib code that never imports `hundred` (sqlite3, `re` in a child process, plain arithmetic).

I could not run the competitors (no accounts). Repo/CI integration, PR comments, running scanners on infrastructure and dashboards are marked **OUT OF SCOPE**. They are not counted as failures.

Every scenario can be replayed with `pytest tests/scenarios/test_engineering.py` (72 checks). Each fix has a unit test in `tests/agents/test_engineering_*.py`.

**About a "plain AI" baseline.** I did not run a separate model without the playbook and tools, so this report makes no measured plain-AI claims. What was observed is listed per agent under "traps in the scenario": pitfalls that were planted or turned up. The tools now catch them deterministically, and several of them caught out *our own* pre-fix tooling.

## Overview

| Agent | Comparable & price | Checklist (M / P / Miss / OOS) | Recall / precision / correctness | Verdict | Fixes made |
|---|---|---|---|---|---|
| code-reviewer | CodeRabbit, $24–30/dev/mo | 3 / 3 / 2 / 1 | 5/5 planted defects (2/5 before the fix). 0 findings on the clean file. 0 blocker false positives across 10.3k lines of stdlib, apart from 4 in `ssl.py`'s own unverified-context factory, which are true constructs | **AT PAR** on reviewing a pasted diff; **BELOW** on breadth (no Ruff/ESLint runs, no dependency scanning) | Detects SQL built from strings, TLS verification turned off, and 23 cloud/API key formats. Never echoes a secret (it used to print the full AWS secret) |
| security-auditor | Snyk Team "from $25/mo"; GitGuardian (paid tiers not public) | 4 / 3 / 1 / 1 | CVSS 10/10 against NVD. SQLi and TLS sinks 2/2. Secrets 2/2. 0 false positives on the clean file. Secret leak fixed | **AT PAR** on the pasted-code job, secrets and CVSS; **BELOW** Snyk on dataflow depth and dependency scanning | Every secret on a line is now redacted (one finding's context leaked the other secret). Adds SQL built in f-strings, `.format()` and JS template literals. Findings deduplicated per line and CWE |
| bug-hunter | Sentry Team $26/mo + Seer $40/contributor/mo | 3 / 1 / 0 / 3 (+1 above) | Blame frame exact. Node frames 5/5 (3/5 before, one mangled). Log counts exact. Busiest minute, bisect steps and suspect ranking checked by hand | **AT PAR** on the paste-a-trace-and-logs job | Parses `at async`/`new`/`node:` frames. Handles implicit vs explicit Python exception chains correctly. Hint for JS `undefined`. `changes_before_first_problem` in the log output |
| sql-wizard | AI2sql $9–19/mo; EverSQL/Aiven optimizer (free) | 4 / 3 / 0 / 1 | 3/3 planted traps; 4/4 in the second query (2/4 before the fix). Rewrite lints clean. sqlite3 confirms the original returns **0 rows** and the rewrite uses the range | **AT PAR** | Catches lowercase `lower()`/`date_trunc()`/`extract()` and reports every non-sargable predicate. Index advice: `NOT IN` is not an index prefix, the driving table's join key is dropped, anti/semi-join index added, duplicates removed |
| api-designer | Stoplight Basic $56/mo (3 users); oasdiff (free CLI, Pro $100/mo) | 8 / 1 / 1 / 1 | Breaking changes: 6/6 planted, 0 false positives (1 false positive + 2 misses before the fix). Spec lint: 6/6 planted Spectral issues (2/6 before). Clean spec scores 100 | **AT PAR** on common lint and breaking-change checks; **BELOW** oasdiff on breadth | Renamed path parameters are matched the way oasdiff does it. Detects narrowed parameter enums. Adds undefined security schemes, duplicated or mistyped enums, `array` without `items`, trailing slash and query string in path keys |
| test-writer | Qodo Pro Team $30/mo base (credit-based) | 4 / 1 / 0 / 1 | 3/3 planted gaps. Generated tests: 28 pass, 3/3 mutants killed. Branch and raise counts checked by hand | **AT PAR** for Python | Tracks each raise *site* (one `raises(ValueError)` no longer counts as covering five). Exception classes passed in through `@parametrize` are recognised (the tool used to flag its own generated tests) |
| regex-builder | regex101 (free; Pro price not public); AutoRegex $3.49/mo (third-party listing) | 4 / 2 / 2 / 0 (+1 above) | OWASP evil regexes 9/9 (8/9 before: the real-world email regex was rated "safe"). 10/10 safe patterns, confirmed linear on 20k-character input | **AT PAR** (ABOVE on ReDoS; BELOW on substitution and debugger) | Computes the first characters of a group correctly when its leading atom is optional |
| commit-crafter | No paid comparable. De-facto standard: commitlint + semantic-release + conventional-commits-filter (free) | 8 / 0 / 0 / 1 | 5/5 lint cases and 7/7 SemVer cases match the specs. Changelog bump and entries correct | **AT PAR** | `type:subject` with no space is now invalid, as the spec requires. A commit reverted inside the release range is dropped with its revert |
| incident-commander | incident.io Team $19/user/mo ($15 annual) | 4 / 2 / 0 / 2 (+1 above) | TTD/TTA/TTI/TTM/TTR exact (TTR was 94 min, should be 89). Error budget exact. Postmortem: 6/6 planted problems, clean draft scores 100 | **AT PAR**; ABOVE on SLO math | "Status page" is no longer tagged as detection, and a status-page post no longer counts as the resolution |
| system-design | ByteByteGo URL-shortener chapter (reference answer; price not shown on the fetched page); no paid tool | 5 / 1 / 0 / 0 (+1 above) | Every ByteByteGo number reproduced. Availability, latency, fleet and cache results match hand math | **AT PAR** (ABOVE on quantified reliability) | `id_space`: records over the horizon, base62/base36/hex key length (integer arithmetic), int32/int64 fit |

(M = MATCHES, P = PARTIAL, Miss = MISSING, OOS = OUT OF SCOPE. "Above" = a documented capability we exceed.)

**Totals.** 16 defects found and fixed in the tools, 1 playbook claim tightened (code-reviewer's scan scope), 2 playbooks extended (bug-hunter chain semantics, test-writer raise sites). No agent is BELOW on its core overlapping job after the fixes. Where a BELOW remains, it is breadth: linter/SCA suites, dataflow analysis, oasdiff's long tail of checks. None of those can be fixed cheaply in deterministic stdlib code.

**Test runs.**
- `pytest -q tests/agents -k engineering tests/scenarios/test_engineering.py`: **219 passed**
- `pytest -q tests/test_library.py`: **303 passed**

---

## 1. code-reviewer (vs CodeRabbit)

**Scenario.** "Review PR #218: nightly invoice export to S3." Two new files, 128 lines:
- `app/billing/invoice_export.py` has 5 planted defects:
  - L23: fake AWS key id and secret inside `boto3.client(...)`
  - L28: f-string SQL injection
  - L30: debug `print` of customer ids
  - L37: `verify=False`
  - L62: `except Exception: pass` around the S3 upload
- `app/billing/money.py` is clean (Decimal with ROUND_HALF_EVEN, parameterised query).

**Checklist.** Sources: [docs.coderabbit.ai](https://docs.coderabbit.ai/) (bugs, security, "leaked secrets", "vulnerable dependencies", one-click fixes, learns from feedback) and [docs.coderabbit.ai/tools](https://docs.coderabbit.ai/tools/) (50+ tools including Ruff, ESLint, Betterleaks).

| # | CodeRabbit capability | Status | Why |
|---|---|---|---|
| 1 | Bug detection in the diff | MATCHES | 5/5 planted defects located to the line; `score_review` gives Request changes |
| 2 | Security vulnerabilities | MATCHES (after fix) | SQL built from strings and TLS-off are blockers. Before the fix only the host AI's reading would catch them |
| 3 | Leaked-secret detection | PARTIAL | Reuses the security-auditor's 23 detectors with redaction. Far fewer rules than a gitleaks-class scanner |
| 4 | 50+ linters/SAST tools run | PARTIAL | Regex smell scan + Python AST complexity. Ruff/ESLint are not executed |
| 5 | Vulnerable dependencies | MISSING | No dependency (SCA) data |
| 6 | Summary / walkthrough | MATCHES | `diff_stats` (size class, risk flags, review order) + the playbook's Summary |
| 7 | One-click fixes | PARTIAL | Every blocker and major carries concrete code. Applying it in the repo is out of scope |
| 8 | Learns from team feedback | MISSING | No per-team memory |
| 9 | Runs automatically on each PR, posts comments | OUT OF SCOPE | Repo integration |

**Correctness.**

| Check | Result |
|---|---|
| Recall on planted defects | 5/5 (before the fix: 2/5, only print and swallowed exception) |
| Findings on the clean `money.py` | 0 |
| Precision on real code (10 stdlib modules, 10,343 lines as a new-file diff) | 0 SQL/credential blockers. 4 TLS hits, all inside `ssl.py`'s own `_create_unverified_context` / `cert_reqs=CERT_NONE`: true constructs, fine in a library |
| Secret echo | Before: the "long line" smell printed the full AWS secret. After: `AKIA…(20 chars)`, `fAkE…(40 chars)` |
| Verdict rule | 3 blockers + 4 majors gives Request changes. Flagged one major missing a failure scenario, which was then fixed |

**Deliverable excerpt.**
```
## Review: app/billing/invoice_export.py — Request changes
**Size:** L, 2 files, +128/−0 · **Est. review time:** 19 min · **Tests:** MISSING

### Summary
Adds a nightly per-customer invoice CSV export to S3 plus a Money helper. The approach is fine,
but the export ships three security blockers (SQL injection, committed AWS keys, TLS off) and
reports success when the upload fails. money.py is the pattern the exporter should reuse.

### Blocking
- `invoice_export.py:28` — **issue (blocking):** customer_id/status are f-string'd into SQL; a crafted
  id (' OR '1'='1) returns every customer's invoices → `cur.execute("… WHERE customer_id = %s AND status = %s", (customer_id, status))`
- `invoice_export.py:23` — **issue (blocking):** AWS key id + secret committed (AKIA…(20 chars)); anyone
  with repo read can use them → rotate now, `boto3.client("s3")` with the instance role, purge history, add gitleaks
- `invoice_export.py:37` — **issue (blocking):** `verify=False` lets a MITM return a fake FX rate → drop it or pass the CA bundle
### Should fix before merge
- `invoice_export.py:62` — **issue:** `except Exception: pass` makes export_all log success when nothing uploaded → log.exception + re-raise
- `invoice_export.py:43` — **issue:** fx_rate is called per row (one HTTP call per invoice) → fetch once per currency
- `invoice_export.py:30` — **issue:** print() of customer ids → log.debug without the id
- **issue:** 128 new lines, no tests → render_csv (EUR/non-EUR), put_object raising, fetch_invoices with a stub cursor
### Praise
- **praise:** money.py keeps integer minor units and ROUND_HALF_EVEN at the boundary, with a parameterised query.
```
What flips the verdict to Approve: the three blockers and four majors fixed with the suggested code.

**Honest gaps.**
- The scan is pattern-based. SQL built inside a helper in another file, a missing authZ check, or an unsafe ORM `.raw()` fed from elsewhere is found only if the host AI reads for it. The playbook now says so explicitly.
- No real linters run and no dependency scanning (MISSING vs CodeRabbit).

**Traps in the scenario.**
- The AWS secret shares a line with the key id, so any tool that echoes context leaks it. Our own tool did until the fix.
- `except …: pass` spans two lines, so single-line greps miss it (the scanner handles this).

---

## 2. security-auditor (vs Snyk Code + GitGuardian)

**Scenario.** "Security review of this export job before it goes to prod," using the planted file above. Also: score the CVEs, and grade the headers from `curl -I`.

**Checklist.** Sources:
- Snyk Code does "source to sink" dataflow/taint analysis with CWE-keyed fix examples, and covers 12 languages ([docs.snyk.io Snyk Code](https://docs.snyk.io/scan-with-snyk/snyk-code), [Agent Fix](https://docs.snyk.io/scan-with-snyk/snyk-code/manage-code-vulnerabilities/fix-code-vulnerabilities-automatically)).
- GitGuardian has hundreds of specific detectors plus 23 generic ones, and runs validity checks ([supported credentials](https://docs.gitguardian.com/secrets-detection/secrets-detection-engine/detectors/supported_credentials)).
- CVSS reference: NVD API.

| # | Capability | Status | Why |
|---|---|---|---|
| 1 | SAST source→sink taint analysis | PARTIAL | Line-level CWE lint + the host AI traces input to sink. No interprocedural dataflow |
| 2 | CWE mapping | MATCHES | Every rule carries a CWE |
| 3 | Fix guidance | MATCHES | Class-level fixes (parameterise, allow-list, `yaml.safe_load`…) |
| 4 | Secret detection breadth | PARTIAL | 23 detectors (AWS, GitHub, GitLab, Slack, Stripe, Google, OpenAI, Anthropic, SendGrid, npm, PyPI, HF, JWT, private keys, DB URLs, 2 generic) vs hundreds |
| 5 | Secret validity check | OUT OF SCOPE | Needs calls to provider APIs |
| 6 | Never exposes the secret | MATCHES (after fix) | Every secret on the line is redacted in every finding's context |
| 7 | Severity scoring | MATCHES | CVSS 3.1 exact on 10/10 NVD vectors |
| 8 | Vulnerable dependencies (SCA) | MISSING | No advisory database |
| 9 | Language coverage | PARTIAL | Python, JS/TS, Go, Java, PHP, Ruby, shell rules. No C/C++/C#/Swift/Apex |

**Correctness.**

| Check | Result |
|---|---|
| Secrets in the planted file | 2/2 (AWS key id, AWS secret), both high-confidence, line 23. Clean file: 0 |
| Secret leak | **Before:** the key-id finding's `context` printed the full 40-character secret. **After:** neither value appears anywhere in the output (asserted) |
| Lint on planted / clean | CWE-89 at L28 and CWE-295 at L37 / 0 findings |
| Indirect SQL (probe) | Before: an f-string built on its own line, and `.format()` in a helper, were **missed**. After: caught, including JS template literals. No false positive on parameterised queries or on `log.info(f"… {n} rows")` |
| CVSS vs NVD | 10/10 exact. Log4Shell CVE-2021-44228 10.0; Heartbleed CVE-2014-0160 7.5; Spring4Shell CVE-2022-22965 9.8; CVE-2020-11022 6.1 (NVD) and 6.9 (GitHub CNA); CVE-2019-11043 8.7 (PHP CNA); CVE-2021-3156 7.8; CVE-2019-5736 8.6; CVE-2018-11776 8.1; CVE-2021-41773 7.5 (Apache CNA). Covers AV:L, AC:H, PR:L, UI:R, S:C and mixed C/I/A |
| Headers (nginx/Express sample) | Grade F: unsafe-inline + `https:` in script-src, HSTS max-age 86400, no frame-ancestors, no nosniff, session cookie without Secure/SameSite, `Server: nginx/1.18.0` version leak. All correct |

**Deliverable excerpt.**
```
# Security review: app/billing/invoice_export.py — 2026-09-27
**Scope:** 1 file · **Exposure:** internal batch job, reads customer ids from the admin API · **Data:** invoices (PII, amounts)
**Summary:** 1 critical, 2 high, 0 medium, 0 low, 1 hardening

### [CRITICAL] Committed AWS credentials — CWE-798 — rotate now (not CVSS-scored: live credential = P0)
**Where:** `invoice_export.py:23` — AKIA…(20 chars) / fAkE…(40 chars)
**Fix:** rotate/revoke → boto3.client("s3") with the task role → git filter-repo → gitleaks pre-commit + CI
### [HIGH] SQL injection in fetch_invoices — CWE-89 — CVSS 8.8 (CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H)
**Repro:** 1. POST /admin/exports {"customer_id": "x' OR '1'='1"} 2. CSV contains every customer's invoices
**Fix:** cur.execute("… WHERE customer_id = %s AND status = %s", (customer_id, status)) · **Class fix:** ban f-strings in execute (ruff S608)
### [HIGH] TLS verification disabled on FX call — CWE-295 — CVSS 7.4 (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N)
**Fix:** remove verify=False; pin the internal CA bundle
## Hardening
- `except Exception: pass` hides upload failures (availability/integrity of the export, not exploitable)
## Not reviewed / assumptions
- dependency versions (no SCA), IAM policy of the bucket, the admin API's authZ
```

**Honest gaps.**
- BELOW Snyk on dataflow: a tainted value that crosses functions or files is found only if the host AI traces it.
- No dependency (SCA) scanning.
- Secret coverage is roughly an order of magnitude smaller than GitGuardian's.

**Traps in the scenario.**
- Two secrets on one line (the leak).
- CNA and NVD vectors differ for the same CVE (CVE-2020-11022: 6.9 vs 6.1). The report must state which vector it scored.

---

## 3. bug-hunter (vs Sentry Seer)

**Scenario.** "Checkout 500s since the 14:02 deploy. Here's the traceback, a Node trace from the invoice service, and 400 lines of logs. What's wrong?" Inputs:
- A Flask traceback with *implicit* chaining: a KeyError cache miss, then "During handling…", then AttributeError on `None.amount_cents` in `repo.py:56`.
- A Node trace with `at async` frames.
- A seeded 400-line log containing a deploy line before the first error.

**Checklist.** Sources: [Seer](https://docs.sentry.io/product/ai-in-sentry/seer/) (errors, stack traces, traces/spans, logs, linked repo code, profiles) and [Autofix](https://docs.sentry.io/product/ai-in-sentry/seer/autofix/) (root cause → editable solution plan → diffs → PR → iterates on CI).

| # | Seer capability | Status | Why |
|---|---|---|---|
| 1 | Root cause from error + stack trace | MATCHES (after fix) | Blame frame `repo.py:56 fetch_price`. The implicit chain is now read correctly: the final AttributeError is the bug, not the handled KeyError |
| 2 | Uses logs | MATCHES | Templates, counts, first-seen order, and the deploy that preceded the first error |
| 3 | Traces/spans/profiles | OUT OF SCOPE | No telemetry access |
| 4 | Relevant code from linked repos | OUT OF SCOPE | The host AI reads the code |
| 5 | Suspect changes | PARTIAL | `rank_suspects` needs the changed-file list from the user; Seer pulls commits itself |
| 6 | Editable solution plan, add regression tests | MATCHES | Playbook: ranked hypotheses with a falsifying test, fix at the cause, regression test |
| 7 | Code diffs / PR / CI iteration | OUT OF SCOPE | Repo integration |
| 8 | Bisect planning | ABOVE | `bisect_plan`: 137 commits → 8 steps, 32 min. Not documented for Seer |

**Correctness.**

| Check | Expected (how verified) | Tool |
|---|---|---|
| Python blame frame | repo.py:56 (read off the trace) | ✓ |
| Python root exception | AttributeError (implicit chain) | ✓. Was **KeyError** before the fix, with the note "fix that, not the outer one", which is wrong |
| Explicit chain (`raise … from`) | KeyError first | ✓ |
| Node frames | 5 (format.js:23, build.js:57, service.js:112, routes/invoices.js:34, express layer.js:95) | ✓. Was 3, one parsed as file `async /app/…` |
| Log levels | 278 INFO / 92 ERROR / 30 WARN (independent Counter) | ✓ |
| First error line / deploy line | 80 / 75 (independent scan) | ✓, and the deploy is now named in the verdict |
| Busiest error minute | 14:08 with 15 errors (`cut \| sort \| uniq -c`) | ✓ |
| Bisect steps for 137 commits | ceil(log2 137) = 8 | ✓ |
| Suspect ranking | repo.py > pricing.py > migration | ✓ |

**Deliverable excerpt.**
```
## Diagnosis: Top hypothesis — fetch_price returns None for regions with no DB price row; the cache-miss fallback path added in pricing-service 2026.09.21-3 dereferences it (unconfirmed)
**Error:** `AttributeError: 'NoneType' object has no attribute 'amount_cents'` · **Blame frame:** `/srv/app/checkout/repo.py:56 in fetch_price` · **Family:** data
### What the evidence says
- Implicit chain: KeyError ('SKU-1042','eu-west') was being handled → the fallback itself failed → the fallback is the bug
- First ERROR at line 80 (14:02:08), 7s after "deploy pricing-service version=2026.09.21-3" (line 75) → regression
- 30 WARN "cache miss … region=eu-west falling back to db" → only eu-west misses → data-dependent
### Hypotheses (ranked)
1. **eu-west prices missing from the prices table; fetch_price assumes a row** — test: `SELECT count(*) FROM prices WHERE region='eu-west'`
2. **new cache build skips eu-west** — test: dump cache keys for SKU-1042 on one pod
### Reproduce
`pytest tests/test_repo.py::test_fetch_price_missing_region_raises_price_not_found`
### Fix
fetch_price raises PriceNotFound (→ 409/422 to the client) instead of returning None; backfill eu-west prices
**Blast radius:** any caller of fetch_price for a new region · **Unexplained:** why the cache lost eu-west (check the deploy diff)
```

**Honest gaps.**
- No live telemetry, and no automatic commit or suspect discovery. Seer's advantage is that it sees traces and commits without being asked.
- The log template masking merges different HTTP status codes into one template (split by level only).

---

## 4. sql-wizard (vs AI2sql / EverSQL-Aiven optimizer)

**Scenario.** "This dashboard query takes 38 s on 24M orders. What's wrong and what index fixes it?" It contains three planted traps: `DATE(o.created_at) = …` (non-sargable), `NOT IN (SELECT r.customer_id FROM refunds r)` over a nullable column, and a LEFT JOIN cancelled by `WHERE c.country = 'DE'`. A second query, written in lowercase, has four more: leading-wildcard LIKE, `lower()`, `extract(year from …)`, and `select *`.

**Checklist.** Sources: [AI2sql pricing/features](https://www.ai2sql.io/pricing) (generation, explanation, error fixing, optimisation on Pro, 7 databases, live DB on Pro) and [Aiven SQL optimizer](https://aiven.io/tools/sql-query-optimizer) (index recommendations + rewrites, PostgreSQL/MySQL, manual upload of SQL + metadata).

| # | Capability | Status | Why |
|---|---|---|---|
| 1 | NL → SQL | MATCHES | Host AI writes it; the tools lint, format and index it |
| 2 | Explain a query | MATCHES | `explain_structure` (tables, joins, CTEs, grain hint) |
| 3 | Fix syntax errors | PARTIAL | The tokenizer catches unterminated strings and bad characters only; no grammar |
| 4 | Index recommendations | MATCHES (after fix) | ESR order; anti/semi-join lookup index |
| 5 | Rewrites with change notes | MATCHES | Each lint finding carries its rewrite; before→after verified on a real engine |
| 6 | Dialect breadth | PARTIAL | PG/MySQL/SQLite/SQL Server/BigQuery notes; no Oracle/Snowflake specifics |
| 7 | Uses schema/EXPLAIN metadata | PARTIAL | The AI reads EXPLAIN; no plan parser or cost model |
| 8 | Live DB connection | OUT OF SCOPE | |

**Correctness.**

| Check | Result |
|---|---|
| Query 1 traps | 3/3, no extras |
| Query 2 traps | Before: 2/4. Lowercase `lower(...)` was not recognised; `extract(year from …)` and `date_trunc('month', col)` never matched; only the first non-sargable predicate was reported. After: 4/4 |
| Rewrite (NOT EXISTS, sargable range, INNER JOIN with the country in ON) | Lints clean |
| Index advice, before | `orders (status, customer_id, created_at)`: the NOT IN column wrongly used as an equality prefix, which kills the ORDER BY. No refunds index |
| Index advice, after | `orders (status, created_at)` + `refunds (customer_id)`; duplicates removed |
| Independent sqlite3 run | Original returns **[]** (NULL in `refunds.customer_id`). Rewrite returns `[(10, 1, 500, 'a@x.de')]`. EXPLAIN shows `status=? AND created_at>? AND created_at<?` |
| Existing unit test | Its own query contained `lower(u.email) like …`, which the old linter silently missed. Assertion updated |

**Deliverable excerpt.**
```
**Grain:** one row per order · **Dialect:** PostgreSQL (assumed) · **Assumptions:** orders.customer_id → customers.id
SELECT o.id, o.customer_id, o.total_cents, c.email
FROM orders o
JOIN customers c
    ON c.id = o.customer_id
    AND c.country = 'DE'          -- WHERE on c already made the LEFT JOIN inner; say so
WHERE o.created_at >= '2026-09-01'
    AND o.created_at < '2026-09-02'   -- sargable replacement for DATE(created_at) = …
    AND o.status = 'paid'
    AND NOT EXISTS (SELECT 1 FROM refunds r WHERE r.customer_id = o.customer_id)  -- NOT IN + a NULL row returned nothing
ORDER BY o.created_at DESC
LIMIT 50;
**Correctness notes:** the original returns ZERO rows as soon as refunds has one NULL customer_id.
**Indexes:** CREATE INDEX CONCURRENTLY idx_orders_status_created_at ON orders (status, created_at); -- equality + sort/range
             CREATE INDEX CONCURRENTLY idx_refunds_customer_id ON refunds (customer_id);         -- anti-join probe
**Before → after:** index on status only + filter on DATE() → Index Scan on (status, created_at) range, ~1 day of paid orders
```

**Honest gaps.**
- No grammar-level parser, no cost model.
- The index advisor treats the first FROM table as the driving table.

---

## 5. api-designer (vs Stoplight/Spectral + oasdiff)

**Scenario.** "We're shipping Orders API v2. Is it breaking? Also lint the spec before publishing." v1 → v2 carries six planted breaking changes and four non-breaking ones.

Planted breaking changes:
- **B1:** `legacy_id` removed from Order
- **B2:** `total_cents` changed from integer to string
- **B3:** new required request field `channel`
- **B4:** currency enum loses GBP
- **B5:** new required query parameter `region`
- **B6:** `DELETE /orders/{orderId}` removed

Non-breaking noise:
- `{orderId}` renamed to `{id}`
- optional `updated_at` added
- optional `status` filter added
- new `/orders/{id}/events` endpoint

For the lint, a second variant of the spec carries six planted Spectral violations.

**Checklist.** Sources: the [Spectral OAS ruleset](https://raw.githubusercontent.com/stoplightio/spectral/develop/docs/reference/openapi-rules.md), [oasdiff breaking changes](https://github.com/oasdiff/oasdiff/blob/main/docs/BREAKING-CHANGES.md), [oasdiff endpoint matching](https://github.com/oasdiff/oasdiff/blob/main/docs/MATCHING-ENDPOINTS.md) ("By default, the matching algorithm **ignores** path parameter names") and [oasdiff pricing](https://www.oasdiff.com/pricing).

| # | Capability | Status |
|---|---|---|
| 1 | operation-operationId / -unique | MATCHES |
| 2 | operation-success-response | MATCHES |
| 3 | path-params (declared/required) | MATCHES |
| 4 | operation-tags | MATCHES |
| 5 | oas3-operation-security-defined | MATCHES (after fix) |
| 6 | duplicated-entry-in-enum, typed-enum, array-items | MATCHES (after fix) |
| 7 | path-keys-no-trailing-slash, path-not-include-query | MATCHES (after fix; these existed only for endpoint lists) |
| 8 | oas3-schema structural validation, valid examples | MISSING |
| 9 | oasdiff core: removed operation, new required parameter/field, removed response property, type change, enum value removed, path-parameter rename ignored | MATCHES (after fix) |
| 10 | oasdiff breadth (hundreds of checks: max-length, pattern, content type, security…) | PARTIAL |
| 11 | Hosted docs, mocks, visual editor | OUT OF SCOPE |

**Correctness.**

| Check | Before fix | After fix |
|---|---|---|
| Planted breaking changes found | 4/6 root changes. The rename made `GET /orders/{orderId}` look "removed" (false positive), hiding B1/B2 on that endpoint | 6/6 (10 occurrences across the 3 operations sharing `Order`), **0 false positives**, rename reported as a note |
| Additive changes | rename also reported as "operation added" (false positive) | 3/3 (events endpoint, status parameter, updated_at) |
| Spectral-style planted issues | 2/6 | 6/6 |
| Clean v2 spec score | 100 | 100 |

**Deliverable excerpt.**
```
# Orders API — review of v2.0.0 against v1.4.0
**Verdict:** 10 breaking occurrences from 6 changes → major (publish as /v2 or add a deprecation path) · spec lint 100/100
| Breaking change | Where | Client impact | Non-breaking alternative |
|---|---|---|---|
| operation removed | DELETE /orders/{orderId} | 404/405 for cancel | keep it, add Deprecation/Sunset headers |
| new required query param | GET /orders ?region | every existing list call 400s | optional with default = caller's home region |
| new required request field | POST /orders body.channel | existing creates 422 | optional, default "api" |
| request enum value removed | POST /orders body.currency (GBP) | GBP orders rejected | keep GBP, reject at business-rule level with problem+json |
| response field removed ×3 | legacy_id in list/get/create | clients read undefined | keep, mark deprecated |
| response field type changed ×3 | total_cents integer→string | strict decoders fail | add total_cents_str, keep the integer |
Note: /orders/{orderId} → /orders/{id} is a rename only — not breaking on the wire (oasdiff agrees).
```

**Honest gaps.**
- JSON input only; the host AI converts YAML first.
- No JSON-schema validation of the document itself.
- oasdiff's long tail of checks is not replicated (for example `maxLength` lowered, `pattern` tightened, response media type removed).

---

## 6. test-writer (vs Qodo)

**Scenario.** "Write the missing tests for durations.py; here's the existing test file." The existing tests have three planted gaps:
- `format_duration` has no tests
- the TypeError path is never asserted
- `test_parse_duration_smoke` has no assertion

**Checklist.** Sources: [Qodo testing](https://www.qodo.ai/solutions/testing/) and [qodo-cover](https://github.com/qodo-ai/qodo-cover): behaviour-based generation; edge cases (null, empty, boundaries, unicode, long input, type mismatch); behaviour coverage; runs the tests and iterates on coverage.

| # | Capability | Status | Why |
|---|---|---|---|
| 1 | Tests with meaningful assertions | MATCHES | 28 generated cases pass; 3/3 mutants killed |
| 2 | Edge-case catalogue | MATCHES | `edge_case_matrix` covers boundaries, empty/None, unicode, long input, type confusion |
| 3 | Behaviour coverage (untested paths) | MATCHES (after fix) | Tracks each raise site, not only each exception type |
| 4 | Happy / edge / rare structure | MATCHES | Playbook file order and tiers |
| 5 | Runs tests and iterates on coverage | OUT OF SCOPE | Execution in the customer's repo; the host AI can run pytest |
| 6 | Many languages | PARTIAL | Tools are Python-only; the playbook covers Jest/Go/JUnit conventions |

**Correctness.**

| Check | Result |
|---|---|
| Branch counts | parse_duration 7, format_duration 4 (counted by hand); minimum tests 10 / 6 |
| Planted gaps | 3/3 |
| Raise sites | Before: one `raises(ValueError)` on `"abc"` counted as covering all 5 ValueError sites. After: 5 sites reported as not pinned by `match=` |
| Tests generated through the tool's own `parametrize_block` | Before: flagged "ValueError never asserted" (a false positive on its own output, since `pytest.raises(exc)`'s `exc` comes from parametrize). After: 0 gaps |
| Execution | 28 passed in a clean temp dir |
| Mutants | `>` → `>=` on the limit: killed. Repeated-unit check deleted: killed. `if n:` → `if n or True:`: killed |

**Deliverable excerpt.**
```
## Test plan for durations
| # | Case | Input | Expected | Tier |
| 1 | hours+minutes | "1h30m" | 5400 | must |
| 2 | trims + lowercases | "  1H " | 3600 | must |
| 3 | exactly max | "30d" | 2592000 | must |
| 4 | one over max | "30d1s" | ValueError("too long") | must |
| 5 | repeated unit | "1h1h" | ValueError("repeated") | must |
| 6 | whitespace only | "   " | ValueError("empty") | must |
| 7 | not a string | None | TypeError("string") | must |
| 8 | round trip | 0…2592000 | parse(format(x)) == x | should |
@pytest.mark.parametrize("text, exc, match", [
    pytest.param('', ValueError, 'empty', id='-raises-ValueError'),
    pytest.param('1h1h', ValueError, 'repeated', id='1h1h-raises-ValueError'),
    pytest.param('30d1s', ValueError, 'too long', id='one-over-max'),
    pytest.param(None, TypeError, 'string', id='raw_None-raises-TypeError'), …])
def test_parse_duration_raises(text, exc, match):
    with pytest.raises(exc, match=match):
        parse_duration(text)
**Determinism:** pure functions, nothing to stub · **Not covered:** locale-specific digits (by design, ASCII only)
```

**Honest gaps.**
- Static analysis only; there is no coverage-guided loop.
- Python-only tooling.
- The auto-generated id for the empty string is `-raises-ValueError` (readable, but not pretty).

---

## 7. regex-builder (vs regex101 / AutoRegex)

**Scenario.** "Validate order ids like ORD-2026-000123 (year 20xx, 6 digits) on user input in our Node API." Also: "is the email regex we copied from RegExLib safe?"

**Checklist.** Sources: [regex101 docs](https://docs.regex101.com/) (engine choice, explanation, match/groups, substitution, unit tests; Pro adds debugger, benchmark, multiple strings; code generation) and [OWASP ReDoS](https://community.owasp.org/attacks/Regular_expression_Denial_of_Service_-_ReDoS).

| # | Capability | Status | Why |
|---|---|---|---|
| 1 | Engine/flavour choice | PARTIAL | Matching runs on Python's engine only; `convert_flavor` produces JS/PCRE/Java/Go with caveats |
| 2 | Explanation | MATCHES | Token table |
| 3 | Match info / groups | MATCHES | Spans, groups, named groups |
| 4 | Substitution | MISSING | No replace mode |
| 5 | Unit tests | MATCHES | should_match / should_not_match with failure hints |
| 6 | Debugger (Pro) | MISSING | |
| 7 | Catastrophic-backtracking detection | ABOVE (after fix) | Static analysis catches 9/9 OWASP patterns before running; sandboxed 1 s timeout on top |
| 8 | Code generation | PARTIAL | The host AI writes it |
| 9 | NL → regex (AutoRegex) | MATCHES | Host AI + playbook examples-first procedure |

**Correctness.**

| Check | Result |
|---|---|
| OWASP evil set: `(a+)+`, `([a-zA-Z]+)*`, `(a\|aa)+`, `(a\|a?)+`, ReGexLib email, Java classname, plus 3 more | Before: 8/9, and the **real-world email regex was rated "safe"**. After: 9/9 "dangerous" |
| Empirical check of that email regex (child process, no project code) | 0.005 s → 0.13 s → 1.3 s for 16/20/24 × 'a' + '!' (exponential) |
| 10 linear patterns | 10/10 "safe"; all run in well under 10 s combined on 20k-character adversarial input in a subprocess |
| ORD task | First draft `\AORD-20\d{2}-\d{6}\Z` scores 10/11: `\d` accepts Arabic-Indic digits `٠٠٠١٢٣`. Final `[0-9]` scores 11/11. JS conversion `^ORD-20[0-9]{2}-[0-9]{6}$` is correct, since JS `$` has no trailing-newline allowance without `m` |

**Deliverable excerpt.**
```
**Pattern (JavaScript):** `^ORD-20[0-9]{2}-[0-9]{6}$` · **Flags:** none · **Mode:** fullmatch (test())
**Safety:** safe — no repeats over overlapping sets; still cap input at 64 chars before matching
| Sample | Expected | Result |
| ORD-2026-000123 | match | ✓ |
| ORD-2026-00123 | no | ✓ (5 digits) |
| ord-2026-000123 | no | ✓ (case) |
| ORD-2026-000123\n | no | ✓ (trailing newline) |
| ORD-2026-٠٠٠١٢٣ | no | ✓ ([0-9], not \d) |
**Notes:** Python's \d is Unicode — the first draft let Arabic-Indic digits through.
Your RegExLib email regex is DANGEROUS: (([\-.]|[_]+)?([a-zA-Z0-9]+))* — the optional separator lets
iterations split a run of letters many ways; 24 chars + '!' takes 1.3 s and doubles every ~char.
```

**Honest gaps.**
- No substitution mode and no step debugger.
- Testing happens only in Python's engine, so flavour differences are described in the conversion caveats but not executed.

---

## 8. commit-crafter (vs commitlint + semantic-release, free de-facto standard)

**Scenario.** "Lint these messages and cut the release from these 12 commits since v1.9.3." The history includes a merge, a non-conventional commit, `feat:add …` with no space, a `BREAKING CHANGE:` footer, and a feat that is reverted within the same range.

**Checklist.** Sources: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) ("REQUIRED terminal colon and space"; `BREAKING CHANGE` / `BREAKING-CHANGE` / `!`), [commitlint rules](https://commitlint.js.org/reference/rules.html) (type-enum with the 11 Angular types, body-leading-blank, subject-case, breaking-change-exclamation-mark), [SemVer 2.0.0](https://semver.org/) §11, and [conventional-commits-filter](https://github.com/conventional-changelog/conventional-changelog/tree/master/packages/conventional-commits-filter) ("Filter out reverted commits").

| # | Capability | Status |
|---|---|---|
| 1 | type-enum (11 types, case-insensitive) | MATCHES |
| 2 | Header length (72 hard limit; commitlint's is configurable) | MATCHES |
| 3 | subject-case / full-stop / body-leading-blank | MATCHES |
| 4 | breaking-change-exclamation-mark consistency | MATCHES (warning) |
| 5 | Header grammar: colon **and space** | MATCHES (after fix) |
| 6 | Bump rules: breaking → major, feat → minor, fix/perf/revert → patch; 0.x convention | MATCHES |
| 7 | Reverted commits dropped from the release | MATCHES (after fix) |
| 8 | SemVer pre-release arithmetic and precedence | MATCHES |
| 9 | Tag, publish, GitHub release | OUT OF SCOPE |

**Correctness.**

| Case | Spec says | Before | After |
|---|---|---|---|
| `feat:add login` | invalid (colon + space required) | **valid, minor** | invalid; fixed header `feat: add login`; left out of the changelog as non-conventional |
| `BREAKING-CHANGE:` footer on a chore | major | major | major |
| 1.0.0-beta.9 prerelease | 1.0.0-beta.10 (numeric precedence) | ✓ | ✓ |
| 0.9.4 major | 0.10.0 by the 0.x convention (flagged in notes) | ✓ | ✓ |
| Release from 12 commits | 2.0.0. The a1b2c3d feat is reverted by 5e6f7a8, so both are dropped | 2.0.0, but listed "Add cursor pagination" **and** "Feat(api): add cursor pagination" | 2.0.0, 5 entries, both dropped, with a note |

**Deliverable excerpt.**
```
## Release 2.0.0 (bump: major)
## [2.0.0] - 2026-09-27
### ⚠ BREAKING CHANGES
- **export:** The export endpoint now returns 202 with a job URL instead of the file body. (0a1b2c3)
### Added
- **export:** Stream CSV exports to S3 (0a1b2c3)
### Changed
- **db:** Batch price lookups in cart_total (c3d4e5f)
### Fixed
- **auth:** Reject expired refresh tokens (b2c3d4e)
- Handle empty carts in checkout (2c3d4e5)
Needs manual classification: "Updated readme", "feat:add region header" (missing space after colon).
Left out: a1b2c3d (cursor pagination) was reverted by 5e6f7a8 in this range.
```

**Honest gaps.**
- Commit bodies are not rewritten automatically. The "why" warning relies on a keyword list, so a good body without those words gets a spurious warning.

---

## 9. incident-commander (vs incident.io Team)

**Scenario.** "Here are the Slack timestamps from last night's checkout incident (it crosses midnight). Build the timeline and MTTR, tell me where we are on the 99.9% SLO, and check the postmortem draft." The draft has six planted problems:
- "Maria should have…"
- "human error"
- an action item without an owner
- a vague action item ("Add monitoring")
- an action item without a due date
- no Detection section

**Checklist.** Sources:
- [incident.io pricing](https://incident.io/pricing): Team has a basic post-mortem editor, one status page, and on-call. AI and insights are Pro+.
- [Post-mortem management](https://docs.incident.io/post-incident/postmortem-management): severity, duration, follow-ups, policies with deadlines.
- [Validating incident timestamps](https://help.incident.io/articles/1814235031-validating-incident-timestamps) and [lifecycle](https://docs.incident.io/incidents/lifecycle): duration metrics such as "Time to fix", "Impact Started At".
- [Google SRE workbook](https://sre.google/workbook/alerting-on-slos/): burn-rate windows.

| # | Capability | Status | Why |
|---|---|---|---|
| 1 | Severity levels | MATCHES | Explicit, tunable rules plus response expectations |
| 2 | Timeline with timestamps and time since start | MATCHES | Handles midnight rollover |
| 3 | Duration metrics measured from impact start | MATCHES (after fix) | TTD/TTA/TTI/TTM/TTR |
| 4 | Post-mortem doc (summary, timeline, follow-ups) | MATCHES | Output format plus `check_postmortem` |
| 5 | Follow-up tracking and completion reports | PARTIAL | Checks owner and due date; does not track completion |
| 6 | Post-mortem policies and deadlines | PARTIAL | Deadlines per SEV in the response table; not enforced |
| 7 | Status page hosting | OUT OF SCOPE | We draft the updates |
| 8 | Slack-native channel, on-call paging | OUT OF SCOPE | |
| 9 | SLO error budget and burn rate | ABOVE | Not in the Team plan; exact math |

**Correctness.**

| Metric | By hand | Before | After |
|---|---|---|---|
| TTD 23:41→23:47 | 6 | 6 | 6 |
| TTA 23:47→23:52 | 5 | 5 | 5 |
| TTI 23:47→00:18 | 31 | 31 | 31 |
| TTM 23:41→00:24 | 43 | 43 | 43 |
| TTR 23:41→01:10 | **89** | **94** (the 01:15 status-page post was taken as the resolution, and "status page" was tagged as detection) | 89 |
| Comms gap | 00:31→01:10 = 39 m | ✓ | ✓ |
| Budget, 99.9% over 30 d | 43.2 min | ✓ | ✓ |
| 38,480 bad of 52M requests | 74.0% consumed, 11.2 min left | ✓ | ✓ |
| Burn rate at day 21 | 0.74 / 0.7 = 1.06×; exhausts day 28.4 | ✓ | ✓ |
| Burn-rate alert thresholds | 14.4×/1h/2%, 6×/6h/5%, 1×/3d/10% (SRE workbook) | ✓ | ✓ |
| Postmortem planted problems | 6 | 6/6 | 6/6 |
| Clean postmortem | no flags | 100/100, no blame flags | same |

**Deliverable excerpt.**
```
# Postmortem: Checkout errors after pricing deploy — 2026-09-21 — SEV1
**Duration:** 23:41–01:10 UTC (89 min) · TTD 6m · TTA 5m · TTI 31m · TTM 43m · TTR 1h 29m (all from impact start)
## Impact
30% of checkout attempts failed for 43 min; 38,480 failed requests = 74.0% of the 30-day 99.9% budget
(11.2 min left, burn 1.06× → exhausts on day 28 of 30: freeze risky changes, reliability work this sprint)
## Timeline (UTC)
| 23:41 | pricing-service 2026.09.21-3 deployed (canary skipped) | impact start |
| 23:47 | PagerDuty 5xx alert | detected |
| 23:52 | @maria acknowledged, IC @dev | acknowledged |
| 00:18 | traced to missing eu-west prices in the new cache | identified |
| 00:24 | rolled back to 2026.09.21-2 | mitigated |
| 01:10 | 5xx at baseline 30 min — resolved | resolved |
⚠ 39 min without an update between 00:31 and 01:10 (SEV1 cadence is 30 min)
## Root cause(s) and contributing factors
Region list duplicated in a config file drifted from the database; the canary skip flag removed the one check that would have caught it.
## Action items
| 1 | Warm-up reads regions from the DB | prevent | @liam | 2026-10-10 | P1 |
| 2 | Alert on per-region price-cache misses > 1% | detect | @maria | 2026-10-03 | P1 |
```

**Honest gaps.**
- Milestone tagging is keyword-based. Unusual phrasing, such as "we flipped it off", may need an explicit "mitigated" line. The tool reports untagged milestones in `notes`.

---

## 10. system-design (vs ByteByteGo reference answer)

**Scenario.** "Design a URL shortener: 100M new URLs/day, 10:1 read/write, 10 years, 100-byte records." This is ByteByteGo's own worked example, so every number has a published answer.

**Checklist.** Source: [ByteByteGo "Design a URL shortener"](https://bytebytego.com/courses/system-design-interview/design-a-url-shortener). Quotes: "100 million / 24 /3600 = 1160", "1160 * 10 = 11,600", "365 billion records", "365 billion * 100 bytes = 36.5 TB", and the smallest n with 62ⁿ ≥ 365 billion.

| # | Step | Status | Result |
|---|---|---|---|
| 1 | Write QPS | MATCHES | 1,157.41/s (ByteByteGo rounds to 1,160) |
| 2 | Read QPS | MATCHES | 11,574.07/s (11,600) |
| 3 | Records over 10 years | MATCHES | 365,000,000,000 |
| 4 | Storage | MATCHES | 36.50 TB |
| 5 | Short-code length (62ⁿ) | MATCHES (after fix; was MISSING) | 7 base62 characters. The tool also reports that int32 overflows |
| 6 | High-level choices (301 vs 302, base62 counter vs hash + collision check) | PARTIAL | Written by the host AI; the playbook is generic and doesn't name them |
| 7 | Latency, availability, fleet and cache math | ABOVE | Not in the reference; all checked by hand below |

**Correctness (independent arithmetic).**

| Check | By hand | Tool |
|---|---|---|
| Composite availability: LB 99.99, API 99.5×3, Redis 99.9×2, PG 99.95 | 99.9399% (26.0 min/month) | 99.9399% |
| Fan-out of 20 at p99 | 1−0.99²⁰ = 18.2% | 18.2% |
| p99 bound (3+15+5+40) | 63 ms | 63 ms |
| Fleet for 38k rps at 1.5k/instance, 60% utilisation, +20% growth, 3 AZs, N+1 | ceil(45,600/900) = 51 → 77 → 78 | 78 |
| Cache at 90% hits, 20M × 250 B | 3,800 rps to origin, 6.5 GB, 231.5 refills/s | same |
| `_key_len(62**7)` / `(62**7+1)` | 7 / 8 | 7 / 8 (integer arithmetic, no float-log rounding) |

**Deliverable excerpt.**
```
# URL shortener — design
**Requirements:** shorten (write), redirect (read, p99 < 50 ms), 99.9%+, links never expire · **Assumptions:** 100 B/record, RF 1 for parity with the reference
## Numbers
| Write QPS avg | 1,157 | ×peak factor for provisioning |
| Read QPS avg | 11,574 | redirects are 91% of traffic |
| Records, 10 y | 365 B | → 7 base62 chars; int32 ids overflow → int64 / Snowflake-style |
| Storage, 10 y | 36.5 TB raw (×3 replicated = 109.5 TB) | partition by short code |
## Architecture
client → CDN/LB → stateless API → cache (hot codes) → KV store (code → long URL); id generator → base62
redirect 302 if click analytics matter (301 is cached by browsers and hides clicks)
## Availability & failure modes
composite 99.94% (26 min/month) — weakest link: the single primary DB; add a replica before promising 99.95
```

**Honest gaps.**
- The domain-specific design choices (redirect code, ID generation scheme) come from the host AI's knowledge; the playbook does not prompt for them.

---

## Files changed

**Tools and playbooks**
- `hundred/agents/engineering/security_auditor.py`: new shared helpers `find_secrets_in_line` and `redact_line`; context redaction; new SQL rules (f-string / `.format()` / JS template literal); findings deduplicated per line and CWE.
- `hundred/agents/engineering/code_reviewer.py`: new smells (SQL built from strings, TLS off, provider-key detectors); secret redaction; playbook step 2 clarified.
- `hundred/agents/engineering/bug_hunter.py`: Node frame regex; implicit/explicit chains with `chain_kind`; message-level hints; `changes_before_first_problem`; playbook steps 1–2.
- `hundred/agents/engineering/sql_wizard.py`: `NON_SARGABLE_RE` (case-insensitive, leading arguments, all occurrences); index advisor fixes.
- `hundred/agents/engineering/api_designer.py`: positional path-parameter matching; parameter enum narrowing; Spectral-parity checks.
- `hundred/agents/engineering/commit_crafter.py`: colon-space rule; reverted-pair filtering.
- `hundred/agents/engineering/incident_commander.py`: comms lines no longer become detection/resolution milestones.
- `hundred/agents/engineering/regex_builder.py`: `_branch_first_set` looks past optional leading atoms.
- `hundred/agents/engineering/system_design.py`: `id_space` + `_key_len`; playbook step 2.
- `hundred/agents/engineering/test_writer.py`: raise-site pinning; exception classes resolved from parametrize; playbook step 2.

**Tests**
- `tests/agents/test_engineering_*.py`: one or more unit tests per fix. The sql-wizard classic-traps assertion was updated because its own query's lowercase `lower()` is now caught.
- `tests/scenarios/test_engineering.py`: the 10 scenarios above, 72 checks.

**Not edited: an issue for core/lib.** None found. `hundred.admin brief … | head` raises BrokenPipeError when piped into `head`. That is cosmetic, in `hundred/admin.py`, and outside my scope.
