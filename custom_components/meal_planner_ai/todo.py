"""Eigene Einkaufsliste, falls der Nutzer keine vorhandene Liste nutzen will."""

from __future__ import annotations

from typing import Any
import uuid

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .const import (
    CONF_SHOPPING_LIST,
    DOMAIN,
    OWN_LIST,
    STORAGE_KEY_SHOPPING,
    STORAGE_KEY_WISHES,
    STORAGE_VERSION,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entities = [StoredTodoList(hass, entry, STORAGE_KEY_WISHES, "wishes", "todo.meal_planner_wishes")]
    if {**entry.data, **entry.options}.get(CONF_SHOPPING_LIST) == OWN_LIST:
        entities.append(StoredTodoList(hass, entry, STORAGE_KEY_SHOPPING, "shopping_list",
                                       "todo.meal_planner_shopping_list"))
    for entity in entities:
        await entity.async_load()
    async_add_entities(entities)


class StoredTodoList(TodoListEntity):
    """Einfache Liste im HA-Speicher (Wünsche bzw. eigene Einkaufsliste)."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.MOVE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, storage_key: str, key: str,
                 entity_id: str) -> None:
        self._hass = hass
        self._key = storage_key
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, storage_key)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_icon = "mdi:lightbulb-on-outline" if key == "wishes" else "mdi:cart"
        # Feste, sprachunabhängige ID, damit Automationen und Claude sie sicher finden.
        self.entity_id = entity_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Meal Planner AI",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_todo_items: list[TodoItem] = []

    async def async_load(self) -> None:
        from .storage import async_load_with_legacy

        data = await async_load_with_legacy(self._hass, self._store, self._key) or {}
        self._attr_todo_items = [
            TodoItem(
                uid=i["uid"],
                summary=i["summary"],
                status=TodoItemStatus(i["status"]),
                description=i.get("description"),
            )
            for i in data.get("items", [])
        ]

    def _data(self) -> dict[str, Any]:
        return {
            "items": [
                {"uid": i.uid, "summary": i.summary, "status": i.status, "description": i.description}
                for i in self._attr_todo_items
            ]
        }

    async def async_will_remove_from_hass(self) -> None:
        await self._store.async_save(self._data())

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 1)
        self.async_write_ha_state()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        self._attr_todo_items.append(
            TodoItem(
                uid=uuid.uuid4().hex,
                summary=item.summary,
                status=item.status or TodoItemStatus.NEEDS_ACTION,
                description=item.description,
            )
        )
        self._save()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        for idx, existing in enumerate(self._attr_todo_items):
            if existing.uid == item.uid:
                self._attr_todo_items[idx] = item
                break
        self._save()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        self._attr_todo_items = [i for i in self._attr_todo_items if i.uid not in set(uids)]
        self._save()

    async def async_move_todo_item(self, uid: str, previous_uid: str | None = None) -> None:
        items = self._attr_todo_items
        moving = next((i for i in items if i.uid == uid), None)
        if moving is None:
            return
        items.remove(moving)
        pos = 0
        if previous_uid:
            pos = next((n + 1 for n, i in enumerate(items) if i.uid == previous_uid), len(items))
        items.insert(pos, moving)
        self._save()
