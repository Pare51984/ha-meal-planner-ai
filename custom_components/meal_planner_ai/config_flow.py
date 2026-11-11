"""Einrichtungs- und Optionsdialog des Essensplaners."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.components.todo import TodoListEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector as sel

from .const import (
    AI_NONE,
    CONF_CATALOG,
    CONF_DASHBOARD_PATH,
    CONF_DEADLINE_DAY,
    CONF_DEADLINE_TIME,
    CONF_KCAL_MAX_NO_SIDE,
    CONF_CAL_RULES,
    MAX_CAL_RULES,
    CONF_NOTIFY,
    CONF_PLAN_DAY,
    CONF_PLAN_TIME,
    CONF_PORTIONS,
    CONF_PROFILE,
    CONF_MAX_SAME_MAIN,
    CONF_QUICK_SHARE,
    CONF_SKIP_SPICES,
    CONF_HABITS,
    CONF_KCAL_AWARE,
    MAX_HABITS,
    CONF_STAPLES,
    CONF_TIME_MAX,
    CONF_TIME_QUICK,
    DEFAULTS,
    WEEKDAYS,
    CONF_TRIPS,
    DEFAULT_TRIPS,
    CONF_DISPLAY,
    CONF_DISPLAY_DASHBOARD,
    CONF_DISPLAY_STYLE,
    DISPLAYS,
    STYLES,
    DISPLAY_PANEL,
    RELEASE_IMMEDIATE,
    RELEASE_TIMED,
    CONF_AI_SHOPPING,
    CONF_AI_TASK,
    CONF_AI_SEARCH,
    CONF_PROPOSALS_FROM,
    PROPOSALS_EXTERNAL,
    PROPOSALS_HA,
    CONF_REGION,
    REGIONS,
    default_region,
    CONF_CUSTOM_DEVICES,
    CONF_CUSTOM_SOURCES,
    CONF_HIDDEN_SOURCES,
    CONF_DEVICE_COUNTS,
    CONF_DEVICES,
    CONF_DIET,
    CONF_KCAL_MAX,
    CONF_RECIPES_PER_WEEK,
    CONF_SHOPPING_LIST,
    CONF_SOURCES,
    DEFAULT_RECIPES_PER_WEEK,
    DEVICE_STOVE,
    DEVICE_THERMOMIX,
    DEVICES,
    DIET_MODES,
    DIETS,
    DOMAIN,
    MODE_COUNT,
    MODE_OFF,
    OWN_LIST,
    PRESET_SOURCES,
)
from .planning import habits_from_options, overlap_needed, settings_from_options
from .messages import ui
from .shopping import DEFAULT_CATALOG, DEFAULT_STAPLES


def _site_key(domain: str) -> str:
    return "site_" + domain.replace(".", "_").replace("-", "_")


def _writable_lists(hass: HomeAssistant) -> list[sel.SelectOptionDict]:
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    options: list[sel.SelectOptionDict] = []
    for state in hass.states.async_all("todo"):
        features = int(state.attributes.get("supported_features", 0))
        reg = registry.async_get(state.entity_id)
        # eigene Listen (Wunschliste, eingebaute Einkaufsliste) nicht anbieten, auch nach Umbenennen
        if features & TodoListEntityFeature.CREATE_TODO_ITEM and not (reg and reg.platform == DOMAIN):
            options.append({"value": state.entity_id, "label": f"{state.name} ({state.entity_id})"})
    options.sort(key=lambda o: o["label"].lower())
    return options


def _list_schema(hass: HomeAssistant, current: str | None) -> vol.Schema:
    options = _writable_lists(hass) + [{"value": OWN_LIST, "label": ui(hass.config.language, "own_list")}]
    default = current or (options[0]["value"] if options else OWN_LIST)
    return vol.Schema({
        vol.Required(CONF_SHOPPING_LIST, default=default): sel.SelectSelector(
            sel.SelectSelectorConfig(options=options, mode=sel.SelectSelectorMode.DROPDOWN)
        )
    })


def _ai_schema(hass: HomeAssistant, current: str | None, shopping: bool, search: str | None = None,
               source: str = PROPOSALS_HA) -> vol.Schema:
    from .agent import resolve_agent

    search = resolve_agent(hass, search) or AI_NONE
    agents: list[sel.SelectOptionDict] = [{"value": AI_NONE, "label": ui(hass.config.language, "no_agent")}]
    from .agent import web_search_on

    for state in sorted(hass.states.async_all("conversation"), key=lambda s: s.name.lower()):
        if state.entity_id != "conversation.home_assistant":
            web = f" · {ui(hass.config.language, 'web_on')}" if web_search_on(hass, state.entity_id) else ""
            agents.append({"value": state.entity_id, "label": f"{state.name}{web} ({state.entity_id})"})
    options: list[sel.SelectOptionDict] = [{"value": AI_NONE, "label": ui(hass.config.language, "no_ai")}]
    for state in sorted(hass.states.async_all("ai_task"), key=lambda s: s.name.lower()):
        options.append({"value": state.entity_id, "label": f"{state.name} ({state.entity_id})"})
    default = current if current in [o["value"] for o in options] else (
        options[1]["value"] if len(options) > 1 and current is None else AI_NONE)
    return vol.Schema({
        vol.Required(CONF_PROPOSALS_FROM, default=source): sel.SelectSelector(sel.SelectSelectorConfig(
            options=[PROPOSALS_HA, PROPOSALS_EXTERNAL], translation_key="proposals_from",
            mode=sel.SelectSelectorMode.LIST)),
        vol.Required(CONF_AI_TASK, default=default): sel.SelectSelector(
            sel.SelectSelectorConfig(options=options, mode=sel.SelectSelectorMode.DROPDOWN)
        ),
        vol.Optional(CONF_AI_SHOPPING, default=shopping): sel.BooleanSelector(),
        vol.Required(CONF_AI_SEARCH, default=search if search in [o["value"] for o in agents] else AI_NONE):
            sel.SelectSelector(sel.SelectSelectorConfig(options=agents, mode=sel.SelectSelectorMode.DROPDOWN)),
        **_create_agent_field(hass, current, search),
    })


PROVIDER_NAMES = {"anthropic": "Claude (Anthropic)", "openai_conversation": "ChatGPT (OpenAI)",
                  "google_generative_ai_conversation": "Gemini (Google)"}


def _create_agent_field(hass: HomeAssistant, ai_task: str | None, search: str) -> dict[Any, Any]:
    """Auswahl, bei welchem KI-Anbieter der Such-Agent angelegt wird (nur Anbieter ohne Such-Agent)."""
    from homeassistant.helpers import entity_registry as er

    from .agent import _existing, pick_entry, provider_entries

    entries = [e for e in provider_entries(hass) if not _existing(e)]
    if not entries:
        return {}
    options = [{"value": "no", "label": ui(hass.config.language, "no")}] + [
        {"value": e.entry_id, "label": f"{PROVIDER_NAMES.get(e.domain, e.domain)}: {e.title}"} for e in entries]
    default = "no"
    if search == AI_NONE and ai_task and ai_task != AI_NONE:
        # neutral: nur den Anbieter vorschlagen, den der Nutzer schon als Haupt-KI gewählt hat
        preferred = pick_entry(hass, ai_task)
        reg_entry = er.async_get(hass).async_get(ai_task)
        if preferred in entries and reg_entry and reg_entry.config_entry_id == preferred.entry_id:
            default = preferred.entry_id
    return {vol.Optional("create_search_agent", default=default): sel.SelectSelector(
        sel.SelectSelectorConfig(options=options, mode=sel.SelectSelectorMode.DROPDOWN))}


def _region_selector() -> sel.SelectSelector:
    return sel.SelectSelector(sel.SelectSelectorConfig(
        options=REGIONS, translation_key="region", mode=sel.SelectSelectorMode.LIST))


async def _apply_ai(hass: HomeAssistant, user_input: dict[str, Any], target: dict[str, Any]) -> dict[str, str]:
    """KI-Auswahl übernehmen; auf Wunsch den Such-Agenten mit Websuche anlegen. Liefert Formularfehler."""
    from .agent import async_create_agent, pick_entry

    target[CONF_PROPOSALS_FROM] = user_input.get(CONF_PROPOSALS_FROM, PROPOSALS_HA)
    target[CONF_AI_TASK] = user_input[CONF_AI_TASK]
    target[CONF_AI_SHOPPING] = user_input.get(CONF_AI_SHOPPING, True)
    target[CONF_AI_SEARCH] = user_input.get(CONF_AI_SEARCH, AI_NONE)
    choice = user_input.get("create_search_agent")
    if choice and choice != "no":
        entry = (hass.config_entries.async_get_entry(choice) if isinstance(choice, str)
                 else pick_entry(hass, user_input[CONF_AI_TASK]))
        if entry is not None:
            try:
                target[CONF_AI_SEARCH] = await async_create_agent(hass, entry)
            except HomeAssistantError:
                return {"base": "agent_failed"}
    return {}


def _display_schema(hass: HomeAssistant, mode: str, dashboard: str, style: str = "system") -> vol.Schema:
    from .frontend import dashboards

    boards = dashboards(hass)
    return vol.Schema({
        vol.Required(CONF_DISPLAY, default=mode): sel.SelectSelector(sel.SelectSelectorConfig(
            options=DISPLAYS, translation_key="display", mode=sel.SelectSelectorMode.LIST)),
        vol.Optional(CONF_DISPLAY_DASHBOARD, default=dashboard if dashboard in boards else boards[0]):
            sel.SelectSelector(sel.SelectSelectorConfig(options=boards, mode=sel.SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_DISPLAY_STYLE, default=style): sel.SelectSelector(sel.SelectSelectorConfig(
            options=STYLES, translation_key="style", mode=sel.SelectSelectorMode.LIST)),
    })


def _split_names(text: str | None) -> list[str]:
    return [p.strip() for p in (text or "").split(",") if p.strip()]


def _devices_schema(devices: list[str], custom: list[str]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_DEVICES, default=devices): sel.SelectSelector(
            sel.SelectSelectorConfig(
                options=DEVICES, multiple=True, mode=sel.SelectSelectorMode.LIST,
                translation_key="device",
            )
        ),
        vol.Optional(CONF_CUSTOM_DEVICES, default=", ".join(custom)): sel.TextSelector(),
    })


DOCS_URL = "https://github.com/Pare51984/ha-meal-planner-ai/blob/main/docs/"


class EssensplanerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ersteinrichtung: Einkaufsliste und Küchengeräte."""

    VERSION = 1

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        from .storage import LEGACY_DOMAIN

        if user_input is None and not getattr(self, "_legacy_asked", False) and \
                self.hass.config_entries.async_entries(LEGACY_DOMAIN):
            return await self.async_step_import_legacy()
        if user_input is not None:
            self._options[CONF_REGION] = user_input.get(CONF_REGION, default_region(self.hass.config.language))
            self._options[CONF_SHOPPING_LIST] = user_input[CONF_SHOPPING_LIST]
            return await self.async_step_devices()
        schema = vol.Schema({
            vol.Required(CONF_REGION, default=default_region(self.hass.config.language)): _region_selector(),
            **_list_schema(self.hass, None).schema,
        })
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_import_legacy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Frühere Integration „Essensplaner“ gefunden: Einstellungen übernehmen (Rezepte, Wünsche und Listen
        werden beim Start automatisch übernommen)."""
        from .storage import LEGACY_DOMAIN

        if user_input is not None:
            self._legacy_asked = True
            if user_input.get("import_settings", True):
                from homeassistant.config_entries import ConfigEntryDisabler

                old = self.hass.config_entries.async_entries(LEGACY_DOMAIN)[0]
                if old.disabled_by is None:
                    # alte Instanz abschalten, sonst planen beide und schreiben doppelt auf dieselbe Liste
                    await self.hass.config_entries.async_set_disabled_by(old.entry_id, ConfigEntryDisabler.USER)
                return self.async_create_entry(title="Meal Planner AI", data=dict(old.data),
                                               options=dict(old.options))
            return await self.async_step_user()
        return self.async_show_form(step_id="import_legacy", data_schema=vol.Schema({
            vol.Required("import_settings", default=True): sel.BooleanSelector()}))

    async def async_step_devices(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._options[CONF_DEVICES] = user_input[CONF_DEVICES]
            self._options[CONF_CUSTOM_DEVICES] = _split_names(user_input.get(CONF_CUSTOM_DEVICES))
            self._options[CONF_RECIPES_PER_WEEK] = DEFAULT_RECIPES_PER_WEEK
            return await self.async_step_ai()
        return self.async_show_form(
            step_id="devices", data_schema=_devices_schema([DEVICE_STOVE], [])
        )

    async def async_step_ai(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _apply_ai(self.hass, user_input, self._options)
            if not errors:
                return await self.async_step_display()
        return self.async_show_form(step_id="ai", data_schema=_ai_schema(self.hass, None, True), errors=errors)

    async def async_step_display(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._options[CONF_DISPLAY] = user_input[CONF_DISPLAY]
            self._options[CONF_DISPLAY_DASHBOARD] = user_input.get(CONF_DISPLAY_DASHBOARD, "lovelace")
            self._options[CONF_DISPLAY_STYLE] = user_input.get(CONF_DISPLAY_STYLE, "system")
            # Einkäufe in der Sprache der Instanz vorbelegen (Namen erscheinen als Knöpfe auf den Kacheln)
            self._options.setdefault(CONF_TRIPS, [
                {**trip, "name": ui(self.hass.config.language, "trip", i=i)} for i, trip in enumerate(DEFAULT_TRIPS, 1)])
            return self.async_create_entry(title="Meal Planner AI", data={}, options=self._options)
        return self.async_show_form(step_id="display", data_schema=_display_schema(self.hass, DISPLAY_PANEL, "lovelace"))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EssensplanerOptionsFlow()


class EssensplanerOptionsFlow(OptionsFlow):
    """Einstellungen: Einkaufsliste, Rezeptquellen, Ernährung, Küchengeräte."""

    def __init__(self) -> None:
        self._new: dict[str, Any] = {}
        self._clamped: list[str] = []

    @property
    def _opts(self) -> dict[str, Any]:
        return {**self.config_entry.options, **self._new}

    def _save(self) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **self._new})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["region", "schedule", "trips", "calendar", "rules", "habits", "diet_count", "shopping_list", "sources", "devices", "ai", "display"],
            # Link zur ausführlichen Anleitung (Adressen dürfen laut hassfest nicht im Übersetzungstext stehen)
            description_placeholders={"docs_url": DOCS_URL + ("anleitung.md" if self.hass.config.language == "de" else "guide.md")},
        )

    # --------------------------------------------------------- Einkaufsliste ---
    async def async_step_shopping_list(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        opts = self._opts
        if user_input is not None:
            self._new[CONF_SHOPPING_LIST] = user_input[CONF_SHOPPING_LIST]
            self._new[CONF_STAPLES] = user_input.get(CONF_STAPLES, "")
            self._new[CONF_SKIP_SPICES] = user_input.get(CONF_SKIP_SPICES, True)
            self._new[CONF_CATALOG] = user_input.get(CONF_CATALOG, "")
            return self._save()
        schema = _list_schema(self.hass, opts.get(CONF_SHOPPING_LIST)).extend({
            vol.Optional(CONF_STAPLES, default=opts.get(CONF_STAPLES, DEFAULT_STAPLES)): sel.TextSelector(
                sel.TextSelectorConfig(multiline=True)),
            vol.Optional(CONF_SKIP_SPICES, default=opts.get(CONF_SKIP_SPICES, True)): sel.BooleanSelector(),
            vol.Optional(CONF_CATALOG, default=opts.get(CONF_CATALOG, DEFAULT_CATALOG)): sel.TextSelector(
                sel.TextSelectorConfig(multiline=True)),
        })
        return self.async_show_form(step_id="shopping_list", data_schema=schema)

    # ------------------------------------------------------------ Zeitplan ---
    async def async_step_schedule(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        opts = {**DEFAULTS, **self._opts}
        if user_input is not None:
            for key in (CONF_PLAN_DAY, CONF_DEADLINE_DAY):
                self._new[key] = WEEKDAYS.index(user_input[key])
            for key in (CONF_PLAN_TIME, CONF_DEADLINE_TIME):
                self._new[key] = str(user_input[key])[:5]
            self._new[CONF_NOTIFY] = user_input.get(CONF_NOTIFY, [])
            self._new[CONF_DASHBOARD_PATH] = user_input.get(CONF_DASHBOARD_PATH, "")
            return self._save()
        day = sel.SelectSelector(sel.SelectSelectorConfig(
            options=WEEKDAYS, translation_key="weekday", mode=sel.SelectSelectorMode.DROPDOWN))
        notify = sorted(f"notify.{svc}" for svc in self.hass.services.async_services_for_domain("notify"))
        schema = vol.Schema({
            vol.Required(CONF_PLAN_DAY, default=WEEKDAYS[opts[CONF_PLAN_DAY]]): day,
            vol.Required(CONF_PLAN_TIME, default=f"{opts[CONF_PLAN_TIME]}:00"[:8]): sel.TimeSelector(),
            vol.Required(CONF_DEADLINE_DAY, default=WEEKDAYS[opts[CONF_DEADLINE_DAY]]): day,
            vol.Required(CONF_DEADLINE_TIME, default=f"{opts[CONF_DEADLINE_TIME]}:00"[:8]): sel.TimeSelector(),
            vol.Optional(CONF_NOTIFY, default=[n for n in opts[CONF_NOTIFY] if n in notify]): sel.SelectSelector(
                sel.SelectSelectorConfig(options=notify, multiple=True, mode=sel.SelectSelectorMode.DROPDOWN)),
            vol.Optional(CONF_DASHBOARD_PATH, default=opts[CONF_DASHBOARD_PATH]): sel.TextSelector(),
        })
        return self.async_show_form(step_id="schedule", data_schema=schema)

    # ------------------------------------------------------------ Einkäufe ---
    async def async_step_trips(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = settings_from_options(self._opts)[CONF_TRIPS]
        if user_input is not None:
            self._trip_count = int(user_input["count"])
            return await self.async_step_trip_details()
        return self.async_show_form(last_step=False, step_id="trips", data_schema=vol.Schema({
            vol.Required("count", default=str(len(current))): sel.SelectSelector(sel.SelectSelectorConfig(
                options=[str(i) for i in range(1, 8)], mode=sel.SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_trip_details(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = settings_from_options(self._opts)[CONF_TRIPS]
        count = getattr(self, "_trip_count", len(current))
        if user_input is not None:
            trips = []
            for i in range(1, count + 1):
                trip: dict[str, Any] = {
                    "name": str(user_input.get(f"name_{i}") or ui(self.hass.config.language, "trip", i=i)).strip(),
                    "release": user_input.get(f"release_{i}", RELEASE_IMMEDIATE),
                }
                trip["days"] = [WEEKDAYS.index(d) for d in user_input.get(f"days_{i}", [])]
                if trip["release"] == RELEASE_TIMED:
                    trip["weekday"] = WEEKDAYS.index(user_input.get(f"weekday_{i}", "mon"))
                    trip["time"] = str(user_input.get(f"time_{i}", "18:00:00"))[:5]
                trips.append(trip)
            self._new[CONF_TRIPS] = trips
            return self._save()
        day = sel.SelectSelector(sel.SelectSelectorConfig(
            options=WEEKDAYS, translation_key="weekday", mode=sel.SelectSelectorMode.DROPDOWN))
        days = sel.SelectSelector(sel.SelectSelectorConfig(
            options=WEEKDAYS, translation_key="weekday", multiple=True, mode=sel.SelectSelectorMode.DROPDOWN))
        release = sel.SelectSelector(sel.SelectSelectorConfig(
            options=[RELEASE_IMMEDIATE, RELEASE_TIMED], translation_key="release",
            mode=sel.SelectSelectorMode.DROPDOWN))
        schema: dict[Any, Any] = {}
        for i in range(1, count + 1):
            trip = current[i - 1] if i <= len(current) else {
                "name": ui(self.hass.config.language, "trip", i=i), "release": RELEASE_TIMED, "weekday": 0,
                "time": "18:00"}
            schema[vol.Required(f"name_{i}", default=trip["name"])] = sel.TextSelector()
            schema[vol.Optional(f"days_{i}", default=[WEEKDAYS[d] for d in trip.get("days") or []])] = days
            schema[vol.Required(f"release_{i}", default=trip["release"])] = release
            schema[vol.Optional(f"weekday_{i}", default=WEEKDAYS[trip.get("weekday") or 0])] = day
            schema[vol.Optional(f"time_{i}", default=f"{trip.get('time') or '18:00'}:00"[:8])] = sel.TimeSelector()
        return self.async_show_form(step_id="trip_details", data_schema=vol.Schema(schema))

    # ------------------------------------------------------------ Kalender ---
    async def async_step_calendar(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Bis zu drei Kalender-Regeln: welche Termine, was sie für die Planung bedeuten."""
        current = settings_from_options(self._opts)[CONF_CAL_RULES]
        if user_input is not None:
            rules = []
            for i in range(1, MAX_CAL_RULES + 1):
                cals = user_input.get(f"calendars_{i}") or []
                if not cals:
                    continue
                rules.append({
                    "label": str(user_input.get(f"label_{i}") or f"Termin {i}").strip(),
                    "calendars": cals,
                    "keyword": str(user_input.get(f"keyword_{i}") or "").strip(),
                    "hint": str(user_input.get(f"hint_{i}") or "").strip(),
                })
            self._new[CONF_CAL_RULES] = rules
            return self._save()
        schema: dict[Any, Any] = {}
        for i in range(1, MAX_CAL_RULES + 1):
            rule = current[i - 1] if i <= len(current) else {}
            schema[vol.Optional(f"label_{i}", description={"suggested_value": rule.get("label")})] = sel.TextSelector()
            schema[vol.Optional(f"calendars_{i}", default=rule.get("calendars", []))] = sel.EntitySelector(
                sel.EntitySelectorConfig(domain="calendar", multiple=True))
            schema[vol.Optional(f"keyword_{i}", description={"suggested_value": rule.get("keyword")})] = sel.TextSelector()
            schema[vol.Optional(f"hint_{i}", description={"suggested_value": rule.get("hint")})] = sel.TextSelector(
                sel.TextSelectorConfig(multiline=True))
        return self.async_show_form(step_id="calendar", data_schema=vol.Schema(schema))

    # ------------------------------------------------------------- Regeln ---
    async def async_step_rules(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        opts = {**DEFAULTS, **self._opts}
        n = int(opts.get(CONF_RECIPES_PER_WEEK, DEFAULT_RECIPES_PER_WEEK))
        if user_input is not None:
            for key in (CONF_PORTIONS, CONF_TIME_MAX, CONF_TIME_QUICK, CONF_QUICK_SHARE, CONF_MAX_SAME_MAIN):
                self._new[key] = int(user_input.get(key, 0))
            self._new[CONF_PROFILE] = user_input.get(CONF_PROFILE, "")
            self._new[CONF_KCAL_AWARE] = bool(user_input.get(CONF_KCAL_AWARE))
            if self._new[CONF_KCAL_AWARE]:
                return await self.async_step_rules_kcal()
            return self._save()

        def num(lo: int, hi: int, step: int = 1, unit: str | None = None) -> sel.NumberSelector:
            cfg: dict[str, Any] = {"min": lo, "max": hi, "step": step, "mode": sel.NumberSelectorMode.BOX}
            if unit:
                cfg["unit_of_measurement"] = unit
            return sel.NumberSelector(sel.NumberSelectorConfig(**cfg))

        schema = vol.Schema({
            vol.Required(CONF_PORTIONS, default=opts[CONF_PORTIONS]): num(1, 12),
            vol.Required(CONF_TIME_MAX, default=opts[CONF_TIME_MAX]): num(10, 300, 5, "min"),
            vol.Required(CONF_TIME_QUICK, default=opts[CONF_TIME_QUICK]): num(5, 300, 5, "min"),
            vol.Required(CONF_QUICK_SHARE, default=min(opts[CONF_QUICK_SHARE], n)): sel.NumberSelector(
                sel.NumberSelectorConfig(min=0, max=n, step=1, mode=sel.NumberSelectorMode.SLIDER)),
            vol.Required(CONF_MAX_SAME_MAIN, default=settings_from_options(self._opts)["max_same_main"]): sel.NumberSelector(
                sel.NumberSelectorConfig(min=0, max=n, step=1, mode=sel.NumberSelectorMode.SLIDER)),
            vol.Optional(CONF_KCAL_AWARE, default=settings_from_options(self._opts)["kcal_aware"]):
                sel.BooleanSelector(),
            vol.Optional(CONF_PROFILE, default=opts[CONF_PROFILE]): sel.TextSelector(
                sel.TextSelectorConfig(multiline=True)),
        })
        return self.async_show_form(step_id="rules", data_schema=schema,
                                    description_placeholders={"recipes": str(n)})

    async def async_step_rules_kcal(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Nur bei "kalorienbewusst": kcal-Grenzen (leer = keine Grenze)."""
        opts = self._opts
        if user_input is not None:
            for key in (CONF_KCAL_MAX, CONF_KCAL_MAX_NO_SIDE):
                kcal = user_input.get(key)
                self._new[key] = int(kcal) if kcal else None
            return self._save()
        kcal = sel.NumberSelector(sel.NumberSelectorConfig(
            min=100, max=3000, step=10, unit_of_measurement="kcal", mode=sel.NumberSelectorMode.BOX))
        return self.async_show_form(step_id="rules_kcal", data_schema=vol.Schema({
            vol.Optional(CONF_KCAL_MAX, description={"suggested_value": opts.get(CONF_KCAL_MAX)}): kcal,
            vol.Optional(CONF_KCAL_MAX_NO_SIDE, description={"suggested_value": opts.get(CONF_KCAL_MAX_NO_SIDE)}): kcal,
        }))

    # ---------------------------------------------------------------- Region ---
    async def async_step_region(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._new[CONF_REGION] = user_input[CONF_REGION]
            return self._save()
        current = self._opts.get(CONF_REGION) or "de"
        return self.async_show_form(step_id="region", data_schema=vol.Schema({
            vol.Required(CONF_REGION, default=current): _region_selector()}))

    # ------------------------------------------------------- Essgewohnheiten ---
    async def async_step_habits(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._new[CONF_HABITS] = [str(user_input.get(f"habit_{i}") or "").strip()
                                      for i in range(1, MAX_HABITS + 1)]
            self._new[CONF_HABITS] = [h for h in self._new[CONF_HABITS] if h]
            return self._save()
        current = habits_from_options(self._opts)
        schema = {
            vol.Optional(f"habit_{i}", description={"suggested_value": current[i - 1] if i <= len(current) else None}):
                sel.TextSelector()
            for i in range(1, MAX_HABITS + 1)
        }
        return self.async_show_form(step_id="habits", data_schema=vol.Schema(schema))

    # --------------------------------------------------------- Rezeptquellen ---
    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        settings = settings_from_options(self._opts)
        has_tm = DEVICE_THERMOMIX in settings[CONF_DEVICES]
        # nur die Seiten der eingestellten Region
        visible = [d for d in settings[CONF_SOURCES] if has_tm or not PRESET_SOURCES[d][1]]
        custom: list[str] = list(settings[CONF_CUSTOM_SOURCES])
        hidden: list[str] = list(settings[CONF_HIDDEN_SOURCES])
        errors: dict[str, str] = {}
        placeholders = {"error": "", "thermomix_note": "" if has_tm else
                        "Thermomix-Seiten sind ausgeblendet, weil kein Thermomix angehakt ist."}

        if user_input is not None:
            stored = dict(self._opts.get(CONF_SOURCES, {}))
            for domain in visible:
                stored[domain] = bool(user_input.get(_site_key(domain)))
            remove = set(user_input.get("remove_custom") or [])
            custom = [c for c in custom if c not in remove]
            # mitgelieferte Seiten werden nur ausgeblendet, damit man sie wiederherstellen kann
            restore = set(user_input.get("restore_sources") or [])
            hidden = [h for h in hidden if h not in restore] + sorted(
                d for d in remove if d in PRESET_SOURCES and d not in hidden)
            for domain in remove & set(PRESET_SOURCES):
                stored.pop(domain, None)
            for domain in restore:
                stored[domain] = True
            new_url = (user_input.get("new_source_url") or "").strip()
            if new_url:
                from .services import fetch_recipe

                try:
                    recipe = await fetch_recipe(self.hass, new_url)
                except HomeAssistantError as err:
                    errors["new_source_url"] = "test_failed"
                    placeholders["error"] = str(err)
                else:
                    domain = (urlparse(new_url).hostname or "").removeprefix("www.")
                    if domain and domain not in custom and domain not in PRESET_SOURCES:
                        custom.append(domain)
                    elif domain in PRESET_SOURCES:
                        stored[domain] = True
                        hidden = [h for h in hidden if h != domain]
                    placeholders["error"] = f"Test ok: {recipe.get('title')}"
            if not errors:
                self._new[CONF_SOURCES] = stored
                self._new[CONF_CUSTOM_SOURCES] = custom
                self._new[CONF_HIDDEN_SOURCES] = hidden
                return self._save()

        schema: dict[Any, Any] = {}
        for domain in visible:
            schema[vol.Optional(_site_key(domain), default=settings[CONF_SOURCES][domain])] = sel.BooleanSelector()
        removable = visible + custom  # mitgelieferte und eigene Seiten lassen sich entfernen
        if removable:
            schema[vol.Optional("remove_custom", default=[])] = sel.SelectSelector(
                sel.SelectSelectorConfig(options=removable, multiple=True, mode=sel.SelectSelectorMode.LIST)
            )
        if hidden:
            schema[vol.Optional("restore_sources", default=[])] = sel.SelectSelector(
                sel.SelectSelectorConfig(options=hidden, multiple=True, mode=sel.SelectSelectorMode.LIST)
            )
        schema[vol.Optional("new_source_url")] = sel.TextSelector(
            sel.TextSelectorConfig(type=sel.TextSelectorType.URL)
        )
        placeholders["custom"] = ", ".join(custom) if custom else "keine"
        return self.async_show_form(
            step_id="sources", data_schema=vol.Schema(schema), errors=errors,
            description_placeholders=placeholders,
        )

    # ------------------------------------------------------------- Ernährung ---
    async def async_step_diet_count(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            n = int(user_input[CONF_RECIPES_PER_WEEK])
            self._new[CONF_RECIPES_PER_WEEK] = n
            diet = {k: dict(v) for k, v in self._opts.get(CONF_DIET, {}).items()}
            self._clamped = []
            for key, rule in diet.items():
                if rule.get("count", 0) > n:
                    self._clamped.append(f"{key}: {rule['count']} → {n}")
                    rule["count"] = n
            counts = {k: int(v) for k, v in self._opts.get(CONF_DEVICE_COUNTS, {}).items()}
            for key, value in counts.items():
                if value > n:
                    self._clamped.append(f"{key}: {value} → {n}")
                    counts[key] = n
            self._new[CONF_DIET] = diet
            self._new[CONF_DEVICE_COUNTS] = counts
            return await self.async_step_diet()
        current = int(self._opts.get(CONF_RECIPES_PER_WEEK, DEFAULT_RECIPES_PER_WEEK))
        return self.async_show_form(last_step=False,
            step_id="diet_count",
            data_schema=vol.Schema({
                vol.Required(CONF_RECIPES_PER_WEEK, default=current): sel.NumberSelector(
                    sel.NumberSelectorConfig(min=1, max=21, step=1, mode=sel.NumberSelectorMode.SLIDER)
                )
            }),
        )

    async def async_step_diet(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        n = int(self._opts.get(CONF_RECIPES_PER_WEEK, DEFAULT_RECIPES_PER_WEEK))
        settings = settings_from_options(self._opts)
        errors: dict[str, str] = {}
        if user_input is not None:
            diet: dict[str, dict[str, Any]] = {}
            for key in DIETS:
                mode = user_input.get(f"{key}_mode", MODE_OFF)
                count = int(user_input.get(f"{key}_count", 0))
                if mode == MODE_COUNT and count == 0:
                    errors[f"{key}_count"] = "count_zero"
                diet[key] = {"mode": mode, "count": count if mode == MODE_COUNT else 0}
            if not errors:
                self._new[CONF_DIET] = diet
                if overlap_needed(diet, n) > 0:
                    return await self.async_step_diet_overlap()
                return self._save()

        schema: dict[Any, Any] = {}
        for key in DIETS:
            rule = settings[CONF_DIET][key]
            schema[vol.Required(f"{key}_mode", default=rule["mode"])] = sel.SelectSelector(
                sel.SelectSelectorConfig(options=DIET_MODES, translation_key="diet_mode",
                                         mode=sel.SelectSelectorMode.DROPDOWN)
            )
            schema[vol.Optional(f"{key}_count", default=min(rule["count"], n))] = sel.NumberSelector(
                sel.NumberSelectorConfig(min=0, max=n, step=1, mode=sel.NumberSelectorMode.SLIDER)
            )
        return self.async_show_form(
            step_id="diet", data_schema=vol.Schema(schema), errors=errors,
            description_placeholders={
                "recipes": str(n),
                "clamped": ("Angepasst, weil die Rezeptzahl gesunken ist: " + "; ".join(self._clamped))
                if self._clamped else "",
            },
        )

    async def async_step_diet_overlap(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        n = int(self._opts.get(CONF_RECIPES_PER_WEEK, DEFAULT_RECIPES_PER_WEEK))
        if user_input is not None:
            return self._save()
        return self.async_show_form(
            step_id="diet_overlap", data_schema=vol.Schema({}),
            description_placeholders={
                "overlap": str(overlap_needed(self._new[CONF_DIET], n)), "recipes": str(n)
            },
        )

    # -------------------------------------------------------------- Anzeige ---
    async def async_step_display(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._new[CONF_DISPLAY] = user_input[CONF_DISPLAY]
            self._new[CONF_DISPLAY_DASHBOARD] = user_input.get(CONF_DISPLAY_DASHBOARD, "lovelace")
            self._new[CONF_DISPLAY_STYLE] = user_input.get(CONF_DISPLAY_STYLE, "system")
            return self._save()
        opts = {**DEFAULTS, **self._opts}
        return self.async_show_form(step_id="display", data_schema=_display_schema(
            self.hass, opts[CONF_DISPLAY], opts[CONF_DISPLAY_DASHBOARD], opts[CONF_DISPLAY_STYLE]))

    # ------------------------------------------------------------------- KI ---
    async def async_step_ai(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _apply_ai(self.hass, user_input, self._new)
            if not errors:
                return self._save()
        return self.async_show_form(
            step_id="ai", errors=errors,
            data_schema=_ai_schema(self.hass, self._opts.get(CONF_AI_TASK, AI_NONE),
                                   bool(self._opts.get(CONF_AI_SHOPPING, True)),
                                   self._opts.get(CONF_AI_SEARCH, AI_NONE),
                                   self._opts.get(CONF_PROPOSALS_FROM, PROPOSALS_HA)),
        )

    # ----------------------------------------------------------- Küchengeräte ---
    async def async_step_devices(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        settings = settings_from_options(self._opts)
        if user_input is not None:
            self._new[CONF_DEVICES] = user_input[CONF_DEVICES]
            self._new[CONF_CUSTOM_DEVICES] = _split_names(user_input.get(CONF_CUSTOM_DEVICES))
            return await self.async_step_device_counts()
        return self.async_show_form(last_step=False,
            step_id="devices",
            data_schema=_devices_schema(settings[CONF_DEVICES], settings[CONF_CUSTOM_DEVICES]),
        )

    async def async_step_device_counts(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        n = int(self._opts.get(CONF_RECIPES_PER_WEEK, DEFAULT_RECIPES_PER_WEEK))
        owned = [d for d in self._new[CONF_DEVICES] if d != DEVICE_STOVE] + self._new[CONF_CUSTOM_DEVICES]
        current = {k: int(v) for k, v in self._opts.get(CONF_DEVICE_COUNTS, {}).items()}
        if user_input is not None or not owned:
            counts = {}
            for dev in owned:
                key = f"count_{dev}" if dev in DEVICES else dev
                value = int((user_input or {}).get(key, 0))
                if value:
                    counts[dev] = value
            self._new[CONF_DEVICE_COUNTS] = counts
            return self._save()
        schema: dict[Any, Any] = {}
        for dev in owned:
            key = f"count_{dev}" if dev in DEVICES else dev
            schema[vol.Optional(key, default=min(current.get(dev, 0), n))] = sel.NumberSelector(
                sel.NumberSelectorConfig(min=0, max=n, step=1, mode=sel.NumberSelectorMode.SLIDER)
            )
        return self.async_show_form(
            step_id="device_counts", data_schema=vol.Schema(schema),
            description_placeholders={"recipes": str(n)},
        )
