"""
SubAgent 机制单元测试

测试 SubAgent 定义、生命周期管理和管理器的核心功能。
"""

import asyncio
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from langchain_core.tools import BaseTool, tool


from src.core.sub_agent_types import (
    ToolInheritanceMode,
    SubAgentState,
    ToolPermissionConfig,
    SubAgentExecutionConfig,
    SubAgentModelConfig,
    SubAgentDefinition,
    SubAgentInstance,
    SubAgentSpawnOptions,
)
from src.core.sub_agent_lifecycle import SubAgentLifecycleManager
from src.core.sub_agents import (
    SubAgentManager,
    ToolPermissionResolver,
    ConfigInheritanceResolver,
    create_spawn_agent_tool,
)


class TestToolInheritanceMode:
    """测试工具继承模式枚举"""
    
    def test_inheritance_modes_exist(self):
        """测试所有继承模式都存在"""
        assert ToolInheritanceMode.INHERIT_ALL == "inherit_all"
        assert ToolInheritanceMode.INHERIT_SELECTED == "inherit_selected"
        assert ToolInheritanceMode.INDEPENDENT == "independent"
    
    def test_inheritance_mode_values(self):
        """测试继承模式值"""
        modes = [mode.value for mode in ToolInheritanceMode]
        assert "inherit_all" in modes
        assert "inherit_selected" in modes
        assert "independent" in modes


class TestSubAgentState:
    """测试 SubAgent 状态枚举"""
    
    def test_states_exist(self):
        """测试所有状态都存在"""
        assert SubAgentState.CREATED == "created"
        assert SubAgentState.RUNNING == "running"
        assert SubAgentState.COMPLETED == "completed"
        assert SubAgentState.FAILED == "failed"
        assert SubAgentState.TIMEOUT == "timeout"
        assert SubAgentState.CANCELLED == "cancelled"


class TestToolPermissionConfig:
    """测试工具权限配置"""
    
    def test_default_values(self):
        """测试默认值"""
        config = ToolPermissionConfig()
        assert config.inherit_from_parent is True
        assert config.allowlist is None
        assert config.denylist is None
        assert config.custom_permissions == {}
    
    def test_custom_values(self):
        """测试自定义值"""
        config = ToolPermissionConfig(
            inherit_from_parent=False,
            allowlist=["tool1", "tool2"],
            denylist=["tool3"],
            custom_permissions={"tool4": "ask"}
        )
        assert config.inherit_from_parent is False
        assert config.allowlist == ["tool1", "tool2"]
        assert config.denylist == ["tool3"]
        assert config.custom_permissions == {"tool4": "ask"}


class TestSubAgentExecutionConfig:
    """测试 SubAgent 执行配置"""
    
    def test_default_values(self):
        """测试默认值"""
        config = SubAgentExecutionConfig()
        assert config.timeout == 120
        assert config.max_retries == 0
        assert config.recursion_limit == 50
        assert config.max_context_tokens is None
        assert config.use_query_engine is False
    
    def test_custom_values(self):
        """测试自定义值"""
        config = SubAgentExecutionConfig(
            timeout=300,
            max_retries=3,
            recursion_limit=100,
            max_context_tokens=50000,
            use_query_engine=True
        )
        assert config.timeout == 300
        assert config.max_retries == 3
        assert config.recursion_limit == 100
        assert config.max_context_tokens == 50000
        assert config.use_query_engine is True


class TestSubAgentModelConfig:
    """测试 SubAgent 模型配置"""
    
    def test_default_values(self):
        """测试默认值"""
        config = SubAgentModelConfig()
        assert config.inherit is True
        assert config.provider is None
        assert config.name is None
        assert config.temperature is None
        assert config.max_tokens is None
    
    def test_custom_values(self):
        """测试自定义值"""
        config = SubAgentModelConfig(
            inherit=False,
            provider="openai",
            name="gpt-4",
            temperature=0.5,
            max_tokens=4000
        )
        assert config.inherit is False
        assert config.provider == "openai"
        assert config.name == "gpt-4"
        assert config.temperature == 0.5
        assert config.max_tokens == 4000
    
    def test_temperature_validation(self):
        """测试温度参数验证"""
        with pytest.raises(ValueError):
            SubAgentModelConfig(temperature=1.5)
        
        with pytest.raises(ValueError):
            SubAgentModelConfig(temperature=-0.1)


class TestSubAgentDefinition:
    """测试 SubAgent 定义"""
    
    def test_minimal_definition(self):
        """测试最小定义"""
        definition = SubAgentDefinition(name="test-agent")
        assert definition.name == "test-agent"
        assert definition.description == ""
        assert definition.version == "1.0"
        assert definition.system_prompt is None
        assert definition.system_prompt_file is None
        assert definition.tool_inheritance == ToolInheritanceMode.INHERIT_ALL
    
    def test_full_definition(self):
        """测试完整定义"""
        definition = SubAgentDefinition(
            name="test-agent",
            description="Test agent description",
            version="2.0",
            system_prompt="You are a test agent.",
            model=SubAgentModelConfig(inherit=False, name="gpt-4"),
            execution=SubAgentExecutionConfig(timeout=60),
            tool_inheritance=ToolInheritanceMode.INDEPENDENT,
            available_tools=["tool1", "tool2"],
            metadata={"author": "test"}
        )
        assert definition.name == "test-agent"
        assert definition.description == "Test agent description"
        assert definition.version == "2.0"
        assert definition.system_prompt == "You are a test agent."
        assert definition.tool_inheritance == ToolInheritanceMode.INDEPENDENT
        assert definition.available_tools == ["tool1", "tool2"]
    
    def test_get_system_prompt_content_inline(self):
        """测试获取内联系统提示词"""
        definition = SubAgentDefinition(
            name="test-agent",
            system_prompt="Inline prompt"
        )
        assert definition.get_system_prompt_content() == "Inline prompt"
    
    def test_get_system_prompt_content_default(self):
        """测试获取默认系统提示词"""
        definition = SubAgentDefinition(name="test-agent")
        prompt = definition.get_system_prompt_content()
        assert "test-agent" in prompt
        assert "子智能体" in prompt


class TestSubAgentInstance:
    """测试 SubAgent 实例"""
    
    def test_create_instance(self):
        """测试创建实例"""
        definition = SubAgentDefinition(name="test-agent")
        instance = SubAgentInstance(
            instance_id="test-id",
            name="test-agent",
            definition=definition,
            task="Test task"
        )
        assert instance.instance_id == "test-id"
        assert instance.name == "test-agent"
        assert instance.state == SubAgentState.CREATED
        assert instance.task == "Test task"
        assert instance.result is None
        assert instance.error is None
        assert instance.depth == 0
    
    def test_instance_state_transitions(self):
        """测试实例状态转换"""
        definition = SubAgentDefinition(name="test-agent")
        instance = SubAgentInstance(
            instance_id="test-id",
            name="test-agent",
            definition=definition,
            task="Test task"
        )
        
        assert instance.state == SubAgentState.CREATED
        
        instance.state = SubAgentState.RUNNING
        assert instance.state == SubAgentState.RUNNING
        
        instance.state = SubAgentState.COMPLETED
        assert instance.state == SubAgentState.COMPLETED


class TestSubAgentSpawnOptions:
    """测试 SubAgent 创建选项"""
    
    def test_minimal_options(self):
        """测试最小选项"""
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Test task"
        )
        assert options.agent_name == "test-agent"
        assert options.task == "Test task"
        assert options.inherit_parent_tools is True
        assert options.max_recursion_depth == 5
    
    def test_full_options(self):
        """测试完整选项"""
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Test task",
            system_prompt="Custom prompt",
            inherit_parent_tools=False,
            session_id="session-123",
            max_recursion_depth=3,
            timeout=60,
            use_query_engine=True,
            tool_inheritance=ToolInheritanceMode.INDEPENDENT,
            available_tools=["tool1"]
        )
        assert options.system_prompt == "Custom prompt"
        assert options.inherit_parent_tools is False
        assert options.session_id == "session-123"
        assert options.max_recursion_depth == 3
        assert options.timeout == 60
        assert options.use_query_engine is True


class TestSubAgentLifecycleManager:
    """测试 SubAgent 生命周期管理器"""
    
    @pytest.fixture
    def lifecycle_manager(self):
        """创建生命周期管理器"""
        return SubAgentLifecycleManager(max_concurrent=5)
    
    @pytest.fixture
    def sample_definition(self):
        """创建示例定义"""
        return SubAgentDefinition(
            name="test-agent",
            execution=SubAgentExecutionConfig(timeout=10)
        )
    
    @pytest.mark.asyncio
    async def test_create_instance(self, lifecycle_manager, sample_definition):
        """测试创建实例"""
        instance = await lifecycle_manager.create_instance(
            name="test-agent",
            definition=sample_definition,
            task="Test task"
        )
        
        assert instance.name == "test-agent"
        assert instance.state == SubAgentState.CREATED
        assert instance.task == "Test task"
        assert instance.instance_id is not None
    
    @pytest.mark.asyncio
    async def test_start_instance_success(self, lifecycle_manager, sample_definition):
        """测试成功启动实例"""
        instance = await lifecycle_manager.create_instance(
            name="test-agent",
            definition=sample_definition,
            task="Test task"
        )
        
        async def executor():
            await asyncio.sleep(0.1)
            return "Success result"
        
        result = await lifecycle_manager.start_instance(instance, executor)
        
        assert result == "Success result"
        assert instance.state == SubAgentState.COMPLETED
        assert instance.result == "Success result"
    
    @pytest.mark.asyncio
    async def test_start_instance_timeout(self, lifecycle_manager):
        """测试实例超时"""
        definition = SubAgentDefinition(
            name="test-agent",
            execution=SubAgentExecutionConfig(timeout=0.1)
        )
        
        instance = await lifecycle_manager.create_instance(
            name="test-agent",
            definition=definition,
            task="Test task"
        )
        
        async def executor():
            await asyncio.sleep(1)
            return "Should not reach"
        
        with pytest.raises(TimeoutError):
            await lifecycle_manager.start_instance(instance, executor)
        
        assert instance.state == SubAgentState.TIMEOUT
        assert "超时" in instance.error
    
    @pytest.mark.asyncio
    async def test_start_instance_failure(self, lifecycle_manager):
        """测试实例失败"""
        definition = SubAgentDefinition(
            name="test-agent",
            execution=SubAgentExecutionConfig(timeout=60)
        )
        
        instance = await lifecycle_manager.create_instance(
            name="test-agent",
            definition=definition,
            task="Test task"
        )
        
        async def executor():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await lifecycle_manager.start_instance(instance, executor)
        
        assert instance.state == SubAgentState.FAILED
        assert "Test error" in instance.error
    
    @pytest.mark.asyncio
    async def test_destroy_instance(self, lifecycle_manager, sample_definition):
        """测试销毁实例"""
        instance = await lifecycle_manager.create_instance(
            name="test-agent",
            definition=sample_definition,
            task="Test task"
        )
        
        assert lifecycle_manager.get_instance(instance.instance_id) is not None
        
        destroyed = await lifecycle_manager.destroy_instance(instance.instance_id)
        assert destroyed is True
        assert lifecycle_manager.get_instance(instance.instance_id) is None
    
    def test_get_statistics(self, lifecycle_manager):
        """测试获取统计信息"""
        stats = lifecycle_manager.get_statistics()
        
        assert "total_instances" in stats
        assert "by_state" in stats
        assert "max_concurrent" in stats
        assert stats["max_concurrent"] == 5
    
    def test_callback_registration(self, lifecycle_manager):
        """测试回调注册"""
        created_instances = []
        
        def on_created(instance):
            created_instances.append(instance)
        
        lifecycle_manager.on_created(on_created)
        assert len(lifecycle_manager._on_created) == 1
        
        started_instances = []
        lifecycle_manager.on_started(lambda i: started_instances.append(i))
        assert len(lifecycle_manager._on_started) == 1
        
        completed_instances = []
        lifecycle_manager.on_completed(lambda i: completed_instances.append(i))
        assert len(lifecycle_manager._on_completed) == 1
        
        failed_instances = []
        lifecycle_manager.on_failed(lambda i: failed_instances.append(i))
        assert len(lifecycle_manager._on_failed) == 1


class TestToolPermissionResolver:
    """测试工具权限解析器"""
    
    def create_mock_tool(self, name: str) -> BaseTool:
        """创建模拟工具"""
        from langchain_core.tools import StructuredTool
        
        def mock_func() -> str:
            return "mock"
        
        mock_tool = StructuredTool(
            name=name,
            description="Mock tool",
            func=mock_func
        )
        return mock_tool
    
    def test_inherit_all_tools(self):
        """测试继承所有工具"""
        tools = [
            self.create_mock_tool("tool1"),
            self.create_mock_tool("tool2"),
            self.create_mock_tool("tool3")
        ]
        
        permissions = ToolPermissionConfig(inherit_from_parent=True)
        tool_registry = MagicMock()
        
        result = ToolPermissionResolver.resolve(tools, permissions, tool_registry)
        
        assert len(result) == 3
        assert [t.name for t in result] == ["tool1", "tool2", "tool3"]
    
    def test_allowlist_filter(self):
        """测试白名单过滤"""
        tools = [
            self.create_mock_tool("tool1"),
            self.create_mock_tool("tool2"),
            self.create_mock_tool("tool3")
        ]
        
        permissions = ToolPermissionConfig(
            inherit_from_parent=True,
            allowlist=["tool1", "tool3"]
        )
        tool_registry = MagicMock()
        
        result = ToolPermissionResolver.resolve(tools, permissions, tool_registry)
        
        assert len(result) == 2
        assert [t.name for t in result] == ["tool1", "tool3"]
    
    def test_denylist_filter(self):
        """测试黑名单过滤"""
        tools = [
            self.create_mock_tool("tool1"),
            self.create_mock_tool("tool2"),
            self.create_mock_tool("tool3")
        ]
        
        permissions = ToolPermissionConfig(
            inherit_from_parent=True,
            denylist=["tool2"]
        )
        tool_registry = MagicMock()
        
        result = ToolPermissionResolver.resolve(tools, permissions, tool_registry)
        
        assert len(result) == 2
        assert [t.name for t in result] == ["tool1", "tool3"]
    
    def test_available_tools_override(self):
        """测试可用工具覆盖"""
        tools = [
            self.create_mock_tool("tool1"),
            self.create_mock_tool("tool2")
        ]
        
        mock_tool3 = self.create_mock_tool("tool3")
        tool_registry = MagicMock()
        tool_registry.get_tools_by_names.return_value = [mock_tool3]
        
        permissions = ToolPermissionConfig(inherit_from_parent=False)
        
        result = ToolPermissionResolver.resolve(
            tools, permissions, tool_registry, available_tools=["tool3"]
        )
        
        assert len(result) == 1
        assert result[0].name == "tool3"


class TestConfigInheritanceResolver:
    """测试配置继承解析器"""
    
    def test_inherit_parent_config(self):
        """测试继承父配置"""
        parent_config = MagicMock()
        parent_config.provider = "openai"
        parent_config.name = "gpt-4"
        parent_config.api_key = "test-key"
        parent_config.base_url = "https://api.openai.com"
        parent_config.temperature = 0.7
        parent_config.max_tokens = 2000
        
        sub_agent_config = SubAgentModelConfig(inherit=True)
        
        result = ConfigInheritanceResolver.resolve_model_config(
            parent_config, sub_agent_config
        )
        
        assert result["provider"] == "openai"
        assert result["name"] == "gpt-4"
        assert result["api_key"] == "test-key"
    
    def test_override_parent_config(self):
        """测试覆盖父配置"""
        parent_config = MagicMock()
        parent_config.provider = "openai"
        parent_config.name = "gpt-4"
        parent_config.temperature = 0.7
        
        sub_agent_config = SubAgentModelConfig(
            inherit=True,
            temperature=0.5,
            max_tokens=4000
        )
        
        result = ConfigInheritanceResolver.resolve_model_config(
            parent_config, sub_agent_config
        )
        
        assert result["provider"] == "openai"
        assert result["name"] == "gpt-4"
        assert result["temperature"] == 0.5
        assert result["max_tokens"] == 4000
    
    def test_no_inherit(self):
        """测试不继承"""
        parent_config = MagicMock()
        parent_config.name = "gpt-4"
        
        sub_agent_config = SubAgentModelConfig(
            inherit=False,
            provider="anthropic",
            name="claude-3"
        )
        
        result = ConfigInheritanceResolver.resolve_model_config(
            parent_config, sub_agent_config
        )
        
        assert result["provider"] == "anthropic"
        assert result["name"] == "claude-3"


class TestSubAgentManager:
    """测试 SubAgent 管理器"""
    
    @pytest.fixture
    def mock_llm(self):
        """创建模拟 LLM"""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response"))
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
    
    def test_initialization(self, sub_agent_manager):
        """测试初始化"""
        assert sub_agent_manager.recursion_limit == 50
        assert isinstance(sub_agent_manager.agent_definitions, dict)
        assert isinstance(sub_agent_manager._lifecycle_manager, SubAgentLifecycleManager)
    
    def test_list_agents(self, sub_agent_manager):
        """测试列出 Agents"""
        agents = sub_agent_manager.list_agents()
        assert isinstance(agents, list)
    
    def test_check_recursion_depth(self, sub_agent_manager):
        """测试递归深度检查"""
        session_id = "test-session"
        
        assert sub_agent_manager.check_recursion_depth(session_id, 5) is True
        
        sub_agent_manager.increment_depth(session_id)
        assert sub_agent_manager.get_current_depth(session_id) == 1
        
        for _ in range(4):
            sub_agent_manager.increment_depth(session_id)
        
        assert sub_agent_manager.check_recursion_depth(session_id, 5) is False
    
    def test_increment_decrement_depth(self, sub_agent_manager):
        """测试递归深度增减"""
        session_id = "test-session"
        
        sub_agent_manager.increment_depth(session_id)
        assert sub_agent_manager.get_current_depth(session_id) == 1
        
        sub_agent_manager.increment_depth(session_id)
        assert sub_agent_manager.get_current_depth(session_id) == 2
        
        sub_agent_manager.decrement_depth(session_id)
        assert sub_agent_manager.get_current_depth(session_id) == 1
        
        sub_agent_manager.decrement_depth(session_id)
        assert sub_agent_manager.get_current_depth(session_id) == 0
        assert session_id not in sub_agent_manager._session_depths
    
    def test_get_statistics(self, sub_agent_manager):
        """测试获取统计信息"""
        stats = sub_agent_manager.get_statistics()
        
        assert "predefined_agents" in stats
        assert "active_sessions" in stats
        assert "lifecycle_stats" in stats
    
    def test_is_known_agent_predefined(self, sub_agent_manager):
        """测试 _is_known_agent 匹配预定义 SubAgent"""
        sub_agent_manager.agent_definitions["predefined-agent"] = SubAgentDefinition(
            name="predefined-agent"
        )
        assert sub_agent_manager._is_known_agent("predefined-agent") is True
    
    def test_is_known_agent_role_config(self, sub_agent_manager, tmp_path):
        """测试 _is_known_agent 匹配角色配置文件"""
        sub_agent_manager.roles_dir = tmp_path
        (tmp_path / "my-role.yaml").write_text("name: my-role", encoding="utf-8")
        assert sub_agent_manager._is_known_agent("my-role") is True
    
    def test_is_known_agent_role_config_hyphen_underscore(self, sub_agent_manager, tmp_path):
        """测试 _is_known_agent 角色名连字符/下划线变体匹配"""
        sub_agent_manager.roles_dir = tmp_path
        (tmp_path / "bs_ui_kb_curator.yaml").write_text("name: bs-ui-kb-curator", encoding="utf-8")
        assert sub_agent_manager._is_known_agent("bs-ui-kb-curator") is True
    
    def test_is_known_agent_unknown(self, sub_agent_manager):
        """测试 _is_known_agent 不匹配未知名称"""
        assert sub_agent_manager._is_known_agent("unknown-agent-xyz") is False
    
    @pytest.mark.asyncio
    async def test_spawn_agent_known_role_ignores_system_prompt(self, sub_agent_manager):
        """测试已知角色名时忽略 LLM 传入的 system_prompt"""
        sub_agent_manager.agent_definitions["known-role"] = SubAgentDefinition(
            name="known-role",
            system_prompt="Role config prompt"
        )
        
        with patch.object(sub_agent_manager, '_create_sub_agent_by_role', new_callable=AsyncMock, return_value="role result") as mock_role, \
             patch.object(sub_agent_manager, '_create_dynamic_sub_agent', new_callable=AsyncMock, return_value="dynamic result") as mock_dynamic:
            
            options = SubAgentSpawnOptions(
                agent_name="known-role",
                task="Test task",
                system_prompt="LLM generated prompt"
            )
            
            result = await sub_agent_manager.spawn_agent(options)
            
            assert result == "role result"
            mock_role.assert_called_once()
            mock_dynamic.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_spawn_agent_unknown_with_system_prompt_uses_dynamic(self, sub_agent_manager):
        """测试未知角色名 + 有 system_prompt 时走动态创建"""
        with patch.object(sub_agent_manager, '_create_sub_agent_by_role', new_callable=AsyncMock, return_value="role result") as mock_role, \
             patch.object(sub_agent_manager, '_create_dynamic_sub_agent', new_callable=AsyncMock, return_value="dynamic result") as mock_dynamic:
            
            options = SubAgentSpawnOptions(
                agent_name="custom-agent-xyz",
                task="Test task",
                system_prompt="Custom prompt"
            )
            
            result = await sub_agent_manager.spawn_agent(options)
            
            assert result == "dynamic result"
            mock_dynamic.assert_called_once()
            mock_role.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_spawn_agent_unknown_without_system_prompt_uses_role(self, sub_agent_manager):
        """测试未知角色名 + 无 system_prompt 时走角色路径（回退默认）"""
        with patch.object(sub_agent_manager, '_create_sub_agent_by_role', new_callable=AsyncMock, return_value="role result") as mock_role, \
             patch.object(sub_agent_manager, '_create_dynamic_sub_agent', new_callable=AsyncMock, return_value="dynamic result") as mock_dynamic:
            
            options = SubAgentSpawnOptions(
                agent_name="custom-agent-xyz",
                task="Test task"
            )
            
            result = await sub_agent_manager.spawn_agent(options)
            
            assert result == "role result"
            mock_role.assert_called_once()
            mock_dynamic.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_spawn_agent_recursion_limit(self, sub_agent_manager):
        """测试递归深度限制"""
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


class TestCreateSpawnAgentTool:
    """测试创建 spawn_agent 工具"""
    
    @pytest.fixture
    def mock_llm(self):
        """创建模拟 LLM"""
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response"))
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
    
    def test_tool_creation(self, sub_agent_manager):
        """测试工具创建"""
        spawn_tool = create_spawn_agent_tool(sub_agent_manager)
        
        assert spawn_tool is not None
        assert hasattr(spawn_tool, "name")
        assert spawn_tool.name == "spawn_agent"
    
    def test_tool_description(self, sub_agent_manager):
        """测试工具描述"""
        spawn_tool = create_spawn_agent_tool(sub_agent_manager)
        
        assert spawn_tool.description is not None
        assert "子智能体" in spawn_tool.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
