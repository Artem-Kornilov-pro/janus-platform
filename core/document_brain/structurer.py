"""Turn raw extracted document text into a StructuredDocument via an LLM.

This is the "semantic" layer of the Document Brain: given the raw text and
table data produced by the extractor, ask an LLM to identify the document
type, parties, dates and break the content into typed sections.
"""

import json

import anthropic

from core.document_brain.models import DocumentExtraction, StructuredDocument

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a document analysis engine for a legal-domain assistant.
Given the raw extracted text of a document, return a JSON object matching
this schema exactly (no extra commentary, no markdown fences):

{
  "document_type": string,   // e.g. "contract", "court_ruling", "claim", "invoice", "other"
  "title": string,
  "parties": string[],       // names of organizations/persons involved
  "dates": string[],         // ISO 8601 dates found in the document
  "sections": [
    {"title": string, "content": string, "section_type": string}
  ],
  "summary": string           // 2-4 sentence summary
}
"""


def structure_text(text: str, client: anthropic.Anthropic | None = None) -> StructuredDocument:
    """Structure a raw text blob into a StructuredDocument via an LLM."""
    client = client or anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )

    data = json.loads(response.content[0].text)
    return StructuredDocument(**data)


def structure_document(extraction: DocumentExtraction, client: anthropic.Anthropic | None = None) -> StructuredDocument:
    return structure_text(extraction.full_text(), client=client)
