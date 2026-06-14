from unittest.mock import MagicMock

import pytest

from core.llm.client import complete
from core.llm.json_utils import parse_json_response


def _make_client(outputs):
    client = MagicMock()
    responses = [MagicMock(output_text=text) for text in outputs]
    client.responses.create.side_effect = responses
    return client


def test_complete_returns_first_non_empty_response():
    client = _make_client(["", '{"cypher": "MATCH (n) RETURN n"}'])

    result = complete("instructions", "question", client=client)

    assert result == '{"cypher": "MATCH (n) RETURN n"}'
    assert client.responses.create.call_count == 2


def test_complete_returns_empty_string_after_exhausting_retries():
    client = _make_client(["", "", ""])

    result = complete("instructions", "question", client=client, retries=2)

    assert result == ""
    assert client.responses.create.call_count == 3


def test_complete_does_not_retry_on_first_success():
    client = _make_client(['{"ok": true}'])

    result = complete("instructions", "question", client=client)

    assert result == '{"ok": true}'
    assert client.responses.create.call_count == 1


def test_parse_json_response_raises_on_empty_string():
    with pytest.raises(ValueError, match="empty response"):
        parse_json_response("")


def test_parse_json_response_raises_on_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_json_response("not json at all")


def test_parse_json_response_strips_markdown_fences():
    result = parse_json_response("```json\n{\"a\": 1}\n```")

    assert result == {"a": 1}
