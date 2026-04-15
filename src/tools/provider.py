from abc import ABC, abstractmethod
from typing import List, Any
from langchain_core.tools import BaseTool
from .shell import RubatoShellTool


class ToolProvider(ABC):
    """工具提供者抽象基类
    
    定义工具提供者的标准接口，用于统一管理不同来源的工具。
    """
    
    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """获取工具列表
        
        Returns:
            List[BaseTool]: 工具实例列表
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查工具是否可用
        
        Returns:
            bool: 工具是否可用
        """
        pass


class LocalToolProvider(ToolProvider):
    """本地工具提供者
    
    用于提供本地定义的工具，如 spawn_agent 等。
    接受工具类或工具实例列表，返回对应的工具实例。
    """
    
    def __init__(self, tool_classes: List[Any] = None):
        """初始化本地工具提供者
        
        Args:
            tool_classes: 工具类或工具实例列表
                - 可以是 @tool 装饰的函数（会自动转换为 StructuredTool）
                - 可以是 BaseTool 的子类
                - 可以是 BaseTool 的实例
        """
        self._tool_classes = tool_classes or []
        self._tools: List[BaseTool] = []
        self._initialize_tools()
    
    def _initialize_tools(self) -> None:
        for tool_item in self._tool_classes:
            if isinstance(tool_item, BaseTool):
                self._tools.append(tool_item)
            elif isinstance(tool_item, type) and issubclass(tool_item, BaseTool):
                self._tools.append(tool_item())
    
    def get_tools(self) -> List[BaseTool]:
        """获取工具列表
        
        Returns:
            List[BaseTool]: 本地工具实例列表
        """
        return self._tools
    
    def is_available(self) -> bool:
        """检查工具是否可用
        
        本地工具始终可用。
        
        Returns:
            bool: 始终返回 True
        """
        return True
    
    def add_tool(self, tool: Any) -> None:
        self._tool_classes.append(tool)
        if isinstance(tool, BaseTool):
            self._tools.append(tool)
        elif isinstance(tool, type) and issubclass(tool, BaseTool):
            self._tools.append(tool())


class ShellToolProvider(ToolProvider):
    """Shell工具提供者
    
    用于提供 ShellTool 实例，用于执行 shell 命令。
    """
    
    def __init__(self):
        """初始化 Shell 工具提供者"""
        self._tool: BaseTool = RubatoShellTool()
    
    def get_tools(self) -> List[BaseTool]:
        """获取工具列表
        
        Returns:
            List[BaseTool]: 包含 ShellTool 实例的列表
        """
        return [self._tool]
    
    def is_available(self) -> bool:
        """检查 ShellTool 是否可用
        
        Returns:
            bool: ShellTool 是否可用
        """
        try:
            return self._tool is not None
        except Exception:
            return False
