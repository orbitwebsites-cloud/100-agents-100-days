"""Commit Coroner — the CI-failure autopsy agent.

Agent #4 of the 100-agents-100-days build. When a test goes red, most tools
stop at "here's the stack trace." Commit Coroner keeps going: it walks the
*real* git history of the failing file, pulls the actual diffs of every
commit that touched it recently, and reasons about which one introduced the
break — then it doesn't just tell you, it opens the GitHub issue and pings
Slack itself, with a named suspect and a confidence call.

It isn't a log summarizer. Log summarizers describe a failure that already
happened. Commit Coroner performs git bisection-by-reasoning against your
actual commit objects and takes the follow-up action on its own — the same
loop a senior engineer runs at 2am, minus the engineer.
"""
