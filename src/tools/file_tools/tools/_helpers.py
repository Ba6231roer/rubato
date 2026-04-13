from pathlib import Path
from typing import Optional, Tuple

from src.tools.file_tools.audit import OperationType


def check_permission(
    provider,
    tool_name: str,
    path: str,
    operation: OperationType
) -> Tuple[Optional[Path], Optional[str]]:
    permission_result = provider.check_permission(path, operation)

    if not permission_result.allowed:
        provider.log_denied(
            tool_name=tool_name,
            path=path,
            operation=operation,
            reason=permission_result.reason or "Permission denied"
        )
        return None, f"Error: Permission denied - {permission_result.reason}"

    return permission_result.resolved_path, None


def check_dual_permission(
    provider,
    tool_name: str,
    src: str,
    dst: str,
    src_operation: OperationType,
    dst_operation: OperationType
) -> Tuple[Optional[Path], Optional[Path], Optional[str]]:
    src_result = provider.check_permission(src, src_operation)
    if not src_result.allowed:
        provider.log_denied(
            tool_name=tool_name,
            path=src,
            operation=src_operation,
            reason=src_result.reason or "Permission denied"
        )
        return None, None, f"Error: Permission denied for source - {src_result.reason}"

    dst_result = provider.check_permission(dst, dst_operation)
    if not dst_result.allowed:
        provider.log_denied(
            tool_name=tool_name,
            path=dst,
            operation=dst_operation,
            reason=dst_result.reason or "Permission denied"
        )
        return None, None, f"Error: Permission denied for destination - {dst_result.reason}"

    return src_result.resolved_path, dst_result.resolved_path, None
