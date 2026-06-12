"""
AlloChef evaluation suite.

Metrics
-------
faithfulness     % of cases where the LLM response is grounded (not hallucinated / fallback)
retrieval_recall % of cases where Pinecone returns docs the relevance judge considers relevant
allergen_recall  % of allergen cases where at least the expected min unsafe recipes are flagged
sub_accuracy     % of substitution cases where the expected substitute appears in the pipeline output
sub_applied      % of substitution cases where the allergen word is absent from the LLM-generated steps
fallback_rate    % of cases that ended in the honest-fallback response

Usage
-----
  cd allochef/
  python3 -m eval.run_eval
  python3 -m eval.run_eval --cases data/eval/eval_cases.json --out data/eval/results/run.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.graph import graph

# ── helpers ───────────────────────────────────────────────────────────────────

def _run_case(case: dict) -> dict:
    """Invoke the graph for one eval case and return the raw result."""
    return graph.invoke({
        "ingredients":         case["ingredients"],
        "active_members":      case.get("active_members", []),
        "family_profiles":     case.get("family_profiles", {}),
        "messages":            [],
        "retrieval_attempts":  0,
        "generation_attempts": 0,
    })


def _is_fallback(result: dict) -> bool:
    resp = result.get("response", "")
    return (
        result.get("hallucination_verdict") == "unknown"
        or "wasn't able" in resp.lower()
        or "i don't" in resp.lower()
    )


def _parse_steps(response: str) -> list[str]:
    """Return all numbered step lines from the structured LLM response."""
    steps: list[str] = []
    in_steps = False
    for line in response.splitlines():
        stripped = line.strip()
        if re.match(r"^steps\s*:", stripped, re.IGNORECASE):
            in_steps = True
            continue
        if stripped == "---":
            in_steps = False
            continue
        if re.match(r"^ingredients\s*:", stripped, re.IGNORECASE):
            in_steps = False
            continue
        if in_steps:
            m = re.match(r"^\d+\.\s*(.+)", stripped)
            if m:
                steps.append(m.group(1).lower())
    return steps


def _parse_ingredients(response: str) -> list[str]:
    """Return all ingredient lines from the structured LLM response."""
    ings: list[str] = []
    in_ings = False
    for line in response.splitlines():
        stripped = line.strip()
        if re.match(r"^ingredients\s*:", stripped, re.IGNORECASE):
            in_ings = True
            continue
        if stripped == "---" or re.match(r"^steps\s*:", stripped, re.IGNORECASE):
            in_ings = False
            continue
        if in_ings and stripped.startswith("-"):
            ings.append(stripped.lstrip("- ").strip().lower())
    return ings


# ── per-check evaluators ──────────────────────────────────────────────────────

def check_retrieval_relevant(result: dict, expected: bool) -> tuple[bool, str]:
    verdict = result.get("relevance_verdict", "relevant")
    actual  = (verdict == "relevant")
    if actual == expected:
        return True, f"retrieval={verdict}"
    return False, f"expected retrieval={'relevant' if expected else 'not_relevant'}, got {verdict}"


def check_faithfulness(result: dict) -> tuple[bool, str]:
    if _is_fallback(result):
        return False, "fallback response — cannot assess faithfulness"
    verdict = result.get("hallucination_verdict", "")
    if verdict == "grounded":
        return True, "hallucination=grounded"
    return False, f"hallucination={verdict}"


def check_no_fallback(result: dict) -> tuple[bool, str]:
    if _is_fallback(result):
        return False, "unexpected fallback response"
    return True, "no fallback"


def check_expect_fallback(result: dict) -> tuple[bool, str]:
    if _is_fallback(result):
        return True, "fallback as expected"
    return False, "expected fallback but got a response"


def check_min_safe(result: dict, minimum: int) -> tuple[bool, str]:
    safe = result.get("safe_recipes", [])
    unique = len({d.metadata.get("recipe_id") for d in safe})
    if unique >= minimum:
        return True, f"safe_recipes={unique} (>= {minimum})"
    return False, f"safe_recipes={unique} (< {minimum})"


def check_max_unsafe(result: dict, maximum: int) -> tuple[bool, str]:
    unsafe = result.get("unsafe_pairs", [])
    unique = len({p["doc"].metadata.get("recipe_id") for p in unsafe})
    if unique <= maximum:
        return True, f"unsafe={unique} (<= {maximum})"
    return False, f"unsafe={unique} (> {maximum})"


def check_min_unsafe(result: dict, minimum: int) -> tuple[bool, str]:
    unsafe = result.get("unsafe_pairs", [])
    unique = len({p["doc"].metadata.get("recipe_id") for p in unsafe})
    if unique >= minimum:
        return True, f"unsafe_recipes={unique} (>= {minimum})"
    return False, f"unsafe_recipes={unique} (< {minimum})"


def check_expected_restrictions(result: dict, expected: list[str]) -> tuple[bool, str]:
    actual = sorted(result.get("restrictions", []))
    exp    = sorted(expected)
    if actual == exp:
        return True, f"restrictions={actual}"
    return False, f"restrictions: expected {exp}, got {actual}"


def check_substitution_accuracy(result: dict, sub_spec: dict) -> tuple[bool, str]:
    """At least one expected substitute option must appear in the pipeline output."""
    original = sub_spec["original"].lower()
    options  = [o.lower() for o in sub_spec["expected_options"]]
    subs     = result.get("substitutions", [])
    for entry in subs:
        for s in entry.get("available_substitutes", []):
            if s.get("original", "").lower() == original:
                found = s.get("substitute", "").lower()
                if any(opt in found or found in opt for opt in options):
                    return True, f"sub: {original} → {s['substitute']} [{s.get('source', '?')}]"
    return False, f"no substitute found for '{original}' in {options}"


def check_allergen_absent_from_steps(result: dict, allergen_word: str) -> tuple[bool, str]:
    """
    The allergen word must not appear in ANY step line across the response.
    Recipe names (bold **...**) are excluded — we only check step text.
    """
    response = result.get("response", "")
    steps    = _parse_steps(response)
    ings     = _parse_ingredients(response)
    word     = allergen_word.lower()

    step_hits = [s for s in steps if word in s]
    ing_hits  = [i for i in ings if word in i]

    if not step_hits and not ing_hits:
        return True, f"'{allergen_word}' absent from steps and ingredients"
    details = []
    if step_hits:
        details.append(f"found in steps: {step_hits[:2]}")
    if ing_hits:
        details.append(f"found in ingredients: {ing_hits[:2]}")
    return False, f"'{allergen_word}' still present — " + "; ".join(details)


# ── case runner ───────────────────────────────────────────────────────────────

def evaluate_case(case: dict) -> dict:
    case_id     = case["id"]
    description = case["description"]
    checks_spec = case.get("checks", {})

    print(f"  Running {case_id} …", end=" ", flush=True)
    result = _run_case(case)

    passed: list[str]   = []
    failed: list[str]   = []
    skipped: list[str]  = []

    def run(label: str, fn, *args):
        ok, note = fn(*args)
        (passed if ok else failed).append(f"{label}: {note}")

    # retrieval relevance
    if "retrieval_relevant" in checks_spec:
        run("retrieval_relevant", check_retrieval_relevant,
            result, checks_spec["retrieval_relevant"])

    # faithfulness
    if checks_spec.get("faithfulness"):
        run("faithfulness", check_faithfulness, result)

    # fallback checks
    if checks_spec.get("no_fallback"):
        run("no_fallback", check_no_fallback, result)
    if checks_spec.get("expect_fallback"):
        run("expect_fallback", check_expect_fallback, result)

    # recipe counts
    if "min_safe_recipes" in checks_spec:
        run("min_safe_recipes", check_min_safe, result, checks_spec["min_safe_recipes"])
    if "max_unsafe_recipes" in checks_spec:
        run("max_unsafe_recipes", check_max_unsafe, result, checks_spec["max_unsafe_recipes"])
    if "min_unsafe_recipes" in checks_spec:
        run("min_unsafe_recipes", check_min_unsafe, result, checks_spec["min_unsafe_recipes"])

    # restriction aggregation
    if "expected_restrictions" in checks_spec:
        run("restrictions", check_expected_restrictions,
            result, checks_spec["expected_restrictions"])

    # substitution accuracy (one check per sub spec)
    for sub_spec in checks_spec.get("substitutions", []):
        label = f"sub_accuracy[{sub_spec['original']}]"
        run(label, check_substitution_accuracy, result, sub_spec)

    # allergen absent from LLM output
    if "allergen_absent_from_steps" in checks_spec:
        word = checks_spec["allergen_absent_from_steps"]
        run(f"allergen_absent[{word}]", check_allergen_absent_from_steps, result, word)

    status = "PASS" if not failed else "FAIL"
    print(status)

    return {
        "id":          case_id,
        "description": description,
        "status":      status,
        "passed":      passed,
        "failed":      failed,
        "skipped":     skipped,
        "raw": {
            "relevance_verdict":     result.get("relevance_verdict"),
            "hallucination_verdict": result.get("hallucination_verdict"),
            "is_fallback":           _is_fallback(result),
            "safe_count":            len({d.metadata.get("recipe_id") for d in result.get("safe_recipes", [])}),
            "unsafe_count":          len({p["doc"].metadata.get("recipe_id") for p in result.get("unsafe_pairs", [])}),
            "substitution_count":    len(result.get("substitutions", [])),
            "generation_attempts":   result.get("generation_attempts", 0),
            "retrieval_attempts":    result.get("retrieval_attempts", 0),
        },
    }


# ── aggregate scoring ─────────────────────────────────────────────────────────

def score_results(results: list[dict]) -> dict[str, Any]:
    """Roll up per-case results into metric scores."""
    metrics: dict[str, list[bool]] = {
        "faithfulness":     [],
        "retrieval_recall": [],
        "allergen_recall":  [],
        "sub_accuracy":     [],
        "sub_applied":      [],
    }
    fallbacks = 0

    for r in results:
        raw = r["raw"]
        all_checks = r["passed"] + r["failed"]

        if raw["is_fallback"]:
            fallbacks += 1

        # faithfulness — any case that has this check
        faith_checks = [c for c in all_checks if c.startswith("faithfulness:")]
        for c in faith_checks:
            metrics["faithfulness"].append(c in r["passed"])

        # retrieval recall
        ret_checks = [c for c in all_checks if c.startswith("retrieval_relevant:")]
        for c in ret_checks:
            metrics["retrieval_recall"].append(c in r["passed"])

        # allergen recall (min_unsafe_recipes check)
        allergen_checks = [c for c in all_checks if c.startswith("min_unsafe_recipes:")]
        for c in allergen_checks:
            metrics["allergen_recall"].append(c in r["passed"])

        # substitution accuracy
        sub_checks = [c for c in all_checks if c.startswith("sub_accuracy[")]
        for c in sub_checks:
            metrics["sub_accuracy"].append(c in r["passed"])

        # substitution applied (allergen absent)
        absent_checks = [c for c in all_checks if c.startswith("allergen_absent[")]
        for c in absent_checks:
            metrics["sub_applied"].append(c in r["passed"])

    def pct(lst):
        if not lst:
            return None
        n = sum(lst)
        return {"passed": n, "total": len(lst), "pct": round(100 * n / len(lst), 1)}

    return {
        "faithfulness":     pct(metrics["faithfulness"]),
        "retrieval_recall": pct(metrics["retrieval_recall"]),
        "allergen_recall":  pct(metrics["allergen_recall"]),
        "sub_accuracy":     pct(metrics["sub_accuracy"]),
        "sub_applied":      pct(metrics["sub_applied"]),
        "fallback_rate":    {"triggered": fallbacks, "total": len(results),
                             "pct": round(100 * fallbacks / len(results), 1)},
    }


# ── report printer ────────────────────────────────────────────────────────────

def print_report(results: list[dict], scores: dict) -> None:
    width = 70
    ts    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print()
    print("=" * width)
    print(f"  AlloChef Evaluation  —  {ts}")
    print("=" * width)

    for r in results:
        icon = "✓" if r["status"] == "PASS" else "✗"
        raw  = r["raw"]
        meta = (f"  safe={raw['safe_count']} unsafe={raw['unsafe_count']}"
                f"  subs={raw['substitution_count']}"
                f"  attempts={raw['generation_attempts']}")
        print(f"\n  {icon} {r['id']}")
        print(f"    {r['description']}")
        print(f"   {meta}")
        for note in r["passed"]:
            print(f"    ✓ {note}")
        for note in r["failed"]:
            print(f"    ✗ {note}")

    print()
    print("-" * width)
    print("  METRIC SCORES")
    print("-" * width)

    def fmt(label: str, s):
        if s is None:
            return f"  {label:<24}  n/a"
        return f"  {label:<24}  {s['passed']}/{s['total']}  ({s['pct']}%)"

    print(fmt("faithfulness",     scores["faithfulness"]))
    print(fmt("retrieval_recall", scores["retrieval_recall"]))
    print(fmt("allergen_recall",  scores["allergen_recall"]))
    print(fmt("sub_accuracy",     scores["sub_accuracy"]))
    print(fmt("sub_applied",      scores["sub_applied"]))

    fb = scores["fallback_rate"]
    print(f"  {'fallback_rate':<24}  {fb['triggered']}/{fb['total']}  ({fb['pct']}%)")

    total_checks  = sum(len(r["passed"]) + len(r["failed"]) for r in results)
    total_passed  = sum(len(r["passed"]) for r in results)
    overall_cases = sum(1 for r in results if r["status"] == "PASS")
    print()
    print(f"  Cases:   {overall_cases}/{len(results)} passed")
    print(f"  Checks:  {total_passed}/{total_checks} passed  "
          f"({round(100*total_passed/total_checks, 1) if total_checks else 0}%)")
    print("=" * width)
    print()


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run AlloChef evaluation suite")
    parser.add_argument(
        "--cases",
        default=str(Path(__file__).parent.parent / "data" / "eval" / "eval_cases.json"),
        help="Path to eval cases JSON",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write results JSON",
    )
    parser.add_argument(
        "--ids",
        nargs="*",
        help="Run only specific case IDs (space-separated)",
    )
    args = parser.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"ERROR: cases file not found: {cases_path}")
        sys.exit(1)

    with open(cases_path) as f:
        all_cases = json.load(f)

    cases = all_cases
    if args.ids:
        cases = [c for c in all_cases if c["id"] in args.ids]
        if not cases:
            print(f"ERROR: no cases matched IDs: {args.ids}")
            sys.exit(1)

    print(f"\nRunning {len(cases)} eval case(s)…\n")
    results = [evaluate_case(c) for c in cases]
    scores  = score_results(results)

    print_report(results, scores)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cases_file": str(cases_path),
            "scores":     scores,
            "results":    results,
        }
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"Results saved → {out_path}")


if __name__ == "__main__":
    main()
