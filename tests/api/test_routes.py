import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestConfigsEndpoint:
    @pytest.mark.asyncio
    async def test_list_configs(self, client):
        response = await client.get("/api/configs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        names = [c["name"] for c in data]
        assert "model" in names
        assert "mcp" in names
        assert "prompt" in names
        assert "skills" in names
        assert "test" in names

    @pytest.mark.asyncio
    async def test_list_configs_item_structure(self, client):
        response = await client.get("/api/configs")
        data = response.json()
        for item in data:
            assert "name" in item
            assert "file" in item
            assert "description" in item

    @pytest.mark.asyncio
    async def test_get_config_not_found_name(self, client):
        response = await client.get("/api/configs/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_config_not_found_file(self, client):
        with patch("src.api.routes.configs.CONFIG_DIR") as mock_dir:
            from pathlib import Path
            mock_dir.__truediv__ = lambda self, other: Path("/nonexistent") / other
            response = await client.get("/api/configs/model")
            assert response.status_code == 404


class TestSessionsEndpoint:
    @pytest.mark.asyncio
    async def test_list_sessions_no_agent(self, client):
        with patch("src.api.routes.sessions.get_app_state", return_value=None):
            response = await client.get("/api/sessions")
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_list_sessions_agent_no_session_storage(self, client):
        mock_state = MagicMock()
        mock_state.agent = MagicMock()
        mock_state.agent.get_session_storage.return_value = None
        with patch("src.api.routes.sessions.get_app_state", return_value=mock_state):
            response = await client.get("/api/sessions")
            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_sessions_with_data(self, client):
        mock_meta = MagicMock()
        mock_meta.session_id = "s1"
        mock_meta.role = "tester"
        mock_meta.model = "gpt-4"
        mock_meta.message_count = 3
        mock_meta.created_at = "2025-01-01T00:00:00"
        mock_meta.updated_at = "2025-01-02T00:00:00"
        mock_meta.description = "test"
        mock_meta.parent_session_id = None

        mock_storage = MagicMock()
        mock_storage.list_sessions.return_value = [mock_meta]

        mock_state = MagicMock()
        mock_state.agent = MagicMock()
        mock_state.agent.get_session_storage.return_value = mock_storage

        with patch("src.api.routes.sessions.get_app_state", return_value=mock_state):
            response = await client.get("/api/sessions")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["session_id"] == "s1"
            assert data[0]["role"] == "tester"

    @pytest.mark.asyncio
    async def test_get_session_no_agent(self, client):
        with patch("src.api.routes.sessions.get_app_state", return_value=None):
            response = await client.get("/api/sessions/s1")
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client):
        mock_storage = MagicMock()
        mock_storage.get_session_metadata.return_value = None

        mock_state = MagicMock()
        mock_state.agent = MagicMock()
        mock_state.agent.get_session_storage.return_value = mock_storage

        with patch("src.api.routes.sessions.get_app_state", return_value=mock_state):
            response = await client.get("/api/sessions/nonexistent")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_load_session_no_agent(self, client):
        with patch("src.api.routes.sessions.get_app_state", return_value=None):
            response = await client.post("/api/sessions/s1/load")
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_load_session_no_storage(self, client):
        mock_state = MagicMock()
        mock_state.agent = MagicMock()
        mock_state.agent.get_session_storage.return_value = None

        with patch("src.api.routes.sessions.get_app_state", return_value=mock_state):
            response = await client.post("/api/sessions/s1/load")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "未初始化" in data["message"]

    @pytest.mark.asyncio
    async def test_load_session_not_exists(self, client):
        mock_storage = MagicMock()
        mock_storage.session_exists.return_value = False

        mock_state = MagicMock()
        mock_state.agent = MagicMock()
        mock_state.agent.get_session_storage.return_value = mock_storage

        with patch("src.api.routes.sessions.get_app_state", return_value=mock_state):
            response = await client.post("/api/sessions/nonexistent/load")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_load_session_success(self, client):
        mock_storage = MagicMock()
        mock_storage.session_exists.return_value = True
        mock_storage.load_session_with_meta.return_value = (MagicMock(), [])

        mock_state = MagicMock()
        mock_state.agent = MagicMock()
        mock_state.agent.get_session_storage.return_value = mock_storage
        mock_state.agent.load_session.return_value = True

        with patch("src.api.routes.sessions.get_app_state", return_value=mock_state):
            response = await client.post("/api/sessions/s1/load")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["session_id"] == "s1"

    @pytest.mark.asyncio
    async def test_load_session_agent_failure(self, client):
        mock_storage = MagicMock()
        mock_storage.session_exists.return_value = True

        mock_state = MagicMock()
        mock_state.agent = MagicMock()
        mock_state.agent.get_session_storage.return_value = mock_storage
        mock_state.agent.load_session.return_value = False

        with patch("src.api.routes.sessions.get_app_state", return_value=mock_state):
            response = await client.post("/api/sessions/s1/load")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False


class TestWorkspaceEndpoint:
    @pytest.mark.asyncio
    async def test_get_workspace_tree_no_path(self, client):
        with patch("src.api.routes.workspace.get_workspace_path") as mock_path:
            from pathlib import Path
            mock_path.return_value = Path("/nonexistent_dir_xyz")
            response = await client.get("/api/workspace/tree")
            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_workspace_file_not_found(self, client):
        with patch("src.api.routes.workspace.get_workspace_path") as mock_path:
            from pathlib import Path
            mock_path.return_value = Path("/nonexistent_dir_xyz")
            response = await client.get("/api/workspace/file", params={"path": "test.md"})
            assert response.status_code == 404


class TestCommandsEndpoint:
    @pytest.mark.asyncio
    async def test_list_commands(self, client):
        response = await client.get("/api/commands")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for cmd in data:
            assert "name" in cmd
            assert "aliases" in cmd
            assert "description" in cmd
            assert "usage" in cmd

    @pytest.mark.asyncio
    async def test_execute_command_no_dispatcher(self, client):
        with patch("src.api.routes.commands._dispatcher", None):
            response = await client.post("/api/command", json={"command": "/help"})
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_execute_command_invalid_format(self, client):
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "type": "error",
            "message": "Not a valid command",
            "data": None,
            "actions": [],
        }
        mock_dispatcher.dispatch = AsyncMock(return_value=None)

        with patch("src.api.routes.commands._dispatcher", mock_dispatcher):
            response = await client.post("/api/command", json={"command": "hello"})
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_execute_command_success(self, client):
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "type": "info",
            "message": "帮助信息",
            "data": None,
            "actions": [],
        }
        mock_dispatcher.dispatch = AsyncMock(return_value=mock_result)

        with patch("src.api.routes.commands._dispatcher", mock_dispatcher):
            response = await client.post("/api/command", json={"command": "/help"})
            assert response.status_code == 200
            data = response.json()
            assert data["type"] == "info"
            assert data["message"] == "帮助信息"
