# AlloChef — Agent Architecture (handoff)

This document describes the current multi-agent architecture of AlloChef's `agent/`
layer and the Streamlit app, after the Week-3 refactor. It's written as a handoff
so another developer (or coding agent) can pick it up.

## Mental model

Two kinds of components, and they are **not** the same thing:

- **Agents** = LLM-driven `langchain.agents.create_agent` loops. They reason and
  decide which tools to call.
- **Tools** = plain deterministic Python functions. No LLM. They compute facts.

**Core principle:** *LLMs for language and reasoning; deterministic code for facts
and safety.* Anything safety-critical (allergen detection, pantry diff, the
human-approval gate) is deterministic and authoritative — an agent can never
corrupt it.

## Agent hierarchy

```
Meal Orchestrator        (agent — routes by intent)
├── recommend_recipes →  Recipe Recommender   (agent)
│                          └── search_recipes → RAG graph (agent/graph.py)
│                                                 └── Substitution Agent (agent)
└── plan_groceries    →  Grocery Agent         (agent; deterministic facts + LLM for notes)
      └── (uses) Substitution Agent (agent)
```

| Component | Kind | File | Responsibility |
|---|---|---|---|
| Meal Orchestrator | agent | `agent/meal_orchestrator.py` | Interpret intent, route to a sub-agent. No domain logic. |
| Recipe Recommender | agent | `agent/recipe_recommender_agent.py` | "What can I cook?" Wraps the RAG graph as a tool. |
| Grocery Agent | agent + det. | `agent/grocery_agent.py` | Pantry diff → safety → substitution → shopping list. |
| Substitution Agent | agent | `agent/substitution_agent.py` | Context-aware, safety-verified substitutes. Shared. |
| RAG recipe graph | LangGraph | `agent/graph.py`, `agent/nodes.py` | Retrieval + corrective RAG (relevance + hallucination gates). Unchanged. |
| Pantry tools | tools | `agent/pantry_tools.py` | `compare_pantry_tool`, `load_pantry_tool`, ingredient dedupe. |
| Safety tools | tools | `agent/safety_tools.py` | `check_grocery_safety_tool` (analog-aware triage). |
| Allergen domain | tools | `agent/nodes.py` | `detect_allergens`, `_ALLERGEN_TO_INGREDIENTS`, `_pinecone_substitute_fallback`. |
| Instacart MCP | tool | `agent/instacart_mcp.py` | Streamable-HTTP MCP client → shoppable cart link. |
| Cart builders | tools | `agent/grocery_agent.py` | `build_cart`, `create_mock_cart`, `create_instacart_cart`, `nebius_normalize_items`. |
| Pantry store | data | `pantry.py` | SQLite-backed pantry (same DB as profiles). |

## Key flows

### 1. Recipe recommendation
`app.run_agent(ingredients)` → `run_meal_orchestrator(...)` → orchestrator calls
`recommend_recipes` tool → `run_recipe_recommender(...)` → `search_recipes` tool →
`recommend_recipes_raw()` → `graph.invoke(...)` (RAG: retrieve → relevance check →
allergen check → substitution → generate → hallucination check).

The structured RAG result is stashed in a `sink` dict and returned as
`result["rag"]`, so the UI still renders rich recipe cards. There is a
**direct-graph fallback** (`_run_rag_direct`) if the orchestrator can't return a
structured result.

### 2. Grocery planning  (Grocery Agent)
`app` "Plan groceries" button → `run_grocery_agent(recipe, restrictions)`:

1. `_compute_plan_facts()` — **deterministic & authoritative**: pantry diff
   (`compare_pantry_tool`) → allergen triage (`check_grocery_safety_tool`) →
   substitutes (`find_safe_substitute_tool`). The LLM cannot alter these.
2. **Only if** a free-text `user_note` is given (e.g. "I already have spinach"),
   a small `create_agent` interprets it and records noted items; facts are then
   recomputed honouring them. No note → no LLM call.
3. Returns a `grocery_plan` dict (no cart).

**Cart + approval are deterministic and UI-gated:** the modal shows the plan, the
user approves, then `build_cart(plan, edits, provider)` runs (`CART_PROVIDER` =
`mock` | `instacart`). No cart is ever created without explicit approval. There is
**no `interrupt()`** in this path anymore.

### 3. Substitution (the USP)  `agent/substitution_agent.py`
- `find_recipe_substitutions(unsafe_pairs, restrictions)` — recipe-rec entry point:
  detect culprit ingredients → `gather_candidate_substitutes` (Neo4j → Pinecone) →
  `run_substitution_agent`.
- `run_substitution_agent(...)` — a `create_agent` with two `@tool`s:
  - `lookup_substitute_candidates(ingredient, allergen)` — DB candidates.
  - `check_allergen_safety(substitute)` — **mandatory** intelligent safety check.
  - Picks the best **context-aware** substitute (vegan mozzarella for a bake vs.
    nutritional yeast for a topping vs. cashew cream for a sauce), rewrites the
    title naturally, and returns a reason. Output is structured (Pydantic
    `response_format`).
- `check_substitute_allergens(...)` — LLM judges allergen content **analog-aware**
  ("almond cheese" is milk-free but tree-nut; "cheddar cheese" is milk).
  Deterministic `_fallback_allergen_check` if the LLM is down. A backstop
  re-verifies every chosen substitute (defense in depth).
- `find_safe_substitute_tool(...)` — single-best substitute used by the Grocery Agent.

## Safety invariants (do not break these)
1. **Allergen detection is deterministic & analog-aware** (`detect_allergens` in
   `agent/nodes.py`). Shared by the safety triage and the substitution fallback.
2. **The grocery pantry/safety/substitution facts are deterministic** — the LLM
   only interprets natural-language notes.
3. **No cart without human approval** — approval is a UI step; `build_cart` runs
   only after the user approves.
4. **Every substitute is safety-verified** before it reaches a card/cart.

## Config (`config.py`, all env-overridable)
- `ORCHESTRATOR_MODEL` (default `gpt-4o-mini`)
- `GROCERY_AGENT_MODEL` (default `gpt-4o-mini`)
- `SUBSTITUTION_AGENT_MODEL` (default `gpt-4o`), `SUBSTITUTION_AGENT_TEMPERATURE` (`0.4`)
- `SUBSTITUTION_SAFETY_MODEL` (default `gpt-4o-mini`)
- `CART_PROVIDER` (`mock` | `instacart`), `INSTACART_API_KEY`, `INSTACART_MCP_URL`
- `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL` (grocery item normalization)

## Removed in the refactor
- `agent/grocery_nodes.py`, `agent/grocery_graph.py`, `agent/grocery_state.py`
  (the old deterministic `StateGraph` orchestrator + compat shims).
- `agent/pantry_agent.py` → `agent/pantry_tools.py`,
  `agent/allergy_safety_agent.py` → `agent/safety_tools.py` (renamed; node
  wrappers stripped — they're tools, not agents).

## Tests
- `python -m eval.grocery_eval` — 23 deterministic checks on the tool functions
  (pantry compare, safety triage, cart). Currently 23/23. Keep it green.

## Known rough edges / TODO for next dev
1. **Built-in dialog ✕ leaves stale state.** Streamlit's top-right ✕ dismisses a
   `@st.dialog` without firing our close handler, so `grocery_phase` can stay set
   and the grocery modal may reappear on the next interaction. The crash from two
   dialogs opening at once is guarded (`_pantry_opening` flag in `app.py`), but the
   stale-phase reopen is unsolved. Suggested fix: reset `grocery_phase = None` when
   the pantry dialog opens, and/or detect dismissal.
2. **Seed substitutions need re-ingestion to reach the grocery path.**
   `data/substitutions/seed_substitutions.json` now has `paneer → firm tofu` (and
   halloumi), but the **grocery** substitution path reads Neo4j/Pinecone, not the
   JSON. Run the ingestion (`python -m ingestion.graph_loader` + the Pinecone subs
   index build) to load new entries. The **recipe recommender** already handles
   paneer via the LLM substitution agent.
3. **Allergen vocabulary is hand-maintained.** `_ALLERGEN_TO_INGREDIENTS` may miss
   regional/uncommon dairy/allergen ingredients (paneer was missing — now added).
   Consider auditing the recipe corpus for un-vocabularised allergen words.
4. **Extra latency on recipe search.** It routes orchestrator → recommender → RAG
   (two extra `gpt-4o-mini` calls). Acceptable for demo; if latency matters, call
   the RAG graph directly for the structured ingredient form and reserve the
   orchestrator for a conversational entry. Direct fallback already exists.
5. **`agent/substitution_agent.py` still imports from `agent/nodes.py`**
   (`_ALLERGEN_TO_INGREDIENTS`, `_pinecone_substitute_fallback`, `detect_allergens`).
   For a fully self-contained agent layer, move the allergen vocabulary + Pinecone
   fallback into a shared `agent/allergens.py` module.
6. **No conversational UI yet.** The Meal Orchestrator is exercised via
   `run_agent`, but there's no free-text "Ask AlloChef" box in the app to show
   intent routing (recommend vs. plan) directly. Optional next feature.
7. **Card ↔ LLM matching is name-based.** Recipe cards match the LLM output by
   recipe name, with a fallback to the substitution's `renamed_title`. It's robust
   for current cases but still string-matching; a recipe_id round-trip would be
   sturdier.
