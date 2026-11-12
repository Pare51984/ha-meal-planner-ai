"""Einkaufsliste: Einträge, die es beim Austragen nicht mehr gibt, dürfen keinen Fehler auslösen."""
import itertools

from homeassistant.components.todo import TodoListEntityFeature
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from custom_components.meal_planner_ai.shopping import async_add_items, async_remove_tag

ENTITY = "todo.fake"


class FakeStore:
    """Nur der Teil des Rezeptspeichers, den die Einkaufsliste braucht."""

    def __init__(self, owned: list[str] | None = None) -> None:
        self.meta = {"shopping_owned": {ENTITY: owned or []}}

    def set_meta(self, key, value):
        self.meta[key] = value

    def owned(self):
        return self.meta["shopping_owned"].get(ENTITY, [])
FEATURES = (TodoListEntityFeature.CREATE_TODO_ITEM | TodoListEntityFeature.UPDATE_TODO_ITEM
            | TodoListEntityFeature.DELETE_TODO_ITEM | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM)


def _fake_list(hass: HomeAssistant, items: list[dict], *, new_ids: bool = False, stale_first: int = 0):
    """Liste wie Bring!: optional neue IDs bei jedem Lesen; die ersten `stale_first` Aufrufe
    treffen auf eine schon vergebene ID (Eintrag nicht gefunden)."""
    counter = itertools.count()
    calls = {"stale": stale_first, "remove": [], "update": []}
    hass.states.async_set(ENTITY, "0", {"supported_features": FEATURES})

    def get_items(call: ServiceCall):
        if new_ids:
            for item in items:
                item["uid"] = f"u{next(counter)}"
        return {ENTITY: {"items": [dict(i, status="needs_action") for i in items]}}

    def _find(uid):
        if calls["stale"] > 0:
            calls["stale"] -= 1
            raise ServiceValidationError(f"Unable to find to-do list item: {uid}")
        hit = next((i for i in items if i["uid"] == uid), None)
        if hit is None:
            raise ServiceValidationError(f"Unable to find to-do list item: {uid}")
        return hit

    def remove_item(call: ServiceCall):
        hit = _find(call.data["item"])
        items.remove(hit)
        calls["remove"].append(hit["summary"])

    def update_item(call: ServiceCall):
        hit = _find(call.data["item"])
        hit["description"] = call.data["description"]
        calls["update"].append(hit["summary"])

    def add_item(call: ServiceCall):
        items.append({"uid": f"n{next(counter)}", "summary": call.data["item"],
                      "description": call.data.get("description")})

    hass.services.async_register("todo", "get_items", get_items, supports_response=SupportsResponse.ONLY)
    hass.services.async_register("todo", "remove_item", remove_item)
    hass.services.async_register("todo", "update_item", update_item)
    hass.services.async_register("todo", "add_item", add_item)
    return calls


async def test_remove_survives_new_ids(hass: HomeAssistant):
    items = [{"uid": "a", "summary": "Linsen", "description": "200 g (Spätzle)"},
             {"uid": "b", "summary": "Zwiebeln", "description": "1 (Curry) + 2 (Spätzle)"},
             {"uid": "c", "summary": "Milch", "description": "1 l (Curry)"}]
    _fake_list(hass, items, new_ids=True, stale_first=1)
    removed = await async_remove_tag(hass, ENTITY, "Spätzle", FakeStore(["linsen"]))
    assert sorted(removed) == ["Linsen", "Zwiebeln"]
    assert [i["summary"] for i in items] == ["Zwiebeln", "Milch"]
    assert items[0]["description"] == "1 (Curry)"


async def test_remove_gives_up_quietly_on_missing_item(hass: HomeAssistant):
    items = [{"uid": "a", "summary": "Linsen", "description": "200 g (Spätzle)"}]
    _fake_list(hass, items, stale_first=10)
    assert await async_remove_tag(hass, ENTITY, "Spätzle") == []  # kein Fehler


async def test_add_falls_back_when_merge_target_vanished(hass: HomeAssistant):
    items = [{"uid": "a", "summary": "Zwiebeln", "description": "1 (Curry)"}]
    _fake_list(hass, items, stale_first=1)
    result = await async_add_items(hass, ENTITY, [{"name": "Zwiebeln", "spec": "2"}], "Spätzle")
    assert result[0]["action"] == "merged"
    assert items[0]["description"] == "1 (Curry) + 2 (Spätzle)"


async def test_ai_call_times_out(hass: HomeAssistant):
    """Hängt die KI, gibt es nach AI_TIMEOUT einen klaren Fehler statt eines ewig laufenden Plans."""
    import asyncio
    from unittest.mock import patch

    import pytest

    from custom_components.meal_planner_ai.ai import AIError, async_ask

    async def slow(call: ServiceCall):
        await asyncio.sleep(5)
        return {"data": "{}"}

    hass.states.async_set("ai_task.slow", "unknown")
    hass.services.async_register("ai_task", "generate_data", slow, supports_response=SupportsResponse.ONLY)
    with patch("custom_components.meal_planner_ai.ai.AI_TIMEOUT", 0.05), pytest.raises(AIError, match="nicht innerhalb"):
        await async_ask(hass, "ai_task.slow", "Test", "x")


async def test_own_item_without_description_is_kept(hass: HomeAssistant):
    """Selbst eingetragene „Milch“: ein Gericht hängt sich an, beim Abwählen bleibt die Milch stehen."""
    items = [{"uid": "a", "summary": "Milch", "description": None}]
    calls = _fake_list(hass, items)
    store = FakeStore()
    result = await async_add_items(hass, ENTITY, [{"name": "Milch", "spec": "1 l"}], "Curry", store)
    assert result[0]["action"] == "merged" and items[0]["description"] == "1 l (Curry)"
    assert await async_remove_tag(hass, ENTITY, "Curry", store) == ["Milch"]
    assert [i["summary"] for i in items] == ["Milch"] and not items[0]["description"]
    assert calls["remove"] == []


async def test_own_item_description_restored(hass: HomeAssistant):
    items = [{"uid": "a", "summary": "Milch", "description": "Bio"}]
    _fake_list(hass, items)
    store = FakeStore()
    await async_add_items(hass, ENTITY, [{"name": "Milch", "spec": "1 l"}], "Curry", store)
    assert items[0]["description"] == "Bio + 1 l (Curry)"
    await async_remove_tag(hass, ENTITY, "Curry", store)
    assert items[0]["description"] == "Bio"


async def test_created_item_removed_and_forgotten(hass: HomeAssistant):
    items: list[dict] = []
    calls = _fake_list(hass, items)
    store = FakeStore()
    await async_add_items(hass, ENTITY, [{"name": "Linsen", "spec": "200 g"}], "Curry", store)
    assert store.owned() == ["linsen"]
    await async_add_items(hass, ENTITY, [{"name": "Linsen", "spec": "100 g"}], "Dal", store)
    await async_remove_tag(hass, ENTITY, "Curry", store)
    assert items[0]["description"] == "100 g (Dal)"
    await async_remove_tag(hass, ENTITY, "Dal", store)
    assert items == [] and calls["remove"] == ["Linsen"] and store.owned() == []


async def test_same_name_added_by_user_later_is_not_ours(hass: HomeAssistant):
    """Name ist noch als „unserer“ gemerkt (z. B. alter Eintrag abgehakt), der Haushalt trägt ihn neu ein."""
    items = [{"uid": "a", "summary": "Milch", "description": ""}]
    calls = _fake_list(hass, items)
    store = FakeStore(["milch"])
    await async_add_items(hass, ENTITY, [{"name": "Milch", "spec": "1 l"}], "Curry", store)
    assert store.owned() == []
    await async_remove_tag(hass, ENTITY, "Curry", store)
    assert [i["summary"] for i in items] == ["Milch"] and calls["remove"] == []
