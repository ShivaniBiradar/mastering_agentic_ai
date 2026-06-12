from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AlloChefState(TypedDict):
    # conversation history — add_messages reducer appends rather than overwrites
    messages:         Annotated[list[BaseMessage], add_messages]

    # provided by Streamlit UI before invoking the graph
    ingredients:      list[str]              # ["chicken", "garlic", "tomatoes"]
    active_members:   list[str]              # family members eating tonight
    family_profiles:  dict[str, list[str]]   # {name: ["milk", "peanuts", ...]}

    # derived by aggregate_restrictions_node
    restrictions:     list[str]              # flat union of allergens for tonight

    # retrieval
    query:            str                    # built from ingredients
    retrieved_docs:   list                   # LangChain Document objects from Pinecone

    # allergen check output
    safe_recipes:     list                   # docs that passed allergen check
    unsafe_pairs:     list[dict]             # [{doc, allergens:[...]}]

    # substitution output — per unsafe recipe, what substitutes were found
    substitutions:    list[dict]             # [{recipe_name, recipe_id, allergen, available_substitutes:[...]}]

    # corrective RAG loop counters — prevent infinite retry cycles
    retrieval_attempts:   int    # incremented by rewrite_query_node, capped at MAX_RETRIEVAL_ATTEMPTS
    generation_attempts:  int    # incremented by generate_response_node, capped at MAX_GENERATION_ATTEMPTS

    # verdicts written by checker nodes, read by routing functions
    relevance_verdict:    str    # "relevant" | "not_relevant"
    hallucination_verdict: str   # "grounded" | "hallucinating"

    # final LLM response
    response:         str
