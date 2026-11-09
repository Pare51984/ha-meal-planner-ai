"""Konstanten für die Essensplaner-Integration."""

from __future__ import annotations

DOMAIN = "meal_planner_ai"

# Ehrliche Kennung beim Abruf der Rezeptseite, keine Browser-Tarnung.
USER_AGENT = (
    "Mozilla/5.0 (compatible; Essensplaner-HomeAssistant/1.0; "
    "+https://github.com/Pare51984/ha-meal-planner-ai)"
)
FETCH_TIMEOUT = 20  # Sekunden
MAX_HTML_BYTES = 5 * 1024 * 1024

STORAGE_VERSION = 1
STORAGE_KEY_RECIPES = f"{DOMAIN}.recipes"
STORAGE_KEY_SHOPPING = f"{DOMAIN}.shopping_list"
STORAGE_KEY_WISHES = f"{DOMAIN}.wishes"

# --- Optionen (Schlüssel in entry.options) -------------------------------
CONF_SHOPPING_LIST = "shopping_list"  # entity_id oder OWN_LIST
OWN_LIST = "own"
CONF_RECIPES_PER_WEEK = "recipes_per_week"
CONF_DIET = "diet"  # {diet_key: {"mode": ..., "count": int}}
CONF_KCAL_MAX = "kcal_max"
CONF_SOURCES = "sources"  # {domain: bool}
CONF_CUSTOM_SOURCES = "custom_sources"  # [domain]
CONF_DEVICES = "devices"  # [device_key]
CONF_CUSTOM_DEVICES = "custom_devices"  # [name]
CONF_DEVICE_COUNTS = "device_counts"  # {device: int}
CONF_AI_TASK = "ai_task"  # entity_id einer AI-Task-Entität oder AI_NONE
CONF_AI_SHOPPING = "ai_shopping_names"  # KI bereinigt Artikelnamen für die Liste
AI_NONE = "none"
MAX_PLAN_ROUNDS = 4

DEFAULT_RECIPES_PER_WEEK = 10

# Wochenablauf
CONF_PORTIONS = "portions"
CONF_KCAL_MAX_NO_SIDE = "kcal_max_without_side"
CONF_TIME_MAX = "time_max"
CONF_TIME_QUICK = "time_quick"
CONF_QUICK_SHARE = "quick_share"
CONF_SOUP_MAX = "soup_max"  # alt, wird in die Essgewohnheiten übernommen
CONF_HABITS = "habits"  # Essgewohnheiten: Regeln für die Rezeptauswahl (Freitext, bis zu 5)
MAX_HABITS = 5
DEFAULT_HABITS = ["Suppen/Eintöpfe höchstens 1x pro Woche"]
CONF_PROPOSALS_FROM = "proposals_from"  # "ha" = KI in Home Assistant, "external" = externe KI über Aktionen
PROPOSALS_HA = "ha"
PROPOSALS_EXTERNAL = "external"
EXTERNAL_FALLBACK_HOURS = 5  # so lange nach dem Planungszeitpunkt auf die externe KI warten
CONF_AI_SEARCH = "ai_search"  # Gesprächsagent mit Websuche für die Rezeptsuche (leer = AI Task)
CONF_KCAL_AWARE = "kcal_aware"  # kalorienbewusst an/aus; nur dann gelten die kcal-Grenzen
CONF_PROFILE = "profile"  # Freitext: Grundregeln und Geschmack
CONF_STAPLES = "staples"
CONF_SKIP_SPICES = "skip_spices"
CONF_CATALOG = "catalog"
CONF_CAL_RULES = "calendar_rules"  # [{label, calendars, keyword, hint}], bis zu 3
MAX_CAL_RULES = 3
CONF_NOTIFY = "notify"
CONF_DASHBOARD_PATH = "dashboard_path"
CONF_DISPLAY = "display"
CONF_DISPLAY_DASHBOARD = "display_dashboard"
DISPLAY_PANEL = "panel"  # eigene Seite in der Seitenleiste
DISPLAY_VIEW = "view"  # Ansicht in einem vorhandenen Dashboard
DISPLAY_NONE = "none"  # nur die Karte
DISPLAYS = [DISPLAY_PANEL, DISPLAY_VIEW, DISPLAY_NONE]
CONF_DISPLAY_STYLE = "display_style"
STYLES = ["system", "warm"]  # system = Farben des HA-Designs
CONF_PLAN_DAY = "plan_weekday"
CONF_PLAN_TIME = "plan_time"
CONF_DEADLINE_DAY = "deadline_weekday"
CONF_DEADLINE_TIME = "deadline_time"

DEFAULTS = {
    CONF_PORTIONS: 3,
    CONF_KCAL_MAX_NO_SIDE: None,  # leer = keine Grenze
    CONF_TIME_MAX: 60,
    CONF_TIME_QUICK: 40,
    CONF_QUICK_SHARE: 8,
    CONF_PROFILE: "",
    CONF_SKIP_SPICES: True,
    CONF_NOTIFY: [],
    CONF_DASHBOARD_PATH: "",
    CONF_DISPLAY: DISPLAY_PANEL,
    CONF_DISPLAY_DASHBOARD: "lovelace",
    CONF_DISPLAY_STYLE: "system",
    CONF_PLAN_DAY: 4,  # Montag = 0 ... Freitag = 4
    CONF_PLAN_TIME: "18:00",
    CONF_DEADLINE_DAY: 5,
    CONF_DEADLINE_TIME: "12:00",
}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Einkäufe: 1 bis 7, je mit Namen, abgedeckten Kochtagen und Freigabe "sofort" oder "zu Wochentag/Uhrzeit"
CONF_TRIPS = "trips"
TRIP_KEYS = [f"trip{i}" for i in range(1, 8)]  # bis zu 7 Einkäufe pro Woche (auch täglich)
RELEASE_IMMEDIATE = "immediate"
RELEASE_TIMED = "timed"
DEFAULT_TRIPS = [
    {"name": "Einkauf 1", "release": RELEASE_IMMEDIATE, "days": []},
    {"name": "Einkauf 2", "release": RELEASE_TIMED, "weekday": 0, "time": "18:00", "days": []},
]

# Auswahl je Gericht
CHOICE_NONE = "none"
CHOICE_DECLINED = "declined"  # doch nicht
CHOICE_EARLY = TRIP_KEYS[0]
CHOICE_LATE = TRIP_KEYS[1]
CHOICES = [CHOICE_NONE, CHOICE_DECLINED, *TRIP_KEYS]

SIGNAL_BOARD_UPDATED = f"{DOMAIN}_board_updated"

MODE_OFF = "off"
MODE_ALWAYS = "always"
MODE_COUNT = "count"
DIET_MODES = [MODE_OFF, MODE_ALWAYS, MODE_COUNT]

DIET_VEGETARIAN = "vegetarian"
DIET_VEGAN = "vegan"
DIET_LACTOSE_FREE = "lactose_free"
DIET_GLUTEN_FREE = "gluten_free"
DIET_LOW_CHOLESTEROL = "low_cholesterol"
DIET_LOW_CALORIE = "low_calorie"
DIETS = [
    DIET_VEGETARIAN,
    DIET_VEGAN,
    DIET_LACTOSE_FREE,
    DIET_GLUTEN_FREE,
    DIET_LOW_CHOLESTEROL,
]  # kcal-Grenzen stehen unter "Regeln"; "kalorienbewusst" als eigene Option gibt es nicht mehr
# Weiche Kriterien: die Integration liefert Hinweise, entscheiden muss der KI-Planer.
SOFT_DIETS = {DIET_LOW_CHOLESTEROL}

DEVICE_STOVE = "stove_oven"
DEVICE_THERMOMIX = "thermomix"
DEVICE_AIRFRYER = "airfryer"
DEVICES = [DEVICE_STOVE, DEVICE_THERMOMIX, DEVICE_AIRFRYER]
DEVICE_LABELS = {
    DEVICE_STOVE: "Herd und Backofen",
    DEVICE_THERMOMIX: "Thermomix",
    DEVICE_AIRFRYER: "Airfryer",
}

# Vorbelegte Rezeptseiten: domain -> (Voreinstellung, nur mit Thermomix)
# Region: Sprache der Vorschläge, Rezeptseiten und Cookidoo-Land
# Abwechslung: höchstens so viele Gerichte pro Woche mit derselben Hauptzutat (Erkennung am Gerichtsnamen, ohne Wünsche)
MAX_SAME_MAIN = 3
CONF_MAX_SAME_MAIN = "max_same_main"  # 0 = egal
MAIN_INGREDIENTS: dict[str, list[str]] = {
    "Hähnchen/Pute": ["hahnchen", "huhn", "hendl", "geflugel", "pute", "chicken", "turkey", "pollo", "pavo",
                      "frango", "peru", "poulet", "volaille", "dinde"],
    "Rind": ["rind", "beef", "ternera", "vacuno", "carne de vaca", "boeuf", "bœuf"],
    "Schwein": ["schwein", "pork", "cerdo", "porco", "porc"],
    "Hackfleisch": ["hack", "minced", "mince", "meatball", "albondiga", "carne picada", "almondega", "kofta", "boulette"],
    "Lachs": ["lachs", "salmon", "salmao", "saumon"],
}
CONF_REGION = "region"
REGIONS = ["de", "en", "es", "pt", "fr"]
REGION_LOCALE = {"de": "de-DE", "en": "en-GB", "es": "es-ES", "pt": "pt-PT", "fr": "fr-FR"}
REGION_LANGUAGE = {"de": "Deutsch", "en": "Englisch", "es": "Spanisch", "pt": "Portugiesisch", "fr": "Französisch"}
# Domain -> (standardmäßig an, nur mit Thermomix). Deutsch live geprüft; die anderen Länder nutzen von
# recipe-scrapers unterstützte Seiten (Stand 11/2026), ihre Suche ist noch nicht live geprüft.
REGION_SOURCES: dict[str, dict[str, tuple[bool, bool]]] = {
    "de": {
        "chefkoch.de": (True, False),
        "rezeptwelt.de": (True, True),
        "zaubertopf.de": (True, True),
        "lecker.de": (True, False),
        "eatsmarter.de": (True, False),
        "kitchenstories.com": (False, False),
        "emmikochteinfach.de": (False, False),
        "springlane.de": (False, False),
        "kochbar.de": (False, False),
        "hellofresh.de": (False, False),
        "sallys-blog.de": (False, False),
        "cookidoo.de": (True, True),
        "einfachkochen.de": (True, False),
        "essen-und-trinken.de": (True, False),
        "kuechengoetter.de": (True, False),
    },
    "en": {
        "allrecipes.com": (True, False),
        "bbcgoodfood.com": (True, False),
        "seriouseats.com": (True, False),
        "simplyrecipes.com": (True, False),
        "recipetineats.com": (True, False),
        "budgetbytes.com": (True, False),
        "jamieoliver.com": (True, False),
        "eatingwell.com": (False, False),
        "food.com": (False, False),
        "cookidoo.co.uk": (True, True),
    },
    "es": {
        "directoalpaladar.com": (True, False),
        "recetasgratis.net": (True, False),
        "hellofresh.es": (True, False),
        "cookidoo.es": (True, True),
    },
    "pt": {
        "tudogostoso.com.br": (True, False),
        "panelinha.com.br": (True, False),
        "receitas.globo.com": (True, False),
        "receitasnestle.com.br": (True, False),
        "pingodoce.pt": (True, False),
        "cookidoo.pt": (True, True),
    },
    "fr": {
        "marmiton.org": (True, False),
        "cuisineaz.com": (True, False),
        "750g.com": (True, False),
        "cuisine.journaldesfemmes.fr": (True, False),
        "jow.fr": (True, False),
        "hellofresh.fr": (False, False),
        "cookidoo.fr": (True, True),
    },
}
PRESET_SOURCES: dict[str, tuple[bool, bool]] = {d: v for sites in REGION_SOURCES.values() for d, v in sites.items()}


def default_region(language: str | None) -> str:
    lang = (language or "").split("-")[0].lower()
    return lang if lang in REGIONS else "en"


THERMOMIX_SOURCES = {d for d, (_, tm) in PRESET_SOURCES.items() if tm}

# Verlauf
STATUS_NEW = "new"
STATUS_BOUGHT = "bought"  # eingekauft, noch nicht gemacht
STATUS_COOKED = "cooked"
STATUSES = [STATUS_NEW, STATUS_BOUGHT, STATUS_COOKED]
RATING_MIN = 1
RATING_MAX = 5
