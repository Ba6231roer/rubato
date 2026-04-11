"""
SubAgent 类型定义

根据设计文档 11.2 节实现，定义 SubAgent 的数据结构。
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolInheritanceMode(str, Enum):
    """工具继承模式"""
    
    INHERIT_ALL = "inherit_all"
    """继承所有父工具
    
    - SubAgent 继承父 Agent 的所有工具
    - 受 tool_permissions 的 allowlist/denylist 约束
    - 适用于通用任务处理
    """
    
    INHERIT_SELECTED = "inherit_selected"
    """继承选定的工具
    
    - SubAgent 只继承 available_tools 中指定的工具
    - 适用于特定任务场景
    - 需要明确指定工具列表
    """
    
    INDEPENDENT = "independent"
    """独立工具集
    
    - SubAgent 使用完全独立的工具集
    - 不继承父 Agent 的任何工具
    - 需要通过 available_tools 指定工具
    """


class SubAgentState(str, Enum):
    """SubAgent 状态"""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ToolPermissionConfig(BaseModel):
    """工具权限配置"""
    
    inherit_from_parent: bool = Field(
        default=True,
        description="是否从父 Agent 继承工具权限"
    )
    allowlist: Optional[List[str]] = Field(
        default=None,
        description="允许的工具列表（白名单）"
    )
    denylist: Optional[List[str]] = Field(
        default=None,
        description="禁止的工具列表（黑名单）"
    )
    custom_permissions: Dict[str, str] = Field(
        default_factory=dict,
        description="自定义工具权限映射"
    )


class SubAgentExecutionConfig(BaseModel):
    """SubAgent 执行配置"""
    
    timeout: int = Field(
        default=120,
        description="执行超时时间（秒）"
    )
    max_retries: int = Field(
        default=0,
        description="最大重试次数"
    )
    recursion_limit: int = Field(
        default=50,
        description="递归调用限制"
    )
    max_context_tokens: Optional[int] = Field(
        default=None,
        description="最大上下文 token 数"
    )


class SubAgentModelConfig(BaseModel):
    """SubAgent 模型配置"""
    
    inherit: bool = Field(
        default=True,
        description="是否继承父 Agent 的模型配置"
    )
    provider: Optional[str] = Field(
        default=None,
        description="模型提供商"
    )
    name: Optional[str] = Field(
        default=None,
        description="模型名称"
    )
    temperature: Optional[float] = Field(
        default=None,
        description="温度参数",
        ge=0.0,
        le=1.0
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="最大输出 token 数"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API 密钥"
    )
    base_url: Optional[str] = Field(
        default=None,
        description="API 基础 URL"
    )


class SubAgentDefinition(BaseModel):
    """SubAgent 定义结构
    
    参考 Claude Code 的 AgentDefinition 设计
    """
    
    name: str = Field(
        ...,
        description="SubAgent 名称（唯一标识）"
    )
    description: str = Field(
        default="",
        description="SubAgent 描述"
    )
    version: str = Field(
        default="1.0",
        description="版本号"
    )
    
    system_prompt: Optional[str] = Field(
        default=None,
        description="系统提示词（内联）"
    )
    system_prompt_file: Optional[str] = Field(
        default=None,
        description="系统提示词文件路径"
    )
    
    model: SubAgentModelConfig = Field(
        default_factory=SubAgentModelConfig,
        description="模型配置"
    )
    execution: SubAgentExecutionConfig = Field(
        default_factory=SubAgentExecutionConfig,
        description="执行配置"
    )
    
    tool_inheritance: ToolInheritanceMode = Field(
        default=ToolInheritanceMode.INHERIT_ALL,
        description="工具继承模式"
    )
    tool_permissions: ToolPermissionConfig = Field(
        default_factory=ToolPermissionConfig,
        description="工具权限配置"
    )
    available_tools: Optional[List[str]] = Field(
        default=None,
        description="可用工具列表（当 tool_inheritance=INDEPENDENT 时使用）"
    )
    skills: Optional[List[str]] = Field(
        default=None,
        description="Skills 列表（从角色配置继承）"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="元数据"
    )
    
    def get_system_prompt_content(self, base_dir: Optional[Path] = None) -> str:
        """获取系统提示词内容
        
        Args:
            base_dir: 基础目录（用于解析相对路径）
            
        Returns:
            系统提示词内容
        """
        if self.system_prompt:
            return self.system_prompt
        
        if self.system_prompt_file:
            prompt_path = Path(self.system_prompt_file)
            if base_dir and not prompt_path.is_absolute():
                prompt_path = base_dir / prompt_path
            
            if prompt_path.exists():
                return prompt_path.read_text(encoding='utf-8')
        
        return f"你是一个名为 {self.name} 的子智能体，负责执行特定任务。"


class SubAgentInstance(BaseModel):
    """SubAgent 实例"""
    
    instance_id: str = Field(..., description="实例 ID")
    name: str = Field(..., description="SubAgent 名称")
    definition: SubAgentDefinition = Field(..., description="SubAgent 定义")
    
    state: SubAgentState = Field(
        default=SubAgentState.CREATED,
        description="当前状态"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="开始执行时间"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="完成时间"
    )
    
    task: str = Field(..., description="任务描述")
    result: Optional[str] = Field(
        default=None,
        description="执行结果"
    )
    error: Optional[str] = Field(
        default=None,
        description="错误信息"
    )
    
    parent_session_id: Optional[str] = Field(
        default=None,
        description="父会话 ID"
    )
    depth: int = Field(
        default=0,
        description="递归深度"
    )
    
    tool_calls: int = Field(default=0, description="工具调用次数")
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token 使用统计"
    )
    
    class Config:
        arbitrary_types_allowed = True


class SubAgentSpawnOptions(BaseModel):
    """SubAgent 创建选项"""
    
    agent_name: str = Field(..., description="SubAgent 名称")
    task: str = Field(..., description="任务描述")
    system_prompt: Optional[str] = Field(
        default=None,
        description="自定义系统提示词"
    )
    inherit_parent_tools: bool = Field(
        default=True,
        description="是否继承父 Agent 的工具"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="会话 ID（用于递归深度控制）"
    )
    max_recursion_depth: int = Field(
        default=5,
        description="最大递归深度"
    )
    timeout: Optional[int] = Field(
        default=None,
        description="执行超时时间（秒）"
    )
    tool_inheritance: Optional[ToolInheritanceMode] = Field(
        default=None,
        description="工具继承模式"
    )
    available_tools: Optional[List[str]] = Field(
        default=None,
        description="可用工具列表"
    )
