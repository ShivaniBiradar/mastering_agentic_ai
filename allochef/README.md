# AlloChef

**An agentic, allergen-safe meal & grocery assistant for multi-diet families.**

AlloChef answers two questions for a household where different people have different
allergies: *"What can we cook tonight with what we have?"* and *"What do I need to buy
to make it — safely?"*

You chat in plain English ("what can I cook with what I have?") or list ingredients,
pick who's eating, and AlloChef recommends recipes from a 230k-recipe corpus, swaps out
unsafe ingredients with **context-aware substitutions**, then plans the groceries —
diffing your pantry, flagging allergens, and building a cart you approve before anything
is added. Every recipe is grounded in real retrieved data, never hallucinated.

---

## Features

- **Conversational interface** — ask in natural language *or* paste an ingredient list; the
  Meal Orchestrator figures out the intent and routes it.
- **Cook-from-your-pantry** — "what can I cook with what I have?" reads your saved pantry.
- **Hybrid recipe retrieval** — dense semantic + BM25 sparse search via Pinecone.
- **Corrective RAG** — LLM relevance check (re-retrieves) + hallucination guard (every
  recipe name must be grounded in retrieved context).
- **Intelligent substitutions (the USP)** — an LLM agent picks the *context-appropriate*
  swap (vegan mozzarella for a bake vs. nutritional yeast for a topping vs. cashew cream
  for a sauce), rewrites the recipe title naturally, and **safety-verifies** every swap.
- **Analog-aware allergen detection** — knows "almond milk" / "vegan butter" are dairy-free
  (but almond items still trip tree-nuts).
- **Grocery planning** — pantry diff → allergen triage → substitution → normalized shopping
  list with quantities → human-approved cart.
- **Cart fulfillment** — mock cart by default, or a real shoppable Instacart link via the
  Instacart **MCP** server (`CART_PROVIDER=instacart`).
- **Family profiles & pantry** — per-member allergens and a saved pantry, persisted in SQLite.
- **Fridge photo scan** — upload a photo; GPT-4o vision adds the ingredients to your pantry.

**Supported allergens:** Milk/Dairy · Eggs · Fish · Shellfish · Tree Nuts · Peanuts · Wheat · Gluten · Soy · Sesame

---

## Architecture — a multi-agent system

AlloChef is built as **agents** (LLM-driven agent loops that reason and route)
on top of **deterministic tools** (plain functions that compute facts). Guiding principle:
*LLMs for language & reasoning, deterministic code for facts & safety.*

```
Meal Orchestrator            (agent — routes by intent)
├── recommend_recipes →  Recipe Recommender   (agent)
│                          └── search_recipes → RAG graph (retrieval + corrective RAG)
│                                                 └── Substitution Agent (agent)
└── plan_groceries    →  Grocery Agent         (deterministic facts + LLM for notes)
      └── (uses) Substitution Agent (agent)
```

| Component | Kind | Responsibility |
|---|---|---|
| **Meal Orchestrator** | agent | Interpret the chat message, route to a specialist. |
| **Recipe Recommender** | agent | "What can I cook?" — reads the pantry when asked, runs the RAG graph. |
| **Grocery Agent** | agent + deterministic | Pantry diff → allergen triage → substitution → shopping list. |
| **Substitution Agent** | agent | Context-aware, safety-verified ingredient swaps (shared). |
| RAG recipe graph | LangGraph | Hybrid retrieval + relevance & hallucination gates + grounded generation. |
| Pantry / Safety tools | functions | Deterministic pantry compare & analog-aware allergen triage. |
| Instacart MCP client | tool | Streamable-HTTP MCP → shoppable cart link. |

**Safety invariants** (an agent can never override these):
1. Allergen detection is deterministic and analog-aware.
2. The grocery pantry/safety/substitution facts are deterministic — the LLM only interprets
   free-text notes ("I already have spinach").
3. **No cart is created without explicit human approval.**
4. Every substitute is safety-verified before it reaches a card or cart.

**Stack:** LangGraph · Pinecone (hybrid) · Neo4j Aura ·
OpenAI (GPT-4o / GPT-4o-mini) · Nebius (grocery normalization) · Instacart MCP · Streamlit · SQLite

---

## Grocery planning flow

```
Recipe chosen ("Plan groceries")
   → pantry diff           (what you have vs. need — deterministic)
   → allergen triage       (safe vs. unsafe missing items)
   → substitution          (safe swap for each unsafe item)
   → shopping list         (Nebius normalization + quantities)
   → HUMAN APPROVAL  ←── you review & edit quantities in a modal
   → cart                  (mock, or real Instacart link via MCP)
```

---

## Eval

```bash
python3 -m eval.grocery_eval     # grocery agent: pantry diff, allergen triage, cart
```

| Suite | Result |
|---|---|
| Grocery agent checks (`eval/grocery_eval.py`) | **23 / 23** |
| RAG retrieval relevance | 11 / 11 · 100% |
| Allergen recall (unsafe recipes flagged) | 7 / 7 · 100% |
| Faithfulness (grounded responses) | 100% (hallucination guard) |

Substitution is now handled by the context-aware Substitution Agent, which renames recipe
titles and verifies every swap is allergen-safe (replacing the earlier static rule lookup).

---

## Setup

### Prerequisites
- Python 3.11+
- [Pinecone](https://pinecone.io) — two indexes: `allochef-recipes`, `allochef-substitutions`
- [Neo4j Aura](https://neo4j.com/cloud/platform/aura-graph-database/) free instance (substitution graph)
- OpenAI API key
- *(optional)* [Nebius](https://studio.nebius.com) key for grocery-item normalization
- *(optional)* [Instacart Developer Platform](https://docs.instacart.com/developer_platform_api) key for real carts

### Install
```bash
cd allochef
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configure
Copy `.env.example` to `.env` and fill in your keys. OpenAI, Pinecone, and Neo4j are
required; Nebius and Instacart are optional. Model choices and `CART_PROVIDER` are also
env-overridable — see `.env.example` for the full list and defaults.

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

The recipe corpus is the [Food.com Kaggle dataset](https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions)
(231k recipes). The raw CSV and cleaned JSONL are **not** in this repo (too large for GitHub) —
the data is already indexed in Pinecone. `data/cleaned/bm25_encoder.json` (~1 MB) is included
and required at runtime for sparse retrieval.

Re-index from scratch:
```bash
python3 -m ingestion.recipe_loader      # parse CSV
python3 -m ingestion.cleaner            # clean + allergen-flag
python3 -m ingestion.pinecone_indexer   # embed + upsert to Pinecone
python3 -m ingestion.graph_loader       # load substitutions to Neo4j
```

---

## Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → New app → select repo → entry point `allochef/app.py`.
3. Add secrets in the Streamlit dashboard (same keys as `.env`).
4. Deploy — all services run on free tiers; Nebius and Instacart are optional.
