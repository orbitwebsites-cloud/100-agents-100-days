"""Security Auditor — find the exploitable issue, score it properly, fix it at the root.

Tools scan for leaked secrets (redacted in output), lint code for risky
patterns mapped to CWEs, compute exact CVSS 3.1 base scores, and grade HTTP
security headers.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Literal

from ...core import Agent, ToolError
from ._common import require_text, shannon_entropy

AGENT = Agent(
    slug="security-auditor",
    name="Security Auditor",
    category="engineering",
    tagline="Audit code like an AppSec engineer: leaked secrets, injection and crypto flaws with CWE ids, exact CVSS scores, and class-closing fixes.",
    description=(
        "Performs an application-security review the way a senior AppSec engineer does: threat model "
        "first, then evidence. Scans text and code for leaked credentials (AWS, GitHub, Slack, Stripe, "
        "private keys, JWTs, connection strings, high-entropy assignments — reported redacted), lints "
        "source for risky patterns mapped to CWE ids (injection, unsafe deserialisation, weak crypto, "
        "shell execution, TLS verification off), computes exact CVSS 3.1 base scores and vector strings, "
        "and grades HTTP security headers with a ready-to-paste header set."
    ),
    triggers=[
        "security review / audit this code",
        "are there secrets or credentials in this file / repo",
        "how severe is this vulnerability / what's the CVSS score",
        "check our HTTP security headers / CSP / HSTS",
        "is this code vulnerable to injection / XSS / SSRF",
        "threat model this feature",
    ],
    examples=[
        "Review this Flask app for security issues before we open it to customers.",
        "We found an IDOR on /invoices/{id} — score it and write the ticket.",
        "Here are our response headers from curl -I — what are we missing?",
    ],
    connectors=["GitHub", "GitLab", "Snyk", "Jira", "Linear", "Slack", "Cloudflare"],
    playbook="""
    ## Standard
    You are a senior application-security engineer doing a review that will be read by the
    developers who have to fix it. Excellent means: every finding is exploitable in a way you
    can describe step by step (or is explicitly labelled a hardening item), it carries a CWE, a
    defensible severity, and a fix that closes the whole class of bug, not the one line. The
    one metric: **exploitable findings that reach production**. Second: developer time per
    finding — no noise. Not legal advice; regulatory notification questions (breach, PII) go
    to counsel.

    ## Intake
    You need the code/config/headers to review and the context that sets severity: who can
    reach it (internet, authenticated users, internal), what data it touches (PII, payments,
    secrets), and the trust boundaries. Ask at most 3 questions only when exposure is unknown
    and it flips severity; otherwise assume internet-facing with authenticated users and say so.

    ## Procedure
    1. **Threat model in five lines**: assets, entry points, trust boundaries, attacker
       capabilities (anonymous / user / admin / insider), and the top three things that must
       not happen. Everything below is prioritised by this.
    2. **Scan for secrets first** — call `security_auditor__scan_secrets` on every file, diff
       or log pasted. Any live credential is a P0 regardless of the rest: rotate now, then
       purge history (`git filter-repo`), then add a pre-commit scanner (gitleaks/trufflehog).
       The tool redacts matches; never repeat a secret in your output either.
    3. **Lint the code** with `security_auditor__lint_risky_code` (language auto-detected).
       Each hit has a CWE and a fix. Then read the code around each hit yourself: is the
       input attacker-controlled? Is there a sanitiser the linter can't see? Upgrade to
       "exploitable" only when you can trace input → sink. Downgrade to "hardening" when you
       can't, and say why.
    4. **Hunt what linters miss**, in this order (OWASP Top 10 + the common serious ones):
       broken access control (IDOR, missing authZ on new endpoints, tenant isolation), injection
       (SQL/NoSQL/command/LDAP/template), SSRF (URL fetch from user input), auth flaws (password
       reset, session fixation, JWT `alg:none`/weak secret), unsafe deserialisation, mass
       assignment, file upload (path traversal, content-type), XSS (reflected, stored, DOM),
       CSRF on state-changing GETs, security misconfiguration (debug on, CORS `*` with
       credentials, default creds), logging of secrets/PII, race conditions on money.
    5. **Check the transport/browser layer**: if headers are available, call
       `security_auditor__check_security_headers`. Paste its recommended header block into the
       fix section.
    6. **Score each finding** with `security_auditor__cvss_score` using the CVSS 3.1 metrics
       you can justify (attack vector, complexity, privileges, user interaction, scope, C/I/A).
       Report score + vector string. Business context adjusts *priority*, not the score.
    7. **Write the report** in the output format: findings ordered by severity, each with
       reproduction steps, impact, CWE, CVSS, fix (code), and a "class fix" (the pattern/
       library/lint rule that prevents recurrence). End with what you did *not* review.

    ## Frameworks
    - **CVSS 3.1** base metrics: AV (N/A/L/P), AC (L/H), PR (N/L/H), UI (N/R), S (U/C), C/I/A
      (H/L/N). Critical ≥ 9.0, High 7.0-8.9, Medium 4.0-6.9, Low 0.1-3.9.
    - **Severity sanity checks**: unauthenticated RCE/SQLi on internet-facing = Critical;
      IDOR exposing other users' PII = High (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N = 6.5, raise
      priority for PII volume); reflected XSS = Medium (6.1); missing HSTS = Low/hardening.
    - **Fix at the class**: parameterised queries (not escaping), allow-lists (not deny-lists),
      output encoding by context, `secrets` module for tokens, Argon2id/bcrypt for passwords,
      constant-time comparison, `defusedxml`, `yaml.safe_load`, `subprocess` with list args
      and no shell, SSRF allow-list + block private ranges + no redirects.
    - **Secrets hygiene**: rotate → revoke → purge history → scan in CI → short-lived creds
      (OIDC, STS) over long-lived keys.
    - **Headers baseline**: HSTS max-age ≥ 1 year + includeSubDomains; CSP with no
      `unsafe-inline` in script-src (nonces/hashes); X-Content-Type-Options nosniff;
      frame-ancestors/X-Frame-Options; Referrer-Policy strict-origin-when-cross-origin;
      Permissions-Policy; cookies Secure + HttpOnly + SameSite=Lax/Strict.

    ## Output format
    ```
    # Security review: <target> — <date>
    **Scope:** <files/endpoints> · **Exposure:** <internet/authn/internal> · **Data:** <PII/payments/…>
    **Summary:** <n> critical, <n> high, <n> medium, <n> low, <n> hardening

    ## Findings
    ### [<CRITICAL|HIGH|MEDIUM|LOW>] <title> — CWE-<n> — CVSS <score> (<vector>)
    **Where:** `file:line` / endpoint
    **Repro:** 1. … 2. … (request/payload)
    **Impact:** <what an attacker gets>
    **Fix:** ```<code>``` · **Class fix:** <pattern/lint/library>

    ## Hardening (not exploitable as found)
    - …

    ## Not reviewed / assumptions
    ```

    ## Anti-patterns
    - Reporting every linter hit as a vulnerability. Trace the input or label it hardening.
    - Severity by adjective ("very bad"). Use CVSS and show the vector.
    - "Sanitise inputs" as the fix. Name the exact mechanism (parameterised query, encoder).
    - Printing the leaked secret in the report.
    - Recommending a WAF as the fix for an injection bug.
    - Ignoring authorisation because authentication exists. Every object access needs an ownership check.
    - Closing a secrets incident after rotation without purging git history and checking access logs.
    """,
)

# ── secrets ──────────────────────────────────────────────────────────────────

SECRET_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("AWS access key id", re.compile(r"\b(AKIA|ASIA|AROA|AIDA)[0-9A-Z]{16}\b"), "high"),
    ("AWS secret access key", re.compile(r"(?i)aws[_\-\s]?secret[_\-\s]?(access[_\-\s]?)?key['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})\b"), "high"),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b"), "high"),
    ("GitLab token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), "high"),
    ("Slack token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b"), "high"),
    ("Slack webhook", re.compile(r"https://hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]{20,}"), "high"),
    ("Stripe live key", re.compile(r"\b(sk|rk)_live_[0-9A-Za-z]{20,}\b"), "high"),
    ("Stripe test key", re.compile(r"\b(sk|rk)_test_[0-9A-Za-z]{20,}\b"), "low"),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "medium"),
    ("Google OAuth client secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{20,}\b"), "high"),
    ("OpenAI key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"), "high"),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"), "high"),
    ("SendGrid key", re.compile(r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b"), "high"),
    ("Twilio key", re.compile(r"\bSK[0-9a-fA-F]{32}\b"), "medium"),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), "high"),
    ("PyPI token", re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,}\b"), "high"),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"), "medium"),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----"), "high"),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "medium"),
    ("Database connection string with password", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|mssql)://[^\s:/@]+:[^\s@]{3,}@[^\s]+"), "high"),
    ("Basic auth in URL", re.compile(r"https?://[^\s:/@]+:[^\s@]{3,}@[^\s/]+"), "medium"),
    ("Azure storage key", re.compile(r"AccountKey=[A-Za-z0-9+/=]{80,}"), "high"),
    ("Generic credential assignment", re.compile(r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key|token)\b\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]"), "medium"),
    ("Generic credential env line", re.compile(r"(?im)^\s*(?:export\s+)?([A-Z][A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|APIKEY|PRIVATE_KEY))\s*=\s*['\"]?([^'\"\s#]{8,})"), "medium"),
]
PLACEHOLDER = re.compile(r"(?i)^(x{4,}|\*{4,}|<[^>]+>|\$\{[^}]+\}|\{\{.*\}\}|your[_-]?|changeme|change[_-]?me|example|placeholder|dummy|sample|test|redacted|none|null|todo|fixme|password|secret|123456|abc123|\.\.\.|%s|\$[A-Z_]+)")


def _redact(s: str) -> str:
    keep = 4 if len(s) > 12 else 2
    return f"{s[:keep]}…({len(s)} chars)"


def find_secrets_in_line(line: str, min_entropy: float = 3.5) -> list[tuple[str, str, str]]:
    """(detector name, confidence, secret value) for every credential on one line (placeholders skipped)."""
    hits: list[tuple[str, str, str]] = []
    for name, rx, conf in SECRET_PATTERNS:
        for m in rx.finditer(line):
            secret = next((g for g in reversed(m.groups() or ()) if g and len(g) >= 8), None) if m.groups() else None
            secret = secret or m.group(0)
            c = conf
            if name.startswith("Generic"):
                val = m.group(m.lastindex or 0)
                if PLACEHOLDER.match(val) or val.lower() in ("password", "secret", "changeme"):
                    continue
                ent = shannon_entropy(val)
                if ent < min_entropy and not re.search(r"\d", val):
                    continue
                if ent < min_entropy:
                    c = "low"
                secret = val
            if any(secret == s for _, _, s in hits):
                continue
            hits.append((name, c, secret))
    return hits


def redact_line(line: str, secrets: list[str]) -> str:
    """Replace every secret value on the line (longest first) with its redacted form."""
    for s in sorted(set(secrets), key=len, reverse=True):
        line = line.replace(s, _redact(s))
    return line


@AGENT.tool
def scan_secrets(text: str, min_entropy: float = 3.5) -> dict:
    """Scan text, code, config or logs for leaked credentials (cloud keys, API tokens, private keys, JWTs, connection strings, credential assignments) and report each redacted (prefix + length) with line number, confidence and entropy — never the secret itself.

    Call on every pasted file/diff/log before anything else. Placeholders (xxxx, <token>, ${VAR}) are skipped.

    Args:
        text: The content to scan.
        min_entropy: Shannon entropy (bits/char) below which a generic credential assignment is treated as a placeholder (3.5 default).
    """
    text = require_text(text, "text", 2_000_000)
    lines = text.splitlines()
    findings = []
    seen: set[tuple[int, str]] = set()
    for ln, line in enumerate(lines, 1):
        hits = find_secrets_in_line(line, min_entropy)
        # redact *every* secret on the line in each context, not just the finding's own
        context = redact_line(line.strip(), [s for _, _, s in hits])[:160]
        for name, conf, secret in hits:
            key = (ln, secret)
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                "line": ln, "type": name, "confidence": conf, "redacted": _redact(secret), "entropy": shannon_entropy(secret),
                "context": context,
            })
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order[f["confidence"]], f["line"]))
    by_type = Counter(f["type"] for f in findings)
    high = sum(1 for f in findings if f["confidence"] == "high")
    remediation = []
    if findings:
        remediation = [
            "Treat every high-confidence hit as compromised: rotate/revoke it now, before anything else.",
            "Check the provider's access logs for use of the credential since the earliest commit that contained it.",
            "Purge it from git history (git filter-repo) and force-push; invalidate forks/caches; the old value stays burned regardless.",
            "Move secrets to a manager (Vault, AWS Secrets Manager, Doppler) and load via environment at runtime.",
            "Add gitleaks/trufflehog as a pre-commit hook and CI step to stop the next one.",
        ]
    return {
        "findings": findings[:200],
        "count": len(findings),
        "high_confidence": high,
        "by_type": dict(by_type),
        "lines_scanned": len(lines),
        "remediation": remediation,
        "verdict": (f"{len(findings)} potential secret(s) ({high} high-confidence): " + ", ".join(f"{n}× {t}" for t, n in by_type.most_common(4)) + ". Rotate first, then purge."
                    if findings else "No credentials detected. (Absence of a match is not proof — obfuscated or split secrets need a manual look.)"),
    }


# ── risky code ───────────────────────────────────────────────────────────────

RULES: dict[str, list[tuple[str, re.Pattern, str, str, str]]] = {
    "python": [
        ("eval/exec of dynamic code", re.compile(r"\b(eval|exec)\s*\("), "CWE-95", "high", "Never evaluate strings; use ast.literal_eval for data, a dispatch dict for behaviour."),
        ("pickle/marshal load", re.compile(r"\b(pickle|cPickle|marshal|shelve)\.(loads?|open)\s*\("), "CWE-502", "high", "Untrusted pickle = RCE. Use JSON or a schema-validated format; sign payloads if pickle is unavoidable."),
        ("yaml.load without SafeLoader", re.compile(r"\byaml\.load\s*\((?![^)]*(SafeLoader|safe_load|CSafeLoader))"), "CWE-502", "high", "Use yaml.safe_load()."),
        ("shell=True subprocess", re.compile(r"subprocess\.\w+\([^)]*shell\s*=\s*True"), "CWE-78", "high", "Pass a list of args with shell=False; never interpolate user input into a command string."),
        ("os.system / os.popen", re.compile(r"\bos\.(system|popen)\s*\("), "CWE-78", "high", "Use subprocess.run([...]) with a list; validate/allow-list every argument."),
        ("SQL built with string formatting", re.compile(r"\.(execute|executemany|raw|extra)\s*\(\s*(f['\"]|['\"][^'\"]*['\"]\s*(%|\+)|.*\.format\()"), "CWE-89", "high", "Use parameterised queries: cursor.execute('... WHERE id = %s', (id,)) / SQLAlchemy bound params."),
        ("SQL string concatenation", re.compile(r"(?i)['\"]\s*(SELECT|INSERT|UPDATE|DELETE|WHERE)\b[^'\"]*['\"]\s*(\+|%)\s*\w"), "CWE-89", "high", "Parameterise; never concatenate identifiers/values from input."),
        ("TLS verification disabled", re.compile(r"verify\s*=\s*False|CERT_NONE|check_hostname\s*=\s*False"), "CWE-295", "high", "Keep verification on; pin or supply the CA bundle instead."),
        ("weak hash for security use", re.compile(r"hashlib\.(md5|sha1)\s*\(|\bMD5\(|\bSHA1\("), "CWE-328", "medium", "Use SHA-256+ for integrity, Argon2id/bcrypt/scrypt for passwords, HMAC for authentication."),
        ("random for security tokens", re.compile(r"\brandom\.(random|randint|choice|choices|getrandbits|randrange)\s*\([^\n]*(token|secret|password|key|nonce|salt|otp|session)|(token|secret|password|key|nonce|salt|otp|session)[^\n]*=\s*[^\n]*\brandom\.(random|randint|choice|choices|getrandbits|randrange)\s*\("), "CWE-338", "high", "Use the secrets module (secrets.token_urlsafe) for anything security-sensitive."),
        ("debug mode on", re.compile(r"\b(debug\s*=\s*True|DEBUG\s*=\s*True|app\.run\([^)]*debug\s*=\s*True)"), "CWE-489", "medium", "Debug off in production (env-driven); Werkzeug debugger allows RCE."),
        ("bind to all interfaces", re.compile(r"['\"]0\.0\.0\.0['\"]"), "CWE-668", "low", "Bind to localhost unless the service must be reachable; put it behind the load balancer/firewall."),
        ("insecure temp file", re.compile(r"tempfile\.mktemp\s*\("), "CWE-377", "medium", "Use tempfile.NamedTemporaryFile / mkstemp."),
        ("XML parsed without defusedxml", re.compile(r"\b(xml\.etree|xml\.dom|xml\.sax|lxml\.etree)\b[^\n]*\b(parse|fromstring|XMLParser)\b"), "CWE-611", "medium", "Use defusedxml, or disable entity resolution (resolve_entities=False)."),
        ("template autoescape off / mark_safe", re.compile(r"autoescape\s*=\s*False|\bmark_safe\s*\(|\bMarkup\s*\("), "CWE-79", "medium", "Keep autoescape on; escape by context; never mark user input safe."),
        ("assert used for auth/validation", re.compile(r"^\s*assert\s+[^\n]*(auth|permission|user|admin|role|token|owner)", re.I), "CWE-617", "medium", "asserts vanish under python -O; raise explicit exceptions."),
        ("hardcoded IP/host allow", re.compile(r"ALLOWED_HOSTS\s*=\s*\[\s*['\"]\*['\"]"), "CWE-16", "medium", "List real hostnames; '*' enables Host-header attacks."),
        ("open redirect from request param", re.compile(r"redirect\s*\(\s*(request\.(args|GET|params|form|values)|flask\.request\.args)"), "CWE-601", "medium", "Validate the target against an allow-list or use relative paths only."),
        ("requests to user-supplied URL", re.compile(r"\b(requests|httpx|urllib\.request)\.(get|post|urlopen|request)\s*\(\s*(request\.|params\[|user_url|target_url|data\[|req\.)"), "CWE-918", "high", "SSRF: allow-list hosts/schemes, resolve and block private ranges, disable redirects."),
        ("logging a secret", re.compile(r"(?i)(log(ger)?\.(info|debug|warning|error)|print)\s*\([^\n]*(password|secret|token|api_key|authorization)"), "CWE-532", "medium", "Never log credentials; redact before logging."),
    ],
    "javascript": [
        ("eval / new Function", re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(|setTimeout\s*\(\s*['\"]|setInterval\s*\(\s*['\"]"), "CWE-95", "high", "Never evaluate strings; use JSON.parse for data."),
        ("innerHTML / document.write with data", re.compile(r"\.(innerHTML|outerHTML)\s*[+]?=|document\.write(ln)?\s*\(|\.insertAdjacentHTML\s*\("), "CWE-79", "high", "Use textContent, or sanitise with DOMPurify before inserting HTML."),
        ("dangerouslySetInnerHTML", re.compile(r"dangerouslySetInnerHTML"), "CWE-79", "medium", "Sanitise with DOMPurify; prefer rendering text."),
        ("child_process with string command", re.compile(r"child_process[^\n]*\.(exec|execSync)\s*\(\s*(`|['\"][^'\"]*['\"]\s*\+|\w+\s*\+)"), "CWE-78", "high", "Use execFile/spawn with an args array; never build shell strings from input."),
        ("SQL via template literal / concat", re.compile(r"\.(query|execute|raw)\s*\(\s*(`[^`]*\$\{|['\"][^'\"]*['\"]\s*\+)"), "CWE-89", "high", "Use parameterised queries ($1 / ? placeholders) or the ORM's bound parameters."),
        ("TLS verification disabled", re.compile(r"rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0"), "CWE-295", "high", "Keep certificate verification on; add the CA to the trust store."),
        ("Math.random for tokens", re.compile(r"(token|secret|password|key|nonce|salt|otp|session)[^\n]*Math\.random\s*\(|Math\.random\s*\([^\n]*(token|secret|password|key|nonce|otp)"), "CWE-338", "high", "Use crypto.randomBytes / crypto.getRandomValues."),
        ("weak hash", re.compile(r"createHash\s*\(\s*['\"](md5|sha1)['\"]"), "CWE-328", "medium", "SHA-256+ for integrity; bcrypt/argon2 for passwords."),
        ("CORS wildcard with credentials", re.compile(r"(origin\s*:\s*['\"]\*['\"][^\n]*credentials\s*:\s*true|credentials\s*:\s*true[^\n]*origin\s*:\s*['\"]\*['\"]|Access-Control-Allow-Origin['\"]?\s*,\s*['\"]\*['\"])"), "CWE-942", "medium", "Reflect an allow-list of origins; never '*' with credentials."),
        ("JWT verification disabled / none alg", re.compile(r"algorithms\s*:\s*\[[^\]]*['\"]none['\"]|jwt\.decode\s*\([^)]*\)\s*(?!.*verify)|verify\s*:\s*false"), "CWE-347", "high", "jwt.verify with an explicit algorithms allow-list; reject 'none'."),
        ("prototype pollution sink", re.compile(r"\b(merge|extend|assign|deepMerge|_\.merge)\s*\([^)]*(req\.body|req\.query|JSON\.parse)"), "CWE-1321", "medium", "Validate against a schema; use Object.create(null) or freeze prototypes; avoid recursive merge of untrusted objects."),
        ("regex from user input", re.compile(r"new\s+RegExp\s*\(\s*(req\.|params|query|input|user)"), "CWE-1333", "medium", "Escape the input or use a fixed pattern; user-controlled regexes enable ReDoS."),
        ("path from request into fs", re.compile(r"fs\.\w+\s*\([^)]*(req\.(params|query|body)|params\.|query\.)"), "CWE-22", "high", "Resolve against a base dir and verify the result stays inside it; allow-list filenames."),
        ("logging a secret", re.compile(r"(?i)console\.(log|info|debug)\s*\([^\n]*(password|secret|token|apikey|api_key|authorization)"), "CWE-532", "medium", "Never log credentials."),
    ],
    "go": [
        ("exec with shell", re.compile(r"exec\.Command\s*\(\s*['\"](sh|bash|cmd)['\"]\s*,\s*['\"]-c['\"]"), "CWE-78", "high", "Call the binary directly with separate args; no shell."),
        ("SQL via fmt.Sprintf/concat", re.compile(r"(Query|Exec|QueryRow)(Context)?\s*\(\s*(ctx\s*,\s*)?(fmt\.Sprintf\(|['\"`][^'\"`]*['\"`]\s*\+)"), "CWE-89", "high", "Use placeholders ($1/?) with args."),
        ("TLS InsecureSkipVerify", re.compile(r"InsecureSkipVerify\s*:\s*true"), "CWE-295", "high", "Remove; configure RootCAs instead."),
        ("math/rand for secrets", re.compile(r"\"math/rand\""), "CWE-338", "medium", "Use crypto/rand for tokens/keys (math/rand is fine for non-security use)."),
        ("weak hash", re.compile(r"\b(md5|sha1)\.(New|Sum)\b"), "CWE-328", "medium", "SHA-256+; bcrypt/argon2 for passwords."),
        ("template.HTML from input", re.compile(r"template\.HTML\s*\("), "CWE-79", "medium", "Let html/template escape; never wrap user data in template.HTML."),
        ("http.Get with user URL", re.compile(r"http\.(Get|Post)\s*\(\s*(r\.|req\.|url\b|userURL|input)"), "CWE-918", "high", "SSRF: allow-list hosts, block private ranges, custom Transport with no redirects."),
        ("filepath from request", re.compile(r"(os\.Open|ioutil\.ReadFile|os\.ReadFile)\s*\([^)]*(r\.URL|r\.FormValue|mux\.Vars|c\.Param)"), "CWE-22", "high", "filepath.Clean + verify prefix against base dir; allow-list."),
    ],
    "java": [
        ("Runtime.exec / ProcessBuilder with concat", re.compile(r"Runtime\.getRuntime\(\)\.exec\s*\(\s*[^)]*\+|new\s+ProcessBuilder\s*\([^)]*\+"), "CWE-78", "high", "Pass arguments as an array; validate each."),
        ("SQL via string concat", re.compile(r"(createStatement\(\)|\.executeQuery\s*\(|\.execute\s*\(|\.prepareStatement\s*\()\s*[^;]*\+\s*\w"), "CWE-89", "high", "Use PreparedStatement with ? placeholders; never concatenate."),
        ("ObjectInputStream deserialisation", re.compile(r"new\s+ObjectInputStream\s*\(|\.readObject\s*\("), "CWE-502", "high", "Avoid Java serialisation for untrusted data; use JSON with a schema, or an ObjectInputFilter allow-list."),
        ("XML without secure processing", re.compile(r"(DocumentBuilderFactory|SAXParserFactory|XMLInputFactory)\.newInstance\s*\(\)(?![\s\S]{0,300}(FEATURE_SECURE_PROCESSING|disallow-doctype-decl|setExpandEntityReferences\(false\)))"), "CWE-611", "medium", "Disable DOCTYPE/external entities: setFeature(\"http://apache.org/xml/features/disallow-doctype-decl\", true)."),
        ("TrustManager accepts all", re.compile(r"checkServerTrusted\s*\([^)]*\)\s*\{\s*\}|ALLOW_ALL_HOSTNAME_VERIFIER|setHostnameVerifier\s*\(\s*\(\w+,\s*\w+\)\s*->\s*true"), "CWE-295", "high", "Use the default trust manager; add the CA to the truststore."),
        ("weak hash / cipher", re.compile(r"getInstance\s*\(\s*['\"](MD5|SHA-?1|DES|RC4|AES/ECB[^'\"]*)['\"]"), "CWE-327", "medium", "SHA-256+, AES/GCM, bcrypt/argon2 for passwords."),
        ("java.util.Random for secrets", re.compile(r"new\s+Random\s*\(\)[^\n]*(token|secret|password|key|nonce|otp)|(token|secret|password|key|nonce|otp)[^\n]*new\s+Random\s*\("), "CWE-338", "high", "Use SecureRandom."),
        ("Spring CSRF disabled", re.compile(r"csrf\(\)\.disable\(\)|\.csrf\s*\(\s*\w+\s*->\s*\w+\.disable\(\)\)"), "CWE-352", "medium", "Keep CSRF protection for cookie-authenticated sessions."),
    ],
    "php": [
        ("eval", re.compile(r"\beval\s*\("), "CWE-95", "high", "Remove eval; use a dispatch table."),
        ("shell exec", re.compile(r"\b(system|exec|shell_exec|passthru|popen|proc_open)\s*\(|`[^`]*\$"), "CWE-78", "high", "Use escapeshellarg for each argument, or avoid shelling out."),
        ("SQL via interpolation", re.compile(r"(mysqli?_query|->query|->exec)\s*\([^)]*(\$_(GET|POST|REQUEST)|\"\s*\.\s*\$|\{\$)"), "CWE-89", "high", "Use PDO prepared statements with bound params."),
        ("unserialize of input", re.compile(r"unserialize\s*\(\s*\$_(GET|POST|REQUEST|COOKIE)"), "CWE-502", "high", "Use json_decode; never unserialize untrusted data."),
        ("include from input", re.compile(r"(include|require)(_once)?\s*\(?\s*\$_(GET|POST|REQUEST)"), "CWE-98", "high", "Map input to an allow-list of files."),
        ("echo of request data", re.compile(r"echo\s+[^;]*\$_(GET|POST|REQUEST|COOKIE)"), "CWE-79", "high", "htmlspecialchars($x, ENT_QUOTES, 'UTF-8') before output."),
        ("weak hash", re.compile(r"\b(md5|sha1)\s*\(\s*\$\w*(pass|pwd)"), "CWE-328", "high", "password_hash() / password_verify()."),
    ],
    "ruby": [
        ("eval / instance_eval / send with input", re.compile(r"\b(eval|instance_eval|class_eval|module_eval)\s*\(|\.send\s*\(\s*params"), "CWE-95", "high", "Avoid eval; use public_send with an allow-list."),
        ("shell via backticks/system with interpolation", re.compile(r"`[^`]*#\{|\b(system|exec|spawn)\s*\(\s*\"[^\"]*#\{|IO\.popen\s*\(\s*\"[^\"]*#\{"), "CWE-78", "high", "Pass separate arguments: system('cmd', arg1, arg2)."),
        ("SQL via interpolation", re.compile(r"\.(where|find_by_sql|execute|order|joins)\s*\(\s*\"[^\"]*#\{"), "CWE-89", "high", "Use placeholders: where('name = ?', name) or hash conditions."),
        ("Marshal.load / YAML.load of input", re.compile(r"Marshal\.load\s*\(|YAML\.load\s*\((?![^)]*safe)"), "CWE-502", "high", "Use JSON or YAML.safe_load."),
        ("html_safe / raw on input", re.compile(r"\.html_safe\b|\braw\s*\("), "CWE-79", "medium", "Let ERB escape; sanitise with the sanitize helper if HTML is required."),
        ("permit! mass assignment", re.compile(r"\.permit!\b"), "CWE-915", "high", "Permit an explicit list of attributes."),
        ("open redirect", re.compile(r"redirect_to\s+params\["), "CWE-601", "medium", "Validate against an allow-list or use url_for with known routes."),
    ],
    "shell": [
        ("curl | sh", re.compile(r"(curl|wget)[^|\n]*\|\s*(sudo\s+)?(ba)?sh\b"), "CWE-494", "high", "Download to a file, verify checksum/signature, then run."),
        ("chmod 777", re.compile(r"chmod\s+(-R\s+)?[0-7]?777\b"), "CWE-732", "medium", "Use the minimal mode (e.g. 750/640)."),
        ("rm -rf with variable", re.compile(r"rm\s+-rf?\s+[\"']?\$\{?\w+\}?/?\s*$|rm\s+-rf?\s+\$\w+/"), "CWE-78", "high", "Guard: set -u, quote, check the variable is non-empty and expected before deleting."),
        ("secret on command line", re.compile(r"(?i)--?(password|passwd|token|api[-_]?key)[= ]\S{6,}"), "CWE-214", "medium", "Pass secrets via env/file; command lines are visible in ps and shell history."),
        ("no set -e/-u", re.compile(r"^#!/.*(ba)?sh\s*$(?![\s\S]{0,200}set\s+-[a-z]*[eu])", re.M), "CWE-703", "low", "Start scripts with set -euo pipefail."),
        ("eval of variable", re.compile(r"\beval\s+[\"']?\$"), "CWE-78", "high", "Avoid eval; use arrays and explicit commands."),
    ],
}
GENERIC_RULES: list[tuple[str, re.Pattern, str, str, str]] = [
    ("plain http URL for download/API", re.compile(r"['\"]http://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|10\.|192\.168\.|example\.)[^'\"]+['\"]"), "CWE-319", "low", "Use https://."),
    ("TODO security note", re.compile(r"(?i)\b(TODO|FIXME|HACK)\b[^\n]*(secur|auth|sanitiz|escape|inject|xss|csrf|crypto)"), "CWE-1059", "low", "Resolve before shipping; security TODOs are findings."),
    ("private IP / internal host hardcoded", re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"), "CWE-547", "low", "Move to config; hardcoded infra details leak topology and break environments."),
]
LANG_HINTS = [
    ("python", re.compile(r"^\s*(def |import |from \w+ import|class \w+\(|if __name__|print\()", re.M)),
    ("go", re.compile(r"^\s*(package \w+|func \w+\(|import \(|:=)", re.M)),
    ("java", re.compile(r"^\s*(public|private|protected)\s+(static\s+)?(class|void|[A-Z]\w*)\s|System\.out|import java\.", re.M)),
    ("php", re.compile(r"<\?php|\$_(GET|POST|REQUEST)|->\w+\(")),
    ("ruby", re.compile(r"^\s*(def \w+|end\s*$|require ['\"]|class \w+ < )|\bputs\b", re.M)),
    ("shell", re.compile(r"^#!.*\b(ba|z)?sh\b|^\s*(fi|done|esac)\s*$|\$\{\w+\}", re.M)),
    ("javascript", re.compile(r"\b(const|let|var)\s+\w+\s*=|=>|require\(|function\s*\w*\s*\(|console\.", re.M)),
]


def _detect_language(source: str) -> str:
    scores = {lang: len(rx.findall(source)) for lang, rx in LANG_HINTS}
    # python/ruby/js overlap; weight distinctive tokens
    if re.search(r"^\s*def \w+.*:\s*$", source, re.M):
        scores["python"] += 5
    if re.search(r"^\s*end\s*$", source, re.M) and not re.search(r":\s*$", source, re.M):
        scores["ruby"] += 5
    if re.search(r"^#!.*\b(ba|z)?sh\b", source):
        scores["shell"] += 10
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] else "javascript"


@AGENT.tool
def lint_risky_code(source: str, language: Literal["auto", "python", "javascript", "typescript", "go", "java", "php", "ruby", "shell"] = "auto") -> dict:
    """Lint source for risky security patterns mapped to CWE ids — injection sinks, shell execution, unsafe deserialisation, disabled TLS verification, weak crypto/randomness, XSS sinks, SSRF, path traversal, debug flags, secret logging — with line numbers and the fix for each.

    Call after scan_secrets. Hits are candidates: trace input to sink before calling them exploitable.

    Args:
        source: The code to lint (one file or a concatenation with clear boundaries).
        language: Language of the source; "auto" detects from syntax. TypeScript uses the JavaScript rules.
    """
    source = require_text(source, "source", 500_000)
    lang = _detect_language(source) if language == "auto" else ("javascript" if language == "typescript" else language)
    rules = RULES.get(lang, []) + GENERIC_RULES
    findings = []
    lines = source.splitlines()
    for name, rx, cwe, sev, fix in rules:
        for m in rx.finditer(source):
            ln = source.count("\n", 0, m.start()) + 1
            line_text = lines[ln - 1] if ln - 1 < len(lines) else ""
            if re.match(r"^\s*(#|//|/\*|\*|--)", line_text) and name != "TODO security note":
                continue
            findings.append({"line": ln, "rule": name, "cwe": cwe, "severity": sev, "code": line_text.strip()[:160], "fix": fix})
    uniq = {}
    for f in findings:
        uniq.setdefault((f["line"], f["rule"]), f)
    findings = sorted(uniq.values(), key=lambda f: ({"high": 0, "medium": 1, "low": 2}[f["severity"]], f["line"]))
    counts = Counter(f["severity"] for f in findings)
    score = max(0, 100 - 20 * counts["high"] - 8 * counts["medium"] - 2 * counts["low"])
    return {
        "language": lang,
        "findings": findings[:300],
        "counts": dict(counts),
        "score": score,
        "lines": len(lines),
        "next_step": "For each high: trace whether the input reaches the sink from an attacker-controlled source; if yes, score it with cvss_score." if counts["high"] else "No high-severity patterns; review authorisation and business logic by hand — linters can't see those.",
        "verdict": (f"{len(findings)} pattern(s): {counts['high']} high, {counts['medium']} medium, {counts['low']} low in {len(lines)} lines of {lang}." if findings else f"No risky patterns matched in {len(lines)} lines of {lang}."),
    }


# ── CVSS 3.1 ─────────────────────────────────────────────────────────────────

AV_W = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
AC_W = {"L": 0.77, "H": 0.44}
PR_W = {"U": {"N": 0.85, "L": 0.62, "H": 0.27}, "C": {"N": 0.85, "L": 0.68, "H": 0.5}}
UI_W = {"N": 0.85, "R": 0.62}
CIA_W = {"H": 0.56, "L": 0.22, "N": 0.0}


def _roundup(x: float) -> float:
    i = round(x * 100000)
    if i % 10000 == 0:
        return i / 100000.0
    return (math.floor(i / 10000) + 1) / 10.0


@AGENT.tool
def cvss_score(
    attack_vector: Literal["N", "A", "L", "P"],
    attack_complexity: Literal["L", "H"],
    privileges_required: Literal["N", "L", "H"],
    user_interaction: Literal["N", "R"],
    scope: Literal["U", "C"],
    confidentiality: Literal["H", "L", "N"],
    integrity: Literal["H", "L", "N"],
    availability: Literal["H", "L", "N"],
) -> dict:
    """Compute the exact CVSS 3.1 base score, severity rating and vector string from the eight base metrics, with the impact/exploitability sub-scores and a plain-English reading of each choice.

    Call for every finding; report score and vector together.

    Args:
        attack_vector: N network, A adjacent, L local, P physical.
        attack_complexity: L low, H high (needs conditions beyond the attacker's control).
        privileges_required: N none, L low (basic user), H high (admin).
        user_interaction: N none, R required (a user must click/open).
        scope: U unchanged, C changed (impact crosses a security boundary, e.g. escapes a sandbox/tenant).
        confidentiality: H high, L low, N none.
        integrity: H high, L low, N none.
        availability: H high, L low, N none.
    """
    av, ac, pr, ui, s, c, i, a = attack_vector, attack_complexity, privileges_required, user_interaction, scope, confidentiality, integrity, availability
    iss = 1 - (1 - CIA_W[c]) * (1 - CIA_W[i]) * (1 - CIA_W[a])
    if s == "U":
        impact = 6.42 * iss
    else:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    exploitability = 8.22 * AV_W[av] * AC_W[ac] * PR_W[s][pr] * UI_W[ui]
    if impact <= 0:
        base = 0.0
    elif s == "U":
        base = _roundup(min(impact + exploitability, 10))
    else:
        base = _roundup(min(1.08 * (impact + exploitability), 10))
    rating = "None" if base == 0 else "Low" if base < 4 else "Medium" if base < 7 else "High" if base < 9 else "Critical"
    vector = f"CVSS:3.1/AV:{av}/AC:{ac}/PR:{pr}/UI:{ui}/S:{s}/C:{c}/I:{i}/A:{a}"
    reading = {
        "attack_vector": {"N": "reachable over the network", "A": "needs adjacent network access", "L": "needs local access", "P": "needs physical access"}[av],
        "attack_complexity": {"L": "no special conditions", "H": "needs conditions the attacker can't control (race, specific config)"}[ac],
        "privileges_required": {"N": "no account needed", "L": "a basic user account", "H": "admin privileges"}[pr],
        "user_interaction": {"N": "no victim action", "R": "a victim must act (click/open)"}[ui],
        "scope": {"U": "impact stays within the vulnerable component", "C": "impact crosses into other components/tenants"}[s],
        "impact": f"confidentiality {c}, integrity {i}, availability {a}",
    }
    priority = []
    if base >= 9:
        priority.append("Critical: fix within 24-72h; consider taking the feature offline.")
    elif base >= 7:
        priority.append("High: fix this sprint (≤ 7-14 days); interim mitigation now.")
    elif base >= 4:
        priority.append("Medium: fix within 30-90 days; batch with related work.")
    elif base > 0:
        priority.append("Low: backlog / hardening; fix opportunistically.")
    if c == "H" and pr == "N" and av == "N":
        priority.append("Unauthenticated network-reachable confidentiality loss — treat as a potential data-breach scenario; involve the incident process.")
    return {
        "base_score": base,
        "severity": rating,
        "vector": vector,
        "impact_subscore": round(impact, 2),
        "exploitability_subscore": round(exploitability, 2),
        "iss": round(iss, 4),
        "reading": reading,
        "priority_guidance": priority,
        "verdict": f"CVSS 3.1 {base} ({rating}) — {vector}",
    }


# ── security headers ─────────────────────────────────────────────────────────

RECOMMENDED = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'nonce-<random>'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; upgrade-insecure-requests",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store (for authenticated/sensitive responses)",
}


@AGENT.tool
def check_security_headers(headers: dict, is_html: bool = True) -> dict:
    """Grade HTTP response headers A-F: HSTS (max-age ≥ 1 year, includeSubDomains), CSP quality (unsafe-inline/eval, wildcards, frame-ancestors), nosniff, framing, Referrer-Policy, Permissions-Policy, cookie flags (Secure/HttpOnly/SameSite), CORS misconfiguration, and version-leaking headers — with a ready-to-paste recommended set.

    Call with the headers from `curl -sI https://host` (name → value; case-insensitive).

    Args:
        headers: Response headers as {name: value}. Multiple Set-Cookie values may be joined with a newline.
        is_html: Whether the response is an HTML page (CSP/framing/referrer rules apply); false for pure JSON APIs.
    """
    if not isinstance(headers, dict) or not headers:
        raise ToolError("headers must be a non-empty {name: value} dict.")
    if len(headers) > 200:
        raise ToolError("Too many headers (max 200).")
    h = {str(k).lower().strip(): str(v) for k, v in headers.items()}
    findings = []
    score = 100

    def add(sev: str, header: str, msg: str, fix: str, pts: int) -> None:
        nonlocal score
        findings.append({"severity": sev, "header": header, "message": msg, "fix": fix})
        score -= pts

    hsts = h.get("strict-transport-security")
    if not hsts:
        add("high", "Strict-Transport-Security", "missing — first request over http can be intercepted/downgraded", RECOMMENDED["Strict-Transport-Security"], 20)
    else:
        m = re.search(r"max-age=(\d+)", hsts)
        age = int(m.group(1)) if m else 0
        if age < 31536000:
            add("medium", "Strict-Transport-Security", f"max-age {age} < 1 year (31536000)", RECOMMENDED["Strict-Transport-Security"], 8)
        if "includesubdomains" not in hsts.lower():
            add("low", "Strict-Transport-Security", "no includeSubDomains — subdomains stay downgradeable", "add includeSubDomains (after checking all subdomains serve HTTPS)", 3)
    csp = h.get("content-security-policy")
    if is_html:
        if not csp:
            add("high", "Content-Security-Policy", "missing — no defence-in-depth against XSS/injection", RECOMMENDED["Content-Security-Policy"], 20)
        else:
            low = csp.lower()
            script = re.search(r"script-src([^;]*)", low)
            script_src = script.group(1) if script else (re.search(r"default-src([^;]*)", low).group(1) if re.search(r"default-src([^;]*)", low) else "")
            if "'unsafe-inline'" in script_src and "nonce-" not in script_src and "'sha" not in script_src:
                add("high", "Content-Security-Policy", "script-src allows 'unsafe-inline' — CSP gives no XSS protection", "use nonces or hashes for inline scripts; remove 'unsafe-inline'", 15)
            if "'unsafe-eval'" in script_src:
                add("medium", "Content-Security-Policy", "script-src allows 'unsafe-eval'", "remove eval/new Function usage and drop 'unsafe-eval'", 6)
            if re.search(r"(^|\s)\*(\s|$)|https?:(\s|$)", script_src):
                add("high", "Content-Security-Policy", "script-src allows any host (* or https:) — trivially bypassed", "list specific script origins; prefer 'self' + nonces", 10)
            if "default-src" not in low:
                add("low", "Content-Security-Policy", "no default-src fallback", "add default-src 'self'", 3)
            if "object-src" not in low and "default-src 'none'" not in low:
                add("low", "Content-Security-Policy", "object-src not restricted (plugins)", "add object-src 'none'", 2)
            if "base-uri" not in low:
                add("low", "Content-Security-Policy", "base-uri not restricted (base-tag hijack of relative URLs)", "add base-uri 'self'", 2)
            if "frame-ancestors" not in low and not h.get("x-frame-options"):
                add("medium", "Content-Security-Policy", "no frame-ancestors and no X-Frame-Options — clickjacking possible", "add frame-ancestors 'none' (or 'self')", 8)
            if "report-uri" not in low and "report-to" not in low:
                add("info", "Content-Security-Policy", "no reporting endpoint — violations are invisible", "add report-to / report-uri and monitor", 0)
        if not h.get("x-frame-options") and not (csp and "frame-ancestors" in csp.lower()):
            pass  # already covered above when CSP exists; add when neither exists
        if not csp and not h.get("x-frame-options"):
            add("medium", "X-Frame-Options", "missing (and no CSP frame-ancestors) — clickjacking", "X-Frame-Options: DENY", 8)
    if (h.get("x-content-type-options") or "").lower().strip() != "nosniff":
        add("medium", "X-Content-Type-Options", "missing/invalid — browsers may sniff content types (MIME confusion XSS)", "X-Content-Type-Options: nosniff", 8)
    if is_html:
        rp = (h.get("referrer-policy") or "").lower()
        if not rp:
            add("low", "Referrer-Policy", "missing — full URLs (with tokens/ids) leak to third parties", "Referrer-Policy: strict-origin-when-cross-origin", 5)
        elif rp in ("unsafe-url", "no-referrer-when-downgrade", "origin-when-cross-origin"):
            add("low", "Referrer-Policy", f"'{rp}' leaks path/query cross-origin", "strict-origin-when-cross-origin or no-referrer", 3)
        if not h.get("permissions-policy") and not h.get("feature-policy"):
            add("low", "Permissions-Policy", "missing — powerful features (camera, geolocation) not restricted", RECOMMENDED["Permissions-Policy"], 4)
    cookies = h.get("set-cookie", "")
    for ck in [c for c in re.split(r"\n|(?<!\d),\s*(?=[\w-]+=)", cookies) if "=" in c]:
        name = ck.split("=", 1)[0].strip()
        lowck = ck.lower()
        issues = []
        if "secure" not in lowck:
            issues.append("no Secure")
        if "httponly" not in lowck and not re.search(r"(csrf|xsrf|_token|lang|theme|consent)", name, re.I):
            issues.append("no HttpOnly")
        if "samesite" not in lowck:
            issues.append("no SameSite (defaults to Lax in modern browsers; set explicitly)")
        elif "samesite=none" in lowck and "secure" not in lowck:
            issues.append("SameSite=None requires Secure")
        if issues:
            add("medium" if "no Secure" in issues or "no HttpOnly" in issues else "low", "Set-Cookie", f"cookie '{name}': " + ", ".join(issues), f"Set-Cookie: {name}=…; Secure; HttpOnly; SameSite=Lax", 6 if "no Secure" in issues or "no HttpOnly" in issues else 2)
    acao = h.get("access-control-allow-origin")
    acac = (h.get("access-control-allow-credentials") or "").lower()
    if acao == "*" and acac == "true":
        add("high", "Access-Control-Allow-Origin", "'*' together with Allow-Credentials: true — browsers block it, but it signals a reflect-any-origin config that may leak with a specific Origin", "reflect only allow-listed origins; add Vary: Origin", 15)
    elif acao and acao not in ("*",) and "vary" in h and "origin" not in h.get("vary", "").lower():
        add("low", "Vary", "ACAO varies by origin but Vary: Origin is missing — caches may serve the wrong ACAO", "add Vary: Origin", 3)
    for leak in ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version", "x-generator"):
        val = h.get(leak)
        if val and re.search(r"\d", val):
            add("low", leak.title(), f"reveals software/version: {val[:40]}", f"remove or strip the version from {leak}", 2)
        elif val and leak != "server":
            add("info", leak.title(), f"reveals stack: {val[:40]}", f"remove {leak}", 1)
    cc = (h.get("cache-control") or "").lower()
    if not cc and "set-cookie" in h:
        add("low", "Cache-Control", "authenticated response without Cache-Control — shared caches/back button may store it", "Cache-Control: no-store", 4)
    if h.get("x-xss-protection") and h["x-xss-protection"].strip() not in ("0",):
        add("info", "X-XSS-Protection", "legacy header; modern browsers ignore it and old filters caused vulnerabilities", "X-XSS-Protection: 0 (or remove)", 0)
    if not h.get("cross-origin-opener-policy") and is_html:
        add("info", "Cross-Origin-Opener-Policy", "missing — window.opener isolation (Spectre/tabnabbing hardening)", "Cross-Origin-Opener-Policy: same-origin", 1)
    score = max(0, score)
    grade = "A+" if score >= 97 and not any(f["severity"] in ("high", "medium") for f in findings) else "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 65 else "D" if score >= 50 else "F"
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: order[f["severity"]])
    counts = Counter(f["severity"] for f in findings)
    present = {k: v[:80] for k, v in h.items() if k in ("strict-transport-security", "content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy")}
    rec = dict(RECOMMENDED)
    if not is_html:
        rec = {k: v for k, v in rec.items() if k in ("Strict-Transport-Security", "X-Content-Type-Options", "Cache-Control")} | {"Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'"}
    return {
        "grade": grade,
        "score": score,
        "counts": dict(counts),
        "findings": findings,
        "present": present,
        "recommended_headers": rec,
        "verdict": f"Grade {grade} ({score}/100): {counts['high']} high, {counts['medium']} medium, {counts['low']} low. " + (f"Fix first: {findings[0]['header']} — {findings[0]['message']}." if findings and findings[0]["severity"] in ("high", "medium") else "Solid baseline."),
    }
