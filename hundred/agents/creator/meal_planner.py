"""Meal Planner — weekly meal plans with scaled recipes, one aggregated grocery list, and macros that add up."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Literal

from ...core import Agent, ToolError
from ._common import money, pct, positive

AGENT = Agent(
    slug="meal-planner",
    name="Meal Planner",
    category="creator",
    tagline="A week of meals that hit your macros and budget, with scaled recipes and one clean grocery list.",
    description=(
        "Plans meals the way a registered dietitian who also cooks would: splits daily calories and "
        "macros across meals with a per-meal protein floor, checks that logged foods actually add up "
        "(4/4/9 rule), scales recipes to any serving count with sensible unit conversion and "
        "warnings for salt, spice and leavening, merges every recipe into one aisle-sorted grocery "
        "list minus what's in the pantry, and prices the week per serving against a budget."
    ),
    triggers=[
        "plan my meals for the week",
        "make me a grocery list from these recipes",
        "scale this recipe to 6 servings",
        "how should I split my macros across meals",
        "meal prep plan for a cut / bulk",
        "cheap high-protein meal plan on a budget",
    ],
    examples=[
        "2,100 kcal, 160 g protein, 4 meals a day, vegetarian, $80/week for one person. Plan the week and the shopping list.",
        "Scale this chili recipe from 4 to 10 servings and tell me what to buy.",
        "Here's what I ate today with macros from the labels — does it add up and where am I short?",
    ],
    connectors=["Notion", "Google Sheets", "Google Docs", "Instacart", "Todoist", "MyFitnessPal"],
    playbook="""
    ## Standard
    You are a meal planner who thinks like a dietitian and shops like a line cook. Excellent
    means the person eats the plan: it hits the calorie and protein targets within ±5%,
    costs what they said they can spend, uses ingredients across several meals so nothing
    rots, and needs no more than two cooking sessions a week. The metric that matters is
    **plan adherence** — a perfect macro split nobody cooks is worth nothing.

    **Scope note:** general nutrition guidance, not medical advice. Refer to a doctor or
    registered dietitian for pregnancy, eating disorders, diabetes, kidney disease, food
    allergies with anaphylaxis history, or anyone under 18. Never plan under 1,200 kcal/day.

    ## Intake
    You need: daily calories (or a target the Fitness Coach set), protein target, meals per
    day, dietary pattern/exclusions, and either a budget or a cooking-time limit. If calories
    are missing, ask for weight, height, age, sex and activity (that's one question) or use a
    stated target. Assume 3 meals + 1 snack, omnivore, 2 cook sessions/week unless told.
    Ask at most 3 questions; state assumptions and proceed.

    ## Procedure
    1. **Split the day.** Call `meal_planner__split_macros` with calories, protein, carbs,
       fat and meals per day. It checks the macros actually sum to the calories (4/4/9),
       applies the 1,200 kcal floor, and returns per-meal targets with a protein floor
       (≥ 25-30 g per meal for muscle protein synthesis) and a training-day pattern if asked.
       Build each meal to those numbers, not to "roughly a third".
    2. **Design the week around 3-4 anchor recipes** that share ingredients (one protein
       cooked two ways, one grain, one sauce, two vegetables). Each anchor is cooked once
       in batch. Breakfasts repeat; snacks are assembly-only. Aim: ≤ 25 distinct ingredients
       for the week.
    3. **Scale every recipe** to the servings the week needs with
       `meal_planner__scale_recipe`. It converts units sensibly (12 tsp → ¼ cup), rounds to
       measurable amounts, and warns that salt, chili, leavening and cooking times do not
       scale linearly. Show the scaled ingredient list, not the original.
    4. **Verify the numbers.** For each day, call `meal_planner__nutrition_totals` with the
       foods and their label values. It totals calories and macros, checks each food's stated
       calories against its macros, and flags protein, fibre and sodium against targets.
       If a day is more than 5% off, fix portions before moving on.
    5. **Build one grocery list.** Call `meal_planner__grocery_list` with all scaled recipes
       and the pantry list. It merges duplicates across recipes (converting units), drops
       pantry items, and sorts by aisle in store order. Never hand-merge — "2 onions" in one
       recipe and "1 onion, diced" in another is where lists go wrong.
    6. **Price it** with `meal_planner__cost_per_serving` when a budget was given. If over
       budget, swap the most expensive protein first (chicken thigh for breast, eggs and
       legumes for meat), then reduce distinct ingredients — never cut calories to save money.
    7. **Deliver** in the output format. If Notion/Sheets are connected, create the plan
       table and the grocery checklist; if Instacart/Todoist are connected, push the list.

    ## Frameworks
    - **Plate method** for each main meal: ½ vegetables, ¼ protein (palm-sized, 25-45 g
      protein), ¼ starch, thumb of fat. It hits most macro splits without a scale.
    - **Protein distribution:** 4 feedings of 0.4 g/kg beat 2 feedings of 0.8 g/kg for muscle
      retention; every meal ≥ 25 g, breakfast is the usual gap.
    - **Fibre 25-38 g/day**, sodium ≤ 2,300 mg unless told otherwise, ≥ 5 different plants a day.
    - **Batch cooking:** proteins keep 3-4 days refrigerated (freeze the rest), grains 4-5
      days, cut vegetables 3 days, sauces 7 days. Plan day 5-7 meals from frozen portions.
    - **Budget levers, in order:** dried legumes, eggs, oats, frozen vegetables, whole
      chicken / thighs, canned fish, seasonal produce, store brands. Protein per dollar
      beats calories per dollar for anyone tracking macros.
    - **Recipe scaling:** ingredients scale linearly; salt and hot spices start at ~75% when
      doubling or more, then adjust; leavening scales but pan size and time do not — same
      depth, more pans.

    ## Output format
    ```
    # Meal plan — <dates>, <N> kcal · P <g> / C <g> / F <g> · <pattern>
    _General guidance, not medical advice._

    ## Per-meal targets
    | Meal | kcal | Protein | Carbs | Fat |

    ## The week
    | Day | Breakfast | Lunch | Dinner | Snack | Day total (kcal / P) |
    (each cell names the dish + portion; day totals from the tool)

    ## Anchor recipes (scaled)
    ### <Recipe> — makes <N> servings, <kcal>/serving, P <g>
    - <scaled ingredient list>
    - Method: <≤ 6 steps>

    ## Grocery list (by aisle)
    **Produce:** … **Meat/Fish:** … **Dairy/Eggs:** … **Pantry:** … **Frozen:** …
    Estimated cost: $<n> (<$/serving>) vs budget $<n>

    ## Prep plan
    Cook session 1 (<day>, ~<min>): … · Session 2: … · Freeze: …
    ```

    ## Anti-patterns
    - Seven different dinners. Nobody cooks that; three anchors, rotated.
    - Macros that don't add up: "500 kcal, 40 P / 60 C / 30 F" is 670 kcal. The totals tool catches it.
    - A grocery list that lists "chicken" three times in three units.
    - Ignoring the pantry. Oil, salt, rice and spices are probably already there — ask once.
    - Meal prep with fresh fish for day 6. Food safety: fresh proteins die by day 4.
    - Cutting calories to fit the budget. Fix the ingredients, not the energy.
    """,
)

# ── units ───────────────────────────────────────────────────────
MASS_G = {"g": 1.0, "gram": 1.0, "grams": 1.0, "kg": 1000.0, "kilogram": 1000.0, "kilograms": 1000.0, "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495, "lb": 453.592, "lbs": 453.592, "pound": 453.592, "pounds": 453.592}
VOL_ML = {"ml": 1.0, "milliliter": 1.0, "millilitre": 1.0, "l": 1000.0, "liter": 1000.0, "litre": 1000.0, "tsp": 4.929, "teaspoon": 4.929, "teaspoons": 4.929, "tbsp": 14.787, "tablespoon": 14.787, "tablespoons": 14.787, "cup": 236.588, "cups": 236.588, "fl oz": 29.574, "floz": 29.574, "pint": 473.176, "pints": 473.176, "quart": 946.353, "quarts": 946.353}
COUNT_UNITS = {"", "each", "pc", "pcs", "piece", "pieces", "whole", "clove", "cloves", "can", "cans", "bunch", "bunches", "slice", "slices", "stalk", "stalks", "head", "heads", "sprig", "sprigs", "leaf", "leaves", "pack", "packet", "jar", "bag", "large", "medium", "small", "egg", "eggs", "fillet", "fillets", "breast", "breasts"}


def _norm_unit(unit: str) -> str:
    u = str(unit or "").strip().lower().rstrip(".")
    return {"tbs": "tbsp", "tbl": "tbsp", "t": "tsp", "ts": "tsp", "c": "cup", "fl. oz": "fl oz", "fluid ounce": "fl oz", "fluid ounces": "fl oz"}.get(u, u)


def _kind(unit: str) -> str:
    if unit in MASS_G:
        return "mass"
    if unit in VOL_ML:
        return "volume"
    if unit in COUNT_UNITS:
        return "count"
    return "other"


def _to_base(qty: float, unit: str) -> tuple[float, str]:
    if unit in MASS_G:
        return qty * MASS_G[unit], "g"
    if unit in VOL_ML:
        return qty * VOL_ML[unit], "ml"
    return qty, unit


def _nice_fraction(x: float, denom: int) -> str:
    whole = math.floor(x + 1e-9)
    frac = round((x - whole) * denom)
    if frac == denom:
        whole, frac = whole + 1, 0
    frac_map = {(1, 2): "½", (1, 4): "¼", (3, 4): "¾", (1, 3): "⅓", (2, 3): "⅔", (1, 8): "⅛", (3, 8): "⅜", (5, 8): "⅝", (7, 8): "⅞"}
    if frac == 0:
        return str(whole)
    g = math.gcd(frac, denom)
    num, den = frac // g, denom // g
    sym = frac_map.get((num, den), f"{num}/{den}")
    return f"{whole} {sym}" if whole else sym


def _display(qty: float, unit: str) -> str:
    """Round a scaled quantity to something measurable and promote tsp→tbsp→cup."""
    if unit in ("tsp", "tbsp", "cup") and qty > 0:
        ml = qty * VOL_ML[unit]
        cups = ml / VOL_ML["cup"]
        if cups >= 0.24 and abs(round(cups * 8) / 8 - cups) / cups <= 0.04:
            return f"{_nice_fraction(cups, 8)} cup"
        tbsp = ml / VOL_ML["tbsp"]
        if tbsp >= 0.99 and abs(round(tbsp * 2) / 2 - tbsp) / tbsp <= 0.04:
            return f"{_nice_fraction(tbsp, 2)} tbsp"
        return f"{_nice_fraction(ml / VOL_ML['tsp'], 4)} tsp"
    if unit in ("g", "ml"):
        step = 1 if qty < 20 else 5 if qty < 200 else 10
        return f"{int(round(qty / step) * step)} {unit}"
    if unit in ("kg", "l", "lb", "oz"):
        return f"{round(qty, 2):g} {unit}"
    if unit in COUNT_UNITS:
        return f"{_nice_fraction(qty, 2)} {unit}".strip()
    return f"{round(qty, 2):g} {unit}"


NONLINEAR_RE = re.compile(r"\b(salt|soy sauce|fish sauce|chili|chilli|cayenne|pepper flakes|hot sauce|baking (soda|powder)|yeast|vinegar|lemon juice|lime juice|garlic|ginger|vanilla|alcohol|wine|liqueur|stock cube|bouillon)\b", re.I)


@AGENT.tool
def scale_recipe(ingredients: list[dict], from_servings: float, to_servings: float) -> dict:
    """Scale a recipe's ingredient quantities to a new serving count with measurable rounding and non-linear warnings.

    Promotes small units (12 tsp → ¼ cup), rounds grams/ml to kitchen-scale steps, and flags salt,
    spices, acids and leavening, which should start at ~75% of linear when scaling 2× or more.

    Args:
        ingredients: List of {"name": "onion", "qty": 2, "unit": "each"}; unit may be g, kg, oz, lb, ml, l, tsp, tbsp, cup, or a count word.
        from_servings: Servings the recipe currently makes.
        to_servings: Servings you want.
    """
    f = positive(from_servings, "from_servings", 500)
    t = positive(to_servings, "to_servings", 500)
    if not ingredients or len(ingredients) > 200:
        raise ToolError("Give 1-200 ingredients")
    factor = t / f
    rows, warnings = [], []
    for i, ing in enumerate(ingredients, 1):
        if not isinstance(ing, dict) or not ing.get("name"):
            raise ToolError(f"ingredient #{i} needs a 'name'")
        try:
            qty = float(ing.get("qty", 0))
        except (TypeError, ValueError):
            raise ToolError(f"{ing.get('name')}: qty must be a number") from None
        if qty < 0:
            raise ToolError(f"{ing['name']}: qty cannot be negative")
        unit = _norm_unit(ing.get("unit", ""))
        scaled = qty * factor
        row = {"name": str(ing["name"]).strip(), "original": f"{qty:g} {unit}".strip(), "scaled_qty": round(scaled, 3), "unit": unit, "display": _display(scaled, unit)}
        if factor >= 2 and NONLINEAR_RE.search(row["name"]):
            row["display_conservative"] = _display(scaled * 0.75, unit)
            row["note"] = "Season to taste: start at ~75% of linear, then adjust."
        rows.append(row)
    if factor >= 2:
        warnings.append("Cooking time and pan size do not scale: keep the same depth per pan and use more pans; check doneness, not the clock.")
        warnings.append("Sauté/sear in batches — crowding the pan steams instead of browns.")
    if factor < 0.5:
        warnings.append("Scaling down under half: eggs and leavening become awkward (e.g. ½ egg = ~25 g beaten egg). Round to whole eggs and reduce liquid slightly.")
    if factor >= 4:
        warnings.append("At 4× or more, taste midway — liquids often need 10-20% less than linear because evaporation is proportionally lower in bigger pots.")
    return {
        "from_servings": f,
        "to_servings": t,
        "factor": round(factor, 3),
        "ingredients": rows,
        "warnings": warnings,
        "summary": f"Scaled {len(rows)} ingredients by ×{factor:.2f} ({f:g} → {t:g} servings); {sum(1 for r in rows if 'note' in r)} flagged for taste-scaling.",
    }


AISLES: list[tuple[str, re.Pattern]] = [
    ("frozen", re.compile(r"\bfrozen\b")),
    ("produce", re.compile(r"\b(onion|garlic|tomato|lettuce|spinach|kale|apple|banana|lemon|lime|orange|berr|pepper|carrot|potato|sweet potato|broccoli|cauliflower|zucchini|courgette|cucumber|avocado|mushroom|celery|ginger|herb|cilantro|coriander|parsley|basil|mint|dill|scallion|spring onion|leek|cabbage|squash|pumpkin|corn|pea|bean sprout|salad|greens|fruit|grape|mango|pineapple|melon|chili|chilli|jalape)\w*"))
    ,
    ("meat & fish", re.compile(r"\b(chicken|beef|pork|lamb|turkey|salmon|tuna|cod|shrimp|prawn|fish|steak|mince|ground|sausage|bacon|ham|tofu|tempeh|seitan)\b")),
    ("dairy & eggs", re.compile(r"\b(milk|cheese|yogurt|yoghurt|butter|cream|egg|eggs|feta|mozzarella|parmesan|cheddar|ricotta|paneer|kefir)\b")),
    ("bakery", re.compile(r"\b(bread|tortilla|wrap|bun|bagel|pita|naan|baguette|roll)s?\b")),
    ("pantry", re.compile(r"\b(rice|pasta|noodle|flour|sugar|oil|oats|bean|lentil|chickpea|quinoa|canned|can of|stock|broth|sauce|vinegar|honey|syrup|spice|salt|pepper|cumin|paprika|oregano|cinnamon|curry|nut|almond|peanut|seed|coconut|soy|tahini|mustard|ketchup|tomato paste|passata|couscous|barley|cereal|granola|protein powder|cocoa|chocolate|baking|yeast|vanilla)\w*")),
]
DESCRIPTOR_RE = re.compile(r"\b(fresh|chopped|diced|minced|sliced|grated|crushed|peeled|large|medium|small|ripe|boneless|skinless|finely|roughly|to taste|optional|of)\b|,.*$", re.I)


def _norm_name(name: str) -> str:
    n = DESCRIPTOR_RE.sub("", str(name).lower()).strip()
    n = re.sub(r"\s{2,}", " ", n)
    if n.endswith("ies"):
        n = n[:-3] + "y"
    elif n.endswith("oes"):
        n = n[:-2]
    elif n.endswith("s") and not n.endswith("ss") and len(n) > 3:
        n = n[:-1]
    return n or str(name).strip().lower()


@AGENT.tool
def grocery_list(recipes: list[dict], pantry: list[str] | None = None) -> dict:
    """Merge the ingredients of several recipes into one aisle-sorted grocery list, converting units and removing pantry items.

    Normalises names ("onions, diced" and "onion" merge), sums quantities in a common unit
    (g or ml), keeps counts as counts, and lists anything that couldn't be merged separately.

    Args:
        recipes: List of {"name": "Chili", "ingredients": [{"name": "onion", "qty": 2, "unit": "each"}, ...]} (already scaled).
        pantry: Ingredient names you already have (e.g. ["olive oil", "salt", "rice"]); matched by normalised name.
    """
    if not recipes or len(recipes) > 60:
        raise ToolError("Give 1-60 recipes")
    pantry_norm = {_norm_name(p) for p in (pantry or []) if str(p).strip()}
    totals: dict[tuple[str, str], dict] = {}
    n_ing = 0
    for ri, r in enumerate(recipes, 1):
        if not isinstance(r, dict) or not isinstance(r.get("ingredients"), list):
            raise ToolError(f"recipe #{ri} needs an 'ingredients' list")
        for ing in r["ingredients"]:
            if not isinstance(ing, dict) or not ing.get("name"):
                raise ToolError(f"recipe #{ri}: each ingredient needs a 'name'")
            n_ing += 1
            if n_ing > 1500:
                raise ToolError("Too many ingredients (1500 max)")
            try:
                qty = float(ing.get("qty", 0) or 0)
            except (TypeError, ValueError):
                raise ToolError(f"{ing['name']}: qty must be a number") from None
            unit = _norm_unit(ing.get("unit", ""))
            base_qty, base_unit = _to_base(qty, unit)
            key = (_norm_name(ing["name"]), base_unit if _kind(unit) in ("mass", "volume") else ("count" if _kind(unit) == "count" else unit))
            entry = totals.setdefault(key, {"qty": 0.0, "recipes": [], "count_unit": unit if _kind(unit) == "count" else ""})
            entry["qty"] += base_qty
            if str(r.get("name", f"recipe {ri}")) not in entry["recipes"]:
                entry["recipes"].append(str(r.get("name", f"recipe {ri}")))
    by_aisle: dict[str, list[dict]] = defaultdict(list)
    skipped = []
    for (name, unit), entry in sorted(totals.items()):
        if name in pantry_norm or any(p and p in name for p in pantry_norm if len(p) > 3):
            skipped.append(name)
            continue
        aisle = next((a for a, rx in AISLES if rx.search(name)), "other")
        qty = entry["qty"]
        if unit == "g":
            display = f"{qty / 1000:.2f} kg".replace(".00", "") if qty >= 1000 else f"{int(round(qty))} g"
        elif unit == "ml":
            display = f"{qty / 1000:.2f} L".replace(".00", "") if qty >= 1000 else f"{int(round(qty))} ml"
        elif unit == "count":
            display = f"{_nice_fraction(qty, 2)} {entry['count_unit']}".strip() if qty else name
        else:
            display = f"{round(qty, 2):g} {unit}".strip()
        by_aisle[aisle].append({"item": name, "qty": round(qty, 2), "unit": unit if unit != "count" else entry["count_unit"], "display": display, "used_in": entry["recipes"]})
    order = ["produce", "meat & fish", "dairy & eggs", "bakery", "pantry", "frozen", "other"]
    aisles = {a: by_aisle[a] for a in order if by_aisle.get(a)}
    total_items = sum(len(v) for v in aisles.values())
    return {
        "recipes": len(recipes),
        "raw_ingredient_lines": n_ing,
        "items": total_items,
        "merged_away": n_ing - total_items - len(skipped),
        "skipped_from_pantry": skipped,
        "by_aisle": aisles,
        "checklist": [f"[ ] {row['display']} {row['item']}" for a in order for row in aisles.get(a, [])],
        "summary": f"{total_items} items from {n_ing} ingredient lines across {len(recipes)} recipes; {len(skipped)} already in the pantry.",
    }


@AGENT.tool
def split_macros(
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    meals: int = 4,
    pattern: Literal["even", "front_loaded", "post_workout", "dinner_heavy"] = "even",
    bodyweight_kg: float = 0,
) -> dict:
    """Split daily calories and macros into per-meal targets, after checking the macros actually add up to the calories.

    Applies the 4/4/9 kcal rule (flags > 8% mismatch), the 1,200 kcal floor, a per-meal protein
    floor (25 g, or 0.4 g/kg if bodyweight given) and shifts carbs toward the chosen meal pattern.

    Args:
        calories: Daily calorie target.
        protein_g: Daily protein grams.
        carbs_g: Daily carbohydrate grams.
        fat_g: Daily fat grams.
        meals: Meals per day, 2-8 (default 4; snacks count as meals).
        pattern: even (default), front_loaded (bigger breakfast/lunch), post_workout (carbs to meal 2), dinner_heavy.
        bodyweight_kg: Optional bodyweight to set the per-meal protein floor at 0.4 g/kg.
    """
    cal = positive(calories, "calories", 8000)
    for label, v in (("protein_g", protein_g), ("carbs_g", carbs_g), ("fat_g", fat_g)):
        if v < 0 or v > 1500:
            raise ToolError(f"{label} must be 0-1500")
    if not 2 <= meals <= 8:
        raise ToolError("meals must be 2-8")
    flags = []
    if cal < 1200:
        flags.append(f"{cal:.0f} kcal is below the 1,200 kcal floor — not planning below it; confirm with a professional.")
        cal = 1200.0
    from_macros = protein_g * 4 + carbs_g * 4 + fat_g * 9
    mismatch = (from_macros - cal) / cal * 100
    if abs(mismatch) > 8:
        flags.append(f"Macros compute to {from_macros:.0f} kcal, {mismatch:+.0f}% vs the {cal:.0f} kcal target — fix the split before planning (4/4/9 rule).")
    floor = max(25.0, 0.4 * bodyweight_kg) if bodyweight_kg else 25.0
    if protein_g / meals < floor:
        flags.append(f"Protein per meal is {protein_g / meals:.0f} g (< {floor:.0f} g floor). Fewer, bigger protein feedings or raise the daily target.")
    weights = {
        "even": [1.0] * meals,
        "front_loaded": [1.3, 1.2] + [0.9] * (meals - 2) if meals > 2 else [1.2, 0.8],
        "post_workout": [0.9, 1.4] + [0.9] * (meals - 2) if meals > 2 else [1.3, 0.7],
        "dinner_heavy": [0.85] * (meals - 1) + [1.35],
    }[pattern]
    total_w = sum(weights)
    rows = []
    for i, w in enumerate(weights, 1):
        share = w / total_w
        p = protein_g / meals  # protein stays even — distribution matters more than timing
        c = carbs_g * share
        f_ = fat_g * share
        rows.append({"meal": i, "kcal": round(p * 4 + c * 4 + f_ * 9), "protein_g": round(p), "carbs_g": round(c), "fat_g": round(f_), "share_pct": round(100 * share)})
    return {
        "daily": {"kcal": round(cal), "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g, "kcal_from_macros": round(from_macros)},
        "macro_split_pct": {"protein": round(pct(protein_g * 4, from_macros)), "carbs": round(pct(carbs_g * 4, from_macros)), "fat": round(pct(fat_g * 9, from_macros))},
        "pattern": pattern,
        "protein_floor_per_meal_g": round(floor),
        "meals": rows,
        "flags": flags,
        "verdict": f"{meals} meals, ~{rows[0]['protein_g']} g protein each; " + (" ".join(flags) if flags else "macros reconcile with the calorie target."),
    }


@AGENT.tool
def nutrition_totals(items: list[dict], protein_target_g: float = 0, calorie_target: float = 0) -> dict:
    """Total calories and macros for a list of foods, check each item's label math (4/4/9), and compare to targets.

    Args:
        items: List of {"name": "Greek yogurt", "servings": 1.5, "calories": 100, "protein_g": 17, "carbs_g": 6, "fat_g": 0, "fiber_g": 0 (opt), "sodium_mg": 60 (opt)} — values per serving.
        protein_target_g: Daily protein target to compare against (0 = skip).
        calorie_target: Daily calorie target to compare against (0 = skip).
    """
    if not items or len(items) > 300:
        raise ToolError("Give 1-300 items")
    tot = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "sodium_mg": 0.0}
    rows, flags = [], []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict) or not it.get("name"):
            raise ToolError(f"item #{i} needs a 'name'")
        try:
            s = float(it.get("servings", 1) or 0)
            vals = {k: float(it.get(k, 0) or 0) for k in tot}
        except (TypeError, ValueError):
            raise ToolError(f"{it['name']}: nutrition values must be numbers") from None
        if s < 0 or any(v < 0 for v in vals.values()):
            raise ToolError(f"{it['name']}: values cannot be negative")
        calc = vals["protein_g"] * 4 + vals["carbs_g"] * 4 + vals["fat_g"] * 9
        row = {"name": it["name"], "servings": s, **{k: round(v * s, 1) for k, v in vals.items()}}
        if vals["calories"] and calc and abs(calc - vals["calories"]) / vals["calories"] > 0.15:
            row["label_check"] = f"stated {vals['calories']:.0f} kcal vs {calc:.0f} from macros ({(calc - vals['calories']) / vals['calories']:+.0%})"
            flags.append(f"{it['name']}: {row['label_check']} — check the entry (fibre/alcohol/sugar alcohols can explain part).")
        for k in tot:
            tot[k] += vals[k] * s
        rows.append(row)
    cal = tot["calories"] or (tot["protein_g"] * 4 + tot["carbs_g"] * 4 + tot["fat_g"] * 9)
    split = {"protein": round(pct(tot["protein_g"] * 4, cal)), "carbs": round(pct(tot["carbs_g"] * 4, cal)), "fat": round(pct(tot["fat_g"] * 9, cal))} if cal else {}
    if protein_target_g:
        gap = tot["protein_g"] - protein_target_g
        if gap < -0.05 * protein_target_g:
            flags.append(f"Protein {tot['protein_g']:.0f} g is {-gap:.0f} g short of {protein_target_g:g} g.")
    if calorie_target:
        gap = tot["calories"] - calorie_target
        if abs(gap) > 0.05 * calorie_target:
            flags.append(f"Calories {tot['calories']:.0f} are {gap:+.0f} vs the {calorie_target:g} target (> 5%).")
    if tot["fiber_g"] and tot["fiber_g"] < 25:
        flags.append(f"Fibre {tot['fiber_g']:.0f} g < 25 g — add legumes, oats, berries or vegetables.")
    if tot["sodium_mg"] > 2300:
        flags.append(f"Sodium {tot['sodium_mg']:.0f} mg > 2,300 mg.")
    return {
        "items": rows,
        "totals": {k: round(v, 1) for k, v in tot.items()},
        "macro_split_pct": split,
        "vs_targets": {"protein_gap_g": round(tot["protein_g"] - protein_target_g, 1) if protein_target_g else None, "calorie_gap": round(tot["calories"] - calorie_target) if calorie_target else None},
        "flags": flags,
        "verdict": f"{tot['calories']:.0f} kcal · P {tot['protein_g']:.0f} / C {tot['carbs_g']:.0f} / F {tot['fat_g']:.0f} g" + ("; " + " ".join(flags) if flags else "; on target."),
    }


@AGENT.tool
def cost_per_serving(recipes: list[dict], people: int = 1, days: int = 7, weekly_budget: float = 0, meals_per_day: int = 3) -> dict:
    """Price a meal plan: cost per serving per recipe, weekly total, per person per day, and gap vs budget with swap advice.

    Args:
        recipes: List of {"name": "Chili", "cost": 18.40, "servings": 8, "servings_used": 8 (optional, defaults to servings)}; cost is the ingredient cost for the batch.
        people: Number of people eating (default 1).
        days: Days the plan covers (default 7).
        weekly_budget: Budget for the period (0 = skip comparison).
        meals_per_day: Meals per person per day the plan is meant to cover (default 3), to check coverage.
    """
    if not recipes or len(recipes) > 100:
        raise ToolError("Give 1-100 recipes")
    if people < 1 or days < 1 or days > 60 or meals_per_day < 1:
        raise ToolError("people, days and meals_per_day must be positive (days ≤ 60)")
    if weekly_budget < 0:
        raise ToolError("weekly_budget cannot be negative")
    rows, total, servings_total = [], 0.0, 0.0
    for i, r in enumerate(recipes, 1):
        if not isinstance(r, dict) or not r.get("name"):
            raise ToolError(f"recipe #{i} needs a 'name'")
        try:
            cost = float(r.get("cost", 0))
            servings = float(r.get("servings", 0))
            used = float(r.get("servings_used", servings))
        except (TypeError, ValueError):
            raise ToolError(f"{r['name']}: cost and servings must be numbers") from None
        if servings <= 0 or cost < 0 or used < 0:
            raise ToolError(f"{r['name']}: servings must be > 0 and cost ≥ 0")
        cps = cost / servings
        spend = cps * used
        total += spend
        servings_total += used
        rows.append({"name": r["name"], "cost_per_serving": money(cps), "servings": servings, "servings_used": used, "spend": money(spend)})
    rows.sort(key=lambda r: -r["cost_per_serving"])
    needed = people * days * meals_per_day
    per_person_day = total / (people * days)
    flags = []
    if servings_total < needed:
        flags.append(f"Plan covers {servings_total:g} servings but {needed} meals are needed ({people} × {days} × {meals_per_day}); add {needed - servings_total:g} servings.")
    if weekly_budget:
        gap = total - weekly_budget
        if gap > 0:
            top = rows[0]
            flags.append(f"Over budget by {gap:.2f}. Start with '{top['name']}' at {top['cost_per_serving']:.2f}/serving — swap the protein or halve its share of the week.")
    return {
        "recipes": rows,
        "total_cost": money(total),
        "servings": servings_total,
        "servings_needed": needed,
        "avg_cost_per_serving": money(total / servings_total) if servings_total else None,
        "cost_per_person_per_day": money(per_person_day),
        "budget": weekly_budget or None,
        "vs_budget": money(total - weekly_budget) if weekly_budget else None,
        "flags": flags,
        "verdict": f"{total:.2f} total, {per_person_day:.2f}/person/day, {total / servings_total if servings_total else 0:.2f}/serving" + (f"; {'under' if total <= weekly_budget else 'OVER'} budget by {abs(total - weekly_budget):.2f}." if weekly_budget else "."),
    }
