"""Zutaten in die gewählte To-do-Liste schreiben und wieder austragen.

Format wie im bisherigen Planer: Artikelname (Katalogname) als Eintrag, in der
Beschreibung Teile "<Menge> (<Gericht>)", mehrere Gerichte mit " + " verbunden.
So kann jedes Gericht einzeln wieder ausgetragen werden. Abgehakte Einträge
werden nie angefasst und nie neu angelegt.
"""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.todo import TodoListEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .classify import format_amount, parse_ingredient, servings_from_yields

DEFAULT_STAPLES = "Salz, Pfeffer, Zucker, Öl, Olivenöl, Rapsöl, Sonnenblumenöl, Pflanzenöl, Essig, Mehl, Brühe, Gemüsebrühe, Wasser"
DEFAULT_CATALOG = """Emmentaler gerieben = Reibekäse
geriebener Käse = Reibekäse
passierte Tomaten = Dosentomaten
stückige Tomaten = Dosentomaten
Wirsing = Kohl
Schlagsahne = Sahne
rote Linsen = Linsen
Rinderhack = Hackfleisch
gemischtes Hackfleisch = Hackfleisch
Möhren = Karotten
Möhre = Karotten
TK-Blattspinat = Spinat
Blattspinat = Spinat
Staudensellerie = Sellerie"""

_SPICE_WORDS = (
    "pulver", "gewürz", "oregano", "thymian", "rosmarin", "majoran", "kümmel", "kreuzkümmel",
    "zimt", "muskat", "curry", "kurkuma", "paprika edelsüß", "paprika rosenscharf", "chili",
    "cayenne", "lorbeer", "nelke", "piment", "italienische kräuter",
    "kräuter der provence", "garam masala", "zatar", "ras el hanout",
    "senfsaat", "fenchelsaat", "anis", "vanille", "brühwürfel", "brühpulver", "fond",
    "edelsüß", "edelsuess", "rosenscharf",
    # andere Sprachen (nur eindeutige Gewürze; "Paprika" allein ist auf Deutsch das Gemüse)
    "powder", "ground cumin", "cinnamon", "nutmeg", "bay leaf", "dried thyme", "dried oregano", "smoked paprika",
    "comino", "pimentón", "canela", "nuez moscada", "laurel", "cominho", "colorau", "noz-moscada", "louro",
    "cannelle", "muscade", "herbes de provence", "piment d'espelette",
)


def parse_staples(text: str | None) -> set[str]:
    return {p.strip().lower() for p in (text if text is not None else DEFAULT_STAPLES).split(",") if p.strip()}


def parse_catalog(text: str | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in (text if text is not None else DEFAULT_CATALOG).splitlines():
        if "=" in line:
            left, right = line.split("=", 1)
        elif "->" in line:
            left, right = line.split("->", 1)
        else:
            continue
        if left.strip() and right.strip():
            mapping[left.strip().lower()] = right.strip()
    return mapping


def _is_staple(name: str, staples: set[str], skip_spices: bool) -> bool:
    low = name.lower().strip(" .")
    if low in staples or any(low == f"etwas {s}" for s in staples):
        return True
    # Zusammensetzungen wie "Jodsalz", "Meersalz", "Weizenmehl" (nur längere Grundzutaten, nicht "Öl")
    if " " not in low and any(len(s) >= 4 and low.endswith(s) for s in staples):
        return True
    for sep in (" und ", ", ", " & "):
        if sep in low and all(p.strip() in staples for p in low.split(sep)):
            return True
    return skip_spices and any(w in low for w in _SPICE_WORDS) and "schote" not in low


def round_amount(amount: float | None, unit: str | None) -> float | None:
    """Sinnvoll runden: Gramm/ml auf 5er bzw. 10er, Stück auf ganze, Löffel auf halbe."""
    if amount is None:
        return None
    u = (unit or "").lower().rstrip(".")
    if u in ("g", "ml", "gr"):
        step = 10 if amount >= 500 else 5
        return max(step, math.floor(amount / step + 0.5) * step)
    if u in ("kg", "l"):
        return round(amount * 4) / 4 or 0.25
    if u in ("el", "tl", "msp", "prise", "prisen", "prise(n)"):
        return max(0.5, round(amount * 2) / 2)
    if not u or u.startswith(("stück", "stk", "zehe", "dose", "bund", "becher", "pck", "pkt",
                              "päckchen", "packung", "scheibe", "stange", "knolle", "kopf", "glas")):
        return float(max(1, math.ceil(amount - 0.15)))
    return round(amount, 1)


def build_items(
    recipe: dict[str, Any],
    portions: float | None,
    staples: set[str] | None = None,
    skip_spices: bool = True,
) -> tuple[list[dict[str, str]], list[str]]:
    """Einträge bauen: Name + Menge (auf Portionen umgerechnet), Grundzutaten weglassen."""
    staples = parse_staples(None) if staples is None else staples
    base = servings_from_yields(recipe.get("yields"))
    factor = portions / base if portions and base else 1.0
    merged: dict[str, dict[str, str]] = {}
    skipped: list[str] = []
    for line in recipe.get("ingredients") or []:
        parsed = parse_ingredient(line)
        name = parsed["name"]
        if not name:
            continue
        if _is_staple(name, staples, skip_spices):
            skipped.append(name)
            continue
        amount = parsed["amount"] * factor if parsed["amount"] is not None else None
        amount = round_amount(amount, parsed["unit"])
        spec = format_amount(amount, parsed["unit"])
        if parsed["note"]:
            spec = f"{spec}, {parsed['note']}" if spec else parsed["note"]
        key = name.lower()
        if key in merged:
            merged[key]["spec"] = " und ".join(x for x in (merged[key]["spec"], spec) if x)
        else:
            merged[key] = {"name": name, "spec": spec}
    return list(merged.values()), skipped


def apply_catalog(items: list[dict[str, str]], catalog: dict[str, str]) -> list[dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for item in items:
        name = catalog.get(item["name"].strip().lower(), item["name"].strip())
        key = name.lower()
        if key in out:
            out[key]["spec"] = " und ".join(x for x in (out[key]["spec"], item["spec"]) if x)
        else:
            out[key] = {"name": name, "spec": item["spec"]}
    return list(out.values())


def _variants(key: str) -> list[str]:
    """Einzahl/Mehrzahl-Varianten, damit 'Zwiebel' und 'Zwiebeln' derselbe Artikel sind."""
    out = [key]
    for suffix in ("n", "en", "e", "s"):
        out.append(key + suffix)
        if key.endswith(suffix) and len(key) > len(suffix) + 2:
            out.append(key[: -len(suffix)])
    return out


def _find_existing(existing: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    for variant in _variants(name.strip().lower()):
        if variant in existing:
            return existing[variant]
    return None


def _part(spec: str, tag: str) -> str:
    return f"{spec} ({tag})" if spec else f"({tag})"


def strip_tag(description: str | None, tag: str) -> str:
    marker = f"({tag})"
    parts = [p.strip() for p in (description or "").split(" + ")]
    return " + ".join(p for p in parts if p and not p.endswith(marker))


async def _features(hass: HomeAssistant, entity_id: str) -> int:
    state = hass.states.get(entity_id)
    if state is None:
        raise HomeAssistantError(f"Einkaufsliste {entity_id} nicht gefunden.")
    return int(state.attributes.get("supported_features", 0))


async def _open_items(hass: HomeAssistant, entity_id: str) -> list[dict[str, Any]]:
    resp = await hass.services.async_call(
        "todo", "get_items", {"entity_id": entity_id, "status": "needs_action"},
        blocking=True, return_response=True,
    )
    return list((resp or {}).get(entity_id, {}).get("items", []))


async def async_add_items(
    hass: HomeAssistant, entity_id: str, items: list[dict[str, str]], tag: str
) -> list[dict[str, str]]:
    """Zutaten eines Gerichts eintragen; vorhandene offene Artikel bekommen einen weiteren Teil."""
    features = await _features(hass, entity_id)
    if not features & TodoListEntityFeature.CREATE_TODO_ITEM:
        raise HomeAssistantError(f"In {entity_id} können keine Einträge angelegt werden.")
    with_desc = bool(features & TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM)
    can_update = bool(features & TodoListEntityFeature.UPDATE_TODO_ITEM)
    existing = {i["summary"].strip().lower(): i for i in await _open_items(hass, entity_id)}
    result: list[dict[str, str]] = []
    for item in items:
        if not with_desc:
            text = f"{item['name']} – {_part(item['spec'], tag)}"
            if text.lower() not in existing:
                await hass.services.async_call(
                    "todo", "add_item", {"entity_id": entity_id, "item": text}, blocking=True)
            result.append({"name": text, "spec": "", "action": "added"})
            continue
        part = _part(item["spec"], tag)
        found = _find_existing(existing, item["name"])
        if found and can_update and found.get("uid"):
            desc = found.get("description") or ""
            if f"({tag})" in desc:
                result.append({**item, "action": "already"})
                continue
            new_desc = f"{desc} + {part}" if desc else part
            await hass.services.async_call(
                "todo", "update_item",
                {"entity_id": entity_id, "item": found["uid"], "description": new_desc}, blocking=True)
            found["description"] = new_desc
            result.append({**item, "action": "merged"})
            continue
        await hass.services.async_call(
            "todo", "add_item",
            {"entity_id": entity_id, "item": item["name"], "description": part}, blocking=True)
        result.append({**item, "action": "added"})
        # Namen sind innerhalb eines Gerichts eindeutig: lokal merken statt die ganze Liste neu zu laden
        existing[item["name"].strip().lower()] = {"summary": item["name"], "description": part}
    return result


async def async_remove_tag(hass: HomeAssistant, entity_id: str, tag: str) -> list[str]:
    """Alle Teile eines Gerichts aus offenen Einträgen entfernen; leere Einträge löschen."""
    features = await _features(hass, entity_id)
    with_desc = bool(features & TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM)
    removed: list[str] = []
    for item in await _open_items(hass, entity_id):
        if not with_desc:
            if item["summary"].endswith(f"({tag})"):
                await hass.services.async_call(
                    "todo", "remove_item", {"entity_id": entity_id, "item": item["uid"]}, blocking=True)
                removed.append(item["summary"])
            continue
        desc = item.get("description") or ""
        if f"({tag})" not in desc:
            continue
        rest = strip_tag(desc, tag)
        if rest:
            await hass.services.async_call(
                "todo", "update_item",
                {"entity_id": entity_id, "item": item["uid"], "description": rest}, blocking=True)
        else:
            await hass.services.async_call(
                "todo", "remove_item", {"entity_id": entity_id, "item": item["uid"]}, blocking=True)
        removed.append(item["summary"])
    return removed
