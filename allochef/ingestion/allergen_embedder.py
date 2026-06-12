"""
Embedding-based allergen detection for recipe ingredients.

Instead of keyword matching, embeds each unique ingredient once and computes
cosine similarity against allergen reference descriptions. More accurate than
keyword matching — correctly handles cases like:
  "peanut butter" → peanuts (not milk)
  "almond milk"   → tree_nuts (not milk)
  "tahini"        → sesame (even if not in keyword vocab)
  "ghee"          → milk (knows it's clarified butter)

Run once to build the cache, then cleaner.py uses it for free:
    python -m ingestion.allergen_embedder

Output: data/cleaned/allergen_embeddings_cache.json
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
from openai import OpenAI
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ALLERGEN_EMBEDDINGS_CACHE, FOOD_COM_CSV
from ingestion.recipe_loader import load_recipe_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Prototypical ingredient examples per allergen.
# Multiple examples per allergen are used — the max similarity across all examples is taken.
# This is more discriminative than a single reference description.
# All entries must be ingredient strings that exist in the Food.com dataset
# so they are already embedded in allergen_embeddings_cache.json.
ALLERGEN_EXAMPLES: dict[str, list[str]] = {
    "milk":      ["milk", "butter", "cream", "cheese", "yogurt", "whey", "casein", "lactose",
                  "cream cheese", "sour cream", "heavy cream", "buttermilk",
                  "mozzarella", "cheddar", "parmesan", "brie"],
    "eggs":      ["egg", "eggs", "egg whites", "egg yolk", "beaten egg", "large eggs"],
    "fish":      ["fish", "salmon", "tuna", "cod", "anchovy", "sardine", "pollock", "tilapia",
                  "halibut", "trout", "catfish", "mackerel", "anchovies", "bass"],
    "shellfish": ["shrimp", "crab", "lobster", "oyster", "scallop", "clam", "mussel",
                  "prawns", "squid", "calamari"],
    "tree_nuts": ["almonds", "walnuts", "cashews", "pecans", "hazelnuts", "pistachios",
                  "macadamia", "almond", "walnut", "cashew", "pine nuts"],
    "peanuts":   ["peanuts", "peanut butter", "peanut oil", "peanut", "groundnut"],
    "wheat":     ["flour", "wheat", "semolina", "whole wheat flour", "bread flour",
                  "all-purpose flour", "pasta", "bread", "couscous", "bulgur"],
    "gluten":    ["barley", "rye", "wheat", "malt", "spelt"],
    "soy":       ["soy sauce", "tofu", "soybeans", "miso", "tempeh", "edamame",
                  "soy milk", "tamari"],
    "sesame":    ["sesame", "tahini", "sesame seeds", "sesame oil", "sesame paste"],
}

SIMILARITY_THRESHOLD = 0.55
EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 2000


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


def embed_batch(texts: list[str], client: OpenAI) -> list[list[float]]:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [item.embedding for item in response.data]


def embed_all(texts: list[str], client: OpenAI) -> dict[str, list[float]]:
    """Embed a list of texts in batches, returning a text → embedding dict."""
    results = {}
    batches = [texts[i : i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]

    for batch in tqdm(batches, desc="Embedding batches"):
        embeddings = embed_batch(batch, client)
        for text, embedding in zip(batch, embeddings):
            results[text] = embedding

    return results


def build_cache(csv_path: Path, output_path: Path) -> None:
    """
    Embed all unique ingredients from the dataset + all allergen examples.
    Saves a single cache JSON with both ingredient and allergen embeddings.
    If a cache file already exists, reuses its ingredient embeddings and only
    re-embeds ingredients that are missing (avoids redundant API calls).
    """
    client = OpenAI()

    # load existing ingredient embeddings if cache exists
    existing_ingredient_embeddings = {}
    if output_path.exists():
        logger.info("Existing cache found — reusing ingredient embeddings")
        with open(output_path, encoding="utf-8") as f:
            existing_cache = json.load(f)
        existing_ingredient_embeddings = existing_cache.get("ingredients", {})

    # collect unique normalized ingredients
    df = load_recipe_data(csv_path)
    unique_ingredients = list({
        ing.lower().strip()
        for ings in df["ingredients"]
        for ing in ings
        if isinstance(ing, str) and ing.strip()
    })
    logger.info(f"Unique ingredients to embed: {len(unique_ingredients):,}")

    # only embed ingredients not already cached
    to_embed = [ing for ing in unique_ingredients if ing not in existing_ingredient_embeddings]
    if to_embed:
        logger.info(f"  {len(to_embed):,} new ingredients to embed")
        new_embs = embed_all(to_embed, client)
        ingredient_embeddings = {**existing_ingredient_embeddings, **new_embs}
    else:
        logger.info("  All ingredients already cached — skipping ingredient embedding")
        ingredient_embeddings = existing_ingredient_embeddings

    # embed allergen examples (any example not in ingredient cache gets embedded separately)
    logger.info("Embedding allergen examples...")
    all_examples = list({ex for exs in ALLERGEN_EXAMPLES.values() for ex in exs})
    missing = [ex for ex in all_examples if ex not in ingredient_embeddings]
    if missing:
        logger.info(f"  {len(missing)} examples not in ingredient cache — embedding separately")
        missing_embs = embed_batch(missing, client)
        for ex, emb in zip(missing, missing_embs):
            ingredient_embeddings[ex] = emb

    # build allergen section: {allergen: [emb1, emb2, ...]}
    allergen_embeddings = {
        allergen: [ingredient_embeddings[ex] for ex in examples if ex in ingredient_embeddings]
        for allergen, examples in ALLERGEN_EXAMPLES.items()
    }

    cache = {
        "ingredients": ingredient_embeddings,
        "allergens":   allergen_embeddings,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cache, f)

    logger.info(f"Cache saved to {output_path}")
    logger.info(f"  {len(ingredient_embeddings):,} ingredient embeddings")
    for allergen, embs in allergen_embeddings.items():
        logger.info(f"  {allergen}: {len(embs)} example embeddings")


def load_cache(cache_path: Path) -> tuple[dict, dict]:
    """
    Load ingredient and allergen embeddings from cache.
    Returns:
        ingredient_cache: {ingredient_text: embedding}
        allergen_embeddings: {allergen: [emb1, emb2, ...]}
    """
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Embedding cache not found at {cache_path}. "
            "Run: python -m ingestion.allergen_embedder"
        )
    with open(cache_path, encoding="utf-8") as f:
        cache = json.load(f)

    allergens = cache["allergens"]

    # support old cache format (single vector per allergen) by wrapping in list
    allergens = {
        k: v if isinstance(v, list) and isinstance(v[0], list) else [v]
        for k, v in allergens.items()
    }

    return cache["ingredients"], allergens


def get_allergen_flags(
    ingredients: list[str],
    ingredient_cache: dict[str, list[float]],
    allergen_embeddings: dict[str, list[list[float]]],
    threshold: float = SIMILARITY_THRESHOLD,
) -> dict[str, bool]:
    """
    For each ingredient, look up its cached embedding and compute cosine
    similarity against each allergen's example embeddings.
    Flags the allergen if ANY ingredient exceeds the threshold against ANY example.
    """
    flags = {f"contains_{allergen}": False for allergen in allergen_embeddings}

    for ingredient in ingredients:
        ing_emb = ingredient_cache.get(ingredient.lower().strip())
        if ing_emb is None:
            continue

        for allergen, example_embs in allergen_embeddings.items():
            if flags[f"contains_{allergen}"]:
                continue  # already flagged, skip
            max_sim = max(cosine_similarity(ing_emb, ex_emb) for ex_emb in example_embs)
            if max_sim >= threshold:
                flags[f"contains_{allergen}"] = True

    return flags


if __name__ == "__main__":
    build_cache(FOOD_COM_CSV, ALLERGEN_EMBEDDINGS_CACHE)
