import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.config.models import FileToolsConfig, PermissionMode
from src.tools.file_tools.workspace import WorkspaceManager
from src.tools.file_tools.audit import OperationType


class PermissionStatus:
    """权限状态常量"""
    ALLOWED = "allowed"
    DENIED = "denied"
    ASK = "ask"


@dataclass
class PermissionResult:
    """权限检查结果数据类

    包含权限检查的完整结果信息，包括是否允许、拒绝原因等。
    """
    allowed: bool
    status: str
    path: Path
    operation: OperationType
    reason: Optional[str] = None
    requires_confirmation: bool = False
    resolved_path: Optional[Path] = None

    def __bool__(self) -> bool:
        return self.allowed

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "path": str(self.path),
            "operation": self.operation.value,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
            "resolved_path": str(self.resolved_path) if self.resolved_path else None
        }


class PermissionChecker:
    """权限检查器

    负责：
    1. 操作类型权限检查
    2. Workspace 边界检查（通过 WorkspaceManager）
    3. 排除列表检查（通过 WorkspaceManager）
    4. 自定义权限规则应用
    """

    DEFAULT_OPERATION_PERMISSIONS: Dict[str, PermissionMode] = {
        OperationType.READ.value: PermissionMode.allow,
        OperationType.LIST.value: PermissionMode.allow,
        OperationType.EXISTS.value: PermissionMode.allow,
        OperationType.SEARCH.value: PermissionMode.allow,
        OperationType.WRITE.value: PermissionMode.ask,
        OperationType.REPLACE.value: PermissionMode.ask,
        OperationType.DELETE.value: PermissionMode.deny,
        OperationType.COPY.value: PermissionMode.ask,
        OperationType.MOVE.value: PermissionMode.ask,
        OperationType.MKDIR.value: PermissionMode.ask,
    }

    DANGEROUS_OPERATIONS: List[OperationType] = [
        OperationType.DELETE,
        OperationType.MOVE,
    ]

    WRITE_OPERATIONS: List[OperationType] = [
        OperationType.WRITE,
        OperationType.REPLACE,
        OperationType.DELETE,
        OperationType.COPY,
        OperationType.MOVE,
        OperationType.MKDIR,
    ]

    def __init__(
        self,
        config: FileToolsConfig,
        workspace_manager: WorkspaceManager
    ):
        self._config = config
        self._workspace_manager = workspace_manager
        self._permissions = self._build_permissions()
        self._logger = logging.getLogger(__name__)

    def _build_permissions(self) -> Dict[str, PermissionMode]:
        permissions = dict(self.DEFAULT_OPERATION_PERMISSIONS)

        if self._config.custom_permissions:
            for op, mode in self._config.custom_permissions.items():
                permissions[op.lower()] = mode

        return permissions

    def _make_denied_result(
        self,
        path_obj: Path,
        operation: OperationType,
        reason: str,
        resolved_path: Optional[Path] = None
    ) -> PermissionResult:
        return PermissionResult(
            allowed=False,
            status=PermissionStatus.DENIED,
            path=path_obj,
            operation=operation,
            reason=reason,
            requires_confirmation=False,
            resolved_path=resolved_path
        )

    def _make_ask_result(
        self,
        path_obj: Path,
        operation: OperationType,
        reason: str,
        resolved_path: Path
    ) -> PermissionResult:
        return PermissionResult(
            allowed=True,
            status=PermissionStatus.ASK,
            path=path_obj,
            operation=operation,
            reason=reason,
            requires_confirmation=True,
            resolved_path=resolved_path
        )

    def _make_allowed_result(
        self,
        path_obj: Path,
        operation: OperationType,
        resolved_path: Path
    ) -> PermissionResult:
        return PermissionResult(
            allowed=True,
            status=PermissionStatus.ALLOWED,
            path=path_obj,
            operation=operation,
            requires_confirmation=False,
            resolved_path=resolved_path
        )

    def check(
        self,
        path: Union[str, Path],
        operation: OperationType
    ) -> PermissionResult:
        if isinstance(path, str) and (not path or not path.strip()):
            return self._make_denied_result(
                Path("."), operation, "Invalid path: path cannot be empty"
            )

        path_obj = Path(path) if isinstance(path, str) else path

        try:
            resolved_path = self._workspace_manager.resolve_path(path_obj)
        except ValueError as e:
            return self._make_denied_result(
                path_obj, operation, f"Invalid path: {str(e)}"
            )

        if not self._workspace_manager.is_within_workspace(resolved_path):
            return self._make_denied_result(
                path_obj, operation,
                "Path is outside workspace boundaries",
                resolved_path
            )

        if self._workspace_manager.is_excluded(resolved_path):
            return self._make_denied_result(
                path_obj, operation,
                "Path is excluded from workspace operations",
                resolved_path
            )

        operation_mode = self._get_operation_permission(operation)

        if operation_mode == PermissionMode.deny:
            return self._make_denied_result(
                path_obj, operation,
                f"Operation '{operation.value}' is denied by permission policy",
                resolved_path
            )

        if operation_mode == PermissionMode.ask:
            return self._make_ask_result(
                path_obj, operation,
                "Operation requires user confirmation",
                resolved_path
            )

        if operation in self.DANGEROUS_OPERATIONS:
            return self._make_ask_result(
                path_obj, operation,
                "Dangerous operation requires confirmation",
                resolved_path
            )

        return self._make_allowed_result(path_obj, operation, resolved_path)

    def _get_operation_permission(self, operation: OperationType) -> PermissionMode:
        op_key = operation.value.lower()

        if op_key in self._permissions:
            return self._permissions[op_key]

        return self._config.default_permissions

    def is_operation_allowed(self, operation: OperationType) -> bool:
        mode = self._get_operation_permission(operation)
        return mode != PermissionMode.deny

    def is_write_operation(self, operation: OperationType) -> bool:
        return operation in self.WRITE_OPERATIONS

    def is_dangerous_operation(self, operation: OperationType) -> bool:
        return operation in self.DANGEROUS_OPERATIONS

    def get_permission_mode(self, operation: OperationType) -> PermissionMode:
        return self._get_operation_permission(operation)

    def set_permission_mode(
        self,
        operation: OperationType,
        mode: PermissionMode
    ) -> None:
        self._permissions[operation.value.lower()] = mode
        self._logger.info(f"Permission for '{operation.value}' set to '{mode.value}'")

    def get_all_permissions(self) -> Dict[str, PermissionMode]:
        return dict(self._permissions)

    def check_path_access(
        self,
        path: Union[str, Path]
    ) -> PermissionResult:
        return self.check(path, OperationType.READ)

    def validate_for_operation(
        self,
        path: Union[str, Path],
        operation: OperationType
    ) -> Path:
        result = self.check(path, operation)

        if not result.allowed:
            if "outside workspace" in (result.reason or ""):
                raise ValueError(result.reason)
            else:
                raise PermissionError(result.reason)

        return result.resolved_path

    @property
    def workspace_manager(self) -> WorkspaceManager:
        return self._workspace_manager

    @property
    def config(self) -> FileToolsConfig:
        return self._config
