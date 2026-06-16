"""GraphRAG extraction for the Lex domain.

Takes a StructuredDocument produced by the Document Brain and extracts a
typed graph of legal entities (parties, obligations, risks, legal norms,
clauses) ready to be written to Neo4j via Neo4jClient.write_graph.

Per-clause extraction (obligations, risks, referenced/violated norms) is
done with an LLM, since this information is not present in the
StructuredDocument produced by the basic Document Brain pipeline.
"""

from __future__ import annotations

import openai
from pydantic import BaseModel

from core.document_brain.models import DocumentSection, StructuredDocument
from core.llm.client import complete
from core.llm.json_utils import parse_json_response

SYSTEM_PROMPT = """\
You are a legal analysis engine. Given a clause from a contract, extract:

- obligations: list of {"description": string, "obligated_party": string, "beneficiary_party": string}
- risks: list of {"description": string, "severity": "low"|"medium"|"high"}
- referenced_norms: list of {"code": string, "description": string}   // laws/articles mentioned
- violated_norms: list of {"code": string, "description": string, "reason": string}
- invoices: list of {"number": string, "amount": number, "currency": string, "vat_rate": number,
  "due_date": string, "issuer_party": string, "payer_party": string}
  // счета на оплату (invoices/bills) mentioned in the clause. amount is the total
  // (gross, including VAT if applicable) numeric amount. vat_rate is a percentage
  // (0, 10 or 20), or -1 if not specified. due_date is an ISO date string or "" if unknown.
- deadlines: list of {"description": string, "date": string, "type": "contractual"|"statutory"|"procedural",
  "bound_party": string}
  // explicit срок (deadline) mentioned in the clause. date is ISO string or "" if not specified.
  // type: "contractual" = set by agreement, "statutory" = set by law, "procedural" = court/process срок.
- claims: list of {"number": string, "description": string, "date_filed": string,
  "deadline_response": string, "claimant_party": string, "respondent_party": string}
  // претензии (legal claims/demands) referenced in the clause. dates are ISO strings or "".

Return JSON only, matching this schema exactly, no markdown fences:
{"obligations": [...], "risks": [...], "referenced_norms": [...], "violated_norms": [...], "invoices": [...], "deadlines": [...], "claims": [...]}

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


class Invoice(BaseModel):
    number: str
    amount: float
    currency: str = ""
    vat_rate: float = -1
    due_date: str = ""
    issuer_party: str = ""
    payer_party: str = ""


class Deadline(BaseModel):
    description: str
    date: str = ""
    type: str = "contractual"
    bound_party: str = ""


class Claim(BaseModel):
    number: str = ""
    description: str
    date_filed: str = ""
    deadline_response: str = ""
    claimant_party: str = ""
    respondent_party: str = ""


class ClauseAnalysis(BaseModel):
    obligations: list[Obligation] = []
    risks: list[Risk] = []
    referenced_norms: list[LegalNorm] = []
    violated_norms: list[ViolatedNorm] = []
    invoices: list[Invoice] = []
    deadlines: list[Deadline] = []
    claims: list[Claim] = []


def analyze_clause(
    section: DocumentSection,
    client: openai.OpenAI | None = None,
    extra_instructions: str = "",
) -> ClauseAnalysis:
    """Use an LLM to extract obligations, risks and legal norm references from a clause.

    `extra_instructions`, if provided, is appended to the system prompt -
    typically a "lessons learned" section produced by the Learning Brain's
    prompt optimizer from past human feedback.
    """
    system_prompt = SYSTEM_PROMPT + extra_instructions
    raw = complete(system_prompt, f"{section.title}\n\n{section.content}", max_output_tokens=2048, client=client)
    data = parse_json_response(raw)
    return ClauseAnalysis(**data)


def _clause_id(document_id: str, index: int) -> str:
    return f"{document_id}:clause:{index}"


def _obligation_id(clause_id: str, index: int) -> str:
    return f"{clause_id}:obligation:{index}"


def _risk_id(clause_id: str, index: int) -> str:
    return f"{clause_id}:risk:{index}"


def _invoice_id(clause_id: str, index: int) -> str:
    return f"{clause_id}:invoice:{index}"


def _deadline_id(clause_id: str, index: int) -> str:
    return f"{clause_id}:deadline:{index}"


def _claim_id(document_id: str, index: int) -> str:
    return f"{document_id}:claim:{index}"


def build_graph(
    document_id: str,
    document: StructuredDocument,
    client: openai.OpenAI | None = None,
    extra_instructions: str = "",
) -> tuple[list[dict], list[dict]]:
    """Build the node/relationship batch for a structured document.

    Returns a (nodes, relationships) tuple suitable for Neo4jClient.write_graph.
    """

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

        analysis = analyze_clause(section, client=client, extra_instructions=extra_instructions)

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

        for j, invoice in enumerate(analysis.invoices):
            invoice_id = _invoice_id(clause_id, j)
            nodes.append({
                "label": "Invoice",
                "key_property": "id",
                "key_value": invoice_id,
                "properties": {
                    "number": invoice.number,
                    "amount": invoice.amount,
                    "currency": invoice.currency,
                    "vat_rate": invoice.vat_rate,
                    "due_date": invoice.due_date,
                },
            })
            relationships.append({
                "from_label": "Clause", "from_key": "id", "from_value": clause_id,
                "to_label": "Invoice", "to_key": "id", "to_value": invoice_id,
                "rel_type": "CONTAINS",
            })

            for party_name in (invoice.issuer_party, invoice.payer_party):
                if not party_name:
                    continue
                nodes.append({
                    "label": "Party",
                    "key_property": "name",
                    "key_value": party_name,
                    "properties": {"name": party_name},
                })

            if invoice.issuer_party:
                relationships.append({
                    "from_label": "Party", "from_key": "name", "from_value": invoice.issuer_party,
                    "to_label": "Invoice", "to_key": "id", "to_value": invoice_id,
                    "rel_type": "ISSUES",
                })
            if invoice.payer_party:
                relationships.append({
                    "from_label": "Invoice", "from_key": "id", "from_value": invoice_id,
                    "to_label": "Party", "to_key": "name", "to_value": invoice.payer_party,
                    "rel_type": "BILLED_TO",
                })

        for j, deadline in enumerate(analysis.deadlines):
            deadline_id = _deadline_id(clause_id, j)
            nodes.append({
                "label": "Deadline",
                "key_property": "id",
                "key_value": deadline_id,
                "properties": {
                    "description": deadline.description,
                    "date": deadline.date,
                    "type": deadline.type,
                },
            })
            relationships.append({
                "from_label": "Clause", "from_key": "id", "from_value": clause_id,
                "to_label": "Deadline", "to_key": "id", "to_value": deadline_id,
                "rel_type": "HAS_DEADLINE",
            })
            if deadline.bound_party:
                nodes.append({
                    "label": "Party",
                    "key_property": "name",
                    "key_value": deadline.bound_party,
                    "properties": {"name": deadline.bound_party},
                })
                relationships.append({
                    "from_label": "Deadline", "from_key": "id", "from_value": deadline_id,
                    "to_label": "Party", "to_key": "name", "to_value": deadline.bound_party,
                    "rel_type": "BINDS",
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

    # Claims may span the whole document; run a dedicated extraction pass for
    # documents whose type or title indicates a pretension/claim document.

    if "claim" in document.document_type.lower() or "претензи" in document.title.lower():
        for i, section in enumerate(document.sections):
            clause_id = _clause_id(document_id, i)
            analysis = analyze_clause(section, client=client, extra_instructions=extra_instructions)
            for j, claim in enumerate(analysis.claims):
                claim_id = _claim_id(document_id, j)
                nodes.append({
                    "label": "Claim",
                    "key_property": "id",
                    "key_value": claim_id,
                    "properties": {
                        "number": claim.number,
                        "description": claim.description,
                        "date_filed": claim.date_filed,
                        "deadline_response": claim.deadline_response,
                    },
                })
                relationships.append({
                    "from_label": "Document", "from_key": "id", "from_value": document_id,
                    "to_label": "Claim", "to_key": "id", "to_value": claim_id,
                    "rel_type": "HAS_CLAIM",
                })
                for party_name, rel_type in (
                    (claim.claimant_party, "FILED_BY"),
                    (claim.respondent_party, "FILED_AGAINST"),
                ):
                    if not party_name:
                        continue
                    nodes.append({
                        "label": "Party",
                        "key_property": "name",
                        "key_value": party_name,
                        "properties": {"name": party_name},
                    })
                    relationships.append({
                        "from_label": "Claim", "from_key": "id", "from_value": claim_id,
                        "to_label": "Party", "to_key": "name", "to_value": party_name,
                        "rel_type": rel_type,
                    })

    return nodes, relationships
