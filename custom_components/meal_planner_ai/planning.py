"""Einstellungen auswerten und Wochenpläne gegen die Vorgaben prüfen (ohne HA)."""

from __future__ import annotations

import re

from datetime import date
from typing import Any

from .classify import classify_diet, detect_devices, feasible
from .const import (
    AI_NONE,
    CONF_AI_SHOPPING,
    CONF_AI_TASK,
    CONF_CATALOG,
    CONF_STAPLES,
    CONF_TRIPS,
    CONF_CAL_RULES,
    MAX_CAL_RULES,
    DEFAULT_TRIPS,
    DEFAULTS,
    RELEASE_IMMEDIATE,
    RELEASE_TIMED,
    TRIP_KEYS,
    CONF_CUSTOM_DEVICES,
    CONF_CUSTOM_SOURCES,
    CONF_DEVICE_COUNTS,
    CONF_DEVICES,
    CONF_DIET,
    CONF_KCAL_MAX,
    CONF_KCAL_MAX_NO_SIDE,
    CONF_RECIPES_PER_WEEK,
    CONF_SHOPPING_LIST,
    CONF_SOURCES,
    DEFAULT_RECIPES_PER_WEEK,
    DEVICE_STOVE,
    DEVICE_THERMOMIX,
    DIET_VEGAN,
    DIET_VEGETARIAN,
    DIETS,
    MODE_ALWAYS,
    MODE_COUNT,
    MODE_OFF,
    REGION_SOURCES,
    CONF_REGION,
    SOFT_DIETS,
    STATUS_BOUGHT,
)


def trips_from_options(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Einkäufe normalisieren; alte Einstellungen (zweiter Einkauf Mo 18 Uhr) werden übernommen."""
    raw = options.get(CONF_TRIPS)
    if not raw:
        raw = [dict(t) for t in DEFAULT_TRIPS]
        if "late_weekday" in options or "late_time" in options:
            raw[1]["weekday"] = int(options.get("late_weekday", 0))
            raw[1]["time"] = str(options.get("late_time", "18:00"))
    trips = []
    for key, trip in zip(TRIP_KEYS, raw, strict=False):  # höchstens so viele Einkäufe wie Schlüssel
        release = trip.get("release", RELEASE_IMMEDIATE)
        trips.append({
            "key": key,
            "name": str(trip.get("name") or key).strip(),
            "release": release,
            "weekday": int(trip.get("weekday", 0)) if release == RELEASE_TIMED else None,
            "time": str(trip.get("time", "18:00"))[:5] if release == RELEASE_TIMED else None,
            "days": [int(d) for d in trip.get("days") or []],
        })
    return trips


_LIMIT_STOP = {"und", "oder", "mit", "ohne", "gericht", "gerichte", "essen", "speisen", "pro", "woche"}


def _stem(word: str) -> str:
    word = word.lower().replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
    for suffix in ("en", "e", "n", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


_MAX_RE = re.compile(r"^(?P<what>.+?)\s+(?:höchstens|maximal|max\.?|nicht mehr als)\s*(?P<n>\d+)\s*(?:x|×|mal)\b",
                     re.IGNORECASE)


def _kcal_aware(options: dict[str, Any]) -> bool:
    from .const import CONF_KCAL_AWARE, CONF_KCAL_MAX_NO_SIDE

    if CONF_KCAL_AWARE in options:
        return bool(options[CONF_KCAL_AWARE])
    return bool(options.get(CONF_KCAL_MAX) or options.get(CONF_KCAL_MAX_NO_SIDE))


def habits_from_options(options: dict[str, Any]) -> list[str]:
    """Essgewohnheiten als Liste (leere Felder fallen weg)."""
    from .const import CONF_HABITS, CONF_SOUP_MAX, DEFAULT_HABITS, MAX_HABITS

    habits = options.get(CONF_HABITS)
    if habits is None:
        old = options.get(CONF_SOUP_MAX)
        habits = DEFAULT_HABITS if old is None else [f"Suppen/Eintöpfe höchstens {int(old)}x pro Woche"]
    return [str(h).strip() for h in habits if str(h or "").strip()][:MAX_HABITS]


def dish_limits_from_habits(habits: list[str]) -> list[dict[str, Any]]:
    """Gewohnheiten wie "Suppen/Eintöpfe höchstens 1x pro Woche" zusätzlich hart prüfen (nur mit "höchstens")."""
    out = []
    for habit in habits:
        match = _MAX_RE.match(habit)
        if not match:
            continue
        label = match.group("what").strip()
        stems = [_stem(w) for w in re.findall(r"[^\W\d_]+", label) if w.lower() not in _LIMIT_STOP]
        if stems:
            out.append({"label": label, "max": int(match.group("n")), "stems": stems})
    return out


def _max_same_main(options: dict[str, Any]) -> int:
    from .const import CONF_MAX_SAME_MAIN, MAX_SAME_MAIN

    value = options.get(CONF_MAX_SAME_MAIN, MAX_SAME_MAIN)
    return MAX_SAME_MAIN if value is None else int(value)


def _main_limits(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Abwechslung: höchstens so viele Gerichte mit derselben Hauptzutat (0 = keine Grenze)."""
    from .const import MAIN_INGREDIENTS

    limit = _max_same_main(options)
    if not limit:
        return []
    return [{"label": f"Gerichte mit {label}", "max": limit, "stems": stems}
            for label, stems in MAIN_INGREDIENTS.items()]


def dish_matches(limit: dict[str, Any], title: str) -> bool:
    norm = title.lower().replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
    return any(stem in norm for stem in limit["stems"])


def calendar_rules_from_options(options: dict[str, Any]) -> list[dict[str, Any]]:
    rules = options.get(CONF_CAL_RULES)
    if rules is None and options.get("kid_calendars"):  # alte Einstellung übernehmen
        rules = [{"label": "Kind ok", "calendars": options["kid_calendars"],
                  "keyword": options.get("kid_keyword", ""),
                  "hint": "An diesen Tagen isst ein Kind mit: genug kindertaugliche Gerichte (nicht scharf, nicht zu exotisch)."}]
    out = []
    for rule in (rules or [])[:MAX_CAL_RULES]:
        cals = [c for c in rule.get("calendars") or [] if c]
        if not cals:
            continue
        out.append({
            "label": str(rule.get("label") or "Termin").strip()[:30],
            "calendars": cals,
            "keyword": str(rule.get("keyword") or "").strip(),
            "hint": str(rule.get("hint") or "").strip(),
        })
    return out


def settings_from_options(options: dict[str, Any]) -> dict[str, Any]:
    """Gespeicherte Optionen mit Voreinstellungen zu einem vollständigen Satz ergänzen."""
    devices = list(options.get(CONF_DEVICES, [DEVICE_STOVE]))
    custom_devices = [d for d in options.get(CONF_CUSTOM_DEVICES, []) if d]
    stored_sources = options.get(CONF_SOURCES, {})
    region = options.get(CONF_REGION) or "de"  # ältere Einrichtungen waren deutsch
    sources: dict[str, bool] = {}
    for domain, (default, needs_tm) in REGION_SOURCES.get(region, REGION_SOURCES["de"]).items():
        enabled = stored_sources.get(domain, default)
        if needs_tm and DEVICE_THERMOMIX not in devices:
            enabled = False
        sources[domain] = enabled
    diet_raw = options.get(CONF_DIET, {})
    diet = {
        key: {
            "mode": diet_raw.get(key, {}).get("mode", MODE_OFF),
            "count": int(diet_raw.get(key, {}).get("count", 0)),
        }
        for key in DIETS
    }
    return {
        CONF_SHOPPING_LIST: options.get(CONF_SHOPPING_LIST),
        CONF_RECIPES_PER_WEEK: int(options.get(CONF_RECIPES_PER_WEEK, DEFAULT_RECIPES_PER_WEEK)),
        CONF_DIET: diet,
        CONF_KCAL_MAX: options.get(CONF_KCAL_MAX) if _kcal_aware(options) else None,
        CONF_SOURCES: sources,
        CONF_CUSTOM_SOURCES: list(options.get(CONF_CUSTOM_SOURCES, [])),
        CONF_DEVICES: devices,
        CONF_CUSTOM_DEVICES: custom_devices,
        CONF_DEVICE_COUNTS: {k: int(v) for k, v in options.get(CONF_DEVICE_COUNTS, {}).items() if int(v) > 0},
        CONF_AI_TASK: None if options.get(CONF_AI_TASK, AI_NONE) in (AI_NONE, None, "") else options[CONF_AI_TASK],
        CONF_AI_SHOPPING: bool(options.get(CONF_AI_SHOPPING, True)),
        "proposals_from": options.get("proposals_from") or "ha",
        "ai_search": None if options.get("ai_search", AI_NONE) in (AI_NONE, None, "") else options["ai_search"],
        CONF_STAPLES: options.get(CONF_STAPLES),
        CONF_CATALOG: options.get(CONF_CATALOG),
        **{key: options.get(key, default) for key, default in DEFAULTS.items()},
        CONF_KCAL_MAX_NO_SIDE: options.get(CONF_KCAL_MAX_NO_SIDE) if _kcal_aware(options) else None,
        CONF_TRIPS: trips_from_options(options),
        CONF_CAL_RULES: calendar_rules_from_options(options),
        CONF_REGION: options.get(CONF_REGION) or "de",
        "kcal_aware": _kcal_aware(options),
        "habits": habits_from_options(options),
        "max_same_main": _max_same_main(options),
        "dish_limits": _main_limits(options) + dish_limits_from_habits(habits_from_options(options)),
    }


def enabled_sources(settings: dict[str, Any]) -> list[str]:
    return [d for d, on in settings[CONF_SOURCES].items() if on] + settings[CONF_CUSTOM_SOURCES]


def overlap_needed(settings_or_counts: dict[str, Any], recipes_per_week: int) -> int:
    """Wie viele Gerichte mehrere Vorgaben gleichzeitig erfüllen müssen (0 = keine)."""
    diet = settings_or_counts
    counts = {k: v["count"] for k, v in diet.items() if v["mode"] == MODE_COUNT}
    always = [k for k, v in diet.items() if v["mode"] == MODE_ALWAYS]
    if always:
        return 0  # "immer" gilt für alle, dann ist jede Anzahl automatisch Überschneidung
    veg = max(counts.pop(DIET_VEGETARIAN, 0), counts.pop(DIET_VEGAN, 0))
    total = veg + sum(counts.values())
    return max(0, total - recipes_per_week)


def evaluate_recipe(recipe: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    """Einordnung eines einzelnen Rezepts gemessen an den Einstellungen."""
    owned = settings[CONF_DEVICES] + settings[CONF_CUSTOM_DEVICES]
    diet = classify_diet(recipe, settings[CONF_KCAL_MAX])
    ai_diet = recipe.get("ai_diet") or {}
    diet_source = {}
    for key in DIETS:
        diet_source[key] = "rules" if diet[key] is not None else None
        if diet[key] is None and isinstance(ai_diet.get(key), bool):
            diet[key] = ai_diet[key]
            diet_source[key] = "ai"
    if diet[DIET_VEGAN] is True and diet[DIET_VEGETARIAN] is not True:
        diet[DIET_VEGETARIAN] = True
    required = detect_devices(recipe, settings[CONF_CUSTOM_DEVICES])
    # Adresse, unter der das Rezept abgerufen wurde (Eatsmarter meldet intern "eatsmarter.com")
    from urllib.parse import urlparse

    host = ((urlparse(recipe.get("source_url") or "").hostname or recipe.get("host") or "")
            .removeprefix("www."))
    hist = recipe.get("history") or {}
    cooked = hist.get("cooked_on") or []
    violations = []
    for key in DIETS:
        rule = settings[CONF_DIET][key]
        if rule["mode"] == MODE_ALWAYS and diet[key] is False:
            violations.append(key)
    return {
        "diet": {k: diet[k] for k in DIETS},
        "diet_hints": diet["hints"],
        "diet_source": diet_source,
        "ai_note": recipe.get("ai_note"),
        "devices_required": required,
        "feasible": feasible(required, owned),
        "source_enabled": host in enabled_sources(settings) if host else None,
        "breaks_always_rules": violations,
        "last_cooked": cooked[-1] if cooked else None,
        "times_cooked": len(cooked),
        "rating": hist.get("rating"),
        "status": hist.get("status"),
    }


def validate_plan(
    recipes: list[dict[str, Any]], settings: dict[str, Any], today: date
) -> dict[str, Any]:
    """Prüft eine Wochenauswahl gegen alle Vorgaben.

    Harte Fehler stehen in "violations"; was nur der KI-Planer beurteilen kann
    (z. B. cholesterinarm), steht in "needs_ai_review".
    """
    target = settings[CONF_RECIPES_PER_WEEK]
    violations: list[str] = []
    warnings: list[str] = []
    needs_ai: list[dict[str, Any]] = []
    evaluated = [(r, evaluate_recipe(r, settings)) for r in recipes]

    if len(recipes) != target:
        violations.append(f"Anzahl Rezepte {len(recipes)}, eingestellt sind {target}.")

    counts: dict[str, int] = {}
    unknown: dict[str, int] = {}
    for key in DIETS:
        counts[key] = sum(1 for _, ev in evaluated if ev["diet"][key] is True)
        unknown[key] = sum(1 for _, ev in evaluated if ev["diet"][key] is None)

    for key in DIETS:
        rule = settings[CONF_DIET][key]
        if rule["mode"] == MODE_OFF:
            continue
        needed = len(recipes) if rule["mode"] == MODE_ALWAYS else rule["count"]
        if key in SOFT_DIETS and unknown[key]:
            needs_ai.append({
                "rule": key,
                "mode": rule["mode"],
                "needed": needed,
                "candidates": [
                    {"id": r.get("id"), "title": r.get("title"),
                     "hints": ev["diet_hints"]["cholesterol_relevant"]}
                    for r, ev in evaluated if ev["diet"][key] is None
                ],
            })
            continue
        if rule["mode"] == MODE_ALWAYS:
            for r, ev in evaluated:
                if ev["diet"][key] is False:
                    violations.append(f"{key} gilt immer, '{r.get('title')}' erfüllt es nicht.")
            unclear = [r.get("title") for r, ev in evaluated if ev["diet"][key] is None]
            if unclear:
                needs_ai.append({"rule": key, "mode": MODE_ALWAYS, "unclear": unclear})
        elif counts[key] < needed:
            if counts[key] + unknown[key] >= needed:
                needs_ai.append({"rule": key, "mode": rule["mode"], "needed": needed,
                                 "confirmed": counts[key], "unclear": unknown[key]})
            else:
                violations.append(
                    f"{key}: {counts[key]} von {needed} erforderlichen Gerichten erfüllt."
                )

    for r, ev in evaluated:
        if not ev["feasible"]:
            violations.append(
                f"'{r.get('title')}' braucht {', '.join(ev['devices_required'])}, nicht alles vorhanden."
            )
        if ev["source_enabled"] is False:
            warnings.append(f"'{r.get('title')}' stammt von einer abgeschalteten Quelle ({r.get('host')}).")
        if ev["rating"] is not None and ev["rating"] <= 2:
            warnings.append(f"'{r.get('title')}' ist schlecht bewertet ({ev['rating']}/5).")
        if ev["status"] == STATUS_BOUGHT:
            warnings.append(f"'{r.get('title')}' wurde schon eingekauft, aber noch nicht gemacht.")
        if ev["last_cooked"]:
            days = (today - date.fromisoformat(ev["last_cooked"])).days
            if days < 28:
                warnings.append(f"'{r.get('title')}' gab es erst vor {days} Tagen.")

    device_counts: dict[str, int] = {}
    for dev, wanted in settings[CONF_DEVICE_COUNTS].items():
        have = sum(1 for _, ev in evaluated if dev in ev["devices_required"])
        device_counts[dev] = have
        if have < wanted:
            violations.append(f"Gerät {dev}: {have} von {wanted} gewünschten Gerichten.")

    if len({r.get("id") for r in recipes}) != len(recipes):
        warnings.append("Ein Rezept ist mehrfach in der Auswahl.")

    return {
        "ok": not violations and not needs_ai,
        "violations": violations,
        "needs_ai_review": needs_ai,
        "warnings": warnings,
        "counts": {**{k: counts[k] for k in DIETS}, "devices": device_counts, "total": len(recipes)},
        "recipes": [
            {"id": r.get("id"), "title": r.get("title"), **{k: ev[k] for k in ("diet", "devices_required", "feasible")}}
            for r, ev in evaluated
        ],
    }


def planner_brief(settings: dict[str, Any]) -> dict[str, Any]:
    """Kompakte Vorgaben für den KI-Planer."""
    diet_rules = {
        k: v for k, v in settings[CONF_DIET].items() if v["mode"] != MODE_OFF
    }
    return {
        "recipes_per_week": settings[CONF_RECIPES_PER_WEEK],
        "diet_rules": diet_rules,
        "kcal_max_per_serving": settings[CONF_KCAL_MAX],
        "enabled_sources": enabled_sources(settings),
        "devices": settings[CONF_DEVICES] + settings[CONF_CUSTOM_DEVICES],
        "device_counts_per_week": settings[CONF_DEVICE_COUNTS],
        "ai_task": settings[CONF_AI_TASK],
        "notes": [
            "Vegan zählt automatisch als vegetarisch.",
            "Ein Gericht darf mehrere Vorgaben gleichzeitig erfüllen.",
            "Cholesterinarm prüft die Integration nicht per Stichwort; mit gewählter KI bewertet sie es über meal_planner_ai.assess_recipes, sonst der Planer.",
            "Vor dem Festlegen mit meal_planner_ai.validate_plan prüfen.",
        ],
        "overlap_needed": overlap_needed(settings[CONF_DIET], settings[CONF_RECIPES_PER_WEEK]),
    }
