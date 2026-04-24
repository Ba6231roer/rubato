import re
import json
from langchain_core.tools import BaseTool
from typing import List, Optional
import time

from .llm_wrapper import LLMCaller
from ..config.models import AppConfig, RoleConfig
from ..mcp.tools import ToolRegistry
from ..skills.loader import SkillLoader
from ..skills.manager import SkillManager
from ..context.manager import ContextManager
from ..context.system_prompt_registry import SystemPromptRegistry
from .sub_agents import SubAgentManager, create_spawn_agent_tool
from ..utils.logger import get_llm_logger
from ..tools.docs import generate_tool_docs_for_prompt
from .query_engine import QueryEngine, QueryEngineConfig, FileStateCache
from ..context.session_storage import SessionStorage





class RubatoAgent:
    
    def __init__(
        self, 
        config: AppConfig,
        skill_loader: SkillLoader,
        context_manager: ContextManager,
        tool_registry: ToolRegistry,
        mcp_manager = None,
        role_config: Optional[RoleConfig] = None,
        roles_dir: str = "config/roles",
        session_storage: Optional[SessionStorage] = None
    ):
        self.config = config
        self.skill_loader = skill_loader
        self.context_manager = context_manager
        self.tool_registry = tool_registry
        self.mcp_manager = mcp_manager
        self.role_config = role_config
        self.roles_dir = roles_dir
        self._session_storage = session_storage
        self.logger = get_llm_logger()
        
        self.logging_config = config.agent.logging
        self.logger.set_log_format(self.logging_config.log_format)
        self.logger.set_tool_log_mode(self.logging_config.tool_log_mode)
        
        self.llm = self._create_llm()
        
        self._role_skills: Optional[List[str]] = None
        if role_config and role_config.tools and role_config.tools.skills:
            self._role_skills = role_config.tools.skills
        
        self._system_prompt_registry = self._build_system_prompt_registry()
        self._current_system_prompt = self._system_prompt_registry.build()
        
        self.llm.system_prompt_registry = self._system_prompt_registry
        self.llm.logging_config = self.logging_config
        
        self.max_context_tokens = (
            role_config.execution.max_context_tokens
            if role_config and role_config.execution and role_config.execution.max_context_tokens
            else config.agent.max_context_tokens
        )
        
        self.max_turns = (
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
        
        self.tools = self._get_tools_for_role()
        
        self._sub_agent_manager = SubAgentManager(
            llm=self.llm,
            parent_agent=self,
            sub_agents_dir="sub_agents",
            roles_dir=self.roles_dir,
            recursion_limit=sub_agent_recursion_limit,
            session_storage=self._session_storage
        )
        
        self._ensure_spawn_agent_tool()
        
        self._file_state_cache = FileStateCache()
        self._query_engine: QueryEngine = self._create_query_engine()
        
        self.logger.log_agent_action("agent_initialized", {
            "model": config.model.model.name,
            "tool_count": len(self.tools),
            "max_context_tokens": self.max_context_tokens,
            "max_turns": self.max_turns,
            "compression_enabled": self.compression_config.enabled
        })
    
    def get_role_name(self) -> str:
        if self.role_config and hasattr(self.role_config, 'name'):
            return self.role_config.name
        return "default"
    
    def _create_query_engine(self) -> QueryEngine:
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
            initial_messages=[],
            read_file_cache=self._file_state_cache,
            custom_system_prompt=self._current_system_prompt,
            max_turns=self.max_turns,
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
            large_message_char_threshold=getattr(self.compression_config, 'large_message_char_threshold', 50000),
            llm_timeout=float(self.config.agent.execution.llm_timeout),
            retry_max_count=self.config.model.parameters.retry_max_count,
            retry_initial_delay=self.config.model.parameters.retry_initial_delay,
            retry_max_delay=self.config.model.parameters.retry_max_delay,
            system_prompt_registry=self._system_prompt_registry,
            logging_config=self.logging_config,
            session_storage=self._session_storage,
            role_name=self.get_role_name(),
        )
        
        return QueryEngine(query_config)
    
    def _rebuild_query_engine(self) -> None:
        old_messages = []
        if self._query_engine is not None:
            old_messages = self._query_engine.get_messages()
        
        self._current_system_prompt = self._system_prompt_registry.build()
        self._query_engine = self._create_query_engine()
        
        if old_messages:
            self._query_engine.set_messages(old_messages)
    
    def _create_llm(self, model_config: Optional['ModelConfig'] = None):
        from ..config.models import ModelConfig
        
        config = model_config if model_config is not None else self.config.model.model

        return LLMCaller(
            api_key=config.api_key,
            model=config.name,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            default_headers={"Authorization": config.auth} if config.auth else None,
            system_prompt_registry=getattr(self, '_system_prompt_registry', None),
            logging_config=getattr(self, 'logging_config', None),
        )
    
    def _get_tools_for_role(self) -> List[BaseTool]:
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
    
    def _should_enable_spawn_agent(self) -> bool:
        if not self.role_config or not self.role_config.tools or not self.role_config.tools.builtin:
            return True
        builtin = self.role_config.tools.builtin
        if isinstance(builtin, dict):
            return builtin.get('spawn_agent', True)
        return True

    def _ensure_spawn_agent_tool(self) -> None:
        should_enable = self._should_enable_spawn_agent()
        has_spawn_agent = any(t.name == 'spawn_agent' for t in self.tools)
        
        if should_enable and not has_spawn_agent:
            spawn_agent_tool = create_spawn_agent_tool(self._sub_agent_manager)
            self.tools.append(spawn_agent_tool)
            self.logger.log_agent_action("spawn_agent_added", {
                "reason": "tool_missing_from_list",
                "role": self.get_role_name()
            })
        elif not should_enable and has_spawn_agent:
            self.tools = [t for t in self.tools if t.name != 'spawn_agent']
            self.logger.log_agent_action("spawn_agent_removed", {
                "reason": "disabled_by_role_config",
                "role": self.get_role_name()
            })
    
    def _load_system_prompt(self) -> str:
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
        if self.config.tools and hasattr(self.config.tools, 'tool_docs'):
            return self.config.tools.tool_docs.auto_inject
        return True
    
    def _generate_tool_docs(self) -> str:
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
    
    def _build_system_prompt_with_skills(self, base_prompt: str) -> str:
        if not self._role_skills or not self.skill_loader:
            return base_prompt
        
        skill_contents = []
        for skill_name in self._role_skills:
            content = self.skill_loader.get_skill_content_sync(skill_name)
            if content and isinstance(content, str):
                skill_contents.append(f"## {skill_name}\n\n{content}")
                self.context_manager.mark_skill_loaded(skill_name)
                self.logger.log_agent_action("skill_full_loaded", {
                    "skill": skill_name,
                    "content_length": len(content)
                })
            else:
                self.logger.log_agent_action("skill_content_unavailable", {
                    "skill": skill_name
                })
        
        if skill_contents:
            skills_section = "\n\n# 角色专用 Skills\n\n" + "\n\n".join(skill_contents)
            return f"{base_prompt}\n{skills_section}"
        
        return base_prompt
    
    def _build_system_prompt_registry(self) -> SystemPromptRegistry:
        registry = SystemPromptRegistry(logger=self.logger)
        
        base_prompt = self._load_system_prompt()
        registry.add_static("base_prompt", base_prompt)
        
        if self._role_skills and self.skill_loader:
            for skill_name in self._role_skills:
                content = self.skill_loader.get_skill_content_sync(skill_name)
                if content and isinstance(content, str):
                    registry.add_skill(skill_name, content)
                    self.context_manager.mark_skill_loaded(skill_name)
                    self.logger.log_agent_action("skill_full_loaded", {
                        "skill": skill_name,
                        "content_length": len(content)
                    })
                else:
                    self.logger.log_agent_action("skill_content_unavailable", {
                        "skill": skill_name
                    })
        
        return registry
    
    def _get_default_system_prompt(self) -> str:
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
        from .query_engine import SDKMessage, SubmitOptions
        
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
            skill_content = await self.skill_loader.load_full_skill(skill_name)
            self._system_prompt_registry.add_skill(skill_name, skill_content)
            self._current_system_prompt = self._system_prompt_registry.build()
            self._rebuild_query_engine()
            self.context_manager.mark_skill_loaded(skill_name)
        elif skill_name and self._system_prompt_registry.has_skill(skill_name):
            self._system_prompt_registry.mark_skill_referenced(skill_name)
        
        if self._query_engine is None:
            self._query_engine = self._create_query_engine()
        
        self._query_engine.update_session_metadata(role=self.get_role_name(), model=self.llm.model_name if hasattr(self.llm, 'model_name') else "")
        
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
        from .query_engine import SDKMessage, SubmitOptions
        
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
            skill_content = await self.skill_loader.load_full_skill(skill_name)
            self._system_prompt_registry.add_skill(skill_name, skill_content)
            self._current_system_prompt = self._system_prompt_registry.build()
            self._rebuild_query_engine()
            self.context_manager.mark_skill_loaded(skill_name)
        elif skill_name and self._system_prompt_registry.has_skill(skill_name):
            self._system_prompt_registry.mark_skill_referenced(skill_name)
        
        if self._query_engine is None:
            self._query_engine = self._create_query_engine()
        
        self._query_engine.update_session_metadata(role=self.get_role_name(), model=self.llm.model_name if hasattr(self.llm, 'model_name') else "")
        
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
    
    async def run_stream_structured(self, user_input: str):
        from .query_engine import SDKMessage, SubmitOptions
        
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
                yield SDKMessage.error("浏览器初始化失败，请检查 MCP 连接", error_type="browser")
                return
        
        skill_name = self.skill_loader.find_matching_skill(user_input)
        
        if skill_name and not self.context_manager.is_skill_loaded(skill_name):
            self.logger.log_agent_action("loading_skill", {"skill": skill_name})
            skill_content = await self.skill_loader.load_full_skill(skill_name)
            self._system_prompt_registry.add_skill(skill_name, skill_content)
            self._current_system_prompt = self._system_prompt_registry.build()
            self._rebuild_query_engine()
            self.context_manager.mark_skill_loaded(skill_name)
        elif skill_name and self._system_prompt_registry.has_skill(skill_name):
            self._system_prompt_registry.mark_skill_referenced(skill_name)
        
        if self._query_engine is None:
            self._query_engine = self._create_query_engine()
        
        self.logger.log_agent_action("query_engine_stream_start", {
            "session_id": self._query_engine.get_session_id(),
            "prompt_length": len(user_input)
        })
        
        start_time = time.time()
        
        try:
            options = SubmitOptions(stream=True)
            
            async for message in self._query_engine.submit_message(user_input, options):
                if message.type == "tool_use":
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
                
                yield message
            
            elapsed = time.time() - start_time
            usage = self._query_engine.get_usage()
            
            self.logger.log_agent_action("query_engine_stream_complete", {
                "elapsed_seconds": round(elapsed, 2),
                "total_tokens": usage.total_tokens,
                "cost_usd": usage.cost_usd
            })
            
        except Exception as e:
            import traceback
            self.logger.log_error("query_engine_stream", e)
            self.logger.log_agent_action("query_engine_stream_error", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc()
            })
            yield SDKMessage.error(str(e), error_type=type(e).__name__)

    async def _inject_skill(self, skill_name: str) -> str:
        skill_content = await self.skill_loader.load_full_skill(skill_name)
        
        self._system_prompt_registry.add_skill(skill_name, skill_content)
        self._current_system_prompt = self._system_prompt_registry.build()
        return self._current_system_prompt
    
    def get_system_prompt(self) -> str:
        return self._current_system_prompt
    
    def get_current_system_prompt(self) -> str:
        return self._current_system_prompt
    
    def get_loaded_skills(self) -> List[str]:
        return self.context_manager.get_loaded_skills()
    
    def _reload_execution_config(self) -> dict:
        old_values = {
            "max_turns": self.max_turns,
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
            
            self.max_turns = (
                exec_config.recursion_limit
                if exec_config.recursion_limit
                else self.config.agent.execution.recursion_limit
            )
            
            sub_agent_recursion_limit = (
                exec_config.sub_agent_recursion_limit
                if exec_config.sub_agent_recursion_limit
                else self.config.agent.execution.sub_agent_recursion_limit
            )
        else:
            self.max_context_tokens = self.config.agent.max_context_tokens
            self.max_turns = self.config.agent.execution.recursion_limit
            sub_agent_recursion_limit = self.config.agent.execution.sub_agent_recursion_limit
        
        if sub_agent_recursion_limit != old_values["sub_agent_recursion_limit"]:
            self._sub_agent_manager = SubAgentManager(
                llm=self.llm,
                parent_agent=self,
                sub_agents_dir="sub_agents",
                recursion_limit=sub_agent_recursion_limit,
                session_storage=self._session_storage
            )
        
        self._ensure_spawn_agent_tool()
        
        self._rebuild_query_engine()
        
        return {
            "max_turns": {"old": old_values["max_turns"], "new": self.max_turns},
            "sub_agent_recursion_limit": {"old": old_values["sub_agent_recursion_limit"], "new": self._sub_agent_manager.recursion_limit},
            "max_context_tokens": {"old": old_values["max_context_tokens"], "new": self.max_context_tokens}
        }
    
    def reload_system_prompt(self, role_config: Optional[RoleConfig] = None) -> None:
        if role_config is not None:
            self.role_config = role_config
            if role_config.tools and role_config.tools.skills:
                self._role_skills = role_config.tools.skills
            else:
                self._role_skills = None
            
            config_changes = self._reload_execution_config()
        
        self._system_prompt_registry = self._build_system_prompt_registry()
        self._current_system_prompt = self._system_prompt_registry.build()
        self._rebuild_query_engine()
        
        log_data = {
            "role_config_updated": role_config is not None,
            "role_skills": self._role_skills
        }
        if role_config is not None:
            log_data["config_changes"] = config_changes
        
        self.logger.log_agent_action("system_prompt_reloaded", log_data)
    
    def reload_tools(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry
        
        self.tools = self._get_tools_for_role()
        
        config_changes = self._reload_execution_config()
        
        self.logger.log_agent_action("tools_reloaded", {
            "tool_count": len(self.tools),
            "tool_names": [tool.name for tool in self.tools],
            "config_changes": config_changes
        })
    
    def update_role_skills(self, skills: Optional[List[str]]) -> None:
        self._role_skills = skills
        self._system_prompt_registry = self._build_system_prompt_registry()
        self._current_system_prompt = self._system_prompt_registry.build()
        self._rebuild_query_engine()
        
        self.logger.log_agent_action("role_skills_updated", {
            "skills": skills,
            "filtered": skills is not None
        })
    
    async def load_role_skills(self, skills: Optional[List[str]]) -> None:
        self._role_skills = skills
        self._system_prompt_registry = self._build_system_prompt_registry()
        self._current_system_prompt = self._system_prompt_registry.build()
        self._rebuild_query_engine()
        
        self.logger.log_agent_action("role_skills_loaded", {
            "skills": skills
        })
    
    def set_compression_callback(self, callback):
        if self._query_engine:
            self._query_engine.set_compression_callback(callback)

    def clear_context(self) -> None:
        self.context_manager.clear()
        self._query_engine = self._create_query_engine()
    
    def load_session(self, session_id: str) -> bool:
        if not self._session_storage or not self._query_engine:
            return False
        metadata = self._session_storage.get_session_metadata(session_id)
        if not metadata:
            return False
        _, messages = self._session_storage.load_session_with_meta(session_id)
        
        if metadata.role and metadata.role != self.get_role_name():
            try:
                from ..config.role_loader import RoleConfigLoader
                loader = RoleConfigLoader(self.roles_dir)
                role_config = loader.get_role(metadata.role)
                if role_config:
                    self.reload_system_prompt(role_config)
                    if metadata.model:
                        from ..config.models import ModelConfigLoader
                        model_loader = ModelConfigLoader()
                        merged_model = model_loader.get_merged_config(metadata.role)
                        if merged_model:
                            self.llm = self._create_llm(merged_model)
            except Exception:
                self.logger.log_agent_action("session_role_restore_failed", {
                    "session_id": session_id,
                    "role": metadata.role
                })
        
        if self._query_engine and messages:
            self._query_engine.mutable_messages = messages
            self._query_engine._session_id = session_id
            if self._session_storage:
                self._session_storage.append_messages(
                    session_id, messages, metadata={"role": metadata.role, "model": metadata.model}
                )
        
        self.logger.log_agent_action("session_loaded", {
            "session_id": session_id,
            "role": metadata.role,
            "message_count": len(messages) if messages else 0
        })
        return True
    
    def get_session_storage(self) -> Optional[SessionStorage]:
        return self._session_storage
    
    def get_current_session_id(self) -> str:
        if self._query_engine:
            return self._query_engine.get_session_id()
        return ""
    
    def interrupt(self, reason: str = "用户中断") -> None:
        if self._query_engine is not None and self._query_engine.is_running():
            self._query_engine.interrupt(reason)
    
    def activate_skills_for_paths(self, file_paths: List[str]) -> List[str]:
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
        self.config = new_config
        
        self.max_context_tokens = (
            self.role_config.execution.max_context_tokens
            if self.role_config and self.role_config.execution and self.role_config.execution.max_context_tokens
            else new_config.agent.max_context_tokens
        )
        
        self.max_turns = (
            self.role_config.execution.recursion_limit
            if self.role_config and self.role_config.execution and self.role_config.execution.recursion_limit
            else new_config.agent.execution.recursion_limit
        )
        
        self.compression_config = new_config.agent.message_compression
        self.logging_config = new_config.agent.logging
        
        self.logger.log_agent_action("config_updated", {
            "max_context_tokens": self.max_context_tokens,
            "max_turns": self.max_turns,
            "compression_enabled": self.compression_config.enabled
        })
