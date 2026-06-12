"""
Read and load the data of recipes from Food.com. dataset obtained from Kaggle.com.
Not much cleaning needed for this step since the data is moderately available

How to run:
cd ./allochef
python -m ingestion.recipe_loader

"""


import ast

import sys

from pathlib import Path

import logging
import pandas as pd


sys.path.insert(0, str(Path(__file__).parent.parent))
from config import FOOD_COM_CSV
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

def _parse_list(value: str) -> list:
    """Parse a string-encoded Python list from Food.com CSV."""
    try:
        result = ast.literal_eval(value)
        return result if isinstance(result, list) else []
    except (ValueError, SyntaxError):
        return []

def load_recipe_data(csv_path: Path) -> pd.DataFrame:
    """
    Load and parse the Food.com recipes CSV.
    List columns (ingredients, steps, tags, nutrition) are stored as
    string-encoded Python lists and are parsed back into real lists.
    """
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} recipes from {csv_path}")

    for col in ["ingredients", "steps", "tags", "nutrition"]:
        df[col] = df[col].apply(_parse_list)

    return df


if __name__ == "__main__":
    df = load_recipe_data(FOOD_COM_CSV)
    print(df.head(3).to_string())
    print(f"\nColumns: {list(df.columns)}")
    print(f"Sample ingredients: {df['ingredients'].iloc[0]}")
