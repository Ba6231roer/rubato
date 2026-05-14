import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path
import threading

from ..config.models import AppConfig, RoleConfig, ProjectConfig, FileToolsConfig, UnifiedToolsConfig
from ..config.loader import ConfigLoader
from ..context.manager import ContextManager
from ..context.session_storage import SessionStorage
from ..skills.loader import SkillLoader
from ..skills.manager import SkillManager
from ..mcp.tools import ToolRegistry
from ..tools.provider import LocalToolProvider, ShellToolProvider
from ..tools.mcp_provider import MCPToolProvider
from ..tools.file_tools import FileToolProvider
from .agent import RubatoAgent
from .role_manager import RoleManager, DEFAULT_ROLE_NAME
from ..utils.logger import get_llm_logger


class InstanceStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    DISPOSED = "disposed"


@dataclass
class AgentInstance:
    instance_id: str
    agent: RubatoAgent
    context_manager: ContextManager
    skill_loader: SkillLoader
    tool_registry: ToolRegistry
    role_name: Optional[str] = None
    status: InstanceStatus = InstanceStatus.IDLE
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: Optional[datetime] = None
    task_count: int = 0
    error_message: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def acquire(self) -> bool:
        with self._lock:
            if self.status == InstanceStatus.IDLE:
                self.status = InstanceStatus.BUSY
                self.last_used_at = datetime.now()
                return True
            return False

    def release(self) -> None:
        with self._lock:
            if self.status == InstanceStatus.BUSY:
                self.status = InstanceStatus.IDLE

    def mark_error(self, error_message: str) -> None:
        with self._lock:
            self.status = InstanceStatus.ERROR
            self.error_message = error_message

    def dispose(self) -> None:
        with self._lock:
            self.status = InstanceStatus.DISPOSED
            self.context_manager.clear()

    def is_available(self) -> bool:
        with self._lock:
            return self.status == InstanceStatus.IDLE


class AgentPool:
    """Agent实例池管理器"""

    def __init__(
        self,
        config: AppConfig,
        max_instances: int = 5,
        default_role_name: Optional[str] = None,
        roles_dir: str = "config/roles",
        skills_dir: str = "skills"
    ):
        self.config = config
        self.max_instances = max_instances
        self.default_role_name = default_role_name
        self.roles_dir = roles_dir
        self.skills_dir = skills_dir

        self._instances: Dict[str, AgentInstance] = {}
        self._instances_lock = threading.RLock()
        self._role_manager: Optional[RoleManager] = None
        self._logger = get_llm_logger()

        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        self._role_manager = RoleManager(
            roles_dir=self.roles_dir,
            default_model_config=self.config.model
        )
        self._role_manager.load_roles()
        
        if self._role_manager.has_role(DEFAULT_ROLE_NAME):
            self.default_role_name = DEFAULT_ROLE_NAME
            self._logger.log_agent_action("default_role_set", {
                "default_role_name": DEFAULT_ROLE_NAME
            })
        
        self._initialized = True

        self._logger.log_agent_action("agent_pool_initialized", {
            "max_instances": self.max_instances,
            "available_roles": self._role_manager.list_roles()
        })

    def _create_context_manager(self, role_config: Optional[RoleConfig] = None) -> ContextManager:
        return ContextManager()

    def _create_skill_loader(self) -> SkillLoader:
        disabled_skills = None
        
        if self.config.skills:
            disabled_skills = self.config.skills.disabled_skills
        
        return SkillLoader(
            skills_dir=self.skills_dir,
            disabled_skills=disabled_skills
        )

    def _create_tool_registry(
        self,
        mcp_manager=None,
        role_config: Optional[RoleConfig] = None,
        skill_loader: Optional[SkillLoader] = None,
        on_skill_changed=None
    ) -> ToolRegistry:
        registry = ToolRegistry()
        tools_summary = {"builtin": [], "mcp": [], "file_tools": []}
        
        unified_config = self._get_unified_tools_config(role_config)
        
        if unified_config and unified_config.builtin.enabled:
            if unified_config.builtin.shell_tool.enabled:
                shell_provider = ShellToolProvider()
                registry.register_provider(shell_provider)
                tools_summary["builtin"].append("shell_tool")
        else:
            shell_provider = ShellToolProvider()
            registry.register_provider(shell_provider)
            tools_summary["builtin"].append("shell_tool")
        
        if mcp_manager is not None:
            should_register_mcp = True
            if role_config and role_config.tools and role_config.tools.mcp:
                mcp_role_config = role_config.tools.mcp
                if isinstance(mcp_role_config, dict):
                    should_register_mcp = mcp_role_config.get('enabled', True)
            
            if should_register_mcp:
                mcp_config = self.config.mcp.model_dump() if self.config.mcp else {}
                mcp_provider = MCPToolProvider(mcp_config, mcp_manager)
                registry.register_provider(mcp_provider)
                tools_summary["mcp"] = ["mcp_tools"]
        
        if self._should_enable_file_tools(role_config, unified_config):
            file_tool_provider = self._create_file_tool_provider(role_config, unified_config)
            if file_tool_provider and file_tool_provider.is_available():
                registry.register_provider(file_tool_provider)
                tools_summary["file_tools"] = [t.name for t in file_tool_provider.get_tools()]
        
        if self._should_enable_skill_manage(role_config, unified_config):
            from ..tools.skill_manage import create_skill_manage_tool
            skill_manage_tool = create_skill_manage_tool(
                skill_manager=skill_loader if isinstance(skill_loader, SkillLoader) else None,
                on_skill_changed=on_skill_changed
            )
            if skill_manage_tool is not None:
                registry.register(skill_manage_tool)
                tools_summary["builtin"].append("skill_manage")
        
        self._log_tool_summary(tools_summary)
        
        return registry
    
    def _get_unified_tools_config(self, role_config: Optional[RoleConfig] = None) -> Optional[UnifiedToolsConfig]:
        if role_config and role_config.tools:
            return self._convert_role_tools_to_unified(role_config.tools)
        
        if role_config and role_config.available_tools:
            return self._convert_available_tools_to_unified(role_config.available_tools)
        
        if self.config.tools:
            return self.config.tools
        
        return None
    
    def _convert_available_tools_to_unified(self, available_tools: List[str]) -> UnifiedToolsConfig:
        from ..config.models import (
            UnifiedToolsConfig, BuiltinToolsConfig, MCPToolsConfig, 
            SkillsToolsConfig, ToolDocsConfig, FileToolsSubConfig,
            SpawnAgentConfig, ShellToolConfig
        )
        
        builtin_names = {'spawn_agent', 'shell_tool', 'file_read', 'file_write', 
                        'file_list', 'file_search', 'file_exists', 'file_mkdir', 
                        'file_replace', 'file_delete', 'file_copy', 'file_move', 'terminal',
                        'skill_manage'}
        
        has_spawn_agent = 'spawn_agent' in available_tools
        has_shell_tool = 'shell_tool' in available_tools
        has_file_tools = any(t in available_tools for t in ['file_read', 'file_write', 'file_list', 'file_exists'])
        has_mcp = any(t not in builtin_names for t in available_tools)
        
        return UnifiedToolsConfig(
            builtin=BuiltinToolsConfig(
                enabled=True,
                spawn_agent=SpawnAgentConfig(enabled=has_spawn_agent),
                shell_tool=ShellToolConfig(enabled=has_shell_tool),
                file_tools=FileToolsSubConfig(enabled=has_file_tools)
            ),
            mcp=MCPToolsConfig(auto_connect=has_mcp),
            skills=SkillsToolsConfig(),
            tool_docs=ToolDocsConfig()
        )
    
    def _convert_role_tools_to_unified(self, role_tools) -> Optional[UnifiedToolsConfig]:
        from ..config.models import (
            UnifiedToolsConfig, BuiltinToolsConfig, MCPToolsConfig, 
            SkillsToolsConfig, ToolDocsConfig, FileToolsSubConfig,
            SpawnAgentConfig, ShellToolConfig
        )
        
        builtin_config = BuiltinToolsConfig()
        if role_tools.builtin:
            builtin_data = role_tools.builtin
            if isinstance(builtin_data, dict):
                builtin_config = BuiltinToolsConfig(
                    enabled=builtin_data.get('enabled', True),
                    spawn_agent=SpawnAgentConfig(enabled=builtin_data.get('spawn_agent', True)),
                    shell_tool=ShellToolConfig(enabled=builtin_data.get('shell_tool', True)),
                    file_tools=FileToolsSubConfig(
                        enabled=builtin_data.get('file_tools', {}).get('enabled', True)
                    ),
                    skill_manage=SpawnAgentConfig(enabled=builtin_data.get('skill_manage', True))
                )
        
        mcp_config = MCPToolsConfig()
        if role_tools.mcp:
            mcp_data = role_tools.mcp
            if isinstance(mcp_data, dict):
                mcp_config = MCPToolsConfig(
                    auto_connect=mcp_data.get('enabled', True)
                )
        
        skills_list = role_tools.skills if role_tools.skills else []
        
        self._logger.log_agent_action("role_tools_converted", {
            "skills": skills_list,
            "builtin_enabled": builtin_config.enabled,
            "mcp_auto_connect": mcp_config.auto_connect
        })
        
        return UnifiedToolsConfig(
            builtin=builtin_config,
            mcp=mcp_config,
            skills=SkillsToolsConfig(),
            tool_docs=ToolDocsConfig()
        )
    
    def _log_tool_summary(self, tools_summary: Dict[str, List[str]]) -> None:
        total_tools = sum(len(tools) for tools in tools_summary.values())
        summary_lines = [f"工具加载完成: {total_tools}个工具"]
        
        if tools_summary["builtin"]:
            summary_lines.append(f"  - 内置工具: {', '.join(tools_summary['builtin'])}")
        if tools_summary["file_tools"]:
            summary_lines.append(f"  - 文件工具: {', '.join(tools_summary['file_tools'])}")
        if tools_summary["mcp"]:
            summary_lines.append(f"  - MCP工具: {', '.join(tools_summary['mcp'])}")
        
        self._logger.log_agent_action("tools_loaded", {
            "summary": "\n".join(summary_lines),
            "total": total_tools,
            "builtin": tools_summary["builtin"],
            "file_tools": tools_summary["file_tools"],
            "mcp": tools_summary["mcp"]
        })
    
    def _should_enable_file_tools(
        self, 
        role_config: Optional[RoleConfig] = None,
        unified_config: Optional[UnifiedToolsConfig] = None
    ) -> bool:
        if unified_config and unified_config.builtin.file_tools.enabled:
            return True
        
        if role_config and role_config.file_tools:
            if hasattr(role_config.file_tools, 'enabled'):
                return role_config.file_tools.enabled
            return True
        
        if self.config.file_tools:
            return self.config.file_tools.enabled
        
        return False
    
    def _should_enable_skill_manage(
        self,
        role_config: Optional[RoleConfig] = None,
        unified_config: Optional[UnifiedToolsConfig] = None
    ) -> bool:
        if unified_config and unified_config.builtin:
            builtin_data = unified_config.builtin
            if hasattr(builtin_data, 'skill_manage') and builtin_data.skill_manage is not None:
                if hasattr(builtin_data.skill_manage, 'enabled'):
                    return builtin_data.skill_manage.enabled
        return True
    
    def _create_file_tool_provider(
        self,
        role_config: Optional[RoleConfig] = None,
        unified_config: Optional[UnifiedToolsConfig] = None
    ) -> Optional[FileToolProvider]:
        project_config = self._get_project_config(role_config)
        file_tools_config = self._get_file_tools_config(role_config, unified_config)
        
        if not project_config or not file_tools_config:
            return None
        
        try:
            return FileToolProvider(project_config, file_tools_config)
        except Exception as e:
            self._logger.log_error("create_file_tool_provider", e)
            return None
    
    def _get_file_tools_config(
        self, 
        role_config: Optional[RoleConfig] = None,
        unified_config: Optional[UnifiedToolsConfig] = None
    ) -> Optional[FileToolsConfig]:
        if unified_config and unified_config.builtin.file_tools:
            ft_config = unified_config.builtin.file_tools
            from ..config.models import PermissionMode
            permissions = ft_config.permissions or {}
            return FileToolsConfig(
                enabled=ft_config.enabled,
                permission_mode=ft_config.permission_mode,
                custom_permissions=permissions,
                default_permissions=ft_config.permission_mode,
                audit=ft_config.audit
            )
        
        if role_config and role_config.file_tools:
            if hasattr(role_config.file_tools, 'permissions'):
                from ..config.models import PermissionMode
                permissions = role_config.file_tools.permissions or {}
                return FileToolsConfig(
                    enabled=True,
                    permission_mode=permissions.get('default', PermissionMode.ask),
                    custom_permissions=permissions.get('custom', {}),
                    default_permissions=permissions.get('default', PermissionMode.ask),
                    audit=getattr(role_config.file_tools, 'audit', True)
                )
            return self.config.file_tools if self.config.file_tools else FileToolsConfig()
        
        if self.config.file_tools:
            return self.config.file_tools
        
        return None
    
    def _get_project_config(self, role_config: Optional[RoleConfig] = None) -> Optional[ProjectConfig]:
        if role_config and role_config.file_tools:
            if hasattr(role_config.file_tools, 'workspace'):
                from ..config.models import WorkspaceConfig
                workspace_config = role_config.file_tools.workspace
                if isinstance(workspace_config, WorkspaceConfig):
                    return ProjectConfig(
                        name=self.config.project.name if self.config.project else "default",
                        root=self.config.project.root if self.config.project else Path.cwd(),
                        workspace=workspace_config
                    )
        
        if self.config.project:
            return self.config.project
        
        return None

    async def create_instance(
        self,
        instance_id: Optional[str] = None,
        role_name: Optional[str] = None
    ) -> AgentInstance:
        if not self._initialized:
            await self.initialize()

        with self._instances_lock:
            if len(self._instances) >= self.max_instances:
                raise RuntimeError(f"已达到最大实例数限制: {self.max_instances}")

        effective_role_name = role_name or self.default_role_name
        
        if effective_role_name is None and self._role_manager:
            if self._role_manager.has_role(DEFAULT_ROLE_NAME):
                effective_role_name = DEFAULT_ROLE_NAME
                self._logger.log_agent_action("role_fallback_to_default", {
                    "requested_role": role_name,
                    "default_role_name": DEFAULT_ROLE_NAME
                })
        
        role_config: Optional[RoleConfig] = None

        if effective_role_name and self._role_manager:
            if self._role_manager.has_role(effective_role_name):
                role_config = self._role_manager.get_role(effective_role_name)

        context_manager = self._create_context_manager(role_config)
        skill_loader = self._create_skill_loader()
        await skill_loader.load_skill_metadata()
        
        tool_registry = self._create_tool_registry(
            mcp_manager=None,
            role_config=role_config,
            skill_loader=skill_loader
        )

        project_root = self.config.project.root if self.config.project else Path.cwd()
        session_storage = SessionStorage(
            storage_dir=str(project_root / ".rubato" / "sessions")
        )

        agent = RubatoAgent(
            config=self.config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry,
            role_config=role_config,
            roles_dir=self.roles_dir,
            session_storage=session_storage
        )

        inst_id = instance_id or str(uuid.uuid4())
        instance = AgentInstance(
            instance_id=inst_id,
            agent=agent,
            context_manager=context_manager,
            skill_loader=skill_loader,
            tool_registry=tool_registry,
            role_name=effective_role_name
        )

        with self._instances_lock:
            self._instances[inst_id] = instance

        self._logger.log_agent_action("instance_created", {
            "instance_id": inst_id,
            "role_name": effective_role_name,
            "requested_role": role_name,
            "total_instances": len(self._instances)
        })

        return instance

    def destroy_instance(self, instance_id: str) -> bool:
        with self._instances_lock:
            instance = self._instances.pop(instance_id, None)
            if instance:
                instance.dispose()
                self._logger.log_agent_action("instance_destroyed", {
                    "instance_id": instance_id,
                    "remaining_instances": len(self._instances)
                })
                return True
        return False

    def destroy_all_instances(self) -> int:
        count = 0
        with self._instances_lock:
            for instance_id in list(self._instances.keys()):
                if self.destroy_instance(instance_id):
                    count += 1
        return count


