from unittest.mock import MagicMock, AsyncMock
import pytest
from app.services.c4.enrichment.agent_loop import (
    LLMAgentLoop, LoopResult, StopReason, Budget,
)


@pytest.mark.asyncio
async def test_loop_stops_on_natural_end():
    client = MagicMock()
    registry = MagicMock()
    registry.get_tools.return_value = []
    loop = LLMAgentLoop(client=client, tool_registry=registry,
                        system_prompt="test")
    resp = MagicMock()
    resp.content = []
    resp.stop_reason = "end_turn"
    resp.usage = MagicMock(input_tokens=10, output_tokens=20)
    client.messages_create = AsyncMock(return_value=resp)
    result = await loop.run("hello", Budget(max_tool_calls=10, max_tokens=1000))
    assert result.stop_reason == StopReason.natural_stop


@pytest.mark.asyncio
async def test_loop_stops_on_budget_exceeded():
    client = MagicMock()
    registry = MagicMock()
    registry.get_tools.return_value = []
    loop = LLMAgentLoop(client=client, tool_registry=registry,
                        system_prompt="test")
    resp = MagicMock()
    resp.content = [MagicMock(type="tool_use")]
    resp.stop_reason = "tool_use"
    resp.usage = MagicMock(input_tokens=100, output_tokens=100)
    client.messages_create = AsyncMock(return_value=resp)
    result = await loop.run("hello", Budget(max_tool_calls=1, max_tokens=1000))
    assert result.stop_reason == StopReason.budget_exceeded


@pytest.mark.asyncio
async def test_loop_dispatches_tool_calls():
    client = MagicMock()
    registry = MagicMock()
    registry.get_tools.return_value = []
    tool_resp = MagicMock()
    tool_resp.content = [MagicMock(type="tool_use", name="grep",
                                   input={"pattern": "stripe"}, id="call1")]
    tool_resp.stop_reason = "tool_use"
    tool_resp.usage = MagicMock(input_tokens=10, output_tokens=10)
    end_resp = MagicMock()
    end_resp.content = [MagicMock(type="text", text="done")]
    end_resp.stop_reason = "end_turn"
    end_resp.usage = MagicMock(input_tokens=10, output_tokens=10)
    client.messages_create = AsyncMock(side_effect=[tool_resp, end_resp])
    registry.dispatch = MagicMock(return_value={"is_error": False,
                                               "content": "[]"})
    loop = LLMAgentLoop(client=client, tool_registry=registry,
                        system_prompt="test")
    result = await loop.run("find deps", Budget(max_tool_calls=5, max_tokens=5000))
    assert result.tool_calls_used == 1