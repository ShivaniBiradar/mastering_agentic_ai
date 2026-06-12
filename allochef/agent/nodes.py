"""
LangGraph nodes for the AlloChef agent.

Node execution order:
  aggregate_restrictions → hybrid_retrieve → allergen_check
      ├── [safe]   → generate_response
      └── [unsafe] → retrieve_substitute → generate_response
"""

from __future__ import annotations

import sys
from pathlib import Path

from langchain_community.retrievers import PineconeHybridSearchRetriever
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BM25_ENCODER_PATH,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USERNAME,
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_SUBS_INDEX,
)
from ingestion.graph_loader import query_substitutes

from agent.run_logger import log_check
from agent.state import AlloChefState

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_RETRIEVAL_ATTEMPTS  = 2   # how many times we rewrite the query before giving up
MAX_GENERATION_ATTEMPTS = 2   # how many times we regenerate before accepting the answer

# Comprehensive ingredient list per allergen.
# Two purposes:
#   1. Substitution lookup — tells retrieve_substitute_node which ingredients to
#      query Neo4j/Pinecone for when a recipe is flagged unsafe.
#   2. False-positive exposure — if NONE of these appear in a flagged recipe's
#      text, the allergen flag was likely a false positive from the embedder
#      threshold and the node skips substitution quietly.
_ALLERGEN_TO_INGREDIENTS: dict[str, list[str]] = {
    "milk": [
        # fluid dairy
        "milk", "whole milk", "skim milk", "2% milk", "low-fat milk", "nonfat milk",
        "buttermilk", "half and half", "heavy cream", "heavy whipping cream",
        "light cream", "whipping cream", "evaporated milk", "condensed milk",
        "sweetened condensed milk", "dry milk", "milk powder", "nonfat dry milk",
        # butter / fat
        "butter", "unsalted butter", "salted butter", "clarified butter", "ghee",
        # cream-based
        "sour cream", "creme fraiche", "cream cheese", "whipped cream",
        # cheese
        "cheese", "cheddar", "mozzarella", "parmesan", "parmigiano", "brie",
        "gouda", "swiss", "gruyere", "ricotta", "cottage cheese", "feta",
        "provolone", "gorgonzola", "mascarpone", "velveeta",
        # fermented
        "yogurt", "greek yogurt", "kefir",
        # protein fractions (common in processed / packaged foods)
        "whey", "casein", "lactalbumin", "caseinate", "sodium caseinate",
        "lactose", "milk solids",
    ],

    "eggs": [
        "egg", "eggs", "large egg", "large eggs", "medium egg",
        "egg white", "egg whites", "egg yolk", "egg yolks",
        "beaten egg", "whole egg", "egg wash",
        "dried egg", "powdered egg", "egg powder",
        "albumin", "meringue", "mayonnaise", "aioli", "hollandaise",
    ],

    "fish": [
        # fresh / frozen fish
        "fish", "salmon", "tuna", "cod", "tilapia", "halibut", "trout", "bass",
        "catfish", "snapper", "flounder", "sole", "mahi mahi", "swordfish",
        "sardines", "herring", "mackerel", "pollock", "haddock", "grouper",
        "sea bass", "bluefish", "perch", "pike", "branzino", "arctic char",
        # preserved / tinned
        "anchovies", "anchovy", "anchovy paste", "smoked salmon", "lox",
        "canned tuna", "canned salmon", "salt cod", "bacalao",
        # sauces and condiments derived from fish
        "fish sauce", "worcestershire sauce", "caesar dressing",
        "caviar", "roe", "fish stock", "fish broth",
    ],

    "shellfish": [
        # crustaceans
        "shrimp", "prawns", "crab", "lobster", "crayfish", "crawfish",
        "langoustine", "krill",
        # mollusks
        "scallops", "oysters", "clams", "mussels", "squid", "octopus",
        "calamari", "abalone", "snails", "escargot",
        # pastes and sauces
        "shrimp paste", "oyster sauce", "crab paste",
    ],

    "tree_nuts": [
        # whole nuts
        "almonds", "almond", "cashews", "cashew", "walnuts", "walnut",
        "pecans", "pecan", "hazelnuts", "hazelnut", "pistachios", "pistachio",
        "macadamia", "macadamia nuts", "brazil nuts", "pine nuts", "chestnuts",
        # butters and spreads
        "almond butter", "cashew butter", "hazelnut spread", "nutella",
        "praline", "marzipan", "frangipane",
        # flours and milks
        "almond flour", "almond meal", "chestnut flour",
        "almond milk", "cashew milk", "hazelnut milk",
        # oils and confections
        "walnut oil", "almond oil", "nougat", "gianduja", "mixed nuts", "trail mix",
    ],

    "peanuts": [
        "peanuts", "peanut", "groundnuts", "groundnut",
        "peanut butter", "peanut oil", "peanut flour", "peanut sauce",
        "satay sauce", "satay", "kung pao sauce", "beer nuts", "boiled peanuts",
    ],

    "wheat": [
        # flours
        "flour", "all-purpose flour", "bread flour", "cake flour", "wheat flour",
        "whole wheat flour", "self-rising flour", "semolina", "durum",
        "spelt", "kamut", "einkorn",
        # wheat fractions
        "wheat germ", "wheat bran", "wheat starch", "modified wheat starch",
        # pasta and dried grains
        "pasta", "spaghetti", "penne", "fettuccine", "linguine", "lasagna",
        "noodles", "egg noodles", "couscous", "bulgur", "farro", "wheat berries",
        "orzo",
        # bread products
        "bread", "breadcrumbs", "bread crumbs", "panko", "croutons",
        "pita", "naan", "tortilla", "crackers", "matzo",
        # batters, coatings, gluten products
        "batter", "breading", "tempura batter", "seitan", "vital wheat gluten",
    ],

    "gluten": [
        # wheat-derived (overlap intentional — gluten is the broader category)
        "flour", "all-purpose flour", "bread flour", "wheat flour", "semolina",
        "pasta", "bread", "breadcrumbs", "couscous", "bulgur", "farro",
        "spelt", "kamut", "seitan",
        # barley
        "barley", "pearl barley", "barley flour", "malt", "malt vinegar",
        "malt extract", "beer", "ale", "lager",
        # rye
        "rye", "rye flour", "rye bread",
        # oats (frequently cross-contaminated unless certified GF)
        "oats", "rolled oats", "oat flour",
    ],

    "soy": [
        # whole / fermented
        "tofu", "tempeh", "edamame", "miso", "natto", "soybeans", "soy beans",
        # sauces and condiments
        "soy sauce", "tamari", "shoyu", "teriyaki sauce", "hoisin sauce",
        "black bean sauce",
        # dairy alternatives
        "soy milk", "soy cheese", "soy cream cheese", "soy yogurt",
        # protein products and oils
        "soy protein", "soy protein isolate", "textured vegetable protein", "tvp",
        "hydrolyzed soy protein", "soy flour", "soy lecithin", "soybean oil",
    ],

    "sesame": [
        # seeds
        "sesame seeds", "sesame", "white sesame seeds", "black sesame seeds",
        "toasted sesame seeds", "benne seeds", "til",
        # oils and pastes
        "sesame oil", "toasted sesame oil", "sesame paste", "tahini",
        # sesame-containing foods
        "hummus", "halva", "halvah", "gomashio",
    ],
}


_RECIPE_FORMAT = """\
**[Recipe Name]**
- [One sentence on why this is a great match — style, flavor, or occasion. Do NOT list ingredients.]

Ingredients:
- [copy each ingredient exactly as listed in the context, one per line]

Steps:
1. [Split Raw instructions into one logical action per step. Do not add or remove any information — only split into clear numbered steps.]
2. [...]

---"""

_RESPONSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", f"""You are AlloChef, a warm and practical cooking assistant for multi-diet families.
From the recipes in the context below, suggest 3 to 5 recipes. Prioritise recipes that use more of the available ingredients, but a recipe that uses even one of them is a valid suggestion.
Do NOT invent recipes — only suggest recipes that appear in the context.
If no recipes are available, say so honestly.

Format each recipe exactly like this:

{_RECIPE_FORMAT}

Rules:
- Copy the recipe name exactly as it appears in the context (### heading).
- Copy ingredients exactly from the context. Do not add or remove any.
- Split Raw instructions into numbered steps — one action per step. Do not add, remove, or rephrase any information.
- The one-line description must focus on style, flavor, or occasion only.
- SUBSTITUTION OVERRIDE: If a recipe appears in 'Substitutions available', you MUST replace every mention of the allergen ingredient with its listed substitute — in BOTH the Ingredients list AND every Step. The allergen ingredient must NOT appear anywhere in your output for that recipe. This rule overrides the "copy exactly" rule above."""),
    ("human", (
        "Available ingredients: {ingredients}\n"
        "Eating tonight: {active_members}\n"
        "Dietary restrictions: {restrictions}\n\n"
        "Safe recipes (ONLY suggest from this list):\n{recipes_context}\n\n"
        "Substitutions available:\n{substitutions_context}\n\n"
        "What should we cook tonight?"
    )),
])

_RESPONSE_PROMPT_STRICT = ChatPromptTemplate.from_messages([
    ("system", f"""You are AlloChef. Your previous response referenced a recipe not in the context.
You MUST only use recipes from the context. Copy recipe names exactly as they appear (### heading).

Format each recipe exactly like this:

{_RECIPE_FORMAT}

Rules:
- Copy the recipe name exactly — do not paraphrase or shorten it.
- Copy ingredients exactly from context. Do not add or remove any.
- Copy steps exactly from Raw instructions. Do not add, remove, reorder, or rephrase any step.
- SUBSTITUTION OVERRIDE: If a recipe appears in 'Substitutions available', replace every mention of the allergen ingredient with its substitute in BOTH Ingredients AND Steps. The allergen must not appear in your output for that recipe."""),
    ("human", (
        "Available ingredients: {ingredients}\n"
        "Eating tonight: {active_members}\n"
        "Dietary restrictions: {restrictions}\n\n"
        "You may ONLY suggest from these exact recipes:\n{recipes_context}\n\n"
        "Substitutions available:\n{substitutions_context}\n\n"
        "Suggest what to cook, staying strictly within the recipes listed above."
    )),
])

_RELEVANCE_CHECK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "You are strictly checking whether retrieved recipe documents are relevant to a user's ingredients. "
        "Answer 'yes' only if the majority of retrieved documents contain recipes that directly use "
        "the user's listed ingredients. If the recipes are unrelated or only share one incidental ingredient, "
        "answer 'no'. "
        "Reply with 'yes' or 'no' followed by a one-line reason, e.g. 'no - recipes are desserts, user has chicken and ginger'."
    )),
    ("human", (
        "User's available ingredients: {ingredients}\n\n"
        "Retrieved recipes:\n{docs_summary}\n\n"
        "Are the majority of these recipes directly relevant to the user's ingredients? "
        "Reply 'yes' or 'no' followed by a one-line reason."
    )),
])

_HALLUCINATION_CHECK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "You are checking whether a cooking suggestion is grounded in the provided recipe context. "
        "A suggestion is hallucinated if it references a recipe name that does NOT appear in the context. "
        "The one-line descriptions are style/occasion framing — do not check them for ingredient accuracy. "
        "Reply with 'yes' (all recipe names found in context) or 'no' (a recipe name is missing) "
        "followed by a one-line reason, "
        "e.g. 'no - suggested Pad Thai but no Pad Thai recipe appears in context'."
    )),
    ("human", (
        "Retrieved recipe context (the ONLY allowed source):\n{context}\n\n"
        "Generated suggestion:\n{response}\n\n"
        "Do ALL recipe names in the suggestion appear in the context above? "
        "Reply 'yes' or 'no' followed by a one-line reason."
    )),
])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_retriever() -> PineconeHybridSearchRetriever:
    """Build a Pinecone hybrid retriever using saved BM25Encoder."""
    encoder = BM25Encoder()
    encoder.load(str(BM25_ENCODER_PATH))

    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)

    return PineconeHybridSearchRetriever(
        embeddings=embeddings,
        sparse_encoder=encoder,
        index=index,
        top_k=20,
        text_key="text",
    )


def _pinecone_substitute_fallback(ingredient: str, allergen: str) -> list[dict]:
    """Semantic fallback when Neo4j has no substitute for an ingredient."""
    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_SUBS_INDEX)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)
    query_vec  = embeddings.embed_query(f"substitute for {ingredient} {allergen} allergy")

    results = index.query(
        vector=query_vec,
        top_k=3,
        include_metadata=True,
        filter={"allergen": allergen},
    )

    return [
        {
            "original":   m.metadata.get("original", ingredient),
            "substitute": m.metadata.get("substitute", ""),
            "works_in":   m.metadata.get("works_in", []),
            "notes":      m.metadata.get("notes", ""),
        }
        for m in results.matches
        if m.score > 0.7
    ]


# ── Nodes ──────────────────────────────────────────────────────────────────────

def aggregate_restrictions_node(state: AlloChefState) -> dict:
    """
    Merge allergen restrictions for all active family members into a flat list.
    e.g. Maya has ["milk"] and Leo has ["peanuts"] → restrictions = ["milk", "peanuts"]
    """
    profiles      = state.get("family_profiles", {})
    active        = state.get("active_members", [])
    restrictions: set[str] = set()

    for member in active:
        allergens = profiles.get(member, [])
        restrictions.update(allergens)

    return {"restrictions": sorted(restrictions)}


def hybrid_retrieve_node(state: AlloChefState) -> dict:
    """
    Query Pinecone with dense + BM25 sparse vectors.
    Uses all ingredients so allergen-containing recipes are retrieved,
    caught by allergen_check_node, and passed to retrieve_substitute_node.
    """
    ingredients = state.get("ingredients", [])
    query = state.get("query") or " ".join(ingredients)

    retriever = _build_retriever()
    docs      = retriever.invoke(query)

    return {"query": query, "retrieved_docs": docs}


def _confirmed_allergen(doc, allergen: str) -> bool:
    """
    Verify an allergen flag by scanning the recipe text for known allergen
    ingredients. Returns True only if at least one known ingredient is found.

    This catches false positives from the embedding-based allergen detector —
    e.g. a recipe flagged contains_sesame=True because "sesame" was semantically
    close to some ingredient, but none of tahini / sesame oil / sesame seeds
    actually appear in the recipe text.
    """
    text = (doc.page_content + " " + doc.metadata.get("text", "")).lower()
    return any(ing in text for ing in _ALLERGEN_TO_INGREDIENTS.get(allergen, []))


def allergen_check_node(state: AlloChefState) -> dict:
    """
    Check each retrieved doc's allergen metadata against tonight's restrictions.

    Two-step check per allergen flag:
      1. Does the metadata flag say contains_<allergen>=True?  (index-time signal)
      2. Does the recipe text actually contain a known allergen ingredient?  (runtime verify)

    Only flags that pass BOTH steps are treated as real conflicts.
    Flags that fail step 2 are quietly dropped as false positives from the embedder.
    """
    restrictions = state.get("restrictions", [])
    docs         = state.get("retrieved_docs", [])

    if not restrictions:
        return {"safe_recipes": docs, "unsafe_pairs": []}

    safe, unsafe = [], []
    for doc in docs:
        confirmed_conflicts = [
            a for a in restrictions
            if doc.metadata.get(f"contains_{a}", False) and _confirmed_allergen(doc, a)
        ]
        if confirmed_conflicts:
            unsafe.append({"doc": doc, "allergens": confirmed_conflicts})
        else:
            safe.append(doc)

    return {"safe_recipes": safe, "unsafe_pairs": unsafe}


def _recipe_ingredients(doc) -> list[str]:
    """Parse ingredient list from the stored text metadata field."""
    text = doc.metadata.get("text", "")
    for line in text.splitlines():
        if line.lower().startswith("ingredients:"):
            return [i.strip() for i in line.split(":", 1)[1].split(",")]
    return []


def retrieve_substitute_node(state: AlloChefState) -> dict:
    """
    For each unsafe recipe + allergen:
      1. Query Neo4j for deterministic substitutes (Tier 1)
      2. Fall back to Pinecone semantic search if Neo4j has nothing (Tier 2)
    Only looks up ingredients actually present in the recipe (parsed from metadata),
    not every possible allergen ingredient — avoids hundreds of redundant lookups.
    """
    unsafe_pairs  = state.get("unsafe_pairs", [])
    restrictions  = state.get("restrictions", [])
    substitutions = []

    for pair in unsafe_pairs:
        doc          = pair["doc"]
        recipe_name  = doc.metadata.get("name", "Unknown recipe")
        recipe_id    = doc.metadata.get("recipe_id", "")

        for allergen in pair["allergens"]:
            available_substitutes = []

            # find allergen ingredients that appear in the recipe text (substring match).
            # _recipe_ingredients() reads metadata["text"] which is absent on instruction
            # chunks, so we scan page_content directly — same approach as _confirmed_allergen.
            recipe_text   = (doc.page_content + " " + doc.metadata.get("text", "")).lower()
            allergen_ings = _ALLERGEN_TO_INGREDIENTS.get(allergen, [])
            # deduplicate; prefer longer (more-specific) matches first so "shrimp paste"
            # is looked up before "shrimp"
            culprit_ings  = list({
                ing for ing in allergen_ings if ing in recipe_text
            })
            culprit_ings.sort(key=len, reverse=True)

            # if nothing matched (shouldn't happen, but be safe), skip
            if not culprit_ings:
                continue

            for ingredient in culprit_ings:
                neo4j_subs = query_substitutes(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
                                               ingredient, allergen)
                if neo4j_subs:
                    # filter: substitute must not trigger any other active restriction
                    safe_subs = [
                        s for s in neo4j_subs
                        if not any(
                            s["substitute"].lower() in _ALLERGEN_TO_INGREDIENTS.get(other, [])
                            for other in restrictions
                            if other != allergen
                        )
                    ]
                    for s in safe_subs:
                        available_substitutes.append({
                            "original":   ingredient,
                            "substitute": s["substitute"],
                            "works_in":   s.get("works_in", []),
                            "notes":      s.get("notes", ""),
                            "source":     "neo4j",
                        })
                else:
                    # Tier 2 fallback: Pinecone semantic search
                    pinecone_subs = _pinecone_substitute_fallback(ingredient, allergen)
                    for s in pinecone_subs:
                        available_substitutes.append({**s, "source": "pinecone"})

            if available_substitutes:
                substitutions.append({
                    "recipe_name":           recipe_name,
                    "recipe_id":             recipe_id,
                    "allergen":              allergen,
                    "available_substitutes": available_substitutes,
                })
                # recipe now has substitutes — add to safe list
                state["safe_recipes"].append(doc)

    return {"substitutions": substitutions}


def generate_response_node(state: AlloChefState) -> dict:
    """
    Format retrieved recipes + substitutions into context and generate a
    conversational response with GPT-4o.
    """
    safe_recipes  = state.get("safe_recipes", [])
    substitutions = state.get("substitutions", [])
    ingredients   = state.get("ingredients", [])
    active        = state.get("active_members", [])
    restrictions  = state.get("restrictions", [])

    # group docs by recipe_id so we can pass full ingredients + instructions
    from collections import defaultdict
    recipe_groups: dict = defaultdict(lambda: {"overview": None, "instructions": []})
    for doc in safe_recipes:
        rid = doc.metadata.get("recipe_id", "")
        if doc.metadata.get("chunk_type") == "overview":
            recipe_groups[rid]["overview"] = doc
        else:
            recipe_groups[rid]["instructions"].append(doc)

    recipes_lines: list[str] = []
    for rid, group in recipe_groups.items():
        ov           = group["overview"]
        instr_chunks = sorted(group["instructions"], key=lambda d: d.metadata.get("chunk_index", 0))
        # use any available chunk for metadata if overview wasn't retrieved
        any_doc  = ov or (instr_chunks[0] if instr_chunks else None)
        if not any_doc:
            continue
        name     = " ".join(any_doc.metadata.get("name", "Unknown").split())  # normalise whitespace
        minutes  = any_doc.metadata.get("minutes", "")
        time_str = f" ({minutes} min)" if minutes else ""
        instr_text = " ".join(
            " ".join(l for l in d.page_content.splitlines() if not l.lower().startswith("recipe:"))
            for d in instr_chunks
        )
        recipes_lines.append(f"### {name}{time_str}")
        if ov:
            recipes_lines.append(ov.page_content)
        if instr_text:
            recipes_lines.append(f"Raw instructions: {instr_text}")
        recipes_lines.append("")
    recipes_context = "\n".join(recipes_lines) if recipes_lines else "No safe recipes found."

    # format substitution context
    subs_lines: list[str] = []
    for entry in substitutions:
        for sub in entry["available_substitutes"][:2]:  # top 2 per allergen
            works = ", ".join(sub.get("works_in", []))
            subs_lines.append(
                f"- In {entry['recipe_name']}: replace {sub['original']} "
                f"→ {sub['substitute']} (works in: {works}) {sub.get('notes', '')}"
            )
    substitutions_context = "\n".join(subs_lines) if subs_lines else "No substitutions needed."

    # use stricter grounding prompt on retry after a hallucination was detected
    generation_attempts = state.get("generation_attempts", 0)
    prompt_template = _RESPONSE_PROMPT_STRICT if generation_attempts > 0 else _RESPONSE_PROMPT
    temperature     = 0.0 if generation_attempts > 0 else 0.3

    llm    = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=temperature, max_tokens=2000)
    prompt = prompt_template.invoke({
        "ingredients":           ", ".join(ingredients),
        "active_members":        ", ".join(active),
        "restrictions":          ", ".join(restrictions) if restrictions else "none",
        "recipes_context":       recipes_context,
        "substitutions_context": substitutions_context,
    })

    ai_response   = llm.invoke(prompt)
    response_text = ai_response.content

    return {
        "response":             response_text,
        "messages":             [AIMessage(content=response_text)],
        "generation_attempts":  generation_attempts + 1,
    }


def check_relevance_node(state: AlloChefState) -> dict:
    """
    LLM-as-judge: are the retrieved docs relevant to the user's ingredients?
    Sets relevance_verdict to 'relevant' or 'not_relevant'.
    Uses gpt-4o-mini — this is a binary classification, not generation.
    """
    ingredients = state.get("ingredients", [])
    docs        = state.get("retrieved_docs", [])

    docs_summary = "\n".join(
        f"- {d.metadata.get('name', 'Unknown')}: {d.page_content[:150]}"
        for d in docs[:6]
    )

    llm    = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0)
    prompt = _RELEVANCE_CHECK_PROMPT.invoke({
        "ingredients": ", ".join(ingredients),
        "docs_summary": docs_summary,
    })

    llm_raw = llm.invoke(prompt).content.strip()
    verdict = "relevant" if llm_raw.lower().startswith("yes") else "not_relevant"
    reason  = llm_raw.split("-", 1)[-1].strip() if "-" in llm_raw else llm_raw

    log_check(
        "relevance_check",
        query              = state.get("query", ""),
        ingredients        = ", ".join(ingredients),
        verdict            = verdict,
        reason             = reason,
        llm_raw            = llm_raw,
        retrieval_attempts = state.get("retrieval_attempts", 0),
        docs_summary       = docs_summary,
    )
    return {"relevance_verdict": verdict}


def rewrite_query_node(state: AlloChefState) -> dict:
    """
    Rewrite the retrieval query when retrieved docs were not relevant.
    Each attempt broadens the query progressively:
      attempt 0 → explicit recipe framing: "recipe with chicken tomato garlic"
      attempt 1 → top 3 ingredients only: "chicken tomato garlic"
    """
    ingredients = state.get("ingredients", [])
    attempts    = state.get("retrieval_attempts", 0)

    if attempts == 0:
        query = "recipe with " + " ".join(ingredients)
    else:
        query = " ".join(ingredients[:3])

    return {
        "query":               query,
        "retrieval_attempts":  attempts + 1,
    }


def check_hallucination_node(state: AlloChefState) -> dict:
    """
    LLM-as-judge: does the generated response reference only recipes from
    the retrieved context, or did it invent details?
    Sets hallucination_verdict to 'grounded' or 'hallucinating'.
    Uses gpt-4o-mini — just a binary check.
    """
    safe_recipes = state.get("safe_recipes", [])
    response     = state.get("response", "")

    # build a list of normalised recipe names — the check only needs names, not page content.
    # including page_content risks the judge LLM confusing the old triple-spaced name stored
    # in the text with the normalised name used in the response.
    seen_names: set[str] = set()
    for d in safe_recipes:
        seen_names.add(" ".join(d.metadata.get("name", "Unknown").split()))
    context = "\n".join(f"- {n}" for n in sorted(seen_names))

    if not context:
        verdict = "hallucinating"
        reason  = "no recipes were retrieved — any response is hallucinated"
        llm_raw = ""
    else:
        llm    = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0)
        prompt = _HALLUCINATION_CHECK_PROMPT.invoke({"context": context, "response": response})
        llm_raw = llm.invoke(prompt).content.strip()
        verdict = "grounded" if llm_raw.lower().startswith("yes") else "hallucinating"
        reason  = llm_raw.split("-", 1)[-1].strip() if "-" in llm_raw else llm_raw

    log_check(
        "hallucination_check",
        query               = state.get("query", ""),
        verdict             = verdict,
        reason              = reason,
        llm_raw             = llm_raw,
        generation_attempts = state.get("generation_attempts", 0),
        response_snippet    = response[:300],
    )
    return {"hallucination_verdict": verdict}


# ── Routing ────────────────────────────────────────────────────────────────────

def route_allergen_check(state: AlloChefState) -> str:
    """Route to substitution if any unsafe recipes exist, otherwise generate directly."""
    return "substitute" if state.get("unsafe_pairs") else "generate"


def route_relevance_check(state: AlloChefState) -> str:
    """
    After check_relevance_node:
      - 'relevant'     → proceed to allergen_check
      - 'not_relevant' → rewrite query and re-retrieve (if under attempt limit)
      - 'proceed'      → max attempts reached, continue with whatever was retrieved
    """
    if state.get("retrieval_attempts", 0) >= MAX_RETRIEVAL_ATTEMPTS:
        return "proceed"
    return state.get("relevance_verdict", "relevant")


def fallback_response_node(state: AlloChefState) -> dict:
    """
    Called when the hallucination checker fires MAX_GENERATION_ATTEMPTS times.
    Returns an honest "I don't know" rather than delivering a potentially
    hallucinated answer. Safety over helpfulness.
    """
    ingredients = state.get("ingredients", [])
    ingredient_str = ", ".join(ingredients) if ingredients else "the ingredients you provided"
    message = (
        f"I wasn't able to find reliable recipe suggestions I'm confident about for "
        f"{ingredient_str}. This can happen when the available recipes don't closely "
        f"match what you have on hand. Try rephrasing your ingredients, or ask me "
        f"about a specific recipe you have in mind and I'll do my best to help."
    )
    log_check(
        "fallback_triggered",
        query               = state.get("query", ""),
        ingredients         = ", ".join(ingredients),
        generation_attempts = state.get("generation_attempts", 0),
        reason              = "max hallucination retries reached — returning fallback response",
    )
    return {
        "response": message,
        "messages": [AIMessage(content=message)],
    }


def route_hallucination_check(state: AlloChefState) -> str:
    """
    After check_hallucination_node:
      - 'grounded'      → deliver to user
      - 'hallucinating' → regenerate with stricter prompt (if under attempt limit)
      - 'unknown'       → max attempts reached, deliver honest fallback instead
    """
    verdict = state.get("hallucination_verdict", "grounded")
    if verdict == "grounded":
        return "grounded"
    # still hallucinating — fall back if at the retry cap, otherwise regenerate
    if state.get("generation_attempts", 0) >= MAX_GENERATION_ATTEMPTS:
        return "unknown"
    return verdict
