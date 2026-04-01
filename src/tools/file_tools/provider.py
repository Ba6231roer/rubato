import logging
from pathlib import Path
from typing import List, Union, Optional, Dict, Any

from langchain_core.tools import BaseTool

from src.tools.provider import ToolProvider
from src.tools.file_tools.workspace import WorkspaceManager
from src.tools.file_tools.permission import PermissionChecker, PermissionResult
from src.tools.file_tools.audit import AuditLogger, AuditConfig, OperationType, OperationResult
from src.config.models import ProjectConfig, FileToolsConfig


class FileToolProvider(ToolProvider):
    """文件工具提供者
    
    负责：
    1. 提供文件操作工具
    2. 管理权限检查
    3. 记录审计日志
    4. 确保 workspace 边界安全
    """
    
    def __init__(
        self,
        project_config: ProjectConfig,
        file_tools_config: FileToolsConfig
    ):
        """初始化文件工具提供者
        
        Args:
            project_config: 项目配置
            file_tools_config: 文件工具配置
        """
        self._project_config = project_config
        self._file_tools_config = file_tools_config
        
        self._workspace_manager = WorkspaceManager(project_config)
        self._permission_checker = PermissionChecker(
            file_tools_config,
            self._workspace_manager
        )
        
        audit_config = AuditConfig(
            enabled=file_tools_config.audit,
            log_file="logs/file_tools_audit.log"
        )
        self._audit_logger = AuditLogger(audit_config)
        
        self._tools: List[BaseTool] = []
        self._logger = logging.getLogger(__name__)
        
        self._initialize_tools()
    
    def _initialize_tools(self) -> None:
        """初始化文件操作工具"""
        self._tools = []
        
        if not self._file_tools_config.enabled:
            self._logger.info("File tools are disabled")
            return
        
        from src.tools.file_tools.tools import (
            create_file_read_tool,
            create_file_write_tool,
            create_file_replace_tool,
            create_file_list_tool,
            create_file_search_tool,
            create_file_exists_tool,
            create_file_delete_tool,
            create_file_copy_tool,
            create_file_move_tool,
            create_file_mkdir_tool
        )
        
        self._tools = [
            create_file_read_tool(self),
            create_file_write_tool(self),
            create_file_replace_tool(self),
            create_file_list_tool(self),
            create_file_search_tool(self),
            create_file_exists_tool(self),
            create_file_delete_tool(self),
            create_file_copy_tool(self),
            create_file_move_tool(self),
            create_file_mkdir_tool(self)
        ]
        
        self._logger.info(f"File tools initialized: {len(self._tools)} tools loaded")
    
    def get_tools(self) -> List[BaseTool]:
        """获取文件操作工具列表
        
        Returns:
            List[BaseTool]: 文件操作工具列表
        """
        if not self.is_available():
            return []
        
        return self._tools
    
    def is_available(self) -> bool:
        """检查文件工具是否可用
        
        检查条件：
        1. 配置是否启用 file_tools
        2. Workspace 配置是否有效
        
        Returns:
            bool: 文件工具是否可用
        """
        if not self._file_tools_config.enabled:
            return False
        
        try:
            workspace_roots = self._workspace_manager.get_workspace_roots()
            if not workspace_roots:
                return False
            
            for root in workspace_roots:
                if not root.exists():
                    self._logger.warning(f"Workspace root does not exist: {root}")
                    return False
            
            return True
        except Exception as e:
            self._logger.error(f"Error checking file tools availability: {e}")
            return False
    
    def check_permission(
        self,
        path: Union[str, Path],
        operation: OperationType
    ) -> PermissionResult:
        """检查路径操作的权限
        
        Args:
            path: 待检查的路径
            operation: 操作类型
            
        Returns:
            PermissionResult: 权限检查结果
        """
        return self._permission_checker.check(path, operation)
    
    def log_audit(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        result: OperationResult,
        error_message: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录审计日志
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            result: 操作结果
            error_message: 错误信息（可选）
            user_info: 用户信息（可选）
            extra: 额外信息（可选）
        """
        self._audit_logger.log(
            tool_name=tool_name,
            path=path,
            operation=operation,
            result=result,
            error_message=error_message,
            user_info=user_info,
            extra=extra
        )
    
    def log_success(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        user_info: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录成功操作
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            user_info: 用户信息（可选）
            extra: 额外信息（可选）
        """
        self._audit_logger.log_success(
            tool_name=tool_name,
            path=path,
            operation=operation,
            user_info=user_info,
            extra=extra
        )
    
    def log_denied(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        reason: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录拒绝操作
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            reason: 拒绝原因
            user_info: 用户信息（可选）
        """
        self._audit_logger.log_denied(
            tool_name=tool_name,
            path=path,
            operation=operation,
            reason=reason,
            user_info=user_info
        )
    
    def log_error(
        self,
        tool_name: str,
        path: str,
        operation: OperationType,
        error: str,
        user_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录错误操作
        
        Args:
            tool_name: 工具名称
            path: 目标路径
            operation: 操作类型
            error: 错误信息
            user_info: 用户信息（可选）
        """
        self._audit_logger.log_error(
            tool_name=tool_name,
            path=path,
            operation=operation,
            error=error,
            user_info=user_info
        )
    
    def resolve_path(self, path: Union[str, Path]) -> Path:
        """解析路径
        
        Args:
            path: 待解析的路径
            
        Returns:
            Path: 解析后的绝对路径
        """
        return self._workspace_manager.resolve_path(path)
    
    def validate_path(self, path: Union[str, Path]) -> Path:
        """验证路径并返回解析后的路径
        
        Args:
            path: 待验证的路径
            
        Returns:
            Path: 解析后的路径
            
        Raises:
            ValueError: 如果路径不在 workspace 内
            PermissionError: 如果路径被排除
        """
        return self._workspace_manager.validate_path(path)
    
    def is_within_workspace(self, path: Union[str, Path]) -> bool:
        """检查路径是否在 Workspace 边界内
        
        Args:
            path: 待检查的路径
            
        Returns:
            bool: 如果路径在任一 workspace 内返回 True
        """
        return self._workspace_manager.is_within_workspace(path)
    
    def is_excluded(self, path: Union[str, Path]) -> bool:
        """检查路径是否在排除列表中
        
        Args:
            path: 待检查的路径
            
        Returns:
            bool: 如果路径匹配任一排除模式返回 True
        """
        return self._workspace_manager.is_excluded(path)
    
    @property
    def workspace_manager(self) -> WorkspaceManager:
        """获取 WorkspaceManager 实例"""
        return self._workspace_manager
    
    @property
    def permission_checker(self) -> PermissionChecker:
        """获取 PermissionChecker 实例"""
        return self._permission_checker
    
    @property
    def audit_logger(self) -> AuditLogger:
        """获取 AuditLogger 实例"""
        return self._audit_logger
    
    @property
    def config(self) -> FileToolsConfig:
        """获取文件工具配置"""
        return self._file_tools_config
    
    def close(self) -> None:
        """关闭资源"""
        self._audit_logger.close()
