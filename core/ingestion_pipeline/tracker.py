"""Track the progress of document ingestion jobs in Neo4j."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

JOB_CONSTRAINT = (
    "CREATE CONSTRAINT ingestion_job_id IF NOT EXISTS "
    "FOR (j:IngestionJob) REQUIRE j.id IS UNIQUE"
)


class IngestionJob(BaseModel):
    id: str = Field(default_factory=lambda: f"job-{uuid.uuid4().hex[:12]}")
    status: str = "running"  # running | completed | failed
    source_path: str
    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    total_chunks: int = 0
    processed_chunks: int = 0
    errors: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


async def create_job(client, job: IngestionJob) -> None:
    query = "MERGE (j:IngestionJob {id: $id}) SET j += $properties"
    async with client._driver.session(database=client._database) as session:
        await session.run(query, id=job.id, properties=job.model_dump())


async def update_job(client, job: IngestionJob) -> None:
    job.updated_at = datetime.now(timezone.utc).isoformat()
    query = "MERGE (j:IngestionJob {id: $id}) SET j += $properties"
    async with client._driver.session(database=client._database) as session:
        await session.run(query, id=job.id, properties=job.model_dump())


async def get_job(client, job_id: str) -> dict | None:
    query = "MATCH (j:IngestionJob {id: $id}) RETURN j"
    async with client._driver.session(database=client._database) as session:
        result = await session.run(query, id=job_id)
        record = await result.single()
        return dict(record["j"]) if record else None
