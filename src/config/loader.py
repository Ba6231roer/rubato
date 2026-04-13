import yaml
from pathlib import Path
from typing import Optional, Tuple

from .models import (
    AppConfig, FullModelConfig, MCPConfig,
    PromptConfig, SkillsConfig, AgentConfig,
    ProjectConfig, FileToolsConfig, UnifiedToolsConfig
)
from .validators import (
    ConfigValidationError, validate_api_key, handle_pydantic_error, replace_env_vars
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
        prompt_config = self._load_config_section("prompt_config.yaml", "prompts", PromptConfig)
        skills_config = self._load_config_section("skills_config.yaml", "skills", SkillsConfig)
        agent_config = self._load_config_section(
            "agent_config.yaml", "agent", AgentConfig, optional=True, default=AgentConfig()
        )
        project_config = self._load_project_config()
        file_tools_config, unified_tools_config = self._load_tools_configs()

        return AppConfig(
            model=model_config,
            mcp=mcp_config,
            prompts=prompt_config,
            skills=skills_config,
            agent=agent_config,
            project=project_config,
            file_tools=file_tools_config,
            tools=unified_tools_config
        )

    def _load_yaml(self, filename: str) -> dict:
        """加载YAML文件"""
        file_path = self.config_dir / filename
        if not file_path.exists():
            raise ConfigValidationError(f"配置文件不存在：{file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = replace_env_vars(content, self.config_dir)

        return yaml.safe_load(content)

    def _safe_create_config(self, config_class: type, data: dict):
        """安全创建配置对象，统一处理Pydantic验证错误"""
        try:
            return config_class(**data)
        except Exception as e:
            if hasattr(e, 'errors'):
                raise handle_pydantic_error(e)
            raise

    def _load_config_section(self, filename: str, section: str, config_class: type,
                             optional: bool = False, default=None):
        """加载配置文件的指定section并创建配置对象

        Args:
            filename: YAML文件名
            section: 顶层section键名
            config_class: 配置模型类
            optional: 是否可选（可选配置文件不存在时返回default）
            default: 可选配置的默认返回值
        """
        try:
            data = self._load_yaml(filename)
            section_data = data.get(section, {})
            if not section_data and optional:
                return default
            return self._safe_create_config(config_class, section_data)
        except ConfigValidationError:
            if optional:
                return default
            raise

    def _load_model_config(self) -> FullModelConfig:
        """加载模型配置"""
        data = self._load_yaml("model_config.yaml")

        model_data = data.get('model', {})
        model_data['api_key'] = validate_api_key(
            model_data.get('api_key', ''),
            'OPENAI_API_KEY'
        )

        return self._safe_create_config(FullModelConfig, data)

    def _load_mcp_config(self) -> MCPConfig:
        """加载MCP配置"""
        data = self._load_yaml("mcp_config.yaml")

        mcp_data = data.get('mcp', {})
        migrated_data = AppConfig.migrate_old_config({'mcp': mcp_data})
        return self._safe_create_config(MCPConfig, migrated_data.get('mcp', {}))

    def _load_project_config(self) -> Optional[ProjectConfig]:
        """加载项目配置"""
        try:
            data = self._load_yaml("project_config.yaml")
            project_data = data.get('project', {})

            if not project_data:
                return None

            if 'root' in project_data:
                root_path = project_data['root']
                if not Path(root_path).is_absolute():
                    project_data['root'] = str(
                        (self.config_dir.parent / root_path).resolve()
                    )

            if 'workspace' in project_data:
                workspace_data = project_data['workspace']
                project_root = Path(project_data.get('root', self.config_dir.parent))

                if 'main' in workspace_data:
                    main_path = workspace_data['main']
                    if not Path(main_path).is_absolute():
                        workspace_data['main'] = str(
                            (project_root / main_path).resolve()
                        )

                if 'additional' in workspace_data:
                    workspace_data['additional'] = [
                        str((project_root / p).resolve()) if not Path(p).is_absolute() else p
                        for p in workspace_data['additional']
                    ]

            return self._safe_create_config(ProjectConfig, project_data)
        except ConfigValidationError:
            return None

    def _load_tools_configs(self) -> Tuple[Optional[FileToolsConfig], Optional[UnifiedToolsConfig]]:
        """加载工具配置（合并读取tools_config.yaml，避免重复IO）"""
        try:
            data = self._load_yaml("tools_config.yaml")
        except ConfigValidationError:
            return None, None

        file_tools_data = data.get('file_tools', {})
        unified_tools_data = data.get('tools', {})

        file_tools = self._safe_create_config(FileToolsConfig, file_tools_data) if file_tools_data else None
        unified_tools = self._safe_create_config(UnifiedToolsConfig, unified_tools_data) if unified_tools_data else None

        return file_tools, unified_tools

    def get_config(self, key: str) -> Optional[any]:
        """获取指定配置"""
        return self.configs.get(key)
