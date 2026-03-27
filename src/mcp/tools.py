import warnings
from langchain_core.tools import BaseTool
from typing import List, Dict, Optional, Callable, Union, Protocol, runtime_checkable


@runtime_checkable
class ToolProvider(Protocol):
    """工具提供者协议"""
    def get_tools(self) -> List[BaseTool]:
        """获取工具列表"""
        ...


ProviderType = Union[Callable[[], List[BaseTool]], ToolProvider]


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._providers: List[ProviderType] = []
        self._tools: Dict[str, BaseTool] = {}
    
    def register_provider(self, provider: ProviderType) -> None:
        """注册工具提供者"""
        self._providers.append(provider)
    
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
        """获取所有工具（从直接注册的工具和所有提供者获取）"""
        tools_dict: Dict[str, BaseTool] = dict(self._tools)
        for provider in self._providers:
            if callable(provider):
                provider_tools = provider()
            else:
                provider_tools = provider.get_tools()
            for tool in provider_tools:
                if tool.name not in tools_dict:
                    tools_dict[tool.name] = tool
        return list(tools_dict.values())
    
    def get_tools_by_names(self, names: List[str]) -> List[BaseTool]:
        """根据名称列表获取工具"""
        all_tools = self.get_all_tools()
        return [tool for tool in all_tools if tool.name in names]
    
    def list_tool_names(self) -> List[str]:
        """列出所有工具名称"""
        return [tool.name for tool in self.get_all_tools()]


_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表
    
    .. deprecated::
        全局注册表已废弃，请创建 ToolRegistry 实例使用。
    """
    warnings.warn(
        "get_tool_registry() is deprecated. "
        "Please create a ToolRegistry instance instead.",
        DeprecationWarning,
        stacklevel=2
    )
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def register_mcp_tools(tools: List[BaseTool]) -> None:
    """注册MCP工具到全局注册表
    
    .. deprecated::
        全局注册表已废弃，请创建 ToolRegistry 实例使用。
    """
    warnings.warn(
        "register_mcp_tools() is deprecated. "
        "Please create a ToolRegistry instance and use register_all() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    registry = get_tool_registry()
    registry.register_all(tools)


def get_all_tools() -> List[BaseTool]:
    """获取所有已注册的工具
    
    .. deprecated::
        全局注册表已废弃，请创建 ToolRegistry 实例使用。
    """
    warnings.warn(
        "get_all_tools() is deprecated. "
        "Please create a ToolRegistry instance and use get_all_tools() method instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_tool_registry().get_all_tools()


def get_tools_by_names(names: List[str]) -> List[BaseTool]:
    """根据名称列表获取已注册的工具
    
    .. deprecated::
        全局注册表已废弃，请创建 ToolRegistry 实例使用。
    """
    warnings.warn(
        "get_tools_by_names() is deprecated. "
        "Please create a ToolRegistry instance and use get_tools_by_names() method instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_tool_registry().get_tools_by_names(names)
