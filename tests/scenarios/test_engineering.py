"""Engineering — replayable evaluation scenarios (see evals/engineering.md).

Each test replays one realistic customer request through the agent's tools the way the
customer's AI calls them, and asserts on values checked BY HAND, against a published
reference, or with independent stdlib code in this file (which never imports `hundred`).
Inputs were written for this eval with planted defects; recall AND precision are asserted.

External references (checked 2026-09-27):
- NVD CVSS 3.1 vectors/scores via services.nvd.nist.gov/rest/json/cves/2.0 (10 vectors below).
- OWASP ReDoS page: evil regexes (a+)+, ([a-zA-Z]+)*, (a|aa)+, (a|a?)+, the ReGexLib email
  regex and the Java-classname regex.
- ByteByteGo "Design a URL shortener": 100M URLs/day → ~1160 writes/s, 11,600 reads/s,
  365 billion records / 36.5 TB over 10 years at 100 bytes; 62^n ≥ 365B → n = 7.
- Conventional Commits 1.0.0 (colon AND space required; BREAKING CHANGE / BREAKING-CHANGE /
  `!`), SemVer 2.0.0 §11 precedence, conventional-commits-filter (reverted commits dropped).
- Google SRE workbook multi-window burn-rate alerts: 14.4×/1h, 6×/6h, 1×/3d.
- oasdiff: path-parameter names are ignored when matching endpoints.
"""

from __future__ import annotations

import copy
import json
import math
import random
import re
import sqlite3
import subprocess
import sys
from collections import Counter

import pytest

from hundred import registry


def call(slug: str, tool: str, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ══ 1+2. code-reviewer / security-auditor: PR with 5 planted defects + a clean file ══════════

# synthetic credentials, split so repository secret scanners don't trip on this file
FAKE_KEY_ID = "AKIA" + "FAKEEXAMPLE00001"
FAKE_SECRET = "fAkE0SynthEtic/TESTonly" + "+NotARealKey12345"

PLANTED = f'''"""Nightly invoice export to S3 for the finance team."""

import csv
import io
import logging
from datetime import date, timedelta

import boto3
import psycopg2
import requests

log = logging.getLogger(__name__)

EXPORT_BUCKET = "acme-finance-exports"
FX_API = "https://fx.internal.acme.test/v2/rates"


def get_connection(dsn):
    return psycopg2.connect(dsn)


def s3_client():
    return boto3.client("s3", region_name="eu-west-1", aws_access_key_id="{FAKE_KEY_ID}", aws_secret_access_key="{FAKE_SECRET}")


def fetch_invoices(conn, customer_id, status="open"):
    cur = conn.cursor()
    cur.execute(f"SELECT id, customer_id, amount_cents, currency, issued_on FROM invoices WHERE customer_id = '{{customer_id}}' AND status = '{{status}}'")
    rows = cur.fetchall()
    print("fetched", len(rows), "invoices for", customer_id)
    return rows


def fx_rate(currency):
    if currency == "EUR":
        return 1.0
    resp = requests.get(FX_API, params={{"base": "EUR", "symbol": currency}}, timeout=5, verify=False)
    resp.raise_for_status()
    return float(resp.json()["rate"])


def to_eur_cents(amount_cents, currency):
    return round(amount_cents / fx_rate(currency))


def render_csv(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["invoice_id", "customer_id", "amount_eur_cents", "issued_on"])
    for inv_id, cust_id, amount_cents, currency, issued_on in rows:
        writer.writerow([inv_id, cust_id, to_eur_cents(amount_cents, currency), issued_on.isoformat()])
    return buf.getvalue()


def export_customer(conn, customer_id, day=None):
    day = day or date.today() - timedelta(days=1)
    rows = fetch_invoices(conn, customer_id)
    body = render_csv(rows)
    key = f"invoices/{{day.isoformat()}}/{{customer_id}}.csv"
    try:
        s3_client().put_object(Bucket=EXPORT_BUCKET, Key=key, Body=body.encode("utf-8"))
    except Exception:
        pass
    return key


def export_all(dsn, customer_ids):
    conn = get_connection(dsn)
    try:
        keys = []
        for cid in customer_ids:
            keys.append(export_customer(conn, cid))
        log.info("exported %d customers", len(keys))
        return keys
    finally:
        conn.close()
'''

CLEAN = '''"""Money helpers: integer minor units only, banker's rounding at the boundary."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

log = logging.getLogger(__name__)

MINOR_UNITS = {"EUR": 2, "USD": 2, "GBP": 2, "JPY": 0}


class CurrencyError(ValueError):
    """Raised for an unknown or mismatched currency."""


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if self.currency not in MINOR_UNITS:
            raise CurrencyError(f"unsupported currency {self.currency!r}")

    def __add__(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise CurrencyError(f"cannot add {other.currency} to {self.currency}")
        return Money(self.amount_minor + other.amount_minor, self.currency)


def parse_amount(text: str, currency: str) -> Money:
    """Parse a decimal string like '12.30' into minor units for the currency."""
    places = MINOR_UNITS.get(currency)
    if places is None:
        raise CurrencyError(f"unsupported currency {currency!r}")
    quant = Decimal(1).scaleb(-places)
    value = Decimal(text.strip()).quantize(quant, rounding=ROUND_HALF_EVEN)
    return Money(int(value.scaleb(places)), currency)


def fetch_invoice_total(conn, customer_id: str, currency: str) -> Money:
    """Sum open invoices for one customer with a parameterised query."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM invoices WHERE customer_id = %s AND currency = %s AND status = 'open'",
            (customer_id, currency),
        )
        (total,) = cur.fetchone()
    log.debug("total for customer computed")
    return Money(int(total), currency)
'''


def new_file_diff(files: dict[str, str]) -> str:
    out = ""
    for path, text in files.items():
        lines = text.splitlines()
        out += f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n"
        out += "".join("+" + ln + "\n" for ln in lines)
    return out


PR_DIFF = new_file_diff({"app/billing/invoice_export.py": PLANTED, "app/billing/money.py": CLEAN})
PLANTED_LINES = {i for i, ln in enumerate(PLANTED.splitlines(), 1) if re.search(r"AKIA|cur\.execute\(f|print\(|verify=False|except Exception:", ln)}


def test_planted_line_numbers_are_what_the_eval_says():
    assert PLANTED_LINES == {23, 28, 30, 37, 62}


def test_code_reviewer_finds_all_five_planted_defects_and_nothing_in_the_clean_file():
    stats = call("code-reviewer", "diff_stats", diff=PR_DIFF)
    assert (stats["files"], stats["additions"], stats["size_class"]) == (2, 128, "L")
    assert stats["source_without_tests"] is True

    out = call("code-reviewer", "scan_diff_smells", diff=PR_DIFF)
    got = {(f["line"], f["smell"]) for f in out["findings"] if f["file"].endswith("invoice_export.py")}
    assert got == {
        (23, "hardcoded credential"), (28, "sql built from string"), (30, "debug print"),
        (37, "tls verification off"), (62, "swallowed exception"),
    }  # recall 5/5, and no extra hits on the planted file
    assert [f for f in out["findings"] if f["file"].endswith("money.py")] == []  # precision on clean code
    sev = {f["line"]: f["severity"] for f in out["findings"]}
    assert sev[23] == sev[28] == sev[37] == "blocker"
    blob = json.dumps(out)
    assert FAKE_SECRET not in blob and FAKE_KEY_ID not in blob  # never echo the credential


def test_code_reviewer_verdict_on_the_written_review():
    findings = [
        {"severity": "blocker", "category": "security", "file": "app/billing/invoice_export.py", "line": 28, "message": "customer_id is interpolated into SQL, so a crafted id returns every customer's invoices", "suggestion": "bound parameters"},
        {"severity": "blocker", "category": "security", "file": "app/billing/invoice_export.py", "line": 23, "message": "AWS keys committed; anyone with repo access can use them", "suggestion": "rotate, use the instance role"},
        {"severity": "blocker", "category": "security", "file": "app/billing/invoice_export.py", "line": 37, "message": "verify=False lets a MITM return a fake FX rate", "suggestion": "drop verify=False"},
        {"severity": "major", "category": "correctness", "file": "app/billing/invoice_export.py", "line": 62, "message": "S3 failures are swallowed so the job reports success when nothing was uploaded", "suggestion": "log.exception and re-raise"},
        {"severity": "praise", "category": "design", "file": "app/billing/money.py", "line": 36, "message": "integer minor units + ROUND_HALF_EVEN", "suggestion": ""},
    ]
    out = call("code-reviewer", "score_review", findings=findings)
    assert out["verdict"] == "Request changes"
    assert out["counts"] == {"blocker": 3, "major": 1, "praise": 1}


def test_security_auditor_secrets_redacted_even_when_two_share_a_line():
    out = call("security-auditor", "scan_secrets", text=PLANTED)
    assert out["count"] == 2 and out["high_confidence"] == 2
    assert {f["type"] for f in out["findings"]} == {"AWS access key id", "AWS secret access key"}
    assert all(f["line"] == 23 for f in out["findings"])
    blob = json.dumps(out)
    assert FAKE_SECRET not in blob and FAKE_KEY_ID not in blob  # was leaking via the other finding's context
    assert call("security-auditor", "scan_secrets", text=CLEAN)["count"] == 0


def test_security_auditor_lint_recall_and_precision():
    hits = call("security-auditor", "lint_risky_code", source=PLANTED)
    assert {(f["line"], f["cwe"]) for f in hits["findings"]} == {(28, "CWE-89"), (37, "CWE-295")}
    assert call("security-auditor", "lint_risky_code", source=CLEAN)["findings"] == []


NVD = [  # (CVE, source, vector, NVD-published base score)
    ("CVE-2021-44228", "nvd", "AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
    ("CVE-2014-0160", "nvd", "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N", 7.5),
    ("CVE-2022-22965", "nvd", "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
    ("CVE-2020-11022", "nvd", "AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
    ("CVE-2020-11022", "github cna", "AV:N/AC:H/PR:N/UI:R/S:C/C:H/I:L/A:N", 6.9),
    ("CVE-2019-11043", "php cna", "AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:N", 8.7),
    ("CVE-2021-3156", "nvd", "AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 7.8),
    ("CVE-2019-5736", "nvd", "AV:L/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:H", 8.6),
    ("CVE-2018-11776", "nvd", "AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H", 8.1),
    ("CVE-2021-41773", "apache cna", "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N", 7.5),
]
KEYS = ["attack_vector", "attack_complexity", "privileges_required", "user_interaction", "scope", "confidentiality", "integrity", "availability"]


@pytest.mark.parametrize("cve,src,vector,score", NVD, ids=[f"{c}-{s}" for c, s, _, _ in NVD])
def test_cvss_matches_nvd(cve, src, vector, score):
    out = call("security-auditor", "cvss_score", **dict(zip(KEYS, [p.split(":")[1] for p in vector.split("/")])))
    assert out["base_score"] == score
    assert out["vector"] == "CVSS:3.1/" + vector


def test_security_headers_realistic_curl():
    out = call("security-auditor", "check_security_headers", headers={
        "Server": "nginx/1.18.0", "Strict-Transport-Security": "max-age=86400",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https:",
        "Set-Cookie": "session=abc123; Path=/; HttpOnly", "X-Powered-By": "Express",
    })
    assert out["grade"] == "F" and out["counts"]["high"] == 2
    msgs = " ".join(f["message"] for f in out["findings"])
    for needle in ("unsafe-inline", "< 1 year", "clickjacking", "sniff content types", "no Secure", "nginx/1.18.0"):
        assert needle in msgs


# ══ 3. bug-hunter ═════════════════════════════════════════════════════════════════════════

PY_TRACE = '''Traceback (most recent call last):
  File "/srv/app/checkout/pricing.py", line 88, in price_for
    return self._cache[(sku, region)]
           ~~~~~~~~~~~^^^^^^^^^^^^^^^
KeyError: ('SKU-1042', 'eu-west')

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/srv/venv/lib/python3.11/site-packages/flask/app.py", line 1484, in full_dispatch_request
    rv = self.dispatch_request()
  File "/srv/venv/lib/python3.11/site-packages/flask/app.py", line 1469, in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)
  File "/srv/app/checkout/views.py", line 41, in create_order
    total = cart_total(cart, region=request.headers.get("X-Region"))
  File "/srv/app/checkout/cart.py", line 17, in cart_total
    return sum(pricer.price_for(line.sku, region) * line.qty for line in cart.lines)
  File "/srv/app/checkout/cart.py", line 17, in <genexpr>
    return sum(pricer.price_for(line.sku, region) * line.qty for line in cart.lines)
  File "/srv/app/checkout/pricing.py", line 91, in price_for
    price = self.repo.fetch_price(sku, region)
  File "/srv/app/checkout/repo.py", line 56, in fetch_price
    return row.amount_cents
           ^^^^^^^^^^^^^^^^
AttributeError: 'NoneType' object has no attribute 'amount_cents'
'''

JS_TRACE = """TypeError: Cannot read properties of undefined (reading 'map')
    at formatLineItems (/app/src/invoices/format.js:23:28)
    at buildInvoicePayload (/app/src/invoices/build.js:57:19)
    at async InvoiceService.send (/app/src/invoices/service.js:112:21)
    at async /app/src/routes/invoices.js:34:5
    at async Layer.handle [as handle_request] (/app/node_modules/express/lib/router/layer.js:95:5)
"""


def test_bug_hunter_python_implicit_chain_blames_the_handler_not_the_cache_miss():
    out = call("bug-hunter", "parse_stack_trace", trace=PY_TRACE)
    assert out["exception_type"] == "AttributeError"
    assert out["chain_kind"] == "implicit"
    assert out["root_cause_exception"]["type"] == "AttributeError"  # was KeyError (the handled miss)
    assert (out["blame_frame"]["file"], out["blame_frame"]["line"]) == ("/srv/app/checkout/repo.py", 56)
    assert [f["in_user_code"] for f in out["frames"]] == [True] * 5 + [False] * 2
    assert not any("fix that, not the outer one" in n for n in out["notes"])


def test_bug_hunter_explicit_chain_still_points_at_the_first_exception():
    trace = PY_TRACE.replace("During handling of the above exception, another exception occurred",
                             "The above exception was the direct cause of the following exception")
    out = call("bug-hunter", "parse_stack_trace", trace=trace)
    assert out["chain_kind"] == "explicit" and out["root_cause_exception"]["type"] == "KeyError"


def test_bug_hunter_node_async_frames():
    out = call("bug-hunter", "parse_stack_trace", trace=JS_TRACE)
    assert [(f["file"], f["line"]) for f in out["frames"]] == [
        ("/app/src/invoices/format.js", 23), ("/app/src/invoices/build.js", 57), ("/app/src/invoices/service.js", 112),
        ("/app/src/routes/invoices.js", 34), ("/app/node_modules/express/lib/router/layer.js", 95),
    ]  # 5/5 frames (was 3, one with the path mangled to "async /app/…")
    assert out["frames"][-1]["in_user_code"] is False
    assert "undefined/null" in out["hint"]


def make_incident_log() -> str:
    random.seed(7)
    lines, s = [], 14 * 3600

    def ts(x: int) -> str:
        return f"2026-09-21T{x // 3600:02d}:{x % 3600 // 60:02d}:{x % 60:02d}.{random.randint(0, 999):03d}Z"

    for _ in range(400):
        s += random.randint(0, 3)
        r = random.random()
        if s < 14 * 3600 + 120:
            lines.append(f"{ts(s)} INFO  http request_id={random.randint(10**7, 10**8)} method=POST path=/v1/orders status=201 duration_ms={random.randint(40, 90)}")
        elif s < 14 * 3600 + 130 and "deploy" not in " ".join(lines[-50:]):
            lines.append(f"{ts(s)} INFO  deploy pricing-service version=2026.09.21-3 by=ci-bot")
        elif r < 0.05:
            lines.append(f"{ts(s)} WARN  pricing cache miss sku=SKU-{random.randint(1000, 1100)} region=eu-west falling back to db")
        elif r < 0.35:
            lines.append(f"{ts(s)} ERROR http request_id={random.randint(10**7, 10**8)} method=POST path=/v1/orders status=500 error=\"AttributeError: 'NoneType' object has no attribute 'amount_cents'\"")
        else:
            lines.append(f"{ts(s)} INFO  http request_id={random.randint(10**7, 10**8)} method=POST path=/v1/orders status=201 duration_ms={random.randint(40, 90)}")
    return "\n".join(lines) + "\n"


def test_bug_hunter_log_clusters_match_independent_counts():
    logs = make_incident_log()
    lines = logs.splitlines()
    # independent ground truth
    levels = Counter(ln.split()[1] for ln in lines)
    first_err = next(i for i, ln in enumerate(lines, 1) if " ERROR " in ln)
    deploy_line = next(i for i, ln in enumerate(lines, 1) if " deploy " in ln)
    err_min = Counter(ln[:16] for ln in lines if " ERROR " in ln).most_common(1)[0]
    assert (levels["ERROR"], levels["WARN"], levels["INFO"], first_err, deploy_line) == (92, 30, 278, 80, 75)

    out = call("bug-hunter", "cluster_logs", logs=logs)
    assert out["levels"] == {"INFO": 278, "ERROR": 92, "WARN": 30}
    assert out["unique_templates"] == 4
    assert out["first_problems_in_order"][0]["line"] == first_err
    assert out["changes_before_first_problem"][-1]["line"] == deploy_line
    assert "pricing-service version=2026.09.21-3" in out["verdict"]
    assert (out["busiest_error_minute"]["minute"], out["busiest_error_minute"]["errors"]) == err_min == ("2026-09-21T14:08", 15)


def test_bug_hunter_suspects_and_bisect():
    frames = call("bug-hunter", "parse_stack_trace", trace=PY_TRACE)["frames"]
    out = call("bug-hunter", "rank_suspects", frames=frames, error_message="'NoneType' object has no attribute 'amount_cents'",
               changed_files=["db/migrations/0042_region_prices.sql", "app/checkout/repo.py", "app/checkout/pricing.py", "docs/pricing.md", "app/search/index.py"])
    assert [r["file"] for r in out["ranked"][:3]] == ["app/checkout/repo.py", "app/checkout/pricing.py", "db/migrations/0042_region_prices.sql"]
    b = call("bug-hunter", "bisect_plan", commit_count=137, minutes_per_test=4)
    assert b["steps"] == math.ceil(math.log2(137)) == 8 and b["estimated_minutes"] == 32


# ══ 4. sql-wizard ═════════════════════════════════════════════════════════════════════════

SLOW = """-- dashboard: paid German orders from 1 Sept without refunds (takes 38s on 24M orders)
SELECT o.id, o.customer_id, o.total_cents, c.email
FROM orders o
LEFT JOIN customers c ON c.id = o.customer_id
WHERE DATE(o.created_at) = '2026-09-01'
  AND o.status = 'paid'
  AND o.customer_id NOT IN (SELECT r.customer_id FROM refunds r)
  AND c.country = 'DE'
ORDER BY o.created_at DESC
LIMIT 50;"""
FIXED = ("SELECT o.id, o.customer_id, o.total_cents, c.email FROM orders o JOIN customers c ON c.id = o.customer_id AND c.country = 'DE' "
         "WHERE o.created_at >= '2026-09-01' AND o.created_at < '2026-09-02' AND o.status = 'paid' "
         "AND NOT EXISTS (SELECT 1 FROM refunds r WHERE r.customer_id = o.customer_id) ORDER BY o.created_at DESC LIMIT 50;")
SLOW2 = "select * from signups s where lower(s.email) like '%@acme.com' and extract(year from s.created_at) = 2026 and s.plan = 'pro';"


def test_sql_lint_recall_on_planted_traps():
    rules = [f["rule"] for f in call("sql-wizard", "lint_sql", sql=SLOW)["findings"]]
    assert sorted(rules) == ["left-join-cancelled", "non-sargable", "not-in-subquery"]  # 3/3, no extras
    f2 = call("sql-wizard", "lint_sql", sql=SLOW2)["findings"]
    assert sorted(f["rule"] for f in f2) == ["leading-wildcard", "non-sargable", "non-sargable", "select-star"]  # lowercase lower()/extract() caught
    assert call("sql-wizard", "lint_sql", sql=FIXED)["findings"] == []  # precision: the rewrite is clean


def test_sql_index_advice_follows_esr_and_covers_the_anti_join():
    stmts = {i["statement"] for i in call("sql-wizard", "suggest_indexes", sql=SLOW)["indexes"]}
    assert "CREATE INDEX CONCURRENTLY idx_orders_status_created_at ON orders (status, created_at);" in stmts  # not (status, customer_id, created_at)
    assert "CREATE INDEX CONCURRENTLY idx_refunds_customer_id ON refunds (customer_id);" in stmts
    fixed = call("sql-wizard", "suggest_indexes", sql=FIXED)["indexes"]
    assert len({(i["table"], tuple(i["columns"])) for i in fixed}) == len(fixed)  # no duplicates


def test_sql_claims_hold_on_a_real_engine():
    """Independent: sqlite3 shows the original returns nothing (NULL in NOT IN) and the rewrite uses the range."""
    db = sqlite3.connect(":memory:")
    db.executescript("""
    CREATE TABLE customers(id INTEGER PRIMARY KEY, email TEXT, country TEXT);
    CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INT, total_cents INT, status TEXT, created_at TEXT);
    CREATE TABLE refunds(id INTEGER PRIMARY KEY, customer_id INT);
    INSERT INTO customers VALUES (1,'a@x.de','DE'),(2,'b@x.de','DE'),(3,'c@x.fr','FR');
    INSERT INTO orders VALUES (10,1,500,'paid','2026-09-01 09:00:00'),(11,2,700,'paid','2026-09-01 10:00:00'),
                              (12,3,900,'paid','2026-09-01 11:00:00'),(13,4,100,'paid','2026-09-01 12:00:00');
    INSERT INTO refunds VALUES (100,2),(101,NULL);
    CREATE INDEX idx_orders_status_created_at ON orders(status, created_at);
    """)
    assert db.execute(SLOW).fetchall() == []
    assert db.execute(FIXED).fetchall() == [(10, 1, 500, "a@x.de")]
    plan = " ".join(r[3] for r in db.execute("EXPLAIN QUERY PLAN " + FIXED))
    assert "created_at>? AND created_at<?" in plan


# ══ 5. api-designer ═══════════════════════════════════════════════════════════════════════


def orders_spec(v2: bool) -> dict:
    order = {"type": "object", "required": ["id", "status", "total_cents", "created_at"], "properties": {
        "id": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "paid", "shipped"]},
        "total_cents": {"type": "integer"}, "currency": {"type": "string"}, "legacy_id": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"}}}
    create = {"type": "object", "required": ["customer_id", "items", "currency"], "properties": {
        "customer_id": {"type": "string"}, "currency": {"type": "string", "enum": ["EUR", "USD", "GBP"]}, "note": {"type": "string"},
        "items": {"type": "array", "items": {"type": "object", "required": ["sku", "qty"], "properties": {"sku": {"type": "string"}, "qty": {"type": "integer"}}}}}}
    err = {"description": "Problem", "content": {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}}}
    s = {"openapi": "3.0.3", "info": {"title": "Orders API", "version": "2.0.0" if v2 else "1.4.0", "description": "Create and track orders."},
         "servers": [{"url": "https://api.acme.test/v1"}], "security": [{"bearer": []}],
         "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}, "schemas": {
             "Order": copy.deepcopy(order), "CreateOrder": copy.deepcopy(create),
             "Problem": {"type": "object", "properties": {"type": {"type": "string"}, "title": {"type": "string"}, "status": {"type": "integer"}, "detail": {"type": "string"}}},
             "OrderList": {"type": "object", "properties": {"data": {"type": "array", "items": {"$ref": "#/components/schemas/Order"}}, "next_cursor": {"type": "string", "nullable": True}}}}},
         "paths": {}}
    s["paths"]["/orders"] = {
        "get": {"operationId": "listOrders", "summary": "List orders", "tags": ["orders"],
                "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}, "description": "Page size"},
                               {"name": "cursor", "in": "query", "schema": {"type": "string"}, "description": "Cursor"}],
                "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/OrderList"}}}}, "401": err}},
        "post": {"operationId": "createOrder", "summary": "Create order", "tags": ["orders"],
                 "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CreateOrder"}}}},
                 "responses": {"201": {"description": "Created", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Order"}}}}, "422": err}}}
    pid = "id" if v2 else "orderId"  # path parameter renamed in v2 — NOT a breaking change
    item = {"parameters": [{"name": pid, "in": "path", "required": True, "schema": {"type": "string"}, "description": "Order id"}],
            "get": {"operationId": "getOrder", "summary": "Get order", "tags": ["orders"],
                    "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Order"}}}}, "404": err}}}
    if not v2:
        item["delete"] = {"operationId": "cancelOrder", "summary": "Cancel order", "tags": ["orders"], "responses": {"204": {"description": "Cancelled"}, "404": err}}
    s["paths"]["/orders/{%s}" % pid] = item
    if v2:
        o = s["components"]["schemas"]["Order"]["properties"]
        del o["legacy_id"]                                                  # B1 response field removed
        o["total_cents"] = {"type": "string"}                               # B2 type change
        o["updated_at"] = {"type": "string", "format": "date-time"}         # additive
        c = s["components"]["schemas"]["CreateOrder"]
        c["properties"]["channel"] = {"type": "string"}
        c["required"].append("channel")                                     # B3 new required request field
        c["properties"]["currency"]["enum"] = ["EUR", "USD"]                # B4 request enum value removed
        s["paths"]["/orders"]["get"]["parameters"] += [
            {"name": "region", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Region"},  # B5
            {"name": "status", "in": "query", "schema": {"type": "string"}, "description": "Filter"}]                    # additive
        s["paths"]["/orders/{id}/events"] = {"get": {"operationId": "listOrderEvents", "summary": "Order events", "tags": ["orders"],
            "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "Order id"},
                           {"name": "limit", "in": "query", "schema": {"type": "integer"}, "description": "Page size"}],
            "responses": {"200": {"description": "OK"}, "404": err}}}      # additive; B6 = DELETE dropped above
    return s


def test_api_breaking_changes_recall_and_no_false_positive_on_path_param_rename():
    out = call("api-designer", "diff_breaking_changes", old_spec=json.dumps(orders_spec(False)), new_spec=json.dumps(orders_spec(True)))
    got = {(b["kind"], b["where"]) for b in out["breaking"]}
    assert got == {
        ("operation removed", "DELETE /orders/{orderId}"),                        # B6
        ("new required parameter", "GET /orders query:region"),                   # B5
        ("new required request field", "POST /orders body.channel"),              # B3
        ("request enum value removed", "POST /orders body.currency"),             # B4
        ("response field removed", "GET /orders 200.data[].legacy_id"),           # B1 ×3 operations
        ("response field removed", "GET /orders/{id} 200.legacy_id"),
        ("response field removed", "POST /orders 201.legacy_id"),
        ("response field type changed", "GET /orders 200.data[].total_cents"),    # B2 ×3 operations
        ("response field type changed", "GET /orders/{id} 200.total_cents"),
        ("response field type changed", "POST /orders 201.total_cents"),
    }
    assert not any("GET /orders/{orderId}" in b["where"] and b["kind"] == "operation removed" for b in out["breaking"])
    assert {a["where"] for a in out["additive"]} >= {"GET /orders/{id}/events", "GET /orders query:status", "GET /orders/{id} 200.updated_at"}
    assert any("path parameter renamed" in n for n in out["notes"])
    assert out["semver_bump"] == "major"


def test_api_spec_lint_spectral_parity():
    assert call("api-designer", "check_openapi", spec=json.dumps(orders_spec(True)))["score"] == 100  # precision
    bad = orders_spec(True)
    bad["paths"]["/orders/{id}"]["get"]["security"] = [{"oauth2": ["orders:read"]}]
    bad["components"]["schemas"]["Order"]["properties"]["status"]["enum"] = ["pending", "paid", "paid"]
    bad["paths"]["/customers/"] = {"get": {"operationId": "listOrders", "summary": "x", "tags": ["c"], "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}, "description": "n"}], "responses": {"200": {"description": "ok"}}}}
    bad["paths"]["/search?q={q}"] = {"get": {"operationId": "search", "summary": "x", "tags": ["s"], "responses": {"200": {"description": "ok"}}}}
    bad["paths"]["/orders/{id}/events"]["get"].pop("tags")
    msgs = " | ".join(f"{i['where']}: {i['message']}" for i in call("api-designer", "check_openapi", spec=json.dumps(bad))["issues"])
    for needle in ("'oauth2' is not defined", "duplicated entries", "ends with '/'", "query string in the path key", "'listOrders' used 2 times", "no tags"):
        assert needle in msgs  # 6/6 planted (Spectral: oas3-operation-security-defined, duplicated-entry-in-enum, …)


# ══ 6. commit-crafter ═════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("message,valid,bump", [
    ("feat:add login", False, "minor"),                          # spec: colon AND space required
    ("Fixed the bug.", False, "none"),
    ("feat(api)!: drop v1 order endpoints\n\nv1 leaked internal ids because it predates the id mapper.\n\nBREAKING CHANGE: /v1/orders is gone; use /v2/orders.", True, "major"),
    ("fix(auth): reject expired refresh tokens\n\nPreviously the clock-skew window was applied twice.", True, "patch"),
    ("chore: drop node 18\n\nBREAKING-CHANGE: node 18 is no longer supported", True, "major"),  # BREAKING-CHANGE synonym
])
def test_commit_lint_follows_conventional_commits(message, valid, bump):
    out = call("commit-crafter", "lint_commit", message=message)
    assert out["valid"] is valid and out["implied_bump"] == bump


@pytest.mark.parametrize("current,bump,pid,expected", [
    ("1.9.3", "major", "", "2.0.0"), ("0.9.4", "major", "", "0.10.0"), ("1.0.0-beta.9", "prerelease", "", "1.0.0-beta.10"),
    ("1.0.0-rc.1", "release", "", "1.0.0"), ("1.9.3", "premajor", "rc", "2.0.0-rc.0"), ("2.0.0-rc.1", "major", "", "2.0.0"),
    ("1.2.3+build.5", "patch", "", "1.2.4"),
])
def test_semver_arithmetic(current, bump, pid, expected):
    assert call("commit-crafter", "semver_bump", current=current, bump=bump, prerelease_id=pid)["next"] == expected


def test_changelog_release_from_realistic_history():
    commits = [
        "a1b2c3d feat(api): add cursor pagination to GET /orders\n\nOffset pagination timed out past page 400.\n\nCloses #412",
        "b2c3d4e fix(auth): reject expired refresh tokens\n\nThe clock-skew window was applied twice.",
        "c3d4e5f perf(db): batch price lookups in cart_total",
        "d4e5f6a refactor(cart): extract Money value object",
        "e5f6a7b docs: document pagination parameters",
        "f6a7b8c chore(deps): bump psycopg to 3.2.3",
        "0a1b2c3 feat(export): stream CSV exports to S3\n\nBREAKING CHANGE: the export endpoint now returns 202 with a job URL instead of the file body.",
        "1b2c3d4 Merge pull request #420 from acme/feat/export",
        "2c3d4e5 fix: handle empty carts in checkout",
        "3c4d5e6 Updated readme",
        "4d5e6f7 feat:add region header",
        "5e6f7a8 revert: feat(api): add cursor pagination\n\nThis reverts commit a1b2c3d.",
    ]
    out = call("commit-crafter", "changelog", commits=commits, current_version="1.9.3", release_date="2026-09-27")
    assert (out["bump"], out["next_version"]) == ("major", "2.0.0")
    assert out["unparsed_commits"] == ["Updated readme", "feat:add region header"]
    md = out["markdown"]
    assert "cursor pagination" not in md.lower()  # feat + its revert cancel out (conventional-commits-filter)
    assert "### ⚠ BREAKING CHANGES" in md and "returns 202 with a job URL" in md
    assert md.count("\n- ") == 5  # 1 breaking + 1 added + 1 changed + 2 fixed


# ══ 7. incident-commander ═════════════════════════════════════════════════════════════════

EVENTS = [
    "23:41 pricing-service 2026.09.21-3 deployed to prod (canary skipped)",
    "23:47 PagerDuty alert fired: checkout 5xx > 2% for 5 min",
    "23:52 @maria acknowledged, incident declared, IC @dev",
    "00:05 status page updated: investigating elevated checkout errors",
    "00:18 traced it to missing eu-west prices in the new pricing cache",
    "00:24 rolled back pricing-service to 2026.09.21-2",
    "00:31 error rate recovering, 5xx back under 0.5%",
    "01:10 5xx at baseline for 30 min, incident resolved",
    "01:15 status page updated: resolved",
]


def minutes(a: str, b: str) -> int:
    ha, ma = map(int, a.split(":"))
    hb, mb = map(int, b.split(":"))
    return (hb * 60 + mb - ha * 60 - ma) % 1440


def test_incident_timeline_metrics_by_hand():
    out = call("incident-commander", "build_timeline", events=EVENTS, incident_date="2026-09-21")
    m = out["metrics"]
    assert m["time_to_detect_min"] == minutes("23:41", "23:47") == 6
    assert m["time_to_acknowledge_min"] == minutes("23:47", "23:52") == 5
    assert m["time_to_identify_min"] == minutes("23:47", "00:18") == 31
    assert m["time_to_mitigate_min"] == minutes("23:41", "00:24") == 43
    assert m["time_to_resolve_min"] == minutes("23:41", "01:10") == 89  # not 94: the status-page post isn't the resolution
    assert out["milestones"]["detected"] == "2026-09-21 23:47"
    assert [g["gap"] for g in out["comms_gaps"]] == ["39m"]


def test_error_budget_by_hand():
    out = call("incident-commander", "error_budget", slo_pct=99.9, window_days=30, bad_events=38480, total_events=52_000_000, elapsed_days=21)
    budget = 30 * 1440 * 0.001
    consumed = 38480 / (52_000_000 * 0.001)
    burn = consumed / (21 / 30)
    assert out["budget_minutes"] == round(budget, 2) == 43.2
    assert out["consumed_pct"] == round(100 * consumed, 1) == 74.0
    assert out["remaining_minutes"] == round(budget * (1 - consumed), 1) == 11.2
    assert out["burn_rate"] == round(burn, 2) == 1.06
    assert out["projected_exhaustion_day"] == round(30 / burn, 1) == 28.4
    assert out["status"] == "burning fast"
    assert [(a["burn_rate"], a["long_window"], a["budget_consumed_pct"]) for a in out["burn_rate_alerts"]] == [(14.4, "1h", 2), (6.0, "6h", 5), (1.0, "3d", 10)]
    t = call("incident-commander", "error_budget", slo_pct=99.95, window_days=28, downtime_minutes=13)
    assert t["budget_minutes"] == round(28 * 1440 * 0.0005, 2) and t["consumed_pct"] == round(100 * 13 / 20.16, 1)


def test_severity_rules():
    out = call("incident-commander", "grade_severity", users_affected_pct=30, core_functionality_down=True, workaround_available=False, revenue_impact_per_hour=8000)
    assert out["severity"] == "SEV1"


PM_DRAFT = """# Postmortem: Checkout errors after pricing deploy — 2026-09-21 — SEV1

## Summary
A pricing-service deploy shipped a cache that had no eu-west prices. Checkout returned 500s for about 30% of users for 43 minutes until we rolled back.

## Impact
- 30% of checkout attempts failed between 23:41 and 00:24 UTC
- 38,480 failed requests; 74% of the monthly error budget consumed
- Estimated 5,700 EUR of lost orders

## Timeline
| Time (UTC) | Event |
|---|---|
| 23:41 | pricing-service 2026.09.21-3 deployed (canary skipped) |
| 00:24 | Rolled back |

## Root cause
The root cause was human error: Maria should have checked that the cache warm-up covered every region before deploying. The warm-up job reads the region list from a config file that had not been updated because the new region was added directly in the database.

## What went well
- Rollback took 6 minutes once started.

## Action items
- Add monitoring
- Make the warm-up job read regions from the database, owner @liam, due 2026-10-10
- Block deploys that skip the canary stage — @dev
"""


def test_postmortem_audit_finds_the_planted_problems():
    out = call("incident-commander", "check_postmortem", text=PM_DRAFT)
    f = " | ".join(out["findings"])
    for needle in ('"Maria should have"', '"human error"', 'without owner: "Add monitoring"', 'vague action item: "Add monitoring"',
                   "missing section: detection", 'without due date: "Block deploys'):
        assert needle in f  # 6/6
    assert out["verdict"].startswith("Not ready")


def test_postmortem_audit_clean_draft_passes():
    clean = PM_DRAFT.split("## Root cause")[0] + """## Detection
The 5xx alert fired 6 minutes after impact began; a per-region price-miss alert would have fired within 1 minute.

## Root cause and contributing factors
The warm-up job reads regions from a config file, which went stale because regions are now added in the database. Why did it reach prod? Because the canary stage can be skipped with a flag, which meant the only eu-west check never ran. Why is the flag there? It was added for hotfixes and has no expiry.

## Response and mitigation
The on-call engineer rolled back at 00:24; the error rate recovered within 7 minutes.

## What went well / what went poorly / where we got lucky
- Rollback took 6 minutes once started.

## Action items
| # | Action | Type | Owner | Due | Priority |
|---|---|---|---|---|---|
| 1 | Warm-up job reads regions from the database | prevent | @liam | 2026-10-10 | P1 |
| 2 | Alert on price-cache misses per region above 1% | detect | @maria | 2026-10-03 | P1 |

## Lessons learned
Config that duplicates database state drifts.
"""
    out = call("incident-commander", "check_postmortem", text=clean)
    assert out["blame_flags"] == [] and out["sections_missing"] == [] and out["score"] == 100


# ══ 8. regex-builder ══════════════════════════════════════════════════════════════════════

OWASP_EVIL = [
    r"^(a+)+$", r"^([a-zA-Z]+)*$", r"^(a|aa)+$", r"^(a|a?)+$",
    r"^([a-zA-Z0-9])(([\-.]|[_]+)?([a-zA-Z0-9]+))*(@){1}[a-z0-9]+[.]{1}(([a-z]{2,3})|([a-z]{2,3}[.]{1}[a-z]{2,3}))$",  # ReGexLib email
    r"^(([a-z])+.)+[A-Z]([a-z])+$",  # Java classname
    r"^(\w+\s?)*$", r"(\d+)*x", r"^(.*,)*$",
]
SAFE = [
    r"^[a-z0-9]+$", r"^\d{3}-\d{4}$", r"^[^@\s]+@[^@\s]+\.[a-z]{2,24}$", r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$",
    r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", r"^\w+(?:\s\w+)*$", r"^[a-z]+(?:-[a-z]+)*$",
    r"^(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}$", r"^[a-z0-9]+(?:[._-][a-z0-9]+)*@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,24}$",
    r"^(?:\d{4}-\d{2}-\d{2})$",
]


@pytest.mark.parametrize("pattern", OWASP_EVIL)
def test_regex_safety_flags_every_owasp_evil_pattern(pattern):
    assert call("regex-builder", "check_regex_safety", pattern=pattern)["risk"] == "dangerous"


@pytest.mark.parametrize("pattern", SAFE)
def test_regex_safety_no_false_alarm_on_linear_patterns(pattern):
    assert call("regex-builder", "check_regex_safety", pattern=pattern)["risk"] == "safe"


def test_safe_patterns_really_are_linear():
    """Independent: run each 'safe' pattern on 20k-char adversarial input in a child interpreter with a timeout."""
    code = "import re,sys,json\nfor p in json.loads(sys.argv[1]):\n    for s in ('a'*20000+'!', '1'*20000+'x', 'a '*10000+'!'):\n        re.match(p, s)\n"
    subprocess.run([sys.executable, "-c", code, json.dumps(SAFE)], check=True, timeout=10)


def test_regex_order_id_task_end_to_end():
    pos = ["ORD-2026-000123", "ORD-2000-999999", "ORD-2099-000001"]
    neg = ["ORD-2026-00123", "ord-2026-000123", "ORD-1999-000123", "ORD-2026-000123\n", "ORD-2026-0001234", " ORD-2026-000123", "ORD-2026-٠٠٠١٢٣", ""]
    first = call("regex-builder", "test_regex", pattern=r"\AORD-20\d{2}-\d{6}\Z", should_match=pos, should_not_match=neg)
    assert first["verdict"].startswith("10/11")  # \d accepts Arabic-Indic digits — the near-miss catches it
    final = call("regex-builder", "test_regex", pattern=r"\AORD-20[0-9]{2}-[0-9]{6}\Z", should_match=pos, should_not_match=neg)
    assert final["verdict"].startswith("11/11")
    assert call("regex-builder", "convert_flavor", pattern=r"\AORD-20[0-9]{2}-[0-9]{6}\Z", target="javascript")["pattern"] == "^ORD-20[0-9]{2}-[0-9]{6}$"


# ══ 9. system-design ══════════════════════════════════════════════════════════════════════


def test_url_shortener_envelope_matches_bytebytego():
    out = call("system-design", "estimate_capacity", daily_active_users=100_000_000, actions_per_user_per_day=11, read_write_ratio=10,
               avg_record_bytes=100, retention_days=0, peak_multiplier=1, replication_factor=1, years=10)
    assert out["write_qps"]["avg"] == round(100e6 / 86400, 2) == 1157.41   # ByteByteGo rounds to 1160
    assert out["read_qps"]["avg"] == round(1e9 / 86400, 2) == 11574.07     # ByteByteGo: 11,600
    assert out["id_space"]["records_over_horizon"] == 100_000_000 * 365 * 10 == 365_000_000_000
    assert out["projection"][-1]["storage_raw_bytes"] == 365_000_000_000 * 100  # 36.5 TB
    assert out["id_space"]["base62_chars"] == 7 == next(n for n in range(1, 12) if 62**n >= 365e9)
    assert out["id_space"]["fits_int32"] is False


def test_design_calculators_by_hand():
    av = call("system-design", "availability_math", target_pct=99.9, components=[
        {"name": "LB", "availability_pct": 99.99}, {"name": "API", "availability_pct": 99.5, "redundancy": 3},
        {"name": "Redis", "availability_pct": 99.9, "redundancy": 2}, {"name": "Postgres primary", "availability_pct": 99.95}])
    comp = 0.9999 * (1 - 0.005**3) * (1 - 0.001**2) * 0.9995
    assert av["composite_pct"] == round(comp * 100, 4) and av["weakest_link"] == "Postgres primary"
    lb = call("system-design", "latency_budget", target_p99_ms=100, hops=[
        {"name": "LB", "p50_ms": 1, "p99_ms": 3}, {"name": "API", "p50_ms": 4, "p99_ms": 15},
        {"name": "Redis", "p50_ms": 1, "p99_ms": 5}, {"name": "shards", "p50_ms": 8, "p99_ms": 40, "fanout": 20}])
    assert lb["p99_upper_bound_ms"] == 63 and lb["hops"][3]["p_any_straggler_pct"] == round(100 * (1 - 0.99**20), 1) == 18.2
    fl = call("system-design", "size_fleet", peak_rps=38000, per_instance_rps=1500, target_utilization_pct=60, zones=3, n_plus=1, growth_headroom_pct=20)
    base = -(-38000 * 1.2 // (1500 * 0.6))
    assert (fl["instances_for_demand"], fl["instances_total"]) == (base, 78) == (51, 78)
    cm = call("system-design", "cache_math", request_rps=38000, hit_rate_pct=90, working_set_items=20e6, avg_item_bytes=250, ttl_seconds=86400, origin_latency_ms=20)
    assert cm["current"]["origin_rps"] == 3800 and cm["memory_bytes"] == 20e6 * 250 * 1.3


# ══ 10. test-writer ═══════════════════════════════════════════════════════════════════════

DURATIONS = '''"""Parse human durations like '1h30m', '45s', '2d' into seconds."""

import re

UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}
TOKEN = re.compile(r"(\\d+)([dhms])")


def parse_duration(text: str, max_seconds: int = 30 * 86400) -> int:
    """Return the duration in seconds. Raises ValueError on bad input or out-of-range values."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    s = text.strip().lower()
    if not s:
        raise ValueError("empty duration")
    pos, total, seen = 0, 0, set()
    for m in TOKEN.finditer(s):
        if m.start() != pos:
            raise ValueError(f"unexpected text at {pos}")
        unit = m.group(2)
        if unit in seen:
            raise ValueError(f"unit {unit} repeated")
        seen.add(unit)
        total += int(m.group(1)) * UNITS[unit]
        pos = m.end()
    if pos != len(s):
        raise ValueError(f"unexpected text at {pos}")
    if total > max_seconds:
        raise ValueError("duration too long")
    return total


def format_duration(seconds: int) -> str:
    """Inverse of parse_duration: 5400 -> '1h30m'. 0 -> '0s'."""
    if seconds < 0:
        raise ValueError("negative duration")
    if seconds == 0:
        return "0s"
    out = []
    for unit, size in UNITS.items():
        n, seconds = divmod(seconds, size)
        if n:
            out.append(f"{n}{unit}")
    return "".join(out)
'''

EXISTING_TESTS = '''import pytest

from durations import parse_duration


def test_parse_duration_hours_and_minutes():
    assert parse_duration("1h30m") == 5400


def test_parse_duration_rejects_garbage():
    with pytest.raises(ValueError):
        parse_duration("abc")


def test_parse_duration_smoke():
    parse_duration("45s")
'''


def test_test_writer_finds_planted_gaps():
    sig = call("test-writer", "extract_signatures", source=DURATIONS, module_name="durations")
    assert {f["name"]: (f["branches"], f["raises"], f["min_tests"]) for f in sig["functions"]} == {
        "parse_duration": (7, ["TypeError", "ValueError"], 10), "format_duration": (4, ["ValueError"], 6)}  # counted by hand
    g = call("test-writer", "coverage_gaps", source=DURATIONS, tests=EXISTING_TESTS)
    assert g["untested_functions"] == ["format_duration"]                              # gap 1
    assert g["tests_without_assertions"] == ["test_parse_duration_smoke"]              # gap 2
    rows = {r["function"]: r for r in g["rows"]}
    assert rows["parse_duration"]["untested_raises"] == ["TypeError"]                  # gap 3
    assert len(rows["parse_duration"]["unpinned_raise_sites"]) == 5                    # one raises(ValueError) pins none of 5 sites


def generated_tests() -> str:
    pb = registry.get("test-writer").get_tool("parametrize_block")
    b1 = pb.call({"function_name": "parse_duration", "arg_names": ["text"], "cases": [
        {"text": "1h30m", "expected": 5400}, {"text": "45s", "expected": 45}, {"text": "2d", "expected": 172800},
        {"text": "  1H ", "expected": 3600, "id": "trims-and-lowercases"}, {"text": "0s", "expected": 0}, {"text": "30d", "expected": 2592000, "id": "exactly-max"},
        {"text": "", "raises": "ValueError", "match": "empty"}, {"text": "   ", "raises": "ValueError", "match": "empty", "id": "whitespace-only"},
        {"text": "1h1h", "raises": "ValueError", "match": "repeated"}, {"text": "1h x", "raises": "ValueError", "match": "unexpected"},
        {"text": "10", "raises": "ValueError", "match": "unexpected", "id": "no-unit"}, {"text": "30d1s", "raises": "ValueError", "match": "too long", "id": "one-over-max"},
        {"text": "raw:None", "raises": "TypeError", "match": "string"}]})
    b2 = pb.call({"function_name": "format_duration", "arg_names": ["seconds"], "cases": [
        {"seconds": 5400, "expected": "1h30m"}, {"seconds": 0, "expected": "0s"}, {"seconds": 86461, "expected": "1d1m1s"},
        {"seconds": 59, "expected": "59s"}, {"seconds": -1, "raises": "ValueError", "match": "negative"}]})
    return ("import pytest\n\nfrom durations import format_duration, parse_duration\n\n\n" + b1["code"] + "\n\n\n" + b2["code"] + "\n\n\n"
            "@pytest.mark.parametrize(\"seconds\", [0, 1, 59, 60, 3599, 3600, 86399, 86400, 90061, 2592000])\n"
            "def test_format_then_parse_round_trips(seconds):\n    assert parse_duration(format_duration(seconds)) == seconds\n")


def run_pytest(tmp_path, source: str, tests: str) -> subprocess.CompletedProcess:
    (tmp_path / "durations.py").write_text(source)
    (tmp_path / "test_gen.py").write_text(tests)
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_gen.py"], cwd=tmp_path, capture_output=True, text=True, timeout=60)


def test_generated_tests_run_green_and_close_every_gap(tmp_path):
    tests = generated_tests()
    r = run_pytest(tmp_path, DURATIONS, tests)
    assert r.returncode == 0 and "28 passed" in r.stdout
    g = call("test-writer", "coverage_gaps", source=DURATIONS, tests=tests)
    assert g["untested_functions"] == [] and g["tests_without_assertions"] == []
    assert all(r_["untested_raises"] == [] and r_["unpinned_raise_sites"] == [] for r_ in g["rows"])  # parametrized raises resolved


@pytest.mark.parametrize("mutation", [
    ("if total > max_seconds", "if total >= max_seconds"),   # off-by-one on the limit
    ("if unit in seen:", "if False:"),                        # repeated-unit check deleted
    ("        if n:", "        if n or True:"),               # zero components emitted
])
def test_generated_tests_kill_mutants(tmp_path, mutation):
    mutant = DURATIONS.replace(*mutation)
    assert mutant != DURATIONS
    assert run_pytest(tmp_path, mutant, generated_tests()).returncode == 1
