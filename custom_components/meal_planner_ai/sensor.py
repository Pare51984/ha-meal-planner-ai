"""Zwei Sensoren als Datenquelle für die Kacheln: Vorschläge und laufende Woche."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_BOARD_UPDATED, TRIP_KEYS

DISH_FIELDS = (
    "id", "nr", "title", "url", "time_min", "kcal", "kcal_note", "meatless", "low_cholesterol",
    "fits", "skip_items", "foreign_language", "own_recipe", "tip", "choice", "ingredients_ready", "on_list", "cooked_on",
    "rating", "note", "carried", "checked", "reason",
)
SCHEDULE_KEYS = ("plan_weekday", "plan_time", "deadline_weekday", "deadline_time", "recipes_per_week")
BOARD_FIELDS = ("kw", "start", "end", "deadline", "release_at", "released", "problems", "deficits")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([
        BoardSensor(entry, "next", "proposals", "proposals"),
        BoardSensor(entry, "current", "week", "week"),
    ])


class BoardSensor(SensorEntity):
    """Zustand = Anzahl der Gerichte; Attribute = Gerichte mit allem für die Kachel."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({"dishes", "trips", "schedule", "wishes_entity", "busy", *BOARD_FIELDS})

    def __init__(self, entry: ConfigEntry, key: str, object_id: str, translation_key: str) -> None:
        self._entry = entry
        self._key = key
        self.entity_id = f"sensor.meal_planner_{object_id}"
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = "mdi:silverware-fork-knife" if key == "current" else "mdi:chef-hat"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name="Meal Planner AI", entry_type=DeviceEntryType.SERVICE)

    @property
    def _board(self) -> dict[str, Any] | None:
        return self._entry.runtime_data.store.meta.get("board", {}).get(self._key)

    @property
    def native_value(self) -> int:
        board = self._board
        if not board:
            return 0
        if self._key == "current":
            return sum(1 for d in board["dishes"] if d["choice"] in TRIP_KEYS)
        return len(board["dishes"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        board = self._board
        settings = self._entry.runtime_data.planner.settings
        trips = [{k: t.get(k) for k in ("key", "name", "release", "weekday", "time", "days")} for t in settings["trips"]]
        # Zeitplan für die „So geht's“-Hilfe der Karte
        schedule = {k: settings.get(k) for k in SCHEDULE_KEYS}
        extra = {"trips": trips, "schedule": schedule,
                 "wishes_entity": self._entry.runtime_data.planner.wishes_entity(),
                 "busy": self._entry.runtime_data.planner.busy}
        if not board:
            return {**extra, "dishes": []}
        return {
            **extra,
            **{k: board.get(k) for k in BOARD_FIELDS},
            "dishes": [{k: d.get(k) for k in DISH_FIELDS} for d in board["dishes"]],
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_BOARD_UPDATED, self._update))

    @callback
    def _update(self) -> None:
        self.async_write_ha_state()
