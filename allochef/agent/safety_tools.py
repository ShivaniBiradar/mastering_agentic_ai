"""
Safety tools — deterministic allergen triage for grocery items.

Plain functions (not an LLM agent). The Grocery Agent calls
check_grocery_safety_tool to split the items it needs to buy into safe vs.
unsafe against the family's active allergens, then routes the unsafe ones to
the Substitution Agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.nodes import detect_allergens


# ── Tool ──────────────────────────────────────────────────────────────────────

def check_grocery_safety_tool(
    items: list[str],
    restrictions: list[str],
) -> dict:
    """
    Classify grocery items as safe or unsafe against active allergen restrictions.

    Uses the shared analog-aware detector (detect_allergens), so a dairy-free
    analog like "almond milk" is NOT flagged for a milk allergy just because
    "milk" appears in its name (it would still trip a tree-nut restriction).

    Returns:
      safe_missing_items   — items that triggered no restriction
      unsafe_missing_items — [{ingredient, allergens:[str]}] for flagged items
    """
    safe:   list[str]  = []
    unsafe: list[dict] = []

    for item in items:
        triggered = detect_allergens(item, restrictions)
        if triggered:
            unsafe.append({"ingredient": item, "allergens": triggered})
        else:
            safe.append(item)

    return {"safe_missing_items": safe, "unsafe_missing_items": unsafe}
