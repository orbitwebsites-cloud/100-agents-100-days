"""Server-rendered storefront pages. No build step, no JS framework."""

from __future__ import annotations

import html
import json

from .. import plans, registry
from ..core import CATEGORIES, Agent
from .settings import settings

e = html.escape

CSS = """
:root{--bg:#0b0d12;--panel:#12151c;--line:#232835;--text:#e8ebf2;--muted:#9aa3b5;--accent:#7c5cff;--accent2:#22d3a6;--warn:#ffb020}
@media (prefers-color-scheme: light){:root:not([data-theme=dark]){--bg:#fafafb;--panel:#fff;--line:#e5e7ee;--text:#0f1320;--muted:#5b6478;--accent:#5b3df5;--accent2:#0f9f7a;--warn:#b86e00}}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--accent)}.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
header.top{display:flex;justify-content:space-between;align-items:center;padding:18px 0}
.logo{font-weight:800;letter-spacing:-.02em;font-size:20px;color:var(--text);text-decoration:none}.logo b{color:var(--accent)}
nav a{color:var(--muted);text-decoration:none;margin-left:18px;font-size:15px}
.hero{padding:56px 0 28px;text-align:center}.hero h1{font-size:clamp(34px,6vw,60px);line-height:1.05;letter-spacing:-.03em;margin:0 0 16px}
.hero p{color:var(--muted);font-size:clamp(17px,2.2vw,20px);max-width:720px;margin:0 auto 26px}
.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:10px;padding:13px 22px;font-weight:700;font-size:16px;text-decoration:none;cursor:pointer}
.btn.ghost{background:transparent;color:var(--text);border:1px solid var(--line)}.btn.small{padding:8px 14px;font-size:14px}
.pill{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:4px 12px;font-size:13px;color:var(--muted);margin-bottom:18px}
.pill b{color:var(--accent2)}
section{padding:40px 0}h2{font-size:30px;letter-spacing:-.02em;margin:0 0 8px}.sub{color:var(--muted);margin:0 0 24px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}
.card h3{margin:0 0 6px;font-size:17px}.card p{margin:0;color:var(--muted);font-size:14px}
.steps{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}.steps .n{color:var(--accent);font-weight:800}
.plan{display:flex;flex-direction:column}.plan .price{font-size:34px;font-weight:800;letter-spacing:-.02em;margin:6px 0}
.plan .price small{font-size:15px;color:var(--muted);font-weight:500}.plan ul{padding-left:18px;color:var(--muted);font-size:14px;flex:1}
.plan.hl{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}.tag{font-size:12px;font-weight:700;color:var(--accent2);text-transform:uppercase;letter-spacing:.06em}
.cat h3{margin:28px 0 10px;font-size:19px}.agent{display:flex;gap:10px;align-items:flex-start;cursor:pointer}
.agent input{margin-top:4px;accent-color:var(--accent);width:18px;height:18px;flex:none}.agent .free{color:var(--accent2);font-size:12px;font-weight:700}
.agent a{color:var(--text);text-decoration:none;font-weight:650}
.bar{position:sticky;bottom:0;background:var(--panel);border-top:1px solid var(--line);padding:12px 0;display:none;z-index:5}
.bar .wrap{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}.bar .hint{color:var(--muted);font-size:14px}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px}pre{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto;white-space:pre-wrap;word-break:break-all}
.key{font-size:16px;color:var(--accent2)}input[type=email],input[type=text]{width:100%;max-width:460px;padding:12px;border-radius:10px;border:1px solid var(--line);background:var(--panel);color:var(--text);font-size:15px}
details{border-bottom:1px solid var(--line);padding:14px 0}summary{cursor:pointer;font-weight:650}
footer{color:var(--muted);font-size:14px;padding:40px 0;border-top:1px solid var(--line);margin-top:40px}
.plans{grid-template-columns:repeat(auto-fit,minmax(196px,1fr))}
@media (max-width:560px){nav a{margin-left:12px;font-size:14px}nav a:first-child{display:none}.hero h1 br{display:none}}
.notice{border:1px solid var(--warn);color:var(--warn);border-radius:10px;padding:10px 14px;margin:14px 0}
"""


def layout(title: str, body: str, description: str = "") -> str:
    desc = e(description or f"{len(registry.all_agents())} expert AI agents that plug into Claude, ChatGPT and Cursor with one link.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<meta name="description" content="{desc}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{desc}">
<style>{CSS}</style></head><body>
<div class="wrap"><header class="top"><a class="logo" href="/">{e(settings.brand)}<b>.</b></a>
<nav><a href="/#agents">Agents</a><a href="/#pricing">Pricing</a><a href="/setup">Setup</a><a href="/account">Account</a></nav></header></div>
{body}
<div class="wrap"><footer>{e(settings.brand)} · Expert agents for the AI you already use · <a href="/setup">Setup</a> · <a href="/account">Manage billing</a> · <a href="mailto:{e(settings.support_email)}">Support</a></footer></div>
</body></html>"""


def _plan_card(p: plans.Plan, founder_left: int) -> str:
    per = "/yr" if p.interval == "year" else "/mo"
    unit = ""  # "per agent"/"per pack" lives in the pitch; keeps the price on one line
    extra = ""
    if p.code == "founder":
        extra = f'<div class="tag">{founder_left} of {p.seat_cap} seats left</div>' if founder_left else '<div class="tag">Sold out</div>'
    if p.code in ("single", "pick5"):
        cta = '<a class="btn small ghost" href="#agents">Pick agents ↓</a>'
    elif p.code == "pack":
        options = "".join(f'<option value="{c}">{e(n)}</option>' for c, n in CATEGORIES.items() if c in registry.by_category())
        cta = (f'<form method="post" action="/checkout"><input type="hidden" name="plan" value="pack">'
               f'<select name="categories" style="width:100%;padding:9px;border-radius:8px;margin-bottom:8px;background:var(--panel);color:var(--text);border:1px solid var(--line)">{options}</select>'
               f'<button class="btn small" style="width:100%">Start 7-day trial</button></form>')
    else:
        disabled = " disabled" if p.code == "founder" and not founder_left else ""
        cta = (f'<form method="post" action="/checkout"><input type="hidden" name="plan" value="{p.code}">'
               f'<button class="btn small" style="width:100%"{disabled}>Start 7-day trial</button></form>')
    bullets = "".join(f"<li>{e(b)}</li>" for b in p.bullets)
    return (f'<div class="card plan{" hl" if p.highlight or p.code == "founder" else ""}">{extra}<h3>{e(p.name)}</h3>'
            f'<div class="price">{p.price}<small>{per}{unit}</small></div><p>{e(p.pitch)}</p><ul>{bullets}</ul>{cta}</div>')


def home_page(founder_left: int, canceled: bool = False) -> str:
    agents = registry.all_agents()
    n = len(agents)
    cats = registry.by_category()
    catalog = []
    for code, group in cats.items():
        items = []
        for a in group:
            box = ('<span class="free">FREE</span>' if a.free else
                   f'<input type="checkbox" name="agents" value="{a.slug}" aria-label="Select {e(a.name)}">')
            items.append(f'<label class="card agent">{box}<div><a href="/agents/{a.slug}">{e(a.name)}</a>'
                         f'<p>{e(a.tagline)}</p></div></label>')
        catalog.append(f'<div class="cat"><h3>{e(CATEGORIES[code])} <span class="sub">· {len(group)}</span></h3>'
                       f'<div class="grid">{"".join(items)}</div></div>')
    shown = ["founder", "single", "pick5", "pack", "all"]
    cards = "".join(_plan_card(plans.PLANS[c], founder_left) for c in shown if c != "founder" or founder_left)
    notice = '<div class="wrap"><div class="notice">Checkout canceled — nothing was charged.</div></div>' if canceled else ""
    body = f"""{notice}
<div class="wrap hero"><div class="pill"><b>{n} agents</b> · plugs into Claude, ChatGPT, Cursor & more</div>
<h1>Expert agents for the AI<br>you already use.</h1>
<p>Cold emails that book meetings. SEO audits. 13-week cash forecasts. Contract red-flags. {n} specialist agents —
each with a pro's playbook and real calculators — added to your AI with <b>one link</b>.</p>
<a class="btn" href="#pricing">Start 7-day free trial</a> &nbsp; <a class="btn ghost" href="/setup">Try the free agents</a></div>

<div class="wrap"><section><div class="steps">
<div class="card"><div class="n">1</div><h3>Pick your agents</h3><p>$4.99/mo each, or grab a bundle. Cancel anytime.</p></div>
<div class="card"><div class="n">2</div><h3>Paste one link</h3><p>Add your private MCP link to Claude, ChatGPT, Cursor, VS Code or Claude Code. 30 seconds.</p></div>
<div class="card"><div class="n">3</div><h3>Just ask</h3><p>"Forecast my cash for 13 weeks." Your AI calls the right agent, follows its playbook, runs its tools.</p></div>
</div></section>

<section id="pricing"><h2>Pricing</h2><p class="sub">Every plan starts with a 7-day free trial. Access follows your subscription — update your card and it's back instantly.</p>
<div class="grid plans">{cards}</div></section>

<section id="agents"><h2>The agents</h2><p class="sub">Tick the ones you want — we'll price the cheapest way to get them.</p>
<form id="pick" method="post" action="/checkout"><input type="hidden" name="plan" id="plan" value="single">{"".join(catalog)}</form></section>

<section><h2>FAQ</h2>
<details><summary>Which AI apps does it work with?</summary><p>Anything that speaks MCP over HTTP: Claude (web, desktop, Claude Code), ChatGPT (connectors / developer mode), Cursor, VS Code, Windsurf, Gemini CLI and more. See <a href="/setup">setup</a>.</p></details>
<details><summary>What's actually inside an agent?</summary><p>An expert operating procedure your AI follows step by step, plus deterministic tools — calculators, scorers, validators, parsers — for the parts AI usually gets wrong (math, dates, limits, statistics).</p></details>
<details><summary>What happens if my card declines?</summary><p>Agents pause right away and you get an email with a link to update your card. The moment payment succeeds they switch back on — same link, nothing to reinstall.</p></details>
<details><summary>Do you see my data?</summary><p>Your AI sends only what a tool needs (e.g. numbers for a forecast). We don't store tool inputs or outputs — we only count calls for fair use.</p></details>
<details><summary>Can I change agents later?</summary><p>Yes. Add or swap agents any time; they appear in your AI automatically.</p></details>
</section></div>

<div class="bar" id="bar"><div class="wrap"><div><b id="count">0 agents</b> · <span id="price">$0</span>/mo <div class="hint" id="hint"></div></div>
<button class="btn" form="pick" id="go">Start 7-day trial</button></div></div>
<script>
const boxes=[...document.querySelectorAll('#pick input[name=agents]')],bar=document.getElementById('bar');
function upd(){{const n=boxes.filter(b=>b.checked).length;bar.style.display=n?'block':'none';
let plan='single',price=(n*4.99),hint='';
if(n===5){{plan='pick5';price=14.99;hint='Starter Stack: 5 agents for the price of 3.';}}
else if(n===4){{hint='Pick one more — 5 agents are $14.99 total.';}}
else if(n>=6){{hint='All-Access is cheaper: every agent for $29.99/mo.';}}
if(n>=6&&price>29.99){{plan='all';price=29.99;}}
document.getElementById('plan').value=plan;document.getElementById('count').textContent=n+(n===1?' agent':' agents')+(plan==='all'?' → All-Access':'');
document.getElementById('price').textContent='$'+price.toFixed(2);document.getElementById('hint').textContent=hint;}}
boxes.forEach(b=>b.addEventListener('change',upd));
</script>"""
    return layout(f"{settings.brand} — {n} expert AI agents, one link", body)


def agent_page(agent: Agent) -> str:
    tools = "".join(f"<li><b>{e(t.name.replace('_', ' '))}</b> — {e(t.description.split(chr(10)*2)[0])}</li>" for t in agent.tools)
    examples = "".join(f"<li>“{e(x)}”</li>" for x in agent.examples)
    triggers = "".join(f"<li>{e(t)}</li>" for t in agent.triggers)
    conns = ", ".join(agent.connectors) or "—"
    if agent.free:
        cta = f'<a class="btn" href="/setup">Add it free</a>'
    else:
        cta = (f'<form method="post" action="/checkout" style="display:inline"><input type="hidden" name="plan" value="single">'
               f'<input type="hidden" name="agents" value="{agent.slug}"><button class="btn">Get {e(agent.name)} — $4.99/mo</button></form>'
               f' &nbsp; <a class="btn ghost" href="/#pricing">Or all agents, $29.99/mo</a>')
    body = f"""<div class="wrap hero" style="text-align:left"><div class="pill">{e(CATEGORIES[agent.category])} agent{' · <b>FREE</b>' if agent.free else ''}</div>
<h1>{e(agent.name)}</h1><p style="margin-left:0">{e(agent.tagline)}</p>{cta}</div>
<div class="wrap"><section><div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
<div class="card"><h3>What it does</h3><p>{e(agent.description)}</p></div>
<div class="card"><h3>Ask it things like</h3><ul style="color:var(--muted);font-size:14px;padding-left:18px">{examples}</ul></div>
</div></section>
<section><h2>Built-in tools</h2><p class="sub">Deterministic code for the parts AI gets wrong.</p><ul style="color:var(--muted)">{tools}</ul></section>
<section><h2>Your AI calls it when you…</h2><ul style="color:var(--muted)">{triggers}</ul>
<p class="sub">Acts through your connected apps when available: {e(conns)}.</p></section></div>"""
    return layout(f"{agent.name} — AI agent for Claude, ChatGPT & Cursor | {settings.brand}", body, agent.tagline)


def _setup_blocks(url: str) -> str:
    cfg = json.dumps({"mcpServers": {"hundred": {"url": url}}}, indent=2)
    return f"""
<div class="card"><h3>Claude (claude.ai & Desktop)</h3><p>Settings → Connectors → <b>Add custom connector</b> → paste your link → Add. Then enable it in a chat from the tools menu.</p></div>
<div class="card"><h3>ChatGPT</h3><p>Settings → Apps &amp; Connectors → enable <b>Developer mode</b> (under Advanced) → <b>Create</b> → paste your link, no auth. Menu names vary by plan/version.</p></div>
<div class="card"><h3>Claude Code</h3><pre>claude mcp add --transport http hundred "{e(url)}"</pre></div>
<div class="card"><h3>Cursor · Windsurf · VS Code · others</h3><p>Add to your MCP config (e.g. <code>~/.cursor/mcp.json</code>):</p><pre>{e(cfg)}</pre></div>
<div class="card"><h3>Client can't take a URL with <code>?key=</code>?</h3><p>Use the path form <code>{e(settings.public_url)}/k/&lt;your-key&gt;/mcp</code>, or send header <code>Authorization: Bearer &lt;key&gt;</code>.</p></div>"""


def setup_page() -> str:
    free = [a for a in registry.all_agents().values() if a.free]
    free_names = ", ".join(a.name for a in free)
    body = f"""<div class="wrap hero" style="text-align:left"><h1>Connect in 30 seconds</h1>
<p style="margin-left:0">Your link is in your welcome email. No key yet? Use <code>{e(settings.mcp_url)}</code> to try the free agents ({e(free_names)}).</p></div>
<div class="wrap"><div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(320px,1fr))">{_setup_blocks(settings.mcp_url + "?key=YOUR_KEY")}</div>
<section><h2>Then just ask</h2><p class="sub">“Write a 4-step cold email sequence for CFOs at 50-200 person SaaS companies.” Your AI picks the agent, follows its playbook and runs its tools. With many agents, it uses <code>hundred_find_agent</code> to route.</p>
<p class="sub">Want a focused connection? Add <code>&amp;agents=cold-email,lead-qualifier</code> to the link.</p></section></div>"""
    return layout(f"Setup — {settings.brand}", body)


def welcome_page(key: str | None) -> str:
    if key:
        url = f"{settings.mcp_url}?key={key}"
        top = f"""<h1>You're in. 🎉</h1><p style="margin-left:0">Here's your private MCP link. It's shown <b>once</b> (it's also in your email). Treat it like a password.</p>
<pre class="key">{e(url)}</pre>"""
        blocks = _setup_blocks(url)
    else:
        top = """<h1>Payment received — finishing setup</h1><p style="margin-left:0">Your key is on its way to your inbox (usually within a minute).
If this page was already opened once, the key is only in the email now. Nothing there in 5 minutes? Use <a href="/account">Account → recover key</a>.</p>"""
        blocks = _setup_blocks(settings.mcp_url + "?key=YOUR_KEY")
    body = f"""<div class="wrap hero" style="text-align:left">{top}</div>
<div class="wrap"><div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(320px,1fr))">{blocks}</div></div>"""
    return layout(f"Welcome — {settings.brand}", body)


def account_page(error: str = "", notice: str = "") -> str:
    msg = f'<div class="notice">{e(error or notice)}</div>' if (error or notice) else ""
    body = f"""<div class="wrap hero" style="text-align:left"><h1>Account</h1>{msg}</div>
<div class="wrap"><div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(320px,1fr))">
<div class="card"><h3>Update card · change plan · cancel</h3><p>Paste your key (the part after <code>key=</code>).</p><br>
<form method="post"><input type="hidden" name="action" value="portal"><input type="text" name="key" placeholder="hnd_live_…" required><br><br><button class="btn small">Open billing portal</button></form></div>
<div class="card"><h3>Lost your key?</h3><p>We'll email a fresh one to the address on your subscription. The old key stops working.</p><br>
<form method="post"><input type="hidden" name="action" value="recover"><input type="email" name="email" placeholder="you@company.com" required><br><br><button class="btn small ghost">Email me a new key</button></form></div>
</div></div>"""
    return layout(f"Account — {settings.brand}", body)


def message_page(title: str, message: str, back: str = "/") -> str:
    body = f'<div class="wrap hero"><h1>{e(title)}</h1><p>{e(message)}</p><a class="btn ghost" href="{e(back)}">Back</a></div>'
    return layout(f"{title} — {settings.brand}", body)
