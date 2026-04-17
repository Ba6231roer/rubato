import pytest
from pathlib import Path

from src.config.role_loader import RoleConfigLoader
from src.config.validators import ConfigValidationError


def _write_role(roles_dir, filename, content):
    (roles_dir / filename).write_text(content, encoding="utf-8")


class TestRoleConfigLoaderLazyLoad:
    def test_initial_state_not_loaded(self, tmp_path):
        loader = RoleConfigLoader(roles_dir=str(tmp_path / "roles"))
        assert loader._loaded is False
        assert loader._roles == {}

    def test_load_all_sets_loaded_flag(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        loader.load_all()
        assert loader._loaded is True

    def test_load_all_returns_cached_on_second_call(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "test.yaml", (
            "name: test-role\n"
            "description: Test\n"
            "system_prompt_file: test.txt\n"
        ))
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        roles1 = loader.load_all()
        _write_role(roles_dir, "test2.yaml", (
            "name: test-role2\n"
            "description: Test2\n"
            "system_prompt_file: test2.txt\n"
        ))
        roles2 = loader.load_all()
        assert roles1 is roles2
        assert "test-role2" not in roles2

    def test_get_role_triggers_lazy_load(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "my-role.yaml", (
            "name: my-role\n"
            "description: My Role\n"
            "system_prompt_file: my.txt\n"
        ))
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        assert loader._loaded is False
        role = loader.get_role("my-role")
        assert loader._loaded is True
        assert role is not None
        assert role.name == "my-role"

    def test_get_all_roles_triggers_lazy_load(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        assert loader._loaded is False
        loader.get_all_roles()
        assert loader._loaded is True

    def test_list_roles_triggers_lazy_load(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        assert loader._loaded is False
        loader.list_roles()
        assert loader._loaded is True


class TestRoleConfigLoaderFileParsing:
    def test_parse_yaml_role_file(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "executor.yaml", (
            "name: case-executor\n"
            "description: Case Executor\n"
            "system_prompt_file: prompts/executor.txt\n"
            "available_tools:\n"
            "  - shell_tool\n"
            "  - spawn_agent\n"
        ))
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        roles = loader.load_all()
        assert "case-executor" in roles
        assert roles["case-executor"].description == "Case Executor"
        assert roles["case-executor"].available_tools == ["shell_tool", "spawn_agent"]

    def test_parse_yml_extension(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "runner.yml", (
            "name: runner\n"
            "description: Runner\n"
            "system_prompt_file: runner.txt\n"
        ))
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        roles = loader.load_all()
        assert "runner" in roles

    def test_parse_empty_yaml_returns_none(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "empty.yaml", "")
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        roles = loader.load_all()
        assert len(roles) == 0

    def test_parse_invalid_role_raises(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "bad.yaml", "invalid: data\nno_name: true\n")
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        with pytest.raises(ConfigValidationError, match="加载角色配置文件"):
            loader.load_all()

    def test_parse_multiple_roles(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "role1.yaml", (
            "name: role-one\n"
            "description: Role One\n"
            "system_prompt_file: one.txt\n"
        ))
        _write_role(roles_dir, "role2.yaml", (
            "name: role-two\n"
            "description: Role Two\n"
            "system_prompt_file: two.txt\n"
        ))
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        roles = loader.load_all()
        assert len(roles) == 2
        assert "role-one" in roles
        assert "role-two" in roles


class TestRoleConfigLoaderAutoCreateDir:
    def test_directory_not_exists_creates_it(self, tmp_path):
        roles_dir = tmp_path / "nonexistent" / "roles"
        assert not roles_dir.exists()
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        loader.load_all()
        assert roles_dir.exists()

    def test_directory_not_exists_returns_empty_roles(self, tmp_path):
        roles_dir = tmp_path / "nonexistent" / "roles"
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        roles = loader.load_all()
        assert roles == {}


class TestRoleConfigLoaderReload:
    def test_reload_picks_up_new_files(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "role1.yaml", (
            "name: role-one\n"
            "description: Role One\n"
            "system_prompt_file: one.txt\n"
        ))
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        roles1 = loader.load_all()
        assert "role-one" in roles1

        _write_role(roles_dir, "role2.yaml", (
            "name: role-two\n"
            "description: Role Two\n"
            "system_prompt_file: two.txt\n"
        ))
        roles2 = loader.reload()
        assert "role-one" in roles2
        assert "role-two" in roles2

    def test_reload_clears_old_roles(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        _write_role(roles_dir, "old.yaml", (
            "name: old-role\n"
            "description: Old\n"
            "system_prompt_file: old.txt\n"
        ))
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        loader.load_all()
        assert "old-role" in loader._roles

        (roles_dir / "old.yaml").unlink()
        loader.reload()
        assert "old-role" not in loader._roles

    def test_reload_resets_loaded_flag(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        loader = RoleConfigLoader(roles_dir=str(roles_dir))
        loader.load_all()
        assert loader._loaded is True
        loader.reload()
        assert loader._loaded is True
