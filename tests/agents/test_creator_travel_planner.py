"""Travel Planner tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("travel-planner")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_flight_time_and_jetlag_eastbound():
    out = call("flight_time_and_jetlag", depart_local="2026-11-03 21:35", depart_tz="Europe/London", arrive_local="2026-11-04 17:50", arrive_tz="Asia/Singapore")
    # London is UTC+0 in November, Singapore UTC+8 → 12h15m
    assert out["duration"] == "12h 15m" and out["duration_minutes"] == 735
    assert out["timezone_shift_hours"] == 8.0 and out["direction"] == "east"
    assert out["days_to_adjust"] == 8.0
    assert out["overnight_flight"] is True
    assert "Eastbound" in out["arrival_day_advice"] and "20-min nap" in out["arrival_day_advice"]
    west = call("flight_time_and_jetlag", depart_local="2026-10-10 11:00", depart_tz="America/Los_Angeles", arrive_local="2026-10-11 14:30", arrive_tz="Asia/Tokyo")
    assert west["duration_minutes"] == 11 * 60 + 30  # PDT -7 → JST +9 = 16h shift; but crossing the date line it is 8 zones west
    assert west["direction"] == "west" and west["zones_crossed"] == 8.0
    assert west["days_to_adjust"] == round(8 / 1.5, 1)


def test_flight_time_rejects_backwards_and_bad_tz():
    with pytest.raises(ToolError):
        call("flight_time_and_jetlag", depart_local="2026-11-04 17:50", depart_tz="Asia/Singapore", arrive_local="2026-11-03 21:35", arrive_tz="Europe/London")
    with pytest.raises(ToolError):
        call("flight_time_and_jetlag", depart_local="2026-11-03 21:35", depart_tz="Europe/Londn", arrive_local="2026-11-04 17:50", arrive_tz="Asia/Singapore")


def test_day_planner_usable_hours_and_flags():
    out = call(
        "day_planner",
        start_date="2026-10-10",  # Saturday
        stops=[{"city": "Tokyo", "nights": 3}, {"city": "Hakone", "nights": 1}, {"city": "Kyoto", "nights": 3}],
        arrival_time="15:00",
        departure_time="11:00",
        pace="moderate",
    )
    s = out["schedule"]
    assert out["days"] == 8 and out["nights"] == 7 and out["end"] == "2026-10-17"
    assert s[0]["type"] == "arrival" and s[0]["usable_hours"] == 5.0 and s[0]["max_anchors"] == 1
    assert s[1]["type"] == "full" and s[1]["usable_hours"] == 8.0 and s[1]["max_anchors"] == 3
    assert s[2]["weekday"] == "Mon" and any("Monday" in n for n in s[2]["notes"])
    assert s[3]["city"] == "Hakone" and s[3]["type"] == "transfer" and s[3]["usable_hours"] == 3.5
    assert s[-1]["type"] == "departure" and s[-1]["usable_hours"] == 0.0
    assert any("Hakone: 1-night" in w for w in out["warnings"])
    assert out["full_days"] == 4


def test_day_planner_bad_stops():
    with pytest.raises(ToolError):
        call("day_planner", start_date="2026-10-10", stops=[{"city": "Tokyo", "nights": 0}])
    with pytest.raises(ToolError):
        call("day_planner", start_date="2026-10-10", stops=[{"city": "Tokyo", "nights": 2}], arrival_time="25:00")


def test_trip_budget_totals_and_flags():
    out = call(
        "trip_budget",
        days=10,
        travelers=2,
        items=[
            {"category": "flights", "amount": 900, "per": "person"},
            {"category": "lodging", "amount": 150, "per": "night"},
            {"category": "food", "amount": 50, "per": "person_day"},
            {"category": "transport", "amount": 200, "per": "trip"},
        ],
        contingency_pct=10,
        home_currency_rate=0.92,
        home_currency="EUR",
    )
    assert out["by_category"] == {"flights": 1800.0, "lodging": 1350.0, "food": 1000.0, "transport": 200.0}
    assert out["subtotal"] == 4350.0 and out["contingency"] == 435.0 and out["total"] == 4785.0
    assert out["per_person_per_day"] == round(4785 / 20, 2)
    assert out["home_currency_total"] == round(4785 * 0.92, 2)
    assert out["missing_categories"] == ["activities", "insurance"]
    assert any("Flights + lodging" in f for f in out["flags"])


def test_trip_budget_bad_per():
    with pytest.raises(ToolError):
        call("trip_budget", days=5, travelers=1, items=[{"category": "food", "amount": 20, "per": "hour"}])


def test_connection_check_rules():
    tight = call("connection_check", arrival_time="2026-11-04 08:10", departure_time="2026-11-04 09:00", same_ticket=True, international_arrival=True, international_departure=False)
    assert tight["layover_minutes"] == 50 and tight["minimum_required_minutes"] == 90 and tight["risk"] == "high"
    safe = call("connection_check", arrival_time="2026-11-04 08:10", departure_time="2026-11-04 10:30", same_ticket=True)
    assert safe["risk"] == "low" and safe["margin_minutes"] == 80
    self_transfer = call("connection_check", arrival_time="2026-11-04 08:10", departure_time="2026-11-04 12:00", same_ticket=False, international_arrival=True, checked_bags=True, international_departure=True)
    assert self_transfer["minimum_required_minutes"] == 270 and self_transfer["risk"] == "high"
    with pytest.raises(ToolError):
        call("connection_check", arrival_time="2026-11-04 10:00", departure_time="2026-11-04 09:00")


def test_call_home_window_overlap():
    out = call("call_home_window", date="2026-10-12", here_tz="Asia/Tokyo", home_tz="America/Los_Angeles")
    assert out["hours_ahead_of_home"] == 16.0
    # Tokyo 08:00-22:00 vs LA 08:00-22:00 (16h behind): overlap is Tokyo 08:00-14:00 (= LA 16:00-22:00 previous day)
    assert out["best_window"]["here"] == "08:00-14:00" and out["best_window"]["minutes"] == 360
    assert out["best_window"]["home"].startswith("Sun 16:00")
    with pytest.raises(ToolError):
        call("call_home_window", date="2026-10-12", here_tz="Asia/Tokyo", home_tz="America/Los_Angeles", awake_from="22:00", awake_until="08:00")
