import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from src.mcp.client import MCPManager, _DEFAULT_RETRY_TIMES, _DEFAULT_RETRY_DELAY, _DEFAULT_TIMEOUT
from src.mcp.errors import MCPConnectionError


def _make_config(server_name="test_server", command="test_cmd", args=None, connection=None):
    config = {
        server_name: {
            "command": command,
            "args": args or [],
        }
    }
    if connection:
        config[server_name]["connection"] = connection
    return config


def _make_mock_tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


class TestMCPManagerInit:
    def test_default_state(self):
        manager = MCPManager(config={})
        assert manager.is_connected is False
        assert manager.browser_alive is False
        assert manager._client is None
        assert manager._tools == []
        assert manager._sessions == {}
        assert manager._session_cms == {}

    def test_config_stored(self):
        config = _make_config()
        manager = MCPManager(config=config)
        assert manager.config is config


class TestMCPManagerParseConnectionConfig:
    def test_defaults(self):
        retry, delay, timeout = MCPManager._parse_connection_config({})
        assert retry == _DEFAULT_RETRY_TIMES
        assert delay == _DEFAULT_RETRY_DELAY
        assert timeout == _DEFAULT_TIMEOUT

    def test_custom_values(self):
        cfg = {"retry_times": 5, "retry_delay": 10, "timeout": 60}
        retry, delay, timeout = MCPManager._parse_connection_config(cfg)
        assert retry == 5
        assert delay == 10
        assert timeout == 60

    def test_partial_override(self):
        cfg = {"timeout": 99}
        retry, delay, timeout = MCPManager._parse_connection_config(cfg)
        assert retry == _DEFAULT_RETRY_TIMES
        assert delay == _DEFAULT_RETRY_DELAY
        assert timeout == 99


class TestMCPManagerConnect:
    @pytest.mark.asyncio
    async def test_connect_empty_config_raises(self):
        manager = MCPManager(config={})
        with pytest.raises(MCPConnectionError, match="MCP配置为空"):
            await manager.connect()

    @pytest.mark.asyncio
    async def test_connect_no_valid_servers_raises(self):
        config = {"server1": {"not_command": "x"}}
        manager = MCPManager(config=config)
        with pytest.raises(MCPConnectionError, match="没有有效的MCP服务器配置"):
            await manager.connect()

    @pytest.mark.asyncio
    async def test_connect_all_servers_fail_raises(self):
        config = _make_config()
        manager = MCPManager(config=config)
        mock_client = MagicMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("connect fail"))
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client):
            with pytest.raises(MCPConnectionError, match="无法连接任何MCP服务器"):
                await manager.connect()

    @pytest.mark.asyncio
    async def test_connect_success(self):
        config = _make_config()
        manager = MCPManager(config=config)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_tool = _make_mock_tool("test_tool")

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client), \
             patch("src.mcp.client.load_mcp_tools", return_value=[mock_tool]):
            await manager.connect()

        assert manager.is_connected is True
        assert len(manager._tools) == 1
        assert manager._tools[0].name == "test_tool"

    @pytest.mark.asyncio
    async def test_connect_playwright_sets_browser_alive(self):
        config = _make_config(server_name="playwright", command="npx.cmd")
        manager = MCPManager(config=config)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_tool = _make_mock_tool("browser_click")

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client), \
             patch("src.mcp.client.load_mcp_tools", return_value=[mock_tool]):
            await manager.connect()

        assert manager.browser_alive is True

    @pytest.mark.asyncio
    async def test_connect_non_playwright_no_browser(self):
        config = _make_config(server_name="other_server", command="cmd")
        manager = MCPManager(config=config)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client), \
             patch("src.mcp.client.load_mcp_tools", return_value=[]):
            await manager.connect()

        assert manager.browser_alive is False

    @pytest.mark.asyncio
    async def test_connect_skips_non_dict_server_config(self):
        config = {"bad_server": "not_a_dict", "good_server": {"command": "cmd", "args": []}}
        manager = MCPManager(config=config)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client), \
             patch("src.mcp.client.load_mcp_tools", return_value=[]):
            await manager.connect()

        assert manager.is_connected is True
        mock_client.session.assert_called_once_with("good_server")


class TestMCPManagerGetTools:
    @pytest.mark.asyncio
    async def test_get_tools_when_not_connected_raises(self):
        manager = MCPManager(config={})
        with pytest.raises(MCPConnectionError, match="MCP未连接"):
            manager.get_tools()

    @pytest.mark.asyncio
    async def test_get_tools_returns_tools(self):
        config = _make_config()
        manager = MCPManager(config=config)
        mock_tool = _make_mock_tool("t1")
        manager._tools = [mock_tool]
        manager._connected = True
        tools = manager.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "t1"


class TestMCPManagerBrowserLifecycle:
    @pytest.mark.asyncio
    async def test_check_browser_alive_no_session(self):
        manager = MCPManager(config={})
        result = await manager.check_browser_alive()
        assert result is False
        assert manager.browser_alive is False

    @pytest.mark.asyncio
    async def test_check_browser_alive_success(self):
        manager = MCPManager(config={})
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=None)
        manager._sessions["playwright"] = mock_session

        result = await manager.check_browser_alive()
        assert result is True
        assert manager.browser_alive is True
        mock_session.call_tool.assert_called_once_with("browser_snapshot", {})

    @pytest.mark.asyncio
    async def test_check_browser_alive_failure(self):
        manager = MCPManager(config={})
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(side_effect=Exception("browser gone"))
        manager._sessions["playwright"] = mock_session

        result = await manager.check_browser_alive()
        assert result is False
        assert manager.browser_alive is False

    @pytest.mark.asyncio
    async def test_close_browser_no_session(self):
        manager = MCPManager(config={})
        result = await manager.close_browser()
        assert result is False

    @pytest.mark.asyncio
    async def test_close_browser_success(self):
        manager = MCPManager(config={})
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=None)
        manager._sessions["playwright"] = mock_session
        manager._browser_alive = True

        result = await manager.close_browser()
        assert result is True
        assert manager.browser_alive is False
        mock_session.call_tool.assert_called_once_with("browser_close", {})

    @pytest.mark.asyncio
    async def test_close_browser_failure(self):
        manager = MCPManager(config={})
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(side_effect=Exception("close fail"))
        manager._sessions["playwright"] = mock_session

        result = await manager.close_browser()
        assert result is False


class TestMCPManagerDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_resets_state(self):
        config = _make_config()
        manager = MCPManager(config=config)
        manager._connected = True
        manager._tools = [_make_mock_tool("t1")]
        manager._sessions = {"test_server": AsyncMock()}
        manager._session_cms = {"test_server": AsyncMock()}
        manager._client = MagicMock()

        await manager.disconnect()

        assert manager.is_connected is False
        assert manager._tools == []
        assert manager._client is None
        assert manager._sessions == {}
        assert manager._session_cms == {}

    @pytest.mark.asyncio
    async def test_disconnect_with_close_browser(self):
        config = _make_config(server_name="playwright")
        manager = MCPManager(config=config)
        manager._connected = True
        manager._browser_alive = True
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=None)
        manager._sessions["playwright"] = mock_session
        manager._session_cms["playwright"] = AsyncMock()
        manager._client = MagicMock()

        await manager.disconnect(close_browser=True)

        assert manager.browser_alive is False

    @pytest.mark.asyncio
    async def test_disconnect_without_close_browser(self):
        config = _make_config(server_name="playwright")
        manager = MCPManager(config=config)
        manager._connected = True
        manager._browser_alive = True
        manager._sessions["playwright"] = AsyncMock()
        manager._session_cms["playwright"] = AsyncMock()
        manager._client = MagicMock()

        await manager.disconnect(close_browser=False)

        assert manager.browser_alive is True


class TestMCPManagerContextManager:
    @pytest.mark.asyncio
    async def test_aenter_calls_connect(self):
        config = _make_config()
        manager = MCPManager(config=config)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client), \
             patch("src.mcp.client.load_mcp_tools", return_value=[]):
            async with manager as m:
                assert m.is_connected is True

    @pytest.mark.asyncio
    async def test_aexit_calls_disconnect(self):
        config = _make_config()
        manager = MCPManager(config=config)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client), \
             patch("src.mcp.client.load_mcp_tools", return_value=[]):
            async with manager:
                pass

        assert manager.is_connected is False


class TestMCPManagerEnsureBrowser:
    @pytest.mark.asyncio
    async def test_ensure_browser_already_alive(self):
        manager = MCPManager(config=_make_config(server_name="playwright"))
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=None)
        manager._sessions["playwright"] = mock_session
        manager._browser_alive = True

        result = await manager.ensure_browser()
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_browser_no_playwright_config(self):
        manager = MCPManager(config=_make_config(server_name="other"))
        manager._sessions = {}
        manager._browser_alive = False

        result = await manager.ensure_browser()
        assert result is False

    @pytest.mark.asyncio
    async def test_ensure_browser_reconnect_success(self):
        config = _make_config(server_name="playwright", command="npx.cmd")
        manager = MCPManager(config=config)
        manager._browser_alive = False

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_tool = _make_mock_tool("browser_click")

        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        mock_client = MagicMock()
        mock_client.session.return_value = mock_session_cm

        with patch("src.mcp.client.MultiServerMCPClient", return_value=mock_client), \
             patch("src.mcp.client.load_mcp_tools", return_value=[mock_tool]):
            manager._client = mock_client
            manager._sessions = {}
            manager._session_cms = {}

            async def fake_check():
                manager._browser_alive = True
                return True

            with patch.object(manager, "check_browser_alive", side_effect=fake_check):
                pass

            result = await manager._connect_single_server("playwright", {})
            assert result is True


class TestMCPManagerCleanupServerSession:
    @pytest.mark.asyncio
    async def test_cleanup_removes_session(self):
        manager = MCPManager(config={})
        mock_cm = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        manager._session_cms["srv"] = mock_cm
        manager._sessions["srv"] = MagicMock()

        await manager._cleanup_server_session("srv")

        assert "srv" not in manager._sessions
        assert "srv" not in manager._session_cms

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_no_error(self):
        manager = MCPManager(config={})
        await manager._cleanup_server_session("nonexistent")

    @pytest.mark.asyncio
    async def test_cleanup_handles_exit_exception(self):
        manager = MCPManager(config={})
        mock_cm = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(side_effect=Exception("exit fail"))
        manager._session_cms["srv"] = mock_cm
        manager._sessions["srv"] = MagicMock()

        await manager._cleanup_server_session("srv")

        assert "srv" not in manager._sessions
