import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.ingestion_pipeline.watcher import _NewFileHandler, watch_folder


def _make_event(src_path: str, is_directory: bool = False):
    event = MagicMock()
    event.src_path = src_path
    event.is_directory = is_directory
    return event


def test_on_created_ignores_directories():
    loop = asyncio.new_event_loop()
    handler = _NewFileHandler(loop, client_factory=MagicMock(), folder="/tmp")

    with patch("core.ingestion_pipeline.watcher.asyncio.run_coroutine_threadsafe") as mock_run:
        handler.on_created(_make_event("/tmp/newdir", is_directory=True))

    mock_run.assert_not_called()
    loop.close()


def test_on_created_ignores_unsupported_extensions():
    loop = asyncio.new_event_loop()
    handler = _NewFileHandler(loop, client_factory=MagicMock(), folder="/tmp")

    with patch("core.ingestion_pipeline.watcher.asyncio.run_coroutine_threadsafe") as mock_run:
        handler.on_created(_make_event("/tmp/notes.xyz"))

    mock_run.assert_not_called()
    loop.close()


def test_on_created_schedules_ingest_for_supported_extension():
    loop = asyncio.new_event_loop()
    handler = _NewFileHandler(loop, client_factory=MagicMock(), folder="/tmp")

    with patch("core.ingestion_pipeline.watcher.asyncio.run_coroutine_threadsafe") as mock_run:
        handler.on_created(_make_event("/tmp/contract.pdf"))

    mock_run.assert_called_once()
    args = mock_run.call_args.args
    assert args[1] is loop
    loop.close()


@pytest.mark.asyncio
async def test_ingest_closes_client_after_ingest_paths():
    client = AsyncMock()
    handler = _NewFileHandler(asyncio.get_event_loop(), client_factory=lambda: client, folder="/tmp")

    fake_job = MagicMock(id="job-1", errors=[])
    with patch("core.ingestion_pipeline.watcher.ingest_paths", new=AsyncMock(return_value=fake_job)) as mock_ingest:
        await handler._ingest(Path("/tmp/contract.pdf"))

    mock_ingest.assert_awaited_once_with(client, [Path("/tmp/contract.pdf")], source_path="/tmp")
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_closes_client_even_on_error():
    client = AsyncMock()
    handler = _NewFileHandler(asyncio.get_event_loop(), client_factory=lambda: client, folder="/tmp")

    with patch("core.ingestion_pipeline.watcher.ingest_paths", new=AsyncMock(side_effect=RuntimeError("boom"))):
        with pytest.raises(RuntimeError, match="boom"):
            await handler._ingest(Path("/tmp/contract.pdf"))

    client.close.assert_awaited_once()


def test_watch_folder_starts_observer():
    with patch("core.ingestion_pipeline.watcher.Observer") as mock_observer_cls:
        observer = MagicMock()
        mock_observer_cls.return_value = observer

        result = watch_folder("/tmp", client_factory=MagicMock())

    observer.schedule.assert_called_once()
    observer.start.assert_called_once()
    assert result is observer
