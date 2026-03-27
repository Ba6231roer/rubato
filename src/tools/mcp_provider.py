import asyncio
from typing import List, Optional, Dict, Any
from langchain_core.tools import BaseTool

from .provider import ToolProvider
from ..mcp.client import MCPManager
from ..mcp.errors import MCPConnectionError


class MCPToolProvider(ToolProvider):
    """MCP工具提供者
    
    用于提供MCP服务器的工具，支持异步连接和工具缓存。
    支持多个MCP服务器配置。
    """
    
    def __init__(
        self,
        mcp_config: Dict[str, Any],
        mcp_manager: Optional[MCPManager] = None
    ):
        """初始化MCP工具提供者
        
        Args:
            mcp_config: MCP配置字典，包含服务器配置信息
            mcp_manager: 可选的MCPManager实例，如果提供则直接使用
        """
        self._mcp_config = mcp_config
        self._mcp_manager = mcp_manager
        self._tools: List[BaseTool] = []
        self._initialized = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    @property
    def mcp_manager(self) -> Optional[MCPManager]:
        """获取MCP管理器实例"""
        return self._mcp_manager
    
    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    def is_available(self) -> bool:
        """检查MCP是否可用
        
        检查条件：
        1. MCP配置存在且启用
        2. MCPManager实例存在
        3. 已连接到MCP服务器
        
        Returns:
            bool: MCP是否可用
        """
        if not self._mcp_config:
            return False
        
        if not self._mcp_manager:
            return False
        
        return self._mcp_manager.is_connected
    
    def get_tools(self) -> List[BaseTool]:
        """获取MCP工具列表
        
        如果MCP禁用，返回空列表。
        如果MCP启用但未连接，尝试同步连接（如果可能）。
        如果已连接，返回缓存的工具列表。
        
        Returns:
            List[BaseTool]: MCP工具列表
        """
        if not self._mcp_config:
            return []
        
        if not self._mcp_manager:
            return []
        
        if not self._mcp_manager.is_connected:
            if not self._try_sync_connect():
                return []
        
        if self._initialized and self._tools:
            return self._tools
        
        try:
            self._tools = self._mcp_manager.get_tools()
            self._initialized = True
            return self._tools
        except MCPConnectionError:
            return []
    
    def _try_sync_connect(self) -> bool:
        """尝试同步连接MCP服务器
        
        Returns:
            bool: 连接是否成功
        """
        if not self._mcp_manager:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return False
            
            loop.run_until_complete(self._mcp_manager.connect())
            return self._mcp_manager.is_connected
        except RuntimeError:
            return False
        except MCPConnectionError:
            return False
        except Exception:
            return False
    
    async def async_connect(self) -> bool:
        """异步连接MCP服务器
        
        Returns:
            bool: 连接是否成功
        """
        if not self._mcp_manager:
            return False
        
        if self._mcp_manager.is_connected:
            return True
        
        try:
            await self._mcp_manager.connect()
            self._tools = self._mcp_manager.get_tools()
            self._initialized = True
            return True
        except MCPConnectionError:
            return False
        except Exception:
            return False
    
    async def async_get_tools(self) -> List[BaseTool]:
        """异步获取MCP工具列表
        
        如果未连接，会先尝试连接。
        
        Returns:
            List[BaseTool]: MCP工具列表
        """
        if not self._mcp_config:
            return []
        
        if not self._mcp_manager:
            return []
        
        if not self._mcp_manager.is_connected:
            await self.async_connect()
        
        if not self._mcp_manager.is_connected:
            return []
        
        try:
            self._tools = self._mcp_manager.get_tools()
            self._initialized = True
            return self._tools
        except MCPConnectionError:
            return []
    
    async def async_disconnect(self, close_browser: bool = False) -> None:
        """异步断开MCP连接
        
        Args:
            close_browser: 是否关闭浏览器
        """
        if self._mcp_manager and self._mcp_manager.is_connected:
            await self._mcp_manager.disconnect(close_browser=close_browser)
            self._tools = []
            self._initialized = False
    
    def refresh_tools(self) -> List[BaseTool]:
        """刷新工具列表
        
        强制重新获取工具列表。
        
        Returns:
            List[BaseTool]: 刷新后的工具列表
        """
        self._initialized = False
        self._tools = []
        return self.get_tools()
    
    async def async_refresh_tools(self) -> List[BaseTool]:
        """异步刷新工具列表
        
        强制重新获取工具列表。
        
        Returns:
            List[BaseTool]: 刷新后的工具列表
        """
        self._initialized = False
        self._tools = []
        return await self.async_get_tools()
    
    def set_mcp_manager(self, mcp_manager: MCPManager) -> None:
        """设置MCP管理器实例
        
        Args:
            mcp_manager: MCPManager实例
        """
        self._mcp_manager = mcp_manager
        self._initialized = False
        self._tools = []
    
    def get_server_names(self) -> List[str]:
        """获取配置的MCP服务器名称列表
        
        Returns:
            List[str]: 服务器名称列表
        """
        if not self._mcp_config:
            return []
        
        return list(self._mcp_config.keys())
    
    def is_server_enabled(self, server_name: str) -> bool:
        """检查指定服务器是否启用
        
        Args:
            server_name: 服务器名称
            
        Returns:
            bool: 服务器是否启用
        """
        if not self._mcp_config:
            return False
        
        server_config = self._mcp_config.get(server_name, {})
        return server_config.get("enabled", False)
