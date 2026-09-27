"""Regex Builder — patterns that match exactly what you mean and can't take down the server.

A small regex parser powers the explainer and the static safety analysis (nested
quantifiers, overlapping alternation, ambiguous adjacent repeats). Matching
against samples runs in a forked subprocess with a hard timeout.
"""

from __future__ import annotations

import multiprocessing
import re
import string
from typing import Literal

from ...core import Agent, ToolError
from ._common import require_text

AGENT = Agent(
    slug="regex-builder",
    name="Regex Builder",
    category="engineering",
    tagline="Build, test and explain regular expressions that match exactly the right strings — and are proven safe from catastrophic backtracking.",
    description=(
        "Writes regular expressions the way a compiler engineer would: from positive and negative "
        "examples, tested against every sample in a sandboxed matcher with a hard timeout, statically "
        "checked for ReDoS (nested quantifiers, overlapping alternation, ambiguous repeats), explained "
        "token by token, and converted between Python, JavaScript, PCRE, Java and Go (RE2) flavours "
        "with every unsupported feature called out."
    ),
    triggers=[
        "write a regex that matches …",
        "why doesn't this regex match / work",
        "explain this regular expression",
        "is this regex safe / could it cause ReDoS",
        "convert this regex to JavaScript / Python / Go",
        "test this pattern against these strings",
    ],
    examples=[
        "Regex for US phone numbers like (555) 123-4567 or 555-123-4567 but not 5551234567.",
        "Explain ^(?=.*[A-Z])(?=.*\\d)[A-Za-z\\d]{8,}$ and tell me if it's safe for user input.",
        "This pattern hangs on long inputs in production: ^(\\w+\\s?)*$ — fix it.",
    ],
    connectors=["GitHub", "GitLab"],
    playbook="""
    ## Standard
    You are the engineer people bring regexes to before they go into production. Excellent
    means: the pattern matches every positive example and none of the negatives, it is
    anchored and bounded so it cannot be weaponised with a long input, and someone reading it
    next year can understand it from the explanation. The one metric: **zero false matches
    in production** — a regex that over-matches is a validation bypass.

    ## Intake
    You need: what should match (≥3 examples), what must not match (≥3 examples, especially
    near-misses), where it runs (language/flavour, and whether input is user-controlled), and
    the operation (validate whole string / find in text / extract groups / replace). Ask at
    most 3 questions only when examples are missing; otherwise invent near-miss negatives
    yourself, state them, and proceed.

    ## Procedure
    1. **Write the spec as examples first.** Two lists: `should_match`, `should_not_match`.
       Add near-misses the user didn't mention (empty string, extra whitespace, wrong case,
       trailing characters, unicode look-alikes). Validation regexes get `fullmatch` semantics
       (anchor with `^…$` or `\\A…\\Z`); extraction regexes get `search`/`findall`.
    2. **Draft the pattern** using the simplest construct that works: character classes
       over alternation, explicit repeat counts `{3}` over `+` where the length is known,
       non-capturing groups `(?:…)` unless you extract, named groups `(?P<area>…)` when you do.
    3. **Check safety before running anything.** Call `regex_builder__check_regex_safety`.
       `dangerous` → rewrite before testing (make the repeated tokens mutually exclusive, add
       anchors, replace `(a|ab)*` style ambiguity with a class, bound the repeat). `warning` →
       fix if the input is user-controlled.
    4. **Test it.** Call `regex_builder__test_regex` with the pattern, both sample lists,
       flags and mode. It runs every sample in a sandbox with a 1-second hard timeout and
       reports each failure with a hint (case, anchoring, whitespace). Iterate until every
       sample passes; never hand over an untested pattern.
    5. **Explain it.** Call `regex_builder__explain_regex` and include the token table in the
       answer — it is the documentation, and it catches "I didn't mean that" moments.
    6. **Port it.** If the target flavour differs from Python (JS, PCRE, Java, Go/RE2), call
       `regex_builder__convert_flavor` and hand over the converted pattern plus the list of
       unsupported features and how you worked around them.
    7. **Deliver** with the output format: the pattern in the target flavour, flags, the
       sample results table, the explanation, and the safety verdict. If the requirement is
       really a parser (nested structures, dates with validation, email per RFC 5322), say so
       and give the regex only as a coarse pre-filter.

    ## Frameworks
    - **ReDoS triad**: (1) a repeated group that contains a repeat (`(\\w+)*`), (2) alternation
      inside a repeat whose branches can match the same text (`(a|a)*`, `(\\w|\\d)+`),
      (3) adjacent repeats over overlapping sets (`\\s*\\s*`, `.*\\w+.*`) — each makes the
      number of ways to match grow exponentially/polynomially on a non-matching input.
      Fixes: make tokens mutually exclusive, anchor, bound repeats `{1,64}`, use possessive
      `*+` / atomic `(?>…)` where supported (Python 3.11+, PCRE, Java), or use RE2 (Go) which
      is linear by construction.
    - **Anchoring rule**: validation = `\\A…\\Z` (`^…$` with `re.M` matches per line — a bypass).
      Python `$` matches before a trailing newline; use `\\Z` for strict end.
    - **Greedy vs lazy**: `.*?` stops at the first possible end; a lazy quantifier is not a
      fix for a wrong character class — prefer `[^"]*` over `.*?"`.
    - **Unicode**: `\\d` in Python matches Arabic-Indic digits unless `re.ASCII`; `\\w` matches
      letters in any script. Say which you want. JS needs the `u` flag for astral characters.
    - **Length bounds**: any regex applied to user input should have a maximum input length
      enforced *before* matching (e.g. 1,000 chars) regardless of pattern safety.

    ## Output format
    ```
    **Pattern (<flavour>):** `<pattern>` · **Flags:** <…> · **Mode:** fullmatch | search | findall
    **Safety:** <safe | warning | dangerous> — <one-line reason>

    | Sample | Expected | Result | Groups |
    |---|---|---|---|

    **Explanation**
    | Token | Means |
    |---|---|

    **Notes:** <unicode/anchoring/flavour caveats; when to use a real parser instead>
    ```

    ## Anti-patterns
    - Testing only the positives. The negatives are where validation regexes fail.
    - `.*` as glue between tokens. Use the tightest class that can appear there.
    - `^` and `$` with the multiline flag on user input — any line matching bypasses the check.
    - Trusting a regex from a blog for email/URL/IP without running the samples.
    - Capturing groups you never read; they cost time and confuse readers.
    - Nested quantifiers "because it works on my test strings" — attackers don't send your test strings.
    - Using a regex where a parser belongs (HTML, JSON, nested parentheses, full email validation).
    """,
)

MAX_PATTERN = 500
MAX_SAMPLE = 1000
MAX_SAMPLES = 100
FLAG_MAP = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE, "a": re.ASCII, "u": 0}

# ── parser ───────────────────────────────────────────────────────────────────

ESCAPES = {
    "d": "a digit (0-9; any Unicode digit unless ASCII flag)", "D": "a non-digit", "w": "a word character (letter, digit, underscore)", "W": "a non-word character",
    "s": "a whitespace character", "S": "a non-whitespace character", "b": "a word boundary", "B": "not a word boundary",
    "A": "start of string", "Z": "end of string (Python)", "z": "absolute end of string", "n": "a newline", "t": "a tab", "r": "a carriage return",
    ".": "a literal dot", "\\": "a literal backslash", "/": "a literal slash", "-": "a literal hyphen", "G": "end of previous match (PCRE)", "h": "horizontal whitespace (PCRE)",
    "R": "any line break (PCRE)", "0": "a NUL byte",
}
ALL = None  # sentinel meaning "any character"
DIGITS = set(string.digits)
WORD = set(string.ascii_letters + string.digits + "_")
SPACE = set(" \t\n\r\f\v")


class _Parser:
    def __init__(self, pattern: str):
        self.p = pattern
        self.i = 0
        self.group_count = 0

    def parse(self) -> list[list[dict]]:
        alts, closed = self._alternatives()
        if closed:
            raise ToolError(f"Unbalanced ')' at position {self.i - 1}.")
        return alts

    def _alternatives(self) -> tuple[list[list[dict]], bool]:
        branches: list[list[dict]] = [[]]
        while self.i < len(self.p):
            c = self.p[self.i]
            if c == "|":
                self.i += 1
                branches.append([])
                continue
            if c == ")":
                self.i += 1
                return branches, True
            atom = self._atom()
            if atom is None:
                continue
            self._quantifier(atom)
            branches[-1].append(atom)
        return branches, False

    def _atom(self) -> dict | None:
        p, i = self.p, self.i
        c = p[i]
        start = i
        if c == "(":
            return self._group()
        if c == "[":
            return self._class()
        if c == "\\":
            if i + 1 >= len(p):
                raise ToolError("Pattern ends with a lone backslash.")
            n = p[i + 1]
            if n.isdigit() and n != "0":
                j = i + 1
                while j < len(p) and p[j].isdigit():
                    j += 1
                self.i = j
                return {"type": "backref", "raw": p[start:j], "start": start}
            if n == "x":
                self.i = i + 4
                return {"type": "literal", "raw": p[start:self.i], "char": chr(int(p[i + 2:i + 4], 16)) if re.fullmatch(r"[0-9a-fA-F]{2}", p[i + 2:i + 4]) else "?", "start": start}
            if n == "u":
                self.i = i + 6
                return {"type": "literal", "raw": p[start:self.i], "char": "?", "start": start}
            if n == "p" or n == "P":
                m = re.match(r"\\[pP]\{[^}]*\}", p[i:])
                self.i = i + (m.end() if m else 2)
                return {"type": "escape", "raw": p[start:self.i], "meaning": "a Unicode property class (not supported by Python's re)", "start": start}
            if n == "k":
                m = re.match(r"\\k<[^>]*>", p[i:])
                self.i = i + (m.end() if m else 2)
                return {"type": "backref", "raw": p[start:self.i], "start": start}
            self.i = i + 2
            if n in "dDwWsSbBAZzGhR":
                return {"type": "escape", "raw": p[start:self.i], "meaning": ESCAPES.get(n, ""), "start": start}
            return {"type": "literal", "raw": p[start:self.i], "char": {"n": "\n", "t": "\t", "r": "\r", "0": "\0"}.get(n, n), "start": start}
        if c == ".":
            self.i += 1
            return {"type": "any", "raw": ".", "start": start}
        if c in "^$":
            self.i += 1
            return {"type": "anchor", "raw": c, "start": start}
        if c in "*+?":
            raise ToolError(f"Quantifier '{c}' at position {i} has nothing to repeat.")
        if c == "{" and re.match(r"\{\d*,?\d*\}", p[i:]) and (i == 0 or p[i - 1] in "(|"):
            raise ToolError(f"Quantifier at position {i} has nothing to repeat.")
        self.i += 1
        return {"type": "literal", "raw": c, "char": c, "start": start}

    def _group(self) -> dict:
        p, start = self.p, self.i
        self.i += 1
        kind, name, flags = "capture", None, None
        if p.startswith("?", self.i):
            rest = p[self.i:]
            m = re.match(r"\?P<([^>]+)>|\?<([A-Za-z_]\w*)>|\?'([A-Za-z_]\w*)'", rest)
            if m:
                kind, name = "named", m.group(1) or m.group(2) or m.group(3)
                self.i += m.end()
            elif rest.startswith("?:"):
                kind, self.i = "noncapture", self.i + 2
            elif rest.startswith("?="):
                kind, self.i = "lookahead", self.i + 2
            elif rest.startswith("?!"):
                kind, self.i = "negative lookahead", self.i + 2
            elif rest.startswith("?<="):
                kind, self.i = "lookbehind", self.i + 3
            elif rest.startswith("?<!"):
                kind, self.i = "negative lookbehind", self.i + 3
            elif rest.startswith("?>"):
                kind, self.i = "atomic", self.i + 2
            elif rest.startswith("?P="):
                m2 = re.match(r"\?P=(\w+)\)", rest)
                if not m2:
                    raise ToolError(f"Bad named backreference at position {start}.")
                self.i += m2.end()
                return {"type": "backref", "raw": p[start:self.i], "start": start}
            elif rest.startswith("?#"):
                end = p.find(")", self.i)
                self.i = len(p) if end < 0 else end + 1
                return {"type": "comment", "raw": p[start:self.i], "start": start}
            elif rest.startswith("?("):
                kind, self.i = "conditional", self.i + 1
                end = p.find(")", self.i)
                self.i = end + 1 if end >= 0 else len(p)
            else:
                m3 = re.match(r"\?([aiLmsux]+)(?:-([aiLmsux]+))?(:|\))", rest)
                if not m3:
                    raise ToolError(f"Unknown group syntax at position {start}: '{p[start:start + 4]}'.")
                flags = m3.group(0)[1:-1]
                if m3.group(3) == ")":
                    self.i += m3.end()
                    return {"type": "flags", "raw": p[start:self.i], "flags": flags, "start": start}
                kind = "flags-scoped"
                self.i += m3.end()
        if kind in ("capture", "named"):
            self.group_count += 1
        number = self.group_count if kind in ("capture", "named") else None
        alts, closed = self._alternatives()
        if not closed:
            raise ToolError(f"Unclosed '(' at position {start}.")
        return {"type": "group", "kind": kind, "name": name, "number": number, "flags": flags, "alternatives": alts, "raw": p[start:self.i], "start": start}

    def _class(self) -> dict:
        p, start = self.p, self.i
        i = self.i + 1
        negated = p.startswith("^", i)
        if negated:
            i += 1
        items: list[str] = []
        first = True
        while i < len(p):
            c = p[i]
            if c == "]" and not first:
                break
            first = False
            if c == "\\" and i + 1 < len(p):
                items.append(p[i:i + 2])
                i += 2
                continue
            if c == "[" and p.startswith("[:", i):
                end = p.find(":]", i)
                if end > 0:
                    items.append(p[i:end + 2])
                    i = end + 2
                    continue
            if i + 2 < len(p) and p[i + 1] == "-" and p[i + 2] != "]":
                items.append(p[i:i + 3])
                i += 3
                continue
            items.append(c)
            i += 1
        if i >= len(p):
            raise ToolError(f"Unclosed '[' at position {start}.")
        self.i = i + 1
        return {"type": "class", "raw": p[start:self.i], "negated": negated, "items": items, "start": start}

    def _quantifier(self, atom: dict) -> None:
        p = self.p
        if self.i >= len(p):
            return
        c = p[self.i]
        q = None
        if c in "*+?":
            q = {"*": (0, None), "+": (1, None), "?": (0, 1)}[c]
            raw = c
            self.i += 1
        elif c == "{":
            m = re.match(r"\{(\d*)(,)?(\d*)\}", p[self.i:])
            if not m or (not m.group(1) and not m.group(3)):
                return
            lo = int(m.group(1) or 0)
            hi = None if m.group(2) and not m.group(3) else int(m.group(3) or lo)
            if hi is not None and hi < lo:
                raise ToolError(f"Quantifier {m.group(0)} has max < min at position {self.i}.")
            q, raw = (lo, hi), m.group(0)
            self.i += m.end()
        if q is None:
            return
        lazy = possessive = False
        if self.i < len(p) and p[self.i] == "?":
            lazy, self.i = True, self.i + 1
            raw += "?"
        elif self.i < len(p) and p[self.i] == "+":
            possessive, self.i = True, self.i + 1
            raw += "+"
        if atom["type"] in ("anchor",) or (atom["type"] == "escape" and atom["raw"][1] in "bBAZzG"):
            raise ToolError(f"Cannot repeat a zero-width assertion '{atom['raw']}' at position {atom['start']}.")
        atom["quant"] = {"min": q[0], "max": q[1], "lazy": lazy, "possessive": possessive, "raw": raw}


def _parse(pattern: str) -> list[list[dict]]:
    return _Parser(pattern).parse()


# ── explain ──────────────────────────────────────────────────────────────────


def _quant_text(q: dict | None) -> str:
    if not q:
        return ""
    lo, hi = q["min"], q["max"]
    if (lo, hi) == (0, None):
        core = "zero or more times"
    elif (lo, hi) == (1, None):
        core = "one or more times"
    elif (lo, hi) == (0, 1):
        core = "optionally (0 or 1 time)"
    elif hi is None:
        core = f"at least {lo} times"
    elif lo == hi:
        core = f"exactly {lo} time{'s' if lo != 1 else ''}"
    else:
        core = f"between {lo} and {hi} times"
    mode = " (lazy: as few as possible)" if q["lazy"] else " (possessive: never gives back)" if q["possessive"] else " (greedy)" if hi != lo else ""
    return ", " + core + mode


def _class_text(atom: dict) -> str:
    parts = []
    for it in atom["items"]:
        if len(it) == 3 and it[1] == "-":
            parts.append(f"{it[0]}-{it[2]}")
        elif it.startswith("\\") and len(it) == 2 and it[1] in ESCAPES:
            parts.append(ESCAPES[it[1]])
        elif it.startswith("[:"):
            parts.append(f"POSIX class {it}")
        else:
            parts.append(repr(it))
    return ("any character NOT in: " if atom["negated"] else "one character from: ") + ", ".join(parts)


def _explain(branches: list[list[dict]], depth: int, rows: list[dict]) -> None:
    for bi, branch in enumerate(branches):
        if len(branches) > 1:
            rows.append({"depth": depth, "token": "|" if bi else "", "meaning": f"alternative {bi + 1} of {len(branches)}"})
        run: list[dict] = []

        def flush_run() -> None:
            if run:
                text = "".join(a["char"] for a in run)
                rows.append({"depth": depth, "token": "".join(a["raw"] for a in run), "meaning": f"the literal text {text!r}" if len(run) > 1 else f"the character {text!r}"})
                run.clear()

        for atom in branch:
            t = atom["type"]
            q = atom.get("quant")
            if t == "literal" and not q:
                run.append(atom)
                continue
            flush_run()
            if t == "literal":
                rows.append({"depth": depth, "token": atom["raw"] + q["raw"], "meaning": f"the character {atom['char']!r}" + _quant_text(q)})
            elif t == "escape":
                rows.append({"depth": depth, "token": atom["raw"] + (q["raw"] if q else ""), "meaning": atom["meaning"] + _quant_text(q)})
            elif t == "any":
                rows.append({"depth": depth, "token": "." + (q["raw"] if q else ""), "meaning": "any character except newline (any at all with DOTALL)" + _quant_text(q)})
            elif t == "anchor":
                rows.append({"depth": depth, "token": atom["raw"], "meaning": "start of string (or line with MULTILINE)" if atom["raw"] == "^" else "end of string / before a final newline (or end of line with MULTILINE)"})
            elif t == "class":
                rows.append({"depth": depth, "token": atom["raw"] + (q["raw"] if q else ""), "meaning": _class_text(atom) + _quant_text(q)})
            elif t == "backref":
                rows.append({"depth": depth, "token": atom["raw"] + (q["raw"] if q else ""), "meaning": "the same text captured earlier by that group" + _quant_text(q)})
            elif t == "flags":
                rows.append({"depth": depth, "token": atom["raw"], "meaning": f"inline flags '{atom['flags']}' for the whole pattern"})
            elif t == "comment":
                rows.append({"depth": depth, "token": atom["raw"], "meaning": "a comment (ignored)"})
            elif t == "group":
                k = atom["kind"]
                label = {
                    "capture": f"capturing group #{atom['number']}", "named": f"named capturing group '{atom['name']}' (#{atom['number']})", "noncapture": "non-capturing group",
                    "lookahead": "lookahead: must be followed by (not consumed)", "negative lookahead": "negative lookahead: must NOT be followed by",
                    "lookbehind": "lookbehind: must be preceded by", "negative lookbehind": "negative lookbehind: must NOT be preceded by",
                    "atomic": "atomic group (no backtracking into it)", "flags-scoped": f"group with flags '{atom['flags']}'", "conditional": "conditional group",
                }[k]
                open_tok = atom["raw"][: len(atom["raw"]) - len(_inner_raw(atom)) - 1]
                rows.append({"depth": depth, "token": open_tok, "meaning": label + " — start"})
                _explain(atom["alternatives"], depth + 1, rows)
                rows.append({"depth": depth, "token": ")" + (q["raw"] if q else ""), "meaning": f"end of {label.split(':')[0].split(' —')[0]}" + _quant_text(q)})
        flush_run()


def _inner_raw(group: dict) -> str:
    raw = group["raw"]
    m = re.match(r"\((\?P<[^>]+>|\?<[A-Za-z_]\w*>|\?'[^']*'|\?:|\?=|\?!|\?<=|\?<!|\?>|\?[aiLmsux-]+:|\?\([^)]*\))?", raw)
    head = m.end() if m else 1
    return raw[head:-1]


@AGENT.tool
def explain_regex(pattern: str) -> dict:
    """Explain a regular expression token by token (groups indented, quantifiers spelled out, classes expanded) and summarise its groups, anchors, lookarounds and flags.

    Call for every pattern you deliver, and whenever a user pastes one they don't understand.

    Args:
        pattern: The regular expression (Python/PCRE-style syntax).
    """
    pattern = _check_pattern(pattern)
    tree = _parse(pattern)
    rows: list[dict] = []
    _explain(tree, 0, rows)
    groups, named, lookarounds, backrefs, anchors, inline_flags = [], [], 0, 0, [], []

    def walk(branches):
        nonlocal lookarounds, backrefs
        for br in branches:
            for a in br:
                if a["type"] == "group":
                    if a["kind"] in ("capture", "named"):
                        groups.append(a["number"])
                        if a["name"]:
                            named.append(a["name"])
                    if "look" in a["kind"]:
                        lookarounds += 1
                    walk(a["alternatives"])
                elif a["type"] == "backref":
                    backrefs += 1
                elif a["type"] == "anchor" or (a["type"] == "escape" and a["raw"][1] in "AZzb"):
                    anchors.append(a["raw"])
                elif a["type"] == "flags":
                    inline_flags.append(a["flags"])

    walk(tree)
    starts = pattern.startswith(("^", "\\A"))
    ends = pattern.endswith(("$", "\\Z", "\\z")) and not pattern.endswith("\\$")
    notes = []
    if not (starts and ends):
        notes.append("Not fully anchored — as a validator it would accept any string *containing* a match. Use fullmatch or \\A…\\Z.")
    if pattern.endswith("$"):
        notes.append("Python's $ also matches before a trailing newline; use \\Z for a strict end.")
    if "\\d" in pattern or "\\w" in pattern:
        notes.append("\\d/\\w match non-ASCII digits/letters in Python 3 unless re.ASCII is set.")
    return {
        "pattern": pattern,
        "tokens": rows,
        "table": "\n".join(f"{'  ' * r['depth']}{r['token']:<24} {r['meaning']}" for r in rows),
        "capturing_groups": len(groups),
        "named_groups": named,
        "alternatives_at_top_level": len(tree),
        "lookarounds": lookarounds,
        "backreferences": backrefs,
        "anchors": anchors,
        "inline_flags": inline_flags,
        "fully_anchored": bool(starts and ends),
        "notes": notes,
        "summary": f"{len(rows)} tokens, {len(groups)} capturing group(s)" + (f" ({', '.join(named)})" if named else "") + f", {len(tree)} top-level alternative(s), {'anchored' if starts and ends else 'not anchored'}.",
    }


# ── safety ───────────────────────────────────────────────────────────────────


def _charset(atom: dict):
    """Approximate set of characters an atom can start with; None = any."""
    t = atom["type"]
    if t == "literal":
        return {atom["char"]}
    if t == "any":
        return ALL
    if t == "escape":
        e = atom["raw"][1]
        return {"d": DIGITS, "w": WORD, "s": SPACE, "h": {" ", "\t"}}.get(e, ALL if e in "DWS" else set())
    if t == "class":
        s: set[str] = set()
        for it in atom["items"]:
            if len(it) == 3 and it[1] == "-":
                lo, hi = ord(it[0]), ord(it[2])
                s |= {chr(c) for c in range(lo, min(hi, lo + 300) + 1)}
            elif it.startswith("\\") and len(it) == 2:
                sub = {"d": DIGITS, "w": WORD, "s": SPACE}.get(it[1])
                if sub is None:
                    if it[1] in "DWS":
                        return ALL
                    s.add(it[1])
                else:
                    s |= sub
            elif it.startswith("[:"):
                return ALL
            else:
                s.add(it)
        if atom["negated"]:
            return ALL  # negated classes overlap with almost everything
        return s
    if t == "group":
        s = set()
        for br in atom["alternatives"]:
            first = _first_atom(br)
            if first is None:
                return ALL
            cs = _charset(first)
            if cs is ALL:
                return ALL
            s |= cs
        return s
    if t == "backref":
        return ALL
    return set()


def _first_atom(branch: list[dict]) -> dict | None:
    for a in branch:
        if a["type"] in ("anchor", "flags", "comment") or (a["type"] == "escape" and a["raw"][1] in "bBAZzG"):
            continue
        if a["type"] == "group" and "look" in a["kind"]:
            continue
        return a
    return None


def _overlap(a, b) -> bool:
    if a is ALL or b is ALL:
        return True
    return bool(a & b)


def _unbounded(atom: dict) -> bool:
    q = atom.get("quant")
    return bool(q) and (q["max"] is None or q["max"] > 10) and not q["possessive"]


def _contains_unbounded(atom: dict) -> bool:
    if atom["type"] != "group":
        return False
    for br in atom["alternatives"]:
        for a in br:
            if _unbounded(a) or _contains_unbounded(a):
                return True
    return False


def _group_first_set(group: dict):
    s: set[str] = set()
    for br in group["alternatives"]:
        f = _first_atom(br)
        if f is None:
            return ALL
        cs = _charset(f)
        if cs is ALL:
            return ALL
        s |= cs
    return s


def _nested_ambiguous(group: dict) -> bool:
    """A repeated group is dangerous when an unbounded repeat inside it can hand characters
    to what follows it in the same iteration or to the start of the next iteration."""
    first = _group_first_set(group)
    for br in group["alternatives"]:
        atoms = [a for a in br if a["type"] not in ("flags", "comment")]
        for idx, x in enumerate(atoms):
            inner_unbounded = _unbounded(x) or (x["type"] == "group" and not x.get("quant") and _contains_unbounded(x))
            if not inner_unbounded:
                continue
            xs = _charset(x)
            follow = set()
            ends_open = True
            for y in atoms[idx + 1:]:
                cs = _charset(y)
                follow = ALL if (cs is ALL or follow is ALL) else follow | cs
                if not _can_be_empty(y):
                    ends_open = False
                    break
            if ends_open:
                follow = ALL if (follow is ALL or first is ALL) else follow | first
            if _overlap(xs, follow):
                return True
    return False


def _can_be_empty(atom: dict) -> bool:
    q = atom.get("quant")
    if q and q["min"] == 0:
        return True
    if atom["type"] == "group":
        return any(all(_can_be_empty(a) for a in br) for br in atom["alternatives"])
    return atom["type"] in ("anchor", "flags", "comment") or (atom["type"] == "escape" and atom["raw"][1] in "bBAZzG")


def _scan(branches: list[list[dict]], findings: list[dict], dot_stars: list[int]) -> None:
    for br in branches:
        atoms = [a for a in br if a["type"] not in ("flags", "comment")]
        for idx, a in enumerate(atoms):
            q = a.get("quant")
            if a["type"] == "any" and q and q["max"] is None:
                dot_stars.append(a["start"])
            if a["type"] == "group":
                if _unbounded(a) and not a["quant"]["possessive"] and a["kind"] != "atomic":
                    if _contains_unbounded(a) and _nested_ambiguous(a):
                        findings.append({"level": "dangerous", "at": a["start"], "token": a["raw"] + a["quant"]["raw"], "problem": "nested quantifier: a repeated group containing an unbounded repeat — exponential backtracking on non-matching input",
                                         "fix": "Make the inner repeat and the outer separator mutually exclusive (e.g. (?:\\w+(?:\\s\\w+)*)), bound the repeats, or use possessive/atomic."})
                    if len(a["alternatives"]) > 1:
                        firsts = [_first_atom(b) for b in a["alternatives"]]
                        sets = [_charset(f) if f else ALL for f in firsts]
                        for x in range(len(sets)):
                            for y in range(x + 1, len(sets)):
                                if _overlap(sets[x], sets[y]):
                                    findings.append({"level": "dangerous", "at": a["start"], "token": a["raw"] + a["quant"]["raw"], "problem": f"repeated alternation whose branches {x + 1} and {y + 1} can match the same text — exponential backtracking",
                                                     "fix": "Merge the branches into one character class or make them start with different characters."})
                                    break
                            else:
                                continue
                            break
                    if any(all(_can_be_empty(x) for x in b) for b in a["alternatives"]):
                        findings.append({"level": "warning", "at": a["start"], "token": a["raw"] + a["quant"]["raw"], "problem": "repeated group that can match the empty string — ambiguous, slow, and matches nothing useful",
                                         "fix": "Require at least one character inside the group."})
                _scan(a["alternatives"], findings, dot_stars)
            if idx + 1 < len(atoms):
                b = atoms[idx + 1]
                if _unbounded(a) and _unbounded(b) and _overlap(_charset(a), _charset(b)):
                    findings.append({"level": "warning", "at": a["start"], "token": f"{a['raw']}{a['quant']['raw']}{b['raw']}{b['quant']['raw']}", "problem": "two adjacent unbounded repeats over overlapping characters — polynomial (O(n²)) backtracking",
                                     "fix": "Make the two repeats mutually exclusive, or merge them into one."})
                if _unbounded(a) and idx + 2 < len(atoms) and _unbounded(atoms[idx + 2]) and _can_be_empty(b) and _overlap(_charset(a), _charset(atoms[idx + 2])):
                    findings.append({"level": "warning", "at": a["start"], "token": f"{a['raw']}{a['quant']['raw']}{b['raw']}…", "problem": "unbounded repeats separated by an optional token over overlapping characters — polynomial backtracking",
                                     "fix": "Make the separator mandatory or the repeats mutually exclusive."})


def _check_pattern(pattern: str) -> str:
    if not isinstance(pattern, str) or not pattern:
        raise ToolError("pattern is empty.")
    if len(pattern) > MAX_PATTERN:
        raise ToolError(f"pattern too long ({len(pattern)} chars; max {MAX_PATTERN}).")
    return pattern


def _safety(pattern: str) -> dict:
    tree = _parse(pattern)
    findings: list[dict] = []
    dot_stars: list[int] = []
    _scan(tree, findings, dot_stars)
    if len(dot_stars) >= 2:
        findings.append({"level": "warning", "at": dot_stars[0], "token": ".*", "problem": f"{len(dot_stars)} unbounded '.' repeats — each pair backtracks quadratically on long non-matching input",
                         "fix": "Replace '.*' glue with the tightest class that can appear there (e.g. [^,]*)."})
    anchored = pattern.startswith(("^", "\\A")) and pattern.endswith(("$", "\\Z", "\\z"))
    if not anchored and any(_unbounded(a) for br in tree for a in br) and not findings:
        findings.append({"level": "info", "at": 0, "token": pattern[:20], "problem": "unanchored pattern with unbounded repeats — search re-tries from every position (O(n·m)); fine for short inputs",
                         "fix": "Anchor it, or cap input length before matching."})
    seen = set()
    uniq = []
    for f in findings:
        key = (f["level"], f["at"], f["problem"][:30])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    order = {"dangerous": 0, "warning": 1, "info": 2}
    uniq.sort(key=lambda f: (order[f["level"]], f["at"]))
    risk = uniq[0]["level"] if uniq else "safe"
    return {"risk": risk, "findings": uniq, "anchored": anchored}


@AGENT.tool
def check_regex_safety(pattern: str) -> dict:
    """Statically analyse a regex for catastrophic backtracking (ReDoS): nested quantifiers, repeated alternation with overlapping branches, adjacent overlapping repeats, empty-matching repeats, multiple `.*`. Returns risk level and a fix per finding.

    Call before test_regex and before shipping any pattern that runs on user input.

    Args:
        pattern: The regular expression to analyse.
    """
    pattern = _check_pattern(pattern)
    s = _safety(pattern)
    verdicts = {
        "dangerous": "DANGEROUS — exponential backtracking possible; do not run on untrusted input. Rewrite per the fixes.",
        "warning": "WARNING — polynomial backtracking on long inputs; cap input length (≤ ~1k chars) or fix.",
        "info": "Acceptable — linear-ish; cap input length as usual.",
        "safe": "Safe — no backtracking hazards found.",
    }
    return {"pattern": pattern, "risk": s["risk"], "anchored": s["anchored"], "findings": s["findings"], "verdict": verdicts[s["risk"]]}


# ── sandboxed testing ────────────────────────────────────────────────────────


def _match_worker(conn, pattern: str, flags: int, mode: str, samples: list[tuple[str, str]]) -> None:
    try:
        rx = re.compile(pattern, flags)
        rx_i = re.compile(pattern, flags | re.IGNORECASE)
        out = []
        for kind, s in samples:
            if mode == "findall":
                found = rx.findall(s)
                out.append({"kind": kind, "sample": s, "matched": bool(found), "found": [f if isinstance(f, str) else list(f) for f in found[:20]], "count": len(found)})
                continue
            m = rx.fullmatch(s) if mode == "fullmatch" else rx.search(s)
            row = {"kind": kind, "sample": s, "matched": m is not None}
            if m:
                row["span"] = list(m.span())
                row["match"] = m.group(0)[:200]
                row["groups"] = [g[:200] if isinstance(g, str) else g for g in m.groups()]
                row["named"] = {k: (v[:200] if isinstance(v, str) else v) for k, v in m.groupdict().items()}
            elif kind == "should_match":
                row["search_would_match"] = mode == "fullmatch" and rx.search(s) is not None
                row["ignorecase_would_match"] = (rx_i.fullmatch(s) if mode == "fullmatch" else rx_i.search(s)) is not None
                row["stripped_would_match"] = (rx.fullmatch(s.strip()) if mode == "fullmatch" else rx.search(s.strip())) is not None and s != s.strip()
            out.append(row)
        conn.send(("ok", out))
    except re.error as e:
        conn.send(("error", f"Invalid regex: {e}"))
    except Exception as e:  # pragma: no cover
        conn.send(("error", f"Matcher failed: {e}"))
    finally:
        conn.close()


def _run_sandboxed(pattern: str, flags: int, mode: str, samples: list[tuple[str, str]], timeout: float = 1.0) -> list[dict]:
    try:
        ctx = multiprocessing.get_context("fork")
    except ValueError:
        ctx = None
    if ctx is None:
        # No fork available: rely on static check having passed, run inline.
        class _Conn:
            def __init__(self):
                self.msg = None

            def send(self, m):
                self.msg = m

            def close(self):
                pass

        c = _Conn()
        _match_worker(c, pattern, flags, mode, samples)
        status, payload = c.msg
    else:
        parent, child = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_match_worker, args=(child, pattern, flags, mode, samples), daemon=True)
        proc.start()
        child.close()
        proc.join(timeout)
        if proc.is_alive():
            proc.kill()
            proc.join(0.5)
            raise ToolError(f"Matching exceeded the {timeout:.0f}s limit — the pattern backtracks catastrophically on these samples. Run check_regex_safety and rewrite it.")
        if not parent.poll(0.1):
            raise ToolError("Matcher produced no result (crashed). Simplify the pattern.")
        status, payload = parent.recv()
    if status == "error":
        raise ToolError(payload)
    return payload


@AGENT.tool
def test_regex(pattern: str, should_match: list[str], should_not_match: list[str] = [], flags: str = "", mode: Literal["fullmatch", "search", "findall"] = "fullmatch") -> dict:
    """Test a regex against positive and negative samples in a sandbox (forked process, 1s hard timeout, static ReDoS pre-check), returning per-sample results, captured groups and hints for every failure.

    Call after check_regex_safety; iterate until every sample passes.

    Args:
        pattern: The regular expression (Python syntax; ≤ 500 chars).
        should_match: Strings that must match (≤ 100, each ≤ 1000 chars).
        should_not_match: Strings that must NOT match.
        flags: Any of i (ignorecase), m (multiline), s (dotall), x (verbose), a (ascii).
        mode: fullmatch (validate whole string), search (find anywhere), findall (extract all).
    """
    pattern = _check_pattern(pattern)
    if not isinstance(should_match, list) or not should_match:
        raise ToolError("should_match needs at least one sample.")
    should_not_match = list(should_not_match or [])
    if len(should_match) + len(should_not_match) > MAX_SAMPLES:
        raise ToolError(f"Too many samples (max {MAX_SAMPLES} total).")
    samples: list[tuple[str, str]] = []
    for kind, lst in (("should_match", should_match), ("should_not_match", should_not_match)):
        for s in lst:
            if not isinstance(s, str):
                raise ToolError(f"{kind} samples must be strings.")
            if len(s) > MAX_SAMPLE:
                raise ToolError(f"sample too long ({len(s)} chars; max {MAX_SAMPLE}).")
            samples.append((kind, s))
    fl = 0
    for ch in flags.replace(",", "").replace(" ", "").lower():
        if ch not in FLAG_MAP:
            raise ToolError(f"unknown flag {ch!r}; use i, m, s, x, a.")
        fl |= FLAG_MAP[ch]
    safety = _safety(pattern)
    if safety["risk"] == "dangerous":
        f = safety["findings"][0]
        raise ToolError(f"Refusing to run a dangerous pattern: {f['problem']} at position {f['at']} ('{f['token']}'). Fix: {f['fix']}")
    try:
        re.compile(pattern, fl)
    except re.error as e:
        raise ToolError(f"Invalid regex: {e.msg} at position {e.pos}.") from None
    results = _run_sandboxed(pattern, fl, mode, samples)
    failures = []
    for r in results:
        expected = r["kind"] == "should_match"
        r["passed"] = r["matched"] == expected
        if not r["passed"]:
            hints = []
            if expected:
                if r.get("search_would_match"):
                    hints.append("matches a substring but not the whole string — something before/after isn't covered; check anchors and optional parts")
                if r.get("ignorecase_would_match"):
                    hints.append("would match with the i flag — case sensitivity")
                if r.get("stripped_would_match"):
                    hints.append("would match after stripping whitespace — allow \\s* at the edges or strip input first")
                if not hints:
                    hints.append("no match at all — compare the sample character by character against the token table from explain_regex")
            else:
                hints.append(f"unwanted match: {r.get('match', r.get('found'))!r}" + ("" if mode == "fullmatch" else " — with search mode the pattern only needs to occur somewhere; anchor it if you meant validation"))
            r["hints"] = hints
            failures.append(r)
    n_pass = sum(1 for r in results if r["passed"])
    verdict = f"{n_pass}/{len(results)} samples pass"
    if failures:
        verdict += f" — {sum(1 for f in failures if f['kind'] == 'should_match')} false negative(s), {sum(1 for f in failures if f['kind'] == 'should_not_match')} false positive(s)."
    else:
        verdict += " — all positives match, all negatives rejected."
    return {
        "pattern": pattern,
        "flags": flags,
        "mode": mode,
        "safety": {"risk": safety["risk"], "findings": safety["findings"]},
        "results": results,
        "failures": failures,
        "passed": n_pass,
        "total": len(results),
        "all_pass": not failures,
        "verdict": verdict,
    }


# ── flavour conversion ───────────────────────────────────────────────────────

FLAVOURS = ("python", "javascript", "pcre", "java", "go")


@AGENT.tool
def convert_flavor(pattern: str, target: Literal["python", "javascript", "pcre", "java", "go"], source: Literal["python", "javascript", "pcre", "java", "go"] = "python") -> dict:
    """Convert a regex between Python, JavaScript, PCRE, Java and Go (RE2) syntax: named groups, backreferences, anchors (\\A \\Z \\z), inline flags, possessive/atomic constructs, lookarounds, Unicode classes — listing each rewrite and every feature the target cannot express.

    Call whenever the runtime language differs from the one you tested in.

    Args:
        pattern: The pattern in the source flavour.
        target: Flavour to convert to.
        source: Flavour the pattern is written in (default python).
    """
    pattern = _check_pattern(pattern)
    if source == target:
        return {"pattern": pattern, "target": target, "changes": [], "unsupported": [], "notes": ["source and target are the same flavour"], "verdict": "No conversion needed."}
    out = pattern
    changes, unsupported, notes = [], [], []

    def sub(rx: str, repl: str, why: str) -> None:
        nonlocal out
        new = re.sub(rx, repl, out)
        if new != out:
            changes.append(why)
            out = new

    # named groups & backrefs
    if target == "python":
        sub(r"\(\?<([A-Za-z_]\w*)>", r"(?P<\1>", "named group (?<n>…) → (?P<n>…)")
        sub(r"\(\?'([A-Za-z_]\w*)'", r"(?P<\1>", "named group (?'n'…) → (?P<n>…)")
        sub(r"\\k<([A-Za-z_]\w*)>", r"(?P=\1)", "named backreference \\k<n> → (?P=n)")
        sub(r"\\z", r"\\Z", "\\z → \\Z (Python's \\Z is the absolute end)")
        if source in ("pcre", "java", "javascript") and "\\Z" in pattern:
            notes.append("\\Z in the source means 'end or before final newline'; Python's \\Z is absolute end — use \\n?\\Z if you need the old behaviour.")
        sub(r"\\h", r"[ \\t]", "\\h → [ \\t]")
        sub(r"\\R", r"(?:\\r\\n|\\n|\\r)", "\\R → (?:\\r\\n|\\n|\\r)")
        if re.search(r"\\[pP]\{", out):
            unsupported.append("\\p{…} Unicode properties — Python's re lacks them; use the third-party `regex` module or explicit ranges")
        if re.search(r"\[\[:\w+:\]\]", out):
            unsupported.append("POSIX classes [[:alpha:]] — replace with explicit classes ([A-Za-z])")
    else:
        sub(r"\(\?P<([A-Za-z_]\w*)>", r"(?<\1>", "named group (?P<n>…) → (?<n>…)")
        sub(r"\(\?P=([A-Za-z_]\w*)\)", r"\\k<\1>", "named backreference (?P=n) → \\k<n>")
        if target == "go":
            out2 = re.sub(r"\(\?<([A-Za-z_]\w*)>", r"(?P<\1>", out)
            if out2 != out:
                changes[-1:] = ["named group → (?P<n>…) (Go accepts (?P<n>) on all versions; (?<n>) only from Go 1.22)"]
                out = out2
    if target == "javascript":
        sub(r"\\A", "^", "\\A → ^ (only equivalent without the m flag)")
        sub(r"\\[Zz]", "$", "\\Z/\\z → $ (only equivalent without the m flag)")
        if re.search(r"\(\?[aimsux-]+\)", out):
            flags_found = re.findall(r"\(\?([aimsux-]+)\)", out)
            out = re.sub(r"\(\?[aimsux-]+\)", "", out)
            changes.append(f"inline flags {flags_found} removed — pass them as RegExp flags (i, m, s, u)")
        if re.search(r"\(\?[aimsux-]+:", out):
            unsupported.append("scoped inline flags (?i:…) — JavaScript has no scoped flags (ES2025 adds them); apply the flag globally")
        if re.search(r"\(\?>", out):
            unsupported.append("atomic groups (?>…) — not in JavaScript; simplify the pattern so backtracking can't hurt")
        if re.search(r"[*+?}]\+", out):
            unsupported.append("possessive quantifiers (*+, ++, ?+) — not in JavaScript; use a lookahead-guarded group or remove")
        if re.search(r"\(\?\(", out):
            unsupported.append("conditional groups (?(1)…) — not in JavaScript")
        if re.search(r"\\[pP]\{", out):
            notes.append("\\p{…} needs the u (or v) flag in JavaScript.")
        sub(r"\\h", r"[ \\t]", "\\h → [ \\t]")
        sub(r"\\R", r"(?:\\r\\n|\\n|\\r)", "\\R → (?:\\r\\n|\\n|\\r)")
        notes.append("JavaScript \\d, \\w, \\b are ASCII-only; Python's are Unicode-aware unless re.ASCII — behaviour may differ on non-ASCII input.")
        notes.append("Escape forward slashes if using a /literal/ regex.")
    if target == "go":
        for feat, rx in (("backreferences (\\1, \\k<n>, (?P=n))", r"\\[1-9]|\\k<|\(\?P="), ("lookahead/lookbehind (?=, (?!, (?<=, (?<!", r"\(\?<?[=!]"),
                         ("atomic groups (?>…)", r"\(\?>"), ("possessive quantifiers", r"[*+?}]\+"), ("conditional groups", r"\(\?\(")):
            if re.search(rx, out):
                unsupported.append(f"{feat} — RE2 guarantees linear time by excluding these; restructure or post-validate in code")
        sub(r"\\Z", r"\\z", "\\Z → \\z (Go has only \\z, absolute end)")
        sub(r"\\h", r"[ \\t]", "\\h → [ \\t]")
        sub(r"\\R", r"(?:\\r\\n|\\n|\\r)", "\\R → (?:\\r\\n|\\n|\\r)")
        notes.append("RE2 is linear-time: no ReDoS possible, but the unsupported features above must be handled in code.")
    if target == "java":
        if re.search(r"\(\?P<", pattern):
            notes.append("Java group names must be letters/digits only (no underscores).")
        if re.search(r"\[\[:\w+:\]\]", out):
            unsupported.append("POSIX classes [[:alpha:]] — Java uses \\p{Alpha}")
        notes.append("In a Java string literal every backslash must be doubled (\"\\\\d+\").")
        if re.search(r"\(\?[aimsux-]*L", out):
            unsupported.append("Python's L (locale) flag has no Java equivalent")
    if target == "pcre":
        notes.append("PCRE \\Z matches before a final newline as well as at the end; use \\z for the absolute end.")
        if re.search(r"\(\?[aimsux-]*a", pattern) and source == "python":
            unsupported.append("Python's (?a) ASCII flag — PCRE is ASCII by default unless compiled with UTF/UCP")
    if source == "javascript" and target != "javascript":
        if re.search(r"\\u\{", pattern):
            sub(r"\\u\{([0-9A-Fa-f]+)\}", lambda m: "\\x{" + m.group(1) + "}" if target in ("pcre", "java") else "\\U" + m.group(1).zfill(8), "\\u{…} code point escape converted")
    if source == "python" and target != "python" and re.search(r"\(\?[aimsux-]*x", pattern):
        notes.append("Verbose (x) mode: JavaScript has none — strip whitespace/comments manually; PCRE/Java/Go support (?x).")
    verdict = (f"Converted with {len(changes)} rewrite(s)" + (f"; {len(unsupported)} feature(s) unsupported in {target} — handle in code." if unsupported else "."))
    return {"pattern": out, "source": source, "target": target, "changes": changes, "unsupported": unsupported, "notes": notes, "verdict": verdict}
