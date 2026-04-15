"""Core module - Agent engine, sub-agents, role manager and agent pool"""

from .role_manager import RoleManager
from .agent_pool import (
    AgentPool,
    AgentInstance,
    ParallelExecutor,
    InstanceStatus,
    Task,
    execute_parallel
)
from .test_suite_executor import (
    TestCaseScanner,
    TestSuiteExecutor,
    TestCase,
    TestCaseStatus,
    TestCasePriority,
    ExecutionResult,
    TestReport,
    execute_test_suite,
)
from .query_engine import (
    QueryEngine,
    QueryEngineConfig,
    FileStateCache,
    PermissionDenial,
    AbortController,
    Usage,
    SDKMessage,
    SubmitOptions,
)
from .sub_agent_types import (
    ToolInheritanceMode,
    SubAgentState,
    ToolPermissionConfig,
    SubAgentExecutionConfig,
    SubAgentModelConfig,
    SubAgentDefinition,
    SubAgentInstance,
    SubAgentSpawnOptions,
)
from .sub_agent_lifecycle import SubAgentLifecycleManager
from .sub_agents import (
    SubAgentManager,
    ToolPermissionResolver,
    ConfigInheritanceResolver,
    create_spawn_agent_tool,
)

__all__ = [
    "RoleManager",
    "AgentPool",
    "AgentInstance",
    "ParallelExecutor",
    "InstanceStatus",
    "Task",
    "execute_parallel",
    "TestCaseScanner",
    "TestSuiteExecutor",
    "TestCase",
    "TestCaseStatus",
    "TestCasePriority",
    "ExecutionResult",
    "TestReport",
    "execute_test_suite",
    "QueryEngine",
    "QueryEngineConfig",
    "FileStateCache",
    "PermissionDenial",
    "AbortController",
    "Usage",
    "SDKMessage",
    "SubmitOptions",
    "ToolInheritanceMode",
    "SubAgentState",
    "ToolPermissionConfig",
    "SubAgentExecutionConfig",
    "SubAgentModelConfig",
    "SubAgentDefinition",
    "SubAgentInstance",
    "SubAgentSpawnOptions",
    "SubAgentLifecycleManager",
    "SubAgentManager",
    "ToolPermissionResolver",
    "ConfigInheritanceResolver",
    "create_spawn_agent_tool",
]
