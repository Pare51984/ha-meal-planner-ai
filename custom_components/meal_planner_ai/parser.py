"""Rezeptdaten aus HTML lesen (ohne Home-Assistant-Abhängigkeit, damit testbar)."""

from __future__ import annotations

import re
from typing import Any

from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import WebsiteNotImplementedError

_KCAL_RE = re.compile(r"(\d+(?:[.,]\d+)?)")



def _safe_url(value: object) -> str | None:
    """Nur echte Webadressen übernehmen (keine javascript:- oder data:-Links aus fremden Seiten)."""
    text = str(value or "").strip()
    return text if text.lower().startswith(("http://", "https://")) else None

def _safe(scraper: Any, name: str) -> Any:
    """Ein Feld lesen; fehlende Angaben liefern None statt eines Fehlers."""
    method = getattr(scraper, name, None)
    if method is None:
        return None
    try:
        value = method()
    except Exception:  # noqa: BLE001 - jede Seite liefert andere Felder
        return None
    if value in ("", [], {}):
        return None
    return value


def _kcal(nutrients: dict[str, str] | None) -> float | None:
    """kcal pro Portion aus den Nährwerten herausziehen."""
    if not nutrients:
        return None
    raw = nutrients.get("calories")
    if not raw:
        return None
    match = _KCAL_RE.search(str(raw))
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    # Manche Seiten geben kJ an; grob erkennen und umrechnen.
    if "kj" in str(raw).lower() and "kcal" not in str(raw).lower():
        value = value / 4.184
    return round(value)


def parse_recipe(html: str, url: str) -> dict[str, Any]:
    """HTML einer Rezeptseite in ein einfaches Rezept-Dictionary umwandeln."""
    try:
        scraper = scrape_html(html, url, supported_only=True)
        known_site = True
    except WebsiteNotImplementedError:
        # Unbekannte Seite: allgemeiner Modus über strukturierte Rezeptdaten.
        scraper = scrape_html(html, url, supported_only=False)
        known_site = False

    nutrients = _safe(scraper, "nutrients")
    groups = _safe(scraper, "ingredient_groups")
    group_list = None
    if groups and len(groups) > 1:
        group_list = [
            {"name": g.purpose, "ingredients": list(g.ingredients)} for g in groups
        ]

    recipe = {
        "title": _safe(scraper, "title"),
        "author": _safe(scraper, "author"),
        "source_url": _safe_url(_safe(scraper, "canonical_url")) or url,
        "host": _safe(scraper, "host"),
        "known_site": known_site,
        "image": _safe(scraper, "image"),
        "yields": _safe(scraper, "yields"),
        "total_time_min": _safe(scraper, "total_time"),
        "prep_time_min": _safe(scraper, "prep_time"),
        "cook_time_min": _safe(scraper, "cook_time"),
        "kcal_per_serving": _kcal(nutrients),
        "nutrients": nutrients,
        "ingredients": _safe(scraper, "ingredients") or [],
        "ingredient_groups": group_list,
        "instructions": _safe(scraper, "instructions_list") or [],
        "dietary_restrictions": _safe(scraper, "dietary_restrictions"),
        "equipment": _safe(scraper, "equipment"),
    }

    # Chefkoch hängt den Autor an den Titel ("Cremige Kürbis-Gnocchi von bethsiii.")
    if recipe["title"] and recipe["author"]:
        suffix = f" von {recipe['author']}".lower()
        title = str(recipe["title"]).rstrip(". ").rstrip()
        if title.lower().endswith(suffix.rstrip(". ")):
            recipe["title"] = title[: -len(suffix.rstrip(". "))].rstrip(" -–")

    if not recipe["title"] or not recipe["ingredients"]:
        raise ValueError("Auf der Seite wurde kein vollständiges Rezept gefunden.")
    return recipe
