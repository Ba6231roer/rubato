import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
import threading

from ..config.models import AppConfig, RoleConfig, ProjectConfig, FileToolsConfig, UnifiedToolsConfig
from ..config.loader import ConfigLoader
from ..context.manager import ContextManager
from ..skills.loader import SkillLoader
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


@dataclass
class Task:
    task_id: str
    input_text: str
    role_name: Optional[str] = None
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[Exception] = None
    instance_id: Optional[str] = None
    callback: Optional[Callable[[str, Optional[Exception]], None]] = None

    def __lt__(self, other: "Task") -> bool:
        return self.priority > other.priority


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
        max_tokens = 4000
        if role_config and role_config.execution:
            max_tokens = min(4000, role_config.execution.max_context_tokens // 20)

        return ContextManager(
            max_tokens=max_tokens,
            keep_recent=4,
            auto_compress=True
        )

    def _create_skill_loader(self) -> SkillLoader:
        enabled_skills = None
        max_loaded_skills = 3
        
        if self.config.skills:
            enabled_skills = self.config.skills.enabled_skills
            if self.config.skills.skill_loading:
                max_loaded_skills = self.config.skills.skill_loading.max_loaded_skills
        
        return SkillLoader(
            skills_dir=self.skills_dir,
            enabled_skills=enabled_skills,
            max_loaded_skills=max_loaded_skills
        )

    def _create_tool_registry(
        self,
        mcp_manager=None,
        role_config: Optional[RoleConfig] = None
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
        
        self._log_tool_summary(tools_summary)
        
        return registry
    
    def _get_unified_tools_config(self, role_config: Optional[RoleConfig] = None) -> Optional[UnifiedToolsConfig]:
        if role_config and role_config.tools:
            return self._convert_role_tools_to_unified(role_config.tools)
        
        if self.config.tools:
            return self.config.tools
        
        return None
    
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
                    )
                )
        
        mcp_config = MCPToolsConfig()
        if role_tools.mcp:
            mcp_data = role_tools.mcp
            if isinstance(mcp_data, dict):
                mcp_config = MCPToolsConfig(
                    auto_connect=mcp_data.get('enabled', True)
                )
        
        skills_list = role_tools.skills if role_tools.skills else []
        
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
            role_config=role_config
        )

        agent = RubatoAgent(
            config=self.config,
            skill_loader=skill_loader,
            context_manager=context_manager,
            tool_registry=tool_registry,
            role_config=role_config
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

    def get_instance(self, instance_id: str) -> Optional[AgentInstance]:
        with self._instances_lock:
            return self._instances.get(instance_id)

    def get_instance_by_role(self, role_name: str) -> Optional[AgentInstance]:
        with self._instances_lock:
            for instance in self._instances.values():
                if instance.role_name == role_name and instance.is_available():
                    return instance
        return None

    async def acquire_instance(
        self,
        role_name: Optional[str] = None,
        create_if_needed: bool = True
    ) -> AgentInstance:
        if not self._initialized:
            await self.initialize()

        if role_name:
            instance = self.get_instance_by_role(role_name)
            if instance and instance.acquire():
                return instance

        with self._instances_lock:
            for inst in self._instances.values():
                if inst.is_available():
                    if inst.acquire():
                        return inst

        if create_if_needed:
            with self._instances_lock:
                if len(self._instances) < self.max_instances:
                    return await self.create_instance(role_name=role_name)

        raise RuntimeError("没有可用的Agent实例，且已达到最大实例数限制")

    def release_instance(self, instance_id: str) -> None:
        with self._instances_lock:
            instance = self._instances.get(instance_id)
            if instance:
                instance.release()
                self._logger.log_agent_action("instance_released", {
                    "instance_id": instance_id
                })

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

    def list_instances(self) -> List[Dict[str, Any]]:
        with self._instances_lock:
            return [
                {
                    "instance_id": inst.instance_id,
                    "role_name": inst.role_name,
                    "status": inst.status.value,
                    "created_at": inst.created_at.isoformat(),
                    "last_used_at": inst.last_used_at.isoformat() if inst.last_used_at else None,
                    "task_count": inst.task_count,
                    "error_message": inst.error_message
                }
                for inst in self._instances.values()
            ]

    def get_instance_count(self) -> int:
        with self._instances_lock:
            return len(self._instances)

    def get_available_count(self) -> int:
        with self._instances_lock:
            return sum(1 for inst in self._instances.values() if inst.is_available())

    async def execute_on_instance(
        self,
        instance_id: str,
        input_text: str
    ) -> str:
        instance = self.get_instance(instance_id)
        if not instance:
            raise ValueError(f"实例不存在: {instance_id}")

        if not instance.acquire():
            raise RuntimeError(f"实例不可用: {instance_id}")

        try:
            instance.task_count += 1
            result = await instance.agent.run(input_text)
            return result
        except Exception as e:
            instance.mark_error(str(e))
            raise
        finally:
            instance.release()


class ParallelExecutor:
    """并行任务执行器"""

    def __init__(
        self,
        pool: AgentPool,
        max_parallel: int = 3
    ):
        self.pool = pool
        self.max_parallel = max_parallel
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._pending_tasks: Dict[str, Task] = {}
        self._running_tasks: Dict[str, Task] = {}
        self._completed_tasks: Dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._logger = get_llm_logger()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        self._logger.log_agent_action("parallel_executor_started", {
            "max_parallel": self.max_parallel
        })

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._logger.log_agent_action("parallel_executor_stopped", {})

    def submit_task(
        self,
        input_text: str,
        role_name: Optional[str] = None,
        priority: int = 0,
        callback: Optional[Callable[[str, Optional[Exception]], None]] = None
    ) -> str:
        task = Task(
            task_id=str(uuid.uuid4()),
            input_text=input_text,
            role_name=role_name,
            priority=priority,
            callback=callback
        )

        self._task_queue.put_nowait(task)
        self._pending_tasks[task.task_id] = task

        self._logger.log_agent_action("task_submitted", {
            "task_id": task.task_id,
            "role_name": role_name,
            "priority": priority,
            "queue_size": self._task_queue.qsize()
        })

        return task.task_id

    def submit_tasks(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[str]:
        task_ids = []
        for task_info in tasks:
            task_id = self.submit_task(
                input_text=task_info["input_text"],
                role_name=task_info.get("role_name"),
                priority=task_info.get("priority", 0),
                callback=task_info.get("callback")
            )
            task_ids.append(task_id)
        return task_ids

    async def _worker_loop(self) -> None:
        semaphore = asyncio.Semaphore(self.max_parallel)
        active_tasks: List[asyncio.Task] = []

        while self._running:
            try:
                while len(active_tasks) >= self.max_parallel:
                    done, active_tasks = await asyncio.wait(
                        active_tasks,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in done:
                        try:
                            await t
                        except Exception:
                            pass

                try:
                    task = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=0.5
                    )
                except asyncio.TimeoutError:
                    continue

                async with semaphore:
                    async with self._lock:
                        if task.task_id in self._pending_tasks:
                            del self._pending_tasks[task.task_id]
                            self._running_tasks[task.task_id] = task

                    worker = asyncio.create_task(
                        self._execute_task(task)
                    )
                    active_tasks.append(worker)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.log_error("worker_loop", e)

    async def _execute_task(self, task: Task) -> None:
        instance: Optional[AgentInstance] = None
        try:
            task.started_at = datetime.now()

            instance = await self.pool.acquire_instance(
                role_name=task.role_name,
                create_if_needed=True
            )
            task.instance_id = instance.instance_id

            result = await instance.agent.run(task.input_text)
            task.result = result
            task.completed_at = datetime.now()

            async with self._lock:
                if task.task_id in self._running_tasks:
                    del self._running_tasks[task.task_id]
                self._completed_tasks[task.task_id] = task

            self._logger.log_agent_action("task_completed", {
                "task_id": task.task_id,
                "instance_id": instance.instance_id,
                "duration_seconds": (task.completed_at - task.started_at).total_seconds()
            })

            if task.callback:
                try:
                    task.callback(result, None)
                except Exception as e:
                    self._logger.log_error("task_callback", e)

        except Exception as e:
            task.error = e
            task.completed_at = datetime.now()

            async with self._lock:
                if task.task_id in self._running_tasks:
                    del self._running_tasks[task.task_id]
                self._completed_tasks[task.task_id] = task

            self._logger.log_error("task_execution", e)

            if task.callback:
                try:
                    task.callback("", e)
                except Exception as callback_error:
                    self._logger.log_error("task_callback", callback_error)

        finally:
            if instance:
                instance.release()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        if task_id in self._pending_tasks:
            task = self._pending_tasks[task_id]
            return {
                "task_id": task.task_id,
                "status": "pending",
                "created_at": task.created_at.isoformat()
            }

        if task_id in self._running_tasks:
            task = self._running_tasks[task_id]
            return {
                "task_id": task.task_id,
                "status": "running",
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "instance_id": task.instance_id
            }

        if task_id in self._completed_tasks:
            task = self._completed_tasks[task_id]
            return {
                "task_id": task.task_id,
                "status": "completed" if not task.error else "failed",
                "created_at": task.created_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "result": task.result,
                "error": str(task.error) if task.error else None,
                "instance_id": task.instance_id
            }

        return None

    def get_all_pending_tasks(self) -> List[Dict[str, Any]]:
        return [
            self.get_task_status(task_id)
            for task_id in self._pending_tasks
        ]

    def get_all_running_tasks(self) -> List[Dict[str, Any]]:
        return [
            self.get_task_status(task_id)
            for task_id in self._running_tasks
        ]

    def get_all_completed_tasks(self) -> List[Dict[str, Any]]:
        return [
            self.get_task_status(task_id)
            for task_id in self._completed_tasks
        ]

    def clear_completed_tasks(self) -> int:
        count = len(self._completed_tasks)
        self._completed_tasks.clear()
        return count

    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Optional[str]:
        start_time = asyncio.get_event_loop().time()

        while True:
            status = self.get_task_status(task_id)
            if not status:
                return None

            if status["status"] in ("completed", "failed"):
                if status.get("error"):
                    raise status["error"]
                return status.get("result")

            if timeout:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    raise asyncio.TimeoutError(f"任务 {task_id} 等待超时")

            await asyncio.sleep(0.1)

    async def wait_for_all_tasks(self, timeout: Optional[float] = None) -> Dict[str, str]:
        results: Dict[str, str] = {}
        start_time = asyncio.get_event_loop().time()

        all_task_ids = (
            list(self._pending_tasks.keys()) +
            list(self._running_tasks.keys())
        )

        for task_id in all_task_ids:
            try:
                remaining_timeout = None
                if timeout:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    remaining_timeout = max(0, timeout - elapsed)

                result = await self.wait_for_task(task_id, timeout=remaining_timeout)
                results[task_id] = result or ""
            except Exception as e:
                results[task_id] = f"Error: {str(e)}"

        return results


async def execute_parallel(
    pool: AgentPool,
    tasks: List[Dict[str, Any]],
    max_parallel: int = 3
) -> Dict[str, str]:
    executor = ParallelExecutor(pool, max_parallel=max_parallel)

    await executor.start()
    task_ids = executor.submit_tasks(tasks)

    try:
        results = await executor.wait_for_all_tasks()
        return results
    finally:
        await executor.stop()
