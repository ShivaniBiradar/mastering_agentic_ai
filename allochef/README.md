# AlloChef

**Allergen-safe recipe suggestions for multi-diet families.**

AlloChef answers the question: *"What can we safely cook tonight, given what we have and who's eating?"*

Enter your available ingredients, select which family members are eating, and AlloChef retrieves recipes from a 230k-recipe corpus, checks them against each person's allergen profile, finds ingredient substitutions where needed, and generates practical cooking suggestions — all grounded in real retrieved recipes, never hallucinated.

---

## Features

- **Hybrid recipe retrieval** — dense semantic + BM25 sparse search via Pinecone
- **Runtime allergen checking** — two-step: metadata flag at index time + text scan at runtime
- **Allergen substitutions** — deterministic Neo4j graph lookup (79 curated rules) with Pinecone semantic fallback
- **Substitution applied in output** — allergen ingredients replaced with their swap in both ingredient list and cooking steps
- **Hallucination guard** — LLM-as-judge verifies every recipe name is grounded in retrieved context
- **Family profiles** — per-member allergen settings persisted in SQLite, managed from the sidebar
- **Fridge photo scan** — upload a photo, GPT-4o vision identifies the ingredients

**Supported allergens:** Milk/Dairy · Eggs · Fish · Shellfish · Tree Nuts · Peanuts · Wheat · Gluten · Soy · Sesame

---

## Architecture

```
User ingredients + family allergen profiles
        │
        ▼
Pinecone hybrid retrieval (dense + BM25, top-20)
        │
        ▼
LLM relevance check → rewrite query if poor (max 2 retries)
        │
        ▼
Two-step allergen check (metadata flag + page_content text scan)
  ├── Safe recipes ──────────────────────────────────────┐
  └── Unsafe recipes → Neo4j substitution lookup         │
                        (Pinecone semantic fallback)      │
                        Recipes with subs added to safe ──┘
        │
        ▼
One GPT-4o-mini call — full RAG context → structured recipe cards
(ingredients + steps copied from Pinecone; allergen swapped for substitute)
        │
        ▼
LLM hallucination check → regenerate with stricter prompt if needed
        │
        ▼
Streamlit UI — Need a Substitution (first) · Ready to Cook (second)
```

**Stack:** LangGraph · Pinecone (hybrid) · Neo4j Aura · OpenAI GPT-4o-mini · Streamlit · SQLite

---

## Eval Results (baseline)

| Metric | Score |
|---|---|
| Faithfulness (grounded responses) | 10/10 · 100% |
| Retrieval relevance | 11/11 · 100% |
| Allergen recall (unsafe recipes flagged) | 7/7 · 100% |
| Substitution accuracy (correct sub found) | 3/5 · 60% |
| Substitution applied in output | 0/3 · 0% |
| Fallback rate | 0/11 · 0% |

Run the eval suite: `python3 -m eval.run_eval`

---

## Setup

### Prerequisites

- Python 3.11+
- [Pinecone](https://pinecone.io) account — two indexes: `allochef-recipes`, `allochef-substitutions`
- [Neo4j Aura](https://neo4j.com/cloud/platform/aura-graph-database/) free instance
- OpenAI API key

### Install

```bash
cd allochef
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` and fill in your keys:

```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=allochef-recipes
PINECONE_SUBS_INDEX_NAME=allochef-substitutions
NEO4J_URI=neo4j+s://...
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
```

### Load the substitution graph

```bash
python3 -m ingestion.graph_loader
```

### Run

```bash
streamlit run app.py
```

---

## Data

The recipe corpus is the [Food.com Kaggle dataset](https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions) (231k recipes). The raw CSV and cleaned JSONL are **not** included in this repo (too large for GitHub) — the data is already indexed in Pinecone. The `data/cleaned/bm25_encoder.json` (1 MB) is included and required at runtime for sparse retrieval.

To re-index from scratch:
```bash
python3 -m ingestion.recipe_loader      # parse CSV
python3 -m ingestion.cleaner            # clean + allergen-flag
python3 -m ingestion.pinecone_indexer   # embed + upsert to Pinecone
python3 -m ingestion.graph_loader       # load substitutions to Neo4j
```

---

## Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → select repo → entry point `allochef/app.py`
3. Add secrets in the Streamlit dashboard (same keys as `.env` above)
4. Deploy — no other infrastructure needed, all services run on free tiers
