# Meal Planner AI – detailed guide

[Deutsche Fassung → anleitung.md](anleitung.md) · [Short overview → README](../README.md)

This guide explains how the meal planner works: what happens when, what the AI does and what the integration checks
itself, how to use the card and what each setting does.

## Contents
1. [The idea in one sentence](#1-the-idea-in-one-sentence)
2. [The week step by step](#2-the-week-step-by-step)
3. [Using the card](#3-using-the-card)
4. [Shopping list](#4-shopping-list)
5. [How suggestions are made and checked](#5-how-suggestions-are-made-and-checked)
6. [Choosing the AI](#6-choosing-the-ai)
7. [External AI via MCP](#7-external-ai-via-mcp)
8. [Taste, ratings and memory](#8-taste-ratings-and-memory)
9. [All settings explained](#9-all-settings-explained)
10. [Notifications](#10-notifications)
11. [Actions and entities for automations](#11-actions-and-entities-for-automations)
12. [Questions and problems](#12-questions-and-problems)

## 1. The idea in one sentence
Once a week an AI suggests dishes with real recipe links, the meal planner checks every dish itself, you pick in the
card, and the ingredients land on your shopping list at the right time.

The AI only makes suggestions. Fetching, checking, storing, the shopping list and the schedule are done by the
integration itself, locally in Home Assistant.

## 2. The week step by step
Example with the defaults: suggestions Friday 18:00, selection deadline Saturday 12:00, two shopping trips.

| When | What happens |
|---|---|
| until Friday 18:00 | You add meal wishes in the card (optional). |
| Friday 18:00 | The AI plans the coming week. This takes a few minutes. Then a push notification arrives and the card shows the **proposals for week …** as tiles. |
| Friday 18:00 to Saturday 12:00 | You pick a shopping trip per dish. Mark what you already have with "Have everything" or "Partly at home …". Remove unwanted suggestions with "✕ Remove". |
| Saturday 12:00 (deadline) | Unpicked dishes are dropped. The picked dishes become **This week**, the old week is archived. |
| fixed shopping time | The trip's ingredients go on the shopping list, minus what you marked as at home. |
| during the week | Tick off cooked dishes with the circle, rate them with stars if you like. Need one dish more? "More suggestions" adds five. |

**Carried over:** a dish of the running week that is not cooked yet but whose ingredients are at home is carried into
the next suggestions, already picked. If it gets cooked before the deadline, the copy is dropped.

**Restart or outage:** the meal planner checks hourly whether something is due and catches up on missed steps (e.g.
after a restart). If the AI fails, it tries up to three times and reports the error once by push.

## 3. Using the card
The card has up to four tabs. "Taste profile", "Recipes" and "Settings" are visible to administrators only.

### Sections of the "Meal plan" tab
| Section | Meaning |
|---|---|
| **Proposals week …** | The new suggestions for the coming week. Usually only visible between planning and deadline. |
| **This week** | Your picked dishes of the running week. |
| **To choose for this week** | Extra dishes from "More suggestions" during the week. They go on the list only once you tap a trip. |
| **Meal wishes** | Wishes for the next planning. |
| **How it works** | Short help and a timeline of what happens when. |

### Buttons on a tile
| Button | Effect |
|---|---|
| Trip (e.g. "Sat–Tue") | Assigns the dish to this trip. Tap again to deselect. Dashed = the planner's tip. |
| ✕ Remove | Only on unpicked suggestions: gone. "Undo" appears at the bottom. |
| Not after all | On picked dishes: deselect. If its ingredients are on the list already, they come off again. |
| Have everything | All ingredients are at home; nothing goes on the list (or it is removed). |
| Partly at home … | Tick single ingredients you have. Only the rest goes on the list. |
| Circle "cooked" | Saves the cooking day. The dish is not suggested again for 4 weeks, and the rating "How was it?" opens. |
| Stars, "+ Note" | Rating and note. Both feed into future suggestions. |

### More buttons
* **More suggestions:** adds five more dishes. Before the deadline they join the suggestions, during the week they appear under "To choose for this week".
* **Remove remaining suggestions:** clears all unpicked dishes under "To choose" at once (tap twice).
* **🛒 "Shop … now":** shown for fixed-time trips until their time is reached. Puts the ingredients on the list right away when you go shopping earlier (tap twice).
* **Plan suggestions now:** plans the coming week right away instead of at the scheduled time (tap twice).

### Meal wishes
A wish can be a dish ("lasagne"), an ingredient ("something with pumpkin") or a recipe link. The AI tries to include it
in the next planning. Fulfilled wishes disappear from the list, open ones stay for the next week. **Own recipe** means a
dish without a recipe from the web (e.g. grandma's goulash); you add its ingredients yourself.

## 4. Shopping list
* **Which list:** any to-do list in Home Assistant that accepts items, e.g. Bring!, or the meal planner's own list.
* **Format:** item name as the entry, amount and dish in the description (Bring! style). If an ingredient appears in several dishes, the amounts are combined in the same entry.
* **Amounts** are scaled to the servings you set.
* **Staples** (e.g. salt, oil) and, if you like, dried spices never go on the list.
* **Catalog names:** "passata = canned tomatoes" keeps an item's name on the list consistent.
* **AI item names** (optional): "1 red pepper, diced" becomes "Pepper".
* **When items go on the list:** each trip is either "Immediately" (when you tap) or "Fixed time" (on the chosen weekday and time). If you pick before that time and mark what you have, only the rest goes on the list. Dishes picked after that time go on right away. "Have everything" or "Partly at home" takes them off again afterwards.
* **Removing again:** every entry remembers which dish it belongs to. Deselect a dish and exactly its amounts disappear; other dishes stay untouched.

## 5. How suggestions are made and checked
1. **Request to the AI:** rules, diets, devices, habits, calendar events, taste profile, ratings, recently cooked dishes and open wishes. The AI is asked for a few more ideas than needed, because some fail the checks.
2. **Fetching the recipe:** every link is loaded and read with [recipe-scrapers](https://github.com/hhursev/recipe-scrapers): title, ingredients, time, nutrition. Only recipes that can be fetched are accepted.
3. **Replacement search:** if the link is missing, dead or leads to another dish, the meal planner searches the same dish on your enabled recipe sites itself. A result must have the same main ingredient, and a dish meant to be vegetarian is never replaced by one with meat or fish.
4. **Checking each dish:** maximum time, kcal limits, diets (vegetarian, vegan, lactose and gluten free are detected from the ingredients; low cholesterol is judged by the AI), kitchen devices, cooked in the last 4 weeks, poorly rated, duplicate.
5. **Weekly rules:** share of quick dishes, minimum counts per diet, maximum dishes with the same main ingredient, habits with "at most …x".
6. **Follow-up rounds:** if something is still missing, the AI is told what was rejected and why, and delivers more. It does not propose rejected dishes again.

The result is a board with as many dishes as set. If that is not reached, the push notification says what is missing.

## 6. Choosing the AI
Under **Settings → AI** you decide who plans.

| Field | Meaning |
|---|---|
| Who makes the suggestions? | "AI in Home Assistant" (normal case) or "External AI" (see section 7). |
| Main AI | An AI task entity (Gemini, Claude, ChatGPT …). Plans, judges "low cholesterol" and optionally simplifies item names. |
| Recipe search on the web | A conversation agent with web search. It finds real links, also on Cookidoo. Without an agent the main AI only names dishes and the meal planner searches itself (without Cookidoo). |
| Create search agent at | Creates an agent "Essensplaner Rezeptsuche (provider)" at the chosen provider. |

**The created search agent** gets the same basic settings for every provider: a current low-cost model (Gemini
`gemini-3.8-flash`, Claude `claude-haiku-5-5`, ChatGPT `gpt-6.1-terra`), web search on, 16000 maximum tokens and no
access to your home. You can change the model at any time in the provider's integration.

**Tip:** Gemini can be used for free with a key from Google AI Studio (with a quota). Claude and ChatGPT need an API
account with credit at the provider; this is separate from a chat subscription.

**Important for Claude with thinking:** *maximum tokens* must be well above the default of 3000, otherwise the answer
stays empty. The created agent has 16000.

## 7. External AI via MCP
Instead of an AI in Home Assistant, a scheduled task in an AI subscription can deliver the suggestions (tested with
Claude). The task fetches the brief via MCP (`planning_brief`), searches recipes and submits them (`submit_proposals`).
The meal planner checks them exactly as in section 5.

**Setup with the official "Model Context Protocol Server" integration:**
1. Settings → Devices & services → Add integration → **Model Context Protocol Server**.
2. Under **Configure**, switch **off** "all LLM APIs" and tick only **Meal Planner AI**. Otherwise the AI could also control your home through this access.
3. In your AI (e.g. Claude → Settings → Connectors) add a custom connector with `https://<your-ha-address>/api/mcp` and sign in with your Home Assistant account. Home Assistant must be reachable from the internet.
4. Tell the AI: "Set up my meal planner from Home Assistant." It creates the scheduled task. If that does not work, the card shows everything for manual setup under **Settings → Set up external AI**.

**What the external path does not cover:** "More suggestions", "Plan suggestions now", the AI diet assessment, AI item
names and the fallback need an AI *inside* Home Assistant. Tip: also select a free Gemini AI. If nothing arrives from
the external AI within five hours after the planning time, it steps in.

## 8. Taste, ratings and memory
* **Taste (free text):** sent with every planning, e.g. "like Mediterranean, no offal".
* Ratings go from **1 to 10 stars**. **Liked (7–10 stars)** is named to the AI as an example, **disliked (1–4 stars)** is not suggested again. Ratings from the 5-star days were doubled once by the update to 0.41.0 (4 of 5 is now 8 of 10).
* **Cooked in the last 4 weeks** is not suggested again. This is based on the "cooked" circle only.
* **"Taste profile" tab:** free text, liked, disliked, recently cooked. ✕ removes an entry.
* **"Recipes" tab:** all rated recipes with search, sorting, note and delete.

All data stays local in Home Assistant. It is removed when you delete the integration.

## 9. All settings explained
Available in the card under **Settings** or under Devices & services → Meal Planner AI → Configure.

| Section | What you set there |
|---|---|
| Language and region | Country of the recipes: decides recipe sites, language of dishes and items, Cookidoo country. The interface follows your Home Assistant profile. |
| Schedule and notifications | Weekday and time of the suggestions, selection deadline, who gets push notifications, which page opens when you tap one. |
| Shopping trips | Number of trips per week (1 to 7). Per trip: name (becomes the button), cooking days (hint for the AI), "Immediately" or "Fixed time". |
| Calendar | Up to three rules: calendars, optional keyword, meaning ("one more person", "only quick dishes"). Matching dishes get a label. |
| Rules and taste | Servings, maximum time, what counts as "quick" and how many quick dishes per week, taste, calorie aware (kcal per serving with and without side), variety of the main ingredient. |
| Eating habits | Up to five rules in your own words. With "at most …x" the integration counts itself. |
| Diet and suggestions per week | Number of suggestions. Per diet: off, always or a minimum count. |
| Shopping list | Target list, staples, leave out spices, catalog names. |
| Recipe sources | Which sites are used (on/off). Add your own site with an example recipe link; the integration checks it can read it. "Remove sites" removes own and built-in sites from the list; built-in ones can be brought back any time with "Restore removed sites". |
| Kitchen devices | Devices you have, optionally a minimum number of dishes per device. Thermomix recipes only with a Thermomix. |
| AI | See section 6. |
| Display | Own page in the sidebar, a view in a dashboard or none (add the card yourself). Colors like Home Assistant or "Warm". |

Changes apply to the whole household right away. If you change something while a planning run is going on, that run
finishes with the old values.

## 10. Notifications
Push notifications (to the devices chosen under "Schedule") are sent for:
* new suggestions, with the number of dishes, meat-free and low-cholesterol ones, fulfilled and open wishes, and what is missing,
* "Meal plan is set" after the deadline,
* AI errors (once a week) and when an external AI delivered nothing.

## 11. Actions and entities for automations
All actions return response data. The most useful ones:

| Action | Purpose |
|---|---|
| `meal_planner_ai.generate_proposals` | Create suggestions now (`force: true` plans again even if suggestions exist). |
| `meal_planner_ai.more_proposals` | More dishes to choose from. |
| `meal_planner_ai.choose_dish` | Pick a trip, deselect (`none`) or remove (`declined`). |
| `meal_planner_ai.set_ingredients_ready` / `set_items_at_home` | Ingredients fully or partly at home. |
| `meal_planner_ai.mark_cooked` | Cooked, with rating and note. |
| `meal_planner_ai.release_shopping` | Release a fixed-time trip now. |
| `meal_planner_ai.finalize_week` / `sync_shopping_list` | Deadline or list sync by hand. |
| `meal_planner_ai.import_recipe` / `get_recipe` / `list_recipes` / `delete_recipe` | Recipes. |
| `meal_planner_ai.import_week` | Import a week; an empty list with `board: next` discards the suggestions. |
| `meal_planner_ai.import_history` / `update_history` / `memory_overview` / `set_profile` | Memory. |
| `meal_planner_ai.planning_brief` / `submit_proposals` / `external_setup` | For an external AI. |

Entities: `sensor.meal_planner_proposals` (suggestions, attribute `dishes`), `sensor.meal_planner_week` (running week),
`todo.meal_planner_wishes` (wishes) and, with the built-in list, `todo.meal_planner_shopping_list`.

## 12. Questions and problems
**Fewer dishes than set.** The checks are strict. The push notification names common reasons, e.g. too few quick or
vegetarian dishes. Helps: enable more recipe sites, use a search agent with web search, relax rules.

**The AI reports an error or an empty answer.** For models with thinking, raise *maximum tokens* in the AI integration.
With Gemini on the free tier, error 429 means the quota is used up.

**A dish is wrongly marked vegetarian.** The classification is based on keywords in ingredients and title and is not
perfect. Please report it as an issue with the recipe link.

**The card is slow while planning.** During planning Home Assistant loads many recipe pages. On small hardware (e.g. a
Raspberry Pi) this can slow things down briefly.

**What does it cost?** The integration itself nothing. Costs only arise at the AI provider, depending on model and plan.

**Found a bug or have a wish?** Please open an [issue on GitHub](https://github.com/Pare51984/ha-meal-planner-ai/issues),
ideally with Home Assistant version, AI provider, shopping list and a log excerpt (`custom_components.meal_planner_ai`).
