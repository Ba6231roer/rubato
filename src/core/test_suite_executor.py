import asyncio
import json
import yaml
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import threading

from .agent_pool import AgentPool, ParallelExecutor
from ..config.models import AppConfig
from ..utils.logger import get_llm_logger


class TestCaseStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class TestCasePriority(Enum):
    HIGH = 3
    MEDIUM = 2
    LOW = 1

    @classmethod
    def from_string(cls, value: str) -> "TestCasePriority":
        mapping = {
            "high": cls.HIGH,
            "medium": cls.MEDIUM,
            "low": cls.LOW,
        }
        return mapping.get(value.lower(), cls.MEDIUM)


@dataclass
class TestCase:
    case_id: str
    name: str
    file_path: Path
    content: str
    priority: TestCasePriority = TestCasePriority.MEDIUM
    tags: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    expected_results: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: TestCaseStatus = TestCaseStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


@dataclass
class ExecutionResult:
    case_id: str
    status: TestCaseStatus
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


@dataclass
class TestReport:
    report_id: str
    execution_time: datetime
    total_cases: int = 0
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    total_duration_seconds: float = 0.0
    results: List[ExecutionResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return (self.passed_count / self.total_cases) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "execution_time": self.execution_time.isoformat(),
            "total_cases": self.total_cases,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "pass_rate": f"{self.pass_rate:.2f}%",
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "summary": self.summary,
            "results": [
                {
                    "case_id": r.case_id,
                    "status": r.status.value,
                    "result": r.result,
                    "error": r.error,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "duration_seconds": r.duration_seconds,
                }
                for r in self.results
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class TestCaseScanner:
    """测试案例目录扫描器"""

    SUPPORTED_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json"}

    def __init__(self, base_dir: str = "test_cases"):
        self.base_dir = Path(base_dir)
        self._logger = get_llm_logger()

    def scan_directory(
        self,
        directory: Optional[str] = None,
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> List[TestCase]:
        target_dir = Path(directory) if directory else self.base_dir

        if not target_dir.exists():
            self._logger.log_agent_action("scan_directory", {
                "error": f"目录不存在: {target_dir}"
            })
            return []

        valid_extensions = set(extensions) if extensions else self.SUPPORTED_EXTENSIONS

        test_cases: List[TestCase] = []
        pattern = "**/*" if recursive else "*"

        for file_path in target_dir.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
                case = self._parse_test_case(file_path)
                if case:
                    test_cases.append(case)

        test_cases.sort(key=lambda c: c.priority.value, reverse=True)

        self._logger.log_agent_action("scan_directory", {
            "directory": str(target_dir),
            "recursive": recursive,
            "found_cases": len(test_cases)
        })

        return test_cases

    def _parse_test_case(self, file_path: Path) -> Optional[TestCase]:
        try:
            content = file_path.read_text(encoding="utf-8")

            if file_path.suffix.lower() in {".yaml", ".yml"}:
                return self._parse_yaml_case(file_path, content)
            elif file_path.suffix.lower() == ".json":
                return self._parse_json_case(file_path, content)
            else:
                return self._parse_markdown_case(file_path, content)

        except Exception as e:
            self._logger.log_error("parse_test_case", e)
            return None

    def _parse_yaml_case(self, file_path: Path, content: str) -> TestCase:
        data = yaml.safe_load(content)

        priority = TestCasePriority.from_string(
            data.get("priority", "medium")
        )

        return TestCase(
            case_id=data.get("id", file_path.stem),
            name=data.get("name", file_path.stem),
            file_path=file_path,
            content=content,
            priority=priority,
            tags=data.get("tags", []),
            steps=data.get("steps", []),
            expected_results=data.get("expected", []),
            preconditions=data.get("preconditions", []),
            metadata=data.get("metadata", {}),
        )

    def _parse_json_case(self, file_path: Path, content: str) -> TestCase:
        data = json.loads(content)

        priority = TestCasePriority.from_string(
            data.get("priority", "medium")
        )

        return TestCase(
            case_id=data.get("id", file_path.stem),
            name=data.get("name", file_path.stem),
            file_path=file_path,
            content=content,
            priority=priority,
            tags=data.get("tags", []),
            steps=data.get("steps", []),
            expected_results=data.get("expected", []),
            preconditions=data.get("preconditions", []),
            metadata=data.get("metadata", {}),
        )

    def _parse_markdown_case(self, file_path: Path, content: str) -> TestCase:
        lines = content.split("\n")
        name = file_path.stem
        steps: List[str] = []
        expected_results: List[str] = []
        preconditions: List[str] = []
        tags: List[str] = []
        priority = TestCasePriority.MEDIUM
        current_section: Optional[str] = None

        for line in lines:
            line = line.strip()

            if line.startswith("# "):
                name = line[2:].strip()
            elif line.lower().startswith("## 前置条件") or line.lower().startswith("## preconditions"):
                current_section = "preconditions"
            elif line.lower().startswith("## 测试步骤") or line.lower().startswith("## steps"):
                current_section = "steps"
            elif line.lower().startswith("## 预期结果") or line.lower().startswith("## expected"):
                current_section = "expected"
            elif line.lower().startswith("## 标签") or line.lower().startswith("## tags"):
                current_section = "tags"
            elif line.lower().startswith("## 优先级") or line.lower().startswith("## priority"):
                current_section = "priority"
            elif line.startswith("- ") or line.startswith("* "):
                item = line[2:].strip()
                if current_section == "preconditions":
                    preconditions.append(item)
                elif current_section == "steps":
                    steps.append(item)
                elif current_section == "expected":
                    expected_results.append(item)
                elif current_section == "tags":
                    tags.append(item)
                elif current_section == "priority":
                    priority = TestCasePriority.from_string(item)
            elif line and line[0].isdigit() and ". " in line:
                item = line.split(". ", 1)[-1].strip()
                if current_section == "steps":
                    steps.append(item)
                elif current_section == "expected":
                    expected_results.append(item)

        return TestCase(
            case_id=file_path.stem,
            name=name,
            file_path=file_path,
            content=content,
            priority=priority,
            tags=tags,
            steps=steps,
            expected_results=expected_results,
            preconditions=preconditions,
        )


class TestSuiteExecutor:
    """测试案例集执行器"""

    def __init__(
        self,
        config: AppConfig,
        max_parallel: int = 3,
        role_name: str = "test-case-executor",
        roles_dir: str = "config/roles",
        skills_dir: str = "skills",
    ):
        self.config = config
        self.max_parallel = max_parallel
        self.role_name = role_name
        self.roles_dir = roles_dir
        self.skills_dir = skills_dir

        self._pool: Optional[AgentPool] = None
        self._executor: Optional[ParallelExecutor] = None
        self._scanner = TestCaseScanner()
        self._logger = get_llm_logger()

        self._test_cases: Dict[str, TestCase] = {}
        self._results: Dict[str, ExecutionResult] = {}
        self._progress_callbacks: List[Callable[[str, TestCaseStatus, Optional[str]], None]] = []
        self._lock = threading.Lock()

    def add_progress_callback(
        self,
        callback: Callable[[str, TestCaseStatus, Optional[str]], None]
    ) -> None:
        self._progress_callbacks.append(callback)

    def _notify_progress(
        self,
        case_id: str,
        status: TestCaseStatus,
        message: Optional[str] = None
    ) -> None:
        for callback in self._progress_callbacks:
            try:
                callback(case_id, status, message)
            except Exception as e:
                self._logger.log_error("progress_callback", e)

    async def initialize(self) -> None:
        self._pool = AgentPool(
            config=self.config,
            max_instances=self.max_parallel,
            default_role_name=self.role_name,
            roles_dir=self.roles_dir,
            skills_dir=self.skills_dir,
        )
        await self._pool.initialize()

        self._executor = ParallelExecutor(
            pool=self._pool,
            max_parallel=self.max_parallel,
        )
        await self._executor.start()

        self._logger.log_agent_action("test_suite_executor_initialized", {
            "max_parallel": self.max_parallel,
            "role_name": self.role_name,
        })

    async def shutdown(self) -> None:
        if self._executor:
            await self._executor.stop()

        if self._pool:
            self._pool.destroy_all_instances()

        self._logger.log_agent_action("test_suite_executor_shutdown", {})

    def load_test_cases(
        self,
        directory: str,
        recursive: bool = True,
        extensions: Optional[List[str]] = None,
    ) -> int:
        cases = self._scanner.scan_directory(
            directory=directory,
            recursive=recursive,
            extensions=extensions,
        )

        with self._lock:
            for case in cases:
                self._test_cases[case.case_id] = case

        self._logger.log_agent_action("test_cases_loaded", {
            "directory": directory,
            "count": len(cases),
        })

        return len(cases)

    def add_test_case(self, case: TestCase) -> None:
        with self._lock:
            self._test_cases[case.case_id] = case

    def get_test_case(self, case_id: str) -> Optional[TestCase]:
        return self._test_cases.get(case_id)

    def list_test_cases(self) -> List[Dict[str, Any]]:
        return [
            {
                "case_id": case.case_id,
                "name": case.name,
                "file_path": str(case.file_path),
                "priority": case.priority.name,
                "status": case.status.value,
                "tags": case.tags,
            }
            for case in self._test_cases.values()
        ]

    async def execute_all(
        self,
        timeout_per_case: Optional[float] = None,
        stop_on_failure: bool = False,
    ) -> TestReport:
        if not self._executor:
            await self.initialize()

        report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()

        sorted_cases = sorted(
            self._test_cases.values(),
            key=lambda c: c.priority.value,
            reverse=True,
        )

        task_mapping: Dict[str, str] = {}

        for case in sorted_cases:
            if case.status == TestCaseStatus.SKIPPED:
                continue

            case.status = TestCaseStatus.PENDING
            self._notify_progress(case.case_id, TestCaseStatus.PENDING, "等待执行")

            task_input = self._build_task_input(case)

            task_id = self._executor.submit_task(
                input_text=task_input,
                role_name=self.role_name,
                priority=case.priority.value,
                callback=lambda result, error, cid=case.case_id: self._handle_result(cid, result, error),
            )

            task_mapping[task_id] = case.case_id

        try:
            await self._executor.wait_for_all_tasks(timeout=timeout_per_case)
        except asyncio.TimeoutError:
            self._logger.log_agent_action("execute_all_timeout", {})

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        report = self._generate_report(report_id, start_time, duration)

        return report

    async def execute_single(self, case_id: str) -> ExecutionResult:
        if not self._executor:
            await self.initialize()

        case = self._test_cases.get(case_id)
        if not case:
            raise ValueError(f"测试案例不存在: {case_id}")

        case.status = TestCaseStatus.RUNNING
        case.started_at = datetime.now()
        self._notify_progress(case.case_id, TestCaseStatus.RUNNING, "开始执行")

        task_input = self._build_task_input(case)

        task_id = self._executor.submit_task(
            input_text=task_input,
            role_name=self.role_name,
            priority=case.priority.value,
        )

        try:
            result = await self._executor.wait_for_task(task_id)

            case.status = TestCaseStatus.PASSED
            case.result = result
            case.completed_at = datetime.now()
            case.duration_seconds = (case.completed_at - case.started_at).total_seconds()

            self._notify_progress(case.case_id, TestCaseStatus.PASSED, "执行成功")

        except Exception as e:
            case.status = TestCaseStatus.FAILED
            case.error = str(e)
            case.completed_at = datetime.now()
            case.duration_seconds = (case.completed_at - case.started_at).total_seconds()

            self._notify_progress(case.case_id, TestCaseStatus.FAILED, str(e))

        execution_result = ExecutionResult(
            case_id=case.case_id,
            status=case.status,
            result=case.result,
            error=case.error,
            started_at=case.started_at,
            completed_at=case.completed_at,
            duration_seconds=case.duration_seconds,
        )

        with self._lock:
            self._results[case.case_id] = execution_result

        return execution_result

    def _build_task_input(self, case: TestCase) -> str:
        parts = [f"执行测试案例: {case.name}"]

        if case.preconditions:
            parts.append("\n前置条件:")
            for pre in case.preconditions:
                parts.append(f"- {pre}")

        if case.steps:
            parts.append("\n测试步骤:")
            for i, step in enumerate(case.steps, 1):
                parts.append(f"{i}. {step}")

        if case.expected_results:
            parts.append("\n预期结果:")
            for exp in case.expected_results:
                parts.append(f"- {exp}")

        if case.content:
            parts.append(f"\n原始内容:\n{case.content}")

        return "\n".join(parts)

    def _handle_result(
        self,
        case_id: str,
        result: Optional[str],
        error: Optional[Exception]
    ) -> None:
        case = self._test_cases.get(case_id)
        if not case:
            return

        if error:
            case.status = TestCaseStatus.FAILED
            case.error = str(error)
            self._notify_progress(case_id, TestCaseStatus.FAILED, str(error))
        else:
            case.status = TestCaseStatus.PASSED
            case.result = result
            self._notify_progress(case_id, TestCaseStatus.PASSED, "执行成功")

        case.completed_at = datetime.now()
        if case.started_at:
            case.duration_seconds = (case.completed_at - case.started_at).total_seconds()

        execution_result = ExecutionResult(
            case_id=case.case_id,
            status=case.status,
            result=case.result,
            error=case.error,
            started_at=case.started_at,
            completed_at=case.completed_at,
            duration_seconds=case.duration_seconds,
        )

        with self._lock:
            self._results[case.case_id] = execution_result

    def _generate_report(
        self,
        report_id: str,
        execution_time: datetime,
        duration: float
    ) -> TestReport:
        results = list(self._results.values())

        passed = sum(1 for r in results if r.status == TestCaseStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestCaseStatus.FAILED)
        skipped = sum(1 for r in results if r.status == TestCaseStatus.SKIPPED)
        errors = sum(1 for r in results if r.status == TestCaseStatus.ERROR)

        failed_cases = [
            {"case_id": r.case_id, "error": r.error}
            for r in results
            if r.status == TestCaseStatus.FAILED
        ]

        summary = {
            "total_cases": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "pass_rate": f"{(passed / len(results) * 100) if results else 0:.2f}%",
            "failed_cases": failed_cases,
        }

        return TestReport(
            report_id=report_id,
            execution_time=execution_time,
            total_cases=len(results),
            passed_count=passed,
            failed_count=failed,
            skipped_count=skipped,
            error_count=errors,
            total_duration_seconds=duration,
            results=results,
            summary=summary,
        )

    def get_execution_status(self) -> Dict[str, Any]:
        if not self._executor:
            return {"status": "not_initialized"}

        pending = len(self._executor.get_all_pending_tasks())
        running = len(self._executor.get_all_running_tasks())
        completed = len(self._executor.get_all_completed_tasks())

        return {
            "status": "running" if running > 0 else "idle",
            "pending_tasks": pending,
            "running_tasks": running,
            "completed_tasks": completed,
            "total_cases": len(self._test_cases),
            "completed_cases": len(self._results),
        }

    def save_report(self, report: TestReport, file_path: str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(report.to_json())

        self._logger.log_agent_action("report_saved", {
            "file_path": str(path),
            "report_id": report.report_id,
        })

    def clear_results(self) -> None:
        with self._lock:
            self._results.clear()
            for case in self._test_cases.values():
                case.status = TestCaseStatus.PENDING
                case.result = None
                case.error = None
                case.started_at = None
                case.completed_at = None
                case.duration_seconds = None


async def execute_test_suite(
    config: AppConfig,
    test_directory: str,
    max_parallel: int = 3,
    role_name: str = "test-case-executor",
    output_file: Optional[str] = None,
) -> TestReport:
    executor = TestSuiteExecutor(
        config=config,
        max_parallel=max_parallel,
        role_name=role_name,
    )

    await executor.initialize()

    try:
        executor.load_test_cases(test_directory)
        report = await executor.execute_all()

        if output_file:
            executor.save_report(report, output_file)

        return report

    finally:
        await executor.shutdown()
