"""Ops category — replayable evaluation scenarios (see evals/ops.md).

Each test replays a realistic customer request through the agent's tools, exactly as the
customer's AI would call them, and asserts values that were verified independently
(hand CPM, stdlib zoneinfo, brute-force sweeps, hand TCO/SLA math) during the evaluation.
"""

from pathlib import Path

from hundred import registry

ROOT = Path(__file__).resolve().parents[2]


def run(slug, tool, **kwargs):
    agent = registry.get(slug)
    assert agent is not None, slug
    return agent.get_tool(tool).call(kwargs)


# ─────────────────────────── meeting-ops (free lead magnet) ───────────────────────────

LAUNCH_SYNC = "Launch Sync - Oct 7, 2026 (Wednesday)\nAttendees: Priya Shah, Jordan Lee, Mei Chen, Aisha Bello, Carlos Ruiz, Dev Patel\nRecording: otter.ai export\n\nPriya Shah  0:00\nOkay, um, can everyone hear me? Carlos, you're on mute I think. Yeah. Okay. So the main thing today is the launch on the fifteenth and the Acme renewal, and I want to leave with owners for everything, because last week we, uh, didn't.\n\nJordan Lee  0:41\nSure. So SSO. We did the bake-off. Honestly Auth0 was nicer to integrate but the pricing at our tier is brutal. Okta's fine.\n\nMei Chen  1:02\nAcme specifically asked for Okta, for what it's worth. Their IT team only supports Okta.\n\nPriya Shah  1:10\nThen let's go with Okta. Final call, we're not reopening that.\n\nJordan Lee  1:15\nWorks for me. The login bug Acme hit is still open though, the redirect loop. I'll have the SSO fix in staging by EOD Thursday.\n\nPriya Shah  1:31\nGreat. And the launch date, are we still good for the fifteenth? I was wondering if we should push to the twentieth to give QA room.\n\nAisha Bello  1:44\nI'd rather not move it, marketing has the email scheduled.\n\nPriya Shah  1:50\nYeah, okay, let's keep the fifteenth. Launch stays October 15th.\n\nMei Chen  2:05\nOn Acme, the renewal is up at end of month and they want a proposal with the multi-year discount. I'll send the renewal proposal to Acme by Friday.\n\nPriya Shah  2:20\nPerfect. Do we need legal to look at their DPA redlines?\n\nJordan Lee  2:26\nProbably. Someone should ping legal about the DPA, I don't know who owns that relationship now.\n\nPriya Shah  2:33\nHm. Let's figure that out offline. [crosstalk]\n\nCarlos Ruiz  2:40\nCan I jump in? For the migration I can write the runbook, it's mostly the cutover steps.\n\nPriya Shah  2:52\nWait, Carlos, aren't you out next week? The runbook has to be done before cutover. Aisha, can you take the runbook instead?\n\nAisha Bello  3:01\nYeah, I'll take it. Next Tuesday works for me.\n\nCarlos Ruiz  3:05\nFair, I'm out Monday to Friday. I'll send Aisha my notes. Sorry, I'll just leave them in the doc.\n\nPriya Shah  3:14\nThanks. Dev, churn numbers for the board deck?\n\nDev Patel  3:20\nI'll pull the Q3 churn cohort numbers by Monday. Also I can do the refresh of the legacy analytics dashboard this week, actually no, scratch that, we're killing that dashboard anyway right?\n\nPriya Shah  3:36\nYes. We're killing the legacy dashboard, it gets turned off end of month. Nobody refresh it. And I'll update the board deck with the new churn numbers by October 15th.\n\nJordan Lee  3:50\nWe should maybe someday rebuild the whole admin panel, it's held together with tape.\n\nPriya Shah  3:55\nHa, someday. Not this quarter.\n\nJordan Lee  4:01\nAlso for the load test, I'll book the load test environment tomorrow, it needs a day's notice.\n\nPriya Shah  4:10\nGood. Jordan, can you send me the deploy notes once the fix is out?\n\nJordan Lee  4:15\nYep, will do.\n\nAisha Bello  4:18\nAnd I'll set up the launch retro for end of next week so it's on everyone's calendar.\n\nPriya Shah  4:25\nGreat. Last thing, enterprise tier pricing, we still haven't landed on per-seat versus flat. Let's revisit that when we have the Acme numbers. Okay, I think that's it. Thanks all.\n"

# Ground truth planted in LAUNCH_SYNC: (line, owner, due) for every real commitment.
LAUNCH_ACTIONS = {
    18: ("Jordan Lee", "2026-10-08"),  # SSO fix in staging by EOD Thursday
    30: ("Mei Chen", "2026-10-09"),  # renewal proposal to Acme by Friday
    48: ("Aisha Bello", "2026-10-13"),  # runbook: reassigned from Carlos, "next Tuesday"
    51: ("Carlos Ruiz", None),  # leave migration notes in the doc (no date)
    57: ("Dev Patel", "2026-10-12"),  # Q3 churn cohort numbers by Monday
    60: ("Priya Shah", "2026-10-15"),  # board deck by October 15th
    69: ("Jordan Lee", "2026-10-08"),  # book load-test env tomorrow
    75: ("Jordan Lee", None),  # deploy notes "once the fix is out" -> no date
    78: ("Aisha Bello", "2026-10-16"),  # launch retro end of next week
}
NOT_ACTIONS = {66}  # "we should maybe someday rebuild the admin panel"
DECISION_LINES = {15, 27, 60}  # Okta; launch stays Oct 15; kill legacy dashboard


def test_meeting_ops_standup_sample_speakers_and_dates():
    t = (ROOT / "samples" / "standup_transcript.txt").read_text()
    out = run("meeting-ops", "transcript_stats", transcript=t)
    assert sorted(out["speakers"]) == ["Dana", "Marcus", "Priya"]  # "Attendees:" is a header, not a speaker
    real = {6, 10, 14, 16, 18, 20}  # PR by Wed, pull tokens, device pass, exec update, deploy notes, A/B meeting
    assert real <= {c["line"] for c in out["commitment_candidates"]}
    dates = run("meeting-ops", "resolve_due_dates", phrases=["by Wednesday", "tomorrow", "by end of day Thursday", "as soon as it's merged"], meeting_date="2026-09-28")
    got = [r["due"] for r in dates["resolved"]]
    assert got == ["2026-09-30", "2026-09-29", "2026-10-01", None]  # was 2026-09-28 for "end of day Thursday" before the fix


def test_meeting_ops_messy_otter_export_recall_and_dates():
    out = run("meeting-ops", "transcript_stats", transcript=LAUNCH_SYNC)
    assert sorted(out["speakers"]) == ["Aisha Bello", "Carlos Ruiz", "Dev Patel", "Jordan Lee", "Mei Chen", "Priya Shah"]
    assert out["detected_meeting_date"] == "2026-10-07"
    cand = {c["line"] for c in out["commitment_candidates"]}
    assert set(LAUNCH_ACTIONS) <= cand  # recall 9/9
    assert not (NOT_ACTIONS & cand)
    assert DECISION_LINES <= {c["line"] for c in out["decision_candidates"]}
    assert 57 in {c["line"] for c in out["retractions"]}  # "scratch that" on the dashboard refresh
    by_line = {c["line"]: c["speaker"] for c in out["commitment_candidates"]}
    assert by_line[48] == "Aisha Bello" and by_line[42] == "Carlos Ruiz"  # the reassignment is visible
    res = run("meeting-ops", "resolve_due_dates", meeting_date="2026-10-07", phrases=["by EOD Thursday", "by Friday", "Next Tuesday", "by Monday", "by October 15th", "tomorrow", "end of next week", "once the fix is out", "end of month"])
    assert [r["due"] for r in res["resolved"]] == ["2026-10-08", "2026-10-09", "2026-10-13", "2026-10-12", "2026-10-15", "2026-10-08", "2026-10-16", None, "2026-10-31"]


def test_meeting_ops_final_action_list_matches_ground_truth():
    items = [
        {"task": "Ship the SSO redirect-loop fix to staging", "owner": "Jordan Lee", "due": "2026-10-08"},
        {"task": "Send the Acme renewal proposal with the multi-year discount", "owner": "Mei Chen", "due": "2026-10-09"},
        {"task": "Write the migration cutover runbook", "owner": "Aisha Bello", "due": "2026-10-13"},
        {"task": "Pull the Q3 churn cohort numbers", "owner": "Dev Patel", "due": "2026-10-12"},
        {"task": "Update the board deck with the new churn numbers", "owner": "Priya Shah", "due": "2026-10-15"},
        {"task": "Book the load-test environment", "owner": "Jordan Lee", "due": "2026-10-08"},
        {"task": "Send Priya the deploy notes after the SSO fix ships", "owner": "Jordan Lee", "due": ""},
        {"task": "Schedule the launch retro", "owner": "Aisha Bello", "due": "2026-10-16"},
        {"task": "Leave migration notes in the runbook doc for Aisha", "owner": "Carlos Ruiz", "due": ""},
    ]
    out = run("meeting-ops", "format_action_items", items=items)
    assert out["ready_to_file"] is True and len(out["items"]) == 9
    assert sorted((i["owner"], i["due"]) for i in out["items"]) == sorted(LAUNCH_ACTIONS.values())
    undated = [i["n"] for i in out["items"] if any("no due date" in x for x in i["issues"])]
    assert undated == [7, 9]  # flagged, never guessed
    assert "Carlos Ruiz" not in [i["owner"] for i in out["items"] if "runbook" in i["task"].lower() and "notes" not in i["task"].lower()]


# ─────────────────────────── project-planner ───────────────────────────

PORTAL_TASKS = [
    {
        "id": "T1",
        "name": "Requirements sign-off",
        "duration": 3,
        "depends_on": [],
        "owner": "Priya"
    },
    {
        "id": "T2",
        "name": "UX design",
        "duration": 5,
        "depends_on": [
            "T1"
        ],
        "owner": "Dana"
    },
    {
        "id": "T3",
        "name": "API spec",
        "duration": 2,
        "depends_on": [
            "T1"
        ],
        "owner": "Marcus"
    },
    {
        "id": "T4",
        "name": "Backend build",
        "duration": 8,
        "depends_on": [
            "T3"
        ],
        "owner": "Marcus"
    },
    {
        "id": "T5",
        "name": "Frontend build",
        "duration": 7,
        "depends_on": [
            "T2",
            "T3"
        ],
        "owner": "Lena"
    },
    {
        "id": "T6",
        "name": "Okta SSO integration",
        "duration": 4,
        "depends_on": [
            "T3"
        ],
        "owner": "Raj"
    },
    {
        "id": "T7",
        "name": "Data migration scripts",
        "duration": 5,
        "depends_on": [
            "T4"
        ],
        "owner": "Marcus"
    },
    {
        "id": "T8",
        "name": "Integration testing",
        "duration": 4,
        "depends_on": [
            "T5",
            "T6",
            "T7"
        ],
        "owner": "QA"
    },
    {
        "id": "T9",
        "name": "Security review",
        "duration": 3,
        "depends_on": [
            "T6"
        ],
        "owner": "Raj"
    },
    {
        "id": "T10",
        "name": "Help-center docs",
        "duration": 3,
        "depends_on": [
            "T5"
        ],
        "owner": "Dana"
    },
    {
        "id": "T11",
        "name": "UAT with pilot customers",
        "duration": 4,
        "depends_on": [
            "T8",
            "T9"
        ],
        "owner": "Priya"
    },
    {
        "id": "T12",
        "name": "Portal v2 live",
        "duration": 0,
        "depends_on": [
            "T11",
            "T10"
        ],
        "owner": "Priya"
    }
]
HOLIDAYS = ["2026-11-26", "2026-11-27", "2026-12-25"]
CHAIN = [("T1", 2, 3, 5), ("T3", 1, 2, 4), ("T4", 6, 8, 14), ("T7", 3, 5, 10), ("T8", 3, 4, 8), ("T11", 3, 4, 7)]


def test_project_planner_cpm_matches_hand_calculation():
    out = run("project-planner", "critical_path", tasks=PORTAL_TASKS)
    assert out["project_duration_days"] == 26
    assert out["critical_path"] == ["T1", "T3", "T4", "T7", "T8", "T11", "T12"]
    tf = {t["id"]: t["total_float"] for t in out["tasks"]}
    ff = {t["id"]: t["free_float"] for t in out["tasks"]}
    assert tf == {"T1": 0, "T2": 3, "T3": 0, "T4": 0, "T5": 3, "T6": 9, "T7": 0, "T8": 0, "T9": 10, "T10": 8, "T11": 0, "T12": 0}
    assert ff["T2"] == 0 and ff["T9"] == 10 and ff["T10"] == 8  # T2 has 3 days total float but no free float


def test_project_planner_calendar_pert_and_slip():
    cal = run("project-planner", "schedule_calendar", tasks=PORTAL_TASKS, start_date="2026-11-09", holidays=HOLIDAYS)
    assert cal["end_date"] == "2026-12-16"
    t5 = next(t for t in cal["tasks"] if t["id"] == "T5")
    assert (t5["start"], t5["end"], t5["holidays_inside"]) == ("2026-11-19", "2026-12-01", ["2026-11-26", "2026-11-27"])
    pert = run("project-planner", "pert_estimate", tasks=[{"id": i, "optimistic": o, "most_likely": m, "pessimistic": p} for i, o, m, p in CHAIN], start_date="2026-11-09", holidays=HOLIDAYS)
    c = pert["chain"]
    assert (c["expected_p50"], c["sigma"], c["p80"], c["p90"]) == (28.33, 2.19, 30.17, 31.13)
    assert c["probability_plan_date_holds_pct"] == 14.3 and c["buffer_vs_plan_for_p80"] == 4.17
    d = pert["calendar_dates"]
    assert (d["plan_most_likely"], d["p50"], d["p80"], d["p90"]) == ("2026-12-16", "2026-12-21", "2026-12-23", "2026-12-24")
    slip = run("project-planner", "slip_report", as_of="2026-11-30", holidays=HOLIDAYS, milestones=[
        {"name": "Requirements signed", "baseline": "2026-11-11", "actual": "2026-11-12"},
        {"name": "API spec", "baseline": "2026-11-13", "actual": "2026-11-13"},
        {"name": "Backend build done", "baseline": "2026-11-25", "forecast": "2026-12-02"},
        {"name": "Integration testing done", "baseline": "2026-12-10", "forecast": "2026-12-17"},
        {"name": "Portal v2 live", "baseline": "2026-12-16", "forecast": "2026-12-23"},
    ])
    assert [m["slip_working_days"] for m in slip["milestones"]] == [1, 0, 3, 5, 5]
    assert slip["rag"] == "AMBER" and slip["project_end_slip_working_days"] == 5


def test_project_planner_typed_links_variant():
    tasks = [dict(t) for t in PORTAL_TASKS]
    by = {t["id"]: t for t in tasks}
    by["T5"]["depends_on"] = ["T2 SS+2", "T3"]
    by["T10"]["depends_on"] = ["T5:FF+1"]
    by["T11"]["depends_on"] = ["T8+2", "T9"]
    out = run("project-planner", "critical_path", tasks=tasks)
    t = {r["id"]: r for r in out["tasks"]}
    assert out["project_duration_days"] == 28
    assert (t["T5"]["es"], t["T10"]["es"], t["T11"]["es"]) == (5, 10, 24)
    assert (t["T2"]["lf"], t["T2"]["free_float"], t["T10"]["total_float"]) == (14, 0, 15)


# ─────────────────────────── time-blocker ───────────────────────────

CAL_WEEK = [
    {
        "title": "Daily standup",
        "start": "2026-10-19 09:30",
        "end": "2026-10-19 09:45"
    },
    {
        "title": "Roadmap review",
        "start": "2026-10-19 10:00",
        "end": "2026-10-19 11:00"
    },
    {
        "title": "1:1 with Sam",
        "start": "2026-10-19 11:00",
        "end": "2026-10-19 11:30"
    },
    {
        "title": "Customer call - Acme",
        "start": "2026-10-19 13:00",
        "end": "2026-10-19 14:00"
    },
    {
        "title": "Hiring debrief",
        "start": "2026-10-19 14:00",
        "end": "2026-10-19 14:30"
    },
    {
        "title": "Focus: board memo",
        "start": "2026-10-19 16:00",
        "end": "2026-10-19 17:00"
    },
    {
        "title": "Daily standup",
        "start": "2026-10-20 09:30",
        "end": "2026-10-20 09:45"
    },
    {
        "title": "Focus block - pricing model",
        "start": "2026-10-20 10:00",
        "end": "2026-10-20 12:00"
    },
    {
        "title": "Lunch with investor",
        "start": "2026-10-20 12:00",
        "end": "2026-10-20 13:00"
    },
    {
        "title": "Sprint planning",
        "start": "2026-10-20 14:00",
        "end": "2026-10-20 15:00"
    },
    {
        "title": "Candidate screen",
        "start": "2026-10-20 15:05",
        "end": "2026-10-20 15:30"
    },
    {
        "title": "Daily standup",
        "start": "2026-10-21 09:30",
        "end": "2026-10-21 09:45"
    },
    {
        "title": "Vendor demo - Brightline",
        "start": "2026-10-21 10:00",
        "end": "2026-10-21 10:30"
    },
    {
        "title": "Design review",
        "start": "2026-10-21 10:30",
        "end": "2026-10-21 11:00"
    },
    {
        "title": "Partner sync",
        "start": "2026-10-21 11:00",
        "end": "2026-10-21 11:45"
    },
    {
        "title": "All-hands",
        "start": "2026-10-21 13:30",
        "end": "2026-10-21 14:30"
    },
    {
        "title": "Interview - backend candidate",
        "start": "2026-10-21 15:00",
        "end": "2026-10-21 16:00"
    },
    {
        "title": "Daily standup",
        "start": "2026-10-22 09:30",
        "end": "2026-10-22 09:45"
    },
    {
        "title": "Pricing workshop",
        "start": "2026-10-22 09:45",
        "end": "2026-10-22 10:30"
    },
    {
        "title": "Customer QBR - Northwind",
        "start": "2026-10-22 11:00",
        "end": "2026-10-22 12:00"
    },
    {
        "title": "Offsite planning",
        "start": "2026-10-22 14:00",
        "end": "2026-10-22 16:00"
    },
    {
        "title": "Team offsite prep (all day)",
        "start": "2026-10-23 00:00",
        "end": "2026-10-24 00:00"
    }
]


def test_time_blocker_dst_edge_conversion_and_slots():
    out = run("time-blocker", "convert_time", when="2026-10-27 10:00", from_zone="New York", to_zones=["London", "Berlin", "Sydney", "Bangalore"])
    loc = {c["zone"]: (c["weekday"][:3], c["local"][11:]) for c in out["conversions"]}
    # EU left DST on Oct 25, the US only on Nov 1: New York is 4 h (not 5) behind London this week
    assert loc["Europe/London"] == ("Tue", "14:00") and loc["Europe/Berlin"] == ("Tue", "15:00")
    assert loc["Australia/Sydney"] == ("Wed", "01:00") and loc["Asia/Kolkata"] == ("Tue", "19:30")
    people = [{"name": "Maya", "zone": "San Francisco"}, {"name": "Tom", "zone": "London"}, {"name": "Arjun", "zone": "Bangalore"}]
    oct27 = run("time-blocker", "find_meeting_slots", participants=people, duration_minutes=30, date="2026-10-27")
    assert oct27["everyone_in_hours"] == [] and oct27["best_compromise"][0]["start_utc"] == "2026-10-27 14:00"
    nov3 = run("time-blocker", "find_meeting_slots", participants=people, duration_minutes=30, date="2026-11-03")
    assert nov3["best_compromise"] == []  # after US DST ends there is no 07:00-20:00 overlap at all
    amb = run("time-blocker", "convert_time", when="2026-11-01 01:30", from_zone="New York", to_zones=["UTC"])
    assert amb["warning"] and "twice" in amb["warning"]


def test_time_blocker_pack_day_constraints():
    out = run("time-blocker", "pack_day", tasks=[
        {"name": "Write Q4 board memo", "minutes": 150, "priority": 1, "kind": "deep"},
        {"name": "Review Acme contract redlines", "minutes": 45, "priority": 1, "kind": "deep"},
        {"name": "Prep for Acme call", "minutes": 30, "priority": 1, "kind": "shallow", "due_by": "13:00"},
        {"name": "Reply to investor emails", "minutes": 20, "priority": 2, "kind": "shallow"},
        {"name": "Hiring scorecards", "minutes": 30, "priority": 2, "kind": "shallow"},
        {"name": "Expense report", "minutes": 15, "priority": 3, "kind": "admin"},
        {"name": "Read competitor teardown", "minutes": 60, "priority": 4, "kind": "deep"},
    ], fixed_events=[{"title": "Standup", "start": "10:00", "end": "10:30"}, {"title": "Acme customer call", "start": "13:00", "end": "14:00"}, {"title": "1:1 with Sam", "start": "15:30", "end": "16:00"}],
        day_start="08:00", day_end="17:30", peak_start="08:00", peak_end="11:00", lunch_start="12:15", lunch_minutes=30)
    blocks = sorted(out["blocks"], key=lambda b: b["start"])
    for a, b in zip(blocks, blocks[1:]):
        assert a["end"] <= b["start"], (a, b)  # no overlaps
    assert all("08:00" <= b["start"] and b["end"] <= "17:30" for b in blocks)
    prep = next(b for b in blocks if b["task"] == "Prep for Acme call")
    assert prep["end"] <= "13:00"  # before the call it prepares for (was 14:10 before the fix)
    assert all(b["minutes"] >= 25 for b in blocks if b["kind"] == "deep")  # no 5-minute deep slivers
    memo = sum(b["minutes"] for b in blocks if b["task"] == "Write Q4 board memo")
    assert memo == 150 and blocks[0]["task"] == "Write Q4 board memo"  # P1 deep work opens the peak
    for m in ("10:30", "14:00", "16:00"):  # 10-min buffer after each meeting
        assert not any(m <= b["start"] < m[:3] + "10" for b in blocks if b["kind"] not in ("meeting", "break"))


def test_time_blocker_calendar_audit_week():
    out = run("time-blocker", "audit_calendar", events=CAL_WEEK, work_start="09:00", work_end="18:00")
    # hand ground truth: 195 + 160 + 240 + 240 + 0 = 835 min over 5 x 540 = 30.9%
    assert out["days_analysed"] == 5 and out["total_meeting_hours"] == 13.9 and out["meeting_load_pct"] == 31 and out["rag"] == "AMBER"
    assert [d["meeting_minutes"] for d in out["by_day"]] == [195, 160, 240, 240, 0]
    assert out["fragments_under_30"] == 3 and out["back_to_back_transitions"] == 5
    assert out["focus_minutes_scheduled"] == 180 and out["all_day_items_ignored"] == 1 and out["meeting_free_days"] == ["2026-10-23"]


# ─────────────────────────── inbox-triage ───────────────────────────

INBOX = [
    {
        "id": "1",
        "from": "Sarah Kim <sarah@harborvc.com>",
        "to": "alex@northwind.io",
        "subject": "Board deck",
        "body": "Hi Alex, can you send the Q3 board deck by Thursday? Also, are we still on for the 8th? Thanks, Sarah",
        "received": "2026-09-29"
    },
    {
        "id": "2",
        "from": "Dana White <dana.w@acme.com>",
        "to": "alex@northwind.io",
        "subject": "SSO outage this morning",
        "body": "Alex, our team couldn't log in from 8:00 to 9:30 this morning. Can you confirm the root cause and whether this counts toward our SLA credits? I need an answer today for our IT review.",
        "received": "2026-09-29"
    },
    {
        "id": "3",
        "from": "GitHub <noreply@github.com>",
        "to": "alex@northwind.io",
        "subject": "[northwind/api] PR #482 approved",
        "body": "jordan-lee approved this pull request. View it on GitHub.",
        "received": "2026-09-29"
    },
    {
        "id": "4",
        "from": "Lenny's Newsletter <newsletter@lennysnewsletter.com>",
        "to": "alex@northwind.io",
        "subject": "How the best PMs prioritize",
        "body": "This week: prioritization frameworks from 40 PMs. View in browser. Unsubscribe | Manage preferences",
        "received": "2026-09-29"
    },
    {
        "id": "5",
        "from": "Jamie Ortiz <jamie@northwind.io>",
        "to": "alex@northwind.io",
        "subject": "Offer for backend candidate - approve?",
        "body": "Can you approve the offer at $185k base by EOD tomorrow? She has a competing offer that expires Thursday.",
        "received": "2026-09-29"
    },
    {
        "id": "6",
        "from": "AWS Billing <billing@aws.amazon.com>",
        "to": "alex@northwind.io",
        "subject": "Your AWS invoice for September is available",
        "body": "Your invoice for account 4411 is available in the Billing console. Amount due: $3,412.18.",
        "received": "2026-09-28"
    },
    {
        "id": "7",
        "from": "Rick Stone <rick@talentsprint.io>",
        "to": "alex@northwind.io",
        "subject": "Quick question",
        "body": "Hi Alex, are you hiring engineers? We have 5 pre-vetted backend candidates. Let me know if you'd like a quick call.",
        "received": "2026-09-28"
    },
    {
        "id": "8",
        "from": "Priya Shah <priya@northwind.io>",
        "to": "team@northwind.io",
        "cc": "alex@northwind.io",
        "subject": "FYI: churn dashboard updated",
        "body": "No action needed, just FYI the churn dashboard now includes September cohorts.",
        "received": "2026-09-28"
    },
    {
        "id": "9",
        "from": "Mark Evans <mark@brightline.io>",
        "to": "alex@northwind.io",
        "subject": "Brightline renewal - 2027 pricing",
        "body": "Hi Alex, our renewal pricing for 2027 is attached: a 12% increase on the current contract. Please confirm by October 15 to lock the current terms.",
        "received": "2026-09-28"
    },
    {
        "id": "10",
        "from": "Google Calendar <calendar-notification@google.com>",
        "to": "alex@northwind.io",
        "subject": "Invitation: Design review @ Thu Oct 1",
        "body": "You have been invited to Design review. Going? Yes / No / Maybe",
        "received": "2026-09-29"
    },
    {
        "id": "11",
        "from": "Lee Park <lee@acme.com>",
        "to": "alex@northwind.io",
        "subject": "Re: export fix",
        "body": "Thanks, that worked!",
        "received": "2026-09-29"
    },
    {
        "id": "12",
        "from": "Accounting <accounting@northwind.io>",
        "to": "alex@northwind.io",
        "subject": "Missing receipts for September close",
        "body": "Please upload the 3 missing receipts by Friday so we can close September.",
        "received": "2026-09-29"
    },
    {
        "id": "13",
        "from": "SaaStr Events <events@saastr.com>",
        "to": "alex@northwind.io",
        "subject": "Last chance: SaaStr Annual tickets",
        "body": "Prices go up tonight! Grab your ticket. You are receiving this because you attended in 2025. Unsubscribe.",
        "received": "2026-09-29"
    },
    {
        "id": "14",
        "from": "Tom Reyes <tom@reyescapital.com>",
        "to": "alex@northwind.io",
        "subject": "Coffee next week?",
        "body": "Hi Alex, would you be free for coffee next week? Happy to come to your office.",
        "received": "2026-09-26"
    },
    {
        "id": "15",
        "from": "Okta <no-reply@okta.com>",
        "to": "alex@northwind.io",
        "subject": "Security alert: new sign-in to your account",
        "body": "A new sign-in from Chrome on macOS was detected. If this was you, no action is needed.",
        "received": "2026-09-29"
    }
]
INBOX_TRUTH = {  # evaluator's EA judgement for each email
    "1": "Reply now", "2": "Reply now", "5": "Reply now",
    "9": "Reply today", "12": "Reply today", "14": "Reply today",
    "3": "Archive", "6": "Archive", "7": "Archive", "8": "Archive", "10": "Archive", "11": "Archive", "15": "Archive",
    "4": "Unsubscribe or digest", "13": "Unsubscribe or digest",
}


def test_inbox_triage_fifteen_emails():
    out = run("inbox-triage", "score_priority", emails=INBOX, me="alex@northwind.io", vips=["harborvc.com", "acme.com", "jamie@northwind.io"], as_of="2026-09-29")
    got = {r["id"]: r["action"] for r in out["emails"]}
    assert got == INBOX_TRUTH
    dl = {r["id"]: r["deadline"] for r in out["emails"]}
    assert (dl["1"], dl["2"], dl["5"], dl["9"], dl["12"]) == ("2026-10-01", "2026-09-29", "2026-09-30", "2026-10-15", "2026-10-02")
    assert out["reply_now_ids"][:3] == ["2", "5", "1"]  # today, tomorrow, Thursday


def test_inbox_triage_asks_reply_and_session():
    asks = run("inbox-triage", "extract_asks", body=INBOX[1]["body"] + "\n\nOn Mon, Sep 28, 2026 at 4:02 PM Alex wrote:\n> Thanks Dana, the export fix is live.", as_of="2026-09-29", received="2026-09-29")
    assert asks["counts"]["questions"] == 1 and asks["earliest_deadline"]["date"] == "2026-09-29" and asks["quoted_history_dropped"]
    reply = run("inbox-triage", "fill_reply_template", template="Hi {name},\n\nThanks for flagging this, and sorry for the disruption. Root cause: {cause}. {sla_line} I will send the written incident report by {date}.\n\nBest,\nAlex",
                fields={"name": "Dana", "cause": "an expired SAML signing certificate on our side, fixed at 9:32", "sla_line": "The 90 minutes count toward your SLA; the credit will appear on your next invoice.", "date": "Thursday, Oct 1"})
    assert reply["ready_to_send"] is True and reply["sentences"] == 4
    plan = run("inbox-triage", "plan_session", minutes_available=30, as_of="2026-09-29", items=[
        {"id": "2", "action": "Reply now", "minutes": 15, "score": 100, "deadline": "2026-09-29"},
        {"id": "5", "action": "Reply now", "minutes": 15, "score": 100, "deadline": "2026-09-30"},
        {"id": "1", "action": "Reply now", "minutes": 5, "score": 100, "deadline": "2026-10-01"},
        {"id": "9", "action": "Reply today", "minutes": 5, "score": 75, "deadline": "2026-10-15"},
        {"id": "14", "action": "Reply today", "minutes": 5, "score": 73},
        {"id": "12", "action": "Reply today", "minutes": 2, "score": 70, "deadline": "2026-10-02"},
    ])
    assert plan["minutes_planned"] <= 27 and plan["deferred_at_risk"] == ["5"]


# ─────────────────────────── sop-writer ───────────────────────────

def test_sop_writer_refund_sop():
    draft = run("sop-writer", "lint_steps", roles=["Support agent", "Support lead", "Finance"], steps=[
        "Support agent: Open the refund request in Zendesk.",
        "The agent checks the order in Shopify and looks at the purchase date.",
        "If the order is older than 30 days, escalate to the Support lead.",
        "Support agent: Issue the refund in Stripe and email the customer.",
        "Refunds over 00 should be approved by Finance as needed.",
        "Tag the ticket refund-processed.",
        "Close the ticket.",
    ])
    flagged = {r["n"] for r in draft["steps"] if r["issues"]}
    assert flagged == {2, 3, 4, 5} and draft["score"] < 85
    assert any("irreversible" in i for i in draft["steps"][3]["issues"])  # "Issue the refund" with no verify step
    cyc = run("sop-writer", "cycle_time", steps=[
        {"step": "Open request", "touch_minutes": 2, "wait_minutes": 240, "role": "Support agent"},
        {"step": "Check order date", "touch_minutes": 3, "wait_minutes": 0, "role": "Support agent"},
        {"step": "Finance approval", "touch_minutes": 5, "wait_minutes": 1440, "role": "Finance"},
        {"step": "Issue refund in Stripe", "touch_minutes": 4, "wait_minutes": 30, "role": "Support agent"},
        {"step": "Verify Stripe status", "touch_minutes": 1, "wait_minutes": 0, "role": "Support agent"},
        {"step": "Send confirmation", "touch_minutes": 2, "wait_minutes": 0, "role": "Support agent"},
        {"step": "Tag and solve", "touch_minutes": 1, "wait_minutes": 0, "role": "Support agent"},
    ])
    assert (cyc["touch_time_minutes"], cyc["lead_time_minutes"], cyc["process_cycle_efficiency_pct"], cyc["handoffs"]) == (18, 1728, 1.0, 2)
    assert "Finance approval (1.0 days)" in cyc["verdict"]  # elapsed day, not "3.0 workdays"
    raci = run("sop-writer", "build_raci", activities=[
        {"activity": "Handle >30-day exceptions", "responsible": ["Support lead"], "accountable": ["Support lead"], "consulted": ["Finance"], "informed": ["Finance"]},
        {"activity": "Monthly refund reconciliation", "responsible": ["Finance"], "accountable": ["Finance lead", "CFO"]},
    ])
    assert raci["valid"] is False and len([r for r in raci["activities"] if r["issues"]]) == 2
    for eff, nxt, days in (("2026-10-01", "2027-04-01", 186), ("2026-08-31", "2027-02-28", 154)):
        cb = run("sop-writer", "sop_control_block", title="Customer refund processing", owner="Support lead", effective_date=eff, version="1.3", change_type="major", review_months=6, department="CS", as_of="2026-09-27")
        assert (cb["version"], cb["next_review_date"], cb["days_until_review"]) == ("2.0", nxt, days)


# ─────────────────────────── okr-coach ───────────────────────────

def test_okr_coach_q4_grading_forecast_calendar():
    lint = run("okr-coach", "lint_okrs", objectives=[
        {"objective": "Launch the new onboarding flow and grow revenue 30%", "key_results": ["Launch onboarding v2", "Improve activation", "Grow MRR from 80k to 40k", "Hire 2 growth engineers"]},
        {"objective": "Make support feel instant for every customer", "key_results": ["Reduce median first-response time from 9h to 4h", "Raise CSAT from 88% to 93% by Dec 31"]},
    ])
    assert lint["score"] == 76 and lint["objectives"][1]["score"] == 100
    g = run("okr-coach", "grade_progress", period_start="2026-10-01", period_end="2026-12-31", as_of="2026-11-13", key_results=[
        {"name": "Activation", "start": 31, "target": 45, "current": 37},
        {"name": "MRR", "start": 180, "target": 240, "current": 196, "type": "committed"},
        {"name": "First response", "start": 9, "target": 4, "current": 8, "type": "committed"},
        {"name": "CSAT", "start": 88, "target": 93, "current": 91},
    ])
    assert g["period"]["days"] == 92 and g["period"]["elapsed_pct"] == 46.7 and g["period"]["weeks_left"] == 7.0
    assert [(k["progress_pct"], k["status"], k["score"]) for k in g["key_results"]] == [(42.9, "on track", 0.4), (26.7, "at risk", 0.3), (20.0, "off track", 0.2), (60.0, "on track", 0.6)]
    assert [k["needed_per_week"] for k in g["key_results"]] == [1.14, 6.29, 0.57, 0.29]
    f = run("okr-coach", "forecast_key_result", target=45, period_end="2026-12-31", history=[{"date": d, "value": v} for d, v in [("2026-10-02", 31), ("2026-10-09", 32.5), ("2026-10-16", 33), ("2026-10-23", 34.5), ("2026-10-30", 35), ("2026-11-06", 36.5), ("2026-11-13", 37)]])
    assert (f["slope_per_week"], f["r_squared"], f["projected_end_value"], f["projected_hit_date"], f["reaches_target_on_trend"]) == (1.0, 0.985, 44.07, "2027-01-06", False)
    cal = run("okr-coach", "okr_calendar", period_start="2026-10-01", period_end="2026-12-31", as_of="2026-11-13", holidays=["2026-11-26", "2026-12-25", "2027-01-01"])
    assert cal["scoring_day"] == "2027-01-04" and cal["draft_next_cycle"]["start"] == "2026-12-09" and len(cal["checkins"]) == 13


# ─────────────────────────── status-reporter ───────────────────────────

STATUS_DRAFT = '**Portal v2 — week of 2026-11-20 — 🔴 RED** (last week: 🟡 AMBER)\n\n**TL;DR**\n- Okta SSO shipped; pilot sign-ups 34 of 40 (+6 vs last week).\n- Backend build slipped 3 working days to Dec 2, which pushes go-live from Dec 16 to Dec 23.\n- Open P1 bugs are 9 against a target of 5 (down from 12): we need one more engineer on bug triage.\n\n**Asks / decisions needed**\n- Approve moving Lena from docs to P1 triage for 2 weeks — by Nov 24 — from Priya.\n- Confirm the Dec 23 go-live with the two pilot customers — by Nov 25 — from Mei.\n\n**Progress**\n| Metric | Target | This week | Last week | Δ | RAG |\n|---|---|---|---|---|---|\n| Pilot sign-ups | 40 | 34 | 28 | +6 | AMBER |\n| Open P1 bugs | ≤5 | 9 | 12 | -3 | RED |\n| Test coverage | 80% | 78% | 74% | +4 | GREEN |\n| p95 page load | ≤1500 ms | 1450 ms | 1600 ms | -150 | GREEN |\n\n- Shipped: Okta SSO integration. Slipped: Backend build (+3 wd, data-model rework). Added: Frontend build. Dropped: pricing page copy (moved to marketing).\n\n**Risks & issues**\n- 🔴 Issue: 9 open P1 bugs; impact: UAT cannot start; mitigation: Lena on triage; owner Marcus; review Nov 27.\n- 🟡 Risk: security review has not started and is due Nov 24; owner Raj; mitigation: start Monday.\n\n**Next week**\n- Backend build to 90% complete.\n- P1 bugs down to 5.\n- Security review started and scoped.\n\n_RAG: Green = on plan · Amber = at risk, plan in place · Red = off plan, escalation needed_\n'


def test_status_reporter_weekly_exec_update():
    rag = run("status-reporter", "compute_rag", metrics=[
        {"name": "Pilot sign-ups", "target": 40, "current": 34, "previous": 28},
        {"name": "Open P1 bugs", "target": 5, "current": 9, "previous": 12, "direction": "lower"},
        {"name": "Test coverage", "target": 80, "current": 78, "previous": 74},
        {"name": "p95 page load", "target": 1500, "current": 1450, "previous": 1600, "direction": "lower"},
    ])
    assert [(m["attainment_pct"], m["rag"]) for m in rag["metrics"]] == [(85.0, "AMBER"), (55.6, "RED"), (97.5, "GREEN"), (103.4, "GREEN")]
    assert rag["overall"] == "RED" and len(rag["rag_changes"]) == 3
    ms = run("status-reporter", "milestone_health", as_of="2026-11-20", holidays=["2026-11-26", "2026-11-27", "2026-12-25"], milestones=[
        {"name": "Backend build done", "baseline": "2026-11-25", "forecast": "2026-12-02"},
        {"name": "Portal v2 live", "baseline": "2026-12-16", "forecast": "2026-12-23"},
    ])
    assert [m["slip_working_days"] for m in ms["milestones"]] == [3, 5]  # same numbers as project-planner's slip_report
    lint = run("status-reporter", "lint_report", report=STATUS_DRAFT, audience="exec")
    assert lint["score"] >= 80 and lint["asks_before_progress"] is True and lint["missing_sections"] == []


# ─────────────────────────── decision-matrix ───────────────────────────

OFFICE = {
    "criteria": [
        {
            "name": "Talent pool",
            "weight": 0.4668
        },
        {
            "name": "Cost",
            "weight": 0.1603,
            "direction": "lower",
            "normalise": True
        },
        {
            "name": "Time-zone overlap",
            "weight": 0.2776
        },
        {
            "name": "Quality of life",
            "weight": 0.0953
        }
    ],
    "options": [
        {
            "name": "Lisbon",
            "scores": {
                "Talent pool": 3,
                "Cost": 95,
                "Time-zone overlap": 2,
                "Quality of life": 5
            }
        },
        {
            "name": "Austin",
            "scores": {
                "Talent pool": 5,
                "Cost": 175,
                "Time-zone overlap": 5,
                "Quality of life": 3
            }
        },
        {
            "name": "Toronto",
            "scores": {
                "Talent pool": 4,
                "Cost": 140,
                "Time-zone overlap": 5,
                "Quality of life": 4
            }
        },
        {
            "name": "Stay remote-only",
            "scores": {
                "Talent pool": 4,
                "Cost": 120,
                "Time-zone overlap": 3,
                "Quality of life": 4
            }
        }
    ]
}


def test_decision_matrix_office_choice():
    ahp = run("decision-matrix", "pairwise_weights", criteria=["Talent pool", "Cost", "Time-zone overlap", "Quality of life"], comparisons=[
        {"a": "Talent pool", "b": "Cost", "ratio": 3}, {"a": "Talent pool", "b": "Time-zone overlap", "ratio": 2}, {"a": "Talent pool", "b": "Quality of life", "ratio": 4},
        {"a": "Cost", "b": "Time-zone overlap", "ratio": 0.5}, {"a": "Cost", "b": "Quality of life", "ratio": 2}, {"a": "Time-zone overlap", "b": "Quality of life", "ratio": 3},
    ])
    assert list(ahp["weights"].values()) == [0.4668, 0.1603, 0.2776, 0.0953] and ahp["consistency_ratio"] == 0.011
    ws = run("decision-matrix", "weighted_score", **OFFICE)
    assert {r["option"]: r["total"] for r in ws["ranking"]} == {"Austin": 80.2, "Toronto": 79.7, "Stay remote-only": 72.6, "Lisbon": 64.7}
    assert ws["closeness"] == "CLOSE CALL"
    sens = run("decision-matrix", "sensitivity_check", **OFFICE)
    assert {f["criterion"]: f["flip_at_weight_pct"] for f in sens["weight_flips"]} == {"Talent pool": 45.5, "Cost": 16.8, "Time-zone overlap": 11.1, "Quality of life": 11.4}
    assert sens["equal_weights_winner"] == "Toronto" and sens["robustness"] == "FRAGILE"
    ev = run("decision-matrix", "expected_value", options=[
        {"name": "3-year lease", "outcomes": [{"name": "on plan", "probability": 0.6, "value": 400000}, {"name": "slower", "probability": 0.3, "value": 50000}, {"name": "downturn", "probability": 0.1, "value": -600000}]},
        {"name": "12-month coworking", "outcomes": [{"name": "on plan", "probability": 0.6, "value": 250000}, {"name": "slower", "probability": 0.3, "value": 80000}, {"name": "downturn", "probability": 0.1, "value": -50000}]},
    ])
    assert [(r["option"], r["expected_value"], r["std_dev"]) for r in ev["ranking"]] == [("3-year lease", 195000.0, 307774.27), ("12-month coworking", 169000.0, 105399.24)]
    assert ev["regret"]["minimax_choice"] == "12-month coworking"


# ─────────────────────────── vendor-evaluator ───────────────────────────

RFP = {
    "must_haves": [
        "SSO/SAML",
        "SOC 2 Type II",
        "EU data residency"
    ],
    "criteria": [
        {
            "name": "Ticket workflows",
            "weight": 20,
            "category": "Functionality"
        },
        {
            "name": "Knowledge base",
            "weight": 10,
            "category": "Functionality"
        },
        {
            "name": "Agent UX",
            "weight": 15,
            "category": "Usability"
        },
        {
            "name": "Security & compliance",
            "weight": 15,
            "category": "Security"
        },
        {
            "name": "Salesforce + Slack integration",
            "weight": 15,
            "category": "Integration"
        },
        {
            "name": "Vendor support & viability",
            "weight": 10,
            "category": "Support"
        },
        {
            "name": "Reporting",
            "weight": 15,
            "category": "Functionality"
        }
    ],
    "vendors": [
        {
            "name": "Helply",
            "must_haves": {
                "SSO/SAML": True,
                "SOC 2 Type II": True,
                "EU data residency": "unverified"
            },
            "scores": {
                "Ticket workflows": 4,
                "Knowledge base": 4,
                "Agent UX": 4,
                "Security & compliance": 4,
                "Salesforce + Slack integration": 5,
                "Vendor support & viability": 3,
                "Reporting": 3
            }
        },
        {
            "name": "DeskPro",
            "must_haves": {
                "SSO/SAML": True,
                "SOC 2 Type II": True,
                "EU data residency": True
            },
            "scores": {
                "Ticket workflows": 5,
                "Knowledge base": 3,
                "Agent UX": 3,
                "Security & compliance": 4,
                "Salesforce + Slack integration": 3,
                "Vendor support & viability": 4,
                "Reporting": 4
            }
        },
        {
            "name": "SupportHub",
            "must_haves": {
                "SSO/SAML": True,
                "SOC 2 Type II": False,
                "EU data residency": True
            },
            "scores": {
                "Ticket workflows": 4,
                "Knowledge base": 5,
                "Agent UX": 5,
                "Security & compliance": 3,
                "Salesforce + Slack integration": 4,
                "Vendor support & viability": 4,
                "Reporting": 5
            }
        }
    ]
}
TCO = {
    "years": 3,
    "discount_rate_pct": 8,
    "hourly_rate": 75,
    "vendors": [
        {
            "name": "Helply",
            "per_seat_month": 49,
            "seats": 60,
            "seat_growth_pct_yr": 20,
            "annual_increase_pct": 7,
            "one_time": 12000,
            "internal_hours_setup": 80,
            "internal_hours_per_month": 10,
            "training": 3000,
            "exit_cost": 5000
        },
        {
            "name": "DeskPro",
            "per_seat_month": 39,
            "seats": 60,
            "seat_growth_pct_yr": 20,
            "platform_fee_yr": 6000,
            "annual_increase_pct": 9,
            "one_time": 25000,
            "internal_hours_setup": 160,
            "internal_hours_per_month": 20,
            "training": 6000,
            "exit_cost": 15000
        },
        {
            "name": "SupportHub",
            "per_seat_month": 59,
            "seats": 60,
            "seat_growth_pct_yr": 20,
            "annual_increase_pct": 3,
            "internal_hours_setup": 40,
            "internal_hours_per_month": 6,
            "exit_cost": 2000
        }
    ]
}


def test_vendor_evaluator_selection_tco_contract_sla():
    rfp = run("vendor-evaluator", "score_rfp", **RFP)
    assert [(r["vendor"], r["score"]) for r in rfp["ranking"]] == [("Helply", 78.0), ("DeskPro", 76.0)]
    assert rfp["knocked_out"] == [{"vendor": "SupportHub", "failed": ["SOC 2 Type II"]}]
    tco = run("vendor-evaluator", "calculate_tco", **TCO)
    got = {o["vendor"]: (o["total_nominal"], o["npv"]) for o in tco["ranking"]}
    assert got == {"SupportHub": (181082, 165238), "Helply": (191744, 175254), "DeskPro": (244518, 222738)}
    arrears = run("vendor-evaluator", "calculate_tco", **{**TCO, "billing": "arrears"})
    assert {o["vendor"]: o["npv"] for o in arrears["ranking"]}["Helply"] == 165840
    c = run("vendor-evaluator", "contract_risk_check", today="2026-09-27", annual_fees=28800, terms={
        "start_date": "2025-12-01", "term_months": 12, "auto_renew": True, "notice_days": 60, "price_cap_pct": 9, "sla_uptime_pct": 99.5,
        "sla_credits": True, "liability_cap_months": 6, "unilateral_changes": True, "data_export": True, "payment_terms_days": 15,
        "termination_for_convenience": False, "soc2": True, "dpa": True})
    assert (c["term_end_date"], c["notice_deadline"], c["days_until_notice_deadline"], c["recommended_send_by"]) == ("2026-11-30", "2026-10-01", 4, "2026-09-28")
    assert [f["severity"] for f in c["flags"]].count("high") == 2 and c["risk_level"] == "HIGH"
    sla = run("vendor-evaluator", "sla_downtime", uptime_pct=99.5, monthly_fee=2400, credit_tiers=[{"below_pct": 99.5, "credit_pct": 5}, {"below_pct": 99.0, "credit_pct": 10}], actual_downtime_minutes=218, outage_cost_per_hour=1500, month="2026-11")
    assert sla["allowed_downtime_minutes"]["this_month"] == 216.0 and sla["actual"]["breach"] is True
    assert (sla["actual"]["credit_usd"], sla["actual"]["your_outage_cost_usd"], sla["actual"]["credit_covers_pct_of_loss"]) == (120.0, 5450.0, 2.2)
