"""Regressionstests zu den Funden aus dem Code-Review (Nov 2026)."""
from datetime import datetime

from homeassistant.core import HomeAssistant

from custom_components.meal_planner_ai.ai import parse_json
from custom_components.meal_planner_ai.board import _norm_title, _wish_matches, week_meta
from custom_components.meal_planner_ai.classify import parse_ingredient
from custom_components.meal_planner_ai.shopping import async_remove_tag, has_tag, strip_tag

from .test_list_robust import ENTITY, _fake_list


def test_tag_with_plus_in_title():
    desc = "1 (Curry) + 2 (Fish & Chips)"
    assert has_tag(desc, "Fish + Chips")
    assert strip_tag(desc, "Fish + Chips") == "1 (Curry)"


async def test_remove_tag_ignores_substring_in_other_text(hass: HomeAssistant):
    """„(vegan)“ mitten im Text ist kein Gericht „vegan“: nichts tun und nicht im Kreis laufen."""
    items = [{"uid": "a", "summary": "Tofu", "description": "200 g (vegan) extra (Curry)"}]
    _fake_list(hass, items)
    assert await async_remove_tag(hass, ENTITY, "vegan") == []
    assert items[0]["description"] == "200 g (vegan) extra (Curry)"


def test_title_without_tm_suffix_counts_as_duplicate():
    assert _norm_title("Linseneintopf (TM)") == _norm_title("Linseneintopf")


def test_wish_partial_match():
    assert _wish_matches(_norm_title("was mit Kürbis"), ("Kürbis", "Kürbissuppe mit Ingwer"))
    assert not _wish_matches(_norm_title("Lasagne"), ("Kürbis", "Kürbissuppe"))


def test_ingredient_plural_and_note():
    got = parse_ingredient("2 Zwiebel(n) (fein gewürfelt)")
    assert (got["name"], got["note"]) == ("Zwiebeln", "fein gewürfelt")


def test_parse_json_takes_second_code_block():
    raw = 'Beispiel:\n```\nnicht json\n```\nErgebnis:\n```json\n{"dishes": []}\n```'
    assert parse_json(raw) == {"dishes": []}


def test_release_not_before_deadline():
    """Einkauf Sa 10:00, Auswahlschluss So 12:00: Freigabe am Samstag danach, nicht vor dem Auswahlschluss."""
    settings = {"deadline_weekday": 6, "deadline_time": "12:00",
                "trips": [{"key": "trip1", "release": "timed", "weekday": 5, "time": "10:00"},
                          {"key": "trip2", "release": "timed", "weekday": 6, "time": "12:00"}]}
    meta = week_meta(datetime(2026, 11, 13, 18, 0), settings)  # Freitag 18:00
    assert meta["deadline"].startswith("2026-11-15T12:00")
    assert meta["release_at"]["trip1"].startswith("2026-11-21T10:00")
    assert meta["release_at"]["trip2"].startswith("2026-11-15T12:00")  # genau zum Auswahlschluss bleibt


async def test_llm_api_has_requires_admin(hass: HomeAssistant):
    """Neuere HA-Versionen lesen api.requires_admin in llm/list_apis; fehlt es, bricht die ganze Liste."""
    from custom_components.meal_planner_ai.llm_api import EssensplanerAPI

    api = EssensplanerAPI(hass)
    assert api.requires_admin is False


async def test_ai_error_details_and_empty_answer(hass: HomeAssistant):
    """Live-Test 11/2026: Fehler kamen nur als „unknown“ an, leere Antworten (max_tokens) liefen still durch."""
    from homeassistant.core import SupportsResponse

    from custom_components.meal_planner_ai.ai import AIError, async_ask

    async def fake_process(call):
        if "fehler" in call.data["text"]:
            return {"response": {"response_type": "error", "data": {"code": "unknown"}, "speech": {"plain": {
                "speech": "Sorry, I had a problem talking to Anthropic: stop_reason max_tokens"}}}}
        return {"response": {"response_type": "action_done", "speech": {"plain": {"speech": ""}}}}

    async def fake_task(call):
        return {"conversation_id": "x", "data": None}

    hass.services.async_register("conversation", "process", fake_process, supports_response=SupportsResponse.ONLY)
    hass.services.async_register("ai_task", "generate_data", fake_task, supports_response=SupportsResponse.ONLY)
    hass.states.async_set("conversation.suche", "unknown")
    hass.states.async_set("ai_task.ki", "unknown")
    for entity, text, expected in (
        ("conversation.suche", "fehler", "max_tokens"),
        ("conversation.suche", "leer", "Maximale Tokens"),
        ("ai_task.ki", "leer", "Maximale Tokens"),
    ):
        try:
            await async_ask(hass, entity, "Test", text)
            raise AssertionError("Fehler erwartet")
        except AIError as err:
            assert expected in str(err), str(err)


def test_same_dish_rejects_other_main_ingredient():
    """Live-Test 11/2026: die Ersatzsuche übernahm Treffer mit anderer Hauptzutat."""
    from custom_components.meal_planner_ai.search import same_dish

    assert not same_dish("Kürbis-Curry mit Reis", "Hähnchen-Curry mit Kurkuma-Reis")
    assert not same_dish("Kürbispfanne mit Feta", "Feta-Dip mit Kräutern (TM)")
    assert not same_dish("Hähnchen-Gemüse-Pfanne mit Reis", "Bratreis")
    assert not same_dish("Hähnchen-Gyros mit Krautsalat, Reis", "Griechisches Putengyros mit Paprika, Feta, Reis (TM)")
    # zusammengesetzte Wörter und Adjektive bleiben erlaubt
    assert same_dish("Rinderschmorgulasch mit Nudeln", "Rindergulasch mit Nudeln")
    assert same_dish("Ofenlachs mit Kartoffeln und Gemüse", "Lachs mit Gemüse und Kartoffeln")
    assert same_dish("Schnelle Süßkartoffel-Hähnchen-Pfanne", "Süßkartoffel-Hähnchenpfanne")
    assert same_dish("Linsen Curry", "Linsencurry")
    assert same_dish("Pilz-Risotto (TM)", "Pilzrisotto mit gebratenen Pilzen (TM)")


def test_meat_beats_wrong_vegetarian_label():
    """Live-Test 11/2026: „Griechisches Putengyros“ war als fleischlos markiert (Seite sagte vegetarisch)."""
    from custom_components.meal_planner_ai.classify import classify_diet

    base = {"title": "Griechisches Putengyros mit Paprika, Feta, Reis",
            "dietary_restrictions": ["VegetarianDiet"]}
    assert classify_diet({**base, "ingredients": ["400 g Putenbrust", "1 Paprika"]}, None)["vegetarian"] is False
    # auch ohne lesbare Zutaten entscheidet der Titel
    assert classify_diet({**base, "ingredients": []}, None)["vegetarian"] is False
    # echte vegetarische Gerichte bleiben vegetarisch
    veg = {"title": "Kürbis-Kichererbsen-Curry", "ingredients": ["500 g Kürbis", "1 Dose Kichererbsen"]}
    assert classify_diet(veg, None)["vegetarian"] is True
    assert classify_diet({**veg, "ingredients": [], "dietary_restrictions": ["VegetarianDiet"]}, None)["vegetarian"] is True


async def test_rejected_titles_lead_followup_prompt(hass: HomeAssistant):
    """Live-Test 11/2026: Folge-Runden schlugen verworfene Gerichte erneut vor, dazu Titel wie „X-Alternative: Y“."""
    from homeassistant.core import SupportsResponse

    from .test_integration import setup_entry

    prompts = []

    async def task(call):
        prompts.append(call.data["instructions"])
        return {"conversation_id": "x", "data": {"dishes": [
            {"title": "Ofen-Kürbis-Gnocchi-Alternative: Kürbis-Lasagne", "url": "https://www.chefkoch.de/rezepte/1/x.html"}]}}

    hass.services.async_register("ai_task", "generate_data", task, supports_response=SupportsResponse.ONLY)
    hass.states.async_set("ai_task.gemini", "unknown")
    entry = await setup_entry(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, "ai_task": "ai_task.gemini",
                                                           "ai_search": None})
    await hass.async_block_till_done()
    planner = hass.config_entries.async_entries("meal_planner_ai")[0].runtime_data.planner
    await planner.async_generate(force=True)
    assert len(prompts) >= 2
    line = next(x for x in prompts[1].splitlines() if x.startswith("Nicht vorschlagen"))
    assert line.split(": ", 1)[1].startswith("Ofen-Kürbis-Gnocchi-Alternative: Kürbis-Lasagne")
    assert planner.boards["next"]["dishes"] == []
    # Budget hängt an der Zahl der Gerichte
    from custom_components.meal_planner_ai.board import SEARCH_BUDGET, SEARCH_PER_DISH
    assert planner._budget <= max(SEARCH_BUDGET, SEARCH_PER_DISH * planner.settings["recipes_per_week"])



async def test_busy_is_validation_error_and_kochbar_not_searched(hass: HomeAssistant):
    """Doppelt gedrückt: kein ERROR im Log (ServiceValidationError); kochbar.de-Suche liefert 404 und wird ausgelassen."""
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.meal_planner_ai.search import NO_SEARCH

    from .test_integration import setup_entry

    assert "kochbar.de" in NO_SEARCH
    await setup_entry(hass)
    planner = hass.config_entries.async_entries("meal_planner_ai")[0].runtime_data.planner
    planner.busy = True
    with pytest.raises(ServiceValidationError):
        await planner.async_more()
    planner.busy = False
