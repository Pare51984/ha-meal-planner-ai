"""Einstellungen im Dashboard: die Karte nutzt die normale Options-API von HA (nur Admins)."""
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_integration import setup_entry


async def _run(client, entry_id, step, data):
    resp = await client.post("/api/config/config_entries/options/flow", json={"handler": entry_id})
    menu = await resp.json()
    assert menu["type"] == "menu" and step in menu["menu_options"]
    resp = await client.post(f"/api/config/config_entries/options/flow/{menu['flow_id']}", json={"next_step_id": step})
    form = await resp.json()
    assert form["type"] == "form", form
    resp = await client.post(f"/api/config/config_entries/options/flow/{menu['flow_id']}", json=data)
    assert resp.status == 200, await resp.text()
    return form, await resp.json()


async def test_settings_over_http(hass: HomeAssistant, hass_client, hass_ws_client):
    entry = await setup_entry(hass)
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()

    # So schickt die Karte die Werte: Zahlen als JSON-Zahl, Uhrzeit mit Sekunden, leere Texte als ""
    form, res = await _run(client, entry.entry_id, "schedule", {
        "plan_weekday": "thu", "plan_time": "17:30:00", "deadline_weekday": "sat", "deadline_time": "12:00:00",
        "notify": [], "dashboard_path": ""})
    assert res["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.options["plan_weekday"] == 3 and entry.options["plan_time"] == "17:30"

    form, res = await _run(client, entry.entry_id, "rules", {
        "portions": 4, "time_max": 60, "time_quick": 40, "quick_share": 8,
        "kcal_aware": False, "profile": "mag Pilze"})
    assert res["type"] == "create_entry", res
    await hass.async_block_till_done()
    assert int(entry.options["portions"]) == 4 and entry.options["profile"] == "mag Pilze"
    # kalorienbewusst aus = keine kcal-Grenzen
    settings = entry.runtime_data.planner.settings
    assert settings["kcal_max"] is None and settings["kcal_max_without_side"] is None
    assert settings["habits"] == ["Suppen/Eintöpfe höchstens 1x pro Woche"]  # Standard

    # mehrstufig: erst Anzahl Einkäufe ("Weiter"), dann Details
    form, res = await _run(client, entry.entry_id, "trips", {"count": "1"})
    assert form["last_step"] is False and res["type"] == "form" and res["step_id"] == "trip_details"

    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "config_entries/get", "domain": "meal_planner_ai"})
    msg = await ws.receive_json()
    assert msg["result"][0]["entry_id"] == entry.entry_id
    await ws.send_json({"id": 2, "type": "frontend/get_translations", "language": "de", "category": "options",
                        "integration": ["meal_planner_ai"]})
    res = (await ws.receive_json())["result"]["resources"]
    assert res["component.meal_planner_ai.options.step.init.menu_options.rules"]
    assert res["component.meal_planner_ai.options.step.rules.data.portions"]
