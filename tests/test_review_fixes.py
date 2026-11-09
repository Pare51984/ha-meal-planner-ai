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
