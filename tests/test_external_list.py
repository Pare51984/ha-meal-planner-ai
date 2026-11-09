from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .test_integration import PAGES, URL1, URL2, call, fake_fetch

DOMAIN = "meal_planner_ai"


async def test_external_list_and_rules(hass: HomeAssistant, tmp_path):
    import os
    os.makedirs(hass.config.path(".storage"), exist_ok=True)
    if True:
        local = MockConfigEntry(domain="local_todo", data={"todo_list_name": "Zuhause", "storage_key": "zuhause"})
        local.add_to_hass(hass)
        assert await hass.config_entries.async_setup(local.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get("todo.zuhause") is not None

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    values = [o["value"] for o in result["data_schema"].schema["shopping_list"].config["options"]]
    assert values == ["todo.zuhause", "own"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"shopping_list": "todo.zuhause"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"devices": ["stove_oven"]})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ai_task": "none"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"display": "none"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("todo.meal_planner_shopping_list") is None
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch):
        shop = await call(hass, "add_to_shopping_list", {"url": URL2})
        assert shop["list"] == "todo.zuhause" and shop["count"] == 3
        items = await hass.services.async_call("todo", "get_items", {"entity_id": "todo.zuhause"},
                                               blocking=True, return_response=True)
        assert {i["summary"] for i in items["todo.zuhause"]["items"]} == {"Linsen", "Kokosmilch", "Zwiebel"}

        # "immer vegetarisch" + 1 Rezept/Woche, Absenken kürzt Werte
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"next_step_id": "diet_count"})
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"recipes_per_week": 3})
        data = {f"{k}_mode": "off" for k in ["vegetarian", "vegan", "lactose_free", "gluten_free", "low_cholesterol"]}
        data.update({"vegetarian_mode": "always", "gluten_free_mode": "count", "gluten_free_count": 3})
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], data)
        assert flow["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"next_step_id": "diet_count"})
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"recipes_per_week": 1})
        assert "gluten_free: 3 → 1" in flow["description_placeholders"]["clamped"]
        await hass.config_entries.options.async_configure(flow["flow_id"], {**data, "gluten_free_count": 1})
        await hass.async_block_till_done()

        ok = await call(hass, "validate_plan", {"urls": [URL2]})
        assert ok["ok"] is True, ok
        bad = await call(hass, "validate_plan", {"urls": [URL1]})
        assert any("vegetarian gilt immer" in v for v in bad["violations"]), bad
