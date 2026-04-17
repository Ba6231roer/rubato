import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from langchain_core.tools import BaseTool

from src.core.sub_agents import (
    SubAgentManager,
    ToolPermissionResolver,
    ConfigInheritanceResolver,
)
from src.core.sub_agent_types import (
    ToolInheritanceMode,
    SubAgentState,
    ToolPermissionConfig,
    SubAgentDefinition,
    SubAgentExecutionConfig,
    SubAgentModelConfig,
    SubAgentSpawnOptions,
)


def _make_mock_tool(name="test_tool"):
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    tool.description = f"A {name} tool"
    return tool


def _make_mock_tool_registry(tools=None):
    registry = MagicMock()
    if tools:
        registry.get_tools_by_names.return_value = tools
        registry.get_tool.side_effect = lambda n: next(
            (t for t in tools if t.name == n), None
        )
    else:
        registry.get_tools_by_names.return_value = []
        registry.get_tool.return_value = None
    return registry


class TestIsKnownAgent:
    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_known_from_definitions(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager.agent_definitions["known-agent"] = MagicMock()

        assert manager._is_known_agent("known-agent") is True

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_known_from_roles_dir(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
            roles_dir="config/roles",
        )
        manager.agent_definitions = {}

        with patch.object(Path, 'exists', return_value=True):
            assert manager._is_known_agent("some-role") is True

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_unknown_agent(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
            roles_dir="/nonexistent/roles",
        )
        manager.agent_definitions = {}

        assert manager._is_known_agent("unknown-agent") is False

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_underscore_hyphen_variant(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
            roles_dir="/some/dir",
        )
        manager.agent_definitions = {}

        result = manager._is_known_agent("my-agent")
        assert result is False


class TestFilterSpawnAgentByDepth:
    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_no_session_id_returns_all(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        tools = [_make_mock_tool("spawn_agent"), _make_mock_tool("other")]
        result = manager._filter_spawn_agent_by_depth(tools, None, 5)
        assert len(result) == 2

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_filters_spawn_agent_at_max_depth(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._session_depths["session-1"] = 5

        tools = [_make_mock_tool("spawn_agent"), _make_mock_tool("other")]
        result = manager._filter_spawn_agent_by_depth(tools, "session-1", 5)
        assert len(result) == 1
        assert result[0].name == "other"

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_keeps_spawn_agent_below_max_depth(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._session_depths["session-1"] = 3

        tools = [_make_mock_tool("spawn_agent"), _make_mock_tool("other")]
        result = manager._filter_spawn_agent_by_depth(tools, "session-1", 5)
        assert len(result) == 2


class TestRecursionDepth:
    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_check_recursion_depth_below_limit(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._session_depths["session-1"] = 2
        assert manager.check_recursion_depth("session-1", 5) is True

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_check_recursion_depth_at_limit(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._session_depths["session-1"] = 5
        assert manager.check_recursion_depth("session-1", 5) is False

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_check_recursion_depth_unknown_session(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        assert manager.check_recursion_depth("unknown", 5) is True

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_increment_depth(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager.increment_depth("session-1")
        assert manager._session_depths["session-1"] == 1
        manager.increment_depth("session-1")
        assert manager._session_depths["session-1"] == 2

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_decrement_depth(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._session_depths["session-1"] = 2
        manager.decrement_depth("session-1")
        assert manager._session_depths["session-1"] == 1

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_decrement_depth_removes_at_zero(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._session_depths["session-1"] = 1
        manager.decrement_depth("session-1")
        assert "session-1" not in manager._session_depths

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_decrement_depth_no_negative(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager.decrement_depth("session-1")
        assert manager._session_depths.get("session-1", 0) == 0

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_get_current_depth(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        assert manager.get_current_depth("session-1") == 0
        manager._session_depths["session-1"] = 3
        assert manager.get_current_depth("session-1") == 3


class TestToolPermissionResolver:
    def test_inherit_all(self):
        tool1 = _make_mock_tool("tool1")
        tool2 = _make_mock_tool("tool2")
        parent_tools = [tool1, tool2]
        permissions = ToolPermissionConfig()
        registry = _make_mock_tool_registry()

        result = ToolPermissionResolver.resolve(
            parent_tools=parent_tools,
            permissions=permissions,
            tool_registry=registry,
            tool_inheritance=ToolInheritanceMode.INHERIT_ALL,
        )
        assert len(result) == 2
        assert result[0].name == "tool1"
        assert result[1].name == "tool2"

    def test_independent_with_available_tools(self):
        tool1 = _make_mock_tool("tool1")
        registry = _make_mock_tool_registry([tool1])

        result = ToolPermissionResolver.resolve(
            parent_tools=[_make_mock_tool("parent_tool")],
            permissions=ToolPermissionConfig(),
            tool_registry=registry,
            available_tools=["tool1"],
            tool_inheritance=ToolInheritanceMode.INDEPENDENT,
        )
        assert len(result) == 1
        assert result[0].name == "tool1"

    def test_independent_without_available_tools(self):
        registry = _make_mock_tool_registry()

        result = ToolPermissionResolver.resolve(
            parent_tools=[_make_mock_tool("parent_tool")],
            permissions=ToolPermissionConfig(),
            tool_registry=registry,
            tool_inheritance=ToolInheritanceMode.INDEPENDENT,
        )
        assert result == []

    def test_inherit_selected_with_available_tools(self):
        tool1 = _make_mock_tool("tool1")
        registry = _make_mock_tool_registry([tool1])

        result = ToolPermissionResolver.resolve(
            parent_tools=[_make_mock_tool("parent_tool")],
            permissions=ToolPermissionConfig(),
            tool_registry=registry,
            available_tools=["tool1"],
            tool_inheritance=ToolInheritanceMode.INHERIT_SELECTED,
        )
        assert len(result) == 1
        assert result[0].name == "tool1"

    def test_inherit_selected_without_available_tools(self):
        parent_tools = [_make_mock_tool("tool1"), _make_mock_tool("tool2")]
        registry = _make_mock_tool_registry()

        result = ToolPermissionResolver.resolve(
            parent_tools=parent_tools,
            permissions=ToolPermissionConfig(),
            tool_registry=registry,
            tool_inheritance=ToolInheritanceMode.INHERIT_SELECTED,
        )
        assert len(result) == 2

    def test_allowlist_filtering(self):
        tool1 = _make_mock_tool("tool1")
        tool2 = _make_mock_tool("tool2")
        parent_tools = [tool1, tool2]
        permissions = ToolPermissionConfig(allowlist=["tool1"])
        registry = _make_mock_tool_registry()

        result = ToolPermissionResolver.resolve(
            parent_tools=parent_tools,
            permissions=permissions,
            tool_registry=registry,
            tool_inheritance=ToolInheritanceMode.INHERIT_ALL,
        )
        names = [t.name for t in result]
        assert "tool1" in names

    def test_denylist_filtering(self):
        tool1 = _make_mock_tool("tool1")
        tool2 = _make_mock_tool("tool2")
        parent_tools = [tool1, tool2]
        permissions = ToolPermissionConfig(denylist=["tool2"])
        registry = _make_mock_tool_registry()

        result = ToolPermissionResolver.resolve(
            parent_tools=parent_tools,
            permissions=permissions,
            tool_registry=registry,
            tool_inheritance=ToolInheritanceMode.INHERIT_ALL,
        )
        names = [t.name for t in result]
        assert "tool1" in names
        assert "tool2" not in names

    def test_allowlist_adds_from_registry(self):
        tool1 = _make_mock_tool("tool1")
        tool_from_registry = _make_mock_tool("registry_tool")
        parent_tools = [tool1]
        permissions = ToolPermissionConfig(allowlist=["tool1", "registry_tool"])
        registry = _make_mock_tool_registry([tool_from_registry])

        result = ToolPermissionResolver.resolve(
            parent_tools=parent_tools,
            permissions=permissions,
            tool_registry=registry,
            tool_inheritance=ToolInheritanceMode.INHERIT_ALL,
        )
        names = [t.name for t in result]
        assert "registry_tool" in names

    def test_none_inheritance_defaults_to_inherit_selected(self):
        parent_tools = [_make_mock_tool("tool1")]
        permissions = ToolPermissionConfig()
        registry = _make_mock_tool_registry()

        result = ToolPermissionResolver.resolve(
            parent_tools=parent_tools,
            permissions=permissions,
            tool_registry=registry,
            tool_inheritance=None,
        )
        assert len(result) == 1


class TestConfigInheritanceResolver:
    def test_no_inherit(self):
        sub_config = SubAgentModelConfig(
            inherit=False,
            provider="anthropic",
            name="claude-3",
            api_key="key",
            base_url="https://api.anthropic.com",
            temperature=0.5,
            max_tokens=8000,
            auth="Bearer token",
        )
        parent_config = MagicMock()

        result = ConfigInheritanceResolver.resolve_model_config(
            parent_config, sub_config
        )
        assert result["provider"] == "anthropic"
        assert result["name"] == "claude-3"
        assert result["temperature"] == 0.5
        assert result["max_tokens"] == 8000

    def test_inherit_from_parent(self):
        parent_config = MagicMock()
        parent_config.provider = "openai"
        parent_config.name = "gpt-4"
        parent_config.api_key = "parent-key"
        parent_config.base_url = "https://api.openai.com"
        parent_config.temperature = 0.7
        parent_config.max_tokens = 4000
        parent_config.auth = None

        sub_config = SubAgentModelConfig(inherit=True)

        result = ConfigInheritanceResolver.resolve_model_config(
            parent_config, sub_config
        )
        assert result["provider"] == "openai"
        assert result["name"] == "gpt-4"
        assert result["api_key"] == "parent-key"

    def test_inherit_with_overrides(self):
        parent_config = MagicMock()
        parent_config.provider = "openai"
        parent_config.name = "gpt-4"
        parent_config.api_key = "parent-key"
        parent_config.base_url = "https://api.openai.com"
        parent_config.temperature = 0.7
        parent_config.max_tokens = 4000
        parent_config.auth = None

        sub_config = SubAgentModelConfig(
            inherit=True,
            name="gpt-3.5-turbo",
            temperature=0.3,
        )

        result = ConfigInheritanceResolver.resolve_model_config(
            parent_config, sub_config
        )
        assert result["provider"] == "openai"
        assert result["name"] == "gpt-3.5-turbo"
        assert result["temperature"] == 0.3
        assert result["max_tokens"] == 4000

    def test_inherit_parent_missing_attributes(self):
        parent_config = MagicMock(spec=[])
        sub_config = SubAgentModelConfig(inherit=True)

        result = ConfigInheritanceResolver.resolve_model_config(
            parent_config, sub_config
        )
        assert result["provider"] is None
        assert result["name"] is None


class TestSubAgentManagerSpawnAgent:
    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_spawn_agent_recursion_limit(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._session_depths["session-1"] = 5

        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Do something",
            session_id="session-1",
            max_recursion_depth=5,
        )
        result = asyncio_run(manager.spawn_agent(options))
        assert "递归深度限制" in result

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_spawn_agent_known_role(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager.agent_definitions["known-agent"] = SubAgentDefinition(
            name="known-agent",
            system_prompt="Known agent prompt",
        )
        manager._create_sub_agent_by_role = AsyncMock(return_value="result from role")

        options = SubAgentSpawnOptions(
            agent_name="known-agent",
            task="Do something",
        )
        result = asyncio_run(manager.spawn_agent(options))
        assert result == "result from role"

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_spawn_agent_dynamic_with_prompt(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._create_dynamic_sub_agent = AsyncMock(return_value="dynamic result")

        options = SubAgentSpawnOptions(
            agent_name="custom-agent",
            task="Do something",
            system_prompt="Custom prompt",
        )
        result = asyncio_run(manager.spawn_agent(options))
        assert result == "dynamic result"

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_spawn_agent_depth_increment_decrement(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._create_sub_agent_by_role = AsyncMock(return_value="ok")

        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Do something",
            session_id="session-1",
            max_recursion_depth=5,
        )
        asyncio_run(manager.spawn_agent(options))
        assert manager.get_current_depth("session-1") == 0

    @patch("src.core.sub_agents.SubAgentLifecycleManager")
    @patch("src.core.sub_agents.get_llm_logger")
    def test_spawn_agent_error_handling(self, mock_logger, mock_lifecycle):
        mock_lifecycle.return_value = MagicMock()
        manager = SubAgentManager(
            llm=MagicMock(),
            parent_agent=MagicMock(),
            sub_agents_dir="nonexistent",
        )
        manager._create_sub_agent_by_role = AsyncMock(side_effect=Exception("boom"))

        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Do something",
        )
        result = asyncio_run(manager.spawn_agent(options))
        assert "执行失败" in result


def asyncio_run(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)
