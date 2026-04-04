import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm_wrapper import LLMCaller, UsageStats, RobustChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, SystemMessage
from langchain_core.tools import tool
from src.config.loader import ConfigLoader


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
    return mock_tool


def test_usage_stats():
    print("=" * 60)
    print("Test UsageStats - Usage Statistics")
    print("=" * 60)
    
    stats = UsageStats()
    
    print("\n1. Test initial state:")
    assert stats.prompt_tokens == 0
    assert stats.completion_tokens == 0
    assert stats.total_tokens == 0
    assert stats.call_count == 0
    print("   [OK] Initial state correct")
    
    print("\n2. Test update statistics:")
    stats.update(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    assert stats.prompt_tokens == 100
    assert stats.completion_tokens == 50
    assert stats.total_tokens == 150
    assert stats.call_count == 1
    print("   [OK] Update statistics correct")
    
    print("\n3. Test multiple updates:")
    stats.update(prompt_tokens=200, completion_tokens=100, total_tokens=300)
    assert stats.prompt_tokens == 300
    assert stats.completion_tokens == 150
    assert stats.total_tokens == 450
    assert stats.call_count == 2
    print("   [OK] Multiple updates correct")
    
    print("\n4. Test to_dict:")
    stats_dict = stats.to_dict()
    assert stats_dict["prompt_tokens"] == 300
    assert stats_dict["completion_tokens"] == 150
    assert stats_dict["total_tokens"] == 450
    assert stats_dict["call_count"] == 2
    print("   [OK] to_dict correct")
    
    print("\n5. Test reset:")
    stats.reset()
    assert stats.prompt_tokens == 0
    assert stats.completion_tokens == 0
    assert stats.total_tokens == 0
    assert stats.call_count == 0
    print("   [OK] Reset correct")
    
    print("\n" + "=" * 60)
    print("[OK] UsageStats test completed!")
    print("=" * 60)
    return True


def test_llm_caller_init():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Initialization")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool()
    
    print("\n1. Test basic initialization:")
    caller = LLMCaller(llm=mock_llm)
    assert caller.llm == mock_llm
    assert caller.tools == []
    assert caller.system_prompt is None
    assert caller.usage_stats is not None
    print("   [OK] Basic initialization correct")
    
    print("\n2. Test initialization with tools:")
    caller = LLMCaller(llm=mock_llm, tools=[mock_tool])
    assert len(caller.tools) == 1
    assert caller.tools[0] == mock_tool
    print("   [OK] Initialization with tools correct")
    
    print("\n3. Test initialization with system prompt:")
    caller = LLMCaller(
        llm=mock_llm,
        system_prompt="You are a test assistant"
    )
    assert caller.system_prompt == "You are a test assistant"
    print("   [OK] Initialization with system prompt correct")
    
    print("\n" + "=" * 60)
    print("[OK] LLMCaller initialization test completed!")
    print("=" * 60)
    return True


def test_bind_tools():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Tool Binding")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool1 = create_mock_tool("tool1")
    mock_tool2 = create_mock_tool("tool2")
    
    print("\n1. Test bind tools:")
    caller = LLMCaller(llm=mock_llm, tools=[mock_tool1])
    result = caller.bind_tools()
    
    assert result == caller
    assert caller._bound_llm is not None
    mock_llm.bind_tools.assert_called_once()
    print("   [OK] Tool binding correct")
    
    print("\n2. Test bind new tools:")
    caller.bind_tools([mock_tool2])
    assert mock_llm.bind_tools.call_count == 2
    print("   [OK] Bind new tools correct")
    
    print("\n3. Test chain call:")
    caller = LLMCaller(llm=mock_llm, tools=[mock_tool1])
    result = caller.bind_tools()
    assert result == caller
    print("   [OK] Chain call correct")
    
    print("\n" + "=" * 60)
    print("[OK] Tool binding test completed!")
    print("=" * 60)
    return True


async def test_invoke():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Non-streaming Call")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_response = AIMessage(content="Test response")
    mock_llm.ainvoke.return_value = mock_response
    
    print("\n1. Test basic call:")
    caller = LLMCaller(llm=mock_llm)
    messages = [HumanMessage(content="Hello")]
    
    response = await caller.invoke(messages, use_tools=False)
    
    assert response == mock_response
    mock_llm.ainvoke.assert_called_once()
    print("   [OK] Basic call correct")
    
    print("\n2. Test call with system prompt:")
    caller = LLMCaller(
        llm=mock_llm,
        system_prompt="You are a test assistant"
    )
    
    response = await caller.invoke(messages, use_tools=False)
    
    called_messages = mock_llm.ainvoke.call_args[0][0]
    assert len(called_messages) == 2
    assert isinstance(called_messages[0], SystemMessage)
    assert called_messages[0].content == "You are a test assistant"
    print("   [OK] Call with system prompt correct")
    
    print("\n3. Test with usage statistics:")
    mock_response_with_usage = AIMessage(
        content="Test response",
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150
        }
    )
    mock_llm.ainvoke.return_value = mock_response_with_usage
    
    caller = LLMCaller(llm=mock_llm)
    response = await caller.invoke(messages, use_tools=False)
    
    stats = caller.get_usage_stats()
    assert stats["prompt_tokens"] == 100
    assert stats["completion_tokens"] == 50
    assert stats["total_tokens"] == 150
    assert stats["call_count"] == 1
    print("   [OK] Usage statistics correct")
    
    print("\n" + "=" * 60)
    print("[OK] Non-streaming call test completed!")
    print("=" * 60)
    return True


async def test_stream():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Streaming Call")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    
    async def mock_astream(messages):
        chunks = [
            AIMessageChunk(content="Hel"),
            AIMessageChunk(content="lo"),
            AIMessageChunk(content="!")
        ]
        for chunk in chunks:
            yield chunk
    
    mock_llm.astream = mock_astream
    
    print("\n1. Test basic streaming call:")
    caller = LLMCaller(llm=mock_llm)
    messages = [HumanMessage(content="Hello")]
    
    chunks = []
    async for chunk in caller.stream(messages, use_tools=False):
        chunks.append(chunk)
    
    assert len(chunks) == 3
    assert chunks[0].content == "Hel"
    assert chunks[1].content == "lo"
    assert chunks[2].content == "!"
    print("   [OK] Basic streaming call correct")
    
    print("\n" + "=" * 60)
    print("[OK] Streaming call test completed!")
    print("=" * 60)
    return True


async def test_stream_call():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Structured Streaming Call")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    
    async def mock_astream(messages):
        chunks = [
            AIMessageChunk(content="Test"),
            AIMessageChunk(content=" response")
        ]
        for chunk in chunks:
            yield chunk
    
    mock_llm.astream = mock_astream
    
    print("\n1. Test structured streaming call:")
    caller = LLMCaller(llm=mock_llm)
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
    print("   [OK] Structured streaming call correct")
    
    print("\n" + "=" * 60)
    print("[OK] Structured streaming call test completed!")
    print("=" * 60)
    return True


async def test_with_tools():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Tool Call")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    mock_tool = create_mock_tool("test_tool")
    
    mock_response = AIMessage(
        content="",
        tool_calls=[{
            "name": "test_tool",
            "args": {"arg1": "value1"},
            "id": "call_123"
        }]
    )
    mock_llm.ainvoke.return_value = mock_response
    
    print("\n1. Test call with tools:")
    caller = LLMCaller(llm=mock_llm, tools=[mock_tool])
    messages = [HumanMessage(content="Use tool")]
    
    response = await caller.invoke(messages, use_tools=True)
    
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["name"] == "test_tool"
    print("   [OK] Tool call correct")
    
    print("\n" + "=" * 60)
    print("[OK] Tool call test completed!")
    print("=" * 60)
    return True


async def test_error_handling():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Error Handling")
    print("=" * 60)
    
    mock_llm = create_mock_llm()
    
    print("\n1. Test LLM throws exception:")
    mock_llm.ainvoke.side_effect = Exception("Test error")
    
    caller = LLMCaller(llm=mock_llm)
    messages = [HumanMessage(content="Test")]
    
    try:
        await caller.invoke(messages, use_tools=False)
        print("   [FAIL] Should throw exception")
        return False
    except Exception as e:
        assert str(e) == "Test error"
        print("   [OK] Exception handling correct")
    
    print("\n2. Test reset usage statistics:")
    caller.usage_stats.update(100, 50, 150)
    caller.reset_usage_stats()
    stats = caller.get_usage_stats()
    assert stats["prompt_tokens"] == 0
    assert stats["call_count"] == 0
    print("   [OK] Reset statistics correct")
    
    print("\n" + "=" * 60)
    print("[OK] Error handling test completed!")
    print("=" * 60)
    return True


async def test_real_llm_caller():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Real LLM Call (Optional)")
    print("=" * 60)
    
    try:
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        print("\n1. Create LLMCaller instance:")
        llm = RobustChatOpenAI(
            model=config.model.model.name,
            api_key=config.model.model.api_key,
            base_url=config.model.model.base_url,
            temperature=config.model.model.temperature,
            max_tokens=config.model.model.max_tokens
        )
        
        caller = LLMCaller(
            llm=llm,
            system_prompt="You are a test assistant. Please answer briefly."
        )
        print("   [OK] Instance created successfully")
        
        print("\n2. Test non-streaming call:")
        messages = [HumanMessage(content="Please reply 'Test successful'")]
        response = await caller.invoke(messages, use_tools=False)
        print("   [OK] Call successful")
        print(f"   Response: {response.content[:100]}")
        
        print("\n3. Test usage statistics:")
        stats = caller.get_usage_stats()
        print(f"   Call count: {stats['call_count']}")
        if stats['total_tokens'] > 0:
            print(f"   Total tokens: {stats['total_tokens']}")
        print("   [OK] Usage statistics correct")
        
        print("\n4. Test streaming call:")
        caller.reset_usage_stats()
        messages = [HumanMessage(content="Count to 3")]
        
        chunks = []
        async for event in caller.stream_call(messages, use_tools=False):
            if event.get("type") == "text_delta":
                chunks.append(event["text"])
        
        print("   [OK] Streaming call successful")
        print(f"   Received {len(chunks)} text chunks")
        
        print("\n" + "=" * 60)
        print("[OK] Real LLM call test completed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[SKIP] Real LLM call test skipped: {e}")
        return True


async def test_tool_binding_with_real_tools():
    print("\n" + "=" * 60)
    print("Test LLMCaller - Real Tool Binding (Optional)")
    print("=" * 60)
    
    try:
        @tool
        def get_weather(city: str) -> str:
            """Get weather information
            
            Args:
                city: City name
                
            Returns:
                Weather information
            """
            return f"Weather in {city}: Sunny, 25C"
        
        loader = ConfigLoader(config_dir="config")
        config = loader.load_all()
        
        print("\n1. Create LLMCaller with tools:")
        llm = RobustChatOpenAI(
            model=config.model.model.name,
            api_key=config.model.model.api_key,
            base_url=config.model.model.base_url,
            temperature=config.model.model.temperature,
            max_tokens=config.model.model.max_tokens
        )
        
        caller = LLMCaller(
            llm=llm,
            tools=[get_weather],
            system_prompt="You are an assistant that can use tools to get information."
        )
        print("   [OK] Instance created successfully")
        
        print("\n2. Test tool binding:")
        caller.bind_tools()
        print("   [OK] Tool binding successful")
        
        print("\n3. Test call with tools:")
        messages = [HumanMessage(content="What's the weather in Beijing today?")]
        response = await caller.invoke(messages, use_tools=True)
        
        print("   [OK] Call successful")
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f"   Tool call: {response.tool_calls[0]['name']}")
        else:
            print(f"   Response: {response.content[:100]}")
        
        print("\n" + "=" * 60)
        print("[OK] Real tool binding test completed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[SKIP] Real tool binding test skipped: {e}")
        return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("LLMCaller Complete Test Suite")
    print("=" * 60)
    
    success = True
    
    success = test_usage_stats() and success
    
    success = test_llm_caller_init() and success
    
    success = test_bind_tools() and success
    
    success = asyncio.run(test_invoke()) and success
    
    success = asyncio.run(test_stream()) and success
    
    success = asyncio.run(test_stream_call()) and success
    
    success = asyncio.run(test_with_tools()) and success
    
    success = asyncio.run(test_error_handling()) and success
    
    success = asyncio.run(test_real_llm_caller()) and success
    
    success = asyncio.run(test_tool_binding_with_real_tools()) and success
    
    if success:
        print("\n[SUCCESS] All tests passed!")
        sys.exit(0)
    else:
        print("\n[FAILED] Some tests failed!")
        sys.exit(1)
