"""
Recipe Recommender Agent — answers "what can I cook?".

A thin LLM agent (create_agent) that extracts the ingredients the user has from
their message and calls the RAG recipe pipeline (agent.graph) to suggest
allergen-safe recipes (with substitutions for unsafe ones). The heavy lifting —
hybrid retrieval, allergen checking, the substitution agent, grounded generation
with hallucination/relevance guards — stays in the tuned RAG graph; this agent
just turns a natural-language request into a search and summarises the result.

The raw RAG result (response text + safe_recipes + unsafe_pairs + substitutions)
is stashed in a caller-provided `sink` so the UI can still render rich recipe
cards from the structured state.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from agent.graph import graph
from config import OPENAI_API_KEY, ORCHESTRATOR_MODEL
from pantry import list_pantry_items


def recommend_recipes_raw(
    ingredients: list[str],
    active_members: list[str],
    family_profiles: dict[str, list[str]],
) -> dict:
    """Invoke the RAG recipe pipeline directly; returns the full result state
    (response, safe_recipes, unsafe_pairs, substitutions, …)."""
    return graph.invoke({
        "ingredients":     ingredients,
        "active_members":  active_members,
        "family_profiles": family_profiles,
        "messages":        [],
    })


_RECO_SYSTEM = """You are AlloChef's Recipe Recommender. Figure out which ingredients to cook with,
then call search_recipes with that list to find allergen-safe recipes for the household.

Choosing the ingredient list:
- If the user names specific ingredients (a list or a sentence like "I have chicken and rice"),
  use exactly those.
- If the user refers to what they already have / their pantry / fridge, or doesn't name specific
  ingredients ("what can I cook tonight?"), call get_pantry_ingredients first and use those.
- You may combine both (named ingredients + pantry) when that makes sense.

Always call search_recipes (after get_pantry_ingredients if needed). Never invent recipes yourself.
After the tool returns, briefly present the suggestions."""


def _build_recommender(active_members, family_profiles, sink: dict, household_id: str = "default"):
    @tool
    def get_pantry_ingredients() -> list[str]:
        """Return the ingredients the household already has saved in their pantry.
        Use this when the user asks what they can cook with what they have."""
        items = [p["item_name"] for p in list_pantry_items(household_id)]
        sink["pantry"] = items
        return items

    @tool
    def search_recipes(ingredients: list[str]) -> str:
        """Search the recipe knowledge base for allergen-safe recipes that use the
        given ingredients. Returns ready-to-show recipe suggestions."""
        result = recommend_recipes_raw(ingredients, active_members, family_profiles)
        sink["rag"] = result            # structured state for the UI's recipe cards
        sink["ingredients"] = ingredients
        return result.get("response") or "No matching recipes found."

    model = ChatOpenAI(model=ORCHESTRATOR_MODEL, api_key=OPENAI_API_KEY, temperature=0.0)
    return create_agent(model=model, tools=[get_pantry_ingredients, search_recipes],
                        system_prompt=_RECO_SYSTEM)


def run_recipe_recommender(
    user_query: str,
    active_members: list[str],
    family_profiles: dict[str, list[str]],
    sink: dict | None = None,
) -> str:
    """
    Run the Recipe Recommender on a natural-language request.

    Returns the recommendation text. If `sink` is provided, the raw RAG result is
    placed under sink["rag"] so the caller can render structured recipe cards.
    Never raises — returns an error string on failure.
    """
    sink = sink if sink is not None else {}
    try:
        agent = _build_recommender(active_members, family_profiles, sink)
        out = agent.invoke({"messages": [{"role": "user", "content": user_query}]})
        msgs = out.get("messages", [])
        return msgs[-1].content if msgs else (sink.get("rag", {}).get("response", ""))
    except Exception as exc:  # noqa: BLE001
        return f"Sorry — I couldn't fetch recipes right now ({exc})."
