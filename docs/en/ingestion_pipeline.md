# Ingestion Pipeline

**Path**: `core/ingestion_pipeline/`

The Ingestion Pipeline takes a folder (or single file) of documents and runs
them through extraction → chunking → Document Brain structuring → Graph
Brain GraphRAG → Neo4j, with deduplication, retry, error handling, and
progress tracking.

## Files

- `extractors.py`:
  - `extract_text(path)` — extracts raw text from `.pdf`, `.docx`, `.txt`, `.md`, `.rtf` (using `pdfplumber`, `python-docx`, `striprtf`, plain reads).
  - `discover_documents(folder, recursive)` — walks a folder and returns all files with supported extensions.
  - `UnsupportedFileTypeError` — raised for unsupported extensions.

- `chunker.py`:
  - `chunk_text(text, max_chars=6000, overlap_chars=400)` — splits text into paragraph-aware chunks. Paragraphs are kept whole where possible; chunks include `overlap_chars` of trailing context from the previous chunk so entities/clauses spanning chunk boundaries aren't lost. Paragraphs longer than `max_chars` are hard-split.

- `tracker.py`:
  - `IngestionJob` (pydantic) — `id`, `status` (`pending`/`running`/`completed`/`failed`), `source_path`, `total_files`, `processed_files`, `skipped_files`, `total_chunks`, `processed_chunks`, `errors`, `created_at`, `updated_at`.
  - `JOB_CONSTRAINT` — Neo4j uniqueness constraint on `IngestionJob.id`.
  - `create_job`, `update_job`, `get_job` — persist/read job state as `:IngestionJob` nodes in Neo4j, so progress survives across MCP calls.

- `batch_ingester.py`:
  - `content_hash(text)` — SHA-256 hash of normalized text, used for dedup.
  - `_with_retry` — wraps LLM/graph calls with retry + exponential backoff.
  - `ingest_chunk(client, document_id, chunk_text, ..., extra_instructions)` — runs `structure_text` → `build_graph` → `write_graph` for one chunk.
  - `ingest_file(client, path, job, ...)` — extracts text, chunks it, skips chunks whose `content_hash` already exists in the graph (`find_document_by_hash`), and ingests the rest.
  - `ingest_paths(client, paths, source_path)` — top-level orchestration over multiple files; creates/updates an `IngestionJob`, calls `retrain_prompts` once up front, and continues past per-file errors (recorded in `job.errors`).
  - `ingest_folder(client, path, recursive=True)` — `discover_documents` + `ingest_paths`.

- `watcher.py`:
  - `watch_folder(...)` — uses `watchdog` to monitor a folder for new/changed files and trigger ingestion automatically (for a "drop files here" workflow, independent of the MCP `ingest_folder` call).

- `janus_ingest.py` (project root) — CLI:
  - `--folder <path> [--recursive]` — ingest a folder.
  - `--file <path>` — ingest a single file.
  - `--status <job_id>` — check job status.

## Flow

```
discover_documents(folder)
   │
   ▼
for each file:
  extract_text(path)
   │
   ▼
  chunk_text(text)
   │
   ▼
  for each chunk:
    content_hash(chunk) ──▶ already in graph? ──yes──▶ skip (skipped_files++)
       │ no
       ▼
    structure_text(chunk)  ──▶ StructuredDocument
       │
       ▼
    build_graph(doc_id, structured, extra_instructions=retrain_prompts(...))
       │
       ▼
    write_graph(nodes, relationships)  ──▶ Neo4j
       │
       ▼
    update_job(processed_chunks += 1, processed_files += 1, ...)
```

Errors during any single file/chunk are caught, appended to
`job.errors`, and processing continues with the next file — a corrupt
document doesn't abort the whole batch.

## MCP integration

`ingest_folder` and `get_ingestion_status` are exposed as MCP tools (see
[mcp_fabric.md](mcp_fabric.md)) and used by the frontend's **Documents** tab.
`list_documents` (also MCP) reads back `:Document` nodes written during
ingestion.

## Known limitation

Re-running ingestion on a folder where some files were already ingested may
not skip *all* duplicates (only some) — content-hash dedup currently works
per-chunk and depends on chunk boundaries lining up exactly between runs.
This is a known follow-up, not yet fully fixed.
