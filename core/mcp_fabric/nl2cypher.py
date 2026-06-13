"""Natural language to Cypher translation for the Lex knowledge graph."""

from __future__ import annotations

import json

import anthropic

from core.graph_brain.schema import NODE_LABELS, RELATIONSHIP_TYPES

MODEL = "claude-sonnet-4-6"

SCHEMA_DESCRIPTION = f"""\
Node labels: {", ".join(NODE_LABELS)}
Relationship types: {", ".join(RELATIONSHIP_TYPES)}

Key node properties:
- Document: id, title, document_type, summary, dates
- Clause: id, title, content, section_type
- Party: name
- Obligation: id, description
- Risk: id, description, severity
- LegalNorm: code, description
- CourtDecision: id

Common relationship patterns:
(Document)-[:CONTAINS]->(Clause)
(Clause)-[:CONTAINS]->(Obligation)
(Clause)-[:HAS_RISK]->(Risk)
(Clause)-[:REFERENCES|VIOLATES]->(LegalNorm)
(Document)-[:INVOLVES]->(Party)
(Party)-[:OBLIGATES]->(Obligation)-[:OBLIGATES]->(Party)
"""

SYSTEM_PROMPT = f"""\
You are a Cypher query generator for a Neo4j legal knowledge graph.

Graph schema:
{SCHEMA_DESCRIPTION}

Given a natural language question, return a JSON object with a single
read-only Cypher query that answers it:
{{"cypher": string, "parameters": object}}

Rules:
- The query MUST be read-only (MATCH/RETURN/WHERE/WITH/ORDER BY/LIMIT only).
- Never use CREATE, MERGE, DELETE, SET, or any write clause.
- Use parameters for literal values from the question where useful.
- Return JSON only, no markdown fences, no commentary.
"""


def question_to_cypher(question: str, client: anthropic.Anthropic | None = None) -> tuple[str, dict]:
    """Translate a natural-language question into a (cypher, parameters) pair."""
    client = client or anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )

    data = json.loads(response.content[0].text)
    cypher = data["cypher"]

    forbidden = ("CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "CALL")
    if any(keyword in cypher.upper() for keyword in forbidden):
        raise ValueError(f"Generated query is not read-only: {cypher}")

    return cypher, data.get("parameters", {})
