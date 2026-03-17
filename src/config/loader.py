import yaml
import os
import re
from pathlib import Path
from typing import Optional

from .models import (
    AppConfig, FullModelConfig, MCPConfig, 
    PromptConfig, SkillsConfig, ModelConfig
)
from .validators import (
    ConfigValidationError, validate_required_configs,
    validate_api_key, handle_pydantic_error
)


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.configs: dict = {}
    
    def load_all(self) -> AppConfig:
        """加载所有配置并验证"""
        model_config = self._load_model_config()
        mcp_config = self._load_mcp_config()
        prompt_config = self._load_prompt_config()
        skills_config = self._load_skills_config()
        
        return AppConfig(
            model=model_config,
            mcp=mcp_config,
            prompts=prompt_config,
            skills=skills_config
        )
    
    def _load_yaml(self, filename: str) -> dict:
        """加载YAML文件"""
        file_path = self.config_dir / filename
        if not file_path.exists():
            raise ConfigValidationError(f"配置文件不存在：{file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = self._replace_env_vars(content)
        
        return yaml.safe_load(content)
    
    def _replace_env_vars(self, content: str) -> str:
        """替换环境变量"""
        pattern = r'\$\{([^}]+)\}'
        
        def replacer(match):
            env_var = match.group(1)
            value = os.getenv(env_var, "")
            return value
        
        return re.sub(pattern, replacer, content)
    
    def _load_model_config(self) -> FullModelConfig:
        """加载模型配置"""
        data = self._load_yaml("model_config.yaml")
        
        try:
            model_data = data.get('model', {})
            model_data['api_key'] = validate_api_key(
                model_data.get('api_key', ''), 
                'OPENAI_API_KEY'
            )
            
            config = FullModelConfig(**data)
            return config
        except Exception as e:
            if hasattr(e, 'errors'):
                raise handle_pydantic_error(e)
            raise
    
    def _load_mcp_config(self) -> MCPConfig:
        """加载MCP配置"""
        data = self._load_yaml("mcp_config.yaml")
        
        try:
            return MCPConfig(**data.get('mcp', {}))
        except Exception as e:
            if hasattr(e, 'errors'):
                raise handle_pydantic_error(e)
            raise
    
    def _load_prompt_config(self) -> PromptConfig:
        """加载提示词配置"""
        data = self._load_yaml("prompt_config.yaml")
        
        try:
            return PromptConfig(**data.get('prompts', {}))
        except Exception as e:
            if hasattr(e, 'errors'):
                raise handle_pydantic_error(e)
            raise
    
    def _load_skills_config(self) -> SkillsConfig:
        """加载Skill配置"""
        data = self._load_yaml("skills_config.yaml")
        
        try:
            return SkillsConfig(**data.get('skills', {}))
        except Exception as e:
            if hasattr(e, 'errors'):
                raise handle_pydantic_error(e)
            raise
    
    def get_config(self, key: str) -> Optional[any]:
        """获取指定配置"""
        return self.configs.get(key)
