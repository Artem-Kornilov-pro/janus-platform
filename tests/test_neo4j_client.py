from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.graph_brain.neo4j_client import Neo4jClient


def _make_client_with_session(run_result=None):
    with patch("core.graph_brain.neo4j_client.AsyncGraphDatabase") as mock_db:
        driver = MagicMock()
        mock_db.driver.return_value = driver
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="pw")

    session = AsyncMock()
    session.run = AsyncMock(return_value=run_result)
    session.execute_write = AsyncMock()
    client._driver.session.return_value.__aenter__.return_value = session
    client._driver.session.return_value.__aexit__.return_value = None
    return client, session


def _records(items):
    async def fake_aiter():
        for item in items:
            yield item

    fake_result = MagicMock()
    fake_result.__aiter__ = lambda self: fake_aiter()
    return fake_result


@pytest.mark.asyncio
async def test_close_closes_driver():
    client, _ = _make_client_with_session()
    client._driver.close = AsyncMock()

    await client.close()

    client._driver.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_schema_runs_all_statements():
    client, session = _make_client_with_session()

    await client.setup_schema()

    assert session.run.await_count > 1


@pytest.mark.asyncio
async def test_create_document_node():
    client, session = _make_client_with_session()

    await client.create_document_node("doc-1", {"title": "Contract"})

    session.execute_write.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_entity_uses_label_in_query():
    client, session = _make_client_with_session()

    await client.create_entity("Risk", "id", "risk-1", {"severity": "high"})

    session.execute_write.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_graph_calls_execute_write_with_nodes_and_relationships():
    client, session = _make_client_with_session()
    nodes = [{"label": "Document", "key_property": "id", "key_value": "doc-1", "properties": {}}]
    relationships = []

    await client.write_graph(nodes, relationships)

    session.execute_write.assert_awaited_once()
    args = session.execute_write.call_args.args
    assert args[1] == nodes
    assert args[2] == relationships


@pytest.mark.asyncio
async def test_write_graph_tx_runs_node_and_relationship_queries():
    tx = AsyncMock()
    nodes = [{"label": "Document", "key_property": "id", "key_value": "doc-1", "properties": {"title": "x"}}]
    relationships = [
        {
            "from_label": "Document",
            "from_key": "id",
            "from_value": "doc-1",
            "to_label": "Clause",
            "to_key": "id",
            "to_value": "clause-1",
            "rel_type": "CONTAINS",
        }
    ]

    await Neo4jClient._write_graph_tx(tx, nodes, relationships)

    assert tx.run.await_count == 2
    node_query = tx.run.await_args_list[0].args[0]
    rel_query = tx.run.await_args_list[1].args[0]
    assert "MERGE (n:Document" in node_query
    assert "MERGE (a)-[r:CONTAINS]->(b)" in rel_query


@pytest.mark.asyncio
async def test_find_risks_for_document_returns_records():
    items = [{"clause_id": "c1", "clause_title": "Title", "risk": "late fee", "severity": "high"}]
    record = MagicMock()
    record.data.return_value = items[0]
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    result = await client.find_risks_for_document("doc-1")

    assert result == items


@pytest.mark.asyncio
async def test_find_document_by_hash_returns_none_when_missing():
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value=None)
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=fake_result)

    result = await client.find_document_by_hash("hash123")

    assert result is None


@pytest.mark.asyncio
async def test_find_document_by_hash_returns_dict_when_found():
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value={"d": {"id": "doc-1", "content_hash": "hash123"}})
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=fake_result)

    result = await client.find_document_by_hash("hash123")

    assert result == {"id": "doc-1", "content_hash": "hash123"}


@pytest.mark.asyncio
async def test_list_documents_returns_records():
    record = MagicMock()
    record.data.return_value = {"id": "doc-1", "title": "Contract"}
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    result = await client.list_documents()

    assert result == [{"id": "doc-1", "title": "Contract"}]


@pytest.mark.asyncio
async def test_get_entity_by_label_returns_node_dicts():
    record = {"n": {"id": "party-1", "name": "Acme"}}
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    result = await client.get_entity_by_label("Party", "Acme")

    assert result == [{"id": "party-1", "name": "Acme"}]
    args, kwargs = session.run.call_args
    assert "MATCH (n:Party)" in args[0]
    assert kwargs == {"name": "Acme"}


@pytest.mark.asyncio
async def test_find_relationships_returns_records():
    record = MagicMock()
    record.data.return_value = {"relationship": "HAS_RISK"}
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    result = await client.find_relationships("Acme", "late fee")

    assert result == [{"relationship": "HAS_RISK"}]
    args, kwargs = session.run.call_args
    assert kwargs == {"source": "Acme", "target": "late fee"}


@pytest.mark.asyncio
async def test_run_read_query_passes_parameters():
    record = MagicMock()
    record.data.return_value = {"count": 1}
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    result = await client.run_read_query("MATCH (n) RETURN count(n) AS count", {"foo": "bar"})

    assert result == [{"count": 1}]
    args, _ = session.run.call_args
    assert args[0] == "MATCH (n) RETURN count(n) AS count"
    assert args[1] == {"foo": "bar"}


@pytest.mark.asyncio
async def test_run_read_query_defaults_parameters_to_empty_dict():
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([]))

    await client.run_read_query("MATCH (n) RETURN n")

    args, _ = session.run.call_args
    assert args[1] == {}
