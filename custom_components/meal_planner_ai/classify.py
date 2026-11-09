"""Zutaten zerlegen und Rezepte einordnen (Ernährung, Geräte).

Reine Python-Logik ohne Home Assistant, damit sie einfach testbar ist.
Ergebnisse sind True (erfüllt), False (nicht erfüllt) oder None (unklar,
entscheidet der KI-Planer). Ganz fehlerfrei ist eine Stichwortprüfung nie.
"""

from __future__ import annotations

from fractions import Fraction
import re
from typing import Any

from .const import (
    DEVICE_AIRFRYER,
    DEVICE_STOVE,
    DEVICE_THERMOMIX,
    DIET_GLUTEN_FREE,
    DIET_LACTOSE_FREE,
    DIET_LOW_CALORIE,
    DIET_LOW_CHOLESTEROL,
    DIET_VEGAN,
    DIET_VEGETARIAN,
    THERMOMIX_SOURCES,
)

# ---------------------------------------------------------------- Zutaten ---

_UNICODE_FRACTIONS = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3", "⅛": "1/8"}

UNITS = [
    "kg", "g", "mg", "l", "ml", "cl", "dl",
    "EL", "TL", "Msp.", "Msp", "Prise(n)", "Prise", "Prisen", "Pck.", "Pkt.", "Päckchen",
    "Pck", "Becher", "Dose(n)", "Dose", "Dosen", "Bund", "Stück", "Stk.", "Stk",
    "Zehe(n)", "Zehe", "Zehen", "Scheibe(n)", "Scheibe", "Scheiben", "Tasse(n)", "Tasse",
    "Glas", "Gläser", "Flasche", "Würfel", "Handvoll", "Spritzer", "Schuss", "Zweig(e)",
    "Zweig", "Zweige", "Blatt", "Blätter", "Stange(n)", "Stange", "Stangen", "Knolle(n)",
    "Knolle", "cm", "Tropfen", "Tüte", "Beutel", "Netz", "Kopf", "Rolle", "Packung",
    "Paket", "Pkg.", "gr", "gr.", "cup", "cups", "tbsp", "tsp", "oz", "lb",
]
_UNIT_RE = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
_AMOUNT_RE = r"(\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?(?:\s*(?:-|–|bis)\s*\d+(?:[.,]\d+)?)?)"
_INGREDIENT_RE = re.compile(
    rf"^\s*{_AMOUNT_RE}?\s*(?:({_UNIT_RE})(?=\s|$|\.))?\.?\s*(.*)$", re.IGNORECASE
)


def _to_number(text: str) -> float | None:
    text = text.replace(",", ".").replace(" ", "")
    if "-" in text or "–" in text or "bis" in text:
        text = re.split(r"-|–|bis", text)[-1]  # Spanne: obere Grenze nehmen
    try:
        return float(Fraction(text)) if "/" in text else float(text)
    except (ValueError, ZeroDivisionError):
        return None


def parse_ingredient(line: str) -> dict[str, Any]:
    """'500 g Nudeln' -> {'amount': 500, 'unit': 'g', 'name': 'Nudeln', ...}."""
    original = line.strip()
    text = original
    for sym, rep in _UNICODE_FRACTIONS.items():
        text = text.replace(sym, f" {rep}")
    text = re.sub(r"(\d)\s+(\d/\d)", lambda m: str(float(m.group(1)) + float(Fraction(m.group(2)))), text)
    match = _INGREDIENT_RE.match(text)
    amount = unit = None
    name = original
    if match:
        raw_amount, raw_unit, rest = match.groups()
        if raw_amount:
            amount = _to_number(raw_amount)
        unit = raw_unit
        name = rest.strip() or original
    note = None
    # Pluralendung zuerst auflösen: „Zwiebel(n) (fein gewürfelt)“ → „Zwiebeln (fein gewürfelt)“
    name = re.sub(r"\((n|en|e|s|er)\)", lambda m: m.group(1), name)
    if "," in name:
        name, note = (part.strip() for part in name.split(",", 1))
    elif "(" in name and name.endswith(")"):
        base, extra = name.rsplit("(", 1)
        if len(base.strip()) > 2:
            name, note = base.strip(), extra[:-1].strip()
    return {"original": original, "amount": amount, "unit": unit, "name": name.strip(), "note": note}


def format_amount(amount: float | None, unit: str | None) -> str:
    if amount is None:
        return unit or ""
    if abs(amount - round(amount)) < 0.01:
        text = str(int(round(amount)))
    else:
        text = f"{amount:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{text} {unit}".strip() if unit else text


def servings_from_yields(yields: str | None) -> float | None:
    if not yields:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", str(yields))
    return float(match.group(1).replace(",", ".")) if match else None


# --------------------------------------------------------------- Ernährung ---

_VEGGIE_MARKERS = ("vegan", "vegetar", "veggie", "pflanzlich", "fleischersatz", "tofu", "seitan", "soja")

_MEAT = (
    "fleisch", "hack", "rind", "schwein", "kalb", "lamm", "huhn", "hühn", "hähnchen", "haehnchen",
    "pute", "puten", "truthahn", "geflügel", "ente", "gans", "wildschwein", "hirsch", "reh",
    "speck", "bacon", "pancetta", "schinken", "prosciutto", "salami", "wurst", "würstchen",
    "chorizo", "mortadella", "leberkäse", "kassler", "kasseler", "gyros", "frikadell", "leber",
    "niere", "filet", "steak", "schnitzel", "gulasch", "rouladen", "bratwurst", "mett", "maultasche", "fleischkäse",
    "lachs", "thunfisch", "fisch", "forelle", "kabeljau", "seelachs", "dorsch", "hering",
    "makrele", "sardelle", "sardine", "garnele", "shrimp", "scampi", "krabbe", "muschel",
    "tintenfisch", "calamari", "surimi", "gelatine",
)
_MEAT_EXCEPTIONS = (
    "fleischtomate", "brotrinde", "käserinde", "pflanzliche gelatine", "steakpfeffer",
    "steakgewürz", "hähnchengewürz", "grillgewürz", "gyrosgewürz", "gehackt", "kohlsteak",
    "selleriesteak", "sellerieschnitzel", "fischsauce-ersatz",
)
_DUCK_RE = re.compile(r"(^|\s|-)enten?(brust|keule|fett|\s|$|,)")

_DAIRY = (
    "milch", "sahne", "rahm", "butter", "käse", "kaese", "quark", "joghurt", "jogurt",
    "schmand", "crème fraîche", "creme fraiche", "crème fraiche", "creme fraîche",
    "mascarpone", "ricotta", "mozzarella", "parmesan", "pecorino", "gouda", "emmentaler",
    "feta", "gorgonzola", "camembert", "brie", "burrata", "skyr", "kefir", "molke",
    "buttermilch", "ghee", "grana padano", "halloumi", "hirtenkäse", "schafskäse",
    "frischkäse", "schmelzkäse", "kondensmilch", "milchpulver", "dickmilch", "sauerrahm",
)
_DAIRY_EXCEPTIONS = (
    "kokosmilch", "hafermilch", "sojamilch", "mandelmilch", "reismilch", "dinkelmilch",
    "erbsenmilch", "cashewmilch", "erdnussbutter", "kakaobutter", "nussbutter", "mandelbutter",
    "laktosefrei", "vegan", "pflanzlich", "sojajoghurt", "kokosjoghurt", "hafersahne",
    "sojasahne", "kokossahne",
)
_OTHER_ANIMAL = ("honig", "schmalz", "mayonnaise", "mayo")
_EGG_RE = re.compile(r"(^|\s|-)(ei|eier|eigelb|eigelbe|eiweiß|eiweiss|eiklar)(\s|$|,|\(|-)", re.IGNORECASE)

_GLUTEN = (
    "mehl", "weizen", "dinkel", "roggen", "gerste", "hafer", "grünkern", "emmer", "kamut",
    "nudel", "pasta", "spaghetti", "penne", "tagliatelle", "fusilli", "farfalle", "lasagne",
    "makkaroni", "maccheroni", "rigatoni", "linguine", "fettuccine", "tortellini", "ravioli",
    "gnocchi", "spätzle", "maultasche", "knödel", "couscous", "bulgur", "grieß", "griess",
    "paniermehl", "semmelbrösel", "brösel", "brot", "brötchen", "toast", "baguette",
    "ciabatta", "fladenbrot", "tortilla", "wrap", "blätterteig", "hefeteig", "pizzateig",
    "mürbeteig", "strudelteig", "yufka", "filoteig", "sojasauce", "sojasoße", "bier",
    "seitan", "graupen", "panko", "zwieback", "keks", "kuchen", "croutons",
)
_GLUTEN_EXCEPTIONS = (
    "glutenfrei", "reismehl", "maismehl", "maisstärke", "kartoffelmehl", "kartoffelstärke",
    "buchweizen", "mandelmehl", "kokosmehl", "kichererbsenmehl", "reisnudel", "glasnudel",
    "maistortilla", "tamari", "johannisbrotkernmehl", "speisestärke", "reisbrot",
)

_CHOLESTEROL_HINTS = (
    "butter", "sahne", "speck", "bacon", "leber", "niere",
    "schmalz", "salami", "wurst", "käse", "mascarpone", "crème fraîche", "schmand",
    "garnele", "shrimp", "schwein", "hackfleisch", "rinderhack", "mett",
)


# Harmlose Wörter, die Fleisch-, Milch- oder Mehl-Stichworte enthalten ("Butternuss", "Kürbisfleisch",
# "mehligkochend"); sie werden vor dem Abgleich neutralisiert, statt die ganze Zutat zu ignorieren.
_NEUTRAL = re.compile(
    r"butternuss|butter-nuss|frucht-?fleisch|kürbis-?fleisch|kuerbis-?fleisch|kokos-?fleisch|avocado-?fleisch|"
    r"melonen-?fleisch|mehlig\s*kochend|mehligkochend|mehlige|butternut",
    re.IGNORECASE)


# Ausweichzutaten zählen nicht: "500 g Rinderhack (fleischlose Alternative: Soja-Hack)" ist Fleisch
_ALT_WORDS = (r"alternativ\w*|ersatz|statt|anstelle|oder|alternative|instead|substitut\w*|or use|"
              r"en su lugar|o bien|sustitu\w*|em vez|ou bien|à la place|remplac\w*")
_ALT_PAREN = re.compile(r"\([^)]*\b(?:" + _ALT_WORDS + r")\b[^)]*\)", re.IGNORECASE)
_ALT_TAIL = re.compile(r"[,;]?\s*\b(?:" + _ALT_WORDS + r")\b.*$", re.IGNORECASE)


def _main_part(text: str) -> str:
    return _ALT_TAIL.sub("", _ALT_PAREN.sub("", text)).strip() or text


def _names(recipe: dict[str, Any]) -> list[str]:
    out = []
    for line in recipe.get("ingredients") or []:
        parsed = parse_ingredient(line)
        text = parsed["name"]
        if parsed["note"]:
            text = f"{text} ({parsed['note']})"
        out.append(_NEUTRAL.sub("~", _main_part(text).lower()))
    return out


# Englisch, Französisch, Spanisch, Portugiesisch: als ganze Wörter, damit z. B. "ham" nicht in
# "Champignons" und "egg" nicht in "eggplant" anschlägt
def _w(words: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w])(?:{words})(?![\w])", re.IGNORECASE)


_INTL_MEAT = _w(
    r"chicken|beef|pork|bacon|ham|sausages?|fish|salmon|tuna|shrimps?|prawns?|lamb|turkey|anchov\w*|mince|"
    r"minced meat|meat\w*|veal|duck|crab|lobster|squid|mussels?|"
    r"poulet|b(?:oe|œ)uf|porc|jambon|lardons?|viande|poisson|saumon|thon|crevettes?|agneau|dinde|canard|veau|"
    r"saucisses?|cabillaud|moules?|"
    r"pollo|carne|cerdo|ternera|jam[oó]n|pescado|at[uú]n|gambas?|langostinos?|cordero|pavo|salchichas?|"
    r"bacalao|merluza|calamares|"
    r"frango|porco|presunto|peixe|atum|camar(?:[aã]o|[oõ]es)|borrego|peru|lingui[cç]a|bacalhau|salsichas?")
_INTL_VEGGIE = _w(r"vegan|vegetarian|v[eé]g[eé]tal\w*|vegetal|plant[- ]based|meatless|sans viande|sin carne|sem carne")
_INTL_DAIRY = _w(
    r"milk|cream|butter|cheese|yogh?urt|ghee|"
    r"lait|cr[eè]me|beurre|fromage|yaourt|"
    r"leche|nata|mantequilla|queso|yogur|"
    r"leite|natas?|manteiga|queijo|iogurte|requeij[aã]o")
_INTL_DAIRY_EXC = _w(
    r"coconut|coco|almond|oat|soy|soja|rice milk|peanut butter|nut butter|cocoa butter|"
    r"amande|avoine|cacahu[eè]te|almendra|avena|am[eê]ndoa|aveia|amendoim|vegan|v[eé]g[eé]tal\w*|vegetal")
_INTL_EGG = _w(r"eggs?|egg yolks?|egg whites?|(?:o|œ)eufs?|oeufs?|huevos?|yemas?|ovos?|gemas?")
_INTL_OTHER = _w(r"honey|miel|mel|mayonnaise|mayonesa|maionese|gelatine?|g[eé]latine|gelatina|lard|manteca|banha")
_INTL_GLUTEN = _w(
    r"flour|wheat|pasta|noodles?|spaghetti|bread\w*|breadcrumbs|couscous|bulgur|barley|rye|tortillas?|pita|"
    r"beer|soy sauce|"
    r"farine|bl[eé]|p[aâ]tes|pain|chapelure|bi[eè]re|sauce soja|"
    r"harina|trigo|fideos|pan|cerveza|salsa de soja|"
    r"farinha|massa|macarr[aã]o|p[aã]o|cevada|centeio|cerveja|molho de soja")
_INTL_GLUTEN_EXC = _w(
    r"rice flour|corn ?flour|corn ?starch|gluten[- ]free|almond flour|tamari|farine de riz|sans gluten|maïzena|"
    r"harina de arroz|sin gluten|ma[ií]zena|farinha de arroz|sem gl[uú]ten|amido de milho|rice noodles?")
_INTL_CHOL = _w(r"butter|cream|bacon|cheese|sausages?|beurre|cr[eè]me|lardons|fromage|mantequilla|nata|queso|"
                r"manteiga|natas?|queijo")


def _contains(name: str, words: tuple[str, ...], exceptions: tuple[str, ...]) -> bool:
    if any(exc in name for exc in exceptions):
        return False
    return any(w in name for w in words)


def _is_meat(name: str) -> bool:
    if any(m in name for m in _VEGGIE_MARKERS) or _INTL_VEGGIE.search(name):
        return False
    if _DUCK_RE.search(name):
        return True
    return _contains(name, _MEAT, _MEAT_EXCEPTIONS) or bool(_INTL_MEAT.search(name))


def _is_dairy(name: str) -> bool:
    if _contains(name, _DAIRY, _DAIRY_EXCEPTIONS):
        return True
    return bool(_INTL_DAIRY.search(name)) and not _INTL_DAIRY_EXC.search(name)


def _is_other_animal(name: str) -> bool:
    if any(m in name for m in ("vegan", "pflanzlich", "ei-ersatz", "eiersatz")) or _INTL_VEGGIE.search(name):
        return False
    return (bool(_EGG_RE.search(name)) or _contains(name, _OTHER_ANIMAL, ("veganes", "vegane"))
            or bool(_INTL_EGG.search(name)) or bool(_INTL_OTHER.search(name)))


def _site_diet(recipe: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for item in recipe.get("dietary_restrictions") or []:
        text = str(item).lower()
        if "vegan" in text:
            found |= {DIET_VEGAN, DIET_VEGETARIAN}
        elif "vegetarian" in text:
            found.add(DIET_VEGETARIAN)
        if "gluten" in text:
            found.add(DIET_GLUTEN_FREE)
        if "lactose" in text or "dairyfree" in text.replace(" ", ""):
            found.add(DIET_LACTOSE_FREE)
        if "lowcalorie" in text.replace(" ", ""):
            found.add(DIET_LOW_CALORIE)
        if "lowfat" in text.replace(" ", ""):
            found.add(DIET_LOW_CHOLESTEROL)
    return found


def classify_diet(recipe: dict[str, Any], kcal_max: int | None) -> dict[str, Any]:
    """Ernährungs-Einordnung eines Rezepts."""
    names = _names(recipe)
    site = _site_diet(recipe)
    meat = [n for n in names if _is_meat(n)]
    dairy = [n for n in names if _is_dairy(n)]
    other = [n for n in names if _is_other_animal(n)]
    gluten = [n for n in names if _contains(n, _GLUTEN, _GLUTEN_EXCEPTIONS)
              or (_INTL_GLUTEN.search(n) and not _INTL_GLUTEN_EXC.search(n))]

    vegetarian = True if DIET_VEGETARIAN in site else (not meat if names else None)
    vegan = True if DIET_VEGAN in site else (
        (vegetarian is True and not dairy and not other) if names else None
    )
    if vegan:
        vegetarian = True

    kcal = recipe.get("kcal_per_serving")
    low_cal = None
    if kcal_max and kcal is not None:
        low_cal = kcal <= kcal_max

    chol_hits = sorted({
        n for n in names
        if _EGG_RE.search(n) or any(h in n for h in _CHOLESTEROL_HINTS) or _INTL_EGG.search(n) or _INTL_CHOL.search(n)
    })

    return {
        DIET_VEGETARIAN: vegetarian,
        DIET_VEGAN: vegan,
        DIET_LACTOSE_FREE: True if DIET_LACTOSE_FREE in site else (not dairy if names else None),
        DIET_GLUTEN_FREE: True if DIET_GLUTEN_FREE in site else (not gluten if names else None),
        DIET_LOW_CALORIE: low_cal,
        DIET_LOW_CHOLESTEROL: None,  # weich: entscheidet der KI-Planer
        "hints": {
            "meat_or_fish": meat,
            "dairy": dairy,
            "egg_or_other_animal": other,
            "gluten": gluten,
            "cholesterol_relevant": chol_hits,
        },
    }


# ----------------------------------------------------------------- Geräte ---

_DEVICE_KEYWORDS = {
    DEVICE_THERMOMIX: ("thermomix", "varoma", "linkslauf", "teigknetstufe", "mixtopf",
                       "tm5", "tm6", "tm7", "tm31"),
    DEVICE_AIRFRYER: ("airfryer", "air fryer", "heißluftfritteuse", "heissluftfritteuse",
                      "heißluft-fritteuse", "air-fryer"),
}
_THERMOMIX_STEP_RE = re.compile(
    r"(sek|min)\.?\s*/\s*(stufe|linkslauf)|stufe\s*\d+(?:[.,]\d)?\s*/|/\s*\d+\s*°c\s*/\s*stufe",
    re.IGNORECASE,
)


def detect_devices(recipe: dict[str, Any], custom_devices: list[str]) -> list[str]:
    """Welche Geräte braucht das Rezept? Herd/Backofen ist die Grundannahme."""
    text = " ".join(
        [str(s) for s in recipe.get("instructions") or []]
        + [str(e) for e in recipe.get("equipment") or []]
        + [str(recipe.get("title") or "")]
    ).lower()
    found: list[str] = []
    host = (recipe.get("host") or "").removeprefix("www.")
    if host in THERMOMIX_SOURCES or any(k in text for k in _DEVICE_KEYWORDS[DEVICE_THERMOMIX]) \
            or _THERMOMIX_STEP_RE.search(text):
        found.append(DEVICE_THERMOMIX)
    if any(k in text for k in _DEVICE_KEYWORDS[DEVICE_AIRFRYER]):
        found.append(DEVICE_AIRFRYER)
    if not found or any(k in text for k in ("backofen", "ofen", "herd", "pfanne")):
        found.insert(0, DEVICE_STOVE)
    for name in custom_devices:
        if name and name.lower() in text:
            found.append(name)
    return found


def feasible(required: list[str], owned: list[str]) -> bool:
    """Machbar, wenn jedes benötigte Gerät vorhanden ist."""
    return all(dev in owned for dev in required)
