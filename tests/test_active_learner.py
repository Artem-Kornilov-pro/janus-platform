from unittest.mock import AsyncMock

import pytest

from core.learning_brain.active_learner import ENTITY_QUERIES, select_for_review


@pytest.mark.asyncio
async def test_select_for_review_queries_each_entity_type_and_merges_results():
    rows_by_query = {
        "Obligation": [{"clause_id": "c1", "entity_id": "o1", "value": "pay rent", "entity_type": "Obligation"}],
        "Risk": [{"clause_id": "c2", "entity_id": "r1", "value": "late fee", "entity_type": "Risk"}],
        "LegalNorm": [],
    }
    queries_by_text = {query: rows_by_query[label] for label, query in ENTITY_QUERIES.items()}

    client = AsyncMock()

    async def run_read_query(query, params):
        assert params == {"limit": 2}
        return queries_by_text[query]

    client.run_read_query = AsyncMock(side_effect=run_read_query)

    results = await select_for_review(client, per_type_limit=2)

    assert client.run_read_query.await_count == len(ENTITY_QUERIES)
    assert {r["entity_id"] for r in results} == {"o1", "r1"}


@pytest.mark.asyncio
async def test_select_for_review_respects_per_type_limit():
    client = AsyncMock()
    client.run_read_query = AsyncMock(return_value=[])

    await select_for_review(client, per_type_limit=5)

    for call in client.run_read_query.await_args_list:
        _, kwargs_or_args = call
        params = call.args[1]
        assert params["limit"] == 5
