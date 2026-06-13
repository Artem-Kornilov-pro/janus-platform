"""Demo: run a sample contract through Graph Brain and query its risks.

Usage:
    python -m demo.graph_demo

Requires a running Neo4j instance configured via environment variables:
    NEO4J_URI (default: bolt://localhost:7687)
    NEO4J_USER (default: neo4j)
    NEO4J_PASSWORD
"""

import asyncio
import json
import os
from pathlib import Path

from core.document_brain.models import StructuredDocument
from core.graph_brain.graph_rag import build_graph
from core.graph_brain.neo4j_client import Neo4jClient

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "sample_contract.json"
DOCUMENT_ID = "contract-14-2026"


async def main() -> None:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    document = StructuredDocument(**data)

    print(f"Loaded document: {document.title}")
    print(f"Building graph (analyzing {len(document.sections)} clauses)...")

    nodes, relationships = build_graph(DOCUMENT_ID, document)

    print(f"Extracted {len(nodes)} nodes and {len(relationships)} relationships:")
    for rel in relationships:
        print(f"  ({rel['from_label']}:{rel['from_value']}) -[{rel['rel_type']}]-> "
              f"({rel['to_label']}:{rel['to_value']})")

    client = Neo4jClient(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ["NEO4J_PASSWORD"],
    )

    try:
        await client.setup_schema()
        await client.write_graph(nodes, relationships)

        print("\nQuery: Find all risks in this document")
        risks = await client.find_risks_for_document(DOCUMENT_ID)
        for risk in risks:
            print(f"  [{risk['severity']}] {risk['clause_title']}: {risk['risk']}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
