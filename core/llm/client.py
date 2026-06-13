"""Shared LLM client for Janus, backed by Yandex Cloud's OpenAI-compatible API.

All core modules (Document Brain structurer, Graph Brain GraphRAG, MCP
NL-to-Cypher) go through `complete_json` / `complete` so the model
provider can be swapped in one place.

Environment variables:
    YANDEX_CLOUD_FOLDER    - Yandex Cloud folder ID
    YANDEX_CLOUD_API_KEY   - API key
    YANDEX_CLOUD_MODEL     - model name, e.g. "deepseek-v4-flash/latest"
"""

from __future__ import annotations

import os

import openai


def get_client() -> openai.OpenAI:
    return openai.OpenAI(
        api_key=os.environ["YANDEX_CLOUD_API_KEY"],
        base_url="https://ai.api.cloud.yandex.net/v1",
        project=os.environ["YANDEX_CLOUD_FOLDER"],
    )


def _model_uri() -> str:
    folder = os.environ.get("YANDEX_CLOUD_FOLDER", "unset")
    model = os.environ.get("YANDEX_CLOUD_MODEL", "deepseek-v4-flash/latest")
    return f"gpt://{folder}/{model}"


def complete(
    instructions: str,
    input_text: str,
    max_output_tokens: int = 4096,
    temperature: float = 0.3,
    client: openai.OpenAI | None = None,
) -> str:
    """Run a single instruction/input completion and return the raw text output."""
    client = client or get_client()

    response = client.responses.create(
        model=_model_uri(),
        temperature=temperature,
        instructions=instructions,
        input=input_text,
        max_output_tokens=max_output_tokens,
    )

    return response.output_text
