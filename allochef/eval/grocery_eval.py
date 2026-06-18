"""
Grocery planner eval — runs 3 scenarios against the tool functions directly
(no network calls, no LangGraph execution overhead).

Run:
  cd allochef
  python -m eval.grocery_eval
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.safety_tools import check_grocery_safety_tool
from agent.grocery_agent import create_cart_draft_tool
from agent.pantry_tools import compare_pantry_tool

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results: list[dict] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = PASS if condition else FAIL
    print(f"  {status}  {label}")
    if not condition and detail:
        print(f"       {detail}")
    results.append({"label": label, "passed": condition})


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — pantry has most ingredients; butter is unsafe (milk allergy)
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Scenario 1: garlic chicken over rice (Maya has milk allergy) ──")

pantry_s1 = [
    {"item_name": "chicken", "normalized_name": "chicken"},
    {"item_name": "garlic",  "normalized_name": "garlic"},
    {"item_name": "onion",   "normalized_name": "onion"},
]
recipe_s1 = ["chicken breast", "garlic cloves", "onion", "butter", "rice", "fresh parsley"]

pantry_result = compare_pantry_tool(recipe_s1, pantry_s1)
check("chicken breast matched from pantry",  "chicken breast" in pantry_result["already_have"])
check("garlic cloves matched from pantry",   "garlic cloves"  in pantry_result["already_have"])
check("onion matched from pantry",           "onion"          in pantry_result["already_have"])
check("butter in missing_ingredients",       "butter"         in pantry_result["missing_ingredients"])
check("rice in missing_ingredients",         "rice"           in pantry_result["missing_ingredients"])
check("parsley in missing_ingredients",      "fresh parsley"  in pantry_result["missing_ingredients"])

safety_result = check_grocery_safety_tool(
    pantry_result["missing_ingredients"],
    restrictions=["milk"],
)
check("butter flagged unsafe (milk)",  any(u["ingredient"] == "butter" for u in safety_result["unsafe_missing_items"]))
check("rice is safe",                  "rice"         in safety_result["safe_missing_items"])
check("parsley is safe",               "fresh parsley" in safety_result["safe_missing_items"])

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — empty pantry (all ingredients missing, no allergen conflicts)
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Scenario 2: empty pantry, no allergen restrictions ──")

recipe_s2 = ["olive oil", "chicken", "lemon", "rosemary", "garlic"]
pantry_result_2 = compare_pantry_tool(recipe_s2, pantry_items=[])

check("already_have is empty for empty pantry", pantry_result_2["already_have"] == [])
check("all ingredients are missing",            len(pantry_result_2["missing_ingredients"]) == len(recipe_s2))

safety_result_2 = check_grocery_safety_tool(
    pantry_result_2["missing_ingredients"],
    restrictions=[],
)
check("all items safe with no restrictions", len(safety_result_2["safe_missing_items"]) == len(recipe_s2))
check("no unsafe items",                     safety_result_2["unsafe_missing_items"] == [])

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — uncertain pantry match & cart draft creation
# ─────────────────────────────────────────────────────────────────────────────

print("\n── Scenario 3: uncertain pantry match (tomato vs tomato paste) ──")

pantry_s3 = [
    {"item_name": "tomato", "normalized_name": "tomato"},
    {"item_name": "olive oil", "normalized_name": "olive oil"},
]
recipe_s3 = ["tomato paste", "olive oil", "pasta", "garlic"]

pantry_result_3 = compare_pantry_tool(recipe_s3, pantry_s3)
check("olive oil matched from pantry",      "olive oil"   in pantry_result_3["already_have"])
check("tomato paste flagged as uncertain",
      any(u["recipe_ingredient"] == "tomato paste" for u in pantry_result_3["uncertain_matches"]))
check("pasta in missing",                   "pasta"       in pantry_result_3["missing_ingredients"])
check("garlic in missing",                  "garlic"      in pantry_result_3["missing_ingredients"])

# Cart draft creation
cart = create_cart_draft_tool([
    {"name": "rice"},
    {"name": "fresh parsley"},
    {"name": "olive oil"},
])
check("cart has items",                           len(cart["items"]) == 3)
check("cart status is draft",                     cart["status"] == "draft")
check("cart has created_at timestamp",            bool(cart.get("created_at")))
check("cart note says no order placed",           "No real order" in cart.get("note", ""))
check("rice categorised as pantry",               any(i["name"] == "rice"          and i["category"] == "pantry"  for i in cart["items"]))
check("olive oil categorised as pantry",          any(i["name"] == "olive oil"     and i["category"] == "pantry"  for i in cart["items"]))

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

total  = len(results)
passed = sum(1 for r in results if r["passed"])
print(f"\n── Results: {passed}/{total} passed ──\n")

# Write JSON log
out_path = Path(__file__).parent / "grocery_eval_results.json"
with open(out_path, "w") as f:
    json.dump(
        {
            "total":   total,
            "passed":  passed,
            "failed":  total - passed,
            "results": results,
        },
        f,
        indent=2,
    )
print(f"Results written to {out_path}\n")

if passed < total:
    sys.exit(1)
