# Meal Planner AI for Home Assistant

*Meal planner · weekly plan · recipes · shopping list · AI · Essensplaner · Wochenplan · Rezepte · Einkaufsliste*

[Deutsche Anleitung → README.de.md](README.de.md)

Meal Planner AI plans your week's dinners inside Home Assistant. Once a week an AI suggests dishes from real recipe
websites, your household picks what it wants on a dashboard card, and the ingredients land on the shopping list of
your choice (for example Bring!). Ratings, wishes and what you cooked recently feed into the next plan.

No extra app and no cloud service of its own: recipes are read straight from the recipe page with
[recipe-scrapers](https://github.com/hhursev/recipe-scrapers) (MIT) and stored locally in Home Assistant.

> **Status: early release, feedback wanted.** The integration runs daily in one household (Home Assistant 2026.11,
> German, Bring!, Gemini, Claude as external AI). Many combinations are not tested yet, see
> [What is tested](#what-is-tested). Please try it and report what works and what doesn't in the
> [issues](https://github.com/Pare51984/ha-meal-planner-ai/issues).

## Features
* Weekly suggestions at a time you choose, with a selection deadline and 1 to 7 shopping trips per week
  (each with its own name, cooking days and release time).
* Dashboard card with tiles per dish: choose a shopping trip, mark "ingredients at home", tick off cooked
  dishes, rate them with stars, add wishes. A timeline built from your settings shows when what happens.
* Shopping trips with a fixed time (e.g. Saturday 12:00) get a **Shop now** button for when you go earlier.
* Rules the integration checks itself: time limit, quick dishes per week, kcal per serving, vegetarian, vegan,
  lactose free, gluten free and low cholesterol counts, max dishes with the same main ingredient, habits in your own
  words, kitchen devices, calendar rules (e.g. "guest eats with us").
* Shopping list: amounts scaled to your servings, staples and spices left out, names mapped to your list's catalog
  (good for Bring!), per-dish tags so dishes can be removed again.
* Taste memory: profile text, ratings, cooking history; editable in the card (tabs "Taste profile" and "Recipes").
* Languages: German, English, Spanish, Portuguese, French.

## Installation
1. HACS → three dots → *Custom repositories* → add `https://github.com/Pare51984/ha-meal-planner-ai`
   as type *Integration*, then install **Meal Planner AI**. (Manual: copy `custom_components/meal_planner_ai`
   to `/config/custom_components/`.)
2. Restart Home Assistant.
3. Settings → Devices & services → Add integration → **Meal Planner AI**. Pick region, shopping list,
   kitchen devices, AI and where the card should appear.

All further settings are under **Configure** or in the card's **Settings** tab (admins only).

## AI options
The integration does the checking, importing and storing itself; the AI only proposes dishes.

| Option | What you need | Notes |
|---|---|---|
| **AI in Home Assistant** | An *AI Task* entity: Google Gemini, Anthropic (Claude) or OpenAI (ChatGPT) integration with an API key | Runs on schedule inside HA. |
| **Search agent with web search** (optional, recommended) | Pick a provider under *Create search agent with web search at* | Finds real recipe links, also Cookidoo. Gemini: free API key from Google AI Studio worked with `gemini-2.5-flash` in our test; newer models refused search on the free tier. Google returns redirect links, the integration resolves them. |
| **External AI** (subscription, no API key) | An AI with scheduled tasks and web search (e.g. Claude), connected to HA via MCP, plus remote access to HA | Tell the AI *"Set up my meal planner from Home Assistant."* It calls `meal_planner_ai.external_setup` and creates the task. If nothing arrives within 5 hours, the AI in HA takes over. |

For MCP you can use the official **Model Context Protocol Server** integration with the tool set **"Meal Planner AI"**
(it only allows fetching the brief and submitting proposals) or any MCP server that can call actions.

## Actions
All actions return response data. Most useful ones:

| Action | Purpose |
|---|---|
| `meal_planner_ai.import_recipe` | Load a recipe by link and store it |
| `meal_planner_ai.generate_proposals` | Create this week's suggestions now |
| `meal_planner_ai.planning_brief` / `submit_proposals` | Brief for an external AI and its answer |
| `meal_planner_ai.external_setup` | Schedule and task text for the external AI |
| `meal_planner_ai.choose_dish` / `set_ingredients_ready` / `mark_cooked` | What the card does |
| `meal_planner_ai.import_history` / `import_week` | Move over from another planner: history, ratings and the running week |
| `meal_planner_ai.memory_overview` / `set_profile` / `update_history` / `delete_recipe` | Taste memory |
| `meal_planner_ai.finalize_week` / `release_shopping` / `sync_shopping_list` | Schedule steps by hand |

Entities: `sensor.meal_planner_proposals`, `sensor.meal_planner_week` (attribute `dishes`),
`todo.meal_planner_wishes`, and `todo.meal_planner_shopping_list` if you use the built-in list.

## Card
The card `custom:meal-planner-card` is registered automatically. Display options: own sidebar page, a view in an
existing dashboard, or none (add the card yourself). Colors follow your theme; `preset: warm` gives a warm beige style.
Options: `title` (empty hides it), `help: false` hides the "How it works" column, single colors can be overridden
(`accent`, `tile`, `text`, `muted`, `star`, `radius`, …). `custom:meal-planner-memory-card` shows profile and recipes
on their own.

## What is tested
Tested live: Home Assistant 2026.11 on a Raspberry Pi 4, German, Bring! via the Bring! integration, Gemini as AI task and
search agent, Claude as external AI through a scheduled task with an MCP add-on, all display modes, migration from the
predecessor "Essensplaner". The automated tests (79) run against Home Assistant 2026.2.

**Not tested yet, testers welcome:**
* the official *Model Context Protocol Server* integration as the MCP path
* Claude (Anthropic) and ChatGPT (OpenAI) as AI task inside HA
* ChatGPT and Gemini scheduled tasks as external AI
* daily use in English, Spanish, Portuguese or French, and regions other than Germany
* shopping lists other than Bring! and the built-in list (Todoist, Google Tasks, local To-do, …)
* installation through HACS

## Notes
Diet classification (vegetarian, vegan, lactose/gluten free, devices) is based on keywords in ingredients and is not
perfect. "Low cholesterol" is judged by the AI. Please respect the terms of the recipe websites you enable.

## License
MIT
