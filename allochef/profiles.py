"""
Persistent family profiles backed by SQLite.

Schema:
  members(id INTEGER PK, name TEXT UNIQUE)
  allergens(id INTEGER PK, member_id FK, allergen TEXT)

Usage:
  from profiles import add_member, remove_member, set_allergens, load_profiles

  add_member("Maya")
  set_allergens("Maya", ["milk", "tree_nuts"])
  profiles = load_profiles()
  # {"Maya": ["milk", "tree_nuts"], "Leo": ["peanuts"]}
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import PROFILES_DB


@contextmanager
def _conn():
    con = sqlite3.connect(PROFILES_DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS members (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS allergens (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
                allergen  TEXT    NOT NULL,
                UNIQUE(member_id, allergen)
            );
        """)


def add_member(name: str) -> None:
    with _conn() as con:
        con.execute("INSERT OR IGNORE INTO members(name) VALUES (?)", (name.strip(),))


def remove_member(name: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM members WHERE name = ?", (name.strip(),))


def set_allergens(name: str, allergens: list[str]) -> None:
    """Replace all allergens for a member."""
    with _conn() as con:
        row = con.execute("SELECT id FROM members WHERE name = ?", (name.strip(),)).fetchone()
        if not row:
            con.execute("INSERT INTO members(name) VALUES (?)", (name.strip(),))
            row = con.execute("SELECT id FROM members WHERE name = ?", (name.strip(),)).fetchone()
        member_id = row[0]
        con.execute("DELETE FROM allergens WHERE member_id = ?", (member_id,))
        con.executemany(
            "INSERT OR IGNORE INTO allergens(member_id, allergen) VALUES (?, ?)",
            [(member_id, a.strip()) for a in allergens],
        )


def get_allergens(name: str) -> list[str]:
    with _conn() as con:
        rows = con.execute(
            "SELECT allergen FROM allergens JOIN members ON members.id = allergens.member_id WHERE members.name = ?",
            (name.strip(),),
        ).fetchall()
    return [r[0] for r in rows]


def list_members() -> list[str]:
    with _conn() as con:
        rows = con.execute("SELECT name FROM members ORDER BY name").fetchall()
    return [r[0] for r in rows]


def load_profiles() -> dict[str, list[str]]:
    """Return {member_name: [allergen, ...]} for all members."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT m.name, a.allergen
            FROM members m
            LEFT JOIN allergens a ON a.member_id = m.id
            ORDER BY m.name
            """
        ).fetchall()

    profiles: dict[str, list[str]] = {}
    for name, allergen in rows:
        profiles.setdefault(name, [])
        if allergen:
            profiles[name].append(allergen)
    return profiles


# initialise on import so the DB and tables always exist
init_db()
