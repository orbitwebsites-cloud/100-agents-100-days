"""Creator & Personal scenario regressions (evals/creator.md).

Each test replays one realistic customer scenario through the agent's tools exactly as the
customer's AI would call them, and asserts the values that were verified by hand with
independent arithmetic (published formulas, zoneinfo, the SM-2 paper) — not by re-running
our own code. If one of these fails, a number the eval signed off on has changed.
"""

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import re

import pytest

from hundred import registry


def run(slug, tool, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ── content-calendar: solo food creator, 6 h/week, IG + TikTok + YouTube, London → US East ──

PLATFORMS_WANTED = [
    {"platform": "instagram", "posts_per_week": 4},
    {"platform": "tiktok", "posts_per_week": 4},
    {"platform": "youtube", "posts_per_week": 1},
]


def test_content_calendar_capacity_fit_uses_the_hours():
    out = run("content-calendar", "capacity_check", hours_per_week=6, platforms=PLATFORMS_WANTED)
    # effective minutes/post with 30% repurposing: 45, 75, 360 × 0.775 = 34.875, 58.125, 279
    assert out["hours_needed"] == round((4 * 34.875 + 4 * 58.125 + 279) / 60, 1) == 10.8
    assert out["fits"] is False
    fitted = {f["platform"]: f["posts_per_week"] for f in out["fit_plan"]}
    # Hand-derived optimum: IG 2 + TikTok 2 + YouTube every other week = 325.5 of 360 min.
    assert fitted == {"instagram": 2, "tiktok": 2, "youtube": 0.5}
    assert out["fit_plan_hours"] == round((2 * 34.875 + 2 * 58.125 + 0.5 * 279) / 60, 1) == 5.4


def test_content_calendar_schedule_is_audience_anchored_across_both_dst_changes():
    out = run(
        "content-calendar", "build_schedule",
        start_date="2026-10-19", weeks=4, timezone="Europe/London", audience_timezone="America/New_York",
        pillars=["Quick recipes", "Kitchen myths", "Budget meals", "Behind the scenes"],
        platforms=[{"platform": "instagram", "posts_per_week": 2}, {"platform": "tiktok", "posts_per_week": 2},
                   {"platform": "youtube", "posts_per_week": 0.5}],
    )
    assert out["posts_per_platform"] == {"instagram": 8, "tiktok": 8, "youtube": 2}
    ig = {r["date"]: r for r in out["slots"] if r["platform"] == "instagram"}
    # 11:00 New York → London, computed independently with zoneinfo (UK DST ends Oct 25, US Nov 1)
    for d in ("2026-10-20", "2026-10-27", "2026-11-03"):
        y, m, dd = map(int, d.split("-"))
        expect = datetime(y, m, dd, 11, 0, tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo("Europe/London"))
        assert ig[d]["time_local"] == expect.strftime("%H:%M")
        assert ig[d]["time_audience"] == "11:00"
    assert ig["2026-10-20"]["time_local"] == "16:00" and ig["2026-10-27"]["time_local"] == "15:00"
    assert [r["date"] for r in out["slots"] if r["platform"] == "youtube"] == ["2026-10-23", "2026-11-06"]
    pillars = [r["pillar"] for r in out["slots"]]
    assert all(a != b for a, b in zip(pillars, pillars[1:]))


def test_content_calendar_instagram_hashtag_cap_and_x_url_weighting():
    ig = run("content-calendar", "check_post_fits", platform="instagram",
             text="Your $4 dinner is hiding in your freezer.\nHere are 3 meals I make from one bag of frozen spinach.\n"
                  "Save this for Sunday prep.\n#budgetmeals #mealprep #frozenfood #cheapeats #easyrecipes #spinach")
    assert ig["hashtags"] == 6 and any("maximum of 5" in f for f in ig["fixes"])
    tweet = ("New video: 3 dinners from one bag of frozen spinach, all under $4 a serving. Full recipes here "
             "https://www.youtube.com/watch?v=abcdefghijk&t=10s and the shopping list is pinned.")
    x = run("content-calendar", "check_post_fits", platform="x", text=tweet)
    url = "https://www.youtube.com/watch?v=abcdefghijk&t=10s"
    assert x["chars"] == len(tweet) - len(url) + 23 == 151 and x["fits"]


# ── short-video-scripter: 60-second finance TikTok full of numbers ──

SCRIPT = """Stop keeping $10,000 in checking.
[TEXT: Your checking account pays 0.01%]
At 0.01%, ten grand earns you one dollar a year.
Here are 3 places your emergency fund should never sit, and the one place it should.
One: checking. It's too easy to spend, and it pays basically nothing.
[B-ROLL: bank app showing $0.08 interest]
Two: the stock market. Emergencies love to happen right when stocks are down 20%.
Three: a CD you can't touch for five years. The penalty eats the interest.
So where does it go?
A high-yield savings account paying around 4%.
On $10,000 that's about $400 a year for doing nothing.
It's FDIC insured up to $250,000, and you can move it in one or two days.
[TEXT: HYSA = safe + liquid + paid]
Open one tonight and set an automatic transfer on payday.
Follow for part two, where I show you how big your fund should be.
"""
# The same lines written out as they are spoken (hand transcription), one per line.
SPOKEN = """Stop keeping ten thousand dollars in checking
At zero point zero one percent ten grand earns you one dollar a year
Here are three places your emergency fund should never sit and the one place it should
One checking It's too easy to spend and it pays basically nothing
Two the stock market Emergencies love to happen right when stocks are down twenty percent
Three a CD you can't touch for five years The penalty eats the interest
So where does it go
A high-yield savings account paying around four percent
On ten thousand dollars that's about four hundred dollars a year for doing nothing
It's FDIC insured up to two hundred fifty thousand dollars and you can move it in one or two days
Open one tonight and set an automatic transfer on payday
Follow for part two where I show you how big your fund should be"""


def test_short_video_timing_counts_numbers_as_spoken():
    out = run("short-video-scripter", "time_script", script=SCRIPT, pace="natural", platform="tiktok", target_seconds=60)
    spoken = [len(line.replace("-", " ").split()) for line in SPOKEN.splitlines()]
    assert [r["words"] for r in out["lines"]] == spoken
    written = sum(len([t for t in r["line"].split() if re.search(r"[^\W_]", t)]) for r in out["lines"])  # Word's count
    assert out["spoken_words"] == sum(spoken) == 150 and out["written_words"] == written == 133
    assert out["total_seconds"] == 60.0 == 150 / 2.5  # a written-word count would have said 55.2 s
    assert out["hook_words"] == 7 and out["hook_seconds"] == 2.8
    assert out["lines"][-1]["starts_at"] == "0:54" and (150 - 14) / 2.5 == 54.4 and not out["flags"]


def test_short_video_beats_and_hooks():
    beats = run("short-video-scripter", "plan_beats", duration_seconds=60, format="listicle", pace="natural")
    assert [b["seconds"] for b in beats["beats"]] == [3.0, 10.8, 10.8, 10.8, 13.8, 10.8]
    assert sum(b["seconds"] for b in beats["beats"]) == pytest.approx(60.0)
    assert beats["total_word_budget"] == 150
    greet = run("short-video-scripter", "score_hook", hook="Hey guys, today I want to talk about some really amazing savings tips")
    best = run("short-video-scripter", "score_hook", hook="Stop keeping $10,000 in checking.")
    assert greet["score"] == 0 and best["score"] >= 75 and best["words"] == 7


# ── podcast-producer: 46:30 interview, timestamped transcript ──

TRANSCRIPT = """[00:00] Leo: The single biggest sleep mistake I see is people sleeping in on Saturday. You basically give yourself jet lag every weekend.
[00:22] Maya: Welcome to Rested, I'm Maya. Today I'm with Dr. Leo Park, a sleep physician at Northwestern who runs the insomnia clinic there.
[01:05] Maya: Leo, what is social jet lag, actually?
[01:12] Leo: So, um, social jet lag is the gap between your body clock on workdays and on free days. If you, like, go to bed at eleven during the week and two on Friday, that's a three-hour shift, which is, you know, like flying from Chicago to LA and back every week.
[06:40] Maya: How do you measure it in a patient?
[06:48] Leo: We use the Munich Chronotype Questionnaire, and a week of actigraphy with a wrist tracker. The midpoint of sleep is the number that matters.
[12:15] Maya: So is the fix just an alarm clock on weekends?
[12:21] Leo: Mostly. Keep your wake time within an hour, seven days a week. Get outdoor light in the first thirty minutes. That's it. Light is the lever.
[19:30] Maya: What about melatonin? Everyone asks.
[19:38] Leo: Um, low dose, half a milligram, about five hours before your target bedtime, if you're a night owl. Uh, the big doses people buy, ten milligrams, they're, um, basically overkill and they leave you groggy.
[27:02] Maya: You mentioned caffeine before we started recording.
[27:10] Leo: Caffeine has a half-life of about five to six hours. A three pm coffee is still half there at nine. Matthew Walker's book Why We Sleep covers it, though I disagree with some of his numbers.
[34:45] Maya: What should shift workers do?
[34:52] Leo: Anchor sleep. Pick four hours that never move, and build the rest around them. And dark glasses on the drive home.
[41:30] Maya: What's one thing a listener should do tonight?
[41:36] Leo: Set one alarm for the same wake time on Saturday. Just one. Then go outside.
[45:10] Maya: Leo, where can people find you?
[45:14] Leo: My clinic site, and I post on Instagram as at sleepdocleo.
[46:02] Maya: Thanks for listening to Rested. New episodes every Tuesday.
"""
CHAPTER_STARTS = ["0:00", "1:05", "6:40", "12:15", "19:30", "27:02", "34:45", "41:30", "45:10"]


def test_podcast_transcript_profile():
    out = run("podcast-producer", "analyze_transcript", transcript=TRANSCRIPT, host="Maya")
    import re
    words = {"Leo": 0, "Maya": 0}
    for line in TRANSCRIPT.strip().splitlines():
        who, said = line[8:].split(":", 1)
        words[who.strip()] += len(re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*", said))
    total = sum(words.values())
    assert out["total_words"] == total
    assert out["talk_share_pct"] == {"Leo": round(100 * words["Leo"] / total, 1), "Maya": round(100 * words["Maya"] / total, 1)}
    assert out["questions_by_speaker"]["Maya"] == 7
    assert out["fillers_by_speaker"] == {"Leo": 9, "Maya": 1}  # um×3, uh, like×2, you know, basically×2 / actually
    assert out["estimated_minutes"] == 46.0 and out["duration_source"] == "timestamps"


def test_podcast_chapters_follow_youtube_rules():
    titles = ["Cold open: the weekend sleep mistake", "What social jet lag really is", "How clinics measure your body clock",
              "The one-alarm weekend fix", "Melatonin: half a milligram, five hours early", "Why a 3 pm coffee still counts",
              "Anchor sleep for shift workers", "One thing to do tonight", "Where to find Dr. Park"]
    out = run("podcast-producer", "format_chapters", total_duration="46:30",
              chapters=[{"start": s, "title": t} for s, t in zip(CHAPTER_STARTS, titles)])
    assert out["youtube_valid"] and out["issues"] == []
    assert [c["length_s"] for c in out["chapters"]] == [65, 335, 335, 435, 452, 463, 405, 220, 80]
    bad = run("podcast-producer", "format_chapters", chapters=[{"start": "0:05", "title": "Intro"}, {"start": "0:12", "title": "Sleep"}, {"start": "0:12", "title": "Melatonin"}])
    assert not bad["youtube_valid"]
    assert any("0:00" in i for i in bad["issues"]) and any("≥ 10 s" in i for i in bad["issues"]) and any("ascend" in i for i in bad["issues"])


def test_podcast_ad_breaks_snap_and_price_by_placement():
    out = run("podcast-producer", "plan_ad_breaks", duration="46:30", ad_load="standard", downloads_per_episode=8500,
              cpm=25, cold_open_seconds=65, chapter_starts=CHAPTER_STARTS)
    # unsnapped ideal points: 480 + (2511-480)·k/3 → 19:17 and 30:34; next chapter boundaries: 19:30, 34:45
    assert [(b["type"], b["at"]) for b in out["breaks"]] == [("pre-roll", "0:00"), ("mid-roll 1", "19:30"), ("mid-roll 2", "34:45"), ("post-roll", "46:10")]
    assert out["ad_load_pct"] == round(100 * 180 / 2790, 1) == 6.5
    assert out["estimated_revenue"] == pytest.approx(8.5 * (25 * 0.75 + 25 + 25 + 25 * 0.5), abs=0.01) and out["estimated_revenue"] == 690.63


def test_podcast_metadata_and_release_calendar_dst():
    good = run("podcast-producer", "check_metadata", title="Dr. Leo Park: sleeping in on Saturday is giving you jet lag",
               show_name="Rested", guest="Leo Park",
               description="Sleeping in on weekends shifts your body clock like a flight to LA and back. Sleep physician Dr. Leo Park explains social jet lag and the one-alarm fix.\n\n(1:05) What social jet lag is\n(12:15) The one-alarm weekend fix\n\nMentioned: Munich Chronotype Questionnaire; Why We Sleep by Matthew Walker.")
    assert good["fixes"] == [] and good["title"]["chars"] == 59
    bad = run("podcast-producer", "check_metadata", title="Ep. 42 - A conversation with Leo Park | Rested", show_name="Rested", guest="Leo Park", description="In this episode we talk about sleep.")
    assert len(bad["fixes"]) == 4
    cal = run("podcast-producer", "plan_release_calendar", first_publish="2026-10-06", count=6, cadence="weekly", publish_time="05:00", timezone="America/Chicago")
    utc = [r["publish_utc"] for r in cal["schedule"]]
    assert utc[3] == "2026-10-27 10:00 UTC" and utc[4] == "2026-11-03 11:00 UTC"  # US DST ends Nov 1
    assert cal["schedule"][0]["record_by"] == "2026-09-29"


# ── sponsorship-pricer: YouTuber, 40k median views, finance niche, $900 offer ──

VIEWS = [38200, 41500, 36900, 44100, 40300, 129000, 39800, 35200, 42700, 47900, 37600, 40100, 33800, 45200, 41900]


def test_sponsorship_media_kit_numbers():
    out = run("sponsorship-pricer", "media_kit_numbers", views=VIEWS, followers=185000, likes=21000, comments=2400, shares=900, previous_followers=178000, period_days=30)
    assert out["median_views"] == 40300 and out["mean_views"] == 46280
    assert out["engagement_rate_by_views_pct"] == round(100 * 24300 / sum(VIEWS), 1) == 3.5
    assert out["engagement_rate_by_followers_pct"] == round(100 * 24300 / 15 / 185000, 1) == 0.9
    assert out["follower_growth_pct"] == round(100 * 7000 / 178000, 1)


def test_sponsorship_rate_card_and_offer():
    card = run("sponsorship-pricer", "rate_card", platform="youtube", median_views=40300, deliverable="integration",
               engagement_rate_pct=3.5, niche="finance", usage_days=90, exclusivity_months=3, production_hours=8, hourly_floor=75)
    # 40.3 × $20/30/40 CPM × finance 1.5 × (1 + 50% usage + 45% exclusivity)
    for key, cpm in (("quote_low", 20), ("quote_mid", 30), ("quote_high", 40)):
        assert card[key] == pytest.approx(40.3 * cpm * 1.5 * 1.95, abs=0.01)
    assert (card["quote_low"], card["quote_mid"], card["quote_high"]) == (2357.55, 3536.33, 4715.1)
    offer = run("sponsorship-pricer", "evaluate_offer", offer_amount=900, platform="youtube", median_views=40300, deliverable="integration",
                production_hours=8, hourly_floor=75, usage_days=90, exclusivity_months=3, payment_terms_days=60, deposit_pct=0,
                revision_rounds=2, kill_fee=False, engagement_rate_pct=3.5, niche="finance")
    assert offer["implied_cpm"] == round(900 / 40.3, 2) == 22.33 and offer["effective_hourly"] == 112.5
    assert offer["counter"] == 3525.0
    # fallback is organic-only (no usage/exclusivity): 40.3 × 30 × 1.5 = 1813.5 → 1825; walk-away 40.3 × 20 × 1.5 = 1209 → 1200
    assert offer["fallback_with_reduced_scope"] == 1825.0 and offer["walk_away"] == 1200.0
    assert "organic-only" in offer["counter_script"] and "1,825" in offer["counter_script"]
    assert any("Net-60" in r for r in offer["red_flags"]) and any("kill fee" in a for a in offer["amber_flags"])


def test_sponsorship_bundle():
    out = run("sponsorship-pricer", "bundle_quote", items=[{"deliverable": "YouTube integration", "rate": 3525, "quantity": 1}, {"deliverable": "YouTube Short", "rate": 500, "quantity": 2}], bundle_discount_pct=10)
    assert out["list_price"] == 4525 and out["package_price"] == 4072.5
    assert [p["amount"] for p in out["payment_schedule"]] == [2036.25, 2036.25]


# ── fitness-coach: 34 M, 88 kg, 178 cm, 4×/week, wants −1 kg/week ──

def test_fitness_one_rep_maxes():
    for w, r, expect in ((100, 5, 114.6), (80, 6, 94.5), (140, 3, 151.1)):
        out = run("fitness-coach", "one_rep_max", weight=w, reps=r)
        epley, brzycki = w * (1 + r / 30), w * 36 / (37 - r)
        assert out["estimated_1rm"] == round((epley + brzycki) / 2, 1) == expect
    rir = run("fitness-coach", "one_rep_max", weight=100, reps=5, reps_in_reserve=2)
    assert rir["estimated_1rm"] == round((100 * (1 + 7 / 30) + 100 * 36 / 30) / 2, 1) == 121.7


def test_fitness_tdee_flags_aggressive_cut_and_offers_safer_target():
    out = run("fitness-coach", "tdee_and_macros", sex="male", age=34, height_cm=178, weight_kg=88, activity="moderate", goal="lose", weekly_change_kg=1)
    bmr = 10 * 88 + 6.25 * 178 - 5 * 34 + 5  # Mifflin-St Jeor 1990
    tdee = bmr * 1.55
    assert out["bmr_kcal"] == round(bmr) == 1828 and out["tdee_kcal"] == round(tdee) == 2833
    assert out["target_kcal"] == round(tdee - 1100) == 1733 and out["deficit_pct_of_tdee"] == 38.8
    assert out["macros_g"] == {"protein": 176, "fat": 53, "carbs": 138}
    assert any("39% of TDEE" in f for f in out["flags"]) and any("over 1% of bodyweight" in f for f in out["flags"])
    alt = out["safer_alternative"]
    assert alt["target_kcal"] == round(tdee * 0.8) == 2266 and alt["weekly_change_kg"] == round(tdee * 0.2 * 7 / 7700, 2) == 0.52


def test_fitness_guardrails_floor_and_underweight():
    floored = run("fitness-coach", "tdee_and_macros", sex="female", age=29, height_cm=160, weight_kg=55, activity="sedentary", goal="lose", weekly_change_kg=0.75)
    tdee = (10 * 55 + 6.25 * 160 - 5 * 29 - 161) * 1.2
    assert floored["target_kcal"] == 1200 and floored["requested_weekly_change_kg"] == 0.75
    assert floored["weekly_change_kg"] == round((tdee - 1200) * 7 / 7700, 2) == 0.27  # what 1,200 kcal actually delivers
    under = run("fitness-coach", "tdee_and_macros", sex="female", age=29, height_cm=165, weight_kg=48, goal="lose")
    assert under["goal"] == "maintain" and under["target_kcal"] == under["tdee_kcal"] and any("18.5" in f for f in under["flags"])


def test_fitness_531_plates_volume_and_zones():
    squat = run("fitness-coach", "progression_plan", exercise="Back squat", one_rm=114.6, weeks=8, model="531")
    assert squat["weeks"][0]["training_max"] == 102.5  # 0.9 × 114.6 = 103.1 → nearest 2.5
    assert [s["load"] for s in squat["weeks"][0]["sets"]] == [67.5, 77.5, 87.5]
    assert squat["weeks"][4]["training_max"] == 107.5 and squat["peak_top_set"] == 102.5
    incline = run("fitness-coach", "progression_plan", exercise="Incline dumbbell press", one_rm=60, weeks=4)
    assert incline["increment_per_step"] == 2.5  # upper body
    assert run("fitness-coach", "plate_loading", target=132.5)["plates_per_side"] == [25, 25, 5, 1.25]
    assert run("fitness-coach", "plate_loading", target=80, plates=[20, 15])["plates_per_side"] == [15, 15]
    week = [
        {"day": "Mon", "exercises": [{"name": "Back squat", "sets": 4}, {"name": "Romanian deadlift", "sets": 3}, {"name": "Leg curl", "sets": 3}, {"name": "Standing calf raise", "sets": 3}]},
        {"day": "Tue", "exercises": [{"name": "Bench press", "sets": 4}, {"name": "Barbell row", "sets": 4}, {"name": "Overhead press", "sets": 3}, {"name": "Lat pulldown", "sets": 3}, {"name": "Triceps pushdown", "sets": 2}]},
        {"day": "Thu", "exercises": [{"name": "Deadlift", "sets": 3}, {"name": "Bulgarian split squat", "sets": 3}, {"name": "Hip thrust", "sets": 3}, {"name": "Hanging leg raise", "sets": 3}]},
        {"day": "Fri", "exercises": [{"name": "Incline dumbbell press", "sets": 3}, {"name": "Chin-up", "sets": 4}, {"name": "Seated cable row", "sets": 3}, {"name": "Lateral raise", "sets": 3}, {"name": "Dumbbell curl", "sets": 3}]},
    ]
    vol = {m["muscle"]: m["effective_sets"] for m in run("fitness-coach", "weekly_volume_audit", sessions=week)["per_muscle"]}
    assert vol == {"chest": 7, "back": 17, "shoulders": 9.5, "quads": 7, "hamstrings": 14, "glutes": 16, "biceps": 10, "triceps": 7, "calves": 3, "core": 3}
    z = run("fitness-coach", "heart_rate_zones", age=34, resting_hr=58)
    hrmax = round(208 - 0.7 * 34)
    assert z["max_hr"] == hrmax == 184 and z["zone2_bpm"] == [round(58 + 0.6 * (hrmax - 58)), round(58 + 0.7 * (hrmax - 58))] == [134, 146]


# ── meal-planner: 2,100 kcal / 160 P, a week of three batch recipes, $80 ──

def test_meal_split_and_day_totals():
    out = run("meal-planner", "split_macros", calories=2100, protein_g=160, carbs_g=210, fat_g=70, meals=4, pattern="post_workout", bodyweight_kg=78)
    assert out["daily"]["kcal_from_macros"] == 160 * 4 + 210 * 4 + 70 * 9 == 2110 and out["flags"] == []
    assert out["meals"][1] == {"meal": 2, "kcal": 662, "protein_g": 40, "carbs_g": 72, "fat_g": 24, "share_pct": 34}
    day = run("meal-planner", "nutrition_totals", protein_target_g=160, calorie_target=2100, items=[
        {"name": "Overnight oats", "calories": 560, "protein_g": 38, "carbs_g": 62, "fat_g": 17, "fiber_g": 11, "sodium_mg": 120},
        {"name": "Chicken rice bowl", "calories": 610, "protein_g": 45, "carbs_g": 64, "fat_g": 18, "fiber_g": 3, "sodium_mg": 1100},
        {"name": "Chicken chili", "calories": 420, "protein_g": 40, "carbs_g": 35, "fat_g": 12, "fiber_g": 10, "sodium_mg": 780},
        {"name": "2 eggs + banana", "calories": 250, "protein_g": 13, "carbs_g": 28, "fat_g": 10, "fiber_g": 3, "sodium_mg": 140},
        {"name": "Protein bar", "calories": 200, "protein_g": 20, "carbs_g": 24, "fat_g": 9, "fiber_g": 5, "sodium_mg": 200}])
    assert day["totals"]["calories"] == 2040 and day["totals"]["protein_g"] == 156 and day["totals"]["sodium_mg"] == 2340
    assert any("257 from macros" in f for f in day["flags"]) and any("Sodium" in f for f in day["flags"])


def test_meal_scaling_displays_measurable_amounts():
    out = run("meal-planner", "scale_recipe", from_servings=2, to_servings=7, ingredients=[
        {"name": "chicken breast", "qty": 300, "unit": "g"}, {"name": "soy sauce", "qty": 2, "unit": "tbsp"},
        {"name": "rice vinegar", "qty": 1, "unit": "tbsp"}, {"name": "broccoli", "qty": 1, "unit": "cup"}, {"name": "garlic", "qty": 2, "unit": "cloves"}])
    rows = {r["name"]: r for r in out["ingredients"]}
    assert out["factor"] == 3.5 and rows["chicken breast"]["display"] == "1050 g"
    assert rows["soy sauce"]["display"] == "7 tbsp" and rows["soy sauce"]["display_conservative"] == "⅓ cup"  # 5.25 tbsp
    assert rows["rice vinegar"]["display_conservative"] == "2 ½ tbsp + ½ tsp"  # 2.625 tbsp
    assert rows["broccoli"]["display"] == "3 ½ cup" and rows["garlic"]["display_conservative"] == "5 ½ cloves"


def test_meal_grocery_list_merges_and_respects_pantry():
    recipes = [
        {"name": "Chicken chili (6)", "ingredients": [
            {"name": "boneless skinless chicken thighs", "qty": 1.5, "unit": "lb"}, {"name": "onion, diced", "qty": 1.5, "unit": "each"},
            {"name": "garlic cloves, minced", "qty": 4.5, "unit": "clove"}, {"name": "black beans", "qty": 1.5, "unit": "can"},
            {"name": "crushed tomatoes", "qty": 1.5, "unit": "can"}, {"name": "chili powder", "qty": 1.5, "unit": "tbsp"},
            {"name": "ground cumin", "qty": 1.5, "unit": "tsp"}, {"name": "salt", "qty": 0.75, "unit": "tsp"}, {"name": "olive oil", "qty": 1.5, "unit": "tbsp"}]},
        {"name": "Chicken rice bowls (7)", "ingredients": [
            {"name": "chicken breast", "qty": 1050, "unit": "g"}, {"name": "jasmine rice", "qty": 525, "unit": "g"}, {"name": "garlic", "qty": 7, "unit": "cloves"},
            {"name": "soy sauce", "qty": 7, "unit": "tbsp"}, {"name": "rice vinegar", "qty": 3.5, "unit": "tbsp"}, {"name": "broccoli", "qty": 3.5, "unit": "cup"},
            {"name": "large eggs", "qty": 7, "unit": "large"}]},
        {"name": "Overnight oats (7)", "ingredients": [{"name": "rolled oats", "qty": 350, "unit": "g"}, {"name": "peanut butter", "qty": 7, "unit": "tbsp"}]},
        {"name": "Snack (7)", "ingredients": [{"name": "eggs", "qty": 14, "unit": ""}, {"name": "onion", "qty": 200, "unit": "g"}]},
    ]
    out = run("meal-planner", "grocery_list", recipes=recipes, pantry=["olive oil", "salt", "black pepper", "rice", "soy sauce"])
    items = {r["item"]: (aisle, r) for aisle, rows in out["by_aisle"].items() for r in rows}
    assert items["garlic"][1]["buy"] == math.ceil(4.5 + 7) == 12 and items["garlic"][0] == "produce"
    assert items["egg"][1]["buy"] == 7 + 14 and items["egg"][0] == "dairy & eggs"
    assert items["black bean"][1]["display"] == "2 cans (recipes use 1 ½)"
    assert items["chicken thigh"][1]["display"] == "680 g (1.50 lb)"  # 1.5 × 453.592 g
    assert items["broccoli"][1]["display"] == "3 ½ cup"
    for thing, aisle in (("ground cumin", "pantry"), ("chili powder", "pantry"), ("peanut butter", "pantry"), ("crushed tomato", "pantry"), ("rolled oat", "pantry")):
        assert items[thing][0] == aisle, thing
    assert sorted(out["skipped_from_pantry"]) == ["olive oil", "salt", "soy sauce"]
    assert "rice vinegar" in items and "jasmine rice" in items and len(out["check_pantry"]) == 2
    assert any(c.startswith("onion:") for c in out["unit_conflicts"])


def test_meal_cost_per_serving():
    out = run("meal-planner", "cost_per_serving", weekly_budget=80, people=1, days=7, meals_per_day=4, recipes=[
        {"name": "Chicken chili", "cost": 16.8, "servings": 6}, {"name": "Chicken rice bowls", "cost": 21.5, "servings": 7},
        {"name": "Overnight oats", "cost": 17.2, "servings": 7}, {"name": "Eggs + banana snack", "cost": 7.9, "servings": 7}])
    assert out["total_cost"] == 63.4 and out["cost_per_person_per_day"] == round(63.4 / 7, 2) == 9.06
    assert out["servings"] == 27 and out["servings_needed"] == 28 and out["vs_budget"] == -16.6


# ── travel-planner: Chicago → San Francisco → Tokyo, back after US DST ends ──

def _minutes(a, az, b, bz):
    d = datetime.strptime(a, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(az))
    e = datetime.strptime(b, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(bz))
    return int((e - d).total_seconds() // 60)


def test_travel_flight_durations_date_line_and_dst():
    legs = [
        ("2026-10-29 10:05", "America/Chicago", "2026-10-29 12:35", "America/Los_Angeles", 270),
        ("2026-10-29 14:10", "America/Los_Angeles", "2026-10-30 17:45", "Asia/Tokyo", 695),
        ("2026-11-08 16:05", "Asia/Tokyo", "2026-11-08 13:10", "America/Chicago", 725),  # CST: would be 665 on CDT
    ]
    for dep, dz, arr, az, expect in legs:
        out = run("travel-planner", "flight_time_and_jetlag", depart_local=dep, depart_tz=dz, arrive_local=arr, arrive_tz=az)
        assert out["duration_minutes"] == _minutes(dep, dz, arr, az) == expect
    back = run("travel-planner", "flight_time_and_jetlag", depart_local="2026-11-08 16:05", depart_tz="Asia/Tokyo", arrive_local="2026-11-08 13:10", arrive_tz="America/Chicago")
    assert back["timezone_shift_hours"] == 9.0 and back["direction"] == "east" and back["calendar_days_elapsed"] == 0


def test_travel_jet_lag_uses_the_journey_not_the_last_leg():
    leg = run("travel-planner", "flight_time_and_jetlag", depart_local="2026-10-29 14:10", depart_tz="America/Los_Angeles",
              arrive_local="2026-10-30 17:45", arrive_tz="Asia/Tokyo", body_clock_tz="America/Chicago")
    assert leg["zones_crossed"] == 10 and leg["direction"] == "west" and leg["days_to_adjust"] == round(10 / 1.5, 1)
    whole = run("travel-planner", "flight_time_and_jetlag", depart_local="2026-10-29 10:05", depart_tz="America/Chicago",
                arrive_local="2026-10-30 17:45", arrive_tz="Asia/Tokyo")
    assert whole["duration"] == "17h 40m" and whole["zones_crossed"] == 10


def test_travel_connection_day_plan_budget_and_call_window():
    conn = run("travel-planner", "connection_check", arrival_time="2026-10-29 12:35", departure_time="2026-10-29 14:10", same_ticket=True, international_departure=True)
    assert conn["layover_minutes"] == 95 and conn["minimum_required_minutes"] == 90 and conn["risk"] == "medium"
    assert "rebooks" in conn["verdict"] and "MCT" in conn["basis"]
    plan = run("travel-planner", "day_planner", start_date="2026-10-30", stops=[{"city": "Tokyo", "nights": 4}, {"city": "Kyoto", "nights": 3}, {"city": "Tokyo", "nights": 2}],
               arrival_time="17:45", departure_time="16:05", pace="moderate")
    s = plan["schedule"]
    assert plan["days"] == 10 and plan["nights"] == 9 and plan["full_days"] == 6
    assert s[0]["usable_hours"] == 2.2 and s[-1]["usable_hours"] == round(16 + 5 / 60 - 3 - 8, 1) == 5.1
    assert s[-1]["date"] == "2026-11-08" and "13:05" in s[-1]["notes"][0]
    assert [r["type"] for r in s if r["type"] == "transfer"] == ["transfer", "transfer"]
    budget = run("travel-planner", "trip_budget", days=10, travelers=2, contingency_pct=10, home_currency_rate=0.0067, home_currency="USD", items=[
        {"category": "flights", "amount": 285000, "per": "person"}, {"category": "lodging", "amount": 22000, "per": "night"},
        {"category": "food", "amount": 6000, "per": "person_day"}, {"category": "transport", "amount": 28340, "per": "person"},
        {"category": "transport local", "amount": 1200, "per": "person_day"}, {"category": "activities", "amount": 30000, "per": "trip"},
        {"category": "insurance", "amount": 9000, "per": "person"}])
    sub = 570000 + 22000 * 9 + 120000 + 56680 + 24000 + 30000 + 18000
    assert budget["subtotal"] == sub == 1016680 and budget["total"] == round(sub * 1.1, 2)
    assert budget["per_person_per_day"] == round(sub * 1.1 / 20, 2) and budget["home_currency_total"] == round(sub * 1.1 * 0.0067, 2)
    for day, expect in (("2026-10-31", 14.0), ("2026-11-02", 15.0)):
        call = run("travel-planner", "call_home_window", date=day, here_tz="Asia/Tokyo", home_tz="America/Chicago")
        assert call["hours_ahead_of_home"] == expect
    assert call["best_window"]["here"] == "08:00-13:00" and call["best_window"]["home"] == "Sun 17:00-22:00"


# ── study-coach: pharmacology final, 6 topics, 8 h/week, cards graded with SM-2 ──

def _sm2(ease, q, reps, interval):
    """Wozniak 1990 SM-2, written from the paper: EF unchanged when q < 3; intervals rounded up."""
    if q < 3:
        return ease, 0, 1
    ef = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    n = reps + 1
    return ef, n, 1 if n == 1 else 6 if n == 2 else math.ceil(interval * ef - 1e-9)


def test_study_sm2_matches_published_algorithm():
    cards = [{"id": "c1", "quality": 5}, {"id": "c2", "quality": 4, "repetitions": 1, "interval_days": 1, "ease": 2.5},
             {"id": "c3", "quality": 3, "repetitions": 2, "interval_days": 6, "ease": 2.5}, {"id": "c4", "quality": 5, "repetitions": 3, "interval_days": 15, "ease": 2.6},
             {"id": "c5", "quality": 2, "repetitions": 3, "interval_days": 15, "ease": 2.36}, {"id": "c6", "quality": 4, "repetitions": 4, "interval_days": 39, "ease": 2.7}]
    out = run("study-coach", "sm2_review", cards=cards, review_date="2026-11-10", exam_date="2026-12-11")
    by = {c["id"]: c for c in out["cards"]}
    for c in cards:
        ef, n, iv = _sm2(c.get("ease", 2.5), c["quality"], c.get("repetitions", 0), c.get("interval_days", 0))
        assert (by[c["id"]]["ease"], by[c["id"]]["repetitions"], by[c["id"]]["interval_days"]) == (round(ef, 2), n, iv), c["id"]
    assert [by[k]["interval_days"] for k in ("c3", "c4", "c6")] == [15, 41, 106] and by["c5"]["ease"] == 2.36
    assert out["redrill_today"] == ["c3", "c5"] and out["due_after_exam"] == ["c4", "c6"]
    assert by["c6"]["due"] == "2027-02-24" and by["c6"]["review_before_exam"] == "2026-12-09"


def test_study_load_calendar_cards_and_session():
    topics = [{"topic": "Autonomic drugs", "weight": 20, "hours_needed": 9}, {"topic": "Cardiovascular", "weight": 25, "hours_needed": 12},
              {"topic": "Antimicrobials", "weight": 20, "hours_needed": 10}, {"topic": "CNS", "weight": 15, "hours_needed": 8},
              {"topic": "Endocrine", "weight": 10, "hours_needed": 5}, {"topic": "Pharmacokinetics", "weight": 10, "hours_needed": 6}]
    load = run("study-coach", "study_load", exam_date="2026-12-11", today="2026-10-26", hours_per_week=8, topics=topics)
    assert load["days_left"] == 46 and load["study_days"] == 42 and load["hours_available"] == 48.0
    assert load["fits"] is False and any("8.3" in f for f in load["flags"])
    cal = run("study-coach", "review_calendar", exam_date="2026-12-11", topics=[
        {"topic": "Autonomic drugs", "learned_on": "2026-10-27"}, {"topic": "Pharmacokinetics", "learned_on": "2026-10-29"},
        {"topic": "Cardiovascular", "learned_on": "2026-11-03"}, {"topic": "Antimicrobials", "learned_on": "2026-11-10"},
        {"topic": "CNS", "learned_on": "2026-11-17"}, {"topic": "Endocrine", "learned_on": "2026-11-24"}])
    auto = next(t for t in cal["topics"] if t["topic"] == "Autonomic drugs")
    assert auto["reviews"] == ["2026-10-28", "2026-10-30", "2026-11-03", "2026-11-10", "2026-11-26", "2026-12-09"]
    assert not any("> 4" in f for f in cal["flags"]) and any("mixed, timed practice test" in f for f in cal["flags"])
    anki = run("study-coach", "anki_export", deck="Pharm Final", cards=[
        {"front": "Is propranolol cardioselective?", "back": "No"},
        {"front": "Name the aminoglycosides", "back": "Gentamicin, tobramycin, amikacin, streptomycin, neomycin"},
        {"front": "Why does first-pass metabolism lower oral bioavailability?", "back": "Liver metabolises drug\nbefore systemic circulation"}])
    issues = {i["card"]: i["detail"] for i in anki["issues"]}
    assert "yes/no" in issues[1] and "cloze" in issues[2] and "<br>" not in anki["file_content"]
    session = run("study-coach", "pomodoro_plan", start_time="18:30", available_minutes=150, tasks=[
        {"name": "Cardio drug cards (new)", "minutes": 50, "priority": 1}, {"name": "Autonomic review", "minutes": 25, "priority": 2},
        {"name": "PK practice problems", "minutes": 50, "priority": 3}])
    kinds = [b["type"] for b in session["schedule"]]
    assert kinds.count("work") == 5 and all(not (a == b == "work") for a, b in zip(kinds, kinds[1:]))
    assert session["end"] == "20:55" and session["unfinished"] == []
