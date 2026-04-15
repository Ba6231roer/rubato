import logging
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from src.tools.file_tools.audit import OperationType
from src.tools.file_tools.tools._helpers import check_permission


def create_file_write_tool(provider):
    logger = logging.getLogger(__name__)

    @tool
    def file_write(
        path: str,
        content: str,
        mode: Literal["overwrite", "append"] = "overwrite",
        encoding: str = "utf-8"
    ) -> str:
        """写入文件内容

        Args:
            path: 文件路径（相对于项目根目录或绝对路径）
            content: 要写入的内容
            mode: 写入模式，可选 "overwrite"（覆盖）或 "append"（追加），默认 "overwrite"
            encoding: 文件编码，默认 utf-8

        Returns:
            成功返回 "Success: File written successfully"，失败返回错误信息

        注意：
            - overwrite 模式会覆盖文件原有内容
            - append 模式会在文件末尾追加内容
            - 如果文件不存在，会自动创建（包括父目录）
        """
        tool_name = "file_write"

        resolved_path, error = check_permission(provider, tool_name, path, OperationType.WRITE)
        if error:
            return error

        try:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

            write_mode = 'w' if mode == "overwrite" else 'a'

            with open(resolved_path, write_mode, encoding=encoding) as f:
                f.write(content)

            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.WRITE,
                extra={
                    "mode": mode,
                    "encoding": encoding,
                    "content_length": len(content)
                }
            )

            return "Success: File written successfully"

        except PermissionError as e:
            error_msg = f"Error: Permission denied when writing file: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.WRITE,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to write file: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.WRITE,
                error=error_msg
            )
            return error_msg

    return file_write
