"""Security Auditor tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("security-auditor")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


SECRETS = (
    'aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"\n'
    'AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n'
    'password = "changeme"\n'
    "DATABASE_URL=postgres://app:S3cr3tPassw0rd@db.internal:5432/app\n"
    'token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"\n'
    'api_key = "xxxxxxxxxxxx"\n'
    "-----BEGIN RSA PRIVATE KEY-----\n"
)


def test_scan_secrets_redacts_and_classifies():
    out = call("scan_secrets", text=SECRETS)
    assert out["count"] == 5 and out["high_confidence"] == 5
    types = [f["type"] for f in out["findings"]]
    assert types == ["AWS access key id", "AWS secret access key", "Database connection string with password", "GitHub token", "Private key block"]
    gh = next(f for f in out["findings"] if f["type"] == "GitHub token")
    assert gh["redacted"] == "ghp_…(40 chars)" and gh["line"] == 5
    joined = str(out)
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in joined
    assert "S3cr3tPassw0rd" not in joined
    assert "wJalrXUtnFEMI" not in joined
    assert out["remediation"][0].startswith("Treat every high-confidence hit")


def test_scan_secrets_clean_and_rejects_empty():
    assert call("scan_secrets", text='name = "alice"\nport = 8080')["count"] == 0
    with pytest.raises(ToolError):
        call("scan_secrets", text="")


PY = (
    "import os, subprocess, pickle, hashlib\n"
    "result = subprocess.run(cmd, shell=True)\n"
    "obj = pickle.loads(data)\n"
    'cur.execute(f"SELECT * FROM users WHERE id = {uid}")\n'
    "requests.get(url, verify=False)\n"
    "h = hashlib.md5(pw).hexdigest()\n"
    "app.run(debug=True)\n"
    "# eval(x) in a comment should be ignored\n"
)


def test_lint_risky_code_python():
    out = call("lint_risky_code", source=PY)
    assert out["language"] == "python"
    cwes = {(f["line"], f["cwe"]) for f in out["findings"]}
    assert {(2, "CWE-78"), (3, "CWE-502"), (4, "CWE-89"), (5, "CWE-295"), (6, "CWE-328"), (7, "CWE-489")} <= cwes
    assert not any(f["line"] == 8 for f in out["findings"])
    assert out["counts"]["high"] == 4


def test_lint_risky_code_javascript_autodetect():
    src = "const q = db.query(`SELECT * FROM t WHERE id = ${req.params.id}`);\nel.innerHTML = userInput;\nconst t = Math.random().toString(36); // token\n"
    out = call("lint_risky_code", source=src)
    assert out["language"] == "javascript"
    rules = {f["rule"] for f in out["findings"]}
    assert "SQL via template literal / concat" in rules and "innerHTML / document.write with data" in rules


def test_lint_risky_code_rejects_empty():
    with pytest.raises(ToolError):
        call("lint_risky_code", source="   ")


@pytest.mark.parametrize(
    "metrics,score,severity",
    [
        (("N", "L", "N", "N", "C", "H", "H", "H"), 10.0, "Critical"),  # Log4Shell
        (("N", "L", "N", "N", "U", "H", "N", "N"), 7.5, "High"),  # Heartbleed
        (("N", "L", "L", "N", "U", "H", "N", "N"), 6.5, "Medium"),  # IDOR
        (("N", "L", "N", "R", "C", "L", "L", "N"), 6.1, "Medium"),  # reflected XSS
        (("L", "L", "L", "N", "U", "H", "H", "H"), 7.8, "High"),  # local privesc
        (("L", "H", "H", "R", "U", "N", "N", "N"), 0.0, "None"),
    ],
)
def test_cvss_score_matches_published_values(metrics, score, severity):
    keys = ["attack_vector", "attack_complexity", "privileges_required", "user_interaction", "scope", "confidentiality", "integrity", "availability"]
    out = call("cvss_score", **dict(zip(keys, metrics)))
    assert out["base_score"] == score and out["severity"] == severity
    assert out["vector"].startswith("CVSS:3.1/AV:")


def test_cvss_score_rejects_bad_metric():
    with pytest.raises(ToolError):
        call("cvss_score", attack_vector="X", attack_complexity="L", privileges_required="N", user_interaction="N", scope="U", confidentiality="H", integrity="H", availability="H")


def test_check_security_headers_grades():
    weak = call("check_security_headers", headers={"Server": "nginx/1.18.0", "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'", "Set-Cookie": "session=abc; Path=/", "X-Powered-By": "Express"})
    assert weak["grade"] == "F"
    highs = [f["header"] for f in weak["findings"] if f["severity"] == "high"]
    assert highs == ["Strict-Transport-Security", "Content-Security-Policy"]
    cookie = [f for f in weak["findings"] if f["header"] == "Set-Cookie"]
    assert len(cookie) == 1 and "no Secure" in cookie[0]["message"] and "no HttpOnly" in cookie[0]["message"]
    strong = call("check_security_headers", headers={
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'nonce-abc'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; report-to csp",
        "X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin", "Permissions-Policy": "camera=()",
        "Cross-Origin-Opener-Policy": "same-origin", "Set-Cookie": "sid=1; Secure; HttpOnly; SameSite=Lax", "Cache-Control": "no-store",
    })
    assert strong["grade"] == "A+" and strong["score"] == 100


def test_check_security_headers_rejects_empty():
    with pytest.raises(ToolError):
        call("check_security_headers", headers={})


def test_scan_secrets_redacts_every_secret_on_a_shared_line():
    kid, sec = "AKIA" + "FAKEEXAMPLE00001", "fAkE0SynthEtic/TESTonly" + "+NotARealKey12345"
    line = f'boto3.client("s3", aws_access_key_id="{kid}", aws_secret_access_key="{sec}")'
    out = call("scan_secrets", text=line)
    assert out["count"] == 2
    for f in out["findings"]:  # each context used to leak the *other* secret
        assert kid not in f["context"] and sec not in f["context"]


@pytest.mark.parametrize("src,lang,line", [
    ('def f(cur, uid):\n    q = f"SELECT * FROM users WHERE id = {uid}"\n    cur.execute(q)\n', "python", 2),
    ('def build(uid):\n    return "DELETE FROM t WHERE id = {}".format(uid)\n', "python", 2),
    ("const q = `SELECT * FROM users WHERE id = ${req.params.id}`;\nawait db.query(q);\n", "javascript", 1),
])
def test_lint_catches_sql_built_away_from_the_execute_call(src, lang, line):
    hits = [f for f in call("lint_risky_code", source=src, language=lang)["findings"] if f["cwe"] == "CWE-89"]
    assert [f["line"] for f in hits] == [line]


def test_lint_no_sql_false_positive_on_params_or_plain_fstrings():
    src = 'def f(cur, uid, n):\n    cur.execute("SELECT * FROM users WHERE id = %s", (uid,))\n    log.info(f"selected {n} rows from the cache")\n'
    assert call("lint_risky_code", source=src, language="python")["findings"] == []
