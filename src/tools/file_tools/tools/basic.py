import logging
import shutil
from pathlib import Path

from langchain_core.tools import tool

from src.tools.file_tools.audit import OperationType
from src.tools.file_tools.tools._helpers import check_permission, check_dual_permission


def create_file_exists_tool(provider):
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

        resolved_path, error = check_permission(provider, tool_name, path, OperationType.EXISTS)
        if error:
            return error

        try:
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

        resolved_path, error = check_permission(provider, tool_name, path, OperationType.DELETE)
        if error:
            return error

        try:
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
        path_log = f"{src} -> {dst}"

        src_path, dst_path, error = check_dual_permission(
            provider, tool_name, src, dst, OperationType.READ, OperationType.WRITE
        )
        if error:
            return error

        try:
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
                path=path_log,
                operation=OperationType.COPY
            )

            return "Success: Copied successfully"

        except PermissionError as e:
            error_msg = f"Error: Permission denied when copying: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path_log,
                operation=OperationType.COPY,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to copy: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path_log,
                operation=OperationType.COPY,
                error=error_msg
            )
            return error_msg

    return file_copy


def create_file_move_tool(provider):
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
        path_log = f"{src} -> {dst}"

        src_path, dst_path, error = check_dual_permission(
            provider, tool_name, src, dst, OperationType.READ, OperationType.WRITE
        )
        if error:
            return error

        try:
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
                path=path_log,
                operation=OperationType.MOVE
            )

            return "Success: Moved successfully"

        except PermissionError as e:
            error_msg = f"Error: Permission denied when moving: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path_log,
                operation=OperationType.MOVE,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to move: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path_log,
                operation=OperationType.MOVE,
                error=error_msg
            )
            return error_msg

    return file_move


def create_file_mkdir_tool(provider):
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

        resolved_path, error = check_permission(provider, tool_name, path, OperationType.MKDIR)
        if error:
            return error

        try:
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
