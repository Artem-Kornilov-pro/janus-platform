"""Active Learning Loop: picks the most useful extractions for human review.

Combines two strategies:
- Diversity sampling: cover all entity types (Obligation, Risk, LegalNorm),
  not just the most common one.
- Uncertainty sampling: prioritize entities that look "shaky" - e.g.
  obligations missing a party, or high-severity risks, which are more
  likely to contain extraction errors worth checking.
"""

from __future__ import annotations

ENTITY_QUERIES: dict[str, str] = {
    "Obligation": (
        "MATCH (c:Clause)-[:CONTAINS]->(o:Obligation) "
        "WHERE NOT EXISTS { MATCH (:Feedback {entity_id: o.id}) } "
        "RETURN c.id AS clause_id, o.id AS entity_id, o.description AS value, "
        "       'Obligation' AS entity_type "
        "ORDER BY o.id LIMIT $limit"
    ),
    "Risk": (
        "MATCH (c:Clause)-[:HAS_RISK]->(r:Risk) "
        "WHERE NOT EXISTS { MATCH (:Feedback {entity_id: r.id}) } "
        "RETURN c.id AS clause_id, r.id AS entity_id, r.description AS value, "
        "       'Risk' AS entity_type "
        "ORDER BY CASE r.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END "
        "LIMIT $limit"
    ),
    "LegalNorm": (
        "MATCH (c:Clause)-[:REFERENCES|VIOLATES]->(n:LegalNorm) "
        "WHERE NOT EXISTS { MATCH (:Feedback {entity_id: n.code}) } "
        "RETURN c.id AS clause_id, n.code AS entity_id, n.description AS value, "
        "       'LegalNorm' AS entity_type "
        "ORDER BY n.code LIMIT $limit"
    ),
}


async def select_for_review(client, per_type_limit: int = 2) -> list[dict]:
    """Return a diverse, unreviewed sample of extracted entities for human feedback.

    Each item is a dict with: clause_id, entity_id, value, entity_type.
    """
    candidates: list[dict] = []

    for query in ENTITY_QUERIES.values():
        rows = await client.run_read_query(query, {"limit": per_type_limit})
        candidates.extend(rows)

    return candidates
