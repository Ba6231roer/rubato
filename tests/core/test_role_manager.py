import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.core.role_manager import RoleManager, DEFAULT_ROLE_NAME
from src.config.models import (
    RoleConfig, RoleModelConfig, ModelConfig, FullModelConfig,
    RoleExecutionConfig
)
from src.config.validators import ConfigValidationError


def _make_role_config(
    name="test-role",
    description="Test role",
    system_prompt_file="prompts/test.txt",
    inherit=True,
    provider=None,
    model_name=None,
    api_key=None,
    base_url=None,
    temperature=None,
    max_tokens=None,
):
    return RoleConfig(
        name=name,
        description=description,
        system_prompt_file=system_prompt_file,
        model=RoleModelConfig(
            inherit=inherit,
            provider=provider,
            name=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        ),
        execution=RoleExecutionConfig(),
    )


def _make_default_model_config():
    return FullModelConfig(
        model=ModelConfig(
            provider="openai",
            name="gpt-4",
            api_key="default-api-key",
            base_url="https://api.openai.com",
            temperature=0.7,
            max_tokens=4000,
        )
    )


class TestDefaultRoleName:
    def test_default_role_name_value(self):
        assert DEFAULT_ROLE_NAME == "_default"


class TestRoleManagerLoadRoles:
    @patch("src.core.role_manager.RoleConfigLoader")
    def test_load_roles_returns_roles(self, MockLoader):
        mock_loader = MockLoader.return_value
        role1 = _make_role_config(name="role1")
        role2 = _make_role_config(name="role2")
        mock_loader.load_all.return_value = {"role1": role1, "role2": role2}
        mock_loader.list_roles.return_value = ["role1", "role2"]

        manager = RoleManager(default_model_config=_make_default_model_config())
        roles = manager.load_roles()

        assert "role1" in roles
        assert "role2" in roles
        mock_loader.load_all.assert_called_once()

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_load_roles_sets_current_role_to_default(self, MockLoader):
        mock_loader = MockLoader.return_value
        default_role = _make_role_config(name=DEFAULT_ROLE_NAME)
        mock_loader.load_all.return_value = {DEFAULT_ROLE_NAME: default_role}
        mock_loader.list_roles.return_value = [DEFAULT_ROLE_NAME]
        mock_loader.get_role.return_value = default_role

        manager = RoleManager(default_model_config=_make_default_model_config())
        manager.load_roles()

        assert manager._current_role is not None
        assert manager._current_role.name == DEFAULT_ROLE_NAME

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_load_roles_no_default_role(self, MockLoader):
        mock_loader = MockLoader.return_value
        role1 = _make_role_config(name="role1")
        mock_loader.load_all.return_value = {"role1": role1}
        mock_loader.list_roles.return_value = ["role1"]

        manager = RoleManager(default_model_config=_make_default_model_config())
        manager.load_roles()

        assert manager._current_role is None


class TestGetMergedModelConfig:
    @patch("src.core.role_manager.RoleConfigLoader")
    def test_inherit_from_default(self, MockLoader):
        mock_loader = MockLoader.return_value
        role = _make_role_config(name="inherited-role", inherit=True)
        mock_loader.load_all.return_value = {"inherited-role": role}
        mock_loader.list_roles.return_value = ["inherited-role"]

        default_config = _make_default_model_config()
        manager = RoleManager(default_model_config=default_config)
        manager.load_roles()

        merged = manager.get_merged_model_config("inherited-role")
        assert merged is not None
        assert merged.provider == "openai"
        assert merged.name == "gpt-4"

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_inherit_with_override(self, MockLoader):
        mock_loader = MockLoader.return_value
        role = _make_role_config(
            name="override-role",
            inherit=True,
            model_name="gpt-3.5-turbo",
            temperature=0.3,
        )
        mock_loader.load_all.return_value = {"override-role": role}
        mock_loader.list_roles.return_value = ["override-role"]

        default_config = _make_default_model_config()
        manager = RoleManager(default_model_config=default_config)
        manager.load_roles()

        merged = manager.get_merged_model_config("override-role")
        assert merged.name == "gpt-3.5-turbo"
        assert merged.temperature == 0.3
        assert merged.provider == "openai"

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_no_inherit_with_full_config(self, MockLoader):
        mock_loader = MockLoader.return_value
        role = _make_role_config(
            name="independent-role",
            inherit=False,
            provider="anthropic",
            model_name="claude-3",
            api_key="anthropic-key",
        )
        mock_loader.load_all.return_value = {"independent-role": role}
        mock_loader.list_roles.return_value = ["independent-role"]

        default_config = _make_default_model_config()
        manager = RoleManager(default_model_config=default_config)
        manager.load_roles()

        merged = manager.get_merged_model_config("independent-role")
        assert merged.provider == "anthropic"
        assert merged.name == "claude-3"

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_no_inherit_missing_required_fields(self, MockLoader):
        mock_loader = MockLoader.return_value
        role = _make_role_config(
            name="bad-role",
            inherit=False,
            provider=None,
            model_name=None,
        )
        mock_loader.load_all.return_value = {"bad-role": role}
        mock_loader.list_roles.return_value = ["bad-role"]

        default_config = _make_default_model_config()
        manager = RoleManager(default_model_config=default_config)
        with pytest.raises(ConfigValidationError, match="必须提供 provider 和 name"):
            manager.load_roles()

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_no_default_config_raises(self, MockLoader):
        mock_loader = MockLoader.return_value
        role = _make_role_config(name="orphan-role", inherit=True)
        mock_loader.load_all.return_value = {"orphan-role": role}
        mock_loader.list_roles.return_value = ["orphan-role"]

        manager = RoleManager(default_model_config=None)
        with pytest.raises(ConfigValidationError, match="未提供默认模型配置"):
            manager.load_roles()

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_unknown_role_returns_none(self, MockLoader):
        mock_loader = MockLoader.return_value
        mock_loader.load_all.return_value = {}
        mock_loader.list_roles.return_value = []
        mock_loader.get_role.return_value = None

        manager = RoleManager(default_model_config=_make_default_model_config())
        manager.load_roles()

        result = manager.get_merged_model_config("nonexistent")
        assert result is None


class TestSwitchRole:
    @patch("src.core.role_manager.RoleConfigLoader")
    def test_switch_role_success(self, MockLoader):
        mock_loader = MockLoader.return_value
        role = _make_role_config(name="target-role")
        mock_loader.get_role.return_value = role

        manager = RoleManager(default_model_config=_make_default_model_config())
        result = manager.switch_role("target-role")

        assert result.name == "target-role"
        assert manager._current_role.name == "target-role"

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_switch_role_nonexistent(self, MockLoader):
        mock_loader = MockLoader.return_value
        mock_loader.get_role.return_value = None

        manager = RoleManager(default_model_config=_make_default_model_config())
        with pytest.raises(ConfigValidationError, match="不存在"):
            manager.switch_role("nonexistent")


class TestListRoles:
    @patch("src.core.role_manager.RoleConfigLoader")
    def test_list_roles_excludes_default(self, MockLoader):
        mock_loader = MockLoader.return_value
        mock_loader.list_roles.return_value = [DEFAULT_ROLE_NAME, "role1", "role2"]

        manager = RoleManager(default_model_config=_make_default_model_config())
        roles = manager.list_roles()

        assert DEFAULT_ROLE_NAME not in roles
        assert "role1" in roles
        assert "role2" in roles

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_list_roles_empty(self, MockLoader):
        mock_loader = MockLoader.return_value
        mock_loader.list_roles.return_value = []

        manager = RoleManager(default_model_config=_make_default_model_config())
        roles = manager.list_roles()
        assert roles == []


class TestHasRole:
    @patch("src.core.role_manager.RoleConfigLoader")
    def test_has_role_true(self, MockLoader):
        mock_loader = MockLoader.return_value
        mock_loader.list_roles.return_value = ["role1", DEFAULT_ROLE_NAME]

        manager = RoleManager(default_model_config=_make_default_model_config())
        assert manager.has_role("role1") is True

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_has_role_false(self, MockLoader):
        mock_loader = MockLoader.return_value
        mock_loader.list_roles.return_value = ["role1"]

        manager = RoleManager(default_model_config=_make_default_model_config())
        assert manager.has_role("nonexistent") is False


class TestIsDefaultRole:
    def test_is_default_role(self):
        manager = RoleManager(default_model_config=_make_default_model_config())
        assert manager.is_default_role(DEFAULT_ROLE_NAME) is True
        assert manager.is_default_role("other") is False


class TestGetCurrentRole:
    @patch("src.core.role_manager.RoleConfigLoader")
    def test_get_current_role_with_default(self, MockLoader):
        mock_loader = MockLoader.return_value
        default_role = _make_role_config(name=DEFAULT_ROLE_NAME)
        mock_loader.load_all.return_value = {DEFAULT_ROLE_NAME: default_role}
        mock_loader.list_roles.return_value = [DEFAULT_ROLE_NAME]
        mock_loader.get_role.return_value = default_role

        manager = RoleManager(default_model_config=_make_default_model_config())
        manager.load_roles()

        current = manager.get_current_role()
        assert current is not None
        assert current.name == DEFAULT_ROLE_NAME

    @patch("src.core.role_manager.RoleConfigLoader")
    def test_get_current_role_none(self, MockLoader):
        mock_loader = MockLoader.return_value
        mock_loader.load_all.return_value = {}
        mock_loader.list_roles.return_value = []

        manager = RoleManager(default_model_config=_make_default_model_config())
        manager.load_roles()

        assert manager.get_current_role() is None


class TestSetDefaultModelConfig:
    @patch("src.core.role_manager.RoleConfigLoader")
    def test_set_default_model_config_clears_cache(self, MockLoader):
        mock_loader = MockLoader.return_value
        role = _make_role_config(name="role1", inherit=True)
        mock_loader.load_all.return_value = {"role1": role}
        mock_loader.list_roles.return_value = ["role1"]
        mock_loader.get_all_roles.return_value = {"role1": role}

        manager = RoleManager(default_model_config=_make_default_model_config())
        manager.load_roles()

        assert "role1" in manager._merged_model_configs

        new_config = FullModelConfig(
            model=ModelConfig(
                provider="anthropic",
                name="claude-3",
                api_key="new-key",
            )
        )
        manager.set_default_model_config(new_config)

        merged = manager.get_merged_model_config("role1")
        assert merged.provider == "anthropic"
        assert merged.name == "claude-3"
