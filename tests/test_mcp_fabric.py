import json
from unittest.mock import MagicMock

import pytest

from core.mcp_fabric.nl2cypher import question_to_cypher


def _mock_client(response_payload: dict) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.output_text = json.dumps(response_payload)
    client.responses.create.return_value = response
    return client


def test_question_to_cypher_returns_query_and_parameters():
    payload = {
        "cypher": "MATCH (d:Document {id: $document_id})-[:CONTAINS]->(c:Clause)-[:HAS_RISK]->(r:Risk) "
                  "RETURN c.title AS clause, r.description AS risk, r.severity AS severity",
        "parameters": {"document_id": "contract-14-2026"},
    }
    client = _mock_client(payload)

    cypher, parameters = question_to_cypher("Show all risks in contract 14-2026", client=client)

    assert "RETURN" in cypher
    assert parameters == {"document_id": "contract-14-2026"}


def test_question_to_cypher_rejects_write_queries():
    payload = {"cypher": "MATCH (d:Document) DELETE d", "parameters": {}}
    client = _mock_client(payload)

    with pytest.raises(ValueError):
        question_to_cypher("Delete everything", client=client)
