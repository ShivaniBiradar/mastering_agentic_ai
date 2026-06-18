from pathlib import Path
from dotenv import load_dotenv
import os
load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEANED_DIR = DATA_DIR / "cleaned"
SUBS_DIR = DATA_DIR / "substitutions"

FOOD_COM_CSV = RAW_DIR / "recipes.csv"
CLEANED_RECIPES_JSONL = CLEANED_DIR / "recipes.jsonl"
SUBSTITUTIONS_JSON = SUBS_DIR / "seed_substitutions.json"
ALLERGEN_VOCAB_JSON = SUBS_DIR / "allergen_vocab.json"
ALLERGEN_EMBEDDINGS_CACHE = CLEANED_DIR / "allergen_embeddings_cache.json"
BM25_ENCODER_PATH = CLEANED_DIR / "bm25_encoder.json"
PROFILES_DB       = DATA_DIR / "profiles.db"

USDA_FDC_API_KEY = os.getenv("USDA_FDC_API_KEY")

OPENAI_API_KEY         = os.getenv("OPENAI_API_KEY")
NEBIUS_API_KEY         = os.getenv("NEBIUS_API_KEY")
NEBIUS_BASE_URL        = os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/")
NEBIUS_MODEL           = os.getenv("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")
# Cart backend: "mock" (default, no external account) or "instacart" (real MCP)
CART_PROVIDER          = os.getenv("CART_PROVIDER", "mock")
# Substitution agent — stronger model + a little creativity for context-aware picks.
# The allergen safety check stays on a cheap, deterministic model (temp 0).
SUBSTITUTION_AGENT_MODEL       = os.getenv("SUBSTITUTION_AGENT_MODEL", "gpt-4o")
SUBSTITUTION_AGENT_TEMPERATURE = float(os.getenv("SUBSTITUTION_AGENT_TEMPERATURE", "0.4"))
SUBSTITUTION_SAFETY_MODEL      = os.getenv("SUBSTITUTION_SAFETY_MODEL", "gpt-4o-mini")
# Grocery + Meal orchestrator agents (light reasoning / routing → cheap model)
GROCERY_AGENT_MODEL            = os.getenv("GROCERY_AGENT_MODEL", "gpt-4o-mini")
ORCHESTRATOR_MODEL             = os.getenv("ORCHESTRATOR_MODEL", "gpt-4o-mini")
INSTACART_API_KEY      = os.getenv("INSTACART_API_KEY")
INSTACART_MCP_URL      = os.getenv("INSTACART_MCP_URL", "https://mcp.dev.instacart.tools/mcp")
PINECONE_API_KEY       = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME    = os.getenv("PINECONE_INDEX_NAME", "allochef-recipes")
PINECONE_SUBS_INDEX    = os.getenv("PINECONE_SUBS_INDEX_NAME", "allochef-substitutions")
NEO4J_URI              = os.getenv("NEO4J_URI")
NEO4J_USERNAME         = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD         = os.getenv("NEO4J_PASSWORD")

# Open Food Facts allergen tag IDs mapped to internal names
ALLERGEN_NAMES: list[str] = [
    "milk",    
    "eggs",     
    "fish",
    "shellfish",
    "tree_nuts",
    "peanuts",
    "wheat",
    "gluten",
    "soy",
    "sesame",
]
FOOD_GENERIC_TERMS: set[str] =  [
    "citric", "acid", "sodium", "starch", "modified", "natural", "artificial",
    "flavor", "flavors", "flavoring", "extract", "color", "colour", "dye","coloring",
    "preservative", "concentrate", "powder", "dried", "dehydrated", "enriched",
    "bleached", "organic", "filtered", "purified", "refined", "hydrogenated",
    "partially", "water", "salt", "sugar", "oil", "vinegar", "spice", "spices",
    "lecithin", "xanthan", "gum", "mono", "diglycerides", "emulsifier",
    "potassium", "calcium", "iron", "zinc", "niacin", "riboflavin", "thiamine",
    "garlic", "onion", "ginger", "pepper", "paprika", "turmeric", "cumin","bisulfite",
    "sauce", "corn", "brown", "sulfate","vitamin","vegetable","tripolyphosphate",
    "less", "cocoa", "chocolate", "vanilla", "vanillin", "cinnamon", "clove","seasalt","sea",
    "baking","white","whole","contains","rice", "corn", "tapioca", "potato", "oat",
    "canola", "fiber", "cane", 

]

USDA_FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

# Only needed for allergens where the name itself doesn't work as a USDA search term
ALLERGEN_QUERY_OVERRIDES: dict[str, str] = {
    "tree_nuts": "almonds walnuts cashews pecans",
    "gluten":    "wheat bread barley rye",
}
