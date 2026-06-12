"""
Assembles the AlloChef LangGraph state machine.

Full graph with corrective RAG loops:

  START
    └── aggregate_restrictions
            └── hybrid_retrieve
                    └── check_relevance
                            ├── [relevant / proceed]  → allergen_check
                            └── [not_relevant]         → rewrite_query → hybrid_retrieve (retry)

                    allergen_check
                            ├── [safe]   → generate_response
                            └── [unsafe] → retrieve_substitute → generate_response

                    generate_response
                            └── check_hallucination
                                    ├── [grounded / accept]  → END
                                    └── [hallucinating]       → generate_response (retry, stricter prompt)

Usage:
  from agent.graph import graph

  result = graph.invoke({
      "ingredients":     ["chicken", "garlic", "tomatoes"],
      "active_members":  ["Maya", "Leo"],
      "family_profiles": {"Maya": ["milk"], "Leo": ["peanuts"]},
      "messages":        [],
  })
  print(result["response"])
"""

from __future__ import annotations

import sys
from pathlib import Path

from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.nodes import (
    aggregate_restrictions_node,
    allergen_check_node,
    check_hallucination_node,
    check_relevance_node,
    fallback_response_node,
    generate_response_node,
    hybrid_retrieve_node,
    retrieve_substitute_node,
    rewrite_query_node,
    route_allergen_check,
    route_hallucination_check,
    route_relevance_check,
)
from agent.state import AlloChefState


def build_graph() -> StateGraph:
    builder = StateGraph(AlloChefState)

    # ── register nodes ────────────────────────────────────────────────────────
    builder.add_node("aggregate_restrictions", aggregate_restrictions_node)
    builder.add_node("hybrid_retrieve",        hybrid_retrieve_node)
    builder.add_node("check_relevance",        check_relevance_node)
    builder.add_node("rewrite_query",          rewrite_query_node)
    builder.add_node("allergen_check",         allergen_check_node)
    builder.add_node("retrieve_substitute",    retrieve_substitute_node)
    builder.add_node("generate_response",      generate_response_node)
    builder.add_node("check_hallucination",    check_hallucination_node)
    builder.add_node("fallback_response",      fallback_response_node)

    # ── linear edges ──────────────────────────────────────────────────────────
    builder.add_edge(START,                    "aggregate_restrictions")
    builder.add_edge("aggregate_restrictions", "hybrid_retrieve")
    builder.add_edge("hybrid_retrieve",        "check_relevance")
    builder.add_edge("rewrite_query",          "hybrid_retrieve")   # relevance retry loop
    builder.add_edge("retrieve_substitute",    "generate_response")
    builder.add_edge("generate_response",      "check_hallucination")

    # ── conditional edges ─────────────────────────────────────────────────────

    # relevance check: re-retrieve if docs not relevant (capped at MAX_RETRIEVAL_ATTEMPTS)
    builder.add_conditional_edges(
        "check_relevance",
        route_relevance_check,
        {
            "relevant":     "allergen_check",
            "not_relevant": "rewrite_query",
            "proceed":      "allergen_check",   # max retries hit — proceed anyway
        },
    )

    # allergen check: substitute unsafe recipes or generate directly
    builder.add_conditional_edges(
        "allergen_check",
        route_allergen_check,
        {
            "substitute": "retrieve_substitute",
            "generate":   "generate_response",
        },
    )

    # hallucination check: regenerate with strict prompt, or admit we don't know
    builder.add_conditional_edges(
        "check_hallucination",
        route_hallucination_check,
        {
            "grounded":      END,
            "hallucinating": "generate_response",   # retry with _RESPONSE_PROMPT_STRICT
            "unknown":       "fallback_response",   # max retries hit — honest fallback
        },
    )
    builder.add_edge("fallback_response", END)

    return builder.compile()


# compiled graph — import this in app.py
graph = build_graph()
