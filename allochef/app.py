"""
AlloChef — What can we cook tonight?
Streamlit UI: family profile management + allergen-safe recipe suggestions.
"""

from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path

import streamlit as st
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))

from agent.grocery_agent import build_cart, run_grocery_agent
from agent.meal_orchestrator import restrictions_for, run_meal_orchestrator
from agent.run_logger import read_recent_checks
from config import ALLERGEN_NAMES, OPENAI_API_KEY
from pantry import add_pantry_items, clear_pantry, list_pantry_items, remove_pantry_item
from profiles import (
    add_member,
    get_allergens,
    list_members,
    load_profiles,
    remove_member,
    set_allergens,
)

# ── Constants ─────────────────────────────────────────────────────────────────

ALLERGEN_LABELS: dict[str, str] = {
    "milk":      "Milk / Dairy",
    "eggs":      "Eggs",
    "fish":      "Fish",
    "shellfish": "Shellfish",
    "tree_nuts": "Tree Nuts",
    "peanuts":   "Peanuts",
    "wheat":     "Wheat",
    "gluten":    "Gluten",
    "soy":       "Soy",
    "sesame":    "Sesame",
}

ALLERGEN_COLORS: dict[str, str] = {
    "milk":      "#FFE0D6",
    "eggs":      "#FFF8D6",
    "fish":      "#D6EEFF",
    "shellfish": "#D6F4FF",
    "tree_nuts": "#EDE0D6",
    "peanuts":   "#F5EAD6",
    "wheat":     "#FFEFD6",
    "gluten":    "#FFE5D6",
    "soy":       "#D6F0D6",
    "sesame":    "#EDD6D6",
}

# food category emoji assigned by scanning recipe tags
CATEGORY_EMOJI: dict[str, str] = {
    "chicken":    "🍗",
    "beef":       "🥩",
    "pasta":      "🍝",
    "soup":       "🍲",
    "stew":       "🍲",
    "salad":      "🥗",
    "dessert":    "🎂",
    "cake":       "🎂",
    "cookies":    "🍪",
    "seafood":    "🐟",
    "fish":       "🐟",
    "shrimp":     "🦐",
    "vegetarian": "🥦",
    "vegan":      "🥦",
    "breakfast":  "🍳",
    "egg":        "🍳",
    "sandwich":   "🥪",
    "pizza":      "🍕",
    "rice":       "🍚",
    "bread":      "🍞",
    "curry":      "🍛",
    "mexican":    "🌮",
    "taco":       "🌮",
    "asian":      "🥢",
    "stir-fry":   "🥢",
    "pork":       "🥩",
    "lamb":       "🥩",
    "turkey":     "🍗",
    "fruit":      "🍓",
    "smoothie":   "🥤",
    "drink":      "🥤",
    "potato":     "🥔",
    "mushroom":   "🍄",
}

HERO_IMAGE = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=1600&q=80"

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AlloChef",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
[data-testid="stAppViewContainer"] {
    background-color: #FEFDF8;
}
[data-testid="stSidebar"] {
    background-color: #F0F5F3;
    border-right: 1px solid #DDE8E4;
}
[data-testid="stSidebar"] section { padding-top: 1rem; }

/* ── Hero ── */
.hero {
    position: relative;
    width: 100%;
    height: 260px;
    border-radius: 20px;
    overflow: hidden;
    margin-bottom: 32px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.12);
}
.hero img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}
.hero-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(61,122,106,0.82) 0%, rgba(244,162,97,0.55) 100%);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: center;
    padding: 0 48px;
}
.hero-title {
    font-family: 'Playfair Display', serif;
    font-size: 30rem;
    font-weight: 900;
    color: #FFFFFF;
    margin: 0;
    letter-spacing: -0.04em;
    text-shadow: 0 4px 20px rgba(0,0,0,0.35);
    line-height: 1.0;
}
.hero-sub {
    font-size: 1.4rem;
    color: rgba(255,255,255,0.9);
    margin-top: 10px;
    font-weight: 300;
    letter-spacing: 0.01em;
}

/* ── Sidebar branding ── */
.brand-block {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 0 12px;
}
.brand-icon {
    width: 64px;
    height: 64px;
    border-radius: 18px;
    background: linear-gradient(135deg, #7CB9A8 0%, #5FA090 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.2rem;
    flex-shrink: 0;
    box-shadow: 0 4px 16px rgba(124,185,168,0.4);
    line-height: 1;
}
.brand-text { display: flex; flex-direction: column; gap: 2px; }
.sidebar-logo {
    font-family: 'Playfair Display', serif !important;
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    color: #2D5A4E !important;
    margin: 0 !important;
    letter-spacing: -0.03em !important;
    line-height: 1.0 !important;
}
.sidebar-tagline {
    font-size: 0.8rem;
    color: #7A9E96;
    margin: 0;
    font-weight: 400;
    letter-spacing: 0.01em;
}

/* ── Member avatar ── */
.member-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    font-weight: 700;
    flex-shrink: 0;
    color: #FFFFFF;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    margin-top: 2px;
}

/* ── Sidebar member row alignment ── */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
    align-items: center !important;
    gap: 4px !important;
}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .element-container {
    display: flex !important;
    align-items: center !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* ── Sidebar delete button — transparent, X centred ── */
[data-testid="stSidebar"] div[data-testid="stButton"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: transparent !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
    color: #9ABDB5 !important;
    padding: 0 !important;
    margin: 0 auto !important;
    font-size: 1rem !important;
    border-radius: 50% !important;
    line-height: 1 !important;
    height: 28px !important;
    width: 28px !important;
    min-height: 28px !important;
    min-width: 28px !important;
    max-height: 28px !important;
    max-width: 28px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"] * {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
    width: 100% !important;
    height: 100% !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: #FFE0D6 !important;
    color: #C0504A !important;
}
/* Manage Pantry — full-width primary button in sidebar */
[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"] {
    width: 100% !important;
    max-width: 100% !important;
    white-space: nowrap !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    padding: 0.45rem 1rem !important;
    height: auto !important;
    min-height: 38px !important;
    border-radius: 8px !important;
    margin: 6px 0 0 0 !important;
}

/* ── Section labels ── */
.section-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #7A9E96;
    margin: 28px 0 10px 0;
}

/* ── Restriction strip ── */
.restriction-strip {
    background: linear-gradient(90deg, #F0F5F3 0%, #FEFDF8 100%);
    border: 1px solid #DDE8E4;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    font-size: 0.9rem;
    color: #3D7A6A;
    font-weight: 500;
}

/* ── Allergen badges ── */
.badge-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }
.allergen-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    color: #3A3A3A;
    letter-spacing: 0.01em;
}

/* ── Input section ── */
.input-card {
    background: #FFFFFF;
    border: 1px solid #E0EBE7;
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.input-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.3rem;
    color: #2D3436;
    margin: 0 0 4px 0;
    font-weight: 600;
}
.input-hint {
    font-size: 0.85rem;
    color: #8A9E96;
    margin-bottom: 16px;
}
[data-testid="stTextArea"] textarea {
    font-size: 1rem !important;
    border-radius: 10px !important;
    border: 1.5px solid #D0DDD9 !important;
    padding: 14px 16px !important;
    line-height: 1.6 !important;
    min-height: 100px !important;
    background: #FAFCFB !important;
    color: #2D3436 !important;
}
[data-testid="stTextArea"] textarea:focus {
    border-color: #7CB9A8 !important;
    box-shadow: 0 0 0 3px rgba(124,185,168,0.15) !important;
}

/* ── Primary button ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #7CB9A8 0%, #5FA090 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.65rem 2.2rem !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
    box-shadow: 0 4px 14px rgba(124,185,168,0.4) !important;
    transition: all 0.2s ease !important;
    color: #FFFFFF !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(124,185,168,0.5) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:disabled {
    background: #C8D8D4 !important;
    box-shadow: none !important;
    transform: none !important;
}

/* ── Response box ── */
.response-box {
    background: linear-gradient(135deg, #F0F7F5 0%, #FEFDF8 100%);
    border: 1px solid #C8DDD8;
    border-left: 5px solid #7CB9A8;
    border-radius: 0 16px 16px 0;
    padding: 28px 32px;
    margin: 20px 0;
    color: #2D3436;
    line-height: 1.85;
    font-size: 1.05rem;
    box-shadow: 0 2px 12px rgba(124,185,168,0.1);
}
.fallback-box {
    background: linear-gradient(135deg, #FFF8F0 0%, #FEFDF8 100%);
    border: 1px solid #F4D4BC;
    border-left: 5px solid #F4A261;
    border-radius: 0 16px 16px 0;
    padding: 28px 32px;
    margin: 20px 0;
    color: #2D3436;
    line-height: 1.85;
    font-size: 1.05rem;
}

/* ── Recipe cards ── */
.recipe-card {
    background: #FFFFFF;
    border: 1px solid #E8EEE8;
    border-radius: 16px;
    padding: 0;
    margin: 12px 0;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    overflow: hidden;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.recipe-card:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.1);
    transform: translateY(-2px);
}
.recipe-card-top {
    background: linear-gradient(135deg, #F0F5F3 0%, #EDF5F0 100%);
    padding: 20px 24px 16px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.recipe-card-top.unsafe {
    background: linear-gradient(135deg, #FDF5F3 0%, #FFF0EC 100%);
}
.recipe-emoji {
    font-size: 2.6rem;
    line-height: 1;
    flex-shrink: 0;
}
.recipe-card-name {
    font-family: 'Playfair Display', serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: #2D3436;
    text-transform: capitalize;
    margin: 0 0 4px 0;
    line-height: 1.3;
}
.recipe-card-meta {
    font-size: 0.82rem;
    color: #8A9E96;
    font-weight: 500;
}
.recipe-card-body {
    padding: 14px 24px 18px;
}
.safe-pill   { display:inline-block; background:#D6F0D6; color:#2A6A2A; padding:3px 12px; border-radius:20px; font-size:0.72rem; font-weight:700; margin-left:10px; letter-spacing:0.03em; }
.unsafe-pill { display:inline-block; background:#FFE0D6; color:#7A2A2A; padding:3px 12px; border-radius:20px; font-size:0.72rem; font-weight:700; margin-left:10px; letter-spacing:0.03em; }

/* ── Substitution card ── */
.sub-card {
    background: #FAFCFA;
    border: 1px solid #DDE8E4;
    border-radius: 12px;
    padding: 16px 20px;
    margin: 10px 0;
}
.sub-recipe-name {
    font-family: 'Playfair Display', serif;
    font-size: 1rem;
    font-weight: 600;
    color: #2D3436;
    margin-bottom: 10px;
}
.sub-row {
    font-size: 0.88rem;
    color: #444;
    margin: 6px 0 6px 4px;
    line-height: 1.5;
}
.sub-arrow { color: #7CB9A8; font-weight: 700; margin: 0 6px; }
.sub-note { font-size: 0.78rem; color: #888; margin-left: 4px; }

/* ── Horizontal recipe row ── */
.recipe-row {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    padding: 8px 4px 20px;
    align-items: flex-start;
    scrollbar-width: thin;
    scrollbar-color: #C8DDD8 transparent;
}
.recipe-row::-webkit-scrollbar { height: 5px; }
.recipe-row::-webkit-scrollbar-thumb { background: #C8DDD8; border-radius: 10px; }
.recipe-card-h {
    background: #FFFFFF;
    border: 1px solid #E8EEE8;
    border-radius: 16px;
    min-width: 240px;
    max-width: 240px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    overflow: hidden;
    flex-shrink: 0;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.recipe-card-h:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,0.1);
    transform: translateY(-3px);
}
.recipe-card-h-top {
    padding: 18px 16px 14px;
    text-align: center;
    font-size: 2.8rem;
    line-height: 1;
}
.recipe-card-h-top.safe   { background: linear-gradient(160deg, #F0F7F5, #EDF5F0); }
.recipe-card-h-top.unsafe { background: linear-gradient(160deg, #FDF5F3, #FFF0EC); }
.recipe-card-h-body { padding: 14px 16px 16px; }
.recipe-card-h-name {
    font-family: 'Playfair Display', serif;
    font-size: 0.97rem;
    font-weight: 600;
    color: #2D3436;
    text-transform: capitalize;
    margin: 0 0 4px 0;
    line-height: 1.3;
}
.recipe-card-h-meta { font-size: 0.78rem; color: #8A9E96; margin-bottom: 10px; }
.recipe-card-h-ingredients {
    font-size: 0.78rem;
    color: #555;
    line-height: 1.55;
    margin-bottom: 10px;
    border-top: 1px solid #F0F0EC;
    padding-top: 8px;
}
.recipe-card-h-ingredients strong {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8A9E96;
    display: block;
    margin-bottom: 3px;
}

/* ── Debug entries ── */
.debug-entry {
    padding: 12px 16px;
    border-radius: 10px;
    margin: 6px 0;
    font-size: 0.83rem;
    line-height: 1.55;
    font-family: 'Inter', sans-serif;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 0.95rem;
    font-weight: 500;
    padding: 8px 20px;
}

/* ── Hide streamlit chrome ── */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
[data-testid="stToolbar"] { visibility: hidden; }

/* ── Always show sidebar toggle ── */
[data-testid="stSidebarCollapsedControl"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
}
button[data-testid="baseButton-headerNoPadding"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}

/* ── Uniform recipe cards ── */
/* Each content section has a fixed height, so every card is the same overall
   height (and the action buttons line up) no matter the recipe. Robust because
   it doesn't depend on Streamlit's flex/DOM nesting. */
.rc-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.05rem;
    font-weight: 600;
    color: #2D3436;
    line-height: 1.25;
    margin-bottom: 4px;
    min-height: 2.6em;            /* up to 2 lines of title */
}
.rc-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-content: flex-start;
    min-height: 60px;            /* up to 2 rows of allergen pills */
    margin: 8px 0 4px;
}
.rc-ing-preview {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 2.6em;           /* exactly 2 lines */
    font-size: 0.8rem;
    color: #6b7c77;
    margin: 2px 0 4px;
}
.rc-pantry {
    min-height: 3.4em;           /* "You have X" + up to 2 "Need:" lines */
    margin: 6px 0 2px;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

for key, default in [
    ("result", None),
    ("ingredients_input", ""),
    ("chat_reply", ""),            # latest assistant reply from the Meal Orchestrator
    ("scan_just_done", False),
    ("scan_count", 0),
    # grocery planning workflow
    ("grocery_phase", None),       # None | "planning" | "awaiting_approval" | "resuming" | "cart_ready"
    ("grocery_recipe", None),      # dict: {name, ingredients, steps, description}
    ("grocery_thread_id", None),   # str: LangGraph thread ID for resuming after interrupt
    ("grocery_plan_data", None),   # dict: grocery plan returned by the graph
    ("grocery_cart", None),        # dict: cart draft after approval
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_amt(a) -> str:
    """Format a quantity amount without a trailing .0 (2.0 -> '2', 1.5 -> '1.5')."""
    try:
        f = float(a)
        return str(int(f)) if f == int(f) else str(f)
    except (TypeError, ValueError):
        return str(a)


def _qty_label(amount, unit, name: str) -> str:
    """
    Human-friendly quantity label. 'each' is a count, not a word to show:
      (2, 'each', 'chicken breast') -> '2 × chicken breast'
      (2, 'tbsp', 'olive oil')      -> '2 tbsp olive oil'
    """
    a = _fmt_amt(amount)
    if unit in (None, "", "each"):
        return f"{a} × {name}"
    return f"{a} {unit} {name}"


def _parse_response(text: str) -> tuple[str, dict]:
    """Split the structured LLM response into display text and per-recipe card data.

    Returns:
        display_text  — name + description lines only (shown in the response box)
        card_data     — {recipe_name_lower: {name, description, ingredients, steps}}
    """
    import re
    blocks = re.split(r'\*\*(.+?)\*\*', text)
    display_lines: list[str] = []
    card_data: dict = {}
    # blocks[0] is text before the first **Name** — discard it
    if len(blocks) < 3:
        return text, {}  # LLM didn't follow the format at all; show raw

    for i in range(1, len(blocks), 2):
        name    = blocks[i].strip()
        content = blocks[i + 1] if i + 1 < len(blocks) else ""

        # match "- description" whether it is on its own line OR inline after **Name** (leading spaces ok)
        desc_match  = re.search(r'^\s*-\s+(.+)', content, re.MULTILINE)
        description = desc_match.group(1).strip() if desc_match else ""
        title_name  = name.title()

        display_lines.append(f"<p style='margin:12px 0 2px'><strong>{title_name}</strong></p>")
        if description:
            display_lines.append(f"<p style='margin:0 0 4px;color:#555;font-size:0.9rem'>— {description}</p>")

        ingredients: list[str] = []
        steps:       list[str] = []
        quantities:  dict      = {}   # clean_name -> {"amount": float, "unit": str}
        section = None
        for line in content.splitlines():
            stripped = line.strip()
            if re.match(r'^ingredients\s*:', stripped, re.IGNORECASE):
                section = "ingredients"
                continue
            if re.match(r'^steps\s*:', stripped, re.IGNORECASE):
                section = "steps"
                continue
            if stripped == "---":
                section = None
                continue
            if section == "ingredients" and stripped.startswith("-"):
                ing = stripped.lstrip("- ").strip()
                if not ing:
                    continue
                # split "name | amount unit"; quantity portion is optional
                amount, unit = 1.0, "each"
                if "|" in ing:
                    ing, qty_part = (p.strip() for p in ing.split("|", 1))
                    qm = re.match(r'^([\d]+(?:\.[\d]+)?)\s*(.*)$', qty_part)
                    if qm:
                        amount = float(qm.group(1))
                        unit   = (qm.group(2).strip() or "each")
                if ing:
                    ingredients.append(ing)
                    quantities[ing] = {"amount": amount, "unit": unit}
            elif section == "steps":
                m = re.match(r'^\d+\.\s*(.+)', stripped)
                if m:
                    steps.append(m.group(1).strip())

        card_data[" ".join(name.lower().split())] = {
            "name":        title_name,
            "description": description,
            "ingredients": ingredients,
            "quantities":  quantities,
            "steps":       steps,
        }

    return "\n".join(display_lines).strip(), card_data


def extract_ingredients_from_image(image_bytes: bytes) -> list[str]:
    client = OpenAI(api_key=OPENAI_API_KEY)
    b64    = base64.b64encode(image_bytes).decode()
    resp   = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Look at this fridge or pantry photo. "
                        "List every food ingredient you can identify. "
                        "Return only a comma-separated list of ingredient names in lowercase, nothing else. "
                        "Example: chicken, garlic, tomatoes, olive oil"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                },
            ],
        }],
        max_tokens=300,
    )
    raw = resp.choices[0].message.content.strip()
    return [i.strip() for i in raw.split(",") if i.strip()]


# Recipe discovery now flows entirely through the Meal Orchestrator
# (run_meal_orchestrator) from the chat box — the orchestrator routes the raw
# user message to the Recipe Recommender, which reads the pantry when asked.


AVATAR_PALETTE = [
    "#7CB9A8", "#F4A261", "#A8B4D4", "#D4A8C4",
    "#A8D4B4", "#D4C4A8", "#B4C8D4", "#C4D4A8",
]

def avatar_html(name: str) -> str:
    color = AVATAR_PALETTE[hash(name) % len(AVATAR_PALETTE)]
    initial = name[0].upper() if name else "?"
    return f'<div class="member-avatar" style="background:{color}">{initial}</div>'


def allergen_badge_html(allergen: str) -> str:
    color = ALLERGEN_COLORS.get(allergen, "#E8E8E0")
    label = ALLERGEN_LABELS.get(allergen, allergen.replace("_", " ").title())
    return f'<span class="allergen-badge" style="background:{color}">{label}</span>'


def recipe_emoji(doc) -> str:
    tags = doc.metadata.get("tags", [])
    name = doc.metadata.get("name", "").lower()
    combined = " ".join(tags).lower() + " " + name
    for keyword, emoji in CATEGORY_EMOJI.items():
        if keyword in combined:
            return emoji
    return "🍽️"


def render_recipe_card(doc, safe: bool = True) -> None:
    meta     = doc.metadata
    name     = meta.get("name", "unknown recipe").title()
    minutes  = meta.get("minutes")
    time_str = f"  ·  {int(minutes)} min" if minutes else ""
    flags    = [a for a in ALLERGEN_NAMES if meta.get(f"contains_{a}", False)]
    badges   = "".join(allergen_badge_html(a) for a in flags)
    emoji    = recipe_emoji(doc)
    top_cls  = "recipe-card-top" if safe else "recipe-card-top unsafe"
    pill     = '<span class="safe-pill">Safe</span>' if safe else '<span class="unsafe-pill">Conflict</span>'

    st.markdown(f"""
    <div class="recipe-card">
      <div class="{top_cls}">
        <span class="recipe-emoji">{emoji}</span>
        <div>
          <div class="recipe-card-name">{name}{pill}</div>
          <div class="recipe-card-meta">Recipe{time_str}</div>
        </div>
      </div>
      {'<div class="recipe-card-body"><div class="badge-row">' + badges + '</div></div>' if badges else ''}
    </div>
    """, unsafe_allow_html=True)


# ── Pantry dialog ─────────────────────────────────────────────────────────────

@st.dialog("My Pantry", width="large")
def pantry_dialog() -> None:
    all_items = list_pantry_items()

    # explicit close button (top-right) — app-scope rerun dismisses the dialog
    _, c_close = st.columns([8, 1])
    with c_close:
        if st.button("✕", key="dlg_close", help="Close pantry"):
            st.rerun()

    search = st.text_input("Search pantry", placeholder="e.g. garlic", label_visibility="visible")
    filtered = [
        item for item in all_items
        if not search or search.lower() in item["item_name"].lower()
    ]

    st.markdown(
        f'<div style="font-size:0.8rem;color:#8A9E96;margin:4px 0 10px">'
        f'{len(all_items)} item{"s" if len(all_items) != 1 else ""} saved</div>',
        unsafe_allow_html=True,
    )

    if filtered:
        # render items as removable chips in a flow layout
        # group into rows of 3 columns
        cols_per_row = 3
        for i in range(0, len(filtered), cols_per_row):
            row_items = filtered[i : i + cols_per_row]
            cols = st.columns(cols_per_row)
            for col, item in zip(cols, row_items):
                with col:
                    c_name, c_del = st.columns([4, 1], vertical_alignment="center")
                    with c_name:
                        st.markdown(
                            f'<div style="background:#F0F5F3;border:1px solid #DDE8E4;'
                            f'border-radius:8px;padding:6px 10px;font-size:0.87rem;'
                            f'color:#2D3436">{item["item_name"]}</div>',
                            unsafe_allow_html=True,
                        )
                    with c_del:
                        if st.button("✕", key=f"dlg_del_{item['normalized_name']}",
                                     help=f"Remove {item['item_name']}"):
                            remove_pantry_item(item["normalized_name"])
                            st.rerun(scope="fragment")
    elif all_items:
        st.caption("No items match your search.")
    else:
        st.info("Your pantry is empty. Add items below to enable grocery planning.")

    st.divider()
    st.markdown("**Add items**")
    with st.form("dlg_add_form", clear_on_submit=True):
        new_input = st.text_input(
            "Items",
            placeholder="chicken, garlic, olive oil",
            label_visibility="collapsed",
        )
        col_add, col_clear, _ = st.columns([2, 2, 3])
        with col_add:
            do_add = st.form_submit_button("Add items", use_container_width=True, type="primary")
        with col_clear:
            do_clear = st.form_submit_button("Clear all", use_container_width=True)

    if do_add and new_input.strip():
        add_pantry_items([i.strip() for i in new_input.replace("\n", ",").split(",") if i.strip()])
        st.rerun(scope="fragment")
    if do_clear:
        clear_pantry()
        st.rerun(scope="fragment")


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div class="brand-block">
      <div class="brand-icon">🍳</div>
      <div class="brand-text">
        <p class="sidebar-logo" style="font-size:2.2rem!important;font-weight:700!important;line-height:1!important;white-space:nowrap!important;">AlloChef</p>
        <p class="sidebar-tagline">Cook safely for everyone.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    st.markdown('<div class="section-label">Family Members</div>', unsafe_allow_html=True)

    members        = list_members()
    active_members = []

    if not members:
        st.caption("No family members yet. Add one below.")
    else:
        for member in members:
            allergens     = get_allergens(member)
            badge_preview = "".join(allergen_badge_html(a) for a in allergens[:3])
            if len(allergens) > 3:
                badge_preview += f'<span style="font-size:0.75rem;color:#8A9E96"> +{len(allergens)-3}</span>'

            col_av, col_check, col_del = st.columns([1, 5, 1], vertical_alignment="center")
            with col_av:
                st.markdown(avatar_html(member), unsafe_allow_html=True)
            with col_check:
                active = st.checkbox(member, value=True, key=f"active_{member}")
                if active:
                    active_members.append(member)
            with col_del:
                if st.button("✕", key=f"del_{member}", help=f"Remove {member}"):
                    remove_member(member)
                    st.rerun()

            if allergens:
                st.markdown(f'<div style="margin:-4px 0 6px 44px" class="badge-row">{badge_preview}</div>', unsafe_allow_html=True)

            with st.expander(f"Edit allergens — {member}"):
                current  = get_allergens(member)
                selected = []
                cols     = st.columns(2)
                for i, allergen in enumerate(ALLERGEN_NAMES):
                    with cols[i % 2]:
                        checked = st.checkbox(
                            ALLERGEN_LABELS[allergen],
                            value=allergen in current,
                            key=f"allergy_{member}_{allergen}",
                        )
                        if checked:
                            selected.append(allergen)
                if sorted(selected) != sorted(current):
                    set_allergens(member, selected)

    st.divider()
    st.markdown('<div class="section-label">Add family member</div>', unsafe_allow_html=True)

    with st.form("add_member_form", clear_on_submit=True):
        new_name  = st.text_input("Name", placeholder="e.g. Maya", label_visibility="collapsed")
        submitted = st.form_submit_button("+ Add member", use_container_width=True)
        if submitted and new_name.strip():
            add_member(new_name.strip())
            st.rerun()

    st.divider()

    # ── My Pantry — compact control ───────────────────────────────────────────
    st.markdown('<div class="section-label">My Pantry</div>', unsafe_allow_html=True)

    _sidebar_pantry = list_pantry_items()
    _pantry_count   = len(_sidebar_pantry)

    if _pantry_count == 0:
        st.caption("No items saved yet.")
    else:
        st.markdown(
            f'<div style="font-size:0.88rem;color:#3D7A6A;font-weight:500;'
            f'margin-bottom:6px">{_pantry_count} item{"s" if _pantry_count != 1 else ""} saved</div>',
            unsafe_allow_html=True,
        )
        # preview chips — first 3 items + overflow count
        _preview = [p["item_name"].title() for p in _sidebar_pantry[:3]]
        _overflow = _pantry_count - 3
        _chip_text = " · ".join(_preview)
        if _overflow > 0:
            _chip_text += f" +{_overflow} more"
        st.markdown(
            f'<div style="font-size:0.78rem;color:#7A9E96;margin-bottom:10px">{_chip_text}</div>',
            unsafe_allow_html=True,
        )

    if st.button("🗂  Manage pantry", use_container_width=True, key="open_pantry_dialog", type="primary"):
        # flag so the grocery dialog isn't also opened this run (only one dialog allowed)
        st.session_state["_pantry_opening"] = True
        pantry_dialog()

    st.divider()
    with st.expander("🔍  Agent debug log"):
        checks = read_recent_checks(15)
        if checks:
            for entry in reversed(checks):
                event   = entry.get("event", "")
                verdict = entry.get("verdict", "")
                reason  = entry.get("reason", "")
                ts      = entry.get("timestamp", "")[:19].replace("T", " ")
                bg      = "#D6F0D6" if verdict in ("relevant", "grounded") \
                     else "#FFE0D6" if verdict in ("not_relevant", "hallucinating") \
                     else "#F5F5F0"
                st.markdown(
                    f'<div class="debug-entry" style="background:{bg}">'
                    f'<strong style="font-size:0.75rem">{ts}</strong><br>'
                    f'{event} · <strong>{verdict}</strong><br>'
                    f'<span style="color:#555;font-size:0.78rem">{reason}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No checks logged yet.")

# ── Hero ──────────────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
.ht {{ font-family:'Playfair Display',serif; font-size:5rem; font-weight:900; color:#fff;
       margin:0; line-height:1.05; letter-spacing:-0.03em;
       text-shadow:0 4px 20px rgba(0,0,0,0.4); }}
.hs {{ font-size:1.5rem; font-weight:300; color:rgba(255,255,255,0.9);
       margin:12px 0 0; letter-spacing:0.01em; }}
</style>
<div class="hero">
  <img src="{HERO_IMAGE}" alt="food" />
  <div class="hero-overlay">
    <p class="ht">What can we cook tonight?</p>
    <p class="hs">Allergen-safe recipes for your whole family, every night.</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tonight's restrictions ────────────────────────────────────────────────────

profiles     = load_profiles()
restrictions = sorted({a for m in active_members for a in profiles.get(m, [])})

if active_members and restrictions:
    badges_html = "".join(allergen_badge_html(a) for a in restrictions)
    members_str = ", ".join(active_members)
    st.markdown(f"""
    <div class="restriction-strip">
      <span>Tonight: <strong>{members_str}</strong></span>
      <span style="color:#C8D8D4">·</span>
      <span>Avoiding</span>
      <div class="badge-row" style="margin:0">{badges_html}</div>
    </div>
    """, unsafe_allow_html=True)
elif active_members:
    members_str = ", ".join(active_members)
    st.markdown(f"""
    <div class="restriction-strip">
      <span>Tonight: <strong>{members_str}</strong></span>
      <span style="color:#C8D8D4">·</span>
      <span style="color:#5FA090; font-weight:500">No allergen restrictions</span>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="restriction-strip">
      <span style="color:#8A9E96">No family members selected — enter your ingredients and find recipes.</span>
    </div>
    """, unsafe_allow_html=True)

# ── Ask AlloChef (chat) ────────────────────────────────────────────────────────

st.markdown('<div class="section-label">Ask AlloChef</div>', unsafe_allow_html=True)
st.caption(
    'Ask in plain English — "what can I cook tonight with what I have?" — or just '
    'list ingredients like "chicken, garlic, tomato". I\'ll keep your family\'s allergens in mind.'
)

# Optional: scan a fridge photo straight into your pantry, then ask what to cook
with st.expander("📷  Scan a fridge photo into your pantry"):
    uploaded = st.file_uploader("Upload photo", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
    if uploaded:
        st.image(uploaded, use_container_width=True)
        if st.button("Scan & add to pantry", type="primary"):
            with st.spinner("Identifying ingredients..."):
                found = extract_ingredients_from_image(uploaded.read())
            if found:
                add_pantry_items(found)
                st.success(f"Added {len(found)} item{'s' if len(found) != 1 else ''} to your pantry: {', '.join(found)}")
                st.rerun()
            else:
                st.warning("Could not identify ingredients. Try a clearer photo.")

# latest assistant reply
if st.session_state.get("chat_reply"):
    st.markdown(
        f'<div style="background:#F0F7F5;border:1px solid #C8DDD8;border-radius:12px;'
        f'padding:12px 16px;margin:10px 0;font-size:0.92rem;color:#2D3436;line-height:1.5">'
        f'{st.session_state.chat_reply}</div>',
        unsafe_allow_html=True,
    )

_user_msg = st.chat_input("e.g. 'what can I cook with what I have?'  or  'chicken, garlic, tomato'")
if _user_msg:
    st.session_state.result = None
    with st.spinner("AlloChef is thinking…"):
        try:
            _res = run_meal_orchestrator(_user_msg, active_members, profiles)
            st.session_state.result     = _res.get("rag")
            st.session_state.chat_reply = _res.get("text", "")
        except Exception as e:
            st.session_state.chat_reply = f"Something went wrong: {e}"
    st.rerun()

# ── Results ───────────────────────────────────────────────────────────────────

result = st.session_state.result

if result:
    response = result.get("response", "")
    display_text, card_data = _parse_response(response)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">Tonight\'s Suggestions</div>', unsafe_allow_html=True)

    is_fallback = (
        result.get("hallucination_verdict") == "unknown"
        or "wasn't able" in response.lower()
        or "don't know" in response.lower()
        or "i don't" in response.lower()
    )

    if is_fallback:
        st.markdown(f'<div class="fallback-box">{display_text}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="response-box">{display_text}</div>', unsafe_allow_html=True)

    safe_recipes  = result.get("safe_recipes", [])
    unsafe_pairs  = result.get("unsafe_pairs", [])
    substitutions = result.get("substitutions", [])

    # recipe cards — horizontal scrollable rows
    if safe_recipes or unsafe_pairs:
        st.markdown("<br>", unsafe_allow_html=True)

        # Structural keywords that mark a tag as metadata, not food
        _META_EXACT    = {"time-to-make", "course", "main-ingredient", "cuisine",
                          "preparation", "main-dish", "occasion", "dietary", "equipment"}
        _META_CONTAINS = ["minutes", "hours", "or-less", "steps-or-less", "by-ingredient"]
        _META_STARTS   = ("low-", "high-", "for-", "number-of-")

        def food_tags(tags: list) -> list[str]:
            out = []
            for t in tags:
                if t in _META_EXACT:
                    continue
                if t.startswith(_META_STARTS):
                    continue
                if any(p in t for p in _META_CONTAINS):
                    continue
                out.append(t.replace("-", " ").title())
            return out

        def parse_ingredients(text: str) -> list[str]:
            for line in text.splitlines():
                if line.lower().startswith("ingredients:"):
                    return [i.strip() for i in line.split(":", 1)[1].split(",") if i.strip()]
            return []

        def parse_servings(tags: list) -> str:
            serving_keywords = ["serving", "portion", "people", "yield", "for-1", "for-2",
                                 "for-3", "for-4", "for-5", "for-6"]
            for tag in tags:
                if any(k in tag for k in serving_keywords):
                    return tag.replace("-", " ").title()
            return ""

        # group all safe_recipe docs by recipe_id so we can combine overview + instruction chunks
        from collections import defaultdict
        recipe_chunks: dict[str, list] = defaultdict(list)
        for doc in safe_recipes:
            recipe_chunks[doc.metadata.get("recipe_id", "")].append(doc)

        def _full_recipe_content(overview_doc, instr_docs, tags, ingredients, minutes, servings, flag_labels, llm_card=None):
            col_t, col_s = st.columns(2)
            with col_t:
                if minutes:
                    st.markdown(f"**Cook time**  \n{int(minutes)} min")
            with col_s:
                if servings:
                    st.markdown(f"**Servings**  \n{servings}")
            if flag_labels:
                st.markdown(f"**Contains:** {', '.join(flag_labels)}")
            st.divider()

            # prefer LLM-parsed ingredients; fall back to Pinecone overview chunk
            display_ingredients = (llm_card or {}).get("ingredients") or ingredients
            _qty_map = (llm_card or {}).get("quantities", {}) or {}
            if display_ingredients:
                st.markdown("**Ingredients**")
                for ing in display_ingredients:
                    q = _qty_map.get(ing)
                    if q:
                        st.markdown(f"- {_qty_label(q.get('amount', 1), q.get('unit', 'each'), ing)}")
                    else:
                        st.markdown(f"- {ing}")

            ftags = food_tags(tags)
            if ftags:
                chips = "".join(
                    f'<span style="display:inline-block;background:#EDF5F0;color:#3D7A6A;'
                    f'padding:4px 12px;border-radius:20px;font-size:0.75rem;font-weight:500;'
                    f'margin:3px 3px 3px 0;border:1px solid #C8DDD8">{t}</span>'
                    for t in ftags
                )
                st.markdown(
                    f'<div style="margin:8px 0 12px"><strong style="font-size:0.8rem;color:#555">'
                    f'Key ingredients & categories</strong>'
                    f'<div style="margin-top:6px">{chips}</div></div>',
                    unsafe_allow_html=True,
                )

            # prefer LLM-parsed steps; fall back to raw Pinecone instruction text
            llm_steps = (llm_card or {}).get("steps")
            if llm_steps:
                st.divider()
                st.markdown("**Instructions**")
                for i, step in enumerate(llm_steps, 1):
                    st.markdown(f"{i}. {step}")
            elif instr_docs:
                import re
                raw = " ".join(
                    " ".join(l for l in d.page_content.splitlines() if not l.lower().startswith("recipe:"))
                    for d in instr_docs
                )
                if raw.strip():
                    st.divider()
                    st.markdown("**Instructions**")
                    st.markdown(raw)

        # load pantry once for the whole grid (fast SQLite call)
        from agent.pantry_tools import compare_pantry_tool as _cpt
        _pantry_for_cards = list_pantry_items()

        # build a lookup: recipe_id → substitution entry (so cards can show renamed title)
        sub_by_rid: dict[str, dict] = {}
        for sub_entry in substitutions:
            rid_s = sub_entry.get("recipe_id", "")
            if rid_s:
                sub_by_rid[rid_s] = sub_entry

        def _apply_sub_to_title(title: str, sub_entry: dict) -> str:
            """Use the substitution agent's natural renamed title; fall back to a
            deterministic word-replace of the allergen ingredient."""
            renamed = (sub_entry.get("renamed_title") or "").strip()
            if renamed:
                return renamed.title()
            for sub in sub_entry.get("available_substitutes", [])[:1]:
                original   = sub.get("original", "").strip()
                substitute = sub.get("substitute", "").strip()
                if original and substitute:
                    import re as _re2
                    title = _re2.sub(rf'\b{_re2.escape(original)}\b', substitute, title, flags=_re2.IGNORECASE)
            return title.title()

        def _render_recipe_grid(items: list, safe: bool) -> None:
            top_bg   = "linear-gradient(160deg,#F0F7F5,#EDF5F0)" if safe else "linear-gradient(160deg,#FDF5F3,#FFF0EC)"
            cols_per = 3

            # normalized lookup of the LLM cards (strip "(N min)" suffix + lowercase)
            import re as _rx
            def _nn(s: str) -> str:
                s = _rx.sub(r'\s*\(\d+[\d.]*\s*min\)', '', s or '', flags=_rx.IGNORECASE)
                return " ".join(s.lower().split())
            card_by_norm = {_nn(k): v for k, v in card_data.items()}
            for row_start in range(0, len(items), cols_per):
                row  = items[row_start:row_start + cols_per]
                cols = st.columns(cols_per, gap="medium")
                for col, (rid, chunks) in zip(cols, row):
                    overview_doc = next((d for d in chunks if d.metadata.get("chunk_type") == "overview"), chunks[0])
                    instr_docs   = sorted(
                        [d for d in chunks if d.metadata.get("chunk_type") == "instructions"],
                        key=lambda d: d.metadata.get("chunk_index", 0),
                    )
                    meta        = overview_doc.metadata
                    raw_name    = meta.get("name", "unknown recipe").title()
                    minutes     = meta.get("minutes")
                    time_str    = f"{int(minutes)} min" if minutes else "—"
                    tags        = meta.get("tags", [])
                    flags       = [a for a in ALLERGEN_NAMES if meta.get(f"contains_{a}", False)]
                    badges      = "".join(allergen_badge_html(a) for a in flags)
                    emoji       = recipe_emoji(overview_doc)
                    pinecone_ings = parse_ingredients(overview_doc.page_content)
                    servings    = parse_servings(tags)
                    flag_labels = [ALLERGEN_LABELS[a] for a in flags]

                    # match the LLM card by recipe name; if this recipe was renamed by a
                    # substitution (e.g. "Palak Paneer" → "Palak Tofu"), the LLM keyed its
                    # card under the renamed title, so try that too — otherwise the card
                    # falls back to raw Pinecone data (no parsed ingredients / steps).
                    card_sub = sub_by_rid.get(rid)
                    llm_card = card_by_norm.get(_nn(meta.get("name", "")))
                    if not llm_card and card_sub and card_sub.get("renamed_title"):
                        llm_card = card_by_norm.get(_nn(card_sub["renamed_title"]))

                    # if a substitution exists for this recipe, apply it to the title
                    # and badge the card — deterministic, doesn't depend on LLM name matching
                    if card_sub:
                        name = _apply_sub_to_title(raw_name, card_sub)
                        sub_word     = (card_sub.get("available_substitutes") or [{}])[0]
                        sub_badge    = (
                            f'<span style="display:inline-block;background:#D6F0D6;color:#2A6A2A;'
                            f'padding:2px 10px;border-radius:20px;font-size:0.72rem;font-weight:600;'
                            f'margin-left:6px">sub: {sub_word.get("original","?")} → {sub_word.get("substitute","?")}</span>'
                        )
                        _reason   = card_sub.get("reason") or sub_word.get("reason", "")
                        sub_reason_html = (
                            f'<div style="font-size:0.74rem;color:#3D7A6A;font-style:italic;'
                            f'margin:4px 0 0;line-height:1.3">↳ {_reason}</div>'
                            if _reason else ""
                        )
                    else:
                        name     = raw_name
                        sub_badge = ""
                        sub_reason_html = ""

                    preview_ings = (llm_card or {}).get("ingredients") or pinecone_ings
                    ing_preview = ", ".join(preview_ings[:5]) + (f" +{len(preview_ings)-5} more" if len(preview_ings) > 5 else "")
                    badge_block = f'<div class="rc-badges">{badges}</div>'

                    # pantry diff — built as fixed-height HTML so all cards align
                    pantry_html = ""
                    if _pantry_for_cards and preview_ings:
                        _diff = _cpt(preview_ings, _pantry_for_cards)
                        _have  = len(_diff["already_have"])
                        _total = len(preview_ings)
                        _need  = _diff["missing_ingredients"][:3]
                        _need_str = ", ".join(_need) + ("…" if len(_diff["missing_ingredients"]) > 3 else "")
                        _have_color = "#2A6A2A" if _have == _total else "#8A6500" if _have > 0 else "#7A2A2A"
                        pantry_html = (
                            f'<div style="font-size:0.78rem;color:{_have_color};font-weight:500">'
                            f'You have {_have} of {_total} ingredients</div>'
                            + (f'<div style="font-size:0.75rem;color:#888">Need: {_need_str}</div>' if _need else "")
                        )

                    with col:
                        with st.container(border=True):
                            # one HTML block with fixed-height sections → uniform cards
                            st.markdown(
                                f'<span class="rc-marker"></span>'
                                f'<div style="text-align:center;font-size:2.8rem;padding:16px 0 12px;'
                                f'background:{top_bg};border-radius:10px;margin-bottom:12px">{emoji}</div>'
                                f'<div class="rc-title">{name}{sub_badge}</div>'
                                f'<div style="font-size:0.8rem;color:#8A9E96;margin-bottom:6px">⏱ {time_str}</div>'
                                f'{badge_block}'
                                f'{sub_reason_html}'
                                f'<div class="rc-ing-preview">{ing_preview}</div>'
                                f'<div class="rc-pantry">{pantry_html}</div>',
                                unsafe_allow_html=True,
                            )

                            with st.expander("View full recipe"):
                                _full_recipe_content(
                                    overview_doc, instr_docs, tags,
                                    pinecone_ings, minutes, servings, flag_labels,
                                    llm_card=llm_card,
                                )
                            plan_ings = (llm_card or {}).get("ingredients") or pinecone_ings
                            if st.button(
                                "Plan groceries",
                                key=f"plan_{rid}",
                                use_container_width=True,
                            ):
                                st.session_state.grocery_recipe = {
                                    "name":        name,
                                    "ingredients": plan_ings,
                                    "quantities":  (llm_card or {}).get("quantities", {}),
                                    "steps":       (llm_card or {}).get("steps", []),
                                    "description": (llm_card or {}).get("description", ""),
                                }
                                st.session_state.grocery_thread_id = str(uuid.uuid4())
                                st.session_state.grocery_phase     = "planning"
                                st.session_state.grocery_plan_data = None
                                st.session_state.grocery_cart      = None
                                st.rerun()

        # LLM-selected recipe names (whitespace-normalised for reliable lookup).
        # The LLM copies the ### heading format which includes "(N min)" — strip
        # that suffix so names match the plain Pinecone metadata field.
        import re as _re
        def _norm_name(s: str) -> str:
            s = _re.sub(r'\s*\(\d+[\d.]*\s*min\)', '', s, flags=_re.IGNORECASE)
            return " ".join(s.lower().split())

        llm_names = {_norm_name(k) for k in card_data.keys()}

        # a substituted recipe is renamed in the LLM response (e.g. "Palak Paneer"
        # → "Palak Tofu"), so map each recipe_id to its renamed title to match it
        # back to the right LLM card during selection.
        renamed_norm_by_rid = {
            e.get("recipe_id", ""): _norm_name(e.get("renamed_title", ""))
            for e in substitutions if e.get("renamed_title")
        }

        # recipe_ids that have an allergen conflict (these must only show in substitution section)
        unsafe_recipe_ids = {
            pair["doc"].metadata.get("recipe_id", "")
            for pair in unsafe_pairs
        }

        def _llm_picked(rid: str, chunks: list) -> bool:
            """True if the LLM actually carded this recipe — by original name OR
            by its substitution-renamed title."""
            if any(_norm_name(d.metadata.get("name", "")) in llm_names for d in chunks):
                return True
            return renamed_norm_by_rid.get(rid, "\0") in llm_names

        # only render recipes the LLM actually suggested (each has a real card).
        # Cap at 5 to match the LLM's 3-5 suggestion limit.
        _MAX_CARDS = 5
        if not is_fallback:
            selected_chunks = {
                rid: chunks for rid, chunks in recipe_chunks.items()
                if _llm_picked(rid, chunks)
            }
            if not selected_chunks:
                # name matching failed entirely — show top retrieved as a last resort
                selected_chunks = dict(list(recipe_chunks.items())[:_MAX_CARDS])
        else:
            selected_chunks = dict(list(recipe_chunks.items())[:_MAX_CARDS])

        safe_selected = {rid: c for rid, c in selected_chunks.items() if rid not in unsafe_recipe_ids}
        sub_selected  = {rid: c for rid, c in selected_chunks.items() if rid in unsafe_recipe_ids}

        # ── Need a Substitution — rendered FIRST ─────────────────────────────
        if unsafe_pairs:
            if sub_selected:
                display_unsafe = sub_selected
            else:
                # LLM didn't format any substitution recipes — show raw unsafe docs
                display_unsafe: dict[str, list] = defaultdict(list)
                seen_unsafe: set[str] = set()
                for pair in unsafe_pairs:
                    doc = pair["doc"]
                    rid = doc.metadata.get("recipe_id", "")
                    if rid not in seen_unsafe:
                        seen_unsafe.add(rid)
                        display_unsafe[rid].append(doc)
            st.markdown(
                f'<div class="section-label">Need a Substitution ({len(display_unsafe)})</div>',
                unsafe_allow_html=True,
            )
            _render_recipe_grid(list(display_unsafe.items()), safe=False)

        # ── Ready to Cook — rendered SECOND ──────────────────────────────────
        if safe_selected:
            if is_fallback:
                st.markdown(
                    f'<div class="section-label">Suggestions — may need extra ingredients ({len(safe_selected)})</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div style="font-size:0.88rem;color:#8A9E96;margin-bottom:12px">'
                    'These recipes are close matches but may use ingredients beyond what you scanned. '
                    'Check the ingredient list before cooking.</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f'<div class="section-label">Ready to Cook ({len(safe_selected)})</div>', unsafe_allow_html=True)
            _render_recipe_grid(list(safe_selected.items()), safe=not is_fallback)


# ── Grocery Planning Panel ────────────────────────────────────────────────────

_GROCERY_UNITS = ["each", "g", "kg", "ml", "l", "tsp", "tbsp", "cup",
                  "clove", "can", "bunch", "pinch", "slice", "lb", "oz"]


@st.dialog("Grocery Plan", width="large")
def grocery_plan_dialog() -> None:
    """
    Modal that drives the whole grocery flow inside one pop-up:
      planning → awaiting_approval → resuming → cart_ready.
    Internal transitions use fragment-scoped reruns so the modal stays open;
    Cancel/Close use app-scoped reruns to dismiss it.
    """
    phase = st.session_state.grocery_phase

    # ── planning: run the Grocery Agent to produce the plan ──
    if phase == "planning":
        selected_recipe = st.session_state.grocery_recipe or {}
        st.markdown(f"**Planning groceries for {selected_recipe.get('name', 'selected recipe')}…**")
        with st.spinner("The Grocery Agent is checking your pantry, allergens and substitutions…"):
            _members  = st.session_state.get("_active_members", [])
            _profiles = st.session_state.get("_profiles", {})
            _restrictions = restrictions_for(_members, _profiles)
            try:
                st.session_state.grocery_plan_data = run_grocery_agent(selected_recipe, _restrictions)
                st.session_state.grocery_phase = "awaiting_approval"
            except Exception as _e:
                st.error(f"Grocery planning failed: {_e}")
                st.session_state.grocery_phase = None
        st.rerun()

    # ── resuming: build the cart after the human approved (deterministic, gated here) ──
    elif phase == "resuming":
        st.markdown("**Creating your cart…**")
        with st.spinner("Creating your cart draft…"):
            try:
                edits = st.session_state.get("grocery_qty_edits", {})
                st.session_state.grocery_cart  = build_cart(st.session_state.grocery_plan_data or {}, edits)
                st.session_state.grocery_phase = "cart_ready"
            except Exception as _e:
                st.error(f"Cart creation failed: {_e}")
                st.session_state.grocery_phase = "awaiting_approval"
        st.rerun()

    # ── awaiting_approval / cart_ready: show the plan / cart ──
    else:
        _grocery_plan_contents()


def _grocery_plan_contents() -> None:
    """Render the grocery plan review UI (awaiting_approval and cart_ready phases)."""
    plan  = st.session_state.grocery_plan_data or {}
    cart  = st.session_state.grocery_cart or {}
    phase = st.session_state.grocery_phase
    recipe_name = plan.get("recipe_name", "Selected Recipe")

    st.markdown(
        f'<div class="section-label">Grocery Plan — {recipe_name}</div>',
        unsafe_allow_html=True,
    )

    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        # Already have
        already_have = plan.get("already_have", [])
        st.markdown("**Already in pantry**")
        if already_have:
            for item in already_have:
                st.markdown(
                    f'<span style="color:#2A6A2A">✓ {item}</span>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Nothing matched in pantry.")

        # Uncertain matches
        uncertain = plan.get("uncertain", [])
        if uncertain:
            st.markdown("**Possible matches — please confirm**")
            for u in uncertain:
                st.markdown(
                    f'<span style="color:#8A6500">? {u["recipe_ingredient"]}</span>'
                    f'<span style="font-size:0.8rem;color:#888"> (pantry has: {u["pantry_item"]})</span>',
                    unsafe_allow_html=True,
                )

    with col_r:
        # Need to buy — editable quantities during approval
        need_to_buy = plan.get("need_to_buy", [])
        details     = plan.get("need_to_buy_details", []) or []
        qty_by_ing  = {d.get("ingredient", ""): d for d in details}
        st.markdown("**Need to buy**")

        if details and phase == "awaiting_approval":
            st.caption("Adjust amounts before approving:")
            for d in details:
                ing   = d.get("ingredient", "")
                amt0  = float(d.get("amount", 1.0) or 1.0)
                unit0 = d.get("unit", "each")
                c_a, c_u, c_n = st.columns([1.1, 1.4, 3], vertical_alignment="center")
                with c_a:
                    st.number_input("amount", min_value=0.0, value=amt0, step=0.5,
                                    key=f"qty_amt_{ing}", label_visibility="collapsed")
                with c_u:
                    st.selectbox("unit", _GROCERY_UNITS,
                                 index=_GROCERY_UNITS.index(unit0) if unit0 in _GROCERY_UNITS else 0,
                                 key=f"qty_unit_{ing}", label_visibility="collapsed")
                with c_n:
                    st.markdown(ing)
        elif need_to_buy:
            for item in need_to_buy:
                d = qty_by_ing.get(item, {})
                if d:
                    st.markdown(f"- {_qty_label(d.get('amount', 1), d.get('unit', 'each'), item)}")
                else:
                    st.markdown(f"- {item}")
        else:
            st.caption("Nothing to buy — you have everything!")

        # Substitutions
        substitutions = plan.get("substitutions", [])
        if substitutions:
            st.markdown("**Substitutions**")
            for sub in substitutions:
                note = f" — {sub['notes']}" if sub.get("notes") else ""
                st.markdown(
                    f'<span style="font-size:0.88rem">'
                    f'<span style="color:#C0504A">✗ {sub["original"]}</span>'
                    f' → <span style="color:#2A6A2A">✓ {sub["substitute"]}</span>'
                    f'<span style="color:#888;font-size:0.78rem"> ({sub["allergen"]} allergy{note})</span>'
                    f'</span>',
                    unsafe_allow_html=True,
                )

        # Blocked items
        blocked = plan.get("blocked", [])
        if blocked:
            st.markdown("**Cannot include — no safe substitute found**")
            for b in blocked:
                st.markdown(
                    f'<span style="color:#7A2A2A">✗ {b["ingredient"]}</span>'
                    f'<span style="font-size:0.78rem;color:#888"> {b["reason"]}</span>',
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)

    if phase == "awaiting_approval":
        if not need_to_buy and not plan.get("substitutions"):
            st.info("You already have everything in your pantry!")

        col_approve, col_edit, col_cancel = st.columns([2, 2, 2])
        with col_approve:
            if st.button("Approve cart draft", type="primary", use_container_width=True):
                # collect edited quantities from the widgets, keyed by ingredient name
                edits = {}
                for d in details:
                    ing = d.get("ingredient", "")
                    edits[ing] = {
                        "amount": st.session_state.get(f"qty_amt_{ing}", d.get("amount", 1.0)),
                        "unit":   st.session_state.get(f"qty_unit_{ing}", d.get("unit", "each")),
                    }
                st.session_state.grocery_qty_edits = edits
                st.session_state.grocery_phase = "resuming"
                st.rerun()
        with col_edit:
            if st.button("Edit pantry", use_container_width=True):
                st.info("Update your pantry in the sidebar, then click 'Plan groceries' again.")
        with col_cancel:
            if st.button("Cancel", use_container_width=True):
                st.session_state.grocery_phase = None
                st.rerun()

    elif phase == "cart_ready":
        if cart:
            insta_url = cart.get("instacart_url")
            if insta_url:
                st.success("Your shopping list is ready on Instacart! 🛒")
                st.link_button(
                    "🛒  Add everything to my Instacart cart",
                    insta_url,
                    use_container_width=True,
                    type="primary",
                )
                st.caption("Opens Instacart with every item pre-loaded. No order is placed until you check out.")
            else:
                st.success("Cart draft created! (No real order placed.)")
                if cart.get("instacart_error"):
                    st.caption(f"Instacart link unavailable — {cart['instacart_error']}")

            st.markdown("**Your grocery cart draft**")
            items_by_cat: dict[str, list] = {}
            for it in cart.get("items", []):
                label = _qty_label(it.get("amount", 1), it.get("unit", "each"), it["name"])
                items_by_cat.setdefault(it["category"], []).append(label)
            for cat, names in sorted(items_by_cat.items()):
                st.markdown(f"*{cat.title()}*")
                for n in names:
                    st.markdown(f"  - {n}")
            st.caption(f"Created at {cart.get('created_at', '')[:19].replace('T', ' ')} UTC")
        else:
            err = st.session_state.grocery_plan_data.get("error", "") if st.session_state.grocery_plan_data else ""
            if err:
                st.warning(err)

        if st.button("Close", use_container_width=False):
            st.session_state.grocery_phase = None
            st.session_state.grocery_plan_data = None
            st.session_state.grocery_cart = None
            st.rerun()


# Stash the inputs the grocery modal needs so it can read them on fragment reruns
st.session_state._active_members = active_members
st.session_state._profiles       = profiles

# The grocery plan lives in a modal pop-up that drives the full flow
# (planning → approval → cart). Only one dialog may open per run, so skip it if
# the pantry dialog was opened this run.
_pantry_opening = st.session_state.pop("_pantry_opening", False)
if not _pantry_opening and st.session_state.grocery_phase in ("planning", "awaiting_approval", "resuming", "cart_ready"):
    grocery_plan_dialog()
