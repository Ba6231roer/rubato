import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langchain_core.tools import BaseTool

from src.tools.mcp_provider import MCPToolProvider
from src.mcp.errors import MCPConnectionError


def _make_mock_manager(connected=False, tools=None):
    manager = Mock()
    manager.is_connected = connected
    manager.connect = AsyncMock()
    manager.disconnect = AsyncMock()
    manager.get_tools = Mock(return_value=tools or [])
    return manager


class TestMCPToolProviderInit:
    """MCPToolProvider 初始化和配置测试"""

    def test_init_with_config_only(self):
        config = {"server1": {"enabled": True}}
        provider = MCPToolProvider(mcp_config=config)
        assert provider.mcp_manager is None
        assert provider.is_initialized is False
        assert provider.get_tools() == []

    def test_init_with_config_and_manager(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager()
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        assert provider.mcp_manager is manager

    def test_init_empty_config(self):
        provider = MCPToolProvider(mcp_config={})
        assert provider.is_available() is False

    def test_init_no_manager(self):
        provider = MCPToolProvider(mcp_config={"server1": {"enabled": True}})
        assert provider.is_available() is False


class TestMCPToolProviderGetTools:
    """MCPToolProvider get_tools 测试"""

    def test_get_tools_no_config_returns_empty(self):
        provider = MCPToolProvider(mcp_config={})
        assert provider.get_tools() == []

    def test_get_tools_no_manager_returns_empty(self):
        provider = MCPToolProvider(mcp_config={"server1": {"enabled": True}})
        assert provider.get_tools() == []

    def test_get_tools_manager_not_connected(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=False)
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)

        with patch.object(provider, '_try_sync_connect', return_value=False):
            tools = provider.get_tools()
        assert tools == []

    def test_get_tools_manager_connected(self):
        config = {"server1": {"enabled": True}}
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "mcp_tool_1"
        manager = _make_mock_manager(connected=True, tools=[mock_tool])
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)

        tools = provider.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "mcp_tool_1"
        assert provider.is_initialized is True

    def test_get_tools_cached_after_first_call(self):
        config = {"server1": {"enabled": True}}
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "mcp_tool_1"
        manager = _make_mock_manager(connected=True, tools=[mock_tool])
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)

        tools1 = provider.get_tools()
        tools2 = provider.get_tools()
        assert tools1 is tools2
        manager.get_tools.assert_called_once()

    def test_get_tools_connection_error_returns_empty(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=True)
        manager.get_tools.side_effect = MCPConnectionError("fail")
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)

        tools = provider.get_tools()
        assert tools == []


class TestMCPToolProviderIsAvailable:
    """MCPToolProvider is_available 测试"""

    def test_not_available_without_config(self):
        provider = MCPToolProvider(mcp_config={})
        assert provider.is_available() is False

    def test_not_available_without_manager(self):
        provider = MCPToolProvider(mcp_config={"server1": {"enabled": True}})
        assert provider.is_available() is False

    def test_not_available_manager_not_connected(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=False)
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        assert provider.is_available() is False

    def test_available_when_connected(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=True)
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        assert provider.is_available() is True


class TestMCPToolProviderServerConfig:
    """MCPToolProvider 服务器配置测试"""

    def test_get_server_names(self):
        config = {"server1": {"enabled": True}, "server2": {"enabled": False}}
        provider = MCPToolProvider(mcp_config=config)
        names = provider.get_server_names()
        assert "server1" in names
        assert "server2" in names

    def test_get_server_names_empty_config(self):
        provider = MCPToolProvider(mcp_config={})
        assert provider.get_server_names() == []

    def test_is_server_enabled(self):
        config = {"server1": {"enabled": True}, "server2": {"enabled": False}}
        provider = MCPToolProvider(mcp_config=config)
        assert provider.is_server_enabled("server1") is True
        assert provider.is_server_enabled("server2") is False

    def test_is_server_enabled_missing_key(self):
        config = {"server1": {"enabled": True}}
        provider = MCPToolProvider(mcp_config=config)
        assert provider.is_server_enabled("unknown") is False


class TestMCPToolProviderSetManager:
    """MCPToolProvider set_mcp_manager 测试"""

    def test_set_mcp_manager_resets_state(self):
        config = {"server1": {"enabled": True}}
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "mcp_tool"
        manager1 = _make_mock_manager(connected=True, tools=[mock_tool])
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager1)

        provider.get_tools()
        assert provider.is_initialized is True

        manager2 = _make_mock_manager(connected=False)
        provider.set_mcp_manager(manager2)
        assert provider.is_initialized is False
        assert provider.mcp_manager is manager2


class TestMCPToolProviderRefresh:
    """MCPToolProvider refresh_tools 测试"""

    def test_refresh_tools_resets_and_reloads(self):
        config = {"server1": {"enabled": True}}
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "mcp_tool"
        manager = _make_mock_manager(connected=True, tools=[mock_tool])
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)

        provider.get_tools()
        assert provider.is_initialized is True

        with patch.object(provider, 'get_tools', return_value=[mock_tool]) as mock_get:
            result = provider.refresh_tools()
            mock_get.assert_called_once()


class TestMCPToolProviderAsync:
    """MCPToolProvider 异步方法测试"""

    @pytest.mark.asyncio
    async def test_async_connect_success(self):
        config = {"server1": {"enabled": True}}
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "mcp_tool"
        manager = _make_mock_manager(connected=False, tools=[mock_tool])

        async def fake_connect():
            manager.is_connected = True

        manager.connect = AsyncMock(side_effect=fake_connect)
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)

        result = await provider.async_connect()
        assert result is True
        assert provider.is_initialized is True

    @pytest.mark.asyncio
    async def test_async_connect_no_manager(self):
        provider = MCPToolProvider(mcp_config={"server1": {"enabled": True}})
        result = await provider.async_connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_async_connect_already_connected(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=True)
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        result = await provider.async_connect()
        assert result is True
        manager.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_connect_failure(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=False)
        manager.connect = AsyncMock(side_effect=MCPConnectionError("fail"))
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        result = await provider.async_connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_async_get_tools_no_config(self):
        provider = MCPToolProvider(mcp_config={})
        tools = await provider.async_get_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_async_get_tools_connected(self):
        config = {"server1": {"enabled": True}}
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "mcp_tool"
        manager = _make_mock_manager(connected=True, tools=[mock_tool])
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        tools = await provider.async_get_tools()
        assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_async_disconnect(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=True)
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        provider._initialized = True

        await provider.async_disconnect()
        assert provider.is_initialized is False
        manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_disconnect_with_close_browser(self):
        config = {"server1": {"enabled": True}}
        manager = _make_mock_manager(connected=True)
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)

        await provider.async_disconnect(close_browser=True)
        manager.disconnect.assert_called_once_with(close_browser=True)

    @pytest.mark.asyncio
    async def test_async_refresh_tools(self):
        config = {"server1": {"enabled": True}}
        mock_tool = Mock(spec=BaseTool)
        mock_tool.name = "mcp_tool"
        manager = _make_mock_manager(connected=True, tools=[mock_tool])
        provider = MCPToolProvider(mcp_config=config, mcp_manager=manager)
        provider._initialized = True

        tools = await provider.async_refresh_tools()
        assert provider.is_initialized is True
