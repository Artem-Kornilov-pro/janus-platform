"""Natural language to Cypher translation for the Lex knowledge graph."""

from __future__ import annotations

import openai

from core.graph_brain.schema import NODE_LABELS, RELATIONSHIP_TYPES
from core.llm.client import complete
from core.llm.json_utils import parse_json_response

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
- The query MUST be read-only (MATCH/RETURN/WHERE/WITH/ORDER BY/LIMIT/UNWIND only).
- Never use CREATE, MERGE, DELETE, SET, or any write clause.
- Cypher has NO "GROUP BY" clause. To aggregate, list the grouping keys and
  aggregation functions (e.g. count(*), collect(...)) together in the same
  RETURN (or WITH) clause - grouping is implicit from the non-aggregate keys.
  Example: "MATCH (n) RETURN head(labels(n)) AS label, count(*) AS count"
- To combine multiple queries with different RETURN shapes, use UNION ALL,
  but each side must be a complete, independently valid query
  (its own MATCH ... RETURN ...) - never split a single RETURN across a UNION.
- Use parameters for literal values from the question where useful.
- Return JSON only, no markdown fences, no commentary.
"""


def question_to_cypher(question: str, client: openai.OpenAI | None = None) -> tuple[str, dict]:
    """Translate a natural-language question into a (cypher, parameters) pair."""
    raw = complete(SYSTEM_PROMPT, question, max_output_tokens=4096, client=client)
    data = parse_json_response(raw)
    cypher = data["cypher"]

    forbidden = ("CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "CALL")
    if any(keyword in cypher.upper() for keyword in forbidden):
        raise ValueError(f"Generated query is not read-only: {cypher}")

    return cypher, data.get("parameters", {})
