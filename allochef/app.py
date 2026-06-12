"""
AlloChef — What can we cook tonight?
Streamlit UI: family profile management + allergen-safe recipe suggestions.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import streamlit as st
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))

from agent.graph import graph
from agent.run_logger import read_recent_checks
from config import ALLERGEN_NAMES, OPENAI_API_KEY
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
[data-testid="stSidebar"] div[data-testid="stButton"] > button {
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
[data-testid="stSidebar"] div[data-testid="stButton"] > button *  {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
    width: 100% !important;
    height: 100% !important;
}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    background: #FFE0D6 !important;
    color: #C0504A !important;
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
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

for key, default in [
    ("result", None),
    ("ingredients_input", ""),
    ("scan_just_done", False),
    ("scan_count", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Helpers ───────────────────────────────────────────────────────────────────

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
                if ing:
                    ingredients.append(ing)
            elif section == "steps":
                m = re.match(r'^\d+\.\s*(.+)', stripped)
                if m:
                    steps.append(m.group(1).strip())

        card_data[" ".join(name.lower().split())] = {
            "name":        title_name,
            "description": description,
            "ingredients": ingredients,
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


def run_agent(ingredients: list[str], active_members: list[str], profiles: dict) -> dict:
    return graph.invoke({
        "ingredients":         ingredients,
        "active_members":      active_members,
        "family_profiles":     profiles,
        "messages":            [],
        "retrieval_attempts":  0,
        "generation_attempts": 0,
    })


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

# ── Ingredient input ──────────────────────────────────────────────────────────

st.markdown('<div class="section-label">What do you have in the kitchen?</div>', unsafe_allow_html=True)

tab_text, tab_photo = st.tabs(["  Type ingredients  ", "  Scan fridge photo  "])

with tab_text:
    st.markdown("""
    <div style="margin-bottom: 8px">
      <span style="font-size:0.9rem; color:#555">
        List what you have — separate with commas or new lines.
      </span>
    </div>
    """, unsafe_allow_html=True)
    typed = st.text_area(
        "ingredients",
        value=st.session_state.ingredients_input,
        placeholder="chicken, garlic, tomatoes, olive oil, lemon, onion...",
        height=110,
        label_visibility="collapsed",
    )
    if typed != st.session_state.ingredients_input:
        st.session_state.ingredients_input = typed

with tab_photo:
    st.markdown("""
    <div style="margin-bottom: 12px">
      <span style="font-size:0.9rem; color:#555">
        Upload a photo of your fridge or pantry — GPT-4o will identify the ingredients.
      </span>
    </div>
    """, unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Upload photo",
        type=["jpg", "jpeg", "png"],
        label_visibility="collapsed",
    )
    if st.session_state.scan_just_done:
        n = st.session_state.scan_count
        st.markdown(
            f'<div style="background:#D6F0D6;border:1px solid #A8D4A8;border-radius:10px;'
            f'padding:12px 18px;margin-bottom:12px;font-size:0.9rem;color:#2A6A2A">'
            f'✅ <strong>Scan complete</strong> — {n} ingredient{"s" if n != 1 else ""} identified. '
            f'Switch to the <em>Type ingredients</em> tab to review or edit them.</div>',
            unsafe_allow_html=True,
        )
        st.session_state.scan_just_done = False

    if uploaded:
        col_img, col_gap, col_btn = st.columns([3, 1, 2])
        with col_img:
            st.image(uploaded, use_container_width=True)
        with col_btn:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("Scan for ingredients", type="primary", use_container_width=True):
                with st.spinner("Identifying ingredients..."):
                    found = extract_ingredients_from_image(uploaded.read())
                if found:
                    st.session_state.ingredients_input = ", ".join(found)
                    st.session_state.scan_just_done = True
                    st.session_state.scan_count = len(found)
                    st.rerun()
                else:
                    st.warning("Could not identify ingredients. Try a clearer photo.")

ingredients = [
    i.strip()
    for i in st.session_state.ingredients_input.replace("\n", ",").split(",")
    if i.strip()
]

# ── Find Recipes ──────────────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)

col_btn, _ = st.columns([2, 5])
with col_btn:
    find_clicked = st.button(
        "Find Recipes",
        type="primary",
        use_container_width=True,
    )

if find_clicked and ingredients:
    st.session_state.result = None
    with st.spinner("Finding recipes safe for everyone..."):
        try:
            st.session_state.result = run_agent(ingredients, active_members, profiles)
        except Exception as e:
            st.error(f"Something went wrong: {e}")

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
            if display_ingredients:
                st.markdown("**Ingredients**")
                for ing in display_ingredients:
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

        def _render_recipe_grid(items: list, safe: bool) -> None:
            top_bg   = "linear-gradient(160deg,#F0F7F5,#EDF5F0)" if safe else "linear-gradient(160deg,#FDF5F3,#FFF0EC)"
            cols_per = 3
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
                    name        = meta.get("name", "unknown recipe").title()
                    minutes     = meta.get("minutes")
                    time_str    = f"{int(minutes)} min" if minutes else "—"
                    tags        = meta.get("tags", [])
                    flags       = [a for a in ALLERGEN_NAMES if meta.get(f"contains_{a}", False)]
                    badges      = "".join(allergen_badge_html(a) for a in flags)
                    emoji       = recipe_emoji(overview_doc)
                    pinecone_ings = parse_ingredients(overview_doc.page_content)
                    servings    = parse_servings(tags)
                    flag_labels = [ALLERGEN_LABELS[a] for a in flags]
                    llm_card    = card_data.get(" ".join(meta.get("name", "").lower().split()))
                    preview_ings = (llm_card or {}).get("ingredients") or pinecone_ings
                    ing_preview = ", ".join(preview_ings[:5]) + (f" +{len(preview_ings)-5} more" if len(preview_ings) > 5 else "")
                    badge_block = f'<div class="badge-row" style="margin:8px 0 4px">{badges}</div>' if badges else ""

                    with col:
                        with st.container(border=True):
                            st.markdown(
                                f'<div style="text-align:center;font-size:2.8rem;padding:16px 0 12px;'
                                f'background:{top_bg};border-radius:10px;margin-bottom:12px">{emoji}</div>'
                                f'<div style="font-family:\'Playfair Display\',serif;font-size:1rem;'
                                f'font-weight:600;color:#2D3436;margin-bottom:4px">{name}</div>'
                                f'<div style="font-size:0.8rem;color:#8A9E96;margin-bottom:6px">⏱ {time_str}</div>'
                                f'{badge_block}',
                                unsafe_allow_html=True,
                            )
                            if ing_preview:
                                st.caption(ing_preview)
                            with st.expander("View full recipe"):
                                _full_recipe_content(
                                    overview_doc, instr_docs, tags,
                                    pinecone_ings, minutes, servings, flag_labels,
                                    llm_card=llm_card,
                                )

        # LLM-selected recipe names (whitespace-normalised for reliable lookup)
        llm_names = {" ".join(k.split()) for k in card_data.keys()}

        # recipe_ids that have an allergen conflict (these must only show in substitution section)
        unsafe_recipe_ids = {
            pair["doc"].metadata.get("recipe_id", "")
            for pair in unsafe_pairs
        }

        # all LLM-selected chunks, split by whether they have an allergen conflict
        if not is_fallback:
            selected_chunks = {
                rid: chunks for rid, chunks in recipe_chunks.items()
                if any(" ".join(d.metadata.get("name", "").lower().split()) in llm_names for d in chunks)
            }
        else:
            selected_chunks = recipe_chunks

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


