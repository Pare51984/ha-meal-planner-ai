"""Umstieg von der früheren Kennung „essensplaner“ auf „meal_planner_ai“."""
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .test_integration import call

DOMAIN = "meal_planner_ai"


async def test_takeover_from_essensplaner(hass: HomeAssistant):
    old_opts = {"region": "de", "shopping_list": "own", "devices": ["stove_oven"], "ai_task": "none",
                "display": "none", "recipes_per_week": 7, "profile": "Keine Pilze"}
    MockConfigEntry(domain="essensplaner", title="Essensplaner", data={}, options=old_opts).add_to_hass(hass)
    await Store(hass, 1, "essensplaner.recipes").async_save(
        {"recipes": {"abc": {"id": "abc", "title": "Linsencurry", "source_url": None, "ingredients": [],
                             "history": {"status": "cooked", "rating": 5, "cooked_on": ["2026-11-01"],
                                         "bought_on": None, "note": "super"}}}, "meta": {}})
    await Store(hass, 1, "essensplaner.wishes").async_save(
        {"items": [{"uid": "w1", "summary": "Lasagne", "status": "needs_action", "description": None}]})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "import_legacy"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"import_settings": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options["recipes_per_week"] == 7 and entry.title == "Meal Planner AI"

    mem = await call(hass, "memory_overview")
    assert mem["profile_text"] == "Keine Pilze" and mem["liked"][0]["title"] == "Linsencurry"
    assert hass.states.get("sensor.meal_planner_proposals") is not None
    resp = await hass.services.async_call("todo", "get_items", {"entity_id": "todo.meal_planner_wishes"},
                                          blocking=True, return_response=True)
    assert [i["summary"] for i in resp["todo.meal_planner_wishes"]["items"]] == ["Lasagne"]


async def test_fresh_setup_without_legacy(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["step_id"] == "user"
