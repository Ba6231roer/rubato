import logging
import shutil
from pathlib import Path

from langchain_core.tools import tool

from src.tools.file_tools.audit import OperationType


def create_file_exists_tool(provider):
    """创建 file_exists 工具
    
    Args:
        provider: FileToolProvider 实例，提供权限检查和审计日志功能
        
    Returns:
        StructuredTool: file_exists 工具实例
    """
    logger = logging.getLogger(__name__)
    
    @tool
    def file_exists(path: str) -> str:
        """检查文件或目录是否存在
        
        Args:
            path: 文件或目录路径（相对于项目根目录或绝对路径）
        
        Returns:
            "true" 如果存在，"false" 如果不存在，失败返回错误信息
        """
        tool_name = "file_exists"
        
        permission_result = provider.check_permission(path, OperationType.EXISTS)
        
        if not permission_result.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=path,
                operation=OperationType.EXISTS,
                reason=permission_result.reason or "Permission denied"
            )
            return f"Error: Permission denied - {permission_result.reason}"
        
        try:
            resolved_path = permission_result.resolved_path
            exists = resolved_path.exists()
            
            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.EXISTS,
                extra={"exists": exists}
            )
            
            return "true" if exists else "false"
            
        except Exception as e:
            error_msg = f"Error: Failed to check existence: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.EXISTS,
                error=error_msg
            )
            return error_msg
    
    return file_exists


def create_file_delete_tool(provider):
    """创建 file_delete 工具
    
    Args:
        provider: FileToolProvider 实例，提供权限检查和审计日志功能
        
    Returns:
        StructuredTool: file_delete 工具实例
    """
    logger = logging.getLogger(__name__)
    
    @tool
    def file_delete(path: str) -> str:
        """删除文件或目录
        
        Args:
            path: 文件或目录路径（相对于项目根目录或绝对路径）
        
        Returns:
            成功返回 "Success: Deleted successfully"，失败返回错误信息
            
        注意：
            - 删除目录时会递归删除所有内容
            - 此操作不可逆，请谨慎使用
        """
        tool_name = "file_delete"
        
        permission_result = provider.check_permission(path, OperationType.DELETE)
        
        if not permission_result.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=path,
                operation=OperationType.DELETE,
                reason=permission_result.reason or "Permission denied"
            )
            return f"Error: Permission denied - {permission_result.reason}"
        
        try:
            resolved_path = permission_result.resolved_path
            
            if not resolved_path.exists():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.DELETE,
                    error="Path does not exist"
                )
                return f"Error: Path does not exist: {path}"
            
            if resolved_path.is_file():
                resolved_path.unlink()
            elif resolved_path.is_dir():
                shutil.rmtree(resolved_path)
            
            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.DELETE
            )
            
            return "Success: Deleted successfully"
            
        except PermissionError as e:
            error_msg = f"Error: Permission denied when deleting: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.DELETE,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to delete: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.DELETE,
                error=error_msg
            )
            return error_msg
    
    return file_delete


def create_file_copy_tool(provider):
    """创建 file_copy 工具
    
    Args:
        provider: FileToolProvider 实例，提供权限检查和审计日志功能
        
    Returns:
        StructuredTool: file_copy 工具实例
    """
    logger = logging.getLogger(__name__)
    
    @tool
    def file_copy(src: str, dst: str) -> str:
        """复制文件或目录
        
        Args:
            src: 源文件或目录路径
            dst: 目标路径
        
        Returns:
            成功返回 "Success: Copied successfully"，失败返回错误信息
            
        注意：
            - 复制目录时会递归复制所有内容
            - 如果目标路径已存在，会被覆盖
        """
        tool_name = "file_copy"
        
        src_permission = provider.check_permission(src, OperationType.READ)
        if not src_permission.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=src,
                operation=OperationType.COPY,
                reason=src_permission.reason or "Permission denied"
            )
            return f"Error: Permission denied for source - {src_permission.reason}"
        
        dst_permission = provider.check_permission(dst, OperationType.WRITE)
        if not dst_permission.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=dst,
                operation=OperationType.COPY,
                reason=dst_permission.reason or "Permission denied"
            )
            return f"Error: Permission denied for destination - {dst_permission.reason}"
        
        try:
            src_path = src_permission.resolved_path
            dst_path = dst_permission.resolved_path
            
            if not src_path.exists():
                provider.log_error(
                    tool_name=tool_name,
                    path=src,
                    operation=OperationType.COPY,
                    error="Source path does not exist"
                )
                return f"Error: Source path does not exist: {src}"
            
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
            elif src_path.is_dir():
                if dst_path.exists():
                    shutil.rmtree(dst_path)
                shutil.copytree(src_path, dst_path)
            
            provider.log_success(
                tool_name=tool_name,
                path=f"{src} -> {dst}",
                operation=OperationType.COPY
            )
            
            return "Success: Copied successfully"
            
        except PermissionError as e:
            error_msg = f"Error: Permission denied when copying: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=f"{src} -> {dst}",
                operation=OperationType.COPY,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to copy: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=f"{src} -> {dst}",
                operation=OperationType.COPY,
                error=error_msg
            )
            return error_msg
    
    return file_copy


def create_file_move_tool(provider):
    """创建 file_move 工具
    
    Args:
        provider: FileToolProvider 实例，提供权限检查和审计日志功能
        
    Returns:
        StructuredTool: file_move 工具实例
    """
    logger = logging.getLogger(__name__)
    
    @tool
    def file_move(src: str, dst: str) -> str:
        """移动或重命名文件或目录
        
        Args:
            src: 源文件或目录路径
            dst: 目标路径
        
        Returns:
            成功返回 "Success: Moved successfully"，失败返回错误信息
            
        注意：
            - 如果目标路径已存在，会被覆盖
            - 可以用于重命名文件或目录
        """
        tool_name = "file_move"
        
        src_permission = provider.check_permission(src, OperationType.READ)
        if not src_permission.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=src,
                operation=OperationType.MOVE,
                reason=src_permission.reason or "Permission denied"
            )
            return f"Error: Permission denied for source - {src_permission.reason}"
        
        dst_permission = provider.check_permission(dst, OperationType.WRITE)
        if not dst_permission.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=dst,
                operation=OperationType.MOVE,
                reason=dst_permission.reason or "Permission denied"
            )
            return f"Error: Permission denied for destination - {dst_permission.reason}"
        
        try:
            src_path = src_permission.resolved_path
            dst_path = dst_permission.resolved_path
            
            if not src_path.exists():
                provider.log_error(
                    tool_name=tool_name,
                    path=src,
                    operation=OperationType.MOVE,
                    error="Source path does not exist"
                )
                return f"Error: Source path does not exist: {src}"
            
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            if dst_path.exists():
                if dst_path.is_dir():
                    shutil.rmtree(dst_path)
                else:
                    dst_path.unlink()
            
            shutil.move(str(src_path), str(dst_path))
            
            provider.log_success(
                tool_name=tool_name,
                path=f"{src} -> {dst}",
                operation=OperationType.MOVE
            )
            
            return "Success: Moved successfully"
            
        except PermissionError as e:
            error_msg = f"Error: Permission denied when moving: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=f"{src} -> {dst}",
                operation=OperationType.MOVE,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to move: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=f"{src} -> {dst}",
                operation=OperationType.MOVE,
                error=error_msg
            )
            return error_msg
    
    return file_move


def create_file_mkdir_tool(provider):
    """创建 file_mkdir 工具
    
    Args:
        provider: FileToolProvider 实例，提供权限检查和审计日志功能
        
    Returns:
        StructuredTool: file_mkdir 工具实例
    """
    logger = logging.getLogger(__name__)
    
    @tool
    def file_mkdir(path: str) -> str:
        """创建目录
        
        Args:
            path: 目录路径（相对于项目根目录或绝对路径）
        
        Returns:
            成功返回 "Success: Directory created"，失败返回错误信息
            
        注意：
            - 会递归创建所有父目录
            - 如果目录已存在，不会报错
        """
        tool_name = "file_mkdir"
        
        permission_result = provider.check_permission(path, OperationType.MKDIR)
        
        if not permission_result.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=path,
                operation=OperationType.MKDIR,
                reason=permission_result.reason or "Permission denied"
            )
            return f"Error: Permission denied - {permission_result.reason}"
        
        try:
            resolved_path = permission_result.resolved_path
            
            resolved_path.mkdir(parents=True, exist_ok=True)
            
            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.MKDIR
            )
            
            return "Success: Directory created"
            
        except PermissionError as e:
            error_msg = f"Error: Permission denied when creating directory: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.MKDIR,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to create directory: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.MKDIR,
                error=error_msg
            )
            return error_msg
    
    return file_mkdir
