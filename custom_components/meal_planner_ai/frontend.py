"""Karte ausliefern und anzeigen: eigene Seite, Ansicht in einem Dashboard oder nur Karte."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DISPLAY_NONE, DISPLAY_PANEL, DISPLAY_VIEW, DOMAIN
from .messages import ui

_LOGGER = logging.getLogger(__name__)

CARD_URL = f"/{DOMAIN}/meal-planner-card.js"
PANEL_PATH = "meal-planner"
VIEW_PATH = "meal-planner"
_CARD_FILE = Path(__file__).parent / "www" / "meal-planner-card.js"


async def _version(hass: HomeAssistant) -> str:
    from homeassistant.loader import async_get_integration

    return str((await async_get_integration(hass, DOMAIN)).version)


async def async_register_card(hass: HomeAssistant) -> None:
    """JS-Datei bereitstellen und als Dashboard-Ressource anmelden (nur einmal je Start)."""
    if hass.data.get(f"{DOMAIN}_card"):
        return
    hass.data[f"{DOMAIN}_card"] = True
    if getattr(hass, "http", None) is None:
        return
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(_CARD_FILE), False)])
    url = f"{CARD_URL}?v={await _version(hass)}"
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        data = hass.data.get(LOVELACE_DATA)
        if data is None or data.resource_mode != "storage":
            _LOGGER.info("Dashboard-Ressourcen im YAML-Modus: %s bitte selbst eintragen", url)
            return
        resources = data.resources
        if not resources.loaded:
            await resources.async_load()
            resources.loaded = True
        for item in resources.async_items():
            if str(item.get("url", "")).split("?")[0] == CARD_URL:
                if item["url"] != url:
                    await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
                return
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception as err:  # noqa: BLE001 - Anzeige darf die Integration nie blockieren
        _LOGGER.warning("Karte konnte nicht automatisch angemeldet werden: %s", err)


LEGACY_VIEW_PATHS = ("essensplaner",)  # Ansichten der früheren Version „Essensplaner“
CARD_TYPES = ("custom:meal-planner-card", "custom:essensplaner-card")


def _board(hass: HomeAssistant, dashboard: str) -> Any | None:
    from homeassistant.components.lovelace.const import LOVELACE_DATA

    data = hass.data.get(LOVELACE_DATA)
    if data is None:
        return None
    boards = data.dashboards
    if dashboard in ("lovelace", "default"):
        # seit HA 2026 liegt das Standard-Dashboard unter "lovelace", früher unter None
        return boards.get("lovelace") or boards.get(None)
    return boards.get(dashboard)


def _our_view(view: dict[str, Any]) -> bool:
    """Eine Ansicht, die die Integration selbst angelegt hat: eigener Pfad und nur unsere Karte darin."""
    cards = view.get("cards") or []
    return (view.get("path") in (VIEW_PATH, *LEGACY_VIEW_PATHS) and len(cards) == 1
            and cards[0].get("type") in CARD_TYPES)


def _managed(meta: dict[str, Any]) -> list[str]:
    """Dashboards, in denen die Integration eine Ansicht angelegt hat (inkl. früherer Version)."""
    return list(dict.fromkeys([*meta.get("display_views", []), *meta.get("views_added", [])]))


async def _register_panel(hass: HomeAssistant, style: str) -> None:
    from homeassistant.components import frontend, panel_custom

    frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)  # neu anmelden, damit Farben greifen
    await panel_custom.async_register_panel(
        hass, frontend_url_path=PANEL_PATH, webcomponent_name="meal-planner-panel",
        sidebar_title=ui(hass.config.language, "panel"),
        sidebar_icon="mdi:silverware-fork-knife", module_url=f"{CARD_URL}?v={await _version(hass)}",
        require_admin=False, config={"preset": style})


async def _sync_view(hass: HomeAssistant, dashboard: str, keep: bool, style: str) -> bool:
    """Ansicht in einem Dashboard anlegen bzw. aktualisieren (keep) oder entfernen. True = es gibt sie danach."""
    board = _board(hass, dashboard)
    if board is None:
        _LOGGER.warning("Dashboard %s nicht gefunden", dashboard)
        return False
    try:
        config = await board.async_load(False)
    except Exception as err:  # noqa: BLE001 - z. B. leeres Standard-Dashboard (automatisch erzeugt)
        if not keep:
            return False
        _LOGGER.warning("Dashboard %s nicht lesbar: %s", dashboard, err)
        return False
    views = config.setdefault("views", [])
    ours = [v for v in views if _our_view(v)]
    card = {"type": "custom:meal-planner-card", **({"preset": style} if style != "system" else {})}
    changed = False
    if keep:
        if ours:
            for view in ours:
                if view["cards"][0] != card:
                    view["cards"][0] = card
                    changed = True
        else:
            views.append({"title": ui(hass.config.language, "view"), "path": VIEW_PATH, "icon": "mdi:silverware-fork-knife",
                          "type": "panel", "cards": [card]})
            changed = True
    elif ours:
        config["views"] = [v for v in views if not _our_view(v)]
        changed = True
    if changed:
        await board.async_save(config)
    return keep


async def async_setup_display(
    hass: HomeAssistant, mode: str, dashboard: str | None, meta: dict[str, Any], style: str = "system"
) -> bool:
    """Den eingestellten Zustand herstellen: eigene Seite, Ansicht in genau einem Dashboard oder nichts.
    Angefasst werden nur Ansichten, die die Integration selbst angelegt hat. True = meta geändert."""
    from homeassistant.components import frontend

    if mode == DISPLAY_PANEL:
        await _register_panel(hass, style)
    else:
        frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
    target = dashboard if mode == DISPLAY_VIEW and dashboard else None
    before = _managed(meta)
    after: list[str] = []
    try:
        for board in dict.fromkeys([*before, *([target] if target else [])]):
            if await _sync_view(hass, board, board == target, style):
                after.append(board)
    except Exception as err:  # noqa: BLE001 - Anzeige darf die Integration nie blockieren
        _LOGGER.warning("Anzeige konnte nicht eingerichtet werden: %s (%s)", err, type(err).__name__)
        return False
    changed = after != meta.get("display_views") or "views_added" in meta
    meta["display_views"] = after
    meta.pop("views_added", None)
    return changed


async def async_remove_display(hass: HomeAssistant, meta: dict[str, Any] | None = None) -> None:
    """Beim Entladen die eigene Seite entfernen; beim Löschen der Integration (meta) auch die Ansichten."""
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
    if meta is not None:
        for board in _managed(meta):
            try:
                await _sync_view(hass, board, False, "system")
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Ansicht in %s nicht entfernt: %s", board, err)


def dashboards(hass: HomeAssistant) -> list[str]:
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        data = hass.data.get(LOVELACE_DATA)
        if data is None:
            return ["lovelace"]
        # "map" ist das eingebaute Karten-Dashboard, dort ergibt eine Essen-Ansicht keinen Sinn
        return sorted({"lovelace" if k is None else k for k, v in data.dashboards.items()
                       if v.__class__.__name__ == "LovelaceStorage" and k != "map"})
    except Exception:  # noqa: BLE001
        return ["lovelace"]


__all__ = ["DISPLAY_NONE", "async_register_card", "async_setup_display", "async_remove_display", "dashboards"]
