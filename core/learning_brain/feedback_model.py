"""Feedback storage schema for the Learning Brain.

Feedback is stored as :Feedback nodes in the same Neo4j graph used by the
Graph Brain. Each feedback record refers to a specific extracted entity
(by id and type) and records whether the extraction was correct, and if
not, what the corrected value should have been.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

FEEDBACK_CONSTRAINT = (
    "CREATE CONSTRAINT feedback_id IF NOT EXISTS "
    "FOR (f:Feedback) REQUIRE f.id IS UNIQUE"
)


class Feedback(BaseModel):
    """A single piece of human feedback on an extracted entity."""

    id: str = Field(default_factory=lambda: f"feedback-{uuid.uuid4().hex[:12]}")
    document_id: str
    clause_id: str
    entity_id: str
    entity_type: str  # "Obligation" | "Risk" | "LegalNorm" | "Party" | ...
    original_value: str
    is_correct: bool
    corrected_value: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_properties(self) -> dict:
        return self.model_dump()


async def store_feedback(client, feedback: Feedback) -> None:
    """Persist a Feedback record as a :Feedback node, linked to its document and clause."""
    query = (
        "MERGE (f:Feedback {id: $id}) "
        "SET f += $properties "
        "WITH f "
        "MATCH (c:Clause {id: $clause_id}) "
        "MERGE (f)-[:ABOUT]->(c)"
    )
    async with client._driver.session(database=client._database) as session:
        await session.run(
            query,
            id=feedback.id,
            clause_id=feedback.clause_id,
            properties=feedback.to_properties(),
        )


async def list_feedback(client, entity_type: str | None = None) -> list[dict]:
    """Return all stored feedback, optionally filtered by entity_type."""
    if entity_type:
        query = "MATCH (f:Feedback {entity_type: $entity_type}) RETURN f ORDER BY f.timestamp"
        params = {"entity_type": entity_type}
    else:
        query = "MATCH (f:Feedback) RETURN f ORDER BY f.timestamp"
        params = {}

    async with client._driver.session(database=client._database) as session:
        result = await session.run(query, **params)
        return [dict(record["f"]) async for record in result]
