"""
单元测试：角色切换重构验证

测试内容：
1. 测试 RubatoAgent._load_system_prompt() 包含工具说明
2. 测试 RubatoAgent._create_llm() 支持传入模型配置
3. 测试 RubatoAgent.reload_tools() 正确更新工具列表
4. 测试 RubatoAgent.reload_system_prompt() 正确更新系统提示词
5. 测试 get_system_prompt() 和 get_current_system_prompt() 返回相同值
6. 测试 SubAgentManager 实例级别管理
7. 测试子 Agent 工具继承
8. 测试子 Agent 系统提示词包含工具说明
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path

sys.path.insert(0, '.')

from src.core.agent import RubatoAgent
from src.core.sub_agents import SubAgentManager, create_spawn_agent_tool
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
    skill_loader.load_full_skill = Mock(return_value=None)
    skill_loader.get_all_skill_metadata = Mock(return_value={})
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


class TestRubatoAgentSystemPrompt:
    """测试 RubatoAgent 系统提示词相关功能"""
    
    def test_load_system_prompt_contains_tool_docs(self):
        """测试 1: _load_system_prompt() 包含工具说明"""
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
        
        system_prompt = agent._load_system_prompt()
        
        assert system_prompt is not None
        assert len(system_prompt) > 0
        assert "工具" in system_prompt or "Tool" in system_prompt.lower()
        
    def test_get_system_prompt_methods_return_same_value(self):
        """测试 5: get_system_prompt() 和 get_current_system_prompt() 返回相同值"""
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
        
        prompt1 = agent.get_system_prompt()
        prompt2 = agent.get_current_system_prompt()
        
        assert prompt1 == prompt2
        assert prompt1 is not None
        assert len(prompt1) > 0
    
    def test_reload_system_prompt_updates_correctly(self):
        """测试 4: reload_system_prompt() 正确更新系统提示词"""
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
        
        original_prompt = agent.get_system_prompt()
        
        new_role_config = RoleConfig(
            name='test-role',
            description='测试角色',
            system_prompt_file='prompts/test_role.txt'
        )
        
        with patch.object(Path, 'exists', return_value=False):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = Mock()
                mock_open.return_value.read.return_value = "这是测试角色的系统提示词"
                
                agent.reload_system_prompt(role_config=new_role_config)
        
        new_prompt = agent.get_system_prompt()
        
        assert new_prompt != original_prompt
        assert "测试角色" in new_prompt or "这是测试角色的系统提示词" in new_prompt


class TestRubatoAgentLLM:
    """测试 RubatoAgent LLM 创建相关功能"""
    
    def test_create_llm_with_model_config(self):
        """测试 2: _create_llm() 支持传入模型配置"""
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
        
        custom_model_config = ModelConfig(
            provider="openai",
            name="custom-model",
            api_key="custom-api-key",
            base_url="https://custom.api.com/v1",
            temperature=0.5,
            max_tokens=40000
        )
        
        custom_llm = agent._create_llm(model_config=custom_model_config)
        
        assert custom_llm is not None
        assert custom_llm.model_name == "custom-model"
        
        default_llm = agent._create_llm()
        
        assert default_llm.model_name == "test-model"


class TestRubatoAgentTools:
    """测试 RubatoAgent 工具相关功能"""
    
    def test_reload_tools_updates_tool_list(self):
        """测试 3: reload_tools() 正确更新工具列表"""
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
        
        original_tool_count = len(agent.tools)
        
        new_tool_registry = ToolRegistry()
        
        @tool
        def new_tool(query: str) -> str:
            """新工具"""
            return f"new result: {query}"
        
        new_tool_registry.register(new_tool)
        
        agent.reload_tools(new_tool_registry)
        
        assert len(agent.tools) > 0
        tool_names = [t.name for t in agent.tools]
        assert "new_tool" in tool_names


class TestSubAgentManager:
    """测试 SubAgentManager 实例级别管理"""
    
    def test_sub_agent_manager_instance_creation(self):
        """测试 6: SubAgentManager 实例级别管理"""
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
        
        assert agent._sub_agent_manager is not None
        assert agent._sub_agent_manager.parent_agent == agent
        assert agent._sub_agent_manager.llm == agent.llm
    
    def test_sub_agent_tool_inheritance(self):
        """测试 7: 子 Agent 工具继承"""
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
        
        parent_tools = agent.tools
        
        sub_agent = agent._sub_agent_manager.create_agent(
            system_prompt="测试子Agent",
            parent_tools=parent_tools
        )
        
        assert sub_agent is not None
    
    def test_sub_agent_system_prompt_contains_tool_docs(self):
        """测试 8: 子 Agent 系统提示词包含工具说明"""
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
        
        tool_docs = agent._sub_agent_manager._generate_tool_docs_for_sub_agent(agent.tools)
        
        assert tool_docs is not None
        assert len(tool_docs) > 0
        assert "工具" in tool_docs or "Tool" in tool_docs.lower()
    
    def test_spawn_agent_tool_creation(self):
        """测试 spawn_agent 工具创建"""
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
        
        spawn_tool = create_spawn_agent_tool(agent._sub_agent_manager)
        
        assert spawn_tool is not None
        assert spawn_tool.name == "spawn_agent"


class TestRoleConfigIntegration:
    """测试角色配置集成"""
    
    def test_agent_with_role_config(self):
        """测试带角色配置的 Agent 初始化"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        role_config = RoleConfig(
            name='test-executor',
            description='测试执行者',
            system_prompt_file='prompts/roles/test_executor.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(
                max_context_tokens=60000,
                timeout=300,
                recursion_limit=80,
                sub_agent_recursion_limit=40
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
        
        assert agent.role_config == role_config
        assert agent.max_context_tokens == 60000
        assert agent.recursion_limit == 80
    
    def test_agent_role_tools_filtering(self):
        """测试角色工具过滤"""
        config = create_mock_config()
        skill_loader = create_mock_skill_loader()
        context_manager = create_mock_context_manager()
        tool_registry = create_mock_tool_registry()
        
        role_config = RoleConfig(
            name='limited-role',
            description='受限角色',
            system_prompt_file='prompts/roles/limited.txt',
            model=RoleModelConfig(inherit=True),
            execution=RoleExecutionConfig(),
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
        
        tool_names = [t.name for t in agent.tools if t.name != 'spawn_agent']
        assert 'test_tool_1' in tool_names
        assert 'test_tool_2' not in tool_names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
