"""
SubAgent 管理器

根据设计文档 11.3-11.6 节实现，管理 SubAgent 的创建和执行。
"""

import asyncio
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from ..config.models import RoleConfig
from ..utils.logger import get_llm_logger
from ..tools.docs import generate_tool_docs_for_prompt
from .sub_agent_types import (
    SubAgentDefinition,
    SubAgentExecutionConfig,
    SubAgentInstance,
    SubAgentModelConfig,
    SubAgentSpawnOptions,
    SubAgentState,
    ToolInheritanceMode,
    ToolPermissionConfig,
)
from .sub_agent_lifecycle import SubAgentLifecycleManager


class ToolPermissionResolver:
    """工具权限解析器"""
    
    @staticmethod
    def resolve(
        parent_tools: List[BaseTool],
        permissions: ToolPermissionConfig,
        tool_registry: Any,
        available_tools: Optional[List[str]] = None
    ) -> List[BaseTool]:
        """解析工具权限
        
        应用顺序：
        1. 确定初始工具集（基于继承模式）
        2. 应用白名单（allowlist）
        3. 应用黑名单（denylist）
        
        Args:
            parent_tools: 父 Agent 的工具列表
            permissions: 权限配置
            tool_registry: 工具注册表
            available_tools: 可用工具列表
            
        Returns:
            过滤后的工具列表
        """
        if available_tools:
            tools = tool_registry.get_tools_by_names(available_tools)
        elif permissions.inherit_from_parent:
            tools = list(parent_tools)
        else:
            tools = []
        
        if permissions.allowlist:
            tools = [
                tool for tool in tools 
                if tool.name in permissions.allowlist
            ]
            
            for tool_name in permissions.allowlist:
                if not any(t.name == tool_name for t in tools):
                    tool = tool_registry.get_tool(tool_name)
                    if tool:
                        tools.append(tool)
        
        if permissions.denylist:
            tools = [
                tool for tool in tools 
                if tool.name not in permissions.denylist
            ]
        
        return tools


class ConfigInheritanceResolver:
    """配置继承解析器"""
    
    @staticmethod
    def resolve_model_config(
        parent_config: Any,
        sub_agent_config: SubAgentModelConfig
    ) -> Dict[str, Any]:
        """解析模型配置
        
        继承规则：
        - 如果 inherit=True，继承父 Agent 的模型配置
        - 子配置中的非 None 值会覆盖父配置
        
        Args:
            parent_config: 父 Agent 的模型配置
            sub_agent_config: SubAgent 的模型配置
            
        Returns:
            合并后的模型配置
        """
        if not sub_agent_config.inherit:
            return {
                "provider": sub_agent_config.provider,
                "name": sub_agent_config.name,
                "api_key": sub_agent_config.api_key,
                "base_url": sub_agent_config.base_url,
                "temperature": sub_agent_config.temperature,
                "max_tokens": sub_agent_config.max_tokens,
            }
        
        merged = {
            "provider": getattr(parent_config, 'provider', None),
            "name": getattr(parent_config, 'name', None),
            "api_key": getattr(parent_config, 'api_key', None),
            "base_url": getattr(parent_config, 'base_url', None),
            "temperature": getattr(parent_config, 'temperature', None),
            "max_tokens": getattr(parent_config, 'max_tokens', None),
        }
        
        if sub_agent_config.provider is not None:
            merged["provider"] = sub_agent_config.provider
        if sub_agent_config.name is not None:
            merged["name"] = sub_agent_config.name
        if sub_agent_config.api_key is not None:
            merged["api_key"] = sub_agent_config.api_key
        if sub_agent_config.base_url is not None:
            merged["base_url"] = sub_agent_config.base_url
        if sub_agent_config.temperature is not None:
            merged["temperature"] = sub_agent_config.temperature
        if sub_agent_config.max_tokens is not None:
            merged["max_tokens"] = sub_agent_config.max_tokens
        
        return merged


class SubAgentManager:
    """SubAgent 管理器
    
    负责：
    - 加载和管理 SubAgent 定义
    - 创建指定角色的 SubAgent
    - 创建动态系统提示词的 SubAgent
    - 工具继承和权限过滤
    - 递归深度控制
    """
    
    def __init__(
        self,
        llm: Any,
        parent_agent: Any,
        sub_agents_dir: str = "sub_agents",
        roles_dir: str = "config/roles",
        recursion_limit: int = 50,
        max_concurrent: int = 10
    ):
        """初始化 SubAgent 管理器
        
        Args:
            llm: LLM 实例
            parent_agent: 父 Agent 实例
            sub_agents_dir: SubAgent 配置目录
            roles_dir: 角色配置目录
            recursion_limit: 递归调用限制
            max_concurrent: 最大并发 SubAgent 数量
        """
        self.llm = llm
        self.parent_agent = parent_agent
        self.sub_agents_dir = Path(sub_agents_dir)
        self.roles_dir = Path(roles_dir)
        if not self.roles_dir.is_absolute():
            self.roles_dir = Path.cwd() / self.roles_dir
        self.recursion_limit = recursion_limit
        
        self.agent_definitions: Dict[str, SubAgentDefinition] = {}
        self._load_agent_definitions()
        
        self._logger = get_llm_logger()
        self._session_depths: Dict[str, int] = {}
        self._active_sub_agents: Dict[str, SubAgentInstance] = {}
        
        self._lifecycle_manager = SubAgentLifecycleManager(max_concurrent=max_concurrent)
    
    def _load_agent_definitions(self) -> None:
        """加载所有 SubAgent 定义"""
        if not self.sub_agents_dir.exists():
            return
        
        for config_file in self.sub_agents_dir.glob("*.yaml"):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_dict = yaml.safe_load(f)
                    if config_dict and 'name' in config_dict:
                        definition = SubAgentDefinition(**config_dict)
                        self.agent_definitions[definition.name] = definition
            except Exception as e:
                print(f"加载 SubAgent 配置失败 {config_file}: {e}")
    
    def get_agent_definition(self, agent_name: str) -> Optional[SubAgentDefinition]:
        """获取 SubAgent 定义
        
        Args:
            agent_name: SubAgent 名称
            
        Returns:
            SubAgentDefinition 或 None
        """
        return self.agent_definitions.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """列出所有预定义的 SubAgent
        
        Returns:
            SubAgent 名称列表
        """
        return list(self.agent_definitions.keys())
    
    def check_recursion_depth(self, session_id: str, max_depth: int) -> bool:
        """检查递归深度是否超过限制
        
        Args:
            session_id: 会话 ID
            max_depth: 最大递归深度
            
        Returns:
            True 表示可以继续创建子 Agent，False 表示超过限制
        """
        current = self._session_depths.get(session_id, 0)
        return current < max_depth
    
    def increment_depth(self, session_id: str) -> None:
        """增加递归深度"""
        old_depth = self._session_depths.get(session_id, 0)
        new_depth = old_depth + 1
        self._session_depths[session_id] = new_depth
        self._logger.log_agent_action("recursion_depth_incremented", {
            "session_id": session_id,
            "old_depth": old_depth,
            "new_depth": new_depth
        })
    
    def decrement_depth(self, session_id: str) -> None:
        """减少递归深度"""
        old_depth = self._session_depths.get(session_id, 0)
        if old_depth > 0:
            new_depth = old_depth - 1
            self._session_depths[session_id] = new_depth
            self._logger.log_agent_action("recursion_depth_decremented", {
                "session_id": session_id,
                "old_depth": old_depth,
                "new_depth": new_depth
            })
            if new_depth == 0:
                del self._session_depths[session_id]
    
    def get_current_depth(self, session_id: str) -> int:
        """获取当前递归深度
        
        Args:
            session_id: 会话 ID
            
        Returns:
            当前递归深度
        """
        return self._session_depths.get(session_id, 0)
    
    async def spawn_agent(self, options: SubAgentSpawnOptions) -> str:
        """生成并运行 SubAgent
        
        这是主要的入口方法，根据选项决定创建方式：
        1. 如果提供了 system_prompt，使用动态创建
        2. 否则尝试加载预定义配置或角色配置
        
        Args:
            options: 创建选项
            
        Returns:
            执行结果
        """
        parent_role = self.parent_agent.get_role_name() if hasattr(self.parent_agent, 'get_role_name') else 'unknown'
        self._logger.set_role_context(options.agent_name, parent_role=parent_role)
        
        if options.session_id:
            if not self.check_recursion_depth(options.session_id, options.max_recursion_depth):
                return f"错误：已达到最大递归深度限制（{options.max_recursion_depth}），无法创建更多子智能体"
            self.increment_depth(options.session_id)
        
        try:
            if options.system_prompt:
                result = await self._create_dynamic_sub_agent(options)
            else:
                result = await self._create_sub_agent_by_role(options)
            
            return result
            
        except Exception as e:
            self._logger.log_agent_action("spawn_agent_error", {
                "agent_name": options.agent_name,
                "error": str(e),
                "error_type": type(e).__name__
            })
            return f"错误：SubAgent 执行失败 - {str(e)}"
        
        finally:
            self._logger.clear_role_context()
            if options.session_id:
                self.decrement_depth(options.session_id)
    
    async def _create_sub_agent_by_role(self, options: SubAgentSpawnOptions) -> str:
        """根据角色创建 SubAgent
        
        Args:
            options: 创建选项
            
        Returns:
            执行结果
        """
        definition = self._load_role_definition(options.agent_name)
        
        if options.timeout is not None:
            definition.execution.timeout = options.timeout
        if options.use_query_engine is not None:
            definition.execution.use_query_engine = options.use_query_engine
        if options.tool_inheritance is not None:
            definition.tool_inheritance = options.tool_inheritance
        if options.available_tools is not None:
            definition.available_tools = options.available_tools
        
        tools = self._resolve_tools(definition)
        
        system_prompt = await self._build_system_prompt(definition, tools)
        
        llm = self._create_llm(definition)
        
        sub_agent = self._create_agent_instance(
            llm=llm,
            tools=tools,
            system_prompt=system_prompt,
            definition=definition
        )
        
        return await self._execute_sub_agent(
            sub_agent=sub_agent,
            task=options.task,
            definition=definition,
            session_id=options.session_id
        )
    
    async def _create_dynamic_sub_agent(self, options: SubAgentSpawnOptions) -> str:
        """创建动态系统提示词的 SubAgent
        
        Args:
            options: 创建选项
            
        Returns:
            执行结果
        """
        system_prompt = options.system_prompt
        
        if system_prompt is None:
            system_prompt = await self._generate_system_prompt(
                options.agent_name, 
                options.task
            )
        
        tool_inheritance = (
            ToolInheritanceMode.INHERIT_ALL 
            if options.inherit_parent_tools 
            else ToolInheritanceMode.INDEPENDENT
        )
        
        definition = SubAgentDefinition(
            name=options.agent_name,
            description=f"动态创建的 SubAgent: {options.agent_name}",
            system_prompt=system_prompt,
            tool_inheritance=tool_inheritance,
            available_tools=options.available_tools,
            execution=SubAgentExecutionConfig(
                timeout=options.timeout or 120,
                recursion_limit=self.recursion_limit,
                use_query_engine=options.use_query_engine or False
            )
        )
        
        tools = self._resolve_tools(definition)
        
        llm = self._create_llm(definition)
        
        sub_agent = self._create_agent_instance(
            llm=llm,
            tools=tools,
            system_prompt=system_prompt,
            definition=definition
        )
        
        return await self._execute_sub_agent(
            sub_agent=sub_agent,
            task=options.task,
            definition=definition,
            session_id=options.session_id
        )
    
    def _load_role_definition(self, role_name: str) -> SubAgentDefinition:
        """加载角色定义
        
        优先级：
        1. 预定义的 SubAgent 定义
        2. 角色配置文件（尝试多种命名格式）
        3. 默认定义
        
        Args:
            role_name: 角色名称
            
        Returns:
            SubAgentDefinition
        """
        if role_name in self.agent_definitions:
            return self.agent_definitions[role_name]
        
        possible_filenames = [
            f"{role_name}.yaml",
            f"{role_name.replace('-', '_')}.yaml",
            f"{role_name.replace('_', '-')}.yaml",
        ]
        
        for filename in possible_filenames:
            role_config_path = self.roles_dir / filename
            if role_config_path.exists():
                self._logger.log_agent_action("sub_agent_role_definition_found", {
                    "role_name": role_name,
                    "filename": filename,
                    "role_config_path": str(role_config_path)
                })
                return self._convert_role_config_to_definition(role_config_path)
        
        self._logger.log_agent_action("sub_agent_role_definition_not_found", {
            "role_name": role_name,
            "roles_dir": str(self.roles_dir),
            "tried_filenames": possible_filenames
        })
        
        return SubAgentDefinition(
            name=role_name,
            description=f"动态创建的 SubAgent: {role_name}",
            system_prompt=f"你是一个名为 {role_name} 的子智能体，负责执行特定任务。",
            execution=SubAgentExecutionConfig(
                timeout=120,
                recursion_limit=self.recursion_limit
            )
        )
    
    def _convert_role_config_to_definition(
        self, 
        role_config_path: Path
    ) -> SubAgentDefinition:
        """将角色配置转换为 SubAgent 定义
        
        Args:
            role_config_path: 角色配置文件路径
            
        Returns:
            SubAgentDefinition
        """
        with open(role_config_path, 'r', encoding='utf-8') as f:
            role_config_dict = yaml.safe_load(f)
        
        role_config = RoleConfig(**role_config_dict)
        
        system_prompt = ""
        if role_config.system_prompt_file:
            prompt_path = Path(role_config.system_prompt_file)
            if not prompt_path.is_absolute():
                prompt_path = Path.cwd() / prompt_path
            
            self._logger.log_agent_action("sub_agent_system_prompt_file_loading", {
                "role_name": role_config.name,
                "system_prompt_file": role_config.system_prompt_file,
                "resolved_path": str(prompt_path)
            })
            
            if prompt_path.exists():
                try:
                    system_prompt = prompt_path.read_text(encoding='utf-8')
                    self._logger.log_agent_action("sub_agent_system_prompt_file_loaded", {
                        "role_name": role_config.name,
                        "prompt_length": len(system_prompt),
                        "prompt_preview": system_prompt[:100] + "..." if len(system_prompt) > 100 else system_prompt
                    })
                except Exception as e:
                    self._logger.log_agent_action("sub_agent_system_prompt_file_load_error", {
                        "role_name": role_config.name,
                        "error": str(e)
                    })
            else:
                self._logger.log_agent_action("sub_agent_system_prompt_file_not_found", {
                    "role_name": role_config.name,
                    "prompt_path": str(prompt_path)
                })
        
        available_tools = role_config.available_tools or []
        
        skills: List[str] = []
        if role_config.tools and role_config.tools.skills:
            skills = role_config.tools.skills
        
        model_config = SubAgentModelConfig(inherit=True)
        if role_config.model:
            model_config = SubAgentModelConfig(
                inherit=role_config.model.inherit,
                provider=role_config.model.provider,
                name=role_config.model.name,
                api_key=role_config.model.api_key,
                base_url=role_config.model.base_url,
                temperature=role_config.model.temperature,
                max_tokens=role_config.model.max_tokens
            )
        
        self._logger.log_agent_action("sub_agent_config_converted", {
            "role_name": role_config.name,
            "skills": skills,
            "available_tools": available_tools[:5] if available_tools else [],
            "model_inherit": model_config.inherit
        })
        
        return SubAgentDefinition(
            name=role_config.name,
            description=role_config.description or "",
            system_prompt=system_prompt,
            model=model_config,
            execution=SubAgentExecutionConfig(
                timeout=role_config.execution.timeout if role_config.execution else 300,
                recursion_limit=role_config.execution.recursion_limit if role_config.execution else self.recursion_limit,
                use_query_engine=role_config.execution.use_query_engine if role_config.execution else False
            ),
            tool_inheritance=ToolInheritanceMode.INHERIT_SELECTED,
            available_tools=available_tools if available_tools else None,
            skills=skills if skills else None
        )
    
    def _resolve_tools(self, definition: SubAgentDefinition) -> List[BaseTool]:
        """解析工具列表
        
        根据工具继承模式和权限配置，确定最终的工具列表
        
        Args:
            definition: SubAgent 定义
            
        Returns:
            工具列表
        """
        parent_tools = self.parent_agent.tools
        
        if definition.tool_inheritance == ToolInheritanceMode.INHERIT_ALL:
            tools = list(parent_tools)
        elif definition.tool_inheritance == ToolInheritanceMode.INDEPENDENT:
            if definition.available_tools:
                tools = self.parent_agent.tool_registry.get_tools_by_names(
                    definition.available_tools
                )
            else:
                tools = []
        else:  # INHERIT_SELECTED
            if definition.available_tools:
                tools = self.parent_agent.tool_registry.get_tools_by_names(
                    definition.available_tools
                )
            else:
                tools = list(parent_tools)
        
        tools = ToolPermissionResolver.resolve(
            parent_tools=parent_tools,
            permissions=definition.tool_permissions,
            tool_registry=self.parent_agent.tool_registry,
            available_tools=definition.available_tools
        )
        
        return tools
    
    async def _build_system_prompt(
        self, 
        definition: SubAgentDefinition, 
        tools: List[BaseTool]
    ) -> str:
        """构建系统提示词
        
        Args:
            definition: SubAgent 定义
            tools: 工具列表
            
        Returns:
            系统提示词
        """
        base_prompt = definition.get_system_prompt_content(self.sub_agents_dir)
        
        skills_content = await self._load_skills_content(definition.skills)
        
        tool_docs = self._generate_tool_docs_for_sub_agent(tools, definition.skills)
        
        parts = [base_prompt]
        if skills_content:
            parts.append(f"\n\n# 可用技能\n\n{skills_content}")
        if tool_docs:
            parts.append(f"\n\n{tool_docs}")
        
        final_prompt = "\n\n".join(parts)
        
        self._logger.log_agent_action("sub_agent_system_prompt_built", {
            "skills": definition.skills,
            "skills_loaded": bool(skills_content),
            "prompt_length": len(final_prompt)
        })
        
        return final_prompt
    
    async def _load_skills_content(self, skills: Optional[List[str]]) -> str:
        """加载 skills 内容
        
        Args:
            skills: skills 名称列表
            
        Returns:
            skills 内容字符串
        """
        if not skills:
            return ""
        
        if hasattr(self.parent_agent, 'skill_loader') and self.parent_agent.skill_loader:
            contents = []
            for skill_name in skills:
                try:
                    content = await self.parent_agent.skill_loader.load_full_skill(skill_name)
                    if content:
                        contents.append(f"## {skill_name}\n\n{content}")
                        self._logger.log_agent_action("sub_agent_skill_loaded", {
                            "skill_name": skill_name,
                            "content_length": len(content)
                        })
                except Exception as e:
                    self._logger.log_error(f"load_skill_{skill_name}", e)
            return "\n\n".join(contents)
        
        return ""
    
    def _generate_tool_docs_for_sub_agent(
        self, 
        tools: List[BaseTool],
        skills: Optional[List[str]] = None
    ) -> str:
        """为 SubAgent 生成工具说明文档
        
        Args:
            tools: 工具列表
            skills: skills 列表
            
        Returns:
            工具说明文档
        """
        builtin_tools = []
        mcp_tools = []
        
        builtin_names = {'spawn_agent', 'shell_tool', 'file_read', 'file_write', 
                        'file_list', 'file_search', 'file_exists', 'file_mkdir', 
                        'file_replace', 'file_delete'}
        
        for tool in tools:
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            if tool_name in builtin_names:
                builtin_tools.append(tool_name)
            else:
                mcp_tools.append({
                    "name": tool_name,
                    "description": tool.description if hasattr(tool, 'description') else "",
                    "parameters": []
                })
        
        skills_metadata = []
        if skills and hasattr(self.parent_agent, 'skill_loader') and self.parent_agent.skill_loader:
            try:
                skill_metadata_dict = self.parent_agent.skill_loader.get_all_skill_metadata()
                for skill_name in skills:
                    if skill_name in skill_metadata_dict:
                        meta = skill_metadata_dict[skill_name]
                        skills_metadata.append({
                            "name": skill_name,
                            "description": meta.get("description", ""),
                            "triggers": meta.get("triggers", []),
                            "required_tools": meta.get("required_tools", [])
                        })
            except Exception as e:
                self._logger.log_error("get_skill_metadata", e)
        
        return generate_tool_docs_for_prompt(
            builtin_tools=builtin_tools,
            mcp_tools=mcp_tools,
            skills=skills_metadata,
            include_examples=True
        )
    
    def _create_llm(self, definition: SubAgentDefinition) -> Any:
        """创建 LLM 实例
        
        Args:
            definition: SubAgent 定义
            
        Returns:
            LLM 实例
        """
        if definition.model.inherit:
            return self.llm
        
        model_config = ConfigInheritanceResolver.resolve_model_config(
            self.parent_agent.config.model.model,
            definition.model
        )
        
        if model_config.get("name") and model_config.get("api_key"):
            from langchain_openai import ChatOpenAI
            
            return ChatOpenAI(
                model=model_config.get("name"),
                api_key=model_config.get("api_key"),
                base_url=model_config.get("base_url"),
                temperature=model_config.get("temperature", 0.7),
                max_tokens=model_config.get("max_tokens", 2000)
            )
        
        return self.llm
    
    def _create_agent_instance(
        self,
        llm: Any,
        tools: List[BaseTool],
        system_prompt: str,
        definition: SubAgentDefinition
    ) -> Any:
        """创建 Agent 实例
        
        Args:
            llm: LLM 实例
            tools: 工具列表
            system_prompt: 系统提示词
            definition: SubAgent 定义
            
        Returns:
            Agent 实例
        """
        return create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt
        )
    
    async def _execute_sub_agent(
        self,
        sub_agent: Any,
        task: str,
        definition: SubAgentDefinition,
        session_id: Optional[str] = None
    ) -> str:
        """执行 SubAgent
        
        Args:
            sub_agent: Agent 实例
            task: 任务描述
            definition: SubAgent 定义
            session_id: 会话 ID
            
        Returns:
            执行结果
        """
        self._logger.log_agent_action("sub_agent_execution_start", {
            "name": definition.name,
            "task": task[:100] + "..." if len(task) > 100 else task,
            "timeout": definition.execution.timeout,
            "recursion_limit": definition.execution.recursion_limit,
            "session_id": session_id
        })
        
        messages_for_log = []
        system_prompt_content = definition.get_system_prompt_content(self.sub_agents_dir)
        if system_prompt_content:
            messages_for_log.append(SystemMessage(content=system_prompt_content[:500] + "..." if len(system_prompt_content) > 500 else system_prompt_content))
        messages_for_log.append(HumanMessage(content=task))
        
        model_name = self.llm.model_name if hasattr(self.llm, 'model_name') else 'unknown'
        self._logger.log_request(messages_for_log, model_name)
        
        last_error = None
        for attempt in range(definition.execution.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    sub_agent.ainvoke(
                        {"messages": [HumanMessage(content=task)]},
                        config={"recursion_limit": definition.execution.recursion_limit}
                    ),
                    timeout=definition.execution.timeout
                )
                
                final_result = result["messages"][-1].content
                
                self._logger.log_agent_action("sub_agent_execution_success", {
                    "name": definition.name,
                    "attempt": attempt + 1,
                    "result_length": len(final_result) if final_result else 0
                })
                
                return final_result
                
            except asyncio.TimeoutError:
                last_error = f"子智能体执行超时（{definition.execution.timeout}秒）"
                self._logger.log_agent_action("sub_agent_execution_timeout", {
                    "name": definition.name,
                    "attempt": attempt + 1,
                    "timeout": definition.execution.timeout
                })
            except Exception as e:
                last_error = f"子智能体执行失败：{str(e)}"
                self._logger.log_agent_action("sub_agent_execution_error", {
                    "name": definition.name,
                    "attempt": attempt + 1,
                    "error": str(e)
                })
            
            if attempt < definition.execution.max_retries:
                await asyncio.sleep(1)
        
        return f"错误：{last_error}，已重试{definition.execution.max_retries}次"
    
    async def _generate_system_prompt(
        self,
        agent_name: str,
        task: str
    ) -> str:
        """生成系统提示词
        
        让 LLM 根据任务描述生成合适的系统提示词
        
        Args:
            agent_name: SubAgent 名称
            task: 任务描述
            
        Returns:
            生成的系统提示词
        """
        prompt_generation_msg = f"""请为以下任务生成一个专门的子智能体系统提示词。

子智能体名称：{agent_name}
任务描述：{task}

请生成一个简洁、专业的系统提示词，包括：
1. 角色定位
2. 核心职责
3. 工作流程
4. 输出格式要求

直接输出系统提示词内容，不要包含其他说明。"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="你是一个系统提示词生成专家。"),
                HumanMessage(content=prompt_generation_msg)
            ])
            
            generated_prompt = response.content
            
            self._logger.log_agent_action("system_prompt_generated", {
                "agent_name": agent_name,
                "prompt_length": len(generated_prompt)
            })
            
            return generated_prompt
            
        except Exception as e:
            self._logger.log_agent_action("system_prompt_generation_failed", {
                "agent_name": agent_name,
                "error": str(e)
            })
            return f"你是一个名为 {agent_name} 的子智能体，负责执行以下任务：{task}"
    
    def get_lifecycle_manager(self) -> SubAgentLifecycleManager:
        """获取生命周期管理器
        
        Returns:
            SubAgentLifecycleManager
        """
        return self._lifecycle_manager
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "predefined_agents": list(self.agent_definitions.keys()),
            "active_sessions": len(self._session_depths),
            "session_depths": dict(self._session_depths),
            "lifecycle_stats": self._lifecycle_manager.get_statistics()
        }


def create_spawn_agent_tool(sub_agent_manager: SubAgentManager):
    """创建绑定到特定 Agent 实例的 spawn_agent 工具
    
    Args:
        sub_agent_manager: SubAgent 管理器实例
        
    Returns:
        绑定到当前 Agent 实例的 spawn_agent 工具
    """
    from langchain_core.tools import tool
    
    @tool
    async def spawn_agent(
        agent_name: str,
        task: str,
        system_prompt: Optional[str] = None,
        inherit_parent_tools: bool = True,
        session_id: Optional[str] = None,
        max_recursion_depth: int = 5,
        timeout: Optional[int] = None,
        use_query_engine: Optional[bool] = None,
        tool_inheritance: Optional[str] = None,
        available_tools: Optional[List[str]] = None
    ) -> str:
        """生成并运行一个子智能体
        
        这是一个通用的子智能体调用工具。子智能体有独立的系统提示词和上下文，
        不会污染主智能体的对话历史。
        
        子智能体默认继承父角色的所有工具权限和配置。
        
        Args:
            agent_name: 子智能体名称
                - 如果是预定义的子智能体（如"snapshot-analyzer"），会加载对应配置
                - 如果是角色名称（如"test-case-executor"），会加载角色配置
                - 如果是自定义名称，需要提供 system_prompt 参数
            
            task: 要执行的任务描述
            
            system_prompt: 可选的系统提示词
                - 如果提供，会使用这个提示词创建子智能体
                - 如果不提供，会从配置文件加载预定义的提示词
                - 如果都没有，会根据任务动态生成提示词
            
            inherit_parent_tools: 是否继承父角色的工具（默认 True）
            
            session_id: 会话 ID（用于递归深度控制）
            
            max_recursion_depth: 最大递归深度（默认 5）
            
            timeout: 执行超时时间（秒），默认使用配置中的值
            
            use_query_engine: 是否使用 Query Engine，默认使用配置中的值
            
            tool_inheritance: 工具继承模式
                - "inherit_all": 继承所有父工具
                - "inherit_selected": 继承选定的工具
                - "independent": 独立工具集
            
            available_tools: 可用工具列表（当指定工具继承模式时使用）
        
        Returns:
            子智能体的执行结果
        
        Examples:
            # 使用预定义的 SubAgent
            result = spawn_agent("snapshot-analyzer", "分析这个页面快照：...")
            
            # 使用角色配置
            result = spawn_agent("test-case-executor", "执行测试案例：登录功能")
            
            # 使用自定义系统提示词
            result = spawn_agent(
                "my-agent",
                "分析数据",
                system_prompt="你是数据分析专家..."
            )
            
            # 动态生成系统提示词
            result = spawn_agent(
                "data-processor",
                "处理这批数据并生成报告"
            )
        """
        inheritance_mode = None
        if tool_inheritance:
            try:
                inheritance_mode = ToolInheritanceMode(tool_inheritance)
            except ValueError:
                pass
        
        options = SubAgentSpawnOptions(
            agent_name=agent_name,
            task=task,
            system_prompt=system_prompt,
            inherit_parent_tools=inherit_parent_tools,
            session_id=session_id,
            max_recursion_depth=max_recursion_depth,
            timeout=timeout,
            use_query_engine=use_query_engine,
            tool_inheritance=inheritance_mode,
            available_tools=available_tools
        )
        
        return await sub_agent_manager.spawn_agent(options)
    
    return spawn_agent
