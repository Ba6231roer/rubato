import json
import pytest
import pytest_asyncio
from pathlib import Path
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


class TestFileReferenceResolution:
    @pytest.mark.asyncio
    async def test_no_references(self):
        from src.api.websocket import _resolve_file_references
        result = await _resolve_file_references("hello world")
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_nonexistent_file_reference(self):
        from src.api.websocket import _resolve_file_references
        result = await _resolve_file_references("@workspace/nonexistent_file.txt")
        assert "@workspace/nonexistent_file.txt: [文件不存在]" in result

    @pytest.mark.asyncio
    async def test_valid_file_reference(self, tmp_path):
        from src.api.websocket import _resolve_file_references
        test_file = tmp_path / "workspace" / "test.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("hello from file", encoding="utf-8")
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            result = await _resolve_file_references("@workspace/test.md")
            assert "@workspace/test.md: hello from file" in result
            assert "--- 文件" not in result
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_single_file_with_user_text(self, tmp_path):
        from src.api.websocket import _resolve_file_references
        test_file = tmp_path / "workspace" / "note.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("file content here", encoding="utf-8")
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            result = await _resolve_file_references("@workspace/note.txt please review this")
            assert result.startswith("@workspace/note.txt: file content here")
            assert "\n\nplease review this" in result
            file_part, user_part = result.split("\n\n", 1)
            assert "file content here" in file_part
            assert user_part == "please review this"
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_multiple_file_references(self, tmp_path):
        from src.api.websocket import _resolve_file_references
        (tmp_path / "workspace").mkdir(parents=True)
        file_a = tmp_path / "workspace" / "a.txt"
        file_b = tmp_path / "workspace" / "b.txt"
        file_a.write_text("content A", encoding="utf-8")
        file_b.write_text("content B", encoding="utf-8")
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            result = await _resolve_file_references("@workspace/a.txt @workspace/b.txt compare them")
            file_part, user_part = result.split("\n\n", 1)
            lines = file_part.split("  \n")
            assert any("@workspace/a.txt: content A" in line for line in lines)
            assert any("@workspace/b.txt: content B" in line for line in lines)
            assert user_part == "compare them"
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_file_read_failure(self, tmp_path):
        from src.api.websocket import _resolve_file_references
        test_file = tmp_path / "workspace" / "broken.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("data", encoding="utf-8")
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            with patch("src.tools.file_converter.convert_to_text", side_effect=PermissionError("access denied")):
                result = await _resolve_file_references("@workspace/broken.txt")
            assert "@workspace/broken.txt: [文件读取失败: access denied]" in result
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_backslash_path_reference(self, tmp_path):
        from src.api.websocket import _resolve_file_references
        test_file = tmp_path / "workspace" / "knowledge" / "test.md"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("backslash content", encoding="utf-8")
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            result = await _resolve_file_references("@workspace\\knowledge\\test.md")
            assert "@workspace/knowledge/test.md: backslash content" in result
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_backslash_path_nonexistent(self):
        from src.api.websocket import _resolve_file_references
        result = await _resolve_file_references("@workspace\\nonexistent\\file.txt")
        assert "@workspace/nonexistent/file.txt: [文件不存在]" in result


class TestContextCompressedMessage:
    def test_context_compressed_in_task_stream(self, app):
        mock_state = MagicMock()
        mock_agent = AsyncMock()

        async def fake_stream(content):
            from collections import namedtuple
            SdkMsg = namedtuple("SdkMsg", ["type", "content"])
            yield SdkMsg(type="context_compressed", content="上下文已压缩")
            yield SdkMsg(type="assistant", content="final answer")

        mock_agent.run_stream_structured = fake_stream
        mock_state.agent = mock_agent

        with patch("src.api.websocket.get_app_state", return_value=mock_state), \
             patch("src.api.websocket._current_task", None):
            client = TestClient(app)
            with client.websocket_connect("/ws") as ws:
                connected_msg = ws.receive_json()
                assert connected_msg["type"] == "connected"

                ws.send_json({"type": "task", "content": "test task"})

                messages = []
                for _ in range(10):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] in ("done", "error", "interrupted"):
                        break

                types = [m["type"] for m in messages]
                assert "context_compressed" in types
