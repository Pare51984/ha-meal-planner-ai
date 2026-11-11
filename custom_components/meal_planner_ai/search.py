"""Eigene Rezeptsuche: Suchseiten der freigegebenen Rezeptseiten abfragen und Rezeptlinks herausziehen.

Die KI liefert nur Gerichtsideen; echte Links holt die Integration selbst. Ob ein Treffer wirklich ein
Rezept ist, entscheidet danach der normale Abruf (recipe-scrapers). Seiten ohne eigenen Eintrag werden
über die WordPress-Suche (?s=) versucht, die viele Foodblogs haben.
"""

from __future__ import annotations

from html import unescape
import logging
import re
from typing import Any
from urllib.parse import quote, quote_plus, urljoin, urlparse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

# Suchadresse ({q} = Suchbegriff, {qp} = Suchbegriff als Pfad, {locale} = z. B. de-DE) und Muster für Rezeptlinks.
# Einträge ohne Muster nutzen die allgemeine Erkennung.
SITES: dict[str, tuple[str, str | None]] = {
    "chefkoch.de": ("https://www.chefkoch.de/rs/s0/{qp}/Rezepte.html", r"/rezepte/\d+/[^/?#\s]+\.html"),
    "cookidoo.de": ("https://cookidoo.de/search/{locale}?query={q}", r"/recipes/recipe/[a-z]{2}-[A-Za-z]{2}/r\d+"),
    "lecker.de": ("https://www.lecker.de/suche?search={q}", r"/[a-z0-9-]+-\d{4,}\.html"),
    "eatsmarter.de": ("https://eatsmarter.de/suche/rezepte?ft={q}", r"/rezepte/[a-z0-9-]{6,}"),
    "einfachkochen.de": ("https://www.einfachkochen.de/suche?search={q}", r"/rezepte/[a-z0-9-]{6,}"),
    "essen-und-trinken.de": ("https://www.essen-und-trinken.de/suche?search={q}", r"/rezepte/[a-z0-9-]{6,}"),
    "kuechengoetter.de": ("https://www.kuechengoetter.de/suche?q={q}", r"/rezepte/[a-z0-9-]{6,}"),
    "kochbar.de": ("https://www.kochbar.de/suche.html?query={q}", r"/rezept/\d+/[^/?#\s]+"),
    "rezeptwelt.de": ("https://www.rezeptwelt.de/suche?search={q}", None),
    "kitchenstories.com": ("https://www.kitchenstories.com/de/suche?search={q}", r"/de/rezepte/[a-z0-9-]{6,}"),
}
# Eigene Suche dort gerade kaputt (Live-Test 10.11.2026: kochbar.de antwortet auf die Suchadresse mit HTTP 404).
# Links von der KI auf diese Seiten werden weiter geprüft und angenommen, nur die Ersatzsuche lässt sie aus.
NO_SEARCH = ("kochbar.de",)
# Am 07.11.2026 live geprüft: diese Suchen liefern echte Rezeptlinks. Sie kommen zuerst dran.
TESTED = ("chefkoch.de", "rezeptwelt.de", "eatsmarter.de", "zaubertopf.de")
# Seiten ohne Wörter in der Rezeptadresse (Treffer lassen sich nicht vorab am Link prüfen)
_NO_SLUG = ("cookidoo.",)
_SKIP = re.compile(
    r"(/tag/|/tags/|/kategorie|/category|/categories|/suche|/search|/author|/autor|/page/|/wp-|/login|/konto|"
    r"/newsletter|/impressum|/datenschutz|/kontakt|/feed|/shop|/assets/|/saison/|/zutaten/|"
    r"\.(?:jpe?g|png|webp|gif|svg|pdf|css|js|json|xml|ico|woff2?|ttf)(?:$|\?))",
    re.IGNORECASE)
_HREF = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.IGNORECASE)
MAX_LINKS = 4


def search_url(host: str, query: str, locale: str) -> str:
    template = SITES.get(host, (None, None))[0] or f"https://{host}/?s={{q}}"
    return template.format(q=quote_plus(query), qp=quote(query), locale=locale)


def _norm(text: str) -> str:
    """Kleinschreibung ohne Umlaute; "ue/ae/oe" aus Adressen ("kuerbis") wird wie "ü" behandelt."""
    text = text.lower().replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "ss")
    return text.replace("ue", "u").replace("ae", "a").replace("oe", "o")


def _stem(word: str) -> str:
    for suffix in ("en", "n", "e", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[: -len(suffix)]
            break
    return word[:8]  # lang genug, dass "Rindergeschnetzeltes" nicht auf "Rinderfilet" passt


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]{4,}", _norm(text))}


# Beschreibende Wörter vor dem eigentlichen Gericht, die nichts über die Hauptzutat sagen
_ADJECTIVES = (
    "schnell", "einfach", "cremig", "bunt", "vegetarisch", "vegan", "leicht", "herbstlich", "winterlich",
    "klassisch", "wurzig", "wurzige", "asiatisch", "griechisch", "mediterran", "italienisch", "indisch",
    "orientalisch", "mexikanisch", "frisch", "gebraten", "gebratene", "gefullt", "gefullte", "geschmort",
    "uberbacken", "knusprig", "herzhaft", "scharf", "mild", "fruhling", "sommerlich", "omas", "schwabisch",
    "hausgemacht", "selbstgemacht", "warm", "kalt", "lauwarm", "rot", "grun", "gelb", "weiss",
)
_HEAD_SPLIT = re.compile(r"\b(?:mit|in|auf|und|an|im|nach|vom|von|aus|zu|alla|al|à|a la)\b")


def _head_words(title: str) -> list[str]:
    """Wörter des eigentlichen Gerichts: der Teil vor „mit/in/auf …“, ohne Adjektive, Bindestriche getrennt."""
    head = _HEAD_SPLIT.split(_norm(title).replace("(tm)", " "), maxsplit=1)[0]
    words = re.findall(r"[a-z]{4,}", head)
    return [w for w in words if not any(w.startswith(a) for a in _ADJECTIVES)]


def _word_in(word: str, norm_title: str) -> bool:
    """Steckt das Wort im Titel? Zusammengesetzte Wörter zählen auch über Anfang oder Ende
    („Rinderschmorgulasch“ ~ „Rindergulasch“, „Ofenlachs“ ~ „Lachs“)."""
    if _stem(word) in norm_title:
        return True
    return len(word) >= 8 and (word[:5] in norm_title or word[-5:] in norm_title)


def same_dish(original: str, title: str) -> bool:
    """Ist ein Suchtreffer dasselbe Gericht wie das gesuchte? Strenger als relevant(): Die Hauptzutat
    (erstes Wort des Gerichts) muss im Treffer stecken und mindestens die Hälfte der Gerichtswörter.
    Live-Test 11/2026: „Kürbis-Curry“ → „Hähnchen-Curry“, „Kürbispfanne mit Feta“ → „Feta-Dip“."""
    words = _head_words(original)
    if not words:
        return True
    norm = _norm(title)
    if not _word_in(words[0], norm):
        return False
    return sum(1 for w in words if _word_in(w, norm)) * 2 >= len(words)


def relevant(query: str, title: str, fallback: str = "") -> bool:
    """Passt ein Suchtreffer zum gesuchten Gericht? Mindestens die Hälfte der Suchwörter steckt im Titel
    (Wortanfänge, damit "Linsen Curry" auch "Linsencurry" findet)."""
    words = _stems(query) or _stems(fallback)
    if not words:
        return True
    norm = _norm(title)
    return sum(1 for w in words if w in norm) * 2 >= len(words)


def extract_links(html: str, base: str, host: str, query: str) -> list[str]:
    """Rezeptlinks derselben Seite aus einer Suchergebnisseite, die besten Treffer zuerst."""
    pattern = SITES.get(host, (None, None))[1]
    words = _stems(query)
    need_hit = bool(words) and not host.startswith(_NO_SLUG)
    seen: dict[str, int] = {}
    for order, raw in enumerate(_HREF.findall(html)):
        url = urljoin(base, unescape(raw.strip()))
        parsed = urlparse(url)
        link_host = (parsed.hostname or "").removeprefix("www.")
        if parsed.scheme not in ("http", "https") or not (link_host == host or link_host.endswith("." + host)):
            continue
        path = parsed.path.rstrip("/")
        if not path or _SKIP.search(path):
            continue
        if pattern:
            if not re.search(pattern, path):
                continue
        elif not (path.count("-") >= 2 or re.search(r"rezept|recipe", path, re.IGNORECASE)):
            continue
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean in seen:
            continue
        norm_path = _norm(path)
        hits = sum(1 for w in words if w in norm_path)
        if need_hit and not hits:
            continue  # Link passt gar nicht zum Gericht (Kategorie, anderes Rezept)
        seen[clean] = hits * 1000 - order
    return sorted(seen, key=lambda u: -seen[u])[:MAX_LINKS]


async def async_search(hass: HomeAssistant, host: str, query: str, locale: str) -> list[str]:
    """Eine Seite durchsuchen. Fehler (Seite blockt, anderes Format) liefern einfach keine Treffer."""
    from .services import fetch_html

    url = search_url(host, query, locale)
    try:
        html, final = await fetch_html(hass, url)
    except HomeAssistantError as err:
        _LOGGER.info("Suche auf %s nicht möglich: %s", host, err)
        return []
    # Suchseiten sind groß: Regex-Auswertung nicht im Event-Loop
    links = await hass.async_add_executor_job(extract_links, html, final, host, query)
    _LOGGER.debug("Suche %s auf %s: %s", query, host, links)
    return links


async def async_search_report(hass: HomeAssistant, hosts: list[str], query: str, locale: str) -> list[dict[str, Any]]:
    """Für die Aktion meal_planner_ai.search_recipes: je Seite Suchadresse und gefundene Links."""
    from .services import fetch_html

    out = []
    for host in hosts:
        url = search_url(host, query, locale)
        entry: dict[str, Any] = {"site": host, "search_url": url, "links": []}
        try:
            html, final = await fetch_html(hass, url)
            entry["links"] = await hass.async_add_executor_job(extract_links, html, final, host, query)
        except HomeAssistantError as err:
            entry["error"] = str(err)
        out.append(entry)
    return out
