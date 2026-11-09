"""Aktionen des Essensplaners (alle mit Antwortdaten für Claude / Automationen)."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Any

import aiohttp
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .ai import AIError, assess_prompt, async_ask
from .const import (
    CHOICES,
    TRIP_KEYS,
    CONF_AI_TASK,
    CONF_SHOPPING_LIST,
    DIETS,
    DOMAIN,
    FETCH_TIMEOUT,
    MAX_HTML_BYTES,
    OWN_LIST,
    RATING_MAX,
    RATING_MIN,
    STATUS_BOUGHT,
    STATUSES,
    USER_AGENT,
)
from .planning import evaluate_recipe, planner_brief, settings_from_options, validate_plan
from .shopping import async_add_items
from .storage import RecipeStore

OWN_LIST_ENTITY_UNIQUE = "_shopping_list"


@dataclass
class EssensplanerData:
    """Laufzeitdaten am Config Entry."""

    store: RecipeStore
    platforms: list[str]
    planner: Any = None
    options: dict[str, Any] | None = None  # Stand beim Laden, um reine Profiländerungen zu erkennen


type EssensplanerConfigEntry = ConfigEntry[EssensplanerData]


# ------------------------------------------------------------------ Hilfen ---

def _entry(hass: HomeAssistant) -> EssensplanerConfigEntry:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry
    raise ServiceValidationError(
        "Der Essensplaner ist noch nicht eingerichtet (Geräte & Dienste → Integration hinzufügen)."
    )


def _settings(entry: EssensplanerConfigEntry) -> dict[str, Any]:
    return settings_from_options({**entry.data, **entry.options})


class RecipeFetchError(HomeAssistantError):
    """Rezeptseite nicht erreichbar oder antwortet mit Fehler (Seite existiert evtl. nicht)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RecipeParseError(HomeAssistantError):
    """Seite geladen, aber kein Rezept darin lesbar."""


MAX_REDIRECTS = 5


async def _resolve(hass: HomeAssistant, host: str) -> list[str]:
    """Alle Adressen eines Hostnamens (eigene Funktion, damit Tests sie ersetzen können)."""
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


async def _check_public(hass: HomeAssistant, url: URL) -> None:
    """Nur öffentliche http(s)-Adressen abrufen, nie das Heimnetz, HA selbst oder den Supervisor."""
    if url.scheme not in ("http", "https") or not url.host:
        raise RecipeFetchError(f"Adresse nicht erlaubt: {url.scheme or '?'}://{url.host or ''}")
    try:
        addresses = [url.host] if _is_ip(url.host) else await _resolve(hass, url.host)
    except OSError as err:
        raise RecipeFetchError(f"Rezeptseite nicht erreichbar: {url.host} ({err})") from err
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise RecipeFetchError(f"Adresse nicht erlaubt: {url.host} zeigt ins lokale Netz")


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


async def fetch_html(hass: HomeAssistant, url: str) -> tuple[str, str]:
    """Seite laden und Weiterleitungen (z. B. share.google) selbst folgen; jeder Schritt wird geprüft."""
    session = async_get_clientsession(hass)
    current = URL(url)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            await _check_public(hass, current)
            async with session.get(
                current,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9,en;q=0.5"},
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT),
            ) as resp:
                if resp.status in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                    current = current.join(URL(resp.headers["Location"]))
                    continue
                if resp.status != 200:
                    raise RecipeFetchError(
                        f"Rezeptseite antwortet mit HTTP {resp.status} ({current.host}).", resp.status)
                # read(n) liefert nur, was gerade im Puffer liegt; große Seiten (Chefkoch) daher bis zum Ende lesen
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= MAX_HTML_BYTES:
                        break
                raw = b"".join(chunks)
                return raw.decode(resp.charset or "utf-8", errors="replace"), str(current)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        raise RecipeFetchError(f"Rezeptseite nicht erreichbar: {err}") from err
    raise RecipeFetchError(f"Zu viele Weiterleitungen ({current.host}).")


async def fetch_recipe(hass: HomeAssistant, url: str) -> dict[str, Any]:
    from .parser import parse_recipe  # Bibliothek erst bei Bedarf laden

    html, final_url = await fetch_html(hass, url)
    try:
        return await hass.async_add_executor_job(parse_recipe, html, final_url)
    except ValueError as err:
        raise RecipeParseError(str(err)) from err
    except Exception as err:  # noqa: BLE001 - Fremdbibliothek, jede Seite ist anders
        raise RecipeParseError(f"Rezept konnte nicht gelesen werden: {err}") from err


def _with_checks(recipe: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    return {**recipe, "checks": evaluate_recipe(recipe, settings)}


def _summary(recipe: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    ev = evaluate_recipe(recipe, settings)
    return {
        "id": recipe["id"],
        "title": recipe.get("title"),
        "host": recipe.get("host"),
        "source_url": recipe.get("source_url"),
        "kcal_per_serving": recipe.get("kcal_per_serving"),
        "total_time_min": recipe.get("total_time_min"),
        "rating": ev["rating"],
        "status": ev["status"],
        "last_cooked": ev["last_cooked"],
        "times_cooked": ev["times_cooked"],
        "diet": ev["diet"],
        "feasible": ev["feasible"],
        "stub": recipe.get("stub", False),
    }


def _find(store: RecipeStore, data: dict[str, Any]) -> dict[str, Any] | None:
    return store.find(
        recipe_id=data.get("recipe_id"), url=data.get("url"), title=data.get("title")
    )


def _require(store: RecipeStore, data: dict[str, Any]) -> dict[str, Any]:
    recipe = _find(store, data)
    if recipe is None:
        raise ServiceValidationError("Rezept nicht gefunden (recipe_id, url oder title prüfen).")
    return recipe


def _list_entity(hass: HomeAssistant, entry: EssensplanerConfigEntry) -> str:
    target = _settings(entry)[CONF_SHOPPING_LIST]
    if target == OWN_LIST or not target:
        from homeassistant.helpers import entity_registry as er

        ent = er.async_get(hass).async_get_entity_id(
            "todo", DOMAIN, f"{entry.entry_id}{OWN_LIST_ENTITY_UNIQUE}"
        )
        if ent is None:
            raise HomeAssistantError("Die eigene Einkaufsliste des Essensplaners fehlt.")
        return ent
    return target


# ------------------------------------------------------------------ Schemas ---

_SELECT = {
    vol.Optional("recipe_id"): cv.string,
    vol.Optional("url"): cv.url,
    vol.Optional("title"): cv.string,
}
_HAS_REF = cv.has_at_least_one_key("recipe_id", "url", "title")

IMPORT_SCHEMA = vol.Schema({vol.Required("url"): cv.url, vol.Optional("save", default=True): cv.boolean})
GET_SCHEMA = vol.All(vol.Schema(_SELECT), _HAS_REF)
LIST_SCHEMA = vol.Schema({
    vol.Optional("query"): cv.string,
    vol.Optional("status"): vol.In(STATUSES),
    vol.Optional("min_rating"): vol.All(vol.Coerce(int), vol.Range(RATING_MIN, RATING_MAX)),
    vol.Optional("limit", default=100): vol.All(vol.Coerce(int), vol.Range(1, 1000)),
})
DELETE_SCHEMA = vol.Schema({vol.Required("recipe_id"): cv.string})
SHOP_SCHEMA = vol.All(vol.Schema({
    **_SELECT,
    vol.Optional("servings"): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=50)),
    vol.Optional("force", default=False): cv.boolean,
}), _HAS_REF)
HISTORY_SCHEMA = vol.All(vol.Schema({
    **_SELECT,
    vol.Optional("rating"): vol.All(vol.Coerce(int), vol.Range(0, RATING_MAX)),  # 0 = entfernen
    vol.Optional("cooked_on"): cv.date,
    vol.Optional("remove_cooked_on"): cv.date,
    vol.Optional("status"): vol.In(STATUSES),
    vol.Optional("note"): vol.Any(cv.string, None),
}), _HAS_REF)
_HISTORY_ENTRY = vol.Schema({
    vol.Required("title"): cv.string,
    vol.Optional("url"): cv.url,
    vol.Optional("rating"): vol.All(vol.Coerce(int), vol.Range(RATING_MIN, RATING_MAX)),
    vol.Optional("cooked_on"): vol.All(cv.ensure_list, [cv.date]),
    vol.Optional("status"): vol.In(STATUSES),
    vol.Optional("note"): cv.string,
}, extra=vol.REMOVE_EXTRA)
IMPORT_HISTORY_SCHEMA = vol.Schema({
    vol.Required("entries"): vol.All(cv.ensure_list, [_HISTORY_ENTRY]),
    vol.Optional("fetch_recipes", default=False): cv.boolean,
})
ASSESS_SCHEMA = vol.Schema({
    vol.Optional("recipe_ids"): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("keys"): vol.All(cv.ensure_list, [vol.In(DIETS)]),
    vol.Optional("force", default=False): cv.boolean,
})
GENERATE_SCHEMA = vol.Schema({
    vol.Optional("notes"): cv.string,
    vol.Optional("force", default=False): cv.boolean,
})
DISH_SCHEMA = vol.Schema({vol.Required("dish_id"): cv.string})
ITEMS_SCHEMA = vol.Schema({
    vol.Required("dish_id"): cv.string,
    vol.Optional("items", default=[]): vol.All(cv.ensure_list, [cv.string]),
})
RELEASE_SCHEMA = vol.Schema({vol.Optional("trip"): vol.In(TRIP_KEYS)})
CHOOSE_SCHEMA = vol.Schema({
    vol.Required("dish_id"): cv.string,
    vol.Required("choice"): vol.In(CHOICES),
})
READY_SCHEMA = vol.Schema({
    vol.Required("dish_id"): cv.string,
    vol.Optional("ready", default=True): cv.boolean,
})
COOKED_SCHEMA = vol.Schema({
    vol.Required("dish_id"): cv.string,
    vol.Optional("cooked", default=True): cv.boolean,
    vol.Optional("rating"): vol.All(vol.Coerce(int), vol.Range(RATING_MIN, RATING_MAX)),
    vol.Optional("note"): cv.string,
})
PLAN_SCHEMA = vol.Schema({
    vol.Optional("recipe_ids", default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("urls", default=[]): vol.All(cv.ensure_list, [cv.url]),
})


# -------------------------------------------------------------- Handler ---

async def _import_recipe(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    entry = _entry(hass)
    recipe = await fetch_recipe(hass, call.data["url"])
    if call.data["save"]:
        recipe = entry.runtime_data.store.upsert(recipe, call.data["url"])
    return _with_checks(recipe, _settings(entry))


async def _get_recipe(call: ServiceCall) -> ServiceResponse:
    entry = _entry(call.hass)
    return _with_checks(_require(entry.runtime_data.store, call.data), _settings(entry))


async def _list_recipes(call: ServiceCall) -> ServiceResponse:
    entry = _entry(call.hass)
    settings = _settings(entry)
    query = (call.data.get("query") or "").lower()
    out = []
    for rec in entry.runtime_data.store.recipes.values():
        hist = rec.get("history") or {}
        if query and query not in (rec.get("title") or "").lower() and not any(
            query in i.lower() for i in rec.get("ingredients") or []
        ):
            continue
        if call.data.get("status") and hist.get("status") != call.data["status"]:
            continue
        if call.data.get("min_rating") and (hist.get("rating") or 0) < call.data["min_rating"]:
            continue
        out.append(_summary(rec, settings))
    out.sort(key=lambda r: (r["title"] or "").lower())
    return {"count": len(out), "recipes": out[: call.data["limit"]]}


async def _delete_recipe(call: ServiceCall) -> ServiceResponse:
    entry = _entry(call.hass)
    if not entry.runtime_data.store.delete(call.data["recipe_id"]):
        raise ServiceValidationError("Rezept nicht gefunden.")
    return {"deleted": call.data["recipe_id"]}


async def _add_to_shopping_list(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    entry = _entry(hass)
    store = entry.runtime_data.store
    recipe = _find(store, call.data)
    if recipe is None or recipe.get("stub"):
        if not call.data.get("url") and not (recipe and recipe.get("source_url")):
            raise ServiceValidationError("Rezept nicht gefunden; mit url wird es vorher importiert.")
        url = call.data.get("url") or recipe["source_url"]
        recipe = store.upsert(await fetch_recipe(hass, url), url)
    status = (recipe.get("history") or {}).get("status")
    if status == STATUS_BOUGHT and not call.data["force"]:
        return {
            "added": [],
            "skipped_reason": "already_bought",
            "message": f"'{recipe.get('title')}' wurde schon eingekauft und noch nicht gemacht; "
            "Zutaten nicht erneut hinzugefügt (force: true erzwingt es).",
            "recipe_id": recipe["id"],
        }
    settings = _settings(entry)
    portions = call.data.get("servings") or settings["portions"]
    items, staples = await entry.runtime_data.planner.async_recipe_items(recipe, portions)
    target = _list_entity(hass, entry)
    written = await async_add_items(hass, target, items, recipe.get("title") or recipe["id"])
    store.update_history(recipe["id"], status=STATUS_BOUGHT)
    fmt = lambda i: f"{i['name']} ({i['spec']})" if i["spec"] else i["name"]  # noqa: E731
    return {
        "recipe_id": recipe["id"],
        "title": recipe.get("title"),
        "list": target,
        "added": [fmt(i) for i in written if i["action"] == "added"],
        "merged": [fmt(i) for i in written if i["action"] in ("merged", "already")],
        "count": len(written),
        "skipped_staples": staples,
    }


async def _update_history(call: ServiceCall) -> ServiceResponse:
    entry = _entry(call.hass)
    store = entry.runtime_data.store
    recipe = _find(store, call.data)
    if recipe is None:
        if not call.data.get("title"):
            raise ServiceValidationError("Rezept nicht gefunden; für neue Einträge title angeben.")
        recipe = store.add_stub(call.data["title"], call.data.get("url"))
    rec = store.update_history(
        recipe["id"],
        rating=call.data.get("rating"),
        cooked_on=call.data.get("cooked_on"),
        status=call.data.get("status"),
        note=("" if call.data["note"] is None else call.data["note"]) if "note" in call.data else None,
        remove_cooked_on=call.data.get("remove_cooked_on"),
    )
    return {"recipe_id": rec["id"], "title": rec.get("title"), "history": rec["history"]}


async def _import_history(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    entry = _entry(hass)
    store = entry.runtime_data.store
    created = updated = 0
    failed: list[dict[str, str]] = []
    for item in call.data["entries"]:
        recipe = store.find(url=item.get("url"), title=item["title"])
        if recipe is None:
            if item.get("url") and call.data["fetch_recipes"]:
                try:
                    recipe = store.upsert(await fetch_recipe(hass, item["url"]), item["url"])
                except HomeAssistantError as err:
                    failed.append({"title": item["title"], "error": str(err)})
                    recipe = store.add_stub(item["title"], item["url"])
            else:
                recipe = store.add_stub(item["title"], item.get("url"))
            created += 1
        else:
            updated += 1
        for day in item.get("cooked_on") or []:
            store.update_history(recipe["id"], cooked_on=day)
        store.update_history(
            recipe["id"], rating=item.get("rating"), status=item.get("status"), note=item.get("note")
        )
    return {"created": created, "updated": updated, "fetch_errors": failed}


async def _validate_plan(call: ServiceCall) -> ServiceResponse:
    hass = call.hass
    entry = _entry(hass)
    store = entry.runtime_data.store
    recipes: list[dict[str, Any]] = []
    missing: list[str] = []
    for rid in call.data["recipe_ids"]:
        rec = store.get(rid)
        recipes.append(rec) if rec else missing.append(rid)
    for url in call.data["urls"]:
        rec = store.find(url=url)
        if rec is None:
            try:
                rec = store.upsert(await fetch_recipe(hass, url), url)
            except HomeAssistantError:
                missing.append(url)
                continue
        recipes.append(rec)
    result = validate_plan(recipes, _settings(entry), dt_util.now().date())
    if missing:
        result["ok"] = False
        result["violations"].append(f"Nicht gefunden: {', '.join(missing)}")
    return result


async def _get_settings(call: ServiceCall) -> ServiceResponse:
    entry = _entry(call.hass)
    settings = _settings(entry)
    return {"planner": planner_brief(settings), "settings": settings,
            "recipes_stored": len(entry.runtime_data.store.recipes),
            "board": entry.runtime_data.store.meta.get("board")}


def _ai_entity(entry: EssensplanerConfigEntry) -> str:
    ai = _settings(entry)[CONF_AI_TASK]
    if not ai:
        raise ServiceValidationError(
            "Keine KI ausgewählt. Im Essensplaner unter Konfigurieren → KI eine AI-Task-Entität "
            "(z. B. Claude, ChatGPT oder Gemini) wählen."
        )
    return ai


async def async_assess(
    hass: HomeAssistant, entry: EssensplanerConfigEntry, recipes: list[dict[str, Any]],
    keys: list[str] | None = None, force: bool = False,
) -> dict[str, Any]:
    """Unklare Ernährungs-Kriterien von der KI bewerten lassen und am Rezept speichern."""
    ai = _ai_entity(entry)
    store = entry.runtime_data.store
    settings = _settings(entry)
    wanted = keys or DIETS
    todo: list[tuple[dict[str, Any], list[str]]] = []
    for rec in recipes:
        if rec.get("stub") or not rec.get("ingredients"):
            continue
        diet = evaluate_recipe({**rec, "ai_diet": {} if force else rec.get("ai_diet")}, settings)["diet"]
        missing = [k for k in wanted if diet[k] is None]
        if missing:
            todo.append((rec, missing))
    results: dict[str, Any] = {}
    for start in range(0, len(todo), 6):
        batch = todo[start : start + 6]
        keys_needed = sorted({k for _, ks in batch for k in ks}, key=DIETS.index)
        answer = await async_ask(hass, ai, "Essensplaner Ernährung prüfen",
                                 assess_prompt([r for r, _ in batch], keys_needed))
        by_id = {str(x.get("id")): x for x in (answer.get("results") or [])} if isinstance(answer, dict) else {}
        for rec, ks in batch:
            got = by_id.get(rec["id"])
            if not got:
                continue
            ai_diet = {**(rec.get("ai_diet") or {})}
            for k in ks:
                if isinstance(got.get(k), bool):
                    ai_diet[k] = got[k]
            store.set_fields(rec["id"], ai_diet=ai_diet, ai_note=got.get("note"))
            results[rec["id"]] = {"title": rec.get("title"), **ai_diet, "note": got.get("note")}
    return results


async def _assess_recipes(call: ServiceCall) -> ServiceResponse:
    entry = _entry(call.hass)
    store = entry.runtime_data.store
    ids = call.data.get("recipe_ids") or list(store.recipes)
    recipes = [store.recipes[i] for i in ids if i in store.recipes]
    try:
        results = await async_assess(call.hass, entry, recipes, call.data.get("keys"), call.data["force"])
    except AIError as err:
        raise HomeAssistantError(str(err)) from err
    return {"assessed": len(results), "results": results}


def _planner(call: ServiceCall):  # noqa: ANN202
    return _entry(call.hass).runtime_data.planner


SEARCH_SCHEMA = vol.Schema({vol.Required("query"): cv.string, vol.Optional("sites"): [cv.string]})


async def _search_recipes(call: ServiceCall) -> ServiceResponse:
    """Eigene Rezeptsuche ausprobieren: je Seite Suchadresse und gefundene Rezeptlinks."""
    from .planning import enabled_sources
    from .search import async_search_report

    planner = _planner(call)
    hosts = call.data.get("sites") or enabled_sources(planner.settings)
    return {"results": await async_search_report(call.hass, hosts, call.data["query"], planner._local_locale())}


async def _generate_proposals(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_generate(call.data.get("notes"), call.data["force"])


BRIEF_SCHEMA = vol.Schema({
    vol.Optional("notes"): cv.string,
    vol.Optional("restart", default=False): cv.boolean,
})
SUBMIT_SCHEMA = vol.Schema({
    vol.Required("dishes"): vol.Any(list, dict, cv.string),
    vol.Optional("final", default=False): cv.boolean,
    vol.Optional("restart", default=False): cv.boolean,
})


async def _planning_brief(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_planning_brief(call.data.get("notes"), call.data["restart"])


def _dish_list(value: Any) -> list[Any]:
    """Externe KIs schicken die Liste mal direkt, mal als JSON-Text oder samt {"dishes": …}."""
    if isinstance(value, str):
        from .ai import parse_json

        try:
            value = parse_json(value)
        except Exception as err:  # noqa: BLE001
            raise ServiceValidationError(f"dishes ist kein gültiges JSON: {err}") from err
    if isinstance(value, dict):
        value = value.get("dishes", [value])
    if not isinstance(value, list):
        raise ServiceValidationError("dishes muss eine Liste von Gerichten sein.")
    return value


async def _submit_proposals(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_submit_proposals(
        _dish_list(call.data["dishes"]), final=call.data["final"], restart=call.data["restart"])


async def _memory_overview(call: ServiceCall) -> ServiceResponse:
    """Alles, was der Essensplaner sich merkt: Geschmacksprofil und Rezeptsammlung (für die Kachel „Gemerkt“)."""
    entry = _entry(call.hass)
    planner = entry.runtime_data.planner
    recipes = []
    for rec in entry.runtime_data.store.recipes.values():
        hist = rec.get("history") or {}
        cooked = hist.get("cooked_on") or []
        recipes.append({
            "id": rec["id"], "title": rec.get("title"), "url": rec.get("source_url"), "host": rec.get("host"),
            "rating": hist.get("rating"), "note": hist.get("note"), "status": hist.get("status"),
            "cooked_on": cooked, "last": cooked[-1] if cooked else None, "times": len(cooked),
            "stub": rec.get("stub", False), "imported_at": rec.get("imported_at"),
        })
    recipes.sort(key=lambda r: (r["title"] or "").lower())
    from .const import CONF_PROFILE

    return {"profile_text": _settings(entry).get(CONF_PROFILE) or "", **planner.profile_data(),
            "recipes": recipes}


async def _set_profile(call: ServiceCall) -> ServiceResponse:
    """Grundregeln und Geschmack (Freitext) ändern."""
    from .const import CONF_PROFILE

    entry = _entry(call.hass)
    text = (call.data.get("text") or "").strip()
    call.hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_PROFILE: text})
    return {"profile_text": text}


async def async_external_setup(hass: HomeAssistant, activate: bool = False, view: bool = False) -> dict[str, Any]:
    """Einrichtung für eine externe KI: Zeitplan, Aufgabentext und Anweisung an die KI, alles aus den Einstellungen.
    activate stellt „Vorschläge kommen von“ auf externe KI um. Ruft eine KI das auf (view = False), merkt sich der
    Essensplaner den Zeitplan, damit die Karte warnen kann, wenn er später nicht mehr passt."""
    from .external import setup_info

    entry = _entry(hass)
    if activate and _settings(entry)["proposals_from"] != "external":
        hass.config_entries.async_update_entry(entry, options={**entry.options, "proposals_from": "external"})
    settings = settings_from_options({**entry.data, **entry.options})
    info = setup_info(settings, str(hass.config.time_zone), settings["proposals_from"] == "external")
    store = entry.runtime_data.store
    if not view:
        store.set_meta("external_schedule", info["schedule"])
    registered = store.meta.get("external_schedule")
    return {**info, "registered_schedule": registered,
            "schedule_changed": bool(registered) and registered != info["schedule"]}


async def _external_setup(call: ServiceCall) -> ServiceResponse:
    return await async_external_setup(call.hass, bool(call.data.get("activate")), bool(call.data.get("view")))


async def _choose_dish(call: ServiceCall) -> ServiceResponse:
    planner = _planner(call)
    choice = call.data["choice"]
    if choice in TRIP_KEYS and choice not in planner.trip_keys:
        raise ServiceValidationError(f"{choice} ist nicht eingerichtet (Konfigurieren → Einkäufe).")
    return await planner.async_choose(call.data["dish_id"], choice)


async def _set_ingredients_ready(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_set_ready(call.data["dish_id"], call.data["ready"])


async def _mark_cooked(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_mark_cooked(
        call.data["dish_id"], call.data["cooked"], call.data.get("rating"), call.data.get("note"))


async def _dish_items(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_dish_items(call.data["dish_id"])


async def _set_items_at_home(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_set_skip(call.data["dish_id"], call.data["items"])


IMPORT_WEEK_SCHEMA = vol.Schema({
    vol.Required("dishes"): vol.Any(list, dict, cv.string),
    vol.Optional("board", default="current"): vol.In(["current", "next"]),
})


async def _import_week(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_import_week(_dish_list(call.data["dishes"]), call.data["board"])


MORE_SCHEMA = vol.Schema({vol.Optional("count", default=5): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                          vol.Optional("notes"): cv.string})
SWAP_SCHEMA = vol.Schema({vol.Required("dish_id"): cv.string, vol.Optional("notes"): cv.string})


async def _more_proposals(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_more(call.data["count"], call.data.get("notes"))


async def _swap_dish(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_swap(call.data["dish_id"], call.data.get("notes"))


async def _finalize_week(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_finalize()


async def _release_shopping(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_release(call.data.get("trip"))


async def _sync_shopping_list(call: ServiceCall) -> ServiceResponse:
    return await _planner(call).async_sync()


SERVICES: list[tuple[str, Any, vol.Schema, SupportsResponse]] = [
    ("import_recipe", _import_recipe, IMPORT_SCHEMA, SupportsResponse.ONLY),
    ("get_recipe", _get_recipe, GET_SCHEMA, SupportsResponse.ONLY),
    ("list_recipes", _list_recipes, LIST_SCHEMA, SupportsResponse.ONLY),
    ("delete_recipe", _delete_recipe, DELETE_SCHEMA, SupportsResponse.OPTIONAL),
    ("add_to_shopping_list", _add_to_shopping_list, SHOP_SCHEMA, SupportsResponse.OPTIONAL),
    ("update_history", _update_history, HISTORY_SCHEMA, SupportsResponse.OPTIONAL),
    ("import_history", _import_history, IMPORT_HISTORY_SCHEMA, SupportsResponse.OPTIONAL),
    ("validate_plan", _validate_plan, PLAN_SCHEMA, SupportsResponse.ONLY),
    ("get_settings", _get_settings, vol.Schema({}), SupportsResponse.ONLY),
    ("search_recipes", _search_recipes, SEARCH_SCHEMA, SupportsResponse.ONLY),
    ("assess_recipes", _assess_recipes, ASSESS_SCHEMA, SupportsResponse.ONLY),
    ("generate_proposals", _generate_proposals, GENERATE_SCHEMA, SupportsResponse.OPTIONAL),
    ("planning_brief", _planning_brief, BRIEF_SCHEMA, SupportsResponse.ONLY),
    ("memory_overview", _memory_overview, vol.Schema({}), SupportsResponse.ONLY),
    ("external_setup", _external_setup, vol.Schema({vol.Optional("activate", default=False): cv.boolean,
                                                    vol.Optional("view", default=False): cv.boolean}),
     SupportsResponse.ONLY),
    ("set_profile", _set_profile, vol.Schema({vol.Optional("text", default=""): cv.string}),
     SupportsResponse.OPTIONAL),
    ("submit_proposals", _submit_proposals, SUBMIT_SCHEMA, SupportsResponse.OPTIONAL),
    ("choose_dish", _choose_dish, CHOOSE_SCHEMA, SupportsResponse.OPTIONAL),
    ("set_ingredients_ready", _set_ingredients_ready, READY_SCHEMA, SupportsResponse.OPTIONAL),
    ("mark_cooked", _mark_cooked, COOKED_SCHEMA, SupportsResponse.OPTIONAL),
    ("dish_items", _dish_items, DISH_SCHEMA, SupportsResponse.ONLY),
    ("set_items_at_home", _set_items_at_home, ITEMS_SCHEMA, SupportsResponse.OPTIONAL),
    ("finalize_week", _finalize_week, vol.Schema({}), SupportsResponse.OPTIONAL),
    ("import_week", _import_week, IMPORT_WEEK_SCHEMA, SupportsResponse.OPTIONAL),
    ("more_proposals", _more_proposals, MORE_SCHEMA, SupportsResponse.OPTIONAL),
    ("swap_dish", _swap_dish, SWAP_SCHEMA, SupportsResponse.OPTIONAL),
    ("release_shopping", _release_shopping, RELEASE_SCHEMA, SupportsResponse.OPTIONAL),
    ("sync_shopping_list", _sync_shopping_list, vol.Schema({}), SupportsResponse.OPTIONAL),
]


def async_register_services(hass: HomeAssistant) -> None:
    for name, handler, schema, response in SERVICES:
        hass.services.async_register(DOMAIN, name, handler, schema=schema, supports_response=response)
