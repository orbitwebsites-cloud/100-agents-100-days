"""Recipes: multi-agent workflows no single-purpose tool can run.

A standalone tool does one job: Lavender scores the email, Clari forecasts the
pipeline, Float forecasts the cash. A recipe chains our agents in the order a
practitioner would, and names what each step hands to the next. The customer's
AI runs the steps; shared context is saved to memory so the chain survives
across chats and days.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import registry


@dataclass(frozen=True)
class Step:
    agent: str
    does: str
    hands_on: str  # what this step's output gives the next step


@dataclass(frozen=True)
class Recipe:
    slug: str
    name: str
    goal: str
    when: tuple[str, ...]
    steps: tuple[Step, ...]


RECIPES: tuple[Recipe, ...] = (
    Recipe("launch-product", "Launch a product",
           "Take a product from positioning to launch day with one consistent message.",
           ("launch", "go to market", "new product", "announce"),
           (Step("positioning-strategist", "Pick the category, alternatives and the one differentiated value", "positioning statement"),
            Step("persona-builder", "Turn customer evidence into the buyer the message targets", "persona + jobs-to-be-done"),
            Step("landing-page-cro", "Write and audit the launch page against the positioning", "approved headline and proof points"),
            Step("ad-copy-lab", "Cut platform-valid ads from the approved headline", "ad variants per platform"),
            Step("email-campaign", "Write the announcement and follow-up emails", "email sequence + send schedule"),
            Step("press-release", "Draft the release and the embargoed pitch", "release + media timing"),
            Step("launch-planner", "Put every asset on one dated countdown with owners", "launch calendar + go/no-go"))),
    Recipe("after-sales-call", "After a sales call",
           "Turn a call into CRM updates, a follow-up that gets answered and an honest forecast.",
           ("sales call", "discovery call", "demo", "debrief"),
           (Step("sales-call-debrief", "Extract next steps, buying signals and CRM fields", "deal update"),
            Step("follow-up-machine", "Write and schedule the follow-up for the agreed next step", "dated follow-up"),
            Step("pipeline-forecaster", "Re-weight the deal and the quarter's commit", "updated forecast"))),
    Recipe("outbound-campaign", "Outbound campaign",
           "Go from a raw lead list to a scheduled multi-channel sequence.",
           ("outbound", "prospecting", "lead list", "cold outreach"),
           (Step("lead-qualifier", "Score and tier the list against the ICP", "A/B-tier leads"),
            Step("linkedin-prospector", "Find the hook per lead and plan LinkedIn touches", "hooks + LinkedIn plan"),
            Step("cold-email", "Write, score and schedule the email sequence", "sequence with send dates"),
            Step("follow-up-machine", "Plan follow-ups that add something new each time", "follow-up cadence"))),
    Recipe("close-a-deal", "Close a deal",
           "Handle the last objections, negotiate terms and get a clean contract signed.",
           ("close", "negotiate", "late-stage deal", "procurement"),
           (Step("objection-handler", "Classify and answer the open objections", "resolved objections + ROI case"),
            Step("negotiation-coach", "Set the anchor, concession ladder and walk-away", "negotiation plan"),
            Step("proposal-builder", "Build the priced proposal and payment schedule", "proposal"),
            Step("contract-reviewer", "Check the customer's paper for red flags and deadlines", "redlines + renewal dates"))),
    Recipe("month-end-numbers", "Month-end numbers",
           "Categorise the month, forecast cash, check unit economics and write the investor update.",
           ("month end", "monthly close", "investor update", "board"),
           (Step("expense-categorizer", "Categorise the bank export and find recurring costs", "categorised spend"),
            Step("cashflow-forecaster", "Roll the 13-week cash forecast forward", "cash forecast + runway"),
            Step("unit-economics", "Recompute LTV, CAC, payback and retention", "unit economics"),
            Step("investor-update", "Write the update with exact month-over-month deltas", "investor update"))),
    Recipe("raise-a-round", "Raise a round",
           "Size the raise from the model and build a deck that survives diligence.",
           ("fundraise", "raise", "seed", "series a", "pitch deck"),
           (Step("startup-model", "Project revenue, hiring and burn; size the raise", "raise amount + runway"),
            Step("pitch-deck-coach", "Check the deck's story, market size and dilution math", "deck fixes"),
            Step("investor-update", "Draft the outreach update with traction numbers", "investor email"))),
    Recipe("publish-and-repurpose", "Publish and repurpose",
           "Write one strong article, make it rank, then turn it into a month of posts.",
           ("blog", "article", "content plan", "repurpose"),
           (Step("blog-writer", "Plan and draft the article to a word budget", "draft"),
            Step("copy-editor", "Tighten the draft and prove the readability gain", "final article"),
            Step("meta-writer", "Write the title and description that fit the SERP", "meta tags"),
            Step("schema-markup", "Generate valid Article/FAQ JSON-LD", "structured data"),
            Step("content-repurposer", "Cut platform-sized posts from the article", "post set"),
            Step("content-calendar", "Schedule the posts across platforms", "posting calendar"))),
    Recipe("fix-seo", "Fix a page's SEO",
           "Audit a page, re-target it and fix its snippet and structured data.",
           ("seo", "rankings", "organic traffic", "audit"),
           (Step("seo-auditor", "Audit the page and rank the fixes", "fix list"),
            Step("keyword-strategist", "Choose the target cluster and intent", "target keywords"),
            Step("meta-writer", "Rewrite title and description for the target", "meta tags"),
            Step("schema-markup", "Add or repair structured data", "JSON-LD"))),
    Recipe("hire-someone", "Hire someone",
           "Write a fair job post, run a structured loop and onboard the hire.",
           ("hiring", "recruit", "job post", "interview loop"),
           (Step("job-description", "Write an inclusive posting with a salary band", "job post"),
            Step("hiring-scorecard", "Build the rubric and interview loop; score candidates", "hire decision"),
            Step("onboarding-planner", "Plan pre-boarding and the first 90 days with dates", "onboarding plan"))),
    Recipe("land-a-job", "Land a job",
           "Tailor the application, prepare the interviews and negotiate the offer.",
           ("job search", "apply", "job application", "offer"),
           (Step("resume-optimizer", "Match the resume to the posting", "tailored resume"),
            Step("cover-letter", "Cover the top requirements with evidence", "cover letter"),
            Step("interview-coach", "Build STAR stories and a prep schedule", "interview prep"),
            Step("salary-negotiator", "Compare offers and plan the counter", "counter-offer script"))),
    Recipe("ship-a-feature", "Ship a feature",
           "From spec to merged code with accessible, well-written UI.",
           ("feature", "spec", "prd", "ship"),
           (Step("prd-writer", "Write a complete PRD with testable requirements", "PRD"),
            Step("roadmap-prioritizer", "Confirm it beats the alternatives on RICE", "priority call"),
            Step("ux-writer", "Write and lint the interface copy", "UI strings"),
            Step("accessibility-checker", "Check contrast, labels and target sizes", "a11y fixes"),
            Step("test-writer", "Generate edge-case tests for the new code", "tests"),
            Step("code-reviewer", "Review the diff before merge", "review"),
            Step("commit-crafter", "Write commits and the changelog entry", "release notes"))),
    Recipe("handle-an-incident", "Handle an incident",
           "Find the cause, run the response and tell stakeholders.",
           ("incident", "outage", "production bug", "postmortem"),
           (Step("bug-hunter", "Parse the traces and logs to the likely cause", "root-cause hypothesis"),
            Step("incident-commander", "Grade severity, time the response and write the postmortem", "postmortem"),
            Step("status-reporter", "Report status and follow-ups to stakeholders", "status update"))),
    Recipe("grow-a-store", "Grow a store",
           "Find the funnel leak, fix pricing and listings, then automate retention email.",
           ("ecommerce", "store", "shopify", "conversion"),
           (Step("store-cro", "Find the biggest funnel leak and test plan", "priority fix"),
            Step("ecom-pricing", "Check true margin, discount break-even and price position", "pricing plan"),
            Step("product-listing", "Rewrite the top listings within marketplace limits", "listings"),
            Step("email-flows", "Time the cart, welcome and win-back flows from real cycles", "flow schedule"))),
    Recipe("meeting-to-done", "Meeting to done",
           "Turn a meeting into owned tasks, a real schedule and a weekly status.",
           ("meeting", "project kickoff", "action items"),
           (Step("meeting-ops", "Extract decisions and owned, dated action items", "task list"),
            Step("project-planner", "Schedule the tasks and find the critical path", "project plan"),
            Step("status-reporter", "Report progress against the plan each week", "status report"))),
    Recipe("freelance-client", "Freelance client, start to paid",
           "Contract the work, get paid on time and set aside the tax.",
           ("freelance", "client", "contractor"),
           (Step("freelance-contract", "Price the work and set milestones and scope limits", "contract + schedule"),
            Step("invoice-chaser", "Track invoices and chase late payment politely", "collections plan"),
            Step("freelance-tax", "Estimate quarterly tax and the amount to set aside", "tax set-aside"))),
)

BY_SLUG = {r.slug: r for r in RECIPES}


def find(goal: str, limit: int = 5) -> list[Recipe]:
    terms = [t for t in re.findall(r"[a-z0-9]+", (goal or "").lower()) if len(t) > 2]
    if not terms:
        return list(RECIPES)
    scored = []
    for r in RECIPES:
        hay = " ".join([r.slug, r.name, r.goal, " ".join(r.when)]).lower()
        score = sum(3 if t in " ".join(r.when) else 1 for t in terms if t in hay)
        if score:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limit]]


def plan(recipe: Recipe, owned: set[str]) -> dict:
    agents = registry.all_agents()
    steps = []
    for i, st in enumerate(recipe.steps, 1):
        a = agents.get(st.agent)
        steps.append({
            "step": i,
            "agent": st.agent,
            "name": a.name if a else st.agent,
            "does": st.does,
            "hands_on": st.hands_on,
            "owned": st.agent in owned,
        })
    missing = [s["name"] for s in steps if not s["owned"]]
    return {
        "recipe": recipe.slug,
        "name": recipe.name,
        "goal": recipe.goal,
        "steps": steps,
        "missing_agents": missing,
        "how_to_run": (
            "Run the steps in order. For each step, start that agent, pass it the previous step's output, and "
            f"save the step's result with hundred_memory (action 'save', name 'recipe/{recipe.slug}/<step>') so "
            "the chain can resume in a later chat. Show the user the final deliverable and a one-line summary per step."
        ),
    }
