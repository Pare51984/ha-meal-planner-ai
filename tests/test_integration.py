import json
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DOMAIN = "meal_planner_ai"
URL1 = "https://www.chefkoch.de/rezepte/3199691476184958/Nudeln-mit-Spinat-Hackfleisch-Sosse.html"
URL2 = "https://www.chefkoch.de/rezepte/2/Linsencurry.html"


def page(name, ingredients, kcal, url, instr="Im Topf kochen.", minutes=35):
    ld = {"@context": "http://schema.org", "@type": "Recipe", "name": name,
          "author": {"@type": "Person", "name": "test"}, "recipeYield": "4 Portionen",
          "totalTime": f"PT{minutes}M", "nutrition": {"@type": "NutritionInformation", "calories": f"{kcal} kcal"},
          "recipeIngredient": ingredients, "recipeInstructions": instr, "url": url}
    return f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head></html>'


PAGES = {
    URL1: page("Nudeln mit Spinat-Hackfleisch-Soße",
               ["500 g Nudeln", "400 g Hackfleisch", "450 g Blattspinat, TK", "1 Zwiebel(n)", "Salz und Pfeffer"],
               712, URL1),
    URL2: page("Linsencurry", ["200 g rote Linsen", "400 ml Kokosmilch", "1 Zwiebel"], 450, URL2),
}


async def fake_fetch(hass, url):
    return PAGES[url], url


async def setup_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"region": "de", "shopping_list": "own"})
    assert result["step_id"] == "devices"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"devices": ["stove_oven", "thermomix"], "custom_devices": "Slow Cooker"})
    assert result["step_id"] == "ai"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ai_task": "none"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"display": "none"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0]


async def call(hass, service, data=None, response=True):
    return await hass.services.async_call(DOMAIN, service, data or {}, blocking=True, return_response=response)


async def test_full_flow(hass: HomeAssistant):
    entry = await setup_entry(hass)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert hass.states.get("todo.meal_planner_shopping_list") is not None

    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch):
        rec = await call(hass, "import_recipe", {"url": URL1})
        assert rec["title"].startswith("Nudeln") and rec["kcal_per_serving"] == 712
        assert rec["checks"]["diet"]["vegetarian"] is False
        assert rec["checks"]["source_enabled"] is True
        rid = rec["id"]
        again = await call(hass, "import_recipe", {"url": URL1})
        assert again["id"] == rid

        lst = await call(hass, "list_recipes")
        assert lst["count"] == 1

        shop = await call(hass, "add_to_shopping_list", {"recipe_id": rid, "servings": 2})
        assert shop["count"] == 4, shop
        assert "Nudeln (250 g)" in shop["added"]
        assert shop["skipped_staples"] == ["Salz und Pfeffer"]
        items = await hass.services.async_call("todo", "get_items", {"entity_id": "todo.meal_planner_shopping_list"},
                                               blocking=True, return_response=True)
        got = items["todo.meal_planner_shopping_list"]["items"]
        T = "Nudeln mit Spinat-Hackfleisch-Soße"
        assert {i["summary"]: i.get("description") for i in got} == {
            "Nudeln": f"250 g ({T})", "Hackfleisch": f"200 g ({T})",
            "Spinat": f"225 g, TK ({T})", "Zwiebeln": f"1 ({T})"}

        skip = await call(hass, "add_to_shopping_list", {"recipe_id": rid})
        assert skip["skipped_reason"] == "already_bought"

        forced = await call(hass, "add_to_shopping_list", {"recipe_id": rid, "force": True})
        assert forced["added"] == [] and len(forced["merged"]) == 4, forced  # kein Doppel

        hist = await call(hass, "update_history", {"recipe_id": rid, "rating": 4, "cooked_on": "2026-11-01"})
        assert hist["history"]["status"] == "cooked" and hist["history"]["rating"] == 4

        imp = await call(hass, "import_history", {"entries": [
            {"title": "Gnocchi-Pfanne", "rating": 5, "cooked_on": ["2026-10-01"]},
            {"title": "Linsencurry", "url": URL2, "rating": 3}], "fetch_recipes": True})
        assert imp == {"created": 2, "updated": 0, "fetch_errors": []}

        lst = await call(hass, "list_recipes", {"min_rating": 4})
        assert {r["title"] for r in lst["recipes"]} == {"Nudeln mit Spinat-Hackfleisch-Soße", "Gnocchi-Pfanne"}

        # Ernährung einstellen: 2 Rezepte/Woche, 1 vegetarisch, 1 vegan -> keine Überschneidung nötig (vegan zählt als veg.)
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        assert flow["type"] is FlowResultType.MENU
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"next_step_id": "diet_count"})
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"recipes_per_week": 2})
        assert flow["step_id"] == "diet"
        data = {f"{k}_mode": "off" for k in ["vegetarian", "vegan", "lactose_free", "gluten_free", "low_cholesterol"]}
        data.update({"vegetarian_mode": "count", "vegetarian_count": 1, "vegan_mode": "count", "vegan_count": 1,
                     "gluten_free_mode": "count", "gluten_free_count": 2})
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], data)
        assert flow["step_id"] == "diet_overlap", flow
        assert flow["description_placeholders"]["overlap"] == "1"
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {})
        assert flow["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

        settings = await call(hass, "get_settings")
        assert settings["planner"]["recipes_per_week"] == 2
        assert "rezeptwelt.de" in settings["planner"]["enabled_sources"]

        plan = await call(hass, "validate_plan", {"urls": [URL1, URL2]})
        assert plan["counts"]["vegan"] == 1 and plan["counts"]["vegetarian"] == 1
        assert any("gluten_free" in v for v in plan["violations"]), plan
        assert plan["ok"] is False

        # Thermomix abwählen -> Thermomix-Seiten aus
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"next_step_id": "devices"})
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"devices": ["stove_oven"], "custom_devices": "Slow Cooker"})
        assert flow["step_id"] == "device_counts"
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"Slow Cooker": 1})
        assert flow["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        settings = await call(hass, "get_settings")
        assert "rezeptwelt.de" not in settings["planner"]["enabled_sources"]
        assert settings["planner"]["device_counts_per_week"] == {"Slow Cooker": 1}

        # Quellen: chefkoch aus, eigene Seite per Testlink hinzufügen
        PAGES["https://meinblog.example.org/r/1"] = page("Blog-Suppe", ["1 l Wasser", "2 Karotten"], 100,
                                                         "https://meinblog.example.org/r/1")
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {"next_step_id": "sources"})
        assert "site_rezeptwelt_de" not in [str(k) for k in flow["data_schema"].schema]
        flow = await hass.config_entries.options.async_configure(flow["flow_id"], {
            "site_chefkoch_de": False, "new_source_url": "https://meinblog.example.org/r/1"})
        assert flow["type"] is FlowResultType.CREATE_ENTRY, flow
        await hass.async_block_till_done()
        settings = await call(hass, "get_settings")
        assert "chefkoch.de" not in settings["planner"]["enabled_sources"]
        assert "meinblog.example.org" in settings["planner"]["enabled_sources"]  # codeql[py/incomplete-url-substring-sanitization] Listenprüfung, keine URL-Prüfung

        # Daten überleben Reload
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        lst = await call(hass, "list_recipes")
        assert lst["count"] == 3
        assert hass.states.get("todo.meal_planner_shopping_list") is not None

        await call(hass, "delete_recipe", {"recipe_id": rid}, response=False)
        assert (await call(hass, "list_recipes"))["count"] == 2


async def test_single_instance(hass: HomeAssistant):
    await setup_entry(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
