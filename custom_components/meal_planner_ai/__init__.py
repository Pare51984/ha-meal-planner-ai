"""Essensplaner: Rezepte importieren, speichern, einkaufen und Wochenpläne prüfen."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from datetime import datetime

from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .board import WeekPlanner, _parse_time
from .frontend import async_register_card, async_remove_display, async_setup_display
from .const import (
    CONF_DEADLINE_TIME,
    CONF_DISPLAY,
    CONF_DISPLAY_DASHBOARD,
    CONF_DISPLAY_STYLE,
    CONF_PLAN_TIME,
    CONF_PROFILE,
    DOMAIN,
)
from .services import EssensplanerConfigEntry, EssensplanerData, async_register_services
from .storage import RecipeStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _platforms(entry: EssensplanerConfigEntry) -> list[Platform]:
    return [Platform.SENSOR, Platform.TODO]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Aktionen registrieren (einmalig, unabhängig vom Eintrag)."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EssensplanerConfigEntry) -> bool:
    store = RecipeStore(hass)
    await store.async_load()
    platforms = _platforms(entry)
    entry.runtime_data = EssensplanerData(store=store, platforms=platforms, options=dict(entry.options))
    planner = WeekPlanner(hass, entry)
    entry.runtime_data.planner = planner
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    settings = planner.settings
    times = {_parse_time(settings[k]) for k in (CONF_PLAN_TIME, CONF_DEADLINE_TIME)}
    times |= {_parse_time(t["time"]) for t in settings["trips"] if t["time"]}

    async def _tick(now: datetime) -> None:
        await planner.async_tick(dt_util.as_local(now))

    for at in times:
        entry.async_on_unload(
            async_track_time_change(hass, _tick, hour=at.hour, minute=at.minute, second=5))
    # stündlich nachsehen, ob die externe KI geliefert hat (sonst springt die KI in HA ein)
    entry.async_on_unload(async_track_time_change(hass, _tick, minute=0, second=20))

    from .llm_api import async_register as async_register_llm_api

    # Werkzeug-Sammlung „Meal Planner AI“ für externe KIs (z. B. über den offiziellen MCP-Server)
    entry.async_on_unload(async_register_llm_api(hass))

    await async_register_card(hass)
    if await async_setup_display(hass, settings[CONF_DISPLAY], settings[CONF_DISPLAY_DASHBOARD], store.meta,
                                 settings[CONF_DISPLAY_STYLE]):
        store.set_meta("display_views", store.meta["display_views"])

    async def _catch_up(_hass: HomeAssistant) -> None:
        await planner.async_tick(dt_util.now())

    # Verpasste Schritte (z. B. Neustart zum Auswahlschluss) nachholen, wenn HA fertig gestartet ist.
    entry.async_on_unload(async_at_started(hass, _catch_up))
    return True


async def _async_reload(hass: HomeAssistant, entry: EssensplanerConfigEntry) -> None:
    data = getattr(entry, "runtime_data", None)
    old = (data.options if data else None) or {}
    changed = {k for k in {*old, *entry.options} if old.get(k) != entry.options.get(k)}
    if data is not None and changed <= {CONF_PROFILE}:
        # nur das Geschmacksprofil geändert: wird beim nächsten Lauf frisch gelesen, kein Neuladen nötig
        data.options = dict(entry.options)
        return
    planner = getattr(data, "planner", None)
    if planner is not None and planner.busy:
        # Einstellungen wurden während eines Vorschlagslaufs gespeichert: erst danach neu laden
        planner.reload_pending = True
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: EssensplanerConfigEntry) -> None:
    """Integration gelöscht: auch die selbst angelegten Ansichten wieder entfernen."""
    from homeassistant.helpers.storage import Store

    from .const import STORAGE_KEY_RECIPES, STORAGE_VERSION

    from .const import STORAGE_KEY_SHOPPING, STORAGE_KEY_WISHES

    data = await Store(hass, STORAGE_VERSION, STORAGE_KEY_RECIPES).async_load() or {}
    await async_remove_display(hass, data.get("meta") or {})
    if not hass.config_entries.async_entries(DOMAIN):
        # letzte Instanz gelöscht: gespeicherte Rezepte, Wünsche und eigene Liste mit entfernen
        for key in (STORAGE_KEY_RECIPES, STORAGE_KEY_WISHES, STORAGE_KEY_SHOPPING):
            await Store(hass, STORAGE_VERSION, key).async_remove()


async def async_unload_entry(hass: HomeAssistant, entry: EssensplanerConfigEntry) -> bool:
    await async_remove_display(hass)
    await entry.runtime_data.store.async_flush()
    return await hass.config_entries.async_unload_platforms(entry, entry.runtime_data.platforms)
