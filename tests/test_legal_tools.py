"""Tests for legal MCP tools and neo4j_client legal query methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.mcp_fabric import server


# ---------------------------------------------------------------------------
# Helpers (reuse pattern from test_mcp_server_tools)
# ---------------------------------------------------------------------------

def _patch_client():
    client = AsyncMock()
    client.close = AsyncMock()
    return patch.object(server, "_get_client", return_value=client), client


# ---------------------------------------------------------------------------
# MCP tool: get_risk_report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_risk_report_returns_records():
    patcher, client = _patch_client()
    client.get_risk_report = AsyncMock(return_value=[
        {"severity": "high", "risk": "Штраф", "clause_title": "§3", "document_title": "Договор"},
    ])

    with patcher:
        result = await server.get_risk_report()

    assert result[0]["severity"] == "high"
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_risk_report_closes_client_on_error():
    patcher, client = _patch_client()
    client.get_risk_report = AsyncMock(side_effect=RuntimeError("neo4j down"))

    with patcher, pytest.raises(RuntimeError):
        await server.get_risk_report()

    client.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# MCP tool: get_obligations_by_party
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_obligations_by_party_passes_name():
    patcher, client = _patch_client()
    client.get_obligations_by_party = AsyncMock(return_value=[
        {"obligated_party": "Acme", "obligation": "Pay", "beneficiary_party": "Beta"},
    ])

    with patcher:
        result = await server.get_obligations_by_party("Acme")

    client.get_obligations_by_party.assert_awaited_once_with("Acme")
    assert result[0]["obligated_party"] == "Acme"


# ---------------------------------------------------------------------------
# MCP tool: get_deadlines
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_deadlines_default_not_overdue_only():
    patcher, client = _patch_client()
    client.get_deadlines = AsyncMock(return_value=[
        {"date": "2026-07-01", "description": "Срок оплаты", "type": "contractual"},
    ])

    with patcher:
        result = await server.get_deadlines()

    client.get_deadlines.assert_awaited_once_with(overdue_only=False)
    assert result[0]["date"] == "2026-07-01"


@pytest.mark.asyncio
async def test_get_deadlines_overdue_only_flag():
    patcher, client = _patch_client()
    client.get_deadlines = AsyncMock(return_value=[])

    with patcher:
        await server.get_deadlines(overdue_only=True)

    client.get_deadlines.assert_awaited_once_with(overdue_only=True)


# ---------------------------------------------------------------------------
# Neo4jClient query shape tests (via mocked session)
# ---------------------------------------------------------------------------

from tests.test_neo4j_client import _make_client_with_session, _records  # noqa: E402


@pytest.mark.asyncio
async def test_get_risk_report_query_contains_has_risk():
    record = MagicMock()
    record.data.return_value = {"severity": "high", "risk": "штраф", "clause_title": "§1", "document_title": "doc"}
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    result = await client.get_risk_report()

    args, _ = session.run.call_args
    assert "HAS_RISK" in args[0]
    assert result[0]["severity"] == "high"


@pytest.mark.asyncio
async def test_get_obligations_by_party_query_contains_obligates():
    record = MagicMock()
    record.data.return_value = {"obligated_party": "Acme", "obligation": "pay", "beneficiary_party": "Beta"}
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    await client.get_obligations_by_party("Acme")

    args, kwargs = session.run.call_args
    assert "OBLIGATES" in args[0]
    assert kwargs.get("name") == "Acme"


@pytest.mark.asyncio
async def test_get_deadlines_query_contains_has_deadline():
    record = MagicMock()
    record.data.return_value = {"date": "2026-07-01", "description": "Срок", "type": "contractual",
                                 "bound_party": None, "clause_title": "§3", "document_title": "doc"}
    client, session = _make_client_with_session()
    session.run = AsyncMock(return_value=_records([record]))

    result = await client.get_deadlines()

    args, _ = session.run.call_args
    assert "HAS_DEADLINE" in args[0]
    assert result[0]["date"] == "2026-07-01"
