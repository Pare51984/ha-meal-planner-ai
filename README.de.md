# Meal Planner AI für Home Assistant (Essensplaner)

[English → README.md](README.md)

*Essensplaner · Wochenplan · Rezepte · Einkaufsliste · KI · meal planner · recipes · shopping list*

Importiert Rezepte per Link (z. B. Chefkoch), speichert sie lokal in Home Assistant,
schreibt Zutaten in eine To-do-Liste deiner Wahl (z. B. Bring!) und prüft Wochenpläne
gegen Ernährungs- und Geräte-Vorgaben. Keine Zusatz-App, kein Cloud-Dienst: abgerufen
wird nur die Rezeptseite selbst, über [recipe-scrapers](https://github.com/hhursev/recipe-scrapers) (MIT).

> **Status: frühe Version, Feedback erwünscht.** Die Integration läuft täglich in einem Haushalt (Home Assistant 2026.11,
> Deutsch, Bring!, Gemini, Claude als externe KI). Vieles ist noch nicht getestet, siehe „Was getestet ist“. Bitte
> ausprobieren und Rückmeldung in den [Issues](https://github.com/Pare51984/ha-meal-planner-ai/issues) geben.

## Installation
HACS → drei Punkte → *Benutzerdefinierte Repositories* → `https://github.com/Pare51984/ha-meal-planner-ai` als
*Integration* hinzufügen und **Meal Planner AI** installieren (oder `custom_components/meal_planner_ai` von Hand nach
`/config/custom_components/` kopieren), Home Assistant neu starten.

## Einrichtung
Einstellungen → Geräte & Dienste → Integration hinzufügen → **Meal Planner AI**.
Dort Einkaufsliste und Küchengeräte wählen. Ist noch die frühere Version „Essensplaner“ eingerichtet, bietet die Einrichtung an, deren Einstellungen zu übernehmen; Rezepte, Bewertungen, Wünsche und die eigene Liste werden automatisch übernommen. Danach die alte Integration löschen. Weitere Einstellungen (Rezeptquellen,
Ernährung, Rezepte pro Woche, Geräte pro Woche) über **Konfigurieren** oder direkt in der Karte
im Reiter **Einstellungen** (nur für Administratoren sichtbar; mit `settings: false` in der Karte ausblendbar).

## Aktionen
| Aktion | Zweck |
|---|---|
| `meal_planner_ai.import_recipe` | Rezept per Link laden und speichern (Kurzlinks werden aufgelöst) |
| `meal_planner_ai.get_recipe` / `list_recipes` | Gespeicherte Rezepte lesen |
| `meal_planner_ai.add_to_shopping_list` | Zutaten in die gewählte Liste, optional für andere Portionszahl |
| `meal_planner_ai.update_history` | Bewertung (1–5), gekocht am, Status, Notiz |
| `meal_planner_ai.import_history` | Bewertungen aus einem anderen Planer übernehmen |
| `meal_planner_ai.validate_plan` | Wochenauswahl gegen alle Vorgaben prüfen |
| `meal_planner_ai.get_settings` | Vorgaben für einen (KI-)Planer |
| `meal_planner_ai.delete_recipe` | Rezept löschen |
| `meal_planner_ai.generate_proposals` | KI erstellt die Wochenvorschläge (sonst automatisch nach Zeitplan) |
| `meal_planner_ai.more_proposals` | Weitere Gerichte zur Auswahl dazuholen |
| `meal_planner_ai.planning_brief` | Planungsauftrag für eine externe KI: Regeln, Wünsche, Termine, Antwortformat |
| `meal_planner_ai.submit_proposals` | Gerichte einer externen KI prüfen und in die Vorschläge übernehmen; Antwort nennt, was fehlt |
| `meal_planner_ai.external_setup` | Zeitplan und Aufgabentext für die geplante Aufgabe der externen KI |
| `meal_planner_ai.memory_overview` / `set_profile` | Geschmacksprofil und Rezeptsammlung lesen, Grundregeln ändern |
| `meal_planner_ai.choose_dish` | Gericht einem Einkauf zuordnen oder abwählen; Liste passt sich an |
| `meal_planner_ai.set_ingredients_ready` | Zutaten schon da: nicht (mehr) auf die Liste, ungekocht in die nächste Woche |
| `meal_planner_ai.mark_cooked` | Gekocht abhaken und bewerten |
| `meal_planner_ai.dish_items` / `set_items_at_home` | Zutaten eines Gerichts ansehen, einzelne als „schon da“ markieren |
| `meal_planner_ai.finalize_week` / `release_shopping` / `sync_shopping_list` | Schritte des Zeitplans von Hand |
| `meal_planner_ai.assess_recipes` | KI bewertet unklare Kriterien (z. B. cholesterinarm) |

Alle Aktionen liefern Antwortdaten (`response_variable`).

## Anzeige
Die Integration bringt die Karte `custom:meal-planner-card` mit und meldet sie selbst als Dashboard-Ressource an.
Unter **Konfigurieren → Anzeige** wählbar: eigene Seite „Essensplaner“ in der Seitenleiste, eine Ansicht „Essen“
in einem vorhandenen Dashboard (wird einmalig angelegt) oder keine, dann die Karte selbst über „Karte hinzufügen“ einfügen.
Farben folgen standardmäßig dem aktiven Home-Assistant-Design. Alternativ `preset: warm`, und einzelne Farben lassen
sich in der Karte überschreiben: `accent`, `accent_text`, `tile`, `tile_selected`, `tile_done`, `text`, `muted`,
`chip`, `chip_text`, `star`, `star_off`, `input`, `border`, `tile_border`, `radius`, `background`.

### Reiter „Geschmacksprofil“ und „Rezepte“
Die Essensplaner-Karte hat für Administratoren vier Reiter: Essensplan, Geschmacksprofil, Rezepte, Einstellungen.
**Geschmacksprofil** zeigt, was die KI über den Haushalt bekommt: Grundregeln (direkt bearbeitbar), gemocht (4–5 Sterne),
nicht gemocht (1–2 Sterne) und die in den letzten 4 Wochen gekochten Gerichte. **Rezepte** listet alle gespeicherten
Rezepte mit Suche und Sortierung. Sterne und Notizen lassen sich ändern, Bewertungen, Kochtage und Rezepte löschen.
Wer beides als eigene Karte woanders haben will, nimmt `custom:meal-planner-memory-card`.

## Wochenablauf
Einkäufe mit festem Termin (z. B. Samstag 12 Uhr) haben in der Karte einen Knopf **„jetzt einkaufen“**: Wer früher
einkauft, tippt ihn zweimal, und die gewählten Gerichte kommen sofort auf die Liste. Die Zeitleiste in „So geht's“ zeigt aus
den Einstellungen, wann was passiert.

**„Mehr Vorschläge“** holt jederzeit 5 weitere Gerichte zur Auswahl dazu, Vorhandenes bleibt. Typischer Ablauf: ein Gericht
auf „doch nicht“ stellen, „Mehr Vorschläge“ tippen, eines der neuen wählen. Läuft die Woche schon, erscheinen die neuen
Gerichte unter „Zur Auswahl für diese Woche“ und kommen erst auf die Einkaufsliste, wenn ihr einen Einkauf wählt. So geht auch
„wir brauchen diese Woche ein Gericht mehr“. Nicht gewählte Vorschläge lassen sich mit **„Entfernen“** wegräumen.

Alles ist einstellbar: Wann die Vorschläge kommen, wann Auswahlschluss ist und wie oft eingekauft wird
(1 bis 7 Einkäufe pro Woche, je mit Namen, Kochtagen und Freigabe „sofort“ oder „Wochentag + Uhrzeit“,
auch sonntags). Zum eingestellten Zeitpunkt (Standard Freitag 18 Uhr) erstellt die KI die Vorschläge für die kommende
Woche und berücksichtigt Wünsche (Liste `todo.meal_planner_wishes`), Bewertungen, zuletzt Gekochtes,
Saison und frei definierbare Kalender-Regeln (z. B. Kind isst mit, Gäste, Spätschicht). Die Integration prüft Links, Zeit, kcal und Anteile
selbst und lässt bei Verstößen nachbessern. Gewählte Gerichte kommen je nach Einkauf sofort oder zum
eingestellten Termin auf die Einkaufsliste. Zum Auswahlschluss
(Standard Samstag 12 Uhr) fällt Nicht-Gewähltes weg. Daten für Kacheln: `sensor.meal_planner_proposals`
und `sensor.meal_planner_week` (Attribut `dishes`).

## KI
Der Essensplaner nutzt die KI deines Systems über die AI-Task-Schnittstelle von Home Assistant,
z. B. Claude (Anthropic), ChatGPT (OpenAI) oder Gemini (Google). Unter **Konfigurieren → KI**
die AI-Task-Entität wählen. Die KI schlägt Gerichte vor, macht Artikelnamen katalogtauglich und
bewertet weiche Kriterien; Import, Regelprüfung und Speicherung erledigt die Integration selbst.

**Rezeptlinks:** Eine KI ohne Websuche kennt keine aktuellen Links. Darum prüft die Integration jeden Link;
fehlt er oder ist er tot, sucht sie das Gericht selbst auf den freigegebenen Rezeptseiten (z. B. die
Chefkoch-Suche) und nimmt nur Treffer, die sich als passendes Rezept auslesen lassen. Mit der Aktion
`meal_planner_ai.search_recipes` lässt sich die Suche je Seite ausprobieren.

**Optional: Such-Agent mit Websuche** für bessere Treffer (z. B. Cookidoo, das nur per Websuche
auffindbar ist). Im Schritt KI das Häkchen „Such-Agent mit Websuche automatisch anlegen“ setzen: Der
Essensplaner legt in deiner KI-Integration einen eigenen Gesprächsagenten „Essensplaner Rezeptsuche“ mit
Websuche an – bei Google Gemini mit „Google Search tool“, bei Claude (Anthropic) und ChatGPT (OpenAI) mit
„Web search“. Für Claude und ChatGPT braucht es ein API-Konto beim Anbieter (Abrechnung pro Nutzung,
getrennt von einem Chat-Abo). Bestehende Agenten und die Sprachsteuerung bleiben unverändert. Die Google-Suche ist im kostenlosen
Gemini-Tarif begrenzt (Fehler 429 = Kontingent erschöpft); dann greift automatisch die eigene Suche.
Tipp: Im kostenlosen Tarif von Google AI Studio lief im Test (11/2026) **Gemini 3.8 Flash** mit Google-Suche
problemlos und ohne Kosten (Modell in der Gemini-Integration beim Agenten einstellen). Mit Gemini 3.1 Flash Lite lehnte
Google die Suche im kostenlosen Tarif in einem früheren Test ab. Google liefert Links als Weiterleitung (vertexaisearch…); die Integration löst sie selbst auf.
Andere Anbieter: einen Gesprächsagenten mit Websuche und ohne KI-Werkzeuge selbst anlegen und unter
„Rezeptsuche“ auswählen.

### KI einrichten (Schritt für Schritt)
Einmalig unter **Einstellungen → Geräte & Dienste → Integration hinzufügen**:

| KI | Einrichtung | Kosten |
|---|---|---|
| **Claude (Anthropic)** – bei Denkmodus „Maximale Tokens“ deutlich erhöhen (Standard 3000 reicht nicht) | console.anthropic.com → „Billing“ Guthaben aufladen → „API Keys“ Schlüssel erstellen → Integration „Anthropic“ hinzufügen | pro Nutzung beim Anbieter |
| **Gemini (Google)** | aistudio.google.com → API-Schlüssel → Integration „Google Generative AI“ | kostenlos nutzbar (im Test mit Gemini 3.8 Flash); Google-Suche im Gratis-Tarif begrenzt |
| **ChatGPT (OpenAI)** | platform.openai.com → Guthaben + API-Schlüssel → Integration „OpenAI Conversation“ | pro Nutzung |

Danach im Essensplaner unter **KI** bei „Such-Agent mit Websuche anlegen bei“ den Anbieter wählen. Gute Mischung: Gemini
als Haupt-KI (kostenlos), Claude nur für die Rezeptsuche. API-Schlüssel nie weitergeben.

### Externe KI über dein Abo (ohne API-Schlüssel)
Statt einer KI in Home Assistant kann eine KI außerhalb die Rezepte heraussuchen, zum Beispiel dein Claude- oder
ChatGPT-Abo. Du legst dort einmal eine **geplante Aufgabe** an. Sie startet zur eingestellten Zeit, fragt den
Essensplaner, ob gerade geplant werden soll, holt sich den Auftrag mit deinen aktuellen Regeln, Wünschen und Terminen,
sucht die Rezepte im Web und gibt sie zurück. Der Essensplaner prüft jedes Gericht genauso wie bei der eingebauten KI
(Link, Zeit, kcal, Regeln, Ersatzsuche) und meldet zurück, was fehlt; die KI liefert dann nach.

**Was du brauchst**
1. Ein KI-Abo mit geplanten Aufgaben und Websuche. Getestet mit Claude. ChatGPT-Aufgaben können laut OpenAI seit 06/2026
   auch Connectors nutzen (eigene MCP-Connectors nur in bezahlten Tarifen), ungetestet. Ob geplante Aktionen in Gemini
   MCP-Verbindungen nutzen können, ist offen.
2. Eine Verbindung dieser KI zu Home Assistant über MCP. Am einfachsten: die offizielle Integration **Model Context
   Protocol Server** hinzufügen und dort die Werkzeug-Sammlung **„Meal Planner AI“** auswählen. Die KI darf damit nur den
   Auftrag holen und Vorschläge einreichen, sonst nichts. Alternativ geht jeder MCP-Server, der Aktionen aufrufen kann.
3. Fernzugriff auf Home Assistant von außen (z. B. Home Assistant Cloud oder Cloudflare), weil die KI im Internet läuft.

**Einrichten**
1. Erst alle Einstellungen fertig machen, vor allem Zeitplan, Regeln und Rezeptseiten.
2. Die KI einmal mit Home Assistant verbinden (MCP-Connector, siehe oben).
3. Der KI in einem neuen Chat schreiben: **„Richte meinen Essensplaner aus Home Assistant ein.“** Sie ruft
   `meal_planner_ai.external_setup` (bzw. das Werkzeug `meal_planner_setup`) auf, bekommt dort Anweisung, Zeitplan aus den
   Einstellungen und Aufgabentext, stellt auf „Externe KI“ um und legt die geplante Aufgabe in ihrem eigenen System an.
   Home Assistant selbst kann keine Aufgabe in der KI anlegen.
4. Klappt das nicht, zeigt die Karte im Reiter **Einstellungen** unter „Externe KI einrichten“ alles zum Anlegen von Hand.

Ändert man später **Planungstag oder Uhrzeit**, muss Schritt 3 wiederholt werden; die Karte zeigt dann einen Hinweis.
Alle anderen Einstellungen holt sich die Aufgabe bei jedem Lauf automatisch.

Wann wirklich geplant wird, entscheidet der Essensplaner: Ist nichts fällig, beendet sich die Aufgabe sofort. Kommt
fünf Stunden nach dem Planungszeitpunkt nichts, springt die KI in Home Assistant ein (falls eine gewählt ist); sonst
kommt eine Meldung. Hat die externe KI nur einen Teil geliefert, wird mit dem Vorhandenen abgeschlossen. Ändert man den
Planungszeitpunkt, muss nur die Uhrzeit der Aufgabe angepasst werden; der Einrichtungskasten zeigt die neue an.

**Was über den externen Weg nicht geht:** Die externe KI liefert nur die Wochenvorschläge zum geplanten Zeitpunkt. Alles,
was zwischendurch neue Gerichte braucht, läuft über die KI *in* Home Assistant. Ist unter **Konfigurieren → KI** keine
AI-Task-Entität gewählt, funktionieren nicht: **Mehr Vorschläge**, **Jetzt Vorschläge planen**
(`generate_proposals`), die KI-Bewertung der Ernährungsform (`assess_recipes`), die KI-Einkaufsnamen und die
Rückfallebene, wenn die externe KI nichts liefert. Tipp: zusätzlich eine kostenlose Gemini-KI auswählen. Dann geht all
das, und den Wochenplan macht trotzdem die externe KI.

## Was getestet ist
Live getestet: Home Assistant 2026.11 auf Raspberry Pi 4, Deutsch, Bring!, Gemini als KI und Such-Agent, Claude als
externe KI über eine geplante Aufgabe mit MCP-App, alle Anzeigearten, Übernahme vom Vorgänger „Essensplaner“.
Die automatischen Tests (95) laufen gegen Home Assistant 2026.2.

Je ein Testlauf mit KI-Task und Such-Agent anderer Anbieter (11/2026, sonst Standardeinstellungen):

| Modell | Ergebnis |
|---|---|
| OpenAI `gpt-6.1-terra` | bester Lauf: 10 Gerichte, die meisten Links von der KI selbst, ca. 1,5 Minuten |
| OpenAI `gpt-6.1-sol` | 10 Gerichte, weniger eigene Links, ca. 5 Minuten |
| Claude Sonnet 5.5 | 7 Gerichte, keine eigenen Links (alle über die eigene Suche) |
| Claude Haiku 5.5 | gescheitert: Die Standard-„Maximale Tokens“ (3000) gingen fürs Nachdenken drauf, leere Antwort |

**Noch nicht getestet, Tester willkommen:** die offizielle Integration *Model Context Protocol Server* als MCP-Weg,
Claude mit höheren „Maximale Tokens“, ChatGPT- und Gemini-Aufgaben als externe KI, Alltag auf Englisch, Spanisch,
Portugiesisch oder Französisch und außerhalb Deutschlands, andere Einkaufslisten als Bring! und die eigene Liste,
Installation über HACS.

## Hinweise
Die Einordnung (vegetarisch, vegan, laktose-/glutenfrei, Geräte) beruht auf Stichworten
in Zutaten und Schritten und ist nicht fehlerfrei. „Cholesterinarm“ wird bewusst nicht
automatisch entschieden. Bitte die Nutzungsbedingungen der Rezeptseiten beachten.

Lizenz: MIT
