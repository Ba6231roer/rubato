import pytest
from pathlib import Path
from unittest.mock import patch

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


class TestToolInheritanceMode:
    def test_inherit_all(self):
        assert ToolInheritanceMode.INHERIT_ALL == "inherit_all"

    def test_inherit_selected(self):
        assert ToolInheritanceMode.INHERIT_SELECTED == "inherit_selected"

    def test_independent(self):
        assert ToolInheritanceMode.INDEPENDENT == "independent"

    def test_from_string(self):
        assert ToolInheritanceMode("inherit_all") == ToolInheritanceMode.INHERIT_ALL
        assert ToolInheritanceMode("inherit_selected") == ToolInheritanceMode.INHERIT_SELECTED
        assert ToolInheritanceMode("independent") == ToolInheritanceMode.INDEPENDENT

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ToolInheritanceMode("invalid_mode")

    def test_all_members(self):
        members = list(ToolInheritanceMode)
        assert len(members) == 3


class TestSubAgentState:
    def test_created(self):
        assert SubAgentState.CREATED == "created"

    def test_running(self):
        assert SubAgentState.RUNNING == "running"

    def test_completed(self):
        assert SubAgentState.COMPLETED == "completed"

    def test_failed(self):
        assert SubAgentState.FAILED == "failed"

    def test_timeout(self):
        assert SubAgentState.TIMEOUT == "timeout"

    def test_cancelled(self):
        assert SubAgentState.CANCELLED == "cancelled"

    def test_all_members(self):
        members = list(SubAgentState)
        assert len(members) == 6

    def test_from_string(self):
        assert SubAgentState("running") == SubAgentState.RUNNING


class TestSubAgentDefinition:
    def test_minimal_creation(self):
        definition = SubAgentDefinition(name="test-agent")
        assert definition.name == "test-agent"
        assert definition.description == ""
        assert definition.version == "1.0"
        assert definition.system_prompt is None
        assert definition.system_prompt_file is None
        assert definition.tool_inheritance == ToolInheritanceMode.INHERIT_ALL
        assert definition.available_tools is None
        assert definition.skills is None

    def test_full_creation(self):
        definition = SubAgentDefinition(
            name="full-agent",
            description="A full agent",
            version="2.0",
            system_prompt="You are a helper",
            tool_inheritance=ToolInheritanceMode.INDEPENDENT,
            available_tools=["tool1", "tool2"],
            skills=["skill1"],
        )
        assert definition.name == "full-agent"
        assert definition.description == "A full agent"
        assert definition.version == "2.0"
        assert definition.system_prompt == "You are a helper"
        assert definition.tool_inheritance == ToolInheritanceMode.INDEPENDENT
        assert definition.available_tools == ["tool1", "tool2"]
        assert definition.skills == ["skill1"]

    def test_name_is_required(self):
        with pytest.raises(Exception):
            SubAgentDefinition()

    def test_default_model_config(self):
        definition = SubAgentDefinition(name="test")
        assert definition.model.inherit is True
        assert definition.model.provider is None

    def test_default_execution_config(self):
        definition = SubAgentDefinition(name="test")
        assert definition.execution.timeout == 120
        assert definition.execution.max_retries == 0
        assert definition.execution.recursion_limit == 50

    def test_default_tool_permissions(self):
        definition = SubAgentDefinition(name="test")
        assert definition.tool_permissions.inherit_from_parent is True
        assert definition.tool_permissions.allowlist is None
        assert definition.tool_permissions.denylist is None

    def test_get_system_prompt_content_inline(self):
        definition = SubAgentDefinition(
            name="test",
            system_prompt="Inline prompt"
        )
        assert definition.get_system_prompt_content() == "Inline prompt"

    def test_get_system_prompt_content_default(self):
        definition = SubAgentDefinition(name="my-agent")
        content = definition.get_system_prompt_content()
        assert "my-agent" in content


class TestSubAgentSpawnOptions:
    def test_required_fields(self):
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Do something"
        )
        assert options.agent_name == "test-agent"
        assert options.task == "Do something"
        assert options.system_prompt is None
        assert options.inherit_parent_tools is True
        assert options.max_recursion_depth == 5

    def test_full_creation(self):
        options = SubAgentSpawnOptions(
            agent_name="test-agent",
            task="Do something",
            system_prompt="Custom prompt",
            inherit_parent_tools=False,
            session_id="session-1",
            max_recursion_depth=3,
            timeout=60,
            tool_inheritance=ToolInheritanceMode.INDEPENDENT,
            available_tools=["tool1"],
        )
        assert options.system_prompt == "Custom prompt"
        assert options.inherit_parent_tools is False
        assert options.session_id == "session-1"
        assert options.max_recursion_depth == 3
        assert options.timeout == 60
        assert options.tool_inheritance == ToolInheritanceMode.INDEPENDENT
        assert options.available_tools == ["tool1"]

    def test_missing_required_fields(self):
        with pytest.raises(Exception):
            SubAgentSpawnOptions()


class TestToolPermissionConfig:
    def test_defaults(self):
        config = ToolPermissionConfig()
        assert config.inherit_from_parent is True
        assert config.allowlist is None
        assert config.denylist is None
        assert config.custom_permissions == {}

    def test_custom_values(self):
        config = ToolPermissionConfig(
            inherit_from_parent=False,
            allowlist=["tool1", "tool2"],
            denylist=["tool3"],
            custom_permissions={"tool1": "read"}
        )
        assert config.inherit_from_parent is False
        assert config.allowlist == ["tool1", "tool2"]
        assert config.denylist == ["tool3"]
        assert config.custom_permissions == {"tool1": "read"}


class TestSubAgentModelConfig:
    def test_defaults(self):
        config = SubAgentModelConfig()
        assert config.inherit is True
        assert config.provider is None
        assert config.name is None
        assert config.temperature is None
        assert config.max_tokens is None

    def test_custom_values(self):
        config = SubAgentModelConfig(
            inherit=False,
            provider="anthropic",
            name="claude-3",
            temperature=0.5,
            max_tokens=8000,
        )
        assert config.inherit is False
        assert config.provider == "anthropic"
        assert config.name == "claude-3"
        assert config.temperature == 0.5
        assert config.max_tokens == 8000

    def test_temperature_validation(self):
        with pytest.raises(Exception):
            SubAgentModelConfig(temperature=1.5)

    def test_temperature_zero(self):
        config = SubAgentModelConfig(temperature=0.0)
        assert config.temperature == 0.0


class TestSubAgentExecutionConfig:
    def test_defaults(self):
        config = SubAgentExecutionConfig()
        assert config.timeout == 120
        assert config.max_retries == 0
        assert config.recursion_limit == 50
        assert config.max_context_tokens is None

    def test_custom_values(self):
        config = SubAgentExecutionConfig(
            timeout=300,
            max_retries=3,
            recursion_limit=100,
            max_context_tokens=160000,
        )
        assert config.timeout == 300
        assert config.max_retries == 3
        assert config.recursion_limit == 100
        assert config.max_context_tokens == 160000
