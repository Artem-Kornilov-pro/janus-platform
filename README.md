# Janus Platform

Universal professional ML platform: a shared core (document understanding, knowledge graph, MCP data fabric) with domain modules for specific professions. First domain: **Lex** (legal: contracts, obligations, risks, deadlines, claims), with a **Finance** domain (VAT/УСН tax calculations, invoice reporting) layered on top.

## Architecture

```
core/
  document_brain/      # OCR + layout parsing + LLM structuring of documents
  graph_brain/          # Neo4j-based knowledge graph (Lex ontology)
  learning_brain/        # Human feedback, reward model, prompt optimization
  ingestion_pipeline/     # Multi-format extraction, chunking, batch graph writes
  mcp_fabric/              # MCP server (FastMCP/SSE) exposing all tools
  llm/                      # Shared LLM client (Yandex Cloud, OpenAI-compatible)
domains/
  lex/    # Legal domain (ontology lives in core/graph_brain/schema.py)
  finance/ # VAT / УСН tax calculator helpers
frontend/  # PyQt6 desktop UI: Chat, Documents, Graph, Entities, Learning Brain, Finance, Legal
```

## Status

Core, Lex domain, and a Finance domain extension are implemented; the desktop frontend covers all seven tabs above. See [docs/en/architecture.md](docs/en/architecture.md) for the full picture.

## Documentation

Detailed docs (English / Русский) for each component:

- [Setup & Installation](docs/en/setup.md) / [Установка и запуск](docs/ru/setup.md)
- [Architecture overview](docs/en/architecture.md) / [Обзор архитектуры](docs/ru/architecture.md)
- [Document Brain](docs/en/document_brain.md) / [Document Brain (рус.)](docs/ru/document_brain.md)
- [Graph Brain](docs/en/graph_brain.md) / [Graph Brain (рус.)](docs/ru/graph_brain.md)
- [MCP Fabric](docs/en/mcp_fabric.md) / [MCP Fabric (рус.)](docs/ru/mcp_fabric.md)
- [Learning Brain](docs/en/learning_brain.md) / [Learning Brain (рус.)](docs/ru/learning_brain.md)
- [Ingestion Pipeline](docs/en/ingestion_pipeline.md) / [Конвейер загрузки](docs/ru/ingestion_pipeline.md)
- [Frontend (PyQt6)](docs/en/frontend.md) / [Фронтенд (PyQt6)](docs/ru/frontend.md)
