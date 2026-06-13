"""CLI for manually labeling Graph Brain extractions as correct/incorrect.

Walks through a diverse, unreviewed sample of extracted entities (chosen by
the active learner), asks the user to confirm or correct each one, and
stores the result as feedback for the Learning Brain.

Usage:
    python feedback_cli.py

Environment variables: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (see core.graph_brain.neo4j_client)
"""

import asyncio
import os

from core.graph_brain.neo4j_client import Neo4jClient
from core.learning_brain.active_learner import select_for_review
from core.learning_brain.feedback_model import Feedback, store_feedback


def _get_client() -> Neo4jClient:
    return Neo4jClient(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ["NEO4J_PASSWORD"],
    )


async def main() -> None:
    client = _get_client()
    try:
        await client.setup_schema()
        candidates = await select_for_review(client, per_type_limit=3)

        if not candidates:
            print("Nothing to review - no unreviewed extractions found.")
            return

        print(f"Reviewing {len(candidates)} extracted entities...\n")

        for item in candidates:
            print(f"[{item['entity_type']}] {item['value']}")
            answer = input("Correct? (y/n, or type a correction): ").strip()

            if answer.lower() == "y":
                feedback = Feedback(
                    document_id=item["clause_id"].split(":clause:")[0],
                    clause_id=item["clause_id"],
                    entity_id=item["entity_id"],
                    entity_type=item["entity_type"],
                    original_value=item["value"],
                    is_correct=True,
                )
            elif answer.lower() == "n":
                feedback = Feedback(
                    document_id=item["clause_id"].split(":clause:")[0],
                    clause_id=item["clause_id"],
                    entity_id=item["entity_id"],
                    entity_type=item["entity_type"],
                    original_value=item["value"],
                    is_correct=False,
                )
            else:
                feedback = Feedback(
                    document_id=item["clause_id"].split(":clause:")[0],
                    clause_id=item["clause_id"],
                    entity_id=item["entity_id"],
                    entity_type=item["entity_type"],
                    original_value=item["value"],
                    is_correct=False,
                    corrected_value=answer,
                )

            await store_feedback(client, feedback)
            print("  -> recorded\n")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
