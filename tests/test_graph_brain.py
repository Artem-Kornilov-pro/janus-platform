import json
from unittest.mock import MagicMock

from core.document_brain.models import DocumentSection, StructuredDocument
from core.graph_brain.graph_rag import ClauseAnalysis, analyze_clause, build_graph


def _mock_client(response_payload: dict) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.output_text = json.dumps(response_payload)
    client.responses.create.return_value = response
    return client


def test_analyze_clause_extracts_risks_and_obligations():
    payload = {
        "obligations": [
            {"description": "Pay within 30 days", "obligated_party": "Buyer", "beneficiary_party": "Seller"}
        ],
        "risks": [
            {"description": "Unlimited liability", "severity": "high"}
        ],
        "referenced_norms": [
            {"code": "Art. 506 Civil Code", "description": "Supply contract definition"}
        ],
        "violated_norms": [],
    }
    client = _mock_client(payload)

    section = DocumentSection(title="Payment", content="Buyer pays within 30 days.", section_type="terms")
    analysis = analyze_clause(section, client=client)

    assert isinstance(analysis, ClauseAnalysis)
    assert analysis.obligations[0].obligated_party == "Buyer"
    assert analysis.risks[0].severity == "high"
    assert analysis.referenced_norms[0].code == "Art. 506 Civil Code"


def test_build_graph_creates_document_party_and_clause_nodes():
    clause_payload = {
        "obligations": [],
        "risks": [{"description": "Late delivery risk", "severity": "medium"}],
        "referenced_norms": [],
        "violated_norms": [],
    }
    client = _mock_client(clause_payload)

    document = StructuredDocument(
        document_type="contract",
        title="Supply Agreement",
        parties=["Acme LLC", "Globex LLC"],
        dates=["2026-01-01"],
        sections=[
            DocumentSection(title="Delivery", content="Goods delivered within 30 days.", section_type="terms"),
        ],
        summary="Supply agreement between Acme and Globex.",
    )

    nodes, relationships = build_graph("doc-1", document, client=client)

    node_labels = {(n["label"], n["key_value"]) for n in nodes}
    assert ("Document", "doc-1") in node_labels
    assert ("Party", "Acme LLC") in node_labels
    assert ("Party", "Globex LLC") in node_labels
    assert ("Clause", "doc-1:clause:0") in node_labels
    assert ("Risk", "doc-1:clause:0:risk:0") in node_labels

    rel_types = {(r["from_label"], r["rel_type"], r["to_label"]) for r in relationships}
    assert ("Document", "CONTAINS", "Clause") in rel_types
    assert ("Document", "INVOLVES", "Party") in rel_types
    assert ("Clause", "HAS_RISK", "Risk") in rel_types


def test_build_graph_creates_invoice_nodes_and_relationships():
    clause_payload = {
        "obligations": [],
        "risks": [],
        "referenced_norms": [],
        "violated_norms": [],
        "invoices": [
            {
                "number": "7-2026",
                "amount": 120000.0,
                "currency": "RUB",
                "vat_rate": 20,
                "due_date": "2026-02-01",
                "issuer_party": "ООО Альфа",
                "payer_party": "ООО Бета",
            }
        ],
    }
    client = _mock_client(clause_payload)

    document = StructuredDocument(
        document_type="contract",
        title="Supply Agreement",
        parties=["ООО Альфа", "ООО Бета"],
        dates=["2026-01-01"],
        sections=[
            DocumentSection(title="Payment", content="Pay invoice 7-2026.", section_type="terms"),
        ],
        summary="Supply agreement.",
    )

    nodes, relationships = build_graph("doc-1", document, client=client)

    invoice_nodes = [n for n in nodes if n["label"] == "Invoice"]
    assert len(invoice_nodes) == 1
    assert invoice_nodes[0]["properties"]["number"] == "7-2026"
    assert invoice_nodes[0]["properties"]["amount"] == 120000.0

    rel_types = {(r["from_label"], r["rel_type"], r["to_label"]) for r in relationships}
    assert ("Clause", "CONTAINS", "Invoice") in rel_types
    assert ("Party", "ISSUES", "Invoice") in rel_types
    assert ("Invoice", "BILLED_TO", "Party") in rel_types
