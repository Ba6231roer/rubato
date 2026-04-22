import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def workspace_dir(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "test_cases").mkdir()
    (ws / "knowledge").mkdir()
    (ws / "test_cases" / "sample.md").write_text("# Test Case\n\nSample test case content", encoding="utf-8")
    (ws / "test_cases" / "data.txt").write_text("Plain text content", encoding="utf-8")
    (ws / "knowledge" / "guide.md").write_text("# Guide\n\nKnowledge base guide", encoding="utf-8")
    return ws


class TestWorkspaceTree:
    def test_tree_returns_structure(self, client, workspace_dir):
        with patch("src.api.routes.workspace.get_workspace_path", return_value=workspace_dir):
            response = client.get("/api/workspace/tree")
            assert response.status_code == 200
            data = response.json()
            assert len(data) > 0
            folder_names = [n["name"] for n in data]
            assert "test_cases" in folder_names
            assert "knowledge" in folder_names

    def test_tree_empty_when_no_workspace(self, client, tmp_path):
        with patch("src.api.routes.workspace.get_workspace_path", return_value=tmp_path / "nonexistent"):
            response = client.get("/api/workspace/tree")
            assert response.status_code == 200
            assert response.json() == []

    def test_tree_includes_multiple_formats(self, client, workspace_dir):
        (workspace_dir / "test_cases" / "sample.docx").write_bytes(b"fake docx")
        with patch("src.api.routes.workspace.get_workspace_path", return_value=workspace_dir):
            response = client.get("/api/workspace/tree")
            assert response.status_code == 200
            data = response.json()
            tc_folder = next(n for n in data if n["name"] == "test_cases")
            file_names = [c["name"] for c in tc_folder["children"]]
            assert "sample.md" in file_names
            assert "data.txt" in file_names
            assert "sample.docx" in file_names


class TestWorkspaceFile:
    def test_get_text_file(self, client, workspace_dir):
        with patch("src.api.routes.workspace.get_workspace_path", return_value=workspace_dir):
            response = client.get("/api/workspace/file?path=test_cases/sample.md")
            assert response.status_code == 200
            data = response.json()
            assert data["editable"] is True
            assert data["file_type"] == "text"
            assert "Test Case" in data["content"]

    def test_get_non_text_file(self, client, workspace_dir):
        (workspace_dir / "test_cases" / "sample.docx").write_bytes(b"fake docx")
        with patch("src.api.routes.workspace.get_workspace_path", return_value=workspace_dir):
            response = client.get("/api/workspace/file?path=test_cases/sample.docx")
            assert response.status_code == 200
            data = response.json()
            assert data["editable"] is False
            assert data["file_type"] == "document"

    def test_get_nonexistent_file(self, client, workspace_dir):
        with patch("src.api.routes.workspace.get_workspace_path", return_value=workspace_dir):
            response = client.get("/api/workspace/file?path=nonexistent.md")
            assert response.status_code == 404

    def test_save_text_file(self, client, workspace_dir):
        with patch("src.api.routes.workspace.get_workspace_path", return_value=workspace_dir):
            response = client.put("/api/workspace/file", json={
                "path": "test_cases/sample.md",
                "content": "# Updated Content"
            })
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_save_non_text_file_rejected(self, client, workspace_dir):
        (workspace_dir / "test_cases" / "sample.docx").write_bytes(b"fake docx")
        with patch("src.api.routes.workspace.get_workspace_path", return_value=workspace_dir):
            response = client.put("/api/workspace/file", json={
                "path": "test_cases/sample.docx",
                "content": "should not work"
            })
            assert response.status_code == 400
