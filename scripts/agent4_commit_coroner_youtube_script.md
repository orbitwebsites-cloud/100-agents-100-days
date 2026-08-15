# YouTube Script — Agent #4: Commit Coroner
### "I built an AI agent that autopsies broken code and names the commit that killed it"

**Runtime target:** ~5 minutes
**Series:** 100 Agents · 100 Days

---

## HOOK (0:00–0:20)

Your test suite goes red. You get a stack trace. Now what?

You scroll `git log`. You squint at five commits that touched the file. You
run `git show` on each one, by hand, trying to remember whose diff you're
even looking at. Fifteen minutes later you find it — some commit from
Tuesday that looked innocent.

I built an agent that does that entire investigation itself — and then
files the report and pages the team, without me touching git once.

This is Agent #4: **Commit Coroner**. Day 4 of 100 agents, 100 days.

## WHAT MAKES THIS ONE DIFFERENT (0:20–0:55)

Quick gut check before I show it — the test I hold every agent in this
series to: **could you get the same result by pasting a prompt into
ChatGPT?**

Every "AI debugging assistant" you've seen do this test — you paste in a
stack trace, it makes something up about what's probably wrong. It's never
looked at your actual commits. It's guessing.

Commit Coroner doesn't get to guess. It has to call a tool that runs real
`git log` against your real repo, get back real commit SHAs, then call
another tool that runs real `git show` and reads the *actual diff* — before
it's allowed to accuse anything. Then it opens a real GitHub issue and posts
a real Slack alert. That's four tool calls, three of them touching things
that actually exist outside the chat window. That's the bar for "agent" in
this series, and this is the first one in the build that does forensics on
your own git history instead of talking to a SaaS API.

## LIVE DEMO (0:55–3:30)

Let me show you the failure. [SCREEN: samples/ci_failure_report.txt] Here's
a CI run that just went red — a test on one of our connector files failed,
and I've got the stack trace.

One command:

```
python run_coroner.py
```

[SCREEN: terminal running, narrate as it streams]

Watch what it does. First tool call — `list_suspect_commits`. It's not
asking me who touched this file. It's running git, right now, against the
actual repo, and getting back real commits with real SHAs, real authors,
real dates.

Now it's picking one it's suspicious of and calling `inspect_commit`. That
pulls the *actual diff* — the real lines that were added and removed. This
is the part that matters: the system prompt won't let it name a culprit
commit unless it's actually called this tool and read this diff first. It
can't fabricate a verdict from a commit *subject line* — it has to have
looked.

And now — it's filing. `file_autopsy_report` opens a GitHub issue: verdict,
evidence, suggested fix. [SCREEN: printed issue body] Then
`raise_incident_alert` — a Slack-ready summary, so the team doesn't have to
go looking for a GitHub notification to find out something's on fire.

All of that ran in dry-run just now because I haven't wired up my GitHub
token in this take — it prints exactly what it would have filed and posted.
Drop in a `GITHUB_TOKEN` and a `SLACK_WEBHOOK_URL` and the exact same run
opens a real issue and pings a real channel. Nothing about the agent's
behavior changes — only where the output lands.

## WHY THIS DOESN'T EXIST YET (3:30–4:15)

I looked before I built this. There's no shortage of "AI log summarizer"
products — Sentry has AI triage, there are a dozen "paste your stack trace"
tools. What none of them do is the part that actually matters: read your
git history like a detective, force itself to look at evidence before
naming a suspect, and then close the loop by taking the two actions a human
would take next — file it, alert it.

That's the whole design principle behind this build. Not "can the model
write a paragraph about my bug" — can it investigate something real and act
on what it finds, on its own, the way the engineer on call would at 2am.

## HOW IT'S BUILT (4:15–4:45)

[SCREEN: file tree] `commit_coroner/` — same shape as every agent in this
series. A tools file with the four tools the model can call. Connectors —
`git_forensics.py` shells out to the real `git` binary, no API key required
for that part ever. `github.py` and `slack.py` follow the same dry-run
pattern you've seen in every episode: no keys, no product breaks, you just
get printed output instead of a live action.

It runs on either brain — Anthropic's Tool Runner, or Cerebras' free tier
if you don't have a paid key yet. Link's in the description, whole thing's
open source.

## OUTRO (4:45–5:00)

That's Agent #4. Tomorrow: agent #5. If you want to build this one
yourself, it's a 30-second setup — link's below. Subscribe if you want to
watch all 100 of these get built in public.

---

### Notes for editing
- B-roll: terminal recording of `python run_coroner.py --selftest` for a
  fast "plumbing works" beat if the full run needs trimming.
- On-screen callout during the tool-call section: freeze-frame the printed
  `sha | date | author | subject` table — it's the visual proof this is
  real git data, not a hallucinated log.
- Thumbnail idea: a stack trace with a magnifying glass over one commit SHA,
  title card "WHO BROKE THE BUILD?"
