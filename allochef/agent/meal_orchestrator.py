"""
Meal Orchestrator — the top-level AlloChef agent.

A create_agent that owns the conversation and routes by intent to the
specialist sub-agents (exposed to it as tools):

  Meal Orchestrator (this agent)
  ├── recommend_recipes  → Recipe Recommender agent   ("what can I cook?")
  └── plan_groceries     → Grocery Agent              ("buy what's missing")

The orchestrator holds no domain logic itself — it interprets the request and
delegates. Structured results (RAG state for recipe cards, the grocery plan) are
stashed in a `sink` so the UI can render rich output.

Hard guarantees still live in the specialists: the Grocery Agent always runs the
allergen-safety pipeline (deterministic backfill), and the cart/approval stays a
human-gated step in the UI (build_cart) — never inside the agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from agent.grocery_agent import run_grocery_agent
from agent.recipe_recommender_agent import run_recipe_recommender
from config import OPENAI_API_KEY, ORCHESTRATOR_MODEL


def restrictions_for(active_members: list[str], family_profiles: dict[str, list[str]]) -> list[str]:
    """Flat allergen union for the active family members."""
    out: set[str] = set()
    for m in active_members:
        out.update(family_profiles.get(m, []))
    return sorted(out)


_ORCH_SYSTEM = """You are AlloChef's Meal Orchestrator for a multi-diet family.
Active diners: {members}. Their combined allergens: {restrictions}.

Your job is to DELEGATE to the right tool — you do not answer recipe or grocery questions yourself.

- ANY request about what to cook / meal ideas / "what can I make" / a list of ingredients to use up
  → call recommend_recipes, passing the user's message verbatim.
  IMPORTANT: recommend_recipes can read the family's saved pantry itself, so NEVER ask the user to
  list their ingredients. If they say "what I have", "my pantry", or give no ingredients, still call
  recommend_recipes — it will use the pantry.
- A request to shop / "plan groceries" / "buy what's missing" for a specific recipe
  → call plan_groceries with the recipe name and its ingredients.
- Only for clearly unrelated small talk, answer briefly.

Never invent recipes or grocery lists yourself, and never ask the user for ingredients — delegate."""


def _build_orchestrator(active_members, family_profiles, sink: dict):
    restrictions = restrictions_for(active_members, family_profiles)

    @tool
    def recommend_recipes(user_request: str) -> str:
        """Suggest allergen-safe recipes for the household from the ingredients the user has.
        Use when the intent is to find something to cook."""
        return run_recipe_recommender(user_request, active_members, family_profiles, sink)

    @tool
    def plan_groceries(recipe_name: str, ingredients: list[str]) -> str:
        """Plan groceries for a chosen recipe: diff the pantry, handle allergen substitutions,
        and assemble a shopping list. Pass the recipe name and its ingredient list."""
        plan = run_grocery_agent(
            {"name": recipe_name, "ingredients": ingredients},
            restrictions,
        )
        sink["grocery_plan"] = plan
        subs = [(s["original"], s["substitute"]) for s in plan.get("substitutions", [])]
        return (f"Need to buy: {plan.get('need_to_buy', [])}. "
                f"Substitutions: {subs or 'none'}. "
                f"Already have: {plan.get('already_have', [])}.")

    model = ChatOpenAI(model=ORCHESTRATOR_MODEL, api_key=OPENAI_API_KEY, temperature=0.0)
    return create_agent(
        model=model,
        tools=[recommend_recipes, plan_groceries],
        system_prompt=_ORCH_SYSTEM.format(
            members=", ".join(active_members) or "none",
            restrictions=", ".join(restrictions) or "none",
        ),
    )


def run_meal_orchestrator(
    user_query: str,
    active_members: list[str],
    family_profiles: dict[str, list[str]],
) -> dict:
    """
    Route a natural-language request to the right specialist.

    Returns {"text": <assistant reply>, "rag": <RAG result|None>,
             "grocery_plan": <plan|None>} so the UI can render whichever
    structured result was produced.
    """
    sink: dict = {}
    try:
        agent = _build_orchestrator(active_members, family_profiles, sink)
        out = agent.invoke({"messages": [{"role": "user", "content": user_query}]})
        msgs = out.get("messages", [])
        text = msgs[-1].content if msgs else ""
    except Exception as exc:  # noqa: BLE001
        text = f"Sorry — something went wrong ({exc})."
    return {"text": text, "rag": sink.get("rag"), "grocery_plan": sink.get("grocery_plan")}
