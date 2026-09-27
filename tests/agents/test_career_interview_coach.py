"""Interview Coach tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("interview-coach")

STORY = (
    "At Beta, our largest customer was threatening to churn after a failed migration; that account was 18% of ARR. "
    "My job was to save the renewal in six weeks while engineering was slammed. I decided to get in front of the CTO "
    "myself rather than wait for a fix. I mapped every open issue, then I negotiated a phased migration with weekly "
    "checkpoints, and I convinced our head of engineering to assign one dedicated engineer. I also drafted a shared "
    "status doc so the customer saw progress daily. As a result, they renewed for 3 years at a 12% higher contract "
    "value, and the checkpoint format became our standard for enterprise migrations. Looking back, I now escalate to "
    "the executive sponsor in week one instead of week three."
)


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_check_star_story_scores_structure_and_ownership():
    out = call("check_star_story", story=STORY)
    assert out["score"] >= 80
    assert out["ownership"]["i_in_action"] > out["ownership"]["we_in_action"]
    assert out["result_quantified"] is True and out["reflection_present"] is True
    assert 40 <= out["word_share_pct"]["A"] <= 60
    assert "12%" in out["segments"]["R"]
    weak = call("check_star_story", story="We had a big project. We all worked hard together and it went really well and everyone was happy.")
    assert weak["score"] < 30
    assert "Result has no number" in weak["issues"] and "no Action detected" in weak["issues"]


def test_check_star_story_rejects_bad_target():
    with pytest.raises(ToolError):
        call("check_star_story", story=STORY, target_seconds=5)


def test_question_bank_is_deterministic_and_role_aware():
    a = call("question_bank", role_family="Senior PM", level="senior", count=12)
    b = call("question_bank", role_family="Senior PM", level="senior", count=12)
    assert a == b
    assert a["role_family"] == "product" and a["count"] == 12
    assert a["coverage"]["role:product"] == 3
    assert {q["competency"] for q in a["questions"]} >= {"ownership", "ambiguity", "influence", "conflict", "failure"}
    assert all(q["strong"] and q["red_flags"] for q in a["questions"])
    lead = call("question_bank", role_family="engineering manager", level="lead", count=8)
    assert lead["role_family"] == "engineering" and "leadership" in lead["coverage"]


def test_question_bank_rejects_unknown_competency():
    with pytest.raises(ToolError):
        call("question_bank", role_family="sales", competencies=["charisma"])


def test_lint_answer_counts_fillers_and_ownership():
    out = call(
        "lint_answer",
        answer="So um basically I think we kind of just, you know, worked on the thing and it was really good and actually we like shipped it and it was fine and everyone was happy and stuff and then we moved on to the next project after that which was also big.",
        question="Tell me about a project you shipped",
        max_seconds=60,
    )
    terms = {f["term"]: f["count"] for f in out["fillers"]}
    assert terms["um"] == 1 and terms["you know"] == 1 and terms["kind of"] == 1
    assert out["filler_pct"] > 15
    assert out["ownership"]["we"] > out["ownership"]["i"]
    assert out["number_present"] is False
    assert len(out["run_on_sentences"]) == 1
    assert out["score"] < 60
    assert out["word_budget"] == 150


def test_lint_answer_rejects_empty():
    with pytest.raises(ToolError):
        call("lint_answer", answer="")


def test_plan_prep_schedule_dates_and_light_day_before():
    out = call("plan_prep_schedule", interview_date="2026-10-05", start_date="2026-09-27", hours_per_day=2)
    assert out["days_before_interview"] == 8 and out["compressed"] is False
    assert out["schedule"][0] == {"date": "2026-09-27", "weekday": "Sun", "focus": "Research", "hours": 2.0, "tasks": out["schedule"][0]["tasks"], "done_when": out["schedule"][0]["done_when"]}
    light = [r for r in out["schedule"] if r["date"] == "2026-10-04"]
    assert light and light[0]["focus"].startswith("Light review")
    assert out["schedule"][-1]["date"] == "2026-10-05" and out["schedule"][-1]["focus"] == "Interview day"
    assert all(r["hours"] <= 2.0 for r in out["schedule"])
    same_day = call("plan_prep_schedule", interview_date="2026-09-27", start_date="2026-09-27")
    assert same_day["schedule"][0]["focus"] == "Same-day essentials"


def test_plan_prep_schedule_rejects_past_interview():
    with pytest.raises(ToolError):
        call("plan_prep_schedule", interview_date="2026-09-20", start_date="2026-09-27")


def test_check_star_story_flags_we_heavy_action():
    story = ("At Acme our churn was 8 percent. We needed to cut it. So we pulled the data and we interviewed ten customers. "
             "We decided to rebuild onboarding and we launched it in May. As a result churn fell to 5 percent.")
    out = call("check_star_story", story=story)
    assert out["ownership"]["we_in_action"] > out["ownership"]["i_in_action"] == 0
    assert any("'we'" in i for i in out["issues"])


def test_lint_answer_flags_non_inclusive_wording():
    out = call("lint_answer", answer="The guys on my team thought the plan was insane, so I ran a sanity check and cut scope 30 percent.")
    assert {h["term"] for h in out["non_inclusive"]} == {"guys", "insane", "sanity check"}
