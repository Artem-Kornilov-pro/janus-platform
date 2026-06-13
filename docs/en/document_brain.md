# Document Brain

**Path**: `core/document_brain/`

The Document Brain turns raw files (PDF, scans, etc.) into a structured,
typed representation of a document that the rest of the system can reason
about.

## Files

- `models.py` — pydantic models:
  - `TextBlock`, `PageExtraction`, `DocumentExtraction` (with a `full_text()` helper that concatenates all pages/blocks)
  - `DocumentSection`
  - `StructuredDocument` — the final output: `document_type`, `title`, `parties`, `dates`, `sections` (list of `DocumentSection`), `summary`
- `extractor.py` — `extract_document(file_path)`:
  - Uses **pdfplumber** to pull native text and tables per page.
  - Falls back to **pytesseract** (Tesseract OCR) + **Pillow** for pages that have no extractable text (e.g. scanned images).
  - Returns a `DocumentExtraction`.
- `structurer.py`:
  - `structure_text(text, client=None)` — sends raw text to the LLM with instructions to produce a `StructuredDocument` as JSON, then validates it with pydantic.
  - `structure_document(extraction, client=None)` — convenience wrapper that calls `structure_text` on `extraction.full_text()`.

## LLM client

**Path**: `core/llm/`

- `client.py`:
  - `get_client()` returns an `openai.OpenAI` instance configured for **Yandex Cloud's** OpenAI-compatible endpoint (`base_url="https://ai.api.cloud.yandex.net/v1"`), authenticated with `YANDEX_CLOUD_API_KEY` and `project=YANDEX_CLOUD_FOLDER`.
  - `_model_uri()` builds a `gpt://{folder}/{model}` URI from `YANDEX_CLOUD_FOLDER` and `YANDEX_CLOUD_MODEL` (default model: `deepseek-v4-flash/latest`).
  - `complete(instructions, input_text, max_output_tokens=4096, temperature=0.3, client=None)` calls `client.responses.create(...)` (the **Responses API**) and returns `response.output_text`.
- `json_utils.py`:
  - `parse_json_response(raw)` strips ```` ```json ```` markdown fences (LLMs love to add them) via regex, then `json.loads`s the result.

Every LLM call in the codebase (Document Brain structuring, Graph Brain
GraphRAG extraction, MCP Fabric's NL→Cypher translation, Learning Brain
prompt optimization) goes through `complete()` + `parse_json_response()`, so
the model/provider can be swapped in one place.

## How it fits together

```
file (PDF/DOCX/TXT/MD/RTF)
   │
   ▼
extractor.extract_document()  ──▶ DocumentExtraction (pages, blocks, tables)
   │
   ▼
structurer.structure_document() ──▶ LLM (core.llm.client.complete)
   │                                    │
   │                                    ▼
   │                              JSON → parse_json_response → StructuredDocument
   ▼
StructuredDocument (document_type, title, parties, dates, sections, summary)
   │
   ▼
consumed by Graph Brain's GraphRAG (build_graph) to produce graph nodes/relationships
```

## Notes

- For the **ingestion pipeline**, raw text comes from `core/ingestion_pipeline/extractors.py` (which supports more formats: PDF/DOCX/TXT/MD/RTF) rather than `document_brain/extractor.py`. The Document Brain's `extractor.py` is focused on PDF + OCR, while `structurer.structure_text()` is the shared LLM-structuring step used by both paths.
- Cyrillic text displayed in a Windows PowerShell console may look garbled (`?`/mojibake) due to the console code page — the underlying data stored in Neo4j is correct UTF-8.
