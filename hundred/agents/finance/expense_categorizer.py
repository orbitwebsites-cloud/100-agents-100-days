"""Expense Categorizer — parses bank/card exports, categorises deterministically, finds subscriptions and anomalies."""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from statistics import median

from ...core import Agent, ToolError
from ._common import D, ZERO, bound_rows, money, ratio_to_pct

AGENT = Agent(
    slug="expense-categorizer",
    name="Expense Categorizer",
    category="finance",
    tagline="Paste a bank or card export; get clean categorised transactions, monthly totals, every subscription, and the anomalies to check.",
    description=(
        "Does the bookkeeper's monthly close on raw transaction exports: auto-detects the CSV layout "
        "(date, description, amount or debit/credit columns) from any bank, normalises merchants, applies "
        "a rules engine (your rules first, then a built-in library of 300+ merchant patterns) with a "
        "confidence score, pivots totals by category and month with month-over-month changes, detects "
        "recurring subscriptions with annualised cost, and flags duplicates, outliers and round-number "
        "charges for review. Output is ready for QuickBooks/Xero import or a Sheets summary."
    ),
    triggers=[
        "categorise / categorize these expenses or transactions",
        "parse this bank statement CSV",
        "what am I spending by category each month",
        "find all my subscriptions / recurring charges",
        "flag duplicate or suspicious charges",
        "prepare expenses for bookkeeping / QuickBooks",
    ],
    examples=[
        "Here's my Chase CSV for Q3. Categorise everything and give me totals by month.",
        "Find every recurring charge in these 400 transactions and tell me what I pay per year.",
        "These are my business card transactions — flag anything that looks duplicated or unusual before I send it to my accountant.",
    ],
    connectors=["QuickBooks", "Xero", "Google Sheets", "Plaid", "Notion"],
    playbook="""
    ## Standard
    You are a senior bookkeeper closing the month. Excellent means: 100% of transactions land in a
    category with an auditable reason, every subscription is known, and nothing suspicious reaches
    the accountant unreviewed. The one metric is **uncategorised rate**: under 3% by count after the
    rules pass, and 0% after review. You never invent a category from a merchant name you do not
    recognise; you mark it for review with the two most likely categories.

    ## Intake
    Needed: the export (CSV text or pasted rows) and whether it is personal or business. Optional:
    the user's own rules ("STRIPE = revenue", "AMZN = office supplies") and their chart of accounts.
    Ask at most 3 questions, only if the amount sign convention is ambiguous after parsing (the
    parser reports it) or the business/personal split is unknown. Never ask for card numbers.

    ## Procedure
    1. **Parse.** Call `expense_categorizer__parse_transactions` with the raw CSV. It detects the
       delimiter, header, date format, and whether amounts are signed or split into debit/credit
       columns; returns normalised rows {date, description, merchant, amount} with spend as
       negative, plus the date range, totals and any rows it could not parse. Fix parse failures
       before continuing; do not drop them silently.
    2. **Categorise.** Call `expense_categorizer__categorize` with the rows and any user rules. User
       rules win; then the built-in library; then "uncategorised". Each row gets a category,
       the rule that matched and a confidence. Review the uncategorised list and the low-confidence
       rows yourself, using context (amount, cadence, other rows from the same merchant), and re-run
       with the new rules you infer — never edit categories by hand without a rule.
    3. **Summarise.** Call `expense_categorizer__totals_by_category_month` with the categorised rows.
       It returns the category × month pivot, category shares, and the biggest month-over-month
       movers. Lead the report with the three largest movers, not the pivot.
    4. **Find subscriptions.** Call `expense_categorizer__detect_recurring`. It groups by merchant,
       tests for regular cadence and stable amounts, and returns each subscription with its
       annualised cost and last charge date. Flag any subscription with no charge in the last 45 days
       as possibly cancelled, and any two subscriptions in the same category as a consolidation candidate.
    5. **Flag anomalies.** Call `expense_categorizer__flag_anomalies`. It returns duplicates (same
       merchant and amount within 3 days), outliers (more than 3× a merchant's median), large round
       amounts and weekend charges on business cards. Every flag needs a one-line disposition:
       "OK — explained", "refund requested", "ask cardholder".
    6. **Deliver.** With QuickBooks/Xero: create the expense entries with category and memo. With
       Sheets: write the categorised table and the pivot. Otherwise output CSV-ready text.

    ## Frameworks
    - **Category set (business default)**: Revenue, Cost of goods, Payroll, Contractors, Rent,
      Utilities, Software, Marketing, Travel, Meals, Office, Equipment, Insurance, Professional
      services, Bank fees, Taxes, Transfers, Owner draw, Uncategorised. Personal default: Housing,
      Utilities, Groceries, Dining, Transport, Health, Insurance, Subscriptions, Shopping,
      Entertainment, Travel, Income, Transfers, Fees, Uncategorised.
    - **Transfers are not expenses**: card payments, moves between accounts and owner draws are
      excluded from spend totals — the tools do this; keep it that way in the report.
    - **Confidence**: user rule 1.0, exact merchant match 0.9, keyword match 0.7, fuzzy 0.5.
    - **Anomaly thresholds**: duplicate = same merchant + same amount within 3 days; outlier = > 3×
      merchant median and > $50; round = whole hundreds ≥ $500.

    ## Output format
    ```
    # Expense summary — <period> (<n> transactions, <currency>)
    **Spend:** $X · **Income:** $Y · **Transfers excluded:** $Z · **Uncategorised:** n (p%)

    ## Biggest movers vs prior month
    | Category | This month | Prior | Change |

    ## By category
    | Category | <M1> | <M2> | … | Total | Share |

    ## Subscriptions (N, $A/year)
    | Merchant | Amount | Cadence | Last charged | Annualised |

    ## Review
    | Date | Merchant | Amount | Flag | Suggested disposition |

    ## Rules learned (add to your rule list)
    - "<pattern>" → <category>
    ```

    ## Anti-patterns
    - Guessing categories from an unknown merchant string. Mark for review with options.
    - Counting card payments and transfers as spend (double counting).
    - Summing amounts in your head or in prose. Every total comes from the tool.
    - Reporting the pivot without the movers. The reader wants to know what changed.
    - Treating a single charge as a subscription, or missing an annual renewal because it is not monthly.
    """,
)

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y", "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y", "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y", "%Y%m%d"]
DATE_HEADERS = ("date", "transaction date", "posted date", "posting date", "trans date", "booking date", "value date")
DESC_HEADERS = ("description", "memo", "details", "narrative", "payee", "merchant", "name", "transaction", "transaction description")
AMOUNT_HEADERS = ("amount", "transaction amount", "value", "amount (usd)")
DEBIT_HEADERS = ("debit", "withdrawal", "withdrawals", "money out", "paid out", "outflow", "charge")
CREDIT_HEADERS = ("credit", "deposit", "deposits", "money in", "paid in", "inflow", "payment")

NOISE_RE = re.compile(r"(\b\d{2,}\b|#\w+|\*\w*|\bpos\b|\bdebit\b|\bcredit\b|\bpurchase\b|\bcard\b|\bpayment\b|\bonline\b|\bwww\.|\.com\b|\bllc\b|\binc\b|[^\w\s&'-])", re.I)
SPACE_RE = re.compile(r"\s+")


def _parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None


def _merchant(desc: str) -> str:
    cleaned = NOISE_RE.sub(" ", desc)
    words = [w for w in SPACE_RE.sub(" ", cleaned).strip().split(" ") if re.search(r"[A-Za-z&]", w)]
    return " ".join(words[:3]).title() if words else desc.strip()[:40].title()


def _find_col(headers: list[str], names: tuple[str, ...]) -> int | None:
    low = [h.strip().lower() for h in headers]
    for n in names:
        if n in low:
            return low.index(n)
    for i, h in enumerate(low):
        if any(n in h for n in names):
            return i
    return None


@AGENT.tool
def parse_transactions(csv_text: str, spend_is_negative: bool | None = None) -> dict:
    """Parse a bank/card CSV export into normalised rows {date, description, merchant, amount} with spend negative.

    Auto-detects delimiter, header row, date format and amount layout (single signed column or
    debit/credit columns). Reports rows it could not parse instead of dropping them.

    Args:
        csv_text: The raw CSV text (header row recommended). Up to 200k characters / 5,000 rows.
        spend_is_negative: For single-amount exports: true if purchases are negative in the file, false if positive. Leave unset to auto-detect from the mix of signs.
    """
    if not csv_text or not csv_text.strip():
        raise ToolError("csv_text is empty")
    if len(csv_text) > 200_000:
        raise ToolError("csv_text too long (200k chars max) — split the export")
    sample = csv_text[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = "\t" if sample.count("\t") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(csv_text.strip()), delimiter=delim)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ToolError("No rows found")
    if len(rows) > 5001:
        raise ToolError("Too many rows (5,000 max) — split the export")
    headers = rows[0]
    has_header = _parse_date(headers[0]) is None and any(_find_col(headers, n) is not None for n in (DATE_HEADERS, AMOUNT_HEADERS, DEBIT_HEADERS))
    if has_header:
        data = rows[1:]
        di = _find_col(headers, DATE_HEADERS)
        de = _find_col(headers, DESC_HEADERS)
        ai = _find_col(headers, AMOUNT_HEADERS)
        dbi = _find_col(headers, DEBIT_HEADERS)
        cri = _find_col(headers, CREDIT_HEADERS)
        if ai is not None and (dbi == ai or cri == ai):
            dbi = cri = None
    else:
        data = rows
        di, de, ai, dbi, cri = 0, 1, len(rows[0]) - 1, None, None
        for i, cell in enumerate(rows[0]):
            if _parse_date(cell):
                di = i
                break
    if di is None:
        raise ToolError(f"Could not find a date column in headers {headers[:8]}")
    if ai is None and (dbi is None and cri is None):
        # fall back: last numeric column
        ai = len(headers) - 1
    parsed, failures = [], []
    for n, r in enumerate(data, 2 if has_header else 1):
        try:
            d = _parse_date(r[di]) if di < len(r) else None
            if not d:
                raise ValueError(f"bad date {r[di]!r}" if di < len(r) else "missing date")
            desc = r[de].strip() if de is not None and de < len(r) else " ".join(c for i, c in enumerate(r) if i not in (di, ai, dbi, cri)).strip()
            if dbi is not None or cri is not None:
                deb = D(r[dbi], "debit") if dbi is not None and dbi < len(r) and r[dbi].strip() else ZERO
                cre = D(r[cri], "credit") if cri is not None and cri < len(r) and r[cri].strip() else ZERO
                amt = cre - abs(deb)
                layout = "debit/credit"
            else:
                amt = D(r[ai], "amount")
                layout = "signed"
            parsed.append({"line": n, "date": d, "description": desc, "amount": amt, "_layout": layout})
        except Exception as e:  # noqa: BLE001 — report, do not drop
            failures.append({"line": n, "row": r[:6], "error": str(e)[:120]})
    if not parsed:
        raise ToolError(f"No rows parsed; first failure: {failures[0] if failures else 'unknown layout'}")
    layout = parsed[0]["_layout"]
    if layout == "signed":
        neg = sum(1 for p in parsed if p["amount"] < 0)
        pos = sum(1 for p in parsed if p["amount"] > 0)
        if spend_is_negative is None:
            spend_neg = neg >= pos  # most rows in an export are spend
            sign_note = f"auto-detected: {'spend negative' if spend_neg else 'spend positive'} ({neg} negative, {pos} positive rows)" + (" — ambiguous, confirm with the user" if min(neg, pos) > 0.35 * len(parsed) else "")
        else:
            spend_neg = spend_is_negative
            sign_note = "sign convention supplied"
        if not spend_neg:
            for p in parsed:
                p["amount"] = -p["amount"]
    else:
        sign_note = "debit/credit columns: spend negative"
    out_rows = []
    for p in parsed:
        out_rows.append({"line": p["line"], "date": p["date"].isoformat(), "description": p["description"][:200], "merchant": _merchant(p["description"]), "amount": money(p["amount"])})
    spend = sum(-p["amount"] for p in parsed if p["amount"] < 0)
    income = sum(p["amount"] for p in parsed if p["amount"] > 0)
    dates_ = sorted(p["date"] for p in parsed)
    return {
        "rows": out_rows,
        "count": len(out_rows),
        "failed_rows": failures[:50],
        "failed_count": len(failures),
        "date_range": {"from": dates_[0].isoformat(), "to": dates_[-1].isoformat()},
        "layout": {"delimiter": delim, "header": headers if has_header else None, "amounts": layout, "sign_convention": sign_note},
        "total_spend": money(spend),
        "total_income": money(income),
        "verdict": f"Parsed {len(out_rows)} rows ({dates_[0]} to {dates_[-1]}), {len(failures)} failed; spend ${money(spend):,.2f}, income ${money(income):,.2f}. {sign_note}.",
    }


# Built-in merchant/keyword library: (regex, category, confidence). First match wins after user rules.
_LIB = [
    (r"\b(stripe|paypal|square|shopify payout|gumroad|paddle|lemon ?squeezy)\b.*(payout|transfer|deposit)|payout", "Revenue", 0.7),
    (r"\b(payroll|gusto|rippling|justworks|adp|paychex|deel|remote\.com)\b", "Payroll", 0.9),
    (r"\b(upwork|fiverr|toptal|contractor|freelance)\b", "Contractors", 0.8),
    (r"\b(rent|lease|wework|regus|industrious|landlord|property mgmt)\b", "Rent", 0.8),
    (r"\b(electric|pg&e|con ?ed|duke energy|water|gas co|utility|comcast|xfinity|verizon|at&t|t-mobile|spectrum|internet)\b", "Utilities", 0.8),
    (r"\b(aws|amazon web|google cloud|gcp|azure|vercel|netlify|heroku|digitalocean|cloudflare|github|gitlab|atlassian|jira|notion|slack|zoom|figma|adobe|microsoft 365|google workspace|gsuite|dropbox|1password|openai|anthropic|hubspot|salesforce|mailchimp|intercom|zendesk|twilio|sendgrid|datadog|linear|loom|calendly|canva|quickbooks|xero|docusign|zapier|airtable|webflow|squarespace|godaddy|namecheap)\b", "Software", 0.9),
    (r"\b(google ads|adwords|facebook ads|meta ads|fb ads|linkedin ads|twitter ads|tiktok ads|bing ads|semrush|ahrefs|sponsor)\b", "Marketing", 0.9),
    (r"\b(united|delta|american air|southwest|jetblue|alaska air|british airways|lufthansa|ryanair|easyjet|airbnb|marriott|hilton|hyatt|hotel|motel|expedia|booking\.com|hertz|avis|enterprise rent|amtrak|uber(?! eats)|lyft|taxi|parking|toll)\b", "Travel", 0.8),
    (r"\b(doordash|uber eats|grubhub|postmates|deliveroo|restaurant|cafe|coffee|starbucks|chipotle|mcdonald|pizza|sushi|bistro|grill|diner|bar & grill|taco|burger|bakery|deli)\b", "Meals", 0.8),
    (r"\b(staples|office depot|officemax|amazon|amzn|uline|fedex|ups store|usps|postage)\b", "Office", 0.6),
    (r"\b(apple store|apple\.com|best buy|dell|lenovo|b&h|micro center|newegg)\b", "Equipment", 0.7),
    (r"\b(insurance|geico|state farm|allstate|progressive|hiscox|next insurance|blue cross|aetna|cigna|united ?health)\b", "Insurance", 0.9),
    (r"\b(law|legal|attorney|llp|cpa|accountant|accounting|bookkeep|consulting|advisory)\b", "Professional services", 0.7),
    (r"\b(fee|service charge|overdraft|wire fee|monthly maintenance|interest charge|late fee|foreign transaction)\b", "Bank fees", 0.8),
    (r"\b(irs|us treasury|tax|franchise tax|dept of revenue|department of revenue|hmrc|cra)\b", "Taxes", 0.9),
    (r"\b(transfer|xfer|zelle|venmo|cash app|online payment|autopay|card payment|payment thank you|payment received|to savings|from checking|capital one .*payment|chase .*payment|amex .*payment)\b", "Transfers", 0.8),
    (r"\b(owner|draw|distribution|dividend)\b", "Owner draw", 0.6),
    (r"\b(whole foods|trader joe|safeway|kroger|costco|walmart|target|aldi|publix|wegmans|heb|grocery|supermarket|tesco|sainsbury|lidl)\b", "Groceries", 0.8),
    (r"\b(netflix|spotify|hulu|disney\+|hbo|max\b|apple music|youtube premium|audible|kindle|prime video|peloton|nyt|new york times|wsj|substack|patreon)\b", "Subscriptions", 0.9),
    (r"\b(cvs|walgreens|pharmacy|rite aid|dental|dentist|clinic|hospital|medical|doctor|md\b|urgent care|gym|fitness|equinox|planet fitness)\b", "Health", 0.8),
    (r"\b(shell|chevron|exxon|mobil|bp\b|arco|sunoco|gas station|fuel|76\b|wawa|sheetz|circle k|7-eleven|metro|transit|mta|bart|subway(?! sandwich))\b", "Transport", 0.7),
    (r"\b(mortgage|hoa|home depot|lowe'?s|ikea|wayfair)\b", "Housing", 0.7),
    (r"\b(steam|playstation|xbox|nintendo|cinema|amc|regal|ticketmaster|stubhub|concert|theatre|theater)\b", "Entertainment", 0.8),
    (r"\b(nike|adidas|zara|h&m|uniqlo|nordstrom|macy|gap\b|old navy|etsy|ebay|sephora|ulta|lululemon)\b", "Shopping", 0.7),
    (r"\b(salary|direct dep|direct deposit|payroll dep|interest paid|dividend|refund|reimburse)\b", "Income", 0.7),
]
LIB = [(re.compile(p, re.I), c, conf) for p, c, conf in _LIB]
NON_SPEND = {"Transfers", "Revenue", "Income", "Owner draw"}


def _apply_rules(desc: str, merchant: str, amount: Decimal, user_rules: list[tuple[re.Pattern, str]]) -> tuple[str, str, float]:
    hay = f"{desc} {merchant}"
    for pat, cat in user_rules:
        if pat.search(hay):
            return cat, f"user rule /{pat.pattern}/", 1.0
    inbound = ("Income", "Revenue", "Transfers")
    order = ([x for x in LIB if x[1] in inbound] + [x for x in LIB if x[1] not in inbound]) if amount > 0 else LIB
    for pat, cat, conf in order:
        m = pat.search(hay)
        if m:
            if cat in ("Income", "Revenue") and amount < 0:
                continue
            return cat, f"library /{m.group(0)}/", conf
    if amount > 0:
        return "Income", "positive amount, no match", 0.5
    return "Uncategorised", "no match", 0.0


@AGENT.tool
def categorize(transactions: list[dict], rules: list[dict] | None = None) -> dict:
    """Assign a category, matched rule and confidence to every transaction; user rules override the built-in library.

    Args:
        transactions: Rows from parse_transactions: {"date": "YYYY-MM-DD", "description": str, "merchant": str (optional), "amount": number (spend negative)}.
        rules: Optional user rules [{"pattern": "regex or substring", "category": "Software"}], applied first in order.
    """
    rows = bound_rows(transactions, "transactions", limit=5000)
    user_rules = []
    for i, r in enumerate(rules or [], 1):
        if not isinstance(r, dict) or not r.get("pattern") or not r.get("category"):
            raise ToolError(f"rules[{i}] needs 'pattern' and 'category'")
        pat = str(r["pattern"])
        if len(pat) > 120:
            raise ToolError(f"rules[{i}]: pattern too long (120 chars max)")
        try:
            user_rules.append((re.compile(pat, re.I), str(r["category"])))
        except re.error:
            user_rules.append((re.compile(re.escape(pat), re.I), str(r["category"])))
    if len(user_rules) > 300:
        raise ToolError("at most 300 rules")
    out, uncategorised, low_conf = [], [], []
    by_cat = defaultdict(lambda: ZERO)
    cache: dict[tuple[str, bool], tuple[str, str, float]] = {}  # bank exports repeat merchants with varying reference numbers
    for i, t in enumerate(rows, 1):
        if not isinstance(t, dict):
            raise ToolError(f"transactions[{i}] must be an object")
        desc = str(t.get("description", ""))
        merchant = str(t.get("merchant") or _merchant(desc))
        amt = D(t.get("amount", 0), f"transactions[{i}].amount")
        key = (re.sub(r"\d+", "", f"{desc} {merchant}".lower()), amt > 0)
        if key not in cache:
            cache[key] = _apply_rules(desc, merchant, amt, user_rules)
        cat, why, conf = cache[key]
        row = {**t, "merchant": merchant, "amount": money(amt), "category": cat, "rule": why, "confidence": conf}
        out.append(row)
        if cat == "Uncategorised":
            uncategorised.append({"description": desc[:80], "merchant": merchant, "amount": money(amt), "date": t.get("date")})
        elif conf < 0.7:
            low_conf.append({"merchant": merchant, "amount": money(amt), "category": cat, "confidence": conf})
        if cat not in NON_SPEND and amt < 0:
            by_cat[cat] += -amt
    n = len(out)
    unc_pct = ratio_to_pct(Decimal(len(uncategorised)) / n)
    merchants_unc = defaultdict(int)
    for u in uncategorised:
        merchants_unc[u["merchant"]] += 1
    top_unc = sorted(merchants_unc.items(), key=lambda kv: -kv[1])[:10]
    return {
        "rows": out,
        "count": n,
        "uncategorised": uncategorised[:100],
        "uncategorised_count": len(uncategorised),
        "uncategorised_pct": unc_pct,
        "top_uncategorised_merchants": [{"merchant": m, "count": c} for m, c in top_unc],
        "low_confidence": low_conf[:100],
        "spend_by_category": {k: money(v) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
        "verdict": f"{n - len(uncategorised)}/{n} categorised ({unc_pct}% uncategorised; target <3%). " + (f"Write rules for: {', '.join(m for m, _ in top_unc[:5])}." if top_unc else "Nothing left to review."),
    }


@AGENT.tool
def totals_by_category_month(transactions: list[dict], include_income: bool = False) -> dict:
    """Pivot categorised transactions into category × month totals with shares and month-over-month movers.

    Transfers, revenue, income and owner draws are excluded from spend (income shown separately).

    Args:
        transactions: Categorised rows: {"date": "YYYY-MM-DD", "amount": number (spend negative), "category": str}.
        include_income: If true, also return an income pivot by category and month.
    """
    rows = bound_rows(transactions, "transactions", limit=5000)
    pivot: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    income: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    months = set()
    transfers = ZERO
    for i, t in enumerate(rows, 1):
        if not isinstance(t, dict) or not t.get("date"):
            raise ToolError(f"transactions[{i}] needs a date")
        d = _parse_date(str(t["date"]))
        if not d:
            raise ToolError(f"transactions[{i}]: bad date {t['date']!r}")
        m = d.strftime("%Y-%m")
        months.add(m)
        amt = D(t.get("amount", 0), f"transactions[{i}].amount")
        cat = str(t.get("category") or "Uncategorised")
        if cat in NON_SPEND:
            if cat == "Transfers":
                transfers += abs(amt)
            elif amt > 0:
                income[cat][m] += amt
            continue
        if amt < 0:
            pivot[cat][m] += -amt
        elif amt > 0:
            income[cat][m] += amt
    if not pivot and not income:
        raise ToolError("No spend or income rows after excluding transfers")
    months_sorted = sorted(months)
    total_by_month = {m: sum(pivot[c][m] for c in pivot) for m in months_sorted}
    grand = sum(total_by_month.values())
    table = []
    for c in sorted(pivot, key=lambda c: -sum(pivot[c].values())):
        tot = sum(pivot[c].values())
        table.append({"category": c, "by_month": {m: money(pivot[c][m]) for m in months_sorted}, "total": money(tot), "share_pct": ratio_to_pct(tot / grand) if grand else 0.0, "avg_per_month": money(tot / len(months_sorted))})
    movers = []
    if len(months_sorted) >= 2:
        last, prev = months_sorted[-1], months_sorted[-2]
        for c in pivot:
            a, b = pivot[c][last], pivot[c][prev]
            if a == b:
                continue
            movers.append({"category": c, "this_month": money(a), "prior_month": money(b), "change": money(a - b), "change_pct": ratio_to_pct((a - b) / b) if b else None})
        movers.sort(key=lambda x: -abs(x["change"]))
    out = {
        "months": months_sorted,
        "spend_by_month": {m: money(v) for m, v in total_by_month.items()},
        "total_spend": money(grand),
        "avg_monthly_spend": money(grand / len(months_sorted)),
        "transfers_excluded": money(transfers),
        "categories": table,
        "top_movers": movers[:5],
        "verdict": f"${money(grand):,.2f} spend over {len(months_sorted)} month(s) (avg ${money(grand / len(months_sorted)):,.2f}); top category {table[0]['category']} at {table[0]['share_pct']}%." if table else "No spend rows.",
    }
    if movers:
        m0 = movers[0]
        out["verdict"] += f" Biggest mover: {m0['category']} {'+' if m0['change'] > 0 else ''}{m0['change']:,.2f} vs prior month."
    if include_income:
        out["income"] = {c: {m: money(income[c][m]) for m in months_sorted} for c in income}
        out["total_income"] = money(sum(sum(v.values()) for v in income.values()))
    return out


@AGENT.tool
def detect_recurring(transactions: list[dict], min_occurrences: int = 3, amount_tolerance_pct: float = 10) -> dict:
    """Find subscriptions and recurring charges by merchant cadence and amount stability, with annualised cost.

    A merchant is recurring when it has >= min_occurrences charges at a stable interval (weekly,
    monthly, quarterly, annual within ±20% of the period) and amounts within the tolerance of the median.

    Args:
        transactions: Rows {"date": "YYYY-MM-DD", "merchant": str, "description": str, "amount": number (spend negative)}.
        min_occurrences: Minimum charges to count as recurring (default 3; annual renewals need 2).
        amount_tolerance_pct: Allowed variation from the median amount, e.g. 10.
    """
    rows = bound_rows(transactions, "transactions", limit=5000)
    if not 2 <= min_occurrences <= 24:
        raise ToolError("min_occurrences must be 2-24")
    tol = D(amount_tolerance_pct, "amount_tolerance_pct") / 100
    groups: dict[str, list[tuple[date, Decimal]]] = defaultdict(list)
    latest = None
    for i, t in enumerate(rows, 1):
        if not isinstance(t, dict):
            raise ToolError(f"transactions[{i}] must be an object")
        d = _parse_date(str(t.get("date", "")))
        if not d:
            raise ToolError(f"transactions[{i}]: bad or missing date")
        amt = D(t.get("amount", 0), f"transactions[{i}].amount")
        if amt >= 0:
            continue
        merchant = str(t.get("merchant") or _merchant(str(t.get("description", "")))).strip().lower()
        groups[merchant].append((d, -amt))
        latest = d if latest is None or d > latest else latest
    found = []
    cadences = [("weekly", 7), ("biweekly", 14), ("monthly", 30), ("quarterly", 91), ("annual", 365)]
    for merchant, charges in groups.items():
        charges.sort()
        if len(charges) < 2:
            continue
        gaps = [(b[0] - a[0]).days for a, b in zip(charges, charges[1:])]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue
        med_gap = median(gaps)
        cadence = next((name for name, days in cadences if abs(med_gap - days) <= days * 0.2 + 2), None)
        if not cadence:
            continue
        needed = 2 if cadence == "annual" else min_occurrences
        if len(charges) < needed:
            continue
        amounts = [c[1] for c in charges]
        med_amt = Decimal(str(median(amounts)))
        stable = sum(1 for a in amounts if abs(a - med_amt) <= med_amt * tol) / len(amounts)
        if stable < 0.7:
            continue
        per_year = {"weekly": 52, "biweekly": 26, "monthly": 12, "quarterly": 4, "annual": 1}[cadence]
        last = charges[-1][0]
        stale = latest is not None and (latest - last).days > {"weekly": 14, "biweekly": 28, "monthly": 45, "quarterly": 120, "annual": 400}[cadence]
        found.append(
            {
                "merchant": merchant.title(),
                "cadence": cadence,
                "occurrences": len(charges),
                "typical_amount": money(med_amt),
                "annualised": money(med_amt * per_year),
                "first_charged": charges[0][0].isoformat(),
                "last_charged": last.isoformat(),
                "amount_stable_pct": ratio_to_pct(Decimal(str(stable))),
                "possibly_cancelled": stale,
            }
        )
    found.sort(key=lambda x: -x["annualised"])
    total = sum(Decimal(str(f["annualised"])) for f in found if not f["possibly_cancelled"])
    return {
        "recurring": found,
        "count": len(found),
        "annualised_total_active": money(total),
        "monthly_equivalent": money(total / 12),
        "verdict": f"{len(found)} recurring charges; active ones cost ${money(total):,.2f}/year (${money(total / 12):,.2f}/month)." + (f" {sum(1 for f in found if f['possibly_cancelled'])} look cancelled/lapsed." if any(f["possibly_cancelled"] for f in found) else ""),
    }


@AGENT.tool
def flag_anomalies(transactions: list[dict], duplicate_window_days: int = 3, outlier_multiple: float = 3, round_threshold: float = 500, business: bool = False) -> dict:
    """Flag duplicates, per-merchant outliers, large round-number charges and (for business cards) weekend charges.

    Args:
        transactions: Rows {"date": "YYYY-MM-DD", "merchant": str, "description": str, "amount": number (spend negative)}.
        duplicate_window_days: Same merchant + same amount within this many days = duplicate.
        outlier_multiple: Flag a charge above this multiple of the merchant's median (needs >= 3 charges at that merchant).
        round_threshold: Flag whole-hundred amounts at or above this value.
        business: If true, also flag weekend charges for review.
    """
    rows = bound_rows(transactions, "transactions", limit=5000)
    if not 0 <= duplicate_window_days <= 30:
        raise ToolError("duplicate_window_days must be 0-30")
    mult = D(outlier_multiple, "outlier_multiple")
    if mult < 1:
        raise ToolError("outlier_multiple must be >= 1")
    thr = D(round_threshold, "round_threshold")
    items = []
    for i, t in enumerate(rows, 1):
        if not isinstance(t, dict):
            raise ToolError(f"transactions[{i}] must be an object")
        d = _parse_date(str(t.get("date", "")))
        if not d:
            raise ToolError(f"transactions[{i}]: bad or missing date")
        amt = D(t.get("amount", 0), f"transactions[{i}].amount")
        merchant = str(t.get("merchant") or _merchant(str(t.get("description", "")))).strip().lower()
        items.append({"i": i, "date": d, "merchant": merchant, "amount": amt, "description": str(t.get("description", ""))[:80]})
    flags = []
    by_m: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_m[it["merchant"]].append(it)
    for merchant, lst in by_m.items():
        lst.sort(key=lambda x: x["date"])
        same_amount: dict[Decimal, list[dict]] = defaultdict(list)
        for x in lst:
            if x["amount"] < 0:
                same_amount[x["amount"]].append(x)
        for grp in same_amount.values():
            for a, b in zip(grp, grp[1:]):  # already date-sorted: consecutive pairs are the only candidates
                if (b["date"] - a["date"]).days <= duplicate_window_days:
                    flags.append({"type": "duplicate", "merchant": merchant.title(), "amount": money(-a["amount"]), "dates": [a["date"].isoformat(), b["date"].isoformat()], "rows": [a["i"], b["i"]], "disposition": "confirm not double-charged; request refund if so"})
        spends = [-x["amount"] for x in lst if x["amount"] < 0]
        if len(spends) >= 3:
            med = Decimal(str(median(spends)))
            for x in lst:
                v = -x["amount"]
                if x["amount"] < 0 and med > 0 and v > med * mult and v >= 50:
                    flags.append({"type": "outlier", "merchant": merchant.title(), "amount": money(v), "median": money(med), "multiple": float((v / med).quantize(Decimal("0.1"))), "date": x["date"].isoformat(), "rows": [x["i"]], "disposition": "explain: one-off purchase, annual renewal, or error?"})
    for x in items:
        v = -x["amount"]
        if x["amount"] < 0 and v >= thr and v % 100 == 0:
            flags.append({"type": "round_amount", "merchant": x["merchant"].title(), "amount": money(v), "date": x["date"].isoformat(), "rows": [x["i"]], "disposition": "verify invoice/receipt — round amounts are often deposits, retainers or transfers"})
        if business and x["amount"] < 0 and x["date"].weekday() >= 5 and v >= 25:
            flags.append({"type": "weekend", "merchant": x["merchant"].title(), "amount": money(v), "date": x["date"].isoformat(), "rows": [x["i"]], "disposition": "ask cardholder: business purpose?"})
    counts = defaultdict(int)
    for f in flags:
        counts[f["type"]] += 1
    at_risk = sum(Decimal(str(f["amount"])) for f in flags if f["type"] in ("duplicate", "outlier"))
    return {
        "flags": flags[:300],
        "count": len(flags),
        "by_type": dict(counts),
        "amount_at_risk": money(at_risk),
        "verdict": f"{len(flags)} flag(s): " + ", ".join(f"{v} {k}" for k, v in counts.items()) + f"; ${money(at_risk):,.2f} in duplicates/outliers to verify." if flags else "No anomalies by the standard thresholds.",
    }
