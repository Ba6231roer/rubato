import pytest
from src.config.models import (
    PermissionMode,
    ModelConfig,
    RoleConfig,
    RoleToolsConfig,
    RoleFileToolsConfig,
    AppConfig,
    MessageCompressionConfig,
    FullModelConfig,
    MCPConfig,
    PromptConfig,
    SkillsConfig,
    AgentConfig,
)


class TestPermissionMode:
    def test_enum_values(self):
        assert PermissionMode.ask.value == "ask"
        assert PermissionMode.allow.value == "allow"
        assert PermissionMode.deny.value == "deny"

    def test_enum_members_count(self):
        assert len(PermissionMode) == 3

    def test_enum_from_string(self):
        assert PermissionMode("ask") == PermissionMode.ask
        assert PermissionMode("allow") == PermissionMode.allow
        assert PermissionMode("deny") == PermissionMode.deny

    def test_enum_invalid_value(self):
        with pytest.raises(ValueError):
            PermissionMode("invalid")


class TestModelConfig:
    def test_valid_config(self):
        config = ModelConfig(
            provider="openai",
            name="gpt-4",
            api_key="test-key",
        )
        assert config.provider == "openai"
        assert config.name == "gpt-4"
        assert config.api_key == "test-key"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000

    def test_temperature_range_valid(self):
        config = ModelConfig(provider="openai", name="gpt-4", api_key="k", temperature=0.0)
        assert config.temperature == 0.0
        config = ModelConfig(provider="openai", name="gpt-4", api_key="k", temperature=1.0)
        assert config.temperature == 1.0
        config = ModelConfig(provider="openai", name="gpt-4", api_key="k", temperature=0.5)
        assert config.temperature == 0.5

    def test_temperature_range_invalid(self):
        with pytest.raises(ValueError):
            ModelConfig(provider="openai", name="gpt-4", api_key="k", temperature=-0.1)
        with pytest.raises(ValueError):
            ModelConfig(provider="openai", name="gpt-4", api_key="k", temperature=1.1)
        with pytest.raises(ValueError):
            ModelConfig(provider="openai", name="gpt-4", api_key="k", temperature=2.0)

    def test_provider_allowed_values(self):
        for provider in ["openai", "anthropic", "local"]:
            config = ModelConfig(provider=provider, name="m", api_key="k")
            assert config.provider == provider

    def test_provider_invalid(self):
        with pytest.raises(ValueError):
            ModelConfig(provider="invalid", name="m", api_key="k")
        with pytest.raises(ValueError):
            ModelConfig(provider="google", name="m", api_key="k")


class TestRoleConfig:
    def test_valid_name(self):
        role = RoleConfig(name="my-role", description="d", system_prompt_file="f.txt")
        assert role.name == "my-role"

    def test_name_with_underscore(self):
        role = RoleConfig(name="my_role", description="d", system_prompt_file="f.txt")
        assert role.name == "my_role"

    def test_name_alphanumeric(self):
        role = RoleConfig(name="role123", description="d", system_prompt_file="f.txt")
        assert role.name == "role123"

    def test_name_strip_and_lowercase(self):
        role = RoleConfig(name="My-Role", description="d", system_prompt_file="f.txt")
        assert role.name == "my-role"

    def test_name_lowercase_only(self):
        role = RoleConfig(name="MYROLE", description="d", system_prompt_file="f.txt")
        assert role.name == "myrole"

    def test_name_empty_raises(self):
        with pytest.raises(ValueError):
            RoleConfig(name="", description="d", system_prompt_file="f.txt")

    def test_name_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            RoleConfig(name="   ", description="d", system_prompt_file="f.txt")

    def test_name_invalid_characters_raises(self):
        with pytest.raises(ValueError):
            RoleConfig(name="invalid name", description="d", system_prompt_file="f.txt")
        with pytest.raises(ValueError):
            RoleConfig(name="role!", description="d", system_prompt_file="f.txt")
        with pytest.raises(ValueError):
            RoleConfig(name="role@name", description="d", system_prompt_file="f.txt")

    def test_default_values(self):
        role = RoleConfig(name="test", description="d", system_prompt_file="f.txt")
        assert role.model.inherit is True
        assert role.execution.max_context_tokens == 80000
        assert role.available_tools == []
        assert role.file_tools is None
        assert role.tools is None
        assert role.metadata is None


class TestRoleToolsConfig:
    def test_builtin_none(self):
        config = RoleToolsConfig(builtin=None)
        assert config.builtin is None

    def test_builtin_dict(self):
        config = RoleToolsConfig(builtin={"enabled": True, "tools": ["shell_tool"]})
        assert config.builtin == {"enabled": True, "tools": ["shell_tool"]}

    def test_builtin_bool_true(self):
        config = RoleToolsConfig(builtin=True)
        assert config.builtin == {"enabled": True}

    def test_builtin_bool_false(self):
        config = RoleToolsConfig(builtin=False)
        assert config.builtin == {"enabled": False}

    def test_builtin_list(self):
        config = RoleToolsConfig(builtin=["shell_tool", "spawn_agent"])
        assert config.builtin == {"enabled": True, "tools": ["shell_tool", "spawn_agent"]}

    def test_builtin_empty_list(self):
        config = RoleToolsConfig(builtin=[])
        assert config.builtin == {"enabled": True, "tools": []}


class TestRoleFileToolsConfig:
    def test_permissions_none_fills_default(self):
        config = RoleFileToolsConfig(permissions=None)
        assert config.permissions == {"default": PermissionMode.ask, "custom": {}}

    def test_permissions_dict_missing_default(self):
        config = RoleFileToolsConfig(permissions={"custom": {"read:*": "allow"}})
        assert config.permissions["default"] == PermissionMode.ask
        assert config.permissions["custom"] == {"read:*": "allow"}

    def test_permissions_dict_missing_custom(self):
        config = RoleFileToolsConfig(permissions={"default": "deny"})
        assert config.permissions["default"] == "deny"
        assert config.permissions["custom"] == {}

    def test_permissions_dict_complete(self):
        config = RoleFileToolsConfig(
            permissions={"default": "allow", "custom": {"write:*": "ask"}}
        )
        assert config.permissions["default"] == "allow"
        assert config.permissions["custom"] == {"write:*": "ask"}

    def test_default_values(self):
        config = RoleFileToolsConfig()
        assert config.enabled is True
        assert config.audit is True
        assert config.workspace is None
        assert config.workspace_restriction is None


class TestAppConfigMigrateOldConfig:
    def test_migrate_old_mcp_format(self):
        data = {
            "mcp": {
                "playwright": {
                    "command": "npx",
                    "args": ["-y", "@playwright/mcp"],
                },
                "other-server": {
                    "command": "node",
                    "args": ["server.js"],
                },
            }
        }
        result = AppConfig.migrate_old_config(data)
        assert "servers" in result["mcp"]
        assert "playwright" in result["mcp"]["servers"]
        assert "other-server" in result["mcp"]["servers"]

    def test_migrate_new_format_unchanged(self):
        data = {
            "mcp": {
                "servers": {
                    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp"]}
                }
            }
        }
        result = AppConfig.migrate_old_config(data)
        assert result == data

    def test_migrate_mcp_none(self):
        data = {"mcp": None}
        result = AppConfig.migrate_old_config(data)
        assert result["mcp"] is None

    def test_migrate_no_mcp_key(self):
        data = {"model": {}}
        result = AppConfig.migrate_old_config(data)
        assert "mcp" not in result

    def test_migrate_filters_non_server_entries(self):
        data = {
            "mcp": {
                "some_setting": "value",
                "valid_server": {"command": "node", "args": []},
            }
        }
        result = AppConfig.migrate_old_config(data)
        assert "valid_server" in result["mcp"]["servers"]
        assert "some_setting" not in result["mcp"]["servers"]


class TestMessageCompressionConfig:
    def test_default_values(self):
        config = MessageCompressionConfig()
        assert config.enabled is True
        assert config.max_tokens == 50000
        assert config.keep_recent == 6
        assert config.summary_max_length == 300
        assert config.max_consecutive_failures == 3

    def test_positive_validation(self):
        with pytest.raises(ValueError):
            MessageCompressionConfig(max_tokens=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(max_tokens=-1)
        with pytest.raises(ValueError):
            MessageCompressionConfig(keep_recent=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(summary_max_length=-10)
        with pytest.raises(ValueError):
            MessageCompressionConfig(history_summary_count=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(autocompact_buffer_tokens=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(manual_compact_buffer_tokens=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(warning_threshold_buffer_tokens=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(snip_keep_recent=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(tool_result_persist_threshold=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(tool_result_budget_per_message=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(max_consecutive_failures=0)
        with pytest.raises(ValueError):
            MessageCompressionConfig(skill_stale_timeout_seconds=0)

    def test_valid_custom_values(self):
        config = MessageCompressionConfig(
            max_tokens=100000,
            keep_recent=10,
            summary_max_length=500,
            max_consecutive_failures=5,
        )
        assert config.max_tokens == 100000
        assert config.keep_recent == 10
