# FitFindr 🛍️

FitFindr is a multi-tool AI agent that helps you find secondhand clothing and figure out how
to wear it. You describe what you're after in plain language; a planning loop searches a mock
listings dataset, styles the top find against your wardrobe with an LLM, and writes a
shareable "fit card" caption — handling the messy cases (no matches, empty wardrobe, missing
outfit) gracefully along the way.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tools.py                   # The three required tools
├── agent.py                   # Planning loop + query parser + session state
├── app.py                     # Gradio UI
├── tests/test_tools.py        # pytest tests (one per failure mode + happy paths)
├── docs/failure_modes.md      # Triggered-failure evidence (Milestone 5)
├── planning.md                # The spec, written before any code
└── requirements.txt
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## Running It

```bash
python app.py          # launch the Gradio UI (open the URL printed in the terminal)
python agent.py        # run the happy path + no-results path from the CLI
pytest tests/          # run the tool unit tests
```

---

## Tool Inventory

All signatures below match `tools.py` exactly.

### `search_listings(description, size=None, max_price=None) → list[dict]`
- **Inputs:**
  - `description` (`str`) — keywords describing the desired item (e.g. `"vintage graphic tee"`).
  - `size` (`str | None`) — size to filter by; case-insensitive **substring** match (`"M"` matches `"S/M"`, `"M/L"`). `None` skips size filtering.
  - `max_price` (`float | None`) — inclusive price ceiling. `None` skips price filtering.
- **Output:** a `list[dict]` of full listing dicts (`id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`), sorted by keyword-overlap relevance (best first). Returns `[]` when nothing matches.
- **Purpose:** find candidate listings; pure Python (no LLM), so it's deterministic and fast.

### `suggest_outfit(new_item, wardrobe) → str`
- **Inputs:**
  - `new_item` (`dict`) — a listing dict (the top search result).
  - `wardrobe` (`dict`) — a wardrobe dict with an `items` list (each item has `name`, `category`, `colors`, `style_tags`, optional `notes`). May be empty.
- **Output:** a non-empty `str` of outfit advice. With a populated wardrobe it names specific owned pieces; with an empty wardrobe it gives general styling advice. Uses Groq `llama-3.3-70b-versatile` (temp 0.7).
- **Purpose:** style the found item against what the user already owns.

### `create_fit_card(outfit, new_item) → str`
- **Inputs:**
  - `outfit` (`str`) — the outfit suggestion from `suggest_outfit()`.
  - `new_item` (`dict`) — the listing dict (supplies title, price, platform).
- **Output:** a 2–4 sentence `str` caption (casual OOTD tone, mentions item/price/platform once each). Uses the LLM at **temp 0.9** so output varies across runs.
- **Purpose:** turn the outfit into something share-worthy.

---

## How the Planning Loop Works

The loop lives in `run_agent(query, wardrobe)` in `agent.py`. It is **data-driven** — it
does not call all three tools unconditionally; the search result decides the path.

1. **Parse** — `_parse_query()` extracts `description`, `size`, and `max_price` from the
   natural-language query with regex (a `$NN`/"under NN" cue → price; a `size X` phrase or a
   standalone size word → size; the remaining keywords → description, with era tags like
   `90s`/`y2k` preserved). Stored in `session["parsed"]`.
2. **Search** — calls `search_listings(...)` with the parsed params. **This is the decision
   point:**
   - **If the result list is empty** → set `session["error"]` to a specific, actionable
     message and `return` immediately. `suggest_outfit` and `create_fit_card` are never
     called.
   - **If there are matches** → set `session["selected_item"] = search_results[0]` and continue.
3. **Suggest** — calls `suggest_outfit(selected_item, wardrobe)`; result → `session["outfit_suggestion"]`.
4. **Fit card** — calls `create_fit_card(outfit_suggestion, selected_item)`; result → `session["fit_card"]`.
5. **Return** the completed session.

The agent is "done" when it either returns early on the empty-search branch or finishes the
fit card. (Query parsing is done in pure Python rather than via the LLM — a deliberate choice
for determinism and easy debugging; see Spec Reflection.)

## State Management Approach

A single `session` dict (built by `_new_session()`) is the one source of truth for an
interaction. It's created once and mutated in place as each step completes:

| Field | Written by | Read by |
|------|-----------|---------|
| `query` | init | parser |
| `parsed` | step 1 | step 2 (search) |
| `search_results` | step 2 | branch decision |
| `selected_item` | step 2 | steps 3 **and** 4 |
| `wardrobe` | init | step 3 |
| `outfit_suggestion` | step 3 | step 4 |
| `fit_card` | step 4 | UI |
| `error` | early-exit | UI |

The found item flows downstream without the user re-entering anything: `selected_item` is the
**same dict object** passed into both `suggest_outfit` and `create_fit_card`
(`search_results[0] is selected_item` → `True`), and `outfit_suggestion` is passed straight
into `create_fit_card`. `app.py`'s `handle_query()` reads the final session and maps it to the
three output panels.

---

## Interaction Walkthrough

**User query:** `vintage graphic tee under $30` (with the example wardrobe)

**Step 1 — Tool called: `search_listings`**
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0` (parsed from the query)
- Why this tool: the user is searching for an item, so the loop always starts here.
- Output: a non-empty ranked list; the top result is **"Y2K Baby Tee — Butterfly Print", $18, depop**. Results non-empty → `selected_item = results[0]`, proceed.

**Step 2 — Tool called: `suggest_outfit`**
- Input: `new_item=<Y2K Baby Tee dict>`, `wardrobe=<example wardrobe, 10 items>`
- Why this tool: an item was found and a wardrobe exists, so style the item against it.
- Output: *"...Pair it with your **Baggy straight-leg jeans** and **Chunky white sneakers** for a fun, casual look... Alternatively, layer the tee under your **Oversized grey crewneck sweatshirt** and pair with **Black combat boots**... tuck the tee into your jeans to add some definition."*

**Step 3 — Tool called: `create_fit_card`**
- Input: `outfit=<the suggestion above>`, `new_item=<Y2K Baby Tee dict>`
- Why this tool: an outfit suggestion exists, so generate the shareable caption.
- Output: *"just threw on my new y2k baby tee from depop ($18 steal, btw) and i'm feeling like a total 90s kid 😊. paired it with my fave baggy straight-leg jeans and chunky white sneakers... the butterfly print is giving me life 💖"*

**Final output to user:** three Gradio panels — the listing (title, $18, depop, condition, style), the outfit idea naming their own pieces, and the fit-card caption.

---

## Error Handling and Fail Points

See `docs/failure_modes.md` for the exact commands and full triggered output.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query | Returns `[]` (no exception). The loop sets `session["error"]` to a specific message and returns early — `suggest_outfit`/`create_fit_card` are skipped. **Concrete example:** `search_listings('designer ballgown', 'XXS', 5)` → `[]`; the full agent then reports *"No listings matched 'designer ballgown' in size XXS under $5. Try broader keywords, removing the size filter, or raising your max price."* and leaves `fit_card = None`. |
| `suggest_outfit` | Wardrobe is empty (`items == []`) | Branches to a "general styling advice" prompt instead of referencing nonexistent owned pieces; if the LLM call itself raises, it's caught and a non-empty fallback string is returned. **Concrete example:** with `get_empty_wardrobe()` it returned general advice (*"Pair it with a flowy skirt in a neutral shade... or high-waisted jeans and sneakers for a casual, everyday vibe..."*) rather than crashing. |
| `create_fit_card` | Outfit string missing/empty | Guards `if not outfit.strip()` and returns a descriptive error string; LLM exceptions fall back to a templated caption. **Concrete example:** `create_fit_card('', item)` → *"Can't write a fit card without an outfit suggestion — try styling the item first."* |

---

## Spec Reflection

**One way planning.md helped during implementation:**
Writing the error-handling table and the architecture diagram *before* coding forced me to
decide the empty-search branch was an early `return` from the planning loop, not something
each downstream tool had to defend against. Because that contract was settled on paper, the
`run_agent` implementation was a near-direct translation of the seven numbered steps, and I
never had to retrofit "what if search returned nothing" into `suggest_outfit`.

**One divergence from your spec, and why:**
The spec left query parsing open ("regex, string splitting, or the LLM"). I committed to pure
regex parsing in `_parse_query`, and during testing found two cases the spec hadn't
anticipated: era tags like `90s` were being mangled (the tokenizer dropped the digits, turning
`90s` into `s`, and the price regex ate the `90`). I added an alphanumeric tokenizer and a
word-boundary price regex so era/style tags survive — a refinement that only surfaced once I
ran real example queries through the parser.

---

## AI Usage

**1. Implementing `search_listings` (Milestone 3).**
I gave Claude the Tool 1 block from `planning.md` (inputs, return value, failure mode) plus the
listing field list, and asked it to implement the function using `load_listings()` with keyword
scoring, a substring size filter, and an inclusive price filter. I reviewed the result against
the spec before trusting it and verified it (a) filtered on all three params, (b) returned `[]`
(not an exception) for impossible queries, and (c) returned full listing dicts — then ran the
three pytest cases. I kept it essentially as generated; the spec was specific enough that no
override was needed.

**2. Implementing the planning loop `run_agent` (Milestone 4).**
I gave Claude the architecture diagram and the Planning Loop + State Management sections and
asked it to implement `run_agent` per the numbered TODOs in `agent.py`. The thing I **changed**
was the query parser: the first parse pass mangled era tags (`90s` → `s`), which I caught by
printing `_parse_query` output for the app's example queries. I overrode the tokenizer to keep
alphanumeric tokens (`[a-z0-9]+`) and split the price-stripping regex so digits inside words
survive. I also confirmed by hand that `search_results[0] is selected_item` (same object flows
downstream) rather than assuming the generated code passed state correctly.

---

## Where to Start (original starter notes)

1. Read `planning.md`.
2. Verify the data loads: `python utils/data_loader.py`.
3. Build and test each tool individually, then wire them through the planning loop.
