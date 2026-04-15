import fnmatch
import logging
import re
from pathlib import Path
from typing import Optional, List

from langchain_core.tools import tool

from src.tools.file_tools.audit import OperationType
from src.tools.file_tools.tools._helpers import check_permission


def create_file_search_tool(provider):
    logger = logging.getLogger(__name__)

    @tool
    def file_search(
        path: str,
        pattern: str,
        file_pattern: Optional[str] = None,
        recursive: bool = True,
        encoding: str = "utf-8"
    ) -> str:
        """搜索文件内容

        Args:
            path: 搜索起始路径（相对于项目根目录或绝对路径）
            pattern: 搜索模式（支持正则表达式）
            file_pattern: 文件名匹配模式（支持通配符，如 *.py），可选
            recursive: 是否递归搜索子目录，默认 True
            encoding: 文件编码，默认 utf-8

        Returns:
            搜索结果，格式为 "文件路径:行号:匹配内容"，失败返回错误信息

        注意：
            - pattern 支持正则表达式语法
            - 默认递归搜索所有子目录
            - 使用 file_pattern 可以限制搜索的文件类型
        """
        tool_name = "file_search"

        resolved_path, error = check_permission(provider, tool_name, path, OperationType.SEARCH)
        if error:
            return error

        try:
            if not resolved_path.exists():
                provider.log_error(
                    tool_name=tool_name,
                    path=path,
                    operation=OperationType.SEARCH,
                    error="Path does not exist"
                )
                return f"Error: Path does not exist: {path}"

            try:
                regex = re.compile(pattern)
            except re.error as e:
                return f"Error: Invalid regex pattern: {str(e)}"

            results: List[str] = []
            files_searched = 0
            matches_found = 0

            search_path = resolved_path if resolved_path.is_dir() else resolved_path.parent

            if resolved_path.is_file():
                files_to_search = [resolved_path]
            else:
                if recursive:
                    files_to_search = [f for f in search_path.rglob('*') if f.is_file()]
                else:
                    files_to_search = [f for f in search_path.iterdir() if f.is_file()]

            for file_path in files_to_search:
                if provider.is_excluded(file_path):
                    continue

                if file_pattern and not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue

                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        files_searched += 1
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                relative_path = file_path.relative_to(resolved_path) if resolved_path.is_dir() else file_path.name
                                results.append(f"{relative_path}:{line_num}:{line.rstrip()}")
                                matches_found += 1
                except (UnicodeDecodeError, PermissionError):
                    continue
                except Exception:
                    continue

            if results:
                result_text = '\n'.join(results)
                result_text += f"\n\nSearched {files_searched} files, found {matches_found} matches"
            else:
                result_text = f"No matches found in {files_searched} files"

            provider.log_success(
                tool_name=tool_name,
                path=path,
                operation=OperationType.SEARCH,
                extra={
                    "pattern": pattern,
                    "file_pattern": file_pattern,
                    "recursive": recursive,
                    "files_searched": files_searched,
                    "matches_found": matches_found
                }
            )

            return result_text

        except PermissionError as e:
            error_msg = f"Error: Permission denied when searching: {str(e)}"
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.SEARCH,
                error=error_msg
            )
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to search: {str(e)}"
            logger.exception(f"Unexpected error in {tool_name}")
            provider.log_error(
                tool_name=tool_name,
                path=path,
                operation=OperationType.SEARCH,
                error=error_msg
            )
            return error_msg

    return file_search
