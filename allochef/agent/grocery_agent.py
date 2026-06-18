"""
Grocery Agent — an LLM tool-calling agent (create_agent) that turns a chosen
recipe into a grocery plan: it diffs the pantry, triages the missing items for
allergens, gets safe substitutes for the unsafe ones, and assembles a
normalized shopping list with quantities.

It is a real agent (it sequences the tools and can act on natural-language notes
like "I already have rice"), but a deterministic backfill guarantees the full
safe pipeline always runs even if the LLM skips a step — so the plan is never
unsafe. It deliberately does NOT create the cart or take approval: that stays a
deterministic, human-gated step in the UI (build_cart), called only after the
user approves the plan.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from openai import OpenAI

from agent.instacart_mcp import create_instacart_shopping_list
from agent.pantry_tools import compare_pantry_tool
from agent.safety_tools import check_grocery_safety_tool
from agent.substitution_agent import find_safe_substitute_tool
from config import (
    CART_PROVIDER,
    GROCERY_AGENT_MODEL,
    NEBIUS_API_KEY,
    NEBIUS_BASE_URL,
    NEBIUS_MODEL,
    OPENAI_API_KEY,
)
from pantry import list_pantry_items, normalize_item


# ── Nebius Tool ───────────────────────────────────────────────────────────────

def nebius_normalize_items(items: list[str]) -> list[dict]:
    """
    Use Nebius Token Factory to normalize raw grocery item names into
    structured, shopping-ready entries with a clean display name and category.

    Falls back to deterministic passthrough if NEBIUS_API_KEY is not set or
    the call fails — the rest of the workflow continues unaffected.

    Example:
      Input:  ["2 garlic cloves", "long grain white rice", "fresh parsley"]
      Output: [
        {"ingredient": "garlic cloves", "shopping_query": "garlic bulb",       "category": "produce"},
        {"ingredient": "long grain white rice", "shopping_query": "long grain white rice", "category": "pantry"},
        {"ingredient": "fresh parsley",  "shopping_query": "fresh parsley",    "category": "produce"},
      ]
    """
    if not NEBIUS_API_KEY or not items:
        return [{"ingredient": i, "shopping_query": i, "category": "other"} for i in items]

    client = OpenAI(api_key=NEBIUS_API_KEY, base_url=NEBIUS_BASE_URL)

    prompt = (
        "You are a grocery shopping assistant. "
        "Convert the following raw recipe ingredient names into clean, shopping-ready entries. " \
        "Preserve all meaningful grocery descriptors. Do not generalize the item if descriptors affect what the user needs to buy."
        "Return a JSON array — one object per item — with these exact keys:\n"
        '  "ingredient"     : the simplified ingredient name (no quantities or prep notes)\n'
        '  "shopping_query" : the best search term to find this item in a grocery store\n'
        '  "category"       : one of produce, protein, dairy, pantry, spices, other\n\n'
        "Return ONLY the JSON array. No explanation, no markdown fences.\n\n"
        f"Items: {json.dumps(items)}"
    )

    try:
        response = client.chat.completions.create(
            model=NEBIUS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        raw = response.choices[0].message.content.strip()
        # strip markdown fences if the model added them anyway
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return parsed
    except Exception as exc:  # noqa: BLE001
        # Nebius is optional — log once why we're falling back, then continue.
        # A 404 usually means a wrong NEBIUS_BASE_URL (host moved to .com) or model.
        print(f"[nebius] normalization unavailable, using raw item names: {exc}")

    # deterministic fallback
    return [{"ingredient": i, "shopping_query": i, "category": "other"} for i in items]


# ── Tool ──────────────────────────────────────────────────────────────────────

def create_cart_draft_tool(items: list[dict]) -> dict:
    """
    Mock cart draft tool — builds a structured cart without calling any real
    shopping service. Swap this implementation for an Instacart MCP call when
    ready; the rest of the graph does not need to change.
    """
    _CATEGORIES: dict[str, set[str]] = {
        "produce": {"garlic", "onion", "tomato", "potato", "carrot", "celery",
                    "pepper", "spinach", "broccoli", "mushroom", "parsley",
                    "cilantro", "basil", "ginger", "lemon", "lime", "lemon juice"},
        "protein": {"chicken", "beef", "pork", "turkey", "tofu", "egg", "salmon",
                    "tuna", "shrimp", "lamb", "sausage"},
        "dairy":   {"milk", "butter", "cream", "cheese", "yogurt", "sour cream",
                    "heavy cream", "cream cheese"},
        "pantry":  {"rice", "pasta", "flour", "oil", "olive oil", "vinegar",
                    "soy sauce", "sugar", "salt", "bread", "breadcrumbs",
                    "stock", "broth", "canned"},
        "spices":  {"cumin", "paprika", "oregano", "thyme", "rosemary", "sage",
                    "cinnamon", "chili", "pepper", "turmeric"},
    }

    def _categorise(name: str) -> str:
        n = name.lower()
        for cat, keywords in _CATEGORIES.items():
            if any(kw in n for kw in keywords):
                return cat
        return "other"

    def _fmt_amount(amount) -> str:
        try:
            f = float(amount)
            return str(int(f)) if f == int(f) else str(f)
        except (TypeError, ValueError):
            return str(amount or "1")

    cart_items = [
        {
            "name":     item["name"],
            "amount":   _fmt_amount(item.get("amount", 1)),
            "unit":     item.get("unit", "each"),
            "quantity": f'{_fmt_amount(item.get("amount", 1))} {item.get("unit", "each")}',
            # use a real category if provided (e.g. from Nebius); else categorise locally
            "category": item["category"] if item.get("category") not in (None, "", "other")
                        else _categorise(item["name"]),
        }
        for item in items
    ]

    return {
        "items":      cart_items,
        "status":     "draft",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "note":       "Cart draft created. No real order has been placed.",
    }


# ── Grocery plan assembly (pure) ────────────────────────────────────────────────

def assemble_grocery_plan(
    recipe: dict,
    already_have: list[str],
    safe_missing: list[str],
    substitutions: list[dict],
    blocked: list[dict],
    uncertain: list[dict],
) -> dict:
    """
    Assemble the full grocery plan from the resolved ingredient sets.

    Normalizes the need-to-buy list via Nebius (shopping_query + category) and
    attaches the LLM-estimated quantities from the recipe card. Pure function —
    no state, no side effects.
    """
    recipe_name = recipe.get("name", "Selected Recipe")
    quantities  = recipe.get("quantities", {}) or {}
    norm_qty    = {normalize_item(k): v for k, v in quantities.items()}

    def _qty_for(name: str) -> dict:
        if name in quantities:
            return quantities[name]
        return norm_qty.get(normalize_item(name), {"amount": 1.0, "unit": "each"})

    need_to_buy_raw: list[str] = list(safe_missing)
    sub_qty: dict[str, dict] = {}
    for sub in substitutions:
        need_to_buy_raw.append(sub["substitute"])
        sub_qty[sub["substitute"]] = _qty_for(sub.get("original", ""))

    need_to_buy_normalized = nebius_normalize_items(need_to_buy_raw)
    for i, detail in enumerate(need_to_buy_normalized):
        raw_name = need_to_buy_raw[i] if i < len(need_to_buy_raw) else detail.get("ingredient", "")
        qty = sub_qty.get(raw_name) or _qty_for(raw_name)
        detail["amount"] = qty.get("amount", 1.0)
        detail["unit"]   = qty.get("unit", "each")

    return {
        "recipe_name":         recipe_name,
        "already_have":        already_have,
        "need_to_buy":         need_to_buy_raw,
        "need_to_buy_details": need_to_buy_normalized,
        "substitutions":       substitutions,
        "blocked":             blocked,
        "uncertain":           uncertain,
    }


# ── Grocery Agent ───────────────────────────────────────────────────────────────
#
# Design: the pantry diff, allergen safety and substitution facts are computed
# DETERMINISTICALLY and are authoritative — the LLM can't corrupt them (an LLM
# doing set-difference on your pantry is both unreliable and pointless). The
# Grocery Agent (create_agent) is used only for what genuinely needs language
# understanding: interpreting a free-text note like "I've already got spinach and
# some leftover paneer" and marking those as already-owned. No note → no LLM call.

def _compute_plan_facts(ctx: dict, recipe: dict, restrictions: list[str], household_id: str) -> None:
    """
    Authoritative, deterministic plan facts: pantry diff (honouring any items the
    user noted as already-owned) → allergen safety → substitutes. Always recomputed.
    """
    pantry = list_pantry_items(household_id)
    diff = (compare_pantry_tool(recipe.get("ingredients", []), pantry) if pantry
            else {"already_have": [], "missing_ingredients": list(recipe.get("ingredients", [])),
                  "uncertain_matches": []})
    already_have = list(diff["already_have"])
    missing      = list(diff["missing_ingredients"])

    # honour items the user explicitly said they already have (from a note)
    noted = ctx.get("noted_have", set())
    if noted:
        moved   = [m for m in missing if normalize_item(m) in noted]
        missing = [m for m in missing if normalize_item(m) not in noted]
        already_have += moved

    safety = check_grocery_safety_tool(missing, restrictions)
    unsafe = safety["unsafe_missing_items"]

    subs, blocked = [], []
    for u in unsafe:
        found = None
        for allergen in u["allergens"]:
            found = find_safe_substitute_tool(u["ingredient"], allergen, restrictions)
            if found:
                break
        if found:
            subs.append(found)
        else:
            blocked.append({"ingredient": u["ingredient"],
                            "reason": f"No safe substitute for {', '.join(u['allergens'])} allergy."})

    ctx.update({
        "already_have": already_have,
        "missing":      missing,
        "uncertain":    diff["uncertain_matches"],
        "safe":         safety["safe_missing_items"],
        "unsafe":       unsafe,
        "substitutes":  subs,
        "blocked":      blocked,
    })


_GROCERY_NOTE_SYSTEM = """You are AlloChef's Grocery Agent. The user is planning groceries for a recipe and
may mention ingredients they ALREADY have at home. Read their note and call note_already_have with exactly
those ingredients (prefer the recipe's own ingredient names). Call check_pantry if you want to see what is
currently missing. Only mark items the user clearly said they already have — never guess."""


def _build_note_agent(recipe: dict, restrictions: list[str], household_id: str, ctx: dict):
    """A small create_agent that interprets a free-text 'what I already have' note.
    It cannot touch the deterministic facts — it only records noted items, which
    _compute_plan_facts then honours."""

    @tool
    def check_pantry() -> str:
        """Show what the recipe still needs vs. what's already accounted for."""
        return f"Already accounted for: {ctx.get('already_have', [])}. Still missing: {ctx.get('missing', [])}."

    @tool
    def note_already_have(items: list[str]) -> str:
        """Record ingredients the user explicitly said they already have at home."""
        ctx.setdefault("noted_have", set()).update(normalize_item(i) for i in items if i)
        return f"Noted as already have: {sorted(ctx['noted_have'])}."

    model = ChatOpenAI(model=GROCERY_AGENT_MODEL, api_key=OPENAI_API_KEY, temperature=0.0)
    return create_agent(model=model, tools=[check_pantry, note_already_have],
                        system_prompt=_GROCERY_NOTE_SYSTEM)


def run_grocery_agent(
    recipe: dict,
    restrictions: list[str],
    household_id: str = "default",
    user_note: str = "",
) -> dict:
    """
    Produce a grocery plan for `recipe`. The pantry/safety/substitution facts are
    deterministic and authoritative; if `user_note` is given, the Grocery Agent
    interprets it (e.g. "I already have spinach") and those items are honoured.
    Returns a grocery_plan dict (no cart).
    """
    ctx: dict = {"noted_have": set()}
    _compute_plan_facts(ctx, recipe, restrictions, household_id)

    if user_note and user_note.strip():
        try:
            agent = _build_note_agent(recipe, restrictions, household_id, ctx)
            agent.invoke({"messages": [{"role": "user",
                                        "content": f"Recipe: {recipe.get('name', 'this recipe')}. "
                                                   f"What I already have: {user_note}"}]})
            _compute_plan_facts(ctx, recipe, restrictions, household_id)  # re-apply with noted items
        except Exception:
            pass  # keep the deterministic plan

    return assemble_grocery_plan(
        recipe,
        ctx["already_have"],
        ctx["safe"],
        ctx["substitutes"],
        ctx["blocked"],
        ctx["uncertain"],
    )


# ── Cart (deterministic, human-gated by the UI) ─────────────────────────────────

def create_mock_cart(items: list[dict], recipe_name: str = "") -> dict:
    """Local structured cart draft — no external service. Retries once."""
    for attempt in range(2):
        try:
            return create_cart_draft_tool(items)
        except Exception as exc:
            if attempt == 1:
                grocery_list = "\n".join(f"- {i['name']}" for i in items)
                return {
                    "items":  [],
                    "status": "error",
                    "note":   f"Cart tool failed after retry: {exc}. Manual list:\n{grocery_list}",
                }
    return {"items": [], "status": "error", "note": "Cart tool failed."}


def create_instacart_cart(items: list[dict], recipe_name: str = "") -> dict:
    """
    Real Instacart shoppable page via the Instacart MCP server.

    Still produces the local structured draft (so the UI shows the itemised
    list), then adds an `instacart_url` the user can open to add everything to
    their cart. If Instacart is unavailable (no key / network / tool error),
    the local draft still stands and `instacart_error` explains why.
    """
    cart = create_mock_cart(items, recipe_name)

    instacart = create_instacart_shopping_list(
        title=f"AlloChef — {recipe_name or 'Grocery List'}",
        items=[
            {
                "name":         i["name"],
                "display_text": i["name"],
                "quantity":     i.get("amount", 1),
                "unit":         i.get("unit", "each"),
            }
            for i in items
        ],
    )
    cart["instacart_url"]   = instacart.get("url")
    cart["instacart_error"] = instacart.get("error")
    if instacart.get("url"):
        cart["status"] = "ready"
        cart["note"]   = (
            "Shopping list created on Instacart. "
            "Open the link to add everything to your cart — no order is placed until you check out."
        )
    return cart


def build_cart(grocery_plan: dict, edits: dict | None = None, provider: str | None = None) -> dict:
    """
    Build the cart from an APPROVED grocery plan. Called by the UI only after the
    user approves — this function does not gate approval itself.

    Applies user quantity edits (from the approval modal) and dispatches to the
    configured cart backend (config.CART_PROVIDER): "instacart" (real MCP page)
    or "mock" (local structured draft, default).
    """
    edits    = edits or {}
    provider = provider or CART_PROVIDER
    recipe_name = grocery_plan.get("recipe_name", "AlloChef Grocery List")

    details = grocery_plan.get("need_to_buy_details")
    items_to_buy: list[dict] = []
    if details:
        for d in details:
            ingredient = d.get("ingredient", "")
            name       = d.get("shopping_query") or ingredient
            amount     = d.get("amount", 1.0)
            unit       = d.get("unit", "each")
            edit = edits.get(ingredient) or edits.get(name)
            if edit:
                amount = edit.get("amount", amount)
                unit   = edit.get("unit", unit)
            items_to_buy.append({"name": name, "category": d.get("category", "other"),
                                 "amount": amount, "unit": unit})
    else:
        for item in grocery_plan.get("need_to_buy", []):
            edit = edits.get(item, {})
            items_to_buy.append({"name": item, "amount": edit.get("amount", 1.0),
                                 "unit": edit.get("unit", "each")})

    if provider == "instacart":
        return create_instacart_cart(items_to_buy, recipe_name)
    return create_mock_cart(items_to_buy, recipe_name)
