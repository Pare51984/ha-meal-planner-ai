"""Eigene Rezeptsuche: Links aus Suchseiten ziehen und tote KI-Links ersetzen."""
from datetime import date
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.meal_planner_ai.search import extract_links, search_url

from .test_integration import call, page, setup_entry

REAL = "https://www.chefkoch.de/rezepte/4242424242/Ofen-Gnocchi-mit-Kuerbis.html"
SEARCH_HTML = f"""<html><a href="/rs/s0/gnocchi/Rezepte.html">weiter</a>
<a href="https://www.chefkoch.de/rezepte/111/Tomatensuppe.html">Suppe</a>
<a href="https://www.chefkoch.de/rezepte/222/Saftiger-Kuerbis-Gnocchi-Auflauf.html">Auflauf</a>
<a href="{REAL}?utm=1">Ofen-Gnocchi</a><a href="https://www.chefkoch.de/rezepte/kategorie/abc">Kat</a>
<a href="https://fremd.de/rezepte/1/x.html">fremd</a></html>"""


def test_relevant():
    from custom_components.meal_planner_ai.search import relevant

    assert relevant("Kürbis Gnocchi", "Ofen-Gnocchi mit Kürbis und Salbei")
    assert not relevant("Kürbis Gnocchi", "Tomatensuppe")
    assert relevant("Linsen Curry vegan", "Rotes Linsencurry")  # 2 von 3 (Wortanfänge)
    assert not relevant("Rindergeschnetzeltes", "Klassisches Carpaccio mit Rinderfilet")
    assert relevant("Nudeln mit Hähnchen", "20-Minuten-Hähnchen-Mais-Nudelpfanne")
    assert relevant("Kürbis-Risotto", "Cremiges Kürbisrisotto")


def test_extract_links():
    links = extract_links(SEARCH_HTML, "https://www.chefkoch.de/rs/s0/x/Rezepte.html", "chefkoch.de", "Kürbis Gnocchi")
    assert REAL in links[:2]  # passende Treffer zuerst, Parameter entfernt
    assert "https://www.chefkoch.de/rezepte/111/Tomatensuppe.html" not in links  # passt nicht zur Suche
    assert all("fremd.de" not in l and "kategorie" not in l for l in links)
    assert "https://www.chefkoch.de/rezepte/222/Saftiger-Kuerbis-Gnocchi-Auflauf.html" in links  # "kuerbis" = "Kürbis"
    fonts = '<a href="https://hellofresh.de/assets/fonts/x/kuerbis-gnocchi.woff2">f</a>'
    assert extract_links(fonts, "https://hellofresh.de/?s=x", "hellofresh.de", "Kürbis Gnocchi") == []
    wp = '<a href="https://blog.de/kuerbis-gnocchi-aus-dem-ofen/">x</a><a href="https://blog.de/tag/kuerbis/">t</a>'
    assert extract_links(wp, "https://blog.de/?s=x", "blog.de", "Kürbis Gnocchi") == ["https://blog.de/kuerbis-gnocchi-aus-dem-ofen/"]
    assert search_url("chefkoch.de", "Kürbis Gnocchi", "de-DE") == "https://www.chefkoch.de/rs/s0/K%C3%BCrbis%20Gnocchi/Rezepte.html"
    assert search_url("blog.de", "a b", "de-DE") == "https://blog.de/?s=a+b"


async def fake_fetch(hass, url):
    if url.startswith("https://www.chefkoch.de/rs/s0/"):
        return SEARCH_HTML, url
    if url == REAL:
        return page("Ofen-Gnocchi mit Kürbis und Salbei", ["500 g Gnocchi", "1 Hokkaido"], 520, REAL), url
    if "chefkoch.de/rezepte/111" in url:
        return page("Tomatensuppe", ["1 kg Tomaten"], 200, url), url
    from custom_components.meal_planner_ai.services import RecipeFetchError
    raise RecipeFetchError("Rezeptseite antwortet mit HTTP 404 (x).", 404)


async def test_dead_link_replaced_by_search(hass: HomeAssistant):
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch):
        # geratener Link -> Integration sucht selbst und nimmt das echte Rezept mit echtem Titel
        dish, why = await planner._check_dish(
            {"title": "Kürbis-Gnocchi", "url": "https://www.chefkoch.de/rezepte/999/geraten.html",
             "query": "Kürbis Gnocchi", "site": "chefkoch.de"}, set(), date(2026, 11, 7))
        assert why is None, why
        assert dish["url"] == REAL and dish["title"] == "Ofen-Gnocchi mit Kürbis und Salbei" and dish["recipe_id"]
        # ohne Link, nur Suchbegriff
        dish, why = await planner._check_dish({"title": "Gnocchi", "query": "Kürbis Gnocchi"}, set(), date(2026, 11, 7))
        assert dish and dish["url"] == REAL
        # schon vergeben -> nächster passender Treffer, nie die Tomatensuppe
        dish, why = await planner._check_dish({"title": "Gnocchi", "query": "Kürbis Gnocchi", "site": "chefkoch.de"},
                                              {"ofen-gnocchi mit kürbis und salbei"}, date(2026, 11, 7))
        assert dish is None or "Gnocchi" in dish["title"]
        # nichts zu finden
        dish, why = await planner._check_dish({"title": "Quatsch", "url": "https://lecker.de/x-12345.html",
                                               "query": "zzz", "site": "lecker.de"}, set(), date(2026, 11, 7))
        assert dish is None and why

        res = await call(hass, "search_recipes", {"query": "Kürbis Gnocchi", "sites": ["chefkoch.de", "lecker.de"]})
        assert REAL in res["results"][0]["links"] and res["results"][1]["error"]


async def test_resolve_agent(hass: HomeAssistant):
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.meal_planner_ai.agent import AGENT_TITLE, _existing, resolve_agent

    entry = MockConfigEntry(domain="google_generative_ai_conversation", subentries_data=[
        ConfigSubentryData(data={}, subentry_type="conversation", title=AGENT_TITLE, unique_id=None)])
    entry.add_to_hass(hass)
    sub_id = _existing(entry)
    assert sub_id
    reg = er.async_get(hass)
    reg.async_get_or_create("conversation", "google_generative_ai_conversation", sub_id,
                            config_entry=entry, config_subentry_id=sub_id, suggested_object_id="essensplaner_rezeptsuche")
    assert resolve_agent(hass, f"auto:{entry.entry_id}:{sub_id}") == "conversation.essensplaner_rezeptsuche"
    assert resolve_agent(hass, "conversation.x") == "conversation.x"
    assert resolve_agent(hass, "none") is None and resolve_agent(hass, f"auto:{entry.entry_id}:nix") is None


async def test_fetch_reads_whole_page(hass: HomeAssistant, aioclient_mock):
    """Große Seiten kommen in mehreren Stücken; das Rezept steht oft ganz hinten."""
    from custom_components.meal_planner_ai.services import fetch_html

    body = "<html>" + "x" * 300_000 + '<script type="application/ld+json">{"@type":"Recipe"}</script></html>'
    aioclient_mock.get("https://www.chefkoch.de/rezepte/1/x.html", text=body)
    with patch("custom_components.meal_planner_ai.services._resolve", return_value=["91.198.174.192"]):
        html, _ = await fetch_html(hass, "https://www.chefkoch.de/rezepte/1/x.html")
    assert html.endswith("</script></html>")


async def test_fake_wish_and_wrong_link(hass: HomeAssistant):
    """KI-Begründung im Feld "wish" hebelt keine Regeln aus; Link zu anderem Rezept wird ersetzt."""
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    slow = "https://www.chefkoch.de/rezepte/5/Kohlrouladen.html"

    async def fetch(hass_, url):
        if url == slow:
            return page("Omas Kohlrouladen", ["1 Weißkohl", "500 g Hackfleisch"], 600, slow, minutes=90), url
        return await fake_fetch(hass_, url)

    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fetch):
        planner._wish_texts = {"lasagne"}
        dish, why = await planner._check_dish({"title": "Omas Kohlrouladen", "url": slow, "wish": "Bodenständig"},
                                              set(), date(2026, 11, 7))
        assert dish is None and "dauert 90" in why
        # Link der KI zeigt auf ein anderes Rezept (Tomatensuppe) -> Suche nach dem gemeinten Gericht
        dish, why = await planner._check_dish(
            {"title": "Kürbis Gnocchi", "url": "https://www.chefkoch.de/rezepte/111/Tomatensuppe.html",
             "site": "chefkoch.de"}, set(), date(2026, 11, 7))
        assert dish and dish["url"] == REAL


async def test_google_redirect_resolved(hass: HomeAssistant):
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/ABC"

    async def fetch(hass_, url):
        if url == redirect:
            return page("Ofen-Gnocchi mit Kürbis und Salbei", ["500 g Gnocchi"], 520, REAL), REAL
        return await fake_fetch(hass_, url)

    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fetch):
        dish, why = await planner._check_dish({"title": "Ofen-Gnocchi mit Kürbis", "url": redirect}, set(),
                                              date(2026, 11, 7))
        assert why is None and dish["url"] == REAL


async def test_undo_cooked_restores_history(hass: HomeAssistant):
    """Versehentlich als gekocht markiert: Rückgängig entfernt Tag, Sterne und Notiz aus dem Verlauf."""
    from custom_components.meal_planner_ai.board import WeekPlanner  # noqa: F401

    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch):
        dish, _ = await planner._check_dish({"title": "Kürbis Gnocchi", "url": REAL}, set(), date(2026, 11, 7))
    planner.store.update_history(dish["recipe_id"], rating=5, note="lecker")  # alte Bewertung
    planner.boards["next"] = {"dishes": [dish]}
    await planner.async_mark_cooked(dish["id"], True, 2, "Test")
    hist = planner.store.get(dish["recipe_id"])["history"]
    assert hist["cooked_on"] and hist["rating"] == 2
    await planner.async_mark_cooked(dish["id"], False, None, None)
    hist = planner.store.get(dish["recipe_id"])["history"]
    assert hist["cooked_on"] == [] and hist["rating"] == 5 and hist["note"] == "lecker" and hist["status"] == "new"
    assert dish["cooked_on"] is None and dish["rating"] is None


async def test_wish_with_dead_link_is_searched(hass: HomeAssistant):
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    planner._wish_texts = {"kürbis gnocchi"}
    with patch("custom_components.meal_planner_ai.services.fetch_html", side_effect=fake_fetch):
        dish, why = await planner._check_dish(
            {"title": "Kürbis Gnocchi", "wish": "Kürbis Gnocchi", "url": "https://www.chefkoch.de/rezepte/9/tot.html"},
            set(), date(2026, 11, 7))
    assert why is None and dish["url"] == REAL and dish["wish"]


async def test_settings_saved_during_run_wait(hass: HomeAssistant):
    """Einstellungen während eines Laufs speichern: Neuladen wartet, der Lauf behält seinen Speicher."""
    entry = await setup_entry(hass)
    planner = entry.runtime_data.planner
    planner.busy = True
    hass.config_entries.async_update_entry(entry, options={**entry.options, "portions": 4})
    await hass.async_block_till_done()
    assert entry.runtime_data.planner is planner and planner.reload_pending
    assert planner.store is entry.runtime_data.store
