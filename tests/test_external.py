"""Externe KI (z. B. geplante Aufgabe in Claude): Auftrag holen, Vorschläge einreichen, Ersatz im Zeitplan."""
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_fire_time_changed
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .test_integration import call, setup_entry
from .test_workflow import URL1, URL2, URL3, URL4, fake_fetch2


async def _external(hass):
    await hass.config.async_set_time_zone("Europe/Berlin")
    entry = await setup_entry(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "proposals_from": "external"})
    await hass.async_block_till_done()
    return hass.config_entries.async_get_entry(entry.entry_id)


def _notes(hass):
    sent = []

    async def notify(call):
        sent.append(call.data)

    hass.services.async_register("notify", "handy", notify)
    return sent


async def test_brief_and_submit(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")  # Freitag nach dem Planungszeitpunkt
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    assert planner.settings["proposals_from"] == "external"
    total = planner.settings["recipes_per_week"]

    brief = await call(hass, "planning_brief")
    assert brief["due"] is True and brief["need"] == total and brief["planned"] == 0
    assert "Leitplanken" in brief["prompt"] and "submit_proposals" in brief["how_to_submit"]

    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch2):
        res = await call(hass, "submit_proposals", {"dishes": [
            {"title": "Nudeln mit Spinat-Hackfleisch-Soße", "url": URL1, "tip": "trip1"},
            {"title": "Linsencurry", "url": URL2, "tip": "trip1"},
            {"title": "Schmorbraten", "url": URL4},  # zu lang
            {"title": "Linsencurry", "url": URL2},   # doppelt
            "kein Gericht",
        ]})
        assert res["accepted"] == ["Nudeln mit Spinat-Hackfleisch-Soße", "Linsencurry"]
        assert res["need"] == total - 2 and not res["complete"] and res["rejected"]
        assert "Fehlen" in res["next_step"] or "fehlen" in res["next_step"]
        board = planner.boards["next"]
        assert board["source"] == "external" and len(board["dishes"]) == 2 and not board["notified"]

        # zweiter Aufruf baut auf der Tafel auf; der Auftrag kennt jetzt die geplanten Gerichte
        brief = await call(hass, "planning_brief")
        assert brief["planned"] == 2 and "Linsencurry" in brief["prompt"]
        res = await call(hass, "submit_proposals", {"dishes": [
            {"title": "Gemüsepfanne", "url": URL3, "tip": "trip1"},
            {"title": "Linsencurry", "url": URL2}], "final": True})
        assert res["accepted"] == ["Gemüsepfanne"] and res["count"] == 3
        assert planner.boards["next"]["notified"] is True
        brief = await call(hass, "planning_brief")  # fertig: nichts mehr zu tun
        assert brief["due"] is False and "fertig" in brief["reason"]

        # neu beginnen ersetzt die Tafel
        res = await call(hass, "submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2}],
                                                     "restart": True})
        assert res["dishes"] == ["Linsencurry"]


async def test_external_mode_waits_then_reports(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-11 10:00:00+01:00")
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    planner.settings  # noqa: B018
    with patch.object(planner, "async_generate") as gen:
        freezer.move_to("2026-11-13 18:00:05+01:00")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert await planner.async_tick(dt_util.now()) == []
        gen.assert_not_called()  # wartet auf die externe KI
        freezer.move_to("2026-11-13 20:30:00+01:00")
        await planner.async_tick(dt_util.now())
        assert planner._missed is None  # wartet noch (5 Stunden)
        freezer.move_to("2026-11-13 23:00:20+01:00")
        done = await planner.async_tick(dt_util.now())
        gen.assert_not_called()  # keine KI in HA gewählt: nur Meldung, kein eigener Lauf
        assert planner._missed
        assert done == []


async def test_not_due_before_planning_time(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-12 10:00:00+01:00")  # Donnerstag, vor dem Planungszeitpunkt
    await _external(hass)
    brief = await call(hass, "planning_brief")
    assert brief["due"] is False and brief["next_planning"].startswith("2026-11-13T18:00")
    assert "prompt" not in brief


async def test_partial_external_board_is_finished_by_fallback(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch2):
        await call(hass, "submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2}]})
    assert not planner.boards["next"]["notified"]
    freezer.move_to("2026-11-13 23:00:20+01:00")
    assert await planner.async_tick(dt_util.now()) == ["external_final"]
    assert planner.boards["next"]["notified"] is True


async def test_memory_overview_and_edits(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-13 18:30:00+01:00")
    await _external(hass)
    await call(hass, "update_history", {"title": "Linsencurry", "url": URL2, "rating": 5, "note": "super",
                                        "cooked_on": "2026-11-10"}, response=False)
    await call(hass, "update_history", {"title": "Leber", "rating": 1}, response=False)
    mem = await call(hass, "memory_overview")
    assert [r["title"] for r in mem["liked"]] == ["Linsencurry"] and [r["title"] for r in mem["disliked"]] == ["Leber"]
    assert mem["recent"][0]["last"] == "2026-11-10" and len(mem["recipes"]) == 2
    rid = mem["liked"][0]["id"]
    await call(hass, "update_history", {"recipe_id": rid, "rating": 0, "remove_cooked_on": "2026-11-10",
                                        "note": ""}, response=False)
    mem = await call(hass, "memory_overview")
    assert not mem["liked"] and not mem["recent"]
    rec = next(r for r in mem["recipes"] if r["id"] == rid)
    assert rec["rating"] is None and rec["times"] == 0 and rec["note"] is None and rec["status"] == "new"
    await call(hass, "set_profile", {"text": "Keine Pilze"}, response=False)
    await hass.async_block_till_done()
    assert (await call(hass, "memory_overview"))["profile_text"] == "Keine Pilze"


async def test_llm_tools_and_setup_info(hass: HomeAssistant, freezer):
    from homeassistant.helpers import llm

    freezer.move_to("2026-11-13 18:30:00+01:00")
    await _external(hass)
    apis = {a.id: a for a in llm.async_get_apis(hass)}
    assert "meal_planner_ai" in apis
    ctx = llm.LLMContext(platform="mcp_server", context=None, language="de", assistant=None, device_id=None)
    inst = await llm.async_get_api(hass, "meal_planner_ai", ctx)
    assert {t.name for t in inst.tools} == {"meal_planner_setup", "meal_planner_planning_brief",
                                            "meal_planner_submit_proposals"}
    # Schemas müssen sich für MCP/OpenAPI umwandeln lassen
    from voluptuous_openapi import convert
    for tool in inst.tools:
        convert(tool.parameters)
    tools = {t.name: t for t in inst.tools}
    brief = await tools["meal_planner_planning_brief"].async_call(
        hass, llm.ToolInput("meal_planner_planning_brief", {}), ctx)
    assert brief["due"] is True and brief["need"] == 10
    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch2):
        res = await tools["meal_planner_submit_proposals"].async_call(
            hass, llm.ToolInput("meal_planner_submit_proposals", {"dishes": [{"title": "Linsencurry", "url": URL2}]}), ctx)
    assert res["accepted"] == ["Linsencurry"]

    info = await call(hass, "external_setup")
    assert info["enabled"] is True and info["language"] == "de"
    assert info["schedule"] == "Freitag um 18:05, 20:05, 22:05"
    assert info["cron"] == "CRON_TZ=Europe/Berlin 5 18,20,22 * * 5"
    assert "Freitag 23:00" in info["fallback"] and "planning_brief" in info["task_text"]
    assert len(info["steps"]) == 6 and "Freitag um 18:05" in info["chat_message"] and info["task_text"] in info["chat_message"]


async def test_brief_before_planning_day_uses_coming_week(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-09 08:00:00+01:00")  # Montag
    entry = await _external(hass)
    brief = await call(hass, "planning_brief", {"restart": True})
    assert brief["due"] is True and "Hand" in brief["reason"] and brief["deadline"].startswith("2026-11-14T12:00")
    meta = entry.runtime_data.planner._plan_meta()
    # Freigaben gehören zur kommenden Woche (nach dem Planungszeitpunkt Fr 13.11.), nicht zu dieser
    assert all(at > "2026-11-14" for at in meta["release_at"].values()), meta["release_at"]



async def test_setup_activate_via_ai(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-09 08:00:00+01:00")
    await hass.config.async_set_time_zone("Europe/Berlin")
    entry = await setup_entry(hass)
    info = await call(hass, "external_setup")
    assert info["enabled"] is False and "activate: true" in info["instructions_for_ai"]
    assert info["phrase"] in info["steps"][2] and len(info["steps"]) == 6
    info = await call(hass, "external_setup", {"activate": True})
    await hass.async_block_till_done()
    assert info["enabled"] is True and "bereits" in info["instructions_for_ai"]
    assert hass.config_entries.async_get_entry(entry.entry_id).options["proposals_from"] == "external"



async def test_schedule_change_is_flagged(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-09 08:00:00+01:00")
    entry = await _external(hass)
    info = await call(hass, "external_setup", {"view": True})
    assert info["registered_schedule"] is None and info["schedule_changed"] is False
    await call(hass, "external_setup")  # KI richtet sich ein
    hass.config_entries.async_update_entry(entry, options={**entry.options, "plan_time": "17:00"})
    await hass.async_block_till_done()
    info = await call(hass, "external_setup", {"view": True})
    assert info["schedule_changed"] is True and "18:05" in info["registered_schedule"] and "17:05" in info["schedule"]
    await call(hass, "external_setup")  # KI noch einmal gefragt
    assert (await call(hass, "external_setup", {"view": True}))["schedule_changed"] is False


async def test_slot_conflict_rejects_early(hass: HomeAssistant, freezer):
    from custom_components.meal_planner_ai.board import new_dish

    freezer.move_to("2026-11-13 18:30:00+01:00")
    entry = await _external(hass)
    planner = entry.runtime_data.planner
    s = planner.settings
    total = s["recipes_per_week"]

    def dish(title, minutes=20, meatless=False, wish=None):
        return new_dish(title=title, time_min=minutes, meatless=meatless, wish=wish)

    plan = [dish("Hähnchen-Curry"), dish("Putengeschnetzeltes"), dish("Hähnchen-Pfanne")]
    why = planner._slot_conflict(dish("Honig-Hähnchen"), plan, total)
    assert why and "Hähnchen/Pute" in why
    assert planner._slot_conflict(dish("Hähnchen-Lasagne", wish="Lasagne"), plan, total) is None  # Wunsch
    assert planner._slot_conflict(dish("Linsencurry", meatless=True), plan, total) is None
    # schnelle Gerichte: bleiben nur noch so viele Plätze wie schnelle Gerichte fehlen, keine langsamen mehr
    quick = s["quick_share"]
    slow_plan = [dish(f"Schmorgericht {i}", minutes=90, meatless=i < 2) for i in range(total - quick)]
    assert "fehlen noch" in planner._slot_conflict(dish("Braten", minutes=120), slow_plan, total)
    assert planner._slot_conflict(dish("Nudeln", minutes=20), slow_plan, total) is None
