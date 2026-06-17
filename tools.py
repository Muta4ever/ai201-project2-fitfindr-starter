"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Tokenize the description into lowercase keywords.
    keywords = [w for w in description.lower().split() if w]

    results = []
    for item in listings:
        # --- Price filter (inclusive) ---
        if max_price is not None and item["price"] > max_price:
            continue

        # --- Size filter (case-insensitive substring match) ---
        # e.g. "M" matches "S/M", "M/L"; "8" matches "US 8".
        if size is not None and size.strip():
            if size.strip().lower() not in item["size"].lower():
                continue

        # --- Relevance score: keyword overlap with title / description / tags ---
        haystack = " ".join(
            [item["title"], item["description"], " ".join(item["style_tags"])]
        ).lower()
        score = sum(1 for kw in keywords if kw in haystack)

        # Drop items with no keyword match at all.
        if score == 0:
            continue

        results.append((score, item))

    # Sort by score, highest first. Returns [] when nothing matched.
    results.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    item_desc = (
        f"{new_item.get('title', 'this item')} "
        f"(category: {new_item.get('category', 'unknown')}, "
        f"colors: {', '.join(new_item.get('colors', [])) or 'n/a'}, "
        f"style: {', '.join(new_item.get('style_tags', [])) or 'n/a'})"
    )

    items = wardrobe.get("items", [])

    if not items:
        # --- Empty-wardrobe branch: general styling advice, no owned pieces. ---
        prompt = (
            f"A shopper is considering buying this secondhand item: {item_desc}.\n"
            "They have NOT entered any wardrobe yet, so do not reference specific "
            "pieces they own. Suggest 1-2 complete outfit ideas in general terms: "
            "what categories, colors, and silhouettes pair well with it, and what "
            "overall vibe it suits. Keep it to 3-4 sentences, friendly and concrete."
        )
    else:
        # --- Populated-wardrobe branch: name specific owned pieces. ---
        wardrobe_lines = "\n".join(
            f"- {it['name']} ({it.get('category', '')}; "
            f"{', '.join(it.get('colors', []))}; "
            f"{', '.join(it.get('style_tags', []))})"
            for it in items
        )
        prompt = (
            f"A shopper is considering buying this secondhand item: {item_desc}.\n\n"
            f"Here is their current wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfit combinations that style the new item with "
            "SPECIFIC pieces from their wardrobe (name them). Mention how to wear it "
            "(layering, tucking, etc.) where useful. Keep it to 3-5 sentences, "
            "friendly and concrete."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a sharp, encouraging personal stylist who "
                    "gives specific, wearable outfit advice.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # Never crash the agent — return a usable fallback string.
        return (
            f"Couldn't reach the styling model ({e.__class__.__name__}). "
            f"As a starting point, {new_item.get('title', 'this piece')} works well "
            f"with simple basics in neutral colors — build the rest of the outfit "
            f"around its {', '.join(new_item.get('style_tags', [])) or 'overall'} vibe."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # --- Guard: no outfit to caption. ---
    if not outfit or not outfit.strip():
        return (
            "Can't write a fit card without an outfit suggestion — "
            "try styling the item first."
        )

    title = new_item.get("title", "this piece")
    price = new_item.get("price")
    platform = new_item.get("platform", "secondhand")
    price_str = f"${price:.0f}" if isinstance(price, (int, float)) else "a steal"

    prompt = (
        f"Write a short, shareable outfit caption (like a real Instagram/TikTok "
        f"OOTD post — casual, a little playful, NOT a product description).\n\n"
        f"Item: {title}\n"
        f"Price: {price_str}\n"
        f"Platform: {platform}\n"
        f"Outfit being worn: {outfit}\n\n"
        "Rules: 2-4 sentences. Mention the item name, the price, and the platform "
        "naturally, once each. Capture the outfit's specific vibe. Lowercase-casual "
        "is fine. An emoji or two is fine. Make it sound like a real person posting."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You write punchy, authentic social-media outfit "
                    "captions that sound like a real person, never an ad.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.9,  # high temperature → varied output across runs
        )
        return response.choices[0].message.content.strip()
    except Exception:
        # Fallback caption built from the item fields — never raises.
        return (
            f"thrifted this {title.lower()} off {platform} for {price_str} and "
            f"i'm obsessed 🛍️ styled it exactly how i wanted. full fit in stories!"
        )
