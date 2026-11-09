"""Wochenablauf: Vorschläge, Auswahl, Einkauf, Wochenwechsel.

Zwei Tafeln im Speicher:
  next    = Vorschläge für die kommende Woche (ab dem Planungstermin bis zum Auswahlschluss)
  current = die laufende Woche (nach dem Auswahlschluss)
Was fest ist (Termine, Einkaufsliste, Zählen, Prüfen), macht der Code. Was Geschmack
und Urteil braucht (Rezepte finden, Katalognamen, weiche Kriterien), macht die KI.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
import logging
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .messages import msg
from .ai import AIError, async_ask, board_prompt, shopping_prompt
from .classify import classify_diet
from .const import (
    DOMAIN,
    CHOICE_DECLINED,
    CHOICE_NONE,
    CONF_AI_SHOPPING,
    CONF_AI_TASK,
    CONF_CATALOG,
    CONF_DASHBOARD_PATH,
    CONF_DEADLINE_DAY,
    CONF_DEADLINE_TIME,
    CONF_DEVICE_COUNTS,
    CONF_DIET,
    CONF_KCAL_MAX,
    CONF_KCAL_MAX_NO_SIDE,
    CONF_CAL_RULES,
    CONF_NOTIFY,
    CONF_PLAN_DAY,
    CONF_PLAN_TIME,
    CONF_PORTIONS,
    CONF_QUICK_SHARE,
    CONF_RECIPES_PER_WEEK,
    CONF_SKIP_SPICES,
    CONF_STAPLES,
    CONF_TIME_MAX,
    CONF_TIME_QUICK,
    CONF_TRIPS,
    RELEASE_TIMED,
    DEVICE_THERMOMIX,
    DIET_LOW_CHOLESTEROL,
    DIET_VEGETARIAN,
    EXTERNAL_FALLBACK_HOURS,
    MAX_PLAN_ROUNDS,
    PROPOSALS_EXTERNAL,
    MODE_ALWAYS,
    MODE_COUNT,
    SIGNAL_BOARD_UPDATED,
    THERMOMIX_SOURCES,
)
from .planning import dish_matches, enabled_sources
from .search import TESTED, async_search, relevant
from .const import CONF_REGION, REGION_LANGUAGE
from .shopping import (
    apply_catalog,
    async_add_items,
    async_remove_tag,
    build_items,
    parse_catalog,
    parse_staples,
)

if TYPE_CHECKING:
    from .services import EssensplanerConfigEntry

_LOGGER = logging.getLogger(__name__)
DAY_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _parse_time(text: str) -> time:
    hour, minute = (int(x) for x in str(text).split(":")[:2])
    return time(hour, minute)


# Weiterleitungen von KI-Websuchen (Google-Grounding) – das Ziel steht erst nach dem Abruf fest
REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)
RETRY_DELAY = 20  # Sekunden bis zum zweiten Versuch beim Such-Agenten
MAX_PROPOSALS = 20  # Gerichte pro submit_proposals-Aufruf, die geprüft werden
SEARCH_BUDGET = 40  # Abrufe (Suchseiten + Rezepte) für die Ersatzsuche pro Lauf
MAX_FAILURES = 3  # KI-Fehlschläge pro Woche, danach kein stündlicher Neuversuch mehr
MAX_TEXT = 200  # Wunsch, Suchbegriff, Seite
MAX_URL = 2048


def _num(value: Any) -> int | None:
    """Zahl aus einem KI-Feld („30“, 30.0, "abc") – Unbrauchbares wird None statt eines Absturzes."""
    if isinstance(value, bool):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _short(text: str, limit: int = 60) -> str:
    """Titel kürzen, ohne mitten im Wort abzuschneiden."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" -–,") + " …"


def _norm_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def next_weekday_at(after: datetime, weekday: int, at: time) -> datetime:
    """Nächster Zeitpunkt mit diesem Wochentag und dieser Uhrzeit nach `after`."""
    candidate = after.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    candidate += timedelta(days=(weekday - after.weekday()) % 7)
    if candidate <= after:
        candidate += timedelta(days=7)
    return candidate


def last_weekday_at(before: datetime, weekday: int, at: time) -> datetime:
    return next_weekday_at(before, weekday, at) - timedelta(days=7)


def week_meta(plan_at: datetime, settings: dict[str, Any]) -> dict[str, Any]:
    """Termine der Woche, für die zum Planungszeitpunkt `plan_at` Vorschläge entstehen."""
    deadline = next_weekday_at(plan_at, settings[CONF_DEADLINE_DAY], _parse_time(settings[CONF_DEADLINE_TIME]))
    start = deadline.date()
    release_at: dict[str, str] = {}
    released: dict[str, bool] = {}
    for trip in settings[CONF_TRIPS]:
        if trip["release"] == RELEASE_TIMED:
            release_at[trip["key"]] = next_weekday_at(
                plan_at, trip["weekday"], _parse_time(trip["time"])).isoformat()
            released[trip["key"]] = False
        else:
            released[trip["key"]] = True
    kw = (start + timedelta(days=3)).isocalendar()
    return {
        "id": start.isoformat(),
        "kw": kw.week,
        "year": kw.year,
        "start": start.isoformat(),
        "end": (start + timedelta(days=6)).isoformat(),
        "deadline": deadline.isoformat(),
        "release_at": release_at,
        "released": released,
    }


def new_dish(**fields: Any) -> dict[str, Any]:
    dish = {
        "id": uuid.uuid4().hex[:8],
        "nr": 0,
        "recipe_id": None,
        "title": "",
        "url": None,
        "time_min": None,
        "kcal": None,
        "kcal_note": None,
        "meatless": False,
        "low_cholesterol": False,
        "fits": [],
        "skip_items": [],
        "foreign_language": None,
        "wish": None,
        "own_recipe": False,
        "tip": None,
        "reason": "",
        "choice": CHOICE_NONE,
        "ingredients_ready": False,
        "on_list": False,
        "cooked_on": None,
        "rating": None,
        "note": None,
        "carried": False,
        "checked": True,
    }
    dish.update(fields)
    return dish


class WeekPlanner:
    """Steuert die Tafeln eines Config Entries."""

    def __init__(self, hass: HomeAssistant, entry: EssensplanerConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.busy = False
        self.reload_pending = False
        self._store = entry.runtime_data.store  # fest merken: bleibt gültig, auch wenn neu geladen wird
        self._tick_lock = asyncio.Lock()
        self._labels: set[str] = set()
        self._rotation = 0
        self._wish_texts: set[str] = set()
        self._replaced: list[str] = []
        self._missed: str | None = None
        self._frozen: dict[str, Any] | None = None
        self._failures: dict[str, int] = {}
        self._in_tick = False
        self._budget = SEARCH_BUDGET
        self._wish_hosts: set[str] = set()

    # ----------------------------------------------------------- Zugriff ---
    @property
    def store(self):  # noqa: ANN201
        return self._store

    @property
    def settings(self) -> dict[str, Any]:
        from .services import _settings

        # während eines Laufs gilt durchgehend derselbe Stand (Termine, Regeln, Einkäufe)
        return self._frozen if self._frozen is not None else _settings(self.entry)

    @property
    def boards(self) -> dict[str, Any]:
        return self.store.meta.setdefault("board", {"current": None, "next": None})

    def _changed(self) -> None:
        self.store.set_meta("board", self.boards)
        async_dispatcher_send(self.hass, SIGNAL_BOARD_UPDATED)

    def find(self, dish_id: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
        for key in ("next", "current"):
            board = self.boards.get(key)
            for dish in (board or {}).get("dishes", []):
                if dish["id"] == dish_id or str(dish["nr"]) == str(dish_id) and key == self._active_key():
                    return key, board, dish
        raise ServiceValidationError(f"Gericht {dish_id} nicht gefunden.")

    def _active_key(self) -> str:
        return "next" if self.boards.get("next") else "current"

    # ----------------------------------------------------------- Einkauf ---
    def _list_entity(self) -> str:
        from .services import _list_entity

        return _list_entity(self.hass, self.entry)

    async def _items_for(self, dish: dict[str, Any], *, all_items: bool = False) -> list[dict[str, str]]:
        recipe = self.store.get(dish["recipe_id"]) if dish.get("recipe_id") else None
        if not recipe or recipe.get("stub"):
            return []
        items, _ = await self.async_recipe_items(recipe, self.settings[CONF_PORTIONS])
        if all_items:
            return items
        skip = {n.lower() for n in dish.get("skip_items") or []}
        return [i for i in items if i["name"].lower() not in skip]

    async def async_dish_items(self, dish_id: str) -> dict[str, Any]:
        """Einkaufszeilen eines Gerichts, mit Markierung, was schon da ist."""
        _, _, dish = self.find(dish_id)
        skip = {n.lower() for n in dish.get("skip_items") or []}
        items = await self._items_for(dish, all_items=True)
        return {"dish_id": dish["id"], "title": dish["title"],
                "items": [{**i, "at_home": i["name"].lower() in skip} for i in items]}

    async def async_set_skip(self, dish_id: str, names: list[str]) -> dict[str, Any]:
        """Teilweise vorhandene Zutaten: diese Artikel nicht auf die Liste."""
        _, _, dish = self.find(dish_id)
        dish["skip_items"] = sorted({n.strip() for n in names if n.strip()})
        if dish["on_list"]:
            await async_remove_tag(self.hass, self._list_entity(), dish["title"])
            dish["on_list"] = False
        report = await self.async_sync()
        return {"dish": dish, **report}

    async def async_recipe_items(
        self, recipe: dict[str, Any], portions: float | None
    ) -> tuple[list[dict[str, str]], list[str]]:
        """Einkaufszeilen eines Rezepts: umrechnen, Grundzutaten weg, Katalognamen (KI + Liste)."""
        settings = self.settings
        items, skipped = build_items(recipe, portions, parse_staples(settings[CONF_STAPLES]),
                                     settings[CONF_SKIP_SPICES])
        catalog = parse_catalog(settings[CONF_CATALOG])
        if settings[CONF_AI_TASK] and settings[CONF_AI_SHOPPING] and items:
            cache_key = f"p{portions}"
            cached = (recipe.get("ai_shopping") or {}).get(cache_key)
            if cached:
                items = cached
            else:
                try:
                    answer = await async_ask(self.hass, settings[CONF_AI_TASK], "Essensplaner Einkaufsliste",
                                             shopping_prompt(items, catalog, REGION_LANGUAGE.get(
                                                 self.settings[CONF_REGION], "Deutsch")))
                    ai_items = [
                        {"name": str(i["name"]).strip(), "spec": str(i.get("spec") or "").strip()}
                        for i in answer.get("items", []) if str(i.get("name") or "").strip()
                    ]
                    if ai_items:
                        items = ai_items
                        self.store.set_fields(recipe["id"], ai_shopping={
                            **(recipe.get("ai_shopping") or {}), cache_key: ai_items})
                except (AIError, AttributeError, KeyError, TypeError) as err:
                    _LOGGER.warning("KI-Aufbereitung der Einkaufsliste übersprungen: %s", err)
        return apply_catalog(items, catalog), skipped

    def _wants_list(self, board: dict[str, Any], dish: dict[str, Any]) -> bool:
        if dish["ingredients_ready"] or dish["own_recipe"] or not dish.get("recipe_id"):
            return False
        if dish["choice"] not in self.trip_keys:
            return False
        return board.get("released", {}).get(dish["choice"], True)

    async def async_sync(self) -> dict[str, list[str]]:
        """Einkaufsliste an die Auswahl angleichen (eintragen bzw. austragen)."""
        report: dict[str, list[str]] = {"added": [], "removed": [], "errors": []}
        target = self._list_entity()
        failed: list[tuple[str, Exception]] = []
        for key in ("current", "next"):
            board = self.boards.get(key)
            for dish in (board or {}).get("dishes", []):
                want = self._wants_list(board, dish)
                # jedes Gericht für sich: ein Fehler bei einem darf die anderen nicht aufhalten
                try:
                    if want and not dish["on_list"]:
                        items = await self._items_for(dish)
                        if items:
                            await async_add_items(self.hass, target, items, dish["title"])
                        dish["on_list"] = True
                        report["added"].append(dish["title"])
                    elif not want and dish["on_list"] and not dish["cooked_on"]:
                        await async_remove_tag(self.hass, target, dish["title"])
                        dish["on_list"] = False
                        report["removed"].append(dish["title"])
                except HomeAssistantError as err:
                    _LOGGER.warning("Einkaufsliste für '%s' nicht abgeglichen: %s", dish["title"], err)
                    failed.append((dish["title"], err))
                    report["errors"].append(f"{dish['title']}: {err}")
        self._changed()
        if failed and not report["added"] and not report["removed"]:
            # nichts ging: einmal deutlich melden (beim nächsten Abgleich wird es erneut versucht)
            title, err = failed[0]
            raise HomeAssistantError(f"Einkaufsliste für '{title}' nicht abgeglichen: {err}") from err
        return report

    # ---------------------------------------------------------- Aktionen ---
    async def async_choose(self, dish_id: str, choice: str) -> dict[str, Any]:
        _, _, dish = self.find(dish_id)
        dish["choice"] = choice
        report = await self.async_sync()
        return {"dish": dish, **report}

    async def async_set_ready(self, dish_id: str, ready: bool) -> dict[str, Any]:
        _, _, dish = self.find(dish_id)
        dish["ingredients_ready"] = ready
        report = await self.async_sync()
        return {"dish": dish, **report}

    async def async_mark_cooked(
        self, dish_id: str, cooked: bool, rating: int | None, note: str | None
    ) -> dict[str, Any]:
        _, _, dish = self.find(dish_id)
        today = dt_util.now().date()
        if not cooked:
            # Rückgängig: Kochtag, Bewertung und Notiz aus dem Verlauf entfernen, wie vorher
            if dish.get("cooked_on") and dish.get("recipe_id") and self.store.get(dish["recipe_id"]):
                self.store.undo_cooked(dish["recipe_id"], dish["cooked_on"], dish.get("before_cooked"))
            before = dish.pop("before_cooked", None) or {}
            dish["cooked_on"] = None
            dish["rating"] = before.get("dish_rating")
            dish["note"] = before.get("dish_note")
            self._changed()
            return {"dish": dish}
        if not dish.get("cooked_on"):
            rec = self.store.get(dish["recipe_id"]) if dish.get("recipe_id") else None
            hist = (rec or {}).get("history") or {}
            dish["before_cooked"] = {"rating": hist.get("rating"), "note": hist.get("note"),
                                     "status": hist.get("status"), "dish_rating": dish.get("rating"),
                                     "dish_note": dish.get("note")}
        dish["cooked_on"] = today.isoformat() if cooked else None
        if rating is not None:
            dish["rating"] = rating
        if note is not None:
            dish["note"] = note or None
        if dish.get("recipe_id") and self.store.get(dish["recipe_id"]):
            self.store.update_history(
                dish["recipe_id"], cooked_on=today if cooked else None, rating=rating, note=note,
                status="cooked" if cooked else None)
        elif cooked:
            stub = self.store.find(title=dish["title"]) or self.store.add_stub(dish["title"], dish.get("url"))
            self.store.update_history(stub["id"], cooked_on=today, rating=rating, note=note)
            dish["recipe_id"] = dish["recipe_id"] or stub["id"]
        self._changed()
        return {"dish": dish}

    @property
    def trip_keys(self) -> list[str]:
        return [t["key"] for t in self.settings[CONF_TRIPS]]

    def trip_name(self, key: str) -> str:
        return next((t["name"] for t in self.settings[CONF_TRIPS] if t["key"] == key), key)

    async def async_release(self, trip: str | None = None) -> dict[str, Any]:
        """Einkauf freigeben: Zutaten der dafür gewählten Gerichte kommen auf die Liste."""
        for key in ("next", "current"):
            board = self.boards.get(key)
            if not board:
                continue
            for trip_key in list(board.setdefault("released", {})):
                if trip is None or trip == trip_key:
                    board["released"][trip_key] = True
        return await self.async_sync()

    async def async_finalize(self) -> dict[str, Any]:
        """Auswahlschluss: Nicht Gewähltes fällt weg, die Vorschläge werden zur laufenden Woche."""
        nxt = self.boards.get("next")
        if not nxt:
            return {"finalized": False, "reason": "keine Vorschläge"}
        target = self._list_entity()
        for dish in nxt["dishes"]:
            if dish["choice"] in (CHOICE_NONE, CHOICE_DECLINED) and dish["on_list"]:
                await async_remove_tag(self.hass, target, dish["title"])
                dish["on_list"] = False
        kept = [d for d in nxt["dishes"] if d["choice"] in self.trip_keys]
        per_trip = {k: sum(1 for d in kept if d["choice"] == k) for k in self.trip_keys}
        nxt["dishes"] = kept
        nxt["finalized_at"] = dt_util.now().isoformat()
        archive = self.store.meta.setdefault("archive", [])
        if self.boards.get("current"):
            archive.append(self.boards["current"])
            del archive[:-8]
        self.boards["current"] = nxt
        self.boards["next"] = None
        self._changed()
        trips = ", ".join(f"{n} × {self.trip_name(k)}" for k, n in per_trip.items())
        await self.async_notify(msg(self.settings, "done_title"), msg(self.settings, "done", kw=nxt["kw"], trips=trips))
        return {"finalized": True, "per_trip": {self.trip_name(k): n for k, n in per_trip.items()}}

    async def async_import_week(self, dishes: list[dict[str, Any]], board_key: str = "current") -> dict[str, Any]:
        """Woche von außen übernehmen (Umstieg von einem anderen Planer) oder Vorschläge verwerfen.

        board_key "current": laufende Woche (Kochen, Abhaken, noch ausstehende Einkäufe),
        "next": Vorschläge der kommenden Woche; eine leere Liste verwirft sie.
        """
        from .services import fetch_recipe

        settings = self.settings
        now = dt_util.now()
        if board_key == "next":
            if not dishes:
                self.boards["next"] = None
                self._changed()
                return {"board": "next", "count": 0, "cleared": True}
            meta = self._plan_meta()
        else:
            plan_at = last_weekday_at(now + timedelta(minutes=1), settings[CONF_PLAN_DAY],
                                      _parse_time(settings[CONF_PLAN_TIME]))
            meta = week_meta(plan_at, settings)
            if dt_util.parse_datetime(meta["deadline"]) > now:  # Auswahl läuft noch: laufend ist die Vorwoche
                meta = week_meta(plan_at - timedelta(days=7), settings)
            meta["released"] = {k: (dt_util.parse_datetime(at) <= now)
                                for k, at in meta["release_at"].items()} | {
                k: True for k in self.trip_keys if k not in meta["release_at"]}
        names = {self._norm_trip(t["name"]): t["key"] for t in settings[CONF_TRIPS]}
        built: list[dict[str, Any]] = []
        problems: list[str] = []
        for nr, raw in enumerate(dishes[:MAX_PROPOSALS], 1):
            choice = str(raw.get("choice") or "")
            choice = choice if choice in self.trip_keys else names.get(self._norm_trip(choice), CHOICE_NONE)
            url = str(raw.get("url") or "").strip()[:MAX_URL] or None
            recipe = None
            if url:
                try:
                    recipe = self.store.upsert(await fetch_recipe(self.hass, url), url)
                except HomeAssistantError as err:
                    problems.append(f"{raw.get('title') or url}: Rezept nicht lesbar ({err})")
            dish = new_dish(
                nr=nr, title=_short(str(raw.get("title") or (recipe or {}).get("title") or "?")), url=url,
                recipe_id=(recipe or {}).get("id"),
                time_min=(recipe or {}).get("total_time_min") or _num(raw.get("time_min")),
                kcal=(recipe or {}).get("kcal_per_serving") or _num(raw.get("kcal")),
                meatless=bool(raw.get("meatless")), low_cholesterol=bool(raw.get("low_cholesterol")),
                own_recipe=bool(raw.get("own_recipe")), wish=str(raw.get("wish") or "")[:MAX_TEXT] or None,
                choice=choice, tip=choice if choice in self.trip_keys else None,
                ingredients_ready=bool(raw.get("ingredients_ready")), on_list=bool(raw.get("on_list")),
                skip_items=[str(x) for x in raw.get("skip_items") or []],
                cooked_on=raw.get("cooked_on"), rating=_num(raw.get("rating")), note=raw.get("note"),
                reason=str(raw.get("reason") or "")[:MAX_TEXT])
            if recipe:
                diet = classify_diet(recipe, settings[CONF_KCAL_MAX])
                if diet[DIET_VEGETARIAN] is not None:
                    dish["meatless"] = diet[DIET_VEGETARIAN]
            built.append(dish)
        board = {**meta, "created": now.isoformat(), "dishes": built, "rounds": 0, "problems": problems,
                 "source": "import", "excluded": [], "deficits": [], "notified": True}
        if board_key == "current":
            board["finalized_at"] = now.isoformat()
        self.boards[board_key] = board
        report = await self.async_sync()
        return {"board": board_key, "kw": meta["kw"], "count": len(built), "problems": problems, **report}

    @staticmethod
    def _norm_trip(name: str) -> str:
        return re.sub(r"[\s\-–—]+", "-", str(name).strip().lower())

    # -------------------------------------------------------- Vorschläge ---
    def _trip_texts(self, meta: dict[str, Any]) -> list[str]:
        out = []
        for trip in self.settings[CONF_TRIPS]:
            at_text = (meta.get("release_at") or {}).get(trip["key"])
            if (meta.get("released") or {}).get(trip["key"]) or (trip["release"] == RELEASE_TIMED and not at_text):
                when = "ist schon eingekauft bzw. freigegeben, kommt bei Wahl sofort auf die Liste"
            elif trip["release"] == RELEASE_TIMED:
                at = dt_util.parse_datetime(at_text)
                when = f"kommt {DAY_SHORT[at.weekday()]} {at.strftime('%d.%m. %H:%M')} auf die Liste"
            else:
                when = "kommt direkt nach der Auswahl auf die Liste"
            days = f", für {', '.join(DAY_SHORT[d] for d in trip['days'])}" if trip["days"] else ""
            out.append(f"{trip['key']} = \"{trip['name']}\" ({when}{days})")
        return out

    def wishes_entity(self) -> str:
        """Wunschliste über die Registry finden (bleibt gültig, wenn jemand die Entität umbenennt)."""
        from homeassistant.helpers import entity_registry as er

        return er.async_get(self.hass).async_get_entity_id(
            "todo", DOMAIN, f"{self.entry.entry_id}_wishes") or "todo.meal_planner_wishes"

    async def _wishes(self) -> list[dict[str, Any]]:
        entity = self.wishes_entity()
        if self.hass.states.get(entity) is None:
            return []
        resp = await self.hass.services.async_call(
            "todo", "get_items", {"entity_id": entity, "status": "needs_action"},
            blocking=True, return_response=True)
        wishes = []
        for item in (resp or {}).get(entity, {}).get("items", []):
            text = item["summary"].strip()
            desc = (item.get("description") or "").strip()
            own = "eigenes rezept" in f"{text} {desc}".lower()
            clean = re.sub(r"\(?\s*eigenes rezept\s*\)?", "", text, flags=re.IGNORECASE).strip(" ,-–")
            wishes.append({"uid": item["uid"], "text": (clean or text)[:MAX_TEXT], "note": desc[:MAX_TEXT],
                           "own_recipe": own})
        return wishes

    async def _calendar_context(self, start: date, end: date) -> list[dict[str, Any]]:
        """Kalender-Regeln auswerten: je Regel die betroffenen Tage samt Terminnamen."""
        out: list[dict[str, Any]] = []
        for rule in self.settings[CONF_CAL_RULES]:
            cals = [c for c in rule["calendars"] if self.hass.states.get(c)]
            if not cals:
                continue
            try:
                resp = await self.hass.services.async_call(
                    "calendar", "get_events",
                    {"entity_id": cals,
                     "start_date_time": dt_util.start_of_local_day(start).isoformat(),
                     "end_date_time": dt_util.start_of_local_day(end + timedelta(days=1)).isoformat()},
                    blocking=True, return_response=True)
            except HomeAssistantError as err:
                _LOGGER.warning("Kalender nicht lesbar: %s", err)
                continue
            keyword = rule["keyword"].lower()
            days: dict[date, list[str]] = {}
            for data in (resp or {}).values():
                for ev in data.get("events", []):
                    summary = ev.get("summary") or ""
                    if keyword and keyword not in f"{summary} {ev.get('description') or ''}".lower():
                        continue
                    s_raw, e_raw = str(ev["start"]), str(ev.get("end") or ev["start"])
                    day = max(date.fromisoformat(s_raw[:10]), start)
                    last = date.fromisoformat(e_raw[:10])
                    if len(e_raw) == 10 and last > date.fromisoformat(s_raw[:10]):
                        last -= timedelta(days=1)  # Ganztags-Ende ist exklusiv
                    while day <= min(last, end):
                        days.setdefault(day, []).append(summary)
                        day += timedelta(days=1)
            if days:
                out.append({
                    "label": rule["label"],
                    "hint": rule["hint"],
                    "days": [f"{DAY_SHORT[d.weekday()]} {d.strftime('%d.%m.')}: {', '.join(sorted(set(v)))}"
                             for d, v in sorted(days.items())],
                })
        return out

    def profile_data(self, today: date | None = None) -> dict[str, list[dict[str, Any]]]:
        """Geschmacksprofil, wie es die KI bekommt: gemocht (4–5), nicht gemocht (1–2), kürzlich gekocht."""
        today = today or dt_util.now().date()
        liked, disliked, recent = [], [], []
        for rec in self.store.recipes.values():
            hist = rec.get("history") or {}
            rating = hist.get("rating")
            item = {"id": rec["id"], "title": rec.get("title"), "url": rec.get("source_url"),
                    "rating": rating, "note": hist.get("note")}
            if rating and rating >= 4:
                liked.append(item)
            elif rating and rating <= 2:
                disliked.append(item)
            cooked = hist.get("cooked_on") or []
            if cooked and date.fromisoformat(cooked[-1]) > today - timedelta(days=28):
                recent.append({**item, "last": cooked[-1]})
        recent.sort(key=lambda r: r["last"], reverse=True)
        return {"liked": liked[-40:], "disliked": disliked[-40:], "recent": recent}

    def _profile_context(self, today: date) -> dict[str, list[str]]:
        data = self.profile_data(today)
        note = lambda r: f" – {r['note']}" if r["note"] else ""  # noqa: E731
        return {
            "liked": [f"{r['title']} ({r['rating']}/5){note(r)} {r['url'] or ''}".strip() for r in data["liked"]],
            "disliked": [f"{r['title']} ({r['rating']}/5){note(r)}" for r in data["disliked"]],
            "recent": [f"{r['title']} (zuletzt {r['last']})" for r in data["recent"]],
        }

    def _recently_cooked(self, recipe: dict[str, Any] | None, title: str, today: date) -> bool:
        candidates = [recipe] if recipe else []
        found = self.store.find(title=title)
        if found:
            candidates.append(found)
        for rec in candidates:
            cooked = (rec.get("history") or {}).get("cooked_on") or []
            if cooked and date.fromisoformat(cooked[-1]) > today - timedelta(days=28):
                return True
        return False

    def _disliked(self, recipe: dict[str, Any] | None, title: str) -> bool:
        for rec in filter(None, [recipe, self.store.find(title=title)]):
            rating = (rec.get("history") or {}).get("rating")
            if rating is not None and rating <= 2:
                return True
        return False

    async def _check_dish(
        self, prop: dict[str, Any], taken: set[str], today: date, searched: bool = False
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Einen KI-Vorschlag prüfen; liefert (Gericht, None) oder (None, Grund)."""
        from .services import fetch_recipe

        settings = self.settings
        title = _short(str(prop.get("title") or ""))
        wish = str(prop.get("wish") or "").strip()[:MAX_TEXT] or None
        if wish and not self._is_open_wish(wish, title):
            wish = None  # die KI füllt "wish" gern mit Begründungen; nur echte Wünsche umgehen die Regeln
        own = bool(prop.get("own_recipe")) and bool(wish)
        url = str(prop.get("url") or "").strip()[:MAX_URL] or None
        if not title:
            return None, "ohne Titel"
        if _norm_title(title) in taken:
            return None, f"'{title}' doppelt"
        dish = new_dish(
            title=title, wish=wish, own_recipe=own, reason=str(prop.get("reason") or "")[:200],
            tip=prop.get("tip") if prop.get("tip") in self.trip_keys else None,
            fits=[str(f) for f in (prop.get("fits") if isinstance(prop.get("fits"), list) else []) if str(f) in self._labels],
            low_cholesterol=bool(prop.get("low_cholesterol")),
            meatless=bool(prop.get("meatless")),
        )
        if own:
            dish["tip"] = None
            return dish, None
        prefer = str(prop.get("site") or "").strip().lower()[:MAX_TEXT].removeprefix("www.")
        if not url or not url.startswith("http"):
            if not searched:
                return await self._search_dish(prop, title, prefer, taken, today, f"'{title}' ohne Rezeptlink")
            return None, f"'{title}' ohne Rezeptlink"
        host = (urlparse(url).hostname or "").removeprefix("www.")
        if host in REDIRECT_HOSTS:
            # KI mit Websuche (z. B. Gemini) liefert Weiterleitungsadressen: erst auflösen, dann prüfen
            from .services import fetch_html

            try:
                _, url = await fetch_html(self.hass, url)
            except HomeAssistantError as err:
                if not searched:
                    return await self._search_dish(prop, title, prefer, taken, today,
                                                   f"'{title}': Weiterleitung nicht abrufbar ({err})")
                return None, f"'{title}': Weiterleitung nicht abrufbar ({err})"
            host = (urlparse(url).hostname or "").removeprefix("www.")
        if host.startswith("cookidoo."):
            url = await self._cookidoo_local(url, dish)
        # Wünsche dürfen nur die Seite nutzen, deren Link jemand selbst auf die Wunschliste geschrieben hat
        if host not in enabled_sources(settings) and not (wish and host in self._wish_hosts):
            reason = f"'{title}': Seite {host} ist nicht freigegeben"
            if not searched:
                return await self._search_dish(prop, title, prefer, taken, today, reason)
            return None, reason
        recipe = self.store.find(url=url)
        if recipe is None or recipe.get("stub"):
            try:
                recipe = self.store.upsert(await fetch_recipe(self.hass, url), url)
            except HomeAssistantError as err:
                from .services import RecipeFetchError

                exists = not isinstance(err, RecipeFetchError)  # Seite da, nur nicht lesbar (z. B. Cookidoo)
                if host.startswith("cookidoo.") and exists and _num(prop.get("time_min")) and _num(prop.get("kcal")):
                    recipe = None
                    dish["checked"] = False
                elif not searched:  # auch bei Wünschen: das gewünschte Gericht selbst suchen
                    # Link der KI tot oder geraten: dasselbe Gericht selbst auf den Rezeptseiten suchen
                    return await self._search_dish(prop, title, prefer or host, taken, today,
                                                   f"'{title}' nicht abrufbar ({err})")
                else:
                    return None, f"'{title}' nicht abrufbar ({err})"
        if (recipe and recipe.get("title") and not wish and not searched and not prop.get("_found")
                and not relevant(title, str(recipe["title"]))):
            # Link der KI führt zu einem anderen Rezept: das gemeinte Gericht selbst suchen
            return await self._search_dish(prop, title, prefer or host, taken, today,
                                           f"Link für '{title}' führt zu '{recipe['title']}'")
        if prop.get("_found") and recipe and recipe.get("title"):
            if not relevant(str(prop.get("query") or title), str(recipe["title"]), title):
                return None, f"Suchtreffer '{recipe['title']}' passt nicht zu '{title}'"
            real = _short(str(recipe["title"]), 56)
            if _norm_title(real) in taken:
                return None, f"'{real}' doppelt"
            if _norm_title(real) != _norm_title(title):
                # anderes Rezept als die KI-Idee: deren Begründung und Kennzeichen passen nicht mehr sicher
                dish["reason"] = f"Per Suche gefunden für „{title}“"
                dish["fits"] = []
                dish["low_cholesterol"] = False
            title = dish["title"] = real
        dish["url"] = (recipe or {}).get("source_url") or url
        if host in THERMOMIX_SOURCES and "(TM)" not in dish["title"]:
            dish["title"] = f"{_short(dish['title'], 55)} (TM)"  # Thermomix-Rezept auf einen Blick erkennbar
        dish["recipe_id"] = (recipe or {}).get("id")
        dish["time_min"] = (recipe or {}).get("total_time_min") or _num(prop.get("time_min"))
        kcal = (recipe or {}).get("kcal_per_serving")
        estimated = False
        if not kcal and _num(prop.get("kcal")):
            kcal = _num(prop.get("kcal"))
            estimated = bool(prop.get("kcal_estimated", True))
        without_side = bool(prop.get("kcal_without_side"))
        dish["kcal"] = kcal
        dish["kcal_note"] = ", ".join(
            x for x in ("geschätzt" if estimated else "", "ohne Beilage" if without_side else "") if x) or None
        if recipe:
            diet = classify_diet(recipe, settings[CONF_KCAL_MAX])
            if diet[DIET_VEGETARIAN] is not None:
                dish["meatless"] = diet[DIET_VEGETARIAN]
        if wish:
            return dish, None
        if self._recently_cooked(recipe, title, today):
            return None, f"'{title}' gab es in den letzten 4 Wochen"
        if self._disliked(recipe, title):
            return None, f"'{title}' ist schlecht bewertet"
        t = dish["time_min"]
        if not t:
            return None, f"'{title}' ohne Zeitangabe"
        if t > settings[CONF_TIME_MAX]:
            return None, f"'{title}' dauert {t} Min. (max. {settings[CONF_TIME_MAX]})"
        # leer = keine Grenze; ohne Beilage gilt hilfsweise die Grenze mit Beilage
        limit = (settings[CONF_KCAL_MAX_NO_SIDE] or settings[CONF_KCAL_MAX]) if without_side else settings[CONF_KCAL_MAX]
        if limit:
            if estimated:
                limit -= 100
            if not kcal:
                return None, f"'{title}' ohne kcal-Angabe"
            if kcal < 200 and not estimated:
                return None, f"'{title}': {kcal} kcal ist für ein Hauptgericht unplausibel"
            if kcal > limit:
                return None, f"'{title}' hat {kcal} kcal (Grenze {limit})"
        return dish, None

    async def _assess_dishes(self, dishes: list[dict[str, Any]]) -> None:
        """Cholesterinarm am echten Rezept von der KI bewerten lassen (statt der Behauptung im Vorschlag)."""
        from .services import async_assess

        if not self.settings[CONF_AI_TASK]:
            return
        recipes = [r for d in dishes if d.get("recipe_id") and (r := self.store.recipes.get(d["recipe_id"]))]
        if not recipes:
            return
        try:
            await async_assess(self.hass, self.entry, recipes, [DIET_LOW_CHOLESTEROL])
        except Exception as err:  # noqa: BLE001 - Bewertung ist ein Zusatz, der Plan darf daran nicht scheitern
            _LOGGER.info("Bewertung cholesterinarm nicht möglich: %s", err)
            return
        for dish in dishes:
            rec = self.store.recipes.get(dish.get("recipe_id") or "")
            value = ((rec or {}).get("ai_diet") or {}).get(DIET_LOW_CHOLESTEROL)
            if isinstance(value, bool):
                dish["low_cholesterol"] = value

    def _is_open_wish(self, wish: str, title: str) -> bool:
        """Gehört der Vorschlag zu einem Eintrag auf der Wunschliste?"""
        def within(part: str, whole: str) -> bool:
            return len(part) >= 3 and re.search(rf"(?<!\w){re.escape(part)}(?!\w)", whole) is not None

        for text in self._wish_texts:
            for value in (_norm_title(wish), _norm_title(title)):
                if text and value and (text == value or within(text, value) or within(value, text)):
                    return True
        return False

    async def _search_dish(
        self, prop: dict[str, Any], title: str, prefer: str, taken: set[str], today: date, reason: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Gericht selbst auf den freigegebenen Rezeptseiten suchen (höchstens 10 Suchseiten, 4 Rezepte)."""
        hosts = enabled_sources(self.settings)
        order = [prefer] if prefer in hosts else []
        rest = [h for h in hosts if h not in order and not h.startswith("cookidoo.")]
        if "(TM)" in title or prefer in THERMOMIX_SOURCES:
            # Thermomix-Idee: zuerst auf Thermomix-Seiten suchen, damit es ein TM-Gericht bleibt
            order += [h for h in rest if h in THERMOMIX_SOURCES]
            rest = [h for h in rest if h not in THERMOMIX_SOURCES]
        tested = [h for h in rest if h in TESTED]
        if tested:  # geprüfte Suchen zuerst, reihum, damit nicht alles von derselben Seite kommt
            start = self._rotation % len(tested)
            self._rotation += 1
            tested = tested[start:] + tested[:start]
        order += tested + [h for h in rest if h not in TESTED]
        query = re.sub(r"\(TM\)", "", str(prop.get("query") or title)).strip()
        pages, fetches = 10, 4
        last = reason
        for host in order:
            if pages <= 0 or fetches <= 0:
                break
            if self._budget <= 0:
                last = f"{reason} (Suchbudget für diesen Lauf aufgebraucht)"
                break
            pages -= 1
            self._budget -= 1
            for link in (await async_search(self.hass, host, query, self._local_locale()))[:2]:
                if fetches <= 0 or self._budget <= 0:
                    break
                fetches -= 1
                self._budget -= 1
                dish, why = await self._check_dish({**prop, "url": link, "_found": True}, taken, today, searched=True)
                if dish:
                    self._replaced.append(f"{reason} → ersetzt durch '{dish['title']}'")
                    _LOGGER.info("%s → ersetzt durch %s", reason, dish["url"])
                    return dish, None
                last = why or last
        return None, last if last != reason else f"{reason}, auch per Suche nichts Passendes"

    async def _ask_proposals(self, prompt: str) -> Any:
        """Erst der Such-Agent (Websuche); scheitert er (z. B. Kontingent erschöpft), die normale KI."""
        search, task = self._search_ai(), self.settings[CONF_AI_TASK]
        if search:
            for attempt in (1, 2):  # Google meldet zeitweise "überlastet" (503): einmal nachfassen
                try:
                    return await async_ask(self.hass, search, "Essensplaner Wochenvorschläge", prompt)
                except AIError as err:
                    if attempt == 2 or not task:
                        if not task:
                            raise
                        _LOGGER.warning("Such-Agent %s nicht nutzbar (%s), nehme %s", search, err, task)
                    else:
                        await asyncio.sleep(RETRY_DELAY)
        return await async_ask(self.hass, task, "Essensplaner Wochenvorschläge", prompt)

    def _search_ai(self) -> str | None:
        """Gesprächsagent mit Websuche (falls eingestellt und vorhanden)."""
        from .agent import resolve_agent

        agent = resolve_agent(self.hass, self.settings["ai_search"])
        return agent if agent and self.hass.states.get(agent) else None

    def _local_locale(self) -> str:
        """Sprache/Land der Rezepte, z. B. de-DE (aus der Region-Einstellung)."""
        from .const import CONF_REGION, REGION_LOCALE

        return REGION_LOCALE.get(self.settings[CONF_REGION], "de-DE")

    async def _cookidoo_local(self, url: str, dish: dict[str, Any]) -> str:
        """Cookidoo: Gericht möglichst in der Landessprache.

        1. dasselbe Rezept in der Landessprache, 2. ein gleichwertiges Gericht in der Landessprache
        (sucht die KI), 3. sonst bleibt das fremdsprachige Rezept (Cookidoo kann es übersetzen).
        """
        from .services import fetch_recipe

        locale = self._local_locale()
        match = re.search(r"/([a-z]{2})-([A-Za-z]{2})/", url)
        if not match or match.group(0).lower() == f"/{locale.lower()}/":
            return url
        foreign = match.group(0).strip("/")
        local_url = url.replace(match.group(0), f"/{locale}/", 1)
        try:
            self.store.upsert(await fetch_recipe(self.hass, local_url), local_url)
            return local_url
        except HomeAssistantError:
            pass
        ai = self._search_ai() or self.settings[CONF_AI_TASK]
        if ai:
            try:
                answer = await async_ask(self.hass, ai, "Essensplaner Cookidoo Landessprache", (
                    f"Das Cookidoo-Rezept „{dish['title']}“ ({url}) gibt es nicht in {locale}. Suche per Websuche "
                    f"ein gleichwertiges Gericht auf Cookidoo in {locale} (gleiche Art Gericht, ähnliche "
                    "Hauptzutaten). Nur echte Links. Antworte ausschließlich mit JSON: "
                    '{"url": "https://…" oder null, "title": "Titel in der Landessprache"}'))
                alt = str((answer or {}).get("url") or "").strip() if isinstance(answer, dict) else ""
                if alt and f"/{locale.lower()}/" in alt.lower():
                    recipe = self.store.upsert(await fetch_recipe(self.hass, alt), alt)
                    new_title = str(answer.get("title") or recipe.get("title") or "").strip()
                    if new_title:
                        dish["title"] = (new_title if new_title.endswith("(TM)") else f"{new_title} (TM)")[:60]
                    return alt
            except (AIError, HomeAssistantError) as err:
                _LOGGER.info("Keine Entsprechung in %s für %s: %s", locale, url, err)
        dish["foreign_language"] = foreign
        return url

    def _slot_conflict(self, dish: dict[str, Any], dishes: list[dict[str, Any]], total: int,
                       quota: bool = True) -> str | None:
        """Würde dieses Gericht eine Wochenvorgabe unerfüllbar machen? Dann gleich ablehnen, damit die KI
        passenden Ersatz liefert (statt es anzunehmen und hinterher zu melden, dass etwas fehlt).
        Wünsche sind ausgenommen."""
        if dish.get("wish"):
            return None
        settings = self.settings
        title = dish["title"]
        for limit in settings["dish_limits"]:
            if dish_matches(limit, title):
                hits = sum(1 for d in dishes if not d["wish"] and dish_matches(limit, d["title"]))
                if hits >= limit["max"]:
                    return (f"'{title}': schon {hits} {limit['label']} im Plan (höchstens {limit['max']}), "
                            "bitte eine andere Hauptzutat")
        if not quota:  # Zusatzvorschläge sind Alternativen, keine Wochenplätze
            return None
        free = total - len(dishes)  # freie Plätze einschließlich dieses Gerichts
        quick = settings[CONF_TIME_QUICK]

        def is_quick(d: dict[str, Any]) -> bool:
            return d["own_recipe"] or (d["time_min"] or 999) <= quick

        missing_quick = settings[CONF_QUICK_SHARE] - sum(1 for d in dishes if is_quick(d))
        if missing_quick >= free and not is_quick(dish):
            return (f"'{title}' dauert {dish['time_min']} Min.; es fehlen noch {missing_quick} Gerichte mit "
                    f"höchstens {quick} Min.")
        veg = settings[CONF_DIET][DIET_VEGETARIAN]
        wanted = len(dishes) + 1 if veg["mode"] == MODE_ALWAYS else (veg["count"] if veg["mode"] == MODE_COUNT else 0)
        missing_veg = wanted - sum(1 for d in dishes if d["meatless"])
        if missing_veg >= free and not dish["meatless"]:
            return f"'{title}' ist nicht fleischlos; es fehlen noch {missing_veg} fleischlose Gerichte"
        return None

    def _week_deficits(self, dishes: list[dict[str, Any]]) -> list[tuple[str, int, Any]]:
        """Welche Wochenvorgaben fehlen noch? (Regel, Anzahl, Prüffunktion)"""
        settings = self.settings
        out: list[tuple[str, int, Any]] = []
        diet = settings[CONF_DIET]
        n = len(dishes)

        def need(key: str) -> int:
            rule = diet[key]
            if rule["mode"] == MODE_ALWAYS:
                return n
            return rule["count"] if rule["mode"] == MODE_COUNT else 0

        checks = [
            ("fleischlose Gerichte", need(DIET_VEGETARIAN), lambda d: d["meatless"]),
            ("cholesterinarme Gerichte", need(DIET_LOW_CHOLESTEROL), lambda d: d["low_cholesterol"]),
            (f"Gerichte mit höchstens {settings[CONF_TIME_QUICK]} Min.",
             settings[CONF_QUICK_SHARE] if n >= settings[CONF_RECIPES_PER_WEEK] else 0,
             lambda d: d["own_recipe"] or (d["time_min"] or 999) <= settings[CONF_TIME_QUICK]),
        ]
        tm = settings[CONF_DEVICE_COUNTS].get(DEVICE_THERMOMIX)
        if tm:
            checks.append(("Thermomix-Gerichte", tm, lambda d: (urlparse(d.get("url") or "").hostname or "")
                           .removeprefix("www.") in THERMOMIX_SOURCES or "(TM)" in d["title"]))
        for label, wanted, fn in checks:
            have = sum(1 for d in dishes if fn(d))
            if have < wanted:
                out.append((label, wanted - have, fn))
        for limit in settings["dish_limits"]:
            hits = [d for d in dishes if not d["wish"] and dish_matches(limit, d["title"])]
            if len(hits) > limit["max"]:
                out.append((f"zu viele {limit['label']}", len(hits) - limit["max"],
                            lambda d, lim=limit: not dish_matches(lim, d["title"])))
        return out

    def _plan_meta(self) -> dict[str, Any]:
        """Woche, für die gerade Vorschläge gesammelt werden."""
        settings = self.settings
        now = dt_util.now()
        plan_at = last_weekday_at(now + timedelta(minutes=1), settings[CONF_PLAN_DAY],
                                  _parse_time(settings[CONF_PLAN_TIME]))
        meta = week_meta(plan_at, settings)
        if dt_util.parse_datetime(meta["deadline"]) <= now:
            # vor dem Planungstag: auf den kommenden Planungszeitpunkt rechnen (Freigaben, Auswahlschluss)
            meta = week_meta(next_weekday_at(now, settings[CONF_PLAN_DAY], _parse_time(settings[CONF_PLAN_TIME])),
                             settings)
        return meta

    def _carried(self) -> list[dict[str, Any]]:
        """Bereits eingekaufte, noch nicht gekochte Gerichte wandern in die neue Woche."""
        carried: list[dict[str, Any]] = []
        for dish in (self.boards.get("current") or {}).get("dishes", []):
            if dish["ingredients_ready"] and not dish["cooked_on"] and dish["choice"] in self.trip_keys:
                first = self.trip_keys[0]
                carried.append({**dish, "id": uuid.uuid4().hex[:8], "choice": first, "tip": first,
                                "carried": True, "on_list": False})
        return carried

    async def _context(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Wünsche, Kalender und Geschmacksprofil für eine Planungsrunde laden."""
        settings = self.settings
        wishes = await self._wishes()
        self._wish_texts = {_norm_title(w["text"]) for w in wishes}
        self._wish_hosts = {(urlparse(u).hostname or "").removeprefix("www.")
                            for w in wishes for u in re.findall(r"https?://\S+", f"{w['text']} {w['note']}")}
        self._labels = {r["label"] for r in settings[CONF_CAL_RULES]}
        start, end = date.fromisoformat(meta["start"]), date.fromisoformat(meta["end"])
        return {"wishes": wishes, "calendar": await self._calendar_context(start, end),
                "profile": self._profile_context(dt_util.now().date())}

    @staticmethod
    def _open_wishes(wishes: list[dict[str, Any]], dishes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        done = {_norm_title(d["wish"]) for d in dishes if d.get("wish")} | {
            _norm_title(d["title"]) for d in dishes if d.get("wish")}
        return [w for w in wishes if _norm_title(w["text"]) not in done]

    def _drop_unfit(self, dishes: list[dict[str, Any]], excluded: set[str]) -> list[str]:
        """Plan voll, aber Vorgaben offen: unpassende Gerichte (keine Wünsche, nicht übernommen) austauschen."""
        feedback = []
        for label, missing, fn in self._week_deficits(dishes):
            for dish in reversed(list(dishes)):
                if missing <= 0:
                    break
                # Gewähltes (Auswahl, laufende Woche) bleibt immer stehen
                if (not dish["wish"] and not dish.get("carried") and dish["choice"] not in self.trip_keys
                        and not fn(dish)):
                    dishes.remove(dish)
                    excluded.add(_norm_title(dish["title"]))
                    missing -= 1
            feedback.append(f"Es fehlen noch {label}.")
        return feedback

    async def _accept(self, proposals: list[Any], dishes: list[dict[str, Any]], excluded: set[str],
                      rejected: list[str], total: int, quota: bool = True) -> list[dict[str, Any]]:
        """Vorschläge prüfen (Link, Suche, Regeln) und passende an dishes anhängen."""
        today = dt_util.now().date()
        added: list[dict[str, Any]] = []
        for prop in proposals:
            if len(dishes) >= total:
                break
            if not isinstance(prop, dict):
                continue
            taken = {_norm_title(d["title"]) for d in dishes} | excluded
            try:
                dish, reason = await self._check_dish(prop, taken, today)
            except Exception as err:  # noqa: BLE001 - ein kaputter Vorschlag darf den Lauf nicht abbrechen
                _LOGGER.warning("Vorschlag nicht prüfbar: %s", err, exc_info=True)
                dish, reason = None, f"'{_short(str(prop.get('title') or '?'))}': ungültige Daten"
            if not reason:
                reason = self._slot_conflict(dish, dishes, total, quota)
            if reason:
                _LOGGER.info("Vorschlag verworfen: %s", reason)
                rejected.append(reason)
                excluded.add(_norm_title(str(prop.get("title") or "")))
                continue
            dishes.append(dish)
            added.append(dish)
        await self._assess_dishes(added)
        return added

    def _prompt(self, meta: dict[str, Any], ctx: dict[str, Any], dishes: list[dict[str, Any]],
                excluded: set[str], feedback: list[str], notes: str | None, need: int) -> str:
        return board_prompt(
            settings=self.settings, meta=meta, need=need, trips=self._trip_texts(meta), keep=dishes,
            wishes=self._open_wishes(ctx["wishes"], dishes), calendar=ctx["calendar"],
            profile=ctx["profile"], notes=notes, feedback=feedback, excluded=sorted(excluded),
            today=dt_util.now().date())

    async def _publish(self, meta: dict[str, Any], dishes: list[dict[str, Any]], wishes: list[dict[str, Any]],
                       problems: list[str], *, rounds: int, source: str, excluded: set[str],
                       notify: bool) -> dict[str, Any]:
        """Tafel ablegen, erfüllte Wünsche abhaken und (falls gewünscht) melden."""
        cur = self.boards.get("current")
        if cur and cur.get("id") == meta["id"]:
            # Lauf hat den Auswahlschluss überdauert: die abgeschlossene Woche nicht überschreiben
            raise HomeAssistantError(f"KW {meta['kw']} ist bereits abgeschlossen, Vorschläge verworfen.")
        total = self.settings[CONF_RECIPES_PER_WEEK]
        dishes = [d for d in dishes if d.get("carried")] + sorted(
            [d for d in dishes if not d.get("carried")], key=lambda d: (not d["wish"],))
        for nr, dish in enumerate(dishes, 1):
            dish["nr"] = nr
        old = self.boards.get("next") or {}
        board = {**meta, "created": old.get("created") if old.get("id") == meta["id"] else None,
                 "dishes": dishes, "rounds": rounds, "problems": problems[-30:], "source": source,
                 "excluded": sorted(excluded)[-80:],
                 "deficits": [label for label, *_ in self._week_deficits(dishes)]}
        board["created"] = board["created"] or dt_util.now().isoformat()
        board["notified"] = bool(old.get("notified")) and old.get("id") == meta["id"]
        self.boards["next"] = board
        self._changed()
        open_wishes = self._open_wishes(wishes, dishes)
        open_uids = {w["uid"] for w in open_wishes}
        fulfilled = [w for w in wishes if w["uid"] not in open_uids]
        for wish in fulfilled:  # nicht eingeplante Wünsche bleiben für nächste Woche stehen
            await self.hass.services.async_call(
                "todo", "remove_item", {"entity_id": self.wishes_entity(), "item": wish["uid"]},
                blocking=True)
        if notify and not board["notified"]:
            board["notified"] = True
            self._changed()
            carried = sum(1 for d in dishes if d.get("carried"))
            meatless = sum(1 for d in dishes if d["meatless"])
            chol = sum(1 for d in dishes if d["low_cholesterol"])
            wished = sum(1 for d in dishes if d["wish"])
            st = self.settings
            text = (msg(st, "new", n=len(dishes), kw=meta["kw"], meatless=meatless, chol=chol)
                    + (msg(st, "wishes", n=wished) if wished else "")
                    + (msg(st, "wish_missing", n=len(open_wishes)) if open_wishes else "")
                    + (msg(st, "carried", n=carried) if carried else "") + msg(st, "new_end"))
            if len(dishes) < total or board["deficits"]:
                text += msg(st, "hint", n=len(dishes), total=total) + (
                    msg(st, "open", list=", ".join(board["deficits"])) if board["deficits"] else "") + "."
            await self.async_notify(msg(st, "new_title"), text)
        return {"kw": meta["kw"], "count": len(dishes), "need": max(0, total - len(dishes)),
                "rounds": rounds, "problems": board["problems"], "deficits": board["deficits"],
                "open_wishes": [w["text"] for w in open_wishes],
                "dishes": [d["title"] for d in dishes]}

    async def async_generate(self, notes: str | None = None, force: bool = False) -> dict[str, Any]:
        """Vorschläge für die kommende Woche von der KI holen, prüfen und als Tafel ablegen."""
        if self.busy:
            raise HomeAssistantError("Die Vorschläge werden gerade schon erstellt.")
        settings = self.settings
        ai = self._search_ai() or settings[CONF_AI_TASK]
        if not ai:
            raise ServiceValidationError("Keine KI ausgewählt (Essensplaner → Konfigurieren → KI).")
        meta = self._plan_meta()
        existing = self.boards.get("next")
        if existing and existing["id"] == meta["id"] and not force:
            return {"skipped": True, "reason": f"Vorschläge für KW {meta['kw']} gibt es schon."}
        return await self._run(self._generate(meta, notes))

    async def _run(self, job: Any) -> dict[str, Any]:
        if self.busy:
            job.close()
            raise HomeAssistantError("Die Vorschläge werden gerade schon erstellt.")
        self.busy = True
        async_dispatcher_send(self.hass, SIGNAL_BOARD_UPDATED)  # Karte zeigt „läuft …“, auch auf anderen Geräten
        self._frozen = self.settings
        self._budget = SEARCH_BUDGET
        try:
            return await job
        finally:
            self.busy = False
            async_dispatcher_send(self.hass, SIGNAL_BOARD_UPDATED)
            self._frozen = None
            if self.reload_pending:  # inzwischen gespeicherte Einstellungen jetzt übernehmen
                self.reload_pending = False
                self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
            elif not self._in_tick:
                # während des Laufs fällig gewordene Schritte (z. B. Auswahlschluss) gleich nachholen
                self.hass.async_create_task(self.async_tick(dt_util.now()), eager_start=False)

    async def _generate(self, meta: dict[str, Any], notes: str | None, keep: list[dict[str, Any]] | None = None,
                        excluded: set[str] | None = None) -> dict[str, Any]:
        total = self.settings[CONF_RECIPES_PER_WEEK]
        dishes = list(keep) if keep is not None else self._carried()
        ctx = await self._context(meta)
        self._replaced = []
        excluded = set(excluded or ()) | {
            _norm_title(d["title"]) for d in (self.boards.get("current") or {}).get("dishes", [])}
        rejected, rounds = await self._fill(meta, ctx, dishes, excluded, total, notes)
        return await self._publish(meta, dishes, ctx["wishes"], rejected + self._replaced, rounds=rounds,
                                   source="ha", excluded=excluded, notify=True)

    async def _fill(self, meta: dict[str, Any], ctx: dict[str, Any], dishes: list[dict[str, Any]],
                    excluded: set[str], total: int, notes: str | None,
                    quota: bool = True) -> tuple[list[str], int]:
        """KI so lange fragen, bis `dishes` voll ist und die Wochenvorgaben passen (höchstens MAX_PLAN_ROUNDS).

        quota=False (Zusatzvorschläge): nur auffüllen, Wochenvorgaben wie Schnell-Anteil oder fleischlose
        Gerichte gelten dann nicht, weil die neuen Gerichte Alternativen sind und keine Wochenplätze."""
        def unmet() -> bool:
            return quota and bool(self._week_deficits(dishes))

        rejected: list[str] = []
        feedback: list[str] = []
        rounds = 0
        for rounds in range(1, MAX_PLAN_ROUNDS + 1):
            if len(dishes) >= total:
                if not unmet():
                    break
                feedback.extend(self._drop_unfit(dishes, excluded))
                if len(dishes) >= total or rounds == MAX_PLAN_ROUNDS:
                    break
            need = total - len(dishes)
            # mehr Ideen anfordern als nötig: ein Teil fällt bei der Prüfung erfahrungsgemäß durch
            prompt = self._prompt(meta, ctx, dishes, excluded, feedback + rejected[-12:], notes,
                                  min(need + max(3, need // 2), 15))
            try:
                answer = await self._ask_proposals(prompt)
            except AIError as err:
                if dishes:
                    rejected.append(str(err))
                    break
                if not self._failures.get(meta["id"]):  # nur beim ersten Fehlschlag der Woche melden
                    await self.async_notify(msg(self.settings, "error_title"), msg(self.settings, "error", err=err))
                raise HomeAssistantError(str(err)) from err
            proposals = answer.get("dishes", []) if isinstance(answer, dict) else []
            feedback = []
            await self._accept(proposals, dishes, excluded, rejected, total, quota)
            if len(dishes) >= total and not unmet():
                break
        return rejected, rounds

    # ------------------------------------------------ neu planen und tauschen ---
    def _check_ai(self) -> None:
        if self.busy:
            raise HomeAssistantError("Die Vorschläge werden gerade schon erstellt.")
        if not (self._search_ai() or self.settings[CONF_AI_TASK]):
            raise ServiceValidationError("Keine KI ausgewählt (Essensplaner → Konfigurieren → KI).")

    async def async_more(self, count: int = 5, notes: str | None = None) -> dict[str, Any]:
        """Weitere Gerichte zur Auswahl dazuholen, Vorhandenes bleibt.

        Mit Vorschlägen für die kommende Woche kommen sie dort dazu, sonst in die laufende Woche
        (ohne Einkauf, bis man eines wählt). Ohne beides wird jetzt (vorzeitig) geplant.
        """
        self._check_ai()
        for key in ("next", "current"):
            board = self.boards.get(key)
            if board:
                return await self._run(self._more(key, board, max(1, min(int(count), 10)), notes))
        return await self._run(self._generate(self._plan_meta(), notes))

    async def _more(self, key: str, board: dict[str, Any], count: int, notes: str | None) -> dict[str, Any]:
        meta = {k: board[k] for k in ("id", "kw", "year", "start", "end", "deadline", "release_at", "released")
                if k in board}
        ctx = await self._context(meta)
        self._replaced = []
        stale: list[dict[str, Any]] = []
        if key == "current":
            # nicht genommene Kandidaten vom letzten Mal machen Platz für die neuen
            stale = [d for d in board["dishes"] if d["choice"] == CHOICE_NONE and not d["cooked_on"]]
            board["dishes"] = [d for d in board["dishes"] if d not in stale]
        before = list(board["dishes"])
        excluded = set(board.get("excluded") or []) | {_norm_title(d["title"]) for d in before + stale}
        if key == "next":
            excluded |= {_norm_title(d["title"]) for d in (self.boards.get("current") or {}).get("dishes", [])}
        dishes = list(before)
        rejected, _ = await self._fill(meta, ctx, dishes, excluded, len(before) + count, notes, quota=False)
        new = [d for d in dishes if d not in before][:count]
        nr = max((d["nr"] for d in before), default=0)
        for dish in new:
            nr += 1
            dish["nr"] = nr
            if key == "current":
                dish["choice"] = CHOICE_NONE
        board["dishes"] = before + new  # Vorhandenes bleibt in jedem Fall stehen
        board["excluded"] = sorted(excluded)[-80:]
        if key == "next":
            board["deficits"] = [label for label, *_ in self._week_deficits(board["dishes"])]
        self._changed()
        if not new:
            raise HomeAssistantError("Keine passenden weiteren Gerichte gefunden. " + "; ".join(rejected[-3:]))
        return {"board": key, "added": [d["title"] for d in new], "problems": rejected[-10:]}

    async def async_swap(self, dish_id: str, notes: str | None = None) -> dict[str, Any]:
        """Ein Gericht durch ein anderes ersetzen – in den Vorschläge oder in der laufenden Woche."""
        self._check_ai()
        key, board, dish = self.find(dish_id)
        if dish["cooked_on"]:
            raise ServiceValidationError("Gekochte Gerichte lassen sich nicht tauschen.")
        return await self._run(self._swap(key, board, dish, notes))

    async def _swap(self, key: str, board: dict[str, Any], dish: dict[str, Any], notes: str | None) -> dict[str, Any]:
        meta = {k: board[k] for k in ("id", "kw", "year", "start", "end", "deadline", "release_at", "released")
                if k in board}
        ctx = await self._context(meta)
        self._replaced = []
        others = [d for d in board["dishes"] if d is not dish]
        excluded = set(board.get("excluded") or []) | {_norm_title(dish["title"])}
        dishes = list(others)
        rejected, _ = await self._fill(meta, ctx, dishes, excluded, len(others) + 1, notes)
        new = next((d for d in dishes if d not in others), None)
        if new is None:
            raise HomeAssistantError("Kein passendes anderes Gericht gefunden. " + "; ".join(rejected[-3:]))
        if dish["on_list"]:
            await async_remove_tag(self.hass, self._list_entity(), dish["title"])
        new.update(nr=dish["nr"], choice=dish["choice"], tip=dish["choice"] if dish["choice"] in self.trip_keys
                   else new.get("tip"))
        board["dishes"][board["dishes"].index(dish)] = new
        board["excluded"] = sorted(excluded)[-80:]
        if key == "next":
            board["deficits"] = [label for label, *_ in self._week_deficits(board["dishes"])]
        report = await self.async_sync()
        return {"replaced": dish["title"], "dish": new, "problems": rejected[-10:], **report}

    # --------------------------------------------------- externe KI (Aktionen) ---
    def _next_for(self, meta: dict[str, Any]) -> dict[str, Any] | None:
        board = self.boards.get("next")
        return board if board and board["id"] == meta["id"] else None

    def _due(self) -> tuple[bool, str, str]:
        """Ist gerade eine Planung fällig? Liefert (fällig, Grund, nächster Planungszeitpunkt)."""
        settings = self.settings
        now = dt_util.now()
        plan_at = last_weekday_at(now + timedelta(minutes=1), settings[CONF_PLAN_DAY],
                                  _parse_time(settings[CONF_PLAN_TIME]))
        meta = week_meta(plan_at, settings)
        upcoming = next_weekday_at(now, settings[CONF_PLAN_DAY], _parse_time(settings[CONF_PLAN_TIME]))
        if dt_util.parse_datetime(meta["deadline"]) <= now:
            return False, "Noch keine Planung fällig.", upcoming.isoformat()
        cur, board = self.boards.get("current"), self._next_for(meta)
        if cur and cur["id"] == meta["id"]:
            return False, "Die Woche ist schon abgeschlossen.", upcoming.isoformat()
        if board and board.get("notified"):
            return False, f"Die Vorschläge für KW {meta['kw']} sind fertig.", upcoming.isoformat()
        return True, f"Vorschläge für KW {meta['kw']} werden gebraucht.", plan_at.isoformat()

    async def async_planning_brief(self, notes: str | None = None, restart: bool = False) -> dict[str, Any]:
        """Auftrag für eine externe KI: dieselben Regeln und Hinweise, die die eingebaute KI bekommt."""
        due, why, plan_at = self._due()
        if not due and not restart:
            return {"due": False, "reason": why, "next_planning": plan_at, "need": 0,
                    "how_to_submit": "Nichts zu tun, Lauf beenden."}
        if not due:
            why = "Von Hand neu begonnen (außerhalb des Zeitplans)." 
        meta = self._plan_meta()
        total = self.settings[CONF_RECIPES_PER_WEEK]
        board = None if restart else self._next_for(meta)
        dishes = list(board["dishes"]) if board else self._carried()
        excluded = set(board.get("excluded", [])) if board else {
            _norm_title(d["title"]) for d in (self.boards.get("current") or {}).get("dishes", [])}
        ctx = await self._context(meta)
        need = max(0, total - len(dishes))
        feedback = [f"Es fehlen noch {label}." for label, *_ in self._week_deficits(dishes)] if board else []
        feedback += (board or {}).get("problems", [])[-12:]
        prompt = self._prompt(meta, ctx, dishes, excluded, feedback, notes, min(need + max(3, need // 2), 15))
        return {
            "due": True, "reason": why,
            "kw": meta["kw"], "start": meta["start"], "end": meta["end"], "deadline": meta["deadline"],
            "total": total, "planned": len(dishes), "need": need, "deficits": (board or {}).get("deficits", []),
            "prompt": prompt,
            "how_to_submit": (
                "Recherchiere die Rezepte im Web und rufe dann die Aktion meal_planner_ai.submit_proposals mit "
                "dishes = Liste der Gerichte im JSON-Format aus dem Auftrag auf (ohne die äußere Klammer "
                "{\"dishes\": …}). Gib zu jedem Gericht den direkten Rezeptlink aus deinem Suchergebnis an. "
                "Die Antwort nennt, wie viele noch fehlen (need), welche Vorgaben offen sind (deficits) und "
                "warum Vorschläge verworfen wurden (problems). Ist need größer als 0, schlage weitere Gerichte vor "
                "und rufe die Aktion erneut auf; höchstens viermal. Setze beim letzten Aufruf final: true."),
        }

    async def async_submit_proposals(self, proposals: list[Any], *, final: bool = False,
                                     restart: bool = False) -> dict[str, Any]:
        """Vorschläge einer externen KI wie die der eingebauten KI prüfen und in die nächste Tafel übernehmen."""
        if self.busy:
            raise HomeAssistantError("Die Vorschläge werden gerade schon erstellt.")
        meta = self._plan_meta()
        cut = max(0, len(proposals) - MAX_PROPOSALS)
        result = await self._run(self._submit(meta, proposals[:MAX_PROPOSALS], final=final, restart=restart))
        if cut:
            result["ignored"] = f"{cut} Vorschläge über dem Limit von {MAX_PROPOSALS} pro Aufruf nicht geprüft."
        return result

    async def _submit(self, meta: dict[str, Any], proposals: list[Any], *, final: bool,
                      restart: bool) -> dict[str, Any]:
        total = self.settings[CONF_RECIPES_PER_WEEK]
        board = None if restart else self._next_for(meta)
        dishes = list(board["dishes"]) if board else self._carried()
        excluded = set(board.get("excluded", [])) if board else {
            _norm_title(d["title"]) for d in (self.boards.get("current") or {}).get("dishes", [])}
        problems = list((board or {}).get("problems", []))
        rounds = (board or {}).get("rounds", 0) + 1
        ctx = await self._context(meta)
        self._replaced = []
        rejected: list[str] = []
        before = {d["id"] for d in dishes}
        if len(dishes) >= total and self._week_deficits(dishes):
            self._drop_unfit(dishes, excluded)
        await self._accept(proposals, dishes, excluded, rejected, total)
        added = [d["title"] for d in dishes if d["id"] not in before]
        removed = [t for t in (board or {}).get("dishes", []) if t["id"] not in {d["id"] for d in dishes}]
        complete = len(dishes) >= total and not self._week_deficits(dishes)
        result = await self._publish(
            meta, dishes, ctx["wishes"], problems + rejected + self._replaced, rounds=rounds, source="external",
            excluded=excluded, notify=complete or final)
        return {**result, "accepted": added, "removed": [d["title"] for d in removed],
                "rejected": rejected + self._replaced, "complete": complete,
                "next_step": ("Fertig." if complete or final else
                              f"Es fehlen noch {result['need']} Gericht(e)"
                              + (f", offen: {', '.join(result['deficits'])}" if result["deficits"] else "")
                              + ". Weitere Gerichte vorschlagen und submit_proposals erneut aufrufen.")}

    # ---------------------------------------------------------- Meldungen ---
    async def async_notify(self, title: str, message: str) -> None:
        settings = self.settings
        path = settings[CONF_DASHBOARD_PATH] or None
        for target in settings[CONF_NOTIFY]:
            service = target.removeprefix("notify.")
            if not self.hass.services.has_service("notify", service):
                _LOGGER.warning("Benachrichtigung %s gibt es nicht", target)
                continue
            data: dict[str, Any] = {"title": title, "message": message}
            if path:
                data["data"] = {"clickAction": path, "url": path, "tag": "meal_planner_ai"}
            try:
                await self.hass.services.async_call("notify", service, data, blocking=True)
            except HomeAssistantError as err:
                _LOGGER.warning("Benachrichtigung an %s fehlgeschlagen: %s", target, err)

    # ---------------------------------------------------------- Zeitplan ---
    async def async_tick(self, now: datetime) -> list[str]:
        """Fällige Schritte ausführen (auch zum Nachholen nach einem Neustart)."""
        if self._tick_lock.locked() or self.busy:
            return []  # läuft schon; ein Vorschlagslauf holt den Tick nach seinem Ende nach
        async with self._tick_lock:
            self._in_tick = True
            try:
                return await self._tick(now)
            finally:
                self._in_tick = False

    async def _tick(self, now: datetime) -> list[str]:
        settings = self.settings
        done: list[str] = []
        nxt = self.boards.get("next")
        if nxt and now >= dt_util.parse_datetime(nxt["deadline"]):
            try:
                await self.async_finalize()
                done.append("finalize")
            except HomeAssistantError as err:
                _LOGGER.warning("Auswahlschluss nicht vollständig: %s", err)
        due = False
        for key in ("next", "current"):
            board = self.boards.get(key)
            for trip_key, at in ((board or {}).get("release_at") or {}).items():
                if not board["released"].get(trip_key) and now >= dt_util.parse_datetime(at):
                    board["released"][trip_key] = True
                    due = True
        if due:
            try:
                await self.async_sync()
                done.append("release")
            except HomeAssistantError as err:
                _LOGGER.warning("Einkauf nicht freigegeben (Liste nicht erreichbar?): %s", err)
        plan_at = last_weekday_at(now + timedelta(seconds=1), settings[CONF_PLAN_DAY],
                                  _parse_time(settings[CONF_PLAN_TIME]))
        meta = week_meta(plan_at, settings)
        nxt = self.boards.get("next")
        cur = self.boards.get("current")
        already = (nxt and nxt["id"] == meta["id"]) or (cur and cur["id"] == meta["id"])
        external = settings["proposals_from"] == PROPOSALS_EXTERNAL
        late = now >= plan_at + timedelta(hours=EXTERNAL_FALLBACK_HOURS)
        if external and nxt and nxt["id"] == meta["id"] and not nxt.get("notified") and late:
            # externe KI hat angefangen, aber nicht abgeschlossen: melden, was da ist
            try:
                await self._run(self._submit(meta, [], final=True, restart=False))
                done.append("external_final")
            except HomeAssistantError as err:
                _LOGGER.warning("Vorschläge der externen KI nicht abschließbar: %s", err)
            return done
        if external and not already and plan_at <= now < dt_util.parse_datetime(meta["deadline"]):
            # externe KI liefert über meal_planner_ai.submit_proposals; bleibt sie aus, springt die KI in HA ein
            if now < plan_at + timedelta(hours=EXTERNAL_FALLBACK_HOURS):
                return done
            if not (self._search_ai() or settings[CONF_AI_TASK]):
                if self._missed != meta["id"]:
                    self._missed = meta["id"]
                    await self.async_notify(msg(settings, "missing_title"), msg(settings, "missing", kw=meta["kw"]))
                return done
            _LOGGER.warning("Externe KI hat nichts geliefert, KI in Home Assistant springt ein")
        if (not already and (self._search_ai() or settings[CONF_AI_TASK])
                and plan_at <= now < dt_util.parse_datetime(meta["deadline"])):
            if self._failures.get(meta["id"], 0) >= MAX_FAILURES:
                return done  # KI dauerhaft gestört: bis zur nächsten Woche nicht stündlich weiter versuchen
            try:
                await self.async_generate()
                done.append("generate")
            except HomeAssistantError as err:
                self._failures[meta["id"]] = self._failures.get(meta["id"], 0) + 1
                _LOGGER.error("Wochenvorschläge fehlgeschlagen (%s. Versuch): %s", self._failures[meta["id"]], err)
        return done
