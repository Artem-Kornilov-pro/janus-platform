# Janus Platform — Architecture Overview

Janus Platform is a "Core + Domains" system: a shared, domain-agnostic core
(document understanding, a knowledge graph, a learning loop, an MCP data
fabric, and an ingestion pipeline) plus pluggable domain modules. The first
domain is **Lex** (legal contracts, clauses, obligations, risks, legal norms,
court decisions, invoices, deadlines, claims), with a lightweight **Finance**
domain (`domains/finance/`) layered on top for VAT/УСН tax calculations and
invoice reporting.

## High-level diagram

```
                        ┌─────────────────────────┐
                        │   PyQt6 Desktop Frontend │
                        │ (Chat / Documents / Graph│
                        │  Entities / Learning /   │
                        │  Finance / Legal)        │
                        └────────────┬─────────────┘
                                      │ MCP over SSE
                                      ▼
                        ┌─────────────────────────┐
                        │      MCP Fabric          │
                        │ (FastMCP + SSE server)   │
                        └──┬───────┬──────────┬────┘
                            │       │          │
              ┌─────────────┘       │          └──────────────┐
              ▼                     ▼                          ▼
   ┌─────────────────────┐ ┌──────────────────┐   ┌─────────────────────┐
   │   Document Brain     │ │   Graph Brain     │   │   Learning Brain     │
   │ (extraction + LLM    │ │ (Neo4j ontology,  │   │ (feedback, reward,   │
   │  structuring)        │ │  GraphRAG writer, │   │  prompt optimizer,   │
   │                       │ │  NL→Cypher reads) │   │  active learning)    │
   └───────────┬───────────┘ └─────────┬─────────┘   └──────────┬──────────┘
               │                        │                         │
               │                        ▼                         │
               │              ┌──────────────────┐                │
               └─────────────▶│  Ingestion Pipeline│◀──────────────┘
                               │ (extract → chunk → │
                               │  graph → track)    │
                               └─────────┬──────────┘
                                          ▼
                                  ┌───────────────┐
                                  │     Neo4j      │
                                  │  (Docker)      │
                                  └───────────────┘

   All LLM calls go through `core/llm/client.py`, backed by Yandex Cloud's
   OpenAI-compatible Responses API (model: deepseek-v4-flash/latest).
```

## Components

| Component | Path | Purpose | Doc |
|---|---|---|---|
| Document Brain | `core/document_brain/` | PDF/OCR extraction + LLM structuring into a typed document model | [document_brain.md](document_brain.md) |
| Graph Brain | `core/graph_brain/` | Neo4j ontology, GraphRAG extraction, async graph client | [graph_brain.md](graph_brain.md) |
| MCP Fabric | `core/mcp_fabric/` | FastMCP/SSE server exposing all tools to clients | [mcp_fabric.md](mcp_fabric.md) |
| Learning Brain | `core/learning_brain/` | Human feedback storage, reward model, prompt optimization, active learning | [learning_brain.md](learning_brain.md) |
| Ingestion Pipeline | `core/ingestion_pipeline/` | Multi-format extraction, chunking, batch graph writing, job tracking, folder watching | [ingestion_pipeline.md](ingestion_pipeline.md) |
| Frontend | `frontend/` | PyQt6 desktop UI talking to MCP Fabric over SSE | [frontend.md](frontend.md) |
| LLM Client | `core/llm/` | Shared LLM abstraction (Yandex Cloud, OpenAI-compatible) | see [document_brain.md](document_brain.md#llm-client) |
| Lex domain | `domains/lex/` (ontology lives in `core/graph_brain/schema.py`) | Legal entities (`Party`, `Obligation`, `Risk`, `LegalNorm`, `CourtDecision`, `Invoice`, `Deadline`, `Claim`) and the risk/obligations/deadlines MCP tools behind the **Юрист** tab | [graph_brain.md](graph_brain.md), [mcp_fabric.md](mcp_fabric.md) |
| Finance domain | `domains/finance/` | Pure VAT/УСН tax-calculation helpers, used both by MCP tools (`calculate_vat`, `calculate_usn_tax`) and directly by the **Финансы** tab | [mcp_fabric.md](mcp_fabric.md) |

## Technology stack

- **Language**: Python 3.12+
- **Knowledge graph**: Neo4j 5.26 (Docker container `janus-neo4j`)
- **Document parsing**: `pdfplumber` (native PDF text/tables), `pytesseract` + `pillow` (OCR fallback), `python-docx`, `striprtf`
- **Data validation**: `pydantic` v2 (all structured models)
- **LLM provider**: Yandex Cloud, OpenAI-compatible Responses API via the `openai` SDK, model `deepseek-v4-flash/latest`
- **Protocol**: Model Context Protocol (MCP) via the `mcp` Python SDK, served over Server-Sent Events (SSE) using `FastMCP`
- **Folder watching**: `watchdog`
- **Frontend**: PyQt6 (desktop), with a background asyncio loop bridging MCP's async client to Qt's event loop
- **Testing**: `pytest` + `pytest-asyncio`
- **Packaging/config**: `pyproject.toml`, `requirements.txt`, `docker-compose.yml`, `.env` / `.env.example`

## Typical request flow (chat question)

1. User types a question in the PyQt6 **Chat** tab.
2. `frontend/async_runner.py` schedules `frontend/mcp_client.ask_graph(question)` on a background asyncio loop (so the Qt UI thread never blocks).
3. `mcp_client` opens an SSE connection to the MCP Fabric server (`http://localhost:8000/sse`) and calls the `ask_graph` tool.
4. The server (`core/mcp_fabric/server.py`) calls `core/mcp_fabric/nl2cypher.py`, which asks the LLM to translate the natural-language question into a **read-only** Cypher query (writes are rejected).
5. The query runs against Neo4j via `core/graph_brain/neo4j_client.py`, and the rows are returned as JSON through MCP back to the frontend.
6. The `finished` Qt signal delivers the result back on the main thread, and the Chat tab renders it.

## Typical request flow (document ingestion)

1. User picks a folder in the **Documents** tab → `ingest_folder` MCP tool.
2. `core/ingestion_pipeline/batch_ingester.py` discovers supported files (`extractors.py`), extracts raw text, and splits it into overlapping chunks (`chunker.py`).
3. Each chunk is deduplicated by content hash, structured by the Document Brain (`structure_text`), and turned into graph nodes/relationships by the Graph Brain (`build_graph`), which is written to Neo4j (`write_graph`).
4. Progress is tracked as an `IngestionJob` node in Neo4j (`tracker.py`) and returned to the frontend.

## Running everything

- **Neo4j**: `docker compose up -d` (starts only Neo4j by default).
- **MCP Fabric server**: run locally with `python -m core.mcp_fabric.server` (required for folder ingestion, since the server needs to read the same filesystem paths the frontend's file picker returns). A containerized variant is available via `docker compose --profile docker up -d`.
- **Frontend**: `cd frontend && python app.py`.
- Configuration is read from environment variables — see `.env.example`.
