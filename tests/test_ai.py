import re
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.data_entry_flow import FlowResultType

from .test_integration import URL2, call, fake_fetch

DOMAIN = "meal_planner_ai"
CALLS = []


async def fake_ai(call):
    CALLS.append(call.data["task_name"])
    text = call.data["instructions"]
    if call.data["task_name"] == "Essensplaner Ernährung prüfen":
        ids = re.findall(r'"id": "([0-9a-z]+)"', text)
        return {"conversation_id": "x", "data": {"results": [
            {"id": i, "low_cholesterol": True, "low_calorie": True, "note": "ok"} for i in ids]}}
    if call.data["task_name"] == "Essensplaner Einkaufsliste":
        assert "rote linsen -> Linsen" in text
        return {"conversation_id": "x", "data": '```json\n{"items": [{"name": "Linsen", "spec": "150 g, rot"},'
                ' {"name": "Kokosmilch", "spec": "300 ml"}, {"name": "Zwiebeln", "spec": "1"}]}\n```'}
    raise AssertionError(call.data["task_name"])


async def test_ai_shopping_and_assess(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-11 10:00:00+01:00")  # Mittwoch: kein Planungsfenster
    hass.states.async_set("ai_task.claude", "unknown", {"friendly_name": "Claude AI Task"})
    hass.services.async_register("ai_task", "generate_data", fake_ai, supports_response=SupportsResponse.ONLY)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"region": "de", "shopping_list": "own"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"devices": ["stove_oven"]})
    opts = [o["value"] for o in result["data_schema"].schema["ai_task"].config["options"]]
    assert opts == ["none", "ai_task.claude"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ai_task": "ai_task.claude"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"display": "none"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch):
        rec = await call(hass, "import_recipe", {"url": URL2})
        shop = await call(hass, "add_to_shopping_list", {"recipe_id": rec["id"]})
        assert shop["added"] == ["Linsen (150 g, rot)", "Kokosmilch (300 ml)", "Zwiebeln (1)"], shop
        n = CALLS.count("Essensplaner Einkaufsliste")
        await call(hass, "add_to_shopping_list", {"recipe_id": rec["id"], "force": True})
        assert CALLS.count("Essensplaner Einkaufsliste") == n  # aus dem Zwischenspeicher
        items = await hass.services.async_call("todo", "get_items", {"entity_id": "todo.meal_planner_shopping_list"},
                                               blocking=True, return_response=True)
        got = {i["summary"]: i.get("description") for i in items["todo.meal_planner_shopping_list"]["items"]}
        assert got["Linsen"] == "150 g, rot (Linsencurry)"  # zweites Mal nicht doppelt

        res = await call(hass, "assess_recipes", {"force": True})
        assert res["assessed"] == 1
        rec = await call(hass, "get_recipe", {"recipe_id": rec["id"]})
        assert rec["checks"]["diet_source"]["low_cholesterol"] == "ai"


async def test_ai_parse_json():
    from custom_components.meal_planner_ai.ai import parse_json
    assert parse_json('Hier: {"a": 1} fertig') == {"a": 1}
    assert parse_json('```json\n[1, 2]\n```') == [1, 2]


async def test_conversation_agent_with_search(hass: HomeAssistant):
    """Gesprächsagent (z. B. Gemini mit Google-Suche) statt AI Task: Antworttext enthält das JSON."""
    from custom_components.meal_planner_ai.ai import AIError, async_ask

    calls = []

    async def fake_process(call):
        calls.append(dict(call.data))
        if "kaputt" in call.data["text"]:
            return {"response": {"response_type": "error", "data": {"code": "unknown"}}}
        return {"response": {"response_type": "action_done", "speech": {"plain": {
            "speech": 'Hier: ```json\n{"dishes": [{"title": "Linsencurry", "url": "https://www.chefkoch.de/rezepte/2/x.html"}]}\n```'}}}}

    hass.services.async_register("conversation", "process", fake_process, supports_response=SupportsResponse.ONLY)
    hass.states.async_set("conversation.google_rezeptsuche", "unknown")
    res = await async_ask(hass, "conversation.google_rezeptsuche", "Test", "Rezepte bitte")
    assert res["dishes"][0]["title"] == "Linsencurry"
    assert calls[0]["agent_id"] == "conversation.google_rezeptsuche"
    try:
        await async_ask(hass, "conversation.google_rezeptsuche", "Test", "kaputt")
        raise AssertionError("Fehler erwartet")
    except AIError:
        pass


async def test_search_agent_falls_back_to_ai_task(hass: HomeAssistant):
    """Such-Agent meldet Fehler (z. B. 429) -> Vorschläge kommen von der AI-Task-KI."""
    from .test_integration import setup_entry

    async def broken(call):
        return {"response": {"response_type": "error", "data": {"code": "unknown"}}}

    async def task(call):
        return {"conversation_id": "x", "data": {"dishes": []}}

    hass.services.async_register("conversation", "process", broken, supports_response=SupportsResponse.ONLY)
    hass.services.async_register("ai_task", "generate_data", task, supports_response=SupportsResponse.ONLY)
    hass.states.async_set("conversation.suche", "unknown")
    hass.states.async_set("ai_task.gemini", "unknown")
    entry = await setup_entry(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "ai_task": "ai_task.gemini",
                                                           "ai_search": "conversation.suche"})
    await hass.async_block_till_done()
    planner = hass.config_entries.async_entries("meal_planner_ai")[0].runtime_data.planner
    assert planner._search_ai() == "conversation.suche"
    with patch("custom_components.meal_planner_ai.board.RETRY_DELAY", 0):
        assert await planner._ask_proposals("x") == {"dishes": []}
