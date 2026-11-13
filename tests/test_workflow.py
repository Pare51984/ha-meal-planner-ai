"""Wochenablauf: Vorschläge, Auswahl, Einkauf, Wochenwechsel, Zeitplan."""
import json
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_fire_time_changed
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, SupportsResponse

from .test_integration import PAGES, URL1, URL2, call, page

DOMAIN = "meal_planner_ai"
URL3 = "https://www.chefkoch.de/rezepte/3/Gemuesepfanne.html"
URL4 = "https://www.chefkoch.de/rezepte/4/Schmorbraten.html"
URL_TM_EN = "https://cookidoo.de/recipes/recipe/en-US/r123"
URL_TM_DE = "https://cookidoo.de/recipes/recipe/de-DE/r123"
URL_TM_FR = "https://cookidoo.de/recipes/recipe/fr-FR/r999"
URL_TM_IT = "https://cookidoo.de/recipes/recipe/it-IT/r555"
URL_TM_DE_ALT = "https://cookidoo.de/recipes/recipe/de-DE/r777"
PAGES[URL3] = page("Gemüsepfanne", ["2 Paprika", "1 Zucchini", "1 EL Öl", "1 TL Paprikapulver"], 300, URL3)
PAGES[URL4] = page("Schmorbraten", ["1 kg Rindfleisch"], 700, URL4)
PAGES[URL4] = PAGES[URL4].replace("PT35M", "PT180M")
PAGES[URL_TM_DE] = page("Käsespätzle", ["400 g Spätzle", "200 g Bergkäse"], 600, URL_TM_DE)
PAGES[URL_TM_FR] = page("Curry au lait de coco", ["400 ml Kokosmilch"], 500, URL_TM_FR)
PAGES[URL_TM_IT] = page("Risotto ai funghi", ["300 g Reis"], 550, URL_TM_IT)
PAGES[URL_TM_DE_ALT] = page("Pilzrisotto", ["300 g Risottoreis", "250 g Champignons"], 520, URL_TM_DE_ALT)
PROMPTS = []
NOTES = []
CAL_EVENTS = {"calendar.gast": [{"start": "2026-11-19", "end": "2026-11-22", "summary": "Papa-Wochenende"}],
              "calendar.familie": [{"start": "2026-11-16T15:00:00+01:00", "end": "2026-11-16T16:00:00+01:00", "summary": "Gast abholen"},
                                   {"start": "2026-11-17T09:00:00+01:00", "end": "2026-11-17T10:00:00+01:00", "summary": "Zahnarzt"}]}


async def fake_calendar(call):
    return {e: {"events": CAL_EVENTS.get(e, [])} for e in call.data["entity_id"]}


async def fake_ai(call):
    name = call.data["task_name"]
    text = call.data["instructions"]
    PROMPTS.append(text)
    if name == "Essensplaner Wochenvorschläge":
        dishes = [
            {"title": "Gemüsecurry", "own_recipe": True, "wish": "Gemüsecurry", "meatless": True},
            {"title": "Schmorbraten", "url": URL4, "tip": "trip1"},             # zu lang
            {"title": "Nudeln mit Spinat-Hackfleisch-Soße", "url": URL1, "tip": "trip2"},
            {"title": "Linsencurry", "url": URL2, "tip": "trip1", "low_cholesterol": True},
            {"title": "Linsencurry", "url": URL2},                              # doppelt
            {"title": "Gemüsepfanne", "url": URL3, "tip": "trip1", "fits": ["Gast ok", "Unsinn"]},
            {"title": "Spätzle (TM)", "url": URL_TM_EN, "time_min": 30, "kcal": 500},
            {"title": "Curry (TM)", "url": URL_TM_FR, "time_min": 30, "kcal": 500},
            {"title": "Risotto (TM)", "url": URL_TM_IT, "time_min": 30, "kcal": 500},
            {"title": "Erfunden", "url": "https://www.chefkoch.de/rezepte/999/x.html"},
        ]
        return {"conversation_id": "x", "data": json.dumps({"dishes": dishes})}
    if name == "Essensplaner Cookidoo Landessprache":
        if "Risotto" in text:
            return {"conversation_id": "x", "data": {"url": URL_TM_DE_ALT, "title": "Pilzrisotto"}}
        return {"conversation_id": "x", "data": {"url": None}}
    raise AssertionError(name)


async def fake_fetch2(hass, url):
    if url not in PAGES:
        from homeassistant.exceptions import HomeAssistantError
        raise HomeAssistantError("HTTP 404")
    return PAGES[url], url


async def _items(hass):
    resp = await hass.services.async_call("todo", "get_items", {"entity_id": "todo.meal_planner_shopping_list",
                                          "status": "needs_action"}, blocking=True, return_response=True)
    return {i["summary"]: i.get("description") for i in resp["todo.meal_planner_shopping_list"]["items"]}


async def test_week(hass: HomeAssistant, freezer):
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-11-11 10:00:00+01:00")  # Mittwoch
    hass.states.async_set("ai_task.gemini", "unknown", {"friendly_name": "Gemini"})
    hass.services.async_register("ai_task", "generate_data", fake_ai, supports_response=SupportsResponse.ONLY)
    hass.services.async_register("notify", "handy", lambda c: NOTES.append(c.data))
    hass.services.async_register("calendar", "get_events", fake_calendar, supports_response=SupportsResponse.ONLY)
    hass.states.async_set("calendar.gast", "off")
    hass.states.async_set("calendar.familie", "off")

    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"region": "de", "shopping_list": "own"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"devices": ["stove_oven"]})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"ai_task": "ai_task.gemini", "ai_shopping_names": False})
    await hass.config_entries.flow.async_configure(r["flow_id"], {"display": "none"})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    async def options(step, data):
        f = await hass.config_entries.options.async_init(entry.entry_id)
        f = await hass.config_entries.options.async_configure(f["flow_id"], {"next_step_id": step})
        for d in data:
            f = await hass.config_entries.options.async_configure(f["flow_id"], d)
        await hass.async_block_till_done()
        return f

    diet = {f"{k}_mode": "off" for k in ["vegetarian", "vegan", "lactose_free", "gluten_free", "low_cholesterol"]}
    diet.update({"vegetarian_mode": "count", "vegetarian_count": 2})
    await options("diet_count", [{"recipes_per_week": 4}, diet])
    f = await options("rules", [{"portions": 3, "time_max": 60, "time_quick": 40, "quick_share": 3,
                                 "kcal_aware": True, "profile": "bodenständig"},
                                {"kcal_max": 800, "kcal_max_without_side": 650}])
    assert f["type"] == "create_entry", f
    f = await options("habits", [{"habit_1": "Suppen/Eintöpfe höchstens 1x pro Woche", "habit_3": "mindestens 1x Fisch"}])
    assert f["type"] == "create_entry", f
    assert entry.options["habits"] == ["Suppen/Eintöpfe höchstens 1x pro Woche", "mindestens 1x Fisch"]
    f = await options("schedule", [{"plan_weekday": "fri", "plan_time": "18:00:00", "deadline_weekday": "sat",
                                    "deadline_time": "12:00:00",
                                    "notify": ["notify.handy"], "dashboard_path": "/lovelace/essen"}])
    assert f["type"] == "create_entry", f
    f = await options("trips", [{"count": "2"}, {
        "name_1": "Sa–Di", "days_1": ["sat", "sun", "mon", "tue"], "release_1": "immediate",
        "name_2": "Mi–Fr", "days_2": ["wed", "thu", "fri"], "release_2": "timed",
        "weekday_2": "mon", "time_2": "18:00:00"}])
    assert f["type"] == "create_entry", f

    f = await options("calendar", [{
        "label_1": "Gast ok", "calendars_1": ["calendar.gast"], "keyword_1": "",
        "hint_1": "An diesen Tagen isst ein Kind mit: nicht scharf.",
        "label_2": "Gast ok", "calendars_2": ["calendar.familie"], "keyword_2": "Gast",
        "hint_2": "Kind kommt dazu."}])
    assert f["type"] == "create_entry", f

    # Wunsch eintragen
    await hass.services.async_call("todo", "add_item", {"entity_id": "todo.meal_planner_wishes",
                                   "item": "Gemüsecurry eigenes Rezept"}, blocking=True)

    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch2):
        # Freitag 18 Uhr: Zeitplan erzeugt die Vorschläge
        freezer.move_to("2026-11-13 18:00:05+01:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        st = hass.states.get("sensor.meal_planner_proposals")
        assert st.state == "4", st
        assert st.attributes["kw"] == 47
        titles = [d["title"] for d in st.attributes["dishes"]]
        assert titles[0] == "Gemüsecurry" and set(titles) == {
            "Gemüsecurry", "Nudeln mit Spinat-Hackfleisch-Soße", "Linsencurry", "Gemüsepfanne"}
        plan_prompts = [p for p in PROMPTS if p.startswith("Du bist der Essensplaner")]
        prompt = plan_prompts[-1]
        assert "Grundregeln und Geschmack des Haushalts:\nbodenständig" in prompt
        assert 'trip2 = "Mi–Fr" (kommt Mo 16.11. 18:00 auf die Liste, für Mi, Do, Fr)' in prompt
        assert "Do 19.11.: Papa-Wochenende" in prompt and "Fr 20.11.: Papa-Wochenende" in prompt
        assert "Sa 21.11." not in prompt  # nach dem Wochenende der Planung
        assert "Mo 16.11.: Gast abholen" in prompt and "Zahnarzt" not in prompt
        assert "An diesen Tagen isst ein Kind mit: nicht scharf." in prompt
        assert [(t["key"], t["name"]) for t in st.attributes["trips"]] == [("trip1", "Sa–Di"), ("trip2", "Mi–Fr")]
        assert st.attributes["schedule"]["plan_time"]
        assert any("Neue Essensvorschläge" in n["title"] for n in NOTES)
        assert NOTES[-1]["data"]["clickAction"] == "/lovelace/essen"
        wishes = await hass.services.async_call("todo", "get_items", {"entity_id": "todo.meal_planner_wishes"},
                                                blocking=True, return_response=True)
        assert wishes["todo.meal_planner_wishes"]["items"] == []
        dish = {d["title"]: d for d in st.attributes["dishes"]}
        assert dish["Gemüsepfanne"]["meatless"] is True and dish["Nudeln mit Spinat-Hackfleisch-Soße"]["meatless"] is False
        assert dish["Gemüsepfanne"]["fits"] == ["Gast ok"]

        # Auswahl: sofort auf die Liste (erster Einkauf), zweiter Einkauf wartet
        await call(hass, "choose_dish", {"dish_id": dish["Linsencurry"]["id"], "choice": "trip1"})
        await call(hass, "choose_dish", {"dish_id": dish["Gemüsepfanne"]["id"], "choice": "trip1"})
        await call(hass, "choose_dish", {"dish_id": dish["Nudeln mit Spinat-Hackfleisch-Soße"]["id"], "choice": "trip2"})
        await call(hass, "choose_dish", {"dish_id": dish["Gemüsecurry"]["id"], "choice": "trip1"})
        items = await _items(hass)
        assert items == {"Linsen": "150 g (Linsencurry)", "Kokosmilch": "300 ml (Linsencurry)",
                         "Zwiebel": "1 (Linsencurry)", "Paprika": "2 (Gemüsepfanne)",
                         "Zucchini": "1 (Gemüsepfanne)"}, items
        # Abwählen nimmt wieder runter
        await call(hass, "choose_dish", {"dish_id": dish["Gemüsepfanne"]["id"], "choice": "declined"})
        assert "Paprika" not in await _items(hass)

        # Samstag 12 Uhr: Auswahlschluss
        freezer.move_to("2026-11-14 12:00:05+01:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get("sensor.meal_planner_proposals").state == "0"
        week = hass.states.get("sensor.meal_planner_week")
        assert week.state == "3"
        assert {d["title"] for d in week.attributes["dishes"]} == {
            "Gemüsecurry", "Linsencurry", "Nudeln mit Spinat-Hackfleisch-Soße"}

        # Teilweise da: bei den Nudeln ist das Hackfleisch schon im Haus
        items_resp = await call(hass, "dish_items", {"dish_id": dish["Nudeln mit Spinat-Hackfleisch-Soße"]["id"]})
        assert {i["name"] for i in items_resp["items"]} == {"Nudeln", "Hackfleisch", "Spinat", "Zwiebeln"}
        await call(hass, "set_items_at_home", {"dish_id": dish["Nudeln mit Spinat-Hackfleisch-Soße"]["id"],
                                                "items": ["Hackfleisch"]}, response=False)

        # Montag 18 Uhr: zweiter Einkauf
        freezer.move_to("2026-11-16 18:00:05+01:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        items = await _items(hass)
        assert items["Nudeln"] == "375 g (Nudeln mit Spinat-Hackfleisch-Soße)"
        assert items["Zwiebel"] == "1 (Linsencurry) + 1 (Nudeln mit Spinat-Hackfleisch-Soße)"
        assert "Hackfleisch" not in items

        # Zutaten schon da: Linsencurry runter, Zwiebel bleibt für das andere Gericht
        await call(hass, "set_ingredients_ready", {"dish_id": dish["Linsencurry"]["id"]})
        items = await _items(hass)
        assert "Linsen" not in items and items["Zwiebel"] == "1 (Nudeln mit Spinat-Hackfleisch-Soße)"

        # Gekocht und bewertet
        await call(hass, "mark_cooked", {"dish_id": dish["Nudeln mit Spinat-Hackfleisch-Soße"]["id"], "rating": 10})
        rec = await call(hass, "get_recipe", {"url": URL1})
        assert rec["history"]["rating"] == 10 and rec["history"]["status"] == "cooked"

        # Nächster Freitag: Linsencurry (Zutaten da, nicht gekocht) wird NICHT übernommen (ab 0.45),
        # Nudeln sind frisch gekocht und gut bewertet -> im Prompt als gemocht + zuletzt gekocht
        freezer.move_to("2026-11-20 18:00:05+01:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        st = hass.states.get("sensor.meal_planner_proposals")
        titles = [d["title"] for d in st.attributes["dishes"]]
        assert "Linsencurry" not in titles and not any(d.get("carried") for d in st.attributes["dishes"])
        plan_prompt = [p for p in PROMPTS if p.startswith("Du bist der Essensplaner")][-1]
        assert "Nudeln mit Spinat-Hackfleisch-Soße (10/10)" in plan_prompt
        assert "In den letzten 4 Wochen gekocht" in plan_prompt
        assert "Nudeln mit Spinat-Hackfleisch-Soße" not in [d["title"] for d in st.attributes["dishes"]]
        # Gerichte der laufenden Woche schlägt auch die KI nicht erneut vor
        assert "linsencurry" in plan_prompt.lower().split("nicht vorschlagen")[-1]


async def test_three_trips_sunday(hass: HomeAssistant, freezer):
    """Andere Haushalte: drei Einkäufe, einer sonntags (Länder mit Sonntagsöffnung)."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.config.language = "de"
    hass.config.country = "DE"
    freezer.move_to("2026-11-11 10:00:00+01:00")
    hass.states.async_set("ai_task.gemini", "unknown")
    hass.services.async_register("ai_task", "generate_data", fake_ai, supports_response=SupportsResponse.ONLY)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"region": "de", "shopping_list": "own"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"devices": ["stove_oven", "thermomix"]})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"ai_task": "ai_task.gemini", "ai_shopping_names": False})
    await hass.config_entries.flow.async_configure(r["flow_id"], {"display": "none"})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    f = await hass.config_entries.options.async_init(entry.entry_id)
    f = await hass.config_entries.options.async_configure(f["flow_id"], {"next_step_id": "trips"})
    f = await hass.config_entries.options.async_configure(f["flow_id"], {"count": "3"})
    f = await hass.config_entries.options.async_configure(f["flow_id"], {
        "name_1": "Mo", "release_1": "immediate", "name_2": "Mi", "release_2": "immediate",
        "name_3": "Sonntag", "release_3": "timed", "weekday_3": "sun", "time_3": "09:00:00"})
    assert f["type"] == "create_entry"
    await hass.async_block_till_done()
    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch2):
        await call(hass, "generate_proposals", {}, response=False)
        st = hass.states.get("sensor.meal_planner_proposals")
        d = {x["title"]: x for x in st.attributes["dishes"]}
        # Cookidoo: deutsche Version gefunden -> diese; keine deutsche -> bleibt, mit Hinweis
        assert d["Spätzle (TM)"]["url"] == URL_TM_DE and d["Spätzle (TM)"]["foreign_language"] is None
        assert d["Curry (TM)"]["url"] == URL_TM_FR and d["Curry (TM)"]["foreign_language"] == "fr-FR"
        # kein gleiches Rezept auf Deutsch, aber ein gleichwertiges Gericht -> das deutsche
        assert d["Pilzrisotto (TM)"]["url"] == URL_TM_DE_ALT and d["Pilzrisotto (TM)"]["foreign_language"] is None
        await call(hass, "choose_dish", {"dish_id": d["Linsencurry"]["id"], "choice": "trip3"}, response=False)
        assert await _items(hass) == {}
        import pytest
        from homeassistant.exceptions import ServiceValidationError
        with pytest.raises(ServiceValidationError):
            await call(hass, "choose_dish", {"dish_id": d["Linsencurry"]["id"], "choice": "trip5"}, response=False)
        freezer.move_to("2026-11-15 09:00:05+01:00")  # Sonntag
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert "Linsen" in await _items(hass)


async def test_schedule_math():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from custom_components.meal_planner_ai.board import week_meta
    from custom_components.meal_planner_ai.planning import settings_from_options
    tz = ZoneInfo("Europe/Berlin")
    meta = week_meta(datetime(2026, 11, 6, 18, 0, tzinfo=tz), settings_from_options({}))
    assert meta["kw"] == 46 and meta["start"] == "2026-11-07" and meta["deadline"].startswith("2026-11-07T12:00")
    assert meta["release_at"]["trip2"].startswith("2026-11-09T18:00")
    assert meta["released"] == {"trip1": True, "trip2": False}
