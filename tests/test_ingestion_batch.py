from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from core.document_brain.models import StructuredDocument
from core.ingestion_pipeline import batch_ingester
from core.ingestion_pipeline.batch_ingester import content_hash, ingest_paths

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "ingestion"


class FakeClient:
    def __init__(self, existing_hashes: set[str] | None = None):
        self.existing_hashes = existing_hashes or set()
        self.written_graphs: list[tuple[list, list]] = []
        self.setup_schema = AsyncMock()

    async def find_document_by_hash(self, content_hash: str):
        return {"id": "existing"} if content_hash in self.existing_hashes else None

    async def write_graph(self, nodes, relationships):
        self.written_graphs.append((nodes, relationships))


@pytest.fixture(autouse=True)
def _patch_pipeline(monkeypatch):
    structured = StructuredDocument(
        document_type="contract",
        title="Test Document",
        parties=["A", "B"],
        sections=[],
        summary="",
    )
    monkeypatch.setattr(batch_ingester, "structure_text", lambda text: structured)
    monkeypatch.setattr(
        batch_ingester,
        "build_graph",
        lambda doc_id, doc, client=None, extra_instructions="": (
            [{"label": "Document", "key_property": "id", "key_value": doc_id, "properties": {}}],
            [],
        ),
    )
    monkeypatch.setattr(batch_ingester, "retrain_prompts", AsyncMock(return_value=""))
    monkeypatch.setattr(batch_ingester, "create_job", AsyncMock())
    monkeypatch.setattr(batch_ingester, "update_job", AsyncMock())


@pytest.mark.asyncio
async def test_ingest_paths_processes_new_files():
    client = FakeClient()
    paths = [FIXTURES / "sample.txt", FIXTURES / "sample.md"]

    job = await ingest_paths(client, paths, source_path=str(FIXTURES))

    assert job.status == "completed"
    assert job.processed_files == 2
    assert job.skipped_files == 0
    assert len(client.written_graphs) == 2


@pytest.mark.asyncio
async def test_ingest_paths_skips_duplicate_content():
    sample_text = (FIXTURES / "sample.txt").read_text(encoding="utf-8")
    existing_hash = content_hash(sample_text)

    client = FakeClient(existing_hashes={existing_hash})
    paths = [FIXTURES / "sample.txt", FIXTURES / "sample.md"]

    job = await ingest_paths(client, paths, source_path=str(FIXTURES))

    assert job.processed_files == 1
    assert job.skipped_files == 1
    assert len(client.written_graphs) == 1


@pytest.mark.asyncio
async def test_ingest_paths_continues_on_extraction_error(tmp_path):
    bad_file = tmp_path / "bad.txt"
    bad_file.write_text("Some valid content", encoding="utf-8")

    # Monkeypatch extract_text to raise for this specific path
    import core.ingestion_pipeline.batch_ingester as mod

    original_extract = mod.extract_text

    def boom(path):
        if str(path) == str(bad_file):
            raise ValueError("corrupt file")
        return original_extract(path)

    mod.extract_text = boom
    try:
        client = FakeClient()
        job = await ingest_paths(client, [bad_file, FIXTURES / "sample.txt"], source_path=str(tmp_path))
    finally:
        mod.extract_text = original_extract

    assert job.processed_files == 1
    assert any("corrupt file" in e for e in job.errors)
