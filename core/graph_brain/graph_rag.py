"""GraphRAG extraction for the Lex domain.

Takes a StructuredDocument produced by the Document Brain and extracts a
typed graph of legal entities (parties, obligations, risks, legal norms,
clauses) ready to be written to Neo4j via Neo4jClient.write_graph.

Per-clause extraction (obligations, risks, referenced/violated norms) is
done with an LLM, since this information is not present in the
StructuredDocument produced by the basic Document Brain pipeline.
"""

from __future__ import annotations

import json

import anthropic
from pydantic import BaseModel

from core.document_brain.models import DocumentSection, StructuredDocument

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a legal analysis engine. Given a clause from a contract, extract:

- obligations: list of {"description": string, "obligated_party": string, "beneficiary_party": string}
- risks: list of {"description": string, "severity": "low"|"medium"|"high"}
- referenced_norms: list of {"code": string, "description": string}   // laws/articles mentioned
- violated_norms: list of {"code": string, "description": string, "reason": string}

Return JSON only, matching this schema exactly, no markdown fences:
{"obligations": [...], "risks": [...], "referenced_norms": [...], "violated_norms": [...]}

If a category is empty, return an empty list for it.
"""


class Obligation(BaseModel):
    description: str
    obligated_party: str
    beneficiary_party: str


class Risk(BaseModel):
    description: str
    severity: str


class LegalNorm(BaseModel):
    code: str
    description: str


class ViolatedNorm(LegalNorm):
    reason: str


class ClauseAnalysis(BaseModel):
    obligations: list[Obligation] = []
    risks: list[Risk] = []
    referenced_norms: list[LegalNorm] = []
    violated_norms: list[ViolatedNorm] = []


def analyze_clause(section: DocumentSection, client: anthropic.Anthropic | None = None) -> ClauseAnalysis:
    """Use an LLM to extract obligations, risks and legal norm references from a clause."""
    client = client or anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{section.title}\n\n{section.content}"}],
    )

    data = json.loads(response.content[0].text)
    return ClauseAnalysis(**data)


def _clause_id(document_id: str, index: int) -> str:
    return f"{document_id}:clause:{index}"


def _obligation_id(clause_id: str, index: int) -> str:
    return f"{clause_id}:obligation:{index}"


def _risk_id(clause_id: str, index: int) -> str:
    return f"{clause_id}:risk:{index}"


def build_graph(
    document_id: str,
    document: StructuredDocument,
    client: anthropic.Anthropic | None = None,
) -> tuple[list[dict], list[dict]]:
    """Build the node/relationship batch for a structured document.

    Returns a (nodes, relationships) tuple suitable for Neo4jClient.write_graph.
    """
    client = client or anthropic.Anthropic()

    nodes: list[dict] = [
        {
            "label": "Document",
            "key_property": "id",
            "key_value": document_id,
            "properties": {
                "title": document.title,
                "document_type": document.document_type,
                "summary": document.summary,
                "dates": document.dates,
            },
        }
    ]
    relationships: list[dict] = []

    for party_name in document.parties:
        nodes.append({
            "label": "Party",
            "key_property": "name",
            "key_value": party_name,
            "properties": {"name": party_name},
        })
        relationships.append({
            "from_label": "Document", "from_key": "id", "from_value": document_id,
            "to_label": "Party", "to_key": "name", "to_value": party_name,
            "rel_type": "INVOLVES",
        })

    for i, section in enumerate(document.sections):
        clause_id = _clause_id(document_id, i)
        nodes.append({
            "label": "Clause",
            "key_property": "id",
            "key_value": clause_id,
            "properties": {
                "title": section.title,
                "content": section.content,
                "section_type": section.section_type,
            },
        })
        relationships.append({
            "from_label": "Document", "from_key": "id", "from_value": document_id,
            "to_label": "Clause", "to_key": "id", "to_value": clause_id,
            "rel_type": "CONTAINS",
        })

        analysis = analyze_clause(section, client=client)

        for j, obligation in enumerate(analysis.obligations):
            obligation_id = _obligation_id(clause_id, j)
            nodes.append({
                "label": "Obligation",
                "key_property": "id",
                "key_value": obligation_id,
                "properties": {"description": obligation.description},
            })
            relationships.append({
                "from_label": "Clause", "from_key": "id", "from_value": clause_id,
                "to_label": "Obligation", "to_key": "id", "to_value": obligation_id,
                "rel_type": "CONTAINS",
            })

            for party_name, direction in (
                (obligation.obligated_party, "OBLIGATES"),
                (obligation.beneficiary_party, "OBLIGATES"),
            ):
                if not party_name:
                    continue
                nodes.append({
                    "label": "Party",
                    "key_property": "name",
                    "key_value": party_name,
                    "properties": {"name": party_name},
                })

            if obligation.obligated_party:
                relationships.append({
                    "from_label": "Party", "from_key": "name", "from_value": obligation.obligated_party,
                    "to_label": "Obligation", "to_key": "id", "to_value": obligation_id,
                    "rel_type": "OBLIGATES",
                    "properties": {"role": "obligated"},
                })
            if obligation.beneficiary_party:
                relationships.append({
                    "from_label": "Obligation", "from_key": "id", "from_value": obligation_id,
                    "to_label": "Party", "to_key": "name", "to_value": obligation.beneficiary_party,
                    "rel_type": "OBLIGATES",
                    "properties": {"role": "beneficiary"},
                })

        for j, risk in enumerate(analysis.risks):
            risk_id = _risk_id(clause_id, j)
            nodes.append({
                "label": "Risk",
                "key_property": "id",
                "key_value": risk_id,
                "properties": {"description": risk.description, "severity": risk.severity},
            })
            relationships.append({
                "from_label": "Clause", "from_key": "id", "from_value": clause_id,
                "to_label": "Risk", "to_key": "id", "to_value": risk_id,
                "rel_type": "HAS_RISK",
            })

        for norm in analysis.referenced_norms:
            nodes.append({
                "label": "LegalNorm",
                "key_property": "code",
                "key_value": norm.code,
                "properties": {"description": norm.description},
            })
            relationships.append({
                "from_label": "Clause", "from_key": "id", "from_value": clause_id,
                "to_label": "LegalNorm", "to_key": "code", "to_value": norm.code,
                "rel_type": "REFERENCES",
            })

        for norm in analysis.violated_norms:
            nodes.append({
                "label": "LegalNorm",
                "key_property": "code",
                "key_value": norm.code,
                "properties": {"description": norm.description},
            })
            relationships.append({
                "from_label": "Clause", "from_key": "id", "from_value": clause_id,
                "to_label": "LegalNorm", "to_key": "code", "to_value": norm.code,
                "rel_type": "VIOLATES",
                "properties": {"reason": norm.reason},
            })

    return nodes, relationships
