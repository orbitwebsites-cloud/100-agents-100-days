"""API Designer — REST APIs that are consistent, evolvable and boring in the good way.

Tools lint endpoint naming and method semantics, sanity-check an OpenAPI 3
document, advise the exact status code and error body for a situation, and
diff two spec versions for breaking changes.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from ...core import Agent, ToolError
from ._common import bound_list, require_text

AGENT = Agent(
    slug="api-designer",
    name="API Designer",
    category="engineering",
    tagline="Design REST APIs clients love: consistent resource naming, correct status codes, evolvable schemas, and a spec that passes review.",
    description=(
        "Designs and reviews HTTP APIs to the standard of a platform team: resource-oriented URLs, "
        "method semantics, pagination, filtering, idempotency, versioning and error bodies (RFC 9457). "
        "Lints endpoint lists for naming and method mistakes, scores an OpenAPI 3 document for "
        "completeness, picks the exact status code and response shape for any situation, and diffs two "
        "spec versions to list every breaking change before it ships."
    ),
    triggers=[
        "design a REST API for …",
        "review my API / endpoints / OpenAPI spec",
        "what status code should I return when …",
        "is this API change breaking",
        "how should I name these endpoints / paginate / version this API",
        "write the OpenAPI spec for …",
    ],
    examples=[
        "Design the API for a bookings service: customers, slots, bookings, cancellations, webhooks.",
        "Here's our OpenAPI spec — review it before we publish v2.",
        "We're removing the `legacy_id` field and renaming /orders/{id}/ship to /shipments. Is that breaking?",
    ],
    connectors=["GitHub", "Postman", "Stoplight", "Notion", "Linear", "Jira"],
    playbook="""
    ## Standard
    You are the API platform lead who has run API reviews for hundreds of services. Excellent
    means a client developer can guess the next endpoint without reading the docs, an SDK can be
    generated from the spec with no manual fixes, and the API can evolve for years without a
    v2. The one metric: **client integration time to first successful call**, and the second:
    **breaking changes shipped per year** (target: zero without a version bump).

    ## Intake
    You need the domain (resources and their relationships) and the consumers (internal,
    partner, public — this sets versioning and error verbosity). Nice to have: existing
    endpoints or spec, auth model, expected scale. Ask at most 3 questions only when the
    resource model is genuinely unclear; otherwise assume JSON over HTTPS, OAuth2/bearer auth,
    public-ish consumers, and say so.

    ## Procedure
    1. **Model resources first.** List nouns (plural, kebab-case), their identifiers, and the
       relationships (ownership → nesting, association → link or filter). Max nesting depth of
       2 resources (`/customers/{id}/bookings`); deeper → flatten with a filter
       (`/bookings?customer_id=`). Actions that aren't CRUD become sub-resources or verbs as a
       last resort (`POST /bookings/{id}/cancel` → prefer `POST /bookings/{id}/cancellations` or
       a state field in PATCH).
    2. **Draft the endpoint list**, one line each as `METHOD /path`. Call
       `api_designer__lint_endpoints` with the list. Fix every finding (verbs in paths, singular
       nouns, camelCase, mismatched method/path, inconsistent id naming, trailing slashes,
       inconsistent versioning). Re-run until the score is ≥ 90.
    3. **Decide the cross-cutting rules** and state them once in the doc:
       - Pagination: cursor-based (`?cursor=&limit=`, response `{data, next_cursor}`) for
         anything that grows; offset only for small, static lists. Default limit 20-50, max 100-200.
       - Filtering/sorting: `?status=active&sort=-created_at`; no filters in the body of GET.
       - Idempotency: `Idempotency-Key` header on POST that creates money-like things; PUT/DELETE
         idempotent by definition.
       - Errors: RFC 9457 `application/problem+json` — `type`, `title`, `status`, `detail`,
         `instance`, plus `errors[]` for field validation.
       - Versioning: URL prefix `/v1/` for public APIs (visible, cacheable); header-based for
         internal. Additive changes never bump the version.
       - Auth: bearer tokens; 401 for missing/invalid, 403 for valid-but-not-allowed; never
         leak existence of resources across tenants (404, not 403, for other tenants' ids).
       - Timestamps ISO 8601 UTC with `Z`; ids opaque strings; money as integer minor units +
         currency; enums as lowercase strings; booleans as booleans.
    4. **Pick status codes** with `api_designer__status_code_advisor` for every non-obvious
       situation (async work, partial success, rate limits, conflicts, soft deletes). Use the
       body template it returns; do not improvise codes.
    5. **Write or review the spec.** If reviewing an OpenAPI document, call
       `api_designer__check_openapi` with the JSON (convert YAML → JSON first). Fix every
       `error`-level issue and the `warning`s that affect SDK generation (missing operationId,
       missing 4xx responses, undeclared path params, inline schemas that should be components).
    6. **Check evolvability.** If there is a previous version of the spec, call
       `api_designer__diff_breaking_changes` with old and new JSON. Any breaking change must
       either be reverted, made additive (new field, new endpoint, deprecate the old with a
       `Deprecation`/`Sunset` header), or shipped under a new version with a migration note.
    7. **Deliver** the output format: resource table, endpoint list, conventions block, error
       model, one worked example request/response, and open decisions.

    ## Frameworks
    - **Resource-oriented design** (Google AIP-121/131-135): standard methods List/Get/
      Create/Update/Delete map to GET collection / GET item / POST / PATCH / DELETE.
    - **Richardson Maturity Model**: aim for level 2 (resources + verbs + status codes);
      level 3 hypermedia only if clients will follow links.
    - **Method semantics**: GET safe+idempotent, PUT full replace idempotent, PATCH partial
      (JSON Merge Patch RFC 7386 unless you need JSON Patch), DELETE idempotent (second call
      → 204 or 404, both acceptable, pick one), POST for create/actions.
    - **Status code decision table**: 200 sync success with body · 201 created (+ `Location`) ·
      202 accepted for async (+ status URL) · 204 success no body · 304 conditional GET ·
      400 malformed · 401 unauthenticated · 403 unauthorised · 404 not found/hidden · 405
      wrong method · 409 state conflict / duplicate · 412 precondition (ETag) failed ·
      415 wrong content-type · 422 well-formed but semantically invalid · 429 rate limited
      (+ `Retry-After`) · 500 bug · 502/504 upstream · 503 maintenance/overload (+ `Retry-After`).
    - **Breaking vs additive**: removing/renaming anything, changing a type, adding a required
      request field, tightening validation, changing default behaviour, changing an error code
      clients branch on = breaking. Adding optional fields, endpoints, enum values in requests,
      or response fields = additive (document that clients must ignore unknown fields).

    ## Output format
    ```
    # <API name> — design v<n>
    **Consumers:** … · **Auth:** … · **Base URL:** https://api.example.com/v1

    ## Resources
    | Resource | Identifier | Parent | Notes |

    ## Endpoints
    | Method | Path | Purpose | Success | Notable errors |

    ## Conventions
    Pagination · Filtering/sorting · Idempotency · Versioning · Errors (problem+json) · Rate limits

    ## Error model
    ```json
    { "type": "https://api.example.com/errors/validation", "title": "…", "status": 422, "detail": "…", "errors": [ { "field": "…", "message": "…" } ] }
    ```

    ## Example
    <one request + response, realistic values>

    ## Open decisions
    - <decision> — options, recommendation
    ```
    For a review: lead with the score and the list of breaking/blocking issues, then the fixes.

    ## Anti-patterns
    - Verbs in paths (`/getUser`, `/users/{id}/delete`) — the method is the verb.
    - `200 OK` with `{"success": false}` in the body. Status codes are the contract.
    - Offset pagination on a growing collection; page 500 is slow and skips/duplicates rows.
    - Returning different shapes for the same resource from different endpoints.
    - Breaking changes disguised as "fixes" (renaming a field, making a field non-null).
    - Nesting four levels deep because the database schema is nested.
    - Inventing your own error envelope when problem+json exists.
    """,
)

# ── endpoint linting ─────────────────────────────────────────────────────────

METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
VERB_SEGMENTS = {"get", "fetch", "list", "retrieve", "create", "add", "new", "make", "update", "edit", "modify", "set", "delete", "remove", "destroy", "find", "search", "save", "insert", "put", "post", "read", "load", "do", "run", "execute", "process", "handle", "send", "check", "validate", "verify", "login", "logout", "register", "activate", "deactivate", "enable", "disable", "cancel", "approve", "reject", "submit", "start", "stop", "export", "import", "upload", "download"}
ACTION_OK = {"search", "login", "logout", "register", "cancel", "approve", "reject", "submit", "start", "stop", "export", "import", "upload", "download", "activate", "deactivate", "verify", "refresh", "batch", "bulk"}
UNCOUNTABLE = {"data", "status", "health", "info", "metadata", "config", "settings", "search", "me", "auth", "oauth", "token", "login", "logout", "feedback", "analytics", "stats", "metrics", "healthz", "readyz", "livez", "ping", "version", "docs", "openapi", "graphql", "batch", "bulk", "callback", "webhooks", "news", "series", "media", "sms", "api"}
VERB_TO_METHOD = {"get": "GET", "fetch": "GET", "list": "GET", "retrieve": "GET", "find": "GET", "read": "GET", "load": "GET", "create": "POST", "add": "POST", "new": "POST", "make": "POST", "insert": "POST", "save": "POST", "update": "PATCH", "edit": "PATCH", "modify": "PATCH", "set": "PUT", "delete": "DELETE", "remove": "DELETE", "destroy": "DELETE"}
PARAM_RE = re.compile(r"^(\{[^}]+\}|:[\w]+|<[^>]+>)$")


def _plural(word: str) -> str:
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def _is_plural(word: str) -> bool:
    return word.endswith("s") and not word.endswith("ss") or word in UNCOUNTABLE


def _kebab(seg: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", seg).replace("_", "-").lower()
    return re.sub(r"-+", "-", s)


@AGENT.tool
def lint_endpoints(endpoints: list[str]) -> dict:
    """Lint a list of "METHOD /path" endpoints for REST naming and method-semantics mistakes, with a rewritten path for each finding and a 0-100 consistency score.

    Checks verbs in paths, singular nouns, camelCase/snake_case, trailing slashes, uppercase,
    file extensions, query strings in paths, nesting depth, method/path mismatches, inconsistent
    id-parameter and version styles, and duplicates.

    Args:
        endpoints: Lines like "GET /users/{id}/orders" or "POST /v1/bookings" (max 300).
    """
    endpoints = bound_list(endpoints, "endpoints", 300)
    parsed, findings = [], []
    param_styles: Counter[str] = Counter()
    param_names: Counter[str] = Counter()
    versions: list[bool] = []
    seen: Counter[str] = Counter()
    for i, raw in enumerate(endpoints, 1):
        if not isinstance(raw, str) or not raw.strip():
            raise ToolError(f"endpoint #{i} is empty.")
        parts = raw.strip().split(None, 1)
        if len(parts) != 2 or parts[0].upper() not in METHODS:
            raise ToolError(f"endpoint #{i} must look like 'GET /path', got {raw!r}.")
        method, path = parts[0].upper(), parts[1].strip()
        if not path.startswith("/"):
            path = "/" + path
        seen[f"{method} {path.rstrip('/')}"] += 1
        parsed.append((i, method, path, raw.strip()))
    for i, method, path, raw in parsed:
        issues = []
        fixed = path
        if "?" in path:
            issues.append(("error", "query string in the path definition — query params are documented separately, not in the route"))
            fixed = fixed.split("?")[0]
        if len(fixed) > 1 and fixed.endswith("/"):
            issues.append(("warning", "trailing slash — pick one form; without is conventional"))
            fixed = fixed.rstrip("/")
        if re.search(r"\.(json|xml|html|php|aspx)$", fixed):
            issues.append(("warning", "file extension in path — use the Accept header / content negotiation"))
            fixed = re.sub(r"\.(json|xml|html|php|aspx)$", "", fixed)
        segs = [s for s in fixed.split("/") if s]
        is_ver = bool(segs) and re.fullmatch(r"v\d+", segs[0]) is not None
        versions.append(is_ver)
        resource_depth = 0
        new_segs = []
        for k, seg in enumerate(segs):
            if PARAM_RE.match(seg):
                style = "{}" if seg.startswith("{") else ":" if seg.startswith(":") else "<>"
                param_styles[style] += 1
                name = seg.strip("{}:<>")
                param_names["snake" if "_" in name else "camel" if re.search(r"[a-z][A-Z]", name) else "plain"] += 1
                if seg.startswith(":") or seg.startswith("<"):
                    seg = "{" + name + "}"
                new_segs.append(seg)
                continue
            if re.fullmatch(r"v\d+", seg):
                new_segs.append(seg)
                continue
            resource_depth += 1
            low = seg.lower()
            if seg != seg.lower():
                issues.append(("warning", f"'{seg}' has uppercase/camelCase — use lowercase kebab-case"))
            if "_" in seg:
                issues.append(("warning", f"'{seg}' uses snake_case — use kebab-case in URLs"))
            seg_k = _kebab(seg)
            words = seg_k.split("-")
            head = words[0]
            if head in VERB_SEGMENTS and head not in ACTION_OK and not (k == len(segs) - 1 and method == "POST" and head in ACTION_OK):
                mapped = VERB_TO_METHOD.get(head)
                noun = "-".join(words[1:]) or None
                msg = f"verb '{head}' in path — the HTTP method is the verb"
                if mapped and noun:
                    msg += f"; use {mapped} /{_plural(noun) if not _is_plural(noun) else noun}"
                elif mapped:
                    msg += f"; use {mapped} on the resource"
                issues.append(("error", msg))
                seg_k = noun or seg_k
                if not seg_k:
                    continue
            last_word = seg_k.split("-")[-1]
            if seg_k and last_word not in UNCOUNTABLE and last_word not in ACTION_OK and not _is_plural(last_word) and len(last_word) > 2 and seg_k not in ACTION_OK:
                issues.append(("warning", f"'{seg_k}' is singular — collections are plural nouns (/{_plural(seg_k)})"))
                seg_k = "-".join(seg_k.split("-")[:-1] + [_plural(last_word)])
            new_segs.append(seg_k)
        if resource_depth > 3:
            issues.append(("warning", f"{resource_depth} resource levels deep — flatten to ≤2-3 and filter (/bookings?customer_id=)"))
        last = segs[-1] if segs else ""
        last_is_param = bool(last) and PARAM_RE.match(last) is not None
        last_word = _kebab(last).split("-")[-1] if last else ""
        if method in ("PUT", "PATCH") and not last_is_param and last_word not in ACTION_OK and last_word not in ("me", "settings", "config", "profile"):
            issues.append(("warning", f"{method} on a collection — item updates target /…/{{id}}; bulk updates need an explicit sub-resource"))
        if method == "DELETE" and not last_is_param and last_word not in ("me",):
            issues.append(("warning", "DELETE on a collection deletes everything — usually unintended; require an id or an explicit bulk endpoint"))
        if method == "POST" and last_is_param and len(segs) >= 1:
            issues.append(("warning", "POST to an item path — POST creates in a collection; updates are PATCH/PUT; actions get a sub-resource"))
        if method == "GET" and last_word in ("create", "update", "delete", "remove", "cancel", "submit"):
            issues.append(("error", f"GET with side-effect verb '{last_word}' — GET must be safe; use POST/PATCH/DELETE"))
        if seen[f"{method} {path.rstrip('/')}"] > 1:
            issues.append(("error", "duplicate endpoint"))
        rewritten = "/" + "/".join(new_segs)
        findings.append({
            "endpoint": raw, "issues": [{"level": lvl, "message": msg} for lvl, msg in issues],
            "suggested": f"{method} {rewritten}" if rewritten != path or issues else None,
        })
    # cross-endpoint consistency
    global_issues = []
    if len(param_styles) > 1:
        global_issues.append(f"mixed path-parameter styles {dict(param_styles)} — pick one ({{id}} is OpenAPI's)")
    if len(param_names) > 1 and param_names["snake"] and param_names["camel"]:
        global_issues.append(f"mixed parameter naming ({param_names['snake']} snake_case, {param_names['camel']} camelCase)")
    if any(versions) and not all(versions):
        global_issues.append(f"{sum(versions)} of {len(versions)} paths are versioned — version all or none")
    n_err = sum(1 for f in findings for i in f["issues"] if i["level"] == "error")
    n_warn = sum(1 for f in findings for i in f["issues"] if i["level"] == "warning")
    score = max(0, 100 - 12 * n_err - 5 * n_warn - 8 * len(global_issues))
    clean = sum(1 for f in findings if not f["issues"])
    return {
        "score": score,
        "endpoints": len(findings),
        "clean": clean,
        "errors": n_err,
        "warnings": n_warn,
        "findings": findings,
        "global_issues": global_issues,
        "verdict": (f"{score}/100 — {clean}/{len(findings)} endpoints clean; {n_err} error(s), {n_warn} warning(s)"
                    + (f"; {len(global_issues)} consistency issue(s)." if global_issues else ".")),
    }


# ── status codes ─────────────────────────────────────────────────────────────

STATUS_TABLE: list[dict] = [
    {"code": 200, "keys": "success ok read fetched updated synchronous result returned list get", "when": "Synchronous success with a response body (GET, PATCH/PUT returning the resource, action results).", "headers": ["ETag / Cache-Control for GETs"], "body": "the resource or result"},
    {"code": 201, "keys": "created create new insert registered signup post", "when": "A new resource was created synchronously.", "headers": ["Location: /resources/{new-id}"], "body": "the created resource (with id, created_at)"},
    {"code": 202, "keys": "async accepted queued background job long running processing later pending export report", "when": "Request accepted; work happens asynchronously.", "headers": ["Location: /operations/{id} (status URL)", "Retry-After: <seconds> optional"], "body": '{"id": "op_…", "status": "pending", "status_url": "…"}'},
    {"code": 204, "keys": "no content deleted delete removed empty nothing to return logout", "when": "Success with nothing to return (DELETE, some PUT/PATCH).", "headers": [], "body": "none — no body allowed"},
    {"code": 206, "keys": "partial range bytes chunk resume", "when": "Range request satisfied (file downloads).", "headers": ["Content-Range"], "body": "the byte range"},
    {"code": 304, "keys": "not modified cached etag if-none-match conditional unchanged", "when": "Conditional GET; the client's cached copy is current.", "headers": ["ETag"], "body": "none"},
    {"code": 400, "keys": "malformed bad request invalid json syntax unparsable cannot parse missing required parameter wrong format", "when": "The request itself is malformed (bad JSON, wrong types, unparsable params). Use 422 for well-formed but semantically invalid input.", "headers": [], "body": "problem+json with detail"},
    {"code": 401, "keys": "unauthenticated missing token expired token invalid token not logged in no credentials authentication failed", "when": "No valid credentials. (Named 'Unauthorized' but means unauthenticated.)", "headers": ['WWW-Authenticate: Bearer realm="api"'], "body": "problem+json; never say whether the user exists"},
    {"code": 403, "keys": "forbidden permission denied not allowed insufficient scope role authorization unauthorized action", "when": "Authenticated but not permitted. For resources in another tenant prefer 404 to avoid leaking existence.", "headers": [], "body": "problem+json with the missing permission/scope"},
    {"code": 404, "keys": "not found missing does not exist unknown id other tenant hidden", "when": "Resource doesn't exist — or exists but this caller must not learn that.", "headers": [], "body": "problem+json"},
    {"code": 405, "keys": "method not allowed wrong method unsupported method", "when": "Path exists, method doesn't.", "headers": ["Allow: GET, POST"], "body": "problem+json"},
    {"code": 406, "keys": "not acceptable accept header format unsupported response format", "when": "Cannot produce a representation matching the Accept header.", "headers": [], "body": "problem+json listing supported types"},
    {"code": 408, "keys": "request timeout client slow upload", "when": "Client took too long to send the request.", "headers": ["Connection: close"], "body": "problem+json"},
    {"code": 409, "keys": "conflict duplicate already exists version mismatch state transition concurrent edit unique constraint already cancelled cannot transition", "when": "Request conflicts with current state: duplicate key, invalid state transition, optimistic-lock version mismatch.", "headers": [], "body": "problem+json with current state / conflicting id"},
    {"code": 410, "keys": "gone permanently deleted retired sunset removed endpoint", "when": "Resource or endpoint existed and is permanently gone.", "headers": ["Sunset / Deprecation on the old endpoint beforehand"], "body": "problem+json with migration hint"},
    {"code": 412, "keys": "precondition failed if-match etag stale lost update optimistic", "when": "If-Match / If-Unmodified-Since precondition not met (stale ETag).", "headers": ["ETag of current version"], "body": "problem+json"},
    {"code": 413, "keys": "payload too large body too big upload limit file size", "when": "Request body exceeds the limit.", "headers": [], "body": "problem+json with the limit"},
    {"code": 415, "keys": "unsupported media type wrong content-type not json form-data", "when": "Content-Type not supported for this endpoint.", "headers": ["Accept-Post: application/json"], "body": "problem+json"},
    {"code": 422, "keys": "validation semantic invalid field business rule out of range unprocessable email invalid date in the past negative amount required field", "when": "Well-formed request that fails validation or business rules.", "headers": [], "body": 'problem+json with errors: [{"field": "…", "message": "…", "code": "…"}]'},
    {"code": 423, "keys": "locked resource locked being edited", "when": "Resource is locked (WebDAV-origin; acceptable for explicit locks).", "headers": [], "body": "problem+json with lock owner/expiry"},
    {"code": 428, "keys": "precondition required must send if-match require etag", "when": "Server requires a conditional request (If-Match) to prevent lost updates.", "headers": [], "body": "problem+json"},
    {"code": 429, "keys": "rate limit too many requests throttle quota exceeded burst", "when": "Client exceeded rate limit or quota.", "headers": ["Retry-After: <seconds>", "RateLimit-Limit / RateLimit-Remaining / RateLimit-Reset"], "body": "problem+json with limit and reset time"},
    {"code": 500, "keys": "internal error bug crash unexpected exception unhandled", "when": "Unexpected server error (a bug). Log with a correlation id; never expose stack traces.", "headers": [], "body": 'problem+json with "instance"/correlation id only'},
    {"code": 501, "keys": "not implemented unsupported feature", "when": "Endpoint/method recognised but not implemented.", "headers": [], "body": "problem+json"},
    {"code": 502, "keys": "bad gateway upstream error dependency returned garbage invalid upstream response", "when": "Upstream service returned an invalid response.", "headers": [], "body": "problem+json; don't relay the upstream body"},
    {"code": 503, "keys": "unavailable maintenance overloaded shedding load circuit breaker open degraded down", "when": "Temporarily unable to serve (maintenance, overload, breaker open).", "headers": ["Retry-After: <seconds>"], "body": "problem+json"},
    {"code": 504, "keys": "gateway timeout upstream timed out dependency slow timeout waiting", "when": "Upstream didn't respond in time.", "headers": [], "body": "problem+json; suggest retry with backoff"},
]
PROBLEM_TEMPLATE = {"type": "https://api.example.com/errors/<slug>", "title": "<short human summary>", "status": 0, "detail": "<what went wrong for this request>", "instance": "/v1/<path>/<id> or a request id"}


@AGENT.tool
def status_code_advisor(situation: str) -> dict:
    """Pick the right HTTP status code for a described situation, with the headers to send, the RFC 9457 problem+json body template and the runner-up codes with the distinguishing rule.

    Call for every non-obvious case: async jobs, validation vs malformed, conflicts, auth vs
    permission, rate limits, upstream failures, deletes of missing resources.

    Args:
        situation: Plain-English description, e.g. "user submits a booking for a slot that was just taken by someone else".
    """
    situation = require_text(situation, "situation", 2000)
    words = set(re.findall(r"[a-z][a-z0-9-]+", situation.lower()))
    scored = []
    for row in STATUS_TABLE:
        keys = row["keys"].split()
        hits = [k for k in keys if k in words or (len(k) > 5 and any(w.startswith(k[:5]) for w in words))]
        score = len(hits) + sum(1 for k in keys if "-" in k and k in situation.lower())
        scored.append((score, row, hits))
    scored.sort(key=lambda x: -x[0])
    best_score, best, hits = scored[0]
    if best_score == 0:
        raise ToolError("Couldn't map that description to a status code. Describe what the client did and why it can't be served (e.g. 'invalid token', 'slot already booked', 'job takes minutes').")
    alternatives = [{"code": r["code"], "when": r["when"]} for s, r, _ in scored[1:4] if s > 0]
    body = dict(PROBLEM_TEMPLATE, status=best["code"])
    if best["code"] == 422:
        body["errors"] = [{"field": "<field>", "message": "<why>", "code": "<machine_code>"}]
    rules = []
    if best["code"] in (400, 422):
        rules.append("400 = cannot parse/understand the request; 422 = parsed fine, but the values fail validation or business rules.")
    if best["code"] in (401, 403):
        rules.append("401 = who are you? (missing/invalid credentials); 403 = I know who you are and the answer is no.")
    if best["code"] in (403, 404):
        rules.append("Cross-tenant ids: return 404, not 403, so callers can't enumerate other tenants' resources.")
    if best["code"] in (409, 412):
        rules.append("409 = conflicts with resource state (duplicate, illegal transition); 412 = the client's precondition header (If-Match) failed.")
    if best["code"] in (202, 201):
        rules.append("201 only when the resource exists when the response is sent; 202 when it will exist later — give a status URL.")
    if best["code"] in (502, 503, 504):
        rules.append("Clients retry 503/504 with backoff; 502 usually means a bug on the upstream — retry once at most.")
    if best["code"] >= 400:
        rules.append("Use Content-Type: application/problem+json for every error response.")
    return {
        "status": best["code"],
        "reason": best["when"],
        "matched_on": hits[:6],
        "headers": best["headers"],
        "body": body if best["code"] >= 400 else best["body"],
        "alternatives": alternatives,
        "distinguishing_rules": rules,
        "verdict": f"{best['code']} — {best['when']}",
    }


# ── openapi checks ───────────────────────────────────────────────────────────


def _load_spec(spec: str, name: str) -> dict:
    spec = require_text(spec, name, 3_000_000)
    s = spec.strip()
    if not s.startswith("{"):
        raise ToolError(f"{name} must be OpenAPI JSON (starts with '{{'). Convert YAML to JSON first (e.g. `yq -o=json`).")
    try:
        doc = json.loads(s)
    except json.JSONDecodeError as e:
        raise ToolError(f"{name} is not valid JSON: {e.msg} at line {e.lineno}.") from None
    if not isinstance(doc, dict):
        raise ToolError(f"{name} must be a JSON object.")
    return doc


def _resolve(doc: dict, node, depth: int = 0):
    if depth > 30 or not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        cur = doc
        for part in ref[2:].split("/"):
            if not isinstance(cur, dict) or part not in cur:
                return {}
            cur = cur[part]
        return _resolve(doc, cur, depth + 1)
    return node


HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


@AGENT.tool
def check_openapi(spec: str) -> dict:
    """Score an OpenAPI 3 document (JSON) for completeness and SDK-readiness: operationIds, summaries, tags, 2xx/4xx responses, declared path params, request bodies, security, component reuse, pagination on list endpoints.

    Call when reviewing or before publishing a spec. Fix every error-level issue.

    Args:
        spec: The OpenAPI document as JSON text (convert YAML first).
    """
    doc = _load_spec(spec, "spec")
    issues: list[dict] = []

    def add(level: str, where: str, msg: str) -> None:
        issues.append({"level": level, "where": where, "message": msg})

    version = str(doc.get("openapi", doc.get("swagger", "")))
    if not version.startswith("3"):
        add("error", "root", f"openapi version is {version or 'missing'} — expected 3.x (Swagger 2 is legacy for tooling).")
    info = doc.get("info") or {}
    for key in ("title", "version"):
        if not info.get(key):
            add("error", "info", f"info.{key} missing.")
    if not info.get("description"):
        add("warning", "info", "info.description missing — the first thing a client reads.")
    if not doc.get("servers"):
        add("warning", "root", "servers missing — clients can't derive the base URL.")
    paths = doc.get("paths") or {}
    if not isinstance(paths, dict) or not paths:
        add("error", "paths", "no paths defined.")
    comps = doc.get("components") or {}
    schemas = comps.get("schemas") or {}
    sec_schemes = comps.get("securitySchemes") or {}
    global_sec = doc.get("security")
    op_ids: Counter[str] = Counter()
    ops = 0
    inline_schemas = 0
    ref_count = 0
    list_ops_without_pagination = []
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        declared_in_path = set(re.findall(r"\{([^}]+)\}", path))
        path_level_params = [_resolve(doc, p) for p in item.get("parameters", []) if isinstance(p, dict)]
        for method in HTTP_METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            ops += 1
            where = f"{method.upper()} {path}"
            oid = op.get("operationId")
            if not oid:
                add("error", where, "operationId missing — SDK generators need it.")
            else:
                op_ids[oid] += 1
            if not op.get("summary") and not op.get("description"):
                add("warning", where, "no summary/description.")
            if not op.get("tags"):
                add("warning", where, "no tags — untagged operations end up in a 'default' group.")
            params = path_level_params + [_resolve(doc, p) for p in op.get("parameters", []) if isinstance(p, dict)]
            path_params = {p.get("name") for p in params if p.get("in") == "path"}
            for name in declared_in_path - path_params:
                add("error", where, f"path parameter {{{name}}} not declared in parameters.")
            for p in params:
                if p.get("in") == "path" and p.get("required") is not True:
                    add("error", where, f"path parameter '{p.get('name')}' must be required: true.")
                if not p.get("schema") and not p.get("content"):
                    add("error", where, f"parameter '{p.get('name')}' has no schema.")
                if not p.get("description"):
                    add("info", where, f"parameter '{p.get('name')}' has no description.")
            responses = op.get("responses") or {}
            codes = [str(c) for c in responses]
            if not any(c.startswith("2") for c in codes):
                add("error", where, "no 2xx response defined.")
            if not any(c.startswith("4") or c == "default" for c in codes):
                add("warning", where, "no 4xx/default error response — clients can't generate error types.")
            if method in ("post", "put", "patch") and not op.get("requestBody"):
                add("warning", where, f"{method.upper()} without requestBody.")
            if method == "post" and "201" not in codes and "202" not in codes and not path.rstrip("/").split("/")[-1].startswith("{"):
                add("info", where, "POST to a collection usually returns 201 (or 202 for async).")
            if method == "delete" and "204" not in codes and "200" not in codes and "202" not in codes:
                add("warning", where, "DELETE should define 204/200/202.")
            if method == "get" and not path.rstrip("/").endswith("}"):
                qnames = {str(p.get("name", "")).lower() for p in params if p.get("in") == "query"}
                if not qnames & {"limit", "page", "page_size", "pagesize", "cursor", "offset", "after", "before", "page_token", "pagetoken", "per_page"}:
                    list_ops_without_pagination.append(where)
            if (global_sec is None and not op.get("security")) and sec_schemes:
                add("warning", where, "no security requirement (global or per-operation).")
            for c, r in responses.items():
                r = _resolve(doc, r)
                for ctype, media in (r.get("content") or {}).items():
                    sch = media.get("schema") if isinstance(media, dict) else None
                    if isinstance(sch, dict):
                        if "$ref" in sch or (sch.get("type") == "array" and isinstance(sch.get("items"), dict) and "$ref" in sch["items"]):
                            ref_count += 1
                        elif sch.get("type") == "object" and sch.get("properties"):
                            inline_schemas += 1
                            add("info", where, f"inline object schema in response {c} — move to components.schemas for reuse and SDK type names.")
            rb = _resolve(doc, op.get("requestBody") or {})
            for ctype, media in (rb.get("content") or {}).items():
                sch = media.get("schema") if isinstance(media, dict) else None
                if isinstance(sch, dict) and "$ref" in sch:
                    ref_count += 1
                elif isinstance(sch, dict) and sch.get("properties"):
                    inline_schemas += 1
    for oid, n in op_ids.items():
        if n > 1:
            add("error", "operationId", f"'{oid}' used {n} times — must be unique.")
    if not sec_schemes and ops:
        add("warning", "components.securitySchemes", "no security schemes defined — is the API really unauthenticated?")
    if list_ops_without_pagination:
        add("warning", "pagination", f"{len(list_ops_without_pagination)} collection GET(s) without a pagination parameter: " + ", ".join(list_ops_without_pagination[:5]))
    for name, sch in schemas.items():
        sch = _resolve(doc, sch)
        if isinstance(sch, dict) and sch.get("type") == "object" and not sch.get("properties") and not sch.get("additionalProperties") and not sch.get("allOf") and not sch.get("oneOf"):
            add("warning", f"components.schemas.{name}", "object schema with no properties — clients get an untyped map.")
        if isinstance(sch, dict) and isinstance(sch.get("properties"), dict):
            for pname, prop in sch["properties"].items():
                prop = _resolve(doc, prop)
                if isinstance(prop, dict) and prop.get("type") == "string" and prop.get("format") in (None,) and re.search(r"(_at|_on|date|time)$", str(pname)):
                    add("info", f"components.schemas.{name}.{pname}", "looks like a timestamp but has no format: date-time.")
    counts = Counter(i["level"] for i in issues)
    score = max(0, 100 - 10 * counts["error"] - 4 * counts["warning"] - 1 * counts["info"])
    order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: (order[i["level"]], i["where"]))
    return {
        "score": score,
        "openapi_version": version,
        "operations": ops,
        "schemas": len(schemas),
        "schema_refs_used": ref_count,
        "inline_schemas": inline_schemas,
        "counts": dict(counts),
        "issues": issues[:300],
        "verdict": (f"{score}/100 — {ops} operations, {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info. "
                    + ("Not SDK-ready: fix the errors first." if counts["error"] else "SDK-ready once warnings are addressed." if counts["warning"] else "Publishable.")),
    }


# ── breaking changes ─────────────────────────────────────────────────────────


def _props(doc: dict, schema, depth: int = 0) -> dict:
    """Flatten a schema into {path: {type, required, enum}} following $ref/allOf, bounded depth."""
    out: dict[str, dict] = {}
    schema = _resolve(doc, schema)
    if not isinstance(schema, dict) or depth > 6:
        return out
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        return {f"[].{k}": v for k, v in _props(doc, schema["items"], depth + 1).items()}
    parts = [schema] + [_resolve(doc, s) for s in schema.get("allOf", []) if isinstance(s, dict)]
    for part in parts:
        if not isinstance(part, dict):
            continue
        required = set(part.get("required") or [])
        for name, prop in (part.get("properties") or {}).items():
            prop = _resolve(doc, prop)
            if not isinstance(prop, dict):
                continue
            out[name] = {"type": prop.get("type") or ("ref" if "$ref" in prop else "any"), "required": name in required, "enum": prop.get("enum"), "nullable": prop.get("nullable")}
            if prop.get("type") == "object" or prop.get("properties") or prop.get("allOf"):
                for sub, val in _props(doc, prop, depth + 1).items():
                    out[f"{name}.{sub}"] = val
            if prop.get("type") == "array" and isinstance(prop.get("items"), dict):
                for sub, val in _props(doc, prop["items"], depth + 1).items():
                    out[f"{name}[].{sub}"] = val
    return out


def _ops(doc: dict) -> dict[str, dict]:
    ops = {}
    for path, item in (doc.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        base_params = [_resolve(doc, p) for p in item.get("parameters", []) if isinstance(p, dict)]
        for m in HTTP_METHODS:
            op = item.get(m)
            if not isinstance(op, dict):
                continue
            params = {f"{p.get('in')}:{p.get('name')}": p for p in base_params + [_resolve(doc, p) for p in op.get("parameters", []) if isinstance(p, dict)]}
            req_schema = None
            rb = _resolve(doc, op.get("requestBody") or {})
            for media in (rb.get("content") or {}).values():
                if isinstance(media, dict) and media.get("schema") is not None:
                    req_schema = media["schema"]
                    break
            resp_schemas = {}
            for code, r in (op.get("responses") or {}).items():
                r = _resolve(doc, r)
                for media in (r.get("content") or {}).values():
                    if isinstance(media, dict) and media.get("schema") is not None:
                        resp_schemas[str(code)] = media["schema"]
                        break
            ops[f"{m.upper()} {path}"] = {"params": params, "request": req_schema, "responses": resp_schemas, "codes": {str(c) for c in (op.get("responses") or {})}, "deprecated": op.get("deprecated", False)}
    return ops


@AGENT.tool
def diff_breaking_changes(old_spec: str, new_spec: str) -> dict:
    """Diff two OpenAPI 3 documents (JSON) and list every breaking change (removed paths/operations/fields, type changes, new required inputs, removed enum values, dropped status codes) versus additive ones, with a semver verdict.

    Call before merging any spec change. Breaking changes need a version bump or a deprecation path.

    Args:
        old_spec: The currently published OpenAPI document (JSON).
        new_spec: The proposed OpenAPI document (JSON).
    """
    old, new = _load_spec(old_spec, "old_spec"), _load_spec(new_spec, "new_spec")
    o_ops, n_ops = _ops(old), _ops(new)
    breaking, additive, notes = [], [], []
    for key in sorted(set(o_ops) - set(n_ops)):
        breaking.append({"kind": "operation removed", "where": key, "detail": "clients calling it get 404/405"})
    for key in sorted(set(n_ops) - set(o_ops)):
        additive.append({"kind": "operation added", "where": key})
    for key in sorted(set(o_ops) & set(n_ops)):
        a, b = o_ops[key], n_ops[key]
        for pk, p in a["params"].items():
            if pk not in b["params"]:
                breaking.append({"kind": "parameter removed", "where": f"{key} {pk}", "detail": "requests sending it may be rejected or silently ignored"})
            else:
                q = b["params"][pk]
                if not p.get("required") and q.get("required"):
                    breaking.append({"kind": "parameter became required", "where": f"{key} {pk}", "detail": "existing requests without it now fail"})
                pt = (_resolve(new, q.get("schema") or {}) or {}).get("type")
                ot = (_resolve(old, p.get("schema") or {}) or {}).get("type")
                if ot and pt and ot != pt:
                    breaking.append({"kind": "parameter type changed", "where": f"{key} {pk}", "detail": f"{ot} → {pt}"})
        for pk, q in b["params"].items():
            if pk not in a["params"]:
                if q.get("required"):
                    breaking.append({"kind": "new required parameter", "where": f"{key} {pk}", "detail": "existing requests don't send it"})
                else:
                    additive.append({"kind": "optional parameter added", "where": f"{key} {pk}"})
        if a["request"] is not None and b["request"] is None:
            notes.append(f"{key}: request body removed — breaking if clients send one that is now rejected")
        if a["request"] is not None and b["request"] is not None:
            op_, np_ = _props(old, a["request"]), _props(new, b["request"])
            for f in sorted(set(op_) - set(np_)):
                breaking.append({"kind": "request field removed", "where": f"{key} body.{f}", "detail": "clients still sending it may be rejected (if additionalProperties: false) or silently dropped"})
            for f in sorted(set(np_) - set(op_)):
                if np_[f]["required"]:
                    breaking.append({"kind": "new required request field", "where": f"{key} body.{f}", "detail": "existing clients don't send it"})
                else:
                    additive.append({"kind": "optional request field added", "where": f"{key} body.{f}"})
            for f in sorted(set(op_) & set(np_)):
                if not op_[f]["required"] and np_[f]["required"]:
                    breaking.append({"kind": "request field became required", "where": f"{key} body.{f}", "detail": "existing requests omitting it now fail"})
                if op_[f]["type"] != np_[f]["type"] and "any" not in (op_[f]["type"], np_[f]["type"]):
                    breaking.append({"kind": "request field type changed", "where": f"{key} body.{f}", "detail": f"{op_[f]['type']} → {np_[f]['type']}"})
                oe, ne = op_[f]["enum"], np_[f]["enum"]
                if oe and ne:
                    removed = [v for v in oe if v not in ne]
                    if removed:
                        breaking.append({"kind": "request enum value removed", "where": f"{key} body.{f}", "detail": f"values no longer accepted: {removed}"})
                    if [v for v in ne if v not in oe]:
                        additive.append({"kind": "request enum value added", "where": f"{key} body.{f}"})
        for code in sorted(a["codes"] - b["codes"]):
            if code.startswith("2"):
                breaking.append({"kind": "success status code removed", "where": f"{key} {code}", "detail": "clients branching on it break"})
            else:
                notes.append(f"{key}: error response {code} removed from the spec — fine if it's never emitted")
        for code, sch in a["responses"].items():
            if code not in b["responses"]:
                continue
            op_, np_ = _props(old, sch), _props(new, b["responses"][code])
            for f in sorted(set(op_) - set(np_)):
                breaking.append({"kind": "response field removed", "where": f"{key} {code}.{f}", "detail": "clients reading it get undefined/null"})
            for f in sorted(set(np_) - set(op_)):
                additive.append({"kind": "response field added", "where": f"{key} {code}.{f}"})
            for f in sorted(set(op_) & set(np_)):
                if op_[f]["type"] != np_[f]["type"] and "any" not in (op_[f]["type"], np_[f]["type"]):
                    breaking.append({"kind": "response field type changed", "where": f"{key} {code}.{f}", "detail": f"{op_[f]['type']} → {np_[f]['type']}"})
                if op_[f]["required"] and not np_[f]["required"]:
                    breaking.append({"kind": "response field no longer guaranteed", "where": f"{key} {code}.{f}", "detail": "was required, now optional — strict clients break"})
                if op_[f]["nullable"] is not True and np_[f]["nullable"] is True:
                    breaking.append({"kind": "response field became nullable", "where": f"{key} {code}.{f}", "detail": "clients assuming non-null break"})
                oe, ne = op_[f]["enum"], np_[f]["enum"]
                if oe and ne and [v for v in ne if v not in oe]:
                    notes.append(f"{key} {code}.{f}: new enum value(s) in a response — breaking for clients with exhaustive switches; document 'unknown value' handling")
        if not a["deprecated"] and b["deprecated"]:
            additive.append({"kind": "operation deprecated", "where": key})
    o_schemas, n_schemas = set((old.get("components") or {}).get("schemas") or {}), set((new.get("components") or {}).get("schemas") or {})
    for s in sorted(o_schemas - n_schemas):
        notes.append(f"components.schemas.{s} removed — breaking only if still referenced by clients' generated types")
    if breaking:
        bump, verdict = "major", f"{len(breaking)} breaking change(s) — needs a new API version or a deprecation path; {len(additive)} additive."
    elif additive:
        bump, verdict = "minor", f"No breaking changes; {len(additive)} additive change(s) — safe to ship under the current version."
    else:
        bump, verdict = "patch", "No contract changes detected (docs/descriptions only)."
    return {
        "breaking": breaking,
        "additive": additive,
        "notes": notes,
        "operations_old": len(o_ops),
        "operations_new": len(n_ops),
        "semver_bump": bump,
        "verdict": verdict,
    }
