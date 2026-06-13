from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.mcp_fabric import server


def _patch_client(return_value=None, side_effect=None):
    client = AsyncMock()
    client.close = AsyncMock()
    return patch.object(server, "_get_client", return_value=client), client


@pytest.mark.asyncio
async def test_get_entity_by_label_closes_client():
    patcher, client = _patch_client()
    client.get_entity_by_label = AsyncMock(return_value=[{"id": "party-1"}])

    with patcher:
        result = await server.get_entity_by_label("Party", "Acme")

    assert result == [{"id": "party-1"}]
    client.get_entity_by_label.assert_awaited_once_with("Party", "Acme")
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_relationships_closes_client():
    patcher, client = _patch_client()
    client.find_relationships = AsyncMock(return_value=[{"relationship": "HAS_RISK"}])

    with patcher:
        result = await server.find_relationships("Acme", "late fee")

    assert result == [{"relationship": "HAS_RISK"}]
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_from_text_builds_and_writes_graph():
    patcher, client = _patch_client()
    client.setup_schema = AsyncMock()
    client.write_graph = AsyncMock()

    structured = MagicMock(title="Contract", document_type="agreement")
    nodes = [{"label": "Document"}]
    relationships = []

    with patcher, \
        patch.object(server, "structure_text", return_value=structured) as mock_structure, \
        patch.object(server, "retrain_prompts", new=AsyncMock(return_value="")) as mock_retrain, \
        patch.object(server, "build_graph", return_value=(nodes, relationships)) as mock_build:

        result = await server.extract_from_text("some text", document_id="doc-42")

    mock_structure.assert_called_once_with("some text")
    mock_retrain.assert_awaited_once_with(client)
    mock_build.assert_called_once_with("doc-42", structured, extra_instructions="")
    client.setup_schema.assert_awaited_once()
    client.write_graph.assert_awaited_once_with(nodes, relationships)
    client.close.assert_awaited_once()
    assert result == {
        "document_id": "doc-42",
        "title": "Contract",
        "document_type": "agreement",
        "nodes_written": 1,
        "relationships_written": 0,
    }


@pytest.mark.asyncio
async def test_extract_from_text_generates_document_id_when_missing():
    patcher, client = _patch_client()
    client.setup_schema = AsyncMock()
    client.write_graph = AsyncMock()

    structured = MagicMock(title="Contract", document_type="agreement")

    with patcher, \
        patch.object(server, "structure_text", return_value=structured), \
        patch.object(server, "retrain_prompts", new=AsyncMock(return_value="")), \
        patch.object(server, "build_graph", return_value=([], [])):

        result = await server.extract_from_text("some text")

    assert result["document_id"].startswith("doc-")


@pytest.mark.asyncio
async def test_ask_graph_runs_generated_cypher():
    patcher, client = _patch_client()
    client.run_read_query = AsyncMock(return_value=[{"count": 1}])

    with patcher, patch.object(server, "question_to_cypher", return_value=("MATCH (n) RETURN n", {"x": 1})) as mock_q2c:
        result = await server.ask_graph("how many documents?")

    mock_q2c.assert_called_once_with("how many documents?")
    client.run_read_query.assert_awaited_once_with("MATCH (n) RETURN n", {"x": 1})
    assert result == [{"count": 1}]
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_feedback_stores_and_returns_id():
    patcher, client = _patch_client()
    client.setup_schema = AsyncMock()

    with patcher, patch.object(server, "store_feedback", new=AsyncMock()) as mock_store:
        result = await server.submit_feedback(
            document_id="doc-1",
            clause_id="clause-1",
            entity_id="entity-1",
            entity_type="Risk",
            original_value="late fee",
            is_correct=True,
        )

    client.setup_schema.assert_awaited_once()
    mock_store.assert_awaited_once()
    assert result["stored"] is True
    assert result["feedback_id"].startswith("feedback-")
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_learning_stats_aggregates_by_entity_type():
    patcher, client = _patch_client()
    feedback_items = [{"entity_type": "Risk"}]

    fake_stat = MagicMock(total=1, correct=1, incorrect=0, precision=1.0, reward=1.0)

    with patcher, \
        patch.object(server, "list_feedback", new=AsyncMock(return_value=feedback_items)), \
        patch.object(server, "compute_stats", return_value={"Risk": fake_stat}):

        result = await server.get_learning_stats()

    assert result["total_feedback"] == 1
    assert result["by_entity_type"]["Risk"] == {
        "total": 1,
        "correct": 1,
        "incorrect": 0,
        "precision": 1.0,
        "reward": 1.0,
    }
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_folder_returns_job_dump():
    patcher, client = _patch_client()
    fake_job = MagicMock()
    fake_job.model_dump.return_value = {"status": "completed"}

    with patcher, patch.object(server, "run_ingest_folder", new=AsyncMock(return_value=fake_job)) as mock_run:
        result = await server.ingest_folder("/data", recursive=False)

    mock_run.assert_awaited_once_with(client, "/data", recursive=False)
    assert result == {"status": "completed"}
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_ingestion_status_returns_job_dict():
    patcher, client = _patch_client()

    with patcher, patch.object(server, "get_job", new=AsyncMock(return_value={"id": "job-1"})) as mock_get_job:
        result = await server.get_ingestion_status("job-1")

    mock_get_job.assert_awaited_once_with(client, "job-1")
    assert result == {"id": "job-1"}
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_documents_closes_client():
    patcher, client = _patch_client()
    client.list_documents = AsyncMock(return_value=[{"id": "doc-1"}])

    with patcher:
        result = await server.list_documents()

    assert result == [{"id": "doc-1"}]
    client.close.assert_awaited_once()


def test_get_client_reads_env_vars(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://example:7687")
    monkeypatch.setenv("NEO4J_USER", "custom_user")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")

    with patch.object(server, "Neo4jClient") as mock_cls:
        server._get_client()

    mock_cls.assert_called_once_with(uri="bolt://example:7687", user="custom_user", password="secret")
