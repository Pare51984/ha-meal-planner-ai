"""Rezeptspeicher im HA-eigenen Speicher (.storage/meal_planner_ai.recipes)."""

from __future__ import annotations

from datetime import date
import hashlib
import re
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    RATING_MAX,
    RATING_SCALE_KEY,
    RATING_MIN,
    STATUS_BOUGHT,
    STATUS_COOKED,
    STATUS_NEW,
    STORAGE_KEY_RECIPES,
    STORAGE_VERSION,
)


def normalize_url(url: str) -> str:
    """Für den Vergleich: ohne Protokoll, www, Query und Schrägstrich am Ende."""
    url = re.sub(r"^https?://(www\.)?", "", url.strip().lower())
    return url.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def recipe_id_for(url: str) -> str:
    return hashlib.sha1(normalize_url(url).encode(), usedforsecurity=False).hexdigest()[:12]


def title_id_for(title: str) -> str:
    return "t" + hashlib.sha1(title.strip().lower().encode(), usedforsecurity=False).hexdigest()[:11]


def _empty_history() -> dict[str, Any]:
    return {"status": STATUS_NEW, "rating": None, "cooked_on": [], "bought_on": None, "note": None}


LEGACY_DOMAIN = "essensplaner"  # frühere Kennung der Integration (bis 0.35)


async def async_load_with_legacy(hass: HomeAssistant, store: Store, key: str) -> dict[str, Any] | None:
    """Gespeicherte Daten laden; gibt es noch keine, die der früheren Kennung „essensplaner“ übernehmen."""
    data = await store.async_load()
    if data is None and "." in key:
        legacy = Store(hass, STORAGE_VERSION, f"{LEGACY_DOMAIN}.{key.split('.', 1)[1]}")
        data = await legacy.async_load()
        if data is not None:
            await store.async_save(data)
    return data


class RecipeStore:
    """Hält alle Rezepte samt Verlauf im Speicher und sichert verzögert."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY_RECIPES)
        self.recipes: dict[str, dict[str, Any]] = {}
        self.meta: dict[str, Any] = {}

    async def async_load(self) -> None:
        data = await async_load_with_legacy(self._hass, self._store, STORAGE_KEY_RECIPES) or {}
        self.recipes = data.get("recipes", {})
        self.meta = data.get("meta", {})
        if self.meta.get(RATING_SCALE_KEY) != RATING_MAX:
            self._migrate_ratings()

    def _migrate_ratings(self) -> None:
        """Einmalig: Bewertungen von 5 auf 10 Sterne umrechnen (mal 2), damit „gut“ gut bleibt.

        Betrifft den Verlauf jedes Rezepts und die Gerichte der gespeicherten Wochen samt
        Rückgängig-Stand. Der Merker verhindert eine zweite Umrechnung.
        """
        def double(value: Any) -> Any:
            return min(RATING_MAX, int(value) * 2) if isinstance(value, (int, float)) and value else value

        for rec in self.recipes.values():
            hist = rec.get("history")
            if hist:
                hist["rating"] = double(hist.get("rating"))
        boards = self.meta.get("board")
        for board in (boards.values() if isinstance(boards, dict) else []):
            dishes = board.get("dishes") if isinstance(board, dict) else None
            for dish in dishes or []:
                if not isinstance(dish, dict):
                    continue
                dish["rating"] = double(dish.get("rating"))
                before = dish.get("before_cooked")
                if isinstance(before, dict):
                    before["rating"] = double(before.get("rating"))
                    before["dish_rating"] = double(before.get("dish_rating"))
        self.meta[RATING_SCALE_KEY] = RATING_MAX
        self._save()

    def _data(self) -> dict[str, Any]:
        return {"recipes": self.recipes, "meta": self.meta}

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 2)

    async def async_flush(self) -> None:
        """Sofort sichern (beim Entladen, damit nichts verloren geht)."""
        await self._store.async_save(self._data())

    def set_fields(self, recipe_id: str, **fields: Any) -> dict[str, Any]:
        """Zusatzfelder (z. B. KI-Ergebnisse) an einem Rezept speichern."""
        self.recipes[recipe_id].update(fields)
        self._save()
        return self.recipes[recipe_id]

    def set_meta(self, key: str, value: Any) -> None:
        self.meta[key] = value
        self._save()

    # ------------------------------------------------------------ lesen ---
    def get(self, recipe_id: str) -> dict[str, Any] | None:
        return self.recipes.get(recipe_id)

    def find(self, recipe_id: str | None = None, url: str | None = None,
             title: str | None = None) -> dict[str, Any] | None:
        if recipe_id and recipe_id in self.recipes:
            return self.recipes[recipe_id]
        if url:
            rid = recipe_id_for(url)
            if rid in self.recipes:
                return self.recipes[rid]
            norm = normalize_url(url)
            for rec in self.recipes.values():
                if normalize_url(rec.get("source_url") or "") == norm:
                    return rec
        if title:
            wanted = title.strip().lower()
            for rec in self.recipes.values():
                if (rec.get("title") or "").strip().lower() == wanted:
                    return rec
        return None

    # --------------------------------------------------------- schreiben ---
    def upsert(self, recipe: dict[str, Any], requested_url: str) -> dict[str, Any]:
        """Rezept anlegen oder Inhalt aktualisieren; der Verlauf bleibt erhalten."""
        existing = self.find(url=recipe.get("source_url")) or self.find(url=requested_url) \
            or self.find(title=recipe.get("title"))
        if existing:
            rid = existing["id"]
            history = existing.get("history") or _empty_history()
            imported_at = existing.get("imported_at")
        else:
            rid = recipe_id_for(recipe.get("source_url") or requested_url)
            history = _empty_history()
            imported_at = dt_util.now().isoformat()
        keep = {k: existing[k] for k in ("ai_diet", "ai_note", "ai_shopping") if existing and k in existing}
        stored = {
            **recipe,
            **keep,
            "id": rid,
            "imported_at": imported_at,
            "updated_at": dt_util.now().isoformat(),
            "history": history,
        }
        self.recipes[rid] = stored
        self._save()
        return stored

    def delete(self, recipe_id: str) -> bool:
        if self.recipes.pop(recipe_id, None) is None:
            return False
        self._save()
        return True

    def update_history(
        self,
        recipe_id: str,
        *,
        rating: int | None = None,
        cooked_on: date | None = None,
        status: str | None = None,
        note: str | None = None,
        remove_cooked_on: date | None = None,
    ) -> dict[str, Any]:
        rec = self.recipes[recipe_id]
        hist = rec.setdefault("history", _empty_history())
        if rating is not None:  # 0 = Bewertung entfernen
            hist["rating"] = max(RATING_MIN, min(RATING_MAX, int(rating))) if int(rating) else None
        if remove_cooked_on is not None:
            hist["cooked_on"] = [d for d in hist["cooked_on"] if d != remove_cooked_on.isoformat()]
            if not hist["cooked_on"] and hist.get("status") == STATUS_COOKED:
                hist["status"] = "new"
        if cooked_on is not None:
            day = cooked_on.isoformat()
            if day not in hist["cooked_on"]:
                hist["cooked_on"].append(day)
                hist["cooked_on"].sort()
            hist["status"] = STATUS_COOKED
        if status is not None:
            hist["status"] = status
            if status == STATUS_BOUGHT:
                hist["bought_on"] = dt_util.now().date().isoformat()
        if note is not None:
            hist["note"] = note or None
        self._save()
        return rec

    def undo_cooked(self, recipe_id: str, day: str, before: dict[str, Any] | None) -> dict[str, Any]:
        """Versehentlich als gekocht markiert: Tag entfernen, vorherige Bewertung/Notiz/Status zurück."""
        rec = self.recipes[recipe_id]
        hist = rec.setdefault("history", _empty_history())
        hist["cooked_on"] = [d for d in hist["cooked_on"] if d != day]
        if before is not None:
            hist["rating"] = before.get("rating")
            hist["note"] = before.get("note")
            hist["status"] = before.get("status") or ("cooked" if hist["cooked_on"] else "new")
        elif not hist["cooked_on"] and hist.get("status") == STATUS_COOKED:
            hist["status"] = "new"
        self._save()
        return rec

    def add_stub(self, title: str, url: str | None) -> dict[str, Any]:
        """Platzhalter für übernommene Bewertungen ohne importiertes Rezept."""
        rid = recipe_id_for(url) if url else title_id_for(title)
        self.recipes[rid] = {
            "id": rid,
            "title": title,
            "source_url": url,
            "host": None,
            "stub": True,
            "ingredients": [],
            "instructions": [],
            "imported_at": dt_util.now().isoformat(),
            "updated_at": dt_util.now().isoformat(),
            "history": _empty_history(),
        }
        self._save()
        return self.recipes[rid]
