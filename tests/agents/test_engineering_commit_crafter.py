"""Commit Crafter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("commit-crafter")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_lint_commit_flags_and_fixes():
    out = call("lint_commit", message="Fixed the login bug.\nSome body right after header that is way too long for a single line of a commit body ok")
    assert out["valid"] is False
    assert any("not imperative" in e for e in out["errors"])
    assert any("period" in e for e in out["errors"])
    assert any("type(scope)" in e for e in out["errors"])
    assert any("blank line" in e for e in out["errors"])
    assert out["fixed_header"] == "chore: fix the login bug"


def test_lint_commit_valid_conventional():
    msg = "feat(api)!: add cursor pagination to /orders\n\nOffset pagination was slow beyond 10k rows because each page\nrescanned the prefix.\n\nBREAKING CHANGE: `page` query param removed; use `cursor`.\nRefs PROJ-42"
    out = call("lint_commit", message=msg)
    assert out["valid"] is True
    assert out["parsed"] == {"type": "feat", "scope": "api", "subject": "add cursor pagination to /orders", "breaking": True, "tickets": ["PROJ-42"]}
    assert out["implied_bump"] == "major"
    assert out["warnings"] == []


def test_lint_commit_rejects_empty():
    with pytest.raises(ToolError):
        call("lint_commit", message="  ")


@pytest.mark.parametrize(
    "current,bump,pre,expected",
    [
        ("1.4.2", "minor", "", "1.5.0"),
        ("1.4.2", "major", "", "2.0.0"),
        ("0.9.3", "major", "", "0.10.0"),
        ("1.4.2", "preminor", "rc", "1.5.0-rc.0"),
        ("1.5.0-rc.0", "prerelease", "", "1.5.0-rc.1"),
        ("1.5.0-rc.1", "release", "", "1.5.0"),
        ("1.5.0-rc.1", "minor", "", "1.5.0"),
        ("2.0.0-beta.2", "prerelease", "rc", "2.0.0-rc.0"),
    ],
)
def test_semver_bump(current, bump, pre, expected):
    assert call("semver_bump", current=current, bump=bump, prerelease_id=pre)["next"] == expected


def test_semver_bump_rejects_bad_version():
    with pytest.raises(ToolError):
        call("semver_bump", current="1.2", bump="patch")
    with pytest.raises(ToolError):
        call("semver_bump", current="1.2.3", bump="release")


COMMITS = [
    "a1b2c3d feat(api): add cursor pagination\n\nBREAKING CHANGE: page param removed",
    "b2c3d4e fix(auth): reject expired refresh tokens\n\nFixes #88",
    "c3d4e5f perf(db): batch inserts",
    "d4e5f6a docs: update README",
    "e5f6a7b chore(deps): bump pydantic",
    "Merge branch 'main' into feature",
    "random commit without a type",
]


def test_changelog_bump_and_markdown():
    out = call("changelog", commits=COMMITS, current_version="2.3.1", release_date="2026-09-27", repo_url="https://github.com/org/repo")
    assert out["bump"] == "major" and out["next_version"] == "3.0.0"
    assert out["counts"] == {"feat": 1, "fix": 1, "perf": 1, "docs": 1, "chore": 1}
    assert out["unparsed_commits"] == ["random commit without a type"]
    md = out["markdown"]
    assert md.startswith("## [3.0.0] - 2026-09-27")
    assert "### ⚠ BREAKING CHANGES\n- **api:** Page param removed" in md
    assert "### Added\n- **api:** Add cursor pagination ([a1b2c3d](https://github.com/org/repo/commit/a1b2c3d))" in md
    assert "### Fixed\n- **auth:** Reject expired refresh tokens [#88](https://github.com/org/repo/issues/88)" in md
    assert "README" not in md  # docs excluded by default
    assert "[3.0.0]: https://github.com/org/repo/compare/v2.3.1...v3.0.0" in md


def test_changelog_patch_only_and_internal():
    out = call("changelog", commits=["fix: typo in error message", "docs: add guide"], current_version="0.4.0", include_internal=True)
    assert out["bump"] == "patch" and out["next_version"] == "0.4.1"
    assert "### Documentation" in out["markdown"]


def test_changelog_rejects_bad_date():
    with pytest.raises(ToolError):
        call("changelog", commits=["fix: x"], current_version="1.0.0", release_date="27/09/2026")


DIFF = """--- a/src/billing/invoice.py
+++ b/src/billing/invoice.py
@@ -1,2 +1,4 @@
 x = 1
+y = 2
+z = 3
--- a/tests/billing/test_invoice.py
+++ b/tests/billing/test_invoice.py
@@ -1,1 +1,2 @@
 pass
+assert True
--- a/README.md
+++ b/README.md
@@ -1,1 +1,2 @@
 # hi
+more
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,1 +1,2 @@
 {}
+{}
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1,1 +1,2 @@
 on: push
+jobs: {}
"""


def test_split_changes_groups_and_order():
    out = call("split_changes", diff=DIFF)
    kinds = [c["kind"] for c in out["commits"]]
    assert kinds == ["dependencies", "ci", "source", "docs"]
    src = out["commits"][2]
    assert set(src["files"]) == {"src/billing/invoice.py", "tests/billing/test_invoice.py"}
    assert src["suggested_header"].startswith("feat(billing):")
    assert src["note"] == ""
    assert out["commits"][0]["suggested_header"].startswith("build(deps):")
    assert out["files"] == 5


def test_split_changes_rejects_non_diff():
    with pytest.raises(ToolError):
        call("split_changes", diff="nothing")


def test_lint_requires_space_after_colon():
    out = call("lint_commit", message="feat:add login")
    assert out["valid"] is False and any("no space after the colon" in e for e in out["errors"])
    assert out["fixed_header"] == "feat: add login"


def test_changelog_drops_commits_reverted_in_the_same_range():
    out = call("changelog", current_version="1.2.0", release_date="2026-09-27", commits=[
        "aaaaaaa feat: add dark mode", "bbbbbbb fix: correct rounding",
        "ccccccc revert: feat: add dark mode\n\nThis reverts commit aaaaaaa."])
    assert out["bump"] == "patch" and out["next_version"] == "1.2.1"
    assert "dark mode" not in out["markdown"] and out["notes"][0].startswith("aaaaaaa was reverted")
