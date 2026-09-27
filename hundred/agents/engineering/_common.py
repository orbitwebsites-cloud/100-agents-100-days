"""Shared helpers for the engineering agents.

Underscore module: the registry skips it. Only pure, deterministic stdlib code
lives here — input bounding, a unified-diff parser, unit formatting, entropy.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from ...core import ToolError

MAX_TEXT = 200_000


def require_text(value: str, name: str = "input", limit: int = MAX_TEXT) -> str:
    """Return the text stripped of trailing whitespace, or raise a clean ToolError."""
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{name} is empty.")
    if len(value) > limit:
        raise ToolError(f"{name} too long ({len(value):,} chars; max {limit:,}). Split it up.")
    return value


def bound_list(items: list, name: str, limit: int) -> list:
    if not isinstance(items, list) or not items:
        raise ToolError(f"{name} must be a non-empty list.")
    if len(items) > limit:
        raise ToolError(f"{name} has {len(items)} entries; max {limit}.")
    return items


def human_bytes(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1000 or unit == "PB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.2f} {unit}"
        n /= 1000
    return f"{n:,.2f} PB"


def human_number(n: float) -> str:
    n = float(n)
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{n / div:,.2f}{suffix}"
    return f"{n:,.2f}" if n != int(n) else f"{int(n):,}"


def shannon_entropy(s: str) -> float:
    """Bits per character of a string (max ~6 for base64-looking noise, ~4 for hex)."""
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return round(-sum(c / n * math.log2(c / n) for c in counts.values()), 3)


# ── unified diff parsing ─────────────────────────────────────────────────────

_DIFF_GIT = re.compile(r"^diff --git a/(.+?) b/(.+)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|specs)(/|$)|(_test|\.test|\.spec|_spec)\.[a-z]+$|(^|/)test_[^/]+\.py$", re.I)
DOC_PATH = re.compile(r"\.(md|rst|txt|adoc)$|(^|/)docs?(/|$)|(^|/)(README|CHANGELOG|LICENSE)", re.I)
CONFIG_PATH = re.compile(r"\.(ya?ml|toml|ini|cfg|env|json|conf|properties)$|(^|/)\.github/|Dockerfile|Makefile|(^|/)\.(eslintrc|prettierrc|babelrc)", re.I)
LOCK_PATH = re.compile(r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Pipfile\.lock|Cargo\.lock|go\.sum|composer\.lock|Gemfile\.lock|uv\.lock)$")
MIGRATION_PATH = re.compile(r"(^|/)(migrations?|migrate|alembic|db/schema)(/|$)|\.sql$", re.I)
GENERATED_PATH = re.compile(r"\.(min\.js|min\.css|map|pb\.go|pb2\.py|generated\.[a-z]+|snap)$|(^|/)(dist|build|vendor|node_modules|__snapshots__)/", re.I)
SENSITIVE_PATH = re.compile(r"auth|login|session|token|crypto|secret|password|payment|billing|permission|acl|iam", re.I)

LANG_BY_EXT = {
    "py": "Python", "js": "JavaScript", "jsx": "JavaScript", "ts": "TypeScript", "tsx": "TypeScript", "mjs": "JavaScript",
    "go": "Go", "rs": "Rust", "java": "Java", "kt": "Kotlin", "rb": "Ruby", "php": "PHP", "cs": "C#", "swift": "Swift",
    "c": "C", "h": "C", "cpp": "C++", "cc": "C++", "hpp": "C++", "scala": "Scala", "sql": "SQL", "sh": "Shell",
    "bash": "Shell", "yml": "YAML", "yaml": "YAML", "json": "JSON", "toml": "TOML", "md": "Markdown", "html": "HTML",
    "css": "CSS", "scss": "SCSS", "tf": "Terraform", "proto": "Protobuf", "ex": "Elixir", "exs": "Elixir",
}


def language_of(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    if path.endswith("Dockerfile"):
        return "Docker"
    return LANG_BY_EXT.get(ext, "Other")


def classify_path(path: str) -> str:
    """One of: test, docs, lockfile, generated, migration, config, source."""
    if LOCK_PATH.search(path):
        return "lockfile"
    if GENERATED_PATH.search(path):
        return "generated"
    if TEST_PATH.search(path):
        return "test"
    if DOC_PATH.search(path):
        return "docs"
    if MIGRATION_PATH.search(path):
        return "migration"
    if CONFIG_PATH.search(path):
        return "config"
    return "source"


def parse_unified_diff(diff: str) -> list[dict]:
    """Parse a unified diff (git or plain) into per-file records.

    Each record: path, old_path, additions, deletions, hunks, status
    (added/deleted/modified/renamed/binary), added_lines [(new_lineno, text)],
    removed_lines [(old_lineno, text)], kind, language.
    """
    files: list[dict] = []
    cur: dict | None = None
    new_ln = old_ln = 0
    git_style = False

    def start(path: str, old_path: str | None = None) -> dict:
        rec = {
            "path": path, "old_path": old_path or path, "additions": 0, "deletions": 0, "hunks": 0,
            "status": "modified", "added_lines": [], "removed_lines": [],
        }
        files.append(rec)
        return rec

    def norm(p: str) -> str:
        p = p.split("\t")[0].strip()
        return p[2:] if p[:2] in ("a/", "b/") else p

    for raw in diff.splitlines():
        m = _DIFF_GIT.match(raw)
        if m:
            git_style = True
            cur = start(m.group(2), m.group(1))
            if m.group(1) != m.group(2):
                cur["status"] = "renamed"
            continue
        if raw.startswith("--- ") and (cur is None or cur["hunks"] == 0 or not git_style):
            p = norm(raw[4:])
            if cur is None or cur["hunks"] > 0:
                cur = start(p)
            if p == "/dev/null":
                cur["status"] = "added"
            continue
        if raw.startswith("+++ ") and cur is not None and cur["hunks"] == 0:
            p = norm(raw[4:])
            if p == "/dev/null":
                cur["status"] = "deleted"
            else:
                cur["path"] = p
            continue
        if cur is None:
            continue
        if raw.startswith("new file mode"):
            cur["status"] = "added"
            continue
        if raw.startswith("deleted file mode"):
            cur["status"] = "deleted"
            continue
        if raw.startswith("rename from "):
            cur["old_path"] = raw[len("rename from "):].strip()
            cur["status"] = "renamed"
            continue
        if raw.startswith("rename to "):
            cur["path"] = raw[len("rename to "):].strip()
            continue
        if raw.startswith("Binary files") or raw.startswith("GIT binary patch"):
            cur["status"] = "binary"
            continue
        h = _HUNK.match(raw)
        if h:
            cur["hunks"] += 1
            old_ln, new_ln = int(h.group(1)), int(h.group(3))
            continue
        if cur["hunks"] == 0:
            continue
        if raw.startswith("+"):
            cur["additions"] += 1
            cur["added_lines"].append((new_ln, raw[1:]))
            new_ln += 1
        elif raw.startswith("-"):
            cur["deletions"] += 1
            cur["removed_lines"].append((old_ln, raw[1:]))
            old_ln += 1
        elif raw.startswith("\\"):
            continue  # "\ No newline at end of file"
        else:
            new_ln += 1
            old_ln += 1
    for f in files:
        f["kind"] = classify_path(f["path"])
        f["language"] = language_of(f["path"])
    return files
