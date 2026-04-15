"""
测试 spawn_agent 工具修复

测试内容：
1. _should_enable_spawn_agent() 默认返回 True，配置为 true 返回 True，配置为 false 返回 False
2. _ensure_spawn_agent_tool() 在应启用但缺失时添加，在应禁用时移除
3. reload_tools() 在工具重载后保留 spawn_agent
4. 角色切换时相同 sub_agent_recursion_limit 保留 spawn_agent
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

sys.path.insert(0, '.')

from src.core.agent import RubatoAgent
from src.core.sub_agents import SubAgentManager, create_spawn_agent_tool
from src.config.models import (
    AppConfig, FullModelConfig, ModelConfig, MCPConfig,
    PromptConfig, SkillsConfig, AgentConfig, AgentExecutionConfig,
    ProjectConfig, FileToolsConfig, UnifiedToolsConfig, RoleConfig,
    RoleExecutionConfig, WorkspaceConfig, RoleToolsConfig
)
from src.context.manager import ContextManager
from src.mcp.tools import ToolRegistry
from src.skills.loader import SkillLoader
from langchain_core.tools import tool


def create_mock_config() -> AppConfig:
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
    skill_loader = Mock(spec=SkillLoader)
    skill_loader.has_skill = Mock(return_value=False)
    skill_loader.load_full_skill = Mock(return_value=None)
    skill_loader.get_all_skill_metadata = Mock(return_value={})
    return skill_loader


def create_mock_tool_registry() -> ToolRegistry:
    tool_registry = ToolRegistry()

    @tool
    def test_tool_1(query: str) -> str:
        """Test tool 1"""
        return f"result: {query}"

    tool_registry.register(test_tool_1)
    return tool_registry


def create_mock_context_manager() -> ContextManager:
    return ContextManager()


def _create_agent(role_config=None):
    config = create_mock_config()
    skill_loader = create_mock_skill_loader()
    context_manager = create_mock_context_manager()
    tool_registry = create_mock_tool_registry()

    with patch.object(Path, 'exists', return_value=False):
        agent = RubatoAgent(
            config=config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry,
            role_config=role_config
        )
    return agent


class TestShouldEnableSpawnAgent:
    """测试 _should_enable_spawn_agent() 方法"""

    def test_default_no_role_config_returns_true(self):
        agent = _create_agent(role_config=None)
        assert agent._should_enable_spawn_agent() is True

    def test_default_no_tools_config_returns_true(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt'
        )
        agent = _create_agent(role_config=role_config)
        assert agent._should_enable_spawn_agent() is True

    def test_default_no_builtin_config_returns_true(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt',
            tools=RoleToolsConfig()
        )
        agent = _create_agent(role_config=role_config)
        assert agent._should_enable_spawn_agent() is True

    def test_spawn_agent_true_returns_true(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt',
            tools=RoleToolsConfig(builtin={"spawn_agent": True})
        )
        agent = _create_agent(role_config=role_config)
        assert agent._should_enable_spawn_agent() is True

    def test_spawn_agent_false_returns_false(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt',
            tools=RoleToolsConfig(builtin={"spawn_agent": False})
        )
        agent = _create_agent(role_config=role_config)
        assert agent._should_enable_spawn_agent() is False

    def test_default_spawn_agent_missing_returns_true(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt',
            tools=RoleToolsConfig(builtin={"shell_tool": True})
        )
        agent = _create_agent(role_config=role_config)
        assert agent._should_enable_spawn_agent() is True


class TestEnsureSpawnAgentTool:
    """测试 _ensure_spawn_agent_tool() 方法"""

    def test_adds_spawn_agent_when_missing_and_enabled(self):
        agent = _create_agent(role_config=None)
        agent.tools = [t for t in agent.tools if t.name != 'spawn_agent']
        assert not any(t.name == 'spawn_agent' for t in agent.tools)

        agent._ensure_spawn_agent_tool()

        assert any(t.name == 'spawn_agent' for t in agent.tools)

    def test_removes_spawn_agent_when_present_and_disabled(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt',
            tools=RoleToolsConfig(builtin={"spawn_agent": False})
        )
        agent = _create_agent(role_config=role_config)
        assert not any(t.name == 'spawn_agent' for t in agent.tools)

        spawn_tool = create_spawn_agent_tool(agent._sub_agent_manager)
        agent.tools.append(spawn_tool)
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        agent._ensure_spawn_agent_tool()

        assert not any(t.name == 'spawn_agent' for t in agent.tools)

    def test_no_change_when_spawn_agent_present_and_enabled(self):
        agent = _create_agent(role_config=None)
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        tool_count_before = len(agent.tools)
        agent._ensure_spawn_agent_tool()

        assert any(t.name == 'spawn_agent' for t in agent.tools)
        assert len(agent.tools) == tool_count_before

    def test_no_change_when_spawn_agent_missing_and_disabled(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt',
            tools=RoleToolsConfig(builtin={"spawn_agent": False})
        )
        agent = _create_agent(role_config=role_config)
        assert not any(t.name == 'spawn_agent' for t in agent.tools)

        tool_count_before = len(agent.tools)
        agent._ensure_spawn_agent_tool()

        assert not any(t.name == 'spawn_agent' for t in agent.tools)
        assert len(agent.tools) == tool_count_before


class TestReloadToolsPreservesSpawnAgent:
    """测试 reload_tools() 保留 spawn_agent"""

    def test_reload_tools_preserves_spawn_agent(self):
        agent = _create_agent(role_config=None)
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        new_tool_registry = ToolRegistry()

        @tool
        def another_tool(query: str) -> str:
            """Another tool"""
            return f"another: {query}"

        new_tool_registry.register(another_tool)

        agent.reload_tools(new_tool_registry)

        tool_names = [t.name for t in agent.tools]
        assert 'spawn_agent' in tool_names
        assert 'another_tool' in tool_names

    def test_reload_tools_with_same_recursion_limit_preserves_spawn_agent(self):
        role_config = RoleConfig(
            name='test-role',
            description='test',
            system_prompt_file='prompts/test.txt',
            execution=RoleExecutionConfig(
                sub_agent_recursion_limit=500
            )
        )
        agent = _create_agent(role_config=role_config)
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        new_tool_registry = ToolRegistry()

        @tool
        def reload_tool(query: str) -> str:
            """Reload tool"""
            return f"reload: {query}"

        new_tool_registry.register(reload_tool)

        new_role_config = RoleConfig(
            name='test-role-2',
            description='test 2',
            system_prompt_file='prompts/test2.txt',
            execution=RoleExecutionConfig(
                sub_agent_recursion_limit=500
            )
        )
        agent.role_config = new_role_config

        agent.reload_tools(new_tool_registry)

        tool_names = [t.name for t in agent.tools]
        assert 'spawn_agent' in tool_names


class TestMultipleRoleSwitches:
    """测试多次角色切换 spawn_agent 一致性"""

    def test_multiple_role_switches_spawn_agent_consistency(self):
        agent = _create_agent(role_config=None)
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        role_enabled = RoleConfig(
            name='enabled-role',
            description='enabled',
            system_prompt_file='prompts/enabled.txt',
            tools=RoleToolsConfig(builtin={"spawn_agent": True})
        )
        agent.role_config = role_enabled
        agent._ensure_spawn_agent_tool()
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        role_disabled = RoleConfig(
            name='disabled-role',
            description='disabled',
            system_prompt_file='prompts/disabled.txt',
            tools=RoleToolsConfig(builtin={"spawn_agent": False})
        )
        agent.role_config = role_disabled
        agent._ensure_spawn_agent_tool()
        assert not any(t.name == 'spawn_agent' for t in agent.tools)

        agent.role_config = role_enabled
        agent._ensure_spawn_agent_tool()
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        role_no_config = RoleConfig(
            name='no-config-role',
            description='no config',
            system_prompt_file='prompts/noconfig.txt'
        )
        agent.role_config = role_no_config
        agent._ensure_spawn_agent_tool()
        assert any(t.name == 'spawn_agent' for t in agent.tools)

        agent.role_config = role_disabled
        agent._ensure_spawn_agent_tool()
        assert not any(t.name == 'spawn_agent' for t in agent.tools)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
