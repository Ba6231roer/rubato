from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any


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


class RoleConfig(BaseModel):
    name: str
    description: str
    system_prompt_file: str
    model: RoleModelConfig = RoleModelConfig()
    execution: RoleExecutionConfig = RoleExecutionConfig()
    available_tools: List[str] = []
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

    @field_validator('max_tokens', 'keep_recent', 'summary_max_length', 'history_summary_count')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class AgentLoggingConfig(BaseModel):
    log_token_estimation: bool = True
    log_compression_stats: bool = True
    log_step_details: bool = True


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


class AppConfig(BaseModel):
    model: FullModelConfig
    mcp: Optional[MCPConfig] = None
    prompts: PromptConfig
    skills: SkillsConfig
    agent: AgentConfig = AgentConfig()

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
