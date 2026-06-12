"""
Embeds and indexes recipe chunks + substitutions into Pinecone.

Two indexes:
  allochef-recipes       — recipe chunks (overview + instructions)
                           dense (text-embedding-3-small) + sparse (BM25) vectors
  allochef-substitutions — substitution entries
                           dense vectors only (small corpus, exact lookup via Neo4j)

Sparse vectors are produced by pinecone_text BM25Encoder — fit once on the full
corpus, saved to BM25_ENCODER_PATH, and reloaded at query time by the agent.
Token IDs are consistent between index time and query time.

Resume-safe: tracks progress in a local checkpoint file so a partial run
can be resumed without re-embedding already-indexed chunks.

How to run:
  cd allochef
  python -m ingestion.indexer

Estimated cost: ~$1.50 for 475k recipe chunks (one-time)
Estimated time: 35–70 minutes depending on OpenAI rate limit tier
"""

import json
import logging
import sys
import time
from pathlib import Path

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from pinecone_text.sparse import BM25Encoder
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BM25_ENCODER_PATH,
    CLEANED_RECIPES_JSONL,
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_SUBS_INDEX,
    SUBSTITUTIONS_JSON,
)
from ingestion.chunker import chunk_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

EMBED_MODEL  = "text-embedding-3-small"
EMBED_DIMS   = 1536
EMBED_BATCH  = 100
UPSERT_BATCH = 100
CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / "cleaned" / "indexer_checkpoint.json"


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_texts(texts: list[str], client: OpenAI) -> list[list[float]]:
    """Embed a batch of texts with retry on rate limit."""
    for attempt in range(5):
        try:
            response = client.embeddings.create(model=EMBED_MODEL, input=texts)
            return [item.embedding for item in response.data]
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < 4:
                wait = 2 ** attempt * 10
                logger.warning(f"Rate limited — retrying in {wait}s")
                time.sleep(wait)
            else:
                raise


# ── Checkpoint ────────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return set(json.load(f))
    return set()


def save_checkpoint(indexed_ids: set[str]) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(list(indexed_ids), f)


# ── Pinecone setup ────────────────────────────────────────────────────────────

def get_or_create_index(pc: Pinecone, name: str, metric: str = "dotproduct") -> object:
    existing = [idx.name for idx in pc.list_indexes()]
    if name not in existing:
        logger.info(f"Creating Pinecone index: {name}")
        pc.create_index(
            name=name,
            dimension=EMBED_DIMS,
            metric=metric,
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        while not pc.describe_index(name).status["ready"]:
            time.sleep(1)
        logger.info(f"Index {name} ready")
    else:
        logger.info(f"Index {name} already exists")
    return pc.Index(name)


# ── Recipe indexing ───────────────────────────────────────────────────────────

def index_recipes(index, client: OpenAI, encoder: BM25Encoder) -> None:
    logger.info("Loading and chunking recipes...")
    all_chunks = chunk_all(CLEANED_RECIPES_JSONL)
    logger.info(f"Total chunks to index: {len(all_chunks):,}")

    indexed_ids = load_checkpoint()
    remaining = [c for c in all_chunks if f"{c['metadata']['recipe_id']}_{c['metadata']['chunk_index']}" not in indexed_ids]
    logger.info(f"Already indexed: {len(indexed_ids):,} | Remaining: {len(remaining):,}")

    batches = [remaining[i : i + EMBED_BATCH] for i in range(0, len(remaining), EMBED_BATCH)]

    for batch in tqdm(batches, desc="Indexing recipes"):
        texts      = [c["text"] for c in batch]
        dense_embs = embed_texts(texts, client)
        sparse_vecs = encoder.encode_documents(texts)

        vectors = []
        for chunk, dense, sparse in zip(batch, dense_embs, sparse_vecs):
            chunk_id = f"{chunk['metadata']['recipe_id']}_{chunk['metadata']['chunk_index']}"
            vectors.append({
                "id":            chunk_id,
                "values":        dense,
                "sparse_values": sparse,
                "metadata":      {**chunk["metadata"], "text": chunk["text"]},
            })

        for i in range(0, len(vectors), UPSERT_BATCH):
            index.upsert(vectors=vectors[i : i + UPSERT_BATCH])

        for chunk in batch:
            indexed_ids.add(f"{chunk['metadata']['recipe_id']}_{chunk['metadata']['chunk_index']}")

        save_checkpoint(indexed_ids)

    logger.info(f"Recipe indexing complete — {len(indexed_ids):,} chunks in Pinecone")


# ── Substitution indexing ─────────────────────────────────────────────────────

def serialize_substitution(entry: dict) -> str:
    works_in = ", ".join(entry.get("works_in", []))
    return (
        f"Replace {entry['original']} ({entry['allergen']} allergy) "
        f"with {entry['substitute']}. "
        f"Works in: {works_in}. "
        f"{entry.get('notes', '')}"
    )


def index_substitutions(index, client: OpenAI) -> None:
    with open(SUBSTITUTIONS_JSON) as f:
        data = json.load(f)

    entries = data["substitutions"]
    texts   = [serialize_substitution(e) for e in entries]
    logger.info(f"Indexing {len(entries)} substitutions...")

    embeddings = embed_texts(texts, client)

    vectors = [
        {
            "id":       f"sub_{i}",
            "values":   emb,
            "metadata": {
                "text":       texts[i],
                "original":   entries[i]["original"],
                "substitute": entries[i]["substitute"],
                "allergen":   entries[i]["allergen"],
                "works_in":   entries[i].get("works_in", []),
                "notes":      entries[i].get("notes", ""),
            },
        }
        for i, emb in enumerate(embeddings)
    ]

    index.upsert(vectors=vectors)
    logger.info("Substitution indexing complete")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    client = OpenAI(api_key=OPENAI_API_KEY)
    pc     = Pinecone(api_key=PINECONE_API_KEY)

    recipe_index = get_or_create_index(pc, PINECONE_INDEX_NAME)
    subs_index   = get_or_create_index(pc, PINECONE_SUBS_INDEX)

    # fit BM25Encoder on full corpus and save — reused at query time by the agent
    logger.info("Fitting BM25Encoder on recipe corpus...")
    all_chunks = chunk_all(CLEANED_RECIPES_JSONL)
    encoder = BM25Encoder()
    encoder.fit([c["text"] for c in all_chunks])
    encoder.dump(str(BM25_ENCODER_PATH))
    logger.info(f"BM25Encoder saved to {BM25_ENCODER_PATH}")

    index_recipes(recipe_index, client, encoder)
    index_substitutions(subs_index, client)


if __name__ == "__main__":
    main()
