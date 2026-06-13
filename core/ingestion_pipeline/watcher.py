"""Watch a folder for new documents and ingest them automatically.

Uses watchdog to detect file-creation events for supported extensions and
runs the batch ingester on each new file as it appears.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from core.graph_brain.neo4j_client import Neo4jClient
from core.ingestion_pipeline.batch_ingester import ingest_paths
from core.ingestion_pipeline.extractors import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


class _NewFileHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, client_factory, folder: str):
        self._loop = loop
        self._client_factory = client_factory
        self._folder = folder

    def on_created(self, event):
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return

        logger.info("New document detected: %s", path)
        asyncio.run_coroutine_threadsafe(self._ingest(path), self._loop)

    async def _ingest(self, path: Path) -> None:
        client = self._client_factory()
        try:
            job = await ingest_paths(client, [path], source_path=self._folder)
            logger.info("Ingested %s: job=%s, errors=%s", path, job.id, job.errors)
        finally:
            await client.close()


def watch_folder(folder: str, client_factory) -> Observer:
    """Start watching `folder` for new documents. Returns the Observer (call .stop() to end)."""
    loop = asyncio.get_event_loop()
    handler = _NewFileHandler(loop, client_factory, folder)

    observer = Observer()
    observer.schedule(handler, folder, recursive=True)
    observer.start()

    logger.info("Watching %s for new documents...", folder)
    return observer
