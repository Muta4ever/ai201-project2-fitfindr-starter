# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset (40 secondhand items loaded via `load_listings()`) for pieces matching the user's keywords, optionally filtered by size and a price ceiling, and returns the matches ranked by how relevant they are to the keywords.

**Input parameters:**
- `description` (str): Free-text keywords describing what the user wants, e.g. `"vintage graphic tee"`. Tokenized into lowercase words; each word is matched against each listing's `title`, `description`, and `style_tags`.
- `size` (str | None): A size string to filter by, e.g. `"M"`. Matching is case-insensitive and substring-based so `"M"` matches `"S/M"` and `"M/L"`. `None` skips size filtering entirely.
- `max_price` (float | None): Inclusive price ceiling — only listings with `price <= max_price` survive. `None` skips price filtering.

**What it returns:**
A `list[dict]` of matching listings, sorted by relevance score (highest first). Each dict is a full listing with the fields: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`. Returns `[]` (empty list) when nothing matches — never raises.

**What happens if it fails or returns nothing:**
Returns an empty list rather than raising. The planning loop detects the empty list and sets `session["error"]` to a specific, actionable message (e.g. "No listings matched 'designer ballgown' in size XXS under $5. Try removing the size filter, raising your max price, or using broader keywords.") and returns early — it does **not** call `suggest_outfit` with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific thrifted item and the user's wardrobe, calls the Groq LLM (`llama-3.3-70b-versatile`) to suggest one or two complete, wearable outfit combinations that style the new item with named pieces the user already owns.

**Input parameters:**
- `new_item` (dict): A single listing dict (typically `session["selected_item"]`, the top search result). The tool uses its `title`, `category`, `colors`, and `style_tags` to ground the suggestion.
- `wardrobe` (dict): A wardrobe dict with an `items` key holding a list of wardrobe item dicts (each has `name`, `category`, `colors`, `style_tags`, optional `notes`). May be empty (`{"items": []}`) — handled explicitly.

**What it returns:**
A non-empty `str` of natural-language outfit advice. With a populated wardrobe it names specific owned pieces ("pair with your baggy dark-wash jeans and chunky white sneakers..."). With an empty wardrobe it returns general styling advice (what categories/colors pair well, what vibe the item suits) instead of referencing nonexistent items.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool branches to a "general styling advice" prompt rather than crashing. If the LLM call raises (network/API error), the tool catches the exception and returns a friendly fallback string describing the item generically so the workflow can still continue to the fit card.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, casual, shareable outfit caption — the kind of thing someone posts with an OOTD photo — from the outfit suggestion and the item details, using the LLM at a higher temperature so the output varies across runs and inputs.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit()` (`session["outfit_suggestion"]`).
- `new_item` (dict): The listing dict for the thrifted item — supplies `title`, `price`, and `platform` to weave into the caption once each.

**What it returns:**
A 2–4 sentence `str` usable as an Instagram/TikTok caption: casual tone, mentions the item name, price, and platform naturally, captures the outfit vibe, and reads differently each run (temperature ≈ 0.9).

**What happens if it fails or returns nothing:**
Guards against an empty/whitespace-only `outfit` string by returning a descriptive error message string ("Can't write a fit card without an outfit suggestion — try styling the item first.") rather than raising. If the LLM call raises, it catches and returns a plain fallback caption built from the item fields.

---

### Additional Tools (if any)

None for the required build. (Stretch candidate: `compare_price(new_item)` to estimate whether a listing's price is fair against comparable items in the dataset — will be added to this section before that stretch feature is started.)

---

## Planning Loop

**How does your agent decide which tool to call next?**

The loop lives in `run_agent(query, wardrobe)` and is driven by what each step returns, stored in a single `session` dict. The branches are:

1. **Parse.** Extract `description`, `size`, and `max_price` from the natural-language `query` (regex for `$NN` and a size token like `size M`; remaining words become the description). Store in `session["parsed"]`.
2. **Search.** Call `search_listings(description, size, max_price)`; store in `session["search_results"]`.
   - **Branch A — empty results:** if `len(search_results) == 0`, set `session["error"]` to a specific message and `return session` immediately. `selected_item`, `outfit_suggestion`, and `fit_card` stay `None`. The loop ends here.
   - **Branch B — matches found:** set `session["selected_item"] = search_results[0]` (top-ranked) and continue.
3. **Suggest.** Call `suggest_outfit(selected_item, wardrobe)`; store in `session["outfit_suggestion"]`. The empty-wardrobe case is handled inside the tool (general advice), so the loop proceeds either way — but the *content* differs based on whether the wardrobe has items.
4. **Fit card.** Call `create_fit_card(outfit_suggestion, selected_item)`; store in `session["fit_card"]`.
5. **Done.** `return session`.

The agent is "done" when it either returns early on the empty-search branch or completes step 4. It does **not** call all three tools unconditionally: when search returns nothing, tools 2 and 3 are never called. Behavior is therefore a function of the data, not a fixed script.

---

## State Management

**How does information from one tool get passed to the next?**

A single `session` dict (created by `_new_session()`) is the one source of truth for an interaction. It is created once at the start of `run_agent` and mutated in place as each step completes. Key fields:

- `query` — the raw user input (set at init).
- `parsed` — `{description, size, max_price}` extracted in step 1.
- `search_results` — list returned by `search_listings`.
- `selected_item` — `search_results[0]`; the **exact same dict** is passed into `suggest_outfit` and `create_fit_card`, so the found item flows downstream without the user re-entering anything.
- `wardrobe` — passed in at init, read by `suggest_outfit`.
- `outfit_suggestion` — string from `suggest_outfit`; passed directly into `create_fit_card`.
- `fit_card` — final string from `create_fit_card`.
- `error` — `None` normally; set to a message string when the loop terminates early.

Data flows tool→tool purely through these fields: `selected_item` is written by step 2 and read by steps 3 and 4; `outfit_suggestion` is written by step 3 and read by step 4. `run_agent` returns the completed `session`, and `app.py`'s `handle_query()` reads `error`, `selected_item`, `outfit_suggestion`, and `fit_card` from it to populate the three UI panels.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Tool returns `[]`. Loop sets `session["error"]` = "No listings matched '<keywords>'[ in size <size>][ under $<price>]. Try broader keywords, removing the size filter, or raising your max price." and returns early — `suggest_outfit`/`create_fit_card` are never called. UI shows the message in the listing panel; outfit and fit-card panels stay empty. |
| suggest_outfit | Wardrobe is empty (`items == []`) | Tool detects the empty list and calls the LLM with a "general styling advice" prompt instead — returns wearable, item-specific guidance ("this band tee suits a relaxed grunge look; pair with baggy bottoms and chunky boots, layer under an open flannel") without referencing owned pieces that don't exist. If the LLM call itself errors, it catches and returns a generic, non-empty fallback string. |
| create_fit_card | Outfit input is missing or incomplete | Tool checks `if not outfit or not outfit.strip()` and returns the string "Can't write a fit card without an outfit suggestion — try styling the item first." instead of raising. If the LLM errors, it catches and returns a simple template caption built from the item's title/price/platform. |

---

## Architecture

```
                          User query (text)  +  wardrobe choice
                                     │
                                     ▼
                        ┌─────────────────────────┐
                        │   run_agent(query,       │
                        │            wardrobe)     │
                        │   _new_session() ──► session dict
                        └─────────────────────────┘
                                     │
                          (1) parse query → session["parsed"]
                                     │ {description, size, max_price}
                                     ▼
        ┌──────────► (2) search_listings(description, size, max_price)
        │                            │
        │                            ├── results == []  ──► [ERROR]
        │                            │      session["error"] = "No listings..."
        │                            │      return session ─────────────────┐
        │                            │                                       │
        │                            │ results == [item, ...]                │
        │                            ▼                                       │
        │            session["selected_item"] = results[0]                  │
        │                            │                                       │
        │              (3) suggest_outfit(selected_item, wardrobe)          │
        │                            │   (empty wardrobe → general advice)  │
        │                            ▼                                       │
        │            session["outfit_suggestion"] = "..."                   │
        │                            │                                       │
        │              (4) create_fit_card(outfit_suggestion, selected_item)│
        │                            │   (empty outfit → error string)      │
        │                            ▼                                       │
        │            session["fit_card"] = "..."                            │
        │                            │                                       │
        └────────────────────────────┴──────── return session ◄────────────┘
                                     │
                                     ▼
                handle_query() in app.py reads session and fills:
          ┌────────────────┬────────────────────┬──────────────────┐
          │ 🛍️ Top listing │ 👗 Outfit idea     │ ✨ Fit card      │
          │ selected_item   │ outfit_suggestion  │ fit_card         │
          │ (or error msg)  │ (empty on error)   │ (empty on error) │
          └────────────────┴────────────────────┴──────────────────┘

  Session dict is the shared state read/written at every numbered step.
  Error branch from step (2) terminates the flow early — steps (3)/(4) are skipped.
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

I'll use **Claude (Claude Code)**, one tool at a time.
- **search_listings:** I'll paste the Tool 1 block (inputs, return value, failure mode) plus the listings field list and ask Claude to implement it using `load_listings()` — keyword tokenization scored against `title`/`description`/`style_tags`, substring size match, inclusive price filter, score-0 dropped, sorted descending. **Verify before trusting:** confirm it (a) filters on all three params, (b) returns `[]` (not an exception) for impossible queries, (c) returns full listing dicts. Then run the three pytest cases (results, empty, price filter).
- **suggest_outfit:** I'll give Claude the Tool 2 block and the wardrobe schema, and ask it to branch on `wardrobe["items"]` being empty and call Groq `llama-3.3-70b-versatile`. **Verify:** check the empty-wardrobe branch exists and that an API exception is caught; test with `get_example_wardrobe()` and `get_empty_wardrobe()`.
- **create_fit_card:** I'll give Claude the Tool 3 block and ask for the empty-outfit guard + a high-temperature (≈0.9) Groq call. **Verify:** run it 3× on the same input and confirm outputs differ; pass `""` as outfit and confirm it returns the error string, not an exception.

**Milestone 4 — Planning loop and state management:**

I'll give **Claude** the full **Architecture diagram** plus the **Planning Loop** and **State Management** sections of this file, and ask it to implement `run_agent()` per the numbered TODO steps in `agent.py`. **Verify before trusting:** confirm the code (a) branches on `search_results` being empty and `return`s early there, (b) writes each result into the `session` dict and reads `selected_item`/`outfit_suggestion` from it (no re-calling search or hardcoded values), and (c) does **not** call `suggest_outfit`/`create_fit_card` on the empty-search path. I'll then run `python agent.py` and check both the happy path and the no-results path, printing `session["selected_item"]` to confirm the same dict flows into `suggest_outfit`.

---

## A Complete Interaction (Step by Step)

**What FitFindr does (in my own words):** FitFindr is a multi-tool agent that takes a natural-language thrifting request and runs it through a planning loop that decides which tool to call based on what each step returns. A search request triggers `search_listings` to filter the mock listings dataset; if at least one match comes back, the top result flows into `suggest_outfit` (which pairs it against the user's wardrobe via the LLM), and that suggestion plus the item flow into `create_fit_card` to generate a shareable caption. If any step fails — no listings match, an empty wardrobe, or a missing outfit — the agent stops at that point and tells the user what went wrong and what to try next, rather than calling the next tool with empty input or crashing.

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
`run_agent` initializes the session and parses the query → `parsed = {description: "vintage graphic tee", size: None, max_price: 30.0}`. It then calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. Scoring against `title`/`description`/`style_tags` surfaces graphic-tee listings under $30 — e.g. `lst_006` ("Graphic Tee — 2003 Tour Bootleg Style", $24, depop), `lst_033` ("Vintage Band Tee — Faded Grey", $19), `lst_002` ("Y2K Baby Tee", $18). Results are non-empty, so `session["selected_item"] = results[0]` (the top-scored tee, e.g. `lst_006`).

**Step 2:**
With `selected_item` set, the loop calls `suggest_outfit(selected_item, wardrobe)` where `wardrobe = get_example_wardrobe()` (baggy jeans, chunky white sneakers, black denim jacket, etc.). The LLM returns something like: "Pair this faded bootleg tee with your baggy dark-wash jeans and chunky white sneakers for an easy 90s streetwear look. Throw the vintage black denim jacket over it and add the brown leather belt for a little structure." Stored in `session["outfit_suggestion"]`.

**Step 3:**
The loop calls `create_fit_card(outfit_suggestion, selected_item)`. With temperature ≈0.9 the LLM returns a caption like: "found this 2003 bootleg tee on depop for $24 and it's already my whole personality 🖤 styled it with my baggy jeans + chunky sneakers, denim jacket on top. full fit in stories." Stored in `session["fit_card"]`. The loop returns the session.

**Final output to user:**
The Gradio UI fills three panels — 🛍️ the chosen listing (title, $24, depop, condition), 👗 the outfit idea naming their baggy jeans / chunky sneakers / denim jacket, and ✨ the shareable fit card caption. On the error path (e.g. the "designer ballgown size XXS under $5" query), only the first panel shows: "No listings matched 'designer ballgown' in size XXS under $5. Try broader keywords, removing the size filter, or raising your max price." — and the outfit and fit-card panels stay empty.
