"""Test Writer — tests that catch the bugs that matter, written from the code's actual shape.

Tools read Python with `ast` (never executed): extract signatures and raise
paths, build an edge-case matrix per parameter type, find untested functions by
cross-referencing a test module, and generate a correct parametrize block.
"""

from __future__ import annotations

import ast
import re
from collections import Counter

from ...core import Agent, ToolError
from ._common import bound_list, require_text

AGENT = Agent(
    slug="test-writer",
    name="Test Writer",
    category="engineering",
    tagline="Turn a function or module into a test suite that covers the branches, the edges and the failure paths — not just the happy path.",
    description=(
        "Writes tests the way a senior engineer does: reads the code's real signatures and raise paths, "
        "derives an edge-case matrix per parameter type (empty, boundary, unicode, None, huge, "
        "leap-day…), finds which functions and error paths the existing tests never touch, and emits "
        "parametrized pytest that is deterministic, readable and fails for the right reasons. Works "
        "for pytest first, with guidance for Jest, Go test and JUnit."
    ),
    triggers=[
        "write tests for this function / module / class",
        "what test cases am I missing",
        "generate edge cases for this input",
        "improve test coverage for …",
        "write a parametrized pytest for …",
        "review my tests / are these tests good",
    ],
    examples=[
        "Write pytest tests for this parse_duration function — it takes strings like '1h30m'.",
        "Here's my module and its test file. What's untested?",
        "Give me the edge cases for an API that takes (email: str, age: int, tags: list[str]).",
    ],
    connectors=["GitHub", "GitLab", "Linear", "Jira"],
    playbook="""
    ## Standard
    You are a staff engineer who treats tests as the executable spec. Excellent means: every
    branch and every documented failure has a test with a name that reads as a sentence; the
    suite runs in seconds with no network, clock or randomness; and a future refactor that
    breaks behaviour fails exactly one obviously-named test. The one metric: **bugs caught
    before merge per test written** — not line coverage.

    ## Intake
    You need the code under test (or its signature and docstring at minimum), the framework
    (assume pytest for Python, Jest for JS/TS, `testing` for Go, JUnit 5 for Java — say so),
    and any existing tests. Ask at most 3 questions and only when behaviour is genuinely
    unspecified (e.g. "what should happen on a negative amount?"). Otherwise infer from the
    code, state the assumption in a comment above the test, and continue.

    ## Procedure
    1. **Read the shape.** For Python, call `test_writer__extract_signatures` with the source.
       It returns every function/method with parameters, defaults, return type, the exceptions
       it raises, branch count, side-effect calls (I/O, time, randomness, network) and suggested
       test names. Branch count + raise count is your minimum test count per function.
    2. **Find the gaps.** If tests exist, call `test_writer__coverage_gaps` with the source and
       the test module. Prioritise: (a) public functions with zero tests, (b) raise paths never
       asserted with `pytest.raises`, (c) tests without assertions. Don't rewrite tests that
       already cover behaviour; add the missing ones.
    3. **Build the case matrix.** For each function's parameters, call
       `test_writer__edge_case_matrix` with name + type (+ min/max/choices/nullable if known).
       Pick from the returned tiers: every `must` case, the `should` cases for boundary
       parameters, `could` only for high-risk code (parsers, money, dates, auth).
    4. **Design each test** against this checklist:
       - One behaviour per test; name `test_<unit>_<scenario>_<expected>` (e.g.
         `test_parse_duration_rejects_negative`).
       - Arrange / Act / Assert with blank lines between; no logic (loops/ifs) inside a test.
       - Assert on values and messages, not on types or "no exception". For errors:
         `with pytest.raises(ValueError, match="negative")`.
       - Isolate side effects: freeze time, seed randomness, stub network/filesystem at the
         boundary (monkeypatch/fixtures), never sleep.
       - Table-driven cases go in `@pytest.mark.parametrize` with readable ids — generate the
         block with `test_writer__parametrize_block` so quoting, ids and duplicates are right.
    5. **Order the file**: fixtures → happy path → edge cases (parametrized) → error paths →
       property/round-trip tests if applicable (`decode(encode(x)) == x`).
    6. **Self-check** before delivering: would each test fail if the feature were deleted?
       Does any test depend on another's order or on a real clock/network? Are the names
       sentences? Is there a test for each `raise` in the source?

    ## Frameworks
    - **Test pyramid**: many unit tests (ms, no I/O), some integration (real DB in a container),
      few end-to-end. Unit tests here unless asked otherwise.
    - **Boundary value analysis**: for a range [min, max] test min-1, min, min+1, max-1, max,
      max+1. **Equivalence partitioning**: one representative per class of input.
    - **Zero-One-Many**: collections with 0, 1 and many items; strings empty/one char/long.
    - **Failure paths first**: a `raise` without a test is a documented behaviour nobody checks.
    - **Property-based** (Hypothesis / fast-check) for parsers, serialisers, maths: state the
      invariant (round-trip, idempotence, monotonicity) instead of picking examples.
    - **Mutation mindset**: for each test ask "which single-line change would this catch?"
    - **Determinism rules**: `freezegun`/`time_machine` for clocks, `random.seed`, tmp_path for
      files, `responses`/`respx` for HTTP, no `sleep`, no ordering dependence.

    ## Output format
    ```
    ## Test plan for <unit>
    | # | Case | Input | Expected | Tier |
    |---|---|---|---|---|

    ## tests/test_<module>.py
    ```python
    <complete, runnable test module: imports, fixtures, parametrized happy/edge cases, error paths>
    ```

    **Determinism:** <what is frozen/stubbed and how>
    **Not covered (and why):** <e.g. real DB behaviour — integration test suggested>
    **Assumptions:** <behaviour inferred from code, to confirm>
    ```

    ## Anti-patterns
    - Testing the implementation (mocking internals, asserting call counts on private helpers).
      Test the observable behaviour through the public surface.
    - `assert result` / `assert result is not None` — asserts nothing useful.
    - One giant test that walks through five scenarios; when it fails nobody knows why.
    - Snapshot tests of large outputs without a reason — they lock in bugs.
    - Sleeping to wait for async work; poll a condition or await the future.
    - Parametrize ids like `case0..case9`. The id should say what the case is.
    - 100% coverage as a goal. Coverage says which lines ran, not whether behaviour was checked.
    """,
)

SIDE_EFFECT_CALLS = {
    "open": "filesystem", "print": "stdout", "input": "stdin",
    "requests": "network", "httpx": "network", "urllib": "network", "aiohttp": "network", "socket": "network", "boto3": "network (AWS)",
    "subprocess": "process", "os.system": "process", "os.popen": "process",
    "time.sleep": "clock/sleep", "time.time": "clock", "datetime.now": "clock", "datetime.utcnow": "clock", "date.today": "clock", "time.monotonic": "clock",
    "random": "randomness", "uuid": "randomness", "secrets": "randomness",
    "os.environ": "environment", "os.getenv": "environment",
    "logging": "logging", "redis": "network (redis)", "sqlalchemy": "database", "psycopg2": "database", "sqlite3": "database", "pymongo": "database",
    "smtplib": "email", "threading": "concurrency", "asyncio.sleep": "clock/sleep", "multiprocessing": "concurrency",
}


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    return ""


def _ann(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _branches(fn: ast.AST) -> int:
    n = 0
    for node in ast.walk(fn):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.AsyncFor, ast.ExceptHandler, ast.IfExp, ast.match_case)):
            n += 1
        elif isinstance(node, ast.BoolOp):
            n += len(node.values) - 1
    return n


@AGENT.tool
def extract_signatures(source: str, module_name: str = "") -> dict:
    """Extract every function/method from Python source: parameters with types and defaults, return type, exceptions raised, branch count, side-effect calls to stub, and suggested test names.

    Call first. Uses `ast` only — the code is never executed.

    Args:
        source: The Python source to test.
        module_name: Optional module name (e.g. "billing.invoices") for the suggested test file/import.
    """
    source = require_text(source, "source", 400_000)
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ToolError(f"Not valid Python: {e.msg} at line {e.lineno}.") from None
    owner: dict[int, str] = {}
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [c.name for c in node.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes.append({"name": node.name, "line": node.lineno, "methods": methods, "bases": [_ann(b) for b in node.bases]})
            for c in node.body:
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner[id(c)] = node.name
    functions = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        cls = owner.get(id(node))
        qual = f"{cls}.{node.name}" if cls else node.name
        a = node.args
        params = []
        pos = a.posonlyargs + a.args
        defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
        for arg, d in zip(pos, defaults):
            if arg.arg in ("self", "cls") and cls:
                continue
            params.append({"name": arg.arg, "type": _ann(arg.annotation), "default": _ann(d) if d is not None else None, "kind": "positional"})
        for arg, d in zip(a.kwonlyargs, a.kw_defaults):
            params.append({"name": arg.arg, "type": _ann(arg.annotation), "default": _ann(d) if d is not None else None, "kind": "keyword-only"})
        if a.vararg:
            params.append({"name": "*" + a.vararg.arg, "type": _ann(a.vararg.annotation), "default": None, "kind": "varargs"})
        if a.kwarg:
            params.append({"name": "**" + a.kwarg.arg, "type": _ann(a.kwarg.annotation), "default": None, "kind": "kwargs"})
        raises, effects, is_gen = [], {}, False
        for sub in ast.walk(node):
            if isinstance(sub, ast.Raise) and sub.exc is not None:
                name = _dotted(sub.exc)
                if name and name not in raises:
                    raises.append(name)
            if isinstance(sub, (ast.Yield, ast.YieldFrom)):
                is_gen = True
            if isinstance(sub, ast.Call):
                name = _dotted(sub.func)
                for key, kind in SIDE_EFFECT_CALLS.items():
                    if name == key or name.startswith(key + ".") or (("." in key) and name.endswith(key)):
                        effects[name] = kind
        decorators = [_dotted(d) or _ann(d) for d in node.decorator_list]
        branches = _branches(node)
        doc = ast.get_docstring(node)
        base = node.name.strip("_") or "call"
        suggested = [f"test_{base}_happy_path"]
        if branches:
            suggested.append(f"test_{base}_<each_branch>  # {branches} branch(es)")
        for r in raises:
            suggested.append(f"test_{base}_raises_{re.sub(r'(?<!^)(?=[A-Z])', '_', r.rsplit('.', 1)[-1]).lower()}")
        for p in params:
            if p["default"] is not None:
                suggested.append(f"test_{base}_default_{p['name'].strip('*')}")
        if is_gen:
            suggested.append(f"test_{base}_is_lazy_and_yields_in_order")
        functions.append({
            "name": qual, "line": node.lineno, "is_async": isinstance(node, ast.AsyncFunctionDef), "is_generator": is_gen,
            "is_public": not node.name.startswith("_") or node.name.startswith("__"), "decorators": decorators,
            "params": params, "returns": _ann(node.returns), "raises": raises, "branches": branches,
            "min_tests": 1 + branches + len(raises), "side_effects": effects, "docstring": (doc or "").split("\n")[0][:160],
            "suggested_tests": suggested,
        })
    if not functions:
        raise ToolError("No functions or methods found in the source.")
    functions.sort(key=lambda f: f["line"])
    mod = module_name or "module"
    public = [f for f in functions if f["is_public"]]
    all_effects = Counter(kind for f in functions for kind in f["side_effects"].values())
    return {
        "module": mod,
        "suggested_test_file": f"tests/test_{mod.rsplit('.', 1)[-1]}.py",
        "import_line": f"from {mod} import " + ", ".join(sorted({f["name"].split(".")[0] for f in public})) if module_name else None,
        "classes": classes,
        "functions": functions,
        "public_functions": len(public),
        "total_min_tests": sum(f["min_tests"] for f in public),
        "side_effects_to_stub": dict(all_effects),
        "summary": f"{len(functions)} function(s) ({len(public)} public); at least {sum(f['min_tests'] for f in public)} tests to cover branches and raise paths"
                   + (f"; stub: {', '.join(all_effects)}" if all_effects else "; no side effects detected") + ".",
    }


# ── edge cases ───────────────────────────────────────────────────────────────

EDGE: dict[str, list[tuple[str, str, str]]] = {  # type -> (tier, value repr, why)
    "int": [("must", "0", "zero — off-by-one and division"), ("must", "1", "smallest positive"), ("must", "-1", "negative"),
            ("should", "2**31 - 1", "32-bit max"), ("should", "2**63", "beyond 64-bit"), ("should", "-2**31", "32-bit min"), ("could", "True", "bool is an int in Python")],
    "float": [("must", "0.0", "zero"), ("must", "-0.0", "negative zero"), ("must", "0.1 + 0.2", "precision (≠ 0.3)"), ("should", "float('nan')", "NaN ≠ NaN"),
              ("should", "float('inf')", "infinity"), ("should", "1e-300", "denormal-ish"), ("should", "1e308", "huge"), ("could", "-1e-9", "tiny negative")],
    "str": [("must", "''", "empty"), ("must", "' '", "whitespace only"), ("must", "'a'", "single char"), ("must", "'x' * 10_000", "very long"),
            ("must", "'  padded  '", "leading/trailing whitespace"), ("should", "'Ünïcödé ✓'", "non-ASCII"), ("should", "'😀'", "emoji (surrogate pairs, width)"),
            ("should", "'line1\\nline2'", "embedded newline"), ("should", "'\\x00'", "null byte"), ("should", "'ABC' vs 'abc'", "case sensitivity"),
            ("could", "'<script>alert(1)</script>'", "HTML injection"), ("could", "\"'; DROP TABLE users; --\"", "SQL injection"), ("could", "'مرحبا'", "right-to-left text"),
            ("could", "'e\\u0301' vs 'é'", "unicode normalisation (NFC/NFD)")],
    "bool": [("must", "True", ""), ("must", "False", ""), ("should", "'false' (string)", "string truthiness trap"), ("could", "None", "tri-state")],
    "list": [("must", "[]", "empty"), ("must", "[x]", "single item"), ("must", "[x, x]", "duplicates"), ("should", "[x] * 10_000", "large"),
             ("should", "[None]", "None element"), ("should", "[x, y] in reverse order", "ordering assumptions"), ("could", "nested lists", "depth")],
    "dict": [("must", "{}", "empty"), ("must", "missing expected key", "KeyError path"), ("must", "extra unexpected key", "strictness"),
             ("should", "{'k': None}", "None value"), ("should", "nested dict", "depth"), ("could", "non-string keys", "serialisation")],
    "date": [("must", "today", "baseline"), ("must", "2024-02-29", "leap day"), ("must", "2026-12-31 → 2027-01-01", "year boundary"),
             ("should", "1970-01-01", "epoch"), ("should", "2038-01-19", "32-bit time_t overflow"), ("should", "naive vs aware datetime", "tz mixing raises"),
             ("should", "DST transition (e.g. 2026-03-29 02:30 Europe/London)", "non-existent local time"), ("could", "0001-01-01 / 9999-12-31", "min/max")],
    "email": [("must", "'a@b.co'", "minimal valid"), ("must", "''", "empty"), ("must", "'no-at-sign'", "invalid"), ("should", "'A@B.CO'", "case"),
              ("should", "'a+tag@b.co'", "plus addressing"), ("should", "'a@[127.0.0.1]'", "IP literal"), ("could", "'\"quoted local\"@b.co'", "RFC 5321 oddities")],
    "url": [("must", "'https://example.com'", "minimal"), ("must", "''", "empty"), ("must", "'not a url'", "invalid"), ("should", "'HTTP://EXAMPLE.COM/'", "case + trailing slash"),
            ("should", "'https://example.com:8443/p?q=1#f'", "port, query, fragment"), ("should", "'javascript:alert(1)'", "dangerous scheme"), ("could", "'https://exämple.com'", "IDN")],
    "path": [("must", "'file.txt'", "relative"), ("must", "'/abs/path'", "absolute"), ("must", "'../../etc/passwd'", "traversal"), ("should", "'with space.txt'", "spaces"),
             ("should", "'' ", "empty"), ("could", "'C:\\\\Windows\\\\x'", "Windows separators"), ("could", "very long path (> 255)", "OS limits")],
    "id": [("must", "valid existing id", ""), ("must", "non-existent id", "404 path"), ("must", "''", "empty"), ("should", "id of another tenant/user", "authorisation"),
           ("should", "malformed (not a UUID/int)", "validation"), ("could", "'0' / negative", "sentinel values")],
    "money": [("must", "0", "zero"), ("must", "0.01 / 1 minor unit", "smallest"), ("must", "-1", "negative"), ("should", "999_999_999.99", "large"),
              ("should", "0.005", "rounding half-even vs half-up"), ("should", "'10.00' (string)", "type confusion"), ("could", "different currency", "mixing currencies")],
    "enum": [("must", "each valid value", "exhaustive"), ("must", "invalid value", "rejection"), ("should", "wrong case", "case sensitivity"), ("could", "None", "unset")],
}
ALIASES = {"integer": "int", "number": "float", "double": "float", "decimal": "money", "string": "str", "text": "str", "boolean": "bool", "array": "list", "sequence": "list",
           "tuple": "list", "set": "list", "object": "dict", "mapping": "dict", "map": "dict", "datetime": "date", "timestamp": "date", "time": "date", "uri": "url",
           "filepath": "path", "file": "path", "uuid": "id", "identifier": "id", "amount": "money", "price": "money", "currency": "money", "choice": "enum", "literal": "enum"}


@AGENT.tool
def edge_case_matrix(params: list[dict]) -> dict:
    """Build the edge-case matrix for a set of parameters by type (int, float, str, bool, list, dict, date, email, url, path, id, money, enum), with boundary values from min/max, tiered must/should/could, and pairwise vs full-combination counts.

    Call per function after extract_signatures. Feed the `must` tier straight into parametrize.

    Args:
        params: List of {"name": str, "type": str, "min": number?, "max": number?, "nullable": bool?, "choices": list?, "max_length": int?}.
    """
    params = bound_list(params, "params", 40)
    matrix, unknown = [], []
    for i, p in enumerate(params, 1):
        if not isinstance(p, dict) or not p.get("name"):
            raise ToolError(f"param #{i} needs a name.")
        raw_type = str(p.get("type", "str")).lower().strip()
        base = re.sub(r"\[.*\]|optional|\||none|\s", "", raw_type) or "str"
        base = ALIASES.get(base, base)
        if base not in EDGE:
            for key in EDGE:
                if key in raw_type:
                    base = key
                    break
            else:
                unknown.append(f"{p['name']}: {raw_type}")
                base = "str"
        cases = [{"tier": t, "value": v, "why": w} for t, v, w in EDGE[base]]
        lo, hi = p.get("min"), p.get("max")
        if lo is not None or hi is not None:
            for bound, label in ((lo, "min"), (hi, "max")):
                if bound is None:
                    continue
                try:
                    b = float(bound)
                except (TypeError, ValueError):
                    raise ToolError(f"{p['name']}.{label} must be a number.") from None
                step = 1 if base == "int" or b == int(b) and base != "float" else 0.01
                fmt = (lambda x: str(int(x))) if step == 1 else (lambda x: f"{x:.2f}")
                cases = [c for c in cases if c["why"] not in ("32-bit max", "32-bit min", "beyond 64-bit")]
                cases.insert(0, {"tier": "must", "value": fmt(b), "why": f"{label} boundary (inclusive?)"})
                cases.insert(1, {"tier": "must", "value": fmt(b - step if label == "min" else b + step), "why": f"just outside {label} — must reject"})
                cases.insert(2, {"tier": "should", "value": fmt(b + step if label == "min" else b - step), "why": f"just inside {label}"})
        if p.get("max_length"):
            n = int(p["max_length"])
            cases.insert(0, {"tier": "must", "value": f"'x' * {n}", "why": "exactly max_length"})
            cases.insert(1, {"tier": "must", "value": f"'x' * {n + 1}", "why": "one over max_length — must reject"})
        if p.get("choices"):
            ch = list(p["choices"])[:20]
            cases.insert(0, {"tier": "must", "value": f"each of {ch}", "why": "every allowed value"})
            cases.insert(1, {"tier": "must", "value": "value not in choices", "why": "rejection"})
        if p.get("nullable"):
            cases.insert(0, {"tier": "must", "value": "None", "why": "nullable — explicit None path"})
        else:
            cases.append({"tier": "should", "value": "None", "why": "not nullable — must reject, not crash"})
        seen = set()
        deduped = []
        for c in cases:
            if c["value"] not in seen:
                seen.add(c["value"])
                deduped.append(c)
        matrix.append({"name": p["name"], "type": base, "cases": deduped, "must": sum(c["tier"] == "must" for c in deduped)})
    must_counts = [m["must"] for m in matrix]
    full = 1
    for n in must_counts:
        full *= max(1, n)
    pairwise = max(must_counts) * (sorted(must_counts)[-2] if len(must_counts) > 1 else 1)
    single = sum(must_counts)
    return {
        "matrix": matrix,
        "unrecognised_types": unknown,
        "counts": {"must_cases_total": single, "one_at_a_time_tests": single, "pairwise_estimate": pairwise, "full_cartesian": full},
        "recommendation": (
            f"Test each parameter's must-cases one at a time with the others at a valid default ({single} tests); "
            + (f"full combination would be {full:,} — use pairwise (~{pairwise}) only for parameters that interact." if full > 50 else f"the full combination is only {full}, so cover it if parameters interact.")
        ),
    }


# ── coverage gaps ────────────────────────────────────────────────────────────


def _test_functions(tree: ast.Module) -> list[dict]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            names: set[str] = set()
            has_assert = False
            uses_raises = False
            raised_types: set[str] = set()
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    names.add(sub.attr)
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    names.add(sub.value)
                if isinstance(sub, ast.Assert):
                    has_assert = True
                if isinstance(sub, ast.Call):
                    fn = _dotted(sub.func)
                    if fn.endswith("raises") or fn.startswith("assert") or fn.endswith(("assert_called", "assert_called_once", "assert_called_with", "assertEqual", "assertTrue", "assertRaises")):
                        has_assert = True
                        if fn.endswith("raises") or fn.endswith("assertRaises"):
                            uses_raises = True
                            if sub.args:
                                raised_types.add(_dotted(sub.args[0]).rsplit(".", 1)[-1])
            params = any(_dotted(d).endswith("parametrize") for d in node.decorator_list)
            out.append({"name": node.name, "line": node.lineno, "names": names, "has_assert": has_assert, "uses_raises": uses_raises, "raised_types": raised_types, "parametrized": params})
    return out


@AGENT.tool
def coverage_gaps(source: str, tests: str) -> dict:
    """Cross-reference a Python module with its test module to list untested functions, raise paths never asserted, tests without assertions, and a per-function test count versus its branch count.

    Call when tests already exist, before writing more. Static analysis only — no execution.

    Args:
        source: The module under test (Python source).
        tests: The test module (Python source, pytest or unittest style).
    """
    source = require_text(source, "source", 400_000)
    tests = require_text(tests, "tests", 400_000)
    try:
        src_tree = ast.parse(source)
    except SyntaxError as e:
        raise ToolError(f"source is not valid Python: {e.msg} at line {e.lineno}.") from None
    try:
        test_tree = ast.parse(tests)
    except SyntaxError as e:
        raise ToolError(f"tests is not valid Python: {e.msg} at line {e.lineno}.") from None
    tfuncs = _test_functions(test_tree)
    if not tfuncs:
        raise ToolError("No test functions (def test_*) found in the test module.")
    owner: dict[int, str] = {}
    for node in ast.walk(src_tree):
        if isinstance(node, ast.ClassDef):
            for c in node.body:
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner[id(c)] = node.name
    rows = []
    for node in ast.walk(src_tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_") and not node.name.startswith("__"):
            continue
        cls = owner.get(id(node))
        qual = f"{cls}.{node.name}" if cls else node.name
        raises = sorted({_dotted(s.exc).rsplit(".", 1)[-1] for s in ast.walk(node) if isinstance(s, ast.Raise) and s.exc is not None and _dotted(s.exc)})
        key = cls if node.name == "__init__" and cls else node.name
        covering = [t for t in tfuncs if key in t["names"] or (cls and cls in t["names"] and node.name in t["names"])]
        branches = _branches(node)
        tested_raises = sorted({r for t in covering if t["uses_raises"] for r in t["raised_types"]})
        untested_raises = [r for r in raises if r not in tested_raises and not (tested_raises == [] and any(t["uses_raises"] for t in covering) and len(raises) == 1)]
        need = 1 + branches + len(raises)
        have = sum(3 if t["parametrized"] else 1 for t in covering)
        rows.append({
            "function": qual, "line": node.lineno, "branches": branches, "raises": raises, "tests": [t["name"] for t in covering],
            "test_count": len(covering), "estimated_cases": have, "min_cases_needed": need, "gap": max(0, need - have),
            "untested_raises": untested_raises,
        })
    untested = [r["function"] for r in rows if r["test_count"] == 0]
    no_assert = [t["name"] for t in tfuncs if not t["has_assert"]]
    rows.sort(key=lambda r: (-int(r["test_count"] == 0), -r["gap"], r["line"]))
    total_gap = sum(r["gap"] for r in rows)
    priorities = []
    for r in rows:
        if r["test_count"] == 0:
            priorities.append(f"{r['function']}: no tests at all ({r['min_cases_needed']} cases needed)")
    for r in rows:
        for x in r["untested_raises"]:
            priorities.append(f"{r['function']}: raise {x} never asserted with pytest.raises")
    for name in no_assert:
        priorities.append(f"{name}: no assertion — passes even if the code is deleted")
    return {
        "source_functions": len(rows),
        "test_functions": len(tfuncs),
        "untested_functions": untested,
        "tests_without_assertions": no_assert,
        "rows": rows,
        "priorities": priorities[:40],
        "estimated_missing_cases": total_gap,
        "verdict": (f"{len(untested)}/{len(rows)} public functions untested; ~{total_gap} cases missing; "
                    f"{sum(len(r['untested_raises']) for r in rows)} raise path(s) unasserted; {len(no_assert)} test(s) without assertions."),
    }


# ── parametrize ──────────────────────────────────────────────────────────────


def _pyrepr(v) -> str:
    if isinstance(v, str) and re.fullmatch(r"(raw:).*", v):
        return v[4:]
    return repr(v)


def _slug_id(v) -> str:
    s = str(v) if not isinstance(v, str) else v
    s = re.sub(r"[^A-Za-z0-9_.\-]+", "_", s).strip("_")
    return (s or "empty")[:40]


@AGENT.tool
def parametrize_block(function_name: str, arg_names: list[str], cases: list[dict], expected_key: str = "expected", raises_key: str = "raises") -> dict:
    """Generate a correct @pytest.mark.parametrize block plus test body from a table of cases: proper quoting, unique readable ids, duplicate-input detection, and separate handling for cases that expect an exception.

    Call once the case table is decided. Use "raw:" prefix in a value to insert Python code verbatim (e.g. "raw:float('nan')").

    Args:
        function_name: The function under test, e.g. "parse_duration".
        arg_names: The argument names in order, e.g. ["text"].
        cases: Each {"<arg>": value, ..., "expected": value} or {"<arg>": value, "raises": "ValueError", "match": "negative"}; optional "id".
        expected_key: Key holding the expected return value (default "expected").
        raises_key: Key naming the expected exception class (default "raises").
    """
    function_name = require_text(function_name, "function_name", 200).strip()
    if not re.fullmatch(r"[A-Za-z_][\w.]*", function_name):
        raise ToolError("function_name must be a Python identifier (dots allowed).")
    arg_names = bound_list(arg_names, "arg_names", 20)
    for a in arg_names:
        if not isinstance(a, str) or not re.fullmatch(r"[A-Za-z_]\w*", a):
            raise ToolError(f"bad argument name {a!r}.")
    cases = bound_list(cases, "cases", 500)
    ok_rows, err_rows, ids_seen, dupes = [], [], Counter(), []
    inputs_seen: dict[str, str] = {}
    for i, c in enumerate(cases, 1):
        if not isinstance(c, dict):
            raise ToolError(f"case #{i} must be an object.")
        missing = [a for a in arg_names if a not in c]
        if missing:
            raise ToolError(f"case #{i} is missing argument(s): {', '.join(missing)}.")
        args = [_pyrepr(c[a]) for a in arg_names]
        sig = ", ".join(args)
        cid = c.get("id") or "-".join(_slug_id(c[a]) for a in arg_names)
        if raises_key in c:
            cid = c.get("id") or f"{cid}-raises-{_slug_id(c[raises_key])}"
        ids_seen[cid] += 1
        if ids_seen[cid] > 1:
            cid = f"{cid}-{ids_seen[cid]}"
        if sig in inputs_seen:
            dupes.append(f"case #{i} repeats the inputs of '{inputs_seen[sig]}'")
        else:
            inputs_seen[sig] = cid
        if raises_key in c:
            exc = str(c[raises_key])
            if not re.fullmatch(r"[A-Za-z_][\w.]*", exc):
                raise ToolError(f"case #{i}: raises must be an exception class name, got {exc!r}.")
            err_rows.append((args, exc, c.get("match"), cid))
        else:
            if expected_key not in c:
                raise ToolError(f"case #{i} has neither '{expected_key}' nor '{raises_key}'.")
            ok_rows.append((args, _pyrepr(c[expected_key]), cid))
    fn = function_name.rsplit(".", 1)[-1]
    lines = []
    if ok_rows:
        names = ", ".join(arg_names + [expected_key])
        lines.append(f'@pytest.mark.parametrize(\n    "{names}",\n    [')
        for args, exp, cid in ok_rows:
            lines.append(f"        pytest.param({', '.join(args)}, {exp}, id={cid!r}),")
        lines.append("    ],\n)")
        lines.append(f"def test_{fn}({', '.join(arg_names)}, {expected_key}):")
        lines.append(f"    assert {function_name}({', '.join(arg_names)}) == {expected_key}")
    if err_rows:
        if ok_rows:
            lines.append("")
            lines.append("")
        lines.append('@pytest.mark.parametrize(\n    "' + ", ".join(arg_names + ["exc", "match"]) + '",\n    [')
        for args, exc, match, cid in err_rows:
            lines.append(f"        pytest.param({', '.join(args)}, {exc}, {match!r}, id={cid!r}),")
        lines.append("    ],\n)")
        lines.append(f"def test_{fn}_raises({', '.join(arg_names)}, exc, match):")
        lines.append("    with pytest.raises(exc, match=match):")
        lines.append(f"        {function_name}({', '.join(arg_names)})")
    code = "\n".join(lines)
    try:
        ast.parse("import pytest\n" + code)
    except SyntaxError as e:
        raise ToolError(f"Generated block is not valid Python ({e.msg}); check raw: values.") from None
    return {
        "code": code,
        "cases": len(cases),
        "value_cases": len(ok_rows),
        "error_cases": len(err_rows),
        "ids": [r[-1] for r in ok_rows] + [r[-1] for r in err_rows],
        "duplicate_inputs": dupes,
        "summary": f"{len(ok_rows)} value case(s) + {len(err_rows)} error case(s) for {function_name}" + (f"; {len(dupes)} duplicate input(s) to remove." if dupes else "."),
    }
