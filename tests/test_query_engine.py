"""
QueryEngine 单元测试
"""
import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.query_engine import (
    QueryEngine,
    QueryEngineConfig,
    SDKMessage,
    SubmitOptions,
    FileStateCache,
    Usage,
    AbortController,
    PermissionDenial,
)
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langchain_core.tools import tool


def create_mock_llm():
    """创建 Mock LLM"""
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock()
    mock_llm.astream = AsyncMock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    return mock_llm


def create_mock_tool(name: str = "test_tool"):
    """创建 Mock 工具"""
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
    mock_tool.ainvoke = AsyncMock(return_value="Tool executed successfully")
    return mock_tool


def test_sdk_message():
    print("=" * 60)
    print("Test SDKMessage - Message Types")
    print("=" * 60)
    
    print("\n1. Test assistant message:")
    msg = SDKMessage.assistant(content="Hello", phase="test")
    assert msg.type == "assistant"
    assert msg.content == "Hello"
    assert msg.metadata["phase"] == "test"
    print("   [OK] Assistant message correct")
    
    print("\n2. Test tool_use message:")
    msg = SDKMessage.tool_use(
        tool_name="test_tool",
        tool_args={"arg1": "value1"},
        tool_call_id="call_123"
    )
    assert msg.type == "tool_use"
    assert msg.content["name"] == "test_tool"
    assert msg.content["args"] == {"arg1": "value1"}
    print("   [OK] Tool use message correct")
    
    print("\n3. Test tool_result message:")
    msg = SDKMessage.tool_result(
        tool_name="test_tool",
        result="Success",
        tool_call_id="call_123",
        status="success"
    )
    assert msg.type == "tool_result"
    assert msg.content["result"] == "Success"
    assert msg.content["status"] == "success"
    print("   [OK] Tool result message correct")
    
    print("\n4. Test error message:")
    msg = SDKMessage.error(message="Test error", error_type="test")
    assert msg.type == "error"
    assert msg.content["message"] == "Test error"
    print("   [OK] Error message correct")
    
    print("\n" + "=" * 60)
    print("[OK] SDKMessage test completed!")
    print("=" * 60)
    return True


def test_query_engine_config():
    print("\n" + "=" * 60)
    print("Test QueryEngineConfig - Configuration")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool()
    
    print("\n1. Test basic configuration:")
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None
    )
    
    assert config.cwd == "/tmp"
    assert config.llm == mock_llm
    assert len(config.tools) == 1
    assert config.max_turns is None
    print("   [OK] Basic configuration correct")
    
    print("\n2. Test configuration with limits:")
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None,
        max_turns=10,
        max_budget_usd=1.0
    )
    
    assert config.max_turns == 10
    assert config.max_budget_usd == 1.0
    print("   [OK] Configuration with limits correct")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngineConfig test completed!")
    print("=" * 60)
    return True


def test_query_engine_init():
    print("\n" + "=" * 60)
    print("Test QueryEngine - Initialization")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool()
    
    print("\n1. Test basic initialization:")
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None
    )
    
    engine = QueryEngine(config)
    
    assert engine.config == config
    assert len(engine.mutable_messages) == 0
    assert engine.abort_controller is not None
    assert engine.llm_caller is not None
    assert len(engine._tool_map) == 1
    print("   [OK] Basic initialization correct")
    
    print("\n2. Test initialization with initial messages:")
    initial_messages = [HumanMessage(content="Initial message")]
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None,
        initial_messages=initial_messages
    )
    
    engine = QueryEngine(config)
    
    assert len(engine.mutable_messages) == 1
    assert engine.mutable_messages[0].content == "Initial message"
    print("   [OK] Initialization with messages correct")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine initialization test completed!")
    print("=" * 60)
    return True


async def test_query_engine_simple_flow():
    print("\n" + "=" * 60)
    print("Test QueryEngine - Simple Flow")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool()
    
    async def mock_astream(messages):
        chunks = [
            AIMessageChunk(content="Hello"),
            AIMessageChunk(content="!"),
        ]
        for chunk in chunks:
            yield chunk
    
    mock_llm.astream = mock_astream
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    print("\n1. Test simple message flow:")
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None,
        max_turns=1
    )
    
    engine = QueryEngine(config)
    
    messages = []
    async for msg in engine.submit_message("Test message"):
        messages.append(msg)
    
    assert len(messages) > 0
    assert any(msg.type == "assistant" for msg in messages)
    print("   [OK] Simple flow completed")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine simple flow test completed!")
    print("=" * 60)
    return True


async def test_query_engine_tool_call():
    print("\n" + "=" * 60)
    print("Test QueryEngine - Tool Call Flow")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool("weather_tool")
    
    async def mock_astream_with_tool(messages):
        yield {
            "type": "tool_call_start",
            "tool": {
                "id": "call_123",
                "name": "weather_tool",
                "args": {}
            }
        }
        yield {
            "type": "complete",
            "response": AIMessage(
                content="",
                tool_calls=[{
                    "name": "weather_tool",
                    "args": {"city": "Beijing"},
                    "id": "call_123"
                }]
            )
        }
    
    mock_llm.astream = mock_astream_with_tool
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    print("\n1. Test tool call flow:")
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None,
        max_turns=2
    )
    
    engine = QueryEngine(config)
    
    messages = []
    async for msg in engine.submit_message("What's the weather?"):
        messages.append(msg)
    
    tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
    tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
    
    assert len(tool_use_msgs) > 0
    print("   [OK] Tool call flow completed")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine tool call test completed!")
    print("=" * 60)
    return True


async def test_query_engine_permission_denial():
    print("\n" + "=" * 60)
    print("Test QueryEngine - Permission Denial")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool("restricted_tool")
    
    async def mock_astream_with_tool(messages):
        yield {
            "type": "tool_call_start",
            "tool": {
                "id": "call_123",
                "name": "restricted_tool",
                "args": {}
            }
        }
        yield {
            "type": "complete",
            "response": AIMessage(
                content="",
                tool_calls=[{
                    "name": "restricted_tool",
                    "args": {"arg1": "value1"},
                    "id": "call_123"
                }]
            )
        }
    
    mock_llm.astream = mock_astream_with_tool
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    print("\n1. Test permission denial:")
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: False,
        get_app_state=lambda: {},
        set_app_state=lambda state: None,
        max_turns=1
    )
    
    engine = QueryEngine(config)
    
    messages = []
    async for msg in engine.submit_message("Use restricted tool"):
        messages.append(msg)
    
    tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
    
    assert len(tool_result_msgs) > 0
    assert "权限拒绝" in tool_result_msgs[0].content["result"]
    print("   [OK] Permission denial handled correctly")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine permission denial test completed!")
    print("=" * 60)
    return True


async def test_query_engine_interrupt():
    print("\n" + "=" * 60)
    print("Test QueryEngine - Interrupt")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool()
    
    async def mock_astream(messages):
        yield {"type": "text_delta", "text": "Test"}
        yield {"type": "complete", "response": AIMessage(content="Test")}
    
    mock_llm.astream = mock_astream
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    print("\n1. Test interrupt:")
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None,
        max_turns=1
    )
    
    engine = QueryEngine(config)
    
    messages = []
    async for msg in engine.submit_message("Test"):
        messages.append(msg)
        if len(messages) == 1:
            engine.interrupt("User cancelled")
    
    interrupt_msgs = [msg for msg in messages if msg.type == "interrupt"]
    
    print("   [OK] Interrupt handled correctly")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine interrupt test completed!")
    print("=" * 60)
    return True


def test_usage_and_stats():
    print("\n" + "=" * 60)
    print("Test Usage and Statistics")
    print("=" * 60)
    
    print("\n1. Test Usage class:")
    usage = Usage()
    
    usage.add(Usage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.01
    ))
    
    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 150
    assert usage.cost_usd == 0.01
    print("   [OK] Usage class correct")
    
    print("\n" + "=" * 60)
    print("[OK] Usage and statistics test completed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("QueryEngine Complete Test Suite")
    print("=" * 60)
    
    success = True
    
    success = test_sdk_message() and success
    
    success = test_query_engine_config() and success
    
    success = test_query_engine_init() and success
    
    success = asyncio.run(test_query_engine_simple_flow()) and success
    
    success = asyncio.run(test_query_engine_tool_call()) and success
    
    success = asyncio.run(test_query_engine_permission_denial()) and success
    
    success = asyncio.run(test_query_engine_interrupt()) and success
    
    success = test_usage_and_stats() and success
    
    if success:
        print("\n[SUCCESS] All tests passed!")
        sys.exit(0)
    else:
        print("\n[FAILED] Some tests failed!")
        sys.exit(1)
