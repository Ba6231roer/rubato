from typing import Any, Dict

_CONCURRENCY_SAFE_TOOLS: Dict[str, bool] = {
    "spawn_agent": True,
}


def is_concurrency_safe(tool_name: str, tool_instance: Any = None, tool_args: Dict[str, Any] = None) -> bool:
    """Check if a tool call is safe to execute concurrently with other tool calls.

    Default is False (not safe). Only tools explicitly marked as safe can be parallelized.

    Args:
        tool_name: Name of the tool
        tool_instance: Optional tool instance for future conditional logic
        tool_args: Optional tool arguments for future conditional logic

    Returns:
        True if the tool can safely run concurrently, False otherwise
    """
    return _CONCURRENCY_SAFE_TOOLS.get(tool_name, False)
