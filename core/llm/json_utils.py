"""Helpers for parsing JSON out of LLM text responses."""

import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json_response(raw: str) -> dict:
    """Parse a JSON object from an LLM response, stripping markdown code fences if present."""
    cleaned = _FENCE_RE.sub("", raw.strip())
    if not cleaned:
        raise ValueError("LLM returned an empty response (no JSON to parse)")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {cleaned!r}") from exc
