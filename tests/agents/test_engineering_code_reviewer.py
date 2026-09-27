"""Code Reviewer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("code-reviewer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


DIFF = """diff --git a/app/auth/login.py b/app/auth/login.py
index 1111111..2222222 100644
--- a/app/auth/login.py
+++ b/app/auth/login.py
@@ -1,4 +1,8 @@
 import os
+print("debug")
+password = "hunter2secret"
 def login(user):
-    return None
+    try:
+        return user.token
+    except Exception:
+        pass
diff --git a/tests/test_login.py b/tests/test_login.py
new file mode 100644
--- /dev/null
+++ b/tests/test_login.py
@@ -0,0 +1,3 @@
+def test_login():
+    # TODO fix me
+    assert True
"""


def test_diff_stats_counts_and_flags():
    out = call("diff_stats", diff=DIFF)
    assert out["files"] == 2
    assert out["additions"] == 9
    assert out["deletions"] == 1
    assert out["size_class"] == "S"
    assert out["by_kind"] == {"source": 1, "test": 1}
    assert out["source_without_tests"] is False
    assert any("security-sensitive" in f for f in out["risk_flags"])
    assert out["review_order"][0]["path"] == "app/auth/login.py"


def test_diff_stats_xl_verdict_and_missing_tests():
    body = "\n".join(f"+line {i}" for i in range(600))
    diff = f"--- a/src/big.py\n+++ b/src/big.py\n@@ -0,0 +1,600 @@\n{body}\n"
    out = call("diff_stats", diff=diff)
    assert out["size_class"] == "XL"
    assert out["source_without_tests"] is True
    assert "split" in out["verdict"]


def test_diff_stats_rejects_non_diff():
    with pytest.raises(ToolError):
        call("diff_stats", diff="just some prose about code")


def test_scan_diff_smells_finds_leftovers():
    out = call("scan_diff_smells", diff=DIFF)
    smells = {f["smell"] for f in out["findings"]}
    assert {"debug print", "hardcoded credential", "swallowed exception", "todo without ticket"} <= smells
    cred = next(f for f in out["findings"] if f["smell"] == "hardcoded credential")
    assert cred["file"] == "app/auth/login.py" and cred["line"] == 3
    assert out["findings"][0]["severity"] == "blocker"


def test_scan_diff_smells_rejects_empty():
    with pytest.raises(ToolError):
        call("scan_diff_smells", diff="")


SRC = '''
def simple(a, b=1):
    """ok"""
    return a + b

class K:
    def messy(self, a, b, c, d, e, f, items=[]):
        total = 0
        for i in items:
            if i > a and i < b or i == c:
                if d:
                    while e:
                        try:
                            total += i
                        except:
                            pass
                elif f:
                    total -= 1
        return total if total else None
'''


def test_python_complexity_values():
    out = call("python_complexity", source=SRC)
    assert out["module"]["functions"] == 2
    worst = out["functions"][0]
    assert worst["name"] == "K.messy"
    assert worst["complexity"] == 10  # 1 + for + if + and + or + if + while + except + elif + ifexp
    assert worst["params"] == 7
    assert worst["max_nesting"] >= 4
    assert any("mutable default" in f for f in worst["flags"])
    assert any("bare `except:`" in f for f in worst["flags"])
    assert any("swallowed" in f for f in worst["flags"])
    assert out["functions"][1]["complexity"] == 1


def test_python_complexity_rejects_syntax_error():
    with pytest.raises(ToolError):
        call("python_complexity", source="def broken(:\n  pass")


def test_score_review_verdict_and_formatting():
    out = call(
        "score_review",
        findings=[
            {"severity": "nit", "message": "rename x", "file": "a.py", "line": 3},
            {"severity": "blocker", "category": "security", "message": "SQL built by string concat breaks when input has quotes", "file": "db.py", "line": 10, "suggestion": "use parameters"},
            {"severity": "major", "message": "no test", "file": "a.py"},
        ],
    )
    assert out["verdict"] == "Request changes"
    assert out["findings"][0]["severity"] == "blocker"
    assert out["findings"][0]["formatted"].startswith("**issue (blocking):**")
    assert out["categories"] == {"security": 1, "other": 1}
    assert len(out["unactionable"]) == 2  # the major has no suggestion and no failure scenario


def test_score_review_approve_on_nits_only():
    out = call("score_review", findings=[{"severity": "nit", "message": "spacing"}] * 6)
    assert out["verdict"] == "Approve"
    assert any("nits dominate" in h for h in out["review_health"])


def test_score_review_rejects_bad_severity():
    with pytest.raises(ToolError):
        call("score_review", findings=[{"severity": "huge", "message": "x"}])


def _new_file(path, lines):
    return f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + "".join("+" + l + "\n" for l in lines)


def test_scan_diff_smells_catches_sql_formatting_tls_off_and_cloud_keys_without_echoing_them():
    key = "AKIA" + "FAKEEXAMPLE00001"
    diff = _new_file("app/export.py", [
        f'client = boto3.client("s3", aws_access_key_id="{key}")',
        "cur.execute(f\"SELECT * FROM t WHERE id = '{uid}'\")",
        'cur.execute("SELECT * FROM t WHERE id = " + uid)',
        "requests.get(url, verify=False)",
        'cur.execute("SELECT * FROM t WHERE id = %s", (uid,))',
        "ctx.check_hostname = True",
    ])
    out = call("scan_diff_smells", diff=diff)
    got = {(f["line"], f["smell"]) for f in out["findings"]}
    assert got == {(1, "hardcoded credential"), (2, "sql built from string"), (3, "sql built from string"), (4, "tls verification off")}
    assert key not in str(out)


def test_scan_diff_smells_redacts_generic_password_literal():
    out = call("scan_diff_smells", diff=_new_file("app/db.py", ['password = "Hunter2Hunter2x"']))
    assert out["findings"][0]["smell"] == "hardcoded credential"
    assert "Hunter2Hunter2x" not in str(out)
