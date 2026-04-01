import fnmatch
import logging
from pathlib import Path
from typing import Optional, List

from langchain_core.tools import tool

from src.tools.file_tools.audit import OperationType


def create_file_list_tool(provider):
    """创建 file_list 工具
    
    Args:
        provider: FileToolProvider 实例，提供权限检查和审计日志功能
        
    Returns:
        StructuredTool: file_list 工具实例
    """
    logger = logging.getLogger(__name__)
    
    @tool
    def file_list(
        path: str = ".",
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> str:
        """列出目录内容
        
        Args:
            path: 目录路径（相对于项目根目录或绝对路径），默认为当前目录
            pattern: 文件名匹配模式（支持通配符，如 *.py），可选
            recursive: 是否递归列出子目录，默认 False
        
        Returns:
            目录内容列表，每行一个条目，失败返回错误信息
            
        注意：
            - 目录以 / 结尾标识
            - 支持 Unix shell 风格的通配符：*、?、[seq]
            - recursive=True 时会递归列出所有子目录内容
        """
        tool_name = "file_list"
        
        permission_result = provider.check_permission(path, OperationType.LIST)
        
        if not permission_result.allowed:
            provider.log_denied(
                tool_name=tool_name,
                path=path,
                operation=OperationType.LIST,
                reason=permission_result.reason or "Permission denied"
            )
            return f"Error: Permission denied - {permission_result.reason}"
        
        try:
            resolved_path = permission_result.resolved_path
            
            if not resolved_path.exists():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.LIST,
                    error="Directory does not exist"
                )
                return f"Error: Directory does not exist: {path}"
            
            if not resolved_path.is_dir():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.LIST,
                    error="Path is not a directory"
                )
                return f"Error: Path is not a directory: {path}"
            
            entries: List[str] = []
            
            if recursive:
                for item in resolved_path.rglob('*'):
                    if provider.is_excluded(item):
                        continue
                    
                    relative_path = item.relative_to(resolved_path)
                    
                    if pattern and not fnmatch.fnmatch(item.name, pattern):
                        continue
                    
                    if item.is_dir():
                        entries.append(f"{relative_path}/")
                    else:
                        entries.append(str(relative_path))
            else:
                for item in resolved_path.iterdir():
                    if provider.is_excluded(item):
                        continue
                    
                    if pattern and not fnmatch.fnmatch(item.name, pattern):
                        continue
                    
                    if item.is_dir():
                        entries.append(f"{item.name}/")
                    else:
                        entries.append(item.name)
            
            entries.sort()
            result = '\n'.join(entries) if entries else "(empty directory)"
            
            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.LIST,
                extra={
                    "pattern": pattern,
                    "recursive": recursive,
                    "entry_count": len(entries)
                }
            )
            
            return result
            
        except PermissionError as e:
            error_msg = f"Error: Permission denied when listing directory: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.LIST,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to list directory: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.LIST,
                error=error_msg
            )
            return error_msg
    
    return file_list
