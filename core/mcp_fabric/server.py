"""MCP server exposing the Janus Lex knowledge graph as tools.

Runs as an SSE server (FastAPI/Starlette under the hood via FastMCP) so it
can be connected to Claude Desktop, Cursor, or any other MCP client.

Tools:
    get_entity_by_label(label, name)  - look up nodes by label and name
    find_relationships(source, target) - relationships between two entities
    extract_from_text(text)            - run Document Brain + Graph Brain on raw text
    ask_graph(question)                - natural language -> Cypher -> results
    submit_feedback(...)               - record human feedback on an extracted entity
    get_learning_stats()               - precision/reward per entity type from feedback

Environment variables:
    NEO4J_URI       (default: bolt://localhost:7687)
    NEO4J_USER      (default: neo4j)
    NEO4J_PASSWORD  (required)
    MCP_TRANSPORT   (default: sse)
    MCP_PORT        (default: 8000)
"""

from __future__ import annotations

import os
import uuid

from mcp.server.fastmcp import FastMCP

from core.document_brain.structurer import structure_text
from core.graph_brain.graph_rag import build_graph
from core.graph_brain.neo4j_client import Neo4jClient
from core.learning_brain.feedback_model import Feedback, list_feedback, store_feedback
from core.learning_brain.prompt_optimizer import retrain_prompts
from core.learning_brain.reward_model import compute_stats
from core.mcp_fabric.nl2cypher import question_to_cypher

mcp = FastMCP("janus-lex-graph")


def _get_client() -> Neo4jClient:
    return Neo4jClient(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ["NEO4J_PASSWORD"],
    )


@mcp.tool()
async def get_entity_by_label(label: str, name: str) -> list[dict]:
    """Find graph entities of a given label whose name/title/id/code matches `name`.

    Valid labels: Document, Clause, Party, Obligation, Risk, LegalNorm, CourtDecision.
    """
    client = _get_client()
    try:
        return await client.get_entity_by_label(label, name)
    finally:
        await client.close()


@mcp.tool()
async def find_relationships(source: str, target: str) -> list[dict]:
    """Find relationships between two entities identified by name/title/id/code."""
    client = _get_client()
    try:
        return await client.find_relationships(source, target)
    finally:
        await client.close()


@mcp.tool()
async def extract_from_text(text: str, document_id: str | None = None) -> dict:
    """Run the Document Brain + Graph Brain pipeline on raw text and write the result to the graph.

    Returns the generated document_id and counts of extracted nodes/relationships.
    """
    document_id = document_id or f"doc-{uuid.uuid4().hex[:8]}"

    structured = structure_text(text)

    client = _get_client()
    try:
        await client.setup_schema()
        extra_instructions = await retrain_prompts(client)
        nodes, relationships = build_graph(document_id, structured, extra_instructions=extra_instructions)
        await client.write_graph(nodes, relationships)
    finally:
        await client.close()

    return {
        "document_id": document_id,
        "title": structured.title,
        "document_type": structured.document_type,
        "nodes_written": len(nodes),
        "relationships_written": len(relationships),
    }


@mcp.tool()
async def ask_graph(question: str) -> list[dict]:
    """Answer a natural-language question about the legal knowledge graph.

    Translates the question into a read-only Cypher query and executes it.
    Example questions: "Show all risks in contract 14-2026",
    "What obligations does Acme LLC have?"
    """
    cypher, parameters = question_to_cypher(question)

    client = _get_client()
    try:
        return await client.run_read_query(cypher, parameters)
    finally:
        await client.close()


@mcp.tool()
async def submit_feedback(
    document_id: str,
    clause_id: str,
    entity_id: str,
    entity_type: str,
    original_value: str,
    is_correct: bool,
    corrected_value: str | None = None,
) -> dict:
    """Record human feedback on an extracted entity (Obligation, Risk, LegalNorm, ...).

    This feedback is used by the Learning Brain to improve future
    extractions via the prompt optimizer (see retrain_prompts).
    """
    feedback = Feedback(
        document_id=document_id,
        clause_id=clause_id,
        entity_id=entity_id,
        entity_type=entity_type,
        original_value=original_value,
        is_correct=is_correct,
        corrected_value=corrected_value,
    )

    client = _get_client()
    try:
        await client.setup_schema()
        await store_feedback(client, feedback)
    finally:
        await client.close()

    return {"feedback_id": feedback.id, "stored": True}


@mcp.tool()
async def get_learning_stats() -> dict:
    """Return precision/reward statistics per entity type, based on stored feedback."""
    client = _get_client()
    try:
        feedback_items = await list_feedback(client)
    finally:
        await client.close()

    stats = compute_stats(feedback_items)
    return {
        "total_feedback": len(feedback_items),
        "by_entity_type": {
            entity_type: {
                "total": s.total,
                "correct": s.correct,
                "incorrect": s.incorrect,
                "precision": s.precision,
                "reward": s.reward,
            }
            for entity_type, s in stats.items()
        },
    }


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "sse")
    mcp.run(transport=transport)
