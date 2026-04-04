"""
QueryEngine 核心类实现

根据设计文档 2.1 节实现，管理单次对话的完整生命周期。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from ..skills.parser import SkillMetadata
from ..utils.logger import get_llm_logger


@dataclass
class FileStateCache:
    """文件状态缓存"""
    cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def get(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取文件状态"""
        return self.cache.get(file_path)
    
    def set(self, file_path: str, state: Dict[str, Any]) -> None:
        """设置文件状态"""
        self.cache[file_path] = state
    
    def remove(self, file_path: str) -> None:
        """移除文件状态"""
        self.cache.pop(file_path, None)
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
    
    def has(self, file_path: str) -> bool:
        """检查文件是否存在缓存"""
        return file_path in self.cache


@dataclass
class PermissionDenial:
    """权限拒绝记录"""
    tool_name: str
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AbortController:
    """中断控制器"""
    _aborted: bool = field(default=False, repr=False)
    _reason: Optional[str] = field(default=None, repr=False)
    
    def abort(self, reason: Optional[str] = None) -> None:
        """触发中断"""
        self._aborted = True
        self._reason = reason
    
    def is_aborted(self) -> bool:
        """检查是否已中断"""
        return self._aborted
    
    def get_reason(self) -> Optional[str]:
        """获取中断原因"""
        return self._reason
    
    def reset(self) -> None:
        """重置状态"""
        self._aborted = False
        self._reason = None


@dataclass
class Usage:
    """使用量统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    
    def add(self, other: 'Usage') -> None:
        """累加使用量"""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cost_usd += other.cost_usd


@dataclass
class SDKMessage:
    """SDK消息类型"""
    type: str
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def assistant(cls, content: str, **metadata) -> 'SDKMessage':
        """创建助手消息"""
        return cls(type="assistant", content=content, metadata=metadata)
    
    @classmethod
    def tool_use(cls, tool_name: str, tool_args: Dict, tool_call_id: str, **metadata) -> 'SDKMessage':
        """创建工具使用消息"""
        return cls(
            type="tool_use",
            content={"name": tool_name, "args": tool_args, "id": tool_call_id},
            metadata=metadata
        )
    
    @classmethod
    def tool_result(cls, tool_name: str, result: Any, tool_call_id: str, **metadata) -> 'SDKMessage':
        """创建工具结果消息"""
        return cls(
            type="tool_result",
            content={"name": tool_name, "result": result, "id": tool_call_id},
            metadata=metadata
        )
    
    @classmethod
    def error(cls, message: str, error_type: str = "unknown", **metadata) -> 'SDKMessage':
        """创建错误消息"""
        return cls(
            type="error",
            content={"message": message, "error_type": error_type},
            metadata=metadata
        )
    
    @classmethod
    def interrupt(cls, reason: Optional[str] = None, **metadata) -> 'SDKMessage':
        """创建中断消息"""
        return cls(
            type="interrupt",
            content={"reason": reason},
            metadata=metadata
        )
    
    @classmethod
    def result(cls, result: Any, **metadata) -> 'SDKMessage':
        """创建结果消息"""
        return cls(type="result", content=result, metadata=metadata)


@dataclass
class SubmitOptions:
    """提交选项"""
    stream: bool = True
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


Skill = Union[SkillMetadata, Dict[str, Any], str]


@dataclass
class QueryEngineConfig:
    """QueryEngine 配置"""
    cwd: str
    tools: List[BaseTool]
    skills: List[Skill]
    can_use_tool: Callable[[str, Dict[str, Any]], bool]
    get_app_state: Callable[[], Dict[str, Any]]
    set_app_state: Callable[[Dict[str, Any]], None]
    initial_messages: List[BaseMessage] = field(default_factory=list)
    read_file_cache: FileStateCache = field(default_factory=FileStateCache)
    custom_system_prompt: Optional[str] = None
    max_turns: Optional[int] = None
    max_budget_usd: Optional[float] = None
    json_schema: Optional[Dict[str, Any]] = None
    model_name: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class QueryEngine:
    """查询引擎，管理单次对话的完整生命周期"""
    
    def __init__(self, config: QueryEngineConfig):
        self.config = config
        self.mutable_messages: List[BaseMessage] = list(config.initial_messages)
        self.abort_controller = AbortController()
        self.permission_denials: List[PermissionDenial] = []
        self.total_usage = Usage()
        self.read_file_state = config.read_file_cache
        self.discovered_skill_names: Set[str] = set()
        self._session_id: str = str(uuid.uuid4())
        self._current_turn: int = 0
        self._is_running: bool = False
        self.logger = get_llm_logger()
    
    async def submit_message(
        self,
        prompt: str,
        options: Optional[SubmitOptions] = None
    ) -> AsyncGenerator[SDKMessage, None]:
        """提交消息并返回异步生成器
        
        Args:
            prompt: 用户输入
            options: 提交选项
            
        Yields:
            SDKMessage: 流式消息
        """
        options = options or SubmitOptions()
        
        self.abort_controller.reset()
        self._is_running = True
        self._current_turn = 0
        
        self.logger.log_agent_action("query_start", {
            "session_id": self._session_id,
            "prompt_length": len(prompt),
            "max_turns": self.config.max_turns,
            "max_budget_usd": self.config.max_budget_usd
        })
        
        try:
            self.mutable_messages.append(HumanMessage(content=prompt))
            
            yield SDKMessage.assistant(
                content="",
                metadata={"phase": "init", "session_id": self._session_id}
            )
            
            async for message in self._run_react_loop(options):
                if self.abort_controller.is_aborted():
                    yield SDKMessage.interrupt(
                        reason=self.abort_controller.get_reason(),
                        session_id=self._session_id
                    )
                    return
                
                if self._check_budget_exceeded():
                    yield SDKMessage.error(
                        message=f"预算超限: 已使用 ${self.total_usage.cost_usd:.4f}，限制 ${self.config.max_budget_usd}",
                        error_type="budget_exceeded"
                    )
                    return
                
                if self._check_max_turns_reached():
                    yield SDKMessage.error(
                        message=f"达到最大轮次限制: {self.config.max_turns}",
                        error_type="max_turns_reached"
                    )
                    return
                
                yield message
            
            yield SDKMessage.result(
                result=self._get_final_result(),
                session_id=self._session_id,
                total_turns=self._current_turn
            )
            
        except asyncio.CancelledError:
            yield SDKMessage.interrupt(
                reason="任务被取消",
                session_id=self._session_id
            )
        except Exception as e:
            self.logger.log_error("query_engine", e)
            yield SDKMessage.error(
                message=str(e),
                error_type=type(e).__name__,
                session_id=self._session_id
            )
        finally:
            self._is_running = False
            self.logger.log_agent_action("query_end", {
                "session_id": self._session_id,
                "total_turns": self._current_turn,
                "total_tokens": self.total_usage.total_tokens,
                "cost_usd": self.total_usage.cost_usd
            })
    
    async def _run_react_loop(
        self,
        options: SubmitOptions
    ) -> AsyncGenerator[SDKMessage, None]:
        """运行 ReAct 循环
        
        Args:
            options: 提交选项
            
        Yields:
            SDKMessage: 流式消息
        """
        self._current_turn += 1
        
        yield SDKMessage.assistant(
            content=f"[轮次 {self._current_turn}] 开始处理...",
            metadata={"phase": "reason", "turn": self._current_turn}
        )
        
        for skill in self.config.skills:
            skill_name = self._get_skill_name(skill)
            if skill_name:
                yield SDKMessage.assistant(
                    content=f"检测到 Skill: {skill_name}",
                    metadata={"phase": "skill_detection", "skill": skill_name}
                )
        
        yield SDKMessage.assistant(
            content="处理完成",
            metadata={"phase": "complete", "turn": self._current_turn}
        )
    
    def _get_skill_name(self, skill: Skill) -> Optional[str]:
        """获取 Skill 名称"""
        if isinstance(skill, SkillMetadata):
            return skill.name
        elif isinstance(skill, dict):
            return skill.get("name")
        elif isinstance(skill, str):
            return skill
        return None
    
    def _check_budget_exceeded(self) -> bool:
        """检查预算是否超限"""
        if self.config.max_budget_usd is None:
            return False
        return self.total_usage.cost_usd >= self.config.max_budget_usd
    
    def _check_max_turns_reached(self) -> bool:
        """检查是否达到最大轮次"""
        if self.config.max_turns is None:
            return False
        return self._current_turn >= self.config.max_turns
    
    def _get_final_result(self) -> str:
        """获取最终结果"""
        for msg in reversed(self.mutable_messages):
            if isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            return item["text"]
                        elif isinstance(item, str):
                            return item
        return "任务已完成"
    
    def interrupt(self, reason: Optional[str] = None) -> None:
        """中断当前查询
        
        Args:
            reason: 中断原因
        """
        self.abort_controller.abort(reason)
        self.logger.log_agent_action("query_interrupted", {
            "session_id": self._session_id,
            "reason": reason
        })
    
    def get_messages(self) -> List[BaseMessage]:
        """获取消息列表
        
        Returns:
            List[BaseMessage]: 消息列表
        """
        return list(self.mutable_messages)
    
    def get_session_id(self) -> str:
        """获取会话ID
        
        Returns:
            str: 会话ID
        """
        return self._session_id
    
    def get_usage(self) -> Usage:
        """获取使用量统计
        
        Returns:
            Usage: 使用量统计
        """
        return self.total_usage
    
    def is_running(self) -> bool:
        """检查是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return self._is_running
    
    def add_permission_denial(self, tool_name: str, reason: str) -> None:
        """添加权限拒绝记录
        
        Args:
            tool_name: 工具名称
            reason: 拒绝原因
        """
        self.permission_denials.append(PermissionDenial(
            tool_name=tool_name,
            reason=reason
        ))
        self.logger.log_agent_action("permission_denied", {
            "session_id": self._session_id,
            "tool_name": tool_name,
            "reason": reason
        })
    
    def clear_messages(self) -> None:
        """清空消息列表"""
        self.mutable_messages.clear()
        self._session_id = str(uuid.uuid4())
        self._current_turn = 0
        self.total_usage = Usage()
        self.permission_denials.clear()
        self.abort_controller.reset()
    
    def add_message(self, message: BaseMessage) -> None:
        """添加消息
        
        Args:
            message: 消息对象
        """
        self.mutable_messages.append(message)
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称
        
        Returns:
            List[str]: 工具名称列表
        """
        return [tool.name for tool in self.config.tools]
    
    def get_skill_names(self) -> List[str]:
        """获取所有 Skill 名称
        
        Returns:
            List[str]: Skill 名称列表
        """
        names = []
        for skill in self.config.skills:
            name = self._get_skill_name(skill)
            if name:
                names.append(name)
        return names
    
    def update_usage(self, prompt_tokens: int, completion_tokens: int, cost_usd: float = 0.0) -> None:
        """更新使用量统计
        
        Args:
            prompt_tokens: 提示词 token 数
            completion_tokens: 完成 token 数
            cost_usd: 费用（美元）
        """
        self.total_usage.prompt_tokens += prompt_tokens
        self.total_usage.completion_tokens += completion_tokens
        self.total_usage.total_tokens += prompt_tokens + completion_tokens
        self.total_usage.cost_usd += cost_usd
