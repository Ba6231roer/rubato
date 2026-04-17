import os
import pytest
from pathlib import Path

from src.config.loader import ConfigLoader
from src.config.validators import ConfigValidationError


def _write_yaml(directory, filename, content):
    (directory / filename).write_text(content, encoding="utf-8")


def _create_minimal_config_dir(tmp_path, with_agent=False):
    _write_yaml(tmp_path, "model_config.yaml", (
        "model:\n"
        "  provider: openai\n"
        "  name: gpt-4\n"
        "  api_key: test-api-key\n"
        "  temperature: 0.7\n"
        "  max_tokens: 2000\n"
        "parameters:\n"
        "  retry_max_count: 3\n"
        "  retry_initial_delay: 10.0\n"
        "  retry_max_delay: 60.0\n"
        "  llm_timeout: 300.0\n"
    ))
    _write_yaml(tmp_path, "mcp_config.yaml", (
        "mcp:\n"
        "  servers: {}\n"
    ))
    _write_yaml(tmp_path, "prompt_config.yaml", (
        "prompts:\n"
        "  system_prompt_file: prompts/system_prompt.txt\n"
        "  skill_loading_prompt_file: prompts/skill_loading_prompt.txt\n"
    ))
    _write_yaml(tmp_path, "skills_config.yaml", (
        "skills:\n"
        "  directory: skills\n"
        "  auto_load: true\n"
    ))
    if with_agent:
        _write_yaml(tmp_path, "agent_config.yaml", (
            "agent:\n"
            "  max_context_tokens: 80000\n"
            "  execution:\n"
            "    recursion_limit: 100\n"
            "    sub_agent_recursion_limit: 50\n"
            "    llm_timeout: 300\n"
        ))


class TestConfigLoaderLoadAll:
    def test_load_all_complete_config(self, tmp_path):
        _create_minimal_config_dir(tmp_path, with_agent=True)
        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load_all()
        assert config.model.model.provider == "openai"
        assert config.model.model.name == "gpt-4"
        assert config.prompts.system_prompt_file == "prompts/system_prompt.txt"
        assert config.skills.directory == "skills"
        assert config.agent.max_context_tokens == 80000

    def test_load_all_without_agent_uses_default(self, tmp_path):
        _create_minimal_config_dir(tmp_path, with_agent=False)
        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load_all()
        assert config.agent.max_context_tokens == 80000

    def test_load_all_missing_required_file(self, tmp_path):
        loader = ConfigLoader(config_dir=str(tmp_path))
        with pytest.raises(ConfigValidationError):
            loader.load_all()


class TestConfigLoaderLoadYaml:
    def test_load_yaml_env_var_substitution(self, tmp_path):
        os.environ["RUBATO_TEST_VAR"] = "replaced_value"
        try:
            _write_yaml(tmp_path, "test.yaml", "key: ${RUBATO_TEST_VAR}")
            loader = ConfigLoader(config_dir=str(tmp_path))
            data = loader._load_yaml("test.yaml")
            assert data["key"] == "replaced_value"
        finally:
            del os.environ["RUBATO_TEST_VAR"]

    def test_load_yaml_project_root_substitution(self, tmp_path):
        _write_yaml(tmp_path, "test.yaml", "path: ${PROJECT_ROOT}")
        loader = ConfigLoader(config_dir=str(tmp_path))
        data = loader._load_yaml("test.yaml")
        assert data["path"] == str(tmp_path.parent.resolve())

    def test_load_yaml_config_dir_substitution(self, tmp_path):
        _write_yaml(tmp_path, "test.yaml", "path: ${CONFIG_DIR}")
        loader = ConfigLoader(config_dir=str(tmp_path))
        data = loader._load_yaml("test.yaml")
        assert data["path"] == str(tmp_path.resolve())

    def test_load_yaml_file_not_found(self, tmp_path):
        loader = ConfigLoader(config_dir=str(tmp_path))
        with pytest.raises(ConfigValidationError, match="配置文件不存在"):
            loader._load_yaml("nonexistent.yaml")

    def test_load_yaml_undefined_env_var_returns_empty(self, tmp_path):
        _write_yaml(tmp_path, "test.yaml", 'key: "${RUBATO_UNDEF_VAR_XYZ}"')
        loader = ConfigLoader(config_dir=str(tmp_path))
        data = loader._load_yaml("test.yaml")
        assert data["key"] == ""


class TestConfigLoaderSafeCreateConfig:
    def test_safe_create_config_valid(self, tmp_path):
        from src.config.models import PromptConfig
        loader = ConfigLoader(config_dir=str(tmp_path))
        result = loader._safe_create_config(PromptConfig, {
            "system_prompt_file": "test.txt",
            "skill_loading_prompt_file": "skill.txt",
        })
        assert result.system_prompt_file == "test.txt"

    def test_safe_create_config_pydantic_error_converted(self, tmp_path):
        from src.config.models import ModelConfig
        loader = ConfigLoader(config_dir=str(tmp_path))
        with pytest.raises(ConfigValidationError, match="配置验证失败"):
            loader._safe_create_config(ModelConfig, {
                "provider": "invalid_provider",
                "name": "test",
                "api_key": "k",
            })

    def test_safe_create_config_non_pydantic_error_reraise(self, tmp_path):
        loader = ConfigLoader(config_dir=str(tmp_path))
        with pytest.raises(TypeError):
            loader._safe_create_config(dict, None)


class TestConfigLoaderOptionalDefaults:
    def test_optional_config_missing_returns_default(self, tmp_path):
        from src.config.models import AgentConfig
        _create_minimal_config_dir(tmp_path, with_agent=False)
        loader = ConfigLoader(config_dir=str(tmp_path))
        result = loader._load_config_section(
            "agent_config.yaml", "agent", AgentConfig,
            optional=True, default=AgentConfig()
        )
        assert result.max_context_tokens == 80000

    def test_optional_config_file_missing_returns_default(self, tmp_path):
        from src.config.models import AgentConfig
        loader = ConfigLoader(config_dir=str(tmp_path))
        result = loader._load_config_section(
            "nonexistent.yaml", "agent", AgentConfig,
            optional=True, default=AgentConfig()
        )
        assert result.max_context_tokens == 80000

    def test_required_config_file_missing_raises(self, tmp_path):
        from src.config.models import PromptConfig
        loader = ConfigLoader(config_dir=str(tmp_path))
        with pytest.raises(ConfigValidationError):
            loader._load_config_section(
                "nonexistent.yaml", "prompts", PromptConfig,
                optional=False
            )
