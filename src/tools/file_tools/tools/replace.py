import logging
from pathlib import Path

from langchain_core.tools import tool

from src.tools.file_tools.audit import OperationType
from src.tools.file_tools.tools._helpers import check_permission


def create_file_replace_tool(provider):
    logger = logging.getLogger(__name__)

    @tool
    def file_replace(
        path: str,
        old_str: str,
        new_str: str,
        encoding: str = "utf-8"
    ) -> str:
        """替换文件内容

        Args:
            path: 文件路径（相对于项目根目录或绝对路径）
            old_str: 要替换的旧字符串
            new_str: 替换后的新字符串
            encoding: 文件编码，默认 utf-8

        Returns:
            成功返回替换信息，失败返回错误信息

        注意：
            - 精确匹配替换，只替换第一个匹配项
            - 如果 old_str 不存在，返回错误信息
            - old_str 和 new_str 不能相同
        """
        tool_name = "file_replace"

        if old_str == new_str:
            return "Error: old_str and new_str are identical, no replacement needed"

        resolved_path, error = check_permission(provider, tool_name, path, OperationType.REPLACE)
        if error:
            return error

        try:
            if not resolved_path.exists():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.REPLACE,
                    error="File does not exist"
                )
                return f"Error: File does not exist: {path}"

            if not resolved_path.is_file():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.REPLACE,
                    error="Path is not a file"
                )
                return f"Error: Path is not a file: {path}"

            with open(resolved_path, 'r', encoding=encoding) as f:
                content = f.read()

            if old_str not in content:
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.REPLACE,
                    error="old_str not found in file"
                )
                return f"Error: old_str not found in file"

            new_content = content.replace(old_str, new_str, 1)

            with open(resolved_path, 'w', encoding=encoding) as f:
                f.write(new_content)

            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.REPLACE,
                extra={
                    "encoding": encoding,
                    "old_str_length": len(old_str),
                    "new_str_length": len(new_str)
                }
            )

            return f"Success: Replaced 1 occurrence in {path}"

        except UnicodeDecodeError as e:
            error_msg = f"Error: Failed to decode file with encoding '{encoding}': {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.REPLACE,
                error=error_msg
            )
            return error_msg
        except PermissionError as e:
            error_msg = f"Error: Permission denied when replacing file content: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.REPLACE,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to replace file content: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.REPLACE,
                error=error_msg
            )
            return error_msg

    return file_replace
