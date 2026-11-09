"""Einrichtungshilfe für eine externe KI (z. B. geplante Aufgabe in Claude, ChatGPT oder Gemini).

Liefert den Zeitplan passend zu den Einstellungen und den Aufgabentext zum Kopieren, in der Sprache der Region.
Die eigentliche Planung (Regeln, Wünsche, Termine) holt sich die KI bei jedem Lauf frisch über planning_brief.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

from .const import CONF_PLAN_DAY, CONF_PLAN_TIME, CONF_REGION, EXTERNAL_FALLBACK_HOURS

# Läufe nach dem Planungszeitpunkt (Minuten): drei Chancen, alle vor der Rückfallebene
RUN_OFFSETS = (5, 125, 245)

DAYS = {
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
    "pt": ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"],
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
}

TEXTS: dict[str, dict[str, Any]] = {
    "de": {
        "steps": [
            "Mach zuerst die Einstellungen fertig, vor allem Zeitplan, Regeln und Rezeptseiten.",
            "Verbinde deine KI einmal mit Home Assistant: in der KI einen Connector mit der Adresse deines MCP-Servers hinzufügen (siehe oben).",
            "Schreib ihr in einem neuen Chat mit diesem Connector: „{phrase}“",
            "Die KI holt sich beim Essensplaner alles Nötige, stellt auf „Externe KI“ um und legt die geplante Aufgabe an. Vor dem Anlegen fragt sie meist noch einmal nach, ob das so passt.",
            "Prüfe danach in der KI bei den geplanten Aufgaben (Claude: geplante Aufgaben, ChatGPT: Aufgaben, Gemini: geplante Aktionen), ob sie mit dem richtigen Zeitplan da ist.",
            "Änderst du später Planungstag oder Uhrzeit, wiederhole Schritt 3, damit die KI den neuen Zeitplan übernimmt. Alle anderen Einstellungen holt sich die Aufgabe bei jedem Lauf automatisch.",
        ],
        "phrase": "Richte meinen Essensplaner aus Home Assistant ein.",
        "ai": (
            "Der Nutzer möchte, dass du die Rezepte für seinen Essensplaner in Home Assistant heraussuchst. Home Assistant "
            "kann dafür keine Aufgabe bei dir anlegen, das musst du in deinem eigenen System tun (nicht in Home Assistant). "
            "Lege eine wiederkehrende geplante Aufgabe an: Name „{name}“, Zeitplan {schedule} (Zeitzone {tz}){cron}, "
            "als Aufgabentext genau den Text aus task_text. Die Aufgabe braucht bei jedem Lauf dieselbe Verbindung zu "
            "Home Assistant wie jetzt und Websuche. Sag dem Nutzer vorher kurz, was du anlegst, und bestätige danach Name "
            "und Zeitplan. Gibt es bei dir schon eine Aufgabe mit diesem Namen, passe sie an, statt eine zweite anzulegen. {activate}Kannst du keine geplanten Aufgaben anlegen, sag das ehrlich und nenne den Weg über "
            "die Essensplaner-Karte (Reiter Einstellungen) zum Anlegen von Hand."
        ),
        "activate_on": "Der Essensplaner steht bereits auf „Externe KI“. ",
        "activate_off": "Der Essensplaner steht noch auf „KI in Home Assistant“: Rufe zuerst meal_planner_ai.external_setup mit activate: true auf (bzw. das Werkzeug meal_planner_setup mit activate: true), damit er deine Vorschläge erwartet. ",
        "name": "Essensplaner Rezeptsuche",
        "chat": "Lege bitte eine geplante Aufgabe an.\nName: Essensplaner Rezeptsuche\nZeitplan: {schedule} (Zeitzone {tz})\nAufgabentext:\n{task}",
        "schedule": "{day} um {times}",
        "fallback": "Kommt bis {day} {time} nichts, plant die KI in Home Assistant (falls eine gewählt ist).",
        "task": (
            "Du recherchierst die Wochenrezepte für meinen Essensplaner in Home Assistant. Niemand sitzt daneben: "
            "nicht nachfragen.\n"
            "1. Rufe in Home Assistant meal_planner_ai.planning_brief mit Antwortdaten auf (als Aktion oder als Werkzeug "
            "„meal_planner_planning_brief“, je nachdem, was deine Verbindung anbietet).\n"
            "2. Ist due false, beende den Lauf sofort ohne Nachricht.\n"
            "3. Sonst befolge den Auftrag im Feld prompt genau: Suche jedes Gericht im Web und nimm nur Rezeptlinks, "
            "die du in deinen Suchergebnissen gesehen hast. Rate keine Links.\n"
            "4. Rufe meal_planner_ai.submit_proposals mit dishes = Liste der Gerichte im Format aus dem Auftrag auf.\n"
            "5. Lies die Antwort: Ist need größer als 0 oder sind deficits offen, recherchiere passende weitere "
            "Gerichte (problems sagt, warum etwas verworfen wurde) und rufe submit_proposals erneut auf. Höchstens "
            "vier Aufrufe, beim letzten final: true setzen.\n"
            "6. Antworte zum Schluss mit einer kurzen Liste der übernommenen Gerichte."
        ),
        "req_ai": "Ein KI-Abo mit geplanten Aufgaben und Websuche (z. B. Claude, ChatGPT; Gemini ungetestet)",
        "req_mcp": "Eine Verbindung dieser KI zu deinem Home Assistant über MCP: entweder die Integration "
                   "„Model Context Protocol Server“ mit der Werkzeug-Sammlung „Meal Planner AI“ oder ein MCP-Server, "
                   "der Aktionen aufrufen kann",
        "req_remote": "Fernzugriff auf Home Assistant von außen (z. B. Home Assistant Cloud oder Cloudflare), "
                      "weil die KI im Internet läuft",
    },
    "en": {
        "steps": [
            "Finish the settings first, especially schedule, rules and recipe sites.",
            "Connect your AI to Home Assistant once: add a connector with your MCP server's address in the AI (see above).",
            "In a new chat with that connector, write: “{phrase}”",
            "The AI fetches everything it needs from the meal planner, switches to “External AI” and creates the scheduled task. It usually asks you to confirm first.",
            "Afterwards check the AI's scheduled tasks (Claude: scheduled tasks, ChatGPT: tasks, Gemini: scheduled actions) to see it is there with the right schedule.",
            "If you later change the planning day or time, repeat step 3 so the AI takes over the new schedule. All other settings are fetched by the task automatically on every run.",
        ],
        "phrase": "Set up my meal planner from Home Assistant.",
        "ai": (
            "The user wants you to find the recipes for their meal planner in Home Assistant. Home Assistant cannot create "
            "a task with you, so you must do it in your own system (not in Home Assistant). Create a recurring scheduled "
            "task: name “{name}”, schedule {schedule} (time zone {tz}){cron}, with exactly the text from task_text as "
            "the task text. Every run needs the same Home Assistant connection as now and web search. Briefly tell the "
            "user what you are about to create, then confirm name and schedule. If you already have a task with this name, update it instead of creating a second one. {activate}If you cannot create scheduled "
            "tasks, say so honestly and point to the meal planner card (Settings tab) for creating it by hand."
        ),
        "activate_on": "The meal planner is already set to “External AI”. ",
        "activate_off": "The meal planner is still set to “AI in Home Assistant”: first call meal_planner_ai.external_setup with activate: true (or the tool meal_planner_setup with activate: true) so it expects your proposals. ",
        "name": "Meal planner recipe search",
        "chat": "Please create a scheduled task.\nName: Meal planner recipe search\nSchedule: {schedule} (time zone {tz})\nTask text:\n{task}",
        "schedule": "{day} at {times}",
        "fallback": "If nothing arrives by {day} {time}, the AI in Home Assistant plans (if one is selected).",
        "task": (
            "You research the weekly recipes for my meal planner in Home Assistant. Nobody is watching: don't ask "
            "questions.\n"
            "1. In Home Assistant, call meal_planner_ai.planning_brief with response data (as an action or as the tool "
            "“meal_planner_planning_brief”, whichever your connection offers).\n"
            "2. If due is false, end the run right away without a message.\n"
            "3. Otherwise follow the brief in the prompt field exactly: search the web for every dish and only use "
            "recipe links you saw in your search results. Never guess links.\n"
            "4. Call meal_planner_ai.submit_proposals with dishes = list of dishes in the format from the brief.\n"
            "5. Read the response: if need is greater than 0 or deficits are open, research suitable further dishes "
            "(problems says why something was rejected) and call submit_proposals again. At most four calls; set "
            "final: true on the last one.\n"
            "6. Finally reply with a short list of the accepted dishes."
        ),
        "req_ai": "An AI subscription with scheduled tasks and web search (e.g. Claude, ChatGPT; Gemini untested)",
        "req_mcp": "A connection from that AI to your Home Assistant via MCP: either the “Model Context Protocol "
                   "Server” integration with the “Meal Planner AI” tool set, or an MCP server that can call actions",
        "req_remote": "Remote access to Home Assistant from outside (e.g. Home Assistant Cloud or Cloudflare), "
                      "because the AI runs on the internet",
    },
    "es": {
        "steps": [
            "Termina primero los ajustes, sobre todo horario, reglas y webs de recetas.",
            "Conecta una vez tu IA con Home Assistant: añade en la IA un conector con la dirección de tu servidor MCP (ver arriba).",
            "En un chat nuevo con ese conector escribe: «{phrase}»",
            "La IA recoge del planificador todo lo necesario, cambia a «IA externa» y crea la tarea programada. Normalmente antes te pide confirmación.",
            "Después comprueba en las tareas programadas de la IA (Claude: tareas programadas, ChatGPT: tareas, Gemini: acciones programadas) que está con el horario correcto.",
            "Si más adelante cambias el día o la hora de planificación, repite el paso 3 para que la IA adopte el nuevo horario. Los demás ajustes los recoge la tarea automáticamente en cada ejecución.",
        ],
        "phrase": "Configura mi planificador de comidas de Home Assistant.",
        "ai": (
            "El usuario quiere que busques las recetas para su planificador de comidas en Home Assistant. Home Assistant no "
            "puede crear una tarea contigo; tienes que hacerlo en tu propio sistema (no en Home Assistant). Crea una tarea "
            "programada recurrente: nombre «{name}», horario {schedule} (zona horaria {tz}){cron}, y como texto de la tarea "
            "exactamente el texto de task_text. Cada ejecución necesita la misma conexión con Home Assistant que ahora y "
            "búsqueda web. Di brevemente al usuario qué vas a crear y confirma después nombre y horario. Si ya tienes una tarea con este nombre, actualízala en lugar de crear otra. {activate}Si no "
            "puedes crear tareas programadas, dilo con honestidad e indica la tarjeta del planificador (pestaña Ajustes) para crearla a mano."
        ),
        "activate_on": "El planificador ya está en «IA externa». ",
        "activate_off": "El planificador aún está en «IA en Home Assistant»: llama primero a meal_planner_ai.external_setup con activate: true (o a la herramienta meal_planner_setup con activate: true) para que espere tus propuestas. ",
        "name": "Búsqueda de recetas del planificador",
        "chat": "Crea por favor una tarea programada.\nNombre: Búsqueda de recetas del planificador\nHorario: {schedule} (zona horaria {tz})\nTexto de la tarea:\n{task}",
        "schedule": "{day} a las {times}",
        "fallback": "Si no llega nada antes del {day} a las {time}, planifica la IA de Home Assistant (si hay una elegida).",
        "task": (
            "Buscas las recetas de la semana para mi planificador de comidas en Home Assistant. Nadie está mirando: "
            "no hagas preguntas.\n"
            "1. En Home Assistant, llama a meal_planner_ai.planning_brief con datos de respuesta (como acción o como la "
            "herramienta «meal_planner_planning_brief», según lo que ofrezca tu conexión).\n"
            "2. Si due es false, termina enseguida sin mensaje.\n"
            "3. Si no, sigue exactamente el encargo del campo prompt: busca cada plato en la web y usa solo enlaces "
            "de recetas que hayas visto en tus resultados. No adivines enlaces.\n"
            "4. Llama a meal_planner_ai.submit_proposals con dishes = lista de platos en el formato del encargo.\n"
            "5. Lee la respuesta: si need es mayor que 0 o hay deficits abiertos, busca más platos adecuados "
            "(problems dice por qué se descartó algo) y vuelve a llamar a submit_proposals. Como máximo cuatro "
            "llamadas; en la última pon final: true.\n"
            "6. Al final responde con una lista corta de los platos aceptados."
        ),
        "req_ai": "Una suscripción de IA con tareas programadas y búsqueda web (p. ej. Claude, ChatGPT; Gemini sin probar)",
        "req_mcp": "Una conexión de esa IA con tu Home Assistant por MCP: la integración «Model Context Protocol "
                   "Server» con el conjunto de herramientas «Meal Planner AI», o un servidor MCP que pueda llamar acciones",
        "req_remote": "Acceso remoto a Home Assistant desde fuera (p. ej. Home Assistant Cloud o Cloudflare), "
                      "porque la IA funciona en internet",
    },
    "pt": {
        "steps": [
            "Termina primeiro as definições, sobretudo horário, regras e sites de receitas.",
            "Liga uma vez a tua IA ao Home Assistant: adiciona na IA um conector com o endereço do teu servidor MCP (ver acima).",
            "Num chat novo com esse conector escreve: «{phrase}»",
            "A IA vai buscar ao planeador tudo o que precisa, muda para «IA externa» e cria a tarefa agendada. Normalmente pede-te confirmação antes.",
            "Depois verifica nas tarefas agendadas da IA (Claude: tarefas agendadas, ChatGPT: tarefas, Gemini: ações agendadas) se está lá com o horário certo.",
            "Se mais tarde mudares o dia ou a hora de planeamento, repete o passo 3 para a IA adotar o novo horário. As outras definições são lidas pela tarefa automaticamente em cada execução.",
        ],
        "phrase": "Configura o meu planeador de refeições do Home Assistant.",
        "ai": (
            "O utilizador quer que pesquises as receitas para o seu planeador de refeições no Home Assistant. O Home "
            "Assistant não consegue criar uma tarefa contigo; tens de o fazer no teu próprio sistema (não no Home Assistant). "
            "Cria uma tarefa agendada recorrente: nome «{name}», horário {schedule} (fuso horário {tz}){cron}, e como texto "
            "da tarefa exatamente o texto de task_text. Cada execução precisa da mesma ligação ao Home Assistant que agora e "
            "de pesquisa web. Diz brevemente ao utilizador o que vais criar e confirma depois nome e horário. Se já tiveres uma tarefa com este nome, atualiza-a em vez de criar outra. {activate}Se "
            "não conseguires criar tarefas agendadas, di-lo com honestidade e indica o cartão do planeador (separador Definições) para a criar à mão."
        ),
        "activate_on": "O planeador já está em «IA externa». ",
        "activate_off": "O planeador ainda está em «IA no Home Assistant»: chama primeiro meal_planner_ai.external_setup com activate: true (ou a ferramenta meal_planner_setup com activate: true) para que espere as tuas propostas. ",
        "name": "Pesquisa de receitas do planeador",
        "chat": "Cria por favor uma tarefa agendada.\nNome: Pesquisa de receitas do planeador\nHorário: {schedule} (fuso horário {tz})\nTexto da tarefa:\n{task}",
        "schedule": "{day} às {times}",
        "fallback": "Se nada chegar até {day} às {time}, a IA do Home Assistant planeia (se houver uma escolhida).",
        "task": (
            "Pesquisas as receitas da semana para o meu planeador de refeições no Home Assistant. Ninguém está a ver: "
            "não faças perguntas.\n"
            "1. No Home Assistant, chama meal_planner_ai.planning_brief com dados de resposta (como ação ou como a "
            "ferramenta «meal_planner_planning_brief», conforme o que a tua ligação oferecer).\n"
            "2. Se due for false, termina logo sem mensagem.\n"
            "3. Caso contrário, segue exatamente o pedido no campo prompt: pesquisa cada prato na web e usa só links "
            "de receitas que viste nos resultados. Nunca adivinhes links.\n"
            "4. Chama meal_planner_ai.submit_proposals com dishes = lista de pratos no formato do pedido.\n"
            "5. Lê a resposta: se need for maior que 0 ou houver deficits em aberto, pesquisa mais pratos adequados "
            "(problems diz porque algo foi rejeitado) e chama submit_proposals de novo. No máximo quatro chamadas; "
            "na última define final: true.\n"
            "6. No fim responde com uma lista curta dos pratos aceites."
        ),
        "req_ai": "Uma subscrição de IA com tarefas agendadas e pesquisa web (p. ex. Claude, ChatGPT; Gemini não testado)",
        "req_mcp": "Uma ligação dessa IA ao teu Home Assistant por MCP: a integração «Model Context Protocol Server» "
                   "com o conjunto de ferramentas «Meal Planner AI», ou um servidor MCP que consiga chamar ações",
        "req_remote": "Acesso remoto ao Home Assistant a partir de fora (p. ex. Home Assistant Cloud ou Cloudflare), "
                      "porque a IA corre na internet",
    },
    "fr": {
        "steps": [
            "Termine d'abord les réglages, surtout l'horaire, les règles et les sites de recettes.",
            "Connecte une fois ton IA à Home Assistant : ajoute dans l'IA un connecteur avec l'adresse de ton serveur MCP (voir plus haut).",
            "Dans une nouvelle discussion avec ce connecteur, écris : « {phrase} »",
            "L'IA récupère tout ce qu'il faut auprès du planificateur, passe sur « IA externe » et crée la tâche planifiée. En général, elle te demande d'abord de confirmer.",
            "Vérifie ensuite dans les tâches planifiées de l'IA (Claude : tâches planifiées, ChatGPT : tâches, Gemini : actions planifiées) qu'elle y est avec le bon horaire.",
            "Si tu changes plus tard le jour ou l'heure de planification, refais l'étape 3 pour que l'IA reprenne le nouvel horaire. Les autres réglages sont récupérés automatiquement par la tâche à chaque exécution.",
        ],
        "phrase": "Configure mon planificateur de repas de Home Assistant.",
        "ai": (
            "L'utilisateur veut que tu cherches les recettes pour son planificateur de repas dans Home Assistant. Home "
            "Assistant ne peut pas créer de tâche chez toi ; tu dois le faire dans ton propre système (pas dans Home "
            "Assistant). Crée une tâche planifiée récurrente : nom « {name} », horaire {schedule} (fuseau horaire {tz}){cron}, "
            "avec comme texte de tâche exactement le texte de task_text. Chaque exécution a besoin de la même connexion à "
            "Home Assistant qu'en ce moment et de la recherche web. Dis brièvement à l'utilisateur ce que tu vas créer, puis "
            "confirme le nom et l'horaire. Si tu as déjà une tâche de ce nom, mets-la à jour au lieu d'en créer une deuxième. {activate}Si tu ne peux pas créer de tâches planifiées, dis-le honnêtement et "
            "indique la carte du planificateur (onglet Réglages) pour la créer à la main."
        ),
        "activate_on": "Le planificateur est déjà sur « IA externe ». ",
        "activate_off": "Le planificateur est encore sur « IA dans Home Assistant » : appelle d'abord meal_planner_ai.external_setup avec activate: true (ou l'outil meal_planner_setup avec activate: true) pour qu'il attende tes propositions. ",
        "name": "Recherche de recettes du planificateur",
        "chat": "Crée s'il te plaît une tâche planifiée.\nNom : Recherche de recettes du planificateur\nHoraire : {schedule} (fuseau horaire {tz})\nTexte de la tâche :\n{task}",
        "schedule": "{day} à {times}",
        "fallback": "Si rien n'arrive avant {day} {time}, l'IA de Home Assistant planifie (si une est choisie).",
        "task": (
            "Tu recherches les recettes de la semaine pour mon planificateur de repas dans Home Assistant. Personne "
            "ne regarde : ne pose pas de questions.\n"
            "1. Dans Home Assistant, appelle meal_planner_ai.planning_brief avec données de réponse (comme action ou "
            "comme l'outil « meal_planner_planning_brief », selon ce que ta connexion propose).\n"
            "2. Si due vaut false, termine tout de suite sans message.\n"
            "3. Sinon, suis exactement la demande du champ prompt : cherche chaque plat sur le web et n'utilise que "
            "des liens de recettes vus dans tes résultats. Ne devine jamais de liens.\n"
            "4. Appelle meal_planner_ai.submit_proposals avec dishes = liste des plats au format de la demande.\n"
            "5. Lis la réponse : si need est supérieur à 0 ou si des deficits restent ouverts, cherche d'autres plats "
            "adaptés (problems indique pourquoi quelque chose a été refusé) et rappelle submit_proposals. Quatre "
            "appels au maximum ; au dernier, mets final: true.\n"
            "6. Pour finir, réponds avec une courte liste des plats acceptés."
        ),
        "req_ai": "Un abonnement IA avec tâches planifiées et recherche web (p. ex. Claude, ChatGPT ; Gemini non testé)",
        "req_mcp": "Une connexion de cette IA à ton Home Assistant via MCP : l'intégration « Model Context Protocol "
                   "Server » avec l'ensemble d'outils « Meal Planner AI », ou un serveur MCP capable d'appeler des actions",
        "req_remote": "Un accès à distance à Home Assistant (p. ex. Home Assistant Cloud ou Cloudflare), "
                      "car l'IA fonctionne sur internet",
    },
}


def _parse(value: str) -> time:
    hour, minute = (int(x) for x in str(value).split(":")[:2])
    return time(hour, minute)


def setup_info(settings: dict[str, Any], time_zone: str, enabled: bool) -> dict[str, Any]:
    """Zeitplan und Aufgabentext für die geplante Aufgabe der externen KI."""
    lang = settings.get(CONF_REGION) or "de"
    lang = lang if lang in TEXTS else "en"
    text = TEXTS[lang]
    days = DAYS[lang]
    weekday = int(settings[CONF_PLAN_DAY])
    start = datetime.combine(datetime(2026, 1, 5).date() + timedelta(days=weekday), _parse(settings[CONF_PLAN_TIME]))
    runs = [start + timedelta(minutes=m) for m in RUN_OFFSETS]
    fallback = start + timedelta(hours=EXTERNAL_FALLBACK_HOURS)
    groups: dict[int, list[datetime]] = {}
    for run in runs:
        groups.setdefault(run.weekday(), []).append(run)
    schedule = "; ".join(
        text["schedule"].format(day=days[day], times=", ".join(r.strftime("%H:%M") for r in items))
        for day, items in groups.items())
    # ein Cron-Ausdruck geht nur, wenn alle Läufe am selben Tag zur selben Minute liegen
    cron = None
    if len(groups) == 1 and len({r.minute for r in runs}) == 1:
        cron_day = (runs[0].weekday() + 1) % 7  # Cron: 0 = Sonntag
        cron = f"CRON_TZ={time_zone} {runs[0].minute} {','.join(str(r.hour) for r in runs)} * * {cron_day}"
    return {
        "enabled": enabled,
        "language": lang,
        "schedule": schedule,
        "runs": [{"weekday": r.weekday(), "time": r.strftime("%H:%M")} for r in runs],
        "cron": cron,
        "fallback": text["fallback"].format(day=days[fallback.weekday()], time=fallback.strftime("%H:%M")),
        "requirements": [text["req_ai"], text["req_mcp"], text["req_remote"]],
        "task_text": text["task"],
        "steps": [x.format(phrase=text["phrase"]) for x in text["steps"]],
        "phrase": text["phrase"],
        "chat_message": text["chat"].format(schedule=schedule, tz=time_zone, task=text["task"]),
        # Anweisung für eine KI, die diese Aktion/dieses Werkzeug aufruft („Richte meinen Essensplaner ein“)
        "instructions_for_ai": text["ai"].format(
            name=text["name"], schedule=schedule, tz=time_zone, cron=f", Cron: {cron}" if cron else "",
            activate=text["activate_on"] if enabled else text["activate_off"]),
        "task_name": text["name"],
    }
