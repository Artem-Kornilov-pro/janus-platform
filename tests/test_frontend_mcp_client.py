import json
from unittest.mock import AsyncMock, patch

import pytest

from frontend import mcp_client


class FakeContent:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeResult:
    def __init__(self, payload, is_error: bool = False) -> None:
        self.isError = is_error
        if isinstance(payload, str):
            self.content = [FakeContent(payload)]
        else:
            self.content = [FakeContent(json.dumps(payload))]


@pytest.mark.asyncio
async def test_call_tool_parses_json_result():
    fake_session = AsyncMock()
    fake_session.initialize = AsyncMock()
    fake_session.call_tool = AsyncMock(return_value=FakeResult({"hello": "world"}))

    with patch.object(mcp_client, "sse_client") as mock_sse, patch.object(mcp_client, "ClientSession") as mock_session_cls:
        mock_sse.return_value.__aenter__.return_value = (None, None)
        mock_sse.return_value.__aexit__.return_value = None
        mock_session_cls.return_value.__aenter__.return_value = fake_session
        mock_session_cls.return_value.__aexit__.return_value = None

        result = await mcp_client.call_tool("ask_graph", {"question": "test"})

    assert result == {"hello": "world"}
    fake_session.call_tool.assert_awaited_once_with("ask_graph", {"question": "test"})


@pytest.mark.asyncio
async def test_call_tool_raises_on_error_result():
    fake_session = AsyncMock()
    fake_session.initialize = AsyncMock()
    fake_session.call_tool = AsyncMock(return_value=FakeResult("boom", is_error=True))

    with patch.object(mcp_client, "sse_client") as mock_sse, patch.object(mcp_client, "ClientSession") as mock_session_cls:
        mock_sse.return_value.__aenter__.return_value = (None, None)
        mock_sse.return_value.__aexit__.return_value = None
        mock_session_cls.return_value.__aenter__.return_value = fake_session
        mock_session_cls.return_value.__aexit__.return_value = None

        with pytest.raises(RuntimeError, match="boom"):
            await mcp_client.call_tool("ask_graph", {"question": "test"})


@pytest.mark.asyncio
async def test_ask_graph_calls_call_tool():
    with patch.object(mcp_client, "call_tool", new=AsyncMock(return_value=[{"r": 1}])) as mock_call:
        result = await mcp_client.ask_graph("question?")

    mock_call.assert_awaited_once_with("ask_graph", {"question": "question?"})
    assert result == [{"r": 1}]
