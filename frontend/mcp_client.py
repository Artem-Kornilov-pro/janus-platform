"""Synchronous-friendly MCP client wrapper for the PyQt6 frontend.

Each call opens a fresh SSE connection to the MCP Fabric server, calls the
requested tool, and returns the parsed JSON result. Designed to be invoked
from a background thread (see frontend.async_runner) so the Qt event loop is
never blocked.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from mcp import ClientSession
from mcp.client.sse import sse_client


def _server_url() -> str:
    return os.environ.get("MCP_SERVER_URL", "http://localhost:8000/sse")


async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call an MCP tool and return its result parsed as JSON when possible."""
    try:
        async with sse_client(_server_url()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments or {})
    except ExceptionGroup as group:
        exc = group.exceptions[0]
        if isinstance(exc, (OSError, httpx.HTTPError)):
            raise RuntimeError(
                f"Could not reach MCP server at {_server_url()}. "
                f"Is it running (python -m core.mcp_fabric.server)? ({exc})"
            ) from group
        raise exc from group
    except (OSError, httpx.HTTPError) as exc:
        raise RuntimeError(
            f"Could not reach MCP server at {_server_url()}. "
            f"Is it running (python -m core.mcp_fabric.server)? ({exc})"
        ) from exc

    if result.isError:
        text = "; ".join(
            block.text for block in result.content if hasattr(block, "text")
        )
        raise RuntimeError(text or f"MCP tool '{name}' returned an error")

    texts = [block.text for block in result.content if hasattr(block, "text")]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except (json.JSONDecodeError, ValueError):
            return texts[0]

    parsed = []
    for text in texts:
        try:
            parsed.append(json.loads(text))
        except (json.JSONDecodeError, ValueError):
            parsed.append(text)
    return parsed


async def ask_graph(question: str) -> Any:
    return await call_tool("ask_graph", {"question": question})


async def get_entity_by_label(label: str, name: str | None = None) -> Any:
    args: dict[str, Any] = {"label": label}
    if name:
        args["name"] = name
    return await call_tool("get_entity_by_label", args)


async def find_relationships(source: str, target: str) -> Any:
    return await call_tool("find_relationships", {"source": source, "target": target})


async def list_invoices() -> Any:
    return await call_tool("list_invoices")


async def calculate_vat(amount: float, vat_rate: float, amount_includes_vat: bool = False) -> Any:
    return await call_tool(
        "calculate_vat",
        {"amount": amount, "vat_rate": vat_rate, "amount_includes_vat": amount_includes_vat},
    )


async def calculate_usn_tax(income: float, rate: float = 6.0) -> Any:
    return await call_tool("calculate_usn_tax", {"income": income, "rate": rate})


async def extract_from_text(text: str, document_id: str | None = None) -> Any:
    args: dict[str, Any] = {"text": text}
    if document_id:
        args["document_id"] = document_id
    return await call_tool("extract_from_text", args)


async def ingest_folder(path: str, recursive: bool = True) -> Any:
    return await call_tool("ingest_folder", {"path": path, "recursive": recursive})


async def get_ingestion_status(job_id: str) -> Any:
    return await call_tool("get_ingestion_status", {"job_id": job_id})


async def list_documents() -> Any:
    return await call_tool("list_documents", {})


async def submit_feedback(
    document_id: str,
    clause_id: str,
    entity_id: str,
    entity_type: str,
    original_value: str,
    is_correct: bool,
    corrected_value: str | None = None,
) -> Any:
    args: dict[str, Any] = {
        "document_id": document_id,
        "clause_id": clause_id,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "original_value": original_value,
        "is_correct": is_correct,
    }
    if corrected_value:
        args["corrected_value"] = corrected_value
    return await call_tool("submit_feedback", args)


async def get_learning_stats() -> Any:
    return await call_tool("get_learning_stats", {})
