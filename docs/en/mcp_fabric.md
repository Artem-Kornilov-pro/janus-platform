# MCP Fabric

**Path**: `core/mcp_fabric/`

The MCP Fabric is the single entry point for any external client (the PyQt6
frontend, Claude Desktop, Cursor, etc.) to interact with the Janus Lex
knowledge graph. It is built with **FastMCP** (`mcp.server.fastmcp.FastMCP`)
and served over **Server-Sent Events (SSE)**.

## Files

- `server.py` — defines the FastMCP server `"janus-lex-graph"` and registers
  all tools (see below). Entry point: `python -m core.mcp_fabric.server`.
- `nl2cypher.py` — `question_to_cypher(question, client=None)`: sends the
  user's natural-language question to the LLM with instructions to produce a
  **read-only** Cypher query + parameters. Before execution, the generated
  query is checked against a denylist of write keywords
  (`CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`, `CALL`) and rejected
  if any are present — this is the safety guardrail that lets `ask_graph`
  run arbitrary LLM-generated queries without risking the graph.
- `claude_desktop_config.example.json` — example MCP client config pointing
  at `http://localhost:8000/sse`, for connecting Claude Desktop/Cursor to the
  server directly.

## Tools exposed

| Tool | Backed by | Description |
|---|---|---|
| `get_entity_by_label(label, name)` | `Neo4jClient.get_entity_by_label` | Find nodes of a given label (`Party`, `Obligation`, `Risk`, `LegalNorm`, `Invoice`, `Deadline`, `Claim`, etc.) whose name/title/id/code matches. |
| `find_relationships(source, target)` | `Neo4jClient.find_relationships` | Find relationships between two named entities. |
| `get_risk_report()` | `Neo4jClient.get_risk_report` | All risks across all documents, ordered by severity (high → medium → low). Each record: `document_id`, `document_title`, `clause_title`, `risk`, `severity`. |
| `get_obligations_by_party(party_name)` | `Neo4jClient.get_obligations_by_party` | Obligations where `party_name` is the obligated or beneficiary party (case-insensitive partial match). Each record: `obligated_party`, `obligation`, `beneficiary_party`. |
| `get_deadlines(overdue_only=False)` | `Neo4jClient.get_deadlines` | All `Deadline` nodes sorted by date; `overdue_only=True` filters to past dates. Each record: `deadline_id`, `description`, `date`, `type`, `bound_party`, `clause_title`, `document_title`. |
| `calculate_vat(amount, vat_rate, amount_includes_vat=False)` | `domains.finance.tax_calculator` (`vat_from_net`/`vat_from_gross`) | VAT (НДС) breakdown for an amount — net or gross input. Returns `net_amount`, `vat_rate`, `vat_amount`, `gross_amount`. |
| `calculate_usn_tax(income, rate=6.0)` | `domains.finance.tax_calculator.simplified_tax` | Simplified taxation system (УСН "доходы") tax for an income/rate. |
| `list_invoices()` | `Neo4jClient.list_invoices` | All `Invoice` entities with their issuer/payer parties, for finance reporting. |
| `extract_from_text(text, document_id=None)` | Document Brain `structure_text` + Graph Brain `build_graph` + `write_graph` | Run the full extraction pipeline on raw text and write the result into the graph. |
| `ask_graph(question)` | `nl2cypher.question_to_cypher` + `run_read_query` | Natural-language Q&A over the graph, translated to read-only Cypher. |
| `submit_feedback(document_id, clause_id, entity_id, entity_type, original_value, is_correct, corrected_value=None)` | Learning Brain `store_feedback` | Record human feedback on an extracted entity. |
| `get_learning_stats()` | Learning Brain `compute_stats` | Precision/reward per entity type, from stored feedback. |
| `ingest_folder(path, recursive=True)` | Ingestion Pipeline `ingest_folder` | Extract, chunk, and graph every supported document in a folder; returns an `IngestionJob` summary. |
| `get_ingestion_status(job_id)` | Ingestion Pipeline `get_job` | Status of a previously run ingestion job. |
| `list_documents()` | `Neo4jClient.list_documents` | List all documents currently in the graph. |

`get_risk_report`, `get_obligations_by_party`, `get_deadlines` back the
**Юрист (Legal)** frontend tab; `calculate_vat`, `calculate_usn_tax`,
`list_invoices` back the **Финансы (Finance)** tab — see
[frontend.md](frontend.md). `calculate_vat`/`calculate_usn_tax` are plain
sync functions (no Neo4j access); every other tool opens its own
`Neo4jClient` (via `_get_client()`, which reads `NEO4J_*` env vars) and
closes it when done.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j user |
| `NEO4J_PASSWORD` | *(required)* | Neo4j password |
| `MCP_TRANSPORT` | `sse` | Transport (`sse` for HTTP/SSE clients) |
| `MCP_HOST` | `127.0.0.1` | Bind host (set to `0.0.0.0` in Docker) |
| `MCP_PORT` | `8000` | Bind port |
| `YANDEX_CLOUD_FOLDER`, `YANDEX_CLOUD_API_KEY`, `YANDEX_CLOUD_MODEL` | — | LLM credentials, used by `extract_from_text`, `ask_graph`, ingestion |

> **Note**: `FastMCP`'s `host`/`port` are constructor kwargs with hardcoded
> defaults — they do **not** read `FASTMCP_HOST`/`FASTMCP_PORT` env vars.
> `server.py` reads `MCP_HOST`/`MCP_PORT` itself and passes them explicitly
> to `FastMCP(...)`.

## Running

```bash
# local (required for ingest_folder to see local filesystem paths)
python -m core.mcp_fabric.server

# or via Docker (optional; ingest_folder won't see host paths)
docker compose --profile docker up -d
```

The SSE endpoint is `http://<host>:8000/sse`.

## Why folder ingestion needs a local server

`ingest_folder(path)` takes a filesystem path. If the MCP server runs inside
a Docker container, it has its own filesystem and cannot read paths like
`D:/data` chosen via the frontend's native folder picker on Windows. For
local development, always run the MCP server as a plain Python process on
the same machine/filesystem as the frontend.
