"""
Loads seed substitutions into Neo4j Aura as a knowledge graph.

Graph structure:
  (:Ingredient {name}) -[:SUBSTITUTES {allergen, works_in, notes}]-> (:Ingredient {name})
  (:Ingredient {name}) -[:TRIGGERS]-> (:Allergen {name})

Run once after Neo4j Aura instance is set up:
  cd allochef
  python -m ingestion.graph_loader
"""

import json
import logging
import sys
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME, SUBSTITUTIONS_JSON

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_graph(uri: str, username: str, password: str) -> None:
    with open(SUBSTITUTIONS_JSON) as f:
        data = json.load(f)

    entries = data["substitutions"]
    driver = GraphDatabase.driver(uri, auth=(username, password))

    with driver.session() as session:
        # clear existing graph so reruns are idempotent
        session.run("MATCH (n) DETACH DELETE n")
        logger.info("Cleared existing graph")

        for entry in entries:
            original   = entry["original"].lower().strip()
            substitute = entry["substitute"].lower().strip()
            allergen   = entry["allergen"].lower().strip()
            works_in   = entry.get("works_in", [])
            notes      = entry.get("notes", "")

            # create ingredient nodes + SUBSTITUTES edge
            session.run(
                """
                MERGE (orig:Ingredient {name: $original})
                MERGE (sub:Ingredient  {name: $substitute})
                MERGE (orig)-[r:SUBSTITUTES]->(sub)
                SET r.allergen = $allergen,
                    r.works_in = $works_in,
                    r.notes    = $notes
                """,
                original=original,
                substitute=substitute,
                allergen=allergen,
                works_in=works_in,
                notes=notes,
            )

            # create allergen node + TRIGGERS edge from original ingredient
            session.run(
                """
                MERGE (orig:Ingredient {name: $original})
                MERGE (a:Allergen      {name: $allergen})
                MERGE (orig)-[:TRIGGERS]->(a)
                """,
                original=original,
                allergen=allergen,
            )

        logger.info(f"Loaded {len(entries)} substitution entries")

        # verify
        result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count")
        for record in result:
            logger.info(f"  {record['label']}: {record['count']} nodes")

        result = session.run("MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS count")
        for record in result:
            logger.info(f"  {record['rel']}: {record['count']} edges")

    driver.close()
    logger.info("Graph loaded successfully")


# Module-level singleton — one driver reused for all query_substitutes calls.
# Creating a new driver per call opens a new connection pool each time; under
# load (eval suite, multiple unsafe recipes) this exhausts Neo4j Aura's connection
# limit and causes ConnectionAcquisitionTimeoutError.
_singleton_driver = None
_singleton_creds: tuple[str, str, str] | None = None


def _get_driver(uri: str, username: str, password: str):
    global _singleton_driver, _singleton_creds
    creds = (uri, username, password)
    if _singleton_driver is None or _singleton_creds != creds:
        if _singleton_driver is not None:
            try:
                _singleton_driver.close()
            except Exception:
                pass
        _singleton_driver = GraphDatabase.driver(uri, auth=(username, password))
        _singleton_creds  = creds
    return _singleton_driver


def query_substitutes(uri: str, username: str, password: str, ingredient: str, allergen: str) -> list[dict]:
    """
    Find safe substitutes for an ingredient given an allergen constraint.
    Used by the LangGraph agent's substitute node.
    """
    driver = _get_driver(uri, username, password)
    with driver.session() as session:
        result = session.run(
            """
            MATCH (orig:Ingredient {name: $ingredient})-[r:SUBSTITUTES]->(sub:Ingredient)
            WHERE r.allergen = $allergen
            AND NOT (sub)-[:TRIGGERS]->(:Allergen {name: $allergen})
            RETURN sub.name AS substitute, r.works_in AS works_in, r.notes AS notes
            """,
            ingredient=ingredient.lower().strip(),
            allergen=allergen.lower().strip(),
        )
        substitutes = [dict(record) for record in result]
    return substitutes


if __name__ == "__main__":
    from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME

    if not NEO4J_URI:
        logger.error("NEO4J_URI not set in .env")
        sys.exit(1)

    load_graph(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

    # quick test query
    logger.info("\nTest query: substitutes for peanut butter (peanuts allergy)")
    results = query_substitutes(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, "peanut butter", "peanuts")
    for r in results:
        logger.info(f"  → {r['substitute']} | works in: {r['works_in']}")
