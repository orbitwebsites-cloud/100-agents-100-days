"""SQL Wizard — queries that are correct first, fast second, readable always.

A small SQL tokenizer feeds four tools: a deterministic formatter, an
anti-pattern linter, a structure explainer (tables, joins, nesting), and an
index advisor that applies the equality → sort → range rule.
"""

from __future__ import annotations

import re
from collections import Counter, OrderedDict, defaultdict

from ...core import Agent, ToolError
from ._common import require_text

AGENT = Agent(
    slug="sql-wizard",
    name="SQL Wizard",
    category="engineering",
    tagline="Write, fix and tune SQL like a database engineer: lint for the classic traps, format, and get index suggestions from the query itself.",
    description=(
        "Turns a question or a slow query into correct, readable, index-friendly SQL. Explains the "
        "structure of any query (tables, joins, CTEs, nesting), lints it against the traps that produce "
        "wrong results or full scans (NOT IN with NULLs, LEFT JOIN cancelled by WHERE, non-sargable "
        "predicates, leading wildcards, comma joins, LIMIT without ORDER BY), formats it consistently, "
        "and derives concrete CREATE INDEX statements using the equality-sort-range rule. Dialect-aware "
        "for PostgreSQL, MySQL, SQLite, SQL Server and BigQuery."
    ),
    triggers=[
        "write a SQL query that …",
        "why is this query slow / optimize this query",
        "explain what this SQL does",
        "format / clean up this SQL",
        "what index should I add for this query",
        "is this query correct / review my SQL",
    ],
    examples=[
        "Write a query for monthly active users by plan from these tables: users, events, subscriptions.",
        "This query takes 40 seconds on 20M rows — what's wrong and what index fixes it?",
        "Explain this 80-line report query someone left behind and tell me if it's safe to change.",
    ],
    connectors=["PostgreSQL", "MySQL", "BigQuery", "Snowflake", "Supabase", "GitHub"],
    playbook="""
    ## Standard
    You are a database engineer who has tuned queries on billion-row tables. Excellent means:
    the query returns exactly the rows the user meant (including the NULL and duplicate cases
    they didn't think about), it uses indexes the planner can actually use, and someone else can
    read it in a year. The one metric: **correct result on the first run**. Second: rows
    scanned per row returned.

    ## Intake
    You need: the query (or the question in plain English), the tables involved with their key
    columns, and the dialect (assume PostgreSQL if not stated — say so). For tuning you also
    want rough row counts and the EXPLAIN output if they have it. Ask at most 3 questions only
    when the join keys or the grain of the result ("one row per what?") are genuinely unknowable.
    Otherwise state assumptions inline (`-- assumes orders.user_id → users.id`) and proceed.

    ## Procedure
    1. **Understand the shape.** For any existing query, call `sql_wizard__explain_structure`
       first. It returns the statement type, tables and aliases, joins, CTEs, nesting depth,
       aggregates, window functions and the WHERE columns. Restate the grain in one sentence:
       "one row per (user, month)". If you can't, the query probably has a fan-out bug.
    2. **Lint before you tune.** Call `sql_wizard__lint_sql`. Fix correctness findings
       (severity `critical`/`high`) before touching performance: a fast wrong query is worse
       than a slow right one. Each finding carries the rewrite; apply it and say why.
    3. **Write or rewrite** following these rules:
       - Explicit `JOIN … ON`, never comma joins. Every join key named; note the cardinality
         (1:1, 1:N). An N:M join into an aggregate needs a pre-aggregated CTE, not DISTINCT.
       - Filter early: predicates on the driving table in WHERE; predicates on the right side of
         a LEFT JOIN go in the ON clause or the join silently becomes INNER.
       - Sargable predicates: `col >= '2026-01-01' AND col < '2026-02-01'`, not
         `DATE(col) = …` or `YEAR(col) = …`; `col LIKE 'abc%'`, not `'%abc%'`; no `LOWER(col)`
         unless there's an expression index.
       - `NOT EXISTS` instead of `NOT IN (subquery)` — NOT IN returns nothing if the subquery
         yields a NULL. `EXISTS` instead of `COUNT(*) > 0`.
       - `UNION ALL` unless you need de-duplication; `LIMIT` always with `ORDER BY`.
       - Name every derived column; no `SELECT *` in application code (column order and width
         are not a contract).
       - Keyset pagination (`WHERE (created_at, id) < (?, ?) ORDER BY created_at DESC, id DESC
         LIMIT n`) beyond ~10k rows of OFFSET.
    4. **Format** the final query with `sql_wizard__format_sql` so what you deliver is what the
       tool produced — consistent keyword case, one column per line, aligned clauses.
    5. **Index it.** For anything that will run more than once, call
       `sql_wizard__suggest_indexes` and include the CREATE INDEX statements, each with the one
       line of reasoning (which predicate/sort it serves). Warn about write amplification when
       suggesting more than two indexes on one table.
    6. **Say how to verify**: the EXPLAIN (ANALYZE, BUFFERS) command, what to look for (Seq Scan
       on a big table, Nested Loop with high loops, rows estimate off by >10×, Sort with
       external merge), and a sanity check query for the result (e.g. total should equal the
       untouched count).

    ## Frameworks
    - **Grain first**: decide the grain before the SELECT list. Every join either preserves
      the grain (1:1, N:1) or changes it (1:N) — the latter must be aggregated back.
    - **ESR rule** for composite B-tree indexes: Equality columns first, then Sort (ORDER BY)
      columns, then Range columns. Leftmost-prefix matters; the planner can't skip a column.
    - **Selectivity**: an index on a column with < ~5-10 distinct values (status, boolean) rarely
      helps alone — use it as a leading column only with a more selective one after it, or a
      partial index (`WHERE status = 'pending'`).
    - **Three-valued logic**: `NULL = NULL` is unknown, `NOT IN` with a NULL is empty, `<>`
      excludes NULLs, `COUNT(col)` skips NULLs, `COUNT(*)` doesn't.
    - **Window vs GROUP BY**: need the row *and* the aggregate → window function; need one row
      per group → GROUP BY. `ROW_NUMBER() OVER (PARTITION BY k ORDER BY t DESC) = 1` for
      latest-per-group.
    - **Dialect gotchas**: MySQL `"` is a string, Postgres `"` is an identifier; BigQuery
      needs backticks for project.dataset.table; SQL Server uses TOP not LIMIT; SQLite has no
      RIGHT JOIN before 3.39 and weak typing.

    ## Output format
    ```
    **Grain:** one row per <…> · **Dialect:** <…> · **Assumptions:** <join keys, filters>

    ```sql
    <formatted query, with -- comments on non-obvious lines>
    ```

    **Correctness notes:** <NULL handling, duplicates, time-zone/boundary choices>
    **Indexes:**
    ```sql
    CREATE INDEX … ; -- serves WHERE x = ? ORDER BY y
    ```
    **Verify:** `EXPLAIN (ANALYZE, BUFFERS) …` — expect <index name> scan, no Seq Scan on <big table>.
    **Sanity check:** <query whose result must equal …>
    ```
    For a tuning job, add a "Before → after" line: what was wrong, what changed, expected effect
    (e.g. "Seq Scan on orders (20M rows) → Index Scan on ~40k rows").

    ## Anti-patterns
    - Adding DISTINCT to hide a fan-out join. Find the 1:N join and aggregate it.
    - `SELECT *` in a CTE that then joins — drags every column through the whole plan.
    - Function-wrapped columns in WHERE (`DATE(created_at) = …`); no index will be used.
    - `NOT IN (SELECT …)` on a nullable column — returns zero rows and nobody notices.
    - OFFSET pagination on big tables; page 1000 scans 1000 pages.
    - Suggesting an index on every WHERE column separately instead of one composite in ESR order.
    - `BETWEEN` on timestamps — the end bound is inclusive; use `>= start AND < end`.
    """,
)

# ── tokenizer ────────────────────────────────────────────────────────────────

TOKEN_RE = re.compile(
    r"(?P<ws>\s+)"
    r"|(?P<comment>--[^\n]*|#[^\n]*|/\*.*?\*/)"
    r"|(?P<string>'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|`[^`]*`|\[[^\]]*\])"
    r"|(?P<number>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"|(?P<param>\?|:\w+|\$\d+|%s|%\(\w+\)s|@\w+)"
    r"|(?P<word>[A-Za-z_][\w$]*(?:\.(?:[A-Za-z_][\w$]*|\*))*)"
    r"|(?P<op><=|>=|<>|!=|::|\|\||->>|->|[=<>+\-*/%,;().])",
    re.S,
)

KEYWORDS = set("""
SELECT FROM WHERE GROUP BY HAVING ORDER LIMIT OFFSET UNION ALL EXCEPT INTERSECT INSERT INTO VALUES UPDATE SET DELETE
WITH RECURSIVE AS ON JOIN LEFT RIGHT INNER OUTER FULL CROSS NATURAL USING AND OR NOT IN IS NULL LIKE ILIKE BETWEEN EXISTS
CASE WHEN THEN ELSE END DISTINCT ASC DESC NULLS FIRST LAST OVER PARTITION ROWS RANGE UNBOUNDED PRECEDING FOLLOWING CURRENT ROW
CAST TRUE FALSE RETURNING CREATE TABLE INDEX DROP ALTER TRUNCATE VIEW TOP FETCH NEXT ONLY LATERAL WINDOW QUALIFY ANY SOME
PRIMARY KEY FOREIGN REFERENCES DEFAULT IF REPLACE MERGE MATCHED FILTER WITHIN EXPLAIN ANALYZE
""".split())
AGGREGATES = {"COUNT", "SUM", "AVG", "MIN", "MAX", "ARRAY_AGG", "STRING_AGG", "GROUP_CONCAT", "LISTAGG", "JSON_AGG", "BOOL_OR", "BOOL_AND", "EVERY", "APPROX_COUNT_DISTINCT", "PERCENTILE_CONT"}
FUNCTIONS = {"COALESCE", "NULLIF", "LOWER", "UPPER", "TRIM", "LENGTH", "SUBSTRING", "SUBSTR", "CONCAT", "REPLACE", "ROUND", "ABS", "FLOOR", "CEIL",
             "NOW", "CURRENT_DATE", "DATE", "DATE_TRUNC", "EXTRACT", "TO_CHAR", "TO_DATE", "CAST", "CONVERT", "IFNULL", "NVL", "GREATEST", "LEAST",
             "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE", "NTILE", "EXISTS", "IF", "ISNULL", "DATEDIFF", "DATEADD", "YEAR", "MONTH", "DAY"}
CLAUSE_STARTERS = {"SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "OFFSET", "UNION", "UNION ALL", "EXCEPT", "INTERSECT",
                   "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM", "DELETE", "WITH", "RETURNING", "WINDOW", "QUALIFY", "FETCH"}
JOIN_WORDS = {"JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN", "CROSS JOIN", "NATURAL JOIN", "LEFT OUTER JOIN", "RIGHT OUTER JOIN", "FULL OUTER JOIN"}


def tokenize(sql: str) -> list[dict]:
    """Tokens: {type, text, upper, adj} where adj = no whitespace before this token."""
    tokens: list[dict] = []
    pos, adj = 0, True
    for m in TOKEN_RE.finditer(sql):
        if m.start() != pos:
            raise ToolError(f"Unexpected character {sql[pos]!r} at position {pos}.")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            adj = False
            continue
        text_ = m.group()
        up = text_.upper() if kind == "word" else text_
        tokens.append({"type": kind, "text": text_, "upper": up, "adj": adj, "kw": kind == "word" and up in KEYWORDS})
        adj = True
    if pos != len(sql):
        raise ToolError(f"Unterminated string or comment near position {pos}.")
    return tokens


def _merge_keywords(tokens: list[dict]) -> list[dict]:
    """Merge multi-word keywords (GROUP BY, LEFT OUTER JOIN, INSERT INTO, UNION ALL, IS NOT, NOT IN...)."""
    out: list[dict] = []
    i = 0
    pairs = {("GROUP", "BY"), ("ORDER", "BY"), ("PARTITION", "BY"), ("INSERT", "INTO"), ("DELETE", "FROM"), ("UNION", "ALL"),
             ("IS", "NOT"), ("NOT", "IN"), ("NOT", "LIKE"), ("NOT", "EXISTS"), ("NOT", "BETWEEN"), ("UNION", "DISTINCT")}
    while i < len(tokens):
        t = tokens[i]
        if t["type"] == "word":
            u = t["upper"]
            if u in ("LEFT", "RIGHT", "FULL", "INNER", "CROSS", "NATURAL"):
                j = i + 1
                parts = [u]
                if j < len(tokens) and tokens[j]["upper"] == "OUTER":
                    parts.append("OUTER")
                    j += 1
                if j < len(tokens) and tokens[j]["upper"] == "JOIN":
                    parts.append("JOIN")
                    out.append({"type": "word", "text": " ".join(parts), "upper": " ".join(parts), "adj": t["adj"], "kw": True})
                    i = j + 1
                    continue
            if i + 1 < len(tokens) and tokens[i + 1]["type"] == "word" and (u, tokens[i + 1]["upper"]) in pairs:
                merged = f"{u} {tokens[i + 1]['upper']}"
                out.append({"type": "word", "text": merged, "upper": merged, "adj": t["adj"], "kw": True})
                i += 2
                continue
        out.append(t)
        i += 1
    return out


def _split_statements(tokens: list[dict]) -> list[list[dict]]:
    stmts, cur = [], []
    for t in tokens:
        if t["type"] == "op" and t["text"] == ";":
            if cur:
                stmts.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        stmts.append(cur)
    return [s for s in stmts if any(t["type"] != "comment" for t in s)]


# ── formatter ────────────────────────────────────────────────────────────────


def _format_statement(tokens: list[dict], indent_unit: str, kw_case: str) -> str:
    out: list[str] = []
    line: list[str] = []
    depth_stack: list[dict] = [{"indent": 0, "clause": None, "paren": 0}]
    case_depth = 0
    cur_line_indent = [0]

    def kw(text_: str) -> str:
        return text_.upper() if kw_case == "upper" else text_.lower()

    def flush() -> None:
        if line:
            out.append("".join(line).rstrip())
            line.clear()

    def newline(ind: int) -> None:
        flush()
        cur_line_indent[0] = ind
        line.append(indent_unit * ind)

    def emit(text_: str, space: bool = True) -> None:
        if line and line[-1] and not line[-1].endswith((" ", "(")) and space and text_ not in (",", ")", ";", "::", ".") and not line[-1].endswith("."):
            line.append(" ")
        line.append(text_)

    n = len(tokens)
    for i, t in enumerate(tokens):
        ctx = depth_stack[-1]
        nxt = tokens[i + 1] if i + 1 < n else None
        prev = tokens[i - 1] if i else None
        text_ = t["text"]
        if t["type"] == "comment":
            if text_.startswith("--") or text_.startswith("#"):
                emit(text_)
                newline(ctx["indent"])
            else:
                emit(text_)
            continue
        if t["type"] == "op" and text_ == "(":
            is_sub = nxt is not None and nxt["upper"] in ("SELECT", "WITH")
            space = not (prev and t["adj"] and prev["type"] in ("word",) and not prev["kw"]) and not (prev and prev["upper"] in ("COUNT", "SUM", "AVG", "MIN", "MAX", "CAST"))
            emit("(", space)
            if is_sub:
                base = cur_line_indent[0]
                depth_stack.append({"indent": base + 1, "clause": None, "paren": 0, "close_indent": base})
                newline(base + 1)
            else:
                ctx["paren"] += 1
            continue
        if t["type"] == "op" and text_ == ")":
            if ctx["paren"] == 0 and len(depth_stack) > 1:
                closed = depth_stack.pop()
                newline(closed["close_indent"])
                emit(")", False)
            else:
                ctx["paren"] = max(0, ctx["paren"] - 1)
                emit(")", False)
            continue
        if t["type"] == "op" and text_ == ",":
            emit(",", False)
            if ctx["paren"] == 0 and ctx["clause"] in ("SELECT", "WITH", "GROUP BY", "ORDER BY", "SET", "RETURNING"):
                newline(ctx["indent"] + 1)
            else:
                line.append(" ")
            continue
        if t["type"] == "word" and t["kw"]:
            u = t["upper"]
            if u in CLAUSE_STARTERS and ctx["paren"] == 0:
                if not (u == "SELECT" and (not line or line[-1].strip() == "" and len(out) == 0) and ctx["clause"] is None) or True:
                    if line and line[-1].strip():
                        newline(ctx["indent"])
                    elif not line:
                        newline(ctx["indent"])
                ctx["clause"] = u
                emit(kw(u))
                if u in ("SELECT",) and nxt and nxt["upper"] not in ("DISTINCT", "TOP", "*"):
                    newline(ctx["indent"] + 1)
                elif u == "SELECT" and nxt and nxt["upper"] == "DISTINCT":
                    emit(kw("DISTINCT"))
                    newline(ctx["indent"] + 1)
                    tokens[i + 1] = {**nxt, "type": "skip"}
                elif u in ("GROUP BY", "ORDER BY", "SET", "RETURNING"):
                    newline(ctx["indent"] + 1)
                continue
            if u in JOIN_WORDS and ctx["paren"] == 0:
                newline(ctx["indent"])
                ctx["clause"] = "JOIN"
                emit(kw(u))
                continue
            if u == "ON" and ctx["paren"] == 0 and ctx["clause"] == "JOIN":
                newline(ctx["indent"] + 1)
                emit(kw(u))
                continue
            if u in ("AND", "OR") and ctx["paren"] == 0 and ctx["clause"] in ("WHERE", "HAVING", "JOIN", "QUALIFY"):
                newline(ctx["indent"] + 1)
                emit(kw(u))
                continue
            if u == "CASE":
                case_depth += 1
                emit(kw(u))
                continue
            if u in ("WHEN", "ELSE") and case_depth:
                newline(ctx["indent"] + 1 + case_depth)
                emit(kw(u))
                continue
            if u == "END" and case_depth:
                newline(ctx["indent"] + case_depth)
                case_depth -= 1
                emit(kw(u))
                continue
            emit(kw(u))
            continue
        if t["type"] == "skip":
            continue
        if t["type"] == "op":
            if text_ in (".", "::"):
                emit(text_, False)
            elif text_ in ("(", ")"):
                emit(text_, False)
            else:
                emit(text_)
            continue
        # words, strings, numbers, params
        if t["type"] == "word" and nxt is not None and nxt["text"] == "(" and nxt["adj"] and (t["upper"] in AGGREGATES or t["upper"] in FUNCTIONS):
            text_ = kw(t["upper"])
        if prev and prev["type"] == "op" and prev["text"] in (".", "::"):
            emit(text_, False)
        else:
            emit(text_)
    flush()
    return "\n".join(l for l in out if l.strip() != "" or False).rstrip()


@AGENT.tool
def format_sql(sql: str, keyword_case: str = "upper", indent: int = 4) -> dict:
    """Format SQL deterministically: keywords cased, one SELECT column per line, clauses aligned, subqueries and CASE indented, strings untouched.

    Call on every query you deliver so output is consistent. Handles multiple statements.

    Args:
        sql: The SQL text (one or more statements).
        keyword_case: "upper" or "lower" for keywords; identifiers are never changed.
        indent: Spaces per indent level (2-8).
    """
    sql = require_text(sql, "sql", 100_000)
    if keyword_case not in ("upper", "lower"):
        raise ToolError('keyword_case must be "upper" or "lower".')
    indent = max(2, min(8, int(indent)))
    tokens = _merge_keywords(tokenize(sql))
    stmts = _split_statements(tokens)
    if not stmts:
        raise ToolError("No SQL statements found.")
    formatted = []
    for st in stmts:
        formatted.append(_format_statement([dict(t) for t in st], " " * indent, keyword_case) + ";")
    text_out = "\n\n".join(formatted)
    return {
        "formatted": text_out,
        "statements": len(stmts),
        "lines": text_out.count("\n") + 1,
        "chars_before": len(sql),
        "chars_after": len(text_out),
        "summary": f"Formatted {len(stmts)} statement(s) into {text_out.count(chr(10)) + 1} lines.",
    }


# ── skeleton for rule matching ───────────────────────────────────────────────


def _skeleton(tokens: list[dict]) -> str:
    parts = []
    for t in tokens:
        if t["type"] == "comment":
            continue
        if t["type"] == "string":
            parts.append("'?'" if t["text"].startswith("'") else "\"?\"")
        elif t["type"] == "number":
            parts.append("0")
        elif t["type"] == "param":
            parts.append("?")
        elif t["type"] == "word":
            parts.append(t["upper"] if t["kw"] else t["text"])
        else:
            parts.append(t["text"])
    return " ".join(parts)


def _clause_spans(tokens: list[dict]) -> dict[str, list[dict]]:
    """Top-level clause → tokens (paren depth 0 of the outermost statement)."""
    spans: dict[str, list[dict]] = defaultdict(list)
    depth, clause = 0, "PRE"
    for t in tokens:
        if t["type"] == "op" and t["text"] == "(":
            depth += 1
        elif t["type"] == "op" and t["text"] == ")":
            depth -= 1
        elif depth == 0 and t["type"] == "word" and t["kw"] and (t["upper"] in CLAUSE_STARTERS or t["upper"] in JOIN_WORDS):
            clause = "JOIN" if t["upper"] in JOIN_WORDS else t["upper"]
            spans[clause].append(t)
            continue
        spans[clause].append(t)
    return spans


# ── structure ────────────────────────────────────────────────────────────────


def _analyse(tokens: list[dict]) -> dict:
    toks = [t for t in tokens if t["type"] != "comment"]
    words = [t["upper"] if t["kw"] else t["text"] for t in toks]
    first_kw = next((t["upper"] for t in toks if t["kw"]), "UNKNOWN")
    stmt_type = "SELECT" if first_kw == "WITH" else first_kw.split()[0]
    ctes: list[str] = []
    tables: "OrderedDict[str, str]" = OrderedDict()  # alias -> table
    joins: list[dict] = []
    depth = 0
    max_sub = 0
    sub_count = 0
    n = len(toks)
    for i, t in enumerate(toks):
        if t["type"] == "op" and t["text"] == "(":
            depth += 1
            if i + 1 < n and toks[i + 1]["upper"] in ("SELECT", "WITH"):
                sub_count += 1
                max_sub = max(max_sub, depth)
        elif t["type"] == "op" and t["text"] == ")":
            depth -= 1
        if t["kw"] and t["upper"] == "AS" and i + 1 < n and toks[i + 1]["text"] == "(" and i >= 1 and toks[i - 1]["type"] == "word" and not toks[i - 1]["kw"]:
            ctes.append(toks[i - 1]["text"])
        if t["kw"] and (t["upper"] in ("FROM", "DELETE FROM", "UPDATE", "INSERT INTO", "INTO") or t["upper"] in JOIN_WORDS):
            j = i + 1
            while j < n:
                if toks[j]["type"] == "op" and toks[j]["text"] == "(":
                    name = "(subquery)"
                    d = 1
                    j += 1
                    while j < n and d:
                        d += (toks[j]["text"] == "(") - (toks[j]["text"] == ")")
                        j += 1
                elif toks[j]["type"] in ("word", "string") and not toks[j]["kw"]:
                    name = toks[j]["text"]
                    j += 1
                else:
                    break
                alias = name
                if j < n and toks[j]["kw"] and toks[j]["upper"] == "AS":
                    j += 1
                if j < n and toks[j]["type"] == "word" and not toks[j]["kw"]:
                    alias = toks[j]["text"]
                    j += 1
                tables[alias] = name
                if t["upper"] in JOIN_WORDS:
                    joins.append({"type": t["upper"], "table": name, "alias": alias, "on": ""})
                if j < n and toks[j]["text"] == "," and t["upper"] in ("FROM", "DELETE FROM"):
                    joins.append({"type": "COMMA JOIN", "table": None, "alias": None, "on": ""})
                    j += 1
                    continue
                break
        if t["kw"] and t["upper"] == "ON" and joins:
            j = i + 1
            cond = []
            while j < n and not (toks[j]["kw"] and (toks[j]["upper"] in CLAUSE_STARTERS or toks[j]["upper"] in JOIN_WORDS or toks[j]["upper"] == "WHERE")):
                cond.append(toks[j]["text"])
                j += 1
            joins[-1]["on"] = " ".join(cond)[:120]
        if t["kw"] and t["upper"] == "USING" and joins:
            joins[-1]["on"] = "USING " + " ".join(x["text"] for x in toks[i + 1:i + 6])[:60]
    aggs = Counter(t["upper"] for i, t in enumerate(toks) if t["type"] == "word" and t["upper"] in AGGREGATES and i + 1 < n and toks[i + 1]["text"] == "(")
    windows = sum(1 for t in toks if t["kw"] and t["upper"] == "OVER")
    spans = _clause_spans(toks)
    select_items = 0
    if "SELECT" in spans:
        d = 0
        select_items = 1
        for t in spans["SELECT"][1:]:
            if t["text"] == "(":
                d += 1
            elif t["text"] == ")":
                d -= 1
            elif t["text"] == "," and d == 0:
                select_items += 1
    where_cols = []
    wtoks = spans.get("WHERE", [])
    for i, t in enumerate(wtoks):
        if t["type"] == "word" and not t["kw"] and t["upper"] not in AGGREGATES and not (i + 1 < len(wtoks) and wtoks[i + 1]["text"] == "(" and wtoks[i + 1]["adj"]):
            where_cols.append(t["text"])
    where_cols = list(dict.fromkeys(where_cols))
    sel = spans.get("SELECT", [])
    return {
        "statement_type": stmt_type,
        "ctes": ctes,
        "tables": [{"table": tb, "alias": al} for al, tb in tables.items() if tb not in ctes] ,
        "cte_references": [al for al, tb in tables.items() if tb in ctes],
        "joins": joins,
        "join_count": len(joins),
        "subqueries": sub_count,
        "max_subquery_depth": max_sub,
        "select_items": select_items,
        "select_star": any((t["text"] == "*" and (i == 0 or sel[i - 1]["text"] != "(")) or t["text"].endswith(".*") for i, t in enumerate(sel)),
        "select_aliases": [sel[i + 1]["text"] for i, t in enumerate(sel) if t["kw"] and t["upper"] == "AS" and i + 1 < len(sel) and sel[i + 1]["type"] == "word" and not sel[i + 1]["kw"]],
        "aggregates": dict(aggs),
        "has_group_by": "GROUP BY" in spans,
        "window_functions": windows,
        "where_columns": where_cols[:40],
        "has_order_by": "ORDER BY" in spans,
        "has_limit": "LIMIT" in spans or "FETCH" in spans or any(w == "TOP" for w in words[:4]),
        "has_where": "WHERE" in spans,
        "spans": spans,
        "words": words,
        "tokens": toks,
    }


@AGENT.tool
def explain_structure(sql: str) -> dict:
    """Map a query's structure: statement type, tables and aliases, joins with ON conditions, CTEs, subquery nesting, aggregates, window functions, WHERE columns.

    Call first on any existing query so you can state its grain before changing it.

    Args:
        sql: A single SQL statement (or several; each is analysed separately).
    """
    sql = require_text(sql, "sql", 100_000)
    stmts = _split_statements(_merge_keywords(tokenize(sql)))
    if not stmts:
        raise ToolError("No SQL statements found.")
    results = []
    for st in stmts:
        a = _analyse(st)
        shape = []
        if a["ctes"]:
            shape.append(f"{len(a['ctes'])} CTE(s): {', '.join(a['ctes'][:6])}")
        shape.append(f"{a['statement_type']} over {len(a['tables'])} table(s)")
        if a["join_count"]:
            shape.append(f"{a['join_count']} join(s): " + ", ".join(j["type"] for j in a["joins"]))
        if a["aggregates"]:
            shape.append("aggregates: " + ", ".join(f"{k}×{v}" for k, v in a["aggregates"].items()))
        if a["window_functions"]:
            shape.append(f"{a['window_functions']} window function(s)")
        if a["subqueries"]:
            shape.append(f"{a['subqueries']} subquery(ies), max depth {a['max_subquery_depth']}")
        grain_hint = (
            "one row per GROUP BY key" if a["has_group_by"] else
            "one row per source row of the driving table — unless a 1:N join fans it out" if a["join_count"] else
            "one row per row of " + (a["tables"][0]["table"] if a["tables"] else "the source")
        )
        results.append({k: v for k, v in a.items() if k not in ("spans", "words", "tokens")} | {"shape": "; ".join(shape), "grain_hint": grain_hint})
    return {"statements": results, "summary": " | ".join(r["shape"] for r in results)}


# ── linter ───────────────────────────────────────────────────────────────────

NON_SARGABLE_FUNCS = r"(LOWER|UPPER|DATE|YEAR|MONTH|DAY|TRUNC|DATE_TRUNC|CAST|CONVERT|COALESCE|SUBSTR|SUBSTRING|LEFT|RIGHT|TRIM|TO_CHAR|EXTRACT|LENGTH|ABS|ROUND|IFNULL|NVL)"


def _lint_statement(st: list[dict]) -> list[dict]:
    a = _analyse(st)
    sk = _skeleton(st)
    findings = []

    def add(rule: str, severity: str, message: str, fix: str) -> None:
        findings.append({"rule": rule, "severity": severity, "message": message, "fix": fix})

    stype = a["statement_type"]
    if stype in ("DELETE", "UPDATE") and not a["has_where"]:
        add("no-where-on-write", "critical", f"{stype} without WHERE touches every row.", "Add a WHERE clause; run a SELECT with the same predicate first to count affected rows.")
    if re.search(r"\b(DROP|TRUNCATE)\s+(TABLE|DATABASE|SCHEMA)?", sk):
        add("destructive", "critical", "DROP/TRUNCATE is irreversible.", "Confirm a backup exists and run inside a transaction where the engine supports it.")
    if a["select_star"] and stype == "SELECT":
        add("select-star", "medium", "SELECT * couples the query to column order/width and drags unused columns through the plan.", "List the columns you use; enables covering indexes.")
    if re.search(r"NOT IN \( SELECT", sk):
        add("not-in-subquery", "high", "NOT IN (subquery) returns no rows if the subquery yields any NULL.", "Rewrite as NOT EXISTS (SELECT 1 FROM … WHERE … = outer.col).")
    if re.search(r"(=|<>|!=) NULL\b", sk):
        add("null-equality", "critical", "`= NULL` / `<> NULL` is never true — three-valued logic.", "Use IS NULL / IS NOT NULL.")
    for t_i, t in enumerate(st):
        if t["type"] == "string" and t_i and st[t_i - 1]["upper"] in ("LIKE", "ILIKE", "NOT LIKE") and t["text"][1:2] in ("%", "_"):
            add("leading-wildcard", "high", f"LIKE {t['text'][:20]} with a leading wildcard cannot use a B-tree index (full scan).", "Anchor the pattern ('abc%'), or use a trigram/full-text index (pg_trgm, FULLTEXT).")
            break
    m = re.search(r"\b(WHERE|AND|OR|ON)\s+" + NON_SARGABLE_FUNCS + r" \( [\w.]+ (?:,[^)]*)?\) (=|<|>|<=|>=|<>|!=|IN|LIKE|BETWEEN)", sk)
    if m:
        add("non-sargable", "high", f"{m.group(2)}(column) in a predicate defeats the index on that column.", "Move the function to the constant side (col >= '2026-01-01' AND col < '2026-02-01'; LOWER(col) needs an expression index).")
    if any(j["type"] == "COMMA JOIN" for j in a["joins"]):
        add("comma-join", "medium", "Comma-separated tables in FROM (implicit join) — easy to forget the join predicate and get a cartesian product.", "Use explicit JOIN … ON.")
    if any(j["type"] in ("CROSS JOIN",) for j in a["joins"]):
        add("cross-join", "medium", "CROSS JOIN multiplies rows.", "Confirm the cartesian product is intended (e.g. calendar × dimension).")
    # LEFT JOIN cancelled by WHERE on the right table
    for j in a["joins"]:
        if j["type"].startswith("LEFT") and j["alias"]:
            where_sk = _skeleton(a["spans"].get("WHERE", []))
            if re.search(rf"\b{re.escape(j['alias'])}\.\w+ (=|<>|!=|<|>|<=|>=|IN|LIKE) ", where_sk) and not re.search(rf"\b{re.escape(j['alias'])}\.\w+ IS NULL", where_sk):
                add("left-join-cancelled", "high", f"WHERE filters {j['alias']}.column, which turns the LEFT JOIN on {j['table']} into an INNER JOIN (rows with no match are dropped).", f"Move the {j['alias']} predicate into the ON clause, or add `OR {j['alias']}.col IS NULL`.")
    if a["has_limit"] and not a["has_order_by"] and stype == "SELECT":
        add("limit-without-order", "medium", "LIMIT without ORDER BY returns an arbitrary, unstable subset.", "Add ORDER BY on a unique key (or created_at, id).")
    for t_i, t in enumerate(st):
        if t["kw"] and t["upper"] == "OFFSET" and t_i + 1 < len(st) and st[t_i + 1]["type"] == "number" and float(st[t_i + 1]["text"]) >= 10000:
            add("deep-offset", "medium", f"OFFSET {st[t_i + 1]['text']} scans and discards that many rows on every page.", "Use keyset pagination: WHERE (sort_col, id) < (?, ?) ORDER BY sort_col, id LIMIT n.")
    if "DISTINCT" in a["words"] and a["join_count"]:
        add("distinct-with-joins", "medium", "DISTINCT combined with joins usually hides a 1:N fan-out.", "Find the join that multiplies rows and aggregate it in a CTE, or use EXISTS.")
    if re.search(r"COUNT \( \*? ?\) (>|>=) 0", sk) or re.search(r"COUNT \( [\w.]+ \) (>|>=) 0", sk):
        add("count-for-existence", "low", "COUNT(*) > 0 counts every matching row just to test existence.", "Use EXISTS (SELECT 1 …).")
    if re.search(r"\bUNION\b(?! ALL)", sk):
        add("union-dedup", "low", "UNION de-duplicates (sort/hash of the whole result).", "Use UNION ALL unless duplicates are possible and unwanted.")
    if "SELECT" in a["spans"]:
        sel = _skeleton(a["spans"]["SELECT"])
        if re.search(r"\( SELECT ", sel):
            add("correlated-subselect", "medium", "Subquery in the SELECT list runs once per output row (N+1 inside the database).", "Rewrite as a JOIN to a pre-aggregated derived table / CTE.")
    if re.search(r"\bBETWEEN\b", sk) and re.search(r"(_at|_date|_time|date|time|timestamp)\b", sk, re.I):
        add("between-timestamp", "medium", "BETWEEN is inclusive on both ends — with timestamps the end boundary double-counts or misses sub-second rows.", "Use col >= start AND col < end.")
    if re.search(r"\bWHERE\b.*\bOR\b", _skeleton(a["spans"].get("WHERE", []))) and not re.search(r"\(", _skeleton(a["spans"].get("WHERE", []))):
        add("or-without-parens", "medium", "AND/OR mixed without parentheses — precedence is AND before OR, often not what was meant.", "Parenthesise the OR group explicitly.")
    if "HAVING" in a["spans"] and not any(t["upper"] in AGGREGATES for t in a["spans"]["HAVING"]):
        add("having-without-aggregate", "low", "HAVING with no aggregate filters after grouping — slower than WHERE.", "Move the condition to WHERE.")
    ins = [t for t in st if t["upper"] == "INSERT INTO"]
    if ins:
        i0 = st.index(ins[0])
        if i0 + 2 < len(st) and st[i0 + 2]["text"] != "(":
            add("insert-without-columns", "medium", "INSERT without a column list breaks when the table gets a new column.", "INSERT INTO t (col1, col2) VALUES (...).")
    if a["join_count"] and any(j["type"] not in ("COMMA JOIN", "CROSS JOIN", "NATURAL JOIN") and not j["on"] for j in a["joins"]):
        add("join-without-on", "critical", "A JOIN has no ON/USING condition → cartesian product.", "Add the join predicate.")
    if len(a["where_columns"]) == 0 and stype == "SELECT" and a["tables"] and not a["has_limit"] and not a["aggregates"]:
        add("unbounded-select", "low", "No WHERE and no LIMIT — returns the whole table.", "Add a filter or LIMIT for interactive use.")
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: sev_order[f["severity"]])
    return findings


@AGENT.tool
def lint_sql(sql: str) -> dict:
    """Lint SQL for the classic correctness and performance traps: NOT IN with NULLs, = NULL, LEFT JOIN cancelled by WHERE, non-sargable predicates, leading wildcards, comma joins, LIMIT without ORDER BY, deep OFFSET, DISTINCT hiding fan-out, writes without WHERE.

    Call before tuning; fix critical/high findings first.

    Args:
        sql: One or more SQL statements.
    """
    sql = require_text(sql, "sql", 100_000)
    stmts = _split_statements(_merge_keywords(tokenize(sql)))
    if not stmts:
        raise ToolError("No SQL statements found.")
    per = []
    all_findings = []
    for i, st in enumerate(stmts, 1):
        f = _lint_statement(st)
        per.append({"statement": i, "findings": f})
        all_findings.extend(f)
    counts = Counter(f["severity"] for f in all_findings)
    score = max(0, 100 - 40 * counts["critical"] - 20 * counts["high"] - 8 * counts["medium"] - 3 * counts["low"])
    if counts["critical"]:
        verdict = f"Do not run: {counts['critical']} critical finding(s) — " + "; ".join(f["message"] for f in all_findings if f["severity"] == "critical")[:200]
    elif counts["high"]:
        verdict = f"Likely wrong or slow: {counts['high']} high-severity finding(s)."
    elif all_findings:
        verdict = f"Runs correctly; {len(all_findings)} improvement(s)."
    else:
        verdict = "Clean: no anti-patterns detected."
    return {"score": score, "counts": dict(counts), "statements": per, "findings": all_findings, "verdict": verdict}


# ── index advisor ────────────────────────────────────────────────────────────

EQ_OPS = {"=", "IN", "IS"}
RANGE_OPS = {"<", ">", "<=", ">=", "BETWEEN", "LIKE", "ILIKE", "<>", "!="}


def _collect_predicates(tokens: list[dict]) -> list[tuple[str, str, bool]]:
    """(column, kind, wrapped_in_function) for predicates at any depth of the clause tokens."""
    preds = []
    n = len(tokens)
    for i, t in enumerate(tokens):
        if t["type"] != "word" or t["kw"] or t["upper"] in AGGREGATES:
            continue
        nxt = tokens[i + 1] if i + 1 < n else None
        prev = tokens[i - 1] if i else None
        if nxt is None:
            continue
        wrapped = prev is not None and prev["text"] == "(" and i >= 2 and tokens[i - 2]["type"] == "word" and re.fullmatch(NON_SARGABLE_FUNCS, tokens[i - 2]["upper"] or "")
        if wrapped:
            # skip closing paren to find operator
            k = i + 1
            while k < n and tokens[k]["text"] != ")":
                k += 1
            nxt = tokens[k + 1] if k + 1 < n else None
            if nxt is None:
                continue
        op = nxt["upper"] if nxt["type"] in ("op", "word") else ""
        if op in EQ_OPS or op == "NOT IN":
            after = tokens[i + 2] if i + 2 < n else None
            if op == "=" and after and after["type"] == "word" and not after["kw"] and "." in after["text"]:
                preds.append((t["text"], "join", bool(wrapped)))
                preds.append((after["text"], "join", False))
            elif op == "IS":
                preds.append((t["text"], "equality", bool(wrapped)))
            else:
                preds.append((t["text"], "equality", bool(wrapped)))
        elif op in RANGE_OPS or op in ("NOT LIKE", "NOT BETWEEN"):
            leading = op in ("LIKE", "ILIKE") and i + 2 < n and tokens[i + 2]["type"] == "string" and tokens[i + 2]["text"][1:2] in ("%", "_")
            preds.append((t["text"], "unindexable" if leading else "range", bool(wrapped)))
    return preds


@AGENT.tool
def suggest_indexes(sql: str, dialect: str = "postgresql") -> dict:
    """Derive CREATE INDEX statements from a query's WHERE, JOIN and ORDER BY columns using the equality → sort → range composite rule, per table.

    Call for any query that will run repeatedly. Flags function-wrapped and leading-wildcard
    predicates that no B-tree can serve.

    Args:
        sql: A single SELECT/UPDATE/DELETE statement.
        dialect: postgresql | mysql | sqlite | sqlserver | bigquery — affects syntax and notes.
    """
    sql = require_text(sql, "sql", 100_000)
    dialect = dialect.lower().strip()
    stmts = _split_statements(_merge_keywords(tokenize(sql)))
    if not stmts:
        raise ToolError("No SQL statement found.")
    if len(stmts) > 1:
        raise ToolError("Pass one statement at a time for index advice.")
    a = _analyse(stmts[0])
    if not a["tables"]:
        raise ToolError("No tables found in FROM/JOIN/UPDATE — nothing to index.")
    alias_to_table = {t["alias"]: t["table"] for t in a["tables"]}
    single = a["tables"][0]["table"] if len(a["tables"]) == 1 else None
    per_table: dict[str, dict] = defaultdict(lambda: {"equality": [], "range": [], "sort": [], "join": [], "unindexable": []})
    unassigned = []

    aliases = set(a.get("select_aliases", []))

    def place(col: str, kind: str, wrapped: bool) -> None:
        if col in aliases and "." not in col:
            return
        if "." in col:
            al, c = col.rsplit(".", 1)
            tb = alias_to_table.get(al)
            if tb is None:
                unassigned.append(col)
                return
        elif single:
            tb, c = single, col
        else:
            unassigned.append(col)
            return
        bucket = "unindexable" if (wrapped or kind == "unindexable") else kind
        lst = per_table[tb][bucket]
        entry = c if not wrapped else f"{c} (function-wrapped)"
        if entry not in lst:
            lst.append(entry)

    for clause in ("WHERE", "JOIN", "HAVING"):
        for col, kind, wrapped in _collect_predicates(a["spans"].get(clause, [])):
            place(col, kind, wrapped)
    ob = a["spans"].get("ORDER BY", [])
    d = 0
    for t in ob[1:]:
        if t["text"] == "(":
            d += 1
        elif t["text"] == ")":
            d -= 1
        elif d == 0 and t["type"] == "word" and not t["kw"] and t["upper"] not in AGGREGATES:
            place(t["text"], "sort", False)
    if a["has_group_by"]:
        for t in a["spans"]["GROUP BY"][1:]:
            if t["type"] == "word" and not t["kw"]:
                place(t["text"], "sort", False)

    statements, notes = [], []
    for tb, cols in per_table.items():
        eq = [c for c in cols["equality"] if "(" not in c and c.lower() != "id"]
        join = [c for c in cols["join"] if c not in eq and c.lower() != "id"]
        sort = [c for c in cols["sort"] if c not in eq and c not in join and c.lower() != "id"]
        rng = [c for c in cols["range"] if c not in eq and c not in sort and c not in join]
        for u in cols["unindexable"]:
            notes.append(f"{tb}.{u}: not B-tree indexable as written — " + ("use an expression index on the same expression, or make the predicate sargable." if "function" in u else "leading-wildcard LIKE needs a trigram/full-text index."))
        ordered = eq + join + sort + rng[:1]
        if not ordered:
            if any(c.lower() == "id" for c in cols["equality"] + cols["join"]):
                notes.append(f"{tb}: only `id` is used — assumed primary key, already indexed.")
            continue
        name = f"idx_{re.sub(r'[^a-z0-9]+', '_', tb.lower())}_{'_'.join(re.sub(r'[^a-z0-9]+', '_', c.lower()) for c in ordered)}"[:63]
        stmt = f"CREATE INDEX {name} ON {tb} ({', '.join(ordered)});"
        if dialect == "postgresql":
            stmt = stmt.replace("CREATE INDEX", "CREATE INDEX CONCURRENTLY")
        reason = []
        if eq:
            reason.append(f"equality on {', '.join(eq)}")
        if join:
            reason.append(f"join key {', '.join(join)}")
        if sort:
            reason.append(f"sort/group on {', '.join(sort)}")
        if rng:
            reason.append(f"range on {rng[0]}" + (f" (only the first range column benefits; {', '.join(rng[1:])} filtered after)" if len(rng) > 1 else ""))
        statements.append({"table": tb, "columns": ordered, "statement": stmt, "serves": "; ".join(reason)})
    if unassigned:
        notes.append("Unqualified/unknown columns not assigned to a table: " + ", ".join(sorted(set(unassigned))[:10]) + ". Qualify them (alias.col) for precise advice.")
    if dialect == "bigquery":
        notes.append("BigQuery has no B-tree indexes: use PARTITION BY on the range/date column and CLUSTER BY the equality columns instead.")
    if len(statements) > 2:
        notes.append(f"{len(statements)} indexes suggested — each adds write cost; keep only those serving hot queries.")
    return {
        "indexes": statements,
        "notes": notes,
        "assumption": "Columns named `id` are treated as the primary key (already indexed) and omitted.",
        "rule": "Composite order = equality columns → join keys → sort/group columns → one range column (leftmost prefix must match the query).",
        "verdict": (f"{len(statements)} index(es) suggested: " + "; ".join(s["statement"] for s in statements)) if statements else "No indexable predicates found" + (" — " + notes[0] if notes else "."),
    }
