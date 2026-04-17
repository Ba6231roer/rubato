import json
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.websocket import ConnectionManager


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def sync_client(app):
    return TestClient(app)


class TestConnectionManager:
    def test_init(self):
        mgr = ConnectionManager()
        assert mgr.active_connections == []

    @pytest.mark.asyncio
    async def test_connect(self):
        mgr = ConnectionManager()
        mock_ws = AsyncMock()
        await mgr.connect(mock_ws)
        assert mock_ws in mgr.active_connections
        mock_ws.accept.assert_awaited_once()

    def test_disconnect(self):
        mgr = ConnectionManager()
        mock_ws = MagicMock()
        mgr.active_connections.append(mock_ws)
        mgr.disconnect(mock_ws)
        assert mock_ws not in mgr.active_connections

    def test_disconnect_not_in_list(self):
        mgr = ConnectionManager()
        mock_ws = MagicMock()
        mgr.disconnect(mock_ws)
        assert len(mgr.active_connections) == 0

    @pytest.mark.asyncio
    async def test_send_message(self):
        mgr = ConnectionManager()
        mock_ws = AsyncMock()
        message = {"type": "test", "content": "hello"}
        await mgr.send_message(mock_ws, message)
        mock_ws.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast(self):
        mgr = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        mgr.active_connections = [ws1, ws2]
        message = {"type": "broadcast", "content": "all"}
        await mgr.broadcast(message)
        ws1.send_json.assert_awaited_once_with(message)
        ws2.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_empty(self):
        mgr = ConnectionManager()
        message = {"type": "test", "content": "none"}
        await mgr.broadcast(message)


class TestWebSocketEndpoint:
    def test_websocket_connect_and_ping(self, sync_client):
        with sync_client.websocket_connect("/ws") as ws:
            connected_msg = ws.receive_json()
            assert connected_msg["type"] == "connected"

            ws.send_json({"type": "ping", "content": ""})
            pong_msg = ws.receive_json()
            assert pong_msg["type"] == "pong"

    def test_websocket_unknown_message_type(self, sync_client):
        with sync_client.websocket_connect("/ws") as ws:
            connected_msg = ws.receive_json()
            assert connected_msg["type"] == "connected"

            ws.send_json({"type": "unknown_type", "content": "test"})
            error_msg = ws.receive_json()
            assert error_msg["type"] == "error"
            assert "未知消息类型" in error_msg["content"]

    def test_websocket_invalid_json(self, sync_client):
        with sync_client.websocket_connect("/ws") as ws:
            connected_msg = ws.receive_json()
            assert connected_msg["type"] == "connected"

            ws.send_text("not valid json{{{")
            error_msg = ws.receive_json()
            assert error_msg["type"] == "error"
            assert "无效的消息格式" in error_msg["content"]

    def test_websocket_command_no_dispatcher(self, app):
        with patch("src.api.websocket._dispatcher", None):
            client = TestClient(app)
            with client.websocket_connect("/ws") as ws:
                connected_msg = ws.receive_json()
                assert connected_msg["type"] == "connected"

                ws.send_json({"type": "command", "content": "/help"})
                error_msg = ws.receive_json()
                assert error_msg["type"] == "error"
                assert "未初始化" in error_msg["content"]

    def test_websocket_task_no_state(self, app):
        with patch("src.api.websocket.get_app_state", return_value=None):
            client = TestClient(app)
            with client.websocket_connect("/ws") as ws:
                connected_msg = ws.receive_json()
                assert connected_msg["type"] == "connected"

                ws.send_json({"type": "task", "content": "do something"})
                error_msg = ws.receive_json()
                assert error_msg["type"] == "error"
                assert "未初始化" in error_msg["content"]

    def test_websocket_task_no_agent(self, app):
        mock_state = MagicMock()
        mock_state.agent = None
        with patch("src.api.websocket.get_app_state", return_value=mock_state):
            client = TestClient(app)
            with client.websocket_connect("/ws") as ws:
                connected_msg = ws.receive_json()
                assert connected_msg["type"] == "connected"

                ws.send_json({"type": "task", "content": "do something"})
                error_msg = ws.receive_json()
                assert error_msg["type"] == "error"
                assert "Agent未初始化" in error_msg["content"]


class TestWebSocketModuleState:
    def test_set_and_get_app_state(self):
        from src.api.websocket import set_app_state, get_app_state

        mock_state = MagicMock()
        set_app_state(mock_state)
        assert get_app_state() is mock_state

        set_app_state(None)
        assert get_app_state() is None

    def test_init_command_dispatcher(self):
        from src.api.websocket import init_command_dispatcher, get_dispatcher
        from src.commands import CommandContext

        context = CommandContext()
        init_command_dispatcher(context)
        dispatcher = get_dispatcher()
        assert dispatcher is not None
