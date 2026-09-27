"""What each agent should remember between chats.

The evaluations found the same structural gap again and again: the paid tools
keep history (Fitbod your lifts, Anki your card state, WRITER your voice, Clari
last week's pipeline) and a stateless agent starts from zero every time. Memory
closes it. The customer's AI saves small JSON notes through ``hundred_memory``,
scoped to the customer's key, only when it decides a result is worth keeping,
and can list or delete them at any time.
"""

from __future__ import annotations

MAX_ENTRIES = 300
MAX_VALUE_BYTES = 48_000
NAME_RE = r"^[a-z0-9][a-z0-9._/-]{0,119}$"

# slug -> (what to keep, suggested memory name)
HINTS: dict[str, tuple[str, str]] = {
    "brand-voice": ("the voice profile, banned/preferred terms and approved samples", "brand-voice/<brand>"),
    "lead-qualifier": ("the ICP weights (from calibrate_weights) and tier cut-offs", "lead-qualifier/icp"),
    "cold-email": ("the persona, offer, proof points and the best-scoring subject lines", "cold-email/<campaign>"),
    "pipeline-forecaster": ("last week's weighted pipeline snapshot, so pipeline_changes can diff it", "pipeline/<yyyy-ww>"),
    "follow-up-machine": ("each open deal's touches sent and next date", "follow-ups/<deal>"),
    "fitness-coach": ("current 1RMs, the training block and each session's top sets", "fitness/log"),
    "meal-planner": ("dietary rules, macro targets, pantry staples and liked recipes", "meals/profile"),
    "study-coach": ("each card's SM-2 state (interval, ease, due date) and the exam date", "study/<deck>"),
    "content-calendar": ("pillars, posting capacity and what was posted when", "content-calendar/<brand>"),
    "expense-categorizer": ("the merchant → category rules the user corrected", "expenses/rules"),
    "cashflow-forecaster": ("the recurring inflows/outflows and last forecast", "cashflow/baseline"),
    "unit-economics": ("last period's metrics for trend lines", "unit-economics/<yyyy-mm>"),
    "investor-update": ("last month's KPI table, so deltas are exact", "investor-update/<yyyy-mm>"),
    "status-reporter": ("last week's status and milestones, for week-over-week deltas", "status/<project>/<yyyy-ww>"),
    "okr-coach": ("the quarter's OKRs, baselines and weekly check-ins", "okrs/<quarter>"),
    "project-planner": ("the task list, dependencies and baseline dates", "project/<name>"),
    "interview-synthesizer": ("the tag taxonomy and per-interview tags, so saturation builds across rounds", "research/<study>"),
    "feedback-analyzer": ("last period's NPS and theme counts", "feedback/<yyyy-mm>"),
    "roadmap-prioritizer": ("the scored backlog and the scoring weights", "roadmap/backlog"),
    "resume-optimizer": ("the master resume and target roles", "career/resume"),
    "salary-negotiator": ("offers received and the negotiation state", "career/offers"),
    "hiring-scorecard": ("the rubric and each candidate's ratings", "hiring/<role>"),
    "sponsorship-pricer": ("the rate card and recent deal terms", "sponsorships/rate-card"),
    "inventory-planner": ("each SKU's lead time, service level and last reorder", "inventory/<sku>"),
    "store-cro": ("the funnel baseline and running tests", "store-cro/funnel"),
    "invoice-chaser": ("open invoices and the touches already sent", "invoices/open"),
    "time-blocker": ("working hours, timezone and focus preferences", "time-blocker/profile"),
    "meeting-ops": ("open action items across meetings, so the next meeting starts from them", "meetings/open-items"),
}


def briefing_section(slug: str) -> str:
    what, name = HINTS.get(slug, ("reusable results the user will want next time (profiles, settings, baselines)",
                                  f"{slug}/<topic>"))
    return (
        "## Memory\n"
        f"Before starting, check for saved context: call `hundred_memory` with action `list` and prefix "
        f"`{name.split('/')[0]}/`, then `get` what applies. After finishing, offer to save {what} "
        f"(action `save`, name like `{name}`) so the next chat starts from it. Save only what the user agrees to; "
        "never save secrets or card numbers."
    )
