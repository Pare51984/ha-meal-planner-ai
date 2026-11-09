"""Absicherung aus dem Code-Review: fremde Adressen, kaputte KI-Daten, Fehlschleifen, Läufe über die Deadline."""
import asyncio
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.meal_planner_ai.ai import AIError
from custom_components.meal_planner_ai.services import RecipeFetchError, fetch_html

from .test_external import _external
from .test_integration import DOMAIN, URL2, call, page, setup_entry
from .test_workflow import fake_fetch2

SVC = "custom_components.meal_planner_ai.services"


# ---------------------------------------------------------------- Nr. 1 SSRF ---
@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://10.0.0.1/x", "http://169.254.169.254/latest",
                                 "http://[::1]/", "file:///etc/passwd", "ftp://example.org/x"])
async def test_fetch_rejects_private_hosts(hass: HomeAssistant, url):
    with pytest.raises(RecipeFetchError):
        await fetch_html(hass, url)


async def test_fetch_rejects_names_resolving_inside(hass: HomeAssistant):
    with patch(f"{SVC}._resolve", return_value=["192.168.0.5"]), pytest.raises(RecipeFetchError, match="lokale Netz"):
        await fetch_html(hass, "https://evil.example/rezept")


async def test_redirect_to_private_host_blocked(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get("https://share.example/x", status=302, headers={"Location": "http://192.168.0.1/admin"})
    with patch(f"{SVC}._resolve", return_value=["93.184.216.34"]), pytest.raises(RecipeFetchError):
        await fetch_html(hass, "https://share.example/x")


async def test_redirect_to_public_host_followed(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get("https://share.example/x", status=302, headers={"Location": "https://www.chefkoch.de/r/1"})
    aioclient_mock.get("https://www.chefkoch.de/r/1", text="<html>ok</html>")
    with patch(f"{SVC}._resolve", return_value=["93.184.216.34"]):
        html, final = await fetch_html(hass, "https://share.example/x")
    assert html == "<html>ok</html>" and final == "https://www.chefkoch.de/r/1"


async def test_wish_does_not_unlock_foreign_host(hass: HomeAssistant):
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    planner._wish_texts = {"ei", "lasagne"}
    planner._wish_hosts = {"meine-seite.example"}
    assert not planner._is_open_wish("Eintopf", "Eintopf")  # „Ei“ ist zu kurz und kein ganzes Wort
    assert planner._is_open_wish("Lasagne", "Gemüse-Lasagne")
    today = dt_util.now().date()
    foreign = "https://fremd.example/lasagne"
    own = "https://meine-seite.example/lasagne"

    async def fetch(hass, url):
        return page("Lasagne", ["500 g Nudeln"], 600, url), url

    with patch(f"{SVC}.fetch_html", side_effect=fetch):
        dish, why = await planner._check_dish({"title": "Lasagne", "wish": "Lasagne", "url": foreign}, set(), today,
                                              searched=True)
        assert dish is None and "nicht freigegeben" in why
        dish, why = await planner._check_dish({"title": "Lasagne", "wish": "Lasagne", "url": own}, set(), today,
                                              searched=True)
        assert why is None and dish["url"] == own


# ------------------------------------------------------- Nr. 3 und 4 Eingaben ---
async def test_submit_survives_broken_fields(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    await _external(hass)
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        res = await call(hass, "submit_proposals", {"dishes": [
            {"title": "Linsencurry", "url": URL2, "kcal": "abc", "time_min": "viel", "fits": 5, "wish": 7},
            {"title": None, "url": 42},
        ]})
    assert res["accepted"] == ["Linsencurry"]


async def test_submit_caps_proposals_and_search(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    await _external(hass)
    fetched, searched = [], []

    async def dead(hass, url):
        fetched.append(url)
        raise RecipeFetchError("Rezeptseite antwortet mit HTTP 404 (x).", 404)

    async def search(hass, host, query, locale):
        searched.append(host)
        return [f"https://{host}/tot/{len(searched)}a", f"https://{host}/tot/{len(searched)}b"]

    dishes = [{"title": f"Gericht {i}", "url": f"https://www.chefkoch.de/rezepte/{i}/x.html"} for i in range(60)]
    with patch(f"{SVC}.fetch_html", side_effect=dead), \
            patch("custom_components.meal_planner_ai.board.async_search", side_effect=search):
        res = await call(hass, "submit_proposals", {"dishes": dishes})
    assert "ignored" in res and res["count"] == 0
    # 20 geprüfte Links plus höchstens 40 Abrufe für die Ersatzsuche
    assert len(fetched) + len(searched) <= 20 + 40


# ------------------------------------------------- Nr. 2 und 7 Lauf vs. Deadline ---
async def test_finalize_waits_for_running_submit(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2}]})
    dish_id = planner.boards["next"]["dishes"][0]["id"]
    await call(hass, "choose_dish", {"dish_id": dish_id, "choice": "trip1"})

    gate = asyncio.Event()
    real_accept = planner._accept

    async def slow_accept(*args, **kwargs):
        await gate.wait()
        return await real_accept(*args, **kwargs)

    freezer.move_to("2026-11-14 11:59:00+01:00")
    with patch.object(planner, "_accept", side_effect=slow_accept), \
            patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        task = hass.async_create_task(planner.async_submit_proposals([], final=True))
        await asyncio.sleep(0)
        assert planner.busy
        freezer.move_to("2026-11-14 12:05:00+01:00")
        assert await planner.async_tick(dt_util.now()) == []  # Auswahlschluss wartet auf den Lauf
        with pytest.raises(HomeAssistantError):
            await planner.async_submit_proposals([])  # zweiter Lauf parallel gesperrt
        gate.set()
        await task
        await hass.async_block_till_done()  # Nachhol-Tick nach dem Lauf
    cur = planner.boards["current"]
    assert cur and [d["title"] for d in cur["dishes"] if d["choice"] == "trip1"] == ["Linsencurry"]


async def test_publish_refuses_closed_week(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    meta = planner._plan_meta()
    planner.boards["current"] = {**meta, "dishes": [{"title": "fertig"}]}
    with pytest.raises(HomeAssistantError, match="abgeschlossen"):
        await planner._publish(meta, [], [], [], rounds=1, source="ha", excluded=set(), notify=False)
    assert planner.boards["current"]["dishes"] == [{"title": "fertig"}]


# --------------------------------------------------------- Nr. 5 Fehlschleife ---
async def test_ai_failure_backoff(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 17:00:00+01:00")
    await hass.config.async_set_time_zone("Europe/Berlin")
    hass.states.async_set("ai_task.claude", "unknown")
    entry = await setup_entry(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "ai_task": "ai_task.claude",
                                                           "notify": ["notify.handy"]})
    await hass.async_block_till_done()
    planner = entry.runtime_data.planner
    sent, asked = [], []

    async def notify(call):
        sent.append(call.data)

    hass.services.async_register("notify", "handy", notify)

    async def broken(prompt):
        asked.append(prompt)
        raise AIError("Kontingent erschöpft")

    with patch.object(planner, "_ask_proposals", side_effect=broken):
        for hour in range(18, 24):
            freezer.move_to(f"2026-11-13 {hour}:00:20+01:00")
            await planner.async_tick(dt_util.now())
    assert len(asked) == 3 and len(sent) == 1


# ------------------------------------------------------ Nr. 6 Liste fehlt im Tick ---
async def test_tick_survives_failing_finalize(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2}]})
    freezer.move_to("2026-11-14 12:00:05+01:00")
    with patch.object(planner, "async_finalize", side_effect=HomeAssistantError("Liste weg")):
        done = await planner.async_tick(dt_util.now())
    assert "finalize" not in done


# ------------------------------------------------------- Nr. 8 Einstellungen ---
async def test_settings_frozen_during_run(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    seen = []

    async def job():
        hass.config_entries.async_update_entry(entry, options={**entry.options, "recipes_per_week": 3})
        seen.append(planner.settings["recipes_per_week"])
        return {}

    before = planner.settings["recipes_per_week"]
    await planner._run(job())
    assert seen == [before] != [3]


# --------------------------------------------- Nr. 9 umbenannte Wunschliste ---
async def test_renamed_wishes_entity_still_used(hass: HomeAssistant):
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    reg = er.async_get(hass)
    reg.async_update_entity("todo.meal_planner_wishes", new_entity_id="todo.wunschliste")
    await hass.async_block_till_done()
    await hass.services.async_call("todo", "add_item", {"entity_id": "todo.wunschliste", "item": "Lasagne"},
                                   blocking=True)
    assert [w["text"] for w in await planner._wishes()] == ["Lasagne"]
    planner._changed()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.meal_planner_proposals").attributes["wishes_entity"] == "todo.wunschliste"


# ------------------------------------------------------- Nr. 10 Rezept-URL ---
def test_parse_rejects_javascript_canonical():
    from custom_components.meal_planner_ai.parser import parse_recipe

    html = page("Suppe", ["1 l Wasser"], 100, "https://x.example/s").replace(
        "<head>", '<head><link rel="canonical" href="javascript:alert(1)">')
    assert parse_recipe(html, "https://x.example/s")["source_url"] == "https://x.example/s"


# ---------------------------------------------- Nr. 11 alte Instanz abschalten ---
async def test_takeover_disables_old_entry(hass: HomeAssistant):
    from homeassistant.data_entry_flow import FlowResultType
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    old = MockConfigEntry(domain="essensplaner", title="Essensplaner", data={},
                          options={"region": "de", "shopping_list": "own", "display": "none"})
    old.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"import_settings": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(old.entry_id).disabled_by is config_entries.ConfigEntryDisabler.USER


# ---------------------------------------------- Nr. 13 Löschen räumt auf ---
async def test_remove_entry_deletes_storage(hass: HomeAssistant, hass_storage):
    entry = await setup_entry(hass)
    await call(hass, "update_history", {"title": "Linsencurry", "rating": 5}, response=False)
    await entry.runtime_data.store.async_flush()
    assert "meal_planner_ai.recipes" in hass_storage
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert "meal_planner_ai.recipes" not in hass_storage


# ------------------------------------------------- Nr. 15 Sprache der Texte ---
async def test_option_labels_follow_language(hass: HomeAssistant):
    hass.config.language = "en"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    labels = [o["label"] for o in result["data_schema"].schema["shopping_list"].config["options"]]
    assert "Create the meal planner's own list" in labels
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"region": "en", "shopping_list": "own"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"devices": ["stove_oven"]})
    assert result["data_schema"].schema["ai_task"].config["options"][0]["label"] == "No AI"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ai_task": "none"})
    await hass.config_entries.flow.async_configure(result["flow_id"], {"display": "none"})
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert [t["name"] for t in entry.options["trips"]] == ["Shopping 1", "Shopping 2"]


# ------------------------------------------------- Nr. 18 Profil ohne Reload ---
async def test_set_profile_does_not_reload(hass: HomeAssistant):
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    await call(hass, "set_profile", {"text": "Keine Pilze"}, response=False)
    await hass.async_block_till_done()
    assert entry.runtime_data.planner is planner  # gleiche Instanz = nicht neu geladen
    assert planner.settings["profile"] == "Keine Pilze"


def test_prompt_truncates_long_inputs():
    from custom_components.meal_planner_ai.ai import assess_prompt, shopping_prompt

    rec = {"id": "a", "title": "x", "ingredients": ["y" * 500] * 200}
    text = assess_prompt([rec], ["low_cholesterol"])
    assert "y" * 121 not in text and text.count("y" * 120) == 60
    text = shopping_prompt([{"name": "z" * 500, "spec": "1"}] * 100)
    assert "z" * 121 not in text


# ------------------------------------------------------ Zeitumstellung (DST) ---
@pytest.mark.parametrize("plan_at, deadline, release", [
    # Sonntag 00:00 vor der Sommerzeit (28.03.2027): Termine danach mit +02:00 und gleicher Uhrzeit
    ("2027-03-28T00:00:00", "2027-03-29T12:00:00+02:00", "2027-03-29T18:00:00+02:00"),
    # Ende der Sommerzeit (31.10.2027)
    ("2027-10-31T00:00:00", "2027-11-01T12:00:00+01:00", "2027-11-01T18:00:00+01:00"),
])
def test_schedule_across_dst(plan_at, deadline, release):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from custom_components.meal_planner_ai.board import week_meta
    from custom_components.meal_planner_ai.planning import settings_from_options

    settings = settings_from_options({"plan_weekday": 6, "plan_time": "00:00", "deadline_weekday": 0,
                                      "deadline_time": "12:00"})
    meta = week_meta(datetime.fromisoformat(plan_at).replace(tzinfo=ZoneInfo("Europe/Berlin")), settings)
    assert meta["deadline"] == deadline and meta["release_at"]["trip2"] == release


# --------------------------------------------- Umstieg: laufende Woche übernehmen ---
async def test_import_week_current_and_clear_next(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-09 12:00:00+01:00")  # Montag, Auswahl der KW 46 ist abgeschlossen
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    planner.boards["next"] = {"id": "x", "dishes": []}
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        res = await call(hass, "import_week", {"dishes": [
            {"title": "Linsencurry", "url": URL2, "choice": "Shopping 2"},
            {"title": "Gemüsecurry (eigenes Rezept)", "own_recipe": True, "choice": "trip1", "meatless": True},
            {"title": "Schon da", "choice": "shopping  1", "ingredients_ready": True},
        ]})
    cur = planner.boards["current"]
    assert res["kw"] == 46 and cur["start"] == "2026-11-07" and res["added"] == []
    assert [d["choice"] for d in cur["dishes"]] == ["trip2", "trip1", "trip1"]
    assert cur["released"] == {"trip1": True, "trip2": False}
    assert cur["dishes"][0]["recipe_id"] and cur["dishes"][1]["own_recipe"]
    await call(hass, "import_week", {"dishes": [], "board": "next"})
    assert planner.boards["next"] is None
    # Montag 18 Uhr: Mi–Fr kommt auf die Liste
    freezer.move_to("2026-11-09 18:00:05+01:00")
    done = await planner.async_tick(dt_util.now())
    assert "release" in done and cur["dishes"][0]["on_list"] is True


# ------------------------------------- Einkauf mit Termin = Auswahlschluss, „jetzt einkaufen“ ---
async def test_trip_released_at_deadline_and_shop_now(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    trips = [{"key": "trip1", "name": "Sa–Di", "release": "timed", "weekday": 5, "time": "12:00", "days": []},
             {"key": "trip2", "name": "Mi–Fr", "release": "timed", "weekday": 0, "time": "18:00", "days": []}]
    hass.config_entries.async_update_entry(entry, options={**entry.options, "trips": trips})
    await hass.async_block_till_done()
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2}]})
        dish = planner.boards["next"]["dishes"][0]
        await call(hass, "choose_dish", {"dish_id": dish["id"], "choice": "trip1"})
        assert dish["on_list"] is False  # wartet auf Samstag 12 Uhr
        freezer.move_to("2026-11-14 12:00:05+01:00")
        done = await planner.async_tick(dt_util.now())
    assert "finalize" in done and "release" in done
    assert planner.boards["current"]["dishes"][0]["on_list"] is True


async def test_shop_now_releases_early(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    trips = [{"key": "trip1", "name": "Sa–Di", "release": "timed", "weekday": 5, "time": "12:00", "days": []}]
    hass.config_entries.async_update_entry(entry, options={**entry.options, "trips": trips})
    await hass.async_block_till_done()
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2}]})
        dish = planner.boards["next"]["dishes"][0]
        await call(hass, "choose_dish", {"dish_id": dish["id"], "choice": "trip1"})
        assert dish["on_list"] is False
        await call(hass, "release_shopping", {"trip": "trip1"})
    assert dish["on_list"] is True


# ------------------------------------------------- neu planen und tauschen ---
def _ai_setup(hass, entry):
    hass.states.async_set("ai_task.claude", "unknown")
    hass.config_entries.async_update_entry(entry, options={**entry.options, "ai_task": "ai_task.claude",
                                                           "recipes_per_week": 2})


async def test_more_adds_and_keeps_everything(hass: HomeAssistant, freezer):
    from .test_integration import URL1
    from .test_workflow import URL3

    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    _ai_setup(hass, entry)
    await hass.async_block_till_done()
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2},
                                                         {"title": "Gemüsepfanne", "url": URL3}], "final": True})
        dish = next(d for d in planner.boards["next"]["dishes"] if d["title"] == "Gemüsepfanne")
        await call(hass, "choose_dish", {"dish_id": dish["id"], "choice": "declined"})

        async def ai(prompt):
            return {"dishes": [{"title": "Linsencurry", "url": URL2}, {"title": "Nudeln mit Spinat", "url": URL1}]}

        with patch.object(planner, "_ask_proposals", side_effect=ai):
            res = await call(hass, "more_proposals", {"count": 1})
    dishes = planner.boards["next"]["dishes"]
    assert [d["nr"] for d in dishes] == [1, 2, 3], res
    assert dishes[2]["title"].startswith("Nudeln") and dishes[1]["choice"] == "declined"


async def test_more_in_running_week_waits_for_pick(hass: HomeAssistant, freezer):
    from .test_integration import URL1

    freezer.move_to("2026-11-09 12:00:00+01:00")
    entry = await _external(hass)
    _ai_setup(hass, entry)
    await hass.async_block_till_done()
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "import_week", {"dishes": [{"title": "Linsencurry", "url": URL2, "choice": "trip1"}]})
        # wie live: ein Einkauf ist schon freigegeben und fehlt in release_at
        planner.boards["current"]["release_at"].pop("trip1", None)
        planner.boards["current"]["released"]["trip1"] = True

        async def ai(prompt):
            assert "trip1" in prompt
            return {"dishes": [{"title": "Nudeln mit Spinat", "url": URL1}]}

        with patch.object(planner, "_ask_proposals", side_effect=ai):
            res = await call(hass, "more_proposals", {"count": 1})
        cand = planner.boards["current"]["dishes"][1]
        assert res["board"] == "current" and cand["choice"] == "none" and not cand["on_list"]
        await call(hass, "choose_dish", {"dish_id": cand["id"], "choice": "trip1"})
    assert cand["on_list"] is True


async def test_more_ignores_week_quotas(hass: HomeAssistant, freezer):
    """Zusatzvorschläge sind Alternativen: Schnell-Anteil und Co. dürfen sie nicht aussortieren."""
    from .test_integration import URL1

    freezer.move_to("2026-11-09 12:00:00+01:00")
    entry = await _external(hass)
    _ai_setup(hass, entry)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "quick_share": 2, "time_quick": 1})
    await hass.async_block_till_done()
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "import_week", {"dishes": [{"title": "Linsencurry", "url": URL2, "choice": "trip1"}]})

        async def ai(prompt):
            return {"dishes": [{"title": "Nudeln mit Spinat", "url": URL1}]}

        with patch.object(planner, "_ask_proposals", side_effect=ai):
            res = await call(hass, "more_proposals", {"count": 1})
    assert res["added"] == [planner.boards["current"]["dishes"][1]["title"]], res


async def test_swap_in_running_week_updates_list(hass: HomeAssistant, freezer):
    from .test_integration import URL1

    freezer.move_to("2026-11-09 12:00:00+01:00")
    entry = await _external(hass)
    _ai_setup(hass, entry)
    await hass.async_block_till_done()
    planner = entry.runtime_data.planner
    with patch(f"{SVC}.fetch_html", side_effect=fake_fetch2):
        await call(hass, "import_week", {"dishes": [{"title": "Linsencurry", "url": URL2, "choice": "trip1"}]})
        old = planner.boards["current"]["dishes"][0]
        assert old["on_list"] is True

        async def ai(prompt):
            return {"dishes": [{"title": "Nudeln mit Spinat", "url": URL1}]}

        with patch.object(planner, "_ask_proposals", side_effect=ai):
            res = await call(hass, "swap_dish", {"dish_id": old["id"]})
    new = planner.boards["current"]["dishes"][0]
    assert res["replaced"] == "Linsencurry" and new["title"].startswith("Nudeln") and new["choice"] == "trip1"
    assert new["on_list"] is True
    items = await hass.services.async_call("todo", "get_items", {"entity_id": "todo.meal_planner_shopping_list"},
                                           blocking=True, return_response=True)
    descs = " ".join(i.get("description") or "" for i in items["todo.meal_planner_shopping_list"]["items"])
    assert "Linsencurry" not in descs and "Nudeln" in descs
