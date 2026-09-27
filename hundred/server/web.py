"""Server-rendered storefront pages. No build step, no JS framework.

Visual identity, "Switchboard": the product patches expert agents into the AI a
customer already uses, so the site borrows from instrument panels. Sage-grey
ground, hairline rules, one signal-amber lamp colour, teal for "live". Archivo
set wide for labels and headlines, IBM Plex Sans for reading, IBM Plex Mono for
the one thing only this product has: real tool names and MCP links. The hero is
a real tool call, computed when the page renders, so the demo is always true.
"""

from __future__ import annotations

import html
import json

from .. import plans, registry
from ..core import CATEGORIES, Agent
from .settings import settings

e = html.escape

FONTS = (
    "https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,500..900"
    "&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
)

CSS = """
:root{
  --ground:#EEF1EC;--panel:#FFFFFF;--sunk:#E4E8E2;--ink:#121517;--muted:#56605B;--line:#D6DAD2;--line-strong:#B9BFB6;
  --amber:#E8A317;--amber-ink:#121517;--amber-text:#8A5A00;--teal:#0E7C6B;--teal-soft:#D5EBE5;--warn:#A4460F;
  --display:"Archivo","Helvetica Neue",Arial,sans-serif;--body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--s6:32px;--s7:48px;--s8:72px;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --ground:#101416;--panel:#161B1E;--sunk:#0B0E10;--ink:#E6EAE3;--muted:#98A29B;--line:#263034;--line-strong:#3A4549;
  --amber:#F0B429;--amber-ink:#121517;--amber-text:#F0B429;--teal:#3CC4A4;--teal-soft:#123A33;--warn:#F08A4B;color-scheme:dark}}
:root[data-theme="dark"]{
  --ground:#101416;--panel:#161B1E;--sunk:#0B0E10;--ink:#E6EAE3;--muted:#98A29B;--line:#263034;--line-strong:#3A4549;
  --amber:#F0B429;--amber-ink:#121517;--amber-text:#F0B429;--teal:#3CC4A4;--teal-soft:#123A33;--warn:#F08A4B;color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);font:400 16px/1.6 var(--body);padding-inline:16px}
a{color:inherit;text-underline-offset:3px;text-decoration-thickness:1px}
a:hover{color:var(--amber-text)}
:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
.wrap{max-width:1160px;margin-inline:auto}
h1,h2,h3{font-family:var(--display);font-stretch:118%;letter-spacing:-.01em;text-wrap:balance;margin:0}
h1{font-weight:850;font-size:clamp(38px,6.2vw,74px);line-height:.98}
h2{font-weight:800;font-size:clamp(26px,3.4vw,38px);line-height:1.05}
h3{font-weight:700;font-size:18px;line-height:1.2;font-stretch:108%}
p{margin:0;max-width:65ch}
.label{font-family:var(--display);font-stretch:125%;font-weight:700;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.lede{font-size:clamp(17px,1.9vw,20px);color:var(--muted);max-width:52ch}
.mono,code,pre{font-family:var(--mono);font-size:.9em}
.num{font-variant-numeric:tabular-nums}

/* header */
.top{display:flex;justify-content:space-between;align-items:center;gap:var(--s4);padding-block:var(--s5);border-bottom:1px solid var(--line)}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;font-family:var(--display);font-stretch:125%;font-weight:900;font-size:19px;letter-spacing:.02em;text-transform:uppercase}
.lamp{width:10px;height:10px;border-radius:50%;background:var(--amber);box-shadow:0 0 0 3px color-mix(in srgb,var(--amber) 25%,transparent);flex:none}
.lamp.live{background:var(--teal);box-shadow:0 0 0 3px color-mix(in srgb,var(--teal) 25%,transparent)}
nav{display:flex;gap:var(--s5);flex-wrap:wrap}
nav a{text-decoration:none;font-size:15px;color:var(--muted)}
nav a:hover{color:var(--ink)}

/* buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;background:var(--amber);color:var(--amber-ink);border:1px solid var(--amber);
  border-radius:4px;padding:13px 20px;font:700 15px/1 var(--body);text-decoration:none;cursor:pointer;transition:transform .12s ease,box-shadow .12s ease}
.btn:hover{color:var(--amber-ink);box-shadow:0 2px 0 var(--ink)}
.btn:active{transform:translateY(1px)}
.btn.line{background:transparent;color:var(--ink);border-color:var(--line-strong)}
.btn.line:hover{border-color:var(--ink);box-shadow:none}
.btn[disabled]{opacity:.45;cursor:not-allowed}
.btn.block{width:100%}
.actions{display:flex;gap:var(--s3);flex-wrap:wrap}

/* hero */
.hero{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:var(--s7);align-items:center;padding-block:var(--s8) var(--s7)}
.hero-copy{display:grid;gap:var(--s5)}
.clients{display:flex;flex-wrap:wrap;gap:6px 14px;font-family:var(--mono);font-size:13px;color:var(--muted)}
.clients span::before{content:"→ ";color:var(--teal)}

/* the console: a real tool call */
.console{background:var(--panel);border:1px solid var(--line-strong);border-radius:6px;overflow:hidden;box-shadow:0 18px 40px -24px rgba(0,0,0,.35)}
.console-head{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--line);font-size:13px;color:var(--muted)}
.console-head b{color:var(--ink);font-weight:600}
.console-body{display:grid;gap:14px;padding:18px}
.say{padding:10px 14px;border-radius:4px;max-width:92%;font-size:15px}
.say.you{justify-self:end;background:var(--sunk)}
.say.ai{border-left:3px solid var(--teal);border-radius:0;padding-block:4px}
.call{font-family:var(--mono);font-size:13px;color:var(--muted)}
.call .fn{color:var(--amber-text);font-weight:500}
.scores{width:100%;border-collapse:collapse;font-size:14px}
.scores td{padding:7px 0;border-top:1px solid var(--line);vertical-align:middle}
.scores .s{font-family:var(--mono);font-size:13px;padding-right:12px}
.scores .bar{width:32%}
.meter{height:6px;background:var(--sunk);border-radius:3px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--teal)}
.meter i.rewrite{background:var(--amber)}
.scores .v{text-align:right;width:52px;font-family:var(--mono);font-variant-numeric:tabular-nums}
.fix{font-size:12px;color:var(--muted);margin-top:2px}

/* sections */
section{padding-block:var(--s7);border-top:1px solid var(--line)}
.section-head{display:grid;gap:var(--s2);margin-bottom:var(--s6)}
.steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0}
.step{padding:var(--s2) var(--s5) var(--s2) 0;display:grid;gap:var(--s2);align-content:start}
.step+.step{padding-left:var(--s5);border-left:1px solid var(--line)}
.step .n{font-family:var(--mono);color:var(--amber-text);font-size:13px}

/* pricing */
.founder{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) auto;gap:var(--s5);align-items:center;background:var(--panel);
  border:1px solid var(--line-strong);border-left:4px solid var(--amber);border-radius:6px;padding:var(--s5);margin-bottom:var(--s5)}
.founder .price{font-family:var(--display);font-stretch:112%;font-weight:850;font-size:40px;line-height:1}
.founder .price small{font-family:var(--body);font-size:15px;font-weight:400;color:var(--muted)}
.seats{display:grid;gap:6px;font-size:13px;color:var(--muted)}
.seats .meter{height:8px}
.seats .meter i{background:var(--amber)}
.plans{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);border-radius:6px;background:var(--panel)}
.plan{display:flex;flex-direction:column;gap:var(--s3);padding:var(--s5)}
.plan+.plan{border-left:1px solid var(--line)}
.plan .price{font-family:var(--display);font-stretch:112%;font-weight:800;font-size:32px;line-height:1;font-variant-numeric:tabular-nums}
.plan .price small{font-family:var(--body);font-size:14px;font-weight:400;color:var(--muted)}
.plan ul{margin:0;padding:0;list-style:none;display:grid;gap:6px;align-content:start;font-size:14px;color:var(--muted);flex:1}
.plan li::before{content:"· ";color:var(--teal);font-weight:700}
.plan.all{background:color-mix(in srgb,var(--amber) 9%,var(--panel))}
.plan select{width:100%;padding:10px;border-radius:4px;border:1px solid var(--line-strong);background:var(--panel);color:var(--ink);font:inherit;font-size:14px}
.fineprint{font-size:13px;color:var(--muted);margin-top:var(--s4)}

/* catalog: a patch panel */
.bank{display:grid;grid-template-columns:220px minmax(0,1fr);gap:var(--s5);padding-block:var(--s5);border-top:1px solid var(--line)}
.bank:first-of-type{border-top:0}
.bank-head{display:grid;gap:4px;align-content:start}
.bank-head .count{font-family:var(--mono);font-size:13px;color:var(--muted)}
.jacks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 var(--s5)}
.jack{display:grid;grid-template-columns:22px minmax(0,1fr);gap:10px;padding:10px 0;border-top:1px solid var(--line);cursor:pointer}
.jack:nth-child(-n+2){border-top:0}
.jack input{appearance:none;width:16px;height:16px;margin:3px 0 0;border:1.5px solid var(--line-strong);border-radius:50%;background:var(--panel);cursor:pointer;display:grid;place-content:center}
.jack input:checked{border-color:var(--amber);background:var(--amber);box-shadow:0 0 0 3px color-mix(in srgb,var(--amber) 25%,transparent)}
.jack .free{font-family:var(--mono);font-size:10px;color:var(--teal);letter-spacing:.06em;margin-top:4px}
.jack a{font-weight:600;text-decoration:none}
.jack a:hover{text-decoration:underline}
.jack p{font-size:14px;color:var(--muted);line-height:1.45}

/* sticky picker bar */
.bar{position:sticky;bottom:0;z-index:5;background:var(--panel);border-top:1px solid var(--line-strong);padding-block:12px calc(12px + env(safe-area-inset-bottom,0px));margin-inline:-16px;padding-inline:16px}
.bar .wrap{display:flex;gap:var(--s4);align-items:center;justify-content:space-between;flex-wrap:wrap}
.bar .hint{color:var(--muted);font-size:14px}

/* faq */
.faq{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--s5) var(--s7)}
.faq h3{font-size:16px;margin-bottom:6px;font-stretch:100%;font-family:var(--body);font-weight:600}
.faq p{color:var(--muted);font-size:15px}

/* inner pages */
.page-head{display:grid;gap:var(--s4);padding-block:var(--s7) var(--s6)}
.cols{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--s6)}
.toollist{display:grid;gap:0;border-top:1px solid var(--line)}
.tool{display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:var(--s5);padding-block:var(--s3);border-bottom:1px solid var(--line)}
.tool code{color:var(--amber-text);word-break:break-all}
.tool p{color:var(--muted);font-size:15px}
.quote{border-left:3px solid var(--teal);padding:2px 0 2px 14px;margin:0 0 10px;font-size:15px}
.plain{margin:0;padding-left:18px;color:var(--muted);display:grid;gap:6px}
.clientlist{display:grid;gap:0;border-top:1px solid var(--line)}
.client{display:grid;grid-template-columns:minmax(0,260px) minmax(0,1fr);gap:var(--s5);padding-block:var(--s5);border-bottom:1px solid var(--line)}
.client p{color:var(--muted)}
pre{background:var(--sunk);border:1px solid var(--line);border-radius:4px;padding:12px 14px;margin:8px 0 0;overflow-x:auto;white-space:pre-wrap;word-break:break-all;line-height:1.5}
.keybox{font-family:var(--mono);font-size:15px;background:var(--panel);border:1px solid var(--line-strong);border-left:4px solid var(--teal);border-radius:4px;padding:14px 16px;word-break:break-all}
.field{display:grid;gap:8px;max-width:460px}
.field input{width:100%;padding:12px;border-radius:4px;border:1px solid var(--line-strong);background:var(--panel);color:var(--ink);font:inherit}
.box{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:var(--s5);display:grid;gap:var(--s3);align-content:start}
.notice{border:1px solid var(--warn);color:var(--warn);border-radius:4px;padding:10px 14px;font-size:15px}

/* post-purchase offer */
.offer{background:var(--panel);border:1px solid var(--line-strong);border-top:4px solid var(--amber);border-radius:6px;padding:var(--s5);display:grid;gap:var(--s3);margin-bottom:var(--s6)}
.offer .timer{color:var(--amber-text)}
.offer .was{text-decoration:line-through;color:var(--muted);font-size:20px;margin-right:10px;font-variant-numeric:tabular-nums}
.offer .now{font-family:var(--display);font-stretch:112%;font-weight:850;font-size:46px;line-height:1;font-variant-numeric:tabular-nums}
.offer .per{color:var(--muted)}
.offer .terms{color:var(--muted);font-size:13px;max-width:80ch}
.offer form{max-width:520px}

footer{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s5);justify-content:space-between;color:var(--muted);font-size:14px;padding-block:var(--s6);border-top:1px solid var(--line);margin-top:var(--s7)}
footer nav{gap:var(--s4)}

@media (max-width:900px){
  .hero{grid-template-columns:1fr;padding-block:var(--s7)}
  .plans{grid-template-columns:repeat(2,minmax(0,1fr))}
  .plan:nth-child(3){border-left:0}
  .plan:nth-child(n+3){border-top:1px solid var(--line)}
  .founder{grid-template-columns:1fr}
  .bank{grid-template-columns:1fr;gap:var(--s3)}
}
@media (max-width:640px){
  nav{gap:var(--s4)}
  nav a.opt{display:none}
  .steps,.faq,.cols{grid-template-columns:1fr}
  .step+.step{padding-left:0;border-left:0;border-top:1px solid var(--line);padding-top:var(--s4)}
  .step{padding-right:0;padding-bottom:var(--s4)}
  .plans{grid-template-columns:1fr}
  .plan+.plan{border-left:0;border-top:1px solid var(--line)}
  .jacks{grid-template-columns:1fr}
  .jack:nth-child(2){border-top:1px solid var(--line)}
  .tool,.client{grid-template-columns:1fr;gap:4px}
  .console-body{padding:14px;gap:12px}
  .scores .bar{width:18%}
  .scores .s{font-size:12px;padding-right:8px}
  .scores .v{width:36px}
  .say{max-width:100%}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def layout(title: str, body: str, description: str = "") -> str:
    desc = e(description or f"{len(registry.all_agents())} expert agents for Claude, ChatGPT and Cursor. One link. $4.99/mo each.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{e(title)}</title>
<meta name="description" content="{desc}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}"><style>{CSS}</style></head><body>
<div class="wrap"><header class="top"><a class="logo" href="/"><span class="lamp" aria-hidden="true"></span>{e(settings.brand)}</a>
<nav aria-label="Main"><a class="opt" href="/#agents">Agents</a><a href="/#pricing">Pricing</a><a href="/setup">Setup</a><a href="/account">Account</a></nav></header></div>
{body}
<div class="wrap"><footer><span>{e(settings.brand)} · Expert agents for the AI you already use</span>
<nav aria-label="Footer"><a href="/setup">Setup</a><a href="/account">Billing</a><span class="mono">{e(settings.support_email)}</span></nav></footer></div>
</body></html>"""


# ── home ────────────────────────────────────────────────────
def _demo() -> str:
    """A real Cold Email Closer tool call, run at render time."""
    agent = registry.get("cold-email")
    tool = agent.get_tool("score_subject_line") if agent else None
    subjects = ["ops cost at Ridgeline", "Quick question!!", "Re: our call", "FREE route optimization demo"]
    if tool is None:
        return ""
    try:
        results = tool.call({"subjects": subjects})["results"]
    except Exception:  # the demo must never take the home page down
        return ""
    rows = []
    for r in results:
        cls = "" if r.get("grade") == "send" else "rewrite"
        fix = f'<div class="fix">{e(r["fixes"][0])}</div>' if r.get("fixes") else ""
        rows.append(
            f'<tr><td class="s">{e(r["subject"])}{fix}</td>'
            f'<td class="bar"><div class="meter"><i class="{cls}" style="width:{int(r["score"])}%"></i></div></td>'
            f'<td class="v">{int(r["score"])}</td></tr>'
        )
    best = max(results, key=lambda r: r["score"])
    worst = min(results, key=lambda r: r["score"])
    advice = f'Send “{e(best["subject"])}”. It scores {best["score"]}/100. Rewrite “{e(worst["subject"])}” first: ' \
             f'{e(worst["fixes"][0]) if worst.get("fixes") else "low score"}.'
    return f"""<figure class="console" aria-label="Example: Claude using the Cold Email Closer agent">
<div class="console-head"><span class="lamp live" aria-hidden="true"></span><b>Your AI</b> · connected to {e(settings.brand)}</div>
<div class="console-body">
<div class="say you">Which of these subject lines should I send to the Ridgeline ops team?</div>
<div class="call">→ <span class="fn">{e(agent.wire_name("score_subject_line"))}</span>({len(subjects)} subjects)</div>
<table class="scores">{"".join(rows)}</table>
<div class="say ai">{advice}</div>
</div></figure>"""


def _founder_row(p: plans.Plan, founder_left: int) -> str:
    cap = p.seat_cap or 0
    taken = max(0, cap - founder_left)
    pct = round(100 * taken / cap) if cap else 0
    bullets = " · ".join(e(b) for b in p.bullets)
    return f"""<div class="founder">
<div><div class="label" style="color:var(--amber-text)">Founding member · first {cap} only</div>
<h3 style="font-size:24px;margin-block:6px">Every agent, half price, for life.</h3><p style="color:var(--muted)">{bullets}</p></div>
<div class="seats"><div class="price num">{p.price}<small>/mo</small></div>
<div class="meter" role="img" aria-label="{taken} of {cap} seats taken"><i style="width:{max(pct, 1)}%"></i></div>
<span class="num">{founder_left} of {cap} seats left</span></div>
<form method="post" action="/checkout"><input type="hidden" name="plan" value="founder"><button class="btn">Claim a seat</button></form>
</div>"""


def _plan_col(p: plans.Plan) -> str:
    per = "/yr" if p.interval == "year" else "/mo"
    if p.code in ("single", "pick5"):
        cta = '<a class="btn line block" href="#agents">Pick agents</a>'
    elif p.code == "pack":
        options = "".join(f'<option value="{c}">{e(n)}</option>' for c, n in CATEGORIES.items() if c in registry.by_category())
        cta = (f'<form method="post" action="/checkout" style="display:grid;gap:8px"><input type="hidden" name="plan" value="pack">'
               f'<label class="label" for="pack-cat">Category</label><select id="pack-cat" name="categories">{options}</select>'
               f'<button class="btn line block">Start 7-day trial</button></form>')
    else:
        cta = (f'<form method="post" action="/checkout"><input type="hidden" name="plan" value="{p.code}">'
               f'<button class="btn block">Start 7-day trial</button></form>')
    bullets = "".join(f"<li>{e(b)}</li>" for b in p.bullets)
    return (f'<div class="plan{" all" if p.code == "all" else ""}"><div class="label">{e(p.name)}</div>'
            f'<div class="price">{p.price}<small>{per}</small></div><p style="font-size:15px">{e(p.pitch)}</p>'
            f'<ul>{bullets}</ul>{cta}</div>')


def home_page(founder_left: int, canceled: bool = False) -> str:
    agents = registry.all_agents()
    n = len(agents)
    n_tools = sum(len(a.tools) for a in agents.values())
    banks = []
    for code, group in registry.by_category().items():
        jacks = []
        for a in group:
            box = ('<span class="free">FREE</span>' if a.free else
                   f'<input type="checkbox" name="agents" value="{a.slug}" id="pick-{a.slug}" aria-label="Select {e(a.name)}">')
            jacks.append(f'<label class="jack">{box}<div><a href="/agents/{a.slug}">{e(a.name)}</a>'
                         f'<p>{e(a.tagline)}</p></div></label>')
        banks.append(f'<div class="bank"><div class="bank-head"><h3>{e(CATEGORIES[code])}</h3>'
                     f'<span class="count">{len(group)} agents</span></div><div class="jacks">{"".join(jacks)}</div></div>')
    founder = plans.PLANS["founder"]
    founder_html = _founder_row(founder, founder_left) if founder_left else ""
    cols = "".join(_plan_col(plans.PLANS[c]) for c in ["single", "pick5", "pack", "all"])
    notice = '<div class="wrap" style="padding-top:16px"><div class="notice">Checkout canceled. Nothing was charged.</div></div>' if canceled else ""
    body = f"""{notice}
<div class="wrap hero">
<div class="hero-copy">
<div class="label">{n} agents · {n_tools} tools · one link</div>
<h1>Plug expert agents into the AI you already use.</h1>
<p class="lede">Each agent is a specialist's playbook plus real calculators, scorers and validators. Your AI follows the playbook and runs the tools for the parts it usually gets wrong: math, dates, limits and statistics.</p>
<div class="actions"><a class="btn" href="#pricing">Start 7-day free trial</a><a class="btn line" href="/setup">Try the free agents</a></div>
<div class="clients" aria-label="Works with"><span>Claude</span><span>ChatGPT</span><span>Cursor</span><span>VS Code</span><span>Claude Code</span><span>Windsurf</span></div>
</div>
{_demo()}
</div>

<div class="wrap">
<section aria-labelledby="how"><div class="section-head"><div class="label">Setup</div><h2 id="how">Three steps. About a minute.</h2></div>
<div class="steps">
<div class="step"><span class="n">1</span><h3>Pick agents</h3><p style="color:var(--muted)">$4.99 a month each, or a bundle. Cancel anytime.</p></div>
<div class="step"><span class="n">2</span><h3>Paste your link</h3><p style="color:var(--muted)">Add your private MCP link to Claude, ChatGPT, Cursor, VS Code or Claude Code.</p></div>
<div class="step"><span class="n">3</span><h3>Ask as usual</h3><p style="color:var(--muted)">“Forecast my cash for 13 weeks.” Your AI picks the agent, follows its playbook and runs its tools.</p></div>
</div></section>

<section id="pricing" aria-labelledby="pricing-h"><div class="section-head"><div class="label">Pricing</div><h2 id="pricing-h">Start with one agent or take them all.</h2>
<p style="color:var(--muted)">Every plan starts with a 7-day free trial. If a payment fails, agents pause; update your card and they come back on the same link.</p></div>
{founder_html}<div class="plans">{cols}</div></section>

<section id="agents" aria-labelledby="agents-h"><div class="section-head"><div class="label">Catalog</div><h2 id="agents-h">All {n} agents</h2>
<p style="color:var(--muted)">Select the agents you want. The bar at the bottom picks the cheapest plan for your selection.</p></div>
<form id="pick" method="post" action="/checkout"><input type="hidden" name="plan" id="plan" value="single">{"".join(banks)}</form></section>

<section aria-labelledby="faq-h"><div class="section-head"><div class="label">Questions</div><h2 id="faq-h">Before you buy</h2></div>
<div class="faq">
<div><h3>Which AI apps does it work with?</h3><p>Anything that connects to MCP servers over HTTP: Claude (web, desktop and Claude Code), ChatGPT connectors, Cursor, VS Code, Windsurf and Gemini CLI. The <a href="/setup">setup guide</a> covers each one.</p></div>
<div><h3>What is inside an agent?</h3><p>A step-by-step procedure your AI follows, plus tools that compute exact answers: scores, dates, statistics, character limits and parsed data.</p></div>
<div><h3>What if my card is declined?</h3><p>Paid agents pause on the next request and we email you a link to update your card. They switch back on the moment the payment goes through.</p></div>
<div><h3>Do you store my data?</h3><p>No. Your AI sends only what a tool needs, such as the numbers for a forecast. We count calls for fair use and keep nothing else.</p></div>
<div><h3>Can I change agents later?</h3><p>Yes. Add or swap agents at any time. They appear in your AI without reinstalling anything.</p></div>
<div><h3>Is anything free?</h3><p>{" and ".join(a.name for a in agents.values() if a.free)} are free forever. Connect with no key to try them.</p></div>
</div></section>
</div>

<div class="bar" id="bar" hidden><div class="wrap"><div><b id="count" class="num">0 agents</b> · <span id="price" class="num">$0</span>/mo <div class="hint" id="hint"></div></div>
<button class="btn" form="pick" id="go">Start 7-day trial</button></div></div>
<script>
const boxes=[...document.querySelectorAll('#pick input[name=agents]')],bar=document.getElementById('bar');
function upd(){{const n=boxes.filter(b=>b.checked).length;bar.hidden=!n;
let plan='single',price=n*4.99,hint='';
if(n===5){{plan='pick5';price=14.99;hint='Starter Stack: 5 agents for the price of 3.';}}
else if(n===4){{hint='Add one more: any 5 agents cost $14.99 in total.';}}
if(n>=6&&price>29.99){{plan='all';price=29.99;hint='All-Access is cheaper than 6 single agents, and includes every agent.';}}
else if(n===6){{hint='For $0.05 more, All-Access includes every agent.';}}
document.getElementById('plan').value=plan;
document.getElementById('count').textContent=n+(n===1?' agent':' agents')+(plan==='all'?' → All-Access':'');
document.getElementById('price').textContent='$'+price.toFixed(2);document.getElementById('hint').textContent=hint;}}
boxes.forEach(b=>b.addEventListener('change',upd));upd();
</script>"""
    return layout(f"{settings.brand} · {n} expert agents for your AI", body)


# ── one page per agent ──────────────────────────────────────
def agent_page(agent: Agent) -> str:
    tools = "".join(
        f'<div class="tool"><code>{e(agent.wire_name(t.name))}</code><p>{e(t.description.split(chr(10) * 2)[0])}</p></div>'
        for t in agent.tools
    )
    examples = "".join(f'<p class="quote">“{e(x)}”</p>' for x in agent.examples)
    triggers = "".join(f"<li>{e(t)}</li>" for t in agent.triggers)
    conns = ", ".join(agent.connectors) or "none needed"
    if agent.free:
        cta = '<a class="btn" href="/setup">Add it free</a>'
    else:
        cta = (f'<form method="post" action="/checkout"><input type="hidden" name="plan" value="single">'
               f'<input type="hidden" name="agents" value="{agent.slug}"><button class="btn">Get {e(agent.name)} · $4.99/mo</button></form>'
               f'<a class="btn line" href="/#pricing">All agents · $29.99/mo</a>')
    body = f"""<div class="wrap page-head">
<div class="label">{e(CATEGORIES[agent.category])} agent{" · free" if agent.free else ""}</div>
<h1>{e(agent.name)}</h1><p class="lede">{e(agent.tagline)}</p><div class="actions">{cta}</div></div>
<div class="wrap">
<section><div class="cols"><div style="display:grid;gap:12px;align-content:start"><div class="label">What it does</div><p>{e(agent.description)}</p></div>
<div style="display:grid;gap:12px;align-content:start"><div class="label">Ask it</div><div>{examples}</div></div></div></section>
<section><div class="section-head"><div class="label">Tools</div><h2>{len(agent.tools)} tools your AI can call</h2>
<p style="color:var(--muted)">Code that computes the exact answer, so your AI doesn't estimate it.</p></div>
<div class="toollist">{tools}</div></section>
<section><div class="cols"><div style="display:grid;gap:12px;align-content:start"><div class="label">Your AI uses it when you ask to</div><ul class="plain">{triggers}</ul></div>
<div style="display:grid;gap:12px;align-content:start"><div class="label">Works with your connected apps</div><p style="color:var(--muted)">{e(conns)}</p></div></div></section>
</div>"""
    return layout(f"{agent.name} · AI agent for Claude, ChatGPT and Cursor", body, agent.tagline)


# ── setup, welcome, offer, account ──────────────────────────
def _setup_blocks(url: str) -> str:
    cfg = json.dumps({"mcpServers": {"hundred": {"url": url}}}, indent=2)
    rows = [
        ("Claude", "Web and desktop", "<p>Settings → Connectors → <b>Add custom connector</b>. Paste your link and select Add. "
         "Then turn it on in a chat from the tools menu.</p>"),
        ("ChatGPT", "Connectors", "<p>Settings → Apps &amp; Connectors → turn on <b>Developer mode</b> under Advanced → <b>Create</b>. "
         "Paste your link with no authentication. Menu names vary by plan.</p>"),
        ("Claude Code", "Terminal", f'<pre>claude mcp add --transport http hundred "{e(url)}"</pre>'),
        ("Cursor, Windsurf, VS Code", "MCP config file", f"<p>Add this to your MCP config, for example <code>~/.cursor/mcp.json</code>:</p><pre>{e(cfg)}</pre>"),
        ("Other clients", "If ?key= is dropped", f"<p>Use <code>{e(settings.public_url)}/k/&lt;your-key&gt;/mcp</code>, "
         "or send the header <code>Authorization: Bearer &lt;key&gt;</code>.</p>"),
    ]
    return '<div class="clientlist">' + "".join(
        f'<div class="client"><div><h3>{e(name)}</h3><div class="label" style="margin-top:4px">{e(kind)}</div></div><div>{how}</div></div>'
        for name, kind, how in rows
    ) + "</div>"


def setup_page() -> str:
    free = [a for a in registry.all_agents().values() if a.free]
    free_names = " and ".join(a.name for a in free)
    body = f"""<div class="wrap page-head"><div class="label">Setup</div><h1>Connect your AI</h1>
<p class="lede">Your private link is in your welcome email. No key yet? Connect <code>{e(settings.mcp_url)}</code> to use {e(free_names)} for free.</p></div>
<div class="wrap"><section>{_setup_blocks(settings.mcp_url + "?key=YOUR_KEY")}</section>
<section><div class="cols"><div style="display:grid;gap:12px"><div class="label">Then</div><h2>Ask as you normally would</h2></div>
<div style="display:grid;gap:12px"><p class="quote">“Write a 4-step cold email sequence for CFOs at 50 to 200 person SaaS companies.”</p>
<p style="color:var(--muted)">Your AI picks the agent, follows its playbook and runs its tools. On large plans it finds agents with <code>hundred_find_agent</code>.
To keep a connection focused, add <code>&amp;agents=cold-email,lead-qualifier</code> to the link.</p></div></div></section></div>"""
    return layout(f"Setup · {settings.brand}", body)


def offer_card(offer, fields: dict[str, str]) -> str:
    """The post-purchase All-Access offer. Big value, plain terms, one click."""
    from .upsell import money

    n = len(registry.all_agents())
    hidden = "".join(f'<input type="hidden" name="{k}" value="{e(v)}">' for k, v in fields.items())
    extra = offer.extra_cents
    delta = f"{money(extra)} a month more than you pay now" if extra > 0 else "the price you pay now"
    return f"""<div class="offer"><div class="label timer">One-time offer · not on our pricing page · expires in 48 hours</div>
<h2>Get all {n} agents for {delta}.</h2>
<p style="color:var(--muted)">Every agent we've built, plus every agent we ship next.</p>
<div><span class="was">{money(offer.list_cents)}</span><span class="now">{money(offer.offer_cents)}</span><span class="per"> /mo · {offer.percent_off}% off, locked for life</span></div>
<form method="post" action="/upsell/accept">{hidden}
<button class="btn block">Yes, upgrade me to all {n} agents for {money(offer.offer_cents)}/mo</button></form>
<p class="terms">Replaces your current plan, so you won't pay for both. Billed {money(offer.offer_cents)} every month to the card you just used,
starting when your free trial ends. Cancel anytime in <a href="/account">Account</a>. Your link stays the same and new agents appear automatically.</p>
<p class="terms"><a href="#setup">No thanks, I'll keep my plan</a></p></div>"""


def offer_page(offer, fields: dict[str, str]) -> str:
    body = f'<div class="wrap page-head">{offer_card(offer, fields)}</div>'
    return layout(f"Your upgrade offer · {settings.brand}", body)


def upgraded_page(price: str) -> str:
    n = len(registry.all_agents())
    body = f"""<div class="wrap page-head"><div class="label" style="color:var(--teal)">Upgraded</div>
<h1>All {n} agents are live.</h1><p class="lede">They're already on the link you set up. {e(price)} a month, locked for life.</p>
<div class="actions"><a class="btn" href="/setup">Open the setup guide</a></div></div>"""
    return layout(f"Upgraded · {settings.brand}", body)


def welcome_page(key: str | None, offer=None, offer_fields: dict[str, str] | None = None) -> str:
    if key:
        url = f"{settings.mcp_url}?key={key}"
        top = f"""<div class="label" style="color:var(--teal)">Payment received</div><h1>You're in.</h1>
<p class="lede">This is your private MCP link. It's shown here once and it's also in your email. Keep it private, like a password.</p>
<div class="keybox">{e(url)}</div>"""
        blocks = _setup_blocks(url)
    else:
        top = """<div class="label" style="color:var(--teal)">Payment received</div><h1>Finishing setup</h1>
<p class="lede">Your key is on its way to your inbox, usually within a minute. If you already opened this page once, the key is only in the email now.
Nothing after 5 minutes? Use <a href="/account">Account → recover key</a>.</p>"""
        blocks = _setup_blocks(settings.mcp_url + "?key=YOUR_KEY")
    upsell_html = offer_card(offer, offer_fields or {}) if offer else ""
    body = f"""<div class="wrap page-head">{top}</div>
<div class="wrap">{upsell_html}<section id="setup" aria-labelledby="setup-h"><div class="section-head"><div class="label">Setup</div>
<h2 id="setup-h">Add your link to your AI</h2></div>{blocks}</section></div>"""
    return layout(f"Welcome · {settings.brand}", body)


def account_page(error: str = "", notice: str = "") -> str:
    msg = f'<div class="notice" role="status">{e(error or notice)}</div>' if (error or notice) else ""
    body = f"""<div class="wrap page-head"><div class="label">Account</div><h1>Billing and keys</h1>{msg}</div>
<div class="wrap"><div class="cols">
<div class="box"><h3>Update card, change plan or cancel</h3><p style="color:var(--muted)">Paste your key: the part of your link after <code>key=</code>.</p>
<form method="post" class="field"><input type="hidden" name="action" value="portal"><label class="label" for="acct-key">License key</label>
<input type="text" id="acct-key" name="key" placeholder="hnd_live_…" required autocomplete="off"><button class="btn">Open billing portal</button></form></div>
<div class="box"><h3>Lost your key?</h3><p style="color:var(--muted)">We'll email a new key to the address on your subscription. The old key stops working.</p>
<form method="post" class="field"><input type="hidden" name="action" value="recover"><label class="label" for="acct-email">Email</label>
<input type="email" id="acct-email" name="email" placeholder="you@company.com" required autocomplete="email"><button class="btn line">Email me a new key</button></form></div>
</div></div>"""
    return layout(f"Account · {settings.brand}", body)


def message_page(title: str, message: str, back: str = "/") -> str:
    body = f"""<div class="wrap page-head"><h1>{e(title)}</h1><p class="lede">{e(message)}</p>
<div class="actions"><a class="btn line" href="{e(back)}">Go back</a></div></div>"""
    return layout(f"{title} · {settings.brand}", body)
