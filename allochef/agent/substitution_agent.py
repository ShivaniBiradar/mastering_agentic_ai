"""
Substitution Agent — finds safe, context-aware substitutes for allergen-unsafe
ingredients. Shared by both the Recipe Recommender (per recipe) and the Grocery
Agent (per missing item).

Capabilities:
  - gather_candidate_substitutes: Tier 1 Neo4j → Tier 2 Pinecone candidate lookup
  - check_substitute_allergens:   intelligent, analog-aware safety check (LLM + fallback)
  - run_substitution_agent:       create_agent that picks the best context-aware
                                  substitute, rewrites the title, and verifies safety
  - find_recipe_substitutions:    recipe-recommendation entry point
  - find_safe_substitute_tool:    single-best substitute (used by the Grocery Agent)

Safety rule: a proposed substitute is rejected if it would reintroduce any active
allergen (verified by the safety check, not by naive name matching).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from config import (
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USERNAME,
    OPENAI_API_KEY,
    SUBSTITUTION_AGENT_MODEL,
    SUBSTITUTION_AGENT_TEMPERATURE,
    SUBSTITUTION_SAFETY_MODEL,
)
from ingestion.graph_loader import query_substitutes

from agent.nodes import _ALLERGEN_TO_INGREDIENTS, _pinecone_substitute_fallback, detect_allergens


# ── Allergen safety check (intelligent, analog-aware) ────────────────────────────

def _fallback_allergen_check(substitute: str, restrictions: list[str]) -> dict:
    """Deterministic, analog-aware safety check (used only if the LLM is down).
    Delegates to the shared analog-aware detector so 'almond cheese' / 'oat milk'
    are correctly treated as milk-free."""
    violations = detect_allergens(substitute, restrictions)
    return {
        "safe":       not violations,
        "violations": violations,
        "reason":     ("contains " + ", ".join(violations)) if violations else "free of all listed allergens",
    }


def check_substitute_allergens(substitute: str, restrictions: list[str]) -> dict:
    """
    Intelligently decide whether `substitute` is free of the diner's allergens.

    Unlike substring matching, this understands food composition: "almond cheese",
    "oat milk", "vegan butter", "cashew cream" do NOT contain milk (even though
    their names include cheese/milk/butter/cream), while "cheddar cheese" does.
    It also knows analogs carry their own base allergen (almond/cashew = tree nuts,
    soy = soy, etc.). Falls back to a deterministic analog-aware check on error.

    Returns {"safe": bool, "violations": [allergen], "reason": str}.
    """
    if not restrictions:
        return {"safe": True, "violations": [], "reason": "no active restrictions"}

    allergen_list = ", ".join(restrictions)
    prompt = (
        f'Does the food item "{substitute}" actually contain any of these allergens: {allergen_list}?\n'
        "Judge by real composition, NOT by words in the name. Rules:\n"
        "- Dairy-free / plant-based analogs do NOT contain milk: almond milk, oat milk, soy cheese, "
        "vegan butter, cashew cream, coconut yogurt, nutritional yeast are MILK-FREE even though their "
        "names include cheese/milk/butter/cream.\n"
        "- Analogs DO contain their plant base allergen: almond/cashew/walnut/hazelnut/pecan = tree_nuts; "
        "soy/tofu/edamame = soy; peanut = peanuts; wheat/seitan = wheat and gluten.\n"
        f'Return ONLY JSON: {{"violations": [...]}} listing which of [{allergen_list}] are truly present.'
    )
    try:
        llm = ChatOpenAI(model=SUBSTITUTION_SAFETY_MODEL, api_key=OPENAI_API_KEY, temperature=0.0, max_tokens=120)
        raw = llm.invoke(prompt).content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        violations = [a for a in data.get("violations", []) if a in restrictions]
        return {
            "safe":       not violations,
            "violations": violations,
            "reason":     ("contains " + ", ".join(violations)) if violations else "free of all listed allergens",
        }
    except Exception:
        return _fallback_allergen_check(substitute, restrictions)


# ── Substitution agent (LLM-driven tool-calling loop) ───────────────────────────

class _SubChoice(BaseModel):
    original:   str = Field(description="the flagged allergen ingredient being replaced")
    substitute: str = Field(description="the chosen, allergen-safe substitute")
    reason:     str = Field(description="one short clause: why it fits THIS recipe's use of the ingredient")


class _RecipeSub(BaseModel):
    recipe_id:     str
    renamed_title: str = Field(description="recipe title rewritten to read naturally with the substitute")
    subs:          list[_SubChoice]


class _SubResult(BaseModel):
    recipes: list[_RecipeSub]


_SUB_AGENT_SYSTEM = """You are AlloChef's Substitution Agent. The diner is allergic to: {restrictions}.
For each recipe you are given, replace the flagged ingredient(s) with the BEST allergen-safe substitute.

CHOOSE BY CONTEXT, not by the candidate list. Think about HOW the ingredient is used in THAT recipe —
role (melt, creaminess, binder, flavour, topping), cooking method, texture — and pick a substitute that
behaves the same way. The same ingredient needs different substitutes in different dishes, e.g. for cheese:
  - melted / baked / grilled  → a shredded plant-based cheese (e.g. vegan mozzarella) that actually melts
  - stirred into a creamy sauce → cashew cream or a plant-based cream cheese
  - sprinkled on top for flavour → nutritional yeast
The provided candidates are only hints — propose a better, widely-available substitute when one fits better.

Tools:
- lookup_substitute_candidates(ingredient, allergen): known options from the knowledge base — use for ideas.
- check_allergen_safety(substitute): REQUIRED. You MUST call this on every substitute you intend to use, and
  only keep substitutes it reports as safe. Do not rely on your own judgement about names — "almond cheese" is
  milk-free but contains tree nuts; the tool knows the difference.

TITLE REWRITE (important): rewrite each recipe title so it NO LONGER implies the allergen. Replace the
allergen word AND any word derived from it ("cheesy", "creamy", "buttery", "three cheese") with the
substitute or a plant-based descriptor. Do NOT simply append the substitute. Examples:
  "Three Cheese Baked Pasta"  (sub: vegan mozzarella) → "Three-Cheese-Style Baked Pasta" or "Vegan Mozzarella Baked Pasta"
  "Cheesy Garlic Toast"       (sub: vegan cheese)     → "Vegan Cheesy Garlic Toast"
  "Butter Chicken"            (sub: olive oil)        → "Olive Oil Chicken"
The final title must not read as if it still contains the real allergen.

Give a short reason per choice referencing how the ingredient is used. Return your final answer in the
required structured format."""


def _build_substitution_tools(restrictions: list[str]):
    """Build the agent's tools, closing over the diner's restrictions so the
    safety check can't be called with the wrong allergen set."""

    @tool
    def lookup_substitute_candidates(ingredient: str, allergen: str) -> list[dict]:
        """Look up known substitute candidates for an allergen-triggering ingredient
        from the substitution knowledge base (Neo4j → Pinecone)."""
        cands = gather_candidate_substitutes(ingredient, allergen, restrictions)
        return [{"substitute": c["substitute"], "notes": c.get("notes", "")} for c in cands]

    @tool
    def check_allergen_safety(substitute: str) -> dict:
        """REQUIRED before finalizing any substitute. Verifies the substitute is free of the
        diner's allergens, understanding that dairy-free analogs like 'almond cheese', 'oat milk',
        'vegan butter', 'cashew cream' do NOT contain milk (but 'almond'/'cashew' items contain
        tree nuts, 'soy' items contain soy, etc.). Returns {safe, violations, reason}."""
        return check_substitute_allergens(substitute, restrictions)

    return [lookup_substitute_candidates, check_allergen_safety]


def run_substitution_agent(recipes: list[dict], restrictions: list[str]) -> dict:
    """
    Context-aware substitution via an LLM tool-calling agent (create_agent).

    The agent reasons per recipe, may look up candidates, MUST call the allergen
    safety tool, and returns structured choices + naturally renamed titles.

    Args:
      recipes: [{recipe_id, recipe_name, allergen, culprits:[str],
                 candidates:[{original, substitute}], recipe_text}]
    Returns:
      {recipe_id: {"renamed_title": str, "subs": [{original, substitute, reason}]}}

    Never raises — returns {} on failure so callers fall back to DB substitutes.
    """
    if not recipes:
        return {}

    blocks = []
    for r in recipes:
        cand_lines = "; ".join(
            f'{c.get("original","")} -> {c.get("substitute","")}'
            for c in r.get("candidates", [])
        ) or "none"
        steps = (r.get("recipe_text", "") or "")[:500]
        blocks.append(
            f'- recipe_id: {r.get("recipe_id","")}\n'
            f'  title: {r.get("recipe_name","")}\n'
            f'  allergen: {r.get("allergen","")}\n'
            f'  flagged ingredients: {", ".join(r.get("culprits", [])) or "n/a"}\n'
            f'  candidate substitutes: {cand_lines}\n'
            f'  how it is used: {steps}'
        )
    user_message = "Recipes to fix:\n" + "\n".join(blocks)

    try:
        model = ChatOpenAI(
            model=SUBSTITUTION_AGENT_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=SUBSTITUTION_AGENT_TEMPERATURE,
        )
        agent = create_agent(
            model=model,
            tools=_build_substitution_tools(restrictions),
            system_prompt=_SUB_AGENT_SYSTEM.format(
                restrictions=", ".join(restrictions) if restrictions else "none"
            ),
            response_format=_SubResult,
        )
        result = agent.invoke({"messages": [{"role": "user", "content": user_message}]})
        structured = result.get("structured_response")
    except Exception:
        return {}

    if not structured:
        return {}

    out: dict = {}
    for r in structured.recipes:
        safe_subs = []
        for s in r.subs:
            substitute = (s.substitute or "").strip()
            if not substitute:
                continue
            # backstop: re-verify safety even if the agent skipped the tool (defense in depth)
            if not check_substitute_allergens(substitute, restrictions)["safe"]:
                continue
            safe_subs.append({
                "original":   (s.original or "").strip(),
                "substitute": substitute,
                "reason":     (s.reason or "").strip(),
            })
        if safe_subs:
            out[r.recipe_id] = {
                "renamed_title": (r.renamed_title or "").strip(),
                "subs":          safe_subs,
            }
    return out


# ── Candidate lookup (shared by both the recipe and grocery flows) ──────────────

def gather_candidate_substitutes(
    ingredient: str,
    allergen: str,
    restrictions: list[str],
) -> list[dict]:
    """
    Candidate substitutes for one ingredient, two-tier:
      Tier 1 — Neo4j knowledge graph (deterministic, curated)
      Tier 2 — Pinecone semantic search (only if Neo4j yields no safe candidate)
    Any candidate that would reintroduce another active restriction is dropped.

    This is the single source of truth for substitute lookup — used by both the
    grocery flow (find_safe_substitute_tool) and the recipe recommendation flow
    (find_recipe_substitutions).
    """
    # deterministic, analog-aware safety filter (no LLM cost on the grocery path)
    def _is_safe(name: str) -> bool:
        return _fallback_allergen_check(name, restrictions)["safe"]

    # Tier 1: Neo4j
    try:
        neo4j_subs = query_substitutes(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, ingredient, allergen)
    except Exception:
        neo4j_subs = []  # Neo4j unavailable — fall through to Pinecone
    candidates = [
        {"original": ingredient, "substitute": s["substitute"],
         "works_in": s.get("works_in", []), "notes": s.get("notes", ""), "source": "neo4j"}
        for s in neo4j_subs if _is_safe(s["substitute"])
    ]
    if candidates:
        return candidates

    # Tier 2: Pinecone semantic fallback
    try:
        pinecone_subs = _pinecone_substitute_fallback(ingredient, allergen)
    except Exception:
        pinecone_subs = []
    return [
        {**s, "source": "pinecone"}
        for s in pinecone_subs if _is_safe(s.get("substitute", ""))
    ]


# ── Tool ──────────────────────────────────────────────────────────────────────

def find_safe_substitute_tool(
    ingredient: str,
    allergen: str,
    restrictions: list[str],
) -> dict | None:
    """
    Find a single safe substitute for an allergen-triggering ingredient.
    Returns a substitute dict, or None if no safe substitute exists.
    """
    candidates = gather_candidate_substitutes(ingredient, allergen, restrictions)
    if candidates:
        best = candidates[0]
        return {
            "original":   ingredient,
            "substitute": best["substitute"],
            "allergen":   allergen,
            "notes":      best.get("notes", ""),
            "source":     best.get("source", ""),
        }
    return None


# ── Recipe-recommendation substitution (used by the RAG graph node) ─────────────

def find_recipe_substitutions(
    unsafe_pairs: list[dict],
    restrictions: list[str],
) -> tuple[list[dict], list]:
    """
    Full substitution pass for the recipe-recommendation flow.

    For each unsafe recipe + allergen:
      1. Find the flagged (culprit) ingredients actually present in the recipe.
      2. Gather candidate substitutes for them (gather_candidate_substitutes).
      3. Let the substitution agent pick the best context-aware substitute and a
         natural renamed title (select_intelligent_substitutions), with DB picks
         kept as a fallback.

    Returns (substitutions, newly_safe_docs) — the caller adds the newly-safe
    docs to its safe-recipe list. State-agnostic so the graph node stays thin.
    """
    substitutions: list[dict] = []
    newly_safe:    list       = []

    for pair in unsafe_pairs:
        doc         = pair["doc"]
        recipe_name = doc.metadata.get("name", "Unknown recipe")
        recipe_id   = doc.metadata.get("recipe_id", "")
        recipe_text = (doc.page_content + " " + doc.metadata.get("text", "")).lower()

        for allergen in pair["allergens"]:
            allergen_ings = _ALLERGEN_TO_INGREDIENTS.get(allergen, [])
            # prefer longer (more specific) matches first: "shrimp paste" before "shrimp"
            culprits = sorted(
                {ing for ing in allergen_ings if ing in recipe_text},
                key=len, reverse=True,
            )
            if not culprits:
                continue

            available: list[dict] = []
            for ingredient in culprits:
                available.extend(gather_candidate_substitutes(ingredient, allergen, restrictions))

            if available:
                substitutions.append({
                    "recipe_name":           recipe_name,
                    "recipe_id":             recipe_id,
                    "allergen":              allergen,
                    "culprits":              culprits,
                    "recipe_text":           doc.page_content,
                    "available_substitutes": available,
                })
                newly_safe.append(doc)

    # context-aware selection + natural title rewrite (falls back to DB picks)
    if substitutions:
        payload = [
            {
                "recipe_id":   e["recipe_id"],
                "recipe_name": e["recipe_name"],
                "allergen":    e["allergen"],
                "culprits":    e.get("culprits", []),
                "candidates":  [
                    {"original": s["original"], "substitute": s["substitute"]}
                    for s in e["available_substitutes"]
                ],
                "recipe_text": e.get("recipe_text", ""),
            }
            for e in substitutions
        ]
        smart = run_substitution_agent(payload, restrictions)
        for e in substitutions:
            res = smart.get(e["recipe_id"])
            if not res:
                continue
            e["renamed_title"] = res.get("renamed_title", "")
            chosen = res.get("subs", [])
            if chosen:
                e["available_substitutes"] = [
                    {
                        "original":   c["original"],
                        "substitute": c["substitute"],
                        "works_in":   [],
                        "notes":      c.get("reason", ""),
                        "reason":     c.get("reason", ""),
                        "source":     "agent",
                    }
                    for c in chosen
                ] + e["available_substitutes"]
                e["reason"] = chosen[0].get("reason", "")

    return substitutions, newly_safe
