"""Meal Planner tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("meal-planner")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_scale_recipe_converts_and_flags():
    out = call(
        "scale_recipe",
        ingredients=[{"name": "olive oil", "qty": 2, "unit": "tbsp"}, {"name": "salt", "qty": 1, "unit": "tsp"}, {"name": "chicken thigh", "qty": 500, "unit": "g"}, {"name": "onion", "qty": 1, "unit": "each"}],
        from_servings=4,
        to_servings=10,
    )
    assert out["factor"] == 2.5
    rows = {r["name"]: r for r in out["ingredients"]}
    assert rows["olive oil"]["display"] == "5 tbsp"
    assert rows["salt"]["display"] == "2 ½ tsp" and rows["salt"]["display_conservative"] == "2 tsp"
    assert rows["chicken thigh"]["display"] == "1250 g"
    assert rows["onion"]["display"] == "2 ½ each"
    assert any("pan size" in w for w in out["warnings"])
    cup = call("scale_recipe", ingredients=[{"name": "stock", "qty": 4, "unit": "tbsp"}], from_servings=1, to_servings=4)
    assert cup["ingredients"][0]["display"] == "1 cup"


def test_scale_recipe_bad_input():
    with pytest.raises(ToolError):
        call("scale_recipe", ingredients=[{"name": "x", "qty": "two", "unit": "g"}], from_servings=2, to_servings=4)
    with pytest.raises(ToolError):
        call("scale_recipe", ingredients=[{"name": "x", "qty": 1}], from_servings=0, to_servings=4)


def test_grocery_list_merges_units_and_pantry():
    out = call(
        "grocery_list",
        recipes=[
            {"name": "Chili", "ingredients": [{"name": "onions, diced", "qty": 2, "unit": "each"}, {"name": "ground beef", "qty": 1, "unit": "lb"}, {"name": "olive oil", "qty": 2, "unit": "tbsp"}]},
            {"name": "Curry", "ingredients": [{"name": "onion", "qty": 1, "unit": "each"}, {"name": "ground beef", "qty": 300, "unit": "g"}, {"name": "coconut milk", "qty": 400, "unit": "ml"}]},
        ],
        pantry=["olive oil"],
    )
    produce = {r["item"]: r for r in out["by_aisle"]["produce"]}
    assert produce["onion"]["qty"] == 3 and produce["onion"]["used_in"] == ["Chili", "Curry"]
    meat = {r["item"]: r for r in out["by_aisle"]["meat & fish"]}
    assert meat["ground beef"]["qty"] == round(453.592 + 300, 2) and meat["ground beef"]["display"] == "754 g (1.66 lb)"
    assert out["skipped_from_pantry"] == ["olive oil"]
    assert out["items"] == 3 and out["merged_away"] == 2
    assert out["checklist"][0] == "[ ] onion: 3"
    assert {r["item"] for r in out["by_aisle"]["pantry"]} == {"coconut milk"}


def test_grocery_list_bad_input():
    with pytest.raises(ToolError):
        call("grocery_list", recipes=[{"name": "x"}])


def test_split_macros_checks_449_and_floors():
    out = call("split_macros", calories=2100, protein_g=160, carbs_g=210, fat_g=70, meals=4, pattern="post_workout", bodyweight_kg=80)
    assert out["daily"]["kcal_from_macros"] == 160 * 4 + 210 * 4 + 70 * 9
    assert out["flags"] == []
    assert [m["protein_g"] for m in out["meals"]] == [40, 40, 40, 40]
    assert out["meals"][1]["carbs_g"] > out["meals"][0]["carbs_g"]
    assert abs(sum(m["kcal"] for m in out["meals"]) - out["daily"]["kcal_from_macros"]) <= 4
    bad = call("split_macros", calories=1000, protein_g=40, carbs_g=60, fat_g=30, meals=3)
    assert any("floor" in f for f in bad["flags"]) and any("4/4/9" in f for f in bad["flags"]) and any("Protein per meal" in f for f in bad["flags"])


def test_split_macros_bad_meals():
    with pytest.raises(ToolError):
        call("split_macros", calories=2000, protein_g=150, carbs_g=200, fat_g=60, meals=1)


def test_nutrition_totals_and_label_check():
    out = call(
        "nutrition_totals",
        items=[
            {"name": "Greek yogurt", "servings": 2, "calories": 100, "protein_g": 17, "carbs_g": 6, "fat_g": 0, "fiber_g": 0, "sodium_mg": 60},
            {"name": "Mystery bar", "servings": 1, "calories": 200, "protein_g": 40, "carbs_g": 60, "fat_g": 30},
        ],
        protein_target_g=160,
        calorie_target=2100,
    )
    assert out["totals"]["calories"] == 400 and out["totals"]["protein_g"] == 74
    assert "label_check" in out["items"][1]
    assert any("Mystery bar" in f for f in out["flags"]) and any("short of 160" in f for f in out["flags"])
    assert out["vs_targets"]["protein_gap_g"] == -86


def test_nutrition_totals_bad_input():
    with pytest.raises(ToolError):
        call("nutrition_totals", items=[{"name": "x", "calories": -5}])


def test_cost_per_serving_budget_and_coverage():
    out = call(
        "cost_per_serving",
        recipes=[{"name": "Chili", "cost": 18.40, "servings": 8}, {"name": "Salmon bowls", "cost": 30, "servings": 4}, {"name": "Oats", "cost": 5, "servings": 7}],
        people=1,
        days=7,
        weekly_budget=45,
        meals_per_day=3,
    )
    assert out["total_cost"] == 53.4
    assert out["recipes"][0]["name"] == "Salmon bowls" and out["recipes"][0]["cost_per_serving"] == 7.5
    assert out["cost_per_person_per_day"] == round(53.4 / 7, 2)
    assert out["servings_needed"] == 21 and any("add 2 servings" in f for f in out["flags"])
    assert any("Over budget by 8.40" in f and "Salmon bowls" in f for f in out["flags"])


def test_cost_per_serving_bad_input():
    with pytest.raises(ToolError):
        call("cost_per_serving", recipes=[{"name": "x", "cost": 5, "servings": 0}])


def test_grocery_list_count_units_do_not_cross_merge_and_pantry_is_exact():
    out = call(
        "grocery_list",
        recipes=[
            {"name": "A", "ingredients": [{"name": "garlic", "qty": 1, "unit": "head"}, {"name": "red bell pepper", "qty": 1, "unit": "each"}, {"name": "unsalted butter", "qty": 2, "unit": "tbsp"}]},
            {"name": "B", "ingredients": [{"name": "garlic cloves", "qty": 3, "unit": ""}, {"name": "ground cumin", "qty": 1, "unit": "tsp"}]},
        ],
        pantry=["salt", "pepper"],
    )
    rows = [(r["item"], r["display"]) for v in out["by_aisle"].values() for r in v]
    assert ("garlic", "1 head") in rows and ("garlic", "3 cloves") in rows  # a head is not a clove
    assert any(i == "red bell pepper" for i, _ in rows) and any(i == "unsalted butter" for i, _ in rows)  # no substring pantry skips
    assert out["skipped_from_pantry"] == [] and any("red bell pepper" in c for c in out["check_pantry"])
    assert {r["item"] for r in out["by_aisle"]["pantry"]} == {"ground cumin"}
