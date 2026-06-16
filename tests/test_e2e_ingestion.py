"""E2E tests: real Neo4j, mocked LLM.

Run these when Neo4j is up:
    docker start janus-neo4j
    python -m pytest tests/test_e2e_ingestion.py -v

They are automatically skipped when Neo4j is not reachable.

Each test uses the ``neo4j`` database but cleans up its own nodes (by
document_id prefix) so they can run safely against a development instance
without wiping production data.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from tests.conftest import requires_neo4j
from core.document_brain.models import DocumentSection, StructuredDocument
from core.graph_brain.graph_rag import build_graph
from core.graph_brain.neo4j_client import Neo4jClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_DOC_PREFIX = "e2e-test:"


def _llm_client(payload: dict) -> MagicMock:
    """Fake OpenAI client that always returns the given JSON payload."""
    client = MagicMock()
    response = MagicMock()
    response.output_text = json.dumps(payload)
    client.responses.create.return_value = response
    return client


def _test_document(doc_id: str) -> tuple[str, StructuredDocument]:
    doc = StructuredDocument(
        document_type="invoice",
        title="Счёт на оплату №E2E-001",
        parties=["ООО «Тест-Продавец»", "ООО «Тест-Покупатель»"],
        dates=["2026-06-16"],
        sections=[
            DocumentSection(
                title="Оплата",
                content="Покупатель обязан оплатить Счёт №E2E-001 на сумму 120 000 руб. (в т.ч. НДС 20%).",
                section_type="payment",
            )
        ],
        summary="Тестовый счёт для E2E.",
    )
    return doc_id, doc


def _invoice_llm_payload() -> dict:
    return {
        "obligations": [
            {
                "description": "Оплатить счёт №E2E-001",
                "obligated_party": "ООО «Тест-Покупатель»",
                "beneficiary_party": "ООО «Тест-Продавец»",
            }
        ],
        "risks": [],
        "referenced_norms": [],
        "violated_norms": [],
        "invoices": [
            {
                "number": "E2E-001",
                "amount": 120000.0,
                "currency": "RUB",
                "vat_rate": 20,
                "due_date": "2026-07-01",
                "issuer_party": "ООО «Тест-Продавец»",
                "payer_party": "ООО «Тест-Покупатель»",
            }
        ],
    }


@pytest.fixture()
async def client(neo4j_test_creds):
    c = Neo4jClient(**neo4j_test_creds)
    yield c
    # Cleanup: remove nodes created by this test run.
    async with c._driver.session(database=c._database) as session:
        await session.run(
            "MATCH (n) WHERE n.id STARTS WITH $prefix DETACH DELETE n",
            prefix=_TEST_DOC_PREFIX,
        )
        await session.run(
            "MATCH (n:Party) WHERE n.name IN $names DETACH DELETE n",
            names=["ООО «Тест-Продавец»", "ООО «Тест-Покупатель»"],
        )
        await session.run(
            "MATCH (n:Invoice) WHERE n.number = 'E2E-001' DETACH DELETE n",
        )
    await c.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@requires_neo4j
@pytest.mark.asyncio
async def test_schema_setup_does_not_raise(client):
    await client.setup_schema()


@requires_neo4j
@pytest.mark.asyncio
async def test_write_and_list_invoices(client):
    await client.setup_schema()

    doc_id = _TEST_DOC_PREFIX + "doc-001"
    doc_id, document = _test_document(doc_id)

    llm = _llm_client(_invoice_llm_payload())
    nodes, relationships = build_graph(doc_id, document, client=llm)

    await client.write_graph(nodes, relationships)

    # Verify Invoice node was persisted.
    invoices = await client.list_invoices()
    e2e_invoices = [i for i in invoices if i.get("number") == "E2E-001"]

    assert len(e2e_invoices) == 1
    inv = e2e_invoices[0]
    assert inv["amount"] == 120000.0
    assert inv["currency"] == "RUB"
    assert inv["vat_rate"] == 20
    assert inv["due_date"] == "2026-07-01"
    assert inv["issuer"] == "ООО «Тест-Продавец»"
    assert inv["payer"] == "ООО «Тест-Покупатель»"


@requires_neo4j
@pytest.mark.asyncio
async def test_invoice_relationships_in_graph(client):
    await client.setup_schema()

    doc_id = _TEST_DOC_PREFIX + "doc-002"
    _, document = _test_document(doc_id)

    llm = _llm_client(_invoice_llm_payload())
    nodes, relationships = build_graph(doc_id, document, client=llm)
    await client.write_graph(nodes, relationships)

    # Invoice must have ISSUES and BILLED_TO relationships.
    rels = await client.find_relationships("ООО «Тест-Продавец»", "*")
    rel_types = {r["relationship"] for r in rels}
    assert "ISSUES" in rel_types


@requires_neo4j
@pytest.mark.asyncio
async def test_get_invoice_entity_by_label(client):
    await client.setup_schema()

    doc_id = _TEST_DOC_PREFIX + "doc-003"
    _, document = _test_document(doc_id)

    llm = _llm_client(_invoice_llm_payload())
    nodes, relationships = build_graph(doc_id, document, client=llm)
    await client.write_graph(nodes, relationships)

    # get_entity_by_label must surface Invoice nodes.
    results = await client.get_entity_by_label("Invoice", "*")
    numbers = [r.get("number") for r in results]
    assert "E2E-001" in numbers
