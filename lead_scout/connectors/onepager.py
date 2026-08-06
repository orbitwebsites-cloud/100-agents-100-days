"""One-pager connector — renders the audit as a leave-behind you can send.

No API needed and nothing dry-run about it: this writes a real, openable HTML
file to `out/`, branded with your agency name, that you can attach to the pitch
or drop into Canva as the basis for a designed version.
"""

import html
import re
from datetime import date
from pathlib import Path

from .. import config

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "out"

_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 16px/1.6 -apple-system, Segoe UI, Roboto, sans-serif;
         max-width: 46rem; margin: 3rem auto; padding: 0 1.25rem; }}
  .score {{ font-size: 3.5rem; font-weight: 700; line-height: 1; }}
  .meta {{ opacity: .7; font-size: .9rem; }}
  li {{ margin: .4rem 0; }}
  .crit::marker {{ content: "🔴 "; }}
  .warn::marker {{ content: "🟡 "; }}
  .note::marker {{ content: "⚪ "; }}
  ul {{ padding-left: 1.4rem; }}
  footer {{ margin-top: 3rem; font-size: .85rem; opacity: .7; }}
</style>
<h1>{title}</h1>
<p class="meta">{url} · audited {today}</p>
<p class="score">{score}<span style="font-size:1.2rem;opacity:.6">/100</span></p>
<p>{summary}</p>
<h2>What we found</h2>
<ul>
{items}
</ul>
<footer>Prepared by {agency} · measurements taken live on {today}.</footer>
"""

_CLASS = {"critical": "crit", "warning": "warn", "note": "note"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "prospect"


def create_onepager(company: str, url: str, score: int, summary: str, findings: list) -> str:
    """Write the audit one-pager. `findings` is the audit's findings list."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{_slug(company or url)}-audit.html"

    items = "\n".join(
        f'<li class="{_CLASS.get(f.get("severity", "note"), "note")}">{html.escape(str(f.get("message", "")))}</li>'
        for f in findings
    ) or "<li>No issues found.</li>"

    path.write_text(
        _TEMPLATE.format(
            title=html.escape(f"Website audit — {company or url}"),
            url=html.escape(url),
            today=date.today().isoformat(),
            score=score,
            summary=html.escape(summary),
            items=items,
            agency=html.escape(config.AGENCY_NAME),
        ),
        encoding="utf-8",
    )
    print(f"   📄 [One-pager] wrote {path}")
    return str(path)
