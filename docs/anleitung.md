# Meal Planner AI – ausführliche Anleitung

[English version → guide.md](guide.md) · [Kurzüberblick → README](../README.de.md)

Diese Anleitung erklärt, wie der Essensplaner arbeitet: was wann passiert, was die KI macht und was die Integration
selbst prüft, wie die Karte zu bedienen ist und was jede Einstellung bewirkt.

## Inhalt
1. [Das Prinzip in einem Satz](#1-das-prinzip-in-einem-satz)
2. [Die Woche im Ablauf](#2-die-woche-im-ablauf)
3. [Die Karte bedienen](#3-die-karte-bedienen)
4. [Einkaufsliste](#4-einkaufsliste)
5. [Wie Vorschläge entstehen und geprüft werden](#5-wie-vorschläge-entstehen-und-geprüft-werden)
6. [KI auswählen](#6-ki-auswählen)
7. [Externe KI über MCP](#7-externe-ki-über-mcp)
8. [Geschmack, Bewertungen und Gedächtnis](#8-geschmack-bewertungen-und-gedächtnis)
9. [Alle Einstellungen erklärt](#9-alle-einstellungen-erklärt)
10. [Benachrichtigungen](#10-benachrichtigungen)
11. [Aktionen und Entitäten für Automationen](#11-aktionen-und-entitäten-für-automationen)
12. [Fragen und Probleme](#12-fragen-und-probleme)

## 1. Das Prinzip in einem Satz
Einmal pro Woche schlägt eine KI Gerichte mit echten Rezeptlinks vor, der Essensplaner prüft jedes Gericht selbst,
ihr wählt in der Karte aus, und die Zutaten landen zum passenden Zeitpunkt auf eurer Einkaufsliste.

Die KI macht nur Vorschläge. Abrufen, Prüfen, Speichern, Einkaufsliste und Zeitplan erledigt die Integration selbst,
lokal in Home Assistant.

## 2. Die Woche im Ablauf
Beispiel mit den Standardwerten: Vorschläge Freitag 18:00, Auswahlschluss Samstag 12:00, zwei Einkäufe.

| Wann | Was passiert |
|---|---|
| bis Freitag 18:00 | Ihr tragt Essenswünsche in der Karte ein (optional). |
| Freitag 18:00 | Die KI plant die kommende Woche. Das dauert einige Minuten. Danach kommt eine Push-Nachricht, und in der Karte erscheinen die **Vorschläge KW …** als Kacheln. |
| Freitag 18:00 bis Samstag 12:00 | Ihr wählt pro Gericht einen Einkauf aus. Was daheim ist, markiert ihr mit „Zutaten schon da“ oder „Teilweise da …“. Nicht passende Vorschläge entfernt ihr mit „✕ Entfernen“. |
| Samstag 12:00 (Auswahlschluss) | Nicht Gewähltes fällt weg. Die gewählten Gerichte werden zu **Diese Woche**, die alte Woche wird archiviert. |
| fester Einkaufstermin | Die Zutaten des Einkaufs kommen auf die Einkaufsliste, ohne das, was ihr als daheim markiert habt. |
| während der Woche | Gekochtes mit dem Kreis abhaken, optional mit Sternen bewerten. Braucht ihr ein Gericht mehr, holt „Mehr Vorschläge“ fünf weitere. |

**Übernahme in die neue Woche:** Ein Gericht aus der laufenden Woche, das noch nicht gekocht ist, dessen Zutaten aber
schon da sind, wird in die nächsten Vorschläge übernommen und ist dort schon gewählt. Wird es vor dem Auswahlschluss
doch noch gekocht, fällt die Kopie weg.

**Neustart oder Ausfall:** Der Essensplaner prüft stündlich, ob etwas fällig ist, und holt Verpasstes nach (z. B. nach
einem Neustart). Scheitert die KI, versucht er es bis zu drei Mal und meldet den Fehler einmal per Push.

## 3. Die Karte bedienen
Die Karte hat bis zu vier Reiter. „Geschmacksprofil“, „Rezepte“ und „Einstellungen“ sehen nur Administratoren.

### Bereiche im Reiter „Essensplan“
| Bereich | Bedeutung |
|---|---|
| **Vorschläge KW …** | Die neuen Vorschläge für die kommende Woche. Normalerweise nur zwischen Planung und Auswahlschluss sichtbar. |
| **Diese Woche** | Eure gewählten Gerichte der laufenden Woche. |
| **Zur Auswahl für diese Woche** | Zusätzliche Gerichte über „Mehr Vorschläge“ während der Woche. Sie kommen erst auf die Liste, wenn ihr einen Einkauf antippt. |
| **Essenswünsche** | Wünsche für die nächste Planung. |
| **So geht's** | Kurzhilfe und eine Zeitleiste, wann was passiert. |

### Knöpfe auf einer Kachel
| Knopf | Wirkung |
|---|---|
| Einkauf (z. B. „Sa–Di“) | Ordnet das Gericht diesem Einkauf zu. Nochmal tippen hebt die Auswahl auf. Gestrichelt = Tipp des Planers. |
| ✕ Entfernen | Nur bei nicht gewählten Vorschlägen: weg damit. Unten erscheint „Rückgängig“. |
| Doch nicht | Bei schon gewählten Gerichten: abwählen. Stehen die Zutaten schon auf der Liste, kommen sie wieder herunter. |
| Zutaten schon da | Alle Zutaten sind daheim, nichts kommt auf die Liste (oder wird wieder entfernt). |
| Teilweise da … | Einzelne Zutaten abhaken, die daheim sind. Nur der Rest kommt auf die Liste. |
| Kreis „gekocht“ | Speichert den Kochtag. Das Gericht wird dann 4 Wochen lang nicht wieder vorgeschlagen, und die Bewertung „Wie war's?“ öffnet sich. |
| Sterne, „+ Notiz“ | Bewertung und Notiz. Beides fließt in künftige Vorschläge ein. |

### Weitere Knöpfe
* **Mehr Vorschläge:** holt fünf weitere Gerichte. Vor dem Auswahlschluss kommen sie zu den Vorschlägen, während der Woche unter „Zur Auswahl für diese Woche“.
* **Übrige Vorschläge entfernen:** räumt alle nicht gewählten Gerichte unter „Zur Auswahl“ auf einmal weg (zweimal tippen).
* **🛒 „… jetzt einkaufen“:** erscheint bei Einkäufen mit festem Termin, solange der Termin noch nicht erreicht ist. Setzt die Zutaten sofort auf die Liste, wenn ihr früher einkaufen geht (zweimal tippen).
* **Jetzt Vorschläge planen:** plant die kommende Woche sofort statt zum eingestellten Termin (zweimal tippen).

### Essenswünsche
Ein Wunsch kann ein Gericht („Lasagne“), eine Zutat („was mit Kürbis“) oder ein Rezeptlink sein. Bei der nächsten Planung
versucht die KI, ihn einzubauen. Erfüllte Wünsche verschwinden von der Liste, offene bleiben für die nächste Woche stehen.
**Eigenes Rezept** heißt: ein Gericht ohne Rezept aus dem Netz (z. B. Omas Gulasch). Die Zutaten tragt ihr dann selbst ein.

## 4. Einkaufsliste
* **Welche Liste:** jede To-do-Liste in Home Assistant, die Einträge annimmt, z. B. Bring!, oder eine eigene Liste des Essensplaners.
* **Format:** Artikelname als Eintrag, Menge und Gericht in der Beschreibung (Bring!-Muster). Kommt eine Zutat in mehreren Gerichten vor, werden die Mengen beim selben Eintrag zusammengeführt.
* **Mengen** werden auf die eingestellten Portionen umgerechnet.
* **Grundzutaten** (z. B. Salz, Öl) und auf Wunsch getrocknete Gewürze kommen nie auf die Liste.
* **Katalognamen:** „passierte Tomaten = Dosentomaten“ sorgt dafür, dass ein Artikel auf der Liste immer gleich heißt.
* **KI-Artikelnamen** (optional): aus „1 rote Paprikaschote, gewürfelt“ wird „Paprika“.
* **Wann etwas auf die Liste kommt:** Jeder Einkauf ist entweder „Sofort“ (beim Antippen) oder „Fester Termin“ (zum gewählten Wochentag und zur Uhrzeit). Wer vor dem Termin auswählt und markiert, was daheim ist, bekommt nur den Rest auf die Liste. Nach dem Termin gewählte Gerichte kommen sofort drauf. „Zutaten schon da“ oder „Teilweise da“ nimmt sie auch nachträglich wieder herunter.
* **Wieder entfernen:** Jeder Eintrag merkt sich, zu welchem Gericht er gehört. Wählt ihr ein Gericht ab, verschwinden genau seine Mengen, andere Gerichte bleiben unberührt.

## 5. Wie Vorschläge entstehen und geprüft werden
1. **Auftrag an die KI:** Regeln, Ernährung, Geräte, Gewohnheiten, Kalender-Termine, Geschmacksprofil, Bewertungen, zuletzt Gekochtes und offene Wünsche. Die KI soll etwas mehr Ideen liefern als nötig, weil ein Teil bei der Prüfung durchfällt.
2. **Rezept abrufen:** Jeder Link wird geladen und mit [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) gelesen: Titel, Zutaten, Zeit, Nährwerte. Nur abrufbare Rezepte werden angenommen.
3. **Ersatzsuche:** Fehlt der Link, ist er tot oder führt er zu einem anderen Gericht, sucht der Essensplaner dasselbe Gericht selbst auf euren eingeschalteten Rezeptseiten. Ein Treffer muss dieselbe Hauptzutat haben, und ein vegetarisch gemeintes Gericht wird nie durch eines mit Fleisch oder Fisch ersetzt.
4. **Prüfung jedes Gerichts:** Zeit höchstens, kcal-Grenzen, Ernährungsformen (vegetarisch, vegan, laktose- und glutenfrei erkennt die Integration an den Zutaten; cholesterinarm bewertet die KI), Küchengeräte, in den letzten 4 Wochen gekocht, schlecht bewertet, doppelt.
5. **Wochenregeln:** Anteil schneller Gerichte, Mindestanzahlen je Ernährungsform, höchstens so viele Gerichte mit derselben Hauptzutat, Gewohnheiten mit „höchstens …x“.
6. **Nachrunden:** Fehlt noch etwas, bekommt die KI eine Rückmeldung, was abgelehnt wurde und warum, und liefert nach. Abgelehnte Gerichte schlägt sie nicht erneut vor.

Am Ende steht eine Tafel mit so vielen Gerichten wie eingestellt. Reicht es nicht, sagt die Push-Nachricht, was fehlt.

## 6. KI auswählen
Unter **Einstellungen → KI** legt ihr fest, wer plant.

| Feld | Bedeutung |
|---|---|
| Wer macht die Vorschläge? | „KI in Home Assistant“ (Normalfall) oder „Externe KI“ (siehe Abschnitt 7). |
| Haupt-KI | Eine AI-Task-Entität (Gemini, Claude, ChatGPT …). Plant, bewertet „cholesterinarm“ und vereinfacht auf Wunsch Artikelnamen. |
| Rezeptsuche im Web | Ein Gesprächsagent mit Websuche. Er findet echte Links, auch auf Cookidoo. Ohne Agent nennt die Haupt-KI nur Gerichte, und der Essensplaner sucht selbst (ohne Cookidoo). |
| Neuen Such-Agenten anlegen bei | Legt beim gewählten Anbieter einen Agenten „Essensplaner Rezeptsuche (Anbieter)“ an. |

**Der angelegte Such-Agent** bekommt bei jedem Anbieter dieselben Grundeinstellungen: ein aktuelles, günstiges Modell
(Gemini `gemini-3.8-flash`, Claude `claude-haiku-5-5`, ChatGPT `gpt-6.1-terra`), Websuche an, 16000 „Maximale Tokens“ und
keinen Zugriff auf euer Haus. Das Modell könnt ihr jederzeit in der Integration des Anbieters ändern.

**Tipp:** Gemini lässt sich mit einem Schlüssel aus Google AI Studio kostenlos nutzen (mit Kontingent). Claude und
ChatGPT brauchen ein API-Konto mit Guthaben beim Anbieter. Das ist getrennt von einem Chat-Abo.

**Wichtig bei Claude mit Denkmodus:** „Maximale Tokens“ muss deutlich über dem Standard von 3000 liegen, sonst bleibt
die Antwort leer. Der automatisch angelegte Agent hat 16000.

## 7. Externe KI über MCP
Statt einer KI in Home Assistant kann eine geplante Aufgabe in einem KI-Abo die Vorschläge liefern (getestet mit Claude).
Die Aufgabe holt sich über MCP den Planungsauftrag (`planning_brief`), sucht Rezepte und reicht sie ein (`submit_proposals`).
Der Essensplaner prüft sie genauso wie in Abschnitt 5.

**Einrichtung mit der offiziellen Integration „Model Context Protocol Server“:**
1. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Model Context Protocol Server**.
2. Unter **Konfigurieren** „Alle LLM-APIs“ **ausschalten** und nur **„Meal Planner AI“** ankreuzen. Sonst kann die KI über diesen Zugang auch euer Haus steuern.
3. In der KI (z. B. Claude → Einstellungen → Connectors) einen eigenen Connector mit `https://<eure-ha-adresse>/api/mcp` anlegen und mit dem Home-Assistant-Konto anmelden. Home Assistant muss von außen erreichbar sein.
4. Der KI schreiben: „Richte meinen Essensplaner aus Home Assistant ein.“ Sie legt die geplante Aufgabe an. Klappt das nicht, zeigt die Karte unter **Einstellungen → Externe KI einrichten** alles zum Anlegen von Hand.

**Was über den externen Weg nicht geht:** „Mehr Vorschläge“, „Jetzt Vorschläge planen“, die KI-Bewertung der
Ernährungsform, KI-Artikelnamen und die Rückfallebene brauchen eine KI *in* Home Assistant. Tipp: zusätzlich eine
kostenlose Gemini-KI auswählen. Kommt fünf Stunden nach dem Planungstermin nichts von der externen KI, springt sie ein.

## 8. Geschmack, Bewertungen und Gedächtnis
* **Geschmack (Freitext):** wird bei jeder Planung mitgegeben, z. B. „gern mediterran, keine Innereien“.
* **Gemocht (4–5 Sterne)** wird der KI als Vorbild genannt, **nicht gemocht (1–2 Sterne)** wird nicht mehr vorgeschlagen.
* **In den letzten 4 Wochen gekocht** wird nicht erneut vorgeschlagen. Grundlage ist nur der Kreis „gekocht“.
* **Reiter „Geschmacksprofil“:** Freitext, Gemocht, Nicht gemocht, zuletzt Gekochtes. Mit ✕ entfernt ihr einen Eintrag.
* **Reiter „Rezepte“:** alle bewerteten Rezepte mit Suche, Sortierung, Notiz und Löschen.

Alle Daten liegen lokal in Home Assistant. Beim Löschen der Integration werden sie mit entfernt.

## 9. Alle Einstellungen erklärt
Erreichbar in der Karte unter **Einstellungen** oder unter Geräte & Dienste → Meal Planner AI → Konfigurieren.

| Bereich | Was ihr dort festlegt |
|---|---|
| Sprache und Region | Land der Rezepte: bestimmt Rezeptseiten, Sprache der Gerichte und Artikel, Cookidoo-Land. Die Bedienoberfläche folgt eurem Home-Assistant-Profil. |
| Zeitplan und Benachrichtigungen | Wochentag und Uhrzeit der Vorschläge, Auswahlschluss, wer Push-Nachrichten bekommt, welche Seite sich beim Antippen öffnet. |
| Einkäufe | Anzahl Einkäufe pro Woche (1 bis 7). Je Einkauf: Name (wird zum Knopf), Kochtage (Hinweis an die KI), „Sofort“ oder „Fester Termin“. |
| Kalender | Bis zu drei Regeln: Kalender, optional Stichwort, Bedeutung („eine Person mehr“, „nur schnelle Gerichte“). Passende Gerichte bekommen ein Kennzeichen. |
| Regeln und Geschmack | Portionen, Zeit höchstens, was als „schnell“ gilt und wie viele schnelle Gerichte pro Woche, Geschmack, kalorienbewusst (kcal pro Portion mit und ohne Beilage), Abwechslung bei der Hauptzutat. |
| Essgewohnheiten | Bis zu fünf Regeln in eigenen Worten. Mit „höchstens …x“ zählt die Integration selbst nach. |
| Ernährung und Vorschläge pro Woche | Anzahl Vorschläge. Je Ernährungsform: Aus, Immer oder Anteilig mit Mindestanzahl. |
| Einkaufsliste | Ziel-Liste, Grundzutaten, Gewürze weglassen, Katalognamen. |
| Rezeptquellen | Welche Seiten genutzt werden (an/aus). Eigene Seiten fügt ihr über einen Beispiel-Rezeptlink hinzu, die Integration prüft, ob sie lesbar sind. Unter „Seiten entfernen“ verschwinden eigene und mitgelieferte Seiten aus der Liste. Mitgelieferte holt ihr über „Entfernte Seiten wiederherstellen“ jederzeit zurück. |
| Küchengeräte | Vorhandene Geräte, optional Mindestanzahl Gerichte pro Gerät. Thermomix-Rezepte nur mit Thermomix. |
| KI | Siehe Abschnitt 6. |
| Anzeige | Eigene Seite in der Seitenleiste, Ansicht in einem Dashboard oder keine (Karte selbst einfügen). Farben wie Home Assistant oder „Warm“. |

Änderungen gelten sofort für den ganzen Haushalt. Ändert ihr während einer laufenden Planung etwas, rechnet diese mit
den alten Werten zu Ende.

## 10. Benachrichtigungen
Push-Nachrichten (an die unter „Zeitplan“ gewählten Geräte) gibt es bei:
* neuen Vorschlägen, mit Anzahl, fleischlosen und cholesterinarmen Gerichten, erfüllten und offenen Wünschen und dem, was fehlt,
* „Essensplan steht“ nach dem Auswahlschluss,
* Fehlern der KI (einmal pro Woche) und wenn eine externe KI nichts geliefert hat.

## 11. Aktionen und Entitäten für Automationen
Alle Aktionen liefern Antwortdaten. Die wichtigsten:

| Aktion | Zweck |
|---|---|
| `meal_planner_ai.generate_proposals` | Vorschläge jetzt erstellen (`force: true` plant neu, auch wenn schon Vorschläge da sind). |
| `meal_planner_ai.more_proposals` | Weitere Gerichte zur Auswahl. |
| `meal_planner_ai.choose_dish` | Einkauf wählen, abwählen (`none`) oder entfernen (`declined`). |
| `meal_planner_ai.set_ingredients_ready` / `set_items_at_home` | Zutaten ganz bzw. teilweise daheim. |
| `meal_planner_ai.mark_cooked` | Gekocht, mit Bewertung und Notiz. |
| `meal_planner_ai.release_shopping` | Einkauf mit festem Termin jetzt freigeben. |
| `meal_planner_ai.finalize_week` / `sync_shopping_list` | Auswahlschluss bzw. Abgleich mit der Liste von Hand. |
| `meal_planner_ai.import_recipe` / `get_recipe` / `list_recipes` / `delete_recipe` | Rezepte. |
| `meal_planner_ai.import_week` | Woche übernehmen; mit leerer Liste und `board: next` werden Vorschläge verworfen. |
| `meal_planner_ai.import_history` / `update_history` / `memory_overview` / `set_profile` | Gedächtnis. |
| `meal_planner_ai.planning_brief` / `submit_proposals` / `external_setup` | Für eine externe KI. |

Entitäten: `sensor.meal_planner_proposals` (Vorschläge, Attribut `dishes`), `sensor.meal_planner_week` (laufende Woche),
`todo.meal_planner_wishes` (Wünsche) und bei eigener Liste `todo.meal_planner_shopping_list`.

## 12. Fragen und Probleme
**Es kommen weniger Gerichte als eingestellt.** Die Prüfung ist streng. Häufige Gründe stehen in der Push-Nachricht,
z. B. zu wenige schnelle oder vegetarische Gerichte. Hilft: mehr Rezeptseiten einschalten, einen Such-Agenten mit
Websuche nutzen, Regeln lockern.

**Die KI meldet einen Fehler oder eine leere Antwort.** Bei Modellen mit Denkmodus „Maximale Tokens“ in der
KI-Integration erhöhen. Bei Gemini im Gratis-Tarif bedeutet Fehler 429, dass das Kontingent erschöpft ist.

**Ein Gericht ist falsch als vegetarisch markiert.** Die Einordnung beruht auf Stichwörtern in Zutaten und Titel und ist
nicht perfekt. Bitte mit Rezeptlink als Issue melden.

**Die Karte reagiert langsam, während geplant wird.** Beim Planen lädt Home Assistant viele Rezeptseiten. Auf kleiner
Hardware (z. B. Raspberry Pi) kann das kurz bremsen.

**Was kostet das?** Die Integration selbst nichts. Kosten entstehen nur beim KI-Anbieter, je nach Modell und Tarif.

**Fehler gefunden oder Wunsch?** Bitte als [Issue auf GitHub](https://github.com/Pare51984/ha-meal-planner-ai/issues)
melden, am besten mit Home-Assistant-Version, KI-Anbieter, Einkaufsliste und einem Log-Auszug
(`custom_components.meal_planner_ai`).
