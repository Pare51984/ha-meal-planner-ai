"""Such-Agenten automatisch anlegen: ein Gesprächsagent mit Websuche in der KI-Integration des Nutzers.

Google Gemini: live geprüft (Option "Google Search tool", nur ohne KI-Werkzeuge nutzbar).
Claude (Anthropic) und ChatGPT (OpenAI): Optionsnamen aus dem Home-Assistant-Quellcode (Stand 11/2026),
noch nicht live geprüft.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import AI_NONE

_LOGGER = logging.getLogger(__name__)

AGENT_TITLE = "Essensplaner Rezeptsuche"
# Anzeigename je Anbieter, damit in der Auswahl erkennbar ist, welcher Agent welcher ist
PROVIDER_NAMES = {"google_generative_ai_conversation": "Gemini", "anthropic": "Claude", "openai_conversation": "ChatGPT"}


def agent_title(domain: str) -> str:
    name = PROVIDER_NAMES.get(domain)
    return f"{AGENT_TITLE} ({name})" if name else AGENT_TITLE
AGENT_PROMPT = (
    "Du recherchierst Rezepte mit der Websuche. Nutze nur Links, die du in den Suchergebnissen gefunden hast, "
    "und antworte ausschließlich im verlangten JSON-Format."
)
# Domain -> Werte für den Gesprächsagenten (nur Felder, die das Formular kennt, werden gesendet)
PROVIDERS: dict[str, dict[str, Any]] = {
    "google_generative_ai_conversation": {
        "recommended": False,
        "llm_hass_api": [],
        "enable_google_search_tool": True,
        # Gemini denkt vor der Antwort; das zählt mit zum Limit (8000 brach am 08.11.2026 ab).
        # Für alle Anbieter gleich: 16000 Tokens und je ein aktuelles, günstiges Modell (faire Wahl)
        "max_tokens": 16000,
        "thinking_budget": 4096,
        # 08.11.2026: mit 3.1 Flash Lite lehnte Google die Suche im kostenlosen Tarif ab (429), 2.5 Flash ging;
        # 11.11.2026: 3.8 Flash sucht im kostenlosen Tarif problemlos (Live-Betrieb)
        "chat_model": "models/gemini-3.8-flash",
    },
    "anthropic": {
        "recommended": False,
        "llm_hass_api": [],
        "web_search": True,
        "web_search_max_uses": 15,
        "user_location": False,
        "max_tokens": 16000,
        "chat_model": "claude-haiku-5-5",  # 11.11.2026 live geprüft: 10 Gerichte
    },
    "openai_conversation": {
        "recommended": False,
        "llm_hass_api": [],
        "web_search": True,
        "search_context_size": "medium",
        "user_location": False,
        "max_tokens": 16000,
        "chat_model": "gpt-6.1-terra",  # 10.11.2026 live geprüft: 10 Gerichte, meiste Links selbst
    },
}
AUTO_PREFIX = "auto:"


def provider_entries(hass: HomeAssistant) -> list[Any]:
    """Geladene KI-Integrationen, bei denen der Essensplaner einen Such-Agenten anlegen kann."""
    return [e for domain in PROVIDERS for e in hass.config_entries.async_entries(domain)
            if e.state is ConfigEntryState.LOADED]


def _existing(entry: Any) -> str | None:
    for sub in entry.subentries.values():
        # auch der alte Name ohne Anbieter gilt, damit bestehende Agenten nicht doppelt angelegt werden
        if sub.subentry_type == "conversation" and sub.title in (AGENT_TITLE, agent_title(entry.domain)):
            return sub.subentry_id
    return None


def has_agent(hass: HomeAssistant) -> bool:
    return any(_existing(e) for e in provider_entries(hass))


def pick_entry(hass: HomeAssistant, ai_task: str | None) -> Any | None:
    """Bevorzugt die Integration, zu der die gewählte AI-Task-Entität gehört."""
    entries = provider_entries(hass)
    if ai_task and ai_task != AI_NONE:
        reg_entry = er.async_get(hass).async_get(ai_task)
        for entry in entries:
            if reg_entry and reg_entry.config_entry_id == entry.entry_id:
                return entry
    return entries[0] if entries else None


async def async_create_agent(hass: HomeAssistant, entry: Any) -> str:
    """Gesprächsagenten mit Websuche anlegen (oder vorhandenen nehmen). Liefert einen auto:-Verweis."""
    sub_id = _existing(entry)
    if sub_id:
        return f"{AUTO_PREFIX}{entry.entry_id}:{sub_id}"
    data = {"name": agent_title(entry.domain), "prompt": AGENT_PROMPT, **PROVIDERS[entry.domain]}
    manager = hass.config_entries.subentries
    try:
        result = await manager.async_init((entry.entry_id, "conversation"), context={"source": SOURCE_USER})
        for _ in range(6):  # nach "recommended: aus" folgen je Anbieter ein bis drei weitere Formulare
            if result["type"] is FlowResultType.CREATE_ENTRY:
                break
            if result["type"] is not FlowResultType.FORM:
                raise HomeAssistantError(f"Agent nicht angelegt: {result.get('reason') or result['type']}")
            keys = {str(k) for k in result["data_schema"].schema} if result.get("data_schema") else set()
            result = await manager.async_configure(result["flow_id"], {k: v for k, v in data.items() if k in keys})
        else:
            raise HomeAssistantError("Agent nicht angelegt: Formular wurde nicht abgeschlossen")
    except HomeAssistantError:
        raise
    except Exception as err:  # noqa: BLE001 - fremde Integration, Formulare können sich ändern
        raise HomeAssistantError(f"Agent nicht angelegt: {err}") from err
    sub_id = _existing(hass.config_entries.async_get_entry(entry.entry_id) or entry)
    if not sub_id:
        raise HomeAssistantError("Agent nicht angelegt: nicht gefunden")
    _LOGGER.info("Such-Agent %s in %s angelegt", agent_title(entry.domain), entry.title)
    return f"{AUTO_PREFIX}{entry.entry_id}:{sub_id}"


def resolve_agent(hass: HomeAssistant, value: str | None) -> str | None:
    """auto:-Verweis in die Entitäts-ID des Gesprächsagenten auflösen (die Entität entsteht erst nach dem Laden)."""
    if not value or value == AI_NONE:
        return None
    if not value.startswith(AUTO_PREFIX):
        return value
    entry_id, _, sub_id = value[len(AUTO_PREFIX):].partition(":")
    for reg in er.async_entries_for_config_entry(er.async_get(hass), entry_id):
        if reg.domain == "conversation" and getattr(reg, "config_subentry_id", None) == sub_id:
            return reg.entity_id
    return None


def web_search_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Hat dieser Gesprächsagent die Websuche eingeschaltet (Gemini: Google-Suche, Claude/ChatGPT: web_search)?"""
    reg = er.async_get(hass).async_get(entity_id)
    if not reg or not reg.config_entry_id:
        return False
    entry = hass.config_entries.async_get_entry(reg.config_entry_id)
    sub = entry and getattr(entry, "subentries", {}).get(getattr(reg, "config_subentry_id", None) or "")
    data = {**(entry.options if entry else {}), **(sub.data if sub else {})}
    return bool(data.get("enable_google_search_tool") or data.get("web_search"))
