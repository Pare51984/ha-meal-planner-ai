"""Bewertung mit 10 Sternen (ab 0.41.0) und einmalige Umrechnung alter 5-Sterne-Bewertungen."""
from datetime import date

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.meal_planner_ai.const import (
    RATING_DISLIKED,
    RATING_LIKED,
    RATING_MAX,
    RATING_SCALE_KEY,
    STORAGE_KEY_RECIPES,
)
from custom_components.meal_planner_ai.services import COOKED_SCHEMA, HISTORY_SCHEMA
from custom_components.meal_planner_ai.storage import RecipeStore


def _rec(rid: str, rating):
    return {"id": rid, "title": rid, "source_url": None, "ingredients": [],
            "history": {"status": "cooked", "rating": rating, "cooked_on": ["2026-11-01"],
                        "bought_on": None, "note": None}}


async def test_old_ratings_doubled_once(hass: HomeAssistant):
    board = {"current": {"id": "2026-46", "dishes": [
        {"id": "d1", "title": "a", "rating": 4,
         "before_cooked": {"rating": 2, "dish_rating": 3, "note": None}},
        {"id": "d2", "title": "b", "rating": None}]}, "next": None}
    await Store(hass, 1, STORAGE_KEY_RECIPES).async_save(
        {"recipes": {"a": _rec("a", 5), "b": _rec("b", 1), "c": _rec("c", None)}, "meta": {"board": board}})

    store = RecipeStore(hass)
    await store.async_load()
    assert [store.recipes[k]["history"]["rating"] for k in "abc"] == [10, 2, None]
    dish = store.meta["board"]["current"]["dishes"][0]
    assert dish["rating"] == 8 and dish["before_cooked"]["rating"] == 4 and dish["before_cooked"]["dish_rating"] == 6
    assert store.meta["board"]["current"]["dishes"][1]["rating"] is None
    assert store.meta[RATING_SCALE_KEY] == RATING_MAX

    await store.async_flush()
    again = RecipeStore(hass)
    await again.async_load()
    assert again.recipes["a"]["history"]["rating"] == 10  # nicht ein zweites Mal verdoppelt


async def test_new_scale_limits(hass: HomeAssistant):
    await Store(hass, 1, STORAGE_KEY_RECIPES).async_save(
        {"recipes": {"a": _rec("a", None)}, "meta": {RATING_SCALE_KEY: RATING_MAX}})
    store = RecipeStore(hass)
    await store.async_load()
    store.update_history("a", rating=10)
    assert store.recipes["a"]["history"]["rating"] == 10
    store.update_history("a", rating=0)
    assert store.recipes["a"]["history"]["rating"] is None

    assert COOKED_SCHEMA({"dish_id": "x", "rating": 10})["rating"] == 10
    for bad in (0, 11):
        with pytest.raises(vol.Invalid):
            COOKED_SCHEMA({"dish_id": "x", "rating": bad})
    with pytest.raises(vol.Invalid):
        HISTORY_SCHEMA({"recipe_id": "a", "rating": 11})
    assert HISTORY_SCHEMA({"recipe_id": "a", "rating": 7})["rating"] == 7
    assert (RATING_LIKED, RATING_DISLIKED) == (7, 4)


async def test_profile_uses_scaled_limits(hass: HomeAssistant):
    from types import SimpleNamespace

    from custom_components.meal_planner_ai.board import WeekPlanner

    await Store(hass, 1, STORAGE_KEY_RECIPES).async_save({"recipes": {
        "gut": _rec("gut", 7), "mittel": _rec("mittel", 6), "schlecht": _rec("schlecht", 4),
        "neutral": _rec("neutral", 5),
    }, "meta": {RATING_SCALE_KEY: RATING_MAX}})
    store = RecipeStore(hass)
    await store.async_load()

    fake = SimpleNamespace(store=store)
    data = WeekPlanner.profile_data(fake, today=date(2026, 12, 31))
    assert [r["title"] for r in data["liked"]] == ["gut"]
    assert [r["title"] for r in data["disliked"]] == ["schlecht"]
    fake.profile_data = lambda today=None: data
    ctx = WeekPlanner._profile_context(fake, date(2026, 12, 31))
    assert ctx["liked"] == ["gut (7/10)"] and ctx["disliked"] == ["schlecht (4/10)"]
    assert WeekPlanner._disliked(fake, store.get("schlecht"), "schlecht")
    assert not WeekPlanner._disliked(fake, store.get("neutral"), "neutral")
