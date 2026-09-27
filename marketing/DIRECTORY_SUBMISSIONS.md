# Hundred — Directory & Marketplace Submissions

Strategy context: [GO_TO_MARKET.md](GO_TO_MARKET.md) §6.2.

> **⚠ Verify current URL/process before submitting. This applies to every row below.**
> MCP directories are young and change often: submission forms move, some switch
> to ingesting from the official MCP Registry, some add fees or review queues. The
> URLs and processes here are our best knowledge at writing time. Open each site,
> find its current "Submit"/"Add server"/"Publish" path and read its rules before
> submitting. Record what you actually did in the tracker at the bottom.

---

## 1. Master asset kit (prepare once, reuse everywhere)

### 1.1 Names
- **Primary listing:** Hundred: 100 Expert Agents
- **Free listing (keyless):** Hundred Free: Meeting Ops & Copy Editor
- **Short name / slug:** `hundred` (free: `hundred-free`)

### 1.2 Descriptions (≤160 characters, counted)
| Use | Text | Chars |
|---|---|---|
| **Main** | 100 expert AI agents in one MCP URL. Pro playbooks + real calculators, scorers & validators for Claude, ChatGPT, Cursor & VS Code. 2 agents free. | 145 |
| **Free listing** | Free MCP server, no key: Meeting Ops turns transcripts into notes, decisions & owners; Copy Editor flags passive voice, clichés & readability. | 142 |
| **Developer angle** | Expert agents over MCP for code review, SQL, regex, commits, incidents & system design. Deterministic tools, no server-side LLM. Cursor & VS Code. | 146 |
| **Business angle** | Sales, marketing, finance & ops expert agents inside Claude or ChatGPT. Pro playbooks plus exact math tools. Paste one URL. From $4.99/mo. | 138 |

### 1.3 Long description (for directories that allow ~150–300 words)
> **Hundred gives the AI you already use 100 expert agents through one MCP URL.**
>
> Each agent combines a top-practitioner playbook (named frameworks, thresholds, decision rules, an exact output template, common mistakes to avoid) with 3–7 deterministic tools for the parts language models get wrong: arithmetic, statistics, dates, character limits, parsing and rubric scoring.
>
> **12 categories:** Sales, Marketing, Content & Writing, SEO & Growth, Operations, Finance, Engineering, Product & Design, Career & HR, Creators, E-commerce, Legal & Admin.
>
> **Examples:** Cold Email Closer (subject-line scorer, spam check, business-day sequence scheduler) · A/B Test Analyst (two-proportion z-test, power, peeking warning) · Cash Flow Forecaster (13-week forecast, runway) · Code Reviewer (diff stats, complexity) · Resume Optimizer (ATS keyword match vs job description).
>
> **How it works:** paste your URL into Claude (custom connector), ChatGPT (developer mode), Cursor, VS Code, Windsurf, Gemini CLI or Claude Code. No LLM runs on our side: your AI reasons, our tools compute. Agents update centrally.
>
> **Pricing:** Meeting Ops and Copy Editor are free with no key. Paid: $4.99/mo per agent, $14.99/mo for any 5 or a full category, $29.99/mo for everything. 7-day free trial. Founding Member: all agents for $14.99/mo, locked for life, first 500 members.

### 1.4 Tags / categories (use what each directory offers)
Primary: `mcp` · `mcp-server` · `remote-mcp` · `ai-agents` · `productivity` · `claude` · `chatgpt` · `cursor` · `vscode`
Secondary (pick per directory's taxonomy): `sales` · `marketing` · `seo` · `writing` · `finance` · `developer-tools` · `project-management` · `ecommerce` · `career` · `calculators`
Free listing adds: `free` · `no-auth` · `meeting-notes` · `copy-editing`

### 1.5 Visual assets
| Asset | Spec | Notes |
|---|---|---|
| Logo | 512×512 PNG, transparent + solid versions | Most directories |
| Logo (Cline) | 400×400 PNG | [verify] Cline marketplace requirement |
| Icon | 128×128 and 64×64 PNG | Small list views |
| Social/OG card | 1200×630 | Link previews for every listing |
| Screenshots | 1280×800 (16:10) PNG, plus PH gallery size [verify] | Use redacted/demo keys only |
| Demo video | 20–60 s MP4 + YouTube link | "Paste URL → first tool call" |

### 1.6 Screenshot list (capture in this order)
1. **Install in Claude:** custom connector dialog with the URL pasted (key redacted).
2. **Agent in action (Claude):** Cold Email Closer scoring subject lines, tool call visible.
3. **Install in ChatGPT:** developer-mode connector setup [verify current UI].
4. **Install in Cursor:** MCP settings or `mcp.json`, with Hundred tools listed.
5. **Precision proof:** A/B Test Analyst returning p-value + power + peeking warning.
6. **Money proof:** Cash Flow Forecaster 13-week table or Unit Economics output.
7. **Catalog:** grid of all 12 categories / 100 agents.
8. **Pricing:** plans incl. Founding Member with live seat count.
9. *(Free listing)* Copy Editor readability before/after, and Meeting Ops decisions + owners.

### 1.7 Install snippets (verify each host's current format before publishing)
```bash
# Claude Code
claude mcp add --transport http hundred "{MCP_URL}"
```
```jsonc
// Cursor — ~/.cursor/mcp.json (or project .cursor/mcp.json)
{ "mcpServers": { "hundred": { "url": "{MCP_URL}" } } }

// VS Code — .vscode/mcp.json
{ "servers": { "hundred": { "type": "http", "url": "{MCP_URL}" } } }

// Windsurf — ~/.codeium/windsurf/mcp_config.json
{ "mcpServers": { "hundred": { "serverUrl": "{MCP_URL}" } } }

// Gemini CLI — ~/.gemini/settings.json
{ "mcpServers": { "hundred": { "httpUrl": "{MCP_URL}" } } }
```
- **Claude (app/web):** Settings → Connectors → Add custom connector → paste URL. [verify menu path + plan availability]
- **ChatGPT:** enable developer mode, then add the MCP server as a connector/app. [verify menu path + which plans support it]
- One-click buttons for the site: Cursor install deeplink and VS Code install link. [verify URL formats in each product's docs]
- For listings, use `{FREE_MCP_URL}` for the free entry and a placeholder like `https://…/mcp?key=YOUR_LICENSE_KEY` for the paid one. **Never publish a real key.**

### 1.8 Required links
- Website: `{SITE}?utm_source=<directory>&utm_medium=directory`
- Pricing, docs/install, privacy policy, terms, support email, status page (if any)
- GitHub repo (public)
- Contact: a monitored email; many directories and all big-platform reviews ask for one

---

## 2. MCP directories & registries

Priority: **P1** = submit days 1–3 · **P2** = week 2 · **P3** = week 2–4, longer review.

| # | Directory | Where (verify) | How to submit (verify) | What to submit | Pri | Notes |
|---|---|---|---|---|---|---|
| 1 | **Official MCP Registry** | registry.modelcontextprotocol.io | `mcp-publisher` CLI with a `server.json`; namespace verified via GitHub login or DNS for a custom domain | Name, description (Main), version, `remotes` entry with transport + URL; separate entry for the free server | P1 | Several directories and clients ingest from here, so it may populate others automatically. Check the current `server.json` schema and how it represents auth headers/keys. |
| 2 | **Smithery** | smithery.ai | Sign in with GitHub → publish/add a server; supports remote URLs [verify current flow for externally hosted servers] | Main + free listing, tags, logo, config schema for the license key if supported | P1 | Large MCP audience; has its own install flow. Check how it handles user-supplied keys. |
| 3 | **mcp.so** | mcp.so | "Submit" on site (historically a GitHub issue on the site's repo) | Name, description, repo URL, server URL, tags | P1 | High-volume listing site. |
| 4 | **PulseMCP** | pulsemcp.com | Submit form (pulsemcp.com/submit historically); also ingests the official registry | Main + free; repo; site | P1 | Also runs a weekly newsletter. Pitch the "100 in 100 days" story for inclusion. |
| 5 | **Glama** | glama.ai/mcp/servers | Indexes public GitHub repos; "Add server"/claim flow; separate listing for remote/hosted connectors [verify] | Repo link, claim ownership, logo, description | P1 | Ensure the repo README has a clear install section; Glama scores repos on it. |
| 6 | **mcpservers.org** | mcpservers.org | Submit form on site [verify if paid fast-track exists] | Name, Main description, URL, category | P1 | |
| 7 | **Cursor Directory** | cursor.directory (MCP section) | "Submit"/add on site [verify] | Name, description (Developer angle), Cursor `mcp.json` snippet, logo | P1 | Include the Cursor deeplink button. |
| 8 | **awesome-mcp-servers** | github.com/punkpeye/awesome-mcp-servers | Pull request following CONTRIBUTING (category, alphabetical order, legend icons for remote/hosted, language) | One line: `[Hundred](link) ☁️ – description` per its format | P1 | Read contribution rules exactly; malformed PRs get closed. |
| 9 | **MCP Market** | mcpmarket.com | Submit on site [verify] | Main + free | P1 | |
| 10 | **Cline MCP Marketplace** | github.com/cline/mcp-marketplace | GitHub issue with repo URL, 400×400 logo, reason to add [verify] | Free listing first (no key = easier approval), then paid | P2 | An `llms-install.md` in the repo helps Cline auto-install [verify]. |
| 11 | **LobeHub MCP** | lobehub.com/mcp | Submit on site / GitHub [verify] | Main + free | P2 | |
| 12 | **Claude Code plugin marketplace** | our own GitHub repo with a marketplace manifest [verify current format: `.claude-plugin/marketplace.json`] | Users add it with `/plugin marketplace add <owner>/<repo>` [verify] | Plugin bundling the MCP server config; optional slash commands per category | P2 | Also submit to community lists of Claude Code plugins/marketplaces [verify which are active]. |
| 13 | **Gemini CLI extensions gallery** | geminicli.com/extensions [verify] | Public GitHub repo with `gemini-extension.json` (MCP config + context file); gallery discovery via repo topic/tag [verify] | Extension manifest pointing at `{MCP_URL}` with key via env/setting | P2 | |
| 14 | **GitHub MCP Registry / VS Code MCP gallery** | github.com/mcp [verify] | [verify] Historically curated/sourced from the official registry | Ensure official registry entry (#1) is complete | P2 | May be automatic once #1 is live. |
| 15 | **Windsurf MCP marketplace** | inside Windsurf/Codeium [verify if it accepts third-party submissions] | [verify] | Main | P3 | If no submission path, ship the JSON snippet on our install page instead. |
| 16 | **Anthropic: Claude connectors directory** | claude.ai directory; submission form linked from Anthropic's connector/MCP docs [verify] | Application + review against Anthropic's directory policy [verify requirements] | Main listing, privacy policy, support contact, test credentials, description of every tool | P3 | **Check auth requirements first.** Directory listings may expect OAuth rather than a key in the URL. If so, OAuth is a product prerequisite; start early. Review can take weeks. |
| 17 | **OpenAI: ChatGPT apps directory** | submitted via the OpenAI Platform [verify] | Build to the Apps SDK (MCP-based), then submit for review against OpenAI's app guidelines [verify] | App name, description, tool list, privacy policy, test account, screenshots | P3 | **Check:** eligibility of apps requiring an external subscription, rules on linking to external checkout, and restrictions on promotional content in tool responses. |
| 18 | **Docker MCP Catalog** | hub.docker.com/mcp [verify] | Oriented to containerized/local servers | — | Skip for now | Our server is remote/hosted; revisit only if we ship a self-host image. |

**Per-listing hygiene:** consistent name and logo everywhere; every link carries its own `utm_source`; the free listing links to paid and vice versa; answer reviews/issues within 48 h; refresh descriptions monthly (agent count, new categories).

---

## 3. General AI & launch directories

Several of these charge for listing or expedited review; **fees and terms change, so verify before paying.** Rule: free listings first; pay only for directories that show evidence of converting traffic in our niche.

| # | Directory | Where (verify) | Submit | Pri | Cost (verify) | Notes |
|---|---|---|---|---|---|---|
| 1 | **Product Hunt** | producthunt.com | Launch page (see LAUNCH_COPY §2) | Launch day 17 | Free | Separate playbook, GTM §6.5 |
| 2 | **Hacker News (Show HN)** | news.ycombinator.com | Show HN post (LAUNCH_COPY §3) | Day 9 | Free | Not a directory, but the same prep |
| 3 | **BetaList** | betalist.com | Startup submission | Week 3 | Free (long queue) / paid expedite | Early-adopter audience |
| 4 | **Uneed** | uneed.best | Launch submission | Week 3 | Free queue / paid skip | |
| 5 | **Microlaunch** | microlaunch.net | Launch submission | Week 3 | Free / paid options | |
| 6 | **Peerlist Launchpad** | peerlist.io | Weekly launchpad | Week 3 | Free | Dev/maker audience |
| 7 | **DevHunt** | devhunt.org | Dev-tool launch | Week 3 | Free / paid options | Use Developer angle |
| 8 | **Fazier** | fazier.com | Launch submission | Week 3 | Free / paid | |
| 9 | **SaaSHub** | saashub.com | Product submission + alternatives | Week 3 | Free | List as alternative to prompt libraries/AI writing tools |
| 10 | **AlternativeTo** | alternativeto.net | Add application | Week 3 | Free | Pick honest "alternative to" entries only |
| 11 | **Indie Hackers** | indiehackers.com | Product page + milestone posts | Week 1 | Free | Build-in-public revenue updates |
| 12 | **There's An AI For That** | theresanaiforthat.com | Tool submission | Week 4 | Paid [verify] | High AI-tool traffic; evaluate fee against CAC ceiling (GTM §13.3) |
| 13 | **Futurepedia** | futurepedia.io | Tool submission | Week 4 | Paid [verify] | Same rule |
| 14 | **Toolify** | toolify.ai | Tool submission | Week 4 | Free/paid tiers [verify] | |
| 15 | **TopAI.tools** | topai.tools | Tool submission | Week 4 | [verify] | |
| 16 | **AI Agents Directory** | aiagentsdirectory.com | Agent submission | Week 2 | [verify] | Category: "agent marketplaces/toolkits" |
| 17 | **AI Agent Store** | aiagentstore.ai | Agent submission | Week 2 | [verify] | |
| 18 | **G2 / Capterra** | g2.com, capterra.com | Vendor profile | Month 3+ | Free profile | Only useful once we have real reviews; ask happy customers then |

---

## 4. Per-category descriptions (≤160 chars) for category pages & multi-listing directories

Only create separate category listings where a directory explicitly allows multiple listings per vendor. Otherwise it reads as spam.

| Category | Description | Chars |
|---|---|---|
| Sales | 10 sales agents for your AI: cold email scoring, MEDDPICC call reviews, objection handling, pipeline forecasts & negotiation math. One MCP URL. | 143 |
| Marketing | 10 marketing agents: ad copy checked against platform limits, A/B significance, CRO scoring, budget & CAC math. Inside Claude, ChatGPT or Cursor. | 145 |
| Content & Writing | 9 writing agents: blog, newsletter, X threads, LinkedIn & YouTube scripts with real length, readability & timing checks. Copy Editor is free. | 141 |
| SEO & Growth | 8 SEO & growth agents: on-page audits, keyword clustering, SERP pixel widths, JSON-LD schema, RICE scoring & K-factor math. One MCP URL. | 136 |
| Operations | 9 ops agents: meeting notes (free), inbox triage, SOPs, critical-path plans, OKRs, RAG status reports & weighted decision matrices. | 131 |
| Finance | 9 finance agents: 13-week cash flow, LTV/CAC, pricing research, invoice aging, MRR models & quarterly tax estimates. Math done by code. | 135 |
| Engineering | 10 engineering agents: code review, stack-trace parsing, SQL linting, regex testing, commit linting, SLO budgets & capacity estimates. | 134 |
| Product & Design | 7 product agents: PRD checks, interview synthesis, RICE/Kano prioritization, NPS math, TAM/SAM/SOM & WCAG contrast checks. | 122 |
| Career & HR | 8 career & HR agents: ATS resume match, STAR interview prep, comp comparisons, bias-checked job posts, scorecards & 30-60-90 plans. | 131 |
| Creators | 8 creator agents: content calendars, short-video timing, podcast notes, sponsorship rate cards, plus fitness, meal, travel & study planners. | 140 |
| E-commerce | 7 e-commerce agents: marketplace listing limits, review replies, funnel math, reorder points & EOQ, break-even ROAS & email flow timing. | 136 |
| Legal & Admin | 5 admin agents: contract red-flag scoring, privacy policy checklists, NDAs, grant budgets & freelance milestones. Not legal advice. | 131 |

---

## 5. Submission tracker (copy to a sheet)

| Directory | Listing (main/free) | Verified process on (date) | Submitted (date) | Status | Live URL | UTM source | Trials (30 d) | Notes |
|---|---|---|---|---|---|---|---|---|
| Official MCP Registry | main | | | | | registry | | |
| Official MCP Registry | free | | | | | registry | | |
| Smithery | main | | | | | smithery | | |
| Smithery | free | | | | | smithery | | |
| mcp.so | main + free | | | | | mcpso | | |
| PulseMCP | main + free | | | | | pulsemcp | | |
| Glama | main | | | | | glama | | |
| mcpservers.org | main | | | | | mcpservers | | |
| Cursor Directory | main | | | | | cursordir | | |
| awesome-mcp-servers | main | | | | | awesome | | |
| MCP Market | main | | | | | mcpmarket | | |
| Cline | free → main | | | | | cline | | |
| LobeHub | main | | | | | lobehub | | |
| Claude Code marketplace | main | | | | | ccplugin | | |
| Gemini CLI extension | main | | | | | geminiext | | |
| Anthropic directory | main | | | | | claudedir | | |
| OpenAI apps directory | main | | | | | openaidir | | |
| *(general directories §3)* | | | | | | | | |

**Monthly review:** sort by trials (30 d). Invest (better screenshots, reviews, updates) in the top 3. Stop maintaining anything with zero trials after 60 days, unless it's the official registry or a big-platform directory.
