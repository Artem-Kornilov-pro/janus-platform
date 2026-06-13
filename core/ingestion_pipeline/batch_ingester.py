"""Batch ingestion: extract -> chunk -> Graph Brain -> Neo4j, with dedup and retries.

This ties together the Document Brain (structurer), Graph Brain (GraphRAG)
and Learning Brain (prompt optimizer) into a pipeline that can process a
whole folder of contracts in one run.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from core.document_brain.structurer import structure_text
from core.graph_brain.graph_rag import build_graph
from core.graph_brain.neo4j_client import Neo4jClient
from core.ingestion_pipeline.chunker import chunk_text
from core.ingestion_pipeline.extractors import discover_documents, extract_text
from core.ingestion_pipeline.tracker import IngestionJob, create_job, update_job
from core.learning_brain.prompt_optimizer import retrain_prompts

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 1.0


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _with_retry(func, *args, **kwargs):
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - genuinely want to retry any transient LLM error
            last_error = exc
            delay = BASE_RETRY_DELAY_SECONDS * (2 ** attempt)
            logger.warning("Attempt %d/%d failed: %s. Retrying in %.1fs", attempt + 1, MAX_RETRIES, exc, delay)
            await asyncio.sleep(delay)

    raise last_error


async def ingest_chunk(
    client: Neo4jClient,
    text: str,
    document_id: str,
    source_path: str,
    extra_instructions: str,
) -> tuple[int, int]:
    """Structure and graph one chunk of text, writing the result to Neo4j.

    Returns (nodes_written, relationships_written).
    """
    structured = await _with_retry(structure_text, text)
    nodes, relationships = await _with_retry(build_graph, document_id, structured, None, extra_instructions)

    nodes[0]["properties"]["content_hash"] = content_hash(text)
    nodes[0]["properties"]["source_path"] = source_path
    nodes[0]["properties"]["ingested_at"] = datetime.now(timezone.utc).isoformat()

    await client.write_graph(nodes, relationships)
    return len(nodes), len(relationships)


async def ingest_file(client: Neo4jClient, path: Path, job: IngestionJob, extra_instructions: str) -> None:
    try:
        text = extract_text(path)
    except Exception as exc:  # noqa: BLE001
        job.errors.append(f"{path}: extraction failed: {exc}")
        return

    if not text.strip():
        job.errors.append(f"{path}: empty document, skipped")
        return

    file_hash = content_hash(text)
    existing = await client.find_document_by_hash(file_hash)
    if existing:
        job.skipped_files += 1
        return

    chunks = chunk_text(text)
    job.total_chunks += len(chunks)

    for i, chunk in enumerate(chunks):
        document_id = f"{path.stem}:{file_hash[:8]}:chunk:{i}"
        try:
            await ingest_chunk(client, chunk, document_id, str(path), extra_instructions)
            job.processed_chunks += 1
        except Exception as exc:  # noqa: BLE001
            job.errors.append(f"{path} chunk {i}: {exc}")

    job.processed_files += 1


async def ingest_paths(client: Neo4jClient, paths: list[Path], source_path: str) -> IngestionJob:
    """Ingest a list of files, tracking progress in an IngestionJob node."""
    job = IngestionJob(source_path=source_path, total_files=len(paths))

    await client.setup_schema()
    await create_job(client, job)

    extra_instructions = await retrain_prompts(client)

    for path in paths:
        await ingest_file(client, path, job, extra_instructions)
        await update_job(client, job)

    job.status = "failed" if job.errors and job.processed_files == 0 else "completed"
    await update_job(client, job)

    return job


async def ingest_folder(client: Neo4jClient, folder: str, recursive: bool = True) -> IngestionJob:
    paths = discover_documents(folder, recursive=recursive)
    return await ingest_paths(client, paths, source_path=str(folder))
