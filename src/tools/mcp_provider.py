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
        self._mcp_config = mcp_config
        self._mcp_manager = mcp_manager
        self._tools: List[BaseTool] = []
        self._initialized = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def mcp_manager(self) -> Optional[MCPManager]:
        return self._mcp_manager

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _has_config_and_manager(self) -> bool:
        return bool(self._mcp_config) and bool(self._mcp_manager)

    def _reset_state(self) -> None:
        self._initialized = False
        self._tools = []

    def is_available(self) -> bool:
        if not self._has_config_and_manager():
            return False
        return self._mcp_manager.is_connected

    def get_tools(self) -> List[BaseTool]:
        if not self._has_config_and_manager():
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
        if not self._mcp_manager:
            return False

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return False

            loop.run_until_complete(self._mcp_manager.connect())
            return self._mcp_manager.is_connected
        except (RuntimeError, MCPConnectionError, Exception):
            return False

    async def async_connect(self) -> bool:
        if not self._mcp_manager:
            return False

        if self._mcp_manager.is_connected:
            return True

        try:
            await self._mcp_manager.connect()
            self._tools = self._mcp_manager.get_tools()
            self._initialized = True
            return True
        except (MCPConnectionError, Exception):
            return False

    async def async_get_tools(self) -> List[BaseTool]:
        if not self._has_config_and_manager():
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
        if self._mcp_manager and self._mcp_manager.is_connected:
            await self._mcp_manager.disconnect(close_browser=close_browser)
            self._reset_state()

    def refresh_tools(self) -> List[BaseTool]:
        self._reset_state()
        return self.get_tools()

    async def async_refresh_tools(self) -> List[BaseTool]:
        self._reset_state()
        return await self.async_get_tools()

    def set_mcp_manager(self, mcp_manager: MCPManager) -> None:
        self._mcp_manager = mcp_manager
        self._reset_state()

    def get_server_names(self) -> List[str]:
        if not self._mcp_config:
            return []
        return list(self._mcp_config.keys())

    def is_server_enabled(self, server_name: str) -> bool:
        if not self._mcp_config:
            return False
        server_config = self._mcp_config.get(server_name, {})
        return server_config.get("enabled", False)
