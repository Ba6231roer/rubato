from pydantic import BaseModel, field_validator
from typing import Optional, List


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


class MCPConfig(BaseModel):
    playwright: PlaywrightConfig


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

    @field_validator('recursion_limit', 'sub_agent_recursion_limit')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('must be positive')
        return v


class AgentConfig(BaseModel):
    max_context_tokens: int = 80000
    execution: AgentExecutionConfig = AgentExecutionConfig()


class AppConfig(BaseModel):
    model: FullModelConfig
    mcp: MCPConfig
    prompts: PromptConfig
    skills: SkillsConfig
    agent: AgentConfig = AgentConfig()
