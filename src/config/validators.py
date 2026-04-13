import re
import os
from pathlib import Path
from typing import List, Any, Optional

from pydantic import ValidationError


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


def replace_env_vars(content: str, config_dir: Optional[Path] = None) -> str:
    """替换环境变量，支持系统环境变量和特殊变量

    Args:
        content: 需要替换的文本内容
        config_dir: 配置目录路径，支持 PROJECT_ROOT 和 CONFIG_DIR 特殊变量
    """
    pattern = r'\$\{([^}]+)\}'

    def replacer(match):
        env_var = match.group(1)
        if config_dir is not None:
            if env_var == 'PROJECT_ROOT':
                return str(config_dir.parent.resolve())
            elif env_var == 'CONFIG_DIR':
                return str(config_dir.resolve())
        if env_var == 'HOME':
            return str(Path.home())
        return os.getenv(env_var, "")

    return re.sub(pattern, replacer, content)
