"""
Pantry tools — deterministic helpers for comparing a recipe's ingredients
against the household's saved pantry.

These are plain functions (not an LLM agent). The Grocery Agent calls
compare_pantry_tool / load_pantry_tool to figure out what's already in the
pantry and what still needs buying.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pantry import list_pantry_items, normalize_item


# words that imply a distinct product when appended to a base ingredient
# (e.g. "tomato" vs "tomato paste" are different; "garlic" vs "garlic cloves" are not)
_QUALIFIERS = {"paste", "powder", "sauce", "oil", "flour", "extract",
               "dried", "fresh", "frozen", "canned", "smoked", "puree",
               "concentrate", "flakes", "juice"}


# ── Tool ──────────────────────────────────────────────────────────────────────

def load_pantry_tool(household_id: str = "default") -> list[dict]:
    """Load all pantry items from SQLite for a given household."""
    return list_pantry_items(household_id)


def _dedupe_ingredients(ingredients: list[str]) -> list[str]:
    """
    Collapse ingredients that refer to the same item — e.g. "garlic" and
    "garlic cloves", or "chicken" and "chicken breast".

    Two ingredients are treated as the same when one normalized name contains
    the other AND the leftover words are not product qualifiers (paste, sauce,
    oil, …) that would make them genuinely different items (tomato vs tomato
    paste stay separate). When merging, the shorter / more general name wins.
    Order is preserved.
    """
    kept: list[tuple[str, str]] = []   # (normalized, original display)
    for ing in ingredients:
        norm = normalize_item(ing)
        if not norm:
            continue
        merged = False
        for idx, (k_norm, _k_orig) in enumerate(kept):
            if k_norm == norm:
                merged = True
                break
            if k_norm in norm or norm in k_norm:
                extra = set(norm.split()) ^ set(k_norm.split())
                if not (extra & _QUALIFIERS):
                    merged = True
                    if len(norm) < len(k_norm):      # keep the more general name
                        kept[idx] = (norm, ing)
                    break
        if not merged:
            kept.append((norm, ing))
    return [orig for _, orig in kept]


def compare_pantry_tool(
    recipe_ingredients: list[str],
    pantry_items: list[dict],
) -> dict:
    """
    Fuzzy-match recipe ingredients against pantry items.

    Matching rules:
    - already_have: the pantry normalized name is a substring of the
      recipe ingredient (or vice versa), AND the extra words are not
      product qualifiers that imply a distinct item.
    - uncertain: partial overlap, but qualifier words (paste, sauce, powder…)
      suggest it might be a different product (e.g. tomato vs tomato paste).
    - missing: no pantry item matches at all.

    Quantity is ignored in MVP — pantry is treated as presence/absence.
    """
    pantry_norms = {p["normalized_name"]: p["item_name"] for p in pantry_items}

    # collapse near-duplicate ingredients (garlic / garlic cloves) up front so
    # the same item can't appear twice across already_have / missing
    recipe_ingredients = _dedupe_ingredients(recipe_ingredients)

    already_have:  list[str]  = []
    missing:       list[str]  = []
    uncertain:     list[dict] = []

    for ing in recipe_ingredients:
        ing_norm   = normalize_item(ing)
        matched    = False
        ambiguous: dict | None = None

        for p_norm, p_display in pantry_norms.items():
            if p_norm in ing_norm or ing_norm in p_norm:
                extra = set(ing_norm.split()) - set(p_norm.split())
                if extra & _QUALIFIERS:
                    ambiguous = {"recipe_ingredient": ing, "pantry_item": p_display}
                else:
                    already_have.append(ing)
                    matched = True
                    break

        if not matched:
            if ambiguous:
                uncertain.append(ambiguous)
            else:
                missing.append(ing)

    return {
        "already_have":        already_have,
        "missing_ingredients": missing,
        "uncertain_matches":   uncertain,
    }
