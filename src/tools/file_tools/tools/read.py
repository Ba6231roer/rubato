import logging
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from src.tools.file_tools.audit import OperationType
from src.tools.file_tools.tools._helpers import check_permission


def create_file_read_tool(provider):
    logger = logging.getLogger(__name__)

    @tool
    def file_read(
        path: str,
        encoding: str = "utf-8",
        start_line: Optional[int] = None,
        end_line: Optional[int] = None
    ) -> str:
        """读取文件内容

        Args:
            path: 文件路径（相对于项目根目录或绝对路径）
            encoding: 文件编码，默认 utf-8
            start_line: 起始行号（可选，从1开始）
            end_line: 结束行号（可选）

        Returns:
            文件内容字符串，如果出错返回错误信息

        注意：
            - start_line 和 end_line 从 1 开始计数
            - 如果指定了行号范围，只返回该范围内的内容
        """
        tool_name = "file_read"

        resolved_path, error = check_permission(provider, tool_name, path, OperationType.READ)
        if error:
            return error

        try:
            if not resolved_path.exists():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.READ,
                    error="File does not exist"
                )
                return f"Error: File does not exist: {path}"

            if not resolved_path.is_file():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.READ,
                    error="Path is not a file"
                )
                return f"Error: Path is not a file: {path}"

            with open(resolved_path, 'r', encoding=encoding) as f:
                if start_line is not None or end_line is not None:
                    lines = f.readlines()

                    start_idx = (start_line - 1) if start_line and start_line > 0 else 0
                    end_idx = end_line if end_line and end_line <= len(lines) else len(lines)

                    if start_idx < 0:
                        start_idx = 0
                    if end_idx > len(lines):
                        end_idx = len(lines)

                    content = ''.join(lines[start_idx:end_idx])
                else:
                    content = f.read()

            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.READ,
                extra={
                    "encoding": encoding,
                    "start_line": start_line,
                    "end_line": end_line,
                    "file_size": len(content)
                }
            )

            return content

        except UnicodeDecodeError as e:
            error_msg = f"Error: Failed to decode file with encoding '{encoding}': {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.READ,
                error=error_msg
            )
            return error_msg
        except PermissionError as e:
            error_msg = f"Error: Permission denied when reading file: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.READ,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to read file: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.READ,
                error=error_msg
            )
            return error_msg

    return file_read
