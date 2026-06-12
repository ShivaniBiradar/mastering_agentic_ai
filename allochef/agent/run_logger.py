"""
Structured logging for AlloChef agent checker nodes.

Every relevance check and hallucination check writes one JSONL entry to
logs/agent_checks.jsonl so you can review what the LLM judges decided and why.

Entry format:
  {
    "timestamp":  "2026-06-11T10:23:45.123Z",
    "event":      "relevance_check" | "hallucination_check" | "fallback_triggered",
    "query":      "chicken garlic tomatoes",
    "verdict":    "relevant" | "not_relevant" | "grounded" | "hallucinating",
    "reason":     "recipes are pasta dishes, user has chicken and ginger",
    "llm_raw":    "no - recipes are pasta dishes, user has chicken and ginger",
    ...event-specific fields...
  }

Usage:
  from agent.run_logger import log_check
  log_check("relevance_check", query=..., verdict=..., reason=..., llm_raw=..., ...)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

LOG_DIR  = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "agent_checks.jsonl"

# console logger — shows up in Streamlit terminal and pytest output
_logger = logging.getLogger("allochef.agent")


def log_check(event: str, **fields) -> None:
    """
    Append one structured entry to logs/agent_checks.jsonl and emit a
    console log line.

    Args:
        event:   event type string, e.g. "relevance_check"
        **fields: any key-value pairs to include in the entry
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event":     event,
        **fields,
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # compact console line — omit long fields like full context/response
    console_fields = {
        k: v for k, v in fields.items()
        if k not in ("context", "docs_summary", "response_snippet")
    }
    _logger.info("[%s] %s", event, json.dumps(console_fields))


def read_recent_checks(n: int = 20) -> list[dict]:
    """Return the n most recent log entries — useful for Streamlit debug panel."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines[-n:]]
