from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum


class PermissionMode(str, Enum):
    ask = "ask"
    allow = "allow"
    deny = "deny"


class WorkspaceConfig(BaseModel):
    main: Path
    additional: List[Path] = []
    excluded: List[str] = []

    @field_validator('main')
    @classmethod
    def validate_main(cls, v):
        if not v:
            raise ValueError('main workspace path cannot be empty')
        return v

    @field_validator('additional')
    @classmethod
    def validate_additional(cls, v):
        for path in v:
            if not path:
                raise ValueError('additional workspace paths cannot contain empty paths')
        return v


class ProjectConfig(BaseModel):
    name: str
    root: Path
    workspace: WorkspaceConfig

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('project name cannot be empty')
        return v.strip()

    @field_validator('root')
    @classmethod
    def validate_root(cls, v):
        if not v:
            raise ValueError('project root cannot be empty')
        return v


class FileToolsConfig(BaseModel):
    enabled: bool = True
    permission_mode: PermissionMode = PermissionMode.ask
    custom_permissions: Dict[str, PermissionMode] = {}
    default_permissions: PermissionMode = PermissionMode.ask
    audit: bool = True

    @field_validator('permission_mode', 'default_permissions', mode='before')
    @classmethod
    def validate_permission_mode(cls, v):
        if isinstance(v, str):
            try:
                return PermissionMode(v)
            except ValueError:
                raise ValueError(f'permission_mode must be one of {[m.value for m in PermissionMode]}')
        return v

    @field_validator('custom_permissions', mode='before')
    @classmethod
    def validate_custom_permissions(cls, v):
        if isinstance(v, dict):
            validated = {}
            for key, value in v.items():
                if isinstance(value, str):
                    try:
                        validated[key] = PermissionMode(value)
                    except ValueError:
                        raise ValueError(f'custom_permissions[{key}] must be one of {[m.value for m in PermissionMode]}')
                else:
                    validated[key] = value
            return validated
        return v


class WorkspaceRestrictionConfig(BaseModel):
    allowed_subdirs: List[str] = []
    excluded_patterns: List[str] = []
    read_only_dirs: List[str] = []
    
    @field_validator('allowed_subdirs', 'excluded_patterns', 'read_only_dirs')
    @classmethod
    def validate_list(cls, v):
        if not isinstance(v, list):
            raise ValueError('must be a list')
        return v


class RoleFileToolsConfig(BaseModel):
    enabled: bool = True
    workspace: Optional[WorkspaceConfig] = None
    workspace_restriction: Optional[WorkspaceRestrictionConfig] = None
    permissions: Optional[Dict[str, Any]] = None
    audit: bool = True
    
    @field_validator('permissions', mode='before')
    @classmethod
    def validate_permissions(cls, v):
        if v is None:
            return {
                'default': PermissionMode.ask,
                'custom': {}
            }
        if isinstance(v, dict):
            if 'default' not in v:
                v['default'] = PermissionMode.ask
            if 'custom' not in v:
                v['custom'] = {}
            return v
        return v


class RoleModelConfig(BaseModel):
    inherit: bool = True
    provider: Optional[str] = None
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        if v is not None and not 0 <= v <= 1:
            raise ValueError('temperature must be between 0 and 1')
        return v


class RoleExecutionConfig(BaseModel):
    max_context_tokens: int = 80000
    timeout: int = 300
    recursion_limit: Optional[int] = None
    sub_agent_recursion_limit: Optional[int] = None

    @field_validator('max_context_tokens', 'timeout')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class RoleToolsConfig(BaseModel):
    """角色工具配置"""
    builtin: Optional[Dict[str, Any]] = None
    mcp: Optional[Dict[str, Any]] = None
    skills: Optional[List[str]] = None

    @field_validator('builtin', mode='before')
    @classmethod
    def validate_builtin(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, bool):
            return {'enabled': v}
        if isinstance(v, list):
            return {'enabled': True, 'tools': v}
        return v


class RoleConfig(BaseModel):
    name: str
    description: str
    system_prompt_file: str
    model: RoleModelConfig = RoleModelConfig()
    execution: RoleExecutionConfig = RoleExecutionConfig()
    available_tools: List[str] = []
    file_tools: Optional[RoleFileToolsConfig] = None
    tools: Optional[RoleToolsConfig] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('name cannot be empty')
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('name can only contain letters, numbers, hyphens and underscores')
        return v.strip().lower()


class ModelConfig(BaseModel):
    provider: str
    name: str
    api_key: str
    auth: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('temperature must be between 0 and 1')
        return v

    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        allowed = ['openai', 'anthropic', 'local']
        if v not in allowed:
            raise ValueError(f'provider must be one of {allowed}')
        return v


class FallbackModelConfig(BaseModel):
    provider: str
    name: str
    api_key: str
    base_url: Optional[str] = None


class ModelParameters(BaseModel):
    retry_times: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0

    @field_validator('retry_times', 'retry_delay', 'timeout')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class FullModelConfig(BaseModel):
    model: ModelConfig
    fallback_model: Optional[FallbackModelConfig] = None
    parameters: ModelParameters = ModelParameters()


class MCPConnectionConfig(BaseModel):
    retry_times: int = 3
    retry_delay: int = 5
    timeout: int = 30

    @field_validator('retry_times', 'retry_delay', 'timeout')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class BrowserViewportConfig(BaseModel):
    width: int = 1280
    height: int = 720


class BrowserConfig(BaseModel):
    type: str = "chromium"
    headless: bool = False
    viewport: BrowserViewportConfig = BrowserViewportConfig()


class ExecutionConfig(BaseModel):
    default_timeout: int = 30000
    slow_mo: int = 0
    video_dir: str = "logs/videos"
    screenshot_dir: str = "logs/screenshots"


class PlaywrightConfig(BaseModel):
    enabled: bool = True
    command: str = "npx"
    args: List[str] = ["-y", "@playwright/mcp"]
    connection: MCPConnectionConfig = MCPConnectionConfig()
    browser: BrowserConfig = BrowserConfig()
    execution: ExecutionConfig = ExecutionConfig()


class MCPServerConfig(BaseModel):
    enabled: bool = True
    command: str
    args: List[str] = []
    connection: Optional[dict] = None
    browser: Optional[dict] = None
    execution: Optional[dict] = None


class MCPConfig(BaseModel):
    servers: Dict[str, MCPServerConfig] = {}


class PromptVariables(BaseModel):
    project_name: str = "Rubato"
    default_browser: str = "chromium"
    default_timeout: int = 30000


class PromptConfig(BaseModel):
    system_prompt_file: str = "prompts/system_prompt.txt"
    skill_loading_prompt_file: str = "prompts/skill_loading_prompt.txt"
    variables: PromptVariables = PromptVariables()


class SkillLoadingConfig(BaseModel):
    trigger_matching: bool = True
    max_loaded_skills: int = 3


class SkillsConfig(BaseModel):
    directory: str = "skills"
    auto_load: bool = True
    enabled_skills: List[str] = []
    skill_loading: SkillLoadingConfig = SkillLoadingConfig()


class AgentExecutionConfig(BaseModel):
    recursion_limit: int = 100
    sub_agent_recursion_limit: int = 50
    default_timeout: int = 300

    @field_validator('recursion_limit', 'sub_agent_recursion_limit', 'default_timeout')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class MessageCompressionConfig(BaseModel):
    enabled: bool = True
    max_tokens: int = 50000
    keep_recent: int = 6
    summary_max_length: int = 300
    history_summary_count: int = 10
    autocompact_buffer_tokens: int = 13000
    manual_compact_buffer_tokens: int = 3000
    warning_threshold_buffer_tokens: int = 20000
    snip_keep_recent: int = 6
    tool_result_persist_threshold: int = 50000
    tool_result_budget_per_message: int = 200000
    max_consecutive_failures: int = 3

    @field_validator('max_tokens', 'keep_recent', 'summary_max_length', 'history_summary_count',
                     'autocompact_buffer_tokens', 'manual_compact_buffer_tokens',
                     'warning_threshold_buffer_tokens', 'snip_keep_recent',
                     'tool_result_persist_threshold', 'tool_result_budget_per_message',
                     'max_consecutive_failures')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class AgentLoggingConfig(BaseModel):
    log_token_estimation: bool = True
    log_compression_stats: bool = True
    log_step_details: bool = True
    log_format: str = "compact"
    tool_log_mode: str = "summary"


class AgentConfig(BaseModel):
    max_context_tokens: int = 80000
    message_compression: MessageCompressionConfig = MessageCompressionConfig()
    execution: AgentExecutionConfig = AgentExecutionConfig()
    logging: AgentLoggingConfig = AgentLoggingConfig()

    @field_validator('max_context_tokens')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class FileToolsSubConfig(BaseModel):
    """文件工具子配置（用于统一工具配置）"""
    enabled: bool = True
    permission_mode: PermissionMode = PermissionMode.ask
    workspace: Optional[WorkspaceConfig] = None
    permissions: Dict[str, PermissionMode] = {}
    audit: bool = True

    @field_validator('permission_mode', mode='before')
    @classmethod
    def validate_permission_mode(cls, v):
        if isinstance(v, str):
            try:
                return PermissionMode(v)
            except ValueError:
                raise ValueError(f'permission_mode must be one of {[m.value for m in PermissionMode]}')
        return v

    @field_validator('permissions', mode='before')
    @classmethod
    def validate_permissions(cls, v):
        if isinstance(v, dict):
            validated = {}
            for key, value in v.items():
                if isinstance(value, str):
                    try:
                        validated[key] = PermissionMode(value)
                    except ValueError:
                        raise ValueError(f'permissions[{key}] must be one of {[m.value for m in PermissionMode]}')
                else:
                    validated[key] = value
            return validated
        return v


class ShellToolConfig(BaseModel):
    """Shell工具配置"""
    enabled: bool = True
    safe_mode: bool = True
    allowed_commands: List[str] = []


class SpawnAgentConfig(BaseModel):
    """spawn_agent工具配置"""
    enabled: bool = True


class BuiltinToolsConfig(BaseModel):
    """系统内置工具配置（包含spawn_agent, shell_tool, file_tools）"""
    enabled: bool = True
    spawn_agent: SpawnAgentConfig = SpawnAgentConfig()
    shell_tool: ShellToolConfig = ShellToolConfig()
    file_tools: FileToolsSubConfig = FileToolsSubConfig()


class MCPToolsConfig(BaseModel):
    """MCP工具配置"""
    config_file: str = "mcp_config.yaml"
    auto_connect: bool = True
    cache_ttl: int = 300


class SkillsToolsConfig(BaseModel):
    """Skill配置"""
    config_file: str = "skills_config.yaml"
    auto_load_metadata: bool = True


class ToolDocsConfig(BaseModel):
    """工具说明文档配置"""
    auto_inject: bool = True
    inject_position: str = "after_prompt"
    format: str = "markdown"
    include_examples: bool = True


class UnifiedToolsConfig(BaseModel):
    """统一工具配置"""
    builtin: BuiltinToolsConfig = BuiltinToolsConfig()
    mcp: MCPToolsConfig = MCPToolsConfig()
    skills: SkillsToolsConfig = SkillsToolsConfig()
    tool_docs: ToolDocsConfig = ToolDocsConfig()


class AppConfig(BaseModel):
    model: FullModelConfig
    mcp: Optional[MCPConfig] = None
    prompts: PromptConfig
    skills: SkillsConfig
    agent: AgentConfig = AgentConfig()
    project: Optional[ProjectConfig] = None
    file_tools: Optional[FileToolsConfig] = None
    tools: Optional[UnifiedToolsConfig] = None

    @classmethod
    def migrate_old_config(cls, data: dict) -> dict:
        if 'mcp' in data and data['mcp'] is not None:
            mcp_data = data['mcp']
            if 'servers' not in mcp_data:
                servers = {}
                for server_name, server_config in mcp_data.items():
                    if isinstance(server_config, dict) and 'command' in server_config:
                        servers[server_name] = server_config
                data['mcp'] = {'servers': servers}
        return data
