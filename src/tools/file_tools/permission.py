import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel

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
        """支持布尔判断"""
        return self.allowed
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
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
        """初始化权限检查器
        
        Args:
            config: 文件工具配置
            workspace_manager: Workspace 管理器实例
        """
        self._config = config
        self._workspace_manager = workspace_manager
        self._permissions = self._build_permissions()
        self._logger = logging.getLogger(__name__)
    
    def _build_permissions(self) -> Dict[str, PermissionMode]:
        """构建权限映射表
        
        合并默认权限和自定义权限配置。
        
        Returns:
            Dict[str, PermissionMode]: 操作类型到权限模式的映射
        """
        permissions = dict(self.DEFAULT_OPERATION_PERMISSIONS)
        
        if self._config.custom_permissions:
            for op, mode in self._config.custom_permissions.items():
                permissions[op.lower()] = mode
        
        return permissions
    
    def check(
        self,
        path: Union[str, Path],
        operation: OperationType
    ) -> PermissionResult:
        """检查路径操作的权限
        
        执行完整的权限检查流程：
        1. 检查路径是否在 Workspace 内
        2. 检查路径是否被排除
        3. 检查操作类型权限
        
        Args:
            path: 待检查的路径
            operation: 操作类型
            
        Returns:
            PermissionResult: 权限检查结果
        """
        if isinstance(path, str) and (not path or not path.strip()):
            return PermissionResult(
                allowed=False,
                status=PermissionStatus.DENIED,
                path=Path("."),
                operation=operation,
                reason="Invalid path: path cannot be empty",
                requires_confirmation=False
            )
        
        path_obj = Path(path) if isinstance(path, str) else path
        
        try:
            resolved_path = self._workspace_manager.resolve_path(path_obj)
        except ValueError as e:
            return PermissionResult(
                allowed=False,
                status=PermissionStatus.DENIED,
                path=path_obj,
                operation=operation,
                reason=f"Invalid path: {str(e)}",
                requires_confirmation=False
            )
        
        if not self._workspace_manager.is_within_workspace(resolved_path):
            return PermissionResult(
                allowed=False,
                status=PermissionStatus.DENIED,
                path=path_obj,
                operation=operation,
                reason="Path is outside workspace boundaries",
                requires_confirmation=False,
                resolved_path=resolved_path
            )
        
        if self._workspace_manager.is_excluded(resolved_path):
            return PermissionResult(
                allowed=False,
                status=PermissionStatus.DENIED,
                path=path_obj,
                operation=operation,
                reason="Path is excluded from workspace operations",
                requires_confirmation=False,
                resolved_path=resolved_path
            )
        
        operation_mode = self._get_operation_permission(operation)
        
        if operation_mode == PermissionMode.deny:
            return PermissionResult(
                allowed=False,
                status=PermissionStatus.DENIED,
                path=path_obj,
                operation=operation,
                reason=f"Operation '{operation.value}' is denied by permission policy",
                requires_confirmation=False,
                resolved_path=resolved_path
            )
        
        if operation_mode == PermissionMode.ask:
            return PermissionResult(
                allowed=True,
                status=PermissionStatus.ASK,
                path=path_obj,
                operation=operation,
                reason="Operation requires user confirmation",
                requires_confirmation=True,
                resolved_path=resolved_path
            )
        
        if operation in self.DANGEROUS_OPERATIONS:
            return PermissionResult(
                allowed=True,
                status=PermissionStatus.ASK,
                path=path_obj,
                operation=operation,
                reason="Dangerous operation requires confirmation",
                requires_confirmation=True,
                resolved_path=resolved_path
            )
        
        return PermissionResult(
            allowed=True,
            status=PermissionStatus.ALLOWED,
            path=path_obj,
            operation=operation,
            requires_confirmation=False,
            resolved_path=resolved_path
        )
    
    def _get_operation_permission(self, operation: OperationType) -> PermissionMode:
        """获取操作类型的权限模式
        
        Args:
            operation: 操作类型
            
        Returns:
            PermissionMode: 权限模式
        """
        op_key = operation.value.lower()
        
        if op_key in self._permissions:
            return self._permissions[op_key]
        
        return self._config.default_permissions
    
    def is_operation_allowed(self, operation: OperationType) -> bool:
        """检查操作类型是否被允许（不考虑路径）
        
        Args:
            operation: 操作类型
            
        Returns:
            bool: 如果操作未被完全禁止返回 True
        """
        mode = self._get_operation_permission(operation)
        return mode != PermissionMode.deny
    
    def is_write_operation(self, operation: OperationType) -> bool:
        """检查是否为写操作
        
        Args:
            operation: 操作类型
            
        Returns:
            bool: 如果是写操作返回 True
        """
        return operation in self.WRITE_OPERATIONS
    
    def is_dangerous_operation(self, operation: OperationType) -> bool:
        """检查是否为危险操作
        
        Args:
            operation: 操作类型
            
        Returns:
            bool: 如果是危险操作返回 True
        """
        return operation in self.DANGEROUS_OPERATIONS
    
    def get_permission_mode(self, operation: OperationType) -> PermissionMode:
        """获取操作类型的权限模式
        
        Args:
            operation: 操作类型
            
        Returns:
            PermissionMode: 权限模式
        """
        return self._get_operation_permission(operation)
    
    def set_permission_mode(
        self,
        operation: OperationType,
        mode: PermissionMode
    ) -> None:
        """动态设置操作权限模式
        
        Args:
            operation: 操作类型
            mode: 权限模式
        """
        self._permissions[operation.value.lower()] = mode
        self._logger.info(f"Permission for '{operation.value}' set to '{mode.value}'")
    
    def get_all_permissions(self) -> Dict[str, PermissionMode]:
        """获取所有操作权限配置
        
        Returns:
            Dict[str, PermissionMode]: 操作类型到权限模式的映射
        """
        return dict(self._permissions)
    
    def check_path_access(
        self,
        path: Union[str, Path]
    ) -> PermissionResult:
        """检查路径访问权限（不涉及具体操作）
        
        Args:
            path: 待检查的路径
            
        Returns:
            PermissionResult: 权限检查结果
        """
        return self.check(path, OperationType.READ)
    
    def validate_for_operation(
        self,
        path: Union[str, Path],
        operation: OperationType
    ) -> Path:
        """验证路径并返回解析后的路径
        
        Args:
            path: 待验证的路径
            operation: 操作类型
            
        Returns:
            Path: 解析后的路径
            
        Raises:
            ValueError: 如果路径不在 workspace 内
            PermissionError: 如果路径被排除或操作被拒绝
        """
        result = self.check(path, operation)
        
        if not result.allowed:
            if "outside workspace" in (result.reason or ""):
                raise ValueError(result.reason)
            else:
                raise PermissionError(result.reason)
        
        return result.resolved_path
    
    @property
    def workspace_manager(self) -> WorkspaceManager:
        """获取关联的 WorkspaceManager 实例"""
        return self._workspace_manager
    
    @property
    def config(self) -> FileToolsConfig:
        """获取配置"""
        return self._config
