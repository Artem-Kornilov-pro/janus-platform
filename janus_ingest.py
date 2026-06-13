"""CLI for the Janus document ingestion pipeline.

Usage:
    janus_ingest.py --folder ./contracts --recursive
    janus_ingest.py --file ./agreement.pdf
    janus_ingest.py --status <job_id>

Environment variables: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (see core.graph_brain.neo4j_client)
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from core.graph_brain.neo4j_client import Neo4jClient
from core.ingestion_pipeline.batch_ingester import ingest_folder, ingest_paths
from core.ingestion_pipeline.tracker import get_job


def _get_client() -> Neo4jClient:
    return Neo4jClient(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ["NEO4J_PASSWORD"],
    )


async def _run(args: argparse.Namespace) -> None:
    client = _get_client()
    try:
        if args.status:
            job = await get_job(client, args.status)
            print(json.dumps(job, indent=2, ensure_ascii=False))
            return

        if args.file:
            job = await ingest_paths(client, [Path(args.file)], source_path=args.file)
        else:
            job = await ingest_folder(client, args.folder, recursive=args.recursive)

        print(json.dumps(job.model_dump(), indent=2, ensure_ascii=False))
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Janus document ingestion pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--folder", help="Folder of documents to ingest")
    group.add_argument("--file", help="Single document to ingest")
    group.add_argument("--status", help="Look up the status of an ingestion job by id")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subfolders (with --folder)")

    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
