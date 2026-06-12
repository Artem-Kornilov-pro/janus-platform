# Janus Platform

Universal professional ML platform: a shared core (document understanding, knowledge graph, MCP data fabric) with domain modules for specific professions. First domain: **Lex** (legal).

## Architecture

```
core/
  document_brain/   # OCR + layout parsing + LLM structuring of documents
  graph_brain/       # Neo4j-based knowledge graph
  mcp_fabric/        # MCP servers for external data sources
domains/
  lex/               # Legal domain module
```

## Status

Early development. Core + Lex domain in progress.
