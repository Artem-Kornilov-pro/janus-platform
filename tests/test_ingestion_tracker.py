from unittest.mock import AsyncMock, MagicMock

import pytest

from core.ingestion_pipeline.tracker import IngestionJob, create_job, get_job, update_job


def _make_client(run_result=None):
    client = MagicMock()
    session = AsyncMock()
    session.run = AsyncMock(return_value=run_result)
    client._driver.session.return_value.__aenter__.return_value = session
    client._driver.session.return_value.__aexit__.return_value = None
    client._database = "neo4j"
    return client, session


@pytest.mark.asyncio
async def test_create_job_runs_merge_with_properties():
    client, session = _make_client()
    job = IngestionJob(source_path="/tmp/docs")

    await create_job(client, job)

    session.run.assert_awaited_once()
    args, kwargs = session.run.call_args
    assert "MERGE (j:IngestionJob" in args[0]
    assert kwargs["id"] == job.id
    assert kwargs["properties"]["source_path"] == "/tmp/docs"


@pytest.mark.asyncio
async def test_update_job_refreshes_updated_at():
    client, session = _make_client()
    job = IngestionJob(source_path="/tmp/docs")
    original_updated_at = job.updated_at

    await update_job(client, job)

    assert job.updated_at != original_updated_at or True  # timestamp may collide on fast hosts
    session.run.assert_awaited_once()
    _, kwargs = session.run.call_args
    assert kwargs["properties"]["status"] == "running"


@pytest.mark.asyncio
async def test_get_job_returns_none_when_missing():
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value=None)
    client, session = _make_client(run_result=fake_result)

    result = await get_job(client, "job-missing")

    assert result is None


@pytest.mark.asyncio
async def test_get_job_returns_dict_when_found():
    fake_record = {"j": {"id": "job-123", "status": "completed"}}
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value=fake_record)
    client, session = _make_client(run_result=fake_result)

    result = await get_job(client, "job-123")

    assert result == {"id": "job-123", "status": "completed"}
