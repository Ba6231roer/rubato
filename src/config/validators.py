from pydantic import ValidationError
from typing import List, Any
import os


class ConfigValidationError(Exception):
    """配置验证错误"""
    pass


def validate_required_configs(configs: dict, required_keys: List[str]) -> None:
    """验证必要的配置项"""
    for key in required_keys:
        if key not in configs:
            raise ConfigValidationError(f"缺少必要配置：{key}")


def validate_api_key(api_key: str, env_var: str = "OPENAI_API_KEY") -> str:
    """验证并获取API密钥"""
    if not api_key or api_key == "${" + env_var + "}":
        api_key = os.getenv(env_var)
        if not api_key:
            raise ConfigValidationError(
                f"未设置API密钥，请设置{env_var}环境变量或在配置文件中配置"
            )
    return api_key


def validate_config_value(value: Any, name: str, min_val: Any = None, max_val: Any = None) -> Any:
    """验证配置值范围"""
    if min_val is not None and value < min_val:
        raise ConfigValidationError(f"{name} 不能小于 {min_val}，当前值：{value}")
    if max_val is not None and value > max_val:
        raise ConfigValidationError(f"{name} 不能大于 {max_val}，当前值：{value}")
    return value


def handle_pydantic_error(error: ValidationError) -> ConfigValidationError:
    """处理Pydantic验证错误"""
    errors = error.errors()
    messages = []
    for err in errors:
        loc = " -> ".join(str(x) for x in err['loc'])
        messages.append(f"{loc}: {err['msg']}")
    return ConfigValidationError(f"配置验证失败：\n" + "\n".join(messages))
