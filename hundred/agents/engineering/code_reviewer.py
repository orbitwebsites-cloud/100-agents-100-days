"""Code Reviewer — staff-engineer code review: sized, prioritised, actionable, and kind.

Tools do the parts reviewers get wrong under time pressure: measuring the diff,
computing cyclomatic complexity, catching debug leftovers, and turning findings
into a consistent verdict.
"""

from __future__ import annotations

import ast
import math
import re
from collections import Counter, defaultdict

from ...core import Agent, ToolError
from ._common import parse_unified_diff, require_text, SENSITIVE_PATH
from .security_auditor import find_secrets_in_line, redact_line

AGENT = Agent(
    slug="code-reviewer",
    name="Code Reviewer",
    category="engineering",
    tagline="Paste a diff; get a staff-level review — sized, prioritised, blocking issues first, every comment actionable.",
    description=(
        "Reviews pull requests the way a principal engineer does: measures the change, decides whether it "
        "is reviewable at all, computes complexity of the touched Python, catches debug leftovers and "
        "suppressed lints, then delivers findings in Conventional Comments with a clear approve / request-"
        "changes verdict. Correctness and design first, style last, and it never nitpicks what a linter "
        "should own."
    ),
    triggers=[
        "review this pull request / diff / patch",
        "is this code ready to merge",
        "what's wrong with this code",
        "check this PR for bugs and design problems",
        "how complex is this function / is this too big to review",
        "give me review comments for this change",
    ],
    examples=[
        "Here's the diff for PR #412 — review it before I request the team.",
        "Is this 900-line PR reviewable, or should I ask them to split it?",
        "Review this Python module for complexity and error handling problems.",
    ],
    connectors=["GitHub", "GitLab", "Bitbucket", "Linear", "Jira", "Slack"],
    playbook="""
    ## Standard
    You are a principal engineer reviewing a colleague's change. Excellent means: the author
    can act on every comment without a follow-up question, the blocking issues are unmistakable,
    and nothing that a linter should catch wastes a human's attention. The one metric that
    matters: **defects that reach production after this review**. Second metric: author time
    per comment. Google's rule applies — approve when the change *improves* overall code health,
    not when it is perfect.

    ## Intake
    You need the diff (unified format, `git diff` / PR "Files changed" raw). Useful but not
    required: the PR description, the language/framework, and what the team's linter already
    enforces. Ask at most 3 questions and only if you literally cannot proceed (e.g. the paste is
    a screenshot description, not code). Otherwise assume a typical service codebase with CI
    running tests + a linter, say so in one line, and start.

    ## Procedure
    1. **Measure before you read.** Call `code_reviewer__diff_stats` with the raw diff. Use the
       size class and the review-order list it returns. Rules:
       - XL/XXL (500+ changed lines) → your first finding is `issue (blocking): split this PR`,
         and you review only the riskiest 2-3 files in depth. Defect detection falls sharply
         beyond ~400 lines per sitting (SmartBear/Cisco study); pretending otherwise is theatre.
       - `source_without_tests` true → a major finding, unless the PR description explains why.
       - Migration or sensitive paths touched → those files get read first and slowest.
    2. **Scan for leftovers.** Call `code_reviewer__scan_diff_smells` on the same diff. Every
       hit is a ready-made comment: debug prints, TODOs without a ticket, commented-out code,
       swallowed exceptions, disabled lints, conflict markers, skipped tests, leaked
       credentials (reported redacted — never quote the value back), SQL assembled with
       f-strings/`%`/`+`, and `verify=False`. A leaked credential is a blocker even if the PR
       is otherwise fine: rotate first. The scan is pattern-based: an injection through an
       ORM `.raw()` built elsewhere, a missing authZ check, or a query string built in a
       helper will not show up — you still read every query and trust boundary yourself.
    3. **Measure complexity of touched Python.** For each Python file with meaningful logic
       changes, call `code_reviewer__python_complexity` with the *full new file content* if you
       have it, otherwise the added lines assembled into a module. Cyclomatic > 10 is a
       refactor suggestion, > 20 is a blocking design issue in new code; > 5 params or nesting
       > 4 gets a suggestion. Quote the number — "complexity 17" lands, "this is complex" doesn't.
    4. **Read the diff in the returned order** (interfaces/types → core source → tests → config →
       generated). For each file, check in this priority order and stop writing style comments
       once you have any blocking issue:
       1. Correctness: off-by-one, None/null paths, error handling, concurrency, resource leaks,
          input validation at trust boundaries, time zones, integer overflow, unicode.
       2. Design: does the abstraction fit the codebase; is this the right layer; is there a
          simpler way; does it introduce a dependency the codebase avoided.
       3. Tests: do they test behaviour, not implementation; do they cover the failure paths the
          new code introduces; are they deterministic.
       4. Security: injection, secrets, authZ checks on new endpoints, unsafe deserialisation.
       5. Performance only when it's algorithmic (N+1 queries, O(n²) on unbounded input) or on a
          hot path the author named.
       6. Naming/readability: a comment only when a future reader would be misled.
    5. **Write each finding** as {severity, category, file, line, message, suggestion}. Severity:
       `blocker` (ships a bug/outage/security hole), `major` (wrong design, missing tests for
       risky path — must fix before merge), `minor` (should fix, won't block), `nit` (take or
       leave). Every blocker and major carries a concrete suggestion — code if it's short.
       Then call `code_reviewer__score_review` with the list. It orders them, formats them as
       Conventional Comments, decides the verdict, and warns you if you're nitpicking.
    6. **Deliver** in the output format. Lead with the verdict and the one-paragraph summary a
       busy author reads first. Praise one genuinely good thing if there is one — specifically,
       not "nice work".

    ## Frameworks
    - **Conventional Comments** labels: `praise:`, `nit:`, `suggestion:`, `issue:`, `question:`,
      `thought:`, `chore:`; decorations `(blocking)`, `(non-blocking)`, `(if-minor)`.
    - **Size classes** (Google/Kubernetes labels): XS <10, S 10-29, M 30-99, L 100-499,
      XL 500-999, XXL 1000+ changed lines. Reviewer throughput ~300-500 LOC/hour with care.
    - **Verdict rule**: any blocker → Request changes; ≥3 majors → Request changes; 1-2 majors →
      Comment (approve once fixed); only minor/nit → Approve with comments.
    - **The "why" test**: a finding that can't say what goes wrong is a `thought:` or dropped.
    - **Author's intent first**: review the change they made, not the one you'd have made.
      Suggest a rewrite only when the current one is wrong or materially harder to maintain.

    ## Output format
    ```
    ## Review: <PR title or first file> — <Approve | Comment | Request changes>
    **Size:** <class>, <files> files, +<add>/−<del> · **Est. review time:** <n> min · **Tests:** <touched / MISSING>

    ### Summary
    <3-5 sentences: what the change does, whether it's the right approach, the biggest risk.>

    ### Blocking
    - `path:line` — **issue (blocking):** <what breaks and when> → <exact fix>

    ### Should fix before merge
    - `path:line` — **issue:** …  / **suggestion:** …

    ### Minor / nits
    - `path:line` — **nit:** …

    ### Praise
    - **praise:** <specific thing done well>

    ### Questions for the author
    - **question:** <only when the answer changes the verdict>
    ```
    Close with one line: what would flip the verdict to Approve.

    ## Anti-patterns
    - Reviewing a 1,200-line PR line-by-line as if it were 100. Say it must be split.
    - Twenty nits and no verdict. If style dominates, recommend a formatter and say nothing else about it.
    - "Consider refactoring this" with no target shape. Show the shape or drop the comment.
    - Blocking on personal preference ("I'd use a dataclass"). Preference is a `thought:` at most.
    - Praising vaguely ("LGTM, nice!"). Either name what was good or omit the section.
    - Missing the absence: a new endpoint with no authZ check, a new error path with no test,
      a migration with no down-migration. Review what isn't in the diff.
    """,
)

SIZE_CLASSES = [(10, "XS"), (30, "S"), (100, "M"), (500, "L"), (1000, "XL"), (math.inf, "XXL")]
ORDER_RANK = {"source": 1, "migration": 0, "test": 2, "config": 3, "docs": 4, "lockfile": 5, "generated": 6}
INTERFACE_HINT = re.compile(r"(types?|interfaces?|schema|models?|proto|api|contract)\b", re.I)


@AGENT.tool
def diff_stats(diff: str) -> dict:
    """Measure a unified diff: size class, per-file churn, test coverage of the change, risk flags and review order.

    Call first on any review. Tells you whether the PR is reviewable in one sitting and which
    files to read first.

    Args:
        diff: The raw unified diff (output of `git diff` or a PR's .diff/.patch).
    """
    diff = require_text(diff, "diff", 2_000_000)
    files = parse_unified_diff(diff)
    if not files:
        raise ToolError("No file changes found — is this a unified diff (lines starting with ---/+++/@@)?")
    adds = sum(f["additions"] for f in files)
    dels = sum(f["deletions"] for f in files)
    changed = adds + dels
    size = next(label for cap, label in SIZE_CLASSES if changed < cap)
    kinds = Counter(f["kind"] for f in files)
    src_lines = sum(f["additions"] + f["deletions"] for f in files if f["kind"] in ("source", "migration"))
    test_lines = sum(f["additions"] + f["deletions"] for f in files if f["kind"] == "test")
    langs = Counter(f["language"] for f in files if f["kind"] == "source")
    flags = []
    if src_lines >= 20 and test_lines == 0:
        flags.append("source changed but no test files touched")
    if kinds.get("migration"):
        flags.append(f"{kinds['migration']} migration/SQL file(s) — verify reversibility and lock impact")
    sensitive = [f["path"] for f in files if SENSITIVE_PATH.search(f["path"])]
    if sensitive:
        flags.append("security-sensitive paths touched: " + ", ".join(sensitive[:5]))
    deleted_tests = [f["path"] for f in files if f["kind"] == "test" and f["status"] == "deleted"]
    if deleted_tests:
        flags.append("test files deleted: " + ", ".join(deleted_tests[:5]))
    weakened = [f["path"] for f in files if f["kind"] == "test" and f["deletions"] > f["additions"] + 5]
    if weakened:
        flags.append("tests shrank markedly in: " + ", ".join(weakened[:5]))
    big = [f["path"] for f in files if f["additions"] + f["deletions"] > 300 and f["kind"] not in ("lockfile", "generated")]
    if big:
        flags.append("very large files (>300 lines): " + ", ".join(big[:5]))
    if kinds.get("generated") or kinds.get("lockfile"):
        flags.append("generated/lock files present — skim only, don't review line by line")
    if len(files) > 25:
        flags.append(f"{len(files)} files touched — likely mixes several concerns")
    reviewable = changed - sum(f["additions"] + f["deletions"] for f in files if f["kind"] in ("lockfile", "generated"))
    est_minutes = max(2, round(reviewable / 400 * 60))
    ordered = sorted(
        files,
        key=lambda f: (ORDER_RANK.get(f["kind"], 3), 0 if INTERFACE_HINT.search(f["path"]) else 1, -(f["additions"] + f["deletions"])),
    )
    per_file = [
        {
            "path": f["path"], "status": f["status"], "kind": f["kind"], "language": f["language"],
            "additions": f["additions"], "deletions": f["deletions"], "hunks": f["hunks"],
        }
        for f in ordered
    ]
    if size in ("XL", "XXL"):
        verdict = f"{size}: {changed} changed lines is beyond a reliable single review (~400). Ask for a split; review only the riskiest files in depth."
    elif size == "L":
        verdict = f"L: {changed} changed lines — reviewable in one focused sitting (~{est_minutes} min). Read in the order given."
    else:
        verdict = f"{size}: {changed} changed lines — quick, thorough review is realistic (~{est_minutes} min)."
    return {
        "files": len(files),
        "additions": adds,
        "deletions": dels,
        "changed_lines": changed,
        "reviewable_lines": reviewable,
        "size_class": size,
        "estimated_review_minutes": est_minutes,
        "by_kind": dict(kinds),
        "languages": dict(langs),
        "source_lines_changed": src_lines,
        "test_lines_changed": test_lines,
        "test_to_source_ratio": round(test_lines / src_lines, 2) if src_lines else None,
        "source_without_tests": src_lines >= 20 and test_lines == 0,
        "risk_flags": flags,
        "review_order": per_file,
        "verdict": verdict,
    }


# ── python complexity ────────────────────────────────────────────────────────

_BRANCH_NODES = (ast.If, ast.For, ast.While, ast.AsyncFor, ast.ExceptHandler, ast.IfExp, ast.Assert, ast.With, ast.AsyncWith)
_NEST_NODES = (ast.If, ast.For, ast.While, ast.AsyncFor, ast.Try, ast.With, ast.AsyncWith, ast.FunctionDef, ast.AsyncFunctionDef)


def _cyclomatic(fn: ast.AST) -> int:
    n = 1
    for node in ast.walk(fn):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.ExceptHandler, ast.IfExp, ast.Assert)):
            n += 1
        elif isinstance(node, ast.BoolOp):
            n += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            n += 1 + len(node.ifs)
        elif isinstance(node, ast.match_case):
            n += 1
    return n


def _max_nesting(node: ast.AST, depth: int = 0) -> int:
    best = depth
    for child in ast.iter_child_nodes(node):
        d = depth + 1 if isinstance(child, _NEST_NODES) and not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else depth
        best = max(best, _max_nesting(child, d))
    return best


@AGENT.tool
def python_complexity(source: str, complexity_threshold: int = 10) -> dict:
    """Compute cyclomatic complexity, nesting, length and parameter counts for every Python function, plus smell flags.

    Call for each touched Python file with real logic. Uses `ast` only — never executes code.

    Args:
        source: Full Python source of the module (or the new version of the file).
        complexity_threshold: Cyclomatic complexity above which a function is flagged (McCabe's classic 10).
    """
    source = require_text(source, "source", 400_000)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ToolError(f"Not valid Python: {e.msg} at line {e.lineno}.") from None
    lines = source.splitlines()
    functions = []
    module_flags = []

    class_of: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_of[id(child)] = node.name

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = f"{class_of[id(node)]}.{node.name}" if id(node) in class_of else node.name
        end = getattr(node, "end_lineno", node.lineno)
        length = end - node.lineno + 1
        args = node.args
        params = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs if a.arg not in ("self", "cls")]
        if args.vararg:
            params.append("*" + args.vararg.arg)
        if args.kwarg:
            params.append("**" + args.kwarg.arg)
        cc = _cyclomatic(node)
        nesting = _max_nesting(node)
        returns = sum(isinstance(n, ast.Return) for n in ast.walk(node))
        flags = []
        if cc > complexity_threshold * 2:
            flags.append(f"complexity {cc} — blocking-level in new code; split into smaller functions")
        elif cc > complexity_threshold:
            flags.append(f"complexity {cc} > {complexity_threshold}; extract branches or use a dispatch table")
        if length > 50:
            flags.append(f"{length} lines long (>50); a reader can't hold it in one screen")
        if len(params) > 5:
            flags.append(f"{len(params)} parameters (>5); group into a dataclass/options object")
        if nesting > 4:
            flags.append(f"nesting depth {nesting} (>4); use guard clauses / early returns")
        if returns > 5:
            flags.append(f"{returns} return statements; consider a single exit or a lookup")
        for d in args.defaults + args.kw_defaults:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)) or (isinstance(d, ast.Call) and getattr(d.func, "id", "") in ("list", "dict", "set")):
                flags.append("mutable default argument — shared across calls; use None and create inside")
                break
        for sub in ast.walk(node):
            if isinstance(sub, ast.ExceptHandler):
                if sub.type is None:
                    flags.append(f"bare `except:` at line {sub.lineno} catches SystemExit/KeyboardInterrupt too")
                if len(sub.body) == 1 and isinstance(sub.body[0], ast.Pass):
                    flags.append(f"swallowed exception at line {sub.lineno} (`except ...: pass`)")
            if isinstance(sub, ast.Global):
                flags.append(f"`global` at line {sub.lineno}; hidden coupling")
        public = not node.name.startswith("_")
        if public and not ast.get_docstring(node) and length > 15:
            flags.append("public function >15 lines without a docstring")
        functions.append({
            "name": name, "line": node.lineno, "lines": length, "params": len(params), "complexity": cc,
            "max_nesting": nesting, "returns": returns, "is_async": isinstance(node, ast.AsyncFunctionDef), "flags": flags,
        })
    if not functions:
        module_flags.append("no functions found — module-level script; consider a main() guard")
    functions.sort(key=lambda f: (-f["complexity"], -f["lines"]))
    todo = sum(1 for l in lines if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", l))
    flagged = [f for f in functions if f["flags"]]
    total_cc = sum(f["complexity"] for f in functions)
    avg_cc = round(total_cc / len(functions), 1) if functions else 0
    worst = functions[0] if functions else None
    verdict = (
        f"{len(functions)} functions, avg complexity {avg_cc}, worst {worst['name']} at {worst['complexity']}. "
        f"{len(flagged)} need comments." if worst else "No functions to assess."
    )
    return {
        "functions": functions,
        "module": {
            "lines": len(lines), "functions": len(functions), "avg_complexity": avg_cc, "max_complexity": worst["complexity"] if worst else 0,
            "todo_markers": todo, "flags": module_flags,
        },
        "flagged": [{"name": f["name"], "line": f["line"], "flags": f["flags"]} for f in flagged],
        "verdict": verdict,
    }


# ── diff smells ──────────────────────────────────────────────────────────────

SMELLS: list[tuple[str, re.Pattern, str, str]] = [
    ("conflict marker", re.compile(r"^(<{7}|={7}|>{7})( |$)"), "blocker", "unresolved merge conflict marker"),
    ("debugger", re.compile(r"\b(pdb\.set_trace|breakpoint\(\)|debugger;|binding\.pry|byebug|ipdb)"), "blocker", "debugger left in code"),
    ("debug print", re.compile(r"^\s*(print\(|console\.(log|debug)\(|fmt\.Println\(|System\.out\.print|var_dump\(|dd\()"), "major", "debug output statement — remove or use the logger"),
    ("swallowed exception", re.compile(r"except(\s+\w+(\s+as\s+\w+)?)?\s*:\s*pass\b|catch\s*\([^)]*\)\s*\{\s*\}"), "major", "exception swallowed silently — log it or narrow it"),
    ("bare except", re.compile(r"^\s*except\s*:"), "major", "bare except catches SystemExit/KeyboardInterrupt"),
    ("hardcoded credential", re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*[\"'][^\"'$<{]{6,}[\"']"), "blocker", "credential literal in code — move to config/secret store and rotate"),
    ("sql built from string", re.compile(r"\.(execute|executemany|raw|query|exec)\s*\(\s*(f[\"']|[\"'][^\"']*[\"']\s*(%|\+)\s*\w|[\"'][^\"']*[\"']\.format\(|`[^`]*\$\{)"), "blocker", "SQL assembled from string formatting — injection (CWE-89); use bound parameters"),
    ("tls verification off", re.compile(r"\bverify\s*=\s*False\b|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true|check_hostname\s*=\s*False|(verify_mode|cert_reqs)\s*=\s*(ssl\.)?CERT_NONE"), "blocker", "TLS certificate verification disabled — man-in-the-middle can alter the response (CWE-295)"),
    ("focused test", re.compile(r"\b(it|describe|test)\.only\(|@pytest\.mark\.skip\b|\bxit\(|\bxdescribe\(|@Ignore\b|t\.Skip\("), "major", "skipped/focused test — CI will silently run less"),
    ("lint suppressed", re.compile(r"#\s*noqa|#\s*type:\s*ignore|eslint-disable|@ts-ignore|@ts-nocheck|#\s*nosec|//\s*nolint|@SuppressWarnings|rubocop:disable"), "minor", "lint/type suppression — needs a justification comment"),
    ("todo without ticket", re.compile(r"\b(TODO|FIXME|XXX|HACK)\b(?![^\n]*(#\d+|[A-Z]{2,}-\d+|https?://))"), "minor", "TODO/FIXME without a ticket reference"),
    ("sleep in test", re.compile(r"\b(time\.sleep|Thread\.sleep|setTimeout\(\s*resolve|sleep\s+\d)"), "minor", "sleep-based timing — flaky; wait on a condition instead"),
    ("commented-out code", re.compile(r"^\s*(#|//)\s*(if|for|while|return|import|from|def|class|const|let|var|function|\w+\s*=\s*\w|\w+\(.*\);?\s*$)"), "minor", "commented-out code — delete it; git remembers"),
    ("insecure url", re.compile(r"[\"']http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)"), "minor", "plain http:// URL"),
    ("wildcard import", re.compile(r"^\s*from\s+\S+\s+import\s+\*"), "minor", "wildcard import hides names"),
    ("long line", re.compile(r"^.{160,}$"), "nit", "line >160 chars"),
    ("trailing whitespace", re.compile(r"[ \t]+$"), "nit", "trailing whitespace"),
]
TEST_ONLY = {"sleep in test"}


@AGENT.tool
def scan_diff_smells(diff: str) -> dict:
    """Scan the added lines of a diff for leftovers and cheap-to-spot hazards: debug prints, debuggers, swallowed exceptions, TODOs without tickets, disabled lints, focused/skipped tests, conflict markers, leaked credentials (AWS/GitHub/Stripe/… detectors, value never echoed), SQL built by string formatting, TLS verification turned off.

    Each hit is a ready-made review comment with file and line number in the new file. A clean
    scan is not a security review — still read every query, auth check and trust boundary.

    Args:
        diff: The raw unified diff.
    """
    diff = require_text(diff, "diff", 2_000_000)
    files = parse_unified_diff(diff)
    if not files:
        raise ToolError("No file changes found — is this a unified diff?")
    findings = []
    for f in files:
        if f["kind"] in ("lockfile", "generated"):
            continue
        added = dict(f["added_lines"])
        for ln, text_line in f["added_lines"]:
            nxt = added.get(ln + 1, "")
            secrets = [] if f["kind"] in ("test", "docs") else [s for _, conf, s in find_secrets_in_line(text_line) if conf != "low"]
            if secrets:
                # provider-specific detectors (AWS, GitHub, Stripe, …) — the value is never echoed back
                findings.append({
                    "file": f["path"], "line": ln, "severity": "blocker", "smell": "hardcoded credential",
                    "message": "credential literal in code — rotate it now, move it to the secret store, purge it from history",
                    "code": redact_line(text_line.strip(), secrets)[:160],
                })
                continue
            if re.match(r"^\s*except\b[^:]*:\s*$", text_line) and re.match(r"^\s*pass\s*$", nxt):
                findings.append({
                    "file": f["path"], "line": ln, "severity": "major", "smell": "swallowed exception",
                    "message": "exception swallowed silently — log it or narrow it", "code": text_line.strip()[:160],
                })
                continue
            for label, rx, sev, msg in SMELLS:
                if label in TEST_ONLY and f["kind"] != "test":
                    continue
                if label == "debug print" and (f["kind"] != "source" or f["language"] in ("Shell", "Other", "Markdown")):
                    continue
                if label == "hardcoded credential" and f["kind"] in ("test", "docs"):
                    continue
                if label in ("sql built from string", "tls verification off") and f["kind"] == "docs":
                    continue
                m = rx.search(text_line)
                if m:
                    code = text_line.strip()
                    if label == "hardcoded credential":
                        code = re.sub(r"([:=]\s*[\"'])[^\"']+([\"'])", lambda q: q.group(1) + "…(redacted)" + q.group(2), code)
                    findings.append({
                        "file": f["path"], "line": ln, "severity": sev, "smell": label, "message": msg,
                        "code": code[:160],
                    })
                    break
    order = {"blocker": 0, "major": 1, "minor": 2, "nit": 3}
    findings.sort(key=lambda x: (order[x["severity"]], x["file"], x["line"]))
    by_sev = Counter(x["severity"] for x in findings)
    by_smell = Counter(x["smell"] for x in findings)
    if findings:
        verdict = f"{len(findings)} leftover(s): " + ", ".join(f"{n} {k}" for k, n in by_smell.most_common(4)) + "."
    else:
        verdict = "No debug leftovers, suppressions or conflict markers in the added lines."
    return {
        "findings": findings[:200],
        "counts_by_severity": dict(by_sev),
        "counts_by_smell": dict(by_smell),
        "added_lines_scanned": sum(len(f["added_lines"]) for f in files),
        "verdict": verdict,
    }


# ── review scoring ───────────────────────────────────────────────────────────

SEVERITIES = ["blocker", "major", "minor", "nit", "praise", "question"]
CATEGORIES_OK = {"correctness", "design", "tests", "security", "performance", "readability", "docs", "other"}
LABEL = {"blocker": "issue (blocking)", "major": "issue", "minor": "suggestion", "nit": "nit", "praise": "praise", "question": "question"}


@AGENT.tool
def score_review(findings: list[dict]) -> dict:
    """Turn raw findings into an ordered, Conventional-Comments-formatted review with a rule-based verdict.

    Verdict rule: any blocker or ≥3 majors → Request changes; 1-2 majors → Comment; else Approve.
    Also flags unactionable findings (no suggestion on a blocker/major) and nit-heavy reviews.

    Args:
        findings: List of {"severity": blocker|major|minor|nit|praise|question, "category": correctness|design|tests|security|performance|readability|docs|other, "file": str, "line": int, "message": str, "suggestion": str}.
    """
    if not isinstance(findings, list):
        raise ToolError("findings must be a list of objects.")
    if len(findings) > 300:
        raise ToolError("Too many findings (max 300) — you are reviewing something that should be split.")
    cleaned, problems = [], []
    for i, raw in enumerate(findings, 1):
        if not isinstance(raw, dict):
            raise ToolError(f"finding #{i} is not an object.")
        sev = str(raw.get("severity", "")).lower().strip()
        if sev not in SEVERITIES:
            raise ToolError(f"finding #{i}: severity must be one of {SEVERITIES}, got {sev!r}.")
        msg = str(raw.get("message", "")).strip()
        if not msg:
            raise ToolError(f"finding #{i} has no message.")
        cat = str(raw.get("category", "other")).lower().strip() or "other"
        if cat not in CATEGORIES_OK:
            cat = "other"
        sugg = str(raw.get("suggestion", "") or "").strip()
        if sev in ("blocker", "major") and not sugg:
            problems.append(f"#{i} ({sev}) has no suggestion — the author will ask 'so what do I do?'")
        if sev in ("blocker", "major") and not re.search(r"\b(when|if|because|will|would|can|leads|causes|breaks|fails|returns|raises)\b", msg, re.I):
            problems.append(f"#{i} ({sev}) doesn't say what goes wrong or when — add the failure scenario")
        loc = f"{raw.get('file', '?')}:{raw.get('line')}" if raw.get("line") else str(raw.get("file", "general"))
        formatted = f"**{LABEL[sev]}:** {msg}" + (f"\n  → {sugg}" if sugg else "")
        cleaned.append({"n": i, "severity": sev, "category": cat, "location": loc, "message": msg, "suggestion": sugg, "formatted": formatted})
    counts = Counter(c["severity"] for c in cleaned)
    order = {s: k for k, s in enumerate(SEVERITIES)}
    cleaned.sort(key=lambda c: (order[c["severity"]], c["location"]))
    if counts["blocker"] or counts["major"] >= 3:
        verdict = "Request changes"
        why = f"{counts['blocker']} blocker(s), {counts['major']} major(s)"
    elif counts["major"]:
        verdict = "Comment"
        why = f"{counts['major']} major issue(s) to fix before merge; no blockers"
    else:
        verdict = "Approve"
        why = "only minor/nit findings" if counts["minor"] or counts["nit"] else "no findings"
    substantive = counts["blocker"] + counts["major"] + counts["minor"]
    health = []
    if counts["nit"] >= 5 and counts["nit"] > 0.6 * max(1, substantive + counts["nit"]):
        health.append(f"{counts['nit']} nits dominate — collapse into one 'run the formatter/linter' comment")
    if substantive == 0 and counts["question"] >= 3:
        health.append("mostly questions; state what would change the verdict or approve")
    if not counts["praise"] and substantive:
        health.append("no praise — if anything was done well, name it specifically")
    by_cat = Counter(c["category"] for c in cleaned if c["severity"] in ("blocker", "major", "minor"))
    grouped = defaultdict(list)
    for c in cleaned:
        grouped[c["severity"]].append(f"`{c['location']}` — {c['formatted']}")
    flip = (
        "Fix all blockers and majors with the suggested changes, then re-request review." if verdict == "Request changes"
        else "Address the major issue(s); no re-review needed if the diff matches the suggestions." if verdict == "Comment"
        else "Nothing — ship it once CI is green."
    )
    return {
        "verdict": verdict,
        "verdict_reason": why,
        "counts": dict(counts),
        "categories": dict(by_cat),
        "findings": cleaned,
        "sections": {k: grouped.get(k, []) for k in SEVERITIES},
        "unactionable": problems,
        "review_health": health,
        "what_flips_to_approve": flip,
        "summary": f"{verdict} — {why}. {len(cleaned)} comments ({', '.join(f'{n} {k}' for k, n in counts.most_common())}).",
    }
