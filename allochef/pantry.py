"""
Persistent pantry storage backed by SQLite (same DB as profiles.py).

Table: pantry_items
  household_id    — multi-household support; defaults to "default"
  item_name       — original string as entered by the user
  normalized_name — lowercased, punctuation-stripped, lightly singularised

Usage:
  from pantry import add_pantry_items, list_pantry_items, remove_pantry_item, clear_pantry
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import PROFILES_DB


@contextmanager
def _conn():
    con = sqlite3.connect(PROFILES_DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _init_pantry_table() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS pantry_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id    TEXT      NOT NULL DEFAULT 'default',
                item_name       TEXT      NOT NULL,
                normalized_name TEXT      NOT NULL,
                quantity        TEXT,
                unit            TEXT,
                source          TEXT      DEFAULT 'manual',
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(household_id, normalized_name)
            )
        """)


def normalize_item(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, light singularisation."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    # simple plural stripping — only for unambiguous cases
    if name.endswith("ies") and len(name) > 4:
        name = name[:-3] + "y"
    elif name.endswith("es") and len(name) > 4 and not name.endswith("ses"):
        name = name[:-2]
    elif name.endswith("s") and len(name) > 3 and not name.endswith("ss"):
        name = name[:-1]
    return name


def add_pantry_items(items: list[str], household_id: str = "default") -> None:
    rows = [
        (household_id, item.strip(), normalize_item(item))
        for item in items
        if item.strip()
    ]
    with _conn() as con:
        con.executemany(
            """
            INSERT OR REPLACE INTO pantry_items (household_id, item_name, normalized_name)
            VALUES (?, ?, ?)
            """,
            rows,
        )


def remove_pantry_item(normalized_name: str, household_id: str = "default") -> None:
    with _conn() as con:
        con.execute(
            "DELETE FROM pantry_items WHERE household_id = ? AND normalized_name = ?",
            (household_id, normalized_name),
        )


def clear_pantry(household_id: str = "default") -> None:
    with _conn() as con:
        con.execute("DELETE FROM pantry_items WHERE household_id = ?", (household_id,))


def list_pantry_items(household_id: str = "default") -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """
            SELECT item_name, normalized_name
            FROM   pantry_items
            WHERE  household_id = ?
            ORDER  BY item_name
            """,
            (household_id,),
        ).fetchall()
    return [{"item_name": r["item_name"], "normalized_name": r["normalized_name"]} for r in rows]


# create table on import so it is always present
_init_pantry_table()
