import re
import json
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import BaseTool
from typing import List, Optional
import time

from ..config.loader import ConfigLoader
from .llm_wrapper import RobustChatOpenAI
from ..config.models import AppConfig, RoleConfig
from ..mcp.tools import ToolRegistry
from ..skills.loader import SkillLoader
from ..skills.manager import SkillManager
from ..context.manager import ContextManager
from .sub_agents import SubAgentManager, create_spawn_agent_tool
from ..utils.logger import get_llm_logger
from ..tools.docs import generate_tool_docs_for_prompt
from .query_engine import QueryEngine, QueryEngineConfig, FileStateCache
from ..context.compressor import ContextCompressor
from ..context.tool_result_storage import ToolResultStorage, ContentReplacementState


def _content_to_str(content) -> str:
    """将消息内容转换为字符串"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if 'text' in item:
                    parts.append(item['text'])
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return " ".join(parts)
    else:
        return str(content)


def _estimate_tokens(messages: List) -> int:
    import warnings
    warnings.warn("_estimate_tokens is deprecated, use ContextCompressor.estimate_tokens() instead", DeprecationWarning, stacklevel=2)
    compressor = ContextCompressor()
    return compressor.estimate_tokens(messages)


def _compress_messages(messages: List, max_tokens: int = 50000, keep_recent: int = 6, 
                       summary_max_length: int = 300, history_summary_count: int = 10) -> List:
    import warnings
    warnings.warn("_compress_messages is deprecated, use ContextCompressor.compress() instead", DeprecationWarning, stacklevel=2)
    compressor = ContextCompressor(max_context_tokens=max_tokens, keep_recent=keep_recent,
                                    summary_max_length=summary_max_length, history_summary_count=history_summary_count)
    return compressor.compress(messages)


def _ensure_message_chain_valid(messages: List) -> List:
    import warnings
    warnings.warn("_ensure_message_chain_valid is deprecated, use ContextCompressor._ensure_message_chain_valid() instead", DeprecationWarning, stacklevel=2)
    compressor = ContextCompressor()
    return compressor._ensure_message_chain_valid(messages)


def _convert_messages_for_api(messages: List) -> List:
    """转换消息格式以兼容DeepSeek API"""
    converted = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            converted.append(ToolMessage(
                content=_content_to_str(msg.content),
                tool_call_id=msg.tool_call_id
            ))
        elif isinstance(msg, AIMessage):
            converted.append(AIMessage(
                content=_content_to_str(msg.content),
                tool_calls=msg.tool_calls if hasattr(msg, 'tool_calls') else []
            ))
        else:
            converted.append(msg)
    return converted


class RubatoAgent:
    """自然语言驱动的自动化测试执行 Agent"""
    
    def __init__(
        self, 
        config: AppConfig,
        skill_loader: SkillLoader,
        context_manager: ContextManager,
        tool_registry: ToolRegistry,
        mcp_manager = None,
        role_config: Optional[RoleConfig] = None,
        roles_dir: str = "config/roles"
    ):
        self.config = config
        self.skill_loader = skill_loader
        self.context_manager = context_manager
        self.tool_registry = tool_registry
        self.mcp_manager = mcp_manager
        self.role_config = role_config
        self.roles_dir = roles_dir
        self.logger = get_llm_logger()
        
        self.logging_config = config.agent.logging
        self.logger.set_log_format(self.logging_config.log_format)
        self.logger.set_tool_log_mode(self.logging_config.tool_log_mode)
        
        self.llm = self._create_llm()
        self._current_system_prompt = self._load_system_prompt()
        
        self.max_context_tokens = (
            role_config.execution.max_context_tokens
            if role_config and role_config.execution and role_config.execution.max_context_tokens
            else config.agent.max_context_tokens
        )
        
        self.recursion_limit = (
            role_config.execution.recursion_limit
            if role_config and role_config.execution and role_config.execution.recursion_limit
            else config.agent.execution.recursion_limit
        )
        
        self.compression_config = config.agent.message_compression
        
        sub_agent_recursion_limit = (
            role_config.execution.sub_agent_recursion_limit
            if role_config and role_config.execution and role_config.execution.sub_agent_recursion_limit
            else config.agent.execution.sub_agent_recursion_limit
        )
        
        self._role_skills: Optional[List[str]] = None
        if role_config and role_config.tools and role_config.tools.skills:
            self._role_skills = role_config.tools.skills
        
        self.tools = self._get_tools_for_role()
        
        self._sub_agent_manager = SubAgentManager(
            llm=self.llm,
            parent_agent=self,
            sub_agents_dir="sub_agents",
            roles_dir=self.roles_dir,
            recursion_limit=sub_agent_recursion_limit
        )
        
        spawn_agent_tool = create_spawn_agent_tool(self._sub_agent_manager)
        self.tools.append(spawn_agent_tool)
        
        self.agent = self._create_agent(self._current_system_prompt)
        
        self.use_query_engine = (
            role_config.execution.use_query_engine
            if role_config and role_config.execution and hasattr(role_config.execution, 'use_query_engine')
            else False
        )
        
        self._query_engine: Optional[QueryEngine] = None
        self._file_state_cache = FileStateCache()
        
        if self.use_query_engine:
            self._query_engine = self._create_query_engine()
        
        self.logger.log_agent_action("agent_initialized", {
            "model": config.model.model.name,
            "tool_count": len(self.tools),
            "max_context_tokens": self.max_context_tokens,
            "recursion_limit": self.recursion_limit,
            "compression_enabled": self.compression_config.enabled,
            "use_query_engine": self.use_query_engine
        })
    
    def get_role_name(self) -> str:
        """获取当前角色名称
        
        Returns:
            角色名称，如果没有配置角色则返回 'default'
        """
        if self.role_config and hasattr(self.role_config, 'name'):
            return self.role_config.name
        return "default"
    
    def _create_agent(self, system_prompt: str):
        """创建Agent实例"""
        def pre_model_hook(state):
            messages = state.get("messages", [])
            
            if self.compression_config.enabled:
                compressor = ContextCompressor(
                    max_context_tokens=self.compression_config.max_tokens,
                    keep_recent=self.compression_config.keep_recent,
                    summary_max_length=self.compression_config.summary_max_length,
                    history_summary_count=self.compression_config.history_summary_count,
                )
                compressed = compressor.compress(messages)
            else:
                compressed = messages
            
            converted = _convert_messages_for_api(compressed)
            
            if self.logging_config.log_token_estimation:
                token_estimate = sum(len(str(m.content)) // 4 for m in compressed)
                self.logger.log_agent_action("pre_model_hook", {
                    "original_messages": len(messages),
                    "compressed_messages": len(compressed),
                    "estimated_tokens": token_estimate,
                    "compression_enabled": self.compression_config.enabled
                })
            
            return {"llm_input_messages": converted}
        
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
            pre_model_hook=pre_model_hook
        )
    
    def _create_query_engine(self) -> QueryEngine:
        """创建 QueryEngine 实例"""
        def can_use_tool(tool_name: str, args: dict) -> bool:
            return True
        
        def get_app_state() -> dict:
            return self.context_manager.get_context()
        
        def set_app_state(state: dict) -> None:
            pass
        
        skills = []
        if self.skill_loader:
            try:
                skill_metadata = self.skill_loader.get_all_skill_metadata()
                for name, meta in skill_metadata.items():
                    if self._role_skills is None or name in self._role_skills:
                        skills.append(meta)
            except Exception:
                pass
        
        query_config = QueryEngineConfig(
            cwd=str(self.config.project.root) if self.config.project else ".",
            llm=self.llm,
            tools=self.tools,
            skills=skills,
            can_use_tool=can_use_tool,
            get_app_state=get_app_state,
            set_app_state=set_app_state,
            initial_messages=self.context_manager.get_messages(),
            read_file_cache=self._file_state_cache,
            custom_system_prompt=self._current_system_prompt,
            max_turns=self.recursion_limit,
            model_name=self.config.model.model.name,
            temperature=self.config.model.model.temperature,
            max_tokens=self.config.model.model.max_tokens,
            compression_enabled=self.compression_config.enabled,
            max_context_tokens=self.max_context_tokens,
            autocompact_buffer_tokens=getattr(self.compression_config, 'autocompact_buffer_tokens', 13000),
            keep_recent=self.compression_config.keep_recent,
            snip_keep_recent=getattr(self.compression_config, 'snip_keep_recent', 6),
            tool_result_persist_threshold=getattr(self.compression_config, 'tool_result_persist_threshold', 50000),
            tool_result_budget_per_message=getattr(self.compression_config, 'tool_result_budget_per_message', 200000),
            max_consecutive_failures=getattr(self.compression_config, 'max_consecutive_failures', 3),
        )
        
        return QueryEngine(query_config)
    
    def _create_llm(self, model_config: Optional['ModelConfig'] = None):
        """创建LLM实例
        
        Args:
            model_config: 可选的模型配置，如果提供则使用该配置，否则使用默认配置
            
        Returns:
            RobustChatOpenAI: LLM实例（带有重试逻辑）
        """
        from ..config.models import ModelConfig
        
        config = model_config if model_config is not None else self.config.model.model

        llm_kwargs = {
            "model": config.name,
            "api_key": config.api_key,
            "base_url": config.base_url,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "default_headers": {"Authorization": config.auth} if config.auth else None,
            "callbacks": [self.logger.get_callback_handler()]
        }
        
        return RobustChatOpenAI(
            **llm_kwargs
        )
    
    def _get_tools_for_role(self) -> List[BaseTool]:
        """根据角色配置获取可用工具
        
        Returns:
            List[BaseTool]: 工具列表
        """
        all_tools = self.tool_registry.get_all_tools()
        
        if self.role_config and self.role_config.available_tools:
            available_tool_names = set(self.role_config.available_tools)
            filtered_tools = [tool for tool in all_tools if tool.name in available_tool_names]
            self.logger.log_agent_action("tools_filtered_by_role", {
                "role_name": self.role_config.name,
                "requested_tools": list(available_tool_names),
                "available_tools": [tool.name for tool in filtered_tools]
            })
            return filtered_tools
        
        self.logger.log_agent_action("tools_loaded", {
            "tool_count": len(all_tools),
            "tool_names": [tool.name for tool in all_tools]
        })
        return all_tools
    
    def _load_system_prompt(self) -> str:
        """加载系统提示词"""
        if self.role_config and self.role_config.system_prompt_file:
            prompt_file = self.role_config.system_prompt_file
        else:
            prompt_file = self.config.prompts.system_prompt_file
        
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                base_prompt = f.read()
        except FileNotFoundError:
            base_prompt = self._get_default_system_prompt()
        
        if self._should_inject_tool_docs():
            tool_docs = self._generate_tool_docs()
            if tool_docs:
                return f"{base_prompt}\n\n{tool_docs}"
        
        return base_prompt
    
    def _should_inject_tool_docs(self) -> bool:
        """检查是否应该注入工具说明"""
        if self.config.tools and hasattr(self.config.tools, 'tool_docs'):
            return self.config.tools.tool_docs.auto_inject
        return True
    
    def _generate_tool_docs(self) -> str:
        """生成工具说明文档"""
        builtin_tools = []
        all_tools = self.tool_registry.get_all_tools()
        for tool in all_tools:
            tool_name = tool.name
            builtin_names = {'spawn_agent', 'shell_tool', 'file_read', 'file_write', 
                            'file_list', 'file_search', 'file_exists', 'file_mkdir', 
                            'file_replace', 'file_delete'}
            if tool_name in builtin_names:
                builtin_tools.append(tool_name)
        
        mcp_tools = []
        if self.mcp_manager and self.mcp_manager.is_connected:
            try:
                mcp_tools_list = self.mcp_manager.get_tools()
                for tool in mcp_tools_list:
                    mcp_tools.append({
                        "name": tool.name if hasattr(tool, 'name') else str(tool),
                        "description": tool.description if hasattr(tool, 'description') else "",
                        "parameters": []
                    })
            except Exception:
                pass
        
        skills = []
        if self.skill_loader:
            try:
                skill_metadata = self.skill_loader.get_all_skill_metadata()
                for name, meta in skill_metadata.items():
                    if self._role_skills is None or name in self._role_skills:
                        skills.append({
                            "name": name,
                            "description": meta.get("description", ""),
                            "triggers": meta.get("triggers", []),
                            "required_tools": meta.get("required_tools", [])
                        })
            except Exception:
                pass
        
        include_examples = True
        if self.config.tools and hasattr(self.config.tools, 'tool_docs'):
            include_examples = self.config.tools.tool_docs.include_examples
        
        return generate_tool_docs_for_prompt(
            builtin_tools=builtin_tools,
            mcp_tools=mcp_tools,
            skills=skills,
            include_examples=include_examples
        )
    
    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词"""
        return """你是Rubato，一个专业的自动化测试执行助手。

# 角色
你是一个能够自主规划和执行测试任务的智能体。

# 目标
根据用户的自然语言描述，执行浏览器自动化测试，并返回测试结果。

# 工作模式
你采用ReAct模式工作：推理（Reason）→ 行动（Act）→ 观察（Observe）

# 可用工具
- browser_navigate: 导航到URL
- browser_click: 点击元素
- browser_type: 输入文本
- browser_snapshot: 获取页面快照
- browser_take_screenshot: 截图
- spawn_agent: 调用子智能体处理复杂任务

# 工作原则
1. 自主规划：根据任务自主决定执行步骤
2. 逐步执行：一次执行一个步骤，观察结果后再决定下一步
3. 错误处理：遇到错误时尝试调整策略
4. 结果导向：确保完成用户的目标
"""
    
    def _extract_file_paths_from_input(self, user_input: str) -> List[str]:
        """从用户输入中提取可能的文件路径
        
        Args:
            user_input: 用户输入文本
            
        Returns:
            List[str]: 提取的文件路径列表
        """
        paths = []
        
        file_patterns = [
            r'[a-zA-Z]:\\[-\\\w\s]+\\\.[\w]+',
            r'/[-\w\s]+/([-\w\s]+/)*[-\w\s]+\.[\w]+',
            r'\./[-\w\s./]+',
            r'\.\./[-\w\s./]+',
            r'"[^"]+\.[\w]+"',
            r"'[^']+\.[\w]+'",
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, user_input)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                match = match.strip('"\'')
                if match and match not in paths:
                    paths.append(match)
        
        return paths
    
    async def run(self, user_input: str) -> str:
        """运行Agent，使用流式处理记录每个步骤"""
        role_name = self.get_role_name()
        self.logger.set_role_context(role_name)
        self.logger.log_agent_thinking(f"收到用户输入: {user_input}")
        
        file_paths = self._extract_file_paths_from_input(user_input)
        if file_paths:
            activated = self.activate_skills_for_paths(file_paths)
            if activated:
                self.logger.log_agent_action("auto_activated_skills", {
                    "skills": activated,
                    "extracted_paths": file_paths
                })
        
        if self.mcp_manager and self.mcp_manager.is_connected:
            browser_ok = await self.mcp_manager.ensure_browser()
            if not browser_ok:
                return "浏览器初始化失败，请检查 MCP 连接"
        
        skill_name = self.skill_loader.find_matching_skill(user_input)
        
        if skill_name and not self.context_manager.is_skill_loaded(skill_name):
            self.logger.log_agent_action("loading_skill", {"skill": skill_name})
            enhanced_prompt = await self._inject_skill(skill_name)
            self._current_system_prompt = enhanced_prompt
            self.agent = self._create_agent(enhanced_prompt)
            self.context_manager.mark_skill_loaded(skill_name)
        
        if self.use_query_engine and self._query_engine:
            return await self._run_with_query_engine(user_input)
        
        self.context_manager.add_user_message(user_input)
        
        messages = self.context_manager.get_messages()
        
        self.logger.log_request(messages, self.config.model.model.name)
        
        start_time = time.time()
        step_count = 0
        
        try:
            final_content = ""
            
            async for event in self.agent.astream(
                {"messages": messages},
                stream_mode="updates",
                config={"recursion_limit": self.recursion_limit}
            ):
                step_count += 1
                
                if event is None:
                    self.logger.log_agent_action("event_none", {
                        "step": step_count,
                        "warning": "Received None event from astream"
                    })
                    continue
                
                self.logger.log_agent_action("stream_event", {
                    "step": step_count,
                    "event_keys": list(event.keys())
                })
                
                for node_name, node_output in event.items():
                    self.logger.log_agent_action("node_output", {
                        "step": step_count,
                        "node": node_name
                    })
                    
                    if "messages" in node_output:
                        for msg in node_output["messages"]:
                            if isinstance(msg, AIMessage):
                                self.context_manager.add_ai_message_full(msg)
                                self.logger.log_response(msg, self.config.model.model.name)
                                
                                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        self.logger.log_tool_call(tc["name"], tc["args"])
                                
                                content_str = _content_to_str(msg.content)
                                if content_str:
                                    final_content = content_str
                                    
                            elif isinstance(msg, ToolMessage):
                                content_str = _content_to_str(msg.content)
                                self.context_manager.add_tool_message(content_str, msg.tool_call_id)
                                self.logger.log_tool_result("tool_message", content_str)
            
            elapsed = time.time() - start_time
            self.logger.log_agent_action("stream_complete", {
                "elapsed_seconds": round(elapsed, 2),
                "total_steps": step_count
            })
            
            return final_content if final_content else "任务已完成"
            
        except Exception as e:
            import traceback
            self.logger.log_error("agent_invoke", e)
            self.logger.log_agent_action("agent_invoke_error_details", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            })
            raise
    
    async def _run_with_query_engine(self, user_input: str) -> str:
        """使用 QueryEngine 运行 Agent
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 最终响应
        """
        from .query_engine import SDKMessage, SubmitOptions
        
        self.context_manager.add_user_message(user_input)
        
        self._query_engine = self._create_query_engine()
        
        self.logger.log_agent_action("query_engine_start", {
            "session_id": self._query_engine.get_session_id(),
            "prompt_length": len(user_input)
        })
        
        start_time = time.time()
        final_content = ""
        
        try:
            options = SubmitOptions(stream=True)
            
            async for message in self._query_engine.submit_message(user_input, options):
                if message.type == "assistant":
                    content = message.content
                    if isinstance(content, str) and content:
                        final_content = content
                        self.logger.log_agent_thinking(content)
                        
                elif message.type == "tool_use":
                    tool_info = message.content
                    self.logger.log_tool_call(
                        tool_info.get("name", "unknown"),
                        tool_info.get("args", {})
                    )
                    
                elif message.type == "tool_result":
                    tool_info = message.content
                    self.logger.log_tool_result(
                        tool_info.get("name", "unknown"),
                        tool_info.get("result", "")
                    )
                    
                elif message.type == "error":
                    error_info = message.content
                    self.logger.log_error("query_engine", Exception(
                        f"{error_info.get('error_type', 'unknown')}: {error_info.get('message', '')}"
                    ))
                    
                elif message.type == "result":
                    final_content = message.content if isinstance(message.content, str) else final_content
                    
            for msg in self._query_engine.get_messages():
                if isinstance(msg, AIMessage):
                    self.context_manager.add_ai_message_full(msg)
                elif isinstance(msg, ToolMessage):
                    self.context_manager.add_tool_message(
                        _content_to_str(msg.content),
                        msg.tool_call_id
                    )
            
            elapsed = time.time() - start_time
            usage = self._query_engine.get_usage()
            
            self.logger.log_agent_action("query_engine_complete", {
                "elapsed_seconds": round(elapsed, 2),
                "total_tokens": usage.total_tokens,
                "cost_usd": usage.cost_usd
            })
            
            return final_content if final_content else "任务已完成"
            
        except Exception as e:
            import traceback
            self.logger.log_error("query_engine_run", e)
            self.logger.log_agent_action("query_engine_error", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            })
            raise
    
    async def run_stream(self, user_input: str):
        """运行Agent，流式返回响应内容（用于WebSocket）"""
        role_name = self.get_role_name()
        self.logger.set_role_context(role_name)
        self.logger.log_agent_thinking(f"收到用户输入: {user_input}")
        
        file_paths = self._extract_file_paths_from_input(user_input)
        if file_paths:
            activated = self.activate_skills_for_paths(file_paths)
            if activated:
                self.logger.log_agent_action("auto_activated_skills", {
                    "skills": activated,
                    "extracted_paths": file_paths
                })
        
        if self.mcp_manager and self.mcp_manager.is_connected:
            browser_ok = await self.mcp_manager.ensure_browser()
            if not browser_ok:
                yield "浏览器初始化失败，请检查 MCP 连接"
                return
        
        skill_name = self.skill_loader.find_matching_skill(user_input)
        
        if skill_name and not self.context_manager.is_skill_loaded(skill_name):
            self.logger.log_agent_action("loading_skill", {"skill": skill_name})
            enhanced_prompt = await self._inject_skill(skill_name)
            self._current_system_prompt = enhanced_prompt
            self.agent = self._create_agent(enhanced_prompt)
            self.context_manager.mark_skill_loaded(skill_name)
        
        if self.use_query_engine and self._query_engine:
            async for content in self._run_stream_with_query_engine(user_input):
                yield content
            return
        
        self.context_manager.add_user_message(user_input)
        messages = self.context_manager.get_messages()
        
        self.logger.log_request(messages, self.config.model.model.name)
        
        start_time = time.time()
        step_count = 0
        
        try:
            final_content = ""
            
            async for event in self.agent.astream(
                {"messages": messages},
                stream_mode="updates",
                config={"recursion_limit": self.recursion_limit}
            ):
                step_count += 1
                
                if event is None:
                    self.logger.log_agent_action("event_none", {
                        "step": step_count,
                        "warning": "Received None event from astream"
                    })
                    continue
                
                for node_name, node_output in event.items():
                    if "messages" in node_output:
                        for msg in node_output["messages"]:
                            if isinstance(msg, AIMessage):
                                self.context_manager.add_ai_message_full(msg)
                                self.logger.log_response(msg, self.config.model.model.name)
                                
                                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                                    for tc in msg.tool_calls:
                                        self.logger.log_tool_call(tc["name"], tc["args"])
                                
                                content_str = _content_to_str(msg.content)
                                if content_str:
                                    final_content = content_str
                                    yield content_str
                                    
                            elif isinstance(msg, ToolMessage):
                                content_str = _content_to_str(msg.content)
                                self.context_manager.add_tool_message(content_str, msg.tool_call_id)
                                self.logger.log_tool_result("tool_message", content_str)
            
            elapsed = time.time() - start_time
            self.logger.log_agent_action("stream_complete", {
                "elapsed_seconds": round(elapsed, 2),
                "total_steps": step_count
            })
            
            if not final_content:
                yield "任务已完成"
            
        except Exception as e:
            import traceback
            self.logger.log_error("agent_invoke", e)
            self.logger.log_agent_action("agent_invoke_error_details", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            })
            yield f"执行错误: {str(e)}"
    
    async def _run_stream_with_query_engine(self, user_input: str):
        """使用 QueryEngine 流式运行 Agent
        
        Args:
            user_input: 用户输入
            
        Yields:
            str: 流式响应内容
        """
        from .query_engine import SDKMessage, SubmitOptions
        
        self.context_manager.add_user_message(user_input)
        
        self._query_engine = self._create_query_engine()
        
        self.logger.log_agent_action("query_engine_stream_start", {
            "session_id": self._query_engine.get_session_id(),
            "prompt_length": len(user_input)
        })
        
        start_time = time.time()
        final_content = ""
        
        try:
            options = SubmitOptions(stream=True)
            
            async for message in self._query_engine.submit_message(user_input, options):
                if message.type == "assistant":
                    content = message.content
                    if isinstance(content, str) and content:
                        final_content = content
                        yield content
                        
                elif message.type == "tool_use":
                    tool_info = message.content
                    self.logger.log_tool_call(
                        tool_info.get("name", "unknown"),
                        tool_info.get("args", {})
                    )
                    tool_name = tool_info.get('name', 'unknown')
                    tool_args = tool_info.get('args', {})
                    args_str = json.dumps(tool_args, ensure_ascii=False) if tool_args else ""
                    yield f"\n[调用工具: {tool_name}, 参数: {args_str}]\n"
                    
                elif message.type == "tool_result":
                    tool_info = message.content
                    self.logger.log_tool_result(
                        tool_info.get("name", "unknown"),
                        tool_info.get("result", "")
                    )
                    
                elif message.type == "error":
                    error_info = message.content
                    self.logger.log_error("query_engine", Exception(
                        f"{error_info.get('error_type', 'unknown')}: {error_info.get('message', '')}"
                    ))
                    yield f"\n[错误: {error_info.get('message', '')}]\n"
                    
                elif message.type == "interrupt":
                    reason = message.content.get("reason", "未知原因")
                    yield f"\n[中断: {reason}]\n"
                    
                elif message.type == "result":
                    if isinstance(message.content, str) and message.content:
                        final_content = message.content
            
            for msg in self._query_engine.get_messages():
                if isinstance(msg, AIMessage):
                    self.context_manager.add_ai_message_full(msg)
                elif isinstance(msg, ToolMessage):
                    self.context_manager.add_tool_message(
                        _content_to_str(msg.content),
                        msg.tool_call_id
                    )
            
            elapsed = time.time() - start_time
            usage = self._query_engine.get_usage()
            
            self.logger.log_agent_action("query_engine_stream_complete", {
                "elapsed_seconds": round(elapsed, 2),
                "total_tokens": usage.total_tokens,
                "cost_usd": usage.cost_usd
            })
            
            if not final_content:
                yield "任务已完成"
            
        except Exception as e:
            import traceback
            self.logger.log_error("query_engine_stream", e)
            self.logger.log_agent_action("query_engine_stream_error", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            })
            yield f"执行错误: {str(e)}"
    
    async def _inject_skill(self, skill_name: str) -> str:
        """将Skill内容注入到提示词中"""
        skill_content = await self.skill_loader.load_full_skill(skill_name)
        
        return f"{self._current_system_prompt}\n\n# 当前加载的Skill\n\n## {skill_name}\n\n{skill_content}\n\n---\n请根据这个Skill的指导，处理用户的请求。"
    
    def get_system_prompt(self) -> str:
        """获取当前系统提示词（包含工具说明）"""
        return self._current_system_prompt
    
    def get_current_system_prompt(self) -> str:
        """获取当前系统提示词（包含工具说明）"""
        return self._current_system_prompt
    
    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills"""
        return self.context_manager.get_loaded_skills()
    
    def _reload_execution_config(self) -> dict:
        """重新加载执行配置
        
        根据 role_config 更新所有 RoleExecutionConfig 相关属性：
        - max_context_tokens
        - recursion_limit
        - sub_agent_recursion_limit（需要重建 SubAgentManager）
        - use_query_engine（需要重建 QueryEngine）
        
        Returns:
            dict: 配置变更记录，用于日志
        """
        old_values = {
            "recursion_limit": self.recursion_limit,
            "use_query_engine": self.use_query_engine,
            "sub_agent_recursion_limit": self._sub_agent_manager.recursion_limit,
            "max_context_tokens": self.max_context_tokens
        }
        
        if self.role_config and self.role_config.execution:
            exec_config = self.role_config.execution
            
            self.max_context_tokens = (
                exec_config.max_context_tokens
                if exec_config.max_context_tokens
                else self.config.agent.max_context_tokens
            )
            
            self.recursion_limit = (
                exec_config.recursion_limit
                if exec_config.recursion_limit
                else self.config.agent.execution.recursion_limit
            )
            
            sub_agent_recursion_limit = (
                exec_config.sub_agent_recursion_limit
                if exec_config.sub_agent_recursion_limit
                else self.config.agent.execution.sub_agent_recursion_limit
            )
            
            self.use_query_engine = (
                exec_config.use_query_engine
                if hasattr(exec_config, 'use_query_engine')
                else False
            )
        else:
            self.max_context_tokens = self.config.agent.max_context_tokens
            self.recursion_limit = self.config.agent.execution.recursion_limit
            sub_agent_recursion_limit = self.config.agent.execution.sub_agent_recursion_limit
            self.use_query_engine = False
        
        if sub_agent_recursion_limit != old_values["sub_agent_recursion_limit"]:
            self._sub_agent_manager = SubAgentManager(
                llm=self.llm,
                parent_agent=self,
                sub_agents_dir="sub_agents",
                recursion_limit=sub_agent_recursion_limit
            )
            spawn_agent_tool = create_spawn_agent_tool(self._sub_agent_manager)
            self.tools = [t for t in self.tools if t.name != 'spawn_agent']
            self.tools.append(spawn_agent_tool)
        
        if self.use_query_engine:
            self._query_engine = self._create_query_engine()
        else:
            self._query_engine = None
        
        return {
            "recursion_limit": {"old": old_values["recursion_limit"], "new": self.recursion_limit},
            "use_query_engine": {"old": old_values["use_query_engine"], "new": self.use_query_engine},
            "sub_agent_recursion_limit": {"old": old_values["sub_agent_recursion_limit"], "new": self._sub_agent_manager.recursion_limit},
            "max_context_tokens": {"old": old_values["max_context_tokens"], "new": self.max_context_tokens}
        }
    
    def reload_system_prompt(self, role_config: Optional[RoleConfig] = None) -> None:
        """重新加载系统提示词（含工具说明注入）
        
        Args:
            role_config: 新的角色配置（可选，为 None 时重新加载当前角色的提示词）
        """
        if role_config is not None:
            self.role_config = role_config
            if role_config.tools and role_config.tools.skills:
                self._role_skills = role_config.tools.skills
            else:
                self._role_skills = None
            
            config_changes = self._reload_execution_config()
        
        self._current_system_prompt = self._load_system_prompt()
        self.agent = self._create_agent(self._current_system_prompt)
        
        log_data = {
            "role_config_updated": role_config is not None,
            "role_skills": self._role_skills
        }
        if role_config is not None:
            log_data["config_changes"] = config_changes
        
        self.logger.log_agent_action("system_prompt_reloaded", log_data)
    
    def reload_tools(self, tool_registry: ToolRegistry) -> None:
        """重新加载工具列表
        
        Args:
            tool_registry: 新的工具注册表
        """
        self.tool_registry = tool_registry
        
        self.tools = self._get_tools_for_role()
        
        config_changes = self._reload_execution_config()
        
        self.agent = self._create_agent(self._current_system_prompt)
        
        self.logger.log_agent_action("tools_reloaded", {
            "tool_count": len(self.tools),
            "tool_names": [tool.name for tool in self.tools],
            "config_changes": config_changes
        })
    
    def update_role_skills(self, skills: Optional[List[str]]) -> None:
        """更新角色的 skills 配置并重新生成系统提示词
        
        Args:
            skills: 角色配置的 skills 列表，为 None 时使用全局配置（不过滤）
        """
        self._role_skills = skills
        self._current_system_prompt = self._load_system_prompt()
        self.agent = self._create_agent(self._current_system_prompt)
        
        self.logger.log_agent_action("role_skills_updated", {
            "skills": skills,
            "filtered": skills is not None
        })
    
    async def load_role_skills(self, skills: Optional[List[str]]) -> None:
        """异步加载角色配置的 skills 全文并注入到系统提示词
        
        Args:
            skills: 角色配置的 skills 列表
        """
        self._role_skills = skills
        
        if not skills or not self.skill_loader:
            self._current_system_prompt = self._load_system_prompt()
            self.agent = self._create_agent(self._current_system_prompt)
            return
        
        skill_contents = []
        for skill_name in skills:
            if self.skill_loader.has_skill(skill_name):
                content = await self.skill_loader.load_full_skill(skill_name)
                if content:
                    skill_contents.append(f"## {skill_name}\n\n{content}")
                    self.context_manager.mark_skill_loaded(skill_name)
                    self.logger.log_agent_action("skill_full_loaded", {
                        "skill": skill_name,
                        "content_length": len(content)
                    })
            else:
                self.logger.log_agent_action("skill_not_found", {
                "skill": skill_name
            })
        
        if skill_contents:
            skills_section = "\n\n# 角色专用 Skills\n\n" + "\n\n".join(skill_contents)
            base_prompt = self._load_system_prompt()
            self._current_system_prompt = f"{base_prompt}\n{skills_section}"
        else:
            self._current_system_prompt = self._load_system_prompt()
        
        self.agent = self._create_agent(self._current_system_prompt)
        
        self.logger.log_agent_action("role_skills_loaded", {
            "skills": skills,
            "loaded_count": len(skill_contents)
        })
    
    def clear_context(self) -> None:
        """清空上下文"""
        self.context_manager.clear()
    
    def activate_skills_for_paths(self, file_paths: List[str]) -> List[str]:
        """激活匹配文件路径的条件 Skills
        
        Args:
            file_paths: 用户正在操作的文件路径列表
            
        Returns:
            List[str]: 激活的 Skill 名称列表
        """
        if not isinstance(self.skill_loader, SkillManager):
            self.logger.log_agent_action("skill_manager_not_available", {
                "message": "SkillLoader is not SkillManager, skipping conditional activation"
            })
            return []
        
        activated = []
        
        discovered = self.skill_loader.discover_for_paths(file_paths)
        if discovered:
            self.logger.log_agent_action("skills_discovered", {
                "skills": discovered,
                "paths": file_paths
            })
            activated.extend(discovered)
        
        conditional_activated = self.skill_loader.activate_for_paths(file_paths)
        if conditional_activated:
            self.logger.log_agent_action("conditional_skills_activated", {
                "skills": conditional_activated,
                "paths": file_paths
            })
            activated.extend(conditional_activated)
        
        return activated
    
    def get_skill_manager_stats(self) -> dict:
        """获取 SkillManager 统计信息
        
        Returns:
            dict: 包含条件 Skills、动态 Skills 和已发现目录的数量
        """
        if not isinstance(self.skill_loader, SkillManager):
            return {
                "is_skill_manager": False,
                "conditional_skills": 0,
                "dynamic_skills": 0,
                "discovered_dirs": 0
            }
        
        return {
            "is_skill_manager": True,
            "conditional_skills": self.skill_loader.get_conditional_skills_count(),
            "dynamic_skills": self.skill_loader.get_dynamic_skills_count(),
            "discovered_dirs": self.skill_loader.get_discovered_dirs_count()
        }
    
    def update_config(self, new_config: AppConfig) -> None:
        """更新配置（支持热重载）"""
        self.config = new_config
        
        self.max_context_tokens = (
            self.role_config.execution.max_context_tokens
            if self.role_config and self.role_config.execution and self.role_config.execution.max_context_tokens
            else new_config.agent.max_context_tokens
        )
        
        self.recursion_limit = (
            self.role_config.execution.recursion_limit
            if self.role_config and self.role_config.execution and self.role_config.execution.recursion_limit
            else new_config.agent.execution.recursion_limit
        )
        
        self.compression_config = new_config.agent.message_compression
        self.logging_config = new_config.agent.logging
        
        self.logger.log_agent_action("config_updated", {
            "max_context_tokens": self.max_context_tokens,
            "recursion_limit": self.recursion_limit,
            "compression_enabled": self.compression_config.enabled
        })
