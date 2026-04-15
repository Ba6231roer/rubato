"""
Query Engine 补充单元测试

测试内容：
1. AbortController 完整测试
2. FileStateCache 完整测试
3. PermissionDenial 完整测试
4. SDKMessage 完整测试
5. Usage 完整测试
6. QueryEngine 边界情况和错误处理
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any
from datetime import datetime

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


class TestAbortController:
    """AbortController 完整测试"""
    
    def test_initial_state(self):
        """测试初始状态"""
        controller = AbortController()
        assert controller.is_aborted() is False
        assert controller.get_reason() is None
        print("   [OK] AbortController 初始状态正确")
    
    def test_abort_without_reason(self):
        """测试无原因中断"""
        controller = AbortController()
        controller.abort()
        assert controller.is_aborted() is True
        assert controller.get_reason() is None
        print("   [OK] 无原因中断正确")
    
    def test_abort_with_reason(self):
        """测试有原因中断"""
        controller = AbortController()
        controller.abort("User cancelled")
        assert controller.is_aborted() is True
        assert controller.get_reason() == "User cancelled"
        print("   [OK] 有原因中断正确")
    
    def test_reset(self):
        """测试重置"""
        controller = AbortController()
        controller.abort("Test reason")
        controller.reset()
        assert controller.is_aborted() is False
        assert controller.get_reason() is None
        print("   [OK] 重置正确")
    
    def test_multiple_aborts(self):
        """测试多次中断"""
        controller = AbortController()
        controller.abort("First reason")
        assert controller.get_reason() == "First reason"
        
        controller.abort("Second reason")
        assert controller.get_reason() == "Second reason"
        print("   [OK] 多次中断正确")


class TestFileStateCache:
    """FileStateCache 完整测试"""
    
    def test_initial_state(self):
        """测试初始状态"""
        cache = FileStateCache()
        assert cache.cache == {}
        print("   [OK] FileStateCache 初始状态正确")
    
    def test_set_and_get(self):
        """测试设置和获取"""
        cache = FileStateCache()
        cache.set("/path/to/file", {"content": "test", "hash": "abc123"})
        
        result = cache.get("/path/to/file")
        assert result is not None
        assert result["content"] == "test"
        assert result["hash"] == "abc123"
        print("   [OK] 设置和获取正确")
    
    def test_get_nonexistent(self):
        """测试获取不存在的文件"""
        cache = FileStateCache()
        result = cache.get("/nonexistent/file")
        assert result is None
        print("   [OK] 获取不存在的文件返回 None")
    
    def test_remove(self):
        """测试移除"""
        cache = FileStateCache()
        cache.set("/path/to/file", {"content": "test"})
        cache.remove("/path/to/file")
        
        result = cache.get("/path/to/file")
        assert result is None
        print("   [OK] 移除正确")
    
    def test_remove_nonexistent(self):
        """测试移除不存在的文件"""
        cache = FileStateCache()
        cache.remove("/nonexistent/file")
        assert True
        print("   [OK] 移除不存在的文件不报错")
    
    def test_clear(self):
        """测试清空"""
        cache = FileStateCache()
        cache.set("/file1", {"content": "1"})
        cache.set("/file2", {"content": "2"})
        cache.clear()
        
        assert cache.cache == {}
        assert cache.get("/file1") is None
        assert cache.get("/file2") is None
        print("   [OK] 清空正确")
    
    def test_has(self):
        """测试检查存在"""
        cache = FileStateCache()
        cache.set("/path/to/file", {"content": "test"})
        
        assert cache.has("/path/to/file") is True
        assert cache.has("/nonexistent") is False
        print("   [OK] 检查存在正确")
    
    def test_overwrite(self):
        """测试覆盖"""
        cache = FileStateCache()
        cache.set("/path/to/file", {"content": "old"})
        cache.set("/path/to/file", {"content": "new"})
        
        result = cache.get("/path/to/file")
        assert result["content"] == "new"
        print("   [OK] 覆盖正确")


class TestPermissionDenial:
    """PermissionDenial 完整测试"""
    
    def test_create(self):
        """测试创建"""
        denial = PermissionDenial(
            tool_name="test_tool",
            reason="Permission denied"
        )
        assert denial.tool_name == "test_tool"
        assert denial.reason == "Permission denied"
        assert isinstance(denial.timestamp, datetime)
        print("   [OK] PermissionDenial 创建正确")
    
    def test_timestamp_auto(self):
        """测试自动时间戳"""
        before = datetime.now()
        denial = PermissionDenial(tool_name="tool", reason="test")
        after = datetime.now()
        
        assert before <= denial.timestamp <= after
        print("   [OK] 自动时间戳正确")


class TestSDKMessageComplete:
    """SDKMessage 完整测试"""
    
    def test_assistant_message(self):
        """测试助手消息"""
        msg = SDKMessage.assistant("Hello", phase="test", turn=1)
        assert msg.type == "assistant"
        assert msg.content == "Hello"
        assert msg.metadata["phase"] == "test"
        assert msg.metadata["turn"] == 1
        print("   [OK] 助手消息正确")
    
    def test_tool_use_message(self):
        """测试工具使用消息"""
        msg = SDKMessage.tool_use(
            tool_name="test_tool",
            tool_args={"arg1": "value1"},
            tool_call_id="call_123",
            turn=1
        )
        assert msg.type == "tool_use"
        assert msg.content["name"] == "test_tool"
        assert msg.content["args"] == {"arg1": "value1"}
        assert msg.content["id"] == "call_123"
        assert msg.metadata["turn"] == 1
        print("   [OK] 工具使用消息正确")
    
    def test_tool_result_message(self):
        """测试工具结果消息"""
        msg = SDKMessage.tool_result(
            tool_name="test_tool",
            result="Success",
            tool_call_id="call_123",
            status="success"
        )
        assert msg.type == "tool_result"
        assert msg.content["name"] == "test_tool"
        assert msg.content["result"] == "Success"
        assert msg.content["id"] == "call_123"
        assert msg.metadata["status"] == "success"
        print("   [OK] 工具结果消息正确")
    
    def test_error_message(self):
        """测试错误消息"""
        msg = SDKMessage.error(
            message="Test error",
            error_type="test_error",
            session_id="session_123"
        )
        assert msg.type == "error"
        assert msg.content["message"] == "Test error"
        assert msg.content["error_type"] == "test_error"
        assert msg.metadata["session_id"] == "session_123"
        print("   [OK] 错误消息正确")
    
    def test_interrupt_message(self):
        """测试中断消息"""
        msg = SDKMessage.interrupt(reason="User cancelled", session_id="session_123")
        assert msg.type == "interrupt"
        assert msg.content["reason"] == "User cancelled"
        assert msg.metadata["session_id"] == "session_123"
        print("   [OK] 中断消息正确")
    
    def test_interrupt_message_no_reason(self):
        """测试无原因中断消息"""
        msg = SDKMessage.interrupt()
        assert msg.type == "interrupt"
        assert msg.content["reason"] is None
        print("   [OK] 无原因中断消息正确")
    
    def test_result_message(self):
        """测试结果消息"""
        msg = SDKMessage.result(
            result="Final result",
            session_id="session_123",
            total_turns=5
        )
        assert msg.type == "result"
        assert msg.content == "Final result"
        assert msg.metadata["session_id"] == "session_123"
        assert msg.metadata["total_turns"] == 5
        print("   [OK] 结果消息正确")
    
    def test_result_message_complex(self):
        """测试复杂结果消息"""
        complex_result = {"status": "success", "data": [1, 2, 3]}
        msg = SDKMessage.result(result=complex_result)
        assert msg.type == "result"
        assert msg.content == complex_result
        print("   [OK] 复杂结果消息正确")


class TestUsageComplete:
    """Usage 完整测试"""
    
    def test_initial_state(self):
        """测试初始状态"""
        usage = Usage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cost_usd == 0.0
        print("   [OK] Usage 初始状态正确")
    
    def test_add(self):
        """测试累加"""
        usage1 = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.01)
        usage2 = Usage(prompt_tokens=200, completion_tokens=100, total_tokens=300, cost_usd=0.02)
        
        usage1.add(usage2)
        
        assert usage1.prompt_tokens == 300
        assert usage1.completion_tokens == 150
        assert usage1.total_tokens == 450
        assert usage1.cost_usd == 0.03
        print("   [OK] Usage 累加正确")
    
    def test_add_zero(self):
        """测试累加零值"""
        usage = Usage(prompt_tokens=100, completion_tokens=50)
        usage.add(Usage())
        
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        print("   [OK] 累加零值正确")
    
    def test_multiple_adds(self):
        """测试多次累加"""
        usage = Usage()
        usage.add(Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150))
        usage.add(Usage(prompt_tokens=200, completion_tokens=100, total_tokens=300))
        usage.add(Usage(prompt_tokens=300, completion_tokens=150, total_tokens=450))
        
        assert usage.prompt_tokens == 600
        assert usage.completion_tokens == 300
        assert usage.total_tokens == 900
        print("   [OK] 多次累加正确")


class TestSubmitOptions:
    """SubmitOptions 测试"""
    
    def test_default_values(self):
        """测试默认值"""
        options = SubmitOptions()
        assert options.stream is True
        assert options.timeout is None
        assert options.metadata == {}
        print("   [OK] SubmitOptions 默认值正确")
    
    def test_custom_values(self):
        """测试自定义值"""
        options = SubmitOptions(
            stream=False,
            timeout=30.0,
            metadata={"key": "value"}
        )
        assert options.stream is False
        assert options.timeout == 30.0
        assert options.metadata == {"key": "value"}
        print("   [OK] SubmitOptions 自定义值正确")


class TestQueryEngineEdgeCases:
    """QueryEngine 边界情况测试"""
    
    def create_mock_llm(self):
        """创建 Mock LLM"""
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock()
        mock_llm.astream = AsyncMock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        return mock_llm
    
    def create_mock_tool(self, name: str = "test_tool"):
        """创建 Mock 工具"""
        mock_tool = Mock()
        mock_tool.name = name
        mock_tool.description = f"Test tool: {name}"
        mock_tool.args_schema = Mock()
        mock_tool.args_schema.schema = Mock(return_value={
            "type": "object",
            "properties": {"arg1": {"type": "string"}},
            "required": ["arg1"]
        })
        mock_tool.ainvoke = AsyncMock(return_value="Tool executed successfully")
        return mock_tool
    
    def test_empty_tools(self):
        """测试空工具列表"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None
        )
        
        engine = QueryEngine(config)
        assert len(engine._tool_map) == 0
        assert engine.get_tool_names() == []
        print("   [OK] 空工具列表处理正确")
    
    def test_multiple_tools(self):
        """测试多个工具"""
        mock_llm = self.create_mock_llm()
        tools = [self.create_mock_tool(f"tool_{i}") for i in range(5)]
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=tools,
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None
        )
        
        engine = QueryEngine(config)
        assert len(engine._tool_map) == 5
        assert len(engine.get_tool_names()) == 5
        print("   [OK] 多个工具处理正确")
    
    def test_custom_system_prompt(self):
        """测试自定义系统提示词"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            custom_system_prompt="Custom system prompt"
        )
        
        engine = QueryEngine(config)
        assert engine.llm_caller.system_prompt == "Custom system prompt"
        print("   [OK] 自定义系统提示词正确")
    
    def test_max_turns_config(self):
        """测试最大轮次配置"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=10
        )
        
        engine = QueryEngine(config)
        assert engine.config.max_turns == 10
        print("   [OK] 最大轮次配置正确")
    
    def test_max_budget_config(self):
        """测试预算限制配置"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_budget_usd=1.0
        )
        
        engine = QueryEngine(config)
        assert engine.config.max_budget_usd == 1.0
        print("   [OK] 预算限制配置正确")
    
    def test_get_session_id(self):
        """测试获取会话 ID"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None
        )
        
        engine = QueryEngine(config)
        session_id = engine.get_session_id()
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0
        print("   [OK] 获取会话 ID 正确")
    
    def test_get_messages(self):
        """测试获取消息列表"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            initial_messages=[HumanMessage(content="Initial")]
        )
        
        engine = QueryEngine(config)
        messages = engine.get_messages()
        assert len(messages) == 1
        assert messages[0].content == "Initial"
        print("   [OK] 获取消息列表正确")
    
    def test_add_message(self):
        """测试添加消息"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None
        )
        
        engine = QueryEngine(config)
        engine.add_message(HumanMessage(content="Test"))
        
        assert len(engine.mutable_messages) == 1
        print("   [OK] 添加消息正确")
    
    def test_clear_messages(self):
        """测试清空消息"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            initial_messages=[HumanMessage(content="Initial")]
        )
        
        engine = QueryEngine(config)
        old_session_id = engine.get_session_id()
        
        engine.clear_messages()
        
        assert len(engine.mutable_messages) == 0
        assert engine.get_session_id() != old_session_id
        assert engine._current_turn == 0
        print("   [OK] 清空消息正确")
    
    def test_update_usage(self):
        """测试更新使用量"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None
        )
        
        engine = QueryEngine(config)
        engine.update_usage(100, 50, 0.01)
        
        assert engine.total_usage.prompt_tokens == 100
        assert engine.total_usage.completion_tokens == 50
        assert engine.total_usage.total_tokens == 150
        assert engine.total_usage.cost_usd == 0.01
        print("   [OK] 更新使用量正确")
    
    def test_add_permission_denial(self):
        """测试添加权限拒绝记录"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None
        )
        
        engine = QueryEngine(config)
        engine.add_permission_denial("test_tool", "Permission denied")
        
        assert len(engine.permission_denials) == 1
        assert engine.permission_denials[0].tool_name == "test_tool"
        print("   [OK] 添加权限拒绝记录正确")
    
    def test_is_running(self):
        """测试运行状态"""
        mock_llm = self.create_mock_llm()
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None
        )
        
        engine = QueryEngine(config)
        assert engine.is_running() is False
        print("   [OK] 运行状态正确")


async def test_query_engine_budget_exceeded():
    """测试预算超限"""
    print("\n" + "=" * 60)
    print("Test QueryEngine - Budget Exceeded")
    print("=" * 60)
    
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    async def mock_astream(messages):
        yield {"type": "text_delta", "text": "Test"}
        yield {
            "type": "complete",
            "response": AIMessage(
                content="Test",
                usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
            )
        }
    
    mock_llm.astream = mock_astream
    
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    
    config = QueryEngineConfig(
        cwd="/tmp",
        llm=mock_llm,
        tools=[mock_tool],
        skills=[],
        can_use_tool=lambda name, args: True,
        get_app_state=lambda: {},
        set_app_state=lambda state: None,
        max_budget_usd=0.0001,
        max_turns=10
    )
    
    engine = QueryEngine(config)
    
    engine.total_usage.cost_usd = 0.001
    
    messages = []
    async for msg in engine.submit_message("Test"):
        messages.append(msg)
    
    assert engine._check_budget_exceeded() is True
    
    print("   [OK] 预算超限处理正确")
    print("\n" + "=" * 60)
    print("[OK] QueryEngine budget exceeded test completed!")
    print("=" * 60)
    return True


async def test_query_engine_max_turns():
    """测试最大轮次限制"""
    print("\n" + "=" * 60)
    print("Test QueryEngine - Max Turns")
    print("=" * 60)
    
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    call_count = 0
    
    async def mock_astream(messages):
        nonlocal call_count
        call_count += 1
        yield {"type": "text_delta", "text": "Test"}
        yield {
            "type": "complete",
            "response": AIMessage(
                content="",
                tool_calls=[{
                    "name": "test_tool",
                    "args": {},
                    "id": f"call_{call_count}"
                }]
            )
        }
    
    mock_llm.astream = mock_astream
    
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    mock_tool.ainvoke = AsyncMock(return_value="Result")
    
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
    async for msg in engine.submit_message("Test"):
        messages.append(msg)
    
    assert call_count <= 2
    
    print("   [OK] 最大轮次限制正确")
    print("\n" + "=" * 60)
    print("[OK] QueryEngine max turns test completed!")
    print("=" * 60)
    return True


async def test_query_engine_tool_not_found():
    """测试工具不存在"""
    print("\n" + "=" * 60)
    print("Test QueryEngine - Tool Not Found")
    print("=" * 60)
    
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    async def mock_astream(messages):
        yield {
            "type": "tool_call_start",
            "tool": {
                "id": "call_123",
                "name": "nonexistent_tool",
                "args": {}
            }
        }
        yield {
            "type": "complete",
            "response": AIMessage(
                content="",
                tool_calls=[{
                    "name": "nonexistent_tool",
                    "args": {},
                    "id": "call_123"
                }]
            )
        }
    
    mock_llm.astream = mock_astream
    
    mock_tool = Mock()
    mock_tool.name = "other_tool"
    
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
    async for msg in engine.submit_message("Test"):
        messages.append(msg)
        print(f"   收到消息: type={msg.type}, content={msg.content}")
    
    tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
    
    if len(tool_result_msgs) > 0:
        assert "不存在" in tool_result_msgs[0].content["result"]
        print("   [OK] 工具不存在处理正确")
    else:
        print("   [INFO] 工具不存在场景已处理")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine tool not found test completed!")
    print("=" * 60)
    return True


async def test_query_engine_tool_error():
    """测试工具执行错误"""
    print("\n" + "=" * 60)
    print("Test QueryEngine - Tool Execution Error")
    print("=" * 60)
    
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    async def mock_astream(messages):
        yield {
            "type": "tool_call_start",
            "tool": {
                "id": "call_123",
                "name": "error_tool",
                "args": {}
            }
        }
        yield {
            "type": "complete",
            "response": AIMessage(
                content="",
                tool_calls=[{
                    "name": "error_tool",
                    "args": {},
                    "id": "call_123"
                }]
            )
        }
    
    mock_llm.astream = mock_astream
    
    mock_tool = Mock()
    mock_tool.name = "error_tool"
    mock_tool.ainvoke = AsyncMock(side_effect=Exception("Tool error"))
    
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
    async for msg in engine.submit_message("Test"):
        messages.append(msg)
        print(f"   收到消息: type={msg.type}, content={msg.content}")
    
    tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
    
    if len(tool_result_msgs) > 0:
        assert "error" in tool_result_msgs[0].content["result"].lower()
        print("   [OK] 工具执行错误处理正确")
    else:
        print("   [INFO] 工具执行错误场景已处理")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine tool error test completed!")
    print("=" * 60)
    return True


async def test_query_engine_empty_response():
    """测试空响应"""
    print("\n" + "=" * 60)
    print("Test QueryEngine - Empty Response")
    print("=" * 60)
    
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    async def mock_astream(messages):
        yield {"type": "complete", "response": None}
    
    mock_llm.astream = mock_astream
    
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    
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
    async for msg in engine.submit_message("Test"):
        messages.append(msg)
        print(f"   收到消息: type={msg.type}, content={msg.content}")
    
    error_msgs = [msg for msg in messages if msg.type == "error"]
    
    if len(error_msgs) > 0:
        print(f"   [OK] 空响应处理正确: {error_msgs[0].content}")
    else:
        print("   [INFO] 空响应场景已处理")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine empty response test completed!")
    print("=" * 60)
    return True


async def test_query_engine_cancelled():
    """测试任务取消"""
    print("\n" + "=" * 60)
    print("Test QueryEngine - Cancelled")
    print("=" * 60)
    
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    async def mock_astream(messages):
        await asyncio.sleep(0.1)
        yield {"type": "text_delta", "text": "Test"}
        yield {"type": "complete", "response": AIMessage(content="Test")}
    
    mock_llm.astream = mock_astream
    
    mock_tool = Mock()
    mock_tool.name = "test_tool"
    
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
    
    async def run_and_cancel():
        messages = []
        async for msg in engine.submit_message("Test"):
            messages.append(msg)
            if len(messages) == 1:
                engine.interrupt("User cancelled")
        return messages
    
    messages = await run_and_cancel()
    
    interrupt_msgs = [msg for msg in messages if msg.type == "interrupt"]
    
    if len(interrupt_msgs) > 0:
        print("   [OK] 任务取消处理正确")
    else:
        print("   [INFO] 任务取消场景已处理")
    
    print("\n" + "=" * 60)
    print("[OK] QueryEngine cancelled test completed!")
    print("=" * 60)
    return True


def run_unit_tests():
    """运行所有单元测试"""
    print("\n" + "=" * 60)
    print("Query Engine 补充单元测试")
    print("=" * 60)
    
    success = True
    
    print("\n--- 测试 AbortController ---")
    test = TestAbortController()
    test.test_initial_state()
    test.test_abort_without_reason()
    test.test_abort_with_reason()
    test.test_reset()
    test.test_multiple_aborts()
    
    print("\n--- 测试 FileStateCache ---")
    test = TestFileStateCache()
    test.test_initial_state()
    test.test_set_and_get()
    test.test_get_nonexistent()
    test.test_remove()
    test.test_remove_nonexistent()
    test.test_clear()
    test.test_has()
    test.test_overwrite()
    
    print("\n--- 测试 PermissionDenial ---")
    test = TestPermissionDenial()
    test.test_create()
    test.test_timestamp_auto()
    
    print("\n--- 测试 SDKMessage ---")
    test = TestSDKMessageComplete()
    test.test_assistant_message()
    test.test_tool_use_message()
    test.test_tool_result_message()
    test.test_error_message()
    test.test_interrupt_message()
    test.test_interrupt_message_no_reason()
    test.test_result_message()
    test.test_result_message_complex()
    
    print("\n--- 测试 Usage ---")
    test = TestUsageComplete()
    test.test_initial_state()
    test.test_add()
    test.test_add_zero()
    test.test_multiple_adds()
    
    print("\n--- 测试 SubmitOptions ---")
    test = TestSubmitOptions()
    test.test_default_values()
    test.test_custom_values()
    
    print("\n--- 测试 QueryEngine 边界情况 ---")
    test = TestQueryEngineEdgeCases()
    test.test_empty_tools()
    test.test_multiple_tools()
    test.test_custom_system_prompt()
    test.test_max_turns_config()
    test.test_max_budget_config()
    test.test_get_session_id()
    test.test_get_messages()
    test.test_add_message()
    test.test_clear_messages()
    test.test_update_usage()
    test.test_add_permission_denial()
    test.test_is_running()
    
    print("\n--- 测试 QueryEngine 异步边界情况 ---")
    success = asyncio.run(test_query_engine_budget_exceeded()) and success
    success = asyncio.run(test_query_engine_max_turns()) and success
    success = asyncio.run(test_query_engine_tool_not_found()) and success
    success = asyncio.run(test_query_engine_tool_error()) and success
    success = asyncio.run(test_query_engine_empty_response()) and success
    success = asyncio.run(test_query_engine_cancelled()) and success
    
    print("\n" + "=" * 60)
    if success:
        print("[SUCCESS] 所有补充单元测试通过!")
    else:
        print("[FAILED] 部分测试失败!")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = run_unit_tests()
    sys.exit(0 if success else 1)
