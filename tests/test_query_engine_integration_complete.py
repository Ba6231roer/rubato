"""
Query Engine 集成测试

测试内容：
1. Query Engine 与工具系统的完整集成
2. SubAgent 与 Query Engine 的集成
3. 多轮对话集成测试
4. 双流程切换集成测试
"""

import sys
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.query_engine import (
    QueryEngine,
    QueryEngineConfig,
    SDKMessage,
    SubmitOptions,
)
from src.core.sub_agents import SubAgentManager, create_spawn_agent_tool
from src.core.sub_agent_types import (
    SubAgentSpawnOptions,
    SubAgentDefinition,
    SubAgentExecutionConfig,
    ToolInheritanceMode,
)
from src.core.agent import RubatoAgent
from langchain_core.messages import HumanMessage, AIMessage, AIMessageChunk, ToolMessage
from langchain_core.tools import tool


def create_mock_llm():
    """创建 Mock LLM"""
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock()
    mock_llm.astream = AsyncMock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    return mock_llm


def create_mock_tool(name: str = "test_tool", result: str = "Tool executed"):
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
    mock_tool.ainvoke = AsyncMock(return_value=result)
    return mock_tool


class TestQueryEngineToolIntegration:
    """Query Engine 与工具系统集成测试"""
    
    @pytest.mark.asyncio
    async def test_single_tool_call(self):
        """测试单个工具调用"""
        mock_llm = create_mock_llm()
        mock_tool = create_mock_tool("weather_tool", "Weather: Sunny, 25°C")
        
        async def mock_astream(messages):
            yield {
                "type": "tool_call_start",
                "tool": {
                    "id": "call_123",
                    "name": "weather_tool",
                    "args": {"city": "Beijing"}
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
        
        mock_llm.astream = mock_astream
        
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
        async for msg in engine.submit_message("What's the weather in Beijing?"):
            messages.append(msg)
        
        tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
        tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
        
        assert len(tool_use_msgs) == 1
        assert tool_use_msgs[0].content["name"] == "weather_tool"
        assert len(tool_result_msgs) == 1
        assert "Sunny" in tool_result_msgs[0].content["result"]
        
        print("   [OK] 单个工具调用集成测试通过")
    
    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self):
        """测试多个工具调用"""
        mock_llm = create_mock_llm()
        tool1 = create_mock_tool("tool1", "Result 1")
        tool2 = create_mock_tool("tool2", "Result 2")
        
        async def mock_astream(messages):
            yield {
                "type": "tool_call_start",
                "tool": {"id": "call_1", "name": "tool1", "args": {}}
            }
            yield {
                "type": "tool_call_start",
                "tool": {"id": "call_2", "name": "tool2", "args": {}}
            }
            yield {
                "type": "complete",
                "response": AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "tool1", "args": {}, "id": "call_1"},
                        {"name": "tool2", "args": {}, "id": "call_2"}
                    ]
                )
            }
        
        mock_llm.astream = mock_astream
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[tool1, tool2],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=2
        )
        
        engine = QueryEngine(config)
        
        messages = []
        async for msg in engine.submit_message("Use both tools"):
            messages.append(msg)
        
        tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
        tool_result_msgs = [msg for msg in messages if msg.type == "tool_result"]
        
        assert len(tool_use_msgs) == 2
        assert len(tool_result_msgs) == 2
        
        print("   [OK] 多个工具调用集成测试通过")
    
    @pytest.mark.asyncio
    async def test_tool_chain(self):
        """测试工具链式调用"""
        mock_llm = create_mock_llm()
        tool1 = create_mock_tool("get_data", "data:123")
        tool2 = create_mock_tool("process_data", "processed:123")
        
        call_count = 0
        
        async def mock_astream(messages):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                yield {
                    "type": "tool_call_start",
                    "tool": {"id": "call_1", "name": "get_data", "args": {}}
                }
                yield {
                    "type": "complete",
                    "response": AIMessage(
                        content="",
                        tool_calls=[{"name": "get_data", "args": {}, "id": "call_1"}]
                    )
                }
            else:
                yield {
                    "type": "tool_call_start",
                    "tool": {"id": "call_2", "name": "process_data", "args": {}}
                }
                yield {
                    "type": "complete",
                    "response": AIMessage(
                        content="",
                        tool_calls=[{"name": "process_data", "args": {}, "id": "call_2"}]
                    )
                }
        
        mock_llm.astream = mock_astream
        
        config = QueryEngineConfig(
            cwd="/tmp",
            llm=mock_llm,
            tools=[tool1, tool2],
            skills=[],
            can_use_tool=lambda name, args: True,
            get_app_state=lambda: {},
            set_app_state=lambda state: None,
            max_turns=3
        )
        
        engine = QueryEngine(config)
        
        messages = []
        async for msg in engine.submit_message("Chain tools"):
            messages.append(msg)
        
        tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
        assert len(tool_use_msgs) >= 2
        
        print("   [OK] 工具链式调用集成测试通过")


class TestSubAgentQueryEngineIntegration:
    """SubAgent 与 Query Engine 集成测试"""
    
    @pytest.fixture
    def mock_llm(self):
        """创建模拟 LLM"""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response"))
        llm.astream = AsyncMock()
        llm.bind_tools = Mock(return_value=llm)
        return llm
    
    @pytest.fixture
    def mock_parent_agent(self, mock_llm):
        """创建模拟父 Agent"""
        agent = MagicMock()
        agent.tools = []
        agent.tool_registry = MagicMock()
        agent.tool_registry.get_tools_by_names.return_value = []
        agent.config = MagicMock()
        agent.config.model.model = MagicMock()
        return agent
    
    @pytest.fixture
    def sub_agent_manager(self, mock_llm, mock_parent_agent):
        """创建 SubAgent 管理器"""
        return SubAgentManager(
            llm=mock_llm,
            parent_agent=mock_parent_agent,
            sub_agents_dir="sub_agents",
            recursion_limit=50
        )
    
    @pytest.mark.asyncio
    async def test_spawn_agent_with_query_engine(self, sub_agent_manager):
        """测试使用 Query Engine 的 SubAgent"""
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Test task",
            use_query_engine=True,
            timeout=10
        )
        
        with patch.object(sub_agent_manager, '_execute_sub_agent', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "Task completed"
            
            result = await sub_agent_manager.spawn_agent(options)
            
            assert result == "Task completed"
            print("   [OK] 使用 Query Engine 的 SubAgent 测试通过")
    
    @pytest.mark.asyncio
    async def test_sub_agent_tool_inheritance(self, sub_agent_manager):
        """测试 SubAgent 工具继承"""
        tool1 = create_mock_tool("tool1")
        tool2 = create_mock_tool("tool2")
        
        sub_agent_manager.parent_agent.tools = [tool1, tool2]
        sub_agent_manager.parent_agent.tool_registry.get_tools_by_names.return_value = [tool1]
        
        definition = SubAgentDefinition(
            name="test-agent",
            tool_inheritance=ToolInheritanceMode.INHERIT_SELECTED,
            available_tools=["tool1"]
        )
        
        tools = sub_agent_manager._resolve_tools(definition)
        
        assert len(tools) == 1
        assert tools[0].name == "tool1"
        
        print("   [OK] SubAgent 工具继承测试通过")
    
    @pytest.mark.asyncio
    async def test_sub_agent_recursion_limit(self, sub_agent_manager):
        """测试 SubAgent 递归深度限制"""
        session_id = "test-session"
        
        for _ in range(5):
            sub_agent_manager.increment_depth(session_id)
        
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Test task",
            session_id=session_id,
            max_recursion_depth=5
        )
        
        result = await sub_agent_manager.spawn_agent(options)
        
        assert "错误" in result
        assert "递归深度限制" in result
        
        print("   [OK] SubAgent 递归深度限制测试通过")


class TestMultiTurnConversation:
    """多轮对话集成测试"""
    
    @pytest.mark.asyncio
    async def test_multi_turn_with_context(self):
        """测试带上下文的多轮对话"""
        mock_llm = create_mock_llm()
        mock_tool = create_mock_tool()
        
        turn_count = 0
        
        async def mock_astream(messages):
            nonlocal turn_count
            turn_count += 1
            
            yield {"type": "text_delta", "text": f"Turn {turn_count}"}
            yield {
                "type": "complete",
                "response": AIMessage(
                    content=f"Response for turn {turn_count}",
                    usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
                )
            }
        
        mock_llm.astream = mock_astream
        
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
        
        messages1 = []
        async for msg in engine.submit_message("First message"):
            messages1.append(msg)
        
        assert len(engine.mutable_messages) == 2
        
        messages2 = []
        async for msg in engine.submit_message("Second message"):
            messages2.append(msg)
        
        assert len(engine.mutable_messages) == 4
        
        print("   [OK] 多轮对话上下文测试通过")
    
    @pytest.mark.asyncio
    async def test_conversation_with_tools(self):
        """测试带工具的多轮对话"""
        mock_llm = create_mock_llm()
        mock_tool = create_mock_tool("calculator", "42")
        
        turn_count = 0
        
        async def mock_astream(messages):
            nonlocal turn_count
            turn_count += 1
            
            if turn_count == 1:
                yield {
                    "type": "tool_call_start",
                    "tool": {"id": "call_1", "name": "calculator", "args": {}}
                }
                yield {
                    "type": "complete",
                    "response": AIMessage(
                        content="",
                        tool_calls=[{"name": "calculator", "args": {}, "id": "call_1"}]
                    )
                }
            else:
                yield {"type": "text_delta", "text": "The answer is 42"}
                yield {
                    "type": "complete",
                    "response": AIMessage(content="The answer is 42")
                }
        
        mock_llm.astream = mock_astream
        
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
        async for msg in engine.submit_message("Calculate 6 * 7"):
            messages.append(msg)
        
        tool_use_msgs = [msg for msg in messages if msg.type == "tool_use"]
        assert len(tool_use_msgs) >= 1
        
        print("   [OK] 带工具的多轮对话测试通过")


class TestFlowSwitchIntegration:
    """双流程切换集成测试"""
    
    @pytest.mark.asyncio
    async def test_switch_to_query_engine(self):
        """测试切换到 Query Engine 流程"""
        from src.config.models import (
            AppConfig, FullModelConfig, ModelConfig, MCPConfig,
            PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
            ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
            RoleModelConfig, RoleExecutionConfig, WorkspaceConfig
        )
        from src.context.manager import ContextManager
        from src.mcp.tools import ToolRegistry
        from src.skills.loader import SkillLoader
        
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
        
        role_config = RoleConfig(
            name='test-query-engine',
            description='测试 Query Engine',
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
            with patch.object(RubatoAgent, '_create_llm', return_value=create_mock_llm()):
                agent = RubatoAgent(
                    config=config,
                    skill_loader=skill_loader,
                    context_manager=context_manager,
                    tool_registry=tool_registry,
                    role_config=role_config
                )
        
        assert agent.use_query_engine is True
        assert agent._query_engine is not None
        
        print("   [OK] 切换到 Query Engine 流程测试通过")
    
    @pytest.mark.asyncio
    async def test_switch_to_langgraph(self):
        """测试切换到 LangGraph 流程"""
        from src.config.models import (
            AppConfig, FullModelConfig, ModelConfig, MCPConfig,
            PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
            ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
            RoleModelConfig, RoleExecutionConfig, WorkspaceConfig
        )
        from src.context.manager import ContextManager
        from src.mcp.tools import ToolRegistry
        from src.skills.loader import SkillLoader
        
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
        
        initial_role_config = RoleConfig(
            name='test-query-engine',
            description='测试 Query Engine',
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
            with patch.object(RubatoAgent, '_create_llm', return_value=create_mock_llm()):
                agent = RubatoAgent(
                    config=config,
                    skill_loader=skill_loader,
                    context_manager=context_manager,
                    tool_registry=tool_registry,
                    role_config=initial_role_config
                )
        
        assert agent.use_query_engine is True
        
        new_role_config = RoleConfig(
            name='test-langgraph',
            description='测试 LangGraph',
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
            agent.reload_system_prompt(role_config=new_role_config)
        
        assert agent.use_query_engine is False
        assert agent._query_engine is None
        
        print("   [OK] 切换到 LangGraph 流程测试通过")


def run_integration_tests():
    """运行所有集成测试"""
    import pytest
    
    print("\n" + "=" * 60)
    print("Query Engine 集成测试")
    print("=" * 60)
    
    result = pytest.main([__file__, "-v", "-s"])
    
    print("\n" + "=" * 60)
    if result == 0:
        print("[SUCCESS] 所有集成测试通过!")
    else:
        print("[FAILED] 部分测试失败!")
    print("=" * 60)
    
    return result == 0


if __name__ == "__main__":
    import pytest
    success = run_integration_tests()
    sys.exit(0 if success else 1)
