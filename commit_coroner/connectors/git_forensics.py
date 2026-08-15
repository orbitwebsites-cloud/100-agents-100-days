"""Git forensics connector — the real integration, always live.

No API key needed: it shells out to the actual `git` binary against the repo
already on disk. This is what makes Commit Coroner more than a chatbot with a
stack trace pasted in — it reads real commit objects, real diffs, real
authorship, from real history, and hands the model the raw forensic evidence
to reason over.
"""

import subprocess

REPO_PATH = "."


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", REPO_PATH, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return f"git error: {result.stderr.strip()}"
    return result.stdout


def recent_commits_touching(file_path: str, limit: int = 8) -> str:
    """List the most recent commits that touched a file, oldest suspicion first."""
    log = _git(
        "log",
        f"-{limit}",
        "--follow",
        "--date=short",
        "--pretty=format:%H|%ad|%an|%s",
        "--",
        file_path,
    )
    if not log.strip():
        return f"No commit history found for {file_path!r} (bad path, or file is untracked)."
    lines = ["sha | date | author | subject", "-" * 60]
    lines.extend(log.strip().splitlines())
    return "\n".join(lines)


def commit_diff(sha: str, file_path: str = "") -> str:
    """Get the diff a specific commit introduced, optionally scoped to one file."""
    args = ["show", "--pretty=format:commit %H%nauthor: %an%ndate: %ad%nsubject: %s%n", sha]
    if file_path:
        args += ["--", file_path]
    diff = _git(*args)
    return diff[:6000] if diff else f"No diff found for {sha}"
