"""
Query Engine 集成测试

测试内容：
1. 测试 use_query_engine: false 时使用 LangGraph 流程
2. 测试 use_query_engine: true 时使用 Query Engine 流程
3. 测试两种流程的切换
4. 测试向后兼容性
"""

import sys
import asyncio
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path

sys.path.insert(0, '.')

from src.core.agent import RubatoAgent
from src.config.models import (
    AppConfig, FullModelConfig, ModelConfig, MCPConfig, 
    PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
    ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
    RoleModelConfig, RoleExecutionConfig, WorkspaceConfig
)
from src.context.manager import ContextManager
from src.mcp.tools import ToolRegistry
from src.skills.loader import SkillLoader
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, AIMessageChunk


def create_mock_config() -> AppConfig:
    """创建模拟的配置对象"""
    return AppConfig(
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
        prompts=PromptConfig(
            system_prompt_file="prompts/system_prompt.txt"
        ),
        skills=SkillsConfig(
            directory="skills",
            auto_load=False,
            enabled_skills=[]
        ),
        agent=AgentConfig(
            max_context_tokens=80000,
            execution=AgentExecutionConfig(
                recursion_limit=100,
                sub_agent_recursion_limit=50
            )
        ),
        project=ProjectConfig(
            name="test-project",
            root=Path("."),
            workspace=WorkspaceConfig(main=Path("."))
        ),
        file_tools=FileToolsConfig(),
        tools=UnifiedToolsConfig()
    )


def create_mock_skill_loader() -> SkillLoader:
    """创建模拟的 SkillLoader"""
    skill_loader = Mock(spec=SkillLoader)
    skill_loader.has_skill = Mock(return_value=False)
    skill_loader.load_full_skill = AsyncMock(return_value=None)
    skill_loader.get_all_skill_metadata = Mock(return_value={})
    skill_loader.find_matching_skill = Mock(return_value=None)
    return skill_loader


def create_mock_tool_registry() -> ToolRegistry:
    """创建模拟的 ToolRegistry"""
    tool_registry = ToolRegistry()
    
    @tool
    def test_tool_1(query: str) -> str:
        """测试工具1"""
        return f"result: {query}"
    
    @tool
    def test_tool_2(query: str) -> str:
        """测试工具2"""
        return f"result: {query}"
    
    tool_registry.register(test_tool_1)
    tool_registry.register(test_tool_2)
    
    return tool_registry


def create_mock_context_manager() -> ContextManager:
    """创建模拟的 ContextManager"""
    return ContextManager(max_tokens=80000, auto_compress=False)


def create_mock_llm():
    """创建 Mock LLM"""
    mock_llm = Mock()
    mock_llm.ainvoke = AsyncMock()
    mock_llm.astream = AsyncMock()
    mock_llm.bind_tools = Mock(return_value=mock_llm)
    return mock_llm


class TestQueryEngineIntegration:
    """测试 Query Engine 集成功能"""
    
    def test_agent_without_query_engine_by_default(self):
        """测试 1: 默认情况下不使用 Query Engine"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry
            )
        
        assert agent.use_query_engine is False
        assert agent._query_engine is None
        print("   [OK] 默认不使用 Query Engine")
    
    def test_agent_with_query_engine_enabled(self):
        """测试 2: use_query_engine: true 时使用 Query Engine"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
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
            available_tools=['test_tool_1']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry,
                role_config=role_config
            )
        
        assert agent.use_query_engine is True
        assert agent._query_engine is not None
        print("   [OK] use_query_engine: true 时创建 QueryEngine")
    
    def test_agent_with_query_engine_disabled(self):
        """测试 3: use_query_engine: false 时不使用 Query Engine"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        role_config = RoleConfig(
            name='test-langgraph',
            description='测试 LangGraph',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                use_query_engine=False
            ),
            available_tools=['test_tool_1']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry,
                role_config=role_config
            )
        
        assert agent.use_query_engine is False
        assert agent._query_engine is None
        print("   [OK] use_query_engine: false 时不创建 QueryEngine")


class TestQueryEngineFlowSwitch:
    """测试流程切换功能"""
    
    def test_switch_from_langgraph_to_query_engine(self):
        """测试 4: 从 LangGraph 切换到 Query Engine"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry
            )
        
        assert agent.use_query_engine is False
        assert agent._query_engine is None
        
        new_role_config = RoleConfig(
            name='query-engine-role',
            description='Query Engine 角色',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                use_query_engine=True
            ),
            available_tools=['test_tool_1']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent.reload_system_prompt(role_config=new_role_config)
        
        assert agent.use_query_engine is True
        assert agent._query_engine is not None
        print("   [OK] 从 LangGraph 切换到 Query Engine 成功")
    
    def test_switch_from_query_engine_to_langgraph(self):
        """测试 5: 从 Query Engine 切换到 LangGraph"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        initial_role_config = RoleConfig(
            name='query-engine-role',
            description='Query Engine 角色',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                use_query_engine=True
            ),
            available_tools=['test_tool_1']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry,
                role_config=initial_role_config
            )
        
        assert agent.use_query_engine is True
        assert agent._query_engine is not None
        
        new_role_config = RoleConfig(
            name='langgraph-role',
            description='LangGraph 角色',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                use_query_engine=False
            ),
            available_tools=['test_tool_1']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent.reload_system_prompt(role_config=new_role_config)
        
        assert agent.use_query_engine is False
        assert agent._query_engine is None
        print("   [OK] 从 Query Engine 切换到 LangGraph 成功")


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    def test_agent_without_role_config(self):
        """测试 6: 无角色配置时使用默认 LangGraph 流程"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry
            )
        
        assert agent.use_query_engine is False
        assert agent.agent is not None
        print("   [OK] 无角色配置时使用 LangGraph 流程")
    
    def test_role_config_without_use_query_engine_field(self):
        """测试 7: 角色配置无 use_query_engine 字段时默认为 False"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        role_config = RoleConfig(
            name='test-no-field',
            description='无 use_query_engine 字段',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300
            ),
            available_tools=['test_tool_1']
        )
        
        with patch.object(Path, 'exists', return_value=False):
            agent = RubatoAgent(
                config=config,
                skill_loader=skill_loader,
                context_manager=context_manager,
                tool_registry=tool_registry,
                role_config=role_config
            )
        
        assert agent.use_query_engine is False
        print("   [OK] 无 use_query_engine 字段时默认为 False")


class TestQueryEngineExecution:
    """测试 Query Engine 执行流程"""
    
    @pytest.mark.asyncio
    async def test_run_with_query_engine(self):
        """测试 8: 使用 Query Engine 执行任务"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        role_config = RoleConfig(
            name='test-query-exec',
            description='测试 Query Engine 执行',
            system_prompt_file='prompts/roles/test.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=80000,
                timeout=300,
                use_query_engine=True
            ),
            available_tools=['test_tool_1']
        )
        
        mock_llm = create_mock_llm()
        
        async def mock_astream(messages):
            yield AIMessageChunk(content="Hello")
            yield AIMessageChunk(content=" from Query Engine!")
        
        mock_llm.astream = mock_astream
        
        with patch.object(Path, 'exists', return_value=False):
            with patch.object(RubatoAgent, '_create_llm', return_value=mock_llm):
                agent = RubatoAgent(
                    config=config,
                    skill_loader=skill_loader,
                    context_manager=context_manager,
                    tool_registry=tool_registry,
                    role_config=role_config
                )
                
                mock_query_engine = Mock()
                mock_query_engine.get_session_id = Mock(return_value="test-session")
                mock_query_engine.get_messages = Mock(return_value=[])
                mock_query_engine.get_usage = Mock(return_value=Mock(total_tokens=100, cost_usd=0.01))
                
                async def mock_submit_message(user_input, options):
                    from src.core.query_engine import SDKMessage
                    yield SDKMessage.assistant(content="Test response")
                    yield SDKMessage.result(content="Final result")
                
                mock_query_engine.submit_message = mock_submit_message
                
                agent._query_engine = mock_query_engine
                
                result = await agent.run("Test input")
                
                assert result is not None
                print("   [OK] Query Engine 执行成功")


def run_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Query Engine 集成测试")
    print("=" * 60)
    
    test_integration = TestQueryEngineIntegration()
    test_switch = TestQueryEngineFlowSwitch()
    test_compat = TestBackwardCompatibility()
    
    print("\n--- 测试 Query Engine 集成 ---")
    test_integration.test_agent_without_query_engine_by_default()
    test_integration.test_agent_with_query_engine_enabled()
    test_integration.test_agent_with_query_engine_disabled()
    
    print("\n--- 测试流程切换 ---")
    test_switch.test_switch_from_langgraph_to_query_engine()
    test_switch.test_switch_from_query_engine_to_langgraph()
    
    print("\n--- 测试向后兼容性 ---")
    test_compat.test_agent_without_role_config()
    test_compat.test_role_config_without_use_query_engine_field()
    
    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过!")
    print("=" * 60)


if __name__ == '__main__':
    import pytest
    run_tests()
