"""
Clean and normalize raw Food.com recipes into analysis-ready documents.

Steps:
  1. Validate — drop rows missing critical fields
  2. Normalize ingredients — lowercase, strip quantities/punctuation
  3. Normalize steps + tags — strip HTML entities, deduplicate
  4. Extract allergen flags — embedding-based cosine similarity (not keyword matching)

Requires allergen_embeddings_cache.json to exist.
Build it once with: python -m ingestion.allergen_embedder

How to run:
cd ./allochef
python -m ingestion.cleaner

Output:
data/cleaned/recipes.jsonl
"""

import html
import json
import logging
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ALLERGEN_EMBEDDINGS_CACHE, CLEANED_RECIPES_JSONL, FOOD_COM_CSV
from ingestion.allergen_embedder import get_allergen_flags, load_cache
from ingestion.recipe_loader import load_recipe_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def is_valid(row: pd.Series) -> bool:
    """Drop recipes missing critical fields."""
    return (
        isinstance(row["name"], str) and bool(row["name"].strip())
        and isinstance(row["ingredients"], list) and len(row["ingredients"]) >= 2
        and isinstance(row["steps"], list) and len(row["steps"]) >= 1
    )


def normalize_ingredient(ingredient: str) -> str:
    """Lowercase, strip leading quantities, remove trailing punctuation."""
    ingredient = ingredient.lower().strip()
    ingredient = re.sub(r"^\d[\d\s/\.]*", "", ingredient)   # strip leading quantities
    ingredient = re.sub(r"\s+", " ", ingredient)             # collapse whitespace
    ingredient = ingredient.rstrip(".,;:")
    return ingredient.strip()


def normalize_step(step: str) -> str:
    """Decode HTML entities, strip boilerplate, collapse whitespace."""
    step = html.unescape(step)
    step = re.sub(r"\s+", " ", step).strip()
    return step


def normalize_tags(tags: list[str]) -> list[str]:
    """Lowercase, normalize separators, deduplicate."""
    seen = set()
    result = []
    for tag in tags:
        normalized = tag.lower().strip().replace(" ", "-")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def clean_recipe(
    row: pd.Series,
    ingredient_cache: dict,
    allergen_embeddings: dict,
) -> dict | None:
    """Transform a raw recipe row into a clean document. Returns None if invalid."""
    if not is_valid(row):
        return None

    ingredients = [
        normalize_ingredient(i) for i in row["ingredients"] if str(i).strip()
    ]
    steps = [
        normalize_step(s) for s in row["steps"] if str(s).strip()
    ]
    steps = [s for s in steps if len(s) > 5]

    if not ingredients or not steps:
        return None

    allergen_flags = get_allergen_flags(ingredients, ingredient_cache, allergen_embeddings)

    return {
        "id":          str(row["id"]),
        "name":        row["name"].strip(),
        "description": normalize_step(str(row.get("description", "") or "")),
        "ingredients": ingredients,
        "steps":       steps,
        "tags":        normalize_tags(row.get("tags") or []),
        "minutes":     row.get("minutes", ""),
        **allergen_flags,
    }


def run(sample: int = 0):
    """
    Clean the full dataset and write to JSONL.
    If sample > 0, print that many cleaned recipes to stdout instead.
    """
    df = load_recipe_data(FOOD_COM_CSV)
    ingredient_cache, allergen_embeddings = load_cache(ALLERGEN_EMBEDDINGS_CACHE)
    logger.info(f"Loaded embedding cache: {len(ingredient_cache):,} ingredients, {len(allergen_embeddings)} allergens")

    CLEANED_RECIPES_JSONL.parent.mkdir(parents=True, exist_ok=True)

    total = skipped = 0

    with open(CLEANED_RECIPES_JSONL, "w", encoding="utf-8") as out:
        for _, row in df.iterrows():
            total += 1
            cleaned = clean_recipe(row, ingredient_cache, allergen_embeddings)

            if cleaned is None:
                skipped += 1
                continue

            out.write(json.dumps(cleaned) + "\n")

            if sample and (total - skipped) <= sample:
                print(f"\n{'─' * 60}")
                print(f"NAME: {cleaned['name']}")
                print(f"INGREDIENTS ({len(cleaned['ingredients'])}): {cleaned['ingredients'][:4]}")
                print(f"STEPS: {len(cleaned['steps'])} total | first: {cleaned['steps'][0][:80]}")
                print(f"TAGS: {cleaned['tags'][:5]}")
                flags = [k for k, v in cleaned.items() if k.startswith("contains_") and v]
                print(f"ALLERGENS: {flags if flags else 'none detected'}")

    logger.info(f"Done — {total} rows | {total - skipped} cleaned | {skipped} skipped")
    logger.info(f"Output: {CLEANED_RECIPES_JSONL}")


if __name__ == "__main__":
    run(sample=20)
