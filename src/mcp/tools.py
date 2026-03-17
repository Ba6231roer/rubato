from langchain_core.tools import BaseTool
from typing import List, Dict, Optional


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
    
    def register_all(self, tools: List[BaseTool]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register(tool)
    
    def unregister(self, name: str) -> None:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取指定工具"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def get_tools_by_names(self, names: List[str]) -> List[BaseTool]:
        """根据名称列表获取工具"""
        return [self._tools[name] for name in names if name in self._tools]
    
    def list_tool_names(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())


_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def register_mcp_tools(tools: List[BaseTool]) -> None:
    """注册MCP工具到全局注册表"""
    registry = get_tool_registry()
    registry.register_all(tools)


def get_all_tools() -> List[BaseTool]:
    """获取所有已注册的工具"""
    return get_tool_registry().get_all_tools()


def get_tools_by_names(names: List[str]) -> List[BaseTool]:
    """根据名称列表获取已注册的工具"""
    return get_tool_registry().get_tools_by_names(names)
