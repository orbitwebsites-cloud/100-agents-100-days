"""Travel Planner — itineraries with real timezone math, honest daily hours, a budget that closes, and safe connections."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Literal

from ...core import Agent, ToolError
from ...lib import dates
from ._common import money, parse_hhmm, parse_local_datetime, pct, tz

AGENT = Agent(
    slug="travel-planner",
    name="Travel Planner",
    category="creator",
    tagline="Itineraries that respect jet lag, opening days and your budget — with timezone math done by code, not vibes.",
    description=(
        "Plans trips like a veteran travel designer: computes real flight durations and jet-lag recovery "
        "across timezones, turns dates and stops into a day-by-day plan with honest usable hours "
        "(arrival and transfer days are not full days), checks layovers against minimum connection "
        "rules, builds a per-person per-day budget with contingency and currency conversion, and "
        "finds the window to call home. Every date, hour and total comes from tools, never guessed."
    ),
    triggers=[
        "plan my trip / itinerary",
        "how bad will the jet lag be / when will I land",
        "is a 55-minute layover enough",
        "budget for 10 days in Japan for two people",
        "day by day plan for Lisbon and Porto",
        "when can I call home from Tokyo",
    ],
    examples=[
        "12 days in Japan, Oct 10-22, flying SFO→Tokyo, want Tokyo, Kyoto and Osaka. Plan it and budget for two.",
        "Departing London 21:35 Nov 3, arriving Singapore 17:50 Nov 4 — how long is the flight and how do I beat the jet lag?",
        "I have 50 minutes in Frankfurt between Lufthansa flights on one ticket, arriving from Boston. Safe?",
    ],
    connectors=["Google Calendar", "Notion", "Google Docs", "Google Maps", "TripIt", "Google Sheets"],
    playbook="""
    ## Standard
    You are a travel designer who has planned hundreds of trips and knows that the itinerary
    that looks best on paper is rarely the one people enjoy. Excellent means: no day is
    over-scheduled, jet lag is planned for rather than suffered, the first and last days are
    treated as half-days, the budget closes with contingency, and every connection is safe.
    The metric that matters is **days that go to plan** — a trip is judged by how many days
    the traveller actually did what was written, without exhaustion or a missed flight.

    ## Intake
    You need: dates (or trip length), origin, destinations in order, travellers, and either a
    total budget or a comfort level (backpacker / mid-range / comfortable). Ask at most 3
    questions and only if you cannot proceed; otherwise assume mid-range, a moderate pace,
    and the traveller's home timezone from the origin. State assumptions and continue.

    ## Procedure
    1. **Fix the timezone facts first.** For every flight with known times call
       `travel_planner__flight_time_and_jetlag`. It gives the true duration, time zones
       crossed, direction, an arrival-day plan (what to do in the first 24 h based on arrival
       hour) and the days needed to adjust. Use its `arrival_day_advice` when writing day 1.
    2. **Check every connection** with `travel_planner__connection_check` — same ticket or
       separate, domestic or international, bags or not. If it says risky, propose the next
       flight or a ticket change before building the itinerary on it.
    3. **Build the day skeleton** with `travel_planner__day_planner`: dates, stops with
       nights, arrival/departure times and pace. It returns each day's usable hours and the
       maximum sensible number of activities, and flags 1-night stops, over-heavy transfer
       ratios, and Mondays/Sundays (many museums close Monday, shops Sunday in much of
       Europe). Fill days in the tool's budget: a "full day" holds 3 anchors at moderate
       pace, not 7.
    4. **Fill each day**: one morning anchor, one afternoon anchor, one evening (dinner
       area), grouped by neighbourhood so transit is under 30 min between anchors. Put the
       must-do item on a full day with a backup day. Book-ahead items (popular museums,
       restaurants, trains) get a "book by" date in the plan.
    5. **Price it** with `travel_planner__trip_budget`: flights, lodging, food, local
       transport, activities, insurance, and the tool's contingency (10% default). If the
       traveller gave a total, compare; if over, cut lodging category or nights, not food.
    6. **Practicalities**: when someone needs to stay in touch, call
       `travel_planner__call_home_window` for the hours that work in both places. Add visa /
       entry requirement reminders as "verify with the official source" — never assert them.
    7. **Deliver** in the output format, then offer to create calendar events (Google
       Calendar) or a Notion/Docs page if connected.

    ## Frameworks
    - **Half-day rule:** arrival day = usable from arrival + 2 h; departure day = until
      departure − 3 h (international) / − 2 h (domestic). Transfer days between cities lose
      4-5 h door-to-door even for a 2-h train.
    - **Pace:** relaxed 2 anchors/day, moderate 3, packed 4. Over 4 is a checklist, not a trip.
    - **Jet lag:** the body shifts about 1 h/day eastward and ~1.5 h/day westward; anything
      over 3 zones needs a plan. East: morning light, no naps over 20 min, dinner and bed at
      local time from day 1. West: evening light, stay up until 22:00 local.
    - **Minimum connections (default rules):** same ticket domestic 60 min, international
      90-120 min (more if a terminal change or immigration on arrival); separate tickets with
      bags 3 h+ (you reclaim, re-check, re-clear security). Under those numbers, book the
      next flight.
    - **Stops:** 3 nights minimum per city unless it is a deliberate stopover; 1-night stops
      cost half a day each side in packing and transit.
    - **Budget structure:** flights + lodging ≈ 50-60% of most mid-range trips; food and
      activities are the flexible part; contingency 10% (15% for first-time destinations).

    ## Output format
    ```
    # <Destination(s)> — <dates> (<N> nights) · <travellers> · <pace>
    **Flights:** <route, duration, zones crossed, jet-lag plan in one line>
    **Budget:** <total> (<per person/day>) incl. <n>% contingency vs <stated budget>

    ## Day by day
    | Day | Date | City | Usable hrs | Plan (morning / afternoon / evening) | Book by |
    |---|---|---|---|---|---|
    (arrival, transfer and departure days marked; closures noted)

    ## Book-ahead list
    - <item> — book by <date> (<why>)

    ## Budget
    | Category | Total | Per person | Per day | Notes |

    ## Practical
    Call-home window · Connections check · Verify entry requirements at <official source>
    ```

    ## Anti-patterns
    - Treating arrival day as a full day after a 12-hour eastbound flight.
    - "Day 4: Kyoto — Fushimi Inari, Arashiyama, Gion, Nijo, Nishiki, Kinkaku-ji" — six anchors across four districts.
    - Guessing flight durations or arrival times from departure + "about 11 hours". Use the tool.
    - A 45-minute international connection on separate tickets called "tight but doable".
    - A budget with no contingency and no insurance line.
    - Asserting visa rules from memory. Point to the official source and flag it.
    """,
)


@AGENT.tool
def flight_time_and_jetlag(depart_local: str, depart_tz: str, arrive_local: str, arrive_tz: str) -> dict:
    """Compute a flight's true duration, time zones crossed, jet-lag recovery days and a first-24-hours plan from local times.

    Args:
        depart_local: Departure date and time in the departure city's local time, e.g. "2026-11-03 21:35".
        depart_tz: IANA timezone of the departure airport, e.g. "Europe/London".
        arrive_local: Arrival date and time in the arrival city's local time, e.g. "2026-11-04 17:50".
        arrive_tz: IANA timezone of the arrival airport, e.g. "Asia/Singapore".
    """
    dep = parse_local_datetime(depart_local, depart_tz)
    arr = parse_local_datetime(arrive_local, arrive_tz)
    duration = arr - dep
    minutes = int(duration.total_seconds() // 60)
    if minutes <= 0:
        raise ToolError("Arrival is not after departure once timezones are applied — check the dates/times.")
    if minutes > 40 * 60:
        raise ToolError("Duration over 40 hours — check the dates; multi-leg trips should be entered per flight.")
    dep_off = dep.utcoffset().total_seconds() / 3600
    arr_off = arr.utcoffset().total_seconds() / 3600
    shift = arr_off - dep_off
    if shift > 12:
        shift -= 24
    elif shift < -12:
        shift += 24
    zones = abs(shift)
    direction = "east" if shift > 0 else "west" if shift < 0 else "none"
    if zones < 1:
        recovery_days = 0.0
    elif direction == "east":
        recovery_days = round(zones / 1.0, 1)
    else:
        recovery_days = round(zones / 1.5, 1)
    arr_hour = arr.hour
    overnight = dep.hour >= 20 or (dep + duration).day != dep.day and minutes >= 6 * 60
    if zones < 3:
        advice = "Under 3 zones: keep local meal times and you will adjust within a day."
    elif direction == "east":
        advice = "Eastbound is the hard direction: get outdoor light in the destination morning, avoid light after 20:00 for 2-3 days, no naps over 20 min, and eat dinner on local time from day 1. "
    else:
        advice = "Westbound: seek late-afternoon/evening light, stay up until at least 22:00 local, and avoid bright light in the early morning for 2-3 days. "
    if zones >= 3:
        if 5 <= arr_hour < 12:
            advice += f"You land at {arr.strftime('%H:%M')}: shower, get outside, light lunch, no nap — bed at 21:30-22:00 local."
        elif 12 <= arr_hour < 18:
            advice += f"You land at {arr.strftime('%H:%M')}: one 20-min nap max, walk, early dinner, bed by 22:30."
        else:
            advice += f"You land at {arr.strftime('%H:%M')}: go straight to bed on local time; set an alarm for 07:30 and get morning light."
    if overnight and zones >= 3:
        advice += " Sleep on the plane from the destination's night hours; set your watch on boarding."
    return {
        "departure_utc": dep.astimezone(tz("UTC")).strftime("%Y-%m-%d %H:%M UTC"),
        "arrival_utc": arr.astimezone(tz("UTC")).strftime("%Y-%m-%d %H:%M UTC"),
        "duration_minutes": minutes,
        "duration": f"{minutes // 60}h {minutes % 60:02d}m",
        "timezone_shift_hours": round(shift, 1),
        "zones_crossed": round(zones, 1),
        "direction": direction,
        "overnight_flight": bool(overnight),
        "arrival_local_hour": arr_hour,
        "arrival_weekday": arr.strftime("%A"),
        "days_to_adjust": recovery_days,
        "calendar_days_elapsed": (arr.date() - dep.date()).days,
        "arrival_day_advice": advice.strip(),
        "summary": f"{minutes // 60}h {minutes % 60:02d}m flight, {zones:g} zones {direction}; ~{recovery_days:g} day(s) to adjust; arrive {arr.strftime('%a %H:%M')} local.",
    }


PACE_HOURS = {"relaxed": (6, 2), "moderate": (8, 3), "packed": (10, 4)}


@AGENT.tool
def day_planner(
    start_date: str,
    stops: list[dict],
    arrival_time: str = "15:00",
    departure_time: str = "12:00",
    pace: Literal["relaxed", "moderate", "packed"] = "moderate",
    international_departure: bool = True,
    transfer_hours: float = 4.5,
) -> dict:
    """Turn dates and stops into a day-by-day skeleton with usable hours per day, activity caps and closure warnings.

    Arrival day counts from arrival + 2 h, departure day ends 3 h (international) / 2 h before
    departure, transfer days lose the transfer time; Mondays and Sundays are flagged for closures.

    Args:
        start_date: Arrival date at the first stop, YYYY-MM-DD.
        stops: Ordered list of {"city": "Tokyo", "nights": 4}; the trip ends the morning after the last night.
        arrival_time: Local arrival time at the first stop, HH:MM (default 15:00).
        departure_time: Local departure time on the final day, HH:MM (default 12:00).
        pace: relaxed (2 anchors/day), moderate (3, default) or packed (4).
        international_departure: Whether the final flight is international (3 h airport buffer vs 2 h).
        transfer_hours: Door-to-door hours lost on a city-to-city transfer day (default 4.5).
    """
    start = dates.parse_date(start_date)
    if not stops or len(stops) > 30:
        raise ToolError("Give 1-30 stops")
    ah, am = parse_hhmm(arrival_time)
    dh, dm = parse_hhmm(departure_time)
    if not 0 <= transfer_hours <= 16:
        raise ToolError("transfer_hours must be 0-16")
    full_hours, anchors = PACE_HOURS[pace]
    total_nights = 0
    parsed = []
    for i, s in enumerate(stops, 1):
        if not isinstance(s, dict) or not s.get("city"):
            raise ToolError(f"stop #{i} needs a 'city'")
        n = s.get("nights", 0)
        if not isinstance(n, int) or n < 1 or n > 60:
            raise ToolError(f"{s['city']}: nights must be an integer 1-60")
        parsed.append((str(s["city"]).strip(), n))
        total_nights += n
    if total_nights > 120:
        raise ToolError("Trip over 120 nights — split it")
    rows, warnings = [], []
    day_n = 0
    d = start
    for si, (city, nights) in enumerate(parsed):
        for k in range(nights):
            day_n += 1
            is_arrival = si == 0 and k == 0
            is_transfer = si > 0 and k == 0
            if is_arrival:
                usable = max(0.0, 22 - (ah + am / 60 + 2))
                kind = "arrival"
            elif is_transfer:
                usable = max(0.0, full_hours - transfer_hours)
                kind = "transfer"
            else:
                usable = float(full_hours)
                kind = "full"
            cap = max(0, min(anchors, int(usable // (full_hours / anchors)))) if usable > 0 else 0
            notes = []
            if d.weekday() == 0:
                notes.append("Monday: many museums closed — verify the anchor's opening days.")
            if d.weekday() == 6:
                notes.append("Sunday: reduced shop/transit hours in many places.")
            rows.append({"day": day_n, "date": d.isoformat(), "weekday": d.strftime("%a"), "city": city, "type": kind, "usable_hours": round(usable, 1), "max_anchors": cap, "notes": notes})
            d += timedelta(days=1)
        if nights == 1:
            warnings.append(f"{city}: 1-night stop — costs half a day each side in packing/transit; consider a day trip instead.")
    # departure day
    day_n += 1
    buffer = 3 if international_departure else 2
    usable = max(0.0, (dh + dm / 60) - buffer - 8)
    rows.append({"day": day_n, "date": d.isoformat(), "weekday": d.strftime("%a"), "city": parsed[-1][0], "type": "departure", "usable_hours": round(usable, 1), "max_anchors": min(anchors, int(usable // (full_hours / anchors))) if usable > 0 else 0, "notes": [f"Leave for the airport by {int(dh + dm / 60 - buffer):02d}:{dm:02d}."]})
    full_days = sum(1 for r in rows if r["type"] == "full")
    partial = len(rows) - full_days
    if partial / len(rows) > 0.4 and len(rows) >= 4:
        warnings.append(f"{partial} of {len(rows)} days are arrival/transfer/departure days — too many moves for the length; drop a stop.")
    total_usable = sum(r["usable_hours"] for r in rows)
    by_city: dict[str, float] = defaultdict(float)
    for r in rows:
        by_city[r["city"]] += r["usable_hours"]
    return {
        "start": start.isoformat(),
        "end": d.isoformat(),
        "nights": total_nights,
        "days": len(rows),
        "full_days": full_days,
        "pace": pace,
        "anchors_per_full_day": anchors,
        "total_usable_hours": round(total_usable, 1),
        "usable_hours_by_city": {c: round(h, 1) for c, h in by_city.items()},
        "total_anchor_slots": sum(r["max_anchors"] for r in rows),
        "schedule": rows,
        "warnings": warnings,
        "summary": f"{len(rows)} days / {total_nights} nights across {len(parsed)} stop(s): {full_days} full days, {total_usable:.0f} usable hours, room for ~{sum(r['max_anchors'] for r in rows)} anchors at {pace} pace.",
    }


CATEGORIES_EXPECTED = ["flights", "lodging", "food", "transport", "activities", "insurance"]


@AGENT.tool
def trip_budget(days: int, travelers: int, items: list[dict], contingency_pct: float = 10, home_currency_rate: float = 1.0, home_currency: str = "") -> dict:
    """Total a trip budget from mixed per-trip / per-day / per-person lines, add contingency, convert to home currency, and flag missing categories.

    Args:
        days: Trip length in days.
        travelers: Number of travellers.
        items: Lines like {"category": "lodging", "amount": 140, "per": "day"} where per is trip, day, person or person_day (amount is in the trip currency).
        contingency_pct: Contingency to add on top, percent (default 10; use 15 for first-time destinations).
        home_currency_rate: Multiply trip-currency totals by this to get home currency (1.0 = same currency).
        home_currency: Label for the home currency in the output (e.g. "USD").
    """
    if days < 1 or days > 365:
        raise ToolError("days must be 1-365")
    if travelers < 1 or travelers > 50:
        raise ToolError("travelers must be 1-50")
    if not 0 <= contingency_pct <= 50:
        raise ToolError("contingency_pct must be 0-50")
    if home_currency_rate <= 0:
        raise ToolError("home_currency_rate must be > 0")
    if not items or len(items) > 200:
        raise ToolError("Give 1-200 budget lines")
    by_cat: dict[str, float] = defaultdict(float)
    lines = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict) or not it.get("category"):
            raise ToolError(f"line #{i} needs a 'category'")
        try:
            amt = float(it.get("amount", 0))
        except (TypeError, ValueError):
            raise ToolError(f"{it['category']}: amount must be a number") from None
        if amt < 0:
            raise ToolError(f"{it['category']}: amount cannot be negative")
        per = str(it.get("per", "trip")).lower()
        mult = {"trip": 1, "day": days, "person": travelers, "person_day": days * travelers, "night": days - 1 if days > 1 else 1}.get(per)
        if mult is None:
            raise ToolError(f"{it['category']}: per must be trip, day, night, person or person_day")
        total = amt * mult
        cat = str(it["category"]).strip().lower()
        by_cat[cat] += total
        lines.append({"category": cat, "amount": amt, "per": per, "total": money(total)})
    subtotal = sum(by_cat.values())
    contingency = subtotal * contingency_pct / 100
    grand = subtotal + contingency
    missing = [c for c in CATEGORIES_EXPECTED if not any(c in k for k in by_cat)]
    flags = []
    if missing:
        flags.append("No line for: " + ", ".join(missing) + ". Add them or state they are covered.")
    share = {c: pct(v, subtotal) for c, v in sorted(by_cat.items(), key=lambda kv: -kv[1])}
    fixed = sum(v for k, v in by_cat.items() if "flight" in k or "lodging" in k or "hotel" in k)
    if subtotal and fixed / subtotal > 0.7:
        flags.append(f"Flights + lodging are {pct(fixed, subtotal)}% of the budget — little left for food/activities; reconsider lodging tier.")
    return {
        "days": days,
        "travelers": travelers,
        "lines": lines,
        "by_category": {c: money(v) for c, v in by_cat.items()},
        "category_share_pct": share,
        "subtotal": money(subtotal),
        "contingency": money(contingency),
        "total": money(grand),
        "per_person": money(grand / travelers),
        "per_day": money(grand / days),
        "per_person_per_day": money(grand / travelers / days),
        "home_currency_total": money(grand * home_currency_rate) if home_currency_rate != 1 else None,
        "home_currency": home_currency or None,
        "missing_categories": missing,
        "flags": flags,
        "verdict": f"{grand:,.0f} total incl. {contingency_pct:g}% contingency = {grand / travelers / days:,.0f} per person per day" + (f" (≈ {grand * home_currency_rate:,.0f} {home_currency})" if home_currency_rate != 1 else "") + ("; " + " ".join(flags) if flags else "."),
    }


@AGENT.tool
def connection_check(
    arrival_time: str,
    departure_time: str,
    same_ticket: bool = True,
    international_arrival: bool = False,
    international_departure: bool = False,
    checked_bags: bool = True,
    terminal_change: bool = False,
    immigration_on_arrival: bool = False,
) -> dict:
    """Judge whether a layover is safe using minimum-connection rules for ticket type, bags, immigration and terminal changes.

    Args:
        arrival_time: Scheduled arrival of the inbound flight, "YYYY-MM-DD HH:MM" local at the connecting airport.
        departure_time: Scheduled departure of the outbound flight, same format and airport.
        same_ticket: True if both flights are on one booking (protected connection); False for self-transfer.
        international_arrival: Inbound flight is international.
        international_departure: Outbound flight is international.
        checked_bags: Travelling with checked luggage.
        terminal_change: The connection requires changing terminals.
        immigration_on_arrival: You must clear immigration/customs at the connecting airport (e.g. first entry to the US/UK, or Schengen entry).
    """
    arr = parse_local_datetime(arrival_time, "UTC")
    dep = parse_local_datetime(departure_time, "UTC")
    layover = int((dep - arr).total_seconds() // 60)
    if layover <= 0:
        raise ToolError("Departure must be after arrival.")
    if layover > 48 * 60:
        raise ToolError("Layover over 48 hours — that's a stopover, not a connection.")
    if same_ticket:
        base = 60
        if international_arrival or international_departure:
            base = 90
        if international_arrival and international_departure:
            base = 120
        reasons = [f"same-ticket {'international' if base >= 90 else 'domestic'} connection: {base} min baseline"]
        if terminal_change:
            base += 30
            reasons.append("+30 terminal change")
        if immigration_on_arrival:
            base += 60
            reasons.append("+60 immigration/customs (and bag re-check where required)")
    else:
        base = 120
        reasons = ["separate tickets: 120 min baseline (no protection if the first flight is late)"]
        if checked_bags:
            base += 60
            reasons.append("+60 reclaim and re-check bags")
        if immigration_on_arrival or international_arrival:
            base += 60
            reasons.append("+60 immigration/customs")
        if international_departure:
            base += 30
            reasons.append("+30 international check-in cut-off")
        if terminal_change:
            base += 30
            reasons.append("+30 terminal change")
    margin = layover - base
    if margin < 0:
        verdict, risk = f"Too short: {layover} min vs {base} min minimum. Book the next departure or a single ticket.", "high"
    elif margin < 30:
        verdict, risk = f"Legal but tight: {layover} min vs {base} min minimum; any delay over {margin} min breaks it.", "medium"
    elif layover > 6 * 60:
        verdict, risk = f"Long layover ({layover // 60}h {layover % 60:02d}m): safe; consider leaving the airport if entry rules allow.", "low"
    else:
        verdict, risk = f"Safe: {layover} min with {margin} min to spare over the {base} min minimum.", "low"
    if not same_ticket and risk != "high":
        verdict += " Separate tickets: buy the second with a flexible fare or travel insurance covering missed connections."
    return {
        "layover_minutes": layover,
        "layover": f"{layover // 60}h {layover % 60:02d}m",
        "minimum_required_minutes": base,
        "margin_minutes": margin,
        "risk": risk,
        "rules_applied": reasons,
        "overnight": arr.date() != dep.date(),
        "verdict": verdict,
    }


@AGENT.tool
def call_home_window(date: str, here_tz: str, home_tz: str, awake_from: str = "08:00", awake_until: str = "22:00") -> dict:
    """Find the hours on a given date when it is reasonable to call between two timezones (both sides awake).

    Args:
        date: The date at your current location, YYYY-MM-DD.
        here_tz: IANA timezone where you are (e.g. "Asia/Tokyo").
        home_tz: IANA timezone of the person you're calling (e.g. "America/Los_Angeles").
        awake_from: Earliest acceptable local hour for either side, HH:MM (default 08:00).
        awake_until: Latest acceptable local hour for either side, HH:MM (default 22:00).
    """
    day = dates.parse_date(date)
    zh, zo = tz(here_tz), tz(home_tz)
    f_h, f_m = parse_hhmm(awake_from)
    u_h, u_m = parse_hhmm(awake_until)
    if (u_h, u_m) <= (f_h, f_m):
        raise ToolError("awake_until must be after awake_from")
    start = datetime(day.year, day.month, day.day, 0, 0, tzinfo=zh)
    windows, current = [], None
    for q in range(0, 24 * 4):
        t = start + timedelta(minutes=15 * q)
        home = t.astimezone(zo)
        ok = (f_h, f_m) <= (t.hour, t.minute) < (u_h, u_m) and (f_h, f_m) <= (home.hour, home.minute) < (u_h, u_m)
        if ok and current is None:
            current = t
        elif not ok and current is not None:
            windows.append((current, t))
            current = None
    if current is not None:
        windows.append((current, start + timedelta(days=1)))
    offset = (start.utcoffset() - start.astimezone(zo).utcoffset()).total_seconds() / 3600
    out = [{
        "here": f"{a.strftime('%H:%M')}-{b.strftime('%H:%M')}",
        "home": f"{a.astimezone(zo).strftime('%a %H:%M')}-{b.astimezone(zo).strftime('%H:%M')}",
        "minutes": int((b - a).total_seconds() // 60),
    } for a, b in windows]
    best = max(out, key=lambda w: w["minutes"]) if out else None
    return {
        "date": day.isoformat(),
        "here_tz": here_tz,
        "home_tz": home_tz,
        "hours_ahead_of_home": round(offset, 1),
        "windows": out,
        "best_window": best,
        "summary": (f"{here_tz} is {abs(offset):g}h {'ahead of' if offset > 0 else 'behind'} {home_tz}; " if offset else "Same time; ") + (f"best window {best['here']} your time = {best['home']} at home." if best else "no overlap within the awake hours — shift one side's window."),
    }
