"""
Chunks cleaned recipe documents for embedding and indexing into Pinecone.

Structured sections strategy — always produces at least 2 chunks per recipe:

  Chunk type "overview"
    → name + ingredients + tags + time
    → answers queries like "what can I make with eggs and flour?"
      or "find me a quick vegetarian dish"

  Chunk type "instructions" (one or more)
    → name + steps (sliding window of 4 steps, 1-step overlap if long)
    → answers queries like "how do I make this?" or "what's the process for X?"

Both chunk types carry the same allergen flags as metadata so Pinecone
can hard-filter on allergens regardless of which chunk type is retrieved.
Both link back to the same recipe via recipe_id.

How to run (inspect sample output + full dataset stats):
  cd allochef
  python -m ingestion.chunker
"""

import json
import logging
import sys
from pathlib import Path

import tiktoken

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CLEANED_RECIPES_JSONL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

MAX_TOKENS = 512
STEP_WINDOW = 4
STEP_OVERLAP = 1

# cl100k_base is the encoding used by all OpenAI embedding models
_tokenizer = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text))


def _base_metadata(recipe: dict, chunk_type: str, chunk_index: int, total_chunks: int) -> dict:
    """Metadata stored alongside each chunk vector in Pinecone."""
    meta = {
        "recipe_id":    recipe["id"],
        "name":         recipe["name"],
        "chunk_type":   chunk_type,
        "chunk_index":  chunk_index,
        "total_chunks": total_chunks,
        "minutes":      recipe.get("minutes", ""),
        "tags":         recipe.get("tags", []),
    }
    for key, val in recipe.items():
        if key.startswith("contains_"):
            meta[key] = val
    return meta


def _overview_chunk(recipe: dict, total_chunks: int) -> dict:
    """
    Overview chunk: name + ingredients + tags + time.
    Optimised for ingredient and dietary queries.
    """
    ingredients = ", ".join(recipe["ingredients"])
    tags = ", ".join(recipe.get("tags", []))
    minutes = recipe.get("minutes", "")
    time_str = f"\nTime: {minutes} minutes" if minutes else ""

    text = (
        f"Recipe: {recipe['name']}\n"
        f"Ingredients: {ingredients}\n"
        f"Tags: {tags}"
        f"{time_str}"
    )
    return {
        "text":     text,
        "metadata": _base_metadata(recipe, chunk_type="overview", chunk_index=0, total_chunks=total_chunks),
    }


def _instruction_chunks(recipe: dict, chunk_offset: int, total_chunks: int) -> list[dict]:
    """
    Instruction chunk(s): name + steps.
    Single chunk if steps fit within MAX_TOKENS, sliding window otherwise.
    Optimised for cooking method and process queries.
    """
    steps = recipe["steps"]
    full_text = f"Recipe: {recipe['name']}\n" + " ".join(steps)

    # short — single instruction chunk
    if count_tokens(full_text) < MAX_TOKENS:
        text = f"Recipe: {recipe['name']}\n" + " ".join(steps)
        return [{
            "text":     text,
            "metadata": _base_metadata(
                recipe, chunk_type="instructions",
                chunk_index=chunk_offset, total_chunks=total_chunks
            ),
        }]

    # long — sliding window over steps
    windows = []
    i = 0
    while i < len(steps):
        windows.append(steps[i : i + STEP_WINDOW])
        i += STEP_WINDOW - STEP_OVERLAP

    chunks = []
    for idx, window in enumerate(windows):
        text = f"Recipe: {recipe['name']}\n" + " ".join(window)
        chunks.append({
            "text":     text,
            "metadata": _base_metadata(
                recipe, chunk_type="instructions",
                chunk_index=chunk_offset + idx, total_chunks=total_chunks
            ),
        })
    return chunks


def chunk_recipe(recipe: dict) -> list[dict]:
    """
    Chunk a single cleaned recipe using the structured sections strategy.
    Always returns at least 2 chunks: 1 overview + 1 or more instruction chunks.
    """
    steps = recipe["steps"]
    full_steps_text = f"Recipe: {recipe['name']}\n" + " ".join(steps)
    long_recipe = count_tokens(full_steps_text) >= MAX_TOKENS

    # calculate total chunks upfront for metadata
    if long_recipe:
        n_instruction_windows = 0
        i = 0
        while i < len(steps):
            n_instruction_windows += 1
            i += STEP_WINDOW - STEP_OVERLAP
        total_chunks = 1 + n_instruction_windows
    else:
        total_chunks = 2  # 1 overview + 1 instructions

    overview = _overview_chunk(recipe, total_chunks)
    instructions = _instruction_chunks(recipe, chunk_offset=1, total_chunks=total_chunks)

    return [overview] + instructions


def chunk_all(jsonl_path: Path) -> list[dict]:
    """Load all cleaned recipes and chunk them. Returns a flat list of chunks."""
    chunks = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            recipe = json.loads(line)
            chunks.extend(chunk_recipe(recipe))
    return chunks


if __name__ == "__main__":
    if not CLEANED_RECIPES_JSONL.exists():
        logger.error(f"Cleaned recipes not found at {CLEANED_RECIPES_JSONL}. Run cleaner first.")
        sys.exit(1)

    with open(CLEANED_RECIPES_JSONL, encoding="utf-8") as f:
        lines = f.readlines()

    # print first 3 recipes in detail
    for line in lines[:3]:
        recipe = json.loads(line)
        chunks = chunk_recipe(recipe)
        print(f"\n{'─' * 60}")
        print(f"RECIPE : {recipe['name']}")
        print(f"CHUNKS : {len(chunks)}")
        for chunk in chunks:
            tokens = count_tokens(chunk["text"])
            ctype = chunk["metadata"]["chunk_type"]
            cidx = chunk["metadata"]["chunk_index"]
            print(f"  [{ctype}] chunk {cidx}: {tokens} tokens")
            preview = chunk["text"][:200].replace("\n", " | ")
            print(f"    {preview}...")

    # stats across full dataset
    total_recipes = 0
    total_chunks = 0
    type_counts = {"overview": 0, "instructions": 0}
    multi_instruction = 0

    for line in lines:
        recipe = json.loads(line)
        chunks = chunk_recipe(recipe)
        total_recipes += 1
        total_chunks += len(chunks)
        for chunk in chunks:
            type_counts[chunk["metadata"]["chunk_type"]] += 1
        instruction_chunks = [c for c in chunks if c["metadata"]["chunk_type"] == "instructions"]
        if len(instruction_chunks) > 1:
            multi_instruction += 1

    print(f"\n{'─' * 60}")
    print(f"Total recipes          : {total_recipes:,}")
    print(f"Total chunks           : {total_chunks:,}")
    print(f"Avg chunks/recipe      : {total_chunks/total_recipes:.2f}")
    print(f"  overview chunks      : {type_counts['overview']:,}")
    print(f"  instruction chunks   : {type_counts['instructions']:,}")
    print(f"  multi-window recipes : {multi_instruction:,}  (instructions split across windows)")
