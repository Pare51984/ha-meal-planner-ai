from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DOMAIN = "meal_planner_ai"


async def _setup(hass, display, dashboard="lovelace"):
    assert await async_setup_component(hass, "lovelace", {})
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"region": "de", "shopping_list": "own"})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"devices": ["stove_oven"]})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"ai_task": "none"})
    assert r["step_id"] == "display"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"display": display, "display_dashboard": dashboard, "display_style": "warm"})
    assert r["type"] == "create_entry"
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0]


async def test_panel_and_resource(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-11 10:00:00+01:00")
    entry = await _setup(hass, "panel")
    assert hass.data["frontend_panels"]["meal-planner"].config["preset"] == "warm"
    from homeassistant.components.lovelace.const import LOVELACE_DATA
    urls = [i["url"] for i in hass.data[LOVELACE_DATA].resources.async_items()]
    assert any(u.startswith("/meal_planner_ai/meal-planner-card.js?v=") for u in urls), urls
    await hass.config_entries.async_unload(entry.entry_id)
    assert "meal-planner" not in hass.data["frontend_panels"]


async def test_view_in_dashboard(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-11 10:00:00+01:00")
    from homeassistant.components.lovelace.const import LOVELACE_DATA
    assert await async_setup_component(hass, "lovelace", {})
    board = hass.data[LOVELACE_DATA].dashboards[None]
    await board.async_save({"views": [{"title": "Übersicht", "cards": []}]})
    entry = await _setup(hass, "view")
    config = await board.async_load(False)
    assert [v.get("path") for v in config["views"]] == [None, "meal-planner"]
    assert config["views"][1]["cards"] == [{"type": "custom:meal-planner-card", "preset": "warm"}]
    # Einstellung wird bei jedem Laden hergestellt: gelöschte Ansicht kommt zurück (abschalten über „keine“)
    config["views"].pop()
    await board.async_save(config)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len((await board.async_load(False))["views"]) == 2


async def _options(hass, entry, **values):
    hass.config_entries.async_update_entry(entry, options={**entry.options, **values})
    await hass.async_block_till_done()


async def test_switching_display_modes(hass: HomeAssistant, freezer):
    freezer.move_to("2026-11-11 10:00:00+01:00")
    from homeassistant.components.lovelace.const import LOVELACE_DATA
    assert await async_setup_component(hass, "lovelace", {})
    board = hass.data[LOVELACE_DATA].dashboards[None]
    mine = {"title": "Meins", "cards": [{"type": "custom:meal-planner-card"}, {"type": "markdown", "content": "x"}]}
    await board.async_save({"views": [{"title": "Übersicht", "cards": []}, mine]})
    entry = await _setup(hass, "view")
    paths = lambda c: [v.get("path") for v in c["views"]]  # noqa: E731
    assert paths(await board.async_load(False)) == [None, None, "meal-planner"]

    await _options(hass, entry, display_style="system")  # Farben ändern wirkt auf die Ansicht
    assert (await board.async_load(False))["views"][2]["cards"] == [{"type": "custom:meal-planner-card"}]

    await _options(hass, entry, display="panel")  # Ansicht weg, eigene Seite da
    config = await board.async_load(False)
    assert paths(config) == [None, None] and config["views"][1] == mine  # eigene Ansicht bleibt unberührt
    assert "meal-planner" in hass.data["frontend_panels"]

    await _options(hass, entry, display_style="warm")  # Farben der eigenen Seite
    assert hass.data["frontend_panels"]["meal-planner"].config["preset"] == "warm"

    await _options(hass, entry, display="none")
    assert "meal-planner" not in hass.data["frontend_panels"]
    assert paths(await board.async_load(False)) == [None, None]

    await _options(hass, entry, display="view")
    assert paths(await board.async_load(False)) == [None, None, "meal-planner"]
    await hass.config_entries.async_remove(entry.entry_id)  # Integration löschen räumt die Ansicht weg
    await hass.async_block_till_done()
    assert paths(await board.async_load(False)) == [None, None]


async def test_legacy_view_is_adopted(hass: HomeAssistant, freezer):
    """Ansicht der früheren Version („essensplaner“) wird übernommen, nicht verdoppelt."""
    freezer.move_to("2026-11-11 10:00:00+01:00")
    from homeassistant.components.lovelace.const import LOVELACE_DATA
    from homeassistant.helpers.storage import Store
    assert await async_setup_component(hass, "lovelace", {})
    board = hass.data[LOVELACE_DATA].dashboards[None]
    await board.async_save({"views": [{"title": "Essen", "path": "essensplaner", "type": "panel",
                                       "cards": [{"type": "custom:meal-planner-card", "preset": "warm"}]}]})
    await Store(hass, 1, "meal_planner_ai.recipes").async_save({"recipes": {}, "meta": {"views_added": ["lovelace"]}})
    await _setup(hass, "view")
    config = await board.async_load(False)
    assert [v.get("path") for v in config["views"]] == ["essensplaner"]
