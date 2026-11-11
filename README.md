# Meal Planner AI for Home Assistant

*Meal planner · weekly plan · recipes · shopping list · AI · Essensplaner · Wochenplan · Rezepte · Einkaufsliste*

[Deutsche Anleitung → README.de.md](README.de.md) · 📖 [Detailed guide: how it works](docs/guide.md)

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
* **More suggestions** adds 5 more dishes to pick from at any time (also during the week, when you need one dish more).
  Don't want a dish? **Remove** it (a picked dish: **Not after all**, its ingredients come off the list) and pick a new one.
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
| **Search agent with web search** (optional, recommended) | Pick a provider under *Create search agent with web search at* | Finds real recipe links, also Cookidoo. Every provider gets the same treatment: a current low-cost model (Gemini `gemini-3.8-flash`, Claude `claude-haiku-5-5`, ChatGPT `gpt-6.1-terra`), web search on, 16000 maximum tokens, no access to your home; you can change the model in the agent. Gemini: a free API key from Google AI Studio works; in our test (11/2026) `gemini-3.8-flash` searched fine on the free tier at no cost (older test: `gemini-3.1-flash-lite` refused search there). The free tier has rate limits; if Google answers 429, the integration falls back to its own search. Google returns redirect links, the integration resolves them. |
| **External AI** (subscription, no API key) | An AI with scheduled tasks and web search (e.g. Claude), connected to HA via MCP, plus remote access to HA | Tell the AI *"Set up my meal planner from Home Assistant."* It calls `meal_planner_ai.external_setup` and creates the task. If nothing arrives within 5 hours, the AI in HA takes over. |

For MCP you can use the official **Model Context Protocol Server** integration or any MCP server that can call actions.
Setup with the official integration:
1. Settings → Devices & services → Add integration → **Model Context Protocol Server**.
2. Under **Configure**, switch **off** "all LLM APIs" and tick only **Meal Planner AI**. Then the AI can only fetch the
   brief and submit proposals. With all LLM APIs it could also control your home.
3. In your AI (e.g. Claude → Settings → Connectors) add a custom connector with `https://<your-ha-address>/api/mcp`
   and sign in with your Home Assistant account. Your HA must be reachable from the internet.

**Limits of the external AI path.** The external AI only delivers the weekly suggestions at the scheduled time. Everything
that needs new dishes in between runs on the AI *inside* Home Assistant. Without an AI task selected under
**Configure → AI**, these do not work: **More suggestions**, **Plan suggestions now** (`generate_proposals`),
`assess_recipes`, AI shopping names, and the fallback when the external AI delivers nothing. Tip: also select a free
Gemini AI task, then these work too and the external AI still does the weekly plan.

## Actions
All actions return response data. Most useful ones:

| Action | Purpose |
|---|---|
| `meal_planner_ai.import_recipe` | Load a recipe by link and store it |
| `meal_planner_ai.generate_proposals` | Create this week's suggestions now |
| `meal_planner_ai.more_proposals` | Add more dishes to choose from |
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
predecessor "Essensplaner". The automated tests (95) run against Home Assistant 2026.2.

Test runs with the AI task and search agent (11/2026, default settings otherwise):

| Model | Result |
|---|---|
| Gemini `gemini-3.8-flash` | in daily use (main AI and search agent) |
| OpenAI `gpt-6.1-terra` | 10 dishes, most links found by the AI itself, about 1.5 minutes |
| OpenAI `gpt-6.1-sol` | 10 dishes, fewer own links, about 5 minutes |
| Claude Sonnet 5.5 | with the default *maximum tokens* (3000): 7 dishes, no own links (all found by the integration's search) |
| Claude Haiku 5.5 | with the default *maximum tokens* (3000): failed, thinking used them up. With the search agent the integration creates (16000): 10 dishes, few own links, about 8 minutes. |

The official *Model Context Protocol Server* integration works as the MCP path: added as a custom connector in Claude
(`https://<your-ha>/api/mcp`), sign-in with the Home Assistant account, brief fetched (11/2026).

**Not tested yet, testers welcome:**
* ChatGPT and Gemini scheduled tasks as external AI
* daily use in English, Spanish, Portuguese or French, and regions other than Germany
* shopping lists other than Bring! and the built-in list (Todoist, Google Tasks, local To-do, …)

## Notes
Diet classification (vegetarian, vegan, lactose/gluten free, devices) is based on keywords in ingredients and is not
perfect. "Low cholesterol" is judged by the AI. Please respect the terms of the recipe websites you enable.

## License
MIT
