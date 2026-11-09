from custom_components.meal_planner_ai.classify import (
    classify_diet, detect_devices, parse_ingredient, servings_from_yields)

def test_parse_ingredient():
    p = parse_ingredient("500 g Nudeln")
    assert (p["amount"], p["unit"], p["name"]) == (500, "g", "Nudeln")
    p = parse_ingredient("1 ½ EL Olivenöl")
    assert p["amount"] == 1.5 and p["unit"] == "EL" and p["name"] == "Olivenöl"
    p = parse_ingredient("450 g Blattspinat, TK")
    assert p["name"] == "Blattspinat" and p["note"] == "TK"
    p = parse_ingredient("Salz und Pfeffer")
    assert p["amount"] is None and p["name"] == "Salz und Pfeffer"
    p = parse_ingredient("2 Zwiebel(n)")
    assert p["amount"] == 2 and p["name"] == "Zwiebeln"
    p = parse_ingredient("1 Pck. Sahne")
    assert p["unit"] == "Pck." and p["name"] == "Sahne"
    p = parse_ingredient("3 Ei(er)")
    assert p["name"] == "Eier"

def test_servings():
    assert servings_from_yields("4 servings") == 4

def r(*ing, **kw):
    return {"ingredients": list(ing), **kw}

def test_diet():
    d = classify_diet(r("500 g Nudeln", "400 g Hackfleisch, gemischt", "450 g Blattspinat"), 800)
    assert d["vegetarian"] is False and d["vegan"] is False and d["gluten_free"] is False
    d = classify_diet(r("200 g Linsen", "1 Zwiebel", "400 ml Kokosmilch", "1 TL Gemüsebrühe"), None)
    assert d["vegetarian"] and d["vegan"] and d["lactose_free"] and d["gluten_free"]
    d = classify_diet(r("2 Eier", "100 g Parmesan", "200 g Polenta"), None)
    assert d["vegetarian"] is True and d["vegan"] is False and d["lactose_free"] is False
    assert d["gluten_free"] is True
    d = classify_diet(r("50 g gehackte Mandeln", "1 Eisbergsalat"), None)
    assert d["vegan"] is True
    d = classify_diet(r("1 Entenbrust", "500 g Rinderhack"), None)
    assert d["hints"]["meat_or_fish"] == ["entenbrust", "rinderhack"]
    d = classify_diet(r("200 g Hackfleisch, vegan"), None)
    assert d["vegetarian"] is True
    d = classify_diet({"ingredients": ["x"], "kcal_per_serving": 900}, 800)
    assert d["low_calorie"] is False
    d = classify_diet(r(), None)
    assert d["vegetarian"] is None

def test_devices():
    assert detect_devices({"instructions": ["Im Backofen backen"]}, []) == ["stove_oven"]
    assert "thermomix" in detect_devices({"instructions": ["10 Sek./Stufe 5 zerkleinern"]}, [])
    assert detect_devices({"host": "rezeptwelt.de", "instructions": ["x"]}, []) == ["thermomix"]
    assert "airfryer" in detect_devices({"instructions": ["In der Heißluftfritteuse garen"]}, [])
    assert "Slow Cooker" in detect_devices({"instructions": ["Im Slow Cooker 6 h garen"]}, ["Slow Cooker"])


def test_shopping_helpers():
    from custom_components.meal_planner_ai.shopping import (
        apply_catalog, build_items, parse_catalog, round_amount, strip_tag)
    items, skipped = build_items({"yields": "4", "ingredients": [
        "2 Zwiebeln", "1 Zwiebeln", "100 g Butter", "1 EL Butter", "Salz und Pfeffer",
        "1 TL Paprikapulver", "2 rote Paprikaschoten", "333 g Möhren"]}, 3)
    assert {"name": "Zwiebeln", "spec": "2 und 1"} in items
    assert {"name": "Butter", "spec": "75 g und 1 EL"} in items
    assert "Salz und Pfeffer" in skipped and "Paprikapulver" in skipped
    assert {"name": "rote Paprikaschoten", "spec": "2"} in items
    mapped = apply_catalog(items, parse_catalog(None))
    assert {"name": "Karotten", "spec": "250 g"} in mapped
    assert round_amount(0.75, None) == 1 and round_amount(1.6, "EL") == 1.5 and round_amount(337, "g") == 335
    assert strip_tag("1 (A) + 2 (B)", "A") == "2 (B)"


def test_habits_and_limits():
    from custom_components.meal_planner_ai.planning import (
        dish_limits_from_habits, dish_matches, habits_from_options, settings_from_options)

    assert habits_from_options({}) == ["Suppen/Eintöpfe höchstens 1x pro Woche"]  # Standard
    assert habits_from_options({"soup_max": 2}) == ["Suppen/Eintöpfe höchstens 2x pro Woche"]
    assert habits_from_options({"habits": ["", " kein Schwein "]}) == ["kein Schwein"]
    limits = dish_limits_from_habits(["Suppen/Eintöpfe höchstens 1x pro Woche", "Aufläufe maximal 2 mal",
                                      "mindestens 1x Fisch", "Fisch 1x"])
    assert [(x["label"], x["max"]) for x in limits] == [("Suppen/Eintöpfe", 1), ("Aufläufe", 2)]
    soup, bake = limits
    assert dish_matches(soup, "Kürbissuppe mit Ingwer") and dish_matches(soup, "Linseneintopf")
    assert not dish_matches(soup, "Spaghetti Bolognese") and dish_matches(bake, "Kartoffelauflauf")
    # kcal nur bei "kalorienbewusst"
    assert settings_from_options({"kcal_max": 800})["kcal_max"] == 800  # alte Einstellung = an
    off = settings_from_options({"kcal_aware": False, "kcal_max": 800, "kcal_max_without_side": 650})
    assert off["kcal_max"] is None and off["kcal_max_without_side"] is None


def test_false_friends():
    """Butternuss ist keine Butter, Kürbisfleisch kein Fleisch, mehligkochend kein Mehl."""
    from custom_components.meal_planner_ai.classify import classify_diet

    c = classify_diet({"ingredients": ["400 Gramm Butternuss-Kürbisfleisch, in kleinen Stücken",
                                       "200 Gramm Kartoffeln, mehligkochend", "400 g Butternusskürbis(se)"]}, None)
    assert c["vegetarian"] is True and c["vegan"] is True and c["gluten_free"] is True
    c = classify_diet({"ingredients": ["400 g Butternusskürbis", "50 g Butter"]}, None)
    assert c["vegan"] is False and c["vegetarian"] is True


def test_staple_compounds():
    from custom_components.meal_planner_ai.shopping import _is_staple, parse_staples

    staples = parse_staples(None)
    assert _is_staple("Jodsalz", staples, False) and _is_staple("Meersalz", staples, False)
    assert _is_staple("Weizenmehl", staples, False)
    assert not _is_staple("Sesamöl", staples, False) or "sesamöl" in staples  # kurze Grundzutat "Öl" zählt nicht
    assert not _is_staple("Paprika", staples, False)


def test_region_sources_and_languages():
    from custom_components.meal_planner_ai.classify import classify_diet
    from custom_components.meal_planner_ai.planning import enabled_sources, settings_from_options

    de = settings_from_options({})
    assert de["region"] == "de" and "chefkoch.de" in enabled_sources(de)  # ältere Einrichtung bleibt deutsch
    fr = settings_from_options({"region": "fr", "devices": ["stove_oven", "thermomix"]})
    assert "marmiton.org" in enabled_sources(fr) and "cookidoo.fr" in enabled_sources(fr)  # codeql[py/incomplete-url-substring-sanitization] Listenprüfung, keine URL-Prüfung
    assert "chefkoch.de" not in enabled_sources(fr)
    en_no_tm = settings_from_options({"region": "en"})
    assert "cookidoo.co.uk" not in enabled_sources(en_no_tm)
    # Fleisch/Milch/Gluten auch in anderen Sprachen, ohne falsche Treffer
    assert classify_diet({"ingredients": ["2 chicken breasts", "1 eggplant"]}, None)["vegetarian"] is False
    c = classify_diet({"ingredients": ["400 g champignons", "1 butternut squash", "200 ml coconut milk"]}, None)
    assert c["vegan"] is True and c["lactose_free"] is True
    c = classify_diet({"ingredients": ["200 g de lardons", "20 cl de crème fraîche", "250 g de pâtes"]}, None)
    assert c["vegetarian"] is False and c["lactose_free"] is False and c["gluten_free"] is False
    assert classify_diet({"ingredients": ["500 g de frango", "2 ovos"]}, None)["vegetarian"] is False
    assert classify_diet({"ingredients": ["300 g de pollo"]}, None)["vegetarian"] is False


def test_main_ingredient_limit():
    from custom_components.meal_planner_ai.planning import dish_matches, settings_from_options

    limits = {l["label"]: l for l in settings_from_options({"region": "de"})["dish_limits"]}
    chicken = limits["Gerichte mit Hähnchen/Pute"]
    assert chicken["max"] == 3
    assert dish_matches(chicken, "Hähnchen-Kokos-Curry mit Reis (TM)")
    assert dish_matches(chicken, "Putengeschnetzeltes auf Rösti")
    assert not dish_matches(chicken, "Gemüse-Curry mit Kichererbsen")
    assert dish_matches(limits["Gerichte mit Hackfleisch"], "Hackbällchen mit Tomatensoße")
    assert "rewe.de" not in settings_from_options({"region": "de", "sources": {"rewe.de": True}})["sources"]



def test_main_limit_setting():
    from custom_components.meal_planner_ai.planning import settings_from_options

    assert settings_from_options({"region": "de"})["max_same_main"] == 3
    off = settings_from_options({"region": "de", "max_same_main": 0})
    assert off["max_same_main"] == 0 and not any(l["label"].startswith("Gerichte mit") for l in off["dish_limits"])
    assert {l["max"] for l in settings_from_options({"region": "de", "max_same_main": 2})["dish_limits"]
            if l["label"].startswith("Gerichte mit")} == {2}


def test_spices_skipped():
    from custom_components.meal_planner_ai.shopping import _is_staple

    assert _is_staple("Edelsüßpaprika", set(), True)
    assert _is_staple("Paprikapulver", set(), True)
    assert not _is_staple("Paprika", set(), True)
    assert not _is_staple("Paprikaschote", set(), True)
    assert _is_staple("ground cumin", set(), True) and _is_staple("Pimentón", set(), True)


def test_alternatives_do_not_count():
    from custom_components.meal_planner_ai.classify import classify_diet

    meat = {"ingredients": ["500 g Rinderhackfleisch (fleischlose Alternative: z.B. Soja-Hack)", "250 g Nudeln"]}
    assert classify_diet(meat, None)["vegetarian"] is False
    meat2 = {"ingredients": ["400 g Hähnchenbrust, alternativ Tofu", "1 Paprika"]}
    assert classify_diet(meat2, None)["vegetarian"] is False
    veg = {"ingredients": ["200 g Tofu (oder Tempeh)", "1 Zucchini"]}
    assert classify_diet(veg, None)["vegetarian"] is True
    veg2 = {"ingredients": ["200 g Räuchertofu", "Gemüsebrühe (statt Hühnerbrühe)"]}
    assert classify_diet(veg2, None)["vegetarian"] is True
