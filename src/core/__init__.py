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
]
