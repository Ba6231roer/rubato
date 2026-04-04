"""
Query Engine 端到端测试

测试内容：
1. 完整的对话流程测试
2. 工具调用流程测试
3. SubAgent 创建和执行测试
4. 双流程切换测试
5. 复杂场景测试
"""

import sys
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, List
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.query_engine import (
    QueryEngine,
    QueryEngineConfig,
    SDKMessage,
    SubmitOptions,
)
from src.core.sub_agents import SubAgentManager
from src.core.sub_agent_types import SubAgentSpawnOptions
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk
from langchain_core.tools import tool


def create_mock_llm_with_responses(responses: List[dict]):
    """创建带预设响应的 Mock LLM"""
    mock_llm = Mock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    
    response_index = [0]
    
    async def mock_astream(messages):
        idx = response_index[0]
        if idx < len(responses):
            response = responses[idx]
            response_index[0] += 1
            
            if "text" in response:
                yield {"type": "text_delta", "text": response["text"]}
            
            if "tool_calls" in response:
                for tc in response["tool_calls"]:
                    yield {
                        "type": "tool_call_start",
                        "tool": {
                            "id": tc["id"],
                            "name": tc["name"],
                            "args": tc.get("args", {})
                        }
                    }
            
            yield {
                "type": "complete",
                "response": AIMessage(
                    content=response.get("content", ""),
                    tool_calls=response.get("tool_calls", []),
                    usage_metadata=response.get("usage_metadata", {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15
                    })
                )
            }
    
    mock_llm.astream = mock_astream
    return mock_llm


def create_mock_tool(name: str, result: Any = "Tool executed"):
    """创建 Mock 工具"""
    mock_tool = Mock()
    mock_tool.name = name
    mock_tool.description = f"Test tool: {name}"
    mock_tool.args_schema = Mock()
    mock_tool.args_schema.schema = Mock(return_value={
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": []
    })
    mock_tool.ainvoke = AsyncMock(return_value=result)
    return mock_tool


class TestCompleteConversationFlow:
    """完整对话流程测试"""
    
    @pytest.mark.asyncio
    async def test_simple_conversation(self):
        """测试简单对话"""
        print("\n--- 测试简单对话 ---")
        
        responses = [
            {"text": "Hello!", "content": "Hello! How can I help you?"}
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        messages = []
        async for msg in engine.submit_message("Hello"):
            messages.append(msg)
            print(f"   收到消息: type={msg.type}")
        
        assistant_msgs = [msg for msg in messages if msg.type == "assistant"]
        result_msgs = [msg for msg in messages if msg.type == "result"]
        
        assert len(assistant_msgs) > 0
        assert len(result_msgs) > 0
        
        print("   [OK] 简单对话测试通过")
    
    @pytest.mark.asyncio
    async def test_conversation_with_context(self):
        """测试带上下文的对话"""
        print("\n--- 测试带上下文的对话 ---")
        
        responses = [
            {"text": "I remember", "content": "I'll remember your name is Alice."},
            {"text": "Hello Alice", "content": "Hello Alice! How can I help you?"}
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        messages1 = []
        async for msg in engine.submit_message("My name is Alice"):
            messages1.append(msg)
        
        assert len(engine.mutable_messages) == 2
        
        messages2 = []
        async for msg in engine.submit_message("What's my name?"):
            messages2.append(msg)
        
        assert len(engine.mutable_messages) == 4
        
        print("   [OK] 带上下文的对话测试通过")
    
    @pytest.mark.asyncio
    async def test_long_conversation(self):
        """测试长对话"""
        print("\n--- 测试长对话 ---")
        
        responses = [
            {"text": f"Response {i}", "content": f"Response {i}"}
            for i in range(10)
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        for i in range(10):
            messages = []
            async for msg in engine.submit_message(f"Message {i}"):
                messages.append(msg)
        
        assert len(engine.mutable_messages) == 20
        
        print("   [OK] 长对话测试通过")


class TestToolCallFlow:
    """工具调用流程测试"""
    
    @pytest.mark.asyncio
    async def test_single_tool_call_flow(self):
        """测试单个工具调用流程"""
        print("\n--- 测试单个工具调用流程 ---")
        
        responses = [
            {
                "tool_calls": [{
                    "name": "calculator",
                    "args": {"expression": "2+2"},
                    "id": "call_1"
                }]
            },
            {"text": "The result is 4", "content": "The result is 4"}
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        calculator_tool = create_mock_tool("calculator", "4")
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[calculator_tool],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=3
        )
        
        engine = QueryEngine(config)
        
        messages = []
        phases = []
        async for msg in engine.submit_message("Calculate 2+2"):
            messages.append(msg)
            if msg.type == "assistant" and "phase" in msg.metadata:
                phases.append(msg.metadata["phase"])
        
        tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
        tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
        
        assert len(tool_use_msgs) == 1
        assert len(tool_result_msgs) == 1
        assert "reason_start" in phases
        assert "tool_execution_start" in phases
        
        print("   [OK] 单个工具调用流程测试通过")
    
    @pytest.mark.asyncio
    async def test_parallel_tool_calls(self):
        """测试并行工具调用"""
        print("\n--- 测试并行工具调用 ---")
        
        responses = [
            {
                "tool_calls": [
                    {"name": "weather", "args": {"city": "Beijing"}, "id": "call_1"},
                    {"name": "weather", "args": {"city": "Shanghai"}, "id": "call_2"}
                ]
            },
            {"text": "Both cities", "content": "Beijing: Sunny, Shanghai: Cloudy"}
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        weather_tool = create_mock_tool("weather", "Sunny, 25°C")
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[weather_tool],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=3
        )
        
        engine = QueryEngine(config)
        
        messages = []
        async for msg in engine.submit_message("Weather in Beijing and Shanghai"):
            messages.append(msg)
        
        tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
        tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
        
        assert len(tool_use_msgs) == 2
        assert len(tool_result_msgs) == 2
        
        print("   [OK] 并行工具调用测试通过")
    
    @pytest.mark.asyncio
    async def test_tool_chain_execution(self):
        """测试工具链式执行"""
        print("\n--- 测试工具链式执行 ---")
        
        responses = [
            {"tool_calls": [{"name": "get_data", "args": {}, "id": "call_1"}]},
            {"tool_calls": [{"name": "process_data", "args": {}, "id": "call_2"}]},
            {"tool_calls": [{"name": "save_result", "args": {}, "id": "call_3"}]},
            {"text": "Done", "content": "All steps completed"}
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        tool1 = create_mock_tool("get_data", "data:123")
        tool2 = create_mock_tool("process_data", "processed:123")
        tool3 = create_mock_tool("save_result", "saved")
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[tool1, tool2, tool3],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=5
        )
        
        engine = QueryEngine(config)
        
        messages = []
        async for msg in engine.submit_message("Execute the pipeline"):
            messages.append(msg)
        
        tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
        
        assert len(tool_use_msgs) == 3
        
        tool_names = [msg.content["name"] for msg in tool_use_msgs]
        assert tool_names == ["get_data", "process_data", "save_result"]
        
        print("   [OK] 工具链式执行测试通过")


class TestSubAgentExecution:
    """SubAgent 创建和执行测试"""
    
    @pytest.mark.asyncio
    async def test_spawn_sub_agent(self):
        """测试创建 SubAgent"""
        print("\n--- 测试创建 SubAgent ---")
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="SubAgent result"))
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        mock_parent_agent = MagicMock()
        mock_parent_agent.tools = []
        mock_parent_agent.tool_registry = MagicMock()
        mock_parent_agent.tool_registry.get_tools_by_names.return_value = []
        mock_parent_agent.config = MagicMock()
        mock_parent_agent.config.model.model = MagicMock()
        
        sub_agent_manager = SubAgentManager(
            llm=mock_llm,
            parent_agent=mock_parent_agent,
            sub_agents_dir="sub_agents",
            recursion_limit=50
        )
        
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Test task",
            system_prompt="You are a test agent.",
            timeout=10
        )
        
        with patch.object(sub_agent_manager, '_execute_sub_agent', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "Task completed successfully"
            
            result = await sub_agent_manager.spawn_agent(options)
            
            assert result == "Task completed successfully"
        
        print("   [OK] 创建 SubAgent 测试通过")
    
    @pytest.mark.asyncio
    async def test_sub_agent_with_tools(self):
        """测试带工具的 SubAgent"""
        print("\n--- 测试带工具的 SubAgent ---")
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Result"))
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        tool1 = create_mock_tool("tool1")
        tool2 = create_mock_tool("tool2")
        
        mock_parent_agent = MagicMock()
        mock_parent_agent.tools = [tool1, tool2]
        mock_parent_agent.tool_registry = MagicMock()
        mock_parent_agent.tool_registry.get_tools_by_names.return_value = [tool1]
        mock_parent_agent.config = MagicMock()
        mock_parent_agent.config.model.model = MagicMock()
        
        sub_agent_manager = SubAgentManager(
            llm=mock_llm,
            parent_agent=mock_parent_agent,
            sub_agents_dir="sub_agents",
            recursion_limit=50
        )
        
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Test task",
            available_tools=["tool1"],
            timeout=10
        )
        
        with patch.object(sub_agent_manager, '_execute_sub_agent', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "Success"
            
            result = await sub_agent_manager.spawn_agent(options)
            
            assert result == "Success"
        
        print("   [OK] 带工具的 SubAgent 测试通过")


class TestFlowSwitchE2E:
    """双流程切换端到端测试"""
    
    @pytest.mark.asyncio
    async def test_complete_flow_switch(self):
        """测试完整的流程切换"""
        print("\n--- 测试完整的流程切换 ---")
        
        from src.config.models import (
            AppConfig, FullModelConfig, ModelConfig, MCPConfig,
            PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
            ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
            RoleModelConfig, RoleExecutionConfig, WorkspaceConfig
        )
        from src.context.manager import ContextManager
        from src.mcp.tools import ToolRegistry
        from src.skills.loader import SkillLoader
        from src.core.agent import RubatoAgent
        
        config = AppConfig(
            model=FullModelConfig(
                model=ModelConfig(
                    provider="openai",
                    name="test-model",
                    api_key="test-api-key",
                    base_url="https://api.test.com/v1",
                    temperature=0.7,
                    max_tokens=80000
                )
            ),
            mcp=MCPConfig(servers={}),
            prompts=PromptConfig(system_prompt_file="prompts/system_prompt.txt"),
            skills=SkillsConfig(directory="skills", auto_load=False, enabled_skills=[]),
            agent=AgentConfig(
                max_context_tokens=80000,
                execution=AgentExecutionConfig(recursion_limit=100)
            ),
            project=ProjectConfig(
                name="test-project",
                root=Path("."),
                workspace=WorkspaceConfig(main=Path("."))
            ),
            file_tools=FileToolsConfig(),
            tools=UnifiedToolsConfig()
        )
        
        skill_loader = Mock(spec=SkillLoader)
        skill_loader.has_skill = Mock(return_value=False)
        skill_loader.load_full_skill = AsyncMock(return_value=None)
        skill_loader.get_all_skill_metadata = Mock(return_value={})
        
        tool_registry = ToolRegistry()
        
        @tool
        def test_tool(query: str) -> str:
            """Test tool"""
            return f"result: {query}"
        
        tool_registry.register(test_tool)
        
        context_manager = ContextManager(max_tokens=80000, auto_compress=False)
        
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        
        with patch.object(Path, 'exists', return_value=False):
            with patch.object(RubatoAgent, '_create_llm', return_value=mock_llm):
                agent = RubatoAgent(
                    config=config,
                    skill_loader=skill_loader,
                    context_manager=context_manager,
                    tool_registry=tool_registry
                )
        
        assert agent.use_query_engine is False
        
        query_engine_role = RoleConfig(
            name='query-engine-role',
            description='Query Engine Role',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                use_query_engine=True
            ),
            available_tools=['test_tool']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent.reload_system_prompt(role_config=query_engine_role)
        
        assert agent.use_query_engine is True
        assert agent._query_engine is not None
        
        langgraph_role = RoleConfig(
            name='langgraph-role',
            description='LangGraph Role',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                use_query_engine=False
            ),
            available_tools=['test_tool']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent.reload_system_prompt(role_config=langgraph_role)
        
        assert agent.use_query_engine is False
        assert agent._query_engine is None
        
        print("   [OK] 完整的流程切换测试通过")


class TestComplexScenarios:
    """复杂场景测试"""
    
    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """测试错误恢复"""
        print("\n--- 测试错误恢复 ---")
        
        responses = [
            {"tool_calls": [{"name": "failing_tool", "args": {}, "id": "call_1"}]},
            {"text": "Recovered", "content": "I recovered from the error"}
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        
        failing_tool = create_mock_tool("failing_tool")
        failing_tool.ainvoke = AsyncMock(side_effect=Exception("Tool failed"))
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[failing_tool],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=3
        )
        
        engine = QueryEngine(config)
        
        messages = []
        async for msg in engine.submit_message("Use failing tool"):
            messages.append(msg)
        
        tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
        
        assert len(tool_result_msgs) == 1
        assert "error" in tool_result_msgs[0].content["result"].lower()
        
        print("   [OK] 错误恢复测试通过")
    
    @pytest.mark.asyncio
    async def test_interrupt_and_resume(self):
        """测试中断和恢复"""
        print("\n--- 测试中断和恢复 ---")
        
        responses = [
            {"text": "Working", "content": "Working on it..."}
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        messages = []
        async for msg in engine.submit_message("Start task"):
            messages.append(msg)
            if len(messages) == 2:
                engine.interrupt("User cancelled")
        
        interrupt_msgs = [msg for msg in messages if msg.type == "interrupt"]
        
        assert len(interrupt_msgs) > 0
        
        print("   [OK] 中断和恢复测试通过")
    
    @pytest.mark.asyncio
    async def test_budget_tracking(self):
        """测试预算跟踪"""
        print("\n--- 测试预算跟踪 ---")
        
        responses = [
            {
                "text": "Response",
                "content": "Response",
                "usage_metadata": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
            },
            {
                "text": "Response 2",
                "content": "Response 2",
                "usage_metadata": {"input_tokens": 200, "output_tokens": 100, "total_tokens": 300}
            }
        ]
        
        mock_llm = create_mock_llm_with_responses(responses)
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=1
        )
        
        engine = QueryEngine(config)
        
        messages1 = []
        async for msg in engine.submit_message("First"):
            messages1.append(msg)
        
        usage1 = engine.get_usage()
        assert usage1.total_tokens == 150
        
        messages2 = []
        async for msg in engine.submit_message("Second"):
            messages2.append(msg)
        
        usage2 = engine.get_usage()
        assert usage2.total_tokens == 450
        
        print("   [OK] 预算跟踪测试通过")


def run_e2e_tests():
    """运行所有端到端测试"""
    import pytest
    
    print("\n" + "=" * 60)
    print("Query Engine 端到端测试")
    print("=" * 60)
    
    result = pytest.main([__file__, "-v", "-s"])
    
    print("\n" + "=" * 60)
    if result == 0:
        print("[SUCCESS] 所有端到端测试通过!")
    else:
        print("[FAILED] 部分测试失败!")
    print("=" * 60)
    
    return result == 0


if __name__ == "__main__":
    import pytest
    success = run_e2e_tests()
    sys.exit(0 if success else 1)
