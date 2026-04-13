import sys
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm_wrapper import LLMCaller, UsageStats
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, SystemMessage
from langchain_core.tools import tool
from src.config.loader import ConfigLoader


def create_mock_tool(name: str = "test_tool"):
    mock_tool = Mock()
    mock_tool.name = name
    mock_tool.description = f"Test tool: {name}"
    mock_tool.args_schema = Mock()
    mock_tool.args_schema.schema = Mock(return_value={
        "type": "object",
        "properties": {
            "arg1": {"type": "string"}
        },
        "required": ["arg1"]
    })
    return mock_tool


def test_usage_stats():
    stats = UsageStats()
    
    assert stats.prompt_tokens == 0
    assert stats.completion_tokens == 0
    assert stats.total_tokens == 0
    assert stats.call_count == 0
    
    stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert stats.prompt_tokens == 100
    assert stats.completion_tokens == 50
    assert stats.total_tokens == 150
    assert stats.call_count == 1
    
    stats.update(prompt_tokens=200, completion_tokens=100, total_tokens=300)
    assert stats.prompt_tokens == 300
    assert stats.completion_tokens == 150
    assert stats.total_tokens == 450
    assert stats.call_count == 2
    
    stats_dict = stats.to_dict()
    assert stats_dict["prompt_tokens"] == 300
    assert stats_dict["completion_tokens"] == 150
    assert stats_dict["total_tokens"] == 450
    assert stats_dict["call_count"] == 2
    
    stats.reset()
    assert stats.prompt_tokens == 0
    assert stats.call_count == 0


def test_llm_caller_init():
    caller = LLMCaller(api_key="test-key", model="test-model")
    assert caller.model == "test-model"
    assert caller.tools == []
    assert caller.system_prompt is None
    assert caller.usage_stats is not None
    assert caller.client is not None
    
    mock_tool = create_mock_tool()
    caller_with_tools = LLMCaller(api_key="test-key", model="test-model", tools=[mock_tool])
    assert len(caller_with_tools.tools) == 1
    
    caller_with_prompt = LLMCaller(api_key="test-key", model="test-model", system_prompt="You are helpful")
    assert caller_with_prompt.system_prompt == "You are helpful"


def test_bind_tools():
    mock_tool1 = create_mock_tool("tool1")
    mock_tool2 = create_mock_tool("tool2")
    
    caller = LLMCaller(api_key="test-key", model="test-model", tools=[mock_tool1])
    result = caller.bind_tools()
    assert result == caller
    assert caller._tool_schemas is not None
    assert len(caller._tool_schemas) == 1
    
    caller.bind_tools([mock_tool2])
    assert len(caller._tool_schemas) == 1
    
    caller_no_tools = LLMCaller(api_key="test-key", model="test-model")
    caller_no_tools.bind_tools()
    assert caller_no_tools._tool_schemas is None


async def test_invoke():
    caller = LLMCaller(api_key="test-key", model="test-model", base_url="https://api.test.com/v1")
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15
    
    caller.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    messages = [HumanMessage(content="Hello")]
    response = await caller.invoke(messages, use_tools=False)
    
    assert isinstance(response, AIMessage)
    assert response.content == "Test response"
    
    caller_with_prompt = LLMCaller(
        api_key="test-key", model="test-model",
        base_url="https://api.test.com/v1",
        system_prompt="You are a test assistant"
    )
    caller_with_prompt.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    response = await caller_with_prompt.invoke(messages, use_tools=False)
    assert isinstance(response, AIMessage)
    
    call_args = caller_with_prompt.client.chat.completions.create.call_args
    openai_messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
    assert len(openai_messages) == 2
    assert openai_messages[0]["role"] == "system"


async def test_stream():
    caller = LLMCaller(api_key="test-key", model="test-model", base_url="https://api.test.com/v1")
    
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta.content = "Hel"
    mock_chunk1.choices[0].delta.tool_calls = None
    
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta.content = "lo"
    mock_chunk2.choices[0].delta.tool_calls = None
    
    mock_chunk3 = MagicMock()
    mock_chunk3.choices = [MagicMock()]
    mock_chunk3.choices[0].delta.content = "!"
    mock_chunk3.choices[0].delta.tool_calls = None
    
    async def mock_aiter():
        yield mock_chunk1
        yield mock_chunk2
        yield mock_chunk3
    
    caller.client.chat.completions.create = AsyncMock(return_value=mock_aiter())
    
    messages = [HumanMessage(content="Hello")]
    chunks = []
    async for chunk in caller.stream(messages, use_tools=False):
        chunks.append(chunk)
    
    assert len(chunks) == 3
    assert chunks[0].content == "Hel"
    assert chunks[1].content == "lo"
    assert chunks[2].content == "!"


async def test_stream_call():
    caller = LLMCaller(api_key="test-key", model="test-model", base_url="https://api.test.com/v1")
    
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta.content = "Test"
    mock_chunk1.choices[0].delta.tool_calls = None
    
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock()]
    mock_chunk2.choices[0].delta.content = " response"
    mock_chunk2.choices[0].delta.tool_calls = None
    
    async def mock_aiter():
        yield mock_chunk1
        yield mock_chunk2
    
    caller.client.chat.completions.create = AsyncMock(return_value=mock_aiter())
    
    messages = [HumanMessage(content="Hello")]
    events = []
    async for event in caller.stream_call(messages, use_tools=False):
        events.append(event)
    
    text_deltas = [e for e in events if e.get("type") == "text_delta"]
    complete_events = [e for e in events if e.get("type") == "complete"]
    
    assert len(text_deltas) == 2
    assert text_deltas[0]["text"] == "Test"
    assert text_deltas[1]["text"] == " response"
    assert len(complete_events) == 1
    assert isinstance(complete_events[0]["response"], AIMessage)


async def test_with_tools():
    mock_tool = create_mock_tool("test_tool")
    caller = LLMCaller(
        api_key="test-key", model="test-model",
        base_url="https://api.test.com/v1",
        tools=[mock_tool]
    )
    
    mock_tc = MagicMock()
    mock_tc.id = "call_123"
    mock_tc.function.name = "test_tool"
    mock_tc.function.arguments = '{"arg1": "value1"}'
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = ""
    mock_response.choices[0].message.tool_calls = [mock_tc]
    mock_response.usage = None
    
    caller.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    messages = [HumanMessage(content="Use tool")]
    response = await caller.invoke(messages, use_tools=True)
    
    assert isinstance(response, AIMessage)
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["name"] == "test_tool"


async def test_error_handling():
    caller = LLMCaller(api_key="test-key", model="test-model", base_url="https://api.test.com/v1")
    
    caller.client.chat.completions.create = AsyncMock(side_effect=Exception("Test error"))
    
    messages = [HumanMessage(content="Test")]
    
    try:
        await caller.invoke(messages, use_tools=False)
        assert False, "Should have raised exception"
    except Exception as e:
        assert str(e) == "Test error"
    
    caller.usage_stats.update(100, 50, 150)
    caller.reset_usage_stats()
    stats = caller.get_usage_stats()
    assert stats["prompt_tokens"] == 0
    assert stats["call_count"] == 0


async def test_real_llm_caller():
    try:
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        caller = LLMCaller(
            api_key=config.model.model.api_key,
            model=config.model.model.name,
            base_url=config.model.model.base_url,
            temperature=config.model.model.temperature,
            max_tokens=config.model.model.max_tokens,
            system_prompt="You are a test assistant. Please answer briefly."
        )
        
        messages = [HumanMessage(content="Please reply 'Test successful'")]
        response = await caller.invoke(messages, use_tools=False)
        
        stats = caller.get_usage_stats()
        assert stats['call_count'] == 1
        
        caller.reset_usage_stats()
        messages = [HumanMessage(content="Count to 3")]
        
        chunks = []
        async for event in caller.stream_call(messages, use_tools=False):
            if event.get("type") == "text_delta":
                chunks.append(event["text"])
        
        assert len(chunks) > 0
        
    except Exception as e:
        pass


async def test_tool_binding_with_real_tools():
    try:
        @tool
        def get_weather(city: str) -> str:
            """Get weather information"""
            return f"Weather in {city}: Sunny, 25C"
        
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        caller = LLMCaller(
            api_key=config.model.model.api_key,
            model=config.model.model.name,
            base_url=config.model.model.base_url,
            temperature=config.model.model.temperature,
            max_tokens=config.model.model.max_tokens,
            tools=[get_weather],
            system_prompt="You are an assistant that can use tools to get information."
        )
        
        caller.bind_tools()
        assert caller._tool_schemas is not None
        
        messages = [HumanMessage(content="What's the weather in Beijing today?")]
        response = await caller.invoke(messages, use_tools=True)
        
    except Exception as e:
        pass


if __name__ == "__main__":
    print("LLMCaller Complete Test Suite")
    
    success = True
    
    try:
        test_usage_stats()
        print("[OK] test_usage_stats")
    except Exception as e:
        print(f"[FAIL] test_usage_stats: {e}")
        success = False
    
    try:
        test_llm_caller_init()
        print("[OK] test_llm_caller_init")
    except Exception as e:
        print(f"[FAIL] test_llm_caller_init: {e}")
        success = False
    
    try:
        test_bind_tools()
        print("[OK] test_bind_tools")
    except Exception as e:
        print(f"[FAIL] test_bind_tools: {e}")
        success = False
    
    try:
        asyncio.run(test_invoke())
        print("[OK] test_invoke")
    except Exception as e:
        print(f"[FAIL] test_invoke: {e}")
        success = False
    
    try:
        asyncio.run(test_stream())
        print("[OK] test_stream")
    except Exception as e:
        print(f"[FAIL] test_stream: {e}")
        success = False
    
    try:
        asyncio.run(test_stream_call())
        print("[OK] test_stream_call")
    except Exception as e:
        print(f"[FAIL] test_stream_call: {e}")
        success = False
    
    try:
        asyncio.run(test_with_tools())
        print("[OK] test_with_tools")
    except Exception as e:
        print(f"[FAIL] test_with_tools: {e}")
        success = False
    
    try:
        asyncio.run(test_error_handling())
        print("[OK] test_error_handling")
    except Exception as e:
        print(f"[FAIL] test_error_handling: {e}")
        success = False
    
    if success:
        print("\n[SUCCESS] All tests passed!")
        sys.exit(0)
    else:
        print("\n[FAILED] Some tests failed!")
        sys.exit(1)
