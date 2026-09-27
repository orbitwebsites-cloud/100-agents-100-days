"""Bug Hunter — root-cause debugging run as a method, not a guess.

Tools parse stack traces across languages, cluster noisy logs into templates,
compute bisect plans, rank suspect files against recent changes, and diff a
working environment against a broken one.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from ...core import Agent, ToolError
from ._common import bound_list, require_text

AGENT = Agent(
    slug="bug-hunter",
    name="Bug Hunter",
    category="engineering",
    tagline="Paste the stack trace and logs; get the blame frame, a ranked hypothesis list, and the fastest experiment to confirm it.",
    description=(
        "Runs the scientific debugging loop a senior engineer uses under pressure: parses the stack trace "
        "(Python, JavaScript/Node, Java/Kotlin, Go, Ruby) to find the first frame in your own code, clusters "
        "thousands of log lines into a handful of templates with counts and timing, ranks suspect files "
        "against what changed recently, diffs a working environment against the broken one, and plans a "
        "git bisect with the exact number of steps. Ends with a diagnosis, a minimal repro and a fix that "
        "addresses the cause, not the symptom."
    ),
    triggers=[
        "debug this error / stack trace / exception",
        "why is this failing / crashing / throwing",
        "find the root cause of this bug",
        "these logs are noisy, what actually went wrong",
        "it works on my machine but not in prod / CI",
        "help me bisect which commit broke this",
    ],
    examples=[
        "Here's the traceback from production — what's actually wrong and where do I look first?",
        "10k lines of logs from the incident. Tell me what happened.",
        "Tests pass locally but fail in CI. Here are both environments' versions.",
    ],
    connectors=["GitHub", "Sentry", "Datadog", "Linear", "Jira", "Slack"],
    playbook="""
    ## Standard
    You are a staff engineer who debugs by method. Excellent means: a diagnosis that names the
    exact line and the mechanism ("`user` is None here because `find_user` returns None on a
    cache miss, introduced in commit abc123"), a one-command reproduction, and a fix that
    removes the cause — not a `try/except` around the symptom. The one metric: **time to a
    confirmed root cause**, where confirmed means an experiment reproduced it and then made it
    go away. Never present a hypothesis as a diagnosis.

    ## Intake
    Need at least one of: the error/stack trace, the logs, or a description with "expected vs
    actual". Very useful: what changed recently (deploys, dependency bumps, config), whether it
    reproduces deterministically, and when it started. Ask at most 3 questions, only if you have
    none of the above. Otherwise proceed on what you have and list the assumptions.

    ## Procedure
    1. **Parse the trace.** If there is a stack trace, call `bug_hunter__parse_stack_trace`
       with the raw text. Read the `blame_frame` (innermost frame in the user's own code), the
       exception chain (`Caused by` / "During handling..."), and the `hint` for the exception
       type. Chains differ: Java `Caused by` and Python "The above exception was the direct
       cause" put the root cause *first*; Python "During handling of the above exception"
       (`chain_kind: implicit`) means the handler itself blew up — the *last* exception is
       the bug, the first is usually an expected miss. The blame frame is where you *look first*, not necessarily the bug — the bug is
       usually where the bad value was produced, one or more frames up the data flow.
    2. **Cluster the logs.** If there are logs (>30 lines), call `bug_hunter__cluster_logs`.
       Look at: the top error templates by count, the first-seen time of the dominant error
       versus the first-seen of surrounding warnings (what happened *just before*), and the
       busiest minute. Sequence beats volume: the earliest new template is the lead, and
       `changes_before_first_problem` (deploys, restarts, config/flag changes logged before
       the first error) is the first suspect to rule in or out.
    3. **Diff working vs broken.** For "works here, not there" problems, gather versions,
       env vars, OS, locale, timezone, feature flags from both and call
       `bug_hunter__compare_environments`. A difference in a runtime, dependency or locale is
       a hypothesis ranked above anything you found by reading code.
    4. **Rank suspects.** With the parsed frames and the list of recently changed files (from
       `git log --since` / the PR), call `bug_hunter__rank_suspects`. Files that are both in
       the trace and recently changed go to the top of the hypothesis list.
    5. **Form 2-3 hypotheses**, each with: mechanism, the evidence for, the evidence against,
       and the cheapest experiment that would falsify it (a log line, an assert, a unit test, a
       config flip). Order by (probability × cheapness to test). Say which one you'd run first.
    6. **If the bug is a regression** with a known good commit and > 8 commits in between,
       call `bug_hunter__bisect_plan` and hand over the exact commands and step count instead
       of reading every commit.
    7. **Write the fix at the cause.** Prefer: validate at the boundary where bad data enters;
       make invalid states unrepresentable; add the regression test that fails before and
       passes after. Name what else the same cause could break (the "blast radius").
    8. **Self-check**: does the diagnosis explain *every* symptom, including the timing and
       the "why now"? If not, say what's unexplained.

    ## Frameworks
    - **The debugging loop**: Observe → Hypothesise → Predict → Experiment → Conclude. Never
      skip Predict: state what you expect to see before running the experiment.
    - **Read the error message literally.** Half of all bugs are stated in the message
      (`KeyError: 'user_id'` means the key is missing, not that the dict is None).
    - **Five root-cause families**: wrong data in (validation), wrong state (ordering/race/
      caching), wrong environment (versions/config/locale/tz), wrong assumption (API contract),
      wrong code (logic). Classify every hypothesis; it tells you where to instrument.
    - **Bisect math**: log2(N) steps, rounded up — 100 commits = 7 tests. Cheaper than reading.
    - **Timing tells**: intermittent under load → race or resource exhaustion; only at a
      specific time → cron/tz/expiry; only for some users → data-dependent; after deploy →
      regression; after nothing changed → dependency, cert, disk, quota, upstream.
    - **When to stop instrumenting**: when one experiment can distinguish your top two hypotheses.

    ## Output format
    ```
    ## Diagnosis: <one line naming cause and location, or "Top hypothesis: … (unconfirmed)">
    **Error:** `<Type>: <message>` · **Blame frame:** `<file>:<line> in <fn>` · **Family:** <data|state|env|assumption|logic>

    ### What the evidence says
    - <fact from trace/logs/env diff> → <what it implies>

    ### Hypotheses (ranked)
    1. **<mechanism>** — for: … / against: … / test: `<command or code, < 5 min>`
    2. …

    ### Reproduce
    `<minimal command or test>`

    ### Fix
    <diff or code at the cause> + regression test name
    **Blast radius:** <what else this cause affects>
    **Unexplained:** <symptoms this diagnosis doesn't cover, or "none">
    ```

    ## Anti-patterns
    - Fixing the frame that threw instead of the frame that produced the bad value.
    - "Try adding a null check" — that hides the bug; ask why the value is null.
    - Reading 5,000 log lines top to bottom instead of clustering and looking at first-seen order.
    - Presenting the most likely hypothesis as fact. Confidence words must match evidence.
    - Suggesting "clear the cache / restart / reinstall" without a mechanism.
    - Skipping the regression test. A fix without a failing-then-passing test is a hope.
    """,
)

# ── stack trace parsing ──────────────────────────────────────────────────────

PY_FRAME = re.compile(r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<fn>\S+))?')
PY_EXC = re.compile(r"^(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning|Fault|Timeout|Denied|Found|Stop\w*)?)(?:: (?P<msg>.*))?$")
JS_FRAME = re.compile(r"^\s*at (?:async )?(?:new )?(?:(?P<fn>[^()]+?) \()?(?P<file>(?:node:|file://)?[^():]+?):(?P<line>\d+)(?::(?P<col>\d+))?\)?\s*$")
JS_EXC = re.compile(r"^(?:Uncaught )?(?P<type>[A-Z][\w.$]*(?:Error|Exception|Rejection)?)(?:\s*\[(?P<code>[A-Z_]+)\])?: (?P<msg>.*)$")
JAVA_FRAME = re.compile(r"^\s*at (?P<fn>[\w$.<>]+)\((?P<file>[^:)]+)(?::(?P<line>\d+))?\)")
JAVA_EXC = re.compile(r"^(?:Exception in thread \"[^\"]*\" )?(?:Caused by: )?(?P<type>[a-z][\w.]*\.[A-Z][\w$]*(?:Exception|Error|Throwable)?)(?:: (?P<msg>.*))?$")
GO_FILE = re.compile(r"^\s*(?P<file>/?[\w./\-@]+\.go):(?P<line>\d+)")
GO_FN = re.compile(r"^(?P<fn>[\w./\-@]+(?:\([^)]*\))?[\w.]*)\((?:[^)]*)\)$")
RUBY_FRAME = re.compile(r"^\s*(?:from )?(?P<file>[^:\s]+):(?P<line>\d+):in [`'](?P<fn>[^'`]+)'")
RUBY_EXC = re.compile(r"^.*?:\d+:in [`'][^'`]+': (?P<msg>.*) \((?P<type>[A-Z][\w:]+)\)$")

LIB_PATH = re.compile(
    r"site-packages|dist-packages|node_modules|/usr/lib/python|<frozen |internal/|node:internal|\bwebpack\b|/vendor/|/gems/|"
    r"^(java|javax|jdk|sun|kotlin|org\.springframework|org\.hibernate|org\.apache|io\.netty|com\.google|reactor\.)|"
    r"^(runtime|net/http|encoding/|database/sql|reflect)\b|/go/pkg/mod/|/usr/local/go/",
)

HINTS = {
    "KeyError": "A dict/mapping is missing that key. Find where the mapping is built — the producer changed shape, or the key is conditionally present.",
    "AttributeError": "If the message says 'NoneType', a function up the call chain returned None (usually a lookup miss or an early return). Trace the variable back to its source.",
    "TypeError": "Wrong type or wrong arity. Common causes: API signature changed after a dependency bump, str vs bytes, None arithmetic, calling a module instead of a function.",
    "ValueError": "Right type, bad value. Check parsing at the boundary (int('') / date strings / enum values).",
    "IndexError": "Empty or shorter-than-expected sequence. Look for off-by-one or an empty result treated as non-empty.",
    "ImportError": "Module or name missing: dependency not installed in this environment, version mismatch, or circular import.",
    "ModuleNotFoundError": "Dependency not installed in *this* environment (venv/CI image) or wrong working directory/PYTHONPATH.",
    "RecursionError": "Unbounded recursion — usually a cycle in data, a __getattr__ that references itself, or a missing base case.",
    "UnicodeDecodeError": "Bytes decoded with the wrong encoding; the default encoding differs between machines (locale). Pass encoding explicitly.",
    "ConnectionError": "Network/DNS/port; check the target host from *this* machine, TLS, and proxies before reading code.",
    "TimeoutError": "Slow dependency or deadlock. Check pool exhaustion, lock ordering, and whether the timeout is realistic under load.",
    "AssertionError": "An invariant the author believed in is false. The assert's message/condition is the exact question to answer.",
    "PermissionError": "File/dir permissions differ between environments (container user, mounted volume, umask).",
    "MemoryError": "Unbounded growth — loading whole files/results into memory, a leak in a long-lived process, or a pathological input size.",
    "NullPointerException": "A reference is null where code assumed non-null. Find the producer: Optional.get without isPresent, map.get miss, uninitialised field, or a mocked dependency returning null.",
    "ClassCastException": "Runtime type differs from the declared one — generics erasure, serialisation, or a proxy/mock.",
    "ConcurrentModificationException": "Collection mutated while iterated — usually another thread or removal inside a for-each.",
    "OutOfMemoryError": "Heap exhausted: unbounded cache/collection, huge result set, or -Xmx too small for the workload.",
    "StackOverflowError": "Infinite recursion — cyclic data or recursive toString/equals/hashCode.",
    "IllegalArgumentException": "Precondition failed on a parameter. The message usually names the parameter; find the caller that passes it.",
    "IllegalStateException": "Called out of order (used after close, started twice, not initialised). Check lifecycle.",
    "ReferenceError": "Variable not defined — typo, missing import, temporal dead zone (let/const used before declaration), or a browser-only global in Node.",
    "RangeError": "Invalid length/argument (array size, recursion depth 'Maximum call stack size exceeded', toFixed digits).",
    "SyntaxError": "Usually a JSON.parse on non-JSON (an HTML error page, an empty body) — log the raw text before parsing.",
    "UnhandledPromiseRejection": "An async error had no catch. Add the handler where the promise is awaited, and check for a missing `await`.",
    "ECONNREFUSED": "Nothing is listening at that host:port from this machine — wrong host in config, service not up yet, or localhost inside a container.",
    "NoMethodError": "Called a method on nil or the wrong object — the receiver came from a lookup that returned nil.",
    "nil pointer dereference": "A pointer/interface was nil — usually an error return that was ignored, or a struct field never set.",
    "index out of range": "Slice/array index beyond length — empty result treated as non-empty, or off-by-one on len().",
    "deadlock": "All goroutines blocked — unbuffered channel with no receiver, or WaitGroup count mismatch.",
}


MESSAGE_HINTS = [
    (re.compile(r"Cannot read propert(y|ies) of (undefined|null)|undefined is not an object|null is not an object|is not a function", re.I),
     "A value is undefined/null where an object was expected. Find the producer: a missing field in an API/DB response, an un-awaited promise, a wrong destructuring, or an optional chain that should have been a validation error."),
]


def _hint(exc_type: str, message: str) -> str:
    for rx, h in MESSAGE_HINTS:
        if rx.search(message or ""):
            return h
    short = exc_type.rsplit(".", 1)[-1]
    if short in HINTS:
        return HINTS[short]
    for key, h in HINTS.items():
        if key.lower() in message.lower():
            return h
    return "No canned hint — read the message literally and trace the failing value back to where it was produced."


def _finish_frames(frames: list[dict]) -> None:
    for f in frames:
        f["in_user_code"] = not LIB_PATH.search(f["file"] or "") and not LIB_PATH.search(f.get("function") or "")


@AGENT.tool
def parse_stack_trace(trace: str) -> dict:
    """Parse a stack trace (Python, JavaScript/Node, Java/Kotlin, Go, Ruby) into frames, the exception chain, and the blame frame in the user's own code.

    Call first whenever there is a traceback. Frames are ordered innermost (where it threw) first.

    Args:
        trace: The raw stack trace text, including the exception line.
    """
    trace = require_text(trace, "trace", 200_000)
    lines = trace.splitlines()
    language = None
    if re.search(r"Traceback \(most recent call last\)|^\s*File \".+\", line \d+", trace, re.M):
        language = "python"
    elif re.search(r"^\s*at [\w$.<>]+\([\w$]+\.(java|kt|scala):\d+\)", trace, re.M) or re.search(r"^\s*at [\w$.<>]+\((Native Method|Unknown Source)\)", trace, re.M):
        language = "java"
    elif re.search(r"^\s*at .+:\d+:\d+\)?\s*$", trace, re.M):
        language = "javascript"
    elif re.search(r"^goroutine \d+ \[|^panic: ", trace, re.M) or re.search(r"^\s*\S+\.go:\d+", trace, re.M):
        language = "go"
    elif re.search(r":\d+:in [`']", trace):
        language = "ruby"
    if not language:
        raise ToolError("Couldn't recognise a Python, JavaScript, Java, Go or Ruby stack trace. Paste the full trace including 'File …, line …' / 'at …' lines.")

    chain: list[dict] = []  # each: {type, message, frames}
    frames: list[dict] = []
    exc_type, exc_msg = "", ""

    if language == "python":
        segments = re.split(r"\n(?=(?:During handling of the above exception|The above exception was the direct cause))", trace)
        links = re.findall(r"^(During handling of the above exception|The above exception was the direct cause)", trace, re.M)
        for seg in segments:
            seg_frames, cur_type, cur_msg = [], "", ""
            seg_lines = seg.splitlines()
            i = 0
            while i < len(seg_lines):
                m = PY_FRAME.match(seg_lines[i])
                if m:
                    seg_frames.append({"file": m.group("file"), "line": int(m.group("line")), "function": m.group("fn") or "<module>"})
                    i += 1
                    continue
                s = seg_lines[i].strip()
                if seg_frames and s and not s.startswith(("Traceback", "During handling", "The above", "^", "~")) and not seg_lines[i].startswith("    "):
                    m2 = PY_EXC.match(s)
                    if m2 and (m2.group("type").endswith(("Error", "Exception", "Exit", "Interrupt", "Warning", "Fault", "Timeout", "Denied", "Found")) or ":" in s or "." in m2.group("type")):
                        cur_type, cur_msg = m2.group("type"), (m2.group("msg") or "").strip()
                i += 1
            if seg_frames:
                seg_frames.reverse()  # innermost first
                chain.append({"type": cur_type, "message": cur_msg, "frames": seg_frames})
        if chain:
            last = chain[-1]  # the exception that actually propagated
            frames, exc_type, exc_msg = last["frames"], last["type"], last["message"]
            root = chain[0]
    elif language in ("javascript", "java"):
        FR, EX = (JS_FRAME, JS_EXC) if language == "javascript" else (JAVA_FRAME, JAVA_EXC)
        cur: dict | None = None
        for ln in lines:
            fm = FR.match(ln)
            if fm and cur is not None:
                cur["frames"].append({"file": fm.group("file"), "line": int(fm.group("line")) if fm.groupdict().get("line") else None, "function": fm.group("fn") or "<anonymous>"})
                continue
            if fm and cur is None:
                cur = {"type": "", "message": "", "frames": [{"file": fm.group("file"), "line": int(fm.group("line")) if fm.group("line") else None, "function": fm.group("fn") or "<anonymous>"}]}
                chain.append(cur)
                continue
            em = EX.match(ln.strip())
            if em:
                cur = {"type": em.group("type"), "message": (em.group("msg") or "").strip(), "frames": []}
                if language == "javascript" and em.groupdict().get("code"):
                    cur["message"] = f"[{em.group('code')}] " + cur["message"]
                chain.append(cur)
        chain = [c for c in chain if c["frames"] or c["type"]]
        if chain:
            first = chain[0]
            frames, exc_type, exc_msg = first["frames"], first["type"], first["message"]
            root = chain[-1]  # Java: last "Caused by" is the root cause
    elif language == "go":
        m = re.search(r"^panic: (.*?)(?: \[recovered\])?$", trace, re.M) or re.search(r"^fatal error: (.*)$", trace, re.M)
        exc_type, exc_msg = ("panic", m.group(1).strip()) if m else ("error", "")
        em = re.match(r"^(runtime error: )?(.*)$", exc_msg)
        pending_fn = None
        for ln in lines:
            fm = GO_FILE.match(ln)
            if fm:
                frames.append({"file": fm.group("file"), "line": int(fm.group("line")), "function": pending_fn or "?"})
                pending_fn = None
                continue
            fn = GO_FN.match(ln.strip())
            if fn and not ln.startswith(("goroutine", "panic", "fatal")):
                pending_fn = fn.group("fn")
        frames = [f for f in frames if not re.search(r"runtime/panic\.go|runtime/proc\.go|asm_\w+\.s", f["file"])]
        chain = [{"type": exc_type, "message": exc_msg, "frames": frames}]
        root = chain[0]
    else:  # ruby
        em = RUBY_EXC.search(trace)
        exc_type, exc_msg = (em.group("type"), em.group("msg")) if em else ("", "")
        for ln in lines:
            fm = RUBY_FRAME.match(ln)
            if fm:
                frames.append({"file": fm.group("file"), "line": int(fm.group("line")), "function": fm.group("fn")})
        chain = [{"type": exc_type, "message": exc_msg, "frames": frames}]
        root = chain[0]

    if not chain or (not frames and not exc_type):
        raise ToolError(f"Detected {language} but found no frames or exception line. Paste the complete trace.")
    for c in chain:
        _finish_frames(c["frames"])
    _finish_frames(frames)
    blame = next((f for f in frames if f["in_user_code"]), None)
    origin = frames[0] if frames else None
    root_blame = next((f for f in root["frames"] if f["in_user_code"]), None) if chain else None
    user_frames = [f for f in frames if f["in_user_code"]]
    notes = []
    if origin and not origin["in_user_code"]:
        notes.append(f"Threw inside a library ({origin['file']}); the bad input came from your frame {blame['file']}:{blame['line']} — start there." if blame else "Threw inside a library and no user-code frame found: likely a config/env/dependency issue, not application code.")
    chain_kind = None
    if language == "python" and len(chain) > 1:
        chain_kind = "implicit" if links and all(l.startswith("During handling") for l in links) else "explicit"
    if chain_kind == "implicit":
        root = chain[-1]
        root_blame = next((f for f in root["frames"] if f["in_user_code"]), None)
        notes.append(
            f"Implicit chain of {len(chain)} ('During handling of the above exception…'): `{chain[0]['type']}` was being handled when "
            f"`{exc_type}` was raised inside the handler. The final exception is the bug to fix; the first is context "
            "(often an expected miss/fallback) — check whether the fallback path itself is what's broken."
        )
    elif len(chain) > 1:
        notes.append(f"Exception chain of {len(chain)}: the root cause is `{root['type']}: {root['message'][:120]}`; fix that, not the outer one.")
    if exc_type and "NoneType" in exc_msg:
        notes.append("'NoneType' in the message: something returned None. Find that producer, not the consumer.")
    return {
        "language": language,
        "exception_type": exc_type,
        "message": exc_msg,
        "frames": frames[:60],
        "frame_count": len(frames),
        "user_code_frames": user_frames[:20],
        "origin_frame": origin,
        "blame_frame": blame,
        "chain": [{"type": c["type"], "message": c["message"][:200], "frames": len(c["frames"]), "blame_frame": next((f for f in c["frames"] if f["in_user_code"]), None)} for c in chain],
        "root_cause_exception": {"type": root["type"], "message": root["message"][:200], "blame_frame": root_blame} if chain else None,
        "chain_kind": chain_kind,
        "hint": _hint(exc_type, exc_msg),
        "notes": notes,
        "verdict": (
            f"{exc_type}: {exc_msg[:100]} — look first at {blame['file']}:{blame['line']} in {blame['function']}."
            if blame else f"{exc_type}: {exc_msg[:100]} — no user-code frame; suspect environment or dependency."
        ),
    }


# ── log clustering ───────────────────────────────────────────────────────────

TS_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)|"
    r"(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2})|(\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b)"
)
LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|ERR|CRIT(?:ICAL)?|FATAL|PANIC|SEVERE)\b")
MASKS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<ts>"),
    (re.compile(r"\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b"), "<time>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<uuid>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
    (re.compile(r"https?://\S+"), "<url>"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<hex>"),
    (re.compile(r"\b[0-9a-f]{12,}\b", re.I), "<hash>"),
    (re.compile(r"(['\"])(?:(?!\1).){0,200}\1"), "<str>"),
    (re.compile(r"(?<=[=:/#\[(])\s?[\w-]*\d[\w-]*"), "<id>"),
    (re.compile(r"(?<![\w<])[-+]?\d+(?:\.\d+)?(?:ms|s|us|µs|KB|MB|GB|%)?\b"), "<n>"),
]


CHANGE_RE = re.compile(r"\b(deploy(ed|ing|ment)?|released?|rollout|rolled out|upgraded?|migrat\w*|config(uration)? (reload(ed)?|change[d]?|update[d]?)|feature[ _-]?flag|flag (enabled|disabled|flipped)|restart(ed|ing)?|failover)\b", re.I)


def _normalise_line(line: str) -> str:
    s = line
    for rx, tok in MASKS:
        s = rx.sub(tok, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:300]


def _parse_ts(line: str) -> str | None:
    m = TS_RE.search(line)
    return next((g for g in m.groups() if g), None) if m else None


@AGENT.tool
def cluster_logs(logs: str, max_clusters: int = 25) -> dict:
    """Collapse noisy log lines into templates (numbers, ids, timestamps masked) with counts, levels, first/last seen and the busiest minute.

    Call when there are more than ~30 log lines. Read first-seen order, not just volume.

    Args:
        logs: Raw log text, one event per line.
        max_clusters: How many templates to return, most frequent first (max 100).
    """
    logs = require_text(logs, "logs", 2_000_000)
    lines = [l for l in logs.splitlines() if l.strip()]
    if len(lines) > 50_000:
        raise ToolError(f"{len(lines):,} lines — cap is 50,000. Filter to the incident window first.")
    max_clusters = max(1, min(int(max_clusters), 100))
    clusters: dict[str, dict] = {}
    levels: Counter[str] = Counter()
    per_minute: Counter[str] = Counter()
    error_per_minute: Counter[str] = Counter()
    for idx, line in enumerate(lines):
        lm = LEVEL_RE.search(line[:120])
        level = lm.group(1).upper() if lm else "UNKNOWN"
        level = {"WARNING": "WARN", "ERR": "ERROR", "CRIT": "CRITICAL", "SEVERE": "ERROR"}.get(level, level)
        levels[level] += 1
        ts = _parse_ts(line)
        template = _normalise_line(line)
        c = clusters.get(template)
        if c is None:
            c = clusters[template] = {"template": template, "count": 0, "level": level, "first_seen": ts, "first_line": idx + 1, "last_seen": ts, "example": line.strip()[:300]}
        c["count"] += 1
        if ts:
            c["last_seen"] = ts
            minute = ts[:16] if len(ts) >= 16 else ts[:5]
            per_minute[minute] += 1
            if level in ("ERROR", "CRITICAL", "FATAL", "PANIC"):
                error_per_minute[minute] += 1
    total = len(lines)
    ordered = sorted(clusters.values(), key=lambda c: -c["count"])
    for c in ordered:
        c["share_pct"] = round(100 * c["count"] / total, 1)
    error_clusters = [c for c in ordered if c["level"] in ("ERROR", "CRITICAL", "FATAL", "PANIC")]
    by_first = sorted((c for c in ordered if c["level"] in ("ERROR", "CRITICAL", "FATAL", "PANIC", "WARN")), key=lambda c: c["first_line"])
    first_problem_line = by_first[0]["first_line"] if by_first else None
    changes = [
        {"line": c["first_line"], "first_seen": c["first_seen"], "event": c["example"][:200]}
        for c in sorted(clusters.values(), key=lambda c: c["first_line"])
        if c["level"] not in ("ERROR", "CRITICAL", "FATAL", "PANIC", "WARN") and CHANGE_RE.search(c["example"])
        and (first_problem_line is None or c["first_line"] <= first_problem_line)
    ][-5:]
    busiest = per_minute.most_common(1)[0] if per_minute else None
    busiest_err = error_per_minute.most_common(1)[0] if error_per_minute else None
    n_err = sum(levels[k] for k in ("ERROR", "CRITICAL", "FATAL", "PANIC"))
    verdict = f"{total:,} lines → {len(clusters)} templates; {n_err:,} error-level ({round(100 * n_err / total, 1)}%)."
    if error_clusters:
        verdict += f" Top error: \"{error_clusters[0]['template'][:90]}\" ×{error_clusters[0]['count']}."
    if by_first:
        verdict += f" First problem template appears at line {by_first[0]['first_line']}: \"{by_first[0]['template'][:80]}\"."
    if changes and by_first:
        verdict += f" Change just before it (line {changes[-1]['line']}): \"{changes[-1]['event'][:90]}\" — prime suspect."
    return {
        "total_lines": total,
        "unique_templates": len(clusters),
        "levels": dict(levels.most_common()),
        "error_lines": n_err,
        "clusters": ordered[:max_clusters],
        "error_clusters": error_clusters[:max_clusters],
        "first_problems_in_order": [{"line": c["first_line"], "first_seen": c["first_seen"], "level": c["level"], "template": c["template"], "count": c["count"]} for c in by_first[:10]],
        "changes_before_first_problem": changes,
        "busiest_minute": {"minute": busiest[0], "lines": busiest[1]} if busiest else None,
        "busiest_error_minute": {"minute": busiest_err[0], "errors": busiest_err[1]} if busiest_err else None,
        "verdict": verdict,
    }


# ── bisect ───────────────────────────────────────────────────────────────────


@AGENT.tool
def bisect_plan(commit_count: int = 0, commits: list[str] | None = None, good_ref: str = "", bad_ref: str = "HEAD", minutes_per_test: float = 5) -> dict:
    """Plan a git bisect: exact number of steps, the first commit to test, time estimate, and the command sequence.

    Call for regressions with a known-good ref and more than ~8 candidate commits. Pass either
    the commit count or the ordered list of commits (oldest first).

    Args:
        commit_count: Number of commits between good and bad (exclusive of good). Ignored if `commits` is given.
        commits: Ordered candidate commit SHAs/titles, oldest → newest (max 5000).
        good_ref: A ref known to work (tag, SHA, branch).
        bad_ref: A ref known to fail. Defaults to HEAD.
        minutes_per_test: How long one build+test cycle takes, for the time estimate.
    """
    commits = list(commits or [])
    if len(commits) > 5000:
        raise ToolError("Too many commits (max 5000).")
    n = len(commits) if commits else int(commit_count)
    if n <= 0:
        raise ToolError("Give a positive commit_count or a non-empty commits list.")
    steps = math.ceil(math.log2(n)) if n > 1 else 0
    linear = n - 1
    mid = n // 2
    first = commits[mid] if commits else f"commit #{mid + 1} of {n} (0-based index {mid})"
    saved = linear - steps
    good = good_ref or "<good-ref>"
    cmds = [
        f"git bisect start {bad_ref} {good}",
        "# build + run the failing test; then:",
        "git bisect good   # or: git bisect bad",
        f"# repeat ~{steps} times; or automate:",
        f"git bisect run <test-command>   # exit 0 = good, 1-124 = bad, 125 = skip",
        "git bisect reset",
    ]
    if minutes_per_test <= 0:
        raise ToolError("minutes_per_test must be positive.")
    return {
        "candidates": n,
        "steps": steps,
        "linear_steps_avoided": max(0, saved),
        "first_commit_to_test": first,
        "estimated_minutes": round(steps * minutes_per_test, 1),
        "estimated_minutes_linear": round(linear * minutes_per_test, 1),
        "commands": cmds,
        "tips": [
            "Make the test deterministic first; a flaky test makes bisect lie.",
            "If a commit won't build, `git bisect skip` it rather than guessing.",
            "Bisect on the smallest reproducer, not the full suite.",
        ],
        "verdict": f"{n} candidates → {steps} test(s) instead of up to {linear}; ~{round(steps * minutes_per_test)} min. Test {first} first.",
    }


# ── suspect ranking ──────────────────────────────────────────────────────────


def _path_match(a: str, b: str) -> int:
    """0 = no match, 1 = basename match, 2 = suffix path match, 3 = exact."""
    a, b = a.replace("\\", "/"), b.replace("\\", "/")
    if a == b:
        return 3
    if a.endswith("/" + b) or b.endswith("/" + a):
        return 2
    if a.rsplit("/", 1)[-1] == b.rsplit("/", 1)[-1]:
        return 1
    return 0


@AGENT.tool
def rank_suspects(frames: list[dict], changed_files: list[str], error_message: str = "") -> dict:
    """Rank recently changed files by how likely they caused the failure, using trace frames, path overlap and message keywords.

    Call after parse_stack_trace with the `frames` it returned and the files changed in the
    last deploy/PR (`git diff --name-only good..bad`).

    Args:
        frames: Frames from parse_stack_trace (each has file, line, function, in_user_code), innermost first.
        changed_files: Paths changed recently, most recent first if known.
        error_message: The exception message, for keyword overlap with file/function names.
    """
    changed_files = bound_list(changed_files, "changed_files", 2000)
    if not isinstance(frames, list):
        raise ToolError("frames must be a list.")
    frames = frames[:200]
    words = {w.lower() for w in re.findall(r"[A-Za-z_]{4,}", error_message or "")}
    blame_idx = next((i for i, f in enumerate(frames) if f.get("in_user_code")), None)
    results = []
    for order, path in enumerate(changed_files):
        if not isinstance(path, str) or not path.strip():
            continue
        score, reasons = 0, []
        best = 0
        for i, fr in enumerate(frames):
            m = _path_match(path, str(fr.get("file", "")))
            if m and m >= best:
                best = m
                pts = 60 if i == blame_idx else 40 if fr.get("in_user_code") else 15
                pts -= min(10, i)  # deeper in the stack = slightly less
                if pts > score:
                    score, reasons = pts, [f"in trace at frame {i} ({fr.get('function')}:{fr.get('line')}){' — blame frame' if i == blame_idx else ''}"]
        stem = re.sub(r"\.\w+$", "", path.rsplit("/", 1)[-1]).lower()
        if words and any(w in stem or stem in w for w in words if len(stem) >= 4):
            score += 15
            reasons.append("name appears in the error message")
        if re.search(r"(^|/)(config|settings|env|schema|migration|requirements|package\.json|lock|Dockerfile)", path, re.I):
            score += 12
            reasons.append("config/dependency/schema change — affects everything")
        if re.search(r"(^|/)(tests?|docs?)/|\.md$", path):
            score -= 20
            reasons.append("test/docs file — unlikely cause")
        recency = max(0, 8 - order)
        score += recency
        if recency and order < 3:
            reasons.append("among the most recent changes")
        results.append({"file": path, "score": max(0, score), "reasons": reasons or ["changed, but not in the trace"]})
    results.sort(key=lambda r: -r["score"])
    top = results[0] if results else None
    return {
        "ranked": results[:50],
        "in_trace": [r["file"] for r in results if any("in trace" in x for x in r["reasons"])],
        "verdict": (f"Start with {top['file']} (score {top['score']}: {'; '.join(top['reasons'])})." if top and top["score"] >= 20
                    else "No changed file appears in the trace — suspect data, environment, or an upstream dependency rather than this change."),
    }


# ── environment comparison ───────────────────────────────────────────────────

VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _vtuple(v: str) -> tuple | None:
    m = VERSION_RE.match(str(v).strip())
    return tuple(int(x or 0) for x in m.groups()) if m else None


@AGENT.tool
def compare_environments(working: dict, broken: dict) -> dict:
    """Diff a working environment against a broken one (versions, env vars, OS, locale, flags) and rank the differences by how often they cause 'works on my machine' bugs.

    Args:
        working: Key → value for the environment where it works (e.g. {"python": "3.11.4", "TZ": "UTC", "django": "4.2"}).
        broken: Same keys for the environment where it fails.
    """
    if not isinstance(working, dict) or not isinstance(broken, dict) or not (working or broken):
        raise ToolError("Give two non-empty dicts of key → value.")
    if len(working) + len(broken) > 2000:
        raise ToolError("Too many keys (max 2000 combined).")
    keys = sorted(set(working) | set(broken), key=str.lower)
    diffs, same = [], 0
    for k in keys:
        a, b = working.get(k), broken.get(k)
        if str(a).strip() == str(b).strip():
            same += 1
            continue
        kl = k.lower()
        weight, why = 30, "differs"
        if a is None or b is None:
            weight, why = 70, "missing on one side"
        elif _vtuple(str(a)) and _vtuple(str(b)):
            va, vb = _vtuple(str(a)), _vtuple(str(b))
            if va[0] != vb[0]:
                weight, why = 90, "MAJOR version differs — breaking changes likely"
            elif va[1] != vb[1]:
                weight, why = 65, "minor version differs — behaviour/deprecations"
            else:
                weight, why = 35, "patch version differs"
        if re.search(r"^(python|node|java|ruby|go|php|dotnet|rust|npm|pip|openssl|glibc|postgres|mysql|redis)\b", kl):
            weight += 15
            why += "; runtime/platform"
        if re.search(r"(^|_)(tz|timezone|lang|lc_|locale|encoding|charset)", kl):
            weight += 30
            why += "; locale/tz — classic silent-difference bug"
        if re.search(r"(debug|flag|feature|env|mode|stage)", kl):
            weight += 10
            why += "; behaviour switch"
        if re.search(r"(secret|token|password|key)", kl):
            a_disp, b_disp = ("<set>" if a else "<missing>"), ("<set>" if b else "<missing>")
        else:
            a_disp, b_disp = (str(a)[:80] if a is not None else None), (str(b)[:80] if b is not None else None)
        diffs.append({"key": k, "working": a_disp, "broken": b_disp, "weight": min(100, weight), "why": why})
    diffs.sort(key=lambda d: -d["weight"])
    top = diffs[0] if diffs else None
    return {
        "compared": len(keys),
        "identical": same,
        "differences": diffs,
        "verdict": (f"{len(diffs)} difference(s). Test first: {top['key']} ({top['working']} vs {top['broken']}) — {top['why']}."
                    if top else "Environments identical on the keys given — the difference is in data, timing, or something not captured here (network, permissions, disk)."),
    }
