import os
import pytest
from pathlib import Path

from pydantic import ValidationError

from src.config.validators import (
    ConfigValidationError,
    replace_env_vars,
    validate_api_key,
    handle_pydantic_error,
    validate_required_configs,
    validate_config_value,
)
from src.config.models import ModelConfig


class TestReplaceEnvVars:
    def test_project_root_substitution(self, tmp_path):
        content = "root: ${PROJECT_ROOT}"
        result = replace_env_vars(content, config_dir=tmp_path)
        assert result == f"root: {tmp_path.parent.resolve()}"

    def test_config_dir_substitution(self, tmp_path):
        content = "dir: ${CONFIG_DIR}"
        result = replace_env_vars(content, config_dir=tmp_path)
        assert result == f"dir: {tmp_path.resolve()}"

    def test_home_substitution(self):
        content = "home: ${HOME}"
        result = replace_env_vars(content)
        assert result == f"home: {Path.home()}"

    def test_normal_env_var(self):
        os.environ["RUBATO_TEST_REPLACE"] = "hello_world"
        try:
            content = "val: ${RUBATO_TEST_REPLACE}"
            result = replace_env_vars(content)
            assert result == "val: hello_world"
        finally:
            del os.environ["RUBATO_TEST_REPLACE"]

    def test_undefined_env_var_returns_empty(self):
        content = "val: ${RUBATO_UNDEF_XYZ_123}"
        result = replace_env_vars(content)
        assert result == "val: "

    def test_no_config_dir_skips_special_vars(self):
        content = "root: ${PROJECT_ROOT}"
        result = replace_env_vars(content, config_dir=None)
        assert "PROJECT_ROOT" not in result or result == "root: "

    def test_multiple_vars_in_content(self, tmp_path):
        os.environ["RUBATO_MULTI_TEST"] = "multi_val"
        try:
            content = "a: ${PROJECT_ROOT}\nb: ${RUBATO_MULTI_TEST}"
            result = replace_env_vars(content, config_dir=tmp_path)
            assert str(tmp_path.parent.resolve()) in result
            assert "multi_val" in result
        finally:
            del os.environ["RUBATO_MULTI_TEST"]

    def test_no_vars_returns_unchanged(self):
        content = "key: plain_value"
        result = replace_env_vars(content)
        assert result == content


class TestValidateApiKey:
    def test_config_value_takes_priority(self):
        result = validate_api_key("my-config-key", "OPENAI_API_KEY")
        assert result == "my-config-key"

    def test_env_var_fallback(self):
        os.environ["RUBATO_API_KEY_TEST"] = "env-key-123"
        try:
            result = validate_api_key("", "RUBATO_API_KEY_TEST")
            assert result == "env-key-123"
        finally:
            del os.environ["RUBATO_API_KEY_TEST"]

    def test_placeholder_triggers_env_fallback(self):
        os.environ["RUBATO_API_PLACEHOLDER"] = "env-key-456"
        try:
            result = validate_api_key("${RUBATO_API_PLACEHOLDER}", "RUBATO_API_PLACEHOLDER")
            assert result == "env-key-456"
        finally:
            del os.environ["RUBATO_API_PLACEHOLDER"]

    def test_missing_both_raises(self):
        env_var = "RUBATO_MISSING_KEY_XYZ_999"
        os.environ.pop(env_var, None)
        with pytest.raises(ConfigValidationError, match="未设置API密钥"):
            validate_api_key("", env_var)

    def test_empty_string_triggers_env_fallback(self):
        os.environ["RUBATO_EMPTY_KEY_TEST"] = "fallback-key"
        try:
            result = validate_api_key("", "RUBATO_EMPTY_KEY_TEST")
            assert result == "fallback-key"
        finally:
            del os.environ["RUBATO_EMPTY_KEY_TEST"]


class TestHandlePydanticError:
    def test_formats_error_path(self):
        try:
            ModelConfig(provider="invalid", name="test", api_key="k")
        except ValidationError as e:
            result = handle_pydantic_error(e)
            assert isinstance(result, ConfigValidationError)
            assert "配置验证失败" in str(result)
            assert "provider" in str(result)

    def test_multiple_errors_formatted(self):
        try:
            ModelConfig(provider="bad", name="test", api_key="k", temperature=5.0)
        except ValidationError as e:
            result = handle_pydantic_error(e)
            msg = str(result)
            assert "provider" in msg
            assert "temperature" in msg

    def test_single_error_format(self):
        try:
            ModelConfig(provider="openai", name="test", api_key="k", temperature=-1.0)
        except ValidationError as e:
            result = handle_pydantic_error(e)
            assert "temperature" in str(result)


class TestConfigValidationError:
    def test_is_exception(self):
        err = ConfigValidationError("test error")
        assert isinstance(err, Exception)

    def test_message_preserved(self):
        err = ConfigValidationError("custom message")
        assert str(err) == "custom message"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ConfigValidationError):
            raise ConfigValidationError("test")


class TestValidateRequiredConfigs:
    def test_all_required_present(self):
        configs = {"a": 1, "b": 2, "c": 3}
        validate_required_configs(configs, ["a", "b"])

    def test_missing_required_raises(self):
        configs = {"a": 1}
        with pytest.raises(ConfigValidationError, match="缺少必要配置"):
            validate_required_configs(configs, ["a", "b"])

    def test_empty_required_list(self):
        validate_required_configs({}, [])


class TestValidateConfigValue:
    def test_value_in_range(self):
        assert validate_config_value(5, "test", min_val=1, max_val=10) == 5

    def test_value_below_min_raises(self):
        with pytest.raises(ConfigValidationError, match="不能小于"):
            validate_config_value(0, "test", min_val=1)

    def test_value_above_max_raises(self):
        with pytest.raises(ConfigValidationError, match="不能大于"):
            validate_config_value(11, "test", max_val=10)

    def test_no_bounds(self):
        assert validate_config_value(42, "test") == 42
