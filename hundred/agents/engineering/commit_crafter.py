"""Commit Crafter — commit messages, changelogs and version bumps that tools and humans can read.

Tools lint a message against Conventional Commits, split a diff into logical
commits, render a Keep-a-Changelog release from commit history, and compute
SemVer bumps exactly.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

from ...core import Agent, ToolError
from ._common import bound_list, parse_unified_diff, require_text

AGENT = Agent(
    slug="commit-crafter",
    name="Commit Crafter",
    category="engineering",
    tagline="Write commits, changelogs and version bumps that release tooling can parse and teammates can read in git blame two years later.",
    description=(
        "Turns a diff into well-scoped Conventional Commits with the type, scope and subject right, "
        "lints messages against the spec and the 50/72 rules with an auto-fixed rewrite, groups a "
        "range of commits into a Keep-a-Changelog release with the correct SemVer bump, and computes "
        "version arithmetic including pre-releases. Works with GitHub, GitLab, semantic-release, "
        "commitlint and release-please conventions."
    ),
    triggers=[
        "write a commit message for this diff",
        "split this change into commits",
        "is this commit message correct / lint my commit",
        "generate a changelog / release notes from these commits",
        "what version should the next release be",
        "bump the version / semver",
    ],
    examples=[
        "Here's my staged diff — write the commit message(s).",
        "Generate the CHANGELOG entry for v2.4.0 from these 37 commits since v2.3.1.",
        "We're on 1.9.3 and this release drops Python 3.8 support. What's the next version?",
    ],
    connectors=["GitHub", "GitLab", "Bitbucket", "Linear", "Jira", "Slack"],
    playbook="""
    ## Standard
    You are the release engineer whose commit history reads like documentation. Excellent
    means: each commit is one logical change that builds and passes on its own, its subject
    tells a reader *what* changed in ≤ 50 chars and its body tells *why*, and a release tool
    (semantic-release, release-please, commitlint) can compute the version and changelog from
    the messages without a human. The one metric: **can a teammate understand the change from
    `git log --oneline` alone?**

    ## Intake
    You need the diff (`git diff --staged`) or the commit list (`git log v1.2.0..HEAD
    --format='%s%n%b%n---'`), and the current version for release work. Nice to have: the
    ticket id, the team's scope names, whether the repo is 0.x. Ask at most 3 questions only
    if the change's intent is not inferable from the diff (rare); otherwise infer, and put the
    inference in the body where the author can correct it.

    ## Procedure
    1. **Split before you write.** For a diff, call `commit_crafter__split_changes`. It groups
       files into logical commits (source per area, tests with their source, docs, config/CI,
       dependency lockfiles) and proposes a type + scope for each. One commit per group; if a
       group mixes a refactor with a feature, split it further by hand. Order: refactors and
       chores first (they make the feature diff smaller), then the feature/fix, then docs.
    2. **Write each message** in Conventional Commits form:
       `<type>(<scope>)!: <subject>` + blank line + body + blank line + footers.
       - type: `feat` (user-visible capability), `fix` (user-visible bug), `perf`, `refactor`
         (no behaviour change), `docs`, `test`, `build`, `ci`, `chore`, `style`, `revert`.
       - scope: the module/package/area the team uses (lowercase, no spaces), omit if global.
       - subject: imperative mood ("add", not "added/adds"), lowercase, no trailing period,
         ≤ 50 chars (hard limit 72), specific ("cap retry backoff at 30s" not "fix retry").
       - body: wrap at 72; explain *why* and what alternatives were rejected; mention
         behaviour changes and migration steps. Skip the body only for trivial changes.
       - footers: `BREAKING CHANGE: <what breaks and how to migrate>` (and `!` in the header);
         `Fixes #123` / `Refs PROJ-42`; `Co-authored-by:`.
    3. **Lint every message** with `commit_crafter__lint_commit`. Fix every error and take the
       auto-rewrite for the header unless it lost meaning. Re-run until `valid` is true.
    4. **For a release**, call `commit_crafter__changelog` with the commit messages (subject +
       body each) and the current version. It parses types, breaking-change footers and
       ticket refs, decides the SemVer bump (breaking → major, feat → minor, fix/perf →
       patch; in 0.x breaking → minor unless told otherwise), and renders the Keep-a-Changelog
       section. Non-conventional commits are listed for manual classification — never drop
       them silently.
    5. **Compute the version** with `commit_crafter__semver_bump` for anything beyond the
       obvious (pre-releases `1.2.0-rc.1`, promoting a pre-release, build metadata). Never do
       version arithmetic in your head.
    6. **Deliver** the output format: the commit plan (or the changelog), each message in a
       fenced block ready for `git commit -F`, and the exact git commands.

    ## Frameworks
    - **Conventional Commits 1.0**: `type(scope)!: description`, `BREAKING CHANGE:` footer,
      any type allowed but the Angular set is the convention tooling expects.
    - **50/72 rule**: subject ≤ 50, body wrapped at 72 (git and GitHub truncate beyond that).
    - **Imperative test**: the subject completes "If applied, this commit will ___".
    - **SemVer 2.0**: MAJOR incompatible API change, MINOR backwards-compatible feature,
      PATCH backwards-compatible fix. Pre-release `-alpha.1 < -beta.1 < -rc.1 < release`;
      build metadata `+build.5` ignored in precedence. 0.y.z: anything may change; many teams
      treat breaking as MINOR until 1.0.
    - **Keep a Changelog**: sections Added / Changed / Deprecated / Removed / Fixed /
      Security, newest release first, ISO dates, "Unreleased" at the top.
    - **Atomic commit test**: could you revert this commit alone without breaking the build?
      If not, it's mis-split.

    ## Output format
    ```
    ## Commit plan (<n> commits)
    1. `<type>(<scope>): <subject>` — <files>
    2. …

    ### Commit 1
    ```
    <type>(<scope>): <subject>

    <body wrapped at 72>

    <footers>
    ```
    git add <files> && git commit -F msg1.txt

    ## Release <version> (bump: <major|minor|patch>) — for changelog requests
    ```markdown
    ## [<version>] - <YYYY-MM-DD>
    ### Added / Changed / Fixed / Removed / Security
    - <entry> (<hash or #PR>)
    ```
    ```

    ## Anti-patterns
    - `fix: fix bug`, `chore: updates`, `wip` — subjects that say nothing.
    - Past tense or descriptive mood ("Added tests", "Fixes the thing").
    - One commit with a feature, a drive-by refactor and a formatting pass.
    - `BREAKING CHANGE` buried in the body without the `!` — some tools miss it.
    - Bumping MAJOR for a big-but-compatible feature, or MINOR for a removed endpoint.
    - Changelog entries that restate the commit type ("Fixed: fixed the login bug"); write
      the user-facing effect ("Login no longer fails when the email has uppercase letters").
    - Ticket numbers as the whole subject (`PROJ-123`). The ticket goes in the footer.
    """,
)

TYPES = {"feat": "Features", "fix": "Bug Fixes", "perf": "Performance", "refactor": "Refactoring", "docs": "Documentation", "test": "Tests",
         "build": "Build", "ci": "CI", "chore": "Chores", "style": "Style", "revert": "Reverts"}
HEADER_RE = re.compile(r"^(?P<type>[A-Za-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s?(?P<subject>.*)$")
PAST_TENSE = re.compile(r"^(added|adds|adding|fixed|fixes|fixing|updated|updates|updating|removed|removes|removing|changed|changes|changing|implemented|implements|refactored|created|creates|moved|renamed|deleted|improved|bumped|merged)\b", re.I)
IMPERATIVE_FIX = {"added": "add", "adds": "add", "adding": "add", "fixed": "fix", "fixes": "fix", "fixing": "fix", "updated": "update", "updates": "update", "updating": "update",
                  "removed": "remove", "removes": "remove", "removing": "remove", "changed": "change", "changes": "change", "changing": "change", "implemented": "implement",
                  "implements": "implement", "refactored": "refactor", "created": "create", "creates": "create", "moved": "move", "renamed": "rename", "deleted": "delete",
                  "improved": "improve", "bumped": "bump", "merged": "merge"}
VAGUE = re.compile(r"^(fix(es)?( bug| stuff| things| it)?|update(s)?|change(s)?|wip|misc|cleanup|stuff|minor changes?|tweaks?|more|changes|test|tests)$", re.I)
TICKET_RE = re.compile(r"(?<![\w/#-])(#\d+|[A-Z]{2,10}-\d+)\b")
BREAKING_RE = re.compile(r"^BREAKING[ -]CHANGE:\s*(.+)$", re.M)


def _parse_commit(message: str) -> dict:
    lines = message.strip("\n").splitlines()
    header = lines[0].strip() if lines else ""
    m = HEADER_RE.match(header)
    body = "\n".join(lines[1:]).strip("\n") if len(lines) > 1 else ""
    breaking = BREAKING_RE.search(message)
    return {
        "header": header, "type": m.group("type").lower() if m else None, "scope": (m.group("scope") or "").strip() if m else None,
        "bang": bool(m and m.group("bang")), "subject": m.group("subject").strip() if m else header, "body": body,
        "breaking": bool(breaking) or bool(m and m.group("bang")), "breaking_note": breaking.group(1).strip() if breaking else None,
        "tickets": sorted({t for t in TICKET_RE.findall(message)}),
        "conventional": m is not None and m.group("type").lower() in TYPES and re.match(r"^[A-Za-z]+(?:\([^)]*\))?!?: ", header) is not None,
    }


@AGENT.tool
def lint_commit(message: str, max_subject: int = 50, allowed_scopes: list[str] | None = None) -> dict:
    """Lint a commit message against Conventional Commits and the 50/72 rules: type, scope, imperative mood, subject length/case/period, blank line before body, body wrap, breaking-change consistency, vague subjects — with an auto-fixed header.

    Call on every message before committing; loop until `valid` is true.

    Args:
        message: The full commit message (header, blank line, body, footers).
        max_subject: Soft subject-length limit (default 50; the hard limit is 72).
        allowed_scopes: Optional list of scopes the team uses; other scopes are flagged.
    """
    message = require_text(message, "message", 20_000)
    p = _parse_commit(message)
    lines = message.strip("\n").splitlines()
    errors, warnings = [], []
    header = p["header"]
    if not p["type"]:
        errors.append("header is not `type(scope): subject` — no recognised type prefix")
    elif p["type"] not in TYPES:
        errors.append(f"unknown type '{p['type']}' — use one of {', '.join(TYPES)}")
    if p["scope"] is not None and p["scope"] != "":
        if not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*", p["scope"]):
            warnings.append(f"scope '{p['scope']}' should be lowercase kebab/dot case with no spaces")
        if allowed_scopes and p["scope"] not in allowed_scopes:
            warnings.append(f"scope '{p['scope']}' not in the team's list ({', '.join(allowed_scopes[:10])})")
    if p["scope"] == "" and p["type"]:
        warnings.append("empty scope parentheses — omit them")
    if p["type"] and re.match(r"^[A-Za-z]+(?:\([^)]*\))?!?:(?!\s)", header):
        errors.append("no space after the colon — the spec requires `type: subject` (colon AND space); parsers such as commitlint won't read the type")
    subject = p["subject"]
    if not subject:
        errors.append("subject is empty")
    else:
        if len(header) > 72:
            errors.append(f"header is {len(header)} chars — hard limit 72 (git/GitHub truncate)")
        elif len(header) > max_subject + (len(header) - len(subject)):
            warnings.append(f"subject is {len(subject)} chars — aim for ≤ {max_subject}")
        if subject.endswith("."):
            errors.append("subject ends with a period")
        if subject[0].isupper() and not re.match(r"^[A-Z]{2,}", subject):
            warnings.append("subject starts with a capital — Conventional Commits tooling usually expects lowercase")
        first = subject.split()[0].lower() if subject.split() else ""
        if PAST_TENSE.match(subject):
            errors.append(f"'{first}' is not imperative — write it as a command ('{IMPERATIVE_FIX.get(first, first)} …')")
        if VAGUE.match(subject.strip()):
            errors.append(f"subject '{subject}' says nothing — name the specific change")
        if re.fullmatch(r"(#\d+|[A-Z]{2,10}-\d+)(\s*[:-]\s*)?", subject.strip()):
            errors.append("subject is just a ticket id — describe the change; put the ticket in a footer")
        if len(subject.split()) < 2 and not VAGUE.match(subject):
            warnings.append("one-word subject — usually too terse")
    if len(lines) > 1:
        if lines[1].strip():
            errors.append("no blank line between header and body")
        long_body = [i + 1 for i, l in enumerate(lines[1:], 1) if len(l) > 72 and not re.search(r"https?://\S{30,}", l)]
        if long_body:
            warnings.append(f"body line(s) {long_body[:5]} exceed 72 chars — wrap them")
    body_text = p["body"]
    if p["type"] in ("feat", "fix", "perf") and not body_text.strip():
        warnings.append("no body — say why (the diff already says what)")
    elif body_text.strip() and not re.search(r"\b(because|so that|since|to avoid|to allow|to fix|to make|to prevent|otherwise|previously|before this|which caused|so we|allows|enables|why)\b", body_text, re.I):
        warnings.append("body doesn't explain why — add the reason or the problem it solves")
    if p["bang"] and not p["breaking_note"]:
        warnings.append("header has `!` but no `BREAKING CHANGE:` footer describing the migration")
    if p["breaking_note"] and not p["bang"]:
        warnings.append("BREAKING CHANGE footer present but header lacks `!` — add it so all tools notice")
    if re.search(r"\bBREAKING CHANGE\b", message) and not BREAKING_RE.search(message):
        warnings.append("'BREAKING CHANGE' must be its own footer line: `BREAKING CHANGE: <description>`")
    if re.search(r"\b(fixes|closes|resolves)\s+(#\d+|[A-Z]{2,10}-\d+)", header, re.I):
        warnings.append("move `Fixes #123` into a footer line, not the subject")
    # auto-fix header
    fixed_subject = subject.rstrip(".").strip()
    words = fixed_subject.split()
    if words and words[0].lower() in IMPERATIVE_FIX:
        words[0] = IMPERATIVE_FIX[words[0].lower()]
        fixed_subject = " ".join(words)
    if fixed_subject and not re.match(r"^[A-Z]{2,}", fixed_subject):
        fixed_subject = fixed_subject[0].lower() + fixed_subject[1:]
    fixed_type = p["type"] if p["type"] in TYPES else "chore"
    fixed_scope = f"({p['scope']})" if p["scope"] else ""
    fixed_header = f"{fixed_type}{fixed_scope}{'!' if p['breaking'] else ''}: {fixed_subject}" if fixed_subject else header
    bump = "major" if p["breaking"] else "minor" if p["type"] == "feat" else "patch" if p["type"] in ("fix", "perf") else "none"
    score = max(0, 100 - 25 * len(errors) - 8 * len(warnings))
    return {
        "valid": not errors,
        "score": score,
        "parsed": {k: p[k] for k in ("type", "scope", "subject", "breaking", "tickets")},
        "header_length": len(header),
        "errors": errors,
        "warnings": warnings,
        "fixed_header": fixed_header,
        "implied_bump": bump,
        "verdict": ("Valid" if not errors else f"{len(errors)} error(s)") + f", {len(warnings)} warning(s); implies {bump} bump." + (f" Suggested header: `{fixed_header}`" if fixed_header != header else ""),
    }


# ── semver ───────────────────────────────────────────────────────────────────

SEMVER_RE = re.compile(r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$")


def _parse_semver(v: str) -> dict:
    m = SEMVER_RE.match(str(v).strip())
    if not m:
        raise ToolError(f"{v!r} is not a valid SemVer version (expected MAJOR.MINOR.PATCH[-pre][+build]).")
    pre = m.group("pre").split(".") if m.group("pre") else []
    for ident in pre:
        if not ident or (ident.isdigit() and len(ident) > 1 and ident[0] == "0"):
            raise ToolError(f"{v!r}: pre-release identifier {ident!r} is invalid (empty or leading zero).")
    return {"major": int(m.group("major")), "minor": int(m.group("minor")), "patch": int(m.group("patch")), "pre": pre, "build": m.group("build")}


def _fmt(v: dict, build: str | None = None) -> str:
    s = f"{v['major']}.{v['minor']}.{v['patch']}"
    if v["pre"]:
        s += "-" + ".".join(v["pre"])
    if build:
        s += "+" + build
    return s


def _pre_key(pre: list[str]):
    return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in pre]


def _cmp_key(v: dict):
    return (v["major"], v["minor"], v["patch"], 1 if not v["pre"] else 0, _pre_key(v["pre"]))


@AGENT.tool
def semver_bump(current: str, bump: str, prerelease_id: str = "", zero_major_breaking_is_minor: bool = True) -> dict:
    """Compute the next SemVer version for a bump (major, minor, patch, premajor, preminor, prepatch, prerelease, release) with correct pre-release arithmetic and precedence check.

    Call for any version arithmetic; never compute versions in your head.

    Args:
        current: The current version, e.g. "1.4.2" or "2.0.0-rc.1".
        bump: major | minor | patch | premajor | preminor | prepatch | prerelease | release (drop the pre-release tag).
        prerelease_id: Pre-release identifier for pre* bumps, e.g. "alpha", "beta", "rc".
        zero_major_breaking_is_minor: If true and current is 0.y.z, a `major` bump becomes a minor bump (the common pre-1.0 convention).
    """
    v = _parse_semver(current)
    bump = bump.lower().strip()
    if bump not in ("major", "minor", "patch", "premajor", "preminor", "prepatch", "prerelease", "release"):
        raise ToolError("bump must be one of major, minor, patch, premajor, preminor, prepatch, prerelease, release.")
    if prerelease_id and not re.fullmatch(r"[0-9A-Za-z-]+", prerelease_id):
        raise ToolError("prerelease_id must be alphanumeric (e.g. alpha, beta, rc).")
    notes = []
    new = dict(v, pre=[])
    if bump == "major" and v["major"] == 0 and zero_major_breaking_is_minor:
        bump = "minor"
        notes.append("0.y.z: breaking change bumps MINOR by the pre-1.0 convention (set zero_major_breaking_is_minor=false to go to 1.0.0).")
    if bump in ("major", "minor", "patch"):
        if v["pre"] and ((bump == "patch") or (bump == "minor" and v["patch"] == 0) or (bump == "major" and v["minor"] == 0 and v["patch"] == 0)):
            notes.append(f"{current} is a pre-release of this exact level — releasing it drops the tag without incrementing.")
        elif bump == "major":
            new.update(major=v["major"] + 1, minor=0, patch=0)
        elif bump == "minor":
            new.update(minor=v["minor"] + 1, patch=0)
        else:
            new.update(patch=v["patch"] + 1)
    elif bump == "release":
        if not v["pre"]:
            raise ToolError(f"{current} is not a pre-release; nothing to promote.")
    elif bump == "prerelease":
        if v["pre"]:
            pre = list(v["pre"])
            if prerelease_id and pre[0] != prerelease_id:
                pre = [prerelease_id, "0"]
                notes.append(f"switched pre-release track from {v['pre'][0]} to {prerelease_id}")
            elif pre[-1].isdigit():
                pre[-1] = str(int(pre[-1]) + 1)
            else:
                pre.append("1")
            new["pre"] = pre
        else:
            new.update(patch=v["patch"] + 1, pre=[prerelease_id or "rc", "0"])
            notes.append("no existing pre-release — started one on the next patch")
    else:  # premajor / preminor / prepatch
        level = bump[3:]
        if level == "major":
            new.update(major=v["major"] + 1, minor=0, patch=0)
        elif level == "minor":
            new.update(minor=v["minor"] + 1, patch=0)
        else:
            new.update(patch=v["patch"] + 1)
        new["pre"] = [prerelease_id or "rc", "0"]
    result = _fmt(new)
    if _cmp_key(new) <= _cmp_key(v):
        raise ToolError(f"Computed {result} does not sort after {current} — check the bump type.")
    ladder = []
    if new["pre"]:
        ladder = [_fmt(dict(new, pre=[])), "← the eventual release"]
    return {
        "current": _fmt(v, v["build"]),
        "bump": bump,
        "next": result,
        "is_prerelease": bool(new["pre"]),
        "eventual_release": _fmt(dict(new, pre=[])) if new["pre"] else result,
        "precedence": f"{_fmt(v)} < {result}",
        "notes": notes,
        "verdict": f"{_fmt(v)} → {result} ({bump})" + (f"; {' '.join(notes)}" if notes else ""),
    }


# ── changelog ────────────────────────────────────────────────────────────────

SECTION_FOR = {"feat": "Added", "fix": "Fixed", "perf": "Changed", "refactor": "Changed", "revert": "Changed", "docs": "Documentation", "build": "Build", "ci": "Build", "chore": "Maintenance", "style": "Maintenance", "test": "Tests"}
USER_FACING = {"feat", "fix", "perf", "revert"}


@AGENT.tool
def changelog(commits: list[str], current_version: str, release_date: str = "", include_internal: bool = False, repo_url: str = "") -> dict:
    """Parse Conventional Commits into a Keep-a-Changelog release section, decide the SemVer bump (breaking → major, feat → minor, fix/perf → patch) and compute the next version; lists non-conventional commits for manual triage.

    Call with every commit since the last tag (subject + body each, "---"-separated blocks or one per list item).

    Args:
        commits: Commit messages (each may include body/footers). Optionally prefix with the short hash: "abc1234 feat(api): …".
        current_version: The last released version, e.g. "2.3.1".
        release_date: Release date YYYY-MM-DD; defaults to today.
        include_internal: Also list docs/chore/ci/build/test/refactor commits in the changelog.
        repo_url: Optional repository URL to link hashes and tickets (e.g. https://github.com/org/repo).
    """
    commits = bound_list(commits, "commits", 2000)
    v = _parse_semver(current_version)
    rd = release_date.strip() or date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rd):
        raise ToolError("release_date must be YYYY-MM-DD.")
    sections: dict[str, list[str]] = defaultdict(list)
    breaking_entries, unparsed, parsed = [], [], []
    type_counts: Counter[str] = Counter()
    items: list[tuple[str | None, str]] = []
    for raw in commits:
        if not isinstance(raw, str) or not raw.strip():
            continue
        text = raw.strip()
        hm = re.match(r"^([0-9a-f]{7,40})\s+(.+)$", text.split("\n", 1)[0])
        sha = None
        if hm:
            sha = hm.group(1)[:7]
            text = hm.group(2) + ("\n" + text.split("\n", 1)[1] if "\n" in text else "")
        items.append((sha, text))
    # a commit reverted inside the same range cancels out (as conventional-commits-filter does): drop both
    shas = {sha for sha, _ in items if sha}
    dropped: set[int] = set()
    reverted_notes = []
    for i, (sha, text) in enumerate(items):
        if not re.match(r"^(revert\b|Revert \")", text, re.I):
            continue
        refs = re.findall(r"(?:This reverts commit|Refs:?)\s+([0-9a-f]{7,40})", text, re.I)
        target = next((r[:7] for r in refs if r[:7] in shas), None)
        if target:
            j = next(k for k, (sh, _) in enumerate(items) if sh == target)
            dropped |= {i, j}
            reverted_notes.append(f"{target} was reverted by {sha or 'a later commit'} in this range — both left out of the changelog and the bump.")
    for idx, (sha, text) in enumerate(items):
        if idx in dropped:
            continue
        p = _parse_commit(text)
        if not p["conventional"]:
            if re.match(r"^Merge (branch|pull request|remote)", p["header"]):
                continue
            unparsed.append(p["header"][:100])
            continue
        type_counts[p["type"]] += 1
        parsed.append(p)
        link = f" ([{sha}]({repo_url.rstrip('/')}/commit/{sha}))" if sha and repo_url else f" ({sha})" if sha else ""
        refs = ""
        if p["tickets"]:
            if repo_url:
                refs = " " + ", ".join(f"[{t}]({repo_url.rstrip('/')}/issues/{t[1:]})" if t.startswith("#") else t for t in p["tickets"])
            else:
                refs = " " + ", ".join(p["tickets"])
        scope = f"**{p['scope']}:** " if p["scope"] else ""
        subj = p["subject"][0].upper() + p["subject"][1:] if p["subject"] else ""
        entry = f"- {scope}{subj}{refs}{link}"
        if p["breaking"]:
            note = p["breaking_note"] or p["subject"]
            breaking_entries.append(f"- {scope}{note[0].upper() + note[1:]}{link}")
        if p["type"] in USER_FACING or include_internal:
            sections[SECTION_FOR.get(p["type"], "Changed")].append(entry)
    if not parsed and not unparsed:
        raise ToolError("No commits to process.")
    if breaking_entries:
        bump = "major"
    elif type_counts["feat"]:
        bump = "minor"
    elif type_counts["fix"] or type_counts["perf"] or type_counts["revert"]:
        bump = "patch"
    else:
        bump = "none"
    notes = list(reverted_notes)
    if bump == "none":
        next_v = _fmt(dict(v, pre=[]))
        notes.append("Only internal commits — no user-facing change; release only if you need to ship them.")
        next_version = next_v
    else:
        b = semver_bump(_fmt(v), bump)
        next_version = b["next"]
        notes.extend(b["notes"])
    order = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security", "Documentation", "Build", "Tests", "Maintenance"]
    md = [f"## [{next_version}] - {rd}"]
    if breaking_entries:
        md += ["", "### ⚠ BREAKING CHANGES"] + breaking_entries
    for sec in order:
        if sections.get(sec):
            md += ["", f"### {sec}"] + sections[sec]
    if repo_url:
        md += ["", f"[{next_version}]: {repo_url.rstrip('/')}/compare/v{_fmt(v)}...v{next_version}"]
    markdown = "\n".join(md)
    return {
        "current_version": _fmt(v),
        "next_version": next_version,
        "bump": bump,
        "counts": dict(type_counts),
        "breaking_changes": len(breaking_entries),
        "user_facing_entries": sum(len(sections[s]) for s in ("Added", "Fixed", "Changed")),
        "unparsed_commits": unparsed,
        "markdown": markdown,
        "notes": notes,
        "verdict": f"{len(parsed)} conventional commit(s) ({', '.join(f'{n} {t}' for t, n in type_counts.most_common(4))}) → {bump} bump: {_fmt(v)} → {next_version}."
                   + (f" {len(unparsed)} non-conventional commit(s) need manual classification." if unparsed else ""),
    }


# ── split diff ───────────────────────────────────────────────────────────────


def _scope_of(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    skip = {"src", "lib", "app", "pkg", "internal", "cmd", "packages", "apps", "services", "hundred"}
    for p in parts[:-1]:
        if p not in skip:
            return re.sub(r"[^a-z0-9-]", "-", p.lower())
    return re.sub(r"\.\w+$", "", parts[-1]).lower() if parts else "root"


@AGENT.tool
def split_changes(diff: str) -> dict:
    """Group a unified diff into logical commits (source per area with its tests, docs, config/CI, dependency lockfiles, generated files) and propose a Conventional Commit type, scope and header for each, in a sensible commit order.

    Call before writing messages for any diff touching more than a couple of files.

    Args:
        diff: The raw unified diff (`git diff --staged`).
    """
    diff = require_text(diff, "diff", 2_000_000)
    files = parse_unified_diff(diff)
    if not files:
        raise ToolError("No file changes found — is this a unified diff?")
    groups: dict[str, dict] = {}

    def group(key: str, kind: str, ctype: str, scope: str, order: int) -> dict:
        return groups.setdefault(key, {"key": key, "kind": kind, "type": ctype, "scope": scope, "files": [], "additions": 0, "deletions": 0, "order": order})

    test_by_scope: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        k = f["kind"]
        if k == "lockfile":
            g = group("deps", "dependencies", "build", "deps", 0)
        elif k == "config":
            if re.search(r"(^|/)\.github/|\.gitlab-ci|Jenkinsfile|\.circleci|azure-pipelines|(^|/)ci/", f["path"]):
                g = group("ci", "ci", "ci", "", 1)
            elif re.search(r"(package\.json|pyproject\.toml|setup\.cfg|setup\.py|requirements[^/]*\.txt|Cargo\.toml|go\.mod|Gemfile|composer\.json|build\.gradle|pom\.xml)$", f["path"]):
                g = group("deps", "dependencies", "build", "deps", 0)
            else:
                g = group("config", "config", "chore", "config", 2)
        elif k == "docs":
            g = group("docs", "docs", "docs", "", 9)
        elif k == "generated":
            g = group("generated", "generated", "chore", "generated", 8)
        elif k == "migration":
            g = group("migration", "migration", "feat", "db", 3)
        elif k == "test":
            test_by_scope[_scope_of(re.sub(r"(^|/)(tests?|__tests__|spec)/", r"\1", f["path"]))].append(f)
            continue
        else:
            g = group(f"src:{_scope_of(f['path'])}", "source", "feat", _scope_of(f["path"]), 5)
        g["files"].append(f["path"])
        g["additions"] += f["additions"]
        g["deletions"] += f["deletions"]
    src_scopes = {g["scope"]: g for g in groups.values() if g["kind"] == "source"}
    for scope, tfiles in test_by_scope.items():
        target = src_scopes.get(scope) or (next(iter(src_scopes.values())) if len(src_scopes) == 1 else None)
        if target is None:
            target = group("tests", "tests", "test", scope if len(test_by_scope) == 1 else "", 6)
        for f in tfiles:
            target["files"].append(f["path"])
            target["additions"] += f["additions"]
            target["deletions"] += f["deletions"]
    out = []
    for g in sorted(groups.values(), key=lambda g: (g["order"], g["key"])):
        added = sum(1 for f in files if f["path"] in g["files"] and f["status"] == "added")
        deleted = sum(1 for f in files if f["path"] in g["files"] and f["status"] == "deleted")
        if g["kind"] == "source":
            if deleted and not added and g["deletions"] > g["additions"]:
                g["type"], hint = "refactor", "remove"
            elif g["deletions"] > g["additions"] * 1.5 and g["deletions"] > 30:
                g["type"], hint = "refactor", "simplify"
            else:
                hint = "add" if added else "<verb>"
            has_tests = any(re.search(r"(^|/)(tests?|__tests__|spec)/|_test\.|\.test\.|\.spec\.|(^|/)test_", p) for p in g["files"])
            note = "" if has_tests else "no tests in this group — add or justify"
        else:
            hint = {"dependencies": "bump", "ci": "update", "config": "update", "docs": "update", "generated": "regenerate", "migration": "add", "tests": "add"}.get(g["kind"], "update")
            note = ""
        scope = f"({g['scope']})" if g["scope"] else ""
        header = f"{g['type']}{scope}: {hint} <what>"
        if g["kind"] == "dependencies":
            header = f"build(deps): bump <package> to <version>"
        elif g["kind"] == "docs":
            header = "docs: " + ("update " + ", ".join(p.rsplit("/", 1)[-1] for p in g["files"][:2]) if g["files"] else "update docs")
        elif g["kind"] == "generated":
            header = "chore: regenerate " + ", ".join(p.rsplit("/", 1)[-1] for p in g["files"][:2])
        out.append({
            "n": len(out) + 1, "kind": g["kind"], "suggested_header": header, "files": g["files"], "additions": g["additions"], "deletions": g["deletions"],
            "size": g["additions"] + g["deletions"], "git": "git add " + " ".join(f'"{p}"' if " " in p else p for p in g["files"]) + " && git commit", "note": note,
        })
    total = sum(g["size"] for g in out)
    if len(out) == 1:
        verdict = "One logical change — a single commit is right."
    else:
        verdict = f"{len(out)} commits suggested from {len(files)} files ({total} lines): " + "; ".join(g["suggested_header"].split(":")[0] for g in out) + "."
    if any(g["kind"] == "source" and g["size"] > 400 for g in out):
        verdict += " A source group exceeds 400 lines — consider splitting it by feature vs refactor."
    return {"commits": out, "files": len(files), "changed_lines": total, "verdict": verdict}
