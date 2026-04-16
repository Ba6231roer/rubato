"""
QueryEngine 核心类实现

根据设计文档 2.1 节实现，管理单次对话的完整生命周期。
"""

import asyncio
import json
import os
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

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import BaseTool

from ..context.compressor import ContextCompressor
from ..context.conversation_history import ConversationHistory, ConversationTurn, AssistantStep
from ..context.session_storage import SessionStorage, SessionMetadata, SubSessionRef
from ..context.system_prompt_registry import SystemPromptRegistry
from ..context.task_intent_manager import TaskIntentManager
from ..context.tool_result_storage import ToolResultStorage, ContentReplacementState
from ..skills.parser import SkillMetadata
from ..utils.logger import get_llm_logger
from .llm_wrapper import LLMCaller


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
    llm: Any
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
    compression_enabled: bool = True
    max_context_tokens: int = 80000
    autocompact_buffer_tokens: int = 13000
    keep_recent: int = 6
    snip_keep_recent: int = 6
    tool_result_persist_threshold: int = 50000
    tool_result_budget_per_message: int = 200000
    max_consecutive_failures: int = 3
    llm_timeout: Optional[float] = None
    retry_max_count: int = 3
    retry_initial_delay: float = 10.0
    retry_max_delay: float = 60.0
    system_prompt_registry: Optional[SystemPromptRegistry] = None
    conversation_history: Optional[ConversationHistory] = None
    skill_stale_timeout_seconds: int = 300
    logging_config: Optional[Any] = None
    session_storage: Optional[SessionStorage] = None
    role_name: str = ""
    task_intent_protection_enabled: bool = True
    task_intent_full_threshold: int = 2000
    task_intent_token_budget: int = 10000


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
        self._reactive_compact_attempted: bool = False
        self.logger = get_llm_logger()
        self._session_storage: Optional[SessionStorage] = config.session_storage
        if self._session_storage:
            skill_names = [s.name for s in config.skills if hasattr(s, 'name')]
            self._session_storage.save_session(
                self._session_id, [],
                metadata={
                    "role": config.role_name,
                    "model": config.model_name or "",
                    "skills": skill_names,
                },
            )
        
        # 创建 LLMCaller，传递 logger 和 timeout
        timeout = config.llm_timeout if config.llm_timeout is not None else 300.0
        
        if isinstance(config.llm, LLMCaller):
            self.llm_caller = config.llm
            self.llm_caller.tools = config.tools
            self.llm_caller.system_prompt = config.custom_system_prompt
            self.llm_caller.system_prompt_registry = config.system_prompt_registry
            self.llm_caller.logger = self.logger
            self.llm_caller.timeout = timeout
            self.llm_caller.max_context_tokens = config.max_context_tokens
            self.llm_caller.retry_max_count = config.retry_max_count
            self.llm_caller.retry_initial_delay = config.retry_initial_delay
            self.llm_caller.retry_max_delay = config.retry_max_delay
        else:
            self.llm_caller = LLMCaller(
                llm=config.llm,
                tools=config.tools,
                system_prompt=config.custom_system_prompt,
                logger=self.logger,
                timeout=timeout,
                max_context_tokens=config.max_context_tokens,
                retry_max_count=config.retry_max_count,
                retry_initial_delay=config.retry_initial_delay,
                retry_max_delay=config.retry_max_delay,
            )
        
        self._tool_map: Dict[str, BaseTool] = {
            tool.name: tool for tool in config.tools
        }

        self.system_prompt_registry = config.system_prompt_registry
        self.conversation_history = config.conversation_history or ConversationHistory()
        self.skill_stale_timeout_seconds = config.skill_stale_timeout_seconds
        self._compression_enabled = config.compression_enabled
        self.logging_config = config.logging_config

        self._task_intent_manager: Optional[TaskIntentManager] = None
        if config.task_intent_protection_enabled and self._compression_enabled:
            session_dir = os.path.join(config.cwd, ".rubato", "sessions", self._session_id)
            self._task_intent_manager = TaskIntentManager(
                session_dir=session_dir,
                full_threshold=config.task_intent_full_threshold,
                token_budget=config.task_intent_token_budget,
            )
        if self._compression_enabled:
            session_dir = os.path.join(config.cwd, ".rubato", "sessions", self._session_id)
            self._tool_result_storage = ToolResultStorage(
                session_dir=session_dir,
                persist_threshold=config.tool_result_persist_threshold,
                message_budget=config.tool_result_budget_per_message,
            )
            self._content_replacement_state = ContentReplacementState()
            self._compressor = ContextCompressor(
                llm_caller=self.llm_caller,
                max_context_tokens=config.max_context_tokens,
                autocompact_buffer_tokens=config.autocompact_buffer_tokens,
                keep_recent=config.keep_recent,
                snip_keep_recent=config.snip_keep_recent,
                max_consecutive_failures=config.max_consecutive_failures,
                tool_result_storage=self._tool_result_storage,
                content_replacement_state=self._content_replacement_state,
                logger=self.logger,
                task_intent_manager=self._task_intent_manager,
            )
        else:
            self._tool_result_storage = None
            self._content_replacement_state = None
            self._compressor = None
    
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
            if self._task_intent_manager is not None:
                self._task_intent_manager.extract_task_intent(prompt)
            self.conversation_history.start_turn(HumanMessage(content=prompt))
            
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
            if self._session_storage and self.mutable_messages:
                try:
                    self._session_storage.append_messages(
                        self._session_id, self.mutable_messages,
                        metadata={"role": self.config.role_name, "model": self.config.model_name or ""},
                    )
                except Exception:
                    pass
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
        
        这是 Query Engine 的核心方法，实现了完整的 ReAct 循环：
        1. 调用 LLM 获取响应
        2. 检测并执行工具调用
        3. 处理工具结果
        4. 循环直到任务完成或达到限制
        
        Args:
            options: 提交选项
            
        Yields:
            SDKMessage: 流式消息事件
        """
        max_no_tool_turns = 3
        no_tool_turn_count = 0
        
        while self._current_turn < (self.config.max_turns or 100):
            self._current_turn += 1
            self._reactive_compact_attempted = False
            
            should_log_steps = (
                self.logging_config is None
                or getattr(self.logging_config, "log_step_details", True)
            )
            if should_log_steps:
                self.logger.log_agent_action("react_loop_start", {
                    "session_id": self._session_id,
                    "turn": self._current_turn,
                    "max_turns": self.config.max_turns,
                    "message_count": len(self.mutable_messages)
                })

            await self._run_compression_pipeline()

            if self._compressor is not None:
                estimated_tokens = self._compressor.estimate_tokens(self.mutable_messages)
                warning_state = self._compressor.calculate_token_warning_state(estimated_tokens)
                if should_log_steps:
                    self.logger.log_agent_action("token_estimation", {
                        "session_id": self._session_id,
                        "turn": self._current_turn,
                        "estimated_tokens": estimated_tokens,
                        "warning_state": warning_state,
                    })

            if self._check_blocking_limit():
                force_success = await self._force_compact()
                if force_success:
                    self.logger.log_agent_action("blocking_limit_recovered", {
                        "session_id": self._session_id,
                        "turn": self._current_turn,
                    })
                else:
                    yield SDKMessage.error(
                        message="上下文已达到阻塞限制，请开始新对话或清理上下文",
                        error_type="blocking_limit_reached"
                    )
                    break
            
            yield SDKMessage.assistant(
                content="",
                metadata={
                    "phase": "reason_start",
                    "turn": self._current_turn
                }
            )
            
            llm_response = None
            prompt_too_long_detected = False
            async for chunk in self._stream_llm_call():
                if chunk.get("type") == "text_delta":
                    yield SDKMessage.assistant(
                        content=chunk.get("text", ""),
                        metadata={"phase": "streaming"}
                    )
                elif chunk.get("type") == "tool_call_start":
                    tool_info = chunk.get("tool", {})
                    yield SDKMessage.tool_use(
                        tool_name=tool_info.get("name"),
                        tool_args=tool_info.get("args", {}),
                        tool_call_id=tool_info.get("id"),
                        turn=self._current_turn
                    )
                elif chunk.get("type") == "complete":
                    llm_response = chunk.get("response")
                elif chunk.get("type") == "error":
                    error_msg = chunk.get("message", "")
                    error_lower = error_msg.lower()
                    if any(kw in error_lower for kw in ["prompt too long", "context_length_exceeded", "context length", "max_tokens", "token limit"]):
                        prompt_too_long_detected = True
                    else:
                        yield SDKMessage.error(
                            message=error_msg,
                            error_type="llm_error"
                        )
            
            if prompt_too_long_detected:
                recovered = await self._handle_prompt_too_long()
                if recovered:
                    self.logger.log_agent_action("prompt_too_long_recovered", {
                        "session_id": self._session_id,
                        "turn": self._current_turn,
                    })
                    continue
                yield SDKMessage.error(
                    message="上下文过长导致API请求失败，压缩后仍无法恢复",
                    error_type="prompt_too_long"
                )
                break

            if llm_response is None:
                yield SDKMessage.error(
                    message="LLM 响应为空",
                    error_type="empty_response"
                )
                break
            
            self.mutable_messages.append(llm_response)
            self.conversation_history.append_assistant_step(llm_response, tool_results=[])
            
            self._update_usage_from_response(llm_response)
            
            if not hasattr(llm_response, 'tool_calls') or not llm_response.tool_calls:
                no_tool_turn_count += 1
                
                if should_log_steps:
                    self.logger.log_agent_action("no_tool_call", {
                        "session_id": self._session_id,
                        "turn": self._current_turn,
                        "no_tool_turn_count": no_tool_turn_count,
                        "content_preview": llm_response.content[:200] if llm_response.content else ""
                    })
                
                content_str = str(llm_response.content) if llm_response.content else ""
                completion_indicators = [
                    "完成", "已完成", "成功", "结束", "完毕",
                    "测试报告", "汇总", "结果如下"
                ]
                
                task_seems_complete = any(
                    indicator in content_str 
                    for indicator in completion_indicators
                ) and len(content_str) > 100
                
                if task_seems_complete or no_tool_turn_count >= max_no_tool_turns:
                    yield SDKMessage.assistant(
                        content=llm_response.content,
                        metadata={"phase": "final", "reason": "task_complete" if task_seems_complete else "max_no_tool_turns"}
                    )
                    break
                else:
                    tool_names = list(self._tool_map.keys())
                    guidance_msg = HumanMessage(
                        content=f"""你刚才的回复没有使用任何工具。请使用可用的工具来完成任务。

可用工具列表: {', '.join(tool_names[:10])}

请选择合适的工具来执行下一步操作。如果你认为任务已经完成，请明确说明"任务已完成"。"""
                    )
                    self.mutable_messages.append(guidance_msg)
                    
                    yield SDKMessage.assistant(
                        content="",
                        metadata={
                            "phase": "guidance_added",
                            "turn": self._current_turn,
                            "no_tool_turn_count": no_tool_turn_count
                        }
                    )
                    
                    if should_log_steps:
                        self.logger.log_agent_action("guidance_added", {
                            "session_id": self._session_id,
                            "turn": self._current_turn,
                            "available_tools": tool_names[:5]
                        })
                    continue
            
            no_tool_turn_count = 0
            
            yield SDKMessage.assistant(
                content="",
                metadata={
                    "phase": "tool_execution_start",
                    "tool_count": len(llm_response.tool_calls)
                }
            )
            
            for tool_call in llm_response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_call_id = tool_call.get("id")
                
                if not self.config.can_use_tool(tool_name, tool_args):
                    denial_reason = f"工具 '{tool_name}' 权限被拒绝"
                    self.add_permission_denial(tool_name, denial_reason)
                    
                    tool_result_msg = ToolMessage(
                        content=f"权限拒绝: {denial_reason}",
                        tool_call_id=tool_call_id
                    )
                    self.mutable_messages.append(tool_result_msg)
                    
                    yield SDKMessage.tool_result(
                        tool_name=tool_name,
                        result=f"权限拒绝: {denial_reason}",
                        tool_call_id=tool_call_id,
                        status="denied"
                    )
                    continue
                
                tool_instance = self._tool_map.get(tool_name)
                if tool_instance is None:
                    error_msg = f"工具 '{tool_name}' 不存在"
                    tool_result_msg = ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call_id
                    )
                    self.mutable_messages.append(tool_result_msg)
                    
                    yield SDKMessage.tool_result(
                        tool_name=tool_name,
                        result=error_msg,
                        tool_call_id=tool_call_id,
                        status="error"
                    )
                    continue
                
                try:
                    yield SDKMessage.assistant(
                        content="",
                        metadata={
                            "phase": "tool_executing",
                            "tool_name": tool_name
                        }
                    )
                    
                    preprocessed_args = self._preprocess_tool_args(tool_name, tool_args)
                    
                    result = await self._execute_tool_safe(
                        tool_instance,
                        preprocessed_args,
                        tool_call_id
                    )
                    
                    tool_result_msg = ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id
                    )
                    self.mutable_messages.append(tool_result_msg)
                    
                    yield SDKMessage.tool_result(
                        tool_name=tool_name,
                        result=result,
                        tool_call_id=tool_call_id,
                        status="success"
                    )
                    
                except Exception as e:
                    error_msg = self._build_format_hint(
                        tool_name, tool_args, f"工具执行错误: {str(e)}"
                    )
                    tool_result_msg = ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call_id
                    )
                    self.mutable_messages.append(tool_result_msg)
                    
                    yield SDKMessage.tool_result(
                        tool_name=tool_name,
                        result=error_msg,
                        tool_call_id=tool_call_id,
                        status="error"
                    )
            
            yield SDKMessage.assistant(
                content="",
                metadata={
                    "phase": "tool_execution_complete",
                    "turn": self._current_turn
                }
            )
        
        self.conversation_history.finish_turn()
        
        if self._current_turn >= (self.config.max_turns or 100):
            yield SDKMessage.error(
                message=f"达到最大轮次限制: {self.config.max_turns}",
                error_type="max_turns_reached"
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

    def _check_blocking_limit(self) -> bool:
        if self._compressor is None:
            return False
        estimated_tokens = self._compressor.estimate_tokens(self.mutable_messages)
        warning_state = self._compressor.calculate_token_warning_state(estimated_tokens)
        return warning_state.get("is_at_blocking_limit", False)

    async def _run_compression_pipeline(self) -> None:
        if not self._compression_enabled or self._compressor is None:
            return

        if self.system_prompt_registry is not None:
            self.system_prompt_registry.remove_stale_skills(self.skill_stale_timeout_seconds)

        messages = self._compressor.get_messages_after_compact_boundary(self.mutable_messages)
        messages, _ = self._compressor.apply_tool_result_budget(messages)
        messages, snip_tokens_freed = self._compressor.snip_compact(messages)

        original_len = len(self.mutable_messages)
        messages = await self._compressor.auto_compact_if_needed(messages, snip_tokens_freed)

        if len(messages) < original_len:
            self.mutable_messages = messages
            self._restore_post_compact_context()
            should_log = (
                self.logging_config is None
                or getattr(self.logging_config, "log_compression_stats", True)
            )
            if should_log:
                self.logger.log_agent_action("compression_pipeline_completed", {
                    "session_id": self._session_id,
                    "original_message_count": original_len,
                    "compressed_message_count": len(self.mutable_messages),
                })
        elif messages is not self.mutable_messages:
            self.mutable_messages = messages

    def _handle_compact_boundary(self) -> None:
        if self._compressor is None:
            return
        boundary_idx = -1
        for i, msg in enumerate(self.mutable_messages):
            if isinstance(msg, SystemMessage) and isinstance(msg.content, str) and msg.content.startswith("[compact_boundary]"):
                boundary_idx = i
        if boundary_idx >= 0:
            self.mutable_messages = self.mutable_messages[boundary_idx:]

    def _restore_post_compact_context(self) -> None:
        if self._compressor is None or self._tool_result_storage is None:
            return
        if self.read_file_state and self.read_file_state.cache:
            attachment_parts = []
            for file_path, state in list(self.read_file_state.cache.items())[-5:]:
                content = state.get("content", "")
                if content:
                    estimated_tokens = self._compressor.count_text_tokens(content) if self._compressor else len(content) // 4
                    if estimated_tokens <= 5000:
                        attachment_parts.append(f"File: {file_path}\n{content[:20000]}")
            if attachment_parts:
                total_tokens = sum(self._compressor.count_text_tokens(p) if self._compressor else len(p) // 4 for p in attachment_parts)
                if total_tokens <= 50000:
                    attachment_msg = HumanMessage(
                        content="[Post-compact file context]\n" + "\n---\n".join(attachment_parts)
                    )
                    self.mutable_messages.append(attachment_msg)
        if self._task_intent_manager is not None and self._task_intent_manager.has_task_intent():
            task_intent_msg = self._task_intent_manager.build_recovery_message(self._compressor)
            if task_intent_msg is not None:
                self.mutable_messages.append(task_intent_msg)

    async def _force_compact(self) -> bool:
        if self._compressor is None:
            return False
        if self._compressor._consecutive_failures >= self._compressor.max_consecutive_failures:
            self.logger.log_agent_action("force_compact_skipped", {
                "session_id": self._session_id,
                "reason": "circuit_breaker_active",
                "consecutive_failures": self._compressor._consecutive_failures,
            })
            return False
        try:
            messages = self._compressor.get_messages_after_compact_boundary(self.mutable_messages)
            messages = self._compressor._strip_images_from_messages(messages)
            compressed = await self._compressor.auto_compact(messages)
            self.mutable_messages = compressed
            self._restore_post_compact_context()
            self._compressor._consecutive_failures = 0
            self.logger.log_agent_action("force_compact_success", {
                "session_id": self._session_id,
                "compressed_message_count": len(self.mutable_messages),
            })
            return True
        except Exception as e:
            self._compressor._consecutive_failures += 1
            self.logger.log_error("force_compact", e)
            return False
    
    async def _handle_prompt_too_long(self) -> bool:
        if self._reactive_compact_attempted:
            self.logger.log_agent_action("reactive_compact_skipped", {
                "session_id": self._session_id,
                "reason": "already_attempted",
            })
            return False
        self._reactive_compact_attempted = True
        if self._compressor is None:
            return False
        try:
            messages = self._compressor.get_messages_after_compact_boundary(self.mutable_messages)
            compressed = await self._compressor.auto_compact(messages)
            self.mutable_messages = compressed
            self._restore_post_compact_context()
            self.logger.log_agent_action("reactive_compact_success", {
                "session_id": self._session_id,
                "compressed_message_count": len(self.mutable_messages),
            })
            return True
        except Exception as e:
            self.logger.log_error("reactive_compact", e)
            return False
    
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
        self.mutable_messages.clear()
        self._session_id = str(uuid.uuid4())
        self._current_turn = 0
        self.total_usage = Usage()
        self.permission_denials.clear()
        self.abort_controller.reset()
        if self._task_intent_manager is not None:
            self._task_intent_manager.clear()
        if self._session_storage:
            self._session_storage.save_session(self._session_id, [], metadata={"role": "", "model": ""})
    
    def add_message(self, message: BaseMessage) -> None:
        """添加消息
        
        Args:
            message: 消息对象
        """
        self.mutable_messages.append(message)
    
    def set_messages(self, messages: List[BaseMessage]) -> None:
        self.mutable_messages = list(messages)
    
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
    
    async def _stream_llm_call(self) -> AsyncGenerator[Dict[str, Any], None]:
        messages = await self._prepare_messages_for_llm()
        async for chunk in self.llm_caller.stream_call(messages, use_tools=True):
            yield chunk
    
    async def _prepare_messages_for_llm(self) -> List[BaseMessage]:
        if self.system_prompt_registry is not None:
            self.llm_caller.system_prompt = self.system_prompt_registry.build()
            return [msg for msg in self.mutable_messages if not isinstance(msg, SystemMessage)]
        return list(self.mutable_messages)
    
    def _preprocess_tool_args(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """预处理工具参数，检测并修复 JSON 编码的字符串参数

        对于拥有自定义 model_validator 的工具（如 terminal 的 RubatoShellInput），
        跳过预处理，让工具自身的 validator 处理 JSON 解包。

        Args:
            tool_name: 工具名称
            args: 工具参数字典

        Returns:
            Dict[str, Any]: 预处理后的参数字典
        """
        if not isinstance(args, dict):
            return args

        skip_keys = set()
        if tool_name == "terminal":
            skip_keys.add("commands")

        preprocessed = {}
        for key, value in args.items():
            if key in skip_keys:
                preprocessed[key] = value
                continue

            if isinstance(value, str) and len(value) > 1:
                stripped = value.strip()
                if (stripped.startswith('[') and stripped.endswith(']')) or \
                   (stripped.startswith('{') and stripped.endswith('}')):
                    try:
                        parsed = json.loads(stripped)
                        self.logger.log_agent_action("tool_args_preprocessed", {
                            "session_id": self._session_id,
                            "tool_name": tool_name,
                            "param_name": key,
                            "original_type": "str",
                            "original_value_preview": stripped[:100],
                            "parsed_type": type(parsed).__name__,
                        })
                        preprocessed[key] = parsed
                        continue
                    except (json.JSONDecodeError, TypeError):
                        pass
            preprocessed[key] = value

        return preprocessed

    def _build_format_hint(self, tool_name: str, args: Dict[str, Any], original_error: str) -> str:
        """构建参数格式修正提示

        Args:
            tool_name: 工具名称
            args: 原始工具参数
            original_error: 原始错误信息

        Returns:
            str: 包含格式修正提示的错误消息
        """
        hint = original_error

        if tool_name == "terminal" and "commands" in args:
            commands_value = args["commands"]
            if isinstance(commands_value, str):
                stripped = commands_value.strip()
                if stripped.startswith('[') or stripped.startswith('{'):
                    hint += (
                        "\n\n[参数格式提示] commands 参数应为纯命令字符串，"
                        "不要使用 JSON 数组格式。"
                        f"正确示例: commands='git status'，"
                        f"错误示例: commands='{stripped[:50]}'"
                    )

        return hint

    async def _execute_tool_safe(
        self,
        tool: BaseTool,
        args: Dict[str, Any],
        tool_call_id: str
    ) -> Any:
        """安全执行工具
        
        Args:
            tool: 工具实例
            args: 工具参数
            tool_call_id: 工具调用 ID
            
        Returns:
            Any: 工具执行结果
        """
        self.logger.log_agent_action("tool_execution_start", {
            "session_id": self._session_id,
            "tool_name": tool.name,
            "tool_args": args,
            "tool_call_id": tool_call_id
        })
        
        try:
            if hasattr(tool, 'ainvoke'):
                result = await tool.ainvoke(args)
            else:
                result = tool.invoke(args)
            
            self.logger.log_agent_action("tool_execution_success", {
                "session_id": self._session_id,
                "tool_name": tool.name,
                "tool_call_id": tool_call_id,
                "result_length": len(str(result)) if result else 0
            })
            
            return result
            
        except Exception as e:
            self.logger.log_agent_action("tool_execution_error", {
                "session_id": self._session_id,
                "tool_name": tool.name,
                "tool_call_id": tool_call_id,
                "error": str(e)
            })
            raise
    
    def _update_usage_from_response(self, response: AIMessage) -> None:
        """从响应中更新使用量统计
        
        Args:
            response: AI 响应
        """
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)
            total_tokens = response.usage_metadata.get("total_tokens", 0)
            
            self.total_usage.prompt_tokens += input_tokens
            self.total_usage.completion_tokens += output_tokens
            self.total_usage.total_tokens += total_tokens
            
            self.logger.log_agent_action("usage_updated", {
                "session_id": self._session_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cumulative_tokens": self.total_usage.total_tokens
            })
        
        if self._compressor is not None:
            self._compressor.update_usage_from_response(response)
    
    def load_session(self, session_id: str) -> bool:
        if not self._session_storage:
            return False
        try:
            metadata, messages = self._session_storage.load_session_with_meta(session_id)
            self._session_id = session_id
            self.mutable_messages = messages
            return True
        except Exception:
            return False
    
    def get_session_metadata(self) -> Optional[SessionMetadata]:
        if not self._session_storage:
            return None
        return self._session_storage.get_session_metadata(self._session_id)
    
    def update_session_metadata(self, **kwargs) -> None:
        if self._session_storage:
            self._session_storage.append_messages(self._session_id, self.mutable_messages, metadata=kwargs)
