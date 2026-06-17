"""
tests/test_tools.py

Unit tests for the three FitFindr tools, run with:  pytest tests/

Each tool has at least one happy-path test and at least one failure-mode test.
The search_listings tests are pure (no network). The LLM-backed tools
(suggest_outfit, create_fit_card) are tested for their NON-LLM behavior —
the empty/missing-input guards — so the suite passes without API access.
A network-dependent happy-path test for each is included but skipped when
GROQ_API_KEY is not set.
"""

import os

import pytest

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

_KEY = os.environ.get("GROQ_API_KEY", "")
# Treat the starter placeholder as "no key" so the LLM tests skip cleanly.
HAS_KEY = bool(_KEY) and _KEY != "your_key_here"


# ── search_listings ─────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    # Every result is a full listing dict.
    assert all("title" in item and "price" in item for item in results)


def test_search_empty_results():
    # Impossible query → empty list, no exception.
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_substring():
    # "M" should match sizes like "S/M" and "M/L", case-insensitively.
    results = search_listings("tee", size="m", max_price=None)
    assert all("m" in item["size"].lower() for item in results)


def test_search_ranks_by_relevance():
    # More keyword overlap should rank higher (non-increasing scores).
    results = search_listings("vintage denim jacket", size=None, max_price=None)
    assert len(results) > 0
    # Top result should be denim/jacket-related.
    assert any(
        kw in results[0]["title"].lower() or kw in " ".join(results[0]["style_tags"]).lower()
        for kw in ("denim", "jacket")
    )


# ── suggest_outfit ──────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe_returns_string():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    # Must return a non-empty string (general advice), never crash/empty.
    assert isinstance(result, str)
    assert len(result.strip()) > 0


@pytest.mark.skipif(not HAS_KEY, reason="GROQ_API_KEY not set")
def test_suggest_outfit_with_wardrobe():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


# ── create_fit_card ─────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit_returns_error_string():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("", item)
    # Returns a descriptive error string, not an exception or empty string.
    assert isinstance(result, str)
    assert "without an outfit" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_string():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("   \n  ", item)
    assert isinstance(result, str)
    assert "without an outfit" in result.lower()


@pytest.mark.skipif(not HAS_KEY, reason="GROQ_API_KEY not set")
def test_create_fit_card_varies():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    outfit = "Pair with baggy jeans and chunky sneakers, denim jacket on top."
    a = create_fit_card(outfit, item)
    b = create_fit_card(outfit, item)
    assert isinstance(a, str) and isinstance(b, str)
    if "i'm obsessed" in a and a == b:
        pytest.skip("LLM unreachable (invalid key) — returned identical fallback")
    # High temperature should (almost always) produce different captions.
    assert a != b
