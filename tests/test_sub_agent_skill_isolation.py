"""
验证 SubAgent 的 LLMCaller 状态隔离：
- SubAgent 不应共享父 Agent 的 system_prompt_registry
- SubAgent 的系统提示词必须包含 skill 内容
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from src.core.sub_agents import SubAgentManager
from src.core.sub_agent_types import (
    SubAgentDefinition,
    SubAgentModelConfig,
    SubAgentExecutionConfig,
    ToolInheritanceMode,
)
from src.core.llm_wrapper import LLMCaller


def _make_parent_agent():
    parent_llm = LLMCaller(
        api_key="test-key",
        model="test-model",
        base_url="http://localhost:11434/v1",
    )
    parent_llm.system_prompt_registry = MagicMock()
    parent_llm.system_prompt_registry.build.return_value = "parent system prompt"

    parent_config = MagicMock()
    parent_config.model.model.name = "test-model"
    parent_config.model.model.api_key = "test-key"
    parent_config.model.model.base_url = "http://localhost:11434/v1"
    parent_config.model.model.temperature = 0.7
    parent_config.model.model.max_tokens = 80000
    parent_config.model.model.auth = None
    parent_config.model.parameters.retry_max_count = 3
    parent_config.model.parameters.retry_initial_delay = 10.0
    parent_config.model.parameters.retry_max_delay = 60.0
    parent_config.project.root = Path(".")

    parent_agent = MagicMock()
    parent_agent.config = parent_config
    parent_agent.llm = parent_llm
    parent_agent.tools = []
    parent_agent.tool_registry = MagicMock()
    parent_agent.tool_registry.get_all_tools.return_value = []
    parent_agent.tool_registry.get_tools_by_names.return_value = []
    parent_agent.tool_registry.get_tool.return_value = None
    parent_agent.get_role_name.return_value = "parent-role"
    parent_agent.skill_loader = None
    parent_agent.compression_config = MagicMock(enabled=False)

    return parent_agent


class TestSubAgentLLMIsolation:
    """验证 _create_llm 返回新实例，不共享父 Agent 的可变状态"""

    def test_create_llm_returns_new_instance(self):
        parent_agent = _make_parent_agent()
        manager = SubAgentManager(
            llm=parent_agent.llm,
            parent_agent=parent_agent,
            roles_dir="config/roles",
        )

        definition = SubAgentDefinition(
            name="test-sub",
            model=SubAgentModelConfig(inherit=True),
            execution=SubAgentExecutionConfig(),
        )

        sub_llm = manager._create_llm(definition)

        assert sub_llm is not parent_agent.llm, (
            "SubAgent _create_llm 不应返回父 Agent 的同一个 LLMCaller 实例"
        )

    def test_create_llm_new_instance_has_no_system_prompt_registry(self):
        parent_agent = _make_parent_agent()
        manager = SubAgentManager(
            llm=parent_agent.llm,
            parent_agent=parent_agent,
            roles_dir="config/roles",
        )

        definition = SubAgentDefinition(
            name="test-sub",
            model=SubAgentModelConfig(inherit=True),
            execution=SubAgentExecutionConfig(),
        )

        sub_llm = manager._create_llm(definition)

        assert sub_llm.system_prompt_registry is None, (
            "新 LLMCaller 实例不应继承父 Agent 的 system_prompt_registry"
        )

    def test_create_llm_inherits_model_params(self):
        parent_agent = _make_parent_agent()
        manager = SubAgentManager(
            llm=parent_agent.llm,
            parent_agent=parent_agent,
            roles_dir="config/roles",
        )

        definition = SubAgentDefinition(
            name="test-sub",
            model=SubAgentModelConfig(inherit=True),
            execution=SubAgentExecutionConfig(),
        )

        sub_llm = manager._create_llm(definition)

        assert sub_llm.model == "test-model"
        assert sub_llm.temperature == 0.7
        assert sub_llm.max_tokens == 80000


class TestQueryEngineSystemPromptIsolation:
    """验证 QueryEngine 初始化时显式覆盖 system_prompt_registry"""

    def test_query_engine_resets_system_prompt_registry(self):
        from src.core.query_engine import QueryEngine, QueryEngineConfig

        llm = LLMCaller(
            api_key="test-key",
            model="test-model",
            base_url="http://localhost:11434/v1",
        )
        parent_registry = MagicMock()
        parent_registry.build.return_value = "parent prompt should not be used"
        llm.system_prompt_registry = parent_registry

        config = QueryEngineConfig(
            cwd=".",
            llm=llm,
            tools=[],
            skills=[],
            can_use_tool=lambda n, a: True,
            get_app_state=lambda: {},
            set_app_state=lambda s: None,
            custom_system_prompt="sub-agent prompt with skill content",
            system_prompt_registry=None,
        )

        qe = QueryEngine(config)

        assert qe.llm_caller.system_prompt_registry is None, (
            "QueryEngine 应将 system_prompt_registry 显式设置为 config 中的值（None），"
            "而非保留 LLMCaller 上原有的父 Agent 注册表"
        )
        assert qe.llm_caller.system_prompt == "sub-agent prompt with skill content"
