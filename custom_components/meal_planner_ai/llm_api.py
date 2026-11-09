"""Werkzeug-Sammlung „Meal Planner AI“ für KIs (z. B. über die Integration „Model Context Protocol Server“).

Damit kann eine externe KI (geplante Aufgabe in Claude, ChatGPT …) den Planungsauftrag holen und Vorschläge
einreichen, ohne dass sie beliebige Aktionen in Home Assistant aufrufen darf. Es sind dieselben Abläufe wie bei
den Aktionen meal_planner_ai.planning_brief und meal_planner_ai.submit_proposals.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

API_ID = "meal_planner_ai"
API_NAME = "Meal Planner AI"
API_PROMPT = (
    "Bittet dich der Nutzer, den Essensplaner einzurichten, rufe meal_planner_setup auf und folge "
    "instructions_for_ai. "
    "Mit diesen Werkzeugen planst du die Wochengerichte des Essensplaners: zuerst meal_planner_planning_brief "
    "aufrufen; ist due false, ist nichts zu tun. Sonst den Auftrag im Feld prompt befolgen, Rezepte im Web suchen "
    "und mit meal_planner_submit_proposals einreichen, bis need 0 ist (höchstens viermal, zuletzt final: true)."
)


def _planner(hass: HomeAssistant) -> Any:
    from .services import _entry

    return _entry(hass).runtime_data.planner


class PlanningBriefTool(llm.Tool):
    name = "meal_planner_planning_brief"
    description = (
        "Planungsauftrag für die kommende Woche holen: due (ist gerade etwas zu tun), need (wie viele Gerichte "
        "fehlen) und prompt (Regeln, Wünsche, Termine, Antwortformat)."
    )
    parameters = vol.Schema({
        vol.Optional("notes", description="Zusätzliche Hinweise nur für diese Woche"): str,
        vol.Optional("restart", description="Vorhandene Vorschläge ignorieren und neu beginnen"): bool,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> JsonObjectType:
        args = tool_input.tool_args
        return await _planner(hass).async_planning_brief(args.get("notes"), bool(args.get("restart")))


class SubmitProposalsTool(llm.Tool):
    name = "meal_planner_submit_proposals"
    description = (
        "Gerichte einreichen (Format wie im Auftrag: title, url, query, site, tip, wish, …). Der Essensplaner prüft "
        "Link und Regeln und antwortet mit accepted, rejected, need, deficits und problems."
    )
    parameters = vol.Schema({
        vol.Required("dishes", description="Liste der Gerichte"): [dict],
        vol.Optional("final", description="Letzter Aufruf: danach melden, auch wenn etwas fehlt"): bool,
        vol.Optional("restart", description="Vorhandene Vorschläge der Woche ersetzen"): bool,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> JsonObjectType:
        from .services import _dish_list

        args = tool_input.tool_args
        return await _planner(hass).async_submit_proposals(
            _dish_list(args.get("dishes", [])), final=bool(args.get("final")), restart=bool(args.get("restart")))


class SetupTool(llm.Tool):
    name = "meal_planner_setup"
    description = (
        "Einrichtung der externen KI: Aufrufen, wenn der Nutzer sagt „Richte meinen Essensplaner ein“. Liefert "
        "instructions_for_ai (was du jetzt tun sollst), Zeitplan und task_text für eine geplante Aufgabe in deinem "
        "System. activate: true stellt den Essensplaner auf externe KI um."
    )
    parameters = vol.Schema({
        vol.Optional("activate", description="Essensplaner auf externe KI umstellen"): bool,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> JsonObjectType:
        from .services import async_external_setup

        return await async_external_setup(hass, bool(tool_input.tool_args.get("activate")))


class EssensplanerAPI(llm.API):
    """Nur die beiden Werkzeuge zum Planen, sonst kein Zugriff auf Home Assistant."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.id = API_ID
        self.name = API_NAME

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        return llm.APIInstance(api=self, api_prompt=API_PROMPT, llm_context=llm_context,
                               tools=[SetupTool(), PlanningBriefTool(), SubmitProposalsTool()])


def async_register(hass: HomeAssistant) -> Any:
    """Werkzeug-Sammlung anmelden; liefert die Abmeldefunktion."""
    return llm.async_register_api(hass, EssensplanerAPI(hass))
