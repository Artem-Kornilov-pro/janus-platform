from unittest.mock import AsyncMock, MagicMock

import pytest

from core.learning_brain.feedback_model import Feedback, list_feedback, store_feedback


def _make_client(run_result=None):
    client = MagicMock()
    session = AsyncMock()
    session.run = AsyncMock(return_value=run_result)
    client._driver.session.return_value.__aenter__.return_value = session
    client._driver.session.return_value.__aexit__.return_value = None
    client._database = "neo4j"
    return client, session


@pytest.mark.asyncio
async def test_store_feedback_runs_merge_and_links_clause():
    client, session = _make_client()
    feedback = Feedback(
        document_id="doc-1",
        clause_id="clause-1",
        entity_id="entity-1",
        entity_type="Risk",
        original_value="late fee",
        is_correct=False,
        corrected_value="late payment fee",
    )

    await store_feedback(client, feedback)

    session.run.assert_awaited_once()
    args, kwargs = session.run.call_args
    assert "MERGE (f:Feedback" in args[0]
    assert kwargs["id"] == feedback.id
    assert kwargs["clause_id"] == "clause-1"
    assert kwargs["properties"]["entity_type"] == "Risk"


@pytest.mark.asyncio
async def test_list_feedback_without_filter():
    fake_records = [{"f": {"id": "feedback-1", "entity_type": "Risk"}}]

    class FakeResult:
        def __aiter__(self):
            return iter(fake_records).__iter__()

    async def fake_aiter():
        for record in fake_records:
            yield record

    client, session = _make_client()
    fake_result = MagicMock()
    fake_result.__aiter__ = lambda self: fake_aiter()
    session.run = AsyncMock(return_value=fake_result)

    result = await list_feedback(client)

    assert result == [{"id": "feedback-1", "entity_type": "Risk"}]
    args, kwargs = session.run.call_args
    assert "MATCH (f:Feedback)" in args[0]
    assert kwargs == {}


@pytest.mark.asyncio
async def test_list_feedback_with_entity_type_filter():
    async def fake_aiter():
        for record in [{"f": {"id": "feedback-2", "entity_type": "Obligation"}}]:
            yield record

    client, session = _make_client()
    fake_result = MagicMock()
    fake_result.__aiter__ = lambda self: fake_aiter()
    session.run = AsyncMock(return_value=fake_result)

    result = await list_feedback(client, entity_type="Obligation")

    assert result == [{"id": "feedback-2", "entity_type": "Obligation"}]
    args, kwargs = session.run.call_args
    assert "f:Feedback {entity_type: $entity_type}" in args[0]
    assert kwargs == {"entity_type": "Obligation"}
