// meal-planner-card: Kacheln für die Integration "Essensplaner".
// Liest sensor.meal_planner_proposals, sensor.meal_planner_week und todo.meal_planner_wishes,
// schaltet über die Aktionen der Integration. Knöpfe richten sich nach den eingestellten Einkäufen.
const VERSION = "2.4.1";
const DOMAIN = "meal_planner_ai";
console.info("%c MEAL-PLANNER-CARD %c " + VERSION + " ", "background:#6E7F4E;color:#fff", "");

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Oberflächentexte; Sprache = Home-Assistant-Profil (Rückfall: Englisch, dann Deutsch)
const I18N = {
  de: {
    more: "Mehr Vorschläge", more_hint: "Holt 5 weitere Gerichte dazu, Gewähltes bleibt. Einfach auswählen, was passt.", cand: "Zur Auswahl für diese Woche", cand_hint: "kommt erst auf die Einkaufsliste, wenn ihr es wählt", plan_now: "Jetzt Vorschläge planen", plan_now_sure: "Nochmal tippen: jetzt planen", plan_now_hint: "Plant die kommende Woche sofort statt zum eingestellten Termin.", busy: "KI sucht Rezepte, 1 bis 3 Minuten …",
    shop_now: "{trip} jetzt einkaufen", shop_sure: "Nochmal tippen: {trip} kommt jetzt auf die Liste", shop_hint: "Ihr kauft früher ein? Dann kommt der Einkauf sofort auf die Einkaufsliste.",
    tl_plan: "**{n} Vorschläge** kommen als Kacheln. Wünsche bis dahin unten unter **Essenswünsche** eintragen.", tl_deadline: "**Auswahlschluss:** nicht Gewähltes verschwindet, die Woche steht.", tl_release: "**{trip}** kommt auf die Einkaufsliste, später Gewähltes sofort.",
    m_admin: "Geschmacksprofil und Rezepte können nur Administratoren ändern.",
    title: "Essensplan", h_title: "So geht's", h_pick: "**Auswählen:** Pro Gericht einen Einkauf antippen ({trips}), nochmal tippen = abwählen. Gestrichelt = Tipp des Planers.", h_now: "{trip} kommt sofort nach dem Antippen auf die Einkaufsliste.", h_undo: "**Umentschieden?** Auf der Kachel **Doch nicht** drücken, die Zutaten kommen wieder von der Liste.", h_cook: "**Gekocht?** Kreis antippen. **Sterne** sind freiwillig und fließen in die nächsten Vorschläge ein.", sub_now: "sofort", sub_at: "ab {at}",
    x_changed: "Der Zeitplan hat sich geändert: Deine KI ist auf „{old}“ eingerichtet, jetzt gilt „{now}“. Schreib deiner KI noch einmal den Satz aus Schritt 3, damit sie die Aufgabe anpasst.",
    x_copy_phrase: "Satz kopieren", x_manual: "Klappt das nicht? Aufgabe von Hand anlegen", x_manual_hint: "Entweder die komplette Chat-Nachricht einfügen (mit Zeitplan und Text) oder in der KI selbst eine geplante Aufgabe mit dem Zeitplan oben und diesem Text anlegen.",
    x_how: "So legst du die Aufgabe in deiner KI an (Home Assistant kann das nicht selbst)", x_copy_chat: "Chat-Nachricht kopieren", x_copy: "Nur Aufgabentext kopieren",
    x_title: "Externe KI einrichten", x_intro: "Die Vorschläge kommen von einer KI außerhalb von Home Assistant, z. B. einer geplanten Aufgabe in deinem Claude- oder ChatGPT-Abo. Sie holt sich bei jedem Lauf den Auftrag mit deinen aktuellen Einstellungen und liefert die Gerichte zurück; der Essensplaner prüft jedes Gericht.", x_need: "Das brauchst du", x_when: "Wann die Aufgabe laufen soll", x_text: "Text für die geplante Aufgabe", x_copied: "Kopiert ✓",
    tab_plan: "Essensplan", tab_settings: "Einstellungen", prep: "Zubereitung {n} Min", meatless: "vegetarisch",
    lowchol: "cholesterinarm", foreign: "Rezept auf {lang}, in Cookidoo übersetzbar", own: "eigenes Rezept, Zutaten selbst eintragen",
    carried: "aus letzter Woche", recipe: "Rezept ↗", loading: "lädt …", items_hint: "Angehakt = schon da, kommt nicht auf die Liste",
    no_items: "Keine Zutatenliste verfügbar.", ready: "Zutaten schon da", part_n: "{n} schon da", partly: "Teilweise da …",
    not_on_list: "kommt nicht auf die Einkaufsliste", tip: "Tipp", declined: "abgewählt", declined_hint: ", Zutaten kommen von der Liste",
    undo: "Rückgängig", stars: "{n} Sterne", cooked: "gekocht", not_cooked: "noch nicht gekocht", how: "Wie war's?", note: "+ Notiz",
    decline: "Doch nicht", docs: "Ausführliche Anleitung: so funktioniert der Essensplaner", drop: "Entfernen", drop_all: "Übrige Vorschläge entfernen", drop_all_sure: "Nochmal tippen: alle entfernen", removed: "„{title}“ entfernt", note_ph: "z. B. nächstes Mal weniger scharf", save: "Speichern", release: "{trip} kommt {at} auf die Liste",
    proposals: "Vorschläge KW {kw}", proposals_hint: "Pro Gericht einen Einkauf antippen, nochmal tippen = abwählen. Auswahlschluss {at}",
    open: "Offen: ", week: "Diese Woche · {c}/{n} gekocht",
    week_hint: "Kreis antippen = gekocht. Sterne sind freiwillig und fließen in die nächsten Vorschläge ein",
    empty: "Gerade nichts geplant. Die nächsten Vorschläge kommen zum eingestellten Termin.", wishes: "Essenswünsche",
    wishes_hint: "Gericht, Zutat oder Rezeptlink. Fließt in die nächsten Vorschläge ein. „Eigenes Rezept“ = ohne Rezept aus dem Netz",
    wish_ph: "z. B. Lasagne, mal wieder Fisch, was mit Kürbis", add: "Hinzufügen", own_btn: "Eigenes Rezept", own_short: "(eigenes)",
    del_wish: "Wunsch löschen", rating: ["", "nicht nochmal", "eher nicht", "neutral", "gut", "super"],
    days: ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"], loading_settings: "Einstellungen werden geladen …",
    not_setup: "Der Essensplaner ist noch nicht eingerichtet.", settings_hint: "Bereich antippen, ändern, speichern. Gilt sofort für den ganzen Haushalt.",
    ext: "Dieselben Einstellungen findest du auch unter", ext_path: "Einstellungen → Geräte & Dienste → Essensplaner",
    saved: "„{s}“ gespeichert. Der Essensplaner übernimmt die Änderung sofort.", saving: "Speichert …", next: "Weiter",
    cancel: "Abbrechen", back: "Zurück", all_settings: "Alle Einstellungen", no_choice: "Keine Auswahl verfügbar.",
    m_title: "Gemerkt", m_profile: "Geschmacksprofil", m_recipes: "Rezepte",
    m_profile_hint: "Das bekommt die KI bei jeder Planung mit. Sterne ändern oder ✕ entfernt den Eintrag aus dem Profil, das Rezept bleibt gespeichert.",
    m_rules: "Grundregeln und Geschmack", m_rules_hint: "Freitext für alle Planungen, z. B. Vorlieben, Abneigungen, Allergien.",
    m_rules_ph: "z. B. Wir essen gern scharf, keine Pilze, Fisch höchstens einmal pro Woche",
    m_liked: "Gemocht", m_neutral: "Neutral", m_disliked: "Nicht gemocht", m_recent: "In den letzten 4 Wochen gekocht",
    m_recent_hint: "Wird nicht erneut vorgeschlagen. ✕ entfernt den Kochtag.", m_none: "Noch nichts.",
    m_search: "Suchen …", m_sort_name: "Name", m_sort_rating: "Bewertung", m_sort_last: "Zuletzt gekocht", m_sort_times: "Wie oft gekocht",
    m_times: "{n}× gekocht", m_last: "zuletzt {d}", m_never: "noch nie gekocht", m_stub: "nur Bewertung, kein Rezept gespeichert",
    m_del: "Löschen", m_del_sure: "Wirklich löschen?", m_unrate: "Bewertung entfernen", m_note: "Notiz", m_saved: "Gespeichert.",
    m_more: "{n} weitere anzeigen", m_count: "{n} Rezepte",
  },
  en: {
    more: "More suggestions", more_hint: "Adds 5 more dishes, picked ones stay. Just pick what fits.", cand: "To choose for this week", cand_hint: "only goes on the shopping list once you pick it", plan_now: "Plan suggestions now", plan_now_sure: "Tap again: plan now", plan_now_hint: "Plans the coming week right away instead of at the scheduled time.", busy: "AI is searching recipes, 1 to 3 minutes …",
    shop_now: "Shop {trip} now", shop_sure: "Tap again: {trip} goes on the list now", shop_hint: "Shopping earlier? Then this trip goes on the shopping list right away.",
    tl_plan: "**{n} suggestions** arrive as tiles. Add wishes below under **Meal wishes** before then.", tl_deadline: "**Selection closes:** unpicked suggestions disappear, the week is set.", tl_release: "**{trip}** goes on the shopping list, later picks right away.",
    m_admin: "Only administrators can change the taste profile and recipes.",
    title: "Meal plan", h_title: "How it works", h_pick: "**Choose:** tap a shopping trip per dish ({trips}), tap again to deselect. Dashed = the planner's tip.", h_now: "{trip} goes on the shopping list as soon as you tap.", h_undo: "**Changed your mind?** Press **Not after all** on the tile, the ingredients come off the list.", h_cook: "**Cooked?** Tap the circle. **Stars** are optional and shape the next suggestions.", sub_now: "right away", sub_at: "from {at}",
    x_changed: "The schedule has changed: your AI is set up for “{old}”, now it is “{now}”. Send your AI the sentence from step 3 again so it updates the task.",
    x_copy_phrase: "Copy sentence", x_manual: "Doesn't work? Create the task by hand", x_manual_hint: "Either paste the full chat message (with schedule and text) or create a scheduled task in the AI yourself with the schedule above and this text.",
    x_how: "How to create the task in your AI (Home Assistant can't do it for you)", x_copy_chat: "Copy chat message", x_copy: "Copy task text only",
    x_title: "Set up external AI", x_intro: "Proposals come from an AI outside Home Assistant, e.g. a scheduled task in your Claude or ChatGPT subscription. On every run it fetches the brief with your current settings and hands the dishes back; the meal planner checks every dish.", x_need: "What you need", x_when: "When the task should run", x_text: "Text for the scheduled task", x_copied: "Copied ✓",
    tab_plan: "Meal plan", tab_settings: "Settings", prep: "Ready in {n} min", meatless: "vegetarian",
    lowchol: "low cholesterol", foreign: "Recipe in {lang}, translatable in Cookidoo", own: "own recipe, add ingredients yourself",
    carried: "from last week", recipe: "Recipe ↗", loading: "loading …", items_hint: "Ticked = already at home, not added to the list",
    no_items: "No ingredient list available.", ready: "Have everything", part_n: "{n} at home", partly: "Partly at home …",
    not_on_list: "not added to the shopping list", tip: "Tip", declined: "removed", declined_hint: ", ingredients come off the list",
    undo: "Undo", stars: "{n} stars", cooked: "cooked", not_cooked: "not cooked yet", how: "How was it?", note: "+ Note",
    decline: "Not after all", docs: "Detailed guide: how the meal planner works", drop: "Remove", drop_all: "Remove remaining suggestions", drop_all_sure: "Tap again: remove all", removed: "“{title}” removed", note_ph: "e.g. less spicy next time", save: "Save", release: "{trip} goes on the list {at}",
    proposals: "Proposals week {kw}", proposals_hint: "Tap a shopping trip per dish, tap again to remove. Choice closes {at}",
    open: "Open: ", week: "This week · {c}/{n} cooked",
    week_hint: "Tap the circle = cooked. Stars are optional and shape the next proposals",
    empty: "Nothing planned right now. The next proposals arrive at the scheduled time.", wishes: "Meal wishes",
    wishes_hint: "Dish, ingredient or recipe link. Goes into the next proposals. “Own recipe” = no recipe from the web",
    wish_ph: "e.g. lasagne, fish again, something with pumpkin", add: "Add", own_btn: "Own recipe", own_short: "(own)",
    del_wish: "Delete wish", rating: ["", "never again", "rather not", "neutral", "good", "great"],
    days: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], loading_settings: "Loading settings …",
    not_setup: "The meal planner is not set up yet.", settings_hint: "Tap a section, change, save. Applies to the whole household right away.",
    ext: "The same settings are also under", ext_path: "Settings → Devices & services → Essensplaner",
    saved: "“{s}” saved. The meal planner applies the change right away.", saving: "Saving …", next: "Next",
    cancel: "Cancel", back: "Back", all_settings: "All settings", no_choice: "Nothing to choose.",
    m_title: "Remembered", m_profile: "Taste profile", m_recipes: "Recipes",
    m_profile_hint: "The AI gets this with every planning run. Change the stars or ✕ to remove the entry from the profile; the recipe stays stored.",
    m_rules: "Basic rules and taste", m_rules_hint: "Free text for all planning runs, e.g. likes, dislikes, allergies.",
    m_rules_ph: "e.g. We like it spicy, no mushrooms, fish at most once a week",
    m_liked: "Liked", m_neutral: "Neutral", m_disliked: "Disliked", m_recent: "Cooked in the last 4 weeks",
    m_recent_hint: "Won't be proposed again. ✕ removes the cooked day.", m_none: "Nothing yet.",
    m_search: "Search …", m_sort_name: "Name", m_sort_rating: "Rating", m_sort_last: "Last cooked", m_sort_times: "Times cooked",
    m_times: "cooked {n}×", m_last: "last {d}", m_never: "never cooked", m_stub: "rating only, no recipe stored",
    m_del: "Delete", m_del_sure: "Really delete?", m_unrate: "Remove rating", m_note: "Note", m_saved: "Saved.",
    m_more: "Show {n} more", m_count: "{n} recipes",
  },
  es: {
    more: "Más propuestas", more_hint: "Añade 5 platos más, lo elegido se queda. Elegid lo que encaje.", cand: "Para elegir esta semana", cand_hint: "solo va a la lista al elegirlo", plan_now: "Planificar ahora", plan_now_sure: "Toca otra vez: planificar ahora", plan_now_hint: "Planifica la próxima semana ya, en lugar de a la hora fijada.", busy: "La IA busca recetas, de 1 a 3 minutos …",
    shop_now: "Comprar {trip} ahora", shop_sure: "Toca otra vez: {trip} pasa ahora a la lista", shop_hint: "¿Compráis antes? Entonces esta compra pasa ya a la lista.",
    tl_plan: "Llegan **{n} propuestas** como tarjetas. Antes, añade deseos abajo en **Deseos de comida**.", tl_deadline: "**Cierre de la elección:** lo no elegido desaparece, la semana queda fijada.", tl_release: "**{trip}** pasa a la lista de la compra, lo elegido después al momento.",
    m_admin: "Solo los administradores pueden cambiar el perfil de gustos y las recetas.",
    title: "Menú", h_title: "Cómo funciona", h_pick: "**Elegir:** toca una compra por plato ({trips}), otra vez = quitar. Discontinuo = consejo del planificador.", h_now: "{trip} pasa a la lista de la compra al tocarlo.", h_undo: "**¿Cambio de idea?** Pulsa **Mejor no** en la tarjeta, los ingredientes salen de la lista.", h_cook: "**¿Cocinado?** Toca el círculo. Las **estrellas** son opcionales y orientan las próximas propuestas.", sub_now: "al momento", sub_at: "desde {at}",
    x_changed: "El horario ha cambiado: tu IA está configurada para «{old}», ahora es «{now}». Envía de nuevo a tu IA la frase del paso 3 para que actualice la tarea.",
    x_copy_phrase: "Copiar frase", x_manual: "¿No funciona? Crear la tarea a mano", x_manual_hint: "Pega el mensaje completo (con horario y texto) o crea tú mismo en la IA una tarea programada con el horario de arriba y este texto.",
    x_how: "Cómo crear la tarea en tu IA (Home Assistant no puede hacerlo por ti)", x_copy_chat: "Copiar mensaje para el chat", x_copy: "Copiar solo el texto de la tarea",
    m_title: "Guardado", m_profile: "Perfil de gustos", m_recipes: "Recetas",
    m_profile_hint: "Esto recibe la IA en cada planificación. Cambia las estrellas o ✕ quita la entrada del perfil; la receta se queda guardada.",
    m_rules: "Reglas básicas y gustos", m_rules_hint: "Texto libre para todas las planificaciones, p. ej. preferencias, rechazos, alergias.",
    m_rules_ph: "p. ej. Nos gusta el picante, sin setas, pescado como mucho una vez por semana",
    m_liked: "Gustó", m_neutral: "Neutral", m_disliked: "No gustó", m_recent: "Cocinado en las últimas 4 semanas",
    m_recent_hint: "No se volverá a proponer. ✕ quita el día cocinado.", m_none: "Nada todavía.",
    m_search: "Buscar …", m_sort_name: "Nombre", m_sort_rating: "Valoración", m_sort_last: "Cocinado por última vez", m_sort_times: "Veces cocinado",
    m_times: "cocinado {n}×", m_last: "última vez {d}", m_never: "nunca cocinado", m_stub: "solo valoración, sin receta guardada",
    m_del: "Borrar", m_del_sure: "¿Seguro que borrar?", m_unrate: "Quitar valoración", m_note: "Nota", m_saved: "Guardado.",
    m_more: "Mostrar {n} más", m_count: "{n} recetas",
    x_title: "Configurar IA externa", x_intro: "Las propuestas vienen de una IA fuera de Home Assistant, p. ej. una tarea programada en tu suscripción de Claude o ChatGPT. En cada ejecución recoge el encargo con tus ajustes actuales y devuelve los platos; el planificador comprueba cada plato.", x_need: "Lo que necesitas", x_when: "Cuándo debe ejecutarse la tarea", x_text: "Texto para la tarea programada", x_copied: "Copiado ✓",
    tab_plan: "Menú", tab_settings: "Ajustes", prep: "Listo en {n} min", meatless: "vegetariano",
    lowchol: "bajo en colesterol", foreign: "Receta en {lang}, traducible en Cookidoo", own: "receta propia, añade los ingredientes tú",
    carried: "de la semana pasada", recipe: "Receta ↗", loading: "cargando …", items_hint: "Marcado = ya en casa, no va a la lista",
    no_items: "No hay lista de ingredientes.", ready: "Lo tengo todo", part_n: "{n} en casa", partly: "Parte en casa …",
    not_on_list: "no va a la lista de la compra", tip: "Consejo", declined: "descartado", declined_hint: ", los ingredientes salen de la lista",
    undo: "Deshacer", stars: "{n} estrellas", cooked: "cocinado", not_cooked: "aún sin cocinar", how: "¿Qué tal?", note: "+ Nota",
    decline: "Mejor no", docs: "Guía detallada (en inglés): cómo funciona el planificador", drop: "Quitar", drop_all: "Quitar las demás propuestas", drop_all_sure: "Toca otra vez: quitar todas", removed: "«{title}» quitado", note_ph: "p. ej. la próxima vez menos picante", save: "Guardar", release: "{trip} pasa a la lista {at}",
    proposals: "Propuestas semana {kw}", proposals_hint: "Toca una compra por plato, otra vez para quitar. Cierre {at}",
    open: "Pendiente: ", week: "Esta semana · {c}/{n} cocinados",
    week_hint: "Toca el círculo = cocinado. Las estrellas son opcionales e influyen en las próximas propuestas",
    empty: "Nada planificado. Las próximas propuestas llegan a la hora fijada.", wishes: "Deseos",
    wishes_hint: "Plato, ingrediente o enlace. Entra en las próximas propuestas. «Receta propia» = sin receta de la web",
    wish_ph: "p. ej. lasaña, otra vez pescado, algo con calabaza", add: "Añadir", own_btn: "Receta propia", own_short: "(propia)",
    del_wish: "Borrar deseo", rating: ["", "nunca más", "mejor no", "neutral", "bueno", "genial"],
    days: ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"], loading_settings: "Cargando ajustes …",
    not_setup: "El planificador aún no está configurado.", settings_hint: "Toca una sección, cambia, guarda. Vale enseguida para toda la casa.",
    ext: "Los mismos ajustes están en", ext_path: "Ajustes → Dispositivos y servicios → Essensplaner",
    saved: "«{s}» guardado. El planificador aplica el cambio enseguida.", saving: "Guardando …", next: "Siguiente",
    cancel: "Cancelar", back: "Atrás", all_settings: "Todos los ajustes", no_choice: "Nada que elegir.",
  },
  pt: {
    more: "Mais sugestões", more_hint: "Acrescenta mais 5 pratos, o escolhido fica. Escolham o que servir.", cand: "Para escolher esta semana", cand_hint: "só vai para a lista quando o escolherem", plan_now: "Planear agora", plan_now_sure: "Toca outra vez: planear agora", plan_now_hint: "Planeia a próxima semana já, em vez de à hora definida.", busy: "A IA procura receitas, 1 a 3 minutos …",
    shop_now: "Comprar {trip} agora", shop_sure: "Toca outra vez: {trip} vai agora para a lista", shop_hint: "Vão às compras mais cedo? Então esta compra vai já para a lista.",
    tl_plan: "Chegam **{n} sugestões** como cartões. Antes disso, adiciona desejos abaixo em **Desejos de refeição**.", tl_deadline: "**Fecho da escolha:** o que não foi escolhido desaparece, a semana fica definida.", tl_release: "**{trip}** vai para a lista de compras, escolhas posteriores de imediato.",
    m_admin: "Só os administradores podem alterar o perfil de gostos e as receitas.",
    title: "Ementa", h_title: "Como funciona", h_pick: "**Escolher:** toca numa compra por prato ({trips}), de novo = retirar. Tracejado = dica do planeador.", h_now: "{trip} vai para a lista de compras ao tocar.", h_undo: "**Mudaste de ideias?** Carrega em **Afinal não** no cartão, os ingredientes saem da lista.", h_cook: "**Cozinhado?** Toca no círculo. As **estrelas** são opcionais e orientam as próximas sugestões.", sub_now: "já", sub_at: "a partir de {at}",
    x_changed: "O horário mudou: a tua IA está configurada para «{old}», agora é «{now}». Envia de novo à tua IA a frase do passo 3 para atualizar a tarefa.",
    x_copy_phrase: "Copiar frase", x_manual: "Não funciona? Criar a tarefa à mão", x_manual_hint: "Cola a mensagem completa (com horário e texto) ou cria tu mesmo na IA uma tarefa agendada com o horário acima e este texto.",
    x_how: "Como criar a tarefa na tua IA (o Home Assistant não o faz por ti)", x_copy_chat: "Copiar mensagem para o chat", x_copy: "Copiar só o texto da tarefa",
    m_title: "Guardado", m_profile: "Perfil de gosto", m_recipes: "Receitas",
    m_profile_hint: "É isto que a IA recebe em cada planeamento. Muda as estrelas ou ✕ remove a entrada do perfil; a receita continua guardada.",
    m_rules: "Regras básicas e gosto", m_rules_hint: "Texto livre para todos os planeamentos, p. ex. preferências, rejeições, alergias.",
    m_rules_ph: "p. ex. Gostamos de picante, sem cogumelos, peixe no máximo uma vez por semana",
    m_liked: "Gostámos", m_neutral: "Neutro", m_disliked: "Não gostámos", m_recent: "Cozinhado nas últimas 4 semanas",
    m_recent_hint: "Não volta a ser proposto. ✕ remove o dia cozinhado.", m_none: "Ainda nada.",
    m_search: "Pesquisar …", m_sort_name: "Nome", m_sort_rating: "Avaliação", m_sort_last: "Última vez cozinhado", m_sort_times: "Vezes cozinhado",
    m_times: "cozinhado {n}×", m_last: "última vez {d}", m_never: "nunca cozinhado", m_stub: "só avaliação, sem receita guardada",
    m_del: "Apagar", m_del_sure: "Apagar mesmo?", m_unrate: "Remover avaliação", m_note: "Nota", m_saved: "Guardado.",
    m_more: "Mostrar mais {n}", m_count: "{n} receitas",
    x_title: "Configurar IA externa", x_intro: "As propostas vêm de uma IA fora do Home Assistant, p. ex. uma tarefa agendada na tua subscrição Claude ou ChatGPT. Em cada execução vai buscar o pedido com as tuas definições atuais e devolve os pratos; o planeador verifica cada prato.", x_need: "O que precisas", x_when: "Quando a tarefa deve correr", x_text: "Texto para a tarefa agendada", x_copied: "Copiado ✓",
    tab_plan: "Ementa", tab_settings: "Definições", prep: "Pronto em {n} min", meatless: "vegetariano",
    lowchol: "baixo colesterol", foreign: "Receita em {lang}, traduzível no Cookidoo", own: "receita própria, adiciona os ingredientes",
    carried: "da semana passada", recipe: "Receita ↗", loading: "a carregar …", items_hint: "Marcado = já em casa, não vai para a lista",
    no_items: "Sem lista de ingredientes.", ready: "Tenho tudo", part_n: "{n} em casa", partly: "Parte em casa …",
    not_on_list: "não vai para a lista de compras", tip: "Dica", declined: "removido", declined_hint: ", os ingredientes saem da lista",
    undo: "Desfazer", stars: "{n} estrelas", cooked: "cozinhado", not_cooked: "ainda não cozinhado", how: "Que tal?", note: "+ Nota",
    decline: "Afinal não", docs: "Guia detalhado (em inglês): como funciona o planeador", drop: "Remover", drop_all: "Remover as restantes sugestões", drop_all_sure: "Toca outra vez: remover todas", removed: "«{title}» removido", note_ph: "p. ex. menos picante da próxima vez", save: "Guardar", release: "{trip} vai para a lista {at}",
    proposals: "Propostas semana {kw}", proposals_hint: "Toca numa compra por prato, de novo para retirar. Fecho {at}",
    open: "Em falta: ", week: "Esta semana · {c}/{n} cozinhados",
    week_hint: "Toca no círculo = cozinhado. As estrelas são opcionais e contam para as próximas propostas",
    empty: "Nada planeado. As próximas propostas chegam à hora definida.", wishes: "Desejos",
    wishes_hint: "Prato, ingrediente ou link. Entra nas próximas propostas. «Receita própria» = sem receita da web",
    wish_ph: "p. ex. lasanha, peixe outra vez, algo com abóbora", add: "Adicionar", own_btn: "Receita própria", own_short: "(própria)",
    del_wish: "Apagar desejo", rating: ["", "nunca mais", "melhor não", "neutro", "bom", "ótimo"],
    days: ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"], loading_settings: "A carregar definições …",
    not_setup: "O planeador ainda não está configurado.", settings_hint: "Toca numa secção, altera, guarda. Vale logo para toda a casa.",
    ext: "As mesmas definições estão em", ext_path: "Definições → Dispositivos e serviços → Essensplaner",
    saved: "«{s}» guardado. O planeador aplica a alteração de imediato.", saving: "A guardar …", next: "Seguinte",
    cancel: "Cancelar", back: "Voltar", all_settings: "Todas as definições", no_choice: "Nada para escolher.",
  },
  fr: {
    more: "Plus de propositions", more_hint: "Ajoute 5 plats de plus, les choix restent. Prenez ce qui convient.", cand: "À choisir cette semaine", cand_hint: "ne va sur la liste qu’une fois choisi", plan_now: "Planifier maintenant", plan_now_sure: "Touchez encore : planifier maintenant", plan_now_hint: "Planifie la semaine prochaine tout de suite au lieu de l'heure prévue.", busy: "L'IA cherche des recettes, 1 à 3 minutes …",
    shop_now: "Faire {trip} maintenant", shop_sure: "Touchez encore : {trip} va sur la liste maintenant", shop_hint: "Vous faites les courses plus tôt ? Cette course va tout de suite sur la liste.",
    tl_plan: "**{n} propositions** arrivent en tuiles. Ajoutez vos envies avant, ci-dessous sous **Envies de repas**.", tl_deadline: "**Clôture du choix :** ce qui n'est pas choisi disparaît, la semaine est fixée.", tl_release: "**{trip}** va sur la liste de courses, les choix suivants tout de suite.",
    m_admin: "Seuls les administrateurs peuvent modifier le profil de goûts et les recettes.",
    title: "Menu", h_title: "Mode d'emploi", h_pick: "**Choisir :** touchez une course par plat ({trips}), à nouveau = retirer. Pointillés = conseil du planificateur.", h_now: "{trip} va sur la liste de courses dès que vous touchez.", h_undo: "**Changé d'avis ?** Appuyez sur **Finalement non** sur la tuile, les ingrédients quittent la liste.", h_cook: "**Cuisiné ?** Touchez le cercle. Les **étoiles** sont facultatives et guident les prochaines propositions.", sub_now: "tout de suite", sub_at: "dès {at}",
    x_changed: "L'horaire a changé : ton IA est configurée pour « {old} », maintenant c'est « {now} ». Renvoie à ton IA la phrase de l'étape 3 pour qu'elle mette la tâche à jour.",
    x_copy_phrase: "Copier la phrase", x_manual: "Ça ne marche pas ? Créer la tâche à la main", x_manual_hint: "Colle le message complet (avec horaire et texte) ou crée toi-même dans l'IA une tâche planifiée avec l'horaire ci-dessus et ce texte.",
    x_how: "Créer la tâche dans ton IA (Home Assistant ne peut pas le faire à ta place)", x_copy_chat: "Copier le message", x_copy: "Copier seulement le texte de la tâche",
    m_title: "Mémorisé", m_profile: "Profil de goût", m_recipes: "Recettes",
    m_profile_hint: "C'est ce que l'IA reçoit à chaque planification. Change les étoiles ou ✕ retire l'entrée du profil ; la recette reste enregistrée.",
    m_rules: "Règles de base et goûts", m_rules_hint: "Texte libre pour toutes les planifications, p. ex. préférences, aversions, allergies.",
    m_rules_ph: "p. ex. On aime épicé, pas de champignons, poisson au plus une fois par semaine",
    m_liked: "Aimé", m_neutral: "Neutre", m_disliked: "Pas aimé", m_recent: "Cuisiné ces 4 dernières semaines",
    m_recent_hint: "Ne sera pas reproposé. ✕ retire le jour cuisiné.", m_none: "Rien pour l'instant.",
    m_search: "Rechercher …", m_sort_name: "Nom", m_sort_rating: "Note", m_sort_last: "Dernière fois cuisiné", m_sort_times: "Fois cuisiné",
    m_times: "cuisiné {n}×", m_last: "dernière fois {d}", m_never: "jamais cuisiné", m_stub: "note seulement, aucune recette enregistrée",
    m_del: "Supprimer", m_del_sure: "Vraiment supprimer ?", m_unrate: "Retirer la note", m_note: "Note", m_saved: "Enregistré.",
    m_more: "Afficher {n} de plus", m_count: "{n} recettes",
    x_title: "Configurer une IA externe", x_intro: "Les propositions viennent d'une IA hors de Home Assistant, p. ex. une tâche planifiée dans ton abonnement Claude ou ChatGPT. À chaque exécution, elle récupère la demande avec tes réglages actuels et renvoie les plats ; le planificateur vérifie chaque plat.", x_need: "Ce qu'il te faut", x_when: "Quand la tâche doit s'exécuter", x_text: "Texte de la tâche planifiée", x_copied: "Copié ✓",
    tab_plan: "Menu", tab_settings: "Réglages", prep: "Prêt en {n} min", meatless: "végétarien",
    lowchol: "pauvre en cholestérol", foreign: "Recette en {lang}, traduisible dans Cookidoo", own: "recette perso, ajoute les ingrédients toi-même",
    carried: "de la semaine dernière", recipe: "Recette ↗", loading: "chargement …", items_hint: "Coché = déjà à la maison, pas sur la liste",
    no_items: "Pas de liste d'ingrédients.", ready: "J'ai tout", part_n: "{n} à la maison", partly: "En partie …",
    not_on_list: "ne va pas sur la liste de courses", tip: "Conseil", declined: "retiré", declined_hint: ", les ingrédients sortent de la liste",
    undo: "Annuler", stars: "{n} étoiles", cooked: "cuisiné", not_cooked: "pas encore cuisiné", how: "C'était comment ?", note: "+ Note",
    decline: "Finalement non", docs: "Guide détaillé (en anglais) : comment fonctionne le planificateur", drop: "Retirer", drop_all: "Retirer les autres propositions", drop_all_sure: "Touchez encore : tout retirer", removed: "« {title} » retiré", note_ph: "p. ex. moins épicé la prochaine fois", save: "Enregistrer", release: "{trip} va sur la liste {at}",
    proposals: "Propositions semaine {kw}", proposals_hint: "Touche une course par plat, encore une fois pour retirer. Clôture {at}",
    open: "Manquant : ", week: "Cette semaine · {c}/{n} cuisinés",
    week_hint: "Touche le cercle = cuisiné. Les étoiles sont facultatives et guident les prochaines propositions",
    empty: "Rien de prévu. Les prochaines propositions arrivent à l'heure réglée.", wishes: "Envies",
    wishes_hint: "Plat, ingrédient ou lien. Entre dans les prochaines propositions. « Recette perso » = sans recette du web",
    wish_ph: "p. ex. lasagnes, du poisson, quelque chose au potiron", add: "Ajouter", own_btn: "Recette perso", own_short: "(perso)",
    del_wish: "Supprimer l'envie", rating: ["", "plus jamais", "plutôt pas", "neutre", "bon", "super"],
    days: ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"], loading_settings: "Chargement des réglages …",
    not_setup: "Le planificateur n'est pas encore configuré.", settings_hint: "Touche une section, modifie, enregistre. Valable tout de suite pour toute la maison.",
    ext: "Les mêmes réglages se trouvent sous", ext_path: "Paramètres → Appareils et services → Essensplaner",
    saved: "« {s} » enregistré. Le planificateur applique la modification tout de suite.", saving: "Enregistrement …", next: "Suivant",
    cancel: "Annuler", back: "Retour", all_settings: "Tous les réglages", no_choice: "Rien à choisir.",
  },
};
let LANG = "de";
const t = (key, vars) => {
  const pack = I18N[LANG] || I18N.en;
  let text = pack[key] ?? I18N.en[key] ?? I18N.de[key] ?? key;
  for (const [k, v] of Object.entries(vars || {})) text = text.split(`{${k}}`).join(v);
  return text;
};
const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? String(u) : "");
const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");
const FLOW = "config/config_entries/options/flow";
const errText = (e) => String((e && ((e.body && e.body.message) || e.message || e.error)) || e);
const fmt = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return `${t("days")[d.getDay()]} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};
const DEFAULTS = {
  proposals: "sensor.meal_planner_proposals",
  week: "sensor.meal_planner_week",
  wishes: "todo.meal_planner_wishes",
  preset: "system",
};
// Farben: Standard = aktuelles HA-Design. "warm" = Essensplan-Stil. Einzelne Farben per Karteneinstellung
// überschreibbar (accent, accent_text, tile, tile_selected, text, muted, chip, star, background, border).
const PRESETS = {
  warm: {
    background: "#E9E1D3", tile: "#F6F0E6", tile_selected: "#EEF0E2", tile_done: "#F1EEE2", text: "#2E2A25",
    muted: "#6B6156", chip: "#E6DCCB", chip_text: "#5A4E3F", accent: "#6E7F4E", accent_text: "#F1F4E8",
    star: "#D99A2B", star_off: "#D8CCB8", input: "#FFFDF8", border: "#D8CCB8", tile_border: "transparent",
    radius: "20px", header: "#6E7F4E", header_text: "#F1F4E8",
    heading: "#4A4239", check_border: "#8A7F72", note: "#45512F", tile_border_width: "2px", shadow: "none", page_padding: "8px 16px 16px",
  },
};
const VARS = ["background", "tile", "tile_selected", "tile_done", "text", "muted", "chip", "chip_text", "accent",
  "accent_text", "star", "star_off", "input", "border", "tile_border", "radius", "header", "header_text",
  "heading", "check_border", "note", "tile_border_width", "shadow", "page_padding"];
const themeCss = (config) => {
  const values = { ...(PRESETS[config.preset] || {}) };
  for (const key of VARS) if (config[key]) values[key] = config[key];
  const css = Object.entries(values).filter(([k]) => VARS.includes(k)).map(([k, v]) => `--ep-${k.replace(/_/g, "-")}:${String(v).replace(/[;{}<>]/g, "")}`).join(";");
  return css ? `:host{${css}}` : "";
};

// Bewertung: 10 Sterne (bis 0.40 waren es 5; die Texte in I18N.rating gelten je zwei Sterne)
const STAR_MAX = 10;
const STARS = Array.from({ length: STAR_MAX }, (_, i) => i + 1);
const DOCS_URL = "https://github.com/Pare51984/ha-meal-planner-ai/blob/main/docs/";
const MEM_TABS = ["profile", "recipes"];
const cardCss = (config) => `
      :host{display:block;
        --_tile:var(--ep-tile,var(--ha-card-background,var(--card-background-color,#fff)));
        --_text:var(--ep-text,var(--primary-text-color,#212121));
        --_muted:var(--ep-muted,var(--secondary-text-color,#727272));
        --_accent:var(--ep-accent,var(--primary-color,#03a9f4));
        --_accent-text:var(--ep-accent-text,var(--text-primary-color,#fff));
        --_chip:var(--ep-chip,var(--secondary-background-color,#e5e5e5));
        --_chip-text:var(--ep-chip-text,var(--primary-text-color,#212121));
        --_sel:var(--ep-tile-selected,color-mix(in srgb,var(--_accent) 12%,var(--_tile)));
        --_done:var(--ep-tile-done,color-mix(in srgb,var(--_muted) 8%,var(--_tile)));
        --_star:var(--ep-star,var(--warning-color,#ffa600));
        --_star-off:var(--ep-star-off,var(--disabled-text-color,#bdbdbd));
        --_input:var(--ep-input,var(--input-fill-color,var(--secondary-background-color,#fff)));
        --_border:var(--ep-border,var(--divider-color,rgba(0,0,0,.12)));
        --_tile-border:var(--ep-tile-border,var(--ha-card-border-color,var(--divider-color,#e0e0e0)));
        --_radius:var(--ep-radius,var(--ha-card-border-radius,12px));
        --_error:var(--error-color,#db4437);
        --_heading:var(--ep-heading,var(--_text));
        --_check:var(--ep-check-border,var(--_muted));
        --_note:var(--ep-note,var(--_accent));
        --_bw:var(--ep-tile-border-width,var(--ha-card-border-width,1px));
        --_shadow:var(--ep-shadow,var(--ha-card-box-shadow,none));
        background:var(--ep-background,transparent);color:var(--_text)}
      :host([fill]){min-height:calc(100vh - var(--header-height,56px));box-sizing:border-box;padding:var(--ep-page-padding,8px 12px 16px)}
      .titel{display:flex;align-items:center;gap:6px;color:var(--_heading);font-size:15px;font-weight:500;padding:6px 4px 10px}
      .titel ha-icon{--mdc-icon-size:18px;color:var(--_heading)}
      .layout{container-type:inline-size}
      .cols{display:block}
      .help{background:var(--_tile);color:var(--_text);border-radius:var(--_radius);padding:14px 16px;font-size:14px;line-height:1.5;margin-bottom:12px}
      .help p{margin:0 0 10px}
      .help p:last-child{margin:0}
      .tl{margin:0 0 12px;border-left:2px solid var(--_accent);padding-left:10px}
      .tlr{display:grid;grid-template-columns:72px 1fr;gap:6px;margin-bottom:8px}
      .tlr b{white-space:nowrap}
      @container (min-width:900px){.cols{display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:16px;align-items:start}}
      .sec{font-size:13px;font-weight:600;color:var(--_heading);margin:6px 4px 8px}
      .sec span{display:block;font-weight:400;font-size:12px;color:var(--_muted);margin-top:2px}
      .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px;margin-bottom:12px}
      .tile{background:var(--_tile);color:var(--_text);border-radius:var(--_radius);padding:10px 12px;border:var(--_bw) solid var(--_tile-border);box-shadow:var(--_shadow)}
      .tile.sel{border-color:var(--_accent);border-width:2px;background:var(--_sel)}
      .tile.rated{background:var(--_done)}
      .tile.undo{opacity:.75}
      .tile.undo .name{text-decoration:line-through}
      .head{display:flex;gap:10px;align-items:flex-start}
      .ico{flex:0 0 34px;height:34px;border-radius:50%;background:var(--_chip);color:var(--_chip-text);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:600}
      .tile.sel .ico{background:var(--_accent);color:var(--_accent-text)}
      .ck{flex:0 0 34px;height:34px;border-radius:50%;border:2px solid var(--_check);background:transparent;color:var(--_accent-text);font:inherit;font-size:16px;font-weight:700;cursor:pointer;padding:0}
      .ck.on{background:var(--_accent);border-color:var(--_accent)}
      .ckw{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:2px}
      .ckw .ck{flex:none;width:34px}
      .ckl{font-size:10px;line-height:1;color:var(--_muted)}
      .txt{flex:1;min-width:0}
      .name{font-size:14px;font-weight:600;line-height:1.25}
      .l1{font-size:12px;color:var(--_heading);margin-top:3px;line-height:1.35}
      .l1:empty{display:none}
      .l2{font-size:12px;color:var(--_muted);line-height:1.35}
      .rate{font-size:12px;color:var(--_note);margin-top:4px;font-style:italic}
      .opts{display:grid;gap:6px;margin-top:10px}
      .opt{font:inherit;border:none;cursor:pointer;border-radius:calc(var(--_radius) * .7);background:var(--_chip);color:var(--_chip-text);font-size:13px;font-weight:600;padding:7px 4px;display:flex;flex-direction:column;align-items:center;line-height:1.2}
      .opt small{font-weight:400;font-size:10px;opacity:.85}
      .opt.tip{outline:1px dashed var(--_muted)}
      .opt.on{background:var(--_accent);color:var(--_accent-text)}
      .lnk{font-size:12px;color:var(--_chip-text);background:var(--_chip);border-radius:calc(var(--_radius) * .7);padding:7px 12px;font-weight:600;text-decoration:none;white-space:nowrap;display:flex;align-items:center;justify-content:center}
      .foot{display:flex;align-items:center;margin-top:8px;gap:8px;flex-wrap:wrap}
      .stars{display:flex;gap:2px}
      .star{font:inherit;border:none;background:none;cursor:pointer;font-size:22px;line-height:1;padding:2px 1px;color:var(--_star-off)}
      .star.on{color:var(--_star)}
      .hint{flex:1;font-size:12px;color:var(--_muted)}
      .small{font:inherit;border:none;cursor:pointer;border-radius:calc(var(--_radius) * .6);background:var(--_chip);color:var(--_chip-text);font-size:12px;padding:5px 10px}
      .small.on{background:var(--_accent);color:var(--_accent-text)}
      .rbox{display:flex;gap:6px;margin-top:8px}
      .darow{display:flex;align-items:center;gap:8px;margin-top:8px}
      .darow.shop{flex-wrap:wrap;margin:-4px 4px 14px}
      .darow.pick{margin:-4px 4px 14px}
      .undobar{position:sticky;bottom:12px;z-index:2;display:flex;align-items:center;gap:12px;justify-content:space-between;margin:0 4px 14px;padding:10px 14px;border-radius:12px;background:var(--_text);color:var(--_tile);box-shadow:0 4px 14px rgba(0,0,0,.18);font-size:14px}
      .rbox input,.wish input{flex:1;min-width:0;font:inherit;font-size:13px;border:1px solid var(--_border);border-radius:calc(var(--_radius) * .6);padding:7px 10px;background:var(--_input);color:var(--_text)}
      .wish{display:flex;gap:6px;margin:0 0 8px}
      .items{display:flex;flex-direction:column;gap:4px;margin-top:8px;padding:8px 10px;border-radius:calc(var(--_radius) * .6);background:var(--_chip)}
      .item{font-size:13px;color:var(--_chip-text);display:flex;align-items:center;gap:6px}
      .item small{color:var(--_muted)}
      .chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
      .chip{display:inline-flex;align-items:center;gap:4px;background:var(--_tile);color:var(--_text);border:1px solid var(--_tile-border);border-radius:14px;padding:4px 4px 4px 12px;font-size:13px}
      .chip button{font:inherit;border:none;background:var(--_chip);color:var(--_chip-text);border-radius:50%;width:22px;height:22px;font-size:11px;cursor:pointer;padding:0}
      .empty{margin-bottom:12px;background:var(--_tile);color:var(--_muted);border-radius:var(--_radius);padding:14px;font-size:13px}
      .empty.err{color:var(--_error)}
      .tabs{display:flex;flex-wrap:wrap;gap:6px;margin:0 4px 10px}
      .back{font:inherit;border:none;background:none;cursor:pointer;color:var(--_accent);font-size:13px;font-weight:600;padding:4px 4px 8px}
      .tab{font:inherit;border:none;cursor:pointer;border-radius:calc(var(--_radius) * .6);background:var(--_chip);color:var(--_chip-text);font-size:13px;font-weight:600;padding:6px 14px}
      .tab.on{background:var(--_accent);color:var(--_accent-text)}
      .menu{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;margin-bottom:12px}
      .mbtn{font:inherit;text-align:left;border:var(--ha-card-border-width,1px) solid var(--_tile-border);cursor:pointer;background:var(--_tile);color:var(--_text);border-radius:var(--_radius);padding:12px 14px;font-size:14px;font-weight:600}
      .mbtn small{display:block;font-weight:400;font-size:12px;color:var(--_muted);margin-top:2px}
      .form{background:var(--_tile);color:var(--_text);border-radius:var(--_radius);padding:12px 14px;border:var(--ha-card-border-width,1px) solid var(--_tile-border);margin-bottom:12px;max-width:760px}
      .form h3{margin:0 0 4px;font-size:15px}
      .desc{font-size:12px;color:var(--_muted);margin-bottom:10px;line-height:1.4}
      .f{display:flex;flex-direction:column;gap:4px;margin:0 0 12px;font-size:13px}
      .f > b{font-weight:600}
      .f small,.fb small{color:var(--_muted);font-size:12px;line-height:1.35;display:block}
      .f input:not([type=checkbox]):not([type=radio]):not([type=range]),.f select,.f textarea{font:inherit;font-size:13px;border:1px solid var(--_border);border-radius:calc(var(--_radius) * .5);padding:7px 10px;background:var(--_input);color:var(--_text);max-width:100%;box-sizing:border-box}
      .f textarea{min-height:70px;resize:vertical}
      .fb{display:flex;flex-direction:row;align-items:flex-start;gap:8px;margin:0 0 10px;font-size:13px;cursor:pointer}
      .fb input{margin-top:2px}
      .choices{display:flex;flex-wrap:wrap;gap:6px}
      .choice{display:inline-flex;align-items:center;gap:5px;background:var(--_chip);color:var(--_chip-text);border-radius:14px;padding:4px 10px;font-size:13px;cursor:pointer}
      .range{display:flex;align-items:center;gap:10px}
      .range input{flex:1}
      .range output{min-width:28px;font-weight:600}
      .ferr{color:var(--_error);font-size:12px}
      .actions{display:flex;gap:8px;align-items:center;margin-top:4px}
      .ok{margin-bottom:12px;background:var(--_sel);color:var(--_text);border-radius:var(--_radius);padding:10px 14px;font-size:13px}
      .ext{font-size:12px;color:var(--_muted);margin:0 4px 12px}
      .ext a{color:var(--_accent)}
      .mrow{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-top:1px solid var(--_border)}
      .mrow:first-child{border-top:none}
      .mrow .txt a{color:var(--_text);text-decoration:none}
      .mrow .txt a:hover{text-decoration:underline}
      .mtools{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:4px}
      .mstars .star{font-size:17px;padding:2px 0}
      .x{font:inherit;border:none;background:var(--_chip);color:var(--_chip-text);border-radius:50%;width:26px;height:26px;font-size:12px;cursor:pointer;padding:0;flex:0 0 26px}
      .x.warn{background:var(--_error);color:#fff;width:auto;border-radius:13px;padding:0 10px}
      .mbar{display:flex;gap:6px;margin:0 0 10px;flex-wrap:wrap}
      .mbar input,.mbar select,.ptext{font:inherit;font-size:13px;border:1px solid var(--_border);border-radius:calc(var(--_radius) * .6);padding:7px 10px;background:var(--_input);color:var(--_text)}
      .mbar input{flex:1;min-width:140px}
      .ptext{width:100%;box-sizing:border-box;min-height:80px;resize:vertical}
      .count{font-weight:400;color:var(--_muted)}
      .xbox{max-width:none}
      .xl{margin:4px 0 10px;padding-left:20px;font-size:13px;line-height:1.4}
      .xt{white-space:pre-wrap;font:inherit;font-size:12px;line-height:1.45;background:var(--_chip);color:var(--_chip-text);border-radius:calc(var(--_radius) * .6);padding:10px 12px;margin:4px 0 8px;user-select:text}
      .xbox code{font-size:12px}
      .xd{margin-top:10px;font-size:13px}
      .xd summary{cursor:pointer;color:var(--_accent);font-weight:600}
      ${themeCss(config)}
    `;

class EssensplanerCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...(config || {}) };
    this._wishesSet = !!(config && config.wishes);
    this._open = null;
    this._wish = this._wish || "";
    this._wishes = [];
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }
  static getStubConfig() { return {}; }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: "full", rows: "auto" }; }

  set hass(hass) {
    const old = this._hass;
    this._hass = hass;
    const lang = String(hass.language || (hass.locale && hass.locale.language) || "de").slice(0, 2);
    LANG = I18N[lang] ? lang : "en";
    // umbenannte Wunschliste: die Integration nennt die aktuelle ID im Vorschlags-Sensor
    const named = ((hass.states[this._config.proposals] || {}).attributes || {}).wishes_entity;
    if (!this._wishesSet && named && named !== this._config.wishes && !this._sub) this._config.wishes = named;
    if (!this._sub && hass.connection && hass.states[this._config.wishes]) {
      this._sub = hass.connection
        .subscribeMessage((msg) => { this._wishes = msg.items || []; this._render(); },
          { type: "todo/item/subscribe", entity_id: this._config.wishes })
        .catch(() => {});
    }
    if (this._tab === "settings" && old) return; // Formular nicht beim Tippen neu aufbauen
    if (MEM_TABS.includes(this._tab) && old) { if (this._mem) this._mem.hass = hass; return; }
    const ids = [this._config.proposals, this._config.week];
    if (!old || ids.some((id) => old.states[id] !== hass.states[id])) this._render();
  }
  // Allein in einer Panel-Ansicht: ganze Höhe füllen, damit der Farbstil nicht mitten auf der Seite endet
  connectedCallback() {
    let n = this, fill = false;
    for (let i = 0; n && i < 12; i++) {
      if (n.localName === "hui-panel-view") { fill = true; break; }
      n = n.parentNode || n.host;
    }
    this.toggleAttribute("fill", fill);
  }
  disconnectedCallback() {
    if (this._sub) { this._sub.then((u) => u && u()).catch(() => {}); this._sub = null; }
    this._cancelFlow();
  }

  _svc(service, data) {
    return this._hass.callService(DOMAIN, service, data).catch((e) => {
      const m = String(e.message || e);
      // läuft schon eine Suche (z. B. von einem anderen Gerät gestartet): kein Fehler, die Anzeige zeigt „läuft …“
      this._err = /gerade schon erstellt/.test(m) ? null : m;
      this._render();
    });
  }
  _attrs(id) { return (this._hass?.states[id] || {}).attributes || {}; }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const admin = this._canSettings();
    if (!admin) this._tab = "plan";
    const cur = this._tab || "plan";
    const tabs = this._titleHtml(this._config.title == null ? t("title") : this._config.title, "mdi:silverware-fork-knife") + (admin ? `<div class="tabs">${[["plan", "tab_plan"], ["profile", "m_profile"], ["recipes", "m_recipes"], ["settings", "tab_settings"]]
      .map(([k, label]) => `<button class="tab ${cur === k ? "on" : ""}" data-tab="${k}">${t(label)}</button>`).join("")}</div>` : "");
    if (this._tab === "settings") return this._paint(tabs + this._settingsHtml(), true);
    if (MEM_TABS.includes(this._tab)) return this._showMemory(tabs);
    const prop = this._attrs(this._config.proposals);
    const week = this._attrs(this._config.week);
    // läuft gerade eine KI-Suche? (vom Sensor, also auch nach Neuladen und auf anderen Geräten richtig)
    const serverBusy = !!(prop.busy || week.busy);
    const trips = prop.trips || week.trips || [];
    const tripName = (k) => (trips.find((t) => t.key === k) || {}).name || k;
    const sched = prop.schedule || week.schedule || null;
    const dayAt = (wd, time) => (wd == null ? "" : `${t("days")[(+wd + 1) % 7]} ${time || ""}`.trim());
    const tripSub = (trip) => (trip.release === "timed" ? t("sub_at", { at: dayAt(trip.weekday, trip.time) }) : t("sub_now"));
    const short = trips.length > 3;

    const info = (d) => {
      const l1 = d.time_min ? t("prep", { n: d.time_min }) : "";
      const tags = [];
      if (d.kcal) tags.push(`${d.kcal} kcal${d.kcal_note ? ` (${d.kcal_note})` : ""}`);
      if (d.meatless) tags.push(t("meatless"));
      if (d.low_cholesterol) tags.push(t("lowchol"));
      for (const f of d.fits || []) tags.push(f);
      if (d.foreign_language) tags.push(t("foreign", { lang: d.foreign_language }));
      if (d.own_recipe) tags.push(t("own"));
      if (d.carried) tags.push(t("carried"));
      if (d.reason) tags.push(d.reason);
      return `<div class="l1">${esc(l1)}</div>${tags.length ? `<div class="l2">${tags.map(esc).join(" · ")}</div>` : ""}`;
    };
    const link = (d) => safeUrl(d.url) ? `<a class="lnk" href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener">${t("recipe")}</a>` : "";
    const ready = (d) => {
      if (d.own_recipe) return "";
      const part = (d.skip_items || []).length;
      const list = this._items && this._items.id === d.id
        ? `<div class="items">${this._items.loading ? `<span class="hint">${t("loading")}</span>` : this._items.items.length
          ? this._items.items.map((i) => `<label class="item"><input type="checkbox" data-act="item" data-id="${esc(d.id)}" data-name="${esc(i.name)}" ${i.at_home ? "checked" : ""}> ${esc(i.name)} <small>${esc(i.spec)}</small></label>`).join("")
          + `<span class="hint">${t("items_hint")}</span>`
          : `<span class="hint">${t("no_items")}</span>`}</div>` : "";
      return `<div class="darow"><button class="small ${d.ingredients_ready ? "on" : ""}" data-act="ready" data-id="${esc(d.id)}">${d.ingredients_ready ? "✓ " : ""}${t("ready")}</button>${!d.ingredients_ready ? `<button class="small ${part ? "on" : ""}" data-act="items" data-id="${esc(d.id)}">${part ? t("part_n", { n: part }) : t("partly")}</button>` : ""}<span class="hint">${d.ingredients_ready ? t("not_on_list") : ""}</span></div>${list}`;
    };
    const tripBtns = (d) => {
      const btns = trips.map((trip) => `<button class="opt ${d.choice === trip.key ? "on" : ""} ${d.tip === trip.key && d.choice !== trip.key ? "tip" : ""}" data-act="pick" data-trip="${esc(trip.key)}" data-id="${esc(d.id)}"${d.tip === trip.key ? ` title="${esc(t("tip"))}"` : ""}>${esc(short ? trip.name.slice(0, 6) : trip.name)}${short ? "" : `<small>${esc(tripSub(trip))}</small>`}</button>`).join("");
      return `<div class="opts" style="grid-template-columns:repeat(${trips.length},1fr)${d.url ? " auto" : ""}">${btns}${link(d)}</div>`;
    };

    const propTile = (d) => {
      const sel = trips.some((t) => t.key === d.choice);
      return `<div class="tile ${sel ? "sel" : ""}">
        <div class="head"><div class="ico">${sel ? "✓" : d.nr}</div>
          <div class="txt"><div class="name">${esc(d.title)}</div>${info(d)}</div></div>
        ${tripBtns(d)}${ready(d)}${sel ? "" : `<div class="darow"><button class="small" data-act="drop" data-id="${esc(d.id)}">✕ ${t("drop")}</button></div>`}</div>`;
    };
    const weekTile = (d) => {
      const done = !!d.cooked_on;
      const declined = d.choice === "declined";
      if (declined) return `<div class="tile undo">
        <div class="head"><div class="ico">✕</div><div class="txt"><div class="name">${esc(d.title)}</div>
          <div class="l2"><b>${t("declined")}</b>${t("declined_hint")}</div></div></div>
        <div class="foot"><span class="hint"></span><button class="small on" data-act="restore" data-id="${esc(d.id)}">${t("undo")}</button></div></div>`;
      const stars = STARS.map((n) => `<button class="star ${n <= (d.rating || 0) ? "on" : ""}" data-act="star" data-n="${n}" data-id="${esc(d.id)}" aria-label="${t("stars", { n })}">★</button>`).join("");
      const open = this._open === d.id;
      return `<div class="tile ${done ? "rated" : ""}">
        <div class="head"><div class="ckw"><button class="ck ${done ? "on" : ""}" data-act="cooked" data-id="${esc(d.id)}" aria-label="${t("cooked")}">${done ? "✓" : ""}</button><span class="ckl">${t("cooked")}</span></div>
          <div class="txt"><div class="name">${esc(d.title)}</div>
            <div class="l2"><b>${done ? t("cooked") : t("not_cooked")}</b> · ${esc(tripName(d.choice))}</div>${info(d)}
            ${d.note ? `<div class="rate">„${esc(d.note)}“</div>` : ""}</div></div>
        <div class="foot"><div class="stars">${stars}</div>
          <span class="hint">${d.rating ? `${d.rating}/${STAR_MAX} · ${t("rating")[Math.ceil(d.rating / 2)]}` : t("how")}</span>
          ${d.rating ? `<button class="small" data-act="note" data-id="${esc(d.id)}">${t("note")}</button>` : ""}
          ${!done && !d.rating ? `<button class="small" data-act="decline" data-id="${esc(d.id)}">${t("decline")}</button>` : ""}${link(d)}</div>
        ${!done ? ready(d) : ""}
        ${open ? `<div class="rbox"><input id="r-${esc(d.id)}" placeholder="${esc(t("note_ph"))}"><button class="small on" data-act="save" data-id="${esc(d.id)}">${t("save")}</button></div>` : ""}
      </div>`;
    };

    const propsAll = prop.dishes || [];
    const props = propsAll.filter((d) => d.choice !== "declined");  // entfernte Vorschläge ausblenden
    const plan = week.dishes || [];
    let body = this._err ? `<div class="empty err">${esc(this._err)}</div>` : "";
    if (props.length) {
      const counts = trips.map((t) => `${props.filter((d) => d.choice === t.key).length} × ${t.name}`).join(", ");
      const rel = Object.entries(prop.release_at || {}).map(([k, at]) => t("release", { trip: tripName(k), at: fmt(at) }));
      body += `<div class="sec">${esc(t("proposals", { kw: prop.kw }))} · ${esc(counts)}<span>${esc(t("proposals_hint", { at: fmt(prop.deadline) }))}${rel.length ? ". " + esc(rel.join(", ")) : ""}</span></div>
        <div class="grid">${props.map(propTile).join("")}</div>`;
      if ((prop.deficits || []).length) body += `<div class="darow pick"><span class="hint">${t("open")}${esc(prop.deficits.join(", "))}</span></div>`;
    }
    // Kandidaten in der laufenden Woche (über „Mehr Vorschläge“ dazugeholt, noch nicht gewählt)
    const cands = plan.filter((d) => d.choice === "none" && !d.cooked_on);
    // „Doch nicht“: abgewählte Gerichte verschwinden aus der Woche (Rückgängig über die Leiste unten)
    const taken = plan.filter((d) => !cands.includes(d) && d.choice !== "declined");
    if (taken.length) {
      const cooked = taken.filter((d) => d.cooked_on).length;
      body += `<div class="sec">${esc(t("week", { c: cooked, n: taken.length }))}<span>${t("week_hint")}</span></div>
        <div class="grid">${taken.map(weekTile).join("")}</div>`;
    }
    if (cands.length) {
      body += `<div class="sec">${esc(t("cand"))}<span>${esc(t("cand_hint"))}</span></div>
        <div class="grid">${cands.map(propTile).join("")}</div>
        <div class="darow"><button class="small ${this._sure === "dropall" ? "on" : ""}" data-act="dropall">✕ ${t(this._sure === "dropall" ? "drop_all_sure" : "drop_all")}</button></div>`;
    }
    // Früher einkaufen: Einkäufe mit festem Termin, die noch nicht auf der Liste sind, sofort freigeben
    const waiting = trips.filter((x) => [[prop, props], [week, plan]].some(([b, ds]) =>
      (b.released || {})[x.key] === false && ds.some((d) => d.choice === x.key && !d.ingredients_ready && !d.own_recipe)));
    if (waiting.length) {
      body += `<div class="darow shop">${waiting.map((x) => `<button class="small ${this._shopSure === x.key ? "on" : ""}" data-act="shopnow" data-trip="${esc(x.key)}">🛒 ${esc(this._shopSure === x.key ? t("shop_sure", { trip: x.name }) : t("shop_now", { trip: x.name }))}</button>`).join("")}<span class="hint">${esc(t("shop_hint"))}</span></div>`;
    }
    if (!props.length && !plan.length) body += `<div class="empty">${t("empty")}</div>`;
    // Mehr Vorschläge: holt weitere Gerichte dazu, ohne Vorschläge und Woche wird jetzt geplant
    const rk = props.length || plan.length ? "more" : "plan_now";
    body += `<div class="darow shop">${this._busy === "more" || (serverBusy && !this._busy)
      ? `<button class="small on" disabled>⏳ ${t("busy")}</button>`
      : `<button class="small ${this._sure === "more" ? "on" : ""}" data-act="more" data-kind="${rk}"${this._busy || serverBusy ? " disabled" : ""}>${rk === "more" ? "➕" : "✨"} ${t(this._sure === "more" ? "plan_now_sure" : rk)}</button>`}<span class="hint">${t(rk + "_hint")}</span></div>`;
    const undo = this._undo && [...propsAll, ...plan].find((d) => d.id === this._undo.id && d.choice === "declined");
    if (undo) {
      body += `<div class="undobar"><span>${esc(t("removed", { title: undo.title }))}</span><button class="small on" data-act="restore" data-id="${esc(undo.id)}">${t("undo")}</button></div>`;
    }
    if (this._hass.states[this._config.wishes]) {
      const open = this._wishes.filter((w) => w.status !== "completed");
      body += `<div class="sec">${t("wishes")}<span>${esc(t("wishes_hint"))}</span></div>
        <div class="wish"><input id="wish-in" placeholder="${esc(t("wish_ph"))}" value="${esc(this._wish)}"><button class="small on" data-act="wish">${t("add")}</button><button class="small" data-act="wishown">${t("own_btn")}</button></div>
        ${open.length ? `<div class="chips">${open.map((w) => `<span class="chip">${esc(w.summary)}${/eigenes rezept/i.test(w.description || "") ? ` <small>${t("own_short")}</small>` : ""}<button data-act="delwish" data-uid="${esc(w.uid)}" aria-label="${t("del_wish")}">✕</button></span>`).join("")}</div>` : ""}`;
    }

    let help = "";
    if (this._config.help !== false && sched) {
      // Zeitleiste aus den Einstellungen: was passiert wann, ab dem Planungstag in Reihenfolge
      const pos = (wd, time) => {
        const [h, m] = String(time || "0:0").split(":").map(Number);
        return ((+wd - +sched.plan_weekday + 7) % 7) * 1440 + h * 60 + (m || 0);
      };
      const ev = [[pos(sched.plan_weekday, sched.plan_time), dayAt(sched.plan_weekday, sched.plan_time), t("tl_plan", { n: sched.recipes_per_week })],
        [pos(sched.deadline_weekday, sched.deadline_time), dayAt(sched.deadline_weekday, sched.deadline_time), t("tl_deadline")],
        ...trips.filter((x) => x.release === "timed").map((x) => [pos(x.weekday, x.time), dayAt(x.weekday, x.time), t("tl_release", { trip: x.name })])]
        .sort((a, b) => a[0] - b[0]);
      const now = trips.filter((x) => x.release !== "timed").map((x) => t("h_now", { trip: x.name })).join(" ");
      help = `<div class="tl">${ev.map(([, at, txt]) => `<div class="tlr"><b>${esc(at)}</b><span>${md(txt)}</span></div>`).join("")}</div>`
        + [t("h_pick", { trips: trips.map((x) => x.name).join(", ") }) + (now ? " " + now : ""), t("h_undo"), t("h_cook")]
          .map((x) => `<p>${md(x)}</p>`).join("");
    }
    const main = help
      ? `<div class="layout"><div class="cols"><div>${tabs}${body}</div><div class="aside">${this._titleHtml(t("h_title"), "mdi:information-outline")}<div class="help">${help}</div></div></div></div>`
      : tabs + body;
    this._paint(main, false);

    const all = [...propsAll, ...plan];
    const find = (id) => all.find((d) => d.id === id);
    const win = this.shadowRoot.getElementById("wish-in");
    if (win) {
      win.addEventListener("input", () => { this._wish = win.value; });
      win.addEventListener("keydown", (ev) => { if (ev.key === "Enter") this._addWish(false); });
    }
    this.shadowRoot.querySelectorAll("[data-act]").forEach((el) => el.addEventListener("click", (ev) => {
      if (el.dataset.act !== "item") ev.stopPropagation();
      this._err = null;
      const act = el.dataset.act;
      if (act === "wish" || act === "wishown") return this._addWish(act === "wishown");
      if (act === "delwish") return this._hass.callService("todo", "remove_item", { item: el.dataset.uid }, { entity_id: this._config.wishes });
      if (act === "more") {
        const key = "more";
        // vorzeitiges Planen mit zweitem Tippen bestätigen, Dazuholen sofort
        if (el.dataset.kind !== "more" && this._sure !== key) { this._sure = key; return this._render(); }
        this._sure = null;
        this._busy = "more";
        this._render();
        const done = () => { this._busy = null; this._render(); };
        return this._svc("more_proposals", {}).then(done, done);
      }
      if (act === "shopnow") {
        // zweimal tippen: der Einkauf landet sofort auf der Liste
        if (this._shopSure !== el.dataset.trip) { this._shopSure = el.dataset.trip; return this._render(); }
        this._shopSure = null;
        return this._svc("release_shopping", { trip: el.dataset.trip });
      }
      if (act === "dropall") {
        // zweimal tippen: alle noch nicht gewählten Kandidaten der Woche entfernen
        if (this._sure !== "dropall") { this._sure = "dropall"; return this._render(); }
        this._sure = null;
        const ids = cands.map((x) => x.id);
        return ids.reduce((p, id) => p.then(() => this._svc("choose_dish", { dish_id: id, choice: "declined" })), Promise.resolve());
      }
      const d = find(el.dataset.id); if (!d) return;
      if (act === "pick") this._svc("choose_dish", { dish_id: d.id, choice: d.choice === el.dataset.trip ? "none" : el.dataset.trip });
      else if (act === "ready") this._svc("set_ingredients_ready", { dish_id: d.id, ready: !d.ingredients_ready });
      else if (act === "cooked") this._svc("mark_cooked", { dish_id: d.id, cooked: !d.cooked_on });
      else if (act === "star") this._svc("mark_cooked", { dish_id: d.id, cooked: !!d.cooked_on, rating: +el.dataset.n });
      else if (act === "decline" || act === "drop") {
        this._prev = { ...(this._prev || {}), [d.id]: d.choice };
        clearTimeout(this._undoTimer);
        this._undo = { id: d.id };
        this._undoTimer = setTimeout(() => { this._undo = null; this._render(); }, 8000);
        this._svc("choose_dish", { dish_id: d.id, choice: "declined" });
      }
      else if (act === "restore") {
        clearTimeout(this._undoTimer); this._undo = null;
        this._svc("choose_dish", { dish_id: d.id, choice: (this._prev || {})[d.id] || d.tip || (trips[0] || {}).key });
      }
      else if (act === "items") this._toggleItems(d);
      else if (act === "item") this._saveItems(d);
      else if (act === "note") { this._open = this._open === d.id ? null : d.id; this._render(); }
      else if (act === "save") {
        const i = this.shadowRoot.getElementById("r-" + d.id);
        this._open = null;
        this._svc("mark_cooked", { dish_id: d.id, cooked: !!d.cooked_on, rating: d.rating || 6, note: i ? i.value : "" });
      }
    }));
  }

  // Geschmacksprofil und Rezepte: eine dauerhafte Unteransicht, damit Suche und Eingaben beim Wechseln erhalten bleiben
  _showMemory(tabs) {
    this._paint(tabs + '<div id="mem"></div>', false);
    if (!this._mem) {
      this._mem = document.createElement("meal-planner-memory-card");
      this._mem.setConfig({ ...this._config, embedded: true });
    }
    this._mem._view = this._tab;
    this.shadowRoot.getElementById("mem").appendChild(this._mem);
    this._mem.hass = this._hass;
    this._mem._render();
  }

  _titleHtml(text, icon) {
    return text ? `<div class="titel"><ha-icon icon="${icon}"></ha-icon><span>${esc(text)}</span></div>` : "";
  }
  _paint(body, settings) {
    this.shadowRoot.innerHTML = `<style>${cardCss(this._config)}</style>${body}`;
    this.shadowRoot.querySelectorAll("[data-tab]").forEach((el) => el.addEventListener("click", () => {
      const tab = el.dataset.tab;
      if (tab === this._tab || (!this._tab && tab === "plan")) return;
      this._tab = tab;
      if (tab === "settings") this._openSettings(); else { this._cancelFlow(); this._set = null; this._render(); }
      if (MEM_TABS.includes(tab) && this._mem) this._mem._load();
    }));
    if (settings) this._bindSettings();
  }

  // ------------------------------------------------------------ Einstellungen ---
  // Nutzt den normalen Optionsdialog der Integration über die HA-API (nur für Administratoren).
  _canSettings() {
    return this._config.settings !== false && !!(this._hass && this._hass.user && this._hass.user.is_admin);
  }
  _t(key, ph) {
    let text = (this._trans || {})["component." + DOMAIN + "." + key];
    if (text == null || text === "") return null;
    for (const [k, v] of Object.entries(ph || {})) text = text.split(`{${k}}`).join(v == null ? "" : String(v));
    return text;
  }
  async _loadTranslations() {
    if (this._trans) return;
    const get = (category) => this._hass.callWS({ type: "frontend/get_translations", language: this._hass.language || "en",
      category, integration: [DOMAIN] }).then((r) => (r && r.resources) || {}).catch(() => ({}));
    const [a, b] = await Promise.all([get("options"), get("selector")]);
    this._trans = { ...a, ...b };
  }
  async _entryId() {
    if (this._entry) return this._entry;
    const list = await this._hass.callWS({ type: "config_entries/get", domain: DOMAIN });
    this._entry = list && list[0] && list[0].entry_id;
    if (!this._entry) throw new Error(t("not_setup"));
    return this._entry;
  }
  _cancelFlow() {
    const flow = this._set && this._set.flow;
    if (flow && this._hass) this._hass.callApi("DELETE", `${FLOW}/${flow}`).catch(() => {});
    if (this._set) this._set.flow = null;
  }
  async _openSettings(msg) {
    this._set = { loading: true };
    this._render();
    try {
      await this._loadTranslations();
      if (!this._menu) {
        const res = await this._hass.callApi("POST", FLOW, { handler: await this._entryId(), show_advanced_options: false });
        this._menu = res.menu_options || [];
        this._hass.callApi("DELETE", `${FLOW}/${res.flow_id}`).catch(() => {});
      }
      this._set = { menu: true, msg };
      // Einrichtungshilfe, wenn die Vorschläge von einer externen KI kommen
      try {
        const ext = await this._hass.callService(DOMAIN, "external_setup", { view: true }, undefined, false, true);
        this._ext = ext.response || ext;
      } catch (e) { this._ext = null; }
    } catch (e) { this._set = { menu: true, error: errText(e) }; }
    this._render();
  }
  async _startStep(step) {
    this._cancelFlow();
    this._set = { loading: true };
    this._render();
    try {
      let res = await this._hass.callApi("POST", FLOW, { handler: await this._entryId(), show_advanced_options: false });
      if (res.type === "menu") res = await this._hass.callApi("POST", `${FLOW}/${res.flow_id}`, { next_step_id: step });
      this._section = step;
      this._handle(res);
    } catch (e) { this._set = { menu: true, error: errText(e) }; this._render(); }
  }
  _handle(res) {
    const section = this._t(`options.step.init.menu_options.${this._section}`) || this._section;
    if (res.type === "form") {
      const same = this._set && this._set.step === res.step_id && this._set.data;
      const data = {};
      for (const f of res.data_schema || []) {
        if (same && f.name in this._set.data) data[f.name] = this._set.data[f.name];
        else if (f.description && f.description.suggested_value != null) data[f.name] = f.description.suggested_value;
        else if ("default" in f) data[f.name] = f.default;
      }
      this._set = { flow: res.flow_id, step: res.step_id, schema: res.data_schema || [], data,
        ph: res.description_placeholders || {}, errors: res.errors || {}, last: res.last_step };
    } else if (res.type === "create_entry") {
      this._set = { menu: true, msg: t("saved", { s: section }) };
    } else if (res.type === "abort") {
      this._set = { menu: true, error: this._t(`options.abort.${res.reason}`, res.description_placeholders) || res.reason };
    } else if (res.type === "menu") {
      this._set = { menu: true };
    }
    this._render();
  }
  async _submit() {
    const st = this._set; if (!st || !st.flow) return;
    const payload = {};
    for (const f of st.schema) {
      const type = Object.keys(f.selector || {})[0];
      let v = st.data[f.name];
      if (v === undefined || v === null) continue;
      if (v === "" && type !== "text") continue;
      if (type === "time" && /^\d{2}:\d{2}$/.test(v)) v += ":00";
      payload[f.name] = v;
    }
    st.busy = true; st.error = null;
    this._render();
    try {
      this._handle(await this._hass.callApi("POST", `${FLOW}/${st.flow}`, payload));
    } catch (e) { st.busy = false; st.error = errText(e); this._render(); }
  }

  _settingsHtml() {
    const st = this._set || { loading: true };
    if (st.loading) return `<div class="empty">${t("loading_settings")}</div>`;
    if (st.menu) {
      const items = (this._menu || []).map((m) => `<button class="mbtn" data-step="${esc(m)}">${esc(this._t(`options.step.init.menu_options.${m}`) || m)}</button>`).join("");
      return `${st.msg ? `<div class="ok">${esc(st.msg)}</div>` : ""}${st.error ? `<div class="empty err">${esc(st.error)}</div>` : ""}
        <div class="sec">${t("tab_settings")}<span>${md((this._t("options.step.init.description") || t("settings_hint")).replace(/\s*📖 \[[^\]]*\]\([^)]*\)/, ""))}</span></div>
        ${this._extHtml()}<div class="menu">${items}</div>
        <div class="ext">${t("ext")} <a href="/config/integrations/integration/meal_planner_ai">${esc(t("ext_path"))}</a>.</div>
        <div class="ext">📖 <a href="${DOCS_URL}${LANG === "de" ? "anleitung.md" : "guide.md"}" target="_blank" rel="noopener noreferrer">${esc(t("docs"))}</a></div>`;
    }
    const title = this._t(`options.step.${st.step}.title`, st.ph) || this._t(`options.step.init.menu_options.${this._section}`) || st.step;
    const desc = this._t(`options.step.${st.step}.description`, st.ph);
    const base = st.errors.base ? (this._t(`options.error.${st.errors.base}`, st.ph) || st.errors.base) : "";
    const sub = st.step !== this._section;  // zweiter Schritt eines Bereichs (z. B. Einkauf-Details)
    return `<button class="back" data-sact="${sub ? "restart" : "cancel"}">‹ ${sub ? t("back") : t("all_settings")}</button>
      <div class="form"><h3>${esc(title)}</h3>${desc ? `<div class="desc">${md(desc)}</div>` : ""}
      ${base ? `<div class="ferr">${esc(base)}</div>` : ""}${st.error ? `<div class="ferr">${esc(st.error)}</div>` : ""}
      ${st.schema.map((f) => this._fieldHtml(f)).join("")}
      <div class="actions"><button class="small on" data-sact="submit" ${st.busy ? "disabled" : ""}>${st.busy ? t("saving") : st.last === false ? t("next") : t("save")}</button>
        <button class="small" data-sact="cancel">${t("cancel")}</button></div></div>
      <button class="back" data-sact="cancel">‹ ${t("all_settings")}</button>`;
  }
  _selectTask() {  // ohne Zwischenablage-Zugriff (z. B. http): Text markieren, damit man ihn kopieren kann
    const pre = this.shadowRoot.querySelector(".xt");
    if (!pre) return;
    const range = document.createRange(); range.selectNodeContents(pre);
    const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  }
  _extHtml() {
    const x = this._ext;
    if (!x || !x.enabled) return "";
    return `${x.schedule_changed ? `<div class="empty err">${esc(t("x_changed", { old: x.registered_schedule, now: x.schedule }))}</div>` : ""}<div class="form xbox"><h3>${t("x_title")}</h3><div class="desc">${esc(t("x_intro"))}</div>
      <b>${t("x_need")}</b><ol class="xl">${x.requirements.map((r) => `<li>${esc(r)}</li>`).join("")}</ol>
      <b>${t("x_when")}</b><div class="desc">${esc(x.schedule)}${x.cron ? `<br><code>${esc(x.cron)}</code>` : ""}<br>${esc(x.fallback)}</div>
      <b>${t("x_how")}</b><ol class="xl">${(x.steps || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ol>
      ${x.phrase ? `<div class="actions"><button class="small on" data-sact="copy" data-what="phrase">${this._copied === "phrase" ? t("x_copied") : t("x_copy_phrase")}</button></div>` : ""}
      <details class="xd"><summary>${t("x_manual")}</summary>
        <div class="desc">${esc(t("x_manual_hint"))}</div>
        <div class="actions"><button class="small" data-sact="copy" data-what="chat">${this._copied === "chat" ? t("x_copied") : t("x_copy_chat")}</button>
          <button class="small" data-sact="copy" data-what="task">${this._copied === "task" ? t("x_copied") : t("x_copy")}</button></div>
        <pre class="xt">${esc(x.task_text)}</pre></details></div>`;
  }
  _fieldHtml(f) {
    const st = this._set;
    const name = f.name;
    const label = this._t(`options.step.${st.step}.data.${name}`, st.ph) || name;
    const help = this._t(`options.step.${st.step}.data_description.${name}`, st.ph);
    const err = st.errors[name] ? `<span class="ferr">${esc(this._t(`options.error.${st.errors[name]}`, st.ph) || st.errors[name])}</span>` : "";
    const type = Object.keys(f.selector || { text: {} })[0];
    const c = (f.selector || {})[type] || {};
    const v = st.data[name];
    const n = esc(name);
    const head = `<b>${esc(label)}</b>${help ? `<small>${md(help)}</small>` : ""}`;
    if (type === "boolean") {
      return `<label class="fb"><input type="checkbox" data-f="${n}" data-k="bool" ${v ? "checked" : ""}><span>${head}${err}</span></label>`;
    }
    let input = "";
    if (type === "number") {
      const attrs = `min="${esc(c.min ?? "")}" max="${esc(c.max ?? "")}" step="${esc(c.step ?? 1)}"`;
      input = c.mode === "slider"
        ? `<div class="range"><input type="range" ${attrs} value="${esc(v ?? c.min ?? 0)}" data-f="${n}" data-k="num"><output>${esc(v ?? "")}</output>${c.unit_of_measurement ? esc(c.unit_of_measurement) : ""}</div>`
        : `<div class="range"><input type="number" ${attrs} value="${esc(v ?? "")}" data-f="${n}" data-k="num" style="max-width:140px">${c.unit_of_measurement ? esc(c.unit_of_measurement) : ""}</div>`;
    } else if (type === "time") {
      input = `<input type="time" value="${esc(String(v || "").slice(0, 5))}" data-f="${n}" data-k="str" style="max-width:140px">`;
    } else if (type === "select" || type === "entity") {
      let opts;
      if (type === "entity") {
        const domains = [].concat(c.domain || [], ...(Array.isArray(c.filter) ? c.filter : c.filter ? [c.filter] : []).map((x) => x.domain || []));
        opts = Object.entries(this._hass.states).filter(([id]) => !domains.length || domains.includes(id.split(".")[0]))
          .map(([id, s]) => ({ value: id, label: (s.attributes && s.attributes.friendly_name) || id }))
          .sort((a, b) => a.label.localeCompare(b.label));
      } else {
        opts = (c.options || []).map((o) => typeof o === "object" ? o
          : { value: o, label: (c.translation_key && this._t(`selector.${c.translation_key}.options.${o}`)) || o });
      }
      for (const o of [].concat(v ?? [])) if (o !== "" && !opts.some((x) => x.value === o)) opts.push({ value: o, label: o });
      if (c.multiple) {
        const sel = [].concat(v || []);
        input = opts.length ? `<div class="choices">${opts.map((o) => `<label class="choice"><input type="checkbox" data-f="${n}" data-k="multi" value="${esc(o.value)}" ${sel.includes(o.value) ? "checked" : ""}>${esc(o.label)}</label>`).join("")}</div>`
          : `<small>${t("no_choice")}</small>`;
      } else if (c.mode === "list" && opts.length <= 8) {
        input = `<div class="choices">${opts.map((o) => `<label class="choice"><input type="radio" name="r-${n}" data-f="${n}" data-k="str" value="${esc(o.value)}" ${v === o.value ? "checked" : ""}>${esc(o.label)}</label>`).join("")}</div>`;
      } else {
        input = `<select data-f="${n}" data-k="str">${f.required ? "" : `<option value=""></option>`}${opts.map((o) => `<option value="${esc(o.value)}" ${v === o.value ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`;
      }
    } else {
      input = c.multiline
        ? `<textarea data-f="${n}" data-k="str">${esc(v ?? "")}</textarea>`
        : `<input type="${c.type === "url" ? "url" : "text"}" value="${esc(v ?? "")}" data-f="${n}" data-k="str">`;
    }
    return `<div class="f">${head}${input}${err}</div>`;
  }
  _bindSettings() {
    const root = this.shadowRoot;
    root.querySelectorAll("[data-step]").forEach((el) => el.addEventListener("click", () => this._startStep(el.dataset.step)));
    root.querySelectorAll("[data-sact]").forEach((el) => el.addEventListener("click", () => {
      const act = el.dataset.sact;
      if (act === "copy") {
        const what = el.dataset.what || "task";
        const done = () => { this._copied = what; this._render(); setTimeout(() => { this._copied = null; this._render(); }, 2500); };
        const text = (this._ext || {})[{ chat: "chat_message", phrase: "phrase" }[what] || "task_text"] || "";
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done).catch(() => this._selectTask());
        else this._selectTask();
        return;
      }
      if (act === "submit") this._submit();
      else if (act === "restart") this._startStep(this._section);  // Bereich von vorn: Schritt 1
      else { this._cancelFlow(); this._openSettings(); }
    }));
    const st = this._set;
    if (!st || !st.data) return;
    root.querySelectorAll("[data-f]").forEach((el) => {
      const update = () => {
        const name = el.dataset.f;
        const kind = el.dataset.k;
        if (kind === "bool") st.data[name] = el.checked;
        else if (kind === "num") {
          st.data[name] = el.value === "" ? null : Number(el.value);
          const out = el.parentElement && el.parentElement.querySelector("output");
          if (out) out.textContent = el.value;
        } else if (kind === "multi") {
          st.data[name] = [...root.querySelectorAll('input[data-k="multi"]')].filter((b) => b.dataset.f === name && b.checked).map((b) => b.value);
        } else if (el.type !== "radio" || el.checked) st.data[name] = el.value;
      };
      el.addEventListener("input", update);
      el.addEventListener("change", update);
    });
  }

  async _toggleItems(d) {
    if (this._items && this._items.id === d.id) { this._items = null; this._render(); return; }
    this._items = { id: d.id, loading: true, items: [] };
    this._render();
    try {
      const res = await this._hass.callService(DOMAIN, "dish_items", { dish_id: d.id }, undefined, false, true);
      this._items = { id: d.id, loading: false, items: (res && res.response && res.response.items) || [] };
    } catch (e) { this._items = null; this._err = String(e.message || e); }
    this._render();
  }
  _saveItems(d) {
    const boxes = [...this.shadowRoot.querySelectorAll('input[data-act="item"]')].filter((b) => b.dataset.id === d.id);
    const names = boxes.filter((b) => b.checked).map((b) => b.dataset.name);
    if (this._items) this._items.items = this._items.items.map((i) => ({ ...i, at_home: names.includes(i.name) }));
    this._svc("set_items_at_home", { dish_id: d.id, items: names });
  }

  _addWish(own) {
    const text = (this._wish || "").trim(); if (!text) return;
    this._wish = "";
    const data = { item: text };
    if (own) data.description = "eigenes Rezept";
    this._hass.callService("todo", "add_item", data, { entity_id: this._config.wishes });
    this._render();
  }
}

// Kachel "Gemerkt": Geschmacksprofil und Rezeptsammlung ansehen, ändern, löschen
class EssensplanerMemoryCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...(config || {}) };
    this._view = this._view || "profile";
    this._q = this._q || "";
    this._sort = this._sort || "name";
    this._limit = 30;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }
  static getStubConfig() { return {}; }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: "full", rows: "auto" }; }

  set hass(hass) {
    const old = this._hass;
    this._hass = hass;
    const lang = String(hass.language || (hass.locale && hass.locale.language) || "de").slice(0, 2);
    LANG = I18N[lang] ? lang : "en";
    // neu laden, wenn sich die Woche ändert (gekocht, bewertet)
    const id = this._config.week;
    // Nicht-Admins sehen nur einen Hinweis: einmal zeichnen, nicht bei jeder Zustandsänderung im Haus
    if (!(hass.user && hass.user.is_admin)) { if (!old) this._render(); return; }
    // Integration noch nicht geladen (z. B. kurz nach dem Neustart): nicht anfragen, sonst Fehler im Log.
    // Sobald der Sensor da ist, ändert er sich und das Laden startet von selbst.
    if (!hass.states[id]) { if (!old) this._render(); return; }
    if (!old || !this._data || (old.states[id] !== hass.states[id] && !this._editing)) this._load();
  }

  async _load() {
    if (this._loading || !this._hass) return;
    this._loading = true;
    try {
      const res = await this._hass.callService(DOMAIN, "memory_overview", {}, undefined, false, true);
      this._data = res.response || res;
      this._err = null;
    } catch (e) { this._err = String(e.message || e); }
    this._loading = false;
    this._render();
  }
  async _svc(service, data) {
    try { await this._hass.callService(DOMAIN, service, data); this._err = null; }
    catch (e) { this._err = String(e.message || e); }
    this._editing = null; this._sure = null;
    await this._load();
  }

  _stars(r, act) {
    return `<span class="stars mstars">${STARS.map((n) => `<button class="star ${n <= (r.rating || 0) ? "on" : ""}" data-act="${act}" data-n="${n}" data-id="${esc(r.id)}" aria-label="${t("stars", { n })}">★</button>`).join("")}</span>`;
  }
  _title(r) {
    return safeUrl(r.url) ? `<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title);
  }
  _date(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.split("-");
    return `${d}.${m}.${y}`;
  }

  _profileHtml(d) {
    const row = (r, recent) => `<div class="mrow"><div class="txt"><div class="name">${this._title(r)}</div>
        <div class="mtools">${recent ? `<span class="l2">${esc(t("m_last", { d: this._date(r.last) }))}</span>` : this._stars(r, "rate")}
        ${r.note ? `<span class="l2">„${esc(r.note)}“</span>` : ""}</div></div>
        ${recent ? `<button class="x" data-act="uncook" data-id="${esc(r.id)}" data-day="${esc(r.last)}" aria-label="✕">✕</button>`
          : `<button class="x" data-act="unrate" data-id="${esc(r.id)}" aria-label="${t("m_unrate")}" title="${t("m_unrate")}">✕</button>`}</div>`;
    const block = (title, list, recent, hint) => `<div class="form"><h3>${title} <span class="count">${list.length}</span></h3>
      ${hint ? `<div class="desc">${esc(hint)}</div>` : ""}
      ${list.length ? list.map((r) => row(r, recent)).join("") : `<div class="l2">${t("m_none")}</div>`}</div>`;
    return `<div class="sec">${t("m_profile")}<span>${esc(t("m_profile_hint"))}</span></div>
      <div class="form"><h3>${t("m_rules")}</h3><div class="desc">${esc(t("m_rules_hint"))}</div>
        <textarea id="ptext" class="ptext" placeholder="${esc(t("m_rules_ph"))}">${esc(this._ptext ?? d.profile_text)}</textarea>
        <div class="actions"><button class="small on" data-act="saveprofile">${t("save")}</button>${this._ok ? `<span class="hint">${t("m_saved")}</span>` : ""}</div></div>
      ${block(t("m_liked"), d.liked || [], false)}${block(t("m_neutral"), d.neutral || [], false)}${block(t("m_disliked"), d.disliked || [], false)}
      ${block(t("m_recent"), d.recent || [], true, t("m_recent_hint"))}`;
  }

  _recipesHtml(d) {
    const q = this._q.toLowerCase();
    // nur bewertete Rezepte; alles andere ist Zwischenspeicher aus Vorschlägen
    let list = (d.recipes || []).filter((r) => r.rating).filter((r) => !q || (r.title || "").toLowerCase().includes(q) || (r.note || "").toLowerCase().includes(q));
    const by = {
      name: (a, b) => (a.title || "").localeCompare(b.title || ""),
      rating: (a, b) => (b.rating || 0) - (a.rating || 0) || (a.title || "").localeCompare(b.title || ""),
      last: (a, b) => String(b.last || "").localeCompare(String(a.last || "")),
      times: (a, b) => b.times - a.times,
    };
    list = [...list].sort(by[this._sort] || by.name);
    const shown = list.slice(0, this._limit);
    const row = (r) => {
      const info = [r.times ? t("m_times", { n: r.times }) : t("m_never")];
      if (r.last) info.push(t("m_last", { d: this._date(r.last) }));
      if (r.host) info.push(r.host);
      if (r.stub) info.push(t("m_stub"));
      const edit = this._editing === r.id;
      return `<div class="mrow"><div class="txt"><div class="name">${this._title(r)}</div>
          <div class="l2">${esc(info.join(" · "))}</div>
          <div class="mtools">${this._stars(r, "rate")}
            ${r.rating ? `<button class="small" data-act="unrate" data-id="${esc(r.id)}">${t("m_unrate")}</button>` : ""}
            <button class="small ${edit ? "on" : ""}" data-act="note" data-id="${esc(r.id)}">${t("m_note")}</button>
            ${r.note && !edit ? `<span class="l2">„${esc(r.note)}“</span>` : ""}</div>
          ${edit ? `<div class="rbox"><input id="n-${esc(r.id)}" value="${esc(r.note || "")}" placeholder="${esc(t("note_ph"))}"><button class="small on" data-act="savenote" data-id="${esc(r.id)}">${t("save")}</button></div>` : ""}
        </div>
        <button class="x ${this._sure === r.id ? "warn" : ""}" data-act="del" data-id="${esc(r.id)}" aria-label="${t("m_del")}" title="${t("m_del")}">${this._sure === r.id ? t("m_del_sure") : "🗑"}</button></div>`;
    };
    return `<div class="mbar"><input id="mq" placeholder="${esc(t("m_search"))}" value="${esc(this._q)}">
        <select id="msort">${["name", "rating", "last", "times"].map((k) => `<option value="${k}" ${this._sort === k ? "selected" : ""}>${t("m_sort_" + k)}</option>`).join("")}</select></div>
      <div class="form"><h3>${t("m_recipes")} <span class="count">${esc(t("m_count", { n: list.length }))}</span></h3>
        ${shown.length ? shown.map(row).join("") : `<div class="l2">${t("m_none")}</div>`}
        ${list.length > shown.length ? `<div class="actions"><button class="small" data-act="more">${esc(t("m_more", { n: list.length - shown.length }))}</button></div>` : ""}</div>`;
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    if (!(this._hass.user && this._hass.user.is_admin)) {
      // Profil und Rezepte ändern nur Administratoren (wie die Tabs in der Hauptkarte)
      this.shadowRoot.innerHTML = `<style>${cardCss(this._config)}</style><div class="empty">${t("m_admin")}</div>`;
      return;
    }
    const d = this._data;
    const tabs = this._config.embedded ? "" : `<div class="tabs">${["profile", "recipes"].map((v) => `<button class="tab ${this._view === v ? "on" : ""}" data-view="${v}">${t(v === "profile" ? "m_profile" : "m_recipes")}</button>`).join("")}</div>`;
    let body = this._err ? `<div class="empty err">${esc(this._err)}</div>` : "";
    if (!d) body += `<div class="empty">${t("loading")}</div>`;
    else body += this._view === "recipes" ? this._recipesHtml(d) : this._profileHtml(d);
    const focus = this.shadowRoot.activeElement && this.shadowRoot.activeElement.id;
    this.shadowRoot.innerHTML = `<style>${cardCss(this._config)}</style>${tabs}${body}`;
    this._bind(d);
    if (focus === "mq") { const q = this.shadowRoot.getElementById("mq"); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
  }

  _bind(d) {
    const root = this.shadowRoot;
    root.querySelectorAll("[data-view]").forEach((el) => el.addEventListener("click", () => {
      this._view = el.dataset.view; this._sure = null; this._render();
    }));
    const q = root.getElementById("mq");
    if (q) q.addEventListener("input", () => { this._q = q.value; this._limit = 30; this._render(); });
    const sort = root.getElementById("msort");
    if (sort) sort.addEventListener("change", () => { this._sort = sort.value; this._render(); });
    const ptext = root.getElementById("ptext");
    if (ptext) ptext.addEventListener("input", () => { this._ptext = ptext.value; this._ok = false; });
    root.querySelectorAll("[data-act]").forEach((el) => el.addEventListener("click", (ev) => {
      ev.preventDefault();
      const act = el.dataset.act, id = el.dataset.id;
      if (act === "rate") return this._svc("update_history", { recipe_id: id, rating: +el.dataset.n });
      if (act === "unrate") return this._svc("update_history", { recipe_id: id, rating: 0 });
      if (act === "uncook") return this._svc("update_history", { recipe_id: id, remove_cooked_on: el.dataset.day });
      if (act === "note") { this._editing = this._editing === id ? null : id; return this._render(); }
      if (act === "savenote") {
        const i = root.getElementById("n-" + id);
        return this._svc("update_history", { recipe_id: id, note: i ? i.value : "" });
      }
      if (act === "del") {
        if (this._sure !== id) { this._sure = id; return this._render(); }
        return this._svc("delete_recipe", { recipe_id: id });
      }
      if (act === "more") { this._limit += 50; return this._render(); }
      if (act === "saveprofile") {
        const text = this._ptext ?? (d && d.profile_text) ?? "";
        this._hass.callService(DOMAIN, "set_profile", { text }).then(() => {
          this._ok = true; this._ptext = undefined; setTimeout(() => this._load(), 1500); this._render();
        }).catch((e) => { this._err = String(e.message || e); this._render(); });
      }
    }));
  }
}

// Eigene Seite in der Seitenleiste: Kopfzeile + Karte, Farben aus dem HA-Design oder dem gewählten Stil
class EssensplanerPanel extends HTMLElement {
  _build() {
    const cfg = (this._panel && this._panel.config) || {};
    const preset = PRESETS[cfg.preset] || {};
    this.innerHTML = `<style>
      meal-planner-panel{display:block;min-height:100vh;background:${preset.background || "var(--primary-background-color)"}}
      meal-planner-panel .bar{display:flex;align-items:center;gap:8px;height:56px;padding:0 12px;font-size:20px;
        background:${preset.header || "var(--app-header-background-color,var(--primary-color))"};
        color:${preset.header_text || "var(--app-header-text-color,var(--text-primary-color,#fff))"}}
      meal-planner-panel .wrap{max-width:1100px;margin:0 auto;padding:12px}
    </style><div class="bar"><ha-menu-button></ha-menu-button><span>Essensplaner</span></div><div class="wrap"></div>`;
    this._card = document.createElement("meal-planner-card");
    this._card.setConfig({ preset: cfg.preset || "system", title: "" });
    this.querySelector(".wrap").appendChild(this._card);
  }
  set hass(hass) {
    this._hass = hass;
    if (!this._card) this._build();
    const menu = this.querySelector("ha-menu-button");
    if (menu) { menu.hass = hass; menu.narrow = this._narrow; }
    this._card.hass = hass;
  }
  set narrow(n) { this._narrow = n; const m = this.querySelector("ha-menu-button"); if (m) m.narrow = n; }
  set panel(p) {
    const changed = this._panel && JSON.stringify(this._panel.config) !== JSON.stringify(p.config);
    this._panel = p;
    if (changed && this._hass) { this._card = null; this.hass = this._hass; }
  }
}

if (!customElements.get("meal-planner-card")) customElements.define("meal-planner-card", EssensplanerCard);
if (!customElements.get("meal-planner-panel")) customElements.define("meal-planner-panel", EssensplanerPanel);
if (!customElements.get("meal-planner-memory-card")) customElements.define("meal-planner-memory-card", EssensplanerMemoryCard);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "meal-planner-memory-card")) {
  window.customCards.push({ type: "meal-planner-memory-card", name: "Meal Planner AI: Gemerkt", description: "Geschmacksprofil und gespeicherte Rezepte ansehen, ändern, löschen" });
}
if (!window.customCards.some((c) => c.type === "meal-planner-card")) {
  window.customCards.push({ type: "meal-planner-card", name: "Meal Planner AI", description: "Vorschläge, Woche und Wünsche des Essensplaners" });
}
