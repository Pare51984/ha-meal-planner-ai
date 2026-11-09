"""Push-Meldungen in der Sprache der Region (de, en, es, pt, fr)."""

from __future__ import annotations

from typing import Any

from .const import CONF_REGION

MSG: dict[str, dict[str, str]] = {
    "de": {
        "done_title": "🍽️ Essensplan steht", "done": "Woche KW {kw} steht: {trips}.",
        "new_title": "🍽️ Neue Essensvorschläge",
        "new": "{n} Vorschläge für KW {kw}: {meatless} fleischlos, {chol} cholesterinarm",
        "wishes": ", {n} Wünsche", "wish_missing": " ({n} Wunsch nicht gefunden, bleibt stehen)",
        "carried": ", {n} übernommen", "new_end": ". Tippt bei euren Favoriten den Einkauf an.",
        "hint": " Hinweis: {n} von {total}", "open": ", offen: {list}",
        "error_title": "🍽️ Essensplan: Fehler", "error": "Die KI hat nicht geantwortet: {err}",
        "missing_title": "🍽️ Essensplan: keine Vorschläge",
        "missing": "Die externe KI hat für KW {kw} noch nichts geliefert.",
    },
    "en": {
        "done_title": "🍽️ Meal plan is set", "done": "Week {kw} is set: {trips}.",
        "new_title": "🍽️ New meal proposals",
        "new": "{n} proposals for week {kw}: {meatless} meat-free, {chol} low cholesterol",
        "wishes": ", {n} wishes", "wish_missing": " ({n} wish not found, kept for next time)",
        "carried": ", {n} carried over", "new_end": ". Tap a shopping trip on your favourites.",
        "hint": " Note: {n} of {total}", "open": ", open: {list}",
        "error_title": "🍽️ Meal plan: error", "error": "The AI did not respond: {err}",
        "missing_title": "🍽️ Meal plan: no proposals",
        "missing": "The external AI has not delivered anything for week {kw} yet.",
    },
    "es": {
        "done_title": "🍽️ Menú listo", "done": "La semana {kw} está lista: {trips}.",
        "new_title": "🍽️ Nuevas propuestas de comidas",
        "new": "{n} propuestas para la semana {kw}: {meatless} sin carne, {chol} bajas en colesterol",
        "wishes": ", {n} deseos", "wish_missing": " ({n} deseo no encontrado, se mantiene)",
        "carried": ", {n} de la semana pasada", "new_end": ". Elegid la compra en vuestros favoritos.",
        "hint": " Nota: {n} de {total}", "open": ", pendiente: {list}",
        "error_title": "🍽️ Menú: error", "error": "La IA no respondió: {err}",
        "missing_title": "🍽️ Menú: sin propuestas",
        "missing": "La IA externa aún no ha entregado nada para la semana {kw}.",
    },
    "pt": {
        "done_title": "🍽️ Plano de refeições pronto", "done": "A semana {kw} está pronta: {trips}.",
        "new_title": "🍽️ Novas propostas de refeições",
        "new": "{n} propostas para a semana {kw}: {meatless} sem carne, {chol} pobres em colesterol",
        "wishes": ", {n} desejos", "wish_missing": " ({n} desejo não encontrado, mantém-se)",
        "carried": ", {n} da semana passada", "new_end": ". Escolham a compra nos vossos favoritos.",
        "hint": " Nota: {n} de {total}", "open": ", em falta: {list}",
        "error_title": "🍽️ Plano de refeições: erro", "error": "A IA não respondeu: {err}",
        "missing_title": "🍽️ Plano de refeições: sem propostas",
        "missing": "A IA externa ainda não entregou nada para a semana {kw}.",
    },
    "fr": {
        "done_title": "🍽️ Menu prêt", "done": "La semaine {kw} est prête : {trips}.",
        "new_title": "🍽️ Nouvelles propositions de repas",
        "new": "{n} propositions pour la semaine {kw} : {meatless} sans viande, {chol} pauvres en cholestérol",
        "wishes": ", {n} envies", "wish_missing": " ({n} envie non trouvée, conservée)",
        "carried": ", {n} reportés", "new_end": ". Choisissez la course pour vos favoris.",
        "hint": " Remarque : {n} sur {total}", "open": ", manquant : {list}",
        "error_title": "🍽️ Menu : erreur", "error": "L'IA n'a pas répondu : {err}",
        "missing_title": "🍽️ Menu : aucune proposition",
        "missing": "L'IA externe n'a encore rien livré pour la semaine {kw}.",
    },
}


def msg(settings: dict[str, Any], key: str, **values: Any) -> str:
    lang = settings.get(CONF_REGION) or "de"
    pack = MSG.get(lang, MSG["en"])
    return pack.get(key, MSG["en"][key]).format(**values)


# Feste Auswahltexte in Formularen und Ansichten (Sprache des HA-Profils bzw. der Instanz)
UI: dict[str, dict[str, str]] = {
    "de": {"own_list": "Eigene Liste des Essensplaners anlegen", "no_ai": "Keine KI",
           "no_agent": "Keine (die KI oben sucht selbst)", "no": "Nein", "trip": "Einkauf {i}", "view": "Essen",
           "panel": "Essensplaner", "web_on": "Websuche an"},
    "en": {"own_list": "Create the meal planner's own list", "no_ai": "No AI",
           "no_agent": "None (the AI above searches itself)", "no": "No", "trip": "Shopping {i}", "view": "Meals",
           "panel": "Meal Planner", "web_on": "web search on"},
    "es": {"own_list": "Crear la lista propia del planificador", "no_ai": "Sin IA",
           "no_agent": "Ninguno (la IA de arriba busca sola)", "no": "No", "trip": "Compra {i}", "view": "Comidas",
           "panel": "Planificador", "web_on": "búsqueda web activa"},
    "pt": {"own_list": "Criar a lista própria do planeador", "no_ai": "Sem IA",
           "no_agent": "Nenhum (a IA acima pesquisa sozinha)", "no": "Não", "trip": "Compras {i}", "view": "Refeições",
           "panel": "Planeador", "web_on": "pesquisa web ativa"},
    "fr": {"own_list": "Créer la liste propre du planificateur", "no_ai": "Pas d'IA",
           "no_agent": "Aucun (l'IA ci-dessus cherche elle-même)", "no": "Non", "trip": "Courses {i}", "view": "Repas",
           "panel": "Planificateur", "web_on": "recherche web activée"},
}


def ui(language: str | None, key: str, **values: Any) -> str:
    pack = UI.get((language or "en")[:2].lower(), UI["en"])
    return pack.get(key, UI["en"][key]).format(**values)
